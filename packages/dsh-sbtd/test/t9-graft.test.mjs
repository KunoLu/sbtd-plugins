import assert from "node:assert/strict";
import { test } from "node:test";
import {
  GRAFT_SKIP_REASONS,
  SUPPORTED_GRAFT_VERSIONS,
  detectChanges,
  impact,
} from "../dist/backends/graft.js";

const CWD = "/tmp/dsh-sbtd-t9";

function mcpStub(toolMap) {
  const names = Object.keys(toolMap);
  return {
    listToolNames: () => names,
    callTool: async (name, args) => {
      const fn = toolMap[name];
      if (!fn) throw new Error("unknown tool: " + name);
      return fn(args);
    },
  };
}

/** Freshness probe that reports an in-sync graph. */
const FRESH = "graph in sync with the code";

function freshMcp(extra = {}) {
  return mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () => FRESH,
    ...extra,
  });
}

test("reason vocabulary lock: exactly six reasons (R2 Q4 A)", () => {
  assert.deepEqual([...GRAFT_SKIP_REASONS], [
    "launcher-missing",
    "version-unsupported",
    "call-failed",
    "guard-failed",
    "graph-missing",
    "graph-stale",
  ]);
});


// --- Six dedicated reason tests (R2 Q4 A) ---

test("reason launcher-missing: no MCP client injected", async () => {
  const pre = await impact(CWD, "Foo", undefined, {});
  assert.equal(pre.status, "skipped");
  assert.equal(pre.reason, "launcher-missing");
  const post = await detectChanges(CWD, undefined, { mcp: null });
  assert.equal(post.status, "skipped");
  assert.equal(post.reason, "launcher-missing");
});

test("reason launcher-missing: client wired but no graft_* tools visible", async () => {
  const mcp = mcpStub({ "mcp__other__tool": async () => ({}) });
  const result = await impact(CWD, "Foo", undefined, { mcp });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "launcher-missing");
});

test("reason version-unsupported: injected declaration outside supported set", async () => {
  const mcp = freshMcp({
    "mcp__sbtd-graft__graft_find_code": async () => ({ hit: 1 }),
  });
  const result = await impact(CWD, "Foo", undefined, {
    mcp,
    versionDeclaration: "0.21.0",
  });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "version-unsupported");
  assert.match(result.summary, /0\.21\.0/);
  assert.match(result.summary, /0\.22\.0/);
});

test("supported version declaration passes the gate (0.22.0)", async () => {
  assert.deepEqual([...SUPPORTED_GRAFT_VERSIONS], ["0.22.0"]);
  const mcp = freshMcp({
    "mcp__sbtd-graft__graft_find_code": async (args) => ({
      hit: args.query,
    }),
  });
  const result = await impact(CWD, "Foo", undefined, {
    mcp,
    versionDeclaration: "0.22.0",
  });
  assert.equal(result.status, "ok");
  assert.match(result.summary, /Foo/);
});

test("reason call-failed: MCP call throws a generic error", async () => {
  const mcp = mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () => {
      throw new Error("socket hangup");
    },
  });
  const pre = await impact(CWD, "Foo", undefined, { mcp });
  assert.equal(pre.status, "skipped");
  assert.equal(pre.reason, "call-failed");
  assert.match(pre.summary, /socket hangup/);
  const post = await detectChanges(CWD, undefined, { mcp });
  assert.equal(post.status, "skipped");
  assert.equal(post.reason, "call-failed");
});

test("reason call-failed: find_code call throws after fresh probe", async () => {
  const mcp = freshMcp({
    "mcp__sbtd-graft__graft_find_code": async () => {
      throw new Error("boom");
    },
  });
  const result = await impact(CWD, "Foo", undefined, { mcp });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "call-failed");
  assert.match(result.summary, /boom/);
});

test("reason guard-failed: launcher guard stderr line surfaced", async () => {
  const mcp = mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () => {
      throw new Error("sbtd-graft-entry: graph state missing; refusing");
    },
  });
  const result = await detectChanges(CWD, undefined, { mcp });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "guard-failed");
});

test("reason guard-failed: exit code 2 surfaced by host", async () => {
  const mcp = mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () => {
      throw new Error("MCP server exited with code 2");
    },
  });
  const result = await impact(CWD, "Foo", undefined, { mcp });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "guard-failed");
});

test("reason graph-missing: freshness probe reports no graph", async () => {
  const mcp = mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () =>
      "no graph found for this repository",
  });
  const pre = await impact(CWD, "Foo", undefined, { mcp });
  assert.equal(pre.status, "skipped");
  assert.equal(pre.reason, "graph-missing");
  const post = await detectChanges(CWD, undefined, { mcp });
  assert.equal(post.status, "skipped");
  assert.equal(post.reason, "graph-missing");
});

