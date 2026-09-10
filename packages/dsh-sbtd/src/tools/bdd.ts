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
  mkdirSync,
  readdirSync,
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
   * Optional allowlist of absolute roots under which extra_paths may resolve.
   * When set, extras outside the allowlist are rejected (not scanned).
   * When unset, extras must exist as directories and are accepted as user-supplied.
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
    | "agents-default";
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

/** True when `child` is `parent` or a path under it (after resolve). */
function isInsideRoot(parent: string, child: string): boolean {
  const p = resolve(parent);
  const c = resolve(child);
  if (p === c) return true;
  const rel = relative(p, c);
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
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

function findFeatureFiles(root: string, max = 500): string[] {
  const out: string[] = [];
  const stack = [root];
  const skip = new Set([
    "node_modules",
    ".git",
    "dist",
    "build",
    "coverage",
    ".trellis",
    ".gitnexus",
  ]);
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
      if (skip.has(name)) continue;
      const full = join(dir, name);
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

export type ConventionKind =
  | "existing-features-dir"
  | "existing-feature-files"
  | "bdd-runner"
  | "agents-default";

/**
 * Q2B: prefer existing features/ / .feature / BDD runner; AGENTS default only if none.
 */
export function detectFeatureConvention(
  cwd: string,
  featureRootOverride?: string,
): { kind: ConventionKind; featureRoot: string } {
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
  if (isDir(featuresDir)) {
    return { kind: "existing-features-dir", featureRoot: featuresDir };
  }
  const found = findFeatureFiles(cwd, 20);
  if (found.length > 0) {
    const first = found[0];
    if (first == null) {
      return { kind: "agents-default", featureRoot: featuresDir };
    }
    return {
      kind: "existing-feature-files",
      featureRoot: dirname(first),
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
  return target.includes("/") || target.endsWith(".feature");
}

/**
 * Resolve write/sync target path under host cwd (Q1C + Q2B).
 * Absolute / escaping paths are rejected.
 */
export function resolveFeatureTargetPath(
  cwd: string,
  target: string,
  convention: { kind: ConventionKind; featureRoot: string },
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
    const abs = join(convention.featureRoot, `${trimmed}.feature`);
    if (!isInsideRoot(cwd, abs) && !isInsideRoot(convention.featureRoot, abs)) {
      // featureRoot should be under cwd; if host override is outside, still require under featureRoot
      if (!isInsideRoot(convention.featureRoot, abs)) {
        return { ok: false, reason: "target-escapes-feature-root" };
      }
    }
    return { ok: true, path: abs };
  }
  return { ok: false, reason: "invalid-target" };
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
  const allow =
    host.allowedExtraRoots
      ?.map((r) => resolve(r))
      .filter((r) => r.length > 0) ?? null;

  for (const raw of extraPaths) {
    if (typeof raw !== "string" || raw.trim().length === 0) {
      rejected.push({ path: String(raw), reason: "empty-path" });
      continue;
    }
    const trimmed = raw.trim();
    // Extra roots are user-supplied local paths — may be absolute (sibling repos)
    // or cwd-relative. Host must still validate before scan.
    const abs = isAbsolute(trimmed) ? resolve(trimmed) : resolve(cwd, trimmed);
    if (!isDir(abs)) {
      rejected.push({ path: trimmed, reason: "not-a-directory" });
      continue;
    }
    if (allow != null && allow.length > 0) {
      const ok = allow.some((root) => isInsideRoot(root, abs) || root === abs);
      if (!ok) {
        rejected.push({ path: trimmed, reason: "not-host-allowed" });
        continue;
      }
    }
    // Never treat primary cwd as an "extra" silently inventing scope — allow if user named it.
    validated.push(abs);
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
    const feat = line.match(/^\s*Feature:\s*(.*)\s*$/);
    if (feat) {
      featureTitle = (feat[1] ?? "").trim() || null;
      pendingTags = [];
      continue;
    }
    if (/^\s*Scenario(?: Outline)?:\s*/.test(line)) {
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
    const catalog = catalogFeatures(scanRoots);
    // Sync Mode report (gherkin-bdd Sync Mode, tool-local): inventory + optional write of target.
    // Do not invent new SoT from code without model-supplied content.
    const updated: string[] = [];
    const created: string[] = [];
    const unchanged: string[] = [];
    const body = featureBody(input);
    let writtenPath: string | undefined;

    if (typeof input.target === "string" && input.target.trim().length > 0) {
      const resolved = resolveFeatureTargetPath(cwd, input.target, convention);
      if (!resolved.ok) {
        return blockedResult(intent, "invalid-target", resolved.reason, "none");
      }
      if (body.length > 0) {
        const existed = isFile(resolved.path);
        mkdirSync(dirname(resolved.path), { recursive: true });
        writeFileSync(resolved.path, body, "utf8");
        writtenPath = resolved.path;
        if (existed) updated.push(relative(cwd, resolved.path));
        else created.push(relative(cwd, resolved.path));
      } else if (isFile(resolved.path)) {
        unchanged.push(relative(cwd, resolved.path));
      }
    } else {
      for (const entry of catalog) {
        unchanged.push(
          entry.root === cwd ? entry.path : join(entry.root, entry.path),
        );
      }
    }

    return {
      ok: true,
      intent: "sync",
      status: "done",
      mutation: updated.length > 0 || created.length > 0 ? "sync" : "none",
      convention: convention.kind,
      ...(writtenPath != null ? { path: writtenPath } : {}),
      sync: {
        mode: "run",
        rootsScanned: scanRoots,
        features: catalogFeatures(scanRoots),
        updated,
        created,
        unchanged,
        note:
          "BDD Sync Mode: local inventory under host roots (+ validated extras). " +
          "Full code↔feature behavior audit is model-led; tool does not invent SoT. " +
          "Provide target+content to update/create a .feature during sync.",
      },
      note: "BDD Sync Mode: run",
      ...(body.length > 0 ? { content: body } : {}),
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
  const resolved = resolveFeatureTargetPath(cwd, target, convention);
  if (!resolved.ok) {
    return blockedResult(intent, "invalid-target", resolved.reason, "none");
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
  "intent=write creates/updates a .feature; intent=sync audits inventory under host roots " +
  "(+ user-supplied extra_paths) and may update a target when content is provided; " +
  "intent=read parses a rebuildable local catalog with Mutation: none. " +
  "Model args: intent + target (capability slug or cwd-relative path) + optional content/body; " +
  "extra_paths and cross_repo_required only for sync/read. " +
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
            "write = create/update .feature; sync = inventory/audit (+ optional target update); read = local catalog, Mutation none.",
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
