/**
 * sbtd_validate (T10) — pre impact / post detectChanges+tests.
 *
 * Locks: Q1A / Q2A / Q3A(+clar) / Q4A / Q5A.
 * Host injects cwd + GitNexusOptions. Model never supplies trust handles.
 */

import { type ChildProcess, spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import {
  type AnalysisResult,
  detectChanges,
  type GitNexusOptions,
  impact,
  type McpClient,
} from "../backends/gitnexus.js";
import { getSession } from "../state.js";
import {
  type PlanToolExec,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";

export const SBTD_VALIDATE_TOOL_NAME = "sbtd_validate";

export const VALIDATE_PHASES = ["pre", "post"] as const;
export type ValidatePhase = (typeof VALIDATE_PHASES)[number];

/** Model-visible args only (Q1A). */
export type ValidateInput = {
  phase: string;
  target?: string;
  direction?: string;
  scope?: string;
};

export type TestsResult = {
  status: "done" | "skipped" | "failed" | "not-applicable";
  summary: string;
};

export type ValidateSessionSlice = {
  pre?: "done" | "skipped";
  post?: "done" | "blocked";
};

export type ValidateToolResult = {
  phase: ValidatePhase;
  gitnexus: AnalysisResult;
  tests?: TestsResult;
  validate: ValidateSessionSlice;
};

/**
 * Host-injected trust handles + test overrides (Q1A).
 * Never exposed on the model tool schema.
 */
export type ValidateHostOptions = {
  cwd?: string;
  gitnexus?: GitNexusOptions;
  /** Override project-test runner (tests / host). */
  runTests?: (cwd: string) => Promise<TestsResult>;
  /** Cap for spawned test commands. Default 120s. */
  testTimeoutMs?: number;
  /** Per-invocation cancellation (from ToolRunContext.signal). */
  signal?: AbortSignal;
};

/**
 * PluginHost surface for production injection (Q1A).
 * `validateHost` is explicit; otherwise cwd + tools→MCP bridge are derived.
 */
export type ValidatePluginHost = ToolsHost & {
  cwd?: string;
  validateHost?: ValidateHostOptions;
};

export type ValidateToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: ValidateToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (
    args: ValidateInput,
    exec: PlanToolExec,
  ) => Promise<ValidateToolResult>;
};

const DEFAULT_TEST_TIMEOUT_MS = 120_000;
const TERM_GRACE_MS = 5_000;

const FORBIDDEN_MODEL_KEYS = [
  "cwd",
  "mcp",
  "runRefresh",
  "serverName",
  "toolNames",
] as const;

const META_CHAR_RE = /[;&|`$<>]/;

/** Allowlisted executables for docs-discovered and package-manager test commands. */
const ALLOWED_TEST_COMMANDS = new Set([
  "pnpm",
  "yarn",
  "bun",
  "npm",
  "pytest",
  "uv",
  "go",
  "gradle",
  "gradlew",
  "swift",
]);

function isValidatePhase(value: string): value is ValidatePhase {
  return (VALIDATE_PHASES as readonly string[]).includes(value);
}

function mapPreFromGitNexus(
  status: AnalysisResult["status"],
): "done" | "skipped" {
  // Q3 clar.: skipped → pre=skipped; ok|advisory → pre=done
  if (status === "skipped") return "skipped";
  return "done";
}

function skippedGitNexus(summary: string, reason: string): AnalysisResult {
  return { status: "skipped", summary, reason };
}

function readTextIfPresent(path: string): string | null {
  try {
    if (!existsSync(path)) return null;
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

type DiscoveredCommand = {
  command: string;
  args: string[];
  source: string;
};

function detectPackageManager(cwd: string): "pnpm" | "yarn" | "bun" | "npm" {
  if (existsSync(join(cwd, "pnpm-lock.yaml"))) return "pnpm";
  if (existsSync(join(cwd, "yarn.lock"))) return "yarn";
  if (existsSync(join(cwd, "bun.lockb")) || existsSync(join(cwd, "bun.lock"))) {
    return "bun";
  }
  return "npm";
}

function commandFromPackageScripts(cwd: string): DiscoveredCommand | null {
  const pkgPath = join(cwd, "package.json");
  const raw = readTextIfPresent(pkgPath);
  if (raw == null) return null;
  let scripts: Record<string, unknown> | undefined;
  try {
    const pkg = JSON.parse(raw) as { scripts?: Record<string, unknown> };
    scripts = pkg.scripts;
  } catch {
    return null;
  }
  if (scripts == null || typeof scripts.test !== "string") return null;
  const pm = detectPackageManager(cwd);
  // Report-type tests: native command, no rtk (§T10 / Q2A implementation).
  if (pm === "pnpm") {
    return {
      command: "pnpm",
      args: ["test"],
      source: "package.json#scripts.test",
    };
  }
  if (pm === "yarn") {
    return {
      command: "yarn",
      args: ["test"],
      source: "package.json#scripts.test",
    };
  }
  if (pm === "bun") {
    // Honor package.json#scripts.test via `bun run test` (not Bun's built-in runner).
    return {
      command: "bun",
      args: ["run", "test"],
      source: "package.json#scripts.test",
    };
  }
  return {
    command: "npm",
    args: ["test", "--"],
    source: "package.json#scripts.test",
  };
}

function argsAreSafe(args: string[]): boolean {
  return args.every((a) => a.length > 0 && !META_CHAR_RE.test(a));
}

function finalizeDiscovered(
  parts: string[],
  source: string,
): DiscoveredCommand | null {
  if (parts.length < 1) return null;
  let command = parts[0];
  const args = parts.slice(1);
  if (command == null) return null;
  // Normalize ./gradlew → gradlew (spawn under cwd).
  if (command === "./gradlew" || command.endsWith("/gradlew")) {
    command = "gradlew";
  }
  if (!ALLOWED_TEST_COMMANDS.has(command)) return null;
  if (!argsAreSafe(args)) return null;
  return { command, args, source };
}

/**
 * Best-effort: pull an explicit test command line from AGENTS.md / README.md.
 * Supports npm-family and common non-Node project commands (pytest / go / gradle / swift).
 * No shell metacharacters; argv spawn only.
 */
function commandFromDocs(cwd: string): DiscoveredCommand | null {
  // Ordered patterns: first match in file wins per file; files checked AGENTS → README.
  const patterns: RegExp[] = [
    /(?:^|\n)\s*(?:[-*]\s*)?(?:`)?((?:pnpm|yarn|bun|npm)(?:\s+run)?\s+test)(?:`)?(?:\s|$)/i,
    /(?:^|\n)\s*(?:[-*]\s*)?(?:`)?(uv\s+run\s+pytest(?:\s+[^\n;`|&$<>]+)?)(?:`)?(?:\s|$)/i,
    /(?:^|\n)\s*(?:[-*]\s*)?(?:`)?(pytest(?:\s+[^\n;`|&$<>]+)?)(?:`)?(?:\s|$)/i,
    /(?:^|\n)\s*(?:[-*]\s*)?(?:`)?(go\s+test(?:\s+[^\n;`|&$<>]+)?)(?:`)?(?:\s|$)/i,
    /(?:^|\n)\s*(?:[-*]\s*)?(?:`)?((?:\.\/)?gradlew\s+test(?:\s+[^\n;`|&$<>]+)?|gradle\s+test(?:\s+[^\n;`|&$<>]+)?)(?:`)?(?:\s|$)/i,
    /(?:^|\n)\s*(?:[-*]\s*)?(?:`)?(swift\s+test(?:\s+[^\n;`|&$<>]+)?)(?:`)?(?:\s|$)/i,
  ];

  for (const name of ["AGENTS.md", "README.md", "README_zh.md"] as const) {
    const text = readTextIfPresent(join(cwd, name));
    if (text == null) continue;
    for (const re of patterns) {
      const match = text.match(re);
      const captured = match?.[1];
      if (captured == null) continue;
      const parts = captured.trim().split(/\s+/).filter(Boolean);
      const discovered = finalizeDiscovered(parts, name);
      if (discovered != null) return discovered;
    }
  }
  return null;
}

/**
 * Strategy priority (design §T10): AGENTS / README / package scripts / defaults.
 * No discoverable script ⇒ skipped + residual risk (never pretend passed).
 */
export function discoverProjectTestCommand(
  cwd: string,
): DiscoveredCommand | null {
  return commandFromDocs(cwd) ?? commandFromPackageScripts(cwd);
}

export type RunTestsOptions = {
  timeoutMs?: number;
  signal?: AbortSignal;
};

function resolveSpawnCommand(
  cwd: string,
  discovered: DiscoveredCommand,
): { command: string; args: string[] } {
  if (discovered.command === "gradlew") {
    const local = join(cwd, "gradlew");
    if (existsSync(local)) {
      return { command: local, args: discovered.args };
    }
  }
  return { command: discovered.command, args: discovered.args };
}

function terminateSpawned(child: ChildProcess): void {
  if (child.pid == null) return;
  try {
    if (process.platform !== "win32") {
      try {
        // When spawned detached, child is process-group leader.
        process.kill(-child.pid, "SIGTERM");
        return;
      } catch {
        // Not a group leader / already exited — fall through.
      }
    }
    child.kill("SIGTERM");
  } catch {
    // ignore
  }
}

function forceKillSpawned(child: ChildProcess): void {
  if (child.pid == null) return;
  try {
    if (process.platform !== "win32") {
      try {
        process.kill(-child.pid, "SIGKILL");
        return;
      } catch {
        // fall through
      }
    }
    child.kill("SIGKILL");
  } catch {
    // ignore
  }
}

export function defaultRunTests(
  cwd: string,
  timeoutMsOrOpts: number | RunTestsOptions = DEFAULT_TEST_TIMEOUT_MS,
): Promise<TestsResult> {
  const opts: RunTestsOptions =
    typeof timeoutMsOrOpts === "number"
      ? { timeoutMs: timeoutMsOrOpts }
      : timeoutMsOrOpts;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TEST_TIMEOUT_MS;
  const signal = opts.signal;

  const discovered = discoverProjectTestCommand(cwd);
  if (discovered == null) {
    return Promise.resolve({
      status: "skipped",
      summary:
        "No project test script found (checked AGENTS.md / README / package.json scripts). Residual risk: changes were not exercised by automated tests.",
    });
  }

  const spawnSpec = resolveSpawnCommand(cwd, discovered);
  const cmdLabel = `${discovered.command} ${discovered.args.join(" ")}`;

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result: TestsResult) => {
      if (settled) return;
      settled = true;
      if (signal != null) {
        signal.removeEventListener("abort", onAbort);
      }
      resolve(result);
    };

    let child: ChildProcess;
    let timedOut = false;
    let cancelled = false;
    let killEscalate: ReturnType<typeof setTimeout> | undefined;

    const onAbort = () => {
      cancelled = true;
      terminateSpawned(child);
      if (killEscalate == null) {
        killEscalate = setTimeout(() => {
          forceKillSpawned(child);
        }, TERM_GRACE_MS);
      }
    };

    try {
      child = spawn(spawnSpec.command, spawnSpec.args, {
        cwd,
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
        shell: false,
        // Own process group on Unix so SIGTERM can cover descendants.
        detached: process.platform !== "win32",
      });
    } catch (err) {
      finish({
        status: "failed",
        summary: `Failed to spawn tests (${discovered.source}: ${cmdLabel}): ${
          err instanceof Error ? err.message : String(err)
        }`,
      });
      return;
    }

    let stdout = "";
    let stderr = "";
    child.stdout?.setEncoding("utf8");
    child.stderr?.setEncoding("utf8");
    child.stdout?.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr?.on("data", (chunk: string) => {
      stderr += chunk;
    });

    const timer = setTimeout(() => {
      timedOut = true;
      terminateSpawned(child);
      killEscalate = setTimeout(() => {
        forceKillSpawned(child);
      }, TERM_GRACE_MS);
      // Do not finish yet — wait for close so the owned process reaches quiescence.
    }, timeoutMs);

    if (signal != null) {
      if (signal.aborted) {
        onAbort();
      } else {
        signal.addEventListener("abort", onAbort, { once: true });
      }
    }

    child.on("error", (err) => {
      clearTimeout(timer);
      if (killEscalate != null) clearTimeout(killEscalate);
      finish({
        status: "failed",
        summary: `Project tests spawn error (${discovered.source}): ${err.message}`,
      });
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      if (killEscalate != null) clearTimeout(killEscalate);
      const combined = [stdout.trim(), stderr.trim()]
        .filter(Boolean)
        .join("\n");
      if (cancelled) {
        finish({
          status: "failed",
          summary: `Project tests cancelled (${discovered.source}: ${cmdLabel}).${
            combined ? `\n${combined.slice(0, 4000)}` : ""
          }`,
        });
        return;
      }
      if (timedOut) {
        finish({
          status: "failed",
          summary: `Project tests timed out after ${timeoutMs}ms (${discovered.source}: ${cmdLabel}).`,
        });
        return;
      }
      if (code === 0) {
        finish({
          status: "done",
          summary: `Project tests passed (${discovered.source}: ${cmdLabel}).${
            combined ? `\n${combined.slice(0, 4000)}` : ""
          }`,
        });
      } else {
        finish({
          status: "failed",
          summary: `Project tests failed with exit ${code == null ? "null" : code} (${discovered.source}: ${cmdLabel}).${
            combined ? `\n${combined.slice(0, 4000)}` : ""
          }`,
        });
      }
    });
  });
}

/** Pick only model-visible keys (Q1A); drop trust-handle extras if present. */
export function pickValidateInput(args: unknown): ValidateInput {
  const src =
    args != null && typeof args === "object"
      ? (args as Record<string, unknown>)
      : {};
  const out: ValidateInput = {
    phase: typeof src.phase === "string" ? src.phase : "",
  };
  if (typeof src.target === "string") out.target = src.target;
  if (typeof src.direction === "string") out.direction = src.direction;
  if (typeof src.scope === "string") out.scope = src.scope;
  return out;
}

function canBridgeTools(tools: ToolsHost["tools"]): boolean {
  return typeof tools.schemas === "function";
}

/**
 * Host-owned bridge: Cordis/DSH ToolRuntime → T9 McpClient.
 * list/call happen at use time so MCP tools registered after apply() are visible.
 */
export function createToolsMcpBridge(tools: ToolsHost["tools"]): McpClient {
  return {
    listToolNames: () => {
      try {
        const schemas = tools.schemas?.() ?? [];
        return schemas.map((s) => s.name);
      } catch {
        return [];
      }
    },
    callTool: async (name, args) => {
      if (typeof tools.execute !== "function") {
        throw new Error(
          `GitNexus MCP bridge: tools.execute missing for ${name}`,
        );
      }
      const result = await tools.execute({
        callId: `sbtd_validate:${name}:${Date.now()}`,
        name,
        arguments: args,
        signal: AbortSignal.timeout(DEFAULT_TEST_TIMEOUT_MS),
      });
      if (result.isError) {
        throw new Error(
          result.error?.message ?? `MCP tool ${name} returned error`,
        );
      }
      if (result.value !== undefined) return result.value;
      return result.content;
    },
  };
}

/**
 * Resolve host-owned cwd + GitNexusOptions for production registration (Q1A).
 * Explicit `validateHost` wins; otherwise derive cwd and bridge MCP from tools.
 */
export function resolveValidateHost(
  ctx: ValidatePluginHost,
): ValidateHostOptions {
  const explicit = ctx.validateHost ?? {};
  const cwd =
    typeof explicit.cwd === "string" && explicit.cwd.length > 0
      ? explicit.cwd
      : typeof ctx.cwd === "string" && ctx.cwd.length > 0
        ? ctx.cwd
        : process.cwd();

  const gitnexus: GitNexusOptions = { ...(explicit.gitnexus ?? {}) };
  if (gitnexus.mcp == null && canBridgeTools(ctx.tools)) {
    gitnexus.mcp = createToolsMcpBridge(ctx.tools);
  }

  return {
    ...explicit,
    cwd,
    gitnexus,
  };
}

export async function sbtdValidate(
  sessionId: string,
  input: ValidateInput,
  host: ValidateHostOptions = {},
): Promise<ValidateToolResult> {
  if (!isValidatePhase(input.phase)) {
    throw new Error(
      `sbtd_validate: phase must be one of ${VALIDATE_PHASES.join(", ")}`,
    );
  }
  const phase = input.phase;
  const cwd = host.cwd ?? process.cwd();
  const gnOpts: GitNexusOptions = host.gitnexus ?? {};
  const session = getSession(sessionId);

  if (phase === "pre") {
    const target = typeof input.target === "string" ? input.target.trim() : "";
    let gitnexus: AnalysisResult;
    if (!target) {
      // Q2A: skip impact when target missing
      gitnexus = skippedGitNexus(
        "Pre impact skipped: no target provided.",
        "missing-target",
      );
    } else {
      gitnexus = await impact(cwd, target, input.direction, gnOpts);
    }
    const pre = mapPreFromGitNexus(gitnexus.status);
    session.validate.pre = pre;
    const validate: ValidateSessionSlice = { pre };
    if (session.validate.post !== undefined) {
      validate.post = session.validate.post;
    }
    return {
      phase,
      gitnexus,
      validate,
    };
  }

  // phase === "post"
  const gitnexus = await detectChanges(cwd, input.scope, gnOpts);
  const timeoutMs = host.testTimeoutMs ?? DEFAULT_TEST_TIMEOUT_MS;
  const tests = host.runTests
    ? await host.runTests(cwd)
    : await defaultRunTests(cwd, {
        timeoutMs,
        ...(host.signal != null ? { signal: host.signal } : {}),
      });

  // Q3A: GitNexus skipped/advisory never sets post=blocked.
  // Q4A: failed tests ⇒ post=blocked; no-script skip ⇒ post=done.
  let post: "done" | "blocked";
  if (tests.status === "failed") {
    post = "blocked";
  } else {
    post = "done";
  }
  session.validate.post = post;

  const validate: ValidateSessionSlice = { post };
  if (session.validate.pre !== undefined) {
    validate.pre = session.validate.pre;
  }
  return {
    phase,
    gitnexus,
    tests,
    validate,
  };
}

export const SBTD_VALIDATE_DESCRIPTION =
  "Pre/post verification: phase=pre runs GitNexus impact (skip if unavailable or target missing); phase=post runs GitNexus detectChanges then project tests. Missing GitNexus never blocks post or skips tests. post=blocked only when tests fail. No test script ⇒ skipped/not-applicable + residual risk (never fake passed). cwd and GitNexus MCP/refresh options are host-injected — do not pass them.";

export function createValidateTool(
  host: ValidateHostOptions = {},
): ValidateToolDefinition {
  return {
    name: SBTD_VALIDATE_TOOL_NAME,
    description: SBTD_VALIDATE_DESCRIPTION,
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        phase: {
          type: "string",
          enum: [...VALIDATE_PHASES],
          description:
            "pre = GitNexus impact before edits; post = detectChanges then project tests.",
        },
        target: {
          type: "string",
          description:
            "Optional impact target symbol/path for phase=pre (analysis hint only).",
        },
        direction: {
          type: "string",
          description:
            "Optional impact direction hint for phase=pre (analysis hint only).",
        },
        scope: {
          type: "string",
          description:
            "Optional detectChanges scope hint for phase=post (analysis hint only).",
        },
      },
      required: ["phase"],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          phase: { type: "string" },
          gitnexus: { type: "object" },
          tests: { type: "object" },
          validate: { type: "object" },
        },
      },
      render(_args, value) {
        const lines = [
          `phase: ${value.phase}`,
          `gitnexus.status: ${value.gitnexus.status}`,
        ];
        if (value.gitnexus.advisory === true) {
          lines.push("gitnexus.advisory: true");
        }
        if (value.gitnexus.reason !== undefined) {
          lines.push(`gitnexus.reason: ${value.gitnexus.reason}`);
        }
        if (value.tests !== undefined) {
          lines.push(`tests.status: ${value.tests.status}`);
        }
        if (value.validate.pre !== undefined) {
          lines.push(`validate.pre: ${value.validate.pre}`);
        }
        if (value.validate.post !== undefined) {
          lines.push(`validate.post: ${value.validate.post}`);
        }
        lines.push("", "--- gitnexus ---", value.gitnexus.summary);
        if (value.tests !== undefined) {
          lines.push("", "--- tests ---", value.tests.summary);
        }
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe() {
      return false;
    },
    async execute(args, exec) {
      const modelArgs = pickValidateInput(args);
      const signal = exec.signal ?? host.signal;
      return sbtdValidate(sessionIdFromExec(exec), modelArgs, {
        ...host,
        ...(signal != null ? { signal } : {}),
      });
    },
  };
}

/** Schema helper for tests — model must not see trust-handle keys (Q1A). */
export function modelSchemaForbidsTrustHandles(
  parameters: Record<string, unknown>,
): boolean {
  const props = parameters.properties as Record<string, unknown> | undefined;
  if (props == null) return false;
  for (const key of FORBIDDEN_MODEL_KEYS) {
    if (Object.hasOwn(props, key)) return false;
  }
  return true;
}

export function registerValidateTool(
  ctx: ToolsHost,
  host: ValidateHostOptions = {},
): void {
  ctx.tools.register(createValidateTool(host));
}
