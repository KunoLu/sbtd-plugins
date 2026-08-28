// Slice 7 three-profile certification runner CLI for
// .github/workflows/omp-compatibility-certification.yml.
//
// Commands:
//   admit          Record the immutable identity of a published Plugin
//                  version, byte-verify the live Registry tarball against
//                  it, append the target to the staged catalog, and stage
//                  the verified tarball/manifest under transport/registry/.
//   plan           Plan minimum/latest/new-Runtime cells for the staged
//                  catalog and print the matrix run report. An EMPTY catalog
//                  is blocked (exit 1), never a pass; zero in-range cells
//                  is also exit 1 — the workflow must fail closed.
//   run-cell       Execute one in-range cell in an isolated environment:
//                  provision the exact OMP package (bun install
//                  --ignore-scripts, spawned as dist/cli.js — never the
//                  .bin/omp shim), install the subject ONLY through the
//                  shared npm-offline-v1 installer (install-subject-plugin.ts,
//                  npm ci --offline against the lock-and-cache job's staged
//                  lock+cache — never online, never bun), run the
//                  runtime-capability probe, the four-command surface and
//                  the 12-event Host Event suite, write the three evidence
//                  bundles and the attestation subjects, and emit the cell
//                  assessment draft.
//   finalize-cell  Verify the GitHub artifact attestation bundle against
//                  the draft, stage the attested subject bytes
//                  content-addressed under validation/p0/evidence/<sha256>,
//                  mint the ledger assessment entry with CI provenance, and
//                  append it to the staged ledger.
//   collect        Re-append every finalized cell entry (plus the admission
//                  catalog update) against the committed ledger, re-verify
//                  the merged ledger and emit the committable update
//                  artifact (catalog, ledger, evidence) only when a real
//                  attested update exists.
//
// This command never packs, never publishes, never moves dist-tags, never
// writes outside its stage/runs roots, and never prints "certified": the
// only outcome vocabulary is the derived ledger overallOutcome.
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { ompExtensionV1Inventory } from "../../src/runtime/omp-extension-v1.ts";
import {
  appendLedgerAssessment,
  type CompatibilityEvidenceReader,
  createRepoEvidenceReader,
  parseCompatibilityLedger,
  parseCompatibilityTargets,
  verifyCompatibilityLedgerEvidence,
} from "./compatibility-ledger.ts";
import {
  commandSurfaceRunRecordSchema,
  parseCapabilityProbeLog,
  runCommandSurfaceCell,
  scoreCapabilityProbe,
  scoreCommandSurfaceRecord,
} from "./host-event/run-command-surface-cell.ts";
import { runLiveCell } from "./host-event/run-live-cell.ts";
import { P0ValidationError } from "./release-validator.ts";
import {
  admitPublishedTarget,
  assertCellHostIdentity,
  buildCellAssessmentDraft,
  CERTIFICATION_EVIDENCE_KIND,
  type CertificationEvidenceWrite,
  certificationCellPlanSchema,
  commandSetSubjectDocument,
  extractTarballMemberBytes,
  finalizeCellAssessment,
  hostEventCertificationBundleFromLiveCell,
  hostEventScenarioSetSubjectDocument,
  parseNpmViewJson,
  planCertificationRun,
  serializeCertificationEvidence,
} from "./three-profile-certification.ts";

const pluginRoot = fileURLToPath(new URL("../..", import.meta.url));
const defaultDataRoot = join(pluginRoot, "validation", "p0");
const suiteDir = join(pluginRoot, "scripts", "p0", "host-event");
const commands = new Set([
  "admit",
  "plan",
  "run-cell",
  "finalize-cell",
  "collect",
]);
const REPEATABLE_OPTIONS = new Set(["cell-stage"]);

