import { registerSection, type SectionHost } from "./section.js";

export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export {
  registerSection,
  SBTD_SECTION_NAME,
  SBTD_SECTION_ORDER,
  SBTD_SECTION_TEXT,
} from "./section.js";
export { getSession, restore, serialize } from "./state.js";

export function apply(ctx: SectionHost): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  registerSection(ctx);
}
