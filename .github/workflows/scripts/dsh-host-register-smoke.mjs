import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

const require = createRequire(join(process.cwd(), "package.json"));
const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));
const importPinned = (fromDsh, specifier) =>
  import(pathToFileURL(fromDsh.resolve(specifier)).href);
const assertNoTypeArrays = (schema) => {
  for (const prop of Object.values(schema.properties ?? {})) {
    if (prop.type !== undefined) assert.equal(Array.isArray(prop.type), false);
  }
};

const pluginPkgPath = require.resolve("@kunolu/dsh-sbtd/package.json");
const pluginPkg = readJson(pluginPkgPath);
const dshPkgPath = require.resolve("@deepseek-ai/dsh/package.json");
const dshPkg = readJson(dshPkgPath);
if (process.env.DSH_PIN_SMOKE === "1") {
  assert.equal(pluginPkg.version, "0.1.0-rc.2");
  assert.equal(dshPkg.version, "0.1.1-rc.2");
  assert.equal(pluginPkg.peerDependencies["@deepseek-ai/dsh"], "0.1.1-rc.2");
} else {
  assert.equal(dshPkg.version, process.env.DSH_VERSION);
}
const fromDsh = createRequire(dshPkgPath);
if (process.env.DSH_PIN_SMOKE === "1") {
  assert.equal(readJson(fromDsh.resolve("@deepseek-ai/dsh-tools/package.json")).version, "0.1.1-rc.2");
}
const pluginRoot = dirname(pluginPkgPath);
const [{ Context }, { default: SystemPrompt }, { default: ToolRuntime }, { default: CommandRuntime }, plugin] =
  await Promise.all([
    importPinned(fromDsh, "@deepseek-ai/cordis"),
    importPinned(fromDsh, "@deepseek-ai/dsh-system-prompt"),
    importPinned(fromDsh, "@deepseek-ai/dsh-tools"),
    importPinned(fromDsh, "@deepseek-ai/dsh-commands"),
    import(pathToFileURL(join(pluginRoot, "dist/index.js")).href),
  ]);
const ctx = new Context();
await ctx.plugin(SystemPrompt);
await ctx.plugin(ToolRuntime);
await ctx.plugin(CommandRuntime);
await ctx.plugin({ name: plugin.name, inject: [...plugin.inject], apply: plugin.apply });
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
console.log("register smoke ok", dshPkg.version, pluginPkg.version);