function parseArguments(argv: readonly string[]): {
  readonly command: string;
  readonly options: Readonly<Record<string, string>>;
} {
  const [command, ...rest] = argv;
  const options: Record<string, string> = {};
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index];
    if (token === undefined || !token.startsWith("--"))
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Unexpected certification runner argument: ${token}`,
        "Use only documented --name value options.",
      );
    const value = rest[index + 1];
    if (value === undefined || value.startsWith("--"))
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Missing value for ${token}`,
        "Supply a value for every certification runner option.",
      );
    const name = token.slice(2);
    if (REPEATABLE_OPTIONS.has(name) && options[name] !== undefined)
      options[name] = `${options[name]}\n${value}`;
    else if (REPEATABLE_OPTIONS.has(name)) options[name] = value;
    else if (options[name] !== undefined)
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Duplicate certification runner option: ${token}`,
        "Pass each option once; only --cell-stage may repeat.",
      );
    else options[name] = value;
    index += 1;
  }
  if (command === undefined || !commands.has(command))
    throw new P0ValidationError(
      "CLI_COMMAND_INVALID",
      "The certification runner command is missing or unsupported.",
      "Use admit, plan, run-cell, finalize-cell or collect.",
    );
  return { command, options };
}

const sha256Hex = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");

async function readJson(path: string): Promise<unknown> {
  let raw: string;
  try {
    raw = await readFile(path, "utf8");
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_DATA_MISSING",
      `The compatibility data file ${path} is unreadable.`,
      "Restore the versioned validation/p0 compatibility data files.",
    );
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new P0ValidationError(
      "JSON_INVALID",
      `The compatibility data file ${path} is not valid JSON.`,
      "Regenerate the versioned validation asset from its source of truth.",
    );
  }
}

async function readJsonIfExists(path: string): Promise<unknown> {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return undefined;
  }
}

async function writeJson(path: string, value: unknown): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
}

// ---------------------------------------------------------------------------
// Stage layout (artifact content mirrors the repo so evidence locators
// resolve through createRepoEvidenceReader(stageRoot)).
// ---------------------------------------------------------------------------

const mirrorP0 = (stageRoot: string): string =>
  join(stageRoot, "plugins", "omp-sbtd", "validation", "p0");
const mirrorEvidence = (stageRoot: string): string =>
  join(mirrorP0(stageRoot), "evidence");
const transport = (stageRoot: string): string => join(stageRoot, "transport");

async function loadStagedOrCommitted(
  stageRoot: string | undefined,
  dataRoot: string,
  file: string,
): Promise<unknown> {
  if (stageRoot !== undefined) {
    const staged = await readJsonIfExists(join(mirrorP0(stageRoot), file));
    if (staged !== undefined) return staged;
  }
  return readJson(join(dataRoot, file));
}

// Evidence overlay for certification stage roots, the byte-level twin of
// loadStagedOrCommitted: staged bytes win, and a locator the stage does not
// carry (a historical committed attestation bundle or profile evidence file
// referenced by an earlier ledger entry, e.g. the entry committed before the
// current cell ran) falls through to the committed repository that dataRoot
// belongs to. The ledger validator digest-verifies every read, so the
// committed fallback can never smuggle drifted bytes past a staged twin. A
// locator escaping the stage root fails closed immediately; one missing from
// BOTH roots surfaces as COMPATIBILITY_ATTESTATION_MISSING /
// COMPATIBILITY_EVIDENCE_MISSING from the committed read.
const createStageEvidenceReader = (
  stageRoot: string,
  dataRoot: string,
): CompatibilityEvidenceReader => {
  const staged = createRepoEvidenceReader(stageRoot);
  const committed = createRepoEvidenceReader(
    resolve(dataRoot, "..", "..", "..", ".."),
  );
  return {
    readBytes: async (locator) => {
      try {
        return await staged.readBytes(locator);
      } catch (error) {
        if (error instanceof P0ValidationError) throw error;
        return committed.readBytes(locator);
      }
    },
  };
};

// ---------------------------------------------------------------------------
// Registry I/O (the only network surface; everything downstream is pure)
// ---------------------------------------------------------------------------

function npmView(
  spec: string,
  fields: readonly string[],
): Readonly<Record<string, unknown>> {
  let raw: string;
  try {
    raw = execFileSync("npm", ["view", spec, ...fields, "--json"], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
      env: { PATH: process.env.PATH ?? "" },
    });
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      `npm view failed for ${spec}.`,
      "Registry admission needs the live Registry metadata for the exact published version; retry when the Registry is reachable.",
    );
  }
  return parseNpmViewJson(raw, spec, fields);
}

async function fetchBytes(url: string): Promise<Uint8Array> {
  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      "The Registry tarball could not be fetched.",
      "Retry when the Registry is reachable; admission never falls back to a local build.",
    );
  }
  if (!response.ok)
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      `The Registry tarball fetch returned HTTP ${response.status}.`,
      "Retry when the Registry is reachable; admission never falls back to a local build.",
    );
  return new Uint8Array(await response.arrayBuffer());
}

// ---------------------------------------------------------------------------
// Shared pieces
// ---------------------------------------------------------------------------

type ProfileOutcome =
  | "passed"
  | "passed-with-diagnostics"
  | "failed"
  | "blocked"
  | "missing";

interface CellProfilePlumbing {
  readonly outcome: ProfileOutcome;
  readonly blockedReason?: string;
  readonly evidence?: CertificationEvidenceWrite & { readonly bundle: unknown };
}

function requireOption(
  options: Readonly<Record<string, string>>,
  name: string,
): string {
  const value = options[name];
  if (value === undefined || value.length === 0)
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      `The certification runner requires --${name}.`,
      "Supply every documented option for the chosen command.",
    );
  return value;
}

function requireGithubEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0)
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      `The ${name} environment variable is required.`,
      "The certification runner mints gha:<run>:<attempt> attempt ids and provenance only inside the trusted GitHub workflow.",
    );
  return value;
}

function githubAttemptId(): string {
  const runId = requireGithubEnv("GITHUB_RUN_ID");
  const attempt = requireGithubEnv("GITHUB_RUN_ATTEMPT");
  if (!/^\d+$/.test(runId) || !/^\d+$/.test(attempt))
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT must be numeric.",
      "The certification runner mints gha:<run>:<attempt> attempt ids only inside the trusted GitHub workflow.",
    );
  return `gha:${runId}:${attempt}`;
}

/** Content-addressed evidence write: identical rewrites are idempotent,
 *  conflicting bytes at the same digest are a hard failure. */
async function stageEvidenceFile(
  stageRoot: string,
  written: CertificationEvidenceWrite,
): Promise<void> {
  const dir = mirrorEvidence(stageRoot);
  await mkdir(dir, { recursive: true });
  const path = join(dir, `${written.sha256}.json`);
  const existing = await readFile(path).catch(() => undefined);
  if (existing !== undefined) {
    if (!existing.equals(Buffer.from(written.bytes)))
      throw new P0ValidationError(
        "COMPATIBILITY_EVIDENCE_CONFLICT",
        "An evidence file with the same content address but different bytes already exists.",
        "Evidence is content-addressed and immutable; investigate the conflicting writer before retrying.",
      );
    return;
  }
  await writeFile(path, written.bytes, { mode: 0o600 });
}

/** Attested-subject blob write: raw bytes at the UNSUFFIXED content address
 *  `<sha256>` so the ledger validator can cryptographically verify the exact
 *  subject files against the committed bundle. Profile evidence already
 *  staged at `<sha256>.json` carries the identical bytes and is reused
 *  instead of duplicated; any other content at the same address is a hard
 *  failure. */
async function stageSubjectBlob(
  stageRoot: string,
  bytes: Uint8Array,
): Promise<string> {
  const dir = mirrorEvidence(stageRoot);
  await mkdir(dir, { recursive: true });
  const digest = sha256Hex(bytes);
  const reused = await readFile(join(dir, `${digest}.json`)).catch(
    () => undefined,
  );
  if (reused?.equals(Buffer.from(bytes))) return digest;
  const path = join(dir, digest);
  const existing = await readFile(path).catch(() => undefined);
  if (existing !== undefined) {
    if (!existing.equals(Buffer.from(bytes)))
      throw new P0ValidationError(
        "COMPATIBILITY_EVIDENCE_CONFLICT",
        "An attested subject blob with the same content address but different bytes already exists.",
        "Evidence is content-addressed and immutable; investigate the conflicting writer before retrying.",
      );
    return digest;
  }
  await writeFile(path, bytes, { mode: 0o600 });
  return digest;
}

async function provisionCellOmpRuntime(
  stageDir: string,
  homeDir: string,
  ompVersion: string,
): Promise<string> {
  // Era guard: this provisioner still spawns bun, and OMP 18 no longer uses
  // bun. This slice must never claim 18 compatibility — an 18+ (or
  // unparsable) target major fails closed here instead of provisioning a
  // wrong-artifact Host. The non-bun Host provisioner is a separate slice.
  const major = Number.parseInt(ompVersion.split(".")[0] ?? "", 10);
  if (!Number.isInteger(major) || major >= 18)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_RUNTIME_UNSUPPORTED_MAJOR",
      `The bun-based Host provisioner cannot provision OMP ${ompVersion}.`,
      "OMP 18 dropped bun; certifying an 18+ Host requires the new non-bun provisioner contract, which is a separate slice. Keep the cell out-of-range until then.",
    );
  await mkdir(stageDir, { recursive: true, mode: 0o700 });
  await writeFile(
    join(stageDir, "package.json"),
    `${JSON.stringify(
      {
        name: "omp-certification-cell-runtime",
        private: true,
        dependencies: { "@oh-my-pi/pi-coding-agent": ompVersion },
      },
      null,
      2,
    )}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
  const exitCode = await new Promise<number | null>((complete) => {
    const installer = spawn("bun", ["install", "--ignore-scripts"], {
      cwd: stageDir,
      env: { PATH: process.env.PATH ?? "", HOME: homeDir },
      shell: false,
      stdio: "ignore",
    });
    installer.once("error", () => complete(null));
    installer.once("close", complete);
  });
  if (exitCode !== 0)
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_RUNTIME_UNAVAILABLE",
      `The isolated OMP ${ompVersion} runtime could not be provisioned.`,
      "The cell needs an exact Registry install of @oh-my-pi/pi-coding-agent; retry when the Registry is reachable.",
    );
  return join(
    stageDir,
    "node_modules",
    "@oh-my-pi",
    "pi-coding-agent",
    "dist",
    "cli.js",
  );
}

