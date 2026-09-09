import assert from "node:assert/strict";
import {
  mkdirSync,
  mkdtempSync,
  writeFileSync,
  readFileSync,
  existsSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  defaultRunRefresh,
  detect,
  detectChanges,
  formToolNames,
  impact,
  resolveAnalysisTools,
} from "../dist/backends/gitnexus.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t9-" + label + "-"));
}

function withIndex(root, opts = {}) {
  mkdirSync(join(root, ".gitnexus"), { recursive: true });
  if (opts.lastCommit != null) {
    writeFileSync(
      join(root, ".gitnexus", "meta.json"),
      JSON.stringify({ lastCommit: opts.lastCommit }),
      "utf8",
    );
  }
  if (opts.runCjs) {
    writeFileSync(join(root, ".gitnexus", "run.cjs"), opts.runCjs, "utf8");
  }
}

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

test("detect: never throws; empty cwd => all false-ish", async () => {
  const root = fixtureRoot("empty");
  const result = await detect(root, {});
  assert.equal(result.mcpVisible, false);
  assert.equal(result.indexPresent, false);
  assert.equal(result.stale, false);
});

test("detect: mcpVisible false does not flip indexPresent (Q1B)", async () => {
  const root = fixtureRoot("idx-no-mcp");
  withIndex(root, { lastCommit: "aaa" });
  const result = await detect(root, {
    resolveHead: () => "aaa",
    resolveIndexedCommit: () => "aaa",
  });
  assert.equal(result.mcpVisible, false);
  assert.equal(result.indexPresent, true);
  assert.equal(result.stale, false);
});

test("detect: three fields independent; stale when HEAD != indexed", async () => {
  const root = fixtureRoot("stale");
  withIndex(root, { lastCommit: "oldsha" });
  const mcp = mcpStub({
    "mcp__gitnexus__impact": () => "ok",
  });
  const result = await detect(root, {
    mcp,
    resolveHead: () => "newsha",
    resolveIndexedCommit: () => "oldsha",
  });
  assert.equal(result.mcpVisible, true);
  assert.equal(result.indexPresent, true);
  assert.equal(result.stale, true);
});

test("detect: missing MCP with index still reports indexPresent", async () => {
  const root = fixtureRoot("mcp-miss-idx");
  withIndex(root, { lastCommit: "x" });
  const result = await detect(root, {
    toolNames: ["mcp__other__foo"],
    resolveHead: () => "x",
    resolveIndexedCommit: () => "x",
  });
  assert.equal(result.mcpVisible, false);
  assert.equal(result.indexPresent, true);
  assert.equal(result.stale, false);
});

test("impact/detectChanges: no MCP => skipped, no throw (Q2A)", async () => {
  const root = fixtureRoot("skip-mcp");
  withIndex(root, { lastCommit: "h" });
  const a = await impact(root, "pkg/x.ts", undefined, {
    resolveHead: () => "h",
    resolveIndexedCommit: () => "h",
  });
  assert.equal(a.status, "skipped");
  assert.equal(typeof a.summary, "string");
  assert.ok(a.summary.length > 0);
  assert.equal(a.advisory, undefined);
  const b = await detectChanges(root, "all", {
    resolveHead: () => "h",
    resolveIndexedCommit: () => "h",
  });
  assert.equal(b.status, "skipped");
});

test("impact/detectChanges: no .gitnexus/ => skipped (Q2A)", async () => {
  const root = fixtureRoot("skip-idx");
  const mcp = mcpStub({
    "mcp__gitnexus__impact": () => ({ hits: [] }),
    "mcp__gitnexus__detect_changes": () => ({ changed: [] }),
  });
  const a = await impact(root, "t", "upstream", { mcp });
  assert.equal(a.status, "skipped");
  assert.equal(a.reason, "index-missing");
  const b = await detectChanges(root, undefined, { mcp });
  assert.equal(b.status, "skipped");
  assert.equal(b.reason, "index-missing");
});

test("impact: ok path returns printable summary (Q3A)", async () => {
  const root = fixtureRoot("ok-impact");
  withIndex(root, { lastCommit: "head1" });
  const mcp = mcpStub({
    "mcp__gitnexus__impact": (args) => ({
      target: args.target,
      direction: args.direction ?? null,
      nodes: ["a"],
    }),
  });
  const result = await impact(root, "src/foo.ts", "downstream", {
    mcp,
    resolveHead: () => "head1",
    resolveIndexedCommit: () => "head1",
  });
  assert.equal(result.status, "ok");
  assert.match(result.summary, /src\/foo\.ts/);
  assert.equal(result.advisory, undefined);
});

test("detectChanges: ok path with scope", async () => {
  const root = fixtureRoot("ok-dc");
  withIndex(root, { lastCommit: "head1" });
  const mcp = mcpStub({
    "mcp__gitnexus__detect_changes": (args) => ({ scope: args.scope, n: 2 }),
  });
  const result = await detectChanges(root, "staged", {
    mcp,
    resolveHead: () => "head1",
    resolveIndexedCommit: () => "head1",
  });
  assert.equal(result.status, "ok");
  assert.match(result.summary, /staged/);
});

