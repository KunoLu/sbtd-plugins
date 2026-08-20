import { createHash } from "node:crypto";
import { z } from "zod";

/**
 * Tool Risk module: the single seam between raw OMP tool-call events and the
 * SBTD rule registry. It owns tool capability classification, dependency
 * mutation detection, secret-access detection, stable input fingerprints and
 * typed one-shot approvals. `beforeToolCall` consumes only
 * {@link observeToolRisk} output; OMP event types stay at the adapter edge.
 *
 * Host contract limitation (OMP 17.3.5): the extension event carries only
 * `toolCallId`/`toolName`/`input`; the host's internal ToolTier and shell
 * tokenizer are not exposed. Shell text cannot prove alias/function/wrapper or
 * dynamic-variable behavior, so command parsing here is conservative: it can
 * prove high-confidence danger, never complete mediation.
 */

export const toolCapabilities = [
  "local-read",
  "external-read",
  "workspace-write",
  "external-write",
  "destructive",
  "phase-transition",
  "coordination",
  "diagnostic",
  "unknown",
] as const;

export type ToolCapability = (typeof toolCapabilities)[number];

export type ToolRiskClass = "dependency-install" | "secret-read";

const toolCallSchema = z.object({ toolName: z.string() }).passthrough();

const toolCallIdSchema = z
  .object({ toolCallId: z.string().optional() })
  .passthrough();

const bashToolCallSchema = z
  .object({
    toolName: z.literal("bash"),
    input: z.object({ command: z.string() }).passthrough(),
  })
  .passthrough();

const pathReadToolCallSchema = z
  .object({
    toolName: z.enum(["read", "grep", "glob"]),
    input: z.object({ path: z.string() }).passthrough(),
  })
  .passthrough();

/**
 * Plugin-local capability registry for the OMP 17.3.5 built-in tool set.
 * Mirrors the host's declared read tier where it exists; everything not
 * listed (including `mcp__*` tools) stays `unknown` and fails closed.
 */
const builtinToolCapabilities: Readonly<Record<string, ToolCapability>> = {
  read: "local-read",
  grep: "local-read",
  glob: "local-read",
  lsp: "local-read",
  ast_grep: "local-read",
  inspect_image: "local-read",
  web_search: "external-read",
  ask: "coordination",
  todo: "coordination",
  debug: "diagnostic",
  recall: "diagnostic",
  reflect: "diagnostic",
  security_scan: "diagnostic",
  write: "workspace-write",
  edit: "workspace-write",
  ast_edit: "workspace-write",
  memory_edit: "workspace-write",
  retain: "workspace-write",
  learn: "workspace-write",
  checkpoint: "workspace-write",
  bash: "destructive",
  eval: "destructive",
  rewind: "destructive",
  browser: "external-write",
  computer: "external-write",
  github: "external-write",
  hub: "external-write",
  task: "external-write",
  sbtd_workflow: "phase-transition",
};

const safeDiagnosticCapabilities: Readonly<Record<string, true>> = {
  "local-read": true,
  "external-read": true,
  coordination: true,
  diagnostic: true,
};

const sshPathPattern = /^ssh:\/\//i;

// ---------------------------------------------------------------------------
// Shell text analysis (conservative; see host contract limitation above)
// ---------------------------------------------------------------------------

interface ShellToken {
  readonly text: string;
  /** True only for a single quoted literal, not a nested command string. */
  readonly quoted: boolean;
}

function tokenizeShell(text: string, depth = 0): ShellToken[] {
  const tokens: ShellToken[] = [];
  const pattern = /"([^"]*)"|'([^']*)'|(\S+)/g;
  for (const match of text.matchAll(pattern)) {
    const doubleQuoted = match[1];
    const singleQuoted = match[2];
    if (doubleQuoted !== undefined || singleQuoted !== undefined) {
      const inner = doubleQuoted ?? singleQuoted ?? "";
      if (depth < 2 && /\s/.test(inner)) {
        // A quoted string that itself contains a command line (for example
        // `bash -c 'cat .env'`) is a nested command, not a quoted literal.
        tokens.push(...tokenizeShell(inner, depth + 1));
        continue;
      }
      tokens.push({ text: inner, quoted: true });
      continue;
    }
    const bare = match[3] ?? "";
    if (bare.length > 0) tokens.push({ text: bare, quoted: false });
  }
  return tokens;
}

