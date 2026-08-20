import { z } from "zod";
import {
  type ToolEvidenceRecord,
  toolEvidenceRecordSchema,
} from "../environment/tool-evidence.js";
import type {
  EffectiveControlState,
  SbtdSessionState,
} from "../state/index.js";
import { type WorkflowRouteId, workflowRouteIds } from "../workflow/index.js";

const safeIdentifierSchema = z
  .string()
  .regex(/^[A-Za-z0-9](?:[A-Za-z0-9._:@/-]{0,127})$/)
  .max(128);
const safeCodeSchema = z
  .string()
  .regex(/^[a-z][a-z0-9-]{0,95}$/)
  .max(96);
/**
 * Public report transport budget in UTF-8 bytes. The renderer must keep every
 * schema-valid report within this bound and the parser enforces it on the
 * assembled public text (Markdown plus the fenced JSON document).
 */
export const MAX_RENDERED_SBTD_REPORT_BYTES = 32 * 1024;
/**
 * Tool-evidence records are the variable-length report section. This cap keeps
 * the worst-case render (128-character identifiers in Markdown and JSON)
 * inside MAX_RENDERED_SBTD_REPORT_BYTES; the builder truncates deterministically
 * and the schema rejects larger documents from the wire.
 */
export const MAX_REPORT_TOOL_EVIDENCE_RECORDS = 24;
const safeRelativePathSchema = z
  .string()
  .min(1)
  .max(512)
  .refine(
    (value) =>
      !value.startsWith("/") &&
      !value.includes("\\") &&
      value
        .split("/")
        .every((part) => /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(part)),
    "report paths must be safe relative paths",
  );

export const checkRequirementSchema = z.enum([
  "required",
  "optional",
  "not-applicable",
]);
export const validationStatusSchema = z.enum([
  "passed",
  "failed",
  "blocked",
  "skipped",
  "not-needed",
]);
export const e2eModeSchema = z.enum([
  "full-stack",
  "contract-backed",
  "mock-backed",
  "app-mocked",
  "backend-only",
  "smoke-only",
  "blocked",
  "not-needed",
]);
export const evidenceEnvelopeSchema = z
  .object({
    evidenceSource: z.enum([
      "developer-local",
      "ci",
      "knowledge-server",
      "not-needed",
    ]),
    sourceRevision: z.enum(["exact", "dirty", "unknown", "not-needed"]),
    environmentAlignment: z.enum([
      "verified",
      "unverified",
      "mismatch",
      "not-needed",
    ]),
    evidencePublication: z.enum([
      "local-only",
      "published",
      "blocked",
      "not-configured",
      "not-needed",
    ]),
  })
  .strict()
  .superRefine((envelope, ctx) => {
    if (
      envelope.sourceRevision === "dirty" &&
      (envelope.evidenceSource !== "developer-local" ||
        envelope.evidencePublication !== "local-only")
    )
      ctx.addIssue({
        code: "custom",
        path: ["evidencePublication"],
        message: "dirty evidence must remain developer-local and local-only",
      });
  });

const fileIntegritySchema = z
  .object({
    sizeBytes: z.number().int().nonnegative(),
    sha256: z.string().regex(/^[0-9a-f]{64}$/),
    modifiedAt: z.string().datetime(),
  })
  .strict();
const formalArtifactReportExtensions: Readonly<
  Record<"playwright" | "api" | "maestro", readonly string[]>
> = {
  playwright: [".html"],
  api: [".html", ".json", ".txt", ".xml"],
  maestro: [".html", ".xml"],
};

