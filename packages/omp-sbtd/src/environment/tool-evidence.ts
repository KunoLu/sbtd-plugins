import { createHash } from "node:crypto";
import { realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { z } from "zod";
import type { FileAdapter } from "../onboard/index.js";

const installationSchema = z.enum([
  "installed",
  "missing",
  "broken",
  "not-needed",
]);
const configurationSchema = z.enum([
  "configured",
  "not-configured",
  "not-needed",
]);
const callabilitySchema = z.enum([
  "callable",
  "unavailable",
  "blocked",
  "not-needed",
]);
const projectReadinessSchema = z.enum([
  "ready",
  "not-ready",
  "blocked",
  "not-needed",
]);
const freshnessSchema = z.enum(["current", "stale", "unknown", "not-needed"]);

export const toolEvidenceStateSchema = z
  .object({
    installation: installationSchema,
    configuration: configurationSchema,
    callability: callabilitySchema,
    projectReadiness: projectReadinessSchema,
    freshness: freshnessSchema,
    observedAt: z.string().datetime(),
    evidence: z.array(z.string().min(1)).max(32),
    blockedReason: z.string().min(1).optional(),
  })
  .strict();

export type ToolEvidenceState = z.infer<typeof toolEvidenceStateSchema>;

export const toolEvidenceSubjectSchema = z.enum([
  "runtime-capability",
  "external-tool",
  "non-executable-skill",
]);

export type ToolEvidenceSubject = z.infer<typeof toolEvidenceSubjectSchema>;

export const toolEvidenceRecordSchema = toolEvidenceStateSchema
  .extend({
    key: z.string().regex(/^[0-9a-f]{64}$/),
    toolId: z.string().min(1),
    capability: z.string().min(1),
    subject: toolEvidenceSubjectSchema,
    probeRegistryVersion: z.string().min(1),
    kitRevision: z.string().regex(/^[0-9a-f]{64}$/),
    scopeKey: z.string().min(1),
    inputFingerprint: z.string().min(1),
    validUntil: z.string().datetime(),
  })
  .strict()
  .superRefine((record, ctx) => {
    if (
      record.callability === "not-needed" &&
      record.subject !== "non-executable-skill"
    ) {
      ctx.addIssue({
        code: "custom",
        message:
          "only a non-executable Skill may record callability as not-needed",
        path: ["callability"],
      });
    }
  });

export type ToolEvidenceRecord = z.infer<typeof toolEvidenceRecordSchema>;

const toolEvidenceStoreSchema = z
  .object({
    schemaVersion: z.literal(1),
    revision: z.number().int().nonnegative(),
    records: z.array(toolEvidenceRecordSchema).max(4096),
  })
  .strict();

type ToolEvidenceStore = z.infer<typeof toolEvidenceStoreSchema>;

export interface ToolEvidenceFacet<T extends string> {
  readonly value: T;
  readonly evidence: string;
  readonly blockedReason?: string;
}

export interface ToolEvidenceProbe {
  readonly toolId: string;
  readonly capability: string;
  readonly subject: ToolEvidenceSubject;
  readonly inputFingerprint: string;
  readonly validityMs: number;
  readonly observeInstallation: () => Promise<
    ToolEvidenceFacet<ToolEvidenceState["installation"]>
  >;
  readonly observeConfiguration: () => Promise<
    ToolEvidenceFacet<ToolEvidenceState["configuration"]>
  >;
  readonly observeCallability: () => Promise<
    ToolEvidenceFacet<ToolEvidenceState["callability"]>
  >;
  readonly observeProjectReadiness: () => Promise<
    ToolEvidenceFacet<ToolEvidenceState["projectReadiness"]>
  >;
  readonly observeFreshness: () => Promise<
    ToolEvidenceFacet<ToolEvidenceState["freshness"]>
  >;
}

export interface ToolEvidenceObserverInputs {
  readonly files: FileAdapter;
  readonly storePath: string;
  readonly kitRevision: string;
  readonly scope: "global" | "project";
  readonly projectRoot?: string;
  readonly probeRegistryVersion: string;
  readonly now: () => string;
  /**
   * Read-only commands may probe and render current facts but must not create
   * a store or lock directory as a side effect.
   */
  readonly persist?: boolean;
}

export interface ToolEvidenceObservation {
  readonly storeRevision: number;
  readonly records: readonly ToolEvidenceRecord[];
}

type ScopedToolEvidenceObserverInputs = ToolEvidenceObserverInputs & {
  readonly scopeKey: string;
};

const sleep = (milliseconds: number): Promise<void> => {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, milliseconds);
  return promise;
};

