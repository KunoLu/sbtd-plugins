// Slice 5 Host Event Surface suite — evidence validator.
//
// Scores one real-Host run dir (observer.jsonl + driver.jsonl + scenario.json)
// against the versioned `ompExtensionV1Inventory` — the single event list,
// reused from the Slice 4 Host Contract; this file declares no parallel list.
// The validator fails closed on: missing required events, schema-invalid
// required payloads (as judged at observe time by the subject tarball's own
// adapter-edge validator), Plugin/OMP artifact digest mismatch, denied
// approvals that still produced a tool_result, cross-Session/turn/target
// reuse or double consumption of approvals/results, out-of-order
// tool_result, and shared/stale observer logs (run-id binding).
//
// Outcomes are profile-local: "passed" | "passed-with-diagnostics" | "failed".
// This validator never emits "certified"; trusted certification derivation is
// Slice 6 (ledger/trust policy), and local runs are `local-observation` only.
//
// Evidence writes are content-addressed: one new sha256-named directory per
// distinct bundle, never overwritten; identical rewrite is a no-op, digest
// conflict errors. Sanitization contract: digests, names, counts and stable
// reason codes only — no prompt text, tool I/O text, tokens, transcripts,
// local paths, or PII. Raw run files are scanned with the shared P0
// sanitization detectors before scoring; any hit fails closed.
//
// Trace: packages/omp-sbtd/features/sbtd-control-bootstrap.feature
//   Rule: 宿主事件不被伪造解释且跨边界不复用
// Trace: packages/omp-sbtd/features/p0-conformance-release.feature
//   Scenario: Host Event Surface 未通过时四命令结果不能派生 certified
import { createHash } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import { ompExtensionV1Inventory } from "../../../src/runtime/omp-extension-v1.ts";
import { hasSensitiveText } from "../sanitization.ts";

const sha256 = (value: string | Buffer): string =>
  createHash("sha256").update(value).digest("hex");

// ---------------------------------------------------------------------------
// Record and scenario schemas (evidence schema — validated fail-closed)
// ---------------------------------------------------------------------------

const HEX64 = /^[a-f0-9]{64}$/;

const baseRecordSchema = z.looseObject({
  seq: z.number().int().positive(),
  runId: z.string().min(1),
  kind: z.string(),
});

const eventRecordSchema = baseRecordSchema.extend({
  kind: z.literal("event"),
  event: z.string().min(1),
  schemaValid: z.boolean(),
  reason: z.string().optional(),
  sessionDigest: z.string().regex(HEX64).optional(),
  toolCallDigest: z.string().regex(HEX64).optional(),
  ctxSessionDigest: z.string().regex(HEX64).optional(),
  approved: z.boolean().optional(),
  hostReason: z.string().optional(),
  hostReasonDigest: z.string().regex(HEX64).optional(),
  toolNameDigest: z.string().regex(HEX64).optional(),
  turnIndex: z.number().optional(),
  turnId: z.number().optional(),
  newLeafDigest: z.string().regex(HEX64).nullable().optional(),
  oldLeafDigest: z.string().regex(HEX64).nullable().optional(),
});

const identityRecordSchema = baseRecordSchema.extend({
  kind: z.literal("host_identity"),
  hostPackageFound: z.boolean().optional(),
  hostPackageVersion: z.string().optional(),
  hostEntrypointSha256: z.string().regex(HEX64).optional(),
  hostPackageJsonSha256: z.string().regex(HEX64).optional(),
  validatorLoaded: z.boolean().optional(),
  validatorModuleSha256: z.string().regex(HEX64).optional(),
  validatorInventoryVersion: z.string().optional(),
});

const readyRecordSchema = baseRecordSchema.extend({
  kind: z.literal("observer_ready"),
  subscriptions: z.number().int().nonnegative(),
});

export type ObserverEventRecord = z.infer<typeof eventRecordSchema>;
export type HostIdentityRecord = z.infer<typeof identityRecordSchema>;

