// Slice 6 focused tests for the compatibility target/ledger/trust module.
//
// Trace: docs/assets/omp-plugin-compatibility-decoupling-plan.md §7, §9, §12.4
// and packages/omp-sbtd/features/p0-conformance-release.feature
//   Rule: 认证历史只可追加且独立于 npm 发布.
//
// Mock Strategy: the repository evidence/attestation store is replaced by an
// in-memory CompatibilityEvidenceReader so tests prove content binding
// (bundle existence, digest equality, in-toto subject equality) without
// filesystem fixtures. Fixture identities are deliberately synthetic
// (0.1.0-rc.99) so no test promotes the unpublished rc.13 candidate.
// Cryptographic Sigstore verification is CI-side (gh attestation verify) and
// out of scope here; these tests never claim it.
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type {
  CompatibilityEvidenceReader,
  CompatibilityLedgerDocument,
  CompatibilityTargetsDocument,
  CompatibilityTrustPolicy,
  LedgerAssessmentEntry,
  LedgerProfileResult,
  LedgerRevocationEntry,
} from "../scripts/p0/compatibility-ledger.ts";
import {
  appendCompatibilityTarget,
  appendLedgerAssessment,
  appendLedgerRevocation,
  canonicalizeRfc8785,
  derivePublishedCompatibilityState,
  deriveSupportMatrix,
  ledgerEntryContentSha256,
  parseCompatibilityLedger,
  parseCompatibilityTargets,
  parseCompatibilityTrustPolicy,
  planCompatibilityMatrixRun,
  reportCompatibilityMatrixRun,
  validateCompatibilityLedger,
  verifyCompatibilityLedgerEvidence,
} from "../scripts/p0/compatibility-ledger.ts";
import { P0ValidationError } from "../scripts/p0/release-validator.ts";

const pluginRoot = fileURLToPath(new URL("..", import.meta.url));
const dataRoot = join(pluginRoot, "validation", "p0");

const sha = (label: string): string =>
  createHash("sha256").update(label).digest("hex");
const shaBytes = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex");
const sri = (label: string): string =>
  `sha512-${createHash("sha512").update(label).digest("base64")}`;

const committedTrustPolicy: CompatibilityTrustPolicy = JSON.parse(
  await readFile(join(dataRoot, "compatibility-trust-policy.v1.json"), "utf8"),
) as CompatibilityTrustPolicy;

const TARBALL_SHA = sha("fixture-tarball-rc99");
const MANIFEST_SHA = sha("fixture-manifest-rc99");
const OMP_ARTIFACT_SHA = sha("fixture-omp-artifact-17.3.5");
const PACKAGE_SRI = sri("fixture-tarball-rc99");
const COMMAND_SET_SHA = sha("fixture-command-set");
const SCENARIO_SET_SHA = sha("fixture-host-event-scenario-set");

const fixtureTarget = {
  pluginVersion: "0.1.0-rc.99",
  pluginTarballSha256: TARBALL_SHA,
  packageIntegrity: PACKAGE_SRI,
  pluginManifestSha256: MANIFEST_SHA,
  pluginPeerRange: ">=17.3.5 <18",
} as const;

const registryProof = {
  registryVersion: fixtureTarget.pluginVersion,
  registryDistIntegrity: fixtureTarget.packageIntegrity,
} as const;

const emptyTargets: CompatibilityTargetsDocument = {
  schemaVersion: 1,
  kind: "compatibility-targets",
  targets: [],
};
const emptyLedger: CompatibilityLedgerDocument = {
  schemaVersion: 1,
  kind: "compatibility-ledger",
  entries: [],
};

// In-memory content-addressed repository store. Entries register their
// bundle/evidence bytes here; negative tests use readers that omit or
// replace files to prove fail-closed behavior.
const fixtureFiles = new Map<string, Uint8Array>();

function storeContent(content: string): { locator: string; sha256: string } {
  const bytes = Buffer.from(content, "utf8");
  const digest = shaBytes(bytes);
  const locator = `packages/omp-sbtd/validation/p0/evidence/${digest}.json`;
  fixtureFiles.set(locator, bytes);
  return { locator, sha256: digest };
}

function mapReader(
  files: ReadonlyMap<string, Uint8Array>,
): CompatibilityEvidenceReader {
  return {
    readBytes: async (locator) => {
      const bytes = files.get(locator);
      if (bytes === undefined)
        throw new Error(`ENOENT: no such evidence file ${locator}`);
      return bytes;
    },
  };
}

const trustedReader = mapReader(fixtureFiles);

function buildAttestationBundle(subjects: Readonly<Record<string, string>>): {
  readonly locator: string;
  readonly sha256: string;
} {
  const statement = {
    _type: "https://in-toto.io/Statement/v1",
    subject: Object.entries(subjects).map(([name, digest]) => ({
      name,
      digest: { sha256: digest },
    })),
    predicateType: "https://slsa.dev/provenance/v1",
    predicate: { buildType: "https://example.invalid/omp-certification" },
  };
  const bundle = {
    mediaType: "application/vnd.dev.sigstore.bundle.v0.3+json",
    verificationMaterial: {
      // Fixture stand-in: real bundles carry Fulcio/Rekor material that CI
      // verifies cryptographically with `gh attestation verify` (HITL).
      certificate: "fixture-not-cryptographically-verified",
    },
    dsseEnvelope: {
      payloadType: "application/vnd.in-toto+json",
      payload: Buffer.from(JSON.stringify(statement), "utf8").toString(
        "base64",
      ),
      signatures: [{ sig: "fixture-signature-not-cryptographically-verified" }],
    },
  };
  return storeContent(JSON.stringify(bundle));
}

