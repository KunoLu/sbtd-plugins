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
assert.equal(dshPkg.version, process.env.DSH_VERSION);
if (process.env.DSH_PIN_SMOKE === "1") {
  assert.ok(process.env.GITHUB_WORKSPACE, "GITHUB_WORKSPACE is required for pin smoke");
  const sourcePkg = readJson(
    join(process.env.GITHUB_WORKSPACE, "packages/dsh-sbtd/package.json"),
  );
  // Locked peer/engines range: docs/prd/dsh-sbtd-0.2.0-rc.1.md:17.
  const DSH_HOST_RANGE = ">=0.2.0-rc.2 <0.3.0-0";
  assert.equal(pluginPkg.version, sourcePkg.version);
  assert.equal(pluginPkg.peerDependencies["@deepseek-ai/dsh"], DSH_HOST_RANGE);
  assert.equal(pluginPkg.engines.dsh, DSH_HOST_RANGE);
  assert.equal(pluginPkg.peerDependencies["@deepseek-ai/dsh"], pluginPkg.engines.dsh);
}
const fromDsh = createRequire(dshPkgPath);
if (process.env.DSH_PIN_SMOKE === "1") {
  assert.equal(readJson(fromDsh.resolve("@deepseek-ai/dsh-tools/package.json")).version, process.env.DSH_VERSION);
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

// T0 (R1 Q6 A): nine tools + sbtd section + /sbtd command all register.
const TOOL_NAMES = [
  "sbtd_plan",
  "sbtd_review",
  "sbtd_clarify",
  "sbtd_spec",
  "sbtd_tickets",
  "sbtd_validate",
  "sbtd_lessons",
  "sbtd_bdd",
  "sbtd_e2e",
];
for (const toolName of TOOL_NAMES) {
  assert.ok(ctx.tools.get(toolName), toolName);
}
const assembly = await ctx.systemPrompt.assemble({});
assert.ok(
  assembly.sections.some((section) => section.name === "sbtd"),
  "sbtd section",
);
assert.ok(ctx.commands.find({ id: "register-smoke" }, "sbtd"), "/sbtd command");

const clarify = ctx.tools.get("sbtd_clarify");
const spec = ctx.tools.get("sbtd_spec");
const tickets = ctx.tools.get("sbtd_tickets");
assert.equal(clarify.output.schema.properties.mode.type, "string");
assert.equal(clarify.output.schema.properties.currentQuestion.type, "string");
// Draft-only schema (R1 Q2 A): mode/artifact, no slug/source.
assert.equal(spec.output.schema.properties.mode.type, "string");
assert.equal(spec.output.schema.properties.artifact.type, "string");
assert.equal(tickets.output.schema.properties.mode.type, "string");
assert.equal(tickets.output.schema.properties.artifact.type, "string");
assertNoTypeArrays(clarify.output.schema);
assertNoTypeArrays(spec.output.schema);
assertNoTypeArrays(tickets.output.schema);

// T0 (R1 Q6 A): drive agent/pre-step through the real host waterfall — the
// notice must carry the V4 producer kind dsh-sbtd and the enter decision must
// keep startsRequestSeries.
const { isSbtdSource } = await import(pathToFileURL(join(pluginRoot, "dist/hooks.js")).href);
const decision = await ctx.waterfall(
  "agent/pre-step",
  {
    agent: { id: "register-smoke" },
    messages: [
      { content: [{ type: "text", text: "实现这个功能，改 src/ 生产代码" }] },
    ],
  },
  async () => ({ kind: "enter", messages: [], startsRequestSeries: true }),
);
assert.equal(decision.kind, "enter");
assert.equal(decision.startsRequestSeries, true);
const notice = decision.messages.at(-1);
assert.ok(isSbtdSource(notice.source), "pre-step notice recognized as dsh-sbtd source");
assert.equal(notice.source.kind, "dsh-sbtd");
assert.equal(notice.source.form, "notice");
assert.match(notice.source.summary, /sbtd_plan/);

// T0 (R1 Q6 A): a production edit without a plan still asks.
const gate = await ctx.waterfall(
  "tools/pre-execute",
  {
    name: "write",
    arguments: { path: "src/foo.ts" },
    agent: { id: "register-smoke-gate" },
  },
  async () => ({ kind: "allow" }),
);
assert.equal(gate.kind, "ask");
assert.match(gate.reason, /sbtd_plan/);

console.log("register smoke ok", dshPkg.version, pluginPkg.version);
