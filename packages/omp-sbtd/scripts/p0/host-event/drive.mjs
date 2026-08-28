#!/usr/bin/env node
// Slice 5 Host Event Surface suite — deterministic Host driver (promoted from
// the Gate 0.2 spike driver).
// Drives a real OMP 17.3.5 Host (spawned in --mode rpc-ui) through its public
// RPC surface plus one public ExtensionCommandContext API (navigateTree, via
// the companion /spike command). A loopback-only stub implements the OpenAI
// chat-completions endpoint so no real Provider credential is needed.
// It never calls Plugin handlers and never emits synthetic Host events.
//
// Slice 5 changes vs the spike:
// - No REQUIRED_EVENTS list here: the suite's single event list is
//   `ompExtensionV1Inventory`, delivered to the observer by the runner through
//   HOST_EVENT_OBSERVE_EVENTS. Scoring/verdicts moved to the TS evidence
//   validator (validate.ts); this driver only drives and records.
// - Every run is bound to HOST_EVENT_RUN_ID; a run dir that already contains a
//   completed scenario.json is refused so logs are never shared across runs.
// - The scenario additionally attempts the public RPC `handoff` command to
//   cover session_switch reason "handoff"; a refused/unsupported attempt is
//   recorded as a blocked cell, never faked.
//
// Required env: SPIKE_OMP_BIN, SPIKE_PLUGIN_EXT, SPIKE_RUN_DIR,
//   HOST_EVENT_RUN_ID, HOST_EVENT_OBSERVE_EVENTS (JSON string array).
// Optional env: HOST_EVENT_VALIDATOR_MODULE (defaults to the sibling
//   dist/runtime/omp-extension-v1.js of SPIKE_PLUGIN_EXT).
// Writes: <SPIKE_RUN_DIR>/out/{driver.jsonl,observer.jsonl,driver-ext.jsonl,
//   scenario.json}. Analysis/verdicts are the evidence validator's job.
import { spawn } from "node:child_process";
import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sanitizeStderrText, sha256 } from "./lib.mjs";

const env = (name) => {
  const value = process.env[name];
  if (typeof value !== "string" || value.length === 0)
    throw new Error(`missing env ${name}`);
  return value;
};

const OMP_BIN = env("SPIKE_OMP_BIN");
const PLUGIN_EXT = env("SPIKE_PLUGIN_EXT");
const RUN_DIR = env("SPIKE_RUN_DIR");
const RUN_ID = env("HOST_EVENT_RUN_ID");
const OBSERVE_EVENTS = env("HOST_EVENT_OBSERVE_EVENTS");
const VALIDATOR_MODULE =
  process.env.HOST_EVENT_VALIDATOR_MODULE ??
  join(dirname(PLUGIN_EXT), "runtime", "omp-extension-v1.js");
const SUITE_DIR = dirname(fileURLToPath(import.meta.url));
const OBSERVER_EXT = join(SUITE_DIR, "observer.mjs");
const DRIVER_EXT = join(SUITE_DIR, "driver-ext.mjs");
const OBSERVER_LOG = join(RUN_DIR, "out", "observer.jsonl");
const DRIVER_LOG = join(RUN_DIR, "out", "driver.jsonl");
const DRIVER_EXT_LOG = join(RUN_DIR, "out", "driver-ext.jsonl");
const SCENARIO_JSON = join(RUN_DIR, "out", "scenario.json");
const HOME_DIR = join(RUN_DIR, "home");
const AGENT_DIR = join(RUN_DIR, "agent");
const PROJECT_DIR = join(RUN_DIR, "project");

// A completed run dir is immutable: refuse to share/truncate another run's
// logs. The runner creates a fresh content-scoped run dir per cell.
if (existsSync(SCENARIO_JSON))
  throw new Error(
    "run dir already contains a completed scenario.json; use a fresh SPIKE_RUN_DIR per run",
  );
for (const dir of [
  join(RUN_DIR, "out"),
  HOME_DIR,
  AGENT_DIR,
  join(PROJECT_DIR, ".omp"),
])
  mkdirSync(dir, { recursive: true });

