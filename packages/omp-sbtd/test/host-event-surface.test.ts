// Slice 5 contract tests for 08-20-omp-plugin-compatibility-decoupling.
//
// Always-on (inside the 30s default budget): sanitizer, evidence schema and
// content addressing, inventory alignment with `ompExtensionV1Inventory`,
// fail-closed validator negatives over fixture records, packaging exclusion
// of the observer/driver, and driver-side Host identity recomputation. The
// real-Host cell is env-gated (SPIKE_OMP_BIN + HOST_EVENT_PLUGIN_TARBALL) and
// never runs in default CI.
//
// Trace: packages/omp-sbtd/features/sbtd-control-bootstrap.feature
//   Rule: 宿主事件不被伪造解释且跨边界不复用
// Trace: packages/omp-sbtd/features/p0-conformance-release.feature
//   Scenario: Host Event Surface 未通过时四命令结果不能派生 certified
//
// Mock Strategy: contract-backed fixtures for the validator; the live cell
// drives a real OMP Host when the documented env is present.

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
// Untyped .mjs suite helper: exercised behaviorally, no type surface needed.
// @ts-expect-error JS module without declarations
import { sanitizeStderrText } from "../scripts/p0/host-event/lib.mjs";
import {
  assertPackedControllerFailClosed,
  completeLiveCellAfterDriver,
  hostEventObserveEvents,
  runLiveCell,
  subjectStaleBlockedReason,
} from "../scripts/p0/host-event/run-live-cell.ts";
import {
  buildLocalObservationBundle,
  type HostEventRunExpectation,
  hostEventEvidenceBundleSchema,
  recomputeHostIdentity,
  validateHostEventRun,
  writeLocalObservationEvidence,
} from "../scripts/p0/host-event/validate.ts";
import { ompExtensionV1Inventory } from "../src/runtime/index.ts";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = join(TEST_DIR, "..");

const d = (label: string) => createHash("sha256").update(label).digest("hex");

const RUN_ID = "test-run";
const SESS_A = d("session-a");
const SESS_B = d("session-b");
const SESS_C = d("session-c");
const T_PLAIN = d("call-plain");
const T_APPROVED = d("call-approved");
const T_DENIED = d("call-denied");
const TOOL_BASH = d("tool-bash");

const EXPECTED: HostEventRunExpectation = {
  runId: RUN_ID,
  targetOmpVersion: "17.3.5",
  hostEntrypointSha256: d("host-entrypoint"),
  hostPackageJsonSha256: d("host-package-json"),
  hostPackageVersion: "17.3.5",
  pluginValidatorModuleSha256: d("validator-module"),
  pluginTarballSha256: d("plugin-tarball"),
};

/** Fixture mirror of the observer JSONL record shape (index signature keeps
 * member access typed without casts; the validator re-parses with zod). */
interface FixtureRecord {
  seq: number;
  atMs: number;
  runId: string;
  kind: string;
  event?: string;
  schemaValid?: boolean;
  reason?: string;
  sessionDigest?: string;
  toolCallDigest?: string;
  ctxSessionDigest?: string;
  approved?: boolean;
  hostReason?: string;
  hostReasonDigest?: string;
  toolNameDigest?: string;
  turnIndex?: number;
  newLeafDigest?: string | null;
  oldLeafDigest?: string | null;
  [key: string]: unknown;
}

interface EventOverrides {
  readonly schemaValid?: boolean;
  readonly reason?: string;
  readonly sessionDigest?: string;
  readonly toolCallDigest?: string;
  readonly ctxSessionDigest?: string;
  readonly approved?: boolean;
  readonly hostReason?: string;
  readonly hostReasonDigest?: string;
  readonly toolNameDigest?: string;
  readonly turnIndex?: number;
  readonly newLeafDigest?: string | null;
  readonly oldLeafDigest?: string | null;
}

const ev = (
  seq: number,
  event: string,
  overrides: EventOverrides = {},
): FixtureRecord => ({
  seq,
  atMs: seq,
  runId: RUN_ID,
  kind: "event",
  event,
  schemaValid: true,
  fields: ["type"],
  ...overrides,
});

/** A complete passing run: all 12 required events + credential_disabled,
 * approved + denied approvals, session A/B/A isolation with restore,
 * session-bound compaction, tree navigation, and a handoff switch. */
