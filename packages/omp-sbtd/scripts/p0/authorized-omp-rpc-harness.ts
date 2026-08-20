#!/usr/bin/env -S node --import tsx
import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  access,
  constants,
  lstat,
  mkdir,
  mkdtemp,
  open,
  readdir,
  readFile,
  realpath,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { z } from "zod";
import {
  MAX_RENDERED_SBTD_REPORT_BYTES,
  parseRenderedSbtdReport,
} from "../../src/report/index.ts";
import {
  acceptanceArtifactSha256,
  assertJudgeScoreMatchesRubric,
  blindJudgeResultSha256,
  compatibilityCommandsSchema,
  currentRuntimeVersionSchema,
  runIdSchema,
  valueStudyFixtureSchema,
  valueStudyFixtureSha256,
} from "./release-validator.ts";
import { hasSensitiveFieldName, hasSensitiveText } from "./sanitization.ts";

const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_RESPONSE_BYTES = 128 * 1024;
const MAX_RPC_FRAME_BYTES = 128 * 1024;
const MAX_TOOL_TEXT_BYTES = 64 * 1024;
// The public report contract owns the 32 KiB UTF-8 byte budget; every captured
// public text frame shares it so a rendered report always fits one frame.
const MAX_CAPTURED_TEXT_BYTES = MAX_RENDERED_SBTD_REPORT_BYTES;
// Total bounded accumulation across the frames of one session (four read-only
// commands each within the per-frame budget).
const MAX_TOTAL_CAPTURED_TEXT_BYTES = 4 * MAX_CAPTURED_TEXT_BYTES;
const START_TIMEOUT_MS = 15_000;
const JUDGE_TIMEOUT_MS = 60_000;
const TERMINATION_GRACE_MS = 250;

// Zod string .max() counts UTF-16 code units; the public RPC byte limits are
// UTF-8 budgets, so multibyte text must not bypass them.
const utf8BoundedTextSchema = (maxBytes: number) =>
  z.string().refine((value) => Buffer.byteLength(value, "utf8") <= maxBytes, {
    message: `expected at most ${maxBytes} UTF-8 bytes`,
  });
const REQUIRED_GATE_IDS = [
  "bdd",
  "tdd",
  "legacy-change-safety",
  "refactoring-pass",
  "ddia-data-design",
  "ddd-distilled-modeling",
  "release-readiness",
] as const;
const DECLINED_ONBOARD_APPROVAL_TITLES: Readonly<Record<string, true>> = {
  "Install Shared CLI Dependencies": true,
  "Merge OMP MCP Configuration": true,
  "Initialize Trellis Projects": true,
};
const ROUTE_COST_BY_ID: Readonly<
  Record<string, "light" | "standard" | "heavy">
> = {
  "small-direct-change": "light",
  bugfix: "standard",
  "bdd-user-visible-change": "standard",
  "trellis-managed-task": "standard",
  "legacy-safe-change": "standard",
  "refactoring-pass": "standard",
  "data-design-risk": "standard",
  "web-runtime-diagnostics": "heavy",
  "web-e2e-regression": "heavy",
  "mobile-e2e": "heavy",
  "release-readiness": "heavy",
  review: "heavy",
};

const boundedTextSchema = z.string().min(1).max(4_096);
const hashSchema = z.string().regex(/^[a-f0-9]{64}$/);
const absolutePathSchema = z
  .string()
  .min(1)
  .max(4_096)
  .refine(isAbsolute, "expected an absolute path");
const blockerSchema = z
  .object({
    code: boundedTextSchema,
    reason: boundedTextSchema.optional(),
    recovery: boundedTextSchema,
  })
  .strict();
const acceptanceArtifactSchema = z
  .object({
    finalResponse: z
      .string()
      .min(1)
      .max(32 * 1024)
      .optional(),
    patch: z
      .string()
      .max(64 * 1024)
      .optional(),
    commandOutcomes: z
      .array(
        z
          .object({
            command: z.string().min(1).max(512),
            status: z.enum(["passed", "failed", "blocked"]),
          })
          .strict(),
      )
      .max(24),
  })
  .strict()
  .refine(
    (artifact) =>
      artifact.finalResponse !== undefined ||
      artifact.patch !== undefined ||
      artifact.commandOutcomes.length > 0,
    "expected a bounded acceptance artifact",
  );
const rubricCriterionSchema = z
  .object({
    id: z.string().min(1),
    description: z.string().min(1),
    weight: z.number().int().positive(),
    severe: z.boolean(),
  })
  .strict();
const judgeScoreSchema = z
  .object({
    total: z.number().min(0).max(100),
    severeAcceptanceFailure: z.boolean(),
    criteria: z
      .array(
        z
          .object({
            id: z.string().min(1),
            score: z.number().min(0).max(100),
            reason: z.string().min(1).max(4_096),
          })
          .strict(),
      )
      .min(1),
  })
  .strict();
