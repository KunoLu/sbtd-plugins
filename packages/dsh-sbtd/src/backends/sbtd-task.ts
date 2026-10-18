/**
 * sbtd-task read-only layer (PR-B) — workflow_mode layered lookup.
 *
 * Locks: R1 Q4 (A+B layered), R2 Q6 B, R3 Q4 A.
 * The plugin NEVER writes task files — TaskStore is the only writer. This
 * module only reads `.sbtd/active-task.json` and the pointed task.md, and
 * never rejects plugin load: every failure degrades to `default` + note.
 */

import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, readFileSync, realpathSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";

export const WORKFLOW_MODES = ["strict", "default", "lite"] as const;
export type WorkflowMode = (typeof WORKFLOW_MODES)[number];

/** Resolution layer that produced the mode (R1 Q4 来源层). */
export type WorkflowModeSource = "param" | "host" | "task-file" | "default";

export type WorkflowModeResolution = {
  mode: WorkflowMode;
  source: WorkflowModeSource;
  /** Present when a layer failed or the task belongs to another branch. */
  note?: string;
};

export type WorkflowModeLookup = {
  /** Tool argument `workflow_mode` (model-visible on plan/review/validate). */
  param?: string | undefined;
  /** Host-injected `workflow_mode` (plugin host options). */
  host?: string | undefined;
  /** Project root for the `.sbtd` read; default `process.cwd()`. */
  cwd?: string | undefined;
  /**
   * Current branch override (tests / host). `undefined` probes git;
   * explicit `null` means "branch unknown" (comparison impossible).
   */
  currentBranch?: string | null | undefined;
};

const SOURCE_LABELS: Record<WorkflowModeSource, string> = {
  param: "工具参数",
  host: "宿主注入",
  "task-file": "任务文件",
  default: "缺省",
};

/** Human label for notices/status, e.g. `strict（来源：任务文件）`. */
export function describeWorkflowMode(resolution: WorkflowModeResolution): string {
  return `${resolution.mode}（来源：${SOURCE_LABELS[resolution.source]}）`;
}

function parseMode(
  value: string | undefined,
): { ok: true; mode: WorkflowMode } | { ok: false } {
  if (value == null) return { ok: false };
  const trimmed = value.trim();
  return (WORKFLOW_MODES as readonly string[]).includes(trimmed)
    ? { ok: true, mode: trimmed as WorkflowMode }
    : { ok: false };
}

/** Minimal frontmatter read: leading --- block, bare/quoted scalar values. */
function parseTaskFrontmatter(text: string): {
  workflowMode?: string;
  branch?: string | null;
} {
  const out: { workflowMode?: string; branch?: string | null } = {};
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/);
  if (lines[0] !== "---") return out;
  const end = lines.indexOf("---", 1);
  if (end === -1) return out;
  const seen = new Set<string>();
  for (const line of lines.slice(1, end)) {
    const match = /^(workflow_mode|branch):[ \t]*(.*)$/.exec(line);
    if (match?.[1] === undefined || match[2] === undefined) continue;
    if (seen.has(match[1])) return {};
    seen.add(match[1]);
    let value = match[2].trim();
    const quoted = value.startsWith('"') || value.startsWith("'");
    if (quoted) {
      if (value.length < 2 || value.at(-1) !== value[0]) return {};
      value = value.slice(1, -1);
    }
    if (match[1] === "workflow_mode") {
      out.workflowMode = value;
    } else {
      out.branch = !quoted && (value === "" || value === "null" || value === "~")
        ? null
        : value;
    }
  }
  return seen.has("branch") ? out : {};
}

function probeCurrentBranch(cwd: string): string | null {
  try {
    const branch = spawnSync("git", ["branch", "--show-current"], {
      cwd,
      encoding: "utf8",
      timeout: 5000,
    });
    if (branch.error != null || branch.status !== 0) return null;
    const name = (branch.stdout ?? "").trim();
    if (name !== "") return name;
    const head = spawnSync("git", ["rev-parse", "HEAD"], {
      cwd,
      encoding: "utf8",
      timeout: 5000,
    });
    if (head.error != null || head.status !== 0) return null;
    const sha = (head.stdout ?? "").trim();
    return sha === "" ? null : `detached:${sha}`;
  } catch {
    return null;
  }
}

type TaskPathOutcome =
  | { ok: true; path: string }
  | { ok: false; reason: "missing-pointer" | "unsafe-path" | "missing-file" };

