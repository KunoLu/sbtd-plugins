// Slice 7 three-profile certification producer for
// 08-20-omp-plugin-compatibility-decoupling.
//
// This module is the isolated certification cell engine used by
// .github/workflows/omp-compatibility-certification.yml:
// - Admission: a published target enters the catalog only when live npm
//   Registry bytes re-verify the recorded immutable identity (exact version,
//   tarball SHA-256, SRI integrity, extracted manifest SHA-256, tarball-bound
//   peer). Recorded identities today: rc.12 (M5) and rc.13 (cloud §4 HITL
//   next, digest b0e1f133…). Unknown versions are never admitted.

// - Planning: cells come from planCompatibilityMatrixRun and key off each
//   target's own tarball-bound pluginPeerRange. An empty catalog or a plan
//   with zero in-range cells is an unavailable matrix: blocked, never pass.
// - Evidence: each in-range cell produces one sanitized content-addressed
//   evidence bundle per profile with evidenceKind "omp-certification-run-v1".
//   Bundles labeled "local-observation" (e.g. straight from a local live
//   cell) are rejected here and can never be promoted into a ledger entry.
// - Assessment: overallOutcome is DERIVED via deriveLedgerAssessmentOutcome;
//   callers never submit one. The attestation bundle must content-bind every
//   subject digest before the entry is returned for append.
//
// This module never packs, publishes, moves dist-tags, pushes branches, or
// claims certification; it produces verified entries for
// appendLedgerAssessment, which re-runs both ledger validation tiers.
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { z } from "zod";
import {
  appendCompatibilityTarget,
  type CompatibilityMatrixCellPlan,
  type CompatibilityMatrixRunReport,
  type CompatibilityTargetEntry,
  type CompatibilityTargetsDocument,
  canonicalizeRfc8785,
  compatibilityTargetEntrySchema,
  deriveLedgerAssessmentOutcome,
  type LedgerAssessmentEntry,
  ledgerAssessmentEntrySchema,
  ledgerEntryContentSha256,
  planCompatibilityMatrixRun,
  reportCompatibilityMatrixRun,
  verifyAttestationBundle,
} from "./compatibility-ledger.ts";
import {
  hostEventEvidenceBundleSchema,
  recomputeHostIdentity,
} from "./host-event/validate.ts";
import {
  compatibilityPeerRangeSchema,
  P0ValidationError,
  runtimeVersionSchema,
} from "./release-validator.ts";

const hashSchema = z
  .string()
  .regex(/^[a-f0-9]{64}$/, "expected a SHA-256 digest");
const sriSchema = z
  .string()
  .regex(/^sha512-[A-Za-z0-9+/]+={0,2}$/, "expected an SRI sha512 integrity");
const exactStableRuntimeSchema = z
  .string()
  .regex(
    /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/,
    "expected an exact stable Runtime version",
  );
const evidenceLocatorSchema = z
  .string()
  .regex(
    /^(?:plugins\/omp-sbtd\/)?validation\/p0\/evidence\/[A-Za-z0-9._/-]+$/,
    "expected a repository evidence locator beneath validation/p0/evidence/",
  )
  .refine(
    (value) => !value.split("/").some((segment) => segment === ".."),
    "evidence locator must not traverse outside the evidence root",
  );

const sha256Hex = (bytes: Uint8Array | string): string =>
  createHash("sha256").update(bytes).digest("hex");
const sriSha512 = (bytes: Uint8Array): string =>
  `sha512-${createHash("sha512").update(bytes).digest("base64")}`;

// ---------------------------------------------------------------------------
// Recorded published target identities (immutable admission expectations)
// ---------------------------------------------------------------------------

const recordedPublishedTargetIdentitySchema = z
  .object({
    pluginVersion: runtimeVersionSchema,
    pluginTarballSha256: hashSchema,
    packageIntegrity: sriSchema,
    pluginPeerRange: compatibilityPeerRangeSchema,
  })
  .strict();
export type RecordedPublishedTargetIdentity = z.infer<
  typeof recordedPublishedTargetIdentitySchema
>;

/**
 * The only published npm identity at M5 (2026-08-20):
 * .trellis/tasks/archive/2026-08/08-20-m5-publish-omp-sbtd-rc12/research/registry-identity.md
 * and packages/omp-sbtd/CHANGELOG.md [0.1.0-rc.12]. rc.12 stays immutable and
 * is never repacked.
 */
export const RECORDED_RC12_TARGET_IDENTITY: RecordedPublishedTargetIdentity = {
  pluginVersion: "0.1.0-rc.12",
  pluginTarballSha256:
    "49edb4b7cab68f851359179b2c27bb53be8eff5682f16285f5caf9a351c39a33",
  packageIntegrity:
    "sha512-DOFO9focJ1gU4my0bOO1m2tdYP4Mo2wT0wf6iA3y/IXN2FFml9VSx0IBNVHvieajEhgNtfDQAQXpof9DWetzPw==",
  pluginPeerRange: "17.3.5",
};

/**
 * Cloud §4 green run 33052112414 on main ae5a413, HITL `--tag next`.
 * Byte-verified 2026-08-27 against Registry `0.1.0-rc.13`. The candidate
 * envelope tarball `61610988…f9c7` is a different pre-publication pack and
 * is not this identity.
 */
export const RECORDED_RC13_TARGET_IDENTITY: RecordedPublishedTargetIdentity = {
  pluginVersion: "0.1.0-rc.13",
  pluginTarballSha256:
    "b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185",
  packageIntegrity:
    "sha512-YeHQly8ONkZvNczhPBRd+1re3zX1ZAQ2xPUqfzZHhLVHyX90G3Pyk6ypY+knfBK6jZ5No599YaQZxsITvr232w==",
  pluginPeerRange: ">=17.3.5 <18",
};