test("reason graph-stale: freshness probe reports drift", async () => {
  const mcp = mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () =>
      "graph is stale: 3 files drifted",
  });
  const pre = await impact(CWD, "Foo", undefined, { mcp });
  assert.equal(pre.status, "skipped");
  assert.equal(pre.reason, "graph-stale");
  const post = await detectChanges(CWD, "pkg", { mcp });
  assert.equal(post.status, "skipped");
  assert.equal(post.reason, "graph-stale");
});

// --- Shape + degrade behavior (R1 Q1 A / R2 Q4 A) ---

test("AnalysisResult shape unchanged: ok carries summary, skipped carries reason", async () => {
  const ok = await detectChanges(CWD, undefined, { mcp: freshMcp() });
  assert.deepEqual(Object.keys(ok).sort(), ["status", "summary"]);
  assert.equal(ok.status, "ok");
  const skip = await impact(CWD, "Foo");
  assert.deepEqual(Object.keys(skip).sort(), ["reason", "status", "summary"]);
  assert.equal(skip.status, "skipped");
});

test("graceful degrade: impact/detectChanges never throw without Graft", async () => {
  const weird = mcpStub({
    "mcp__sbtd-graft__graft_check_freshness": async () => {
      throw "non-error throw"; // eslint-disable-line no-throw-literal
    },
  });
  const result = await impact(CWD, "Foo", undefined, { mcp: weird });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "call-failed");
  const listed = {
    mcp: {
      listToolNames: () => {
        throw new Error("list failed");
      },
      callTool: async () => ({}),
    },
  };
  const res2 = await detectChanges(CWD, undefined, listed);
  assert.equal(res2.status, "skipped");
  assert.equal(res2.reason, "launcher-missing");
});

test("detectChanges ok: fresh graph without scope reports in-sync", async () => {
  const result = await detectChanges(CWD, undefined, { mcp: freshMcp() });
  assert.equal(result.status, "ok");
  assert.match(result.summary, /in sync/i);
});


test("impact skipped when find_code not visible although freshness is", async () => {
  const result = await impact(CWD, "Foo", undefined, { mcp: freshMcp() });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "launcher-missing");
});

test("custom serverName is honored end to end", async () => {
  const mcp = mcpStub({
    "mcp__acme__graft_check_freshness": async () => FRESH,
    "mcp__acme__graft_find_code": async () => ({ via: "acme" }),
  });
  const result = await impact(CWD, "Foo", undefined, {
    mcp,
    serverName: "acme",
  });
  assert.equal(result.status, "ok");
  assert.match(result.summary, /acme/);
});

test("freshness empty or unrecognized output never counts as structural proof", async () => {
  for (const raw of [undefined, null, "", { content: [] }, "unexpected reply"]) {
    const mcp = mcpStub({
      "mcp__sbtd-graft__graft_check_freshness": async () => raw,
    });
    const result = await detectChanges(CWD, undefined, { mcp });
    assert.equal(result.status, "skipped");
    assert.equal(result.reason, "call-failed");
  }
});

test("MCP returned error envelopes degrade instead of reporting ok", async () => {
  for (const [message, reason] of [
    ["query failed", "call-failed"],
    ["sbtd-graft-entry: guard failed", "guard-failed"],
  ]) {
    const mcp = freshMcp({
      "mcp__sbtd-graft__graft_find_code": async () => ({
        isError: true,
        content: [{ type: "text", text: message }],
      }),
    });
    const result = await impact(CWD, "Foo", undefined, { mcp });
    assert.equal(result.status, "skipped");
    assert.equal(result.reason, reason);
  }
});

test("native MCP freshness reports distinguish fresh, missing, and drift", async () => {
  for (const [text, status, reason] of [
    ["graft check: OK — the graph is in sync with the code.\n\ngraph check: OK — the wiring graph is in sync with the code.", "ok", undefined],
    ["graft check: NO GRAPH\n\nNo graft/manifest.json found.", "skipped", "graph-missing"],
    ["graft check: OK — the graph is in sync with the code.\n\ngraph check: STALE\nchanged (1):\n  example.ts", "skipped", "graph-stale"],
  ]) {
    const mcp = mcpStub({
      "mcp__sbtd-graft__graft_check_freshness": async () => ({
        content: [{ type: "text", text }],
        isError: false,
      }),
    });
    const result = await detectChanges(CWD, undefined, { mcp });
    assert.equal(result.status, status);
    assert.equal(result.reason, reason);
  }
});
