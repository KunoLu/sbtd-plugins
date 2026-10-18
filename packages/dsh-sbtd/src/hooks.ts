import { relative, resolve, sep } from "node:path";
import {
  describeWorkflowMode,
  resolveWorkflowMode,
} from "./backends/sbtd-task.js";
import { optionalHostBag, optionalHostCwd } from "./host-context.js";
import { getSession } from "./state.js";
import { type PlanToolExec, sessionIdFromExec } from "./tools/plan.js";

export const PRE_EXECUTE_EVENT = "tools/pre-execute";
export const PRE_STEP_EVENT = "agent/pre-step";
export const PLUGIN_NAME = "dsh-sbtd";

export type PreToolDecision =
  | { kind: "allow" }
  | { kind: "deny"; reason: string }
  | { kind: "ask"; reason: string };

export type PreStepDecision =
  | { kind: "reject" }
  | { kind: "enter"; messages: PreStepMessage[] };

export type ToolExec = {
  name: string;
  arguments?: unknown;
  agent?: { id?: string };
};

export type PreStepMessage = {
  id?: string;
  role?: string;
  content?: unknown;
  source?: unknown;
};

export type PreStepPayload = {
  agent?: { id?: string };
  messages?: PreStepMessage[];
};

export type HooksHost = {
  /** Project root for the read-only workflow_mode lookup. */
  cwd?: string;
  /** Host-injected workflow_mode (layer 2; R1 Q4). */
  workflowMode?: string;
  on: {
    (
      event: "tools/pre-execute",
      handler: (
        exec: ToolExec,
        next: () => Promise<PreToolDecision>,
      ) => Promise<PreToolDecision>,
    ): unknown;
    (
      event: "agent/pre-step",
      handler: (
        payload: PreStepPayload,
        next: () => Promise<PreStepDecision>,
      ) => Promise<PreStepDecision>,
    ): unknown;
  };
};

const MUTATION_TOOLS: Record<string, true> = {
  write: true,
  edit: true,
  str_replace_editor: true,
};
const GIT_ALLOW =
  /(?:^|[\s;&|])git(?:\s+-\S+)*\s+(commit|status|log|diff|show)(?:\s|$)/;
const GIT_CHAIN = /&&|\|\||;/;
const PUBLISH_BASH =
  /\b(?:npm|pnpm|yarn|bunx?)\s+publish\b|\bdsh\s+plugin\s+publish\b/;
const PKG_MGR =
  /\b(?:npm|pnpm|yarn|bunx?)\s+(?:add|remove|uninstall|install|i)\b/;
const RM_BASH = /(?:^|[\s;&|])rm(?:\s|$)/;
const MUTATING_BASH =
  /(?:^|[\s;&|])(?:rm|mv|cp|touch|chmod|chown|unlink|mkdir)\b|\s(?:>>?|tee)\s|\bsed\s+-i\b|\bperl\s+-i|\b(?:npm|pnpm|yarn|bunx?)\s+(?:add|remove|uninstall|install|i|publish)\b|\bgit\s+(?:add|push|reset|rebase|cherry-pick|stash|tag|merge)\b/;
const DEV_INTENT =
  /开发|实现|改代码|implement|refactor|bug\s*fix|生产代码|sbtd_plan|src\/|existing production|feature|write|edit/i;
const DATA_PATH =
  /(?:^|\/)(?:schema|migration|migrations|sql|prisma|drizzle|redis|cache|database|persist)(?:\/|$|\.)|\.(?:sql|prisma)$/i;
const IMPL_EXT =
  /\.(?:ts|tsx|js|jsx|mjs|cjs|mts|cts|py|go|rs|java|kt|swift|c|cc|cpp|h|hpp|cs)$/i;
const README = /(?:^|\/)README(?:\.[^/]+)?\.md$/i;
const EXEMPT =
  /(?:^|\/)(?:features|maestro\/flow|\.trellis)(?:\/|$)|(?:^|\/)[^/]*\.test\.[^/]+$|(?:^|\/)[^/]*\.spec\.[^/]+$/;

const ASK_PLAN = "尚未 sbtd_plan，请先调用 sbtd_plan。";
const ASK_RM_PKG =
  "rm 或包管理器将改业务代码，请确认；若尚未计划请先调用 sbtd_plan。";
const NOTICE_TEXT = "尚未 sbtd_plan。开发任务先调用 sbtd_plan。";
const NOTICE_SUMMARY = "尚未 sbtd_plan，先调用 sbtd_plan。";

