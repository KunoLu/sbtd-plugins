// Slice 1 contract tests for 08-20-omp-plugin-compatibility-decoupling.
//
// These tests encode the confirmed publication/certification split. Slice 2
// (Policy v2 + validator clean cutover) implemented the validator surface
// and turned the policy/range/overall-state scenarios green; the
// ledger-bound scenarios remain specified here and land with Slice 6
// (target/ledger derivation).
//
// Trace: packages/omp-sbtd/features/p0-conformance-release.feature
//   Rule: 精确 tarball 四命令是所有 RC 的唯一 npm 发布兼容性 Gate
//     - "满足四命令验收的 RC 不等待任何兼容认证 profile" is additionally
//       characterized GREEN in p0-release-validator.test.ts (failed
//       compatibility evidence never blocks rc-eligible).
//     - "已发布的 in-range target 没有受信 profile 通过时从 eligible 开始"
//       and "已发布 rc.12 的既有四命令结果不被自动提升为 certified" are
//       covered below.
//   Rule: 兼容认证身份由不可变 target 与 tarball-bound peer range 决定
//     - peer range/dev pin separation, dev-pin-in-range, and OMP 18
//       rejection are covered below; the OMP 18 rejection is bound to the
//       packed candidate identity (packed package.json peer range plus the
//       packaged Policy v2 file), never to the in-memory constant. The
//       ledger-entry identity binding scenario is covered below (Slice 6).
//   Rule: 公开兼容状态由受信证据按固定优先级唯一派生
//     - priority, the unique positive certified rung, partially-verified,
//       host-event gate, and untrusted provenance are covered below,
//       including attestations that omit or swap the required
//       commandSet/hostEventScenarioSet subjects (never trusted, never
//       certified).
//   Rule: 认证历史只可追加且独立于 npm 发布
//     - revocation priority and append-only history retention are covered
//       below at the ledger level (Slice 6); the ledger module is proven
//       pure data (deep-frozen inputs in, fresh documents out), so no
//       pack/publish/dist-tag side-effect channel exists in it. These
//       tests observe no process or Registry publication boundary.
//
// Mock Strategy: none — pure validator contract. The OMP 18 scenario packs
// the current candidate locally (no Host or Registry I/O) so the rejection
// is bound to the packed identity rather than the in-memory constant.
//
// Slice 2 contract surface (implemented by the Policy v2 cutover):
//   validateCompatibilityManifest accepts the Policy v2 shape:
//     { schemaVersion: 2, peerRange, developmentRuntimeVersion,
//       pluginPackage, commands }
//   deriveCompatibilityOverallState(input): overall state where input is
//     { runtimeInRange, revoked?, profiles: { runtimeCapability?,
//       commandSurface?, hostEventSurface? } } and each profile is
//     { outcome: "passed" | "passed-with-diagnostics" | "failed" |
//       "blocked" | "not-run", provenanceTrusted: boolean }.
//     Fixed priority: out-of-range → revoked → incompatible → certified →
//     partially-verified → eligible. Callers never submit an overall state.
import { execFile as executeFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";
import type {
  CompatibilityLedgerDocument,
  CompatibilityTargetsDocument,
  LedgerAssessmentEntry,
  LedgerRevocationEntry,
} from "../scripts/p0/compatibility-ledger.ts";
import {
  appendCompatibilityTarget,
  appendLedgerAssessment,
  appendLedgerRevocation,
  derivePublishedCompatibilityState,
  deriveSupportMatrix,
  ledgerEntryContentSha256,
} from "../scripts/p0/compatibility-ledger.ts";
import * as releaseValidator from "../scripts/p0/release-validator.ts";

// Unchecked cast: the module namespace is read as an open record so missing
// future exports surface as `undefined` and fail with the explicit messages
// below instead of a module-load error that would hide the other tests.
const validator = releaseValidator as unknown as Record<string, unknown>;

// Packed-identity helpers mirror test/agent-plugin-pack.test.ts: pack the
// current candidate exactly as publication would, then read the identity
// back from the extracted tarball.
const runProcess = promisify(executeFile);
const packageManager = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const workspaceRoot = fileURLToPath(new URL("../../..", import.meta.url));
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const temporaryRoots: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

async function packCurrentCandidate(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-compat-contract-pack-"));
  temporaryRoots.push(root);
  const packedRoot = join(root, "packed");
  const extractedRoot = join(root, "extracted");
  await mkdir(packedRoot, { recursive: true });
  await mkdir(extractedRoot, { recursive: true });
  const { stdout } = await runProcess(
    packageManager,
    ["pack", "--pack-destination", packedRoot, "--json"],
    { cwd: pluginRoot },
  );
  const packed = JSON.parse(stdout) as { filename: string };
  const tarball = isAbsolute(packed.filename)
    ? packed.filename
    : resolve(packedRoot, packed.filename);
  await runProcess("tar", ["-xzf", tarball, "-C", extractedRoot]);
  return join(extractedRoot, "package");
}

const OMP_RUNTIME_PACKAGE = "@oh-my-pi/pi-coding-agent";

function dependencySpec(
  manifest: unknown,
  section: "peerDependencies" | "devDependencies",
): unknown {
  if (!manifest || typeof manifest !== "object" || !(section in manifest)) {
    return undefined;
  }
  const entries: unknown = manifest[section];
  if (
    !entries ||
    typeof entries !== "object" ||
    !(OMP_RUNTIME_PACKAGE in entries)
  ) {
    return undefined;
  }
  return entries[OMP_RUNTIME_PACKAGE];
}

// Planned Policy v2 shape (Slice 2). The peer range decides installability;
// the exact development pin decides the build/acceptance floor.
const policyV2 = {
  schemaVersion: 2,
  peerRange: ">=17.3.5 <18",
  developmentRuntimeVersion: "17.3.5",
  pluginPackage: "@kunolu/omp-sbtd",
  commands: ["help", "status", "report", "onboard plan"],
} as const;

type ProfileAssessment = Readonly<{
  outcome:
    | "passed"
    | "passed-with-diagnostics"
    | "failed"
    | "blocked"
    | "not-run";
  provenanceTrusted: boolean;
}>;

const passedTrusted: ProfileAssessment = {
  outcome: "passed",
  provenanceTrusted: true,
};

// ---------------------------------------------------------------------------
// Slice 6 ledger contract fixtures. All identities are deliberately
// synthetic (0.1.0-rc.99) so no scenario promotes the unpublished rc.13
// candidate envelope into the published target catalog.
// ---------------------------------------------------------------------------

const ledgerSha = (label: string): string =>
  createHash("sha256").update(label).digest("hex");
const ledgerSri = (label: string): string =>
  `sha512-${createHash("sha512").update(label).digest("base64")}`;

// Content-addressed in-memory repository store: ledger entries register
// their attestation bundle and profile evidence bytes here; the public
// derivation fails closed if any referenced file is absent or mismatched.
const contractFiles = new Map<string, Uint8Array>();
const contractReader = {
  readBytes: async (locator: string): Promise<Uint8Array> => {
    const bytes = contractFiles.get(locator);
    if (bytes === undefined)
      throw new Error(`ENOENT: no such evidence file ${locator}`);
    return bytes;
  },
};

function storeContractContent(content: string): {
  locator: string;
  sha256: string;
} {
  const bytes = Buffer.from(content, "utf8");
  const digest = createHash("sha256").update(bytes).digest("hex");
  const locator = `packages/omp-sbtd/validation/p0/evidence/${digest}.json`;
  contractFiles.set(locator, bytes);
  return { locator, sha256: digest };
}

function contractBundle(subjects: Readonly<Record<string, string>>): {
  locator: string;
  sha256: string;
} {
  const statement = {
    _type: "https://in-toto.io/Statement/v1",
    subject: Object.entries(subjects).map(([name, digest]) => ({
      name,
      digest: { sha256: digest },
    })),
    predicateType: "https://slsa.dev/provenance/v1",
    predicate: {},
  };
  // Fixture bundle: real Sigstore cryptographic verification is CI-side
  // (gh attestation verify, HITL); tests only prove content binding.
  const bundle = {
    mediaType: "application/vnd.dev.sigstore.bundle.v0.3+json",
    verificationMaterial: {},
    dsseEnvelope: {
      payloadType: "application/vnd.in-toto+json",
      payload: Buffer.from(JSON.stringify(statement), "utf8").toString(
        "base64",
      ),
      signatures: [{ sig: "contract-fixture-signature" }],
    },
  };
  return storeContractContent(JSON.stringify(bundle));
}

const contractTrustPolicy = {
  schemaVersion: 1,
  kind: "compatibility-trust-policy",
  attestation: {
    format: "github-artifact-attestation-v1",
    issuer: "https://token.actions.githubusercontent.com",
    repository: "KunoLu/sbtd-plugins",
    workflowRefs: [
      ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
    ],
    sourceRefs: ["refs/heads/main"],
    events: ["workflow_dispatch", "schedule"],
    // Matches the shipped validation/p0/compatibility-trust-policy.v1.json:
    // the command set and Host Event scenario set are required attestation
    // subjects alongside the tarball, manifest and OMP artifact.
    requiredSubjects: [
      "pluginTarball",
      "pluginManifest",
      "ompArtifact",
      "commandSet",
      "hostEventScenarioSet",
    ],
  },
  statusPublisher: {
    context: "omp-compatibility-ledger-validate",
    environment: "omp-compatibility-ledger-status",
    credential: "dedicated Status GitHub App private key (HITL, not in repo)",
  },
} as const;

const contractTarget = {
  pluginVersion: "0.1.0-rc.99",
  pluginTarballSha256: ledgerSha("contract-tarball"),
  packageIntegrity: ledgerSri("contract-tarball"),
  pluginManifestSha256: ledgerSha("contract-manifest"),
  pluginPeerRange: ">=17.3.5 <18",
} as const;
const contractRegistryProof = {
  registryVersion: contractTarget.pluginVersion,
  registryDistIntegrity: contractTarget.packageIntegrity,
} as const;
const contractEmptyTargets: CompatibilityTargetsDocument = {
  schemaVersion: 1,
  kind: "compatibility-targets",
  targets: [],
};
const contractEmptyLedger: CompatibilityLedgerDocument = {
  schemaVersion: 1,
  kind: "compatibility-ledger",
  entries: [],
};
const contractStateQuery = {
  pluginTarballSha256: contractTarget.pluginTarballSha256,
  ompVersion: "17.3.5",
} as const;

function contractProfile(profile: string, outcome: string) {
  const evidence = storeContractContent(`contract-evidence-${profile}`);
  return {
    profile,
    outcome,
    evidenceTrust: "verified",
    evidenceSha256: evidence.sha256,
    evidenceLocator: evidence.locator,
  };
}

function contractAssessment(
  overrides: Readonly<Record<string, unknown>> = {},
): LedgerAssessmentEntry {
  const profiles = {
    runtimeCapabilityProbe: contractProfile(
      "omp-runtime-capabilities-v1",
      "passed",
    ),
    commandSurface: contractProfile("omp-command-surface-v1", "passed"),
    hostEventSurface: contractProfile("omp-host-events-v1", "passed"),
  };
  const subjectDigests = {
    pluginTarball: contractTarget.pluginTarballSha256,
    pluginManifest: contractTarget.pluginManifestSha256,
    ompArtifact: ledgerSha("contract-omp-artifact"),
    commandSet: ledgerSha("contract-command-set"),
    hostEventScenarioSet: ledgerSha("contract-scenario-set"),
    runtimeCapabilityProbe: profiles.runtimeCapabilityProbe.evidenceSha256,
    commandSurface: profiles.commandSurface.evidenceSha256,
    hostEventSurface: profiles.hostEventSurface.evidenceSha256,
  };
  const bundle = contractBundle(subjectDigests);
  const draft = {
    schemaVersion: 1,
    entryType: "assessment",
    attemptId: "gha:8123456789:1",
    pluginPackage: "@kunolu/omp-sbtd",
    pluginVersion: contractTarget.pluginVersion,
    pluginTarballSha256: contractTarget.pluginTarballSha256,
    pluginPackageIntegrity: contractTarget.packageIntegrity,
    pluginManifestSha256: contractTarget.pluginManifestSha256,
    pluginPeerRange: contractTarget.pluginPeerRange,
    assessmentTargetSource: "published-catalog",
    ompVersion: "17.3.5",
    ompRegistryIntegrity: ledgerSri("contract-omp-registry"),
    loadedRuntimeVersion: "17.3.5",
    loadedRuntimeArtifactSha256: ledgerSha("contract-omp-artifact"),
    contractProfile: "omp-extension-v1",
    commandSetSha256: ledgerSha("contract-command-set"),
    hostEventScenarioSetSha256: ledgerSha("contract-scenario-set"),
    previousEntrySha256: null,
    profiles,
    provenance: {
      format: "github-artifact-attestation-v1",
      issuer: "https://token.actions.githubusercontent.com",
      repository: "KunoLu/sbtd-plugins",
      workflowRef:
        ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
      eventName: "workflow_dispatch",
      runId: "8123456789",
      sourceRef: "refs/heads/main",
      sourceRevision: ledgerSha("contract-revision").slice(0, 40),
      attestationBundleSha256: bundle.sha256,
      attestationBundleLocator: bundle.locator,
      subjectDigests,
    },
    overallOutcome: "certified",
    ...overrides,
  };
  return {
    ...draft,
    entrySha256: ledgerEntryContentSha256(draft),
  } as LedgerAssessmentEntry;
}

function contractRevocation(
  supersedesEntrySha256: string,
): LedgerRevocationEntry {
  const subjectDigests = {
    pluginTarball: contractTarget.pluginTarballSha256,
    pluginManifest: contractTarget.pluginManifestSha256,
    ompArtifact: ledgerSha("contract-omp-artifact"),
    commandSet: ledgerSha("contract-command-set"),
    hostEventScenarioSet: ledgerSha("contract-scenario-set"),
  };
  const bundle = contractBundle(subjectDigests);
  const draft = {
    schemaVersion: 1,
    entryType: "revocation",
    pluginTarballSha256: contractTarget.pluginTarballSha256,
    ompVersion: "17.3.5",
    contractProfile: "omp-extension-v1",
    supersedesEntrySha256,
    reasonCode: "HOST_REGRESSION_CONFIRMED",
    effectiveAt: "2026-08-25T00:00:00Z",
    provenance: {
      format: "github-artifact-attestation-v1",
      issuer: "https://token.actions.githubusercontent.com",
      repository: "KunoLu/sbtd-plugins",
      workflowRef:
        ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
      eventName: "workflow_dispatch",
      runId: "8123456789",
      sourceRef: "refs/heads/main",
      sourceRevision: ledgerSha("contract-revision").slice(0, 40),
      attestationBundleSha256: bundle.sha256,
      attestationBundleLocator: bundle.locator,
      subjectDigests,
    },
  };
  return {
    ...draft,
    entrySha256: ledgerEntryContentSha256(draft),
  } as LedgerRevocationEntry;
}

function contractPublishedTargets(): CompatibilityTargetsDocument {
  const result = appendCompatibilityTarget(
    contractEmptyTargets,
    contractTarget,
    contractRegistryProof,
  );
  expect(result.outcome).toBe("appended");
  return result.targets;
}

function deepFreeze(value: unknown): void {
  if (value !== null && typeof value === "object") {
    for (const nested of Object.values(value)) deepFreeze(nested);
    Object.freeze(value);
  }
}

// Recomputes the canonical entry digest after a deliberate fixture
// mutation, so negatives reach the semantic identity/subject-binding checks
// instead of failing the entrySha256 gate first.
function rehashContractEntry(
  draft: Readonly<Record<string, unknown>>,
): LedgerAssessmentEntry {
  return {
    ...draft,
    entrySha256: ledgerEntryContentSha256(draft),
  } as LedgerAssessmentEntry;
}

// Rebuilds an assessment with a mutated subject-digest universe and a
// freshly stored content-addressed bundle over exactly those subjects, so
// subject negatives isolate the trust/binding checks: the committed bundle
// content itself still verifies.
function rebindContractAssessment(
  entry: LedgerAssessmentEntry,
  subjectDigests: Readonly<Record<string, string>>,
): LedgerAssessmentEntry {
  const bundle = contractBundle(subjectDigests);
  return rehashContractEntry({
    ...entry,
    provenance: {
      ...entry.provenance,
      attestationBundleSha256: bundle.sha256,
      attestationBundleLocator: bundle.locator,
      subjectDigests,
    },
  });
}

function deriveOverallState(input: Readonly<Record<string, unknown>>): string {
  const derive = validator.deriveCompatibilityOverallState;
  expect(
    typeof derive,
    "Slice 2/6 must export deriveCompatibilityOverallState from " +
      "scripts/p0/release-validator.ts implementing the fixed priority " +
      "out-of-range → revoked → incompatible → certified → " +
      "partially-verified → eligible; the current validator only models " +
      "one exact current Runtime and has no independent certification " +
      "state derivation.",
  ).toBe("function");
  // Unchecked cast: presence asserted immediately above; the call shape is
  // the Slice 2/6 contract documented in the file header.
  const deriveFn = derive as (
    value: Readonly<Record<string, unknown>>,
  ) => string;
  return deriveFn(input);
}

describe("Feature: P0 一致性研究与不可变证据 — publication/certification contract", () => {
  it("Scenario: peer range 与精确 dev pin 分离", () => {
    // Old assumption replaced by the Slice 2 cutover: the compatibility
    // manifest had to name exactly one exact currentRuntimeVersion (v1
    // strict schema), so the range + pin policy shape was rejected with
    // CURRENT_RUNTIME_COMPATIBILITY_INVALID.
    const validate = validator.validateCompatibilityManifest;
    expect(typeof validate).toBe("function");
    // Unchecked cast: presence asserted above; the call shape is the
    // Slice 2 Policy v2 contract documented in the file header.
    const validatePolicy = validate as (
      input: unknown,
      expectedDevelopmentRuntime?: string,
    ) => { peerRange: string; developmentRuntimeVersion: string };
    const policy = validatePolicy(policyV2, "17.3.5");
    expect(policy.peerRange).toBe(">=17.3.5 <18");
    expect(policy.developmentRuntimeVersion).toBe("17.3.5");
  });

  it("Scenario: 精确 dev pin 必须位于 peer range 内", () => {
    // Old assumption replaced by the Slice 2 cutover: there was no
    // range-membership semantics, so an out-of-range development pin failed
    // only as a generic strict schema error
    // (CURRENT_RUNTIME_COMPATIBILITY_INVALID), not as the required
    // fail-closed range violation.
    const validate = validator.validateCompatibilityManifest;
    expect(typeof validate).toBe("function");
    // Unchecked cast: presence asserted above; same Slice 2 contract.
    const validatePolicy = validate as (
      input: unknown,
      expectedDevelopmentRuntime?: string,
    ) => unknown;
    try {
      validatePolicy(
        { ...policyV2, developmentRuntimeVersion: "18.1.0" },
        "17.3.5",
      );
      throw new Error("Expected an out-of-range dev pin to fail closed.");
    } catch (error) {
      expect(error).toMatchObject({
        code: "COMPATIBILITY_DEV_PIN_OUT_OF_RANGE",
      });
    }
  });

  it("Scenario: OMP 18 被 tarball-bound peer range 拒绝", async () => {
    // Old assumption replaced by the Slice 2 cutover: runtime identity was
    // exact equality with one declared current version
    // (CURRENT_RUNTIME_MISMATCH); the new contract rejects out-of-range
    // runtimes from the tarball-bound peer range, and never runs profiles
    // for them.
    //
    // The rejection identity is the packed candidate itself: the peer range
    // in the packed package.json and the packaged Policy v2 file
    // (validation/p0/compatibility.v2.json is in the package files
    // whitelist). The in-memory policyV2 constant must not decide this
    // scenario — a packed peer range that admits 18, or a tarball that
    // omits the packaged policy, fails this test.
    const packageRoot = await packCurrentCandidate();
    const [packedPackageText, sourcePackageText, packedPolicyText] =
      await Promise.all([
        readFile(join(packageRoot, "package.json"), "utf8"),
        readFile(join(pluginRoot, "package.json"), "utf8"),
        // ENOENT here is the intended failure when the packed tarball omits
        // the packaged policy.
        readFile(
          join(packageRoot, "validation", "p0", "compatibility.v2.json"),
          "utf8",
        ),
      ]);
    const packedPackage: unknown = JSON.parse(packedPackageText);
    const sourcePackage: unknown = JSON.parse(sourcePackageText);
    const packedPolicy: unknown = JSON.parse(packedPolicyText);
    const packedPeerRange = dependencySpec(packedPackage, "peerDependencies");
    expect(packedPeerRange).toBe(
      dependencySpec(sourcePackage, "peerDependencies"),
    );

    const validate = validator.validateCompatibilityManifest;
    expect(typeof validate).toBe("function");
    // Unchecked cast: presence asserted above; the call shape is the
    // Slice 2 Policy v2 contract documented in the file header.
    const validatePolicy = validate as (
      input: unknown,
      expectedDevelopmentRuntime?: string,
    ) => { peerRange: string; developmentRuntimeVersion: string };
    const packedPolicyValidated = validatePolicy(packedPolicy);
    // The packaged policy peer range is the tarball-bound identity and must
    // equal the packed package.json peer range.
    expect(packedPolicyValidated.peerRange).toBe(packedPeerRange);

    const assertInRange = validator.assertRuntimeWithinPeerRange;
    expect(
      typeof assertInRange,
      "Slice 2 must export assertRuntimeWithinPeerRange from " +
        "scripts/p0/release-validator.ts: range membership derived from " +
        "the tarball-bound peer range, not exact-current equality.",
    ).toBe("function");
    // Unchecked cast: presence asserted immediately above; the call shape
    // is the Slice 2 contract documented in the file header.
    const check = assertInRange as (policy: unknown, runtime: string) => void;
    // The exact development pin is in range; OMP 18.0.0 is rejected.
    expect(() => check(packedPolicy, "17.3.5")).not.toThrow();
    try {
      check(packedPolicy, "18.0.0");
      throw new Error("Expected OMP 18 to be rejected as out-of-range.");
    } catch (error) {
      expect(error).toMatchObject({
        code: "COMPATIBILITY_RUNTIME_OUT_OF_RANGE",
      });
    }
  }, 120_000);

  it("Scenario: overall state 按固定优先级唯一派生", () => {
    // Old assumption replaced by the Slice 2 cutover: certification state
    // was conflated with the single exact-current compatibility check; no
    // fixed-priority derivation existed.
    expect(
      deriveOverallState({
        runtimeInRange: false,
        revoked: true,
        profiles: {
          runtimeCapability: passedTrusted,
          commandSurface: passedTrusted,
          hostEventSurface: passedTrusted,
        },
      }),
    ).toBe("out-of-range");
    expect(
      deriveOverallState({
        runtimeInRange: true,
        revoked: true,
        profiles: {
          runtimeCapability: passedTrusted,
          commandSurface: passedTrusted,
          hostEventSurface: passedTrusted,
        },
      }),
    ).toBe("revoked");
    expect(
      deriveOverallState({
        runtimeInRange: true,
        profiles: {
          runtimeCapability: passedTrusted,
          commandSurface: passedTrusted,
          hostEventSurface: {
            outcome: "failed",
            provenanceTrusted: true,
          },
        },
      }),
    ).toBe("incompatible");
  });

  it("Scenario: 三个受信通过 profile 的 in-range 未撤销 target 派生 certified", () => {
    // The unique positive certified assertion: in-range, not revoked, and
    // all three evidence profiles passed with trusted provenance derive
    // exactly certified (the certified rung of the fixed priority).
    expect(
      deriveOverallState({
        runtimeInRange: true,
        revoked: false,
        profiles: {
          runtimeCapability: passedTrusted,
          commandSurface: passedTrusted,
          hostEventSurface: passedTrusted,
        },
      }),
    ).toBe("certified");
  });

  it("Scenario: 只有部分 profile 通过时派生 partially-verified", () => {
    expect(
      deriveOverallState({
        runtimeInRange: true,
        profiles: {
          runtimeCapability: passedTrusted,
          commandSurface: passedTrusted,
          hostEventSurface: {
            outcome: "blocked",
            provenanceTrusted: true,
          },
        },
      }),
    ).toBe("partially-verified");
  });

  it("Scenario: Host Event Surface 未通过时四命令结果不能派生 certified", () => {
    // A passed four-command acceptance is only the Command Surface profile;
    // without a passed Host Event Surface it must never derive certified.
    const state = deriveOverallState({
      runtimeInRange: true,
      profiles: {
        runtimeCapability: passedTrusted,
        commandSurface: passedTrusted,
        hostEventSurface: { outcome: "not-run", provenanceTrusted: true },
      },
    });
    expect(state).not.toBe("certified");
    expect(state).toBe("partially-verified");
  });

  it("Scenario: 未受信 provenance 不能派生 certified", () => {
    // Three green profiles with unverifiable provenance derive at most
    // partially-verified (plan §12.4), never certified.
    const state = deriveOverallState({
      runtimeInRange: true,
      profiles: {
        runtimeCapability: { outcome: "passed", provenanceTrusted: false },
        commandSurface: { outcome: "passed", provenanceTrusted: false },
        hostEventSurface: { outcome: "passed", provenanceTrusted: false },
      },
    });
    expect(state).not.toBe("certified");
    expect(state).toBe("partially-verified");
  });

  it("Scenario: 已发布的 in-range target 没有受信 profile 通过时从 eligible 开始", () => {
    expect(deriveOverallState({ runtimeInRange: true, profiles: {} })).toBe(
      "eligible",
    );
  });

  it("Scenario: 已发布 rc.12 的既有四命令结果不被自动提升为 certified", () => {
    // The historical rc.12 four-command result is a local Command Surface
    // baseline without trusted CI provenance; it must never be promoted to
    // certified. Implemented unique rule (Slice 2): a recorded pass without
    // trusted provenance still counts as a partial pass, so the one exact
    // derived state is partially-verified.
    const state = deriveOverallState({
      runtimeInRange: true,
      profiles: {
        commandSurface: { outcome: "passed", provenanceTrusted: false },
      },
    });
    expect(state).toBe("partially-verified");
  });

  it("Scenario: 缺失或调换 commandSet/hostEventScenarioSet subject 的认证不得入帐", async () => {
    // The trust policy requires the command set and Host Event scenario
    // set attestation subjects (matching the shipped
    // validation/p0/compatibility-trust-policy.v1.json). An attestation
    // that omits either subject, or swaps their digests, is never trusted:
    // the append fails closed and the published target's public state stays
    // eligible, never certified.
    const shippedTrustPolicy = JSON.parse(
      await readFile(
        join(pluginRoot, "validation/p0/compatibility-trust-policy.v1.json"),
        "utf8",
      ),
    ) as { attestation: { requiredSubjects: readonly string[] } };
    expect(contractTrustPolicy.attestation.requiredSubjects).toEqual(
      shippedTrustPolicy.attestation.requiredSubjects,
    );

    const targets = contractPublishedTargets();

    const missingSubject = (
      dropped: "commandSet" | "hostEventScenarioSet",
    ): LedgerAssessmentEntry => {
      const entry = contractAssessment();
      // Unchecked cast: the fixture subject universe is fully populated at
      // runtime; the cast only widens the optional profile subjects so
      // `delete` can remove exactly the named required subject.
      const subjects = {
        ...entry.provenance.subjectDigests,
      } as Record<string, string>;
      delete subjects[dropped];
      return rebindContractAssessment(entry, subjects);
    };
    const swappedSubjects = (): LedgerAssessmentEntry => {
      const entry = contractAssessment();
      // Unchecked cast: same fully-populated fixture universe; the swap
      // exchanges the two required digests between their subject names.
      const subjects = {
        ...entry.provenance.subjectDigests,
        commandSet: entry.provenance.subjectDigests.hostEventScenarioSet,
        hostEventScenarioSet: entry.provenance.subjectDigests.commandSet,
      } as Record<string, string>;
      return rebindContractAssessment(entry, subjects);
    };

    const cases: ReadonlyArray<{
      readonly name: string;
      readonly broken: LedgerAssessmentEntry;
      readonly code: string;
    }> = [
      {
        name: "missing commandSet subject",
        broken: missingSubject("commandSet"),
        code: "COMPATIBILITY_LEDGER_INVALID",
      },
      {
        name: "missing hostEventScenarioSet subject",
        broken: missingSubject("hostEventScenarioSet"),
        code: "COMPATIBILITY_LEDGER_INVALID",
      },
      {
        name: "swapped commandSet/hostEventScenarioSet subjects",
        broken: swappedSubjects(),
        code: "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
      },
    ];
    for (const { name, broken, code } of cases) {
      await expect(
        appendLedgerAssessment(
          contractEmptyLedger,
          targets,
          contractTrustPolicy,
          broken,
          contractReader,
        ),
        name,
      ).rejects.toMatchObject({ code });
      expect(
        await derivePublishedCompatibilityState(
          targets,
          contractEmptyLedger,
          contractTrustPolicy,
          contractStateQuery,
          contractReader,
        ),
        name,
      ).toBe("eligible");
    }
  });

  it("Scenario: ledger entry 绑定精确身份与证据", async () => {
    // Slice 6: a ledger assessment binds the exact Plugin version, package
    // integrity, tarball SHA-256, manifest SHA-256, tarball-bound peer
    // range, the actual loaded OMP artifact and the content-addressed
    // evidence set; an entry omitting or mismatching any binding is
    // rejected (table-driven below) and the existing public state does not
    // change.
    const targets = contractPublishedTargets();
    const entry = contractAssessment();
    const appended = await appendLedgerAssessment(
      contractEmptyLedger,
      targets,
      contractTrustPolicy,
      entry,
      contractReader,
    );
    expect(appended.outcome).toBe("appended");
    expect(
      await derivePublishedCompatibilityState(
        targets,
        appended.ledger,
        contractTrustPolicy,
        {
          pluginTarballSha256: contractTarget.pluginTarballSha256,
          ompVersion: "17.3.5",
        },
        contractReader,
      ),
    ).toBe("certified");

    // Every claimed binding is broken in turn — by omission (malformed
    // entry) and by mismatch (identity or subject binding) — with the
    // canonical digest recomputed so each case reaches the semantic check
    // it targets. Each broken entry is rejected and the published target's
    // public state on the empty ledger stays eligible.
    const bindings: ReadonlyArray<{
      readonly name: string;
      readonly code: string;
      readonly breakBinding: (
        entry: LedgerAssessmentEntry,
      ) => LedgerAssessmentEntry;
    }> = [
      {
        name: "pluginVersion omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { pluginVersion: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "pluginVersion mismatches the published target",
        code: "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({ ...entry, pluginVersion: "0.1.0-rc.98" }),
      },
      {
        name: "pluginTarballSha256 omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { pluginTarballSha256: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "pluginTarballSha256 mismatches the published target",
        code: "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            pluginTarballSha256: ledgerSha("contract-tarball-alt"),
          }),
      },
      {
        name: "pluginManifestSha256 omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { pluginManifestSha256: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "pluginManifestSha256 mismatches the published target",
        code: "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            pluginManifestSha256: ledgerSha("contract-manifest-alt"),
          }),
      },
      {
        name: "pluginPackageIntegrity omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { pluginPackageIntegrity: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "pluginPackageIntegrity mismatches the published target",
        code: "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            pluginPackageIntegrity: ledgerSri("contract-tarball-alt"),
          }),
      },
      {
        name: "pluginPeerRange omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { pluginPeerRange: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "pluginPeerRange mismatches the published target",
        code: "COMPATIBILITY_LEDGER_IDENTITY_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({ ...entry, pluginPeerRange: ">=17 <19" }),
      },
      {
        name: "commandSetSha256 omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { commandSetSha256: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "commandSetSha256 mismatches subjectDigests.commandSet",
        code: "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            commandSetSha256: ledgerSha("contract-command-set-alt"),
          }),
      },
      {
        name: "hostEventScenarioSetSha256 omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { hostEventScenarioSetSha256: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "hostEventScenarioSetSha256 mismatches subjectDigests.hostEventScenarioSet",
        code: "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            hostEventScenarioSetSha256: ledgerSha("contract-scenario-set-alt"),
          }),
      },
      {
        name: "profile evidenceSha256 omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            profiles: {
              ...entry.profiles,
              commandSurface: {
                ...entry.profiles.commandSurface,
                evidenceSha256: undefined,
              },
            },
          }),
      },
      {
        name: "profile evidenceSha256 mismatches its subject",
        code: "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            profiles: {
              ...entry.profiles,
              commandSurface: {
                ...entry.profiles.commandSurface,
                evidenceSha256: ledgerSha("contract-evidence-alt"),
              },
            },
          }),
      },
      {
        name: "loadedRuntimeArtifactSha256 omitted",
        code: "COMPATIBILITY_LEDGER_INVALID",
        breakBinding: (entry) => {
          const { loadedRuntimeArtifactSha256: _omitted, ...rest } = entry;
          return rehashContractEntry(rest);
        },
      },
      {
        name: "loadedRuntimeArtifactSha256 mismatches subjectDigests.ompArtifact",
        code: "COMPATIBILITY_LEDGER_SUBJECT_MISMATCH",
        breakBinding: (entry) =>
          rehashContractEntry({
            ...entry,
            loadedRuntimeArtifactSha256: ledgerSha("contract-omp-artifact-alt"),
          }),
      },
    ];
    for (const { name, code, breakBinding } of bindings) {
      await expect(
        appendLedgerAssessment(
          contractEmptyLedger,
          targets,
          contractTrustPolicy,
          breakBinding(contractAssessment()),
          contractReader,
        ),
        name,
      ).rejects.toMatchObject({ code });
      expect(
        await derivePublishedCompatibilityState(
          targets,
          contractEmptyLedger,
          contractTrustPolicy,
          contractStateQuery,
          contractReader,
        ),
        name,
      ).toBe("eligible");
    }
  });

  it("Scenario: append-only revocation 撤销认证但保留历史", async () => {
    // Slice 6: a trusted revocation supersedes the latest assessment, the
    // current state derives revoked, history stays auditable, and restoring
    // certified requires a fresh complete successor assessment.
    const targets = contractPublishedTargets();
    const certified = await appendLedgerAssessment(
      contractEmptyLedger,
      targets,
      contractTrustPolicy,
      contractAssessment(),
      contractReader,
    );
    const revocation = contractRevocation(
      certified.ledger.entries[0]?.entrySha256 ?? "",
    );
    const revoked = await appendLedgerRevocation(
      certified.ledger,
      contractTrustPolicy,
      revocation,
      contractReader,
    );
    expect(revoked.ledger.entries).toHaveLength(2);
    expect(revoked.ledger.entries[0]?.entryType).toBe("assessment");
    expect(
      await derivePublishedCompatibilityState(
        targets,
        revoked.ledger,
        contractTrustPolicy,
        {
          pluginTarballSha256: contractTarget.pluginTarballSha256,
          ompVersion: "17.3.5",
        },
        contractReader,
      ),
    ).toBe("revoked");
    const recertified = await appendLedgerAssessment(
      revoked.ledger,
      targets,
      contractTrustPolicy,
      contractAssessment({
        attemptId: "gha:8123456789:3",
        previousEntrySha256: revocation.entrySha256,
      }),
      contractReader,
    );
    expect(recertified.ledger.entries).toHaveLength(3);
    expect(
      await derivePublishedCompatibilityState(
        targets,
        recertified.ledger,
        contractTrustPolicy,
        {
          pluginTarballSha256: contractTarget.pluginTarballSha256,
          ompVersion: "17.3.5",
        },
        contractReader,
      ),
    ).toBe("certified");
  });

  it("Scenario: ledger 更新不得触发 pack、publish 或 dist-tag 变更", async () => {
    // Slice 6: the ledger surface is pure data — parsed documents in, new
    // documents out; its only I/O is reading evidence bytes through the
    // injected reader, so no pack/publish/dist-tag side-effect channel
    // exists in this module at all. That is a structural property proven
    // here with deep-frozen inputs (ESM strict mode throws on any in-place
    // write) and fresh output documents — no process or Registry
    // publication boundary is observed.
    const targets = contractPublishedTargets();
    const frozenTargets = structuredClone(targets);
    const frozenEmptyLedger = structuredClone(contractEmptyLedger);
    const frozenTrustPolicy = structuredClone(contractTrustPolicy);
    deepFreeze(frozenTargets);
    deepFreeze(frozenEmptyLedger);
    deepFreeze(frozenTrustPolicy);
    const identityBefore = JSON.stringify(frozenTargets);

    // The freeze is real: any in-place write to an input document throws.
    expect(() => {
      (frozenTargets.targets as unknown[]).push({});
    }).toThrowError(TypeError);
    expect(() => {
      (frozenEmptyLedger.entries as unknown[]).push({});
    }).toThrowError(TypeError);

    // Assessment over frozen documents: inputs untouched, output is a
    // fresh document.
    const assessment = contractAssessment();
    deepFreeze(assessment);
    const appended = await appendLedgerAssessment(
      frozenEmptyLedger,
      frozenTargets,
      frozenTrustPolicy,
      assessment,
      contractReader,
    );
    expect(appended.ledger).not.toBe(frozenEmptyLedger);
    expect(appended.ledger.entries).not.toBe(frozenEmptyLedger.entries);
    expect(appended.ledger.entries).toHaveLength(1);
    expect(frozenEmptyLedger.entries).toHaveLength(0);

    // Revocation over frozen documents.
    const frozenCertifiedLedger = structuredClone(appended.ledger);
    deepFreeze(frozenCertifiedLedger);
    const revocation = contractRevocation(assessment.entrySha256);
    deepFreeze(revocation);
    const revoked = await appendLedgerRevocation(
      frozenCertifiedLedger,
      frozenTrustPolicy,
      revocation,
      contractReader,
    );
    expect(revoked.ledger).not.toBe(frozenCertifiedLedger);
    expect(revoked.ledger.entries).toHaveLength(2);
    expect(frozenCertifiedLedger.entries).toHaveLength(1);

    // Recertification over frozen documents.
    const frozenRevokedLedger = structuredClone(revoked.ledger);
    deepFreeze(frozenRevokedLedger);
    const recertification = contractAssessment({
      attemptId: "gha:8123456789:3",
      previousEntrySha256: revocation.entrySha256,
    });
    deepFreeze(recertification);
    const recertified = await appendLedgerAssessment(
      frozenRevokedLedger,
      frozenTargets,
      frozenTrustPolicy,
      recertification,
      contractReader,
    );
    expect(recertified.ledger).not.toBe(frozenRevokedLedger);
    expect(recertified.ledger.entries).toHaveLength(3);
    expect(frozenRevokedLedger.entries).toHaveLength(2);

    // The derived matrix is the only projection output; the published
    // target identity stays byte-identical across assessment, revocation
    // and recertification, and no new Plugin version appears.
    const frozenRecertifiedLedger = structuredClone(recertified.ledger);
    deepFreeze(frozenRecertifiedLedger);
    const matrix = await deriveSupportMatrix(
      frozenTargets,
      frozenRecertifiedLedger,
      frozenTrustPolicy,
      contractReader,
    );
    expect(matrix.cells).toHaveLength(1);
    expect(matrix.cells[0]?.state).toBe("certified");
    expect(Object.keys(matrix).sort()).toEqual([
      "cells",
      "generatedFrom",
      "kind",
      "schemaVersion",
    ]);
    expect(JSON.stringify(frozenTargets)).toBe(identityBefore);
    expect(frozenTargets.targets[0]?.pluginVersion).toBe("0.1.0-rc.99");
    expect(frozenTargets.targets[0]?.pluginTarballSha256).toBe(
      contractTarget.pluginTarballSha256,
    );
  });

  it("Scenario: 新 OMP 17.x 认证通过不改变既有 Plugin 身份", async () => {
    // Slice 6: a new in-range OMP 17.x three-profile trusted certification
    // derives certified for the (target, Runtime) pair while the published
    // Plugin version and tarball SHA-256 stay byte-identical and no new
    // Plugin version appears.
    const targets = contractPublishedTargets();
    const identityBefore = JSON.stringify(targets);
    const first = await appendLedgerAssessment(
      contractEmptyLedger,
      targets,
      contractTrustPolicy,
      contractAssessment(),
      contractReader,
    );
    const second = await appendLedgerAssessment(
      first.ledger,
      targets,
      contractTrustPolicy,
      contractAssessment({
        attemptId: "gha:8123456789:2",
        ompVersion: "17.4.0",
        loadedRuntimeVersion: "17.4.0",
      }),
      contractReader,
    );
    const matrix = await deriveSupportMatrix(
      targets,
      second.ledger,
      contractTrustPolicy,
      contractReader,
    );
    expect(
      matrix.cells.find((cell) => cell.ompVersion === "17.4.0")?.state,
    ).toBe("certified");
    expect(JSON.stringify(targets)).toBe(identityBefore);
    expect(targets.targets).toHaveLength(1);
  });
});
