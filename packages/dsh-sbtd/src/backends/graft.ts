/**
 * Graft backend (PR-B) — optional read-only structural queries over the
 * managed `sbtd-graft` MCP launcher.
 *
 * Migration from the deleted GitNexus backend (R1 Q5 A):
 * - `AnalysisResult` shape kept unchanged (R2 Q4 A): ok|skipped|advisory +
 *   summary/reason; validate pre/post mapping untouched.
 * - Reason vocabulary replaced by GRAFT_SKIP_REASONS (R2 Q4 A); every
 *   degradation is `skipped` with a reason, never a load rejection and never
 *   blocks validate (R1 Q1 A / Q9 A).
 * - serverName injection kept, default `"sbtd-graft"`; tools probed as
 *   `mcp__<server>__graft_*` (R3 Q2 A).
 * - The plugin never inits/spawns Graft, never writes MCP config, and never
 *   probes the CLI version: `version-unsupported` only comes from a
 *   host-injected version declaration (R3 Q2 A).
 */

/** Shape lock (R2 Q4 A): identical to the deleted GitNexus AnalysisResult. */
export type AnalysisResult = {
  status: "ok" | "skipped" | "advisory";
  summary: string;
  advisory?: true;
  reason?: string;
};

/** Injectable MCP surface for Cordis/DSH tool names + calls. */
export type McpClient = {
  listToolNames: () => Iterable<string> | Promise<Iterable<string>>;
  callTool: (
    name: string,
    args: Record<string, unknown>,
  ) => Promise<unknown>;
};

export type GraftOptions = {
  /** MCP server id; default `"sbtd-graft"` (R3 Q2 A). */
  serverName?: string;
  /** Injected MCP client (production host / tests). */
  mcp?: McpClient | null;
  /**
   * Optional pre-listed tool names for probing without a full client.
   * Ignored for callTool — impact/detectChanges still need `mcp`.
   */
  toolNames?: Iterable<string>;
  /**
   * Host-injected Graft version declaration (R3 Q2 A). When present and not
   * in SUPPORTED_GRAFT_VERSIONS ⇒ skipped `version-unsupported`. The plugin
   * never probes versions on its own.
   */
  versionDeclaration?: string;
};

/** Reason vocabulary lock (R2 Q4 A); each value has a dedicated test. */
export const GRAFT_SKIP_REASONS = [
  "launcher-missing",
  "version-unsupported",
  "call-failed",
  "guard-failed",
  "graph-missing",
  "graph-stale",
] as const;
export type GraftSkipReason = (typeof GRAFT_SKIP_REASONS)[number];

const DEFAULT_SERVER = "sbtd-graft";

/**
 * Supported Graft versions for the injected declaration check (R3 Q2 A).
 * Pinned to the managed launcher pin (@nanonets/graft 0.22.0); extend only
 * together with a managed wiring update.
 */
export const SUPPORTED_GRAFT_VERSIONS = ["0.22.0"] as const;

/**
 * The managed launcher prints one fixed sanitized `sbtd-graft-entry: …`
 * stderr line and exits 2 on any guard failure. Hosts surface that line (or
 * the exit code) through the MCP call error; both mark `guard-failed`.
 */
const GUARD_FAILURE_RE = /sbtd-graft-entry:|\bexited?\s+with\s+(?:code\s+)?2\b/;

/** Freshness probe text markers from `graft_check_freshness`. */
const NO_GRAPH_RE = /no graph/i;
const STALE_RE = /\bstale\b/i;

/** Form Cordis-style Graft tool names for a server (R3 Q2 A). */
export function formGraftToolNames(serverName: string = DEFAULT_SERVER): {
  freshness: string;
  findCode: string;
  prefix: string;
} {
  return {
    freshness: `mcp__${serverName}__graft_check_freshness`,
    findCode: `mcp__${serverName}__graft_find_code`,
    prefix: `mcp__${serverName}__graft_`,
  };
}

async function listedToolSet(options: GraftOptions): Promise<Set<string>> {
  if (options.mcp) {
    try {
      const names = await Promise.resolve(options.mcp.listToolNames());
      return new Set(names);
    } catch {
      return new Set();
    }
  }
  if (options.toolNames) {
    return new Set(options.toolNames);
  }
  return new Set();
}

/**
 * Probe wired Graft tools for the configured server (R3 Q2 A). No fallback
 * server name: a differently-named wiring is not this plugin's backend.
 */
export async function resolveGraftTools(
  options: GraftOptions = {},
): Promise<{
  freshness: string | null;
  findCode: string | null;
  mcpVisible: boolean;
}> {
  const names = formGraftToolNames(options.serverName ?? DEFAULT_SERVER);
  const listed = await listedToolSet(options);
  const freshness = listed.has(names.freshness) ? names.freshness : null;
  const findCode = listed.has(names.findCode) ? names.findCode : null;
  return {
    freshness,
    findCode,
    mcpVisible: freshness != null || findCode != null,
  };
}

function skipped(summary: string, reason: GraftSkipReason): AnalysisResult {
  return { status: "skipped", summary, reason };
}

function callFailed(err: unknown, what: string): AnalysisResult {
  const message = err instanceof Error ? err.message : String(err);
  if (GUARD_FAILURE_RE.test(message)) {
    return skipped(
      `Graft launcher guard failed (${what}): ${message}`,
      "guard-failed",
    );
  }
  return skipped(`Graft ${what} call failed: ${message}`, "call-failed");
}

