import assert from "node:assert/strict";
import {
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  readlinkSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import {
  describeWorkflowMode,
  resolveWorkflowMode,
  WORKFLOW_MODES,
} from "../dist/backends/sbtd-task.js";
import { apply } from "../dist/index.js";

const TASK_REL = "ai/tasks/t7-fixture/task.md";

/** Full task.md metadata block, mirroring the TaskStore-written shape. */
function fullTaskMd(fm) {
  return [
    "---",
    "schema_version: 1",
    "id: t7-fixture",
    fm,
    'status: "in-progress"',
    "created_at: '2026-10-18T10:00:00+08:00'",
    "---",
    "",
    "# T7 fixture task",
    "",
  ].join("\n");
}

function makeProject({ pointer, files = {} } = {}) {
  const cwd = mkdtempSync(join(tmpdir(), "t7-sbtd-task-"));
  if (pointer !== undefined) {
    mkdirSync(join(cwd, ".sbtd"), { recursive: true });
    writeFileSync(join(cwd, ".sbtd", "active-task.json"), pointer);
  }
  for (const [rel, content] of Object.entries(files)) {
    const abs = join(cwd, rel);
    mkdirSync(dirname(abs), { recursive: true });
    writeFileSync(abs, content);
  }
  return cwd;
}

const pointerTo = (taskPath) =>
  JSON.stringify({
    schema_version: 1,
    task_id: "t7-fixture",
    task_path: taskPath,
  });

function projectWithTask(frontmatter) {
  return makeProject({
    pointer: pointerTo(TASK_REL),
    files: { [TASK_REL]: fullTaskMd(frontmatter) },
  });
}

function snapshotTree(root) {
  const entries = [];
  const walk = (dir, prefix) => {
    for (const name of readdirSync(dir).sort()) {
      const abs = join(dir, name);
      const rel = prefix === "" ? name : `${prefix}/${name}`;
      const stat = lstatSync(abs);
      if (stat.isSymbolicLink()) {
        entries.push(`${rel} -> ${readlinkSync(abs)}`);
      } else if (stat.isDirectory()) {
        walk(abs, rel);
      } else {
        entries.push(`${rel}::${readFileSync(abs, "utf8")}`);
      }
    }
  };
  walk(root, "");
  return entries;
}

function loadPluginTools(host = {}) {
  const tools = [];
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
    commands: { register() {} },
    ...host,
  });
  return tools;
}

test("模式词表锁定 strict/default/lite", () => {
  assert.deepEqual([...WORKFLOW_MODES], ["strict", "default", "lite"]);
});

test("分层优先级：工具参数 > 宿主注入 > 任务文件 > 缺省（R1 Q4）", () => {
  const cwd = projectWithTask("workflow_mode: lite\nbranch: feat/t7");

  const byParam = resolveWorkflowMode({
    param: "strict",
    host: "default",
    cwd,
    currentBranch: "feat/t7",
  });
  assert.deepEqual(byParam, { mode: "strict", source: "param" });

  const byHost = resolveWorkflowMode({
    host: "default",
    cwd,
    currentBranch: "feat/t7",
  });
  assert.deepEqual(byHost, { mode: "default", source: "host" });

  const byTask = resolveWorkflowMode({ cwd, currentBranch: "feat/t7" });
  assert.deepEqual(byTask, { mode: "lite", source: "task-file" });

  const byDefault = resolveWorkflowMode({ cwd: makeProject() });
  assert.equal(byDefault.mode, "default");
  assert.equal(byDefault.source, "default");
  assert.match(byDefault.note, /active-task\.json 指针缺失或损坏/);
});

