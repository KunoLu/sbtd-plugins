import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { constants } from "node:fs";
import { access, stat } from "node:fs/promises";
import { dirname, isAbsolute } from "node:path";
import { z } from "zod";
import {
  acceptanceArtifactSha256,
  assertJudgeScoreMatchesRubric,
  blindJudgeResultSha256,
  type CurrentRuntimeCompatibilityAdapter,
  type CurrentRuntimeCompatibilityResult,
  compatibilityCommandsSchema,
  currentRuntimeVersionSchema,
  type OmpProcessAdapter,
  runIdSchema,
  type SanitizedOmpEvent,
  valueStudyFixtureSchema,
} from "./release-validator.ts";
import { hasSensitiveFieldName, hasSensitiveText } from "./sanitization.ts";

const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_RESPONSE_BYTES = 128 * 1024;
const MAX_STDERR_BYTES = 16 * 1024;
const SHORT_COMMAND_TIMEOUT_MS = 15_000;
// The authorized harness bounds Runtime startup at 15s and each of the four
// sequential public commands at a 15s acknowledgment plus a 15s output wait.
// The host deadline covers that complete bounded sequence plus harness
// startup/install overhead while remaining a hard wall-clock bound.
const COMPATIBILITY_TIMEOUT_MS = 150_000;
const TERMINATION_GRACE_MS = 250;
const EXECUTION_CLEANUP_BUDGET_MS = 5_000;
const MAX_EXECUTION_WALL_CLOCK_MS = 600_000;
const REQUIRED_GATE_IDS = [
  "bdd",
  "tdd",
  "legacy-change-safety",
  "refactoring-pass",
  "ddia-data-design",
  "ddd-distilled-modeling",
  "release-readiness",
] as const;
const ROUTE_COSTS = ["light", "standard", "heavy"] as const;
const ATTEMPT_OUTCOMES = [
  "completed",
  "host-start",
  "transport-interruption",
  "runtime-crash",
  "model-quality",
  "task-test-failure",
  "workflow-blocked",
  "timeout",
  "turn-limit",
  "token-limit",
] as const;

const hashSchema = z.string().regex(/^[a-f0-9]{64}$/);
const absolutePathSchema = z
  .string()
  .min(1)
  .max(4096)
  .refine(isAbsolute, "expected an absolute path");
const boundedTextSchema = z.string().min(1).max(4096);
const blockerSchema = z
  .object({
    code: boundedTextSchema,
    reason: boundedTextSchema.optional(),
    recovery: boundedTextSchema,
  })
  .strict();
const commandResultsSchema = z
  .object({
    help: z.enum(["passed", "failed", "blocked"]),
    status: z.enum(["passed", "failed", "blocked"]),
    report: z.enum(["passed", "failed", "blocked"]),
    "onboard plan": z.enum(["passed", "failed", "blocked"]),
  })
  .strict();
const compatibilityResultSchema = z
  .object({
    currentRuntimeVersion: currentRuntimeVersionSchema,
    status: z.enum(["passed", "failed", "blocked"]),
    agentInvoked: z.literal(false),
    acceptanceMode: z.literal("profile-isolated").optional(),
    supportDecision: z.literal("requires-separate-support-review").optional(),
    filesystemBeforeSha256: hashSchema.optional(),
    filesystemAfterSha256: hashSchema.optional(),
    packageSha256: hashSchema.optional(),
    blocker: blockerSchema.optional(),
    commandResults: commandResultsSchema,
  })
  .strict();
const compatibilityRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    operation: z.literal("compatibility"),
    input: z
      .object({
        currentRuntimeVersion: currentRuntimeVersionSchema,
        pluginPackagePath: absolutePathSchema,
        pluginTarballPath: absolutePathSchema,
        sandboxRoot: absolutePathSchema,
        commands: compatibilityCommandsSchema,
      })
      .strict(),
  })
  .strict();
const compatibilityResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    operation: z.literal("compatibility"),
    result: compatibilityResultSchema,
  })
  .strict();

const preflightRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    operation: z.literal("preflight"),
    input: z
      .object({
        executionModelId: boundedTextSchema,
        judgeModelId: boundedTextSchema,
        runtimeVersion: boundedTextSchema,
      })
      .strict(),
  })
  .strict();
const preflightResponseSchema = z.union([
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("preflight"),
      result: z
        .object({
          status: z.literal("ready"),
          runtimeVersion: boundedTextSchema,
          executionModelId: boundedTextSchema,
          judgeModelId: boundedTextSchema,
          executionProcessId: boundedTextSchema,
          judgeProcessId: boundedTextSchema,
          supportsUsageEvents: z.literal(true),
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("preflight"),
      result: z
        .object({
          status: z.literal("blocked"),
          supportsUsageEvents: z.literal(false),
          blocker: blockerSchema,
        })
        .strict(),
    })
    .strict(),
]);

const runtimeModeRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    operation: z.literal("runtime-mode"),
    input: z
      .object({
        fixtureId: boundedTextSchema,
        mode: z.enum(["advisory", "enforced"]),
      })
      .strict(),
  })
  .strict();
const runtimeModeResponseSchema = z.union([
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("runtime-mode"),
      result: z.object({ status: z.literal("ready") }).strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("runtime-mode"),
      result: z
        .object({ status: z.literal("blocked"), blocker: blockerSchema })
        .strict(),
    })
    .strict(),
]);

const sanitizedEventSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("usage"),
      turns: z.number().int().min(0),
      tokens: z.number().int().min(0),
    })
    .strict(),
  z
    .object({
      kind: z.literal("report"),
      requiredGates: z.array(z.enum(REQUIRED_GATE_IDS)),
      // Absent for an explicitly unclassified route:auto observation; a named
      // effective route always carries its concrete cost.
      routeCost: z.enum(ROUTE_COSTS).optional(),
    })
    .strict(),
  z
    .object({
      kind: z.literal("terminal"),
      outcome: z.enum(ATTEMPT_OUTCOMES),
      finalResponse: z
        .string()
        .min(1)
        .max(32 * 1024)
        .optional(),
    })
    .strict(),
]);
const sanitizedEventsSchema = z
  .array(sanitizedEventSchema)
  .min(2)
  .refine((events) => {
    const usageCount = events.filter((event) => event.kind === "usage").length;
    const reportCount = events.filter(
      (event) => event.kind === "report",
    ).length;
    const terminalCount = events.filter(
      (event) => event.kind === "terminal",
    ).length;
    return (
      usageCount >= 1 &&
      reportCount === 1 &&
      terminalCount === 1 &&
      events[events.length - 1]?.kind === "terminal"
    );
  }, "expected bounded usage, one report, and a final terminal event in the execution response");
const acceptanceArtifactSchema = z
  .object({
    finalResponse: z
      .string()
      .min(1)
      .max(32 * 1024)
      .optional(),
    patch: z
      .string()
      .max(64 * 1024)
      .optional(),
    commandOutcomes: z
      .array(
        z
          .object({
            command: z.string().min(1).max(512),
            status: z.enum(["passed", "failed", "blocked"]),
          })
          .strict(),
      )
      .max(24),
  })
  .strict()
  .refine(
    (artifact) =>
      artifact.finalResponse !== undefined ||
      artifact.patch !== undefined ||
      artifact.commandOutcomes.length > 0,
    "expected a bounded acceptance artifact",
  );
const rubricCriterionSchema = z
  .object({
    id: z.string().min(1),
    description: z.string().min(1),
    weight: z.number().int().positive(),
    severe: z.boolean(),
  })
  .strict();
const judgeCriterionScoreSchema = z
  .object({
    id: z.string().min(1),
    score: z.number().min(0).max(100),
    reason: z.string().min(1).max(4_096),
  })
  .strict();
const judgeArmScoreSchema = z
  .object({
    total: z.number().min(0).max(100),
    severeAcceptanceFailure: z.boolean(),
    criteria: z.array(judgeCriterionScoreSchema).min(1),
  })
  .strict();
const executeRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    operation: z.literal("execute"),
    input: z
      .object({
        runId: runIdSchema,
        fixture: valueStudyFixtureSchema,
        fixtureSha256: hashSchema,
        arm: z.enum(["control", "treatment"]),
        mode: z.enum(["advisory", "enforced"]),
        attempt: z.number().int().positive().max(2),
        workspacePath: absolutePathSchema,
        limits: z
          .object({
            wallClockMs: z
              .number()
              .int()
              .positive()
              .max(MAX_EXECUTION_WALL_CLOCK_MS),
            maxTurns: z.number().int().positive(),
            maxTokens: z.number().int().positive(),
          })
          .strict(),
      })
      .strict(),
  })
  .strict();
const executeResponseSchema = z.union([
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("execute"),
      result: z
        .object({
          status: z.literal("completed"),
          runId: runIdSchema,
          fixtureId: boundedTextSchema,
          arm: z.enum(["control", "treatment"]),
          attempt: z.number().int().positive().max(2),
          fixtureSha256: hashSchema,
          executionProcessId: boundedTextSchema,
          events: sanitizedEventsSchema,
          acceptanceArtifact: acceptanceArtifactSchema,
          acceptanceArtifactSha256: hashSchema,
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("execute"),
      result: z
        .object({ status: z.literal("blocked"), blocker: blockerSchema })
        .strict(),
    })
    .strict(),
]);
const judgeRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    operation: z.literal("judge"),
    input: z
      .object({
        runId: runIdSchema,
        fixtureId: boundedTextSchema,
        fixtureSha256: hashSchema,
        rubric: z.array(rubricCriterionSchema).min(1),
        first: z
          .object({
            artifact: acceptanceArtifactSchema,
            artifactSha256: hashSchema,
          })
          .strict(),
        second: z
          .object({
            artifact: acceptanceArtifactSchema,
            artifactSha256: hashSchema,
          })
          .strict(),
      })
      .strict(),
  })
  .strict();
const judgeResponseSchema = z.union([
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("judge"),
      result: z
        .object({
          status: z.literal("completed"),
          runId: runIdSchema,
          fixtureId: boundedTextSchema,
          fixtureSha256: hashSchema,
          judgeProcessId: boundedTextSchema,
          firstArtifactSha256: hashSchema,
          secondArtifactSha256: hashSchema,
          first: judgeArmScoreSchema,
          second: judgeArmScoreSchema,
          judgeResultSha256: hashSchema,
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      operation: z.literal("judge"),
      result: z
        .object({ status: z.literal("blocked"), blocker: blockerSchema })
        .strict(),
    })
    .strict(),
]);

type HostBlocker = Readonly<{
  code: string;
  reason: string;
  recovery: string;
}>;
type HostExchange<T> =
  | Readonly<{ kind: "success"; value: T }>
  | Readonly<{ kind: "blocked"; blocker: HostBlocker }>;

function protocolBlocker(code: string, reason: string): HostBlocker {
  return {
    code,
    reason,
    recovery:
      "Correct the trusted OMP host command protocol and rerun the blocked P0 command.",
  };
}

function containsSensitiveData(value: unknown): boolean {
  if (typeof value === "string") return hasSensitiveText(value);
  if (Array.isArray(value)) return value.some(containsSensitiveData);
  if (value === null || typeof value !== "object") return false;
  return Object.entries(value as Record<string, unknown>).some(
    ([key, nested]) =>
      hasSensitiveFieldName(key) || containsSensitiveData(nested),
  );
}

function blockedCompatibilityResult(
  currentRuntimeVersion: CurrentRuntimeCompatibilityResult["currentRuntimeVersion"],
  blocker: HostBlocker,
): CurrentRuntimeCompatibilityResult {
  return {
    currentRuntimeVersion,
    status: "blocked",
    agentInvoked: false,
    blocker,
    commandResults: {
      help: "blocked",
      status: "blocked",
      report: "blocked",
      "onboard plan": "blocked",
    },
  };
}

