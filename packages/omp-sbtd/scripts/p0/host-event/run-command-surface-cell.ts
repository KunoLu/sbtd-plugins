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
import { spawn } from "node:child_process";
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
import { ompExtensionV1Inventory } from "../../../src/runtime/omp-extension-v1.ts";
import { P0ValidationError } from "../release-validator.ts";
import { hasSensitiveText } from "../sanitization.ts";
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
    inventoryVersion: z.literal("omp-extension-v1"),
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
 * Scores the in-Host capability probe against the single omp-extension-v1
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
  const missingRequired = ompExtensionV1Inventory.requiredCapabilities.filter(
    (name) => present[name] !== true,
  );
  const missingOptional = ompExtensionV1Inventory.optionalCapabilities.filter(
    (name) => present[name] !== true,
  );
  const capabilities = Object.fromEntries(
    [
      ...ompExtensionV1Inventory.requiredCapabilities,
      ...ompExtensionV1Inventory.optionalCapabilities,
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

  // Compatibility-only provider overlay (spec: P0 Compatibility-Only OMP
  // Provider Overlay — exact payload) plus the loopback-only deterministic
  // provider; no real Provider credential exists in a certification cell.
  await writeFile(
    join(projectDir, ".omp", "config.yml"),
    "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\n",
    { encoding: "utf8", mode: 0o600 },
  );
  const stub = createServer((req, res) => {
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

  const probeLogPath = join(outDir, "capabilities.jsonl");
  const recordPath = join(outDir, "command-surface.json");
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
          required: [...ompExtensionV1Inventory.requiredCapabilities],
          optional: [...ompExtensionV1Inventory.optionalCapabilities],
        }),
        HOST_EVENT_RUN_ID: runId,
      },
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  let stderrTail = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => {
    stderrTail = (stderrTail + String(chunk)).slice(-2048);
  });

  const pending = new Map<
    string,
    {
      readonly type: string;
      readonly resolve: (value: unknown) => void;
      readonly reject: (error: Error) => void;
    }
  >();
  let nextId = 0;
  let buffer = "";
  let ready = false;
  let childClosed = false;
  const textWaiters: {
    readonly matches: () => boolean;
    readonly resolve: () => void;
    readonly reject: (error: Error) => void;
  }[] = [];
  const texts: string[] = [];
  let capturedBytes = 0;
  let sanitizationViolations = 0;
  let unexpectedUiRequests = 0;
  let planNotification: unknown;

  const failAll = (error: Error): void => {
    for (const [, entry] of pending) entry.reject(error);
    pending.clear();
    for (const waiter of textWaiters.splice(0)) waiter.reject(error);
  };
  child.on("close", () => {
    childClosed = true;
    failAll(new Error("omp closed early"));
  });
  const send = (value: unknown): void => {
    child.stdin.write(`${JSON.stringify(value)}\n`);
  };
  const command = (
    type: string,
    payload: Readonly<Record<string, unknown>> = {},
    timeout = 30_000,
  ): Promise<unknown> => {
    const id = `cert-cell-${++nextId}`;
    const {
      promise,
      resolve: resolvePending,
      reject,
    } = Promise.withResolvers<unknown>();
    pending.set(id, { type, resolve: resolvePending, reject });
    send({ id, type, ...payload });
    const timer = setTimeout(() => {
      if (pending.delete(id)) reject(new Error(`timeout waiting ${type}`));
    }, timeout);
    return promise.finally(() => clearTimeout(timer));
  };
  const recordText = (text: string): void => {
    if (
      hasSensitiveText(text) ||
      Buffer.byteLength(text, "utf8") > MAX_RENDERED_SBTD_REPORT_BYTES
    ) {
      sanitizationViolations += 1;
      return;
    }
    capturedBytes += Buffer.byteLength(text, "utf8");
    if (capturedBytes > MAX_TOTAL_CAPTURED_TEXT_BYTES) {
      sanitizationViolations += 1;
      return;
    }
    texts.push(text);
    for (const waiter of textWaiters.splice(0)) {
      if (waiter.matches()) waiter.resolve();
      else textWaiters.push(waiter);
    }
  };

  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    buffer += String(chunk);
    for (;;) {
      const nl = buffer.indexOf("\n");
      if (nl < 0) break;
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line.length === 0) continue;
      let frame: Record<string, unknown>;
      try {
        frame = JSON.parse(line) as Record<string, unknown>;
      } catch {
        continue;
      }
      const type = frame.type;
      if (type === "ready") {
        ready = true;
        continue;
      }
      if (type === "response" || type === "prompt_result") {
        const id = typeof frame.id === "string" ? frame.id : undefined;
        const entry = id === undefined ? undefined : pending.get(id);
        if (entry === undefined || id === undefined) continue;
        pending.delete(id);
        if (frame.success === false)
          entry.reject(new Error(`${entry.type} failed`));
        else if (entry.type === "prompt")
          entry.resolve({ agentInvoked: frame.agentInvoked === true });
        else entry.resolve(frame.data);
        continue;
      }
      if (type === "extension_ui_request") {
        const id = typeof frame.id === "string" ? frame.id : undefined;
        if (frame.method === "notify" && typeof frame.message === "string") {
          const consumed = consumeNotifyMessage(frame.message);
          if (consumed.planNotification !== undefined)
            planNotification = consumed.planNotification;
          if (consumed.recordAsText) recordText(frame.message);
          continue;
        }
        if (frame.method === "setStatus" || frame.method === "setWidget")
          continue;
        // confirm/select or any other interactive request is unexpected in
        // the read-only four-command profile: deny and fail closed.
        unexpectedUiRequests += 1;
        if (id !== undefined)
          send({ type: "extension_ui_response", id, cancelled: true });
      }
      // All other streaming frames are intentionally ignored.
    }
  });

  const waitReady = async (timeout = 30_000): Promise<void> => {
    const start = Date.now();
    while (!ready) {
      if (childClosed) throw new Error("omp closed before ready");
      if (Date.now() - start > timeout)
        throw new Error("omp did not become ready");
      await new Promise((resolveWait) => setTimeout(resolveWait, 25));
    }
  };
  const waitForContent = (
    matches: () => boolean,
    timeout = 30_000,
  ): Promise<void> => {
    const {
      promise,
      resolve: resolveWait,
      reject,
    } = Promise.withResolvers<void>();
    const waiter = { matches, resolve: resolveWait, reject };
    const timer = setTimeout(() => {
      const index = textWaiters.indexOf(waiter);
      if (index >= 0) textWaiters.splice(index, 1);
      reject(new Error("timeout waiting command output"));
    }, timeout);
    textWaiters.push(waiter);
    return promise.finally(() => clearTimeout(timer));
  };

  const commandResults: CommandSurfaceRunRecord["commands"][number][] = [];
  let driverError: string | undefined;
  let sbtdCommandRegistered = false;
  const deadline = Date.now() + timeoutMs;
  try {
    await waitReady();
    await command("set_auto_retry", { enabled: false });
    const available = (await command("get_available_commands")) as
      | { commands?: { name?: string }[] }
      | undefined;
    sbtdCommandRegistered = (available?.commands ?? []).some(
      (entry) => entry.name === "sbtd",
    );
    for (const name of COMMAND_ORDER) {
      if (Date.now() > deadline) throw new Error("cell timeout");
      planNotification = undefined;
      const since = texts.length;
      const ack = (await command(
        "prompt",
        { message: `/sbtd ${name}` },
        60_000,
      )) as { agentInvoked?: boolean } | undefined;
      const agentInvoked = ack?.agentInvoked === true;
      if (!agentInvoked) {
        const remaining = Math.max(5_000, deadline - Date.now());
        await waitForContent(
          () =>
            commandContentValidated(
              name,
              texts.slice(since).join("\n"),
              planNotification,
            ),
          Math.min(30_000, remaining),
        ).catch(() => undefined);
      }
      const output = texts.slice(since).join("\n");
      commandResults.push({
        command: name,
        agentInvoked,
        contentValidated:
          !agentInvoked &&
          commandContentValidated(name, output, planNotification),
        outputSha256: sha256Hex(output),
      });
    }
  } catch (error) {
    driverError = error instanceof Error ? error.name : "unknown";
  } finally {
    try {
      child.stdin.end();
    } catch {
      // already closed
    }
    const killer = setTimeout(() => {
      try {
        if (child.pid !== undefined) process.kill(-child.pid, "SIGKILL");
      } catch {
        // already gone
      }
    }, 3_000);
    child.once("close", () => clearTimeout(killer));
  }
  stub.close();

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
    targetOmpVersion: process.env.COMMAND_SURFACE_TARGET_VERSION ?? "17.3.5",
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
