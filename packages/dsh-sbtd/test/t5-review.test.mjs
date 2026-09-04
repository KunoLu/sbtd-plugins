import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { PRE_EXECUTE_EVENT } from "../dist/hooks.js";
import { getSession, serialize } from "../dist/state.js";
import { sbtdPlan } from "../dist/tools/plan.js";
import {
  createReviewTool,
  loadReviewManual,
  REVIEW_KINDS,
  REVIEW_TITLES,
  sbtdReview,
  SBTD_REVIEW_TOOL_NAME,
} from "../dist/tools/review.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

const PASS_TUPLES = [
  [
    "legacy",
    "characterized",
    "fix existing behavior bug",
    "Legacy Change Safety Review",
  ],
  [
    "refactor",
    "proceed",
    "edit existing production module",
    "Refactoring Review",
  ],
  ["ddd", "confirmed", "completed grill-with-docs", "DDD Boundary Review"],
  ["ddia", "confirmed", "persist shared data", "DDIA Data Design Review"],
  ["release", "ready", "deploy production path job", "Release Readiness Review"],
];

function loadPlugin() {
  const tools = [];
  const hooks = new Map();
  apply({
    systemPrompt: {
      section() {},
    },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on(event, handler) {
      hooks.set(event, handler);
    },
  });
  return { tools, hooks };
}

async function nextAllow() {
  return { kind: "allow" };
}

function writeSrc(sessionId, file = "src/foo.ts") {
  return {
    name: "write",
    arguments: { path: file },
    agent: { id: sessionId },
  };
}

function renderedText(tool, value) {
  return tool.output
    .render({}, value)
    .map((part) => part.text)
    .join("\n");
}

test("apply 注册恰好 sbtd_plan 与 sbtd_review", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 2);
  assert.equal(tools[0].name, "sbtd_plan");
  assert.equal(tools[1].name, SBTD_REVIEW_TOOL_NAME);
});

test("五个规范 kind 成功且拒绝别名", () => {
  assert.deepEqual([...REVIEW_KINDS], [
    "legacy",
    "refactor",
    "ddd",
    "ddia",
    "release",
  ]);
  for (const [kind, status, summary] of PASS_TUPLES) {
    const id = `t5-kind-ok-${kind}`;
    sbtdPlan(id, { task_summary: summary });
    const result = sbtdReview(id, { kind, status });
    assert.equal(result.kind, kind);
    assert.equal(result.reviewStatus, status);
  }

  const id = "t5-kind";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  for (const kind of [
    "book-legacy-change-safety",
    "legacy-change-safety",
    "LEGACY",
    "grill-with-docs",
    "to-spec",
    "trellis-workflow",
  ]) {
    assert.throws(
      () => sbtdReview(id, { kind, status: "characterized" }),
      /kind must be one of/,
    );
  }
  assert.equal(getSession(id).plan.gates.legacy.state, "planned");
  assert.equal(getSession(id).plan.gates.legacy.reviewStatus, undefined);
});

test("无 plan 指向 sbtd_plan 且不 fake pass", () => {
  const id = "t5-no-plan";
  assert.throws(
    () => sbtdReview(id, { kind: "legacy", status: "characterized" }),
    /sbtd_plan/,
  );
  assert.equal(getSession(id).plan, undefined);
});

test("各 kind 通过态元组映射为 passed 并存储 reviewStatus", () => {
  for (const [kind, status, summary, title] of PASS_TUPLES) {
    const id = `t5-pass-${kind}`;
    sbtdPlan(id, { task_summary: summary });
    const result = sbtdReview(id, {
      kind,
      status,
      conclusions: `${kind} ok`,
    });
    assert.equal(result.title, title);
    assert.equal(result.reviewStatus, status);
    assert.equal(result.state, "passed");
    assert.equal(result.requirement, "required");
    assert.equal(result.conclusions, `${kind} ok`);
    assert.match(result.markdown, new RegExp(result.title));
    assert.equal(getSession(id).plan.gates[kind].state, "passed");
    assert.equal(getSession(id).plan.gates[kind].reviewStatus, status);
    assert.equal(getSession(id).plan.gates[kind].requirement, "required");
  }
});

test("五个规定标题", () => {
  assert.deepEqual(REVIEW_TITLES, {
    legacy: "Legacy Change Safety Review",
    refactor: "Refactoring Review",
    ddd: "DDD Boundary Review",
    ddia: "DDIA Data Design Review",
    release: "Release Readiness Review",
  });
  for (const [kind, status, summary, title] of PASS_TUPLES) {
    const id = `t5-title-${kind}`;
    sbtdPlan(id, { task_summary: summary });
    assert.equal(sbtdReview(id, { kind, status }).title, title);
  }
});

