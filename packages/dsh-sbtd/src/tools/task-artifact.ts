import {
  currentTask,
  detect,
  type DetectResult,
  writeArtifact,
  type WriteArtifactName,
} from "../backends/trellis.js";
import { getSession } from "../state.js";

/** Same SAFE_SLUG shape as T7 writeArtifact (do not reopen T7). */
const SAFE_SLUG = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const POINTER_PREFIX = ".trellis/tasks/";

export type ArtifactBlocked = {
  kind: "ddd-unconfirmed";
  resume: "not-clarify";
  suggestPrd: false;
  suggestImplement: false;
  reviewStatus: string | null;
};

export type ArtifactMode = "written" | "draft" | "blocked";

export type ArtifactToolResult = {
  ok: boolean;
  mode: ArtifactMode;
  artifact: WriteArtifactName;
  markdown: string;
  path?: string;
  slug?: string | null;
  note?: string;
  blocked?: ArtifactBlocked;
  detect?: DetectResult;
  source?: "explicit" | "pointer" | null;
};

export type ArtifactInput = {
  markdown?: string;
  body?: string;
  task?: string;
  cwd?: string;
  session_key?: string;
};

function isSafeSlug(slug: string): boolean {
  if (slug === "" || slug === "archive" || slug.startsWith("archive.")) {
    return false;
  }
  if (
    slug.includes("/") ||
    slug.includes("\\") ||
    slug.includes("..") ||
    slug.startsWith("/")
  ) {
    return false;
  }
  return SAFE_SLUG.test(slug);
}

/** Strip `.trellis/tasks/` from a currentTask pointer → safe slug, or null if invalid. */
export function slugFromPointer(pointer: string): string | null {
  const p = pointer.trim();
  if (!p.startsWith(POINTER_PREFIX)) {
    return null;
  }
  const rest = p.slice(POINTER_PREFIX.length);
  if (!isSafeSlug(rest)) {
    return null;
  }
  return rest;
}

export function resolveWriteSlug(
  explicit: string | undefined,
  cwd: string,
  sessionKey?: string | null,
  env: NodeJS.ProcessEnv = process.env,
):
  | { ok: true; slug: string; source: "explicit" | "pointer" }
  | { ok: false; reason: string } {
  if (explicit != null && String(explicit).trim() !== "") {
    const slug = String(explicit).trim();
    if (!isSafeSlug(slug)) {
      return { ok: false, reason: "invalid-explicit-task" };
    }
    return { ok: true, slug, source: "explicit" };
  }
  const ct = currentTask(cwd, sessionKey, env);
  if (!ct.ok) {
    return { ok: false, reason: ct.reason };
  }
  const slug = slugFromPointer(ct.task);
  if (slug == null) {
    return { ok: false, reason: "invalid-pointer" };
  }
  return { ok: true, slug, source: "pointer" };
}

/** Q2A: required ddd ∧ reviewStatus≠confirmed ⇒ refuse write (mirror clarify). */
export function dddUnconfirmedBlock(
  sessionId: string,
): ArtifactBlocked | null {
  const gate = getSession(sessionId).plan?.gates.ddd;
  if (gate === undefined) {
    return null;
  }
  if (gate.requirement === "required" && gate.reviewStatus !== "confirmed") {
    return {
      kind: "ddd-unconfirmed",
      resume: "not-clarify",
      suggestPrd: false,
      suggestImplement: false,
      reviewStatus: gate.reviewStatus ?? null,
    };
  }
  return null;
}

function bodyFromInput(input: ArtifactInput): string {
  if (typeof input.markdown === "string") {
    return input.markdown;
  }
  if (typeof input.body === "string") {
    return input.body;
  }
  return "";
}

/**
 * Shared write/draft path for sbtd_spec (prd.md) and sbtd_tickets (implement.md).
 * Locks: Q1C Q2A Q3A Q4A Q6A.
 */
export function runTaskArtifact(
  sessionId: string,
  artifact: "prd.md" | "implement.md",
  input: ArtifactInput,
  env: NodeJS.ProcessEnv = process.env,
): ArtifactToolResult {
  const markdown = bodyFromInput(input);
  // Reject missing/empty/whitespace-only content before any draft or write path
  // so we never silently overwrite existing prd.md / implement.md with "".
  // Throw (not draft) matches sibling tools e.g. sbtd_plan empty task_summary.
  if (markdown.trim() === "") {
    throw new Error(
      "sbtd_spec/sbtd_tickets: markdown/body must be a non-empty string",
    );
  }
  const cwd =
    input.cwd != null && String(input.cwd).trim() !== ""
      ? String(input.cwd).trim()
      : process.cwd();
  const sessionKey =
    input.session_key != null && String(input.session_key).trim() !== ""
      ? String(input.session_key).trim()
      : null;

  const blocked = dddUnconfirmedBlock(sessionId);
  if (blocked !== null) {
    return {
      ok: false,
      mode: "blocked",
      artifact,
      markdown,
      slug: null,
      source: null,
      note: "DDD required but not confirmed; refuse write (blocked.kind=ddd-unconfirmed).",
      blocked,
    };
  }

  const detected = detect(cwd, env);
  const resolved = resolveWriteSlug(input.task, cwd, sessionKey, env);

  // Q3A: draft-only when exists=false; cliOnPath/workflowPresent ignored.
  if (!detected.exists) {
    return {
      ok: true,
      mode: "draft",
      artifact,
      markdown,
      slug: resolved.ok ? resolved.slug : null,
      source: resolved.ok ? resolved.source : null,
      detect: detected,
      note:
        "No .trellis/ directory (detect.exists=false). Returning markdown draft only; never write under docs/; do not trellis init.",
    };
  }

  // Q6A: no usable slug ⇒ draft + structured note, no disk, no throw.
  if (!resolved.ok) {
    return {
      ok: true,
      mode: "draft",
      artifact,
      markdown,
      slug: null,
      source: null,
      detect: detected,
      note: `Undetermined task path (${resolved.reason}). Returning markdown draft only; no disk write.`,
    };
  }

  const written = writeArtifact(cwd, resolved.slug, artifact, markdown);
  if (!written.ok) {
    return {
      ok: true,
      mode: "draft",
      artifact,
      markdown,
      slug: resolved.slug,
      source: resolved.source,
      detect: detected,
      note: `writeArtifact failed (${written.reason}). Returning markdown draft only; never write under docs/.`,
    };
  }

  return {
    ok: true,
    mode: "written",
    artifact,
    markdown,
    path: written.path,
    slug: resolved.slug,
    source: resolved.source,
    detect: detected,
  };
}
