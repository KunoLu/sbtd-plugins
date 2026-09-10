import assert from "node:assert/strict";
import {
  mkdirSync,
  mkdtempSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { apply, inject, name } from "../dist/index.js";
import { getSession } from "../dist/state.js";
import {
  SBTD_VALIDATE_TOOL_NAME,
  bindBridgeOuter,
  bindBridgeSignal,
  createToolsMcpBridge,
  createValidateTool,
  discoverProjectTestCommand,
  modelSchemaForbidsTrustHandles,
  sbtdValidate,
} from "../dist/tools/validate.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t10-" + label + "-"));
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

function withIndex(root, lastCommit = "abc") {
  mkdirSync(join(root, ".gitnexus"), { recursive: true });
  writeFileSync(
    join(root, ".gitnexus", "meta.json"),
    JSON.stringify({ lastCommit }),
    "utf8",
  );
}

function loadPlugin() {
  const tools = [];
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
  });
  return { tools };
}

test("apply registers sbtd_validate (Q5A)", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 8);
  assert.equal(tools[5].name, SBTD_VALIDATE_TOOL_NAME);
});

test("Q1A: model schema forbids cwd/mcp/runRefresh/serverName/toolNames", () => {
  const tool = createValidateTool();
  assert.equal(tool.name, SBTD_VALIDATE_TOOL_NAME);
  assert.equal(modelSchemaForbidsTrustHandles(tool.parameters), true);
  const props = tool.parameters.properties;
  assert.deepEqual(Object.keys(props).sort(), [
    "direction",
    "phase",
    "scope",
    "target",
  ]);
  assert.deepEqual(tool.parameters.required, ["phase"]);
  assert.equal(tool.parameters.additionalProperties, false);
});

test("Q2A/Q3 clar: pre without target => validate.pre=skipped; no tests", async () => {
  const id = "t10-pre-no-target";
  const result = await sbtdValidate(id, { phase: "pre" }, { cwd: fixtureRoot("pre-miss") });
  assert.equal(result.phase, "pre");
  assert.equal(result.gitnexus.status, "skipped");
  assert.equal(result.gitnexus.reason, "missing-target");
  assert.equal(result.validate.pre, "skipped");
  assert.equal(result.tests, undefined);
  assert.equal(getSession(id).validate.pre, "skipped");
});

test("Q2A/Q3 clar: pre with T9 skipped => validate.pre=skipped", async () => {
  const id = "t10-pre-gn-skip";
  const root = fixtureRoot("pre-skip");
  const result = await sbtdValidate(
    id,
    { phase: "pre", target: "Foo" },
    { cwd: root, gitnexus: {} },
  );
  assert.equal(result.gitnexus.status, "skipped");
  assert.equal(result.validate.pre, "skipped");
  assert.equal(result.tests, undefined);
  assert.equal(getSession(id).validate.pre, "skipped");
});

test("Q3 clar: pre with T9 advisory => validate.pre=done; advisory printed", async () => {
  const id = "t10-pre-advisory";
  const root = fixtureRoot("pre-adv");
  withIndex(root, "head1");
  const mcp = mcpStub({
    "mcp__gitnexus__impact": async () => {
      throw new Error("boom");
    },
  });
  const result = await sbtdValidate(
    id,
    { phase: "pre", target: "Bar", direction: "upstream" },
    {
      cwd: root,
      gitnexus: {
        mcp,
        resolveHead: () => "head1",
        resolveIndexedCommit: () => "head1",
      },
    },
  );
  assert.equal(result.gitnexus.status, "advisory");
  assert.equal(result.gitnexus.advisory, true);
  assert.equal(result.validate.pre, "done");
  assert.match(result.gitnexus.summary, /boom|impact failed/i);
  assert.equal(getSession(id).validate.pre, "done");
});

test("Q3 clar: pre with T9 ok => validate.pre=done", async () => {
  const id = "t10-pre-ok";
  const root = fixtureRoot("pre-ok");
  withIndex(root, "h");
  const mcp = mcpStub({
    "mcp__gitnexus__impact": async (args) => ({ hit: args.target }),
  });
  const result = await sbtdValidate(
    id,
    { phase: "pre", target: "Sym" },
    {
      cwd: root,
      gitnexus: {
        mcp,
        resolveHead: () => "h",
        resolveIndexedCommit: () => "h",
      },
    },
  );
  assert.equal(result.gitnexus.status, "ok");
  assert.equal(result.validate.pre, "done");
  assert.equal(getSession(id).validate.pre, "done");
});

