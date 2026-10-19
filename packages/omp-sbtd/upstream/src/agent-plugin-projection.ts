import { execFile } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  cp,
  lstat,
  mkdir,
  readdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { promisify } from "node:util";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import { KitError } from "./index.js";

const CHECK_NAMES = [
  "portable",
  "frontmatter",
  "containment",
  "license",
  "reference-script",
  "runtime-dependency",
] as const;

export type AgentPluginAuditCheckName = (typeof CHECK_NAMES)[number];
export type AgentPluginAuditStatus = "pass" | "fail" | "blocked";
export type AgentPluginDisposition = "certified" | "onboard-owned" | "blocked";

export interface AgentPluginAuditCheck {
  readonly status: AgentPluginAuditStatus;
  readonly reasons: readonly string[];
}

export interface AgentPluginAuditResult {
  readonly name: string;
  readonly sourceSha256: string | null;
  readonly checks: Readonly<
    Record<AgentPluginAuditCheckName, AgentPluginAuditCheck>
  >;
  readonly runtimeDependencies: readonly string[];
  readonly disposition: AgentPluginDisposition;
}

export interface AgentPluginAuditReport {
  readonly schemaVersion: 1;
  readonly candidateCount: number;
  readonly certifiedCount: number;
  readonly results: readonly AgentPluginAuditResult[];
}

interface CandidateDefinition {
  readonly name: string;
  readonly category: string;
  readonly allowedTools: string;
  readonly compatibility: string;
  readonly runtimeDependencies: readonly string[];
}

const CANDIDATES = [
  {
    name: "trellis-workflow",
    category: "workflow",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires Trellis CLI and a repository with .trellis workflow assets.",
    runtimeDependencies: ["Trellis CLI", ".trellis workflow assets"],
  },
  {
    name: "project-validation",
    category: "validation",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires the target repository's native validation tools. Python 3.10+ and jsonschema are required for validation-evidence schema checks; rtk is optional.",
    runtimeDependencies: [
      "project-native validation tools",
      "conditional Python 3.10+",
      "conditional jsonschema",
      "optional rtk",
    ],
  },
  {
    name: "web-ui-autotest-generator",
    category: "testing",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires Playwright, Node.js or TypeScript project tooling, and Python 3.10+ for bundled scripts.",
    runtimeDependencies: [
      "Playwright",
      "Node.js",
      "TypeScript project tooling",
      "Python 3.10+",
    ],
  },
  {
    name: "gherkin-bdd",
    category: "behavior",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires repository BDD conventions or a project test runner; Knowledge Ingest and Maestro are optional.",
    runtimeDependencies: [
      "project BDD or test runner",
      "optional Knowledge Ingest",
      "optional Maestro",
    ],
  },
  {
    name: "knowledge-base-integration",
    category: "knowledge",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires Python 3.10+, PyYAML, jsonschema, and configured repositories or runner adapters.",
    runtimeDependencies: [
      "Python 3.10+",
      "PyYAML",
      "jsonschema",
      "configured repositories or runner adapters",
    ],
  },
  {
    name: "maestro-mobile-e2e",
    category: "testing",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires Java 17+, Maestro CLI, a device, an app artifact, and the scenario environment including account and backend prerequisites.",
    runtimeDependencies: [
      "Java 17+",
      "Maestro CLI",
      "device",
      "app artifact",
      "scenario environment",
    ],
  },
  {
    name: "lessons-record",
    category: "workflow",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires Trellis lesson assets or a repository-documented non-Trellis lessons layout.",
    runtimeDependencies: ["Trellis or repository lessons layout"],
  },
  {
    name: "book-refactoring-pass",
    category: "refactoring",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires project tests; Trellis artifacts and GitNexus are optional context sources.",
    runtimeDependencies: [
      "project tests",
      "optional Trellis",
      "optional GitNexus",
    ],
  },
  {
    name: "book-legacy-change-safety",
    category: "safety",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires project characterization or safety-net tooling; Trellis and GitNexus are optional.",
    runtimeDependencies: [
      "project safety-net tooling",
      "optional Trellis",
      "optional GitNexus",
    ],
  },
  {
    name: "book-ddd-distilled-modeling",
    category: "domain",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires project evidence; Trellis task artifacts and clarification workflows are optional.",
    runtimeDependencies: [
      "project evidence",
      "optional Trellis",
      "optional clarification workflow",
    ],
  },
  {
    name: "book-ddia-data-design",
    category: "data",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires project architecture and data-flow evidence; migration tools, Trellis, GitNexus, and tests are optional.",
    runtimeDependencies: [
      "project architecture and data evidence",
      "optional migration tooling",
      "optional Trellis",
      "optional GitNexus",
    ],
  },
  {
    name: "book-release-readiness",
    category: "release",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires project validation and release evidence; browser, mobile, Trellis, and operational tools are optional.",
    runtimeDependencies: [
      "project validation",
      "release evidence",
      "optional browser or mobile tooling",
      "optional Trellis",
    ],
  },
  {
    name: "seo-geo",
    category: "seo",
    allowedTools: "read grep glob bash",
    compatibility:
      "Requires Python 3.10+ and network access; DataForSEO credentials and API access are optional.",
    runtimeDependencies: [
      "Python 3.10+",
      "network access",
      "optional DataForSEO credentials and API",
    ],
  },
] as const satisfies readonly CandidateDefinition[];

