// Slice 5 Host Event Surface suite — live-cell runner.
//
// Runs ONE fresh isolated real-Host cell: installs the frozen candidate Plugin
// tarball into an isolated agent dir, spawns the deterministic public-RPC
// driver (drive.mjs) against an exact OMP binary, then scores the run with
// the evidence validator and persists a sanitized content-addressed
// local-observation bundle under the run dir.
//
// The suite's single event list is `ompExtensionV1Inventory` (Slice 4 Host
// Contract); the observer receives it through HOST_EVENT_OBSERVE_EVENTS.
// The observer validates payloads with the subject tarball's own
// dist/runtime/omp-extension-v1.js — a missing module fails the cell closed,
// so a stale pre-Slice-4 pack can never silently pass. After install, the
// packed registerRuntimeController is additionally probed behaviorally: it
// must fail closed on a Host without `on` before registerCommand runs.
//
// The subject installs through the shared npm-offline-v1 installer
// (scripts/p0/install-subject-plugin.ts): staged at `plugin.tgz`, resolved
// through the npm-generated diagnostic lock, installed with
// `npm ci --offline` — bun is never spawned.
//
// Outcome vocabulary: "passed" | "passed-with-diagnostics" | "failed" |
// "blocked" (environment/setup unavailable). Local cells are
// `local-observation` evidence only; they never produce `certified`.
//
// CLI: SPIKE_OMP_BIN=<omp> HOST_EVENT_PLUGIN_TARBALL=<tgz> \
//   pnpm exec tsx scripts/p0/host-event/run-live-cell.ts
import { execFileSync, spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ompExtensionV1Inventory } from "../../../src/runtime/omp-extension-v1.ts";
import { installSubjectPluginOfflineV1 } from "../install-subject-plugin.ts";
import {
  buildLocalObservationBundle,
  type EvidenceWriteResult,
  type HostEventEvidenceBundle,
  type HostEventOutcome,
  type HostEventRunDir,
  type HostEventRunExpectation,
  type HostEventVerdict,
  readHostEventRunDir,
  recomputeHostIdentity,
  validateHostEventRun,
  writeLocalObservationEvidence,
} from "./validate.ts";

/** The suite's single event list — straight from the Slice 4 inventory. */
export function hostEventObserveEvents(): readonly string[] {
  return [
    ...ompExtensionV1Inventory.requiredEvents,
    ...ompExtensionV1Inventory.optionalEvents,
  ];
}

export type LiveCellOutcome = HostEventOutcome | "blocked";

export interface LiveCellOptions {
  /** Exact OMP binary (e.g. .tmp/gate-0-2/runtime/node_modules/.bin/omp). */
  readonly ompBin: string;
  /** Frozen candidate Plugin tarball (.tgz); every cell in a run reuses it. */
  readonly pluginTarball: string;
  /** Parent for fresh per-run dirs (default `.tmp/host-event`). */
  readonly runsRoot?: string;
  readonly targetOmpVersion?: string;
  /** Overall driver timeout in ms (default 240_000). */
  readonly timeoutMs?: number;
  /**
   * Trusted npm-offline-v1 lock handoff (certification cells). When set, the
   * subject installs ONLY via `npm ci --offline` against this lock; when
   * omitted (local diagnostic use) the lock+cache are generated first.
   */
  readonly installerLockFile?: string;
  /** Content-addressed npm cache for the offline subject install. */
  readonly installerCacheDir?: string;
}

export interface LiveCellResult {
  readonly outcome: LiveCellOutcome;
  readonly runId: string;
  readonly runDir: string;
  readonly reasonCodes: readonly string[];
  readonly diagnostics: readonly string[];
  readonly verdict?: HostEventVerdict;
  readonly evidence?: EvidenceWriteResult;
  readonly bundle?: HostEventEvidenceBundle;
  readonly pluginTarballSha256?: string;
  /** Setup blocker detail when outcome is "blocked" (sanitized, stable). */
  readonly blockedReason?: string;
}

export interface DriverSpawnResult {
  readonly code: number | null;
  readonly timedOut: boolean;
  readonly spawnFailed: boolean;
}