const scenarioRecordSchema = z.looseObject({
  runId: z.string().min(1),
  /** Suite-owned risk classification: hashed toolName → class, written by
   * the driver for exactly the tools this suite registers. */
  toolRiskClasses: z
    .record(z.string().regex(HEX64), z.enum(["no-approval", "prompt"]))
    .optional(),
  scenario: z.looseObject({
    ready: z.boolean().optional(),
    hostTools: z.boolean().optional(),
    sbtdCommandRegistered: z.boolean().optional(),
    spikeCommandRegistered: z.boolean().optional(),
    plainTurn: z.boolean().optional(),
    autoApprovedToolTurn: z.boolean().optional(),
    approvedToolTurn: z.boolean().optional(),
    deniedToolTurn: z.boolean().optional(),
    extraTurn: z.boolean().optional(),
    compact: z.looseObject({ ok: z.boolean().optional() }).optional(),
    sessionB: z
      .looseObject({ distinctFromA: z.boolean().optional() })
      .optional(),
    sessionBTurn: z.boolean().optional(),
    resumedA: z.boolean().optional(),
    treeNavigation: z.boolean().optional(),
    branch: z.looseObject({ cancelled: z.boolean().optional() }).optional(),
    postBranchTurn: z.boolean().optional(),
    postCompactTurn: z.boolean().optional(),
    handoff: z
      .looseObject({
        attempted: z.boolean().optional(),
        ok: z.boolean().optional(),
      })
      .optional(),
    error: z.string().optional(),
  }),
});

export type HostEventScenarioRecord = z.infer<typeof scenarioRecordSchema>;

// ---------------------------------------------------------------------------
// Expectation and verdict types
// ---------------------------------------------------------------------------

export interface HostEventRunExpectation {
  readonly runId: string;
  readonly targetOmpVersion: string;
  /** Driver-side recomputation over the exact spawned OMP binary. */
  readonly hostEntrypointSha256: string;
  readonly hostPackageJsonSha256: string;
  readonly hostPackageVersion: string;
  /** sha256 of the subject tarball's dist/runtime/omp-extension-v1.js. */
  readonly pluginValidatorModuleSha256: string;
  /** sha256 of the frozen candidate tarball (recorded, evidence identity). */
  readonly pluginTarballSha256: string;
}

export type HostEventOutcome = "passed" | "passed-with-diagnostics" | "failed";

export interface HostEventVerdict {
  readonly profile: "omp-host-events-v1";
  readonly outcome: HostEventOutcome;
  /** Fail-closed reason codes; empty unless outcome is "failed". */
  readonly reasonCodes: readonly string[];
  /** Non-fatal diagnostics (optional-scope absence, blocked live triggers). */
  readonly diagnostics: readonly string[];
  readonly requiredEventsObserved: readonly string[];
  readonly requiredEventsMissing: readonly string[];
  readonly optionalEventsObserved: readonly string[];
  readonly schemaValid: boolean;
  readonly orderingValid: boolean;
  readonly isolationValid: boolean;
  readonly identityValid: boolean;
  readonly bindingValid: boolean;
}

// ---------------------------------------------------------------------------
// Core validator (pure; tests drive it with fixture records)
// ---------------------------------------------------------------------------

export interface HostEventRunInput {
  readonly records: readonly unknown[];
  readonly scenario: unknown;
  /** Lines in observer.jsonl that did not parse as JSON. */
  readonly malformedObserverLines?: number;
  /** Raw run-file strings that tripped the shared P0 sanitization detectors. */
  readonly sanitizationViolations?: number;
}

const REQUIRED = ompExtensionV1Inventory.requiredEvents;
const OPTIONAL = ompExtensionV1Inventory.optionalEvents;
const KNOWN_EVENTS: ReadonlySet<string> = new Set<string>([
  ...REQUIRED,
  ...OPTIONAL,
]);

