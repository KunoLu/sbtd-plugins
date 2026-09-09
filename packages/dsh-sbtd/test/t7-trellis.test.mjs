import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  currentTask,
  detect,
  readWorkflow,
  writeArtifact,
} from "../dist/backends/trellis.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t7-" + label + "-"));
}

function withTrellis(root, opts = {}) {
  mkdirSync(join(root, ".trellis"), { recursive: true });
  if (opts.workflow != null) {
    writeFileSync(join(root, ".trellis", "workflow.md"), opts.workflow, "utf8");
  }
}

test("detect: no .trellis => exists=false and does not throw", () => {
  const root = fixtureRoot("no-trellis");
  const result = detect(root, { ...process.env });
  assert.equal(result.exists, false);
  assert.equal(typeof result.cliOnPath, "boolean");
  assert.equal(result.workflowPresent, false);
});

test("detect: dir present, CLI absent => exists=true, cliOnPath=false", () => {
  const root = fixtureRoot("no-cli");
  withTrellis(root);
  const result = detect(root, { ...process.env, PATH: "", Path: "" });
  assert.equal(result.exists, true);
  assert.equal(result.cliOnPath, false);
  assert.equal(result.workflowPresent, false);
});
test("detect: workflowPresent independent", () => {
  const root = fixtureRoot("workflow");
  withTrellis(root, { workflow: "# wf\n" });
  const withWf = detect(root, { ...process.env, PATH: "" });
  assert.equal(withWf.exists, true);
  assert.equal(withWf.workflowPresent, true);
  assert.equal(withWf.cliOnPath, false);
  const root2 = fixtureRoot("no-workflow");
  withTrellis(root2);
  const noWf = detect(root2, { ...process.env, PATH: "" });
  assert.equal(noWf.exists, true);
  assert.equal(noWf.workflowPresent, false);
});

test("detect: does not throw when CLI present on host PATH", () => {
  const root = fixtureRoot("cli-yes");
  withTrellis(root);
  const result = detect(root, process.env);
  assert.equal(result.exists, true);
  assert.equal(typeof result.cliOnPath, "boolean");
});

test("readWorkflow: returns file bytes from disk", () => {
  const root = fixtureRoot("read-wf");
  withTrellis(root, { workflow: "hello-workflow\n" });
  const result = readWorkflow(root);
  assert.equal(result.ok, true);
  if (result.ok) assert.equal(result.content, "hello-workflow\n");
});

test("readWorkflow: missing trellis/workflow => structured failure", () => {
  const empty = fixtureRoot("rw-empty");
  assert.deepEqual(readWorkflow(empty), { ok: false, reason: "missing-trellis" });
  const root = fixtureRoot("rw-no-wf");
  withTrellis(root);
  assert.deepEqual(readWorkflow(root), { ok: false, reason: "missing-workflow" });
});

test("currentTask: no session => structured; ignores in_progress dirs", () => {
  const root = fixtureRoot("ct-none");
  withTrellis(root);
  mkdirSync(join(root, ".trellis", "tasks", "09-01-other-in-progress"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "tasks", "09-01-other-in-progress", "task.json"),
    JSON.stringify({ status: "in_progress", id: "other" }),
    "utf8",
  );
  const env = { PATH: process.env.PATH };
  const result = currentTask(root, null, env);
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.reason, "no-session");
});

test("currentTask: session pointer; empty pointer structured; ignores decoy", () => {
  const root = fixtureRoot("ct-ptr");
  withTrellis(root);
  const sessions = join(root, ".trellis", ".runtime", "sessions");
  mkdirSync(sessions, { recursive: true });
  writeFileSync(
    join(sessions, "test-session.json"),
    JSON.stringify({ platform: "session", current_task: ".trellis/tasks/09-09-demo", current_run: null }),
    "utf8",
  );
  mkdirSync(join(root, ".trellis", "tasks", "decoy-in-progress"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "tasks", "decoy-in-progress", "task.json"),
    JSON.stringify({ status: "in_progress" }),
    "utf8",
  );
  const hit = currentTask(root, "test-session", {});
  assert.equal(hit.ok, true);
  if (hit.ok) assert.equal(hit.task, ".trellis/tasks/09-09-demo");
  writeFileSync(join(sessions, "empty-session.json"), JSON.stringify({ current_task: null }), "utf8");
  const miss = currentTask(root, "empty-session", {});
  assert.equal(miss.ok, false);
  if (!miss.ok) assert.equal(miss.reason, "no-current-task");
});

test("currentTask: DSH_SESSION_ID maps to dsh_<id> key", () => {
  const root = fixtureRoot("ct-dsh");
  withTrellis(root);
  const sessions = join(root, ".trellis", ".runtime", "sessions");
  mkdirSync(sessions, { recursive: true });
  writeFileSync(
    join(sessions, "dsh_abc-123.json"),
    JSON.stringify({ current_task: ".trellis/tasks/from-dsh" }),
    "utf8",
  );
  const result = currentTask(root, null, { DSH_SESSION_ID: "abc-123" });
  assert.equal(result.ok, true);
  if (result.ok) assert.equal(result.task, ".trellis/tasks/from-dsh");
});

test("currentTask: missing trellis => structured", () => {
  const root = fixtureRoot("ct-missing");
  assert.deepEqual(currentTask(root, "any", {}), { ok: false, reason: "missing-trellis" });
});

test("writeArtifact: accepts whitelist names under tasks/<slug>/", () => {
  const root = fixtureRoot("wa-ok");
  withTrellis(root);
  for (const name of ["prd.md", "design.md", "implement.md"]) {
    const result = writeArtifact(root, "09-09-t7-demo", name, "# " + name + "\n");
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(readFileSync(result.path, "utf8"), "# " + name + "\n");
      assert.ok(result.path.includes(join(".trellis", "tasks", "09-09-t7-demo", name)));
    }
  }
});

test("writeArtifact: sandbox rejects .. / archive / other names / absolute", () => {
  const root = fixtureRoot("wa-bad");
  withTrellis(root);
  assert.throws(() => writeArtifact(root, "../escape", "prd.md", "x"), /rejected|escape|sandbox/i);
  assert.throws(() => writeArtifact(root, "archive", "prd.md", "x"), /archive|rejected/i);
  assert.throws(() => writeArtifact(root, "archive/foo", "prd.md", "x"), /rejected|escape/i);
  assert.throws(() => writeArtifact(root, "/abs/path", "prd.md", "x"), /rejected|escape/i);
  assert.throws(() => writeArtifact(root, "09-09-ok", "research.md", "x"), /whitelist|rejected/i);
  assert.throws(() => writeArtifact(root, "09-09-ok", "implement.jsonl", "x"), /whitelist|rejected/i);
  assert.throws(() => writeArtifact(root, "09-09-ok", "../prd.md", "x"), /whitelist|rejected/i);
});

test("writeArtifact: missing trellis => structured failure (no throw)", () => {
  const root = fixtureRoot("wa-missing");
  assert.deepEqual(writeArtifact(root, "09-09-ok", "prd.md", "body"), {
    ok: false,
    reason: "missing-trellis",
  });
});

