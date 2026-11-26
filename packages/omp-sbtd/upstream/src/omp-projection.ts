import { createHash, randomUUID } from "node:crypto";
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
const PHOSPHOR_METADATA_PATH = `${STABLE_SKILLS_PREFIX}ui-ux-pro-max/data/phosphor-icons-upstream.json`;
const PHOSPHOR_METADATA_SHA256 =
  "2399325233b277b5c97a80e6a5e8941154f5d057beee4e7613db87c87d700236";
// Exact package/LICENSE bytes from @phosphor-icons/core@2.1.1.
// CRLF preservation is the byte contract, not a license interpretation.
const PHOSPHOR_CORE_LICENSE = [
  "MIT License",
  "",
  "Copyright (c) 2023 Phosphor Icons",
  "",
  "Permission is hereby granted, free of charge, to any person obtaining a copy",
  'of this software and associated documentation files (the "Software"), to deal',
  "in the Software without restriction, including without limitation the rights",
  "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
  "copies of the Software, and to permit persons to whom the Software is",
  "furnished to do so, subject to the following conditions:",
  "",
  "The above copyright notice and this permission notice shall be included in all",
  "copies or substantial portions of the Software.",
  "",
  'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR',
  "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,",
  "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE",
  "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER",
  "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,",
  "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE",
  "SOFTWARE.",
  "",
].join("\r\n");
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
  readonly sourceSelection?: DomainSelectionSummary | R1ManualsSummary;
}

export interface GeneratedOmpProjection {
  readonly manifest: OmpProjectionManifestV2;
  readonly report: OmpProjectionReport;
}

