import { describe, expect, it } from "vitest";
import {
  createBookGatePlan,
  recordBookGateReview,
  startBookGate,
} from "../src/gates/index.ts";
import { classifyTask } from "../src/workflow/index.ts";

describe("Feature: SBTD 运行时工作流与门禁", () => {
  it("Scenario: 开发任务生成完整 Book Gate Plan", () => {
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: true,
      existingBehaviorBug: true,
      dataRisk: true,
      productionPathRisk: true,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    const plan = createBookGatePlan(classification);

    expect(plan).toEqual([
      expect.objectContaining({
        id: "ddd-boundary",
        gateState: "not-required",
      }),
      expect.objectContaining({
        id: "ddia-data-design",
        gateState: "planned",
        plannedPhase: "before-design",
      }),
      expect.objectContaining({
        id: "legacy-change-safety",
        gateState: "planned",
        plannedPhase: "before-implementation",
      }),
      expect.objectContaining({
        id: "refactoring",
        gateState: "planned",
        plannedPhase: "before-implementation",
      }),
      expect.objectContaining({
        id: "release-readiness",
        gateState: "planned",
        plannedPhase: "after-validation",
      }),
    ]);
    expect(plan.every((gate) => gate.evidence.length > 0)).toBe(true);
  });

  it("Scenario: 仅通过对应 Reviewer 状态才能通过 Gate", () => {
    const planned = createBookGatePlan(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: false,
        existingBehaviorBug: false,
        dataRisk: true,
        productionPathRisk: false,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    );
    const running = startBookGate(planned, "ddia-data-design");
    const pending = recordBookGateReview(
      running,
      "ddia-data-design",
      "needs-design-change",
    );
    const passed = recordBookGateReview(
      pending,
      "ddia-data-design",
      "confirmed",
    );

    expect(pending[1]).toMatchObject({
      gateState: "running",
      reviewerStatus: "needs-design-change",
    });
    expect(passed[1]).toMatchObject({
      gateState: "passed",
      reviewerStatus: "confirmed",
    });
  });

  it("Scenario: Gate 不能由 planned 直接通过", () => {
    const planned = createBookGatePlan(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: true,
        existingBehaviorBug: false,
        dataRisk: false,
        productionPathRisk: false,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    );

    expect(() =>
      recordBookGateReview(planned, "refactoring", "proceed"),
    ).toThrow("must be running");
  });

  it("Scenario: Release Readiness 必须在验证后才可记录为 ready", () => {
    const plan = createBookGatePlan(
      classifyTask({
        userVisibleBehavior: false,
        existingProductionCode: false,
        existingBehaviorBug: false,
        dataRisk: false,
        productionPathRisk: true,
        crossRepoScope: false,
        domainAmbiguity: false,
        durableRequirements: false,
      }),
    );
    const running = startBookGate(plan, "release-readiness");

    expect(() =>
      recordBookGateReview(running, "release-readiness", "ready"),
    ).toThrow("requires verified validation evidence");
    expect(
      recordBookGateReview(running, "release-readiness", "ready", true),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "release-readiness",
          gateState: "passed",
          reviewerStatus: "ready",
        }),
      ]),
    );
  });
});