test("Q2A/Q3A: post with GitNexus skipped still runs tests; post not blocked from skip", async () => {
  const id = "t10-post-gn-skip-tests";
  const root = fixtureRoot("post-skip");
  let testsCalled = 0;
  const result = await sbtdValidate(
    id,
    { phase: "post", scope: "pkg" },
    {
      cwd: root,
      gitnexus: {},
      runTests: async () => {
        testsCalled += 1;
        return { status: "done", summary: "injected ok" };
      },
    },
  );
  assert.equal(result.gitnexus.status, "skipped");
  assert.equal(testsCalled, 1);
  assert.equal(result.tests.status, "done");
  assert.equal(result.validate.post, "done");
  assert.equal(getSession(id).validate.post, "done");
});

test("Q4A: no test script => tests skipped + residual risk; post=done; never passed", async () => {
  const id = "t10-post-no-script";
  const root = fixtureRoot("no-script");
  writeFileSync(join(root, "package.json"), JSON.stringify({ name: "x" }), "utf8");
  const result = await sbtdValidate(
    id,
    { phase: "post" },
    { cwd: root, gitnexus: {} },
  );
  assert.equal(result.tests.status, "skipped");
  assert.match(result.tests.summary, /Residual risk/i);
  assert.doesNotMatch(result.tests.summary, /\bpassed\b/i);
  assert.equal(result.validate.post, "done");
  assert.equal(getSession(id).validate.post, "done");
});

test("Q4A: failed tests => tests.failed + validate.post=blocked", async () => {
  const id = "t10-post-fail";
  const root = fixtureRoot("fail");
  const result = await sbtdValidate(
    id,
    { phase: "post" },
    {
      cwd: root,
      gitnexus: {},
      runTests: async () => ({
        status: "failed",
        summary: "boom fail",
      }),
    },
  );
  assert.equal(result.tests.status, "failed");
  assert.equal(result.validate.post, "blocked");
  assert.equal(getSession(id).validate.post, "blocked");
});

test("Q3A: GitNexus advisory on post does not set post=blocked when tests done", async () => {
  const id = "t10-post-adv-ok-tests";
  const root = fixtureRoot("post-adv");
  withIndex(root, "h2");
  const mcp = mcpStub({
    "mcp__gitnexus__detect_changes": async () => {
      throw new Error("dc fail");
    },
  });
  const result = await sbtdValidate(
    id,
    { phase: "post" },
    {
      cwd: root,
      gitnexus: {
        mcp,
        resolveHead: () => "h2",
        resolveIndexedCommit: () => "h2",
      },
      runTests: async () => ({ status: "done", summary: "ok" }),
    },
  );
  assert.equal(result.gitnexus.status, "advisory");
  assert.equal(result.validate.post, "done");
});

