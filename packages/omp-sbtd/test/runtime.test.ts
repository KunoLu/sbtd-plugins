import { describe, expect, it } from "vitest";
import { z } from "zod";
import {
  ompExtensionV1Inventory,
  type RuntimeControllerHandlers,
  registerRuntimeController,
} from "../src/runtime/index.ts";

describe("Feature: Runtime Controller session isolation", () => {
  it("Scenario: Session A's pending mutation does not block Session B", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const started: string[] = [];
    const sessionA = Promise.withResolvers<void>();
    const handlers = {
      complete: () => [],
      handleCommand: async () => {},
      transitionStage: async () => "",
      reobserve: async (
        _event: unknown,
        ctx: { sessionManager: { getSessionId: () => string } },
      ) => {
        const sessionId = ctx.sessionManager.getSessionId();
        started.push(sessionId);
        if (sessionId === "session-a") await sessionA.promise;
      },
      beforeAgentStart: async () => undefined,
      beforeToolCall: async () => undefined,
      preserveCompaction: async () => undefined,
      approvalResolved: async () => {},
      toolResult: async () => {},
      turnStart: async () => {},
      turnEnd: async () => {},
      sessionStop: async () => undefined,
    } satisfies RuntimeControllerHandlers;
    registerRuntimeController(
      {
        registerCommand() {},
        zod: z,
        registerTool() {},
        on(
          name: string,
          handler: (event: unknown, ctx: unknown) => Promise<unknown>,
        ) {
          events.set(name, handler);
        },
      } as never,
      handlers,
    );
    const contextFor = (sessionId: string) => ({
      sessionManager: { getSessionId: () => sessionId },
    });

    // The adapter edge now validates payloads fail-closed (Slice 4); the
    // isolation contract under test is Session serialization, so the stub
    // host delivers a schema-valid session_start payload.
    const pendingA = events.get("session_start")?.(
      { type: "session_start" },
      contextFor("session-a"),
    );
    const pendingB = events.get("session_start")?.(
      { type: "session_start" },
      contextFor("session-b"),
    );

    await expect(Promise.resolve()).resolves.toBeUndefined();
    expect(started).toEqual(["session-a", "session-b"]);
    sessionA.resolve();
    await Promise.all([pendingA, pendingB]);
  });

  it("Scenario: 无稳定 Session ID 的 Context 不共享串行队列", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const started: string[] = [];
    const first = Promise.withResolvers<void>();
    const contextA = { sessionManager: {} };
    const contextB = { sessionManager: {} };
    const handlers = {
      complete: () => [],
      handleCommand: async () => {},
      transitionStage: async () => "",
      reobserve: async (_event: unknown, ctx: unknown) => {
        started.push(ctx === contextA ? "a" : "b");
        if (ctx === contextA) await first.promise;
      },
      beforeAgentStart: async () => undefined,
      beforeToolCall: async () => undefined,
      preserveCompaction: async () => undefined,
      approvalResolved: async () => {},
      toolResult: async () => {},
      turnStart: async () => {},
      turnEnd: async () => {},
      sessionStop: async () => undefined,
    } satisfies RuntimeControllerHandlers;
    registerRuntimeController(
      {
        registerCommand() {},
        zod: z,
        registerTool() {},
        on(
          name: string,
          handler: (event: unknown, ctx: unknown) => Promise<unknown>,
        ) {
          events.set(name, handler);
        },
      } as never,
      handlers,
    );

    const pendingA = events.get("session_start")?.(
      { type: "session_start" },
      contextA,
    );
    const pendingB = events.get("session_start")?.(
      { type: "session_start" },
      contextB,
    );

    await expect(Promise.resolve()).resolves.toBeUndefined();
    expect(started).toEqual(["a", "b"]);
    first.resolve();
    await Promise.all([pendingA, pendingB]);
  });
});

// Slice 1 characterization kept as the registration-surface lock. Slice 4
// now owns the versioned omp-extension-v1 inventory; these scenarios assert
// the live seam against that inventory so required events cannot drift.
describe("Feature: SBTD 控制引导 — host registration characterization", () => {
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

  function recordingHost(options?: { withRegisterTool?: boolean }) {
    const commands: string[] = [];
    const tools: string[] = [];
    const events = new Map<string, unknown>();
    const host = {
      registerCommand(name: string) {
        commands.push(name);
      },
      zod: z,
      ...(options?.withRegisterTool === false
        ? {}
        : {
            registerTool(tool: { name: string }) {
              tools.push(tool.name);
            },
          }),
      on(name: string, handler: unknown) {
        events.set(name, handler);
      },
    };
    return { host, commands, tools, events };
  }

  it("Scenario: Host Contract 通过时注册完整 /sbtd — characterization: 当前注册面", () => {
    const { host, commands, tools, events } = recordingHost();
    registerRuntimeController(host as never, {
      ...stubHandlers(),
      credentialDisabled: async () => {},
    });
    expect(commands).toEqual(["sbtd"]);
    expect(tools).toEqual(["sbtd_workflow"]);
    expect([...events.keys()].sort()).toEqual(
      [...ompExtensionV1Inventory.requiredEvents, "credential_disabled"].sort(),
    );
  });

  it("Scenario: 可选 capability 缺失时只降级相关功能 — characterization: registerTool 缺失即跳过工具注册", () => {
    const { host, commands, tools, events } = recordingHost({
      withRegisterTool: false,
    });
    registerRuntimeController(host as never, stubHandlers());
    expect(commands).toEqual(["sbtd"]);
    expect(tools).toEqual([]);
    expect(events.has("credential_disabled")).toBe(false);
    expect([...events.keys()].sort()).toEqual(
      [...ompExtensionV1Inventory.requiredEvents].sort(),
    );
  });
});
