import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  access,
  chmod,
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  realpath,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";
import {
  acceptanceArtifactSha256,
  startingFilesSha256,
  valueStudyFixtureSha256,
} from "../scripts/p0/release-validator.ts";
import {
  currentPublicSbtdReport,
  legacyAsciiSbtdReport,
  smallDirectRoutePublicSbtdReport,
} from "./fixtures/p0-reports.ts";

const workspaceRoot = fileURLToPath(new URL("../../..", import.meta.url));
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const harnessPath = join(
  pluginRoot,
  "scripts/p0/authorized-omp-rpc-harness.ts",
);
const temporaryRoots: string[] = [];

type FakeBehavior =
  | "safe"
  | "malformed-frame"
  | "unknown-tool"
  | "workspace-escape"
  | "secret"
  | "judge-tool"
  | "execution-confirm"
  | "onboard-init-confirm"
  | "onboard-init-no-plan"
  | "onboard-init-digest-mismatch"
  | "onboard-init-title-mismatch"
  | "fatal-before-tool"
  | "model-validation-escape"
  | "private-path"
  | "workspace-path"
  | "bare-token"
  | "unsafe-command-output"
  | "file-uri-path"
  | "file-uri-single-slash-path"
  | "write-symlink"
  | "replace-symlink"
  | "compat-agent-directory"
  | "compat-agent-mutation"
  | "compat-agent-mutation-failure"
  | "compat-agent-empty-directory-mutation"
  | "compat-agent-directory-deletion"
  | "compat-agent-directory-chmod"
  | "status-update"
  | "widget-update"
  | "deferred-prompt-result"
  | "deferred-prompt-result-malformed"
  | "deferred-prompt-result-unbound"
  | "deferred-prompt-result-agent-invoked"
  | "deferred-prompt-result-duplicate"
  | "deferred-prompt-result-timeout"
  | "deferred-agent-start"
  | "workspace-config-capture"
  | "installed-plugin-required"
  | "compatibility-no-plan"
  | "compatibility-plan-with-local-target"
  | "onboard-init-secondary-confirmation"
  | "compatibility-unrelated-help-output"
  | "compatibility-unrelated-status-output"
  | "split-command-output"
  | "oversize-multibyte-report"
  | "flooded-command-output";

type HarnessResult = Readonly<{
  code: number | null;
  stdout: string;
  stderr: string;
}>;

type HarnessResponse = Readonly<{
  schemaVersion: number;
  operation: string;
  result: Readonly<{
    status?: string;
    blocker?: Readonly<{ code?: string }>;
    executionProcessId?: string;
    judgeProcessId?: string;
    events?: readonly unknown[];
    acceptanceArtifact?: unknown;
    acceptanceArtifactSha256?: string;
  }>;
}>;

const fixture = {
  schemaVersion: 1,
  id: "P0-VS-HARNESS-001",
  category: "docs-config",
  prompt: "Return a bounded safe response.",
  startingFiles: { "README.txt": "frozen fixture\n" },
  startingSnapshotSha256: startingFilesSha256({
    "README.txt": "frozen fixture\n",
  }),
  expected: {
    route: "small-direct-change",
    routeCost: "light",
    requiredGates: [],
    obligations: ["return bounded output"],
  },
  rubric: [
    { id: "complete", description: "Complete", weight: 100, severe: true },
  ],
  cleanupBoundary: "invocation workspace only",
  permittedNetwork: "none",
} as const;

function currentPublicReport(): string {
  return currentPublicSbtdReport();
}

function environment(root: string): Record<string, string> {
  return {
    PATH: `${join(root, "bin")}:${process.env.PATH ?? ""}`,
    KPI_OMP_RUNTIME_ROOT: join(root, "runtime"),
    KPI_OMP_RUNTIME_VERSION: "17.3.5",
    KPI_OMP_EXECUTION_MODEL_ID: "execution/model",
    KPI_OMP_JUDGE_MODEL_ID: "judge/model",
    KPI_OMP_EXECUTION_PROCESS_ID: "execution-process",
    KPI_OMP_JUDGE_PROCESS_ID: "judge-process",
    KPI_OMP_PLUGIN_DIR: join(root, "plugin"),
    KPI_OMP_PLUGIN_TARBALL: join(root, "plugin.tgz"),
  };
}

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-authorized-rpc-harness-"));
  temporaryRoots.push(root);
  return root;
}

