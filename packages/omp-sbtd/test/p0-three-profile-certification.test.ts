// Slice 7 focused tests for the three-profile certification producer.
//
// Trace: docs/assets/omp-plugin-compatibility-decoupling-plan.md §7, §12.4
// and the Slice 7 assignment (local://slice-7-implement.md):
// - empty/unavailable matrix is blocked, never a pass;
// - rc.12 admission is byte-verified against the Registry identity recorded
//   at M5 publication; rc.13 is recorded from cloud §4 HITL next (b0e1f133…);
//   unknown versions can never be admitted;

// - local-observation bundles never enter the public ledger;
// - the caller cannot force a certified outcome; outcomes are derived.
//
// Mock Strategy: Registry fetches are injected fixtures; the evidence store
// is in-memory; attestation bundles are fixture stand-ins (cryptographic
// Sigstore verification is CI-side via gh attestation verify and out of
// scope here). Fixture identities are synthetic (0.1.0-rc.99) so no test
// promotes the unpublished rc.13 candidate.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import type {
  CompatibilityEvidenceReader,
  CompatibilityLedgerDocument,
  CompatibilityTargetsDocument,
  CompatibilityTrustPolicy,
} from "../scripts/p0/compatibility-ledger.ts";
import {
  appendCompatibilityTarget,
  appendLedgerAssessment,
  ledgerAssessmentEntrySchema,
  planCompatibilityMatrixRun,
  reportCompatibilityMatrixRun,
} from "../scripts/p0/compatibility-ledger.ts";
import {
  parseCapabilityProbeLog,
  scoreCapabilityProbe,
  scoreCommandSurfaceRecord,
} from "../scripts/p0/host-event/run-command-surface-cell.ts";
import { P0ValidationError } from "../scripts/p0/release-validator.ts";
import {
  admitPublishedTarget,
  assertCellHostIdentity,
  buildCellAssessmentDraft,
  CERTIFICATION_EVIDENCE_KIND,
  certificationCellPlanSchema,
  commandSetSubjectDocument,
  extractTarballMemberBytes,
  finalizeCellAssessment,
  hostEventCertificationBundleFromLiveCell,
  hostEventScenarioSetSubjectDocument,
  normalizeCertificationWorkflowRef,
  parseNpmViewJson,
  planCertificationRun,
  RECORDED_RC12_TARGET_IDENTITY,
  RECORDED_RC13_TARGET_IDENTITY,
  recordedPublishedTargetIdentity,
  serializeCertificationEvidence,
  verifyRegistryTarballAdmission,
} from "../scripts/p0/three-profile-certification.ts";

const pluginRoot = fileURLToPath(new URL("..", import.meta.url));
const dataRoot = join(pluginRoot, "validation", "p0");
const committedTrustPolicy: CompatibilityTrustPolicy = JSON.parse(
  await readFile(join(dataRoot, "compatibility-trust-policy.v1.json"), "utf8"),
) as CompatibilityTrustPolicy;

const sha = (label: string): string =>
  createHash("sha256").update(label).digest("hex");
const shaBytes = (bytes: Uint8Array): string =>
  createHash("sha256").update(bytes).digest("hex");
const sri = (bytes: Uint8Array): string =>
  `sha512-${createHash("sha512").update(bytes).digest("base64")}`;

// ---------------------------------------------------------------------------
// Minimal ustar fixture (real headers; the admission extractor walks them)
// ---------------------------------------------------------------------------

function ustarHeader(name: string, size: number): Buffer {
  const header = Buffer.alloc(512);
  header.write(name, 0, Math.min(name.length, 100), "utf8");
  header.write("0000644\0", 100, 8, "ascii");
  header.write("0000000\0", 108, 8, "ascii");
  header.write("0000000\0", 116, 8, "ascii");
  header.write(`${size.toString(8).padStart(11, "0")}\0`, 124, 12, "ascii");
  header.write("00000000000\0", 136, 12, "ascii");
  header.write("        ", 148, 8, "ascii");
  header.write("0", 156, 1, "ascii");
  header.write("ustar\0", 257, 6, "ascii");
  header.write("00", 263, 2, "ascii");
  let checksum = 0;
  for (const byte of header) checksum += byte;
  header.write(`${checksum.toString(8).padStart(6, "0")}\0 `, 148, 8, "ascii");
  return header;
}

function tarballWith(manifest: string): Uint8Array {
  const content = Buffer.from(manifest, "utf8");
  const padded = Buffer.alloc(Math.ceil(content.length / 512) * 512);
  content.copy(padded);
  return gzipSync(
    Buffer.concat([
      ustarHeader("package/package.json", content.length),
      padded,
      Buffer.alloc(1024),
    ]),
  );
}

const FIXTURE_MANIFEST = JSON.stringify({
  name: "@kunolu/omp-sbtd",
  version: "0.1.0-rc.99",
  peerDependencies: { "@oh-my-pi/pi-coding-agent": "17.3.5" },
});
const fixtureTarball = tarballWith(FIXTURE_MANIFEST);
const fixtureManifestBytes = Buffer.from(FIXTURE_MANIFEST, "utf8");

const fixtureRecordedIdentity = {
  pluginVersion: "0.1.0-rc.99",
  pluginTarballSha256: shaBytes(fixtureTarball),
  packageIntegrity: sri(fixtureTarball),
  pluginPeerRange: "17.3.5",
} as const;

const fixtureFetch = {
  registryVersion: "0.1.0-rc.99",
  registryDistIntegrity: sri(fixtureTarball),
  registryTarballUrl:
    "https://registry.npmjs.org/@kunolu/omp-sbtd/-/omp-sbtd-0.1.0-rc.99.tgz",
  tarballBytes: fixtureTarball,
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
  throw new Error(`expected ${code} but the action succeeded`);
}

// ---------------------------------------------------------------------------
// Empty / unavailable matrix is blocked, never a pass
// ---------------------------------------------------------------------------

