// Slice 6 compatibility target/ledger/trust validators for
// 08-20-omp-plugin-compatibility-decoupling.
//
// Authority boundaries (plan §2/§7):
// - validation/p0/compatibility-targets.v1.json owns published immutable
//   Plugin target identities; unpublished candidate envelopes are NEVER
//   promoted into it.
// - validation/p0/compatibility-ledger.v1.json owns the append-only
//   assessment/revocation successor chain; entrySha256 is computed over the
//   RFC 8785 canonical bytes of the entry minus its entrySha256 field.
// - validation/p0/compatibility-trust-policy.v1.json owns the accepted
//   issuer/repository/workflow/ref/event/subject rules.
// - The public overall state is derived only from the latest valid trusted
//   successor via deriveCompatibilityOverallState; callers never submit one.
// - Trust is NEVER self-declared: field allowlist matches (issuer,
//   repository, workflow, ref, event) are necessary but not sufficient.
//   Public ledger writes and derivations additionally require the
//   content-addressed attestation bundle to exist inside the repository
//   evidence root, its SHA-256 to equal attestationBundleSha256, and its
//   in-toto statement subject digests to exactly equal the entry's plugin
//   tarball/manifest/loaded OMP artifact/profile evidence digests.
//   Cryptographic Sigstore verification of the bundle is a CI-side step
//   (`gh attestation verify` in the ledger validator workflow) and stays
//   HITL-blocked until the certification environment exists; this module
//   never claims cryptographic verification.
// - The derived support matrix is a replayable projection of published
//   targets plus the trusted chain; candidate-envelope assessments stay
//   hidden until the exact identity is admitted to the published catalog.
// - This module never packs, publishes, moves dist-tags, or talks to npm;
//   the only I/O is reading repository evidence/attestation files through
//   the injected CompatibilityEvidenceReader.
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import {
  type CompatibilityOverallState,
  compatibilityPeerRangeSchema,
  deriveCompatibilityOverallState,
  isExactRuntimeWithinPeerRange,
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
    /^(?:(?:plugins|packages)\/omp-sbtd\/)?validation\/p0\/evidence\/[A-Za-z0-9._/-]+$/,
    "expected a repository evidence locator beneath validation/p0/evidence/",
  )
  .refine(
    (value) => !value.split("/").some((segment) => segment === ".."),
    "evidence locator must not traverse outside the evidence root",
  );

// ---------------------------------------------------------------------------
// RFC 8785 (JSON Canonicalization Scheme)
// ---------------------------------------------------------------------------

function sortKeysUtf16(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeysUtf16);
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    // Default string comparison sorts by UTF-16 code units, which is exactly
    // the RFC 8785 member ordering rule (unlike localeCompare).
    entries.sort(([left], [right]) =>
      left < right ? -1 : left > right ? 1 : 0,
    );
    return Object.fromEntries(
      entries.map(([key, nested]) => [key, sortKeysUtf16(nested)]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_ENTRY_TAMPERED",
      "A ledger value contains a non-finite number, which RFC 8785 rejects.",
      "Regenerate the entry from JSON-parseable data without Infinity or NaN.",
    );
  }
  return value;
}

/**
 * Serializes a JSON value per RFC 8785: object members ordered by UTF-16
 * code units, no whitespace, ECMAScript number formatting (JSON.stringify
 * already produces the required shortest round-trip form).
 */
export function canonicalizeRfc8785(value: unknown): string {
  return JSON.stringify(sortKeysUtf16(value));
}

function sha256Hex(content: string): string {
  return createHash("sha256").update(content, "utf8").digest("hex");
}

// ---------------------------------------------------------------------------
// Published target catalog
// ---------------------------------------------------------------------------

export const compatibilityTargetEntrySchema = z
  .object({
    pluginVersion: runtimeVersionSchema,
    pluginTarballSha256: hashSchema,
    packageIntegrity: sriSchema,
    pluginManifestSha256: hashSchema,
    pluginPeerRange: compatibilityPeerRangeSchema,
  })
  .strict();
export type CompatibilityTargetEntry = z.infer<
  typeof compatibilityTargetEntrySchema
>;

export const compatibilityTargetsDocumentSchema = z
  .object({
    schemaVersion: z.literal(1),
    kind: z.literal("compatibility-targets"),
    targets: z.array(compatibilityTargetEntrySchema),
  })
  .strict();
export type CompatibilityTargetsDocument = z.infer<
  typeof compatibilityTargetsDocumentSchema
>;

function targetIdentityConflicts(
  left: CompatibilityTargetEntry,
  right: CompatibilityTargetEntry,
): boolean {
  return (
    left.pluginVersion !== right.pluginVersion ||
    left.pluginTarballSha256 !== right.pluginTarballSha256 ||
    left.packageIntegrity !== right.packageIntegrity ||
    left.pluginManifestSha256 !== right.pluginManifestSha256 ||
    left.pluginPeerRange !== right.pluginPeerRange
  );
}

export function parseCompatibilityTargets(
  input: unknown,
): CompatibilityTargetsDocument {
  const parsed = compatibilityTargetsDocumentSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_TARGETS_INVALID",
      "The published compatibility target catalog is malformed.",
      "Restore the schemaVersion-1 targets document; never edit an entry in place, append a new one instead.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const { targets } = parsed.data;
  for (let index = 0; index < targets.length; index += 1) {
    const entry = targets[index];
    if (entry === undefined) continue;
    const prior = targets
      .slice(0, index)
      .find(
        (candidate) =>
          candidate.pluginVersion === entry.pluginVersion ||
          candidate.pluginTarballSha256 === entry.pluginTarballSha256,
      );
    if (prior !== undefined)
      throw new P0ValidationError(
        "COMPATIBILITY_TARGET_CONFLICT",
        "The published target catalog contains a duplicate or conflicting identity.",
        "Remove the hand-edited duplicate; target entries are append-only and a version or tarball digest maps to exactly one immutable identity.",
        {
          pluginVersion: entry.pluginVersion,
          pluginTarballSha256: entry.pluginTarballSha256,
        },
      );
  }
  return parsed.data;
}

/**
 * Appends one published target after exact Registry identity verification.
 * `registryProof` carries facts CI already fetched from npm (version and
 * dist.integrity); they must equal the entry identity, so a catalog append
 * can never bind a target that the Registry did not confirm. A duplicate
 * identical append is a no-op; a conflicting identity fails closed.
 */