test("stale + refresh fail => advisory:true printable, not skip (Q2A/Q4A)", async () => {
  const root = fixtureRoot("stale-fail");
  withIndex(root, { lastCommit: "old" });
  let refreshed = false;
  const mcp = mcpStub({
    "mcp__gitnexus__impact": () => "impact-summary-body",
  });
  const result = await impact(root, "x", undefined, {
    mcp,
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => {
      refreshed = true;
      return { ok: false, detail: "analyze boom" };
    },
  });
  assert.equal(refreshed, true);
  assert.equal(result.status, "advisory");
  assert.equal(result.advisory, true);
  assert.match(result.summary, /impact-summary-body/);
  assert.match(result.summary, /advisory/i);
  assert.equal(result.reason, "stale-refresh-failed");
});

test("stale + refresh timeout via runRefresh => advisory", async () => {
  const root = fixtureRoot("stale-timeout");
  withIndex(root, { lastCommit: "old" });
  const mcp = mcpStub({
    "mcp__gitnexus__detect_changes": () => "dc-body",
  });
  const result = await detectChanges(root, "all", {
    mcp,
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => ({ ok: false, detail: "refresh timed out after 1ms" }),
  });
  assert.equal(result.status, "advisory");
  assert.equal(result.advisory, true);
  assert.match(result.summary, /dc-body/);
});

test("stale + refresh ok => status ok", async () => {
  const root = fixtureRoot("stale-ok");
  withIndex(root, { lastCommit: "old" });
  const mcp = mcpStub({
    "mcp__gitnexus__impact": () => "fresh-impact",
  });
  const result = await impact(root, "t", undefined, {
    mcp,
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => ({ ok: true }),
  });
  assert.equal(result.status, "ok");
  assert.equal(result.summary, "fresh-impact");
  assert.equal(result.advisory, undefined);
});

test("refresh must not write MCP config (Q4A/Q6A)", async () => {
  const root = fixtureRoot("no-mcp-write");
  withIndex(root, { lastCommit: "old" });
  const mcpPath = join(root, ".cursor", "mcp.json");
  mkdirSync(join(root, ".cursor"), { recursive: true });
  writeFileSync(mcpPath, JSON.stringify({ mcpServers: {} }), "utf8");
  const before = readFileSync(mcpPath, "utf8");
  const mcp = mcpStub({
    "mcp__gitnexus__impact": () => "x",
  });
  await impact(root, "t", undefined, {
    mcp,
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async (cwd) => {
      // Simulate analyze writing only under .gitnexus/
      writeFileSync(
        join(cwd, ".gitnexus", "meta.json"),
        JSON.stringify({ lastCommit: "new" }),
        "utf8",
      );
      return { ok: true };
    },
  });
  assert.equal(readFileSync(mcpPath, "utf8"), before);
  assert.ok(existsSync(join(root, ".gitnexus", "meta.json")));
});

test("serverName forms mcp__<name>__*; fallback mcp__gitnexus__* (Q6A)", async () => {
  assert.deepEqual(formToolNames("gitnexus"), {
    impact: "mcp__gitnexus__impact",
    detectChanges: "mcp__gitnexus__detect_changes",
  });
  assert.deepEqual(formToolNames("customGn"), {
    impact: "mcp__customGn__impact",
    detectChanges: "mcp__customGn__detect_changes",
  });

  const primary = await resolveAnalysisTools({
    serverName: "customGn",
    toolNames: ["mcp__customGn__impact", "mcp__customGn__detect_changes"],
  });
  assert.equal(primary.impact, "mcp__customGn__impact");
  assert.equal(primary.detectChanges, "mcp__customGn__detect_changes");
  assert.equal(primary.mcpVisible, true);

  const fallback = await resolveAnalysisTools({
    serverName: "customGn",
    toolNames: ["mcp__gitnexus__impact"],
  });
  assert.equal(fallback.impact, "mcp__gitnexus__impact");
  assert.equal(fallback.mcpVisible, true);

  const root = fixtureRoot("name-fallback");
  withIndex(root, { lastCommit: "h" });
  const mcp = mcpStub({
    "mcp__gitnexus__impact": (args) => ({ via: "fallback", t: args.target }),
  });
  const result = await impact(root, "file.ts", undefined, {
    serverName: "other",
    mcp,
    resolveHead: () => "h",
    resolveIndexedCommit: () => "h",
  });
  assert.equal(result.status, "ok");
  assert.match(result.summary, /fallback/);
});

test("module importable without apply() registration (Q5A fence)", async () => {
  const mod = await import("../dist/backends/gitnexus.js");
  assert.equal(typeof mod.detect, "function");
  assert.equal(typeof mod.impact, "function");
  assert.equal(typeof mod.detectChanges, "function");
});

