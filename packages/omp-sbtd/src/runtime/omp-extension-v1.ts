// Slice 4 (08-20-omp-plugin-compatibility-decoupling): the single versioned
// omp-extension-v1 Host capability/event inventory, the capability probe, and
// the adapter-edge payload validator. `src/runtime/index.ts` remains the
// public Host seam and re-exports this surface; Slice 5's real Host Event
// integration suite must reuse the same inventory instead of declaring a
// parallel one.
//
// Trace: packages/omp-sbtd/features/sbtd-control-bootstrap.feature
//   Rule: Host Contract 决定 /sbtd 注册的完整性与降级边界
//   Rule: 宿主事件不被伪造解释且跨边界不复用
//
// The event schemas mirror the pinned @oh-my-pi/pi-coding-agent 17.3.5 public
// event types (extensibility/shared-events.ts, extensibility/extensions/
// types.ts). Every schema is `.strict()` with a required `type` literal
// matching the event name: an unknown event name, a missing/wrong
// discriminator, a missing required field, or an unknown key is malformed and
// never reaches a handler. Fields that are optional in the OMP public types
// stay optional; no extra required fields are invented. Zod is the runtime
// source of truth per .trellis/spec/backend/type-safety.md; reason codes are
// stable and carry no profile, token, transcript, or payload content.
import type {
  BeforeAgentStartEvent,
  CredentialDisabledEvent,
  SessionBranchEvent,
  SessionCompactingEvent,
  SessionStartEvent,
  SessionStopEvent,
  SessionSwitchEvent,
  SessionTreeEvent,
  ToolApprovalResolvedEvent,
  ToolCallEvent,
  ToolResultEvent,
  TurnEndEvent,
  TurnStartEvent,
} from "@oh-my-pi/pi-coding-agent";
import { z } from "zod";

/**
 * The versioned omp-extension-v1 Host inventory. Required capabilities and
 * events are fail-closed; optional capability loss degrades only the named
 * feature. `requiredEvents` must stay aligned with `REQUIRED_HOST_EVENTS` in
 * `test/runtime.test.ts`.
 */
export const ompExtensionV1Inventory = {
  version: "omp-extension-v1",
  requiredCapabilities: ["registerCommand", "on", "zod"],
  optionalCapabilities: ["registerTool"],
  requiredEvents: [
    "session_start",
    "session_switch",
    "session_branch",
    "session_tree",
    "before_agent_start",
    "session.compacting",
    "tool_call",
    "tool_approval_resolved",
    "tool_result",
    "turn_start",
    "turn_end",
    "session_stop",
  ],
  optionalEvents: ["credential_disabled"],
} as const;

export type OmpExtensionV1RequiredCapability =
  (typeof ompExtensionV1Inventory.requiredCapabilities)[number];
export type OmpExtensionV1OptionalCapability =
  (typeof ompExtensionV1Inventory.optionalCapabilities)[number];
export type OmpExtensionV1RequiredEvent =
  (typeof ompExtensionV1Inventory.requiredEvents)[number];
export type OmpExtensionV1OptionalEvent =
  (typeof ompExtensionV1Inventory.optionalEvents)[number];

export type OmpExtensionV1ProbeStatus =
  | "passed"
  | "failed"
  | "passed-with-diagnostics";

export interface OmpExtensionV1CapabilityAssessment {
  readonly status: OmpExtensionV1ProbeStatus;
  readonly missingRequired: readonly string[];
  readonly missingOptional: readonly string[];
  readonly disabledFeatures: readonly string[];
  readonly reasonCodes: readonly string[];
}

/**
 * Features degraded by each optional capability loss. The workflow tool is
 * the only currently declared optional-capability-dependent feature.
 */
const optionalCapabilityFeatures: Readonly<
  Record<OmpExtensionV1OptionalCapability, readonly string[]>
> = {
  registerTool: ["sbtd_workflow tool registration"],
};

