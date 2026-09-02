import assert from "node:assert/strict";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { pathToFileURL, fileURLToPath } from "node:url";
import { getSession, restore, serialize } from "../dist/state.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const stateHref = pathToFileURL(join(pkgRoot, "dist/state.js")).href;

const samplePlan = {
  taskId: "dsh-sbtd-t1",
  summary: "section + state",
  gates: {
    ddd: { requirement: "on-demand", state: "not-required" },
    ddia: { requirement: "required", state: "planned" },
    legacy: { requirement: "required", state: "planned" },
    refactor: { requirement: "required", state: "planned" },
    release: { requirement: "required", state: "planned" },
  },
};

test("未知 session id 返回隔离的 {validate:{}}", () => {
  const a = getSession("unknown-a");
  const b = getSession("unknown-b");
  assert.deepEqual(a, { validate: {} });
  assert.deepEqual(b, { validate: {} });
  assert.notEqual(a, b);
  a.validate.pre = "done";
  assert.equal(b.validate.pre, undefined);
});

test("Map 按 sessionId 隔离", () => {
  const one = getSession("sess-1");
  const two = getSession("sess-2");
  one.plan = samplePlan;
  two.maestro = { missing: ["java"] };
  assert.equal(getSession("sess-1").plan?.taskId, "dsh-sbtd-t1");
  assert.equal(getSession("sess-2").plan, undefined);
  assert.deepEqual(getSession("sess-2").maestro?.missing, ["java"]);
  assert.equal(getSession("sess-1").maestro, undefined);
});

test("serialize 至少包含 plan 与 maestro.missing 并可 roundtrip", () => {
  const id = "sess-roundtrip";
  const session = getSession(id);
  session.plan = samplePlan;
  session.maestro = { java: "21", missing: ["cli", "device"] };
  session.validate.pre = "skipped";

  const snapshot = serialize(id);
  assert.deepEqual(snapshot.plan, samplePlan);
  assert.deepEqual(snapshot.maestro, { missing: ["cli", "device"] });
  snapshot.maestro.missing.push("app");
  assert.deepEqual(getSession(id).maestro?.missing, ["cli", "device"]);

  restore("sess-restored", snapshot);
  const restored = getSession("sess-restored");
  assert.deepEqual(restored.plan, samplePlan);
  assert.deepEqual(restored.maestro?.missing, ["cli", "device", "app"]);
  assert.deepEqual(serialize("never-serialized"), {});
});

test("serialize/restore 克隆 plan 与 nested gates，变异不串写", () => {
  const live = getSession("sess-clone-live");
  live.plan = samplePlan;

  const snapshot = serialize("sess-clone-live");
  assert.ok(snapshot.plan);
  assert.notEqual(snapshot.plan, live.plan);
  assert.notEqual(snapshot.plan.gates, live.plan.gates);
  assert.notEqual(snapshot.plan.gates.ddd, live.plan.gates.ddd);

  snapshot.plan.summary = "mutated-handoff";
  snapshot.plan.gates.ddd.state = "passed";
  snapshot.plan.gates.ddd.fact = "handoff";
  assert.equal(live.plan.summary, "section + state");
  assert.equal(live.plan.gates.ddd.state, "not-required");
  assert.equal(live.plan.gates.ddd.fact, undefined);

  restore("sess-clone-restored", snapshot);
  const restored = getSession("sess-clone-restored").plan;
  assert.ok(restored);
  assert.notEqual(restored, snapshot.plan);
  assert.notEqual(restored.gates.ddd, snapshot.plan.gates.ddd);
  restored.summary = "mutated-live";
  restored.gates.legacy.state = "blocked";
  assert.equal(snapshot.plan.summary, "mutated-handoff");
  assert.equal(snapshot.plan.gates.legacy.state, "planned");
});

test("重启后 Map 丢失，但 re-import 后 API 仍可测", async () => {
  const live = await import(`${stateHref}?boot=1`);
  live.getSession("ephemeral").plan = samplePlan;
  assert.equal(live.getSession("ephemeral").plan?.taskId, "dsh-sbtd-t1");

  const restarted = await import(`${stateHref}?boot=2`);
  assert.deepEqual(restarted.getSession("ephemeral"), { validate: {} });
  restarted.getSession("ephemeral").maestro = { missing: ["java"] };
  assert.deepEqual(restarted.serialize("ephemeral"), {
    maestro: { missing: ["java"] },
  });
});
