import type { WorkflowRouteId } from "../src/workflow/index.ts";

/**
 * Versioned deterministic-classifier regression corpus.
 *
 * Scope note (P1-02): this is the repository synthetic/sanitized regression
 * set. It proves parser mechanics only. The 100+ real sanitized NeoX
 * Japanese/Chinese/English production prompts remain promotion-time accuracy
 * evidence and are explicitly not part of this corpus; no production-accuracy
 * claim is derived from these entries.
 */

export const classifierCorpusVersion = 1;

export interface ClassifierCorpusEntry {
  readonly id: string;
  readonly language: "en" | "zh" | "ja";
  readonly prompt: string;
  /** Undefined route means the prompt must stay unclassified. */
  readonly expectedRoute: WorkflowRouteId | undefined;
  readonly expectedFacts?: {
    readonly existingProductionCode?: boolean;
    readonly existingBehaviorBug?: boolean;
  };
  readonly riskLevel: "low" | "medium" | "high";
  readonly source: "rc6-review" | "synthetic";
}

export const classifierCorpus: readonly ClassifierCorpusEntry[] = [
  {
    id: "rc6-ja-display-bug",
    language: "ja",
    prompt: "患者名が表示されない不具合を修正してください",
    expectedRoute: "bugfix",
    expectedFacts: { existingBehaviorBug: true },
    riskLevel: "high",
    source: "rc6-review",
  },
  {
    id: "rc6-ja-existing-code-bug",
    language: "ja",
    prompt: "既存のWPFコードで患者名が表示されないバグを修正してください",
    expectedRoute: "bugfix",
    expectedFacts: { existingProductionCode: true, existingBehaviorBug: true },
    riskLevel: "high",
    source: "rc6-review",
  },
  {
    id: "rc6-zh-fix-problem",
    language: "zh",
    prompt: "修复患者姓名不显示的问题",
    expectedRoute: "bugfix",
    expectedFacts: { existingBehaviorBug: true },
    riskLevel: "high",
    source: "rc6-review",
  },
  {
    id: "rc6-zh-existing-production-defect",
    language: "zh",
    prompt: "请修复现有生产代码中的患者姓名显示缺陷",
    expectedRoute: "bugfix",
    expectedFacts: { existingProductionCode: true, existingBehaviorBug: true },
    riskLevel: "high",
    source: "rc6-review",
  },
  {
    id: "rc6-en-review-capitalized",
    language: "en",
    prompt: "Review this code",
    expectedRoute: "review",
    riskLevel: "medium",
    source: "rc6-review",
  },
  {
    id: "rc6-zh-review",
    language: "zh",
    prompt: "请代码审查",
    expectedRoute: "review",
    riskLevel: "medium",
    source: "rc6-review",
  },
  {
    id: "ctx-ja-context-before-instruction",
    language: "ja",
    prompt:
      "背景: 患者管理システムの保守。\n患者名が表示されない不具合を修正してください",
    expectedRoute: "bugfix",
    expectedFacts: { existingBehaviorBug: true },
    riskLevel: "high",
    source: "synthetic",
  },
  {
    id: "ctx-zh-context-before-instruction",
    language: "zh",
    prompt: "背景：患者管理模块持续报错\n请修复患者姓名不显示的问题",
    expectedRoute: "bugfix",
    expectedFacts: { existingBehaviorBug: true },
    riskLevel: "high",
    source: "synthetic",
  },
  {
    id: "ctx-en-context-before-instruction",
    language: "en",
    prompt:
      "Context: the patient admin module.\nPlease fix the bug where the patient name is missing",
    expectedRoute: "bugfix",
    expectedFacts: { existingBehaviorBug: true },
    riskLevel: "high",
    source: "synthetic",
  },
  {
    id: "ctx-en-review-after-context",
    language: "en",
    prompt: "Here is the change summary for the release.\nreview this code",
    expectedRoute: "review",
    riskLevel: "medium",
    source: "synthetic",
  },
  {
    id: "ja-review-request",
    language: "ja",
    prompt: "このコードをレビューしてください",
    expectedRoute: "review",
    riskLevel: "medium",
    source: "synthetic",
  },
  {
    id: "mention-prefixed-fix",
    language: "zh",
    prompt: "@reviewer 请修复现有生产代码中的患者姓名显示缺陷",
    expectedRoute: "bugfix",
    expectedFacts: { existingProductionCode: true, existingBehaviorBug: true },
    riskLevel: "medium",
    source: "synthetic",
  },
] as const;
