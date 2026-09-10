import assert from "node:assert/strict";
import { test } from "node:test";
import {
  FORBIDDEN_MODEL_KEYS,
  defaultDetectCli,
  defaultDetectDevice,
  defaultDetectJava,
  modelSchemaForbidsTrustHandles,
  pickModelInput,
  preflight,
} from "../dist/backends/maestro.js";
import { getSession, serialize } from "../dist/state.js";

function okProbes(overrides = {}) {
  return {
    detectJava: async () => ({ ok: true, version: "21", detail: "21.0.2" }),
    detectCli: async () => ({ ok: true, version: "1.39.0", detail: "1.39.0" }),
    detectDevice: async () => ({
      ok: true,
      class: "emulator",
      detail: "stub emulator",
    }),
    appInstalled: true,
    appEnv: "staging://api",
    appId: "com.example.app",
    accounts: "qa@example.com",
    ...overrides,
  };
}

test("preflight: all facts ready => ok + empty missing (Q1A)", async () => {
  const result = await preflight(okProbes({ skipSessionWrite: true }));
  assert.equal(result.lastPreflight, "ok");
  assert.deepEqual(result.missing, []);
  assert.match(result.guidance, /ok/i);
  assert.equal(result.probes?.java?.ok, true);
  assert.equal(result.probes?.cli?.ok, true);
  assert.equal(result.probes?.device?.ok, true);
  assert.equal(result.probes?.device?.class, "emulator");
});

test("preflight: missing live java/cli/device => blocked + missing tokens", async () => {
  const result = await preflight(
    okProbes({
      skipSessionWrite: true,
      detectJava: async () => ({ ok: false, detail: "no java" }),
      detectCli: async () => ({ ok: false, detail: "no maestro" }),
      detectDevice: async () => ({ ok: false, detail: "no device" }),
    }),
  );
  assert.equal(result.lastPreflight, "blocked");
  assert.ok(result.missing.includes("java"));
  assert.ok(result.missing.includes("cli"));
  assert.ok(result.missing.includes("device"));
  assert.match(result.guidance, /java --version/);
  assert.match(result.guidance, /maestro --version/);
  // Guidance may warn against `maestro test`; it must not prescribe running it.
  assert.doesNotMatch(result.guidance, /(?<!never run `)maestro test(?!`)/);
  assert.match(result.guidance, /never run `maestro test`/);
});

test("preflight: missing declared app/appEnv/identity => blocked (Q1A)", async () => {
  const result = await preflight({
    skipSessionWrite: true,
    detectJava: async () => ({ ok: true, version: "17" }),
    detectCli: async () => ({ ok: true, version: "1.0.0" }),
    detectDevice: async () => ({ ok: true, class: "sim" }),
    // no appInstalled / appEnv / appId / accounts
  });
  assert.equal(result.lastPreflight, "blocked");
  assert.ok(result.missing.includes("app"));
  assert.ok(result.missing.includes("appEnv"));
  assert.ok(result.missing.includes("identity"));
  assert.equal(result.missing.includes("java"), false);
});

test("preflight: missing app and/or device => guidance mentions app AND virtual device", async () => {
  const both = await preflight(
    okProbes({
      skipSessionWrite: true,
      appInstalled: false,
      detectDevice: async () => ({ ok: false, detail: "gone" }),
    }),
  );
  assert.equal(both.lastPreflight, "blocked");
  assert.match(both.guidance, /app/i);
  assert.match(both.guidance, /virtual device/i);

  const appOnly = await preflight(
    okProbes({
      skipSessionWrite: true,
      appInstalled: false,
    }),
  );
  assert.ok(appOnly.missing.includes("app"));
  assert.match(appOnly.guidance, /app/i);
  assert.match(appOnly.guidance, /virtual device/i);

  const deviceOnly = await preflight(
    okProbes({
      skipSessionWrite: true,
      detectDevice: async () => ({ ok: false }),
    }),
  );
  assert.ok(deviceOnly.missing.includes("device"));
  assert.match(deviceOnly.guidance, /app/i);
  assert.match(deviceOnly.guidance, /virtual device/i);
});

test("preflight: cloud declaration records device class without upload/run (Q6A)", async () => {
  let sawOptions = null;
  const result = await preflight(
    okProbes({
      skipSessionWrite: true,
      deviceClass: "cloud",
      detectDevice: async (opts) => {
        sawOptions = opts;
        // Mirror defaultDetectDevice cloud branch contract for the stub.
        return {
          ok: true,
          class: "cloud",
          detail: "cloud device class declared (no cloud run/upload in T12)",
        };
      },
    }),
  );
  assert.equal(result.lastPreflight, "ok");
  assert.equal(result.probes?.device?.class, "cloud");
  assert.match(result.probes?.device?.detail ?? "", /no cloud run\/upload/i);
  assert.equal(sawOptions?.deviceClass, "cloud");
});

test("defaultDetectDevice: cloud declaration ok without spawning maestro test", () => {
  const probe = defaultDetectDevice({ deviceClass: "cloud" });
  assert.equal(probe.ok, true);
  assert.equal(probe.class, "cloud");
  assert.match(probe.detail ?? "", /no cloud run\/upload/i);
});