async function runHostCommand(
  executable: string,
  environment: Readonly<Record<string, string>>,
  request: string,
  timeoutMs: number,
): Promise<HostExchange<string>> {
  const { promise, resolve } = Promise.withResolvers<HostExchange<string>>();
  let child: ChildProcessWithoutNullStreams;
  try {
    child = spawn(executable, [], {
      cwd: dirname(executable),
      env: environment,
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch {
    resolve({
      kind: "blocked",
      blocker: protocolBlocker(
        "OMP_HOST_COMMAND_FAILED",
        "The authorized OMP host command could not be started.",
      ),
    });
    return promise;
  }

  let settled = false;
  let timedOut = false;
  let stdoutBytes = 0;
  let stderrBytes = 0;
  let outputTooLarge = false;
  let stderrSeen = false;
  let inputFailed = false;
  let streamFailed = false;
  let terminationTimer: NodeJS.Timeout | undefined;
  const stdoutChunks: Buffer[] = [];
  const timeout = setTimeout(() => {
    timedOut = true;
    terminate();
  }, timeoutMs);

  const finish = (result: HostExchange<string>): void => {
    if (settled) return;
    settled = true;
    clearTimeout(timeout);
    clearTimeout(terminationTimer);
    resolve(result);
  };
  const terminate = (): void => {
    try {
      child.kill("SIGTERM");
    } catch {
      // The protocol result remains a safe blocker even if termination races.
    }
    if (terminationTimer === undefined)
      terminationTimer = setTimeout(() => {
        try {
          child.kill("SIGKILL");
        } catch {
          // The child may have exited between the two signals.
        }
      }, TERMINATION_GRACE_MS);
  };

  child.stdout.on("data", (chunk: Buffer | string) => {
    const bytes = Buffer.isBuffer(chunk)
      ? chunk.byteLength
      : Buffer.byteLength(chunk);
    if (stdoutBytes + bytes > MAX_RESPONSE_BYTES) {
      outputTooLarge = true;
      terminate();
      return;
    }
    stdoutBytes += bytes;
    stdoutChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  });
  child.stderr.on("data", (chunk: Buffer | string) => {
    stderrSeen = true;
    stderrBytes += Buffer.isBuffer(chunk)
      ? chunk.byteLength
      : Buffer.byteLength(chunk);
    if (stderrBytes > MAX_STDERR_BYTES) outputTooLarge = true;
    terminate();
  });
  child.stdout.once("error", () => {
    streamFailed = true;
    terminate();
  });
  child.stderr.once("error", () => {
    streamFailed = true;
    terminate();
  });
  child.stdin.once("error", () => {
    inputFailed = true;
    terminate();
  });
  child.once("error", () => {
    finish({
      kind: "blocked",
      blocker: protocolBlocker(
        "OMP_HOST_COMMAND_FAILED",
        "The authorized OMP host command failed before responding.",
      ),
    });
  });
  child.once("close", (exitCode, signal) => {
    if (timedOut)
      return finish({
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_TIMEOUT",
          "The authorized OMP host command did not finish before the protocol timeout.",
        ),
      });
    if (outputTooLarge)
      return finish({
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_OUTPUT_TOO_LARGE",
          "The authorized OMP host command exceeded a protocol output limit.",
        ),
      });
    if (stderrSeen)
      return finish({
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_STDERR_REJECTED",
          "The authorized OMP host command emitted stderr instead of a clean protocol response.",
        ),
      });
    if (inputFailed || streamFailed)
      return finish({
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_FAILED",
          "The authorized OMP host command stream failed before a valid response was received.",
        ),
      });
    if (exitCode !== 0 || signal !== null)
      return finish({
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_FAILED",
          "The authorized OMP host command exited without a successful protocol response.",
        ),
      });
    return finish({
      kind: "success",
      value: Buffer.concat(stdoutChunks).toString("utf8"),
    });
  });

  try {
    child.stdin.end(request);
  } catch {
    inputFailed = true;
    terminate();
  }
  return promise;
}

export type AuthorizedHostCommandAdapter = CurrentRuntimeCompatibilityAdapter &
  OmpProcessAdapter;