const RECORDED_PUBLISHED_TARGET_IDENTITIES: readonly RecordedPublishedTargetIdentity[] =
  [RECORDED_RC12_TARGET_IDENTITY, RECORDED_RC13_TARGET_IDENTITY];

/**
 * Returns the recorded immutable identity for one published Plugin version,
 * or undefined when no published identity is recorded.
 * Admission without a recorded identity is impossible by construction.
 */

export function recordedPublishedTargetIdentity(
  pluginVersion: string,
): RecordedPublishedTargetIdentity | undefined {
  return RECORDED_PUBLISHED_TARGET_IDENTITIES.find(
    (identity) => identity.pluginVersion === pluginVersion,
  );
}

// ---------------------------------------------------------------------------
// Registry admission
// ---------------------------------------------------------------------------

/** Live Registry facts fetched by the CLI layer (npm view + tarball bytes). */
export interface RegistryAdmissionFetch {
  readonly registryVersion: string;
  readonly registryDistIntegrity: string;
  readonly registryTarballUrl: string;
  readonly tarballBytes: Uint8Array;
}

/**
 * Parses `npm view <spec> <fields...> --json` stdout into a field record.
 * npm 12 wraps exact-version answers in a one-element array: a record for
 * multi-field queries, a bare value for single-field queries. npm 10 prints
 * a single-field answer as a bare JSON scalar instead; both single-field
 * shapes map onto the requested field name. Anything else (empty or
 * multi-element arrays, malformed JSON, or a bare value answering a
 * multi-field query) means the spec did not resolve to exactly one published
 * version and fails closed.
 */
export function parseNpmViewJson(
  raw: string,
  spec: string,
  fields: readonly string[],
): Readonly<Record<string, unknown>> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      `npm view returned malformed JSON for ${spec}.`,
      "Registry admission needs the live Registry metadata for the exact published version; retry when the Registry is reachable.",
    );
  }
  if (Array.isArray(parsed)) {
    if (parsed.length !== 1)
      throw new P0ValidationError(
        "COMPATIBILITY_ADMISSION_UNAVAILABLE",
        `npm view did not resolve exactly one published version for ${spec}.`,
        "Admission requires an exact published version; never admit from a range or dist-tag.",
      );
    const only = parsed[0];
    if (only !== null && typeof only === "object" && !Array.isArray(only))
      return only as Record<string, unknown>;
    if (fields.length === 1)
      return { [fields[0]]: only } as Record<string, unknown>;
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      `npm view returned an unexpected shape for ${spec}.`,
      "Admission requires an exact published version; never admit from a range or dist-tag.",
    );
  }
  if (parsed === null || typeof parsed !== "object") {
    // npm 10 prints a single-field exact-version answer as a bare JSON
    // string where npm 12 wraps it in a one-element array. Only a string
    // is a published-field value; null / number / boolean stay fail-closed.
    if (fields.length === 1 && typeof parsed === "string")
      return { [fields[0]]: parsed };
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      `npm view did not resolve exactly one published version for ${spec}.`,
      "Admission requires an exact published version; never admit from a range or dist-tag.",
    );
  }
  return parsed as Record<string, unknown>;
}

/** run-cell / finalize-cell `--cell` JSON. ompVersion is an exact stable Runtime, never a tag or range. */
export const certificationCellPlanSchema = z
  .object({
    pluginVersion: z.string().min(1),
    pluginTarballSha256: hashSchema,
    pluginPeerRange: z.string().min(1),
    ompVersion: exactStableRuntimeSchema,
    selectedAs: z.array(z.string()),
    inRange: z.literal(true),
    profilesToRun: z.array(z.string()),
  })
  .strict();

/**
 * Extracts one regular-file member from a gzipped ustar tarball. Supports
 * ustar prefixes and GNU longname ('L') entries; returns undefined when the
 * member is absent. Corrupt archives throw.
 */
export function extractTarballMemberBytes(
  tarballBytes: Uint8Array,
  memberPath: string,
): Uint8Array | undefined {
  let tar: Buffer;
  try {
    tar = gunzipSync(Buffer.from(tarballBytes));
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      "The downloaded Registry tarball is not a readable gzip archive.",
      "Re-fetch the exact published tarball from the npm Registry; never substitute a workspace pack.",
    );
  }
  const text = (block: Buffer): string =>
    block.toString("utf8").replace(/\0.*$/u, "");
  let offset = 0;
  let longName: string | undefined;
  while (offset + 512 <= tar.length) {
    const header = tar.subarray(offset, offset + 512);
    if (header.every((byte) => byte === 0)) break;
    const size = Number.parseInt(text(header.subarray(124, 136)).trim(), 8);
    if (!Number.isFinite(size) || size < 0)
      throw new P0ValidationError(
        "COMPATIBILITY_ADMISSION_UNAVAILABLE",
        "The downloaded Registry tarball has a corrupt ustar header.",
        "Re-fetch the exact published tarball from the npm Registry; never substitute a workspace pack.",
      );
    const typeflag = String.fromCharCode(header[156] ?? 0);
    const prefix = text(header.subarray(345, 500));
    const name =
      longName ??
      (prefix.length > 0
        ? `${prefix}/${text(header.subarray(0, 100))}`
        : text(header.subarray(0, 100)));
    longName = undefined;
    offset += 512;
    if (typeflag === "L") {
      longName = text(tar.subarray(offset, offset + size));
    } else if ((typeflag === "0" || typeflag === "\0") && name === memberPath) {
      return new Uint8Array(tar.subarray(offset, offset + size));
    }
    offset += Math.ceil(size / 512) * 512;
  }
  return undefined;
}

