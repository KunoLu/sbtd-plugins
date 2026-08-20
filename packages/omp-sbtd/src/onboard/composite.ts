import { createHash, randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { z } from "zod";
import {
  applyCertifiedLeftoverCleanup,
  inventoryPackagedSkills,
} from "../skills/index.js";
import type {
  ApplyResult,
  FileAdapter,
  OnboardPlan,
  OnboardRecovery,
  OnboardService,
} from "./index.js";
import {
  type CanonicalOnboardProcess,
  type CanonicalOnboardRuntime,
  CanonicalOnboardRuntimeError,
} from "./python-runtime.js";

const sha256 = (value: string): string =>
  createHash("sha256").update(value).digest("hex");

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

/* ------------------------------------------------------------------------- */
/* Approval classes                                                           */
/* ------------------------------------------------------------------------- */

export const approvalClassSchema = z.enum([
  "managed-files",
  "shared-dependency-install",
  "mcp-config",
  "trellis-init",
  "provider-bootstrap-handoff",
]);
export type OnboardApprovalClass = z.infer<typeof approvalClassSchema>;

export const onboardApprovalSetSchema = z
  .object({
    "managed-files": z.boolean(),
    "shared-dependency-install": z.boolean(),
    "mcp-config": z.boolean(),
    "trellis-init": z.boolean(),
    "provider-bootstrap-handoff": z.boolean(),
  })
  .strict();
export type OnboardApprovalSet = z.infer<typeof onboardApprovalSetSchema>;

export const emptyApprovalSet = (): OnboardApprovalSet => ({
  "managed-files": false,
  "shared-dependency-install": false,
  "mcp-config": false,
  "trellis-init": false,
  "provider-bootstrap-handoff": false,
});

/* ------------------------------------------------------------------------- */
/* Plan schema (V2)                                                           */
/* ------------------------------------------------------------------------- */

const cliToolNameSchema = z.enum(["omp", "trellis", "gitnexus"]);

const cliToolPlanSchema = z
  .object({
    name: cliToolNameSchema,
    state: z.enum(["verified", "missing", "unknown", "out-of-scope"]),
    version: z.string().min(1).nullable(),
    action: z.enum(["verify", "install", "none"]),
    packageId: z.string().min(1).optional(),
  })
  .strict();
export type OnboardCliToolPlan = z.infer<typeof cliToolPlanSchema>;

export const builtinMcpServerIds = [
  "gitnexus",
  "chrome-devtools",
  "playwright",
] as const;
export type BuiltinMcpServerId = (typeof builtinMcpServerIds)[number];

const builtinMcpServers: Readonly<
  Record<BuiltinMcpServerId, { command: string; args: readonly string[] }>
> = {
  gitnexus: { command: "gitnexus", args: ["mcp"] },
  "chrome-devtools": { command: "npx", args: ["chrome-devtools-mcp@latest"] },
  playwright: { command: "npx", args: ["@playwright/mcp@latest"] },
};

const secretBearingPattern =
  /(api[_-]?key|token|secret|password|passwd|credential)/i;

export const customMcpEntrySchema = z
  .object({
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/),
    command: z.string().regex(/^[a-z0-9._-]+$/i),
    args: z
      .array(
        z
          .string()
          .min(1)
          .max(512)
          .refine((value) => !value.includes("\0")),
      )
      .max(16),
  })
  .strict()
  .refine(
    (entry) =>
      !secretBearingPattern.test(entry.command) &&
      entry.args.every((value) => !secretBearingPattern.test(value)),
    { message: "MCP entries must not carry secret-bearing values." },
  );
export type CustomMcpEntry = z.infer<typeof customMcpEntrySchema>;

const mcpEntryPlanSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/),
    command: z.string().min(1),
    args: z.array(z.string()),
    action: z.enum(["merge", "unchanged", "blocked"]),
    reason: z.string().min(1).optional(),
  })
  .strict();
export type OnboardMcpEntryPlan = z.infer<typeof mcpEntryPlanSchema>;

export const trellisUsernameSchema = z
  .string()
  .regex(/^[a-z0-9][a-z0-9_.-]{0,63}$/i);

const trellisProjectPlanSchema = z
  .object({
    projectRoot: z.string().min(1),
    state: z.enum(["initialized", "not-initialized"]),
    action: z.enum(["skip", "init", "blocked"]),
    reason: z.string().min(1).optional(),
    username: trellisUsernameSchema.optional(),
    bootstrapTask: z.enum([
      "absent",
      "pending",
      "running",
      "completed",
      "unknown",
    ]),
  })
  .strict();
export type OnboardTrellisProjectPlan = z.infer<
  typeof trellisProjectPlanSchema
>;

const compositeIdentitySchema = z
  .object({
    sourceId: z.string().min(1),
    sourceRevision: z.string().regex(/^[0-9a-f]{40}$/),
    transformVersion: z.string().min(1),
    kitRevision: z.string().min(1),
    projectionSha256: sha256Schema,
    pluginVersion: z.string().min(1),
    stableSet: z.string().min(1),
    canonicalRuntimeSha256: sha256Schema.nullable(),
  })
  .strict();
export type CompositeOnboardIdentity = z.infer<typeof compositeIdentitySchema>;

