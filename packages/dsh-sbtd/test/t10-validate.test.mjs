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
  assert.equal(tools.length, 6);
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