const t0 = Date.now();
const dlog = (entry) =>
  appendFileSync(
    DRIVER_LOG,
    `${JSON.stringify({ atMs: Date.now() - t0, runId: RUN_ID, ...entry })}\n`,
    "utf8",
  );
writeFileSync(DRIVER_LOG, "");
writeFileSync(OBSERVER_LOG, "");
writeFileSync(DRIVER_EXT_LOG, "");

// ---------------------------------------------------------------------------
// Deterministic loopback LLM stub (OpenAI chat-completions shape)
// ---------------------------------------------------------------------------
const TOOL_PLAIN = "spike_echo";
const TOOL_GUARDED = "spike_guarded";
// Suite-owned risk classification for exactly the tools this suite registers,
// keyed by hashed toolName. Host 17.3.5 tool events carry no risk-class
// field, so the binding evidence derives the class from this driver-owned
// map, never from a Host payload field.
const TOOL_RISK_CLASSES = {
  [sha256(TOOL_PLAIN)]: "no-approval",
  [sha256(TOOL_GUARDED)]: "prompt",
};
let completionCount = 0;

const lastUserText = (messages) => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m?.role !== "user") continue;
    if (typeof m.content === "string") return m.content;
    if (Array.isArray(m.content))
      return m.content
        .filter((c) => c?.type === "text")
        .map((c) => c.text)
        .join("\n");
  }
  return "";
};
// A turn continues after a tool reply: answer with plain text only when the
// LAST message is the tool reply, so later prompts can still trigger tools.
const lastIsToolReply = (messages) =>
  messages[messages.length - 1]?.role === "tool";

const planCompletion = (body) => {
  completionCount += 1;
  const messages = Array.isArray(body.messages) ? body.messages : [];
  const text = lastUserText(messages);
  if (lastIsToolReply(messages)) return { text: "SPIKE_TOOL_DONE" };
  if (text.includes("SPIKE_TOOL_GUARDED"))
    return {
      tool: TOOL_GUARDED,
      args: JSON.stringify({ value: "guarded" }),
      id: `call_spike_${completionCount}`,
    };
  if (text.includes("SPIKE_TOOL_PLAIN"))
    return {
      tool: TOOL_PLAIN,
      args: JSON.stringify({ value: "plain" }),
      id: `call_spike_${completionCount}`,
    };
  return { text: "SPIKE_OK" };
};

const sseChunk = (obj) => `data: ${JSON.stringify(obj)}\n\n`;
const baseChunk = (body) => ({
  id: `chatcmpl-spike-${completionCount}`,
  object: "chat.completion.chunk",
  created: 1_700_000_000,
  model: body.model ?? "spike-1",
});

const writeCompletion = (res, body, plan) => {
  const usage = { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 };
  if (body.stream) {
    res.writeHead(200, { "content-type": "text/event-stream" });
    if (plan.tool) {
      res.write(
        sseChunk({
          ...baseChunk(body),
          choices: [
            {
              index: 0,
              delta: {
                role: "assistant",
                tool_calls: [
                  {
                    index: 0,
                    id: plan.id,
                    type: "function",
                    function: { name: plan.tool, arguments: "" },
                  },
                ],
              },
              finish_reason: null,
            },
          ],
        }),
      );
      res.write(
        sseChunk({
          ...baseChunk(body),
          choices: [
            {
              index: 0,
              delta: {
                tool_calls: [{ index: 0, function: { arguments: plan.args } }],
              },
              finish_reason: null,
            },
          ],
        }),
      );
      res.write(
        sseChunk({
          ...baseChunk(body),
          choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }],
          usage,
        }),
      );
    } else {
      res.write(
        sseChunk({
          ...baseChunk(body),
          choices: [
            {
              index: 0,
              delta: { role: "assistant", content: plan.text },
              finish_reason: null,
            },
          ],
        }),
      );
      res.write(
        sseChunk({
          ...baseChunk(body),
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
          usage,
        }),
      );
    }
    res.write("data: [DONE]\n\n");
    res.end();
    return;
  }
  const message = plan.tool
    ? {
        role: "assistant",
        content: null,
        tool_calls: [
          {
            id: plan.id,
            type: "function",
            function: { name: plan.tool, arguments: plan.args },
          },
        ],
      }
    : { role: "assistant", content: plan.text };
  res.writeHead(200, { "content-type": "application/json" });
  res.end(
    JSON.stringify({
      id: `chatcmpl-spike-${completionCount}`,
      object: "chat.completion",
      created: 1_700_000_000,
      model: body.model ?? "spike-1",
      choices: [
        {
          index: 0,
          message,
          finish_reason: plan.tool ? "tool_calls" : "stop",
        },
      ],
      usage,
    }),
  );
};

