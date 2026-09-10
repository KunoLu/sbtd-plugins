/**
 * sbtd_e2e (T13) — Web / Mobile / Hybrid preflight · generate · run.
 *
 * Locks: Q1B / Q2A / Q3A / Q4A / Q5A / Q6A.
 * Consumes T12 `preflight()` as-is (never rewrite backends/maestro.ts).
 * Host injects cwd + T12 declared facts + binaries + browser lock + creds.
 * Model never supplies trust handles (cwd / mcp / runRefresh / serverName / toolNames).
 * Unit tests never spawn maestro test / live browser (injectable runners).
 */

import { type ChildProcess, spawn } from "node:child_process";
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  statSync,
  writeFileSync,
} from "node:fs";
import {
  basename,
  dirname,
  extname,
  isAbsolute,
  join,
  normalize,
  relative,
  resolve,
  sep,
} from "node:path";
import {
  type MaestroOptions,
  type PlatformHint,
  type PreflightResult,
  preflight as t12Preflight,
} from "../backends/maestro.js";
import {
  type PlanToolExec,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";

export const SBTD_E2E_TOOL_NAME = "sbtd_e2e";

export const E2E_SURFACES = ["web", "mobile", "hybrid"] as const;
export type E2eSurface = (typeof E2E_SURFACES)[number];

export const E2E_ACTIONS = ["preflight", "generate", "run"] as const;
export type E2eAction = (typeof E2E_ACTIONS)[number];

export const E2E_MODES = [
  "full-stack",
  "contract-backed",
  "mock-backed",
  "smoke-only",
] as const;
export type E2eMode = (typeof E2E_MODES)[number];

export const E2E_OUTCOMES = [
  "ok",
  "blocked",
  "failed",
  "skipped-by-user",
] as const;
export type E2eOutcome = (typeof E2E_OUTCOMES)[number];

/** Model-visible args only (Q4A). */
export type E2eInput = {
  surface: string;
  action: string;
  /**
   * Optional cwd-relative flow/feature path or slug
   * (e.g. `smoke`, `maestro/flow/smoke.yml`, `tests/e2e/login.spec.ts`).
   */
  target?: string;
  /** Optional platform hint for mobile|hybrid (ios|android). */
  platform?: string;
};

/**
 * Host-injected trust handles + test overrides (Q4A / Q3A / Q6A).
 * Never exposed on the model tool schema.
 */
export type E2eHostOptions = {
  cwd?: string;
  /** T12 declared facts + injectable detect* stubs (forwarded to preflight). */
  maestro?: MaestroOptions;
  /** Override T12 preflight (tests). Default imports backends/maestro.preflight. */
  preflight?: (options?: MaestroOptions) => Promise<PreflightResult>;
  /**
   * Browser-controller lock (Q6A). When true / returns true ⇒ blocked;
   * never kill/steal another controller.
   */
  browserControllerBusy?: boolean | (() => boolean | Promise<boolean>);
  /** Host-declared E2E mode; mock/contract cannot report full-stack (Q6A). */
  mode?: E2eMode;
  /** Generate selectors / locator facts; must be affirmative true on generate (Q4A). */
  selectorsReady?: boolean;
  /**
   * Concrete locator / assertVisible texts for generate (Q4A).
   * Required (non-empty) when selectorsReady===true — no wildcard placeholders.
   */
  selectorFacts?: string[];
  /** Host credentials confirmed for generate/run; must be affirmative when needed. */
  credentialsReady?: boolean;
  /** User declined install/assist ⇒ skipped-by-user (Q6A). */
  userDeclinedAssist?: boolean;
  /** Injectable Maestro runner — unit tests stub; never live by default in tests. */
  runMaestro?: (ctx: E2eRunnerContext) => Promise<E2eRunnerResult>;
  /** Injectable Playwright runner — unit tests stub. */
  runPlaywright?: (ctx: E2eRunnerContext) => Promise<E2eRunnerResult>;
  /** Optional flow/report root overrides (still convention-win when unset). */
  flowRoot?: string;
  reportRoot?: string;
  playwrightRoot?: string;
};

export type E2ePluginHost = ToolsHost & {
  cwd?: string;
  e2eHost?: E2eHostOptions;
};

export type E2eRunnerContext = {
  cwd: string;
  surface: E2eSurface;
  action: E2eAction;
  targetPath: string;
  reportDir: string;
  platform?: PlatformHint;
  mode: E2eMode;
};

export type E2eRunnerResult = {
  /** Runner started and assertions passed. */
  ok: boolean;
  /** When ok=false and runner did start: assertion/process failure. */
  failed?: boolean;
  /**
   * True when the runner never started (missing binary / spawn refuse).
   * Mapped to T13 blocked, not failed (Q6A).
   */
  didNotStart?: boolean;
  summary?: string;
  /** Set only when a native reporter actually produced this file (Q6A). */
  reportPath?: string;
  reportMdPath?: string;
};

export type E2eBlocked = {
  kind: string;
  reason: string;
};

export type E2eConvention =
  | "existing-maestro-flow"
  | "existing-maestro-reports"
  | "existing-playwright-e2e"
  | "agents-default";

export type E2eToolResult = {
  ok: boolean;
  surface: E2eSurface;
  action: E2eAction;
  /** Q6A outcome label. */
  outcome: E2eOutcome;
  /** Mandatory mode label (Q6A); never full-stack on mock/contract. */
  mode: E2eMode;
  convention?: E2eConvention;
  path?: string;
  reportPath?: string;
  reportMdPath?: string;
  preflight?: PreflightResult;
  /** True when T12 preflight was invoked this call. */
  calledT12Preflight: boolean;
  /** True when a Maestro/Playwright runner was started. */
  runnerStarted: boolean;
  blocked?: E2eBlocked;
  note?: string;
};

export type E2eToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: E2eToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => boolean;
  execute: (args: E2eInput, exec: PlanToolExec) => Promise<E2eToolResult>;
};

const FORBIDDEN_MODEL_KEYS = [
  "cwd",
  "mcp",
  "runRefresh",
  "serverName",
  "toolNames",
] as const;

const SAFE_SLUG_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/;

