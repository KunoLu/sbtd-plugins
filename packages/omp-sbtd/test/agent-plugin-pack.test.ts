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

const OMP_RUNTIME_PACKAGE = "@oh-my-pi/pi-coding-agent";

function dependencySpec(
  manifest: unknown,
  section: "peerDependencies" | "devDependencies",
): unknown {
  if (!manifest || typeof manifest !== "object" || !(section in manifest)) {
    return undefined;
  }
  const entries: unknown = manifest[section];
  if (
    !entries ||
    typeof entries !== "object" ||
    !(OMP_RUNTIME_PACKAGE in entries)
  ) {
    return undefined;
  }
  return entries[OMP_RUNTIME_PACKAGE];
}

describe("Feature: Hybrid Plugin M2 组包", () => {
  it("Scenario: clean pack 的 tarball 通过 manifest/skill/containment gate", async () => {
    const packageRoot = await packPlugin();

    const [manifestText, packedPackageText] = await Promise.all([
      readFile(join(packageRoot, "plugin.json"), "utf8"),
      readFile(join(packageRoot, "package.json"), "utf8"),
    ]);
    const manifest: unknown = JSON.parse(manifestText);
    const packedPackage: unknown = JSON.parse(packedPackageText);
    const packedVersion =
      packedPackage &&
      typeof packedPackage === "object" &&
      "version" in packedPackage
        ? packedPackage.version
        : undefined;
    expect(packedVersion).toBe("0.1.0-rc.13");
    // Tarball-bound identity: the packed manifest must carry the widened
    // peer range and the exact development pin (Slice 3 candidate contract).
    expect(dependencySpec(packedPackage, "peerDependencies")).toBe(
      ">=17.3.5 <18",
    );
    expect(dependencySpec(packedPackage, "devDependencies")).toBe("17.3.5");
    expect(() =>
      validatePluginManifest(manifest, {
        expectedVersion: packedVersion as string,
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
    const policyText = await readFile(
      join(packageRoot, "validation/p0/compatibility.v2.json"),
      "utf8",
    );
    const policy: unknown = JSON.parse(policyText);
    expect(policy).toMatchObject({
      schemaVersion: 2,
      peerRange: ">=17.3.5 <18",
      developmentRuntimeVersion: "17.3.5",
    });
    expect(policy).not.toHaveProperty("currentRuntimeVersion");
    expect(policy).not.toHaveProperty("latestRuntimeVersion");
    expect(policy).not.toHaveProperty("testedVersions");
    expect(entries).toContain("validation/p0/compatibility.v2.json");
    const sbom = JSON.parse(
      await readFile(join(packageRoot, "SBOM.spdx.json"), "utf8"),
    ) as { files: Array<{ fileName: string }> };
    expect(sbom.files.map((file) => file.fileName)).toContain(
      "./validation/p0/compatibility.v2.json",
    );
    expect(
      packedPackage &&
        typeof packedPackage === "object" &&
        "files" in packedPackage &&
        Array.isArray(packedPackage.files) &&
        packedPackage.files.includes("validation/p0/compatibility.v2.json"),
    ).toBe(true);
    expect(
      entries.some((entry) => entry.startsWith("validation/p0/evidence/")),
    ).toBe(false);
    for (const prefix of ["commands/", "hooks/", "tools/", "runtime/"]) {
      expect(
        entries.some((entry) => entry.startsWith(prefix)),
        `tarball must not contain ${prefix}`,
      ).toBe(false);
    }
    expect(entries).not.toContain("mcp.json");
  }, 120_000);
});
