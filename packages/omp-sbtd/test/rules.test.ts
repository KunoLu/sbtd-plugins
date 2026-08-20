import { describe, expect, it } from "vitest";
import {
  evaluateRuleRegistry,
  ruleRegistry,
  setRuleEnabled,
} from "../src/rules/index.ts";

describe("Feature: SBTD 运行时工作流与门禁", () => {
  it("Scenario: 非 Onboard 的 trellis init 在工具执行前被阻断", () => {
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "tool",
        toolCommand: "trellis init -u name",
        insideOnboard: false,
      }),
    ).toEqual(
      expect.objectContaining({
        decision: "block-tool",
        ruleId: "no-trellis-init-outside-onboard",
      }),
    );
  });

  it("Scenario: 可见行为缺少 BDD 在交付前被阻断", () => {
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "delivery",
        userVisibleBehavior: true,
        bddCovered: false,
      }),
    ).toEqual(
      expect.objectContaining({
        decision: "block-delivery",
        ruleId: "bdd-required-for-visible-behavior",
      }),
    );
  });
  it("Scenario: 使用 RTK 的报告型测试未验证副作用时阻断阶段", () => {
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "stage",
        reportingTestUsingRtk: true,
        rtkSideEffectsVerified: false,
      }),
    ).toMatchObject({
      decision: "block-stage",
      ruleId: "rtk-is-not-test-runner",
    });
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "stage",
        reportingTestUsingRtk: true,
        rtkSideEffectsVerified: true,
      }),
    ).toEqual({ decision: "allow" });
  });

  it("Scenario: 生产路径变更在 Release Gate 就绪前阻断交付", () => {
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "delivery",
        productionPathRisk: true,
        releaseGateReady: false,
      }),
    ).toMatchObject({
      decision: "block-delivery",
      ruleId: "release-gate-before-complete",
    });
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "delivery",
        productionPathRisk: true,
        releaseGateReady: true,
      }),
    ).toEqual({ decision: "allow" });
  });

  it("Scenario: relaxed 不降低 Route 必需门禁", () => {
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        action: "tool",
        requiredBookGatesPassed: false,
        policyProfile: "relaxed",
      }),
    ).toEqual(
      expect.objectContaining({
        decision: "block-tool",
        ruleId: "book-gate-before-edit",
      }),
    );
  });

  it("Scenario: 只有可配置 Optional Rule 可被禁用", () => {
    expect(() =>
      setRuleEnabled(ruleRegistry, "book-gate-before-edit", false),
    ).toThrow("not configurable");
    expect(
      setRuleEnabled(ruleRegistry, "mock-is-not-full-stack", false).find(
        (rule) => rule.id === "mock-is-not-full-stack",
      ),
    ).toMatchObject({ enabled: false });
  });

  it("Scenario: strict 只提升已声明的 Optional Rule", () => {
    const facts = {
      action: "delivery" as const,
      e2eMode: "mock-backed" as const,
    };
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        ...facts,
        policyProfile: "relaxed",
      }),
    ).toEqual({ decision: "allow" });
    expect(
      evaluateRuleRegistry(ruleRegistry, {
        ...facts,
        policyProfile: "strict",
      }),
    ).toMatchObject({
      decision: "interrupt",
      ruleId: "mock-is-not-full-stack",
    });
  });
});
