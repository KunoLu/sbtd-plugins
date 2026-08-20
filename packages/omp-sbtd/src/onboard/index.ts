import { createHash, randomUUID } from "node:crypto";
import { lstat, mkdir, open, readFile, rename, rm } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { z } from "zod";
import {
  type AgentTarget,
  type ManagedAssetState,
  type ManagedBlockOwnership,
  mergeManagedBlock,
  normalizeManagedBlockContent,
  resolveAgentTargets,
  sha256,
} from "../agents/index.js";

export const kitSnapshotSchema = z
  .object({
    sourceId: z.string().min(1),
    sourceRevision: z.string().regex(/^[0-9a-f]{40}$/),
    transformVersion: z.string().min(1),
    kitRevision: z.string().min(1),
    templates: z
      .object({
        global: z.string(),
        "project-root": z.string(),
        "project-omp": z.string(),
      })
      .strict(),
  })
  .strict();
export type KitSnapshot = z.infer<typeof kitSnapshotSchema>;

const inventorySchema = z
  .object({
    schemaVersion: z.literal(1),
    revision: z.string().regex(/^[0-9a-f]{64}$/),
    operationId: z.string().min(1),
    assets: z.array(
      z
        .object({
          path: z.string().min(1),
          role: z.enum(["global", "project-root", "project-omp"]),
          sourceId: z.string().min(1),
          sourceRevision: z.string().regex(/^[0-9a-f]{40}$/),
          transformVersion: z.string().min(1),
          digest: z.string().regex(/^[0-9a-f]{64}$/),
        })
        .strict(),
    ),
  })
  .strict();
const planTargetSchema = z
  .object({
    target: z
      .object({
        role: z.enum(["global", "project-root", "project-omp"]),
        path: z.string().min(1),
      })
      .strict(),
    priorState: z.enum([
      "absent",
      "exact",
      "drifted",
      "merge-required",
      "blocked",
    ]),
    observedDigest: z.string().regex(/^[0-9a-f]{64}$/),
    proposedDigest: z.string().regex(/^[0-9a-f]{64}$/),
    action: z.enum(["write", "skip", "blocked"]),
    backup: z.literal("transaction journal"),
    recovery: z.string().min(1),
  })
  .strict();
const onboardPlanSchema = z
  .object({
    schemaVersion: z.literal(1),
    operationId: z.string().min(1),
    createdAt: z.string().datetime(),
    expiresAt: z.string().datetime(),
    digest: z.string().regex(/^[0-9a-f]{64}$/),
    kit: kitSnapshotSchema.omit({ templates: true }),
    inventoryPath: z.string().min(1),
    inventoryDigest: z.string().regex(/^[0-9a-f]{64}$/),
    targets: z.array(planTargetSchema),
    proposedFiles: z.record(z.string(), z.string()),
  })
  .strict();

const journalBackupSchema = z
  .object({
    path: z.string().min(1),
    backupPath: z.string().min(1).optional(),
    digest: z.string().regex(/^[0-9a-f]{64}$/),
    exists: z.boolean(),
  })
  .strict();
const transactionJournalSchema = z
  .object({
    schemaVersion: z.literal(1),
    operationId: z.string().min(1),
    phase: z.enum([
      "prepared",
      "writing",
      "inventory",
      "rolling-back",
      "rolled-back",
      "repair-required",
      "complete",
    ]),
    planDigest: z.string().regex(/^[0-9a-f]{64}$/),
    backups: z.array(journalBackupSchema),
    written: z.array(z.string().min(1)),
    inFlight: z.string().min(1).optional(),
    residuals: z.array(z.string().min(1)),
  })
  .strict();
type TransactionJournal = z.infer<typeof transactionJournalSchema>;
const recoveryPointerSchema = z
  .object({
    schemaVersion: z.literal(1),
    journalPath: z.string().min(1),
  })
  .strict();

export interface FileAdapter {
  readonly readText: (path: string) => Promise<string | undefined>;
  readonly writeAtomic: (path: string, content: string) => Promise<void>;
  readonly makeDirectory: (path: string) => Promise<void>;
  readonly exists: (path: string) => Promise<boolean>;
  readonly remove: (path: string) => Promise<void>;
  readonly isSymlink: (path: string) => Promise<boolean>;
}