// ---------------------------------------------------------------------------
// admit
// ---------------------------------------------------------------------------

async function runAdmit(
  options: Readonly<Record<string, string>>,
): Promise<unknown> {
  const stageRoot = resolve(requireOption(options, "stage-root"));
  const dataRoot = resolve(options["data-root"] ?? defaultDataRoot);
  const pluginVersion = requireOption(options, "plugin-version");
  await mkdir(mirrorEvidence(stageRoot), { recursive: true });
  await mkdir(transport(stageRoot), { recursive: true });
  const catalog = await loadStagedOrCommitted(
    stageRoot,
    dataRoot,
    "compatibility-targets.v1.json",
  );
  const result = await admitPublishedTarget({
    catalog,
    pluginVersion,
    fetch: async () => {
      const metadata = npmView(`@kunolu/omp-sbtd@${pluginVersion}`, [
        "version",
        "dist.integrity",
        "dist.tarball",
      ]);
      const registryVersion = metadata.version;
      const registryDistIntegrity = metadata["dist.integrity"];
      const registryTarballUrl = metadata["dist.tarball"];
      if (
        typeof registryVersion !== "string" ||
        typeof registryDistIntegrity !== "string" ||
        typeof registryTarballUrl !== "string"
      )
        throw new P0ValidationError(
          "COMPATIBILITY_ADMISSION_UNAVAILABLE",
          "The Registry metadata lacks version, dist.integrity or dist.tarball.",
          "Registry admission needs the live Registry metadata for the exact published version; retry when the Registry is reachable.",
        );
      const tarballBytes = await fetchBytes(registryTarballUrl);
      return {
        registryVersion,
        registryDistIntegrity,
        registryTarballUrl,
        tarballBytes,
      };
    },
  });
  await writeJson(
    join(mirrorP0(stageRoot), "compatibility-targets.v1.json"),
    result.targets,
  );
  const registryStage = join(transport(stageRoot), "registry", pluginVersion);
  await mkdir(registryStage, { recursive: true });
  await writeFile(
    join(registryStage, "plugin.tgz"),
    result.fetched.tarballBytes,
    {
      mode: 0o600,
    },
  );
  const manifestBytes = extractTarballMemberBytes(
    result.fetched.tarballBytes,
    "package/package.json",
  );
  if (manifestBytes === undefined)
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      "The verified Registry tarball lacks package/package.json.",
      "Admission requires the tarball manifest; a tarball that passed verification always contains it.",
    );
  await writeFile(join(registryStage, "package.json"), manifestBytes, {
    mode: 0o600,
  });
  await writeJson(join(transport(stageRoot), "admission.json"), {
    kind: "compatibility-admission",
    pluginVersion,
    outcome: result.outcome,
    entry: result.entry,
  });
  return {
    kind: "compatibility-admission",
    status: "passed",
    outcome: result.outcome,
    entry: result.entry,
  };
}