export const formalArtifactDescriptorSchema = z.discriminatedUnion("status", [
  z
    .object({
      status: z.literal("available"),
      runner: z.enum(["playwright", "api", "maestro"]),
      reportPath: safeRelativePathSchema,
      markdownPath: safeRelativePathSchema,
      observedAt: z.string().datetime(),
      report: fileIntegritySchema,
      markdown: fileIntegritySchema,
    })
    .strict()
    .superRefine((artifact, ctx) => {
      const reportExtension = artifact.reportPath.slice(
        artifact.reportPath.lastIndexOf("."),
      );
      if (
        !formalArtifactReportExtensions[artifact.runner].includes(
          reportExtension,
        )
      )
        ctx.addIssue({
          code: "custom",
          path: ["reportPath"],
          message: "formal report extension is not valid for its runner",
        });
      if (!artifact.markdownPath.endsWith(".md"))
        ctx.addIssue({
          code: "custom",
          path: ["markdownPath"],
          message: "formal report summary must be a Markdown file",
        });
      const reportStem = artifact.reportPath.slice(
        0,
        artifact.reportPath.lastIndexOf("."),
      );
      const markdownStem = artifact.markdownPath.slice(
        0,
        artifact.markdownPath.lastIndexOf("."),
      );
      if (reportStem !== markdownStem)
        ctx.addIssue({
          code: "custom",
          path: ["markdownPath"],
          message: "formal report and Markdown summary must share one stem",
        });
    }),
  z
    .object({
      status: z.literal("blocked"),
      observedAt: z.string().datetime(),
      blockedReason: safeCodeSchema,
      recoveryCode: safeCodeSchema,
    })
    .strict(),
]);

export const validationReportSchema = z
  .object({
    schemaVersion: z.literal(1),
    checkRequirement: checkRequirementSchema,
    validationStatus: validationStatusSchema,
    e2eMode: e2eModeSchema,
    observedAt: z.string().datetime(),
    evidenceEnvelope: evidenceEnvelopeSchema,
    formalArtifact: formalArtifactDescriptorSchema.optional(),
    blockedReason: safeCodeSchema.optional(),
  })
  .strict()
  .superRefine((report, ctx) => {
    if (
      report.validationStatus === "blocked" &&
      report.blockedReason === undefined
    )
      ctx.addIssue({
        code: "custom",
        path: ["blockedReason"],
        message: "blocked validation requires a safe blocker code",
      });
    if (
      report.formalArtifact?.status === "blocked" &&
      report.validationStatus !== "blocked"
    )
      ctx.addIssue({
        code: "custom",
        path: ["validationStatus"],
        message:
          "blocked formal evidence cannot report another validation status",
      });
    if (
      report.checkRequirement === "not-applicable" &&
      (report.validationStatus !== "not-needed" ||
        report.e2eMode !== "not-needed")
    )
      ctx.addIssue({
        code: "custom",
        message:
          "a non-applicable check must remain not-needed instead of manufacturing validation evidence",
      });
  });

export const providerObservationSchema = z
  .object({
    schemaVersion: z.literal(1),
    provider: safeIdentifierSchema.optional(),
    model: safeIdentifierSchema.optional(),
    roleAlias: safeIdentifierSchema.optional(),
    availability: z.enum(["available", "unavailable", "unknown"]),
    fallback: z.enum(["not-observed", "observed", "unavailable"]),
    selection: z.enum(["selected", "blocked", "unavailable", "unknown"]),
    blockerCode: safeCodeSchema.optional(),
    observedAt: z.string().datetime(),
  })
  .strict()
  .superRefine((snapshot, ctx) => {
    if (
      snapshot.availability === "available" &&
      (snapshot.provider === undefined ||
        snapshot.model === undefined ||
        snapshot.selection !== "selected")
    )
      ctx.addIssue({
        code: "custom",
        message:
          "an available Provider observation requires safe provider/model identifiers and a selected result",
      });
    if (
      snapshot.availability === "unavailable" &&
      (snapshot.selection === "selected" || snapshot.blockerCode === undefined)
    )
      ctx.addIssue({
        code: "custom",
        message:
          "an unavailable Provider observation requires an explicit non-selected blocker",
      });
  });

export type EvidenceEnvelope = z.infer<typeof evidenceEnvelopeSchema>;
export type FormalArtifactDescriptor = z.infer<
  typeof formalArtifactDescriptorSchema
>;
export type ValidationReport = z.infer<typeof validationReportSchema>;
export type ProviderObservation = z.infer<typeof providerObservationSchema>;

/**
 * Persisted, hash-bound fingerprint of a validation evidence envelope that the
 * observer verified against the embedded Kit validator at `verifiedAt`. It is
 * compact by design: scenario identity and report identity are digests only,
 * never file contents or free text. A descriptor is only ever recorded after
 * `executionVerified && revisionCurrent`; it attests a past observation and is
 * always re-derived from a fresh observation before it can justify a release
 * decision.
 */
export const scenarioLinkFingerprintSchema = z
  .object({
    sourceLocatorDigest: z.string().regex(/^[0-9a-f]{64}$/),
    reportSha256: z.string().regex(/^[0-9a-f]{64}$/),
    reportFormat: z.enum(["junit-xml-v1", "playwright-json-v1"]),
  })
  .strict();