test("错误 kind 的 status 被拒绝", () => {
  const id = "t5-wrong-status";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  const wrong = [
    ["legacy", "proceed"],
    ["refactor", "characterized"],
    ["ddd", "ready"],
    ["ddia", "characterized"],
    ["release", "confirmed"],
  ];
  for (const [kind, status] of wrong) {
    assert.throws(() => sbtdReview(id, { kind, status }), /status/);
  }
  assert.equal(getSession(id).plan.gates.legacy.state, "planned");
  assert.equal(getSession(id).plan.gates.legacy.reviewStatus, undefined);
});

test("空白填充的 characterized 不推进 gate", () => {
  const id = "t5-padded";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  assert.throws(
    () => sbtdReview(id, { kind: "legacy", status: " characterized" }),
    /status/,
  );
  assert.equal(getSession(id).plan.gates.legacy.state, "planned");
  assert.equal(getSession(id).plan.gates.legacy.reviewStatus, undefined);
});

test("needs-* seam-required refactor-first 保持 running；blocked 为 blocked", () => {
  const running = [
    ["legacy", "needs-safety-net", "fix existing behavior bug"],
    ["legacy", "seam-required", "fix existing behavior bug"],
    ["refactor", "refactor-first", "edit existing production module"],
    ["ddd", "needs-clarification", "completed grill-with-docs"],
    ["ddia", "needs-design-change", "persist shared data"],
    ["release", "needs-mitigation", "deploy production path job"],
  ];
  for (const [kind, status, summary] of running) {
    const id = `t5-run-${kind}-${status}`;
    sbtdPlan(id, { task_summary: summary });
    const result = sbtdReview(id, { kind, status });
    assert.equal(result.state, "running");
    assert.equal(getSession(id).plan.gates[kind].state, "running");
    assert.equal(getSession(id).plan.gates[kind].reviewStatus, status);
    assert.equal(getSession(id).plan.gates[kind].requirement, "required");
  }

  const id = "t5-blocked";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  const blocked = sbtdReview(id, { kind: "legacy", status: "blocked" });
  assert.equal(blocked.state, "blocked");
  assert.equal(getSession(id).plan.gates.legacy.state, "blocked");
});

test("非法 status 不推进 gate", () => {
  const id = "t5-no-fake";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  assert.throws(
    () => sbtdReview(id, { kind: "legacy", status: "passed" }),
    /status/,
  );
  assert.equal(getSession(id).plan.gates.legacy.state, "planned");
  assert.equal(getSession(id).plan.gates.legacy.reviewStatus, undefined);
});

test("on-demand review 不提升 requirement", () => {
  const id = "t5-ondemand";
  sbtdPlan(id, { task_summary: "add a hello world file" });
  assert.equal(getSession(id).plan.gates.legacy.requirement, "on-demand");
  const result = sbtdReview(id, {
    kind: "legacy",
    status: "characterized",
    conclusions: "optional",
  });
  assert.equal(result.requirement, "on-demand");
  assert.equal(result.state, "passed");
  assert.equal(getSession(id).plan.gates.legacy.requirement, "on-demand");
  assert.equal(getSession(id).plan.gates.legacy.reviewStatus, "characterized");
});

test("on-demand ddia confirmed 提升 required 重置 planned 并拦 schema.sql", async () => {
  const id = "t5-promote-ddia";
  const summary = "hello world plan";
  sbtdPlan(id, { task_summary: summary });
  assert.equal(getSession(id).plan.gates.ddia.requirement, "on-demand");
  sbtdReview(id, { kind: "ddia", status: "confirmed", conclusions: "" });
  assert.equal(getSession(id).plan.gates.ddia.state, "passed");
  assert.equal(getSession(id).plan.gates.ddia.requirement, "on-demand");

  const promoted = sbtdPlan(id, {
    task_summary: summary,
    facts: ["persist"],
  });
  assert.equal(promoted.plan.gates.ddia.requirement, "required");
  assert.equal(promoted.plan.gates.ddia.state, "planned");
  assert.notEqual(promoted.plan.gates.ddia.state, "passed");
  assert.equal(promoted.plan.gates.ddia.reviewStatus, undefined);
  assert.equal(
    promoted.plan.gates.ddia.fact,
    "promoted from on-demand; reset inherited pass",
  );

  const { hooks } = loadPlugin();
  const data = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "str_replace_editor",
      arguments: { filePath: "src/schema.sql" },
      agent: { id },
    },
    nextAllow,
  );
  assert.equal(data.kind, "deny");
  assert.match(data.reason, /sbtd_review kind=ddia/);
});

