import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { apply } from "../dist/index.js";
import { sbtdClarify } from "../dist/tools/clarify.js";
import { sbtdPlan } from "../dist/tools/plan.js";
import { sbtdReview } from "../dist/tools/review.js";
import { createSpecTool, sbtdSpec } from "../dist/tools/spec.js";
import { createTicketsTool, sbtdTickets } from "../dist/tools/tickets.js";

for (const [name, run, create] of [
  ["spec", sbtdSpec, createSpecTool],
  ["tickets", sbtdTickets, createTicketsTool],
]) {
  test(`${name}: draft-only even with a writable legacy task pointer; existing files untouched`, () => {
    const root = mkdtempSync(join(tmpdir(), `dsh-sbtd-t8-${name}-`));
    const task = join(root, ".trellis", "tasks", "demo");
    const sessions = join(root, ".trellis", ".runtime", "sessions");
    mkdirSync(task, { recursive: true });
    mkdirSync(sessions, { recursive: true });
    mkdirSync(join(root, "docs", "prd"), { recursive: true });
    writeFileSync(join(sessions, "session.json"), JSON.stringify({ current_task: ".trellis/tasks/demo" }));
    writeFileSync(join(task, "prd.md"), "user-owned PRD\n");
    writeFileSync(join(task, "implement.md"), "user-owned implementation\n");
    const files = readdirSync(root, { recursive: true, withFileTypes: true })
      .filter((entry) => entry.isFile())
      .map((entry) => join(entry.parentPath ?? entry.path, entry.name));
    const before = files.map((path) => [path, readFileSync(path, "utf8")]);
    const tree = readdirSync(root, { recursive: true }).sort();
    const result = run(`t8-draft-${name}`, {
      markdown: "# Requested draft\n",
      cwd: root,
      task: "demo",
      session_key: "session",
    });
    assert.equal(result.mode, "draft");
    assert.equal(result.ok, true);
    assert.deepEqual(readdirSync(root, { recursive: true }).sort(), tree);
    for (const [path, content] of before) assert.equal(readFileSync(path, "utf8"), content);
  });

  test(`${name}: completed docs grill blocks until DDD confirmed in every mode`, async () => {
    for (const workflow_mode of ["strict", "default", "lite"]) {
      const id = `t8-ddd-${name}-${workflow_mode}`;
      sbtdPlan(id, { task_summary: `docs review ${name} ${workflow_mode}`, workflow_mode });
      sbtdClarify(id, { mode: "docs", question: "Q?" });
      sbtdClarify(id, { frontier_empty: true, user_confirmed: true });
      const tool = create();
      const exec = { agent: { id } };
      const blocked = await tool.execute({ markdown: "# Draft\n" }, exec);
      assert.equal(blocked.mode, "blocked");
      assert.equal(blocked.ok, false);
      assert.equal(blocked.blocked.kind, "ddd-unconfirmed");
      assert.equal(blocked.blocked.suggestPrd, false);
      assert.equal(blocked.blocked.suggestImplement, false);
      sbtdReview(id, { kind: "ddd", status: "confirmed" });
      assert.equal((await tool.execute({ markdown: "# Draft\n" }, exec)).mode, "draft");
      sbtdReview(id, { kind: "ddd", status: "blocked" });
      assert.equal((await tool.execute({ markdown: "# Draft\n" }, exec)).mode, "blocked");
    }
  });

  test(`${name}: missing and whitespace content rejected; explicit empty markdown cannot fall back to body`, () => {
    for (const input of [{}, { markdown: " \n\t" }, { body: "" }, { markdown: "", body: "# nonempty" }]) {
      assert.throws(() => run(`t8-empty-${name}`, input), /non-empty string/);
    }
  });
}

test("registered artifact tools retain separate session DDD state", async () => {
  const tools = [];
  apply({
    systemPrompt: { section() {} },
    tools: { register(tool) { tools.push(tool); } },
    on() {},
  });
  sbtdPlan("t8-registered-block", { task_summary: "grill spec", facts: ["完整执行 grill-with-docs"] });
  const tool = tools.find((entry) => entry.name === "sbtd_spec");
  assert.equal((await tool.execute({ body: "# Draft" }, { agent: { id: "t8-registered-block" } })).mode, "blocked");
  assert.equal((await tool.execute({ body: "# Draft" }, { agent: { id: "t8-registered-free" } })).mode, "draft");
});