export const compositeOnboardPlanSchema = z
  .object({
    schemaVersion: z.literal(2),
    operationId: z.string().min(1),
    createdAt: z.string().datetime(),
    expiresAt: z.string().datetime(),
    digest: sha256Schema,
    identity: compositeIdentitySchema,
    context: z
      .object({
        scope: z.enum(["all", "projects"]),
        projectRoot: z.string().min(1),
        agentDirectory: z.string().min(1),
        onboardProfileId: z.string().min(1),
        route: z.string().min(1),
      })
      .strict(),
    agents: z.unknown(),
    skills: z
      .object({
        action: z.enum(["replace-from-embedded-stable", "out-of-scope"]),
        targetDir: z.string().min(1),
        stableSet: z.string().min(1),
        source: z.literal("embedded-stable"),
        network: z.literal(false),
      })
      .strict(),
    certifiedSkills: z
      .object({
        names: z.array(z.string().min(1)),
        packagedCount: z.number().int().nonnegative(),
        packagedDigest: sha256Schema,
        invalidSkills: z.array(z.string().min(1)),
      })
      .strict(),
    cliTools: z.array(cliToolPlanSchema),
    mcpConfigPath: z.string().min(1),
    mcpEntries: z.array(mcpEntryPlanSchema),
    trellisProjects: z.array(trellisProjectPlanSchema),
    bootstrap: z.object({ expected: z.boolean() }).strict(),
    approvalClasses: z.array(approvalClassSchema),
    readSet: sha256Schema,
  })
  .strict();
export type CompositeOnboardPlan = z.infer<typeof compositeOnboardPlanSchema>;

export interface CompositeOnboardRequest {
  readonly mcpSelections?:
    | readonly (BuiltinMcpServerId | CustomMcpEntry)[]
    | undefined;
  readonly trellisUsername?: string | undefined;
}

/* ------------------------------------------------------------------------- */
/* Results                                                                    */
/* ------------------------------------------------------------------------- */

export type CompositeParticipantStatus =
  | "applied"
  | "skipped-not-approved"
  | "not-required"
  | "blocked"
  | "failed";

export interface CompositeParticipantResult {
  readonly status: CompositeParticipantStatus;
  readonly detail: string;
}

export interface CompositeApplyResult {
  readonly kind: "cancelled" | "stale" | "blocked" | "applied" | "partial";
  readonly message: string;
  readonly reloadRequired: boolean;
  readonly operationId: string;
  readonly planDigest: string;
  readonly participants: Readonly<Record<string, CompositeParticipantResult>>;
  readonly bootstrapRequired: boolean;
  readonly residuals: readonly string[];
}

export type BootstrapTaskState =
  | "absent"
  | "pending"
  | "running"
  | "completed"
  | "unknown";

export interface BootstrapHandoffResult {
  readonly kind:
    | "cancelled"
    | "not-required"
    | "unavailable"
    | "scheduled"
    | "bootstrap-required"
    | "ready"
    | "blocked";
  readonly message: string;
  readonly operationId?: string;
  readonly projectRoot?: string;
  readonly taskState?: BootstrapTaskState;
}

/* ------------------------------------------------------------------------- */
/* Persistence                                                                */
/* ------------------------------------------------------------------------- */

const compositeOperationRecordSchema = z
  .object({
    schemaVersion: z.literal(1),
    operationId: z.string().min(1),
    planDigest: sha256Schema,
    completedAt: z.string().datetime(),
    scope: z.enum(["all", "projects"]),
    projectRoot: z.string().min(1),
    participants: z.record(
      z.string(),
      z.object({ status: z.string().min(1), detail: z.string() }).strict(),
    ),
    bootstrapRequired: z.boolean(),
    residuals: z.array(z.string().min(1)),
  })
  .strict();
type CompositeOperationRecord = z.infer<typeof compositeOperationRecordSchema>;

const bootstrapHandoffRecordSchema = z
  .object({
    schemaVersion: z.literal(1),
    operationId: z.string().min(1),
    planDigest: sha256Schema,
    projectRoot: z.string().min(1),
    state: z.enum([
      "scheduled",
      "running",
      "ready",
      "bootstrap-required",
      "blocked",
    ]),
    scheduledAt: z.string().datetime(),
    lastObservedAt: z.string().datetime(),
    taskState: z.enum(["absent", "pending", "running", "completed", "unknown"]),
  })
  .strict();
export type BootstrapHandoffRecord = z.infer<
  typeof bootstrapHandoffRecordSchema
>;

/* ------------------------------------------------------------------------- */
/* Process safety                                                             */
/* ------------------------------------------------------------------------- */

export type OnboardProcess = CanonicalOnboardProcess;

const probeTimeoutMs = 30_000;
const installTimeoutMs = 300_000;
const trellisInitTimeoutMs = 300_000;

const npmInstallSpecs: Readonly<
  Record<"trellis" | "gitnexus", { packageId: string }>
> = {
  trellis: { packageId: "@mindfoldhq/trellis@latest" },
  gitnexus: { packageId: "gitnexus@latest" },
};

export function sanitizeProcessOutput(text: string, limit = 4000): string {
  return text
    .replace(/[^\n\r\t -~]/g, "")
    .replace(
      /((?:api[_-]?key|token|secret|password|passwd|credential)\s*[:=]\s*)\S+/gi,
      "$1[redacted]",
    )
    .slice(0, limit);
}

/* Service                                                                    */
/* ------------------------------------------------------------------------- */
/* ------------------------------------------------------------------------- */

export interface BootstrapHandoffChannel {
  schedule(prompt: string): Promise<void>;
}

export interface CompositeOnboardInputs {
  readonly agents: OnboardService;
  readonly scope: "all" | "projects";
  readonly projectRoot: string;
  readonly agentDirectory: string;
  readonly globalSkillsDirectory: string;
  readonly kitBundledSkillsRoot: string;
  readonly mcpConfigPath: string;
  readonly identity: CompositeOnboardIdentity;
  readonly onboardProfileId: string;
  readonly route: string;
  readonly runtime: CanonicalOnboardRuntime | undefined;
  readonly process: OnboardProcess;
  readonly files: FileAdapter;
  readonly now: () => string;
  readonly operationId?: (() => string) | undefined;
  readonly handoff?: BootstrapHandoffChannel | undefined;
  readonly listDir?: ((path: string) => Promise<readonly string[]>) | undefined;
}

