import { createHash, randomUUID } from "node:crypto";
import {
  mkdir,
  readdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { parse as parseYaml } from "yaml";
import { z } from "zod";

const SOURCE_ROOT = "vendor/sbtd-workflow-kit-upstream";
const STABLE_MANIFEST_SOURCE_PATH =
  "sbtd-workflow-onboard/assets/external-skills/stable/MANIFEST.json";
const AGENTS_SOURCES = [
  "sbtd-workflow-onboard/templates/agents/AGENTS.global.md",
  "sbtd-workflow-onboard/templates/agents/AGENTS.project.md",
] as const;
const TARGETS = [
  "AGENTS.global.md",
  "AGENTS.project-root.md",
  "AGENTS.project-omp.md",
] as const;

const stableRepositorySchema = z
  .object({
    url: z.url(),
    revision: z.string().regex(/^[0-9a-f]{40}$/),
    license: z.string().min(1),
    licenseFiles: z
      .array(
        z
          .object({
            source: z.string().min(1),
            stablePath: z.string().min(1),
          })
          .strict(),
      )
      .min(1),
  })
  .strict();
const stableSkillSchema = z
  .object({
    repository: z.string().min(1),
    sourceSubpath: z.string().min(1),
    stablePath: z.string().min(1),
    treeSha256: z.string().regex(/^[0-9a-f]{64}$/),
  })
  .strict();
const stableManifestSchema = z
  .object({
    schemaVersion: z.literal(1),
    stableSet: z.string().regex(/^\d{4}-\d{2}-\d{2}\.\d+$/),
    promotedAt: z.string().min(1),
    repositories: z.record(z.string(), stableRepositorySchema),
    skills: z.record(z.string(), stableSkillSchema),
  })
  .strict()
  .superRefine((manifest, context) => {
    for (const [name, skill] of Object.entries(manifest.skills)) {
      if (manifest.repositories[skill.repository] === undefined) {
        context.addIssue({
          code: "custom",
          message: `stable Skill ${name} references an unknown repository`,
        });
      }
    }
  });

const stableProvenanceRepositorySchema = z
  .object({
    url: z.url(),
    revision: z.string().regex(/^[0-9a-f]{40}$/),
    license: z.string().min(1),
  })
  .strict();
const stableProvenanceSchema = z
  .object({
    stableSet: z.string().regex(/^\d{4}-\d{2}-\d{2}\.\d+$/),
    manifestSha256: z.string().regex(/^[0-9a-f]{64}$/),
    repositories: z.record(z.string(), stableProvenanceRepositorySchema),
  })
  .strict();

const upstreamLockSchema = z.object({
  schemaVersion: z.literal(1),
  sourceId: z.literal("sbtd-workflow-kit-upstream"),
  canonicalSourceUri: z.url(),
  resolvedRevision: z.string().regex(/^[0-9a-f]{40}$/),
  sourceTag: z.string().min(1).optional(),
  sourceTreeSha256: z.string().regex(/^[0-9a-f]{64}$/),
  transformVersion: z.string().min(1),
});

const targetRoleSchema = z.enum(["global", "project-root", "project-omp"]);
const sectionMapPolicySchema = z.enum([
  "include",
  "omit",
  "replace-with-overlay",
]);
// A classification gated to the committed source revision that introduced the
// section. Gated entries apply only while that exact revision is pinned; they
// are ignored for an earlier pinned source so strict v2 validation remains
// green for the current baseline, and they fail closed (SECTION_MAPPING_UNKNOWN
// or SECTION_UNMAPPED) if they are wrong once their revision is pinned.
const introducedRevisionSchema = z
  .string()
  .regex(/^[0-9a-f]{40}$/)
  .optional();
const includedSectionSchema = z
  .object({
    source: z.string().min(1),
    policy: z.literal("include"),
    owner: targetRoleSchema.optional(),
    splitTargets: z.array(targetRoleSchema).min(1).optional(),
    introducedRevision: introducedRevisionSchema,
  })
  .strict()
  .superRefine((entry, context) => {
    if ((entry.owner === undefined) === (entry.splitTargets === undefined)) {
      context.addIssue({
        code: "custom",
        message: "include requires exactly one of owner or splitTargets",
      });
    }
  });
const omittedSectionSchema = z
  .object({
    source: z.string().min(1),
    policy: z.literal("omit"),
    reason: z.string().min(1),
    introducedRevision: introducedRevisionSchema,
  })
  .strict();
const overlaidSectionSchema = z
  .object({
    source: z.string().min(1),
    policy: z.literal("replace-with-overlay"),
    owner: targetRoleSchema,
    overlay: z.enum(TARGETS),
    introducedRevision: introducedRevisionSchema,
  })
  .strict();
const sectionMapSchema = z
  .object({
    schemaVersion: z.literal(2),
    sections: z.array(
      z.discriminatedUnion("policy", [
        includedSectionSchema,
        omittedSectionSchema,
        overlaidSectionSchema,
      ]),
    ),
  })
  .strict();

export type TargetRole = z.infer<typeof targetRoleSchema>;
export type UpstreamLockV1 = z.infer<typeof upstreamLockSchema>;
export type StableManifest = z.infer<typeof stableManifestSchema>;
export type StableProvenance = z.infer<typeof stableProvenanceSchema>;

export interface StableManifestSnapshot {
  readonly manifest: StableManifest;
  readonly manifestSha256: string;
}

export const kitManifestSchema = z
  .object({
    schemaVersion: z.literal(1),
    sourceId: z.literal("sbtd-workflow-kit-upstream"),
    canonicalSourceUri: z.url(),
    resolvedRevision: z.string().regex(/^[0-9a-f]{40}$/),
    sourceTreeSha256: z.string().regex(/^[0-9a-f]{64}$/),
    transformVersion: z.string().min(1),
    overlayDigests: z.record(z.string(), z.string().regex(/^[0-9a-f]{64}$/)),
    generatedSha256: z.string().regex(/^[0-9a-f]{64}$/),
    targets: z.record(z.string(), z.string().regex(/^[0-9a-f]{64}$/)),
    profileCatalogSha256: z.string().regex(/^[0-9a-f]{64}$/),
    assets: z.record(z.string(), z.string().regex(/^[0-9a-f]{64}$/)),
    stableProvenance: stableProvenanceSchema,
  })
  .strict();

export type KitManifest = z.infer<typeof kitManifestSchema>;
export interface SyncReport {
  readonly added: readonly string[];
  readonly changed: readonly string[];
  readonly removed: readonly string[];
  readonly unmapped: readonly string[];
  readonly inputReadSet: {
    readonly sourceTreeSha256: string;
    readonly mappingSha256: string;
    readonly overlayDigests: Readonly<Record<string, string>>;
    readonly stableManifestSha256: string;
  };
  readonly generatedSha256: string;
}

export interface GeneratedKit {
  readonly targets: readonly (typeof TARGETS)[number][];
  readonly manifest: KitManifest;
  readonly syncReport: SyncReport;
}

export interface GenerateKitOptions {
  readonly packageRoot: string;
  readonly outputDirectory: string;
}

export class KitError extends Error {
  constructor(
    readonly code:
      | "SOURCE_DIGEST_MISMATCH"
      | "SECTION_UNMAPPED"
      | "SECTION_MAPPING_UNKNOWN"
      | "SECTION_MAPPING_CONFLICT"
      | "SECTION_OVERLAY_MISSING"
      | "SECTION_LEAKAGE"
      | "STABLE_MANIFEST_INVALID"
      | "STABLE_INSTALL_POLICY_INVALID"
      | "PROMOTION_DESTINATION_DIRTY"
      | "GENERATED_DRIFT"
      | "KIT_INPUT_INVALID"
      | "SOURCE_REPOSITORY_INVALID"
      | "SOURCE_REVISION_INVALID"
      | "STALE_PLAN"
      | "STAGED_PLUGIN_INVALID"
      | "TRANSACTION_FAILED"
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
    readonly details: Readonly<Record<string, unknown>> = {},
  ) {
    super(message);
    this.name = "KitError";
  }
}

interface MarkdownSection {
  readonly key: string;
  readonly sourcePath: string;
  readonly headingPath: readonly string[];
  readonly level: number;
  readonly start: number;
  readonly end: number;
}

interface SectionAssignment {
  readonly key: string;
  readonly policy: z.infer<typeof sectionMapPolicySchema>;
  readonly targets: readonly TargetRole[];
  readonly overlay?: (typeof TARGETS)[number];
}

export function sha256(bytes: string | Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function digest(bytes: string | Uint8Array): string {
  return sha256(bytes);
}

function replaceUniqueText(
  text: string,
  anchor: string,
  replacement: string,
  description: string,
): string {
  const first = text.indexOf(anchor);
  if (first === -1 || text.indexOf(anchor, first + anchor.length) !== -1) {
    throw new KitError(
      "KIT_INPUT_INVALID",
      `expected exactly one ${description} anchor in vendored runtime asset`,
    );
  }
  return `${text.slice(0, first)}${replacement}${text.slice(first + anchor.length)}`;
}

function packageRuntimeCatalog(catalog: string): string {
  return replaceUniqueText(
    catalog,
    `    {
      "id": "project:gitignore",
      "kind": "project-template",
      "source": "templates/project/.gitignore",
      "targetRole": "project-gitignore"
    }`,
    `    {
      "id": "project:gitignore",
      "kind": "project-template",
      "source": "templates/project/gitignore.template",
      "targetRole": "project-gitignore"
    }`,
    "project gitignore catalog entry",
  );
}

function packageRuntimeOnboard(onboard: string): string {
  const withCopyHelper = replaceUniqueText(
    onboard,
    `def compare_tree(
    source: Path, target: Path, ignored_names: set[str] | None = None
) -> list[str]:`,
    `def restored_template_relative_path(path: Path) -> Path:
    if path.name == "gitignore.template":
        return path.with_name(".gitignore")
    return path


def copy_tree(
    source: Path, target: Path, restore_template_names: bool = False
) -> None:
    shutil.copytree(source, target)
    if not restore_template_names:
        return
    for template in list(target.rglob("gitignore.template")):
        template.rename(template.with_name(".gitignore"))

def compare_tree(
    source: Path,
    target: Path,
    ignored_names: set[str] | None = None,
    restore_template_names: bool = False,
) -> list[str]:`,
    "onboard template copy helper",
  );
  const withCompareMapping = replaceUniqueText(
    withCopyHelper,
    "        other = target / rel",
    `        target_rel = (
            restored_template_relative_path(rel)
            if restore_template_names
            else rel
        )
        other = target / target_rel`,
    "onboard template comparison",
  );
  const withOperationCompareMapping = replaceUniqueText(
    withCompareMapping,
    "    return compare_tree(operation.source, operation.target)",
    `    return compare_tree(
        operation.source,
        operation.target,
        restore_template_names=operation.source.parent.name == "skills",
    )`,
    "onboard template tree verification",
  );
  const withOperationCopyMapping = replaceUniqueText(
    withOperationCompareMapping,
    "    shutil.copytree(operation.source, operation.target)",
    `    copy_tree(
        operation.source,
        operation.target,
        restore_template_names=operation.source.parent.name == "skills",
    )`,
    "onboard template tree copy",
  );
  return withOperationCopyMapping;
}
function packageRuntimeAssetPath(
  pythonOnboardRoot: string,
  source: string,
): string {
  const path = relative(pythonOnboardRoot, source).split(sep).join("/");
  return path.startsWith("templates/") && basename(source) === ".gitignore"
    ? `${path.slice(0, -".gitignore".length)}gitignore.template`
    : path;
}

async function listFiles(root: string): Promise<string[]> {
  const paths: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isSymbolicLink()) {
      throw new KitError(
        "KIT_INPUT_INVALID",
        "vendored source must not contain symbolic links",
        { path },
      );
    }
    if (entry.isDirectory()) {
      paths.push(...(await listFiles(path)));
    } else if (entry.isFile()) {
      paths.push(path);
    }
  }
  return paths.sort();
}