test("MCP call failure => advisory, never throw", async () => {
  const root = fixtureRoot("mcp-fail");
  withIndex(root, { lastCommit: "h" });
  const mcp = {
    listToolNames: () => ["mcp__gitnexus__impact"],
    callTool: async () => {
      throw new Error("transport down");
    },
  };
  const result = await impact(root, "t", undefined, {
    mcp,
    resolveHead: () => "h",
    resolveIndexedCommit: () => "h",
  });
  assert.equal(result.status, "advisory");
  assert.equal(result.advisory, true);
  assert.match(result.summary, /transport down/);
});

test("defaultRunRefresh: run.cjs analyze includes --index-only (Q4A)", async () => {
  const root = fixtureRoot("idx-only-run");
  const argvPath = join(root, ".gitnexus", "argv.json");
  withIndex(root, {
    lastCommit: "old",
    runCjs: `const fs = require("node:fs");
const path = require("node:path");
fs.writeFileSync(
  path.join(__dirname, "argv.json"),
  JSON.stringify(process.argv.slice(2)),
  "utf8",
);
process.exit(0);
`,
  });
  // Sentinel files outside .gitnexus/ must remain untouched by refresh.
  writeFileSync(join(root, "AGENTS.md"), "KEEP_AGENTS\n", "utf8");
  writeFileSync(join(root, "CLAUDE.md"), "KEEP_CLAUDE\n", "utf8");
  const result = await defaultRunRefresh(root, 10_000);
  assert.equal(result.ok, true);
  const argv = JSON.parse(readFileSync(argvPath, "utf8"));
  assert.deepEqual(argv, ["analyze", "--index-only"]);
  assert.equal(readFileSync(join(root, "AGENTS.md"), "utf8"), "KEEP_AGENTS\n");
  assert.equal(readFileSync(join(root, "CLAUDE.md"), "utf8"), "KEEP_CLAUDE\n");
});

test("defaultRunRefresh: PATH gitnexus analyze includes --index-only (Q4A)", async () => {
  const root = fixtureRoot("idx-only-cli");
  mkdirSync(join(root, ".gitnexus"), { recursive: true });
  const bin = join(root, "bin");
  mkdirSync(bin, { recursive: true });
  const log = join(root, "cli-argv.txt");
  writeFileSync(
    join(bin, "gitnexus"),
    `#!/bin/sh\nprintf '%s\\n' "$@" > "${log}"\nexit 0\n`,
    { mode: 0o755 },
  );
  const prev = process.env.PATH;
  process.env.PATH = bin + ":" + prev;
  try {
    const result = await defaultRunRefresh(root, 10_000);
    assert.equal(result.ok, true);
    const argv = readFileSync(log, "utf8")
      .trim()
      .split("\n")
      .filter(Boolean);
    assert.deepEqual(argv, ["analyze", "--index-only"]);
  } finally {
    process.env.PATH = prev;
  }
});

test("impact: toolNames only opposite tool => skipped without refresh (Q2A)", async () => {
  const root = fixtureRoot("impact-opp");
  withIndex(root, { lastCommit: "old" });
  let refreshed = false;
  const result = await impact(root, "t", undefined, {
    toolNames: ["mcp__gitnexus__detect_changes"],
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => {
      refreshed = true;
      return { ok: true };
    },
  });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "mcp-unavailable");
  assert.equal(refreshed, false);
});

test("impact: toolNames without mcp client => skipped without refresh (Q2A)", async () => {
  const root = fixtureRoot("impact-names-only");
  withIndex(root, { lastCommit: "old" });
  let refreshed = false;
  const result = await impact(root, "t", undefined, {
    toolNames: ["mcp__gitnexus__impact"],
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => {
      refreshed = true;
      return { ok: true };
    },
  });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "mcp-unavailable");
  assert.equal(refreshed, false);
});

test("detectChanges: mcp lists only impact => skipped without refresh (Q2A)", async () => {
  const root = fixtureRoot("dc-opp");
  withIndex(root, { lastCommit: "old" });
  let refreshed = false;
  const mcp = mcpStub({
    "mcp__gitnexus__impact": () => "should-not-call",
  });
  const result = await detectChanges(root, "all", {
    mcp,
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => {
      refreshed = true;
      return { ok: true };
    },
  });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "mcp-unavailable");
  assert.equal(refreshed, false);
});

test("detectChanges: toolNames without mcp client => skipped without refresh (Q2A)", async () => {
  const root = fixtureRoot("dc-names-only");
  withIndex(root, { lastCommit: "old" });
  let refreshed = false;
  const result = await detectChanges(root, "all", {
    toolNames: ["mcp__gitnexus__detect_changes"],
    resolveHead: () => "new",
    resolveIndexedCommit: () => "old",
    runRefresh: async () => {
      refreshed = true;
      return { ok: true };
    },
  });
  assert.equal(result.status, "skipped");
  assert.equal(result.reason, "mcp-unavailable");
  assert.equal(refreshed, false);
});