/** Stable blocked reason when the driver did not complete successfully. */
export function liveCellDriverExitReason(
  result: DriverSpawnResult,
): string | undefined {
  if (result.spawnFailed) return "DRIVER_EXIT_SPAWN_FAILED";
  if (result.timedOut) return "DRIVER_EXIT_TIMEOUT";
  if (result.code !== 0) return "DRIVER_EXIT_NONZERO";
  return undefined;
}

/**
 * Post-spawn runner step. A spawn/timeout/nonzero driver is blocked with
 * DRIVER_EXIT_* and leftover observer/scenario files are never scored.
 */
export async function completeLiveCellAfterDriver(input: {
  readonly drive: DriverSpawnResult;
  readonly runId: string;
  readonly runDir: string;
  readonly expectation: HostEventRunExpectation;
}): Promise<LiveCellResult> {
  const blocked = (reason: string): LiveCellResult => ({
    outcome: "blocked",
    runId: input.runId,
    runDir: input.runDir,
    reasonCodes: [],
    diagnostics: [],
    blockedReason: reason,
    pluginTarballSha256: input.expectation.pluginTarballSha256,
  });
  const exitReason = liveCellDriverExitReason(input.drive);
  if (exitReason !== undefined) return blocked(exitReason);

  let run: HostEventRunDir;
  try {
    run = await readHostEventRunDir(input.runDir);
  } catch {
    return blocked("DRIVER_RUN_RECORDS_UNAVAILABLE");
  }
  const verdict = validateHostEventRun(
    {
      records: run.records,
      scenario: run.scenario,
      malformedObserverLines: run.malformedObserverLines,
      sanitizationViolations: run.sanitizationViolations,
    },
    input.expectation,
  );
  const bundle = buildLocalObservationBundle({
    verdict,
    expectation: input.expectation,
    sources: {
      observerLogSha256: run.observerLogSha256,
      driverLogSha256: run.driverLogSha256,
      scenarioSha256: run.scenarioSha256,
    },
  });
  const evidence = await writeLocalObservationEvidence(
    join(input.runDir, "evidence"),
    bundle,
  );
  return {
    outcome: verdict.outcome,
    runId: input.runId,
    runDir: input.runDir,
    reasonCodes: verdict.reasonCodes,
    diagnostics: verdict.diagnostics,
    verdict,
    evidence,
    bundle,
    pluginTarballSha256: input.expectation.pluginTarballSha256,
  };
}

const sha256File = (path: string): string =>
  createHash("sha256").update(readFileSync(path)).digest("hex");

/**
 * Stable blockedReason for a stale-subject failure: keep the thrown
 * `SUBJECT_STALE:*` code when present; anything else (e.g. a `tar` error
 * whose message embeds local paths) collapses to bare `SUBJECT_STALE`.
 * Raw error text never reaches `blockedReason`.
 */
export function subjectStaleBlockedReason(error: unknown): string {
  return error instanceof Error && error.message.startsWith("SUBJECT_STALE:")
    ? error.message
    : "SUBJECT_STALE";
}

/**
 * Thin wrapper over the shared npm-offline-v1 installer
 * (scripts/p0/install-subject-plugin.ts): the tarball is staged at the fixed
 * relative path `plugin.tgz`, dependencies resolve through the npm-generated
 * diagnostic lock, and the install itself is `npm ci --offline`. With a
 * trusted lock+cache handoff (certification cells) only the offline ci runs;
 * without one (local diagnostic use) the lock+cache are generated first.
 * bun is never spawned. Any installer failure throws; callers collapse it to
 * the stable `PLUGIN_INSTALL_FAILED` blockedReason.
 */
export async function installSubjectPlugin(
  agentPluginsDir: string,
  tarballPath: string,
  homeDir: string,
  installer?: {
    readonly lockFilePath?: string;
    readonly cacheDir?: string;
  },
): Promise<string> {
  const result = await installSubjectPluginOfflineV1({
    runDir: agentPluginsDir,
    tarballPath,
    cacheDir: installer?.cacheDir ?? join(homeDir, ".npm"),
    ...(installer?.lockFilePath === undefined
      ? {}
      : { lockFilePath: installer.lockFilePath }),
    homeDir,
  });
  return result.extensionPath;
}

/**
 * Fail-closed subject assertions (parent blocker): the frozen tarball must
 * contain the Slice 4 seam `dist/runtime/omp-extension-v1.js`, and the packed
 * `dist/runtime/index.js` must wire the Slice 4 probe. A stale pre-Slice-4
 * pack can never become the subject.
 */
