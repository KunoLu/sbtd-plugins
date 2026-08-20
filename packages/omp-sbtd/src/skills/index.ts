import { createHash } from "node:crypto";
import { lstat, readdir, readFile, rename } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { type BookGateId, bookGateIds } from "../gates/index.js";
import { coreGateSkillNames } from "../kit/index.js";
import type { FileAdapter } from "../onboard/index.js";

const pluginRoot = fileURLToPath(new URL("../../", import.meta.url));

export const packagedSkillsRoot = join(pluginRoot, "skills");

const retainedBundledSkillNames = [
  "sbtd-workflow-onboard",
  "trellis-workflow",
  "trellis-channel",
] as const;

const bookGateBySkill: Readonly<Record<string, BookGateId>> = {
  "book-ddd-distilled-modeling": "ddd-boundary",
  "book-ddia-data-design": "ddia-data-design",
  "book-legacy-change-safety": "legacy-change-safety",
  "book-refactoring-pass": "refactoring",
  "book-release-readiness": "release-readiness",
};
const routeBySkill: Readonly<Record<string, string>> = {
  "gherkin-bdd": "bdd-tdd",
  "book-release-readiness": "release",
};

export interface RuntimeSkillPolicy {
  readonly name: string;
  readonly activation: "packaged";
  readonly route?: string;
  readonly requiredGates: readonly BookGateId[];
}

export interface PackagedSkillInventory {
  readonly names: readonly string[];
  readonly packagedCount: number;
  readonly packagedDigest: string;
  readonly invalidSkills: readonly string[];
}

export interface CertifiedConflict {
  readonly name: string;
  readonly reason: string;
}

export interface CertifiedCleanupResult {
  readonly status: "applied" | "not-required" | "failed";
  readonly detail: string;
  readonly removed: readonly string[];
  readonly conflicts: readonly CertifiedConflict[];
  readonly rollbackPath: string | null;
}

const sha256 = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");

export function pluginPackageRoot(): string {
  return pluginRoot;
}

