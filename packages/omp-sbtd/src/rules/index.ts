export type PolicyProfile = "strict" | "relaxed";
export type RuleDecisionKind =
  | "allow"
  | "remind"
  | "interrupt"
  | "block-tool"
  | "block-stage"
  | "block-delivery";
export type RuleAction = "tool" | "stage" | "delivery";

export interface RuleEvaluationFacts {
  readonly action: RuleAction;
  readonly toolCommand?: string;
  readonly insideOnboard?: boolean;
  readonly userVisibleBehavior?: boolean;
  readonly bddCovered?: boolean;
  readonly requiredBookGatesPassed?: boolean;
  readonly formalReportPresent?: boolean;
  readonly e2eMode?:
    | "full-stack"
    | "contract-backed"
    | "mock-backed"
    | "app-mocked";
  readonly gitnexusReady?: boolean;
  readonly maestroJava17?: boolean;
  readonly installingDependency?: boolean;
  readonly installApproved?: boolean;
  readonly secretRead?: boolean;
  readonly secretReadApproved?: boolean;
  readonly policyProfile?: PolicyProfile;
  readonly reportingTestUsingRtk?: boolean;
  readonly rtkSideEffectsVerified?: boolean;
  readonly productionPathRisk?: boolean;
  readonly releaseGateReady?: boolean;
}

export interface RuleSpec {
  readonly id:
    | "no-trellis-init-outside-onboard"
    | "bdd-required-for-visible-behavior"
    | "book-gate-before-edit"
    | "report-artifact-required"
    | "mock-is-not-full-stack"
    | "gitnexus-requires-mcp-and-index"
    | "maestro-requires-java17"
    | "secret-read-guard"
    | "install-requires-approval"
    | "rtk-is-not-test-runner"
    | "release-gate-before-complete";
  readonly decision: Exclude<RuleDecisionKind, "allow">;
  readonly configurable: boolean;
  readonly strictOnly?: boolean;
  readonly enabled: boolean;
  readonly applies: (facts: RuleEvaluationFacts) => boolean;
  readonly reason: string;
  readonly recovery: string;
}

export interface RuleMatch {
  readonly ruleId: RuleSpec["id"];
  readonly decision: Exclude<RuleDecisionKind, "allow">;
  readonly configurable: boolean;
  readonly severity: "hard" | "optional";
  readonly reason: string;
  readonly recovery: string;
}

export interface RuleDecision {
  readonly decision: RuleDecisionKind;
  readonly ruleId?: RuleSpec["id"];
  readonly reason?: string;
  readonly recovery?: string;
  readonly matches?: readonly RuleMatch[];
}

const isTrellisInit = (command: string | undefined): boolean =>
  /^\s*trellis\s+init(?:\s|$)/.test(command ?? "");

