// Slice 4 contract tests for 08-20-omp-plugin-compatibility-decoupling.
//
// These tests encode the omp-extension-v1 Host Contract against the runtime
// seam: probe, adapter-edge payload validation, and fail-closed registration
// that does not leave a visible /sbtd command after a required subscription
// failure.
// Trace: packages/omp-sbtd/features/sbtd-control-bootstrap.feature
//   Rule: Host Contract 决定 /sbtd 注册的完整性与降级边界
//     - all three scenarios are GREEN below, plus registration fail-closed
//       and optional-event degrade coverage.
//   Rule: 宿主事件不被伪造解释且跨边界不复用
//     - "malformed event 不得被解释成批准或完成" is GREEN below.
//     - "tool approval 与 tool result 不跨 Session、turn、risk class 或
//       target 复用" and "compaction 与 Session 切换保持状态隔离" are
//       characterized GREEN for the current Session serialization seam in
//       test/runtime.test.ts and receive their full real-Host binding proof
//       in the Slice 5 Host Event integration suite.
//
// Mock Strategy: contract-backed — capability probes run against a simulated
// host surface, not a real OMP host.
//
// Slice 4 contract surface (exported from src/runtime/index.ts):
//   probeOmpExtensionV1Capabilities(host): {
//     status: "passed" | "failed" | "passed-with-diagnostics",
//     missingRequired: string[],   // required capability/event names
//     missingOptional: string[],   // optional capability/event names
//     disabledFeatures: string[],  // features degraded by optional loss
//     reasonCodes: string[],
//   }
//   validateOmpExtensionV1Event(name, payload): validated payload, or a
//     structured fail-closed rejection; a malformed or unknown event never
//     reaches handlers and is never interpreted as approval or completion.
import { describe, expect, it } from "vitest";
import { z } from "zod";
import * as runtimeSeam from "../src/runtime/index.ts";
import {
  type RuntimeControllerHandlers,
  registerRuntimeController,
} from "../src/runtime/index.ts";

// Unchecked cast: the module namespace is read as an open record so missing
// future exports surface as `undefined` and fail with the explicit messages
// below instead of a module-load error that would hide the other tests.
const seam = runtimeSeam as unknown as Record<string, unknown>;

type CapabilityAssessment = Readonly<{
  status: "passed" | "failed" | "passed-with-diagnostics";
  missingRequired: readonly string[];
  missingOptional: readonly string[];
  disabledFeatures: readonly string[];
  reasonCodes: readonly string[];
}>;

function probeCapabilities(host: unknown): CapabilityAssessment {
  const probe = seam.probeOmpExtensionV1Capabilities;
  expect(
    typeof probe,
    "Slice 4 must export probeOmpExtensionV1Capabilities from " +
      "src/runtime/index.ts backed by the single versioned " +
      "omp-extension-v1 inventory; the current seam registers " +
      "unconditionally and cannot fail closed on a missing required " +
      "capability.",
  ).toBe("function");
  // Unchecked cast: presence asserted immediately above; the call shape is
  // the Slice 4 contract documented in the file header.
  const probeFn = probe as (value: unknown) => CapabilityAssessment;
  return probeFn(host);
}

// Simulated host surfaces at the omp-extension-v1 inventory level.
const fullHost = {
  registerCommand() {},
  registerTool() {},
  on() {},
  zod: {},
};

const hostMissingRequiredEvent = {
  registerCommand() {},
  registerTool() {},
  // No `on` event subscription capability.
  zod: {},
};

const hostMissingOptionalTool = {
  registerCommand() {},
  // No optional `registerTool` capability.
  on() {},
  zod: {},
};

function stubHandlers(): RuntimeControllerHandlers {
  return {
    complete: () => [],
    handleCommand: async () => {},
    transitionStage: async () => "",
    reobserve: async () => {},
    beforeAgentStart: async () => undefined,
    beforeToolCall: async () => undefined,
    preserveCompaction: async () => undefined,
    approvalResolved: async () => {},
    toolResult: async () => {},
    turnStart: async () => {},
    turnEnd: async () => {},
    sessionStop: async () => undefined,
  };
}

