/**
 * sbtd_bdd (T11) — write / sync / read persistent `.feature` files.
 *
 * Locks: Q1C / Q2B / Q3A / Q4A / Q5A / Q6A.
 * Host injects cwd (+ optional featureRoot / allowedExtraRoots).
 * Model never supplies trust handles (cwd / mcp / runRefresh / serverName / toolNames).
 * No session.bdd. No manuals embed. No validate.ts change.
 */

import {
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  realpathSync,
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
  type PlanToolExec,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";

export const SBTD_BDD_TOOL_NAME = "sbtd_bdd";

export const BDD_INTENTS = ["write", "sync", "read"] as const;
export type BddIntent = (typeof BDD_INTENTS)[number];

/** Model-visible args only (Q1C). */
export type BddInput = {
  intent: string;
  /**
   * Capability slug (e.g. `login`) or cwd-relative feature path
   * (e.g. `features/login.feature`). Required for write; optional filter for sync/read.
   */
  target?: string;
  /** Feature body for write (Gherkin text). */
  content?: string;
  /** Alias for content. */
  body?: string;
  /**
   * Optional user-supplied extra repo roots for sync/read only (Q1C).
   * Never invented; host-validated before scan.
   */
  extra_paths?: string[];
  /**
   * When true, sync/read require at least one validated extra path;
   * absent/invalid ⇒ blocked (no invented cross-repo SoT).
   */
  cross_repo_required?: boolean;
};

/**
 * Host-injected trust handles (Q1C). Never exposed on the model tool schema.
 */
export type BddHostOptions = {
  cwd?: string;
  /** Primary feature-root override; else derived from cwd conventions (Q2B). */
  featureRoot?: string;
  /**
   * Host allowlist of absolute roots under which extra_paths may resolve (Q1C).
   * Required for any model-supplied extra_paths: unset or empty ⇒ default-deny
   * (extras rejected; directory existence alone is not host provenance).
   */
  allowedExtraRoots?: string[];
};

export type BddPluginHost = ToolsHost & {
  cwd?: string;
  bddHost?: BddHostOptions;
};

export type FeatureCatalogEntry = {
  path: string;
  root: string;
  featureTitle: string | null;
  scenarioCount: number;
  tags: string[];
};

export type BddBlocked = {
  kind: string;
  reason: string;
};

export type BddToolResult = {
  ok: boolean;
  intent: BddIntent;
  status: "done" | "blocked";
  /** Q5A: read always reports Mutation: none. */
  mutation: "none" | "write" | "sync";
  path?: string;
  convention?:
    | "existing-features-dir"
    | "existing-feature-files"
    | "bdd-runner"
    | "agents-default"
    | "ambiguous-feature-trees";
  catalog?: FeatureCatalogEntry[];
  sync?: {
    mode: "run" | "blocked";
    rootsScanned: string[];
    features: FeatureCatalogEntry[];
    updated: string[];
    created: string[];
    unchanged: string[];
    note: string;
  };
  blocked?: BddBlocked;
  note?: string;
  /** Echo of written/sync content when applicable. */
  content?: string;
};

export type BddToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: BddToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => boolean;
  execute: (args: BddInput, exec: PlanToolExec) => Promise<BddToolResult>;
};

const FORBIDDEN_MODEL_KEYS = [
  "cwd",
  "mcp",
  "runRefresh",
  "serverName",
  "toolNames",
] as const;

const SAFE_SLUG_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/;

const BDD_RUNNER_MARKERS = [
  "cucumber.js",
  "cucumber.yml",
  "cucumber.yaml",
  ".cucumber.js",
  "behave.ini",
  "pytest.ini",
  "pyproject.toml",
] as const;

function isBddIntent(value: string): value is BddIntent {
  return (BDD_INTENTS as readonly string[]).includes(value);
}

function featureBody(input: BddInput): string {
  if (typeof input.content === "string") return input.content;
  if (typeof input.body === "string") return input.body;
  return "";
}