const SOURCE_FRONTMATTER_FIELDS = new Set([
  "name",
  "description",
  "license",
  "allowed-tools",
  "metadata",
  "compatibility",
]);
const SCRIPT_EXTENSIONS = new Set([".py", ".sh", ".ts", ".js", ".mjs", ".cjs"]);
const execFileAsync = promisify(execFile);
const PYTHON_IMPORT_AUDIT = `
import ast
import json
import pathlib
import sys

if sys.version_info < (3, 10):
    print(json.dumps({
        "error": "Python 3.10+ is required to audit bundled Python scripts",
        "dependencies": [],
        "syntaxErrors": [],
    }))
    raise SystemExit(0)

paths = [pathlib.Path(value) for value in sys.argv[1:]]
local_modules = {path.stem for path in paths}
stdlib = set(getattr(sys, "stdlib_module_names", ()))
dependencies = set()
syntax_errors = []

for path in paths:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        syntax_errors.append({
            "path": str(path),
            "line": error.lineno,
            "message": error.msg,
        })
        continue
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            root = name.split(".", 1)[0]
            if (
                root != "__future__"
                and root not in stdlib
                and root not in local_modules
            ):
                dependencies.add("PyYAML" if root == "yaml" else root)

print(json.dumps({
    "dependencies": sorted(dependencies),
    "syntaxErrors": syntax_errors,
}))
`;
const SEMANTIC_BLOCKERS = [
  {
    pattern: /(?:^|[^\w])\.omp(?:\/|\/\*\*)/m,
    reason: "references the OMP-private .omp path",
  },
  {
    pattern: /(?:^|[^\w])\.codex(?:\/|\/\*\*)/m,
    reason: "contains host-specific .codex dispatch instructions",
  },
  { pattern: /\bOMP task worker\b/i, reason: "depends on an OMP task worker" },
] as const;

interface ParsedFrontmatter {
  readonly attributes: Readonly<Record<string, unknown>>;
  readonly body: string;
}

interface CanonicalIdentity {
  readonly sourceId: string;
  readonly canonicalSourceUri: string;
  readonly resolvedRevision: string;
  readonly sourceTreeSha256: string;
}

interface CandidateInspection {
  readonly definition: CandidateDefinition;
  readonly root: string;
  readonly files: readonly string[];
  readonly frontmatter: ParsedFrontmatter;
  readonly sourceSha256: string | null;
  readonly result: AgentPluginAuditResult;
}

export interface GenerateAgentPluginProjectionOptions {
  readonly packageRoot: string;
  readonly canonicalDirectory: string;
  readonly outputDirectory: string;
}