const trustedProvenanceBase = {
  format: "github-artifact-attestation-v1",
  issuer: "https://token.actions.githubusercontent.com",
  repository: "KunoLu/sbtd-plugins",
  workflowRef:
    ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
  eventName: "workflow_dispatch",
  runId: "8123456789",
  sourceRef: "refs/heads/main",
  sourceRevision: sha("fixture-source-revision").slice(0, 40),
} as const;

type ProfileOutcome =
  | "passed"
  | "passed-with-diagnostics"
  | "failed"
  | "blocked"
  | "missing";

function profileFixture(
  profile:
    | "omp-runtime-capabilities-v1"
    | "omp-command-surface-v1"
    | "omp-host-events-v1",
  outcome: ProfileOutcome,
  evidenceTrust: "verified" | "missing" | "invalid",
): LedgerProfileResult {
  if (outcome === "blocked" || outcome === "missing")
    return {
      profile,
      outcome,
      evidenceTrust,
      evidenceSha256: null,
      evidenceLocator: null,
    };
  const evidence = storeContent(`fixture-evidence-${profile}-${outcome}`);
  return {
    profile,
    outcome,
    evidenceTrust,
    evidenceSha256: evidence.sha256,
    evidenceLocator: evidence.locator,
  };
}

function subjectDigestsFor(profiles: {
  readonly runtimeCapabilityProbe: LedgerProfileResult;
  readonly commandSurface: LedgerProfileResult;
  readonly hostEventSurface: LedgerProfileResult;
}): Record<string, string> {
  const digests: Record<string, string> = {
    pluginTarball: TARBALL_SHA,
    pluginManifest: MANIFEST_SHA,
    ompArtifact: OMP_ARTIFACT_SHA,
    commandSet: COMMAND_SET_SHA,
    hostEventScenarioSet: SCENARIO_SET_SHA,
  };
  for (const key of [
    "runtimeCapabilityProbe",
    "commandSurface",
    "hostEventSurface",
  ] as const) {
    const evidence = profiles[key].evidenceSha256;
    if (evidence !== null) digests[key] = evidence;
  }
  return digests;
}

interface AssessmentOverrides {
  readonly ompVersion?: string;
  readonly loadedRuntimeVersion?: string;
  readonly previousEntrySha256?: string | null;
  readonly assessmentTargetSource?: "candidate-envelope" | "published-catalog";
  readonly profiles?: {
    readonly runtimeCapabilityProbe?: ProfileOutcome;
    readonly commandSurface?: ProfileOutcome;
    readonly hostEventSurface?: ProfileOutcome;
  };
  readonly evidenceTrust?: "verified" | "missing" | "invalid";
  readonly provenance?: Readonly<Record<string, unknown>>;
  readonly overallOutcome?: string;
  readonly pluginVersion?: string;
  readonly attemptId?: string;
}

function makeAssessment(
  overrides: AssessmentOverrides = {},
): LedgerAssessmentEntry {
  const trust = overrides.evidenceTrust ?? "verified";
  const profiles = {
    runtimeCapabilityProbe: profileFixture(
      "omp-runtime-capabilities-v1",
      overrides.profiles?.runtimeCapabilityProbe ?? "passed",
      trust,
    ),
    commandSurface: profileFixture(
      "omp-command-surface-v1",
      overrides.profiles?.commandSurface ?? "passed",
      trust,
    ),
    hostEventSurface: profileFixture(
      "omp-host-events-v1",
      overrides.profiles?.hostEventSurface ?? "passed",
      trust,
    ),
  };
  const subjectDigests = subjectDigestsFor(profiles);
  const bundle = buildAttestationBundle(subjectDigests);
  const draft = {
    schemaVersion: 1,
    entryType: "assessment",
    attemptId: overrides.attemptId ?? "gha:8123456789:1",
    pluginPackage: "@kunolu/omp-sbtd",
    pluginVersion: overrides.pluginVersion ?? fixtureTarget.pluginVersion,
    pluginTarballSha256: TARBALL_SHA,
    pluginPackageIntegrity: PACKAGE_SRI,
    pluginManifestSha256: MANIFEST_SHA,
    pluginPeerRange: fixtureTarget.pluginPeerRange,
    assessmentTargetSource:
      overrides.assessmentTargetSource ?? "published-catalog",
    ompVersion: overrides.ompVersion ?? "17.3.5",
    ompRegistryIntegrity: sri("fixture-omp-registry"),
    loadedRuntimeVersion:
      overrides.loadedRuntimeVersion ?? overrides.ompVersion ?? "17.3.5",
    loadedRuntimeArtifactSha256: OMP_ARTIFACT_SHA,
    contractProfile: "omp-extension-v1",
    commandSetSha256: COMMAND_SET_SHA,
    hostEventScenarioSetSha256: SCENARIO_SET_SHA,
    previousEntrySha256:
      overrides.previousEntrySha256 === undefined
        ? null
        : overrides.previousEntrySha256,
    profiles,
    provenance: {
      ...trustedProvenanceBase,
      attestationBundleSha256: bundle.sha256,
      attestationBundleLocator: bundle.locator,
      subjectDigests,
      ...(overrides.provenance ?? {}),
    },
  };
  const outcome =
    overrides.overallOutcome ??
    deriveDraftOutcome(draft as unknown as LedgerAssessmentEntry);
  const withOutcome = { ...draft, overallOutcome: outcome };
  return {
    ...withOutcome,
    entrySha256: ledgerEntryContentSha256(withOutcome),
  } as LedgerAssessmentEntry;
}