async function runCommand(
  command: string,
  arguments_: readonly string[],
  cwd: string,
): Promise<void> {
  const { promise, resolve, reject } = Promise.withResolvers<void>();
  const child = spawn(command, arguments_, {
    cwd,
    env: { PATH: process.env.PATH ?? "" },
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  child.once("error", reject);
  child.once("close", (code) => {
    if (code === 0) resolve();
    else reject(new Error(`${command} failed: ${stderr}`));
  });
  return promise;
}

type PackedPlugin = Readonly<{
  tarball: string;
  packageDirectory: string;
}>;

async function extractPackedPlugin(root: string): Promise<PackedPlugin> {
  const packedRoot = join(root, "packed");
  const extractedRoot = join(root, "extracted");
  await mkdir(packedRoot, { recursive: true });
  await runCommand(
    "pnpm",
    ["pack", "--pack-destination", packedRoot],
    pluginRoot,
  );
  const tarballs = (await readdir(packedRoot)).filter((name) =>
    name.endsWith(".tgz"),
  );
  expect(tarballs).toHaveLength(1);
  const tarball = join(packedRoot, tarballs[0] ?? "");
  await mkdir(extractedRoot, { recursive: true });
  await runCommand("tar", ["-xzf", tarball, "-C", extractedRoot], root);
  return { tarball, packageDirectory: join(extractedRoot, "package") };
}

async function installPackedPlugin(
  root: string,
  tarball: string,
): Promise<string> {
  const pluginRoot = join(root, "installed-plugins");
  await mkdir(pluginRoot, { recursive: true });
  await writeFile(
    join(pluginRoot, "package.json"),
    `${JSON.stringify({
      name: "kpi-omp-packed-host-smoke",
      private: true,
      dependencies: { "@kunolu/omp-sbtd": `file:${tarball}` },
    })}\n`,
    "utf8",
  );
  await runCommand(
    "bun",
    ["install", "--ignore-scripts", "--offline"],
    pluginRoot,
  );
  const installed = join(pluginRoot, "node_modules", "@kunolu", "omp-sbtd");
  await readFile(join(installed, "dist", "extension.js"), "utf8");
  return installed;
}

async function localOmpExecutable(): Promise<string> {
  const runtimePackageRoot = join(
    pluginRoot,
    "node_modules",
    "@oh-my-pi",
    "pi-coding-agent",
  );
  const metadata = z
    .object({
      version: z.literal("17.3.5"),
      bin: z.object({ omp: z.literal("dist/cli.js") }),
    })
    .parse(
      JSON.parse(
        await readFile(join(runtimePackageRoot, "package.json"), "utf8"),
      ),
    );
  return join(runtimePackageRoot, metadata.bin.omp);
}

async function snapshotDirectory(root: string): Promise<string> {
  const hash = createHash("sha256");
  const visit = async (directory: string, prefix: string): Promise<void> => {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries.sort((left, right) =>
      left.name.localeCompare(right.name),
    )) {
      const path = join(directory, entry.name);
      const relativePath =
        prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (entry.isDirectory()) {
        hash.update(`directory\0${relativePath}\0`);
        await visit(path, relativePath);
      } else if (entry.isFile()) {
        hash.update(`file\0${relativePath}\0`);
        hash.update(await readFile(path));
      } else {
        hash.update(`other\0${relativePath}\0`);
      }
    }
  };
  await visit(root, "");
  return hash.digest("hex");
}

async function runPackedHostSmoke(
  input: Readonly<{
    executable: string;
    plugin: string;
    project: string;
    home: string;
    agent: string;
  }>,
): Promise<void> {
  const child = spawn(
    input.executable,
    [
      "--mode",
      "rpc",
      "--cwd",
      input.project,
      "--no-session",
      "--no-tools",
      "--no-skills",
      "--no-rules",
      "--no-pty",
      "--no-title",
      "--extension",
      join(input.plugin, "dist", "extension.js"),
    ],
    {
      cwd: input.project,
      env: {
        PATH: process.env.PATH ?? "",
        HOME: input.home,
        XDG_CACHE_HOME: join(input.home, "cache"),
        XDG_CONFIG_HOME: join(input.home, ".config"),
        XDG_DATA_HOME: join(input.home, "data"),
        PI_CODING_AGENT_DIR: input.agent,
        CI: "1",
        NO_COLOR: "1",
        npm_config_offline: "true",
        pnpm_config_offline: "true",
        PIP_NO_INDEX: "1",
      },
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  const ready = Promise.withResolvers<void>();
  const closed = Promise.withResolvers<void>();
  let stopped = false;
  let buffered = "";
  let pending:
    | Readonly<{
        id: string;
        resolve: () => void;
        reject: (error: Error) => void;
      }>
    | undefined;
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  const fail = (reason: string): void => {
    ready.reject(new Error(reason));
    pending?.reject(new Error(reason));
  };
  child.once("error", () => fail("actual OMP host could not start"));
  child.once("close", () => {
    closed.resolve();
    if (!stopped)
      fail(`actual OMP host ended during its public RPC exchange: ${stderr}`);
  });
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    buffered += chunk;
    let newline = buffered.indexOf("\n");
    while (newline >= 0) {
      const line = buffered.slice(0, newline);
      buffered = buffered.slice(newline + 1);
      newline = buffered.indexOf("\n");
      const frame = z
        .object({ type: z.string() })
        .passthrough()
        .safeParse(JSON.parse(line));
      if (!frame.success) {
        fail("actual OMP host emitted an invalid public RPC frame");
        continue;
      }
      if (frame.data.type === "ready") {
        ready.resolve();
        continue;
      }
      if (
        frame.data.type === "agent_start" ||
        frame.data.type === "host_tool_call"
      ) {
        fail("read-only SBTD command attempted provider or tool use");
        continue;
      }
      const response = z
        .object({
          type: z.literal("response"),
          id: z.string(),
          command: z.literal("prompt"),
          success: z.boolean(),
        })
        .passthrough()
        .safeParse(frame.data);
      if (response.success && pending?.id === response.data.id) {
        if (!response.data.success)
          pending.reject(
            new Error("actual OMP host rejected a read-only command"),
          );
        continue;
      }
      const promptResult = z
        .object({
          type: z.literal("prompt_result"),
          id: z.string(),
          agentInvoked: z.boolean(),
        })
        .safeParse(frame.data);
      if (promptResult.success && pending?.id === promptResult.data.id) {
        if (promptResult.data.agentInvoked)
          pending.reject(
            new Error("read-only SBTD command invoked a provider"),
          );
        else pending.resolve();
      }
    }
  });
  // Integration with an external OMP process needs a real-clock bound; all
  // success paths resolve from concrete RPC lifecycle events before it expires.
  const bounded = <T>(promise: Promise<T>, label: string): Promise<T> =>
    new Promise<T>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error(`${label} timed out`)),
        15_000,
      );
      void promise.then(
        (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        (error: unknown) => {
          clearTimeout(timer);
          reject(error);
        },
      );
    });
  try {
    await bounded(ready.promise, "actual OMP host startup");
    for (const command of ["help", "status", "report", "onboard plan"]) {
      const commandPending = Promise.withResolvers<void>();
      const id = `smoke-${command.replace(" ", "-")}`;
      pending = { id, ...commandPending };
      child.stdin.write(
        `${JSON.stringify({ id, type: "prompt", message: `/sbtd ${command}` })}\n`,
      );
      await bounded(commandPending.promise, `/sbtd ${command}`);
      pending = undefined;
    }
  } finally {
    stopped = true;
    child.kill("SIGTERM");
    await bounded(closed.promise, "actual OMP host shutdown");
  }
}