export interface AgentPluginProjectionSkill {
  readonly sourceSha256: string;
  readonly projectionSha256: string;
  readonly files: Readonly<Record<string, string>>;
}

export interface AgentPluginProjectionCatalogEntry {
  readonly name: string;
  readonly source: string;
  readonly certification: {
    readonly disposition: AgentPluginDisposition;
    readonly checks: Readonly<
      Record<AgentPluginAuditCheckName, AgentPluginAuditCheck>
    >;
    readonly sourceSha256: string | null;
    readonly projectionSha256: string | null;
  };
}

export interface AgentPluginProjectionCatalog {
  readonly schemaVersion: 1;
  readonly candidateCount: number;
  readonly certifiedCount: number;
  readonly entries: readonly AgentPluginProjectionCatalogEntry[];
}

export interface AgentPluginProjectionManifest extends CanonicalIdentity {
  readonly schemaVersion: 1;
  readonly transformVersion: "agent-plugin-p0-v1";
  readonly auditSha256: string;
  readonly catalogSha256: string;
  readonly generatedSha256: string;
  readonly candidateCount: number;
  readonly certifiedCount: number;
  readonly certified: readonly string[];
  readonly excluded: readonly {
    readonly name: string;
    readonly reasons: readonly string[];
  }[];
  readonly assets: Readonly<Record<string, string>>;
  readonly skills: Readonly<Record<string, AgentPluginProjectionSkill>>;
}

export interface GeneratedAgentPluginProjection {
  readonly audit: AgentPluginAuditReport;
  readonly catalog: AgentPluginProjectionCatalog;
  readonly manifest: AgentPluginProjectionManifest;
}

function sha256(content: string | Buffer): string {
  return createHash("sha256").update(content).digest("hex");
}

function portablePath(path: string): string {
  return path.split(sep).join("/");
}

function isContained(root: string, target: string): boolean {
  const path = relative(root, target);
  return (
    path === "" ||
    (!path.startsWith(`..${sep}`) && path !== ".." && !isAbsolute(path))
  );
}

async function collectFiles(root: string): Promise<readonly string[]> {
  const files: string[] = [];
  async function walk(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      const local = portablePath(relative(root, path));
      if (entry.isSymbolicLink()) {
        throw new KitError(
          "PROJECTION_CANONICAL_INVALID",
          "Agent Plugin Skill source contains a symbolic link",
          { phase: "agent-plugin", path: local },
        );
      }
      if (entry.isDirectory()) {
        await walk(path);
      } else if (entry.isFile()) {
        files.push(local);
      } else {
        throw new KitError(
          "PROJECTION_CANONICAL_INVALID",
          "Agent Plugin Skill source contains an unsupported filesystem entry",
          { phase: "agent-plugin", path: local },
        );
      }
    }
  }
  await walk(root);
  return files.sort();
}

async function digestFiles(
  root: string,
  files: readonly string[],
): Promise<string> {
  const hasher = createHash("sha256");
  for (const path of [...files].sort()) {
    hasher.update(path);
    hasher.update("\0");
    hasher.update(await readFile(join(root, path)));
    hasher.update("\0");
  }
  return hasher.digest("hex");
}

async function fileDigests(
  root: string,
  files: readonly string[],
  prefix = "",
): Promise<Readonly<Record<string, string>>> {
  return Object.fromEntries(
    await Promise.all(
      [...files]
        .sort()
        .map(
          async (path) =>
            [
              prefix.length === 0 ? path : `${prefix}/${path}`,
              sha256(await readFile(join(root, path))),
            ] as const,
        ),
    ),
  );
}

function parseFrontmatter(content: string): ParsedFrontmatter {
  if (!content.startsWith("---\n")) {
    throw new Error("SKILL.md does not start with YAML frontmatter");
  }
  const closing = content.indexOf("\n---\n", 4);
  if (closing === -1) throw new Error("SKILL.md frontmatter is not closed");
  const parsed: unknown = parseYaml(content.slice(4, closing));
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("SKILL.md frontmatter must be a mapping");
  }
  return {
    attributes: parsed as Record<string, unknown>,
    body: content.slice(closing + 5),
  };
}