export const validationEvidenceDescriptorSchema = z
  .object({
    descriptorVersion: z.literal(1),
    evidenceVersion: z.union([z.literal(1), z.literal(2)]),
    sidecarPath: safeRelativePathSchema,
    sidecarSha256: z.string().regex(/^[0-9a-f]{64}$/),
    repositoryKey: z.string().min(1).max(128),
    sourceRef: z.string().min(1).max(256),
    sourceCommit: z.string().regex(/^[0-9a-f]{40}$/),
    scenarioLinks: z.array(scenarioLinkFingerprintSchema).max(32),
    verifiedAt: z.string().datetime(),
  })
  .strict();

export type ValidationEvidenceDescriptor = z.infer<
  typeof validationEvidenceDescriptorSchema
>;

export interface ReadOnlyCurrentModelQuery {
  readonly current: () => unknown;
}

const safeIdentifier = (value: unknown): string | undefined => {
  const parsed = safeIdentifierSchema.safeParse(value);
  return parsed.success ? parsed.data : undefined;
};

const unknownProviderObservation = (observedAt: string, blockerCode: string) =>
  providerObservationSchema.parse({
    schemaVersion: 1,
    availability: "unknown",
    fallback: "unavailable",
    selection: "unknown",
    blockerCode,
    observedAt,
  });

export function observeProviderSnapshot(
  models: ReadOnlyCurrentModelQuery | undefined,
  observedAt: string,
): ProviderObservation {
  if (models === undefined)
    return unknownProviderObservation(observedAt, "model-facade-unavailable");
  let current: unknown;
  try {
    current = models.current();
  } catch {
    return unknownProviderObservation(observedAt, "model-query-unavailable");
  }
  const identity = z
    .object({ provider: z.unknown(), id: z.unknown() })
    .safeParse(current);
  if (!identity.success)
    return unknownProviderObservation(observedAt, "current-model-unavailable");
  const provider = safeIdentifier(identity.data.provider);
  const model = safeIdentifier(identity.data.id);
  if (provider === undefined || model === undefined)
    return unknownProviderObservation(observedAt, "model-identity-unavailable");
  return providerObservationSchema.parse({
    schemaVersion: 1,
    provider,
    model,
    availability: "available",
    fallback: "unavailable",
    selection: "selected",
    observedAt,
  });
}

export function providerUnavailableSnapshot(
  providerId: unknown,
  observedAt: string,
): ProviderObservation {
  const provider = safeIdentifier(providerId);
  if (provider === undefined)
    return unknownProviderObservation(observedAt, "provider-id-unavailable");
  return providerObservationSchema.parse({
    schemaVersion: 1,
    provider,
    availability: "unavailable",
    fallback: "unavailable",
    selection: "blocked",
    blockerCode: "provider-unavailable",
    observedAt,
  });
}
const workflowReportSchema = z
  .object({
    runtimeMode: z.enum(["enforced", "advisory"]),
    policyProfile: z.enum(["strict", "relaxed"]),
    route: z.string().min(1),
    automaticRoute: z.enum(workflowRouteIds).optional(),
    environmentMode: z.enum([
      "blocked",
      "needs-onboard",
      "degraded",
      "managed",
    ]),
    effectiveControlState: z.enum([
      "advisory",
      "active",
      "preflight-only",
      "blocked",
    ]),
    stage: z
      .object({
        id: z.string().min(1),
        status: z.enum([
          "pending",
          "running",
          "passed",
          "blocked",
          "skipped",
          "not-needed",
        ]),
      })
      .strict()
      .optional(),
    bookGates: z
      .array(
        z
          .object({
            id: z.string().min(1),
            required: z.boolean(),
            gateState: z.enum(["planned", "running", "passed", "blocked"]),
            reviewerStatus: z.string().min(1).optional(),
          })
          .strict(),
      )
      .max(16),
  })
  .strict()
  .superRefine((workflow, ctx) => {
    if (workflow.automaticRoute !== undefined && workflow.route !== "auto")
      ctx.addIssue({
        code: "custom",
        path: ["automaticRoute"],
        message: "automaticRoute requires the raw route to remain auto",
      });
  });

