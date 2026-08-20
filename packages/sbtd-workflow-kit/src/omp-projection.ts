import { randomUUID } from "node:crypto";
import type { Stats } from "node:fs";
import {
  lstat,
  mkdir,
  readdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { dirname, join, resolve, sep } from "node:path";
import { parse as parseYaml } from "yaml";
import { z } from "zod";
import { KitError, kitManifestSchema, sha256 } from "./index.js";

export const OMP_DISTRIBUTION_MAP_PATH = "omp-distribution-map.yaml";
export const OMP_OVERLAY_ROOT = "omp-overlays";
export const OMP_PROJECTION_REPORT_PATH = "projection-report.json";

const EMBEDDED_STABLE_MANIFEST_PATH =
  "onboard/runtime/assets/external-skills/stable/MANIFEST.json";
const EMBEDDED_STABLE_NOTICES_PATH =
  "onboard/runtime/assets/external-skills/stable/THIRD_PARTY_NOTICES.md";
const TOP_LEVEL_NOTICES_PATH = "THIRD_PARTY_NOTICES.md";
const STABLE_SKILLS_PREFIX =
  "onboard/runtime/assets/external-skills/stable/skills/";
const STABLE_LICENSES_PREFIX =
  "onboard/runtime/assets/external-skills/stable/licenses/";
const AGENTS_TARGETS = [
  "AGENTS.global.md",
  "AGENTS.project-root.md",
  "AGENTS.project-omp.md",
] as const;

// Derived outputs are synthesized from the retained decision set; the policy
// must omit their canonical counterparts so exactly one writer owns each path.
const DERIVED_OUTPUTS = [
  TOP_LEVEL_NOTICES_PATH,
  EMBEDDED_STABLE_MANIFEST_PATH,
  EMBEDDED_STABLE_NOTICES_PATH,
] as const;

const sha256HexSchema = z.string().regex(/^[0-9a-f]{64}$/);
const decisionPathSchema = z
  .string()
  .min(1)
  .refine(
    (value) =>
      !value.startsWith("/") &&
      !value.includes("\\") &&
      value.split("/").every((segment) => segment !== "" && segment !== ".."),
    "decision path must be a safe POSIX relative path",
  );

const decisionOwnerSchema = z.enum(["kpi", "third-party"]);
const includeDecisionSchema = z
  .object({
    path: decisionPathSchema,
    owner: decisionOwnerSchema,
    policy: z.literal("include"),
  })
  .strict();
const omitDecisionSchema = z
  .object({
    path: decisionPathSchema,
    owner: decisionOwnerSchema,
    policy: z.literal("omit"),
    reason: z.string().min(1),
  })
  .strict();
const replaceDecisionSchema = z
  .object({
    path: decisionPathSchema,
    owner: decisionOwnerSchema,
    policy: z.literal("replace-with-overlay"),
    overlay: decisionPathSchema,
    reason: z.string().min(1),
  })
  .strict();

export const ompDistributionMapSchema = z
  .object({
    schemaVersion: z.literal(1),
    decisions: z.array(
      z.discriminatedUnion("policy", [
        includeDecisionSchema,
        omitDecisionSchema,
        replaceDecisionSchema,
      ]),
    ),
  })
  .strict();

export type OmpDistributionMap = z.infer<typeof ompDistributionMapSchema>;
export type OmpDistributionDecision = OmpDistributionMap["decisions"][number];

const retainedProvenanceRepositorySchema = z
  .object({
    url: z.url(),
    revision: z.string().regex(/^[0-9a-f]{40}$/),
    license: z.string().min(1),
  })
  .strict();
const retainedProvenanceSkillSchema = z
  .object({
    repository: z.string().min(1),
    sourceSubpath: z.string().min(1),
    stablePath: z.string().min(1),
    treeSha256: sha256HexSchema,
  })
  .strict();
export const retainedProvenanceSchema = z
  .object({
    stableSet: z.string().min(1),
    manifestSha256: sha256HexSchema,
    repositories: z.record(z.string(), retainedProvenanceRepositorySchema),
    skills: z.record(z.string(), retainedProvenanceSkillSchema),
  })
  .strict();
export type RetainedProvenance = z.infer<typeof retainedProvenanceSchema>;

export const ompProjectionManifestSchema = z
  .object({
    schemaVersion: z.literal(2),
    runtime: z.literal("omp"),
    canonical: z
      .object({
        sourceId: z.literal("sbtd-workflow-kit-upstream"),
        canonicalSourceUri: z.url(),
        resolvedRevision: z.string().regex(/^[0-9a-f]{40}$/),
        sourceTreeSha256: sha256HexSchema,
        transformVersion: z.string().min(1),
        manifestSha256: sha256HexSchema,
        generatedSha256: sha256HexSchema,
      })
      .strict(),
    projection: z
      .object({
        policyVersion: z.literal(1),
        policySha256: sha256HexSchema,
        decisionsSha256: sha256HexSchema,
        generatedSha256: sha256HexSchema,
        counts: z
          .object({
            included: z.number().int().min(0),
            omitted: z.number().int().min(0),
            replaced: z.number().int().min(0),
          })
          .strict(),
      })
      .strict(),
    overlayDigests: z.record(z.string(), sha256HexSchema),
    targets: z.record(z.string(), sha256HexSchema),
    profileCatalogSha256: sha256HexSchema,
    assets: z.record(z.string(), sha256HexSchema),
    retainedProvenance: retainedProvenanceSchema,
  })
  .strict();
export type OmpProjectionManifestV2 = z.infer<
  typeof ompProjectionManifestSchema
>;

export interface OmpProjectionReport {
  readonly schemaVersion: 1;
  readonly runtime: "omp";
  readonly counts: {
    readonly included: number;
    readonly omitted: number;
    readonly replaced: number;
  };
  readonly decisions: readonly {
    readonly path: string;
    readonly owner: "kpi" | "third-party";
    readonly policy: "include" | "omit" | "replace-with-overlay";
    readonly detail: string;
  }[];
  readonly policySha256: string;
  readonly decisionsSha256: string;
  readonly canonicalManifestSha256: string;
  readonly retainedProvenanceManifestSha256: string;
  readonly generatedSha256: string;
  readonly forbiddenTokenScan: {
    readonly scannedPaths: number;
    readonly scannedFiles: number;
    readonly matches: 0;
    readonly canonicalRuntimeMatches: number;
  };
}

export interface GeneratedOmpProjection {
  readonly manifest: OmpProjectionManifestV2;
  readonly report: OmpProjectionReport;
}

export interface GenerateOmpProjectionOptions {
  readonly packageRoot: string;
  readonly canonicalDirectory: string;
  readonly outputDirectory: string;
}

interface CanonicalStableSkill {
  readonly repository: string;
  readonly sourceSubpath: string;
  readonly stablePath: string;
  readonly treeSha256: string;
}
interface CanonicalStableRepository {
  readonly url: string;
  readonly revision: string;
  readonly license: string;
  readonly licenseFiles: readonly {
    readonly source: string;
    readonly stablePath: string;
  }[];
}
interface CanonicalStableManifest {
  readonly schemaVersion: 1;
  readonly stableSet: string;
  readonly promotedAt: string;
  readonly repositories: Readonly<Record<string, CanonicalStableRepository>>;
  readonly skills: Readonly<Record<string, CanonicalStableSkill>>;
}

const canonicalStableRepositorySchema = z
  .object({
    url: z.url(),
    revision: z.string().regex(/^[0-9a-f]{40}$/),
    license: z.string().min(1),
    licenseFiles: z
      .array(
        z
          .object({ source: z.string().min(1), stablePath: z.string().min(1) })
          .strict(),
      )
      .min(1),
  })
  .strict();
const canonicalStableManifestSchema = z
  .object({
    schemaVersion: z.literal(1),
    stableSet: z.string().min(1),
    promotedAt: z.string().min(1),
    repositories: z.record(z.string(), canonicalStableRepositorySchema),
    skills: z.record(
      z.string(),
      z
        .object({
          repository: z.string().min(1),
          sourceSubpath: z.string().min(1),
          stablePath: z.string().min(1),
          treeSha256: sha256HexSchema,
        })
        .strict(),
    ),
  })
  .strict();

function projectionError(
  code:
    | "PROJECTION_POLICY_INVALID"
    | "PROJECTION_ASSET_UNCLASSIFIED"
    | "PROJECTION_OWNERSHIP_VIOLATION"
    | "PROJECTION_OVERLAY_MISSING"
    | "PROJECTION_PATH_COLLISION"
    | "PROJECTION_FORBIDDEN_TOKEN"
    | "PROJECTION_LEGAL_INVENTORY"
    | "PROJECTION_DERIVED_CONFLICT"
    | "PROJECTION_CANONICAL_INVALID",
  message: string,
  details: Readonly<Record<string, unknown>> = {},
): KitError {
  return new KitError(code, message, details);
}

const canonicalOnboardRuntimeRelativePath =
  "onboard/runtime/scripts/onboard.py";

function isCanonicalOnboardRuntime(path: string): boolean {
  return path === canonicalOnboardRuntimeRelativePath;
}

function containsForbiddenToken(bytes: Uint8Array): boolean {
  // ASCII case-insensitive scan on the raw bytes; latin1 keeps a 1:1 mapping
  // so binary payloads cannot smuggle or hide an ASCII match.
  return /codex/i.test(Buffer.from(bytes).toString("latin1"));
}

function countForbiddenTokenOccurrences(bytes: Uint8Array): number {
  const text = Buffer.from(bytes).toString("latin1").toLowerCase();
  let matches = 0;
  let index = 0;
  while (index <= text.length - "codex".length) {
    const found = text.indexOf("codex", index);
    if (found === -1) break;
    matches += 1;
    index = found + 1;
  }
  return matches;
}

async function listRegularFiles(root: string, base = root): Promise<string[]> {
  let rootStat: Stats;
  try {
    rootStat = await lstat(root);
  } catch {
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "projection input root is unavailable",
    );
  }
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory())
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "projection input root must be a regular directory",
    );

  const paths: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    const relativePath = path
      .slice(base.length + 1)
      .split(sep)
      .join("/");
    const entryStat = await lstat(path);
    if (entryStat.isSymbolicLink()) {
      throw projectionError(
        "PROJECTION_CANONICAL_INVALID",
        "projection inputs must not contain symbolic links",
        { path: relativePath },
      );
    }
    if (entryStat.isDirectory()) {
      paths.push(...(await listRegularFiles(path, base)));
    } else if (entryStat.isFile()) {
      paths.push(path);
    } else {
      throw projectionError(
        "PROJECTION_CANONICAL_INVALID",
        "projection inputs must contain only regular files and directories",
        { path: relativePath },
      );
    }
  }
  return paths.sort();
}