export interface GenerateOmpProjectionOptions {
  readonly packageRoot: string;
  readonly canonicalDirectory: string;
  readonly outputDirectory: string;
  readonly sourceSelection?: "domain-modeling" | "r1-manuals";
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

const DOMAIN_SOURCE_ROOT = "omp-source-selections/domain-modeling";
const DOMAIN_SKILL_PREFIX = `${STABLE_SKILLS_PREFIX}domain-modeling/`;
const DOMAIN_BASE_MANIFEST_SHA256 =
  "97c71dddf82415b936ae07314e8057183a1a8d0e17e32b02cbc6626fc6f49404";
const DOMAIN_BASE_POLICY_SHA256 =
  "1dfe7f19f6118b4303484163cca691589dd79dac3d33ebe11ce04dec2d331a6f";
const domainFileIdentitySchema = z
  .object({
    blob: z.string().regex(/^[0-9a-f]{40}$/),
    mode: z.literal("100644"),
    sha256: sha256HexSchema,
    bytes: z.number().int().nonnegative(),
  })
  .strict();
const domainSelectionSchema = z
  .object({
    schemaVersion: z.literal(1),
    scope: z.literal("domain-modeling-only"),
    owner: z.literal("third-party"),
    supplier: z
      .object({
        repository: z.literal("https://github.com/KunoLu/640-skills"),
        revision: z.literal("3c835303c23d59d3157ca84121a92f1bd87d4997"),
        path: z.literal(
          "sbtd-workflow-onboard/assets/external-skills/stable/skills/domain-modeling",
        ),
      })
      .strict(),
    origin: z
      .object({
        repository: z.literal("https://github.com/mattpocock/skills.git"),
        sourceSubpath: z.literal("skills/engineering/domain-modeling"),
        license: z.literal("MIT"),
      })
      .strict(),
    base: z
      .object({
        canonicalRevision: z.literal(
          "1d82494d74f6df9bca7dccef2da409f87091883e",
        ),
        canonicalManifestSha256: z.literal(DOMAIN_BASE_MANIFEST_SHA256),
        policySha256: z.literal(DOMAIN_BASE_POLICY_SHA256),
        repositoryKey: z.literal("mattpocock-skills"),
        repositoryRevision: z.literal(
          "3cca18b368ae95cdbdebbff572ccafa662551015",
        ),
        treeSha256: z.literal(
          "731ecd11825453ec3d813ac26e7a082bb458bc332781c6dba18d7004468139d7",
        ),
        absent: z.tuple([z.literal("GLOSSARY-FORMAT.md")]),
      })
      .strict(),
    target: z
      .object({
        repositoryKey: z.literal("mattpocock-skills-domain-modeling"),
        repositoryRevision: z.literal(
          "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d",
        ),
        treeSha256: z.literal(
          "c0bd13ce078a3c8eb5507fc9067165dad89b10f11b33b26e29a5c62f9c840bd2",
        ),
        absent: z.tuple([z.literal("CONTEXT-FORMAT.md")]),
      })
      .strict(),
    license: domainFileIdentitySchema.extend({
      path: z.literal("licenses/mattpocock-skills-LICENSE"),
      blob: z.literal("f1dd2c09108dde1a5f56097cee8461b3ea834499"),
      sha256: z.literal(
        "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5",
      ),
      bytes: z.literal(1068),
    }),
    files: z
      .array(
        z
          .object({
            path: z.enum([
              "ADR-FORMAT.md",
              "CONTEXT-FORMAT.md",
              "GLOSSARY-FORMAT.md",
              "SKILL.md",
              "agents/openai.yaml",
            ]),
            operation: z.enum(["keep", "delete", "add", "replace"]),
            before: domainFileIdentitySchema.nullable(),
            target: domainFileIdentitySchema.nullable(),
          })
          .strict(),
      )
      .length(5),
  })
  .strict();
type DomainSelectionRecord = z.infer<typeof domainSelectionSchema>;
interface DomainSelectionReceipt {
  readonly kind: "mixed-source";
  readonly scope: "domain-modeling-only";
  readonly base: {
    readonly canonicalRevision: string;
    readonly canonicalManifestSha256: string;
    readonly policySha256: string;
    readonly stableSet: string;
    readonly promotedAt: string;
  };
  readonly inputPath: string;
  readonly inputSha256: string;
  readonly record: DomainSelectionRecord;
}
interface DomainSelectionSummary {
  readonly scope: "domain-modeling-only";
  readonly countsAndDecisions: "base-canonical-policy";
  readonly ledgerAssetPath: string;
  readonly inputSha256: string;
  readonly added: readonly string[];
  readonly removed: readonly string[];
  readonly replaced: readonly string[];
}

const R1_SOURCE_ROOT = "omp-source-selections/r1-manuals";
const R1_PRESENTATION_PATH =
  "onboard/runtime/templates/skills/sbtd-task/references/presentation.md";
// Fixed before trees from the canonical manifest and target trees from the
// supplier MANIFEST at 3c835303, independently matched to Matt's 4ae2317 bytes.
const R1_MANUAL_TREES = {
  grilling: {
    sourceSubpath: "skills/productivity/grilling",
    before: "b0af4cb93507011cab704853dc540ae142dec2a1256d374a38f4f196a04f7b50",
    target: "3a7559839f45dfa4491f045d56647148c2b90f0e5ce0b5355301ef0e6d1bc428",
  },
  "to-tickets": {
    sourceSubpath: "skills/engineering/to-tickets",
    before: "7d82d3f4b50f4f57bafc8e361cdf6b06fde6f3b940bbd13199a184e98f0d34c4",
    target: "98422855972ffb35bf33ce3eee1c1255f58e81cf801d6d3fc0185bb8e0351839",
  },
} as const;
const r1ManualsSelectionSchema = z
  .object({
    schemaVersion: z.literal(1),
    scope: z.literal("r1-manuals"),
    owner: domainSelectionSchema.shape.owner,
    supplier: domainSelectionSchema.shape.supplier.extend({
      path: z.literal("sbtd-workflow-onboard/assets/external-skills/stable"),
    }),
    origin: domainSelectionSchema.shape.origin.omit({ sourceSubpath: true }),
    base: domainSelectionSchema.shape.base.omit({
      treeSha256: true,
      absent: true,
    }),
    target: domainSelectionSchema.shape.target
      .omit({ treeSha256: true, absent: true })
      .extend({ repositoryKey: z.literal("mattpocock-skills-r1-manuals") }),
    domainSelection: z
      .object({
        inputPath: z.literal(
          "omp-source-selections/domain-modeling/selection.json",
        ),
        inputSha256: z.literal(
          "6cb1e695b18e76aa771be1ab052085878763a96197205bc4a0f5874384814684",
        ),
      })
      .strict(),
    license: domainSelectionSchema.shape.license,
    skills: z
      .array(
        z
          .object({
            name: z.enum(["grilling", "to-tickets"]),
            sourceSubpath: z.enum([
              "skills/productivity/grilling",
              "skills/engineering/to-tickets",
            ]),
            beforeTreeSha256: sha256HexSchema,
            targetTreeSha256: sha256HexSchema,
            files: z.tuple([
              z
                .object({
                  path: z.literal("SKILL.md"),
                  operation: z.literal("replace"),
                  before: domainFileIdentitySchema,
                  target: domainFileIdentitySchema,
                })
                .strict(),
              z
                .object({
                  path: z.literal("agents/openai.yaml"),
                  operation: z.literal("keep"),
                  before: domainFileIdentitySchema,
                  target: domainFileIdentitySchema,
                })
                .strict(),
            ]),
          })
          .strict(),
      )
      .length(2),
    presentation: z
      .object({
        path: z.literal(R1_PRESENTATION_PATH),
        supplierPath: z.literal(
          "sbtd-workflow-onboard/templates/skills/sbtd-task/references/presentation.md",
        ),
        owner: z.literal("kpi"),
        license: z.literal("Apache-2.0"),
        operation: z.literal("replace"),
        target: domainFileIdentitySchema.extend({
          blob: z.literal("b4e12e1775c98915b816a69a082557d466166245"),
          sha256: z.literal(
            "3a9be511b307210f9ed3a4d5f793a9ed07854652871e05deac07bdab745cf7f5",
          ),
          bytes: z.literal(6271),
        }),
      })
      .strict(),
  })
  .strict();
type R1ManualsRecord = z.infer<typeof r1ManualsSelectionSchema>;
interface R1SourceOperation {
  readonly path: string;
  readonly operation: "add" | "delete" | "replace";
  readonly source: "domain-modeling" | "r1-manuals" | "omp-overlay";
  readonly targetSha256: string | null;
}
type R1FinalOwnership = Record<
  string,
  "mattpocock-skills" | "mattpocock-skills-r1-manuals"
>;
interface R1ManualsReceipt
  extends Omit<DomainSelectionReceipt, "scope" | "record"> {
  readonly scope: "r1-manuals";
  readonly domain: {
    readonly role: "validated-component-input";
    readonly receipt: DomainSelectionReceipt;
  };
  readonly record: R1ManualsRecord;
  readonly sourceOperations: readonly R1SourceOperation[];
  readonly finalOwnership: Readonly<R1FinalOwnership>;
}
interface R1ManualsSummary extends Omit<DomainSelectionSummary, "scope"> {
  readonly scope: "r1-manuals";
  readonly sourceOperations: readonly R1SourceOperation[];
  readonly finalOwnership: Readonly<R1FinalOwnership>;
}

function requireDomainSource(
  condition: unknown,
  reason: string,
  selection: "domain-modeling" | "r1-manuals" = "domain-modeling",
): asserts condition {
  if (!condition) {
    throw projectionError(
      "PROJECTION_POLICY_INVALID",
      `${selection} source selection is invalid`,
      { selection, reason },
    );
  }
}

async function readDomainSourceFile(
  packageRoot: string,
  relativePath: string,
  selection: "domain-modeling" | "r1-manuals" = "domain-modeling",
): Promise<Buffer> {
  let current = packageRoot;
  const segments = relativePath.split("/");
  for (let index = -1; index < segments.length; index++) {
    if (index >= 0) current = join(current, segments[index] ?? "");
    const info = await lstat(current).catch(() => undefined);
    const last = index === segments.length - 1;
    requireDomainSource(
      info !== undefined &&
        !info.isSymbolicLink() &&
        (last ? info.isFile() : info.isDirectory()),
      `non-regular or missing source: ${relativePath}`,
      selection,
    );
    if (last) {
      requireDomainSource(
        (info.mode & 0o7777) === 0o644,
        `source mode differs: ${relativePath}`,
        selection,
      );
    }
  }
  return readFile(current);
}

function verifyDomainIdentity(
  bytes: Buffer,
  expected: z.infer<typeof domainFileIdentitySchema>,
  path: string,
  selection: "domain-modeling" | "r1-manuals" = "domain-modeling",
): void {
  const blob = createHash("sha1")
    .update(`blob ${bytes.length}\0`)
    .update(bytes)
    .digest("hex");
  requireDomainSource(
    bytes.length === expected.bytes &&
      sha256(bytes) === expected.sha256 &&
      blob === expected.blob,
    `file identity differs: ${path}`,
    selection,
  );
}

// Same path-segment ordering and length framing as index.ts's stable tree hash.
function domainTreeDigest(files: ReadonlyMap<string, Buffer>): string {
  const hash = createHash("sha256");
  const length = Buffer.alloc(8);
  const paths = [...files.keys()].sort((left, right) => {
    const a = left.split("/");
    const b = right.split("/");
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      if ((a[i] ?? "") < (b[i] ?? "")) return -1;
      if ((a[i] ?? "") > (b[i] ?? "")) return 1;
    }
    return a.length - b.length;
  });
  for (const path of paths) {
    const content = files.get(path);
    requireDomainSource(content !== undefined, "incomplete selected tree");
    const pathBytes = Buffer.from(path);
    length.writeBigUInt64BE(BigInt(pathBytes.length));
    hash.update(length).update(pathBytes);
    length.writeBigUInt64BE(BigInt(content.length));
    hash.update(length).update(content);
  }
  return hash.digest("hex");
}