/**
 * Verifies live Registry bytes against the recorded immutable published
 * identity and returns the catalog entry to append. Every fact is recomputed
 * from the downloaded bytes: tarball SHA-256, SRI sha512 integrity, extracted
 * manifest SHA-256 and the tarball-bound peer. Any mismatch fails closed and
 * no catalog write may happen.
 */
export function verifyRegistryTarballAdmission(
  expected: unknown,
  fetched: RegistryAdmissionFetch,
): CompatibilityTargetEntry {
  const recorded = recordedPublishedTargetIdentitySchema.safeParse(expected);
  if (!recorded.success)
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNKNOWN_TARGET",
      "The requested admission expectation is malformed.",
      "Admit only a recorded published target identity; unpublished candidates never enter the catalog.",
      { issues: recorded.error.issues.map((issue) => issue.message) },
    );
  const mismatch = (
    reason: string,
    details: Readonly<Record<string, unknown>> = {},
  ): never => {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_MISMATCH",
      `The live Registry identity does not equal the recorded published identity: ${reason}.`,
      "Fail closed: do not write the catalog. Investigate Registry drift; a changed published tarball is a supply-chain incident, never an admission.",
      details,
    );
  };
  if (fetched.registryVersion !== recorded.data.pluginVersion)
    mismatch("registry version differs", {
      expected: recorded.data.pluginVersion,
      actual: fetched.registryVersion,
    });
  if (fetched.registryDistIntegrity !== recorded.data.packageIntegrity)
    mismatch("registry dist.integrity differs from the recorded SRI");
  const tarballSha256 = sha256Hex(fetched.tarballBytes);
  if (tarballSha256 !== recorded.data.pluginTarballSha256)
    mismatch("tarball SHA-256 differs", {
      expected: recorded.data.pluginTarballSha256,
      actual: tarballSha256,
    });
  if (sriSha512(fetched.tarballBytes) !== recorded.data.packageIntegrity)
    mismatch("recomputed SRI sha512 differs from the recorded integrity");
  const manifestBytes = extractTarballMemberBytes(
    fetched.tarballBytes,
    "package/package.json",
  );
  if (manifestBytes === undefined)
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      "The verified Registry tarball has no package/package.json member.",
      "Fail closed: a published Plugin tarball always carries its manifest; never admit without it.",
    );
  let manifest: unknown;
  try {
    manifest = JSON.parse(Buffer.from(manifestBytes).toString("utf8"));
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      "The extracted package manifest is not valid JSON.",
      "Fail closed: never admit a target whose manifest cannot be parsed.",
    );
  }
  const manifestSchema = z
    .object({
      version: z.string(),
      peerDependencies: z
        .object({
          "@oh-my-pi/pi-coding-agent": compatibilityPeerRangeSchema,
        })
        .strict(),
    })
    .passthrough();
  const parsedManifest = manifestSchema.safeParse(manifest);
  if (!parsedManifest.success)
    mismatch("extracted manifest lacks the expected version or OMP peer", {
      issues: parsedManifest.error.issues.map((issue) => issue.message),
    });
  if (parsedManifest.data.version !== recorded.data.pluginVersion)
    mismatch("manifest version differs", {
      expected: recorded.data.pluginVersion,
      actual: parsedManifest.data.version,
    });
  const pluginPeerRange =
    parsedManifest.data.peerDependencies["@oh-my-pi/pi-coding-agent"];
  if (pluginPeerRange !== recorded.data.pluginPeerRange)
    mismatch("tarball-bound peer range differs", {
      expected: recorded.data.pluginPeerRange,
      actual: pluginPeerRange,
    });
  const entry = compatibilityTargetEntrySchema.safeParse({
    pluginVersion: recorded.data.pluginVersion,
    pluginTarballSha256: tarballSha256,
    packageIntegrity: recorded.data.packageIntegrity,
    pluginManifestSha256: sha256Hex(manifestBytes),
    pluginPeerRange,
  });
  if (!entry.success)
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_MISMATCH",
      "The verified admission identity does not form a valid target entry.",
      "Fail closed: never write a malformed catalog entry.",
      { issues: entry.error.issues.map((issue) => issue.message) },
    );
  return entry.data;
}

/**
 * Full admission step for one published Plugin version against a candidate
 * catalog: records the immutable identity, byte-verifies the live Registry
 * tarball against it, then appends through the existing
 * appendCompatibilityTarget (which owns duplicate-identical no-op,
 * conflicting-version rejection and full catalog validation). The fetch
 * callback is the only I/O seam, so tests run the whole path on fixtures.
 */
export async function admitPublishedTarget(input: {
  readonly catalog: unknown;
  readonly pluginVersion: string;
  readonly fetch: () => Promise<RegistryAdmissionFetch>;
}): Promise<{
  readonly entry: CompatibilityTargetEntry;
  readonly outcome: "appended" | "duplicate-noop";
  readonly targets: CompatibilityTargetsDocument;
  readonly fetched: RegistryAdmissionFetch;
}> {
  const recorded = recordedPublishedTargetIdentity(input.pluginVersion);
  if (recorded === undefined)
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNKNOWN_TARGET",
      `No recorded immutable identity for published Plugin ${input.pluginVersion}; only Registry-published versions with a recorded byte identity can be admitted.`,
      "Add the verified byte identity for the published version first; never admit from a local build or mutable tag.",
    );
  const fetched = await input.fetch();
  const entry = verifyRegistryTarballAdmission(recorded, fetched);
  const result = appendCompatibilityTarget(input.catalog, entry, {
    registryVersion: fetched.registryVersion,
    registryDistIntegrity: fetched.registryDistIntegrity,
  });
  return {
    entry,
    outcome: result.outcome,
    targets: result.targets,
    fetched,
  };
}

