import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import { afterEach, describe, expect, it } from "vitest";
import type {
  CandidateEquivalenceAttestation,
  CandidateIdentity,
  CanonicalEvidenceRun,
  EvidenceStore,
  OmpProcessAdapter,
  P0FileSystem,
  PackedPayloadFile,
} from "../scripts/p0/release-validator.ts";
import {
  acceptanceArtifactSha256,
  assertCandidateSourceTree,
  blindJudgeResultSha256,
  candidateIdentitySha256,
  candidateTechnicalCatalog,
  checkTechnicalConformance,
  createBlockedCompatibilityAdapter,
  createEvidenceStore,
  decideRelease,
  deterministicValueStudySchedule,
  loadConformanceCatalog,
  loadValueStudyCorpusBundle,
  renderPluginSpdxSbom,
  replayValueStudyScore,
  resolveDevelopmentRuntimeVersionFromLockfile,
  runCompleteValueStudy,
  runTestedRuntimeCompatibility,
  scoreValueStudy,
  validateCompatibilityManifest,
  validateConformanceCatalog,
  verifyCandidateEquivalence,
  verifyEmbeddedKitReleaseIntegrity,
  verifyEvidenceSnapshot,
  verifyPluginReleaseArtifacts,
  writePluginSpdxSbom,
} from "../scripts/p0/release-validator.ts";
import type { EmbeddedKitManifestV2 } from "../src/kit/manifest.ts";
import { readReleaseFixture } from "./fixtures/release-fixtures.ts";

const workspaceRoot = new URL("../../..", import.meta.url).pathname;
const validationRoot = join(workspaceRoot, "packages/omp-sbtd/validation/p0");
const temporaryRoots: string[] = [];

function requiredFixtureValue<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("Missing required fixture value");
  return value;
}

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-p0-validator-"));
  temporaryRoots.push(root);
  return root;
}

async function frozenStudy() {
  return loadValueStudyCorpusBundle(
    join(validationRoot, "value-study/corpus.v1.json"),
    validationRoot,
  );
}

function releaseCandidate(
  packageVersion: string,
  sourceDigestCharacter: string,
  tarballDigestCharacter: string,
): CandidateIdentity {
  return {
    sourceTreeSha256: sourceDigestCharacter.repeat(64),
    packedTarballSha256: tarballDigestCharacter.repeat(64),
    packageName: "@kunolu/omp-sbtd",
    packageVersion,
  };
}

function candidateRecord(
  candidate: CandidateIdentity,
  channel: "rc" | "stable",
  distTag?: string,
) {
  return {
    schemaVersion: 1,
    candidate,
    channel,
    ...(distTag === undefined ? {} : { distTag }),
    createdAt: "2026-07-27T00:00:00.000Z",
  };
}

function candidateEvidence(
  candidate: CandidateIdentity,
  evidenceId: string,
  gate: "technical" | "package" | "compatibility" | "value",
) {
  const base = {
    schemaVersion: 1,
    evidenceId,
    candidate,
    status: "passed" as const,
    recordedAt: "2026-07-27T00:00:00.000Z",
    reportSha256: "a".repeat(64),
    blockers: [],
  };
  if (gate === "compatibility")
    return {
      ...base,
      gate,
      protocol: { testedRuntimeVersion: "17.1.3" },
    };
  if (gate === "value")
    return {
      ...base,
      gate,
      protocol: {
        armCount: 40,
        pairCount: 20,
        completionProvenanceSha256: "b".repeat(64),
      },
    };
  return { ...base, gate };
}