export function validateHostEventRun(
  input: HostEventRunInput,
  expected: HostEventRunExpectation,
): HostEventVerdict {
  const failures: string[] = [];
  const diagnostics: string[] = [];

  // --- Sanitization and run-id binding: shared/stale/dirty logs fail closed.
  if ((input.malformedObserverLines ?? 0) > 0)
    failures.push("MALFORMED_OBSERVER_RECORD");
  if ((input.sanitizationViolations ?? 0) > 0)
    failures.push("EVIDENCE_SANITIZATION_VIOLATION");

  const parsed: {
    events: ObserverEventRecord[];
    identity?: HostIdentityRecord;
    ready?: z.infer<typeof readyRecordSchema>;
  } = { events: [] };
  let runIdMismatch = false;
  for (const raw of input.records) {
    const base = baseRecordSchema.safeParse(raw);
    if (!base.success) {
      failures.push("EVIDENCE_RECORD_MALFORMED");
      continue;
    }
    if (base.data.runId !== expected.runId) runIdMismatch = true;
    if (base.data.kind === "event") {
      const ev = eventRecordSchema.safeParse(raw);
      if (!ev.success) failures.push("EVIDENCE_RECORD_MALFORMED");
      else parsed.events.push(ev.data);
    } else if (base.data.kind === "host_identity") {
      const id = identityRecordSchema.safeParse(raw);
      if (!id.success) failures.push("EVIDENCE_RECORD_MALFORMED");
      else parsed.identity = id.data;
    } else if (base.data.kind === "observer_ready") {
      const rd = readyRecordSchema.safeParse(raw);
      if (!rd.success) failures.push("EVIDENCE_RECORD_MALFORMED");
      else parsed.ready = rd.data;
    }
  }
  if (runIdMismatch) failures.push("OBSERVER_LOG_SHARED_OR_STALE");
  if (parsed.ready === undefined) failures.push("OBSERVER_READY_MISSING");
  else if (parsed.ready.subscriptions !== KNOWN_EVENTS.size)
    failures.push("OBSERVER_SUBSCRIPTION_MISMATCH");

  // --- Artifact identity (Host + subject Plugin validator module). ---------
  let identityValid = true;
  const identity = parsed.identity;
  if (identity === undefined) {
    failures.push("HOST_IDENTITY_MISSING");
    identityValid = false;
  } else {
    const mismatch = (field: string) => {
      failures.push(`HOST_IDENTITY_MISMATCH:${field}`);
      identityValid = false;
    };
    if (identity.hostPackageFound !== true) mismatch("package-not-found");
    if (identity.hostPackageVersion !== expected.targetOmpVersion)
      mismatch("host-version-vs-target");
    if (identity.hostPackageVersion !== expected.hostPackageVersion)
      mismatch("host-version-vs-driver");
    if (identity.hostEntrypointSha256 !== expected.hostEntrypointSha256)
      mismatch("entrypoint-digest");
    if (identity.hostPackageJsonSha256 !== expected.hostPackageJsonSha256)
      mismatch("package-json-digest");
    if (identity.validatorLoaded !== true)
      mismatch("validator-module-not-loaded");
    if (
      identity.validatorModuleSha256 !== expected.pluginValidatorModuleSha256
    ) {
      failures.push("PLUGIN_MODULE_DIGEST_MISMATCH");
      identityValid = false;
    }
    if (identity.validatorInventoryVersion !== ompExtensionV1Inventory.version)
      mismatch("inventory-version");
  }

  // --- Event coverage against the single inventory list. -------------------
  const byName = new Map<string, ObserverEventRecord[]>();
  for (const ev of parsed.events) {
    if (!KNOWN_EVENTS.has(ev.event)) {
      failures.push(
        `UNKNOWN_HOST_EVENT_RECORD:${ev.event.replace(/[^a-z0-9_.-]/gi, "")}`,
      );
      continue;
    }
    const list = byName.get(ev.event) ?? [];
    list.push(ev);
    byName.set(ev.event, list);
  }

  const requiredObserved: string[] = [];
  const requiredMissing: string[] = [];
  let schemaValid = true;
  for (const name of REQUIRED) {
    const seen = byName.get(name) ?? [];
    if (seen.length === 0) {
      requiredMissing.push(name);
      failures.push(`REQUIRED_EVENT_MISSING:${name}`);
      continue;
    }
    requiredObserved.push(name);
    if (seen.some((ev) => ev.schemaValid !== true)) {
      schemaValid = false;
      failures.push(`REQUIRED_EVENT_SCHEMA_INVALID:${name}`);
    }
  }
  const optionalObserved = OPTIONAL.filter(
    (name) => (byName.get(name) ?? []).length > 0,
  );
  for (const name of OPTIONAL)
    if ((byName.get(name) ?? []).length === 0)
      diagnostics.push(`OPTIONAL_EVENT_ABSENT:${name}`);
  // schemaValid is only about required-event payloads. Other fail-closed
  // reasons keep their own flags / reason codes.

  const scenario = parseScenario(input.scenario);

  // --- Ordering (per approved-tool turn window, plus session_stop pairing). -
  const orderChecks: Array<[string, boolean]> = [];
  const seqOf = (name: string) => (byName.get(name) ?? []).map((e) => e.seq);
  const approvedApproval = (byName.get("tool_approval_resolved") ?? []).find(
    (e) => e.approved === true,
  );
  if (approvedApproval !== undefined) {
    const toolCall = (byName.get("tool_call") ?? []).find(
      (e) => e.toolCallDigest === approvedApproval.toolCallDigest,
    );
    const toolResult = (byName.get("tool_result") ?? []).find(
      (e) => e.toolCallDigest === approvedApproval.toolCallDigest,
    );
    const turnStart = (byName.get("turn_start") ?? [])
      .filter((e) => e.seq < approvedApproval.seq)
      .pop();
    const turnEnd = (byName.get("turn_end") ?? []).find(
      (e) => toolResult !== undefined && e.seq > toolResult.seq,
    );
    const agentStart = seqOf("before_agent_start")[0];
    orderChecks.push(
      [
        "before-agent-start-before-turn-start",
        agentStart !== undefined &&
          turnStart !== undefined &&
          agentStart < turnStart.seq,
      ],
      [
        "turn-start-before-tool-call",
        turnStart !== undefined &&
          toolCall !== undefined &&
          turnStart.seq < toolCall.seq,
      ],
      [
        "tool-call-before-approval",
        toolCall !== undefined && toolCall.seq < approvedApproval.seq,
      ],
      [
        "approval-before-tool-result",
        toolResult !== undefined && approvedApproval.seq < toolResult.seq,
      ],
      [
        "tool-result-before-turn-end",
        toolResult !== undefined &&
          turnEnd !== undefined &&
          toolResult.seq < turnEnd.seq,
      ],
    );
  } else {
    orderChecks.push(["approved-approval-observed", false]);
  }
  const stops = seqOf("session_stop");
  const ends = seqOf("turn_end");
  orderChecks.push([
    "turn-end-before-session-stop",
    stops.some((s) => ends.some((e) => e < s)),
  ]);
  const orderingValid = orderChecks.every(([, ok]) => ok);
  for (const [label, ok] of orderChecks)
    if (!ok) failures.push(`ORDER_VIOLATION:${label}`);

  // --- Approval/result one-shot binding. ------------------------------------
  let bindingValid = true;
  const bindingFailure = (code: string) => {
    failures.push(code);
    bindingValid = false;
  };
  const toolCalls = byName.get("tool_call") ?? [];
  const approvals = byName.get("tool_approval_resolved") ?? [];
  const results = byName.get("tool_result") ?? [];

  for (const denied of approvals.filter((e) => e.approved === false))
    if (results.some((e) => e.toolCallDigest === denied.toolCallDigest))
      bindingFailure("DENIED_APPROVAL_HAS_TOOL_RESULT");

  for (const result of results) {
    const call = toolCalls.find(
      (e) => e.toolCallDigest === result.toolCallDigest,
    );
    if (call === undefined) bindingFailure("TOOL_RESULT_WITHOUT_TOOL_CALL");
    else if (result.seq < call.seq)
      bindingFailure("TOOL_RESULT_BEFORE_TOOL_CALL");
  }

  const countByDigest = (list: readonly ObserverEventRecord[]) => {
    const counts = new Map<string, number>();
    for (const e of list)
      if (e.toolCallDigest !== undefined)
        counts.set(e.toolCallDigest, (counts.get(e.toolCallDigest) ?? 0) + 1);
    return counts;
  };
  for (const [, count] of countByDigest(approvals))
    if (count > 1) bindingFailure("APPROVAL_DOUBLE_CONSUMED");
  for (const [, count] of countByDigest(results))
    if (count > 1) bindingFailure("TOOL_RESULT_DOUBLE_CONSUMED");

  for (const approval of approvals) {
    const call = toolCalls.find(
      (e) => e.toolCallDigest === approval.toolCallDigest,
    );
    if (call === undefined) {
      bindingFailure("APPROVAL_WITHOUT_TOOL_CALL");
      continue;
    }
    // Cross-Session reuse: the approval's payload Session digest must equal
    // the Session digest context of its tool_call.
    if (
      approval.sessionDigest !== undefined &&
      call.ctxSessionDigest !== undefined &&
      approval.sessionDigest !== call.ctxSessionDigest
    )
      bindingFailure("APPROVAL_SESSION_MISMATCH");
  }

  // The same toolCall identity must never span two Sessions.
  const digestSessions = new Map<string, Set<string>>();
  for (const e of [...toolCalls, ...approvals, ...results]) {
    const session = e.sessionDigest ?? e.ctxSessionDigest;
    if (e.toolCallDigest === undefined || session === undefined) continue;
    const set = digestSessions.get(e.toolCallDigest) ?? new Set<string>();
    set.add(session);
    digestSessions.set(e.toolCallDigest, set);
  }
  for (const [, sessions] of digestSessions)
    if (sessions.size > 1) bindingFailure("TOOL_CALL_REUSED_ACROSS_SESSIONS");

  // Cross-target and cross-turn binding: one toolCall identity must stay
  // bound to a single target and a single enclosing turn. Host 17.3.5 tool
  // events carry no risk-class field, so target = hashed toolName is the
  // observable isolation key; the enclosing turn is derived as the nearest
  // preceding same-Session turn_start by seq (fingerprinted by its
  // turnIndex when the observer recorded one, else its seq).
  const turnStarts = [...(byName.get("turn_start") ?? [])].sort(
    (a, b) => a.seq - b.seq,
  );
  const enclosingTurnKey = (event: ObserverEventRecord): string | undefined => {
    const session = event.ctxSessionDigest ?? event.sessionDigest;
    let nearest: ObserverEventRecord | undefined;
    for (const turn of turnStarts) {
      if (turn.seq >= event.seq) break;
      if (
        session !== undefined &&
        turn.ctxSessionDigest !== undefined &&
        turn.ctxSessionDigest !== session
      )
        continue;
      nearest = turn;
    }
    if (nearest === undefined) return undefined;
    const turnId = nearest.turnIndex ?? nearest.seq;
    return `${nearest.ctxSessionDigest ?? "session-unobserved"}:${turnId}`;
  };
  const digestTargets = new Map<string, Set<string>>();
  const digestTurns = new Map<string, Set<string>>();
  for (const e of [...toolCalls, ...approvals, ...results]) {
    if (e.toolCallDigest === undefined) continue;
    if (e.toolNameDigest !== undefined) {
      const set = digestTargets.get(e.toolCallDigest) ?? new Set<string>();
      set.add(e.toolNameDigest);
      digestTargets.set(e.toolCallDigest, set);
    }
    const turnKey = enclosingTurnKey(e);
    if (turnKey !== undefined) {
      const set = digestTurns.get(e.toolCallDigest) ?? new Set<string>();
      set.add(turnKey);
      digestTurns.set(e.toolCallDigest, set);
    }
  }
  for (const [, targets] of digestTargets)
    if (targets.size > 1) bindingFailure("BINDING_TARGET_MISMATCH");
  for (const [, turns] of digestTurns)
    if (turns.size > 1) bindingFailure("BINDING_TURN_MISMATCH");

  // Suite-owned risk classification: the driver records a stable map of
  // hashed toolName → risk class for exactly the tools this suite
  // registers (Host 17.3.5 events carry no risk-class field, so the
  // classification source is the suite, never a Host payload). Every tool
  // event must resolve through that map; an unknown or unrecorded
  // toolName fails closed, and one toolCall identity spanning two classes
  // is a cross-risk-class binding break.
  const riskClassByTool = scenario?.toolRiskClasses;
  const digestRiskClasses = new Map<string, Set<string>>();
  for (const e of [...toolCalls, ...approvals, ...results]) {
    if (e.toolCallDigest === undefined) continue;
    const riskClass =
      e.toolNameDigest !== undefined
        ? riskClassByTool?.[e.toolNameDigest]
        : undefined;
    if (riskClass === undefined) {
      bindingFailure("RISK_CLASS_UNOBSERVABLE");
      continue;
    }
    const set = digestRiskClasses.get(e.toolCallDigest) ?? new Set<string>();
    set.add(riskClass);
    digestRiskClasses.set(e.toolCallDigest, set);
  }
  for (const [, classes] of digestRiskClasses)
    if (classes.size > 1) bindingFailure("BINDING_RISK_MISMATCH");

  // --- Session isolation and Session-bound events. ---------------------------
  let isolationValid = true;
  const isolationFailure = (code: string) => {
    failures.push(code);
    isolationValid = false;
  };
  const ctxDigests = new Set(
    parsed.events
      .map((e) => e.ctxSessionDigest)
      .filter((d): d is string => d !== undefined),
  );
  if (ctxDigests.size < 2)
    isolationFailure("SESSION_ISOLATION_VIOLATION:too-few-sessions");

  const switches = byName.get("session_switch") ?? [];
  const switchReasons = switches.map((e) => e.hostReason);
  if (switches.length > 0 && switchReasons[0] !== "new")
    isolationFailure("SESSION_SWITCH_ORDER:first-not-new");
  if (!switchReasons.includes("resume"))
    isolationFailure("SESSION_SWITCH_REASON_MISSING:resume");

  if (scenario?.scenario.handoff !== undefined) {
    if (scenario.scenario.handoff.ok === true) {
      if (!switchReasons.includes("handoff"))
        isolationFailure("SESSION_SWITCH_REASON_MISSING:handoff");
    } else {
      diagnostics.push("HANDOFF_TRIGGER_BLOCKED");
    }
  } else {
    diagnostics.push("HANDOFF_NOT_ATTEMPTED");
  }

  // Session identity restore: a pre-switch Session identity must be observed
  // again after the resume switch (A suspended by B, then A resumed).
  const firstSwitchSeq = switches[0]?.seq;
  const resumeSwitch = switches.find((e) => e.hostReason === "resume");
  if (firstSwitchSeq !== undefined && resumeSwitch !== undefined) {
    const before = new Set(
      parsed.events
        .filter(
          (e) => e.seq < firstSwitchSeq && e.ctxSessionDigest !== undefined,
        )
        .map((e) => e.ctxSessionDigest),
    );
    const restored = parsed.events.some(
      (e) =>
        e.seq > resumeSwitch.seq &&
        e.ctxSessionDigest !== undefined &&
        before.has(e.ctxSessionDigest),
    );
    if (!restored)
      isolationFailure("SESSION_ISOLATION_VIOLATION:identity-not-restored");
  }

  for (const compacting of byName.get("session.compacting") ?? [])
    if (
      compacting.sessionDigest === undefined ||
      compacting.sessionDigest !== compacting.ctxSessionDigest
    )
      isolationFailure("COMPACTION_NOT_SESSION_BOUND");

  const treeRecords = byName.get("session_tree") ?? [];
  if (
    treeRecords.length > 0 &&
    !treeRecords.some(
      (e) =>
        typeof e.newLeafDigest === "string" &&
        typeof e.oldLeafDigest === "string" &&
        e.newLeafDigest !== e.oldLeafDigest,
    )
  )
    isolationFailure("SESSION_TREE_LEAF_UNCHANGED");

  // --- Driver scenario steps (fail closed on lost driver steps). ------------
  if (scenario === undefined) {
    failures.push("SCENARIO_RECORD_MISSING");
  } else {
    if (scenario.runId !== expected.runId)
      failures.push("SCENARIO_RUN_ID_MISMATCH");
    const s = scenario.scenario;
    const stepChecks: Array<[string, boolean]> = [
      ["ready", s.ready === true],
      ["host-tools", s.hostTools === true],
      ["sbtd-command-registered", s.sbtdCommandRegistered === true],
      ["plain-turn", s.plainTurn === true],
      ["auto-approved-tool-turn", s.autoApprovedToolTurn === true],
      ["approved-tool-turn", s.approvedToolTurn === true],
      ["denied-tool-turn", s.deniedToolTurn === true],
      ["compact", s.compact?.ok === true],
      ["session-b-distinct", s.sessionB?.distinctFromA === true],
      ["session-b-turn", s.sessionBTurn === true],
      ["resumed-a", s.resumedA === true],
      ["tree-navigation", s.treeNavigation === true],
      ["branch", s.branch?.cancelled === false],
      ["post-branch-turn", s.postBranchTurn === true],
      ["post-compact-turn", s.postCompactTurn === true],
    ];
    for (const [step, ok] of stepChecks)
      if (!ok) failures.push(`SCENARIO_STEP_INCOMPLETE:${step}`);
  }

  const dedup = (codes: readonly string[]) => [...new Set(codes)];
  const reasonCodes = dedup(failures);
  const outcome: HostEventOutcome =
    reasonCodes.length > 0
      ? "failed"
      : diagnostics.length > 0
        ? "passed-with-diagnostics"
        : "passed";

  return {
    profile: "omp-host-events-v1",
    outcome,
    reasonCodes,
    diagnostics: dedup(diagnostics),
    requiredEventsObserved: requiredObserved,
    requiredEventsMissing: requiredMissing,
    optionalEventsObserved: optionalObserved,
    schemaValid,
    orderingValid,
    isolationValid,
    identityValid,
    bindingValid,
  };
}

