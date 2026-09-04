import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { getSession, restore } from "../dist/state.js";
import {
  createPlanTool,
  GATE_KINDS,
  inferRequirements,
  sbtdPlan,
  sessionIdFromExec,
  SBTD_PLAN_TOOL_NAME,
  taskIdFromSummary,
} from "../dist/tools/plan.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

test("sessionId 来自 exec.agent.id，缺省为 default", () => {
  assert.equal(sessionIdFromExec({ agent: { id: "sess-a" } }), "sess-a");
  assert.equal(sessionIdFromExec({}), "default");
  assert.equal(sessionIdFromExec(undefined), "default");
});

test("客观谓词：命中 required+planned，未命中 on-demand+not-required", () => {
  const none = inferRequirements("add a hello world file");
  for (const kind of GATE_KINDS) {
    assert.equal(none[kind].requirement, "on-demand");
    assert.equal(none[kind].state, "not-required");
  }

  const hit = inferRequirements("completed grill-with-docs", [
    "修既有行为 bug",
    "将修改既有生产代码",
    "持久化 session 状态",
    "生产路径 deploy",
  ]);
  assert.equal(hit.ddd.requirement, "required");
  assert.equal(hit.ddd.state, "planned");
  assert.equal(hit.legacy.requirement, "required");
  assert.equal(hit.refactor.requirement, "required");
  assert.equal(hit.ddia.requirement, "required");
  assert.equal(hit.release.requirement, "required");

  const subjective = inferRequirements("this feels high risk");
  for (const kind of GATE_KINDS) {
    assert.equal(subjective[kind].requirement, "on-demand");
  }

  const bareDdd = inferRequirements("model DDD ubiquitous language");
  assert.equal(bareDdd.ddd.requirement, "on-demand");
  assert.equal(bareDdd.ddd.state, "not-required");

  const bareRefactor = inferRequirements("please refactor the helpers");
  assert.equal(bareRefactor.refactor.requirement, "on-demand");
  const existingProd = inferRequirements("edit existing production module");
  assert.equal(existingProd.refactor.requirement, "required");
  const docsOnly = inferRequirements("修改既有测试 fixtures");
  assert.equal(docsOnly.refactor.requirement, "on-demand");
  const bugUi = inferRequirements("add bug report UI");
  assert.equal(bugUi.legacy.requirement, "on-demand");
  const existingBug = inferRequirements("fix existing behavior bug");
  assert.equal(existingBug.legacy.requirement, "required");
  const debugFix = inferRequirements("add debug fixture");
  assert.equal(debugFix.legacy.requirement, "on-demand");
  const debugCn = inferRequirements("修改 debug 输出");
  assert.equal(debugCn.legacy.requirement, "on-demand");
});

test("sbtd_plan 写入隔离 session 且五项 gate 齐全", () => {
  const result = sbtdPlan("plan-sess-1", {
    task_summary: "fix existing behavior bug in existing production code",
  });
  const session = getSession("plan-sess-1");
  assert.ok(session.plan);
  assert.equal(session.plan, result.plan);
  assert.equal(getSession("plan-sess-2").plan, undefined);
  for (const kind of GATE_KINDS) {
    assert.ok(session.plan.gates[kind].requirement);
    assert.ok(session.plan.gates[kind].state);
  }
  assert.equal(session.plan.gates.legacy.requirement, "required");
  assert.equal(session.plan.gates.refactor.requirement, "required");
  assert.match(result.markdown, /Book Gate Plan/);
  assert.match(result.markdown, /legacy/);
  assert.equal(result.plan.taskId, taskIdFromSummary(result.plan.summary));
});

test("同一目标重复调用保留 passed，触发消失则写明原因", () => {
  const id = "plan-sess-update";
  const summary = "implement feature x";
  const first = sbtdPlan(id, {
    task_summary: summary,
    facts: ["persist shared data", "fix existing behavior bug"],
  });
  assert.equal(first.plan.gates.ddia.requirement, "required");
  assert.equal(first.plan.gates.legacy.requirement, "required");

  const live = getSession(id);
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";

  const second = sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  assert.equal(second.plan.gates.ddia.state, "passed");
  assert.equal(second.plan.gates.ddia.reviewStatus, "confirmed");
  assert.equal(second.plan.gates.legacy.requirement, "on-demand");
  assert.equal(second.plan.gates.legacy.state, "not-required");

  const third = sbtdPlan(id, {
    task_summary: summary,
    facts: ["this feels high risk"],
  });
  assert.equal(third.plan.gates.ddia.state, "not-required");
  assert.equal(third.plan.gates.ddia.fact, undefined);
  assert.match(third.markdown, /disappeared/);
});

