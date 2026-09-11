import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { apply, inject, name, SBTD_LESSONS_TOOL_NAME } from "../dist/index.js";
import { preflight as t12Preflight } from "../dist/backends/maestro.js";
import {
  SBTD_E2E_TOOL_NAME,
  createE2eTool,
  defaultRunMaestro,
  defaultRunPlaywright,
  detectE2eConvention,
  modelSchemaForbidsTrustHandles,
  pickE2eInput,
  resolveE2eHost,
  resolveE2eTargetPath,
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

/** Affirmative generate facts (Q4A / R2) — undefined selectorsReady must not pass. */
function readyGenerateFacts(overrides = {}) {
  return {
    selectorsReady: true,
    credentialsReady: true,
    selectorFacts: ["Home"],
    ...overrides,
  };
}

test("apply registers sbtd_e2e (Q2A)", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 9);
  const e2e = tools.find((t) => t.name === SBTD_E2E_TOOL_NAME);
  assert.ok(e2e);
  assert.equal(tools[7].name, SBTD_E2E_TOOL_NAME);
  assert.equal(tools[8].name, SBTD_LESSONS_TOOL_NAME);
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
    ...readyGenerateFacts(),
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
    ...readyGenerateFacts(),
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
      ...readyGenerateFacts({ selectorFacts: ["Login"] }),
    },
  );
  assert.equal(result.ok, true);
  assert.equal(result.outcome, "ok");
  assert.equal(result.convention, "existing-maestro-flow");
  assert.equal(existsSync(join(root, "maestro", "flow", "login.yml")), true);
  const body = readFileSync(join(root, "maestro", "flow", "login.yml"), "utf8");
  assert.match(body, /appId: com\.example\.app/);
  assert.match(body, /assertVisible: "Login"/);
  assert.doesNotMatch(body, /assertVisible: "\.\*"/);
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

test("R2: selectorsReady undefined blocks generate (affirmative required)", async () => {
  const root = fixtureRoot("sel-undef");
  const result = await sbtdE2e(
    "t13-sel-undef",
    { surface: "mobile", action: "generate", target: "x" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      // selectorsReady intentionally omitted
      credentialsReady: true,
      selectorFacts: ["Home"],
    },
  );
  assert.equal(result.outcome, "blocked");
  assert.equal(result.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "maestro", "flow", "x.yml")), false);
});

test("R2: selectorsReady true but empty selectorFacts blocks generate", async () => {
  const root = fixtureRoot("sel-empty");
  const result = await sbtdE2e(
    "t13-sel-empty",
    { surface: "web", action: "generate", target: "x" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: [],
    },
  );
  assert.equal(result.outcome, "blocked");
  assert.equal(result.blocked.kind, "missing-selectors");
});

test("resolveE2eHost prefers e2eHost.cwd", () => {
  const host = resolveE2eHost({
    tools: { register() {} },
    cwd: "/from-ctx",
    e2eHost: { cwd: "/from-e2e" },
  });
  assert.equal(host.cwd, "/from-e2e");
});

test("R3: resolveE2eHost wires default production runners", () => {
  const host = resolveE2eHost({
    tools: { register() {} },
    cwd: "/proj",
  });
  assert.equal(host.runMaestro, defaultRunMaestro);
  assert.equal(host.runPlaywright, defaultRunPlaywright);
});