function baseRecords(): FixtureRecord[] {
  return [
    {
      seq: 1,
      atMs: 0,
      runId: RUN_ID,
      kind: "observer_ready",
      subscriptions: 13,
    },
    {
      seq: 2,
      atMs: 1,
      runId: RUN_ID,
      kind: "host_identity",
      hostPackageFound: true,
      hostPackageName: "@oh-my-pi/pi-coding-agent",
      hostPackageVersion: "17.3.5",
      hostEntrypointSha256: EXPECTED.hostEntrypointSha256,
      hostPackageJsonSha256: EXPECTED.hostPackageJsonSha256,
      validatorLoaded: true,
      validatorModuleSha256: EXPECTED.pluginValidatorModuleSha256,
      validatorInventoryVersion: "omp-extension-v1",
    },
    ev(3, "session_start", { ctxSessionDigest: SESS_A }),
    ev(4, "before_agent_start", { ctxSessionDigest: SESS_A }),
    ev(5, "turn_start", { ctxSessionDigest: SESS_A, turnIndex: 0 }),
    ev(6, "tool_call", {
      toolCallDigest: T_PLAIN,
      ctxSessionDigest: SESS_A,
      toolNameDigest: TOOL_BASH,
    }),
    ev(7, "tool_result", {
      toolCallDigest: T_PLAIN,
      ctxSessionDigest: SESS_A,
      toolNameDigest: TOOL_BASH,
    }),
    ev(8, "turn_end", { ctxSessionDigest: SESS_A }),
    ev(9, "session_stop", { ctxSessionDigest: SESS_A }),
    ev(10, "before_agent_start", { ctxSessionDigest: SESS_A }),
    ev(11, "turn_start", { ctxSessionDigest: SESS_A, turnIndex: 1 }),
    ev(12, "tool_call", {
      toolCallDigest: T_APPROVED,
      ctxSessionDigest: SESS_A,
      toolNameDigest: TOOL_BASH,
    }),
    ev(13, "tool_approval_resolved", {
      toolCallDigest: T_APPROVED,
      sessionDigest: SESS_A,
      ctxSessionDigest: SESS_A,
      approved: true,
      toolNameDigest: TOOL_BASH,
    }),
    ev(14, "tool_result", {
      toolCallDigest: T_APPROVED,
      ctxSessionDigest: SESS_A,
      toolNameDigest: TOOL_BASH,
    }),
    ev(15, "turn_end", { ctxSessionDigest: SESS_A }),
    ev(16, "session_stop", { ctxSessionDigest: SESS_A }),
    ev(17, "before_agent_start", { ctxSessionDigest: SESS_A }),
    ev(18, "turn_start", { ctxSessionDigest: SESS_A, turnIndex: 2 }),
    ev(19, "tool_call", {
      toolCallDigest: T_DENIED,
      ctxSessionDigest: SESS_A,
      toolNameDigest: TOOL_BASH,
    }),
    ev(20, "tool_approval_resolved", {
      toolCallDigest: T_DENIED,
      sessionDigest: SESS_A,
      ctxSessionDigest: SESS_A,
      approved: false,
      toolNameDigest: TOOL_BASH,
    }),
    ev(21, "turn_end", { ctxSessionDigest: SESS_A }),
    ev(22, "session_stop", { ctxSessionDigest: SESS_A }),
    ev(23, "session.compacting", {
      sessionDigest: SESS_A,
      ctxSessionDigest: SESS_A,
    }),
    ev(24, "session_switch", { hostReason: "new", ctxSessionDigest: SESS_B }),
    ev(25, "before_agent_start", { ctxSessionDigest: SESS_B }),
    ev(26, "turn_start", { ctxSessionDigest: SESS_B, turnIndex: 0 }),
    ev(27, "turn_end", { ctxSessionDigest: SESS_B }),
    ev(28, "session_stop", { ctxSessionDigest: SESS_B }),
    ev(29, "session_switch", {
      hostReason: "resume",
      ctxSessionDigest: SESS_A,
    }),
    ev(30, "session_tree", {
      newLeafDigest: d("leaf-2"),
      oldLeafDigest: d("leaf-1"),
      ctxSessionDigest: SESS_A,
    }),
    ev(31, "session_branch", { ctxSessionDigest: SESS_A }),
    ev(32, "before_agent_start", { ctxSessionDigest: SESS_A }),
    ev(33, "turn_start", { ctxSessionDigest: SESS_A, turnIndex: 3 }),
    ev(34, "turn_end", { ctxSessionDigest: SESS_A }),
    ev(35, "session_stop", { ctxSessionDigest: SESS_A }),
    ev(36, "session_switch", {
      hostReason: "handoff",
      ctxSessionDigest: SESS_C,
    }),
    ev(37, "credential_disabled", { ctxSessionDigest: SESS_C }),
  ];
}