function parseScenario(raw: unknown): HostEventScenarioRecord | undefined {
  if (raw === undefined || raw === null) return undefined;
  const parsed = scenarioRecordSchema.safeParse(raw);
  return parsed.success ? parsed.data : undefined;
}

// ---------------------------------------------------------------------------
// Run-dir filesystem wrapper
// ---------------------------------------------------------------------------

export interface HostEventRunDir {
  readonly records: unknown[];
  readonly scenario: unknown;
  readonly malformedObserverLines: number;
  readonly sanitizationViolations: number;
  readonly observerLogSha256: string;
  readonly driverLogSha256: string;
  readonly scenarioSha256: string;
}

export async function readHostEventRunDir(
  runDir: string,
): Promise<HostEventRunDir> {
  const observerRaw = await readFile(
    join(runDir, "out", "observer.jsonl"),
    "utf8",
  );
  const driverRaw = await readFile(join(runDir, "out", "driver.jsonl"), "utf8");
  const scenarioRaw = await readFile(
    join(runDir, "out", "scenario.json"),
    "utf8",
  );
  const records: unknown[] = [];
  let malformedObserverLines = 0;
  for (const line of observerRaw.split("\n")) {
    if (line.length === 0) continue;
    try {
      records.push(JSON.parse(line));
    } catch {
      malformedObserverLines += 1;
    }
  }
  let scenario: unknown;
  try {
    scenario = JSON.parse(scenarioRaw);
  } catch {
    scenario = undefined;
  }
  // Raw run files are evidence input: any local path, token-shaped or
  // credential-shaped text fails the run closed instead of being scored.
  const sanitizationViolations = [observerRaw, driverRaw, scenarioRaw].filter(
    (raw) => hasSensitiveText(raw),
  ).length;
  return {
    records,
    scenario,
    malformedObserverLines,
    sanitizationViolations,
    observerLogSha256: sha256(observerRaw),
    driverLogSha256: sha256(driverRaw),
    scenarioSha256: sha256(scenarioRaw),
  };
}