function deriveDraftOutcome(entry: LedgerAssessmentEntry): string {
  // The authoritative derivation is deriveCompatibilityOverallState via
  // deriveLedgerAssessmentOutcome; the fixture mirrors the same fixed
  // priority so drafts are self-consistent by default.
  const profiles = [
    entry.profiles.runtimeCapabilityProbe,
    entry.profiles.commandSurface,
    entry.profiles.hostEventSurface,
  ];
  if (profiles.some((profile) => profile.outcome === "failed"))
    return "incompatible";
  if (
    profiles.every(
      (profile) =>
        (profile.outcome === "passed" ||
          profile.outcome === "passed-with-diagnostics") &&
        profile.evidenceTrust === "verified",
    )
  )
    return "certified";
  if (
    profiles.some(
      (profile) =>
        profile.outcome === "passed" ||
        profile.outcome === "passed-with-diagnostics",
    )
  )
    return "partially-verified";
  return "eligible";
}

function makeRevocation(
  supersedesEntrySha256: string,
  overrides: Readonly<Record<string, unknown>> = {},
): LedgerRevocationEntry {
  const subjectDigests = {
    pluginTarball: TARBALL_SHA,
    pluginManifest: MANIFEST_SHA,
    ompArtifact: OMP_ARTIFACT_SHA,
    commandSet: COMMAND_SET_SHA,
    hostEventScenarioSet: SCENARIO_SET_SHA,
  };
  const bundle = buildAttestationBundle(subjectDigests);
  const draft = {
    schemaVersion: 1,
    entryType: "revocation",
    pluginTarballSha256: TARBALL_SHA,
    ompVersion: "17.3.5",
    contractProfile: "omp-extension-v1",
    supersedesEntrySha256,
    reasonCode: "HOST_REGRESSION_CONFIRMED",
    effectiveAt: "2026-08-25T00:00:00Z",
    provenance: {
      ...trustedProvenanceBase,
      attestationBundleSha256: bundle.sha256,
      attestationBundleLocator: bundle.locator,
      subjectDigests,
    },
    ...overrides,
  };
  return {
    ...draft,
    entrySha256: ledgerEntryContentSha256(draft),
  } as LedgerRevocationEntry;
}

function withPublishedTarget(): CompatibilityTargetsDocument {
  const result = appendCompatibilityTarget(
    emptyTargets,
    fixtureTarget,
    registryProof,
  );
  expect(result.outcome).toBe("appended");
  return result.targets;
}

async function withCertifiedAssessment(): Promise<{
  readonly targets: CompatibilityTargetsDocument;
  readonly ledger: CompatibilityLedgerDocument;
  readonly entry: LedgerAssessmentEntry;
}> {
  const targets = withPublishedTarget();
  const entry = makeAssessment();
  const result = await appendLedgerAssessment(
    emptyLedger,
    targets,
    committedTrustPolicy,
    entry,
    trustedReader,
  );
  expect(result.outcome).toBe("appended");
  return { targets, ledger: result.ledger, entry };
}

async function expectErrorCode(
  action: () => unknown | Promise<unknown>,
  code: string,
): Promise<void> {
  try {
    await action();
  } catch (error) {
    expect(error).toBeInstanceOf(P0ValidationError);
    expect((error as P0ValidationError).code).toBe(code);
    return;
  }
  throw new Error(`Expected the action to fail closed with ${code}.`);
}

