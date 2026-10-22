import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import extension from "../../../dist/extension.js";

// Observe registrations while forwarding every call to the real host API.
// No provider, model, tool execution, or fake host is supplied by this harness.
export default function smoke(pi) {
  const hooks = [];
  const tools = [];
  const extensionErrors = [];
  let toolCall;
  let sbtd;
  extension(
    new Proxy(pi, {
      get(target, key) {
        if (key === "on")
          return (name, handler) => {
            hooks.push(name);
            if (name === "tool_call") toolCall = handler;
            return target.on(name, async (...args) => {
              try {
                return await handler(...args);
              } catch (error) {
                extensionErrors.push(String(error));
                throw error;
              }
            });
          };
        if (key === "registerTool")
          return (tool) => {
            tools.push(tool.name);
            return target.registerTool(tool);
          };
        if (key === "registerCommand")
          return (name, command) => {
            assert.equal(name, "sbtd");
            sbtd = command.handler;
            return target.registerCommand(name, command);
          };
        const value = Reflect.get(target, key);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }),
  );
  pi.on("before_agent_start", () => {
    throw new Error("Smoke must never start a model turn");
  });
  pi.on("session_start", async (_event, ctx) => {
    const notices = [];
    const confirmations = [];
    try {
      assert.equal(ctx.model, undefined, "Smoke must have no configured model");
      assert.equal(typeof sbtd, "function");
      const hostTools = pi.getAllTools().map((tool) => tool.name);
      const hostCommands = pi.getCommands().map((command) => command.name);
      assert(hostCommands.includes("sbtd"));
      assert(tools.includes("sbtd_workflow"));
      assert(hooks.includes("session_start") && hooks.includes("tool_call"));
      assert.deepEqual(extensionErrors, []);
      const refusal = await toolCall(
        {
          type: "tool_call",
          toolName: "bash",
          toolCallId: "row-c-dependency-smoke",
          input: {
            command: `${process.env.ROW_C_SMOKE_PYTHON} onboard.py migration verify`,
          },
        },
        ctx,
      );
      assert.equal(refusal?.block, true);
      const dependencyRefusal = JSON.parse(refusal.reason);
      assert.deepEqual(dependencyRefusal.missingPackages, [
        "jsonschema",
        "PyYAML",
        "markdown-it-py",
        "tomlkit",
        "cryptography",
      ]);
      for (const tool of tools)
        assert(hostTools.includes(tool), `Host omitted ${tool}`);
      const ui = {
        notify(message) {
          notices.push(message);
        },
        async confirm(title, message) {
          confirmations.push({ title, message });
          // Project-only onboard: never approve installs, MCP, Trellis, or a model handoff.
          return title === "Apply SBTD Onboard Plan";
        },
      };
      const commandContext = new Proxy(ctx, {
        get(target, key) {
          return key === "ui" ? ui : Reflect.get(target, key, target);
        },
      });
      await sbtd("help", commandContext);
      await sbtd("onboard plan", commandContext);
      const plan = JSON.parse(notices.at(-1));
      assert.match(plan.digest, /^[a-f0-9]{64}$/);
      await sbtd("onboard init-projects", commandContext);
      const artifacts = ["AGENTS.md", ".omp/AGENTS.md"];
      for (const artifact of artifacts) {
        const content = await readFile(join(ctx.cwd, artifact), "utf8");
        assert(content.includes("sbtd"), `${artifact} lacks managed content`);
      }
      const result = {
        status: "passed",
        hostVersion: "18.11.1",
        model: null,
        commands: hostCommands.filter((name) => name === "sbtd"),
        tools,
        hooks,
        artifacts,
        confirmations,
        notices,
        extensionErrors,
        dependencyRefusal,
      };
      await writeFile(
        process.env.ROW_C_SMOKE_RESULT,
        `${JSON.stringify(result, null, 2)}\n`,
      );
      process.exit(0);
    } catch (error) {
      await writeFile(
        process.env.ROW_C_SMOKE_RESULT,
        `${JSON.stringify({ status: "failed", error: String(error), hooks, tools, notices, confirmations }, null, 2)}\n`,
      );
      process.exit(1);
    }
  });
}