test("defaultDetectDevice: declared sim/emulator/usb equally valid (Q6A)", () => {
  assert.equal(defaultDetectDevice({ deviceClass: "sim" }).class, "sim");
  assert.equal(
    defaultDetectDevice({ deviceClass: "emulator" }).class,
    "emulator",
  );
  assert.equal(defaultDetectDevice({ deviceClass: "usb" }).class, "usb");
});

test("pickModelInput: platform hint only; rejects T10 trust keys (Q4A)", () => {
  assert.deepEqual(pickModelInput({ platform: "ios" }), { platform: "ios" });
  assert.deepEqual(pickModelInput({ platform: "android" }), {
    platform: "android",
  });
  assert.deepEqual(pickModelInput({}), {});
  assert.deepEqual(pickModelInput({ extra: 1 }), {});

  for (const key of FORBIDDEN_MODEL_KEYS) {
    assert.throws(
      () => pickModelInput({ [key]: "/tmp", platform: "ios" }),
      /forbids trust handle/,
    );
  }
  assert.throws(() => pickModelInput({ platform: "web" }), /platform hint/);
});

test("modelSchemaForbidsTrustHandles: public schema must omit T10 keys", () => {
  assert.equal(
    modelSchemaForbidsTrustHandles({ platform: { type: "string" } }),
    true,
  );
  assert.equal(
    modelSchemaForbidsTrustHandles({
      platform: { type: "string" },
      cwd: { type: "string" },
    }),
    false,
  );
  for (const key of FORBIDDEN_MODEL_KEYS) {
    assert.equal(modelSchemaForbidsTrustHandles({ [key]: {} }), false);
  }
});

test("preflight: host cwd inject ok; never invents declared facts", async () => {
  const result = await preflight({
    cwd: "/host/injected/cwd",
    platform: "android",
    skipSessionWrite: true,
    detectJava: async () => ({ ok: true, version: "21" }),
    detectCli: async () => ({ ok: true, version: "1.2.3" }),
    detectDevice: async () => ({ ok: true, class: "emulator" }),
    // intentionally omit appInstalled/appEnv/identity
  });
  assert.equal(result.lastPreflight, "blocked");
  assert.ok(result.missing.includes("app"));
  assert.ok(result.missing.includes("appEnv"));
  assert.ok(result.missing.includes("identity"));
  // Must not invent identity from platform hint alone.
  assert.equal(result.missing.includes("java"), false);
});

test("preflight: writes session.maestro lastPreflight+missing; handoff still missing-only (Q3A)", async () => {
  const sid = "t12-maestro-session-write";
  const session = getSession(sid);
  delete session.maestro;

  const result = await preflight(
    okProbes({
      sessionId: sid,
      appInstalled: false,
      accounts: false,
    }),
  );
  assert.equal(result.lastPreflight, "blocked");
  assert.ok(result.missing.includes("app"));

  const live = getSession(sid).maestro;
  assert.ok(live);
  assert.equal(live.lastPreflight, "blocked");
  assert.deepEqual(live.missing, result.missing);
  assert.equal(live.java, "21");
  assert.equal(live.cli, "1.39.0");
  assert.equal(live.device, "emulator");
  assert.equal(live.appInstalled, false);

  const snap = serialize(sid);
  assert.deepEqual(snap.maestro, { missing: result.missing });
  assert.equal(snap.maestro.lastPreflight, undefined);
  assert.equal(Object.keys(snap.maestro).join(","), "missing");
});

test("preflight: ok path writes session.maestro lastPreflight=ok", async () => {
  const sid = "t12-maestro-session-ok";
  delete getSession(sid).maestro;
  const result = await preflight(okProbes({ sessionId: sid }));
  assert.equal(result.lastPreflight, "ok");
  const live = getSession(sid).maestro;
  assert.equal(live?.lastPreflight, "ok");
  assert.deepEqual(live?.missing, []);
  assert.equal(live?.appInstalled, true);
  assert.equal(live?.appEnv, "staging://api");
  assert.deepEqual(serialize(sid).maestro, { missing: [] });
});

test("preflight: never throws when detect stubs throw", async () => {
  const result = await preflight({
    skipSessionWrite: true,
    detectJava: async () => {
      throw new Error("boom-java");
    },
  });
  assert.equal(result.lastPreflight, "blocked");
  assert.ok(Array.isArray(result.missing));
  assert.ok(result.missing.length > 0);
  assert.equal(typeof result.guidance, "string");
});

test("defaults exist and never throw for missing env", () => {
  assert.equal(typeof defaultDetectJava, "function");
  assert.equal(typeof defaultDetectCli, "function");
  const j = defaultDetectJava();
  const c = defaultDetectCli();
  assert.equal(typeof j.ok, "boolean");
  assert.equal(typeof c.ok, "boolean");
});

test("bundleId alias satisfies identity with accounts", async () => {
  const result = await preflight(
    okProbes({
      skipSessionWrite: true,
      appId: undefined,
      bundleId: "com.example.bundle",
      accounts: true,
    }),
  );
  assert.equal(result.lastPreflight, "ok");
  assert.deepEqual(result.missing, []);
});