function check(
  status: AgentPluginAuditStatus,
  reasons: readonly string[] = [],
): AgentPluginAuditCheck {
  return { status, reasons };
}

function localMarkdownTargets(markdown: string): readonly string[] {
  const targets: string[] = [];
  for (const match of markdown.matchAll(/\]\(([^)\n]+)\)/g)) {
    let target = match[1]?.trim();
    if (target === undefined || target.length === 0) continue;
    if (target.startsWith("<") && target.endsWith(">"))
      target = target.slice(1, -1);
    else target = target.split(/\s+/, 1)[0] ?? target;
    if (
      target.startsWith("#") ||
      target.startsWith("/") ||
      /^[a-z][a-z0-9+.-]*:/i.test(target)
    )
      continue;
    const withoutFragment = target.split(/[?#]/, 1)[0];
    if (withoutFragment !== undefined && withoutFragment.length > 0) {
      targets.push(decodeURIComponent(withoutFragment));
    }
  }
  return targets;
}

interface PythonScriptAudit {
  readonly error?: string;
  readonly dependencies: readonly string[];
  readonly syntaxErrors: readonly {
    readonly path: string;
    readonly line: number | null;
    readonly message: string;
  }[];
}

interface ScriptAudit {
  readonly reasons: readonly string[];
  readonly runtimeDependencies: readonly string[];
}

const DEPENDENCY_STOPWORDS = new Set([
  "and",
  "conditional",
  "configured",
  "native",
  "optional",
  "or",
  "project",
  "project-native",
  "tooling",
  "tools",
]);

function dependencyTokens(value: string): readonly string[] {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9+.-]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0 && !DEPENDENCY_STOPWORDS.has(token));
}

function textCoversDependency(text: string, dependency: string): boolean {
  const normalized = text.toLowerCase().replace(/[^a-z0-9+.-]+/g, " ");
  const tokens = dependencyTokens(dependency);
  return (
    tokens.length > 0 && tokens.every((token) => normalized.includes(token))
  );
}

async function auditScripts(
  root: string,
  paths: readonly string[],
): Promise<ScriptAudit> {
  const reasons: string[] = [];
  const runtimeDependencies = new Set<string>();
  const pythonPaths = paths
    .filter((path) => path.endsWith(".py"))
    .map((path) => join(root, path));
  if (pythonPaths.length > 0) {
    runtimeDependencies.add("Python 3.10+");
    const { stdout } = await execFileAsync(
      "python3",
      ["-c", PYTHON_IMPORT_AUDIT, ...pythonPaths],
      { maxBuffer: 1024 * 1024, timeout: 10_000 },
    );
    const audit = JSON.parse(stdout) as PythonScriptAudit;
    if (audit.error !== undefined) throw new Error(audit.error);
    if (
      !Array.isArray(audit.dependencies) ||
      !Array.isArray(audit.syntaxErrors)
    ) {
      throw new Error("Python script audit returned an invalid result");
    }
    for (const dependency of audit.dependencies) {
      if (typeof dependency !== "string" || dependency.length === 0) {
        throw new Error("Python script audit returned an invalid dependency");
      }
      runtimeDependencies.add(dependency);
    }
    for (const error of audit.syntaxErrors) {
      if (typeof error.path !== "string" || typeof error.message !== "string") {
        throw new Error("Python script audit returned an invalid syntax error");
      }
      const path = portablePath(relative(root, error.path));
      const location =
        typeof error.line === "number" ? `${path}:${error.line}` : path;
      reasons.push(`Python syntax error: ${location}: ${error.message}`);
    }
  }

  for (const path of paths) {
    const absolute = join(root, path);
    try {
      if (path.endsWith(".sh")) {
        runtimeDependencies.add("Bash");
        await execFileAsync("bash", ["-n", absolute], { timeout: 10_000 });
      } else if (/\.(?:c|m)?js$/.test(path)) {
        runtimeDependencies.add("Node.js");
        await execFileAsync(process.execPath, ["--check", absolute], {
          timeout: 10_000,
        });
      } else if (path.endsWith(".ts")) {
        runtimeDependencies.add("TypeScript project tooling");
        reasons.push(`TypeScript syntax audit is unavailable: ${path}`);
      }
    } catch (cause) {
      const error = cause as Error & {
        readonly code?: string;
        readonly stderr?: string;
      };
      if (error.code === "ENOENT") throw cause;
      const detail = error.stderr?.trim() || error.message;
      reasons.push(`script syntax error: ${path}: ${detail}`);
    }
  }

  return {
    reasons,
    runtimeDependencies: [...runtimeDependencies].sort(),
  };
}

