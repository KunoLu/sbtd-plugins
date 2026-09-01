import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  AGENT_PLUGINS_SCHEMA_URL,
  validatePluginManifest,
} from "../scripts/plugin-manifest.mjs";

const pluginRoot = fileURLToPath(new URL("..", import.meta.url));

function validManifest(): Record<string, unknown> {
  return {
    $schema: AGENT_PLUGINS_SCHEMA_URL,
    name: "omp-sbtd",
    version: "0.1.0-rc.14",
    description:
      "SBTD workflow capabilities for coding agents, with an OMP runtime control plane.",
    license: "Apache-2.0",
    keywords: ["oh-my-pi", "omp", "sbtd"],
    homepage: "https://github.com/KunoLu/sbtd-plugins",
    repository: {
      type: "git",
      url: "https://github.com/KunoLu/sbtd-plugins.git",
      directory: "packages/omp-sbtd",
    },
  };
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
  it("Scenario: 根 manifest 通过 schema 1.0.0 校验且版本与 package.json 一致", async () => {
    const [manifest, packageManifest] = await Promise.all([
      readFile(`${pluginRoot}/plugin.json`, "utf8").then(
        (text) => JSON.parse(text) as unknown,
      ),
      readFile(`${pluginRoot}/package.json`, "utf8").then(
        (text) => JSON.parse(text) as unknown,
      ),
    ]);
    const packageVersion = (packageManifest as { version: unknown }).version;
    expect(packageVersion).toBe("0.1.0-rc.14");
    // Candidate identity: the widened tarball-bound peer range with the exact
    // development pin retained (Slice 3 contract; rc.12 stays exact-peer).
    expect(dependencySpec(packageManifest, "peerDependencies")).toBe(
      ">=17.3.5 <18",
    );
    expect(dependencySpec(packageManifest, "devDependencies")).toBe("17.3.5");
    expect(() =>
      validatePluginManifest(manifest, {
        expectedVersion: packageVersion as string,
      }),
    ).not.toThrow();
    expect((manifest as { version: unknown }).version).toBe("0.1.0-rc.14");
  });

  const invalidShapes: ReadonlyArray<{
    readonly shape: string;
    readonly mutate: (manifest: Record<string, unknown>) => void;
    readonly reason: RegExp;
  }> = [
    {
      shape: '"$schema" 指向其他版本',
      mutate: (manifest) => {
        manifest.$schema =
          "https://agent-plugins.org/schemas/0.9.0/plugin.schema.json";
      },
      reason: /1\.0\.0/,
    },
    {
      shape: "含非标准顶层字段",
      mutate: (manifest) => {
        manifest.extensions = { omp: { minimumOmpVersion: "17.3.5" } };
      },
      reason: /non-standard|standard/,
    },
    {
      shape: "缺少必填标准字段",
      mutate: (manifest) => {
        Reflect.deleteProperty(manifest, "description");
      },
      reason: /missing/i,
    },
    {
      shape: '"name" 不是 "omp-sbtd"',
      mutate: (manifest) => {
        manifest.name = "sbtd";
      },
      reason: /name/,
    },
    {
      shape: '"version" 与 package.json 漂移',
      mutate: (manifest) => {
        manifest.version = "0.1.0-rc.11";
      },
      reason: /version/i,
    },
    {
      shape: "description 不是字符串",
      mutate: (manifest) => {
        manifest.description = 42;
      },
      reason: /description/,
    },
    {
      shape: "keywords 不是字符串数组",
      mutate: (manifest) => {
        manifest.keywords = ["omp", 7];
      },
      reason: /keywords/,
    },
  ];

  for (const { shape, mutate, reason } of invalidShapes) {
    it(`Scenario: 非法 manifest 形状被校验拒绝 — ${shape}`, () => {
      const manifest = validManifest();
      mutate(manifest);
      expect(() =>
        validatePluginManifest(manifest, { expectedVersion: "0.1.0-rc.14" }),
      ).toThrow(reason);
    });
  }

  it("Scenario: 非对象 manifest 被校验拒绝", () => {
    for (const manifest of [null, [], "omp-sbtd", 12]) {
      expect(() => validatePluginManifest(manifest)).toThrow(/object/i);
    }
  });

  it("Scenario: repository 形状非法被校验拒绝", () => {
    const manifest = validManifest();
    manifest.repository = { type: "svn", url: "https://example.invalid" };
    expect(() => validatePluginManifest(manifest)).toThrow(/repository/);
  });
});
