import { z } from "zod";
import type { EnvironmentObservation } from "../state/index.js";

export const environmentFactsSchema = z
  .object({
    blockedReasons: z.array(z.string()).max(32),
    missingRequired: z.array(z.string()).max(32),
    missingOptional: z.array(z.string()).max(32),
    routeRequiredGaps: z.array(z.string()).max(32),
    acceptedOptionalSkips: z
      .array(
        z
          .object({
            capability: z.string().min(1),
            expiresAt: z.string().datetime(),
          })
          .strict(),
      )
      .max(32),
  })
  .strict();

export type EnvironmentFacts = z.infer<typeof environmentFactsSchema>;

export const profileEnvironmentInputSchema = z
  .object({
    profile: z
      .object({
        id: z.string().min(1),
        required: z.array(z.string().min(1)).max(64),
        optional: z.array(z.string().min(1)).max(64),
      })
      .strict(),
    capabilities: z.record(z.string(), z.boolean()),
    routeRequiredCapabilities: z.array(z.string().min(1)).max(64),
    acceptedOptionalSkips: environmentFactsSchema.shape.acceptedOptionalSkips,
  })
  .strict();

export type ProfileEnvironmentInput = z.infer<
  typeof profileEnvironmentInputSchema
>;

export function evaluateEnvironment(
  input: unknown,
  observedAt: string,
): EnvironmentObservation {
  const facts = environmentFactsSchema.parse(input);
  if (facts.blockedReasons.length > 0)
    return {
      observedAt,
      mode: "blocked",
      evidence: facts.blockedReasons,
      repairPath: "/sbtd doctor",
    };
  if (facts.routeRequiredGaps.length > 0)
    return {
      observedAt,
      mode: "blocked",
      evidence: facts.routeRequiredGaps,
      repairPath: "/sbtd doctor",
    };
  if (facts.missingRequired.length > 0) {
    return {
      observedAt,
      mode: "needs-onboard",
      evidence: facts.missingRequired,
      repairPath: "/sbtd onboard plan",
    };
  }
  const accepted = new Set(
    facts.acceptedOptionalSkips
      .filter((skip) => skip.expiresAt > observedAt)
      .map((skip) => skip.capability),
  );
  const uncoveredOptional = facts.missingOptional.filter(
    (capability) => !accepted.has(capability),
  );
  if (uncoveredOptional.length > 0)
    return {
      observedAt,
      mode: "needs-onboard",
      evidence: uncoveredOptional,
      repairPath: "/sbtd onboard plan",
    };
  if (facts.missingOptional.length > 0)
    return {
      observedAt,
      mode: "degraded",
      evidence: facts.missingOptional.map(
        (capability) => `accepted skip: ${capability}`,
      ),
      repairPath: "/sbtd doctor",
    };
  return {
    observedAt,
    mode: "managed",
    evidence: ["selected profile requirements are present"],
    repairPath: "/sbtd status",
  };
}

export function evaluateProfileEnvironment(
  input: unknown,
  observedAt: string,
): EnvironmentObservation {
  const profileInput = profileEnvironmentInputSchema.parse(input);
  const missingRequired = profileInput.profile.required.filter(
    (capability) => profileInput.capabilities[capability] !== true,
  );
  const missingOptional = profileInput.profile.optional.filter(
    (capability) => profileInput.capabilities[capability] !== true,
  );
  const routeRequiredGaps = profileInput.routeRequiredCapabilities.filter(
    (capability) => profileInput.capabilities[capability] !== true,
  );
  return evaluateEnvironment(
    {
      blockedReasons: [],
      missingRequired,
      missingOptional,
      routeRequiredGaps,
      acceptedOptionalSkips: profileInput.acceptedOptionalSkips,
    },
    observedAt,
  );
}