export interface OnboardPlanTarget {
  readonly target: AgentTarget;
  readonly priorState: ManagedAssetState;
  readonly observedDigest: string;
  readonly proposedDigest: string;
  readonly action: "write" | "skip" | "blocked";
  readonly backup: "transaction journal";
  readonly recovery: string;
}

export interface OnboardPlan {
  readonly schemaVersion: 1;
  readonly operationId: string;
  readonly createdAt: string;
  readonly expiresAt: string;
  readonly digest: string;
  readonly kit: Omit<KitSnapshot, "templates">;
  readonly inventoryPath: string;
  readonly inventoryDigest: string;
  readonly targets: readonly OnboardPlanTarget[];
  readonly proposedFiles: Readonly<Record<string, string>>;
}

export interface ApplyResult {
  readonly kind:
    | "cancelled"
    | "stale"
    | "blocked"
    | "applied"
    | "rolled-back"
    | "repair-required";
  readonly message: string;
  readonly reloadRequired: boolean;
  readonly residuals: readonly string[];
}

export interface OnboardRecovery {
  readonly kind: "none" | "repair-required";
  readonly operationId?: string;
  readonly phase?: string;
  readonly journalPath?: string;
  readonly backups: readonly string[];
  readonly residuals: readonly string[];
  readonly repairPath: string;
}

export interface OnboardService {
  readonly plan: () => Promise<OnboardPlan>;
  readonly inspectRecovery: () => Promise<OnboardRecovery>;
  readonly recover: () => Promise<ApplyResult>;
  readonly apply: (
    plan: OnboardPlan,
    confirmed: boolean,
  ) => Promise<ApplyResult>;
}

export interface OnboardInputs {
  readonly projectRoot: string;
  readonly scope?: "all" | "projects";
  readonly agentDirectory: string;
  readonly kit: unknown;
  readonly files: FileAdapter;
  readonly now: () => string;
  readonly operationId?: () => string;
}

function planDigest(parts: readonly string[]): string {
  return createHash("sha256").update(parts.join("\u0000")).digest("hex");
}

export function createNodeFileAdapter(): FileAdapter {
  return {
    async readText(path) {
      try {
        return await readFile(path, "utf8");
      } catch (error: unknown) {
        if ((error as NodeJS.ErrnoException).code === "ENOENT")
          return undefined;
        throw error;
      }
    },
    async writeAtomic(path, content) {
      const temporary = `${path}.kpi-${randomUUID()}.tmp`;
      await mkdir(dirname(path), { recursive: true });
      const temporaryFile = await open(temporary, "w", 0o600);
      try {
        await temporaryFile.writeFile(content, "utf8");
        await temporaryFile.sync();
      } finally {
        await temporaryFile.close();
      }
      await rename(temporary, path);
      const parentDirectory = await open(dirname(path), "r");
      try {
        await parentDirectory.sync();
      } finally {
        await parentDirectory.close();
      }
    },
    async exists(path) {
      try {
        await lstat(path);
        return true;
      } catch (error: unknown) {
        if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
        throw error;
      }
    },
    async makeDirectory(path) {
      await mkdir(dirname(path), { recursive: true });
      await mkdir(path);
    },
    async remove(path) {
      await rm(path, { recursive: true, force: true });
    },
    async isSymlink(path) {
      try {
        return (await lstat(path)).isSymbolicLink();
      } catch (error: unknown) {
        if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
        throw error;
      }
    },
  };
}