// ---------------------------------------------------------------------------
// plan
// ---------------------------------------------------------------------------

async function runPlan(
  options: Readonly<Record<string, string>>,
): Promise<{ readonly report: unknown; readonly exit: number }> {
  const stageRoot =
    options["stage-root"] === undefined
      ? undefined
      : resolve(options["stage-root"]);
  const dataRoot = resolve(options["data-root"] ?? defaultDataRoot);
  const catalog = await loadStagedOrCommitted(
    stageRoot,
    dataRoot,
    "compatibility-targets.v1.json",
  );
  const planned = planCertificationRun(catalog, {
    minimumRuntime: requireOption(options, "minimum"),
    latestInRangeRuntime: requireOption(options, "latest"),
    ...(options["new-runtime"] === undefined
      ? {}
      : { newRuntime: options["new-runtime"] }),
  });
  if (options["cells-out"] !== undefined)
    await writeJson(resolve(options["cells-out"]), planned.cellsToRun);
  // An empty/unavailable matrix is blocked (never a pass), and a non-empty
  // catalog with zero in-range cells also fails closed: nothing would run,
  // so the workflow must not continue to certify/collect.
  const exit =
    planned.report.status === "blocked" || planned.cellsToRun.length === 0
      ? 1
      : 0;
  return { report: planned.report, exit };
}

// ---------------------------------------------------------------------------
// run-cell
// ---------------------------------------------------------------------------