function hostRecord(host: unknown): Readonly<Record<string, unknown>> {
  if (typeof host !== "object" && typeof host !== "function") return {};
  if (host === null) return {};
  return host as Record<string, unknown>;
}

function hasCapability(
  host: Readonly<Record<string, unknown>>,
  capability:
    | OmpExtensionV1RequiredCapability
    | OmpExtensionV1OptionalCapability,
): boolean {
  const value = host[capability];
  // `zod` is the injected schema-builder namespace; capabilities that carry
  // host behavior (`registerCommand`, `on`, `registerTool`) must be callable.
  if (capability === "zod")
    return (
      (typeof value === "object" && value !== null) ||
      typeof value === "function"
    );
  return typeof value === "function";
}

/**
 * Assess a Host surface against the omp-extension-v1 inventory. Event
 * availability is contract-bound to the `on` subscription capability: without
 * `on`, every required event is undeliverable and is reported missing; with
 * `on`, an omp-extension-v1 Host is contracted to emit the required events.
 */
export function probeOmpExtensionV1Capabilities(
  host: unknown,
): OmpExtensionV1CapabilityAssessment {
  const record = hostRecord(host);
  const missingRequired: string[] = [];
  const missingOptional: string[] = [];
  const disabledFeatures: string[] = [];
  const reasonCodes: string[] = [];
  for (const capability of ompExtensionV1Inventory.requiredCapabilities) {
    if (hasCapability(record, capability)) continue;
    missingRequired.push(capability);
    reasonCodes.push(`missing-required-capability:${capability}`);
  }
  if (typeof record.on !== "function") {
    for (const event of ompExtensionV1Inventory.requiredEvents) {
      missingRequired.push(event);
      reasonCodes.push(`missing-required-event:${event}`);
    }
  }
  for (const capability of ompExtensionV1Inventory.optionalCapabilities) {
    if (hasCapability(record, capability)) continue;
    missingOptional.push(capability);
    reasonCodes.push(`missing-optional-capability:${capability}`);
    disabledFeatures.push(...optionalCapabilityFeatures[capability]);
  }
  const status: OmpExtensionV1ProbeStatus =
    missingRequired.length > 0
      ? "failed"
      : missingOptional.length > 0
        ? "passed-with-diagnostics"
        : "passed";
  return {
    status,
    missingRequired,
    missingOptional,
    disabledFeatures,
    reasonCodes,
  };
}

/** Payload types for each omp-extension-v1 event the Plugin subscribes to. */
export interface OmpExtensionV1EventPayloadMap {
  readonly session_start: SessionStartEvent;
  readonly session_switch: SessionSwitchEvent;
  readonly session_branch: SessionBranchEvent;
  readonly session_tree: SessionTreeEvent;
  readonly before_agent_start: BeforeAgentStartEvent;
  readonly "session.compacting": SessionCompactingEvent;
  readonly tool_call: ToolCallEvent;
  readonly tool_approval_resolved: ToolApprovalResolvedEvent;
  readonly tool_result: ToolResultEvent;
  readonly turn_start: TurnStartEvent;
  readonly turn_end: TurnEndEvent;
  readonly session_stop: SessionStopEvent;
  readonly credential_disabled: CredentialDisabledEvent;
}

export type OmpExtensionV1EventName = keyof OmpExtensionV1EventPayloadMap;

const sessionSwitchReasons = ["new", "resume", "fork", "handoff"] as const;

/**
 * Adapter-edge schemas for the pinned omp-extension-v1 event shapes. Complex
 * nested values the Plugin never inspects structurally (messages, tool input,
 * signals) are validated for presence, not deep content; deep validation of
 * Host-owned structures is the Slice 5 Host Event suite's job.
 */
const ompExtensionV1EventSchemas: Readonly<
  Record<OmpExtensionV1EventName, z.ZodType<unknown>>
