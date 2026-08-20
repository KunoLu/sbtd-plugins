import { describe, expect, it } from "vitest";
import {
  completeSbtdCommand,
  parseSbtdCommand,
  renderSbtdHelp,
} from "../src/commands/index.ts";
import { evaluateEnvironment } from "../src/environment/index.ts";
import { createBookGatePlan } from "../src/gates/index.ts";
import { evaluateRuleRegistry, ruleRegistry } from "../src/rules/index.ts";
import {
  createStateService,
  defaultSessionState,
  deriveEffectiveControlState,
  restoreSessionState,
  SBTD_STATE_COMPACTION_KEY,
  SBTD_STATE_CUSTOM_TYPE,
} from "../src/state/index.ts";
import { classifyTask } from "../src/workflow/index.ts";

describe("Feature: SBTD 控制引导", () => {
  it("Scenario: 在未完成 Onboard 时查看帮助", () => {
    const first = renderSbtdHelp();
    expect(first).toBe(renderSbtdHelp());
    expect(first).toContain("Usage: /sbtd onboard plan");
    expect(first).toContain("Writes: no; Confirmation: not required");
    expect(parseSbtdCommand("onboard plan")).toMatchObject({
      kind: "command",
      spec: { path: ["onboard", "plan"] },
      args: [],
    });
    expect(parseSbtdCommand("onboar")).toEqual({
      kind: "unknown",
      input: ["onboar"],
      suggestions: [
        "onboard bootstrap",
        "onboard init",
        "onboard init-projects",
        "onboard plan",
        "onboard reset",
        "onboard skip apply",
        "onboard skip list",
        "onboard skip plan create",
        "onboard skip plan expire",
        "onboard skip plan revoke",
        "onboard status",
      ],
    });
  });

  it("Scenario: AcceptedSkip 命令、帮助与候选均由注册表派生", () => {
    expect(
      parseSbtdCommand(
        'onboard skip plan create ui --scope project --expires 2026-08-01T00:00:00.000Z --reason "temporary local exemption"',
      ),
    ).toMatchObject({
      kind: "command",
      spec: { path: ["onboard", "skip", "plan", "create"] },
      args: [
        "ui",
        "--scope",
        "project",
        "--expires",
        "2026-08-01T00:00:00.000Z",
        "--reason",
        "temporary local exemption",
      ],
    });
    expect(parseSbtdCommand("onboard skip apply digest")).toMatchObject({
      kind: "command",
      spec: { path: ["onboard", "skip", "apply"] },
      args: ["digest"],
    });
    expect(
      parseSbtdCommand("onboard skip plan expire record-id --reason elapsed"),
    ).toMatchObject({
      kind: "command",
      spec: { path: ["onboard", "skip", "plan", "expire"] },
      args: ["record-id", "--reason", "elapsed"],
    });
    expect(renderSbtdHelp()).toContain(
      "Usage: /sbtd onboard skip plan revoke <record-id> --reason <text>",
    );
    expect(renderSbtdHelp()).toContain(
      "Usage: /sbtd onboard skip plan expire <record-id> --reason <text>",
    );
  });

  it("Scenario: Trellis bootstrap handoff 绑定已完成 Plan 且需要独立确认", () => {
    expect(parseSbtdCommand("onboard bootstrap plan-digest")).toMatchObject({
      kind: "command",
      spec: {
        path: ["onboard", "bootstrap"],
        requiresConfirmation: true,
        mutates: true,
      },
      args: ["plan-digest"],
    });
    expect(renderSbtdHelp()).toContain(
      "Usage: /sbtd onboard bootstrap <plan-digest>",
    );
  });

  it("Scenario: Route 与 Policy 命令来自确定性命令注册表", () => {
    expect(parseSbtdCommand("route review")).toMatchObject({
      kind: "command",
      spec: { path: ["route"] },
      args: ["review"],
    });
    expect(parseSbtdCommand("strict")).toMatchObject({
      kind: "command",
      spec: { path: ["strict"] },
    });
    expect(parseSbtdCommand("gate start legacy-change-safety")).toMatchObject({
      kind: "command",
      spec: { path: ["gate", "start"] },
      args: ["legacy-change-safety"],
    });
    expect(
      parseSbtdCommand("gate record legacy-change-safety characterized"),
    ).toMatchObject({
      kind: "command",
      spec: { path: ["gate", "record"] },
      args: ["legacy-change-safety", "characterized"],
    });
    expect(renderSbtdHelp()).toContain("Usage: /sbtd route [auto|route-id]");
  });

  it("Scenario: /sbtd report 从命令注册表派生", () => {
    expect(parseSbtdCommand("report")).toMatchObject({
      kind: "command",
      spec: { path: ["report"], category: "Information", mutates: false },
      args: [],
    });
    expect(renderSbtdHelp()).toContain("Usage: /sbtd report");
    expect(completeSbtdCommand("rep")).toEqual(["report"]);
  });

  it("Scenario: 首次加载时查看默认状态", () => {
    const state = restoreSessionState([]);
    expect(state).toMatchObject({
      runtimeMode: "advisory",
      policyProfile: "strict",
      onboardProfileId: "omp-p0-standard-v1",
      securityBaseline: "local-guarded",
      route: "auto",
      environmentObservation: { mode: "needs-onboard" },
    });
    expect(
      deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      ),
    ).toBe("advisory");
  });

  it("Scenario: 缺少必需基线时请求启用 SBTD", () => {
    const entries: unknown[] = [];
    const service = createStateService(
      {
        replay: () => entries,
        append: (customType, data) => {
          entries.push({ customType, data });
        },
      },
      () => "2026-07-24T00:00:00.000Z",
    );
    const observation = evaluateEnvironment(
      {
        blockedReasons: [],
        missingRequired: ["Global AGENTS"],
        missingOptional: [],
        routeRequiredGaps: [],
        acceptedOptionalSkips: [],
      },
      "2026-07-24T00:00:00.000Z",
    );
    const result = service.on(() => observation);
    expect(result.effectiveControlState).toBe("preflight-only");
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      customType: SBTD_STATE_CUSTOM_TYPE,
      data: {
        runtimeMode: "enforced",
        environmentObservation: { mode: "needs-onboard" },
      },
    });
  });

  it("Scenario: Preflight 评估失败时保持原状态", () => {
    const existing = defaultSessionState("2026-07-24T00:00:00.000Z");
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: existing },
    ];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => {
        entries.push({ customType, data });
      },
    });
    expect(() =>
      service.on(() => {
        throw new Error("unavailable");
      }),
    ).toThrow("Preflight could not determine");
    expect(entries).toHaveLength(1);
    expect(service.restore()).toEqual(existing);
  });

  it("Scenario: 恢复 Session 时只更新环境观察", () => {
    const previous = {
      ...defaultSessionState("2026-07-24T00:00:00.000Z"),
      runtimeMode: "enforced" as const,
      policyProfile: "relaxed" as const,
    };
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: previous },
    ];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => {
        entries.push({ customType, data });
      },
    });

    const result = service.refresh(() => ({
      observedAt: "2026-07-24T01:00:00.000Z",
      mode: "managed",
      evidence: ["all baseline assets are exact"],
      repairPath: "/sbtd status",
    }));

    expect(result.effectiveControlState).toBe("active");
    expect(result.state).toMatchObject({
      runtimeMode: "enforced",
      policyProfile: "relaxed",
      environmentObservation: { mode: "managed" },
    });
    expect(entries).toHaveLength(2);
  });

  it("Scenario: 关闭自动控制但保留基础约束", () => {
    const previous = {
      ...defaultSessionState("2026-07-24T00:00:00.000Z"),
      runtimeMode: "enforced" as const,
      policyProfile: "relaxed" as const,
      environmentObservation: {
        observedAt: "2026-07-24T00:00:00.000Z",
        mode: "managed" as const,
        evidence: ["all managed"],
        repairPath: "/sbtd status",
      },
    };
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: previous },
    ];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => {
        entries.push({ customType, data });
      },
    });
    const result = service.off();
    expect(result.effectiveControlState).toBe("advisory");
    expect(result.state).toMatchObject({
      runtimeMode: "advisory",
      policyProfile: "relaxed",
      onboardProfileId: "omp-p0-standard-v1",
      environmentObservation: previous.environmentObservation,
    });
  });
  it("Scenario: 环境评估按 blocked、needs-onboard、degraded、managed 顺序确定结果", () => {
    const observedAt = "2026-07-24T00:00:00.000Z";
    expect(
      evaluateEnvironment(
        {
          blockedReasons: ["unsafe target"],
          missingRequired: ["Global"],
          missingOptional: ["UI"],
          routeRequiredGaps: [],
          acceptedOptionalSkips: [],
        },
        observedAt,
      ).mode,
    ).toBe("blocked");
    expect(
      evaluateEnvironment(
        {
          blockedReasons: [],
          missingRequired: [],
          missingOptional: [],
          routeRequiredGaps: ["required route capability is unavailable"],
          acceptedOptionalSkips: [],
        },
        observedAt,
      ).mode,
    ).toBe("blocked");
    expect(
      evaluateEnvironment(
        {
          blockedReasons: [],
          missingRequired: [],
          missingOptional: ["UI"],
          routeRequiredGaps: [],
          acceptedOptionalSkips: [
            { capability: "UI", expiresAt: "2026-07-25T00:00:00.000Z" },
          ],
        },
        observedAt,
      ).mode,
    ).toBe("degraded");
    expect(
      evaluateEnvironment(
        {
          blockedReasons: [],
          missingRequired: [],
          missingOptional: [],
          routeRequiredGaps: [],
          acceptedOptionalSkips: [],
        },
        observedAt,
      ).mode,
    ).toBe("managed");
  });

  it("Scenario: 版本化分类与门禁状态随 Session 一起恢复", () => {
    const classification = {
      sdd: "not-needed" as const,
      bdd: "not-needed" as const,
      tdd: "not-needed" as const,
      ddd: "not-needed" as const,
      route: "data-design-risk" as const,
      reasons: ["data-risk"],
      userVisibleBehavior: false,
      existingProductionCode: false,
      existingBehaviorBug: false,
      dataRisk: true,
      productionPathRisk: false,
      crossRepoScope: false,
      legacySafetyRisk: false,
      releaseOrDeploy: false,
    };
    const persisted = {
      ...defaultSessionState("2026-07-24T00:00:00.000Z"),
      route: "data-design-risk" as const,
      classification,
      bookGates: createBookGatePlan(classification),
      ruleDecisions: [],
    };

    expect(
      restoreSessionState([
        { customType: SBTD_STATE_CUSTOM_TYPE, data: persisted },
      ]),
    ).toEqual(persisted);
  });

  it("Scenario: 非法 Gate 与 Reviewer 组合不能恢复为有效状态", () => {
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: false,
      existingBehaviorBug: false,
      dataRisk: true,
      productionPathRisk: false,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    const invalidPlan = createBookGatePlan(classification).map((gate) =>
      gate.id === "ddia-data-design"
        ? {
            ...gate,
            gateState: "passed" as const,
            reviewerStatus: "proceed" as const,
          }
        : gate,
    );

    expect(() =>
      restoreSessionState([
        {
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: {
            ...defaultSessionState("2026-07-25T00:00:00.000Z"),
            classification,
            bookGates: invalidPlan,
          },
        },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
  });

  it("Scenario: 缺少载荷的最新 KPi 状态不能回退到旧状态", () => {
    expect(() =>
      restoreSessionState([
        {
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: defaultSessionState("2026-07-25T00:00:00.000Z"),
        },
        { customType: SBTD_STATE_CUSTOM_TYPE },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
  });

  it("Scenario: 无歧义 Draft enabled 与裸 mode 状态迁移到版本一", () => {
    const current = defaultSessionState("2026-07-26T00:00:00.000Z");
    const draft = {
      enabled: true,
      mode: "relaxed",
      onboardProfileId: current.onboardProfileId,
      securityBaseline: current.securityBaseline,
      route: current.route,
      activeSkills: current.activeSkills,
      ruleDecisions: current.ruleDecisions,
      environmentObservation: current.environmentObservation,
    };

    expect(
      restoreSessionState([
        { customType: SBTD_STATE_CUSTOM_TYPE, data: draft },
      ]),
    ).toMatchObject({
      stateVersion: 1,
      runtimeMode: "enforced",
      policyProfile: "relaxed",
      environmentObservation: current.environmentObservation,
    });
  });

  it("Scenario: 冲突 Draft 状态或未知 stateVersion 保持修复阻断", () => {
    const current = defaultSessionState("2026-07-26T00:00:00.000Z");
    const conflictingDraft = {
      enabled: true,
      runtimeMode: "advisory",
      mode: "strict",
      onboardProfileId: current.onboardProfileId,
      securityBaseline: current.securityBaseline,
      route: current.route,
      activeSkills: current.activeSkills,
      ruleDecisions: current.ruleDecisions,
      environmentObservation: current.environmentObservation,
    };

    expect(() =>
      restoreSessionState([
        { customType: SBTD_STATE_CUSTOM_TYPE, data: conflictingDraft },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
    expect(() =>
      restoreSessionState([
        {
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: { ...current, stateVersion: 2 },
        },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
  });

  it("Scenario: Compaction 状态摘要成为最新可恢复的 Session 状态", () => {
    const snapshot = {
      ...defaultSessionState("2026-07-25T00:00:00.000Z"),
      runtimeMode: "enforced" as const,
      route: "review" as const,
    };

    expect(
      restoreSessionState([
        { customType: SBTD_STATE_CUSTOM_TYPE, data: defaultSessionState() },
        {
          type: "compaction",
          preserveData: { [SBTD_STATE_COMPACTION_KEY]: snapshot },
        },
      ]),
    ).toEqual(snapshot);
  });

  it("Scenario: Route 与 Policy 变更先重观测再原子持久化", () => {
    const entries: unknown[] = [];
    const service = createStateService(
      {
        replay: () => entries,
        append: (customType, data) => {
          entries.push({ customType, data });
        },
      },
      () => "2026-07-24T00:00:00.000Z",
    );
    const observation = () => ({
      observedAt: "2026-07-24T00:00:00.000Z",
      mode: "managed" as const,
      evidence: ["selected profile requirements are present"],
      repairPath: "/sbtd status",
    });

    expect(service.setRoute("review", observation).state).toMatchObject({
      route: "review",
      environmentObservation: { mode: "managed" },
    });
    expect(service.setPolicyProfile("strict", observation).state).toMatchObject(
      {
        route: "review",
        policyProfile: "strict",
        environmentObservation: { mode: "managed" },
      },
    );
    service.recordRuleDecision(
      evaluateRuleRegistry(ruleRegistry, {
        action: "delivery",
        e2eMode: "mock-backed",
        policyProfile: "strict",
      }),
      "delivery",
      ["e2e-mode=mock-backed"],
    );
    expect(service.restore().ruleDecisions).toHaveLength(1);
    expect(
      service.setPolicyProfile("relaxed", observation).state.ruleDecisions,
    ).toEqual([]);
    expect(entries).toHaveLength(4);
  });
  it("Scenario: Book Gate 只能经过已验证的状态转换放行", () => {
    const entries: unknown[] = [];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => {
        entries.push({ customType, data });
      },
    });
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: true,
      existingBehaviorBug: true,
      dataRisk: false,
      productionPathRisk: false,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    service.recordWorkflow(classification, createBookGatePlan(classification));
    expect(() =>
      service.recordBookGateReview("legacy-change-safety", "characterized"),
    ).toThrow("must be running");
    service.startBookGate("legacy-change-safety");
    expect(
      service.recordBookGateReview("legacy-change-safety", "characterized")
        .bookGates,
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "legacy-change-safety",
          gateState: "passed",
          reviewerStatus: "characterized",
        }),
      ]),
    );
    expect(
      service.recordWorkflow(classification, createBookGatePlan(classification))
        .bookGates,
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "legacy-change-safety",
          gateState: "passed",
          reviewerStatus: "characterized",
        }),
      ]),
    );
  });

  it("Scenario: 未通过的必需 Gate 阻断阶段推进", () => {
    const entries: unknown[] = [];
    const service = createStateService(
      {
        replay: () => entries,
        append: (customType, data) => {
          entries.push({ customType, data });
        },
      },
      () => "2026-07-25T00:00:00.000Z",
    );
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: true,
      existingBehaviorBug: true,
      dataRisk: false,
      productionPathRisk: false,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    service.recordWorkflow(classification, createBookGatePlan(classification));

    expect(() => service.requestStageTransition("implementation")).toThrow(
      "Required Book Gate transition blocked",
    );

    service.startBookGate("legacy-change-safety");
    service.recordBookGateReview("legacy-change-safety", "characterized");
    service.startBookGate("refactoring");
    service.recordBookGateReview("refactoring", "proceed");

    expect(service.requestStageTransition("implementation")).toMatchObject({
      stage: {
        id: "implementation",
        stageStatus: "running",
        startedAt: "2026-07-25T00:00:00.000Z",
      },
    });
  });

  it("Scenario: 仅交付阶段要求 Release Readiness Gate", () => {
    const entries: unknown[] = [];
    const service = createStateService(
      {
        replay: () => entries,
        append: (customType, data) => {
          entries.push({ customType, data });
        },
      },
      () => "2026-07-25T00:00:00.000Z",
    );
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: true,
      existingBehaviorBug: true,
      dataRisk: false,
      productionPathRisk: true,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    service.recordWorkflow(classification, createBookGatePlan(classification));
    service.startBookGate("legacy-change-safety");
    service.recordBookGateReview("legacy-change-safety", "characterized");
    service.startBookGate("refactoring");
    service.recordBookGateReview("refactoring", "proceed");

    expect(
      service.requestStageTransition("implementation").stage,
    ).toMatchObject({
      id: "implementation",
      stageStatus: "running",
    });
    expect(() => service.requestStageTransition("delivery")).toThrow(
      "release-readiness",
    );
  });
  it("Scenario: 自动重新分类保留兼容 Gate 进度并路由所有必需 Book Gate Skill", () => {
    const entries: unknown[] = [];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => {
        entries.push({ customType, data });
      },
    });
    const classification = classifyTask({
      userVisibleBehavior: true,
      existingProductionCode: true,
      existingBehaviorBug: true,
      dataRisk: true,
      productionPathRisk: true,
      crossRepoScope: false,
      domainAmbiguity: true,
      durableRequirements: true,
    });
    service.recordWorkflow(classification, createBookGatePlan(classification));
    service.startBookGate("ddia-data-design");
    service.recordBookGateReview("ddia-data-design", "confirmed");

    const reclassified = {
      ...classification,
      reasons: [...classification.reasons, "changed-paths-observed"],
    };
    const state = service.recordWorkflow(
      reclassified,
      createBookGatePlan(reclassified),
    );

    expect(state.activeSkills).toEqual(
      expect.arrayContaining([
        "to-spec",
        "gherkin-bdd",
        "tdd",
        "book-ddd-distilled-modeling",
        "book-ddia-data-design",
        "book-legacy-change-safety",
        "book-refactoring-pass",
        "book-release-readiness",
      ]),
    );
    expect(state.bookGates).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "ddia-data-design",
          gateState: "passed",
          reviewerStatus: "confirmed",
        }),
      ]),
    );
  });
});
