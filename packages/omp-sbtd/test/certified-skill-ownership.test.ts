import {
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { createNodeFileAdapter } from "../src/onboard/index.ts";
import {
  applyCertifiedLeftoverCleanup,
  assertRegistryMatchesRuntimeConstants,
  buildRuntimeSkillPolicyRegistry,
  classifyCertifiedLeftovers,
  inspectPluginManifest,
  inventoryPackagedSkills,
  readCertifiedOrGlobalSkill,
  renderAgentPluginDoctorBlock,
} from "../src/skills/index.ts";

const files = createNodeFileAdapter();

const writeTree = async (
  root: string,
  entries: Readonly<Record<string, string>>,
): Promise<void> => {
  for (const [relative, content] of Object.entries(entries)) {
    const path = join(root, relative);
    await mkdir(join(path, ".."), { recursive: true });
    await writeFile(path, content);
  }
};

describe("Feature: Certified Skill 所有权切交（M3）", () => {
  const roots: string[] = [];
  afterEach(async () => {
    await Promise.all(
      roots.splice(0).map((root) => rm(root, { recursive: true, force: true })),
    );
  });

  it("Scenario: OMP Onboard catalog 不再把 certified 名列为 bundled copy 来源", async () => {
    const catalog = JSON.parse(
      await readFile(
        new URL("../kit/onboard/runtime/catalog.json", import.meta.url),
        "utf8",
      ),
    ) as { entries: Array<{ id: string; kind: string }> };
    const bundled = catalog.entries
      .filter((entry) => entry.kind === "bundled-skill")
      .map((entry) => entry.id);
    const external = catalog.entries.filter(
      (entry) => entry.kind === "external-skill",
    );
    expect(bundled).toEqual([
      "skill:sbtd-workflow-onboard",
      "skill:trellis-workflow",
      "skill:trellis-channel",
    ]);
    expect(external).toHaveLength(12);
    expect(bundled.join("\n")).not.toContain("skill:project-validation");
    expect(bundled.join("\n")).not.toContain("skill:gherkin-bdd");
  });

  it("Scenario: digest 匹配的 certified 旧副本被备份后删除", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-cleanup-"));
    roots.push(root);
    const leftover = join(root, "skills", "gherkin-bdd");
    const source = join(root, "kit", "gherkin-bdd");
    await writeTree(leftover, { "SKILL.md": "same\n" });
    await writeTree(source, { "SKILL.md": "same\n" });
    const result = await applyCertifiedLeftoverCleanup({
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      backupRoot: join(root, "backup"),
      packagedNames: ["gherkin-bdd"],
      files,
    });
    expect(result.status).toBe("applied");
    expect(result.removed).toEqual(["gherkin-bdd"]);
    expect(await files.exists(leftover)).toBe(false);
    expect(
      await files.exists(join(root, "backup", "gherkin-bdd", "SKILL.md")),
    ).toBe(true);
  });

  it("Scenario: 同名但内容不匹配的目录必须保留并报冲突", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-conflict-"));
    roots.push(root);
    await writeTree(join(root, "skills", "gherkin-bdd"), {
      "SKILL.md": "user-edited\n",
    });
    await writeTree(join(root, "kit", "gherkin-bdd"), { "SKILL.md": "kit\n" });
    const classified = await classifyCertifiedLeftovers({
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      packagedNames: ["gherkin-bdd"],
      files,
    });
    expect(classified.eligible).toEqual([]);
    expect(classified.conflicts).toEqual([
      { name: "gherkin-bdd", reason: "digest-mismatch" },
    ]);
    expect(
      await files.exists(join(root, "skills", "gherkin-bdd", "SKILL.md")),
    ).toBe(true);
  });

  it("Scenario: 符号链接或非目录同名目标不得删除", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-symlink-"));
    roots.push(root);
    await mkdir(join(root, "skills"), { recursive: true });
    await writeTree(join(root, "kit", "gherkin-bdd"), { "SKILL.md": "kit\n" });
    await symlink(
      join(root, "kit", "gherkin-bdd"),
      join(root, "skills", "gherkin-bdd"),
    );
    const classified = await classifyCertifiedLeftovers({
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      packagedNames: ["gherkin-bdd"],
      files,
    });
    expect(classified.conflicts[0]?.reason).toBe("symlink");
    expect(await files.isSymlink(join(root, "skills", "gherkin-bdd"))).toBe(
      true,
    );
  });

  it("Scenario: 无 certified 旧副本时 cleanup 为零写", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-empty-"));
    roots.push(root);
    await mkdir(join(root, "skills"), { recursive: true });
    const result = await applyCertifiedLeftoverCleanup({
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      backupRoot: join(root, "backup"),
      packagedNames: ["gherkin-bdd"],
      files,
    });
    expect(result.status).toBe("not-required");
    expect(result.removed).toEqual([]);
    expect(await files.exists(join(root, "backup"))).toBe(false);
  });

  it("Scenario: Host 无法证明 resolved source 时 Doctor 报 source-unverified", async () => {
    const packaged = await inventoryPackagedSkills();
    const block = renderAgentPluginDoctorBlock({
      schema: "1.0.0",
      manifest: await inspectPluginManifest(files),
      packagedCount: packaged.packagedCount,
      packagedDigest: packaged.packagedDigest,
      discovered: "source-unverified",
      invalidSkills: packaged.invalidSkills,
      conflicts: [{ name: "gherkin-bdd", reason: "digest-mismatch" }],
      portableMcp: "absent",
      ompRuntimeExtension: "loaded",
    });
    expect(block).toContain("schema: 1.0.0");
    expect(block).toContain("manifest: valid");
    expect(block).toContain(`packaged: ${packaged.packagedCount}`);
    expect(block).toContain("discovered: source-unverified");
    expect(block).toContain("gherkin-bdd");
    expect(block).not.toContain("book-ddd-distilled-modeling");
    expect(packaged.packagedCount).toBe(12);
  });

  it("Scenario: cleanup 中途失败时回滚已移动的目录", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-rollback-"));
    roots.push(root);
    await writeTree(join(root, "skills", "gherkin-bdd"), {
      "SKILL.md": "same\n",
    });
    await writeTree(join(root, "skills", "project-validation"), {
      "SKILL.md": "same\n",
    });
    await writeTree(join(root, "kit", "gherkin-bdd"), { "SKILL.md": "same\n" });
    await writeTree(join(root, "kit", "project-validation"), {
      "SKILL.md": "same\n",
    });
    let moves = 0;
    const result = await applyCertifiedLeftoverCleanup({
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      backupRoot: join(root, "backup"),
      packagedNames: ["gherkin-bdd", "project-validation"],
      files,
      renameEntry: async (from, to) => {
        moves += 1;
        if (moves === 2) throw new Error("simulated mid-move failure");
        await rename(from, to);
      },
    });
    expect(result.status).toBe("failed");
    expect(result.removed).toEqual([]);
    expect(
      await files.exists(join(root, "skills", "gherkin-bdd", "SKILL.md")),
    ).toBe(true);
    expect(
      await files.exists(
        join(root, "skills", "project-validation", "SKILL.md"),
      ),
    ).toBe(true);
  });

  it("Scenario: registry 覆盖且仅覆盖 packaged certified set", async () => {
    const packaged = await inventoryPackagedSkills();
    const registry = buildRuntimeSkillPolicyRegistry(packaged.names);
    expect(registry.map((entry) => entry.name)).toEqual([...packaged.names]);
    expect(() => assertRegistryMatchesRuntimeConstants(registry)).not.toThrow();
    expect(
      registry.find((entry) => entry.name === "book-ddd-distilled-modeling")
        ?.requiredGates,
    ).toEqual(["ddd-boundary"]);
  });

  it("Scenario: registry 的 route 与 gate 映射与 Runtime 常量一致", async () => {
    const packaged = await inventoryPackagedSkills();
    const registry = buildRuntimeSkillPolicyRegistry(packaged.names);
    expect(registry.find((entry) => entry.name === "gherkin-bdd")?.route).toBe(
      "bdd-tdd",
    );
    expect(
      registry.find((entry) => entry.name === "book-release-readiness")?.route,
    ).toBe("release");
    expect(
      registry.find((entry) => entry.name === "book-release-readiness")
        ?.requiredGates,
    ).toEqual(["release-readiness"]);
    expect(
      registry.every(
        (entry) =>
          entry.route === undefined ||
          entry.route === "bdd-tdd" ||
          entry.route === "release",
      ),
    ).toBe(true);
  });

  it("Scenario: packagedDigest 绑定 skill 树内容而非仅名字", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-digest-"));
    roots.push(root);
    await writeTree(join(root, "gherkin-bdd"), { "SKILL.md": "first\n" });
    const before = await inventoryPackagedSkills(root);
    await writeFile(join(root, "gherkin-bdd", "SKILL.md"), "second\n");
    const after = await inventoryPackagedSkills(root);
    expect(before.names).toEqual(after.names);
    expect(before.packagedDigest).not.toBe(after.packagedDigest);
  });

  it("Scenario: 无效 packaged certified 名不得回落到全局 leftover", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-invalid-fallback-"));
    roots.push(root);
    await writeTree(join(root, "global", "gherkin-bdd"), {
      "SKILL.md": "leftover\n",
    });
    const content = await readCertifiedOrGlobalSkill(
      files,
      "gherkin-bdd",
      [],
      join(root, "global"),
      {
        packagedRoot: join(root, "packaged"),
        invalidSkills: ["gherkin-bdd"],
      },
    );
    expect(content).toBeUndefined();
  });
});
