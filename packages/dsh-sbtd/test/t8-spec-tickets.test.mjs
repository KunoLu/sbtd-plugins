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
import { join } from "node:path";
import { test } from "node:test";
import { apply, inject, name } from "../dist/index.js";
import { getSession } from "../dist/state.js";
import { sbtdPlan } from "../dist/tools/plan.js";
import { sbtdReview } from "../dist/tools/review.js";
import {
  SBTD_SPEC_TOOL_NAME,
  sbtdSpec,
} from "../dist/tools/spec.js";
import {
  SBTD_TICKETS_TOOL_NAME,
  sbtdTickets,
} from "../dist/tools/tickets.js";
import { slugFromPointer } from "../dist/tools/task-artifact.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t8-" + label + "-"));
}

function withTrellis(root, opts = {}) {
  mkdirSync(join(root, ".trellis"), { recursive: true });
  if (opts.workflow != null) {
    writeFileSync(join(root, ".trellis", "workflow.md"), opts.workflow, "utf8");
  }
}

function writeSession(root, key, currentTask) {
  const sessions = join(root, ".trellis", ".runtime", "sessions");
  mkdirSync(sessions, { recursive: true });
  writeFileSync(
    join(sessions, key + ".json"),
    JSON.stringify({
      platform: "session",
      current_task: currentTask,
      current_run: null,
    }),
    "utf8",
  );
}

function loadPlugin() {
  const tools = [];
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
  });
  return { tools };
}

function planWithRequiredDdd(id, summary = "t8 ddd required path") {
  // Force required ddd via grill-with-docs fact
  return sbtdPlan(id, {
    task_summary: summary,
    facts: ["完整执行 grill-with-docs"],
  });
}

test("apply 注册 sbtd_spec 与 sbtd_tickets", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt"]);
  assert.equal(tools.length, 6);
  assert.equal(tools[3].name, SBTD_SPEC_TOOL_NAME);
  assert.equal(tools[4].name, SBTD_TICKETS_TOOL_NAME);
});

test("slugFromPointer strips .trellis/tasks/ and rejects invalid", () => {
  assert.equal(slugFromPointer(".trellis/tasks/09-09-demo"), "09-09-demo");
  assert.equal(slugFromPointer(".trellis/tasks/../escape"), null);
  assert.equal(slugFromPointer(".trellis/tasks/archive"), null);
  assert.equal(slugFromPointer("09-09-demo"), null);
  assert.equal(slugFromPointer(".trellis/tasks/foo/bar"), null);
});

test("Q1C: explicit task preferred over differing currentTask pointer", () => {
  const root = fixtureRoot("explicit-wins");
  withTrellis(root);
  writeSession(root, "sess", ".trellis/tasks/pointer-slug");
  const id = "t8-explicit-wins";
  planWithRequiredDdd(id);
  sbtdReview(id, { kind: "ddd", status: "confirmed", conclusions: "ok" });
  const result = sbtdSpec(id, {
    cwd: root,
    session_key: "sess",
    task: "explicit-slug",
    markdown: "# PRD explicit\n",
  }, { PATH: "" });
  assert.equal(result.mode, "written");
  assert.equal(result.artifact, "prd.md");
  assert.equal(result.slug, "explicit-slug");
  assert.equal(result.source, "explicit");
  assert.equal(
    readFileSync(join(root, ".trellis", "tasks", "explicit-slug", "prd.md"), "utf8"),
    "# PRD explicit\n",
  );
  assert.equal(
    existsSync(join(root, ".trellis", "tasks", "pointer-slug", "prd.md")),
    false,
  );
});

test("Q1C: no explicit task + ok pointer => write under derived slug", () => {
  const root = fixtureRoot("from-pointer");
  withTrellis(root);
  writeSession(root, "sess", ".trellis/tasks/09-09-demo");
  const id = "t8-from-pointer";
  sbtdPlan(id, { task_summary: "hello pointer write" });
  const result = sbtdTickets(id, {
    cwd: root,
    session_key: "sess",
    markdown: "# slices\n",
  }, { PATH: "" });
  assert.equal(result.mode, "written");
  assert.equal(result.artifact, "implement.md");
  assert.equal(result.slug, "09-09-demo");
  assert.equal(result.source, "pointer");
  assert.equal(
    readFileSync(
      join(root, ".trellis", "tasks", "09-09-demo", "implement.md"),
      "utf8",
    ),
    "# slices\n",
  );
});