test("无效上层取值带提示落层，永不拒载", () => {
  const cwd = projectWithTask("workflow_mode: lite\nbranch: feat/t7");

  const badParam = resolveWorkflowMode({
    param: "bogus",
    host: "strict",
    cwd,
    currentBranch: "feat/t7",
  });
  assert.equal(badParam.mode, "strict");
  assert.equal(badParam.source, "host");
  assert.match(badParam.note, /工具参数 workflow_mode 无效/);

  const badBoth = resolveWorkflowMode({
    param: "bogus",
    host: "bogus2",
    cwd,
    currentBranch: "feat/t7",
  });
  assert.equal(badBoth.mode, "lite");
  assert.equal(badBoth.source, "task-file");
  assert.match(badBoth.note, /工具参数 workflow_mode 无效/);
  assert.match(badBoth.note, /宿主注入 workflow_mode 无效/);

  // 三层全败：提示按层序以 ；连接
  const allBad = resolveWorkflowMode({
    param: "x",
    host: "y",
    cwd: makeProject(),
  });
  assert.equal(allBad.mode, "default");
  assert.equal(allBad.source, "default");
  const parts = allBad.note.split("；");
  assert.equal(parts.length, 3);
  assert.match(parts[0], /工具参数 workflow_mode 无效/);
  assert.match(parts[1], /宿主注入 workflow_mode 无效/);
  assert.match(parts[2], /指针缺失或损坏/);

  // 空串参数视为未提供（静默落层）；首尾空白取值照常解析
  const blank = resolveWorkflowMode({
    param: "",
    host: "lite",
    cwd: makeProject(),
  });
  assert.deepEqual(blank, { mode: "lite", source: "host" });
  const padded = resolveWorkflowMode({
    param: "  strict  ",
    cwd: makeProject(),
  });
  assert.deepEqual(padded, { mode: "strict", source: "param" });
});

test("active-task 指针缺失或损坏一律退回缺省并提示", () => {
  const cases = [
    ["指针文件不存在", makeProject()],
    ["指针非 JSON", makeProject({ pointer: "not-json{" })],
    [
      "指针缺 task_path 字段",
      makeProject({ pointer: JSON.stringify({ schema_version: 1 }) }),
    ],
    ["task_path 为空串", makeProject({ pointer: pointerTo("   ") })],
    [
      "task_path 非字符串",
      makeProject({ pointer: JSON.stringify({ task_path: 42 }) }),
    ],
  ];
  for (const [label, cwd] of cases) {
    const res = resolveWorkflowMode({ cwd });
    assert.equal(res.mode, "default", label);
    assert.equal(res.source, "default", label);
    assert.match(res.note, /指针缺失或损坏/, label);
  }

  const ghost = resolveWorkflowMode({
    cwd: makeProject({ pointer: pointerTo(TASK_REL) }),
  });
  assert.equal(ghost.mode, "default");
  assert.equal(ghost.source, "default");
  assert.match(ghost.note, /指针指向的 task\.md 缺失/);
});

test("task.md frontmatter 缺陷一律退回缺省并提示", () => {
  const noted = [
    ["无 frontmatter", "# plain markdown\n"],
    [
      "workflow_mode 取值非法",
      fullTaskMd("workflow_mode: banana\nbranch: feat/t7"),
    ],
    ["frontmatter 未闭合", "---\nworkflow_mode: strict\nbranch: feat/t7\n"],
  ];
  for (const [label, content] of noted) {
    const cwd = makeProject({
      pointer: pointerTo(TASK_REL),
      files: { [TASK_REL]: content },
    });
    const res = resolveWorkflowMode({ cwd, currentBranch: "feat/t7" });
    assert.equal(res.mode, "default", label);
    assert.equal(res.source, "default", label);
    assert.match(res.note, /task\.md 无有效 workflow_mode/, label);
  }

  // 加固语义（top-level 键、键唯一、定界符严格、branch 键必需）
  const hardened = [
    ["缺 branch 键", fullTaskMd("workflow_mode: strict")],
    [
      "缩进嵌套键不采纳",
      fullTaskMd("  workflow_mode: strict\n  branch: feat/t7"),
    ],
    [
      "workflow_mode 重复键",
      fullTaskMd("workflow_mode: strict\nworkflow_mode: lite\nbranch: feat/t7"),
    ],
    [
      "branch 同值重复键",
      fullTaskMd("workflow_mode: strict\nbranch: feat/t7\nbranch: feat/t7"),
    ],
    [
      "opener 定界符畸形",
      "----\nworkflow_mode: strict\nbranch: feat/t7\n---\n",
    ],
    [
      "closer 定界符畸形",
      "---\nworkflow_mode: strict\nbranch: feat/t7\n----\n",
    ],
  ];
  for (const [label, content] of hardened) {
    const cwd = makeProject({
      pointer: pointerTo(TASK_REL),
      files: { [TASK_REL]: content },
    });
    const res = resolveWorkflowMode({ cwd, currentBranch: "feat/t7" });
    assert.equal(res.mode, "default", label);
    assert.equal(res.source, "default", label);
    assert.equal(typeof res.note, "string", label);
  }
});

