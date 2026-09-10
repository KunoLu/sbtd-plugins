import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { apply, inject, name } from "../dist/index.js";
import { preflight as t12Preflight } from "../dist/backends/maestro.js";
import {
  SBTD_E2E_TOOL_NAME,
  createE2eTool,
  detectE2eConvention,
  modelSchemaForbidsTrustHandles,
  pickE2eInput,
  resolveE2eHost,
  resolveReportedMode,
  sbtdE2e,
} from "../dist/tools/e2e.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t13-" + label + "-"));
}

function loadPlugin(host = {}) {
  const tools = [];
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
    ...host,
  });
  return { tools };
}

function okMaestroFacts(overrides = {}) {
  return {
    detectJava: async () => ({ ok: true, version: "21" }),
    detectCli: async () => ({ ok: true, version: "1.39.0" }),
    detectDevice: async () => ({ ok: true, class: "emulator" }),
    appInstalled: true,
    appEnv: "staging://api",
    appId: "com.example.app",
    accounts: "qa@example.com",
    skipSessionWrite: true,
    ...overrides,
  };
}

test("apply registers sbtd_e2e (Q2A)", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 8);
  const e2e = tools.find((t) => t.name === SBTD_E2E_TOOL_NAME);
  assert.ok(e2e);
  assert.equal(tools[7].name, SBTD_E2E_TOOL_NAME);
});

test("typeof T12 preflight export unchanged (Q5A consume as-is)", () => {
  assert.equal(typeof t12Preflight, "function");
});

test("Q4A: model schema forbids cwd/mcp/runRefresh/serverName/toolNames", () => {
  const tool = createE2eTool();
  assert.equal(tool.name, SBTD_E2E_TOOL_NAME);
  assert.equal(modelSchemaForbidsTrustHandles(tool.parameters), true);
  const props = tool.parameters.properties;
  assert.deepEqual(Object.keys(props).sort(), [
    "action",
    "platform",
    "surface",
    "target",
  ]);
  assert.deepEqual(tool.parameters.required, ["surface", "action"]);
  assert.equal(tool.parameters.additionalProperties, false);
  assert.deepEqual(props.surface.enum, ["web", "mobile", "hybrid"]);
  assert.deepEqual(props.action.enum, ["preflight", "generate", "run"]);
});

test("Q4A: pickE2eInput rejects T10 trust keys", () => {
  for (const key of ["cwd", "mcp", "runRefresh", "serverName", "toolNames"]) {
    assert.throws(
      () => pickE2eInput({ surface: "web", action: "preflight", [key]: "x" }),
      /forbids trust handle/,
    );
  }
  assert.deepEqual(pickE2eInput({ surface: "mobile", action: "run", target: "smoke", platform: "ios" }), {
    surface: "mobile",
    action: "run",
    target: "smoke",
    platform: "ios",
  });
});

test("Q1B: mobile|hybrid generate/run with T12 not-ok ⇒ blocked; no maestro-test spawn", async () => {
  const root = fixtureRoot("blocked-preflight");
  let maestroCalls = 0;
  let preflightCalls = 0;
  const host = {
    cwd: root,
    maestro: okMaestroFacts({
      detectJava: async () => ({ ok: false, detail: "no java" }),
    }),
    preflight: async (opts) => {
      preflightCalls += 1;
      return t12Preflight(opts);
    },
    runMaestro: async () => {
      maestroCalls += 1;
      return { ok: true, summary: "should not run" };
    },
  };

  for (const surface of ["mobile", "hybrid"]) {
    for (const action of ["generate", "run"]) {
      maestroCalls = 0;
      preflightCalls = 0;
      const result = await sbtdE2e(
        `t13-${surface}-${action}`,
        { surface, action, target: "smoke" },
        host,
      );
      assert.equal(result.outcome, "blocked");
      assert.equal(result.ok, false);
      assert.equal(result.runnerStarted, false);
      assert.equal(result.calledT12Preflight, true);
      assert.equal(result.blocked.kind, "maestro-preflight-blocked");
      assert.equal(maestroCalls, 0, "must not spawn maestro test when preflight blocked");
      assert.equal(preflightCalls, 1, "must re-call T12 preflight");
    }
  }
});