async function readRegularOverlay(
  packageRoot: string,
  overlay: string,
): Promise<Buffer> {
  const overlayRoot = join(packageRoot, OMP_OVERLAY_ROOT);
  let rootStat: Stats;
  try {
    rootStat = await lstat(overlayRoot);
  } catch {
    throw projectionError(
      "PROJECTION_OVERLAY_MISSING",
      "a replace-with-overlay decision references a missing overlay",
      { path: overlay, overlay },
    );
  }
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory())
    throw projectionError(
      "PROJECTION_OVERLAY_MISSING",
      "a replace-with-overlay decision references a missing overlay",
      { path: overlay, overlay },
    );

  let target = overlayRoot;
  const segments = overlay.split("/");
  for (const [index, segment] of segments.entries()) {
    target = join(target, segment);
    let entryStat: Stats;
    try {
      entryStat = await lstat(target);
    } catch {
      throw projectionError(
        "PROJECTION_OVERLAY_MISSING",
        "a replace-with-overlay decision references a missing overlay",
        { path: overlay, overlay },
      );
    }
    if (entryStat.isSymbolicLink())
      throw projectionError(
        "PROJECTION_OVERLAY_MISSING",
        "a replace-with-overlay decision references a missing overlay",
        { path: overlay, overlay },
      );
    if (
      (index === segments.length - 1 && !entryStat.isFile()) ||
      (index < segments.length - 1 && !entryStat.isDirectory())
    )
      throw projectionError(
        "PROJECTION_OVERLAY_MISSING",
        "a replace-with-overlay decision references a missing overlay",
        { path: overlay, overlay },
      );
  }
  try {
    return await readFile(target);
  } catch {
    throw projectionError(
      "PROJECTION_OVERLAY_MISSING",
      "a replace-with-overlay decision references a missing overlay",
      { path: overlay, overlay },
    );
  }
}

