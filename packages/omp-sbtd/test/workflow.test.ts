import { describe, expect, it } from "vitest";
import {
  classifyTask,
  classifyTaskPrompt,
  type TaskFacts,
} from "../src/workflow/index.ts";
import {
  classifierCorpus,
  classifierCorpusVersion,
} from "./classifier-corpus.ts";

const baseTaskFacts: TaskFacts = {
  userVisibleBehavior: false,
  existingProductionCode: false,
  existingBehaviorBug: false,
  dataRisk: false,
  productionPathRisk: false,
  crossRepoScope: false,
  domainAmbiguity: false,
  durableRequirements: false,
};

describe("Feature: SBTD 运行时工作流与门禁", () => {
  it("Scenario: 用户可见变更需要 BDD 并选择对应 Route", () => {
    expect(
      classifyTask({
        userVisibleBehavior: true,
        existingProductionCode: false,
        existingBehaviorBug: false,
        dataRisk: false,
        productionPathRisk: false,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    ).toMatchObject({
      bdd: "required",
      route: "bdd-user-visible-change",
      reasons: ["user-visible-behavior"],
    });
  });

  it("Scenario: 既有缺陷优先选择 Bugfix，同时触发 Legacy、TDD 和 Refactoring", () => {
    expect(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: true,
        existingBehaviorBug: true,
        dataRisk: false,
        productionPathRisk: false,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    ).toMatchObject({
      tdd: "required",
      route: "bugfix",
      reasons: expect.arrayContaining([
        "existing-production-code",
        "existing-behavior-bug",
      ]),
    });
  });

  it("Scenario: 持久数据与生产路径按风险优先选择 Route", () => {
    expect(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: false,
        existingBehaviorBug: false,
        dataRisk: true,
        productionPathRisk: true,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    ).toMatchObject({
      route: "data-design-risk",
      reasons: expect.arrayContaining(["data-risk", "production-path-risk"]),
    });
  });

  it("Scenario: 仅内部文档或配置变更保持轻量 Route", () => {
    expect(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: false,
        existingBehaviorBug: false,
        dataRisk: false,
        productionPathRisk: false,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    ).toEqual({
      sdd: "not-needed",
      bdd: "not-needed",
      tdd: "not-needed",
      ddd: "not-needed",
      route: "small-direct-change",
      reasons: [],
      userVisibleBehavior: false,
      existingProductionCode: false,
      existingBehaviorBug: false,
      dataRisk: false,
      productionPathRisk: false,
      crossRepoScope: false,
      legacySafetyRisk: false,
      releaseOrDeploy: false,
    });
  });

  it("Scenario: 明确修复请求会生成自动分类而引用文本不会", () => {
    expect(classifyTaskPrompt("Fix an existing production bug.")).toMatchObject(
      {
        tdd: "required",
        route: "bugfix",
      },
    );
    expect(
      classifyTaskPrompt(
        'Review this quoted history only: "fix an existing production bug".',
      ),
    ).toBeUndefined();
  });

  it("Scenario: 自动分类记录观察到的项目事实", () => {
    expect(
      classifyTaskPrompt("Fix an existing production bug.", {
        rootProjectFacts: true,
        trellisWorkflow: true,
        activeTrellisTask: true,
        persistedBddCoverage: true,
        testAssetsPresent: true,
        productionSource: true,
        changedPathsObserved: true,
        changedProductionPath: true,
      }),
    ).toMatchObject({
      reasons: expect.arrayContaining([
        "root-project-facts-observed",
        "trellis-workflow-observed",
        "active-trellis-task-observed",
        "persisted-bdd-observed",
        "test-assets-observed",
        "production-source-observed",
        "changed-paths-observed",
      ]),
    });
  });

  it("Scenario: 观察到的活跃 Trellis Task 选择托管 Route", () => {
    expect(
      classifyTaskPrompt("Update the project documentation.", {
        rootProjectFacts: true,
        trellisWorkflow: true,
        activeTrellisTask: true,
        persistedBddCoverage: false,
        testAssetsPresent: false,
        productionSource: false,
        changedPathsObserved: false,
        changedProductionPath: false,
      }),
    ).toMatchObject({
      route: "trellis-managed-task",
      reasons: expect.arrayContaining(["active-trellis-task-observed"]),
    });
  });

  it.each([
    ["Diagnose the web runtime failure.", "web-runtime-diagnostics"],
    ["Run the Playwright web E2E regression.", "web-e2e-regression"],
    ["Run the Maestro mobile E2E regression.", "mobile-e2e"],
    ["Debug the web runtime failure.", "web-runtime-diagnostics"],
    ["Fix the Android E2E regression.", "mobile-e2e"],
  ] as const)("Scenario: %s 选择明确的专项 Route", (prompt, route) => {
    expect(classifyTaskPrompt(prompt)).toMatchObject({ route });
  });

  it("Scenario: 引用或代码中的专项 Route 关键词不触发自动分类", () => {
    expect(
      classifyTaskPrompt(
        "```text\nRun the Playwright web E2E regression.\nDiagnose the web runtime failure.\n```",
      ),
    ).toBeUndefined();
    expect(
      classifyTaskPrompt("> Run the Maestro mobile E2E regression."),
    ).toBeUndefined();
  });

  it.each([
    "Update the internal documentation for web E2E.",
    "更新 Web端到端回归文档",
    "Update the docs for mobile E2E.",
    "更新移动端到端回归文档",
    "Update docs about web runtime diagnosis.",
    "更新浏览器运行时诊断说明",
    "Add documentation for web E2E.",
    "新增 Web端到端回归文档",
    "Update documentation for the API.",
    "更新数据库迁移说明",
    "Update docs for API usage.",
    "更新 API 使用文档",
    "Fix docs for mobile E2E.",
    "Update API documentation.",
    "更新 API 文档",
    "Update database migration guide.",
  ])("Scenario: 文档中的专项关键词不选择专项 Route", (prompt) => {
    expect(classifyTaskPrompt(prompt)).toMatchObject({
      route: "small-direct-change",
    });
  });

  it("Scenario: 文档词汇不降低混合生产代码变更的 Route", () => {
    expect(classifyTaskPrompt("修改生产代码和文档")).toMatchObject({
      route: "legacy-safe-change",
      existingProductionCode: true,
    });
  });

  it("Scenario: 技术文档与生产代码并列变更保留语义 Route 与门禁", () => {
    expect(
      classifyTaskPrompt("Update API documentation and production code."),
    ).toMatchObject({
      route: "bdd-user-visible-change",
      existingProductionCode: true,
    });
  });

  it("Scenario: 专项关键词不升级通用生产代码变更的 Route", () => {
    expect(
      classifyTaskPrompt("Update production code and docs."),
    ).toMatchObject({
      route: "legacy-safe-change",
      existingProductionCode: true,
    });
    expect(
      classifyTaskPrompt("Update production code for Playwright E2E support."),
    ).toMatchObject({
      route: "legacy-safe-change",
      existingProductionCode: true,
    });
  });

  it("Scenario: 显式发布意图选择 Release Readiness Route", () => {
    expect(
      classifyTaskPrompt("Deploy the current service release."),
    ).toMatchObject({
      route: "release-readiness",
      releaseOrDeploy: true,
      reasons: expect.arrayContaining(["release-or-deploy"]),
    });
  });

  it.each([
    ["审阅请求", { review: true }, "review", "review-request"],
    ["重构请求", { refactoring: true }, "refactoring-pass", "refactor-request"],
    [
      "跨仓范围",
      { crossRepoScope: true },
      "trellis-managed-task",
      "cross-repo-scope",
    ],
    [
      "Web运行时诊断",
      { webRuntimeDiagnostics: true },
      "web-runtime-diagnostics",
      "web-runtime-diagnostics",
    ],
    [
      "Web端到端回归",
      { webE2ERegression: true },
      "web-e2e-regression",
      "web-e2e-regression",
    ],
    ["移动端到端回归", { mobileE2E: true }, "mobile-e2e", "mobile-e2e"],
  ] satisfies ReadonlyArray<
    readonly [
      string,
      Partial<TaskFacts>,
      ReturnType<typeof classifyTask>["route"],
      string,
    ]
  >)("Scenario: %s 选择稳定Route并记录客观原因", (_name, changes, route, reason) => {
    expect(classifyTask({ ...baseTaskFacts, ...changes })).toMatchObject({
      route,
      reasons: expect.arrayContaining([reason]),
    });
  });

  it("Scenario: 高Legacy风险选择 Legacy Safe Change Route", () => {
    expect(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: false,
        existingBehaviorBug: false,
        dataRisk: false,
        productionPathRisk: false,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
        weakOrMissingTests: true,
      }),
    ).toMatchObject({
      route: "legacy-safe-change",
      legacySafetyRisk: true,
      reasons: expect.arrayContaining(["weak-or-missing-tests"]),
    });
  });

  it("Scenario: classifier 语料保持版本化", () => {
    expect(classifierCorpusVersion).toBeGreaterThanOrEqual(1);
    expect(classifierCorpus.length).toBeGreaterThanOrEqual(12);
    expect(new Set(classifierCorpus.map((entry) => entry.id)).size).toBe(
      classifierCorpus.length,
    );
  });

  it.each(
    classifierCorpus.map((entry) => [entry.id, entry] as const),
  )("Scenario: 语料样例按期望分类: %s", (_id, entry) => {
    const classification = classifyTaskPrompt(entry.prompt);
    if (entry.expectedRoute === undefined) {
      expect(classification).toBeUndefined();
      return;
    }
    expect(classification).toBeDefined();
    expect(classification?.route).toBe(entry.expectedRoute);
    for (const [fact, expected] of Object.entries(entry.expectedFacts ?? {})) {
      expect(
        classification?.[fact as keyof TaskFacts],
        `${entry.id} fact ${fact}`,
      ).toBe(expected);
    }
  });

  it.each([
    "Review this quoted history only: 历史文本审查",
    "请审查这段引用文本",
    "この引用文をレビューして",
  ])("Scenario: 引用或历史文本审查 guard 不分类: %s", (prompt) => {
    expect(classifyTaskPrompt(prompt)).toBeUndefined();
  });

  it("Scenario: 混合文档变更保持既有 Route 语义", () => {
    expect(
      classifyTaskPrompt("Update API documentation and production code."),
    ).toMatchObject({ route: "bdd-user-visible-change" });
  });
});