const reportToolEvidenceSchema = z
  .object({
    toolId: safeIdentifierSchema,
    capability: safeIdentifierSchema,
    installation: z.enum(["installed", "missing", "broken", "not-needed"]),
    configuration: z.enum(["configured", "not-configured", "not-needed"]),
    callability: z.enum(["callable", "unavailable", "blocked", "not-needed"]),
    projectReadiness: z.enum(["ready", "not-ready", "blocked", "not-needed"]),
    freshness: z.enum(["current", "stale", "unknown", "not-needed"]),
    observedAt: z.string().datetime(),
  })
  .strict();

export const sbtdReportSchema = z
  .object({
    schemaVersion: z.literal(1),
    workflow: workflowReportSchema,
    validation: validationReportSchema,
    evidence: evidenceEnvelopeSchema,
    toolEvidence: z
      .array(reportToolEvidenceSchema)
      .max(MAX_REPORT_TOOL_EVIDENCE_RECORDS),
    provider: providerObservationSchema,
  })
  .strict();

export function parseRenderedSbtdReport(text: string): SbtdReport | undefined {
  const byteLength = Buffer.byteLength(text, "utf8");
  if (byteLength === 0 || byteLength > MAX_RENDERED_SBTD_REPORT_BYTES)
    return undefined;
  const documents = [
    ...text.matchAll(/^```json[ \t]*\r?\n([\s\S]*?)^```[ \t]*$/gm),
  ];
  if (documents.length !== 1) return undefined;
  try {
    const parsed = sbtdReportSchema.safeParse(
      JSON.parse(documents[0]?.[1] ?? ""),
    );
    return parsed.success ? parsed.data : undefined;
  } catch {
    return undefined;
  }
}

export type SbtdReport = z.infer<typeof sbtdReportSchema>;

export interface ReportBuildInput {
  readonly state: SbtdSessionState;
  readonly effectiveControlState: EffectiveControlState;
  readonly automaticRoute?: WorkflowRouteId;
  readonly toolEvidence: readonly ToolEvidenceRecord[];
  readonly provider?: ProviderObservation;
}

const reportToolEvidence = (
  records: readonly ToolEvidenceRecord[],
): SbtdReport["toolEvidence"] =>
  records
    .flatMap((record) => {
      const parsed = toolEvidenceRecordSchema.safeParse(record);
      if (!parsed.success) return [];
      const toolId = safeIdentifier(parsed.data.toolId);
      const capability = safeIdentifier(parsed.data.capability);
      if (toolId === undefined || capability === undefined) return [];
      return [
        {
          toolId,
          capability,
          installation: parsed.data.installation,
          configuration: parsed.data.configuration,
          callability: parsed.data.callability,
          projectReadiness: parsed.data.projectReadiness,
          freshness: parsed.data.freshness,
          observedAt: parsed.data.observedAt,
        },
      ];
    })
    .sort((left, right) =>
      `${left.toolId}\u0000${left.capability}`.localeCompare(
        `${right.toolId}\u0000${right.capability}`,
      ),
    )
    .slice(0, MAX_REPORT_TOOL_EVIDENCE_RECORDS);

export function buildSbtdReport(input: ReportBuildInput): SbtdReport {
  const validation =
    input.state.validationReport ??
    validationReportSchema.parse({
      schemaVersion: 1,
      checkRequirement: "not-applicable",
      validationStatus: "not-needed",
      e2eMode: "not-needed",
      observedAt: input.state.environmentObservation.observedAt,
      evidenceEnvelope: {
        evidenceSource: "not-needed",
        sourceRevision: "not-needed",
        environmentAlignment: "not-needed",
        evidencePublication: "not-needed",
      },
    });
  const provider =
    input.provider === undefined || input.provider.availability === "unknown"
      ? (input.state.providerObservation ??
        input.provider ??
        unknownProviderObservation(
          input.state.environmentObservation.observedAt,
          "provider-observation-unavailable",
        ))
      : input.provider;
  return sbtdReportSchema.parse({
    schemaVersion: 1,
    workflow: {
      runtimeMode: input.state.runtimeMode,
      policyProfile: input.state.policyProfile,
      route: input.state.route,
      environmentMode: input.state.environmentObservation.mode,
      effectiveControlState: input.effectiveControlState,
      ...(input.state.route !== "auto" || input.automaticRoute === undefined
        ? {}
        : { automaticRoute: input.automaticRoute }),
      ...(input.state.stage === undefined
        ? {}
        : {
            stage: {
              id: input.state.stage.id,
              status: input.state.stage.stageStatus,
            },
          }),
      bookGates: [...(input.state.bookGates ?? [])]
        .map((gate) => ({
          id: gate.id,
          required: gate.required,
          gateState: gate.gateState,
          ...(gate.reviewerStatus === undefined
            ? {}
            : { reviewerStatus: gate.reviewerStatus }),
        }))
        .sort((left, right) => left.id.localeCompare(right.id)),
    },
    validation,
    evidence: validation.evidenceEnvelope,
    toolEvidence: reportToolEvidence(input.toolEvidence),
    provider,
  });
}

