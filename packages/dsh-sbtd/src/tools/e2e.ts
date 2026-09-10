/**
 * sbtd_e2e (T13) — Web / Mobile / Hybrid preflight · generate · run.
 *
 * Locks: Q1B / Q2A / Q3A / Q4A / Q5A / Q6A.
 * Consumes T12 `preflight()` as-is (never rewrite backends/maestro.ts).
 * Host injects cwd + T12 declared facts + binaries + browser lock + creds.
 * Model never supplies trust handles (cwd / mcp / runRefresh / serverName / toolNames).
 * Unit tests never spawn maestro test / live browser (injectable runners).
 */

import {
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import {
  dirname,
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
  /** Generate selectors / locator facts; missing on generate ⇒ blocked. */
  selectorsReady?: boolean;
  /** Host credentials confirmed for generate/run; missing ⇒ blocked when needed. */
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
  summary?: string;
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
    const defaultPw = existingTests;
    const playwrightRoot = pwOverride ?? defaultPw;
    const reportRoot =
      typeof host.reportRoot === "string" && host.reportRoot.length > 0
        ? resolve(cwd, host.reportRoot)
        : join(playwrightRoot, "reports", "html");
    if (pwOverride != null || isDir(existingTests) || hasPlaywrightConfig(cwd)) {
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
      if (!isInsideRootLexical(cwd, abs)) {
        return { ok: false, reason: "default-target-escapes-cwd" };
      }
      return { ok: true, path: abs, slug: "smoke" };
    }
    const platformDir =
      platform === "ios" || platform === "android"
        ? join(convention.flowRoot, platform)
        : convention.flowRoot;
    const abs = join(platformDir, "smoke.yml");
    if (!isInsideRootLexical(cwd, abs) && !isInsideRootLexical(convention.flowRoot, abs)) {
      // flowRoot may equal cwd/maestro/flow — still under cwd
      if (!isInsideRootLexical(cwd, abs)) {
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
      if (!isInsideRootLexical(cwd, abs)) {
        return { ok: false, reason: "target-escapes-cwd" };
      }
      return { ok: true, path: abs, slug: trimmed };
    }
    const platformDir =
      platform === "ios" || platform === "android"
        ? join(convention.flowRoot, platform)
        : convention.flowRoot;
    const abs = join(platformDir, `${trimmed}.yml`);
    if (!isInsideRootLexical(cwd, abs)) {
      return { ok: false, reason: "target-escapes-cwd" };
    }
    return { ok: true, path: abs, slug: trimmed };
  }
  if (!isSafeRelative(trimmed)) {
    return { ok: false, reason: "invalid-target" };
  }
  const abs = resolve(cwd, trimmed);
  if (!isInsideRootLexical(cwd, abs)) {
    return { ok: false, reason: "target-escapes-cwd" };
  }
  const base = trimmed.split(/[/\\]/).pop() ?? trimmed;
  const slug = base.replace(/\.(yml|yaml|ts|js|mjs|feature)$/i, "") || "target";
  return { ok: true, path: abs, slug };
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

/**
 * Resolve host-owned cwd / maestro / runners for production registration (Q4A).
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

function defaultMaestroFlowBody(slug: string, appId: string): string {
  return [
    `appId: ${appId}`,
    "---",
    `- launchApp`,
    `# smoke flow generated by sbtd_e2e for ${slug}`,
    `- assertVisible: ".*"`,
    "",
  ].join("\n");
}

function defaultPlaywrightSpecBody(slug: string): string {
  return [
    `import { test, expect } from "@playwright/test";`,
    "",
    `test("${slug} smoke", async ({ page }) => {`,
    `  // Generated by sbtd_e2e — replace URL/selectors with project facts.`,
    `  await page.goto("/");`,
    `  await expect(page).toHaveTitle(/.*/);`,
    `});`,
    "",
  ].join("\n");
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
    );
  }

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
        convention: convention.kind,
        path: targetResolved.path,
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
    if (surface !== "web") {
      // Missing selectors at generate ⇒ blocked, no fragile flow (Q4A / §3.5)
      if (host.selectorsReady === false) {
        return blockedResult(
          surface,
          action,
          mode,
          "missing-selectors",
          "Maestro Flow Assets: blocked — selectors/locator facts missing; will not invent fragile flow.",
          {
            calledT12Preflight,
            convention: convention.kind,
            path: targetResolved.path,
            ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
          },
        );
      }
      if (host.credentialsReady === false) {
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
    } else if (host.selectorsReady === false) {
      return blockedResult(
        surface,
        action,
        mode,
        "missing-selectors",
        "Web generate blocked — selectors missing; will not invent fragile tests.",
        { calledT12Preflight: false, convention: convention.kind, path: targetResolved.path },
      );
    }

    mkdirSync(dirname(targetResolved.path), { recursive: true });
    if (surface === "web") {
      writeFileSync(
        targetResolved.path,
        defaultPlaywrightSpecBody(targetResolved.slug),
        "utf8",
      );
    } else {
      const appId =
        (typeof host.maestro?.appId === "string" && host.maestro.appId) ||
        (typeof host.maestro?.bundleId === "string" && host.maestro.bundleId) ||
        "com.example.app";
      writeFileSync(
        targetResolved.path,
        defaultMaestroFlowBody(targetResolved.slug, appId),
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

  // action === run
  const stem =
    surface === "web"
      ? reportStem("playwright", targetResolved.slug, cwd)
      : reportStem("maestro", targetResolved.slug, cwd);
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

  let runnerResult: E2eRunnerResult;
  let runnerStarted = false;

  if (surface === "web") {
    if (host.runPlaywright == null) {
      // Production without injectable runner: do not spawn live browser in this slice's
      // default path when unset — report blocked (no silent live spawn). Hosts inject.
      return blockedResult(
        surface,
        action,
        mode,
        "runner-not-injected",
        "Playwright runner not host-injected; refusing to spawn a live browser from unit/default path.",
        { calledT12Preflight: false, convention: convention.kind, path: targetResolved.path },
      );
    }
    runnerStarted = true;
    runnerResult = await host.runPlaywright(runnerCtx);
  } else {
    if (host.runMaestro == null) {
      return blockedResult(
        surface,
        action,
        mode,
        "runner-not-injected",
        "Maestro runner not host-injected; refusing to spawn `maestro test` from unit/default path.",
        {
          calledT12Preflight,
          convention: convention.kind,
          path: targetResolved.path,
          ...(preflightResult !== undefined ? { preflight: preflightResult } : {}),
        },
      );
    }
    runnerStarted = true;
    runnerResult = await host.runMaestro(runnerCtx);
  }

  const reportPath =
    runnerResult.reportPath ??
    join(
      reportDir,
      surface === "web" ? `${stem}.html` : `${stem}.xml`,
    );
  const reportMdPath =
    runnerResult.reportMdPath ?? join(reportDir, `${stem}.md`);

  if (runnerResult.ok) {
    // Named reports + 中文 .md only when a native reporter actually ran (Q6A).
    if (!existsSync(reportMdPath)) {
      writeFileSync(
        reportMdPath,
        chineseReportMd({
          surface,
          action,
          outcome: "ok",
          mode,
          summary: runnerResult.summary ?? "E2E run passed.",
        }),
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
        reportPath,
        reportMdPath,
        calledT12Preflight,
        runnerStarted: true,
        note: runnerResult.summary ?? `E2E run ok (mode=${mode})`,
      },
      preflightResult,
    );
  }

  // Runner started and lost ⇒ failed (not blocked) (Q6A)
  if (!existsSync(reportMdPath)) {
    writeFileSync(
      reportMdPath,
      chineseReportMd({
        surface,
        action,
        outcome: "failed",
        mode,
        summary: runnerResult.summary ?? "E2E assertions failed.",
      }),
      "utf8",
    );
  }
  return withOptionalPreflight(
    {
      ok: false,
      surface,
      action,
      outcome: "failed",
      mode,
      convention: convention.kind,
      path: targetResolved.path,
      reportPath,
      reportMdPath,
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