/** Resolve cwd under host; never from model args. */
function resolveCwd(host: BddHostOptions): string {
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

function isFile(path: string): boolean {
  try {
    return existsSync(path) && statSync(path).isFile();
  } catch {
    return false;
  }
}

/** Lexical containment after resolve (no symlink follow). */
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
 * True when `child` is under `parent` using real paths when available (Q1C / R5).
 * For not-yet-written targets, realpath the nearest existing ancestor.
 */
function isInsideRoot(parent: string, child: string): boolean {
  const parentReal = tryRealpath(parent) ?? resolve(parent);
  const childResolved = resolve(child);
  if (existsSync(childResolved)) {
    const childReal = tryRealpath(childResolved);
    if (childReal == null) return false;
    return isInsideRootLexical(parentReal, childReal);
  }
  // Walk up to an existing ancestor (may be a symlink dir) and realpath it.
  let cursor = childResolved;
  while (!existsSync(cursor)) {
    const parentDir = dirname(cursor);
    if (parentDir === cursor) break;
    cursor = parentDir;
  }
  if (!existsSync(cursor)) {
    // Nothing exists along the path — fall back to lexical under parentReal.
    return isInsideRootLexical(parentReal, childResolved);
  }
  const ancestorReal = tryRealpath(cursor);
  if (ancestorReal == null) return false;
  if (!isInsideRootLexical(parentReal, ancestorReal)) return false;
  // Re-join remaining segments onto the real ancestor and check again.
  const suffix = relative(cursor, childResolved);
  const projected =
    suffix === "" ? ancestorReal : resolve(ancestorReal, suffix);
  return isInsideRootLexical(parentReal, projected);
}

function isDirSymlink(path: string): boolean {
  try {
    return lstatSync(path).isSymbolicLink();
  } catch {
    return false;
  }
}

function hasBddRunnerConfig(root: string): boolean {
  for (const marker of BDD_RUNNER_MARKERS) {
    if (existsSync(join(root, marker))) {
      if (marker === "pyproject.toml" || marker === "pytest.ini") {
        try {
          const text = readFileSync(join(root, marker), "utf8");
          if (/bdd|cucumber|behave|pytest-bdd/i.test(text)) return true;
          // pytest.ini without bdd markers is weak evidence — skip
          if (marker === "pytest.ini") continue;
        } catch {}
      } else {
        return true;
      }
    }
  }
  try {
    const pkgPath = join(root, "package.json");
    if (!existsSync(pkgPath)) return false;
    const pkg = JSON.parse(readFileSync(pkgPath, "utf8")) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
      scripts?: Record<string, string>;
    };
    const deps = {
      ...(pkg.dependencies ?? {}),
      ...(pkg.devDependencies ?? {}),
    };
    if (
      deps["@cucumber/cucumber"] != null ||
      deps.cucumber != null ||
      deps["jest-cucumber"] != null
    ) {
      return true;
    }
    const scripts = pkg.scripts ?? {};
    return Object.values(scripts).some((s) => /cucumber/i.test(s));
  } catch {
    return false;
  }
}

const FEATURE_WALK_SKIP = new Set([
  "node_modules",
  ".git",
  "dist",
  "build",
  "coverage",
  ".trellis",
  ".gitnexus",
]);

function findFeatureFiles(root: string, max = 500): string[] {
  const out: string[] = [];
  const stack = [root];
  while (stack.length > 0 && out.length < max) {
    const dir = stack.pop();
    if (dir == null) break;
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      continue;
    }
    for (const name of entries) {
      if (FEATURE_WALK_SKIP.has(name)) continue;
      const full = join(dir, name);
      // Q1C/R5: do not follow directory symlinks out of host roots.
      if (isDirSymlink(full)) continue;
      let st: ReturnType<typeof statSync>;
      try {
        st = statSync(full);
      } catch {
        continue;
      }
      if (st.isDirectory()) {
        stack.push(full);
      } else if (st.isFile() && name.endsWith(".feature")) {
        out.push(full);
      }
    }
  }
  return out.sort();
}

/**
 * Distinct parent directories of `.feature` files under `root` (Q2B / R4).
 * Unlike findFeatureFiles, does **not** stop after N files in one tree — that
 * would hide a second tree and silently pick the sampled root. Early-exits
 * only once `stopAtDistinct` different parents are known (enough for ambiguous).
 */
