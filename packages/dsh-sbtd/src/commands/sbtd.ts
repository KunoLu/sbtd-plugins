import type { MaestroOptions, PreflightResult } from "../backends/maestro.js";
import { preflight } from "../backends/maestro.js";
import type { BookGatePlan } from "../state.js";
import { serialize } from "../state.js";

export const SBTD_COMMAND_NAME = "sbtd";

export const SBTD_COMMAND_DESCRIPTION =
  "Human SBTD status, Book Gate Plan view, and Maestro preflight. Not a model tool.";

export const FORBIDDEN_COMMAND_KEYS = [
  "cwd",
  "mcp",
  "runRefresh",
  "serverName",
  "toolNames",
] as const;

export type SbtdCommandHost = {
  sessionId?: string;
  cwd?: string;
  preflight?: (options?: MaestroOptions) => Promise<PreflightResult>;
  maestro?: MaestroOptions;
};

export type CommandsHost = {
  commands?: {
    register: (definition: SbtdCommandDefinition) => unknown;
  };
  commandHost?: SbtdCommandHost;
};

export type SbtdCommandDefinition = {
  name: "sbtd";
  description: string;
  input: { hint: string };
  handler: (input?: unknown) => Promise<string>;
};

const GATE_KINDS = ["ddd", "ddia", "legacy", "refactor", "release"] as const;

export function parseSbtdArgv(input: unknown): "status" | "plan" | "maestro" {
  if (input !== null && typeof input === "object" && !Array.isArray(input)) {
    const obj = input as Record<string, unknown>;
    for (const key of FORBIDDEN_COMMAND_KEYS) {
      if (Object.hasOwn(obj, key)) {
        throw new Error(
          `sbtd command forbids trust handle "${key}" (host-injected only)`,
        );
      }
    }
    if (typeof obj.args === "string") {
      return parseSbtdArgv(obj.args);
    }
    if (Array.isArray(obj.argv)) {
      return parseSbtdArgv(obj.argv);
    }
    if (typeof obj.subcommand === "string") {
      return parseSbtdArgv(obj.subcommand);
    }
    return "status";
  }

  if (input === undefined || input === null || input === "") {
    return "status";
  }

  let tokens: string[];
  if (typeof input === "string") {
    tokens = input
      .trim()
      .split(/\s+/)
      .filter((t) => t.length > 0);
  } else if (Array.isArray(input)) {
    tokens = input.filter((t): t is string => typeof t === "string");
  } else {
    return "status";
  }

  if (tokens.length > 0 && (tokens[0] === "sbtd" || tokens[0] === "/sbtd")) {
    tokens = tokens.slice(1);
  }
  const head = tokens[0];
  if (head?.startsWith("/")) {
    tokens[0] = head.slice(1);
  }

  if (tokens.length === 0) {
    return "status";
  }

  const first = tokens[0];
  if (first === "plan") {
    return "plan";
  }
  if (first === "maestro") {
    return "maestro";
  }

  throw new Error(
    `unknown subcommand: ${first}\nusage: /sbtd | /sbtd plan | /sbtd maestro`,
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
  input?: unknown,
  host: SbtdCommandHost = {},
): Promise<string> {
  const sessionId =
    typeof host.sessionId === "string" && host.sessionId.length > 0
      ? host.sessionId
      : "default";
  const verb = parseSbtdArgv(input);

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

export function createSbtdCommand(
  host: SbtdCommandHost = {},
): SbtdCommandDefinition {
  return {
    name: SBTD_COMMAND_NAME,
    description: SBTD_COMMAND_DESCRIPTION,
    input: { hint: "[plan|maestro]" },
    handler: (input?: unknown) => runSbtdCommand(input, host),
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
  const explicit = ctx.commandHost ?? {};
  const out: SbtdCommandHost = {};
  if (typeof explicit.sessionId === "string" && explicit.sessionId.length > 0) {
    out.sessionId = explicit.sessionId;
  } else {
    out.sessionId = "default";
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