describe("empty or unavailable matrix", () => {
  it("reports blocked with the stable reason for an empty plan", () => {
    const report = reportCompatibilityMatrixRun([], {
      liveHarnessAvailable: true,
    });
    expect(report.status).toBe("blocked");
    expect(report.cells).toEqual([]);
    expect(report.reason).toContain("no-published-targets");
  });

  it("keeps an empty published catalog blocked through the certification plan", () => {
    const planned = planCertificationRun(emptyTargets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.9.2",
    });
    expect(planned.plan).toEqual([]);
    expect(planned.cellsToRun).toEqual([]);
    expect(planned.report.status).toBe("blocked");
    expect(planned.report.reason).toContain("no-published-targets");
  });

  it("plans minimum and latest cells per published target without hardcoding 17.3.5", () => {
    const appended = appendCompatibilityTarget(
      emptyTargets,
      {
        pluginVersion: "0.1.0-rc.99",
        pluginTarballSha256: sha("fixture-rc99-tarball"),
        packageIntegrity: `sha512-${"A".repeat(86)}==`,
        pluginManifestSha256: sha("fixture-rc99-manifest"),
        pluginPeerRange: ">=17.3.5 <18",
      },
      {
        registryVersion: "0.1.0-rc.99",
        registryDistIntegrity: `sha512-${"A".repeat(86)}==`,
      },
    );
    expect(appended.outcome).toBe("appended");
    const planned = planCertificationRun(appended.targets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.9.2",
      newRuntime: "17.9.2",
    });
    expect(planned.report.status).toBe("ready");
    expect(planned.cellsToRun.map((cell) => cell.ompVersion)).toEqual([
      "17.3.5",
      "17.9.2",
    ]);
    for (const cell of planned.cellsToRun) {
      expect(cell.inRange).toBe(true);
      expect(cell.profilesToRun).toHaveLength(3);
    }
    const direct = planCompatibilityMatrixRun(appended.targets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.9.2",
    });
    expect(direct).toHaveLength(2);
  });

  it("keeps an exact 17.3.5 peer in-range only for 17.3.5", () => {
    expect(RECORDED_RC12_TARGET_IDENTITY.pluginPeerRange).toBe("17.3.5");
    const appended = appendCompatibilityTarget(
      emptyTargets,
      {
        pluginVersion: "0.1.0-rc.99",
        pluginTarballSha256: sha("fixture-exact-peer-tarball"),
        packageIntegrity: `sha512-${"C".repeat(86)}==`,
        pluginManifestSha256: sha("fixture-exact-peer-manifest"),
        pluginPeerRange: "17.3.5",
      },
      {
        registryVersion: "0.1.0-rc.99",
        registryDistIntegrity: `sha512-${"C".repeat(86)}==`,
      },
    );
    const planned = planCertificationRun(appended.targets, {
      minimumRuntime: "17.3.5",
      latestInRangeRuntime: "17.9.2",
    });
    expect(planned.report.status).toBe("ready");
    expect(planned.cellsToRun.map((cell) => cell.ompVersion)).toEqual([
      "17.3.5",
    ]);
    const outOfRange = planned.plan.find(
      (cell) => cell.ompVersion === "17.9.2",
    );
    expect(outOfRange?.inRange).toBe(false);
    expect(outOfRange?.profilesToRun).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Registry admission (byte verification)
// ---------------------------------------------------------------------------
describe("Registry admission", () => {
  it("records rc.12 and rc.13 identities and rejects unknown versions", async () => {
    expect(RECORDED_RC12_TARGET_IDENTITY.pluginVersion).toBe("0.1.0-rc.12");
    expect(RECORDED_RC12_TARGET_IDENTITY.pluginPeerRange).toBe("17.3.5");
    expect(recordedPublishedTargetIdentity("0.1.0-rc.12")).toEqual(
      RECORDED_RC12_TARGET_IDENTITY,
    );
    expect(recordedPublishedTargetIdentity("0.1.0-rc.13")).toEqual(
      RECORDED_RC13_TARGET_IDENTITY,
    );
    expect(RECORDED_RC13_TARGET_IDENTITY.pluginTarballSha256).toBe(
      "b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185",
    );
    expect(recordedPublishedTargetIdentity("0.1.0-rc.99")).toBeUndefined();
    await expectErrorCode(
      () =>
        admitPublishedTarget({
          catalog: emptyTargets,
          pluginVersion: "0.1.0-rc.99",
          fetch: async () => fixtureFetch,
        }),
      "COMPATIBILITY_ADMISSION_UNKNOWN_TARGET",
    );
  });

  it("extracts tarball members and returns undefined for absent ones", () => {
    const bytes = extractTarballMemberBytes(
      fixtureTarball,
      "package/package.json",
    );
    expect(bytes).toBeDefined();
    expect(shaBytes(bytes ?? new Uint8Array())).toBe(
      shaBytes(fixtureManifestBytes),
    );
    expect(
      extractTarballMemberBytes(fixtureTarball, "package/missing.js"),
    ).toBeUndefined();
  });

  it("byte-verifies a fetched Registry tarball against the recorded identity", () => {
    const entry = verifyRegistryTarballAdmission(
      fixtureRecordedIdentity,
      fixtureFetch,
    );
    expect(entry.pluginVersion).toBe("0.1.0-rc.99");
    expect(entry.pluginTarballSha256).toBe(
      fixtureRecordedIdentity.pluginTarballSha256,
    );
    expect(entry.pluginManifestSha256).toBe(shaBytes(fixtureManifestBytes));
    expect(entry.pluginPeerRange).toBe("17.3.5");
  });

  it("fails closed when Registry facts drift from the recorded identity", async () => {
    await expectErrorCode(
      () =>
        verifyRegistryTarballAdmission(fixtureRecordedIdentity, {
          ...fixtureFetch,
          registryVersion: "0.1.0-rc.100",
        }),
      "COMPATIBILITY_ADMISSION_MISMATCH",
    );
    await expectErrorCode(
      () =>
        verifyRegistryTarballAdmission(fixtureRecordedIdentity, {
          ...fixtureFetch,
          registryDistIntegrity: sri(Buffer.from("tampered", "utf8")),
        }),
      "COMPATIBILITY_ADMISSION_MISMATCH",
    );
    await expectErrorCode(
      () =>
        verifyRegistryTarballAdmission(fixtureRecordedIdentity, {
          ...fixtureFetch,
          tarballBytes: tarballWith(
            JSON.stringify({
              name: "@kunolu/omp-sbtd",
              version: "0.1.0-rc.99",
              peerDependencies: { "@oh-my-pi/pi-coding-agent": ">=17.3.5 <18" },
            }),
          ),
        }),
      "COMPATIBILITY_ADMISSION_MISMATCH",
    );
    // A tarball without package/package.json still fails closed: the pinned
    // digest check rejects it before manifest extraction ever runs.
    await expectErrorCode(
      () =>
        verifyRegistryTarballAdmission(fixtureRecordedIdentity, {
          ...fixtureFetch,
          tarballBytes: gzipSync(Buffer.alloc(1024)),
        }),
      "COMPATIBILITY_ADMISSION_MISMATCH",
    );
    await expectErrorCode(
      () =>
        extractTarballMemberBytes(
          Buffer.from("not a gzip"),
          "package/package.json",
        ),
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
    );
  });

  it("appends once and no-ops an identical re-admission", async () => {
    const entry = verifyRegistryTarballAdmission(
      fixtureRecordedIdentity,
      fixtureFetch,
    );
    const proof = {
      registryVersion: fixtureFetch.registryVersion,
      registryDistIntegrity: fixtureFetch.registryDistIntegrity,
    };
    const first = appendCompatibilityTarget(emptyTargets, entry, proof);
    expect(first.outcome).toBe("appended");
    const second = appendCompatibilityTarget(first.targets, entry, proof);
    expect(second.outcome).toBe("duplicate-noop");
  });

  it("the trusted workflow admits every committed catalog target, not one hardcoded version", async () => {
    // Run 33063599037 regression guard: prepare admitted only the hardcoded
    // rc.12, so lock-and-cache found no staged tarball for rc.13's digest
    // and exited 1. The admission step must derive its versions from the
    // committed catalog and stage each target's tarball.
    const workflow = await readFile(
      join(
        pluginRoot,
        "..",
        "..",
        ".github",
        "workflows",
        "omp-compatibility-certification.yml",
      ),
      "utf8",
    );
    expect(workflow).not.toMatch(/--plugin-version\s+0\.1\.0/);
    expect(workflow).toContain("compatibility-targets.v1.json");
    expect(workflow).toContain(".targets[].pluginVersion");
  });
});

// ---------------------------------------------------------------------------
// Cell host identity binding
// ---------------------------------------------------------------------------

describe("cell host identity", () => {
  async function fixtureOmpPackage(version: string): Promise<string> {
    const root = await mkdtemp(join(tmpdir(), "omp-cert-fixture-"));
    const pkg = join(root, "node_modules", "@oh-my-pi", "pi-coding-agent");
    await mkdir(join(pkg, "dist"), { recursive: true });
    await writeFile(
      join(pkg, "package.json"),
      JSON.stringify({ name: "@oh-my-pi/pi-coding-agent", version }),
    );
    await writeFile(join(pkg, "dist", "cli.js"), "// fixture entrypoint\n");
    return join(pkg, "dist", "cli.js");
  }

  it("binds the spawned package identity to the cell version", async () => {
    const ompBin = await fixtureOmpPackage("17.9.2");
    const host = assertCellHostIdentity(ompBin, "17.9.2");
    expect(host.packageVersion).toBe("17.9.2");
    expect(host.entrypointSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(host.packageJsonSha256).toMatch(/^[a-f0-9]{64}$/);
    await expectErrorCode(
      () => assertCellHostIdentity(ompBin, "17.3.5"),
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    );
  });

  it("fails closed when the binary is not the package entrypoint", async () => {
    const root = await mkdtemp(join(tmpdir(), "omp-cert-shim-"));
    const shim = join(root, "omp");
    await writeFile(shim, "#!/bin/sh\n");
    await expectErrorCode(
      () => assertCellHostIdentity(shim, "17.3.5"),
      "OMP_PACKAGE_IDENTITY_UNAVAILABLE",
    );
  });
});

// ---------------------------------------------------------------------------
// Evidence bundles and the cell assessment draft
// ---------------------------------------------------------------------------

const TARBALL_SHA = sha("fixture-rc99-tarball");
const MANIFEST_SHA = sha("fixture-rc99-manifest");
const PACKAGE_INTEGRITY = `sha512-${"B".repeat(86)}==`;
const OMP_ENTRYPOINT_SHA = sha("fixture-omp-cli");
const OMP_PACKAGE_JSON_SHA = sha("fixture-omp-package-json");
const ATTEMPT_ID = "gha:8123456789:1";

const draftTarget = {
  pluginVersion: "0.1.0-rc.99",
  pluginTarballSha256: TARBALL_SHA,
  packageIntegrity: PACKAGE_INTEGRITY,
  pluginManifestSha256: MANIFEST_SHA,
  pluginPeerRange: ">=17.3.5 <18",
} as const;

const draftHost = {
  entrypointSha256: OMP_ENTRYPOINT_SHA,
  packageJsonSha256: OMP_PACKAGE_JSON_SHA,
  packageVersion: "17.9.2",
} as const;

const commandSet = commandSetSubjectDocument([
  "help",
  "status",
  "report",
  "onboard plan",
]);
const scenarioSet = hostEventScenarioSetSubjectDocument({
  driverSha256: sha("fixture-driver"),
  observerSha256: sha("fixture-observer"),
  events: ["session_start", "session_end"],
});

function capabilityBundle(overrides: Readonly<Record<string, unknown>> = {}) {
  return {
    schemaVersion: 1,
    profile: "omp-runtime-capabilities-v1",
    evidenceKind: CERTIFICATION_EVIDENCE_KIND,
    runId: ATTEMPT_ID,
    pluginTarballSha256: TARBALL_SHA,
    ompVersion: "17.9.2",
    ompArtifact: {
      entrypointSha256: OMP_ENTRYPOINT_SHA,
      packageJsonSha256: OMP_PACKAGE_JSON_SHA,
    },
    inventoryVersion: "omp-extension-v1",
    capabilities: { registerCommand: "present", on: "present", zod: "present" },
    pluginRegistered: true,
    missingRequired: [],
    missingOptional: ["registerTool"],
    outcome: "passed-with-diagnostics",
    ...overrides,
  } as const;
}

function commandBundle(overrides: Readonly<Record<string, unknown>> = {}) {
  return {
    schemaVersion: 1,
    profile: "omp-command-surface-v1",
    evidenceKind: CERTIFICATION_EVIDENCE_KIND,
    runId: ATTEMPT_ID,
    pluginTarballSha256: TARBALL_SHA,
    ompVersion: "17.9.2",
    ompArtifact: {
      entrypointSha256: OMP_ENTRYPOINT_SHA,
      packageJsonSha256: OMP_PACKAGE_JSON_SHA,
    },
    commandSetSha256: commandSet.sha256,
    commands: [
      {
        command: "help",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("help"),
      },
      {
        command: "status",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("status"),
      },
      {
        command: "report",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("report"),
      },
      {
        command: "onboard plan",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("plan"),
      },
    ],
    outcome: "passed",
    ...overrides,
  } as const;
}

function localHostEventBundle(
  overrides: Readonly<Record<string, unknown>> = {},
) {
  return {
    schemaVersion: 1,
    profile: "omp-host-events-v1",
    evidenceKind: "local-observation",
    runId: "local-run-1",
    pluginTarballSha256: TARBALL_SHA,
    pluginValidatorModuleSha256: sha("fixture-validator-module"),
    ompVersion: "17.9.2",
    ompArtifact: {
      entrypointSha256: OMP_ENTRYPOINT_SHA,
      packageJsonSha256: OMP_PACKAGE_JSON_SHA,
    },
    requiredEventsObserved: ["session_start"],
    optionalEventsObserved: [],
    schemaValid: true,
    orderingValid: true,
    isolationValid: true,
    identityValid: true,
    bindingValid: true,
    reasonCodes: [],
    diagnostics: [],
    outcome: "passed",
    sources: {
      observerLogSha256: sha("observer-log"),
      driverLogSha256: sha("driver-log"),
      scenarioSha256: sha("scenario"),
    },
    ...overrides,
  } as const;
}

function hostEventBundle() {
  return hostEventCertificationBundleFromLiveCell(localHostEventBundle(), {
    runId: ATTEMPT_ID,
    hostEventScenarioSetSha256: scenarioSet.sha256,
  });
}

function evidenceInput(bundle: unknown) {
  const written = serializeCertificationEvidence(bundle);
  return { bundle, sha256: written.sha256, locator: written.locator };
}

function draftInput(
  overrides: {
    readonly capabilityOutcome?:
      | "passed"
      | "passed-with-diagnostics"
      | "failed"
      | "blocked";
    readonly commandOutcome?: "passed" | "failed" | "blocked";
    readonly hostEventOutcome?: "passed" | "failed" | "blocked";
  } = {},
) {
  const capabilityOutcome = overrides.capabilityOutcome ?? "passed";
  const commandOutcome = overrides.commandOutcome ?? "passed";
  const hostEventOutcome = overrides.hostEventOutcome ?? "passed";
  return {
    attemptId: ATTEMPT_ID,
    target: draftTarget,
    ompVersion: "17.9.2",
    ompRegistryIntegrity: `sha512-${"C".repeat(86)}==`,
    host: draftHost,
    commandSetSha256: commandSet.sha256,
    hostEventScenarioSetSha256: scenarioSet.sha256,
    previousEntrySha256: null,
    profiles: {
      runtimeCapabilityProbe:
        capabilityOutcome === "blocked"
          ? { outcome: "blocked" as const }
          : {
              outcome: capabilityOutcome,
              evidence: evidenceInput(capabilityBundle()),
            },
      commandSurface:
        commandOutcome === "blocked"
          ? { outcome: "blocked" as const }
          : {
              outcome: commandOutcome,
              evidence: evidenceInput(commandBundle()),
            },
      hostEventSurface:
        hostEventOutcome === "blocked"
          ? { outcome: "blocked" as const }
          : {
              outcome: hostEventOutcome,
              evidence: evidenceInput(hostEventBundle()),
            },
    },
  };
}

describe("certification evidence and drafts", () => {
  it("rejects local-observation bundles before they can reach the ledger", async () => {
    await expectErrorCode(
      () => serializeCertificationEvidence(localHostEventBundle()),
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
    );
    await expectErrorCode(
      () =>
        buildCellAssessmentDraft({
          ...draftInput(),
          profiles: {
            ...draftInput().profiles,
            hostEventSurface: {
              outcome: "passed",
              evidence: {
                bundle: localHostEventBundle(),
                sha256: sha("forged"),
                locator: "validation/p0/evidence/forged.json",
              },
            },
          },
        }),
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
    );
  });

  it("re-wraps a live-cell local observation as certification-run evidence", () => {
    const bundle = hostEventBundle();
    expect(bundle.evidenceKind).toBe(CERTIFICATION_EVIDENCE_KIND);
    expect(bundle.runId).toBe(ATTEMPT_ID);
    expect(bundle.hostEventScenarioSetSha256).toBe(scenarioSet.sha256);
    const written = serializeCertificationEvidence(bundle);
    expect(written.locator).toBe(
      `validation/p0/evidence/${written.sha256}.json`,
    );
  });

  it("builds a schema-valid draft with content-bound evidence subjects", () => {
    const draft = buildCellAssessmentDraft(draftInput());
    expect(draft.attemptId).toBe(ATTEMPT_ID);
    expect(Object.keys(draft.subjectDigests)).toHaveLength(8);
    expect(draft.subjectDigests.pluginTarball).toBe(TARBALL_SHA);
    expect(draft.profiles.runtimeCapabilityProbe.evidenceSha256).toMatch(
      /^[a-f0-9]{64}$/,
    );
  });

  it("keeps blocked profiles evidence-free in the draft", () => {
    const draft = buildCellAssessmentDraft(
      draftInput({ hostEventOutcome: "blocked" }),
    );
    expect(draft.profiles.hostEventSurface.outcome).toBe("blocked");
    expect(draft.profiles.hostEventSurface.evidenceSha256).toBeNull();
    expect(Object.keys(draft.subjectDigests)).toHaveLength(7);
  });

  it("fails closed when evidence binds a different cell identity", async () => {
    await expectErrorCode(
      () =>
        buildCellAssessmentDraft({
          ...draftInput(),
          profiles: {
            ...draftInput().profiles,
            commandSurface: {
              outcome: "passed",
              evidence: evidenceInput(commandBundle({ ompVersion: "17.3.5" })),
            },
          },
        }),
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    );
  });

  it("rejects hand-written evidence digests", async () => {
    const bundle = commandBundle();
    await expectErrorCode(
      () =>
        buildCellAssessmentDraft({
          ...draftInput(),
          profiles: {
            ...draftInput().profiles,
            commandSurface: {
              outcome: "passed",
              evidence: {
                bundle,
                sha256: sha("forged-digest"),
                locator: `validation/p0/evidence/${sha("forged-digest")}.json`,
              },
            },
          },
        }),
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
    );
  });
});

// ---------------------------------------------------------------------------
// Finalize: attestation binding and derived outcome
// ---------------------------------------------------------------------------

function buildAttestationBundle(subjects: Readonly<Record<string, string>>): {
  readonly bytes: Uint8Array;
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
  const bytes = Buffer.from(JSON.stringify(bundle), "utf8");
  return { bytes, sha256: shaBytes(bytes) };
}

const trustedProvenance = {
  issuer: "https://token.actions.githubusercontent.com",
  repository: "KunoLu/sbtd-plugins",
  workflowRef:
    ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
  eventName: "workflow_dispatch",
  runId: "8123456789",
  sourceRef: "refs/heads/main",
  sourceRevision: sha("fixture-source-revision").slice(0, 40),
} as const;

describe("finalize cell assessment", () => {
  it("mints a schema-valid entry with derived outcome and verified evidence trust", () => {
    const draft = buildCellAssessmentDraft(draftInput());
    const bundle = buildAttestationBundle(draft.subjectDigests);
    const entry = finalizeCellAssessment({
      draft,
      attestationBundleBytes: bundle.bytes,
      provenance: trustedProvenance,
    });
    expect(ledgerAssessmentEntrySchema.safeParse(entry).success).toBe(true);
    expect(entry.overallOutcome).toBe("certified");
    expect(entry.profiles.runtimeCapabilityProbe.evidenceTrust).toBe(
      "verified",
    );
    expect(entry.provenance.attestationBundleSha256).toBe(bundle.sha256);
    expect(entry.entrySha256).toMatch(/^[a-f0-9]{64}$/);
  });

  it("derives eligible, never certified, for fully blocked cells", () => {
    const draft = buildCellAssessmentDraft(
      draftInput({
        capabilityOutcome: "blocked",
        commandOutcome: "blocked",
        hostEventOutcome: "blocked",
      }),
    );
    const bundle = buildAttestationBundle(draft.subjectDigests);
    const entry = finalizeCellAssessment({
      draft,
      attestationBundleBytes: bundle.bytes,
      provenance: trustedProvenance,
    });
    expect(entry.overallOutcome).toBe("eligible");
    expect(entry.profiles.hostEventSurface.evidenceTrust).toBe("missing");
  });

  it("rejects a draft whose caller tried to force the outcome", async () => {
    const draft = buildCellAssessmentDraft(draftInput());
    const bundle = buildAttestationBundle(draft.subjectDigests);
    await expectErrorCode(
      () =>
        finalizeCellAssessment({
          draft: { ...draft, overallOutcome: "certified" },
          attestationBundleBytes: bundle.bytes,
          provenance: trustedProvenance,
        }),
      "COMPATIBILITY_CELL_DRAFT_INVALID",
    );
  });

  it("normalizes GITHUB_WORKFLOW_REF to the trust-policy workflow identity", () => {
    expect(
      normalizeCertificationWorkflowRef(
        "KunoLu/sbtd-plugins/.github/workflows/omp-compatibility-certification.yml@refs/heads/main",
        "KunoLu/sbtd-plugins",
      ),
    ).toBe(
      ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
    );
    expect(
      normalizeCertificationWorkflowRef(
        ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
        "KunoLu/sbtd-plugins",
      ),
    ).toBe(
      ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
    );
    const draft = buildCellAssessmentDraft(draftInput());
    const bundle = buildAttestationBundle(draft.subjectDigests);
    const entry = finalizeCellAssessment({
      draft,
      attestationBundleBytes: bundle.bytes,
      provenance: {
        ...trustedProvenance,
        workflowRef:
          "KunoLu/sbtd-plugins/.github/workflows/omp-compatibility-certification.yml@refs/heads/main",
      },
    });
    expect(entry.provenance.workflowRef).toBe(
      ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
    );
  });

  it("fails closed on bundle digest or subject drift", async () => {
    const draft = buildCellAssessmentDraft(draftInput());
    await expectErrorCode(
      () =>
        finalizeCellAssessment({
          draft,
          attestationBundleBytes: Buffer.from("tampered", "utf8"),
          provenance: trustedProvenance,
        }),
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    );
    const reduced = { ...draft.subjectDigests };
    delete reduced.commandSet;
    await expectErrorCode(
      () =>
        finalizeCellAssessment({
          draft,
          attestationBundleBytes: buildAttestationBundle(reduced).bytes,
          provenance: trustedProvenance,
        }),
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    );
  });

  it("appends the finalized entry to the ledger with evidence binding", async () => {
    const targets = appendCompatibilityTarget(emptyTargets, draftTarget, {
      registryVersion: draftTarget.pluginVersion,
      registryDistIntegrity: draftTarget.packageIntegrity,
    });
    const draft = buildCellAssessmentDraft(draftInput());
    const bundle = buildAttestationBundle(draft.subjectDigests);
    const entry = finalizeCellAssessment({
      draft,
      attestationBundleBytes: bundle.bytes,
      provenance: trustedProvenance,
    });
    const files = new Map<string, Uint8Array>();
    files.set(
      `packages/omp-sbtd/${entry.provenance.attestationBundleLocator}`,
      bundle.bytes,
    );
    const input = draftInput();
    for (const key of [
      "runtimeCapabilityProbe",
      "commandSurface",
      "hostEventSurface",
    ] as const) {
      const profile = input.profiles[key];
      const evidence = "evidence" in profile ? profile.evidence : undefined;
      if (evidence === undefined) continue;
      const written = serializeCertificationEvidence(evidence.bundle);
      files.set(`packages/omp-sbtd/${written.locator}`, written.bytes);
    }
    const reader: CompatibilityEvidenceReader = {
      readBytes: async (locator) => {
        const bytes =
          files.get(locator) ?? files.get(`packages/omp-sbtd/${locator}`);
        if (bytes === undefined) throw new Error(`ENOENT ${locator}`);
        return bytes;
      },
    };
    const result = await appendLedgerAssessment(
      emptyLedger,
      targets.targets,
      committedTrustPolicy,
      entry,
      reader,
    );
    expect(result.outcome).toBe("appended");
    expect(result.ledger.entries).toHaveLength(1);
    const duplicate = await appendLedgerAssessment(
      result.ledger,
      targets.targets,
      committedTrustPolicy,
      entry,
      reader,
    );
    expect(duplicate.outcome).toBe("duplicate-noop");
  });
});

// ---------------------------------------------------------------------------
// Capability probe and command-surface scoring (fail-closed)
// ---------------------------------------------------------------------------

const expectedHost = {
  entrypointSha256: OMP_ENTRYPOINT_SHA,
  packageJsonSha256: OMP_PACKAGE_JSON_SHA,
  packageVersion: "17.9.2",
} as const;

function probeLogText(overrides: {
  readonly runId?: string;
  readonly present?: Readonly<Record<string, boolean>>;
  readonly packageVersion?: string;
}): string {
  const runId = overrides.runId ?? ATTEMPT_ID;
  return `${JSON.stringify({
    kind: "host_identity",
    runId,
    hostEntrypointSha256: OMP_ENTRYPOINT_SHA,
    hostPackageFound: true,
    hostPackageName: "@oh-my-pi/pi-coding-agent",
    hostPackageVersion: overrides.packageVersion ?? "17.9.2",
    hostPackageJsonSha256: OMP_PACKAGE_JSON_SHA,
  })}\n${JSON.stringify({
    kind: "capabilities",
    runId,
    inventoryVersion: "omp-extension-v1",
    present: overrides.present ?? {
      registerCommand: true,
      on: true,
      zod: true,
      registerTool: true,
    },
  })}\n`;
}

describe("capability probe scoring", () => {
  it("parses a well-formed log and scores full presence as passed", () => {
    const log = parseCapabilityProbeLog(probeLogText({}), ATTEMPT_ID);
    const score = scoreCapabilityProbe({
      log,
      pluginRegistered: true,
      expectedHost,
    });
    expect(score.outcome).toBe("passed");
    expect(score.missingRequired).toEqual([]);
  });

  it("degrades optional-only loss to passed-with-diagnostics", () => {
    const log = parseCapabilityProbeLog(
      probeLogText({
        present: {
          registerCommand: true,
          on: true,
          zod: true,
          registerTool: false,
        },
      }),
      ATTEMPT_ID,
    );
    const score = scoreCapabilityProbe({
      log,
      pluginRegistered: true,
      expectedHost,
    });
    expect(score.outcome).toBe("passed-with-diagnostics");
    expect(score.missingOptional).toEqual(["registerTool"]);
  });

  it("fails missing required capabilities or an unregistered subject", () => {
    const missing = scoreCapabilityProbe({
      log: parseCapabilityProbeLog(
        probeLogText({
          present: { registerCommand: false, on: true, zod: true },
        }),
        ATTEMPT_ID,
      ),
      pluginRegistered: true,
      expectedHost,
    });
    expect(missing.outcome).toBe("failed");
    expect(missing.missingRequired).toEqual(["registerCommand"]);
    const unregistered = scoreCapabilityProbe({
      log: parseCapabilityProbeLog(probeLogText({}), ATTEMPT_ID),
      pluginRegistered: false,
      expectedHost,
    });
    expect(unregistered.outcome).toBe("failed");
  });

  it("fails closed on malformed, foreign or identity-drifted probe logs", async () => {
    await expectErrorCode(
      () => parseCapabilityProbeLog("{not json}\n", ATTEMPT_ID),
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
    );
    await expectErrorCode(
      () =>
        parseCapabilityProbeLog(probeLogText({ runId: "gha:1:1" }), ATTEMPT_ID),
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    );
    await expectErrorCode(
      () => parseCapabilityProbeLog("", ATTEMPT_ID),
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
    );
    const drifted = parseCapabilityProbeLog(
      probeLogText({ packageVersion: "17.3.5" }),
      ATTEMPT_ID,
    );
    await expectErrorCode(
      () =>
        scoreCapabilityProbe({
          log: drifted,
          pluginRegistered: true,
          expectedHost,
        }),
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    );
  });
});

function commandSurfaceRecord(
  overrides: Readonly<Record<string, unknown>> = {},
) {
  return {
    schemaVersion: 1,
    kind: "omp-command-surface-cell",
    runId: ATTEMPT_ID,
    pluginTarballSha256: TARBALL_SHA,
    hostIdentity: {
      entrypointSha256: OMP_ENTRYPOINT_SHA,
      packageVersion: "17.9.2",
      packageJsonSha256: OMP_PACKAGE_JSON_SHA,
    },
    sbtdCommandRegistered: true,
    commands: [
      {
        command: "help",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("help"),
      },
      {
        command: "status",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("status"),
      },
      {
        command: "report",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("report"),
      },
      {
        command: "onboard plan",
        agentInvoked: false,
        contentValidated: true,
        outputSha256: sha("plan"),
      },
    ],
    unexpectedUiRequests: 0,
    sanitizationViolations: 0,
    ...overrides,
  };
}

describe("command surface scoring", () => {
  const input = {
    runId: ATTEMPT_ID,
    pluginTarballSha256: TARBALL_SHA,
    expectedHost,
  } as const;

  it("passes only the fully validated four-command surface", () => {
    expect(
      scoreCommandSurfaceRecord(commandSurfaceRecord(), input).outcome,
    ).toBe("passed");
  });

  it("fails on agent invocation, content drift, UI requests or sanitization violations", () => {
    const mutated = commandSurfaceRecord();
    mutated.commands[0] = { ...mutated.commands[0], agentInvoked: true };
    expect(scoreCommandSurfaceRecord(mutated, input).outcome).toBe("failed");
    const contentDrift = commandSurfaceRecord();
    contentDrift.commands[1] = {
      ...contentDrift.commands[1],
      contentValidated: false,
    };
    expect(scoreCommandSurfaceRecord(contentDrift, input).outcome).toBe(
      "failed",
    );
    expect(
      scoreCommandSurfaceRecord(
        commandSurfaceRecord({ unexpectedUiRequests: 1 }),
        input,
      ).outcome,
    ).toBe("failed");
    expect(
      scoreCommandSurfaceRecord(
        commandSurfaceRecord({ sanitizationViolations: 1 }),
        input,
      ).outcome,
    ).toBe("failed");
    expect(
      scoreCommandSurfaceRecord(
        commandSurfaceRecord({ sbtdCommandRegistered: false }),
        input,
      ).outcome,
    ).toBe("failed");
    expect(
      scoreCommandSurfaceRecord(
        commandSurfaceRecord({ driverError: "Error" }),
        input,
      ).outcome,
    ).toBe("failed");
  });

  it("fails closed on malformed records and identity drift", async () => {
    await expectErrorCode(
      () => scoreCommandSurfaceRecord({ kind: "other" }, input),
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
    );
    await expectErrorCode(
      () =>
        scoreCommandSurfaceRecord(
          commandSurfaceRecord({ runId: "gha:1:1" }),
          input,
        ),
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    );
    const drifted = commandSurfaceRecord();
    drifted.hostIdentity = {
      ...drifted.hostIdentity,
      packageVersion: "17.3.5",
    };
    await expectErrorCode(
      () => scoreCommandSurfaceRecord(drifted, input),
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    );
  });
});

// ---------------------------------------------------------------------------
// npm view --json parsing (characterization of the seam extracted from the
// runner CLI; trace: implement.md §31 and features/p0-conformance-release.feature
// Rule "精确已发布版本的 npm view 输出恰好解析为一个已发布版本")
// ---------------------------------------------------------------------------

const NPM_VIEW_SPEC = "@oh-my-pi/pi-coding-agent@17.3.5";
const NPM_VIEW_INTEGRITY =
  "sha512-LW1lOEmun2xkVPoQ9R5omT2ETY1Fl3FgTJHAySTqbedWOOxFbx5cz+deRBN4Z7N/82PofhngFS8dsLQC5FPyvw==";

function captureParseError(
  raw: string,
  fields: readonly string[],
): P0ValidationError {
  try {
    parseNpmViewJson(raw, NPM_VIEW_SPEC, fields);
  } catch (error) {
    expect(error).toBeInstanceOf(P0ValidationError);
    return error as P0ValidationError;
  }
  throw new Error("expected parseNpmViewJson to throw");
}

describe("parseNpmViewJson", () => {
  it("accepts an npm 10 multi-field object record", () => {
    const record = parseNpmViewJson(
      JSON.stringify({
        version: "17.3.5",
        "dist.integrity": NPM_VIEW_INTEGRITY,
      }),
      NPM_VIEW_SPEC,
      ["version", "dist.integrity"],
    );
    expect(record).toEqual({
      version: "17.3.5",
      "dist.integrity": NPM_VIEW_INTEGRITY,
    });
  });

  it("accepts an npm 12 one-element object array", () => {
    const record = parseNpmViewJson(
      JSON.stringify([
        { version: "17.3.5", "dist.integrity": NPM_VIEW_INTEGRITY },
      ]),
      NPM_VIEW_SPEC,
      ["version", "dist.integrity"],
    );
    expect(record).toEqual({
      version: "17.3.5",
      "dist.integrity": NPM_VIEW_INTEGRITY,
    });
  });

  it("maps an npm 12 one-element scalar array onto the single requested field", () => {
    const record = parseNpmViewJson(
      JSON.stringify([NPM_VIEW_INTEGRITY]),
      NPM_VIEW_SPEC,
      ["dist.integrity"],
    );
    expect(record).toEqual({ "dist.integrity": NPM_VIEW_INTEGRITY });
  });

  it("fails closed on an empty array", () => {
    const error = captureParseError("[]", ["dist.integrity"]);
    expect(error.code).toBe("COMPATIBILITY_ADMISSION_UNAVAILABLE");
    expect(error.message).toBe(
      `npm view did not resolve exactly one published version for ${NPM_VIEW_SPEC}.`,
    );
  });

  it("fails closed on a multi-version array", () => {
    const error = captureParseError(
      JSON.stringify([NPM_VIEW_INTEGRITY, NPM_VIEW_INTEGRITY]),
      ["dist.integrity"],
    );
    expect(error.code).toBe("COMPATIBILITY_ADMISSION_UNAVAILABLE");
    expect(error.message).toBe(
      `npm view did not resolve exactly one published version for ${NPM_VIEW_SPEC}.`,
    );
  });

  it("fails closed on malformed JSON", () => {
    const error = captureParseError("{not json", ["dist.integrity"]);
    expect(error.code).toBe("COMPATIBILITY_ADMISSION_UNAVAILABLE");
    expect(error.message).toBe(
      `npm view returned malformed JSON for ${NPM_VIEW_SPEC}.`,
    );
  });

  it("fails closed on a scalar array answering a multi-field query", () => {
    const error = captureParseError(JSON.stringify(["17.3.5"]), [
      "version",
      "dist.integrity",
    ]);
    expect(error.code).toBe("COMPATIBILITY_ADMISSION_UNAVAILABLE");
    expect(error.message).toBe(
      `npm view returned an unexpected shape for ${NPM_VIEW_SPEC}.`,
    );
  });

  it("fails closed on a bare scalar answering a multi-field query", () => {
    const error = captureParseError(JSON.stringify("17.3.5"), [
      "version",
      "dist.integrity",
    ]);
    expect(error.code).toBe("COMPATIBILITY_ADMISSION_UNAVAILABLE");
    expect(error.message).toBe(
      `npm view did not resolve exactly one published version for ${NPM_VIEW_SPEC}.`,
    );
  });

  it("fails closed on a single-field JSON null", () => {
    const error = captureParseError("null", ["dist.integrity"]);
    expect(error.code).toBe("COMPATIBILITY_ADMISSION_UNAVAILABLE");
    expect(error.message).toBe(
      `npm view did not resolve exactly one published version for ${NPM_VIEW_SPEC}.`,
    );
  });

  // Regression: trusted run 32960820167 failed in run-cell on CI npm 10.9.8,
  // which prints a single-field exact-version answer as a bare JSON string
  // instead of npm 12's one-element array (implement.md §31).
  it("maps an npm 10 single-field bare JSON string onto the requested field", () => {
    const record = parseNpmViewJson(
      JSON.stringify(NPM_VIEW_INTEGRITY),
      NPM_VIEW_SPEC,
      ["dist.integrity"],
    );
    expect(record).toEqual({ "dist.integrity": NPM_VIEW_INTEGRITY });
  });
});

describe("certificationCellPlanSchema", () => {
  const validCell = {
    pluginVersion: "0.1.0-rc.12",
    pluginTarballSha256: "a".repeat(64),
    pluginPeerRange: "17.3.5",
    ompVersion: "17.3.5",
    selectedAs: ["minimum"],
    inRange: true as const,
    profilesToRun: ["omp-runtime-capabilities-v1"],
  };

  it("accepts an exact stable Runtime cell", () => {
    expect(certificationCellPlanSchema.parse(validCell).ompVersion).toBe(
      "17.3.5",
    );
  });

  it("rejects a dist-tag or range as cell ompVersion", () => {
    expect(
      certificationCellPlanSchema.safeParse({
        ...validCell,
        ompVersion: "latest",
      }).success,
    ).toBe(false);
    expect(
      certificationCellPlanSchema.safeParse({
        ...validCell,
        ompVersion: ">=17.3.5",
      }).success,
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// finalize-cell / collect CLI: attested subject bytes are staged and merged
// content-addressed (trace: implement.md §36 and features/
// p0-conformance-release.feature "ledger 校验器密码学验证认证主体文件而不是
// bundle JSON 本身"). `gh attestation verify` is CI-side only and never runs
// here; these tests cover the staging and collect copy contract offline.
// ---------------------------------------------------------------------------

const runnerCliPath = join(
  pluginRoot,
  "scripts/p0/run-three-profile-certification.ts",
);
const tsxCliPath = join(pluginRoot, "node_modules/tsx/dist/cli.mjs");

async function runCertificationCli(
  arguments_: readonly string[],
): Promise<
  Readonly<{ exitCode: number | null; stdout: string; stderr: string }>
> {
  const { promise, reject, resolve } =
    Promise.withResolvers<
      Readonly<{ exitCode: number | null; stdout: string; stderr: string }>
    >();
  const child = spawn(
    process.execPath,
    [tsxCliPath, runnerCliPath, ...arguments_],
    {
      cwd: pluginRoot,
      env: {
        ...process.env,
        GITHUB_RUN_ID: "8123456789",
        GITHUB_RUN_ATTEMPT: "1",
        GITHUB_REPOSITORY: trustedProvenance.repository,
        GITHUB_WORKFLOW_REF: `${trustedProvenance.repository}/${trustedProvenance.workflowRef}`,
        GITHUB_EVENT_NAME: trustedProvenance.eventName,
        GITHUB_REF: trustedProvenance.sourceRef,
        GITHUB_SHA: trustedProvenance.sourceRevision,
      },
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  child.once("error", reject);
  child.once("close", (exitCode) => {
    resolve({ exitCode, stdout, stderr });
  });
  return promise;
}

describe("finalize-cell / collect attested subject staging", () => {
  const cellJson = {
    pluginVersion: draftTarget.pluginVersion,
    pluginTarballSha256: draftTarget.pluginTarballSha256,
    pluginPeerRange: draftTarget.pluginPeerRange,
    ompVersion: "17.9.2",
    selectedAs: ["latest"],
    inRange: true,
    profilesToRun: [
      "omp-runtime-capabilities-v1",
      "omp-command-surface-v1",
      "omp-host-events-v1",
    ],
  } as const;
  const cellKey = `${draftTarget.pluginTarballSha256.slice(0, 12)}-omp-17.9.2`;
  const stageEvidenceDir = (stageRoot: string): string =>
    join(stageRoot, "packages", "omp-sbtd", "validation", "p0", "evidence");
  const stageLedgerPath = (stageRoot: string): string =>
    join(
      stageRoot,
      "packages",
      "omp-sbtd",
      "validation",
      "p0",
      "compatibility-ledger.v1.json",
    );
  // The attested base subjects: bytes whose sha256 equals the draft's
  // subjectDigests entries (fixture identities hash these exact strings).
  const baseSubjectFiles = {
    "plugin.tarball.tgz": Buffer.from("fixture-rc99-tarball", "utf8"),
    "plugin.manifest.json": Buffer.from("fixture-rc99-manifest", "utf8"),
    "omp-artifact.js": Buffer.from("fixture-omp-cli", "utf8"),
    "command-set.json": commandSet.bytes,
    "host-event-scenario-set.json": scenarioSet.bytes,
  } as const;
  const profileSubjects = [
    ["omp-runtime-capabilities-v1", capabilityBundle()],
    ["omp-command-surface-v1", commandBundle()],
    ["omp-host-events-v1", hostEventBundle()],
  ] as const;

  async function stageFinalizeFixture(
    options: {
      readonly committedDataLayout?: boolean;
      readonly historical?: {
        readonly entry: unknown;
        readonly bundleSha256: string;
        readonly bundleBytes: Uint8Array;
        readonly profileEvidence: readonly {
          readonly sha256: string;
          readonly bytes: Uint8Array;
        }[];
      };
    } = {},
  ): Promise<{
    readonly root: string;
    readonly stageRoot: string;
    readonly dataRoot: string;
    readonly evidenceDir: string;
    readonly subjectsDir: string;
    readonly bundlePath: string;
    readonly bundleSha256: string;
    readonly profileEvidence: readonly {
      readonly sha256: string;
      readonly bytes: Uint8Array;
    }[];
  }> {
    const root = await mkdtemp(join(tmpdir(), "omp-cert-finalize-"));
    const stageRoot = join(root, "stage");
    // Committed layout: dataRoot sits at the real repo-relative depth
    // (packages/omp-sbtd/validation/p0) so the stage evidence overlay derives
    // the committed workspace root from it.
    const dataRoot = options.committedDataLayout
      ? join(root, "repo", "packages", "omp-sbtd", "validation", "p0")
      : join(root, "data");
    const evidenceDir = stageEvidenceDir(stageRoot);
    const appended = appendCompatibilityTarget(emptyTargets, draftTarget, {
      registryVersion: draftTarget.pluginVersion,
      registryDistIntegrity: draftTarget.packageIntegrity,
    });
    await mkdir(dataRoot, { recursive: true });
    await writeFile(
      join(dataRoot, "compatibility-targets.v1.json"),
      `${JSON.stringify(appended.targets, null, 2)}\n`,
    );
    await writeFile(
      join(dataRoot, "compatibility-ledger.v1.json"),
      `${JSON.stringify(
        options.historical
          ? { ...emptyLedger, entries: [options.historical.entry] }
          : emptyLedger,
        null,
        2,
      )}\n`,
    );
    await writeFile(
      join(dataRoot, "compatibility-trust-policy.v1.json"),
      `${JSON.stringify(committedTrustPolicy, null, 2)}\n`,
    );
    if (options.historical) {
      // Historical bundles/evidence live ONLY in the committed evidence root,
      // never in any stage — the run 33080049472 regression shape.
      const committedEvidenceDir = join(dataRoot, "evidence");
      await mkdir(committedEvidenceDir, { recursive: true });
      await writeFile(
        join(committedEvidenceDir, `${options.historical.bundleSha256}.json`),
        options.historical.bundleBytes,
      );
      for (const written of options.historical.profileEvidence)
        await writeFile(
          join(committedEvidenceDir, `${written.sha256}.json`),
          written.bytes,
        );
    }
    const cellDir = join(stageRoot, "transport", "cells", cellKey);
    const subjectsDir = join(cellDir, "subjects");
    await mkdir(subjectsDir, { recursive: true });
    const draft = buildCellAssessmentDraft(draftInput());
    await writeFile(
      join(cellDir, "draft.json"),
      `${JSON.stringify(draft, null, 2)}\n`,
    );
    for (const [name, bytes] of Object.entries(baseSubjectFiles))
      await writeFile(join(subjectsDir, name), bytes);
    const profileEvidence = profileSubjects.map(([, bundle]) =>
      serializeCertificationEvidence(bundle),
    );
    for (const [index, [profileName]] of profileSubjects.entries())
      await writeFile(
        join(subjectsDir, `evidence-${profileName}.json`),
        profileEvidence[index]?.bytes ?? new Uint8Array(),
      );
    // What run-cell staged: profile evidence at the suffixed content address.
    await mkdir(evidenceDir, { recursive: true });
    for (const written of profileEvidence)
      await writeFile(
        join(evidenceDir, `${written.sha256}.json`),
        written.bytes,
      );
    const bundle = buildAttestationBundle(draft.subjectDigests);
    const bundlePath = join(root, "bundle.json");
    await writeFile(bundlePath, bundle.bytes);
    return {
      root,
      stageRoot,
      dataRoot,
      evidenceDir,
      subjectsDir,
      bundlePath,
      bundleSha256: bundle.sha256,
      profileEvidence,
    };
  }

  type FinalizeFixture = Awaited<ReturnType<typeof stageFinalizeFixture>>;

  function finalizeFixture(fixture: FinalizeFixture) {
    return runCertificationCli([
      "finalize-cell",
      "--stage-root",
      fixture.stageRoot,
      "--data-root",
      fixture.dataRoot,
      "--cell",
      JSON.stringify(cellJson),
      "--bundle",
      fixture.bundlePath,
    ]);
  }

  it("stages every attested subject blob at its content address", async () => {
    const fixture = await stageFinalizeFixture();
    const result = await finalizeFixture(fixture);
    expect(result.stderr).toBe("");
    expect(result.exitCode).toBe(0);
    // Base subjects: raw bytes at the unsuffixed content address.
    for (const bytes of Object.values(baseSubjectFiles)) {
      const staged = await readFile(join(fixture.evidenceDir, shaBytes(bytes)));
      expect(staged.equals(Buffer.from(bytes))).toBe(true);
    }
    // Profile evidence is reused at its existing .json address, never
    // duplicated at the unsuffixed one.
    for (const written of fixture.profileEvidence) {
      const duplicated = await readFile(
        join(fixture.evidenceDir, written.sha256),
      ).catch(() => undefined);
      expect(duplicated).toBeUndefined();
      const reused = await readFile(
        join(fixture.evidenceDir, `${written.sha256}.json`),
      );
      expect(reused.equals(Buffer.from(written.bytes))).toBe(true);
    }
    // The bundle itself landed at its locator address.
    const bundleStaged = await readFile(
      join(fixture.evidenceDir, `${fixture.bundleSha256}.json`),
    );
    expect(bundleStaged).toBeDefined();
    // The staged ledger carries the appended entry.
    const stagedLedger = JSON.parse(
      await readFile(stageLedgerPath(fixture.stageRoot), "utf8"),
    ) as { entries: unknown[] };
    expect(stagedLedger.entries).toHaveLength(1);
  });

  it("fails closed without ledger append when a subject file is missing or drifted", async () => {
    const missing = await stageFinalizeFixture();
    await rm(join(missing.subjectsDir, "plugin.tarball.tgz"));
    const missingResult = await finalizeFixture(missing);
    expect(missingResult.exitCode).toBe(1);
    expect(missingResult.stderr).toContain(
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    );
    const missingLedger = await readFile(
      stageLedgerPath(missing.stageRoot),
    ).catch(() => undefined);
    expect(missingLedger).toBeUndefined();

    const drifted = await stageFinalizeFixture();
    await writeFile(join(drifted.subjectsDir, "unexpected.bin"), "foreign");
    const driftedResult = await finalizeFixture(drifted);
    expect(driftedResult.exitCode).toBe(1);
    expect(driftedResult.stderr).toContain(
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
    );
    const driftedLedger = await readFile(
      stageLedgerPath(drifted.stageRoot),
    ).catch(() => undefined);
    expect(driftedLedger).toBeUndefined();
  });

  it("collect merges every staged evidence file including subject blobs into the update artifact", async () => {
    const fixture = await stageFinalizeFixture();
    const finalized = await finalizeFixture(fixture);
    expect(finalized.exitCode).toBe(0);
    const outStage = join(fixture.root, "out");
    const result = await runCertificationCli([
      "collect",
      "--data-root",
      fixture.dataRoot,
      "--out",
      outStage,
      "--cell-stage",
      fixture.stageRoot,
    ]);
    expect(result.stderr).toBe("");
    expect(result.exitCode).toBe(0);
    const report = JSON.parse(result.stdout) as { ledgerChanged: boolean };
    expect(report.ledgerChanged).toBe(true);
    const outEvidence = stageEvidenceDir(outStage);
    const updateEvidence = join(outStage, "ledger-update", "evidence");
    // Unsuffixed subject blobs reached both the merged stage and the
    // committable ledger-update artifact.
    for (const bytes of Object.values(baseSubjectFiles)) {
      const digest = shaBytes(bytes);
      const staged = await readFile(join(outEvidence, digest));
      expect(staged.equals(Buffer.from(bytes))).toBe(true);
      const shipped = await readFile(join(updateEvidence, digest));
      expect(shipped.equals(Buffer.from(bytes))).toBe(true);
    }
    // Profile evidence and the bundle ship at their suffixed addresses.
    for (const written of fixture.profileEvidence) {
      const shipped = await readFile(
        join(updateEvidence, `${written.sha256}.json`),
      );
      expect(shipped.equals(Buffer.from(written.bytes))).toBe(true);
    }
    const shippedBundle = await readFile(
      join(updateEvidence, `${fixture.bundleSha256}.json`),
    );
    expect(shippedBundle).toBeDefined();
    const updateLedger = JSON.parse(
      await readFile(
        join(outStage, "ledger-update", "compatibility-ledger.v1.json"),
        "utf8",
      ),
    ) as { entries: unknown[] };
    expect(updateLedger.entries).toHaveLength(1);
    const updateCatalog = await readFile(
      join(outStage, "ledger-update", "compatibility-targets.v1.json"),
      "utf8",
    );
    expect(updateCatalog).toContain("0.1.0-rc.99");
  });

  // -------------------------------------------------------------------------
  // Stage evidence overlay (run 33080049472 regression): the committed ledger
  // already references historical attestation bundles/evidence that live ONLY
  // in the committed repository (validation/p0/evidence/<sha256>.json), never
  // in the freshly minted stage/outStage. finalize-cell and collect must
  // resolve those locators through the committed fallback; a locator missing
  // from BOTH roots still fails closed with COMPATIBILITY_ATTESTATION_MISSING.
  // -------------------------------------------------------------------------

  describe("committed evidence overlay", () => {
    // A complete historical minimum-Runtime (17.3.5) cell entry, distinct
    // identity from the fixture's 17.9.2 cell so it chains as an independent
    // ledger identity with a null predecessor.
    function historicalCell(): {
      readonly entry: unknown;
      readonly bundleSha256: string;
      readonly bundleBytes: Uint8Array;
      readonly profileEvidence: readonly {
        readonly sha256: string;
        readonly bytes: Uint8Array;
      }[];
    } {
      const capability = capabilityBundle({ ompVersion: "17.3.5" });
      const command = commandBundle({ ompVersion: "17.3.5" });
      const hostEvent = hostEventCertificationBundleFromLiveCell(
        localHostEventBundle({ ompVersion: "17.3.5" }),
        {
          runId: ATTEMPT_ID,
          hostEventScenarioSetSha256: scenarioSet.sha256,
        },
      );
      const draft = buildCellAssessmentDraft({
        ...draftInput(),
        ompVersion: "17.3.5",
        host: { ...draftHost, packageVersion: "17.3.5" },
        profiles: {
          runtimeCapabilityProbe: {
            outcome: "passed",
            evidence: evidenceInput(capability),
          },
          commandSurface: {
            outcome: "passed",
            evidence: evidenceInput(command),
          },
          hostEventSurface: {
            outcome: "passed",
            evidence: evidenceInput(hostEvent),
          },
        },
      });
      const bundle = buildAttestationBundle(draft.subjectDigests);
      const entry = finalizeCellAssessment({
        draft,
        attestationBundleBytes: bundle.bytes,
        provenance: trustedProvenance,
      });
      return {
        entry,
        bundleSha256: bundle.sha256,
        bundleBytes: bundle.bytes,
        profileEvidence: [capability, command, hostEvent].map((evidence) =>
          serializeCertificationEvidence(evidence),
        ),
      };
    }

    it("finalize-cell and collect resolve historical committed bundles absent from the stage", async () => {
      const fixture = await stageFinalizeFixture({
        committedDataLayout: true,
        historical: historicalCell(),
      });
      const finalized = await finalizeFixture(fixture);
      expect(finalized.stderr).toBe("");
      expect(finalized.exitCode).toBe(0);
      // The committed entry plus the freshly finalized one are both staged.
      const stagedLedger = JSON.parse(
        await readFile(stageLedgerPath(fixture.stageRoot), "utf8"),
      ) as { entries: unknown[] };
      expect(stagedLedger.entries).toHaveLength(2);

      const outStage = join(fixture.root, "out");
      const collected = await runCertificationCli([
        "collect",
        "--data-root",
        fixture.dataRoot,
        "--out",
        outStage,
        "--cell-stage",
        fixture.stageRoot,
      ]);
      expect(collected.stderr).toBe("");
      expect(collected.exitCode).toBe(0);
      const report = JSON.parse(collected.stdout) as {
        appended: string[];
        ledgerChanged: boolean;
      };
      expect(report.appended).toHaveLength(1);
      expect(report.ledgerChanged).toBe(true);
      const updateLedger = JSON.parse(
        await readFile(
          join(outStage, "ledger-update", "compatibility-ledger.v1.json"),
          "utf8",
        ),
      ) as { entries: unknown[] };
      expect(updateLedger.entries).toHaveLength(2);
    });

    it("still fails closed with COMPATIBILITY_ATTESTATION_MISSING when a bundle is absent from both roots", async () => {
      const historical = historicalCell();
      const fixture = await stageFinalizeFixture({
        committedDataLayout: true,
        historical,
      });
      // Remove the historical bundle from the committed evidence root too:
      // neither the stage nor the committed repository can resolve it now.
      await rm(
        join(fixture.dataRoot, "evidence", `${historical.bundleSha256}.json`),
      );
      const finalized = await finalizeFixture(fixture);
      expect(finalized.exitCode).toBe(1);
      expect(finalized.stderr).toContain("COMPATIBILITY_ATTESTATION_MISSING");
      const stagedLedger = await readFile(
        stageLedgerPath(fixture.stageRoot),
      ).catch(() => undefined);
      expect(stagedLedger).toBeUndefined();
    });

    it("prefers staged bytes over a matching committed twin", async () => {
      const historical = historicalCell();
      const fixture = await stageFinalizeFixture({
        committedDataLayout: true,
        historical,
      });
      // Drifted bytes at the historical bundle locator in the STAGE only.
      // Staged-wins means digest verification fails even though committed
      // still has the matching bundle. A committed-first overlay would pass.
      await writeFile(
        join(fixture.evidenceDir, `${historical.bundleSha256}.json`),
        "drifted-staged-twin",
      );
      const finalized = await finalizeFixture(fixture);
      expect(finalized.exitCode).toBe(1);
      expect(finalized.stderr).toContain(
        "COMPATIBILITY_ATTESTATION_UNVERIFIED",
      );
      const stagedLedger = await readFile(
        stageLedgerPath(fixture.stageRoot),
      ).catch(() => undefined);
      expect(stagedLedger).toBeUndefined();
    });
  });
});
