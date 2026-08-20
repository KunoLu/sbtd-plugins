import { createHash, randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { z } from "zod";
import type { FileAdapter } from "../onboard/index.js";
import type { SbtdSessionState } from "../state/index.js";

const isoTimestampSchema = z.string().datetime();
const capabilitySchema = z.string().regex(/^[a-z0-9][a-z0-9-]*$/);
const acceptedSkipScopeSchema = z.enum(["global", "project"]);
const projectRootKeySchema = z.string().regex(/^[0-9a-f]{64}$/);
const actorSchema = z
  .object({
    kind: z.literal("local-user"),
    id: z.literal("omp-user"),
  })
  .strict();
const provenanceSchema = z
  .object({
    sourceId: z.literal("sbtd-workflow-kit-upstream"),
    kitRevision: z.string().regex(/^[0-9a-f]{64}$/),
    transformVersion: z.string().min(1),
  })
  .strict();
const revocationSchema = z
  .object({
    revokedAt: isoTimestampSchema,
    actor: actorSchema,
    reason: z.string().min(1).max(512),
  })
  .strict();
const expiryReconciliationSchema = z
  .object({
    reconciledAt: isoTimestampSchema,
    actor: actorSchema,
    reason: z.string().min(1).max(512),
  })
  .strict();

export const acceptedSkipRecordSchema = z
  .object({
    recordId: z.string().uuid(),
    version: z.number().int().positive(),
    capability: capabilitySchema,
    scope: acceptedSkipScopeSchema,
    projectRootKey: projectRootKeySchema.optional(),
    onboardProfileId: z.string().min(1),
    kitMajor: z.number().int().positive(),
    actor: actorSchema,
    createdAt: isoTimestampSchema,
    confirmedAt: isoTimestampSchema,
    expiresAt: isoTimestampSchema,
    status: z.enum(["active", "revoked", "expired"]),
    reason: z.string().min(1).max(512),
    planDigest: z
      .string()
      .regex(/^[0-9a-f]{64}$/)
      .optional(),
    evidenceReference: z.string().min(1).max(256).optional(),
    provenance: provenanceSchema,
    predecessorVersion: z.number().int().positive().optional(),
    revocation: revocationSchema.optional(),
    expiryReconciliation: expiryReconciliationSchema.optional(),
  })
  .strict();

export const acceptedSkipStoreSchema = z
  .object({
    schemaVersion: z.literal(1),
    revision: z.number().int().nonnegative(),
    lastOperationId: z.string().uuid().optional(),
    records: z.array(acceptedSkipRecordSchema).max(1024),
  })
  .strict();

export type AcceptedSkipRecord = z.infer<typeof acceptedSkipRecordSchema>;
export type AcceptedSkipStore = z.infer<typeof acceptedSkipStoreSchema>;
export type AcceptedSkipScope = z.infer<typeof acceptedSkipScopeSchema>;

export interface AcceptedSkipContext {
  readonly scope: AcceptedSkipScope;
  readonly projectRootKey?: string;
  readonly onboardProfileId: string;
  readonly kitMajor: number;
  readonly route: SbtdSessionState["route"];
  readonly profile: {
    readonly required: readonly string[];
    readonly optional: readonly string[];
  };
  readonly routeRequiredCapabilities: readonly string[];
  readonly provenance: z.infer<typeof provenanceSchema>;
}

export interface AcceptedSkipPlan {
  readonly schemaVersion: 1;
  readonly operationId: string;
  readonly action: "create" | "revoke" | "expire";
  readonly createdAt: string;
  readonly expiresAt: string;
  readonly storeRevision: number;
  readonly storeDigest: string;
  readonly context: Pick<
    AcceptedSkipContext,
    | "scope"
    | "projectRootKey"
    | "onboardProfileId"
    | "kitMajor"
    | "route"
    | "provenance"
  > & {
    readonly requiredCapabilities: readonly string[];
    readonly optionalCapabilities: readonly string[];
    readonly routeRequiredCapabilities: readonly string[];
  };
  readonly create?: {
    readonly recordId: string;
    readonly capability: string;
    readonly reason: string;
    readonly expiresAt: string;
    readonly evidenceReference?: string;
  };
  readonly target?: {
    readonly recordId: string;
    readonly version: number;
    readonly reason: string;
  };
  readonly digest: string;
}

export type AcceptedSkipPlanResult =
  | { readonly kind: "planned"; readonly plan: AcceptedSkipPlan }
  | { readonly kind: "blocked"; readonly message: string }
  | { readonly kind: "invalid-store"; readonly message: string };

export type AcceptedSkipApplyResult =
  | {
      readonly kind: "applied";
      readonly record: AcceptedSkipRecord;
      readonly revision: number;
    }
  | {
      readonly kind: "stale" | "blocked" | "invalid-store";
      readonly message: string;
    };

export interface AcceptedSkipList {
  readonly kind: "ok" | "invalid-store";
  readonly revision?: number;
  readonly digest?: string;
  readonly records: readonly AcceptedSkipRecord[];
  readonly effectiveRecords: readonly AcceptedSkipRecord[];
  readonly message?: string;
}

export interface AcceptedSkipServiceInputs {
  readonly files: FileAdapter;
  readonly agentDirectory: string;
  readonly now: () => string;
  readonly planTtlMs?: number;
  readonly operationId?: () => string;
}

const defaultStore = (): AcceptedSkipStore => ({
  schemaVersion: 1,
  revision: 0,
  records: [],
});

function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function storeDigest(store: AcceptedSkipStore): string {
  return digest(store);
}

const sleep = (milliseconds: number): Promise<void> => {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, milliseconds);
  return promise;
};