test("mergeGate 仅在先前已是 required 时保留 passed", () => {
  const id = "plan-merge-keep-required-pass";
  const summary = "keep required pass";
  sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  const live = getSession(id);
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";

  const kept = sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  assert.equal(kept.plan.gates.ddia.requirement, "required");
  assert.equal(kept.plan.gates.ddia.state, "passed");
  assert.equal(kept.plan.gates.ddia.reviewStatus, "confirmed");
});

test("required+passed ddia persist 后 schema 重置 planned", () => {
  const id = "plan-merge-fact-change-reset";
  const summary = "keep required pass until fact changes";
  sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  const live = getSession(id);
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";
  assert.equal(live.plan.gates.ddia.fact, "persistence");

  const reset = sbtdPlan(id, { task_summary: summary, facts: ["schema"] });
  assert.equal(reset.plan.gates.ddia.requirement, "required");
  assert.equal(reset.plan.gates.ddia.state, "planned");
  assert.equal(reset.plan.gates.ddia.reviewStatus, undefined);
  assert.equal(reset.plan.gates.ddia.fact, "database/schema");
  assert.match(reset.markdown, /trigger fact changed/);
  assert.match(reset.markdown, /persistence/);
  assert.match(reset.markdown, /database\/schema/);
});

test("A→B reviewed →C 必须再次重置 planned", () => {
  const id = "plan-merge-abc-fact-chain";
  const summary = "abc catalog fact chain";
  sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  const live = getSession(id);
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";
  assert.equal(live.plan.gates.ddia.fact, "persistence");

  const toB = sbtdPlan(id, { task_summary: summary, facts: ["schema"] });
  assert.equal(toB.plan.gates.ddia.state, "planned");
  assert.equal(toB.plan.gates.ddia.fact, "database/schema");

  // simulate sbtd_review pass without overwriting catalog fact
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";
  assert.equal(live.plan.gates.ddia.fact, "database/schema");

  const toC = sbtdPlan(id, { task_summary: summary, facts: ["cache"] });
  assert.equal(toC.plan.gates.ddia.requirement, "required");
  assert.equal(toC.plan.gates.ddia.state, "planned");
  assert.notEqual(toC.plan.gates.ddia.state, "passed");
  assert.equal(toC.plan.gates.ddia.reviewStatus, undefined);
  assert.equal(toC.plan.gates.ddia.fact, "cache");
  assert.match(toC.markdown, /trigger fact changed/);
  assert.match(toC.markdown, /database\/schema/);
  assert.match(toC.markdown, /cache/);
});

test("同一 B 重置后再 plan 同触发不循环重置", () => {
  const id = "plan-merge-same-b-no-loop";
  const summary = "same B after reset stays planned";
  sbtdPlan(id, { task_summary: summary, facts: ["persist"] });
  const live = getSession(id);
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";

  const reset = sbtdPlan(id, { task_summary: summary, facts: ["schema"] });
  assert.equal(reset.plan.gates.ddia.state, "planned");
  assert.equal(reset.plan.gates.ddia.fact, "database/schema");

  const again = sbtdPlan(id, { task_summary: summary, facts: ["schema"] });
  assert.equal(again.plan.gates.ddia.state, "planned");
  assert.equal(again.plan.gates.ddia.fact, "database/schema");
});

test("mergeGate 将 on-demand passed 提升 required 重置为 planned", () => {
  const id = "plan-merge-promote-ondemand";
  const summary = "hello world plan";
  sbtdPlan(id, { task_summary: summary });
  const live = getSession(id);
  assert.equal(live.plan.gates.ddia.requirement, "on-demand");
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";

  const promoted = sbtdPlan(id, {
    task_summary: summary,
    facts: ["persist"],
  });
  assert.equal(promoted.plan.gates.ddia.requirement, "required");
  assert.equal(promoted.plan.gates.ddia.state, "planned");
  assert.equal(promoted.plan.gates.ddia.reviewStatus, undefined);
  assert.equal(promoted.plan.gates.ddia.fact, "persistence");
  assert.match(promoted.markdown, /promoted from on-demand; reset inherited pass/);
});

test("mergeGate 提升 required 时保留 running blocked planned", () => {
  const summary = "hello world plan keep progress";
  for (const state of ["running", "blocked", "planned"]) {
    const id = `plan-merge-keep-${state}`;
    sbtdPlan(id, { task_summary: summary });
    const live = getSession(id);
    live.plan.gates.ddia.state = state;
    live.plan.gates.ddia.reviewStatus = "needs-design-change";

    const next = sbtdPlan(id, {
      task_summary: summary,
      facts: ["persist"],
    });
    assert.equal(next.plan.gates.ddia.requirement, "required");
    assert.equal(next.plan.gates.ddia.state, state);
    assert.equal(next.plan.gates.ddia.reviewStatus, "needs-design-change");
  }
});