export interface CompositeOnboardService {
  plan(request: CompositeOnboardRequest): Promise<CompositeOnboardPlan>;
  apply(
    plan: CompositeOnboardPlan,
    approvals: OnboardApprovalSet,
  ): Promise<CompositeApplyResult>;
  requestBootstrap(
    planDigest: string,
    approved: boolean,
  ): Promise<BootstrapHandoffResult>;
  observeBootstrap(): Promise<readonly BootstrapHandoffRecord[]>;
  inspectRecovery(): Promise<OnboardRecovery>;
  recover(): Promise<ApplyResult>;
}

async function probeCli(
  process: OnboardProcess,
  cwd: string,
  name: "trellis" | "gitnexus",
): Promise<{ state: "verified" | "missing"; version: string | null }> {
  try {
    const result = await process.exec(name, ["--version"], {
      cwd,
      timeout: probeTimeoutMs,
    });
    if (result.killed || result.code !== 0)
      return { state: "missing", version: null };
    const firstLine = sanitizeProcessOutput(result.stdout, 200)
      .split("\n")
      .map((line) => line.trim())
      .find((line) => line.length > 0);
    return { state: "verified", version: firstLine ?? "unknown" };
  } catch {
    return { state: "missing", version: null };
  }
}

export function createCompositeOnboardService(
  inputs: CompositeOnboardInputs,
): CompositeOnboardService {
  const projectRoot = resolve(inputs.projectRoot);
  const agentDirectory = resolve(inputs.agentDirectory);
  const globalSkillsDirectory = resolve(inputs.globalSkillsDirectory);
  const mcpConfigPath = resolve(inputs.mcpConfigPath);
  const compositeRoot = resolve(agentDirectory, "kpi/composite");
  const bootstrapRoot = resolve(agentDirectory, "kpi/bootstrap");

  const operationPath = (planDigest: string) =>
    resolve(compositeRoot, `${planDigest}.json`);
  const handoffPath = (operationId: string) =>
    resolve(bootstrapRoot, `${operationId}.json`);

  const trellisWorkflowPath = (root: string) =>
    resolve(root, ".trellis/workflow.md");
  const trellisBootstrapTaskDir = (root: string) =>
    resolve(root, ".trellis/tasks/00-bootstrap-guidelines");

  async function observeTrellisBootstrapTask(
    root: string,
  ): Promise<BootstrapTaskState> {
    const taskDir = trellisBootstrapTaskDir(root);
    const taskJsonPath = resolve(taskDir, "task.json");
    if (await inputs.files.exists(taskJsonPath)) {
      const text = await inputs.files.readText(taskJsonPath);
      if (text === undefined) return "unknown";
      try {
        const parsed: unknown = JSON.parse(text);
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          !("status" in parsed)
        )
          return "unknown";
        if (parsed.status === "completed") return "completed";
        return parsed.status === "in_progress" ? "running" : "pending";
      } catch {
        return "unknown";
      }
    }
    if (await inputs.files.exists(taskDir)) return "pending";
    if (inputs.listDir !== undefined) {
      try {
        const archiveRoot = resolve(root, ".trellis/tasks/archive");
        for (const month of await inputs.listDir(archiveRoot)) {
          for (const entry of await inputs.listDir(
            resolve(archiveRoot, month),
          )) {
            if (entry.includes("00-bootstrap-guidelines")) return "completed";
          }
        }
      } catch {
        // Archive unreadable; fall through to absent.
      }
    }
    return "absent";
  }

  async function probeOmpCli(): Promise<OnboardCliToolPlan> {
    if (inputs.runtime === undefined)
      return {
        name: "omp",
        state: "unknown",
        version: null,
        action: "verify",
      };
    try {
      const result = await inputs.runtime.run({
        kind: "check-omp-cli",
        cwd: projectRoot,
      });
      if ("mode" in result && result.mode === "check-agent-cli")
        return {
          name: "omp",
          state: result.installed ? "verified" : "missing",
          version: result.version,
          action: "verify",
        };
      return {
        name: "omp",
        state: "unknown",
        version: null,
        action: "verify",
      };
    } catch {
      return {
        name: "omp",
        state: "unknown",
        version: null,
        action: "verify",
      };
    }
  }

  function resolveMcpSelections(
    request: CompositeOnboardRequest,
  ): readonly CustomMcpEntry[] {
    const selections = request.mcpSelections ?? [];
    return selections.map((selection) => {
      if (typeof selection !== "string")
        return customMcpEntrySchema.parse(selection);
      const builtin = builtinMcpServers[selection as BuiltinMcpServerId];
      if (builtin === undefined)
        throw new Error(`Unsupported OMP MCP server selection: ${selection}`);
      return {
        id: selection,
        command: builtin.command,
        args: [...builtin.args],
      };
    });
  }

  async function buildPlan(
    request: CompositeOnboardRequest,
    operationId: string,
  ): Promise<CompositeOnboardPlan> {
    const agentsPlan = await inputs.agents.plan();

    const scopeAll = inputs.scope === "all";
    const ompTool = await probeOmpCli();
    const cliTools: OnboardCliToolPlan[] = [ompTool];
    for (const name of ["trellis", "gitnexus"] as const) {
      const probe = await probeCli(inputs.process, projectRoot, name);
      cliTools.push({
        name,
        state: probe.state,
        version: probe.version,
        action:
          probe.state === "missing" && scopeAll
            ? "install"
            : probe.state === "verified"
              ? "verify"
              : "none",
        ...(probe.state === "missing" && scopeAll
          ? { packageId: npmInstallSpecs[name].packageId }
          : {}),
      });
    }

    const selectedMcp = scopeAll ? resolveMcpSelections(request) : [];
    const mcpText = await inputs.files.readText(mcpConfigPath);
    let mcpBase: Record<string, unknown> | undefined;
    let mcpMalformed = false;
    if (mcpText !== undefined) {
      try {
        const parsed: unknown = JSON.parse(mcpText);
        const candidate = parsed as Record<string, unknown>;
        if (
          typeof parsed === "object" &&
          parsed !== null &&
          !Array.isArray(parsed) &&
          (candidate.mcpServers === undefined ||
            (typeof candidate.mcpServers === "object" &&
              candidate.mcpServers !== null &&
              !Array.isArray(candidate.mcpServers)))
        )
          mcpBase = candidate;
        else mcpMalformed = true;
      } catch {
        mcpMalformed = true;
      }
    }
    const existingServers =
      mcpBase?.mcpServers === undefined
        ? {}
        : (mcpBase.mcpServers as Record<string, unknown>);
    const mcpEntries: OnboardMcpEntryPlan[] = selectedMcp.map((entry) => {
      if (mcpMalformed)
        return {
          ...entry,
          action: "blocked" as const,
          reason:
            "Existing user-level MCP configuration is malformed; repair it before merging.",
        };
      const existing = existingServers[entry.id];
      const desired = { command: entry.command, args: entry.args };
      if (
        existing !== undefined &&
        JSON.stringify(existing) === JSON.stringify(desired)
      )
        return { ...entry, action: "unchanged" as const };
      return { ...entry, action: "merge" as const };
    });

    const trellisInitialized = await inputs.files.exists(
      resolve(projectRoot, ".trellis"),
    );
    const bootstrapTask = trellisInitialized
      ? await observeTrellisBootstrapTask(projectRoot)
      : "absent";
    const username = request.trellisUsername;
    const usernameParse =
      username === undefined
        ? undefined
        : trellisUsernameSchema.safeParse(username);
    const trellisProjects: OnboardTrellisProjectPlan[] = [
      trellisInitialized
        ? { projectRoot, state: "initialized", action: "skip", bootstrapTask }
        : username === undefined || usernameParse?.success !== true
          ? {
              projectRoot,
              state: "not-initialized",
              action: "blocked",
              reason:
                "A confirmed developer username is required before Trellis initialization.",
              bootstrapTask: "absent",
            }
          : {
              projectRoot,
              state: "not-initialized",
              action: "init",
              username: usernameParse.data,
              bootstrapTask: "absent",
            },
    ];

    const bootstrapExpected = trellisProjects.some(
      (project) =>
        project.action === "init" ||
        project.bootstrapTask === "pending" ||
        project.bootstrapTask === "unknown",
    );

    const skills = {
      action: scopeAll
        ? ("replace-from-embedded-stable" as const)
        : ("out-of-scope" as const),
      targetDir: globalSkillsDirectory,
      stableSet: inputs.identity.stableSet,
      source: "embedded-stable" as const,
      network: false as const,
    };
    const packaged = await inventoryPackagedSkills();
    const certifiedSkills = {
      names: [...packaged.names],
      packagedCount: packaged.packagedCount,
      packagedDigest: packaged.packagedDigest,
      invalidSkills: [...packaged.invalidSkills],
    };

    const approvalClasses: OnboardApprovalClass[] = ["managed-files"];
    if (cliTools.some((tool) => tool.action === "install"))
      approvalClasses.push("shared-dependency-install");
    if (mcpEntries.some((entry) => entry.action === "merge"))
      approvalClasses.push("mcp-config");
    if (trellisProjects.some((project) => project.action === "init"))
      approvalClasses.push("trellis-init");
    if (bootstrapExpected) approvalClasses.push("provider-bootstrap-handoff");
    const context = {
      scope: inputs.scope,
      projectRoot,
      agentDirectory,
      onboardProfileId: inputs.onboardProfileId,
      route: inputs.route,
    };
    const readSet = sha256(
      JSON.stringify([
        agentsPlan.digest,
        cliTools.map((tool) => [tool.name, tool.state, tool.version]),
        sha256(mcpText ?? ""),
        trellisProjects.map((project) => [
          project.projectRoot,
          project.state,
          project.bootstrapTask,
        ]),
        context,
        certifiedSkills,
      ]),
    );

    const createdAt = inputs.now();
    const expiresAt = new Date(
      new Date(createdAt).getTime() + 15 * 60_000,
    ).toISOString();
    const identity = inputs.identity;
    const digest = sha256(
      JSON.stringify({
        identity,
        context,
        agentsDigest: agentsPlan.digest,
        skills,
        certifiedSkills,
        cliTools,
        mcpConfigPath,
        mcpEntries,
        trellisProjects,
        bootstrap: { expected: bootstrapExpected },
        approvalClasses,
        readSet,
      }),
    );

    return {
      schemaVersion: 2,
      operationId,
      createdAt,
      expiresAt,
      digest,
      identity,
      context,
      agents: agentsPlan,
      skills,
      certifiedSkills,
      cliTools,
      mcpConfigPath,
      mcpEntries,
      trellisProjects,
      bootstrap: { expected: bootstrapExpected },
      approvalClasses,
      readSet,
    };
  }

  function planRequestFrom(
    plan: CompositeOnboardPlan,
  ): CompositeOnboardRequest {
    return {
      mcpSelections: plan.mcpEntries.map((entry) => ({
        id: entry.id,
        command: entry.command,
        args: entry.args,
      })),
      trellisUsername: plan.trellisProjects.find(
        (project) => project.username !== undefined,
      )?.username,
    };
  }

  async function mergeMcpConfig(
    entries: readonly OnboardMcpEntryPlan[],
  ): Promise<CompositeParticipantResult> {
    const selected = entries.filter((entry) => entry.action === "merge");
    if (selected.length === 0)
      return {
        status: "not-required",
        detail: "No MCP entry required a merge.",
      };
    const prior = await inputs.files.readText(mcpConfigPath);
    let base: Record<string, unknown> = {};
    if (prior !== undefined) {
      try {
        const parsed: unknown = JSON.parse(prior);
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          Array.isArray(parsed)
        )
          return {
            status: "blocked",
            detail:
              "Existing user-level MCP configuration is malformed; no entries were changed.",
          };
        base = parsed as Record<string, unknown>;
      } catch {
        return {
          status: "blocked",
          detail:
            "Existing user-level MCP configuration is malformed; no entries were changed.",
        };
      }
    }
    const existingServers =
      typeof base.mcpServers === "object" &&
      base.mcpServers !== null &&
      !Array.isArray(base.mcpServers)
        ? (base.mcpServers as Record<string, unknown>)
        : {};
    const nextServers: Record<string, unknown> = { ...existingServers };
    for (const entry of selected)
      nextServers[entry.id] = { command: entry.command, args: entry.args };
    const next = JSON.stringify({ ...base, mcpServers: nextServers }, null, 2);
    try {
      await inputs.files.writeAtomic(mcpConfigPath, next);
      const verify = await inputs.files.readText(mcpConfigPath);
      const parsed: unknown = JSON.parse(verify as string);
      const servers = (parsed as Record<string, unknown>).mcpServers as
        | Record<string, unknown>
        | undefined;
      const verified = selected.every(
        (entry) =>
          JSON.stringify(servers?.[entry.id]) ===
          JSON.stringify({ command: entry.command, args: entry.args }),
      );
      if (!verified) throw new Error("MCP merge verification failed");
      return {
        status: "applied",
        detail: `Merged ${selected.length} user-level MCP entr${
          selected.length === 1 ? "y" : "ies"
        }; Reload or a new Session is required before callability.`,
      };
    } catch {
      try {
        if (prior === undefined) await inputs.files.remove(mcpConfigPath);
        else await inputs.files.writeAtomic(mcpConfigPath, prior);
      } catch {
        return {
          status: "failed",
          detail: `MCP merge failed and rollback could not restore ${mcpConfigPath}; repair it manually.`,
        };
      }
      return {
        status: "failed",
        detail:
          "MCP merge failed verification; the previous user-level configuration was restored.",
      };
    }
  }

  async function runTrellisInit(
    project: OnboardTrellisProjectPlan,
    trellisAvailable: boolean,
  ): Promise<CompositeParticipantResult> {
    if (project.action !== "init" || project.username === undefined)
      return {
        status: "not-required",
        detail: "Trellis initialization was not required.",
      };
    if (!trellisAvailable)
      return {
        status: "blocked",
        detail:
          "The Trellis CLI is not callable; install it through an approved shared-dependency Onboard step before initializing projects.",
      };
    const result = await inputs.process.exec(
      "trellis",
      ["init", "-u", project.username, "--omp", "--yes", "--skip-existing"],
      { cwd: project.projectRoot, timeout: trellisInitTimeoutMs },
    );
    if (result.killed || result.code !== 0)
      return {
        status: "failed",
        detail: `trellis init failed: ${sanitizeProcessOutput(
          result.stderr || result.stdout,
          800,
        )}`,
      };
    if (!(await inputs.files.exists(trellisWorkflowPath(project.projectRoot))))
      return {
        status: "failed",
        detail:
          "trellis init exited successfully but did not create a valid project workflow; the project is not reported initialized.",
      };
    return {
      status: "applied",
      detail: "Trellis initialized the project with the omp platform workflow.",
    };
  }

  async function persistOperationRecord(
    record: CompositeOperationRecord,
  ): Promise<void> {
    await inputs.files.makeDirectory(compositeRoot);
    await inputs.files.writeAtomic(
      operationPath(record.planDigest),
      JSON.stringify(record),
    );
  }

  async function loadOperationRecord(
    planDigest: string,
  ): Promise<CompositeOperationRecord | undefined> {
    if (!/^[0-9a-f]{64}$/.test(planDigest)) return undefined;
    const text = await inputs.files.readText(operationPath(planDigest));
    if (text === undefined) return undefined;
    try {
      return compositeOperationRecordSchema.parse(JSON.parse(text));
    } catch {
      return undefined;
    }
  }

  async function loadHandoffRecords(): Promise<BootstrapHandoffRecord[]> {
    if (inputs.listDir === undefined) return [];
    try {
      const names = await inputs.listDir(bootstrapRoot);
      const records: BootstrapHandoffRecord[] = [];
      for (const name of names) {
        if (!name.endsWith(".json")) continue;
        const text = await inputs.files.readText(resolve(bootstrapRoot, name));
        if (text === undefined) continue;
        try {
          records.push(bootstrapHandoffRecordSchema.parse(JSON.parse(text)));
        } catch {
          // Malformed records are never treated as proof.
        }
      }
      return records;
    } catch {
      return [];
    }
  }

  async function observeHandoff(
    record: BootstrapHandoffRecord,
  ): Promise<BootstrapHandoffRecord> {
    if (record.state === "ready") return record;
    const taskState = await observeTrellisBootstrapTask(record.projectRoot);
    const workflowPresent = await inputs.files.exists(
      trellisWorkflowPath(record.projectRoot),
    );
    return {
      ...record,
      lastObservedAt: inputs.now(),
      taskState,
      state:
        taskState === "completed" && workflowPresent
          ? "ready"
          : taskState === "unknown"
            ? "blocked"
            : taskState === "running"
              ? "running"
              : "bootstrap-required",
    };
  }

  async function refreshHandoff(
    record: BootstrapHandoffRecord,
  ): Promise<BootstrapHandoffRecord> {
    const next = await observeHandoff(record);
    if (next.state !== record.state || next.taskState !== record.taskState) {
      await inputs.files.makeDirectory(bootstrapRoot);
      await inputs.files.writeAtomic(
        handoffPath(record.operationId),
        JSON.stringify(next),
      );
    }
    return next;
  }

  return {
    plan: (request) =>
      buildPlan(request, inputs.operationId?.() ?? randomUUID()),

    async apply(plan, approvals) {
      const parsedApprovals = onboardApprovalSetSchema.safeParse(approvals);
      const parsedPlan = compositeOnboardPlanSchema.safeParse(plan);
      if (!parsedPlan.success || !parsedApprovals.success)
        return {
          kind: "blocked",
          message:
            "Composite Onboard Plan or approvals are invalid; create a new plan before applying.",
          reloadRequired: false,
          operationId: String(
            (plan as { operationId?: unknown } | undefined)?.operationId ?? "",
          ),
          planDigest: String(
            (plan as { digest?: unknown } | undefined)?.digest ?? "",
          ),
          participants: {},
          bootstrapRequired: false,
          residuals: [],
        };
      const acceptedPlan = parsedPlan.data;
      const acceptedApprovals = parsedApprovals.data;
      const base = {
        operationId: acceptedPlan.operationId,
        planDigest: acceptedPlan.digest,
      };
      if (Date.parse(acceptedPlan.expiresAt) <= Date.parse(inputs.now()))
        return {
          ...base,
          kind: "stale",
          message: "Plan expired; create a new plan before applying.",
          reloadRequired: false,
          participants: {},
          bootstrapRequired: false,
          residuals: [],
        };
      if (Object.values(acceptedApprovals).every((approved) => !approved))
        return {
          ...base,
          kind: "cancelled",
          message:
            "Composite Onboard Apply was cancelled; no files, tools, MCP configuration, Trellis project, or Agent turn changed.",
          reloadRequired: false,
          participants: {},
          bootstrapRequired: false,
          residuals: [],
        };

      let fresh: CompositeOnboardPlan;
      try {
        fresh = await buildPlan(
          planRequestFrom(acceptedPlan),
          acceptedPlan.operationId,
        );
      } catch {
        return {
          ...base,
          kind: "blocked",
          message:
            "Current Onboard inputs are unsafe or invalid; create a new plan before applying.",
          reloadRequired: false,
          participants: {},
          bootstrapRequired: false,
          residuals: [],
        };
      }
      if (
        fresh.digest !== acceptedPlan.digest ||
        fresh.readSet !== acceptedPlan.readSet ||
        JSON.stringify(fresh.certifiedSkills) !==
          JSON.stringify(acceptedPlan.certifiedSkills)
      )
        return {
          ...base,
          kind: "stale",
          message:
            "Plan read-set changed before Apply; no participant ran. Create a new plan.",
          reloadRequired: false,
          participants: {},
          bootstrapRequired: false,
          residuals: [],
        };

      const participants: Record<string, CompositeParticipantResult> = {};
      const residuals: string[] = [];
      let reloadRequired = false;

      // Participant 1: AGENTS Managed Blocks (TypeScript-owned).
      if (acceptedApprovals["managed-files"]) {
        const agentsResult = await inputs.agents.apply(
          acceptedPlan.agents as OnboardPlan,
          true,
        );
        participants.agents = {
          status:
            agentsResult.kind === "applied"
              ? "applied"
              : agentsResult.kind === "cancelled"
                ? "not-required"
                : agentsResult.kind === "blocked"
                  ? "blocked"
                  : "failed",
          detail: agentsResult.message,
        };
        reloadRequired ||= agentsResult.reloadRequired;
        residuals.push(...agentsResult.residuals);
      } else
        participants.agents = {
          status: "skipped-not-approved",
          detail: "AGENTS Managed Blocks were not approved; no target changed.",
        };

      if (acceptedPlan.skills.action === "out-of-scope")
        participants.certifiedCleanup = {
          status: "not-required",
          detail:
            "Project-only Onboard never inspects global certified leftovers.",
        };
      else if (!acceptedApprovals["managed-files"])
        participants.certifiedCleanup = {
          status: "skipped-not-approved",
          detail: "Certified leftover cleanup was not approved.",
        };
      else {
        const planned = acceptedPlan.certifiedSkills;
        if (planned.packagedCount === 0 || planned.invalidSkills.length > 0)
          participants.certifiedCleanup = {
            status: "blocked",
            detail:
              "Certified leftover cleanup requires a valid packaged portable set before any global leftover is moved.",
          };
        else {
          const cleanup = await applyCertifiedLeftoverCleanup({
            globalSkillsDirectory,
            kitBundledSkillsRoot: inputs.kitBundledSkillsRoot,
            backupRoot: resolve(
              agentDirectory,
              "kpi/certified-cleanup",
              acceptedPlan.digest,
            ),
            packagedNames: planned.names,
            files: inputs.files,
          });
          participants.certifiedCleanup = {
            status: cleanup.status,
            detail: cleanup.detail,
          };
          if (cleanup.rollbackPath !== null)
            residuals.push(cleanup.rollbackPath);
        }
      }

      // Participant 2: retained Skills via the canonical runtime command.
      if (acceptedPlan.skills.action === "out-of-scope")
        participants.skills = {
          status: "not-required",
          detail:
            "Project-only Onboard never inspects or modifies global Skills.",
        };
      else if (!acceptedApprovals["managed-files"])
        participants.skills = {
          status: "skipped-not-approved",
          detail: "Skills installation was not approved; no Skill changed.",
        };
      else if (inputs.runtime === undefined)
        participants.skills = {
          status: "blocked",
          detail:
            "The verified canonical Onboard runtime is unavailable; no Skill changed.",
        };
      else {
        try {
          const result = await inputs.runtime.run({
            kind: "install-stable-external-skills",
            cwd: projectRoot,
            globalSkillsDirectory,
          });
          if ("mode" in result && result.mode === "install-external-skills") {
            const failed = result.results.filter(
              (entry) => "status" in entry && entry.status === "failed",
            );
            const committed = result.transaction.status === "committed";
            participants.skills = {
              status: committed && failed.length === 0 ? "applied" : "failed",
              detail: committed
                ? `Replaced ${result.results.length} selected external Skill target(s) from the embedded stable set ${inputs.identity.stableSet}; rollback path: ${result.transaction.rollbackPath ?? "none"}.`
                : `Skills transaction ended as ${result.transaction.status}; prior targets were restored where possible.`,
            };
            if (committed && failed.length === 0) reloadRequired = true;
            if (result.transaction.rollbackPath !== null && !committed)
              residuals.push(result.transaction.rollbackPath);
          } else
            participants.skills = {
              status: "failed",
              detail: "Canonical runtime returned an unexpected result.",
            };
        } catch (error) {
          participants.skills = {
            status: "failed",
            detail:
              error instanceof CanonicalOnboardRuntimeError
                ? `Canonical Skills installation failed (${error.code}); no target is reported installed.`
                : "Canonical Skills installation failed; no target is reported installed.",
          };
        }
      }

      // Participant 3: required CLI verification / installation.
      for (const tool of acceptedPlan.cliTools) {
        if (tool.action === "install" && tool.packageId !== undefined) {
          if (!acceptedApprovals["shared-dependency-install"]) {
            participants[`cli:${tool.name}`] = {
              status: "skipped-not-approved",
              detail: `${tool.name} installation was not approved; the CLI remains missing.`,
            };
            continue;
          }
          const install = await inputs.process.exec(
            "npm",
            ["install", "-g", tool.packageId],
            { cwd: projectRoot, timeout: installTimeoutMs },
          );
          if (install.killed || install.code !== 0) {
            participants[`cli:${tool.name}`] = {
              status: "blocked",
              detail: `${tool.name} installation failed: ${sanitizeProcessOutput(
                install.stderr || install.stdout,
                800,
              )}`,
            };
            continue;
          }
          const post = await probeCli(
            inputs.process,
            projectRoot,
            tool.name as "trellis" | "gitnexus",
          );
          if (post.state !== "verified") {
            participants[`cli:${tool.name}`] = {
              status: "failed",
              detail: `${tool.name} installer exited successfully but the CLI is not callable; the package-manager effect is recorded as a shared-dependency residual.`,
            };
            residuals.push(`shared-dependency:${tool.packageId}`);
            continue;
          }
          participants[`cli:${tool.name}`] = {
            status: "applied",
            detail: `${tool.name} installed and verified callable (${post.version ?? "unknown"}); the global package remains a shared-dependency residual outside file rollback.`,
          };
          residuals.push(`shared-dependency:${tool.packageId}`);
        } else
          participants[`cli:${tool.name}`] = {
            status: "not-required",
            detail:
              tool.name === "omp"
                ? "The active OMP host was verified only; it is never reinstalled by Onboard."
                : `${tool.name} is already callable or out of scope.`,
          };
      }

      // Participant 4: selected user-level MCP merge.
      if (acceptedPlan.mcpEntries.length === 0)
        participants.mcp = {
          status: "not-required",
          detail: "No MCP server was selected.",
        };
      else if (!acceptedApprovals["mcp-config"])
        participants.mcp = {
          status: "skipped-not-approved",
          detail: "MCP configuration was not approved; no entry changed.",
        };
      else {
        const mcpResult = await mergeMcpConfig(acceptedPlan.mcpEntries);
        participants.mcp = mcpResult;
        reloadRequired ||= mcpResult.status === "applied";
      }

      // Participant 5: per-project Trellis initialization.
      const trellisCallable =
        (await probeCli(inputs.process, projectRoot, "trellis")).state ===
        "verified";
      let bootstrapRequired = false;
      for (const project of acceptedPlan.trellisProjects) {
        if (project.action === "init" && !acceptedApprovals["trellis-init"]) {
          participants[`trellis:${project.projectRoot}`] = {
            status: "skipped-not-approved",
            detail: "Trellis initialization was not approved for this project.",
          };
          continue;
        }
        const result = await runTrellisInit(project, trellisCallable);
        participants[`trellis:${project.projectRoot}`] = result;
        const taskState = await observeTrellisBootstrapTask(
          project.projectRoot,
        );
        bootstrapRequired ||=
          taskState === "pending" || taskState === "unknown";
        if (project.action === "init" && result.status === "applied")
          residuals.push(`external-effect:trellis-init:${project.projectRoot}`);
      }

      const statuses = Object.values(participants).map(
        (participant) => participant.status,
      );
      const failed = statuses.some(
        (status) => status === "failed" || status === "blocked",
      );
      const skipped = statuses.some(
        (status) => status === "skipped-not-approved",
      );
      const kind = failed || skipped ? "partial" : "applied";
      const messageParts = Object.entries(participants).map(
        ([name, participant]) => `${name}: ${participant.status}`,
      );
      const message = `Composite Onboard ${kind} (${messageParts.join(", ")}).${
        bootstrapRequired
          ? " A Trellis bootstrap task is required; run /sbtd onboard bootstrap <plan-digest> after a separate Provider approval."
          : ""
      }${reloadRequired ? " Reload OMP or start a new Session before callability is reported." : ""}`;

      try {
        await persistOperationRecord({
          schemaVersion: 1,
          operationId: acceptedPlan.operationId,
          planDigest: acceptedPlan.digest,
          completedAt: inputs.now(),
          scope: acceptedPlan.context.scope,
          projectRoot,
          participants: Object.fromEntries(
            Object.entries(participants).map(([name, participant]) => [
              name,
              { status: participant.status, detail: participant.detail },
            ]),
          ),
          bootstrapRequired,
          residuals: [...residuals],
        });
      } catch {
        residuals.push(compositeRoot);
      }

      return {
        ...base,
        kind,
        message,
        reloadRequired,
        participants,
        bootstrapRequired,
        residuals,
      };
    },

    async requestBootstrap(planDigest, approved) {
      const record = await loadOperationRecord(planDigest);
      if (record === undefined)
        return {
          kind: "unavailable",
          message:
            "No completed composite Onboard operation is bound to this plan digest. Run /sbtd onboard plan and confirm Apply first.",
        };
      if (!record.bootstrapRequired) {
        const taskState = await observeTrellisBootstrapTask(record.projectRoot);
        if (taskState !== "pending" && taskState !== "unknown")
          return {
            kind: "not-required",
            message:
              "The bound Onboard operation does not require a Trellis bootstrap handoff.",
            operationId: record.operationId,
            projectRoot: record.projectRoot,
            taskState,
          };
      }
      const existingText = await inputs.files.readText(
        handoffPath(record.operationId),
      );
      let handoff: BootstrapHandoffRecord | undefined;
      if (existingText !== undefined) {
        try {
          handoff = bootstrapHandoffRecordSchema.parse(
            JSON.parse(existingText),
          );
        } catch {
          handoff = undefined;
        }
      }
      if (handoff !== undefined) {
        const refreshed = await refreshHandoff(handoff);
        if (refreshed.state === "ready")
          return {
            kind: "ready",
            message:
              "The Trellis bootstrap task is recorded complete by Trellis; the project is ready.",
            operationId: record.operationId,
            projectRoot: record.projectRoot,
            taskState: refreshed.taskState,
          };
        if (refreshed.state === "running")
          return {
            kind: "scheduled",
            message:
              "The Trellis bootstrap Agent turn is running. Completion is observed from Trellis task state only; re-run this command or /sbtd doctor after it finishes.",
            operationId: record.operationId,
            projectRoot: record.projectRoot,
            taskState: refreshed.taskState,
          };
        if (!approved)
          return {
            kind:
              refreshed.state === "blocked" ? "blocked" : "bootstrap-required",
            message: `The Trellis bootstrap handoff is ${refreshed.state}; confirm this command again to resume the same task. No bootstrap completion is claimed.`,
            operationId: record.operationId,
            projectRoot: record.projectRoot,
            taskState: refreshed.taskState,
          };
        if (inputs.handoff === undefined)
          return {
            kind: "unavailable",
            message:
              "This Session cannot schedule an OMP Agent turn; the project remains bootstrap-required.",
            operationId: record.operationId,
            projectRoot: record.projectRoot,
          };
        const resumed: BootstrapHandoffRecord = {
          ...refreshed,
          state: "scheduled",
          scheduledAt: inputs.now(),
          lastObservedAt: inputs.now(),
        };
        await inputs.files.writeAtomic(
          handoffPath(record.operationId),
          JSON.stringify(resumed),
        );
        const resumePrompt = [
          `Enter the project at ${record.projectRoot} and resume the Trellis task 00-bootstrap-guidelines.`,
          "Follow the trellis-workflow Skill: run the before-dev, check, and finish-work gates for that task until Trellis records it completed.",
          "Do not create or complete any other task.",
        ].join(" ");
        await inputs.handoff.schedule(resumePrompt);
        const observed = await refreshHandoff(resumed);
        return {
          kind: observed.state === "ready" ? "ready" : "scheduled",
          message:
            observed.state === "ready"
              ? "The Trellis bootstrap task is recorded complete by Trellis; the project is ready."
              : "Trellis bootstrap handoff resumed as an explicit OMP Agent turn. Completion is observed from Trellis task state only; re-run this command or /sbtd doctor after the turn finishes.",
          operationId: record.operationId,
          projectRoot: record.projectRoot,
          taskState: observed.taskState,
        };
      }
      if (!approved)
        return {
          kind: "cancelled",
          message:
            "Trellis bootstrap handoff was cancelled; no Provider, model, or Agent turn was used and the project remains bootstrap-required.",
          operationId: record.operationId,
          projectRoot: record.projectRoot,
        };
      if (inputs.handoff === undefined)
        return {
          kind: "unavailable",
          message:
            "This Session cannot schedule an OMP Agent turn; the project remains bootstrap-required.",
          operationId: record.operationId,
          projectRoot: record.projectRoot,
        };
      const scheduled: BootstrapHandoffRecord = {
        schemaVersion: 1,
        operationId: record.operationId,
        planDigest: record.planDigest,
        projectRoot: record.projectRoot,
        state: "scheduled",
        scheduledAt: inputs.now(),
        lastObservedAt: inputs.now(),
        taskState: "pending",
      };
      await inputs.files.makeDirectory(bootstrapRoot);
      await inputs.files.writeAtomic(
        handoffPath(record.operationId),
        JSON.stringify(scheduled),
      );
      const prompt = [
        `Enter the project at ${record.projectRoot} and complete the Trellis task 00-bootstrap-guidelines.`,
        "Follow the trellis-workflow Skill: run the before-dev, check, and finish-work gates for that task until Trellis records it completed.",
        "Do not create or complete any other task.",
      ].join(" ");
      await inputs.handoff.schedule(prompt);
      const refreshed = await refreshHandoff(scheduled);
      return {
        kind: refreshed.state === "ready" ? "ready" : "scheduled",
        message:
          refreshed.state === "ready"
            ? "The Trellis bootstrap task is recorded complete by Trellis; the project is ready."
            : "Trellis bootstrap handoff scheduled as an explicit OMP Agent turn. Completion is observed from Trellis task state only; re-run this command or /sbtd doctor after the turn finishes.",
        operationId: record.operationId,
        projectRoot: record.projectRoot,
        taskState: refreshed.taskState,
      };
    },

    async observeBootstrap() {
      const records = await loadHandoffRecords();
      return Promise.all(records.map((record) => observeHandoff(record)));
    },

    inspectRecovery: () => inputs.agents.inspectRecovery(),
    recover: () => inputs.agents.recover(),
  };
}
