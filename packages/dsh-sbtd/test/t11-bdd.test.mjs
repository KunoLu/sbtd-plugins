import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { apply, inject, name } from "../dist/index.js";
import { getSession } from "../dist/state.js";
import {
  SBTD_BDD_TOOL_NAME,
  createBddTool,
  detectFeatureConvention,
  modelSchemaForbidsTrustHandles,
  resolveBddHost,
  sbtdBdd,
  validateExtraPaths,
} from "../dist/tools/bdd.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t11-" + label + "-"));
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

function gitStatusShort(cwd) {
  const r = spawnSync("git", ["status", "--short"], {
    cwd,
    encoding: "utf8",
  });
  return (r.stdout || "").trim();
}

test("apply registers sbtd_bdd (Q3A)", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 7);
  assert.equal(tools[6].name, SBTD_BDD_TOOL_NAME);
});

test("Q1C: model schema forbids cwd/mcp/runRefresh/serverName/toolNames", () => {
  const tool = createBddTool();
  assert.equal(tool.name, SBTD_BDD_TOOL_NAME);
  assert.equal(modelSchemaForbidsTrustHandles(tool.parameters), true);
  const props = tool.parameters.properties;
  assert.deepEqual(Object.keys(props).sort(), [
    "body",
    "content",
    "cross_repo_required",
    "extra_paths",
    "intent",
    "target",
  ]);
  assert.deepEqual(tool.parameters.required, ["intent"]);
  assert.equal(tool.parameters.additionalProperties, false);
});

test("Q1C: write ignores model cwd if smuggled; host cwd wins", () => {
  const root = fixtureRoot("host-cwd");
  const result = sbtdBdd(
    "t11-host-cwd",
    {
      intent: "write",
      target: "login",
      content: "Feature: 登录\n  Scenario: ok\n    Given x\n    When y\n    Then z\n",
      // smuggled — pickBddInput / host must not honor
      cwd: "/tmp/evil",
    },
    { cwd: root },
  );
  assert.equal(result.status, "done");
  assert.equal(result.mutation, "write");
  assert.ok(result.path.startsWith(root));
  assert.equal(existsSync(join(root, "features", "login.feature")), true);
  assert.equal(existsSync("/tmp/evil/features/login.feature"), false);
});

test("Q1C: extra_paths on write ⇒ blocked", () => {
  const root = fixtureRoot("write-extra");
  const result = sbtdBdd(
    "t11-write-extra",
    {
      intent: "write",
      target: "x",
      content: "Feature: x\n  Scenario: a\n    Given a\n    When b\n    Then c\n",
      extra_paths: [root],
    },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "extra-paths-not-allowed");
});

test("Q1C: cross_repo_required without extras ⇒ blocked", () => {
  const root = fixtureRoot("cross-miss");
  const result = sbtdBdd(
    "t11-cross-miss",
    { intent: "sync", cross_repo_required: true },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "cross-repo-missing");
  assert.equal(result.mutation, "none");
});