export function findDistinctFeatureParentDirs(
  root: string,
  stopAtDistinct = 2,
): string[] {
  const parents = new Set<string>();
  const stack = [root];
  while (stack.length > 0) {
    if (parents.size >= stopAtDistinct) break;
    const dir = stack.pop();
    if (dir == null) break;
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      continue;
    }
    for (const name of entries) {
      if (FEATURE_WALK_SKIP.has(name)) continue;
      const full = join(dir, name);
      // Q1C/R5: do not follow directory symlinks out of host roots.
      if (isDirSymlink(full)) continue;
      let st: ReturnType<typeof statSync>;
      try {
        st = statSync(full);
      } catch {
        continue;
      }
      if (st.isDirectory()) {
        stack.push(full);
      } else if (st.isFile() && name.endsWith(".feature")) {
        parents.add(dirname(full));
        if (parents.size >= stopAtDistinct) {
          return [...parents].sort();
        }
      }
    }
  }
  return [...parents].sort();
}

export type ConventionKind =
  | "existing-features-dir"
  | "existing-feature-files"
  | "bdd-runner"
  | "agents-default"
  | "ambiguous-feature-trees";

/**
 * Q2B: prefer existing features/ / .feature / BDD runner; AGENTS default only if none.
 */
export function detectFeatureConvention(
  cwd: string,
  featureRootOverride?: string,
): {
  kind: ConventionKind;
  featureRoot: string;
  /** Distinct feature parent dirs when kind is ambiguous-feature-trees (Q2B). */
  ambiguousRoots?: string[];
} {
  if (
    typeof featureRootOverride === "string" &&
    featureRootOverride.length > 0
  ) {
    const root = resolve(cwd, featureRootOverride);
    return {
      kind: isDir(root) ? "existing-features-dir" : "agents-default",
      featureRoot: root,
    };
  }
  const featuresDir = join(cwd, "features");
  // Q1C/R5: do not adopt a symlink features/ as convention root (stat follows).
  if (isDir(featuresDir) && !isDirSymlink(featuresDir)) {
    return { kind: "existing-features-dir", featureRoot: featuresDir };
  }
  // Q2B/R4: discover distinct feature parents independently of any file-count
  // cap (a large first tree must not hide a second tree / plugin fixtures).
  const dirs = findDistinctFeatureParentDirs(cwd, 2);
  if (dirs.length > 0) {
    if (dirs.length === 1) {
      const only = dirs[0];
      if (only == null) {
        return { kind: "agents-default", featureRoot: featuresDir };
      }
      return {
        kind: "existing-feature-files",
        featureRoot: only,
      };
    }
    // Q2B: never silently pick found[0] across multiple trees (e.g. plugin fixtures).
    return {
      kind: "ambiguous-feature-trees",
      featureRoot: featuresDir,
      ambiguousRoots: dirs,
    };
  }
  if (hasBddRunnerConfig(cwd)) {
    return { kind: "bdd-runner", featureRoot: featuresDir };
  }
  return { kind: "agents-default", featureRoot: featuresDir };
}

function isSlug(target: string): boolean {
  return (
    SAFE_SLUG_RE.test(target) &&
    !target.includes("/") &&
    !target.endsWith(".feature")
  );
}

function isRelativeFeaturePath(target: string): boolean {
  if (target.length === 0) return false;
  if (isAbsolute(target)) return false;
  const n = normalize(target);
  if (n.startsWith("..") || n.includes(`${sep}..`)) return false;
  // Q1C side-effect: relative write targets must be .feature paths (no src/*.ts overwrite).
  if (!target.endsWith(".feature")) return false;
  return true;
}

/**
 * Resolve write/sync target path under host cwd (Q1C + Q2B).
 * Absolute / escaping paths are rejected.
 */