test("R3: resolveE2eHost keeps explicit runner stubs (unit override)", () => {
  const stub = async () => ({ ok: true });
  const host = resolveE2eHost({
    tools: { register() {} },
    e2eHost: { cwd: "/proj", runMaestro: stub, runPlaywright: stub },
  });
  assert.equal(host.runMaestro, stub);
  assert.equal(host.runPlaywright, stub);
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

test("R1: generate rejects cwd-relative overwrite outside flow/spec root", async () => {
  const root = fixtureRoot("overwrite");
  mkdirSync(join(root, "src"), { recursive: true });
  writeFileSync(join(root, "src", "index.ts"), "export {}\n");
  mkdirSync(join(root, "docs"), { recursive: true });
  writeFileSync(join(root, "docs", "note.yml"), "keep: me\n");

  const web = await sbtdE2e(
    "t13-ow-web",
    { surface: "web", action: "generate", target: "src/index.ts" },
    { cwd: root, ...readyGenerateFacts() },
  );
  assert.equal(web.outcome, "blocked");
  assert.equal(web.blocked.kind, "invalid-target");
  assert.equal(readFileSync(join(root, "src", "index.ts"), "utf8"), "export {}\n");

  const mobile = await sbtdE2e(
    "t13-ow-mobile",
    { surface: "mobile", action: "generate", target: "docs/note.yml" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      ...readyGenerateFacts(),
    },
  );
  assert.equal(mobile.outcome, "blocked");
  assert.equal(mobile.blocked.kind, "invalid-target");
  assert.equal(readFileSync(join(root, "docs", "note.yml"), "utf8"), "keep: me\n");
});

test("R1: resolveE2eTargetPath allows relative path under flow root + yml", () => {
  const root = fixtureRoot("rel-ok");
  mkdirSync(join(root, "maestro", "flow"), { recursive: true });
  const convention = detectE2eConvention(root, "mobile");
  const ok = resolveE2eTargetPath(
    root,
    "mobile",
    "maestro/flow/login.yml",
    convention,
  );
  assert.equal(ok.ok, true);
  assert.equal(ok.path, join(root, "maestro", "flow", "login.yml"));
  const badExt = resolveE2eTargetPath(
    root,
    "mobile",
    "maestro/flow/login.ts",
    convention,
  );
  assert.equal(badExt.ok, false);
  const badRoot = resolveE2eTargetPath(root, "mobile", "docs/note.yml", convention);
  assert.equal(badRoot.ok, false);
});

test("R4: ok without native reporter file does not synthesize reportPath/md", async () => {
  const root = fixtureRoot("no-report");
  const result = await sbtdE2e(
    "t13-noreport",
    { surface: "web", action: "run", target: "smoke" },
    {
      cwd: root,
      mode: "smoke-only",
      runPlaywright: async () => ({ ok: true, summary: "ok bare" }),
    },
  );
  assert.equal(result.ok, true);
  assert.equal(result.reportPath, undefined);
  assert.equal(result.reportMdPath, undefined);
  // reportDir may be mkdir'd, but no formal .html/.md claims without native evidence
  const reportDir = join(root, "tests", "e2e", "reports", "html");
  if (existsSync(reportDir)) {
    const { readdirSync } = await import("node:fs");
    assert.equal(
      readdirSync(reportDir).filter((n) => /\.(html|md|xml)$/i.test(n)).length,
      0,
    );
  }
});

test("R4: reportPath + 中文 md only when native reporter file exists", async () => {
  const root = fixtureRoot("native-report");
  const reportDir = join(root, ".maestro", "reports");
  mkdirSync(reportDir, { recursive: true });
  const native = join(reportDir, "maestro-report-smoke-native.xml");
  writeFileSync(native, "<testsuite/>\n");
  const result = await sbtdE2e(
    "t13-native-report",
    { surface: "mobile", action: "run", target: "smoke" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      mode: "smoke-only",
      runMaestro: async () => ({
        ok: true,
        summary: "native ok",
        reportPath: native,
      }),
    },
  );
  assert.equal(result.ok, true);
  assert.equal(result.reportPath, native);
  assert.ok(result.reportMdPath);
  assert.equal(existsSync(result.reportMdPath), true);
  const md = readFileSync(result.reportMdPath, "utf8");
  assert.match(md, /E2E 报告/);
});

test("S1: mobile invalid target still re-calls T12 before reject", async () => {
  const root = fixtureRoot("t12-before-target");
  let calls = 0;
  const result = await sbtdE2e(
    "t13-t12-order",
    { surface: "mobile", action: "generate", target: "/abs/evil.yml" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      ...readyGenerateFacts(),
      preflight: async (opts) => {
        calls += 1;
        return t12Preflight(opts);
      },
    },
  );
  assert.equal(calls, 1);
  assert.equal(result.calledT12Preflight, true);
  assert.equal(result.outcome, "blocked");
  assert.equal(result.blocked.kind, "invalid-target");
});

test("S2: root e2e/ wins as existing Playwright convention", () => {
  const root = fixtureRoot("root-e2e");
  mkdirSync(join(root, "e2e"), { recursive: true });
  const c = detectE2eConvention(root, "web");
  assert.equal(c.kind, "existing-playwright-e2e");
  assert.equal(c.playwrightRoot, join(root, "e2e"));
});


test("R1r2: generate rejects flow symlink that escapes asset root", async () => {
  const root = fixtureRoot("symlink-escape");
  const flowDir = join(root, "maestro", "flow");
  mkdirSync(flowDir, { recursive: true });
  const outside = join(root, "outside-secret.yml");
  writeFileSync(outside, "secret: keep\n");
  symlinkSync(outside, join(flowDir, "login.yml"));

  const byPath = await sbtdE2e(
    "t13-symlink-path",
    { surface: "mobile", action: "generate", target: "maestro/flow/login.yml" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      ...readyGenerateFacts({ selectorFacts: ["Login"] }),
    },
  );
  assert.equal(byPath.outcome, "blocked");
  assert.equal(byPath.blocked.kind, "invalid-target");
  assert.equal(readFileSync(outside, "utf8"), "secret: keep\n");

  const bySlug = await sbtdE2e(
    "t13-symlink-slug",
    { surface: "mobile", action: "generate", target: "login" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      ...readyGenerateFacts({ selectorFacts: ["Login"] }),
    },
  );
  assert.equal(bySlug.outcome, "blocked");
  assert.equal(bySlug.blocked.kind, "invalid-target");
  assert.equal(readFileSync(outside, "utf8"), "secret: keep\n");
  assert.doesNotMatch(readFileSync(outside, "utf8"), /assertVisible/);
});

test("R1r2: resolveE2eTargetPath rejects symlink escape under flow root", () => {
  const root = fixtureRoot("symlink-resolve");
  const flowDir = join(root, "maestro", "flow");
  mkdirSync(flowDir, { recursive: true });
  const outside = join(root, "evil.yml");
  writeFileSync(outside, "x: 1\n");
  symlinkSync(outside, join(flowDir, "login.yml"));
  const convention = detectE2eConvention(root, "mobile");
  const bad = resolveE2eTargetPath(
    root,
    "mobile",
    "maestro/flow/login.yml",
    convention,
  );
  assert.equal(bad.ok, false);
});

test("R2r2: wildcard-only selectorFacts (.*) block generate", async () => {
  const root = fixtureRoot("wild-only");
  const result = await sbtdE2e(
    "t13-wild",
    { surface: "mobile", action: "generate", target: "x" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: true,
      credentialsReady: true,
      selectorFacts: [".*"],
    },
  );
  assert.equal(result.outcome, "blocked");
  assert.equal(result.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "maestro", "flow", "x.yml")), false);

  const web = await sbtdE2e(
    "t13-wild-web",
    { surface: "web", action: "generate", target: "x" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: [".*", "/.*/", "/.*/i"],
    },
  );
  assert.equal(web.outcome, "blocked");
  assert.equal(web.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "tests", "e2e", "x.spec.ts")), false);
});

