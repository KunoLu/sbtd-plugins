export type EnvironmentMode =
  | "blocked"
  | "needs-onboard"
  | "degraded"
  | "managed";

export interface SbtdCommandSpec {
  readonly path: readonly string[];
  readonly aliases: readonly (readonly string[])[];
  readonly category: "Control" | "Onboard" | "Information";
  readonly summary: string;
  readonly usage: string;
  readonly examples: readonly string[];
  readonly mutates: boolean | "conditional";
  readonly requiresConfirmation: boolean;
  readonly availableIn: readonly EnvironmentMode[];
}

const allModes = ["blocked", "needs-onboard", "degraded", "managed"] as const;

export const sbtdCommandSpecs: readonly SbtdCommandSpec[] = [
  {
    path: ["help"],
    aliases: [],
    category: "Information",
    summary: "Show deterministic SBTD command help.",
    usage: "/sbtd help [command]",
    examples: ["/sbtd help", "/sbtd help onboard plan"],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["doctor"],
    aliases: [],
    category: "Information",
    summary: "Inspect SBTD environment and recovery facts.",
    usage: "/sbtd doctor",
    examples: ["/sbtd doctor"],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["status"],
    aliases: [],
    category: "Information",
    summary: "Show persisted choices and derived control state.",
    usage: "/sbtd status",
    examples: ["/sbtd status"],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["report"],
    aliases: [],
    category: "Information",
    summary: "Render the current sanitized validation and Provider report.",
    usage: "/sbtd report",
    examples: ["/sbtd report"],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["on"],
    aliases: [],
    category: "Control",
    summary: "Enable SBTD after a fresh preflight.",
    usage: "/sbtd on",
    examples: ["/sbtd on"],
    mutates: true,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["off"],
    aliases: [],
    category: "Control",
    summary: "Return SBTD to advisory mode.",
    usage: "/sbtd off",
    examples: ["/sbtd off"],
    mutates: true,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["route"],
    aliases: [],
    category: "Control",
    summary: "Show the current SBTD Route or atomically override it.",
    usage: "/sbtd route [auto|route-id]",
    examples: ["/sbtd route", "/sbtd route review", "/sbtd route auto"],
    mutates: "conditional",
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["strict"],
    aliases: [],
    category: "Control",
    summary: "Require configured optional workflow checks.",
    usage: "/sbtd strict",
    examples: ["/sbtd strict"],
    mutates: true,
    requiresConfirmation: false,
    availableIn: ["degraded", "managed"],
  },
  {
    path: ["relaxed"],
    aliases: [],
    category: "Control",
    summary: "Keep optional workflow checks optional.",
    usage: "/sbtd relaxed",
    examples: ["/sbtd relaxed"],
    mutates: true,
    requiresConfirmation: false,
    availableIn: ["degraded", "managed"],
  },
  {
    path: ["gate", "start"],
    aliases: [],
    category: "Control",
    summary: "Start one planned Book Gate before its required phase.",
    usage: "/sbtd gate start <gate-id>",
    examples: ["/sbtd gate start legacy-change-safety"],
    mutates: true,
    requiresConfirmation: false,
    availableIn: ["degraded", "managed"],
  },
  {
    path: ["gate", "record"],
    aliases: [],
    category: "Control",
    summary: "Record a validated Book Gate reviewer outcome.",
    usage: "/sbtd gate record <gate-id> <reviewer-status>",
    examples: ["/sbtd gate record legacy-change-safety characterized"],
    mutates: true,
    requiresConfirmation: true,
    availableIn: ["degraded", "managed"],
  },
  {
    path: ["onboard", "status"],
    aliases: [],
    category: "Onboard",
    summary: "Inspect managed AGENTS assets.",
    usage: "/sbtd onboard status",
    examples: ["/sbtd onboard status"],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["onboard", "plan"],
    aliases: [],
    category: "Onboard",
    summary:
      "Preview a zero-write composite onboarding plan (AGENTS, Skills, CLIs, selected MCP, Trellis).",
    usage: "/sbtd onboard plan [--mcp <ids>] [--trellis-user <name>]",
    examples: [
      "/sbtd onboard plan",
      "/sbtd onboard plan --mcp gitnexus --trellis-user 640",
    ],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["onboard", "init"],
    aliases: [],
    category: "Onboard",
    summary: "Apply the current composite onboarding plan per approval class.",
    usage:
      "/sbtd onboard init [plan-digest] [--mcp <ids>] [--trellis-user <name>]",
    examples: [
      "/sbtd onboard init",
      "/sbtd onboard init --mcp gitnexus --trellis-user 640",
    ],
    mutates: true,
    requiresConfirmation: true,
    availableIn: allModes,
  },
  {
    path: ["onboard", "reset"],
    aliases: [],
    category: "Onboard",
    summary: "Plan a managed-block repair or reset.",
    usage: "/sbtd onboard reset",
    examples: ["/sbtd onboard reset"],
    mutates: true,
    requiresConfirmation: true,
    availableIn: allModes,
  },
  {
    path: ["onboard", "init-projects"],
    aliases: [],
    category: "Onboard",
    summary:
      "Apply project-scoped managed blocks and Trellis initialization only.",
    usage: "/sbtd onboard init-projects [--trellis-user <name>]",
    examples: ["/sbtd onboard init-projects --trellis-user 640"],
    mutates: true,
    requiresConfirmation: true,
    availableIn: allModes,
  },
  {
    path: ["onboard", "bootstrap"],
    aliases: [],
    category: "Onboard",
    summary:
      "Schedule or observe the Trellis bootstrap handoff bound to a completed Onboard Plan.",
    usage: "/sbtd onboard bootstrap <plan-digest>",
    examples: ["/sbtd onboard bootstrap <plan-digest>"],
    mutates: true,
    requiresConfirmation: true,
    availableIn: allModes,
  },
  {
    path: ["onboard", "skip", "list"],
    aliases: [],
    category: "Onboard",
    summary: "List AcceptedSkip records without changing the environment.",
    usage: "/sbtd onboard skip list",
    examples: ["/sbtd onboard skip list"],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["onboard", "skip", "plan", "create"],
    aliases: [],
    category: "Onboard",
    summary: "Create a zero-write Plan for an Optional AcceptedSkip.",
    usage:
      "/sbtd onboard skip plan create <capability> --scope <global|project> --expires <ISO-8601> --reason <text>",
    examples: [
      '/sbtd onboard skip plan create ui --scope project --expires 2026-08-01T00:00:00.000Z --reason "temporary local exemption"',
    ],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["onboard", "skip", "plan", "revoke"],
    aliases: [],
    category: "Onboard",
    summary: "Create a zero-write Plan to revoke an AcceptedSkip.",
    usage: "/sbtd onboard skip plan revoke <record-id> --reason <text>",
    examples: [
      '/sbtd onboard skip plan revoke 00000000-0000-4000-8000-000000000000 --reason "tool is available"',
    ],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["onboard", "skip", "plan", "expire"],
    aliases: [],
    category: "Onboard",
    summary: "Create a zero-write Plan to reconcile an expired AcceptedSkip.",
    usage: "/sbtd onboard skip plan expire <record-id> --reason <text>",
    examples: [
      '/sbtd onboard skip plan expire 00000000-0000-4000-8000-000000000000 --reason "expiry reconciliation"',
    ],
    mutates: false,
    requiresConfirmation: false,
    availableIn: allModes,
  },
  {
    path: ["onboard", "skip", "apply"],
    aliases: [],
    category: "Onboard",
    summary: "Apply a displayed AcceptedSkip Plan after confirmation.",
    usage: "/sbtd onboard skip apply <plan-digest>",
    examples: ["/sbtd onboard skip apply <plan-digest>"],
    mutates: true,
    requiresConfirmation: true,
    availableIn: allModes,
  },
] as const;

