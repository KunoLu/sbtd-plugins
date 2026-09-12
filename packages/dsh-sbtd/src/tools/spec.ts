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

export const SBTD_SPEC_TOOL_NAME = "sbtd_spec";

export type SpecInput = ArtifactInput;
export type SpecToolResult = ArtifactToolResult;
export type SpecHostResult = ArtifactHostResult;

export type SpecToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: SpecHostResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => false;
  execute: (args: SpecInput, exec: PlanToolExec) => Promise<SpecHostResult>;
};

export function sbtdSpec(
  sessionId: string,
  input: SpecInput,
  env: NodeJS.ProcessEnv = process.env,
): SpecToolResult {
  return runTaskArtifact(sessionId, "prd.md", input, env);
}

export const SBTD_SPEC_DESCRIPTION =
  "Write a PRD via the Trellis backend. With .trellis/ present and a resolved task slug, writes only prd.md under .trellis/tasks/<slug>/. Without Trellis or without a usable task path, returns a markdown draft (never writes under docs/; never trellis init). Explicit task (safe slug) preferred; else derives slug by stripping .trellis/tasks/ from the session current-task pointer. When plan.gates.ddd is required and reviewStatus is not confirmed, refuses write and returns blocked.kind=ddd-unconfirmed.";

export function createSpecTool(): SpecToolDefinition {
  return {
    name: SBTD_SPEC_TOOL_NAME,
    description: SBTD_SPEC_DESCRIPTION,
    parameters: {
      type: "object",
      properties: {
        markdown: {
          type: "string",
          description: "PRD markdown body to write or return as draft.",
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
            "blocked: DDD not confirmed; do not write prd.md; further sbtd_clarify is not the resume path.",
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
      return toArtifactHostResult(sbtdSpec(sessionIdFromExec(exec), args));
    },
  };
}

export function registerSpecTool(ctx: ToolsHost): void {
  ctx.tools.register(createSpecTool());
}