test("R2r2: mixed facts drop wildcards but keep concrete locators", async () => {
  const root = fixtureRoot("wild-mix");
  const result = await sbtdE2e(
    "t13-wild-mix",
    { surface: "mobile", action: "generate", target: "login" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: true,
      credentialsReady: true,
      selectorFacts: [".*", "Login", "/.*/"],
    },
  );
  assert.equal(result.ok, true);
  const body = readFileSync(join(root, "maestro", "flow", "login.yml"), "utf8");
  assert.match(body, /assertVisible: "Login"/);
  assert.doesNotMatch(body, /assertVisible: "\.\*"/);
  assert.doesNotMatch(body, /toHaveTitle\(\/\.\*\//);
});

test("R1r3: missing asset root still realpaths symlinked ancestor (web tests/)", async () => {
  const root = fixtureRoot("missing-root-symlink");
  const outside = fixtureRoot("missing-root-outside");
  mkdirSync(outside, { recursive: true });
  // cwd/tests → outside; tests/e2e absent (agents-default). Must not mkdir/write outside.
  symlinkSync(outside, join(root, "tests"));

  const bySlug = await sbtdE2e(
    "t13-missing-root-slug",
    { surface: "web", action: "generate", target: "login" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: ["Login"],
    },
  );
  assert.equal(bySlug.outcome, "blocked");
  assert.equal(bySlug.blocked.kind, "invalid-target");
  assert.equal(existsSync(join(outside, "e2e", "login.spec.ts")), false);
  assert.equal(existsSync(join(root, "tests", "e2e", "login.spec.ts")), false);

  const byRel = await sbtdE2e(
    "t13-missing-root-rel",
    { surface: "web", action: "generate", target: "tests/e2e/escape.spec.ts" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: ["Login"],
    },
  );
  assert.equal(byRel.outcome, "blocked");
  assert.equal(byRel.blocked.kind, "invalid-target");
  assert.equal(existsSync(join(outside, "e2e", "escape.spec.ts")), false);
});

test("R1r3: agents-default still writes when tests/e2e absent (no symlink)", async () => {
  const root = fixtureRoot("missing-root-ok");
  const result = await sbtdE2e(
    "t13-missing-root-ok",
    { surface: "web", action: "generate", target: "login" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: ["Welcome"],
    },
  );
  assert.equal(result.ok, true);
  assert.equal(existsSync(join(root, "tests", "e2e", "login.spec.ts")), true);
});

test("R2r3: grouped catch-all selectorFacts (.*) / /(.*)/ block generate", async () => {
  const root = fixtureRoot("wild-group");
  const mobile = await sbtdE2e(
    "t13-wild-group-m",
    { surface: "mobile", action: "generate", target: "x" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: true,
      credentialsReady: true,
      selectorFacts: ["(.*)"],
    },
  );
  assert.equal(mobile.outcome, "blocked");
  assert.equal(mobile.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "maestro", "flow", "x.yml")), false);

  const web = await sbtdE2e(
    "t13-wild-group-w",
    { surface: "web", action: "generate", target: "x" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: ["(.*)", "/(.*)/", "/(?:.+)/i", "((.*))"],
    },
  );
  assert.equal(web.outcome, "blocked");
  assert.equal(web.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "tests", "e2e", "x.spec.ts")), false);
});