function sessionFromAgent(agent: { id?: string } | undefined): string {
  const exec: PlanToolExec = {};
  const id = agent?.id;
  if (typeof id === "string" && id.length > 0) {
    exec.agent = { id };
  }
  return sessionIdFromExec(exec);
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

function stringField(
  record: Record<string, unknown> | undefined,
  key: string,
): string | undefined {
  const value = record?.[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function commandOf(args: unknown): string {
  const record = asRecord(args);
  return stringField(record, "command") ?? stringField(record, "cmd") ?? "";
}

function pathOf(args: unknown): string | undefined {
  const record = asRecord(args);
  return (
    stringField(record, "path") ??
    stringField(record, "file_path") ??
    stringField(record, "filePath")
  );
}

function relToCwd(file: string, cwd: string): string {
  return relative(cwd, resolve(cwd, file))
    .split(sep)
    .join("/");
}

function pathsFromBash(command: string): string[] {
  const out: string[] = [];
  for (const token of command.split(/\s+/)) {
    if (
      token.includes("/") ||
      README.test(token) ||
      IMPL_EXT.test(token) ||
      /^(?:src|app|packages|features|maestro|\.trellis)/.test(token)
    ) {
      out.push(token.replace(/^['"]|['"]$/g, ""));
    }
  }
  return out;
}

function classifyRel(
  rel: string,
): "readme" | "exempt" | "production" | "other" {
  if (rel === "" || rel.startsWith("..")) {
    return "other";
  }
  if (README.test(rel)) {
    return "readme";
  }
  if (EXEMPT.test(rel)) {
    return "exempt";
  }
  if (/^(?:src|app|packages)(?:\/|$)/.test(rel) && !rel.endsWith(".md")) {
    return "production";
  }
  return "other";
}

function denyReview(kind: "legacy" | "refactor" | "ddd" | "ddia" | "release"): {
  kind: "deny";
  reason: string;
} {
  return {
    kind: "deny",
    reason: `required gate 未 passed，请先调用 sbtd_review kind=${kind}。`,
  };
}

function unpassedRequired(
  gate: { requirement: string; state: string } | undefined,
): boolean {
  return gate?.requirement === "required" && gate.state !== "passed";
}

function remediationAllow(
  gate: { reviewStatus?: string } | undefined,
  status: string,
): boolean {
  return gate?.reviewStatus === status;
}

function isGitAllow(command: string): boolean {
  return GIT_ALLOW.test(command) && !GIT_CHAIN.test(command);
}

function isMutatingBash(command: string): boolean {
  if (command.length === 0) {
    return false;
  }
  if (isGitAllow(command)) {
    return false;
  }
  return MUTATING_BASH.test(command);
}

function primaryClass(
  exec: ToolExec,
  cwd: string,
): "readme" | "exempt" | "production" | "other" {
  const args = exec.arguments;
  const direct = pathOf(args);
  const command = exec.name === "bash" ? commandOf(args) : "";
  const files = direct !== undefined ? [direct] : pathsFromBash(command);
  if (files.length === 0) {
    return "other";
  }
  let sawExempt = false;
  let sawReadme = false;
  for (const file of files) {
    const kind = classifyRel(relToCwd(file, cwd));
    if (kind === "production") {
      return "production";
    }
    if (kind === "readme") {
      sawReadme = true;
    }
    if (kind === "exempt") {
      sawExempt = true;
    }
  }
  if (sawReadme) {
    return "readme";
  }
  return sawExempt ? "exempt" : "other";
}

function isDataPathExec(exec: ToolExec): boolean {
  const args = exec.arguments;
  const direct = pathOf(args);
  const command = exec.name === "bash" ? commandOf(args) : "";
  const files = direct !== undefined ? [direct] : pathsFromBash(command);
  const hay = files.join(" ");
  return DATA_PATH.test(hay);
}

function isRmOrPkgBusiness(exec: ToolExec, cwd: string): boolean {
  if (exec.name !== "bash") {
    return false;
  }
  const command = commandOf(exec.arguments);
  if (RM_BASH.test(command)) {
    const cls = primaryClass(exec, cwd);
    return cls === "production" || cls === "other";
  }
  if (PKG_MGR.test(command)) {
    return /(?:^|\s)(?:src|app|packages)\b|\.\/(?:src|app|packages)/.test(
      command,
    );
  }
  return false;
}

export function gatePreExecute(
  exec: ToolExec,
  host?: Pick<HooksHost, "cwd" | "workflowMode">,
): PreToolDecision | undefined {
  const name = exec.name;
  if (name === "view") {
    return undefined;
  }
  if (name === "str_replace_editor" && commandOf(exec.arguments) === "view") {
    return undefined;
  }
  const command = name === "bash" ? commandOf(exec.arguments) : "";
  if (name === "bash" && isGitAllow(command)) {
    return undefined;
  }
  const mutating =
    MUTATION_TOOLS[name] === true ||
    (name === "bash" && isMutatingBash(command));
  if (!mutating) {
    return undefined;
  }

  const cwd = host?.cwd ?? process.cwd();
  const cls = primaryClass(exec, cwd);
  if (cls === "readme") {
    return undefined;
  }
  const session = getSession(sessionFromAgent(exec.agent));
  const plan = session.plan;
  if (isRmOrPkgBusiness(exec, cwd) && plan === undefined) {
    return { kind: "ask", reason: ASK_RM_PKG };
  }
  if (plan === undefined) {
    if (cls === "other") {
      return undefined;
    }
    return { kind: "ask", reason: ASK_PLAN };
  }

  if (cls === "exempt") {
    return undefined;
  }
  // R2 Q3 A: required book gate denies are strict-only; default/lite 降级为
  // pre-step inject notice，不拦截。无 plan 的 ask 在所有模式保留。
  const strict =
    resolveWorkflowMode({ host: host?.workflowMode, cwd: host?.cwd }).mode ===
    "strict";
  if (!strict) {
    // Full docs-grill DDD remains mandatory in every workflow mode.
    if (cls === "production" && unpassedRequired(plan.gates.ddd)) {
      return denyReview("ddd");
    }
    return undefined;
  }
  if (
    name === "bash" &&
    PUBLISH_BASH.test(command) &&
    unpassedRequired(plan.gates.release)
  ) {
    return denyReview("release");
  }
  if (cls !== "production") {
    return undefined;
  }

  if (
    unpassedRequired(plan.gates.legacy) &&
    !remediationAllow(plan.gates.legacy, "seam-required")
  ) {
    return denyReview("legacy");
  }
  if (
    unpassedRequired(plan.gates.refactor) &&
    !remediationAllow(plan.gates.refactor, "refactor-first")
  ) {
    return denyReview("refactor");
  }
  if (unpassedRequired(plan.gates.ddd)) {
    return denyReview("ddd");
  }
  if (unpassedRequired(plan.gates.ddia) && isDataPathExec(exec)) {
    return denyReview("ddia");
  }
  return undefined;
}

function contentText(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }
  if (!Array.isArray(content)) {
    return "";
  }
  const parts: string[] = [];
  for (const block of content) {
    const record = asRecord(block);
    const text = stringField(record, "text");
    if (text !== undefined) {
      parts.push(text);
    }
  }
  return parts.join("\n");
}

function messagesText(messages: PreStepMessage[] | undefined): string {
  if (messages === undefined) {
    return "";
  }
  return messages.map((message) => contentText(message.content)).join("\n");
}

export async function runPreStep(
  payload: PreStepPayload,
  next: () => Promise<PreStepDecision>,
  host?: Pick<HooksHost, "cwd" | "workflowMode">,
): Promise<PreStepDecision> {
  const decision = await next();
  if (decision.kind !== "enter") {
    return decision;
  }
  const session = getSession(sessionFromAgent(payload.agent));
  const text = `${messagesText(payload.messages)}\n${messagesText(decision.messages)}`;
  const mode = resolveWorkflowMode({
    host: host?.workflowMode,
    cwd: host?.cwd,
  });
  let notice: string;
  let summary: string;
  if (session.plan === undefined && DEV_INTENT.test(text)) {
    notice = NOTICE_TEXT;
    summary = NOTICE_SUMMARY;
  } else if (session.plan !== undefined && mode.mode !== "strict") {
    const pending = Object.entries(session.plan.gates)
      .filter(([kind, gate]) => kind !== "ddd" && unpassedRequired(gate))
      .map(([kind]) => kind);
    if (pending.length === 0) return decision;
    notice = `required book gate 未 passed：${pending.join(", ")}。请调用 sbtd_review；当前模式仅告警，不拦截。`;
    summary = "required book gate 未 passed，仅告警。";
  } else {
    return decision;
  }
  const modeText = `workflowMode: ${mode.mode}; workflowModeSource: ${mode.source}；${describeWorkflowMode(mode)}`;
  return {
    kind: "enter",
    messages: [
      ...decision.messages,
      {
        id: "dsh-sbtd-pre-step-notice",
        role: "user",
        content: [{
          type: "text",
          text: `${notice}\n${modeText}${mode.note ? `\n${mode.note}` : ""}`,
        }],
        source: {
          kind: "plugin",
          plugin: PLUGIN_NAME,
          form: "notice",
          summary: `${summary} ${modeText}`,
        },
      },
    ],
  };
}

export function registerHooks(ctx: HooksHost): void {
  const workflowMode = optionalHostBag<string>(ctx, "workflowMode");
  const host = {
    cwd: optionalHostCwd(ctx),
    ...(workflowMode !== undefined ? { workflowMode } : {}),
  };
  ctx.on(PRE_EXECUTE_EVENT, async (exec, next) => {
    const decision = gatePreExecute(exec, host);
    if (decision === undefined) {
      return next();
    }
    return decision;
  });
  ctx.on(PRE_STEP_EVENT, async (payload, next) => runPreStep(payload, next, host));
}
