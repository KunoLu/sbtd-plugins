import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { once } from "node:events";
import { afterEach, describe, expect, it } from "vitest";
import { currentPublicSbtdReport } from "../../../test/fixtures/p0-reports.ts";
import {
  assertRequestedHostVersion,
  runCommandSurfaceSession,
  scoreCommandSurfaceRecord,
} from "./run-command-surface-cell.ts";

const children: ChildProcessWithoutNullStreams[] = [];
afterEach(async () => {
  for (const child of children.splice(0)) {
    if (child.exitCode !== null || child.signalCode !== null) continue;
    const closed = once(child, "close");
    child.kill("SIGKILL");
    await closed;
  }
});
// A local protocol fixture, NOT an OMP/SDK/provider or trusted §4 run.
function fixture(mode: string): ChildProcessWithoutNullStreams {
  const script = `
    import { createInterface } from 'node:readline';
    const mode = ${JSON.stringify(mode)};
    const report = ${JSON.stringify(currentPublicSbtdReport())};
    const send = value => process.stdout.write(JSON.stringify(value) + '\\n');
    process.stdin.on('end', () => {
      if (mode === 'exit-nonzero') process.exitCode = 7;
      if (mode === 'exit-signal') process.kill(process.pid, 'SIGTERM');
      // Deliberate OS integration: EOF must not be mistaken for child close.
      if (mode === 'hold-open') setInterval(() => {}, 1000);
      if (mode === 'late-error') send({type:'extension_error', error:'fixture'});
      if (mode === 'truncated-on-exit') process.stdout.write('{');
    });
    createInterface({ input: process.stdin }).on('line', line => {
      const request = JSON.parse(line);
      if (request.type !== 'prompt') {
        send({type:'response', id:request.id, command:request.type, success:true,
          data: request.type === 'get_available_commands' ? {commands:[{name:'sbtd'}]} : undefined});
        return;
      }
      if (mode === 'early-close') { process.exit(0); }
      if (mode === 'malformed') process.stdout.write('not-json\\n');
      const notify = () => {
        const message = request.message === '/sbtd help'
          ? 'Usage: /sbtd help [command]\\nUsage: /sbtd report'
          : request.message === '/sbtd status'
            ? 'Runtime Mode: advisory\\nPolicy Profile: strict'
            : request.message === '/sbtd report' ? report
              : JSON.stringify({digest:'a'.repeat(64), targets:[{path:'relative-target'}]});
        if (mode !== 'missing-content') send({type:'extension_ui_request', method:'notify',
          message: mode === 'wrong-content' ? 'wrong' : mode === 'sensitive' ? '/home/runner/private' : message});
      };
      const ack = {type:'response', id:request.id, command: mode === 'ack-wrong-command' ? 'other' : 'prompt', success:mode !== 'ack-error'};
      if (mode === 'ack-agent') ack.data = {agentInvoked:true};
      const terminal = {type:'prompt_result', id:mode === 'wrong-id' ? 'foreign' : request.id,
        status:mode === 'aborted' ? 'aborted' : mode === 'terminal-error' ? 'error' : 'completed',
        sessionSettled:mode !== 'unsettled', agentInvoked:mode === 'terminal-agent'};
      if (mode === 'terminal-error') terminal.error = {message:'fixture',retryable:false};
      if (mode === 'missing-settled') delete terminal.sessionSettled;
      if (mode === 'missing-agent') delete terminal.agentInvoked;
      if (mode === 'notification-first') notify();
      if (mode !== 'terminal-only') send(ack);
      if (['agent_start','agent_end','message_update','model_start','extension_error'].includes(mode)) send({type:mode});
      if (mode === 'interactive') send({type:'extension_ui_request', method:'confirm', id:'ui'});
      if (mode !== 'ack-only') send(terminal);
      if (mode !== 'notification-first') notify();
    });
    send({type:'ready'});
  `;
  const child = spawn(process.execPath, ["--input-type=module", "-e", script], {
    detached: true,
    env: {},
    stdio: ["pipe", "pipe", "pipe"],
  });
  children.push(child);
  return child;
}
function verdict(result: Awaited<ReturnType<typeof runCommandSurfaceSession>>) {
  const host = {
    entrypointSha256: "a".repeat(64),
    packageJsonSha256: "b".repeat(64),
    packageVersion: "18.11.1",
  };
  return scoreCommandSurfaceRecord(
    {
      schemaVersion: 1,
      kind: "omp-command-surface-cell",
      runId: "local-fixture",
      pluginTarballSha256: "c".repeat(64),
      hostIdentity: host,
      ...result,
    },
    {
      runId: "local-fixture",
      pluginTarballSha256: "c".repeat(64),
      expectedHost: host,
    },
  ).outcome;
}

