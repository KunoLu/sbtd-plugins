import { describe, expect, it } from "vitest";
import { z } from "zod";
import {
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

    const pendingA = events.get("session_start")?.({}, contextFor("session-a"));
    const pendingB = events.get("session_start")?.({}, contextFor("session-b"));

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

    const pendingA = events.get("session_start")?.({}, contextA);
    const pendingB = events.get("session_start")?.({}, contextB);

    await expect(Promise.resolve()).resolves.toBeUndefined();
    expect(started).toEqual(["a", "b"]);
    first.resolve();
    await Promise.all([pendingA, pendingB]);
  });
});
