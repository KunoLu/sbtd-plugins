import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { lstat, readdir, readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { relative, resolve, sep } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";
import { z } from "zod";
import {
  type AgentContext,
  discoverAgentContext,
  resolveAgentTargets,
} from "./agents/index.js";
import {
  completeSbtdCommand,
  parseSbtdCommand,
  renderSbtdHelp,
} from "./commands/index.js";
import {
  type AcceptedSkipContext,
  type AcceptedSkipList,
  type AcceptedSkipPlan,
  type AcceptedSkipScope,
  createAcceptedSkipService,
  eligibleAcceptedSkips,
} from "./environment/accepted-skip.js";
import {
  evaluateProfileEnvironment,
  type ProfileEnvironmentInput,
} from "./environment/index.js";
import {
  createToolEvidenceObserver,
  type ToolEvidenceFacet,
  type ToolEvidenceProbe,
  type ToolEvidenceRecord,
  toolEvidenceCapabilityIsReady,
} from "./environment/tool-evidence.js";
import {
  type EvidenceProcess,
  type EvidenceProcessResult,
  observeValidationEvidence,
  type RevisionObserver,
  type ValidationEvidenceObservation,
} from "./evidence/index.js";
import {
  type BookGateId,
  bookGateIds,
  createBookGatePlan,
  type ReviewerStatus,
  reviewerStatuses,
} from "./gates/index.js";
import {
  coreGateSkillNames,
  type EmbeddedKit,
  loadEmbeddedKit,
  releaseEmbeddedKit,
  resolveProfile,
} from "./kit/index.js";
import {
  type CompositeOnboardPlan,
  type CompositeOnboardService,
  createCompositeOnboardService,
  emptyApprovalSet,
} from "./onboard/composite.js";
import type {
  FileAdapter,
  OnboardPlan,
  OnboardService,
} from "./onboard/index.js";
import {
  createNodeFileAdapter,
  createOnboardService,
} from "./onboard/index.js";
import { createCanonicalOnboardRuntime } from "./onboard/python-runtime.js";
import {
  buildSbtdReport,
  type FormalArtifactDescriptor,
  formalArtifactDescriptorSchema,
  observeProviderSnapshot,
  providerUnavailableSnapshot,
  renderSbtdReport,
  type ValidationReport,
  validationReportSchema,
} from "./report/index.js";
import { evaluateRuleRegistry, ruleRegistry } from "./rules/index.js";
import {
  type RuntimeControllerHandlers,
  registerRuntimeController,
} from "./runtime/index.js";
import {
  inventoryPackagedSkills,
  observeAgentPluginDoctorBlock,
  pluginPackageRoot,
  readCertifiedOrGlobalSkill,
} from "./skills/index.js";
import type { SbtdSessionState } from "./state/index.js";
import {
  createStateService,
  deriveEffectiveControlState,
  SBTD_STATE_COMPACTION_KEY,
} from "./state/index.js";
import { observeToolRisk, ToolApprovalBook } from "./tool-risk/index.js";
import { getPluginVersion } from "./version.js";
import {
  classifyTaskPrompt,
  type ObjectiveTaskEvidence,
  type SBTDClassification,
  type WorkflowRouteId,
  workflowRouteIds,
} from "./workflow/index.js";

interface ObservedOnboardEnvironment {
  readonly observation: SbtdSessionState["environmentObservation"];
  readonly context: AgentContext;
  readonly toolEvidence: readonly ToolEvidenceRecord[];
  readonly acceptedSkips: AcceptedSkipList;
}

function routeRequiredCapabilities(
  route: SbtdSessionState["route"],
): readonly string[] {
  switch (route) {
    case "trellis-managed-task":
      return ["trellis"];
    case "bdd-user-visible-change":
    case "legacy-safe-change":
      return ["bdd-tdd"];
    case "web-runtime-diagnostics":
      return ["ui"];
    case "web-e2e-regression":
    case "mobile-e2e":
      return ["web-mobile-e2e"];
    case "release-readiness":
      return ["release"];
    default:
      return [];
  }
}

function isWorkflowRouteId(value: string): value is WorkflowRouteId {
  return (workflowRouteIds as readonly string[]).includes(value);
}

function isBookGateId(value: string): value is BookGateId {
  return (bookGateIds as readonly string[]).includes(value);
}

function isReviewerStatus(value: string): value is ReviewerStatus {
  return (reviewerStatuses as readonly string[]).includes(value);
}

const optionalCapabilitySkills: Readonly<
  Record<string, readonly string[] | undefined>
> = {
  trellis: ["trellis-workflow"],
  "bdd-tdd": ["gherkin-bdd", "tdd"],
  ui: ["ui-ux-pro-max"],
  release: ["book-release-readiness"],
};

function acceptedSkipKitMajor(embedded: EmbeddedKit): number {
  const match = /(?:^|-)v(\d+)$/.exec(embedded.provenance.transformVersion);
  if (match?.[1] === undefined)
    throw new Error("Verified Kit has no supported AcceptedSkip major.");
  return Number(match[1]);
}

function projectRootKey(projectRoot: string): string {
  return createHash("sha256").update(resolve(projectRoot)).digest("hex");
}

type SkipPlanOptionName = "scope" | "expires" | "reason";

function parseSkipPlanOptions(
  args: readonly string[],
  required: readonly SkipPlanOptionName[],
): Readonly<Partial<Record<SkipPlanOptionName, string>>> | undefined {
  const options: Partial<Record<SkipPlanOptionName, string>> = {};
  for (let index = 0; index < args.length; index += 2) {
    const token = args[index];
    const value = args[index + 1];
    if (token === undefined || value === undefined || !token.startsWith("--"))
      return undefined;
    const name = token.slice(2) as SkipPlanOptionName;
    if (!required.includes(name) || options[name] !== undefined)
      return undefined;
    options[name] = value;
  }
  return required.every((name) => options[name] !== undefined)
    ? options
    : undefined;
}

const managedAgentRoles = ["global", "project-root", "project-omp"] as const;

const skillFacet = <T extends string>(
  value: T,
  evidence: string,
  blockedReason?: string,
): ToolEvidenceFacet<T> => ({
  value,
  evidence,
  ...(blockedReason === undefined ? {} : { blockedReason }),
});

function capabilityIds(
  profiles: readonly ProfileEnvironmentInput["profile"][],
  routeRequirements: readonly string[],
): readonly string[] {
  return [
    ...new Set([
      ...profiles.flatMap((profile) => [
        ...profile.required,
        ...profile.optional,
      ]),
      ...routeRequirements,
    ]),
  ].sort();
}

function planTargetIsManaged(
  plan: OnboardPlan,
  role: "global" | "project-root" | "project-omp",
): boolean {
  return plan.targets.some(
    (target) => target.target.role === role && target.action === "skip",
  );
}

function agentTargetIsCallable(
  context: AgentContext,
  role: "global" | "project-root" | "project-omp",
): boolean {
  return context.targets.some(
    (target) => target.role === role && target.loaded && target.effective,
  );
}

function agentTargetExists(
  context: AgentContext,
  role: "global" | "project-root" | "project-omp",
): boolean {
  return context.targets.some(
    (target) => target.role === role && target.exists,
  );
}

function resolveGlobalSkillsDirectory(agentDirectory: string): string {
  return process.env.AGENT_SKILLS_DIR || resolve(agentDirectory, "skills");
}

async function observeCapabilityToolEvidence(
  files: FileAdapter,
  agentDirectory: string,
  projectRoot: string,
  plan: OnboardPlan,
  context: AgentContext,
  embedded: EmbeddedKit,
  routeRequirements: readonly string[],
  observedAt: string,
  persist: boolean,
): Promise<readonly ToolEvidenceRecord[]> {
  const skillsDirectory = resolveGlobalSkillsDirectory(agentDirectory);
  const packaged = await inventoryPackagedSkills();
  const requiredSkillContents = await Promise.all(
    coreGateSkillNames.map((name) =>
      readCertifiedOrGlobalSkill(files, name, packaged.names, skillsDirectory, {
        invalidSkills: packaged.invalidSkills,
      }),
    ),
  );
  const optionalSkillEntries = await Promise.all(
    Object.entries(optionalCapabilitySkills).flatMap(([capability, names]) =>
      (names ?? []).map(
        async (name) =>
          [
            `${capability}:${name}`,
            await readCertifiedOrGlobalSkill(
              files,
              name,
              packaged.names,
              skillsDirectory,
              { invalidSkills: packaged.invalidSkills },
            ),
          ] as const,
      ),
    ),
  );
  const optionalSkillContents: Readonly<Record<string, string | undefined>> =
    Object.fromEntries(optionalSkillEntries);
  const trellisWorkflow = await files.readText(
    `${projectRoot}/.trellis/workflow.md`,
  );
  const observer = createToolEvidenceObserver({
    files,
    storePath: `${agentDirectory}/kpi/tool-evidence-v1.json`,
    kitRevision: embedded.provenance.generatedSha256,
    scope: "project",
    projectRoot,
    probeRegistryVersion: "p0-v2",
    now: () => observedAt,
    persist,
  });
  const skillsAreConfigured = (capability: string): boolean =>
    (optionalCapabilitySkills[capability] ?? []).every((name) => {
      const content = optionalSkillContents[`${capability}:${name}`];
      return content !== undefined && content.trim().length > 0;
    });
  const skillsAreInstalled = (capability: string): boolean =>
    (optionalCapabilitySkills[capability] ?? []).every(
      (name) => optionalSkillContents[`${capability}:${name}`] !== undefined,
    );
  const capabilityProbes = capabilityIds(
    embedded.profiles,
    routeRequirements,
  ).map((capability): ToolEvidenceProbe => {
    const fingerprint = createHash("sha256")
      .update(
        JSON.stringify({
          kitDigest: embedded.provenance.generatedSha256,
          capability,
          importValid: context.importValid,
          targets: context.targets.map((target) => [
            target.role,
            target.exists,
            target.loaded,
            target.effective,
          ]),
          planTargets: plan.targets.map((target) => [
            target.target.role,
            target.action,
          ]),
          coreSkills: requiredSkillContents.map((content) =>
            content === undefined
              ? "absent"
              : createHash("sha256").update(content).digest("hex"),
          ),
          optionalSkills: Object.entries(optionalSkillContents)
            .sort(([left], [right]) => left.localeCompare(right))
            .map(([key, content]) => [
              key,
              content === undefined
                ? "absent"
                : createHash("sha256").update(content).digest("hex"),
            ]),
          trellisWorkflow:
            trellisWorkflow === undefined
              ? "absent"
              : createHash("sha256").update(trellisWorkflow).digest("hex"),
        }),
      )
      .digest("hex");
    const agentProbe = (
      role: "global" | "project-root" | "project-omp",
    ): ToolEvidenceProbe => ({
      toolId: `agents-${role}`,
      capability,
      subject: "runtime-capability",
      inputFingerprint: fingerprint,
      validityMs: 60_000,
      async observeInstallation() {
        return agentTargetExists(context, role)
          ? skillFacet("installed", `AGENTS ${role} target exists`)
          : skillFacet("missing", `AGENTS ${role} target is absent`);
      },
      async observeConfiguration() {
        return planTargetIsManaged(plan, role)
          ? skillFacet(
              "configured",
              `AGENTS ${role} Managed Block matches Plan`,
            )
          : skillFacet(
              "not-configured",
              `AGENTS ${role} Managed Block needs Onboard`,
            );
      },
      async observeCallability() {
        return agentTargetIsCallable(context, role)
          ? skillFacet("callable", `AGENTS ${role} is loaded and effective`)
          : skillFacet(
              "unavailable",
              `AGENTS ${role} is not loaded and effective`,
            );
      },
      async observeProjectReadiness() {
        return role === "global"
          ? skillFacet("not-needed", "global AGENTS has no project predicate")
          : context.importValid
            ? skillFacet("ready", "project AGENTS import chain is valid")
            : skillFacet(
                "blocked",
                "project AGENTS import chain is invalid",
                "/sbtd onboard plan",
              );
      },
      async observeFreshness() {
        return skillFacet(
          "current",
          "AGENTS Plan and discovery inputs are current",
        );
      },
    });
    switch (capability) {
      case "global-agents":
        return agentProbe("global");
      case "project-root-agents":
        return agentProbe("project-root");
      case "project-omp-adapter":
        return agentProbe("project-omp");
      case "plugin-kit-alignment":
        return {
          toolId: "omp-sbtd-plugin",
          capability,
          subject: "runtime-capability",
          inputFingerprint: fingerprint,
          validityMs: 60_000,
          async observeInstallation() {
            return skillFacet("installed", "verified embedded SBTD Kit loaded");
          },
          async observeConfiguration() {
            return embedded.kit.sourceRevision ===
              embedded.provenance.resolvedRevision
              ? skillFacet(
                  "configured",
                  "Kit catalog revision matches provenance",
                )
              : skillFacet(
                  "not-configured",
                  "Kit catalog revision does not match provenance",
                  "/sbtd doctor",
                );
          },
          async observeCallability() {
            return skillFacet(
              "callable",
              "OMP plugin runtime loaded verified Kit",
            );
          },
          async observeProjectReadiness() {
            return plan.kit.kitRevision === embedded.kit.kitRevision
              ? skillFacet("ready", "Onboard Plan is bound to verified Kit")
              : skillFacet(
                  "blocked",
                  "Onboard Plan is not bound to the verified Kit",
                  "/sbtd onboard plan",
                );
          },
          async observeFreshness() {
            return skillFacet("current", "verified Kit identity is current");
          },
        };
      case "always-on-baseline":
        return {
          toolId: "always-on-baseline",
          capability,
          subject: "runtime-capability",
          inputFingerprint: fingerprint,
          validityMs: 60_000,
          async observeInstallation() {
            return managedAgentRoles.every((role) =>
              agentTargetExists(context, role),
            )
              ? skillFacet("installed", "all AGENTS layer targets exist")
              : skillFacet(
                  "missing",
                  "one or more AGENTS layer targets are absent",
                );
          },
          async observeConfiguration() {
            return managedAgentRoles.every((role) =>
              planTargetIsManaged(plan, role),
            )
              ? skillFacet("configured", "all AGENTS Managed Blocks match Plan")
              : skillFacet(
                  "not-configured",
                  "one or more AGENTS Managed Blocks need Onboard",
                );
          },
          async observeCallability() {
            return managedAgentRoles.every((role) =>
              agentTargetIsCallable(context, role),
            )
              ? skillFacet(
                  "callable",
                  "all AGENTS layers are loaded and effective",
                )
              : skillFacet(
                  "unavailable",
                  "one or more AGENTS layers are not effective",
                );
          },
          async observeProjectReadiness() {
            return context.importValid
              ? skillFacet("ready", "AGENTS import chain is valid")
              : skillFacet(
                  "blocked",
                  "AGENTS import chain is invalid",
                  "/sbtd onboard plan",
                );
          },
          async observeFreshness() {
            return skillFacet(
              "current",
              "AGENTS Plan and discovery inputs are current",
            );
          },
        };
      case "core-gate-skills":
        return {
          toolId: "core-gate-skills",
          capability,
          subject: "non-executable-skill",
          inputFingerprint: fingerprint,
          validityMs: 60_000,
          async observeInstallation() {
            return requiredSkillContents.every(
              (content) => content !== undefined,
            )
              ? skillFacet(
                  "installed",
                  "all Core Gate Skill files are installed",
                )
              : skillFacet("missing", "a Core Gate Skill file is absent");
          },
          async observeConfiguration() {
            return requiredSkillContents.every(
              (content) => content !== undefined && content.trim().length > 0,
            )
              ? skillFacet(
                  "configured",
                  "all Core Gate Skill files are configured",
                )
              : skillFacet(
                  "not-configured",
                  "a Core Gate Skill file is absent or empty",
                );
          },
          async observeCallability() {
            return skillFacet(
              "not-needed",
              "Core Gate Skills are non-executable Skills",
            );
          },
          async observeProjectReadiness() {
            return skillFacet(
              "not-needed",
              "Core Gate Skills are global Skills",
            );
          },
          async observeFreshness() {
            return skillFacet(
              "current",
              "Core Gate Skill file observations are current",
            );
          },
        };
      case "trellis":
      case "bdd-tdd":
      case "ui":
      case "release":
        return {
          toolId: `${capability}-skills`,
          capability,
          subject: "non-executable-skill",
          inputFingerprint: fingerprint,
          validityMs: 60_000,
          async observeInstallation() {
            return skillsAreInstalled(capability)
              ? skillFacet(
                  "installed",
                  `${capability} Skill files are installed`,
                )
              : skillFacet("missing", `${capability} Skill file is absent`);
          },
          async observeConfiguration() {
            return skillsAreConfigured(capability)
              ? skillFacet(
                  "configured",
                  `${capability} Skill files are configured`,
                )
              : skillFacet(
                  "not-configured",
                  `${capability} Skill files are absent or empty`,
                );
          },
          async observeCallability() {
            return skillFacet(
              "not-needed",
              `${capability} is a non-executable Skill capability`,
            );
          },
          async observeProjectReadiness() {
            return capability !== "trellis"
              ? skillFacet(
                  "not-needed",
                  `${capability} Skills have no project predicate`,
                )
              : trellisWorkflow?.trim().length !== 0
                ? skillFacet("ready", "Trellis workflow file is present")
                : skillFacet(
                    "not-ready",
                    "Trellis workflow file is absent or empty",
                  );
          },
          async observeFreshness() {
            return skillFacet(
              "current",
              `${capability} Skill inputs are current`,
            );
          },
        };
      case "gitnexus":
      case "web-mobile-e2e":
        return {
          toolId: capability,
          capability,
          subject: "external-tool",
          inputFingerprint: fingerprint,
          validityMs: 60_000,
          async observeInstallation() {
            return skillFacet(
              "missing",
              `${capability} has no approved shell-free installation observer`,
              "/sbtd onboard plan",
            );
          },
          async observeConfiguration() {
            return skillFacet(
              "not-configured",
              `${capability} has no approved shell-free configuration observer`,
              "/sbtd doctor",
            );
          },
          async observeCallability() {
            return skillFacet(
              "blocked",
              `${capability} callability is not probed without an approved host adapter`,
              "/sbtd doctor",
            );
          },
          async observeProjectReadiness() {
            return skillFacet(
              "not-ready",
              `${capability} project readiness cannot be established without an approved host adapter`,
              "/sbtd doctor",
            );
          },
          async observeFreshness() {
            return skillFacet(
              "current",
              `${capability} registry policy is current`,
            );
          },
        };
      default:
        return {
          toolId: capability,
          capability,
          subject: "runtime-capability",
          inputFingerprint: fingerprint,
          validityMs: 60_000,
          async observeInstallation() {
            return skillFacet(
              "missing",
              `no registry observer for ${capability}`,
            );
          },
          async observeConfiguration() {
            return skillFacet(
              "not-configured",
              `no registry observer for ${capability}`,
            );
          },
          async observeCallability() {
            return skillFacet(
              "blocked",
              `no registry observer for ${capability}`,
            );
          },
          async observeProjectReadiness() {
            return skillFacet(
              "not-ready",
              `no registry observer for ${capability}`,
            );
          },
          async observeFreshness() {
            return skillFacet(
              "unknown",
              `no registry observer for ${capability}`,
            );
          },
        };
    }
  });
  return (await observer.observe(capabilityProbes)).records;
}

function evaluateObservedEnvironment(
  plan: OnboardPlan,
  profile: ProfileEnvironmentInput["profile"],
  routeRequirements: readonly string[],
  records: readonly ToolEvidenceRecord[],
  acceptedOptionalSkips: readonly {
    readonly capability: string;
    readonly expiresAt: string;
  }[],
  observedAt: string,
) {
  const blockedReasons = plan.targets
    .filter((target) => target.action === "blocked")
    .map((target) => target.recovery);
  if (blockedReasons.length > 0)
    return {
      observedAt,
      mode: "blocked" as const,
      evidence: blockedReasons,
      repairPath: "/sbtd doctor",
    };
  const recordsByCapability = new Map(
    records.map((record) => [record.capability, record]),
  );
  return evaluateProfileEnvironment(
    {
      profile,
      capabilities: Object.fromEntries(
        capabilityIds([profile], routeRequirements).map((capability) => [
          capability,
          toolEvidenceCapabilityIsReady(recordsByCapability.get(capability)),
        ]),
      ),
      routeRequiredCapabilities: routeRequirements,
      acceptedOptionalSkips,
    },
    observedAt,
  );
}

function renderStatus(
  state: SbtdSessionState,
  context?: AgentContext,
  embedded?: EmbeddedKit,
  toolEvidence: readonly ToolEvidenceRecord[] = [],
  acceptedSkips?: AcceptedSkipList,
): string {
  const effective = deriveEffectiveControlState(
    state.runtimeMode,
    state.environmentObservation.mode,
  );
  return [
    `Runtime Mode: ${state.runtimeMode}`,
    `Policy Profile: ${state.policyProfile}`,
    `Onboard Profile: ${state.onboardProfileId}`,
    `Security Baseline: ${state.securityBaseline}`,
    ...(embedded
      ? [
          `Kit Source: ${embedded.provenance.sourceId}`,
          `Kit Source URI: ${embedded.provenance.canonicalSourceUri}`,
          `Kit Revision: ${embedded.provenance.resolvedRevision}`,
          `Kit Manifest Digest: ${embedded.provenance.manifestSha256}`,
          `Kit Canonical Manifest Digest: ${embedded.provenance.canonicalManifestSha256}`,
          `Kit Projection Digest: ${embedded.provenance.projectionSha256}`,
          `Kit Generated Digest: ${embedded.provenance.generatedSha256}`,
          `Kit Freshness: ${embedded.freshness}`,
        ]
      : []),
    `Route: ${state.route}`,
    `Environment Mode: ${state.environmentObservation.mode}`,
    `Effective Control State: ${effective}`,
    `Repair: ${state.environmentObservation.repairPath}`,
    `Classification: ${state.classification ? JSON.stringify(state.classification) : "not-classified"}`,
    `Book Gates: ${state.bookGates ? JSON.stringify(state.bookGates) : "not-planned"}`,
    `Rule Decisions: ${state.ruleDecisions.length > 0 ? JSON.stringify(state.ruleDecisions) : "none"}`,
    `Stage: ${state.stage ? JSON.stringify(state.stage) : "not-started"}`,
    ...(state.validationReport === undefined
      ? [
          "Validation Check Requirement: not-applicable",
          "Validation Status: not-needed",
          "Actual E2E Mode: not-needed",
        ]
      : [
          `Validation Check Requirement: ${state.validationReport.checkRequirement}`,
          `Validation Status: ${state.validationReport.validationStatus}`,
          `Actual E2E Mode: ${state.validationReport.e2eMode}`,
          `Evidence Envelope: source=${state.validationReport.evidenceEnvelope.evidenceSource} revision=${state.validationReport.evidenceEnvelope.sourceRevision} alignment=${state.validationReport.evidenceEnvelope.environmentAlignment} publication=${state.validationReport.evidenceEnvelope.evidencePublication}`,
        ]),
    ...(state.providerObservation === undefined
      ? [
          "Provider Availability: unknown",
          "Provider Fallback: unavailable",
          "Provider Selection Result: unknown",
        ]
      : [
          `Provider: ${state.providerObservation.provider ?? "unknown"}`,
          `Provider Model: ${state.providerObservation.model ?? "unknown"}`,
          `Provider Availability: ${state.providerObservation.availability}`,
          `Provider Fallback: ${state.providerObservation.fallback}`,
          `Provider Selection Result: ${state.providerObservation.selection}`,
          ...(state.providerObservation.blockerCode === undefined
            ? []
            : [`Provider Blocker: ${state.providerObservation.blockerCode}`]),
        ]),
    ...toolEvidence.map(
      (record) =>
        `Tool Evidence ${record.capability}: installation=${record.installation} configuration=${record.configuration} callability=${record.callability} project-readiness=${record.projectReadiness} freshness=${record.freshness}${record.blockedReason ? ` repair=${record.blockedReason}` : ""}`,
    ),
    ...(acceptedSkips?.kind === "invalid-store"
      ? [`AcceptedSkip Store: invalid; repair=${acceptedSkips.message}`]
      : (acceptedSkips?.effectiveRecords ?? []).map((record) => {
          const validity =
            record.status === "active" &&
            record.expiresAt > state.environmentObservation.observedAt
              ? "eligible-candidate"
              : record.status === "active"
                ? "expired"
                : record.status;
          return `AcceptedSkip ${record.recordId}: capability=${record.capability} scope=${record.scope} profile=${record.onboardProfileId} kit-major=${record.kitMajor} status=${record.status} validity=${validity} owner=${record.actor.kind} provenance=${record.provenance.sourceId}@${record.provenance.kitRevision} repair=/sbtd onboard skip plan revoke ${record.recordId} --reason <text>`;
        })),
    ...(context
      ? [
          `Root Project Facts Import: ${context.importValid ? "valid" : "invalid"}`,
          ...context.targets.map(
            (target) =>
              `AGENTS ${target.role}: exists=${target.exists} discovered=${target.discovered} loaded=${target.loaded} effective=${target.effective}${target.shadowedBy ? ` shadowedBy=${target.shadowedBy}` : ""}`,
          ),
        ]
      : []),
  ].join("\n");
}

function escapeXmlAttribute(value: string | number): string {
  return String(value).replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&apos;",
      })[character] as string,
  );
}

