import type { MaestroOptions, PreflightResult } from "../backends/maestro.js";
import { FORBIDDEN_MODEL_KEYS, preflight } from "../backends/maestro.js";
import { optionalHostBag } from "../host-context.js";
import type { BookGatePlan } from "../state.js";
import { serialize } from "../state.js";

/**
 * Structural match for `@deepseek-ai/dsh-commands@0.1.1-rc.2` `CommandDefinition`
 * (verified in pnpm store; not inferred from omp-sbtd).
 */
export const SBTD_COMMAND_NAME = "sbtd";

export const SBTD_COMMAND_DESCRIPTION =
  "Human SBTD status, Book Gate Plan view, and Maestro preflight. Not a model tool.";

/** Q4A canonical T10 trust-handle list (host-injected via `commandHost`; not on `CommandInvocation`). */
export { FORBIDDEN_MODEL_KEYS };

export type CommandResult =
  | { kind: "success"; text?: string; sourceEventSeq?: number }
  | { kind: "error"; text: string };

/** Minimal invocation surface from dsh-commands `CommandInvocation`. */
export type CommandInvocation = {
  readonly agent: { readonly id?: string };
  readonly rawInput: string;
};

export type SbtdCommandHost = {
  sessionId?: string;
  cwd?: string;
  preflight?: (options?: MaestroOptions) => Promise<PreflightResult>;
  maestro?: MaestroOptions;
};

export type CommandsHost = {
  commands?: {
    register: (definition: SbtdCommandDefinition) => () => void;
  };
  commandHost?: SbtdCommandHost;
};

export type SbtdCommandDefinition = {
  name: "sbtd";
  description: string;
  input?: { hint: string };
  handler: (
    invocation: CommandInvocation,
  ) => CommandResult | Promise<CommandResult>;
};

const GATE_KINDS = ["ddd", "ddia", "legacy", "refactor", "release"] as const;

export function parseSbtdArgv(rawInput: string): "status" | "plan" | "maestro" {
  const tokens = rawInput
    .trim()
    .split(/\s+/)
    .filter((t) => t.length > 0);

  if (tokens.length === 0) {
    return "status";
  }

  if (tokens.length === 1 && tokens[0] === "plan") {
    return "plan";
  }
  if (tokens.length === 1 && tokens[0] === "maestro") {
    return "maestro";
  }

  throw new Error(
    `unknown subcommand: ${tokens[0]}\nusage: /sbtd | /sbtd plan | /sbtd maestro`,
  );
}

function formatMissing(missing: string[] | undefined): string {
  if (missing === undefined || missing.length === 0) {
    return "none";
  }
  return missing.join(", ");
}

export function formatPlanBlock(plan: BookGatePlan): string {
  const lines = [
    "Book Gate Plan",
    `taskId: ${plan.taskId}`,
    `summary: ${plan.summary}`,
    "gates:",
  ];
  for (const kind of GATE_KINDS) {
    const gate = plan.gates[kind];
    if (gate === undefined) {
      lines.push(`  ${kind}: absent absent`);
    } else {
      lines.push(`  ${kind}: ${gate.requirement} ${gate.state}`);
    }
  }
  return lines.join("\n");
}

export async function runSbtdCommand(
  rawInput: string,
  host: SbtdCommandHost = {},
): Promise<string> {
  const sessionId =
    typeof host.sessionId === "string" && host.sessionId.length > 0
      ? host.sessionId
      : "default";
  const verb = parseSbtdArgv(rawInput);

  if (verb === "status") {
    const snap = serialize(sessionId);
    const planBlock =
      snap.plan === undefined ? "no-plan" : formatPlanBlock(snap.plan);
    return `${planBlock}\n\nmaestro missing: ${formatMissing(snap.maestro?.missing)}`;
  }

  if (verb === "plan") {
    const snap = serialize(sessionId);
    if (snap.plan === undefined) {
      return "no-plan";
    }
    return formatPlanBlock(snap.plan);
  }

  const run = host.preflight ?? preflight;
  const options: MaestroOptions = {
    ...host.maestro,
    sessionId,
  };
  if (typeof host.cwd === "string" && host.cwd.length > 0) {
    options.cwd = host.cwd;
  }
  const result = await run(options);
  return `maestro preflight: ${result.lastPreflight}\nmissing: ${formatMissing(result.missing)}\n${result.guidance}`;
}

function sessionIdFromInvocation(
  invocation: CommandInvocation,
  host: SbtdCommandHost,
): string {
  const agentId = invocation.agent.id;
  if (typeof agentId === "string" && agentId.length > 0) {
    return agentId;
  }
  if (typeof host.sessionId === "string" && host.sessionId.length > 0) {
    return host.sessionId;
  }
  return "default";
}

export async function executeSbtdCommand(
  invocation: CommandInvocation,
  host: SbtdCommandHost = {},
): Promise<CommandResult> {
  try {
    const text = await runSbtdCommand(invocation.rawInput, {
      ...host,
      sessionId: sessionIdFromInvocation(invocation, host),
    });
    return { kind: "success", text };
  } catch (error) {
    return {
      kind: "error",
      text: error instanceof Error ? error.message : String(error),
    };
  }
}

export function createSbtdCommand(
  host: SbtdCommandHost = {},
): SbtdCommandDefinition {
  return {
    name: SBTD_COMMAND_NAME,
    description: SBTD_COMMAND_DESCRIPTION,
    input: { hint: "[plan|maestro]" },
    handler: (invocation) => executeSbtdCommand(invocation, host),
  };
}

export function registerCommand(
  ctx: CommandsHost,
  host: SbtdCommandHost = {},
): void {
  if (typeof ctx.commands?.register !== "function") {
    return;
  }
  ctx.commands.register(createSbtdCommand(host));
}

export function resolveCommandHost(ctx: CommandsHost): SbtdCommandHost {
  const explicit = optionalHostBag<SbtdCommandHost>(ctx, "commandHost") ?? {};
  const out: SbtdCommandHost = {};
  if (typeof explicit.sessionId === "string" && explicit.sessionId.length > 0) {
    out.sessionId = explicit.sessionId;
  }
  if (typeof explicit.cwd === "string" && explicit.cwd.length > 0) {
    out.cwd = explicit.cwd;
  }
  if (explicit.preflight !== undefined) {
    out.preflight = explicit.preflight;
  }
  if (explicit.maestro !== undefined) {
    out.maestro = explicit.maestro;
  }
  return out;
}
