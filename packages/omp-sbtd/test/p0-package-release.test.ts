import { execFile as executeFile } from "node:child_process";
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
import { dirname, isAbsolute, join, resolve } from "node:path";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";
import {
  assertOmpDistributionClean,
  countCaseInsensitiveTokenOccurrences,
  inspectPackageMetadata,
  inventoryFiles,
  scanOmpDistributionLeaks,
  verifyEmbeddedKitReleaseIntegrity,
  verifyPackedPackageContents,
  verifyPackedPackageMetadata,
} from "../scripts/p0/release-validator.ts";

const workspaceRoot = new URL("../../..", import.meta.url).pathname;
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const persistentEvidenceRoot = join(pluginRoot, "validation/p0/evidence");
const kitRoot = join(workspaceRoot, "packages/sbtd-workflow-kit");
const p0CliPath = join(pluginRoot, "scripts/p0/cli.ts");
const tsxCliPath = join(pluginRoot, "node_modules/tsx/dist/cli.mjs");

const mutableProjectionManifestSchema = z
  .object({
    schemaVersion: z.number(),
    assets: z.record(z.string(), z.string()),
    retainedProvenance: z.object({ manifestSha256: z.string() }).passthrough(),
    targets: z.record(z.string(), z.string()),
    profileCatalogSha256: z.string(),
  })
  .passthrough();

const temporaryRoots: string[] = [];

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-p0-package-"));
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

const runProcess = promisify(executeFile);
const packageManager = process.platform === "win32" ? "pnpm.cmd" : "pnpm";

async function candidateEvidenceDirectories(
  evidenceRoot = persistentEvidenceRoot,
): Promise<readonly string[]> {
  try {
    return (await readdir(join(evidenceRoot, "candidates"))).sort();
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "code" in error &&
      error.code === "ENOENT"
    )
      return [];
    throw error;
  }
}

async function unpackPluginTarball(
  root: string,
): Promise<Readonly<{ packageRoot: string; tarball: string }>> {
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
  return { packageRoot: join(extractedRoot, "package"), tarball };
}

async function rearchivePackage(
  root: string,
  packageRoot: string,
): Promise<string> {
  const tarball = join(root, "candidate.tgz");
  await runProcess("tar", [
    "-czf",
    tarball,
    "-C",
    dirname(packageRoot),
    "package",
  ]);
  return tarball;
}

async function candidateTemporaryRoot(): Promise<string> {
  const parent = join(workspaceRoot, ".tmp/kpi-p0");
  await mkdir(parent, { recursive: true });
  const root = await mkdtemp(join(parent, "candidate-cli-"));
  temporaryRoots.push(root);
  return root;
}

async function runP0Cli(arguments_: readonly string[], evidenceRoot: string) {
  try {
    const { stdout, stderr } = await runProcess(
      process.execPath,
      [tsxCliPath, p0CliPath, ...arguments_],
      {
        cwd: pluginRoot,
        env: { ...process.env, KPI_P0_EVIDENCE_ROOT: evidenceRoot },
      },
    );
    return { exitCode: 0, stdout, stderr };
  } catch (error) {
    const result = error as Readonly<{
      stdout?: string;
      stderr?: string;
    }>;
    return {
      exitCode: 1,
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
    };
  }
}

