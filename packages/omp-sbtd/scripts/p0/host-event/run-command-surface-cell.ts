// Slice 7 three-profile certification — isolated command-surface +
// runtime-capability cell driver (omp-command-surface-v1 and
// omp-runtime-capabilities-v1 profiles).
//
// Spawns ONE fresh isolated real OMP Host (the cell's exact package
// dist/cli.js, never the .bin/omp shim) with the verified subject Plugin
// tarball installed, plus the capability-probe companion extension. Over the
// public RPC surface it proves:
// - the subject Plugin registered (`sbtd` in get_available_commands) — the
//   packed Slice 4 fail-closed probe passed inside this real Host;
// - the four-command surface (help, status, report, onboard plan) answers
//   with agentInvoked === false and the bounded public content contract
//   (the same predicates as scripts/p0/authorized-omp-rpc-harness.ts);
// - no unexpected interactive UI request and no sensitive text occurred.
//
// It never calls Plugin handlers directly, never emits synthetic Host events,
// and persists only sanitized records: digests, booleans, stable reason
// codes. Raw command text is bounded, sensitive-checked and hashed; the text
// itself never reaches the run record.
import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { z } from "zod";
import {
  MAX_RENDERED_SBTD_REPORT_BYTES,
  parseRenderedSbtdReport,
} from "../../../src/report/index.ts";
import { ompExtensionV2Inventory } from "../../../src/runtime/omp-extension-v2.ts";
import { P0ValidationError } from "../release-validator.ts";
import { hasSensitiveText } from "../sanitization.ts";
import {
  assertLoadedInstallationUnchanged,
  snapshotLoadedInstallation,
} from "./loaded-installation.ts";
import {
  assertPackedControllerFailClosed,
  assertSubjectTarballSeam,
  installSubjectPlugin,
  subjectStaleBlockedReason,
} from "./run-live-cell.ts";
import { recomputeHostIdentity } from "./validate.ts";

const sha256Hex = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");

const SUITE_DIR = dirname(fileURLToPath(import.meta.url));
const PROBE_EXT = join(SUITE_DIR, "capability-probe-ext.mjs");

const MAX_TOTAL_CAPTURED_TEXT_BYTES = 4 * MAX_RENDERED_SBTD_REPORT_BYTES;

const COMMAND_ORDER = ["help", "status", "report", "onboard plan"] as const;
type SurfaceCommand = (typeof COMMAND_ORDER)[number];

export interface CommandSurfaceCellOptions {
  /** Exact OMP package binary (node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js). */
  readonly ompBin: string;
  /** Registry-verified subject Plugin tarball matching the cell identity. */
  readonly pluginTarball: string;
  /** Fresh per-cell run dir (created; never shared across cells). */
  readonly runDir: string;
  /** Cell-scoped run id; binds every record to this cell. */
  readonly runId: string;
  readonly targetOmpVersion: string;
  readonly timeoutMs?: number;
  /**
   * Trusted npm-offline-v1 lock handoff (certification cells / §4 gate). When
   * set, the subject installs ONLY via `npm ci --offline` against this lock;
   * when omitted (local diagnostic use) the lock+cache are generated first.
   */
  readonly installerLockFile?: string;
  /** Content-addressed npm cache for the offline subject install. */
  readonly installerCacheDir?: string;
}

export interface CommandSurfaceCellResult {
  /** "blocked" = environment/setup unavailable; otherwise the run record was written and scoring decides passed/failed. */
  readonly status: "completed" | "blocked";
  readonly runId: string;
  readonly runDir: string;
  readonly recordPath?: string;
  readonly probeLogPath?: string;
  readonly pluginTarballSha256?: string;
  readonly blockedReason?: string;
}

// ---------------------------------------------------------------------------
// Run record schema (parsed by the certification runner before scoring)
// ---------------------------------------------------------------------------

const hashSchema = z
  .string()
  .regex(/^[a-f0-9]{64}$/, "expected a SHA-256 digest");

export const commandSurfaceRunRecordSchema = z
  .object({
    schemaVersion: z.literal(1),
    kind: z.literal("omp-command-surface-cell"),
    runId: z.string().min(1),
    pluginTarballSha256: hashSchema,
    hostIdentity: z
      .object({
        entrypointSha256: hashSchema,
        packageVersion: z.string().min(1),
        packageJsonSha256: hashSchema,
      })
      .strict(),
    sbtdCommandRegistered: z.boolean(),
    commands: z
      .array(
        z
          .object({
            command: z.enum(COMMAND_ORDER),
            agentInvoked: z.boolean(),
            contentValidated: z.boolean(),
            outputSha256: hashSchema,
          })
          .strict(),
      )
      .max(COMMAND_ORDER.length),
    unexpectedUiRequests: z.number().int().nonnegative(),
    sanitizationViolations: z.number().int().nonnegative(),
    driverError: z.string().max(256).optional(),
  })
  .strict();