async function selectDomainModelingSource(
  packageRoot: string,
  canonicalRoot: string,
  stable: CanonicalStableManifest,
  assets: Map<string, Buffer>,
  repositories: Readonly<Record<string, CanonicalStableRepository>>,
  skills: Readonly<Record<string, CanonicalStableSkill>>,
): Promise<{
  repositories: Readonly<Record<string, CanonicalStableRepository>>;
  skills: Readonly<Record<string, CanonicalStableSkill>>;
  receipt: DomainSelectionReceipt;
}> {
  const inputPath = `${DOMAIN_SOURCE_ROOT}/selection.json`;
  const inputBytes = await readDomainSourceFile(packageRoot, inputPath);
  let json: unknown;
  try {
    json = JSON.parse(inputBytes.toString("utf8"));
  } catch {
    requireDomainSource(false, "selection.json is not JSON");
  }
  const parsed = domainSelectionSchema.safeParse(json);
  requireDomainSource(
    parsed.success,
    "selection record violates fixed contract",
  );
  const record = parsed.data;
  const capsuleNames = (await readdir(join(packageRoot, DOMAIN_SOURCE_ROOT)))
    .sort()
    .join("\0");
  requireDomainSource(
    capsuleNames ===
      ["GLOSSARY-FORMAT.md", "SKILL.md", "selection.json"].join("\0"),
    "unexpected or missing capsule member",
  );
  const oldSkill = skills["domain-modeling"];
  const oldRepository = repositories[record.base.repositoryKey];
  requireDomainSource(
    oldSkill !== undefined &&
      oldSkill.repository === record.base.repositoryKey &&
      oldSkill.sourceSubpath === record.origin.sourceSubpath &&
      oldSkill.stablePath === "skills/domain-modeling" &&
      oldSkill.treeSha256 === record.base.treeSha256 &&
      oldRepository !== undefined &&
      oldRepository.url === record.origin.repository &&
      oldRepository.revision === record.base.repositoryRevision &&
      oldRepository.license === "MIT" &&
      repositories[record.target.repositoryKey] === undefined,
    "stale or conflicting base source identity",
  );
  requireDomainSource(
    oldRepository.licenseFiles.length === 1 &&
      oldRepository.licenseFiles[0]?.source === "LICENSE" &&
      oldRepository.licenseFiles[0]?.stablePath === record.license.path,
    "MIT license declaration differs",
  );
  const licensePath = `${STABLE_LICENSES_PREFIX}mattpocock-skills-LICENSE`;
  const licenseBytes = assets.get(licensePath);
  requireDomainSource(licenseBytes !== undefined, "MIT notice is not retained");
  verifyDomainIdentity(licenseBytes, record.license, licensePath);
  const expectedOperations = {
    "ADR-FORMAT.md": "keep",
    "CONTEXT-FORMAT.md": "delete",
    "GLOSSARY-FORMAT.md": "add",
    "SKILL.md": "replace",
    "agents/openai.yaml": "keep",
  } as const;
  const seen = new Set<string>();
  const before = new Map<string, Buffer>();
  const target = new Map<string, Buffer>();
  for (const file of record.files) {
    requireDomainSource(
      !seen.has(file.path) && file.operation === expectedOperations[file.path],
      "duplicate or unexpected selection operation",
    );
    seen.add(file.path);
    const old = assets.get(`${DOMAIN_SKILL_PREFIX}${file.path}`);
    if (file.operation === "add") {
      requireDomainSource(
        file.before === null && old === undefined,
        "add preimage exists",
      );
    } else {
      requireDomainSource(
        file.before !== null && old !== undefined,
        "missing preimage",
      );
      verifyDomainIdentity(old, file.before, file.path);
      const info = await lstat(
        join(canonicalRoot, DOMAIN_SKILL_PREFIX, file.path),
      );
      requireDomainSource(
        info.isFile() && (info.mode & 0o7777) === 0o644,
        "base file mode differs",
      );
      before.set(file.path, old);
    }
    if (file.operation === "delete") {
      requireDomainSource(file.target === null, "deleted path still in target");
    } else {
      requireDomainSource(file.target !== null, "target identity missing");
      const bytes =
        file.operation === "keep"
          ? old
          : await readDomainSourceFile(
              packageRoot,
              `${DOMAIN_SOURCE_ROOT}/${file.path}`,
            );
      requireDomainSource(bytes !== undefined, "kept source missing");
      verifyDomainIdentity(bytes, file.target, file.path);
      target.set(file.path, bytes);
    }
  }
  const retainedDomainPaths = [...assets.keys()].filter((path) =>
    path.startsWith(DOMAIN_SKILL_PREFIX),
  );
  requireDomainSource(
    retainedDomainPaths.length === before.size &&
      before.size === 4 &&
      target.size === 4 &&
      !before.has(record.base.absent[0]) &&
      !target.has(record.target.absent[0]) &&
      domainTreeDigest(before) === record.base.treeSha256 &&
      domainTreeDigest(target) === record.target.treeSha256,
    "selected whole tree or absence proof differs",
  );
  const nextSkills: Record<string, CanonicalStableSkill> = {
    ...skills,
    "domain-modeling": {
      ...oldSkill,
      repository: record.target.repositoryKey,
      treeSha256: record.target.treeSha256,
    },
  };
  const nextRepositories: Record<string, CanonicalStableRepository> = {
    ...repositories,
    [record.target.repositoryKey]: {
      ...oldRepository,
      revision: record.target.repositoryRevision,
    },
  };
  if (
    !Object.values(nextSkills).some(
      (skill) => skill.repository === record.base.repositoryKey,
    )
  ) {
    delete nextRepositories[record.base.repositoryKey];
  }
  // All source/whole-tree checks precede mutation; no generated files exist yet.
  for (const path of retainedDomainPaths) assets.delete(path);
  for (const [path, bytes] of target)
    assets.set(`${DOMAIN_SKILL_PREFIX}${path}`, bytes);
  return {
    repositories: nextRepositories,
    skills: nextSkills,
    receipt: {
      kind: "mixed-source",
      scope: "domain-modeling-only",
      base: {
        canonicalRevision: record.base.canonicalRevision,
        canonicalManifestSha256: DOMAIN_BASE_MANIFEST_SHA256,
        policySha256: DOMAIN_BASE_POLICY_SHA256,
        stableSet: stable.stableSet,
        promotedAt: stable.promotedAt,
      },
      inputPath,
      inputSha256: sha256(inputBytes),
      record,
    },
  };
}