function isE2eSurface(value: string): value is E2eSurface {
  return (E2E_SURFACES as readonly string[]).includes(value);
}

function isE2eAction(value: string): value is E2eAction {
  return (E2E_ACTIONS as readonly string[]).includes(value);
}

function isPlatformHint(value: string): value is PlatformHint {
  return value === "ios" || value === "android";
}

function resolveCwd(host: E2eHostOptions): string {
  if (typeof host.cwd === "string" && host.cwd.length > 0) {
    return resolve(host.cwd);
  }
  return resolve(process.cwd());
}

function isDir(path: string): boolean {
  try {
    return existsSync(path) && statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function isInsideRootLexical(parent: string, child: string): boolean {
  const p = resolve(parent);
  const c = resolve(child);
  if (p === c) return true;
  const rel = relative(p, c);
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
}

function tryRealpath(path: string): string | null {
  try {
    return realpathSync(path);
  } catch {
    return null;
  }
}

/**
 * Project `path` through the realpath of its nearest existing ancestor.
 * Missing leaf segments are re-joined so agents-default roots (not yet mkdir'd)
 * still see symlink escapes on intermediate dirs (Q4A / R1 residual).
 */
function projectThroughExistingAncestor(path: string): string | null {
  const resolved = resolve(path);
  if (existsSync(resolved)) {
    return tryRealpath(resolved);
  }
  let cursor = resolved;
  while (!existsSync(cursor)) {
    const parentDir = dirname(cursor);
    if (parentDir === cursor) break;
    cursor = parentDir;
  }
  if (!existsSync(cursor)) {
    // Nothing exists along the path — lexical fallback.
    return resolved;
  }
  const ancestorReal = tryRealpath(cursor);
  if (ancestorReal == null) return null;
  const suffix = relative(cursor, resolved);
  return suffix === "" ? ancestorReal : resolve(ancestorReal, suffix);
}

/**
 * True when `child` is under `parent` using real paths when available (Q4A / R1).
 * For not-yet-written targets / missing asset roots, realpath the nearest
 * existing ancestor of *both* sides (do not lexical-return when root is absent).
 */
function isInsideRoot(parent: string, child: string): boolean {
  const parentProjected = projectThroughExistingAncestor(parent);
  const childProjected = projectThroughExistingAncestor(child);
  if (parentProjected == null || childProjected == null) return false;
  return isInsideRootLexical(parentProjected, childProjected);
}

/** Q4A/R1: reject final-component symlinks before write (dangling or retarget). */
function rejectSymlinkWriteTarget(
  absPath: string,
): { ok: true } | { ok: false; reason: string } {
  try {
    if (lstatSync(absPath).isSymbolicLink()) {
      return {
        ok: false,
        reason:
          "target-is-symlink: refusing to follow/overwrite a flow/spec symlink outside asset root (Q4A)",
      };
    }
  } catch {
    // ENOENT — final component absent; safe to create a new regular file.
  }
  return { ok: true };
}

function normalizeMode(raw: E2eMode | undefined): E2eMode {
  if (raw === "contract-backed" || raw === "mock-backed") return raw;
  if (raw === "smoke-only") return "smoke-only";
  if (raw === "full-stack") return "full-stack";
  return "smoke-only";
}

/**
 * Q6A: mock/contract-backed must never be reported as full-stack.
 */
export function resolveReportedMode(hostMode: E2eMode | undefined): E2eMode {
  const mode = normalizeMode(hostMode);
  if (mode === "mock-backed" || mode === "contract-backed") return mode;
  return mode;
}

function stampNow(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}_${pad(d.getUTCMonth() + 1)}_${pad(d.getUTCDate())}-${pad(d.getUTCHours())}_${pad(d.getUTCMinutes())}_${pad(d.getUTCSeconds())}`;
}

function branchSlug(cwd: string): string {
  // Lightweight: no git spawn in unit path — use directory basename.
  try {
    const base = cwd.split(sep).filter(Boolean).pop();
    return (base && SAFE_SLUG_RE.test(base) ? base : "local").slice(0, 64);
  } catch {
    return "local";
  }
}

function hasPlaywrightConfig(cwd: string): boolean {
  for (const name of [
    "playwright.config.ts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
  ] as const) {
    if (existsSync(join(cwd, name))) return true;
  }
  try {
    const pkgPath = join(cwd, "package.json");
    if (!existsSync(pkgPath)) return false;
    const raw = readFileSync(pkgPath, "utf8");
    return /@playwright\/test|"playwright"/.test(raw);
  } catch {
    return false;
  }
}

/**
 * Q3A: existing consumer E2E dirs win; else AGENTS defaults.
 */
export function detectE2eConvention(
  cwd: string,
  surface: E2eSurface,
  host: E2eHostOptions = {},
): {
  kind: E2eConvention;
  flowRoot: string;
  reportRoot: string;
  playwrightRoot: string;
} {
  if (surface === "web") {
    const pwOverride =
      typeof host.playwrightRoot === "string" && host.playwrightRoot.length > 0
        ? resolve(cwd, host.playwrightRoot)
        : null;
    const existingTests = join(cwd, "tests", "e2e");
    const existingRootE2e = join(cwd, "e2e");
    // Convention-win: tests/e2e first, then root e2e/, else AGENTS default tests/e2e.
    const detectedExisting = isDir(existingTests)
      ? existingTests
      : isDir(existingRootE2e)
        ? existingRootE2e
        : null;
    const defaultPw = existingTests;
    const playwrightRoot = pwOverride ?? detectedExisting ?? defaultPw;
    const reportRoot =
      typeof host.reportRoot === "string" && host.reportRoot.length > 0
        ? resolve(cwd, host.reportRoot)
        : join(playwrightRoot, "reports", "html");
    if (
      pwOverride != null ||
      detectedExisting != null ||
      hasPlaywrightConfig(cwd)
    ) {
      return {
        kind: "existing-playwright-e2e",
        flowRoot: playwrightRoot,
        reportRoot,
        playwrightRoot,
      };
    }
    return {
      kind: "agents-default",
      flowRoot: defaultPw,
      reportRoot: join(defaultPw, "reports", "html"),
      playwrightRoot: defaultPw,
    };
  }

  // mobile | hybrid — Maestro paths
  const flowOverride =
    typeof host.flowRoot === "string" && host.flowRoot.length > 0
      ? resolve(cwd, host.flowRoot)
      : null;
  const maestroFlow = join(cwd, "maestro", "flow");
  const flowRoot = flowOverride ?? maestroFlow;
  const reportsExisting = join(cwd, ".maestro", "reports");
  const reportRoot =
    typeof host.reportRoot === "string" && host.reportRoot.length > 0
      ? resolve(cwd, host.reportRoot)
      : reportsExisting;

  if (flowOverride != null || isDir(maestroFlow)) {
    return {
      kind: isDir(maestroFlow) || flowOverride != null
        ? "existing-maestro-flow"
        : "agents-default",
      flowRoot,
      reportRoot,
      playwrightRoot: join(cwd, "tests", "e2e"),
    };
  }
  if (isDir(reportsExisting)) {
    return {
      kind: "existing-maestro-reports",
      flowRoot,
      reportRoot,
      playwrightRoot: join(cwd, "tests", "e2e"),
    };
  }
  return {
    kind: "agents-default",
    flowRoot: maestroFlow,
    reportRoot: reportsExisting,
    playwrightRoot: join(cwd, "tests", "e2e"),
  };
}

function isSlug(target: string): boolean {
  return (
    SAFE_SLUG_RE.test(target) &&
    !target.includes("/") &&
    !target.includes("\\")
  );
}

function isSafeRelative(target: string): boolean {
  if (target.length === 0) return false;
  if (isAbsolute(target)) return false;
  const n = normalize(target);
  if (n.startsWith("..") || n.includes(`${sep}..`)) return false;
  return true;
}

/**
 * Resolve optional model target under host cwd (Q4A).
 */
export function resolveE2eTargetPath(
  cwd: string,
  surface: E2eSurface,
  target: string | undefined,
  convention: { flowRoot: string; playwrightRoot: string },
  platform?: PlatformHint,
): { ok: true; path: string; slug: string } | { ok: false; reason: string } {
  const trimmed = typeof target === "string" ? target.trim() : "";
  if (!trimmed) {
    // Default smoke targets
    if (surface === "web") {
      const abs = join(convention.playwrightRoot, "smoke.spec.ts");
      if (!isInsideRoot(cwd, abs)) {
        return { ok: false, reason: "default-target-escapes-cwd" };
      }
      return { ok: true, path: abs, slug: "smoke" };
    }
    const platformDir =
      platform === "ios" || platform === "android"
        ? join(convention.flowRoot, platform)
        : convention.flowRoot;
    const abs = join(platformDir, "smoke.yml");
    if (!isInsideRoot(cwd, abs) && !isInsideRoot(convention.flowRoot, abs)) {
      // flowRoot may equal cwd/maestro/flow — still under cwd
      if (!isInsideRoot(cwd, abs)) {
        return { ok: false, reason: "default-target-escapes-cwd" };
      }
    }
    return { ok: true, path: abs, slug: "smoke" };
  }
  if (isAbsolute(trimmed)) {
    return { ok: false, reason: "absolute-target-forbidden" };
  }
  if (isSlug(trimmed)) {
    if (surface === "web") {
      const abs = join(convention.playwrightRoot, `${trimmed}.spec.ts`);
      if (!isInsideRoot(cwd, abs)) {
        return { ok: false, reason: "target-escapes-cwd" };
      }
      return { ok: true, path: abs, slug: trimmed };
    }
    const platformDir =
      platform === "ios" || platform === "android"
        ? join(convention.flowRoot, platform)
        : convention.flowRoot;
    const abs = join(platformDir, `${trimmed}.yml`);
    if (!isInsideRoot(cwd, abs)) {
      return { ok: false, reason: "target-escapes-cwd" };
    }
    return { ok: true, path: abs, slug: trimmed };
  }
  if (!isSafeRelative(trimmed)) {
    return { ok: false, reason: "invalid-target" };
  }
  const abs = resolve(cwd, trimmed);
  if (!isInsideRoot(cwd, abs)) {
    return { ok: false, reason: "target-escapes-cwd" };
  }
  // Q4A / R1: non-slug paths must stay under surface asset root + allowed extension.
  // Use realpath containment so flow/spec symlinks that escape the asset root are rejected.
  if (surface === "web") {
    if (
      !isInsideRootLexical(convention.playwrightRoot, abs) ||
      !isInsideRoot(convention.playwrightRoot, abs)
    ) {
      return { ok: false, reason: "target-outside-playwright-root" };
    }
    if (!isPlaywrightSpecPath(abs)) {
      return { ok: false, reason: "target-not-playwright-spec" };
    }
  } else {
    if (
      !isInsideRootLexical(convention.flowRoot, abs) ||
      !isInsideRoot(convention.flowRoot, abs)
    ) {
      return { ok: false, reason: "target-outside-flow-root" };
    }
    if (!isMaestroFlowPath(abs)) {
      return { ok: false, reason: "target-not-maestro-yaml" };
    }
  }
  const base = trimmed.split(/[/\\]/).pop() ?? trimmed;
  const slug =
    base.replace(/\.(yml|yaml|spec\.(ts|js|mjs|cjs|tsx|jsx)|test\.(ts|js|mjs|cjs|tsx|jsx)|ts|js|mjs|feature)$/i, "") ||
    "target";
  return { ok: true, path: abs, slug };
}

function isMaestroFlowPath(absPath: string): boolean {
  return /\.ya?ml$/i.test(absPath);
}

function isPlaywrightSpecPath(absPath: string): boolean {
  return /\.(spec|test)\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(absPath);
}

function reportStem(
  kind: "maestro" | "playwright",
  slug: string,
  cwd: string,
): string {
  const stamp = stampNow();
  const branch = branchSlug(cwd);
  if (kind === "maestro") {
    return `maestro-report-${slug}-${branch}-${stamp}`;
  }
  return `playwright-report-${slug}-${branch}-${stamp}`;
}

/** Pick only model-visible keys (Q4A); drop trust-handle extras if present. */
export function pickE2eInput(args: unknown): E2eInput {
  const src =
    args != null && typeof args === "object"
      ? (args as Record<string, unknown>)
      : {};
  for (const key of FORBIDDEN_MODEL_KEYS) {
    if (Object.prototype.hasOwnProperty.call(src, key)) {
      throw new Error(
        `sbtd_e2e model input forbids trust handle "${key}" (host-injected only)`,
      );
    }
  }
  const out: E2eInput = {
    surface: typeof src.surface === "string" ? src.surface : "",
    action: typeof src.action === "string" ? src.action : "",
  };
  if (typeof src.target === "string") out.target = src.target;
  // Accept path as alias for target (relative path·slug)
  if (out.target == null && typeof src.path === "string") {
    out.target = src.path;
  }
  if (typeof src.platform === "string") out.platform = src.platform;
  return out;
}

/** Schema helper for tests — model must not see trust-handle keys (Q4A). */
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

const DEFAULT_E2E_RUN_TIMEOUT_MS = 120_000;

type SpawnRunnerResult = {
  code: number | null;
  stdout: string;
  stderr: string;
  error?: Error;
  /** True when the child was spawned and then hit the wall-clock timeout (Q6A). */
  timedOut?: boolean;
};

function spawnRunner(
  command: string,
  args: string[],
  cwd: string,
  timeoutMs: number,
): Promise<SpawnRunnerResult> {
  return new Promise((resolvePromise) => {
    let settled = false;
    const finish = (result: SpawnRunnerResult) => {
      if (settled) return;
      settled = true;
      resolvePromise(result);
    };

    let child: ChildProcess;
    try {
      child = spawn(command, args, {
        cwd,
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
        shell: false,
      });
    } catch (err) {
      finish({
        code: null,
        stdout: "",
        stderr: "",
        error: err instanceof Error ? err : new Error(String(err)),
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
      try {
        child.kill("SIGTERM");
      } catch {
        // ignore
      }
      // Q6A: timeout fires only after spawn succeeded ⇒ started run ⇒ failed, not blocked.
      finish({
        code: null,
        stdout,
        stderr: `${stderr}\n(timed out after ${timeoutMs}ms)`.trim(),
        timedOut: true,
      });
    }, timeoutMs);

    child.on("error", (err) => {
      clearTimeout(timer);
      finish({ code: null, stdout, stderr, error: err });
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      finish({ code, stdout, stderr });
    });
  });
}

/** Detect npx --no-install failing because Playwright was never resolved (Q6A). */
function isNpxPlaywrightUnresolved(stderr: string, stdout: string): boolean {
  const text = `${stderr}\n${stdout}`;
  return /could not determine executable to run|not found:\s*playwright|No package .*playwright|ERR_MODULE_NOT_FOUND.*playwright|Cannot find (module|package).*playwright|npm error code ENOENT|npx:.*not found|could not find package.*playwright/i.test(
    text,
  );
}

/**
 * Production Maestro runner (Q3A): `maestro test --format junit --output …`.
 * Unit tests inject stubs and never hit this path.
 */
export async function defaultRunMaestro(
  ctx: E2eRunnerContext,
  timeoutMs: number = DEFAULT_E2E_RUN_TIMEOUT_MS,
): Promise<E2eRunnerResult> {
  mkdirSync(ctx.reportDir, { recursive: true });
  const slug =
    basename(ctx.targetPath).replace(/\.ya?ml$/i, "") || "flow";
  const stem = reportStem("maestro", slug, ctx.cwd);
  const reportPath = join(ctx.reportDir, `${stem}.xml`);

  if (!existsSync(ctx.targetPath)) {
    return {
      ok: false,
      didNotStart: true,
      summary: `Maestro flow missing at ${ctx.targetPath}; generate first or pass an existing flow.`,
    };
  }

  const result = await spawnRunner(
    "maestro",
    ["test", ctx.targetPath, "--format", "junit", "--output", reportPath],
    ctx.cwd,
    timeoutMs,
  );

  if (result.timedOut === true) {
    return {
      ok: false,
      failed: true,
      summary:
        result.stderr.trim() ||
        `maestro test timed out after ${timeoutMs}ms (runner started)`,
    };
  }

  if (result.error) {
    const err = result.error as NodeJS.ErrnoException;
    if (err.code === "ENOENT") {
      return {
        ok: false,
        didNotStart: true,
        summary:
          "Maestro CLI not found on PATH. Install Maestro locally, then re-run `sbtd_e2e` action=run (unit tests must inject runMaestro stubs).",
      };
    }
    return {
      ok: false,
      didNotStart: true,
      summary: `Failed to start maestro test: ${err.message}`,
    };
  }

  const nativeOk = existsSync(reportPath);
  if (result.code === 0) {
    return {
      ok: true,
      summary: "maestro test passed",
      ...(nativeOk ? { reportPath } : {}),
    };
  }
  return {
    ok: false,
    failed: true,
    summary:
      result.stderr.trim() ||
      result.stdout.trim() ||
      `maestro test exited ${result.code ?? "null"}`,
    ...(nativeOk ? { reportPath } : {}),
  };
}

/**
 * Production Playwright runner (Q3A): local `playwright` bin or `npx playwright test`.
 * Unit tests inject stubs and never hit this path.
 */
export async function defaultRunPlaywright(
  ctx: E2eRunnerContext,
  timeoutMs: number = DEFAULT_E2E_RUN_TIMEOUT_MS,
): Promise<E2eRunnerResult> {
  mkdirSync(ctx.reportDir, { recursive: true });
  const slug =
    basename(ctx.targetPath)
      .replace(/\.(spec|test)\.(ts|tsx|js|jsx|mjs|cjs)$/i, "") || "spec";
  const stem = reportStem("playwright", slug, ctx.cwd);
  const reportPath = join(ctx.reportDir, `${stem}.html`);
  const tempDir = join(ctx.reportDir, ".playwright-html-current");
  mkdirSync(tempDir, { recursive: true });

  if (!existsSync(ctx.targetPath)) {
    return {
      ok: false,
      didNotStart: true,
      summary: `Playwright spec missing at ${ctx.targetPath}; generate first or pass an existing spec.`,
    };
  }

  const localBin = join(ctx.cwd, "node_modules", ".bin", "playwright");
  const useLocal = existsSync(localBin);
  if (!useLocal) {
    // Q6A: npx --no-install with no Playwright package never runs tests ⇒ blocked/didNotStart.
    const hasPlaywrightPkg =
      existsSync(join(ctx.cwd, "node_modules", "@playwright", "test")) ||
      existsSync(join(ctx.cwd, "node_modules", "playwright")) ||
      existsSync(join(ctx.cwd, "node_modules", "playwright-core"));
    if (!hasPlaywrightPkg) {
      return {
        ok: false,
        didNotStart: true,
        summary:
          "Playwright package not found for `npx --no-install` (no node_modules/.bin/playwright and no @playwright/test|playwright). Install @playwright/test in the project, then re-run action=run (unit tests must inject runPlaywright stubs).",
      };
    }
  }
  const command = useLocal ? localBin : "npx";
  const args = useLocal
    ? ["test", ctx.targetPath, "--reporter=html"]
    : ["--no-install", "playwright", "test", ctx.targetPath, "--reporter=html"];

  const result = await spawnRunner(command, args, ctx.cwd, timeoutMs);

  if (result.timedOut === true) {
    return {
      ok: false,
      failed: true,
      summary:
        result.stderr.trim() ||
        `playwright test timed out after ${timeoutMs}ms (runner started)`,
    };
  }

  if (result.error) {
    const err = result.error as NodeJS.ErrnoException;
    if (err.code === "ENOENT") {
      return {
        ok: false,
        didNotStart: true,
        summary:
          "Playwright binary not found (node_modules/.bin/playwright or npx). Install @playwright/test in the project, then re-run action=run (unit tests must inject runPlaywright stubs).",
      };
    }
    return {
      ok: false,
      didNotStart: true,
      summary: `Failed to start Playwright: ${err.message}`,
    };
  }

  // npx --no-install may exit nonzero when the package still cannot be resolved.
  if (
    !useLocal &&
    result.code !== 0 &&
    isNpxPlaywrightUnresolved(result.stderr, result.stdout)
  ) {
    return {
      ok: false,
      didNotStart: true,
      summary:
        result.stderr.trim() ||
        result.stdout.trim() ||
        "Playwright package unresolved via npx --no-install; install @playwright/test then re-run.",
    };
  }

  // Promote native HTML output when present (temp index or default playwright-report).
  const candidates = [
    join(tempDir, "index.html"),
    join(ctx.cwd, "playwright-report", "index.html"),
    join(ctx.reportDir, "index.html"),
  ];
  let nativeSource: string | undefined;
  for (const c of candidates) {
    if (existsSync(c)) {
      nativeSource = c;
      break;
    }
  }
  if (nativeSource != null) {
    try {
      writeFileSync(reportPath, readFileSync(nativeSource));
    } catch {
      // fall through — only claim reportPath when file exists
    }
  }

  const nativeOk = existsSync(reportPath);
  if (result.code === 0) {
    return {
      ok: true,
      summary: "playwright test passed",
      ...(nativeOk ? { reportPath } : {}),
    };
  }
  return {
    ok: false,
    failed: true,
    summary:
      result.stderr.trim() ||
      result.stdout.trim() ||
      `playwright test exited ${result.code ?? "null"}`,
    ...(nativeOk ? { reportPath } : {}),
  };
}

/**
 * Resolve host-owned cwd / maestro / runners for production registration (Q4A / Q3A).
 * Wires default Maestro/Playwright runners so production `action=run` is not a
 * permanent `runner-not-injected` dead path; unit tests override with stubs.
 */
export function resolveE2eHost(ctx: E2ePluginHost): E2eHostOptions {
  const explicit = ctx.e2eHost ?? {};
  const cwd =
    typeof explicit.cwd === "string" && explicit.cwd.length > 0
      ? explicit.cwd
      : typeof ctx.cwd === "string" && ctx.cwd.length > 0
        ? ctx.cwd
        : process.cwd();
  return {
    ...explicit,
    cwd,
    runMaestro: explicit.runMaestro ?? defaultRunMaestro,
    runPlaywright: explicit.runPlaywright ?? defaultRunPlaywright,
  };
}

function blockedResult(
  surface: E2eSurface,
  action: E2eAction,
  mode: E2eMode,
  kind: string,
  reason: string,
  extras: Partial<E2eToolResult> = {},
): E2eToolResult {
  const outcome: E2eOutcome =
    extras.outcome === "skipped-by-user" ? "skipped-by-user" : "blocked";
  const result: E2eToolResult = {
    ok: false,
    surface,
    action,
    mode,
    note: extras.note ?? reason,
    outcome,
    calledT12Preflight: extras.calledT12Preflight ?? false,
    runnerStarted: false,
    blocked: { kind, reason },
  };
  if (extras.convention !== undefined) result.convention = extras.convention;
  if (extras.path !== undefined) result.path = extras.path;
  if (extras.reportPath !== undefined) result.reportPath = extras.reportPath;
  if (extras.reportMdPath !== undefined) result.reportMdPath = extras.reportMdPath;
  if (extras.preflight !== undefined) result.preflight = extras.preflight;
  return result;
}

function withOptionalPreflight<T extends E2eToolResult>(
  result: T,
  preflightResult: PreflightResult | undefined,
): T {
  if (preflightResult !== undefined) {
    result.preflight = preflightResult;
  }
  return result;
}

async function isBrowserBusy(host: E2eHostOptions): Promise<boolean> {
  const v = host.browserControllerBusy;
  if (typeof v === "function") return Boolean(await v());
  return Boolean(v);
}

function needsT12(surface: E2eSurface, action: E2eAction): boolean {
  // Q1B: mobile|hybrid generate/run always re-call T12; web skips.
  // action=preflight on mobile|hybrid also calls T12 (that is the action).
  if (surface === "web") return false;
  return (
    action === "preflight" || action === "generate" || action === "run"
  );
}

function defaultMaestroFlowBody(
  slug: string,
  appId: string,
  selectorFacts: string[],
): string {
  const assertions = selectorFacts.map(
    (fact) => `- assertVisible: ${JSON.stringify(fact)}`,
  );
  return [
    `appId: ${appId}`,
    "---",
    `- launchApp`,
    `# smoke flow generated by sbtd_e2e for ${slug}`,
    ...assertions,
    "",
  ].join("\n");
}