export async function sourceTreeSha256(sourceRoot: string): Promise<string> {
  const hasher = createHash("sha256");
  for (const path of await listFiles(sourceRoot)) {
    hasher.update(relative(sourceRoot, path).split(sep).join("/"));
    hasher.update("\0");
    hasher.update(await readFile(path));
  }
  return hasher.digest("hex");
}

export async function readUpstreamLock(
  packageRoot: string,
): Promise<UpstreamLockV1> {
  try {
    return upstreamLockSchema.parse(
      JSON.parse(
        await readFile(join(packageRoot, "upstream.lock.json"), "utf8"),
      ),
    );
  } catch (cause) {
    throw new KitError("KIT_INPUT_INVALID", "Kit upstream lock is invalid", {
      cause: cause instanceof Error ? cause.message : "unknown",
    });
  }
}

function comparePathParts(left: string, right: string): number {
  const leftParts = left.split("/");
  const rightParts = right.split("/");
  const shared = Math.min(leftParts.length, rightParts.length);
  for (let index = 0; index < shared; index += 1) {
    const leftPart = leftParts[index] ?? "";
    const rightPart = rightParts[index] ?? "";
    if (leftPart < rightPart) return -1;
    if (leftPart > rightPart) return 1;
  }
  return leftParts.length - rightParts.length;
}