const stub = createServer((req, res) => {
  if (req.method === "POST" && req.url?.startsWith("/v1/chat/completions")) {
    let body = "";
    req.on("data", (c) => {
      body += c;
      if (body.length > 1024 * 1024) req.destroy();
    });
    req.on("end", () => {
      try {
        const parsed = JSON.parse(body);
        dlog({
          kind: "llm_request",
          n: completionCount + 1,
          stream: parsed.stream === true,
        });
        writeCompletion(res, parsed, planCompletion(parsed));
      } catch (error) {
        res.writeHead(400).end(`bad request: ${error}`);
      }
    });
    return;
  }
  res.writeHead(404).end("not found");
});

await new Promise((r) => stub.listen(0, "127.0.0.1", r));
const stubPort = stub.address().port;
dlog({ kind: "stub_listening", port: stubPort });

// ---------------------------------------------------------------------------
// Isolated Host configuration
// ---------------------------------------------------------------------------
writeFileSync(
  join(AGENT_DIR, "models.yml"),
  [
    "providers:",
    "  spike:",
    `    baseUrl: http://127.0.0.1:${stubPort}/v1`,
    "    api: openai-completions",
    "    auth: none",
    "    models:",
    "      - id: spike-1",
    "        name: Spike Deterministic",
    "        supportsTools: true",
    "        contextWindow: 128000",
    "        maxTokens: 4096",
    "        input: [text]",
    "        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }",
    "",
  ].join("\n"),
  "utf8",
);
writeFileSync(
  join(PROJECT_DIR, ".omp", "config.yml"),
  [
    "disabledProviders:",
    "  - ollama",
    "  - llama.cpp",
    "  - lm-studio",
    "tools:",
    "  approval:",
    `    ${TOOL_GUARDED}: prompt`,
    // Tiny keep-recent window so the explicit compact entry always has
    // material to summarize in a deterministic stub session.
    "compaction:",
    "  keepRecentTokens: 1",
    "",
  ].join("\n"),
  { encoding: "utf8" },
);

// ---------------------------------------------------------------------------
// RPC client
// ---------------------------------------------------------------------------
const child = spawn(
  OMP_BIN,
  [
    "--mode",
    "rpc-ui",
    "--cwd",
    PROJECT_DIR,
    "--no-tools",
    "--no-skills",
    "--no-rules",
    "--no-pty",
    "--no-title",
    "--extension",
    PLUGIN_EXT,
    "--extension",
    OBSERVER_EXT,
    "--extension",
    DRIVER_EXT,
  ],
  {
    cwd: PROJECT_DIR,
    detached: true,
    env: {
      PATH: process.env.PATH ?? "",
      HOME: HOME_DIR,
      XDG_CACHE_HOME: join(HOME_DIR, ".cache"),
      XDG_CONFIG_HOME: join(HOME_DIR, ".config"),
      XDG_DATA_HOME: join(HOME_DIR, ".local", "share"),
      PI_CODING_AGENT_DIR: AGENT_DIR,
      CI: "1",
      NO_COLOR: "1",
      SPIKE_OBSERVER_LOG: OBSERVER_LOG,
      SPIKE_DRIVER_EXT_LOG: DRIVER_EXT_LOG,
      HOST_EVENT_RUN_ID: RUN_ID,
      HOST_EVENT_OBSERVE_EVENTS: OBSERVE_EVENTS,
      HOST_EVENT_VALIDATOR_MODULE: VALIDATOR_MODULE,
    },
    stdio: ["pipe", "pipe", "pipe"],
  },
);
let stderrTail = "";
child.stderr.setEncoding("utf8");
child.stderr.on("data", (c) => {
  stderrTail = (stderrTail + c).slice(-4096);
});