export type ParseResult =
  | { kind: "command"; spec: SbtdCommandSpec; args: readonly string[] }
  | {
      kind: "unknown";
      input: readonly string[];
      suggestions: readonly string[];
    };

function tokenizeSbtdCommand(input: string): readonly string[] {
  const tokens: string[] = [];
  let token = "";
  let quote: '"' | "'" | undefined;
  let escaped = false;
  for (const character of input.trim()) {
    if (escaped) {
      token += character;
      escaped = false;
      continue;
    }
    if (character === "\\" && quote !== undefined) {
      escaped = true;
      continue;
    }
    if (character === "'" || character === '"') {
      if (quote === undefined) {
        quote = character;
        continue;
      }
      if (quote === character) {
        quote = undefined;
        continue;
      }
    }
    if (/\s/.test(character) && quote === undefined) {
      if (token.length > 0) {
        tokens.push(token);
        token = "";
      }
      continue;
    }
    token += character;
  }
  if (escaped) token += "\\";
  if (token.length > 0) tokens.push(token);
  return tokens;
}

export function parseSbtdCommand(
  input: string,
  specs: readonly SbtdCommandSpec[] = sbtdCommandSpecs,
): ParseResult {
  const tokens = tokenizeSbtdCommand(input);
  const matched = specs
    .map((spec) => ({
      spec,
      matched: [spec.path, ...spec.aliases].find((candidate) =>
        candidate.every((part, index) => tokens[index] === part),
      ),
    }))
    .filter(
      (
        candidate,
      ): candidate is { spec: SbtdCommandSpec; matched: readonly string[] } =>
        candidate.matched !== undefined,
    )
    .sort((a, b) => b.matched.length - a.matched.length)[0];
  if (matched)
    return {
      kind: "command",
      spec: matched.spec,
      args: tokens.slice(matched.matched.length),
    };
  return {
    kind: "unknown",
    input: tokens,
    suggestions: suggestSbtdCommand(tokens, specs),
  };
}

export function suggestSbtdCommand(
  tokens: readonly string[],
  specs: readonly SbtdCommandSpec[] = sbtdCommandSpecs,
): readonly string[] {
  const query = tokens.join(" ");
  return specs
    .map((spec) => spec.path.join(" "))
    .filter((path) => path.startsWith(query) || path.includes(query))
    .sort();
}

export function completeSbtdCommand(
  prefix: string,
  specs: readonly SbtdCommandSpec[] = sbtdCommandSpecs,
): readonly string[] {
  return specs
    .map((spec) => spec.path.join(" "))
    .filter((path) => path.startsWith(prefix.trim()))
    .sort();
}

export function renderSbtdHelp(
  specs: readonly SbtdCommandSpec[] = sbtdCommandSpecs,
  command?: string,
): string {
  const selected = command ? parseSbtdCommand(command, specs) : undefined;
  const rows =
    selected?.kind === "command"
      ? [selected.spec]
      : [...specs].sort((a, b) =>
          a.path.join(" ").localeCompare(b.path.join(" ")),
        );
  return rows
    .map((spec) =>
      [
        `/sbtd ${spec.path.join(" ")} — ${spec.summary}`,
        `Usage: ${spec.usage}`,
        `Examples: ${spec.examples.join(", ")}`,
        `Writes: ${spec.mutates === "conditional" ? "only with an override argument" : spec.mutates ? "yes" : "no"}; Confirmation: ${spec.requiresConfirmation ? "required" : "not required"}`,
      ].join("\n"),
    )
    .join("\n\n");
}