/** Resolve the active-task pointer to a verified-in-root task.md path. */
function resolveActiveTaskPath(cwd: string): TaskPathOutcome {
  const pointerPath = resolve(cwd, ".sbtd", "active-task.json");
  if (!existsSync(pointerPath)) {
    return { ok: false, reason: "missing-pointer" };
  }
  let taskPath: unknown;
  try {
    if (!lstatSync(resolve(cwd, ".sbtd")).isDirectory() ||
        !lstatSync(pointerPath).isFile()) {
      return { ok: false, reason: "unsafe-path" };
    }
    const parsed: unknown = JSON.parse(readFileSync(pointerPath, "utf8"));
    if (parsed !== null && typeof parsed === "object" && "task_path" in parsed) {
      taskPath = parsed.task_path;
    }
  } catch {
    return { ok: false, reason: "missing-pointer" };
  }
  if (typeof taskPath !== "string" || taskPath.trim() === "") {
    return { ok: false, reason: "missing-pointer" };
  }
  const trimmed = taskPath.trim();
  if (isAbsolute(trimmed) || trimmed.includes("\\") ||
      trimmed.split("/").some((part) => part === "." || part === "..") ||
      !/^(?:ai\/tasks|\.sbtd\/tasks)\/.+\/task\.md$/.test(trimmed)) {
    return { ok: false, reason: "unsafe-path" };
  }
  const abs = resolve(cwd, trimmed);
  const rel = relative(resolve(cwd), abs);
  if (rel === "" || rel.startsWith("..") || isAbsolute(rel)) {
    return { ok: false, reason: "unsafe-path" };
  }
  if (!existsSync(abs)) {
    return { ok: false, reason: "missing-file" };
  }
  try {
    let current = resolve(cwd);
    for (const part of trimmed.split("/")) {
      current = resolve(current, part);
      const stat = lstatSync(current);
      if (stat.isSymbolicLink() || (current === abs && !stat.isFile())) {
        return { ok: false, reason: "unsafe-path" };
      }
    }
    const realRoot = realpathSync(cwd);
    const realFile = realpathSync(abs);
    const realRel = relative(realRoot, realFile);
    if (realRel === "" || realRel.startsWith("..") || isAbsolute(realRel)) {
      return { ok: false, reason: "unsafe-path" };
    }
  } catch {
    return { ok: false, reason: "unsafe-path" };
  }
  return { ok: true, path: abs };
}

const TASK_LAYER_NOTES: Record<
  "missing-pointer" | "unsafe-path" | "missing-file",
  string
> = {
  "missing-pointer": ".sbtd/active-task.json 指针缺失或损坏",
  "unsafe-path": "active-task 指针路径不安全",
  "missing-file": "指针指向的 task.md 缺失",
};

/**
 * Layered workflow_mode lookup (R1 Q4): tool param → host injection →
 * active-task task.md (read-only, branch compared per R2 Q6 B) → default.
 * Every failure falls through with a note; never throws, never rejects load.
 */
export function resolveWorkflowMode(
  lookup: WorkflowModeLookup = {},
): WorkflowModeResolution {
  const notes: string[] = [];

  const param = parseMode(lookup.param);
  if (param.ok) {
    return { mode: param.mode, source: "param" };
  }
  if (lookup.param != null && lookup.param.trim() !== "") {
    notes.push(`工具参数 workflow_mode 无效：${JSON.stringify(lookup.param)}`);
  }

  const host = parseMode(lookup.host);
  if (host.ok) {
    const resolution: WorkflowModeResolution = { mode: host.mode, source: "host" };
    if (notes.length > 0) resolution.note = notes.join("；");
    return resolution;
  }
  if (lookup.host != null && lookup.host.trim() !== "") {
    notes.push(`宿主注入 workflow_mode 无效：${JSON.stringify(lookup.host)}`);
  }

  const cwd = lookup.cwd ?? process.cwd();
  const taskPath = resolveActiveTaskPath(cwd);
  if (!taskPath.ok) {
    notes.push(TASK_LAYER_NOTES[taskPath.reason]);
  } else {
    let frontmatter: { workflowMode?: string; branch?: string | null } = {};
    let readable = true;
    try {
      frontmatter = parseTaskFrontmatter(readFileSync(taskPath.path, "utf8"));
    } catch {
      readable = false;
    }
    if (!readable) {
      notes.push("指针指向的 task.md 不可读");
    } else {
      const taskMode = parseMode(frontmatter.workflowMode);
      if (!taskMode.ok) {
        notes.push("task.md 无有效 workflow_mode");
      } else {
        const current =
          lookup.currentBranch !== undefined
            ? lookup.currentBranch
            : probeCurrentBranch(cwd);
        if (current == null && frontmatter.branch != null) {
          notes.push("无法确定当前分支，未采用任务模式");
        } else if (current !== frontmatter.branch) {
          notes.push(
            `任务属于其他分支（任务分支 ${frontmatter.branch}，当前分支 ${current}）`,
          );
        } else {
          const resolution: WorkflowModeResolution = {
            mode: taskMode.mode,
            source: "task-file",
          };
          if (notes.length > 0) resolution.note = notes.join("；");
          return resolution;
        }
      }
    }
  }

  const resolution: WorkflowModeResolution = { mode: "default", source: "default" };
  if (notes.length > 0) resolution.note = notes.join("；");
  return resolution;
}