function defaultPlaywrightSpecBody(
  slug: string,
  selectorFacts: string[],
): string {
  const asserts = selectorFacts.map(
    (fact) =>
      `  await expect(page.getByText(${JSON.stringify(fact)})).toBeVisible();`,
  );
  return [
    `import { test, expect } from "@playwright/test";`,
    "",
    `test("${slug} smoke", async ({ page }) => {`,
    `  // Generated by sbtd_e2e from host-injected selector facts.`,
    `  await page.goto("/");`,
    ...asserts,
    `});`,
    "",
  ].join("\n");
}

/** Peel balanced outer capturing / non-capturing groups wrapping the whole pattern. */
function unwrapWholePatternGroups(pattern: string): string {
  let s = pattern;
  while (s.length >= 2 && s.startsWith("(") && s.endsWith(")")) {
    let depth = 0;
    let wrapsWhole = true;
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (ch === "(") depth += 1;
      else if (ch === ")") {
        depth -= 1;
        if (depth === 0 && i !== s.length - 1) {
          wrapsWhole = false;
          break;
        }
        if (depth < 0) {
          wrapsWhole = false;
          break;
        }
      }
    }
    if (!wrapsWhole || depth !== 0) break;
    let inner = s.slice(1, -1);
    if (inner.startsWith("?:")) inner = inner.slice(2);
    if (inner.length === 0 || inner === s) break;
    s = inner;
  }
  return s;
}

