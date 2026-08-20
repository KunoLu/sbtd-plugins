import { z } from "zod";

export const workflowRouteIds = [
  "small-direct-change",
  "bugfix",
  "bdd-user-visible-change",
  "trellis-managed-task",
  "legacy-safe-change",
  "refactoring-pass",
  "data-design-risk",
  "web-runtime-diagnostics",
  "web-e2e-regression",
  "mobile-e2e",
  "release-readiness",
  "review",
] as const;

export type WorkflowRouteId = (typeof workflowRouteIds)[number];
export type DisciplineRequirement =
  | "required"
  | "recommended"
  | "not-needed"
  | "blocked";

export const taskFactsSchema = z
  .object({
    userVisibleBehavior: z.boolean(),
    existingProductionCode: z.boolean(),
    existingBehaviorBug: z.boolean(),
    dataRisk: z.boolean(),
    productionPathRisk: z.boolean(),
    crossRepoScope: z.boolean(),
    domainAmbiguity: z.boolean(),
    durableRequirements: z.boolean(),
    activeTrellisTask: z.boolean().optional().default(false),
    review: z.boolean().optional().default(false),
    webRuntimeDiagnostics: z.boolean().optional().default(false),
    webE2ERegression: z.boolean().optional().default(false),
    mobileE2E: z.boolean().optional().default(false),
    refactoring: z.boolean().optional().default(false),
    weakOrMissingTests: z.boolean().optional().default(false),
    hiddenDependencies: z.boolean().optional().default(false),
    highRegressionRisk: z.boolean().optional().default(false),
    releaseOrDeploy: z.boolean().optional().default(false),
  })
  .strict();

export type TaskFacts = z.input<typeof taskFactsSchema>;

export interface SBTDClassification {
  readonly sdd: DisciplineRequirement;
  readonly bdd: DisciplineRequirement;
  readonly tdd: DisciplineRequirement;
  readonly ddd: DisciplineRequirement;
  readonly route: WorkflowRouteId;
  readonly reasons: string[];
  readonly userVisibleBehavior: boolean;
  readonly existingProductionCode: boolean;
  readonly existingBehaviorBug: boolean;
  readonly dataRisk: boolean;
  readonly productionPathRisk: boolean;
  readonly crossRepoScope: boolean;
  readonly legacySafetyRisk: boolean;
  readonly releaseOrDeploy: boolean;
}

function selectRoute(facts: z.output<typeof taskFactsSchema>): WorkflowRouteId {
  if (facts.review) return "review";
  if (facts.releaseOrDeploy) return "release-readiness";
  if (facts.mobileE2E) return "mobile-e2e";
  if (facts.webE2ERegression) return "web-e2e-regression";
  if (facts.webRuntimeDiagnostics) return "web-runtime-diagnostics";
  if (facts.existingBehaviorBug) return "bugfix";
  if (facts.refactoring) return "refactoring-pass";
  if (facts.dataRisk) return "data-design-risk";
  if (facts.userVisibleBehavior) return "bdd-user-visible-change";
  if (
    facts.existingProductionCode ||
    facts.weakOrMissingTests ||
    facts.hiddenDependencies ||
    facts.highRegressionRisk
  )
    return "legacy-safe-change";
  if (
    facts.activeTrellisTask ||
    facts.crossRepoScope ||
    facts.durableRequirements ||
    facts.domainAmbiguity
  )
    return "trellis-managed-task";
  return "small-direct-change";
}