async function runCell(
  options: Readonly<Record<string, string>>,
): Promise<unknown> {
  const stageRoot = resolve(requireOption(options, "stage-root"));
  const dataRoot = resolve(options["data-root"] ?? defaultDataRoot);
  const runsRoot = resolve(
    options["runs-root"] ?? (await mkdtemp(join(tmpdir(), "omp-cert-cell-"))),
  );
  const attemptId = githubAttemptId();
  const cell = certificationCellPlanSchema.parse(
    JSON.parse(requireOption(options, "cell")),
  );
  const cellKey = `${cell.pluginTarballSha256.slice(0, 12)}-omp-${cell.ompVersion}`;
  const cellTransport = join(transport(stageRoot), "cells", cellKey);
  const subjectsDir = join(cellTransport, "subjects");
  await rm(cellTransport, { recursive: true, force: true });
  await mkdir(subjectsDir, { recursive: true });
  await mkdir(mirrorEvidence(stageRoot), { recursive: true });

  // 1. Bind the cell to the staged catalog target (identity equality).
  const catalog = parseCompatibilityTargets(
    await loadStagedOrCommitted(
      stageRoot,
      dataRoot,
      "compatibility-targets.v1.json",
    ),
  );
  const target = catalog.targets.find(
    (entry) => entry.pluginTarballSha256 === cell.pluginTarballSha256,
  );
  if (
    target === undefined ||
    target.pluginVersion !== cell.pluginVersion ||
    target.pluginPeerRange !== cell.pluginPeerRange
  )
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_IDENTITY_MISMATCH",
      "The matrix cell does not equal a staged published target identity.",
      "Run prepare/admit for this exact published version first; cells never admit new identities.",
    );

  // 2. The staged subject tarball/manifest must byte-match the target.
  const registryStage = join(
    transport(stageRoot),
    "registry",
    cell.pluginVersion,
  );
  const tarballPath = join(registryStage, "plugin.tgz");
  const manifestPath = join(registryStage, "package.json");
  let tarballBytes: Buffer;
  let manifestBytes: Buffer;
  try {
    tarballBytes = await readFile(tarballPath);
    manifestBytes = await readFile(manifestPath);
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_UNAVAILABLE",
      "The admission-staged subject tarball or manifest is missing.",
      "Run the prepare job's admission step first; certification cells only use Registry-verified staged subjects.",
    );
  }
  if (
    sha256Hex(tarballBytes) !== target.pluginTarballSha256 ||
    sha256Hex(manifestBytes) !== target.pluginManifestSha256
  )
    throw new P0ValidationError(
      "COMPATIBILITY_ADMISSION_MISMATCH",
      "The staged subject tarball or manifest digest differs from the published target identity.",
      "Fail closed: re-stage the subject from the verified Registry admission; never substitute a workspace pack.",
    );

  // 2b. The npm-offline-v1 lock+cache for this exact subject digest (staged
  // by the certification lock-and-cache job) must be present. Cells install
  // the subject ONLY with `npm ci --offline` — never online, never bun — so
  // a missing handoff fails closed before any Host spawns.
  const installerStage = join(
    transport(stageRoot),
    "installer",
    cell.pluginTarballSha256,
  );
  const installerLockFile = join(installerStage, "package-lock.json");
  const installerCacheDir = join(installerStage, "cache");
  try {
    await readFile(installerLockFile);
    await readdir(installerCacheDir);
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_INSTALLER_UNAVAILABLE",
      "The npm-offline-v1 lock and cache for the cell subject digest are not staged.",
      "Run the certification lock-and-cache job for this exact pluginTarballSha256 first; cells only install the subject with npm ci --offline.",
    );
  }

  // 3. Provision the cell's exact OMP Runtime and bind its loaded identity.
  const ompHome = join(runsRoot, "omp-home");
  const ompBin = await provisionCellOmpRuntime(
    join(runsRoot, "omp-runtime"),
    ompHome,
    cell.ompVersion,
  );
  const host = assertCellHostIdentity(ompBin, cell.ompVersion);
  const ompMetadata = npmView(`@oh-my-pi/pi-coding-agent@${cell.ompVersion}`, [
    "dist.integrity",
  ]);
  const ompRegistryIntegrity = ompMetadata["dist.integrity"];
  if (typeof ompRegistryIntegrity !== "string")
    throw new P0ValidationError(
      "COMPATIBILITY_CELL_RUNTIME_UNAVAILABLE",
      "The Registry dist.integrity for the cell's OMP version is unavailable.",
      "The cell needs the exact Registry integrity; retry when the Registry is reachable.",
    );

  // 4. Subject documents.
  const policy = z
    .object({ commands: z.array(z.string()).min(1) })
    .passthrough()
    .parse(await readJson(join(dataRoot, "compatibility.v2.json")));
  const commandSet = commandSetSubjectDocument(policy.commands);
  const scenarioSet = hostEventScenarioSetSubjectDocument({
    driverSha256: sha256Hex(await readFile(join(suiteDir, "drive.mjs"))),
    observerSha256: sha256Hex(await readFile(join(suiteDir, "observer.mjs"))),
    events: [
      ...ompExtensionV1Inventory.requiredEvents,
      ...ompExtensionV1Inventory.optionalEvents,
    ],
  });

  // 5. Runtime-capability probe + command surface (one isolated Host).
  const profiles: Record<string, CellProfilePlumbing> = {};
  const surface = await runCommandSurfaceCell({
    ompBin,
    pluginTarball: tarballPath,
    runDir: join(runsRoot, "command-surface"),
    runId: attemptId,
    targetOmpVersion: cell.ompVersion,
    installerLockFile,
    installerCacheDir,
  });
  if (surface.status === "blocked") {
    profiles.runtimeCapabilityProbe = {
      outcome: "blocked",
      blockedReason: surface.blockedReason ?? "BLOCKED",
    };
    profiles.commandSurface = {
      outcome: "blocked",
      blockedReason: surface.blockedReason ?? "BLOCKED",
    };
  } else {
    const recordRaw: unknown = JSON.parse(
      await readFile(surface.recordPath ?? "", "utf8"),
    );
    const record = commandSurfaceRunRecordSchema.parse(recordRaw);
    const probeLog = parseCapabilityProbeLog(
      await readFile(surface.probeLogPath ?? "", "utf8"),
      attemptId,
    );
    const capabilityScore = scoreCapabilityProbe({
      log: probeLog,
      pluginRegistered: record.sbtdCommandRegistered,
      expectedHost: host,
    });
    const commandScore = scoreCommandSurfaceRecord(recordRaw, {
      runId: attemptId,
      pluginTarballSha256: target.pluginTarballSha256,
      expectedHost: host,
    });
    const capabilityBundle = {
      schemaVersion: 1,
      profile: "omp-runtime-capabilities-v1",
      evidenceKind: CERTIFICATION_EVIDENCE_KIND,
      runId: attemptId,
      pluginTarballSha256: target.pluginTarballSha256,
      ompVersion: cell.ompVersion,
      ompArtifact: {
        entrypointSha256: host.entrypointSha256,
        packageJsonSha256: host.packageJsonSha256,
      },
      inventoryVersion: "omp-extension-v1",
      capabilities: capabilityScore.capabilities,
      pluginRegistered: capabilityScore.pluginRegistered,
      missingRequired: [...capabilityScore.missingRequired],
      missingOptional: [...capabilityScore.missingOptional],
      outcome: capabilityScore.outcome,
    } as const;
    const commandBundle = {
      schemaVersion: 1,
      profile: "omp-command-surface-v1",
      evidenceKind: CERTIFICATION_EVIDENCE_KIND,
      runId: attemptId,
      pluginTarballSha256: target.pluginTarballSha256,
      ompVersion: cell.ompVersion,
      ompArtifact: {
        entrypointSha256: host.entrypointSha256,
        packageJsonSha256: host.packageJsonSha256,
      },
      commandSetSha256: commandSet.sha256,
      commands: commandScore.commands.map((entry) => ({ ...entry })),
      outcome: commandScore.outcome,
    } as const;
    const capabilityEvidence = {
      ...serializeCertificationEvidence(capabilityBundle),
      bundle: capabilityBundle,
    };
    const commandEvidence = {
      ...serializeCertificationEvidence(commandBundle),
      bundle: commandBundle,
    };
    await stageEvidenceFile(stageRoot, capabilityEvidence);
    await stageEvidenceFile(stageRoot, commandEvidence);
    profiles.runtimeCapabilityProbe = {
      outcome: capabilityScore.outcome,
      evidence: capabilityEvidence,
    };
    profiles.commandSurface = {
      outcome: commandScore.outcome,
      evidence: commandEvidence,
    };
  }

  // 6. Host Event suite (separate isolated Host).
  const live = await runLiveCell({
    ompBin,
    pluginTarball: tarballPath,
    runsRoot: join(runsRoot, "host-event"),
    targetOmpVersion: cell.ompVersion,
    installerLockFile,
    installerCacheDir,
  });
  if (live.outcome === "blocked" || live.bundle === undefined) {
    profiles.hostEventSurface = {
      outcome: "blocked",
      blockedReason: live.blockedReason ?? "BLOCKED",
    };
  } else {
    const hostEventBundle = hostEventCertificationBundleFromLiveCell(
      live.bundle,
      { runId: attemptId, hostEventScenarioSetSha256: scenarioSet.sha256 },
    );
    const hostEventEvidence = {
      ...serializeCertificationEvidence(hostEventBundle),
      bundle: hostEventBundle,
    };
    await stageEvidenceFile(stageRoot, hostEventEvidence);
    profiles.hostEventSurface = {
      outcome: live.outcome,
      evidence: hostEventEvidence,
    };
  }

  // 7. Successor chain link from the existing ledger.
  const ledger = parseCompatibilityLedger(
    await loadStagedOrCommitted(
      stageRoot,
      dataRoot,
      "compatibility-ledger.v1.json",
    ),
  );
  const predecessors = ledger.entries.filter(
    (entry) =>
      entry.pluginTarballSha256 === target.pluginTarballSha256 &&
      entry.ompVersion === cell.ompVersion,
  );

  // 8. Draft + attestation subjects.
  const draft = buildCellAssessmentDraft({
    attemptId,
    target,
    ompVersion: cell.ompVersion,
    ompRegistryIntegrity,
    host,
    commandSetSha256: commandSet.sha256,
    hostEventScenarioSetSha256: scenarioSet.sha256,
    previousEntrySha256: predecessors.at(-1)?.entrySha256 ?? null,
    profiles: {
      runtimeCapabilityProbe: profiles.runtimeCapabilityProbe ?? {
        outcome: "missing",
      },
      commandSurface: profiles.commandSurface ?? { outcome: "missing" },
      hostEventSurface: profiles.hostEventSurface ?? { outcome: "missing" },
    },
  });
  await writeJson(join(cellTransport, "draft.json"), draft);
  await writeFile(join(subjectsDir, "plugin.tarball.tgz"), tarballBytes, {
    mode: 0o600,
  });
  await writeFile(join(subjectsDir, "plugin.manifest.json"), manifestBytes, {
    mode: 0o600,
  });
  await copyFile(ompBin, join(subjectsDir, "omp-artifact.js"));
  await writeFile(join(subjectsDir, "command-set.json"), commandSet.bytes, {
    mode: 0o600,
  });
  await writeFile(
    join(subjectsDir, "host-event-scenario-set.json"),
    scenarioSet.bytes,
    { mode: 0o600 },
  );
  for (const key of [
    "runtimeCapabilityProbe",
    "commandSurface",
    "hostEventSurface",
  ] as const) {
    const evidence = profiles[key]?.evidence;
    if (evidence === undefined) continue;
    const profileName =
      key === "runtimeCapabilityProbe"
        ? "omp-runtime-capabilities-v1"
        : key === "commandSurface"
          ? "omp-command-surface-v1"
          : "omp-host-events-v1";
    await writeFile(
      join(subjectsDir, `evidence-${profileName}.json`),
      evidence.bytes,
      { mode: 0o600 },
    );
  }
  const runReport = {
    kind: "compatibility-cell-run",
    cell: { ...cell },
    attemptId,
    profiles: Object.fromEntries(
      Object.entries(profiles).map(([key, value]) => [
        key,
        {
          outcome: value.outcome,
          ...(value.blockedReason === undefined
            ? {}
            : { blockedReason: value.blockedReason }),
        },
      ]),
    ),
  };
  await writeJson(join(cellTransport, "run.json"), runReport);
  return runReport;
}