export function appendCompatibilityTarget(
  document: unknown,
  entry: unknown,
  registryProof: unknown,
): {
  readonly targets: CompatibilityTargetsDocument;
  readonly outcome: "appended" | "duplicate-noop";
} {
  const catalog = parseCompatibilityTargets(document);
  const parsedEntry = compatibilityTargetEntrySchema.safeParse(entry);
  if (!parsedEntry.success)
    throw new P0ValidationError(
      "COMPATIBILITY_TARGETS_INVALID",
      "The candidate published target entry is malformed.",
      "Bind exact pluginVersion, packageIntegrity, tarball SHA-256, manifest SHA-256 and the tarball-bound peer range.",
      { issues: parsedEntry.error.issues.map((issue) => issue.message) },
    );
  const proofSchema = z
    .object({
      registryVersion: runtimeVersionSchema,
      registryDistIntegrity: sriSchema,
    })
    .strict();
  const proof = proofSchema.safeParse(registryProof);
  if (!proof.success)
    throw new P0ValidationError(
      "COMPATIBILITY_TARGET_REGISTRY_MISMATCH",
      "The exact Registry identity proof is malformed.",
      "Fetch the exact published version and dist.integrity from the npm Registry and pass them as data.",
      { issues: proof.error.issues.map((issue) => issue.message) },
    );
  if (
    proof.data.registryVersion !== parsedEntry.data.pluginVersion ||
    proof.data.registryDistIntegrity !== parsedEntry.data.packageIntegrity
  )
    throw new P0ValidationError(
      "COMPATIBILITY_TARGET_REGISTRY_MISMATCH",
      "The target identity does not equal the exact Registry identity.",
      "Append only after the exact published version and dist.integrity equal the frozen candidate identity; tags are discovery hints, never identity.",
      {
        pluginVersion: parsedEntry.data.pluginVersion,
        registryVersion: proof.data.registryVersion,
      },
    );
  const existing = catalog.targets.find(
    (target) =>
      target.pluginVersion === parsedEntry.data.pluginVersion ||
      target.pluginTarballSha256 === parsedEntry.data.pluginTarballSha256,
  );
  if (existing !== undefined) {
    if (!targetIdentityConflicts(existing, parsedEntry.data))
      return { targets: catalog, outcome: "duplicate-noop" };
    throw new P0ValidationError(
      "COMPATIBILITY_TARGET_CONFLICT",
      "A published target with the same version or tarball digest has a conflicting identity.",
      "Never rewrite a published target; revoke through the ledger and publish a new Plugin version under separate authorization.",
      {
        pluginVersion: parsedEntry.data.pluginVersion,
        pluginTarballSha256: parsedEntry.data.pluginTarballSha256,
      },
    );
  }
  return {
    targets: {
      ...catalog,
      targets: [...catalog.targets, parsedEntry.data],
    },
    outcome: "appended",
  };
}

// ---------------------------------------------------------------------------
// Trust policy
// ---------------------------------------------------------------------------

export const compatibilityTrustPolicySchema = z
  .object({
    schemaVersion: z.literal(1),
    kind: z.literal("compatibility-trust-policy"),
    attestation: z
      .object({
        format: z.literal("github-artifact-attestation-v1"),
        issuer: z.literal("https://token.actions.githubusercontent.com"),
        repository: z.literal("KunoLu/sbtd-plugins"),
        workflowRefs: z.array(z.string().min(1)).min(1),
        sourceRefs: z.array(z.string().min(1)).min(1),
        events: z.array(z.enum(["workflow_dispatch", "schedule"])).min(1),
        requiredSubjects: z
          .array(
            z.enum([
              "pluginTarball",
              "pluginManifest",
              "ompArtifact",
              "commandSet",
              "hostEventScenarioSet",
              "runtimeCapabilityProbe",
              "commandSurface",
              "hostEventSurface",
            ]),
          )
          .min(1),
      })
      .strict(),
    statusPublisher: z
      .object({
        context: z.literal("omp-compatibility-ledger-validate"),
        environment: z.literal("omp-compatibility-ledger-status"),
        credential: z.string().min(1),
      })
      .strict(),
  })
  .strict();
export type CompatibilityTrustPolicy = z.infer<
  typeof compatibilityTrustPolicySchema
>;

export function parseCompatibilityTrustPolicy(
  input: unknown,
): CompatibilityTrustPolicy {
  const parsed = compatibilityTrustPolicySchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_TRUST_POLICY_INVALID",
      "The compatibility trust policy is malformed.",
      "Restore the schemaVersion-1 trust policy: accepted issuer, repository, workflow identity, protected source ref, allowed events and required subjects; it contains no secrets.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  return parsed.data;
}

// ---------------------------------------------------------------------------
// Ledger entries
// ---------------------------------------------------------------------------

const ledgerProfileResultSchema = z
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
    evidenceTrust: z.enum(["verified", "missing", "invalid"]),
    evidenceSha256: hashSchema.nullable(),
    evidenceLocator: evidenceLocatorSchema.nullable(),
  })
  .strict()
  .superRefine((profile, context) => {
    const hasDigest = profile.evidenceSha256 !== null;
    const hasLocator = profile.evidenceLocator !== null;
    if (hasDigest !== hasLocator) {
      context.addIssue({
        code: "custom",
        message:
          "evidenceSha256 and evidenceLocator must both be present or both be null",
      });
      return;
    }
    if (profile.outcome === "blocked" || profile.outcome === "missing") {
      if (hasDigest)
        context.addIssue({
          code: "custom",
          message:
            "blocked or missing scopes must not carry a fabricated evidence digest",
        });
      return;
    }
    if (!hasDigest)
      context.addIssue({
        code: "custom",
        message:
          "passed, passed-with-diagnostics and failed scopes must bind content-addressed evidence",
      });
    if (profile.evidenceTrust === "verified" && !hasDigest)
      context.addIssue({
        code: "custom",
        message: "verified evidence trust requires a bound evidence digest",
      });
  });

export type LedgerProfileResult = z.infer<typeof ledgerProfileResultSchema>;

const subjectDigestsSchema = z
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
  .strict();

export const assessmentProvenanceSchema = z
  .object({
    format: z.literal("github-artifact-attestation-v1"),
    issuer: z.string().min(1),
    repository: z.string().regex(/^[^/\s]+\/[^/\s]+$/, "owner/name"),
    workflowRef: z.string().min(1),
    eventName: z.string().min(1),
    runId: z.string().regex(/^\d+$/, "expected a GitHub Actions run ID"),
    sourceRef: z.string().min(1),
    sourceRevision: z
      .string()
      .regex(/^[a-f0-9]{40}$/, "expected a full commit SHA"),
    attestationBundleSha256: hashSchema,
    attestationBundleLocator: evidenceLocatorSchema,
    subjectDigests: subjectDigestsSchema,
  })
  .strict();