const requestSchema = z.discriminatedUnion("operation", [
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("compatibility"),
      input: z
        .object({
          currentRuntimeVersion: currentRuntimeVersionSchema,
          pluginPackagePath: absolutePathSchema,
          pluginTarballPath: absolutePathSchema,
          sandboxRoot: absolutePathSchema,
          commands: compatibilityCommandsSchema,
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("preflight"),
      input: z
        .object({
          executionModelId: boundedTextSchema,
          judgeModelId: boundedTextSchema,
          runtimeVersion: boundedTextSchema,
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("runtime-mode"),
      input: z
        .object({
          fixtureId: boundedTextSchema,
          mode: z.enum(["advisory", "enforced"]),
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("execute"),
      input: z
        .object({
          runId: runIdSchema,
          fixture: valueStudyFixtureSchema,
          fixtureSha256: hashSchema,
          arm: z.enum(["control", "treatment"]),
          mode: z.enum(["advisory", "enforced"]),
          attempt: z.number().int().positive().max(2),
          workspacePath: absolutePathSchema,
          limits: z
            .object({
              wallClockMs: z.number().int().positive().max(600_000),
              maxTurns: z.number().int().positive(),
              maxTokens: z.number().int().positive(),
            })
            .strict(),
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("judge"),
      input: z
        .object({
          runId: runIdSchema,
          fixtureId: boundedTextSchema,
          fixtureSha256: hashSchema,
          rubric: z.array(rubricCriterionSchema).min(1),
          first: z
            .object({
              artifact: acceptanceArtifactSchema,
              artifactSha256: hashSchema,
            })
            .strict(),
          second: z
            .object({
              artifact: acceptanceArtifactSchema,
              artifactSha256: hashSchema,
            })
            .strict(),
        })
        .strict(),
    })
    .strict(),
]);
const readyFrameSchema = z
  .object({
    type: z.literal("ready"),
    protocolVersion: z.literal(1),
    supportedProtocolVersions: z.tuple([z.literal(1), z.literal(2)]),
    maxFrameBytes: z.number().int().positive(),
    maxReassembledFrameBytes: z.number().int().positive(),
  })
  .strict();
const responseFrameSchema = z
  .object({
    id: z.string().min(1).max(128).optional(),
    type: z.literal("response"),
    command: z.string().min(1).max(128),
    success: z.boolean(),
    data: z.unknown().optional(),
    error: z.string().min(1).max(4_096).optional(),
    code: z.string().min(1).max(256).optional(),
  })
  .strict();
const promptResultFrameSchema = z
  .object({
    type: z.literal("prompt_result"),
    id: z.string().min(1).max(128),
    agentInvoked: z.boolean(),
  })
  .strict();
const commandOutputFrameSchema = z
  .object({
    type: z.literal("command_output"),
    text: utf8BoundedTextSchema(MAX_CAPTURED_TEXT_BYTES),
  })
  .strict();
const notificationFrameSchema = z
  .object({
    type: z.literal("extension_ui_request"),
    id: z.string().min(1).max(128),
    method: z.literal("notify"),
    message: utf8BoundedTextSchema(MAX_CAPTURED_TEXT_BYTES),
    notifyType: z.enum(["info", "warning", "error"]).optional(),
  })
  .strict();
const statusUpdateFrameSchema = z
  .object({
    type: z.literal("extension_ui_request"),
    id: z.string().min(1).max(128),
    method: z.literal("setStatus"),
    statusKey: z.string().min(1).max(256),
    statusText: utf8BoundedTextSchema(MAX_CAPTURED_TEXT_BYTES).optional(),
  })
  .strict();
const widgetUpdateFrameSchema = z
  .object({
    type: z.literal("extension_ui_request"),
    id: z.string().min(1).max(128),
    method: z.literal("setWidget"),
    widgetKey: z.string().min(1).max(256),
    widgetLines: z
      .array(utf8BoundedTextSchema(MAX_CAPTURED_TEXT_BYTES))
      .max(100)
      .optional(),
    widgetPlacement: z.enum(["aboveEditor", "belowEditor"]).optional(),
  })
  .strict();
const confirmationFrameSchema = z
  .object({
    type: z.literal("extension_ui_request"),
    id: z.string().min(1).max(128),
    method: z.literal("confirm"),
    title: z.string().max(4_096),
    message: utf8BoundedTextSchema(MAX_CAPTURED_TEXT_BYTES),
    timeout: z.number().int().positive().optional(),
  })
  .strict();
const hostToolCallSchema = z
  .object({
    type: z.literal("host_tool_call"),
    id: z.string().min(1).max(128),
    toolCallId: z.string().min(1).max(128),
    toolName: z.string().min(1).max(128),
    arguments: z.record(z.string(), z.unknown()),
  })
  .strict();
const terminalFrameSchema = z
  .object({
    type: z.literal("agent_end"),
    isTerminal: z.boolean().optional(),
    willContinue: z.boolean().optional(),
    messages: z.array(z.unknown()).optional(),
  })
  .passthrough();
const usageFrameSchema = z
  .object({ type: z.literal("message_end"), message: z.unknown() })
  .passthrough();
const harmlessFrameTypes = new Set([
  "message_start",
  "message_delta",
  "thinking_delta",
  "turn_start",
  "turn_end",
  "tool_execution_start",
  "tool_execution_end",
  "available_commands_update",
  "session_info_update",
  "config_update",
  "notice",
  "thinking_level_changed",
  "goal_updated",
]);

type HarnessRequest = z.infer<typeof requestSchema>;
type HarnessConfig = Readonly<{
  runtimeVersion: string;
  runtimeRoot: string;
  runtimeExecutable: string;
  executionModelId: string;
  judgeModelId: string;
  executionProcessId: string;
  judgeProcessId: string;
  pluginDirectory?: string;
  extensionPath?: string;
}>;
type Workspace = Readonly<{
  root: string;
  project: string;
  agent: string;
  home: string;
  cache: string;
  data: string;
}>;
type Blocker = z.infer<typeof blockerSchema>;
type PromptOutcomeWaiter = {
  awaiting: boolean;
  settled: boolean;
  promise: Promise<Readonly<{ agentInvoked: boolean }>>;
  resolve: (outcome: Readonly<{ agentInvoked: boolean }>) => void;
  reject: (error: HarnessFailure) => void;
};
type PendingRpcCommand = {
  command: string;
  resolve: (data: unknown) => void;
  reject: (error: HarnessFailure) => void;
  promptOutcome: PromptOutcomeWaiter | undefined;
};

class HarnessFailure extends Error {
  constructor(
    readonly code: string,
    readonly reason: string,
    readonly recovery: string,
  ) {
    super(reason);
  }
}

function failure(code: string, reason: string, recovery: string): never {
  throw new HarnessFailure(code, reason, recovery);
}

function toFailure(error: unknown): HarnessFailure {
  if (error instanceof HarnessFailure) return error;
  return new HarnessFailure(
    "OMP_HARNESS_INTERNAL_FAILURE",
    "The authorized OMP RPC harness stopped before producing a safe result.",
    "Correct the isolated harness configuration and rerun the parent-authorized command.",
  );
}

function asBlocker(error: unknown): Blocker {
  const safe = toFailure(error);
  return { code: safe.code, reason: safe.reason, recovery: safe.recovery };
}

function stableJson(value: unknown): string {
  const sort = (input: unknown): unknown => {
    if (Array.isArray(input)) return input.map(sort);
    if (input !== null && typeof input === "object")
      return Object.fromEntries(
        Object.entries(input as Record<string, unknown>)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([key, nested]) => [key, sort(nested)]),
      );
    return input;
  };
  return `${JSON.stringify(sort(value), null, 2)}\n`;
}

function digest(value: string | Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

function isWithin(root: string, candidate: string, allowRoot = false): boolean {
  const path = relative(resolve(root), resolve(candidate));
  return (
    (allowRoot && path === "") ||
    (path !== "" &&
      path !== ".." &&
      !path.startsWith(`..${sep}`) &&
      !isAbsolute(path))
  );
}

function assertSafeText(value: string): void {
  if (hasSensitiveText(value))
    failure(
      "OMP_HARNESS_SENSITIVE_OUTPUT",
      "The harness refused to return a sensitive value, Provider detail, or local path.",
      "Remove sensitive or Provider-specific content from the public OMP result and rerun.",
    );
}

function assertSafeArtifact(value: unknown): void {
  if (typeof value === "string") {
    assertSafeText(value);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach(assertSafeArtifact);
    return;
  }
  if (value === null || typeof value !== "object") return;
  for (const [key, nested] of Object.entries(
    value as Record<string, unknown>,
  )) {
    if (hasSensitiveFieldName(key))
      failure(
        "OMP_HARNESS_SENSITIVE_OUTPUT",
        "The harness refused a sensitive or Provider-specific output field.",
        "Return only the documented sanitized acceptance-artifact fields.",
      );
    assertSafeArtifact(nested);
  }
}

async function readRequest(): Promise<HarnessRequest> {
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.byteLength;
    if (bytes > MAX_REQUEST_BYTES)
      failure(
        "OMP_HARNESS_REQUEST_TOO_LARGE",
        "The parent request exceeds the bounded authorized-harness protocol limit.",
        "Reduce the request to the documented bounded protocol schema.",
      );
    chunks.push(buffer);
  }
  let raw: unknown;
  try {
    raw = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    failure(
      "OMP_HARNESS_REQUEST_INVALID",
      "The parent request is not one valid JSON protocol object.",
      "Send exactly one schema-versioned authorized-harness request.",
    );
  }
  const parsed = requestSchema.safeParse(raw);
  if (!parsed.success)
    failure(
      "OMP_HARNESS_REQUEST_INVALID",
      "The parent request does not satisfy the strict authorized-harness protocol.",
      "Use the existing authorized host adapter request schema without extra fields.",
    );
  return parsed.data;
}

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0)
    failure(
      "OMP_HARNESS_IDENTITY_REQUIRED",
      "A required explicit harness identity is unavailable.",
      "Configure the parent-authorized harness with explicit Runtime, model, and logical process identities.",
    );
  return value;
}

async function regularFile(
  path: string,
  code: string,
  mustBeExecutable: boolean,
): Promise<void> {
  try {
    const details = await lstat(path);
    if (!details.isFile() || details.isSymbolicLink())
      throw new Error("not regular");
    if (mustBeExecutable) await access(path, constants.X_OK);
  } catch {
    failure(
      code,
      mustBeExecutable
        ? "The explicitly configured OMP Runtime executable is unavailable."
        : "The explicitly configured packed Plugin extension is unavailable.",
      mustBeExecutable
        ? "Provide a regular executable under the configured versioned Runtime root."
        : "Provide a regular compiled extension in the configured packed Plugin directory.",
    );
  }
}

async function harnessConfig(needsPlugin: boolean): Promise<HarnessConfig> {
  const runtimeVersion = requiredEnvironment("KPI_OMP_RUNTIME_VERSION");
  const executionModelId = requiredEnvironment("KPI_OMP_EXECUTION_MODEL_ID");
  const judgeModelId = requiredEnvironment("KPI_OMP_JUDGE_MODEL_ID");
  const executionProcessId = requiredEnvironment(
    "KPI_OMP_EXECUTION_PROCESS_ID",
  );
  const judgeProcessId = requiredEnvironment("KPI_OMP_JUDGE_PROCESS_ID");
  const runtimeRootInput = requiredEnvironment("KPI_OMP_RUNTIME_ROOT");
  if (!/^\d+\.\d+\.\d+$/.test(runtimeVersion))
    failure(
      "OMP_HARNESS_IDENTITY_REQUIRED",
      "The explicit Runtime version is not an exact semantic version.",
      "Set KPI_OMP_RUNTIME_VERSION to the exact selected OMP Runtime version.",
    );
  for (const model of [executionModelId, judgeModelId]) {
    if (
      !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(
        model,
      )
    )
      failure(
        "OMP_HARNESS_IDENTITY_REQUIRED",
        "The explicit model identity is not an exact provider/model selector.",
        "Set each model identity as one bounded provider/model selector without credentials.",
      );
    assertSafeText(model);
  }
  if (
    executionModelId === judgeModelId ||
    executionProcessId === judgeProcessId
  )
    failure(
      "OMP_HARNESS_JUDGE_NOT_INDEPENDENT",
      "Execution and Judge must use different fixed model and logical process identities.",
      "Configure distinct execution and Judge model/process identifiers.",
    );
  if (!isAbsolute(runtimeRootInput))
    failure(
      "OMP_HARNESS_RUNTIME_UNAVAILABLE",
      "The versioned Runtime root is not an absolute path.",
      "Configure KPI_OMP_RUNTIME_ROOT as an absolute versioned Runtime root.",
    );
  let runtimeRoot: string;
  try {
    runtimeRoot = await realpath(runtimeRootInput);
    if (!(await stat(runtimeRoot)).isDirectory())
      throw new Error("not directory");
  } catch {
    failure(
      "OMP_HARNESS_RUNTIME_UNAVAILABLE",
      "The explicit versioned Runtime root is unavailable.",
      "Install or expose the selected Runtime under the authorized local Runtime root.",
    );
  }
  const runtimeExecutable = resolve(runtimeRoot, runtimeVersion, "bin", "omp");
  if (!isWithin(runtimeRoot, runtimeExecutable))
    failure(
      "OMP_HARNESS_RUNTIME_UNAVAILABLE",
      "The explicit Runtime version escaped the configured Runtime root.",
      "Correct the versioned Runtime root layout.",
    );
  await regularFile(runtimeExecutable, "OMP_HARNESS_RUNTIME_UNAVAILABLE", true);

  if (!needsPlugin)
    return {
      runtimeVersion,
      runtimeRoot,
      runtimeExecutable,
      executionModelId,
      judgeModelId,
      executionProcessId,
      judgeProcessId,
    };
  const pluginInput = requiredEnvironment("KPI_OMP_PLUGIN_DIR");
  if (!isAbsolute(pluginInput))
    failure(
      "OMP_HARNESS_PLUGIN_UNAVAILABLE",
      "The explicit packed Plugin directory is not an absolute path.",
      "Configure KPI_OMP_PLUGIN_DIR as an extracted Plugin directory.",
    );
  let pluginDirectory: string;
  try {
    pluginDirectory = await realpath(pluginInput);
    if (!(await stat(pluginDirectory)).isDirectory())
      throw new Error("not directory");
  } catch {
    failure(
      "OMP_HARNESS_PLUGIN_UNAVAILABLE",
      "The explicit packed Plugin directory is unavailable.",
      "Provide an extracted packed Plugin directory to the authorized harness.",
    );
  }
  const extensionPath = join(pluginDirectory, "dist", "extension.js");
  await regularFile(extensionPath, "OMP_HARNESS_PLUGIN_UNAVAILABLE", false);
  return {
    runtimeVersion,
    runtimeRoot,
    runtimeExecutable,
    executionModelId,
    judgeModelId,
    executionProcessId,
    judgeProcessId,
    pluginDirectory,
    extensionPath,
  };
}

async function resolveCompatibilityAgentDirectory(): Promise<
  string | undefined
> {
  const input = process.env.KPI_OMP_COMPAT_AGENT_DIR;
  if (input === undefined) return undefined;
  if (!isAbsolute(input))
    failure(
      "OMP_HARNESS_COMPAT_AGENT_DIR_INVALID",
      "The explicit compatibility agent directory is not an absolute path.",
      "Configure KPI_OMP_COMPAT_AGENT_DIR as a regular absolute directory.",
    );
  try {
    const details = await lstat(input);
    if (!details.isDirectory() || details.isSymbolicLink())
      throw new Error("not a regular directory");
    return await realpath(input);
  } catch {
    failure(
      "OMP_HARNESS_COMPAT_AGENT_DIR_INVALID",
      "The explicit compatibility agent directory is unavailable.",
      "Configure KPI_OMP_COMPAT_AGENT_DIR as a regular absolute directory.",
    );
  }
}

async function makeWorkspace(): Promise<Workspace> {
  const root = await mkdtemp(join(tmpdir(), "kpi-omp-rpc-"));
  const workspace = {
    root,
    project: join(root, "project"),
    agent: join(root, "agent"),
    home: join(root, "home"),
    cache: join(root, "cache"),
    data: join(root, "data"),
  } as const;
  await Promise.all(
    Object.values(workspace)
      .slice(1)
      .map((path) => mkdir(path, { recursive: true, mode: 0o700 })),
  );
  return workspace;
}

async function inWorkspace<T>(
  work: (workspace: Workspace) => Promise<T>,
): Promise<T> {
  const workspace = await makeWorkspace();
  let completed = false;
  try {
    const result = await work(workspace);
    completed = true;
    return result;
  } finally {
    try {
      await rm(workspace.root, { force: true, recursive: true, maxRetries: 2 });
    } catch {
      if (completed)
        failure(
          "OMP_HARNESS_CLEANUP_FAILED",
          "The invocation-scoped OMP workspace could not be removed.",
          "Repair the local temporary-directory permissions before rerunning the harness.",
        );
    }
  }
}

async function writeCompatibilityProviderConfig(
  workspace: Workspace,
): Promise<void> {
  const configDirectory = join(workspace.project, ".omp");
  await mkdir(configDirectory, { recursive: true, mode: 0o700 });
  await writeFile(
    join(configDirectory, "config.yml"),
    "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\n",
    { encoding: "utf8", mode: 0o600 },
  );
}

async function resolveCandidateTarball(input: string): Promise<string> {
  try {
    const details = await lstat(input);
    if (!details.isFile() || details.isSymbolicLink())
      throw new Error("not regular");
    return await realpath(input);
  } catch {
    failure(
      "OMP_HARNESS_PLUGIN_UNAVAILABLE",
      "The explicit candidate Plugin tarball is unavailable.",
      "Configure one regular exact tarball for the authorized compatibility host.",
    );
  }
}

async function installCandidatePlugin(
  workspace: Workspace,
  candidateTarballPath: string,
  compatibilityAgentDirectory: string | undefined,
): Promise<string> {
  const pluginRoot = join(
    compatibilityAgentDirectory ?? workspace.agent,
    "plugins",
  );
  await mkdir(pluginRoot, { recursive: true, mode: 0o700 });
  await writeFile(
    join(pluginRoot, "package.json"),
    `${JSON.stringify(
      {
        name: "kpi-omp-compatibility-plugins",
        private: true,
        dependencies: { "@kunolu/omp-sbtd": `file:${candidateTarballPath}` },
      },
      null,
      2,
    )}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
  const exitCode = await new Promise<number | null>((complete) => {
    const installer = spawn("bun", ["install", "--ignore-scripts"], {
      cwd: pluginRoot,
      env: childEnvironment(workspace, compatibilityAgentDirectory),
      shell: false,
      stdio: "ignore",
    });
    installer.once("error", () => complete(null));
    installer.once("close", complete);
  });
  if (exitCode !== 0)
    failure(
      "OMP_HARNESS_PLUGIN_UNAVAILABLE",
      "The exact candidate Plugin tarball could not be dependency-resolved in the isolated host workspace.",
      "Provide a locally resolvable exact tarball and compatible cached dependencies.",
    );
  const extensionPath = join(
    pluginRoot,
    "node_modules",
    "@kunolu",
    "omp-sbtd",
    "dist",
    "extension.js",
  );
  await regularFile(extensionPath, "OMP_HARNESS_PLUGIN_UNAVAILABLE", false);
  return extensionPath;
}

function childEnvironment(
  workspace: Workspace,
  compatibilityAgentDirectory?: string,
): Readonly<Record<string, string>> {
  return {
    PATH: process.env.PATH ?? "",
    HOME: workspace.home,
    XDG_CACHE_HOME: workspace.cache,
    XDG_CONFIG_HOME: join(workspace.home, ".config"),
    XDG_DATA_HOME: workspace.data,
    PI_CODING_AGENT_DIR: compatibilityAgentDirectory ?? workspace.agent,
    CI: "1",
    NO_COLOR: "1",
    npm_config_offline: "true",
    pnpm_config_offline: "true",
    PIP_NO_INDEX: "1",
  };
}

function processTreeSignal(
  child: ChildProcessWithoutNullStreams,
  signal: NodeJS.Signals,
): void {
  try {
    if (process.platform !== "win32" && child.pid !== undefined)
      process.kill(-child.pid, signal);
  } catch {
    // A process-group race is safe; signal the direct child below.
  }
  if (child.exitCode === null && child.signalCode === null) child.kill(signal);
}

function waitForClose(child: ChildProcessWithoutNullStreams): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null)
    return Promise.resolve();
  const { promise, resolve } = Promise.withResolvers<void>();
  child.once("close", resolve);
  return promise;
}

async function terminate(child: ChildProcessWithoutNullStreams): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return;
  const closed = waitForClose(child);
  processTreeSignal(child, "SIGTERM");
  const { promise: grace, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, TERMINATION_GRACE_MS);
  await Promise.race([closed, grace]);
  if (child.exitCode === null && child.signalCode === null)
    processTreeSignal(child, "SIGKILL");
  await closed;
}

async function verifyRuntime(config: HarnessConfig): Promise<void> {
  await inWorkspace(async (workspace) => {
    const { promise, reject, resolve } = Promise.withResolvers<{
      code: number | null;
      stdout: string;
    }>();
    let child: ChildProcessWithoutNullStreams;
    try {
      child = spawn(config.runtimeExecutable, ["--version"], {
        cwd: workspace.project,
        detached: process.platform !== "win32",
        env: childEnvironment(workspace),
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch {
      failure(
        "OMP_HARNESS_OMP_UNAVAILABLE",
        "The explicit OMP Runtime could not be started.",
        "Repair the selected Runtime installation and rerun the authorized harness.",
      );
    }
    let stdout = "";
    let bytes = 0;
    const timeout = setTimeout(() => {
      void terminate(child);
      reject(
        new HarnessFailure(
          "OMP_HARNESS_TIMEOUT",
          "The explicit OMP Runtime did not return its version in time.",
          "Repair the selected Runtime or choose an available exact version.",
        ),
      );
    }, START_TIMEOUT_MS);
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      bytes += Buffer.byteLength(chunk);
      if (bytes > 4_096) {
        void terminate(child);
        reject(
          new HarnessFailure(
            "OMP_HARNESS_OMP_UNAVAILABLE",
            "The explicit OMP Runtime returned an invalid version response.",
            "Use an exact supported OMP Runtime binary.",
          ),
        );
      } else stdout += chunk;
    });
    child.once("error", () =>
      reject(
        new HarnessFailure(
          "OMP_HARNESS_OMP_UNAVAILABLE",
          "The explicit OMP Runtime could not be started.",
          "Repair the selected Runtime installation and rerun the authorized harness.",
        ),
      ),
    );
    child.once("close", (code) => resolve({ code, stdout }));
    let result: { code: number | null; stdout: string };
    try {
      result = await promise;
    } finally {
      clearTimeout(timeout);
      await terminate(child);
    }
    const versions = result.stdout.match(/\b\d+\.\d+\.\d+\b/g) ?? [];
    if (
      result.code !== 0 ||
      versions.length !== 1 ||
      versions[0] !== config.runtimeVersion
    )
      failure(
        "OMP_HARNESS_RUNTIME_VERSION_MISMATCH",
        "The OMP public Runtime version did not match the explicit requested version.",
        "Configure an exact matching Runtime binary under the authorized Runtime root.",
      );
  });
}

class RpcSession {
  private readonly pending = new Map<string, PendingRpcCommand>();
  private readonly texts: string[] = [];
  private capturedTextBytes = 0;
  private readonly textWaiters: Array<
    Readonly<{
      textIndex: number;
      matches: (text: string) => boolean;
      resolve: () => void;
      reject: (error: HarnessFailure) => void;
    }>
  > = [];
  private readonly onboardingPlanWaiters: Array<
    Readonly<{ resolve: () => void; reject: (error: HarnessFailure) => void }>
  > = [];
  private readonly onboardingInitWaiters: Array<
    Readonly<{ resolve: () => void; reject: (error: HarnessFailure) => void }>
  > = [];
  private readonly terminalWaiters: Array<
    Readonly<{ resolve: () => void; reject: (error: HarnessFailure) => void }>
  > = [];
  private frameBuffer = "";
  private requestNumber = 0;
  private ready = false;
  private terminalReached = false;
  private closed = false;
  private onboardingPlanObservationPending = false;
  private onboardingInitConfirmationPending = false;
  private onboardingInitConfirmed = false;
  private onboardingPlan:
    | Readonly<{ digest: string; targetCount: number }>
    | undefined;
  private fatal: HarnessFailure | undefined;
  private outputQueue: Promise<void> = Promise.resolve();
  private usage = { turns: 0, tokens: 0 };
  private readonly toolExecutor: ToolExecutor | undefined;

  private constructor(
    private readonly child: ChildProcessWithoutNullStreams,
    toolExecutor: ToolExecutor | undefined,
  ) {
    this.toolExecutor = toolExecutor;
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => this.consume(chunk));
    child.stderr.on("data", () => {
      // Child diagnostics stay private; stdout remains the only parsed public RPC channel.
    });
    child.stdout.once("error", () =>
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "The OMP public RPC output stream failed.",
      ),
    );
    child.stdin.once("error", () =>
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "The OMP public RPC input stream failed.",
      ),
    );
    child.once("error", () =>
      this.fail(
        "OMP_HARNESS_OMP_UNAVAILABLE",
        "The OMP public RPC process could not be started.",
      ),
    );
    child.once("close", () => {
      if (!this.closed && this.fatal === undefined)
        this.fail(
          "OMP_HARNESS_OMP_UNAVAILABLE",
          "The OMP public RPC process ended before the bounded exchange completed.",
        );
    });
  }

  static async start(
    config: HarnessConfig,
    workspace: Workspace,
    options: Readonly<{
      modelId?: string;
      plugin: false | "direct" | "installed";
      installedExtensionPath?: string;
      toolExecutor?: ToolExecutor;
      compatibilityAgentDirectory?: string;
    }>,
  ): Promise<RpcSession> {
    const args = [
      "--mode",
      "rpc",
      "--cwd",
      workspace.project,
      "--no-session",
      "--no-tools",
      "--no-skills",
      "--no-rules",
      "--no-pty",
      "--no-title",
    ];
    if (options.modelId !== undefined) args.push("--model", options.modelId);
    if (options.plugin === "direct") {
      if (config.extensionPath === undefined)
        failure(
          "OMP_HARNESS_PLUGIN_UNAVAILABLE",
          "The requested OMP operation requires an explicit packed Plugin.",
          "Provide KPI_OMP_PLUGIN_DIR with the compiled Plugin extension.",
        );
      args.push("--extension", config.extensionPath);
    }
    if (options.plugin === "installed") {
      if (options.installedExtensionPath === undefined)
        failure(
          "OMP_HARNESS_PLUGIN_UNAVAILABLE",
          "The installed candidate Plugin extension is unavailable.",
          "Install the exact candidate tarball before starting OMP.",
        );
      args.push("--extension", options.installedExtensionPath);
    }
    let child: ChildProcessWithoutNullStreams;
    try {
      child = spawn(config.runtimeExecutable, args, {
        cwd: workspace.project,
        detached: process.platform !== "win32",
        env: childEnvironment(workspace, options.compatibilityAgentDirectory),
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
      });
    } catch {
      failure(
        "OMP_HARNESS_OMP_UNAVAILABLE",
        "The explicit OMP Runtime could not start public RPC mode.",
        "Repair the selected OMP Runtime and rerun the authorized harness.",
      );
    }
    const session = new RpcSession(child, options.toolExecutor);
    try {
      await session.waitReady();
      if (options.modelId !== undefined)
        await session.assertExactModel(options.modelId);
      return session;
    } catch (error) {
      await session.stop();
      throw error;
    }
  }

  get usageTotals(): Readonly<{ turns: number; tokens: number }> {
    return { ...this.usage };
  }

  textSince(index: number): readonly string[] {
    return this.texts.slice(index);
  }

  textCount(): number {
    return this.texts.length;
  }

  async waitForTextSince(
    textIndex: number,
    matches: (text: string) => boolean,
    timeoutMs: number,
  ): Promise<void> {
    if (matches(this.texts.slice(textIndex).join("\n"))) return;
    const { promise, reject, resolve } = Promise.withResolvers<void>();
    const waiter = { textIndex, matches, resolve, reject };
    const timeout = setTimeout(() => {
      const index = this.textWaiters.indexOf(waiter);
      if (index >= 0) this.textWaiters.splice(index, 1);
      reject(
        new HarnessFailure(
          "OMP_HARNESS_REPORT_INVALID",
          "The public /sbtd report did not produce the expected bounded output.",
          "Use a compatible packed Plugin that renders the current sanitized /sbtd report.",
        ),
      );
    }, timeoutMs);
    this.textWaiters.push(waiter);
    try {
      await promise;
    } finally {
      clearTimeout(timeout);
      const index = this.textWaiters.indexOf(waiter);
      if (index >= 0) this.textWaiters.splice(index, 1);
    }
  }

  async stop(): Promise<void> {
    this.closed = true;
    try {
      this.child.stdin.end();
    } catch {
      // The process is always terminated below.
    }
    await terminate(this.child);
  }

  async setHostTools(): Promise<void> {
    if (this.toolExecutor === undefined)
      failure(
        "OMP_HARNESS_TOOL_POLICY_VIOLATION",
        "The execution process attempted to register host tools outside the approved policy.",
        "Use only the bounded execution host-tool allowlist.",
      );
    const tools = this.toolExecutor.definitions;
    const data = await this.command("set_host_tools", { tools }, 10_000);
    const parsed = z
      .object({ toolNames: z.array(z.string()) })
      .strict()
      .safeParse(data);
    if (
      !parsed.success ||
      parsed.data.toolNames.length !== tools.length ||
      parsed.data.toolNames.some((name, index) => name !== tools[index]?.name)
    )
      failure(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP did not acknowledge the exact bounded host-tool allowlist.",
        "Use a compatible OMP public RPC Runtime with host-tool registration support.",
      );
  }

  async disableAutoRetry(): Promise<void> {
    await this.command("set_auto_retry", { enabled: false }, 10_000);
  }

  async prompt(
    message: string,
    timeoutMs: number,
  ): Promise<Readonly<{ agentInvoked: boolean }>> {
    const observingOnboardPlan = message === "/sbtd onboard plan";
    if (observingOnboardPlan) {
      this.onboardingPlanObservationPending = true;
      this.onboardingPlan = undefined;
    }
    if (message === "/sbtd onboard init") {
      this.onboardingInitConfirmationPending = true;
      this.onboardingInitConfirmed = false;
    }
    const data = await this.command("prompt", { message }, timeoutMs);
    if (data === undefined) return { agentInvoked: true };
    const parsed = z
      .object({ agentInvoked: z.boolean() })
      .strict()
      .safeParse(data);
    if (!parsed.success)
      failure(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP returned an invalid public prompt acknowledgment.",
        "Use a compatible OMP public RPC Runtime.",
      );
    return parsed.data;
  }

  async waitForOnboardPlan(timeoutMs: number): Promise<void> {
    if (this.fatal !== undefined) throw this.fatal;
    if (this.onboardingPlan !== undefined) {
      this.onboardingPlanObservationPending = false;
      return;
    }
    const { promise, reject, resolve } = Promise.withResolvers<void>();
    const waiter = { resolve, reject };
    const timeout = setTimeout(() => {
      const index = this.onboardingPlanWaiters.indexOf(waiter);
      if (index >= 0) this.onboardingPlanWaiters.splice(index, 1);
      reject(
        new HarnessFailure(
          "OMP_HARNESS_UI_APPROVAL_DENIED",
          "The parent-authorized Onboard plan did not expose one bounded digest and target count.",
          "Use a compatible packed Plugin that renders the exact Onboard plan before initialization.",
        ),
      );
    }, timeoutMs);
    this.onboardingPlanWaiters.push(waiter);
    try {
      await promise;
    } finally {
      clearTimeout(timeout);
      this.onboardingPlanObservationPending = false;
      const index = this.onboardingPlanWaiters.indexOf(waiter);
      if (index >= 0) this.onboardingPlanWaiters.splice(index, 1);
    }
  }

  async waitForOnboardInitConfirmation(timeoutMs: number): Promise<void> {
    if (this.fatal !== undefined) throw this.fatal;
    if (this.onboardingInitConfirmed) return;
    const { promise, reject, resolve } = Promise.withResolvers<void>();
    const waiter = { resolve, reject };
    const timeout = setTimeout(() => {
      const index = this.onboardingInitWaiters.indexOf(waiter);
      if (index >= 0) this.onboardingInitWaiters.splice(index, 1);
      reject(
        new HarnessFailure(
          "OMP_HARNESS_UI_APPROVAL_DENIED",
          "The parent-authorized Onboard initialization did not request the exact expected confirmation.",
          "Use a compatible packed Plugin that requests the exact observed Onboard plan confirmation.",
        ),
      );
    }, timeoutMs);
    this.onboardingInitWaiters.push(waiter);
    try {
      await promise;
    } finally {
      clearTimeout(timeout);
      this.onboardingInitConfirmationPending = false;
      const index = this.onboardingInitWaiters.indexOf(waiter);
      if (index >= 0) this.onboardingInitWaiters.splice(index, 1);
    }
  }

  async waitForTerminal(timeoutMs: number): Promise<void> {
    if (this.fatal !== undefined) throw this.fatal;
    if (this.terminalReached) return;
    const { promise, reject, resolve } = Promise.withResolvers<void>();
    const waiter = { resolve, reject };
    const timer = setTimeout(() => {
      const index = this.terminalWaiters.indexOf(waiter);
      if (index >= 0) this.terminalWaiters.splice(index, 1);
      reject(
        new HarnessFailure(
          "OMP_HARNESS_TIMEOUT",
          "The OMP public RPC session exceeded its bounded execution time.",
          "Correct the task or Runtime behavior, then start a new isolated arm.",
        ),
      );
    }, timeoutMs);
    this.terminalWaiters.push(waiter);
    try {
      await promise;
    } finally {
      clearTimeout(timer);
      const index = this.terminalWaiters.indexOf(waiter);
      if (index >= 0) this.terminalWaiters.splice(index, 1);
    }
  }

  async lastAssistantText(): Promise<string | undefined> {
    const data = await this.command("get_last_assistant_text", {}, 10_000);
    const parsed = z
      .object({
        text: utf8BoundedTextSchema(MAX_CAPTURED_TEXT_BYTES).nullable(),
      })
      .strict()
      .safeParse(data);
    if (!parsed.success)
      failure(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP returned an invalid public assistant-text response.",
        "Use a compatible OMP public RPC Runtime.",
      );
    return parsed.data.text ?? undefined;
  }

  private async assertExactModel(expected: string): Promise<void> {
    const data = await this.command("get_state", {}, 10_000);
    const parsed = z
      .object({
        model: z
          .object({ provider: z.string().min(1), id: z.string().min(1) })
          .passthrough()
          .optional(),
      })
      .passthrough()
      .safeParse(data);
    const model = parsed.success ? parsed.data.model : undefined;
    const identities =
      model === undefined ? [] : [model.id, `${model.provider}/${model.id}`];
    if (!identities.includes(expected))
      failure(
        "OMP_HARNESS_MODEL_UNAVAILABLE",
        "OMP could not prove the exact caller-selected model identity.",
        "Make the exact selected model available to the authorized OMP Runtime without fallback selection.",
      );
  }

  private async waitReady(): Promise<void> {
    if (this.ready) return;
    const { promise, reject, resolve } = Promise.withResolvers<void>();
    const timer = setTimeout(() => {
      reject(
        new HarnessFailure(
          "OMP_HARNESS_OMP_UNAVAILABLE",
          "OMP did not emit a bounded public RPC ready frame.",
          "Use an available OMP Runtime that supports public RPC mode.",
        ),
      );
    }, START_TIMEOUT_MS);
    const check = () => {
      if (this.fatal !== undefined) {
        clearTimeout(timer);
        reject(this.fatal);
      } else if (this.ready) {
        clearTimeout(timer);
        resolve();
      } else setTimeout(check, 5);
    };
    check();
    await promise;
  }

  private async command(
    command: string,
    payload: Record<string, unknown>,
    timeoutMs: number,
  ): Promise<unknown> {
    if (this.fatal !== undefined) throw this.fatal;
    const id = `kpi-${++this.requestNumber}`;
    const {
      promise: response,
      reject,
      resolve,
    } = Promise.withResolvers<unknown>();
    const pending: PendingRpcCommand = {
      command,
      resolve,
      reject,
      promptOutcome: undefined,
    };
    this.pending.set(id, pending);
    await this.send({ id, type: command, ...payload });
    const { promise: deadline, reject: rejectDeadline } =
      Promise.withResolvers<never>();
    const timer = setTimeout(
      () =>
        rejectDeadline(
          new HarnessFailure(
            "OMP_HARNESS_TIMEOUT",
            "The OMP public RPC command exceeded its bounded deadline.",
            "Correct the Runtime or task state and start a new isolated invocation.",
          ),
        ),
      timeoutMs,
    );
    try {
      const data = await Promise.race([response, deadline]);
      if (this.fatal !== undefined) throw this.fatal;
      if (pending.promptOutcome !== undefined && data === undefined) {
        const outcome = await Promise.race([
          pending.promptOutcome.promise,
          deadline,
        ]);
        if (this.fatal !== undefined) throw this.fatal;
        return outcome;
      }
      return data;
    } finally {
      clearTimeout(timer);
      this.pending.delete(id);
    }
  }

  private async send(frame: unknown): Promise<void> {
    if (this.fatal !== undefined) throw this.fatal;
    const serialized = JSON.stringify(frame);
    if (Buffer.byteLength(serialized) > MAX_RPC_FRAME_BYTES)
      failure(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "The harness refused an oversized public RPC command frame.",
        "Reduce the bounded request to the documented public RPC limit.",
      );
    this.outputQueue = this.outputQueue.then(() => {
      if (this.fatal !== undefined) throw this.fatal;
      const { promise, reject, resolve } = Promise.withResolvers<void>();
      this.child.stdin.write(`${serialized}\n`, (error) =>
        error === undefined || error === null ? resolve() : reject(error),
      );
      return promise;
    });
    try {
      await this.outputQueue;
    } catch {
      failure(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "The harness could not write a public RPC command frame.",
        "Repair the selected OMP Runtime transport and rerun.",
      );
    }
  }

  private consume(chunk: string): void {
    this.frameBuffer += chunk;
    if (Buffer.byteLength(this.frameBuffer) > MAX_RPC_FRAME_BYTES) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted an oversized or unterminated public RPC frame.",
      );
      return;
    }
    let newline = this.frameBuffer.indexOf("\n");
    while (newline >= 0) {
      const line = this.frameBuffer.slice(0, newline);
      this.frameBuffer = this.frameBuffer.slice(newline + 1);
      if (line.length > 0) this.handleLine(line);
      newline = this.frameBuffer.indexOf("\n");
    }
  }

  private handleLine(line: string): void {
    let frame: unknown;
    try {
      frame = JSON.parse(line);
    } catch {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted malformed public RPC JSON.",
      );
      return;
    }
    const typeFrame = z
      .object({ type: z.string().min(1) })
      .passthrough()
      .safeParse(frame);
    if (!typeFrame.success) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted an invalid public RPC frame shape.",
      );
      return;
    }
    const { type } = typeFrame.data;
    if (type === "ready") {
      if (!readyFrameSchema.safeParse(frame).success) {
        this.fail(
          "OMP_HARNESS_RPC_FRAME_INVALID",
          "OMP emitted an incompatible public RPC ready frame.",
        );
        return;
      }
      this.ready = true;
      return;
    }
    if (type === "response") {
      this.handleResponse(frame);
      return;
    }
    if (type === "command_output") {
      const parsed = commandOutputFrameSchema.safeParse(frame);
      if (!parsed.success) {
        this.fail(
          "OMP_HARNESS_RPC_FRAME_INVALID",
          "OMP emitted an invalid public command-output frame.",
        );
        return;
      }
      this.recordText(parsed.data.text);
      return;
    }
    if (type === "prompt_result") {
      this.handlePromptResult(frame);
      return;
    }
    if (type === "agent_start") {
      this.handleAgentStart();
      return;
    }
    if (type === "extension_ui_request") {
      void this.handleUi(frame);
      return;
    }
    if (type === "host_tool_call") {
      void this.handleToolCall(frame);
      return;
    }
    if (type === "message_end") {
      const parsed = usageFrameSchema.safeParse(frame);
      if (!parsed.success) {
        this.fail(
          "OMP_HARNESS_RPC_FRAME_INVALID",
          "OMP emitted an invalid public usage frame.",
        );
        return;
      }
      this.recordUsage(parsed.data.message);
      return;
    }
    if (type === "agent_end") {
      const parsed = terminalFrameSchema.safeParse(frame);
      if (!parsed.success) {
        this.fail(
          "OMP_HARNESS_RPC_FRAME_INVALID",
          "OMP emitted an invalid public terminal frame.",
        );
        return;
      }
      if (parsed.data.isTerminal !== false) {
        this.terminalReached = true;
        for (const waiter of this.terminalWaiters.splice(0)) waiter.resolve();
      }
      return;
    }
    if (harmlessFrameTypes.has(type)) return;
    this.fail(
      "OMP_HARNESS_RPC_FRAME_INVALID",
      "OMP emitted an unexpected public RPC frame type.",
    );
  }

  private handlePromptResult(frame: unknown): void {
    const parsed = promptResultFrameSchema.safeParse(frame);
    if (!parsed.success) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted an invalid deferred public prompt result.",
      );
      return;
    }
    const pending = this.pending.get(parsed.data.id);
    const outcome = pending?.promptOutcome;
    if (
      pending?.command !== "prompt" ||
      outcome === undefined ||
      !outcome.awaiting ||
      outcome.settled
    ) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted an unbound deferred public prompt result.",
      );
      return;
    }
    if (parsed.data.agentInvoked) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP reported a model invocation for a deferred local-only prompt result.",
      );
      return;
    }
    outcome.settled = true;
    outcome.resolve({ agentInvoked: false });
  }

  private handleAgentStart(): void {
    for (const pending of this.pending.values()) {
      const outcome = pending.promptOutcome;
      if (
        pending.command !== "prompt" ||
        outcome === undefined ||
        !outcome.awaiting ||
        outcome.settled
      )
        continue;
      outcome.settled = true;
      outcome.resolve({ agentInvoked: true });
      return;
    }
  }

  private handleResponse(frame: unknown): void {
    const parsed = responseFrameSchema.safeParse(frame);
    if (!parsed.success) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted an invalid public RPC response.",
      );
      return;
    }
    const pending =
      parsed.data.id === undefined
        ? undefined
        : this.pending.get(parsed.data.id);
    if (pending === undefined || pending.command !== parsed.data.command) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP returned an unbound public RPC response.",
      );
      return;
    }
    if (!parsed.data.success) {
      pending.reject(
        new HarnessFailure(
          "OMP_HARNESS_RPC_COMMAND_FAILED",
          "OMP rejected a bounded public RPC command.",
          "Correct the isolated OMP Runtime or fixture state and rerun.",
        ),
      );
      return;
    }
    if (pending.command === "prompt" && parsed.data.data === undefined) {
      const promptOutcome =
        Promise.withResolvers<Readonly<{ agentInvoked: boolean }>>();
      void promptOutcome.promise.catch(() => undefined);
      pending.promptOutcome = {
        awaiting: true,
        settled: false,
        promise: promptOutcome.promise,
        resolve: promptOutcome.resolve,
        reject: promptOutcome.reject,
      };
      pending.resolve(undefined);
      return;
    }
    pending.resolve(parsed.data.data);
  }

  private async handleUi(frame: unknown): Promise<void> {
    const notification = notificationFrameSchema.safeParse(frame);
    if (notification.success) {
      if (!this.onboardingPlanObservationPending) {
        this.recordText(notification.data.message);
        return;
      }
      let rawPlan: unknown;
      try {
        rawPlan = JSON.parse(notification.data.message);
      } catch {
        this.fail(
          "OMP_HARNESS_UI_APPROVAL_DENIED",
          "The parent-authorized Onboard plan did not expose one bounded digest and target count.",
        );
        return;
      }
      const plan = z
        .object({
          digest: z.string().regex(/^[a-f0-9]{64}$/),
          targets: z.array(z.unknown()).min(1).max(100),
        })
        .passthrough()
        .safeParse(rawPlan);
      if (!plan.success) {
        this.fail(
          "OMP_HARNESS_UI_APPROVAL_DENIED",
          "The parent-authorized Onboard plan did not expose one bounded digest and target count.",
        );
        return;
      }
      this.onboardingPlan = {
        digest: plan.data.digest,
        targetCount: plan.data.targets.length,
      };
      for (const waiter of this.onboardingPlanWaiters.splice(0))
        waiter.resolve();
      return;
    }
    const statusUpdate = statusUpdateFrameSchema.safeParse(frame);
    if (statusUpdate.success) return;
    const widgetUpdate = widgetUpdateFrameSchema.safeParse(frame);
    if (widgetUpdate.success) return;
    const confirmation = confirmationFrameSchema.safeParse(frame);
    if (!confirmation.success) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP requested an unsupported interactive public RPC UI operation.",
      );
      return;
    }
    if (
      this.onboardingInitConfirmed &&
      DECLINED_ONBOARD_APPROVAL_TITLES[confirmation.data.title] === true
    ) {
      try {
        await this.send({
          type: "extension_ui_response",
          id: confirmation.data.id,
          confirmed: false,
        });
      } catch (error) {
        this.fail(toFailure(error).code, toFailure(error).reason);
      }
      return;
    }
    const plan = this.onboardingPlan;
    const expectedMessage =
      plan === undefined
        ? undefined
        : new RegExp(
            `^Apply plan ${plan.digest} to ${plan.targetCount} managed AGENTS targets(?:; global Skills are out of scope and are not inspected or modified| and replace retained Skills from the embedded stable set [A-Za-z0-9._-]{1,128})?\\?$`,
          );
    if (
      !this.onboardingInitConfirmationPending ||
      plan === undefined ||
      confirmation.data.title !== "Apply SBTD Onboard Plan" ||
      expectedMessage === undefined ||
      !expectedMessage.test(confirmation.data.message)
    ) {
      this.fail(
        "OMP_HARNESS_UI_APPROVAL_DENIED",
        "OMP requested interactive approval outside the exact parent-authorized Onboard initialization plan.",
      );
      return;
    }
    this.onboardingInitConfirmationPending = false;
    this.onboardingInitConfirmed = true;
    for (const waiter of this.onboardingInitWaiters.splice(0)) waiter.resolve();
    try {
      await this.send({
        type: "extension_ui_response",
        id: confirmation.data.id,
        confirmed: true,
      });
    } catch (error) {
      this.fail(toFailure(error).code, toFailure(error).reason);
    }
  }

  private recordText(text: string): void {
    try {
      assertSafeText(text);
    } catch (error) {
      const safe = toFailure(error);
      this.fail(safe.code, safe.reason);
      return;
    }
    this.capturedTextBytes += Buffer.byteLength(text, "utf8");
    if (this.capturedTextBytes > MAX_TOTAL_CAPTURED_TEXT_BYTES) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted more public command output than the bounded capture budget allows.",
      );
      return;
    }
    this.texts.push(text);
    for (const waiter of this.textWaiters.splice(0)) {
      if (waiter.matches(this.texts.slice(waiter.textIndex).join("\n")))
        waiter.resolve();
      else this.textWaiters.push(waiter);
    }
  }

  private async handleToolCall(frame: unknown): Promise<void> {
    if (this.fatal !== undefined) return;
    const parsed = hostToolCallSchema.safeParse(frame);
    if (!parsed.success) {
      this.fail(
        "OMP_HARNESS_RPC_FRAME_INVALID",
        "OMP emitted an invalid host-tool request.",
      );
      return;
    }
    if (this.toolExecutor === undefined) {
      this.fail(
        "OMP_HARNESS_TOOL_POLICY_VIOLATION",
        "The OMP process requested a host tool outside the approved operation policy.",
      );
      return;
    }
    let result: Readonly<{ text: string; isError?: boolean }>;
    try {
      result = await this.toolExecutor.execute(
        parsed.data.toolName,
        parsed.data.arguments,
      );
    } catch (error) {
      const safe = toFailure(error);
      this.fail(safe.code, safe.reason);
      return;
    }
    if (this.fatal !== undefined) return;
    try {
      await this.send({
        type: "host_tool_result",
        id: parsed.data.id,
        isError: result.isError,
        result: { content: [{ type: "text", text: result.text }] },
      });
    } catch (error) {
      this.fail(toFailure(error).code, toFailure(error).reason);
    }
  }

  private recordUsage(message: unknown): void {
    if (message === null || typeof message !== "object") return;
    const candidate = message as {
      role?: unknown;
      usage?: { totalTokens?: unknown };
    };
    if (candidate.role !== "assistant") return;
    const tokens = candidate.usage?.totalTokens;
    if (!Number.isSafeInteger(tokens) || (tokens as number) < 0) {
      this.fail(
        "OMP_HARNESS_USAGE_UNAVAILABLE",
        "OMP did not provide bounded public usage observations for an assistant turn.",
      );
      return;
    }
    this.usage.turns += 1;
    this.usage.tokens += tokens as number;
  }

  private fail(code: string, reason: string): void {
    if (this.fatal !== undefined) return;
    this.fatal = new HarnessFailure(
      code,
      reason,
      "Correct the authorized OMP public RPC exchange and start a new isolated invocation.",
    );
    for (const pending of this.pending.values()) {
      pending.reject(this.fatal);
      pending.promptOutcome?.reject(this.fatal);
    }
    this.pending.clear();
    for (const waiter of this.onboardingPlanWaiters.splice(0))
      waiter.reject(this.fatal);
    for (const waiter of this.onboardingInitWaiters.splice(0))
      waiter.reject(this.fatal);
    for (const waiter of this.textWaiters.splice(0)) waiter.reject(this.fatal);
    for (const waiter of this.terminalWaiters.splice(0))
      waiter.reject(this.fatal);
    void terminate(this.child);
  }
}

class ToolExecutor {
  readonly definitions = [
    {
      name: "kpi_list",
      description:
        "List one workspace-confined directory without following symlinks.",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } },
        required: ["path"],
        additionalProperties: false,
      },
    },
    {
      name: "kpi_read",
      description: "Read one bounded workspace-confined regular text file.",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } },
        required: ["path"],
        additionalProperties: false,
      },
    },
    {
      name: "kpi_write",
      description: "Write one bounded workspace-confined text file.",
      parameters: {
        type: "object",
        properties: { path: { type: "string" }, content: { type: "string" } },
        required: ["path", "content"],
        additionalProperties: false,
      },
    },
    {
      name: "kpi_exact_replace",
      description:
        "Replace one exact bounded text span in one workspace-confined file.",
      parameters: {
        type: "object",
        properties: {
          path: { type: "string" },
          expected: { type: "string" },
          replacement: { type: "string" },
        },
        required: ["path", "expected", "replacement"],
        additionalProperties: false,
      },
    },
  ] as const;
  readonly commandOutcomes: Array<
    Readonly<{ command: string; status: "passed" | "failed" | "blocked" }>
  > = [];

  constructor(private readonly workspace: Workspace) {}

  async execute(
    name: string,
    input: Record<string, unknown>,
  ): Promise<Readonly<{ text: string; isError?: boolean }>> {
    switch (name) {
      case "kpi_list": {
        const parsed = z
          .object({ path: z.string().min(1).max(512) })
          .strict()
          .safeParse(input);
        if (!parsed.success) return this.blockedTool();
        const path = await this.existingPath(parsed.data.path, "directory");
        const entries = await readdir(path, { withFileTypes: true });
        return {
          text: entries
            .slice(0, 100)
            .map((entry) => entry.name)
            .sort()
            .join("\n"),
        };
      }
      case "kpi_read": {
        const parsed = z
          .object({ path: z.string().min(1).max(512) })
          .strict()
          .safeParse(input);
        if (!parsed.success) return this.blockedTool();
        const path = await this.existingPath(parsed.data.path, "file");
        const details = await stat(path);
        if (details.size > MAX_TOOL_TEXT_BYTES)
          return { text: "file exceeds bounded read limit", isError: true };
        return { text: await readFile(path, "utf8") };
      }
      case "kpi_write": {
        const parsed = z
          .object({
            path: z.string().min(1).max(512),
            content: z.string().max(MAX_TOOL_TEXT_BYTES),
          })
          .strict()
          .safeParse(input);
        if (!parsed.success) return this.blockedTool();
        const path = await this.writablePath(parsed.data.path);
        await this.writeWorkspaceFile(path, parsed.data.content);
        return { text: "written" };
      }
      case "kpi_exact_replace": {
        const parsed = z
          .object({
            path: z.string().min(1).max(512),
            expected: z.string().min(1).max(MAX_TOOL_TEXT_BYTES),
            replacement: z.string().max(MAX_TOOL_TEXT_BYTES),
          })
          .strict()
          .safeParse(input);
        if (!parsed.success) return this.blockedTool();
        const path = await this.existingPath(parsed.data.path, "file");
        const content = await readFile(path, "utf8");
        const first = content.indexOf(parsed.data.expected);
        if (first < 0 || content.indexOf(parsed.data.expected, first + 1) >= 0)
          return {
            text: "expected text must occur exactly once",
            isError: true,
          };
        await this.writeWorkspaceFile(
          path,
          `${content.slice(0, first)}${parsed.data.replacement}${content.slice(first + parsed.data.expected.length)}`,
        );
        return { text: "replaced" };
      }
      default:
        failure(
          "OMP_HARNESS_TOOL_POLICY_VIOLATION",
          "The OMP process requested a host tool outside the allowlisted workspace policy.",
          "Use only the documented bounded local host tools.",
        );
    }
  }

  private blockedTool(): Readonly<{ text: string; isError: true }> {
    failure(
      "OMP_HARNESS_TOOL_POLICY_VIOLATION",
      "The OMP process supplied invalid or unsafe host-tool arguments.",
      "Use only workspace-confined paths and the documented allowlisted arguments.",
    );
  }

  private relativePath(value: string): string {
    if (
      value.includes("\0") ||
      isAbsolute(value) ||
      value === "." ||
      value.split(/[\\/]/).some((part) => part === ".." || part.length === 0)
    )
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "A host-tool path escaped the invocation-scoped workspace.",
        "Use a non-empty relative path inside the isolated fixture workspace.",
      );
    const path = resolve(this.workspace.project, value);
    if (!isWithin(this.workspace.project, path))
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "A host-tool path escaped the invocation-scoped workspace.",
        "Use a relative path inside the isolated fixture workspace.",
      );
    return path;
  }

  private async existingPath(
    value: string,
    expected: "file" | "directory",
  ): Promise<string> {
    const path = this.relativePath(value);
    let resolved: string;
    try {
      resolved = await realpath(path);
      const details = await lstat(resolved);
      if (
        details.isSymbolicLink() ||
        (expected === "file" ? !details.isFile() : !details.isDirectory())
      )
        throw new Error("unsafe");
    } catch {
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "A host-tool target is unavailable, not the requested kind, or resolves through a symlink.",
        "Use an existing regular workspace file or directory without symlinks.",
      );
    }
    if (!isWithin(this.workspace.project, resolved))
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "A host-tool target resolved outside the invocation-scoped workspace.",
        "Use a non-symlink relative workspace path.",
      );
    return resolved;
  }

  private async writablePath(value: string): Promise<string> {
    const path = this.relativePath(value);
    const parent = dirname(path);
    if (!isWithin(this.workspace.project, parent, true))
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "A host-tool write target escaped the invocation-scoped workspace.",
        "Use a relative write target inside the isolated workspace.",
      );
    await mkdir(parent, { recursive: true, mode: 0o700 });
    let cursor = this.workspace.project;
    for (const segment of relative(this.workspace.project, parent)
      .split(sep)
      .filter(Boolean)) {
      cursor = join(cursor, segment);
      const details = await lstat(cursor);
      if (details.isSymbolicLink() || !details.isDirectory())
        failure(
          "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
          "A host-tool write path traversed a symlink or non-directory.",
          "Use a regular directory tree inside the isolated workspace.",
        );
    }
    return path;
  }

  private async writeWorkspaceFile(
    path: string,
    content: string,
  ): Promise<void> {
    try {
      const file = await open(
        path,
        constants.O_WRONLY |
          constants.O_CREAT |
          constants.O_TRUNC |
          constants.O_NOFOLLOW,
        0o600,
      );
      try {
        await file.writeFile(content, "utf8");
      } finally {
        await file.close();
      }
    } catch {
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "A host-tool write target was unsafe or could not be opened without following links.",
        "Use a regular relative file inside the isolated workspace.",
      );
    }
  }
}

async function materializeFixture(
  workspace: Workspace,
  fixture: z.infer<typeof valueStudyFixtureSchema>,
): Promise<void> {
  for (const [path, content] of Object.entries(fixture.startingFiles)) {
    if (
      isAbsolute(path) ||
      path.split(/[\\/]/).some((part) => part === ".." || part.length === 0)
    )
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "The frozen fixture contains an unsafe workspace path.",
        "Repair the frozen fixture with safe relative starting-file paths.",
      );
    const target = resolve(workspace.project, path);
    if (!isWithin(workspace.project, target))
      failure(
        "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
        "The frozen fixture path escaped its isolated workspace.",
        "Repair the frozen fixture path before rerunning.",
      );
    await mkdir(dirname(target), { recursive: true, mode: 0o700 });
    await writeFile(target, content, "utf8");
  }
}

async function snapshotProject(
  project: string,
): Promise<ReadonlyMap<string, string>> {
  const files = new Map<string, string>();
  const visit = async (directory: string): Promise<void> => {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
      const path = join(directory, entry.name);
      const rel = relative(project, path);
      if (entry.isSymbolicLink())
        failure(
          "OMP_HARNESS_WORKSPACE_CONFINEMENT_VIOLATION",
          "The isolated project contains a symlink that could escape the workspace.",
          "Remove symlinks from the frozen fixture and generated worktree.",
        );
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) {
        const details = await stat(path);
        if (details.size > MAX_TOOL_TEXT_BYTES) continue;
        files.set(rel, digest(await readFile(path)));
      }
    }
  };
  await visit(project);
  return files;
}

function patchSummary(
  before: ReadonlyMap<string, string>,
  after: ReadonlyMap<string, string>,
): string | undefined {
  const paths = new Set([...before.keys(), ...after.keys()]);
  const changes = [...paths]
    .sort()
    .filter((path) => before.get(path) !== after.get(path))
    .slice(0, 64)
    .map(
      (path) =>
        `${before.has(path) ? (after.has(path) ? "M" : "D") : "A"} ${path} ${after.get(path) ?? "-"}`,
    );
  return changes.length === 0 ? undefined : changes.join("\n");
}

function parseReport(texts: readonly string[]): Readonly<{
  requiredGates: readonly (typeof REQUIRED_GATE_IDS)[number][];
  routeCost?: "light" | "standard" | "heavy";
}> {
  const report = parseRenderedSbtdReport(texts.join("\n"));
  if (report === undefined)
    failure(
      "OMP_HARNESS_REPORT_INVALID",
      "The public /sbtd report did not contain one valid bounded JSON document.",
      "Use a compatible packed Plugin that renders the current sanitized /sbtd report.",
    );
  const gates = z
    .array(
      z
        .object({ id: z.enum(REQUIRED_GATE_IDS), required: z.boolean() })
        .passthrough(),
    )
    .safeParse(report.workflow.bookGates);
  if (!gates.success)
    failure(
      "OMP_HARNESS_REPORT_INVALID",
      "The public /sbtd report contained incompatible Book Gate facts.",
      "Use a compatible packed Plugin report format.",
    );
  const route =
    report.workflow.route === "auto"
      ? report.workflow.automaticRoute
      : report.workflow.route;
  const routeCost = route === undefined ? undefined : ROUTE_COST_BY_ID[route];
  if (route !== undefined && routeCost === undefined)
    failure(
      "OMP_HARNESS_REPORT_INVALID",
      "The public /sbtd report contained an unknown effective workflow route.",
      "Use a compatible packed Plugin report format.",
    );
  return {
    requiredGates: gates.data
      .filter((gate) => gate.required)
      .map((gate) => gate.id),
    ...(routeCost === undefined ? {} : { routeCost }),
  };
}

type ObservableCommand = "help" | "status" | "report" | "onboard plan";

async function promptAcknowledgment(
  session: RpcSession,
  command: string,
): Promise<void> {
  const result = await session.prompt(`/sbtd ${command}`, 15_000);
  if (result.agentInvoked)
    failure(
      "OMP_HARNESS_RPC_FRAME_INVALID",
      "A read-only public /sbtd command unexpectedly invoked a model.",
      "Use a compatible packed Plugin and OMP Runtime without model invocation for /sbtd commands.",
    );
}

async function promptCommand(
  session: RpcSession,
  command: ObservableCommand,
): Promise<void> {
  const textIndex = session.textCount();
  await promptAcknowledgment(session, command);
  switch (command) {
    case "onboard plan":
      await session.waitForOnboardPlan(15_000);
      return;
    case "help":
      await session.waitForTextSince(
        textIndex,
        (text) =>
          text.includes("Usage: /sbtd help [command]") &&
          text.includes("Usage: /sbtd report"),
        15_000,
      );
      return;
    case "status":
      await session.waitForTextSince(
        textIndex,
        (text) =>
          /^Runtime Mode: (advisory|enforced)$/m.test(text) &&
          /^Policy Profile: [a-z0-9-]+$/m.test(text),
        15_000,
      );
      return;
    case "report":
      await session.waitForTextSince(
        textIndex,
        (text) => parseRenderedSbtdReport(text) !== undefined,
        15_000,
      );
      return;
  }
}

async function prepareMode(
  config: HarnessConfig,
  workspace: Workspace,
  mode: "advisory" | "enforced",
  tools: ToolExecutor | undefined,
): Promise<
  Readonly<{
    session: RpcSession;
    report: Readonly<{
      requiredGates: readonly (typeof REQUIRED_GATE_IDS)[number][];
      routeCost?: "light" | "standard" | "heavy";
    }>;
  }>
> {
  const session = await RpcSession.start(config, workspace, {
    modelId: config.executionModelId,
    plugin: "direct",
    toolExecutor: tools,
  });
  try {
    if (tools !== undefined) await session.setHostTools();
    await session.disableAutoRetry();
    await promptCommand(session, "onboard plan");
    await promptAcknowledgment(session, "onboard init");
    await session.waitForOnboardInitConfirmation(15_000);
    await promptAcknowledgment(session, mode === "advisory" ? "off" : "on");
    const textIndex = session.textCount();
    await promptCommand(session, "report");
    const renderedReport = parseRenderedSbtdReport(
      session.textSince(textIndex).join("\n"),
    );
    if (renderedReport?.workflow.runtimeMode !== mode)
      failure(
        "OMP_HARNESS_REPORT_INVALID",
        "The public /sbtd report did not prove the requested runtime mode.",
        "Use a compatible packed Plugin that reports its active runtime mode.",
      );
    const reportTexts = session.textSince(textIndex);
    return { session, report: parseReport(reportTexts) };
  } catch (error) {
    await session.stop();
    throw error;
  }
}

async function digestDirectory(path: string): Promise<string> {
  const entries: string[] = [];
  const visit = async (directory: string): Promise<void> => {
    for (const entry of (
      await readdir(directory, { withFileTypes: true })
    ).sort((left, right) => left.name.localeCompare(right.name))) {
      const target = join(directory, entry.name);
      if (entry.isSymbolicLink())
        failure(
          "OMP_HARNESS_PLUGIN_UNAVAILABLE",
          "The requested packed Plugin contains an unsupported symbolic link.",
          "Use an extracted regular-file Plugin package for compatibility validation.",
        );
      if (entry.isDirectory()) await visit(target);
      else if (entry.isFile())
        entries.push(
          `${relative(path, target)}\0${digest(await readFile(target))}`,
        );
    }
  };
  await visit(path);
  return digest(entries.join("\n"));
}

async function compatibility(
  request: Extract<HarnessRequest, { operation: "compatibility" }>,
): Promise<unknown> {
  try {
    const compatibilityAgentDirectory =
      await resolveCompatibilityAgentDirectory();
    const config = await harnessConfig(true);
    if (config.runtimeVersion !== request.input.currentRuntimeVersion)
      failure(
        "OMP_HARNESS_IDENTITY_MISMATCH",
        "The compatibility request current Runtime identity does not match the explicit authorized Runtime identity.",
        "Run one checked current-Runtime request through a matching authorized harness configuration.",
      );
    const requestedPlugin = await realpath(
      request.input.pluginPackagePath,
    ).catch(() => undefined);
    if (
      requestedPlugin === undefined ||
      requestedPlugin !== config.pluginDirectory
    )
      failure(
        "OMP_HARNESS_PLUGIN_UNAVAILABLE",
        "The compatibility request Plugin does not match the explicit authorized packed Plugin directory.",
        "Use the parent-selected extracted Plugin directory for both request and harness configuration.",
      );
    const requestedTarball = await resolveCandidateTarball(
      request.input.pluginTarballPath,
    );
    const configuredTarball = await resolveCandidateTarball(
      requiredEnvironment("KPI_OMP_PLUGIN_TARBALL"),
    );
    if (requestedTarball !== configuredTarball)
      failure(
        "OMP_HARNESS_PLUGIN_UNAVAILABLE",
        "The compatibility request tarball does not match the parent-authorized candidate tarball.",
        "Use the same exact regular tarball in the request and harness configuration.",
      );
    await verifyRuntime(config);
    const before = await snapshotState(request.input.sandboxRoot);
    const pluginDirectory = config.pluginDirectory;
    if (pluginDirectory === undefined)
      failure(
        "OMP_HARNESS_PLUGIN_UNAVAILABLE",
        "The compatibility request requires one explicit packed Plugin directory.",
        "Set the parent-authorized packed Plugin directory before running compatibility.",
      );
    const packageSha256 = await digestDirectory(pluginDirectory);
    await inWorkspace(async (workspace) => {
      await writeCompatibilityProviderConfig(workspace);
      const installedExtensionPath = await installCandidatePlugin(
        workspace,
        configuredTarball,
        compatibilityAgentDirectory,
      );
      const session = await RpcSession.start(config, workspace, {
        plugin: "installed",
        installedExtensionPath,
        compatibilityAgentDirectory,
      });
      try {
        for (const command of request.input.commands)
          await promptCommand(session, command);
      } finally {
        await session.stop();
      }
    });
    const after = await snapshotState(request.input.sandboxRoot);
    if (before !== after)
      failure(
        "OMP_HARNESS_ZERO_WRITE_VIOLATION",
        "Compatibility validation changed the caller-supplied sandbox.",
        "Repair the compatibility harness so it uses only its invocation-scoped workspace.",
      );
    return {
      schemaVersion: 1,
      operation: "compatibility",
      result: {
        currentRuntimeVersion: request.input.currentRuntimeVersion,
        status: "passed",
        agentInvoked: false,
        filesystemBeforeSha256: before,
        filesystemAfterSha256: after,
        packageSha256,
        ...(compatibilityAgentDirectory === undefined
          ? {}
          : {
              acceptanceMode: "profile-isolated" as const,
              supportDecision: "requires-separate-support-review" as const,
            }),
        commandResults: {
          help: "passed",
          status: "passed",
          report: "passed",
          "onboard plan": "passed",
        },
      },
    };
  } catch (error) {
    return blockedCompatibility(
      request.input.currentRuntimeVersion,
      asBlocker(error),
    );
  }
}

async function snapshotState(path: string): Promise<string> {
  try {
    const details = await lstat(path);
    if (details.isSymbolicLink()) return digest("symlink");
    if (details.isFile()) return digest(await readFile(path));
    if (!details.isDirectory()) return digest("other");
    return await digestDirectory(path);
  } catch {
    return digest("missing");
  }
}

function blockedCompatibility(
  currentRuntimeVersion: string,
  blocker: Blocker,
): unknown {
  return {
    schemaVersion: 1,
    operation: "compatibility",
    result: {
      currentRuntimeVersion,
      status: "blocked",
      agentInvoked: false,
      blocker,
      commandResults: {
        help: "blocked",
        status: "blocked",
        report: "blocked",
        "onboard plan": "blocked",
      },
    },
  };
}

async function preflight(
  request: Extract<HarnessRequest, { operation: "preflight" }>,
): Promise<unknown> {
  try {
    const config = await harnessConfig(false);
    if (
      request.input.runtimeVersion !== config.runtimeVersion ||
      request.input.executionModelId !== config.executionModelId ||
      request.input.judgeModelId !== config.judgeModelId
    )
      failure(
        "OMP_HARNESS_IDENTITY_MISMATCH",
        "The preflight request does not match the explicit authorized Runtime or model identities.",
        "Pass the exact parent-approved Runtime, execution-model, and Judge-model identifiers.",
      );
    await verifyRuntime(config);
    for (const modelId of [config.executionModelId, config.judgeModelId])
      await inWorkspace(async (workspace) => {
        const session = await RpcSession.start(config, workspace, {
          modelId,
          plugin: false,
        });
        try {
          await session.disableAutoRetry();
        } finally {
          await session.stop();
        }
      });
    return {
      schemaVersion: 1,
      operation: "preflight",
      result: {
        status: "ready",
        runtimeVersion: config.runtimeVersion,
        executionModelId: config.executionModelId,
        judgeModelId: config.judgeModelId,
        executionProcessId: config.executionProcessId,
        judgeProcessId: config.judgeProcessId,
        supportsUsageEvents: true,
      },
    };
  } catch (error) {
    return {
      schemaVersion: 1,
      operation: "preflight",
      result: {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: asBlocker(error),
      },
    };
  }
}

async function runtimeMode(
  request: Extract<HarnessRequest, { operation: "runtime-mode" }>,
): Promise<unknown> {
  try {
    const config = await harnessConfig(true);
    await verifyRuntime(config);
    await inWorkspace(async (workspace) => {
      const prepared = await prepareMode(
        config,
        workspace,
        request.input.mode,
        undefined,
      );
      try {
        // `runtime-mode` is a stateless readiness proof. `execute` repeats it in a fresh process.
      } finally {
        await prepared.session.stop();
      }
    });
    return {
      schemaVersion: 1,
      operation: "runtime-mode",
      result: { status: "ready" },
    };
  } catch (error) {
    return {
      schemaVersion: 1,
      operation: "runtime-mode",
      result: { status: "blocked", blocker: asBlocker(error) },
    };
  }
}

async function execute(
  request: Extract<HarnessRequest, { operation: "execute" }>,
): Promise<unknown> {
  try {
    const config = await harnessConfig(true);
    if (
      request.input.fixtureSha256 !==
        valueStudyFixtureSha256(request.input.fixture) ||
      (request.input.arm === "control"
        ? request.input.mode !== "advisory"
        : request.input.mode !== "enforced")
    )
      failure(
        "OMP_HARNESS_REQUEST_INVALID",
        "The execution request does not bind one frozen fixture, arm, and matching mode.",
        "Use the release validator's immutable fixture digest and control/treatment mode mapping.",
      );
    await verifyRuntime(config);
    const result = await inWorkspace(async (workspace) => {
      await materializeFixture(workspace, request.input.fixture);
      const before = await snapshotProject(workspace.project);
      const tools = new ToolExecutor(workspace);
      const prepared = await prepareMode(
        config,
        workspace,
        request.input.mode,
        tools,
      );
      try {
        const promptResult = await prepared.session.prompt(
          request.input.fixture.prompt,
          request.input.limits.wallClockMs,
        );
        if (!promptResult.agentInvoked)
          failure(
            "OMP_HARNESS_RPC_FRAME_INVALID",
            "The fixture prompt did not invoke the explicitly selected execution model.",
            "Use a compatible OMP Runtime with the exact selected execution model.",
          );
        await prepared.session.waitForTerminal(
          request.input.limits.wallClockMs,
        );
        const usage = prepared.session.usageTotals;
        if (usage.turns === 0)
          failure(
            "OMP_HARNESS_USAGE_UNAVAILABLE",
            "The OMP public RPC session did not expose bounded assistant usage events.",
            "Use an OMP Runtime that exposes public usage events before starting the study.",
          );
        const outcome =
          usage.turns > request.input.limits.maxTurns
            ? "turn-limit"
            : usage.tokens > request.input.limits.maxTokens
              ? "token-limit"
              : "completed";
        const finalResponse = await prepared.session.lastAssistantText();
        if (finalResponse !== undefined) assertSafeText(finalResponse);
        const after = await snapshotProject(workspace.project);
        const patch = patchSummary(before, after);
        const acceptanceArtifact = acceptanceArtifactSchema.parse({
          ...(finalResponse === undefined ? {} : { finalResponse }),
          ...(patch === undefined ? {} : { patch }),
          commandOutcomes: tools.commandOutcomes,
        });
        assertSafeArtifact(acceptanceArtifact);
        return {
          report: prepared.report,
          usage,
          outcome,
          finalResponse,
          acceptanceArtifact,
        };
      } finally {
        await prepared.session.stop();
      }
    });
    return {
      schemaVersion: 1,
      operation: "execute",
      result: {
        status: "completed",
        runId: request.input.runId,
        fixtureId: request.input.fixture.id,
        arm: request.input.arm,
        attempt: request.input.attempt,
        fixtureSha256: request.input.fixtureSha256,
        executionProcessId: config.executionProcessId,
        events: [
          {
            kind: "usage",
            turns: result.usage.turns,
            tokens: result.usage.tokens,
          },
          {
            kind: "report",
            requiredGates: result.report.requiredGates,
            // An unclassified auto Session carries no route cost; never
            // synthesize one.
            ...(result.report.routeCost === undefined
              ? {}
              : { routeCost: result.report.routeCost }),
          },
          {
            kind: "terminal",
            outcome: result.outcome,
            ...(result.finalResponse === undefined
              ? {}
              : { finalResponse: result.finalResponse }),
          },
        ],
        acceptanceArtifact: result.acceptanceArtifact,
        acceptanceArtifactSha256: acceptanceArtifactSha256(
          result.acceptanceArtifact,
        ),
      },
    };
  } catch (error) {
    return {
      schemaVersion: 1,
      operation: "execute",
      result: { status: "blocked", blocker: asBlocker(error) },
    };
  }
}

async function judge(
  request: Extract<HarnessRequest, { operation: "judge" }>,
): Promise<unknown> {
  try {
    const config = await harnessConfig(false);
    for (const arm of [request.input.first, request.input.second]) {
      assertSafeArtifact(arm.artifact);
      if (acceptanceArtifactSha256(arm.artifact) !== arm.artifactSha256)
        failure(
          "OMP_HARNESS_REQUEST_INVALID",
          "The blind Judge request contains an acceptance artifact with a mismatched digest.",
          "Bind each frozen masked artifact to its exact digest before judging.",
        );
    }
    await verifyRuntime(config);
    const result = await inWorkspace(async (workspace) => {
      const session = await RpcSession.start(config, workspace, {
        modelId: config.judgeModelId,
        plugin: false,
      });
      try {
        await session.disableAutoRetry();
        const judgePrompt = stableJson({
          instruction:
            "Score exactly the two masked acceptance artifacts against the frozen rubric. Return only JSON with first and second scores. Do not use tools.",
          rubric: request.input.rubric,
          first: request.input.first.artifact,
          second: request.input.second.artifact,
        });
        const prompted = await session.prompt(judgePrompt, JUDGE_TIMEOUT_MS);
        if (!prompted.agentInvoked)
          failure(
            "OMP_HARNESS_JUDGE_RESPONSE_INVALID",
            "The independent Judge did not invoke the explicitly selected model.",
            "Use an available exact Judge model through public OMP RPC.",
          );
        await session.waitForTerminal(JUDGE_TIMEOUT_MS);
        const text = await session.lastAssistantText();
        if (text === undefined)
          failure(
            "OMP_HARNESS_JUDGE_RESPONSE_INVALID",
            "The independent Judge returned no bounded final JSON result.",
            "Return one strict JSON scoring result from the Judge model.",
          );
        assertSafeText(text);
        let raw: unknown;
        try {
          raw = JSON.parse(text);
        } catch {
          failure(
            "OMP_HARNESS_JUDGE_RESPONSE_INVALID",
            "The independent Judge did not return one strict JSON scoring result.",
            "Return only the documented masked Judge JSON result.",
          );
        }
        const scores = z
          .object({ first: judgeScoreSchema, second: judgeScoreSchema })
          .strict()
          .safeParse(raw);
        if (!scores.success)
          failure(
            "OMP_HARNESS_JUDGE_RESPONSE_INVALID",
            "The independent Judge returned an incompatible scoring result.",
            "Return exactly two bounded score objects for the frozen rubric.",
          );
        assertSafeArtifact(scores.data);
        assertJudgeScoreMatchesRubric(
          scores.data.first,
          request.input.rubric,
          `${request.input.fixtureId} first`,
        );
        assertJudgeScoreMatchesRubric(
          scores.data.second,
          request.input.rubric,
          `${request.input.fixtureId} second`,
        );
        return scores.data;
      } finally {
        await session.stop();
      }
    });
    const binding = {
      fixtureId: request.input.fixtureId,
      firstArtifactSha256: request.input.first.artifactSha256,
      secondArtifactSha256: request.input.second.artifactSha256,
      first: result.first,
      second: result.second,
    };
    return {
      schemaVersion: 1,
      operation: "judge",
      result: {
        status: "completed",
        runId: request.input.runId,
        fixtureId: request.input.fixtureId,
        fixtureSha256: request.input.fixtureSha256,
        judgeProcessId: config.judgeProcessId,
        ...binding,
        judgeResultSha256: blindJudgeResultSha256(binding),
      },
    };
  } catch (error) {
    return {
      schemaVersion: 1,
      operation: "judge",
      result: { status: "blocked", blocker: asBlocker(error) },
    };
  }
}

async function dispatch(request: HarnessRequest): Promise<unknown> {
  switch (request.operation) {
    case "compatibility":
      return compatibility(request);
    case "preflight":
      return preflight(request);
    case "runtime-mode":
      return runtimeMode(request);
    case "execute":
      return execute(request);
    case "judge":
      return judge(request);
  }
}

function emit(response: unknown): void {
  let text: string;
  try {
    text = JSON.stringify(response);
  } catch {
    text = JSON.stringify({
      schemaVersion: 1,
      operation: "preflight",
      result: {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: {
          code: "OMP_HARNESS_INTERNAL_FAILURE",
          reason:
            "The authorized OMP harness could not serialize a safe response.",
          recovery:
            "Correct the authorized harness and rerun the parent command.",
        },
      },
    });
  }
  if (Buffer.byteLength(text) > MAX_RESPONSE_BYTES)
    text = JSON.stringify({
      schemaVersion: 1,
      operation: "preflight",
      result: {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: {
          code: "OMP_HARNESS_RESPONSE_TOO_LARGE",
          reason:
            "The authorized OMP harness suppressed an oversized response.",
          recovery:
            "Reduce the bounded result to the documented protocol limits.",
        },
      },
    });
  process.stdout.write(`${text}\n`);
}

try {
  emit(await dispatch(await readRequest()));
} catch (error) {
  const blocker = asBlocker(error);
  emit({
    schemaVersion: 1,
    operation: "preflight",
    result: { status: "blocked", supportsUsageEvents: false, blocker },
  });
}