export const ruleRegistry: readonly RuleSpec[] = [
  {
    id: "no-trellis-init-outside-onboard",
    decision: "block-tool",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "tool" &&
      facts.insideOnboard !== true &&
      isTrellisInit(facts.toolCommand),
    reason:
      "Trellis initialization is only permitted through the approved Onboard workflow.",
    recovery:
      "Use /sbtd onboard plan, then confirm the generated Onboard action.",
  },
  {
    id: "bdd-required-for-visible-behavior",
    decision: "block-delivery",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "delivery" &&
      facts.userVisibleBehavior === true &&
      facts.bddCovered !== true,
    reason: "User-visible behavior has no persisted BDD coverage.",
    recovery:
      "Create or update the capability's .feature scenario before delivery.",
  },
  {
    id: "book-gate-before-edit",
    decision: "block-tool",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "tool" && facts.requiredBookGatesPassed === false,
    reason: "A Route-required Book Gate has not passed.",
    recovery:
      "Complete the required review and record its passing reviewer status.",
  },
  {
    id: "rtk-is-not-test-runner",
    decision: "block-stage",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "stage" &&
      facts.reportingTestUsingRtk === true &&
      facts.rtkSideEffectsVerified !== true,
    reason:
      "RTK output cannot prove a reporting test produced its required artifacts.",
    recovery:
      "Run the reporting test natively, then verify the report was freshly written.",
  },
  {
    id: "report-artifact-required",
    decision: "block-delivery",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "delivery" && facts.formalReportPresent === false,
    reason: "The planned validation report artifact is missing.",
    recovery:
      "Run the planned formal validation and retain its report before delivery.",
  },
  {
    id: "mock-is-not-full-stack",
    decision: "interrupt",
    configurable: true,
    strictOnly: true,
    enabled: true,
    applies: (facts) =>
      facts.action === "delivery" &&
      (facts.e2eMode === "contract-backed" ||
        facts.e2eMode === "mock-backed" ||
        facts.e2eMode === "app-mocked"),
    reason:
      "Mock-backed, contract-backed, and app-mocked evidence is not full-stack evidence.",
    recovery: "Report the actual E2E mode or run the complete real chain.",
  },
  {
    id: "gitnexus-requires-mcp-and-index",
    decision: "block-stage",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "stage" && facts.gitnexusReady === false,
    reason:
      "GitNexus evidence requires both a callable MCP and a current index.",
    recovery:
      "Restore the current GitNexus index or omit GitNexus from this route's evidence.",
  },
  {
    id: "maestro-requires-java17",
    decision: "block-stage",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "stage" && facts.maestroJava17 === false,
    reason: "Maestro requires Java 17 or newer.",
    recovery:
      "Install a supported Java runtime, then re-run the environment check.",
  },
  {
    id: "release-gate-before-complete",
    decision: "block-delivery",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "delivery" &&
      facts.productionPathRisk === true &&
      facts.releaseGateReady !== true,
    reason:
      "Production-path changes require a ready Release Readiness Gate before completion.",
    recovery:
      "Complete the required validation and record Release Readiness as ready.",
  },
  {
    id: "secret-read-guard",
    decision: "block-tool",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "tool" &&
      facts.secretRead === true &&
      facts.secretReadApproved !== true,
    reason: "Secret material cannot be read without an explicit approved path.",
    recovery:
      "Use a supported secret reference instead of reading or logging the secret.",
  },
  {
    id: "install-requires-approval",
    decision: "block-tool",
    configurable: false,
    enabled: true,
    applies: (facts) =>
      facts.action === "tool" &&
      facts.installingDependency === true &&
      facts.installApproved !== true,
    reason: "Dependency and global installation requires explicit approval.",
    recovery:
      "Present the installation plan and obtain approval before installing.",
  },
] as const;

export function setRuleEnabled(
  registry: readonly RuleSpec[],
  id: RuleSpec["id"],
  enabled: boolean,
): readonly RuleSpec[] {
  let found = false;
  const updated = registry.map((rule) => {
    if (rule.id !== id) return rule;
    found = true;
    if (!rule.configurable) throw new Error(`${id} is not configurable`);
    return { ...rule, enabled };
  });
  if (!found) throw new Error(`unknown Rule: ${id}`);
  return updated;
}

const decisionPrecedence: Readonly<Record<RuleDecisionKind, number>> = {
  allow: 0,
  remind: 1,
  interrupt: 2,
  "block-delivery": 3,
  "block-stage": 4,
  "block-tool": 5,
};

export function evaluateRuleRegistry(
  registry: readonly RuleSpec[],
  facts: RuleEvaluationFacts,
): RuleDecision {
  const matches = registry
    .filter(
      (rule) =>
        rule.enabled &&
        (rule.strictOnly !== true ||
          (facts.policyProfile ?? "strict") === "strict") &&
        rule.applies(facts),
    )
    .map(
      (rule): RuleMatch => ({
        ruleId: rule.id,
        decision: rule.decision,
        configurable: rule.configurable,
        severity: rule.configurable ? "optional" : "hard",
        reason: rule.reason,
        recovery: rule.recovery,
      }),
    );
  const effective = matches.reduce<RuleMatch | undefined>(
    (current, match) =>
      current === undefined ||
      decisionPrecedence[match.decision] > decisionPrecedence[current.decision]
        ? match
        : current,
    undefined,
  );
  return effective
    ? {
        decision: effective.decision,
        ruleId: effective.ruleId,
        reason: effective.reason,
        recovery: effective.recovery,
        matches,
      }
    : { decision: "allow" };
}
