import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { PRE_EXECUTE_EVENT } from "../dist/hooks.js";
import { getSession, restore, serialize } from "../dist/state.js";
import { SBTD_SECTION_TEXT } from "../dist/section.js";
import {
  createClarifyTool,
  GRILL_WITH_DOCS_FACT,
  sbtdClarify,
  SBTD_CLARIFY_TOOL_NAME,
} from "../dist/tools/clarify.js";
import { inferRequirements, sbtdPlan } from "../dist/tools/plan.js";
import { SBTD_REVIEW_TOOL_NAME } from "../dist/tools/review.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

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

function planHello(id) {
  return sbtdPlan(id, { task_summary: "hello world clarify" });
}

test("apply 注册 sbtd_plan、sbtd_review、sbtd_clarify、sbtd_spec 与 sbtd_tickets", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 6);
  assert.equal(tools[0].name, "sbtd_plan");
  assert.equal(tools[1].name, SBTD_REVIEW_TOOL_NAME);
  assert.equal(tools[2].name, SBTD_CLARIFY_TOOL_NAME);
  assert.equal(tools[3].name, "sbtd_spec");
  assert.equal(tools[4].name, "sbtd_tickets");
});

test("首次调用省略 mode 抛错；绑定 docs 后省略继承", () => {
  const id = "t6-bind-docs";
  assert.throws(
    () => sbtdClarify(id, { question: "Q?" }),
    /first call requires mode docs\|generic/,
  );
  const first = sbtdClarify(id, { mode: "docs", question: "Need repo facts?" });
  assert.equal(first.mode, "docs");
  assert.equal(first.clarifyStatus, "partial");
  assert.equal(first.currentQuestion, "Need repo facts?");
  const inherited = sbtdClarify(id, { question: "Next?" });
  assert.equal(inherited.mode, "docs");
  assert.equal(getSession(id).clarifyMode, "docs");
});

test("已绑定 docs 时 generic 抛错直至显式 reset", () => {
  const id = "t6-switch-reset";
  sbtdClarify(id, { mode: "docs", question: "Q1" });
  assert.throws(
    () => sbtdClarify(id, { mode: "generic", question: "Q2" }),
    /bound to docs; switch throws until Interview Reset/,
  );
  const reset = sbtdClarify(id, { reset: true });
  assert.equal(reset.mode, null);
  assert.equal(getSession(id).clarifyMode, undefined);
  const rebound = sbtdClarify(id, { mode: "generic", question: "grill-me?" });
  assert.equal(rebound.mode, "generic");
});

test("compaction restore 保留 mode 与 clarifyStatus，不是 Reset", () => {
  const id = "t6-compact-src";
  sbtdClarify(id, { mode: "docs", question: "Keep?" });
  const snapshot = serialize(id);
  assert.equal(snapshot.clarifyMode, "docs");
  assert.equal(snapshot.clarifyStatus, "partial");
  restore("t6-compact-dst", snapshot);
  const dst = getSession("t6-compact-dst");
  assert.equal(dst.clarifyMode, "docs");
  assert.equal(dst.clarifyStatus, "partial");
  const continued = sbtdClarify("t6-compact-dst", { question: "Still docs?" });
  assert.equal(continued.mode, "docs");
});

test("docs Complete 经 haystack 提升 ddd 并调用共享 mapper", () => {
  const id = "t6-docs-complete";
  planHello(id);
  assert.equal(getSession(id).plan.gates.ddd.requirement, "on-demand");
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  const done = sbtdClarify(id, {
    frontier_empty: true,
    user_confirmed: true,
  });
  assert.equal(done.clarifyStatus, "complete");
  assert.equal(done.currentQuestion, null);
  assert.equal(done.ddd.requirement, "required");
  assert.equal(done.ddd.fact, GRILL_WITH_DOCS_FACT);
  assert.equal(done.ddd.reviewStatus, "blocked");
  assert.equal(getSession(id).plan.gates.ddd.requirement, "required");
  assert.equal(getSession(id).plan.gates.ddd.reviewStatus, "blocked");
  assert.equal(getSession(id).clarifyCompleteTaskId, getSession(id).plan.taskId);
  const inferred = inferRequirements("hello world clarify", [
    GRILL_WITH_DOCS_FACT,
  ]);
  assert.equal(inferred.ddd.requirement, "required");
});


test("Partial 不调用 sbtdReview", () => {
  const id = "t6-partial-no-review";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Only one?" });
  assert.equal(getSession(id).plan.gates.ddd.reviewStatus, undefined);
});