> = {
  session_start: z.object({ type: z.literal("session_start") }).strict(),
  session_switch: z
    .object({
      type: z.literal("session_switch"),
      reason: z.enum(sessionSwitchReasons),
      previousSessionFile: z.string().optional(),
    })
    .strict(),
  session_branch: z
    .object({
      type: z.literal("session_branch"),
      previousSessionFile: z.string().optional(),
    })
    .strict(),
  session_tree: z
    .object({
      type: z.literal("session_tree"),
      newLeafId: z.string().nullable(),
      oldLeafId: z.string().nullable(),
      summaryEntry: z.unknown().optional(),
      fromExtension: z.boolean().optional(),
    })
    .strict(),
  before_agent_start: z
    .object({
      type: z.literal("before_agent_start"),
      prompt: z.string(),
      images: z.array(z.unknown()).optional(),
      systemPrompt: z.array(z.string()),
    })
    .strict(),
  "session.compacting": z
    .object({
      type: z.literal("session.compacting"),
      sessionId: z.string(),
      messages: z.array(z.unknown()),
    })
    .strict(),
  tool_call: z
    .object({
      type: z.literal("tool_call"),
      toolCallId: z.string(),
      toolName: z.string(),
      input: z.record(z.string(), z.unknown()),
    })
    .strict(),
  tool_approval_resolved: z
    .object({
      type: z.literal("tool_approval_resolved"),
      sessionId: z.string(),
      toolCallId: z.string(),
      toolName: z.string(),
      approved: z.boolean(),
      reason: z.string().optional(),
    })
    .strict(),
  tool_result: z
    .object({
      type: z.literal("tool_result"),
      toolCallId: z.string(),
      toolName: z.string(),
      input: z.record(z.string(), z.unknown()),
      content: z.array(z.unknown()),
      isError: z.boolean(),
      details: z.unknown(),
    })
    .strict(),
  turn_start: z
    .object({
      type: z.literal("turn_start"),
      turnIndex: z.number(),
      timestamp: z.number(),
    })
    .strict(),
  turn_end: z
    .object({
      type: z.literal("turn_end"),
      turnIndex: z.number(),
      message: z.unknown(),
      toolResults: z.array(z.unknown()),
    })
    .strict(),
  session_stop: z
    .object({
      type: z.literal("session_stop"),
      messages: z.array(z.unknown()),
      turn_id: z.number(),
      last_assistant_message: z.unknown().optional(),
      session_id: z.string(),
      session_file: z.string().optional(),
      stop_hook_active: z.boolean(),
      signal: z.unknown(),
    })
    .strict(),
  // Never schema-parse `disabledCause`: that field is sensitive Host text.
  // Projection is in `projectCredentialDisabled` and reads only type/provider.
  credential_disabled: z.never(),
};

/**
 * Keys the pinned 17.3.5 Host types declare as required but whose schema type
 * is `z.unknown()` — which accepts `undefined`, so the schema alone cannot
 * require the key's *presence* (tool_result.details may hold `undefined`,
 * but the key itself must exist on the payload). `validateOmpExtensionV1Event`
 * enforces own-property presence for exactly these keys.
 */
const requiredPresentKeys: Partial<
  Record<OmpExtensionV1EventName, readonly string[]>
> = {
  tool_result: ["details"],
  turn_end: ["message"],
  session_stop: ["signal"],
};

/**
 * Fail-closed rejection of a malformed or unknown Host event. Reason codes
 * are stable identifiers only; payload content is never echoed into the
 * message or the code.
 */
export class OmpExtensionV1EventRejection extends Error {
  readonly eventName: string;
  readonly reasonCode: string;
  constructor(eventName: string, reasonCode: string) {
    super(
      `${ompExtensionV1Inventory.version} rejected event "${eventName}": ${reasonCode}`,
    );
    this.name = "OmpExtensionV1EventRejection";
    this.eventName = eventName;
    this.reasonCode = reasonCode;
  }
}

