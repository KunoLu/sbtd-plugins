// npm-offline-v1 subject Plugin installer — the single versioned installer
// contract shared by the trusted §4 publish gate and the compatibility
// certification cells
// (docs/assets/omp-plugin-cloud-section4-and-certification-plan.md §5).
//
// Contract:
// 1. stageSubjectLayout places the subject tarball at the fixed relative
//    path `$runDir/plugin.tgz` and writes a diagnostic package.json whose
//    only dependency is `"@kunolu/omp-sbtd": "file:./plugin.tgz"`. Absolute
//    paths never enter the layout, so the generated lock is portable across
//    jobs and pipelines.
// 2. generateLockAndCache (network allowed, trusted lock-generation jobs
//    only) lets NPM generate the diagnostic package-lock.json — the tarball
//    entry's `integrity` is an npm-written SRI (`sha512-…`), never a
//    hand-written content SHA-256 — and materializes a content-addressed
//    npm cache by running a real `npm ci` against that lock. The tarball
//    content SHA-256 is recorded separately as `pluginTarballSha256`,
//    outside the lock.
// 3. ciOffline (no network) requires the staged layout plus a pre-generated
//    lock and runs exactly `npm ci --offline --ignore-scripts --no-audit`.
//    A missing lock/cache or an SRI mismatch fails closed; the subject is
//    never installed with bare `npm install --offline` and bun is never
//    spawned.
//
// `installSubjectPluginOfflineV1` is the full entry: with a trusted
// `--lock-file` handoff it only runs the offline ci (certification cells /
// §4 jobs); without one it generates the lock+cache locally (network) and
// then proves the same offline ci succeeds.
//
// CLI:
//   tsx install-subject-plugin.ts lock-and-cache --tarball <tgz> --work-dir <dir>
//   tsx install-subject-plugin.ts install --tarball <tgz> --run-dir <dir> \
//     --cache-dir <dir> [--lock-file <lock>] [--home-dir <dir>]
//
// CLI output is JSON with stable codes only; installer stderr embeds local
// paths and never prints.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { copyFile, mkdir, readdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

/** Installer generation recorded in §4 status and certification evidence. */
export const INSTALLER_GENERATION = "npm-offline-v1" as const;
export type InstallerGeneration = typeof INSTALLER_GENERATION;

const SUBJECT_PACKAGE = "@kunolu/omp-sbtd";
const STAGED_TARBALL_NAME = "plugin.tgz";
const LOCK_NAME = "package-lock.json";

export interface SubjectInstallEvidence {
  readonly installerGeneration: InstallerGeneration;
  /** Content SHA-256 of the staged tarball; recorded OUTSIDE the lock SRI. */
  readonly pluginTarballSha256: string;
  /** SHA-256 of the npm-generated diagnostic package-lock.json bytes. */
  readonly packageLockSha256: string;
  /**
   * Deterministic digest over the cache's content-addressed payload files
   * (`_cacache/content-v2`). Timestamped cacache index entries are excluded.
   */
  readonly installerCacheSha256: string;
}

export interface SubjectInstallResult extends SubjectInstallEvidence {
  /** Installed extension entrypoint (node_modules/@kunolu/omp-sbtd/dist/extension.js). */
  readonly extensionPath: string;
}

const sha256Hex = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");
const sha256File = (path: string): string => sha256Hex(readFileSync(path));

/**
 * Runs npm fail-closed with a scrubbed environment. Any spawn error or
 * non-zero exit collapses to the stable `PLUGIN_INSTALL_FAILED` code; npm
 * output (which embeds local paths) is discarded, never propagated.
 */
async function runNpm(
  args: readonly string[],
  cwd: string,
  homeDir: string | undefined,
): Promise<void> {
  const exitCode = await new Promise<number | null>((complete) => {
    const child = spawn("npm", [...args], {
      cwd,
      env: {
        PATH: process.env.PATH ?? "",
        HOME: homeDir ?? process.env.HOME ?? "",
      },
      shell: false,
      stdio: "ignore",
    });
    child.once("error", () => complete(null));
    child.once("close", complete);
  });
  if (exitCode !== 0) throw new Error("PLUGIN_INSTALL_FAILED");
}

/**
 * Fixed relative diagnostic layout: the tarball is copied to
 * `$runDir/plugin.tgz` and package.json depends on `file:./plugin.tgz`.
 * Returns the content SHA-256 of the staged tarball bytes npm will consume.
 */
