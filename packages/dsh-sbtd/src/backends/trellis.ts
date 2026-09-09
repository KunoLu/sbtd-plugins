import {
  accessSync,
  constants,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { delimiter, isAbsolute, join, resolve, sep } from "node:path";

export type DetectResult = {
  exists: boolean;
  cliOnPath: boolean;
  workflowPresent: boolean;
};

export type ReadWorkflowResult =
  | { ok: true; content: string }
  | { ok: false; reason: "missing-trellis" | "missing-workflow" };

export type CurrentTaskResult =
  | { ok: true; task: string }
  | { ok: false; reason: "no-session" | "no-current-task" | "missing-trellis" };

export type WriteArtifactResult =
  | { ok: true; path: string }
  | { ok: false; reason: "missing-trellis" };

export const WRITE_ARTIFACT_NAMES = [
  "prd.md",
  "design.md",
  "implement.md",
] as const;
export type WriteArtifactName = (typeof WRITE_ARTIFACT_NAMES)[number];

const SAFE_SLUG = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

function trellisDir(cwd: string): string {
  return join(cwd, ".trellis");
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

/** PATH which for `trellis` — the only use of the binary in T7 (Q2B). */
export function isTrellisOnPath(env: NodeJS.ProcessEnv = process.env): boolean {
  const pathEnv = env.PATH ?? env.Path ?? "";
  if (!pathEnv) return false;
  const exts =
    process.platform === "win32"
      ? (env.PATHEXT ?? ".EXE;.CMD;.BAT;.COM").split(";").filter(Boolean)
      : [""];
  for (const dir of pathEnv.split(delimiter)) {
    if (!dir) continue;
    for (const ext of exts) {
      const candidate = join(dir, `trellis${ext}`);
      try {
        accessSync(candidate, constants.X_OK);
        const st = statSync(candidate);
        if (st.isFile()) return true;
      } catch {
        // keep looking
      }
    }
  }
  return false;
}

export function detect(
  cwd: string,
  env: NodeJS.ProcessEnv = process.env,
): DetectResult {
  const root = trellisDir(cwd);
  const exists = isDirectory(root);
  let cliOnPath = false;
  try {
    cliOnPath = isTrellisOnPath(env);
  } catch {
    cliOnPath = false;
  }
  const workflowPresent = isReadableFile(join(root, "workflow.md"));
  return { exists, cliOnPath, workflowPresent };
}

export function readWorkflow(cwd: string): ReadWorkflowResult {
  const root = trellisDir(cwd);
  if (!isDirectory(root)) {
    return { ok: false, reason: "missing-trellis" };
  }
  const workflowPath = join(root, "workflow.md");
  if (!isReadableFile(workflowPath)) {
    return { ok: false, reason: "missing-workflow" };
  }
  try {
    const content = readFileSync(workflowPath, "utf8");
    return { ok: true, content };
  } catch {
    return { ok: false, reason: "missing-workflow" };
  }
}

function sanitizeKey(value: string): string {
  const cleaned = value
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned.slice(0, 200);
}

/** Resolve Trellis session file stem from optional arg and/or env (Q4A). */
export function resolveSessionKey(
  sessionKey?: string | null,
  env: NodeJS.ProcessEnv = process.env,
): string | null {
  if (sessionKey != null && String(sessionKey).trim() !== "") {
    const key = sanitizeKey(String(sessionKey));
    return key || null;
  }
  const trellisCtx = env.TRELLIS_CONTEXT_ID?.trim();
  if (trellisCtx) {
    const safe = sanitizeKey(trellisCtx);
    return safe || null;
  }
  return null;
}

export function currentTask(
  cwd: string,
  sessionKey?: string | null,
  env: NodeJS.ProcessEnv = process.env,
): CurrentTaskResult {
  const root = trellisDir(cwd);
  if (!isDirectory(root)) {
    return { ok: false, reason: "missing-trellis" };
  }
  const key = resolveSessionKey(sessionKey, env);
  if (!key) {
    return { ok: false, reason: "no-session" };
  }
  const sessionPath = join(root, ".runtime", "sessions", `${key}.json`);
  if (!isReadableFile(sessionPath)) {
    return { ok: false, reason: "no-current-task" };
  }
  try {
    const raw = readFileSync(sessionPath, "utf8");
    const data = JSON.parse(raw) as { current_task?: unknown };
    const task = data.current_task;
    if (typeof task !== "string" || task.trim() === "") {
      return { ok: false, reason: "no-current-task" };
    }
    return { ok: true, task: task.trim() };
  } catch {
    return { ok: false, reason: "no-current-task" };
  }
}

function assertSafeSlug(task: string): string {
  if (typeof task !== "string" || task.trim() === "") {
    throw new Error("writeArtifact: task slug rejected (empty)");
  }
  const slug = task.trim();
  if (
    isAbsolute(slug) ||
    slug.includes("\\") ||
    slug.includes("/") ||
    slug.includes("..")
  ) {
    throw new Error(`writeArtifact: task slug rejected (escape): ${task}`);
  }
  if (slug === "archive" || slug.startsWith("archive.")) {
    throw new Error(`writeArtifact: task slug rejected (archive): ${task}`);
  }
  if (!SAFE_SLUG.test(slug)) {
    throw new Error(`writeArtifact: task slug rejected (unsafe): ${task}`);
  }
  return slug;
}

function assertWhitelistName(name: string): WriteArtifactName {
  if ((WRITE_ARTIFACT_NAMES as readonly string[]).includes(name)) {
    return name as WriteArtifactName;
  }
  throw new Error(`writeArtifact: name rejected (not whitelisted): ${name}`);
}

export function writeArtifact(
  cwd: string,
  task: string,
  name: string,
  body: string,
): WriteArtifactResult {
  const root = trellisDir(cwd);
  if (!isDirectory(root)) {
    return { ok: false, reason: "missing-trellis" };
  }

  const slug = assertSafeSlug(task);
  const artifactName = assertWhitelistName(name);

  const tasksRoot = resolve(root, "tasks");
  const taskDir = resolve(tasksRoot, slug);
  const target = resolve(taskDir, artifactName);

  const tasksRootWithSep = tasksRoot.endsWith(sep)
    ? tasksRoot
    : tasksRoot + sep;
  if (!taskDir.startsWith(tasksRootWithSep) && taskDir !== tasksRoot) {
    throw new Error(`writeArtifact: sandbox escape (taskDir): ${task}`);
  }
  const taskDirWithSep = taskDir.endsWith(sep) ? taskDir : taskDir + sep;
  if (!target.startsWith(taskDirWithSep) && target !== taskDir) {
    throw new Error(`writeArtifact: sandbox escape (target): ${name}`);
  }

  mkdirSync(taskDir, { recursive: true });
  writeFileSync(target, body, "utf8");
  return { ok: true, path: target };
}
