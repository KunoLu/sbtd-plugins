/**
 * Shared draft path for sbtd_spec (prd.md) and sbtd_tickets (implement.md).
 *
 * PR-B (R1 Q2 A): the plugin never writes task files — no .trellis tree, no
 * docs/prd, no task.md. Both tools always return the markdown draft; the
 * caller (model or user) owns persistence.
 */

import { getSession } from "../state.js";

export type ArtifactBlocked = {
  kind: "ddd-unconfirmed";
  resume: "not-clarify";
  suggestPrd: false;
  suggestImplement: false;
  reviewStatus: string | null;
};

export type ArtifactMode = "draft" | "blocked";

export type ArtifactToolResult = {
  ok: boolean;
  mode: ArtifactMode;
  artifact: "prd.md" | "implement.md";
  markdown: string;
  note?: string;
  blocked?: ArtifactBlocked;
};

export type ArtifactInput = {
  markdown?: string;
  body?: string;
};

export const DRAFT_ONLY_NOTE =
  "Draft-only (R1 Q2 A): the plugin writes no task files (.trellis backend removed); persist the draft yourself if needed.";

/**
 * Draft-only path (R1 Q2 A). Empty/whitespace content still throws so a
 * missing body is never mistaken for a delivered draft.
 */
export function runTaskArtifact(
  sessionId: string,
  artifact: "prd.md" | "implement.md",
  input: ArtifactInput,
): ArtifactToolResult {
  const markdown =
    typeof input.markdown === "string"
      ? input.markdown
      : typeof input.body === "string"
        ? input.body
        : "";
  if (markdown.trim() === "") {
    throw new Error(
      "sbtd_spec/sbtd_tickets: markdown/body must be a non-empty string",
    );
  }
  const gate = getSession(sessionId).plan?.gates.ddd;
  if (gate?.requirement === "required" && gate.reviewStatus !== "confirmed") {
    return {
      ok: false,
      mode: "blocked",
      artifact,
      markdown,
      note: "DDD required but not confirmed; do not proceed to PRD or implementation.",
      blocked: {
        kind: "ddd-unconfirmed",
        resume: "not-clarify",
        suggestPrd: false,
        suggestImplement: false,
        reviewStatus: gate.reviewStatus ?? null,
      },
    };
  }
  return {
    ok: true,
    mode: "draft",
    artifact,
    markdown,
    note: DRAFT_ONLY_NOTE,
  };
}