const sanitizeStderr = (text) =>
  sanitizeStderrText(text, [
    [OMP_BIN, "<omp-bin>"],
    [PLUGIN_EXT, "<plugin-ext>"],
    [VALIDATOR_MODULE, "<validator-module>"],
    [HOME_DIR, "<home>"],
    [AGENT_DIR, "<agent-dir>"],
    [PROJECT_DIR, "<project-dir>"],
    [RUN_DIR, "<run-dir>"],
    [process.env.HOME, "<home>"],
  ]);

let nextId = 0;
const pending = new Map();
let buffer = "";
let ready = false;
const terminalWaiters = [];
let nextApprovalChoice = "Approve";
const uiRequests = [];
const hostToolCalls = [];

const failAll = (error) => {
  for (const [, p] of pending) p.reject(error);
  pending.clear();
  for (const w of terminalWaiters.splice(0)) w.reject(error);
};

child.on("close", (code, signal) => {
  dlog({ kind: "child_close", code, signal });
  failAll(
    new Error(
      `omp closed early code=${code} signal=${signal} stderr=${sanitizeStderr(stderrTail.slice(-800))}`,
    ),
  );
});

const send = (obj) => child.stdin.write(`${JSON.stringify(obj)}\n`);

const command = (type, payload = {}, timeoutMs = 30_000) => {
  const id = `spike-${++nextId}`;
  const { promise, resolve: res, reject: rej } = Promise.withResolvers();
  pending.set(id, { resolve: res, reject: rej, type });
  send({ id, type, ...payload });
  const timer = setTimeout(() => {
    if (pending.delete(id)) rej(new Error(`timeout waiting ${type}`));
  }, timeoutMs);
  return promise.finally(() => clearTimeout(timer));
};

const waitTerminal = (timeoutMs = 60_000) => {
  const { promise, resolve: res, reject: rej } = Promise.withResolvers();
  terminalWaiters.push({ resolve: res, reject: rej });
  const timer = setTimeout(
    () => rej(new Error("timeout waiting agent_end terminal")),
    timeoutMs,
  );
  return promise.finally(() => clearTimeout(timer));
};

const handleUiRequest = (frame) => {
  uiRequests.push({
    method: frame.method,
    title: typeof frame.title === "string" ? sha256(frame.title) : undefined,
  });
  if (frame.method === "select") {
    send({
      type: "extension_ui_response",
      id: frame.id,
      value: nextApprovalChoice,
    });
    return;
  }
  if (frame.method === "confirm") {
    send({ type: "extension_ui_response", id: frame.id, confirmed: true });
    return;
  }
  send({ type: "extension_ui_response", id: frame.id, cancelled: true });
};

const handleHostToolCall = (frame) => {
  hostToolCalls.push({
    toolName: frame.toolName,
    toolCallDigest: sha256(String(frame.toolCallId)),
  });
  const ok = frame.toolName === TOOL_PLAIN || frame.toolName === TOOL_GUARDED;
  send({
    type: "host_tool_result",
    id: frame.id,
    result: {
      content: [
        { type: "text", text: ok ? "SPIKE_TOOL_OUTPUT" : "SPIKE_UNKNOWN_TOOL" },
      ],
      details: { spike: true },
    },
    isError: !ok,
  });
};

