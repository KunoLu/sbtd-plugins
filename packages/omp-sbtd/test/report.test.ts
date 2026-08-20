import { describe, expect, it } from "vitest";
import type { ToolEvidenceRecord } from "../src/environment/tool-evidence.ts";
import {
  buildSbtdReport,
  formalArtifactDescriptorSchema,
  MAX_RENDERED_SBTD_REPORT_BYTES,
  MAX_REPORT_TOOL_EVIDENCE_RECORDS,
  observeProviderSnapshot,
  parseRenderedSbtdReport,
  providerUnavailableSnapshot,
  renderSbtdReport,
} from "../src/report/index.ts";
import {
  createStateService,
  defaultSessionState,
  deriveEffectiveControlState,
  restoreSessionState,
  SBTD_STATE_CUSTOM_TYPE,
} from "../src/state/index.ts";
import {
  autoRoutePublicSbtdReport,
  currentPublicSbtdReport,
  legacyAsciiSbtdReport,
} from "./fixtures/p0-reports.ts";

const observedAt = "2026-07-26T00:00:00.000Z";

const validationReport = {
  schemaVersion: 1 as const,
  checkRequirement: "required" as const,
  validationStatus: "passed" as const,
  e2eMode: "mock-backed" as const,
  observedAt,
  evidenceEnvelope: {
    evidenceSource: "developer-local" as const,
    sourceRevision: "dirty" as const,
    environmentAlignment: "unverified" as const,
    evidencePublication: "local-only" as const,
  },
  formalArtifact: {
    status: "available" as const,
    runner: "playwright" as const,
    reportPath:
      "tests/e2e/reports/html/playwright-report-validation-main-2026_07_26-00_00_00.html",
    markdownPath:
      "tests/e2e/reports/html/playwright-report-validation-main-2026_07_26-00_00_00.md",
    observedAt,
    report: {
      sizeBytes: 42,
      sha256: "a".repeat(64),
      modifiedAt: observedAt,
    },
    markdown: {
      sizeBytes: 24,
      sha256: "b".repeat(64),
      modifiedAt: observedAt,
    },
  },
};

const providerObservation = {
  schemaVersion: 1 as const,
  availability: "available" as const,
  fallback: "unavailable" as const,
  selection: "selected" as const,
  provider: "openai",
  model: "gpt-5.6",
  observedAt,
};

