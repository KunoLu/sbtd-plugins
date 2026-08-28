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
import {
  type OmpExtensionV1CapabilityAssessment,
  probeOmpExtensionV1Capabilities,
  validateOmpExtensionV1Event,
} from "./omp-extension-v1.js";

// Slice 4 (08-20-omp-plugin-compatibility-decoupling): this file stays the
// single public Host seam; the versioned omp-extension-v1 inventory, probe,
// and adapter-edge validator are re-exported from the sibling module so the
// runtime probe and the Slice 5 Host Event suite share one inventory.
export {
  type OmpExtensionV1CapabilityAssessment,
  type OmpExtensionV1EventName,
  type OmpExtensionV1EventPayloadMap,
  OmpExtensionV1EventRejection,
  type OmpExtensionV1OptionalCapability,
  type OmpExtensionV1OptionalEvent,
  type OmpExtensionV1ProbeStatus,
  type OmpExtensionV1RequiredCapability,
  type OmpExtensionV1RequiredEvent,
  ompExtensionV1Inventory,
  probeOmpExtensionV1Capabilities,
  validateOmpExtensionV1Event,
} from "./omp-extension-v1.js";

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

function hostEventUnsubscriber(
  host: object,
): ((name: string, handler: unknown) => void) | undefined {
  const record = host as Record<string, unknown>;
  for (const methodName of ["off", "removeListener"] as const) {
    const method = record[methodName];
    if (typeof method === "function")
      return (name, handler) => {
        (method as (eventName: string, listener: unknown) => void).call(
          host,
          name,
          handler,
        );
      };
  }
  return undefined;
}

function rollbackHostEventSubscriptions(
  unsubscribe: ((name: string, handler: unknown) => void) | undefined,
  subscriptions: readonly Readonly<{ name: string; handler: unknown }>[],
): void {
  if (unsubscribe === undefined) return;
  for (const subscription of [...subscriptions].reverse()) {
    try {
      unsubscribe(subscription.name, subscription.handler);
    } catch {
      // Best-effort cleanup only; the required-subscription error is rethrown.
    }
  }
}

export function registerRuntimeController(
  pi: ExtensionAPI,
  handlers: RuntimeControllerHandlers,
): void {
  // Fail closed before any host registration: a Host missing a required
  // omp-extension-v1 capability or required-event delivery (`on`) never gets
  // a /sbtd command, tool, or event subscription, so no misleading ready or
  // partial-registration state can be observed.
  const assessment: OmpExtensionV1CapabilityAssessment =
    probeOmpExtensionV1Capabilities(pi);
  if (assessment.status === "failed")
    throw new Error(
      `omp-extension-v1 host contract failed; registration refused: ${assessment.reasonCodes.join(", ")}`,
    );
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
  // Visible /sbtd registration waits until every required event
  // subscription succeeds. Optional credential_disabled cannot fail the
  // required surface. registerTool runs before registerCommand so a later
  // host throw cannot leave a misleading ready state. Public ExtensionAPI
  // has no event `off`; rollback uses off/removeListener when present.
  const subscriptions: { name: string; handler: unknown }[] = [];
  const subscribeRequired = (
    name: string,
    handler: (event: never, ctx: ExtensionContext) => unknown,
  ): void => {
    (
      pi.on as (
        eventName: string,
        listener: (event: never, ctx: ExtensionContext) => unknown,
      ) => void
    )(name, handler);
    subscriptions.push({ name, handler });
  };
  try {
    subscribeRequired("session_start", (event, ctx) =>
      serialize(ctx, () =>
        handlers.reobserve(
          validateOmpExtensionV1Event("session_start", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("session_switch", (event, ctx) =>
      serialize(ctx, () =>
        handlers.reobserve(
          validateOmpExtensionV1Event("session_switch", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("session_branch", (event, ctx) =>
      serialize(ctx, () =>
        handlers.reobserve(
          validateOmpExtensionV1Event("session_branch", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("session_tree", (event, ctx) =>
      serialize(ctx, () =>
        handlers.reobserve(
          validateOmpExtensionV1Event("session_tree", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("before_agent_start", (event, ctx) =>
      serialize(ctx, () =>
        handlers.beforeAgentStart(
          validateOmpExtensionV1Event("before_agent_start", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("session.compacting", (event, ctx) =>
      serialize(ctx, () =>
        handlers.preserveCompaction(
          validateOmpExtensionV1Event("session.compacting", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("tool_call", (event, ctx) =>
      serialize(ctx, () =>
        handlers.beforeToolCall(
          validateOmpExtensionV1Event("tool_call", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("tool_approval_resolved", (event, ctx) =>
      serialize(ctx, () =>
        handlers.approvalResolved(
          validateOmpExtensionV1Event("tool_approval_resolved", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("tool_result", (event, ctx) =>
      serialize(ctx, () =>
        handlers.toolResult(
          validateOmpExtensionV1Event("tool_result", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("turn_start", (event, ctx) =>
      serialize(ctx, () =>
        handlers.turnStart(
          validateOmpExtensionV1Event("turn_start", event),
          ctx,
        ),
      ),
    );
    subscribeRequired("turn_end", (event, ctx) =>
      serialize(ctx, () =>
        handlers.turnEnd(validateOmpExtensionV1Event("turn_end", event), ctx),
      ),
    );
    subscribeRequired("session_stop", (event, ctx) =>
      serialize(ctx, () =>
        handlers.sessionStop(
          validateOmpExtensionV1Event("session_stop", event),
          ctx,
        ),
      ),
    );
  } catch (error) {
    rollbackHostEventSubscriptions(hostEventUnsubscriber(pi), subscriptions);
    throw error;
  }
  const credentialDisabled = handlers.credentialDisabled;
  if (credentialDisabled !== undefined) {
    try {
      pi.on("credential_disabled", (event, ctx) =>
        serialize(ctx, () =>
          credentialDisabled(
            validateOmpExtensionV1Event("credential_disabled", event),
            ctx,
          ),
        ),
      );
    } catch {
      // Optional event only: rejecting credential_disabled degrades
      // revocation sync and must not block /sbtd ready state.
    }
  }
  // Optional-capability loss degrades only the named feature: no registerTool
  // means no sbtd_workflow tool; every command and required event stays.
  if (!assessment.missingOptional.includes("registerTool"))
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
  pi.registerCommand("sbtd", {
    description: "SBTD control, status, and safe AGENTS onboarding.",
    getArgumentCompletions: handlers.complete,
    handler: (args, ctx) =>
      serialize(ctx, () => handlers.handleCommand(args, ctx)),
  });
}