async function inspectCandidate(
  sourceRoot: string,
  definition: CandidateDefinition,
): Promise<CandidateInspection> {
  const root = join(sourceRoot, definition.name);
  try {
    if (!(await lstat(root)).isDirectory())
      throw new Error("candidate source is not a directory");
    const files = await collectFiles(root);
    const sourceSha256 = await digestFiles(root, files);
    const skillPath = join(root, "SKILL.md");
    const frontmatter = parseFrontmatter(await readFile(skillPath, "utf8"));
    const semanticReasons = SEMANTIC_BLOCKERS.filter(({ pattern }) =>
      pattern.test(frontmatter.body),
    ).map(({ reason }) => reason);

    const frontmatterReasons: string[] = [];
    if (frontmatter.attributes.name !== definition.name) {
      frontmatterReasons.push(
        "frontmatter name does not match the candidate directory",
      );
    }
    if (
      typeof frontmatter.attributes.description !== "string" ||
      frontmatter.attributes.description.trim().length === 0
    ) {
      frontmatterReasons.push("frontmatter description is missing or empty");
    }
    const unexpectedFields = Object.keys(frontmatter.attributes).filter(
      (field) => !SOURCE_FRONTMATTER_FIELDS.has(field),
    );
    if (unexpectedFields.length > 0) {
      frontmatterReasons.push(
        `frontmatter contains unsupported fields: ${unexpectedFields.sort().join(", ")}`,
      );
    }

    const containmentReasons: string[] = [];
    const referenceReasons: string[] = [];
    const scriptPaths: string[] = [];
    for (const path of files) {
      const absolute = resolve(root, path);
      if (!isContained(root, absolute))
        containmentReasons.push(`path escapes the Skill root: ${path}`);
      if (path.endsWith(".md")) {
        const markdown = await readFile(absolute, "utf8");
        for (const target of localMarkdownTargets(markdown)) {
          const resolvedTarget = resolve(dirname(absolute), target);
          if (!isContained(root, resolvedTarget)) {
            containmentReasons.push(
              `Markdown reference escapes the Skill root: ${path} -> ${target}`,
            );
            continue;
          }
          const exists = await stat(resolvedTarget)
            .then(() => true)
            .catch(() => false);
          if (!exists)
            referenceReasons.push(
              `Markdown reference is missing: ${path} -> ${target}`,
            );
        }
      }
      const extension = path.slice(path.lastIndexOf("."));
      if (SCRIPT_EXTENSIONS.has(extension)) {
        scriptPaths.push(path);
        const content = await readFile(absolute);
        if (content.length === 0)
          referenceReasons.push(`script is empty: ${path}`);
      }
    }
    const scriptAudit = await auditScripts(root, scriptPaths);
    referenceReasons.push(...scriptAudit.reasons);

    const licenseReasons: string[] = [];
    if (!files.includes("LICENSE")) licenseReasons.push("LICENSE is missing");
    if (!files.includes("NOTICE")) licenseReasons.push("NOTICE is missing");
    if (files.includes("LICENSE")) {
      const license = await readFile(join(root, "LICENSE"), "utf8");
      if (
        !license.includes("Apache License") ||
        !license.includes("Version 2.0")
      ) {
        licenseReasons.push("LICENSE is not identifiable as Apache-2.0");
      }
    }
    if (files.includes("NOTICE")) {
      const notice = await readFile(join(root, "NOTICE"), "utf8");
      if (notice.trim().length === 0) licenseReasons.push("NOTICE is empty");
    }

    const runtimeReasons: string[] = [];
    if (definition.runtimeDependencies.length === 0) {
      runtimeReasons.push("runtime dependencies are not declared");
    }
    for (const dependency of definition.runtimeDependencies) {
      if (!textCoversDependency(definition.compatibility, dependency)) {
        runtimeReasons.push(
          `compatibility does not declare runtime dependency: ${dependency}`,
        );
      }
    }
    for (const dependency of scriptAudit.runtimeDependencies) {
      if (
        !definition.runtimeDependencies.some((declared) =>
          textCoversDependency(declared, dependency),
        )
      ) {
        runtimeReasons.push(`undeclared Python dependency: ${dependency}`);
      }
      if (!textCoversDependency(definition.compatibility, dependency)) {
        runtimeReasons.push(
          `compatibility omits script dependency: ${dependency}`,
        );
      }
    }
    const checks: Record<AgentPluginAuditCheckName, AgentPluginAuditCheck> = {
      portable: check(
        semanticReasons.length === 0 ? "pass" : "fail",
        semanticReasons,
      ),
      frontmatter: check(
        frontmatterReasons.length === 0 ? "pass" : "fail",
        frontmatterReasons,
      ),
      containment: check(
        containmentReasons.length === 0 ? "pass" : "fail",
        containmentReasons,
      ),
      license: check(
        licenseReasons.length === 0 ? "pass" : "fail",
        licenseReasons,
      ),
      "reference-script": check(
        referenceReasons.length === 0 ? "pass" : "fail",
        referenceReasons,
      ),
      "runtime-dependency": check(
        runtimeReasons.length === 0 ? "pass" : "fail",
        runtimeReasons,
      ),
    };
    const disposition: AgentPluginDisposition = CHECK_NAMES.every(
      (name) => checks[name].status === "pass",
    )
      ? "certified"
      : "onboard-owned";
    return {
      definition,
      root,
      files,
      frontmatter,
      sourceSha256,
      result: {
        name: definition.name,
        sourceSha256,
        checks,
        runtimeDependencies: definition.runtimeDependencies,
        disposition,
      },
    };
  } catch (cause) {
    const reason =
      cause instanceof Error ? cause.message : "candidate audit failed";
    const checks = {} as Record<
      AgentPluginAuditCheckName,
      AgentPluginAuditCheck
    >;
    for (const name of CHECK_NAMES) checks[name] = check("blocked", [reason]);
    return {
      definition,
      root,
      files: [],
      frontmatter: { attributes: {}, body: "" },
      sourceSha256: null,
      result: {
        name: definition.name,
        sourceSha256: null,
        checks,
        runtimeDependencies: definition.runtimeDependencies,
        disposition: "blocked",
      },
    };
  }
}

