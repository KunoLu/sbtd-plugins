import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import {
  executeSbtdCommand,
  FORBIDDEN_MODEL_KEYS,
  parseSbtdArgv,
  runSbtdCommand,
} from "../dist/commands/sbtd.js";
import { FORBIDDEN_MODEL_KEYS as MAESTRO_FORBIDDEN } from "../dist/backends/maestro.js";
import { getSession, serialize } from "../dist/state.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

function loadPlugin(host = {}) {
  const tools = [];
  const commands = [];
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
    commands: {
      register(definition) {
        commands.push(definition);
      },
    },
    ...host,
  });
  return { tools, commands };
}

test("apply registers sbtd command with commands inject", () => {
  const { tools, commands } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt", "commands"]);
  assert.equal(commands.length, 1);
  assert.equal(commands[0].name, "sbtd");
  assert.equal(typeof commands[0].handler, "function");
  assert.equal(tools.length, 9);
  assert.equal(tools.some((t) => t.name === "sbtd"), false);
});

test("bare /sbtd on empty session is read-only no-plan", async () => {
  const out = await runSbtdCommand("", { sessionId: "t15-empty" });
  assert.match(out, /no-plan/);
  assert.match(out, /maestro missing: none/);
  assert.equal(serialize("t15-empty").plan, undefined);
});

test("bare /sbtd shows plan and maestro missing from session", async () => {
  getSession("t15-plan").plan = {
    taskId: "tid",
    summary: "sum",
    gates: {
      ddd: { requirement: "required", state: "planned" },
      ddia: { requirement: "on-demand", state: "not-required" },
      legacy: { requirement: "on-demand", state: "not-required" },
      refactor: { requirement: "on-demand", state: "not-required" },
      release: { requirement: "on-demand", state: "not-required" },
    },
  };
  getSession("t15-plan").maestro = { missing: ["java", "cli"] };
  const out = await runSbtdCommand("", { sessionId: "t15-plan" });
  assert.match(out, /taskId: tid/);
  assert.match(out, /summary: sum/);
  assert.match(out, /maestro missing: java, cli/);
});

test("/sbtd plan is read-only plan view", async () => {
  assert.equal(
    await runSbtdCommand("plan", { sessionId: "t15-empty2" }),
    "no-plan",
  );
  const planOut = await runSbtdCommand("plan", { sessionId: "t15-plan" });
  assert.match(planOut, /Book Gate Plan/);
  assert.doesNotMatch(planOut, /maestro missing/);
  const src = readFileSync(
    join(pkgRoot, "src/commands/sbtd.ts"),
    "utf8",
  );
  assert.doesNotMatch(src, /sbtdPlan/);
});

test("/sbtd maestro calls injected preflight only", async () => {
  let called = 0;
  const out = await runSbtdCommand("maestro", {
    sessionId: "t15-m",
    cwd: "/tmp/t15",
    preflight: async (opts) => {
      called++;
      assert.equal(opts.sessionId, "t15-m");
      assert.equal(opts.cwd, "/tmp/t15");
      return {
        lastPreflight: "blocked",
        missing: ["java"],
        guidance: "install Java 17+ after approval",
      };
    },
  });
  assert.equal(called, 1);
  assert.match(out, /maestro preflight: blocked/);
  assert.match(out, /missing: java/);
  assert.match(out, /install Java 17\+ after approval/);
  const src = readFileSync(
    join(pkgRoot, "src/commands/sbtd.ts"),
    "utf8",
  );
  assert.doesNotMatch(src, /spawn\(.*maestro/);
  assert.doesNotMatch(src, /sdkmanager/);
  assert.doesNotMatch(src, /brew install/);
});

test("handler uses dsh-commands invocation shape and returns CommandResult", async () => {
  const { commands } = loadPlugin({
    commandHost: { cwd: "/tmp/t15-host" },
  });
  const command = commands[0];
  const result = await command.handler({
    agent: { id: "t15-agent" },
    rawInput: "",
  });
  assert.deepEqual(result, {
    kind: "success",
    text: "no-plan\n\nmaestro missing: none",
  });
  assert.equal(serialize("t15-agent").plan, undefined);
});

test("unknown subcommands settle as CommandResult error", async () => {
  for (const token of ["validate", "e2e", "lessons"]) {
    assert.throws(
      () => parseSbtdArgv(token),
      new RegExp(`unknown subcommand: ${token}`),
    );
    const result = await executeSbtdCommand({
      agent: { id: "t15-err" },
      rawInput: token,
    });
    assert.equal(result.kind, "error");
    assert.match(result.text, new RegExp(`unknown subcommand: ${token}`));
  }
  const { commands } = loadPlugin();
  assert.equal(commands.length, 1);
  assert.equal(commands[0].name, "sbtd");
});

test("session id comes from invocation.agent not slash argv", async () => {
  getSession("t15-agent-only").plan = {
    taskId: "agent-tid",
    summary: "agent-sum",
    gates: {
      ddd: { requirement: "required", state: "planned" },
      ddia: { requirement: "on-demand", state: "not-required" },
      legacy: { requirement: "on-demand", state: "not-required" },
      refactor: { requirement: "on-demand", state: "not-required" },
      release: { requirement: "on-demand", state: "not-required" },
    },
  };
  const result = await executeSbtdCommand({
    agent: { id: "t15-agent-only" },
    rawInput: "plan",
  });
  assert.equal(result.kind, "success");
  assert.match(result.text, /taskId: agent-tid/);
});

test("Q4A trust handles use canonical FORBIDDEN_MODEL_KEYS from maestro", () => {
  assert.deepEqual(FORBIDDEN_MODEL_KEYS, MAESTRO_FORBIDDEN);
  const src = readFileSync(join(pkgRoot, "src/commands/sbtd.ts"), "utf8");
  assert.doesNotMatch(src, /FORBIDDEN_COMMAND_KEYS/);
  assert.match(src, /FORBIDDEN_MODEL_KEYS/);
  assert.doesNotMatch(
    src,
    /\[\s*"cwd"\s*,\s*"mcp"\s*,\s*"runRefresh"/,
  );
});

test("README documents /sbtd command and install pins", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /\/sbtd/);
  assert.match(readme, /\/sbtd plan/);
  assert.match(readme, /\/sbtd maestro/);
  assert.match(readme, /@kunolu\/dsh-sbtd@next/);
  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /640-skills/);
  assert.match(readme, /MCP/);
});
