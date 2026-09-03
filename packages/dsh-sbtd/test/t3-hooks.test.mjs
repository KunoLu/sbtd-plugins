import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { apply, inject, name } from "../dist/index.js";
import { getSession } from "../dist/state.js";
import { sbtdPlan } from "../dist/tools/plan.js";
import {
  PRE_EXECUTE_EVENT,
  PRE_STEP_EVENT,
} from "../dist/hooks.js";

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

test("apply 注册 pre-execute 与 pre-step，且仅两个 sbtd_* tool", () => {
  const { tools, hooks } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 2);
  assert.equal(tools[0].name, "sbtd_plan");
  assert.equal(tools[1].name, "sbtd_review");
  assert.equal(typeof hooks.get(PRE_EXECUTE_EVENT), "function");
  assert.equal(typeof hooks.get(PRE_STEP_EVENT), "function");
});

test("无 plan 时写 src 被 ask 去 sbtd_plan", async () => {
  const { hooks } = loadPlugin();
  let nextCalled = false;
  const result = await hooks.get(PRE_EXECUTE_EVENT)(
    writeSrc("t3-no-plan"),
    async () => {
      nextCalled = true;
      return { kind: "allow" };
    },
  );
  assert.equal(nextCalled, false);
  assert.equal(result.kind, "ask");
  assert.match(result.reason, /sbtd_plan/);
});

test("README 编辑放行", async () => {
  const { hooks } = loadPlugin();
  let nextCalled = false;
  const result = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "edit",
      arguments: { file_path: "README.md" },
      agent: { id: "t3-readme" },
    },
    async () => {
      nextCalled = true;
      return { kind: "allow" };
    },
  );
  assert.equal(nextCalled, true);
  assert.equal(result.kind, "allow");
});

test("cwd 外实现文件与无路径 mutating bash 不是生产代码", async () => {
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  for (const exec of [
    writeSrc("t3-offroot", "scripts/foo.ts"),
    {
      name: "bash",
      arguments: { command: "mkdir tmp" },
      agent: { id: "t3-mkdir" },
    },
  ]) {
    let nextCalled = false;
    const result = await pre(exec, async () => {
      nextCalled = true;
      return { kind: "allow" };
    });
    assert.equal(nextCalled, true, exec.arguments.path ?? exec.arguments.command);
    assert.equal(result.kind, "allow");
  }
});

test("str_replace_editor command=view 放行", async () => {
  const { hooks } = loadPlugin();
  let nextCalled = false;
  const result = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "str_replace_editor",
      arguments: { command: "view", path: "src/foo.ts" },
      agent: { id: "t3-sre-view" },
    },
    async () => {
      nextCalled = true;
      return { kind: "allow" };
    },
  );
  assert.equal(nextCalled, true);
  assert.equal(result.kind, "allow");
});

test("view 与 git commit status log diff show 放行", async () => {
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  for (const exec of [
    { name: "view", arguments: { path: "src/foo.ts" }, agent: { id: "t3-view" } },
    {
      name: "bash",
      arguments: { command: "git commit -m wip" },
      agent: { id: "t3-git" },
    },
    {
      name: "bash",
      arguments: { command: "git status" },
      agent: { id: "t3-git" },
    },
    {
      name: "bash",
      arguments: { command: "git log -1" },
      agent: { id: "t3-git" },
    },
    {
      name: "bash",
      arguments: { command: "git diff" },
      agent: { id: "t3-git" },
    },
    {
      name: "bash",
      arguments: { command: "git show HEAD" },
      agent: { id: "t3-git" },
    },
  ]) {
    let nextCalled = false;
    const result = await pre(exec, async () => {
      nextCalled = true;
      return { kind: "allow" };
    });
    assert.equal(nextCalled, true, exec.arguments.command ?? exec.name);
    assert.equal(result.kind, "allow");
  }
});