describe("compatibility target catalog", () => {
  it("parses the committed catalog, ledger and trust policy", async () => {
    const [targetsRaw, ledgerRaw, policyRaw] = await Promise.all([
      readFile(join(dataRoot, "compatibility-targets.v1.json"), "utf8"),
      readFile(join(dataRoot, "compatibility-ledger.v1.json"), "utf8"),
      readFile(join(dataRoot, "compatibility-trust-policy.v1.json"), "utf8"),
    ]);
    const catalog = parseCompatibilityTargets(JSON.parse(targetsRaw));
    expect(catalog.targets.map((target) => target.pluginVersion)).toEqual([
      "0.1.0-rc.12",
      "0.1.0-rc.13",
    ]);
    // Active ledger starts empty after the KunoLu/KPi → KunoLu/sbtd-plugins
    // cutover: historical KPi attestations live in the legacy archive and are
    // not rewritten to pretend they were signed by this repository.
    expect(parseCompatibilityLedger(JSON.parse(ledgerRaw)).entries).toEqual(
      [],
    );
    const legacyArchive = JSON.parse(
      await readFile(
        join(dataRoot, "compatibility-ledger.kunolu-kpi-legacy.v1.json"),
        "utf8",
      ),
    ) as {
      kind: string;
      archivedFromRepository: string;
      entries: ReadonlyArray<{ provenance: { repository: string } }>;
    };
    expect(legacyArchive.kind).toBe("compatibility-ledger-legacy-archive");
    expect(legacyArchive.archivedFromRepository).toBe("KunoLu/KPi");
    expect(legacyArchive.entries.length).toBeGreaterThanOrEqual(1);
    expect(
      legacyArchive.entries.every(
        (entry) => entry.provenance.repository === "KunoLu/KPi",
      ),
    ).toBe(true);
    const policy = parseCompatibilityTrustPolicy(JSON.parse(policyRaw));
    expect(policy.attestation.repository).toBe("KunoLu/sbtd-plugins");
    expect(policy.attestation.sourceRefs).toEqual(["refs/heads/main"]);
    expect(policy.attestation.requiredSubjects).toEqual(
      expect.arrayContaining(["commandSet", "hostEventScenarioSet"]),
    );
    const packaged = JSON.parse(
      await readFile(join(pluginRoot, "package.json"), "utf8"),
    ) as { files: string[] };
    expect(packaged.files).toContain("validation/p0/compatibility.v2.json");
    expect(packaged.files).not.toContain(
      "validation/p0/compatibility-targets.v1.json",
    );
    expect(packaged.files).not.toContain(
      "validation/p0/compatibility-ledger.v1.json",
    );
    expect(packaged.files).not.toContain(
      "validation/p0/compatibility-trust-policy.v1.json",
    );
    expect(
      packaged.files.some(
        (entry) =>
          entry === "validation/p0" ||
          entry.startsWith("validation/p0/evidence") ||
          entry.includes("candidate-envelope") ||
          entry.includes("registry-proof"),
      ),
    ).toBe(false);
  });

  it("keeps the unpublished rc.13 envelope tarball out of the published targets", async () => {
    const raw = await readFile(
      join(dataRoot, "compatibility-targets.v1.json"),
      "utf8",
    );
    const catalog = parseCompatibilityTargets(JSON.parse(raw));
    const candidateRaw = await readFile(
      join(dataRoot, "candidate-envelope.omp-sbtd-0.1.0-rc.13.json"),
      "utf8",
    );
    const candidate = JSON.parse(candidateRaw) as {
      packageVersion: string;
      tarball: { sha256: string };
      publication: { published: boolean };
    };
    expect(candidate.publication.published).toBe(false);
    expect(candidate.tarball.sha256).toBe(
      "61610988e6537c1f478af218f6a13fcb259d90374c0652ffb204d4127a22f9c7",
    );
    expect(
      catalog.targets.some(
        (target) => target.pluginTarballSha256 === candidate.tarball.sha256,
      ),
    ).toBe(false);
    const publishedRc13 = catalog.targets.find(
      (target) => target.pluginVersion === "0.1.0-rc.13",
    );
    expect(publishedRc13?.pluginTarballSha256).toBe(
      "b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185",
    );
  });

  it("appends a published target only with matching exact Registry identity", async () => {
    const result = appendCompatibilityTarget(
      emptyTargets,
      fixtureTarget,
      registryProof,
    );
    expect(result.outcome).toBe("appended");
    expect(result.targets.targets).toHaveLength(1);
    await expectErrorCode(
      () =>
        appendCompatibilityTarget(emptyTargets, fixtureTarget, {
          registryVersion: "0.1.0-rc.100",
          registryDistIntegrity: registryProof.registryDistIntegrity,
        }),
      "COMPATIBILITY_TARGET_REGISTRY_MISMATCH",
    );
    await expectErrorCode(
      () =>
        appendCompatibilityTarget(emptyTargets, fixtureTarget, {
          registryVersion: registryProof.registryVersion,
          registryDistIntegrity: sri("other-tarball"),
        }),
      "COMPATIBILITY_TARGET_REGISTRY_MISMATCH",
    );
  });

  it("treats a duplicate identical target append as a no-op and conflicts fail closed", async () => {
    const catalog = withPublishedTarget();
    const duplicate = appendCompatibilityTarget(
      catalog,
      fixtureTarget,
      registryProof,
    );
    expect(duplicate.outcome).toBe("duplicate-noop");
    expect(duplicate.targets.targets).toHaveLength(1);
    await expectErrorCode(
      () =>
        appendCompatibilityTarget(
          catalog,
          { ...fixtureTarget, pluginManifestSha256: sha("other-manifest") },
          registryProof,
        ),
      "COMPATIBILITY_TARGET_CONFLICT",
    );
    await expectErrorCode(
      () =>
        appendCompatibilityTarget(
          catalog,
          {
            ...fixtureTarget,
            pluginVersion: "0.1.0-rc.100",
          },
          {
            registryVersion: "0.1.0-rc.100",
            registryDistIntegrity: registryProof.registryDistIntegrity,
          },
        ),
      "COMPATIBILITY_TARGET_CONFLICT",
    );
  });
});

