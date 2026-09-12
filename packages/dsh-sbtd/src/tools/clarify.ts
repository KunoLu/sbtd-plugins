import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  type ClarifyMode,
  type ClarifyStatus,
  getSession,
  type SbtdSessionState,
} from "../state.js";
import {
  GATE_KINDS,
  type PlanToolExec,
  sbtdPlan,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";
import { sbtdReview } from "./review.js";

export const SBTD_CLARIFY_TOOL_NAME = "sbtd_clarify";

export const CLARIFY_MODES = ["docs", "generic"] as const;

export const GRILL_WITH_DOCS_FACT = "完整执行 grill-with-docs";

const DDD_STATUSES = ["confirmed", "needs-clarification", "blocked"] as const;

export type ClarifyInput = {
  mode?: string;
  reset?: boolean;
  question?: string;
  frontier_empty?: boolean;
  user_confirmed?: boolean;
  load_manuals?: boolean;
  ddd_status?: string;
  conclusions?: string;
};

export type ClarifyBlocked = {
  kind: "ddd-unconfirmed";
  resume: "not-clarify";
  suggestPrd: false;
  suggestImplement: false;
  reviewStatus: string | null;
};

export type ClarifyToolResult = {
  clarifyStatus: ClarifyStatus;
  mode: ClarifyMode | null;
  currentQuestion: string | null;
  blocked?: ClarifyBlocked;
  ddd?: {
    requirement: "required" | "on-demand";
    state: string;
    reviewStatus?: string;
    fact?: string;
  };
  manuals?: string;
};
/** Host-facing payload: mode/currentQuestion omitted when null (Q1B). */
export type ClarifyHostResult = Omit<
  ClarifyToolResult,
  "mode" | "currentQuestion"
> & {
  mode?: ClarifyMode;
  currentQuestion?: string;
};

export function toClarifyHostResult(
  result: ClarifyToolResult,
): ClarifyHostResult {
  const { mode, currentQuestion, ...rest } = result;
  return {
    ...rest,
    ...(mode === null ? {} : { mode }),
    ...(currentQuestion === null ? {} : { currentQuestion }),
  };
}

export type ClarifyToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: ClarifyHostResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (
    args: ClarifyInput,
    exec: PlanToolExec,
  ) => Promise<ClarifyHostResult>;
};

function isClarifyMode(value: string): value is ClarifyMode {
  return (CLARIFY_MODES as readonly string[]).includes(value);
}

function manualsRoot(): string {
  return join(dirname(fileURLToPath(import.meta.url)), "..", "..", "manuals");
}

function loadManual(id: string): string {
  return readFileSync(join(manualsRoot(), id, "SKILL.md"), "utf8");
}

function loadClarifyManuals(mode: ClarifyMode): string {
  if (mode === "docs") {
    return `${loadManual("grilling")}\n\n${loadManual("grill-with-docs")}`;
  }
  return `${loadManual("grilling")}\n\n${loadManual("grill-me")}`;
}

function priorFacts(sessionId: string): string[] {
  const plan = getSession(sessionId).plan;
  if (plan === undefined) {
    return [];
  }
  const facts: string[] = [];
  for (const kind of GATE_KINDS) {
    const fact = plan.gates[kind].fact;
    if (fact !== undefined) {
      facts.push(fact);
    }
  }
  return facts;
}

function elevateDocsDdd(sessionId: string): void {
  const session = getSession(sessionId);
  const plan = session.plan;
  if (plan === undefined) {
    return;
  }
  if (plan.gates.ddd.requirement === "required") {
    return;
  }
  sbtdPlan(sessionId, {
    task_summary: plan.summary,
    facts: [...priorFacts(sessionId), GRILL_WITH_DOCS_FACT],
  });
}

function recordDocsDdd(sessionId: string, input: ClarifyInput): void {
  const live = getSession(sessionId).plan?.gates.ddd.reviewStatus;
  let status: (typeof DDD_STATUSES)[number];
  if (input.ddd_status !== undefined) {
    if (!(DDD_STATUSES as readonly string[]).includes(input.ddd_status)) {
      throw new Error(
        `sbtd_clarify: ddd_status must be one of ${DDD_STATUSES.join(", ")}`,
      );
    }
    status = input.ddd_status as (typeof DDD_STATUSES)[number];
  } else if (live === "confirmed") {
    status = "confirmed";
  } else {
    status = "blocked";
  }
  sbtdReview(sessionId, {
    kind: "ddd",
    status,
    conclusions:
      input.conclusions ?? "Forced Docs DDD via sbtd_clarify Complete",
  });
}

function dddSnapshot(sessionId: string): ClarifyToolResult["ddd"] {
  const gate = getSession(sessionId).plan?.gates.ddd;
  if (gate === undefined) {
    return undefined;
  }
  const snapshot: NonNullable<ClarifyToolResult["ddd"]> = {
    requirement: gate.requirement,
    state: gate.state,
  };
  if (gate.reviewStatus !== undefined) {
    snapshot.reviewStatus = gate.reviewStatus;
  }
  if (gate.fact !== undefined) {
    snapshot.fact = gate.fact;
  }
  return snapshot;
}

function bindMode(
  session: SbtdSessionState,
  input: ClarifyInput,
): ClarifyMode | null {
  if (session.clarifyMode === undefined) {
    if (input.mode === undefined) {
      return null;
    }
    if (!isClarifyMode(input.mode)) {
      throw new Error("sbtd_clarify: mode must be docs or generic");
    }
    session.clarifyMode = input.mode;
    return input.mode;
  }
  if (input.mode !== undefined && input.mode !== session.clarifyMode) {
    throw new Error(
      `sbtd_clarify: Clarify Mode is bound to ${session.clarifyMode}; switch throws until Interview Reset`,
    );
  }
  return session.clarifyMode;
}