async function selectR1ManualsSource(
  packageRoot: string,
  canonicalRoot: string,
  assets: Map<string, Buffer>,
  repositories: Readonly<Record<string, CanonicalStableRepository>>,
  skills: Readonly<Record<string, CanonicalStableSkill>>,
  domain: DomainSelectionReceipt,
): Promise<{
  repositories: Readonly<Record<string, CanonicalStableRepository>>;
  skills: Readonly<Record<string, CanonicalStableSkill>>;
  receipt: R1ManualsReceipt;
}> {
  const requireR1 = (condition: unknown, reason: string) =>
    requireDomainSource(condition, reason, "r1-manuals");
  const inputPath = `${R1_SOURCE_ROOT}/selection.json`;
  const inputBytes = await readDomainSourceFile(
    packageRoot,
    inputPath,
    "r1-manuals",
  );
  let json: unknown;
  try {
    json = JSON.parse(inputBytes.toString("utf8"));
  } catch {
    requireR1(false, "selection.json is not JSON");
  }
  const parsed = r1ManualsSelectionSchema.safeParse(json);
  requireDomainSource(
    parsed.success,
    "selection record violates fixed contract",
    "r1-manuals",
  );
  const record = parsed.data;
  requireR1(
    (await readdir(join(packageRoot, R1_SOURCE_ROOT))).sort().join("\0") ===
      ["grilling", "selection.json", "to-tickets"].join("\0"),
    "unexpected or missing capsule member",
  );
  requireR1(
    domain.inputPath === record.domainSelection.inputPath &&
      domain.inputSha256 === record.domainSelection.inputSha256,
    "domain selection dependency differs",
  );
  const oldRepository = repositories[record.base.repositoryKey];
  const domainSkill = skills["domain-modeling"];
  requireDomainSource(
    oldRepository !== undefined &&
      oldRepository.url === record.origin.repository &&
      oldRepository.revision === record.base.repositoryRevision &&
      oldRepository.license === record.origin.license &&
      oldRepository.licenseFiles.length === 1 &&
      oldRepository.licenseFiles[0]?.source === "LICENSE" &&
      oldRepository.licenseFiles[0]?.stablePath === record.license.path &&
      repositories[record.target.repositoryKey] === undefined &&
      domainSkill !== undefined &&
      domainSkill.repository === domain.record.target.repositoryKey &&
      domainSkill.treeSha256 === domain.record.target.treeSha256 &&
      Object.values(skills).filter(
        (skill) => skill.repository === domain.record.target.repositoryKey,
      ).length === 1,
    "stale or conflicting source or MIT identity",
    "r1-manuals",
  );
  const licensePath = `${STABLE_LICENSES_PREFIX}mattpocock-skills-LICENSE`;
  verifyDomainIdentity(
    await readDomainSourceFile(canonicalRoot, licensePath, "r1-manuals"),
    record.license,
    licensePath,
    "r1-manuals",
  );
  const presentation = await readDomainSourceFile(
    packageRoot,
    `${OMP_OVERLAY_ROOT}/${R1_PRESENTATION_PATH}`,
    "r1-manuals",
  );
  verifyDomainIdentity(
    presentation,
    record.presentation.target,
    R1_PRESENTATION_PATH,
    "r1-manuals",
  );
  requireR1(
    assets.get(R1_PRESENTATION_PATH)?.equals(presentation),
    "presentation is not the fixed existing overlay",
  );
  const replacements = new Map<string, Buffer>();
  const nextSkills: Record<string, CanonicalStableSkill> = {
    ...skills,
    "domain-modeling": {
      ...domainSkill,
      repository: record.target.repositoryKey,
    },
  };
  const seen = new Set<string>();
  for (const skill of record.skills) {
    const pinned = R1_MANUAL_TREES[skill.name];
    const oldSkill = skills[skill.name];
    const prefix = `${STABLE_SKILLS_PREFIX}${skill.name}/`;
    requireDomainSource(
      !seen.has(skill.name) &&
        skill.sourceSubpath === pinned.sourceSubpath &&
        skill.beforeTreeSha256 === pinned.before &&
        skill.targetTreeSha256 === pinned.target &&
        oldSkill !== undefined &&
        oldSkill.repository === record.base.repositoryKey &&
        oldSkill.sourceSubpath === pinned.sourceSubpath &&
        oldSkill.stablePath === `skills/${skill.name}` &&
        oldSkill.treeSha256 === pinned.before &&
        [...assets.keys()].filter((path) => path.startsWith(prefix)).length ===
          2,
      "stale, duplicate or partial manual tree",
      "r1-manuals",
    );
    seen.add(skill.name);
    requireR1(
      (await readdir(join(packageRoot, R1_SOURCE_ROOT, skill.name))).join(
        "\0",
      ) === "SKILL.md",
      "unexpected or missing manual capsule member",
    );
    const before = new Map<string, Buffer>();
    const target = new Map<string, Buffer>();
    for (const file of skill.files) {
      const path = `${prefix}${file.path}`;
      const old = await readDomainSourceFile(canonicalRoot, path, "r1-manuals");
      requireR1(
        assets.get(path)?.equals(old),
        "manual preimage is not retained",
      );
      verifyDomainIdentity(old, file.before, path, "r1-manuals");
      before.set(file.path, old);
      const bytes =
        file.operation === "keep"
          ? old
          : await readDomainSourceFile(
              packageRoot,
              `${R1_SOURCE_ROOT}/${skill.name}/${file.path}`,
              "r1-manuals",
            );
      verifyDomainIdentity(bytes, file.target, path, "r1-manuals");
      target.set(file.path, bytes);
      if (file.operation === "replace") replacements.set(path, bytes);
    }
    requireR1(
      domainTreeDigest(before) === pinned.before &&
        domainTreeDigest(target) === pinned.target,
      "selected whole manual tree differs from fixed source",
    );
    nextSkills[skill.name] = {
      ...oldSkill,
      repository: record.target.repositoryKey,
      treeSha256: pinned.target,
    };
  }
  const nextRepositories: Record<string, CanonicalStableRepository> = {
    ...repositories,
    [record.target.repositoryKey]: {
      ...oldRepository,
      revision: record.target.repositoryRevision,
    },
  };
  delete nextRepositories[domain.record.target.repositoryKey];
  const finalOwnership: R1FinalOwnership = {};
  for (const [name, skill] of Object.entries(nextSkills)) {
    if (
      skill.repository === record.target.repositoryKey ||
      skill.repository === record.base.repositoryKey
    ) {
      finalOwnership[name] = skill.repository;
    }
  }
  // The domain selection and both complete manual trees are verified before writes.
  for (const [path, bytes] of replacements) assets.set(path, bytes);
  const sourceOperations: R1SourceOperation[] = [
    ...domain.record.files.flatMap((file) =>
      file.operation === "keep"
        ? []
        : [
            {
              path: `${DOMAIN_SKILL_PREFIX}${file.path}`,
              operation: file.operation,
              source: "domain-modeling" as const,
              targetSha256: file.target?.sha256 ?? null,
            },
          ],
    ),
    ...record.skills.map((skill) => ({
      path: `${STABLE_SKILLS_PREFIX}${skill.name}/SKILL.md`,
      operation: "replace" as const,
      source: "r1-manuals" as const,
      targetSha256: skill.files[0].target.sha256,
    })),
    {
      path: R1_PRESENTATION_PATH,
      operation: "replace",
      source: "omp-overlay",
      targetSha256: record.presentation.target.sha256,
    },
  ];
  return {
    repositories: nextRepositories,
    skills: nextSkills,
    receipt: {
      kind: "mixed-source",
      scope: "r1-manuals",
      base: domain.base,
      inputPath,
      inputSha256: sha256(inputBytes),
      domain: { role: "validated-component-input", receipt: domain },
      record,
      sourceOperations,
      finalOwnership,
    },
  };
}

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