async function stableSkillTreeSha256(root: string): Promise<string> {
  const hasher = createHash("sha256");
  const files = (await listFiles(root))
    .map((path) => relative(root, path).split(sep).join("/"))
    .sort(comparePathParts);
  for (const path of files) {
    const pathBytes = Buffer.from(path, "utf8");
    const pathLength = Buffer.alloc(8);
    pathLength.writeBigUInt64BE(BigInt(pathBytes.length));
    hasher.update(pathLength);
    hasher.update(pathBytes);
    const content = await readFile(join(root, path));
    const contentLength = Buffer.alloc(8);
    contentLength.writeBigUInt64BE(BigInt(content.length));
    hasher.update(contentLength);
    hasher.update(content);
  }
  return hasher.digest("hex");
}

function assertContainedStablePath(path: string, description: string): void {
  if (
    path.startsWith("/") ||
    path.split("/").some((segment) => segment === "" || segment === "..")
  ) {
    throw new KitError(
      "STABLE_MANIFEST_INVALID",
      `stable External Skills manifest contains an unsafe ${description}`,
      { path },
    );
  }
}

export async function readStableManifest(
  sourceRoot: string,
): Promise<StableManifestSnapshot> {
  const manifestPath = join(sourceRoot, STABLE_MANIFEST_SOURCE_PATH);
  const bytes = await readFile(manifestPath).catch(() => undefined);
  if (bytes === undefined) {
    throw new KitError(
      "STABLE_MANIFEST_INVALID",
      "stable External Skills manifest is missing from the pinned source",
      { path: STABLE_MANIFEST_SOURCE_PATH },
    );
  }
  let manifest: StableManifest;
  try {
    manifest = stableManifestSchema.parse(JSON.parse(bytes.toString("utf8")));
  } catch (cause) {
    throw new KitError(
      "STABLE_MANIFEST_INVALID",
      "stable External Skills manifest is invalid",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
  const stableRoot = dirname(manifestPath);
  for (const [name, skill] of Object.entries(manifest.skills)) {
    assertContainedStablePath(skill.stablePath, "Skill stablePath");
    const skillRoot = join(stableRoot, skill.stablePath);
    const entry = await stat(skillRoot).catch(() => undefined);
    if (entry === undefined || !entry.isDirectory()) {
      throw new KitError(
        "STABLE_MANIFEST_INVALID",
        "stable External Skill tree is missing from the pinned source",
        { skill: name, stablePath: skill.stablePath },
      );
    }
    const actual = await stableSkillTreeSha256(skillRoot);
    if (actual !== skill.treeSha256) {
      throw new KitError(
        "STABLE_MANIFEST_INVALID",
        "stable External Skill tree digest drifted from the manifest",
        { skill: name, expected: skill.treeSha256, actual },
      );
    }
  }
  for (const [repositoryId, repository] of Object.entries(
    manifest.repositories,
  )) {
    for (const licenseFile of repository.licenseFiles) {
      assertContainedStablePath(licenseFile.stablePath, "license stablePath");
      const entry = await stat(join(stableRoot, licenseFile.stablePath)).catch(
        () => undefined,
      );
      if (entry === undefined || !entry.isFile()) {
        throw new KitError(
          "STABLE_MANIFEST_INVALID",
          "stable External Skills license file is missing from the pinned source",
          { repository: repositoryId, stablePath: licenseFile.stablePath },
        );
      }
    }
  }
  return { manifest, manifestSha256: sha256(bytes) };
}

function deriveStableProvenance(
  snapshot: StableManifestSnapshot,
): StableProvenance {
  return {
    stableSet: snapshot.manifest.stableSet,
    manifestSha256: snapshot.manifestSha256,
    repositories: Object.fromEntries(
      Object.entries(snapshot.manifest.repositories).map(
        ([name, repository]) => [
          name,
          {
            url: repository.url,
            revision: repository.revision,
            license: repository.license,
          },
        ],
      ),
    ),
  };
}

function parseSections(
  sourcePath: string,
  markdown: string,
): MarkdownSection[] {
  const sections: MarkdownSection[] = [];
  const lines = markdown.split(/\r?\n/);
  const headings: { level: number; title: string; index: number }[] = [];
  let fenced = false;

  for (const [index, line] of lines.entries()) {
    if (/^\s*(```|~~~)/.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) continue;
    const match = /^(#{1,6})\s+(.+?)\s*$/.exec(line);
    if (match === null) continue;
    const marker = match[1];
    const title = match[2];
    if (marker === undefined || title === undefined) continue;
    headings.push({ level: marker.length, title, index });
  }

  for (const [position, heading] of headings.entries()) {
    const headingPath: string[] = [];
    for (let level = 1; level <= heading.level; level += 1) {
      const ancestor = headings
        .slice(0, position + 1)
        .reverse()
        .find((candidate) => candidate.level === level);
      if (ancestor !== undefined) headingPath.push(ancestor.title);
    }
    const next = headings
      .slice(position + 1)
      .find((candidate) => candidate.level <= heading.level);
    sections.push({
      key: `${sourcePath}::${headingPath.join(" > ")}`,
      sourcePath,
      headingPath,
      level: heading.level,
      start: heading.index,
      end: next?.index ?? lines.length,
    });
  }
  return sections;
}

function assignmentsFor(
  sections: readonly MarkdownSection[],
  rawMap: z.infer<typeof sectionMapSchema>,
  pinnedRevision: string,
): ReadonlyMap<string, SectionAssignment> {
  const targetForRole: Record<TargetRole, (typeof TARGETS)[number]> = {
    global: "AGENTS.global.md",
    "project-root": "AGENTS.project-root.md",
    "project-omp": "AGENTS.project-omp.md",
  };
  const entries = new Map<string, SectionAssignment>();
  for (const entry of rawMap.sections) {
    if (
      entry.introducedRevision !== undefined &&
      entry.introducedRevision !== pinnedRevision
    ) {
      continue;
    }
    if (entries.has(entry.source)) {
      throw new KitError(
        "SECTION_MAPPING_CONFLICT",
        "a source section has multiple mapping entries",
        { source: entry.source },
      );
    }
    if (
      entry.policy === "replace-with-overlay" &&
      entry.overlay !== targetForRole[entry.owner]
    ) {
      throw new KitError(
        "SECTION_MAPPING_CONFLICT",
        "replace-with-overlay must use its owner's target overlay",
        { source: entry.source, owner: entry.owner, overlay: entry.overlay },
      );
    }
    const targets =
      entry.policy === "include"
        ? entry.owner === undefined
          ? (entry.splitTargets ?? [])
          : [entry.owner]
        : entry.policy === "replace-with-overlay"
          ? [entry.owner]
          : [];
    if (new Set(targets).size !== targets.length) {
      throw new KitError(
        "SECTION_MAPPING_CONFLICT",
        "include splitTargets must not repeat a target",
        { source: entry.source },
      );
    }
    entries.set(entry.source, {
      key: entry.source,
      policy: entry.policy,
      targets,
      ...(entry.policy === "replace-with-overlay"
        ? { overlay: entry.overlay }
        : {}),
    });
  }

  const sourceKeys = new Set(sections.map((section) => section.key));
  const unknown = [...entries.keys()]
    .filter((key) => !sourceKeys.has(key))
    .sort();
  if (unknown.length > 0) {
    throw new KitError(
      "SECTION_MAPPING_UNKNOWN",
      "section mapping contains keys not present in the pinned source",
      {
        unknown,
        syncReport: { added: [], changed: [], removed: unknown, unmapped: [] },
      },
    );
  }
  const unmapped = sections
    .map((section) => section.key)
    .filter((key) => !entries.has(key))
    .sort();
  if (unmapped.length > 0) {
    throw new KitError(
      "SECTION_UNMAPPED",
      "pinned source contains unmapped sections",
      {
        unmapped,
        syncReport: { added: unmapped, changed: [], removed: [], unmapped },
      },
    );
  }
  for (const section of sections.filter((candidate) => candidate.level > 2)) {
    const parent = sections
      .filter(
        (candidate) =>
          candidate.sourcePath === section.sourcePath &&
          candidate.level >= 2 &&
          candidate.level < section.level &&
          candidate.headingPath.every(
            (part, index) => section.headingPath[index] === part,
          ),
      )
      .sort((left, right) => right.level - left.level)[0];
    if (parent === undefined) continue;
    const parentAssignment = entries.get(parent.key);
    const sectionAssignment = entries.get(section.key);
    if (
      parentAssignment === undefined ||
      sectionAssignment === undefined ||
      parentAssignment.policy !== sectionAssignment.policy ||
      parentAssignment.targets.join("\0") !==
        sectionAssignment.targets.join("\0") ||
      parentAssignment.overlay !== sectionAssignment.overlay
    ) {
      throw new KitError(
        "SECTION_MAPPING_CONFLICT",
        "nested sections must inherit the level-2 policy and targets",
        { parent: parent.key, section: section.key },
      );
    }
  }
  return entries;
}

function renderProjectTarget(
  role: "project-root" | "project-omp",
  markdown: string,
  sections: readonly MarkdownSection[],
  assignments: ReadonlyMap<string, SectionAssignment>,
  lock: UpstreamLockV1,
): string {
  const lines = markdown.split(/\r?\n/);
  const topLevel = sections.filter((section) => section.level === 2);
  const rendered = topLevel
    .filter((section) => {
      const assignment = assignments.get(section.key);
      return (
        assignment?.policy === "include" && assignment.targets.includes(role)
      );
    })
    .map((section) =>
      lines.slice(section.start, section.end).join("\n").trimEnd(),
    )
    .join("\n\n");
  const marker = [
    `<!-- KPi template: ${role}; sourceId=${lock.sourceId}; revision=${lock.resolvedRevision}; transform=${lock.transformVersion} -->`,
    role === "project-omp"
      ? "@../AGENTS.md\n\n# OMP Project Adapter\n\nThis adapter preserves Root Project Facts through the import above."
      : "# Root Project Facts",
  ].join("\n");
  return `${marker}\n\n${rendered}\n`;
}

function renderGlobalTarget(
  markdown: string,
  sections: readonly MarkdownSection[],
  assignments: ReadonlyMap<string, SectionAssignment>,
): string {
  const lines = markdown.split(/\r?\n/);
  const topLevel = sections.filter((section) => section.level === 2);
  const firstTopLevel = topLevel[0]?.start ?? lines.length;
  const documentHeader = lines.slice(0, firstTopLevel).join("\n").trimEnd();
  const rendered = topLevel
    .filter((section) => {
      const assignment = assignments.get(section.key);
      return (
        assignment?.policy === "include" &&
        assignment.targets.includes("global")
      );
    })
    .map((section) =>
      lines.slice(section.start, section.end).join("\n").trimEnd(),
    )
    .join("\n\n");
  return `${documentHeader}\n\n${rendered}\n`;
}

function profileCatalog(lock: UpstreamLockV1): string {
  return `${JSON.stringify(
    {
      schemaVersion: 1,
      kitRevision: lock.resolvedRevision,
      profiles: [
        {
          id: "omp-p0-standard-v1",
          required: [
            "plugin-kit-alignment",
            "global-agents",
            "project-root-agents",
            "project-omp-adapter",
            "always-on-baseline",
            "core-gate-skills",
          ],
          optional: [
            "trellis",
            "gitnexus",
            "bdd-tdd",
            "ui",
            "web-mobile-e2e",
            "release",
          ],
        },
      ],
    },
    null,
    2,
  )}\n`;
}

async function readOverlay(
  packageRoot: string,
  target: (typeof TARGETS)[number],
): Promise<string> {
  try {
    return await readFile(join(packageRoot, "overlays", target), "utf8");
  } catch (cause) {
    if (cause instanceof Error && "code" in cause && cause.code === "ENOENT")
      return "";
    throw new KitError("KIT_INPUT_INVALID", "target overlay cannot be read", {
      target,
      cause: cause instanceof Error ? cause.message : "unknown",
    });
  }
}

async function parseInputs(packageRoot: string): Promise<{
  lock: UpstreamLockV1;
  mapping: z.infer<typeof sectionMapSchema>;
}> {
  try {
    const [rawLock, rawMapping] = await Promise.all([
      readFile(join(packageRoot, "upstream.lock.json"), "utf8"),
      readFile(join(packageRoot, "agents-section-map.yaml"), "utf8"),
    ]);
    return {
      lock: upstreamLockSchema.parse(JSON.parse(rawLock)),
      mapping: sectionMapSchema.parse(parseYaml(rawMapping)),
    };
  } catch (cause) {
    if (cause instanceof KitError) throw cause;
    throw new KitError(
      "KIT_INPUT_INVALID",
      "Kit lock or section mapping is invalid",
      { cause: cause instanceof Error ? cause.message : "unknown" },
    );
  }
}

function assertExcludedSectionsAbsent(
  targetContent: Record<(typeof TARGETS)[number], string>,
  sourceTexts: readonly { sourcePath: string; markdown: string }[],
  sections: readonly MarkdownSection[],
  assignments: ReadonlyMap<string, SectionAssignment>,
): void {
  const linesBySource = new Map(
    sourceTexts.map(({ sourcePath, markdown }) => [
      sourcePath,
      markdown.split(/\r?\n/),
    ]),
  );
  for (const section of sections) {
    const assignment = assignments.get(section.key);
    if (assignment === undefined || assignment.policy === "include") continue;
    const body = (linesBySource.get(section.sourcePath) ?? [])
      .slice(section.start, section.end)
      .join("\n")
      .trimEnd();
    if (body.length === 0) continue;
    for (const target of TARGETS) {
      if (targetContent[target].includes(body)) {
        throw new KitError(
          "SECTION_LEAKAGE",
          "an excluded source section appears verbatim in a projected AGENTS target",
          { section: section.key, policy: assignment.policy, target },
        );
      }
    }
  }
}

async function writeSnapshot(
  stage: string,
  packageRoot: string,
  lock: UpstreamLockV1,
  mapping: z.infer<typeof sectionMapSchema>,
): Promise<GeneratedKit> {
  const sourceRoot = join(packageRoot, SOURCE_ROOT);
  const actualDigest = await sourceTreeSha256(sourceRoot);
  if (actualDigest !== lock.sourceTreeSha256) {
    throw new KitError(
      "SOURCE_DIGEST_MISMATCH",
      "vendored source digest does not match upstream lock",
      {
        expected: lock.sourceTreeSha256,
        actual: actualDigest,
      },
    );
  }
  const stableSnapshot = await readStableManifest(sourceRoot);
  const stableProvenance = deriveStableProvenance(stableSnapshot);

  const sourceTexts = await Promise.all(
    AGENTS_SOURCES.map(async (sourcePath) => ({
      sourcePath,
      markdown: await readFile(join(sourceRoot, sourcePath), "utf8"),
    })),
  );
  const sections = sourceTexts.flatMap(({ sourcePath, markdown }) =>
    parseSections(sourcePath, markdown),
  );
  const assignments = assignmentsFor(sections, mapping, lock.resolvedRevision);
  for (const assignment of assignments.values()) {
    if (assignment.policy !== "replace-with-overlay") continue;
    if (assignment.overlay === undefined) {
      throw new KitError(
        "KIT_INPUT_INVALID",
        "replace-with-overlay requires a target overlay",
        { source: assignment.key },
      );
    }
    const overlay = await readOverlay(packageRoot, assignment.overlay);
    if (overlay.length === 0) {
      throw new KitError(
        "SECTION_OVERLAY_MISSING",
        "replace-with-overlay requires a non-empty target overlay",
        { source: assignment.key, overlay: assignment.overlay },
      );
    }
  }
  const global = sourceTexts.find(({ sourcePath }) =>
    sourcePath.endsWith("AGENTS.global.md"),
  );
  const project = sourceTexts.find(({ sourcePath }) =>
    sourcePath.endsWith("AGENTS.project.md"),
  );
  if (global === undefined || project === undefined)
    throw new KitError(
      "KIT_INPUT_INVALID",
      "required AGENTS source is missing",
    );

  const targetContent: Record<(typeof TARGETS)[number], string> = {
    "AGENTS.global.md": renderGlobalTarget(
      global.markdown,
      sections.filter((section) => section.sourcePath === global.sourcePath),
      assignments,
    ),
    "AGENTS.project-root.md": renderProjectTarget(
      "project-root",
      project.markdown,
      sections.filter((section) => section.sourcePath === project.sourcePath),
      assignments,
      lock,
    ),
    "AGENTS.project-omp.md": renderProjectTarget(
      "project-omp",
      project.markdown,
      sections.filter((section) => section.sourcePath === project.sourcePath),
      assignments,
      lock,
    ),
  };
  const overlayDigests: Record<string, string> = {};
  for (const target of TARGETS) {
    const overlay = await readOverlay(packageRoot, target);
    if (overlay.length === 0) continue;
    targetContent[target] =
      `${targetContent[target].trimEnd()}\n\n${overlay.trimEnd()}\n`;
    overlayDigests[target] = digest(overlay);
  }
  assertExcludedSectionsAbsent(
    targetContent,
    sourceTexts,
    sections,
    assignments,
  );
  const catalog = profileCatalog(lock);
  const staticAssetSources = {
    "third-party/sbtd-workflow-onboard/LICENSE":
      "sbtd-workflow-onboard/LICENSE",
    "third-party/sbtd-workflow-onboard/NOTICE": "sbtd-workflow-onboard/NOTICE",
  } as const;
  const stableNotices = Object.entries(stableSnapshot.manifest.repositories)
    .sort(([left], [right]) => left.localeCompare(right))
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
  const thirdPartyNotices = [
    "# Third-Party Notices",
    "",
    "## SBTD Workflow Onboard",
    "",
    `- Source: ${lock.canonicalSourceUri}@${lock.resolvedRevision}`,
    "- License: Apache-2.0",
    "- Retained license: third-party/sbtd-workflow-onboard/LICENSE",
    "- Retained notice: third-party/sbtd-workflow-onboard/NOTICE",
    "",
    `## Stable External Skills (stable set ${stableSnapshot.manifest.stableSet})`,
    "",
    stableNotices,
    "",
  ].join("\n");
  const snapshotAssets: Record<string, string | Uint8Array> = {
    ...targetContent,
    "catalog.json": catalog,
    LICENSE: await readFile(join(packageRoot, "LICENSE")),
    "THIRD_PARTY_NOTICES.md": thirdPartyNotices,
  };
  const pythonOnboardRoot = join(sourceRoot, "sbtd-workflow-onboard");
  for (const source of await listFiles(pythonOnboardRoot)) {
    const runtimePath = packageRuntimeAssetPath(pythonOnboardRoot, source);
    const content = await readFile(source);
    snapshotAssets[`onboard/runtime/${runtimePath}`] =
      runtimePath === "catalog.json"
        ? packageRuntimeCatalog(content.toString("utf8"))
        : runtimePath === "scripts/onboard.py"
          ? packageRuntimeOnboard(content.toString("utf8"))
          : content;
  }
  await Promise.all(
    Object.entries(staticAssetSources).map(async ([target, source]) => {
      snapshotAssets[target] = await readFile(join(sourceRoot, source));
    }),
  );
  const targetDigests = Object.fromEntries(
    TARGETS.map((target) => [target, digest(targetContent[target])]),
  ) as Record<(typeof TARGETS)[number], string>;
  const assetDigests = Object.fromEntries(
    Object.entries(snapshotAssets)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([target, content]) => [target, digest(content)]),
  );
  const generatedDigest = digest(
    [
      ...Object.entries(assetDigests)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([target, assetDigest]) => `${target}\0${assetDigest}`),
      ...Object.keys(overlayDigests)
        .sort()
        .map((target) => `overlay:${target}\0${overlayDigests[target]}`),
    ].join("\n"),
  );
  const manifest = kitManifestSchema.parse({
    schemaVersion: 1,
    sourceId: lock.sourceId,
    canonicalSourceUri: lock.canonicalSourceUri,
    resolvedRevision: lock.resolvedRevision,
    sourceTreeSha256: actualDigest,
    transformVersion: lock.transformVersion,
    overlayDigests,
    generatedSha256: generatedDigest,
    targets: targetDigests,
    profileCatalogSha256: digest(catalog),
    assets: assetDigests,
    stableProvenance,
  });
  const syncReport: SyncReport = {
    added: [],
    changed: [],
    removed: [],
    unmapped: [],
    inputReadSet: {
      sourceTreeSha256: actualDigest,
      mappingSha256: digest(
        await readFile(join(packageRoot, "agents-section-map.yaml"), "utf8"),
      ),
      overlayDigests,
      stableManifestSha256: stableSnapshot.manifestSha256,
    },
    generatedSha256: generatedDigest,
  };

  await mkdir(stage, { recursive: true });
  await Promise.all(
    Object.entries(snapshotAssets).map(async ([target, content]) => {
      const targetPath = join(stage, target);
      await mkdir(dirname(targetPath), { recursive: true });
      await writeFile(targetPath, content);
    }),
  );
  await Promise.all([
    writeFile(
      join(stage, "manifest.json"),
      `${JSON.stringify(manifest, null, 2)}\n`,
      "utf8",
    ),
    writeFile(
      join(stage, "sync-report.json"),
      `${JSON.stringify(syncReport, null, 2)}\n`,
      "utf8",
    ),
  ]);
  return { targets: TARGETS, manifest, syncReport };
}

export async function generateKit(
  options: GenerateKitOptions,
): Promise<GeneratedKit> {
  const packageRoot = resolve(options.packageRoot);
  const outputDirectory = resolve(options.outputDirectory);
  const outputParent = dirname(outputDirectory);
  await mkdir(outputParent, { recursive: true });
  const stage = join(outputParent, `.${randomUUID()}.stage`);
  const backup = join(outputParent, `.${randomUUID()}.previous`);
  const { lock, mapping } = await parseInputs(packageRoot);

  try {
    const result = await writeSnapshot(stage, packageRoot, lock, mapping);
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

export async function checkGenerated(
  options: GenerateKitOptions,
): Promise<void> {
  const root = join(
    dirname(resolve(options.outputDirectory)),
    `.${randomUUID()}.check`,
  );
  await mkdir(root, { recursive: true });
  try {
    await generateKit({ ...options, outputDirectory: root });
    const expectedFiles = (await listFiles(root))
      .map((path) => relative(root, path).split(sep).join("/"))
      .sort();
    const actualRoot = resolve(options.outputDirectory);
    const actualFiles = (await listFiles(actualRoot))
      .map((path) => relative(actualRoot, path).split(sep).join("/"))
      .sort();
    if (expectedFiles.join("\0") !== actualFiles.join("\0")) {
      throw new KitError(
        "GENERATED_DRIFT",
        "generated output has missing or unexpected assets",
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
          "generated output differs from verified Kit",
          { target },
        );
      }
    }
  } finally {
    await rm(root, { force: true, recursive: true });
  }
}