test("required+passed ddia persist 再 plan schema 重置并拦 schema.sql", async () => {
  const id = "t5-fact-change-ddia";
  const summary = "data path after first pass";
  sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  const live = getSession(id);
  assert.equal(live.plan.gates.ddia.requirement, "required");
  assert.equal(live.plan.gates.ddia.fact, "persistence");
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";

  const reset = sbtdPlan(id, {
    task_summary: summary,
    facts: ["schema"],
  });
  assert.equal(reset.plan.gates.ddia.requirement, "required");
  assert.equal(reset.plan.gates.ddia.state, "planned");
  assert.notEqual(reset.plan.gates.ddia.state, "passed");
  assert.equal(reset.plan.gates.ddia.reviewStatus, undefined);
  assert.match(reset.plan.gates.ddia.fact ?? "", /trigger fact changed/);
  assert.match(reset.plan.gates.ddia.fact ?? "", /persistence/);
  assert.match(reset.plan.gates.ddia.fact ?? "", /database\/schema/);

  const { hooks } = loadPlugin();
  const data = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "str_replace_editor",
      arguments: { filePath: "src/schema.sql" },
      agent: { id },
    },
    nextAllow,
  );
  assert.equal(data.kind, "deny");
  assert.match(data.reason, /sbtd_review kind=ddia/);
});

test("独特结论只在返回值不落盘", () => {
  const id = "t5-conclusion";
  const unique = "CONCLUSION-ZX9Q-NOT-PERSIST";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  const result = sbtdReview(id, {
    kind: "legacy",
    status: "characterized",
    conclusions: unique,
  });
  assert.equal(result.conclusions, unique);
  assert.match(result.markdown, new RegExp(unique));
  assert.doesNotMatch(JSON.stringify(getSession(id)), /CONCLUSION-ZX9Q-NOT-PERSIST/);
  assert.doesNotMatch(JSON.stringify(serialize(id)), /CONCLUSION-ZX9Q-NOT-PERSIST/);
  const manuals = readFileSync(
    join(pkgRoot, "manuals/book-legacy-change-safety/SKILL.md"),
    "utf8",
  );
  assert.doesNotMatch(manuals, /CONCLUSION-ZX9Q-NOT-PERSIST/);
});

test("可观察地加载对应 manual，render 含已加载正文", () => {
  const id = "t5-manual";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  const result = sbtdReview(id, {
    kind: "legacy",
    status: "characterized",
  });
  const loaded = loadReviewManual("legacy");
  assert.equal(result.manual, loaded);
  assert.match(result.manual, /name: book-legacy-change-safety/);
  assert.match(loadReviewManual("refactor"), /name: book-refactoring-pass/);
  assert.match(loadReviewManual("ddd"), /name: book-ddd-distilled-modeling/);
  assert.match(loadReviewManual("ddia"), /name: book-ddia-data-design/);
  assert.match(loadReviewManual("release"), /name: book-release-readiness/);

  const tool = createReviewTool();
  const text = renderedText(tool, result);
  assert.ok(text.includes(loaded));
  assert.match(text, /name: book-legacy-change-safety/);

  const src = readFileSync(join(pkgRoot, "src/tools/review.ts"), "utf8");
  assert.doesNotMatch(
    src,
    /grill-with-docs|grill-me|to-spec|to-tickets|trellis-workflow|domain-modeling/,
  );
  assert.doesNotMatch(src, /writeFile|writeFileSync|AGENTS\.md/);
});

test("legacy characterized 后生产 write 放行", async () => {
  const id = "t5-legacy-pass";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  sbtdReview(id, { kind: "legacy", status: "characterized" });
  const { hooks } = loadPlugin();
  let nextCalled = false;
  const result = await hooks.get(PRE_EXECUTE_EVENT)(writeSrc(id), async () => {
    nextCalled = true;
    return { kind: "allow" };
  });
  assert.equal(nextCalled, true);
  assert.equal(result.kind, "allow");
});