const recordIdentity = (
  probe: ToolEvidenceProbe,
  inputs: ScopedToolEvidenceObserverInputs,
): string =>
  [
    probe.toolId,
    probe.capability,
    inputs.probeRegistryVersion,
    inputs.kitRevision,
    inputs.scopeKey,
  ].join("\u0000");

const recordKey = (
  probe: ToolEvidenceProbe,
  inputs: ScopedToolEvidenceObserverInputs,
): string =>
  createHash("sha256")
    .update(`${recordIdentity(probe, inputs)}\u0000${probe.inputFingerprint}`)
    .digest("hex");

async function deriveScopeKey(
  inputs: ToolEvidenceObserverInputs,
): Promise<string> {
  if (inputs.scope === "global") {
    if (inputs.projectRoot !== undefined)
      throw new Error("global Tool Evidence cannot include a project root");
    return "global";
  }
  const projectRoot = z.string().min(1).parse(inputs.projectRoot);
  const canonicalProjectRoot = await realpath(resolve(projectRoot));
  return `project:${createHash("sha256").update(canonicalProjectRoot).digest("hex")}`;
}

async function readStore(
  inputs: ToolEvidenceObserverInputs,
): Promise<ToolEvidenceStore> {
  const content = await inputs.files.readText(inputs.storePath);
  if (content === undefined)
    return { schemaVersion: 1, revision: 0, records: [] };
  return toolEvidenceStoreSchema.parse(JSON.parse(content));
}

async function acquireStoreLock(
  inputs: ToolEvidenceObserverInputs,
): Promise<string> {
  const lockPath = `${inputs.storePath}.lock`;
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
    `Tool Evidence store is locked; inspect and repair ${lockPath}`,
  );
}

export function toolEvidenceCapabilityIsReady(
  record: ToolEvidenceRecord | undefined,
): boolean {
  if (record === undefined) return false;
  return (
    (record.installation === "installed" ||
      record.installation === "not-needed") &&
    (record.configuration === "configured" ||
      record.configuration === "not-needed") &&
    (record.callability === "callable" ||
      record.callability === "not-needed") &&
    (record.projectReadiness === "ready" ||
      record.projectReadiness === "not-needed") &&
    (record.freshness === "current" || record.freshness === "not-needed")
  );
}

async function observeRecord(
  probe: ToolEvidenceProbe,
  inputs: ScopedToolEvidenceObserverInputs,
  observedAt: string,
  observedMilliseconds: number,
): Promise<ToolEvidenceRecord> {
  const [
    installation,
    configuration,
    callability,
    projectReadiness,
    freshness,
  ] = await Promise.all([
    probe.observeInstallation(),
    probe.observeConfiguration(),
    probe.observeCallability(),
    probe.observeProjectReadiness(),
    probe.observeFreshness(),
  ]);
  const facets = [
    installation,
    configuration,
    callability,
    projectReadiness,
    freshness,
  ];
  const blockedFacet = facets.find(
    (facet) => facet.blockedReason !== undefined,
  );
  const state = toolEvidenceStateSchema.parse({
    installation: installation.value,
    configuration: configuration.value,
    callability: callability.value,
    projectReadiness: projectReadiness.value,
    freshness: freshness.value,
    observedAt,
    evidence: [...new Set(facets.map((facet) => facet.evidence))],
    ...(blockedFacet === undefined
      ? {}
      : { blockedReason: blockedFacet.blockedReason }),
  });
  return toolEvidenceRecordSchema.parse({
    ...state,
    observedAt,
    key: recordKey(probe, inputs),
    toolId: probe.toolId,
    capability: probe.capability,
    subject: probe.subject,
    probeRegistryVersion: inputs.probeRegistryVersion,
    kitRevision: inputs.kitRevision,
    scopeKey: inputs.scopeKey,
    inputFingerprint: probe.inputFingerprint,
    validUntil: new Date(observedMilliseconds + probe.validityMs).toISOString(),
  });
}

