import type { SBTDClassification } from "../workflow/index.js";

export const bookGateIds = [
  "ddd-boundary",
  "ddia-data-design",
  "legacy-change-safety",
  "refactoring",
  "release-readiness",
] as const;

export const gateStates = [
  "planned",
  "running",
  "passed",
  "blocked",
  "not-required",
] as const;

export const gatePhases = [
  "requirement-confirmation",
  "before-design",
  "before-implementation",
  "after-validation",
] as const;

export const reviewerStatuses = [
  "confirmed",
  "needs-clarification",
  "needs-design-change",
  "characterized",
  "needs-safety-net",
  "seam-required",
  "proceed",
  "refactor-first",
  "ready",
  "needs-mitigation",
  "blocked",
] as const;

export type BookGateId = (typeof bookGateIds)[number];
export type GateState = (typeof gateStates)[number];
export type GatePhase = (typeof gatePhases)[number];
export type ReviewerStatus = (typeof reviewerStatuses)[number];

export interface BookGateRecord {
  readonly id: BookGateId;
  readonly required: boolean;
  readonly predicate: string[];
  readonly plannedPhase: GatePhase;
  readonly gateState: GateState;
  readonly reviewerStatus?: ReviewerStatus | undefined;
  readonly evidence: string[];
}

interface GateDefinition {
  readonly id: BookGateId;
  readonly plannedPhase: GatePhase;
  readonly required: (classification: SBTDClassification) => boolean;
  readonly predicate: (classification: SBTDClassification) => readonly string[];
  readonly passingStatus: ReviewerStatus;
  readonly reviewerStatuses: readonly ReviewerStatus[];
}

const definitions: readonly GateDefinition[] = [
  {
    id: "ddd-boundary",
    plannedPhase: "requirement-confirmation",
    required: (classification) => classification.ddd === "required",
    predicate: (classification) =>
      classification.ddd === "required" ? ["domain-ambiguity"] : [],
    passingStatus: "confirmed",
    reviewerStatuses: ["confirmed", "needs-clarification", "blocked"],
  },
  {
    id: "ddia-data-design",
    plannedPhase: "before-design",
    required: (classification) => classification.dataRisk,
    predicate: (classification) =>
      classification.dataRisk ? ["data-risk"] : [],
    passingStatus: "confirmed",
    reviewerStatuses: ["confirmed", "needs-design-change", "blocked"],
  },
  {
    id: "legacy-change-safety",
    plannedPhase: "before-implementation",
    required: (classification) => classification.legacySafetyRisk,
    predicate: (classification) =>
      classification.legacySafetyRisk
        ? classification.reasons.filter((reason) =>
            [
              "existing-behavior-bug",
              "weak-or-missing-tests",
              "hidden-dependencies",
              "high-regression-risk",
            ].includes(reason),
          )
        : [],
    passingStatus: "characterized",
    reviewerStatuses: [
      "characterized",
      "needs-safety-net",
      "seam-required",
      "blocked",
    ],
  },
  {
    id: "refactoring",
    plannedPhase: "before-implementation",
    required: (classification) => classification.existingProductionCode,
    predicate: (classification) =>
      classification.existingProductionCode ? ["existing-production-code"] : [],
    passingStatus: "proceed",
    reviewerStatuses: ["proceed", "refactor-first", "blocked"],
  },
  {
    id: "release-readiness",
    plannedPhase: "after-validation",
    required: (classification) =>
      classification.productionPathRisk || classification.releaseOrDeploy,
    predicate: (classification) => [
      ...(classification.productionPathRisk ? ["production-path-risk"] : []),
      ...(classification.releaseOrDeploy ? ["release-or-deploy"] : []),
    ],
    passingStatus: "ready",
    reviewerStatuses: ["ready", "needs-mitigation", "blocked"],
  },
] as const;

function definitionFor(id: BookGateId): GateDefinition {
  const definition = definitions.find((candidate) => candidate.id === id);
  if (!definition) throw new Error(`unknown Book Gate: ${id}`);
  return definition;
}