export type CommandSurfaceRunRecord = z.infer<
  typeof commandSurfaceRunRecordSchema
>;

const probeHostIdentitySchema = z
  .object({
    kind: z.literal("host_identity"),
    runId: z.string().min(1),
    hostEntrypointSha256: hashSchema,
    hostPackageFound: z.literal(true),
    hostPackageName: z.literal("@oh-my-pi/pi-coding-agent"),
    hostPackageVersion: z.string().min(1),
    hostPackageJsonSha256: hashSchema,
  })
  .strict();
const probeCapabilitiesSchema = z
  .object({
    kind: z.literal("capabilities"),
    runId: z.string().min(1),
    inventoryVersion: z.literal("omp-extension-v2"),
    present: z.record(z.string(), z.boolean()),
  })
  .strict();

export interface CapabilityProbeLog {
  readonly hostIdentity: z.infer<typeof probeHostIdentitySchema>;
  readonly capabilities: z.infer<typeof probeCapabilitiesSchema>;
}

const foreignRunId = (): P0ValidationError =>
  new P0ValidationError(
    "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
    "The capability probe log belongs to a different run.",
    "Each certification cell writes a fresh probe log bound to its run id; shared or stale logs fail closed.",
  );

/**
 * Parses the capability probe JSONL log fail-closed: malformed lines,
 * missing records or foreign run ids are invalid evidence input.
 */
export function parseCapabilityProbeLog(
  logText: string,
  runId: string,
): CapabilityProbeLog {
  let hostIdentity: z.infer<typeof probeHostIdentitySchema> | undefined;
  let capabilities: z.infer<typeof probeCapabilitiesSchema> | undefined;
  for (const line of logText.split("\n")) {
    if (line.length === 0) continue;
    let record: unknown;
    try {
      record = JSON.parse(line);
    } catch {
      throw new P0ValidationError(
        "COMPATIBILITY_CELL_EVIDENCE_INVALID",
        "The capability probe log contains a malformed line.",
        "Rerun the isolated certification cell; probe logs are written once per fresh cell and never edited.",
      );
    }
    const identity = probeHostIdentitySchema.safeParse(record);
    if (identity.success) {
      if (identity.data.runId !== runId) throw foreignRunId();
      hostIdentity = identity.data;
      continue;
    }
    const caps = probeCapabilitiesSchema.safeParse(record);
    if (caps.success) {
      if (caps.data.runId !== runId) throw foreignRunId();
      capabilities = caps.data;
    }
  }
  if (hostIdentity === undefined || capabilities === undefined)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
      "The capability probe log lacks the host identity or capabilities record.",
      "Rerun the isolated certification cell; a Host that cannot load the probe extension cannot produce capability evidence.",
    );
  return { hostIdentity, capabilities };
}

export interface CapabilityProbeScore {
  readonly outcome: "passed" | "passed-with-diagnostics" | "failed";
  readonly capabilities: Readonly<Record<string, "present" | "absent">>;
  readonly missingRequired: readonly string[];
  readonly missingOptional: readonly string[];
  readonly pluginRegistered: boolean;
}

export interface ExpectedCellHost {
  readonly entrypointSha256: string;
  readonly packageJsonSha256: string;
  readonly packageVersion: string;
}

function assertObservedHost(
  observed: {
    readonly entrypointSha256: string;
    readonly packageJsonSha256: string;
    readonly packageVersion: string;
  },
  expected: ExpectedCellHost,
): void {
  if (
    observed.entrypointSha256 !== expected.entrypointSha256 ||
    observed.packageJsonSha256 !== expected.packageJsonSha256 ||
    observed.packageVersion !== expected.packageVersion
  )
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
      "The in-Host observed identity differs from the spawned OMP package identity.",
      "Spawn the cell's exact package dist/cli.js and rerun; mismatched identity evidence fails closed.",
    );
}

/**
 * Scores the in-Host capability probe against the single omp-extension-v2
 * inventory: any missing required capability or an unregistered subject
 * Plugin is failed; optional-only loss degrades to passed-with-diagnostics.
 * The in-Host identity must equal the driver-side recomputation of the exact
 * spawned package binary, otherwise scoring fails closed by throwing.
 */