export function resolveFeatureTargetPath(
  cwd: string,
  target: string,
  convention: {
    kind: ConventionKind;
    featureRoot: string;
    ambiguousRoots?: string[];
  },
  /**
   * When true, `convention.featureRoot` came from an explicit host override and
   * may intentionally sit outside cwd (still must contain the target).
   * Convention-derived roots must stay under host cwd (Q1C/R5).
   */
  hostFeatureRootOverride = false,
): { ok: true; path: string } | { ok: false; reason: string } {
  const trimmed = target.trim();
  if (!trimmed) {
    return { ok: false, reason: "empty-target" };
  }
  if (isAbsolute(trimmed)) {
    return { ok: false, reason: "absolute-target-forbidden" };
  }
  if (isRelativeFeaturePath(trimmed)) {
    const abs = resolve(cwd, trimmed);
    if (!isInsideRoot(cwd, abs)) {
      return { ok: false, reason: "target-escapes-cwd" };
    }
    return { ok: true, path: abs };
  }
  if (isSlug(trimmed)) {
    if (convention.kind === "ambiguous-feature-trees") {
      return {
        ok: false,
        reason:
          "ambiguous-feature-root: multiple .feature trees under cwd; provide a cwd-relative .feature path or host featureRoot",
      };
    }
    const abs = join(convention.featureRoot, `${trimmed}.feature`);
    if (isInsideRoot(cwd, abs)) {
      return { ok: true, path: abs };
    }
    // Outside cwd: only an explicit host featureRoot override may authorize.
    if (hostFeatureRootOverride && isInsideRoot(convention.featureRoot, abs)) {
      return { ok: true, path: abs };
    }
    return {
      ok: false,
      reason: hostFeatureRootOverride
        ? "target-escapes-feature-root"
        : "target-escapes-cwd",
    };
  }
  return { ok: false, reason: "invalid-target" };
}

/** Q1C/R5: reject final-component symlinks before write (dangling or retarget). */
function rejectSymlinkFeatureTarget(
  absPath: string,
): { ok: true } | { ok: false; reason: string } {
  try {
    if (lstatSync(absPath).isSymbolicLink()) {
      return {
        ok: false,
        reason:
          "target-is-symlink: refusing to follow/overwrite a .feature symlink (Q1C)",
      };
    }
  } catch {
    // ENOENT — final component absent; safe to create a new regular file.
  }
  return { ok: true };
}

/**
 * Host-validate user-supplied extra paths before any scan (Q1C).
 * Returns validated absolute roots; rejects inventing / escaping.
 */
export function validateExtraPaths(
  cwd: string,
  extraPaths: string[] | undefined,
  host: BddHostOptions,
): {
  validated: string[];
  rejected: Array<{ path: string; reason: string }>;
} {
  const validated: string[] = [];
  const rejected: Array<{ path: string; reason: string }> = [];
  if (extraPaths == null || extraPaths.length === 0) {
    return { validated, rejected };
  }
  const allow = (host.allowedExtraRoots ?? [])
    .map((r) => tryRealpath(r) ?? resolve(r))
    .filter((r) => r.length > 0);

  for (const raw of extraPaths) {
    if (typeof raw !== "string" || raw.trim().length === 0) {
      rejected.push({ path: String(raw), reason: "empty-path" });
      continue;
    }
    const trimmed = raw.trim();
    // Extra roots are user-supplied local paths — may be absolute (sibling repos)
    // or cwd-relative. Host must authorize via allowedExtraRoots before scan (Q1C).
    const abs = isAbsolute(trimmed) ? resolve(trimmed) : resolve(cwd, trimmed);
    if (allow.length === 0) {
      // Default-deny: existence alone is not host provenance.
      rejected.push({ path: trimmed, reason: "no-host-allowlist" });
      continue;
    }
    if (!isDir(abs)) {
      rejected.push({ path: trimmed, reason: "not-a-directory" });
      continue;
    }
    const absReal = tryRealpath(abs) ?? abs;
    const ok = allow.some(
      (root) => isInsideRootLexical(root, absReal) || root === absReal,
    );
    if (!ok) {
      rejected.push({ path: trimmed, reason: "not-host-allowed" });
      continue;
    }
    validated.push(absReal);
  }
  return { validated, rejected };
}

