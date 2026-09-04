import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { type GateState, getSession } from "../state.js";
import {
  type PlanToolExec,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";

export const SBTD_REVIEW_TOOL_NAME = "sbtd_review";

export const REVIEW_KINDS = [
  "legacy",
  "refactor",
  "ddd",
  "ddia",
  "release",
] as const;

export type ReviewKind = (typeof REVIEW_KINDS)[number];

export const REVIEW_TITLES: Record<ReviewKind, string> = {
  legacy: "Legacy Change Safety Review",
  refactor: "Refactoring Review",
  ddd: "DDD Boundary Review",
  ddia: "DDIA Data Design Review",
  release: "Release Readiness Review",
};

const MANUAL_ID: Record<ReviewKind, string> = {
  legacy: "book-legacy-change-safety",
  refactor: "book-refactoring-pass",
  ddd: "book-ddd-distilled-modeling",
  ddia: "book-ddia-data-design",
  release: "book-release-readiness",
};

const REVIEW_STATUSES: Record<ReviewKind, readonly string[]> = {
  legacy: ["characterized", "needs-safety-net", "seam-required", "blocked"],
  refactor: ["proceed", "refactor-first", "blocked"],
  ddd: ["confirmed", "needs-clarification", "blocked"],
  ddia: ["confirmed", "needs-design-change", "blocked"],
  release: ["ready", "needs-mitigation", "blocked"],
};

const PASS_STATUS: Record<string, true> = {
  characterized: true,
  proceed: true,
  confirmed: true,
  ready: true,
};

const RUNNING_STATUS: Record<string, true> = {
  "needs-safety-net": true,
  "needs-clarification": true,
  "needs-design-change": true,
  "needs-mitigation": true,
  "seam-required": true,
  "refactor-first": true,
};

export type ReviewInput = {
  kind: string;
  status: string;
  conclusions?: string;
};

export type ReviewToolResult = {
  title: string;
  kind: ReviewKind;
  reviewStatus: string;
  requirement: "required" | "on-demand";
  state: GateState;
  conclusions: string;
  markdown: string;
  manual: string;
};

export type ReviewToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: ReviewToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (args: ReviewInput, exec: PlanToolExec) => Promise<ReviewToolResult>;
};

function isReviewKind(value: string): value is ReviewKind {
  return (REVIEW_KINDS as readonly string[]).includes(value);
}

function mapGateState(status: string): GateState {
  if (PASS_STATUS[status] === true) {
    return "passed";
  }
  if (status === "blocked") {
    return "blocked";
  }
  if (RUNNING_STATUS[status] === true) {
    return "running";
  }
  throw new Error(`sbtd_review: unmapped status ${status}`);
}

export function loadReviewManual(kind: ReviewKind): string {
  const manualsRoot = join(
    dirname(fileURLToPath(import.meta.url)),
    "..",
    "..",
    "manuals",
  );
  return readFileSync(join(manualsRoot, MANUAL_ID[kind], "SKILL.md"), "utf8");
}

export function sbtdReview(
  sessionId: string,
  input: ReviewInput,
): ReviewToolResult {
  if (!isReviewKind(input.kind)) {
    throw new Error(
      `sbtd_review: kind must be one of ${REVIEW_KINDS.join(", ")}`,
    );
  }
  const kind = input.kind;
  const allowed = REVIEW_STATUSES[kind];
  if (!allowed.includes(input.status)) {
    throw new Error(
      `sbtd_review: status for ${kind} must be one of ${allowed.join(", ")}`,
    );
  }
  const status = input.status;

  const manual = loadReviewManual(kind);
  const session = getSession(sessionId);
  if (session.plan === undefined) {
    throw new Error("尚未 sbtd_plan，请先调用 sbtd_plan。");
  }

  const gate = session.plan.gates[kind];
  gate.state = mapGateState(status);
  gate.reviewStatus = status;

  const conclusions = input.conclusions ?? "";
  const title = REVIEW_TITLES[kind];
  const markdown = [
    `# ${title}`,
    `Status: ${status}`,
    `requirement: ${gate.requirement}`,
    `state: ${gate.state}`,
    "",
    conclusions,
  ].join("\n");

  return {
    title,
    kind,
    reviewStatus: status,
    requirement: gate.requirement,
    state: gate.state,
    conclusions,
    markdown,
    manual,
  };
}

export const SBTD_REVIEW_DESCRIPTION =
  "Record a book-gate review. kind is legacy|refactor|ddd|ddia|release only (no skill ids or aliases). status is the source-skill reviewer enum. Without a plan, call sbtd_plan first. Does not change requirement.";

export function createReviewTool(): ReviewToolDefinition {
  return {
    name: SBTD_REVIEW_TOOL_NAME,
    description: SBTD_REVIEW_DESCRIPTION,
    parameters: {
      type: "object",
      properties: {
        kind: {
          type: "string",
          enum: [...REVIEW_KINDS],
          description:
            "Book gate kind. Exactly legacy, refactor, ddd, ddia, or release.",
        },
        status: {
          type: "string",
          description:
            "Reviewer status from the loaded SKILL.md enum for that kind.",
        },
        conclusions: {
          type: "string",
          description:
            "Review conclusions. Returned only; not written to disk.",
        },
      },
      required: ["kind", "status"],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          title: { type: "string" },
          kind: { type: "string" },
          reviewStatus: { type: "string" },
          requirement: { type: "string" },
          state: { type: "string" },
          conclusions: { type: "string" },
          markdown: { type: "string" },
          manual: { type: "string" },
        },
      },
      render(_args, value) {
        return [{ type: "text", text: `${value.markdown}\n\n${value.manual}` }];
      },
    },
    isConcurrencySafe() {
      return false;
    },
    async execute(args, exec) {
      return sbtdReview(sessionIdFromExec(exec), args);
    },
  };
}

export function registerReviewTool(ctx: ToolsHost): void {
  ctx.tools.register(createReviewTool());
}
