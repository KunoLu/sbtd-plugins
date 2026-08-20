import { z } from "zod";
import type { EnvironmentMode } from "../commands/index.js";
import {
  assertRequiredBookGatesPassedForPhase,
  type BookGateId,
  type BookGateRecord,
  bookGateIds,
  gatePhases,
  gateStates,
  isCompleteBookGatePlan,
  type ReviewerStatus,
  recordBookGateReview,
  resetReleaseReadinessAfterMutation,
  reviewerStatuses,
  startBookGate,
} from "../gates/index.js";
import {
  type ProviderObservation,
  providerObservationSchema,
  type ValidationEvidenceDescriptor,
  type ValidationReport,
  validationEvidenceDescriptorSchema,
  validationReportSchema,
} from "../report/index.js";
import type { RuleDecision, RuleMatch } from "../rules/index.js";
import {
  type SBTDClassification,
  workflowRouteIds,
} from "../workflow/index.js";

export const SBTD_STATE_CUSTOM_TYPE = "kpi.sbtd.session.v1";

export const workflowStageIds = [
  "requirement-confirmation",
  "design",
  "implementation",
  "validation",
  "delivery",
] as const;

export type WorkflowStageId = (typeof workflowStageIds)[number];

function gatePhaseForStage(id: WorkflowStageId) {
  switch (id) {
    case "requirement-confirmation":
      return "requirement-confirmation" as const;
    case "design":
      return "before-design" as const;
    case "implementation":
    case "validation":
      return "before-implementation" as const;
    case "delivery":
      return "after-validation" as const;
  }
}
export const SBTD_STATE_COMPACTION_KEY = "kpi.sbtd.session.v1";

export const environmentObservationSchema = z
  .object({
    observedAt: z.string().datetime(),
    mode: z.enum(["blocked", "needs-onboard", "degraded", "managed"]),
    evidence: z.array(z.string()).max(32),
    repairPath: z.string().min(1),
  })
  .strict();

const disciplineRequirementSchema = z.enum([
  "required",
  "recommended",
  "not-needed",
  "blocked",
]);

export const classificationSchema = z
  .object({
    sdd: disciplineRequirementSchema,
    bdd: disciplineRequirementSchema,
    tdd: disciplineRequirementSchema,
    ddd: disciplineRequirementSchema,
    route: z.enum(workflowRouteIds),
    reasons: z.array(z.string().min(1)).max(64),
    userVisibleBehavior: z.boolean(),
    existingProductionCode: z.boolean(),
    existingBehaviorBug: z.boolean(),
    dataRisk: z.boolean(),
    productionPathRisk: z.boolean(),
    crossRepoScope: z.boolean(),
    legacySafetyRisk: z.boolean().default(false),
    releaseOrDeploy: z.boolean().default(false),
  })
  .strict();

const bookGateRecordSchema = z
  .object({
    id: z.enum(bookGateIds),
    required: z.boolean(),
    predicate: z.array(z.string().min(1)).max(32),
    plannedPhase: z.enum(gatePhases),
    gateState: z.enum(gateStates),
    evidence: z.array(z.string().min(1)).min(1).max(32),
    reviewerStatus: z.enum(reviewerStatuses).optional(),
  })
  .strict();

const ruleDecisionRecordSchema = z
  .object({
    fingerprint: z.string().min(1),
    ruleId: z.string().min(1),
    action: z.enum(["tool", "stage", "delivery"]),
    decision: z.enum([
      "remind",
      "interrupt",
      "block-tool",
      "block-stage",
      "block-delivery",
    ]),
    severity: z.enum(["hard", "optional"]),
    configurable: z.boolean(),
    matchedFacts: z.array(z.string().min(1)).min(1).max(32),
    reason: z.string().min(1),
    recovery: z.string().min(1),
    observedAt: z.string().datetime(),
  })
  .strict();