export function scoreCapabilityProbe(input: {
  readonly log: CapabilityProbeLog;
  readonly pluginRegistered: boolean;
  readonly expectedHost: ExpectedCellHost;
}): CapabilityProbeScore {
  assertObservedHost(
    {
      entrypointSha256: input.log.hostIdentity.hostEntrypointSha256,
      packageJsonSha256: input.log.hostIdentity.hostPackageJsonSha256,
      packageVersion: input.log.hostIdentity.hostPackageVersion,
    },
    input.expectedHost,
  );
  const present = input.log.capabilities.present;
  const missingRequired = ompExtensionV2Inventory.requiredCapabilities.filter(
    (name) => present[name] !== true,
  );
  const missingOptional = ompExtensionV2Inventory.optionalCapabilities.filter(
    (name) => present[name] !== true,
  );
  const capabilities = Object.fromEntries(
    [
      ...ompExtensionV2Inventory.requiredCapabilities,
      ...ompExtensionV2Inventory.optionalCapabilities,
    ].map(
      (name) =>
        [
          name,
          present[name] === true ? ("present" as const) : ("absent" as const),
        ] as const,
    ),
  );
  return {
    outcome:
      missingRequired.length > 0 || !input.pluginRegistered
        ? "failed"
        : missingOptional.length > 0
          ? "passed-with-diagnostics"
          : "passed",
    capabilities,
    missingRequired,
    missingOptional,
    pluginRegistered: input.pluginRegistered,
  };
}

/**
 * Scores the command-surface run record: every one of the four public
 * commands must have a record with agentInvoked === false and validated
 * bounded content, the subject Plugin must be registered, and no unexpected
 * UI request or sensitive text may have occurred. Identity drift fails
 * closed by throwing.
 */
export function scoreCommandSurfaceRecord(
  record: unknown,
  input: {
    readonly runId: string;
    readonly pluginTarballSha256: string;
    readonly expectedHost: ExpectedCellHost;
  },
): {
  readonly outcome: "passed" | "failed";
  readonly commands: CommandSurfaceRunRecord["commands"];
} {
  const parsed = commandSurfaceRunRecordSchema.safeParse(record);
  if (!parsed.success)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_EVIDENCE_INVALID",
      "The command-surface run record is malformed.",
      "Rerun the isolated certification cell; run records are written once per fresh cell and never edited.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const data = parsed.data;
  if (
    data.runId !== input.runId ||
    data.pluginTarballSha256 !== input.pluginTarballSha256
  )
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
      "The command-surface run record does not bind to this cell's run and subject tarball.",
      "Each certification cell writes a fresh record bound to its exact identities; foreign or stale records fail closed.",
    );
  assertObservedHost(data.hostIdentity, input.expectedHost);
  const passed =
    data.driverError === undefined &&
    data.sbtdCommandRegistered &&
    data.unexpectedUiRequests === 0 &&
    data.sanitizationViolations === 0 &&
    COMMAND_ORDER.every((name) =>
      data.commands.some(
        (command) =>
          command.command === name &&
          command.agentInvoked === false &&
          command.contentValidated,
      ),
    );
  return { outcome: passed ? "passed" : "failed", commands: data.commands };
}

// ---------------------------------------------------------------------------
// Isolated cell driver
// ---------------------------------------------------------------------------

const onboardPlanNotificationSchema = z
  .object({
    digest: z.string().regex(/^[a-f0-9]{64}$/),
    targets: z.array(z.unknown()).min(1).max(100),
  })
  .passthrough();

const storedOnboardPlanSchema = z.object({
  digest: z.string().regex(/^[a-f0-9]{64}$/),
  targetCount: z.number().int().min(1).max(100),
});

/** Stable per-command content contract (mirrors the authorized harness). */
function commandContentValidated(
  command: SurfaceCommand,
  text: string,
  planNotification: unknown,
): boolean {
  switch (command) {
    case "help":
      return (
        text.includes("Usage: /sbtd help [command]") &&
        text.includes("Usage: /sbtd report")
      );
    case "status":
      return (
        /^Runtime Mode: (advisory|enforced)$/m.test(text) &&
        /^Policy Profile: [a-z0-9-]+$/m.test(text)
      );
    case "report":
      return parseRenderedSbtdReport(text) !== undefined;
    case "onboard plan":
      return storedOnboardPlanSchema.safeParse(planNotification).success;
  }
}

/** Parse a notify payload. Schema-valid Onboard plans are not recorded as text. */
export function consumeNotifyMessage(message: string): {
  readonly planNotification:
    | { readonly digest: string; readonly targetCount: number }
    | undefined;
  readonly recordAsText: boolean;
} {
  try {
    const plan = onboardPlanNotificationSchema.safeParse(JSON.parse(message));
    if (plan.success)
      return {
        planNotification: {
          digest: plan.data.digest,
          targetCount: plan.data.targets.length,
        },
        recordAsText: false,
      };
  } catch {
    // not JSON
  }
  return { planNotification: undefined, recordAsText: true };
}