// ---------------------------------------------------------------------------
// Cell host identity
// ---------------------------------------------------------------------------

export interface CellHostIdentity {
  readonly entrypointSha256: string;
  readonly packageJsonSha256: string;
  readonly packageVersion: string;
}

/**
 * Recomputes the identity of the exact spawned OMP package binary
 * (dist/cli.js inside @oh-my-pi/pi-coding-agent) and binds it to the cell's
 * OMP version. The node_modules/.bin/omp shim resolves outside the package
 * and yields no package identity (LESSON-20260826-omp-shim-host-identity);
 * any version disagreement fails closed.
 */
export function assertCellHostIdentity(
  ompBin: string,
  expectedOmpVersion: string,
): CellHostIdentity {
  const identity = recomputeHostIdentity(ompBin);
  if (
    identity.packageVersion === undefined ||
    identity.packageJsonSha256 === undefined
  )
    throw new P0ValidationError(
      "OMP_PACKAGE_IDENTITY_UNAVAILABLE",
      "The spawned OMP binary does not resolve to the @oh-my-pi/pi-coding-agent package (a .bin shim is not the package entrypoint).",
      "Spawn the package's own dist/cli.js inside node_modules/@oh-my-pi/pi-coding-agent; never the .bin/omp shim.",
    );
  if (identity.packageVersion !== expectedOmpVersion)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
      "The loaded OMP Runtime version differs from the certification cell.",
      "Install and bind the cell's exact OMP version; a mismatched loaded Runtime never produces certification evidence.",
      {
        expected: expectedOmpVersion,
        actual: identity.packageVersion,
      },
    );
  return {
    entrypointSha256: identity.entrypointSha256,
    packageJsonSha256: identity.packageJsonSha256,
    packageVersion: identity.packageVersion,
  };
}

// ---------------------------------------------------------------------------
// Certification evidence bundles (evidenceKind "omp-certification-run-v1")
// ---------------------------------------------------------------------------

/**
 * Only bundles produced by THIS certification runner may feed a ledger
 * assessment. Live-cell local observations carry evidenceKind
 * "local-observation" and are rejected by the certification schemas, so
 * untrusted local material can never be promoted into the public ledger.
 */
export const CERTIFICATION_EVIDENCE_KIND = "omp-certification-run-v1";

const certificationRunIdSchema = z.string().min(1).max(256);
const ompArtifactSchema = z
  .object({
    entrypointSha256: hashSchema,
    packageJsonSha256: hashSchema,
  })
  .strict();
const certificationOutcomeSchema = z.enum([
  "passed",
  "passed-with-diagnostics",
  "failed",
]);

export const runtimeCapabilityEvidenceSchema = z
  .object({
    schemaVersion: z.literal(1),
    profile: z.literal("omp-runtime-capabilities-v1"),
    evidenceKind: z.literal(CERTIFICATION_EVIDENCE_KIND),
    runId: certificationRunIdSchema,
    pluginTarballSha256: hashSchema,
    ompVersion: exactStableRuntimeSchema,
    ompArtifact: ompArtifactSchema,
    inventoryVersion: z.literal("omp-extension-v1"),
    capabilities: z.record(z.string(), z.enum(["present", "absent"])),
    pluginRegistered: z.boolean(),
    missingRequired: z.array(z.string()),
    missingOptional: z.array(z.string()),
    outcome: certificationOutcomeSchema,
  })
  .strict();
export type RuntimeCapabilityEvidence = z.infer<
  typeof runtimeCapabilityEvidenceSchema
>;

export const COMMAND_SURFACE_COMMANDS = [
  "help",
  "status",
  "report",
  "onboard plan",
] as const;
export type CommandSurfaceCommand = (typeof COMMAND_SURFACE_COMMANDS)[number];

export const commandSurfaceEvidenceSchema = z
  .object({
    schemaVersion: z.literal(1),
    profile: z.literal("omp-command-surface-v1"),
    evidenceKind: z.literal(CERTIFICATION_EVIDENCE_KIND),
    runId: certificationRunIdSchema,
    pluginTarballSha256: hashSchema,
    ompVersion: exactStableRuntimeSchema,
    ompArtifact: ompArtifactSchema,
    commandSetSha256: hashSchema,
    commands: z
      .array(
        z
          .object({
            command: z.enum(COMMAND_SURFACE_COMMANDS),
            agentInvoked: z.boolean(),
            contentValidated: z.boolean(),
            outputSha256: hashSchema,
          })
          .strict(),
      )
      .length(COMMAND_SURFACE_COMMANDS.length),
    outcome: certificationOutcomeSchema,
  })
  .strict();
export type CommandSurfaceEvidence = z.infer<
  typeof commandSurfaceEvidenceSchema
>;