export function classifyTask(input: TaskFacts): SBTDClassification {
  const facts = taskFactsSchema.parse(input);
  const reasons = [
    ...(facts.userVisibleBehavior ? ["user-visible-behavior"] : []),
    ...(facts.existingProductionCode ? ["existing-production-code"] : []),
    ...(facts.existingBehaviorBug ? ["existing-behavior-bug"] : []),
    ...(facts.dataRisk ? ["data-risk"] : []),
    ...(facts.productionPathRisk ? ["production-path-risk"] : []),
    ...(facts.crossRepoScope ? ["cross-repo-scope"] : []),
    ...(facts.domainAmbiguity ? ["domain-ambiguity"] : []),
    ...(facts.activeTrellisTask ? ["active-trellis-task"] : []),
    ...(facts.review ? ["review-request"] : []),
    ...(facts.webRuntimeDiagnostics ? ["web-runtime-diagnostics"] : []),
    ...(facts.webE2ERegression ? ["web-e2e-regression"] : []),
    ...(facts.mobileE2E ? ["mobile-e2e"] : []),
    ...(facts.refactoring ? ["refactor-request"] : []),
    ...(facts.weakOrMissingTests ? ["weak-or-missing-tests"] : []),
    ...(facts.hiddenDependencies ? ["hidden-dependencies"] : []),
    ...(facts.highRegressionRisk ? ["high-regression-risk"] : []),
    ...(facts.releaseOrDeploy ? ["release-or-deploy"] : []),
  ];
  return {
    sdd: facts.durableRequirements ? "required" : "not-needed",
    bdd: facts.userVisibleBehavior ? "required" : "not-needed",
    tdd: facts.existingBehaviorBug ? "required" : "not-needed",
    ddd: facts.domainAmbiguity ? "required" : "not-needed",
    route: selectRoute(facts),
    reasons,
    userVisibleBehavior: facts.userVisibleBehavior,
    existingProductionCode: facts.existingProductionCode,
    existingBehaviorBug: facts.existingBehaviorBug,
    dataRisk: facts.dataRisk,
    productionPathRisk: facts.productionPathRisk || facts.releaseOrDeploy,
    crossRepoScope: facts.crossRepoScope,
    legacySafetyRisk:
      facts.existingBehaviorBug ||
      facts.weakOrMissingTests ||
      facts.hiddenDependencies ||
      facts.highRegressionRisk,
    releaseOrDeploy: facts.releaseOrDeploy,
  };
}

export interface ObjectiveTaskEvidence {
  readonly rootProjectFacts: boolean;
  readonly trellisWorkflow: boolean;
  readonly activeTrellisTask: boolean;
  readonly persistedBddCoverage: boolean;
  readonly testAssetsPresent: boolean;
  readonly productionSource: boolean;
  readonly changedPathsObserved: boolean;
  readonly changedProductionPath: boolean;
}

function classificationEvidenceReasons(
  evidence: ObjectiveTaskEvidence | undefined,
): string[] {
  if (evidence === undefined) return [];
  return [
    ...(evidence.rootProjectFacts ? ["root-project-facts-observed"] : []),
    ...(evidence.trellisWorkflow ? ["trellis-workflow-observed"] : []),
    ...(evidence.activeTrellisTask ? ["active-trellis-task-observed"] : []),
    ...(evidence.persistedBddCoverage ? ["persisted-bdd-observed"] : []),
    ...(evidence.testAssetsPresent ? ["test-assets-observed"] : []),
    ...(evidence.productionSource ? ["production-source-observed"] : []),
    ...(evidence.changedPathsObserved ? ["changed-paths-observed"] : []),
  ];
}

function hasExplicitChangeIntent(line: string): boolean {
  return (
    /^(?:please\s+)?(?:fix|repair|debug|add|change|update|modify|release|deploy)\b/i.test(
      line,
    ) ||
    /^(?:请)?(?:修复|修正|新增|修改|更新|发布|部署)/.test(line) ||
    /(?:修正|修復|追加|変更|更新|実装)(?:して|してください|したい)/.test(
      line,
    ) ||
    /直して(?:ください)?/.test(line)
  );
}