/** Runs the cell protocol and closes its already-spawned child before returning. */
export async function runCommandSurfaceSession(
  child: ChildProcessWithoutNullStreams,
  timeoutMs = 180_000,
  modelRequestObserved: () => boolean = () => false,
): Promise<
  Pick<
    CommandSurfaceRunRecord,
    | "commands"
    | "sbtdCommandRegistered"
    | "unexpectedUiRequests"
    | "sanitizationViolations"
    | "driverError"
  >
> {
  const deadline = Date.now() + timeoutMs;
  const ready = Promise.withResolvers<void>();
  const closed = Promise.withResolvers<{
    code: number | null;
    signal: NodeJS.Signals | null;
  }>();
  const pending = new Map<
    string,
    {
      readonly type: string;
      readonly resolve: (value: unknown) => void;
      readonly reject: (error: Error) => void;
      readonly content?: () => boolean;
      acknowledged: boolean;
      terminal: boolean;
    }
  >();
  let driverError: string | undefined;
  let closing = false;
  let stdoutEnded = false;
  let stderrEnded = false;
  let nextId = 0;
  let buffer = "";
  const texts: string[] = [];
  let capturedBytes = 0;
  let sanitizationViolations = 0;
  let unexpectedUiRequests = 0;
  let planNotification: unknown;
  const commandResults: CommandSurfaceRunRecord["commands"] = [];
  let sbtdCommandRegistered = false;

  const fail = (code: string): void => {
    driverError ??= code;
    const error = new Error(driverError);
    ready.reject(error);
    for (const entry of pending.values()) entry.reject(error);
    pending.clear();
  };
  child.once("close", (code, signal) => {
    closed.resolve({ code, signal });
    if (!closing) fail("HOST_CLOSED_EARLY");
  });
  child.on("error", () => fail("HOST_PROCESS_ERROR"));
  child.stdin.on("error", () => fail("HOST_STDIN_ERROR"));
  child.stdout.on("error", () => fail("HOST_STDOUT_ERROR"));
  child.stderr.on("error", () => fail("HOST_STDERR_ERROR"));
  child.stdout.once("end", () => {
    stdoutEnded = true;
    if (buffer.trim().length > 0) fail("RPC_TRUNCATED_FRAME");
  });
  child.stderr.once("end", () => {
    stderrEnded = true;
  });
  child.stderr.resume();

  const send = (value: unknown): void => {
    try {
      child.stdin.write(`${JSON.stringify(value)}\n`, (error) => {
        if (error) fail("RPC_WRITE_FAILED");
      });
    } catch {
      fail("RPC_WRITE_FAILED");
    }
  };
  const command = (
    type: string,
    payload: Readonly<Record<string, unknown>> = {},
    content?: () => boolean,
  ): Promise<unknown> => {
    if (driverError !== undefined)
      return Promise.reject(new Error(driverError));
    const id = `cert-cell-${++nextId}`;
    const request = Promise.withResolvers<unknown>();
    pending.set(id, {
      type,
      resolve: request.resolve,
      reject: request.reject,
      acknowledged: false,
      terminal: false,
      ...(content === undefined ? {} : { content }),
    });
    // One shared deadline covers ACK, terminal and content, in any arrival order.
    const timer = setTimeout(
      () => fail("RPC_COMMAND_TIMEOUT"),
      Math.max(
        0,
        Math.min(type === "prompt" ? 60_000 : 30_000, deadline - Date.now()),
      ),
    );
    send({ id, type, ...payload });
    return request.promise.finally(() => clearTimeout(timer));
  };
  const completePrompts = (): void => {
    for (const [id, entry] of pending) {
      if (entry.acknowledged && entry.terminal && entry.content?.()) {
        pending.delete(id);
        entry.resolve(undefined);
      }
    }
  };
  const recordText = (text: string): void => {
    capturedBytes += Buffer.byteLength(text, "utf8");
    if (
      hasSensitiveText(text) ||
      Buffer.byteLength(text, "utf8") > MAX_RENDERED_SBTD_REPORT_BYTES ||
      capturedBytes > MAX_TOTAL_CAPTURED_TEXT_BYTES
    ) {
      sanitizationViolations += 1;
      fail("RPC_SANITIZATION_FAILED");
      return;
    }
    texts.push(text);
  };
  const receive = (frame: Record<string, unknown>): void => {
    const type = frame.type;
    if (type === "ready") {
      ready.resolve();
      return;
    }
    if (
      type === "extension_error" ||
      type === "error" ||
      type === "auto_retry_start" ||
      (typeof type === "string" &&
        /^(agent_|turn_|message_|tool_execution_|model_)/.test(type))
    ) {
      fail("RPC_AGENT_OR_EXTENSION_ERROR");
      return;
    }
    if (type === "response" || type === "prompt_result") {
      if (frame.success === false || frame.error !== undefined) {
        fail("RPC_COMMAND_FAILED");
        return;
      }
      const id = typeof frame.id === "string" ? frame.id : undefined;
      const entry = id === undefined ? undefined : pending.get(id);
      if (entry === undefined || id === undefined) {
        if (type === "prompt_result") fail("RPC_UNEXPECTED_TERMINAL");
        return;
      }
      if (type === "response") {
        if (frame.command !== entry.type || frame.success !== true) {
          fail("RPC_ACK_INVALID");
          return;
        }
        if (entry.type !== "prompt") {
          pending.delete(id);
          entry.resolve(frame.data);
          return;
        }
        const data = frame.data;
        if (
          frame.agentInvoked === true ||
          (typeof data === "object" &&
            data !== null &&
            "agentInvoked" in data &&
            data.agentInvoked === true)
        ) {
          fail("RPC_AGENT_INVOKED");
          return;
        }
        entry.acknowledged = true;
      } else {
        if (
          entry.type !== "prompt" ||
          entry.terminal ||
          frame.status !== "completed" ||
          frame.sessionSettled !== true ||
          frame.agentInvoked !== false
        ) {
          fail("RPC_TERMINAL_REJECTED");
          return;
        }
        entry.terminal = true;
      }
      completePrompts();
      return;
    }
    if (type === "extension_ui_request") {
      if (frame.method === "notify" && typeof frame.message === "string") {
        const consumed = consumeNotifyMessage(frame.message);
        if (consumed.planNotification !== undefined)
          planNotification = consumed.planNotification;
        if (consumed.recordAsText) recordText(frame.message);
        completePrompts();
        return;
      }
      if (frame.method === "setStatus" || frame.method === "setWidget") return;
      unexpectedUiRequests += 1;
      if (typeof frame.id === "string")
        send({ type: "extension_ui_response", id: frame.id, cancelled: true });
      fail("RPC_UNEXPECTED_UI");
    }
  };
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    if (driverError !== undefined) return; // Continue draining, never retain failed text.
    buffer += String(chunk);
    if (Buffer.byteLength(buffer, "utf8") > MAX_TOTAL_CAPTURED_TEXT_BYTES) {
      buffer = "";
      fail("RPC_CAPTURE_LIMIT");
      return;
    }
    for (;;) {
      const nl = buffer.indexOf("\n");
      if (nl < 0) break;
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line.length === 0) continue;
      try {
        const parsed: unknown = JSON.parse(line);
        if (
          typeof parsed !== "object" ||
          parsed === null ||
          Array.isArray(parsed)
        )
          throw new Error();
        receive(parsed as Record<string, unknown>);
      } catch {
        fail("RPC_FRAME_INVALID");
      }
      if (driverError !== undefined) break;
    }
  });

  const readyTimer = setTimeout(
    () => fail("RPC_READY_TIMEOUT"),
    Math.max(0, Math.min(30_000, deadline - Date.now())),
  );
  try {
    await ready.promise;
    clearTimeout(readyTimer);
    await command("set_auto_retry", { enabled: false });
    const available = (await command("get_available_commands")) as
      | { commands?: { name?: string }[] }
      | undefined;
    sbtdCommandRegistered = (available?.commands ?? []).some(
      (entry) => entry.name === "sbtd",
    );
    for (const name of COMMAND_ORDER) {
      planNotification = undefined;
      const since = texts.length;
      const content = () =>
        commandContentValidated(
          name,
          texts.slice(since).join("\n"),
          planNotification,
        );
      await command("prompt", { message: `/sbtd ${name}` }, content);
      commandResults.push({
        command: name,
        agentInvoked: false,
        contentValidated: content(),
        outputSha256: sha256Hex(texts.slice(since).join("\n")),
      });
    }
  } catch {
    fail(driverError ?? "RPC_SESSION_FAILED");
  } finally {
    clearTimeout(readyTimer);
    closing = true;
    try {
      child.stdin.end();
    } catch {
      fail("HOST_STDIN_ERROR");
    }
    const waitClose = async () => {
      const grace = Promise.withResolvers<undefined>();
      const timer = setTimeout(() => grace.resolve(undefined), 3_000);
      try {
        return await Promise.race([closed.promise, grace.promise]);
      } finally {
        clearTimeout(timer);
      }
    };
    let exit = await waitClose();
    if (exit === undefined) {
      fail("HOST_CLOSE_TIMEOUT");
      try {
        if (child.pid !== undefined) process.kill(-child.pid, "SIGKILL");
        else child.kill("SIGKILL");
      } catch {
        fail("HOST_KILL_FAILED");
      }
      exit = await waitClose();
    }
    if (exit === undefined) {
      fail("HOST_NOT_CLOSED");
      child.stdin.destroy();
      child.stdout.destroy();
      child.stderr.destroy();
    } else {
      if (exit.signal !== null) fail("HOST_EXIT_SIGNAL");
      else if (exit.code !== 0) fail("HOST_EXIT_NONZERO");
      if (!stdoutEnded || !stderrEnded) fail("HOST_CAPTURE_INCOMPLETE");
    }
  }
  if (modelRequestObserved()) fail("RPC_MODEL_CALL");
  return {
    commands: commandResults,
    sbtdCommandRegistered,
    unexpectedUiRequests,
    sanitizationViolations,
    ...(driverError === undefined ? {} : { driverError }),
  };
}

