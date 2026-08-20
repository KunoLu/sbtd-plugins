import { buildSbtdReport, renderSbtdReport } from "../../src/report/index.ts";
import type { SbtdSessionState } from "../../src/state/index.ts";
import {
  defaultSessionState,
  deriveEffectiveControlState,
} from "../../src/state/index.ts";
import {
  classifyTask,
  type WorkflowRouteId,
} from "../../src/workflow/index.ts";

const OBSERVED_AT = "2026-08-12T00:00:00.000Z";

function publicReportFor(
  state: SbtdSessionState,
  automaticRoute?: WorkflowRouteId,
): string {
  const rendered = renderSbtdReport(
    buildSbtdReport({
      state,
      effectiveControlState: deriveEffectiveControlState(
        state.runtimeMode,
        state.environmentObservation.mode,
      ),
      ...(automaticRoute === undefined ? {} : { automaticRoute }),
      toolEvidence: [],
    }),
  );
  return [rendered.markdown.trimEnd(), "```json", rendered.json, "```"].join(
    "\n\n",
  );
}

export function currentPublicSbtdReport(): string {
  return publicReportFor(defaultSessionState(OBSERVED_AT));
}

export function smallDirectRoutePublicSbtdReport(): string {
  const classification = classifyTask({
    userVisibleBehavior: false,
    existingProductionCode: false,
    existingBehaviorBug: false,
    dataRisk: false,
    productionPathRisk: false,
    crossRepoScope: false,
    domainAmbiguity: false,
    durableRequirements: false,
  });
  return publicReportFor(
    {
      ...defaultSessionState(OBSERVED_AT),
      classification,
    },
    classification.route,
  );
}

export function autoRoutePublicSbtdReport(): string {
  const classification = classifyTask({
    userVisibleBehavior: true,
    existingProductionCode: true,
    existingBehaviorBug: true,
    dataRisk: false,
    productionPathRisk: false,
    crossRepoScope: false,
    domainAmbiguity: false,
    durableRequirements: false,
  });
  return publicReportFor(
    {
      ...defaultSessionState(OBSERVED_AT),
      classification,
    },
    classification.route,
  );
}

export function legacyAsciiSbtdReport(): string {
  return [
    "# SBTD Status",
    "",
    "Route: auto",
    "Book Gates: none",
    "",
    "```json",
    JSON.stringify(
      {
        schemaVersion: 1,
        workflow: {
          route: "auto",
          effectiveControlState: "advisory",
        },
      },
      null,
      2,
    ),
    "```",
  ].join("\n");
}