/** MCP error results may be returned rather than rejected by an injected host. */
async function callGraftTool(
  mcp: McpClient,
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  const result = await mcp.callTool(name, args);
  if (result !== null && typeof result === "object" &&
      "isError" in result && result.isError === true) {
    throw new Error(toSummary(result));
  }
  return result;
}

type FreshnessOutcome =
  | { kind: "fresh" }
  | { kind: "skipped"; result: AnalysisResult };

/**
 * Freshness probe via the managed launcher (read-only). Maps the probe text
 * to graph-missing / graph-stale; errors to guard-failed / call-failed.
 */
async function probeFreshness(
  mcp: McpClient,
  freshnessTool: string,
  what: string,
): Promise<FreshnessOutcome> {
  let raw: unknown;
  try {
    raw = await callGraftTool(mcp, freshnessTool, {});
  } catch (err) {
    return { kind: "skipped", result: callFailed(err, what) };
  }
  const text = toSummary(raw);
  if (NO_GRAPH_RE.test(text)) {
    return {
      kind: "skipped",
      result: skipped(
        "Graft graph missing (freshness probe: no graph).",
        "graph-missing",
      ),
    };
  }
  if (STALE_RE.test(text)) {
    return {
      kind: "skipped",
      result: skipped(
        "Graft graph stale (freshness probe: drift detected); treat structural evidence as unavailable.",
        "graph-stale",
      ),
    };
  }
  if (!/\bin sync with the code\b/i.test(text)) {
    return {
      kind: "skipped",
      result: skipped("Graft freshness probe returned no recognizable verdict.", "call-failed"),
    };
  }
  return { kind: "fresh" };
}

function toSummary(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "(empty)";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/**
 * Shared degradation pipeline (R1 Q1 A): version declaration → launcher
 * probe → freshness probe. Returns the skip result, or the resolved tools
 * when the graph is fresh. Never throws.
 */
async function gate(
  options: GraftOptions,
  what: string,
): Promise<
  | { ok: false; result: AnalysisResult }
  | { ok: true; mcp: McpClient; findCode: string | null }
> {
  if (
    options.versionDeclaration != null &&
    !(SUPPORTED_GRAFT_VERSIONS as readonly string[]).includes(
      options.versionDeclaration.trim(),
    )
  ) {
    return {
      ok: false,
      result: skipped(
        `Graft version declaration ${JSON.stringify(options.versionDeclaration)} is not in the supported set (${SUPPORTED_GRAFT_VERSIONS.join(", ")}); ${what} skipped.`,
        "version-unsupported",
      ),
    };
  }
  if (!options.mcp) {
    return {
      ok: false,
      result: skipped(
        "Graft MCP client not injected; launcher not wired.",
        "launcher-missing",
      ),
    };
  }
  const tools = await resolveGraftTools(options);
  if (!tools.mcpVisible || tools.freshness == null) {
    return {
      ok: false,
      result: skipped(
        `No mcp__${options.serverName ?? DEFAULT_SERVER}__graft_* tools visible; launcher missing.`,
        "launcher-missing",
      ),
    };
  }
  const freshness = await probeFreshness(options.mcp, tools.freshness, what);
  if (freshness.kind === "skipped") {
    return { ok: false, result: freshness.result };
  }
  return { ok: true, mcp: options.mcp, findCode: tools.findCode };
}

/**
 * Pre-change structural lookup (R1 Q1 A): freshness-gated `graft_find_code`
 * on the target. Never throws; every failure is skipped + reason.
 */
export async function impact(
  _cwd: string,
  target: string,
  direction?: string,
  options: GraftOptions = {},
): Promise<AnalysisResult> {
  try {
    const gated = await gate(options, "impact");
    if (!gated.ok) return gated.result;
    if (gated.findCode == null) {
      return skipped(
        "Graft find_code tool not visible; impact skipped.",
        "launcher-missing",
      );
    }
    const query =
      direction !== undefined && direction.trim() !== ""
        ? `${target} (${direction})`
        : target;
    try {
      const raw = await callGraftTool(gated.mcp, gated.findCode, { query });
      return { status: "ok", summary: toSummary(raw) };
    } catch (err) {
      return callFailed(err, "impact");
    }
  } catch (err) {
    return skipped(
      `Graft impact unavailable; skipped (${
        err instanceof Error ? err.message : String(err)
      }).`,
      "call-failed",
    );
  }
}

/**
 * Post-change structural check (R1 Q1 A): the managed launcher's freshness
 * verdict is the change detection — a fresh graph means no structural drift;
 * stale/missing graphs are skipped, never advisory. With a scope hint, also
 * runs `graft_find_code` on the scope. Never throws.
 */
export async function detectChanges(
  _cwd: string,
  scope?: string,
  options: GraftOptions = {},
): Promise<AnalysisResult> {
  try {
    const gated = await gate(options, "detectChanges");
    if (!gated.ok) return gated.result;
    if (scope !== undefined && scope.trim() !== "" && gated.findCode != null) {
      try {
        const raw = await callGraftTool(gated.mcp, gated.findCode, { query: scope });
        return { status: "ok", summary: toSummary(raw) };
      } catch (err) {
        return callFailed(err, "detectChanges");
      }
    }
    return {
      status: "ok",
      summary: "Graft graph in sync with the code (freshness probe).",
    };
  } catch (err) {
    return skipped(
      `Graft detectChanges unavailable; skipped (${
        err instanceof Error ? err.message : String(err)
      }).`,
      "call-failed",
    );
  }
}