test("discoverProjectTestCommand prefers package.json scripts.test", () => {
  const root = fixtureRoot("discover");
  writeFileSync(
    join(root, "package.json"),
    JSON.stringify({ scripts: { test: "node --test" } }),
    "utf8",
  );
  writeFileSync(join(root, "pnpm-lock.yaml"), "", "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  assert.equal(cmd.command, "pnpm");
  assert.deepEqual(cmd.args, ["test"]);
});

test("invalid phase throws", async () => {
  await assert.rejects(
    () => sbtdValidate("t10-bad-phase", { phase: "mid" }),
    /phase must be/,
  );
});

test("return envelope shape (Q4A)", async () => {
  const id = "t10-envelope";
  const result = await sbtdValidate(
    id,
    { phase: "post" },
    {
      cwd: fixtureRoot("env"),
      runTests: async () => ({
        status: "not-applicable",
        summary: "n/a residual risk",
      }),
    },
  );
  assert.equal(result.phase, "post");
  assert.ok(result.gitnexus);
  assert.ok(result.tests);
  assert.ok(result.validate);
  assert.equal(result.validate.post, "done");
});

test("discoverProjectTestCommand reads non-Node AGENTS commands (pytest/go/gradle/swift)", () => {
  const cases = [
    { label: "pytest", body: "# Agents\n\n- `pytest -q`\n", command: "pytest", args: ["-q"] },
    { label: "uv-pytest", body: "Run tests:\n\n`uv run pytest`\n", command: "uv", args: ["run", "pytest"] },
    { label: "go", body: "## Test\n\ngo test ./...\n", command: "go", args: ["test", "./..."] },
    { label: "gradlew", body: "CI:\n./gradlew test\n", command: "gradlew", args: ["test"] },
    { label: "swift", body: "`swift test`\n", command: "swift", args: ["test"] },
  ];
  for (const c of cases) {
    const root = fixtureRoot("docs-" + c.label);
    writeFileSync(join(root, "AGENTS.md"), c.body, "utf8");
    const cmd = discoverProjectTestCommand(root);
    assert.ok(cmd, c.label + " should discover");
    assert.equal(cmd.command, c.command, c.label);
    assert.deepEqual(cmd.args, c.args, c.label);
  }
});

test("discoverProjectTestCommand: bun lockfile uses bun run test", () => {
  const root = fixtureRoot("bun-run");
  writeFileSync(
    join(root, "package.json"),
    JSON.stringify({ scripts: { test: "vitest run" } }),
    "utf8",
  );
  writeFileSync(join(root, "bun.lock"), "", "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  assert.equal(cmd.command, "bun");
  assert.deepEqual(cmd.args, ["run", "test"]);
});

test("Q1A production: apply validateHost injects GitNexus into registered execute", async () => {
  const root = fixtureRoot("inject-host");
  withIndex(root, "h");
  const tools = [];
  const mcp = mcpStub({
    "mcp__gitnexus__impact": async (args) => ({ hit: args.target }),
  });
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
    cwd: root,
    validateHost: {
      cwd: root,
      gitnexus: {
        mcp,
        resolveHead: () => "h",
        resolveIndexedCommit: () => "h",
      },
    },
  });
  const validate = tools.find((t) => t.name === SBTD_VALIDATE_TOOL_NAME);
  assert.ok(validate);
  const result = await validate.execute(
    { phase: "pre", target: "Sym", cwd: "/evil", mcp: null },
    { agent: { id: "t10-inject" } },
  );
  assert.equal(result.gitnexus.status, "ok");
  assert.equal(result.validate.pre, "done");
});

test("Q1A production: apply bridges tools.schemas/execute into GitNexus mcp", async () => {
  const root = fixtureRoot("inject-bridge");
  withIndex(root, "h");
  const tools = [];
  const toolMap = {
    "mcp__gitnexus__impact": async (args) => ({ via: "bridge", t: args.target }),
  };
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
      schemas: () => Object.keys(toolMap).map((name) => ({ name })),
      execute: async ({ name, arguments: args }) => {
        const fn = toolMap[name];
        if (!fn) {
          return { isError: true, error: { message: "missing " + name }, content: [] };
        }
        return { isError: false, value: await fn(args), content: [] };
      },
    },
    on() {},
    cwd: root,
    validateHost: {
      gitnexus: {
        resolveHead: () => "h",
        resolveIndexedCommit: () => "h",
      },
    },
  });
  const validate = tools.find((t) => t.name === SBTD_VALIDATE_TOOL_NAME);
  assert.ok(validate);
  const result = await validate.execute(
    { phase: "pre", target: "BridgeSym" },
    { agent: { id: "t10-bridge" } },
  );
  assert.equal(result.gitnexus.status, "ok");
  assert.match(result.gitnexus.summary, /BridgeSym|bridge/i);
});

test("pickValidateInput drops trust-handle keys", async () => {
  const { pickValidateInput } = await import("../dist/tools/validate.js");
  const picked = pickValidateInput({
    phase: "pre",
    target: "T",
    cwd: "/nope",
    mcp: { x: 1 },
    runRefresh: () => {},
    serverName: "evil",
    toolNames: ["x"],
  });
  assert.deepEqual(picked, { phase: "pre", target: "T" });
});