test("Q1B: web generate/run does NOT call T12 preflight", async () => {
  const root = fixtureRoot("web-skip-t12");
  let preflightCalls = 0;
  let pwCalls = 0;
  const host = {
    cwd: root,
    mode: "smoke-only",
    preflight: async () => {
      preflightCalls += 1;
      return { lastPreflight: "ok", missing: [], guidance: "should not call" };
    },
    runPlaywright: async () => {
      pwCalls += 1;
      return { ok: true, summary: "web ok" };
    },
  };

  const gen = await sbtdE2e(
    "t13-web-gen",
    { surface: "web", action: "generate", target: "login" },
    host,
  );
  assert.equal(gen.ok, true);
  assert.equal(gen.calledT12Preflight, false);
  assert.equal(preflightCalls, 0);
  assert.equal(existsSync(join(root, "tests", "e2e", "login.spec.ts")), true);

  const run = await sbtdE2e(
    "t13-web-run",
    { surface: "web", action: "run", target: "login" },
    host,
  );
  assert.equal(run.ok, true);
  assert.equal(run.calledT12Preflight, false);
  assert.equal(preflightCalls, 0);
  assert.equal(pwCalls, 1);
  assert.equal(run.runnerStarted, true);
});

test("Q1B: hybrid is Maestro-class (T12), not serial dual-suite", async () => {
  const root = fixtureRoot("hybrid-maestro");
  let pwCalls = 0;
  let maestroCalls = 0;
  const result = await sbtdE2e(
    "t13-hybrid-run",
    { surface: "hybrid", action: "run", target: "smoke" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      mode: "smoke-only",
      runPlaywright: async () => {
        pwCalls += 1;
        return { ok: true };
      },
      runMaestro: async () => {
        maestroCalls += 1;
        return { ok: true, summary: "hybrid maestro ok" };
      },
    },
  );
  assert.equal(result.ok, true);
  assert.equal(result.calledT12Preflight, true);
  assert.equal(maestroCalls, 1);
  assert.equal(pwCalls, 0, "hybrid must not run Playwright in the same call");
});

test("Q1B: mobile generate/run always re-calls T12 even if session looks ok", async () => {
  const root = fixtureRoot("recall-t12");
  let calls = 0;
  const host = {
    cwd: root,
    maestro: okMaestroFacts(),
    mode: "smoke-only",
    preflight: async (opts) => {
      calls += 1;
      return t12Preflight(opts);
    },
    runMaestro: async () => ({ ok: true, summary: "ok" }),
  };
  await sbtdE2e("t13-recall-a", { surface: "mobile", action: "run" }, host);
  await sbtdE2e("t13-recall-b", { surface: "mobile", action: "generate" }, host);
  assert.equal(calls, 2);
});

test("Q3A: existing maestro/flow wins over AGENTS default", () => {
  const root = fixtureRoot("conv-flow");
  mkdirSync(join(root, "maestro", "flow"), { recursive: true });
  writeFileSync(join(root, "maestro", "flow", "smoke.yml"), "appId: x\n---\n- launchApp\n");
  const c = detectE2eConvention(root, "mobile");
  assert.equal(c.kind, "existing-maestro-flow");
  assert.equal(c.flowRoot, join(root, "maestro", "flow"));
});

test("Q3A: agents-default when no project E2E dirs", () => {
  const root = fixtureRoot("conv-default");
  const mobile = detectE2eConvention(root, "mobile");
  assert.equal(mobile.kind, "agents-default");
  assert.equal(mobile.flowRoot, join(root, "maestro", "flow"));
  const web = detectE2eConvention(root, "web");
  assert.equal(web.kind, "agents-default");
  assert.equal(web.playwrightRoot, join(root, "tests", "e2e"));
});

test("Q6A: busy browser controller ⇒ blocked (no steal)", async () => {
  const root = fixtureRoot("browser-busy");
  const result = await sbtdE2e(
    "t13-busy",
    { surface: "web", action: "run", target: "smoke" },
    {
      cwd: root,
      browserControllerBusy: true,
      runPlaywright: async () => {
        throw new Error("must not run");
      },
    },
  );
  assert.equal(result.outcome, "blocked");
  assert.equal(result.blocked.kind, "browser-controller-busy");
  assert.equal(result.runnerStarted, false);
});