function payloadReasonCode(error: z.ZodError): string {
  const issue = error.issues[0];
  if (issue === undefined) return "invalid-event-payload";
  return `invalid-event-payload:${issue.code}`;
}

function ownDataString(payload: object, key: string): string | undefined {
  if (!Object.hasOwn(payload, key)) return undefined;
  const desc = Object.getOwnPropertyDescriptor(payload, key);
  if (desc === undefined || !("value" in desc)) return undefined;
  return typeof desc.value === "string" ? desc.value : undefined;
}

function projectCredentialDisabled(payload: unknown): {
  readonly type: "credential_disabled";
  readonly provider: string;
} {
  try {
    if (typeof payload !== "object" || payload === null)
      throw new OmpExtensionV1EventRejection(
        "credential_disabled",
        "invalid-event-payload:invalid_type",
      );
    const allowed = new Set(["type", "provider", "disabledCause"]);
    for (const key of Reflect.ownKeys(payload)) {
      if (typeof key !== "string" || !allowed.has(key))
        throw new OmpExtensionV1EventRejection(
          "credential_disabled",
          "invalid-event-payload:unrecognized_keys",
        );
    }
    if (Object.hasOwn(payload, "type")) {
      const type = ownDataString(payload, "type");
      if (type !== "credential_disabled")
        throw new OmpExtensionV1EventRejection(
          "credential_disabled",
          "invalid-event-payload:invalid_value",
        );
    }
    const provider = ownDataString(payload, "provider");
    if (provider === undefined || provider.length === 0)
      throw new OmpExtensionV1EventRejection(
        "credential_disabled",
        "invalid-event-payload:missing-key:provider",
      );
    if (!Object.hasOwn(payload, "disabledCause"))
      throw new OmpExtensionV1EventRejection(
        "credential_disabled",
        "invalid-event-payload:missing-key:disabledCause",
      );
    return { type: "credential_disabled", provider };
  } catch (error) {
    if (error instanceof OmpExtensionV1EventRejection) throw error;
    throw new OmpExtensionV1EventRejection(
      "credential_disabled",
      "invalid-event-payload:parse-exception",
    );
  }
}

/**
 * Validate one Host event payload at the adapter edge. A malformed payload or
 * an unknown event name throws `OmpExtensionV1EventRejection`; the value never
 * reaches a handler and is never interpreted as an approval or a completion.
 */
export function validateOmpExtensionV1Event<K extends OmpExtensionV1EventName>(
  name: K,
  payload: unknown,
): OmpExtensionV1EventPayloadMap[K];
export function validateOmpExtensionV1Event(
  name: string,
  payload: unknown,
): unknown;
export function validateOmpExtensionV1Event(
  name: string,
  payload: unknown,
): unknown {
  if (name === "credential_disabled") return projectCredentialDisabled(payload);
  const schema = (
    ompExtensionV1EventSchemas as Readonly<Record<string, z.ZodType<unknown>>>
  )[name];
  if (schema === undefined)
    throw new OmpExtensionV1EventRejection(name, "unknown-event");
  for (const key of requiredPresentKeys[name as OmpExtensionV1EventName] ?? [])
    if (
      typeof payload !== "object" ||
      payload === null ||
      !Object.hasOwn(payload, key)
    )
      throw new OmpExtensionV1EventRejection(
        name,
        `invalid-event-payload:missing-key:${key}`,
      );
  let parsed: z.ZodSafeParseResult<unknown>;
  try {
    parsed = schema.safeParse(payload);
  } catch {
    throw new OmpExtensionV1EventRejection(
      name,
      "invalid-event-payload:parse-exception",
    );
  }
  if (!parsed.success)
    throw new OmpExtensionV1EventRejection(
      name,
      payloadReasonCode(parsed.error),
    );
  // The typed overload bridges the validated structural shape to the pinned
  // omp-extension-v1 Host type; zod cannot express nominal Host members
  // (AgentMessage, ImageContent, AbortSignal).
  return parsed.data;
}
