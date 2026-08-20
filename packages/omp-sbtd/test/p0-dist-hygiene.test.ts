import { execFile as executeFile } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";
import {
  assertCompiledArtifactsMatchSources,
  verifyPluginReleaseArtifacts,
  writePluginSpdxSbom,
} from "../scripts/p0/release-validator.ts";

const workspaceRoot = new URL("../../..", import.meta.url).pathname;
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const kitRoot = join(workspaceRoot, "packages/sbtd-workflow-kit");
const cleanDistPath = join(pluginRoot, "scripts/clean-dist.mjs");

const runProcess = promisify(executeFile);
const temporaryRoots: string[] = [];

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-p0-dist-"));
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

async function writeTree(root: string, files: Record<string, string>) {
  await Promise.all(
    Object.entries(files).map(async ([path, content]) => {
      const target = join(root, path);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, content);
    }),
  );
}

async function expectStaleRejection(
  run: () => Promise<unknown>,
  stalePaths: readonly string[],
  payloadMarker?: string,
): Promise<void> {
  try {
    await run();
  } catch (error) {
    expect(error).toMatchObject({
      name: "P0ValidationError",
      code: "PACKAGE_CONTENT_INVALID",
    });
    const serialized = JSON.stringify(error);
    for (const stalePath of stalePaths) expect(serialized).toContain(stalePath);
    if (payloadMarker !== undefined)
      expect(serialized).not.toContain(payloadMarker);
    return;
  }
  throw new Error(
    `expected PACKAGE_CONTENT_INVALID for ${stalePaths.join(", ")}`,
  );
}

const DIST_SUFFIXES = [".js", ".js.map", ".d.ts", ".d.ts.map"] as const;

async function listRelativeFiles(root: string, prefix = ""): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const relative = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
    if (entry.isDirectory())
      files.push(
        ...(await listRelativeFiles(join(root, entry.name), relative)),
      );
    else files.push(relative);
  }
  return files.sort();
}