interface FixtureScenario {
  runId: string;
  scenario: {
    handoff?: { attempted: boolean; ok: boolean };
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

function baseScenario(): FixtureScenario {
  return {
    runId: RUN_ID,
    toolRiskClasses: {
      [TOOL_BASH]: "prompt",
      [d("tool-echo")]: "no-approval",
    },
    scenario: {
      ready: true,
      hostTools: true,
      sbtdCommandRegistered: true,
      spikeCommandRegistered: true,
      plainTurn: true,
      autoApprovedToolTurn: true,
      approvedToolTurn: true,
      deniedToolTurn: true,
      extraTurn: true,
      compact: { ok: true, resultKeys: ["compacted"] },
      sessionB: { idDigest: SESS_B, distinctFromA: true },
      sessionBTurn: true,
      resumedA: true,
      treeNavigation: true,
      branch: { cancelled: false },
      postBranchTurn: true,
      postCompactTurn: true,
      handoff: { attempted: true, ok: true },
    },
    uiRequestsSeen: 2,
    hostToolCalls: [],
    driverExtDiagnostics: [],
  };
}

const validateBase = (
  records: FixtureRecord[],
  scenario: unknown = baseScenario(),
) => validateHostEventRun({ records, scenario }, EXPECTED);

describe("Feature: Host Event Surface — inventory is the single event list", () => {
  it("the suite observe list is exactly the omp-extension-v1 inventory", () => {
    expect(hostEventObserveEvents()).toEqual([
      ...ompExtensionV1Inventory.requiredEvents,
      ...ompExtensionV1Inventory.optionalEvents,
    ]);
    expect(ompExtensionV1Inventory.requiredEvents).toHaveLength(12);
  });

  it("every inventory required event is enforced by the validator", () => {
    for (const name of ompExtensionV1Inventory.requiredEvents) {
      const records = baseRecords().filter((r) => r.event !== name);
      const verdict = validateBase(records);
      expect(verdict.outcome).toBe("failed");
      expect(verdict.reasonCodes).toContain(`REQUIRED_EVENT_MISSING:${name}`);
    }
  });
});

describe("Feature: Host Event Surface — validator fail-closed contract", () => {
  it("a complete well-formed run passes with no certified vocabulary", () => {
    const verdict = validateBase(baseRecords());
    expect(verdict.outcome).toBe("passed");
    expect(verdict.reasonCodes).toEqual([]);
    expect(verdict.schemaValid).toBe(true);
    expect(verdict.identityValid).toBe(true);
    expect(verdict.orderingValid).toBe(true);
    expect(verdict.isolationValid).toBe(true);
    expect(verdict.bindingValid).toBe(true);
    expect(verdict.requiredEventsObserved).toEqual([
      ...ompExtensionV1Inventory.requiredEvents,
    ]);
    expect(JSON.stringify(verdict)).not.toContain("certified");
  });

  it("a schema-invalid required payload fails closed", () => {
    const records = baseRecords().map((r) =>
      r.event === "tool_call" && r.seq === 12
        ? {
            ...r,
            schemaValid: false,
            reason: "EVENT_REJECTED:invalid-event-payload:invalid_type",
          }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.schemaValid).toBe(false);
    expect(verdict.reasonCodes).toContain(
      "REQUIRED_EVENT_SCHEMA_INVALID:tool_call",
    );
  });

  it("a Host entrypoint digest mismatch fails closed", () => {
    const records = baseRecords().map((r) =>
      r.kind === "host_identity"
        ? { ...r, hostEntrypointSha256: d("other-entrypoint") }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.identityValid).toBe(false);
    expect(verdict.schemaValid).toBe(true);
    expect(verdict.reasonCodes).toContain(
      "HOST_IDENTITY_MISMATCH:entrypoint-digest",
    );
  });

  it("a Plugin validator-module digest mismatch fails closed", () => {
    const records = baseRecords().map((r) =>
      r.kind === "host_identity"
        ? { ...r, validatorModuleSha256: d("other-module") }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.identityValid).toBe(false);
    expect(verdict.schemaValid).toBe(true);
    expect(verdict.reasonCodes).toContain("PLUGIN_MODULE_DIGEST_MISMATCH");
  });

  it("a denied approval that still produced a tool_result fails closed", () => {
    const records = [
      ...baseRecords(),
      ev(38, "tool_result", {
        toolCallDigest: T_DENIED,
        ctxSessionDigest: SESS_A,
      }),
    ];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("DENIED_APPROVAL_HAS_TOOL_RESULT");
  });

  it("a tool_result without its tool_call fails closed", () => {
    const records = [
      ...baseRecords(),
      ev(38, "tool_result", {
        toolCallDigest: d("call-orphan"),
        ctxSessionDigest: SESS_A,
      }),
    ];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("TOOL_RESULT_WITHOUT_TOOL_CALL");
  });

  it("a tool_result ordered before its tool_call fails closed", () => {
    const records = [
      ...baseRecords(),
      // seq 5 < the T_PLAIN tool_call at seq 6.
      ev(5, "tool_result", {
        toolCallDigest: T_PLAIN,
        ctxSessionDigest: SESS_A,
      }),
    ];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("TOOL_RESULT_BEFORE_TOOL_CALL");
  });

  it("an approval bound to a different Session than its tool_call fails closed", () => {
    const records = baseRecords().map((r) =>
      r.event === "tool_approval_resolved" && r.toolCallDigest === T_APPROVED
        ? { ...r, sessionDigest: SESS_B }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("APPROVAL_SESSION_MISMATCH");
  });

  it("a double-consumed approval fails closed", () => {
    const records = [
      ...baseRecords(),
      ev(38, "tool_approval_resolved", {
        toolCallDigest: T_APPROVED,
        sessionDigest: SESS_A,
        ctxSessionDigest: SESS_A,
        approved: true,
      }),
    ];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("APPROVAL_DOUBLE_CONSUMED");
  });

  it("a toolCall identity reused across Sessions fails closed", () => {
    const records = [
      ...baseRecords(),
      ev(38, "tool_call", {
        toolCallDigest: T_APPROVED,
        ctxSessionDigest: SESS_B,
      }),
    ];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.bindingValid).toBe(false);
    expect(verdict.reasonCodes).toContain("TOOL_CALL_REUSED_ACROSS_SESSIONS");
  });

  it("a toolCall identity bound to different toolName digests fails closed", () => {
    const records = baseRecords().map((r) =>
      r.event === "tool_result" && r.toolCallDigest === T_APPROVED
        ? { ...r, toolNameDigest: d("tool-echo") }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.bindingValid).toBe(false);
    expect(verdict.reasonCodes).toContain("BINDING_TARGET_MISMATCH");
  });

  it("a toolCall identity spanning two risk classes fails closed", () => {
    // spike_guarded (prompt) vs spike_echo (no-approval): the approval
    // resolves to the other suite-registered class than its call/result.
    const records = baseRecords().map((r) =>
      r.event === "tool_approval_resolved" && r.toolCallDigest === T_APPROVED
        ? { ...r, toolNameDigest: d("tool-echo") }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.bindingValid).toBe(false);
    expect(verdict.reasonCodes).toContain("BINDING_RISK_MISMATCH");
  });

  it("a tool event outside the suite-registered risk map fails closed", () => {
    const records = [
      ...baseRecords(),
      ev(38, "tool_call", {
        toolCallDigest: d("call-foreign"),
        ctxSessionDigest: SESS_A,
        toolNameDigest: d("tool-unknown-to-suite"),
      }),
    ];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.bindingValid).toBe(false);
    expect(verdict.reasonCodes).toContain("RISK_CLASS_UNOBSERVABLE");
  });

  it("a toolCall identity split across enclosing turns fails closed", () => {
    // Move the approved tool_result into the next turn (after the seq-18
    // turn_start): call/approval sit in the seq-11 turn, the result does
    // not. Ordering still holds, so only the turn binding can fail.
    const records = baseRecords().map((r) =>
      r.event === "tool_result" && r.toolCallDigest === T_APPROVED
        ? { ...r, seq: 20, atMs: 20 }
        : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.bindingValid).toBe(false);
    expect(verdict.reasonCodes).toContain("BINDING_TURN_MISMATCH");
  });

  it("a record from another run (shared/stale log) fails closed", () => {
    const foreign = {
      ...ev(38, "session_start", { ctxSessionDigest: SESS_A }),
      runId: "other-run",
    };
    const records = [...baseRecords(), foreign];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("OBSERVER_LOG_SHARED_OR_STALE");
  });

  it("an unknown Host event record fails closed", () => {
    const records = [...baseRecords(), ev(38, "bogus_event")];
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain(
      "UNKNOWN_HOST_EVENT_RECORD:bogus_event",
    );
  });

  it("a missing resume switch fails Session isolation", () => {
    const records = baseRecords().filter((r) => r.hostReason !== "resume");
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain(
      "SESSION_SWITCH_REASON_MISSING:resume",
    );
  });

  it("compaction not bound to its Session fails closed", () => {
    const records = baseRecords().map((r) =>
      r.event === "session.compacting" ? { ...r, sessionDigest: SESS_B } : r,
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("failed");
    expect(verdict.reasonCodes).toContain("COMPACTION_NOT_SESSION_BOUND");
  });

  it("malformed observer lines and sanitization hits fail closed", () => {
    const malformed = validateHostEventRun(
      {
        records: baseRecords(),
        scenario: baseScenario(),
        malformedObserverLines: 1,
      },
      EXPECTED,
    );
    expect(malformed.outcome).toBe("failed");
    expect(malformed.reasonCodes).toContain("MALFORMED_OBSERVER_RECORD");
    const dirty = validateHostEventRun(
      {
        records: baseRecords(),
        scenario: baseScenario(),
        sanitizationViolations: 1,
      },
      EXPECTED,
    );
    expect(dirty.outcome).toBe("failed");
    expect(dirty.reasonCodes).toContain("EVIDENCE_SANITIZATION_VIOLATION");
  });

  it("a refused handoff trigger is a blocked diagnostic, not a failure", () => {
    const scenario = baseScenario();
    scenario.scenario.handoff = { attempted: true, ok: false };
    const records = baseRecords().filter((r) => r.hostReason !== "handoff");
    const verdict = validateBase(records, scenario);
    expect(verdict.outcome).toBe("passed-with-diagnostics");
    expect(verdict.diagnostics).toContain("HANDOFF_TRIGGER_BLOCKED");
  });

  it("an absent optional credential_disabled event degrades to diagnostics only", () => {
    const records = baseRecords().filter(
      (r) => r.event !== "credential_disabled",
    );
    const verdict = validateBase(records);
    expect(verdict.outcome).toBe("passed-with-diagnostics");
    expect(verdict.diagnostics).toContain(
      "OPTIONAL_EVENT_ABSENT:credential_disabled",
    );
  });
});

describe("Feature: Host Event Surface — stderr sanitizer contract", () => {
  it("strips file URIs, known roots, and bare absolute paths from Host errors", () => {
    const raw =
      "Error: omp failed at file:///Users/alice/project/secret.ts:12\n" +
      "home=/Users/alice cwd=/Users/alice/project leftover=/var/tmp/x.log done";
    const out = sanitizeStderrText(raw, [
      ["/Users/alice/project", "<project-dir>"],
      ["/Users/alice", "<home>"],
    ]);
    expect(out).not.toContain("/Users/alice");
    expect(out).not.toContain("/var/tmp/x.log");
    expect(out).toContain("<file-uri>");
    expect(out).toContain("<project-dir>");
    expect(out).toContain("<path>");
    expect(out).toContain("omp failed at");
  });
});

describe("Feature: Host Event Surface — observer reason/toolName sanitization", () => {
  it("persists only allowlisted session_switch reasons; approval reasons and tool names are digests", async () => {
    const root = await mkdtemp(join(tmpdir(), "host-event-observer-"));
    const logPath = join(root, "observer.jsonl");
    const validatorPath = join(root, "validator-fixture.mjs");
    await writeFile(
      validatorPath,
      'export const ompExtensionV1Inventory = { version: "omp-extension-v1" };\n' +
        "export function validateOmpExtensionV1Event() { return {}; }\n",
      "utf8",
    );
    process.env.SPIKE_OBSERVER_LOG = logPath;
    process.env.HOST_EVENT_RUN_ID = RUN_ID;
    process.env.HOST_EVENT_VALIDATOR_MODULE = validatorPath;
    process.env.HOST_EVENT_OBSERVE_EVENTS = JSON.stringify([
      "session_switch",
      "tool_approval_resolved",
    ]);
    try {
      // Query-suffixed specifier: distinct module instance so the env
      // captured at module top level is the one set above. Must be a
      // static literal — vite cannot rewrite variable dynamic imports.
      const mod: { default: (pi: unknown) => void } = await import(
        "../scripts/p0/host-event/observer.mjs?case=sanitize"
      );
      const handlers = new Map<
        string,
        (event: unknown, ctx: unknown) => unknown
      >();
      mod.default({
        on: (
          name: string,
          handler: (event: unknown, ctx: unknown) => unknown,
        ) => handlers.set(name, handler),
      });
      const secretReason =
        "denied: reads /Users/alice/secret.txt for alice@example.com";
      handlers.get("session_switch")?.(
        { type: "session_switch", reason: "resume" },
        {},
      );
      handlers.get("session_switch")?.(
        { type: "session_switch", reason: secretReason },
        {},
      );
      handlers.get("tool_approval_resolved")?.(
        {
          type: "tool_approval_resolved",
          sessionId: "s",
          toolCallId: "c",
          toolName: "bash",
          approved: false,
          reason: secretReason,
        },
        {},
      );
      const raw = await readFile(logPath, "utf8");
      expect(raw).not.toContain("/Users/alice");
      expect(raw).not.toContain("alice@example.com");
      expect(raw).not.toContain("bash");
      const lines = raw
        .trim()
        .split("\n")
        .map((line) => JSON.parse(line) as Record<string, unknown>);
      const switches = lines.filter((l) => l.event === "session_switch");
      expect(switches).toHaveLength(2);
      expect(switches[0]?.hostReason).toBe("resume");
      expect(switches[1]?.hostReason).toBeUndefined();
      expect(switches[1]?.hostReasonDigest).toBe(d(secretReason));
      const approval = lines.find((l) => l.event === "tool_approval_resolved");
      expect(approval?.hostReason).toBeUndefined();
      expect(approval?.hostReasonDigest).toBe(d(secretReason));
      expect(approval?.toolName).toBeUndefined();
      expect(approval?.toolNameDigest).toBe(d("bash"));
    } finally {
      delete process.env.SPIKE_OBSERVER_LOG;
      delete process.env.HOST_EVENT_RUN_ID;
      delete process.env.HOST_EVENT_VALIDATOR_MODULE;
      delete process.env.HOST_EVENT_OBSERVE_EVENTS;
    }
  });
});

describe("Feature: Host Event Surface — evidence bundle and content addressing", () => {
  it("persists a sanitized bundle under its own sha256, idempotently", async () => {
    const verdict = validateBase(baseRecords());
    const bundle = buildLocalObservationBundle({
      verdict,
      expectation: EXPECTED,
      sources: {
        observerLogSha256: d("observer-log"),
        driverLogSha256: d("driver-log"),
        scenarioSha256: d("scenario"),
      },
    });
    expect(() => hostEventEvidenceBundleSchema.parse(bundle)).not.toThrow();
    expect(JSON.stringify(bundle)).not.toContain("certified");

    const root = await mkdtemp(join(tmpdir(), "host-event-evidence-"));
    const first = await writeLocalObservationEvidence(root, bundle);
    expect(first.wrote).toBe(true);
    expect(basename(first.dir)).toBe(first.digest);
    const persisted: unknown = JSON.parse(
      await readFile(join(first.dir, "evidence.json"), "utf8"),
    );
    expect(persisted).toEqual(bundle);

    const second = await writeLocalObservationEvidence(root, bundle);
    expect(second.wrote).toBe(false);
    expect(second.dir).toBe(first.dir);
  });
});

describe("Feature: Host Event Surface — driver-side Host identity recomputation", () => {
  it("hashes the resolved entrypoint and walks up to the owning package", async () => {
    const root = await mkdtemp(join(tmpdir(), "host-event-identity-"));
    const pkgDir = join(root, "node_modules", "@oh-my-pi", "pi-coding-agent");
    const distDir = join(pkgDir, "dist");
    await mkdir(distDir, { recursive: true });
    await writeFile(join(distDir, "cli.js"), "// fake omp cli\n", "utf8");
    const manifest = `${JSON.stringify({ name: "@oh-my-pi/pi-coding-agent", version: "17.3.5" })}\n`;
    await writeFile(join(pkgDir, "package.json"), manifest, "utf8");
    const identity = recomputeHostIdentity(join(distDir, "cli.js"));
    expect(identity.packageVersion).toBe("17.3.5");
    expect(identity.entrypointSha256).toBe(d("// fake omp cli\n"));
    expect(identity.packageJsonSha256).toBe(d(manifest));
  });
});

describe("Feature: Host Event Surface — suite stays out of the npm package", () => {
  it("the package files whitelist excludes scripts/** suite assets", async () => {
    const pkg: unknown = JSON.parse(
      await readFile(join(PLUGIN_ROOT, "package.json"), "utf8"),
    );
    if (pkg === null || typeof pkg !== "object" || !("files" in pkg))
      throw new Error("package.json files whitelist missing");
    const files: unknown = pkg.files;
    if (!Array.isArray(files) || files.some((f) => typeof f !== "string"))
      throw new Error("package.json files must be a string array");
    for (const entry of files) {
      if (typeof entry !== "string") continue;
      expect(entry === "scripts" || entry.startsWith("scripts/")).toBe(false);
    }
    for (const asset of [
      "scripts/p0/host-event/observer.mjs",
      "scripts/p0/host-event/driver-ext.mjs",
      "scripts/p0/host-event/drive.mjs",
      "scripts/p0/host-event/lib.mjs",
      "scripts/p0/host-event/validate.ts",
      "scripts/p0/host-event/run-live-cell.ts",
    ]) {
      // The suite exists on disk and every path is under the excluded
      // scripts/ tree, so none of it can enter the packed tarball.
      expect(asset.startsWith("scripts/")).toBe(true);
      await expect(
        readFile(join(PLUGIN_ROOT, asset), "utf8"),
      ).resolves.toBeTypeOf("string");
    }
  });
});

describe("Feature: Host Event Surface — failed driver cannot score leftover records", () => {
  const writePassingLeftovers = async (runDir: string) => {
    await mkdir(join(runDir, "out"), { recursive: true });
    await writeFile(
      join(runDir, "out", "observer.jsonl"),
      `${baseRecords()
        .map((record) => JSON.stringify(record))
        .join("\n")}\n`,
      "utf8",
    );
    await writeFile(join(runDir, "out", "driver.jsonl"), "{}\n", "utf8");
    await writeFile(
      join(runDir, "out", "scenario.json"),
      `${JSON.stringify(baseScenario())}\n`,
      "utf8",
    );
  };

  it("leftover records that would pass stay blocked on a nonzero driver", async () => {
    expect(validateBase(baseRecords()).outcome).toBe("passed");
    const runDir = await mkdtemp(join(tmpdir(), "host-event-driver-exit-"));
    await writePassingLeftovers(runDir);
    const result = await completeLiveCellAfterDriver({
      drive: { code: 1, timedOut: false, spawnFailed: false },
      runId: RUN_ID,
      runDir,
      expectation: EXPECTED,
    });
    expect(result.outcome).toBe("blocked");
    expect(result.blockedReason).toBe("DRIVER_EXIT_NONZERO");
    expect(result.verdict).toBeUndefined();
    expect(result.evidence).toBeUndefined();
    expect(result.bundle).toBeUndefined();
  });

  it("leftover records stay blocked on a null driver exit", async () => {
    const runDir = await mkdtemp(join(tmpdir(), "host-event-driver-null-"));
    await writePassingLeftovers(runDir);
    const result = await completeLiveCellAfterDriver({
      drive: { code: null, timedOut: false, spawnFailed: false },
      runId: RUN_ID,
      runDir,
      expectation: EXPECTED,
    });
    expect(result.outcome).not.toBe("passed");
    expect(result.outcome).not.toBe("passed-with-diagnostics");
    expect(result.outcome).toBe("blocked");
    expect(result.blockedReason).toBe("DRIVER_EXIT_NONZERO");
  });
});

describe("Feature: Host Event Surface — packed controller fail-closed probe", () => {
  const writeRuntimeIndex = async (content: string): Promise<string> => {
    const root = await mkdtemp(join(tmpdir(), "host-event-probe-"));
    const indexPath = join(root, "index.mjs");
    await writeFile(indexPath, content, "utf8");
    return indexPath;
  };

  it("accepts a packed controller that throws before registerCommand without `on`", async () => {
    const indexPath = await writeRuntimeIndex(
      "export function registerRuntimeController(host) {\n" +
        '  if (typeof host.on !== "function") throw new Error("missing on");\n' +
        '  host.registerCommand("sbtd", {});\n' +
        "}\n",
    );
    await expect(
      assertPackedControllerFailClosed(indexPath),
    ).resolves.toBeUndefined();
  });

  it("rejects a fail-open pack that registers without `on`", async () => {
    const indexPath = await writeRuntimeIndex(
      'export function registerRuntimeController(host) { host.registerCommand("sbtd", {}); }\n',
    );
    await expect(assertPackedControllerFailClosed(indexPath)).rejects.toThrow(
      "SUBJECT_STALE:packed-controller-fail-open-without-on",
    );
  });

  it("rejects a pack whose runtime index lacks the controller export", async () => {
    const indexPath = await writeRuntimeIndex("export const unrelated = 1;\n");
    await expect(assertPackedControllerFailClosed(indexPath)).rejects.toThrow(
      "SUBJECT_STALE:packed-runtime-index-missing-controller",
    );
  });
});

describe("Feature: Host Event Surface — setup blockedReason stays a stable code", () => {
  const stageTarball = async (
    files: Record<string, string>,
  ): Promise<{ root: string; tgz: string }> => {
    const root = await mkdtemp(join(tmpdir(), "host-event-pack-"));
    const stage = join(root, "stage");
    for (const [name, content] of Object.entries(files)) {
      await mkdir(dirname(join(stage, name)), { recursive: true });
      await writeFile(join(stage, name), content, "utf8");
    }
    const tgz = join(root, "subject.tgz");
    execFileSync("tar", ["-czf", tgz, "-C", stage, ...Object.keys(files)]);
    return { root, tgz };
  };

  it("subjectStaleBlockedReason keeps SUBJECT_STALE:* and drops raw error text", () => {
    expect(
      subjectStaleBlockedReason(
        new Error("SUBJECT_STALE:tarball-missing-runtime-index"),
      ),
    ).toBe("SUBJECT_STALE:tarball-missing-runtime-index");
    expect(
      subjectStaleBlockedReason(
        new Error("tar: /Users/alice/x.tgz: Not found"),
      ),
    ).toBe("SUBJECT_STALE");
    expect(subjectStaleBlockedReason(null)).toBe("SUBJECT_STALE");
  });

  it("a corrupt subject tarball blocks with bare SUBJECT_STALE, never tar error text", async () => {
    const root = await mkdtemp(join(tmpdir(), "host-event-stale-"));
    const tgz = join(root, "subject.tgz");
    await writeFile(tgz, "not a gzip tarball\n", "utf8");
    const result = await runLiveCell({
      ompBin: join(root, "no-omp"),
      pluginTarball: tgz,
      runsRoot: join(root, "runs"),
    });
    expect(result.outcome).toBe("blocked");
    expect(result.blockedReason).toBe("SUBJECT_STALE");
    expect(result.blockedReason ?? "").not.toContain(root);
  });

  it("a tarball missing the Slice 4 seam keeps its SUBJECT_STALE:* code", async () => {
    const { root, tgz } = await stageTarball({
      "package/dist/runtime/index.js": "// probeOmpExtensionV1Capabilities\n",
    });
    const result = await runLiveCell({
      ompBin: join(root, "no-omp"),
      pluginTarball: tgz,
      runsRoot: join(root, "runs"),
    });
    expect(result.outcome).toBe("blocked");
    expect(result.blockedReason).toBe(
      "SUBJECT_STALE:tarball-missing-omp-extension-v1",
    );
  });

  it(
    "a subject that fails installation blocks with PLUGIN_INSTALL_FAILED only",
    { timeout: 60_000 },
    async () => {
      // Seam-complete but not an installable package (no package.json in
      // the tarball), so npm-offline-v1 install fails closed.
      const { root, tgz } = await stageTarball({
        "package/dist/runtime/omp-extension-v1.js": "// seam\n",
        "package/dist/runtime/index.js": "// probeOmpExtensionV1Capabilities\n",
      });
      const pkgDir = join(
        root,
        "runtime",
        "node_modules",
        "@oh-my-pi",
        "pi-coding-agent",
      );
      await mkdir(join(pkgDir, "dist"), { recursive: true });
      await writeFile(
        join(pkgDir, "dist", "cli.js"),
        "// fake omp cli\n",
        "utf8",
      );
      await writeFile(
        join(pkgDir, "package.json"),
        `${JSON.stringify({ name: "@oh-my-pi/pi-coding-agent", version: "17.3.5" })}\n`,
        "utf8",
      );
      const result = await runLiveCell({
        ompBin: join(pkgDir, "dist", "cli.js"),
        pluginTarball: tgz,
        runsRoot: join(root, "runs"),
      });
      expect(result.outcome).toBe("blocked");
      expect(result.blockedReason).toBe("PLUGIN_INSTALL_FAILED");
      expect(result.blockedReason ?? "").not.toContain(root);
    },
  );
});

// ---------------------------------------------------------------------------
// Live Host cell — env-gated; never runs in the default 30s suite.
// ---------------------------------------------------------------------------
const liveOmpBin = process.env.SPIKE_OMP_BIN;
const liveTarball = process.env.HOST_EVENT_PLUGIN_TARBALL;
const liveEnabled =
  typeof liveOmpBin === "string" &&
  liveOmpBin.length > 0 &&
  typeof liveTarball === "string" &&
  liveTarball.length > 0;

describe.skipIf(!liveEnabled)(
  "Feature: Host Event Surface — live real-Host cell (env-gated)",
  () => {
    it(
      "one fresh isolated cell passes (or reports blocked), never failed",
      { timeout: 300_000 },
      async () => {
        if (typeof liveOmpBin !== "string" || typeof liveTarball !== "string")
          return;
        const result = await runLiveCell({
          ompBin: liveOmpBin,
          pluginTarball: liveTarball,
          runsRoot: process.env.HOST_EVENT_RUNS_ROOT,
        });
        if (result.outcome === "blocked") {
          // Environment/trigger unavailable: recorded, never faked.
          console.warn(`live cell blocked: ${result.blockedReason ?? ""}`);
          return;
        }
        expect(result.outcome).not.toBe("failed");
        expect(result.reasonCodes).toEqual([]);
        expect(result.evidence?.wrote).toBe(true);
        expect(JSON.stringify(result.bundle ?? {})).not.toContain("certified");
      },
    );
  },
);