export function createOnboardService(inputs: OnboardInputs): OnboardService {
  const kit = kitSnapshotSchema.parse(inputs.kit);
  const projectRoot = resolve(inputs.projectRoot);
  const agentDirectory = resolve(inputs.agentDirectory);
  const targets = resolveAgentTargets(projectRoot, agentDirectory).filter(
    (target) => inputs.scope !== "projects" || target.role !== "global",
  );
  const transactionRoot = resolve(agentDirectory, "kpi/transactions");
  const recoveryPath = resolve(transactionRoot, "recovery-v1.json");
  const inventoryPath = resolve(
    agentDirectory,
    "kpi/provenance/inventory-v1.json",
  );
  const lockPath = resolve(
    transactionRoot,
    `${createHash("sha256")
      .update(
        targets
          .map((target) => target.path)
          .sort()
          .join("\u0000"),
      )
      .digest("hex")}.lock`,
  );
  const within = (candidate: string, allowedRoot: string) => {
    const relation = relative(allowedRoot, candidate);
    return (
      relation !== "" && !relation.startsWith("..") && !relation.includes("../")
    );
  };
  const safePath = async (
    candidate: string,
    allowedRoot: string,
  ): Promise<boolean> => {
    if (
      !within(candidate, allowedRoot) ||
      (await inputs.files.isSymlink(candidate))
    )
      return false;
    let parent = dirname(candidate);
    while (parent !== allowedRoot && parent !== dirname(parent)) {
      if (await inputs.files.isSymlink(parent)) return false;
      parent = dirname(parent);
    }
    return !(await inputs.files.isSymlink(allowedRoot));
  };
  const safeTarget = async (target: AgentTarget): Promise<boolean> =>
    safePath(
      target.path,
      target.role === "global" ? agentDirectory : projectRoot,
    );
  const safeRecoveryJournal = async (
    journalPath: string,
    journal: TransactionJournal,
  ): Promise<boolean> => {
    const expectedJournalPath = resolve(
      transactionRoot,
      `${journal.operationId}.journal.json`,
    );
    if (
      journalPath !== expectedJournalPath ||
      !(await safePath(journalPath, agentDirectory))
    )
      return false;
    const permittedPaths = new Set([
      inventoryPath,
      ...targets.map((target) => target.path),
    ]);
    const restoredPaths = [...journal.written, journal.inFlight].filter(
      (path): path is string => path !== undefined,
    );
    if (
      restoredPaths.some((path) => !permittedPaths.has(path)) ||
      new Set(restoredPaths).size !== restoredPaths.length
    )
      return false;
    const backupRoot = resolve(
      transactionRoot,
      `${journal.operationId}.backups`,
    );
    const backupSafety = await Promise.all(
      journal.backups.map(
        async (backup, index) =>
          permittedPaths.has(backup.path) &&
          backup.backupPath ===
            (backup.exists
              ? resolve(backupRoot, `${index}.backup`)
              : undefined) &&
          (backup.backupPath === undefined ||
            (await safePath(backup.backupPath, agentDirectory))),
      ),
    );
    return backupSafety.every(Boolean);
  };
  const inspectRecovery = async (
    ignoreLock = false,
  ): Promise<OnboardRecovery> => {
    const retainedLock = !ignoreLock && (await inputs.files.exists(lockPath));
    const withLock = (residuals: readonly string[]) =>
      retainedLock ? [...new Set([...residuals, lockPath])] : [...residuals];
    const pointerText = await inputs.files.readText(recoveryPath);
    if (pointerText === undefined) {
      if (retainedLock)
        return {
          kind: "repair-required",
          backups: [],
          residuals: [lockPath],
          repairPath:
            "Confirm /sbtd onboard reset to remove the retained KPi target-set lock.",
        };
      return {
        kind: "none",
        backups: [],
        residuals: [],
        repairPath: "/sbtd onboard plan",
      };
    }
    const pointer = recoveryPointerSchema.safeParse(
      (() => {
        try {
          return JSON.parse(pointerText);
        } catch {
          return undefined;
        }
      })(),
    );
    if (
      !pointer.success ||
      !(await safePath(pointer.data.journalPath, agentDirectory))
    )
      return {
        kind: "repair-required",
        journalPath: pointer.success ? pointer.data.journalPath : recoveryPath,
        backups: [],
        residuals: withLock([recoveryPath]),
        repairPath:
          "Repair the KPi recovery pointer, then run /sbtd onboard reset.",
      };
    const journalText = await inputs.files.readText(pointer.data.journalPath);
    const journal = transactionJournalSchema.safeParse(
      (() => {
        try {
          return journalText === undefined
            ? undefined
            : JSON.parse(journalText);
        } catch {
          return undefined;
        }
      })(),
    );
    if (!journal.success)
      return {
        kind: "repair-required",
        journalPath: pointer.data.journalPath,
        backups: [],
        residuals: withLock([pointer.data.journalPath]),
        repairPath:
          "Repair the KPi transaction journal, then run /sbtd onboard reset.",
      };
    if (!(await safeRecoveryJournal(pointer.data.journalPath, journal.data)))
      return {
        kind: "repair-required",
        journalPath: pointer.data.journalPath,
        backups: [],
        residuals: withLock([pointer.data.journalPath]),
        repairPath:
          "Repair the KPi transaction journal capabilities, then run /sbtd onboard reset.",
      };
    if (journal.data.phase === "complete" && !retainedLock)
      return {
        kind: "none",
        operationId: journal.data.operationId,
        phase: journal.data.phase,
        journalPath: pointer.data.journalPath,
        backups: [],
        residuals: [],
        repairPath: "/sbtd onboard plan",
      };
    return {
      kind: "repair-required",
      operationId: journal.data.operationId,
      phase: journal.data.phase,
      journalPath: pointer.data.journalPath,
      backups: journal.data.backups
        .map((backup) => backup.backupPath)
        .filter((path): path is string => path !== undefined),
      residuals: withLock(journal.data.residuals),
      repairPath:
        "Review the persisted transaction facts, then confirm /sbtd onboard reset.",
    };
  };
  const recover = async (): Promise<ApplyResult> => {
    const recovery = await inspectRecovery();
    if (recovery.kind === "none")
      return {
        kind: "blocked",
        message: "No incomplete Onboard transaction requires recovery.",
        reloadRequired: false,
        residuals: [],
      };
    const removeRetainedLock = async (): Promise<readonly string[]> => {
      if (!(await inputs.files.exists(lockPath))) return [];
      try {
        await inputs.files.remove(lockPath);
        return [];
      } catch {
        return [lockPath];
      }
    };
    if (recovery.journalPath === undefined) {
      const residuals = await removeRetainedLock();
      if (residuals.length > 0)
        return {
          kind: "repair-required",
          message:
            "The retained KPi target-set lock could not be removed during recovery.",
          reloadRequired: false,
          residuals,
        };
      return {
        kind: "rolled-back",
        message: "The retained KPi target-set lock was removed.",
        reloadRequired: false,
        residuals: [],
      };
    }
    const journalText = await inputs.files.readText(
      recovery.journalPath as string,
    );
    const journal = transactionJournalSchema.parse(
      JSON.parse(journalText as string),
    );
    if (!(await safeRecoveryJournal(recovery.journalPath as string, journal)))
      return {
        kind: "repair-required",
        message:
          "Recovery journal capabilities are unsafe; inspect the retained journal.",
        reloadRequired: false,
        residuals: [recovery.journalPath as string],
      };
    if (journal.phase === "complete") {
      await inputs.files.remove(recovery.journalPath);
      await inputs.files.remove(recoveryPath);
      const residuals = await removeRetainedLock();
      if (residuals.length > 0)
        return {
          kind: "repair-required",
          message:
            "The completed Onboard journal was cleaned up, but its retained target-set lock could not be removed.",
          reloadRequired: false,
          residuals,
        };
      return {
        kind: "rolled-back",
        message: "The completed Onboard transaction cleanup was finished.",
        reloadRequired: false,
        residuals: [],
      };
    }
    const residuals: string[] = [];
    for (const path of [
      ...new Set(
        [...journal.written, journal.inFlight]
          .filter((path): path is string => path !== undefined)
          .reverse(),
      ),
    ]) {
      const backup = journal.backups.find(
        (candidate) => candidate.path === path,
      );
      try {
        if (!backup) throw new Error("missing backup");
        if (!backup.exists) await inputs.files.remove(path);
        else {
          const content = await inputs.files.readText(
            backup.backupPath as string,
          );
          if (content === undefined || sha256(content) !== backup.digest)
            throw new Error("invalid backup");
          await inputs.files.writeAtomic(path, content);
        }
      } catch {
        residuals.push(path);
      }
    }
    if (residuals.length > 0)
      return {
        kind: "repair-required",
        message:
          "Recovery could not restore every target; inspect the retained journal.",
        reloadRequired: false,
        residuals,
      };
    await inputs.files.remove(recovery.journalPath as string);
    await inputs.files.remove(recoveryPath);
    const lockResiduals = await removeRetainedLock();
    if (lockResiduals.length > 0)
      return {
        kind: "repair-required",
        message:
          "Targets were restored, but the retained KPi target-set lock could not be removed.",
        reloadRequired: false,
        residuals: lockResiduals,
      };
    return {
      kind: "rolled-back",
      message:
        "The incomplete Onboard transaction was restored from its durable backups.",
      reloadRequired: false,
      residuals: [],
    };
  };
  const buildPlan = async (): Promise<OnboardPlan> => {
    if (
      !(await safePath(inventoryPath, agentDirectory)) ||
      !(await safePath(transactionRoot, agentDirectory)) ||
      !(await safePath(lockPath, agentDirectory))
    )
      throw new Error(
        "KPi provenance or transaction path is unsafe; repair it before onboarding.",
      );
    const inventory = await inputs.files.readText(inventoryPath);
    const inventoryAssets = new Map<string, ManagedBlockOwnership>(
      inventory === undefined
        ? []
        : inventorySchema.parse(JSON.parse(inventory)).assets.map((asset) => [
            asset.path,
            {
              role: asset.role,
              sourceId: asset.sourceId,
              sourceRevision: asset.sourceRevision,
              transformVersion: asset.transformVersion,
              installedDigest: asset.digest,
            },
          ]),
    );
    const proposedFiles: Record<string, string> = {};
    const planTargets: OnboardPlanTarget[] = [];
    for (const target of targets) {
      const targetIsSafe = await safeTarget(target);
      const existing = targetIsSafe
        ? await inputs.files.readText(target.path)
        : undefined;
      const current = existing ?? "";
      const template = kit.templates[target.role];
      const merged = targetIsSafe
        ? mergeManagedBlock(
            current,
            {
              role: target.role,
              sourceId: kit.sourceId,
              sourceRevision: kit.sourceRevision,
              transformVersion: kit.transformVersion,
              content: template,
            },
            inventoryAssets.get(target.path),
          )
        : { next: current, state: "blocked" as const };
      proposedFiles[target.path] = merged.next;
      planTargets.push({
        target,
        priorState: merged.state,
        observedDigest: sha256(current),
        proposedDigest: sha256(merged.next),
        action:
          merged.state === "blocked" || merged.state === "merge-required"
            ? "blocked"
            : merged.state === "exact"
              ? "skip"
              : "write",
        backup: "transaction journal",
        recovery:
          merged.state === "merge-required"
            ? "Reconcile the recorded provenance before onboarding."
            : merged.state === "blocked"
              ? "Repair the target path or markers, then create a new plan."
              : "Restore from the transaction journal if Apply fails.",
      });
    }
    const createdAt = inputs.now();
    const expiresAt = new Date(
      Date.parse(createdAt) + 10 * 60_000,
    ).toISOString();
    const operationId = inputs.operationId?.() ?? randomUUID();
    const identity = {
      sourceId: kit.sourceId,
      sourceRevision: kit.sourceRevision,
      transformVersion: kit.transformVersion,
      kitRevision: kit.kitRevision,
    };
    const digest = planDigest([
      JSON.stringify(identity),
      inventoryPath,
      sha256(inventory ?? ""),
      ...planTargets.map(
        (target) =>
          `${target.target.path}:${target.observedDigest}:${target.proposedDigest}:${target.action}`,
      ),
    ]);
    return {
      schemaVersion: 1,
      operationId,
      createdAt,
      expiresAt,
      digest,
      kit: identity,
      inventoryPath,
      inventoryDigest: sha256(inventory ?? ""),
      targets: planTargets,
      proposedFiles,
    };
  };
  return {
    plan: buildPlan,
    inspectRecovery,
    recover,
    async apply(plan, confirmed) {
      if (!confirmed)
        return {
          kind: "cancelled",
          message:
            "Onboard Apply was cancelled; no files or Session state changed.",
          reloadRequired: false,
          residuals: [],
        };
      const parsedPlan = onboardPlanSchema.safeParse(plan);
      if (!parsedPlan.success)
        return {
          kind: "blocked",
          message:
            "Onboard Plan is invalid; create a new plan before applying.",
          reloadRequired: false,
          residuals: [],
        };
      const acceptedPlan = parsedPlan.data;
      const journalPath = resolve(
        transactionRoot,
        `${acceptedPlan.operationId}.journal.json`,
      );
      if (!(await safePath(journalPath, agentDirectory)))
        return {
          kind: "blocked",
          message:
            "Onboard transaction path is unsafe; repair it before applying.",
          reloadRequired: false,
          residuals: [journalPath],
        };
      const priorJournal = await inputs.files.readText(journalPath);
      if (priorJournal !== undefined) {
        const journal = transactionJournalSchema.safeParse(
          (() => {
            try {
              return JSON.parse(priorJournal);
            } catch {
              return undefined;
            }
          })(),
        );
        if (
          journal.success &&
          journal.data.operationId === acceptedPlan.operationId &&
          journal.data.planDigest === acceptedPlan.digest &&
          journal.data.phase === "complete"
        )
          return {
            kind: "applied",
            message:
              "This Onboard operation is already complete. Reload OMP or start a new Session to verify the environment.",
            reloadRequired: true,
            residuals: [],
          };
      }
      if (Date.parse(acceptedPlan.expiresAt) <= Date.parse(inputs.now()))
        return {
          kind: "stale",
          message: "Plan expired; create a new plan before applying.",
          reloadRequired: false,
          residuals: [],
        };
      if (!(await safePath(lockPath, agentDirectory)))
        return {
          kind: "blocked",
          message: "Onboard lock path is unsafe; repair it before applying.",
          reloadRequired: false,
          residuals: [lockPath],
        };
      try {
        await inputs.files.makeDirectory(lockPath);
      } catch {
        return {
          kind: "blocked",
          message: `Another operation holds the target-set lock: ${lockPath}`,
          reloadRequired: false,
          residuals: [lockPath],
        };
      }
      try {
        if (!(await safePath(journalPath, agentDirectory)))
          return {
            kind: "blocked",
            message:
              "Onboard transaction path changed after locking; repair it before applying.",
            reloadRequired: false,
            residuals: [journalPath],
          };
        const recovery = await inspectRecovery(true);
        if (recovery.kind === "repair-required")
          return {
            kind: "repair-required",
            message:
              "An incomplete Onboard transaction requires review. Run /sbtd doctor, then confirm /sbtd onboard reset.",
            reloadRequired: false,
            residuals: recovery.residuals,
          };
        const existingJournal = await inputs.files.readText(journalPath);
        if (existingJournal !== undefined) {
          const journal = transactionJournalSchema.safeParse(
            (() => {
              try {
                return JSON.parse(existingJournal);
              } catch {
                return undefined;
              }
            })(),
          );
          if (
            journal.success &&
            journal.data.operationId === acceptedPlan.operationId &&
            journal.data.planDigest === acceptedPlan.digest &&
            journal.data.phase === "complete"
          )
            return {
              kind: "applied",
              message:
                "This Onboard operation is already complete. Reload OMP or start a new Session to verify the environment.",
              reloadRequired: true,
              residuals: [],
            };
          return {
            kind: "repair-required",
            message:
              "An incomplete or malformed Onboard journal exists; run /sbtd doctor and reconcile it before retrying.",
            reloadRequired: false,
            residuals: [journalPath],
          };
        }
        let fresh: OnboardPlan;
        try {
          fresh = await buildPlan();
        } catch {
          return {
            kind: "blocked",
            message:
              "Current Onboard inputs are unsafe or invalid; repair them before creating a new plan.",
            reloadRequired: false,
            residuals: [],
          };
        }
        if (fresh.digest !== acceptedPlan.digest)
          return {
            kind: "stale",
            message:
              "Plan read-set changed while waiting for the lock; no target or inventory writes were made. Create a new plan.",
            reloadRequired: false,
            residuals: [],
          };
        if (fresh.targets.some((target) => target.action === "blocked"))
          return {
            kind: "blocked",
            message: "Plan contains blocked targets; repair them before Apply.",
            reloadRequired: false,
            residuals: [],
          };
        if (fresh.targets.every((target) => target.action === "skip"))
          return {
            kind: "applied",
            message: "All Managed Assets are exact; no files were changed.",
            reloadRequired: false,
            residuals: [],
          };
        const originals = new Map<string, string | undefined>();
        const written: string[] = [];
        const backupRoot = resolve(
          transactionRoot,
          `${acceptedPlan.operationId}.backups`,
        );
        let journal: TransactionJournal | undefined;
        const writeVerified = async (path: string, content: string) => {
          await inputs.files.writeAtomic(path, content);
          if ((await inputs.files.readText(path)) !== content)
            throw new Error(`write verification failed for ${path}`);
        };
        const persistJournal = async () => {
          if (!journal) throw new Error("transaction journal is unavailable");
          await writeVerified(journalPath, JSON.stringify(journal));
        };
        try {
          originals.set(
            inventoryPath,
            await inputs.files.readText(inventoryPath),
          );
          for (const target of fresh.targets)
            originals.set(
              target.target.path,
              await inputs.files.readText(target.target.path),
            );
          await inputs.files.makeDirectory(backupRoot);
          const backups = await Promise.all(
            [...originals.entries()].map(async ([path, content], index) => {
              const backupPath =
                content === undefined
                  ? undefined
                  : resolve(backupRoot, `${index}.backup`);
              if (content !== undefined)
                await writeVerified(backupPath as string, content);
              return {
                path,
                backupPath,
                digest: sha256(content ?? ""),
                exists: content !== undefined,
              };
            }),
          );
          journal = {
            schemaVersion: 1,
            operationId: acceptedPlan.operationId,
            phase: "prepared",
            planDigest: fresh.digest,
            backups,
            written: [],
            residuals: [],
          };
          await persistJournal();
          await writeVerified(
            recoveryPath,
            JSON.stringify({ schemaVersion: 1, journalPath }),
          );
          for (const target of fresh.targets) {
            if (target.action === "skip") continue;
            journal.phase = "writing";
            journal.inFlight = target.target.path;
            await persistJournal();
            await writeVerified(
              target.target.path,
              fresh.proposedFiles[target.target.path] as string,
            );
            written.push(target.target.path);
            journal.written = [...written];
            journal.inFlight = undefined;
            await persistJournal();
          }
          journal.phase = "inventory";
          journal.inFlight = inventoryPath;
          await persistJournal();
          const selectedPaths = new Set(
            fresh.targets.map((target) => target.target.path),
          );
          const priorInventory = originals.get(inventoryPath);
          const retainedAssets =
            priorInventory === undefined
              ? []
              : inventorySchema
                  .parse(JSON.parse(priorInventory))
                  .assets.filter((asset) => !selectedPaths.has(asset.path));
          await writeVerified(
            inventoryPath,
            JSON.stringify({
              schemaVersion: 1,
              revision: fresh.digest,
              operationId: acceptedPlan.operationId,
              assets: [
                ...retainedAssets,
                ...fresh.targets.map((target) => ({
                  path: target.target.path,
                  role: target.target.role,
                  sourceId: kit.sourceId,
                  sourceRevision: kit.sourceRevision,
                  transformVersion: kit.transformVersion,
                  digest: sha256(
                    normalizeManagedBlockContent(
                      kit.templates[target.target.role],
                    ),
                  ),
                })),
              ],
            }),
          );
          written.push(inventoryPath);
          journal.written = [...written];
          journal.inFlight = undefined;
          journal.phase = "complete";
          await persistJournal();
          await inputs.files.remove(recoveryPath);
          await inputs.files.remove(backupRoot);
          return {
            kind: "applied",
            message:
              "Managed blocks installed. Reload OMP or start a new Session to verify the environment.",
            reloadRequired: true,
            residuals: [],
          };
        } catch {
          const residuals: string[] = [];
          if (journal) {
            journal.phase = "rolling-back";
            try {
              await persistJournal();
            } catch {
              residuals.push(journalPath);
            }
          }
          for (const path of [
            ...new Set(
              [...written, journal?.inFlight]
                .filter(
                  (candidate): candidate is string => candidate !== undefined,
                )
                .reverse(),
            ),
          ]) {
            try {
              const original = originals.get(path);
              if (original === undefined) await inputs.files.remove(path);
              else await inputs.files.writeAtomic(path, original);
            } catch {
              residuals.push(path);
            }
          }
          if (journal) {
            journal.inFlight = undefined;
            journal.residuals = [...residuals];
            journal.phase =
              residuals.length === 0 ? "rolled-back" : "repair-required";
            try {
              await persistJournal();
            } catch {
              residuals.push(journalPath);
            }
          }
          if (residuals.length === 0) {
            await inputs.files.remove(journalPath);
            await inputs.files.remove(recoveryPath);
            await inputs.files.remove(backupRoot);
          }
          return {
            kind: residuals.length === 0 ? "rolled-back" : "repair-required",
            message:
              "Apply failed; target and provenance writes were rolled back where possible.",
            reloadRequired: false,
            residuals,
          };
        }
      } finally {
        await inputs.files.remove(lockPath);
      }
    },
  };
}