async function acquireStoreLock(
  inputs: AcceptedSkipServiceInputs,
): Promise<string> {
  const lockPath = `${resolve(
    inputs.agentDirectory,
    "kpi/provenance/accepted-skips-v1.json",
  )}.lock`;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      await inputs.files.makeDirectory(lockPath);
      return lockPath;
    } catch (error) {
      if (!(await inputs.files.exists(lockPath))) throw error;
      await sleep(10);
    }
  }
  throw new Error(
    `AcceptedSkip store is locked; inspect and repair ${lockPath}`,
  );
}

function provenanceMatches(
  left: AcceptedSkipRecord["provenance"],
  right: AcceptedSkipRecord["provenance"],
): boolean {
  return (
    left.sourceId === right.sourceId &&
    left.kitRevision === right.kitRevision &&
    left.transformVersion === right.transformVersion
  );
}

function toMillis(value: string): number {
  return Date.parse(value);
}

function validateStoreChronology(store: AcceptedSkipStore): AcceptedSkipStore {
  const parsed = acceptedSkipStoreSchema.parse(store);
  if (parsed.revision !== parsed.records.length)
    throw new Error(
      "AcceptedSkip store revision does not match its append-only history",
    );
  if (
    (parsed.records.length === 0 && parsed.lastOperationId !== undefined) ||
    (parsed.records.length > 0 && parsed.lastOperationId === undefined)
  )
    throw new Error("AcceptedSkip store operation history is incomplete");
  const versionsByRecord = new Map<string, AcceptedSkipRecord[]>();
  const planDigests = new Set<string>();
  for (const record of parsed.records) {
    if (record.planDigest !== undefined) {
      if (planDigests.has(record.planDigest))
        throw new Error("AcceptedSkip operation digest is not unique");
      planDigests.add(record.planDigest);
    }
    const records = versionsByRecord.get(record.recordId) ?? [];
    records.push(record);
    versionsByRecord.set(record.recordId, records);
  }
  for (const records of versionsByRecord.values()) {
    for (const [index, record] of records.entries()) {
      if (
        (record.scope === "project" && record.projectRootKey === undefined) ||
        (record.scope === "global" && record.projectRootKey !== undefined)
      )
        throw new Error("AcceptedSkip record scope identity is invalid");
      if (toMillis(record.confirmedAt) < toMillis(record.createdAt))
        throw new Error("AcceptedSkip confirmation predates creation");
      if (toMillis(record.expiresAt) <= toMillis(record.createdAt))
        throw new Error("AcceptedSkip record expiry does not follow creation");
      if (record.status === "active") {
        if (
          record.predecessorVersion !== undefined ||
          record.revocation !== undefined ||
          record.expiryReconciliation !== undefined
        )
          throw new Error(
            "AcceptedSkip active record contains lifecycle closure details",
          );
      } else if (record.status === "revoked") {
        if (
          record.revocation === undefined ||
          record.expiryReconciliation !== undefined ||
          record.revocation.revokedAt !== record.confirmedAt ||
          toMillis(record.revocation.revokedAt) < toMillis(record.createdAt)
        )
          throw new Error(
            "AcceptedSkip revoked record has invalid lifecycle details",
          );
      } else if (
        record.expiryReconciliation === undefined ||
        record.revocation !== undefined ||
        record.expiryReconciliation.reconciledAt !== record.confirmedAt ||
        toMillis(record.expiryReconciliation.reconciledAt) <
          toMillis(record.createdAt)
      ) {
        throw new Error(
          "AcceptedSkip expired record has invalid lifecycle details",
        );
      }
      if (index === 0) {
        if (
          record.version !== 1 ||
          record.predecessorVersion !== undefined ||
          record.status !== "active"
        )
          throw new Error("AcceptedSkip initial version is invalid");
        continue;
      }
      const predecessor = records[index - 1] as AcceptedSkipRecord;
      if (
        record.version !== predecessor.version + 1 ||
        record.predecessorVersion !== predecessor.version ||
        toMillis(record.confirmedAt) < toMillis(predecessor.confirmedAt)
      )
        throw new Error("AcceptedSkip record chronology is invalid");
      if (
        record.capability !== predecessor.capability ||
        record.scope !== predecessor.scope ||
        record.projectRootKey !== predecessor.projectRootKey ||
        record.onboardProfileId !== predecessor.onboardProfileId ||
        record.kitMajor !== predecessor.kitMajor ||
        record.createdAt !== predecessor.createdAt ||
        record.expiresAt !== predecessor.expiresAt ||
        !provenanceMatches(record.provenance, predecessor.provenance)
      )
        throw new Error(
          "AcceptedSkip version changed immutable eligibility facts",
        );
    }
  }
  return parsed;
}