export const hostEventCertificationEvidenceSchema = z
  .object({
    schemaVersion: z.literal(1),
    profile: z.literal("omp-host-events-v1"),
    evidenceKind: z.literal(CERTIFICATION_EVIDENCE_KIND),
    runId: certificationRunIdSchema,
    pluginTarballSha256: hashSchema,
    pluginValidatorModuleSha256: hashSchema,
    ompVersion: exactStableRuntimeSchema,
    ompArtifact: ompArtifactSchema,
    hostEventScenarioSetSha256: hashSchema,
    requiredEventsObserved: z.array(z.string()),
    optionalEventsObserved: z.array(z.string()),
    schemaValid: z.boolean(),
    orderingValid: z.boolean(),
    isolationValid: z.boolean(),
    identityValid: z.boolean(),
    bindingValid: z.boolean(),
    reasonCodes: z.array(z.string()),
    diagnostics: z.array(z.string()),
    outcome: certificationOutcomeSchema,
    sources: z
      .object({
        observerLogSha256: hashSchema,
        driverLogSha256: hashSchema,
        scenarioSha256: hashSchema,
      })
      .strict(),
  })
  .strict();
export type HostEventCertificationEvidence = z.infer<
  typeof hostEventCertificationEvidenceSchema
>;

export const certificationEvidenceBundleSchema = z.discriminatedUnion(
  "profile",
  [
    runtimeCapabilityEvidenceSchema,
    commandSurfaceEvidenceSchema,
    hostEventCertificationEvidenceSchema,
  ],
);
export type CertificationEvidenceBundle = z.infer<
  typeof certificationEvidenceBundleSchema
>;

/**
 * Re-wraps one validated live-cell local observation as this runner's
 * certification-run evidence. The live cell executed inside THIS
 * certification run, so the runner is the origin of record; the raw local
 * bundle stays in the ephemeral run dir and is never committed. A bundle
 * that fails the live-cell schema (or was not produced by the suite) throws.
 */
export function hostEventCertificationBundleFromLiveCell(
  localBundle: unknown,
  input: {
    readonly runId: string;
    readonly hostEventScenarioSetSha256: string;
  },
): HostEventCertificationEvidence {
  const local = hostEventEvidenceBundleSchema.parse(localBundle);
  return hostEventCertificationEvidenceSchema.parse({
    schemaVersion: 1,
    profile: "omp-host-events-v1",
    evidenceKind: CERTIFICATION_EVIDENCE_KIND,
    runId: input.runId,
    pluginTarballSha256: local.pluginTarballSha256,
    pluginValidatorModuleSha256: local.pluginValidatorModuleSha256,
    ompVersion: local.ompVersion,
    ompArtifact: local.ompArtifact,
    hostEventScenarioSetSha256: input.hostEventScenarioSetSha256,
    requiredEventsObserved: local.requiredEventsObserved,
    optionalEventsObserved: local.optionalEventsObserved,
    schemaValid: local.schemaValid,
    orderingValid: local.orderingValid,
    isolationValid: local.isolationValid,
    identityValid: local.identityValid,
    bindingValid: local.bindingValid,
    reasonCodes: local.reasonCodes,
    diagnostics: local.diagnostics,
    outcome: local.outcome,
    sources: local.sources,
  });
}

// ---------------------------------------------------------------------------
// Content-addressed evidence writer (evidence/<sha256>.json convention)
// ---------------------------------------------------------------------------

export interface CertificationEvidenceWrite {
  readonly locator: string;
  readonly sha256: string;
  readonly bytes: Uint8Array;
}

/**
 * Serializes one certification evidence bundle to its canonical
 * content-addressed bytes. The caller writes the bytes under
 * `<evidenceRoot>/<sha256>.json`; the ledger locator is the plugin-relative
 * `validation/p0/evidence/<sha256>.json` path the controlled bot PR commits.
 */
export function serializeCertificationEvidence(
  bundle: unknown,
): CertificationEvidenceWrite {
  const parsed = certificationEvidenceBundleSchema.safeParse(bundle);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
      "A certification evidence bundle is malformed or carries an untrusted evidence kind.",
      "Only sanitized omp-certification-run-v1 bundles produced by this runner may feed an assessment; local-observation material never enters the public ledger.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const bytes = Buffer.from(`${canonicalizeRfc8785(parsed.data)}\n`, "utf8");
  const sha256 = sha256Hex(bytes);
  return {
    locator: `validation/p0/evidence/${sha256}.json`,
    sha256,
    bytes,
  };
}

// ---------------------------------------------------------------------------
// Subject set documents (command set / Host Event scenario set)
// ---------------------------------------------------------------------------

export interface SubjectDocument {
  readonly bytes: Uint8Array;
  readonly sha256: string;
}

/** Canonical command-set subject document for omp-command-surface-v1. */
export function commandSetSubjectDocument(
  commands: readonly string[],
): SubjectDocument {
  const parsed = z
    .array(z.enum(COMMAND_SURFACE_COMMANDS))
    .length(COMMAND_SURFACE_COMMANDS.length)
    .parse(commands);
  const bytes = Buffer.from(
    `${canonicalizeRfc8785({
      schemaVersion: 1,
      kind: "omp-command-surface-set",
      profile: "omp-command-surface-v1",
      commands: parsed,
    })}\n`,
    "utf8",
  );
  return { bytes, sha256: sha256Hex(bytes) };
}

/**
 * Canonical Host Event scenario-set subject document: the fixed suite
 * definition is identified by the driver/observer content digests plus the
 * single omp-extension-v1 event inventory the suite observes.
 */