async function readCanonicalIdentity(
  canonicalDirectory: string,
): Promise<CanonicalIdentity> {
  try {
    const value: unknown = JSON.parse(
      await readFile(join(canonicalDirectory, "manifest.json"), "utf8"),
    );
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("manifest is not an object");
    }
    const manifest = value as Record<string, unknown>;
    const identity: CanonicalIdentity = {
      sourceId: String(manifest.sourceId ?? ""),
      canonicalSourceUri: String(manifest.canonicalSourceUri ?? ""),
      resolvedRevision: String(manifest.resolvedRevision ?? ""),
      sourceTreeSha256: String(manifest.sourceTreeSha256 ?? ""),
    };
    if (
      identity.sourceId.length === 0 ||
      !/^https:\/\//.test(identity.canonicalSourceUri) ||
      !/^[0-9a-f]{40}$/.test(identity.resolvedRevision) ||
      !/^[0-9a-f]{64}$/.test(identity.sourceTreeSha256)
    )
      throw new Error("manifest identity is incomplete or invalid");
    return identity;
  } catch (cause) {
    throw new KitError(
      "PROJECTION_CANONICAL_INVALID",
      "canonical Kit manifest is invalid for Agent Plugin projection",
      {
        phase: "agent-plugin",
        cause: cause instanceof Error ? cause.message : "unknown",
      },
    );
  }
}

