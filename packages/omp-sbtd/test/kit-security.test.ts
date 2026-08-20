import {
  cp,
  mkdtemp,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";
import { loadEmbeddedKitFromDirectory } from "../src/kit/index.ts";

const pluginRoot = new URL("..", import.meta.url).pathname;
const temporaryRoots: string[] = [];

const mutableManifestSchema = z
  .object({ assets: z.record(z.string(), z.string()) })
  .passthrough();

async function fixtureKit(): Promise<{ root: string; kitRoot: string }> {
  const root = await mkdtemp(join(tmpdir(), "kpi-embedded-kit-security-"));
  temporaryRoots.push(root);
  const kitRoot = join(root, "kit");
  await cp(join(pluginRoot, "kit"), kitRoot, { recursive: true });
  return { root, kitRoot };
}

async function expectSafeFailure(
  run: () => Promise<unknown>,
  root: string,
  pattern: RegExp,
): Promise<void> {
  let failure: unknown;
  try {
    await run();
  } catch (error) {
    failure = error;
  }
  expect(failure).toBeInstanceOf(Error);
  if (!(failure instanceof Error)) throw new Error("expected an Error");
  expect(failure.message).toMatch(pattern);
  expect(failure.message).not.toContain(root);
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("Feature: 严格 OMP Plugin 发布视图", () => {
  it("Scenario: embedded manifest 的非 POSIX asset key 不能逃逸 Kit 根目录", async () => {
    const { root, kitRoot } = await fixtureKit();
    const manifestPath = join(kitRoot, "manifest.json");
    const original = await readFile(manifestPath, "utf8");

    for (const path of [
      "..\\..\\outside.txt",
      "/outside.txt",
      "docs//outside.txt",
      "docs/./outside.txt",
      "docs/../outside.txt",
    ]) {
      const manifest = mutableManifestSchema.parse(JSON.parse(original));
      manifest.assets[path] = "0".repeat(64);
      await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
      await expectSafeFailure(
        () => loadEmbeddedKitFromDirectory(kitRoot),
        root,
        /unsafe embedded Kit asset path/,
      );
      await writeFile(manifestPath, original);
    }
  });

  it("Scenario: embedded asset symlink 在读取前失败且错误不泄露本地根路径", async () => {
    const { root, kitRoot } = await fixtureKit();
    const catalogPath = join(kitRoot, "catalog.json");
    const catalog = await readFile(catalogPath);
    const outside = join(root, "outside-catalog.json");
    await writeFile(outside, catalog);
    await rm(catalogPath);
    await symlink(outside, catalogPath);

    await expectSafeFailure(
      () => loadEmbeddedKitFromDirectory(kitRoot),
      root,
      /symbolic link/,
    );
  });
});
