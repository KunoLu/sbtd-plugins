// Fixture provenance: KPi-owned copy of the upstream 640-skills shared
// fixtures (tests/fixtures/validation-evidence/validation-evidence-v2/ at
// promotion revision 078267f). They are test assets only and are never
// installed into any Skill tree or the embedded Kit.
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  type EvidenceProcess,
  type EvidenceProcessResult,
  observeValidationEvidence,
  type RevisionObservation,
} from "../src/evidence/index.ts";

const pluginRoot = resolve(import.meta.dirname, "..");
const fixtureRoot = join(
  import.meta.dirname,
  "fixtures",
  "validation-evidence-v2",
);
const validatorScript = join(
  pluginRoot,
  "kit",
  "onboard",
  "runtime",
  "templates",
  "skills",
  "project-validation",
  "scripts",
  "validate_validation_evidence.py",
);
const FIXTURE_COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

const nodeProcess: EvidenceProcess = {
  exec: (command, args, options) => {
    const { promise, resolve: settle } =
      Promise.withResolvers<EvidenceProcessResult>();
    execFile(
      command,
      [...args],
      { cwd: options.cwd, timeout: options.timeout },
      (error, stdout, stderr) => {
        settle({
          stdout: String(stdout),
          stderr: String(stderr),
          code:
            error === null
              ? 0
              : typeof error.code === "number"
                ? error.code
                : null,
          killed: error?.killed === true,
        });
      },
    );
    return promise;
  },
};

const currentRevision =
  (commit: string | null = FIXTURE_COMMIT, worktreeDirty = false) =>
  async (): Promise<RevisionObservation> => ({ commit, worktreeDirty });

async function observe(fixture: string, revision = currentRevision()) {
  return observeValidationEvidence({
    projectRoot: join(fixtureRoot, fixture),
    validatorScript,
    process: nodeProcess,
    observeRevision: revision,
    observedAt: "2026-08-17T00:00:00.000Z",
    envelopePaths: ["envelope.json"],
  });
}