async function createFakeRuntime(
  root: string,
  behavior: FakeBehavior,
  publicReportText = smallDirectRoutePublicSbtdReport(),
  secondaryConfirmationTitle = "Install Shared CLI Dependencies",
): Promise<string> {
  const executable = join(root, "runtime", "17.3.5", "bin", "omp");
  const capturePath = join(root, "runtime-cwds.jsonl");
  await Promise.all([
    mkdir(join(root, "plugin", "dist"), { recursive: true }),
    mkdir(join(root, "runtime", "17.3.5", "bin"), { recursive: true }),
  ]);
  await writeFile(
    join(root, "plugin", "dist", "extension.js"),
    "export {};\n",
    "utf8",
  );
  await writeFile(
    executable,
    `#!/usr/bin/env node
const { appendFileSync, chmodSync, existsSync, mkdirSync, readFileSync, rmdirSync, writeFileSync } = require("node:fs");
const readline = require("node:readline");
const behavior = ${JSON.stringify(behavior)};
const capturePath = ${JSON.stringify(capturePath)};
const toolResultPath = ${JSON.stringify(join(root, "runtime-tool-results.jsonl"))};
const hostToolsPath = ${JSON.stringify(join(root, "runtime-host-tools.jsonl"))};
const uiResponsesPath = ${JSON.stringify(join(root, "runtime-ui-responses.jsonl"))};
const modelEscapePath = ${JSON.stringify(join(root, "model-validation-escape.txt"))};
const compatibilityAgentDirectoryPath = ${JSON.stringify(join(root, "compat-agent-directory.txt"))};
const workspaceConfigCapturePath = ${JSON.stringify(join(root, "runtime-workspace-config.txt"))};
const publicReportText = ${JSON.stringify(publicReportText)};
const secondaryConfirmationTitle = ${JSON.stringify(secondaryConfirmationTitle)};
if (behavior === "fatal-before-tool")
  process.on("SIGTERM", () => {
    // Keep the fake peer alive long enough to observe a prohibited late response.
  });
const args = process.argv.slice(2);
if (args.includes("--version")) {
  appendFileSync(capturePath, JSON.stringify(process.cwd()) + "\\n");
  process.stdout.write("17.3.5\\n");
  process.exit(0);
}
appendFileSync(capturePath, JSON.stringify(process.cwd()) + "\\n");
if (behavior === "compat-agent-directory")
  appendFileSync(
    compatibilityAgentDirectoryPath,
    (process.env.PI_CODING_AGENT_DIR ?? "") + "\\n",
  );
if (
  behavior === "compat-agent-mutation" ||
  behavior === "compat-agent-mutation-failure"
)
  writeFileSync(
    (process.env.PI_CODING_AGENT_DIR ?? "") + "/mutation.txt",
    "mutated",
  );
if (behavior === "compat-agent-empty-directory-mutation")
  mkdirSync((process.env.PI_CODING_AGENT_DIR ?? "") + "/empty");
if (behavior === "compat-agent-directory-deletion")
  rmdirSync(process.env.PI_CODING_AGENT_DIR ?? "");
if (behavior === "compat-agent-directory-chmod")
  chmodSync(process.env.PI_CODING_AGENT_DIR ?? "", 0o500);
if (behavior === "workspace-config-capture") {
  const configPath = process.cwd() + "/.omp/config.yml";
  writeFileSync(
    workspaceConfigCapturePath,
    existsSync(configPath) ? readFileSync(configPath, "utf8") : "absent\\n",
  );
}
const model = args.includes("--model") ? args[args.indexOf("--model") + 1] : "";
const [provider, id] = model.split("/");
const installedPluginRoot =
  process.env.PI_CODING_AGENT_DIR +
  "/plugins/node_modules/@kunolu/omp-sbtd";
const installedPluginAvailable =
  args.includes("--extension") &&
  args[args.indexOf("--extension") + 1] ===
    installedPluginRoot + "/dist/extension.js" &&
  existsSync(installedPluginRoot + "/package.json");
let lastText = "safe model result";
let runtimeMode = "advisory";
const onboardPlanDigest = "a".repeat(64);
let pendingOnboardInit;
const output = (value) => process.stdout.write(JSON.stringify(value) + "\\n");
output({ type: "ready", protocolVersion: 1, supportedProtocolVersions: [1, 2], maxFrameBytes: 65536, maxReassembledFrameBytes: 65536 });
if (behavior === "status-update")
  output({
    type: "extension_ui_request",
    id: "runtime-status",
    method: "setStatus",
    statusKey: "runtime",
    statusText: "ready",
  });
if (behavior === "widget-update")
  output({
    type: "extension_ui_request",
    id: "runtime-widget",
    method: "setWidget",
    widgetKey: "runtime",
    widgetLines: ["ready"],
    widgetPlacement: "belowEditor",
  });
readline.createInterface({ input: process.stdin }).on("line", (line) => {
  const request = JSON.parse(line);
  const respond = (data, target = request) => output({ id: target.id, type: "response", command: target.type, success: true, ...(data === undefined ? {} : { data }) });
  if (request.type === "get_state") return respond({ model: { provider, id } });
  if (request.type === "extension_ui_response") {
    appendFileSync(uiResponsesPath, JSON.stringify(request) + "\\n");
    if (request.id === "onboard-init-confirm" && request.confirmed === true && pendingOnboardInit !== undefined) {
      if (behavior === "onboard-init-secondary-confirmation")
        return output({
          type: "extension_ui_request",
          id: "onboard-init-secondary",
          method: "confirm",
          title: secondaryConfirmationTitle,
          message: "Install allowlisted shared CLI dependencies?",
        });
      const pending = pendingOnboardInit;
      pendingOnboardInit = undefined;
      return respond({ agentInvoked: false }, pending);
    }
    if (request.id === "onboard-init-secondary" && request.confirmed === false && pendingOnboardInit !== undefined) {
      const pending = pendingOnboardInit;
      pendingOnboardInit = undefined;
      return respond({ agentInvoked: false }, pending);
    }
    return;
  }
  if (request.type === "set_auto_retry") return respond({});
  if (request.type === "set_host_tools") {
    appendFileSync(hostToolsPath, JSON.stringify(request) + "\\n");
    return respond({ toolNames: request.tools.map((tool) => tool.name) });
  }
  if (request.type === "get_last_assistant_text") return respond({ text: lastText });
  if (request.type === "host_tool_result") {
    appendFileSync(toolResultPath, JSON.stringify(request) + "\\n");
    if (
      (behavior === "model-validation-escape" &&
        request.toolCallId === "validate-1") ||
      (behavior === "write-symlink" || behavior === "replace-symlink") &&
        request.toolCallId === "link-1"
    ) {
      output({ type: "message_end", message: { role: "assistant", usage: { totalTokens: 10 } } });
      output({ type: "agent_end", isTerminal: true });
    }
    return;
  }
  if (request.type === "prompt") {
    if (behavior === "installed-plugin-required" && !installedPluginAvailable)
      return respond({ agentInvoked: true });
    const message = request.message;
    if (message.startsWith("/sbtd")) {
      if (message === "/sbtd onboard plan" &&
        behavior !== "onboard-init-no-plan" &&
        behavior !== "compatibility-no-plan"
      ) {
        const plan = {
          digest: onboardPlanDigest,
          targets:
            behavior === "compatibility-plan-with-local-target"
              ? [{ path: "/private/var/folders/kpi-plan-target/AGENTS.md" }]
              : ["AGENTS.md"],
        };
        output({
          type: "extension_ui_request",
          id: "onboard-plan",
          method: "notify",
          message: JSON.stringify(plan),
        });
      }
      if (message === "/sbtd onboard init") {
        pendingOnboardInit = request;
        const confirmationTitle = behavior === "onboard-init-title-mismatch" ? "Unexpected Onboard title" : "Apply SBTD Onboard Plan";
        const confirmationDigest = behavior === "onboard-init-digest-mismatch" ? "b".repeat(64) : onboardPlanDigest;
        return output({ type: "extension_ui_request", id: "onboard-init-confirm", method: "confirm", title: confirmationTitle, message: "Apply plan " + confirmationDigest + " to 1 managed AGENTS targets?" });
      }
      if (message === "/sbtd on") runtimeMode = "enforced";
      if (message === "/sbtd off") runtimeMode = "advisory";
      if (message === "/sbtd help") {
        const helpText =
          behavior === "compatibility-unrelated-help-output"
            ? "unrelated status update"
            : "Usage: /sbtd help [command]\\nUsage: /sbtd report";
        if (behavior === "split-command-output") {
          output({ type: "command_output", text: "Usage: /sbtd help [command]\\n" });
          output({ type: "command_output", text: "Usage: /sbtd report" });
        } else {
          output({ type: "command_output", text: helpText });
        }
      }
      if (message === "/sbtd status") {
        const statusText =
          behavior === "compatibility-unrelated-status-output"
            ? "unrelated status update"
            : "Runtime Mode: " + runtimeMode + "\\nPolicy Profile: strict";
        if (behavior === "split-command-output") {
          output({ type: "command_output", text: "Runtime Mode: " + runtimeMode + "\\n" });
          output({ type: "command_output", text: "Policy Profile: strict" });
        } else {
          output({ type: "command_output", text: statusText });
        }
      }
      if (message === "/sbtd report") {
        const unsafeReportText = {
          "unsafe-command-output": "/private/var/folders/kpi-command-output",
          "file-uri-path": "file:///private/var/folders/kpi-file-uri-path",
          "file-uri-single-slash-path":
            "file:/private/var/folders/kpi-file-uri-single-slash-path",
        }[behavior] ?? "";
        let reportText =
          publicReportText
            .replace(
              "- Runtime Mode：advisory",
              "- Runtime Mode：" + runtimeMode,
            )
            .replace(
              '"runtimeMode": "advisory"',
              '"runtimeMode": "' + runtimeMode + '"',
            ) +
          (unsafeReportText === "" ? "" : "\\n" + unsafeReportText);
        if (behavior === "oversize-multibyte-report")
          reportText += "\\n" + "界".repeat(20000);
        if (behavior === "flooded-command-output")
          for (let index = 0; index < 5; index += 1)
            output({ type: "command_output", text: "flood-" + "a".repeat(30000) });
        if (behavior === "split-command-output") {
          const fence = reportText.indexOf("\`\`\`json");
          output({ type: "command_output", text: reportText.slice(0, fence) });
          output({ type: "command_output", text: reportText.slice(fence) });
        } else {
          output({ type: "command_output", text: reportText });
        }
      }
      if (behavior.startsWith("deferred-prompt-result")) {
        respond();
        if (behavior === "deferred-prompt-result-timeout") return;
        if (behavior === "deferred-prompt-result-malformed")
          return output({
            type: "prompt_result",
            id: request.id,
            agentInvoked: "false",
          });
        const promptResult = {
          type: "prompt_result",
          id:
            behavior === "deferred-prompt-result-unbound"
              ? "unbound-prompt"
              : request.id,
          agentInvoked:
            behavior === "deferred-prompt-result-agent-invoked" ? true : false,
        };
        output(promptResult);
        if (behavior === "deferred-prompt-result-duplicate")
          output(promptResult);
        return;
      }
      return respond({ agentInvoked: false });
    }
    if (behavior === "execution-confirm") {
      output({ type: "extension_ui_request", id: "unexpected-confirm", method: "confirm", title: "Unexpected approval", message: "Do not approve this execution-time action." });
      return respond({ agentInvoked: true });
    }
    if (behavior === "deferred-agent-start") {
      respond();
      output({ type: "agent_start" });
      output({
        type: "message_end",
        message: { role: "assistant", usage: { totalTokens: 10 } },
      });
      output({ type: "agent_end", isTerminal: true });
      return;
    }
    if (behavior === "model-validation-escape") {
      output({ type: "host_tool_call", id: "tool-validate", toolCallId: "validate-1", toolName: "kpi_validate", arguments: { command: "node-test", targets: ["escape.test.cjs"] } });
      output({ type: "message_end", message: { role: "assistant", usage: { totalTokens: 10 } } });
      output({ type: "agent_end", isTerminal: true });
      return respond({ agentInvoked: true });
    }
    if (behavior === "write-symlink") {
      require("node:fs").symlinkSync(modelEscapePath, "escape-link.txt");
      output({ type: "host_tool_call", id: "tool-link", toolCallId: "link-1", toolName: "kpi_write", arguments: { path: "escape-link.txt", content: "escaped" } });
      return respond({ agentInvoked: true });
    }
    if (behavior === "replace-symlink") {
      require("node:fs").writeFileSync(modelEscapePath, "initial");
      require("node:fs").symlinkSync(modelEscapePath, "escape-link.txt");
      output({ type: "host_tool_call", id: "tool-replace", toolCallId: "link-1", toolName: "kpi_exact_replace", arguments: { path: "escape-link.txt", expected: "initial", replacement: "escaped" } });
      return respond({ agentInvoked: true });
    }
    if (
      behavior === "fatal-before-tool" ||
      behavior === "compat-agent-mutation-failure"
    ) {
      output({ type: "host_tool_call", id: "tool-request", toolCallId: "call-1", toolName: "kpi_read", arguments: { path: "README.txt" } });
      return process.stdout.write("not-json\\n");
    }
    if (behavior === "malformed-frame") return process.stdout.write("not-json\\n");
    if (behavior === "unknown-tool" || behavior === "workspace-escape" || (behavior === "judge-tool" && provider === "judge")) {
      output({ type: "host_tool_call", id: "tool-request", toolCallId: "call-1", toolName: behavior === "workspace-escape" ? "kpi_read" : "not-allowlisted", arguments: behavior === "workspace-escape" ? { path: "../outside" } : {} });
      return respond({ agentInvoked: true });
    }
    if (behavior === "secret") lastText = "api_key=secret-value";
    if (behavior === "private-path") lastText = "/private/var/folders/kpi-private-path";
    if (behavior === "workspace-path") lastText = "/workspace/private-path";
    if (behavior === "bare-token") lastText = "token=bare-secret-value";
    if (provider === "judge") lastText = JSON.stringify({ first: { total: 80, severeAcceptanceFailure: false, criteria: [{ id: "complete", score: 80, reason: "bounded" }] }, second: { total: 80, severeAcceptanceFailure: false, criteria: [{ id: "complete", score: 80, reason: "bounded" }] } });
    respond({ agentInvoked: true });
    output({ type: "message_end", message: { role: "assistant", usage: { totalTokens: 10 } } });
    output({ type: "agent_end", isTerminal: true });
    return;
  }
  output({ id: request.id, type: "response", command: request.type, success: false, error: "unsupported" });
});
`,
    { encoding: "utf8", mode: 0o700 },
  );
  await chmod(executable, 0o700);
  await Promise.all([
    writeFile(join(root, "plugin.tgz"), "fixture tarball", "utf8"),
    createFakeBun(root),
  ]);
  return capturePath;
}