// ---------------------------------------------------------------------------
// finalize-cell
// ---------------------------------------------------------------------------

async function runFinalizeCell(
  options: Readonly<Record<string, string>>,
): Promise<unknown> {
  const stageRoot = resolve(requireOption(options, "stage-root"));
  const dataRoot = resolve(options["data-root"] ?? defaultDataRoot);
  const cell = certificationCellPlanSchema.parse(
    JSON.parse(requireOption(options, "cell")),
  );
  const cellKey = `${cell.pluginTarballSha256.slice(0, 12)}-omp-${cell.ompVersion}`;
  const cellTransport = join(transport(stageRoot), "cells", cellKey);
  const draft = await readJson(join(cellTransport, "draft.json"));
  const attestationBundleBytes = new Uint8Array(
    await readFile(resolve(requireOption(options, "bundle"))),
  );
  const entry = finalizeCellAssessment({
    draft,
    attestationBundleBytes,
    provenance: {
      issuer: "https://token.actions.githubusercontent.com",
      repository: requireGithubEnv("GITHUB_REPOSITORY"),
      workflowRef: requireGithubEnv("GITHUB_WORKFLOW_REF"),
      eventName: requireGithubEnv("GITHUB_EVENT_NAME"),
      runId: requireGithubEnv("GITHUB_RUN_ID"),
      sourceRef: requireGithubEnv("GITHUB_REF"),
      sourceRevision: requireGithubEnv("GITHUB_SHA"),
    },
  });
  await stageEvidenceFile(stageRoot, {
    locator: entry.provenance.attestationBundleLocator,
    sha256: entry.provenance.attestationBundleSha256,
    bytes: attestationBundleBytes,
  });
  // Stage the attested SUBJECT bytes content-addressed: the ledger validator
  // cryptographically verifies these files against the committed bundle,
  // never the bundle JSON itself. finalizeCellAssessment already bound the
  // entry's subjectDigests to the bundle's in-toto subjects, so the staged
  // file digest multiset must equal it exactly — a missing, extra or drifted
  // subject file fails closed here instead of surfacing as a validator 404.
  const subjectsDir = join(cellTransport, "subjects");
  const subjectNames = await readdir(subjectsDir).catch(() => undefined);
  if (subjectNames === undefined || subjectNames.length === 0)
    throw new P0ValidationError(
      "COMPATIBILITY_ATTESTATION_MISSING",
      "The attested subject files are missing from the cell stage.",
      "Run the cell step first; finalize only stages the exact subject files the trusted workflow attested.",
    );
  const stagedDigests: string[] = [];
  for (const name of subjectNames)
    stagedDigests.push(
      await stageSubjectBlob(
        stageRoot,
        await readFile(join(subjectsDir, name)),
      ),
    );
  stagedDigests.sort();
  const expectedDigests = Object.values(entry.provenance.subjectDigests)
    .filter((value): value is string => value !== undefined)
    .sort();
  if (
    stagedDigests.length !== expectedDigests.length ||
    stagedDigests.some((digest, index) => digest !== expectedDigests[index])
  )
    throw new P0ValidationError(
      "COMPATIBILITY_ATTESTATION_UNVERIFIED",
      "The staged subject files do not equal the attested subject digests.",
      "Re-run the cell and attestation over one unchanged subject set; never hand-place subject files.",
      { stagedDigests, expectedDigests },
    );
  const [catalog, trustPolicy, ledgerDocument] = await Promise.all([
    loadStagedOrCommitted(stageRoot, dataRoot, "compatibility-targets.v1.json"),
    loadStagedOrCommitted(
      stageRoot,
      dataRoot,
      "compatibility-trust-policy.v1.json",
    ),
    loadStagedOrCommitted(stageRoot, dataRoot, "compatibility-ledger.v1.json"),
  ]);
  const result = await appendLedgerAssessment(
    ledgerDocument,
    catalog,
    trustPolicy,
    entry,
    createStageEvidenceReader(stageRoot, dataRoot),
  );
  await writeJson(
    join(mirrorP0(stageRoot), "compatibility-ledger.v1.json"),
    result.ledger,
  );
  await writeJson(join(cellTransport, "final.json"), {
    kind: "compatibility-cell-final",
    outcome: result.outcome,
    entry,
  });
  return {
    kind: "compatibility-cell-final",
    status: "passed",
    outcome: result.outcome,
    entrySha256: result.entrySha256,
    overallOutcome: entry.overallOutcome,
  };
}