function renderSkill(
  inspection: CandidateInspection,
  revision: string,
): string {
  const frontmatter = {
    name: inspection.definition.name,
    description: inspection.frontmatter.attributes.description,
    license: "Apache-2.0",
    "allowed-tools": inspection.definition.allowedTools,
    metadata: {
      "sbtd.category": inspection.definition.category,
      "sbtd.portable": "true",
      "sbtd.source-revision": revision,
    },
    compatibility: inspection.definition.compatibility,
  };
  return `---\n${stringifyYaml(frontmatter)}---\n${inspection.frontmatter.body}`;
}

async function writeSnapshot(
  stage: string,
  canonicalDirectory: string,
): Promise<GeneratedAgentPluginProjection> {
  const identity = await readCanonicalIdentity(canonicalDirectory);
  const sourceRoot = join(
    canonicalDirectory,
    "onboard",
    "runtime",
    "templates",
    "skills",
  );
  const inspections = await Promise.all(
    CANDIDATES.map((candidate) => inspectCandidate(sourceRoot, candidate)),
  );
  const audit: AgentPluginAuditReport = {
    schemaVersion: 1,
    candidateCount: inspections.length,
    certifiedCount: inspections.filter(
      ({ result }) => result.disposition === "certified",
    ).length,
    results: inspections.map(({ result }) => result),
  };
  const blocked = audit.results.filter(
    ({ disposition }) => disposition === "blocked",
  );
  if (blocked.length > 0) {
    throw new KitError(
      "PROJECTION_POLICY_INVALID",
      "Agent Plugin audit contains blocked candidates",
      {
        phase: "agent-plugin",
        candidates: blocked.map(({ name }) => name),
        audit,
      },
    );
  }

  await mkdir(join(stage, "skills"), { recursive: true });
  const skills: Record<string, AgentPluginProjectionSkill> = {};
  for (const inspection of inspections) {
    if (inspection.result.disposition !== "certified") continue;
    if (inspection.sourceSha256 === null) {
      throw new KitError(
        "PROJECTION_POLICY_INVALID",
        "certified Agent Plugin Skill has no source digest",
        { phase: "agent-plugin", candidate: inspection.definition.name },
      );
    }
    const destination = join(stage, "skills", inspection.definition.name);
    await cp(inspection.root, destination, { recursive: true });
    await writeFile(
      join(destination, "SKILL.md"),
      renderSkill(inspection, identity.resolvedRevision),
      "utf8",
    );
    const files = await collectFiles(destination);
    skills[inspection.definition.name] = {
      sourceSha256: inspection.sourceSha256,
      projectionSha256: await digestFiles(destination, files),
      files: await fileDigests(destination, files),
    };
  }

  const auditText = `${JSON.stringify(audit, null, 2)}\n`;
  const catalog: AgentPluginProjectionCatalog = {
    schemaVersion: 1,
    candidateCount: audit.candidateCount,
    certifiedCount: audit.certifiedCount,
    entries: inspections.map(({ definition, result }) => ({
      name: definition.name,
      source: `onboard/runtime/templates/skills/${definition.name}`,
      certification: {
        disposition: result.disposition,
        checks: result.checks,
        sourceSha256: result.sourceSha256,
        projectionSha256: skills[definition.name]?.projectionSha256 ?? null,
      },
    })),
  };
  const catalogText = `${JSON.stringify(catalog, null, 2)}\n`;
  await Promise.all([
    writeFile(join(stage, "audit.json"), auditText, "utf8"),
    writeFile(join(stage, "catalog.json"), catalogText, "utf8"),
  ]);
  const projectedFiles = await collectFiles(join(stage, "skills"));
  const assets = {
    "audit.json": sha256(auditText),
    "catalog.json": sha256(catalogText),
    ...(await fileDigests(join(stage, "skills"), projectedFiles, "skills")),
  };
  const generatedSha256 = sha256(
    Object.entries(assets)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([path, digest]) => `${path}\0${digest}`)
      .join("\n"),
  );
  const manifest: AgentPluginProjectionManifest = {
    schemaVersion: 1,
    ...identity,
    transformVersion: "agent-plugin-p0-v1",
    auditSha256: sha256(auditText),
    catalogSha256: sha256(catalogText),
    generatedSha256,
    candidateCount: audit.candidateCount,
    certifiedCount: audit.certifiedCount,
    certified: audit.results
      .filter(({ disposition }) => disposition === "certified")
      .map(({ name }) => name),
    excluded: audit.results
      .filter(({ disposition }) => disposition !== "certified")
      .map(({ name, checks }) => ({
        name,
        reasons: CHECK_NAMES.flatMap((checkName) => checks[checkName].reasons),
      })),
    assets,
    skills,
  };
  await writeFile(
    join(stage, "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );
  return { audit, catalog, manifest };
}

export async function generateAgentPluginProjection(
  options: GenerateAgentPluginProjectionOptions,
): Promise<GeneratedAgentPluginProjection> {
  const packageRoot = resolve(options.packageRoot);
  const canonicalDirectory = resolve(options.canonicalDirectory);
  const outputDirectory = resolve(options.outputDirectory);
  if (
    canonicalDirectory === packageRoot ||
    outputDirectory === packageRoot ||
    !isContained(packageRoot, canonicalDirectory) ||
    !isContained(packageRoot, outputDirectory) ||
    isContained(canonicalDirectory, outputDirectory) ||
    isContained(outputDirectory, canonicalDirectory)
  ) {
    throw new KitError(
      "PROJECTION_POLICY_INVALID",
      "Agent Plugin projection paths must be distinct package-contained trees",
      {
        phase: "agent-plugin",
        packageRoot,
        canonicalDirectory,
        outputDirectory,
      },
    );
  }
  const outputParent = dirname(outputDirectory);
  await mkdir(outputParent, { recursive: true });
  const stage = join(outputParent, `.${randomUUID()}.agent-plugin-stage`);
  const backup = join(outputParent, `.${randomUUID()}.agent-plugin-previous`);
  try {
    const result = await writeSnapshot(stage, canonicalDirectory);
    const outputExists = await stat(outputDirectory)
      .then(() => true)
      .catch(() => false);
    if (outputExists) await rename(outputDirectory, backup);
    try {
      await rename(stage, outputDirectory);
      await rm(backup, { force: true, recursive: true });
    } catch (cause) {
      if (outputExists) await rename(backup, outputDirectory);
      throw cause;
    }
    return result;
  } catch (cause) {
    await rm(stage, { force: true, recursive: true });
    throw cause;
  }
}

export async function checkAgentPluginProjection(
  options: GenerateAgentPluginProjectionOptions,
): Promise<void> {
  const expectedDirectory = resolve(options.outputDirectory);
  const checkDirectory = join(
    dirname(expectedDirectory),
    `.${randomUUID()}.agent-plugin-check`,
  );
  try {
    await generateAgentPluginProjection({
      ...options,
      outputDirectory: checkDirectory,
    });
    const expectedFiles = await collectFiles(checkDirectory);
    const actualFiles = await collectFiles(expectedDirectory).catch(() => []);
    if (expectedFiles.join("\0") !== actualFiles.join("\0")) {
      throw new KitError(
        "GENERATED_DRIFT",
        "Agent Plugin projection has missing or unexpected assets",
        { phase: "agent-plugin", expectedFiles, actualFiles },
      );
    }
    for (const path of expectedFiles) {
      const [expected, actual] = await Promise.all([
        readFile(join(checkDirectory, path)),
        readFile(join(expectedDirectory, path)),
      ]);
      if (!expected.equals(actual)) {
        throw new KitError(
          "GENERATED_DRIFT",
          "Agent Plugin projection differs from the verified Kit",
          { phase: "agent-plugin", path },
        );
      }
    }
  } finally {
    await rm(checkDirectory, { force: true, recursive: true });
  }
}