function splitCommandSegments(command: string): string[] {
  return command
    .split(/&&|\|\||[;|\r\n]/)
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
}

const shellPrefixCommands: Readonly<Record<string, true>> = {
  sudo: true,
  corepack: true,
  command: true,
  builtin: true,
};
const envAssignmentPattern = /^[A-Za-z_][A-Za-z0-9_]*=/;

/**
 * Strips environment assignments and inert wrapper prefixes. Aliases,
 * functions and dynamic variables cannot be resolved from shell text and are
 * never treated as proof of safety.
 */
function significantTokens(segment: string): string[] {
  const tokens = tokenizeShell(segment).map((token) => token.text);
  let index = 0;
  if (tokens[index] === "env") {
    index += 1;
    while (
      index < tokens.length &&
      (envAssignmentPattern.test(tokens[index] ?? "") ||
        tokens[index]?.startsWith("-") === true)
    )
      index += 1;
  }
  while (
    index < tokens.length &&
    (shellPrefixCommands[tokens[index] ?? ""] === true ||
      envAssignmentPattern.test(tokens[index] ?? ""))
  )
    index += 1;
  return tokens.slice(index);
}

const jsPackageManagers: Readonly<Record<string, true>> = {
  npm: true,
  pnpm: true,
  bun: true,
};
const jsInstallSubcommands: Readonly<Record<string, true>> = {
  add: true,
  install: true,
  i: true,
  ci: true,
};
const pythonRuntimes: Readonly<Record<string, true>> = {
  python: true,
  python3: true,
  py: true,
};

function tokensAreDependencyMutation(tokens: readonly string[]): boolean {
  const [command, ...rest] = tokens;
  if (command === undefined) return false;
  const name = command.toLowerCase();
  if (
    name === "bash" ||
    name === "sh" ||
    name === "zsh" ||
    name === "fish" ||
    name === "cmd" ||
    name === "powershell" ||
    name === "pwsh"
  ) {
    const inlineIndex = rest.findIndex((token) => {
      const flag = token.toLowerCase();
      return (
        flag === "-c" ||
        flag === "/c" ||
        flag === "-command" ||
        flag === "-commandwithargs"
      );
    });
    return (
      inlineIndex !== -1 &&
      tokensAreDependencyMutation(rest.slice(inlineIndex + 1))
    );
  }
  const firstMeaningful = () =>
    rest.find((token) => !token.startsWith("-"))?.toLowerCase();
  if (jsPackageManagers[name] === true)
    return jsInstallSubcommands[firstMeaningful() ?? ""] === true;
  if (name === "yarn") {
    if (rest.length === 0) return true; // bare `yarn` performs an install
    const sub = firstMeaningful();
    return sub === "add" || sub === "install";
  }
  if (name === "pip" || name === "pip3") return firstMeaningful() === "install";
  if (name === "uv")
    return (
      rest[0]?.toLowerCase() === "pip" &&
      rest
        .slice(1)
        .find((token) => !token.startsWith("-"))
        ?.toLowerCase() === "install"
    );
  if (pythonRuntimes[name] === true) {
    const moduleIndex = rest.indexOf("-m");
    if (moduleIndex === -1) return false;
    const after = rest.slice(moduleIndex + 1);
    if (after[0]?.toLowerCase() !== "pip") return false;
    return (
      after
        .slice(1)
        .find((token) => !token.startsWith("-"))
        ?.toLowerCase() === "install"
    );
  }
  if (name === "brew") return firstMeaningful() === "install";
  if (name === "cargo")
    return firstMeaningful() === "install" || firstMeaningful() === "add";
  // npx/bunx download and execute a remote package: mutation-equivalent.
  if (name === "npx" || name === "bunx")
    return rest.some((token) => !token.startsWith("-"));
  if (name === "dotnet")
    return (
      rest[0]?.toLowerCase() === "add" &&
      rest.some((token) => token.toLowerCase() === "package")
    );
  if (name === "nuget") return firstMeaningful() === "install";
  if (name === "choco" || name === "chocolatey")
    return firstMeaningful() === "install";
  if (name === "winget") return firstMeaningful() === "install";
  if (name === "composer")
    return (
      firstMeaningful() === "install" ||
      firstMeaningful() === "require" ||
      firstMeaningful() === "update"
    );
  if (name === "go") {
    const sub = firstMeaningful();
    if (sub === "get" || sub === "install") return true;
    if (sub === "mod") {
      const modAction = rest
        .filter((token) => !token.startsWith("-"))
        .at(1)
        ?.toLowerCase();
      return (
        modAction === "tidy" ||
        modAction === "download" ||
        modAction === "vendor"
      );
    }
    return false;
  }
  if (name === "install-package" || name === "install-module") return true;
  return false;
}

