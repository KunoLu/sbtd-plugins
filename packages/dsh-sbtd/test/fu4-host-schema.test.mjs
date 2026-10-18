import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { isSbtdSource } from "../dist/hooks.js";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const requireFromPkg = createRequire(join(pkgRoot, "package.json"));

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function importPinned(fromDsh, specifier) {
  return import(pathToFileURL(fromDsh.resolve(specifier)).href);
}

function assertNoTypeArrays(schema) {
  for (const prop of Object.values(schema.properties ?? {})) {
    if (prop.type !== undefined) {
      assert.equal(Array.isArray(prop.type), false);
    }
  }
}

async function loadHostAndPlugin() {
  const dshPkgPath = requireFromPkg.resolve("@deepseek-ai/dsh/package.json");
  const fromDsh = createRequire(dshPkgPath);
  const [{ Context }, { default: SystemPrompt }, { default: ToolRuntime }, { default: CommandRuntime }, plugin] =
    await Promise.all([
      importPinned(fromDsh, "@deepseek-ai/cordis"),
      importPinned(fromDsh, "@deepseek-ai/dsh-system-prompt"),
      importPinned(fromDsh, "@deepseek-ai/dsh-tools"),
      importPinned(fromDsh, "@deepseek-ai/dsh-commands"),
      import(pathToFileURL(join(pkgRoot, "dist/index.js")).href),
    ]);

  const ctx = new Context();
  await ctx.plugin(SystemPrompt);
  await ctx.plugin(ToolRuntime);
  await ctx.plugin(CommandRuntime);
  await ctx.plugin({
    name: plugin.name,
    inject: [...plugin.inject],
    apply: plugin.apply,
  });
  return { ctx, plugin };
}

test("pinned dsh@0.2.0-rc.2 Cordis register/load 接受 clarify/spec/tickets output.schema", async () => {
  const pluginPkg = readJson(join(pkgRoot, "package.json"));
  assert.equal(pluginPkg.version, "0.2.0-rc.1");
  assert.equal(pluginPkg.peerDependencies["@deepseek-ai/dsh"], ">=0.2.0-rc.2 <0.3.0-0");
  assert.equal(pluginPkg.engines.dsh, ">=0.2.0-rc.2 <0.3.0-0");
  assert.equal(pluginPkg.devDependencies["@deepseek-ai/dsh"], "0.2.0-rc.2");

  const dshPkgPath = requireFromPkg.resolve("@deepseek-ai/dsh/package.json");
  const dshPkg = readJson(dshPkgPath);
  assert.equal(dshPkg.name, "@deepseek-ai/dsh");
  assert.equal(dshPkg.version, "0.2.0-rc.2");

  const fromDsh = createRequire(dshPkgPath);
  const toolsPkg = readJson(fromDsh.resolve("@deepseek-ai/dsh-tools/package.json"));
  assert.equal(toolsPkg.version, "0.2.0-rc.2");

  const { ctx } = await loadHostAndPlugin();

  const clarify = ctx.tools.get("sbtd_clarify");
  const spec = ctx.tools.get("sbtd_spec");
  const tickets = ctx.tools.get("sbtd_tickets");
  assert.ok(clarify, "sbtd_clarify");
  assert.ok(spec, "sbtd_spec");
  assert.ok(tickets, "sbtd_tickets");

  assert.equal(clarify.output.schema.properties.mode.type, "string");
  assert.equal(clarify.output.schema.properties.currentQuestion.type, "string");
  // Draft-only schema (R1 Q2 A): no slug/source; the plugin writes no task files.
  assert.equal(spec.output.schema.properties.mode.type, "string");
  assert.equal(spec.output.schema.properties.artifact.type, "string");
  assert.equal(tickets.output.schema.properties.mode.type, "string");
  assert.equal(tickets.output.schema.properties.artifact.type, "string");

  assertNoTypeArrays(clarify.output.schema);
  assertNoTypeArrays(spec.output.schema);
  assertNoTypeArrays(tickets.output.schema);
});

test("pinned dsh@0.2.0-rc.2 真实宿主 pre-step：notice kind=dsh-sbtd 且保留 startsRequestSeries", async () => {
  const { ctx } = await loadHostAndPlugin();

  const decision = await ctx.waterfall(
    "agent/pre-step",
    {
      agent: { id: "fu4-prestep" },
      messages: [
        { content: [{ type: "text", text: "实现这个功能，改 src/ 生产代码" }] },
      ],
    },
    async () => ({ kind: "enter", messages: [], startsRequestSeries: true }),
  );

  assert.equal(decision.kind, "enter");
  assert.equal(decision.startsRequestSeries, true);
  const notice = decision.messages.at(-1);
  assert.ok(isSbtdSource(notice.source), "notice recognized as dsh-sbtd source");
  assert.equal(notice.source.kind, "dsh-sbtd");
  assert.equal(notice.source.form, "notice");
  assert.match(notice.source.summary, /sbtd_plan/);
});