/** Driver-side recomputation over the exact spawned OMP binary. */
export function recomputeHostIdentity(ompBin: string): {
  readonly entrypointSha256: string;
  readonly packageVersion?: string;
  readonly packageJsonSha256?: string;
} {
  const entrypoint = realpathSync(ompBin);
  const entrypointSha256 = sha256(readFileSync(entrypoint));
  let dir = dirname(entrypoint);
  for (let depth = 0; depth < 8; depth += 1) {
    const candidate = join(dir, "package.json");
    try {
      const parsed = JSON.parse(readFileSync(candidate, "utf8")) as {
        name?: string;
        version?: string;
      };
      if (parsed?.name === "@oh-my-pi/pi-coding-agent")
        return {
          entrypointSha256,
          packageVersion: parsed.version,
          packageJsonSha256: sha256(readFileSync(candidate)),
        };
    } catch {
      // keep walking up
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return { entrypointSha256 };
}

// ---------------------------------------------------------------------------
// Content-addressed local-observation evidence bundle
// ---------------------------------------------------------------------------

export const hostEventEvidenceBundleSchema = z.strictObject({
  schemaVersion: z.literal(1),
  profile: z.literal("omp-host-events-v1"),
  evidenceKind: z.literal("local-observation"),
  runId: z.string().min(1),
  pluginTarballSha256: z.string().regex(HEX64),
  pluginValidatorModuleSha256: z.string().regex(HEX64),
  ompVersion: z.string().min(1),
  ompArtifact: z.strictObject({
    entrypointSha256: z.string().regex(HEX64),
    packageJsonSha256: z.string().regex(HEX64),
  }),
  requiredEventsObserved: z.array(z.string()),
  optionalEventsObserved: z.array(z.string()),
  schemaValid: z.boolean(),
  orderingValid: z.boolean(),
  isolationValid: z.boolean(),
  identityValid: z.boolean(),
  bindingValid: z.boolean(),
  reasonCodes: z.array(z.string()),
  diagnostics: z.array(z.string()),
  outcome: z.enum(["passed", "passed-with-diagnostics", "failed"]),
  sources: z.strictObject({
    observerLogSha256: z.string().regex(HEX64),
    driverLogSha256: z.string().regex(HEX64),
    scenarioSha256: z.string().regex(HEX64),
  }),
});

export type HostEventEvidenceBundle = z.infer<
  typeof hostEventEvidenceBundleSchema
>;

export function buildLocalObservationBundle(input: {
  readonly verdict: HostEventVerdict;
  readonly expectation: HostEventRunExpectation;
  readonly sources: HostEventEvidenceBundle["sources"];
}): HostEventEvidenceBundle {
  const { verdict, expectation } = input;
  return {
    schemaVersion: 1,
    profile: verdict.profile,
    evidenceKind: "local-observation",
    runId: expectation.runId,
    pluginTarballSha256: expectation.pluginTarballSha256,
    pluginValidatorModuleSha256: expectation.pluginValidatorModuleSha256,
    ompVersion: expectation.targetOmpVersion,
    ompArtifact: {
      entrypointSha256: expectation.hostEntrypointSha256,
      packageJsonSha256: expectation.hostPackageJsonSha256,
    },
    requiredEventsObserved: verdict.requiredEventsObserved,
    optionalEventsObserved: verdict.optionalEventsObserved,
    schemaValid: verdict.schemaValid,
    orderingValid: verdict.orderingValid,
    isolationValid: verdict.isolationValid,
    identityValid: verdict.identityValid,
    bindingValid: verdict.bindingValid,
    reasonCodes: verdict.reasonCodes,
    diagnostics: verdict.diagnostics,
    outcome: verdict.outcome,
    sources: input.sources,
  };
}

const sortKeysDeep = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  if (typeof value === "object" && value !== null)
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([key, inner]) => [key, sortKeysDeep(inner)]),
    );
  return value;
};

