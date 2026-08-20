import type {
  BeforeAgentStartEvent,
  BeforeAgentStartEventResult,
  CredentialDisabledEvent,
  ExtensionAPI,
  ExtensionContext,
  SessionCompactingEvent,
  SessionCompactingResult,
  SessionStopEvent,
  SessionStopEventResult,
  ToolApprovalResolvedEvent,
  ToolCallEvent,
  ToolCallEventResult,
  ToolResultEvent,
  TurnEndEvent,
  TurnStartEvent,
} from "@oh-my-pi/pi-coding-agent";
import { type WorkflowStageId, workflowStageIds } from "../state/index.js";

export interface RuntimeControllerHandlers {
  readonly complete: (prefix: string) => {
    readonly value: string;
    readonly label: string;
  }[];
  readonly handleCommand: (
    args: string,
    ctx: ExtensionContext,
  ) => Promise<void>;
  readonly transitionStage: (
    stageId: WorkflowStageId,
    ctx: ExtensionContext,
  ) => Promise<string>;
  readonly reobserve: (event: unknown, ctx: ExtensionContext) => Promise<void>;
  readonly beforeAgentStart: (
    event: BeforeAgentStartEvent,
    ctx: ExtensionContext,
  ) => Promise<BeforeAgentStartEventResult | undefined>;
  readonly beforeToolCall: (
    event: ToolCallEvent,
    ctx: ExtensionContext,
  ) => Promise<ToolCallEventResult | undefined>;
  readonly preserveCompaction: (
    event: SessionCompactingEvent,
    ctx: ExtensionContext,
  ) => Promise<SessionCompactingResult | undefined>;
  readonly approvalResolved: (
    event: ToolApprovalResolvedEvent,
    ctx: ExtensionContext,
  ) => Promise<void>;
  readonly toolResult: (
    event: ToolResultEvent,
    ctx: ExtensionContext,
  ) => Promise<void>;
  readonly turnStart: (
    event: TurnStartEvent,
    ctx: ExtensionContext,
  ) => Promise<void>;
  readonly turnEnd: (
    event: TurnEndEvent,
    ctx: ExtensionContext,
  ) => Promise<void>;
  readonly sessionStop: (
    event: SessionStopEvent,
    ctx: ExtensionContext,
  ) => Promise<SessionStopEventResult | undefined>;
  readonly credentialDisabled?: (
    event: CredentialDisabledEvent,
    ctx: ExtensionContext,
  ) => Promise<void>;
}

const anonymousSessionKeys = new WeakMap<object, string>();
let nextAnonymousSessionKey = 0;

function sessionKeyFor(ctx: ExtensionContext): string {
  const sessionId = ctx.sessionManager.getSessionId?.();
  if (sessionId !== undefined) return `session:${sessionId}`;
  const manager = ctx.sessionManager as object;
  let key = anonymousSessionKeys.get(manager);
  if (key === undefined) {
    key = `anonymous:${nextAnonymousSessionKey++}`;
    anonymousSessionKeys.set(manager, key);
  }
  return key;
}

export function registerRuntimeController(
  pi: ExtensionAPI,
  handlers: RuntimeControllerHandlers,
): void {
  const mutationTails = new Map<string, Promise<void>>();
  const serialize = <T>(
    ctx: ExtensionContext,
    operation: () => Promise<T>,
  ): Promise<T> => {
    const sessionId = sessionKeyFor(ctx);
    const previous = mutationTails.get(sessionId) ?? Promise.resolve();
    const result = previous.then(operation, operation);
    const settled = result.then(
      () => undefined,
      () => undefined,
    );
    mutationTails.set(sessionId, settled);
    void settled.finally(() => {
      if (mutationTails.get(sessionId) === settled)
        mutationTails.delete(sessionId);
    });
    return result;
  };
  pi.registerCommand("sbtd", {
    description: "SBTD control, status, and safe AGENTS onboarding.",
    getArgumentCompletions: handlers.complete,
    handler: (args, ctx) =>
      serialize(ctx, () => handlers.handleCommand(args, ctx)),
  });
  if (typeof pi.registerTool === "function")
    pi.registerTool({
      name: "sbtd_workflow",
      label: "SBTD Workflow",
      description:
        "Request a workflow stage transition after the Session's required Book Gates pass.",
      parameters: pi.zod
        .object({
          stageId: pi.zod.enum(workflowStageIds),
        })
        .strict(),
      approval: "write",
      async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
        return serialize(ctx, async () => ({
          content: [
            {
              type: "text",
              text: await handlers.transitionStage(params.stageId, ctx),
            },
          ],
        }));
      },
    });
  pi.on("session_start", (event, ctx) =>
    serialize(ctx, () => handlers.reobserve(event, ctx)),
  );
  pi.on("session_switch", (event, ctx) =>
    serialize(ctx, () => handlers.reobserve(event, ctx)),
  );
  pi.on("session_branch", (event, ctx) =>
    serialize(ctx, () => handlers.reobserve(event, ctx)),
  );
  pi.on("session_tree", (event, ctx) =>
    serialize(ctx, () => handlers.reobserve(event, ctx)),
  );
  pi.on("before_agent_start", (event, ctx) =>
    serialize(ctx, () => handlers.beforeAgentStart(event, ctx)),
  );
  pi.on("session.compacting", (event, ctx) =>
    serialize(ctx, () => handlers.preserveCompaction(event, ctx)),
  );
  pi.on("tool_call", (event, ctx) =>
    serialize(ctx, () => handlers.beforeToolCall(event, ctx)),
  );
  pi.on("tool_approval_resolved", (event, ctx) =>
    serialize(ctx, () => handlers.approvalResolved(event, ctx)),
  );
  pi.on("tool_result", (event, ctx) =>
    serialize(ctx, () => handlers.toolResult(event, ctx)),
  );
  pi.on("turn_start", (event, ctx) =>
    serialize(ctx, () => handlers.turnStart(event, ctx)),
  );
  pi.on("turn_end", (event, ctx) =>
    serialize(ctx, () => handlers.turnEnd(event, ctx)),
  );
  pi.on("session_stop", (event, ctx) =>
    serialize(ctx, () => handlers.sessionStop(event, ctx)),
  );
  const credentialDisabled = handlers.credentialDisabled;
  if (credentialDisabled !== undefined)
    pi.on("credential_disabled", (event, ctx) =>
      serialize(ctx, () => credentialDisabled(event, ctx)),
    );
}