test("Q6A: runner started + assertions lost ⇒ failed (not blocked)", async () => {
  const root = fixtureRoot("failed-run");
  const result = await sbtdE2e(
    "t13-failed",
    { surface: "mobile", action: "run", target: "smoke" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      mode: "smoke-only",
      runMaestro: async () => ({
        ok: false,
        failed: true,
        summary: "assertion lost",
      }),
    },
  );
  assert.equal(result.outcome, "failed");
  assert.equal(result.ok, false);
  assert.equal(result.runnerStarted, true);
  assert.equal(result.blocked, undefined);
});

test("Q6A: skipped-by-user when user declined assist", async () => {
  const result = await sbtdE2e(
    "t13-skip",
    { surface: "mobile", action: "preflight" },
    { userDeclinedAssist: true, cwd: fixtureRoot("skip") },
  );
  assert.equal(result.outcome, "skipped-by-user");
  assert.equal(result.runnerStarted, false);
  assert.equal(result.calledT12Preflight, false);
});

test("Q6A: mock/contract modes cannot report full-stack", () => {
  assert.equal(resolveReportedMode("mock-backed"), "mock-backed");
  assert.equal(resolveReportedMode("contract-backed"), "contract-backed");
  assert.equal(resolveReportedMode("full-stack"), "full-stack");
  assert.equal(resolveReportedMode("smoke-only"), "smoke-only");
});

test("Q6A: mock-backed run keeps mode label (not full-stack)", async () => {
  const root = fixtureRoot("mock-mode");
  const result = await sbtdE2e(
    "t13-mock",
    { surface: "web", action: "run", target: "smoke" },
    {
      cwd: root,
      mode: "mock-backed",
      runPlaywright: async () => ({ ok: true, summary: "mock pass" }),
    },
  );
  assert.equal(result.mode, "mock-backed");
  assert.notEqual(result.mode, "full-stack");
});

test("mobile generate writes flow under convention path after ok preflight", async () => {
  const root = fixtureRoot("gen-flow");
  mkdirSync(join(root, "maestro", "flow"), { recursive: true });
  const result = await sbtdE2e(
    "t13-gen",
    { surface: "mobile", action: "generate", target: "login" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      mode: "smoke-only",
    },
  );
  assert.equal(result.ok, true);
  assert.equal(result.outcome, "ok");
  assert.equal(result.convention, "existing-maestro-flow");
  assert.equal(existsSync(join(root, "maestro", "flow", "login.yml")), true);
  const body = readFileSync(join(root, "maestro", "flow", "login.yml"), "utf8");
  assert.match(body, /appId: com\.example\.app/);
});

test("generate missing selectors ⇒ blocked (no fragile flow)", async () => {
  const root = fixtureRoot("no-sel");
  const result = await sbtdE2e(
    "t13-nosel",
    { surface: "mobile", action: "generate", target: "x" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: false,
    },
  );
  assert.equal(result.outcome, "blocked");
  assert.equal(result.blocked.kind, "missing-selectors");
  assert.equal(result.runnerStarted, false);
  assert.equal(existsSync(join(root, "maestro", "flow", "x.yml")), false);
});

test("resolveE2eHost prefers e2eHost.cwd", () => {
  const host = resolveE2eHost({
    tools: { register() {} },
    cwd: "/from-ctx",
    e2eHost: { cwd: "/from-e2e" },
  });
  assert.equal(host.cwd, "/from-e2e");
});

test("unit path never requires live maestro/browser binaries (Q3A)", async () => {
  // Hermetic: all detect* + runners injected; no PATH maestro/playwright needed.
  const root = fixtureRoot("hermetic");
  const result = await sbtdE2e(
    "t13-hermetic",
    { surface: "mobile", action: "preflight" },
    { cwd: root, maestro: okMaestroFacts() },
  );
  assert.equal(result.outcome, "ok");
  assert.equal(result.calledT12Preflight, true);
  assert.equal(result.runnerStarted, false);
});