interface ResolvedDecision {
  readonly path: string;
  readonly owner: "kpi" | "third-party";
  readonly policy: "include" | "omit" | "replace-with-overlay";
  readonly detail: string;
}

function resolveDecisions(
  map: OmpDistributionMap,
  canonicalAssets: readonly string[],
): readonly ResolvedDecision[] {
  const canonicalSet = new Set(canonicalAssets);
  const seen = new Map<string, OmpDistributionDecision>();
  const duplicates: string[] = [];
  const stale: string[] = [];
  for (const decision of map.decisions) {
    if (seen.has(decision.path)) duplicates.push(decision.path);
    else seen.set(decision.path, decision);
    if (!canonicalSet.has(decision.path)) stale.push(decision.path);
  }
  if (duplicates.length > 0) {
    throw projectionError(
      "PROJECTION_POLICY_INVALID",
      "OMP distribution map contains duplicate decisions",
      { duplicates: [...new Set(duplicates)].sort() },
    );
  }
  if (stale.length > 0) {
    throw projectionError(
      "PROJECTION_POLICY_INVALID",
      "OMP distribution map contains decisions absent from the canonical manifest",
      { stale: [...new Set(stale)].sort() },
    );
  }
  const unclassified = canonicalAssets.filter((path) => !seen.has(path)).sort();
  if (unclassified.length > 0) {
    throw projectionError(
      "PROJECTION_ASSET_UNCLASSIFIED",
      "canonical assets are missing an exact OMP projection decision",
      { unclassified },
    );
  }
  const ownershipViolations: string[] = [];
  const resolved: ResolvedDecision[] = [];
  for (const decision of map.decisions) {
    if (decision.policy === "replace-with-overlay") {
      if (decision.owner !== "kpi") {
        ownershipViolations.push(decision.path);
        continue;
      }
      if (decision.overlay !== decision.path) {
        throw projectionError(
          "PROJECTION_POLICY_INVALID",
          "an OMP overlay must mirror its canonical asset path",
          { path: decision.path, overlay: decision.overlay },
        );
      }
      resolved.push({
        path: decision.path,
        owner: decision.owner,
        policy: decision.policy,
        detail: decision.overlay,
      });
      continue;
    }
    resolved.push({
      path: decision.path,
      owner: decision.owner,
      policy: decision.policy,
      detail: decision.policy === "omit" ? decision.reason : decision.owner,
    });
  }
  if (ownershipViolations.length > 0) {
    throw projectionError(
      "PROJECTION_OWNERSHIP_VIOLATION",
      "third-party assets cannot be replaced by an OMP overlay",
      { paths: ownershipViolations.sort() },
    );
  }
  const derivedConflicts = DERIVED_OUTPUTS.filter((path) => {
    const decision = seen.get(path);
    return decision !== undefined && decision.policy !== "omit";
  });
  if (derivedConflicts.length > 0) {
    throw projectionError(
      "PROJECTION_DERIVED_CONFLICT",
      "derived OMP outputs require their canonical counterparts to be omitted",
      { conflicts: derivedConflicts.sort() },
    );
  }
  return [...resolved].sort((left, right) =>
    left.path.localeCompare(right.path),
  );
}