test("defaultRunTests honors testTimeoutMs via sbtdValidate host", async () => {
  const root = fixtureRoot("timeout");
  const bin = join(root, "bin");
  mkdirSync(bin, { recursive: true });
  writeFileSync(
    join(bin, "pytest"),
    "#!/usr/bin/env node\nsetTimeout(() => {}, 60_000);\n",
    { mode: 0o755 },
  );
  writeFileSync(join(root, "AGENTS.md"), "`pytest`\n", "utf8");
  const oldPath = process.env.PATH;
  process.env.PATH = bin + ":" + (oldPath || "");
  try {
    const started = Date.now();
    const result = await sbtdValidate(
      "t10-timeout",
      { phase: "post" },
      { cwd: root, gitnexus: {}, testTimeoutMs: 800 },
    );
    const elapsed = Date.now() - started;
    assert.equal(result.tests.status, "failed");
    assert.match(result.tests.summary, /timed out/i);
    assert.ok(elapsed < 15_000, "should not wait full 60s; elapsed=" + elapsed);
    assert.equal(result.validate.post, "blocked");
  } finally {
    process.env.PATH = oldPath;
  }
});

const MULTI_CANDIDATE_AGENTS = `# Test catalog
npm run test
pytest
uv run pytest
go test ./...
`;

