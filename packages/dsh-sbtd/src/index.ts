import { registerSection, type SectionHost } from "./section.js";
import { registerPlanTool, type ToolsHost } from "./tools/plan.js";

export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export type PluginHost = SectionHost & ToolsHost;

export {
  registerSection,
  SBTD_SECTION_NAME,
  SBTD_SECTION_ORDER,
  SBTD_SECTION_TEXT,
} from "./section.js";
export { getSession, restore, serialize } from "./state.js";
export {
  createPlanTool,
  inferRequirements,
  registerPlanTool,
  SBTD_PLAN_TOOL_NAME,
  sbtdPlan,
  sessionIdFromExec,
  taskIdFromSummary,
} from "./tools/plan.js";

export function apply(ctx: PluginHost): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  registerSection(ctx);
  registerPlanTool(ctx);
}
