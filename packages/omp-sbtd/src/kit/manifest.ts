import { createHash } from "node:crypto";
import { z } from "zod";

export const EMBEDDED_STABLE_MANIFEST_PATH =
  "onboard/runtime/assets/external-skills/stable/MANIFEST.json";

const sha256 = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

const stableProvenanceRepositorySchema = z
  .object({
    url: z.url(),
    revision: z.string().regex(/^[0-9a-f]{40}$/),
    license: z.string().min(1),
  })
  .strict();

const stableManifestRepositorySchema =
  stableProvenanceRepositorySchema.passthrough();

const stableProvenanceSkillSchema = z
  .object({
    repository: z.string().min(1),
    sourceSubpath: z.string().min(1),
    stablePath: z.string().min(1),
    treeSha256: sha256Schema,
  })
  .strict();

const stableManifestSkillSchema = stableProvenanceSkillSchema.passthrough();

export const embeddedStableProvenanceSchema = z
  .object({
    stableSet: z.string().min(1),
    manifestSha256: sha256Schema,
    repositories: z.record(z.string(), stableProvenanceRepositorySchema),
    skills: z.record(z.string(), stableProvenanceSkillSchema),
  })
  .strict();

const embeddedStableManifestSchema = z
  .object({
    stableSet: z.string().min(1),
    repositories: z.record(z.string(), stableManifestRepositorySchema),
    skills: z.record(z.string(), stableManifestSkillSchema),
  })
  .passthrough();

const embeddedCanonicalSchema = z
  .object({
    sourceId: z.literal("sbtd-workflow-kit-upstream"),
    canonicalSourceUri: z.url(),
    resolvedRevision: z.string().regex(/^[0-9a-f]{40}$/),
    sourceTreeSha256: sha256Schema,
    transformVersion: z.string().min(1),
    manifestSha256: sha256Schema,
    generatedSha256: sha256Schema,
  })
  .strict();

const embeddedProjectionSchema = z
  .object({
    policyVersion: z.literal(1),
    policySha256: sha256Schema,
    decisionsSha256: sha256Schema,
    generatedSha256: sha256Schema,
    counts: z
      .object({
        included: z.number().int().nonnegative(),
        omitted: z.number().int().nonnegative(),
        replaced: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .strict();

export const embeddedKitManifestSchema = z
  .object({
    schemaVersion: z.literal(2),
    runtime: z.literal("omp"),
    canonical: embeddedCanonicalSchema,
    projection: embeddedProjectionSchema,
    overlayDigests: z.record(z.string(), sha256Schema),
    targets: z.record(z.string(), sha256Schema),
    profileCatalogSha256: sha256Schema,
    assets: z.record(z.string(), sha256Schema),
    retainedProvenance: embeddedStableProvenanceSchema,
  })
  .strict();

export type EmbeddedKitManifestV2 = z.infer<typeof embeddedKitManifestSchema>;

export interface VerifiedEmbeddedKitManifest {
  readonly manifest: EmbeddedKitManifestV2;
  readonly assets: ReadonlyMap<string, Uint8Array>;
}

export function isStrictPosixRelativePath(path: string): boolean {
  return (
    path.length > 0 &&
    !path.startsWith("/") &&
    !path.includes("\\") &&
    !path.includes("\0") &&
    path
      .split("/")
      .every((segment) => segment !== "" && segment !== "." && segment !== "..")
  );
}

function assertStrictPosixRelativePath(path: string): void {
  if (!isStrictPosixRelativePath(path))
    throw new Error(`unsafe embedded Kit asset path: ${path}`);
}

function generatedProjectionDigest(manifest: EmbeddedKitManifestV2): string {
  return sha256(
    [
      ...Object.entries(manifest.assets)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([path, digest]) => `${path}\0${digest}`),
      ...Object.entries(manifest.overlayDigests)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([path, digest]) => `overlay:${path}\0${digest}`),
    ].join("\n"),
  );
}

function assertStableProvenance(
  manifest: EmbeddedKitManifestV2,
  stableManifestBytes: Uint8Array,
): void {
  if (
    sha256(stableManifestBytes) !== manifest.retainedProvenance.manifestSha256
  )
    throw new Error(
      "embedded Kit stable manifest digest does not match derived provenance",
    );

  let stableManifest: z.infer<typeof embeddedStableManifestSchema>;
  try {
    stableManifest = embeddedStableManifestSchema.parse(
      JSON.parse(Buffer.from(stableManifestBytes).toString("utf8")),
    );
  } catch {
    throw new Error("embedded Kit stable manifest is invalid");
  }

  const provenanceRepositories = Object.entries(
    manifest.retainedProvenance.repositories,
  );
  const embeddedRepositories = Object.entries(stableManifest.repositories);
  const provenanceSkills = Object.entries(manifest.retainedProvenance.skills);
  const embeddedSkills = Object.entries(stableManifest.skills);
  if (
    stableManifest.stableSet !== manifest.retainedProvenance.stableSet ||
    provenanceRepositories.length !== embeddedRepositories.length ||
    provenanceRepositories.some(([name, repository]) => {
      const embedded = stableManifest.repositories[name];
      return (
        embedded?.url !== repository.url ||
        embedded?.revision !== repository.revision ||
        embedded?.license !== repository.license
      );
    }) ||
    provenanceSkills.length !== embeddedSkills.length ||
    provenanceSkills.some(([name, skill]) => {
      const embedded = stableManifest.skills[name];
      return (
        embedded?.repository !== skill.repository ||
        embedded?.sourceSubpath !== skill.sourceSubpath ||
        embedded?.stablePath !== skill.stablePath ||
        embedded?.treeSha256 !== skill.treeSha256
      );
    })
  )
    throw new Error(
      "embedded Kit stable provenance drifted from the embedded stable manifest",
    );
}

/**
 * Validates schema-v2 projection bindings using caller-controlled asset reads.
 * The primitive performs no filesystem I/O; every consumer retains ownership of
 * its root-containment and regular-file checks.
 */
export async function verifyEmbeddedKitManifest(
  input: unknown,
  readAsset: (path: string) => Promise<Uint8Array>,
): Promise<VerifiedEmbeddedKitManifest> {
  const manifest = embeddedKitManifestSchema.parse(input);
  const assets = new Map<string, Uint8Array>();
  for (const [path, expectedDigest] of Object.entries(manifest.assets)) {
    assertStrictPosixRelativePath(path);
    const content = await readAsset(path);
    if (sha256(content) !== expectedDigest)
      throw new Error(`embedded Kit asset digest mismatch: ${path}`);
    assets.set(path, content);
  }

  if (
    generatedProjectionDigest(manifest) !==
      manifest.projection.generatedSha256 ||
    manifest.targets["AGENTS.global.md"] !==
      manifest.assets["AGENTS.global.md"] ||
    manifest.targets["AGENTS.project-root.md"] !==
      manifest.assets["AGENTS.project-root.md"] ||
    manifest.targets["AGENTS.project-omp.md"] !==
      manifest.assets["AGENTS.project-omp.md"] ||
    manifest.profileCatalogSha256 !== manifest.assets["catalog.json"]
  )
    throw new Error("embedded Kit manifest is internally inconsistent");

  const stableManifest = assets.get(EMBEDDED_STABLE_MANIFEST_PATH);
  if (stableManifest === undefined)
    throw new Error("embedded Kit stable manifest is missing");
  assertStableProvenance(manifest, stableManifest);

  return { manifest, assets };
}
