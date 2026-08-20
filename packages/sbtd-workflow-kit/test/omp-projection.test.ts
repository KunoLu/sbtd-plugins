import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { stringify as stringifyYaml } from "yaml";
import { KitError, sha256 } from "../src/index.ts";
import {
  checkOmpProjection,
  generateOmpProjection,
  ompProjectionManifestSchema,
} from "../src/omp-projection.ts";

const packageRoot = new URL("..", import.meta.url).pathname;
const temporaryRoots: string[] = [];

const STABLE_MANIFEST_ASSET =
  "onboard/runtime/assets/external-skills/stable/MANIFEST.json";
const STABLE_NOTICES_ASSET =
  "onboard/runtime/assets/external-skills/stable/THIRD_PARTY_NOTICES.md";
const _AGENTS_TARGET_PATHS = [
  "AGENTS.global.md",
  "AGENTS.project-root.md",
  "AGENTS.project-omp.md",
] as const;

const FIXTURE_REVISION = "a".repeat(40);

interface FixtureDecision {
  readonly path: string;
  readonly owner?: "kpi" | "third-party";
  readonly policy: "include" | "omit" | "replace-with-overlay";
  readonly overlay?: string;
  readonly reason?: string;
}

interface FixtureStableManifest {
  readonly repositories?: Record<
    string,
    {
      readonly url: string;
      readonly revision: string;
      readonly license: string;
      readonly licenseFiles: readonly {
        readonly source: string;
        readonly stablePath: string;
      }[];
    }
  >;
  readonly skills?: Record<
    string,
    {
      readonly repository: string;
      readonly sourceSubpath: string;
      readonly stablePath: string;
      readonly treeSha256: string;
    }
  >;
}

async function fixtureRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-omp-projection-"));
  temporaryRoots.push(root);
  return root;
}

async function writeTree(root: string, files: Record<string, string>) {
  await Promise.all(
    Object.entries(files).map(async ([path, content]) => {
      const target = join(root, path);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, content);
    }),
  );
}

/**
 * Synthetic canonical tree + package root. The base assets satisfy every
 * unconditional projection requirement (three AGENTS targets, Profile
 * Catalog, embedded stable manifest); tests add assets/decisions on top.
 */