function renderRuntimeMarker(
  state: SbtdSessionState,
  kitRevision: string,
): string {
  const effective = deriveEffectiveControlState(
    state.runtimeMode,
    state.environmentObservation.mode,
  );
  return `<sbtd-runtime state-version="${escapeXmlAttribute(state.stateVersion)}" kit-revision="${escapeXmlAttribute(kitRevision)}" runtime-mode="${escapeXmlAttribute(state.runtimeMode)}" policy-profile="${escapeXmlAttribute(state.policyProfile)}" environment-mode="${escapeXmlAttribute(state.environmentObservation.mode)}" effective-control-state="${escapeXmlAttribute(effective)}" route="${escapeXmlAttribute(state.route)}" stage="${escapeXmlAttribute(state.stage?.id ?? "intake")}" />`;
}

const bashToolCallSchema = z
  .object({
    toolName: z.literal("bash"),
    input: z.object({ command: z.string() }).passthrough(),
  })
  .passthrough();

const toolCallSchema = z.object({ toolName: z.string() }).passthrough();

function isMutationOrPhaseAdvancingTool(event: unknown): boolean {
  // Capability registry seam (P1-04/P2-01): safe diagnostics (read/grep/glob/
  // lsp/ast_grep/debug/recall/web_search/todo/ask) stay available in
  // preflight-only/blocked; unknown tools and remote locators fail closed.
  return observeToolRisk(event).mutationOrPhaseAdvancing;
}