const stageStateSchema = z
  .object({
    id: z.enum(workflowStageIds),
    stageStatus: z.enum([
      "pending",
      "running",
      "passed",
      "blocked",
      "skipped",
      "not-needed",
    ]),
    reason: z.string().min(1).optional(),
    startedAt: z.string().datetime().optional(),
    completedAt: z.string().datetime().optional(),
  })
  .strict();
export const sbtdSessionStateSchema = z
  .object({
    stateVersion: z.literal(1),
    runtimeMode: z.enum(["enforced", "advisory"]),
    policyProfile: z.enum(["strict", "relaxed"]),
    onboardProfileId: z.literal("omp-p0-standard-v1"),
    securityBaseline: z.literal("local-guarded"),
    route: z.enum(["auto", ...workflowRouteIds]),
    classification: classificationSchema.optional(),
    activeSkills: z.array(z.string().min(1)).max(16).default([]),
    bookGates: z.array(bookGateRecordSchema).max(bookGateIds.length).optional(),
    ruleDecisions: z.array(ruleDecisionRecordSchema).max(64).default([]),
    stage: stageStateSchema.optional(),
    validationReport: validationReportSchema.optional(),
    validationEvidence: validationEvidenceDescriptorSchema.optional(),
    providerObservation: providerObservationSchema.optional(),
    environmentObservation: environmentObservationSchema,
  })
  .strict()
  .superRefine((state, ctx) => {
    if (
      state.bookGates !== undefined &&
      !isCompleteBookGatePlan(state.bookGates)
    )
      ctx.addIssue({
        code: "custom",
        path: ["bookGates"],
        message:
          "Book Gate records must include every canonical Gate with a legal state and reviewer status combination.",
      });
  });

const draftSessionStateSchema = z
  .object({
    enabled: z.boolean().optional(),
    mode: z.enum(["enforced", "advisory", "strict", "relaxed"]).optional(),
    runtimeMode: z.enum(["enforced", "advisory"]).optional(),
    policyProfile: z.enum(["strict", "relaxed"]).optional(),
    onboardProfileId: z.literal("omp-p0-standard-v1").optional(),
    securityBaseline: z.literal("local-guarded").optional(),
    route: z.enum(["auto", ...workflowRouteIds]).optional(),
    classification: classificationSchema.optional(),
    activeSkills: z.array(z.string().min(1)).max(16).optional(),
    bookGates: z.array(bookGateRecordSchema).max(bookGateIds.length).optional(),
    ruleDecisions: z.array(ruleDecisionRecordSchema).max(64).optional(),
    stage: stageStateSchema.optional(),
    validationReport: validationReportSchema.optional(),
    validationEvidence: validationEvidenceDescriptorSchema.optional(),
    providerObservation: providerObservationSchema.optional(),
    environmentObservation: environmentObservationSchema.optional(),
  })
  .strict();

export type EnvironmentObservation = z.infer<
  typeof environmentObservationSchema
>;
export type SbtdSessionState = z.infer<typeof sbtdSessionStateSchema>;
export type EffectiveControlState =
  | "advisory"
  | "active"
  | "preflight-only"
  | "blocked";

export interface SessionEntryAdapter {
  readonly replay: () => readonly unknown[];
  readonly append: (customType: string, data: unknown) => void;
}

export function defaultSessionState(
  observedAt = "1970-01-01T00:00:00.000Z",
): SbtdSessionState {
  return {
    stateVersion: 1,
    runtimeMode: "advisory",
    policyProfile: "strict",
    onboardProfileId: "omp-p0-standard-v1",
    securityBaseline: "local-guarded",
    activeSkills: [],
    ruleDecisions: [],
    route: "auto",
    environmentObservation: {
      observedAt,
      mode: "needs-onboard",
      evidence: ["required baseline has not been verified"],
      repairPath: "/sbtd onboard plan",
    },
  };
}