describe("Feature: SBTD 控制引导 — Host Contract capability boundary", () => {
  it("Scenario: Host Contract 通过时注册完整 /sbtd", () => {
    const assessment = probeCapabilities(fullHost);
    expect(assessment.status).toBe("passed");
    expect(assessment.missingRequired).toEqual([]);
  });

  it("Scenario: 必需 capability 缺失时 fail closed", () => {
    const assessment = probeCapabilities(hostMissingRequiredEvent);
    expect(assessment.status).toBe("failed");
    expect(assessment.missingRequired.length).toBeGreaterThan(0);
    expect(assessment.reasonCodes.length).toBeGreaterThan(0);

    const commands: string[] = [];
    const tools: string[] = [];
    expect(() =>
      registerRuntimeController(
        {
          registerCommand(name: string) {
            commands.push(name);
          },
          registerTool() {
            tools.push("sbtd_workflow");
          },
          zod: z,
        } as never,
        stubHandlers(),
      ),
    ).toThrow(/omp-extension-v1 host contract failed/);
    expect(commands).toEqual([]);
    expect(tools).toEqual([]);
  });

  it("Scenario: 可选 capability 缺失时只降级相关功能", () => {
    const assessment = probeCapabilities(hostMissingOptionalTool);
    expect(assessment.status).toBe("passed-with-diagnostics");
    expect(assessment.missingRequired).toEqual([]);
    expect(assessment.missingOptional).toContain("registerTool");
    expect(assessment.disabledFeatures.length).toBeGreaterThan(0);
  });

  it("Scenario: 可选事件订阅失败时只降级相关功能", () => {
    const commands: string[] = [];
    const tools: string[] = [];
    expect(() =>
      registerRuntimeController(
        {
          registerCommand(name: string) {
            commands.push(name);
          },
          registerTool() {
            tools.push("sbtd_workflow");
          },
          zod: z,
          on(name: string) {
            if (name === "credential_disabled")
              throw new Error("host rejected optional event");
          },
        } as never,
        {
          ...stubHandlers(),
          credentialDisabled: async () => {},
        },
      ),
    ).not.toThrow();
    expect(commands).toEqual(["sbtd"]);
    expect(tools).toEqual(["sbtd_workflow"]);
  });

  it("Scenario: malformed event 不得被解释成批准或完成", async () => {
    const validateEvent = seam.validateOmpExtensionV1Event;
    expect(
      typeof validateEvent,
      "Slice 4 must export validateOmpExtensionV1Event from " +
        "src/runtime/index.ts: adapter-edge payload validation that fails " +
        "closed; the current seam forwards raw host events to handlers, " +
        "so a malformed payload could be interpreted as an approval or a " +
        "completion.",
    ).toBe("function");
    // Unchecked cast: presence asserted immediately above; the call shape
    // is the Slice 4 contract documented in the file header.
    const validate = validateEvent as (
      name: string,
      payload: unknown,
    ) => unknown;
    expect(() =>
      validate("tool_approval_resolved", { unexpected: true }),
    ).toThrow();
    expect(() => validate("unknown_host_event", {})).toThrow();
    // A payload missing the required `type` discriminator is malformed and
    // never reaches handlers — for every subscribed Session lifecycle event.
    expect(() => validate("session_start", {})).toThrow();
    expect(() => validate("session_switch", {})).toThrow();
    expect(() => validate("session_branch", {})).toThrow();
    expect(() => validate("session_tree", {})).toThrow();
    expect(() =>
      validate("session_tree", {
        type: "session_tree",
        newLeafId: null,
        oldLeafId: null,
      }),
    ).not.toThrow();
    expect(() => validate("session_stop", {})).toThrow();
    expect(() =>
      validate("session_stop", {
        type: "session_stop",
        messages: [],
        turn_id: 0,
        session_id: "s",
        stop_hook_active: false,
        signal: {},
      }),
    ).not.toThrow();

    const seenApprovals: unknown[] = [];
    const events = new Map<string, (event: unknown, ctx: unknown) => unknown>();
    registerRuntimeController(
      {
        registerCommand() {},
        registerTool() {},
        zod: z,
        on(name: string, handler: (event: unknown, ctx: unknown) => unknown) {
          events.set(name, handler);
        },
      } as never,
      {
        ...stubHandlers(),
        approvalResolved: async (event) => {
          seenApprovals.push(event);
        },
      },
    );
    await expect(
      Promise.resolve(
        events.get("tool_approval_resolved")?.(
          { unexpected: true },
          { sessionManager: {} },
        ),
      ),
    ).rejects.toThrow();
    expect(seenApprovals).toEqual([]);
  });

  it("Scenario: credential_disabled 缺少 disabledCause own key 时 fail closed", () => {
    const validate = seam.validateOmpExtensionV1Event as (
      name: string,
      payload: unknown,
    ) => unknown;
    expect(() =>
      validate("credential_disabled", {
        type: "credential_disabled",
        provider: "openai",
      }),
    ).toThrow(/missing-key:disabledCause/);
    const withUnreadCause = Object.defineProperties(
      { type: "credential_disabled", provider: "openai" },
      {
        disabledCause: {
          enumerable: true,
          get: (): never => {
            throw new Error("disabledCause must not be read");
          },
        },
      },
    );
    expect(validate("credential_disabled", withUnreadCause)).toEqual({
      type: "credential_disabled",
      provider: "openai",
    });
  });

  it("Scenario: z.unknown() 必填键缺失时 fail closed", () => {
    // Review fix (accepted finding #5): `z.unknown()` accepts `undefined`,
    // so a *missing* required key slips past the schema unless the adapter
    // edge enforces own-property presence. The pinned 17.3.5 Host types
    // declare these keys as required (tool_result.details may hold
    // `undefined`, but the key itself must be present).
    const validate = seam.validateOmpExtensionV1Event as (
      name: string,
      payload: unknown,
    ) => unknown;
    expect(typeof validate).toBe("function");
    expect(() =>
      validate("tool_result", {
        type: "tool_result",
        toolCallId: "c",
        toolName: "bash",
        input: {},
        content: [],
        isError: false,
        // details key missing
      }),
    ).toThrow();
    expect(() =>
      validate("turn_end", {
        type: "turn_end",
        turnIndex: 0,
        toolResults: [],
        // message key missing
      }),
    ).toThrow();
    expect(() =>
      validate("session_stop", {
        type: "session_stop",
        messages: [],
        turn_id: 0,
        session_id: "s",
        stop_hook_active: false,
        // signal key missing
      }),
    ).toThrow();
    // Presence, not value: an explicit `undefined` value for
    // tool_result.details is the pinned Host shape and stays valid.
    expect(() =>
      validate("tool_result", {
        type: "tool_result",
        toolCallId: "c",
        toolName: "write",
        input: {},
        content: [],
        isError: false,
        details: undefined,
      }),
    ).not.toThrow();
  });

  it("Scenario: 必需事件订阅失败时不留下已注册的 /sbtd", () => {
    const commands: string[] = [];
    const tools: string[] = [];
    const events: string[] = [];
    expect(() =>
      registerRuntimeController(
        {
          registerCommand(name: string) {
            commands.push(name);
          },
          registerTool() {
            tools.push("sbtd_workflow");
          },
          zod: z,
          on(name: string) {
            events.push(name);
            if (name === "tool_result")
              throw new Error("host rejected required event");
          },
        } as never,
        stubHandlers(),
      ),
    ).toThrow();
    expect(commands).toEqual([]);
    expect(tools).toEqual([]);
    expect(events).toContain("session_start");
    expect(events).toContain("tool_result");
  });

  it("Scenario: 必需事件订阅失败时回滚已订阅事件", () => {
    const commands: string[] = [];
    const removed: string[] = [];
    expect(() =>
      registerRuntimeController(
        {
          registerCommand(name: string) {
            commands.push(name);
          },
          registerTool() {},
          zod: z,
          on(name: string) {
            if (name === "tool_result")
              throw new Error("host rejected required event");
          },
          off(name: string) {
            removed.push(name);
          },
        } as never,
        stubHandlers(),
      ),
    ).toThrow();
    expect(commands).toEqual([]);
    expect(removed).toContain("session_start");
    expect(removed).toContain("tool_approval_resolved");
    expect(removed).not.toContain("tool_result");
  });
});