export function isDependencyInstall(command: string | undefined): boolean {
  if (command === undefined) return false;
  return splitCommandSegments(command).some((segment) =>
    tokensAreDependencyMutation(significantTokens(segment)),
  );
}

// ---------------------------------------------------------------------------
// Secret access inventory
// ---------------------------------------------------------------------------

const SECRET_BOUNDARY_BEFORE = `(?:^|[/"'\\s:=])`;
const SECRET_BOUNDARY_AFTER = `(?=[/"'\\s]|$)`;

const secretPath = (body: string): RegExp =>
  new RegExp(`${SECRET_BOUNDARY_BEFORE}${body}${SECRET_BOUNDARY_AFTER}`, "i");

/**
 * High-confidence credential locations. Public-certificate and template
 * variants are deliberately excluded here and tracked in
 * {@link mixedSecretPathPatterns} so mixed public/secret files stay
 * policy-configurable instead of being hard-blocked by name alone.
 */
export const highConfidenceSecretPathPatterns: readonly RegExp[] = [
  secretPath(
    `\\.env(?:\\.(?!example\\b|sample\\b|template\\b|dist\\b)[a-z0-9_-]+)?`,
  ),
  secretPath(`\\.envrc`),
  secretPath(`\\.ssh`),
  secretPath(`id_(?:rsa|dsa|ecdsa|ed25519)(?!\\.pub)`),
  secretPath(`\\.netrc`),
  secretPath(`\\.git-credentials`),
  secretPath(`\\.npmrc`),
  secretPath(`\\.pypirc`),
  secretPath(`auth\\.json`),
  secretPath(`\\.docker/config\\.json`),
  secretPath(`\\.kube/config`),
  secretPath(`kubeconfig`),
  secretPath(`\\.aws/credentials`),
  new RegExp(`${SECRET_BOUNDARY_BEFORE}\\.config/gcloud(?:/|$)`, "i"),
  new RegExp(`${SECRET_BOUNDARY_BEFORE}\\.azure(?:/|$)`, "i"),
  secretPath(`\\.pgpass`),
  secretPath(`\\.my(?:login)?\\.cnf`),
  /usersecrets(?:\/[^/\s]+)*\/secrets\.json/i,
  secretPath(`[^/\\s]+\\.(?:pem|key|p12|pfx|keystore|jks)`),
  new RegExp(`${SECRET_BOUNDARY_BEFORE}\\.gnupg(?:/|$)`, "i"),
  /secring\.gpg/i,
];

/**
 * Mixed public/secret files: observable but not hard-blocked by default, so
 * hosts can choose a policy instead of the Plugin blocking on filename alone.
 */
export const mixedSecretPathPatterns: readonly RegExp[] = [
  secretPath(`appsettings\\.[a-z0-9_-]+\\.json`),
  secretPath(`[^/\\s]+\\.(?:crt|cer|der)`),
  secretPath(`\\.env\\.(?:example|sample|template|dist)`),
  secretPath(`nuget\\.config`),
  secretPath(`\\.aws/config`),
];

function matchesAny(text: string, patterns: readonly RegExp[]): boolean {
  const normalized = text.replaceAll("\\", "/");
  return patterns.some((pattern) => pattern.test(normalized));
}

