// Contract tests for the shared npm-offline-v1 subject Plugin installer
// (scripts/p0/install-subject-plugin.ts) — the single installer generation
// shared by the trusted §4 publish gate and the certification cells.
//
// The fixture tarball is a real `npm pack` of a minimal @kunolu/omp-sbtd
// package whose only production dependency is zod@4.1.12 (the same registry
// dependency shape as the real subject), so the npm-generated diagnostic
// lock must carry an npm-written SRI for both the staged tarball and zod.
// One shared generate pass (network, beforeAll) feeds every offline
// assertion; the offline paths under test never touch the network.
//
// Trace: packages/omp-sbtd/features/p0-conformance-release.feature
//   Rule: 精确 tarball 四命令是所有 RC 的唯一 npm 发布兼容性 Gate
// Trace: docs/assets/omp-plugin-cloud-section4-and-certification-plan.md §5
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { copyFile, mkdir, mkdtemp, readdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import {
  ciOffline,
  generateLockAndCache,
  INSTALLER_GENERATION,
  installSubjectPluginOfflineV1,
  stageSubjectLayout,
} from "../scripts/p0/install-subject-plugin.ts";

const sha256File = (path: string): string =>
  createHash("sha256").update(readFileSync(path)).digest("hex");

const HEX64 = /^[a-f0-9]{64}$/;

let root: string;
let tarballPath: string;
let tarballSha256: string;
let generatedRunDir: string;
let generatedCacheDir: string;
let generated: {
  readonly packageLockSha256: string;
  readonly installerCacheSha256: string;
};

beforeAll(async () => {
  root = await mkdtemp(join(tmpdir(), "omp-install-subject-plugin-"));
  const fixtureDir = join(root, "fixture");
  await mkdir(join(fixtureDir, "dist"), { recursive: true });
  await writeFile(
    join(fixtureDir, "package.json"),
    `${JSON.stringify(
      {
        name: "@kunolu/omp-sbtd",
        version: "0.0.0-installer-fixture.1",
        type: "module",
        main: "./dist/extension.js",
        dependencies: { zod: "4.1.12" },
      },
      null,
      2,
    )}\n`,
  );
  await writeFile(join(fixtureDir, "dist", "extension.js"), "export {};\n");
  const packDir = join(root, "pack");
  await mkdir(packDir, { recursive: true });
  execFileSync("npm", ["pack", "--pack-destination", packDir], {
    cwd: fixtureDir,
    stdio: "ignore",
  });
  const tarballs = (await readdir(packDir)).filter((n) => n.endsWith(".tgz"));
  if (tarballs.length !== 1)
    throw new Error("fixture pack did not produce exactly one tarball");
  tarballPath = join(packDir, tarballs[0]);
  tarballSha256 = sha256File(tarballPath);
  generatedRunDir = join(root, "generated", "run");
  generatedCacheDir = join(root, "generated", "cache");
  await stageSubjectLayout({ runDir: generatedRunDir, tarballPath });
  generated = await generateLockAndCache({
    runDir: generatedRunDir,
    cacheDir: generatedCacheDir,
    homeDir: join(root, "home"),
  });
}, 300_000);

describe("npm-offline-v1 subject installer layout", () => {
  it("stages the fixed relative layout with no absolute paths", async () => {
    const runDir = join(root, "layout-run");
    const staged = await stageSubjectLayout({ runDir, tarballPath });
    expect(staged.pluginTarballSha256).toBe(tarballSha256);
    expect(sha256File(join(runDir, "plugin.tgz"))).toBe(tarballSha256);
    const manifest = JSON.parse(
      readFileSync(join(runDir, "package.json"), "utf8"),
    ) as { dependencies: Record<string, string> };
    expect(manifest.dependencies).toEqual({
      "@kunolu/omp-sbtd": "file:./plugin.tgz",
    });
    // The layout must be portable: no absolute tmp path leaks into it.
    expect(readFileSync(join(runDir, "package.json"), "utf8")).not.toContain(
      root,
    );
  });
});

describe("npm-offline-v1 lock generation (network, trusted jobs only)", () => {
  it("lets npm write the lock: SRI integrity, never a hand-written SHA-256", () => {
    const lockPath = join(generatedRunDir, "package-lock.json");
    expect(existsSync(lockPath)).toBe(true);
    const raw = readFileSync(lockPath, "utf8");
    const lock = JSON.parse(raw) as {
      packages: Record<
        string,
        { resolved?: string; integrity?: string; version?: string }
      >;
    };
    const subject = lock.packages["node_modules/@kunolu/omp-sbtd"];
    // npm normalizes the relative spec; both forms are portable.
    expect(subject?.resolved).toMatch(/^file:(\.\/)?plugin\.tgz$/);
    expect(subject?.integrity).toMatch(/^sha512-/);
    // The content SHA-256 lives outside the lock as pluginTarballSha256;
    // it must never appear inside the lock (e.g. hand-written integrity).
    expect(raw).not.toContain(tarballSha256);
    // The registry production dependency is pinned by npm-written SRI too.
    expect(lock.packages["node_modules/zod"]?.version).toBe("4.1.12");
    expect(lock.packages["node_modules/zod"]?.integrity).toMatch(/^sha512-/);
    expect(generated.packageLockSha256).toBe(sha256File(lockPath));
  });

  it("materializes a content-addressed cache the offline ci can consume", () => {
    expect(generated.installerCacheSha256).toMatch(HEX64);
    const contentRoot = join(generatedCacheDir, "_cacache", "content-v2");
    expect(existsSync(contentRoot)).toBe(true);
  });
});

describe("npm-offline-v1 offline install (no network)", () => {
  it(
    "installs the subject fully offline from the generated lock and cache",
    { timeout: 180_000 },
    async () => {
      const runDir = join(root, "offline-run");
      await stageSubjectLayout({ runDir, tarballPath });
      await copyFile(
        join(generatedRunDir, "package-lock.json"),
        join(runDir, "package-lock.json"),
      );
      const result = await ciOffline({
        runDir,
        cacheDir: generatedCacheDir,
        homeDir: join(root, "home"),
      });
      expect(existsSync(result.extensionPath)).toBe(true);
      // The registry dependency must come from the cache, not the network.
      expect(
        existsSync(join(runDir, "node_modules", "zod", "package.json")),
      ).toBe(true);
      expect(result.installerGeneration).toBe(INSTALLER_GENERATION);
      expect(result.installerGeneration).toBe("npm-offline-v1");
      expect(result.pluginTarballSha256).toBe(tarballSha256);
      expect(result.packageLockSha256).toBe(generated.packageLockSha256);
      // An offline ci never mutates the content-addressed cache payloads.
      expect(result.installerCacheSha256).toBe(generated.installerCacheSha256);
    },
  );

  it("fails closed when the pre-generated lock is missing", async () => {
    const runDir = join(root, "no-lock-run");
    await stageSubjectLayout({ runDir, tarballPath });
    await expect(
      ciOffline({ runDir, cacheDir: generatedCacheDir }),
    ).rejects.toThrow("PLUGIN_INSTALL_LOCK_REQUIRED");
  });

  it("fails closed when lock integrity is a content SHA-256 instead of SRI", async () => {
    const runDir = join(root, "stuffed-integrity-run");
    await stageSubjectLayout({ runDir, tarballPath });
    const lock = JSON.parse(
      readFileSync(join(generatedRunDir, "package-lock.json"), "utf8"),
    ) as {
      packages: Record<string, { integrity?: string }>;
    };
    const subject = lock.packages["node_modules/@kunolu/omp-sbtd"];
    if (subject === undefined) throw new Error("fixture lock lacks subject");
    subject.integrity = tarballSha256;
    await writeFile(
      join(runDir, "package-lock.json"),
      `${JSON.stringify(lock)}\n`,
    );
    await expect(
      ciOffline({
        runDir,
        cacheDir: generatedCacheDir,
        homeDir: join(root, "home"),
      }),
    ).rejects.toThrow("PLUGIN_INSTALL_FAILED");
  });

  it(
    "fails closed when the cache cannot satisfy the lock offline",
    { timeout: 180_000 },
    async () => {
      const runDir = join(root, "empty-cache-run");
      const emptyCache = join(root, "empty-cache");
      await mkdir(emptyCache, { recursive: true });
      await stageSubjectLayout({ runDir, tarballPath });
      await copyFile(
        join(generatedRunDir, "package-lock.json"),
        join(runDir, "package-lock.json"),
      );
      // zod is not in the empty cache and --offline forbids the network.
      await expect(
        ciOffline({
          runDir,
          cacheDir: emptyCache,
          homeDir: join(root, "home"),
        }),
      ).rejects.toThrow("PLUGIN_INSTALL_FAILED");
    },
  );

  it(
    "installs from a trusted lock+cache handoff without generating",
    { timeout: 180_000 },
    async () => {
      // The certification-cell path: a staged lock is handed in and the
      // installer must only run the offline ci (no npm install at all).
      const runDir = join(root, "handoff-run");
      const result = await installSubjectPluginOfflineV1({
        runDir,
        tarballPath,
        cacheDir: generatedCacheDir,
        lockFilePath: join(generatedRunDir, "package-lock.json"),
        homeDir: join(root, "home"),
      });
      expect(existsSync(result.extensionPath)).toBe(true);
      expect(result.pluginTarballSha256).toBe(tarballSha256);
      expect(result.packageLockSha256).toBe(generated.packageLockSha256);
    },
  );
});
