import { execFile as executeFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";
import { readAgentPluginManifest } from "../scripts/embed-agent-skills.mjs";
import { validatePluginManifest } from "../scripts/plugin-manifest.mjs";

const runProcess = promisify(executeFile);
const packageManager = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const workspaceRoot = fileURLToPath(new URL("../../..", import.meta.url));
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const generatedManifestUrl = import.meta.resolve(
  "@kunolu/sbtd-workflow-kit/generated-agent-plugin/manifest.json",
);
const generatedRoot = fileURLToPath(new URL(".", generatedManifestUrl));

const temporaryRoots: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

async function packPlugin(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-agent-pack-"));
  temporaryRoots.push(root);
  const packedRoot = join(root, "packed");
  const extractedRoot = join(root, "extracted");
  await mkdir(packedRoot, { recursive: true });
  await mkdir(extractedRoot, { recursive: true });
  const { stdout } = await runProcess(
    packageManager,
    ["pack", "--pack-destination", packedRoot, "--json"],
    { cwd: pluginRoot },
  );
  const packed = JSON.parse(stdout) as { filename: string };
  const tarball = isAbsolute(packed.filename)
    ? packed.filename
    : resolve(packedRoot, packed.filename);
  await runProcess("tar", ["-xzf", tarball, "-C", extractedRoot]);
  return join(extractedRoot, "package");
}

async function packedPaths(root: string, base = root): Promise<string[]> {
  const paths: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = `${root}/${entry.name}`;
    if (entry.isDirectory()) paths.push(...(await packedPaths(path, base)));
    else if (entry.isFile())
      paths.push(relative(base, path).split(sep).join("/"));
  }
  return paths.sort();
}

describe("Feature: Hybrid Plugin M2 组包", () => {
  it("Scenario: clean pack 的 tarball 通过 manifest/skill/containment gate", async () => {
    const packageRoot = await packPlugin();

    const [manifestText, packedPackageText] = await Promise.all([
      readFile(join(packageRoot, "plugin.json"), "utf8"),
      readFile(join(packageRoot, "package.json"), "utf8"),
    ]);
    const manifest: unknown = JSON.parse(manifestText);
    const packedPackage = JSON.parse(packedPackageText) as {
      version: unknown;
    };
    expect(packedPackage.version).toBe("0.1.0-rc.12");
    expect(() =>
      validatePluginManifest(manifest, {
        expectedVersion: packedPackage.version as string,
      }),
    ).not.toThrow();

    const agentPluginManifest = await readAgentPluginManifest(generatedRoot);
    const skillsRoot = join(packageRoot, "skills");
    const packedSkills = (await readdir(skillsRoot)).sort();
    expect(packedSkills).toEqual([...agentPluginManifest.certified].sort());
    expect(packedSkills.length).toBe(agentPluginManifest.certifiedCount);
    for (const name of agentPluginManifest.certified) {
      const expectedFiles = agentPluginManifest.skills[name].files;
      for (const [path, digest] of Object.entries(expectedFiles)) {
        const bytes = await readFile(join(skillsRoot, name, path));
        expect(
          createHash("sha256").update(bytes).digest("hex"),
          `skills/${name}/${path}`,
        ).toBe(digest);
      }
    }

    const entries = await packedPaths(packageRoot);
    for (const prefix of ["commands/", "hooks/", "tools/", "runtime/"]) {
      expect(
        entries.some((entry) => entry.startsWith(prefix)),
        `tarball must not contain ${prefix}`,
      ).toBe(false);
    }
    expect(entries).not.toContain("mcp.json");
  }, 120_000);
});