export type AssessmentProvenance = z.infer<typeof assessmentProvenanceSchema>;

export const ledgerAssessmentEntrySchema = z
  .object({
    schemaVersion: z.literal(1),
    entryType: z.literal("assessment"),
    attemptId: z
      .string()
      .regex(/^gha:\d+:\d+$/, "expected gha:<run>:<attempt>"),
    pluginPackage: z.literal("@kunolu/omp-sbtd"),
    pluginVersion: runtimeVersionSchema,
    pluginTarballSha256: hashSchema,
    pluginPackageIntegrity: sriSchema,
    pluginManifestSha256: hashSchema,
    pluginPeerRange: compatibilityPeerRangeSchema,
    assessmentTargetSource: z.enum(["candidate-envelope", "published-catalog"]),
    ompVersion: exactStableRuntimeSchema,
    ompRegistryIntegrity: sriSchema,
    loadedRuntimeVersion: exactStableRuntimeSchema,
    loadedRuntimeArtifactSha256: hashSchema,
    contractProfile: z.literal("omp-extension-v1"),
    commandSetSha256: hashSchema,
    hostEventScenarioSetSha256: hashSchema,
    previousEntrySha256: hashSchema.nullable(),
    profiles: z
      .object({
        runtimeCapabilityProbe: ledgerProfileResultSchema,
        commandSurface: ledgerProfileResultSchema,
        hostEventSurface: ledgerProfileResultSchema,
      })
      .strict(),
    provenance: assessmentProvenanceSchema,
    overallOutcome: z.enum([
      "incompatible",
      "certified",
      "partially-verified",
      "eligible",
    ]),
    entrySha256: hashSchema,
  })
  .strict();
export type LedgerAssessmentEntry = z.infer<typeof ledgerAssessmentEntrySchema>;

export const ledgerRevocationEntrySchema = z
  .object({
    schemaVersion: z.literal(1),
    entryType: z.literal("revocation"),
    pluginTarballSha256: hashSchema,
    ompVersion: exactStableRuntimeSchema,
    contractProfile: z.literal("omp-extension-v1"),
    supersedesEntrySha256: hashSchema,
    reasonCode: z.string().min(1).max(64),
    effectiveAt: z.string().datetime({ offset: true }),
    provenance: assessmentProvenanceSchema,
    entrySha256: hashSchema,
  })
  .strict();
export type LedgerRevocationEntry = z.infer<typeof ledgerRevocationEntrySchema>;

export const compatibilityLedgerEntrySchema = z.discriminatedUnion(
  "entryType",
  [ledgerAssessmentEntrySchema, ledgerRevocationEntrySchema],
);
export type CompatibilityLedgerEntry = z.infer<
  typeof compatibilityLedgerEntrySchema
>;

export const compatibilityLedgerDocumentSchema = z
  .object({
    schemaVersion: z.literal(1),
    kind: z.literal("compatibility-ledger"),
    entries: z.array(compatibilityLedgerEntrySchema),
  })
  .strict();
export type CompatibilityLedgerDocument = z.infer<
  typeof compatibilityLedgerDocumentSchema
>;

export function parseCompatibilityLedger(
  input: unknown,
): CompatibilityLedgerDocument {
  const parsed = compatibilityLedgerDocumentSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_INVALID",
      "The compatibility ledger is malformed.",
      "Restore the schemaVersion-1 append-only ledger; local, fork or manual observations never enter the public ledger.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  return parsed.data;
}

/**
 * Computes the canonical entry digest: the entry minus its entrySha256
 * field, serialized per RFC 8785, hashed with SHA-256. The digest proves
 * content integrity only; execution authenticity comes from provenance
 * verification against the trust policy.
 */
export function ledgerEntryContentSha256(entry: unknown): string {
  if (entry === null || typeof entry !== "object" || Array.isArray(entry))
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_INVALID",
      "A ledger entry must be an object to compute its canonical digest.",
      "Build the entry through the ledger schema before hashing.",
    );
  const { entrySha256: _omitted, ...content } = entry as Record<
    string,
    unknown
  >;
  return sha256Hex(canonicalizeRfc8785(content));
}

const PROFILE_SUBJECT_KEYS = [
  "runtimeCapabilityProbe",
  "commandSurface",
  "hostEventSurface",
] as const;
type ProfileSubjectKey = (typeof PROFILE_SUBJECT_KEYS)[number];

function assertProvenanceTrusted(
  provenance: AssessmentProvenance,
  policy: CompatibilityTrustPolicy,
): void {
  const attestation = policy.attestation;
  const trusted =
    provenance.format === attestation.format &&
    provenance.issuer === attestation.issuer &&
    provenance.repository === attestation.repository &&
    attestation.workflowRefs.includes(provenance.workflowRef) &&
    attestation.sourceRefs.includes(provenance.sourceRef) &&
    (attestation.events as readonly string[]).includes(provenance.eventName) &&
    attestation.requiredSubjects.every(
      (subject) =>
        provenance.subjectDigests[
          subject as keyof typeof provenance.subjectDigests
        ] !== undefined,
    );
  if (!trusted)
    throw new P0ValidationError(
      "COMPATIBILITY_PROVENANCE_UNTRUSTED",
      "The assessment provenance does not satisfy the versioned trust policy.",
      "Only attestation signed by the accepted issuer, repository, workflow identity, protected source ref and allowlisted event with all required subjects is trusted; fork, local, manual or foreign-workflow runs are local-observation material and never enter the public ledger.",
      {
        issuer: provenance.issuer,
        repository: provenance.repository,
        workflowRef: provenance.workflowRef,
        sourceRef: provenance.sourceRef,
        eventName: provenance.eventName,
      },
    );
}