test("Q6A: invalid/missing pointer + no explicit => draft, no disk, no throw", () => {
  const root = fixtureRoot("no-path");
  withTrellis(root);
  const id = "t8-no-path";
  sbtdPlan(id, { task_summary: "hello no path" });
  const body = "# draft body\n";
  const result = sbtdSpec(id, {
    cwd: root,
    markdown: body,
  }, { PATH: "" });
  assert.equal(result.mode, "draft");
  assert.equal(result.ok, true);
  assert.equal(result.markdown, body);
  assert.equal(result.slug, null);
  assert.match(result.note, /Undetermined task path/);
  assert.equal(existsSync(join(root, ".trellis", "tasks")), false);
  assert.equal(existsSync(join(root, "docs")), false);
});

test("Q6A: invalid pointer form => draft", () => {
  const root = fixtureRoot("bad-pointer");
  withTrellis(root);
  writeSession(root, "sess", "not-a-pointer");
  const id = "t8-bad-pointer";
  sbtdPlan(id, { task_summary: "hello bad pointer" });
  const result = sbtdSpec(id, {
    cwd: root,
    session_key: "sess",
    markdown: "# x\n",
  }, { PATH: "" });
  assert.equal(result.mode, "draft");
  assert.match(result.note, /invalid-pointer|Undetermined/);
  assert.equal(existsSync(join(root, ".trellis", "tasks")), false);
});

test("Q3A: exists=false => draft; never docs/; cliOnPath irrelevant", () => {
  const root = fixtureRoot("no-trellis");
  mkdirSync(join(root, "docs"), { recursive: true });
  writeFileSync(join(root, "docs", "keep.md"), "keep\n", "utf8");
  const id = "t8-no-trellis";
  sbtdPlan(id, { task_summary: "hello no trellis" });
  const result = sbtdSpec(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# draft\n",
  }, { PATH: "/usr/bin" });
  assert.equal(result.mode, "draft");
  assert.equal(result.detect.exists, false);
  assert.match(result.note, /detect\.exists=false|No \.trellis/);
  assert.equal(existsSync(join(root, ".trellis")), false);
  assert.equal(readFileSync(join(root, "docs", "keep.md"), "utf8"), "keep\n");
  assert.equal(existsSync(join(root, "docs", "prd.md")), false);
  assert.deepEqual(readdirSync(join(root, "docs")), ["keep.md"]);
});

test("Q3A: exists=true + cliOnPath=false still writes", () => {
  const root = fixtureRoot("no-cli-write");
  withTrellis(root);
  const id = "t8-no-cli";
  sbtdPlan(id, { task_summary: "hello no cli" });
  const result = sbtdSpec(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# prd\n",
  }, { PATH: "", Path: "" });
  assert.equal(result.mode, "written");
  assert.equal(result.detect.exists, true);
  assert.equal(result.detect.cliOnPath, false);
  assert.equal(
    readFileSync(join(root, ".trellis", "tasks", "09-09-demo", "prd.md"), "utf8"),
    "# prd\n",
  );
});

test("Q2A: required ddd + unconfirmed => blocked, no write", () => {
  const root = fixtureRoot("ddd-block");
  withTrellis(root);
  const id = "t8-ddd-block";
  planWithRequiredDdd(id);
  assert.equal(getSession(id).plan.gates.ddd.requirement, "required");
  // no sbtd_review confirmed
  const result = sbtdSpec(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# should not write\n",
  }, { PATH: "" });
  assert.equal(result.mode, "blocked");
  assert.equal(result.ok, false);
  assert.equal(result.blocked.kind, "ddd-unconfirmed");
  assert.equal(result.blocked.suggestPrd, false);
  assert.equal(result.blocked.suggestImplement, false);
  assert.equal(existsSync(join(root, ".trellis", "tasks", "09-09-demo")), false);
});