export async function stageSubjectLayout(input: {
  readonly runDir: string;
  readonly tarballPath: string;
}): Promise<{ readonly pluginTarballSha256: string }> {
  await mkdir(input.runDir, { recursive: true, mode: 0o700 });
  const stagedTarball = join(input.runDir, STAGED_TARBALL_NAME);
  await copyFile(input.tarballPath, stagedTarball);
  await writeFile(
    join(input.runDir, "package.json"),
    `${JSON.stringify(
      {
        name: "kpi-subject-plugin-diagnostic",
        private: true,
        dependencies: { [SUBJECT_PACKAGE]: `file:./${STAGED_TARBALL_NAME}` },
      },
      null,
      2,
    )}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
  return { pluginTarballSha256: sha256File(stagedTarball) };
}

/**
 * The lock entry for the staged tarball must carry an npm-written SRI
 * (`sha512-…`). A content SHA-256 (64 lowercase hex) is not a valid SRI and
 * must never be hand-written into `integrity`.
 */
function assertLockIntegrityIsSri(lockPath: string): void {
  const lock = JSON.parse(readFileSync(lockPath, "utf8")) as {
    readonly packages?: Readonly<Record<string, { integrity?: unknown }>>;
  };
  const entry = lock.packages?.[`node_modules/${SUBJECT_PACKAGE}`];
  if (
    typeof entry?.integrity !== "string" ||
    !entry.integrity.startsWith("sha512-")
  )
    throw new Error("PLUGIN_INSTALL_FAILED");
}

/**
 * Deterministic digest over the cache's content-addressed payload files
 * (`_cacache/content-v2`, keyed by SRI). cacache index entries embed
 * timestamps and are excluded. A missing/empty cache hashes the empty set.
 */
export async function hashInstallerCache(cacheDir: string): Promise<string> {
  const digests: string[] = [];
  const walk = async (dir: string): Promise<void> => {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) await walk(path);
      else if (entry.isFile()) digests.push(sha256File(path));
    }
  };
  try {
    await walk(join(cacheDir, "_cacache", "content-v2"));
  } catch {
    // Missing cache subtree → empty-set digest.
  }
  return sha256Hex(`${[...digests].sort().join("\n")}\n`);
}

/**
 * Lock-generation step (network allowed, trusted lock-and-cache jobs only):
 * npm generates the diagnostic package-lock.json under the fixed relative
 * layout, then a real online `npm ci` validates the lock and materializes
 * the content-addressed cache consumed by every later offline install.
 */
export async function generateLockAndCache(input: {
  readonly runDir: string;
  readonly cacheDir: string;
  readonly homeDir?: string;
}): Promise<{
  readonly packageLockSha256: string;
  readonly installerCacheSha256: string;
}> {
  const lockPath = join(input.runDir, LOCK_NAME);
  await runNpm(
    [
      "install",
      "--package-lock-only",
      "--ignore-scripts",
      "--no-audit",
      "--no-fund",
    ],
    input.runDir,
    input.homeDir,
  );
  if (!existsSync(lockPath)) throw new Error("PLUGIN_INSTALL_FAILED");
  assertLockIntegrityIsSri(lockPath);
  await runNpm(
    [
      "ci",
      "--ignore-scripts",
      "--no-audit",
      "--no-fund",
      "--cache",
      input.cacheDir,
    ],
    input.runDir,
    input.homeDir,
  );
  return {
    packageLockSha256: sha256File(lockPath),
    installerCacheSha256: await hashInstallerCache(input.cacheDir),
  };
}

/**
 * Offline install step (no network): requires the staged layout plus a
 * pre-generated diagnostic lock and runs exactly
 * `npm ci --offline --ignore-scripts --no-audit`. Missing lock/cache or an
 * SRI/EINTEGRITY mismatch fails closed.
 */
export async function ciOffline(input: {
  readonly runDir: string;
  readonly cacheDir: string;
  readonly homeDir?: string;
}): Promise<SubjectInstallResult> {
  const lockPath = join(input.runDir, LOCK_NAME);
  if (!existsSync(lockPath)) throw new Error("PLUGIN_INSTALL_LOCK_REQUIRED");
  if (!existsSync(input.cacheDir))
    throw new Error("PLUGIN_INSTALL_CACHE_REQUIRED");
  assertLockIntegrityIsSri(lockPath);
  await runNpm(
    [
      "ci",
      "--offline",
      "--ignore-scripts",
      "--no-audit",
      "--no-fund",
      "--cache",
      input.cacheDir,
    ],
    input.runDir,
    input.homeDir,
  );
  const extensionPath = join(
    input.runDir,
    "node_modules",
    "@kunolu",
    "omp-sbtd",
    "dist",
    "extension.js",
  );
  if (!existsSync(extensionPath)) throw new Error("PLUGIN_INSTALL_FAILED");
  return {
    extensionPath,
    installerGeneration: INSTALLER_GENERATION,
    pluginTarballSha256: sha256File(join(input.runDir, STAGED_TARBALL_NAME)),
    packageLockSha256: sha256File(lockPath),
    installerCacheSha256: await hashInstallerCache(input.cacheDir),
  };
}

/**
 * Full npm-offline-v1 install. With a trusted `lockFilePath` handoff the
 * subject installs ONLY via the offline ci (certification cells and the §4
 * job: no network, no bun). Without one (local diagnostic use) the lock and
 * cache are generated with network first, then the same offline ci must
 * also succeed.
 */
export async function installSubjectPluginOfflineV1(input: {
  readonly runDir: string;
  readonly tarballPath: string;
  readonly cacheDir: string;
  readonly lockFilePath?: string;
  readonly homeDir?: string;
}): Promise<SubjectInstallResult> {
  await stageSubjectLayout({
    runDir: input.runDir,
    tarballPath: input.tarballPath,
  });
  if (input.lockFilePath !== undefined) {
    await copyFile(input.lockFilePath, join(input.runDir, LOCK_NAME));
    return ciOffline({
      runDir: input.runDir,
      cacheDir: input.cacheDir,
      ...(input.homeDir === undefined ? {} : { homeDir: input.homeDir }),
    });
  }
  await generateLockAndCache({
    runDir: input.runDir,
    cacheDir: input.cacheDir,
    ...(input.homeDir === undefined ? {} : { homeDir: input.homeDir }),
  });
  return ciOffline({
    runDir: input.runDir,
    cacheDir: input.cacheDir,
    ...(input.homeDir === undefined ? {} : { homeDir: input.homeDir }),
  });
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function parseCliOptions(argv: readonly string[]): Record<string, string> {
  const options: Record<string, string> = {};
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (flag === undefined || !flag.startsWith("--"))
      throw new Error("PLUGIN_INSTALL_USAGE");
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--"))
      throw new Error("PLUGIN_INSTALL_USAGE");
    options[flag.slice(2)] = value;
    index += 1;
  }
  return options;
}

function requireCliOption(
  options: Readonly<Record<string, string>>,
  name: string,
): string {
  const value = options[name];
  if (value === undefined || value.length === 0)
    throw new Error("PLUGIN_INSTALL_USAGE");
  return value;
}

const CLI_USAGE =
  "usage: tsx install-subject-plugin.ts lock-and-cache --tarball <tgz> --work-dir <dir>\n" +
  "       tsx install-subject-plugin.ts install --tarball <tgz> --run-dir <dir> --cache-dir <dir> [--lock-file <lock>] [--home-dir <dir>]";

const isMain = (() => {
  const entry = process.argv[1];
  return (
    typeof entry === "string" &&
    entry.length > 0 &&
    import.meta.url === pathToFileURL(entry).href
  );
})();

if (isMain) {
  const [command, ...rest] = process.argv.slice(2);
  try {
    if (command === "lock-and-cache") {
      const options = parseCliOptions(rest);
      const workDir = resolve(requireCliOption(options, "work-dir"));
      const runDir = join(workDir, "run");
      const cacheDir = join(workDir, "cache");
      await mkdir(workDir, { recursive: true, mode: 0o700 });
      const staged = await stageSubjectLayout({
        runDir,
        tarballPath: resolve(requireCliOption(options, "tarball")),
      });
      const generated = await generateLockAndCache({ runDir, cacheDir });
      await copyFile(join(runDir, LOCK_NAME), join(workDir, LOCK_NAME));
      const evidence = {
        installerGeneration: INSTALLER_GENERATION,
        pluginTarballSha256: staged.pluginTarballSha256,
        ...generated,
      } as const;
      await writeFile(
        join(workDir, "installer.json"),
        `${JSON.stringify(
          { kind: "npm-offline-v1-lock-and-cache", ...evidence },
          null,
          2,
        )}\n`,
        { encoding: "utf8", mode: 0o600 },
      );
      console.log(JSON.stringify({ status: "passed", ...evidence }));
    } else if (command === "install") {
      const options = parseCliOptions(rest);
      const result = await installSubjectPluginOfflineV1({
        runDir: resolve(requireCliOption(options, "run-dir")),
        tarballPath: resolve(requireCliOption(options, "tarball")),
        cacheDir: resolve(requireCliOption(options, "cache-dir")),
        ...(options["lock-file"] === undefined
          ? {}
          : { lockFilePath: resolve(options["lock-file"]) }),
        ...(options["home-dir"] === undefined
          ? {}
          : { homeDir: resolve(options["home-dir"]) }),
      });
      console.log(JSON.stringify({ status: "passed", ...result }));
    } else {
      console.error(CLI_USAGE);
      process.exit(2);
    }
  } catch (error) {
    if (error instanceof Error && error.message === "PLUGIN_INSTALL_USAGE") {
      console.error(CLI_USAGE);
      process.exit(2);
    }
    // Stable code only; underlying npm errors embed local paths.
    const code =
      error instanceof Error && error.message.startsWith("PLUGIN_INSTALL_")
        ? error.message
        : "PLUGIN_INSTALL_FAILED";
    console.log(JSON.stringify({ status: "failed", reason: code }));
    process.exit(1);
  }
}