export async function assertSubjectTarballSeam(
  tarballPath: string,
): Promise<void> {
  const listing = execFileSync("tar", ["-tzf", tarballPath], {
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
  if (!listing.split("\n").includes("package/dist/runtime/omp-extension-v1.js"))
    throw new Error("SUBJECT_STALE:tarball-missing-omp-extension-v1");
  const indexEntry = "package/dist/runtime/index.js";
  if (!listing.split("\n").includes(indexEntry))
    throw new Error("SUBJECT_STALE:tarball-missing-runtime-index");
  // Extract only the seam index to verify the probe wiring without
  // materializing the whole tarball a second time.
  const indexJs = execFileSync("tar", ["-xzOf", tarballPath, indexEntry], {
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
  });
  if (!indexJs.includes("probeOmpExtensionV1Capabilities"))
    throw new Error("SUBJECT_STALE:runtime-index-missing-slice4-probe");
}

/**
 * Behavioral stale-pack probe: the *installed* (packed) runtime controller
 * must fail closed on a Host that has `registerCommand` + `zod` but no `on`
 * — and must throw before `registerCommand` is ever invoked. A pack that
 * registers anyway is a stale pre-Slice-4 build and the cell blocks with
 * `SUBJECT_STALE:*`. This complements the string-level seam check in
 * `assertSubjectTarballSeam`; the packed `index.js` digest is intentionally
 * not pinned (it churns every build).
 */
export async function assertPackedControllerFailClosed(
  runtimeIndexPath: string,
): Promise<void> {
  let module: Record<string, unknown>;
  try {
    // Dynamic import is required: the specifier is the subject tarball's
    // packed dist/runtime/index.js, installed into a fresh per-run dir and
    // only known at runtime (plugin-loading exception).
    module = (await import(
      pathToFileURL(realpathSync(runtimeIndexPath)).href
    )) as Record<string, unknown>;
  } catch {
    throw new Error("SUBJECT_STALE:packed-runtime-index-unimportable");
  }
  if (typeof module.registerRuntimeController !== "function")
    throw new Error("SUBJECT_STALE:packed-runtime-index-missing-controller");
  let registerCommandCalls = 0;
  const hostWithoutOn = {
    zod: {},
    registerCommand: () => {
      registerCommandCalls += 1;
    },
    // intentionally no `on` event subscription capability
  };
  // Handler surface is never reached when the probe fails closed; a Proxy
  // keeps the call total if a fail-open pack tries to use handlers.
  const handlers = new Proxy(
    {},
    { get: () => async () => undefined },
  ) as unknown;
  let threw = false;
  try {
    (
      module.registerRuntimeController as (
        host: unknown,
        handlers: unknown,
      ) => void
    )(hostWithoutOn, handlers);
  } catch {
    threw = true;
  }
  if (!threw)
    throw new Error("SUBJECT_STALE:packed-controller-fail-open-without-on");
  if (registerCommandCalls > 0)
    throw new Error("SUBJECT_STALE:packed-controller-registered-before-probe");
}

export async function runLiveCell(
  options: LiveCellOptions,
): Promise<LiveCellResult> {
  const runsRoot = options.runsRoot ?? ".tmp/host-event";
  const targetOmpVersion = options.targetOmpVersion ?? "17.3.5";
  const timeoutMs = options.timeoutMs ?? 240_000;
  const runId = `run-${Date.now()}-${randomUUID().slice(0, 8)}`;
  const runDir = join(runsRoot, runId);
  const blocked = (reason: string): LiveCellResult => ({
    outcome: "blocked",
    runId,
    runDir,
    reasonCodes: [],
    diagnostics: [],
    blockedReason: reason,
  });

  let tarballPath: string;
  let pluginTarballSha256: string;
  try {
    tarballPath = realpathSync(resolve(options.pluginTarball));
    pluginTarballSha256 = sha256File(tarballPath);
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
  if (hostIdentity.packageVersion === undefined)
    return blocked("OMP_PACKAGE_IDENTITY_UNAVAILABLE");

  await mkdir(join(runDir, "out"), { recursive: true });
  const agentPluginsDir = join(runDir, "agent", "plugins");
  let pluginExt: string;
  try {
    pluginExt = await installSubjectPlugin(
      agentPluginsDir,
      tarballPath,
      join(runDir, "home"),
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
    // Always the stable code: installer errors embed local paths and must
    // never reach blockedReason.
    return blocked("PLUGIN_INSTALL_FAILED");
  }
  // Behavioral stale-pack proof on the installed bits (string checks on the
  // tarball alone are not sufficient): the packed controller must fail
  // closed on a Host without `on` before touching registerCommand.
  try {
    await assertPackedControllerFailClosed(
      join(dirname(pluginExt), "runtime", "index.js"),
    );
  } catch (error) {
    return blocked(subjectStaleBlockedReason(error));
  }
  const validatorModule = join(
    dirname(pluginExt),
    "runtime",
    "omp-extension-v1.js",
  );
  let pluginValidatorModuleSha256: string;
  try {
    pluginValidatorModuleSha256 = sha256File(realpathSync(validatorModule));
  } catch {
    return blocked("PLUGIN_VALIDATOR_MODULE_MISSING");
  }

  const drivePath = fileURLToPath(new URL("./drive.mjs", import.meta.url));
  const driveResult = await new Promise<DriverSpawnResult>((complete) => {
    let settled = false;
    let timedOut = false;
    const finish = (result: DriverSpawnResult) => {
      if (settled) return;
      settled = true;
      complete(result);
    };
    const driver = spawn(process.execPath, [drivePath], {
      env: {
        PATH: process.env.PATH ?? "",
        HOME: join(runDir, "home"),
        SPIKE_OMP_BIN: ompBin,
        SPIKE_PLUGIN_EXT: pluginExt,
        SPIKE_RUN_DIR: resolve(runDir),
        HOST_EVENT_RUN_ID: runId,
        HOST_EVENT_OBSERVE_EVENTS: JSON.stringify(hostEventObserveEvents()),
        HOST_EVENT_VALIDATOR_MODULE: validatorModule,
      },
      stdio: ["ignore", "pipe", "ignore"],
    });
    driver.stdout.resume();
    const killer = setTimeout(() => {
      timedOut = true;
      try {
        driver.kill("SIGKILL");
      } catch {
        // already gone
      }
    }, timeoutMs);
    driver.once("error", () => {
      clearTimeout(killer);
      finish({ code: null, timedOut: false, spawnFailed: true });
    });
    driver.once("close", (code) => {
      clearTimeout(killer);
      finish({ code, timedOut, spawnFailed: false });
    });
  });
  return completeLiveCellAfterDriver({
    drive: driveResult,
    runId,
    runDir,
    expectation: {
      runId,
      targetOmpVersion,
      hostEntrypointSha256: hostIdentity.entrypointSha256,
      hostPackageJsonSha256: hostIdentity.packageJsonSha256 ?? "",
      hostPackageVersion: hostIdentity.packageVersion,
      pluginValidatorModuleSha256,
      pluginTarballSha256,
    },
  });
}

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
  const pluginTarball = process.env.HOST_EVENT_PLUGIN_TARBALL;
  if (typeof ompBin !== "string" || typeof pluginTarball !== "string") {
    console.error(
      "usage: SPIKE_OMP_BIN=<omp> HOST_EVENT_PLUGIN_TARBALL=<tgz> [HOST_EVENT_RUNS_ROOT=<dir>] tsx run-live-cell.ts",
    );
    process.exit(2);
  }
  const result = await runLiveCell({
    ompBin,
    pluginTarball,
    runsRoot: process.env.HOST_EVENT_RUNS_ROOT,
    targetOmpVersion: process.env.HOST_EVENT_TARGET_VERSION,
    ...(process.env.HOST_EVENT_INSTALLER_LOCK_FILE === undefined
      ? {}
      : { installerLockFile: process.env.HOST_EVENT_INSTALLER_LOCK_FILE }),
    ...(process.env.HOST_EVENT_INSTALLER_CACHE_DIR === undefined
      ? {}
      : { installerCacheDir: process.env.HOST_EVENT_INSTALLER_CACHE_DIR }),
  });
  console.log(JSON.stringify(result, null, 2));
  process.exit(
    result.outcome === "failed" ? 1 : result.outcome === "blocked" ? 2 : 0,
  );
}