test("Q2A: on-demand/absent ddd allows write", () => {
  const root = fixtureRoot("ddd-ondemand");
  withTrellis(root);
  const id = "t8-ddd-ondemand";
  sbtdPlan(id, { task_summary: "hello world plain" });
  assert.equal(getSession(id).plan.gates.ddd.requirement, "on-demand");
  const result = sbtdTickets(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# tickets\n",
  }, { PATH: "" });
  assert.equal(result.mode, "written");
  assert.equal(result.blocked, undefined);
  assert.equal(
    readFileSync(
      join(root, ".trellis", "tasks", "09-09-demo", "implement.md"),
      "utf8",
    ),
    "# tickets\n",
  );
});

test("Q2A: required ddd + confirmed allows write", () => {
  const root = fixtureRoot("ddd-ok");
  withTrellis(root);
  const id = "t8-ddd-ok";
  planWithRequiredDdd(id);
  sbtdReview(id, { kind: "ddd", status: "confirmed", conclusions: "locked" });
  const result = sbtdSpec(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# confirmed prd\n",
  }, { PATH: "" });
  assert.equal(result.mode, "written");
  assert.equal(result.blocked, undefined);
});

test("Q4A: sbtd_spec writes only prd.md; sbtd_tickets only implement.md", () => {
  const root = fixtureRoot("artifacts");
  withTrellis(root);
  const id = "t8-artifacts";
  sbtdPlan(id, { task_summary: "hello artifacts" });
  const spec = sbtdSpec(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# PRD\n",
  }, { PATH: "" });
  assert.equal(spec.artifact, "prd.md");
  assert.equal(spec.mode, "written");
  const tickets = sbtdTickets(id, {
    cwd: root,
    task: "09-09-demo",
    markdown: "# IMP\n",
  }, { PATH: "" });
  assert.equal(tickets.artifact, "implement.md");
  assert.equal(tickets.mode, "written");
  const taskDir = join(root, ".trellis", "tasks", "09-09-demo");
  assert.deepEqual(readdirSync(taskDir).sort(), ["implement.md", "prd.md"]);
  assert.equal(existsSync(join(taskDir, "design.md")), false);
  assert.equal(existsSync(join(root, ".trellis", "tasks", "child")), false);
});

test("empty markdown/body rejects before write and preserves existing artifact", () => {
  const root = fixtureRoot("empty-body");
  withTrellis(root);
  const taskDir = join(root, ".trellis", "tasks", "09-09-demo");
  mkdirSync(taskDir, { recursive: true });
  const existing = "# keep me\n";
  writeFileSync(join(taskDir, "prd.md"), existing, "utf8");
  writeFileSync(join(taskDir, "implement.md"), "# keep tickets\n", "utf8");
  const id = "t8-empty-body";
  sbtdPlan(id, { task_summary: "hello empty body guard" });

  assert.throws(
    () =>
      sbtdSpec(
        id,
        { cwd: root, task: "09-09-demo" },
        { PATH: "" },
      ),
    /markdown\/body must be a non-empty string/,
  );
  assert.throws(
    () =>
      sbtdSpec(
        id,
        { cwd: root, task: "09-09-demo", markdown: "   \n\t  " },
        { PATH: "" },
      ),
    /markdown\/body must be a non-empty string/,
  );
  assert.throws(
    () =>
      sbtdTickets(
        id,
        { cwd: root, task: "09-09-demo", body: "" },
        { PATH: "" },
      ),
    /markdown\/body must be a non-empty string/,
  );

  assert.equal(readFileSync(join(taskDir, "prd.md"), "utf8"), existing);
  assert.equal(
    readFileSync(join(taskDir, "implement.md"), "utf8"),
    "# keep tickets\n",
  );
});

test("host pin unchanged in package.json", () => {
  const pkg = JSON.parse(
    readFileSync(
      join(new URL("..", import.meta.url).pathname, "package.json"),
      "utf8",
    ),
  );
  assert.equal(pkg.peerDependencies["@deepseek-ai/dsh"], "0.1.1-rc.2");
});