export async function readOmpDistributionMap(
  packageRoot: string,
): Promise<{ map: OmpDistributionMap; policySha256: string }> {
  let bytes: Buffer;
  try {
    bytes = await readFile(join(packageRoot, OMP_DISTRIBUTION_MAP_PATH));
  } catch {
    throw projectionError(
      "PROJECTION_POLICY_INVALID",
      "OMP distribution map is missing",
      { path: OMP_DISTRIBUTION_MAP_PATH },
    );
  }
  try {
    return {
      map: ompDistributionMapSchema.parse(parseYaml(bytes.toString("utf8"))),
      policySha256: sha256(bytes),
    };
  } catch (cause) {
    if (cause instanceof KitError) throw cause;
    throw projectionError(
      "PROJECTION_POLICY_INVALID",
      "OMP distribution map is invalid",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

function retainedStableSelection(
  stable: CanonicalStableManifest,
  outputPaths: ReadonlySet<string>,
): {
  repositories: Readonly<Record<string, CanonicalStableRepository>>;
  skills: Readonly<Record<string, CanonicalStableSkill>>;
} {
  const selectedSkills: Record<string, CanonicalStableSkill> = {};
  for (const [name, skill] of Object.entries(stable.skills)) {
    const treePrefix = `${STABLE_SKILLS_PREFIX}${name}/`;
    if ([...outputPaths].some((path) => path.startsWith(treePrefix))) {
      selectedSkills[name] = skill;
    }
  }
  const repositories: Record<string, CanonicalStableRepository> = {};
  for (const skill of Object.values(selectedSkills)) {
    const repository = stable.repositories[skill.repository];
    if (repository !== undefined) repositories[skill.repository] = repository;
  }
  return { repositories, skills: selectedSkills };
}

function renderRetainedStableNotices(
  repositories: Readonly<Record<string, CanonicalStableRepository>>,
): string {
  const rows = Object.entries(repositories).map(([, repository]) => {
    const displayName = repository.url
      .replace(/^https:\/\/github\.com\//, "")
      .replace(/\.git$/, "");
    return `| \`${displayName}\` | ${repository.license} | ${repository.licenseFiles
      .map((licenseFile) => `\`${licenseFile.stablePath}\``)
      .join(", ")} |`;
  });
  return [
    "# Stable External Skills",
    "",
    "This directory contains unmodified snapshots of the External Skills used by",
    "the SBTD Onboard workflow. `MANIFEST.json` records the exact upstream commit,",
    "source subpath, content digest, and license files for every snapshot.",
    "",
    "The snapshots are installation fallbacks, not local forks. Update them only",
    "through an explicit stable promotion that preserves upstream content and",
    "refreshes the manifest digests and third-party notices.",
    "",
    "| Repository | License | Included notices |",
    "|---|---|---|",
    ...rows,
    "",
  ].join("\n");
}

async function writeSnapshot(
  stage: string,
  options: GenerateOmpProjectionOptions,
): Promise<GeneratedOmpProjection> {
  const canonicalRoot = resolve(options.canonicalDirectory);
  const packageRoot = resolve(options.packageRoot);
  await listRegularFiles(canonicalRoot);
  const canonicalManifestBytes = await readFile(
    join(canonicalRoot, "manifest.json"),
  ).catch(() => undefined);
  if (canonicalManifestBytes === undefined) {
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "canonical Kit manifest is missing",
      { path: "manifest.json" },
    );
  }
  let canonicalManifest: z.infer<typeof kitManifestSchema>;
  try {
    canonicalManifest = kitManifestSchema.parse(
      JSON.parse(canonicalManifestBytes.toString("utf8")),
    );
  } catch (cause) {
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "canonical Kit manifest is invalid",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
  const canonicalManifestSha256 = sha256(canonicalManifestBytes);
  const canonicalAssets = Object.keys(canonicalManifest.assets).sort();
  const { map, policySha256 } = await readOmpDistributionMap(packageRoot);
  const decisions = resolveDecisions(map, canonicalAssets);

  const canonicalStableBytes = await readFile(
    join(canonicalRoot, EMBEDDED_STABLE_MANIFEST_PATH),
  ).catch(() => undefined);
  if (canonicalStableBytes === undefined) {
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "canonical stable External Skills manifest is missing",
      { path: EMBEDDED_STABLE_MANIFEST_PATH },
    );
  }
  let canonicalStable: CanonicalStableManifest;
  try {
    canonicalStable = canonicalStableManifestSchema.parse(
      JSON.parse(canonicalStableBytes.toString("utf8")),
    );
  } catch (cause) {
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "canonical stable External Skills manifest is invalid",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }

  // Resolve every retained asset byte-for-byte before any output write.
  const retainedAssets = new Map<string, Buffer>();
  const overlayDigests: Record<string, string> = {};
  const digestDrift: { path: string; expected: string; actual: string }[] = [];
  for (const decision of decisions) {
    if (decision.policy === "omit") continue;
    if (decision.policy === "include") {
      const content = await readFile(join(canonicalRoot, decision.path));
      const expected = canonicalManifest.assets[decision.path];
      const actual = sha256(content);
      if (expected !== undefined && actual !== expected) {
        digestDrift.push({ path: decision.path, expected, actual });
        continue;
      }
      retainedAssets.set(decision.path, content);
      continue;
    }
    const overlay = await readRegularOverlay(packageRoot, decision.detail);
    overlayDigests[decision.path] = sha256(overlay);
    retainedAssets.set(decision.path, overlay);
  }
  if (digestDrift.length > 0) {
    throw projectionError(
      "PROJECTION_CANONICAL_INVALID",
      "canonical asset bytes drifted from the canonical manifest",
      { drift: digestDrift },
    );
  }

  // Legal inventory: stable Skills are retained as whole trees, and retained
  // repositories keep exactly their declared license files.
  const outputPaths = new Set(retainedAssets.keys());
  const legalViolations: string[] = [];
  for (const [name] of Object.entries(canonicalStable.skills)) {
    const treePrefix = `${STABLE_SKILLS_PREFIX}${name}/`;
    const canonicalTreeFiles = canonicalAssets.filter((path) =>
      path.startsWith(treePrefix),
    );
    const retainedTreeFiles = canonicalTreeFiles.filter((path) =>
      outputPaths.has(path),
    );
    if (
      retainedTreeFiles.length > 0 &&
      retainedTreeFiles.length !== canonicalTreeFiles.length
    ) {
      legalViolations.push(name);
    }
  }
  const { repositories: retainedRepositories, skills: retainedSkills } =
    retainedStableSelection(canonicalStable, outputPaths);
  for (const [repositoryId, repository] of Object.entries(
    canonicalStable.repositories,
  )) {
    const retainedRepository = retainedRepositories[repositoryId] !== undefined;
    for (const licenseFile of repository.licenseFiles) {
      const licensePath = `${STABLE_LICENSES_PREFIX}${licenseFile.stablePath.replace(/^licenses\//, "")}`;
      const licenseRetained = outputPaths.has(licensePath);
      if (licenseRetained !== retainedRepository) {
        legalViolations.push(`${repositoryId}:${licenseFile.stablePath}`);
      }
    }
  }
  if (legalViolations.length > 0) {
    throw projectionError(
      "PROJECTION_LEGAL_INVENTORY",
      "retained OMP assets must keep whole stable Skill trees and their declared license files",
      { violations: [...new Set(legalViolations)].sort() },
    );
  }

  // Derived KPi-owned outputs bind the retained decision set.
  const retainedStableManifest: CanonicalStableManifest = {
    schemaVersion: 1,
    stableSet: canonicalStable.stableSet,
    promotedAt: canonicalStable.promotedAt,
    repositories: retainedRepositories,
    skills: retainedSkills,
  };
  const retainedStableManifestBytes = Buffer.from(
    `${JSON.stringify(retainedStableManifest, null, 2)}\n`,
    "utf8",
  );
  const retainedStableNotices =
    renderRetainedStableNotices(retainedRepositories);
  const stableNoticeEntries = Object.entries(retainedRepositories)
    .map(([name, repository]) =>
      [
        `### ${name}`,
        "",
        `- Source: ${repository.url}@${repository.revision}`,
        `- License: ${repository.license}`,
        ...repository.licenseFiles.map(
          (licenseFile) =>
            `- Retained license: onboard/runtime/assets/external-skills/stable/${licenseFile.stablePath}`,
        ),
      ].join("\n"),
    )
    .join("\n\n");
  const topLevelNotices = [
    "# Third-Party Notices",
    "",
    "## SBTD Workflow Onboard",
    "",
    `- Source: ${canonicalManifest.canonicalSourceUri}@${canonicalManifest.resolvedRevision}`,
    "- License: Apache-2.0",
    "- Retained license: onboard/runtime/LICENSE",
    "- Retained notice: onboard/runtime/NOTICE",
    "",
    `## Stable External Skills (stable set ${canonicalStable.stableSet})`,
    "",
    stableNoticeEntries,
    "",
  ].join("\n");
  retainedAssets.set(
    EMBEDDED_STABLE_MANIFEST_PATH,
    retainedStableManifestBytes,
  );
  retainedAssets.set(
    EMBEDDED_STABLE_NOTICES_PATH,
    Buffer.from(retainedStableNotices, "utf8"),
  );
  retainedAssets.set(
    TOP_LEVEL_NOTICES_PATH,
    Buffer.from(topLevelNotices, "utf8"),
  );

  const assetDigests = Object.fromEntries(
    [...retainedAssets.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([path, content]) => [path, sha256(content)]),
  );
  const generatedSha256 = sha256(
    [
      ...Object.entries(assetDigests)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([path, digest]) => `${path}\0${digest}`),
      ...Object.entries(overlayDigests)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([path, digest]) => `overlay:${path}\0${digest}`),
    ].join("\n"),
  );
  const decisionsSha256 = sha256(
    decisions
      .map(
        (decision) =>
          `${decision.path}\0${decision.policy}\0${decision.detail}`,
      )
      .join("\n"),
  );
  const counts = {
    included: decisions.filter((decision) => decision.policy === "include")
      .length,
    omitted: decisions.filter((decision) => decision.policy === "omit").length,
    replaced: decisions.filter(
      (decision) => decision.policy === "replace-with-overlay",
    ).length,
  };
  const retainedProvenance: RetainedProvenance = {
    stableSet: canonicalStable.stableSet,
    manifestSha256: sha256(retainedStableManifestBytes),
    repositories: Object.fromEntries(
      Object.entries(retainedRepositories).map(([name, repository]) => [
        name,
        {
          url: repository.url,
          revision: repository.revision,
          license: repository.license,
        },
      ]),
    ),
    skills: Object.fromEntries(
      Object.entries(retainedSkills).map(([name, skill]) => [
        name,
        {
          repository: skill.repository,
          sourceSubpath: skill.sourceSubpath,
          stablePath: skill.stablePath,
          treeSha256: skill.treeSha256,
        },
      ]),
    ),
  };
  const targets = Object.fromEntries(
    AGENTS_TARGETS.map((target) => {
      const digest = assetDigests[target];
      if (digest === undefined) {
        throw projectionError(
          "PROJECTION_POLICY_INVALID",
          "the OMP projection must retain every managed AGENTS target",
          { target },
        );
      }
      return [target, digest];
    }),
  );
  const profileCatalogSha256 = assetDigests["catalog.json"];
  if (profileCatalogSha256 === undefined) {
    throw projectionError(
      "PROJECTION_POLICY_INVALID",
      "the OMP projection must retain the Profile Catalog",
      { path: "catalog.json" },
    );
  }
  const manifest = ompProjectionManifestSchema.parse({
    schemaVersion: 2,
    runtime: "omp",
    canonical: {
      sourceId: canonicalManifest.sourceId,
      canonicalSourceUri: canonicalManifest.canonicalSourceUri,
      resolvedRevision: canonicalManifest.resolvedRevision,
      sourceTreeSha256: canonicalManifest.sourceTreeSha256,
      transformVersion: canonicalManifest.transformVersion,
      manifestSha256: canonicalManifestSha256,
      generatedSha256: canonicalManifest.generatedSha256,
    },
    projection: {
      policyVersion: 1,
      policySha256,
      decisionsSha256,
      generatedSha256,
      counts,
    },
    overlayDigests,
    targets,
    profileCatalogSha256,
    assets: assetDigests,
    retainedProvenance,
  });
  const canonicalRuntimeMatches = countForbiddenTokenOccurrences(
    retainedAssets.get(canonicalOnboardRuntimeRelativePath) ?? Buffer.alloc(0),
  );
  const report: OmpProjectionReport = {
    schemaVersion: 1,
    runtime: "omp",
    counts,
    decisions: decisions.map((decision) => ({
      path: decision.path,
      owner: decision.owner,
      policy: decision.policy,
      detail: decision.detail,
    })),
    policySha256,
    decisionsSha256,
    canonicalManifestSha256,
    retainedProvenanceManifestSha256: retainedProvenance.manifestSha256,
    generatedSha256,
    forbiddenTokenScan: {
      scannedPaths: retainedAssets.size + 2,
      scannedFiles: retainedAssets.size + 2,
      matches: 0,
      canonicalRuntimeMatches,
    },
  };
  const reportBytes = Buffer.from(
    `${JSON.stringify(report, null, 2)}\n`,
    "utf8",
  );
  const manifestBytes = Buffer.from(
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );

  // Strict zero-leakage gate over every emitted path and payload, except the
  // canonical runtime whose counted legacy identifier is required for its
  // constrained OMP adapter contract. The exemption is content-bound: it
  // applies only when the retained bytes exactly match the digest the
  // canonical manifest declares for that path, so an overlay or drifted
  // payload cannot smuggle additional forbidden content under it. Diagnostics
  // expose only relative paths and counts, never payload content.
  const approvedCanonicalRuntimeDigest =
    canonicalManifest.assets[canonicalOnboardRuntimeRelativePath];
  const outputFiles: readonly (readonly [string, Buffer])[] = [
    ...[...retainedAssets.entries()].map(
      ([path, content]) => [path, content] as const,
    ),
    ["manifest.json", manifestBytes] as const,
    [OMP_PROJECTION_REPORT_PATH, reportBytes] as const,
  ];
  const pathViolations = outputFiles
    .map(([path]) => path)
    .filter((path) => containsForbiddenToken(Buffer.from(path, "utf8")))
    .sort();
  const payloadViolations = outputFiles
    .filter(([path, content]) => {
      if (!containsForbiddenToken(content)) return false;
      const approvedCanonicalRuntime =
        isCanonicalOnboardRuntime(path) &&
        approvedCanonicalRuntimeDigest !== undefined &&
        sha256(content) === approvedCanonicalRuntimeDigest;
      return !approvedCanonicalRuntime;
    })
    .map(([path]) => path)
    .sort();
  if (pathViolations.length > 0 || payloadViolations.length > 0) {
    throw projectionError(
      "PROJECTION_FORBIDDEN_TOKEN",
      "OMP projection output contains a forbidden non-OMP Runtime token",
      {
        pathViolations,
        payloadViolations,
        violationCount: pathViolations.length + payloadViolations.length,
      },
    );
  }

  await mkdir(stage, { recursive: true });
  await Promise.all(
    [...retainedAssets.entries()].map(async ([path, content]) => {
      const target = join(stage, path);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, content);
    }),
  );
  await Promise.all([
    writeFile(join(stage, "manifest.json"), manifestBytes),
    writeFile(join(stage, OMP_PROJECTION_REPORT_PATH), reportBytes),
  ]);
  return { manifest, report };
}

export async function generateOmpProjection(
  options: GenerateOmpProjectionOptions,
): Promise<GeneratedOmpProjection> {
  const outputDirectory = resolve(options.outputDirectory);
  const outputParent = dirname(outputDirectory);
  await mkdir(outputParent, { recursive: true });
  const stage = join(outputParent, `.${randomUUID()}.omp-stage`);
  const backup = join(outputParent, `.${randomUUID()}.omp-previous`);
  try {
    const result = await writeSnapshot(stage, options);
    const outputExists = await stat(outputDirectory)
      .then(() => true)
      .catch(() => false);
    if (outputExists) await rename(outputDirectory, backup);
    try {
      await rename(stage, outputDirectory);
      await rm(backup, { force: true, recursive: true });
    } catch (cause) {
      if (outputExists) await rename(backup, outputDirectory);
      throw cause;
    }
    return result;
  } catch (cause) {
    await rm(stage, { force: true, recursive: true });
    throw cause;
  }
}

export async function checkOmpProjection(
  options: GenerateOmpProjectionOptions,
): Promise<void> {
  const root = join(
    dirname(resolve(options.outputDirectory)),
    `.${randomUUID()}.omp-check`,
  );
  await mkdir(root, { recursive: true });
  try {
    await generateOmpProjection({ ...options, outputDirectory: root });
    const expectedFiles = (await listRegularFiles(root)).map((path) =>
      path
        .slice(root.length + 1)
        .split(sep)
        .join("/"),
    );
    const actualRoot = resolve(options.outputDirectory);
    const actualFiles = (await listRegularFiles(actualRoot)).map((path) =>
      path
        .slice(actualRoot.length + 1)
        .split(sep)
        .join("/"),
    );
    if (expectedFiles.join("\0") !== actualFiles.join("\0")) {
      throw new KitError(
        "GENERATED_DRIFT",
        "OMP projection output has missing or unexpected assets",
        { expectedFiles, actualFiles },
      );
    }
    for (const target of expectedFiles) {
      const [expected, actual] = await Promise.all([
        readFile(join(root, target)),
        readFile(join(actualRoot, target)),
      ]);
      if (!expected.equals(actual)) {
        throw new KitError(
          "GENERATED_DRIFT",
          "OMP projection output differs from the verified Kit",
          { target },
        );
      }
    }
  } finally {
    await rm(root, { force: true, recursive: true });
  }
}