export function createToolEvidenceObserver(
  inputs: ToolEvidenceObserverInputs,
): {
  readonly observe: (
    probes: readonly ToolEvidenceProbe[],
  ) => Promise<ToolEvidenceObservation>;
} {
  return {
    async observe(probes) {
      const parsedInputs = {
        ...inputs,
        kitRevision: z
          .string()
          .regex(/^[0-9a-f]{64}$/)
          .parse(inputs.kitRevision),
        probeRegistryVersion: z
          .string()
          .min(1)
          .parse(inputs.probeRegistryVersion),
        scopeKey: await deriveScopeKey(inputs),
      };
      const duplicateKeys = new Set<string>();
      for (const probe of probes) {
        const key = recordKey(probe, parsedInputs);
        if (duplicateKeys.has(key))
          throw new Error(`duplicate Tool Evidence probe: ${probe.toolId}`);
        duplicateKeys.add(key);
        if (!Number.isSafeInteger(probe.validityMs) || probe.validityMs <= 0)
          throw new Error(`invalid Tool Evidence validity: ${probe.toolId}`);
      }
      if (inputs.persist === false) {
        const store = await readStore(parsedInputs);
        const observedAt = z.string().datetime().parse(parsedInputs.now());
        const observedMilliseconds = Date.parse(observedAt);
        const requested = await Promise.all(
          [...probes]
            .sort((left, right) => left.toolId.localeCompare(right.toolId))
            .map(async (probe) => {
              const key = recordKey(probe, parsedInputs);
              const cached = store.records.find(
                (record) =>
                  record.key === key &&
                  (record.freshness === "current" ||
                    record.freshness === "not-needed") &&
                  record.validUntil > observedAt,
              );
              return (
                cached ??
                observeRecord(
                  probe,
                  parsedInputs,
                  observedAt,
                  observedMilliseconds,
                )
              );
            }),
        );
        return { storeRevision: store.revision, records: requested };
      }
      const lockPath = await acquireStoreLock(parsedInputs);
      try {
        const store = await readStore(parsedInputs);
        const observedAt = z.string().datetime().parse(parsedInputs.now());
        const observedMilliseconds = Date.parse(observedAt);
        const records = [...store.records];
        const requested: ToolEvidenceRecord[] = [];
        let changed = false;
        for (const probe of [...probes].sort((left, right) =>
          left.toolId.localeCompare(right.toolId),
        )) {
          const key = recordKey(probe, parsedInputs);
          const cached = records.find(
            (record) =>
              record.key === key &&
              (record.freshness === "current" ||
                record.freshness === "not-needed") &&
              record.validUntil > observedAt,
          );
          if (cached !== undefined) {
            requested.push(cached);
            continue;
          }
          const next = await observeRecord(
            probe,
            parsedInputs,
            observedAt,
            observedMilliseconds,
          );
          const identity = recordIdentity(probe, parsedInputs);
          const retained = records.filter(
            (record) =>
              [
                record.toolId,
                record.capability,
                record.probeRegistryVersion,
                record.kitRevision,
                record.scopeKey,
              ].join("\u0000") !== identity,
          );
          records.splice(0, records.length, ...retained, next);
          requested.push(next);
          changed = true;
        }
        if (changed) {
          const nextStore = toolEvidenceStoreSchema.parse({
            schemaVersion: 1,
            revision: store.revision + 1,
            records: records.sort((left, right) =>
              left.key.localeCompare(right.key),
            ),
          });
          await parsedInputs.files.writeAtomic(
            parsedInputs.storePath,
            `${JSON.stringify(nextStore, null, 2)}\n`,
          );
          return { storeRevision: nextStore.revision, records: requested };
        }
        return { storeRevision: store.revision, records: requested };
      } finally {
        await parsedInputs.files.remove(lockPath);
      }
    },
  };
}