test("generic Complete 不自动要求 DDD 也不写 grill-with-docs 事实", () => {
  const id = "t6-generic-complete";
  planHello(id);
  sbtdClarify(id, { mode: "generic", question: "Trade-off?" });
  const done = sbtdClarify(id, {
    frontier_empty: true,
    user_confirmed: true,
  });
  assert.equal(done.clarifyStatus, "complete");
  assert.equal(done.blocked, undefined);
  assert.equal(getSession(id).plan.gates.ddd.requirement, "on-demand");
  assert.equal(getSession(id).plan.gates.ddd.fact, undefined);
  assert.equal(getSession(id).plan.gates.ddd.reviewStatus, undefined);
  assert.equal(
    inferRequirements(getSession(id).plan.summary).ddd.requirement,
    "on-demand",
  );
});

test("返回值是单个 Current Question", () => {
  const id = "t6-one-question";
  const result = sbtdClarify(id, {
    mode: "docs",
    question: "What is the bounded context?",
  });
  assert.equal(result.currentQuestion, "What is the bounded context?");
  assert.equal(Array.isArray(result.currentQuestion), false);
  const tool = createClarifyTool();
  assert.equal(tool.parameters.properties.question.type, "string");
  assert.equal(tool.parameters.properties.questions, undefined);
});

test("空 frontier 未确认保持 Partial；只读 manuals 不是 Complete", () => {
  const id = "t6-dual-gate";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  const emptyOnly = sbtdClarify(id, { frontier_empty: true });
  assert.equal(emptyOnly.clarifyStatus, "partial");
  const manuals = sbtdClarify(id, { load_manuals: true });
  assert.equal(manuals.clarifyStatus, "partial");
  assert.match(manuals.manuals, /grilling/);
  assert.match(manuals.manuals, /grill-with-docs/);
  assert.equal(getSession(id).clarifyStatus, "partial");
});

test("Partial 无计划成功；Complete 无计划抛错", () => {
  const id = "t6-no-plan";
  const partial = sbtdClarify(id, { mode: "generic", question: "Goal?" });
  assert.equal(partial.clarifyStatus, "partial");
  assert.equal(getSession(id).plan, undefined);
  assert.throws(
    () =>
      sbtdClarify(id, {
        frontier_empty: true,
        user_confirmed: true,
      }),
    /尚未 sbtd_plan，请先调用 sbtd_plan/,
  );
});

test("Complete 且 DDD 未 confirmed 一次性 blocked，再调用不是恢复路径", () => {
  const id = "t6-blocked-terminal";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  const done = sbtdClarify(id, {
    frontier_empty: true,
    user_confirmed: true,
  });
  assert.equal(done.clarifyStatus, "complete");
  assert.equal(done.blocked.kind, "ddd-unconfirmed");
  assert.equal(done.blocked.resume, "not-clarify");
  assert.equal(done.blocked.suggestPrd, false);
  assert.equal(done.blocked.suggestImplement, false);
  assert.throws(
    () => sbtdClarify(id, { question: "resume?" }),
    /Clarify Complete is terminal/,
  );
});

test("docs Complete 已 confirmed 则不 blocked", () => {
  const id = "t6-docs-confirmed";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  const done = sbtdClarify(id, {
    frontier_empty: true,
    user_confirmed: true,
    ddd_status: "confirmed",
  });
  assert.equal(done.clarifyStatus, "complete");
  assert.equal(done.blocked, undefined);
  assert.equal(done.ddd.reviewStatus, "confirmed");
  assert.equal(getSession(id).plan.gates.ddd.state, "passed");
});

test("docs Complete 后 required 未通过的 ddd 仍拦生产 write", async () => {
  const id = "t6-t3-ddd-deny";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
  const { hooks } = loadPlugin();
  const denied = await hooks.get(PRE_EXECUTE_EVENT)(writeSrc(id), nextAllow);
  assert.equal(denied.kind, "deny");
  assert.match(denied.reason, /sbtd_review kind=ddd/);
});

test("docs Complete 后同摘要省略 grill facts 时 ddd 保持 required 且 T3 仍 deny", async () => {
  const id = "t6-fu3-sticky-omit";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
  assert.equal(getSession(id).clarifyStatus, "complete");
  assert.equal(getSession(id).plan.gates.ddd.requirement, "required");
  assert.equal(getSession(id).plan.gates.ddd.state, "blocked");

  const omitted = sbtdPlan(id, { task_summary: "hello world clarify" });
  assert.equal(omitted.plan.gates.ddd.requirement, "required");
  assert.equal(omitted.plan.gates.ddd.state, "blocked");
  assert.equal(omitted.plan.gates.ddd.reviewStatus, "blocked");
  assert.equal(omitted.plan.gates.ddd.fact, GRILL_WITH_DOCS_FACT);

  const { hooks } = loadPlugin();
  const denied = await hooks.get(PRE_EXECUTE_EVENT)(writeSrc(id), nextAllow);
  assert.equal(denied.kind, "deny");
  assert.match(denied.reason, /sbtd_review kind=ddd/);
});