function migrateDraftSessionState(candidate: unknown): unknown {
  const record = z.record(z.string(), z.unknown()).safeParse(candidate);
  if (!record.success || Object.hasOwn(record.data, "stateVersion"))
    return candidate;
  const parsed = draftSessionStateSchema.safeParse(candidate);
  if (
    !parsed.success ||
    (parsed.data.enabled === undefined &&
      parsed.data.mode === undefined &&
      parsed.data.runtimeMode === undefined &&
      parsed.data.policyProfile === undefined)
  )
    return candidate;
  const runtimeCandidates = [
    parsed.data.runtimeMode,
    parsed.data.enabled === undefined
      ? undefined
      : parsed.data.enabled
        ? "enforced"
        : "advisory",
    parsed.data.mode === "enforced" || parsed.data.mode === "advisory"
      ? parsed.data.mode
      : undefined,
  ].filter((mode): mode is "enforced" | "advisory" => mode !== undefined);
  const policyCandidates = [
    parsed.data.policyProfile,
    parsed.data.mode === "strict" || parsed.data.mode === "relaxed"
      ? parsed.data.mode
      : undefined,
  ].filter((profile): profile is "strict" | "relaxed" => profile !== undefined);
  const runtimeModes = runtimeCandidates.filter(
    (mode, index) => runtimeCandidates.indexOf(mode) === index,
  );
  const policyProfiles = policyCandidates.filter(
    (profile, index) => policyCandidates.indexOf(profile) === index,
  );
  if (runtimeModes.length > 1 || policyProfiles.length > 1) return candidate;
  const fallback = defaultSessionState(
    parsed.data.environmentObservation?.observedAt,
  );
  return {
    stateVersion: 1,
    runtimeMode: runtimeModes[0] ?? fallback.runtimeMode,
    policyProfile: policyProfiles[0] ?? fallback.policyProfile,
    onboardProfileId: parsed.data.onboardProfileId ?? fallback.onboardProfileId,
    securityBaseline: parsed.data.securityBaseline ?? fallback.securityBaseline,
    route: parsed.data.route ?? fallback.route,
    classification: parsed.data.classification,
    activeSkills: parsed.data.activeSkills ?? fallback.activeSkills,
    bookGates: parsed.data.bookGates,
    ruleDecisions: parsed.data.ruleDecisions ?? fallback.ruleDecisions,
    stage: parsed.data.stage,
    validationReport: parsed.data.validationReport,
    providerObservation: parsed.data.providerObservation,
    environmentObservation:
      parsed.data.environmentObservation ?? fallback.environmentObservation,
  };
}

const bookGateSkills = {
  "ddd-boundary": "book-ddd-distilled-modeling",
  "ddia-data-design": "book-ddia-data-design",
  "legacy-change-safety": "book-legacy-change-safety",
  refactoring: "book-refactoring-pass",
  "release-readiness": "book-release-readiness",
} as const;

function activeSkillsFor(classification: SBTDClassification): string[] {
  return [
    ...(classification.sdd === "required" ? ["to-spec"] : []),
    ...(classification.bdd === "required" ? ["gherkin-bdd"] : []),
    ...(classification.tdd === "required" ? ["tdd"] : []),
    ...bookGateIds
      .filter((id) => {
        switch (id) {
          case "ddd-boundary":
            return classification.ddd === "required";
          case "ddia-data-design":
            return classification.dataRisk;
          case "legacy-change-safety":
            return classification.legacySafetyRisk;
          case "refactoring":
            return classification.existingProductionCode;
          case "release-readiness":
            return (
              classification.productionPathRisk ||
              classification.releaseOrDeploy
            );
          default:
            return false;
        }
      })
      .map((id) => bookGateSkills[id]),
  ];
}

function reconcileBookGatePlan(
  current: readonly BookGateRecord[] | undefined,
  proposed: readonly BookGateRecord[],
): BookGateRecord[] {
  if (!current) return [...proposed];
  return proposed.map((next) => {
    const previous = current.find((gate) => gate.id === next.id);
    return previous !== undefined &&
      previous.required === next.required &&
      previous.plannedPhase === next.plannedPhase &&
      JSON.stringify(previous.predicate) === JSON.stringify(next.predicate)
      ? previous
      : next;
  });
}