describe("compatibility ledger append and validation", () => {
  it("appends a trusted published-catalog assessment and derives certified", async () => {
    const { targets, ledger, entry } = await withCertifiedAssessment();
    expect(ledger.entries).toHaveLength(1);
    expect(entry.overallOutcome).toBe("certified");
    expect(
      await derivePublishedCompatibilityState(
        targets,
        ledger,
        committedTrustPolicy,
        {
          pluginTarballSha256: TARBALL_SHA,
          ompVersion: "17.3.5",
        },
        trustedReader,
      ),
    ).toBe("certified");
  });

  it("treats a duplicate identical assessment append as a no-op", async () => {
    const { targets, ledger, entry } = await withCertifiedAssessment();
    const duplicate = await appendLedgerAssessment(
      ledger,
      targets,
      committedTrustPolicy,
      entry,
      trustedReader,
    );
    expect(duplicate.outcome).toBe("duplicate-noop");
    expect(duplicate.ledger.entries).toHaveLength(1);
  });

  it("rejects a tampered entry digest", async () => {
    const targets = withPublishedTarget();
    const tampered = {
      ...makeAssessment(),
      ompRegistryIntegrity: sri("tampered-registry"),
    };
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          tampered,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_ENTRY_TAMPERED",
    );
  });

  it.each([
    ["issuer", { issuer: "https://example.invalid" }],
    ["fork repository", { repository: "someone-else/KPi" }],
    [
      "workflow identity",
      {
        workflowRef: ".github/workflows/other.yml@refs/heads/main",
      },
    ],
    ["source ref", { sourceRef: "refs/heads/feature/untrusted" }],
    ["event", { eventName: "pull_request" }],
  ])("rejects untrusted provenance: wrong %s", async (_label, mutation) => {
    const targets = withPublishedTarget();
    const entry = makeAssessment({
      provenance: mutation,
      overallOutcome: "certified",
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          entry,
          trustedReader,
        ),
      "COMPATIBILITY_PROVENANCE_UNTRUSTED",
    );
    // The public state is unchanged: no entry was appended.
    expect(
      await derivePublishedCompatibilityState(
        targets,
        emptyLedger,
        committedTrustPolicy,
        { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.3.5" },
        trustedReader,
      ),
    ).toBe("eligible");
  });

  it("rejects internally consistent forged provenance without a real bundle", async () => {
    // Every self-declared field matches the trust policy, but the referenced
    // attestation bundle does not exist in the repository evidence root:
    // field match alone is never trusted and certified stays unreachable.
    const targets = withPublishedTarget();
    const forged = makeAssessment();
    const readerWithoutBundle = mapReader(new Map());
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          forged,
          readerWithoutBundle,
        ),
      "COMPATIBILITY_ATTESTATION_MISSING",
    );
    // Even if the forged entry were hand-written into the ledger file, the
    // public derivation fails closed instead of deriving certified.
    const forgedLedger: CompatibilityLedgerDocument = {
      ...emptyLedger,
      entries: [forged],
    };
    await expectErrorCode(
      () =>
        derivePublishedCompatibilityState(
          targets,
          forgedLedger,
          committedTrustPolicy,
          { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.3.5" },
          readerWithoutBundle,
        ),
      "COMPATIBILITY_ATTESTATION_MISSING",
    );
    await expectErrorCode(
      () =>
        deriveSupportMatrix(
          targets,
          forgedLedger,
          committedTrustPolicy,
          readerWithoutBundle,
        ),
      "COMPATIBILITY_ATTESTATION_MISSING",
    );
  });

  it("rejects a bundle whose bytes do not match the recorded digest", async () => {
    const targets = withPublishedTarget();
    const entry = makeAssessment();
    const tamperedStore = new Map(fixtureFiles);
    tamperedStore.set(
      entry.provenance.attestationBundleLocator,
      Buffer.from("tampered bundle bytes", "utf8"),
    );
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          entry,
          mapReader(tamperedStore),
        ),
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    );
  });

  it("rejects a bundle whose in-toto subjects differ from the entry digests", async () => {
    const targets = withPublishedTarget();
    // Build a bundle over DIFFERENT subjects, then reference it honestly
    // (digest matches the wrong bundle): content binding must still fail
    // because the statement subjects do not equal the entry subject digests.
    const wrongBundle = buildAttestationBundle({
      pluginTarball: sha("attacker-tarball"),
      pluginManifest: MANIFEST_SHA,
      ompArtifact: OMP_ARTIFACT_SHA,
    });
    const forged = makeAssessment({
      provenance: {
        attestationBundleSha256: wrongBundle.sha256,
        attestationBundleLocator: wrongBundle.locator,
      },
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          forged,
          trustedReader,
        ),
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    );
  });

  it("rejects a missing referenced profile evidence file", async () => {
    const targets = withPublishedTarget();
    const entry = makeAssessment();
    const store = new Map(fixtureFiles);
    const locator = entry.profiles.commandSurface.evidenceLocator;
    expect(locator).not.toBeNull();
    store.delete(locator as string);
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          entry,
          mapReader(store),
        ),
      "COMPATIBILITY_EVIDENCE_MISSING",
    );
  });

  it("rejects an attestation whose entry subjects do not match the identity", async () => {
    const targets = withPublishedTarget();
    const entry = makeAssessment();
    const rebound = {
      ...entry,
      provenance: {
        ...entry.provenance,
        subjectDigests: {
          ...entry.provenance.subjectDigests,
          pluginTarball: sha("different-tarball"),
        },
      },
    };
    const finalized = {
      ...rebound,
      entrySha256: ledgerEntryContentSha256(rebound),
    };
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          finalized,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
    );
  });

  it("rejects command-set or scenario-set swaps without matching attestation subjects", async () => {
    // commandSetSha256 and hostEventScenarioSetSha256 are part of the
    // attested subject universe: swapping either without a matching
    // attestation subject can neither append as trusted nor derive certified.
    const targets = withPublishedTarget();
    for (const [field, subjectKey] of [
      ["commandSetSha256", "commandSet"],
      ["hostEventScenarioSetSha256", "hostEventScenarioSet"],
    ] as const) {
      // Swap only the entry field: the attested subject no longer matches.
      const fieldSwapped = {
        ...makeAssessment(),
        [field]: sha(`attacker-${subjectKey}`),
      };
      const forgedField = {
        ...fieldSwapped,
        entrySha256: ledgerEntryContentSha256(fieldSwapped),
      };
      await expectErrorCode(
        () =>
          appendLedgerAssessment(
            emptyLedger,
            targets,
            committedTrustPolicy,
            forgedField,
            trustedReader,
          ),
        "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
      );
      // Swap both the field and the declared subject: the committed bundle
      // still attests the original digest.
      const base = makeAssessment();
      const fullSwapped = {
        ...base,
        [field]: sha(`attacker-${subjectKey}`),
        provenance: {
          ...base.provenance,
          subjectDigests: {
            ...base.provenance.subjectDigests,
            [subjectKey]: sha(`attacker-${subjectKey}`),
          },
        },
      };
      const forgedFull = {
        ...fullSwapped,
        entrySha256: ledgerEntryContentSha256(fullSwapped),
      };
      await expectErrorCode(
        () =>
          appendLedgerAssessment(
            emptyLedger,
            targets,
            committedTrustPolicy,
            forgedFull,
            trustedReader,
          ),
        "COMPATIBILITY_ATTESTATION_UNVERIFIED",
      );
      // The public state never derives certified from such an entry.
      await expect(
        derivePublishedCompatibilityState(
          targets,
          { ...emptyLedger, entries: [forgedField] },
          committedTrustPolicy,
          {
            pluginTarballSha256: TARBALL_SHA,
            ompVersion: "17.3.5",
          },
          trustedReader,
        ),
      ).rejects.toThrowError(/attestation subjects do not equal/);
    }
  });

  it("rejects a revocation whose subjects drift from the superseded assessment sets", async () => {
    const targets = withPublishedTarget();
    const certified = await appendLedgerAssessment(
      emptyLedger,
      targets,
      committedTrustPolicy,
      makeAssessment(),
      trustedReader,
    );
    const superseded = certified.ledger.entries[0];
    if (superseded === undefined)
      throw new Error(
        "expected the certified ledger to contain one assessment",
      );
    const driftedBase = makeRevocation(superseded.entrySha256);
    const driftedSubjects = {
      ...driftedBase,
      provenance: {
        ...driftedBase.provenance,
        subjectDigests: {
          ...driftedBase.provenance.subjectDigests,
          commandSet: sha("attacker-command-set"),
        },
      },
    };
    const drifted = {
      ...driftedSubjects,
      entrySha256: ledgerEntryContentSha256(driftedSubjects),
    };
    await expectErrorCode(
      () =>
        appendLedgerRevocation(
          certified.ledger,
          committedTrustPolicy,
          drifted,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
    );
  });

  it("rejects local-observation material from the public ledger", async () => {
    const targets = withPublishedTarget();
    const local = {
      ...makeAssessment(),
      assessmentTargetSource: "local-observation",
    };
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          local,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_INVALID",
    );
    expect(
      (
        await deriveSupportMatrix(
          targets,
          emptyLedger,
          committedTrustPolicy,
          trustedReader,
        )
      ).cells,
    ).toEqual([]);
  });

  it("rejects out-of-order and unknown successors", async () => {
    const targets = withPublishedTarget();
    const unknownPredecessor = makeAssessment({
      previousEntrySha256: sha("unknown-predecessor"),
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          unknownPredecessor,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_SUCCESSOR_INVALID",
    );
    const { ledger, entry } = await withCertifiedAssessment();
    const outOfOrder = makeAssessment({
      attemptId: "gha:8123456789:2",
      previousEntrySha256: sha("not-the-latest"),
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          ledger,
          targets,
          committedTrustPolicy,
          outOfOrder,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_SUCCESSOR_INVALID",
    );
    const linked = makeAssessment({
      attemptId: "gha:8123456789:2",
      previousEntrySha256: entry.entrySha256,
    });
    const appended = await appendLedgerAssessment(
      ledger,
      targets,
      committedTrustPolicy,
      linked,
      trustedReader,
    );
    expect(appended.outcome).toBe("appended");
    expect(appended.ledger.entries).toHaveLength(2);
  });

  it("rejects an out-of-range assessment and never runs profiles for it", async () => {
    const targets = withPublishedTarget();
    const entry = makeAssessment({
      ompVersion: "18.0.0",
      loadedRuntimeVersion: "18.0.0",
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          entry,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_OUT_OF_RANGE",
    );
  });

  it("rejects an assessment whose loaded Runtime differs from the target version", async () => {
    const targets = withPublishedTarget();
    const entry = makeAssessment({
      ompVersion: "17.3.5",
      loadedRuntimeVersion: "17.4.0",
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          entry,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_RUNTIME_MISMATCH",
    );
  });

  it("rejects an entry whose submitted overallOutcome is not derived", async () => {
    const targets = withPublishedTarget();
    const lying = makeAssessment({
      profiles: { hostEventSurface: "blocked" },
      overallOutcome: "certified",
    });
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          lying,
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_OUTCOME_MISMATCH",
    );
  });

  it("still appends trusted partial and failed runs with the derived outcome", async () => {
    const targets = withPublishedTarget();
    const partial = makeAssessment({
      profiles: { hostEventSurface: "blocked" },
      evidenceTrust: "verified",
    });
    const partialResult = await appendLedgerAssessment(
      emptyLedger,
      targets,
      committedTrustPolicy,
      partial,
      trustedReader,
    );
    expect(partial.overallOutcome).toBe("partially-verified");
    expect(partialResult.outcome).toBe("appended");
    const failed = makeAssessment({
      attemptId: "gha:8123456789:2",
      ompVersion: "17.4.0",
      profiles: { hostEventSurface: "failed" },
    });
    const failedResult = await appendLedgerAssessment(
      partialResult.ledger,
      targets,
      committedTrustPolicy,
      failed,
      trustedReader,
    );
    expect(failed.overallOutcome).toBe("incompatible");
    expect(failedResult.ledger.entries).toHaveLength(2);
    expect(
      await derivePublishedCompatibilityState(
        targets,
        failedResult.ledger,
        committedTrustPolicy,
        { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.3.5" },
        trustedReader,
      ),
    ).toBe("partially-verified");
    expect(
      await derivePublishedCompatibilityState(
        targets,
        failedResult.ledger,
        committedTrustPolicy,
        { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.4.0" },
        trustedReader,
      ),
    ).toBe("incompatible");
  });

  it("keeps candidate assessments out of the public matrix until admission", async () => {
    const candidateEntry = makeAssessment({
      assessmentTargetSource: "candidate-envelope",
    });
    const appended = await appendLedgerAssessment(
      emptyLedger,
      emptyTargets,
      committedTrustPolicy,
      candidateEntry,
      trustedReader,
    );
    expect(appended.outcome).toBe("appended");
    // Hidden before admission: no published target, no matrix cell.
    expect(
      (
        await deriveSupportMatrix(
          emptyTargets,
          appended.ledger,
          committedTrustPolicy,
          trustedReader,
        )
      ).cells,
    ).toEqual([]);
    await expectErrorCode(
      () =>
        derivePublishedCompatibilityState(
          emptyTargets,
          appended.ledger,
          committedTrustPolicy,
          { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.3.5" },
          trustedReader,
        ),
      "COMPATIBILITY_TARGET_UNKNOWN",
    );
    // Admission appends the exact Registry-verified target and the matrix
    // reuses the immutable candidate assessment without rewriting it.
    const targets = withPublishedTarget();
    const matrix = await deriveSupportMatrix(
      targets,
      appended.ledger,
      committedTrustPolicy,
      trustedReader,
    );
    expect(matrix.cells).toHaveLength(1);
    expect(matrix.cells[0]?.state).toBe("certified");
    expect(matrix.cells[0]?.sourceEntrySha256).toBe(candidateEntry.entrySha256);
    // After admission, new candidate-envelope entries for the same identity
    // are rejected; the published-catalog source is required.
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          appended.ledger,
          targets,
          committedTrustPolicy,
          makeAssessment({
            attemptId: "gha:8123456789:2",
            assessmentTargetSource: "candidate-envelope",
            previousEntrySha256: candidateEntry.entrySha256,
          }),
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
    );
  });

  it("rejects published-catalog assessments for unknown or conflicting identities", async () => {
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          emptyTargets,
          committedTrustPolicy,
          makeAssessment(),
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
    );
    const targets = withPublishedTarget();
    await expectErrorCode(
      () =>
        appendLedgerAssessment(
          emptyLedger,
          targets,
          committedTrustPolicy,
          makeAssessment({ pluginVersion: "0.1.0-rc.100" }),
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
    );
  });

  it("derives revoked from a trusted append-only revocation and retains history", async () => {
    const { targets, ledger, entry } = await withCertifiedAssessment();
    const revocation = makeRevocation(entry.entrySha256);
    const revoked = await appendLedgerRevocation(
      ledger,
      committedTrustPolicy,
      revocation,
      trustedReader,
    );
    expect(revoked.outcome).toBe("appended");
    expect(revoked.ledger.entries).toHaveLength(2);
    expect(revoked.ledger.entries[0]?.entryType).toBe("assessment");
    expect(
      (revoked.ledger.entries[0] as LedgerAssessmentEntry).overallOutcome,
    ).toBe("certified");
    expect(
      await derivePublishedCompatibilityState(
        targets,
        revoked.ledger,
        committedTrustPolicy,
        { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.3.5" },
        trustedReader,
      ),
    ).toBe("revoked");
    // A fresh complete certification links the revocation and restores
    // certified without deleting or rewriting history.
    const recertified = makeAssessment({
      attemptId: "gha:8123456789:3",
      previousEntrySha256: revocation.entrySha256,
    });
    const restored = await appendLedgerAssessment(
      revoked.ledger,
      targets,
      committedTrustPolicy,
      recertified,
      trustedReader,
    );
    expect(restored.ledger.entries).toHaveLength(3);
    expect(
      await derivePublishedCompatibilityState(
        targets,
        restored.ledger,
        committedTrustPolicy,
        { pluginTarballSha256: TARBALL_SHA, ompVersion: "17.3.5" },
        trustedReader,
      ),
    ).toBe("certified");
    // A revocation must supersede the latest entry of its identity.
    await expectErrorCode(
      () =>
        appendLedgerRevocation(
          restored.ledger,
          committedTrustPolicy,
          makeRevocation(entry.entrySha256, {
            effectiveAt: "2026-08-25T01:00:00Z",
          }),
          trustedReader,
        ),
      "COMPATIBILITY_LEDGER_SUCCESSOR_INVALID",
    );
  });

  it("certifies one tarball across two OMP versions with independent chains", async () => {
    const targets = withPublishedTarget();
    const first = await appendLedgerAssessment(
      emptyLedger,
      targets,
      committedTrustPolicy,
      makeAssessment(),
      trustedReader,
    );
    const second = await appendLedgerAssessment(
      first.ledger,
      targets,
      committedTrustPolicy,
      makeAssessment({ attemptId: "gha:8123456789:2", ompVersion: "17.4.0" }),
      trustedReader,
    );
    expect(second.ledger.entries).toHaveLength(2);
    const matrix = await deriveSupportMatrix(
      targets,
      second.ledger,
      committedTrustPolicy,
      trustedReader,
    );
    expect(matrix.cells.map((cell) => [cell.ompVersion, cell.state])).toEqual([
      ["17.3.5", "certified"],
      ["17.4.0", "certified"],
    ]);
  });

  it("fails closed when a persisted ledger entry becomes untrusted", async () => {
    const { targets, ledger } = await withCertifiedAssessment();
    const mutatedPolicy: CompatibilityTrustPolicy = {
      ...committedTrustPolicy,
      attestation: {
        ...committedTrustPolicy.attestation,
        events: ["schedule"],
      },
    };
    await expectErrorCode(
      () => validateCompatibilityLedger(ledger, mutatedPolicy),
      "COMPATIBILITY_PROVENANCE_UNTRUSTED",
    );
    await expectErrorCode(
      () =>
        verifyCompatibilityLedgerEvidence(ledger, mutatedPolicy, trustedReader),
      "COMPATIBILITY_PROVENANCE_UNTRUSTED",
    );
    await expectErrorCode(
      () => deriveSupportMatrix(targets, ledger, mutatedPolicy, trustedReader),
      "COMPATIBILITY_PROVENANCE_UNTRUSTED",
    );
  });
});

describe("RFC 8785 canonical entry hashing", () => {
  it("is independent of member order and ignores the entrySha256 field", () => {
    const entry = makeAssessment();
    const reversed = Object.fromEntries(Object.entries(entry).reverse());
    expect(ledgerEntryContentSha256(reversed)).toBe(entry.entrySha256);
  });

  it("sorts object members by UTF-16 code units with no whitespace", () => {
    expect(canonicalizeRfc8785({ b: 1, A: 2, a: 3 })).toBe(
      '{"A":2,"a":3,"b":1}',
    );
  });
});

describe("support matrix derivation", () => {
  it("is a replayable projection with stable provenance digests", async () => {
    const { targets, ledger, entry } = await withCertifiedAssessment();
    const first = await deriveSupportMatrix(
      targets,
      ledger,
      committedTrustPolicy,
      trustedReader,
    );
    const second = await deriveSupportMatrix(
      targets,
      ledger,
      committedTrustPolicy,
      trustedReader,
    );
    expect(first).toEqual(second);
    expect(first.cells).toHaveLength(1);
    expect(first.cells[0]?.sourceEntrySha256).toBe(entry.entrySha256);
    expect(first.generatedFrom.targetsSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(first.generatedFrom.ledgerSha256).toMatch(/^[a-f0-9]{64}$/);
  });

  it("derives out-of-range from the tarball-bound peer range only", async () => {
    const { targets, ledger } = await withCertifiedAssessment();
    expect(
      await derivePublishedCompatibilityState(
        targets,
        ledger,
        committedTrustPolicy,
        {
          pluginTarballSha256: TARBALL_SHA,
          ompVersion: "18.0.0",
        },
        trustedReader,
      ),
    ).toBe("out-of-range");
    expect(
      await derivePublishedCompatibilityState(
        targets,
        ledger,
        committedTrustPolicy,
        {
          pluginTarballSha256: TARBALL_SHA,
          ompVersion: "17.9.0",
        },
        trustedReader,
      ),
    ).toBe("eligible");
  });

  it("never mutates targets, ledger or plugin identity during updates", async () => {
    const targets = withPublishedTarget();
    const frozenTargets = structuredClone(targets);
    const { ledger } = await withCertifiedAssessment();
    const frozenLedger = structuredClone(ledger);
    const deepFreeze = (value: unknown): void => {
      if (value !== null && typeof value === "object") {
        for (const nested of Object.values(value)) deepFreeze(nested);
        Object.freeze(value);
      }
    };
    deepFreeze(frozenTargets);
    deepFreeze(frozenLedger);
    const matrix = await deriveSupportMatrix(
      frozenTargets,
      frozenLedger,
      committedTrustPolicy,
      trustedReader,
    );
    expect(matrix.cells).toHaveLength(1);
    // The projection carries no publication action surface: ledger updates
    // never pack, publish or move dist-tags, and identity fields are
    // untouched (frozen inputs would have thrown on mutation).
    expect(frozenTargets.targets[0]?.pluginVersion).toBe("0.1.0-rc.99");
    expect(frozenTargets.targets[0]?.pluginTarballSha256).toBe(TARBALL_SHA);
    expect(Object.keys(matrix).sort()).toEqual([
      "cells",
      "generatedFrom",
      "kind",
      "schemaVersion",
    ]);
  });
});

describe("minimum/latest/new-Runtime matrix planning", () => {
  it("runs identical Runtime versions once per target", () => {
    const targets = withPublishedTarget();
    const plan = planCompatibilityMatrixRun(targets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.3.5",
    });
    expect(plan).toHaveLength(1);
    expect(plan[0]?.selectedAs).toEqual(["minimum", "latest"]);
    expect(plan[0]?.profilesToRun).toEqual([
      "omp-runtime-capabilities-v1",
      "omp-command-surface-v1",
      "omp-host-events-v1",
    ]);
  });

  it("plans distinct minimum/latest/new-runtime cells and skips profiles out of range", () => {
    const targets = withPublishedTarget();
    const plan = planCompatibilityMatrixRun(targets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.9.2",
      newRuntime: "18.0.0",
    });
    expect(plan.map((cell) => cell.ompVersion)).toEqual([
      "17.3.5",
      "17.9.2",
      "18.0.0",
    ]);
    const outOfRange = plan.find((cell) => cell.ompVersion === "18.0.0");
    expect(outOfRange?.inRange).toBe(false);
    expect(outOfRange?.profilesToRun).toEqual([]);
    const inRange = plan.filter((cell) => cell.inRange);
    expect(inRange).toHaveLength(2);
    for (const cell of inRange) expect(cell.profilesToRun).toHaveLength(3);
  });

  it("reports blocked without a live harness and never passed or certified", () => {
    const targets = withPublishedTarget();
    const plan = planCompatibilityMatrixRun(targets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.9.2",
      newRuntime: "18.0.0",
    });
    const blocked = reportCompatibilityMatrixRun(plan, {
      liveHarnessAvailable: false,
    });
    expect(blocked.status).toBe("blocked");
    expect(blocked.cells.map((cell) => cell.status)).toEqual([
      "blocked",
      "blocked",
      "out-of-range",
    ]);
    const serialized = JSON.stringify(blocked);
    expect(serialized).not.toContain('"passed"');
    expect(serialized).not.toContain("certified");
    const ready = reportCompatibilityMatrixRun(plan, {
      liveHarnessAvailable: true,
    });
    expect(ready.status).toBe("ready");
    expect(ready.cells.map((cell) => cell.status)).toEqual([
      "pending",
      "pending",
      "out-of-range",
    ]);
    const serializedReady = JSON.stringify(ready);
    expect(serializedReady).not.toContain('"passed"');
    expect(serializedReady).not.toContain("certified");
  });
});