test("R2r3: mixed facts drop grouped catch-alls but keep concrete locators", async () => {
  const root = fixtureRoot("wild-group-mix");
  const result = await sbtdE2e(
    "t13-wild-group-mix",
    { surface: "mobile", action: "generate", target: "login" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: true,
      credentialsReady: true,
      selectorFacts: ["(.*)", "Login", "/(.*)/"],
    },
  );
  assert.equal(result.ok, true);
  const body = readFileSync(join(root, "maestro", "flow", "login.yml"), "utf8");
  assert.match(body, /assertVisible: "Login"/);
  assert.doesNotMatch(body, /assertVisible: "\(\.\*\)"/);
});

test("R2r4: anchored grouped catch-all selectorFacts ^(.*)$ / /^(.*)$/ block generate", async () => {
  const root = fixtureRoot("wild-anchor-group");
  const mobile = await sbtdE2e(
    "t13-wild-anchor-m",
    { surface: "mobile", action: "generate", target: "x" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: true,
      credentialsReady: true,
      selectorFacts: ["^(.*)$"],
    },
  );
  assert.equal(mobile.outcome, "blocked");
  assert.equal(mobile.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "maestro", "flow", "x.yml")), false);

  const web = await sbtdE2e(
    "t13-wild-anchor-w",
    { surface: "web", action: "generate", target: "x" },
    {
      cwd: root,
      selectorsReady: true,
      selectorFacts: ["^(.*)$", "/^(.*)$/", "/^(?:.+)$/i", "^((.*))$"],
    },
  );
  assert.equal(web.outcome, "blocked");
  assert.equal(web.blocked.kind, "missing-selectors");
  assert.equal(existsSync(join(root, "tests", "e2e", "x.spec.ts")), false);
});