child.stdout.setEncoding("utf8");
child.stdout.on("data", (chunk) => {
  buffer += chunk;
  for (;;) {
    const nl = buffer.indexOf("\n");
    if (nl < 0) break;
    const line = buffer.slice(0, nl).trim();
    buffer = buffer.slice(nl + 1);
    if (line.length === 0) continue;
    let frame;
    try {
      frame = JSON.parse(line);
    } catch {
      dlog({ kind: "non_json_line", length: line.length });
      continue;
    }
    const type = frame?.type;
    if (type === "ready") {
      ready = true;
      dlog({ kind: "ready", protocolVersion: frame.protocolVersion });
      continue;
    }
    if (type === "response" || type === "prompt_result") {
      const p = pending.get(frame.id);
      if (p) {
        pending.delete(frame.id);
        if (frame.success === false)
          p.reject(
            new Error(`${p.type} failed: ${frame.error} ${frame.code ?? ""}`),
          );
        else
          p.resolve(
            frame.data ??
              (type === "prompt_result"
                ? { agentInvoked: frame.agentInvoked }
                : undefined),
          );
      }
      continue;
    }
    if (type === "extension_ui_request") {
      handleUiRequest(frame);
      continue;
    }
    if (type === "host_tool_call") {
      handleHostToolCall(frame);
      continue;
    }
    if (type === "agent_end") {
      if (frame.isTerminal !== false)
        for (const w of terminalWaiters.splice(0)) w.resolve();
    }
    // All other streaming frames are intentionally ignored.
  }
});

const waitReady = async (timeoutMs = 30_000) => {
  const start = Date.now();
  while (!ready) {
    if (Date.now() - start > timeoutMs)
      throw new Error(
        `omp did not become ready; stderr=${sanitizeStderr(stderrTail.slice(-1200))}`,
      );
    await new Promise((r) => setTimeout(r, 25));
  }
};

const promptAndWait = async (message) => {
  const terminal = waitTerminal();
  const ack = await command("prompt", { message }, 60_000);
  if (ack?.agentInvoked !== false) await terminal;
  return ack;
};

