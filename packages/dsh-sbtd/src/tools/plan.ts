import { createHash } from "node:crypto";
import { type BookGatePlan, type GateState, getSession } from "../state.js";

export const SBTD_PLAN_TOOL_NAME = "sbtd_plan";

export const GATE_KINDS = [
  "ddd",
  "ddia",
  "legacy",
  "refactor",
  "release",
] as const;

export type GateKind = (typeof GATE_KINDS)[number];

export type PlanInput = {
  task_summary: string;
  facts?: string[];
};

export type PlanToolResult = {
  plan: BookGatePlan;
  markdown: string;
};

export type PlanToolExec = {
  agent?: { id?: string };
};

export type PlanToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: PlanToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (args: PlanInput, exec: PlanToolExec) => Promise<PlanToolResult>;
};

export type ToolsHost = {
  tools: {
    register: (definition: { name: string }) => unknown;
  };
};

const DEFAULT_SESSION_ID = "default";

type InferredGate = {
  requirement: "required" | "on-demand";
  state: GateState;
  fact?: string;
};

const PREDICATES: Record<GateKind, { re: RegExp; fact: string }[]> = {
  ddd: [
    { re: /完整执行\s*grill-with-docs/i, fact: "完整执行 grill-with-docs" },
    { re: /completed\s+grill-with-docs/i, fact: "completed grill-with-docs" },
    {
      re: /fully?\s+executed\s+grill-with-docs/i,
      fact: "fully executed grill-with-docs",
    },
  ],
  ddia: [
    { re: /持久化/, fact: "持久化" },
    { re: /persist/i, fact: "persistence" },
    { re: /数据库/, fact: "数据库" },
    { re: /database|\bsql\b|\bschema\b/i, fact: "database/schema" },
    { re: /缓存|cache|\bredis\b/i, fact: "cache" },
    { re: /共享数据|shared data/i, fact: "共享数据" },
    { re: /异步/, fact: "异步数据流" },
    { re: /\basync\b/i, fact: "async data flow" },
    { re: /跨服务|cross[- ]service/i, fact: "跨服务数据流" },
    {
      re: /\bqueue\b|\bkafka\b|\bpubsub\b|event bus/i,
      fact: "queue/event bus",
    },
  ],
  legacy: [
    { re: /既有行为/, fact: "修既有行为" },
    { re: /existing behavio[u]?r/i, fact: "existing behavior" },
    { re: /bugfix|\bbug[- ]fix\b/i, fact: "bugfix" },
    { re: /弱测试|weak tests/i, fact: "弱测试" },
    { re: /行为不清|unclear behavio[u]?r/i, fact: "行为不清" },
    { re: /隐藏依赖|hidden dependenc/i, fact: "隐藏依赖" },
    { re: /高回归|high regression/i, fact: "高回归" },
  ],
  refactor: [
    { re: /既有生产/, fact: "既有生产代码" },
    { re: /existing production/i, fact: "existing production" },
  ],
  release: [
    { re: /生产路径|production path/i, fact: "生产路径" },
    { re: /部署|\bdeploy/i, fact: "deploy" },
    { re: /发布/, fact: "发布" },
    {
      re: /production (?:service|api|job)/i,
      fact: "production service/API/job",
    },
  ],
};

export function sessionIdFromExec(exec: PlanToolExec | undefined): string {
  const id = exec?.agent?.id;
  if (typeof id === "string" && id.length > 0) {
    return id;
  }
  return DEFAULT_SESSION_ID;
}

export function taskIdFromSummary(summary: string): string {
  const trimmed = summary.trim();
  const digest = createHash("sha256")
    .update(trimmed)
    .digest("hex")
    .slice(0, 12);
  const slug = trimmed
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return slug.length > 0 ? `${slug}-${digest}` : `task-${digest}`;
}

function haystack(summary: string, facts: string[] | undefined): string {
  const extra = facts === undefined ? "" : facts.join("\n");
  return `${summary}\n${extra}`;
}

export function inferRequirements(
  summary: string,
  facts?: string[],
): Record<GateKind, InferredGate> {
  const text = haystack(summary, facts);
  const out = {} as Record<GateKind, InferredGate>;
  for (const kind of GATE_KINDS) {
    const hit = PREDICATES[kind].find((p) => p.re.test(text));
    if (hit !== undefined) {
      out[kind] = {
        requirement: "required",
        state: "planned",
        fact: hit.fact,
      };
    } else {
      out[kind] = {
        requirement: "on-demand",
        state: "not-required",
      };
    }
  }
  return out;
}