async function createFakeBun(root: string): Promise<string> {
  const executable = join(root, "bin", "bun");
  await mkdir(join(root, "bin"), { recursive: true });
  await writeFile(
    executable,
    `#!/usr/bin/env node
const { mkdirSync, writeFileSync } = require("node:fs");
const { join } = require("node:path");
const packageRoot = join(
  process.cwd(),
  "node_modules",
  "@kunolu",
  "omp-sbtd",
);
mkdirSync(packageRoot, { recursive: true });
mkdirSync(join(packageRoot, "dist"), { recursive: true });
writeFileSync(
  join(packageRoot, "package.json"),
  JSON.stringify({
    name: "@kunolu/omp-sbtd",
    version: "0.0.0-test",
    omp: { extensions: ["./dist/extension.js"] },
  }),
);
writeFileSync(join(packageRoot, "dist", "extension.js"), "export {};");
`,
    { encoding: "utf8", mode: 0o700 },
  );
  await chmod(executable, 0o700);
  return executable;
}

async function runHarness(
  root: string,
  request: unknown,
  overrides: Readonly<Record<string, string | undefined>> = {},
): Promise<HarnessResult> {
  const childEnvironment = environment(root);
  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined) delete childEnvironment[key];
    else childEnvironment[key] = value;
  }
  const { promise, resolve } = Promise.withResolvers<HarnessResult>();
  const child = spawn("node", ["--import", "tsx", harnessPath], {
    cwd: pluginRoot,
    env: childEnvironment,
    shell: false,
    stdio: ["pipe", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  child.once("close", (code) => resolve({ code, stdout, stderr }));
  child.stdin.end(JSON.stringify(request));
  return promise;
}

function executeRequest(): unknown {
  return {
    schemaVersion: 1,
    operation: "execute",
    input: {
      runId: "p0-harness-run",
      fixture,
      fixtureSha256: valueStudyFixtureSha256(fixture),
      arm: "treatment",
      mode: "enforced",
      attempt: 1,
      workspacePath: "/parent-supplied-but-untrusted",
      limits: { wallClockMs: 30_000, maxTurns: 4, maxTokens: 100 },
    },
  };
}

function compatibilityRequest(root: string): unknown {
  return {
    schemaVersion: 1,
    operation: "compatibility",
    input: {
      testedRuntimeVersion: "17.3.5",
      pluginPackagePath: join(root, "plugin"),
      pluginTarballPath: join(root, "plugin.tgz"),
      sandboxRoot: join(root, "compatibility"),
      commands: ["help", "status", "report", "onboard plan"],
    },
  };
}

function parsed(result: HarnessResult): HarnessResponse {
  expect(result.code, result.stderr).toBe(0);
  expect(result.stderr).toBe("");
  const lines = result.stdout.trim().split("\n");
  expect(lines).toHaveLength(1);
  const response = JSON.parse(lines[0] ?? "{}") as HarnessResponse;
  if (response.operation === "compatibility") {
    // Slice 2 identity contract: every compatibility response echoes the
    // tested Runtime identity as testedRuntimeVersion, and the retired
    // exact-current alias currentRuntimeVersion must never return.
    expect(response.result).toMatchObject({
      testedRuntimeVersion: "17.3.5",
    });
    expect(response.result).not.toHaveProperty("currentRuntimeVersion");
  }
  return response;
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("authorized OMP public-RPC harness", () => {
  it("Scenario: 当前渲染报告可驱动四命令主机认证", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "safe", currentPublicReport());

    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "passed",
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
  }, 20_000);

  it("Scenario: 含本地目标路径的 Onboard Plan 只保留受控摘要", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(
      root,
      "compatibility-plan-with-local-target",
      currentPublicReport(),
    );

    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "passed",
      commandResults: { "onboard plan": "passed" },
    });
  }, 20_000);

  it("Scenario: 旧 ASCII 伪报告不能驱动主机认证", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "safe", legacyAsciiSbtdReport());

    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_REPORT_INVALID" },
    });
  }, 20_000);

  it("Scenario: 跨多个有效帧拆分的公共输出仍可完成四命令认证", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(
      root,
      "split-command-output",
      currentPublicReport(),
    );

    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "passed",
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
  }, 20_000);

  it("Scenario: 超出 UTF-8 字节上限的多字节公共输出被阻断", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(
      root,
      "oversize-multibyte-report",
      currentPublicReport(),
    );

    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_RPC_FRAME_INVALID" },
    });
  }, 20_000);

  it("Scenario: 累积公共输出超出总有界预算时失败关闭", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(
      root,
      "flooded-command-output",
      currentPublicReport(),
    );

    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_RPC_FRAME_INVALID" },
    });
  }, 20_000);

  it("Scenario: 未分类 auto 观察的执行事件不携带合成 routeCost", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "safe", currentPublicReport());
    const baseRequest = executeRequest() as Readonly<{
      input: Record<string, unknown>;
    }>;
    const controlRequest = {
      ...baseRequest,
      input: { ...baseRequest.input, arm: "control", mode: "advisory" },
    };

    const result = parsed(await runHarness(root, controlRequest));

    expect(result.result).toMatchObject({ status: "completed" });
    const events = (result.result.events ?? []) as readonly Record<
      string,
      unknown
    >[];
    const reportEvent = events.find((event) => event.kind === "report");
    expect(reportEvent).toEqual({ kind: "report", requiredGates: [] });
    expect(reportEvent).not.toHaveProperty("routeCost");
  }, 20_000);

  it.each([
    "Install Shared CLI Dependencies",
    "Merge OMP MCP Configuration",
    "Initialize Trellis Projects",
  ])("Scenario: Value Study 只拒绝指定的全局写入确认：%s", async (secondaryConfirmationTitle) => {
    const root = await temporaryRoot();
    await createFakeRuntime(
      root,
      "onboard-init-secondary-confirmation",
      undefined,
      secondaryConfirmationTitle,
    );
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result.result).toMatchObject({ status: "completed" });
    const confirmations = (
      await readFile(join(root, "runtime-ui-responses.jsonl"), "utf8")
    )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as { id: string; confirmed: boolean });
    expect(confirmations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "onboard-init-confirm",
          confirmed: true,
        }),
        expect.objectContaining({
          id: "onboard-init-secondary",
          confirmed: false,
        }),
      ]),
    );
  }, 20_000);
  it("executes a frozen treatment arm in an isolated workspace with one redacted response", async () => {
    const root = await temporaryRoot();
    const capturePath = await createFakeRuntime(root, "safe");
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result).toMatchObject({
      schemaVersion: 1,
      operation: "execute",
      result: { status: "completed", executionProcessId: "execution-process" },
    });
    expect(result.result.events).toEqual([
      { kind: "usage", turns: 1, tokens: 10 },
      { kind: "report", requiredGates: [], routeCost: "light" },
      {
        kind: "terminal",
        outcome: "completed",
        finalResponse: "safe model result",
      },
    ]);
    expect(result.result.acceptanceArtifactSha256).toBe(
      acceptanceArtifactSha256(result.result.acceptanceArtifact),
    );
    expect(result.result).not.toHaveProperty("workspacePath");
    expect(JSON.stringify(result)).not.toContain("/private");
    const usedWorkspaces = (await readFile(capturePath, "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as string);
    expect(usedWorkspaces).not.toContain("/parent-supplied-but-untrusted");
    const stillExists = await Promise.all(
      usedWorkspaces.map(async (path) => {
        try {
          await access(path);
          return true;
        } catch {
          return false;
        }
      }),
    );
    expect(stillExists).toEqual(usedWorkspaces.map(() => false));
  }, 10_000);

  it("Scenario: 无效的受控认证目录在启动 OMP 前失败关闭", async () => {
    const root = await temporaryRoot();
    const capturePath = await createFakeRuntime(root, "safe");
    const result = parsed(
      await runHarness(root, compatibilityRequest(root), {
        KPI_OMP_COMPAT_AGENT_DIR: join(root, "missing-agent-directory"),
      }),
    );

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_COMPAT_AGENT_DIR_INVALID" },
    });
    await expect(readFile(capturePath, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
    const regularAgentDirectory = join(root, "regular-agent-directory");
    const symbolicAgentDirectory = join(root, "symbolic-agent-directory");
    await mkdir(regularAgentDirectory);
    await symlink(regularAgentDirectory, symbolicAgentDirectory);
    const symbolicResult = parsed(
      await runHarness(root, compatibilityRequest(root), {
        KPI_OMP_COMPAT_AGENT_DIR: symbolicAgentDirectory,
      }),
    );
    expect(symbolicResult.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_COMPAT_AGENT_DIR_INVALID" },
    });
    await expect(readFile(capturePath, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("Scenario: 运行时状态 UI 更新不触发交互审批", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "status-update");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result.status).toBe("passed");
    await expect(
      readFile(join(root, "runtime-ui-responses.jsonl"), "utf8"),
    ).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("Scenario: 运行时 Widget UI 更新不触发交互审批", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "widget-update");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result.status).toBe("passed");
    await expect(
      readFile(join(root, "runtime-ui-responses.jsonl"), "utf8"),
    ).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("Scenario: 传统内联 local prompt 确认保持兼容", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "safe");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "passed",
      agentInvoked: false,
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
  });

  it("Scenario: 精确 tarball 安装后才加载受测 Plugin", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "installed-plugin-required");
    await createFakeBun(root);
    const tarballPath = join(root, "plugin.tgz");
    await writeFile(tarballPath, "fixture tarball", "utf8");
    const result = parsed(
      await runHarness(
        root,
        {
          schemaVersion: 1,
          operation: "compatibility",
          input: {
            testedRuntimeVersion: "17.3.5",
            pluginPackagePath: join(root, "plugin"),
            pluginTarballPath: tarballPath,
            sandboxRoot: join(root, "compatibility"),
            commands: ["help", "status", "report", "onboard plan"],
          },
        },
        {
          PATH: `${join(root, "bin")}:${process.env.PATH ?? ""}`,
          KPI_OMP_PLUGIN_TARBALL: tarballPath,
        },
      ),
    );

    expect(result.result).toMatchObject({
      status: "passed",
      agentInvoked: false,
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
  });

  it("Scenario: 延迟的本地 prompt 结果不被误判为模型调用", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "deferred-prompt-result");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "passed",
      agentInvoked: false,
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
  });

  it.each([
    ["deferred-prompt-result-malformed", "OMP_HARNESS_RPC_FRAME_INVALID"],
    ["deferred-prompt-result-unbound", "OMP_HARNESS_RPC_FRAME_INVALID"],
    ["deferred-prompt-result-agent-invoked", "OMP_HARNESS_RPC_FRAME_INVALID"],
    ["deferred-prompt-result-duplicate", "OMP_HARNESS_RPC_FRAME_INVALID"],
  ] as const)("Scenario: 无效的延迟 local prompt 结果失败关闭: %s", async (behavior, code) => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, behavior);
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code },
    });
  });

  it("Scenario: 缺少延迟 local prompt 结果在有界期限后失败关闭", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "deferred-prompt-result-timeout");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_TIMEOUT" },
    });
  }, 20_000);

  it("Scenario: 兼容性检查要求 Onboard plan 的有界通知", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "compatibility-no-plan");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_UI_APPROVAL_DENIED" },
    });
  }, 20_000);

  it("Scenario: 兼容性检查拒绝无关的帮助输出", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "compatibility-unrelated-help-output");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_REPORT_INVALID" },
    });
  }, 20_000);

  it("Scenario: 兼容性检查拒绝无关的状态输出", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "compatibility-unrelated-status-output");
    const result = parsed(await runHarness(root, compatibilityRequest(root)));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_REPORT_INVALID" },
    });
  }, 20_000);

  it("does not downgrade a bare execution prompt acknowledgment followed by agent_start", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "deferred-agent-start");
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result.result).toMatchObject({
      status: "completed",
      executionProcessId: "execution-process",
    });
  });

  it("Scenario: 兼容性子进程只使用显式授权的 agent directory", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "compat-agent-directory");
    const agentDirectory = join(root, "dedicated-agent");
    await mkdir(agentDirectory);
    const result = parsed(
      await runHarness(root, compatibilityRequest(root), {
        KPI_OMP_COMPAT_AGENT_DIR: agentDirectory,
      }),
    );

    expect(result.result.status).toBe("passed");
    expect(
      await readFile(join(root, "compat-agent-directory.txt"), "utf8"),
    ).toBe(`${await realpath(agentDirectory)}\n`);
  });

  it("Scenario: 仅本地命令的兼容性检查不等待隐式本地 Provider 发现", async () => {
    const compatibilityRoot = await temporaryRoot();
    await createFakeRuntime(compatibilityRoot, "workspace-config-capture");
    const compatibilityResult = parsed(
      await runHarness(
        compatibilityRoot,
        compatibilityRequest(compatibilityRoot),
      ),
    );

    expect(compatibilityResult.result.status).toBe("passed");
    await expect(
      readFile(join(compatibilityRoot, "runtime-workspace-config.txt"), "utf8"),
    ).resolves.toBe(
      "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\n",
    );

    const executionRoot = await temporaryRoot();
    await createFakeRuntime(executionRoot, "workspace-config-capture");
    const executionResult = parsed(
      await runHarness(executionRoot, executeRequest()),
    );

    expect(executionResult.result.status).toBe("completed");
    await expect(
      readFile(join(executionRoot, "runtime-workspace-config.txt"), "utf8"),
    ).resolves.toBe("absent\n");
  });

  it("Scenario: 非兼容性 RPC 操作忽略显式 agent directory", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "compat-agent-directory");
    const agentDirectory = join(root, "dedicated-agent");
    await mkdir(agentDirectory);
    const result = parsed(
      await runHarness(root, executeRequest(), {
        KPI_OMP_COMPAT_AGENT_DIR: agentDirectory,
      }),
    );

    expect(result.result.status).toBe("completed");
    const runtimeAgentDirectory = (
      await readFile(join(root, "compat-agent-directory.txt"), "utf8")
    ).trim();
    expect(runtimeAgentDirectory).not.toBe(await realpath(agentDirectory));
    expect(runtimeAgentDirectory).toMatch(/\/kpi-omp-rpc-[^/]+\/agent$/);
  });

  it("Scenario: 可丢弃 profile 的变更生成 profile-isolated 证据", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "compat-agent-mutation");
    const agentDirectory = join(root, "dedicated-agent");
    await mkdir(agentDirectory);
    const result = parsed(
      await runHarness(root, compatibilityRequest(root), {
        KPI_OMP_COMPAT_AGENT_DIR: agentDirectory,
      }),
    );

    expect(await readFile(join(agentDirectory, "mutation.txt"), "utf8")).toBe(
      "mutated",
    );
    expect(result.result).toMatchObject({
      status: "passed",
      agentInvoked: false,
      acceptanceMode: "profile-isolated",
      supportDecision: "requires-separate-support-review",
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
    expect(result.result.filesystemBeforeSha256).toBe(
      result.result.filesystemAfterSha256,
    );
    expect(JSON.stringify(result)).not.toContain(agentDirectory);
  });

  it("fails closed for absent explicit identities and malformed public RPC frames", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "safe");
    const missing = parsed(
      await runHarness(
        root,
        {
          schemaVersion: 1,
          operation: "preflight",
          input: {
            executionModelId: "execution/model",
            judgeModelId: "judge/model",
            runtimeVersion: "17.3.5",
          },
        },
        { KPI_OMP_RUNTIME_ROOT: undefined },
      ),
    );
    expect(missing.result.blocker?.code).toBe("OMP_HARNESS_IDENTITY_REQUIRED");

    const malformedRoot = await temporaryRoot();
    await createFakeRuntime(malformedRoot, "malformed-frame");
    const malformed = parsed(await runHarness(malformedRoot, executeRequest()));
    expect(malformed.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_RPC_FRAME_INVALID" },
    });
  }, 10_000);
  it("does not issue a host-tool result after a fatal public RPC frame", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "fatal-before-tool");
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_RPC_FRAME_INVALID" },
    });
    await expect(
      readFile(join(root, "runtime-tool-results.jsonl"), "utf8"),
    ).rejects.toMatchObject({ code: "ENOENT" });
  });

  it.each([
    ["unknown-tool", "OMP_HARNESS_TOOL_POLICY_VIOLATION"],
    ["workspace-escape", "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION"],
    ["secret", "OMP_HARNESS_SENSITIVE_OUTPUT"],
  ] as const)("fails closed and suppresses output for %s", async (behavior, code) => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, behavior);
    const result = parsed(await runHarness(root, executeRequest()));
    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code },
    });
    expect(JSON.stringify(result)).not.toContain("secret-value");
  });

  it("blocks a model-requested validator before it executes generated code", async () => {
    const root = await temporaryRoot();
    const marker = join(root, "model-validation-escape.txt");
    await createFakeRuntime(root, "model-validation-escape");
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_TOOL_POLICY_VIOLATION" },
    });
    await expect(access(marker)).rejects.toMatchObject({ code: "ENOENT" });
    await expect(
      readFile(join(root, "runtime-host-tools.jsonl"), "utf8"),
    ).resolves.not.toContain("kpi_validate");
  });

  it("blocks a final symlink write before it escapes the isolated workspace", async () => {
    const root = await temporaryRoot();
    const marker = join(root, "model-validation-escape.txt");
    await createFakeRuntime(root, "write-symlink");
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION" },
    });
    await expect(access(marker)).rejects.toMatchObject({ code: "ENOENT" });
  });
  it("blocks an exact-replace symlink before it escapes the isolated workspace", async () => {
    const root = await temporaryRoot();
    const marker = join(root, "model-validation-escape.txt");
    await createFakeRuntime(root, "replace-symlink");
    const result = parsed(await runHarness(root, executeRequest()));

    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION" },
    });
    await expect(readFile(marker, "utf8")).resolves.toBe("initial");
  });

  it.each([
    ["private-path", "/private/var/folders/kpi-private-path"],
    ["workspace-path", "/workspace/private-path"],
    ["bare-token", "token=bare-secret-value"],
  ] as const)("blocks and redacts unsafe Runtime text: %s", async (behavior, unsafeText) => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, behavior);
    const result = await runHarness(root, executeRequest());
    const response = parsed(result);

    expect(response.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_SENSITIVE_OUTPUT" },
    });
    expect(result.stdout).not.toContain(unsafeText);
  });
  it.each([
    ["file-uri-path", "file:///private/var/folders/kpi-file-uri-path"],
    [
      "file-uri-single-slash-path",
      "file:/private/var/folders/kpi-file-uri-single-slash-path",
    ],
  ] as const)("rejects unsafe public command-output URI before report parsing: %s", async (behavior, unsafeText) => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, behavior);
    const result = await runHarness(root, executeRequest());
    const response = parsed(result);

    expect(response.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_SENSITIVE_OUTPUT" },
    });
    expect(result.stdout).not.toContain(unsafeText);
  });

  it("blocks and redacts unsafe public command output before report parsing", async () => {
    const root = await temporaryRoot();
    const unsafeText = "/private/var/folders/kpi-command-output";
    await createFakeRuntime(root, "unsafe-command-output");
    const result = await runHarness(root, executeRequest());
    const response = parsed(result);

    expect(response.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_SENSITIVE_OUTPUT" },
    });
    expect(result.stdout).not.toContain(unsafeText);
  });

  it("fails closed instead of approving an execution-time confirmation", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "execution-confirm");
    const result = parsed(await runHarness(root, executeRequest()));
    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_UI_APPROVAL_DENIED" },
    });
  });

  it("approves only the expected Onboard-init confirmation during its command exchange", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "onboard-init-confirm");
    const result = parsed(await runHarness(root, executeRequest()));
    expect(result.result).toMatchObject({ status: "completed" });
  });

  it("fails closed when an Onboard plan observation is absent before initialization", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "onboard-init-no-plan");
    const result = parsed(await runHarness(root, executeRequest()));
    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_UI_APPROVAL_DENIED" },
    });
  }, 20_000);

  it.each([
    "onboard-init-digest-mismatch",
    "onboard-init-title-mismatch",
  ] as const)("fails closed when the Onboard-init confirmation does not match the observed plan: %s", async (behavior) => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, behavior);
    const result = parsed(await runHarness(root, executeRequest()));
    expect(result.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_UI_APPROVAL_DENIED" },
    });
  });

  it("gives the blind Judge no tools and binds only masked artifacts to its result", async () => {
    const root = await temporaryRoot();
    await createFakeRuntime(root, "safe");
    const artifact = { finalResponse: "bounded result", commandOutcomes: [] };
    const result = parsed(
      await runHarness(root, {
        schemaVersion: 1,
        operation: "judge",
        input: {
          runId: "p0-harness-run",
          fixtureId: fixture.id,
          fixtureSha256: valueStudyFixtureSha256(fixture),
          rubric: fixture.rubric,
          first: {
            artifact,
            artifactSha256: acceptanceArtifactSha256(artifact),
          },
          second: {
            artifact,
            artifactSha256: acceptanceArtifactSha256(artifact),
          },
        },
      }),
    );
    expect(result).toMatchObject({
      operation: "judge",
      result: { status: "completed", judgeProcessId: "judge-process" },
    });
    expect(result.result).not.toHaveProperty("provider");

    const toolRoot = await temporaryRoot();
    await createFakeRuntime(toolRoot, "judge-tool");
    const blocked = parsed(
      await runHarness(toolRoot, {
        schemaVersion: 1,
        operation: "judge",
        input: {
          runId: "p0-harness-run",
          fixtureId: fixture.id,
          fixtureSha256: valueStudyFixtureSha256(fixture),
          rubric: fixture.rubric,
          first: {
            artifact,
            artifactSha256: acceptanceArtifactSha256(artifact),
          },
          second: {
            artifact,
            artifactSha256: acceptanceArtifactSha256(artifact),
          },
        },
      }),
    );
    expect(blocked.result).toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HARNESS_TOOL_POLICY_VIOLATION" },
    });
  });
  it("smoke-only: exact local OMP 17.3.5 blocks a dependency-resolved packed host before RPC without a provider", async () => {
    const root = await temporaryRoot();
    const candidate = await extractPackedPlugin(root);
    const packedPlugin = await installPackedPlugin(root, candidate.tarball);
    const home = join(root, "isolated-home");
    const project = join(root, "project");
    const agent = join(root, "agent");
    const otherRuntimeConfig = join(home, "other-runtime");
    await Promise.all([
      mkdir(agent, { recursive: true }),
      mkdir(otherRuntimeConfig, { recursive: true }),
      mkdir(join(project, ".omp"), { recursive: true }),
    ]);
    await Promise.all([
      writeFile(
        join(otherRuntimeConfig, "config.json"),
        '{"owner":"other-runtime"}\n',
        "utf8",
      ),
      writeFile(
        join(project, ".omp", "config.yml"),
        "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\n",
        "utf8",
      ),
    ]);
    const before = await Promise.all([
      snapshotDirectory(candidate.packageDirectory),
      snapshotDirectory(project),
      snapshotDirectory(agent),
      snapshotDirectory(otherRuntimeConfig),
    ]);

    await expect(
      runPackedHostSmoke({
        executable: await localOmpExecutable(),
        plugin: packedPlugin,
        project,
        home,
        agent,
      }),
    ).rejects.toThrow("No models available");

    const after = await Promise.all([
      snapshotDirectory(candidate.packageDirectory),
      snapshotDirectory(project),
      snapshotDirectory(agent),
      snapshotDirectory(otherRuntimeConfig),
    ]);
    expect(after[0]).toBe(before[0]);
    expect(after[1]).toBe(before[1]);
    expect(after[2]).not.toBe(before[2]);
    expect(after[3]).toBe(before[3]);
    await expect(readdir(agent)).resolves.toContain("agent.db");
    // A cold OMP process can cross the one-minute startup boundary under a full serial suite.
  }, 90_000);
});
