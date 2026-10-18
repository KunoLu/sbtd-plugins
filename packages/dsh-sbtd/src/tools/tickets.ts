import { type PlanToolExec, sessionIdFromExec, type ToolsHost } from "./plan.js";
import {
  type ArtifactInput,
  type ArtifactToolResult,
  runTaskArtifact,
} from "./task-artifact.js";

export const SBTD_TICKETS_TOOL_NAME = "sbtd_tickets";

export type TicketsInput = ArtifactInput;
export type TicketsToolResult = ArtifactToolResult;

export type TicketsToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: TicketsToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (args: TicketsInput, exec: PlanToolExec) => Promise<TicketsToolResult>;
};

export function sbtdTickets(sessionId: string, input: TicketsInput): TicketsToolResult {
  return runTaskArtifact(sessionId, "implement.md", input);
}

export const SBTD_TICKETS_DESCRIPTION =
  "Return an implementation tickets/slices markdown draft. Draft-only (R1 Q2 A): the plugin writes no task files — the Trellis backend is removed, nothing is written under .trellis/, docs/, or any task store; persist the returned draft yourself if needed.";

export function createTicketsTool(): TicketsToolDefinition {
  return {
    name: SBTD_TICKETS_TOOL_NAME,
    description: SBTD_TICKETS_DESCRIPTION,
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        markdown: {
          type: "string",
          description:
            "Tickets/slices markdown body returned as the draft.",
        },
        body: {
          type: "string",
          description: "Alias for markdown.",
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
          note: { type: "string" },
          blocked: { type: "object" },
        },
      },
      render(_args, value) {
        const lines = [`mode: ${value.mode}`, `artifact: ${value.artifact}`];
        if (value.note !== undefined) {
          lines.push(`note: ${value.note}`);
        }
        lines.push("", value.markdown);
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe() {
      return false;
    },
    async execute(args, exec) {
      return sbtdTickets(sessionIdFromExec(exec), args);
    },
  };
}

export function registerTicketsTool(ctx: ToolsHost): void {
  ctx.tools.register(createTicketsTool());
}