test("required unpassed 时 deny 去 sbtd_review，顺序 legacy 然后 refactor 然后 ddd", async () => {
  const id = "t3-order";
  sbtdPlan(id, {
    task_summary: "change existing production after completed grill-with-docs",
    facts: ["existing behavior", "existing production", "completed grill-with-docs"],
  });
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  const first = await pre(writeSrc(id), nextAllow);
  assert.equal(first.kind, "deny");
  assert.match(first.reason, /sbtd_review kind=legacy/);

  getSession(id).plan.gates.legacy.state = "passed";
  const second = await pre(writeSrc(id), nextAllow);
  assert.equal(second.kind, "deny");
  assert.match(second.reason, /sbtd_review kind=refactor/);

  getSession(id).plan.gates.refactor.state = "passed";
  const third = await pre(writeSrc(id), nextAllow);
  assert.equal(third.kind, "deny");
  assert.match(third.reason, /sbtd_review kind=ddd/);

  getSession(id).plan.gates.ddd.state = "passed";
  let nextCalled = false;
  const fourth = await pre(writeSrc(id), async () => {
    nextCalled = true;
    return { kind: "allow" };
  });
  assert.equal(nextCalled, true);
  assert.equal(fourth.kind, "allow");
});

test("ddia 只拦数据路径", async () => {
  const id = "t3-ddia";
  sbtdPlan(id, { task_summary: "persist schema cache" });
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  let nextCalled = false;
  const code = await pre(writeSrc(id), async () => {
    nextCalled = true;
    return { kind: "allow" };
  });
  assert.equal(nextCalled, true);
  assert.equal(code.kind, "allow");

  const data = await pre(
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

test("release 不拦编辑但拦 publish bash", async () => {
  const id = "t3-release";
  sbtdPlan(id, { task_summary: "deploy production path job" });
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  let nextCalled = false;
  const edit = await pre(writeSrc(id), async () => {
    nextCalled = true;
    return { kind: "allow" };
  });
  assert.equal(nextCalled, true);
  assert.equal(edit.kind, "allow");

  const publish = await pre(
    {
      name: "bash",
      arguments: { command: "npm publish" },
      agent: { id },
    },
    nextAllow,
  );
  assert.equal(publish.kind, "deny");
  assert.match(publish.reason, /sbtd_review kind=release/);
});

test("豁免路径无 plan 时 ask，有 plan 时不硬拦", async () => {
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  const exemptFiles = [
    "src/foo.test.ts",
    "features/t3-hooks-gate.feature",
    "maestro/flow/smoke.yml",
    ".trellis/spec/dsh-sbtd/backend/index.md",
  ];
  for (const file of exemptFiles) {
    const asked = await pre(
      {
        name: "write",
        arguments: { path: file },
        agent: { id: "t3-exempt-noplan" },
      },
      nextAllow,
    );
    assert.equal(asked.kind, "ask", file);
    assert.match(asked.reason, /sbtd_plan/);
  }

  const id = "t3-exempt-plan";
  sbtdPlan(id, {
    task_summary: "fix existing behavior",
    facts: ["existing behavior"],
  });
  for (const file of exemptFiles) {
    let nextCalled = false;
    const result = await pre(
      { name: "write", arguments: { path: file }, agent: { id } },
      async () => {
        nextCalled = true;
        return { kind: "allow" };
      },
    );
    assert.equal(nextCalled, true, file);
    assert.equal(result.kind, "allow", file);
  }
});

test("rm 或包管理器改业务代码要 ask", async () => {
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  for (const command of [
    "rm src/foo.ts",
    "pnpm add ./packages/foo",
    "npm uninstall ./src/legacy",
  ]) {
    const result = await pre(
      { name: "bash", arguments: { command }, agent: { id: "t3-rm" } },
      nextAllow,
    );
    assert.equal(result.kind, "ask", command);
    assert.match(result.reason, /sbtd_plan/);
  }
});

test("无 plan 时 rm src 被 ask", async () => {
  const { hooks } = loadPlugin();
  const result = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "bash",
      arguments: { command: "rm src/foo.ts" },
      agent: { id: "t3-rm-src-noplan" },
    },
    nextAllow,
  );
  assert.equal(result.kind, "ask");
  assert.match(result.reason, /sbtd_plan/);
});

test("有 plan 且 required unpassed 时 rm src 被 deny 去 sbtd_review", async () => {
  const id = "t3-rm-src-plan";
  sbtdPlan(id, {
    task_summary: "change existing production after completed grill-with-docs",
    facts: [
      "existing behavior",
      "existing production",
      "completed grill-with-docs",
    ],
  });
  const { hooks } = loadPlugin();
  const result = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "bash",
      arguments: { command: "rm src/foo.ts" },
      agent: { id },
    },
    nextAllow,
  );
  assert.equal(result.kind, "deny");
  assert.match(result.reason, /sbtd_review kind=legacy/);
});