// p0-v4 (PRD D14): the zero-leakage exemption covers the canonical onboard
// runtime package path set — `onboard/runtime/scripts/*.py`,
// `onboard/runtime/assets/*`, and the two schema JSON files shipping with
// that runtime. The set must not grow beyond D14. Membership follows glob
// semantics: a single path segment below the listed prefix.
const canonicalOnboardRuntimeScriptsPrefix = "onboard/runtime/scripts/";
const canonicalOnboardRuntimeAssetsPrefix = "onboard/runtime/assets/";
const canonicalOnboardRuntimeSchemaPaths: Readonly<Record<string, true>> = {
  "onboard/runtime/onboard-contracts.schema.json": true,
  "onboard/runtime/upgrade.schema.json": true,
};

function isCanonicalOnboardRuntimePackagePath(path: string): boolean {
  if (canonicalOnboardRuntimeSchemaPaths[path] === true) return true;
  if (path.startsWith(canonicalOnboardRuntimeScriptsPrefix)) {
    const rest = path.slice(canonicalOnboardRuntimeScriptsPrefix.length);
    return rest.endsWith(".py") && !rest.includes("/");
  }
  if (path.startsWith(canonicalOnboardRuntimeAssetsPrefix)) {
    const rest = path.slice(canonicalOnboardRuntimeAssetsPrefix.length);
    return rest.length > 0 && !rest.includes("/");
  }
  return false;
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
  let { repositories: retainedRepositories, skills: retainedSkills } =
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

  let sourceSelection: DomainSelectionReceipt | R1ManualsReceipt | undefined;
  if (options.sourceSelection !== undefined) {
    requireDomainSource(
      canonicalManifestSha256 === DOMAIN_BASE_MANIFEST_SHA256 &&
        policySha256 === DOMAIN_BASE_POLICY_SHA256 &&
        sha256(canonicalStableBytes) ===
          canonicalManifest.assets[EMBEDDED_STABLE_MANIFEST_PATH],
      "canonical base or policy differs from the pinned preimage",
    );
    const selected = await selectDomainModelingSource(
      packageRoot,
      canonicalRoot,
      canonicalStable,
      retainedAssets,
      retainedRepositories,
      retainedSkills,
    );
    retainedRepositories = selected.repositories;
    retainedSkills = selected.skills;
    sourceSelection = selected.receipt;
    if (options.sourceSelection === "r1-manuals") {
      const manuals = await selectR1ManualsSource(
        packageRoot,
        canonicalRoot,
        retainedAssets,
        retainedRepositories,
        retainedSkills,
        selected.receipt,
      );
      retainedRepositories = manuals.repositories;
      retainedSkills = manuals.skills;
      sourceSelection = manuals.receipt;
    }
  }
  // Derived KPi-owned outputs bind the retained decision set.
  const retainedStableManifest: CanonicalStableManifest & {
    sourceSelection?: DomainSelectionReceipt | R1ManualsReceipt;
  } = {
    schemaVersion: 1,
    stableSet: canonicalStable.stableSet,
    promotedAt: canonicalStable.promotedAt,
    ...(sourceSelection === undefined ? {} : { sourceSelection }),
    repositories: retainedRepositories,
    skills: retainedSkills,
  };
  const retainedStableManifestBytes = Buffer.from(
    `${JSON.stringify(retainedStableManifest, null, 2)}\n`,
    "utf8",
  );
  let retainedStableNotices = renderRetainedStableNotices(retainedRepositories);
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
  let topLevelNotices = [
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
  const phosphorMetadata = retainedAssets.get(PHOSPHOR_METADATA_PATH);
  if (phosphorMetadata !== undefined) {
    const actualSha256 = sha256(phosphorMetadata);
    if (actualSha256 !== PHOSPHOR_METADATA_SHA256) {
      throw projectionError(
        "PROJECTION_LEGAL_INVENTORY",
        "retained Phosphor metadata differs from the reviewed attribution source",
        {
          path: PHOSPHOR_METADATA_PATH,
          expectedSha256: PHOSPHOR_METADATA_SHA256,
          actualSha256,
        },
      );
    }
    const phosphorAttribution = [
      "",
      "## Retained metadata attribution",
      "",
      "### @phosphor-icons/core@2.1.1",
      "",
      `- Applies to npm package member (relative to package root): kit/${PHOSPHOR_METADATA_PATH}`,
      "- Scope: 1512 metadata records; no SVG assets.",
      "- Source archive: https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz",
      "- Source archive SHA256: 313332be6190b724da24107addd781799b48bf76b13963f24501112ffe1baadd",
      "",
      PHOSPHOR_CORE_LICENSE,
    ].join("\n");
    topLevelNotices += phosphorAttribution;
    retainedStableNotices += phosphorAttribution;
  }
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
  const canonicalRuntimeMatches = [...retainedAssets.entries()]
    .filter(([path]) => isCanonicalOnboardRuntimePackagePath(path))
    .reduce(
      (total, [, content]) => total + countForbiddenTokenOccurrences(content),
      0,
    );
  let sourceSummary: DomainSelectionSummary | R1ManualsSummary | undefined;
  if (sourceSelection !== undefined) {
    sourceSummary = {
      scope: "domain-modeling-only",
      countsAndDecisions: "base-canonical-policy",
      ledgerAssetPath: EMBEDDED_STABLE_MANIFEST_PATH,
      inputSha256: sourceSelection.inputSha256,
      added: [`${DOMAIN_SKILL_PREFIX}GLOSSARY-FORMAT.md`],
      removed: [`${DOMAIN_SKILL_PREFIX}CONTEXT-FORMAT.md`],
      replaced: [`${DOMAIN_SKILL_PREFIX}SKILL.md`],
    };
    if (sourceSelection.scope === "r1-manuals") {
      sourceSummary = {
        ...sourceSummary,
        scope: "r1-manuals",
        replaced: [
          ...sourceSummary.replaced,
          `${STABLE_SKILLS_PREFIX}grilling/SKILL.md`,
          `${STABLE_SKILLS_PREFIX}to-tickets/SKILL.md`,
        ],
        sourceOperations: sourceSelection.sourceOperations,
        finalOwnership: sourceSelection.finalOwnership,
      };
    }
  }
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
    ...(sourceSummary === undefined ? {} : { sourceSelection: sourceSummary }),
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
  // canonical onboard runtime package path set (p0-v4, PRD D14) whose counted
  // legacy identifiers are required for its constrained OMP adapter contract.
  // The exemption is content-bound: it applies only when the retained bytes
  // exactly match the digest the canonical manifest declares for that path,
  // so an overlay or drifted payload cannot smuggle additional forbidden
  // content under it. Diagnostics expose only relative paths and counts,
  // never payload content.
  const outputFiles: readonly (readonly [string, Buffer])[] = [
    ...[...retainedAssets.entries()].map(
      ([path, content]) => [path, content] as const,
    ),
    ["manifest.json", manifestBytes] as const,
    [OMP_PROJECTION_REPORT_PATH, reportBytes] as const,
  ];
  const isApprovedCanonicalRuntime = (path: string, content: Buffer) => {
    if (!isCanonicalOnboardRuntimePackagePath(path)) return false;
    const approvedDigest = canonicalManifest.assets[path];
    return approvedDigest !== undefined && sha256(content) === approvedDigest;
  };
  // The generated metadata files embed exempt-set path strings as JSON
  // keys/values (asset digests, decisions, overlay digests). Those
  // occurrences are gated by the path scan above and by the content-bound
  // exemption, so the payload scan masks exactly the exempt, token-bearing
  // path strings and scans the remainder — any other occurrence (for example
  // a token smuggled through a map-authored reason string) is still caught.
  const exemptTokenPaths = [...retainedAssets.keys()].filter(
    (path) =>
      isCanonicalOnboardRuntimePackagePath(path) &&
      containsForbiddenToken(Buffer.from(path, "utf8")),
  );
  const maskExemptPathStrings = (content: Buffer): Buffer => {
    let text = content.toString("utf8");
    for (const path of exemptTokenPaths) text = text.split(path).join("");
    return Buffer.from(text, "utf8");
  };
  const pathViolations = outputFiles
    .filter(
      ([path, content]) =>
        containsForbiddenToken(Buffer.from(path, "utf8")) &&
        !isApprovedCanonicalRuntime(path, content),
    )
    .map(([path]) => path)
    .sort();
  const payloadViolations = outputFiles
    .filter(([path, content]) => {
      const scanned =
        path === "manifest.json" || path === OMP_PROJECTION_REPORT_PATH
          ? maskExemptPathStrings(content)
          : content;
      return (
        containsForbiddenToken(scanned) &&
        !isApprovedCanonicalRuntime(path, content)
      );
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
  requireDomainSource(
    options.sourceSelection === undefined ||
      options.sourceSelection === "domain-modeling" ||
      options.sourceSelection === "r1-manuals",
    "unsupported source selection",
  );
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