/** True for wildcard-only placeholders that must not become assertVisible / title regexes (Q4A / R2). */
function isWildcardOnlySelectorFact(fact: string): boolean {
  const t = fact.trim();
  if (t.length === 0) return true;
  // Strip /pattern/flags wrappers (e.g. /.*/ / .*/i / /(.*)/).
  const stripped = /^\/(.+)\/[a-z]*$/i.test(t)
    ? t.replace(/^\/(.+)\/[a-z]*$/i, "$1")
    : t;
  // Peel whole-pattern groups so (.*) / (?:.+) / ((.*)) count as catch-alls.
  const bare = unwrapWholePatternGroups(stripped);
  return (
    bare === ".*" ||
    bare === ".+" ||
    bare === "*" ||
    bare === "^.*$" ||
    bare === "^.+$" ||
    bare === "[\\s\\S]*" ||
    bare === "[\\S\\s]*"
  );
}

function normalizeSelectorFacts(raw: string[] | undefined): string[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((s): s is string => typeof s === "string")
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .filter((s) => !isWildcardOnlySelectorFact(s));
}

function hasAffirmativeCredentials(
  host: E2eHostOptions,
  surface: E2eSurface,
): boolean {
  if (surface === "web") return true;
  if (host.credentialsReady === true) return true;
  const accounts = host.maestro?.accounts;
  if (accounts === true) return true;
  return typeof accounts === "string" && accounts.trim().length > 0;
}