const canonicalize = (value: unknown): string =>
  JSON.stringify(sortKeysDeep(value));

export interface EvidenceWriteResult {
  readonly dir: string;
  readonly digest: string;
  /** false when the identical bundle was already persisted (idempotent). */
  readonly wrote: boolean;
}

/**
 * Persist one sanitized local-observation bundle content-addressed:
 * `<evidenceRoot>/<sha256(canonical bundle)>/evidence.json`. A new hash-named
 * directory only; never overwritten. An existing directory with identical
 * content is a no-op; a digest collision with different content is a defect
 * and throws instead of rewriting.
 */
export async function writeLocalObservationEvidence(
  evidenceRoot: string,
  bundle: HostEventEvidenceBundle,
): Promise<EvidenceWriteResult> {
  const parsed = hostEventEvidenceBundleSchema.parse(bundle);
  const canonical = `${canonicalize(parsed)}\n`;
  const digest = sha256(canonical);
  const dir = join(evidenceRoot, digest);
  const file = join(dir, "evidence.json");
  try {
    const existing = await readFile(file, "utf8");
    if (existing === canonical) return { dir, digest, wrote: false };
    throw new Error("EVIDENCE_CONTENT_CONFLICT");
  } catch (error) {
    if (error instanceof Error && error.message === "EVIDENCE_CONTENT_CONFLICT")
      throw error;
    // absent: create below
  }
  await mkdir(dir, { recursive: true });
  await writeFile(file, canonical, { encoding: "utf8", flag: "wx" });
  return { dir, digest, wrote: true };
}
