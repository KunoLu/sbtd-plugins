import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { PRE_EXECUTE_EVENT } from "../dist/hooks.js";
import { getSession } from "../dist/state.js";
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

test("apply 注册恰好 sbtd_plan 与 sbtd_review", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 2);
  assert.equal(tools[0].name, "sbtd_plan");
  assert.equal(tools[1].name, SBTD_REVIEW_TOOL_NAME);
});

test("kind 仅五枚举，拒绝别名与 skill-id", () => {
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

test("通过态映射为 passed 并存储 reviewStatus", () => {
  const cases = [
    ["legacy", "characterized", "fix existing behavior bug"],
    ["refactor", "proceed", "edit existing production module"],
    ["ddd", "confirmed", "completed grill-with-docs"],
    ["ddia", "confirmed", "persist shared data"],
    ["release", "ready", "deploy production path job"],
  ];
  for (const [kind, status, summary] of cases) {
    const id = `t5-pass-${kind}`;
    sbtdPlan(id, { task_summary: summary });
    const result = sbtdReview(id, {
      kind,
      status,
      conclusions: `${kind} ok`,
    });
    assert.equal(result.title, REVIEW_TITLES[kind]);
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

test("结论只在返回值，manuals 只读 1 对 1", () => {
  const id = "t5-manual";
  sbtdPlan(id, { task_summary: "fix existing behavior bug" });
  const result = sbtdReview(id, {
    kind: "legacy",
    status: "characterized",
    conclusions: "do-not-write",
  });
  assert.equal(result.manual, loadReviewManual("legacy"));
  assert.match(result.manual, /name: book-legacy-change-safety/);
  assert.match(loadReviewManual("refactor"), /name: book-refactoring-pass/);
  assert.match(loadReviewManual("ddd"), /name: book-ddd-distilled-modeling/);
  assert.match(loadReviewManual("ddia"), /name: book-ddia-data-design/);
  assert.match(loadReviewManual("release"), /name: book-release-readiness/);

  const src = readFileSync(join(pkgRoot, "src/tools/review.ts"), "utf8");
  assert.match(src, /import\.meta\.url/);
  assert.doesNotMatch(
    src,
    /grill-with-docs|grill-me|to-spec|to-tickets|trellis-workflow|domain-modeling/,
  );
  assert.doesNotMatch(src, /writeFile|writeFileSync|AGENTS\.md/);
  const manuals = readFileSync(
    join(pkgRoot, "manuals/book-legacy-change-safety/SKILL.md"),
    "utf8",
  );
  assert.doesNotMatch(manuals, /do-not-write/);
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

test("required unpassed refactor 与 ddd 仍拦 write", async () => {
  const id = "t5-refactor-ddd";
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
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  const refactorDeny = await pre(writeSrc(id), nextAllow);
  assert.equal(refactorDeny.kind, "deny");
  assert.match(refactorDeny.reason, /sbtd_review kind=refactor/);

  sbtdReview(id, { kind: "refactor", status: "proceed" });
  const dddDeny = await pre(writeSrc(id), nextAllow);
  assert.equal(dddDeny.kind, "deny");
  assert.match(dddDeny.reason, /sbtd_review kind=ddd/);
});

test("required unpassed ddia 拦数据路径；release 拦 publish bash 不拦普通编辑", async () => {
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

  const relId = "t5-release";
  sbtdPlan(relId, { task_summary: "deploy production path job" });
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
  assert.equal(tool.isConcurrencySafe({ kind: "legacy", status: "characterized" }), false);

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
});

test("README 提到 sbtd_review 并保持钉版本", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /sbtd_review/);
  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
  assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
});