/** Public key halves are publishable material, never secret reads. */
const publicKeyPattern = /id_(?:rsa|dsa|ecdsa|ed25519)\.pub(?=["'\s/]|$)/i;

export function isHighConfidenceSecretPath(path: string): boolean {
  return (
    !publicKeyPattern.test(path.replaceAll("\\", "/")) &&
    matchesAny(path, highConfidenceSecretPathPatterns)
  );
}

export function isMixedSecretPath(path: string): boolean {
  return (
    !isHighConfidenceSecretPath(path) &&
    matchesAny(path, mixedSecretPathPatterns)
  );
}

const secretReaderCommands: Readonly<Record<string, true>> = {
  cat: true,
  less: true,
  more: true,
  head: true,
  tail: true,
  sed: true,
  awk: true,
  grep: true,
  rg: true,
  bash: true,
  sh: true,
  zsh: true,
  fish: true,
  xargs: true,
  find: true,
  node: true,
  python: true,
  python3: true,
  ruby: true,
  perl: true,
  "get-content": true,
  gc: true,
  type: true,
  dd: true,
  base64: true,
  openssl: true,
  tar: true,
  cmd: true,
  powershell: true,
  pwsh: true,
};

const searchCommands: Readonly<Record<string, true>> = { grep: true, rg: true };

function isSecretReadCommand(command: string): boolean {
  const tokens = tokenizeShell(command).map((token) => ({
    // A `<.env` style redirection target is a read of that path.
    text: token.text.replace(/^</, ""),
    quoted: token.quoted,
  }));
  const secretTokens = tokens.filter((token) =>
    isHighConfidenceSecretPath(token.text),
  );
  if (secretTokens.length === 0) return false;
  const first = significantTokens(command)[0]?.toLowerCase();
  // A search command whose only secret-looking tokens are quoted patterns is a
  // source/README mention, not a secret read.
  if (
    first !== undefined &&
    searchCommands[first] === true &&
    secretTokens.every((token) => token.quoted)
  )
    return false;
  return tokens.some(
    (token, index) =>
      secretReaderCommands[token.text.toLowerCase()] === true ||
      (token.text.toLowerCase() === "git" &&
        tokens[index + 1]?.text.toLowerCase() === "show"),
  );
}

// ---------------------------------------------------------------------------
// Fingerprints and typed one-shot approvals
// ---------------------------------------------------------------------------

function canonicalizeForFingerprint(value: unknown): unknown {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return value.map(canonicalizeForFingerprint);
  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(record).sort())
      out[key] = canonicalizeForFingerprint(record[key]);
    return out;
  }
  return value;
}

/** Stable fingerprint over the normalized tool name and input payload. */
export function fingerprintToolCall(event: unknown): string {
  const parsed = toolCallSchema.safeParse(event);
  const payload = parsed.success
    ? { toolName: parsed.data.toolName, input: parsed.data.input ?? null }
    : null;
  return createHash("sha256")
    .update(JSON.stringify(canonicalizeForFingerprint(payload)))
    .digest("hex");
}

export interface ToolApprovalDescriptor {
  readonly toolCallId: string;
  readonly riskClasses: readonly ToolRiskClass[];
  readonly fingerprint: string;
  readonly approved: boolean;
}

/**
 * Typed one-shot approvals. A descriptor is recorded only when a risky call is
 * actually blocked; `approvalResolved` can only approve a pending descriptor;
 * replay must match the same risk class and input fingerprint; tool result,
 * deny, fingerprint change and turn/session cleanup consume it.
 */
export class ToolApprovalBook {
  readonly #pending = new Map<string, ToolApprovalDescriptor>();

  recordBlocked(
    toolCallId: string | undefined,
    riskClasses: readonly ToolRiskClass[],
    fingerprint: string,
  ): void {
    if (toolCallId === undefined || riskClasses.length === 0) return;
    this.#pending.set(toolCallId, {
      toolCallId,
      riskClasses: [...new Set(riskClasses)].sort(),
      fingerprint,
      approved: false,
    });
  }

  resolve(toolCallId: string, approved: boolean): void {
    const descriptor = this.#pending.get(toolCallId);
    if (descriptor === undefined) return;
    if (!approved) {
      this.#pending.delete(toolCallId);
      return;
    }
    this.#pending.set(toolCallId, { ...descriptor, approved: true });
  }

  isApproved(
    toolCallId: string | undefined,
    riskClass: ToolRiskClass,
    fingerprint: string,
  ): boolean {
    if (toolCallId === undefined) return false;
    const descriptor = this.#pending.get(toolCallId);
    if (descriptor === undefined) return false;
    if (descriptor.fingerprint !== fingerprint) {
      // A replay with a changed target/command invalidates the approval.
      this.#pending.delete(toolCallId);
      return false;
    }
    return descriptor.approved && descriptor.riskClasses.includes(riskClass);
  }

  consume(toolCallId: string | undefined): void {
    if (toolCallId === undefined) return;
    this.#pending.delete(toolCallId);
  }

  clear(): void {
    this.#pending.clear();
  }

  pendingDescriptors(): readonly ToolApprovalDescriptor[] {
    return [...this.#pending.values()];
  }
}

