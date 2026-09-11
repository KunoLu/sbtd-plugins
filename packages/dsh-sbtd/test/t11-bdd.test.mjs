import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  symlinkSync,
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
  findDistinctFeatureParentDirs,
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
  assert.equal(tools.length, 9);
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

test("validateExtraPaths rejects missing dirs when allowlist set", () => {
  const root = fixtureRoot("val-extra");
  const r = validateExtraPaths(root, [join(root, "nope")], {
    allowedExtraRoots: [root],
  });
  assert.equal(r.validated.length, 0);
  assert.equal(r.rejected[0].reason, "not-a-directory");
});

test("R2: sync inventory-only is blocked (not a successful Sync Mode)", () => {
  const root = fixtureRoot("sync-inv");
  mkdirSync(join(root, "features"), { recursive: true });
  writeFileSync(
    join(root, "features", "a.feature"),
    "Feature: a\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const result = sbtdBdd("t11-sync", { intent: "sync" }, { cwd: root });
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "sync-not-capable");
  assert.equal(result.sync.mode, "blocked");
  assert.equal(result.mutation, "none");
  assert.equal(result.ok, false);
  assert.ok(result.sync.features.length >= 1);
});

test("R1 Q1C: extra_paths with unset/empty allowlist ⇒ blocked (default-deny)", () => {
  const root = fixtureRoot("extra-no-allow");
  const sibling = fixtureRoot("sibling-exist");
  mkdirSync(join(sibling, "features"), { recursive: true });
  writeFileSync(
    join(sibling, "features", "x.feature"),
    "Feature: x\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const unset = sbtdBdd(
    "t11-extra-unset",
    { intent: "read", extra_paths: [sibling] },
    { cwd: root },
  );
  assert.equal(unset.status, "blocked");
  assert.equal(unset.blocked.kind, "extra-path-invalid");
  assert.match(unset.note, /no-host-allowlist/);

  const empty = sbtdBdd(
    "t11-extra-empty",
    { intent: "read", extra_paths: [sibling] },
    { cwd: root, allowedExtraRoots: [] },
  );
  assert.equal(empty.status, "blocked");
  assert.match(empty.note, /no-host-allowlist/);

  // Absolute existing dir still denied without allowlist
  const abs = sbtdBdd(
    "t11-extra-abs",
    { intent: "read", extra_paths: [sibling] },
    { cwd: root },
  );
  assert.equal(abs.status, "blocked");
});