function isPlanningArtifactTool(
  event: unknown,
  projectRoot: string | undefined,
): boolean {
  const parsed = toolCallSchema.safeParse(event);
  if (
    !parsed.success ||
    !["write", "edit"].includes(parsed.data.toolName) ||
    typeof parsed.data.input !== "object" ||
    parsed.data.input === null
  )
    return false;
  const input = parsed.data.input as Record<string, unknown>;
  const targets = [input.path, input.patch].filter(
    (value): value is string => typeof value === "string",
  );
  const candidatePaths = targets.flatMap((target) => [
    target,
    ...Array.from(target.matchAll(/\[([^#\]\n]+)#/g), ([, path]) => path ?? ""),
  ]);
  return candidatePaths.some((path) => {
    const normalized =
      projectRoot === undefined
        ? path
        : relative(projectRoot, resolve(projectRoot, path)).replaceAll(
            "\\",
            "/",
          );
    return /^(?:features\/|\.trellis\/tasks\/|(?:test|tests)\/|__tests__\/)/.test(
      normalized,
    );
  });
}
function commandFromToolEvent(event: unknown): string | undefined {
  return bashToolCallSchema.safeParse(event).data?.input.command;
}

function requiredBookGatesPassedForCurrentStage(
  state: SbtdSessionState,
): boolean | undefined {
  const phaseRank = {
    "requirement-confirmation": 0,
    "before-design": 1,
    "before-implementation": 2,
    "after-validation": 3,
  } as const;
  const currentPhase =
    state.stage?.id === "requirement-confirmation"
      ? 0
      : state.stage?.id === "design"
        ? 1
        : state.stage?.id === "delivery"
          ? 3
          : 2;
  const required = state.bookGates?.filter(
    (gate) => gate.required && phaseRank[gate.plannedPhase] <= currentPhase,
  );
  return required && required.length > 0
    ? required.every((gate) => gate.gateState === "passed")
    : undefined;
}

async function hasPersistedBddCoverage(projectRoot: string): Promise<boolean> {
  try {
    const entries = await readdir(`${projectRoot}/features`, {
      recursive: true,
    });
    return entries.some((entry) => entry.endsWith(".feature"));
  } catch {
    return false;
  }
}

// P1-04: the mtime-based hasFreshBddCoverage heuristic was removed. BDD
// delivery evidence now derives exclusively from the validation evidence
// observer (embedded Kit v2 validator + revision binding); an unrelated
// .feature touch never satisfies BDD.

async function fileIntegrity(path: string) {
  const details = await lstat(path);
  if (!details.isFile())
    throw new Error("Formal report paths must be regular files");
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return {
    sizeBytes: details.size,
    sha256: hash.digest("hex"),
    modifiedAt: details.mtime.toISOString(),
  };
}
const chineseText = /[\u3400-\u9fff\uf900-\ufaff]/u;

async function hasChineseMarkdownText(path: string): Promise<boolean> {
  for await (const chunk of createReadStream(path, { encoding: "utf8" })) {
    if (chineseText.test(String(chunk))) return true;
  }
  return false;
}

async function observeFreshPairedReports(
  projectRoot: string,
  directory: string,
  runner: "playwright" | "api" | "maestro",
  reportPattern: RegExp,
  observedAfter: number,
  observedAt: string,
): Promise<readonly FormalArtifactDescriptor[]> {
  try {
    const entries = await readdir(directory, { recursive: true });
    const artifacts = await Promise.all(
      entries
        .filter((entry) => reportPattern.test(entry))
        .sort()
        .map(async (report) => {
          const markdown = report.replace(/\.(?:html|json|txt|xml)$/, ".md");
          if (!entries.includes(markdown)) return undefined;
          const reportFile = resolve(directory, report);
          const markdownFile = resolve(directory, markdown);
          const [reportStats, markdownStats] = await Promise.all([
            lstat(reportFile),
            lstat(markdownFile),
          ]);
          if (
            !reportStats.isFile() ||
            !markdownStats.isFile() ||
            reportStats.mtimeMs < observedAfter ||
            markdownStats.mtimeMs < observedAfter
          )
            return undefined;
          if (!(await hasChineseMarkdownText(markdownFile))) return undefined;
          const artifact = formalArtifactDescriptorSchema.parse({
            status: "available",
            runner,
            reportPath: relative(projectRoot, reportFile).split(sep).join("/"),
            markdownPath: relative(projectRoot, markdownFile)
              .split(sep)
              .join("/"),
            observedAt,
            report: await fileIntegrity(reportFile),
            markdown: await fileIntegrity(markdownFile),
          });
          return artifact.status === "available" ? artifact : undefined;
        }),
    );
    return artifacts.filter((artifact) => artifact !== undefined);
  } catch {
    return [];
  }
}

async function observeFormalValidationReport(
  projectRoot: string,
  observedAfter: number,
  observedAt: string,
): Promise<FormalArtifactDescriptor> {
  const artifacts = (
    await Promise.all([
      observeFreshPairedReports(
        projectRoot,
        `${projectRoot}/tests/e2e/reports/html`,
        "playwright",
        /^playwright-report-.+\.html$/,
        observedAfter,
        observedAt,
      ),
      observeFreshPairedReports(
        projectRoot,
        `${projectRoot}/tests/api/reports`,
        "api",
        /^api-report-.+\.(?:html|json|txt|xml)$/,
        observedAfter,
        observedAt,
      ),
      observeFreshPairedReports(
        projectRoot,
        `${projectRoot}/.maestro/reports`,
        "maestro",
        /^maestro-report-.+\.(?:html|xml)$/,
        observedAfter,
        observedAt,
      ),
    ])
  )
    .flat()
    .sort((left, right) =>
      left.status === "available" && right.status === "available"
        ? left.reportPath.localeCompare(right.reportPath)
        : 0,
    );
  const available = artifacts.find(
    (artifact) => artifact.status === "available",
  );
  if (available !== undefined) return available;
  return formalArtifactDescriptorSchema.parse({
    status: "blocked",
    observedAt,
    blockedReason: "formal-report-required",
    recoveryCode: "create-fresh-same-stem-report-pair",
  });
}

function validationReportForFormalArtifact(
  artifact: FormalArtifactDescriptor,
): ValidationReport {
  const formalArtifactAvailable = artifact.status === "available";
  return {
    schemaVersion: 1,
    checkRequirement: "required",
    validationStatus: "blocked",
    e2eMode: "blocked",
    observedAt: artifact.observedAt,
    evidenceEnvelope: {
      evidenceSource: "developer-local",
      sourceRevision: "unknown",
      environmentAlignment: "unverified",
      evidencePublication: formalArtifactAvailable ? "local-only" : "blocked",
    },
    formalArtifact: artifact,
    blockedReason: formalArtifactAvailable
      ? "validation-result-unobserved"
      : "formal-report-required",
  };
}

/**
 * Reports a found-but-not-verified evidence observation for session
 * visibility. The report is always `blocked` — a rejected envelope is never
 * presented as validation success, and specification/execution stay separate
 * in the blocker code.
 */
function validationReportForEvidenceObservation(
  observation: ValidationEvidenceObservation,
  observedAt: string,
): ValidationReport {
  const blockedReason = !observation.executionVerified
    ? observation.specificationTraceable
      ? "evidence-execution-failed"
      : "evidence-not-verified"
    : "evidence-stale-revision";
  const candidate = {
    schemaVersion: 1 as const,
    checkRequirement: "required" as const,
    validationStatus: "blocked" as const,
    e2eMode: observation.e2eMode ?? "blocked",
    observedAt,
    evidenceEnvelope: {
      evidenceSource: observation.evidenceSource ?? "developer-local",
      sourceRevision: observation.sourceRevision ?? "unknown",
      environmentAlignment: observation.environmentAlignment ?? "unverified",
      evidencePublication: observation.evidencePublication ?? "blocked",
    },
    blockedReason,
  };
  const parsed = validationReportSchema.safeParse(candidate);
  return parsed.success
    ? parsed.data
    : {
        schemaVersion: 1,
        checkRequirement: "required",
        validationStatus: "blocked",
        e2eMode: "blocked",
        observedAt,
        evidenceEnvelope: {
          evidenceSource: "developer-local",
          sourceRevision: "unknown",
          environmentAlignment: "unverified",
          evidencePublication: "blocked",
        },
        blockedReason,
      };
}

async function directoryExists(path: string): Promise<boolean> {
  try {
    await readdir(path);
    return true;
  } catch {
    return false;
  }
}

async function hasActiveTrellisTask(projectRoot: string): Promise<boolean> {
  const tasksRoot = `${projectRoot}/.trellis/tasks`;
  const directories = await readdir(tasksRoot, { withFileTypes: true }).catch(
    () => [],
  );
  const statuses = await Promise.all(
    directories
      .filter((entry) => entry.isDirectory())
      .map(async (entry) => {
        try {
          const text = await readFile(
            `${tasksRoot}/${entry.name}/task.json`,
            "utf8",
          );
          const parsed = z
            .object({ status: z.string() })
            .safeParse(JSON.parse(text));
          return parsed.success && parsed.data.status === "in_progress";
        } catch {
          return false;
        }
      }),
  );
  return statuses.some(Boolean);
}

async function observeChangedPaths(
  pi: Pick<ExtensionAPI, "exec">,
  projectRoot: string,
): Promise<readonly string[]> {
  try {
    const [changed, untracked] = await Promise.all([
      pi.exec("git", ["diff", "--name-only", "--no-ext-diff", "HEAD"], {
        cwd: projectRoot,
      }),
      pi.exec("git", ["ls-files", "--others", "--exclude-standard"], {
        cwd: projectRoot,
      }),
    ]);
    return [
      ...new Set(
        [changed, untracked].flatMap((result) =>
          result.code === 0
            ? result.stdout.split("\n").filter((path) => path.length > 0)
            : [],
        ),
      ),
    ];
  } catch {
    return [];
  }
}

async function observeObjectiveTaskEvidence(
  pi: Pick<ExtensionAPI, "exec">,
  projectRoot: string,
): Promise<ObjectiveTaskEvidence> {
  const [
    rootProjectFacts,
    trellisWorkflow,
    activeTrellisTask,
    persistedBddCoverage,
    testRoot,
    testsRoot,
    sourceRoot,
    packagesRoot,
    changedPaths,
  ] = await Promise.all([
    readFile(`${projectRoot}/AGENTS.md`, "utf8").then(
      () => true,
      () => false,
    ),
    readFile(`${projectRoot}/.trellis/workflow.md`, "utf8").then(
      () => true,
      () => false,
    ),
    hasActiveTrellisTask(projectRoot),
    hasPersistedBddCoverage(projectRoot),
    directoryExists(`${projectRoot}/test`),
    directoryExists(`${projectRoot}/tests`),
    directoryExists(`${projectRoot}/src`),
    directoryExists(`${projectRoot}/packages`),
    observeChangedPaths(pi, projectRoot),
  ]);
  return {
    rootProjectFacts,
    trellisWorkflow,
    activeTrellisTask,
    persistedBddCoverage,
    testAssetsPresent: testRoot || testsRoot,
    productionSource: sourceRoot || packagesRoot,
    changedPathsObserved: changedPaths.length > 0,
    changedProductionPath: changedPaths.some((path) =>
      /(?:^|\/)(?:src|packages)\/.+\.(?:[cm]?[jt]sx?|cs|php|go|py|java|kt|rb|rs|swift|scala|sql|vue|svelte)$/.test(
        path,
      ),
    ),
  };
}

function routeRequiresFormalValidationReport(
  classification: Pick<SBTDClassification, "route"> | undefined,
): boolean {
  return (
    classification?.route === "web-e2e-regression" ||
    classification?.route === "mobile-e2e"
  );
}

async function observeOnboardEnvironment(
  onboard: OnboardService,
  files: FileAdapter,
  projectRoot: string,
  agentDirectory: string,
  embedded: EmbeddedKit,
  profileId: string,
  route: SbtdSessionState["route"],
  observedAt: string,
  persistToolEvidence: boolean,
): Promise<ObservedOnboardEnvironment> {
  const profile = resolveProfile(embedded.profiles, profileId);
  const acceptedSkipStore = createAcceptedSkipService({
    files,
    agentDirectory,
    now: () => observedAt,
  });
  const [plan, context, acceptedSkips] = await Promise.all([
    onboard.plan(),
    discoverAgentContext({
      targets: resolveAgentTargets(projectRoot, agentDirectory),
      readText: files.readText,
    }),
    acceptedSkipStore.list(),
  ]);
  const routeRequirements = routeRequiredCapabilities(route);
  const toolEvidence = await observeCapabilityToolEvidence(
    files,
    agentDirectory,
    projectRoot,
    plan,
    context,
    embedded,
    routeRequirements,
    observedAt,
    persistToolEvidence,
  );
  const acceptedSkipContext = (
    scope: AcceptedSkipScope,
  ): AcceptedSkipContext => ({
    scope,
    ...(scope === "project"
      ? { projectRootKey: projectRootKey(projectRoot) }
      : {}),
    onboardProfileId: profile.id,
    kitMajor: acceptedSkipKitMajor(embedded),
    route,
    profile,
    routeRequiredCapabilities: routeRequirements,
    provenance: {
      sourceId: embedded.provenance.sourceId,
      kitRevision: embedded.provenance.generatedSha256,
      transformVersion: embedded.provenance.transformVersion,
    },
  });
  const acceptedOptionalSkips =
    acceptedSkips.kind === "ok"
      ? (["global", "project"] as const)
          .flatMap((scope) =>
            eligibleAcceptedSkips(
              acceptedSkips.records,
              acceptedSkipContext(scope),
              observedAt,
            ),
          )
          .map((record) => ({
            capability: record.capability,
            expiresAt: record.expiresAt,
          }))
      : [];
  return {
    observation: evaluateObservedEnvironment(
      plan,
      profile,
      routeRequirements,
      toolEvidence,
      acceptedOptionalSkips,
      observedAt,
    ),
    context,
    toolEvidence,
    acceptedSkips,
  };
}
function effectiveRouteForObservation(
  state: Pick<SbtdSessionState, "route" | "classification">,
): SbtdSessionState["route"] {
  return state.route === "auto"
    ? (state.classification?.route ?? "auto")
    : state.route;
}

interface SessionTransientState {
  readonly approvalBook: ToolApprovalBook;
  readonly pendingAcceptedSkipPlans: Map<string, AcceptedSkipPlan>;
  activeTurnId: string | undefined;
  activeClassification: SBTDClassification | undefined;
  activeClassificationObservedAt: number | undefined;
  activeAutomaticClassification: SBTDClassification | undefined;
  blockedDeliveryFingerprint: string | undefined;
  readonly pendingEvidenceInvalidation: Set<string>;
}

export default function extension(
  pi: Parameters<typeof registerRuntimeController>[0],
): void {
  const anonymousSessionKeys = new WeakMap<object, string>();
  let nextAnonymousSessionKey = 0;
  const sessionIdFor = (ctx: ExtensionContext): string => {
    const sessionId = ctx.sessionManager.getSessionId?.();
    if (sessionId !== undefined) return `session:${sessionId}`;
    const manager = ctx.sessionManager as object;
    let key = anonymousSessionKeys.get(manager);
    if (key === undefined) {
      key = `anonymous:${nextAnonymousSessionKey++}`;
      anonymousSessionKeys.set(manager, key);
    }
    return key;
  };
  const transientBySession = new Map<string, SessionTransientState>();
  const transientFor = (ctx: ExtensionContext): SessionTransientState => {
    const sessionId = sessionIdFor(ctx);
    let transient = transientBySession.get(sessionId);
    if (transient === undefined) {
      transient = {
        approvalBook: new ToolApprovalBook(),
        pendingAcceptedSkipPlans: new Map<string, AcceptedSkipPlan>(),
        activeTurnId: undefined,
        activeClassification: undefined,
        activeClassificationObservedAt: undefined,
        activeAutomaticClassification: undefined,
        blockedDeliveryFingerprint: undefined,
        pendingEvidenceInvalidation: new Set<string>(),
      };
      transientBySession.set(sessionId, transient);
    }
    return transient;
  };
  const kitCacheKeyFor = (ctx: ExtensionContext): string | undefined => {
    const turnId = transientFor(ctx).activeTurnId;
    return turnId === undefined
      ? undefined
      : `${sessionIdFor(ctx)}:turn:${turnId}`;
  };

  const evidenceProcess: EvidenceProcess = {
    exec: async (command, args, options): Promise<EvidenceProcessResult> => {
      try {
        const result = await pi.exec(command, [...args], {
          cwd: options.cwd,
          timeout: options.timeout,
        });
        return {
          stdout: result.stdout,
          stderr: result.stderr,
          code: result.code,
          killed: false,
        };
      } catch {
        return { stdout: "", stderr: "", code: null, killed: true };
      }
    },
  };

  const gitRevisionObserver: RevisionObserver = async (projectRoot) => {
    const [head, status] = await Promise.all([
      pi
        .exec("git", ["rev-parse", "HEAD"], { cwd: projectRoot })
        .catch(() => undefined),
      pi
        .exec("git", ["status", "--porcelain"], { cwd: projectRoot })
        .catch(() => undefined),
    ]);
    const headCommit = head?.code === 0 ? head.stdout.trim() : "";
    return {
      commit: /^[0-9a-f]{40}$/i.test(headCommit)
        ? headCommit.toLowerCase()
        : null,
      worktreeDirty: status?.code !== 0 || status.stdout.trim().length > 0,
    };
  };

  /**
   * P1-04/P1-06 seam: validation evidence is observed through the embedded
   * Kit's promoted validator (SHA-pinned) plus current revision binding.
   * Returns undefined when the Kit cannot be integrity-verified; callers fail
   * closed.
   */
  const observeProjectValidationEvidence = async (
    ctx: ExtensionContext,
  ): Promise<ValidationEvidenceObservation | undefined> => {
    const embedded = await loadEmbeddedKit(kitCacheKeyFor(ctx)).catch(
      () => undefined,
    );
    const runtime = embedded?.validationEvidenceRuntime;
    if (runtime === undefined) return undefined;
    return observeValidationEvidence({
      projectRoot: ctx.cwd,
      validatorScript: runtime.scriptPath,
      validatorSha256: runtime.scriptSha256,
      process: evidenceProcess,
      observeRevision: gitRevisionObserver,
      observedAt: new Date().toISOString(),
    });
  };
  const handleCommand: RuntimeControllerHandlers["handleCommand"] = async (
    args,
    ctx,
  ) => {
    const parsed = parseSbtdCommand(args || "help");
    const transient = transientFor(ctx);
    if (parsed.kind === "unknown") {
      ctx.ui.notify(
        `Unknown /sbtd command. Try: ${parsed.suggestions.join(", ") || "help"}`,
        "warning",
      );
      return;
    }
    const command = parsed.spec.path.join(" ");
    if (command === "help") {
      ctx.ui.notify(
        renderSbtdHelp(undefined, parsed.args.join(" ") || undefined),
        "info",
      );
      return;
    }
    if (command === "off") {
      const state = createStateService({
        replay: () => ctx.sessionManager.getBranch(),
        append: pi.appendEntry.bind(pi),
      });
      const result = state.off();
      ctx.ui.notify(
        `SBTD is ${result.effectiveControlState}; policy and onboard choices were preserved.`,
        "info",
      );
      return;
    }
    const agentDirectory =
      process.env.PI_CODING_AGENT_DIR || `${homedir()}/.omp/agent`;
    const embedded = await loadEmbeddedKit(kitCacheKeyFor(ctx)).catch(() => {
      ctx.ui.notify(
        "Embedded SBTD Kit integrity verification failed. Reinstall @kunolu/omp-sbtd, then run /sbtd doctor.",
        "warning",
      );
      return undefined;
    });
    if (!embedded) return;
    const files = createNodeFileAdapter();
    // Status/Doctor observe composite bootstrap facts through this read-only
    // view; the bootstrap command remains the only persistence path.
    const readOnlyFiles: FileAdapter = {
      readText: (path) => files.readText(path),
      writeAtomic: () =>
        Promise.reject(
          new Error(
            "Read-only command attempted to write through FileAdapter.",
          ),
        ),
      makeDirectory: () =>
        Promise.reject(
          new Error("Read-only command attempted to create a directory."),
        ),
      exists: (path) => files.exists(path),
      remove: () =>
        Promise.reject(
          new Error(
            "Read-only command attempted to remove through FileAdapter.",
          ),
        ),
      isSymlink: (path) => files.isSymlink(path),
    };
    const onboard = createOnboardService({
      projectRoot: ctx.cwd,
      scope: command === "onboard init-projects" ? "projects" : "all",
      agentDirectory,
      kit: embedded.kit,
      files,
      now: () => new Date().toISOString(),
    });
    const compositePromises = new Map<
      FileAdapter,
      Promise<CompositeOnboardService>
    >();
    const composite = (
      fileAdapter: FileAdapter = files,
    ): Promise<CompositeOnboardService> => {
      const cached = compositePromises.get(fileAdapter);
      if (cached !== undefined) return cached;
      const created = (async () => {
        const hostExec = pi.exec;
        const processAdapter = {
          exec: (
            executable: string,
            args: readonly string[],
            options: { readonly cwd: string; readonly timeout: number },
          ) =>
            hostExec === undefined
              ? Promise.resolve({
                  stdout: "",
                  stderr: "OMP host process execution is unavailable.",
                  code: null,
                  killed: false,
                })
              : hostExec(executable, [...args], options),
        };
        const runtime = embedded.onboardRuntime
          ? await createCanonicalOnboardRuntime({
              runtimeRoot: embedded.onboardRuntime.root,
              runtimeScriptSha256: embedded.onboardRuntime.scriptSha256,
              process: processAdapter,
            }).catch(() => undefined)
          : undefined;
        return createCompositeOnboardService({
          agents: onboard,
          scope: command === "onboard init-projects" ? "projects" : "all",
          projectRoot: ctx.cwd,
          agentDirectory,
          globalSkillsDirectory: resolveGlobalSkillsDirectory(agentDirectory),
          kitBundledSkillsRoot: resolve(
            embedded.onboardRuntime?.root ??
              resolve(pluginPackageRoot(), "kit/onboard/runtime"),
            "templates/skills",
          ),
          mcpConfigPath: resolve(agentDirectory, "mcp.json"),
          identity: {
            sourceId: embedded.provenance.sourceId,
            sourceRevision: embedded.provenance.resolvedRevision,
            transformVersion: embedded.provenance.transformVersion,
            kitRevision: embedded.provenance.generatedSha256,
            projectionSha256: embedded.provenance.projectionSha256,
            pluginVersion: await getPluginVersion(),
            stableSet: embedded.provenance.retainedProvenance.stableSet,
            canonicalRuntimeSha256:
              embedded.onboardRuntime?.scriptSha256 ?? null,
          },
          onboardProfileId: currentState.onboardProfileId,
          route: effectiveRouteForObservation(currentState),
          runtime,
          process: processAdapter,
          files: fileAdapter,
          now: () => new Date().toISOString(),
          handoff:
            typeof pi.sendUserMessage === "function"
              ? {
                  async schedule(prompt: string) {
                    pi.sendUserMessage(prompt);
                  },
                }
              : undefined,
          listDir: async (path: string) => readdir(path),
        });
      })();
      compositePromises.set(fileAdapter, created);
      return created;
    };
    const observeCompositeBootstrap = async (): Promise<string[]> => {
      try {
        const records = await (
          await composite(readOnlyFiles)
        ).observeBootstrap();
        return records.map(
          (record) =>
            `Composite Bootstrap ${record.operationId}: state=${record.state} task=${record.taskState} project=${record.projectRoot} plan=${record.planDigest}` +
            (record.state === "ready"
              ? ""
              : ` recovery=/sbtd onboard bootstrap ${record.planDigest}`),
        );
      } catch {
        return ["Composite Bootstrap: observation unavailable"];
      }
    };
    const state = createStateService({
      replay: () => ctx.sessionManager.getBranch(),
      append: pi.appendEntry.bind(pi),
    });
    const currentState = state.restore();
    const acceptedSkips = createAcceptedSkipService({
      files,
      agentDirectory,
      now: () => new Date().toISOString(),
    });
    if (command === "report") {
      const observedAt = new Date().toISOString();
      let reportState = currentState;
      let toolEvidence: readonly ToolEvidenceRecord[] = [];
      try {
        const observed = await observeOnboardEnvironment(
          onboard,
          files,
          ctx.cwd,
          agentDirectory,
          embedded,
          currentState.onboardProfileId,
          effectiveRouteForObservation(currentState),
          observedAt,
          false,
        );
        reportState = {
          ...currentState,
          environmentObservation: observed.observation,
        };
        toolEvidence = observed.toolEvidence;
      } catch {
        // A report remains read-only and renders the last validated Session state.
      }
      const activeAutomaticClassification =
        transientFor(ctx).activeAutomaticClassification;
      const report = buildSbtdReport({
        state: reportState,
        effectiveControlState: deriveEffectiveControlState(
          reportState.runtimeMode,
          reportState.environmentObservation.mode,
        ),
        ...(reportState.route !== "auto" ||
        activeAutomaticClassification === undefined
          ? {}
          : {
              automaticRoute: activeAutomaticClassification.route,
            }),
        toolEvidence,
        provider: observeProviderSnapshot(ctx.models, observedAt),
      });
      const rendered = renderSbtdReport(report);
      ctx.ui.notify(
        [rendered.markdown.trimEnd(), "```json", rendered.json, "```"].join(
          "\n\n",
        ),
        "info",
      );
      return;
    }
    if (command === "route" && parsed.args.length === 0) {
      ctx.ui.notify(
        [
          `Route: ${currentState.route}`,
          `Automatic Route: ${currentState.classification?.route ?? "not-classified"}`,
          `Classification Reasons: ${currentState.classification?.reasons.join(", ") || "none"}`,
        ].join("\n"),
        "info",
      );
      return;
    }
    if (
      (command === "route" && parsed.args.length !== 1) ||
      ((command === "strict" || command === "relaxed") &&
        parsed.args.length !== 0)
    ) {
      ctx.ui.notify(`Usage: ${parsed.spec.usage}`, "warning");
      return;
    }
    if (
      command === "route" &&
      !["degraded", "managed"].includes(
        currentState.environmentObservation.mode,
      )
    ) {
      ctx.ui.notify(
        `${parsed.spec.usage} is unavailable until Environment Mode is managed or degraded. ${currentState.environmentObservation.repairPath}`,
        "warning",
      );
      return;
    }
    if (
      !parsed.spec.availableIn.includes(
        currentState.environmentObservation.mode,
      )
    ) {
      ctx.ui.notify(
        `${parsed.spec.usage} is unavailable until Environment Mode is managed or degraded. ${currentState.environmentObservation.repairPath}`,
        "warning",
      );
      return;
    }
    const effectiveControlState = deriveEffectiveControlState(
      currentState.runtimeMode,
      currentState.environmentObservation.mode,
    );
    const preflightRecoveryCommands = new Set([
      "status",
      "doctor",
      "report",
      "onboard status",
      "onboard plan",
      "onboard skip list",
      "onboard skip plan create",
      "onboard skip plan revoke",
      "onboard skip plan expire",
      "onboard skip apply",
    ]);
    if (
      effectiveControlState === "preflight-only" &&
      !preflightRecoveryCommands.has(command)
    ) {
      ctx.ui.notify(
        `${parsed.spec.usage} is unavailable while SBTD is preflight-only. Run /sbtd onboard plan, complete Onboard outside this enforced Session, then start a new Session.`,
        "warning",
      );
      return;
    }
    if (command === "onboard bootstrap") {
      const planDigest = parsed.args[0];
      if (parsed.args.length !== 1 || planDigest === undefined) {
        ctx.ui.notify(`Usage: ${parsed.spec.usage}`, "warning");
        return;
      }
      const service = await composite();
      const current = await service.requestBootstrap(planDigest, false);
      if (
        current.kind === "unavailable" ||
        current.kind === "not-required" ||
        current.kind === "ready"
      ) {
        ctx.ui.notify(
          current.message,
          current.kind === "ready" ? "info" : "warning",
        );
        return;
      }
      const approved = await ctx.ui.confirm(
        "Schedule Trellis Bootstrap Handoff",
        `Schedule a Provider-using OMP Agent turn for the Trellis bootstrap task bound to plan ${planDigest}? This uses the configured Provider and model.`,
      );
      const result = await service.requestBootstrap(planDigest, approved);
      ctx.ui.notify(
        result.message,
        result.kind === "scheduled" || result.kind === "ready"
          ? "info"
          : "warning",
      );
      return;
    }
    if (
      command === "onboard skip list" ||
      command === "onboard skip plan create" ||
      command === "onboard skip plan revoke" ||
      command === "onboard skip plan expire" ||
      command === "onboard skip apply"
    ) {
      if (command === "onboard skip list") {
        if (parsed.args.length !== 0) {
          ctx.ui.notify(`Usage: ${parsed.spec.usage}`, "warning");
          return;
        }
        const listed = await acceptedSkips.list();
        ctx.ui.notify(
          JSON.stringify(
            listed.kind === "ok"
              ? {
                  revision: listed.revision,
                  digest: listed.digest,
                  records: listed.records.map((record) => ({
                    ...record,
                    effectiveStatus:
                      record.status === "active" &&
                      Date.parse(record.expiresAt) <= Date.now()
                        ? "expired"
                        : record.status,
                  })),
                }
              : listed,
            null,
            2,
          ),
          listed.kind === "ok" ? "info" : "warning",
        );
        return;
      }
      if (command === "onboard skip apply") {
        const planDigest = parsed.args[0];
        if (planDigest === undefined || parsed.args.length !== 1) {
          ctx.ui.notify(`Usage: ${parsed.spec.usage}`, "warning");
          return;
        }
        const plan = transient.pendingAcceptedSkipPlans.get(planDigest);
        if (plan === undefined) {
          ctx.ui.notify(
            "AcceptedSkip Plan is stale or was not displayed in this Session. Create a new Plan.",
            "warning",
          );
          return;
        }
        const currentProfile = resolveProfile(
          embedded.profiles,
          currentState.onboardProfileId,
        );
        const currentRoute = effectiveRouteForObservation(currentState);
        const currentRouteRequirements = [
          ...routeRequiredCapabilities(currentRoute),
        ].sort();
        if (
          plan.context.route !== currentRoute ||
          plan.context.onboardProfileId !== currentProfile.id ||
          plan.context.kitMajor !== acceptedSkipKitMajor(embedded) ||
          plan.context.provenance.sourceId !== embedded.provenance.sourceId ||
          plan.context.provenance.kitRevision !==
            embedded.provenance.generatedSha256 ||
          plan.context.provenance.transformVersion !==
            embedded.provenance.transformVersion ||
          (plan.context.scope === "project" &&
            plan.context.projectRootKey !== projectRootKey(ctx.cwd)) ||
          (plan.context.scope === "global" &&
            plan.context.projectRootKey !== undefined) ||
          JSON.stringify(plan.context.requiredCapabilities) !==
            JSON.stringify([...currentProfile.required].sort()) ||
          JSON.stringify(plan.context.optionalCapabilities) !==
            JSON.stringify([...currentProfile.optional].sort()) ||
          JSON.stringify(plan.context.routeRequiredCapabilities) !==
            JSON.stringify(currentRouteRequirements)
        ) {
          ctx.ui.notify(
            "AcceptedSkip Plan is stale because its bound scope, Profile, Route, capability, or Kit facts changed. Create a new Plan.",
            "warning",
          );
          return;
        }
        const confirmed = await ctx.ui.confirm(
          "Apply AcceptedSkip Plan",
          `Apply ${plan.action} AcceptedSkip Plan ${plan.digest}?`,
        );
        if (!confirmed) {
          ctx.ui.notify("AcceptedSkip Apply was cancelled.", "info");
          return;
        }
        const result = await acceptedSkips.apply(plan);
        if (result.kind !== "applied") {
          ctx.ui.notify(result.message, "warning");
          return;
        }
        try {
          const refreshed = state.restore();
          const observed = await observeOnboardEnvironment(
            onboard,
            files,
            ctx.cwd,
            agentDirectory,
            embedded,
            refreshed.onboardProfileId,
            effectiveRouteForObservation(refreshed),
            new Date().toISOString(),
            false,
          );
          state.refresh(() => observed.observation);
          ctx.ui.notify(
            `AcceptedSkip ${result.record.recordId} is ${result.record.status}; Environment Mode is ${observed.observation.mode}.`,
            "info",
          );
        } catch {
          ctx.ui.notify(
            `AcceptedSkip ${result.record.recordId} was applied. Run /sbtd doctor to re-observe the environment.`,
            "warning",
          );
        }
        return;
      }
      const profile = resolveProfile(
        embedded.profiles,
        currentState.onboardProfileId,
      );
      const route = effectiveRouteForObservation(currentState);
      const routeRequirements = routeRequiredCapabilities(route);
      const provenance = {
        sourceId: embedded.provenance.sourceId,
        kitRevision: embedded.provenance.generatedSha256,
        transformVersion: embedded.provenance.transformVersion,
      };
      if (command === "onboard skip plan create") {
        const capability = parsed.args[0];
        const options = parseSkipPlanOptions(parsed.args.slice(1), [
          "scope",
          "expires",
          "reason",
        ]);
        const scope = options?.scope;
        if (
          capability === undefined ||
          options === undefined ||
          (scope !== "global" && scope !== "project")
        ) {
          ctx.ui.notify(`Usage: ${parsed.spec.usage}`, "warning");
          return;
        }
        const result = await acceptedSkips.planCreate(
          {
            scope,
            ...(scope === "project"
              ? { projectRootKey: projectRootKey(ctx.cwd) }
              : {}),
            onboardProfileId: profile.id,
            kitMajor: acceptedSkipKitMajor(embedded),
            route,
            profile,
            routeRequiredCapabilities: routeRequirements,
            provenance,
          },
          {
            capability,
            reason: options.reason as string,
            expiresAt: options.expires as string,
          },
        );
        if (result.kind !== "planned") {
          ctx.ui.notify(result.message, "warning");
          return;
        }
        transient.pendingAcceptedSkipPlans.set(result.plan.digest, result.plan);
        ctx.ui.notify(
          JSON.stringify(
            {
              ...result.plan,
              confirmation: "required for Apply",
            },
            null,
            2,
          ),
          "info",
        );
        return;
      }
      const recordId = parsed.args[0];
      const options = parseSkipPlanOptions(parsed.args.slice(1), ["reason"]);
      if (recordId === undefined || options === undefined) {
        ctx.ui.notify(`Usage: ${parsed.spec.usage}`, "warning");
        return;
      }
      const listed = await acceptedSkips.list();
      const targetScope =
        listed.kind === "ok"
          ? listed.effectiveRecords.find(
              (record) => record.recordId === recordId,
            )?.scope
          : undefined;
      const scope = targetScope ?? "project";
      const skipContext: AcceptedSkipContext = {
        scope,
        ...(scope === "project"
          ? { projectRootKey: projectRootKey(ctx.cwd) }
          : {}),
        onboardProfileId: profile.id,
        kitMajor: acceptedSkipKitMajor(embedded),
        route,
        profile,
        routeRequiredCapabilities: routeRequirements,
        provenance,
      };
      const result =
        command === "onboard skip plan expire"
          ? await acceptedSkips.planExpire(skipContext, {
              recordId,
              reason: options.reason as string,
            })
          : await acceptedSkips.planRevoke(skipContext, {
              recordId,
              reason: options.reason as string,
            });
      if (result.kind !== "planned") {
        ctx.ui.notify(result.message, "warning");
        return;
      }
      transient.pendingAcceptedSkipPlans.set(result.plan.digest, result.plan);
      ctx.ui.notify(
        JSON.stringify(
          { ...result.plan, confirmation: "required for Apply" },
          null,
          2,
        ),
        "info",
      );
      return;
    }
    if (command === "gate start" || command === "gate record") {
      const [gateId, reviewerStatus] = parsed.args;
      if (
        gateId === undefined ||
        !isBookGateId(gateId) ||
        (command === "gate record" &&
          (reviewerStatus === undefined ||
            !isReviewerStatus(reviewerStatus))) ||
        parsed.args.length !== (command === "gate start" ? 1 : 2)
      ) {
        ctx.ui.notify(
          command === "gate start"
            ? `Usage: /sbtd gate start <gate-id>; gate-id: ${bookGateIds.join(", ")}`
            : `Usage: /sbtd gate record <gate-id> <reviewer-status>; reviewer-status: ${reviewerStatuses.join(", ")}`,
          "warning",
        );
        return;
      }
      if (
        command === "gate record" &&
        !(await ctx.ui.confirm(
          "Record SBTD Book Gate outcome",
          `Record ${gateId} as ${reviewerStatus}? This changes the persisted workflow barrier.`,
        ))
      )
        return;
      if (
        command === "gate record" &&
        gateId === "release-readiness" &&
        reviewerStatus === "ready"
      ) {
        // P1-06: `ready` is never a caller-supplied boolean. It is derived from
        // a fresh, current evidence observation: execution verified, revision
        // current, exact clean binding, and (when the task classification
        // requires BDD) a v2 traceable envelope.
        const observation = await observeProjectValidationEvidence(ctx);
        const restored = state.restore();
        const requiresV2 =
          restored.classification?.userVisibleBehavior === true;
        const verified =
          observation?.executionVerified === true &&
          observation.revisionCurrent &&
          observation.exactRevision &&
          (!requiresV2 || observation.version === 2);
        if (!verified || observation?.descriptor === undefined) {
          ctx.ui.notify(
            `release-readiness cannot be recorded as ready: ${observation?.code ?? "VALIDATOR_UNAVAILABLE"} — ${observation?.message ?? "embedded Kit validator unavailable"}. Provide exact-revision, current evidence verified by the promoted validator; v1 envelopes never satisfy BDD traceability.`,
            "warning",
          );
          return;
        }
        try {
          state.recordValidationEvidence(observation.descriptor);
        } catch (error) {
          ctx.ui.notify(
            error instanceof Error
              ? error.message
              : "Validation evidence descriptor could not be persisted",
            "warning",
          );
          return;
        }
      }
      try {
        const next =
          command === "gate start"
            ? state.startBookGate(gateId)
            : state.recordBookGateReview(
                gateId,
                reviewerStatus as ReviewerStatus,
              );
        ctx.ui.notify(
          JSON.stringify(
            next.bookGates?.find((gate) => gate.id === gateId),
            null,
            2,
          ),
          "info",
        );
      } catch (error) {
        ctx.ui.notify(
          error instanceof Error
            ? error.message
            : "Book Gate transition failed",
          "warning",
        );
      }
      return;
    }
    if (command === "route" || command === "strict" || command === "relaxed") {
      const current = state.restore();
      const candidateRoute =
        command === "route" ? parsed.args[0] : current.route;
      if (
        candidateRoute === undefined ||
        (candidateRoute !== "auto" && !isWorkflowRouteId(candidateRoute))
      ) {
        ctx.ui.notify(
          `Unknown Route. Use auto or: ${workflowRouteIds.join(", ")}`,
          "warning",
        );
        return;
      }
      const currentTaskClassification =
        command !== "route"
          ? undefined
          : candidateRoute === "auto"
            ? transient.activeAutomaticClassification
            : current.classification === undefined
              ? undefined
              : { ...current.classification, route: candidateRoute };
      if (
        command === "route" &&
        candidateRoute === "auto" &&
        currentTaskClassification === undefined
      ) {
        ctx.ui.notify(
          "Automatic Route recovery needs current task facts. Start the current Agent turn, then retry /sbtd route auto.",
          "warning",
        );
        return;
      }
      const workflow =
        currentTaskClassification === undefined
          ? undefined
          : {
              classification: currentTaskClassification,
              bookGates: createBookGatePlan(currentTaskClassification),
            };
      const effectiveRoute =
        currentTaskClassification?.route ??
        (command === "route"
          ? candidateRoute
          : effectiveRouteForObservation(current));
      try {
        const observed = await observeOnboardEnvironment(
          onboard,
          files,
          ctx.cwd,
          agentDirectory,
          embedded,
          current.onboardProfileId,
          effectiveRoute,
          new Date().toISOString(),
          true,
        );
        const result =
          command === "route"
            ? state.setRoute(
                candidateRoute,
                () => observed.observation,
                workflow,
              )
            : state.setPolicyProfile(
                command === "strict" ? "strict" : "relaxed",
                () => observed.observation,
              );
        if (command === "route" && currentTaskClassification !== undefined) {
          transient.activeClassification = currentTaskClassification;
          if (candidateRoute === "auto")
            transient.activeAutomaticClassification = currentTaskClassification;
        }
        ctx.ui.notify(
          [
            `Route: ${result.state.route}`,
            `Policy Profile: ${result.state.policyProfile}`,
            `Effective Control State: ${result.effectiveControlState}`,
            `Reason: ${result.state.route === "auto" ? "automatic route selection restored" : "user route override"}`,
          ].join("\n"),
          "info",
        );
      } catch {
        ctx.ui.notify(
          "Route or policy transition could not determine the environment. Run /sbtd doctor, repair the reported issue, then retry.",
          "warning",
        );
      }
      return;
    }
    if (command === "status" || command === "doctor" || command === "on") {
      const current = state.restore();
      let observed: ObservedOnboardEnvironment;
      try {
        observed = await observeOnboardEnvironment(
          onboard,
          files,
          ctx.cwd,
          agentDirectory,
          embedded,
          current.onboardProfileId,
          effectiveRouteForObservation(current),
          new Date().toISOString(),
          false,
        );
      } catch {
        const failedState = {
          ...current,
          environmentObservation: {
            observedAt: new Date().toISOString(),
            mode: "blocked" as const,
            evidence: ["environment observation failed"],
            repairPath: "/sbtd doctor",
          },
        };
        if (command === "on") {
          ctx.ui.notify(
            "SBTD preflight could not determine the environment. Run /sbtd doctor to inspect and repair it.",
            "warning",
          );
          return;
        }
        if (command === "doctor") {
          const recovery = await onboard.inspectRecovery();
          const bootstrapLines = await observeCompositeBootstrap();
          const bootstrapSuffix =
            bootstrapLines.length > 0 ? `\n${bootstrapLines.join("\n")}` : "";
          const agentPluginBlock = await observeAgentPluginDoctorBlock({
            files,
            globalSkillsDirectory: resolveGlobalSkillsDirectory(agentDirectory),
            kitBundledSkillsRoot: resolve(
              embedded.onboardRuntime?.root ??
                resolve(pluginPackageRoot(), "kit/onboard/runtime"),
              "templates/skills",
            ),
            expectedVersion: await getPluginVersion(),
            ompRuntimeExtension: "loaded",
          });
          ctx.ui.notify(
            `${renderStatus(failedState, undefined, embedded)}\n${agentPluginBlock}\n${JSON.stringify(recovery, null, 2)}${bootstrapSuffix}`,
            "warning",
          );
          return;
        }
        ctx.ui.notify(renderStatus(failedState), "warning");
        return;
      }
      const result =
        command === "on"
          ? state.on(() => observed.observation)
          : {
              state: {
                ...current,
                environmentObservation: observed.observation,
              },
              effectiveControlState: deriveEffectiveControlState(
                current.runtimeMode,
                observed.observation.mode,
              ),
            };
      if (command === "status") {
        const bootstrapLines = await observeCompositeBootstrap();
        ctx.ui.notify(
          [
            renderStatus(
              result.state,
              observed.context,
              embedded,
              observed.toolEvidence,
              observed.acceptedSkips,
            ),
            ...bootstrapLines,
          ].join("\n"),
          "info",
        );
        return;
      }
      if (command === "doctor") {
        const recovery = await onboard.inspectRecovery();
        const bootstrapLines = await observeCompositeBootstrap();
        const bootstrapSuffix =
          bootstrapLines.length > 0 ? `\n${bootstrapLines.join("\n")}` : "";
        const agentPluginBlock = await observeAgentPluginDoctorBlock({
          files,
          globalSkillsDirectory: resolveGlobalSkillsDirectory(agentDirectory),
          kitBundledSkillsRoot: resolve(
            embedded.onboardRuntime?.root ??
              resolve(pluginPackageRoot(), "kit/onboard/runtime"),
            "templates/skills",
          ),
          expectedVersion: await getPluginVersion(),
          ompRuntimeExtension: "loaded",
        });
        ctx.ui.notify(
          `${renderStatus(result.state, observed.context, embedded, observed.toolEvidence, observed.acceptedSkips)}\n${agentPluginBlock}\n${JSON.stringify(recovery, null, 2)}${bootstrapSuffix}`,
          recovery.kind === "none" ? "info" : "warning",
        );
        return;
      }
      ctx.ui.notify(
        `SBTD is ${result.effectiveControlState}. ${observed.observation.repairPath}`,
        "info",
      );
      return;
    }
    if (command === "onboard reset") {
      const recovery = await onboard.inspectRecovery();
      if (recovery.kind === "repair-required") {
        const recoveryMessage =
          recovery.journalPath === undefined
            ? "Remove the retained target-set lock? No AGENTS content will be changed."
            : recovery.phase === "complete"
              ? "Finish cleanup for the completed Onboard transaction? No AGENTS content will be rolled back."
              : `Restore operation ${recovery.operationId} from ${recovery.backups.length} durable backups?`;
        const confirmed = await ctx.ui.confirm(
          "Recover SBTD Onboard Transaction",
          recoveryMessage,
        );
        const result = confirmed
          ? await onboard.recover()
          : {
              kind: "cancelled",
              message: "Onboard recovery was cancelled.",
              reloadRequired: false,
            };
        ctx.ui.notify(
          result.message,
          result.kind === "rolled-back" ? "info" : "warning",
        );
        return;
      }
      const resetPlan = await onboard.plan();
      const confirmed = await ctx.ui.confirm(
        "Apply SBTD Managed Blocks",
        `Apply the current Managed Block plan ${resetPlan.digest}?`,
      );
      const result = confirmed
        ? await onboard.apply(resetPlan, true)
        : {
            kind: "cancelled",
            message: "Managed Block Apply was cancelled.",
            reloadRequired: false,
          };
      ctx.ui.notify(
        result.message,
        result.kind === "applied" ? "info" : "warning",
      );
      if (result.kind === "applied") {
        try {
          const refreshed = state.restore();
          const observed = await observeOnboardEnvironment(
            onboard,
            files,
            ctx.cwd,
            agentDirectory,
            embedded,
            refreshed.onboardProfileId,
            effectiveRouteForObservation(refreshed),
            new Date().toISOString(),
            false,
          );
          state.refresh(() => observed.observation);
        } catch {
          // The Managed Block result remains truthful; Doctor shows recovery facts.
        }
      }
      return;
    }
    if (command === "onboard status") {
      const statusPlan = await onboard.plan();
      ctx.ui.notify(
        JSON.stringify(
          {
            sourceId: embedded.provenance.sourceId,
            canonicalRevision: embedded.provenance.resolvedRevision,
            canonicalManifestSha256:
              embedded.provenance.canonicalManifestSha256,
            projectionSha256: embedded.provenance.projectionSha256,
            kitRevision: statusPlan.kit.kitRevision,
            targets: statusPlan.targets,
            digest: statusPlan.digest,
            confirmation: "required for Apply",
          },
          null,
          2,
        ),
        "info",
      );
      return;
    }
    const onboardOptions = (() => {
      const mcpSelections: string[] = [];
      let digest: string | undefined;
      let trellisUsername: string | undefined;
      let error: string | undefined;
      const args = parsed.args;
      for (let index = 0; index < args.length; index += 1) {
        const arg = args[index] as string;
        if (arg === "--mcp") {
          const value = args[index + 1];
          if (value === undefined || value.startsWith("--")) {
            error = "Missing value for --mcp.";
            break;
          }
          mcpSelections.push(
            ...value
              .split(",")
              .map((entry) => entry.trim())
              .filter((entry) => entry.length > 0),
          );
          index += 1;
        } else if (arg === "--trellis-user") {
          const value = args[index + 1];
          if (value === undefined || value.startsWith("--")) {
            error = "Missing value for --trellis-user.";
            break;
          }
          trellisUsername = value;
          index += 1;
        } else if (!arg.startsWith("--") && digest === undefined) digest = arg;
        else {
          error = `Unknown argument: ${arg}`;
          break;
        }
      }
      return { digest, mcpSelections, trellisUsername, error };
    })();
    if (onboardOptions.error !== undefined) {
      ctx.ui.notify(
        `${onboardOptions.error} Usage: ${parsed.spec.usage}`,
        "warning",
      );
      return;
    }
    const service = await composite();
    let plan: CompositeOnboardPlan;
    try {
      plan = await service.plan({
        mcpSelections: onboardOptions.mcpSelections.map(
          (selection) => selection as never,
        ),
        trellisUsername: onboardOptions.trellisUsername,
      });
    } catch (error) {
      ctx.ui.notify(
        `Composite Onboard Plan failed: ${error instanceof Error ? error.message : "invalid inputs"}`,
        "warning",
      );
      return;
    }
    if (command === "onboard plan") {
      ctx.ui.notify(
        JSON.stringify(
          {
            schemaVersion: plan.schemaVersion,
            sourceId: embedded.provenance.sourceId,
            canonicalRevision: embedded.provenance.resolvedRevision,
            canonicalManifestSha256:
              embedded.provenance.canonicalManifestSha256,
            projectionSha256: embedded.provenance.projectionSha256,
            pluginVersion: plan.identity.pluginVersion,
            stableSet: plan.identity.stableSet,
            canonicalRuntimeSha256: plan.identity.canonicalRuntimeSha256,
            kitRevision: plan.identity.kitRevision,
            targets: (plan.agents as OnboardPlan).targets,
            skills: plan.skills,
            cliTools: plan.cliTools,
            mcpConfigPath: plan.mcpConfigPath,
            mcpEntries: plan.mcpEntries,
            trellisProjects: plan.trellisProjects,
            bootstrap: plan.bootstrap,
            approvalClasses: plan.approvalClasses,
            readSet: plan.readSet,
            expiresAt: plan.expiresAt,
            digest: plan.digest,
            confirmation: "required per approval class for Apply",
          },
          null,
          2,
        ),
        "info",
      );
      return;
    }
    if (
      onboardOptions.digest !== undefined &&
      onboardOptions.digest !== plan.digest
    ) {
      ctx.ui.notify(
        `Plan ${onboardOptions.digest} does not match the current read-set (${plan.digest}); no participant ran. Create a new plan.`,
        "warning",
      );
      return;
    }
    const approvals = emptyApprovalSet();
    if (plan.approvalClasses.includes("managed-files")) {
      const skillsEffect =
        plan.skills.action === "replace-from-embedded-stable"
          ? ` and replace retained Skills from the embedded stable set ${plan.skills.stableSet}`
          : "; global Skills are out of scope and are not inspected or modified";
      approvals["managed-files"] = await ctx.ui.confirm(
        "Apply SBTD Onboard Plan",
        `Apply plan ${plan.digest} to ${(plan.agents as OnboardPlan).targets.length} managed AGENTS targets${skillsEffect}?`,
      );
    }
    if (plan.approvalClasses.includes("shared-dependency-install")) {
      const installs = plan.cliTools
        .filter((tool) => tool.action === "install")
        .map((tool) => tool.packageId ?? tool.name)
        .join(", ");
      approvals["shared-dependency-install"] = await ctx.ui.confirm(
        "Install Shared CLI Dependencies",
        `Install missing global tools (${installs}) with exact allowlisted npm argv? Global package effects are recorded as shared-dependency residuals and are not silently uninstalled.`,
      );
    }
    if (plan.approvalClasses.includes("mcp-config")) {
      const selected = plan.mcpEntries
        .filter((entry) => entry.action === "merge")
        .map((entry) => entry.id)
        .join(", ");
      approvals["mcp-config"] = await ctx.ui.confirm(
        "Merge OMP MCP Configuration",
        `Merge selected user-level MCP entries (${selected}) into ${plan.mcpConfigPath}? Unknown existing entries are preserved; callability is reported only after Reload.`,
      );
    }
    if (plan.approvalClasses.includes("trellis-init")) {
      const projects = plan.trellisProjects.filter(
        (project) => project.action === "init",
      );
      approvals["trellis-init"] = await ctx.ui.confirm(
        "Initialize Trellis Projects",
        `Run trellis init -u ${projects[0]?.username ?? "<user>"} --omp --yes --skip-existing for ${projects.length} project(s) through the approved Onboard process action? Absolute project roots: ${projects.map((project) => project.projectRoot).join(", ")}.`,
      );
    }
    const result = await service.apply(plan, approvals);
    ctx.ui.notify(
      `${result.message}${result.reloadRequired && !result.message.includes("Reload") ? " Reload OMP or start a new Session." : ""}`,
      result.kind === "applied" ? "info" : "warning",
    );
    if (result.kind === "applied") {
      try {
        const refreshedState = state.restore();
        const observed = await observeOnboardEnvironment(
          onboard,
          files,
          ctx.cwd,
          agentDirectory,
          embedded,
          refreshedState.onboardProfileId,
          effectiveRouteForObservation(refreshedState),
          new Date().toISOString(),
          false,
        );
        state.refresh(() => observed.observation);
      } catch {
        // The Apply outcome remains truthful; Doctor supplies the recovery path.
      }
    }
  };
  const transitionStage: RuntimeControllerHandlers["transitionStage"] = async (
    stageId,
    ctx,
  ) => {
    const state = createStateService({
      replay: () => ctx.sessionManager.getBranch(),
      append: pi.appendEntry.bind(pi),
    });
    try {
      const current = state.restore();
      const effective = deriveEffectiveControlState(
        current.runtimeMode,
        current.environmentObservation.mode,
      );
      if (effective !== "active")
        return `Stage transition unavailable while SBTD is ${effective}. Run /sbtd doctor to inspect the current environment.`;
      const next = state.requestStageTransition(stageId);
      return `Stage ${next.stage?.id} is running after all required Book Gates passed.`;
    } catch (error) {
      return `Stage transition blocked: ${error instanceof Error ? error.message : "Book Gate validation failed"}`;
    }
  };
  const reobserve: RuntimeControllerHandlers["reobserve"] = async (
    _event,
    ctx,
  ) => {
    transientFor(ctx).pendingAcceptedSkipPlans.clear();
    const state = createStateService({
      replay: () => ctx.sessionManager.getBranch(),
      append: pi.appendEntry.bind(pi),
    });
    try {
      const embedded = await loadEmbeddedKit(kitCacheKeyFor(ctx));
      const agentDirectory =
        process.env.PI_CODING_AGENT_DIR || `${homedir()}/.omp/agent`;
      const files = createNodeFileAdapter();
      const onboard = createOnboardService({
        projectRoot: ctx.cwd,
        agentDirectory,
        kit: embedded.kit,
        files,
        now: () => new Date().toISOString(),
      });
      const current = state.restore();
      const observedAt = new Date().toISOString();
      const observed = await observeOnboardEnvironment(
        onboard,
        files,
        ctx.cwd,
        agentDirectory,
        embedded,
        current.onboardProfileId,
        effectiveRouteForObservation(current),
        observedAt,
        true,
      );
      state.refresh(() => observed.observation);
      state.recordProviderObservation(
        observeProviderSnapshot(ctx.models, observedAt),
      );
    } catch {
      state.refresh(() => ({
        observedAt: new Date().toISOString(),
        mode: "blocked",
        evidence: ["environment observation failed"],
        repairPath: "/sbtd doctor",
      }));
      ctx.ui.notify(
        "SBTD environment observation failed. Run /sbtd doctor to inspect and repair it.",
        "warning",
      );
    }
  };
  const preserveCompaction: RuntimeControllerHandlers["preserveCompaction"] =
    async (_event, ctx) => {
      try {
        const state = createStateService({
          replay: () => ctx.sessionManager.getBranch(),
          append: pi.appendEntry.bind(pi),
        }).restore();
        return { preserveData: { [SBTD_STATE_COMPACTION_KEY]: state } };
      } catch {
        return undefined;
      }
    };

  const beforeAgentStart: RuntimeControllerHandlers["beforeAgentStart"] =
    async (event, ctx) => {
      try {
        const service = createStateService({
          replay: () => ctx.sessionManager.getBranch(),
          append: pi.appendEntry.bind(pi),
        });
        let state = service.restore();
        state = service.recordProviderObservation(
          observeProviderSnapshot(ctx.models, new Date().toISOString()),
        );
        const effective = deriveEffectiveControlState(
          state.runtimeMode,
          state.environmentObservation.mode,
        );
        const inferred =
          effective === "active"
            ? classifyTaskPrompt(
                event.prompt,
                await observeObjectiveTaskEvidence(pi, ctx.cwd),
              )
            : undefined;
        const classification =
          inferred === undefined
            ? undefined
            : state.route === "auto"
              ? inferred
              : { ...inferred, route: state.route };
        if (classification !== undefined)
          state = service.recordWorkflow(
            classification,
            createBookGatePlan(classification),
          );
        const transient = transientFor(ctx);
        transient.activeClassification = classification;
        transient.activeClassificationObservedAt =
          classification === undefined ? undefined : Date.now();
        transient.activeAutomaticClassification = inferred;
        const embedded = await loadEmbeddedKit(kitCacheKeyFor(ctx));
        return {
          systemPrompt: [
            ...(event.systemPrompt ?? []),
            renderRuntimeMarker(state, embedded.kit.kitRevision),
          ],
        };
      } catch {
        return {
          systemPrompt: [
            ...(event.systemPrompt ?? []),
            '<sbtd-runtime state-version="1" kit-revision="unavailable" effective-control-state="blocked" repair="/sbtd doctor" />',
          ],
        };
      }
    };

  const beforeToolCall: RuntimeControllerHandlers["beforeToolCall"] = async (
    event,
    ctx,
  ) => {
    try {
      const service = createStateService({
        replay: () => ctx.sessionManager.getBranch(),
        append: pi.appendEntry.bind(pi),
      });
      const state = service.restore();
      const effective = deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      );
      if (
        (effective === "preflight-only" || effective === "blocked") &&
        isMutationOrPhaseAdvancingTool(event)
      )
        return {
          block: true,
          reason: `SBTD is ${effective}. Run /sbtd doctor to inspect the current environment and use only recovery actions until it is managed.`,
        };
      const toolCommand = commandFromToolEvent(event);
      const gatesPassed =
        effective === "active" &&
        transientFor(ctx).activeClassification !== undefined &&
        isMutationOrPhaseAdvancingTool(event) &&
        !isPlanningArtifactTool(event, ctx.cwd)
          ? requiredBookGatesPassedForCurrentStage(state)
          : undefined;
      const risk = observeToolRisk(event, transientFor(ctx).approvalBook);
      const decision = evaluateRuleRegistry(ruleRegistry, {
        action: "tool",
        ...(toolCommand === undefined ? {} : { toolCommand }),
        ...(gatesPassed === undefined
          ? {}
          : { requiredBookGatesPassed: gatesPassed }),
        ...(risk.installingDependency ? { installingDependency: true } : {}),
        ...(risk.secretRead ? { secretRead: true } : {}),
        ...(risk.installApproved ? { installApproved: true } : {}),
        ...(risk.secretReadApproved ? { secretReadApproved: true } : {}),
        policyProfile: state.policyProfile,
      });
      service.recordRuleDecision(decision, "tool", [
        "tool-call",
        ...(toolCommand === undefined ? [] : ["shell-command"]),
        ...(gatesPassed === false ? ["required-book-gates-pending"] : []),
        ...(risk.installingDependency ? ["dependency-install"] : []),
        ...(risk.secretRead ? ["secret-read-path"] : []),
        ...(risk.mixedSecretAccess ? ["mixed-secret-access"] : []),
        ...(risk.remote ? ["remote-locator"] : []),
        ...(risk.capability === "unknown" ? ["unknown-tool-capability"] : []),
        ...(risk.installApproved || risk.secretReadApproved
          ? ["explicit-tool-approval"]
          : []),
      ]);
      if (
        decision.decision === "block-tool" &&
        risk.riskClasses.length > 0 &&
        !risk.installApproved &&
        !risk.secretReadApproved
      )
        // Typed one-shot approval: the pending descriptor is recorded only for
        // a risky call that was actually blocked, binding the exact risk
        // classes and input fingerprint at this moment.
        transientFor(ctx).approvalBook.recordBlocked(
          event.toolCallId,
          risk.riskClasses,
          risk.fingerprint,
        );
      if (decision.decision === "allow") {
        const allowedId = z
          .object({ toolCallId: z.string().optional() })
          .safeParse(event).data?.toolCallId;
        if (allowedId !== undefined && isMutationOrPhaseAdvancingTool(event))
          transientFor(ctx).pendingEvidenceInvalidation.add(allowedId);
        return undefined;
      }
      return {
        block:
          decision.decision === "block-tool" ||
          decision.decision === "block-stage" ||
          decision.decision === "block-delivery",
        reason: `${decision.ruleId}: ${decision.reason}. ${decision.recovery}`,
      };
    } catch {
      return {
        block: true,
        reason:
          "KPi could not restore a valid SBTD state. Run /sbtd doctor before executing tools.",
      };
    }
  };

  const approvalResolved: RuntimeControllerHandlers["approvalResolved"] =
    async (event, ctx) => {
      // The host approval event carries only toolCallId/toolName/approved; the
      // exact input fingerprint was bound when the risky call was blocked.
      transientFor(ctx).approvalBook.resolve(event.toolCallId, event.approved);
    };

  const toolResult: RuntimeControllerHandlers["toolResult"] = async (
    event,
    ctx,
  ) => {
    const toolCallId = z
      .object({ toolCallId: z.string().optional() })
      .safeParse(event).data?.toolCallId;
    const transient = transientFor(ctx);
    if (
      toolCallId !== undefined &&
      transient.pendingEvidenceInvalidation.delete(toolCallId)
    ) {
      const service = createStateService({
        replay: () => ctx.sessionManager.getBranch(),
        append: pi.appendEntry.bind(pi),
      });
      service.invalidateValidationEvidence(toolCallId);
    }
    if (toolCallId !== undefined) transient.approvalBook.consume(toolCallId);
  };
  const credentialDisabled: RuntimeControllerHandlers["credentialDisabled"] =
    async (event, ctx) => {
      const service = createStateService({
        replay: () => ctx.sessionManager.getBranch(),
        append: pi.appendEntry.bind(pi),
      });
      service.recordProviderObservation(
        providerUnavailableSnapshot(event.provider, new Date().toISOString()),
      );
    };

  const turnStart: RuntimeControllerHandlers["turnStart"] = async (
    event,
    ctx,
  ) => {
    const transient = transientFor(ctx);
    transient.activeTurnId = String(event.turnIndex);
    transient.blockedDeliveryFingerprint = undefined;
    // Approvals bind session AND turn: nothing carries across a turn boundary.
    transient.approvalBook.clear();
  };

  const turnEnd: RuntimeControllerHandlers["turnEnd"] = async (event, ctx) => {
    const transient = transientFor(ctx);
    const kitCacheKey = kitCacheKeyFor(ctx);
    if (kitCacheKey !== undefined) releaseEmbeddedKit(kitCacheKey);
    if (transient.activeTurnId === String(event.turnIndex)) {
      transient.activeTurnId = undefined;
      transient.activeAutomaticClassification = undefined;
    }
  };

  const sessionStop: RuntimeControllerHandlers["sessionStop"] = async (
    event,
    ctx,
  ) => {
    const service = createStateService({
      replay: () => ctx.sessionManager.getBranch(),
      append: pi.appendEntry.bind(pi),
    });
    const state = service.restore();
    const effective = deriveEffectiveControlState(
      state.runtimeMode,
      state.environmentObservation.mode,
    );
    const transient = transientFor(ctx);
    if (effective !== "active") {
      transientBySession.delete(sessionIdFor(ctx));
      return undefined;
    }
    const classification = transient.activeClassification;
    const observedAfter = transient.activeClassificationObservedAt;
    const evidence =
      classification?.userVisibleBehavior === true
        ? await observeProjectValidationEvidence(ctx)
        : undefined;
    // P1-04: BDD delivery evidence is a version-aware observer decision. Only
    // a v2 envelope whose execution evidence verified AND whose revision binds
    // the current HEAD satisfies BDD; v1 generic envelopes never do, and file
    // mtimes play no role.
    const bddCovered =
      classification?.userVisibleBehavior === true &&
      evidence?.executionVerified === true &&
      evidence.revisionCurrent &&
      evidence.version === 2;
    if (evidence?.descriptor !== undefined)
      service.recordValidationEvidence(evidence.descriptor);
    const observedAt = new Date().toISOString();
    if (
      classification?.userVisibleBehavior === true &&
      evidence !== undefined &&
      evidence.found &&
      !bddCovered
    )
      service.recordValidationReport(
        validationReportForEvidenceObservation(evidence, observedAt),
      );
    const formalArtifact = routeRequiresFormalValidationReport(classification)
      ? await observeFormalValidationReport(
          ctx.cwd,
          observedAfter ?? Number.POSITIVE_INFINITY,
          observedAt,
        )
      : undefined;
    if (formalArtifact !== undefined)
      service.recordValidationReport(
        validationReportForFormalArtifact(formalArtifact),
      );
    const formalReportPresent =
      formalArtifact === undefined
        ? undefined
        : formalArtifact.status === "available";
    const releaseGate = state.bookGates?.find(
      (gate) => gate.id === "release-readiness",
    );
    const decision = evaluateRuleRegistry(ruleRegistry, {
      action: "delivery",
      ...(classification?.userVisibleBehavior === true
        ? { userVisibleBehavior: true, bddCovered }
        : {}),
      ...(formalReportPresent === undefined ? {} : { formalReportPresent }),
      ...(classification?.productionPathRisk === true
        ? {
            productionPathRisk: true,
            releaseGateReady: releaseGate?.gateState === "passed",
          }
        : {}),
      policyProfile: state.policyProfile,
    });
    service.recordRuleDecision(decision, "delivery", [
      "session-stop",
      ...(classification?.userVisibleBehavior
        ? [
            "user-visible-behavior",
            ...(bddCovered
              ? ["bdd-evidence-present"]
              : ["bdd-evidence-missing"]),
            ...(evidence === undefined
              ? ["evidence-observer-unavailable"]
              : [
                  evidence.specificationTraceable
                    ? "specification-traceable"
                    : "specification-not-traceable",
                  evidence.executionVerified && evidence.revisionCurrent
                    ? "execution-evidence-verified"
                    : "execution-evidence-unverified",
                ]),
          ]
        : []),
      ...(formalReportPresent === undefined
        ? []
        : formalReportPresent
          ? ["formal-report-present"]
          : ["formal-report-missing"]),
      ...(classification?.productionPathRisk
        ? ["production-path-risk", "release-gate-evaluated"]
        : []),
    ]);
    if (decision.decision === "allow") {
      transientBySession.delete(sessionIdFor(ctx));
      return undefined;
    }
    const fingerprint = decision.ruleId;
    if (
      transient.blockedDeliveryFingerprint === fingerprint &&
      event.stop_hook_active
    ) {
      service.blockStage(
        "delivery",
        `${decision.ruleId}: ${decision.reason}. ${decision.recovery}`,
      );
      transientBySession.delete(sessionIdFor(ctx));
      return undefined;
    }
    transient.blockedDeliveryFingerprint = fingerprint;
    return {
      decision: "block",
      reason: `${decision.ruleId}: ${decision.reason}. ${decision.recovery}`,
    };
  };
  registerRuntimeController(pi, {
    complete: (prefix) =>
      completeSbtdCommand(prefix).map((value) => ({ value, label: value })),
    handleCommand,
    transitionStage,
    reobserve,
    beforeAgentStart,
    beforeToolCall,
    preserveCompaction,
    approvalResolved,
    toolResult,
    credentialDisabled,
    turnStart,
    turnEnd,
    sessionStop,
  });
}