export async function listDirectoryNames(
  path: string,
): Promise<readonly string[]> {
  try {
    const entries = await readdir(path, { withFileTypes: true });
    return entries.map((entry) => entry.name).sort();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
}

async function directoryDigest(root: string): Promise<string | undefined> {
  try {
    const rootStat = await lstat(root);
    if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) return undefined;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
  const files: string[] = [];
  const walk = async (directory: string, prefix: string): Promise<boolean> => {
    const entries = (await readdir(directory, { withFileTypes: true })).sort(
      (left, right) => left.name.localeCompare(right.name),
    );
    for (const entry of entries) {
      if (
        entry.name === "." ||
        entry.name === ".." ||
        entry.name.includes("\0")
      )
        return false;
      const relative = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (
        relative
          .split("/")
          .some((segment) => segment === "" || segment === "..")
      )
        return false;
      const absolute = join(directory, entry.name);
      if (entry.isSymbolicLink()) return false;
      if (entry.isDirectory()) {
        if (!(await walk(absolute, relative))) return false;
        continue;
      }
      if (!entry.isFile()) return false;
      files.push(`${relative}\0${sha256(await readFile(absolute))}`);
    }
    return true;
  };
  if (!(await walk(root, ""))) return undefined;
  return sha256(files.join("\n"));
}

export async function inventoryPackagedSkills(
  skillsRoot = packagedSkillsRoot,
): Promise<PackagedSkillInventory> {
  const names: string[] = [];
  const invalidSkills: string[] = [];
  for (const name of await listDirectoryNames(skillsRoot)) {
    if (name.startsWith(".")) continue;
    const skillMarkdown = join(skillsRoot, name, "SKILL.md");
    try {
      const stat = await lstat(join(skillsRoot, name));
      if (!stat.isDirectory() || stat.isSymbolicLink()) {
        invalidSkills.push(name);
        continue;
      }
      await readFile(skillMarkdown);
      names.push(name);
    } catch {
      invalidSkills.push(name);
    }
  }
  names.sort();
  invalidSkills.sort();
  const packagedDigest = await directoryDigest(skillsRoot);
  return {
    names,
    packagedCount: names.length,
    packagedDigest: packagedDigest ?? sha256(""),
    invalidSkills,
  };
}

export function isPackagedCertifiedName(
  name: string,
  packagedNames: readonly string[],
): boolean {
  return packagedNames.includes(name);
}

export function buildRuntimeSkillPolicyRegistry(
  packagedNames: readonly string[],
): readonly RuntimeSkillPolicy[] {
  return packagedNames.map((name) => ({
    name,
    activation: "packaged",
    ...(routeBySkill[name] === undefined ? {} : { route: routeBySkill[name] }),
    requiredGates:
      bookGateBySkill[name] === undefined ? [] : [bookGateBySkill[name]],
  }));
}

export function assertRegistryMatchesRuntimeConstants(
  registry: readonly RuntimeSkillPolicy[],
): void {
  const knownGates = new Set<string>(bookGateIds);
  const knownRoutes = new Set(["bdd-tdd", "release", "trellis", "ui"]);
  for (const entry of registry) {
    if (entry.route !== undefined && !knownRoutes.has(entry.route))
      throw new Error(`registry introduces unknown route ${entry.route}`);
    for (const gate of entry.requiredGates) {
      if (!knownGates.has(gate))
        throw new Error(`registry introduces unknown gate ${gate}`);
    }
  }
  for (const name of coreGateSkillNames) {
    const entry = registry.find((item) => item.name === name);
    if (entry === undefined || entry.requiredGates[0] !== bookGateBySkill[name])
      throw new Error(
        `core gate skill ${name} is missing its Book Gate mapping`,
      );
  }
}

export async function readCertifiedOrGlobalSkill(
  files: FileAdapter,
  name: string,
  packagedNames: readonly string[],
  globalSkillsDirectory: string,
  options: {
    readonly packagedRoot?: string;
    readonly invalidSkills?: readonly string[];
  } = {},
): Promise<string | undefined> {
  if (options.invalidSkills?.includes(name)) return undefined;
  const packagedRoot = options.packagedRoot ?? packagedSkillsRoot;
  if (isPackagedCertifiedName(name, packagedNames))
    return files.readText(join(packagedRoot, name, "SKILL.md"));
  return files.readText(join(globalSkillsDirectory, name, "SKILL.md"));
}

export function retainedBundledNames(): readonly string[] {
  return retainedBundledSkillNames;
}

export async function inspectPluginManifest(
  files: FileAdapter,
  expectedVersion?: string,
): Promise<"valid" | "invalid" | "missing"> {
  const raw = await files.readText(join(pluginRoot, "plugin.json"));
  if (raw === undefined) return "missing";
  try {
    const manifest: unknown = JSON.parse(raw);
    if (
      typeof manifest !== "object" ||
      manifest === null ||
      Array.isArray(manifest)
    )
      return "invalid";
    const record = manifest as Record<string, unknown>;
    if (
      record.$schema !==
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json" ||
      record.name !== "omp-sbtd" ||
      typeof record.version !== "string" ||
      record.version.length === 0 ||
      (expectedVersion !== undefined && record.version !== expectedVersion)
    )
      return "invalid";
    return "valid";
  } catch {
    return "invalid";
  }
}

export async function classifyCertifiedLeftovers(input: {
  readonly globalSkillsDirectory: string;
  readonly kitBundledSkillsRoot: string;
  readonly packagedNames: readonly string[];
  readonly files: FileAdapter;
}): Promise<{
  readonly eligible: readonly string[];
  readonly conflicts: readonly CertifiedConflict[];
}> {
  const conflicts: CertifiedConflict[] = [];
  const eligible: string[] = [];
  for (const name of input.packagedNames) {
    const leftover = join(input.globalSkillsDirectory, name);
    if (!(await input.files.exists(leftover))) continue;
    if (await input.files.isSymlink(leftover)) {
      conflicts.push({ name, reason: "symlink" });
      continue;
    }
    try {
      if (!(await lstat(leftover)).isDirectory()) {
        conflicts.push({ name, reason: "not-a-directory" });
        continue;
      }
    } catch {
      conflicts.push({ name, reason: "unreadable" });
      continue;
    }
    const leftoverDigest = await directoryDigest(leftover);
    const sourceDigest = await directoryDigest(
      join(input.kitBundledSkillsRoot, name),
    );
    if (
      leftoverDigest === undefined ||
      sourceDigest === undefined ||
      leftoverDigest !== sourceDigest
    ) {
      conflicts.push({ name, reason: "digest-mismatch" });
      continue;
    }
    eligible.push(name);
  }
  return { eligible, conflicts };
}

export async function applyCertifiedLeftoverCleanup(input: {
  readonly globalSkillsDirectory: string;
  readonly kitBundledSkillsRoot: string;
  readonly backupRoot: string;
  readonly packagedNames: readonly string[];
  readonly files: FileAdapter;
  readonly renameEntry?: (from: string, to: string) => Promise<void>;
}): Promise<CertifiedCleanupResult> {
  const { eligible, conflicts } = await classifyCertifiedLeftovers(input);
  if (eligible.length === 0)
    return {
      status: "not-required",
      detail:
        conflicts.length === 0
          ? "No certified Onboard leftovers were present."
          : `No proven Onboard leftovers; retained ${conflicts.length} same-name conflict(s).`,
      removed: [],
      conflicts,
      rollbackPath: null,
    };

  const move = input.renameEntry ?? rename;
  const moved: string[] = [];
  try {
    await input.files.makeDirectory(input.backupRoot);
    for (const name of eligible) {
      await move(
        join(input.globalSkillsDirectory, name),
        join(input.backupRoot, name),
      );
      moved.push(name);
    }
    return {
      status: "applied",
      detail: `Moved ${moved.length} proven Onboard leftover(s); rollback path: ${input.backupRoot}.`,
      removed: moved,
      conflicts,
      rollbackPath: input.backupRoot,
    };
  } catch (error) {
    for (const name of moved.reverse()) {
      await move(
        join(input.backupRoot, name),
        join(input.globalSkillsDirectory, name),
      );
    }
    return {
      status: "failed",
      detail:
        error instanceof Error
          ? `Certified leftover cleanup failed and was rolled back: ${error.message}`
          : "Certified leftover cleanup failed and was rolled back.",
      removed: [],
      conflicts,
      rollbackPath: null,
    };
  }
}

export function renderAgentPluginDoctorBlock(input: {
  readonly schema: "1.0.0";
  readonly manifest: "valid" | "invalid" | "missing";
  readonly packagedCount: number;
  readonly packagedDigest: string;
  readonly discovered: "source-unverified";
  readonly invalidSkills: readonly string[];
  readonly conflicts: readonly CertifiedConflict[];
  readonly portableMcp: "absent";
  readonly ompRuntimeExtension: "loaded" | "missing";
}): string {
  return [
    "Agent Plugin:",
    `  schema: ${input.schema}`,
    `  manifest: ${input.manifest}`,
    "  portableSkills:",
    `    packaged: ${input.packagedCount}`,
    `    packagedDigest: ${input.packagedDigest}`,
    `    discovered: ${input.discovered}`,
    `    invalidSkills: ${input.invalidSkills.length === 0 ? "[]" : JSON.stringify(input.invalidSkills)}`,
    ...(input.conflicts.length === 0
      ? []
      : [
          `    conflicts: ${JSON.stringify(input.conflicts)} (same-name user assets retained)`,
        ]),
    `  portableMcp: ${input.portableMcp}`,
    `  ompRuntimeExtension: ${input.ompRuntimeExtension}`,
  ].join("\n");
}

export async function observeAgentPluginDoctorBlock(input: {
  readonly files: FileAdapter;
  readonly globalSkillsDirectory: string;
  readonly kitBundledSkillsRoot: string;
  readonly expectedVersion?: string;
  readonly ompRuntimeExtension?: "loaded" | "missing";
}): Promise<string> {
  const packaged = await inventoryPackagedSkills().catch(() => undefined);
  const leftover =
    packaged === undefined
      ? { conflicts: [] as const }
      : await classifyCertifiedLeftovers({
          globalSkillsDirectory: input.globalSkillsDirectory,
          kitBundledSkillsRoot: input.kitBundledSkillsRoot,
          packagedNames: packaged.names,
          files: input.files,
        }).catch(() => ({ conflicts: [] as const }));
  const manifest = await inspectPluginManifest(
    input.files,
    input.expectedVersion,
  ).catch(() => "missing" as const);
  return renderAgentPluginDoctorBlock({
    schema: "1.0.0",
    manifest,
    packagedCount: packaged?.packagedCount ?? 0,
    packagedDigest: packaged?.packagedDigest ?? "unavailable",
    discovered: "source-unverified",
    invalidSkills: packaged?.invalidSkills ?? [],
    conflicts: leftover.conflicts,
    portableMcp: "absent",
    ompRuntimeExtension: input.ompRuntimeExtension ?? "loaded",
  });
}