test("有 plan 时 rm features/test 放行", async () => {
  const id = "t3-rm-exempt-plan";
  sbtdPlan(id, {
    task_summary: "change existing production after completed grill-with-docs",
    facts: [
      "existing behavior",
      "existing production",
      "completed grill-with-docs",
    ],
  });
  const { hooks } = loadPlugin();
  let nextCalled = false;
  const result = await hooks.get(PRE_EXECUTE_EVENT)(
    {
      name: "bash",
      arguments: { command: "rm features/test" },
      agent: { id },
    },
    async () => {
      nextCalled = true;
      return { kind: "allow" };
    },
  );
  assert.equal(nextCalled, true);
  assert.equal(result.kind, "allow");
});

test("pre-step 先 await next，开发意图无 plan 时注入 plugin notice，不自己 reject", async () => {
  const { hooks } = loadPlugin();
  const preStep = hooks.get(PRE_STEP_EVENT);
  let nextCalled = false;
  const entered = await preStep(
    {
      agent: { id: "t3-prestep" },
      messages: [
        { content: [{ type: "text", text: "实现这个功能，改 src/ 生产代码" }] },
      ],
    },
    async () => {
      nextCalled = true;
      return {
        kind: "enter",
        messages: [
          { content: [{ type: "text", text: "实现这个功能，改 src/ 生产代码" }] },
        ],
      };
    },
  );
  assert.equal(nextCalled, true);
  assert.equal(entered.kind, "enter");
  const notice = entered.messages.at(-1);
  assert.equal(notice.source.kind, "plugin");
  assert.equal(notice.source.plugin, "dsh-sbtd");
  assert.equal(notice.source.form, "notice");
  assert.match(notice.source.summary, /sbtd_plan/);
  assert.match(JSON.stringify(notice.content), /sbtd_plan/);

  const rejected = await preStep(
    {
      agent: { id: "t3-prestep-reject" },
      messages: [{ content: [{ type: "text", text: "实现" }] }],
    },
    async () => ({ kind: "reject" }),
  );
  assert.equal(rejected.kind, "reject");
});

test("门禁按 sessionIdFromExec 隔离", async () => {
  sbtdPlan("t3-sess-a", {
    task_summary: "fix existing behavior in production",
    facts: ["existing behavior"],
  });
  const { hooks } = loadPlugin();
  const pre = hooks.get(PRE_EXECUTE_EVENT);
  const planned = await pre(writeSrc("t3-sess-a"), nextAllow);
  assert.equal(planned.kind, "deny");
  assert.match(planned.reason, /sbtd_review/);
  const other = await pre(writeSrc("t3-sess-b"), nextAllow);
  assert.equal(other.kind, "ask");
  assert.match(other.reason, /sbtd_plan/);
});

test("README 提到 hooks 并保持钉版本与 @next 未发布", () => {
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  const src = readFileSync(join(pkgRoot, "src/hooks.ts"), "utf8");
  const index = readFileSync(join(pkgRoot, "src/index.ts"), "utf8");
  assert.match(readme, /hooks/);
  assert.match(readme, /@deepseek-ai\/dsh@0\.1\.1-rc\.2/);
  assert.match(readme, /dsh plugin --profile web add @kunolu\/dsh-sbtd@next/);
  assert.match(readme, /尚未发布到 npm/);
  assert.doesNotMatch(readme, /0\.1\.0-rc\.7|0\.1\.2-alpha/);
  assert.doesNotMatch(
    readme,
    /\/absolute\/path\/to\/sbtd-plugins\/packages\/dsh-sbtd/,
  );
  assert.doesNotMatch(src, /@deepseek-ai\/dsh/);
  assert.doesNotMatch(index, /@deepseek-ai\/dsh|writeFile|AGENTS\.md/);
  assert.doesNotMatch(src, /writeFile|AGENTS\.md/);
});