describe("Feature: P0 发布一致性与证据", () => {
  it("Scenario: SBOM 或许可证通知漂移时包检查失败关闭", async () => {
    const metadata = await inspectPackageMetadata({
      workspaceRoot,
      pluginRoot,
      kitRoot,
    });
    const rootLicense = await readFile(join(workspaceRoot, "LICENSE"), "utf8");
    const [pluginLicense, kitLicense, pluginNotices, kitNotices, sbomText] =
      await Promise.all([
        readFile(join(pluginRoot, "LICENSE"), "utf8"),
        readFile(join(kitRoot, "LICENSE"), "utf8"),
        readFile(join(pluginRoot, "THIRD_PARTY_NOTICES.md"), "utf8"),
        readFile(join(kitRoot, "THIRD_PARTY_NOTICES.md"), "utf8"),
        readFile(join(pluginRoot, "SBOM.spdx.json"), "utf8"),
      ]);
    const sbom = JSON.parse(sbomText) as {
      spdxVersion: string;
      packages: Array<{ licenseDeclared: string }>;
      files: Array<{ fileName: string; licenseConcluded: string }>;
    };

    expect(metadata.plugin.license).toBe("Apache-2.0");
    expect(metadata.kit.license).toBe("Apache-2.0");
    expect(metadata.plugin.name).toBe("@kunolu/omp-sbtd");
    expect(metadata.kit.name).toBe("@kunolu/sbtd-workflow-kit");
    expect(metadata.plugin.files).toEqual(
      expect.arrayContaining([
        "plugin.json",
        "skills",
        "validation/p0/compatibility.v2.json",
      ]),
    );
    expect(pluginLicense).toBe(rootLicense);
    expect(kitLicense).toBe(rootLicense);
    expect(pluginNotices).toContain("kit/onboard/runtime/LICENSE");
    expect(pluginNotices).toContain("kit/onboard/runtime/NOTICE");
    expect(pluginNotices).not.toContain("\n- Retained license: third-party/");
    expect(pluginNotices).not.toContain("\n- Retained notice: third-party/");
    expect(pluginNotices).not.toMatch(/codex/i);
    expect(kitNotices).toContain("third-party/sbtd-workflow-onboard/LICENSE");
    expect(kitNotices).toContain("third-party/sbtd-workflow-onboard/NOTICE");
    expect(sbom.spdxVersion).toBe("SPDX-2.3");
    expect(
      sbom.packages.every((item) => item.licenseDeclared === "Apache-2.0"),
    ).toBe(true);
    for (const fileName of [
      "./kit/onboard/runtime/LICENSE",
      "./kit/onboard/runtime/NOTICE",
    ]) {
      expect(sbom.files).toContainEqual(
        expect.objectContaining({
          fileName,
          licenseConcluded: "Apache-2.0",
        }),
      );
    }
    const portableSkillFiles = sbom.files.filter((file) =>
      file.fileName.startsWith("./skills/"),
    );
    expect(portableSkillFiles.length).toBeGreaterThan(0);
    expect(
      portableSkillFiles.every(
        (file) => file.licenseConcluded === "Apache-2.0",
      ),
    ).toBe(true);
  });

  it("Scenario: 打包库存保留 Kit 运行时需要的隐藏文件", async () => {
    const root = await temporaryRoot();
    const ignored = "*\n";
    const binary = new Uint8Array([0, 255, 128, 65]);
    const hiddenAssetDigest = createHash("sha256")
      .update(ignored)
      .digest("hex");
    const rawAssetDigest = createHash("sha256").update(binary).digest("hex");
    await Promise.all([
      writeFile(join(root, ".gitignore"), ignored, "utf8"),
      writeFile(join(root, "asset.bin"), binary),
    ]);

    expect(await inventoryFiles(root)).toEqual([
      { path: ".gitignore", sha256: hiddenAssetDigest },
      { path: "asset.bin", sha256: rawAssetDigest },
    ]);
    const sbom = JSON.parse(
      await readFile(join(pluginRoot, "SBOM.spdx.json"), "utf8"),
    ) as {
      files: Array<{
        fileName: string;
        checksums: Array<{ algorithm: string; checksumValue: string }>;
      }>;
    };
    const names = sbom.files.map((file) => file.fileName.slice(2));
    const retainedData = sbom.files.find(
      (file) =>
        file.fileName ===
        "./kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/products.csv",
    );

    expect(names).toContain(
      "kit/onboard/runtime/templates/project/gitignore.template",
    );
    expect(names).toContain(
      "kit/onboard/runtime/templates/skills/web-ui-autotest-generator/gitignore.template",
    );
    expect(retainedData).toBeDefined();
    expect(
      retainedData?.checksums.find(
        (checksum) => checksum.algorithm === "SHA256",
      )?.checksumValue,
    ).toBe(
      createHash("sha256")
        .update(
          await readFile(
            join(
              pluginRoot,
              "kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/products.csv",
            ),
          ),
        )
        .digest("hex"),
    );
  });

  it("Scenario: 已打包的 Projection 保留项目与 retained Skill 的忽略规则", async () => {
    const root = await temporaryRoot();
    const { packageRoot: packedRoot } = await unpackPluginTarball(root);
    const [vendorProjectIgnore, overlayProjectIgnore, webUiIgnore] =
      await Promise.all([
        readFile(
          join(
            kitRoot,
            "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/templates/project/.gitignore",
          ),
          "utf8",
        ),
        readFile(
          join(
            kitRoot,
            "omp-overlays/onboard/runtime/templates/project/gitignore.template",
          ),
          "utf8",
        ),
        readFile(
          join(
            kitRoot,
            "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/templates/skills/web-ui-autotest-generator/.gitignore",
          ),
          "utf8",
        ),
      ]);

    const packedProjectIgnore = await readFile(
      join(
        packedRoot,
        "kit/onboard/runtime/templates/project/gitignore.template",
      ),
      "utf8",
    );
    expect(packedProjectIgnore).toBe(overlayProjectIgnore);
    expect(packedProjectIgnore).not.toBe(vendorProjectIgnore);
    expect(packedProjectIgnore).toContain(".omp/plugins/");
    expect(packedProjectIgnore).not.toMatch(/codex/i);
    await expect(
      readFile(
        join(
          packedRoot,
          "kit/onboard/runtime/templates/skills/web-ui-autotest-generator/gitignore.template",
        ),
        "utf8",
      ),
    ).resolves.toBe(webUiIgnore);
    await expect(
      readFile(
        join(packedRoot, "kit/onboard/runtime/templates/project/.gitignore"),
        "utf8",
      ),
    ).rejects.toMatchObject({ code: "ENOENT" });
    await expect(
      readFile(
        join(
          packedRoot,
          "kit/onboard/runtime/templates/skills/web-ui-autotest-generator/.gitignore",
        ),
        "utf8",
      ),
    ).rejects.toMatchObject({ code: "ENOENT" });
  }, 120_000);
  it("Scenario: 实际 tarball 提供 RC6 产品 metadata 与支持文档", async () => {
    const root = await temporaryRoot();
    const { packageRoot } = await unpackPluginTarball(root);
    const [manifestText, readme, security, changelog] = await Promise.all([
      readFile(join(packageRoot, "package.json"), "utf8"),
      readFile(join(packageRoot, "README.md"), "utf8"),
      readFile(join(packageRoot, "SECURITY.md"), "utf8"),
      readFile(join(packageRoot, "CHANGELOG.md"), "utf8"),
    ]);
    const manifest = JSON.parse(manifestText) as {
      repository?: { url?: string };
      bugs?: string;
      homepage?: string;
    };
    expect(manifest.repository?.url).toBe("https://github.com/KunoLu/sbtd-plugins.git");
    expect(manifest.bugs).toBe("https://github.com/KunoLu/sbtd-plugins/issues");
    expect(manifest.homepage).toBe("https://github.com/KunoLu/sbtd-plugins");
    expect(security).toContain("songlin.lu@neox-inc.com");
    expect(security).toMatch(/do not open public GitHub issues/i);
    expect(changelog).toContain("P3-01");
    expect(readme).toMatch(/no telemetry/i);
    expect(readme).toMatch(/npm uninstall -g @kunolu\/omp-sbtd/);
  }, 120_000);
  it("Scenario: 发布候选的路径和内容满足严格零 Codex", async () => {
    const root = await temporaryRoot();
    const { packageRoot: packedRoot } = await unpackPluginTarball(root);
    const leaks = await scanOmpDistributionLeaks(packedRoot);
    expect(leaks).toEqual([]);
    expect(() => assertOmpDistributionClean(leaks)).not.toThrow();
  }, 120_000);

  it("Scenario: manifest v2 绑定漂移使实际发布候选失败关闭", async () => {
    const root = await temporaryRoot();
    const { packageRoot: packedRoot } = await unpackPluginTarball(root);
    const manifestPath = join(packedRoot, "kit", "manifest.json");
    const original = await readFile(manifestPath, "utf8");
    const mutations: readonly [
      string,
      (manifest: z.infer<typeof mutableProjectionManifestSchema>) => void,
    ][] = [
      [
        "schema v1",
        (manifest) => {
          manifest.schemaVersion = 1;
        },
      ],
      [
        "asset digest",
        (manifest) => {
          manifest.assets["catalog.json"] = "0".repeat(64);
        },
      ],
      [
        "retained provenance",
        (manifest) => {
          manifest.retainedProvenance.manifestSha256 = "0".repeat(64);
        },
      ],
      [
        "managed target",
        (manifest) => {
          manifest.targets["AGENTS.global.md"] = "0".repeat(64);
        },
      ],
      [
        "Profile Catalog",
        (manifest) => {
          manifest.profileCatalogSha256 = "0".repeat(64);
        },
      ],
      [
        "canonical runtime binding",
        (manifest) => {
          // Omit the mandatory canonical runtime digest while keeping every
          // other manifest binding internally consistent. The mutable schema
          // only re-parses known fields, so the passthrough projection and
          // overlay digest shapes are asserted once here from the packed
          // manifest contract.
          delete manifest.assets["onboard/runtime/scripts/onboard.py"];
          const projection = manifest.projection as {
            generatedSha256: string;
          };
          const overlayDigests = manifest.overlayDigests as Record<
            string,
            string
          >;
          projection.generatedSha256 = createHash("sha256")
            .update(
              [
                ...Object.entries(manifest.assets)
                  .sort(([left], [right]) => left.localeCompare(right))
                  .map(([path, assetDigest]) => `${path}\0${assetDigest}`),
                ...Object.entries(overlayDigests)
                  .sort(([left], [right]) => left.localeCompare(right))
                  .map(
                    ([path, overlayDigest]) =>
                      `overlay:${path}\0${overlayDigest}`,
                  ),
              ].join("\n"),
            )
            .digest("hex");
        },
      ],
    ];

    for (const [binding, mutate] of mutations) {
      const manifest = mutableProjectionManifestSchema.parse(
        JSON.parse(original),
      );
      mutate(manifest);
      await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
      let failure: unknown;
      try {
        await verifyEmbeddedKitReleaseIntegrity({
          kitRoot: join(packedRoot, "kit"),
        });
      } catch (error) {
        failure = error;
      }
      expect(failure, binding).toMatchObject({
        name: "P0ValidationError",
        code: "PACKAGE_CONTENT_INVALID",
      });
      expect(JSON.stringify(failure)).not.toContain(packedRoot);
      await writeFile(manifestPath, original);
    }
  }, 120_000);

  it("Scenario: 仅摘要绑定的 canonical Onboard runtime 可保留 Codex 兼容分支", async () => {
    const root = await temporaryRoot();
    const packedRoot = join(root, "package");
    const canonicalRuntime = join(
      packedRoot,
      "kit",
      "onboard",
      "runtime",
      "scripts",
    );
    await mkdir(canonicalRuntime, { recursive: true });
    await mkdir(join(packedRoot, "kit", "docs"), { recursive: true });
    const runtimePayload = "# Codex compatibility\n";
    const runtimeDigest = createHash("sha256")
      .update(runtimePayload, "utf8")
      .digest("hex");
    await Promise.all([
      writeFile(join(canonicalRuntime, "onboard.py"), runtimePayload),
      writeFile(
        join(packedRoot, "kit", "docs", "copy.py"),
        "# Codex compatibility\n",
      ),
      writeFile(
        join(packedRoot, "kit", "manifest.json"),
        `${JSON.stringify(
          {
            assets: {
              "onboard/runtime/scripts/onboard.py": runtimeDigest,
            },
          },
          null,
          2,
        )}\n`,
      ),
    ]);

    await expect(scanOmpDistributionLeaks(packedRoot)).resolves.toEqual([
      {
        path: "kit/docs/copy.py",
        pathMatches: 0,
        payloadMatches: 1,
      },
    ]);
  });

  it("Scenario: 未绑定或摘要漂移的 canonical runtime 载荷按普通泄漏失败关闭", async () => {
    const marker = "# CoDeX compatibility\n";
    const buildPackedRoot = async (
      manifest: string | undefined,
    ): Promise<string> => {
      const root = await temporaryRoot();
      const packedRoot = join(root, "package");
      const canonicalRuntime = join(
        packedRoot,
        "kit",
        "onboard",
        "runtime",
        "scripts",
      );
      await mkdir(canonicalRuntime, { recursive: true });
      await writeFile(join(canonicalRuntime, "onboard.py"), marker);
      if (manifest !== undefined)
        await writeFile(join(packedRoot, "kit", "manifest.json"), manifest);
      return packedRoot;
    };
    const expectedLeak = [
      {
        path: "kit/onboard/runtime/scripts/onboard.py",
        pathMatches: 0,
        payloadMatches: 1,
      },
    ];

    // No embedded manifest means no approved digest, so the canonical path
    // payload is scanned like any other file.
    await expect(
      scanOmpDistributionLeaks(await buildPackedRoot(undefined)),
    ).resolves.toEqual(expectedLeak);

    // A manifest binding a different digest does not exempt the payload.
    const drifted = `${JSON.stringify(
      {
        assets: {
          "onboard/runtime/scripts/onboard.py": "0".repeat(64),
        },
      },
      null,
      2,
    )}\n`;
    await expect(
      scanOmpDistributionLeaks(await buildPackedRoot(drifted)),
    ).resolves.toEqual(expectedLeak);
  });

  it("Scenario: 非 OMP 内容使发布候选失败关闭", async () => {
    const root = await temporaryRoot();
    const packedRoot = join(root, "package");
    await mkdir(join(packedRoot, "kit", "docs"), { recursive: true });
    const secretSentence = "See the CoDeX runtime migration guide.";
    await writeFile(
      join(packedRoot, "kit", "docs", "codex-notes.md"),
      "clean payload\n",
    );
    await writeFile(
      join(packedRoot, "kit", "docs", "README.md"),
      `${secretSentence}\nCODEX again\n`,
    );

    const leaks = await scanOmpDistributionLeaks(packedRoot);
    expect(leaks).toEqual([
      {
        path: "kit/docs/codex-notes.md",
        pathMatches: 1,
        payloadMatches: 0,
      },
      {
        path: "kit/docs/README.md",
        pathMatches: 0,
        payloadMatches: 2,
      },
    ]);

    const failure = await scanOmpDistributionLeaks(packedRoot).then((found) => {
      try {
        assertOmpDistributionClean(found);
      } catch (error) {
        return error;
      }
      return undefined;
    });
    expect(failure).toMatchObject({
      name: "P0ValidationError",
      code: "OMP_DISTRIBUTION_LEAKAGE",
    });
    const serialized = JSON.stringify(failure);
    expect(serialized).toContain("kit/docs/codex-notes.md");
    expect(serialized).not.toContain(secretSentence);
    expect(serialized).not.toContain(root);

    expect(
      countCaseInsensitiveTokenOccurrences(
        new TextEncoder().encode("xCodex codex CODEXx"),
      ),
    ).toBe(3);
    expect(
      countCaseInsensitiveTokenOccurrences(new TextEncoder().encode("clean")),
    ).toBe(0);
  });

  it("Scenario: 根文件名为 skills 时载荷仍扫描", async () => {
    const root = await temporaryRoot();
    const packedRoot = join(root, "package");
    await mkdir(packedRoot, { recursive: true });
    await writeFile(
      join(packedRoot, "skills"),
      "See the Codex runtime notes.\n",
    );

    await expect(scanOmpDistributionLeaks(packedRoot)).resolves.toEqual([
      {
        path: "skills",
        pathMatches: 0,
        payloadMatches: 1,
      },
    ]);
  });

  it("Scenario: 实际 tarball 必须包含匹配的 SBOM 且拒绝额外载荷", () => {
    const sha256 = "a".repeat(64);
    const sbomSha256 = "b".repeat(64);
    const expected = [
      { path: "README.md", sha256 },
      { path: "dist/index.js", sha256 },
    ];
    const packed = [
      { path: "package/README.md", sha256, executable: false },
      { path: "package/dist/index.js", sha256, executable: false },
      { path: "package/package.json", sha256, executable: false },
      {
        path: "package/SBOM.spdx.json",
        sha256: sbomSha256,
        executable: false,
      },
    ];

    expect(() =>
      verifyPackedPackageContents(expected, packed, sbomSha256),
    ).not.toThrow();
    expect(() =>
      verifyPackedPackageContents(
        expected,
        packed.filter((file) => file.path !== "package/SBOM.spdx.json"),
        sbomSha256,
      ),
    ).toThrow("Packed Plugin contents differ");
    expect(() =>
      verifyPackedPackageContents(
        expected,
        [...packed, { path: "package/extra.txt", sha256, executable: false }],
        sbomSha256,
      ),
    ).toThrow("Packed Plugin contents differ");
    const sourceManifest = {
      name: "@kunolu/omp-sbtd",
      version: "0.1.0-rc.10",
      license: "Apache-2.0",
      type: "module",
      main: "./dist/extension.js",
      types: "./dist/extension.d.ts",
      files: [
        "dist",
        "kit",
        "LICENSE",
        "SBOM.spdx.json",
        "THIRD_PARTY_NOTICES.md",
      ],
      dependencies: { zod: "4.1.12" },
      peerDependencies: { "@oh-my-pi/pi-coding-agent": "17.3.5" },
      devDependencies: { "@kunolu/sbtd-workflow-kit": "workspace:*" },
      omp: { extensions: ["./dist/extension.js"] },
      pi: { extensions: ["./dist/extension.js"] },
    };
    const workspacePackageManifests = {
      "@kunolu/sbtd-workflow-kit": {
        name: "@kunolu/sbtd-workflow-kit",
        version: "0.1.0",
      },
    };
    expect(() =>
      verifyPackedPackageMetadata(
        sourceManifest,
        {
          ...sourceManifest,
          devDependencies: { "@kunolu/sbtd-workflow-kit": "0.1.0" },
        },
        workspacePackageManifests,
      ),
    ).not.toThrow();
    expect(() =>
      verifyPackedPackageMetadata(
        sourceManifest,
        {
          ...sourceManifest,
          devDependencies: { "@kunolu/sbtd-workflow-kit": "2.0.0" },
        },
        {
          "@kunolu/sbtd-workflow-kit": {
            name: "@kunolu/sbtd-workflow-kit",
            version: "2.0.0",
          },
        },
      ),
    ).not.toThrow();
    expect(() =>
      verifyPackedPackageMetadata(
        sourceManifest,
        {
          ...sourceManifest,
          devDependencies: { "@kunolu/sbtd-workflow-kit": "0.1.0" },
        },
        {
          "@kunolu/sbtd-workflow-kit": {
            name: "@kunolu/sbtd-workflow-kit",
            version: "2.0.0",
          },
        },
      ),
    ).toThrow("Packed Plugin metadata differs");
    expect(() =>
      verifyPackedPackageMetadata(
        sourceManifest,
        {
          ...sourceManifest,
          version: "0.1.1",
        },
        workspacePackageManifests,
      ),
    ).toThrow("Packed Plugin metadata differs");
    expect(() =>
      verifyPackedPackageMetadata(
        sourceManifest,
        {
          ...sourceManifest,
          scripts: { postinstall: "node injected.js" },
        },
        workspacePackageManifests,
      ),
    ).toThrow("Packed Plugin metadata differs");
  });
  it("Scenario: RC 候选拒绝不一致或含链接成员的 tarball", async () => {
    const root = await candidateTemporaryRoot();
    const evidenceRoot = join(root, "candidate-evidence");
    const persistentBefore = await candidateEvidenceDirectories();
    const beforeRejectedRecords =
      await candidateEvidenceDirectories(evidenceRoot);
    const { packageRoot, tarball } = await unpackPluginTarball(root);
    const alternateRoot = join(root, "alternate");
    const mismatchedTarball = join(root, "mismatched.tgz");
    await mkdir(alternateRoot, { recursive: true });
    await runProcess("tar", ["-xzf", tarball, "-C", alternateRoot]);
    await writeFile(
      join(alternateRoot, "package", "unexpected.txt"),
      "mismatch",
    );
    await runProcess("tar", [
      "-czf",
      mismatchedTarball,
      "-C",
      alternateRoot,
      "package",
    ]);

    const result = await runP0Cli(
      [
        "record-candidate",
        "--packed",
        packageRoot,
        "--tarball",
        mismatchedTarball,
        "--dist-tag",
        "next",
        "--created-at",
        "2026-07-27T00:00:00.000Z",
      ],
      evidenceRoot,
    );

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stderr)).toMatchObject({
      code: "CANDIDATE_TARBALL_MISMATCH",
    });
    const linkedTarball = join(root, "linked.tgz");
    await symlink("../outside", join(alternateRoot, "package", "linked.txt"));
    await runProcess("tar", [
      "-czf",
      linkedTarball,
      "-C",
      alternateRoot,
      "package",
    ]);
    const linkedResult = await runP0Cli(
      [
        "record-candidate",
        "--packed",
        packageRoot,
        "--tarball",
        linkedTarball,
        "--dist-tag",
        "next",
        "--created-at",
        "2026-07-27T00:00:00.000Z",
      ],
      evidenceRoot,
    );
    expect(linkedResult.exitCode).toBe(1);
    expect(JSON.parse(linkedResult.stderr)).toMatchObject({
      code: "CANDIDATE_TARBALL_INVALID",
    });
    expect(await candidateEvidenceDirectories(evidenceRoot)).toEqual(
      beforeRejectedRecords,
    );
    expect(await candidateEvidenceDirectories()).toEqual(persistentBefore);
  }, 120_000);

  it("Scenario: 外部候选证据目录被拒绝且不泄露路径", async () => {
    const externalEvidenceRoot = "/private/var/folders/kpi-p0-evidence";
    const result = await runP0Cli(["check-catalog"], externalEvidenceRoot);

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stderr)).toMatchObject({
      code: "CLI_ARGUMENT_INVALID",
    });
    expect(result.stderr).not.toContain(externalEvidenceRoot);
  });

  it("Scenario: 受控 CLI 只从当前验证结果记录精确 RC 候选证据", async () => {
    const root = await candidateTemporaryRoot();
    const evidenceRoot = join(root, "candidate-evidence");
    const persistentBefore = await candidateEvidenceDirectories();
    const { packageRoot } = await unpackPluginTarball(root);
    const tarball = await rearchivePackage(root, packageRoot);
    const common = ["--packed", packageRoot, "--tarball", tarball] as const;
    const admitted = await runP0Cli(
      [
        "record-candidate",
        ...common,
        "--dist-tag",
        "next",
        "--created-at",
        "2026-07-27T00:00:00.000Z",
      ],
      evidenceRoot,
    );

    expect(admitted.exitCode, admitted.stderr).toBe(0);
    const admittedReport: unknown = JSON.parse(admitted.stdout);
    if (
      admittedReport === null ||
      typeof admittedReport !== "object" ||
      !("candidateId" in admittedReport) ||
      typeof admittedReport.candidateId !== "string"
    )
      throw new Error("Candidate admission did not return a candidate ID.");
    const candidateId = admittedReport.candidateId;

    const packageEvidence = await runP0Cli(
      [
        "record-candidate-evidence",
        "--candidate-id",
        candidateId,
        "--gate",
        "package",
        "--evidence-id",
        "rc-package",
        "--recorded-at",
        "2026-07-27T00:01:00.000Z",
        ...common,
      ],
      evidenceRoot,
    );
    expect(packageEvidence.exitCode).toBe(0);

    const decision = await runP0Cli(
      ["decide-candidate", "--candidate-id", candidateId],
      evidenceRoot,
    );
    expect(decision.exitCode).toBe(1);
    expect(JSON.parse(decision.stdout)).toMatchObject({
      decision: "blocked",
      blockers: [{ code: "TECHNICAL_EVIDENCE_MISSING" }],
    });

    const conflict = await runP0Cli(
      [
        "record-candidate",
        ...common,
        "--dist-tag",
        "next",
        "--created-at",
        "2026-07-27T00:03:00.000Z",
      ],
      evidenceRoot,
    );
    expect(conflict.exitCode).toBe(1);
    expect(JSON.parse(conflict.stderr)).toMatchObject({
      code: "CANDIDATE_ALREADY_EXISTS",
    });
    expect(await candidateEvidenceDirectories(evidenceRoot)).toContain(
      candidateId,
    );
    expect(await candidateEvidenceDirectories()).toEqual(persistentBefore);
  }, 60_000);
});
