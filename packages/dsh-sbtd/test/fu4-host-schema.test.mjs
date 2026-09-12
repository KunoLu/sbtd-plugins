import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

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

test("pinned dsh@0.1.1-rc.2 Cordis register/load 接受 clarify/spec/tickets output.schema", async () => {
  const pluginPkg = readJson(join(pkgRoot, "package.json"));
  assert.equal(pluginPkg.version, "0.1.0-rc.1");
  assert.equal(pluginPkg.peerDependencies["@deepseek-ai/dsh"], "0.1.1-rc.2");

  const dshPkgPath = requireFromPkg.resolve("@deepseek-ai/dsh/package.json");
  const dshPkg = readJson(dshPkgPath);
  assert.equal(dshPkg.name, "@deepseek-ai/dsh");
  assert.equal(dshPkg.version, "0.1.1-rc.2");

  const fromDsh = createRequire(dshPkgPath);
  const toolsPkg = readJson(fromDsh.resolve("@deepseek-ai/dsh-tools/package.json"));
  assert.equal(toolsPkg.version, "0.1.1-rc.2");

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

  const clarify = ctx.tools.get("sbtd_clarify");
  const spec = ctx.tools.get("sbtd_spec");
  const tickets = ctx.tools.get("sbtd_tickets");
  assert.ok(clarify, "sbtd_clarify");
  assert.ok(spec, "sbtd_spec");
  assert.ok(tickets, "sbtd_tickets");

  assert.equal(clarify.output.schema.properties.mode.type, "string");
  assert.equal(clarify.output.schema.properties.currentQuestion.type, "string");
  assert.equal(spec.output.schema.properties.slug.type, "string");
  assert.equal(spec.output.schema.properties.source.type, "string");
  assert.equal(tickets.output.schema.properties.slug.type, "string");
  assert.equal(tickets.output.schema.properties.source.type, "string");

  assertNoTypeArrays(clarify.output.schema);
  assertNoTypeArrays(spec.output.schema);
  assertNoTypeArrays(tickets.output.schema);
});