function assertAssessmentSubjectsBound(entry: LedgerAssessmentEntry): void {
  const subjects = entry.provenance.subjectDigests;
  const bound =
    subjects.pluginTarball === entry.pluginTarballSha256 &&
    subjects.pluginManifest === entry.pluginManifestSha256 &&
    subjects.ompArtifact === entry.loadedRuntimeArtifactSha256 &&
    subjects.commandSet === entry.commandSetSha256 &&
    subjects.hostEventScenarioSet === entry.hostEventScenarioSetSha256;
  const profilesBound = PROFILE_SUBJECT_KEYS.every((key: ProfileSubjectKey) => {
    const evidence = entry.profiles[key].evidenceSha256;
    const subject = subjects[key];
    if (evidence === null) return subject === undefined;
    return subject === evidence;
  });
  if (!bound || !profilesBound)
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
      "The attestation subjects do not equal the entry's tarball, manifest, loaded OMP artifact, command set, Host Event scenario set and profile evidence digests.",
      "Sign a fresh attestation over the exact tarball, manifest, actual loaded OMP artifact, command set, Host Event scenario set and the three evidence digests; hashes prove integrity only and cannot substitute for subject binding.",
    );
}

function toDerivedProfile(profile: LedgerProfileResult): {
  readonly outcome:
    | "passed"
    | "passed-with-diagnostics"
    | "failed"
    | "blocked"
    | "not-run";
  readonly provenanceTrusted: boolean;
} {
  return {
    outcome: profile.outcome === "missing" ? "not-run" : profile.outcome,
    provenanceTrusted: profile.evidenceTrust === "verified",
  };
}

/**
 * Derives an assessment entry's public overall outcome from its profile
 * outcomes and evidence trust. The entry's own overallOutcome field must
 * equal this derivation; callers never submit an authoritative state.
 */
export function deriveLedgerAssessmentOutcome(
  entry: LedgerAssessmentEntry,
): CompatibilityOverallState {
  return deriveCompatibilityOverallState({
    runtimeInRange: true,
    revoked: false,
    profiles: {
      runtimeCapability: toDerivedProfile(
        entry.profiles.runtimeCapabilityProbe,
      ),
      commandSurface: toDerivedProfile(entry.profiles.commandSurface),
      hostEventSurface: toDerivedProfile(entry.profiles.hostEventSurface),
    },
  });
}

function ledgerIdentityKey(entry: CompatibilityLedgerEntry): string {
  return [
    entry.pluginTarballSha256,
    entry.ompVersion,
    entry.contractProfile,
  ].join("\n");
}

function assertEntryDigest(entry: CompatibilityLedgerEntry): void {
  if (ledgerEntryContentSha256(entry) !== entry.entrySha256)
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_ENTRY_TAMPERED",
      "A ledger entry digest does not match its RFC 8785 canonical content.",
      "Never edit ledger history; repair is a fresh trusted run append linked by previousEntrySha256.",
      { entrySha256: entry.entrySha256 },
    );
}

// ---------------------------------------------------------------------------
// Content-addressed attestation/evidence verification
// ---------------------------------------------------------------------------

/**
 * Reads repository evidence/attestation files. Locators are repo-relative
 * paths beneath packages/omp-sbtd/validation/p0/evidence/ (the
 * plugin-relative `validation/p0/evidence/...` form is normalized to it).
 */
export interface CompatibilityEvidenceReader {
  readonly readBytes: (locator: string) => Promise<Uint8Array>;
}

export function createRepoEvidenceReader(
  workspaceRoot?: string,
): CompatibilityEvidenceReader {
  const root = resolve(
    workspaceRoot ?? fileURLToPath(new URL("../../../..", import.meta.url)),
  );
  return {
    readBytes: async (locator) => {
      const repoRelative = locator.startsWith("packages/omp-sbtd/")
        ? locator
        : join("packages/omp-sbtd", locator);
      const absolute = resolve(root, repoRelative);
      const containment = relative(root, absolute);
      if (
        isAbsolute(containment) ||
        containment.split(/[\\/]/).some((segment) => segment === "..")
      )
        throw new P0ValidationError(
          "COMPATIBILITY_ATTESTATION_MISSING",
          "The evidence locator escapes the workspace root.",
          "Keep evidence locators repo-relative beneath validation/p0/evidence/.",
          { locator },
        );
      return readFile(absolute);
    },
  };
}

const intotoStatementSchema = z
  .object({
    _type: z.literal("https://in-toto.io/Statement/v1"),
    subject: z
      .array(
        z
          .object({
            name: z.string().min(1),
            digest: z.object({ sha256: hashSchema }).strict(),
          })
          .strict(),
      )
      .min(1),
    predicateType: z.string().min(1),
    predicate: z.unknown(),
  })
  .strict();

const sigstoreBundleSchema = z
  .object({
    mediaType: z.string().min(1),
    verificationMaterial: z.unknown(),
    dsseEnvelope: z
      .object({
        payloadType: z.literal("application/vnd.in-toto+json"),
        payload: z.string().min(1),
        signatures: z
          .array(
            z
              .object({
                sig: z.string().min(1),
                keyid: z.string().optional(),
              })
              .strict(),
          )
          .min(1),
      })
      .strict(),
  })
  .strict();

function unverifiedAttestation(
  reason: string,
  details: Readonly<Record<string, unknown>> = {},
): P0ValidationError {
  return new P0ValidationError(
    "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    `The attestation bundle does not prove the entry's subjects: ${reason}`,
    "Regenerate the bundle with the trusted certification workflow over the exact tarball, manifest, loaded OMP artifact and profile evidence digests; self-declared provenance strings are never trusted on their own.",
    details,
  );
}

/**
 * Verifies the content binding of one Sigstore attestation bundle against a
 * ledger entry: the bundle bytes must hash to attestationBundleSha256, parse
 * as a DSSE-wrapped in-toto statement, and its subject digest multiset must
 * exactly equal the entry's subjectDigests. This is integrity/binding
 * verification only; cryptographic signature verification happens in CI
 * (`gh attestation verify`) and is HITL until the certification environment
 * is provisioned.
 */
