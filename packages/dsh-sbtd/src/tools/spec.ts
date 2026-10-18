import { type PlanToolExec, sessionIdFromExec, type ToolsHost } from "./plan.js";
import {
  type ArtifactInput,
  type ArtifactToolResult,
  runTaskArtifact,
} from "./task-artifact.js";

export const SBTD_SPEC_TOOL_NAME = "sbtd_spec";

export type SpecInput = ArtifactInput;
export type SpecToolResult = ArtifactToolResult;

export type SpecToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: SpecToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (args: SpecInput, exec: PlanToolExec) => Promise<SpecToolResult>;
};

export function sbtdSpec(sessionId: string, input: SpecInput): SpecToolResult {
  return runTaskArtifact(sessionId, "prd.md", input);
}

export const SBTD_SPEC_DESCRIPTION =
  "Return a PRD markdown draft. Draft-only (R1 Q2 A): the plugin writes no task files — the Trellis backend is removed, nothing is written under .trellis/, docs/, or any task store; persist the returned draft yourself if needed.";

export function createSpecTool(): SpecToolDefinition {
  return {
    name: SBTD_SPEC_TOOL_NAME,
    description: SBTD_SPEC_DESCRIPTION,
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        markdown: {
          type: "string",
          description: "PRD markdown body returned as the draft.",
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
      return sbtdSpec(sessionIdFromExec(exec), args);
    },
  };
}

export function registerSpecTool(ctx: ToolsHost): void {
  ctx.tools.register(createSpecTool());
}