function updateGate(
  plan: readonly BookGateRecord[],
  id: BookGateId,
  update: (
    current: BookGateRecord,
    definition: GateDefinition,
  ) => BookGateRecord,
): readonly BookGateRecord[] {
  let found = false;
  const updated = plan.map((current) => {
    if (current.id !== id) return current;
    found = true;
    return update(current, definitionFor(id));
  });
  if (!found) throw new Error(`Book Gate plan does not contain ${id}`);
  return updated;
}
export function isLegalBookGateRecord(record: BookGateRecord): boolean {
  const definition = definitionFor(record.id);
  if (!record.required)
    return (
      record.gateState === "not-required" && record.reviewerStatus === undefined
    );
  if (record.gateState === "planned")
    return record.reviewerStatus === undefined;
  if (record.gateState === "running")
    return (
      record.reviewerStatus === undefined ||
      (definition.reviewerStatuses.includes(record.reviewerStatus) &&
        record.reviewerStatus !== definition.passingStatus &&
        record.reviewerStatus !== "blocked")
    );
  if (record.gateState === "passed")
    return record.reviewerStatus === definition.passingStatus;
  return record.reviewerStatus === "blocked";
}

export function isCompleteBookGatePlan(
  plan: readonly BookGateRecord[],
): boolean {
  return (
    plan.length === bookGateIds.length &&
    bookGateIds.every(
      (id) => plan.filter((gate) => gate.id === id).length === 1,
    ) &&
    plan.every(isLegalBookGateRecord)
  );
}

export function assertRequiredBookGatesPassed(
  plan: readonly BookGateRecord[],
): void {
  const pending = plan.filter(
    (gate) => gate.required && gate.gateState !== "passed",
  );
  if (pending.length === 0) return;
  throw new Error(
    `Required Book Gate transition blocked: ${pending
      .map(
        (gate) =>
          `${gate.id} (state=${gate.gateState}; predicate=${gate.predicate.join(",")})`,
      )
      .join(
        "; ",
      )}. Complete the required review and record its passing reviewer status.`,
  );
}

export function assertRequiredBookGatesPassedForPhase(
  plan: readonly BookGateRecord[],
  phase: GatePhase,
): void {
  const phaseIndex = gatePhases.indexOf(phase);
  const pending = plan.filter(
    (gate) =>
      gate.required &&
      gatePhases.indexOf(gate.plannedPhase) <= phaseIndex &&
      gate.gateState !== "passed",
  );
  if (pending.length === 0) return;
  throw new Error(
    `Required Book Gate transition blocked: ${pending
      .map(
        (gate) =>
          `${gate.id} (state=${gate.gateState}; predicate=${gate.predicate.join(",")})`,
      )
      .join(
        "; ",
      )}. Complete the required review and record its passing reviewer status.`,
  );
}

export function createBookGatePlan(
  classification: SBTDClassification,
): readonly BookGateRecord[] {
  return definitions.map((definition) => {
    const required = definition.required(classification);
    const predicate = definition.predicate(classification);
    return {
      id: definition.id,
      required,
      predicate: [...predicate],
      evidence:
        predicate.length > 0
          ? [...predicate]
          : ["no applicable objective fact for this Gate"],
      plannedPhase: definition.plannedPhase,
      gateState: required ? "planned" : "not-required",
    };
  });
}

export function startBookGate(
  plan: readonly BookGateRecord[],
  id: BookGateId,
): readonly BookGateRecord[] {
  return updateGate(plan, id, (current) => {
    if (!current.required || current.gateState === "not-required")
      throw new Error(`${id} is not required`);
    if (current.gateState !== "planned")
      throw new Error(`${id} must be planned before it can run`);
    return { ...current, gateState: "running" };
  });
}

export function resetReleaseReadinessAfterMutation(
  plan: readonly BookGateRecord[],
): readonly BookGateRecord[] {
  return plan.map((current) => {
    if (current.id !== "release-readiness" || !current.required) return current;
    if (current.gateState !== "passed" && current.gateState !== "running")
      return current;
    return {
      ...current,
      gateState: "planned" as const,
      reviewerStatus: undefined,
    };
  });
}

export function recordBookGateReview(
  plan: readonly BookGateRecord[],
  id: BookGateId,
  reviewerStatus: ReviewerStatus,
  validationVerified = false,
): readonly BookGateRecord[] {
  return updateGate(plan, id, (current, definition) => {
    if (current.gateState !== "running")
      throw new Error(`${id} must be running before recording a review`);
    if (!definition.reviewerStatuses.includes(reviewerStatus))
      throw new Error(`${reviewerStatus} is not valid for ${id}`);
    if (
      id === "release-readiness" &&
      reviewerStatus === "ready" &&
      !validationVerified
    )
      throw new Error(
        "release-readiness-review requires verified validation evidence before ready",
      );
    return {
      ...current,
      reviewerStatus,
      gateState:
        reviewerStatus === "blocked"
          ? "blocked"
          : reviewerStatus === definition.passingStatus
            ? "passed"
            : "running",
    };
  });
}