/**
 * Development/release tooling only. The selected executable is user-trusted and
 * is not sandboxed; it retains all OMP installation, credential, model, and
 * Provider ownership outside KPi. Every host operation receives at most `PATH`.
 * Compatibility alone may additionally receive an explicitly supplied
 * `KPI_OMP_COMPAT_AGENT_DIR` profile-agent directory and always receives the
 * per-request parent-authorized exact candidate tarball as
 * `KPI_OMP_PLUGIN_TARBALL`; no other caller environment value is forwarded.
 */
class HostCommandAdapter
  implements CurrentRuntimeCompatibilityAdapter, OmpProcessAdapter
{
  constructor(
    private readonly executable: string,
    private readonly childEnvironment: Readonly<Record<string, string>>,
    private readonly compatibilityChildEnvironment: Readonly<
      Record<string, string>
    >,
  ) {}

  async runCurrentRuntime(
    input: Parameters<
      CurrentRuntimeCompatibilityAdapter["runCurrentRuntime"]
    >[0],
  ): Promise<CurrentRuntimeCompatibilityResult> {
    const request = compatibilityRequestSchema.safeParse({
      schemaVersion: 1,
      operation: "compatibility",
      input,
    });
    if (!request.success)
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi could not construct a bounded compatibility request for the authorized host.",
        ),
      );
    const response = await this.exchange(
      request.data,
      compatibilityResponseSchema,
      COMPATIBILITY_TIMEOUT_MS,
      {
        ...this.compatibilityChildEnvironment,
        KPI_OMP_PLUGIN_TARBALL: request.data.input.pluginTarballPath,
      },
    );
    if (response.kind === "blocked")
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        response.blocker,
      );
    const result = response.value.result;
    if (result.currentRuntimeVersion !== input.currentRuntimeVersion)
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host response did not match the requested current Runtime identity.",
        ),
      );
    const hasProfileIsolatedFields =
      result.acceptanceMode !== undefined ||
      result.supportDecision !== undefined;
    const hasExplicitCompatibilityProfile =
      this.compatibilityChildEnvironment.KPI_OMP_COMPAT_AGENT_DIR !== undefined;
    if (
      (hasProfileIsolatedFields &&
        (!hasExplicitCompatibilityProfile ||
          result.status !== "passed" ||
          result.acceptanceMode !== "profile-isolated" ||
          result.supportDecision !== "requires-separate-support-review")) ||
      (hasExplicitCompatibilityProfile &&
        result.status === "passed" &&
        !hasProfileIsolatedFields)
    )
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host did not return compatibility evidence consistent with its profile-isolation mode.",
        ),
      );
    if (result.status === "blocked" && result.blocker === undefined)
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host blocked compatibility without a typed blocker.",
        ),
      );
    if (
      result.status === "passed" &&
      (result.blocker !== undefined ||
        Object.values(result.commandResults).some(
          (status) => status !== "passed",
        ))
    )
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host returned a contradictory compatibility pass result.",
        ),
      );
    if (
      result.status === "passed" &&
      (result.filesystemBeforeSha256 === undefined ||
        result.filesystemAfterSha256 === undefined ||
        result.packageSha256 === undefined ||
        result.filesystemBeforeSha256 !== result.filesystemAfterSha256)
    )
      return blockedCompatibilityResult(
        input.currentRuntimeVersion,
        protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host did not provide complete zero-write compatibility proof.",
        ),
      );
    return result;
  }

  async preflight(
    input: Parameters<OmpProcessAdapter["preflight"]>[0],
  ): ReturnType<OmpProcessAdapter["preflight"]> {
    if (containsSensitiveData(input))
      return {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi refused to send sensitive preflight identities to the authorized host.",
        ),
      };
    const request = preflightRequestSchema.safeParse({
      schemaVersion: 1,
      operation: "preflight",
      input,
    });
    if (!request.success)
      return {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi could not construct a bounded value-study preflight request for the authorized host.",
        ),
      };
    const response = await this.exchange(request.data, preflightResponseSchema);
    if (response.kind === "blocked")
      return {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: response.blocker,
      };
    const result = response.value.result;
    if (result.status === "blocked") return result;
    if (
      result.runtimeVersion !== input.runtimeVersion ||
      result.executionModelId !== input.executionModelId ||
      result.judgeModelId !== input.judgeModelId ||
      result.executionProcessId === result.judgeProcessId
    )
      return {
        status: "blocked",
        supportsUsageEvents: false,
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host preflight response did not bind the requested independent identities.",
        ),
      };
    return result;
  }

  async setRuntimeMode(
    input: Parameters<OmpProcessAdapter["setRuntimeMode"]>[0],
  ): ReturnType<OmpProcessAdapter["setRuntimeMode"]> {
    const request = runtimeModeRequestSchema.safeParse({
      schemaVersion: 1,
      operation: "runtime-mode",
      input,
    });
    if (!request.success)
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi could not construct a bounded runtime-mode request for the authorized host.",
        ),
      };
    const response = await this.exchange(
      request.data,
      runtimeModeResponseSchema,
    );
    if (response.kind === "blocked")
      return { status: "blocked", blocker: response.blocker };
    return response.value.result;
  }

  async execute(
    input: Parameters<OmpProcessAdapter["execute"]>[0],
  ): ReturnType<OmpProcessAdapter["execute"]> {
    if (containsSensitiveData({ ...input, workspacePath: undefined }))
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi refused to send sensitive execution data to the authorized host.",
        ),
      };
    const request = executeRequestSchema.safeParse({
      schemaVersion: 1,
      operation: "execute",
      input,
    });
    if (!request.success)
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi could not construct a bounded value-study execute request for the authorized host.",
        ),
      };
    const response = await this.exchange(
      request.data,
      executeResponseSchema,
      request.data.input.limits.wallClockMs + EXECUTION_CLEANUP_BUDGET_MS,
    );
    if (response.kind === "blocked")
      return { status: "blocked", blocker: response.blocker };
    const result = response.value.result;
    if (result.status === "blocked") return result;
    try {
      if (
        result.runId !== input.runId ||
        result.fixtureId !== input.fixture.id ||
        result.fixtureSha256 !== input.fixtureSha256 ||
        result.arm !== input.arm ||
        result.attempt !== input.attempt ||
        acceptanceArtifactSha256(result.acceptanceArtifact) !==
          result.acceptanceArtifactSha256
      )
        return {
          status: "blocked",
          blocker: protocolBlocker(
            "OMP_HOST_COMMAND_RESPONSE_INVALID",
            "The authorized OMP host execute response did not bind the exact requested arm and acceptance artifact.",
          ),
        };
    } catch {
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host execute response contained an invalid acceptance artifact.",
        ),
      };
    }
    const events: readonly SanitizedOmpEvent[] = result.events;
    return { ...result, events };
  }

  async judge(
    input: Parameters<OmpProcessAdapter["judge"]>[0],
  ): ReturnType<OmpProcessAdapter["judge"]> {
    if (containsSensitiveData(input))
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi refused to send sensitive or local-path data to the independent judge.",
        ),
      };
    let firstDigest: string;
    let secondDigest: string;
    try {
      firstDigest = acceptanceArtifactSha256(input.first.artifact);
      secondDigest = acceptanceArtifactSha256(input.second.artifact);
    } catch {
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi refused to send an invalid or unsafe acceptance artifact to the independent judge.",
        ),
      };
    }
    if (
      firstDigest !== input.first.artifactSha256 ||
      secondDigest !== input.second.artifactSha256
    )
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi refused to send an acceptance artifact whose declared digest is not exact.",
        ),
      };
    const request = judgeRequestSchema.safeParse({
      schemaVersion: 1,
      operation: "judge",
      input,
    });
    if (!request.success)
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi could not construct a bounded masked judge request for the authorized host.",
        ),
      };
    const response = await this.exchange(request.data, judgeResponseSchema);
    if (response.kind === "blocked")
      return { status: "blocked", blocker: response.blocker };
    const result = response.value.result;
    if (result.status === "blocked") return result;
    try {
      assertJudgeScoreMatchesRubric(
        result.first,
        input.rubric,
        `${input.fixtureId} first`,
      );
      assertJudgeScoreMatchesRubric(
        result.second,
        input.rubric,
        `${input.fixtureId} second`,
      );
      const expectedDigest = blindJudgeResultSha256({
        fixtureId: result.fixtureId,
        firstArtifactSha256: result.firstArtifactSha256,
        secondArtifactSha256: result.secondArtifactSha256,
        first: result.first,
        second: result.second,
      });
      if (
        result.runId !== input.runId ||
        result.fixtureId !== input.fixtureId ||
        result.fixtureSha256 !== input.fixtureSha256 ||
        result.firstArtifactSha256 !== input.first.artifactSha256 ||
        result.secondArtifactSha256 !== input.second.artifactSha256 ||
        expectedDigest !== result.judgeResultSha256
      )
        return {
          status: "blocked",
          blocker: protocolBlocker(
            "OMP_HOST_COMMAND_RESPONSE_INVALID",
            "The authorized OMP host judge response did not bind the exact masked artifacts and result digest.",
          ),
        };
    } catch {
      return {
        status: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host judge response contained an invalid bounded result.",
        ),
      };
    }
    return result;
  }

  private async exchange<T>(
    request: unknown,
    responseSchema: z.ZodType<T>,
    timeoutMs = SHORT_COMMAND_TIMEOUT_MS,
    childEnvironment = this.childEnvironment,
  ): Promise<HostExchange<T>> {
    let requestText: string;
    try {
      requestText = JSON.stringify(request);
    } catch {
      return {
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_INVALID",
          "KPi could not serialize the authorized host request.",
        ),
      };
    }
    if (Buffer.byteLength(requestText) > MAX_REQUEST_BYTES)
      return {
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_REQUEST_TOO_LARGE",
          "The authorized host request exceeded the bounded protocol limit.",
        ),
      };
    const transport = await runHostCommand(
      this.executable,
      childEnvironment,
      requestText,
      timeoutMs,
    );
    if (transport.kind === "blocked") return transport;
    if (transport.value.trim().length === 0)
      return {
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host command returned no JSON response.",
        ),
      };
    let rawResponse: unknown;
    try {
      rawResponse = JSON.parse(transport.value);
    } catch {
      return {
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host command returned invalid or extra JSON.",
        ),
      };
    }
    if (containsSensitiveData(rawResponse))
      return {
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_SENSITIVE_OUTPUT",
          "The authorized OMP host command returned unsafe sensitive output.",
        ),
      };
    const response = responseSchema.safeParse(rawResponse);
    if (!response.success)
      return {
        kind: "blocked",
        blocker: protocolBlocker(
          "OMP_HOST_COMMAND_RESPONSE_INVALID",
          "The authorized OMP host command returned an incompatible protocol response.",
        ),
      };
    return { kind: "success", value: response.data };
  }
}

export async function createAuthorizedHostCommandAdapter(
  environment: Readonly<NodeJS.ProcessEnv> = process.env,
): Promise<AuthorizedHostCommandAdapter | undefined> {
  const executable = environment.KPI_OMP_HARNESS_PATH;
  if (executable === undefined || !isAbsolute(executable)) return undefined;
  try {
    const details = await stat(executable);
    if (!details.isFile()) return undefined;
    await access(executable, constants.X_OK);
  } catch {
    return undefined;
  }
  const path = environment.PATH;
  const childEnvironment = path === undefined ? {} : { PATH: path };
  const compatibilityAgentDirectory = environment.KPI_OMP_COMPAT_AGENT_DIR;
  const compatibilityChildEnvironment =
    compatibilityAgentDirectory === undefined
      ? childEnvironment
      : {
          ...childEnvironment,
          KPI_OMP_COMPAT_AGENT_DIR: compatibilityAgentDirectory,
        };
  return new HostCommandAdapter(
    executable,
    childEnvironment,
    compatibilityChildEnvironment,
  );
}