describe("Feature: SBTD 运行时工作流与门禁 - v2 BDD evidence observer", () => {
  it.each([
    "positive-changed-junit",
    "positive-ci-junit",
    "positive-html-plus-junit",
    "positive-multi-case-same-suite",
    "positive-unchanged-playwright",
  ])("Scenario: 合法 v2 fixture 通过语义校验: %s", async (fixture) => {
    const observation = await observe(fixture);
    expect(observation).toMatchObject({
      found: true,
      version: 2,
      specificationTraceable: true,
      executionVerified: true,
      revisionCurrent: true,
    });
    expect(observation.descriptor).toMatchObject({
      descriptorVersion: 1,
      evidenceVersion: 2,
      sourceCommit: FIXTURE_COMMIT,
    });
    expect(observation.descriptor?.scenarioLinks.length).toBeGreaterThan(0);
  });

  it("Scenario: 未修改的既有 Scenario 通过当前绑定报告满足追溯", async () => {
    const observation = await observe("positive-unchanged-playwright");
    expect(observation.executionVerified).toBe(true);
    expect(observation.specificationTraceable).toBe(true);
  });

  it("Scenario: exact clean revision 证据满足 release 绑定", async () => {
    const observation = await observe("positive-ci-junit");
    expect(observation.exactRevision).toBe(true);
  });

  it("Scenario: dirty local 证据满足交付追溯但不满足 release exact 绑定", async () => {
    const observation = await observe("positive-changed-junit");
    expect(observation.revisionCurrent).toBe(true);
    expect(observation.exactRevision).toBe(false);
  });

  it.each([
    ["negative-dangling-locator", "DANGLING_LOCATOR"],
    ["negative-fabricated-label", "SELECTOR_ZERO_MATCH"],
    ["negative-failed-case", "CASE_NOT_PASSED"],
    ["negative-feature-directory", "FEATURE_NOT_FILE"],
    ["negative-missing-binding", "BINDING_MISSING"],
    ["negative-real-unrelated-passed-case", "BINDING_MISMATCH"],
    ["negative-tampered-hash", "REPORT_HASH_MISMATCH"],
    ["negative-unsafe-path", "UNSAFE_PATH"],
    ["negative-unsupported-html", "UNSUPPORTED_FORMAT"],
    ["negative-xxe-doctype", "XXE_OR_MALFORMED"],
    ["negative-xxe-entity", "XXE_OR_MALFORMED"],
    ["negative-xxe-junit", "XXE_OR_MALFORMED"],
  ])("Scenario: 非法 v2 fixture fail closed: %s", async (fixture, code) => {
    const observation = await observe(fixture);
    expect(observation.executionVerified).toBe(false);
    expect(observation.descriptor).toBeUndefined();
    expect(observation.code).toBe(code);
  });

  it("Scenario: 真实但无关的 passed case 不满足目标 scenario", async () => {
    const observation = await observe("negative-real-unrelated-passed-case");
    expect(observation.code).toBe("BINDING_MISMATCH");
    expect(observation.executionVerified).toBe(false);
  });

  it("Scenario: sourceCommit 与当前 revision 不一致时证据失效", async () => {
    const observation = await observe(
      "positive-ci-junit",
      currentRevision("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
    );
    expect(observation.executionVerified).toBe(true);
    expect(observation.revisionCurrent).toBe(false);
    expect(observation.code).toBe("STALE_REVISION");
    expect(observation.descriptor).toBeUndefined();
  });

  it("Scenario: 当前 worktree 变脏后 exact 证据失效", async () => {
    const observation = await observe(
      "positive-ci-junit",
      currentRevision(FIXTURE_COMMIT, true),
    );
    expect(observation.revisionCurrent).toBe(false);
    expect(observation.exactRevision).toBe(false);
    expect(observation.descriptor).toBeUndefined();
  });

  it("Scenario: 无 evidence envelope 时返回 not found", async () => {
    const root = await mkdtemp(join(tmpdir(), "kpi-evidence-empty-"));
    try {
      const observation = await observeValidationEvidence({
        projectRoot: root,
        validatorScript,
        process: nodeProcess,
        observeRevision: currentRevision(),
        observedAt: "2026-08-17T00:00:00.000Z",
      });
      expect(observation.found).toBe(false);
      expect(observation.executionVerified).toBe(false);
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });
});

describe("Feature: SBTD 运行时工作流与门禁 - v1 通用 evidence 兼容", () => {
  async function v1Project(
    reports: readonly { name: string; status: string; tamper?: boolean }[],
  ): Promise<string> {
    const root = await mkdtemp(join(tmpdir(), "kpi-evidence-v1-"));
    await mkdir(join(root, "reports"), { recursive: true });
    const reportEntries = [];
    for (const report of reports) {
      const bytes = Buffer.from(`report ${report.name}\n`, "utf8");
      await writeFile(join(root, "reports", report.name), bytes);
      await writeFile(
        join(root, "reports", report.name.replace(/\.[^.]+$/, ".md")),
        `# ${report.name}\n`,
      );
      const sha256 = createHash("sha256").update(bytes).digest("hex");
      reportEntries.push({
        testType: "api",
        path: `reports/${report.name}`,
        summaryMd: `reports/${report.name.replace(/\.[^.]+$/, ".md")}`,
        sha256: report.tamper === true ? "0".repeat(64) : sha256,
        status: report.status,
        mode: "full-stack",
      });
    }
    const envelope = {
      schemaVersion: 1,
      runId: "run-v1",
      createdAt: "2026-08-17T00:00:00Z",
      evidenceSource: "ci",
      trigger: "pull-request",
      repository: {
        repositoryKey: "demo",
        sourceRef: "refs/heads/main",
        sourceCommit: FIXTURE_COMMIT,
        worktreeState: "clean",
      },
      sourceRevision: "exact",
      environmentAlignment: "verified",
      e2eMode: "full-stack",
      mockStrategy: "none",
      featureSources: [],
      reports: reportEntries,
      evidencePublication: "not-configured",
      secretsRedacted: true,
    };
    await writeFile(
      join(root, "reports", "run.evidence.json"),
      JSON.stringify(envelope, null, 2),
    );
    return root;
  }

  it("Scenario: v1 通用证据可验证但不构成 scenario 追溯", async () => {
    const root = await v1Project([
      { name: "api-report-1.json", status: "passed" },
    ]);
    try {
      const observation = await observeValidationEvidence({
        projectRoot: root,
        validatorScript,
        process: nodeProcess,
        observeRevision: currentRevision(),
        observedAt: "2026-08-17T00:00:00.000Z",
      });
      expect(observation).toMatchObject({
        found: true,
        version: 1,
        specificationTraceable: false,
        executionVerified: true,
        revisionCurrent: true,
        exactRevision: true,
      });
      expect(observation.descriptor).toMatchObject({
        evidenceVersion: 1,
        scenarioLinks: [],
      });
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: v1 报告 hash 篡改 fail closed", async () => {
    const root = await v1Project([
      { name: "api-report-1.json", status: "passed", tamper: true },
    ]);
    try {
      const observation = await observeValidationEvidence({
        projectRoot: root,
        validatorScript,
        process: nodeProcess,
        observeRevision: currentRevision(),
        observedAt: "2026-08-17T00:00:00.000Z",
      });
      expect(observation.executionVerified).toBe(false);
      expect(observation.code).toBe("REPORT_HASH_MISMATCH");
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: v1 无 passed 报告不可作为验证证据", async () => {
    const root = await v1Project([
      { name: "api-report-1.json", status: "failed" },
    ]);
    try {
      const observation = await observeValidationEvidence({
        projectRoot: root,
        validatorScript,
        process: nodeProcess,
        observeRevision: currentRevision(),
        observedAt: "2026-08-17T00:00:00.000Z",
      });
      expect(observation.executionVerified).toBe(false);
      expect(observation.code).toBe("REPORT_NOT_PASSED");
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });
});