export function classifyTaskPrompt(
  prompt: string,
  evidence?: ObjectiveTaskEvidence,
): SBTDClassification | undefined {
  const text = prompt
    .replace(/```[\s\S]*?```/g, "")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith(">"))
    .join("\n")
    .trim();
  // Instruction lines: leading context paragraphs, @mentions and list/heading
  // markers must not hide the actionable instruction later in the prompt.
  const lines = text
    .split("\n")
    .map((line) =>
      line
        .trim()
        .replace(/^(?:#{1,6}\s+|[-*]\s+|(?:@[\w-]+\s+)+)/, "")
        .trim(),
    )
    .filter((line) => line.length > 0);
  if (
    text.length === 0 ||
    lines.some(
      (line) =>
        /^(?:review|analyze)\s+(?:this\s+)?(?:quoted|historical)\b/i.test(
          line,
        ) ||
        /^(?:请)?(?:审查|分析)(?:这段)?(?:引用|历史)文本/.test(line) ||
        /(?:引用文|引用文本|履歴).*(?:レビュー|レビューして|分析)/.test(line),
    )
  )
    return undefined;

  const changeIntent = lines.some((line) => hasExplicitChangeIntent(line));
  const documentationTarget = lines.some(
    (line) =>
      /^(?:please\s+)?(?:add|update|modify|change|fix)\s+(?:the\s+)?(?:internal\s+)?(?:(?:api|schema|database(?:\s+migration)?|cache|queue|service|web\s+e2e|mobile\s+e2e|web\s+runtime)\s+)?(?:documentation|docs?|readme|guide|manual)\b/i.test(
        line,
      ) ||
      /^(?:请)?(?:更新|修改|修复|新增|添加).*?(?:文档|说明|指南)$/.test(line),
  );
  const mixedDocumentationChange = lines.some((line) =>
    /^(?:please\s+)?(?:add|update|modify|change|fix)\s+(?:the\s+)?(?:internal\s+)?(?:(?:production|existing)\s+)?(?:code|api|schema|database|migration|cache|queue|service)\b[\s\S]*?(?:\band\b|&|,)\s*(?:the\s+)?(?:documentation|docs?|readme|guide|manual)\b|^(?:please\s+)?(?:add|update|modify|change|fix)\s+(?:the\s+)?(?:internal\s+)?(?:(?:api|schema|database(?:\s+migration)?|cache|queue|service|web\s+e2e|mobile\s+e2e|web\s+runtime)\s+)?(?:documentation|docs?|readme|guide|manual)\b[\s\S]*?(?:\band\b|&|,)\s*(?:the\s+)?(?:(?:production|existing)\s+)?(?:code|api|schema|database|migration|cache|queue|service)\b|^(?:请)?(?:更新|修改|修复|新增|添加)(?:(?:生产|现有))?(?:代码|接口|数据(?:库|迁移|缓存)|队列|服务)[\s\S]*?(?:和|及|与|、)(?:文档|说明|指南)|^(?:请)?(?:更新|修改|修复|新增|添加)(?:文档|说明|指南)[\s\S]*?(?:和|及|与|、)(?:(?:生产|现有))?(?:代码|接口|数据(?:库|迁移|缓存)|队列|服务)/i.test(
      line,
    ),
  );
  const documentationOnly = documentationTarget && !mixedDocumentationChange;
  const semanticChangeIntent = changeIntent && !documentationOnly;
  const webRuntimeDiagnostics =
    /\b(?:web|browser)\s+runtime\b[\s\S]*\b(?:diagnos(?:e|is)|debug|failure|error)\b|\b(?:diagnos(?:e|is)|debug|failure|error)\b[\s\S]*\b(?:web|browser)\s+runtime\b|\b(?:chrome\s+devtools?|devtools)\b[\s\S]*\b(?:diagnos(?:e|is)|debug|failure|error)\b|(?:Web运行时|浏览器运行时)[^\n]*(?:诊断|调试|故障|错误)|(?:诊断|调试|故障|错误)[^\n]*(?:Web运行时|浏览器运行时)|Chrome开发者工具[^\n]*(?:诊断|调试|故障|错误)/i.test(
      text,
    );
  const webE2ERegression =
    /\b(?:web\s+e2e|browser\s+regression)\b|\bplaywright\b[\s\S]*\b(?:e2e|regression|test)\b|\b(?:e2e|regression|test)\b[\s\S]*\bplaywright\b|(?:Web端到端|网页端到端|浏览器回归)|Playwright[^\n]*(?:端到端|回归|测试)|(?:端到端|回归|测试)[^\n]*Playwright/i.test(
      text,
    );
  const mobileE2E =
    /\bmobile\s+e2e\b|\bmaestro\b[\s\S]*\b(?:e2e|regression|test)\b|\b(?:e2e|regression|test)\b[\s\S]*\bmaestro\b|\b(?:ios|android)\b[\s\S]*\b(?:e2e|regression|test)\b|\b(?:e2e|regression|test)\b[\s\S]*\b(?:ios|android)\b|(?:移动端到端|移动E2E|真机回归)|Maestro[^\n]*(?:端到端|回归|测试)|(?:端到端|回归|测试)[^\n]*Maestro/i.test(
      text,
    );
  const routeAction = lines.some(
    (line) =>
      /^(?:please\s+)?(?:run|test|verify|diagnose|debug|fix)\b/i.test(line) ||
      /^(?:请)?(?:运行|测试|验证|诊断|调试|修复)/.test(line),
  );
  const explicitSpecialistRoute =
    !documentationOnly &&
    routeAction &&
    (webRuntimeDiagnostics || webE2ERegression || mobileE2E);
  const review = lines.some(
    (line) =>
      /^review\b/i.test(line) ||
      /^(?:请)?(?:代码)?审查/.test(line) ||
      /(?:コード)?レビュー(?:して|してください|する)/.test(line),
  );
  const facts = {
    userVisibleBehavior:
      semanticChangeIntent &&
      /\b(?:ui|api|cli|user-visible)\b|(?:用户可见|界面|接口)/i.test(text),
    existingProductionCode:
      semanticChangeIntent &&
      (evidence?.changedProductionPath === true ||
        /\b(?:existing production|existing code|production code)\b|(?:现有.*(?:生产|代码))|(?:生产.*代码)|(?:既存(?:の)?\S*コード)|(?:本番)/i.test(
          text,
        )),
    existingBehaviorBug:
      semanticChangeIntent &&
      /\b(?:bug|regression|defect)\b|(?:缺陷|回归|问题|故障|错误)|(?:不具合|バグ|障害)/i.test(
        text,
      ),
    dataRisk:
      semanticChangeIntent &&
      /\b(?:schema|migration|database|cache|queue|stream|cross-service)\b|(?:数据(?:库|迁移|缓存)|跨服务|队列|消息流)/i.test(
        text,
      ),
    productionPathRisk:
      semanticChangeIntent &&
      /\b(?:auth|billing|notification|job|queue|scheduler|integration|deployment)\b|(?:认证|计费|通知|任务队列|调度|集成|部署)/i.test(
        text,
      ),
    crossRepoScope:
      semanticChangeIntent && /\b(?:cross-repo|monorepo)\b|跨仓/i.test(text),
    domainAmbiguity:
      semanticChangeIntent &&
      /\b(?:domain ambiguity|bounded context|ubiquitous language)\b|(?:领域歧义|限界上下文|统一语言)/i.test(
        text,
      ),
    durableRequirements:
      semanticChangeIntent &&
      /\b(?:prd|specification|requirements)\b|(?:需求规格|产品需求|规格)/i.test(
        text,
      ),
    refactoring:
      semanticChangeIntent &&
      /\b(?:refactor|rename|extract|restructure)\b|(?:重构|重命名|提取)/i.test(
        text,
      ),
    weakOrMissingTests:
      semanticChangeIntent &&
      /\b(?:weak|missing)\s+tests?\b|(?:测试(?:较弱|缺失))/i.test(text),
    hiddenDependencies:
      semanticChangeIntent &&
      /\bhidden dependenc(?:y|ies)\b|(?:隐藏依赖)/i.test(text),
    highRegressionRisk:
      semanticChangeIntent &&
      /\bhigh regression risk\b|(?:高回归风险)/i.test(text),
    releaseOrDeploy:
      semanticChangeIntent &&
      /\b(?:release|deploy|rollout)\b|(?:发布|部署|上线)/i.test(text),
    activeTrellisTask: evidence?.activeTrellisTask === true,
    webRuntimeDiagnostics: explicitSpecialistRoute && webRuntimeDiagnostics,
    webE2ERegression: explicitSpecialistRoute && webE2ERegression,
    mobileE2E: explicitSpecialistRoute && mobileE2E,
    review,
  };
  if (!changeIntent && !review && !explicitSpecialistRoute) return undefined;
  const classification = classifyTask(facts);
  const evidenceReasons = classificationEvidenceReasons(evidence);
  return evidenceReasons.length === 0
    ? classification
    : {
        ...classification,
        reasons: [...classification.reasons, ...evidenceReasons],
      };
}