describe("§4 child protocol boundary (local fixtures only)", () => {
  it.each([
    "normal",
    "notification-first",
  ])("passes %s only after terminal, content and real close", async (mode) => {
    const child = fixture(mode);
    const result = await runCommandSurfaceSession(child, 2_000);
    expect(result.driverError).toBeUndefined();
    expect(result.commands.map((entry) => entry.command)).toEqual([
      "help",
      "status",
      "report",
      "onboard plan",
    ]);
    expect(
      result.commands.every(
        (entry) => entry.contentValidated && !entry.agentInvoked,
      ),
    ).toBe(true);
    expect(verdict(result)).toBe("passed");
    expect(child.exitCode).toBe(0);
    expect(child.stdout.readableEnded && child.stderr.readableEnded).toBe(true);
  });

  // Real deadlines/EOF/kill are the subject here, not a sleep-based scheduling guess.
  it.each([
    ["ack-only", "RPC_COMMAND_TIMEOUT"],
    ["terminal-only", "RPC_COMMAND_TIMEOUT"],
    ["missing-content", "RPC_COMMAND_TIMEOUT"],
    ["wrong-content", "RPC_COMMAND_TIMEOUT"],
    ["ack-error", "RPC_COMMAND_FAILED"],
    ["ack-wrong-command", "RPC_ACK_INVALID"],
    ["ack-agent", "RPC_AGENT_INVOKED"],
    ["terminal-error", "RPC_COMMAND_FAILED"],
    ["aborted", "RPC_TERMINAL_REJECTED"],
    ["unsettled", "RPC_TERMINAL_REJECTED"],
    ["missing-settled", "RPC_TERMINAL_REJECTED"],
    ["missing-agent", "RPC_TERMINAL_REJECTED"],
    ["terminal-agent", "RPC_TERMINAL_REJECTED"],
    ["wrong-id", "RPC_UNEXPECTED_TERMINAL"],
    ["agent_start", "RPC_AGENT_OR_EXTENSION_ERROR"],
    ["agent_end", "RPC_AGENT_OR_EXTENSION_ERROR"],
    ["message_update", "RPC_AGENT_OR_EXTENSION_ERROR"],
    ["model_start", "RPC_AGENT_OR_EXTENSION_ERROR"],
    ["extension_error", "RPC_AGENT_OR_EXTENSION_ERROR"],
    ["late-error", "RPC_AGENT_OR_EXTENSION_ERROR"],
    ["interactive", "RPC_UNEXPECTED_UI"],
    ["sensitive", "RPC_SANITIZATION_FAILED"],
    ["malformed", "RPC_FRAME_INVALID"],
    ["truncated-on-exit", "RPC_TRUNCATED_FRAME"],
    ["early-close", "HOST_CLOSED_EARLY"],
    ["exit-nonzero", "HOST_EXIT_NONZERO"],
    ["exit-signal", "HOST_EXIT_SIGNAL"],
    ["hold-open", "HOST_CLOSE_TIMEOUT"],
  ])("rejects %s", async (mode, error) => {
    const child = fixture(mode);
    const result = await runCommandSurfaceSession(child, 1_000);
    expect(result.driverError).toBe(error);
    expect(verdict(result)).toBe("failed");
    expect(child.exitCode !== null || child.signalCode !== null).toBe(true);
  });

  it.each([
    "stdin",
    "stdout",
    "stderr",
  ] as const)("rejects %s capture/write errors and still closes", async (stream) => {
    const child = fixture("normal");
    const pending = runCommandSurfaceSession(child, 1_000);
    child[stream].emit("error", new Error("fixture"));
    const result = await pending;
    expect(result.driverError).toBe(`HOST_${stream.toUpperCase()}_ERROR`);
    expect(verdict(result)).toBe("failed");
    expect(child.exitCode !== null || child.signalCode !== null).toBe(true);
  });

  it("rejects spawn failure without an unhandled process error", async () => {
    const child = spawn("/nonexistent-section4-fixture", [], {
      stdio: ["pipe", "pipe", "pipe"],
      env: {},
    });
    const result = await runCommandSurfaceSession(child, 1_000);
    expect(result.driverError).toBe("HOST_PROCESS_ERROR");
    expect(verdict(result)).toBe("failed");
  });

  it("rejects observed provider traffic even without an agent frame", async () => {
    const result = await runCommandSurfaceSession(
      fixture("normal"),
      2_000,
      () => true,
    );
    expect(result.driverError).toBe("RPC_MODEL_CALL");
    expect(verdict(result)).toBe("failed");
  });
});

describe("requested exact Host version", () => {
  it("accepts the exact requested version", () => {
    expect(() =>
      assertRequestedHostVersion("18.11.1", "18.11.1"),
    ).not.toThrow();
  });
  it.each([
    "18.11.10",
    "19.0.1",
    "18.11.1-extra",
  ])("rejects observed %s", (observed) => {
    expect(() => assertRequestedHostVersion(observed, "18.11.1")).toThrow(
      "OMP_TARGET_VERSION_MISMATCH",
    );
  });
});
