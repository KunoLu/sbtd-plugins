import {
  type PlanToolExec,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";
import {
  type ArtifactHostResult,
  type ArtifactInput,
  type ArtifactToolResult,
  runTaskArtifact,
  toArtifactHostResult,
} from "./task-artifact.js";

export const SBTD_TICKETS_TOOL_NAME = "sbtd_tickets";

export type TicketsInput = ArtifactInput;
export type TicketsToolResult = ArtifactToolResult;
export type TicketsHostResult = ArtifactHostResult;

export type TicketsToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: TicketsHostResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (
    args: TicketsInput,
    exec: PlanToolExec,
  ) => Promise<TicketsHostResult>;
};

export function sbtdTickets(
  sessionId: string,
  input: TicketsInput,
  env: NodeJS.ProcessEnv = process.env,
): TicketsToolResult {
  return runTaskArtifact(sessionId, "implement.md", input, env);
}

export const SBTD_TICKETS_DESCRIPTION =
  "Write implementation tickets/slices via the Trellis backend. With .trellis/ present and a resolved task slug, writes only implement.md under the same .trellis/tasks/<slug>/ (markdown slices, not child tasks). Without Trellis or without a usable task path, returns a markdown draft (never writes under docs/; never trellis init). Explicit task (safe slug) preferred; else derives slug by stripping .trellis/tasks/ from the session current-task pointer. When plan.gates.ddd is required and reviewStatus is not confirmed, refuses write and returns blocked.kind=ddd-unconfirmed.";

export function createTicketsTool(): TicketsToolDefinition {
  return {
    name: SBTD_TICKETS_TOOL_NAME,
    description: SBTD_TICKETS_DESCRIPTION,
    parameters: {
      type: "object",
      properties: {
        markdown: {
          type: "string",
          description: "Tickets/slices markdown body to write or return as draft.",
        },
        body: {
          type: "string",
          description: "Alias for markdown.",
        },
        task: {
          type: "string",
          description:
            "Optional safe Trellis task slug (e.g. 09-09-demo). Preferred over current-task pointer.",
        },
        cwd: {
          type: "string",
          description: "Working directory containing .trellis/ (defaults to process.cwd()).",
        },
        session_key: {
          type: "string",
          description:
            "Optional Trellis session key for current-task pointer lookup (else TRELLIS_CONTEXT_ID).",
        },
      },
      required: [],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          ok: { type: "boolean" },
          mode: { type: "string" },
          artifact: { type: "string" },
          markdown: { type: "string" },
          path: { type: "string" },
          slug: { type: "string" },
          note: { type: "string" },
          blocked: { type: "object" },
          detect: { type: "object" },
          source: { type: "string" },
        },
      },
      render(_args, value) {
        const lines = [
          `mode: ${value.mode}`,
          `artifact: ${value.artifact}`,
        ];
        if (value.slug != null) {
          lines.push(`slug: ${value.slug}`);
        }
        if (value.path !== undefined) {
          lines.push(`path: ${value.path}`);
        }
        if (value.note !== undefined) {
          lines.push(`note: ${value.note}`);
        }
        if (value.blocked !== undefined) {
          lines.push(
            "blocked: DDD not confirmed; do not write implement.md; further sbtd_clarify is not the resume path.",
          );
        }
        lines.push("", value.markdown);
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe() {
      return false;
    },
    async execute(args, exec) {
      return toArtifactHostResult(
        sbtdTickets(sessionIdFromExec(exec), args),
      );
    },
  };
}

export function registerTicketsTool(ctx: ToolsHost): void {
  ctx.tools.register(createTicketsTool());
}