function mergeGate(
  previous: BookGatePlan["gates"][GateKind] | undefined,
  inferred: InferredGate,
): BookGatePlan["gates"][GateKind] {
  if (inferred.requirement === "required") {
    if (previous !== undefined && previous.state === "passed") {
      const kept: BookGatePlan["gates"][GateKind] = {
        requirement: "required",
        state: "passed",
      };
      const fact = inferred.fact ?? previous.fact;
      if (fact !== undefined) {
        kept.fact = fact;
      }
      if (previous.reviewStatus !== undefined) {
        kept.reviewStatus = previous.reviewStatus;
      }
      return kept;
    }
    if (
      previous !== undefined &&
      (previous.state === "running" ||
        previous.state === "blocked" ||
        previous.state === "planned")
    ) {
      const kept: BookGatePlan["gates"][GateKind] = {
        requirement: "required",
        state: previous.state,
      };
      const fact = inferred.fact ?? previous.fact;
      if (fact !== undefined) {
        kept.fact = fact;
      }
      if (previous.reviewStatus !== undefined) {
        kept.reviewStatus = previous.reviewStatus;
      }
      return kept;
    }
    const next: BookGatePlan["gates"][GateKind] = {
      requirement: "required",
      state: "planned",
    };
    if (inferred.fact !== undefined) {
      next.fact = inferred.fact;
    }
    return next;
  }

  if (previous !== undefined && previous.state === "passed") {
    return {
      requirement: "on-demand",
      state: "not-required",
      fact: "trigger fact disappeared; reset passed",
    };
  }

  const optional: BookGatePlan["gates"][GateKind] = {
    requirement: "on-demand",
    state: "not-required",
  };
  if (inferred.fact !== undefined) {
    optional.fact = inferred.fact;
  }
  return optional;
}

export function formatPlanMarkdown(plan: BookGatePlan): string {
  const rows = GATE_KINDS.map((kind) => {
    const gate = plan.gates[kind];
    const fact = gate.fact ?? "";
    return `| ${kind} | ${gate.requirement} | ${gate.state} | ${fact} |`;
  });
  return [
    "# Book Gate Plan",
    "",
    `taskId: ${plan.taskId}`,
    "",
    plan.summary,
    "",
    "| Gate | Requirement | State | Fact |",
    "|---|---|---|---|",
    ...rows,
  ].join("\n");
}

export function sbtdPlan(sessionId: string, input: PlanInput): PlanToolResult {
  const summary = input.task_summary.trim();
  if (summary.length === 0) {
    throw new Error("sbtd_plan: task_summary must be a non-empty string");
  }

  const session = getSession(sessionId);
  const taskId = taskIdFromSummary(summary);
  const inferred = inferRequirements(summary, input.facts);
  const existing = session.plan;
  const sameGoal = existing !== undefined && existing.taskId === taskId;

  const gates = {} as BookGatePlan["gates"];
  for (const kind of GATE_KINDS) {
    const previous = sameGoal ? existing.gates[kind] : undefined;
    gates[kind] = mergeGate(previous, inferred[kind]);
  }

  const plan: BookGatePlan = {
    taskId,
    summary,
    gates,
  };
  session.plan = plan;
  return { plan, markdown: formatPlanMarkdown(plan) };
}

export const SBTD_PLAN_DESCRIPTION =
  "Register or update the session Book Gate Plan. Pass task_summary; optional facts are objective trigger strings. Required gates are inferred from PRD 3.4 predicates, never from subjective risk. Repeat calls for the same goal update facts and keep passed gates unless a trigger disappears.";

export function createPlanTool(): PlanToolDefinition {
  return {
    name: SBTD_PLAN_TOOL_NAME,
    description: SBTD_PLAN_DESCRIPTION,
    parameters: {
      type: "object",
      properties: {
        task_summary: {
          type: "string",
          description: "Short description of the development task.",
        },
        facts: {
          type: "array",
          description:
            "Optional objective trigger facts (PRD 3.4). Also inferred from task_summary.",
          items: { type: "string" },
        },
      },
      required: ["task_summary"],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          plan: { type: "object" },
          markdown: { type: "string" },
        },
      },
      render(_args, value) {
        return [{ type: "text", text: value.markdown }];
      },
    },
    isConcurrencySafe() {
      return false;
    },
    async execute(args, exec) {
      return sbtdPlan(sessionIdFromExec(exec), args);
    },
  };
}

export function registerPlanTool(ctx: ToolsHost): void {
  ctx.tools.register(createPlanTool());
}