export function deriveEffectiveControlState(
  runtimeMode: SbtdSessionState["runtimeMode"],
  environmentMode: EnvironmentMode,
): EffectiveControlState {
  if (runtimeMode === "advisory") return "advisory";
  if (environmentMode === "managed" || environmentMode === "degraded")
    return "active";
  return environmentMode === "blocked" ? "blocked" : "preflight-only";
}

export function restoreSessionState(
  entries: readonly unknown[],
  fallback = defaultSessionState(),
): SbtdSessionState {
  for (const entry of [...entries].reverse()) {
    const record = z.record(z.string(), z.unknown()).safeParse(entry);
    if (!record.success) continue;
    let candidate: unknown;
    if (record.data.customType === SBTD_STATE_CUSTOM_TYPE) {
      candidate = record.data.data;
    } else if (record.data.type === "compaction") {
      const preserved = z
        .record(z.string(), z.unknown())
        .safeParse(record.data.preserveData);
      if (
        !preserved.success ||
        !Object.hasOwn(preserved.data, SBTD_STATE_COMPACTION_KEY)
      )
        continue;
      candidate = preserved.data[SBTD_STATE_COMPACTION_KEY];
    } else {
      continue;
    }
    const parsed = sbtdSessionStateSchema.safeParse(
      migrateDraftSessionState(candidate),
    );
    if (!parsed.success)
      throw new Error(
        "Invalid latest KPi SBTD session state; repair the session history before continuing.",
      );
    return parsed.data;
  }
  return fallback;
}

/**
 * True only when the session carries a persisted evidence descriptor that the
 * observer verified. A descriptor alone never proves freshness: release
 * decisions must re-derive readiness from a current observation; this
 * predicate is the reporting/status surface for what was last verified.
 * v1 generic envelopes never satisfy BDD scenario traceability.
 */
export function hasVerifiedValidationEvidence(
  state: SbtdSessionState,
): boolean {
  return state.validationEvidence !== undefined;
}

export function validationEvidenceSatisfiesBdd(
  state: SbtdSessionState,
): boolean {
  return (
    state.validationEvidence !== undefined &&
    state.validationEvidence.evidenceVersion === 2 &&
    state.validationEvidence.scenarioLinks.length > 0
  );
}

export interface StateService {
  readonly restore: () => SbtdSessionState;
  readonly on: (observe: () => EnvironmentObservation) => {
    state: SbtdSessionState;
    effectiveControlState: EffectiveControlState;
  };
  readonly refresh: (observe: () => EnvironmentObservation) => {
    state: SbtdSessionState;
    effectiveControlState: EffectiveControlState;
  };
  readonly recordWorkflow: (
    classification: SBTDClassification,
    bookGates: readonly BookGateRecord[],
  ) => SbtdSessionState;
  readonly recordRuleDecision: (
    decision: RuleDecision,
    action: "tool" | "stage" | "delivery",
    matchedFacts: readonly string[],
  ) => SbtdSessionState;
  readonly recordValidationReport: (
    report: ValidationReport,
  ) => SbtdSessionState;
  readonly recordValidationEvidence: (
    descriptor: ValidationEvidenceDescriptor,
  ) => SbtdSessionState;
  readonly invalidateValidationEvidence: (reason: string) => SbtdSessionState;
  readonly recordProviderObservation: (
    observation: ProviderObservation,
  ) => SbtdSessionState;
  readonly startBookGate: (id: BookGateId) => SbtdSessionState;
  readonly recordBookGateReview: (
    id: BookGateId,
    reviewerStatus: ReviewerStatus,
  ) => SbtdSessionState;
  readonly blockStage: (
    id: WorkflowStageId,
    reason: string,
  ) => SbtdSessionState;
  readonly requestStageTransition: (id: WorkflowStageId) => SbtdSessionState;
  readonly setRoute: (
    route: SbtdSessionState["route"],
    observe: () => EnvironmentObservation,
    workflow?: {
      readonly classification?: SBTDClassification;
      readonly bookGates?: readonly BookGateRecord[];
    },
  ) => {
    state: SbtdSessionState;
    effectiveControlState: EffectiveControlState;
  };
  readonly setPolicyProfile: (
    policyProfile: SbtdSessionState["policyProfile"],
    observe: () => EnvironmentObservation,
  ) => {
    state: SbtdSessionState;
    effectiveControlState: EffectiveControlState;
  };
  readonly off: () => {
    state: SbtdSessionState;
    effectiveControlState: EffectiveControlState;
  };
}