export function verifyAttestationBundle(
  bundleBytes: unknown,
  entry: CompatibilityLedgerEntry,
): void {
  if (!(bundleBytes instanceof Uint8Array))
    throw new P0ValidationError(
      "COMPATIBILITY_ATTESTATION_MISSING",
      "The attestation bundle was not provided as bytes.",
      "Store the content-addressed bundle in the repository evidence root before referencing it from a ledger entry.",
    );
  const locator = entry.provenance.attestationBundleLocator;
  const actualDigest = createHash("sha256").update(bundleBytes).digest("hex");
  if (actualDigest !== entry.provenance.attestationBundleSha256)
    throw unverifiedAttestation("bundle digest mismatch", {
      locator,
      expected: entry.provenance.attestationBundleSha256,
      actual: actualDigest,
    });
  let bundleJson: unknown;
  try {
    bundleJson = JSON.parse(Buffer.from(bundleBytes).toString("utf8"));
  } catch {
    throw unverifiedAttestation("bundle is not valid JSON", { locator });
  }
  const bundle = sigstoreBundleSchema.safeParse(bundleJson);
  if (!bundle.success)
    throw unverifiedAttestation(
      "bundle is not a DSSE-wrapped Sigstore bundle",
      {
        locator,
        issues: bundle.error.issues.map((issue) => issue.message),
      },
    );
  let statementJson: unknown;
  try {
    statementJson = JSON.parse(
      Buffer.from(bundle.data.dsseEnvelope.payload, "base64").toString("utf8"),
    );
  } catch {
    throw unverifiedAttestation("in-toto payload is not decodable", {
      locator,
    });
  }
  const statement = intotoStatementSchema.safeParse(statementJson);
  if (!statement.success)
    throw unverifiedAttestation("payload is not an in-toto v1 statement", {
      locator,
      issues: statement.error.issues.map((issue) => issue.message),
    });
  const bundleDigests = statement.data.subject
    .map((subject) => subject.digest.sha256)
    .sort();
  const entryDigests = Object.values(entry.provenance.subjectDigests)
    .filter((value): value is string => value !== undefined)
    .sort();
  if (
    bundleDigests.length !== entryDigests.length ||
    bundleDigests.some((digest, index) => digest !== entryDigests[index])
  )
    throw unverifiedAttestation(
      "statement subjects do not equal the entry subject digests",
      { locator, bundleDigests, entryDigests },
    );
}

/**
 * Verifies every ledger entry against real repository content: the
 * attestation bundle must exist at its repo-relative locator, its bytes must
 * match attestationBundleSha256, its in-toto subjects must equal the entry's
 * subject digests, and every referenced profile evidence file must exist and
 * match its evidenceSha256. Missing or unreadable content fails closed with
 * COMPATIBILITY_ATTESTATION_MISSING / COMPATIBILITY_EVIDENCE_MISSING;
 * mismatches fail closed with *_UNVERIFIED / *_MISMATCH. An entry that only
 * carries self-consistent provenance strings cannot pass this tier.
 */
export async function verifyCompatibilityLedgerEvidence(
  document: unknown,
  trustPolicy: unknown,
  reader: CompatibilityEvidenceReader,
): Promise<CompatibilityLedgerDocument> {
  const ledger = validateCompatibilityLedger(document, trustPolicy);
  for (const entry of ledger.entries) {
    let bundleBytes: Uint8Array;
    try {
      bundleBytes = await reader.readBytes(
        entry.provenance.attestationBundleLocator,
      );
    } catch (error) {
      if (error instanceof P0ValidationError) throw error;
      throw new P0ValidationError(
        "COMPATIBILITY_ATTESTATION_MISSING",
        "The attestation bundle referenced by a ledger entry does not exist in the repository evidence root.",
        "Commit the content-addressed bundle in the same controlled bot PR as the first referencing assessment; without the bundle the entry is untrusted and no public state may change.",
        { locator: entry.provenance.attestationBundleLocator },
      );
    }
    verifyAttestationBundle(bundleBytes, entry);
    if (entry.entryType !== "assessment") continue;
    for (const key of PROFILE_SUBJECT_KEYS) {
      const profile = entry.profiles[key];
      if (profile.evidenceSha256 === null || profile.evidenceLocator === null)
        continue;
      let evidenceBytes: Uint8Array;
      try {
        evidenceBytes = await reader.readBytes(profile.evidenceLocator);
      } catch (error) {
        if (error instanceof P0ValidationError) throw error;
        throw new P0ValidationError(
          "COMPATIBILITY_EVIDENCE_MISSING",
          "A profile evidence file referenced by a ledger entry does not exist in the repository evidence root.",
          "Commit the content-addressed evidence file in the same controlled bot PR as its first referencing assessment.",
          { locator: profile.evidenceLocator },
        );
      }
      const actual = createHash("sha256").update(evidenceBytes).digest("hex");
      if (actual !== profile.evidenceSha256)
        throw new P0ValidationError(
          "COMPATIBILITY_EVIDENCE_MISMATCH",
          "A profile evidence file does not match its recorded digest.",
          "Never modify committed evidence; produce fresh evidence with a new trusted run.",
          { locator: profile.evidenceLocator },
        );
    }
  }
  return ledger;
}

/**
 * Fully validates a ledger document against the trust policy: strict schema,
 * canonical entry digests, successor chain order, provenance trust for every
 * entry, subject binding, range membership, loaded-Runtime identity and the
 * derived overall outcome. Any violation fails closed and the public state
 * must not change.
 */