test("分支一致才采用任务模式；mismatch 精确措辞（R2 Q6 B）", () => {
  const fm = "workflow_mode: strict\nbranch: feat/t7";

  const adopted = resolveWorkflowMode({
    cwd: projectWithTask(fm),
    currentBranch: "feat/t7",
  });
  assert.deepEqual(adopted, { mode: "strict", source: "task-file" });

  const quoted = resolveWorkflowMode({
    cwd: projectWithTask('workflow_mode: "strict"\nbranch: "feat/t7"'),
    currentBranch: "feat/t7",
  });
  assert.deepEqual(quoted, { mode: "strict", source: "task-file" });

  const mismatch = resolveWorkflowMode({
    cwd: projectWithTask(fm),
    currentBranch: "main",
  });
  assert.equal(mismatch.mode, "default");
  assert.equal(mismatch.source, "default");
  assert.equal(
    mismatch.note,
    "任务属于其他分支（任务分支 feat/t7，当前分支 main）",
  );

  // 当前分支未知（非 git）：无法比较，退回缺省
  const unknown = resolveWorkflowMode({
    cwd: projectWithTask(fm),
    currentBranch: null,
  });
  assert.equal(unknown.mode, "default");
  assert.match(unknown.note, /无法确定当前分支/);

  // 任务 branch 取值畸形：退回缺省并提示，不拒载
  const weird = resolveWorkflowMode({
    cwd: projectWithTask('workflow_mode: strict\nbranch: "unterminated'),
    currentBranch: "main",
  });
  assert.equal(weird.mode, "default");
  assert.equal(weird.source, "default");
  assert.equal(typeof weird.note, "string");
});

test("任务 branch: null 仅在接受侧同样非 git 时采用（R2 Q6 B）", () => {
  const fm = "workflow_mode: lite\nbranch: null";

  // 双方均非 git：无可比较，采用任务模式
  const bothNonGit = resolveWorkflowMode({
    cwd: projectWithTask(fm),
    currentBranch: null,
  });
  assert.deepEqual(bothNonGit, { mode: "lite", source: "task-file" });

  // 已知 git 分支 vs null 任务绑定：按 mismatch 退回缺省
  const knownGit = resolveWorkflowMode({
    cwd: projectWithTask(fm),
    currentBranch: "main",
  });
  assert.equal(knownGit.mode, "default");
  assert.equal(knownGit.source, "default");
  assert.equal(typeof knownGit.note, "string");
});

test("指针路径逃逸与受限根目录外一律拒绝", () => {
  const outside = mkdtempSync(join(tmpdir(), "t7-outside-"));
  const outsideTask = join(outside, "escape.md");
  writeFileSync(
    outsideTask,
    fullTaskMd("workflow_mode: strict\nbranch: feat/t7"),
  );

  // 绝对路径
  const absolute = resolveWorkflowMode({
    cwd: makeProject({ pointer: pointerTo(outsideTask) }),
    currentBranch: "feat/t7",
  });
  assert.equal(absolute.mode, "default");
  assert.match(absolute.note, /不安全/);

  // .. 相对逃逸
  const dots = resolveWorkflowMode({
    cwd: makeProject({ pointer: pointerTo("../escape.md") }),
    currentBranch: "feat/t7",
  });
  assert.equal(dots.mode, "default");
  assert.match(dots.note, /不安全/);

  // 符号链接逃逸（realpath 校验）
  const linkCwd = makeProject({ pointer: pointerTo(TASK_REL) });
  mkdirSync(join(linkCwd, dirname(TASK_REL)), { recursive: true });
  symlinkSync(outsideTask, join(linkCwd, TASK_REL));
  const linked = resolveWorkflowMode({ cwd: linkCwd, currentBranch: "feat/t7" });
  assert.equal(linked.mode, "default");
  assert.match(linked.note, /不安全/);

  // 受限根目录之外：即使文件存在且元数据完整也拒绝
  const content = fullTaskMd("workflow_mode: strict\nbranch: feat/t7");
  const restricted = [
    ["根目录 task.md", "task.md"],
    ["docs 下的 task.md", "docs/task.md"],
    ["ai/tasks 下非 task.md 文件名", "ai/tasks/t7-fixture/notes.md"],
    ["反斜杠分隔符", "ai\\tasks\\t7-fixture\\task.md"],
    ["点段路径", "ai/tasks/../tasks/t7-fixture/task.md"],
  ];
  for (const [label, rel] of restricted) {
    const cwd = makeProject({ pointer: pointerTo(rel), files: { [rel]: content } });
    const res = resolveWorkflowMode({ cwd, currentBranch: "feat/t7" });
    assert.equal(res.mode, "default", label);
    assert.equal(res.source, "default", label);
    assert.equal(typeof res.note, "string", label);
  }

  // 两个允许根目录都可采用
  for (const rel of [
    "ai/tasks/t7-fixture/task.md",
    ".sbtd/tasks/t7-fixture/task.md",
  ]) {
    const cwd = makeProject({ pointer: pointerTo(rel), files: { [rel]: content } });
    const res = resolveWorkflowMode({ cwd, currentBranch: "feat/t7" });
    assert.deepEqual(res, { mode: "strict", source: "task-file" }, rel);
  }
});

