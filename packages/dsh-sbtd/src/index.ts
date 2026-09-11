import {
  type CommandsHost,
  registerCommand,
  resolveCommandHost,
} from "./commands/sbtd.js";
import { type HooksHost, registerHooks } from "./hooks.js";
import { registerSection, type SectionHost } from "./section.js";
import {
  type BddHostOptions,
  type BddPluginHost,
  registerBddTool,
  resolveBddHost,
} from "./tools/bdd.js";
import { registerClarifyTool } from "./tools/clarify.js";
import {
  type E2eHostOptions,
  type E2ePluginHost,
  registerE2eTool,
  resolveE2eHost,
} from "./tools/e2e.js";
import {
  type LessonsHostOptions,
  registerLessonsTool,
  resolveLessonsHost,
} from "./tools/lessons.js";
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
export const inject = ["tools", "systemPrompt", "commands"] as const;

export type PluginHost = SectionHost &
  ToolsHost &
  HooksHost &
  CommandsHost &
  ValidatePluginHost &
  BddPluginHost &
  E2ePluginHost & {
    /** Optional explicit validate trust handles (Q1A). Prefer validateHost. */
    validateHost?: ValidateHostOptions;
    /** Optional explicit bdd trust handles (Q1C). Prefer bddHost. */
    bddHost?: BddHostOptions;
    /** Optional explicit e2e trust handles (Q4A). Prefer e2eHost. */
    e2eHost?: E2eHostOptions;
    /** Optional explicit lessons trust handles (Q4A). Prefer lessonsHost. */
    lessonsHost?: LessonsHostOptions;
  };

export {
  createSbtdCommand,
  executeSbtdCommand,
  parseSbtdArgv,
  registerCommand,
  resolveCommandHost,
  runSbtdCommand,
  SBTD_COMMAND_DESCRIPTION,
  SBTD_COMMAND_NAME,
} from "./commands/sbtd.js";
export type {
  CommandInvocation,
  CommandResult,
} from "./commands/sbtd.js";
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
  BDD_INTENTS,
  catalogFeatures,
  createBddTool,
  detectFeatureConvention,
  modelSchemaForbidsTrustHandles as bddModelSchemaForbidsTrustHandles,
  pickBddInput,
  registerBddTool,
  resolveBddHost,
  resolveFeatureTargetPath,
  SBTD_BDD_TOOL_NAME,
  sbtdBdd,
  validateExtraPaths,
} from "./tools/bdd.js";
export {
  CLARIFY_MODES,
  createClarifyTool,
  GRILL_WITH_DOCS_FACT,
  registerClarifyTool,
  SBTD_CLARIFY_TOOL_NAME,
  sbtdClarify,
} from "./tools/clarify.js";
export {
  createE2eTool,
  defaultRunMaestro,
  defaultRunPlaywright,
  detectE2eConvention,
  E2E_ACTIONS,
  E2E_MODES,
  E2E_OUTCOMES,
  E2E_SURFACES,
  modelSchemaForbidsTrustHandles as e2eModelSchemaForbidsTrustHandles,
  pickE2eInput,
  registerE2eTool,
  resolveE2eHost,
  resolveE2eTargetPath,
  resolveReportedMode,
  SBTD_E2E_TOOL_NAME,
  sbtdE2e,
} from "./tools/e2e.js";
export {
  createLessonsTool,
  LESSON_EVENTS,
  LESSON_INTENTS,
  modelSchemaForbidsTrustHandles as lessonsModelSchemaForbidsTrustHandles,
  pickLessonsInput,
  registerLessonsTool,
  resolveLessonsHost,
  SBTD_LESSONS_TOOL_NAME,
  sbtdLessons,
} from "./tools/lessons.js";
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
  bindBridgeOuter,
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
  registerBddTool(ctx, resolveBddHost(ctx));
  registerE2eTool(ctx, resolveE2eHost(ctx));
  registerLessonsTool(ctx, resolveLessonsHost(ctx));
  registerHooks(ctx);
  registerCommand(ctx, resolveCommandHost(ctx));
}
