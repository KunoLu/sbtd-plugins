import { type HooksHost, registerHooks } from "./hooks.js";
import { registerSection, type SectionHost } from "./section.js";
import { registerClarifyTool } from "./tools/clarify.js";
import { registerPlanTool, type ToolsHost } from "./tools/plan.js";
import { registerReviewTool } from "./tools/review.js";
import { registerSpecTool } from "./tools/spec.js";
import { registerTicketsTool } from "./tools/tickets.js";
import {
  registerValidateTool,
  resolveValidateHost,
  type ValidateHostOptions,
  type ValidatePluginHost,
} from "./tools/validate.js";

export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export type PluginHost = SectionHost &
  ToolsHost &
  HooksHost &
  ValidatePluginHost & {
    /** Optional explicit validate trust handles (Q1A). Prefer validateHost. */
    validateHost?: ValidateHostOptions;
  };

export {
  PRE_EXECUTE_EVENT,
  PRE_STEP_EVENT,
  registerHooks,
} from "./hooks.js";
export {
  registerSection,
  SBTD_SECTION_NAME,
  SBTD_SECTION_ORDER,
  SBTD_SECTION_TEXT,
} from "./section.js";
export { getSession, restore, serialize } from "./state.js";
export {
  CLARIFY_MODES,
  createClarifyTool,
  GRILL_WITH_DOCS_FACT,
  registerClarifyTool,
  SBTD_CLARIFY_TOOL_NAME,
  sbtdClarify,
} from "./tools/clarify.js";
export {
  createPlanTool,
  inferRequirements,
  registerPlanTool,
  SBTD_PLAN_TOOL_NAME,
  sbtdPlan,
  sessionIdFromExec,
  taskIdFromSummary,
} from "./tools/plan.js";
export {
  createReviewTool,
  REVIEW_KINDS,
  REVIEW_TITLES,
  registerReviewTool,
  SBTD_REVIEW_TOOL_NAME,
  sbtdReview,
} from "./tools/review.js";
export {
  createSpecTool,
  registerSpecTool,
  SBTD_SPEC_TOOL_NAME,
  sbtdSpec,
} from "./tools/spec.js";
export {
  createTicketsTool,
  registerTicketsTool,
  SBTD_TICKETS_TOOL_NAME,
  sbtdTickets,
} from "./tools/tickets.js";
export {
  bindBridgeSignal,
  createToolsMcpBridge,
  createValidateTool,
  discoverProjectTestCommand,
  pickValidateInput,
  registerValidateTool,
  resolveValidateHost,
  SBTD_VALIDATE_TOOL_NAME,
  sbtdValidate,
  VALIDATE_PHASES,
} from "./tools/validate.js";

export function apply(ctx: PluginHost): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  registerSection(ctx);
  registerPlanTool(ctx);
  registerReviewTool(ctx);
  registerClarifyTool(ctx);
  registerSpecTool(ctx);
  registerTicketsTool(ctx);
  registerValidateTool(ctx, resolveValidateHost(ctx));
  registerHooks(ctx);
}