export function validateCompatibilityLedger(
  document: unknown,
  trustPolicy: unknown,
): CompatibilityLedgerDocument {
  const ledger = parseCompatibilityLedger(document);
  const policy = parseCompatibilityTrustPolicy(trustPolicy);
  const seenDigests = new Set<string>();
  const latestByIdentity = new Map<string, CompatibilityLedgerEntry>();
  for (const entry of ledger.entries) {
    assertEntryDigest(entry);
    if (seenDigests.has(entry.entrySha256))
      throw new P0ValidationError(
        "COMPATIBILITY_LEDGER_DUPLICATE",
        "The ledger contains the same entry digest twice.",
        "A duplicate identical append is a no-op at append time and must not persist twice; remove the hand-edited duplicate.",
        { entrySha256: entry.entrySha256 },
      );
    assertProvenanceTrusted(entry.provenance, policy);
    const key = ledgerIdentityKey(entry);
    const latest = latestByIdentity.get(key);
    if (entry.entryType === "assessment") {
      if (
        !isExactRuntimeWithinPeerRange(entry.pluginPeerRange, entry.ompVersion)
      )
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_OUT_OF_RANGE",
          "An assessment exists for a Runtime outside the tarball-bound peer range.",
          "Out-of-range Runtimes never run profiles and never produce ledger entries; out-of-range is derived from the target's bound range only.",
          { ompVersion: entry.ompVersion, peerRange: entry.pluginPeerRange },
        );
      if (entry.loadedRuntimeVersion !== entry.ompVersion)
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_RUNTIME_MISMATCH",
          "The actual loaded Runtime differs from the assessed OMP version.",
          "The real Host must report the exact loaded Runtime version/artifact and it must equal the assessed target version; caller-supplied versions are never accepted.",
          {
            ompVersion: entry.ompVersion,
            loadedRuntimeVersion: entry.loadedRuntimeVersion,
          },
        );
      assertAssessmentSubjectsBound(entry);
      if (deriveLedgerAssessmentOutcome(entry) !== entry.overallOutcome)
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_OUTCOME_MISMATCH",
          "The entry's overallOutcome does not equal the fixed-priority derivation.",
          "overallOutcome is derived by the validator from profile outcomes and evidence trust; never submit an authoritative state.",
          { overallOutcome: entry.overallOutcome },
        );
      if (latest === undefined) {
        if (entry.previousEntrySha256 !== null)
          throw new P0ValidationError(
            "COMPATIBILITY_LEDGER_SUCCESSOR_INVALID",
            "The first assessment for an identity must have a null predecessor.",
            "Link explicit reruns with previousEntrySha256 pointing at the latest entry of the same identity.",
          );
      } else if (entry.previousEntrySha256 !== latest.entrySha256) {
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_SUCCESSOR_INVALID",
          "The assessment does not link the latest entry of its identity.",
          "Append-only successors link the immediately preceding entry digest; out-of-order or unknown predecessors fail closed.",
          { previousEntrySha256: entry.previousEntrySha256 },
        );
      } else if (
        latest.entryType === "assessment" &&
        (latest.pluginVersion !== entry.pluginVersion ||
          latest.pluginManifestSha256 !== entry.pluginManifestSha256 ||
          latest.pluginPeerRange !== entry.pluginPeerRange ||
          latest.pluginPackageIntegrity !== entry.pluginPackageIntegrity)
      ) {
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_CONFLICT",
          "A successor assessment conflicts with the immutable identity of its chain.",
          "One identity chain binds exactly one version, manifest digest, peer range and package integrity; conflicting identity fails closed.",
        );
      }
    } else {
      if (
        latest === undefined ||
        entry.supersedesEntrySha256 !== latest.entrySha256
      )
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_SUCCESSOR_INVALID",
          "A revocation must supersede the latest entry of its identity.",
          "Revocation is a trusted append-only successor naming the current latest entry digest; it never edits history in place.",
          { supersedesEntrySha256: entry.supersedesEntrySha256 },
        );
      if (
        latest !== undefined &&
        latest.entryType === "assessment" &&
        (entry.provenance.subjectDigests.commandSet !==
          latest.commandSetSha256 ||
          entry.provenance.subjectDigests.hostEventScenarioSet !==
            latest.hostEventScenarioSetSha256)
      )
        throw new P0ValidationError(
          "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
          "A revocation's attestation subjects do not equal the superseded assessment's command set and Host Event scenario set digests.",
          "Sign the revocation attestation over the exact subject universe of the assessment it supersedes.",
          { supersedesEntrySha256: entry.supersedesEntrySha256 },
        );
    }
    seenDigests.add(entry.entrySha256);
    latestByIdentity.set(key, entry);
  }
  return ledger;
}

export interface LedgerAppendResult {
  readonly ledger: CompatibilityLedgerDocument;
  readonly outcome: "appended" | "duplicate-noop";
  readonly entrySha256: string;
}

/**
 * Appends one trusted assessment. The existing ledger must already validate
 * (structural tier AND evidence tier); the new entry must carry a correct
 * canonical digest, field-level trusted provenance, a verified
 * content-addressed attestation bundle and evidence files, subject binding,
 * in-range target, matching loaded Runtime, derived outcome and a valid
 * successor link. published-catalog assessments additionally require the
 * exact identity to exist in the published target catalog, and
 * candidate-envelope assessments require that it does not. A duplicate
 * identical append is a no-op; every conflict fails closed.
 */
export async function appendLedgerAssessment(
  document: unknown,
  targets: unknown,
  trustPolicy: unknown,
  entry: unknown,
  reader: CompatibilityEvidenceReader,
): Promise<LedgerAppendResult> {
  const catalog = parseCompatibilityTargets(targets);
  const ledger = await verifyCompatibilityLedgerEvidence(
    document,
    trustPolicy,
    reader,
  );
  const policy = parseCompatibilityTrustPolicy(trustPolicy);
  const parsed = ledgerAssessmentEntrySchema.safeParse(entry);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_INVALID",
      "The assessment entry is malformed.",
      "Build the entry with the schemaVersion-1 assessment shape; local-observation material never enters the public ledger.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const assessment = parsed.data;
  assertEntryDigest(assessment);
  if (
    ledger.entries.some(
      (existing) => existing.entrySha256 === assessment.entrySha256,
    )
  )
    return {
      ledger,
      outcome: "duplicate-noop",
      entrySha256: assessment.entrySha256,
    };
  assertProvenanceTrusted(assessment.provenance, policy);
  const published = catalog.targets.find(
    (target) => target.pluginTarballSha256 === assessment.pluginTarballSha256,
  );
  if (assessment.assessmentTargetSource === "published-catalog") {
    if (
      published === undefined ||
      published.pluginVersion !== assessment.pluginVersion ||
      published.packageIntegrity !== assessment.pluginPackageIntegrity ||
      published.pluginManifestSha256 !== assessment.pluginManifestSha256 ||
      published.pluginPeerRange !== assessment.pluginPeerRange
    )
      throw new P0ValidationError(
        "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
        "A published-catalog assessment must equal an exact published target identity.",
        "Verify the Registry exact version, dist.integrity, tarball and manifest digests and append the published target before recording published-catalog assessments.",
        { pluginTarballSha256: assessment.pluginTarballSha256 },
      );
  } else if (published !== undefined) {
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
      "A candidate-envelope assessment targets an identity that is already published.",
      "After Registry admission, record assessments with assessmentTargetSource published-catalog; never rewrite the immutable candidate entry.",
      { pluginTarballSha256: assessment.pluginTarballSha256 },
    );
  }
  const next: CompatibilityLedgerDocument = {
    ...ledger,
    entries: [...ledger.entries, assessment],
  };
  // Re-running both tiers proves successor chaining, range, runtime,
  // subject, outcome AND attestation/evidence content binding against the
  // combined history in one place.
  await verifyCompatibilityLedgerEvidence(next, policy, reader);
  return {
    ledger: next,
    outcome: "appended",
    entrySha256: assessment.entrySha256,
  };
}

/**
 * Appends one trusted revocation. The revocation must supersede the latest
 * entry of its identity and carry a verified content-addressed attestation
 * bundle; history stays intact and a later fresh complete certification can
 * link a new successor to restore support.
 */