test("Interview Reset 后同摘要省略 facts 允许 demote Forced Docs DDD", () => {
  const id = "t6-fu3-reset-demote";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
  sbtdClarify(id, { reset: true });
  assert.equal(getSession(id).clarifyStatus, undefined);
  assert.equal(getSession(id).clarifyCompleteTaskId, undefined);


  const omitted = sbtdPlan(id, { task_summary: "hello world clarify" });
  assert.equal(omitted.plan.gates.ddd.requirement, "on-demand");
  assert.equal(omitted.plan.gates.ddd.state, "not-required");
});


test("generic Complete 不粘滞独立 required ddd，省略 facts 可 demote", () => {
  const id = "t6-fu3-generic-no-sticky";
  const summary = "hello world generic no sticky";
  sbtdPlan(id, {
    task_summary: summary,
    facts: [GRILL_WITH_DOCS_FACT],
  });
  sbtdClarify(id, { mode: "generic", question: "Trade-off?" });
  sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
  assert.equal(getSession(id).clarifyStatus, "complete");
  assert.equal(getSession(id).clarifyMode, "generic");
  assert.equal(getSession(id).plan.gates.ddd.requirement, "required");

  const omitted = sbtdPlan(id, { task_summary: summary });
  assert.equal(omitted.plan.gates.ddd.requirement, "on-demand");
  assert.equal(omitted.plan.gates.ddd.state, "not-required");
});

test("docs Complete 绑定 taskId；compaction restore 匹配；Reset 清除", () => {
  const id = "t6-complete-taskid-bind";
  const planned = planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
  assert.equal(getSession(id).clarifyCompleteTaskId, planned.plan.taskId);
  const snapshot = serialize(id);
  assert.equal(snapshot.clarifyCompleteTaskId, planned.plan.taskId);
  restore("t6-complete-taskid-dst", snapshot);
  assert.equal(
    getSession("t6-complete-taskid-dst").clarifyCompleteTaskId,
    planned.plan.taskId,
  );
  restore("t6-complete-taskid-empty", {});
  assert.equal(
    getSession("t6-complete-taskid-empty").clarifyCompleteTaskId,
    undefined,
  );
  sbtdClarify(id, { reset: true });
  assert.equal(getSession(id).clarifyCompleteTaskId, undefined);
});

test("他任务 docs Complete 后新任务省略 grill 可 demote 且 T3 不因陈旧 Complete deny", async () => {
  const id = "t6-fu3-stale-complete-cross-task";
  planHello(id);
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
  const summaryB = "task beta grill then omit t6";
  sbtdPlan(id, {
    task_summary: summaryB,
    facts: [GRILL_WITH_DOCS_FACT],
  });
  const omitted = sbtdPlan(id, { task_summary: summaryB });
  assert.equal(omitted.plan.gates.ddd.requirement, "on-demand");
  assert.equal(omitted.plan.gates.ddd.state, "not-required");
  const { hooks } = loadPlugin();
  const allowed = await hooks.get(PRE_EXECUTE_EVENT)(writeSrc(id), nextAllow);
  assert.equal(allowed.kind, "allow");
});



test("createClarifyTool execute 复用 sessionIdFromExec", async () => {
  const tool = createClarifyTool();
  assert.equal(tool.name, SBTD_CLARIFY_TOOL_NAME);
  assert.equal(tool.parameters.type, "object");
  assert.equal(tool.isConcurrencySafe({}), false);
  const result = await tool.execute(
    { mode: "docs", question: "from exec" },
    { agent: { id: "t6-exec-id" } },
  );
  assert.equal(result.mode, "docs");
  assert.equal(getSession("t6-exec-id").clarifyMode, "docs");
});

test("section 将 Forced DDD 收窄为 docs Complete", () => {
  assert.match(SBTD_SECTION_TEXT, /仅 docs 模式 Complete 后必须有 DDD 复审通过态/);
  assert.doesNotMatch(
    SBTD_SECTION_TEXT,
    /澄清走 sbtd_clarify，完整澄清后必须有 DDD 复审通过态/,
  );
});

test("README 提到 sbtd_clarify 并保持钉版本", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /sbtd_clarify/);
  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /0\.1\.0-rc\.1/);
});

test("hydrate 空 snapshot 清除 clarify 绑定", () => {
  const id = "t6-hydrate";
  sbtdClarify(id, { mode: "docs", question: "Q?" });
  restore(id, {});
  const after = getSession(id);
  assert.equal(after.clarifyMode, undefined);
  assert.equal(after.clarifyStatus, undefined);
  assert.equal(after.clarifyCompleteTaskId, undefined);

});