function parseFeatureMeta(text: string): {
  featureTitle: string | null;
  scenarioCount: number;
  tags: string[];
} {
  let featureTitle: string | null = null;
  let scenarioCount = 0;
  const tags = new Set<string>();
  const lines = text.split(/\r?\n/);
  let pendingTags: string[] = [];
  for (const line of lines) {
    const tagMatch = line.match(/^\s*(@\S+(?:\s+@\S+)*)\s*$/);
    if (tagMatch) {
      pendingTags = (tagMatch[1] ?? "")
        .split(/\s+/)
        .filter((t) => t.startsWith("@"));
      for (const t of pendingTags) tags.add(t);
      continue;
    }
    // English + common Chinese Gherkin keywords (S1; Q2B language reuse).
    const feat = line.match(/^\s*(?:Feature|功能):\s*(.*)\s*$/);
    if (feat) {
      featureTitle = (feat[1] ?? "").trim() || null;
      pendingTags = [];
      continue;
    }
    if (/^\s*(?:Scenario(?: Outline)?|场景(?:大纲)?):\s*/.test(line)) {
      scenarioCount += 1;
      pendingTags = [];
    }
  }
  return { featureTitle, scenarioCount, tags: [...tags].sort() };
}

export function catalogFeatures(roots: string[]): FeatureCatalogEntry[] {
  const entries: FeatureCatalogEntry[] = [];
  const seen = new Set<string>();
  for (const root of roots) {
    const files = findFeatureFiles(root);
    for (const file of files) {
      const key = resolve(file);
      if (seen.has(key)) continue;
      seen.add(key);
      let text = "";
      try {
        text = readFileSync(file, "utf8");
      } catch {
        continue;
      }
      const meta = parseFeatureMeta(text);
      entries.push({
        path: relative(root, file) || file,
        root,
        featureTitle: meta.featureTitle,
        scenarioCount: meta.scenarioCount,
        tags: meta.tags,
      });
    }
  }
  return entries;
}

function defaultLoginFeature(): string {
  return [
    "Feature: 用户登录",
    "  用户需要使用账号进入工作区，以便继续管理自己的配置。",
    "",
    "  Scenario: 已注册用户使用正确密码登录",
    "    Given 用户已经注册账号",
    "    When 用户提交正确的邮箱和密码",
    "    Then 用户进入自己的工作区",
    "    And 页面显示当前登录状态",
    "",
  ].join("\n");
}

function blockedResult(
  intent: BddIntent,
  kind: string,
  reason: string,
  mutation: BddToolResult["mutation"] = "none",
): BddToolResult {
  return {
    ok: false,
    intent,
    status: "blocked",
    mutation,
    blocked: { kind, reason },
    note: reason,
  };
}

/** Pick only model-visible keys (Q1C); drop trust-handle extras if present. */
export function pickBddInput(args: unknown): BddInput {
  const src =
    args != null && typeof args === "object"
      ? (args as Record<string, unknown>)
      : {};
  const out: BddInput = {
    intent: typeof src.intent === "string" ? src.intent : "",
  };
  if (typeof src.target === "string") out.target = src.target;
  if (typeof src.content === "string") out.content = src.content;
  if (typeof src.body === "string") out.body = src.body;
  if (Array.isArray(src.extra_paths)) {
    out.extra_paths = src.extra_paths.filter(
      (p): p is string => typeof p === "string",
    );
  }
  if (typeof src.cross_repo_required === "boolean") {
    out.cross_repo_required = src.cross_repo_required;
  }
  return out;
}

/** Schema helper for tests — model must not see trust-handle keys (Q1C). */
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
 * Resolve host-owned cwd / featureRoot for production registration (Q1C).
 */