test("R3: relative non-.feature target rejected (no source overwrite)", () => {
  const root = fixtureRoot("rel-no-feat");
  mkdirSync(join(root, "src"), { recursive: true });
  writeFileSync(join(root, "src", "index.ts"), "export const x = 1;\n", "utf8");
  const before = readFileSync(join(root, "src", "index.ts"), "utf8");
  const result = sbtdBdd(
    "t11-rel-ts",
    {
      intent: "write",
      target: "src/index.ts",
      content: "Feature: evil\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "invalid-target");
  assert.equal(readFileSync(join(root, "src", "index.ts"), "utf8"), before);
});

test("R4 Q2B: multi-tree does not use found[0]; slug write blocked", () => {
  const root = fixtureRoot("multi-tree");
  // Two disjoint feature trees (simulate plugin fixtures + app) — no features/ at cwd.
  mkdirSync(join(root, "packages", "dsh-sbtd", "features"), { recursive: true });
  mkdirSync(join(root, "apps", "web", "specs"), { recursive: true });
  writeFileSync(
    join(root, "packages", "dsh-sbtd", "features", "plugin.feature"),
    "Feature: plugin\n  Scenario: p\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  writeFileSync(
    join(root, "apps", "web", "specs", "app.feature"),
    "Feature: app\n  Scenario: a\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const conv = detectFeatureConvention(root);
  assert.equal(conv.kind, "ambiguous-feature-trees");
  assert.ok(Array.isArray(conv.ambiguousRoots));
  assert.ok(conv.ambiguousRoots.length >= 2);

  const slug = sbtdBdd(
    "t11-amb-slug",
    {
      intent: "write",
      target: "login",
      content:
        "Feature: 用户登录\n  Scenario: 登录成功\n    Given 用户已注册\n    When 用户提交正确密码\n    Then 进入工作区\n",
    },
    { cwd: root },
  );
  assert.equal(slug.status, "blocked");
  assert.equal(slug.blocked.kind, "invalid-target");
  assert.match(slug.blocked.reason, /ambiguous-feature-root/);
  // Must not land in plugin fixtures via found[0]
  assert.equal(
    existsSync(join(root, "packages", "dsh-sbtd", "features", "login.feature")),
    false,
  );

  // Relative .feature path still works under cwd
  const rel = sbtdBdd(
    "t11-amb-rel",
    {
      intent: "write",
      target: "apps/web/specs/login.feature",
      content:
        "Feature: 用户登录\n  Scenario: 登录成功\n    Given 用户已注册\n    When 用户提交正确密码\n    Then 进入工作区\n",
    },
    { cwd: root },
  );
  assert.equal(rel.status, "done");
  assert.equal(
    existsSync(join(root, "apps", "web", "specs", "login.feature")),
    true,
  );
  assert.equal(
    existsSync(join(root, "packages", "dsh-sbtd", "features", "login.feature")),
    false,
  );
});

test("S1: parseFeatureMeta accepts Chinese Feature/Scenario keywords via read", () => {
  const root = fixtureRoot("zh-kw");
  mkdirSync(join(root, "features"), { recursive: true });
  writeFileSync(
    join(root, "features", "zh.feature"),
    "功能: 结账\n  场景: 成功支付\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const result = sbtdBdd("t11-zh", { intent: "read" }, { cwd: root });
  assert.equal(result.status, "done");
  assert.equal(result.catalog.length, 1);
  assert.equal(result.catalog[0].featureTitle, "结账");
  assert.equal(result.catalog[0].scenarioCount, 1);
});

test("R2: sync with target+content still blocked (not inventory success)", () => {
  const root = fixtureRoot("sync-write");
  mkdirSync(join(root, "features"), { recursive: true });
  const result = sbtdBdd(
    "t11-sync-write",
    {
      intent: "sync",
      target: "login",
      content:
        "Feature: 用户登录\n  Scenario: 登录成功\n    Given 用户已注册\n    When 用户提交正确密码\n    Then 进入工作区\n",
    },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "sync-not-capable");
  assert.equal(result.mutation, "none");
  assert.equal(existsSync(join(root, "features", "login.feature")), false);
});

test("R4 residual: >50 features in one tree must not hide a second tree", () => {
  const root = fixtureRoot("cap-multi");
  const big = join(root, "apps", "web", "features");
  const plugin = join(root, "packages", "dsh-sbtd", "features");
  mkdirSync(big, { recursive: true });
  mkdirSync(plugin, { recursive: true });
  // 55 files in the first tree — old findFeatureFiles(cwd, 50) stopped here.
  for (let i = 0; i < 55; i++) {
    writeFileSync(
      join(big, "f" + String(i).padStart(3, "0") + ".feature"),
      "Feature: big" + i + "\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
      "utf8",
    );
  }
  writeFileSync(
    join(plugin, "plugin.feature"),
    "Feature: plugin\n  Scenario: p\n    Given a\n    When b\n    Then c\n",
    "utf8",
  );
  const parents = findDistinctFeatureParentDirs(root, 2);
  assert.ok(parents.length >= 2, "must see both trees despite >50 files");
  const conv = detectFeatureConvention(root);
  assert.equal(conv.kind, "ambiguous-feature-trees");
  const slug = sbtdBdd(
    "t11-cap-slug",
    {
      intent: "write",
      target: "login",
      content:
        "Feature: 用户登录\n  Scenario: 登录成功\n    Given 用户已注册\n    When 用户提交正确密码\n    Then 进入工作区\n",
    },
    { cwd: root },
  );
  assert.equal(slug.status, "blocked");
  assert.match(slug.blocked.reason, /ambiguous-feature-root/);
  assert.equal(existsSync(join(big, "login.feature")), false);
  assert.equal(existsSync(join(plugin, "login.feature")), false);
});

test("R5 Q1C: dir symlink escape blocked on write", () => {
  const root = fixtureRoot("symlink-cwd");
  const outside = fixtureRoot("symlink-outside");
  mkdirSync(join(root, "features"), { recursive: true });
  // cwd/specs → outside (lexical under cwd, real path escapes)
  symlinkSync(outside, join(root, "specs"));
  const result = sbtdBdd(
    "t11-symlink",
    {
      intent: "write",
      target: "specs/login.feature",
      content:
        "Feature: 逃逸\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "invalid-target");
  assert.equal(existsSync(join(outside, "login.feature")), false);
  assert.equal(existsSync(join(root, "specs", "login.feature")), false);
});

test("R5 residual: slug + features/ dir-symlink must not write outside", () => {
  const root = fixtureRoot("symlink-features-cwd");
  const outside = fixtureRoot("symlink-features-outside");
  mkdirSync(outside, { recursive: true });
  // cwd/features → outside (convention root follows symlink)
  symlinkSync(outside, join(root, "features"));
  const result = sbtdBdd(
    "t11-symlink-features",
    {
      intent: "write",
      target: "login",
      content:
        "Feature: 逃逸\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "invalid-target");
  assert.equal(existsSync(join(outside, "login.feature")), false);
});

test("R5 residual: dangling .feature symlink must not write outside", () => {
  const root = fixtureRoot("symlink-dangling-cwd");
  const outside = fixtureRoot("symlink-dangling-outside");
  mkdirSync(join(root, "features"), { recursive: true });
  mkdirSync(outside, { recursive: true });
  const dangling = join(root, "features", "login.feature");
  symlinkSync(join(outside, "login.feature"), dangling);
  const result = sbtdBdd(
    "t11-symlink-dangling",
    {
      intent: "write",
      target: "features/login.feature",
      content:
        "Feature: 逃逸\n  Scenario: s\n    Given a\n    When b\n    Then c\n",
    },
    { cwd: root },
  );
  assert.equal(result.status, "blocked");
  assert.equal(result.blocked.kind, "invalid-target");
  assert.equal(existsSync(join(outside, "login.feature")), false);
});

test("isConcurrencySafe true only for read", () => {
  const tool = createBddTool();
  assert.equal(tool.isConcurrencySafe({ intent: "read" }), true);
  assert.equal(tool.isConcurrencySafe({ intent: "write" }), false);
  assert.equal(tool.isConcurrencySafe({ intent: "sync" }), false);
});