async function syntheticFixture(options: {
  extraAssets?: Record<string, string>;
  extraDecisions?: readonly FixtureDecision[];
  overrides?: readonly FixtureDecision[];
  overlays?: Record<string, string>;
  stable?: FixtureStableManifest;
  mapText?: string;
}): Promise<{
  root: string;
  kitRoot: string;
  canonicalDirectory: string;
  outputDirectory: string;
}> {
  const root = await fixtureRoot();
  const kitRoot = join(root, "kit");
  const canonicalDirectory = join(root, "canonical");
  const outputDirectory = join(root, "out");

  const stableManifest = {
    schemaVersion: 1,
    stableSet: "2026-08-04.1",
    promotedAt: "2026-08-04T00:00:00.000Z",
    repositories: options.stable?.repositories ?? {},
    skills: options.stable?.skills ?? {},
  };
  const assets: Record<string, string> = {
    "catalog.json": '{"profiles":[]}\n',
    "AGENTS.global.md": "# OMP 全局规则\n",
    "AGENTS.project-root.md": "# Root Project Facts\n",
    "AGENTS.project-omp.md": "# OMP Project Facts\n",
    [STABLE_MANIFEST_ASSET]: `${JSON.stringify(stableManifest, null, 2)}\n`,
    ...options.extraAssets,
  };

  const baseDecisions: FixtureDecision[] = [
    { path: "catalog.json", policy: "include" },
    { path: "AGENTS.global.md", policy: "include" },
    { path: "AGENTS.project-root.md", policy: "include" },
    { path: "AGENTS.project-omp.md", policy: "include" },
    {
      path: STABLE_MANIFEST_ASSET,
      owner: "third-party",
      policy: "omit",
      reason: "OMP projection derives a retained-only stable Skill manifest",
    },
  ];
  const overridden = new Set(
    (options.overrides ?? []).map((decision) => decision.path),
  );
  const decisions = [
    ...baseDecisions.filter((decision) => !overridden.has(decision.path)),
    ...(options.overrides ?? []),
    ...(options.extraDecisions ?? []),
  ];
  const mapText =
    options.mapText ??
    stringifyYaml({
      schemaVersion: 1,
      decisions: decisions.map((decision) => ({
        path: decision.path,
        owner: decision.owner ?? "kpi",
        policy: decision.policy,
        ...(decision.overlay === undefined
          ? {}
          : { overlay: decision.overlay }),
        ...(decision.reason === undefined ? {} : { reason: decision.reason }),
      })),
    });

  await writeTree(kitRoot, {
    "omp-distribution-map.yaml": mapText,
    ...Object.fromEntries(
      Object.entries(options.overlays ?? {}).map(([path, content]) => [
        `omp-overlays/${path}`,
        content,
      ]),
    ),
  });

  const assetDigests = Object.fromEntries(
    Object.entries(assets).map(([path, content]) => [
      path,
      createHash("sha256").update(content).digest("hex"),
    ]),
  );
  const canonicalManifest = {
    schemaVersion: 1,
    sourceId: "sbtd-workflow-kit-upstream",
    canonicalSourceUri: "https://example.invalid/upstream.git",
    resolvedRevision: FIXTURE_REVISION,
    sourceTreeSha256: "b".repeat(64),
    transformVersion: "p0-v3",
    overlayDigests: {},
    generatedSha256: "c".repeat(64),
    targets: {},
    profileCatalogSha256: "d".repeat(64),
    assets: assetDigests,
    stableProvenance: {
      stableSet: "2026-08-04.1",
      manifestSha256: "e".repeat(64),
      repositories: {},
    },
  };
  await writeTree(canonicalDirectory, {
    ...assets,
    "manifest.json": `${JSON.stringify(canonicalManifest, null, 2)}\n`,
  });
  return { root, kitRoot, canonicalDirectory, outputDirectory };
}

async function expectKitError(
  run: () => Promise<unknown>,
  code: string,
): Promise<KitError> {
  try {
    await run();
  } catch (cause) {
    expect(cause).toBeInstanceOf(KitError);
    const error = cause as KitError;
    expect(error.code).toBe(code);
    return error;
  }
  throw new Error(`expected KitError ${code}`);
}