function chineseReportMd(opts: {
  surface: E2eSurface;
  action: E2eAction;
  outcome: E2eOutcome;
  mode: E2eMode;
  summary: string;
}): string {
  return [
    `# E2E 报告（${opts.surface} / ${opts.action}）`,
    "",
    `- 结果: ${opts.outcome}`,
    `- 模式: ${opts.mode}`,
    "",
    opts.summary,
    "",
  ].join("\n");
}

/**
 * Core tool logic (Q1B–Q6A).
 */
export async function sbtdE2e(
  sessionId: string,
  input: E2eInput,
  host: E2eHostOptions = {},
): Promise<E2eToolResult> {
  const mode = resolveReportedMode(host.mode);

  if (!isE2eSurface(input.surface)) {
    return blockedResult(
      "web",
      "preflight",
      mode,
      "invalid-surface",
      `surface must be one of ${E2E_SURFACES.join(", ")}`,
    );
  }
  if (!isE2eAction(input.action)) {
    return blockedResult(
      input.surface,
      "preflight",
      mode,
      "invalid-action",
      `action must be one of ${E2E_ACTIONS.join(", ")}`,
    );
  }

  const surface = input.surface;
  const action = input.action;
  const cwd = resolveCwd(host);

  let platform: PlatformHint | undefined;
  if (input.platform != null && input.platform !== "") {
    if (!isPlatformHint(input.platform)) {
      return blockedResult(
        surface,
        action,
        mode,
        "invalid-platform",
        `platform hint must be "ios" | "android" (got ${JSON.stringify(input.platform)})`,
      );
    }
    platform = input.platform;
  }

  if (host.userDeclinedAssist === true) {
    return blockedResult(
      surface,
      action,
      mode,
      "skipped-by-user",
      "User declined install/assist; do not pretend E2E ran.",
      { outcome: "skipped-by-user", calledT12Preflight: false },
    );
  }

  // Q6A: never steal — busy controller ⇒ blocked (web generate/run / web preflight).
  if (surface === "web" && (action === "generate" || action === "run" || action === "preflight")) {
    if (await isBrowserBusy(host)) {
      return blockedResult(
        surface,
        action,
        mode,
        "browser-controller-busy",
        "Another browser controller is already live; refusing to kill/steal the lock.",
      );
    }
  }

  // Q1B S1: mobile|hybrid always re-call T12 before target rejection.
  let calledT12Preflight = false;
  let preflightResult: PreflightResult | undefined;
  const callT12 = needsT12(surface, action);
  if (callT12) {
    calledT12Preflight = true;
    const runPreflight = host.preflight ?? t12Preflight;
    const maestroOpts: MaestroOptions = {
      ...(host.maestro ?? {}),
      cwd,
      sessionId,
      ...(platform != null ? { platform } : {}),
      // Always re-call — do not skip based on stale session.maestro (Q1B).
    };
    preflightResult = await runPreflight(maestroOpts);
    if (preflightResult.lastPreflight !== "ok") {
      // Q1B / Q6A / T12: blocked = did not start; no maestro test process.
      return {
        ok: false,
        surface,
        action,
        outcome: "blocked",
        mode,
        preflight: preflightResult,
        calledT12Preflight: true,
        runnerStarted: false,
        blocked: {
          kind: "maestro-preflight-blocked",
          reason:
            preflightResult.guidance ||
            `T12 preflight blocked (missing: ${preflightResult.missing.join(", ")})`,
        },
        note:
          action === "preflight"
            ? preflightResult.guidance
            : `Blocked before ${action}: T12 preflight not ok — no maestro test process started.`,
      };
    }
  }

  const convention = detectE2eConvention(cwd, surface, host);
  const targetResolved = resolveE2eTargetPath(
    cwd,
    surface,
    input.target,
    convention,
    platform,
  );
  if (!targetResolved.ok) {
    return blockedResult(
      surface,
      action,
      mode,
      "invalid-target",
      targetResolved.reason,
      {
        calledT12Preflight,
        convention: convention.kind,
        ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
      },
    );
  }

  // action === preflight
  if (action === "preflight") {
    if (surface === "web") {
      return {
        ok: true,
        surface,
        action,
        outcome: "ok",
        mode,
        convention: convention.kind,
        path: targetResolved.path,
        calledT12Preflight: false,
        runnerStarted: false,
        note: "Web preflight: T12 Maestro skipped; browser controller available.",
      };
    }
    return withOptionalPreflight(
      {
        ok: true,
        surface,
        action,
        outcome: "ok",
        mode,
        convention: convention.kind,
        path: targetResolved.path,
        calledT12Preflight: true,
        runnerStarted: false,
        note: preflightResult?.guidance ?? "Maestro preflight ok.",
      },
      preflightResult,
    );
  }

  // generate / run — additional generate gates
  if (action === "generate") {
    const selectorFacts = normalizeSelectorFacts(host.selectorFacts);
    // Q4A / R2: require affirmative selector facts (undefined ≠ ok); no fragile wildcards.
    if (host.selectorsReady !== true || selectorFacts.length === 0) {
      const reason =
        surface === "web"
          ? "Web generate blocked — affirmative selectors/locator facts required; will not invent fragile tests."
          : "Maestro Flow Assets: blocked — selectors/locator facts missing; will not invent fragile flow.";
      return blockedResult(
        surface,
        action,
        mode,
        "missing-selectors",
        reason,
        {
          calledT12Preflight,
          convention: convention.kind,
          path: targetResolved.path,
          ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
        },
      );
    }
    if (!hasAffirmativeCredentials(host, surface)) {
      return blockedResult(
        surface,
        action,
        mode,
        "missing-credentials",
        "Maestro Flow Assets: blocked — credentials/accounts not confirmed.",
        {
          calledT12Preflight,
          convention: convention.kind,
          path: targetResolved.path,
          ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
        },
      );
    }

    const assetRoot =
      surface === "web" ? convention.playwrightRoot : convention.flowRoot;
    // Q4A / R1 residual: refuse symlink write targets and realpath escapes (mirror bdd.ts).
    const symlinkGate = rejectSymlinkWriteTarget(targetResolved.path);
    if (!symlinkGate.ok) {
      return blockedResult(
        surface,
        action,
        mode,
        "invalid-target",
        symlinkGate.reason,
        {
          calledT12Preflight,
          convention: convention.kind,
          path: targetResolved.path,
          ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
        },
      );
    }
    // Asset-root + cwd realpath gates: missing roots still project via ancestors
    // so symlink tests/ + absent tests/e2e cannot mkdir/write outside the project.
    if (
      !isInsideRoot(assetRoot, targetResolved.path) ||
      !isInsideRoot(cwd, targetResolved.path)
    ) {
      return blockedResult(
        surface,
        action,
        mode,
        "invalid-target",
        surface === "web"
          ? "target-outside-playwright-root (symlink/realpath escape)"
          : "target-outside-flow-root (symlink/realpath escape)",
        {
          calledT12Preflight,
          convention: convention.kind,
          path: targetResolved.path,
          ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
        },
      );
    }

    mkdirSync(dirname(targetResolved.path), { recursive: true });
    if (surface === "web") {
      writeFileSync(
        targetResolved.path,
        defaultPlaywrightSpecBody(targetResolved.slug, selectorFacts),
        "utf8",
      );
    } else {
      const appId =
        (typeof host.maestro?.appId === "string" && host.maestro.appId) ||
        (typeof host.maestro?.bundleId === "string" && host.maestro.bundleId) ||
        "com.example.app";
      writeFileSync(
        targetResolved.path,
        defaultMaestroFlowBody(targetResolved.slug, appId, selectorFacts),
        "utf8",
      );
    }
    return withOptionalPreflight(
      {
        ok: true,
        surface,
        action,
        outcome: "ok",
        mode,
        convention: convention.kind,
        path: targetResolved.path,
        calledT12Preflight,
        runnerStarted: false,
        note: `Generated ${relative(cwd, targetResolved.path)} (convention=${convention.kind}; mode=${mode})`,
      },
      preflightResult,
    );
  }

  // action === run — production defaults via resolveE2eHost / fallback (Q3A / R3)
  const reportDir = convention.reportRoot;
  mkdirSync(reportDir, { recursive: true });

  const runnerCtx: E2eRunnerContext = {
    cwd,
    surface,
    action,
    targetPath: targetResolved.path,
    reportDir,
    ...(platform != null ? { platform } : {}),
    mode,
  };

  const runPlaywright = host.runPlaywright ?? defaultRunPlaywright;
  const runMaestro = host.runMaestro ?? defaultRunMaestro;
  const runnerResult: E2eRunnerResult =
    surface === "web"
      ? await runPlaywright(runnerCtx)
      : await runMaestro(runnerCtx);

  if (runnerResult.didNotStart === true) {
    return blockedResult(
      surface,
      action,
      mode,
      "runner-unavailable",
      runnerResult.summary ??
        "E2E runner unavailable after start attempt; see host guidance.",
      {
        calledT12Preflight,
        convention: convention.kind,
        path: targetResolved.path,
        ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
      },
    );
  }

  // Q6A / R4: formal reportPath + 中文 .md only when native reporter file exists.
  const nativeReportPath =
    typeof runnerResult.reportPath === "string" &&
    runnerResult.reportPath.length > 0 &&
    existsSync(runnerResult.reportPath)
      ? runnerResult.reportPath
      : undefined;

  let reportMdPath: string | undefined;
  if (nativeReportPath != null) {
    reportMdPath =
      typeof runnerResult.reportMdPath === "string" &&
      runnerResult.reportMdPath.length > 0
        ? runnerResult.reportMdPath
        : join(
            dirname(nativeReportPath),
            `${basename(nativeReportPath, extname(nativeReportPath))}.md`,
          );
    const outcomeLabel: E2eOutcome = runnerResult.ok ? "ok" : "failed";
    if (!existsSync(reportMdPath)) {
      writeFileSync(
        reportMdPath,
        chineseReportMd({
          surface,
          action,
          outcome: outcomeLabel,
          mode,
          summary:
            runnerResult.summary ??
            (runnerResult.ok ? "E2E run passed." : "E2E assertions failed."),
        }),
        "utf8",
      );
    }
  }

  if (runnerResult.ok) {
    return withOptionalPreflight(
      {
        ok: true,
        surface,
        action,
        outcome: "ok",
        mode,
        convention: convention.kind,
        path: targetResolved.path,
        ...(nativeReportPath != null ? { reportPath: nativeReportPath } : {}),
        ...(reportMdPath != null ? { reportMdPath } : {}),
        calledT12Preflight,
        runnerStarted: true,
        note: runnerResult.summary ?? `E2E run ok (mode=${mode})`,
      },
      preflightResult,
    );
  }

  // Runner started and lost ⇒ failed (not blocked) (Q6A)
  return withOptionalPreflight(
    {
      ok: false,
      surface,
      action,
      outcome: "failed",
      mode,
      convention: convention.kind,
      path: targetResolved.path,
      ...(nativeReportPath != null ? { reportPath: nativeReportPath } : {}),
      ...(reportMdPath != null ? { reportMdPath } : {}),
      calledT12Preflight,
      runnerStarted: true,
      note: runnerResult.summary ?? "E2E run failed assertions.",
    },
    preflightResult,
  );
}