// ---------------------------------------------------------------------------
// collect
// ---------------------------------------------------------------------------

async function runCollect(
  options: Readonly<Record<string, string>>,
): Promise<unknown> {
  const dataRoot = resolve(options["data-root"] ?? defaultDataRoot);
  const outStage = resolve(requireOption(options, "out"));
  const admissionStage =
    options["admission-stage"] === undefined
      ? undefined
      : resolve(options["admission-stage"]);
  const cellStages = (options["cell-stage"] ?? "")
    .split("\n")
    .map((value) => value.trim())
    .filter((value) => value.length > 0)
    .map((value) => resolve(value));
  if (admissionStage === undefined && cellStages.length === 0)
    throw new P0ValidationError(
      "COMPATIBILITY_COLLECT_EMPTY",
      "Collect received no admission stage and no cell stages; nothing attested exists to merge.",
      "Fail closed: the workflow must not produce a ledger update when no certification cell ran.",
    );
  await rm(outStage, { recursive: true, force: true });
  await mkdir(mirrorEvidence(outStage), { recursive: true });
  // outStage only receives THIS run's staged evidence; earlier ledger entries
  // reference historical committed bundles, so evidence reads must overlay
  // the committed repository beneath the out-stage mirror.
  const evidenceReader = createStageEvidenceReader(outStage, dataRoot);

  // Catalog: admission-stage mirror when present (it already embeds the
  // append), else the committed catalog.
  const catalog = await loadStagedOrCommitted(
    admissionStage,
    dataRoot,
    "compatibility-targets.v1.json",
  );
  const admission = admissionStage
    ? ((await readJsonIfExists(
        join(transport(admissionStage), "admission.json"),
      )) as { outcome?: string } | undefined)
    : undefined;
  const catalogChanged = admission?.outcome === "appended";
  await writeJson(
    join(mirrorP0(outStage), "compatibility-targets.v1.json"),
    catalog,
  );
  const trustPolicy = await readJson(
    join(dataRoot, "compatibility-trust-policy.v1.json"),
  );
  let ledgerDocument: unknown = await readJson(
    join(dataRoot, "compatibility-ledger.v1.json"),
  );

  const appended: string[] = [];
  const duplicates: string[] = [];
  for (const cellStage of cellStages) {
    const cellsDir = join(transport(cellStage), "cells");
    const cellDirs = await readdir(cellsDir).catch(() => [] as string[]);
    for (const cellDir of cellDirs) {
      const finalRaw = (await readJsonIfExists(
        join(cellsDir, cellDir, "final.json"),
      )) as { entry?: unknown } | undefined;
      if (finalRaw?.entry === undefined) continue;
      // Copy EVERY evidence file this cell staged (content-addressed bundles,
      // profile evidence and the unsuffixed attested-subject blobs), not only
      // locator-referenced basenames: subject blobs carry no locator, but the
      // ledger validator needs their bytes to cryptographically verify each
      // new bundle's attested subjects.
      const cellEvidenceDir = mirrorEvidence(cellStage);
      const cellEvidenceFiles = await readdir(cellEvidenceDir).catch(
        () => [] as string[],
      );
      for (const file of cellEvidenceFiles) {
        const source = join(cellEvidenceDir, file);
        const target = join(mirrorEvidence(outStage), file);
        const bytes = await readFile(source);
        const existing = await readFile(target).catch(() => undefined);
        if (existing !== undefined) {
          if (!existing.equals(bytes))
            throw new P0ValidationError(
              "COMPATIBILITY_EVIDENCE_CONFLICT",
              "Two cell stages carry different bytes at the same evidence content address.",
              "Evidence is content-addressed and immutable; investigate the conflicting cell stage before retrying.",
            );
          continue;
        }
        await writeFile(target, bytes, { mode: 0o600 });
      }
      const result = await appendLedgerAssessment(
        ledgerDocument,
        catalog,
        trustPolicy,
        finalRaw.entry,
        evidenceReader,
      );
      ledgerDocument = result.ledger;
      if (result.outcome === "appended") appended.push(result.entrySha256);
      else duplicates.push(result.entrySha256);
    }
  }
  const ledgerChanged = appended.length > 0;
  const updateChanged = ledgerChanged || catalogChanged;
  if (updateChanged) {
    // Final belt-and-braces verification of the merged state, then emit the
    // committable update artifact (catalog + ledger + evidence only).
    await verifyCompatibilityLedgerEvidence(
      ledgerDocument,
      trustPolicy,
      evidenceReader,
    );
    await writeJson(
      join(mirrorP0(outStage), "compatibility-ledger.v1.json"),
      ledgerDocument,
    );
    const updateDir = join(outStage, "ledger-update");
    await mkdir(updateDir, { recursive: true });
    await copyFile(
      join(mirrorP0(outStage), "compatibility-targets.v1.json"),
      join(updateDir, "compatibility-targets.v1.json"),
    );
    await copyFile(
      join(mirrorP0(outStage), "compatibility-ledger.v1.json"),
      join(updateDir, "compatibility-ledger.v1.json"),
    );
    const evidenceFiles = await readdir(mirrorEvidence(outStage));
    if (evidenceFiles.length > 0) {
      await mkdir(join(updateDir, "evidence"), { recursive: true });
      for (const file of evidenceFiles)
        await copyFile(
          join(mirrorEvidence(outStage), file),
          join(updateDir, "evidence", file),
        );
    }
  }
  return {
    kind: "compatibility-collect",
    status: "passed",
    ledgerChanged: updateChanged,
    catalogChanged,
    appended,
    duplicates,
  };
}