export function hostEventScenarioSetSubjectDocument(input: {
  readonly driverSha256: string;
  readonly observerSha256: string;
  readonly events: readonly string[];
}): SubjectDocument {
  const parsed = z
    .object({
      driverSha256: hashSchema,
      observerSha256: hashSchema,
      events: z.array(z.string().min(1)).min(1),
    })
    .strict()
    .parse(input);
  const bytes = Buffer.from(
    `${canonicalizeRfc8785({
      schemaVersion: 1,
      kind: "omp-host-event-scenario-set",
      profile: "omp-host-events-v1",
      driver: "scripts/p0/host-event/drive.mjs",
      driverSha256: parsed.driverSha256,
      observer: "scripts/p0/host-event/observer.mjs",
      observerSha256: parsed.observerSha256,
      events: parsed.events,
    })}\n`,
    "utf8",
  );
  return { bytes, sha256: sha256Hex(bytes) };
}

// ---------------------------------------------------------------------------
// Matrix planning (empty/unavailable matrix is blocked, never pass)
// ---------------------------------------------------------------------------

export interface CertificationRunPlan {
  readonly plan: readonly CompatibilityMatrixCellPlan[];
  readonly report: CompatibilityMatrixRunReport;
  readonly cellsToRun: readonly CompatibilityMatrixCellPlan[];
}

/**
 * Plans minimum/latest/new-runtime cells from the admitted catalog using the
 * per-target tarball-bound peer range. The report is blocked when the catalog
 * is empty; cellsToRun holds only in-range cells (out-of-range cells are
 * recorded with zero profiles and never execute).
 */
export function planCertificationRun(
  targets: unknown,
  input: {
    readonly minimumRuntime: string;
    readonly latestInRangeRuntime: string;
    readonly newRuntime?: string;
  },
): CertificationRunPlan {
  const plan = planCompatibilityMatrixRun(targets, {
    minimumRuntime: input.minimumRuntime,
    latestInRangeRuntime: input.latestInRangeRuntime,
    ...(input.newRuntime === undefined ? {} : { newRuntime: input.newRuntime }),
  });
  const report = reportCompatibilityMatrixRun(plan, {
    liveHarnessAvailable: true,
  });
  return { plan, report, cellsToRun: plan.filter((cell) => cell.inRange) };
}

// ---------------------------------------------------------------------------
// Cell assessment draft and attested finalize
// ---------------------------------------------------------------------------

const draftProfileSchema = z
  .object({
    profile: z.enum([
      "omp-runtime-capabilities-v1",
      "omp-command-surface-v1",
      "omp-host-events-v1",
    ]),
    outcome: z.enum([
      "passed",
      "passed-with-diagnostics",
      "failed",
      "blocked",
      "missing",
    ]),
    evidenceSha256: hashSchema.nullable(),
    evidenceLocator: evidenceLocatorSchema.nullable(),
  })
  .strict()
  .superRefine((profile, context) => {
    const hasDigest = profile.evidenceSha256 !== null;
    if (hasDigest !== (profile.evidenceLocator !== null)) {
      context.addIssue({
        code: "custom",
        message:
          "evidenceSha256 and evidenceLocator must both be present or both be null",
      });
      return;
    }
    if (
      (profile.outcome === "blocked" || profile.outcome === "missing") &&
      hasDigest
    )
      context.addIssue({
        code: "custom",
        message:
          "blocked or missing scopes must not carry a fabricated evidence digest",
      });
    if (
      (profile.outcome === "passed" ||
        profile.outcome === "passed-with-diagnostics" ||
        profile.outcome === "failed") &&
      !hasDigest
    )
      context.addIssue({
        code: "custom",
        message:
          "passed, passed-with-diagnostics and failed scopes must bind content-addressed evidence",
      });
  });

export const cellAssessmentDraftSchema = z
  .object({
    schemaVersion: z.literal(1),
    kind: z.literal("compatibility-cell-assessment-draft"),
    attemptId: z
      .string()
      .regex(/^gha:\d+:\d+$/, "expected gha:<run>:<attempt>"),
    pluginVersion: runtimeVersionSchema,
    pluginTarballSha256: hashSchema,
    pluginPackageIntegrity: sriSchema,
    pluginManifestSha256: hashSchema,
    pluginPeerRange: compatibilityPeerRangeSchema,
    ompVersion: exactStableRuntimeSchema,
    ompRegistryIntegrity: sriSchema,
    loadedRuntimeVersion: exactStableRuntimeSchema,
    loadedRuntimeArtifactSha256: hashSchema,
    commandSetSha256: hashSchema,
    hostEventScenarioSetSha256: hashSchema,
    previousEntrySha256: hashSchema.nullable(),
    profiles: z
      .object({
        runtimeCapabilityProbe: draftProfileSchema,
        commandSurface: draftProfileSchema,
        hostEventSurface: draftProfileSchema,
      })
      .strict(),
    subjectDigests: z
      .object({
        pluginTarball: hashSchema,
        pluginManifest: hashSchema,
        ompArtifact: hashSchema,
        commandSet: hashSchema,
        hostEventScenarioSet: hashSchema,
        runtimeCapabilityProbe: hashSchema.optional(),
        commandSurface: hashSchema.optional(),
        hostEventSurface: hashSchema.optional(),
      })
      .strict(),
  })
  .strict();
export type CellAssessmentDraft = z.infer<typeof cellAssessmentDraftSchema>;

const PROFILE_KEYS = [
  "runtimeCapabilityProbe",
  "commandSurface",
  "hostEventSurface",
] as const;

/**
 * Builds the per-cell assessment draft from the three profile evidence
 * bundles. Every passed/failed profile must carry a verified
 * omp-certification-run-v1 bundle whose digest equals the recorded evidence
 * digest and whose identity fields equal the cell; local-observation bundles
 * are rejected by the certification schemas and never reach a draft. The
 * draft carries no overallOutcome: the outcome is derived at finalize.
 */
