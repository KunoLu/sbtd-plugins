import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { realpathSync } from "node:fs";
import {
  cp,
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  realpath,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { parse as parseYaml } from "yaml";
import {
  checkAgentPluginProjection,
  generateAgentPluginProjection,
} from "./agent-plugin-projection.js";
import {
  checkGenerated,
  generateKit,
  KitError,
  readUpstreamLock,
  type StableProvenance,
  sha256,
  sourceTreeSha256,
} from "./index.js";
import { checkOmpProjection, generateOmpProjection } from "./omp-projection.js";

const PLUGIN_TOOLING_ROOT = fileURLToPath(
  new URL("../../../packages/omp-sbtd/", import.meta.url),
);
const WORKSPACE_TOOLING_ROOT = fileURLToPath(
  new URL("../../..", import.meta.url),
);

const execFileAsync = promisify(execFile);
const SOURCE_ROOT = "vendor/sbtd-workflow-kit-upstream";

type SyncMode = "plan" | "apply";
type ReplacePath = (source: string, destination: string) => Promise<void>;

export interface SyncUpstreamOptions {
  readonly mode: SyncMode;
  readonly packageRoot: string;
  readonly sourceRoot: string;
  readonly revision: string;
  readonly planDigest?: string;
  readonly pluginRoot?: string;
  /** Test seam for induced destination-backup failures. */
  readonly backupPath?: ReplacePath;
  /** Test seam for induced final-replacement failures. */
  readonly replacePath?: ReplacePath;
}

export interface DirtyPreflight {
  readonly dirty: boolean;
  readonly conflictingPaths: readonly string[];
}

export interface UpstreamSyncResult {
  readonly status: "planned" | "applied";
  readonly sourceId: "sbtd-workflow-kit-upstream";
  readonly canonicalSourceUri: string;
  readonly resolvedRevision: string;
  readonly sourceTreeSha256: string;
  readonly mappingSha256: string;
  readonly overlayDigests: Readonly<Record<string, string>>;
  readonly expectedGeneratedSha256: string;
  readonly stableProvenance: StableProvenance;
  readonly projection: {
    readonly policySha256: string;
    readonly decisionsSha256: string;
    readonly generatedSha256: string;
    readonly retainedProvenanceManifestSha256: string;
  };
  readonly agentPluginProjection: {
    readonly generatedSha256: string;
    readonly auditSha256: string;
    readonly catalogSha256: string;
    readonly candidateCount: number;
    readonly certifiedCount: number;
  };
  readonly classifiedSections: readonly {
    readonly source: string;
    readonly policy: "include" | "omit" | "replace-with-overlay";
  }[];
  readonly destinationSha256: string;
  readonly stagedPluginValidated: true;
  readonly changedInputPaths: readonly string[];
  readonly planDigest: string;
  readonly dirtyPreflight: DirtyPreflight;
}

type CandidateResult = Omit<UpstreamSyncResult, "dirtyPreflight">;

interface Candidate {
  readonly result: CandidateResult;
  readonly workRoot: string;
  readonly stageKit: string;
  readonly stagePlugin: string;
  readonly packageRoot: string;
  readonly pluginRoot: string;
}

interface Replacement {
  readonly staged: string;
  readonly destination: string;
}

interface ReplacementBackup extends Replacement {
  readonly backup: string;
  readonly existed: boolean;
}

function normalizeCanonicalUri(uri: string): string {
  return uri
    .trim()
    .replace(/^git@github\.com:/i, "https://github.com/")
    .replace(/^ssh:\/\/git@github\.com\//i, "https://github.com/")
    .replace(/\.git\/?$/i, "")
    .replace(/\/$/, "");
}

async function exists(path: string): Promise<boolean> {
  return stat(path)
    .then(() => true)
    .catch(() => false);
}

async function listFiles(root: string, base = root): Promise<string[]> {
  const entry = await stat(root).catch(() => undefined);
  if (entry === undefined) return [];
  if (entry.isFile()) return [relative(base, root).split(sep).join("/")];
  const files: string[] = [];
  for (const child of await readdir(root, { withFileTypes: true })) {
    const path = join(root, child.name);
    if (child.isDirectory()) {
      files.push(...(await listFiles(path, base)));
    } else if (child.isFile()) {
      files.push(relative(base, path).split(sep).join("/"));
    }
  }
  return files.sort();
}

async function changedPaths(
  current: string,
  candidate: string,
  prefix: string,
): Promise<string[]> {
  const [currentFiles, candidateFiles] = await Promise.all([
    listFiles(current),
    listFiles(candidate),
  ]);
  const names = [...new Set([...currentFiles, ...candidateFiles])].sort();
  const changed: string[] = [];
  for (const name of names) {
    const [currentFile, candidateFile] = await Promise.all([
      readFile(join(current, name)).catch(() => undefined),
      readFile(join(candidate, name)).catch(() => undefined),
    ]);

    if (
      currentFile === undefined ||
      candidateFile === undefined ||
      !currentFile.equals(candidateFile)
    ) {
      changed.push(name === "" ? prefix : `${prefix}/${name}`);
    }
  }
  return changed;
}

async function destinationsSha256(
  destinations: readonly { readonly label: string; readonly path: string }[],
): Promise<string> {
  const inputs: string[] = [];
  for (const destination of destinations) {
    for (const file of await listFiles(destination.path)) {
      const label =
        file === "" ? destination.label : `${destination.label}/${file}`;
      inputs.push(
        `${label}\0${sha256(await readFile(join(destination.path, file)))}`,
      );
    }
  }
  return sha256(inputs.sort().join("\n"));
}

function classifiedSections(
  mapping: string,
  resolvedRevision: string,
): UpstreamSyncResult["classifiedSections"] {
  const parsed = parseYaml(mapping) as {
    sections?: Array<{
      source?: unknown;
      policy?: unknown;
      introducedRevision?: unknown;
    }>;
  };
  return (parsed.sections ?? [])
    .filter(
      (
        entry,
      ): entry is {
        source: string;
        policy: "include" | "omit" | "replace-with-overlay";
        introducedRevision?: unknown;
      } =>
        typeof entry.source === "string" &&
        (entry.policy === "include" ||
          entry.policy === "omit" ||
          entry.policy === "replace-with-overlay"),
    )
    .filter(
      (entry) =>
        entry.introducedRevision === undefined ||
        entry.introducedRevision === resolvedRevision,
    )
    .map(({ source, policy }) => ({ source, policy }))
    .sort((left, right) => left.source.localeCompare(right.source));
}

async function runGit(sourceRoot: string, args: string[]): Promise<Buffer> {
  try {
    const { stdout } = await execFileAsync("git", ["-C", sourceRoot, ...args], {
      encoding: "buffer",
      maxBuffer: 64 * 1024 * 1024,
    });
    return stdout as Buffer;
  } catch (cause) {
    throw new KitError(
      "SOURCE_REPOSITORY_INVALID",
      "source root is not a readable local Git repository",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

async function verifySource(
  packageRoot: string,
  sourceRoot: string,
  revision: string,
): Promise<{ canonicalSourceUri: string; resolvedRevision: string }> {
  if (!/^[0-9a-f]{40}$/.test(revision)) {
    throw new KitError(
      "SOURCE_REVISION_INVALID",
      "revision must be an explicit 40-character commit SHA",
    );
  }
  const lock = await readUpstreamLock(packageRoot);
  const remote = (await runGit(sourceRoot, ["remote", "get-url", "origin"]))
    .toString("utf8")
    .trim();
  if (
    normalizeCanonicalUri(remote) !==
    normalizeCanonicalUri(lock.canonicalSourceUri)
  ) {
    throw new KitError(
      "SOURCE_REPOSITORY_INVALID",
      "source root does not identify the canonical upstream repository",
    );
  }
  let resolvedRevision: string;
  try {
    resolvedRevision = (
      await runGit(sourceRoot, [
        "rev-parse",
        "--verify",
        `${revision}^{commit}`,
      ])
    )
      .toString("utf8")
      .trim();
  } catch (cause) {
    if (cause instanceof KitError) {
      throw new KitError(
        "SOURCE_REVISION_INVALID",
        "revision is not available as a committed upstream Git object",
      );
    }
    throw cause;
  }
  if (resolvedRevision !== revision) {
    throw new KitError(
      "SOURCE_REVISION_INVALID",
      "revision must resolve to the requested committed Git object",
    );
  }
  return { canonicalSourceUri: lock.canonicalSourceUri, resolvedRevision };
}

async function archiveRevision(
  sourceRoot: string,
  revision: string,
  destination: string,
  archivePath: string,
): Promise<void> {
  const archive = await runGit(sourceRoot, [
    "archive",
    "--format=tar",
    revision,
  ]);
  await mkdir(destination, { recursive: true });
  await writeFile(archivePath, archive);
  try {
    await execFileAsync("tar", ["-xf", archivePath, "-C", destination], {
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (cause) {
    throw new KitError(
      "SOURCE_REVISION_INVALID",
      "committed upstream Git object could not be staged",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

async function runPluginEmbed(
  script: string,
  source: string,
  destination: string,
  pluginLicense: string,
  pluginNotices: string,
  verifyOnly: boolean,
): Promise<void> {
  try {
    await execFileAsync(process.execPath, [script], {
      env: {
        ...process.env,
        KPI_KIT_SOURCE: source,
        KPI_EMBED_DESTINATION: destination,
        KPI_PLUGIN_LICENSE_DESTINATION: pluginLicense,
        KPI_PLUGIN_NOTICES_DESTINATION: pluginNotices,
        ...(verifyOnly ? { KPI_EMBED_VERIFY_ONLY: "1" } : {}),
      },
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (cause) {
    throw new KitError(
      "STAGED_PLUGIN_INVALID",
      "staged Plugin embedded Kit, LICENSE, or notices are invalid",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

async function runPluginSbom(
  stagePlugin: string,
  stageKit: string,
): Promise<void> {
  try {
    await execFileAsync(
      process.execPath,
      [
        join(PLUGIN_TOOLING_ROOT, "node_modules", "tsx", "dist", "cli.mjs"),
        join(PLUGIN_TOOLING_ROOT, "scripts", "p0", "write-sbom.ts"),
      ],
      {
        cwd: PLUGIN_TOOLING_ROOT,
        env: {
          ...process.env,
          KPI_SBOM_PLUGIN_ROOT: stagePlugin,
          KPI_SBOM_KIT_ROOT: stageKit,
          KPI_SBOM_WORKSPACE_ROOT: WORKSPACE_TOOLING_ROOT,
          KPI_SBOM_RELEASE_ROOT: "staged-promotion",
        },
        maxBuffer: 64 * 1024 * 1024,
      },
    );
  } catch (cause) {
    throw new KitError(
      "STAGED_PLUGIN_INVALID",
      "staged Plugin SBOM is invalid",
      {
        cause: cause instanceof Error ? cause.message : "unknown",
      },
    );
  }
}

const PROMOTION_OWNED_PACKAGE_PATHS = [
  SOURCE_ROOT,
  "upstream.lock.json",
  "agents-section-map.yaml",
  "overlays",
  "generated",
  "omp-distribution-map.yaml",
  "omp-overlays",
  "generated-omp",
  "generated-agent-plugin",
] as const;
const PROMOTION_OWNED_PLUGIN_PATHS = [
  "kit",
  "LICENSE",
  "THIRD_PARTY_NOTICES.md",
  "SBOM.spdx.json",
] as const;

async function gitRepositoryRoot(root: string): Promise<string> {
  try {
    const topLevel = (await runGit(root, ["rev-parse", "--show-toplevel"]))
      .toString("utf8")
      .trim();
    return await realpath(topLevel);
  } catch {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "cannot verify promotion destination cleanliness outside a readable Git repository",
      { root },
    );
  }
}

export async function promotionDirtyPreflight(
  options: Pick<SyncUpstreamOptions, "packageRoot" | "pluginRoot">,
): Promise<DirtyPreflight> {
  const packageRoot = await realpath(resolve(options.packageRoot));
  const pluginRoot = await realpath(
    resolve(options.pluginRoot ?? join(packageRoot, "../../packages/omp-sbtd")),
  );
  const repositoryRoot = await gitRepositoryRoot(packageRoot);
  const pluginRepositoryRoot = await gitRepositoryRoot(pluginRoot);
  if (repositoryRoot !== pluginRepositoryRoot) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "promotion destinations must share one Git repository",
      { repositoryRoot, pluginRepositoryRoot },
    );
  }
  const ownedPaths = [
    ...PROMOTION_OWNED_PACKAGE_PATHS.map((path) => join(packageRoot, path)),
    ...PROMOTION_OWNED_PLUGIN_PATHS.map((path) => join(pluginRoot, path)),
  ];
  const relativePaths = ownedPaths.map((path) =>
    relative(repositoryRoot, path).split(sep).join("/"),
  );
  if (
    relativePaths.some(
      (path) => path === "" || path.startsWith("../") || path === "..",
    )
  ) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "promotion destinations must be contained in their Git repository",
      { repositoryRoot },
    );
  }
  let output: Buffer;
  try {
    output = await runGit(repositoryRoot, [
      "status",
      "--porcelain=v1",
      "-z",
      "--no-renames",
      "--",
      ...relativePaths,
    ]);
  } catch (cause) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "cannot verify promotion destination cleanliness",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
  const conflictingPaths = [
    ...new Set(
      output
        .toString("utf8")
        .split("\0")
        .filter((entry) => entry.length > 3)
        .map((entry) => entry.slice(3)),
    ),
  ].sort();
  return { dirty: conflictingPaths.length > 0, conflictingPaths };
}

export interface StableInstallPolicyProof {
  readonly auto: {
    readonly sourceUsed: string;
    readonly stableSet: string | null;
  };
  readonly stable: {
    readonly sourceUsed: string;
    readonly stableSet: string | null;
  };
  readonly gitInvocations: readonly string[];
  readonly upstreamInvokedGit: boolean;
  readonly upstreamRejectedWithoutFallback: boolean;
}

export async function proveStableInstallPolicy(
  sourceRoot: string,
  skillName = "grill-me",
): Promise<StableInstallPolicyProof> {
  const onboardScript = join(
    sourceRoot,
    "sbtd-workflow-onboard",
    "scripts",
    "onboard.py",
  );
  if (!(await exists(onboardScript))) {
    throw new KitError(
      "STABLE_INSTALL_POLICY_INVALID",
      "vendored Onboard runtime script is missing",
      { path: "sbtd-workflow-onboard/scripts/onboard.py" },
    );
  }
  const workRoot = await mkdtemp(join(tmpdir(), "kpi-stable-policy-"));
  try {
    const stubDir = join(workRoot, "bin");
    const gitLog = join(workRoot, "git-invocations.log");
    const workspace = join(workRoot, "workspace");
    await mkdir(stubDir, { recursive: true });
    await mkdir(workspace, { recursive: true });
    await writeFile(
      join(stubDir, "git"),
      `#!/bin/sh\nprintf '%s\\n' "$*" >> "${gitLog}"\nexit 1\n`,
      { mode: 0o755 },
    );
    await writeFile(gitLog, "", "utf8");
    const probeScript = join(workRoot, "probe.py");
    await writeFile(
      probeScript,
      [
        "import importlib.util",
        "import json",
        "import sys",
        "from pathlib import Path",
        `spec = importlib.util.spec_from_file_location("sbtd_onboard", ${JSON.stringify(onboardScript)})`,
        "module = importlib.util.module_from_spec(spec)",
        'sys.modules["sbtd_onboard"] = module',
        "spec.loader.exec_module(module)",
        `resolved = module.resolve_external_install_sources([${JSON.stringify(skillName)}], sys.argv[1], Path(sys.argv[2]))`,
        'print(json.dumps({name: {"sourceUsed": entry["sourceUsed"], "stableSet": entry["stableSet"]} for name, entry in resolved.items()}))',
        "",
      ].join("\n"),
      "utf8",
    );
    const runProbe = async (
      requestedSource: string,
    ): Promise<
      | {
          readonly ok: true;
          readonly result: Record<
            string,
            { readonly sourceUsed: string; readonly stableSet: string | null }
          >;
        }
      | { readonly ok: false; readonly error: string }
    > => {
      try {
        const { stdout } = await execFileAsync(
          "python3",
          [probeScript, requestedSource, workspace],
          {
            env: {
              PATH: `${stubDir}${sep === "\\" ? ";" : ":"}${process.env.PATH ?? "/usr/bin:/bin"}`,
              HOME: workRoot,
              PYTHONDONTWRITEBYTECODE: "1",
            },
            maxBuffer: 64 * 1024 * 1024,
          },
        );
        return { ok: true, result: JSON.parse(stdout) };
      } catch (cause) {
        return {
          ok: false,
          error: cause instanceof Error ? cause.message : "unknown",
        };
      }
    };
    const auto = await runProbe("auto");
    const stable = await runProbe("stable");
    const gitInvocations = (await readFile(gitLog, "utf8"))
      .split("\n")
      .filter((line) => line !== "");
    const upstream = await runProbe("upstream");
    const upstreamInvokedGit =
      (await readFile(gitLog, "utf8")).split("\n").filter((line) => line !== "")
        .length > gitInvocations.length;

    const autoEntry = auto.ok ? auto.result[skillName] : undefined;
    const stableEntry = stable.ok ? stable.result[skillName] : undefined;
    if (
      autoEntry === undefined ||
      autoEntry.sourceUsed !== "stable" ||
      stableEntry === undefined ||
      stableEntry.sourceUsed !== "stable"
    ) {
      throw new KitError(
        "STABLE_INSTALL_POLICY_INVALID",
        "default stable/auto installation did not resolve from the vendored stable set",
        { auto, stable },
      );
    }
    if (gitInvocations.length > 0) {
      throw new KitError(
        "STABLE_INSTALL_POLICY_INVALID",
        "default stable/auto installation invoked Git or the network",
        { gitInvocations },
      );
    }
    if (upstream.ok || !upstreamInvokedGit) {
      throw new KitError(
        "STABLE_INSTALL_POLICY_INVALID",
        "explicit upstream selection did not fail closed and has no silent fallback",
        { upstreamOk: upstream.ok, upstreamInvokedGit },
      );
    }
    return {
      auto: autoEntry,
      stable: stableEntry,
      gitInvocations,
      upstreamInvokedGit,
      upstreamRejectedWithoutFallback: true,
    };
  } finally {
    await rm(workRoot, { force: true, recursive: true });
  }
}

async function stageCandidate(
  options: SyncUpstreamOptions,
): Promise<Candidate> {
  const packageRoot = resolve(options.packageRoot);
  const pluginRoot = resolve(
    options.pluginRoot ?? join(packageRoot, "../../packages/omp-sbtd"),
  );
  const sourceRoot = resolve(options.sourceRoot);
  const source = await verifySource(packageRoot, sourceRoot, options.revision);
  let workRoot: string;
  try {
    workRoot = await mkdtemp(join(dirname(packageRoot), ".sync-upstream-"));
  } catch (cause) {
    throw new KitError(
      "TRANSACTION_FAILED",
      "could not create a local upstream promotion stage",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
  const stageKit = join(workRoot, "kit");
  const stagePlugin = join(workRoot, "plugin");
  try {
    await Promise.all([
      mkdir(stageKit, { recursive: true }),
      mkdir(stagePlugin, { recursive: true }),
      mkdir(join(stagePlugin, "validation", "p0"), { recursive: true }),
    ]);
    await Promise.all([
      cp(
        join(packageRoot, "agents-section-map.yaml"),
        join(stageKit, "agents-section-map.yaml"),
      ),
      cp(join(packageRoot, "overlays"), join(stageKit, "overlays"), {
        recursive: true,
      }),
      cp(join(packageRoot, "LICENSE"), join(stageKit, "LICENSE")),
      cp(join(packageRoot, "package.json"), join(stageKit, "package.json")),
      cp(
        join(packageRoot, "omp-distribution-map.yaml"),
        join(stageKit, "omp-distribution-map.yaml"),
      ),
      cp(join(packageRoot, "omp-overlays"), join(stageKit, "omp-overlays"), {
        recursive: true,
      }),
      cp(join(pluginRoot, "package.json"), join(stagePlugin, "package.json")),
      cp(join(pluginRoot, "plugin.json"), join(stagePlugin, "plugin.json")),
      cp(join(pluginRoot, "README.md"), join(stagePlugin, "README.md")),
      cp(join(pluginRoot, "SECURITY.md"), join(stagePlugin, "SECURITY.md")),
      cp(join(pluginRoot, "CHANGELOG.md"), join(stagePlugin, "CHANGELOG.md")),
      cp(join(pluginRoot, "LICENSE"), join(stagePlugin, "LICENSE")),
      cp(join(pluginRoot, "skills"), join(stagePlugin, "skills"), {
        recursive: true,
      }),
      cp(
        join(pluginRoot, "validation", "p0", "compatibility.v2.json"),
        join(stagePlugin, "validation", "p0", "compatibility.v2.json"),
      ),
      cp(join(pluginRoot, "dist"), join(stagePlugin, "dist"), {
        recursive: true,
      }),
    ]);
    const archivePath = join(workRoot, "upstream.tar");
    const stagedVendor = join(stageKit, SOURCE_ROOT);
    await archiveRevision(
      sourceRoot,
      source.resolvedRevision,
      stagedVendor,
      archivePath,
    );
    const sourceDigest = await sourceTreeSha256(stagedVendor);
    const currentLock = await readUpstreamLock(packageRoot);
    const candidateLock = {
      ...currentLock,
      resolvedRevision: source.resolvedRevision,
      sourceTreeSha256: sourceDigest,
    };
    await writeFile(
      join(stageKit, "upstream.lock.json"),
      `${JSON.stringify(candidateLock, null, 2)}\n`,
      "utf8",
    );
    const generated = await generateKit({
      packageRoot: stageKit,
      outputDirectory: join(stageKit, "generated"),
    });
    const [projection, agentPluginProjection] = await Promise.all([
      generateOmpProjection({
        packageRoot: stageKit,
        canonicalDirectory: join(stageKit, "generated"),
        outputDirectory: join(stageKit, "generated-omp"),
      }),
      generateAgentPluginProjection({
        packageRoot: stageKit,
        canonicalDirectory: join(stageKit, "generated"),
        outputDirectory: join(stageKit, "generated-agent-plugin"),
      }),
    ]);
    await runPluginEmbed(
      join(pluginRoot, "scripts/embed-kit.mjs"),
      join(stageKit, "generated-omp"),
      join(stagePlugin, "kit"),
      join(stagePlugin, "LICENSE"),
      join(stagePlugin, "THIRD_PARTY_NOTICES.md"),
      false,
    );
    await runPluginSbom(stagePlugin, stageKit);

    const mapping = await readFile(
      join(stageKit, "agents-section-map.yaml"),
      "utf8",
    );
    const changedInputPaths = (
      await Promise.all([
        changedPaths(join(packageRoot, SOURCE_ROOT), stagedVendor, SOURCE_ROOT),
        changedPaths(
          join(packageRoot, "upstream.lock.json"),
          join(stageKit, "upstream.lock.json"),
          "upstream.lock.json",
        ),
        changedPaths(
          join(packageRoot, "agents-section-map.yaml"),
          join(stageKit, "agents-section-map.yaml"),
          "agents-section-map.yaml",
        ),
        changedPaths(
          join(packageRoot, "overlays"),
          join(stageKit, "overlays"),
          "overlays",
        ),
        changedPaths(
          join(packageRoot, "generated"),
          join(stageKit, "generated"),
          "generated",
        ),
        changedPaths(
          join(packageRoot, "omp-distribution-map.yaml"),
          join(stageKit, "omp-distribution-map.yaml"),
          "omp-distribution-map.yaml",
        ),
        changedPaths(
          join(packageRoot, "omp-overlays"),
          join(stageKit, "omp-overlays"),
          "omp-overlays",
        ),
        changedPaths(
          join(packageRoot, "generated-omp"),
          join(stageKit, "generated-omp"),
          "generated-omp",
        ),
        changedPaths(
          join(packageRoot, "generated-agent-plugin"),
          join(stageKit, "generated-agent-plugin"),
          "generated-agent-plugin",
        ),
        changedPaths(
          join(pluginRoot, "kit"),
          join(stagePlugin, "kit"),
          "plugin/kit",
        ),
        changedPaths(
          join(pluginRoot, "LICENSE"),
          join(stagePlugin, "LICENSE"),
          "plugin/LICENSE",
        ),
        changedPaths(
          join(pluginRoot, "THIRD_PARTY_NOTICES.md"),
          join(stagePlugin, "THIRD_PARTY_NOTICES.md"),
          "plugin/THIRD_PARTY_NOTICES.md",
        ),
        changedPaths(
          join(pluginRoot, "SBOM.spdx.json"),
          join(stagePlugin, "SBOM.spdx.json"),
          "plugin/SBOM.spdx.json",
        ),
      ])
    )
      .flat()
      .sort();
    const destinationSha256 = await destinationsSha256([
      { label: SOURCE_ROOT, path: join(packageRoot, SOURCE_ROOT) },
      {
        label: "upstream.lock.json",
        path: join(packageRoot, "upstream.lock.json"),
      },
      {
        label: "agents-section-map.yaml",
        path: join(packageRoot, "agents-section-map.yaml"),
      },
      { label: "overlays", path: join(packageRoot, "overlays") },
      { label: "generated", path: join(packageRoot, "generated") },
      {
        label: "omp-distribution-map.yaml",
        path: join(packageRoot, "omp-distribution-map.yaml"),
      },
      { label: "omp-overlays", path: join(packageRoot, "omp-overlays") },
      { label: "generated-omp", path: join(packageRoot, "generated-omp") },
      {
        label: "generated-agent-plugin",
        path: join(packageRoot, "generated-agent-plugin"),
      },
      { label: "plugin/kit", path: join(pluginRoot, "kit") },
      { label: "plugin/LICENSE", path: join(pluginRoot, "LICENSE") },
      {
        label: "plugin/THIRD_PARTY_NOTICES.md",
        path: join(pluginRoot, "THIRD_PARTY_NOTICES.md"),
      },
      {
        label: "plugin/SBOM.spdx.json",
        path: join(pluginRoot, "SBOM.spdx.json"),
      },
    ]);
    const planInputs = {
      sourceId: currentLock.sourceId,
      canonicalSourceUri: source.canonicalSourceUri,
      resolvedRevision: source.resolvedRevision,
      sourceTreeSha256: sourceDigest,
      mappingSha256: sha256(mapping),
      overlayDigests: generated.manifest.overlayDigests,
      expectedGeneratedSha256: generated.manifest.generatedSha256,
      stableProvenance: generated.manifest.stableProvenance,
      projection: {
        policySha256: projection.manifest.projection.policySha256,
        decisionsSha256: projection.manifest.projection.decisionsSha256,
        generatedSha256: projection.manifest.projection.generatedSha256,
        retainedProvenanceManifestSha256:
          projection.manifest.retainedProvenance.manifestSha256,
      },
      agentPluginProjection: {
        generatedSha256: agentPluginProjection.manifest.generatedSha256,
        auditSha256: agentPluginProjection.manifest.auditSha256,
        catalogSha256: agentPluginProjection.manifest.catalogSha256,
        candidateCount: agentPluginProjection.manifest.candidateCount,
        certifiedCount: agentPluginProjection.manifest.certifiedCount,
      },
      classifiedSections: classifiedSections(mapping, source.resolvedRevision),
      changedInputPaths,
      destinationSha256,
      stagedPluginValidated: true,
    } as const;
    return {
      workRoot,
      stageKit,
      stagePlugin,
      packageRoot,
      pluginRoot,
      result: {
        status: options.mode === "plan" ? "planned" : "applied",
        ...planInputs,
        planDigest: sha256(JSON.stringify(planInputs)),
      },
    };
  } catch (cause) {
    await rm(workRoot, { force: true, recursive: true });
    if (cause instanceof KitError) throw cause;
    throw new KitError(
      "KIT_INPUT_INVALID",
      "could not build the verified upstream promotion candidate",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

async function rollback(
  replacements: readonly ReplacementBackup[],
): Promise<void> {
  for (const replacement of [...replacements].reverse()) {
    await rm(replacement.destination, { force: true, recursive: true });
    if (replacement.existed && (await exists(replacement.backup))) {
      await rename(replacement.backup, replacement.destination);
    }
  }
}

async function applyCandidate(
  candidate: Candidate,
  backupPath: ReplacePath,
  replacePath: ReplacePath,
): Promise<void> {
  const backups = join(candidate.workRoot, "backups");
  const replacements: readonly Replacement[] = [
    {
      staged: join(candidate.stageKit, SOURCE_ROOT),
      destination: join(candidate.packageRoot, SOURCE_ROOT),
    },
    {
      staged: join(candidate.stageKit, "upstream.lock.json"),
      destination: join(candidate.packageRoot, "upstream.lock.json"),
    },
    {
      staged: join(candidate.stageKit, "agents-section-map.yaml"),
      destination: join(candidate.packageRoot, "agents-section-map.yaml"),
    },
    {
      staged: join(candidate.stageKit, "overlays"),
      destination: join(candidate.packageRoot, "overlays"),
    },
    {
      staged: join(candidate.stageKit, "generated"),
      destination: join(candidate.packageRoot, "generated"),
    },
    {
      staged: join(candidate.stageKit, "generated-omp"),
      destination: join(candidate.packageRoot, "generated-omp"),
    },
    {
      staged: join(candidate.stageKit, "generated-agent-plugin"),
      destination: join(candidate.packageRoot, "generated-agent-plugin"),
    },
    {
      staged: join(candidate.stagePlugin, "kit"),
      destination: join(candidate.pluginRoot, "kit"),
    },
    {
      staged: join(candidate.stagePlugin, "LICENSE"),
      destination: join(candidate.pluginRoot, "LICENSE"),
    },
    {
      staged: join(candidate.stagePlugin, "THIRD_PARTY_NOTICES.md"),
      destination: join(candidate.pluginRoot, "THIRD_PARTY_NOTICES.md"),
    },
    {
      staged: join(candidate.stagePlugin, "SBOM.spdx.json"),
      destination: join(candidate.pluginRoot, "SBOM.spdx.json"),
    },
  ];
  const completed: ReplacementBackup[] = [];
  await mkdir(backups, { recursive: true });
  try {
    for (const [index, replacement] of replacements.entries()) {
      const backup = join(backups, `${index}-${randomUUID()}`);
      const existed = await exists(replacement.destination);
      if (existed) await backupPath(replacement.destination, backup);
      const entry: ReplacementBackup = {
        ...replacement,
        backup,
        existed,
      };
      completed.push(entry);
      await replacePath(entry.staged, entry.destination);
    }
    await checkGenerated({
      packageRoot: candidate.packageRoot,
      outputDirectory: join(candidate.packageRoot, "generated"),
    });
    await checkOmpProjection({
      packageRoot: candidate.packageRoot,
      canonicalDirectory: join(candidate.packageRoot, "generated"),
      outputDirectory: join(candidate.packageRoot, "generated-omp"),
    });
    await checkAgentPluginProjection({
      packageRoot: candidate.packageRoot,
      canonicalDirectory: join(candidate.packageRoot, "generated"),
      outputDirectory: join(candidate.packageRoot, "generated-agent-plugin"),
    });
    await runPluginEmbed(
      join(candidate.pluginRoot, "scripts/embed-kit.mjs"),
      join(candidate.packageRoot, "generated-omp"),
      join(candidate.pluginRoot, "kit"),
      join(candidate.pluginRoot, "LICENSE"),
      join(candidate.pluginRoot, "THIRD_PARTY_NOTICES.md"),
      true,
    );
    await rm(backups, { force: true, recursive: true });
  } catch (cause) {
    try {
      await rollback(completed);
    } catch (rollbackCause) {
      throw new KitError(
        "TRANSACTION_FAILED",
        "upstream promotion failed and rollback could not restore every destination",
        {
          cause: cause instanceof Error ? cause.message : "unknown",
          rollbackCause:
            rollbackCause instanceof Error ? rollbackCause.message : "unknown",
        },
      );
    }
    throw new KitError(
      "TRANSACTION_FAILED",
      "upstream promotion failed and restored every destination",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

export async function syncUpstream(
  options: SyncUpstreamOptions,
): Promise<UpstreamSyncResult> {
  const dirtyPreflight = await promotionDirtyPreflight(options);
  if (options.mode === "apply" && dirtyPreflight.dirty) {
    throw new KitError(
      "PROMOTION_DESTINATION_DIRTY",
      "promotion-owned destinations have uncommitted changes",
      { conflictingPaths: dirtyPreflight.conflictingPaths },
    );
  }
  const candidate = await stageCandidate(options);
  try {
    const result: UpstreamSyncResult = { ...candidate.result, dirtyPreflight };
    if (options.mode === "plan") {
      return result;
    }
    if (options.planDigest !== candidate.result.planDigest) {
      throw new KitError(
        "STALE_PLAN",
        "apply requires the exact digest of the current verified plan",
        {
          expected: candidate.result.planDigest,
          provided: options.planDigest ?? null,
        },
      );
    }
    await applyCandidate(
      candidate,
      options.backupPath ?? rename,
      options.replacePath ?? rename,
    );
    return result;
  } finally {
    await rm(candidate.workRoot, { force: true, recursive: true });
  }
}

function argumentValue(
  args: readonly string[],
  option: string,
): string | undefined {
  const index = args.indexOf(option);
  if (index === -1) return undefined;
  return args[index + 1];
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const allowedOptions: Record<string, true> = {
    "--plan": true,
    "--apply": true,
    "--source-root": true,
    "--revision": true,
    "--plan-digest": true,
  };
  const unknownOptions = args.filter(
    (argument) => argument.startsWith("--") && !allowedOptions[argument],
  );
  if (unknownOptions.length > 0) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "sync-upstream received an unsupported option",
      { unknownOptions },
    );
  }
  const isPlan = args.includes("--plan");
  const isApply = args.includes("--apply");
  if (isPlan === isApply) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "sync-upstream requires exactly one of --plan or --apply",
    );
  }
  const sourceRoot = argumentValue(args, "--source-root");
  const revision = argumentValue(args, "--revision");
  if (sourceRoot === undefined || revision === undefined) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      "sync-upstream requires --source-root and --revision",
    );
  }
  const planDigest = isApply ? argumentValue(args, "--plan-digest") : undefined;
  const result = await syncUpstream({
    mode: isPlan ? "plan" : "apply",
    packageRoot: process.cwd(),
    sourceRoot,
    revision,
    ...(planDigest === undefined ? {} : { planDigest }),
  });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

if (
  process.argv[1] !== undefined &&
  realpathSync(resolve(process.argv[1])) ===
    realpathSync(fileURLToPath(import.meta.url))
) {
  main().catch((cause: unknown) => {
    const error =
      cause instanceof KitError
        ? cause
        : new KitError("KIT_INPUT_INVALID", "sync-upstream failed", {
            cause: cause instanceof Error ? cause.message : "unknown",
          });
    process.stderr.write(
      `${JSON.stringify({
        status: "failed",
        error: {
          code: error.code,
          message: error.message,
          details: error.details,
        },
      })}\n`,
    );
    process.exitCode = 1;
  });
}
