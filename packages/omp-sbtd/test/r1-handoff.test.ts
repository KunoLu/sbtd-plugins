import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { parse } from "yaml";
import { inspectManagedBlock, sha256 } from "../src/agents/index.js";
import { loadEmbeddedKitFromDirectory } from "../src/kit/index.js";
import {
  createNodeFileAdapter,
  createOnboardService,
} from "../src/onboard/index.js";
import {
  inventoryPackagedSkills,
  readCertifiedOrGlobalSkill,
} from "../src/skills/index.js";
import { generateOmpProjection } from "../upstream/src/omp-projection.js";

const upstreamRoot = fileURLToPath(new URL("../upstream/", import.meta.url));
const stableRoot = "onboard/runtime/assets/external-skills/stable";
const temporaryRoots: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { recursive: true, force: true })),
  );
});

// These are delivery-input checks, not a simulated Agent dialogue or tracker run.
describe("Feature: R1 技能交接输入经既有 Kit / Onboard 消费接口交付", () => {
  it.each([
    {
      profile: "legacy",
      sourceSelection: undefined,
      vocabularyReference: "CONTEXT-FORMAT.md",
      absentReference: "GLOSSARY-FORMAT.md",
      grillingSha256:
        "10ff989e7498b23b5acb49d5048f11dcd906757d2f79c5cdf8a00001381296f2",
      ticketsSha256:
        "5c9fba69845c2519b9b35b9af42ae5142c21f8ca15ac2123dc2722002c8058ae",
    },
    {
      profile: "R1",
      sourceSelection: "r1-manuals" as const,
      vocabularyReference: "GLOSSARY-FORMAT.md",
      absentReference: "CONTEXT-FORMAT.md",
      grillingSha256:
        "a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2",
      ticketsSha256:
        "56ec23c5b2782785d4e65bff9e315b6d3aeb4ef977c174a219e99489fada1995",
    },
  ])("Scenario: $profile 的来源、reference 和目标 role 保持一致", async (profile) => {
    const root = await mkdtemp(join(tmpdir(), "kpi-r1-handoff-"));
    temporaryRoots.push(root);
    const outputDirectory = join(root, "kit");
    const generated = await generateOmpProjection({
      packageRoot: upstreamRoot,
      canonicalDirectory: join(upstreamRoot, "generated"),
      outputDirectory,
      ...(profile.sourceSelection === undefined
        ? {}
        : { sourceSelection: profile.sourceSelection }),
    });
    const loaded = await loadEmbeddedKitFromDirectory(outputDirectory);
    const files = createNodeFileAdapter();
    expect(loaded.provenance.projectionSha256).toBe(
      generated.manifest.projection.generatedSha256,
    );
    expect(loaded.provenance.resolvedRevision).toBe(
      "1d82494d74f6df9bca7dccef2da409f87091883e",
    );
    expect(loaded.kit.templates.global).toBe(
      await readFile(
        join(upstreamRoot, "omp-overlays/AGENTS.global.md"),
        "utf8",
      ),
    );

    const skillsRoot = join(outputDirectory, stableRoot, "skills");
    const inventory = await inventoryPackagedSkills(skillsRoot);
    expect(inventory.invalidSkills).toEqual([]);
    const skills = new Map<string, string>();
    for (const name of [
      "grill-with-docs",
      "grilling",
      "domain-modeling",
      "to-spec",
      "to-tickets",
      "handoff",
    ]) {
      expect(inventory.names).toContain(name);
      const content = await readCertifiedOrGlobalSkill(
        files,
        name,
        inventory.names,
        join(root, "unconfigured-global-skills"),
        { packagedRoot: skillsRoot, invalidSkills: inventory.invalidSkills },
      );
      if (content === undefined)
        throw new Error(`Skill not delivered: ${name}`);
      const frontmatter = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
      if (frontmatter?.[1] === undefined)
        throw new Error(`Skill frontmatter missing: ${name}`);
      expect(parse(frontmatter[1])).toMatchObject({
        name,
        ...(["grill-with-docs", "to-spec", "to-tickets", "handoff"].includes(
          name,
        )
          ? { "disable-model-invocation": true }
          : {}),
      });
      skills.set(name, content);
    }
    expect(sha256(skills.get("grilling") as string)).toBe(
      profile.grillingSha256,
    );
    expect(sha256(skills.get("to-tickets") as string)).toBe(
      profile.ticketsSha256,
    );

    const domain =
      loaded.provenance.retainedProvenance.skills["domain-modeling"];
    if (domain === undefined) throw new Error("Domain provenance missing");
    const domainRoot = posix.join(stableRoot, domain.stablePath);
    const references = [
      ...(skills.get("domain-modeling") as string).matchAll(
        /\[[^\]]+\]\((\.\/[^)]+\.md)\)/g,
      ),
    ].map((match) => match[1] as string);
    expect(references.sort()).toEqual([
      "./ADR-FORMAT.md",
      `./${profile.vocabularyReference}`,
    ]);
    for (const reference of references) {
      const path = posix.join(domainRoot, reference);
      const content = await files.readText(join(outputDirectory, path));
      if (content === undefined)
        throw new Error(`Reference not delivered: ${path}`);
      expect(sha256(content)).toBe(generated.manifest.assets[path]);
    }
    const absentPath = posix.join(domainRoot, profile.absentReference);
    expect(generated.manifest.assets[absentPath]).toBeUndefined();
    expect(await files.exists(join(outputDirectory, absentPath))).toBe(false);

    const projectRoot = join(root, "project");
    const agentDirectory = join(root, "agent");
    const plan = await createOnboardService({
      projectRoot,
      agentDirectory,
      kit: loaded.kit,
      files,
      now: () => "2026-11-21T00:00:00.000Z",
    }).plan();
    const targets = [
      {
        role: "global",
        path: join(agentDirectory, "AGENTS.md"),
        asset: "AGENTS.global.md",
      },
      {
        role: "project-root",
        path: join(projectRoot, "AGENTS.md"),
        asset: "AGENTS.project-root.md",
      },
      {
        role: "project-omp",
        path: join(projectRoot, ".omp/AGENTS.md"),
        asset: "AGENTS.project-omp.md",
      },
    ] as const;
    expect(plan.targets.map(({ target }) => target)).toEqual(
      targets.map(({ role, path }) => ({ role, path })),
    );
    for (const { role, path, asset } of targets) {
      const proposed = plan.proposedFiles[path];
      if (proposed === undefined)
        throw new Error(`Role not delivered: ${role}`);
      const inspected = inspectManagedBlock(proposed, role);
      expect(inspected.block).toMatchObject({
        role,
        sourceId: loaded.kit.sourceId,
        sourceRevision: loaded.kit.sourceRevision,
        content: loaded.kit.templates[role],
      });
      expect(inspected.digest).toBe(generated.manifest.targets[asset]);
      expect(await files.exists(path)).toBe(false);
    }
    expect(await files.exists(plan.inventoryPath)).toBe(false);
  });
});