test("新 taskId 开新 plan，不保留上一目标的 passed", () => {
  const id = "plan-sess-new-task";
  sbtdPlan(id, {
    task_summary: "task alpha persist shared data",
  });
  const live = getSession(id);
  live.plan.gates.ddia.state = "passed";
  live.plan.gates.ddia.reviewStatus = "confirmed";

  const next = sbtdPlan(id, {
    task_summary: "task beta persist shared data",
  });
  assert.notEqual(
    next.plan.taskId,
    taskIdFromSummary("task alpha persist shared data"),
  );
  assert.equal(
    next.plan.taskId,
    taskIdFromSummary("task beta persist shared data"),
  );
  assert.equal(next.plan.gates.ddia.requirement, "required");
  assert.equal(next.plan.gates.ddia.state, "planned");
  assert.equal(next.plan.gates.ddia.reviewStatus, undefined);
});

test("空 task_summary 抛错", () => {
  assert.throws(
    () => sbtdPlan("plan-empty", { task_summary: "" }),
    /task_summary/,
  );
  assert.throws(
    () => sbtdPlan("plan-empty", { task_summary: "   " }),
    /task_summary/,
  );
});

test("restore 已 hydrate；空 snapshot 已清除 plan", () => {
  const id = "plan-sess-restore";
  const written = sbtdPlan(id, {
    task_summary: "persist shared data",
  });
  assert.ok(getSession(id).plan);

  restore("plan-sess-hydrated", { plan: written.plan });
  assert.equal(
    getSession("plan-sess-hydrated").plan?.taskId,
    written.plan.taskId,
  );

  restore(id, {});
  assert.equal(getSession(id).plan, undefined);
});

test("apply 注册 sbtd_plan 且不写 AGENTS.md", async () => {
  const tools = [];
  const sections = [];
  apply({
    systemPrompt: {
      section(opts) {
        sections.push(opts);
      },
    },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
  });

  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 2);
  assert.equal(tools[0].name, SBTD_PLAN_TOOL_NAME);
  assert.equal(tools[1].name, "sbtd_review");
  assert.equal(sections[0].name, "sbtd");
  assert.equal(tools[0].isConcurrencySafe({}), false);
  assert.equal(tools[0].parameters.type, "object");
  assert.deepEqual(tools[0].parameters.required, ["task_summary"]);
  assert.equal(tools[0].parameters.properties.task_summary.type, "string");
  assert.equal(tools[0].parameters.properties.facts.type, "array");
  assert.equal(tools[0].output.schema.type, "object");
  assert.equal(tools[0].output.schema.additionalProperties, false);
  assert.equal(tools[0].output.schema.properties.plan.type, "object");
  assert.equal(tools[0].output.schema.properties.markdown.type, "string");

  const result = await tools[0].execute(
    { task_summary: "deploy production path job" },
    { agent: { id: "plan-sess-tool" } },
  );
  assert.equal(
    getSession("plan-sess-tool").plan?.gates.release.requirement,
    "required",
  );
  assert.ok(result.plan);
  assert.ok(result.markdown);

  const src = readFileSync(join(pkgRoot, "src/tools/plan.ts"), "utf8");
  assert.doesNotMatch(src, /writeFile|AGENTS\.md|@deepseek-ai\/dsh/);
  const index = readFileSync(join(pkgRoot, "src/index.ts"), "utf8");
  assert.doesNotMatch(index, /writeFile|AGENTS\.md|@deepseek-ai\/dsh/);
});

test("createPlanTool parameters 为 JSON Schema object 根，plan type 为 object", () => {
  const tool = createPlanTool();
  assert.equal(tool.name, SBTD_PLAN_TOOL_NAME);
  assert.equal(tool.parameters.type, "object");
  assert.equal(tool.parameters.properties.task_summary.type, "string");
  assert.equal(tool.parameters.properties.task_summary.required, undefined);
  assert.deepEqual(tool.parameters.required, ["task_summary"]);
  assert.equal(tool.parameters.properties.facts.type, "array");
  assert.equal(tool.parameters.properties.facts.items.type, "string");
  assert.equal(tool.parameters.task_summary, undefined);
  assert.equal(tool.output.schema.additionalProperties, false);
  assert.equal(tool.output.schema.properties.plan.type, "object");
  assert.notEqual(tool.output.schema.properties.plan.type, "json");
  assert.equal(tool.isConcurrencySafe({ task_summary: "x" }), false);
});

test("README 提到 sbtd_plan 并保持钉版本与 @next", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /sbtd_plan/);
  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
  assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
  assert.doesNotMatch(
    readme,
    /\/absolute\/path\/to\/sbtd-plugins\/packages\/dsh-sbtd/,
  );
});

test("distinct summaries do not share taskId", () => {
  const a = taskIdFromSummary("a" + "x".repeat(90));
  const b = taskIdFromSummary("a" + "y".repeat(90));
  assert.notEqual(a, b);
  assert.equal(taskIdFromSummary(""), taskIdFromSummary("   "));
  assert.match(taskIdFromSummary(""), /^task-[0-9a-f]{12}$/);
});
