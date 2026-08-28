import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type {
  CandidateEquivalenceAttestation,
  CandidateIdentity,
  CanonicalEvidenceRun,
  EvidenceStore,
  OmpProcessAdapter,
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
  verifyEvidenceSnapshot,
} from "../scripts/p0/release-validator.ts";

const workspaceRoot = new URL("../../..", import.meta.url).pathname;
const validationRoot = join(workspaceRoot, "packages/omp-sbtd/validation/p0");
const temporaryRoots: string[] = [];

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
    pairs: Array.from({ length: 20 }, (_, index) => ({
      fixtureId: `fixture-${String(index + 1).padStart(2, "0")}`,
      expectedRequiredGates: ["bdd"],
      expectedRouteCost: "standard",
      control: {
        status: "completed",
        observedRequiredGates: ["bdd"],
        actualRouteCost: "standard",
        severeWorkflowOmissions: [],
        attempts: [{ attempt: 1, outcome: "completed" }],
      },
      treatment: {
        status: "completed",
        observedRequiredGates: ["bdd"],
        actualRouteCost: "standard",
        severeWorkflowOmissions: [],
        attempts: [{ attempt: 1, outcome: "completed" }],
      },
      judge: {
        control: {
          total: 80,
          severeAcceptanceFailure: false,
          criteria: [{ id: "complete", score: 80, reason: "满足固定验收标准" }],
        },
        treatment: {
          total: 80,
          severeAcceptanceFailure: false,
          criteria: [{ id: "complete", score: 80, reason: "满足固定验收标准" }],
        },
      },
    })),
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
        kit: {
          name: "@kunolu/sbtd-workflow-kit",
          version: "0.1.0",
          license: "Apache-2.0",
        },
        sourceTreeSha256: "a".repeat(64),
        files: [],
        kitManifest: {
          canonical: { resolvedRevision: "d".repeat(40) },
          projection: { generatedSha256: "b".repeat(64) },
        },
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
    expect(rendered.packages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "@kunolu/omp-sbtd",
          SPDXID: "SPDXRef-Package-kunolu-omp-sbtd",
        }),
        expect.objectContaining({
          name: "@kunolu/sbtd-workflow-kit",
          SPDXID: "SPDXRef-Package-kunolu-sbtd-workflow-kit",
        }),
      ]),
    );
    expect(rendered.relationships).toContainEqual({
      spdxElementId: "SPDXRef-Package-kunolu-omp-sbtd",
      relatedSpdxElement: "SPDXRef-Package-kunolu-sbtd-workflow-kit",
      relationshipType: "CONTAINS",
    });
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
      ...duplicate.entries[1],
      id: duplicate.entries[0].id,
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
    const policy = validateCompatibilityManifest(raw, "17.3.5");
    expect(policy.peerRange).toBe(">=17.3.5 <18");
    expect(policy.developmentRuntimeVersion).toBe("17.3.5");
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
    ).toBe("17.3.5");
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
        validateCompatibilityManifest({ ...raw, commands }, "17.3.5"),
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
    duplicateJudge.completionProvenance.judgments[1].fixtureId =
      duplicateJudge.completionProvenance.judgments[0].fixtureId;
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
    invalidRetry.completionProvenance.arms[0].attempts = [
      { attempt: 1, outcome: "model-quality" },
      { attempt: 2, outcome: "completed" },
    ];
    invalidRetry.completionProvenance.arms[0].acceptedAttempt = 2;
    await expect(completed.store.promote(invalidRetry)).rejects.toMatchObject({
      code: "RETRY_LINEAGE_INVALID",
    });

    const contradictoryStatus = structuredClone(completed.run);
    contradictoryStatus.runId = "contradictory-status";
    contradictoryStatus.completionProvenance.arms[0].attempts = [
      { attempt: 1, outcome: "host-start" },
    ];
    contradictoryStatus.completionProvenance.arms[0].acceptedAttempt = 1;
    await expect(
      completed.store.promote(contradictoryStatus),
    ).rejects.toMatchObject({
      code: "ATTEMPT_STATUS_INVALID",
    });

    const unequalLimits = structuredClone(completed.run);
    unequalLimits.runId = "unequal-limits";
    unequalLimits.completionProvenance.arms[1].limits.maxTokens = 79_999;
    await expect(completed.store.promote(unequalLimits)).rejects.toMatchObject({
      code: "VALUE_LIMITS_UNEQUAL",
    });
  });

  it("Scenario: 摘要绑定被篡改的配对研究保持阻断", async () => {
    const completed = await completeRun("tampered-binding");
    const artifactMismatch = structuredClone(completed.run);
    artifactMismatch.runId = "artifact-mismatch";
    artifactMismatch.completionProvenance.arms[0].acceptanceArtifactSha256 =
      "f".repeat(64);
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
    input.pairs[0].treatment.actualRouteCost = "heavy";
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
    zeroBaselineViolation.pairs[0].treatment.severeWorkflowOmissions.push(
      "missing-bdd",
    );
    expect(scoreValueStudy(zeroBaselineViolation).status).toBe("failed");

    const excessiveRoute = completeScoringInput();
    excessiveRoute.pairs[0].treatment.actualRouteCost = "heavy";
    excessiveRoute.pairs[1].treatment.actualRouteCost = "heavy";
    expect(scoreValueStudy(excessiveRoute).status).toBe("failed");

    const treatmentOnlySevere = completeScoringInput();
    treatmentOnlySevere.pairs[0].judge.treatment.severeAcceptanceFailure = true;
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
    const treatmentArm: { actualRouteCost?: string } =
      unclassifiedTreatment.pairs[0].treatment;
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
          policyDevelopmentRuntimeVersion: "17.3.5",
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
        { ...raw, currentRuntimeVersion: "17.3.5" },
        "17.3.5",
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
        testedRuntimeVersion: "17.3.5",
      }),
    ).rejects.toMatchObject({
      code: "TESTED_RUNTIME_MISMATCH",
      details: {
        expectedTestedRuntimeVersion: "17.3.5",
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