export const SBTD_E2E_DESCRIPTION =
  "Preflight, generate, or run Web / Mobile / Hybrid E2E. " +
  "surface=web|mobile|hybrid; action=preflight|generate|run. " +
  "hybrid = hybrid app (RN/Flutter/WebView) on a device via Maestro — not serial Playwright+Maestro. " +
  "mobile|hybrid generate/run always re-call Maestro preflight (T12); not ok ⇒ blocked and no maestro test. " +
  "web skips T12. Model args: surface, action, optional cwd-relative target path/slug, optional platform hint. " +
  "cwd, declared app facts, binaries, browser-controller lock, and credentials are host-injected — " +
  "do not pass cwd, mcp, runRefresh, serverName, or toolNames. " +
  "Existing project E2E dirs win; mock/contract modes must not claim full-stack. " +
  "Never kill/steal another browser controller.";

export function createE2eTool(host: E2eHostOptions = {}): E2eToolDefinition {
  return {
    name: SBTD_E2E_TOOL_NAME,
    description: SBTD_E2E_DESCRIPTION,
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        surface: {
          type: "string",
          enum: [...E2E_SURFACES],
          description:
            "web = Playwright (skips T12); mobile = native Maestro; hybrid = hybrid app device-side Maestro (still T12).",
        },
        action: {
          type: "string",
          enum: [...E2E_ACTIONS],
          description:
            "preflight = env check; generate = write flow/spec; run = execute (mobile|hybrid re-call T12 first).",
        },
        target: {
          type: "string",
          description:
            "Optional cwd-relative flow/feature path or slug (e.g. smoke, maestro/flow/smoke.yml).",
        },
        platform: {
          type: "string",
          enum: ["ios", "android"],
          description: "Optional platform hint for mobile|hybrid (model-visible only).",
        },
      },
      required: ["surface", "action"],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          ok: { type: "boolean" },
          surface: { type: "string" },
          action: { type: "string" },
          outcome: { type: "string" },
          mode: { type: "string" },
          convention: { type: "string" },
          path: { type: "string" },
          reportPath: { type: "string" },
          reportMdPath: { type: "string" },
          preflight: { type: "object" },
          calledT12Preflight: { type: "boolean" },
          runnerStarted: { type: "boolean" },
          blocked: { type: "object" },
          note: { type: "string" },
        },
      },
      render(_args, value) {
        const lines = [
          `surface: ${value.surface}`,
          `action: ${value.action}`,
          `outcome: ${value.outcome}`,
          `mode: ${value.mode}`,
          `calledT12Preflight: ${value.calledT12Preflight}`,
          `runnerStarted: ${value.runnerStarted}`,
        ];
        if (value.convention !== undefined) {
          lines.push(`convention: ${value.convention}`);
        }
        if (value.path !== undefined) lines.push(`path: ${value.path}`);
        if (value.reportPath !== undefined) {
          lines.push(`reportPath: ${value.reportPath}`);
        }
        if (value.blocked !== undefined) {
          lines.push(
            `blocked.kind: ${value.blocked.kind}`,
            `blocked.reason: ${value.blocked.reason}`,
          );
        }
        if (value.preflight !== undefined) {
          lines.push(
            `preflight.lastPreflight: ${value.preflight.lastPreflight}`,
            `preflight.missing: ${value.preflight.missing.join(", ") || "(none)"}`,
          );
        }
        if (value.note !== undefined) {
          lines.push("", value.note);
        }
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe(args) {
      const action =
        args != null &&
        typeof args === "object" &&
        typeof (args as { action?: unknown }).action === "string"
          ? (args as { action: string }).action
          : "";
      return action === "preflight";
    },
    async execute(args, exec) {
      const modelArgs = pickE2eInput(args);
      return sbtdE2e(sessionIdFromExec(exec), modelArgs, host);
    },
  };
}

export function registerE2eTool(
  ctx: ToolsHost,
  host: E2eHostOptions = {},
): void {
  ctx.tools.register(createE2eTool(host));
}