test("R2r4: mixed facts drop anchored grouped catch-alls but keep concrete locators", async () => {
  const root = fixtureRoot("wild-anchor-group-mix");
  const result = await sbtdE2e(
    "t13-wild-anchor-mix",
    { surface: "mobile", action: "generate", target: "login" },
    {
      cwd: root,
      maestro: okMaestroFacts(),
      selectorsReady: true,
      credentialsReady: true,
      selectorFacts: ["^(.*)$", "Login", "/^(.*)$/"],
    },
  );
  assert.equal(result.ok, true);
  const body = readFileSync(join(root, "maestro", "flow", "login.yml"), "utf8");
  assert.match(body, /assertVisible: "Login"/);
  assert.doesNotMatch(body, /assertVisible: "\^\(\.\*\)\$"/);
});

test("R3r2/Q6A: defaultRunMaestro timeout after spawn ⇒ failed (not didNotStart)", async () => {
  const root = fixtureRoot("timeout-m");
  mkdirSync(join(root, "maestro", "flow"), { recursive: true });
  const flow = join(root, "maestro", "flow", "smoke.yml");
  writeFileSync(flow, "appId: com.example.app\n---\n- launchApp\n");
  const bin = join(root, "bin");
  mkdirSync(bin, { recursive: true });
  const maestroShim = join(bin, "maestro");
  writeFileSync(
    maestroShim,
    "#!/bin/sh\nwhile true; do sleep 1; done\n",
    { mode: 0o755 },
  );
  const prevPath = process.env.PATH;
  process.env.PATH = `${bin}:${prevPath ?? ""}`;
  try {
    const result = await defaultRunMaestro(
      {
        cwd: root,
        surface: "mobile",
        action: "run",
        targetPath: flow,
        reportDir: join(root, ".maestro", "reports"),
        mode: "smoke-only",
      },
      300,
    );
    assert.equal(result.ok, false);
    assert.equal(result.failed, true);
    assert.notEqual(result.didNotStart, true);
    assert.match(String(result.summary), /timed out/i);
  } finally {
    process.env.PATH = prevPath;
  }
});

test("R4r2/Q6A: defaultRunPlaywright with no package ⇒ didNotStart (blocked)", async () => {
  const root = fixtureRoot("npx-miss");
  mkdirSync(join(root, "tests", "e2e"), { recursive: true });
  const spec = join(root, "tests", "e2e", "smoke.spec.ts");
  writeFileSync(spec, "import { test } from '@playwright/test';\ntest('x', async () => {});\n");
  // No node_modules/@playwright — must not spawn npx and claim failed.
  const result = await defaultRunPlaywright(
    {
      cwd: root,
      surface: "web",
      action: "run",
      targetPath: spec,
      reportDir: join(root, "tests", "e2e", "reports", "html"),
      mode: "smoke-only",
    },
    5_000,
  );
  assert.equal(result.ok, false);
  assert.equal(result.didNotStart, true);
  assert.notEqual(result.failed, true);
  assert.match(String(result.summary), /Playwright package not found|npx --no-install/i);

  const mapped = await sbtdE2e(
    "t13-npx-map",
    { surface: "web", action: "run", target: "smoke" },
    {
      cwd: root,
      mode: "smoke-only",
      runPlaywright: async () => result,
    },
  );
  assert.equal(mapped.outcome, "blocked");
  assert.equal(mapped.runnerStarted, false);
});