const renderFormalArtifact = (
  artifact: FormalArtifactDescriptor | undefined,
) => {
  if (artifact === undefined) return ["- 正式报告：未记录"];
  if (artifact.status === "blocked")
    return [
      "- 正式报告：blocked",
      `- 阻断代码：${artifact.blockedReason}`,
      `- 恢复代码：${artifact.recoveryCode}`,
    ];
  return [
    `- 正式报告：${artifact.runner}`,
    `- 报告路径：${artifact.reportPath}`,
    `- Markdown 路径：${artifact.markdownPath}`,
    `- 报告完整性：${artifact.report.sha256} (${artifact.report.sizeBytes} bytes)`,
    `- Markdown 完整性：${artifact.markdown.sha256} (${artifact.markdown.sizeBytes} bytes)`,
  ];
};

export interface RenderedSbtdReport {
  readonly json: string;
  readonly markdown: string;
}

export function renderSbtdReport(model: SbtdReport): RenderedSbtdReport {
  const report = sbtdReportSchema.parse(model);
  const lines = [
    "# SBTD 当前报告",
    "",
    "## 工作流",
    `- Runtime Mode：${report.workflow.runtimeMode}`,
    `- Policy Profile：${report.workflow.policyProfile}`,
    `- Route：${report.workflow.route}`,
    ...(report.workflow.automaticRoute === undefined
      ? []
      : [`- Automatic Route：${report.workflow.automaticRoute}`]),
    `- Environment Mode：${report.workflow.environmentMode}`,
    `- Effective Control State：${report.workflow.effectiveControlState}`,
    ...(report.workflow.stage === undefined
      ? []
      : [
          `- Stage：${report.workflow.stage.id}`,
          `- Stage Status：${report.workflow.stage.status}`,
        ]),
    "",
    "## 验证",
    `- Check Requirement：${report.validation.checkRequirement}`,
    `- Validation Status：${report.validation.validationStatus}`,
    `- 实际 E2E Mode：${report.validation.e2eMode}`,
    `- 完整链路：${report.validation.e2eMode === "full-stack" ? "是" : "否"}`,
    ...(report.validation.blockedReason === undefined
      ? []
      : [`- 验证阻断代码：${report.validation.blockedReason}`]),
    ...renderFormalArtifact(report.validation.formalArtifact),
    "",
    "## Evidence Envelope",
    `- Evidence Source：${report.evidence.evidenceSource}`,
    `- Source Revision：${report.evidence.sourceRevision}`,
    `- Environment Alignment：${report.evidence.environmentAlignment}`,
    `- Evidence Publication：${report.evidence.evidencePublication}`,
    "",
    "## 工具证据",
    ...(report.toolEvidence.length === 0
      ? ["- 无"]
      : report.toolEvidence.map(
          (evidence) =>
            `- ${evidence.toolId}/${evidence.capability}：installation=${evidence.installation}; configuration=${evidence.configuration}; callability=${evidence.callability}; projectReadiness=${evidence.projectReadiness}; freshness=${evidence.freshness}`,
        )),
    "",
    "## Provider Coordination",
    `- Provider：${report.provider.provider ?? "unknown"}`,
    `- Model：${report.provider.model ?? "unknown"}`,
    ...(report.provider.roleAlias === undefined
      ? []
      : [`- Role Alias：${report.provider.roleAlias}`]),
    `- Availability：${report.provider.availability}`,
    `- Fallback：${report.provider.fallback}`,
    `- Selection Result：${report.provider.selection}`,
    ...(report.provider.blockerCode === undefined
      ? []
      : [`- Provider 阻断代码：${report.provider.blockerCode}`]),
  ];
  return {
    json: JSON.stringify(report, null, 2),
    markdown: `${lines.join("\n")}\n`,
  };
}