test("multi-candidate AGENTS: Python project selects pytest not npm", () => {
  const root = fixtureRoot("catalog-py");
  writeFileSync(join(root, "AGENTS.md"), MULTI_CANDIDATE_AGENTS, "utf8");
  writeFileSync(join(root, "pyproject.toml"), "[project]\nname='x'\n", "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  assert.equal(cmd.command, "pytest");
  assert.deepEqual(cmd.args, []);
});

test("multi-candidate AGENTS: Go project selects go test not npm", () => {
  const root = fixtureRoot("catalog-go");
  writeFileSync(join(root, "AGENTS.md"), MULTI_CANDIDATE_AGENTS, "utf8");
  writeFileSync(join(root, "go.mod"), "module example.com/x\n\ngo 1.22\n", "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  assert.equal(cmd.command, "go");
  assert.deepEqual(cmd.args, ["test", "./..."]);
});

test("multi-candidate AGENTS: Node with scripts.test selects npm-family", () => {
  const root = fixtureRoot("catalog-node");
  writeFileSync(join(root, "AGENTS.md"), MULTI_CANDIDATE_AGENTS, "utf8");
  writeFileSync(
    join(root, "package.json"),
    JSON.stringify({ scripts: { test: "node --test" } }),
    "utf8",
  );
  writeFileSync(join(root, "pnpm-lock.yaml"), "", "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  assert.equal(cmd.command, "npm");
  assert.deepEqual(cmd.args, ["run", "test"]);
});

test("multi-candidate AGENTS: no markers prefers earliest doc position (npm)", () => {
  const root = fixtureRoot("catalog-none");
  writeFileSync(join(root, "AGENTS.md"), MULTI_CANDIDATE_AGENTS, "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  assert.equal(cmd.command, "npm");
  assert.deepEqual(cmd.args, ["run", "test"]);
});

test("Q3A: cancel aborts without persisting validate.post=blocked", async () => {
  const id = "t10-cancel-no-block";
  const root = fixtureRoot("cancel");
  const bin = join(root, "bin");
  mkdirSync(bin, { recursive: true });
  writeFileSync(
    join(bin, "pytest"),
    "#!/usr/bin/env node\nsetTimeout(() => {}, 60_000);\n",
    { mode: 0o755 },
  );
  writeFileSync(join(root, "AGENTS.md"), "`pytest`\n", "utf8");
  const oldPath = process.env.PATH;
  process.env.PATH = bin + ":" + (oldPath || "");
  const ac = new AbortController();
  try {
    const pending = sbtdValidate(
      id,
      { phase: "post" },
      { cwd: root, gitnexus: {}, signal: ac.signal, testTimeoutMs: 60_000 },
    );
    await new Promise((r) => setTimeout(r, 150));
    ac.abort();
    await assert.rejects(pending, (err) => {
      assert.equal(err?.name, "AbortError");
      return true;
    });
    assert.equal(getSession(id).validate.post, undefined);
  } finally {
    process.env.PATH = oldPath;
  }
});

test("createToolsMcpBridge composes outer abort into nested execute signal", async () => {
  let nestedSignal;
  const tools = {
    schemas: () => [{ name: "mcp__gitnexus__impact" }],
    execute: async ({ signal }) => {
      nestedSignal = signal;
      return { isError: false, value: { ok: 1 }, content: [] };
    },
  };
  const mcp = createToolsMcpBridge(tools);
  const ac = new AbortController();
  bindBridgeSignal(mcp, ac.signal);
  await mcp.callTool("mcp__gitnexus__impact", { target: "X" });
  assert.ok(nestedSignal, "nested execute should receive a signal");
  assert.equal(nestedSignal.aborted, false);
  ac.abort();
  assert.equal(nestedSignal.aborted, true);
});

test("multi-candidate AGENTS: package-lock.json marks Node family", () => {
  const root = fixtureRoot("catalog-pkg-lock");
  writeFileSync(join(root, "AGENTS.md"), MULTI_CANDIDATE_AGENTS, "utf8");
  writeFileSync(join(root, "package.json"), JSON.stringify({ name: "x" }), "utf8");
  writeFileSync(join(root, "package-lock.json"), "{}", "utf8");
  writeFileSync(join(root, "pyproject.toml"), "[project]\nname='x'\n", "utf8");
  const cmd = discoverProjectTestCommand(root);
  assert.ok(cmd);
  // Both node + python applicable → earliest applicable is npm run test.
  assert.equal(cmd.command, "npm");
  assert.deepEqual(cmd.args, ["run", "test"]);
});

test("collectDocCandidates: rejected NPM test does not hang discovery", () => {
  const root = fixtureRoot("npm-case");
  writeFileSync(
    join(root, "AGENTS.md"),
    "NPM test\npytest\n",
    "utf8",
  );
  writeFileSync(join(root, "pyproject.toml"), "[project]\nname='x'\n", "utf8");
  const started = Date.now();
  const cmd = discoverProjectTestCommand(root);
  assert.ok(Date.now() - started < 2_000, "discovery must not infinite-loop");
  assert.ok(cmd);
  assert.equal(cmd.command, "pytest");
});

test("Q3A: cancel with no test script does not persist post=done", async () => {
  const id = "t10-cancel-no-script";
  const root = fixtureRoot("cancel-no-script");
  writeFileSync(join(root, "package.json"), JSON.stringify({ name: "x" }), "utf8");
  const ac = new AbortController();
  ac.abort();
  await assert.rejects(
    sbtdValidate(
      id,
      { phase: "post" },
      { cwd: root, gitnexus: {}, signal: ac.signal },
    ),
    (err) => {
      assert.equal(err?.name, "AbortError");
      return true;
    },
  );
  assert.equal(getSession(id).validate.post, undefined);
});

test("Q3A: injected runTests failed after abort does not persist post=blocked", async () => {
  const id = "t10-cancel-injected-fail";
  const root = fixtureRoot("cancel-injected");
  const ac = new AbortController();
  await assert.rejects(
    sbtdValidate(
      id,
      { phase: "post" },
      {
        cwd: root,
        gitnexus: {},
        signal: ac.signal,
        runTests: async () => {
          ac.abort();
          return { status: "failed", summary: "late fail after abort" };
        },
      },
    ),
    (err) => {
      assert.equal(err?.name, "AbortError");
      return true;
    },
  );
  assert.equal(getSession(id).validate.post, undefined);
});

test("createToolsMcpBridge forwards outer agent + parent token into nested execute", async () => {
  let nested;
  const tools = {
    schemas: () => [{ name: "mcp__gitnexus__impact" }],
    execute: async (exec) => {
      nested = exec;
      return { isError: false, value: { ok: 1 }, content: [] };
    },
  };
  const mcp = createToolsMcpBridge(tools);
  const token = Symbol("outer-validate-token");
  const agent = { id: "t10-outer-agent" };
  bindBridgeOuter(mcp, {
    signal: AbortSignal.timeout(5_000),
    agent,
    token,
    callId: "validate-call-1",
    rootCallId: "validate-root-1",
  });
  await mcp.callTool("mcp__gitnexus__impact", { target: "X" });
  assert.ok(nested, "nested execute should be called");
  assert.equal(nested.agent, agent);
  assert.equal(nested.parent, token);
  assert.equal(nested.rootCallId, "validate-root-1");
  assert.ok(nested.signal, "nested execute should receive a signal");
});