describe("Feature: P0 发布一致性与证据 - 编译产物卫生", () => {
  it("Scenario: build 在编译前以跨平台方式确定性清理 dist", async () => {
    const root = await temporaryRoot();
    const distRoot = join(root, "dist");
    await writeTree(distRoot, {
      "extension.js": "compiled\n",
      "onboard/python-bridge.js": "stale\n",
    });
    const sibling = join(root, "keep.txt");
    await writeFile(sibling, "untouched\n", "utf8");

    const runClean = () =>
      runProcess(process.execPath, [cleanDistPath], {
        cwd: pluginRoot,
        env: { ...process.env, KPI_DIST_DESTINATION: distRoot },
      });
    await runClean();
    await expect(stat(distRoot)).rejects.toMatchObject({ code: "ENOENT" });
    await expect(readFile(sibling, "utf8")).resolves.toBe("untouched\n");
    // Idempotent: a second clean over a missing directory still succeeds.
    await runClean();

    const packageManifest = JSON.parse(
      await readFile(join(pluginRoot, "package.json"), "utf8"),
    ) as { scripts: Record<string, string> };
    const build = packageManifest.scripts.build;
    expect(build).toContain("clean-dist.mjs");
    expect(build.indexOf("clean-dist.mjs")).toBeLessThan(
      build.indexOf("tsc -p tsconfig.json"),
    );
  });

  it("Scenario: 无当前源码的编译产物使发布门失败关闭", async () => {
    const root = await temporaryRoot();
    const syntheticPlugin = join(root, "plugin");
    await writeTree(syntheticPlugin, {
      "src/extension.ts": "export default 1;\n",
      "src/onboard/index.ts": "export {};\n",
      "dist/extension.js": "compiled\n",
      "dist/extension.js.map": "{}\n",
      "dist/extension.d.ts": "declare const x: 1;\n",
      "dist/extension.d.ts.map": "{}\n",
      "dist/onboard/index.js": "compiled\n",
      "dist/onboard/index.js.map": "{}\n",
      "dist/onboard/index.d.ts": "export {};\n",
      "dist/onboard/index.d.ts.map": "{}\n",
    });
    await expect(
      assertCompiledArtifactsMatchSources(syntheticPlugin),
    ).resolves.toBeUndefined();

    const marker = "stale-python-bridge-payload-marker";
    await writeTree(syntheticPlugin, {
      "dist/onboard/python-bridge.js": `${marker}\n`,
      "dist/onboard/python-bridge.d.ts": `${marker}\n`,
    });
    await expectStaleRejection(
      () => assertCompiledArtifactsMatchSources(syntheticPlugin),
      ["dist/onboard/python-bridge.d.ts", "dist/onboard/python-bridge.js"],
      marker,
    );

    const orphanMap = await temporaryRoot();
    const orphanPlugin = join(orphanMap, "plugin");
    await writeTree(orphanPlugin, {
      "src/extension.ts": "export default 1;\n",
      "dist/extension.js": "compiled\n",
      "dist/orphan.js.map": "{}\n",
      "dist/notes.txt": "not a compiler output\n",
    });
    await expectStaleRejection(
      () => assertCompiledArtifactsMatchSources(orphanPlugin),
      ["dist/notes.txt", "dist/orphan.js.map"],
    );
  });

  it("Scenario: 来源忠实的实际树通过发布门而植入的 Python Onboard 残留失败关闭", async () => {
    const root = await temporaryRoot();
    const copyWorkspace = join(root, "workspace");
    const copyPlugin = join(copyWorkspace, "packages/omp-sbtd");
    const copyKit = join(copyWorkspace, "packages/sbtd-workflow-kit");
    await mkdir(copyPlugin, { recursive: true });
    await mkdir(copyKit, { recursive: true });

    // Copy the real release inputs: identity, legal inventory, embedded Kit.
    await Promise.all([
      cp(
        join(workspaceRoot, "package.json"),
        join(copyWorkspace, "package.json"),
      ),
      cp(join(workspaceRoot, "LICENSE"), join(copyWorkspace, "LICENSE")),
      cp(join(pluginRoot, "package.json"), join(copyPlugin, "package.json")),
      cp(join(pluginRoot, "README.md"), join(copyPlugin, "README.md")),
      cp(join(pluginRoot, "LICENSE"), join(copyPlugin, "LICENSE")),
      cp(join(pluginRoot, "SECURITY.md"), join(copyPlugin, "SECURITY.md")),
      cp(join(pluginRoot, "CHANGELOG.md"), join(copyPlugin, "CHANGELOG.md")),
      cp(
        join(pluginRoot, "THIRD_PARTY_NOTICES.md"),
        join(copyPlugin, "THIRD_PARTY_NOTICES.md"),
      ),
      cp(join(pluginRoot, "plugin.json"), join(copyPlugin, "plugin.json")),
      cp(join(pluginRoot, "skills"), join(copyPlugin, "skills"), {
        recursive: true,
      }),
      cp(join(pluginRoot, "kit"), join(copyPlugin, "kit"), {
        recursive: true,
      }),
      cp(join(kitRoot, "package.json"), join(copyKit, "package.json")),
      cp(join(kitRoot, "LICENSE"), join(copyKit, "LICENSE")),
      cp(join(pluginRoot, "src"), join(copyPlugin, "src"), {
        recursive: true,
      }),
    ]);

    // Rebuild a source-faithful dist from the real sources: copy exactly the
    // compiler artifacts whose TypeScript source exists, dropping any stale
    // residue (such as dist/onboard/python-bridge.*) that no clean build
    // could emit.
    const sourceFiles = new Set(
      await listRelativeFiles(join(copyPlugin, "src")),
    );
    const distRoot = join(copyPlugin, "dist");
    const realDistFiles = await listRelativeFiles(join(pluginRoot, "dist"));
    for (const distFile of realDistFiles) {
      const source = DIST_SUFFIXES.find((suffix) => distFile.endsWith(suffix));
      if (source === undefined) continue;
      const sourcePath = `${distFile.slice(0, -source.length)}.ts`;
      if (!sourceFiles.has(sourcePath)) continue;
      const target = join(distRoot, distFile);
      await mkdir(dirname(target), { recursive: true });
      await cp(join(pluginRoot, "dist", distFile), target);
    }

    await writePluginSpdxSbom({
      workspaceRoot: copyWorkspace,
      pluginRoot: copyPlugin,
      kitRoot: copyKit,
    });
    await expect(
      verifyPluginReleaseArtifacts({
        workspaceRoot: copyWorkspace,
        pluginRoot: copyPlugin,
        kitRoot: copyKit,
      }),
    ).resolves.toMatchObject({
      sourceTreeSha256: expect.stringMatching(/^[0-9a-f]{64}$/),
    });

    // Plant the exact stale residue class observed in the real dirty dist:
    // both the SBOM writer and the release gate must fail closed.
    const marker = "stale-python-bridge-payload-marker";
    await writeTree(distRoot, {
      "onboard/python-bridge.js": `${marker}\n`,
      "onboard/python-bridge.js.map": `${marker}\n`,
      "onboard/python-bridge.d.ts": `${marker}\n`,
      "onboard/python-bridge.d.ts.map": `${marker}\n`,
    });
    const stalePaths = [
      "dist/onboard/python-bridge.d.ts",
      "dist/onboard/python-bridge.d.ts.map",
      "dist/onboard/python-bridge.js",
      "dist/onboard/python-bridge.js.map",
    ];
    await expectStaleRejection(
      () =>
        verifyPluginReleaseArtifacts({
          workspaceRoot: copyWorkspace,
          pluginRoot: copyPlugin,
          kitRoot: copyKit,
        }),
      stalePaths,
      marker,
    );
    await expectStaleRejection(
      () =>
        writePluginSpdxSbom({
          workspaceRoot: copyWorkspace,
          pluginRoot: copyPlugin,
          kitRoot: copyKit,
        }),
      stalePaths,
      marker,
    );
  }, 60_000);

  it("Scenario: 受控提升 stage 无源码时仍生成 SBOM 而 source package 保持严格 dist 检查", async () => {
    const root = await temporaryRoot();
    const stagePlugin = join(root, "promotion-stage");
    await mkdir(stagePlugin, { recursive: true });
    await Promise.all([
      cp(join(pluginRoot, "package.json"), join(stagePlugin, "package.json")),
      cp(join(pluginRoot, "README.md"), join(stagePlugin, "README.md")),
      cp(join(pluginRoot, "LICENSE"), join(stagePlugin, "LICENSE")),
      cp(join(pluginRoot, "SECURITY.md"), join(stagePlugin, "SECURITY.md")),
      cp(join(pluginRoot, "CHANGELOG.md"), join(stagePlugin, "CHANGELOG.md")),
      cp(
        join(pluginRoot, "THIRD_PARTY_NOTICES.md"),
        join(stagePlugin, "THIRD_PARTY_NOTICES.md"),
      ),
      cp(join(pluginRoot, "plugin.json"), join(stagePlugin, "plugin.json")),
      cp(join(pluginRoot, "skills"), join(stagePlugin, "skills"), {
        recursive: true,
      }),
      cp(join(pluginRoot, "dist"), join(stagePlugin, "dist"), {
        recursive: true,
      }),
      cp(join(pluginRoot, "kit"), join(stagePlugin, "kit"), {
        recursive: true,
      }),
    ]);

    await expect(
      writePluginSpdxSbom({
        workspaceRoot,
        pluginRoot: stagePlugin,
        kitRoot,
      }),
    ).rejects.toMatchObject({ code: "PACKAGE_CONTENT_INVALID" });
    await expect(
      writePluginSpdxSbom({
        workspaceRoot,
        pluginRoot: stagePlugin,
        kitRoot,
        releaseRoot: "staged-promotion",
      }),
    ).resolves.toMatchObject({
      sourceTreeSha256: expect.stringMatching(/^[0-9a-f]{64}$/),
    });
  });
});