export function createStateService(
  adapter: SessionEntryAdapter,
  now: () => string = () => new Date().toISOString(),
): StateService {
  const restore = (): SbtdSessionState =>
    restoreSessionState(adapter.replay(), defaultSessionState(now()));
  const transition = (
    changes: Partial<
      Pick<
        SbtdSessionState,
        | "runtimeMode"
        | "policyProfile"
        | "route"
        | "classification"
        | "bookGates"
        | "activeSkills"
        | "ruleDecisions"
      >
    >,
    observationFactory: () => EnvironmentObservation,
  ) => {
    let observation: EnvironmentObservation;
    try {
      observation = environmentObservationSchema.parse(observationFactory());
    } catch {
      throw new Error(
        "Preflight could not determine the environment. Run /sbtd doctor, repair the reported issue, then retry.",
      );
    }
    const state = sbtdSessionStateSchema.parse({
      ...restore(),
      ...changes,
      environmentObservation: observation,
    });
    adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
    return {
      state,
      effectiveControlState: deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      ),
    };
  };
  return {
    restore,
    refresh(observationFactory) {
      return transition({}, observationFactory);
    },
    recordWorkflow(classification, bookGates) {
      const current = restore();
      const activeSkills = activeSkillsFor(classification);
      const preservedBookGates = reconcileBookGatePlan(
        current.bookGates,
        bookGates,
      );
      if (
        JSON.stringify(current.classification) ===
          JSON.stringify(classification) &&
        JSON.stringify(current.bookGates) ===
          JSON.stringify(preservedBookGates) &&
        JSON.stringify(current.activeSkills) === JSON.stringify(activeSkills)
      )
        return current;
      const state = sbtdSessionStateSchema.parse({
        ...current,
        classification,
        activeSkills,
        bookGates: preservedBookGates,
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    startBookGate(id) {
      const current = restore();
      if (!current.bookGates)
        throw new Error("No Book Gate Plan is available for this Session");
      const state = sbtdSessionStateSchema.parse({
        ...current,
        bookGates: startBookGate(
          current.bookGates as readonly BookGateRecord[],
          id,
        ),
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    recordBookGateReview(id, reviewerStatus) {
      const current = restore();
      if (!current.bookGates)
        throw new Error("No Book Gate Plan is available for this Session");
      // P1-06: `release-readiness ready` is derived from the persisted
      // evidence descriptor (recorded only by the observer after a verified,
      // revision-current observation), never from a caller-supplied boolean.
      // When the task classification requires BDD, only a v2 descriptor with
      // scenario links satisfies it; v1 generic evidence never does.
      const validationVerified =
        hasVerifiedValidationEvidence(current) &&
        (current.classification?.userVisibleBehavior === true
          ? validationEvidenceSatisfiesBdd(current)
          : true);
      const state = sbtdSessionStateSchema.parse({
        ...current,
        bookGates: recordBookGateReview(
          current.bookGates as readonly BookGateRecord[],
          id,
          reviewerStatus,
          validationVerified,
        ),
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    requestStageTransition(id) {
      const current = restore();
      if (!current.bookGates)
        throw new Error(
          "No Book Gate Plan is available for this Session. Classify the task before requesting a stage transition.",
        );
      assertRequiredBookGatesPassedForPhase(
        current.bookGates,
        gatePhaseForStage(id),
      );
      if (
        current.stage?.id === id &&
        ["running", "passed", "skipped", "not-needed"].includes(
          current.stage.stageStatus,
        )
      )
        return current;
      const state = sbtdSessionStateSchema.parse({
        ...current,
        stage: { id, stageStatus: "running", startedAt: now() },
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    blockStage(id, reason) {
      const current = restore();
      const state = sbtdSessionStateSchema.parse({
        ...current,
        stage: { id, stageStatus: "blocked", reason, completedAt: now() },
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    recordRuleDecision(decision, action, matchedFacts) {
      if (decision.decision === "allow") return restore();
      const current = restore();
      const facts = [...new Set(matchedFacts)].sort();
      const matches = decision.matches ?? [];
      const records = matches.map((match: RuleMatch) => ({
        fingerprint: `${action}:${match.ruleId}:${facts.join(",")}`,
        ruleId: match.ruleId,
        action,
        decision: match.decision,
        severity: match.severity,
        configurable: match.configurable,
        matchedFacts: facts.length > 0 ? facts : ["matched-rule-predicate"],
        reason: match.reason,
        recovery: match.recovery,
        observedAt: now(),
      }));
      const prior = current.ruleDecisions.filter(
        (record) =>
          !records.some(
            (candidate) => candidate.fingerprint === record.fingerprint,
          ),
      );
      const state = sbtdSessionStateSchema.parse({
        ...current,
        ruleDecisions: [...prior, ...records].slice(-64),
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    recordValidationReport(report) {
      const current = restore();
      const state = sbtdSessionStateSchema.parse({
        ...current,
        validationReport: validationReportSchema.parse(report),
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    recordValidationEvidence(descriptor) {
      const current = restore();
      const state = sbtdSessionStateSchema.parse({
        ...current,
        validationEvidence:
          validationEvidenceDescriptorSchema.parse(descriptor),
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    invalidateValidationEvidence(_reason) {
      const current = restore();
      if (
        current.validationEvidence === undefined &&
        current.bookGates?.every(
          (gate) =>
            gate.id !== "release-readiness" ||
            (gate.gateState !== "passed" && gate.gateState !== "running"),
        ) !== false
      )
        return current;
      const state = sbtdSessionStateSchema.parse({
        ...current,
        validationEvidence: undefined,
        bookGates:
          current.bookGates === undefined
            ? undefined
            : resetReleaseReadinessAfterMutation(current.bookGates),
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    recordProviderObservation(observation) {
      const current = restore();
      const next = providerObservationSchema.parse(observation);
      const previous = current.providerObservation;
      if (
        next.availability === "unknown" &&
        previous?.availability === "unavailable"
      )
        return current;
      if (
        previous !== undefined &&
        previous.provider === next.provider &&
        previous.model === next.model &&
        previous.roleAlias === next.roleAlias &&
        previous.availability === next.availability &&
        previous.fallback === next.fallback &&
        previous.selection === next.selection &&
        previous.blockerCode === next.blockerCode
      )
        return current;
      const state = sbtdSessionStateSchema.parse({
        ...current,
        providerObservation: next,
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return state;
    },
    on(observationFactory) {
      return transition({ runtimeMode: "enforced" }, observationFactory);
    },
    setRoute(route, observationFactory, workflow) {
      const current = restore();
      return transition(
        {
          route,
          ...(workflow?.classification === undefined
            ? {}
            : {
                classification: workflow.classification,
                activeSkills: activeSkillsFor(workflow.classification),
                bookGates: reconcileBookGatePlan(
                  current.bookGates,
                  workflow.bookGates ?? [],
                ),
              }),
        },
        observationFactory,
      );
    },
    setPolicyProfile(policyProfile, observationFactory) {
      const current = restore();
      return transition(
        {
          policyProfile,
          ruleDecisions: current.ruleDecisions.filter(
            (decision) => !decision.configurable,
          ),
        },
        observationFactory,
      );
    },
    off() {
      const current = restore();
      const state = sbtdSessionStateSchema.parse({
        ...current,
        runtimeMode: "advisory",
      });
      adapter.append(SBTD_STATE_CUSTOM_TYPE, state);
      return { state, effectiveControlState: "advisory" };
    },
  };
}