// ---------------------------------------------------------------------------
// Entry
// ---------------------------------------------------------------------------

try {
  const parsed = parseArguments(process.argv.slice(2));
  if (parsed.command === "plan") {
    const result = await runPlan(parsed.options);
    process.stdout.write(`${JSON.stringify(result.report)}\n`);
    if (result.exit !== 0) process.exitCode = 1;
  } else {
    const result =
      parsed.command === "admit"
        ? await runAdmit(parsed.options)
        : parsed.command === "run-cell"
          ? await runCell(parsed.options)
          : parsed.command === "finalize-cell"
            ? await runFinalizeCell(parsed.options)
            : await runCollect(parsed.options);
    process.stdout.write(`${JSON.stringify(result)}\n`);
  }
} catch (error) {
  if (process.env.OMP_CERT_DEBUG === "1") console.error(error);
  const normalized =
    error instanceof P0ValidationError
      ? {
          code: error.code,
          message: error.message,
          recovery: error.recovery,
          details: error.details,
        }
      : {
          code: "COMPATIBILITY_RUNNER_UNEXPECTED_FAILURE",
          message:
            "The certification runner stopped before producing a safe result.",
          recovery:
            "Inspect the local output and correct the deterministic validation input.",
        };
  process.stderr.write(`${JSON.stringify(normalized)}\n`);
  process.exitCode = 1;
}