test("解析全程只读：.sbtd 与任务树零写入", () => {
  const cwd = projectWithTask("workflow_mode: strict\nbranch: feat/t7");
  const before = snapshotTree(cwd);
  resolveWorkflowMode({ cwd, currentBranch: "main" });
  resolveWorkflowMode({
    param: "lite",
    host: "strict",
    cwd,
    currentBranch: "feat/t7",
  });
  resolveWorkflowMode({ cwd, currentBranch: "feat/t7" });
  assert.deepEqual(snapshotTree(cwd), before);

  // 无指针项目：解析后不创建 .sbtd
  const empty = makeProject();
  resolveWorkflowMode({ cwd: empty });
  assert.deepEqual(readdirSync(empty), []);
});

test("describeWorkflowMode 输出中文来源标签", () => {
  assert.equal(
    describeWorkflowMode({ mode: "strict", source: "task-file" }),
    "strict（来源：任务文件）",
  );
  assert.equal(
    describeWorkflowMode({ mode: "lite", source: "param" }),
    "lite（来源：工具参数）",
  );
  assert.equal(
    describeWorkflowMode({ mode: "default", source: "host" }),
    "default（来源：宿主注入）",
  );
  assert.equal(
    describeWorkflowMode({ mode: "default", source: "default" }),
    "default（来源：缺省）",
  );
});

test("apply 宿主袋注入直达 plan/review/validate 结果与 schema（R3 Q4 A）", async () => {
  const cwd = makeProject();
  const tools = loadPluginTools({
    planHost: { workflowMode: "strict", cwd },
    reviewHost: { workflowMode: "lite", cwd },
    validateHost: { workflowMode: "default", cwd },
  });
  const byName = (name) => tools.find((tool) => tool.name === name);
  const plan = byName("sbtd_plan");
  const review = byName("sbtd_review");
  const validate = byName("sbtd_validate");

  // schema 表面：三工具都暴露 workflow_mode 参数与模式结果字段
  for (const tool of [plan, review, validate]) {
    assert.ok(tool, "tool registered");
    assert.deepEqual(tool.parameters.properties.workflow_mode.enum, [
      "strict",
      "default",
      "lite",
    ]);
    assert.equal(tool.output.schema.properties.workflowMode.type, "string");
    assert.equal(
      tool.output.schema.properties.workflowModeSource.type,
      "string",
    );
    assert.equal(tool.output.schema.properties.workflowModeNote.type, "string");
  }

  const exec = { agent: { id: "t7-apply-host" } };
  const planResult = await plan.execute(
    { task_summary: "fix existing behavior bug" },
    exec,
  );
  assert.equal(planResult.workflowMode, "strict");
  assert.equal(planResult.workflowModeSource, "host");

  // 工具参数覆盖宿主袋（layer 1 > layer 2），不写入任何会话态
  const overridden = await plan.execute(
    { task_summary: "t7 param override", workflow_mode: "lite" },
    { agent: { id: "t7-apply-override" } },
  );
  assert.equal(overridden.workflowMode, "lite");
  assert.equal(overridden.workflowModeSource, "param");

  const reviewResult = await review.execute(
    { kind: "legacy", status: "characterized" },
    exec,
  );
  assert.equal(reviewResult.workflowMode, "lite");
  assert.equal(reviewResult.workflowModeSource, "host");

  // 宿主袋注入的 default 与缺省层区分：source 仍为 host
  const validateResult = await validate.execute({ phase: "pre" }, exec);
  assert.equal(validateResult.workflowMode, "default");
  assert.equal(validateResult.workflowModeSource, "host");
});