export async function appendLedgerRevocation(
  document: unknown,
  trustPolicy: unknown,
  entry: unknown,
  reader: CompatibilityEvidenceReader,
): Promise<LedgerAppendResult> {
  const ledger = await verifyCompatibilityLedgerEvidence(
    document,
    trustPolicy,
    reader,
  );
  const policy = parseCompatibilityTrustPolicy(trustPolicy);
  const parsed = ledgerRevocationEntrySchema.safeParse(entry);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_LEDGER_INVALID",
      "The revocation entry is malformed.",
      "Build the entry with the schemaVersion-1 revocation shape bound to the superseded entry digest.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const revocation = parsed.data;
  assertEntryDigest(revocation);
  if (
    ledger.entries.some(
      (existing) => existing.entrySha256 === revocation.entrySha256,
    )
  )
    return {
      ledger,
      outcome: "duplicate-noop",
      entrySha256: revocation.entrySha256,
    };
  assertProvenanceTrusted(revocation.provenance, policy);
  const next: CompatibilityLedgerDocument = {
    ...ledger,
    entries: [...ledger.entries, revocation],
  };
  await verifyCompatibilityLedgerEvidence(next, policy, reader);
  return {
    ledger: next,
    outcome: "appended",
    entrySha256: revocation.entrySha256,
  };
}

// ---------------------------------------------------------------------------
// Public state and support-matrix derivation
// ---------------------------------------------------------------------------

function latestEntryForIdentity(
  ledger: CompatibilityLedgerDocument,
  pluginTarballSha256: string,
  ompVersion: string,
): CompatibilityLedgerEntry | undefined {
  let latest: CompatibilityLedgerEntry | undefined;
  for (const entry of ledger.entries) {
    if (
      entry.pluginTarballSha256 === pluginTarballSha256 &&
      entry.ompVersion === ompVersion
    )
      latest = entry;
  }
  return latest;
}

/**
 * Derives the public compatibility state of one published target for one
 * exact Runtime. Out-of-range is decided by the target's tarball-bound
 * historical peer range only; the current Compatibility Policy never
 * reinterprets it. Without any trusted assessment the state starts at
 * eligible. The ledger must pass BOTH validation tiers first (structural
 * plus attestation/evidence content binding), so entries whose provenance
 * is only self-declared never contribute to the derivation.
 */
export async function derivePublishedCompatibilityState(
  targets: unknown,
  ledger: unknown,
  trustPolicy: unknown,
  query: unknown,
  reader: CompatibilityEvidenceReader,
): Promise<CompatibilityOverallState> {
  const catalog = parseCompatibilityTargets(targets);
  const validated = await verifyCompatibilityLedgerEvidence(
    ledger,
    trustPolicy,
    reader,
  );
  const querySchema = z
    .object({
      pluginTarballSha256: hashSchema,
      ompVersion: exactStableRuntimeSchema,
    })
    .strict();
  const parsedQuery = querySchema.safeParse(query);
  if (!parsedQuery.success)
    throw new P0ValidationError(
      "COMPATIBILITY_TARGETS_INVALID",
      "The compatibility state query is malformed.",
      "Query with the exact target tarball SHA-256 and one exact stable Runtime version.",
      { issues: parsedQuery.error.issues.map((issue) => issue.message) },
    );
  const target = catalog.targets.find(
    (candidate) =>
      candidate.pluginTarballSha256 === parsedQuery.data.pluginTarballSha256,
  );
  if (target === undefined)
    throw new P0ValidationError(
      "COMPATIBILITY_TARGET_UNKNOWN",
      "The queried tarball digest is not a published compatibility target.",
      "Select targets only from compatibility-targets.v1.json exact identities; npm tags are one-time discovery hints, never selectors.",
      { pluginTarballSha256: parsedQuery.data.pluginTarballSha256 },
    );
  if (
    !isExactRuntimeWithinPeerRange(
      target.pluginPeerRange,
      parsedQuery.data.ompVersion,
    )
  )
    return "out-of-range";
  const latest = latestEntryForIdentity(
    validated,
    target.pluginTarballSha256,
    parsedQuery.data.ompVersion,
  );
  if (latest === undefined) return "eligible";
  if (latest.entryType === "revocation") return "revoked";
  // A candidate-envelope assessment becomes consumable here only because the
  // exact identity was admitted to the published catalog; admission reuses
  // the immutable assessment instead of rewriting it.
  return deriveLedgerAssessmentOutcome(latest);
}

export interface CompatibilityMatrixCell {
  readonly pluginVersion: string;
  readonly pluginTarballSha256: string;
  readonly ompVersion: string;
  readonly contractProfile: "omp-extension-v1";
  readonly state: CompatibilityOverallState;
  readonly sourceEntrySha256: string;
}

export interface CompatibilitySupportMatrix {
  readonly schemaVersion: 1;
  readonly kind: "compatibility-support-matrix";
  readonly generatedFrom: {
    readonly targetsSha256: string;
    readonly ledgerSha256: string;
  };
  readonly cells: readonly CompatibilityMatrixCell[];
}

/**
 * Derives the public support matrix as a replayable projection: published
 * targets plus the latest valid trusted successor per (target, Runtime).
 * Candidate-envelope assessments only surface after their exact identity was
 * admitted to the catalog; entries failing either validation tier
 * (structural or attestation/evidence content binding) fail the whole
 * derivation closed before any cell is produced. The projection never packs,
 * publishes or moves dist-tags, and never mutates its inputs.
 */
export async function deriveSupportMatrix(
  targets: unknown,
  ledger: unknown,
  trustPolicy: unknown,
  reader: CompatibilityEvidenceReader,
): Promise<CompatibilitySupportMatrix> {
  const catalog = parseCompatibilityTargets(targets);
  const validated = await verifyCompatibilityLedgerEvidence(
    ledger,
    trustPolicy,
    reader,
  );
  const cells: CompatibilityMatrixCell[] = [];
  for (const target of catalog.targets) {
    const versions = new Set<string>();
    for (const entry of validated.entries) {
      if (entry.pluginTarballSha256 === target.pluginTarballSha256)
        versions.add(entry.ompVersion);
    }
    for (const ompVersion of versions) {
      const latest = latestEntryForIdentity(
        validated,
        target.pluginTarballSha256,
        ompVersion,
      );
      if (latest === undefined) continue;
      cells.push({
        pluginVersion: target.pluginVersion,
        pluginTarballSha256: target.pluginTarballSha256,
        ompVersion,
        contractProfile: "omp-extension-v1",
        state:
          latest.entryType === "revocation"
            ? "revoked"
            : deriveLedgerAssessmentOutcome(latest),
        sourceEntrySha256: latest.entrySha256,
      });
    }
  }
  cells.sort((left, right) =>
    left.pluginTarballSha256 < right.pluginTarballSha256
      ? -1
      : left.pluginTarballSha256 > right.pluginTarballSha256
        ? 1
        : left.ompVersion < right.ompVersion
          ? -1
          : left.ompVersion > right.ompVersion
            ? 1
            : 0,
  );
  return {
    schemaVersion: 1,
    kind: "compatibility-support-matrix",
    generatedFrom: {
      targetsSha256: sha256Hex(canonicalizeRfc8785(catalog)),
      ledgerSha256: sha256Hex(canonicalizeRfc8785(validated)),
    },
    cells,
  };
}