function packedPayload(
  candidate: CandidateIdentity,
  opaque = "unchanged",
): readonly PackedPayloadFile[] {
  const packageJson = `${JSON.stringify(
    { name: candidate.packageName, version: candidate.packageVersion },
    null,
    2,
  )}\n`;
  const packageJsonBytes = Buffer.from(packageJson);
  const sbom = `${JSON.stringify(
    {
      spdxVersion: "SPDX-2.3",
      name: `${candidate.packageName}-${candidate.packageVersion}`,
      documentNamespace: `https://kpi.local/spdx/${candidate.sourceTreeSha256}`,
      files: [
        {
          fileName: "./package.json",
          checksums: [
            {
              algorithm: "SHA256",
              checksumValue: createHash("sha256")
                .update(packageJsonBytes)
                .digest("hex"),
            },
          ],
        },
      ],
      packages: [
        {
          name: candidate.packageName,
          SPDXID: "SPDXRef-Package-kunolu-omp-sbtd",
          versionInfo: candidate.packageVersion,
        },
      ],
      opaque,
    },
    null,
    2,
  )}\n`;
  return [
    {
      path: "package/SBOM.spdx.json",
      kind: "file",
      executable: false,
      bytes: Buffer.from(sbom),
    },
    {
      path: "package/package.json",
      kind: "file",
      executable: false,
      bytes: packageJsonBytes,
    },
  ];
}

function trialObservation(candidate: CandidateIdentity, observationId: string) {
  return {
    schemaVersion: 1,
    observationId,
    candidate,
    runtimeVersion: "17.1.3",
    outcome: "passed",
    environment: { host: "isolated" },
    createdAt: "2026-07-27T00:00:00.000Z",
  };
}

function completedStudyAdapter(
  calls: string[],
  options: Readonly<{
    partial?: boolean;
    invalidJudgeRubric?: boolean;
    unsafeArtifactText?: string;
    omitRouteCostForArm?: "control" | "treatment";
  }> = {},
): OmpProcessAdapter {
  return {
    preflight: async (input) => ({
      status: "ready",
      runtimeVersion: input.runtimeVersion,
      executionModelId: input.executionModelId,
      judgeModelId: input.judgeModelId,
      executionProcessId: "execution-process",
      judgeProcessId: "judge-process",
      supportsUsageEvents: true,
    }),
    setRuntimeMode: async ({ fixtureId, mode }) => {
      calls.push(`mode:${fixtureId}:${mode}`);
      return { status: "ready" };
    },
    execute: async (input) => {
      calls.push(`execute:${input.fixture.id}:${input.arm}:${input.attempt}`);
      if (options.partial && input.fixture.id === "P0-VS-DOCS-01")
        return {
          status: "blocked",
          blocker: {
            code: "HOST_INTERRUPTED",
            reason:
              "The public host stopped before returning a bounded result.",
            recovery: "Start a new isolated study after repairing the host.",
          },
        };
      const acceptanceArtifact = {
        finalResponse: options.unsafeArtifactText ?? "已完成固定验收输出",
        patch: "diff --git a/fixture b/fixture\n",
        commandOutcomes: [
          { command: "fixture-check", status: "passed" as const },
        ],
      };
      return {
        status: "completed",
        runId: input.runId,
        fixtureId: input.fixture.id,
        arm: input.arm,
        attempt: input.attempt,
        fixtureSha256: input.fixtureSha256,
        executionProcessId: "execution-process",
        events: [
          { kind: "usage" as const, turns: 1, tokens: 2 },
          {
            kind: "report" as const,
            requiredGates: input.fixture.expected.requiredGates,
            // An explicitly unclassified advisory observation omits the route
            // cost instead of synthesizing one.
            ...(options.omitRouteCostForArm === input.arm
              ? {}
              : { routeCost: input.fixture.expected.routeCost }),
          },
          {
            kind: "terminal" as const,
            outcome: "completed" as const,
            finalResponse: "已完成固定验收输出",
          },
        ],
        acceptanceArtifact,
        acceptanceArtifactSha256: acceptanceArtifactSha256(acceptanceArtifact),
      };
    },
    judge: async (input) => {
      calls.push(`judge:${input.fixtureId}`);
      const score = {
        total: 80,
        severeAcceptanceFailure: false,
        criteria: input.rubric.map((criterion) => ({
          id: criterion.id,
          score: 80,
          reason: "满足冻结验收标准",
        })),
      };
      const secondScore =
        options.invalidJudgeRubric && input.fixtureId === "P0-VS-DOCS-01"
          ? { ...score, total: 81 }
          : score;
      const result = {
        runId: input.runId,
        fixtureId: input.fixtureId,
        fixtureSha256: input.fixtureSha256,
        judgeProcessId: "judge-process",
        firstArtifactSha256: input.first.artifactSha256,
        secondArtifactSha256: input.second.artifactSha256,
        first: score,
        second: secondScore,
      };
      return {
        status: "completed",
        ...result,
        judgeResultSha256: blindJudgeResultSha256({
          fixtureId: result.fixtureId,
          firstArtifactSha256: result.firstArtifactSha256,
          secondArtifactSha256: result.secondArtifactSha256,
          first: result.first,
          second: result.second,
        }),
      };
    },
  };
}

interface CompletedRunFixture {
  readonly root: string;
  readonly store: EvidenceStore;
  readonly run: CanonicalEvidenceRun;
  readonly calls: readonly string[];
}

async function completeRun(
  runId: string,
  calls: string[] = [],
): Promise<CompletedRunFixture> {
  const root = await temporaryRoot();
  const store = createEvidenceStore({
    evidenceRoot: join(root, "evidence"),
    temporaryRoot: join(root, ".tmp/kpi-p0"),
  });
  const study = await frozenStudy();
  const result = await runCompleteValueStudy(
    completedStudyAdapter(calls),
    store,
    {
      runId,
      sourceTreeSha256: "a".repeat(64),
      catalogSha256: "b".repeat(64),
      corpusSha256: "c".repeat(64),
      rubricSha256: "d".repeat(64),
      technicalStatus: "passed",
      corpus: study.corpus,
      fixtures: study.fixtures,
      execution: {
        runtimeVersion: "17.1.3",
        modelId: "execution-model",
      },
      judge: { modelId: "judge-model" },
    },
  );
  expect(result.status, JSON.stringify(result)).toBe("passed");
  if (result.run === undefined) throw new Error("expected complete provenance");
  return { root, store, run: result.run, calls };
}

function completeScoringInput() {
  return {
    schemaVersion: 1,
    sourceTreeSha256: "a".repeat(64),
    execution: {
      runtimeVersion: "17.1.3",
      modelId: "execution-model",
      processId: "execution-process",
    },
    judge: {
      modelId: "judge-model",
      processId: "judge-process",
    },
    pairs: Array.from({ length: 20 }, (_, index) => {
      const controlOmissions: string[] = [];
      const treatmentOmissions: string[] = [];
      return {
        fixtureId: `fixture-${String(index + 1).padStart(2, "0")}`,
        expectedRequiredGates: ["bdd"],
        expectedRouteCost: "standard",
        control: {
          status: "completed",
          observedRequiredGates: ["bdd"],
          actualRouteCost: "standard",
          severeWorkflowOmissions: controlOmissions,
          attempts: [{ attempt: 1, outcome: "completed" }],
        },
        treatment: {
          status: "completed",
          observedRequiredGates: ["bdd"],
          actualRouteCost: "standard",
          severeWorkflowOmissions: treatmentOmissions,
          attempts: [{ attempt: 1, outcome: "completed" }],
        },
        judge: {
          control: {
            total: 80,
            severeAcceptanceFailure: false,
            criteria: [
              { id: "complete", score: 80, reason: "满足固定验收标准" },
            ],
          },
          treatment: {
            total: 80,
            severeAcceptanceFailure: false,
            criteria: [
              { id: "complete", score: 80, reason: "满足固定验收标准" },
            ],
          },
        },
      };
    }),
  };
}

// Original c70 old/mixed profile identities. Complete member bytes now come from
// the independently reconstructed sealed corpus, never from the current projection.
// The gzip payload is inert JSON/base64 data, never code or a generated fixture.
const licenseFixtureDeltaGzip =
  "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";
const licenseFixtureProfiles = JSON.parse(
  gunzipSync(Buffer.from(licenseFixtureDeltaGzip, "base64")).toString("utf8"),
) as Readonly<
  Record<
    "old" | "mixed",
    Readonly<{
      root: string;
      manifestSha256: string;
      ledgerSha256: string;
      projectionReportSha256: string;
      files: Readonly<Record<string, string | null>>;
    }>
  >
>;

async function licenseInventoryFixture(selected = true) {
  const root = "/license-fixture";
  const pluginRoot = join(root, "plugin");
  const upstreamRoot = join(root, "upstream");
  const stable = "onboard/runtime/assets/external-skills/stable";
  const kit = await readReleaseFixture(selected ? "mixed" : "old");
  const profile = licenseFixtureProfiles[selected ? "mixed" : "old"];
  const sha = (bytes: string | Uint8Array) =>
    createHash("sha256").update(bytes).digest("hex");
  const json = (value: unknown) =>
    Buffer.from(JSON.stringify(value, null, 2) + "\n");
  async function frozenFile(path: string, expected: string): Promise<Buffer> {
    const bytes = kit.get(path);
    if (bytes === undefined || sha(bytes) !== expected)
      throw new Error("Frozen fixture input changed or is missing: " + path);
    return bytes;
  }
  const manifestBytes = await frozenFile(
    "manifest.json",
    profile.manifestSha256,
  );
  const manifest = JSON.parse(
    manifestBytes.toString("utf8"),
  ) as EmbeddedKitManifestV2;
  if (
    manifest.projection.generatedSha256 !== profile.root ||
    manifest.retainedProvenance.manifestSha256 !== profile.ledgerSha256
  )
    throw new Error("Frozen profile pairing changed");
  const assets = new Map<string, Buffer>();
  for (const [path, expected] of Object.entries(manifest.assets)) {
    if (
      path.startsWith("/") ||
      path.includes("\\") ||
      path
        .split("/")
        .some((part) => part === "" || part === "." || part === "..")
    )
      throw new Error("Unsafe frozen fixture path");
    assets.set(path, await frozenFile(path, expected));
  }
  const reportBytes = await frozenFile(
    "projection-report.json",
    profile.projectionReportSha256,
  );
  const ledgerBytes = assets.get(stable + "/MANIFEST.json");
  const apache = assets.get("LICENSE");
  if (
    ledgerBytes === undefined ||
    apache === undefined ||
    sha(ledgerBytes) !== profile.ledgerSha256
  )
    throw new Error("Frozen fixture lacks its license/ledger bytes");
  const ledger = JSON.parse(ledgerBytes.toString("utf8")) as {
    stableSet: string;
    repositories: Record<
      string,
      {
        url: string;
        revision: string;
        license: string;
        licenseFiles: Array<{ source: string; stablePath: string }>;
      }
    >;
    skills: Record<
      string,
      {
        repository: string;
        sourceSubpath: string;
        stablePath: string;
        treeSha256: string;
      }
    >;
    sourceSelection?: {
      record: Record<string, unknown>;
      [key: string]: unknown;
    };
  };
  const initialLedger = JSON.stringify(ledger);
  const unchangedMattSkills = [
    "diagnosing-bugs",
    "tdd",
    "grill-me",
    "grill-with-docs",
    "grilling",
    "codebase-design",
    "handoff",
    "writing-for-agents",
    "to-spec",
    "to-tickets",
  ];
  const overlays = { ...manifest.overlayDigests };
  const stored = new Map<string, Buffer>();
  const metadata = {
    name: "@kunolu/omp-sbtd",
    version: "0.2.0-rc.3",
    license: "Apache-2.0",
    files: [
      "dist",
      "kit",
      "plugin.json",
      "skills",
      "LICENSE",
      "SBOM.spdx.json",
      "THIRD_PARTY_NOTICES.md",
    ],
  };
  stored.set(join(root, "package.json"), json({ license: "Apache-2.0" }));
  stored.set(join(pluginRoot, "package.json"), json(metadata));
  stored.set(join(upstreamRoot, "package.json"), json(metadata));
  for (const directory of [root, pluginRoot, upstreamRoot])
    stored.set(join(directory, "LICENSE"), Buffer.from(apache));
  // These outer package scaffolds are virtual; all 276 Kit files are real bytes.
  for (const name of [
    "plugin.json",
    "README.md",
    "README.zh.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "validation/p0/compatibility.v2.json",
  ])
    stored.set(join(pluginRoot, name), Buffer.from("{}\n"));
  stored.set(
    join(pluginRoot, "THIRD_PARTY_NOTICES.md"),
    Buffer.from("kit/onboard/runtime/LICENSE\nkit/onboard/runtime/NOTICE\n"),
  );
  for (const [path, bytes] of assets)
    stored.set(join(pluginRoot, "kit", path), Buffer.from(bytes));
  stored.set(join(pluginRoot, "kit/manifest.json"), Buffer.from(manifestBytes));
  stored.set(
    join(pluginRoot, "kit/projection-report.json"),
    Buffer.from(reportBytes),
  );
  function aggregate(): string {
    return sha(
      [
        ...Object.entries(manifest.assets)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([path, digest]) => path + "\0" + digest),
        ...Object.entries(manifest.overlayDigests)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([path, digest]) => "overlay:" + path + "\0" + digest),
      ].join("\n"),
    );
  }
  if (aggregate() !== profile.root)
    throw new Error("Frozen fixture aggregate changed");
  // Negative cases alone update self-reported metadata. Unchanged ledger/notice
  // bytes are never reformatted, so the attack—not serialization—is the delta.
  function sync() {
    if (JSON.stringify(ledger) !== initialLedger)
      assets.set(stable + "/MANIFEST.json", json(ledger));
    for (const path of stored.keys())
      if (path.startsWith(pluginRoot + "/kit/")) stored.delete(path);
    manifest.assets = Object.fromEntries(
      [...assets].map(([path, bytes]) => [path, sha(bytes)]),
    );
    manifest.overlayDigests = overlays;
    manifest.targets = Object.fromEntries(
      [
        "AGENTS.global.md",
        "AGENTS.project-root.md",
        "AGENTS.project-omp.md",
      ].map((path) => [path, requiredFixtureValue(manifest.assets[path])]),
    );
    manifest.profileCatalogSha256 = requiredFixtureValue(
      manifest.assets["catalog.json"],
    );
    manifest.retainedProvenance = {
      stableSet: ledger.stableSet,
      manifestSha256: requiredFixtureValue(
        manifest.assets[stable + "/MANIFEST.json"],
      ),
      repositories: Object.fromEntries(
        Object.entries(ledger.repositories).map(
          ([key, { url, revision, license }]) => [
            key,
            { url, revision, license },
          ],
        ),
      ),
      skills: ledger.skills,
    };
    manifest.projection.generatedSha256 = aggregate();
    for (const [path, bytes] of assets)
      stored.set(join(pluginRoot, "kit", path), Buffer.from(bytes));
    stored.set(join(pluginRoot, "kit/manifest.json"), json(manifest));
    stored.set(
      join(pluginRoot, "kit/projection-report.json"),
      Buffer.from(reportBytes),
    );
  }
  const directories = new Set([
    join(pluginRoot, "dist"),
    join(pluginRoot, "skills"),
  ]);
  function read(path: string): Buffer {
    const bytes = stored.get(path);
    if (bytes === undefined) throw new Error("Missing fixture file: " + path);
    return bytes;
  }
  const files: P0FileSystem = {
    readText: async (path) => read(path).toString("utf8"),
    readBytes: async (path) => Buffer.from(read(path)),
    writeText: async (path, text) => {
      stored.set(path, Buffer.from(text));
    },
    inspect: async (path) => {
      if (stored.has(path)) return "file";
      if (
        directories.has(path) ||
        [...stored.keys()].some((key) => key.startsWith(path + "/"))
      )
        return "directory";
      throw new Error("Missing fixture path: " + path);
    },
    list: async (path) => {
      const names = new Map<string, "file" | "directory">();
      for (const key of stored.keys()) {
        if (!key.startsWith(path + "/")) continue;
        const rest = key.slice(path.length + 1);
        const name = rest.split("/")[0];
        if (name === undefined) throw new Error("Missing fixture child name");
        names.set(name, rest.includes("/") ? "directory" : "file");
      }
      return [...names].map(([name, kind]) => ({ name, kind }));
    },
    makeDirectory: async () => {
      throw new Error("Unexpected fixture mkdir");
    },
    move: async () => {
      throw new Error("Unexpected fixture move");
    },
    remove: async () => {
      throw new Error("Unexpected fixture remove");
    },
  };
  return {
    input: { workspaceRoot: root, pluginRoot, upstreamRoot, files },
    stable,
    assets,
    ledger,
    stored,
    sync,
    unchangedMattSkills,
    overlays,
    manifest,
    trustedRoot: profile.root,
    trustedLedgerSha256: profile.ledgerSha256,
    aggregate,
    sbom: () =>
      JSON.parse(read(join(pluginRoot, "SBOM.spdx.json")).toString("utf8")) as {
        packages: Array<{ licenseConcluded: string; licenseDeclared: string }>;
        files: Array<{
          fileName: string;
          licenseConcluded: string;
          licenseInfoInFiles: string[];
        }>;
      },
  };
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("Feature: P0 发布一致性与证据", () => {
  it("Scenario: SPDX 包标识与当前 Kunolu 包作用域一致", () => {
    const rendered = JSON.parse(
      renderPluginSpdxSbom({
        plugin: {
          name: "@kunolu/omp-sbtd",
          version: "0.1.0-rc.1",
          license: "Apache-2.0",
        },
        sourceTreeSha256: "a".repeat(64),
        files: [],
      }),
    ) as {
      documentDescribes: string[];
      packages: Array<{ name: string; SPDXID: string }>;
      relationships: Array<{
        spdxElementId: string;
        relatedSpdxElement: string;
      }>;
    };

    expect(rendered.documentDescribes).toEqual([
      "SPDXRef-Package-kunolu-omp-sbtd",
    ]);
    expect(rendered.packages).toEqual([
      expect.objectContaining({
        name: "@kunolu/omp-sbtd",
        SPDXID: "SPDXRef-Package-kunolu-omp-sbtd",
      }),
    ]);
    expect(
      rendered.relationships.some(
        (relationship) =>
          relationship.relatedSpdxElement ===
          "SPDXRef-Package-kunolu-sbtd-workflow-kit",
      ),
    ).toBe(false);
  });
  it("Scenario: 非空 SPDX 保留每文件 MIT 与 Apache 而包身份仍为 Apache", () => {
    const result = JSON.parse(
      renderPluginSpdxSbom({
        plugin: {
          name: "@kunolu/omp-sbtd",
          version: "0.2.0-rc.3",
          license: "Apache-2.0",
        },
        sourceTreeSha256: "a".repeat(64),
        files: [
          { path: "owned.txt", sha256: "b".repeat(64), license: "Apache-2.0" },
          { path: "retained.txt", sha256: "c".repeat(64), license: "MIT" },
        ],
      }),
    );
    expect(
      result.files.map(
        (file: { licenseConcluded: string; licenseInfoInFiles: string[] }) => [
          file.licenseConcluded,
          file.licenseInfoInFiles,
        ],
      ),
    ).toEqual([
      ["Apache-2.0", ["Apache-2.0"]],
      ["MIT", ["MIT"]],
    ]);
    expect(result.packages[0]).toMatchObject({
      licenseConcluded: "Apache-2.0",
      licenseDeclared: "Apache-2.0",
    });
  });

  it("Scenario: renderer 不把未分类文件默认成 Apache", () => {
    expect(() =>
      renderPluginSpdxSbom({
        plugin: {
          name: "@kunolu/omp-sbtd",
          version: "0.2.0-rc.3",
          license: "Apache-2.0",
        },
        sourceTreeSha256: "a".repeat(64),
        files: [{ path: "unclassified.txt", sha256: "b".repeat(64) }],
      }),
    ).toThrow(expect.objectContaining({ code: "LICENSE_MISMATCH" }));
  });

  it.each([
    false,
    true,
  ])("Scenario: 库存识别实际 MIT 子树、Apache 元数据并保持 old/mixed 来源（selected=%s）", async (selected) => {
    const fixture = await licenseInventoryFixture(selected);
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: join(fixture.input.pluginRoot, "kit"),
        files: fixture.input.files,
      }),
    ).resolves.toMatchObject({
      projection: {
        generatedSha256: selected
          ? "03da9a165797514c0e8856e86cdeb4dd603bdcc1efe281e0f41a42561de2fa3f"
          : "b1e4bab0fa5bc30f874329773b099b486efed9eeec795022a904c5a65dd7dbf3",
      },
    });
    const ledgerBefore = JSON.stringify(fixture.ledger);
    const written = await writePluginSpdxSbom(fixture.input);
    const checked = await verifyPluginReleaseArtifacts(fixture.input);
    expect(checked).toEqual(written);
    const byPath = new Map(
      fixture.sbom().files.map((file) => [file.fileName, file]),
    );
    for (const path of [
      "skills/domain-modeling/SKILL.md",
      `skills/domain-modeling/${selected ? "GLOSSARY" : "CONTEXT"}-FORMAT.md`,
      "skills/diagnosing-bugs/SKILL.md",
      "licenses/mattpocock-skills-LICENSE",
    ]) {
      expect(byPath.get(`./kit/${fixture.stable}/${path}`)).toMatchObject({
        licenseConcluded: "MIT",
        licenseInfoInFiles: ["MIT"],
      });
    }
    for (const path of [
      "LICENSE",
      "kit/manifest.json",
      `kit/${fixture.stable}/MANIFEST.json`,
      "kit/onboard/runtime/scripts/onboard.py",
    ]) {
      expect(byPath.get(`./${path}`)).toMatchObject({
        licenseConcluded: "Apache-2.0",
        licenseInfoInFiles: ["Apache-2.0"],
      });
    }
    expect(fixture.sbom().packages[0]).toMatchObject({
      licenseConcluded: "Apache-2.0",
      licenseDeclared: "Apache-2.0",
    });
    expect(JSON.stringify(fixture.ledger)).toBe(ledgerBefore);
    expect(fixture.ledger.stableSet).toBe("2026-09-14.6");
    expect(
      requiredFixtureValue(fixture.ledger.repositories["mattpocock-skills"])
        .revision,
    ).toBe("3cca18b368ae95cdbdebbff572ccafa662551015");
    for (const name of fixture.unchangedMattSkills) {
      expect(requiredFixtureValue(fixture.ledger.skills[name]).repository).toBe(
        "mattpocock-skills",
      );
      expect(
        byPath.get(`./kit/${fixture.stable}/skills/${name}/SKILL.md`),
      ).toMatchObject({ licenseConcluded: "MIT", licenseInfoInFiles: ["MIT"] });
    }
    if (selected)
      expect(
        requiredFixtureValue(
          fixture.ledger.repositories["mattpocock-skills-domain-modeling"],
        ).revision,
      ).toBe("4ae2317ddb22b046e26455e4f9c9b3aaaf62212d");
  });

  it("Scenario: verifier 拒绝把已生成 MIT 文件许可改成 Apache 的 SBOM", async () => {
    const fixture = await licenseInventoryFixture();
    await writePluginSpdxSbom(fixture.input);
    const path = join(fixture.input.pluginRoot, "SBOM.spdx.json");
    const original = fixture.stored.get(path)?.toString("utf8");
    if (original === undefined) throw new Error("Missing written fixture SBOM");
    expect(original).toContain('"licenseConcluded": "MIT"');
    // Keep the writer's exact whitespace/order; only corrupt one license field.
    fixture.stored.set(
      path,
      Buffer.from(
        original.replace(
          '"licenseConcluded": "MIT"',
          '"licenseConcluded": "Apache-2.0"',
        ),
      ),
    );
    await expect(
      verifyPluginReleaseArtifacts(fixture.input),
    ).rejects.toMatchObject({ code: "SBOM_MISMATCH" });
  });

  it.each([
    "missing-repository",
    "unknown-repository",
    "conflicting-license",
    "unknown-pin",
    "missing-license-record",
    "missing-license-asset",
    "conflicting-license-bytes",
    "unknown-stable-asset",
    "overlapping-skill-path",
    "selection-record-conflict",
    "selection-missing",
    "domain-key-reused",
    "missing-notice",
    "notice-conflict",
    "unknown-overlay",
    "conflicting-overlay",
  ])("Scenario: 来源不完整或冲突时库存拒绝猜测许可（%s）", async (failure) => {
    const fixture = await licenseInventoryFixture();
    const domain = "mattpocock-skills-domain-modeling";
    const repository = requiredFixtureValue(
      fixture.ledger.repositories[domain],
    );
    if (failure === "missing-repository")
      delete fixture.ledger.repositories[domain];
    if (failure === "unknown-repository")
      fixture.ledger.repositories["unreviewed-source"] =
        structuredClone(repository);
    if (failure === "conflicting-license") repository.license = "Apache-2.0";
    if (failure === "unknown-pin") repository.revision = "f".repeat(40);
    if (failure === "missing-license-record") repository.licenseFiles = [];
    if (failure === "missing-license-asset")
      fixture.assets.delete(
        `${fixture.stable}/licenses/mattpocock-skills-LICENSE`,
      );
    if (failure === "conflicting-license-bytes")
      fixture.assets.set(
        `${fixture.stable}/licenses/mattpocock-skills-LICENSE`,
        Buffer.from("not the retained license\n"),
      );
    if (failure === "unknown-stable-asset")
      fixture.assets.set(
        `${fixture.stable}/unattributed.txt`,
        Buffer.from("unknown\n"),
      );
    if (failure === "missing-notice")
      fixture.assets.delete(`${fixture.stable}/THIRD_PARTY_NOTICES.md`);
    if (failure === "notice-conflict")
      fixture.assets.set(
        `${fixture.stable}/THIRD_PARTY_NOTICES.md`,
        Buffer.from("No retained license reference\n"),
      );
    if (failure === "overlapping-skill-path")
      requiredFixtureValue(
        fixture.ledger.skills["diagnosing-bugs"],
      ).stablePath = "skills/domain-modeling";
    if (
      failure === "selection-record-conflict" &&
      fixture.ledger.sourceSelection
    )
      fixture.ledger.sourceSelection.record = {
        ...fixture.ledger.sourceSelection.record,
        scope: "other-scope",
      };
    if (failure === "selection-missing") delete fixture.ledger.sourceSelection;
    if (failure === "domain-key-reused")
      requiredFixtureValue(
        fixture.ledger.skills["diagnosing-bugs"],
      ).repository = domain;
    if (failure === "unknown-overlay" || failure === "conflicting-overlay") {
      const path =
        failure === "unknown-overlay"
          ? "onboard/runtime/scripts/unreviewed.py"
          : "onboard/runtime/templates/skills/sbtd-task/references/presentation.md";
      const text = "unreviewed overlay fixture\n";
      fixture.assets.set(path, Buffer.from(text));
      fixture.overlays[path] = createHash("sha256").update(text).digest("hex");
    }
    fixture.sync();
    await expect(writePluginSpdxSbom(fixture.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
    });
    expect(
      fixture.stored.has(join(fixture.input.pluginRoot, "SBOM.spdx.json")),
    ).toBe(false);
  });

  const rootClosureAttacks = [
    "known-prefix-add",
    "replace-domain-skill",
    "delete-domain-adr",
    "remove-overlay-and-replace",
    "notice-only-three-paths",
  ] as const;
  it.each(
    ([false, true] as const).flatMap((selected) =>
      rootClosureAttacks.map((attack) => [selected, attack] as const),
    ),
  )("Scenario: 完整固定根拒绝自洽的未审字节 selected=%s attack=%s", async (selected, attack) => {
    const fixture = await licenseInventoryFixture(selected);
    const domain = fixture.stable + "/skills/domain-modeling";
    if (attack === "known-prefix-add")
      fixture.assets.set(
        domain + "/LOCAL-UNREVIEWED.md",
        Buffer.from("unreviewed local file\n"),
      );
    if (attack === "replace-domain-skill")
      fixture.assets.set(
        domain + "/SKILL.md",
        Buffer.from("unreviewed skill replacement\n"),
      );
    if (attack === "delete-domain-adr")
      fixture.assets.delete(domain + "/ADR-FORMAT.md");
    if (attack === "remove-overlay-and-replace") {
      const path =
        "onboard/runtime/templates/skills/sbtd-task/references/presentation.md";
      delete fixture.overlays[path];
      fixture.assets.set(
        path,
        Buffer.from("unreviewed presentation replacement\n"),
      );
    }
    if (attack === "notice-only-three-paths")
      fixture.assets.set(
        fixture.stable + "/THIRD_PARTY_NOTICES.md",
        Buffer.from(
          [
            "`licenses/mattpocock-skills-LICENSE`",
            "`licenses/ui-ux-pro-max-skill-LICENSE`",
            "`licenses/ponytail-LICENSE`",
          ].join("\n") + "\n",
        ),
      );
    fixture.sync();
    expect(fixture.manifest.retainedProvenance.manifestSha256).toBe(
      fixture.trustedLedgerSha256,
    );
    expect(fixture.manifest.projection.generatedSha256).toBe(
      fixture.aggregate(),
    );
    expect(fixture.manifest.projection.generatedSha256).not.toBe(
      fixture.trustedRoot,
    );
    // Exercise the real MH path: the attack is self-consistent, not malformed.
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: join(fixture.input.pluginRoot, "kit"),
        files: fixture.input.files,
      }),
    ).resolves.toMatchObject({
      projection: {
        generatedSha256: fixture.manifest.projection.generatedSha256,
      },
    });
    await expect(writePluginSpdxSbom(fixture.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
    });
    expect(
      fixture.stored.has(join(fixture.input.pluginRoot, "SBOM.spdx.json")),
    ).toBe(false);
  });

  it("Scenario: verifier 拒绝仅篡改 licenseInfoInFiles 的 SPDX", async () => {
    const fixture = await licenseInventoryFixture();
    await writePluginSpdxSbom(fixture.input);
    const path = join(fixture.input.pluginRoot, "SBOM.spdx.json");
    const original = fixture.stored.get(path)?.toString("utf8");
    if (original === undefined) throw new Error("Missing written fixture SBOM");
    const changed = original.replace(
      /("licenseInfoInFiles":\s*\[\s*)"MIT"/,
      '$1"Apache-2.0"',
    );
    expect(changed).not.toBe(original);
    fixture.stored.set(path, Buffer.from(changed));
    await expect(
      verifyPluginReleaseArtifacts(fixture.input),
    ).rejects.toMatchObject({ code: "SBOM_MISMATCH" });
  });

  it("Scenario: 39 个测试矩阵条目都具有稳定证据定位器", async () => {
    const catalog = await loadConformanceCatalog(
      join(validationRoot, "conformance-matrix.v1.json"),
      workspaceRoot,
    );

    expect(
      catalog.entries.filter((entry) => entry.id.startsWith("P0-E11-")),
    ).toHaveLength(39);
    expect(
      catalog.entries.filter((entry) => entry.id.startsWith("P0-EXIT-")),
    ).not.toHaveLength(0);

    const duplicate = structuredClone(catalog);
    duplicate.entries[1] = {
      ...requiredFixtureValue(duplicate.entries[1]),
      id: requiredFixtureValue(duplicate.entries[0]).id,
    };
    await expect(
      validateConformanceCatalog(duplicate, workspaceRoot),
    ).rejects.toMatchObject({
      code: "CATALOG_MATRIX_INVALID",
    });
  });

  it("Scenario: RC 候选技术范围只执行目录中的 automated 要求", async () => {
    const catalog = await loadConformanceCatalog(
      join(validationRoot, "conformance-matrix.v1.json"),
      workspaceRoot,
    );
    const scope = candidateTechnicalCatalog(catalog);

    expect(scope.catalog.entries).not.toHaveLength(0);
    expect(
      scope.catalog.entries.every(
        (entry) => entry.evidenceRequirement === "automated",
      ),
    ).toBe(true);
    expect(scope.excludedExternalEntryIds).toEqual(
      catalog.entries
        .filter((entry) => entry.evidenceRequirement !== "automated")
        .map((entry) => entry.id),
    );
    expect(scope.excludedExternalEntryIds).toContain("P0-EXIT-04");
  });

  it("Scenario: 长运行的 Kit 转换验证获得候选技术检查完整预算", async () => {
    const catalog = await loadConformanceCatalog(
      join(validationRoot, "conformance-matrix.v1.json"),
      workspaceRoot,
    );
    const entries = catalog.entries.filter((entry) => entry.id === "P0-E11-30");
    const observedTimeouts: number[] = [];

    const report = await checkTechnicalConformance(
      { ...catalog, entries },
      workspaceRoot,
      {
        run: async (_command, options) => {
          observedTimeouts.push(options.timeoutMs);
          return { exitCode: 0, stdout: "", stderr: "", timedOut: false };
        },
      },
    );

    expect(report.entries).toEqual([
      expect.objectContaining({ id: "P0-E11-30", status: "passed" }),
    ]);
    expect(observedTimeouts).toEqual([180_000]);
  });

  it("Scenario: 源码摘要变化不能写入候选技术证据", () => {
    try {
      assertCandidateSourceTree(
        releaseCandidate("0.1.0-rc.1", "a", "b"),
        "c".repeat(64),
      );
      throw new Error(
        "Expected candidate source binding to reject a changed tree.",
      );
    } catch (error) {
      expect(error).toMatchObject({ code: "CANDIDATE_BINDING_MISMATCH" });
    }
  });

  it("Scenario: peer range 与精确 dev pin 分离", async () => {
    const raw = JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    );
    const policy = validateCompatibilityManifest(raw, "18.11.1");
    expect(policy.peerRange).toBe(">=18 <19");
    expect(policy.developmentRuntimeVersion).toBe("18.11.1");
    expect(policy.commands).toEqual([
      "help",
      "status",
      "report",
      "onboard plan",
    ]);
    expect(
      resolveDevelopmentRuntimeVersionFromLockfile(
        await readFile(join(workspaceRoot, "pnpm-lock.yaml"), "utf8"),
      ),
    ).toBe("18.11.1");
  });

  it("Scenario: peer range 与精确 dev pin 分离 — 兼容性策略拒绝重复、遗漏或重排的只读命令", async () => {
    const raw = JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    );
    for (const commands of [
      ["help", "help", "help", "help"],
      ["help", "status", "report", "report"],
      ["status", "help", "report", "onboard plan"],
    ]) {
      expect(() =>
        validateCompatibilityManifest({ ...raw, commands }, "18.11.1"),
      ).toThrow(/required read-only commands/u);
    }
  });

  it("Scenario: 完成的 20 个配对研究提升经过验证的规范证据", async () => {
    const completed = await completeRun("complete-provenance");
    expect(completed.run.completionProvenance.arms).toHaveLength(40);
    expect(completed.run.completionProvenance.judgments).toHaveLength(20);
    expect(
      completed.calls.filter((call) => call.startsWith("execute:")),
    ).toHaveLength(40);
    expect(
      completed.calls.filter((call) => call.startsWith("judge:")),
    ).toHaveLength(20);
    expect(
      completed.calls.findIndex((call) => call.startsWith("judge:")),
    ).toBeGreaterThan(
      completed.calls
        .map((call) => call.startsWith("execute:"))
        .lastIndexOf(true),
    );

    await expect(completed.store.promote(completed.run)).resolves.toMatchObject(
      {
        runId: "complete-provenance",
      },
    );
    await expect(completed.store.readLatest()).resolves.toMatchObject({
      runId: "complete-provenance",
    });
  });

  it("Scenario: 盲评与执行保持模型和进程独立", async () => {
    const completed = await completeRun("independent-judge");
    expect(completed.run.environment).toMatchObject({
      executionModelId: "execution-model",
      judgeModelId: "judge-model",
      executionProcessId: "execution-process",
      judgeProcessId: "judge-process",
    });
    const sameModel = structuredClone(completed.run);
    sameModel.runId = "same-model";
    sameModel.environment.judgeModelId = sameModel.environment.executionModelId;
    await expect(completed.store.promote(sameModel)).rejects.toMatchObject({
      code: "JUDGE_NOT_INDEPENDENT",
    });

    const sameProcess = structuredClone(completed.run);
    sameProcess.runId = "same-process";
    sameProcess.environment.judgeProcessId =
      sameProcess.environment.executionProcessId;
    await expect(completed.store.promote(sameProcess)).rejects.toMatchObject({
      code: "JUDGE_PROCESS_NOT_INDEPENDENT",
    });
  });

  it("Scenario: Judge 响应必须逐项绑定冻结 rubric", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const study = await frozenStudy();
    const result = await runCompleteValueStudy(
      completedStudyAdapter([], { invalidJudgeRubric: true }),
      store,
      {
        runId: "invalid-judge-rubric",
        sourceTreeSha256: "a".repeat(64),
        catalogSha256: "b".repeat(64),
        corpusSha256: "c".repeat(64),
        rubricSha256: "d".repeat(64),
        technicalStatus: "passed",
        corpus: study.corpus,
        fixtures: study.fixtures,
        execution: { runtimeVersion: "17.1.3", modelId: "execution-model" },
        judge: { modelId: "judge-model" },
      },
    );

    expect(result).toMatchObject({
      status: "blocked",
      blocker: { code: "JUDGE_RESULT_INVALID" },
    });
    expect(result).not.toHaveProperty("run");
    await expect(store.readLatest()).resolves.toBeUndefined();
    await expect(store.readApproval()).resolves.toBeUndefined();
  });

  it("Scenario: 不完整或敏感的运行不能提升为规范证据", async () => {
    const completed = await completeRun("incomplete-provenance");
    const missingArm = structuredClone(completed.run);
    missingArm.runId = "missing-arm";
    missingArm.completionProvenance.arms.pop();
    await expect(completed.store.promote(missingArm)).rejects.toMatchObject({
      code: "VALUE_ARM_COMPLETENESS_INVALID",
    });

    const duplicateJudge = structuredClone(completed.run);
    duplicateJudge.runId = "duplicate-judge";
    requiredFixtureValue(
      duplicateJudge.completionProvenance.judgments[1],
    ).fixtureId = requiredFixtureValue(
      duplicateJudge.completionProvenance.judgments[0],
    ).fixtureId;
    await expect(completed.store.promote(duplicateJudge)).rejects.toMatchObject(
      {
        code: "VALUE_JUDGMENT_COMPLETENESS_INVALID",
      },
    );
    await expect(completed.store.readLatest()).resolves.toBeUndefined();
  });

  it("Scenario: 无效重试或不等资源限制不能提升", async () => {
    const completed = await completeRun("retry-and-limits");
    const invalidRetry = structuredClone(completed.run);
    invalidRetry.runId = "invalid-retry";
    requiredFixtureValue(invalidRetry.completionProvenance.arms[0]).attempts = [
      { attempt: 1, outcome: "model-quality" },
      { attempt: 2, outcome: "completed" },
    ];
    requiredFixtureValue(
      invalidRetry.completionProvenance.arms[0],
    ).acceptedAttempt = 2;
    await expect(completed.store.promote(invalidRetry)).rejects.toMatchObject({
      code: "RETRY_LINEAGE_INVALID",
    });

    const contradictoryStatus = structuredClone(completed.run);
    contradictoryStatus.runId = "contradictory-status";
    requiredFixtureValue(
      contradictoryStatus.completionProvenance.arms[0],
    ).attempts = [{ attempt: 1, outcome: "host-start" }];
    requiredFixtureValue(
      contradictoryStatus.completionProvenance.arms[0],
    ).acceptedAttempt = 1;
    await expect(
      completed.store.promote(contradictoryStatus),
    ).rejects.toMatchObject({
      code: "ATTEMPT_STATUS_INVALID",
    });

    const unequalLimits = structuredClone(completed.run);
    unequalLimits.runId = "unequal-limits";
    requiredFixtureValue(
      unequalLimits.completionProvenance.arms[1],
    ).limits.maxTokens = 79_999;
    await expect(completed.store.promote(unequalLimits)).rejects.toMatchObject({
      code: "VALUE_LIMITS_UNEQUAL",
    });
  });

  it("Scenario: 摘要绑定被篡改的配对研究保持阻断", async () => {
    const completed = await completeRun("tampered-binding");
    const artifactMismatch = structuredClone(completed.run);
    artifactMismatch.runId = "artifact-mismatch";
    requiredFixtureValue(
      artifactMismatch.completionProvenance.arms[0],
    ).acceptanceArtifactSha256 = "f".repeat(64);
    await expect(
      completed.store.promote(artifactMismatch),
    ).rejects.toMatchObject({ code: "EVIDENCE_LINEAGE_INVALID" });

    const scoreMismatch = structuredClone(completed.run);
    scoreMismatch.runId = "score-mismatch";
    scoreMismatch.metrics.treatmentMeanCorrectness = 79;
    await expect(completed.store.promote(scoreMismatch)).rejects.toMatchObject({
      code: "VALUE_SCORE_MISMATCH",
    });
  });

  it("Scenario: 随机化顺序固定且盲评输入不携带 arm 元数据", async () => {
    const study = await frozenStudy();
    const fixtureIds = study.fixtures.map((fixture) => fixture.id);
    const first = deterministicValueStudySchedule(
      study.corpus.randomSeed,
      fixtureIds,
    );
    expect(
      deterministicValueStudySchedule(study.corpus.randomSeed, fixtureIds),
    ).toEqual(first);
    expect(
      deterministicValueStudySchedule(
        `${study.corpus.randomSeed}-other`,
        fixtureIds,
      ),
    ).not.toEqual(first);
    expect(first.arms).toHaveLength(40);
    expect(first.judgments).toHaveLength(20);

    const judgeInputs: unknown[] = [];
    const calls: string[] = [];
    const adapter = completedStudyAdapter(calls);
    const originalJudge = adapter.judge;
    const recordingAdapter: OmpProcessAdapter = {
      ...adapter,
      judge: async (input) => {
        judgeInputs.push(input);
        return originalJudge(input);
      },
    };
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    await runCompleteValueStudy(recordingAdapter, store, {
      runId: "masked-judge",
      sourceTreeSha256: "a".repeat(64),
      catalogSha256: "b".repeat(64),
      corpusSha256: "c".repeat(64),
      rubricSha256: "d".repeat(64),
      technicalStatus: "passed",
      corpus: study.corpus,
      fixtures: study.fixtures,
      execution: { runtimeVersion: "17.1.3", modelId: "execution-model" },
      judge: { modelId: "judge-model" },
    });
    const serialized = JSON.stringify(judgeInputs);
    expect(serialized).not.toMatch(
      /"arm"|"mode"|"route"|"gate"|"session"|"provider"|"workspace"|"turns"|"tokens"/i,
    );
  });

  it.each([
    ["bare token", "token=must-not-persist"],
    ["absolute macOS temporary path", "/private/var/folders/kpi-private-path"],
    ["absolute workspace path", "/workspace/private-path"],
    ["absolute local file URI", "file:///private/var/folders/kpi-private-path"],
  ] as const)("Scenario: 敏感值或开发机路径不会写入临时或规范证据: %s", async (_label, unsafeArtifactText) => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const study = await frozenStudy();
    const result = await runCompleteValueStudy(
      completedStudyAdapter([], { unsafeArtifactText }),
      store,
      {
        runId: "sensitive-artifact",
        sourceTreeSha256: "a".repeat(64),
        catalogSha256: "b".repeat(64),
        corpusSha256: "c".repeat(64),
        rubricSha256: "d".repeat(64),
        technicalStatus: "passed",
        corpus: study.corpus,
        fixtures: study.fixtures,
        execution: { runtimeVersion: "17.1.3", modelId: "execution-model" },
        judge: { modelId: "judge-model" },
      },
    );
    expect(result).toMatchObject({
      status: "blocked",
      blocker: { code: "REDACTION_REJECTED" },
    });
    expect(JSON.stringify(result)).not.toContain(unsafeArtifactText);
    await expect(store.readLatest()).resolves.toBeUndefined();
  });

  it("Scenario: 局部失败不改变已有证据指针，重放不会调用模型", async () => {
    const completed = await completeRun("immutable-replay");
    await completed.store.promote(completed.run);
    const study = await frozenStudy();
    const partial = await runCompleteValueStudy(
      completedStudyAdapter([], { partial: true }),
      completed.store,
      {
        runId: "partial-failure",
        sourceTreeSha256: "a".repeat(64),
        catalogSha256: "b".repeat(64),
        corpusSha256: "c".repeat(64),
        rubricSha256: "d".repeat(64),
        technicalStatus: "passed",
        corpus: study.corpus,
        fixtures: study.fixtures,
        execution: { runtimeVersion: "17.1.3", modelId: "execution-model" },
        judge: { modelId: "judge-model" },
      },
    );
    expect(partial).toMatchObject({ status: "blocked" });
    await expect(completed.store.readLatest()).resolves.toMatchObject({
      runId: "immutable-replay",
    });

    await expect(
      verifyEvidenceSnapshot(
        join(completed.root, "evidence"),
        "immutable-replay",
      ),
    ).resolves.toMatchObject({ runId: "immutable-replay" });
    expect(replayValueStudyScore(completed.run)).toMatchObject({
      status: "passed",
      metrics: { pairCount: 20 },
    });
  });

  it("Scenario: advisory control 的未分类路由记录为无路由成本且研究仍通过", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const study = await frozenStudy();
    const result = await runCompleteValueStudy(
      completedStudyAdapter([], { omitRouteCostForArm: "control" }),
      store,
      {
        runId: "advisory-unclassified-control",
        sourceTreeSha256: "a".repeat(64),
        catalogSha256: "b".repeat(64),
        corpusSha256: "c".repeat(64),
        rubricSha256: "d".repeat(64),
        technicalStatus: "passed",
        corpus: study.corpus,
        fixtures: study.fixtures,
        execution: { runtimeVersion: "17.1.3", modelId: "execution-model" },
        judge: { modelId: "judge-model" },
      },
    );
    expect(result.status, JSON.stringify(result)).toBe("passed");
    if (result.run === undefined)
      throw new Error("expected complete provenance");
    const controlArms = result.run.completionProvenance.arms.filter(
      (arm) => arm.arm === "control",
    );
    expect(controlArms).toHaveLength(20);
    expect(controlArms.every((arm) => arm.actualRouteCost === undefined)).toBe(
      true,
    );
    const treatmentArms = result.run.completionProvenance.arms.filter(
      (arm) => arm.arm === "treatment",
    );
    expect(treatmentArms).toHaveLength(20);
    expect(
      treatmentArms.every((arm) => arm.actualRouteCost !== undefined),
    ).toBe(true);
    expect(replayValueStudyScore(result.run)).toMatchObject({
      status: "passed",
      metrics: { pairCount: 20 },
    });
  });

  it("Scenario: treatment 缺失已分类路由成本时研究保持阻断", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const study = await frozenStudy();
    const result = await runCompleteValueStudy(
      completedStudyAdapter([], { omitRouteCostForArm: "treatment" }),
      store,
      {
        runId: "treatment-unclassified-route",
        sourceTreeSha256: "a".repeat(64),
        catalogSha256: "b".repeat(64),
        corpusSha256: "c".repeat(64),
        rubricSha256: "d".repeat(64),
        technicalStatus: "passed",
        corpus: study.corpus,
        fixtures: study.fixtures,
        execution: { runtimeVersion: "17.1.3", modelId: "execution-model" },
        judge: { modelId: "judge-model" },
      },
    );
    expect(result).toMatchObject({
      status: "blocked",
      blocker: { code: "VALUE_ROUTE_UNCLASSIFIED" },
    });
    await expect(store.readLatest()).resolves.toBeUndefined();
  });

  it("Scenario: 价值指标接受边界相等和一个允许的重 Route 激活", () => {
    const input = completeScoringInput();
    requiredFixtureValue(input.pairs[0]).treatment.actualRouteCost = "heavy";
    const score = scoreValueStudy(input);

    expect(score.status).toBe("passed");
    expect(score.metrics.gateRecall).toBe(1);
    expect(score.metrics.unnecessaryHeavyRouteActivations).toBe(1);
    expect(score.metrics.treatmentMeanCorrectness).toBe(
      score.metrics.controlMeanCorrectness,
    );
  });

  it("Scenario: 零基线遗漏、额外重 Route 和 Treatment 专属严重失败都不会被放宽", () => {
    const zeroBaselineViolation = completeScoringInput();
    requiredFixtureValue(
      zeroBaselineViolation.pairs[0],
    ).treatment.severeWorkflowOmissions.push("missing-bdd");
    expect(scoreValueStudy(zeroBaselineViolation).status).toBe("failed");

    const excessiveRoute = completeScoringInput();
    requiredFixtureValue(excessiveRoute.pairs[0]).treatment.actualRouteCost =
      "heavy";
    requiredFixtureValue(excessiveRoute.pairs[1]).treatment.actualRouteCost =
      "heavy";
    expect(scoreValueStudy(excessiveRoute).status).toBe("failed");

    const treatmentOnlySevere = completeScoringInput();
    requiredFixtureValue(
      treatmentOnlySevere.pairs[0],
    ).judge.treatment.severeAcceptanceFailure = true;
    expect(scoreValueStudy(treatmentOnlySevere).status).toBe("failed");
  });

  it("Scenario: 评分保留未分类 advisory control 并要求 treatment 具备已分类路由成本", () => {
    // The fixture builder always sets a cost; the contract under test makes
    // it optional, so omit it through a named optional-cost view.
    const unclassifiedControl = completeScoringInput();
    for (const pair of unclassifiedControl.pairs) {
      const controlArm: { actualRouteCost?: string } = pair.control;
      delete controlArm.actualRouteCost;
    }
    expect(scoreValueStudy(unclassifiedControl).status).toBe("passed");

    const unclassifiedTreatment = completeScoringInput();
    const treatmentArm: { actualRouteCost?: string } = requiredFixtureValue(
      unclassifiedTreatment.pairs[0],
    ).treatment;
    delete treatmentArm.actualRouteCost;
    const score = scoreValueStudy(unclassifiedTreatment);
    expect(score.status).toBe("blocked");
    expect(score.blockers[0]?.code).toBe("VALUE_ROUTE_UNCLASSIFIED");
  });

  it("Scenario: 通过当前技术和包检查的不可变预发布候选才具备 RC 资格", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    await store.recordCandidate(candidateRecord(rc, "rc", "next"));
    await store.recordCandidateEvidence(
      candidateEvidence(rc, "rc-technical", "technical"),
    );
    await store.recordCandidateEvidence(
      candidateEvidence(rc, "rc-package", "package"),
    );

    await expect(
      store.decideCandidate(candidateIdentitySha256(rc)),
    ).resolves.toMatchObject({
      decision: "rc-eligible",
      candidate: rc,
      blockers: [],
    });

    const latestTaggedRc = releaseCandidate("1.2.3-rc.2", "c", "d");
    await expect(
      store.recordCandidate(candidateRecord(latestTaggedRc, "rc", "latest")),
    ).rejects.toMatchObject({ code: "RC_CANDIDATE_INVALID" });

    const stableAsRc = releaseCandidate("1.2.3", "e", "f");
    await expect(
      store.recordCandidate(candidateRecord(stableAsRc, "rc", "next")),
    ).rejects.toMatchObject({ code: "RC_CANDIDATE_INVALID" });
  });

  it("Scenario: 较新的非通过候选 Gate 证据保持失败关闭", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    await store.recordCandidate(candidateRecord(rc, "rc", "next"));
    await store.recordCandidateEvidence({
      ...candidateEvidence(rc, "rc-technical-passed", "technical"),
      recordedAt: "2026-07-27T00:01:00.000Z",
    });
    await store.recordCandidateEvidence({
      ...candidateEvidence(rc, "rc-technical-blocked", "technical"),
      status: "blocked",
      recordedAt: "2026-07-27T00:02:00.000Z",
      blockers: [
        {
          code: "TECHNICAL_REVALIDATION_FAILED",
          reason: "The latest exact-candidate technical run is blocked.",
          recovery: "Correct the technical blocker and record a new candidate.",
        },
      ],
    });
    await store.recordCandidateEvidence(
      candidateEvidence(rc, "rc-package", "package"),
    );

    await expect(
      store.decideCandidate(candidateIdentitySha256(rc)),
    ).resolves.toMatchObject({
      decision: "blocked",
      blockers: expect.arrayContaining([
        expect.objectContaining({ code: "TECHNICAL_EVIDENCE_MISSING" }),
      ]),
    });
  });

  it("Scenario: 观察记录不能提升任何发布 Gate", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const stable = releaseCandidate("1.2.3", "a", "b");
    await store.recordCandidate(candidateRecord(stable, "stable"));
    const observation = trialObservation(stable, "trial-one");
    await store.appendObservation(observation);
    await expect(store.appendObservation(observation)).rejects.toMatchObject({
      code: "OBSERVATION_ALREADY_EXISTS",
    });

    await expect(
      store.decideCandidate(candidateIdentitySha256(stable)),
    ).resolves.toMatchObject({
      decision: "blocked",
      candidate: stable,
      blockers: expect.arrayContaining([
        expect.objectContaining({ code: "TECHNICAL_EVIDENCE_MISSING" }),
        expect.objectContaining({ code: "PACKAGE_EVIDENCE_MISSING" }),
      ]),
    });
  });

  it("Scenario: 仅解析后的版本元数据差异可以建立候选等价证明", () => {
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    const stable = releaseCandidate("1.2.3", "c", "d");
    const attestation = verifyCandidateEquivalence({
      rcCandidate: rc,
      stableCandidate: stable,
      rcFiles: packedPayload(rc),
      stableFiles: packedPayload(stable),
      createdAt: "2026-07-27T00:00:00.000Z",
    });

    expect(attestation).toMatchObject({
      schemaVersion: 1,
      rcCandidate: rc,
      stableCandidate: stable,
      normalizedPayloadSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      attestationSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
    });
  });

  it("Scenario: 新增、删除或不透明的打包内容差异不能建立候选等价证明", () => {
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    const stable = releaseCandidate("1.2.3", "c", "d");
    const verify = (
      stableFiles: readonly PackedPayloadFile[],
    ): CandidateEquivalenceAttestation =>
      verifyCandidateEquivalence({
        rcCandidate: rc,
        stableCandidate: stable,
        rcFiles: packedPayload(rc),
        stableFiles,
        createdAt: "2026-07-27T00:00:00.000Z",
      });

    expect(() =>
      verify([
        {
          path: "package/README.md",
          kind: "file",
          executable: false,
          bytes: Buffer.from("added"),
        },
        ...packedPayload(stable),
      ]),
    ).toThrow();
    expect(() => verify(packedPayload(stable).slice(1))).toThrow();
    expect(() => verify(packedPayload(stable, "changed"))).toThrow();
    expect(() => verify([...packedPayload(stable)].reverse())).toThrow();
    const unparseableVersionMetadata = packedPayload(stable).map((file) =>
      file.path === "package/package.json"
        ? { ...file, bytes: Buffer.from("{") }
        : file,
    );
    expect(() => verify(unparseableVersionMetadata)).toThrow();
    const stalePackageManifestChecksum = packedPayload(stable).map((file) =>
      file.path === "package/SBOM.spdx.json"
        ? {
            ...file,
            bytes: Buffer.from(
              file.bytes
                .toString()
                .replace(
                  /"checksumValue": "[a-f0-9]{64}"/,
                  `"checksumValue": "${"0".repeat(64)}"`,
                ),
            ),
          }
        : file,
    );
    expect(() => verify(stalePackageManifestChecksum)).toThrow();
    const staleStableSpdx = packedPayload(stable).map((file) =>
      file.path === "package/SBOM.spdx.json"
        ? {
            ...file,
            bytes:
              packedPayload(rc).find(
                (rcFile) => rcFile.path === "package/SBOM.spdx.json",
              )?.bytes ?? file.bytes,
          }
        : file,
    );
    expect(() => verify(staleStableSpdx)).toThrow();
  });

  it("Scenario: 候选绑定不允许跨 RC 或跨稳定包复用协议证据", () => {
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    const attestedStable = releaseCandidate("1.2.3", "c", "d");
    const otherStable = releaseCandidate("1.2.4", "e", "f");
    const attestation = verifyCandidateEquivalence({
      rcCandidate: rc,
      stableCandidate: attestedStable,
      rcFiles: packedPayload(rc),
      stableFiles: packedPayload(attestedStable),
      createdAt: "2026-07-27T00:00:00.000Z",
    });

    const decision = decideRelease({
      candidate: otherStable,
      candidateRecord: candidateRecord(otherStable, "stable"),
      evidence: [
        candidateEvidence(otherStable, "other-technical", "technical"),
        candidateEvidence(otherStable, "other-package", "package"),
        candidateEvidence(rc, "rc-compatibility", "compatibility"),
        candidateEvidence(rc, "rc-value", "value"),
      ],
      attestations: [attestation],
      observations: [],
    });

    expect(decision).toMatchObject({
      decision: "blocked",
      blockers: expect.arrayContaining([
        expect.objectContaining({ code: "CANDIDATE_EQUIVALENCE_MISSING" }),
      ]),
    });

    const otherRc = releaseCandidate("1.2.3-rc.2", "9", "8");
    const crossRcDecision = decideRelease({
      candidate: attestedStable,
      candidateRecord: candidateRecord(attestedStable, "stable"),
      evidence: [
        candidateEvidence(attestedStable, "stable-technical", "technical"),
        candidateEvidence(attestedStable, "stable-package", "package"),
        candidateEvidence(otherRc, "other-rc-compatibility", "compatibility"),
        candidateEvidence(otherRc, "other-rc-value", "value"),
      ],
      attestations: [attestation],
      observations: [],
    });
    expect(crossRcDecision).toMatchObject({
      decision: "blocked",
      blockers: expect.arrayContaining([
        expect.objectContaining({ code: "CANDIDATE_EVIDENCE_MISMATCH" }),
      ]),
    });
  });

  it("Scenario: 已证明等价的当前 Runtime RC 兼容性结果可满足匹配稳定候选的兼容性 Gate", async () => {
    const root = await temporaryRoot();
    const store = createEvidenceStore({
      evidenceRoot: join(root, "evidence"),
      temporaryRoot: join(root, ".tmp/kpi-p0"),
    });
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    const stable = releaseCandidate("1.2.3", "c", "d");
    await store.recordCandidate(candidateRecord(rc, "rc", "next"));
    await store.recordCandidate(candidateRecord(stable, "stable"));
    await Promise.all([
      store.recordCandidateEvidence(
        candidateEvidence(stable, "stable-technical", "technical"),
      ),
      store.recordCandidateEvidence(
        candidateEvidence(stable, "stable-package", "package"),
      ),
      store.recordCandidateEvidence(
        candidateEvidence(rc, "rc-compatibility", "compatibility"),
      ),
      store.recordCandidateEvidence(candidateEvidence(rc, "rc-value", "value")),
    ]);
    await store.attestCandidateEquivalence({
      rcCandidate: rc,
      stableCandidate: stable,
      rcFiles: packedPayload(rc),
      stableFiles: packedPayload(stable),
      createdAt: "2026-07-27T00:00:00.000Z",
    });

    await expect(
      store.decideCandidate(candidateIdentitySha256(stable)),
    ).resolves.toMatchObject({
      decision: "ready",
      candidate: stable,
      gateSources: {
        technical: "direct",
        package: "direct",
        compatibility: "attested-rc",
        value: "attested-rc",
      },
    });
  });

  it("Scenario: 已证明等价的完整 40 arm 和 20 对 RC 价值研究可满足匹配稳定候选的价值 Gate", () => {
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    const stable = releaseCandidate("1.2.3", "c", "d");
    const attestation = verifyCandidateEquivalence({
      rcCandidate: rc,
      stableCandidate: stable,
      rcFiles: packedPayload(rc),
      stableFiles: packedPayload(stable),
      createdAt: "2026-07-27T00:00:00.000Z",
    });
    const decision = decideRelease({
      candidate: stable,
      candidateRecord: candidateRecord(stable, "stable"),
      evidence: [
        candidateEvidence(stable, "stable-technical", "technical"),
        candidateEvidence(stable, "stable-package", "package"),
        candidateEvidence(rc, "rc-compatibility", "compatibility"),
        candidateEvidence(rc, "rc-value", "value"),
      ],
      attestations: [attestation],
      observations: [trialObservation(stable, "trial-two")],
    });

    expect(decision).toMatchObject({
      decision: "ready",
      gateSources: { value: "attested-rc" },
    });
  });

  it("Scenario: 稳定候选始终重新运行技术和打包包检查", () => {
    const rc = releaseCandidate("1.2.3-rc.1", "a", "b");
    const stable = releaseCandidate("1.2.3", "c", "d");
    const attestation = verifyCandidateEquivalence({
      rcCandidate: rc,
      stableCandidate: stable,
      rcFiles: packedPayload(rc),
      stableFiles: packedPayload(stable),
      createdAt: "2026-07-27T00:00:00.000Z",
    });
    const evidence = [
      candidateEvidence(rc, "rc-technical", "technical"),
      candidateEvidence(rc, "rc-package", "package"),
      candidateEvidence(rc, "rc-compatibility", "compatibility"),
      candidateEvidence(rc, "rc-value", "value"),
    ];

    for (const missingGate of ["technical", "package"] as const) {
      const decision = decideRelease({
        candidate: stable,
        candidateRecord: candidateRecord(stable, "stable"),
        evidence: [
          ...evidence,
          ...(missingGate === "technical"
            ? [candidateEvidence(stable, "stable-package", "package")]
            : [candidateEvidence(stable, "stable-technical", "technical")]),
        ],
        attestations: [attestation],
        observations: [],
      });
      expect(decision).toMatchObject({
        decision: "blocked",
        blockers: expect.arrayContaining([
          expect.objectContaining({
            code:
              missingGate === "technical"
                ? "TECHNICAL_EVIDENCE_MISSING"
                : "PACKAGE_EVIDENCE_MISSING",
          }),
        ]),
      });
    }
  });

  it("Scenario: 稳定候选的直接协议证据仍可满足对应 Gate", () => {
    const stable = releaseCandidate("1.2.3", "a", "b");
    expect(
      decideRelease({
        candidate: stable,
        candidateRecord: candidateRecord(stable, "stable"),
        evidence: [
          candidateEvidence(stable, "stable-technical", "technical"),
          candidateEvidence(stable, "stable-package", "package"),
          candidateEvidence(stable, "stable-compatibility", "compatibility"),
          candidateEvidence(stable, "stable-value", "value"),
        ],
        attestations: [],
        observations: [],
      }),
    ).toMatchObject({
      decision: "ready",
      gateSources: {
        technical: "direct",
        package: "direct",
        compatibility: "direct",
        value: "direct",
      },
    });
  });
});

// Slice 1 (08-20-omp-plugin-compatibility-decoupling) characterization,
// migrated to the live Policy v2 contract by the Slice 2 clean cutover.
// These tests lock the current Policy v2 validator, adapter and release
// authorization behavior.
describe("Feature: P0 发布一致性与证据 — Policy v2 contract", () => {
  function lockfileWithOmpPin(specifier: string, version: string): string {
    return [
      "lockfileVersion: '9.0'",
      "",
      "importers:",
      "",
      "  packages/omp-sbtd:",
      "    devDependencies:",
      "      '@oh-my-pi/pi-coding-agent':",
      `        specifier: ${specifier}`,
      `        version: ${version}`,
      "",
    ].join("\n");
  }

  it("Scenario: peer range 与精确 dev pin 分离 — characterization: 精确 pin 解析", () => {
    expect(
      resolveDevelopmentRuntimeVersionFromLockfile(
        lockfileWithOmpPin("17.3.5", "17.3.5"),
      ),
    ).toBe("17.3.5");
  });

  it("Scenario: peer range 与精确 dev pin 分离 — characterization: range specifier fail closed", () => {
    try {
      resolveDevelopmentRuntimeVersionFromLockfile(
        lockfileWithOmpPin("^17.3.5", "17.3.5"),
      );
      throw new Error("Expected a range specifier to fail closed.");
    } catch (error) {
      expect(error).toMatchObject({ code: "DEVELOPMENT_RUNTIME_UNRESOLVED" });
    }
  });

  it("Scenario: peer range 与精确 dev pin 分离 — characterization: 缺失 importer fail closed", () => {
    try {
      resolveDevelopmentRuntimeVersionFromLockfile(
        "lockfileVersion: '9.0'\n\nimporters:\n\n  packages/other:\n    {}\n",
      );
      throw new Error("Expected a missing Plugin importer to fail closed.");
    } catch (error) {
      expect(error).toMatchObject({ code: "DEVELOPMENT_RUNTIME_UNRESOLVED" });
    }
  });

  it("Scenario: peer range 与精确 dev pin 分离 — characterization: 非语义安装版本 fail closed", () => {
    try {
      resolveDevelopmentRuntimeVersionFromLockfile(
        lockfileWithOmpPin("17.3.5", "not-a-semver"),
      );
      throw new Error("Expected a non-semver installed version to fail.");
    } catch (error) {
      expect(error).toMatchObject({ code: "DEVELOPMENT_RUNTIME_UNRESOLVED" });
    }
  });

  it("Scenario: peer range 与精确 dev pin 分离 — characterization: 策略 dev pin 与解析版本必须精确相等", async () => {
    const raw = JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    );
    try {
      validateCompatibilityManifest(raw, "17.3.6");
      throw new Error("Expected a development-pin mismatch to fail closed.");
    } catch (error) {
      expect(error).toMatchObject({
        code: "DEVELOPMENT_RUNTIME_MISMATCH",
        details: {
          policyDevelopmentRuntimeVersion: "18.11.1",
          expectedDevelopmentRuntimeVersion: "17.3.6",
        },
      });
    }
  });

  it("Scenario: 未声明 Runtime 需要显式实验授权 — characterization: 非语义检查版本 fail closed", async () => {
    const raw = JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    );
    try {
      validateCompatibilityManifest(raw, "not-a-version");
      throw new Error("Expected a non-semver checked version to fail closed.");
    } catch (error) {
      expect(error).toMatchObject({ code: "DEVELOPMENT_RUNTIME_UNRESOLVED" });
    }
  });

  it("Scenario: peer range 与精确 dev pin 分离 — characterization: 未知字段 fail closed", async () => {
    const raw = JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    );
    try {
      validateCompatibilityManifest(
        { ...raw, currentRuntimeVersion: "18.11.1" },
        "18.11.1",
      );
      throw new Error("Expected a strict-schema policy to fail closed.");
    } catch (error) {
      expect(error).toMatchObject({
        code: "COMPATIBILITY_POLICY_INVALID",
      });
    }
  });

  it("Scenario: 不可用的当前 OMP Runtime 兼容宿主不被当作通过 — characterization: 默认阻断 adapter 形状", async () => {
    const adapter = createBlockedCompatibilityAdapter();
    const result = await adapter.runTestedRuntime({
      testedRuntimeVersion: "17.3.5",
      pluginPackagePath: "/tmp/kpi-char-plugin",
      pluginTarballPath: "/tmp/kpi-char-plugin.tgz",
      sandboxRoot: "/tmp/kpi-char-sandbox",
      commands: ["help", "status", "report", "onboard plan"],
    });
    expect(result).toMatchObject({
      testedRuntimeVersion: "17.3.5",
      status: "blocked",
      agentInvoked: false,
      blocker: { code: "OMP_HOST_UNAVAILABLE" },
      commandResults: {
        help: "blocked",
        status: "blocked",
        report: "blocked",
        "onboard plan": "blocked",
      },
    });
  });

  it("Scenario: 不可用的当前 OMP Runtime 兼容宿主不被当作通过 — characterization: adapter 身份不一致 fail closed", async () => {
    const raw = JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    );
    const foreignAdapter = {
      runTestedRuntime: async () => ({
        testedRuntimeVersion: "17.3.6",
        status: "passed" as const,
        agentInvoked: false as const,
        commandResults: {
          help: "passed" as const,
          status: "passed" as const,
          report: "passed" as const,
          "onboard plan": "passed" as const,
        },
      }),
    };
    await expect(
      runTestedRuntimeCompatibility(raw, foreignAdapter, {
        pluginPackagePath: "/tmp/kpi-char-plugin",
        pluginTarballPath: "/tmp/kpi-char-plugin.tgz",
        sandboxRoot: "/tmp/kpi-char-sandbox",
        testedRuntimeVersion: "18.11.1",
      }),
    ).rejects.toMatchObject({
      code: "TESTED_RUNTIME_MISMATCH",
      details: {
        expectedTestedRuntimeVersion: "18.11.1",
        actualTestedRuntimeVersion: "17.3.6",
      },
    });
  });

  it("Scenario: 满足四命令验收的 RC 不等待任何兼容认证 profile — characterization: 失败的兼容性证据不阻断 rc-eligible", () => {
    const rc = releaseCandidate("0.1.0-rc.99", "a", "b");
    const decision = decideRelease({
      candidate: rc,
      candidateRecord: candidateRecord(rc, "rc", "next"),
      evidence: [
        candidateEvidence(rc, "rc-char-technical", "technical"),
        candidateEvidence(rc, "rc-char-package", "package"),
        {
          ...candidateEvidence(rc, "rc-char-compatibility", "compatibility"),
          status: "failed" as const,
          blockers: [
            {
              code: "OMP_HOST_COMMAND_FAILED",
              reason:
                "A read-only command did not complete in the isolated host.",
              recovery:
                "Rerun the isolated four-command acceptance for this exact candidate.",
            },
          ],
        },
      ],
      attestations: [],
      observations: [],
    });
    expect(decision).toMatchObject({
      decision: "rc-eligible",
      gateSources: {
        technical: "direct",
        package: "direct",
        compatibility: "not-required",
        value: "not-required",
      },
      blockers: [],
    });
  });

  it("Scenario: 较新的阻断运行使旧批准证据不再代表当前 P0 研究就绪状态 — characterization: legacy 决定 fail closed", () => {
    const decision = decideRelease({
      sourceTreeSha256: "a".repeat(64),
      technicalStatus: "passed",
      valueGateStatus: "passed",
      latest: {
        runId: "run-new",
        sourceTreeSha256: "a".repeat(64),
        releaseDecision: "blocked",
      },
      approved: { runId: "run-old", sourceTreeSha256: "a".repeat(64) },
    });
    expect(decision.decision).toBe("blocked");
    expect(decision.blockers.map((blocker) => blocker.code)).toEqual(
      expect.arrayContaining(["LATEST_RUN_BLOCKED", "APPROVAL_STALE"]),
    );
  });
});
