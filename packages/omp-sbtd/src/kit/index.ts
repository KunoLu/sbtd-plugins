import { createHash } from "node:crypto";
import type { Stats } from "node:fs";
import { lstat, readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { kitSnapshotSchema } from "../onboard/index.js";
import {
  type embeddedStableProvenanceSchema,
  isStrictPosixRelativePath,
  verifyEmbeddedKitManifest,
} from "./manifest.js";

const sha256 = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");

const embeddedKitRoot = fileURLToPath(new URL("../../kit/", import.meta.url));
const utf8Decoder = new TextDecoder();

export const profileSchema = z
  .object({
    id: z.string().min(1),
    required: z.array(z.string().min(1)).max(64),
    optional: z.array(z.string().min(1)).max(64),
  })
  .strict();

const profileCatalogSchema = z
  .object({
    schemaVersion: z.literal(1),
    kitRevision: z.string().regex(/^[0-9a-f]{40}$/),
    profiles: z.array(profileSchema).min(1).max(32),
  })
  .strict();
export const coreGateSkillNames = [
  "book-ddd-distilled-modeling",
  "book-ddia-data-design",
  "book-legacy-change-safety",
  "book-refactoring-pass",
  "book-release-readiness",
] as const;

export interface EmbeddedKitProvenance {
  readonly sourceId: "sbtd-workflow-kit-upstream";
  readonly canonicalSourceUri: string;
  readonly resolvedRevision: string;
  readonly sourceTreeSha256: string;
  readonly transformVersion: string;
  readonly manifestSha256: string;
  readonly canonicalManifestSha256: string;
  readonly generatedSha256: string;
  readonly projectionSha256: string;
  readonly profileCatalogSha256: string;
  readonly retainedProvenance: z.infer<typeof embeddedStableProvenanceSchema>;
}

export interface EmbeddedKitOnboardRuntime {
  readonly root: string;
  readonly scriptSha256: string;
}

export interface EmbeddedKitValidationEvidenceRuntime {
  /** Absolute path to the promoted validation evidence validator script. */
  readonly scriptPath: string;
  /** Manifest-pinned SHA-256 of the validator script bytes. */
  readonly scriptSha256: string;
}

export interface EmbeddedKit {
  readonly kit: z.infer<typeof kitSnapshotSchema>;
  readonly provenance: EmbeddedKitProvenance;
  readonly freshness: "current";
  readonly profiles: readonly z.infer<typeof profileSchema>[];
  readonly coreGateSkillTemplatesPresent: boolean;
  readonly optionalCapabilities: Readonly<Record<string, boolean>>;
  readonly onboardRuntime?: EmbeddedKitOnboardRuntime;
  readonly validationEvidenceRuntime?: EmbeddedKitValidationEvidenceRuntime;
}

async function readRegularEmbeddedKitFile(
  root: string,
  relativePath: string,
): Promise<Uint8Array> {
  if (!isStrictPosixRelativePath(relativePath))
    throw new Error(`unsafe embedded Kit asset path: ${relativePath}`);
  let rootStat: Stats;
  try {
    rootStat = await lstat(root);
  } catch {
    throw new Error("embedded Kit root is unavailable");
  }
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink())
    throw new Error("embedded Kit root is unavailable");

  const segments = relativePath.split("/");
  let target = root;
  for (const [index, segment] of segments.entries()) {
    target = join(target, segment);
    let entry: Stats;
    try {
      entry = await lstat(target);
    } catch {
      throw new Error(`embedded Kit asset is unavailable: ${relativePath}`);
    }
    if (entry.isSymbolicLink())
      throw new Error(
        `embedded Kit asset must not be a symbolic link: ${relativePath}`,
      );
    if (index === segments.length - 1) {
      if (!entry.isFile())
        throw new Error(
          `embedded Kit asset is not a regular file: ${relativePath}`,
        );
    } else if (!entry.isDirectory()) {
      throw new Error(
        `embedded Kit asset parent is not a directory: ${relativePath}`,
      );
    }
  }
  try {
    return await readFile(target);
  } catch {
    throw new Error(`embedded Kit asset is unreadable: ${relativePath}`);
  }
}

function assetText(
  assets: ReadonlyMap<string, Uint8Array>,
  path: string,
): string | undefined {
  const content = assets.get(path);
  return content === undefined ? undefined : utf8Decoder.decode(content);
}