export function buildCellAssessmentDraft(input: {
  readonly attemptId: string;
  readonly target: CompatibilityTargetEntry;
  readonly ompVersion: string;
  readonly ompRegistryIntegrity: string;
  readonly host: CellHostIdentity;
  readonly commandSetSha256: string;
  readonly hostEventScenarioSetSha256: string;
  readonly previousEntrySha256: string | null;
  readonly profiles: Readonly<
    Record<
      (typeof PROFILE_KEYS)[number],
      {
        readonly outcome:
          | "passed"
          | "passed-with-diagnostics"
          | "failed"
          | "blocked"
          | "missing";
        readonly evidence?: {
          readonly bundle: unknown;
          readonly sha256: string;
          readonly locator: string;
        };
      }
    >
  >;
}): CellAssessmentDraft {
  const cellRunId = input.attemptId;
  const profiles: Record<string, unknown> = {};
  const subjectDigests: Record<string, string> = {
    pluginTarball: input.target.pluginTarballSha256,
    pluginManifest: input.target.pluginManifestSha256,
    ompArtifact: input.host.entrypointSha256,
    commandSet: input.commandSetSha256,
    hostEventScenarioSet: input.hostEventScenarioSetSha256,
  };
  for (const key of PROFILE_KEYS) {
    const profile = input.profiles[key];
    if (profile.evidence === undefined) {
      profiles[key] = {
        profile:
          key === "runtimeCapabilityProbe"
            ? "omp-runtime-capabilities-v1"
            : key === "commandSurface"
              ? "omp-command-surface-v1"
              : "omp-host-events-v1",
        outcome: profile.outcome,
        evidenceSha256: null,
        evidenceLocator: null,
      };
      continue;
    }
    const written = serializeCertificationEvidence(profile.evidence.bundle);
    if (written.sha256 !== profile.evidence.sha256)
      throw new P0ValidationError(
        "COMPATIBILITY_CELL_EVIDENCE_INVALID",
        "A profile evidence digest does not equal its canonical content.",
        "Record the content-addressed digest produced by the certification runner; never hand-write evidence digests.",
      );
    if (written.locator !== profile.evidence.locator)
      throw new P0ValidationError(
        "COMPATIBILITY_CELL_EVIDENCE_INVALID",
        "A profile evidence locator does not match its content address.",
        "Evidence locators are derived from the content digest; never hand-write them.",
      );
    const parsedBundle = certificationEvidenceBundleSchema.parse(
      profile.evidence.bundle,
    );
    const expectedProfile =
      key === "runtimeCapabilityProbe"
        ? "omp-runtime-capabilities-v1"
        : key === "commandSurface"
          ? "omp-command-surface-v1"
          : "omp-host-events-v1";
    if (
      parsedBundle.profile !== expectedProfile ||
      parsedBundle.pluginTarballSha256 !== input.target.pluginTarballSha256 ||
      parsedBundle.ompVersion !== input.ompVersion ||
      parsedBundle.ompArtifact.entrypointSha256 !==
        input.host.entrypointSha256 ||
      parsedBundle.ompArtifact.packageJsonSha256 !==
        input.host.packageJsonSha256 ||
      parsedBundle.runId !== cellRunId
    )
      throw new P0ValidationError(
        "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
        "A profile evidence bundle does not bind to this cell's target, Runtime, loaded artifact and run.",
        "Evidence is produced inside one isolated certification cell and binds that cell's exact identities; foreign or stale evidence fails closed.",
      );
    profiles[key] = {
      profile: expectedProfile,
      outcome: profile.outcome,
      evidenceSha256: written.sha256,
      evidenceLocator: written.locator,
    };
    subjectDigests[key] = written.sha256;
  }
  const draft = {
    schemaVersion: 1,
    kind: "compatibility-cell-assessment-draft",
    attemptId: input.attemptId,
    pluginVersion: input.target.pluginVersion,
    pluginTarballSha256: input.target.pluginTarballSha256,
    pluginPackageIntegrity: input.target.packageIntegrity,
    pluginManifestSha256: input.target.pluginManifestSha256,
    pluginPeerRange: input.target.pluginPeerRange,
    ompVersion: input.ompVersion,
    ompRegistryIntegrity: input.ompRegistryIntegrity,
    loadedRuntimeVersion: input.host.packageVersion,
    loadedRuntimeArtifactSha256: input.host.entrypointSha256,
    commandSetSha256: input.commandSetSha256,
    hostEventScenarioSetSha256: input.hostEventScenarioSetSha256,
    previousEntrySha256: input.previousEntrySha256,
    profiles,
    subjectDigests,
  };
  const parsed = cellAssessmentDraftSchema.safeParse(draft);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_DRAFT_INVALID",
      "The cell assessment draft is malformed.",
      "Build drafts through buildCellAssessmentDraft from verified cell evidence.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  return parsed.data;
}

/**
 * GitHub sets GITHUB_WORKFLOW_REF to `{owner}/{repo}/{path}@{ref}`. The
 * shipped trust policy pins the path@ref identity; strip a matching
 * `{repository}/` prefix so a trusted main run can append.
 */
export function normalizeCertificationWorkflowRef(
  workflowRef: string,
  repository: string,
): string {
  const prefix = `${repository}/`;
  return workflowRef.startsWith(prefix)
    ? workflowRef.slice(prefix.length)
    : workflowRef;
}

