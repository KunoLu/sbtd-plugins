import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import {
  parseSbtdArgv,
  runSbtdCommand,
} from "../dist/commands/sbtd.js";
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
  assert.equal(tools.length, 9);
  assert.equal(tools.some((t) => t.name === "sbtd"), false);
});

test("bare /sbtd on empty session is read-only no-plan", async () => {
  const out = await runSbtdCommand(undefined, { sessionId: "t15-empty" });
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

test("unknown subcommands are rejected", () => {
  for (const token of ["validate", "e2e", "lessons"]) {
    assert.throws(
      () => parseSbtdArgv(token),
      new RegExp(`unknown subcommand: ${token}`),
    );
  }
  const { commands } = loadPlugin();
  assert.equal(commands.length, 1);
  assert.equal(commands[0].name, "sbtd");
});

test("T10 trust keys forbidden on command input object", async () => {
  for (const key of [
    "cwd",
    "mcp",
    "runRefresh",
    "serverName",
    "toolNames",
  ]) {
    await assert.rejects(
      () => runSbtdCommand({ [key]: key === "cwd" ? "/tmp" : {} }),
      new RegExp(`forbids trust handle "${key}"`),
    );
  }
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