test("Q1C: extra path not host-allowed ⇒ blocked, not scanned", () => {
  const root = fixtureRoot("extra-deny");
  const sibling = fixtureRoot("sibling-secret");
  mkdirSync(join(sibling, "features"), { recursive: true });
  writeFileSync(
    join(sibling, "features", "secret.feature"),
    "Feature: secret\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const allowed = fixtureRoot("allowed-only");
  const result = sbtdBdd(
    "t11-extra-deny",
    { intent: "read", extra_paths: [sibling] },
    { cwd: root, allowedExtraRoots: [allowed] },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "extra-path-invalid");
  assert.match(result.note, /not-host-allowed/);
});

test("Q1C: validated extra_paths included in read catalog", () => {
  const root = fixtureRoot("extra-ok");
  mkdirSync(join(root, "features"), { recursive: true });
  writeFileSync(
    join(root, "features", "local.feature"),
    "Feature: local\n  Scenario: l\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const sibling = fixtureRoot("sibling-ok");
  mkdirSync(join(sibling, "features"), { recursive: true });
  writeFileSync(
    join(sibling, "features", "other.feature"),
    "Feature: other\n  Scenario: o\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const result = sbtdBdd(
    "t11-extra-ok",
    { intent: "read", extra_paths: [sibling] },
    { cwd: root, allowedExtraRoots: [sibling] },
  );
  assert.equal(result.status, "done");
  assert.equal(result.mutation, "none");
  assert.equal(result.catalog.length, 2);
  const paths = result.catalog.map((e) => e.path).sort();
  assert.ok(paths.some((p) => p.includes("local.feature")));
  assert.ok(paths.some((p) => p.includes("other.feature")));
});

test("Q2B: existing features/ reused; AGENTS default only when none", () => {
  const withFeatures = fixtureRoot("conv-features");
  mkdirSync(join(withFeatures, "features"), { recursive: true });
  writeFileSync(
    join(withFeatures, "features", "existing.feature"),
    "Feature: existing\n  Scenario: e\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const c1 = detectFeatureConvention(withFeatures);
  assert.equal(c1.kind, "existing-features-dir");

  const empty = fixtureRoot("conv-empty");
  const c2 = detectFeatureConvention(empty);
  assert.equal(c2.kind, "agents-default");
  assert.equal(c2.featureRoot, join(empty, "features"));
});

test("Q2B: write in consumer cwd does not dual-write plugin fixtures", () => {
  const consumer = fixtureRoot("consumer");
  // Simulate a sibling path that looks like plugin fixtures — must not be touched.
  const pluginFeatures = fixtureRoot("plugin-features");
  mkdirSync(join(pluginFeatures, "features"), { recursive: true });
  writeFileSync(
    join(pluginFeatures, "features", "keep.feature"),
    "Feature: keep\n  Scenario: k\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const before = readdirSync(join(pluginFeatures, "features"));
  const result = sbtdBdd(
    "t11-no-dual",
    {
      intent: "write",
      target: "login",
      content:
        "Feature: 用户登录\n  Scenario: 登录成功\n    Given 用户已注册\n    When 用户提交正确密码\n    Then 进入工作区\n",
    },
    { cwd: consumer },
  );
  assert.equal(result.status, "done");
  assert.equal(existsSync(join(consumer, "features", "login.feature")), true);
  assert.deepEqual(readdirSync(join(pluginFeatures, "features")), before);
  assert.equal(existsSync(join(pluginFeatures, "features", "login.feature")), false);
});

test("Q5A: read ⇒ Mutation none and clean git status", () => {
  const root = fixtureRoot("read-clean");
  mkdirSync(join(root, "features"), { recursive: true });
  writeFileSync(
    join(root, "features", "demo.feature"),
    "Feature: demo\n  Scenario: d\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  // init git so status is meaningful
  spawnSync("git", ["init"], { cwd: root, encoding: "utf8" });
  spawnSync("git", ["add", "features/demo.feature"], {
    cwd: root,
    encoding: "utf8",
  });
  spawnSync(
    "git",
    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
    { cwd: root, encoding: "utf8" },
  );
  assert.equal(gitStatusShort(root), "");
  const result = sbtdBdd("t11-read", { intent: "read" }, { cwd: root });
  assert.equal(result.status, "done");
  assert.equal(result.mutation, "none");
  assert.equal(result.catalog.length, 1);
  assert.equal(gitStatusShort(root), "");
});

test("write login default template (acceptance)", () => {
  const root = fixtureRoot("login-default");
  const result = sbtdBdd(
    "t11-login",
    { intent: "write", target: "login" },
    { cwd: root },
  );
  assert.equal(result.status, "done");
  const text = readFileSync(join(root, "features", "login.feature"), "utf8");
  assert.match(text, /Feature: 用户登录/);
  assert.match(text, /Scenario: 已注册用户使用正确密码登录/);
  assert.match(text, /Given 用户已经注册账号/);
  assert.doesNotMatch(text, /# language: zh-CN/);
});

test("write relative path target", () => {
  const root = fixtureRoot("rel-path");
  mkdirSync(join(root, "features", "auth"), { recursive: true });
  const result = sbtdBdd(
    "t11-rel",
    {
      intent: "write",
      target: "features/auth/signup.feature",
      content:
        "Feature: 注册\n  Scenario: 新用户注册\n    Given 打开注册页\n    When 提交表单\n    Then 创建账号\n",
    },
    { cwd: root },
  );
  assert.equal(result.status, "done");
  assert.equal(
    existsSync(join(root, "features", "auth", "signup.feature")),
    true,
  );
});

test("write rejects absolute / escaping target", () => {
  const root = fixtureRoot("escape");
  const abs = sbtdBdd(
    "t11-abs",
    {
      intent: "write",
      target: "/tmp/evil.feature",
      content: "Feature: x\n  Scenario: a\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  assert.equal(abs.status, "blocked");
  assert.equal(abs.blocked.kind, "invalid-target");

  const esc = sbtdBdd(
    "t11-esc",
    {
      intent: "write",
      target: "../outside.feature",
      content: "Feature: x\n  Scenario: a\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  assert.equal(esc.status, "blocked");
});

test("Q6A: no session.bdd side effects", () => {
  const root = fixtureRoot("no-session");
  const id = "t11-no-session-bdd";
  sbtdBdd(
    id,
    {
      intent: "write",
      target: "x",
      content: "Feature: x\n  Scenario: a\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  const session = getSession(id);
  assert.equal(Object.hasOwn(session, "bdd"), false);
  assert.equal(session.bdd, undefined);
  assert.equal(session.validate != null, true);
});

test("resolveBddHost prefers bddHost.cwd then ctx.cwd", () => {
  const tools = { register() {} };
  const a = resolveBddHost({
    tools,
    cwd: "/ctx",
    bddHost: { cwd: "/explicit" },
  });
  assert.equal(a.cwd, "/explicit");
  const b = resolveBddHost({ tools, cwd: "/ctx" });
  assert.equal(b.cwd, "/ctx");
});

test("validateExtraPaths rejects missing dirs", () => {
  const root = fixtureRoot("val-extra");
  const r = validateExtraPaths(root, [join(root, "nope")], {});
  assert.equal(r.validated.length, 0);
  assert.equal(r.rejected[0].reason, "not-a-directory");
});

test("sync inventory run without content", () => {
  const root = fixtureRoot("sync-inv");
  mkdirSync(join(root, "features"), { recursive: true });
  writeFileSync(
    join(root, "features", "a.feature"),
    "Feature: a\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const result = sbtdBdd("t11-sync", { intent: "sync" }, { cwd: root });
  assert.equal(result.status, "done");
  assert.equal(result.sync.mode, "run");
  assert.equal(result.mutation, "none");
  assert.ok(result.sync.features.length >= 1);
});

test("isConcurrencySafe true only for read", () => {
  const tool = createBddTool();
  assert.equal(tool.isConcurrencySafe({ intent: "read" }), true);
  assert.equal(tool.isConcurrencySafe({ intent: "write" }), false);
  assert.equal(tool.isConcurrencySafe({ intent: "sync" }), false);
});
