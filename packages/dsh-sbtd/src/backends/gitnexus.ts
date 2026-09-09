/**
 * GitNexus backend (T9) — optional analysis primitives over MCP + `.gitnexus/`.
 *
 * Locks: Q1B/Q2A/Q3A/Q4A/Q5A/Q6A.
 * Never throws for unavailability. Never writes user MCP config.
 */

import { spawn, spawnSync } from "node:child_process";
import { accessSync, constants, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

export type DetectResult = {
  mcpVisible: boolean;
  indexPresent: boolean;
  stale: boolean;
};

export type AnalysisResult = {
  status: "ok" | "skipped" | "advisory";
  summary: string;
  advisory?: true;
  reason?: string;
};

/** Injectable MCP surface for Cordis/DSH tool names + calls (Q6A). */
export type McpClient = {
  listToolNames: () => Iterable<string> | Promise<Iterable<string>>;
  callTool: (
    name: string,
    args: Record<string, unknown>,
  ) => Promise<unknown>;
};

export type RefreshResult = {
  ok: boolean;
  detail?: string;
};

export type GitNexusOptions = {
  /** MCP server id; default `"gitnexus"` (Q6A). */
  serverName?: string;
  /** Injected MCP client (production host / tests). */
  mcp?: McpClient | null;
  /**
   * Optional pre-listed tool names for detect without a full client.
   * Ignored for callTool — impact/detectChanges still need `mcp`.
   */
  toolNames?: Iterable<string>;
  /** Best-effort refresh timeout (Q4A). Default 120s. */
  refreshTimeoutMs?: number;
  /** Test / host override for project refresh. */
  runRefresh?: (cwd: string) => Promise<RefreshResult>;
  /** Test override for HEAD SHA. */
  resolveHead?: (cwd: string) => string | null;
  /** Test override for indexed commit from `.gitnexus/`. */
  resolveIndexedCommit?: (cwd: string) => string | null;
};

const DEFAULT_SERVER = "gitnexus";
const DEFAULT_REFRESH_TIMEOUT_MS = 120_000;

function gitnexusDir(cwd: string): string {
  return join(cwd, ".gitnexus");
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function isReadableFile(path: string): boolean {
  try {
    accessSync(path, constants.R_OK);
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** Form Cordis-style tool names for a server (Q6A). */
export function formToolNames(serverName: string = DEFAULT_SERVER): {
  impact: string;
  detectChanges: string;
} {
  return {
    impact: `mcp__${serverName}__impact`,
    detectChanges: `mcp__${serverName}__detect_changes`,
  };
}

async function listedToolSet(options: GitNexusOptions): Promise<Set<string>> {
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
 * Resolve impact / detect_changes tool names: configured serverName first,
 * then fallback `mcp__gitnexus__*` (Q6A).
 */
export async function resolveAnalysisTools(
  options: GitNexusOptions = {},
): Promise<{
  impact: string | null;
  detectChanges: string | null;
  mcpVisible: boolean;
}> {
  const serverName = options.serverName ?? DEFAULT_SERVER;
  const names = await listedToolSet(options);
  const primary = formToolNames(serverName);
  const fallback = formToolNames(DEFAULT_SERVER);

  const impact = names.has(primary.impact)
    ? primary.impact
    : names.has(fallback.impact)
      ? fallback.impact
      : null;
  const detectChanges = names.has(primary.detectChanges)
    ? primary.detectChanges
    : names.has(fallback.detectChanges)
      ? fallback.detectChanges
      : null;

  return {
    impact,
    detectChanges,
    mcpVisible: impact != null || detectChanges != null,
  };
}

function readIndexedCommit(cwd: string): string | null {
  for (const name of ["meta.json", "gitnexus.json"] as const) {
    const path = join(gitnexusDir(cwd), name);
    if (!isReadableFile(path)) continue;
    try {
      const data = JSON.parse(readFileSync(path, "utf8")) as {
        lastCommit?: unknown;
      };
      if (typeof data.lastCommit === "string" && data.lastCommit.trim()) {
        return data.lastCommit.trim();
      }
    } catch {
      // try next file
    }
  }
  return null;
}

function readHeadSha(cwd: string): string | null {
  try {
    const result = spawnSync("git", ["rev-parse", "HEAD"], {
      cwd,
      encoding: "utf8",
      timeout: 5_000,
    });
    if (result.status === 0 && typeof result.stdout === "string") {
      const sha = result.stdout.trim();
      return sha || null;
    }
    return null;
  } catch {
    return null;
  }
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
 * Best-effort project refresh (Q4A):
 * `node .gitnexus/run.cjs analyze` if present, else `gitnexus analyze`.
 * Never writes MCP config.
 */
export function defaultRunRefresh(
  cwd: string,
  timeoutMs: number = DEFAULT_REFRESH_TIMEOUT_MS,
): Promise<RefreshResult> {
  const runCjs = join(gitnexusDir(cwd), "run.cjs");
  const useRunCjs = isReadableFile(runCjs);
  const command = useRunCjs ? process.execPath : "gitnexus";
  const args = useRunCjs ? [runCjs, "analyze"] : ["analyze"];

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result: RefreshResult) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };

    let child;
    try {
      child = spawn(command, args, {
        cwd,
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
      });
    } catch (err) {
      finish({
        ok: false,
        detail: err instanceof Error ? err.message : String(err),
      });
      return;
    }

    let stderr = "";
    child.stderr?.setEncoding("utf8");
    child.stderr?.on("data", (chunk: string) => {
      stderr += chunk;
    });

    const timer = setTimeout(() => {
      try {
        child.kill("SIGTERM");
      } catch {
        // ignore
      }
      finish({ ok: false, detail: `refresh timed out after ${timeoutMs}ms` });
    }, timeoutMs);

    child.on("error", (err) => {
      clearTimeout(timer);
      finish({ ok: false, detail: err.message });
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) {
        finish({ ok: true });
      } else {
        const detail =
          stderr.trim() ||
          `refresh exited with code ${code == null ? "null" : code}`;
        finish({ ok: false, detail });
      }
    });
  });
}

/**
 * Probe MCP visibility, `.gitnexus/` presence, and index freshness (Q1B).
 * Fields are independent. Never throws.
 */
export async function detect(
  cwd: string,
  options: GitNexusOptions = {},
): Promise<DetectResult> {
  try {
    const indexPresent = isDirectory(gitnexusDir(cwd));
    const { mcpVisible } = await resolveAnalysisTools(options);

    let stale = false;
    if (indexPresent) {
      const indexed =
        options.resolveIndexedCommit?.(cwd) ?? readIndexedCommit(cwd);
      const head = options.resolveHead?.(cwd) ?? readHeadSha(cwd);
      // Present index that cannot be verified against HEAD, or mismatches → stale.
      if (!indexed || !head || indexed !== head) {
        stale = true;
      }
    }

    return { mcpVisible, indexPresent, stale };
  } catch {
    return { mcpVisible: false, indexPresent: false, stale: false };
  }
}

async function ensureRefreshIfStale(
  cwd: string,
  stale: boolean,
  options: GitNexusOptions,
): Promise<{ refreshFailed: boolean; detail?: string }> {
  if (!stale) return { refreshFailed: false };
  const timeout = options.refreshTimeoutMs ?? DEFAULT_REFRESH_TIMEOUT_MS;
  const runner =
    options.runRefresh ??
    ((dir: string) => defaultRunRefresh(dir, timeout));
  try {
    const result = await runner(cwd);
    if (result.ok) return { refreshFailed: false };
    return { refreshFailed: true, detail: result.detail ?? "refresh failed" };
  } catch (err) {
    return {
      refreshFailed: true,
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}

function skipped(
  summary: string,
  reason: string,
): AnalysisResult {
  return { status: "skipped", summary, reason };
}

/**
 * Pre-change impact analysis (Q3A / Q2A / Q4A). Never throws.
 */
export async function impact(
  cwd: string,
  target: string,
  direction?: string,
  options: GitNexusOptions = {},
): Promise<AnalysisResult> {
  try {
    const d = await detect(cwd, options);
    if (!d.mcpVisible) {
      return skipped(
        "GitNexus MCP tools not visible; impact skipped.",
        "mcp-unavailable",
      );
    }
    if (!d.indexPresent) {
      return skipped(
        "No .gitnexus/ index; impact skipped.",
        "index-missing",
      );
    }

    const { refreshFailed, detail: refreshDetail } = await ensureRefreshIfStale(
      cwd,
      d.stale,
      options,
    );

    const tools = await resolveAnalysisTools(options);
    if (!tools.impact || !options.mcp) {
      return skipped(
        "GitNexus impact tool not callable; skipped.",
        "mcp-unavailable",
      );
    }

    let summary: string;
    try {
      const args: Record<string, unknown> = { target };
      if (direction !== undefined) args.direction = direction;
      const raw = await options.mcp.callTool(tools.impact, args);
      summary = toSummary(raw);
    } catch (err) {
      return {
        status: "advisory",
        summary: `GitNexus impact failed: ${
          err instanceof Error ? err.message : String(err)
        }`,
        advisory: true,
        reason: "mcp-call-failed",
      };
    }

    if (refreshFailed) {
      return {
        status: "advisory",
        summary: `${summary}\n\n(advisory: index was stale and refresh failed${
          refreshDetail ? `: ${refreshDetail}` : ""
        }; treat as non-authoritative)`,
        advisory: true,
        reason: "stale-refresh-failed",
      };
    }

    return { status: "ok", summary };
  } catch (err) {
    return skipped(
      `GitNexus impact unavailable; skipped (${
        err instanceof Error ? err.message : String(err)
      }).`,
      "unexpected",
    );
  }
}

/**
 * Post-change detect_changes analysis (Q3A / Q2A / Q4A). Never throws.
 */
export async function detectChanges(
  cwd: string,
  scope?: string,
  options: GitNexusOptions = {},
): Promise<AnalysisResult> {
  try {
    const d = await detect(cwd, options);
    if (!d.mcpVisible) {
      return skipped(
        "GitNexus MCP tools not visible; detectChanges skipped.",
        "mcp-unavailable",
      );
    }
    if (!d.indexPresent) {
      return skipped(
        "No .gitnexus/ index; detectChanges skipped.",
        "index-missing",
      );
    }

    const { refreshFailed, detail: refreshDetail } = await ensureRefreshIfStale(
      cwd,
      d.stale,
      options,
    );

    const tools = await resolveAnalysisTools(options);
    if (!tools.detectChanges || !options.mcp) {
      return skipped(
        "GitNexus detect_changes tool not callable; skipped.",
        "mcp-unavailable",
      );
    }

    let summary: string;
    try {
      const args: Record<string, unknown> = {};
      if (scope !== undefined) args.scope = scope;
      const raw = await options.mcp.callTool(tools.detectChanges, args);
      summary = toSummary(raw);
    } catch (err) {
      return {
        status: "advisory",
        summary: `GitNexus detect_changes failed: ${
          err instanceof Error ? err.message : String(err)
        }`,
        advisory: true,
        reason: "mcp-call-failed",
      };
    }

    if (refreshFailed) {
      return {
        status: "advisory",
        summary: `${summary}\n\n(advisory: index was stale and refresh failed${
          refreshDetail ? `: ${refreshDetail}` : ""
        }; treat as non-authoritative)`,
        advisory: true,
        reason: "stale-refresh-failed",
      };
    }

    return { status: "ok", summary };
  } catch (err) {
    return skipped(
      `GitNexus detectChanges unavailable; skipped (${
        err instanceof Error ? err.message : String(err)
      }).`,
      "unexpected",
    );
  }
}