test("required 未通过的 refactor 拦生产 write", async () => {
  const id = "t5-refactor-write";
  sbtdPlan(id, {
    task_summary: "change existing production after completed grill-with-docs",
    facts: [
      "existing behavior",
      "existing production",
      "completed grill-with-docs",
    ],
  });
  sbtdReview(id, { kind: "legacy", status: "characterized" });
  const { hooks } = loadPlugin();
  const refactorDeny = await hooks.get(PRE_EXECUTE_EVENT)(
    writeSrc(id),
    nextAllow,
  );
  assert.equal(refactorDeny.kind, "deny");
  assert.match(refactorDeny.reason, /sbtd_review kind=refactor/);
});

test("更早门禁通过后 required 未通过的 ddd 仍拦 write", async () => {
  const id = "t5-ddd-write";
  sbtdPlan(id, {
    task_summary: "change existing production after completed grill-with-docs",
    facts: [
      "existing behavior",
      "existing production",
      "completed grill-with-docs",
    ],
  });
  sbtdReview(id, { kind: "legacy", status: "characterized" });
  sbtdReview(id, { kind: "refactor", status: "proceed" });
  const { hooks } = loadPlugin();
  const dddDeny = await hooks.get(PRE_EXECUTE_EVENT)(writeSrc(id), nextAllow);
  assert.equal(dddDeny.kind, "deny");
  assert.match(dddDeny.reason, /sbtd_review kind=ddd/);
});

test("required 未通过的 ddia 拦数据路径", async () => {
  const ddiaId = "t5-ddia";
  sbtdPlan(ddiaId, { task_summary: "persist schema cache" });
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  let nextCalled = false;
  const code = await pre(writeSrc(ddiaId), async () => {
    nextCalled = true;
    return { kind: "allow" };
  });
  assert.equal(nextCalled, true);
  assert.equal(code.kind, "allow");
  const data = await pre(
    {
      name: "str_replace_editor",
      arguments: { filePath: "src/schema.sql" },
      agent: { id: ddiaId },
    },
    nextAllow,
  );
  assert.equal(data.kind, "deny");
  assert.match(data.reason, /sbtd_review kind=ddia/);
});

test("required 未通过的 release 拦 publish-family bash 不拦普通编辑", async () => {
  const relId = "t5-release";
  sbtdPlan(relId, { task_summary: "deploy production path job" });
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  let editNext = false;
  const edit = await pre(writeSrc(relId), async () => {
    editNext = true;
    return { kind: "allow" };
  });
  assert.equal(editNext, true);
  assert.equal(edit.kind, "allow");
  const publish = await pre(
    {
      name: "bash",
      arguments: { command: "npm publish" },
      agent: { id: relId },
    },
    nextAllow,
  );
  assert.equal(publish.kind, "deny");
  assert.match(publish.reason, /sbtd_review kind=release/);
});

test("createReviewTool schema 与 execute 复用 sessionIdFromExec", async () => {
  const tool = createReviewTool();
  assert.equal(tool.name, SBTD_REVIEW_TOOL_NAME);
  assert.equal(tool.parameters.type, "object");
  assert.deepEqual(tool.parameters.required, ["kind", "status"]);
  assert.deepEqual(tool.parameters.properties.kind.enum, [...REVIEW_KINDS]);
  assert.equal(tool.output.schema.additionalProperties, false);
  assert.equal(
    tool.isConcurrencySafe({ kind: "legacy", status: "characterized" }),
    false,
  );

  sbtdPlan("t5-tool-sess", { task_summary: "fix existing behavior bug" });
  const result = await tool.execute(
    { kind: "legacy", status: "characterized", conclusions: "via tool" },
    { agent: { id: "t5-tool-sess" } },
  );
  assert.equal(result.state, "passed");
  assert.equal(
    getSession("t5-tool-sess").plan.gates.legacy.reviewStatus,
    "characterized",
  );
  const text = renderedText(tool, result);
  assert.ok(text.includes(result.manual));
  assert.ok(text.includes(loadReviewManual("legacy")));
});

test("README 提到 sbtd_review 并保持钉版本", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /sbtd_review/);
  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
  assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
  assert.doesNotMatch(readme, /plugin loaded \(T0 stub\)/);
  assert.match(readme, /legacy/);
  assert.match(readme, /refactor/);
  assert.match(readme, /ddd/);
  assert.match(readme, /ddia/);
  assert.match(readme, /release/);
  assert.match(readme, /characterized/);
  assert.match(readme, /proceed/);
  assert.match(readme, /confirmed/);
  assert.match(readme, /ready/);
});