// ---------------------------------------------------------------------------
// Scenario
// ---------------------------------------------------------------------------
const scenario = {};
try {
  await waitReady();
  scenario.ready = true;

  await command("set_auto_retry", { enabled: false });
  await command("set_host_tools", {
    tools: [
      {
        name: TOOL_PLAIN,
        label: "Spike Echo",
        description: "Deterministic read-only spike tool.",
        parameters: {
          type: "object",
          properties: { value: { type: "string" } },
          required: ["value"],
          additionalProperties: false,
        },
      },
      {
        name: TOOL_GUARDED,
        label: "Spike Guarded",
        description:
          "Deterministic spike tool gated by an approval prompt policy.",
        parameters: {
          type: "object",
          properties: { value: { type: "string" } },
          required: ["value"],
          additionalProperties: false,
        },
      },
    ],
  });
  scenario.hostTools = true;

  const commands = await command("get_available_commands");
  scenario.sbtdCommandRegistered = (commands?.commands ?? []).some(
    (c) => c.name === "sbtd",
  );
  scenario.spikeCommandRegistered = (commands?.commands ?? []).some(
    (c) => c.name === "spike",
  );

  const stateA = await command("get_state");
  scenario.sessionA = {
    idDigest: sha256(String(stateA.sessionId)),
    hasFile: typeof stateA.sessionFile === "string",
  };
  const sessionFileA = stateA.sessionFile;

  await promptAndWait("SPIKE_PLAIN one");
  scenario.plainTurn = true;

  await promptAndWait("call the tool now: SPIKE_TOOL_PLAIN");
  scenario.autoApprovedToolTurn = true;

  nextApprovalChoice = "Approve";
  await promptAndWait("call the tool now: SPIKE_TOOL_GUARDED");
  scenario.approvedToolTurn = true;

  nextApprovalChoice = "Deny";
  await promptAndWait("call the tool now: SPIKE_TOOL_GUARDED");
  scenario.deniedToolTurn = true;

  // Grow session A's history so the explicit compact entry has enough
  // material (prepareCompaction refuses branches that are too small).
  await promptAndWait("SPIKE_PLAIN extra");
  scenario.extraTurn = true;

  const compactResult = await command("compact", {}, 120_000);
  scenario.compact = {
    ok: true,
    resultKeys: Object.keys(compactResult ?? {}).sort(),
  };

  const newResult = await command("new_session");
  scenario.newSession = { cancelled: newResult?.cancelled };
  const stateB = await command("get_state");
  scenario.sessionB = {
    idDigest: sha256(String(stateB.sessionId)),
    distinctFromA:
      sha256(String(stateB.sessionId)) !== scenario.sessionA.idDigest,
  };

  await promptAndWait("SPIKE_PLAIN two");
  scenario.sessionBTurn = true;

  if (typeof sessionFileA !== "string")
    throw new Error("session A has no sessionFile; cannot resume");
  const switchResult = await command("switch_session", {
    sessionPath: sessionFileA,
  });
  scenario.resumeSession = { cancelled: switchResult?.cancelled };
  const stateA2 = await command("get_state");
  scenario.resumedA =
    sha256(String(stateA2.sessionId)) === scenario.sessionA.idDigest;

  const branchMessages = await command("get_branch_messages");
  const entries = (branchMessages?.messages ?? [])
    .map((m) => m.entryId)
    .filter((v) => typeof v === "string");
  scenario.branchEntries = entries.length;
  if (entries.length < 2)
    throw new Error(`need >=2 branchable entries, got ${entries.length}`);

  // session_tree has no RPC command; drive the public Host navigation API
  // through the /spike extension command (Host emits the real event). Move
  // the active leaf to an earlier entry while the full tree is present.
  const treeTarget = entries[0];
  const treeTerminal = waitTerminal(15_000).catch(() => "no-terminal");
  await command("prompt", { message: `/spike tree ${treeTarget}` }, 30_000);
  await treeTerminal;
  scenario.treeNavigation = true;

  const branchResult = await command("branch", {
    entryId: entries[entries.length - 1],
  });
  scenario.branch = { cancelled: branchResult?.cancelled };

  await promptAndWait("SPIKE_PLAIN three");
  scenario.postBranchTurn = true;

  await promptAndWait("SPIKE_PLAIN four");
  scenario.postCompactTurn = true;

  // session_switch reason "handoff": the RPC union exposes `handoff`; it
  // generates the handoff document through the same deterministic stub model
  // and starts a new Session inside this same Host process. If the public
  // command refuses the attempt, record a blocked cell — never fake it.
  try {
    const handoffResult = await command(
      "handoff",
      { customInstructions: "SPIKE_HANDOFF" },
      120_000,
    );
    scenario.handoff = {
      attempted: true,
      ok: handoffResult !== null && handoffResult !== undefined,
      resultKeys: Object.keys(handoffResult ?? {}).sort(),
    };
  } catch (error) {
    scenario.handoff = {
      attempted: true,
      ok: false,
      errorName: error instanceof Error ? error.name : "unknown",
      error: sanitizeStderr(
        error instanceof Error ? error.message : String(error),
      ),
    };
  }
} catch (error) {
  // Host/RPC error text can embed local paths or file URIs; scenario.json is
  // evidence input, so only sanitized text is ever stored.
  scenario.error = sanitizeStderr(
    error instanceof Error ? error.message : String(error),
  );
} finally {
  try {
    child.stdin.end();
  } catch {
    // ignore
  }
  const killer = setTimeout(() => {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      // ignore
    }
  }, 3_000);
  child.once("close", () => clearTimeout(killer));
}

stub.close();

// ---------------------------------------------------------------------------
// Run record (verdicts are the evidence validator's job, not the driver's)
// ---------------------------------------------------------------------------
const driverExtDiagnostics = readFileSync(DRIVER_EXT_LOG, "utf8")
  .split("\n")
  .filter((l) => l.length > 0)
  .map((l) => JSON.parse(l));

writeFileSync(
  SCENARIO_JSON,
  `${JSON.stringify(
    {
      runId: RUN_ID,
      toolRiskClasses: TOOL_RISK_CLASSES,
      scenario,
      uiRequestsSeen: uiRequests.length,
      hostToolCalls,
      driverExtDiagnostics,
    },
    null,
    2,
  )}\n`,
  "utf8",
);
console.log(
  JSON.stringify({
    runId: RUN_ID,
    scenarioOk: scenario.error === undefined,
    uiRequestsSeen: uiRequests.length,
    hostToolCallsSeen: hostToolCalls.length,
  }),
);