export function sbtdClarify(
  sessionId: string,
  input: ClarifyInput,
): ClarifyToolResult {
  if (input.question !== undefined && typeof input.question !== "string") {
    throw new Error("sbtd_clarify: question must be a single string");
  }

  const session = getSession(sessionId);

  if (input.reset === true) {
    delete session.clarifyMode;
    delete session.clarifyStatus;
    delete session.clarifyCompleteTaskId;
  } else if (session.clarifyStatus === "complete") {
    throw new Error(
      "sbtd_clarify: Clarify Complete is terminal; further sbtd_clarify is not the resume path. Pass reset to Interview Reset.",
    );
  }

  const mode = bindMode(session, input);
  const resetOnly =
    input.reset === true &&
    input.mode === undefined &&
    input.question === undefined &&
    input.frontier_empty !== true &&
    input.user_confirmed !== true &&
    input.load_manuals !== true;

  if (resetOnly) {
    return {
      clarifyStatus: "partial",
      mode: null,
      currentQuestion: null,
    };
  }

  if (mode === null) {
    throw new Error("sbtd_clarify: first call requires mode docs|generic");
  }

  const attemptingComplete =
    input.frontier_empty === true && input.user_confirmed === true;

  if (attemptingComplete) {
    if (session.plan === undefined) {
      throw new Error("尚未 sbtd_plan，请先调用 sbtd_plan。");
    }

    if (mode === "docs") {
      elevateDocsDdd(sessionId);
      recordDocsDdd(sessionId, input);
      session.clarifyCompleteTaskId = session.plan.taskId;
    }

    session.clarifyStatus = "complete";

    const ddd = dddSnapshot(sessionId);
    const result: ClarifyToolResult = {
      clarifyStatus: "complete",
      mode,
      currentQuestion: null,
    };
    if (ddd !== undefined) {
      result.ddd = ddd;
    }
    const requiredUnconfirmed =
      ddd?.requirement === "required" && ddd.reviewStatus !== "confirmed";
    if (requiredUnconfirmed) {
      result.blocked = {
        kind: "ddd-unconfirmed",
        resume: "not-clarify",
        suggestPrd: false,
        suggestImplement: false,
        reviewStatus: ddd.reviewStatus ?? null,
      };
    }
    return result;
  }

  session.clarifyStatus = "partial";
  const result: ClarifyToolResult = {
    clarifyStatus: "partial",
    mode,
    currentQuestion: input.question ?? null,
  };
  if (input.load_manuals === true) {
    result.manuals = loadClarifyManuals(mode);
  }
  return result;
}

export const SBTD_CLARIFY_DESCRIPTION =
  "Interview adapter (grilling). First call requires mode docs|generic; later omit inherits; a different mode throws until reset=true. Ask exactly one Current Question per call. Complete only when frontier_empty and user_confirmed are both true; loading manuals is not Complete. Partial does not need sbtd_plan. Complete requires a plan. docs Complete records Forced Docs DDD via sbtd_review kind=ddd and a grill-with-docs haystack fact; generic never auto-requires DDD. Complete is terminal.";

export function createClarifyTool(): ClarifyToolDefinition {
  return {
    name: SBTD_CLARIFY_TOOL_NAME,
    description: SBTD_CLARIFY_DESCRIPTION,
    parameters: {
      type: "object",
      properties: {
        mode: {
          type: "string",
          enum: [...CLARIFY_MODES],
          description:
            "Clarify Mode. Required on the first call; omit later to inherit.",
        },
        reset: {
          type: "boolean",
          description:
            "Interview Reset. Unbinds Clarify Mode in this session. Compaction is not Reset.",
        },
        question: {
          type: "string",
          description:
            "The single Current Question whose prerequisites are already settled.",
        },
        frontier_empty: {
          type: "boolean",
          description: "True when no frontier questions remain.",
        },
        user_confirmed: {
          type: "boolean",
          description:
            "True when the user explicitly confirmed shared understanding.",
        },
        load_manuals: {
          type: "boolean",
          description:
            "Load grilling manuals into the return. Loading manuals is not Complete.",
        },
        ddd_status: {
          type: "string",
          enum: [...DDD_STATUSES],
          description:
            "Optional DDD reviewer status recorded on docs Complete via sbtdReview.",
        },
        conclusions: {
          type: "string",
          description:
            "Optional DDD conclusions returned only; not written to disk.",
        },
      },
      required: [],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          clarifyStatus: { type: "string" },
          mode: { type: "string" },
          currentQuestion: { type: "string" },
          blocked: { type: "object" },
          ddd: { type: "object" },
          manuals: { type: "string" },
        },
      },
      render(_args, value) {
        const lines = [
          `clarifyStatus: ${value.clarifyStatus}`,
          `mode: ${value.mode ?? ""}`,
        ];
        if (value.currentQuestion !== undefined) {
          lines.push(`currentQuestion: ${value.currentQuestion}`);
        }
        if (value.blocked !== undefined) {
          lines.push(
            "blocked: DDD not confirmed; do not suggest PRD or 实现; further sbtd_clarify is not the resume path.",
          );
        }
        if (value.manuals !== undefined) {
          lines.push("", value.manuals);
        }
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe() {
      return false;
    },
    async execute(args, exec) {
      return toClarifyHostResult(sbtdClarify(sessionIdFromExec(exec), args));
    },
  };
}

export function registerClarifyTool(ctx: ToolsHost): void {
  ctx.tools.register(createClarifyTool());
}