function effectiveRecords(
  records: readonly AcceptedSkipRecord[],
): readonly AcceptedSkipRecord[] {
  const latest = new Map<string, AcceptedSkipRecord>();
  for (const record of records) latest.set(record.recordId, record);
  return [...latest.values()].sort((left, right) =>
    left.recordId.localeCompare(right.recordId),
  );
}

function contextProjection(
  context: AcceptedSkipContext,
): AcceptedSkipPlan["context"] {
  return {
    scope: context.scope,
    ...(context.projectRootKey === undefined
      ? {}
      : { projectRootKey: context.projectRootKey }),
    onboardProfileId: context.onboardProfileId,
    kitMajor: context.kitMajor,
    route: context.route,
    provenance: context.provenance,
    requiredCapabilities: [...context.profile.required].sort(),
    optionalCapabilities: [...context.profile.optional].sort(),
    routeRequiredCapabilities: [...context.routeRequiredCapabilities].sort(),
  };
}

function planWithDigest(
  plan: Omit<AcceptedSkipPlan, "digest">,
): AcceptedSkipPlan {
  return { ...plan, digest: digest(plan) };
}

function planIsConsistent(plan: AcceptedSkipPlan): boolean {
  const { digest: expected, ...unsigned } = plan;
  return expected === digest(unsigned);
}

function recordMatchesContext(
  record: AcceptedSkipRecord,
  context: AcceptedSkipPlan["context"],
): boolean {
  return (
    record.scope === context.scope &&
    record.projectRootKey === context.projectRootKey &&
    record.onboardProfileId === context.onboardProfileId &&
    record.kitMajor === context.kitMajor &&
    provenanceMatches(record.provenance, context.provenance)
  );
}