export async function loadEmbeddedKitFromDirectory(
  root: string,
): Promise<EmbeddedKit> {
  const manifestContent = await readRegularEmbeddedKitFile(
    root,
    "manifest.json",
  );
  let manifestInput: unknown;
  try {
    manifestInput = JSON.parse(utf8Decoder.decode(manifestContent));
  } catch {
    throw new Error("embedded Kit manifest is invalid JSON");
  }
  const { manifest, assets } = await verifyEmbeddedKitManifest(
    manifestInput,
    (path) => readRegularEmbeddedKitFile(root, path),
  );
  const catalogContent = assetText(assets, "catalog.json");
  if (catalogContent === undefined)
    throw new Error("embedded Kit Profile Catalog is missing");
  const catalog = profileCatalogSchema.parse(JSON.parse(catalogContent));
  if (
    catalog.kitRevision !== manifest.canonical.resolvedRevision ||
    new Set(catalog.profiles.map((profile) => profile.id)).size !==
      catalog.profiles.length
  )
    throw new Error("embedded Kit Profile Catalog is internally inconsistent");

  const globalAgents = assetText(assets, "AGENTS.global.md");
  const optionalCapabilitySources: Record<string, boolean> = {
    trellis:
      assetText(
        assets,
        "onboard/runtime/templates/skills/trellis-workflow/SKILL.md",
      ) !== undefined,
    gitnexus: globalAgents?.includes("GitNexus") === true,
    "bdd-tdd":
      assetText(
        assets,
        "onboard/runtime/assets/external-skills/stable/skills/tdd/SKILL.md",
      ) !== undefined,
    ui:
      assetText(
        assets,
        "onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/SKILL.md",
      ) !== undefined,
    "web-mobile-e2e": globalAgents?.includes("Maestro") === true,
    release:
      assetText(
        assets,
        "onboard/runtime/templates/skills/book-release-readiness/SKILL.md",
      ) !== undefined,
  };
  return {
    provenance: {
      sourceId: manifest.canonical.sourceId,
      canonicalSourceUri: manifest.canonical.canonicalSourceUri,
      resolvedRevision: manifest.canonical.resolvedRevision,
      sourceTreeSha256: manifest.canonical.sourceTreeSha256,
      transformVersion: manifest.canonical.transformVersion,
      manifestSha256: sha256(manifestContent),
      canonicalManifestSha256: manifest.canonical.manifestSha256,
      generatedSha256: manifest.projection.generatedSha256,
      projectionSha256: manifest.projection.generatedSha256,
      profileCatalogSha256: manifest.profileCatalogSha256,
      retainedProvenance: manifest.retainedProvenance,
    },
    freshness: "current",
    kit: kitSnapshotSchema.parse({
      sourceId: manifest.canonical.sourceId,
      sourceRevision: manifest.canonical.resolvedRevision,
      transformVersion: manifest.canonical.transformVersion,
      kitRevision: manifest.projection.generatedSha256,
      templates: {
        global: assetText(assets, "AGENTS.global.md"),
        "project-root": assetText(assets, "AGENTS.project-root.md"),
        "project-omp": assetText(assets, "AGENTS.project-omp.md"),
      },
    }),
    profiles: catalog.profiles,
    coreGateSkillTemplatesPresent: coreGateSkillNames.every(
      (name) =>
        assetText(
          assets,
          `onboard/runtime/templates/skills/${name}/SKILL.md`,
        ) !== undefined,
    ),
    optionalCapabilities: Object.fromEntries(
      catalog.profiles.flatMap((profile) =>
        profile.optional.map((capability) => [
          capability,
          optionalCapabilitySources[capability] === true,
        ]),
      ),
    ),
    ...(manifest.assets["onboard/runtime/scripts/onboard.py"] !== undefined
      ? {
          onboardRuntime: {
            root: join(root, "onboard", "runtime"),
            scriptSha256: manifest.assets[
              "onboard/runtime/scripts/onboard.py"
            ] as string,
          },
        }
      : {}),
    ...(manifest.assets[
      "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py"
    ] !== undefined
      ? {
          validationEvidenceRuntime: {
            scriptPath: join(
              root,
              "onboard",
              "runtime",
              "templates",
              "skills",
              "project-validation",
              "scripts",
              "validate_validation_evidence.py",
            ),
            scriptSha256: manifest.assets[
              "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py"
            ] as string,
          },
        }
      : {}),
  };
}

async function readEmbeddedKit(): Promise<EmbeddedKit> {
  return loadEmbeddedKitFromDirectory(embeddedKitRoot);
}

const embeddedKitsByTurn = new Map<string, Promise<EmbeddedKit>>();

export function loadEmbeddedKit(turnCacheKey?: string): Promise<EmbeddedKit> {
  if (turnCacheKey === undefined) return readEmbeddedKit();
  const cached = embeddedKitsByTurn.get(turnCacheKey);
  if (cached !== undefined) return cached;
  const pending = readEmbeddedKit();
  embeddedKitsByTurn.set(turnCacheKey, pending);
  void pending.catch(() => {
    if (embeddedKitsByTurn.get(turnCacheKey) === pending)
      embeddedKitsByTurn.delete(turnCacheKey);
  });
  return pending;
}

export function releaseEmbeddedKit(turnCacheKey: string): void {
  embeddedKitsByTurn.delete(turnCacheKey);
}

export function resolveProfile(
  profiles: EmbeddedKit["profiles"],
  profileId: string,
): z.infer<typeof profileSchema> {
  const profile = profiles.find(({ id }) => id === profileId);
  if (!profile)
    throw new Error(
      `selected SBTD Onboard Profile is unavailable: ${profileId}`,
    );
  return profile;
}