// ---------------------------------------------------------------------------
// Observation seam
// ---------------------------------------------------------------------------

export interface ToolRiskObservation {
  readonly toolName: string | undefined;
  readonly capability: ToolCapability;
  /** True when a nominally local tool reaches a remote (ssh://) target. */
  readonly remote: boolean;
  readonly mutationOrPhaseAdvancing: boolean;
  readonly command: string | undefined;
  readonly installingDependency: boolean;
  readonly secretRead: boolean;
  readonly mixedSecretAccess: boolean;
  readonly fingerprint: string;
  readonly riskClasses: readonly ToolRiskClass[];
  readonly requiresApproval: boolean;
  readonly installApproved: boolean;
  readonly secretReadApproved: boolean;
}

export function riskClassesFor(observation: {
  readonly installingDependency: boolean;
  readonly secretRead: boolean;
}): ToolRiskClass[] {
  return [
    ...(observation.installingDependency
      ? (["dependency-install"] as const)
      : []),
    ...(observation.secretRead ? (["secret-read"] as const) : []),
  ];
}

export function observeToolRisk(
  event: unknown,
  approvals?: ToolApprovalBook,
): ToolRiskObservation {
  const parsed = toolCallSchema.safeParse(event);
  const toolName = parsed.success ? parsed.data.toolName : undefined;
  const path = pathReadToolCallSchema.safeParse(event).data?.input.path;
  const remote = path !== undefined && sshPathPattern.test(path);
  // MCP-mounted tools reuse the registry by their leaf name when the leaf is
  // a known safe diagnostic (mcp__x__debug → debug); anything else fails
  // closed as unknown.
  const mcpLeaf = toolName?.startsWith("mcp__")
    ? toolName.split("__").at(-1)
    : undefined;
  const mcpLeafCapability =
    mcpLeaf === undefined ? undefined : builtinToolCapabilities[mcpLeaf];
  const safeMcpLeaf =
    mcpLeafCapability !== undefined &&
    safeDiagnosticCapabilities[mcpLeafCapability] === true
      ? mcpLeafCapability
      : undefined;
  const capability: ToolCapability =
    toolName === undefined
      ? "unknown"
      : toolName === "read" && remote
        ? "external-read"
        : (builtinToolCapabilities[toolName] ?? safeMcpLeaf ?? "unknown");
  const mutationOrPhaseAdvancing =
    safeDiagnosticCapabilities[capability] !== true || remote;
  const command = bashToolCallSchema.safeParse(event).data?.input.command;
  const installingDependency = isDependencyInstall(command);
  const secretRead =
    (path !== undefined && isHighConfidenceSecretPath(path)) ||
    (command !== undefined && isSecretReadCommand(command));
  const mixedSecretAccess =
    !secretRead &&
    ((path !== undefined && isMixedSecretPath(path)) ||
      (command !== undefined && matchesAny(command, mixedSecretPathPatterns)));
  const fingerprint = fingerprintToolCall(event);
  const riskClasses = riskClassesFor({ installingDependency, secretRead });
  const toolCallId = toolCallIdSchema.safeParse(event).data?.toolCallId;
  const installApproved =
    installingDependency &&
    approvals?.isApproved(toolCallId, "dependency-install", fingerprint) ===
      true;
  const secretReadApproved =
    secretRead &&
    approvals?.isApproved(toolCallId, "secret-read", fingerprint) === true;
  return {
    toolName,
    capability,
    remote,
    mutationOrPhaseAdvancing,
    command,
    installingDependency,
    secretRead,
    mixedSecretAccess,
    fingerprint,
    riskClasses,
    requiresApproval: riskClasses.length > 0,
    installApproved,
    secretReadApproved,
  };
}