export function eligibleAcceptedSkips(
  records: readonly AcceptedSkipRecord[],
  context: AcceptedSkipContext,
  observedAt: string,
): readonly AcceptedSkipRecord[] {
  const required = new Set(context.profile.required);
  const optional = new Set(context.profile.optional);
  const routeRequired = new Set(context.routeRequiredCapabilities);
  return effectiveRecords(records).filter(
    (record) =>
      record.status === "active" &&
      toMillis(observedAt) < toMillis(record.expiresAt) &&
      optional.has(record.capability) &&
      !required.has(record.capability) &&
      !routeRequired.has(record.capability) &&
      recordMatchesContext(record, contextProjection(context)),
  );
}

export function createAcceptedSkipService(inputs: AcceptedSkipServiceInputs): {
  readonly storePath: string;
  readonly list: () => Promise<AcceptedSkipList>;
  readonly planCreate: (
    context: AcceptedSkipContext,
    input: {
      readonly capability: string;
      readonly reason: string;
      readonly expiresAt: string;
      readonly evidenceReference?: string;
    },
  ) => Promise<AcceptedSkipPlanResult>;
  readonly planRevoke: (
    context: AcceptedSkipContext,
    input: { readonly recordId: string; readonly reason: string },
  ) => Promise<AcceptedSkipPlanResult>;
  readonly planExpire: (
    context: AcceptedSkipContext,
    input: { readonly recordId: string; readonly reason: string },
  ) => Promise<AcceptedSkipPlanResult>;
  readonly apply: (plan: AcceptedSkipPlan) => Promise<AcceptedSkipApplyResult>;
} {
  const storePath = `${inputs.agentDirectory}/kpi/provenance/accepted-skips-v1.json`;
  const planTtlMs = inputs.planTtlMs ?? 5 * 60_000;
  const operationId = inputs.operationId ?? randomUUID;

  const readStore = async (): Promise<
    | { readonly kind: "ok"; readonly store: AcceptedSkipStore }
    | { readonly kind: "invalid-store"; readonly message: string }
  > => {
    const text = await inputs.files.readText(storePath);
    if (text === undefined) return { kind: "ok", store: defaultStore() };
    try {
      return { kind: "ok", store: validateStoreChronology(JSON.parse(text)) };
    } catch (error) {
      return {
        kind: "invalid-store",
        message: `AcceptedSkip store is invalid and was not used: ${error instanceof Error ? error.message : "unknown parse failure"}`,
      };
    }
  };

  const makePlan = async (
    context: AcceptedSkipContext,
    action: AcceptedSkipPlan["action"],
    details: Pick<AcceptedSkipPlan, "create" | "target">,
  ): Promise<AcceptedSkipPlanResult> => {
    if (
      (context.scope === "project" && context.projectRootKey === undefined) ||
      (context.scope === "global" && context.projectRootKey !== undefined)
    )
      return {
        kind: "blocked",
        message: "AcceptedSkip scope requires an exact matching identity.",
      };
    const loaded = await readStore();
    if (loaded.kind !== "ok") return loaded;
    const createdAt = inputs.now();
    const expiresAt = new Date(toMillis(createdAt) + planTtlMs).toISOString();
    return {
      kind: "planned",
      plan: planWithDigest({
        schemaVersion: 1,
        operationId: operationId(),
        action,
        createdAt,
        expiresAt,
        storeRevision: loaded.store.revision,
        storeDigest: storeDigest(loaded.store),
        context: contextProjection(context),
        ...details,
      }),
    };
  };

  return {
    storePath,
    async list() {
      const loaded = await readStore();
      if (loaded.kind !== "ok")
        return {
          kind: "invalid-store",
          records: [],
          effectiveRecords: [],
          message: loaded.message,
        };
      return {
        kind: "ok",
        revision: loaded.store.revision,
        digest: storeDigest(loaded.store),
        records: loaded.store.records,
        effectiveRecords: effectiveRecords(loaded.store.records),
      };
    },
    async planCreate(context, input) {
      const capability = capabilitySchema.safeParse(input.capability);
      const reason = z.string().min(1).max(512).safeParse(input.reason);
      const expiresAt = isoTimestampSchema.safeParse(input.expiresAt);
      if (!capability.success || !reason.success || !expiresAt.success)
        return {
          kind: "blocked",
          message: "AcceptedSkip create arguments are invalid.",
        };
      if (toMillis(expiresAt.data) <= toMillis(inputs.now()))
        return {
          kind: "blocked",
          message: "AcceptedSkip expiry must be in the future.",
        };
      if (context.profile.required.includes(capability.data))
        return {
          kind: "blocked",
          message: "Profile-required capabilities cannot be accepted skips.",
        };
      if (context.routeRequiredCapabilities.includes(capability.data))
        return {
          kind: "blocked",
          message: "Route-required capabilities cannot be accepted skips.",
        };
      if (!context.profile.optional.includes(capability.data))
        return {
          kind: "blocked",
          message:
            "AcceptedSkip capability is not Optional in the selected Profile.",
        };
      return makePlan(context, "create", {
        create: {
          recordId: randomUUID(),
          capability: capability.data,
          reason: reason.data,
          expiresAt: expiresAt.data,
          ...(input.evidenceReference === undefined
            ? {}
            : { evidenceReference: input.evidenceReference }),
        },
      });
    },
    async planRevoke(context, input) {
      const recordId = z.string().uuid().safeParse(input.recordId);
      const reason = z.string().min(1).max(512).safeParse(input.reason);
      if (!recordId.success || !reason.success)
        return {
          kind: "blocked",
          message: "AcceptedSkip revoke arguments are invalid.",
        };
      const listed = await readStore();
      if (listed.kind !== "ok") return listed;
      const record = effectiveRecords(listed.store.records).find(
        (candidate) => candidate.recordId === recordId.data,
      );
      if (
        record === undefined ||
        record.status !== "active" ||
        !recordMatchesContext(record, contextProjection(context))
      )
        return {
          kind: "blocked",
          message: "AcceptedSkip revoke target is not an active exact match.",
        };
      return makePlan(context, "revoke", {
        target: {
          recordId: record.recordId,
          version: record.version,
          reason: reason.data,
        },
      });
    },
    async planExpire(context, input) {
      const recordId = z.string().uuid().safeParse(input.recordId);
      const reason = z.string().min(1).max(512).safeParse(input.reason);
      if (!recordId.success || !reason.success)
        return {
          kind: "blocked",
          message: "AcceptedSkip expiry arguments are invalid.",
        };
      const listed = await readStore();
      if (listed.kind !== "ok") return listed;
      const record = effectiveRecords(listed.store.records).find(
        (candidate) => candidate.recordId === recordId.data,
      );
      if (
        record === undefined ||
        record.status !== "active" ||
        toMillis(inputs.now()) < toMillis(record.expiresAt) ||
        !recordMatchesContext(record, contextProjection(context))
      )
        return {
          kind: "blocked",
          message:
            "AcceptedSkip expiry target is not an elapsed active exact match.",
        };
      return makePlan(context, "expire", {
        target: {
          recordId: record.recordId,
          version: record.version,
          reason: reason.data,
        },
      });
    },
    async apply(plan) {
      if (!planIsConsistent(plan))
        return {
          kind: "stale",
          message: "AcceptedSkip Plan digest is invalid.",
        };
      let lockPath: string;
      try {
        lockPath = await acquireStoreLock(inputs);
      } catch (error) {
        return {
          kind: "blocked",
          message: `AcceptedSkip store could not be locked: ${error instanceof Error ? error.message : "unknown lock failure"}`,
        };
      }
      try {
        const loaded = await readStore();
        if (loaded.kind !== "ok") return loaded;
        const replayIndex = loaded.store.records.findIndex(
          (record) => record.planDigest === plan.digest,
        );
        if (replayIndex !== -1)
          return {
            kind: "applied",
            record: loaded.store.records[replayIndex] as AcceptedSkipRecord,
            revision: replayIndex + 1,
          };
        if (toMillis(inputs.now()) >= toMillis(plan.expiresAt))
          return { kind: "stale", message: "AcceptedSkip Plan has expired." };
        if (
          loaded.store.revision !== plan.storeRevision ||
          storeDigest(loaded.store) !== plan.storeDigest
        )
          return {
            kind: "stale",
            message: "AcceptedSkip Plan read set has changed.",
          };
        let record: AcceptedSkipRecord;
        if (plan.action === "create") {
          if (plan.create === undefined)
            return {
              kind: "blocked",
              message: "AcceptedSkip create Plan has no record input.",
            };
          if (
            !plan.context.optionalCapabilities.includes(
              plan.create.capability,
            ) ||
            plan.context.requiredCapabilities.includes(
              plan.create.capability,
            ) ||
            plan.context.routeRequiredCapabilities.includes(
              plan.create.capability,
            )
          )
            return {
              kind: "blocked",
              message:
                "AcceptedSkip create Plan is not Optional under its bound Profile and Route.",
            };
          const confirmedAt = inputs.now();
          record = {
            recordId: plan.create.recordId,
            version: 1,
            capability: plan.create.capability,
            scope: plan.context.scope,
            ...(plan.context.projectRootKey === undefined
              ? {}
              : { projectRootKey: plan.context.projectRootKey }),
            onboardProfileId: plan.context.onboardProfileId,
            kitMajor: plan.context.kitMajor,
            actor: { kind: "local-user", id: "omp-user" },
            createdAt: confirmedAt,
            confirmedAt,
            expiresAt: plan.create.expiresAt,
            status: "active",
            reason: plan.create.reason,
            planDigest: plan.digest,
            ...(plan.create.evidenceReference === undefined
              ? {}
              : { evidenceReference: plan.create.evidenceReference }),
            provenance: plan.context.provenance,
          };
        } else {
          if (plan.target === undefined)
            return {
              kind: "blocked",
              message: "AcceptedSkip lifecycle Plan has no target.",
            };
          const predecessor = effectiveRecords(loaded.store.records).find(
            (candidate) => candidate.recordId === plan.target?.recordId,
          );
          if (
            predecessor === undefined ||
            predecessor.version !== plan.target.version ||
            predecessor.status !== "active" ||
            !recordMatchesContext(predecessor, plan.context)
          )
            return {
              kind: "stale",
              message: "AcceptedSkip Plan target has changed.",
            };
          if (
            plan.action === "expire" &&
            toMillis(inputs.now()) < toMillis(predecessor.expiresAt)
          )
            return {
              kind: "blocked",
              message: "AcceptedSkip expiry Plan is not yet eligible.",
            };
          const confirmedAt = inputs.now();
          record = {
            ...predecessor,
            version: predecessor.version + 1,
            actor: { kind: "local-user", id: "omp-user" },
            confirmedAt,
            status: plan.action === "revoke" ? "revoked" : "expired",
            predecessorVersion: predecessor.version,
            planDigest: plan.digest,
            ...(plan.action === "revoke"
              ? {
                  revocation: {
                    revokedAt: confirmedAt,
                    actor: {
                      kind: "local-user" as const,
                      id: "omp-user" as const,
                    },
                    reason: plan.target.reason,
                  },
                }
              : {
                  expiryReconciliation: {
                    reconciledAt: confirmedAt,
                    actor: {
                      kind: "local-user" as const,
                      id: "omp-user" as const,
                    },
                    reason: plan.target.reason,
                  },
                }),
          };
        }
        const next: AcceptedSkipStore = {
          schemaVersion: 1,
          revision: loaded.store.revision + 1,
          lastOperationId: plan.operationId,
          records: [...loaded.store.records, record],
        };
        try {
          const valid = validateStoreChronology(next);
          await inputs.files.writeAtomic(
            storePath,
            `${JSON.stringify(valid, null, 2)}\n`,
          );
          return { kind: "applied", record, revision: valid.revision };
        } catch (error) {
          return {
            kind: "blocked",
            message: `AcceptedSkip Plan could not be committed: ${error instanceof Error ? error.message : "unknown write failure"}`,
          };
        }
      } finally {
        await inputs.files.remove(lockPath);
      }
    },
  };
}
