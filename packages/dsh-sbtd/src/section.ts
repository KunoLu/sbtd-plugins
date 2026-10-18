export const SBTD_SECTION_NAME = "sbtd";
export const SBTD_SECTION_ORDER = 50;

export const SBTD_SECTION_TEXT = `开发任务先调用 sbtd_plan；所有模式无计划生产 edit 仍 ask，先确认计划。
strict 强制无计划禁改和 required book gate；default/lite 的 book gate 仅告警、不拦截，来源见 workflowModeSource。
澄清走 sbtd_clarify；完整 docs grill 后所有模式都必须有 DDD 复审通过态。
改代码前/后的分析、验证走 sbtd_validate / sbtd_e2e；Graft 缺失只 skipped，strict 下结构证据为「未证明」。
book review 走 sbtd_review。
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