async function scanForForbiddenToken(
  root: string,
): Promise<{ pathMatches: string[]; payloadMatches: string[] }> {
  const pathMatches: string[] = [];
  const payloadMatches: string[] = [];
  const walk = async (directory: string, prefix: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const relative = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (/codex/i.test(relative)) pathMatches.push(relative);
      const full = join(directory, entry.name);
      if (entry.isDirectory()) await walk(full, relative);
      else if (/codex/i.test((await readFile(full)).toString("latin1")))
        payloadMatches.push(relative);
    }
  };
  await walk(root, "");
  return { pathMatches, payloadMatches };
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("OMP Distribution Projection", () => {
  it("Scenario: 相同输入产生相同 projection", async () => {
    const firstRoot = await fixtureRoot();
    const secondRoot = await fixtureRoot();
    const first = await generateOmpProjection({
      packageRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory: join(firstRoot, "generated-omp"),
    });
    const second = await generateOmpProjection({
      packageRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory: join(secondRoot, "generated-omp"),
    });

    expect(second.manifest).toEqual(first.manifest);
    expect(second.report).toEqual(first.report);
    expect(second.manifest.projection.generatedSha256).toBe(
      first.manifest.projection.generatedSha256,
    );

    const firstManifestBytes = await readFile(
      join(firstRoot, "generated-omp", "manifest.json"),
    );
    const secondManifestBytes = await readFile(
      join(secondRoot, "generated-omp", "manifest.json"),
    );
    expect(secondManifestBytes.equals(firstManifestBytes)).toBe(true);
  });

  it("Scenario: canonical Onboard runtime is retained byte-for-byte as a non-executable reference", async () => {
    const root = await fixtureRoot();
    const outputDirectory = join(root, "generated-omp");
    const { manifest, report } = await generateOmpProjection({
      packageRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory,
    });

    const scan = await scanForForbiddenToken(outputDirectory);
    expect(scan.pathMatches).toEqual([]);
    expect(scan.payloadMatches).toEqual(["onboard/runtime/scripts/onboard.py"]);
    expect(report.forbiddenTokenScan).toMatchObject({
      matches: 0,
      canonicalRuntimeMatches: expect.any(Number),
    });
    expect(report.forbiddenTokenScan.canonicalRuntimeMatches).toBeGreaterThan(
      0,
    );
    const [canonicalRuntime, projectedRuntime] = await Promise.all([
      readFile(
        join(packageRoot, "generated", "onboard/runtime/scripts/onboard.py"),
      ),
      readFile(join(outputDirectory, "onboard/runtime/scripts/onboard.py")),
    ]);
    expect(projectedRuntime.equals(canonicalRuntime)).toBe(true);
    expect(manifest.assets["onboard/runtime/SKILL.md"]).toBeUndefined();
    expect(manifest.runtime).toBe("omp");
    expect(manifest.schemaVersion).toBe(2);
  });

  it("Scenario: projection manifest v2 绑定 canonical 与 projection 双层 digest", async () => {
    const root = await fixtureRoot();
    const outputDirectory = join(root, "generated-omp");
    const { manifest } = await generateOmpProjection({
      packageRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory,
    });

    const canonicalManifestBytes = await readFile(
      join(packageRoot, "generated", "manifest.json"),
    );
    expect(manifest.canonical.manifestSha256).toBe(
      sha256(canonicalManifestBytes),
    );
    const canonicalManifest = JSON.parse(canonicalManifestBytes.toString());
    expect(manifest.canonical.resolvedRevision).toBe(
      canonicalManifest.resolvedRevision,
    );
    expect(manifest.canonical.generatedSha256).toBe(
      canonicalManifest.generatedSha256,
    );

    // Every recorded asset digest matches the bytes on disk.
    for (const [path, digest] of Object.entries(manifest.assets)) {
      const content = await readFile(join(outputDirectory, path));
      expect(sha256(content)).toBe(digest);
    }
    // Overlay digests bind the shipped overlay file bytes.
    for (const [path, digest] of Object.entries(manifest.overlayDigests)) {
      const overlay = await readFile(join(packageRoot, "omp-overlays", path));
      expect(sha256(overlay)).toBe(digest);
      const shipped = await readFile(join(outputDirectory, path));
      expect(sha256(shipped)).toBe(digest);
    }
    // The persisted manifest parses as schema v2.
    const persisted = JSON.parse(
      (await readFile(join(outputDirectory, "manifest.json"))).toString(),
    );
    expect(() => ompProjectionManifestSchema.parse(persisted)).not.toThrow();
  });

  it("Scenario: 未分类的新 canonical asset 阻断 projection 且现有输出保持逐字节不变", async () => {
    const { kitRoot, canonicalDirectory, outputDirectory } =
      await syntheticFixture({
        extraAssets: { "onboard/runtime/NEW.md": "new asset\n" },
      });
    await writeTree(outputDirectory, { "keep.txt": "sentinel-bytes\n" });
    const before = await readFile(join(outputDirectory, "keep.txt"));

    const error = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "PROJECTION_ASSET_UNCLASSIFIED",
    );
    expect(error.details).toMatchObject({
      unclassified: ["onboard/runtime/NEW.md"],
    });

    const after = await readFile(join(outputDirectory, "keep.txt"));
    expect(after.equals(before)).toBe(true);
  });

  it("Scenario: 重复、未知或不安全的 projection 决策失败关闭", async () => {
    const duplicate = await syntheticFixture({
      extraDecisions: [{ path: "catalog.json", policy: "include" }],
    });
    const duplicateError = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: duplicate.kitRoot,
          canonicalDirectory: duplicate.canonicalDirectory,
          outputDirectory: duplicate.outputDirectory,
        }),
      "PROJECTION_POLICY_INVALID",
    );
    expect(duplicateError.details).toMatchObject({
      duplicates: ["catalog.json"],
    });

    const stale = await syntheticFixture({
      extraDecisions: [{ path: "gone.md", policy: "include" }],
    });
    const staleError = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: stale.kitRoot,
          canonicalDirectory: stale.canonicalDirectory,
          outputDirectory: stale.outputDirectory,
        }),
      "PROJECTION_POLICY_INVALID",
    );
    expect(staleError.details).toMatchObject({ stale: ["gone.md"] });

    for (const unsafe of ["../escape.md", "absolute\\win.md", "/root.md"]) {
      const fixture = await syntheticFixture({
        mapText: stringifyYaml({
          schemaVersion: 1,
          decisions: [{ path: unsafe, owner: "kpi", policy: "include" }],
        }),
      });
      await expectKitError(
        () =>
          generateOmpProjection({
            packageRoot: fixture.kitRoot,
            canonicalDirectory: fixture.canonicalDirectory,
            outputDirectory: fixture.outputDirectory,
          }),
        "PROJECTION_POLICY_INVALID",
      );
    }

    const mirrored = await syntheticFixture({
      overrides: [
        {
          path: "AGENTS.global.md",
          policy: "replace-with-overlay",
          overlay: "other-name.md",
          reason: "overlay must mirror the canonical path",
        },
      ],
    });
    await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: mirrored.kitRoot,
          canonicalDirectory: mirrored.canonicalDirectory,
          outputDirectory: mirrored.outputDirectory,
        }),
      "PROJECTION_POLICY_INVALID",
    );
  });

  it("Scenario: third-party asset 不能用 KPi overlay 替换", async () => {
    const { kitRoot, canonicalDirectory, outputDirectory } =
      await syntheticFixture({
        extraAssets: { "third-party/vendor/FILE.md": "vendored\n" },
        extraDecisions: [
          {
            path: "third-party/vendor/FILE.md",
            owner: "third-party",
            policy: "replace-with-overlay",
            overlay: "third-party/vendor/FILE.md",
            reason: "attempted third-party replacement",
          },
        ],
      });
    const error = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "PROJECTION_OWNERSHIP_VIOLATION",
    );
    expect(error.details).toMatchObject({
      paths: ["third-party/vendor/FILE.md"],
    });
  });

  it("Scenario: replace 决策引用的 overlay 缺失时失败关闭", async () => {
    const { kitRoot, canonicalDirectory, outputDirectory } =
      await syntheticFixture({
        overrides: [
          {
            path: "AGENTS.global.md",
            policy: "replace-with-overlay",
            overlay: "AGENTS.global.md",
            reason: "overlay intentionally absent from the package root",
          },
        ],
      });
    const error = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "PROJECTION_OVERLAY_MISSING",
    );
    expect(error.details).toMatchObject({ path: "AGENTS.global.md" });
  });

  it("Scenario: canonical 或 overlay symlink 在读取前阻断 projection 且不改变输出", async () => {
    const canonical = await syntheticFixture({});
    await writeTree(canonical.outputDirectory, { "keep.txt": "sentinel\n" });
    const canonicalBefore = await readFile(
      join(canonical.outputDirectory, "keep.txt"),
    );
    const canonicalOutside = join(canonical.root, "canonical-outside.txt");
    await writeFile(canonicalOutside, '{"profiles":[]}\n');
    await rm(join(canonical.canonicalDirectory, "catalog.json"));
    await symlink(
      canonicalOutside,
      join(canonical.canonicalDirectory, "catalog.json"),
    );

    const canonicalFailure = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: canonical.kitRoot,
          canonicalDirectory: canonical.canonicalDirectory,
          outputDirectory: canonical.outputDirectory,
        }),
      "PROJECTION_CANONICAL_INVALID",
    );
    expect(JSON.stringify(canonicalFailure)).toContain("catalog.json");
    expect(JSON.stringify(canonicalFailure)).not.toContain(canonical.root);
    await expect(
      readFile(join(canonical.outputDirectory, "keep.txt")),
    ).resolves.toEqual(canonicalBefore);

    const overlay = await syntheticFixture({
      overrides: [
        {
          path: "AGENTS.global.md",
          policy: "replace-with-overlay",
          overlay: "AGENTS.global.md",
          reason: "use a KPi-owned OMP overlay",
        },
      ],
      overlays: { "AGENTS.global.md": "# OMP overlay\n" },
    });
    await writeTree(overlay.outputDirectory, { "keep.txt": "sentinel\n" });
    const overlayBefore = await readFile(
      join(overlay.outputDirectory, "keep.txt"),
    );
    const overlayOutside = join(overlay.root, "overlay-outside.md");
    await writeFile(overlayOutside, "# OMP overlay\n");
    await rm(join(overlay.kitRoot, "omp-overlays", "AGENTS.global.md"));
    await symlink(
      overlayOutside,
      join(overlay.kitRoot, "omp-overlays", "AGENTS.global.md"),
    );

    const overlayFailure = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: overlay.kitRoot,
          canonicalDirectory: overlay.canonicalDirectory,
          outputDirectory: overlay.outputDirectory,
        }),
      "PROJECTION_OVERLAY_MISSING",
    );
    expect(JSON.stringify(overlayFailure)).toContain("AGENTS.global.md");
    expect(JSON.stringify(overlayFailure)).not.toContain(overlay.root);
    await expect(
      readFile(join(overlay.outputDirectory, "keep.txt")),
    ).resolves.toEqual(overlayBefore);
  });

  it("Scenario: retained path 或 payload 含禁止 token 时失败关闭且不输出内容", async () => {
    const marker = "SeCrEt-CoDeX-payload-marker";
    const { kitRoot, canonicalDirectory, outputDirectory } =
      await syntheticFixture({
        extraAssets: { "docs/note.md": `prefix ${marker} suffix\n` },
        extraDecisions: [{ path: "docs/note.md", policy: "include" }],
      });
    const error = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "PROJECTION_FORBIDDEN_TOKEN",
    );
    expect(error.details).toMatchObject({
      pathViolations: [],
      payloadViolations: ["docs/note.md"],
    });
    // Diagnostics carry relative paths only, never payload content.
    expect(JSON.stringify(error.details)).not.toContain(marker);
    expect(error.message).not.toContain(marker);
  });

  it("Scenario: canonical runtime 豁免只覆盖与 canonical 清单摘要绑定的字节", async () => {
    const canonicalBytes = "# Codex compatibility branch\n";
    const canonicalDigest = createHash("sha256")
      .update(canonicalBytes, "utf8")
      .digest("hex");
    const overlayDecision = {
      path: "onboard/runtime/scripts/onboard.py",
      policy: "replace-with-overlay" as const,
      overlay: "onboard/runtime/scripts/onboard.py",
      reason: "test canonical runtime overlay binding",
    };

    // An overlay whose bytes drift from the canonical manifest binding loses
    // the exemption even though it occupies the canonical path.
    const smuggled = await syntheticFixture({
      extraAssets: { "onboard/runtime/scripts/onboard.py": canonicalBytes },
      extraDecisions: [overlayDecision],
      overlays: {
        "onboard/runtime/scripts/onboard.py": `${canonicalBytes}# extra CoDeX marker\n`,
      },
    });
    const error = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: smuggled.kitRoot,
          canonicalDirectory: smuggled.canonicalDirectory,
          outputDirectory: smuggled.outputDirectory,
        }),
      "PROJECTION_FORBIDDEN_TOKEN",
    );
    expect(error.details).toMatchObject({
      pathViolations: [],
      payloadViolations: ["onboard/runtime/scripts/onboard.py"],
    });

    // The exact canonical bytes remain admissible under the same path.
    const bound = await syntheticFixture({
      extraAssets: { "onboard/runtime/scripts/onboard.py": canonicalBytes },
      extraDecisions: [overlayDecision],
      overlays: { "onboard/runtime/scripts/onboard.py": canonicalBytes },
    });
    const { manifest } = await generateOmpProjection({
      packageRoot: bound.kitRoot,
      canonicalDirectory: bound.canonicalDirectory,
      outputDirectory: bound.outputDirectory,
    });
    expect(manifest.overlayDigests["onboard/runtime/scripts/onboard.py"]).toBe(
      canonicalDigest,
    );
    const projected = await readFile(
      join(bound.outputDirectory, "onboard/runtime/scripts/onboard.py"),
    );
    expect(projected.equals(Buffer.from(canonicalBytes, "utf8"))).toBe(true);
  });

  it("Scenario: derived retained provenance 只包含保留的 stable 仓库与 Skill", async () => {
    const root = await fixtureRoot();
    const outputDirectory = join(root, "generated-omp");
    const { manifest } = await generateOmpProjection({
      packageRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory,
    });

    const retainedRepositories = Object.keys(
      manifest.retainedProvenance.repositories,
    ).sort();
    expect(retainedRepositories).toEqual(
      ["mattpocock-skills", "ui-ux-pro-max-skill"].sort(),
    );
    expect(
      Object.keys(manifest.retainedProvenance.skills).sort(),
    ).not.toContain("impeccable");
    expect(
      Object.keys(manifest.retainedProvenance.skills).sort(),
    ).not.toContain("shadcn");

    const retainedStableManifestBytes = await readFile(
      join(outputDirectory, STABLE_MANIFEST_ASSET),
    );
    expect(sha256(retainedStableManifestBytes)).toBe(
      manifest.retainedProvenance.manifestSha256,
    );
    const retainedStableManifest = JSON.parse(
      retainedStableManifestBytes.toString(),
    );
    expect(Object.keys(retainedStableManifest.repositories).sort()).toEqual(
      retainedRepositories,
    );

    const stableNotices = (
      await readFile(join(outputDirectory, STABLE_NOTICES_ASSET))
    ).toString();
    expect(stableNotices).toContain("mattpocock/skills");
    expect(stableNotices).toContain("ui-ux-pro-max");
    expect(stableNotices).not.toContain("impeccable");
    expect(stableNotices).not.toContain("shadcn");

    const topLevelNotices = (
      await readFile(join(outputDirectory, "THIRD_PARTY_NOTICES.md"))
    ).toString();
    expect(topLevelNotices).toContain("# Third-Party Notices");
    expect(topLevelNotices).toContain("SBTD Workflow Onboard");
    expect(topLevelNotices).not.toContain("impeccable");
  });

  it("Scenario: stable Skill 部分保留或孤儿 license 阻断 projection", async () => {
    const stable: FixtureStableManifest = {
      repositories: {
        "example/repo": {
          url: "https://example.invalid/repo.git",
          revision: FIXTURE_REVISION,
          license: "MIT",
          licenseFiles: [
            { source: "LICENSE", stablePath: "licenses/example-LICENSE" },
          ],
        },
      },
      skills: {
        demo: {
          repository: "example/repo",
          sourceSubpath: "skills/demo",
          stablePath: "skills/demo",
          treeSha256: "f".repeat(64),
        },
      },
    };
    const skillAssets = {
      "onboard/runtime/assets/external-skills/stable/skills/demo/a.md": "a\n",
      "onboard/runtime/assets/external-skills/stable/skills/demo/b.md": "b\n",
      "onboard/runtime/assets/external-skills/stable/licenses/example-LICENSE":
        "license\n",
    };
    const partial = await syntheticFixture({
      extraAssets: skillAssets,
      extraDecisions: [
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/demo/a.md",
          owner: "third-party",
          policy: "include",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/demo/b.md",
          owner: "third-party",
          policy: "omit",
          reason: "partial tree retention attempt",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/licenses/example-LICENSE",
          owner: "third-party",
          policy: "include",
        },
      ],
      stable,
    });
    await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: partial.kitRoot,
          canonicalDirectory: partial.canonicalDirectory,
          outputDirectory: partial.outputDirectory,
        }),
      "PROJECTION_LEGAL_INVENTORY",
    );

    const orphanLicense = await syntheticFixture({
      extraAssets: skillAssets,
      extraDecisions: [
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/demo/a.md",
          owner: "third-party",
          policy: "omit",
          reason: "skill not retained",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/skills/demo/b.md",
          owner: "third-party",
          policy: "omit",
          reason: "skill not retained",
        },
        {
          path: "onboard/runtime/assets/external-skills/stable/licenses/example-LICENSE",
          owner: "third-party",
          policy: "include",
        },
      ],
      stable,
    });
    await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: orphanLicense.kitRoot,
          canonicalDirectory: orphanLicense.canonicalDirectory,
          outputDirectory: orphanLicense.outputDirectory,
        }),
      "PROJECTION_LEGAL_INVENTORY",
    );
  });

  it("Scenario: canonical 派生输出路径必须省略", async () => {
    const { kitRoot, canonicalDirectory, outputDirectory } =
      await syntheticFixture({
        extraAssets: { "THIRD_PARTY_NOTICES.md": "canonical notices\n" },
        extraDecisions: [{ path: "THIRD_PARTY_NOTICES.md", policy: "include" }],
      });
    const error = await expectKitError(
      () =>
        generateOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "PROJECTION_DERIVED_CONFLICT",
    );
    expect(error.details).toMatchObject({
      conflicts: ["THIRD_PARTY_NOTICES.md"],
    });
  });

  it("Scenario: 篡改 projection 输出、canonical 或 overlay 时校验失败关闭", async () => {
    const { kitRoot, canonicalDirectory, outputDirectory } =
      await syntheticFixture({});
    await generateOmpProjection({
      packageRoot: kitRoot,
      canonicalDirectory,
      outputDirectory,
    });
    await checkOmpProjection({
      packageRoot: kitRoot,
      canonicalDirectory,
      outputDirectory,
    });

    // Tamper with a shipped asset byte.
    await writeFile(
      join(outputDirectory, "catalog.json"),
      '{"profiles":[1]}\n',
    );
    const outputDrift = await expectKitError(
      () =>
        checkOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "GENERATED_DRIFT",
    );
    expect(outputDrift.details).toMatchObject({ target: "catalog.json" });
    await writeFile(join(outputDirectory, "catalog.json"), '{"profiles":[]}\n');

    // Tamper with the canonical manifest after generation.
    const canonicalManifestPath = join(canonicalDirectory, "manifest.json");
    const canonicalBefore = await readFile(canonicalManifestPath);
    await writeFile(canonicalManifestPath, `${canonicalBefore.toString()} `);
    await expectKitError(
      () =>
        checkOmpProjection({
          packageRoot: kitRoot,
          canonicalDirectory,
          outputDirectory,
        }),
      "GENERATED_DRIFT",
    );
    await writeFile(canonicalManifestPath, canonicalBefore);
  });

  it("Scenario: OMP catalog overlay 不列出未保留的 agent 模板与 external skill", async () => {
    const root = await fixtureRoot();
    const outputDirectory = join(root, "generated-omp");
    await generateOmpProjection({
      packageRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory,
    });
    const catalog = JSON.parse(
      (
        await readFile(join(outputDirectory, "onboard/runtime/catalog.json"))
      ).toString(),
    );
    const ids = catalog.entries.map((entry: { id: string }) => entry.id);
    expect(ids).not.toContain("agent:codex-global");
    expect(ids).not.toContain("agent:project");
    expect(ids).not.toContain("skill:impeccable");
    expect(ids).not.toContain("skill:shadcn");
    expect(ids).toContain("skill:trellis-workflow");
    expect(ids).toContain("skill:ui-ux-pro-max");

    const schema = JSON.parse(
      (
        await readFile(
          join(outputDirectory, "onboard/runtime/catalog.schema.json"),
        )
      ).toString(),
    );
    expect(JSON.stringify(schema)).not.toContain("codex");
  });
});