export function assertRequestedHostVersion(
  observed: string,
  requested: string,
): void {
  if (observed !== requested) throw new Error("OMP_TARGET_VERSION_MISMATCH");
}

export async function runCommandSurfaceCell(
  options: CommandSurfaceCellOptions,
): Promise<CommandSurfaceCellResult> {
  const runDir = options.runDir;
  const runId = options.runId;
  const timeoutMs = options.timeoutMs ?? 180_000;
  const blocked = (reason: string): CommandSurfaceCellResult => ({
    status: "blocked",
    runId,
    runDir,
    blockedReason: reason,
  });

  let tarballPath: string;
  let pluginTarballSha256: string;
  try {
    tarballPath = realpathSync(resolve(options.pluginTarball));
    pluginTarballSha256 = sha256Hex(readFileSync(tarballPath));
  } catch {
    return blocked("PLUGIN_TARBALL_UNAVAILABLE");
  }
  try {
    await assertSubjectTarballSeam(tarballPath);
  } catch (error) {
    return blocked(subjectStaleBlockedReason(error));
  }
  let ompBin: string;
  try {
    ompBin = realpathSync(resolve(options.ompBin));
  } catch {
    return blocked("OMP_BIN_UNAVAILABLE");
  }
  const hostIdentity = recomputeHostIdentity(ompBin);
  if (
    hostIdentity.packageVersion === undefined ||
    hostIdentity.packageJsonSha256 === undefined
  )
    return blocked("OMP_PACKAGE_IDENTITY_UNAVAILABLE");
  try {
    assertRequestedHostVersion(
      hostIdentity.packageVersion,
      options.targetOmpVersion,
    );
  } catch {
    return blocked("OMP_TARGET_VERSION_MISMATCH");
  }

  const outDir = join(runDir, "out");
  const homeDir = join(runDir, "home");
  const agentDir = join(runDir, "agent");
  const projectDir = join(runDir, "project");
  await mkdir(outDir, { recursive: true });
  await mkdir(join(projectDir, ".omp"), { recursive: true });
  await mkdir(homeDir, { recursive: true });

  let pluginExt: string;
  try {
    pluginExt = await installSubjectPlugin(
      join(agentDir, "plugins"),
      tarballPath,
      homeDir,
      {
        ...(options.installerLockFile === undefined
          ? {}
          : { lockFilePath: options.installerLockFile }),
        ...(options.installerCacheDir === undefined
          ? {}
          : { cacheDir: options.installerCacheDir }),
      },
    );
  } catch {
    return blocked("PLUGIN_INSTALL_FAILED");
  }
  try {
    await assertPackedControllerFailClosed(
      join(dirname(pluginExt), "runtime", "index.js"),
    );
  } catch (error) {
    return blocked(subjectStaleBlockedReason(error));
  }
  const loadedRoot = join(agentDir, "plugins");
  let loadedBaseline: ReadonlyMap<string, string>;
  try {
    loadedBaseline = await snapshotLoadedInstallation(loadedRoot);
  } catch {
    return blocked("LOADED_INSTALLATION_DRIFT");
  }

  // Compatibility-only provider overlay (spec: P0 Compatibility-Only OMP
  // Provider Overlay — exact payload) plus the loopback-only deterministic
  // provider; no real Provider credential exists in a certification cell.
  await writeFile(
    join(projectDir, ".omp", "config.yml"),
    "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\n",
    { encoding: "utf8", mode: 0o600 },
  );
  const probeLogPath = join(outDir, "capabilities.jsonl");
  const recordPath = join(outDir, "command-surface.json");
  let modelRequestObserved = false;
  const stub = createServer((req, res) => {
    modelRequestObserved = true;
    if (req.method === "POST" && req.url?.startsWith("/v1/chat/completions")) {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(
        JSON.stringify({
          id: "chatcmpl-cert-cell",
          object: "chat.completion",
          created: 1_700_000_000,
          model: "spike-1",
          choices: [
            {
              index: 0,
              message: { role: "assistant", content: "SPIKE_OK" },
              finish_reason: "stop",
            },
          ],
          usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
        }),
      );
      return;
    }
    res.writeHead(404).end("not found");
  });
  const listen = Promise.withResolvers<void>();
  stub.listen(0, "127.0.0.1", listen.resolve);
  stub.once("error", listen.reject);
  let session: Awaited<ReturnType<typeof runCommandSurfaceSession>>;
  try {
    await listen.promise;
    const address = stub.address();
    const stubPort =
      typeof address === "object" && address !== null ? address.port : 0;
    await writeFile(
      join(agentDir, "models.yml"),
      [
        "providers:",
        "  spike:",
        `    baseUrl: http://127.0.0.1:${stubPort}/v1`,
        "    api: openai-completions",
        "    auth: none",
        "    models:",
        "      - id: spike-1",
        "        name: Spike Deterministic",
        "        supportsTools: true",
        "        contextWindow: 128000",
        "        maxTokens: 4096",
        "        input: [text]",
        "        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }",
        "",
      ].join("\n"),
      { encoding: "utf8", mode: 0o600 },
    );

    await writeFile(probeLogPath, "", "utf8");

    const child = spawn(
      ompBin,
      [
        "--mode",
        "rpc-ui",
        "--cwd",
        projectDir,
        "--no-tools",
        "--no-skills",
        "--no-rules",
        "--no-pty",
        "--no-title",
        "--extension",
        pluginExt,
        "--extension",
        PROBE_EXT,
      ],
      {
        cwd: projectDir,
        detached: true,
        env: {
          PATH: process.env.PATH ?? "",
          HOME: homeDir,
          XDG_CACHE_HOME: join(homeDir, ".cache"),
          XDG_CONFIG_HOME: join(homeDir, ".config"),
          XDG_DATA_HOME: join(homeDir, ".local", "share"),
          PI_CODING_AGENT_DIR: agentDir,
          CI: "1",
          NO_COLOR: "1",
          CAPABILITY_PROBE_LOG: probeLogPath,
          CAPABILITY_PROBE_NAMES: JSON.stringify({
            required: [...ompExtensionV2Inventory.requiredCapabilities],
            optional: [...ompExtensionV2Inventory.optionalCapabilities],
          }),
          HOST_EVENT_RUN_ID: runId,
        },
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    session = await runCommandSurfaceSession(
      child,
      timeoutMs,
      () => modelRequestObserved,
    );
  } catch {
    return blocked("DRIVER_SETUP_FAILED");
  } finally {
    const stopped = Promise.withResolvers<void>();
    stub.close(() => stopped.resolve());
    stub.closeAllConnections();
    await stopped.promise;
  }
  const {
    commands: commandResults,
    sbtdCommandRegistered,
    unexpectedUiRequests,
    sanitizationViolations,
  } = session;
  let driverError = session.driverError;
  if (modelRequestObserved) driverError ??= "RPC_MODEL_CALL";
  try {
    await assertLoadedInstallationUnchanged(loadedRoot, loadedBaseline);
  } catch {
    driverError ??= "LOADED_INSTALLATION_DRIFT";
  }

  if (commandResults.length === 0)
    return blocked(
      driverError === undefined
        ? "DRIVER_SCENARIO_INCOMPLETE"
        : "DRIVER_EXIT_NONZERO",
    );

  const record: CommandSurfaceRunRecord = {
    schemaVersion: 1,
    kind: "omp-command-surface-cell",
    runId,
    pluginTarballSha256,
    hostIdentity: {
      entrypointSha256: hostIdentity.entrypointSha256,
      packageVersion: hostIdentity.packageVersion,
      packageJsonSha256: hostIdentity.packageJsonSha256,
    },
    sbtdCommandRegistered,
    commands: commandResults,
    unexpectedUiRequests,
    sanitizationViolations,
    ...(driverError === undefined ? {} : { driverError }),
  };
  await writeFile(recordPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  return {
    status: "completed",
    runId,
    runDir,
    recordPath,
    probeLogPath,
    pluginTarballSha256,
  };
}

// ---------------------------------------------------------------------------
// CLI (§4 publish gate): run one cell, score the record, exit on the verdict
// ---------------------------------------------------------------------------
//
// SPIKE_OMP_BIN=<omp dist/cli.js> COMMAND_SURFACE_PLUGIN_TARBALL=<tgz> \
//   [COMMAND_SURFACE_RUNS_ROOT=<dir>] [COMMAND_SURFACE_TARGET_VERSION=<v>] \
//   [INSTALLER_LOCK_FILE=<lock> INSTALLER_CACHE_DIR=<dir>] \
//   tsx run-command-surface-cell.ts
//
// Output is one JSON line with stable codes only. Exit 0 requires the scored
// four-command record to be "passed"; a scored "failed" exits 1; any setup
// blocker exits 2 with a blockedReason — the CLI never fakes a pass.
const isMain = (() => {
  const entry = process.argv[1];
  return (
    typeof entry === "string" &&
    entry.length > 0 &&
    import.meta.url === pathToFileURL(entry).href
  );
})();

if (isMain) {
  const ompBin = process.env.SPIKE_OMP_BIN;
  const pluginTarball = process.env.COMMAND_SURFACE_PLUGIN_TARBALL;
  if (typeof ompBin !== "string" || typeof pluginTarball !== "string") {
    console.error(
      "usage: SPIKE_OMP_BIN=<omp> COMMAND_SURFACE_PLUGIN_TARBALL=<tgz> [COMMAND_SURFACE_RUNS_ROOT=<dir>] [COMMAND_SURFACE_TARGET_VERSION=<v>] [INSTALLER_LOCK_FILE=<lock> INSTALLER_CACHE_DIR=<dir>] tsx run-command-surface-cell.ts",
    );
    process.exit(2);
  }
  const runId = `run-${Date.now()}-${randomUUID().slice(0, 8)}`;
  const runDir = join(
    process.env.COMMAND_SURFACE_RUNS_ROOT ?? ".tmp/command-surface",
    runId,
  );
  await mkdir(runDir, { recursive: true });
  const result = await runCommandSurfaceCell({
    ompBin,
    pluginTarball,
    runDir,
    runId,
    targetOmpVersion: process.env.COMMAND_SURFACE_TARGET_VERSION ?? "18.11.1",
    ...(process.env.INSTALLER_LOCK_FILE === undefined
      ? {}
      : { installerLockFile: process.env.INSTALLER_LOCK_FILE }),
    ...(process.env.INSTALLER_CACHE_DIR === undefined
      ? {}
      : { installerCacheDir: process.env.INSTALLER_CACHE_DIR }),
  });
  if (result.status === "blocked") {
    console.log(
      JSON.stringify({
        status: "blocked",
        runId,
        runDir,
        blockedReason: result.blockedReason ?? "BLOCKED",
      }),
    );
    process.exit(2);
  }
  try {
    const recordRaw: unknown = JSON.parse(
      readFileSync(result.recordPath ?? "", "utf8"),
    );
    const expectedHost = recomputeHostIdentity(realpathSync(resolve(ompBin)));
    if (
      expectedHost.packageVersion === undefined ||
      expectedHost.packageJsonSha256 === undefined
    )
      throw new Error("OMP_PACKAGE_IDENTITY_UNAVAILABLE");
    const scored = scoreCommandSurfaceRecord(recordRaw, {
      runId,
      pluginTarballSha256: result.pluginTarballSha256 ?? "",
      expectedHost: {
        entrypointSha256: expectedHost.entrypointSha256,
        packageJsonSha256: expectedHost.packageJsonSha256,
        packageVersion: expectedHost.packageVersion,
      },
    });
    const record = recordRaw as CommandSurfaceRunRecord;
    console.log(
      JSON.stringify({
        status: "completed",
        outcome: scored.outcome,
        runId,
        runDir,
        recordPath: result.recordPath,
        pluginTarballSha256: result.pluginTarballSha256,
        sbtdCommandRegistered: record.sbtdCommandRegistered,
        driverError: record.driverError ?? null,
        unexpectedUiRequests: record.unexpectedUiRequests,
        sanitizationViolations: record.sanitizationViolations,
        commands: scored.commands,
      }),
    );

    process.exit(scored.outcome === "passed" ? 0 : 1);
  } catch {
    console.log(
      JSON.stringify({
        status: "blocked",
        runId,
        runDir,
        blockedReason: "COMMAND_SURFACE_RECORD_UNSCORABLE",
      }),
    );
    process.exit(2);
  }
}
