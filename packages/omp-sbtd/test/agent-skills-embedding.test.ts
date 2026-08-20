import {
  cp,
  mkdtemp,
  readdir,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  embedAgentSkills,
  readAgentPluginManifest,
  validateEmbeddedAgentSkills,
} from "../scripts/embed-agent-skills.mjs";

const generatedManifestUrl = import.meta.resolve(
  "@kunolu/sbtd-workflow-kit/generated-agent-plugin/manifest.json",
);
const generatedRoot = fileURLToPath(new URL(".", generatedManifestUrl));
const pluginRoot = fileURLToPath(new URL("..", import.meta.url));
const pluginSkills = join(pluginRoot, "skills");

const temporaryRoots: string[] = [];

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-agent-skills-"));
  temporaryRoots.push(root);
  return root;
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

async function files(root: string, base = root): Promise<string[]> {
  const paths: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = `${root}/${entry.name}`;
    if (entry.isDirectory()) paths.push(...(await files(path, base)));
    else if (entry.isFile())
      paths.push(relative(base, path).split(sep).join("/"));
  }
  return paths.sort();
}

async function snapshot(root: string): Promise<ReadonlyMap<string, Buffer>> {
  return new Map(
    await Promise.all(
      (await files(root)).map(
        async (path) =>
          [path, await readFile(join(root, path))] as [string, Buffer],
      ),
    ),
  );
}

async function stagedCertifiedCopy(): Promise<{
  readonly source: string;
  readonly destination: string;
  readonly certified: readonly string[];
}> {
  const root = await temporaryRoot();
  const destination = join(root, "skills");
  const manifest = await readAgentPluginManifest(generatedRoot);
  for (const name of manifest.certified) {
    await cp(join(generatedRoot, "skills", name), join(destination, name), {
      recursive: true,
    });
  }
  return { source: generatedRoot, destination, certified: manifest.certified };
}

describe("Feature: Hybrid Plugin M2 组包", () => {
  it("Scenario: 组包把 certified set 复制到根 skills 目录", async () => {
    const root = await temporaryRoot();
    const destination = join(root, "skills");
    await embedAgentSkills({ source: generatedRoot, destination });
    const manifest = await readAgentPluginManifest(generatedRoot);
    const embedded = (await readdir(destination)).sort();
    expect(embedded).toEqual([...manifest.certified].sort());
    expect(embedded.length).toBe(manifest.certifiedCount);
    const [expected, actual] = await Promise.all([
      snapshot(join(generatedRoot, "skills")),
      snapshot(destination),
    ]);
    expect([...actual.keys()]).toEqual([...expected.keys()]);
    for (const [path, bytes] of expected) {
      expect(actual.get(path)?.equals(bytes)).toBe(true);
    }
    await expect(
      validateEmbeddedAgentSkills({ source: generatedRoot, destination }),
    ).resolves.toBeUndefined();
  });

  it("Scenario: 已提交的根 skills 与第三树 certified 投影一致", async () => {
    const manifest = await readAgentPluginManifest(generatedRoot);
    const embedded = (await readdir(pluginSkills)).sort();
    expect(embedded).toEqual([...manifest.certified].sort());
    expect(embedded.length).toBe(manifest.certifiedCount);
    await expect(
      validateEmbeddedAgentSkills({
        source: generatedRoot,
        destination: pluginSkills,
      }),
    ).resolves.toBeUndefined();
  });

  it("Scenario: onboard-owned 与 explicit non-candidates 不进根 skills", async () => {
    const embedded = await readdir(pluginSkills);
    for (const name of [
      "trellis-workflow",
      "sbtd-workflow-onboard",
      "trellis-channel",
    ]) {
      expect(embedded).not.toContain(name);
    }
  });

  it("Scenario: 手改某个 SKILL.md 的一个字节使校验失败", async () => {
    const { source, destination } = await stagedCertifiedCopy();
    const target = join(destination, "gherkin-bdd", "SKILL.md");
    const original = await readFile(target);
    const mutated = Buffer.from(original);
    mutated[0] = original[0] === 0x23 ? 0x21 : 0x23;
    await writeFile(target, mutated);
    await expect(
      validateEmbeddedAgentSkills({ source, destination }),
    ).rejects.toThrow(/gherkin-bdd\/SKILL\.md/);
  });

  it("Scenario: 删除一个 certified skill 目录使校验失败", async () => {
    const { source, destination } = await stagedCertifiedCopy();
    await rm(join(destination, "lessons-record"), { recursive: true });
    await expect(
      validateEmbeddedAgentSkills({ source, destination }),
    ).rejects.toThrow(/lessons-record|certified/i);
  });

  it("Scenario: 添加一个非 certified 目录使校验失败", async () => {
    const { source, destination } = await stagedCertifiedCopy();
    await cp(
      join(destination, "lessons-record"),
      join(destination, "trellis-workflow"),
      { recursive: true },
    );
    await expect(
      validateEmbeddedAgentSkills({ source, destination }),
    ).rejects.toThrow(/trellis-workflow|unexpected/i);
  });

  it("Scenario: 把某个文件换成符号链接使校验失败", async () => {
    const { source, destination } = await stagedCertifiedCopy();
    const target = join(destination, "lessons-record", "SKILL.md");
    const bytes = await readFile(target);
    const realCopy = join(destination, "lessons-record", "SKILL.real.md");
    await rm(target);
    await writeFile(realCopy, bytes);
    await symlink("SKILL.real.md", target);
    await expect(
      validateEmbeddedAgentSkills({ source, destination }),
    ).rejects.toThrow();
  });

  it("Scenario: certified skill 名含路径穿越时校验失败", async () => {
    const root = await temporaryRoot();
    const source = join(root, "generated-agent-plugin");
    await cp(generatedRoot, source, { recursive: true });
    const manifestPath = join(source, "manifest.json");
    const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
      certified: string[];
      skills: Record<string, unknown>;
    };
    const originalName = "gherkin-bdd";
    const escapedName = "../x";
    manifest.certified = manifest.certified.map((name) =>
      name === originalName ? escapedName : name,
    );
    manifest.skills[escapedName] = manifest.skills[originalName];
    Reflect.deleteProperty(manifest.skills, originalName);
    await writeFile(manifestPath, `${JSON.stringify(manifest)}\n`);
    await expect(readAgentPluginManifest(source)).rejects.toThrow(
      /unsafe certified skill name/i,
    );
    await expect(
      embedAgentSkills({
        source,
        destination: join(root, "skills"),
      }),
    ).rejects.toThrow(/unsafe certified skill name/i);
    await expect(readdir(join(root, "x"))).rejects.toThrow();
    await expect(readdir(join(root, "skills"))).rejects.toThrow();
  });

  it("Scenario: kit 目录仍只嵌入 generated-omp 投影", async () => {
    const kitManifest = JSON.parse(
      await readFile(join(pluginRoot, "kit", "manifest.json"), "utf8"),
    ) as { runtime?: unknown; transformVersion?: unknown };
    expect(kitManifest.runtime).toBe("omp");
    await expect(readdir(join(pluginRoot, "kit", "skills"))).rejects.toThrow();
  });
});