// ---------------------------------------------------------------------------
// Minimum/latest/new-Runtime matrix run planning and reporting
// ---------------------------------------------------------------------------

export const MATRIX_PROFILE_IDS = [
  "omp-runtime-capabilities-v1",
  "omp-command-surface-v1",
  "omp-host-events-v1",
] as const;
export type MatrixProfileId = (typeof MATRIX_PROFILE_IDS)[number];

export interface CompatibilityMatrixCellPlan {
  readonly pluginVersion: string;
  readonly pluginTarballSha256: string;
  readonly pluginPeerRange: string;
  readonly ompVersion: string;
  readonly selectedAs: readonly ("minimum" | "latest" | "new-runtime")[];
  readonly inRange: boolean;
  readonly profilesToRun: readonly MatrixProfileId[];
}

/**
 * Plans the minimum/latest/new-Runtime certification cells for every
 * published target. Identical Runtime versions run once per target;
 * out-of-range cells are recorded with zero profiles and never execute.
 */
export function planCompatibilityMatrixRun(
  targets: unknown,
  input: unknown,
): readonly CompatibilityMatrixCellPlan[] {
  const catalog = parseCompatibilityTargets(targets);
  const inputSchema = z
    .object({
      minimumRuntime: exactStableRuntimeSchema,
      latestInRangeRuntime: exactStableRuntimeSchema,
      newRuntime: exactStableRuntimeSchema.optional(),
    })
    .strict();
  const parsed = inputSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_MATRIX_INPUT_INVALID",
      "The matrix run input is malformed.",
      "Provide exact stable minimum and latest-in-range Runtime versions; prereleases never enter the public certification matrix by default.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const roles: ReadonlyArray<
    readonly ["minimum" | "latest" | "new-runtime", string]
  > = [
    ["minimum", parsed.data.minimumRuntime],
    ["latest", parsed.data.latestInRangeRuntime],
    ...(parsed.data.newRuntime === undefined
      ? []
      : ([["new-runtime", parsed.data.newRuntime]] as const)),
  ];
  const plans: CompatibilityMatrixCellPlan[] = [];
  for (const target of catalog.targets) {
    const byVersion = new Map<
      string,
      ("minimum" | "latest" | "new-runtime")[]
    >();
    for (const [role, version] of roles) {
      const existing = byVersion.get(version);
      if (existing === undefined) byVersion.set(version, [role]);
      else existing.push(role);
    }
    for (const [ompVersion, selectedAs] of byVersion) {
      const inRange = isExactRuntimeWithinPeerRange(
        target.pluginPeerRange,
        ompVersion,
      );
      plans.push({
        pluginVersion: target.pluginVersion,
        pluginTarballSha256: target.pluginTarballSha256,
        pluginPeerRange: target.pluginPeerRange,
        ompVersion,
        selectedAs,
        inRange,
        profilesToRun: inRange ? MATRIX_PROFILE_IDS : [],
      });
    }
  }
  plans.sort((left, right) =>
    left.pluginTarballSha256 < right.pluginTarballSha256
      ? -1
      : left.pluginTarballSha256 > right.pluginTarballSha256
        ? 1
        : left.ompVersion < right.ompVersion
          ? -1
          : left.ompVersion > right.ompVersion
            ? 1
            : 0,
  );
  return plans;
}

export interface CompatibilityMatrixCellReport {
  readonly plan: CompatibilityMatrixCellPlan;
  readonly status: "blocked" | "pending" | "out-of-range";
  readonly reason?: string;
}

export interface CompatibilityMatrixRunReport {
  readonly schemaVersion: 1;
  readonly kind: "compatibility-matrix-run-report";
  readonly status: "blocked" | "ready";
  /** Stable machine-readable reason when status is "blocked". */
  readonly reason?: string;
  readonly cells: readonly CompatibilityMatrixCellReport[];
}

/**
 * Reports a planned matrix run without executing profiles. An empty plan (no
 * published targets) is an unavailable matrix and reports blocked, never a
 * false ready. Without a live isolated Host harness every runnable cell
 * reports blocked; with one, cells report pending until the real
 * three-profile run appends trusted evidence. This command NEVER reports
 * passed or certified: those states exist only as ledger-derived outcomes of
 * trusted CI runs.
 */
export function reportCompatibilityMatrixRun(
  plan: readonly CompatibilityMatrixCellPlan[],
  environment: unknown,
): CompatibilityMatrixRunReport {
  const environmentSchema = z
    .object({ liveHarnessAvailable: z.boolean() })
    .strict();
  const parsed = environmentSchema.safeParse(environment);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_MATRIX_INPUT_INVALID",
      "The matrix run environment declaration is malformed.",
      "Declare liveHarnessAvailable explicitly; without a live isolated Host harness the matrix reports blocked, never passed or certified.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  if (plan.length === 0)
    return {
      schemaVersion: 1,
      kind: "compatibility-matrix-run-report",
      status: "blocked",
      reason:
        "no-published-targets: the published compatibility target catalog is empty, so the certification matrix is unavailable; blocked is never a pass.",
      cells: [],
    };
  const cells: CompatibilityMatrixCellReport[] = plan.map((cell) => {
    if (!cell.inRange) return { plan: cell, status: "out-of-range" };
    if (!parsed.data.liveHarnessAvailable)
      return {
        plan: cell,
        status: "blocked",
        reason:
          "No live isolated OMP Host harness is available; runnable cells stay blocked until a trusted CI run appends attested evidence.",
      };
    return { plan: cell, status: "pending" };
  });
  return {
    schemaVersion: 1,
    kind: "compatibility-matrix-run-report",
    status: cells.some((cell) => cell.status === "blocked")
      ? "blocked"
      : "ready",
    cells,
  };
}