describe("Feature: 验证报告与 Provider 观察", () => {
  it("Scenario: 报告如实保留非完整链路验证模式", () => {
    const state = {
      ...defaultSessionState(observedAt),
      validationReport,
      providerObservation,
    };
    const model = buildSbtdReport({
      state,
      effectiveControlState: deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      ),
      toolEvidence: [],
      provider: providerObservation,
    });

    const rendered = renderSbtdReport(model);
    expect(rendered.json).toBe(renderSbtdReport(model).json);
    expect(JSON.parse(rendered.json)).toMatchObject({
      validation: {
        validationStatus: "passed",
        e2eMode: "mock-backed",
      },
      evidence: {
        evidenceSource: "developer-local",
        sourceRevision: "dirty",
        evidencePublication: "local-only",
      },
    });
    expect(rendered.markdown).toContain("实际 E2E Mode：mock-backed");
    expect(rendered.markdown).toContain("完整链路：否");
    expect(rendered.markdown).toContain("developer-local");
    expect(rendered.markdown).toContain("dirty");
    expect(rendered.markdown).toContain("local-only");
  });

  it("Scenario: 公共报告只接受唯一、带围栏的当前 JSON 文档", () => {
    expect(parseRenderedSbtdReport(currentPublicSbtdReport())).toMatchObject({
      workflow: { route: "auto" },
    });
    expect(parseRenderedSbtdReport(autoRoutePublicSbtdReport())).toMatchObject({
      workflow: { route: "auto", automaticRoute: "bugfix" },
    });
    expect(parseRenderedSbtdReport(legacyAsciiSbtdReport())).toBeUndefined();
    expect(
      parseRenderedSbtdReport(
        `${currentPublicSbtdReport()}\n${currentPublicSbtdReport()}`,
      ),
    ).toBeUndefined();
  });

  it("Scenario: 陈旧、目录或不同 Stem 的报告配对保持阻断", () => {
    expect(
      formalArtifactDescriptorSchema.safeParse({
        ...validationReport.formalArtifact,
        markdownPath:
          "tests/e2e/reports/html/playwright-report-other-main-2026_07_26-00_00_00.md",
      }).success,
    ).toBe(false);
    expect(
      formalArtifactDescriptorSchema.safeParse({
        ...validationReport.formalArtifact,
        markdownPath: validationReport.formalArtifact.reportPath,
      }).success,
    ).toBe(false);
    expect(
      formalArtifactDescriptorSchema.safeParse({
        ...validationReport.formalArtifact,
        reportPath:
          "tests/e2e/reports/html/playwright-report-validation-main-2026_07_26-00_00_00.json",
      }).success,
    ).toBe(false);
    expect(
      formalArtifactDescriptorSchema.safeParse({
        status: "blocked",
        observedAt,
        blockedReason: "formal-report-required",
        recoveryCode: "create-fresh-same-stem-report-pair",
      }).success,
    ).toBe(true);
  });

  it("Scenario: 有效版本化验证与 Provider 状态在 Session 重放后保留", () => {
    const entries: unknown[] = [];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => entries.push({ customType, data }),
    });

    service.recordValidationReport(validationReport);
    service.recordProviderObservation(providerObservation);

    expect(service.restore()).toMatchObject({
      validationReport,
      providerObservation,
    });
    expect(restoreSessionState([])).not.toHaveProperty("validationReport");
  });

  it("Scenario: 无效的版本化验证或 Provider 状态失败关闭", () => {
    expect(() =>
      restoreSessionState([
        {
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: {
            ...defaultSessionState(observedAt),
            validationReport,
            providerObservation: {
              ...providerObservation,
              disabledCause: "never-persist-this-cause",
            },
          },
        },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
    expect(() =>
      restoreSessionState([
        {
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: {
            ...defaultSessionState(observedAt),
            validationReport: {
              ...validationReport,
              schemaVersion: 2,
            },
          },
        },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
    expect(() =>
      restoreSessionState([
        {
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: {
            ...defaultSessionState(observedAt),
            validationReport: {
              ...validationReport,
              evidenceEnvelope: {
                ...validationReport.evidenceEnvelope,
                evidencePublication: "published",
              },
            },
          },
        },
      ]),
    ).toThrow("Invalid latest KPi SBTD session state");
  });

  it("Scenario: Provider 不可用时保留显式阻断", () => {
    const safeReads: string[] = [];
    const current = observeProviderSnapshot(
      {
        current: () =>
          Object.defineProperties(
            {},
            {
              provider: {
                enumerable: true,
                get: () => {
                  safeReads.push("provider");
                  return "openai";
                },
              },
              id: {
                enumerable: true,
                get: () => {
                  safeReads.push("id");
                  return "gpt-5.6";
                },
              },
              headers: {
                enumerable: true,
                get: (): never => {
                  throw new Error("sensitive model fields must not be read");
                },
              },
              metadata: {
                enumerable: true,
                get: (): never => {
                  throw new Error("sensitive model fields must not be read");
                },
              },
              credentialMetadata: {
                enumerable: true,
                get: (): never => {
                  throw new Error("sensitive model fields must not be read");
                },
              },
              disabledCause: {
                enumerable: true,
                get: (): never => {
                  throw new Error("sensitive model fields must not be read");
                },
              },
            },
          ),
      },
      observedAt,
    );
    const unavailable = providerUnavailableSnapshot("openai", observedAt);

    expect(current).toEqual(providerObservation);
    expect(safeReads).toEqual(["provider", "id"]);
    expect(unavailable).toMatchObject({
      availability: "unavailable",
      fallback: "unavailable",
      selection: "blocked",
      provider: "openai",
    });
    expect(JSON.stringify(unavailable)).not.toContain("disabledCause");
    expect(JSON.stringify(current)).not.toContain("headers");
    expect(JSON.stringify(current)).not.toContain("metadata");
    expect(JSON.stringify(current)).not.toContain("disabledCause");
  });

  it("Scenario: 公共报告上限按 UTF-8 字节而非 UTF-16 单元计量", () => {
    const report = currentPublicSbtdReport();

    const multibytePadded = `${report}\n${"界".repeat(32 * 1024 - report.length - 2)}`;
    expect(multibytePadded.length).toBeLessThan(32 * 1024);
    expect(Buffer.byteLength(multibytePadded, "utf8")).toBeGreaterThan(
      MAX_RENDERED_SBTD_REPORT_BYTES,
    );
    expect(parseRenderedSbtdReport(multibytePadded)).toBeUndefined();

    const annotated = `${report}\n备注：${"界".repeat(100)}`;
    expect(Buffer.byteLength(annotated, "utf8")).toBeLessThanOrEqual(
      MAX_RENDERED_SBTD_REPORT_BYTES,
    );
    expect(parseRenderedSbtdReport(annotated)).toMatchObject({
      workflow: { route: "auto" },
    });

    const room =
      MAX_RENDERED_SBTD_REPORT_BYTES - Buffer.byteLength(report, "utf8") - 2;
    const asciiPadded = `${report}\n${" ".repeat(room)}`;
    expect(Buffer.byteLength(asciiPadded, "utf8")).toBeLessThanOrEqual(
      MAX_RENDERED_SBTD_REPORT_BYTES,
    );
    expect(parseRenderedSbtdReport(asciiPadded)).toMatchObject({
      workflow: { route: "auto" },
    });
  });

  it("Scenario: 上限工具证据的最坏渲染仍遵守公共报告字节约束并可往返解析", () => {
    const state = {
      ...defaultSessionState(observedAt),
      validationReport,
      providerObservation,
    };
    const base = buildSbtdReport({
      state,
      effectiveControlState: deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      ),
      toolEvidence: [],
      provider: providerObservation,
    });
    const worstCaseEvidence = Array.from(
      { length: MAX_REPORT_TOOL_EVIDENCE_RECORDS },
      (_, index) => ({
        toolId: `t${String(index)}${"a".repeat(128)}`.slice(0, 128),
        capability: `c${String(index)}${"b".repeat(128)}`.slice(0, 128),
        installation: "not-needed" as const,
        configuration: "not-configured" as const,
        callability: "unavailable" as const,
        projectReadiness: "not-needed" as const,
        freshness: "not-needed" as const,
        observedAt,
      }),
    );
    const rendered = renderSbtdReport({
      ...base,
      toolEvidence: worstCaseEvidence,
    });
    const publicText = [
      rendered.markdown.trimEnd(),
      "```json",
      rendered.json,
      "```",
    ].join("\n\n");

    expect(Buffer.byteLength(publicText, "utf8")).toBeLessThanOrEqual(
      MAX_RENDERED_SBTD_REPORT_BYTES,
    );
    const parsed = parseRenderedSbtdReport(publicText);
    expect(parsed).toMatchObject({ workflow: { route: "auto" } });
    expect(parsed?.toolEvidence).toHaveLength(MAX_REPORT_TOOL_EVIDENCE_RECORDS);
  });

  it("Scenario: 超出公共报告预算的工具证据按确定性顺序截断", () => {
    const state = defaultSessionState(observedAt);
    const records: ToolEvidenceRecord[] = Array.from(
      { length: MAX_REPORT_TOOL_EVIDENCE_RECORDS + 8 },
      (_, index) => ({
        key: "a".repeat(64),
        toolId: `tool-${String(index).padStart(2, "0")}`,
        capability: "probe",
        subject: "external-tool" as const,
        installation: "installed" as const,
        configuration: "configured" as const,
        callability: "callable" as const,
        projectReadiness: "ready" as const,
        freshness: "current" as const,
        observedAt,
        evidence: [],
        probeRegistryVersion: "1",
        kitRevision: "b".repeat(64),
        scopeKey: "scope",
        inputFingerprint: "fingerprint",
        validUntil: observedAt,
      }),
    );

    const model = buildSbtdReport({
      state,
      effectiveControlState: deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      ),
      toolEvidence: records,
    });

    expect(model.toolEvidence).toHaveLength(MAX_REPORT_TOOL_EVIDENCE_RECORDS);
    expect(model.toolEvidence.map((entry) => entry.toolId)).toEqual(
      records
        .slice(0, MAX_REPORT_TOOL_EVIDENCE_RECORDS)
        .map((record) => record.toolId),
    );
  });
});