export interface CellAssessmentProvenanceInput {
  readonly issuer: string;
  readonly repository: string;
  readonly workflowRef: string;
  readonly eventName: string;
  readonly runId: string;
  readonly sourceRef: string;
  readonly sourceRevision: string;
}

const cellAssessmentProvenanceInputSchema = z
  .object({
    issuer: z.string().min(1),
    repository: z.string().regex(/^[^/\s]+\/[^/\s]+$/, "owner/name"),
    workflowRef: z.string().min(1),
    eventName: z.string().min(1),
    runId: z.string().regex(/^\d+$/, "expected a GitHub Actions run ID"),
    sourceRef: z.string().min(1),
    sourceRevision: z
      .string()
      .regex(/^[a-f0-9]{40}$/, "expected a full commit SHA"),
  })
  .strict();

/**
 * Completes one draft into an appendable ledger assessment once the
 * workflow's attest action has signed the cell's subject files:
 * - the bundle bytes hash to attestationBundleSha256 and the in-toto subject
 *   digest multiset equals the entry's subjectDigests (content binding);
 * - overallOutcome is DERIVED from profile outcomes and evidence trust via
 *   deriveLedgerAssessmentOutcome — callers can never submit "certified";
 * - evidenceTrust is "verified" only for profiles whose evidence digest is
 *   bound by the verified attestation bundle.
 * Trust-policy field allowlisting and the full two-tier ledger validation
 * still run inside appendLedgerAssessment; this function never appends.
 */
export function finalizeCellAssessment(input: {
  readonly draft: unknown;
  readonly attestationBundleBytes: Uint8Array;
  readonly provenance: CellAssessmentProvenanceInput;
}): LedgerAssessmentEntry {
  const draft = cellAssessmentDraftSchema.safeParse(input.draft);
  if (!draft.success)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_DRAFT_INVALID",
      "The cell assessment draft is malformed.",
      "Finalize only drafts produced by buildCellAssessmentDraft in the same trusted run.",
      { issues: draft.error.issues.map((issue) => issue.message) },
    );
  const provenance = cellAssessmentProvenanceInputSchema.safeParse(
    input.provenance,
  );
  if (!provenance.success)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_PROVENANCE_INVALID",
      "The attestation provenance declaration is malformed.",
      "Finalize only provenance sourced from the trusted workflow's GitHub environment.",
      { issues: provenance.error.issues.map((issue) => issue.message) },
    );
  const workflowRef = normalizeCertificationWorkflowRef(
    provenance.data.workflowRef,
    provenance.data.repository,
  );
  const attestationBundleSha256 = sha256Hex(input.attestationBundleBytes);
  const profiles = Object.fromEntries(
    PROFILE_KEYS.map((key) => {
      const profile = draft.data.profiles[key];
      return [
        key,
        {
          ...profile,
          evidenceTrust:
            profile.evidenceSha256 !== null ? "verified" : "missing",
        },
      ];
    }),
  );
  const core = {
    schemaVersion: 1,
    entryType: "assessment",
    attemptId: draft.data.attemptId,
    pluginPackage: "@kunolu/omp-sbtd",
    pluginVersion: draft.data.pluginVersion,
    pluginTarballSha256: draft.data.pluginTarballSha256,
    pluginPackageIntegrity: draft.data.pluginPackageIntegrity,
    pluginManifestSha256: draft.data.pluginManifestSha256,
    pluginPeerRange: draft.data.pluginPeerRange,
    assessmentTargetSource: "published-catalog",
    ompVersion: draft.data.ompVersion,
    ompRegistryIntegrity: draft.data.ompRegistryIntegrity,
    loadedRuntimeVersion: draft.data.loadedRuntimeVersion,
    loadedRuntimeArtifactSha256: draft.data.loadedRuntimeArtifactSha256,
    contractProfile: "omp-extension-v1",
    commandSetSha256: draft.data.commandSetSha256,
    hostEventScenarioSetSha256: draft.data.hostEventScenarioSetSha256,
    previousEntrySha256: draft.data.previousEntrySha256,
    profiles,
    provenance: {
      format: "github-artifact-attestation-v1",
      issuer: provenance.data.issuer,
      repository: provenance.data.repository,
      workflowRef,
      eventName: provenance.data.eventName,
      runId: provenance.data.runId,
      sourceRef: provenance.data.sourceRef,
      sourceRevision: provenance.data.sourceRevision,
      attestationBundleSha256,
      attestationBundleLocator: `validation/p0/evidence/${attestationBundleSha256}.json`,
      subjectDigests: draft.data.subjectDigests,
    },
  };
  // Parse through the ledger schema with a placeholder outcome, then replace
  // it with the authoritative fixed-priority derivation. The schema parse
  // proves the profile/subject shapes; the derivation is the only source of
  // overallOutcome.
  const sentinel = ledgerAssessmentEntrySchema.safeParse({
    ...core,
    overallOutcome: "eligible",
    entrySha256: sha256Hex("sentinel"),
  });
  if (!sentinel.success)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_DRAFT_INVALID",
      "The finalized assessment does not satisfy the ledger entry schema.",
      "Fix the draft inputs; ledger entries are only built from schema-valid cell data.",
      { issues: sentinel.error.issues.map((issue) => issue.message) },
    );
  const overallOutcome = deriveLedgerAssessmentOutcome(sentinel.data);
  const withOutcome = { ...core, overallOutcome };
  const entrySha256 = ledgerEntryContentSha256(withOutcome);
  const entry = ledgerAssessmentEntrySchema.parse({
    ...withOutcome,
    entrySha256,
  });
  verifyAttestationBundle(input.attestationBundleBytes, entry);
  return entry;
}
