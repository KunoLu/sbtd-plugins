export const SBTD_SECTION_NAME = "sbtd";
export const SBTD_SECTION_ORDER = 50;

export const SBTD_SECTION_TEXT = `开发任务先调用 sbtd_plan，未出计划不准改生产代码。
澄清走 sbtd_clarify，完整澄清后必须有 DDD 复审通过态。
改代码前/后的分析、验证走 sbtd_validate / sbtd_e2e，不要直接裸调 MCP 名称。
命中 book gate 必须 sbtd_review 到通过态。
最终输出必须包含结论、文件、验证、跳过原因、风险。
Maestro：缺 Java / CLI / 设备 / 已装 app / app 内测试环境时 blocked，先引导用户。`;

export type SectionHost = {
  systemPrompt: {
    section: (opts: { name: string; order: number; text: string }) => void;
  };
};

export function registerSection(ctx: SectionHost): void {
  ctx.systemPrompt.section({
    name: SBTD_SECTION_NAME,
    order: SBTD_SECTION_ORDER,
    text: SBTD_SECTION_TEXT,
  });
}