export function resolveBddHost(ctx: BddPluginHost): BddHostOptions {
  const explicit = ctx.bddHost ?? {};
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

export function sbtdBdd(
  _sessionId: string,
  input: BddInput,
  host: BddHostOptions = {},
): BddToolResult {
  if (!isBddIntent(input.intent)) {
    return blockedResult(
      "read",
      "invalid-intent",
      `intent must be one of ${BDD_INTENTS.join(", ")}`,
    );
  }
  const intent = input.intent;
  const cwd = resolveCwd(host);
  const convention = detectFeatureConvention(cwd, host.featureRoot);

  // Extra paths only for sync/read (Q1C).
  if (
    intent === "write" &&
    input.extra_paths != null &&
    input.extra_paths.length > 0
  ) {
    return blockedResult(
      intent,
      "extra-paths-not-allowed",
      "extra_paths are only allowed for intent=sync|read",
      "none",
    );
  }

  const extras = validateExtraPaths(
    cwd,
    intent === "write" ? undefined : input.extra_paths,
    host,
  );

  if (extras.rejected.length > 0) {
    return {
      ...blockedResult(
        intent,
        "extra-path-invalid",
        extras.rejected.map((r) => `${r.path}: ${r.reason}`).join("; "),
        "none",
      ),
      note: `Host rejected extra_paths before scan: ${extras.rejected
        .map((r) => `${r.path} (${r.reason})`)
        .join("; ")}`,
    };
  }

  if (
    (intent === "sync" || intent === "read") &&
    input.cross_repo_required === true &&
    extras.validated.length === 0
  ) {
    return blockedResult(
      intent,
      "cross-repo-missing",
      "cross_repo_required=true but no validated extra_paths; will not invent cross-repo SoT",
      "none",
    );
  }

  const scanRoots = [cwd, ...extras.validated];

  if (intent === "read") {
    const catalog = catalogFeatures(scanRoots);
    return {
      ok: true,
      intent: "read",
      status: "done",
      mutation: "none",
      convention: convention.kind,
      catalog,
      note: `Local catalog of ${catalog.length} .feature file(s) under ${scanRoots.length} root(s). Mutation: none.`,
    };
  }

  if (intent === "sync") {
    // R2 / gherkin-bdd Sync Mode: a truthful sync audits working tree + features/
    // + code/docs/tests and reports update/create/delete/unchanged. T11 tool cannot
    // perform that whole-tree behavior audit without inventing SoT — do not claim
    // success for .feature inventory (or optional target write) alone.
    const catalog = catalogFeatures(scanRoots);
    const reason =
      "BDD Sync Mode not yet capable in sbtd_bdd: full working-tree + features/ + " +
      "code/docs/tests behavior audit is required (gherkin-bdd AGENTS Sync Mode). " +
      "Inventory-only is not a successful sync. Use intent=read for catalog; " +
      "intent=write to persist a .feature. Sync remains blocked until capable.";
    return {
      ok: false,
      intent: "sync",
      status: "blocked",
      mutation: "none",
      convention: convention.kind,
      blocked: { kind: "sync-not-capable", reason },
      sync: {
        mode: "blocked",
        rootsScanned: scanRoots,
        features: catalog,
        updated: [],
        created: [],
        unchanged: [],
        note: reason,
      },
      note: reason,
    };
  }

  // intent === write
  const target = typeof input.target === "string" ? input.target.trim() : "";
  if (!target) {
    return blockedResult(
      intent,
      "missing-target",
      "write requires target (capability slug or cwd-relative feature path)",
      "none",
    );
  }
  const hostOverride =
    typeof host.featureRoot === "string" && host.featureRoot.length > 0;
  const resolved = resolveFeatureTargetPath(
    cwd,
    target,
    convention,
    hostOverride,
  );
  if (!resolved.ok) {
    return blockedResult(intent, "invalid-target", resolved.reason, "none");
  }
  const symlinkGate = rejectSymlinkFeatureTarget(resolved.path);
  if (!symlinkGate.ok) {
    return blockedResult(intent, "invalid-target", symlinkGate.reason, "none");
  }

  let body = featureBody(input);
  if (body.length === 0) {
    // Acceptance: 「新增登录」能给出/写入 feature — default Chinese+English template for empty body on login-like slug.
    if (isSlug(target) && /login|登录/i.test(target)) {
      body = defaultLoginFeature();
    } else if (isRelativeFeaturePath(target) && /login/i.test(target)) {
      body = defaultLoginFeature();
    } else {
      return blockedResult(
        intent,
        "missing-content",
        "write requires content/body (Gherkin text), or target login for default template",
        "none",
      );
    }
  }

  mkdirSync(dirname(resolved.path), { recursive: true });
  writeFileSync(resolved.path, body, "utf8");

  return {
    ok: true,
    intent: "write",
    status: "done",
    mutation: "write",
    path: resolved.path,
    convention: convention.kind,
    content: body,
    note: `Wrote ${relative(cwd, resolved.path)} (convention=${convention.kind})`,
  };
}

export const SBTD_BDD_DESCRIPTION =
  "Write, sync, or locally catalog persistent Gherkin .feature files (Behavior SoT). " +
  "intent=write creates/updates a .feature; intent=sync is gherkin-bdd Sync Mode " +
  "(full code/docs/tests audit) and is blocked until that capability exists — " +
  "do not treat .feature inventory as a successful sync; " +
  "intent=read parses a rebuildable local catalog with Mutation: none. " +
  "Model args: intent + target (capability slug or cwd-relative .feature path) + optional content/body; " +
  "extra_paths and cross_repo_required only for sync/read (extras require host allowedExtraRoots). " +
  "cwd / feature-root are host-injected — do not pass cwd, mcp, runRefresh, serverName, or toolNames. " +
  "Project feature conventions win; AGENTS features/<slug>.feature only when none exist. " +
  "Missing required cross-repo paths ⇒ blocked (no invented SoT). " +
  "Does not override Trellis prd/implement; does not change sbtd_validate.";

export function createBddTool(host: BddHostOptions = {}): BddToolDefinition {
  return {
    name: SBTD_BDD_TOOL_NAME,
    description: SBTD_BDD_DESCRIPTION,
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        intent: {
          type: "string",
          enum: [...BDD_INTENTS],
          description:
            "write = create/update .feature; sync = gherkin-bdd Sync Mode (blocked until capable); read = local catalog, Mutation none.",
        },
        target: {
          type: "string",
          description:
            "Capability slug (e.g. login) or cwd-relative feature path (e.g. features/login.feature). Required for write.",
        },
        content: {
          type: "string",
          description: "Gherkin .feature body for write (or sync update).",
        },
        body: {
          type: "string",
          description: "Alias for content.",
        },
        extra_paths: {
          type: "array",
          items: { type: "string" },
          description:
            "Optional user-supplied extra repo roots for sync/read only. Host-validated; never invented.",
        },
        cross_repo_required: {
          type: "boolean",
          description:
            "When true, sync/read block if no validated extra_paths (no invented cross-repo SoT).",
        },
      },
      required: ["intent"],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          ok: { type: "boolean" },
          intent: { type: "string" },
          status: { type: "string" },
          mutation: { type: "string" },
          path: { type: "string" },
          convention: { type: "string" },
          catalog: { type: "array" },
          sync: { type: "object" },
          blocked: { type: "object" },
          note: { type: "string" },
          content: { type: "string" },
        },
      },
      render(_args, value) {
        const lines = [
          `intent: ${value.intent}`,
          `status: ${value.status}`,
          `mutation: ${value.mutation}`,
        ];
        if (value.convention !== undefined) {
          lines.push(`convention: ${value.convention}`);
        }
        if (value.path !== undefined) {
          lines.push(`path: ${value.path}`);
        }
        if (value.blocked !== undefined) {
          lines.push(
            `blocked.kind: ${value.blocked.kind}`,
            `blocked.reason: ${value.blocked.reason}`,
          );
        }
        if (value.catalog !== undefined) {
          lines.push(`catalog.count: ${value.catalog.length}`);
          for (const e of value.catalog.slice(0, 30)) {
            lines.push(
              `- ${e.path} (${e.scenarioCount} scenarios)${e.featureTitle != null ? `: ${e.featureTitle}` : ""}`,
            );
          }
        }
        if (value.sync !== undefined) {
          lines.push(
            `sync.mode: ${value.sync.mode}`,
            `sync.roots: ${value.sync.rootsScanned.join(", ")}`,
            `sync.updated: ${value.sync.updated.length}`,
            `sync.created: ${value.sync.created.length}`,
            `sync.unchanged: ${value.sync.unchanged.length}`,
          );
          lines.push(value.sync.note);
        }
        if (value.note !== undefined) {
          lines.push("", value.note);
        }
        if (value.content !== undefined && value.intent === "write") {
          lines.push("", "--- feature ---", value.content);
        }
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe(args) {
      const intent =
        args != null &&
        typeof args === "object" &&
        typeof (args as { intent?: unknown }).intent === "string"
          ? (args as { intent: string }).intent
          : "";
      return intent === "read";
    },
    async execute(args, exec) {
      const modelArgs = pickBddInput(args);
      return sbtdBdd(sessionIdFromExec(exec), modelArgs, host);
    },
  };
}

export function registerBddTool(
  ctx: ToolsHost,
  host: BddHostOptions = {},
): void {
  ctx.tools.register(createBddTool(host));
}
