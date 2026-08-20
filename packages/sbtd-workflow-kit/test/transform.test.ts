import { execFile } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import {
  type AgentPluginAuditReport,
  checkAgentPluginProjection,
  generateAgentPluginProjection,
} from "../src/agent-plugin-projection.ts";
import { checkGenerated, generateKit, sourceTreeSha256 } from "../src/index.ts";
import {
  proveStableInstallPolicy,
  syncUpstream,
} from "../src/sync-upstream.ts";

const packageRoot = new URL("..", import.meta.url).pathname;
const temporaryRoots: string[] = [];
const pluginPackageRoot = new URL("../../../packages/omp-sbtd/", import.meta.url)
  .pathname;
const execFileAsync = promisify(execFile);

const STABLE_MANIFEST_SHA256 =
  "5d607007086b671866142ce3d0edd0a896e8c878e5566cf7ca9b1592e7c844ca";
const STABLE_SET = "2026-08-11.1";
const V106_REVISION = "1f019e070d1ca41f064572febe055643d8dbc1ce";
const HEAD_REVISION = "4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb";
const HEAD_STABLE_SET = "2026-08-11.1";
const HEAD_STABLE_MANIFEST_SHA256 =
  "5d607007086b671866142ce3d0edd0a896e8c878e5566cf7ca9b1592e7c844ca";
const HEAD_MATTPOCOCK_REVISION = "6acc160e4e0cd062dbbbd7a1b26ae92855edf07e";
const STABLE_MANIFEST_PATH =
  "sbtd-workflow-onboard/assets/external-skills/stable/MANIFEST.json";

async function promotionFixture(): Promise<{
  root: string;
  kitRoot: string;
  pluginRoot: string;
  sourceRoot: string;
  revision: string;
}> {
  const root = await mkdtemp(join(tmpdir(), "kpi-promotion-"));
  temporaryRoots.push(root);
  const kitRoot = join(root, "kit");
  const pluginRoot = join(root, "plugin");
  const sourceRoot = join(root, "upstream");
  await Promise.all([
    mkdir(kitRoot, { recursive: true }),
    mkdir(join(pluginRoot, "scripts"), { recursive: true }),
  ]);
  await Promise.all([
    cp(join(packageRoot, "vendor"), join(kitRoot, "vendor"), {
      recursive: true,
    }),
    cp(join(packageRoot, "generated"), join(kitRoot, "generated"), {
      recursive: true,
    }),
    cp(
      join(packageRoot, "upstream.lock.json"),
      join(kitRoot, "upstream.lock.json"),
    ),
    cp(
      join(packageRoot, "agents-section-map.yaml"),
      join(kitRoot, "agents-section-map.yaml"),
    ),
    cp(join(packageRoot, "overlays"), join(kitRoot, "overlays"), {
      recursive: true,
    }),
    cp(join(packageRoot, "LICENSE"), join(kitRoot, "LICENSE")),
    cp(join(packageRoot, "package.json"), join(kitRoot, "package.json")),
    cp(
      join(packageRoot, "omp-distribution-map.yaml"),
      join(kitRoot, "omp-distribution-map.yaml"),
    ),
    cp(join(packageRoot, "omp-overlays"), join(kitRoot, "omp-overlays"), {
      recursive: true,
    }),
    cp(
      join(packageRoot, "generated-agent-plugin"),
      join(kitRoot, "generated-agent-plugin"),
      { recursive: true },
    ),
    cp(join(packageRoot, "generated-omp"), join(kitRoot, "generated-omp"), {
      recursive: true,
    }),
    cp(join(pluginPackageRoot, "kit"), join(pluginRoot, "kit"), {
      recursive: true,
    }),
    cp(join(pluginPackageRoot, "LICENSE"), join(pluginRoot, "LICENSE")),
    cp(
      join(pluginPackageRoot, "THIRD_PARTY_NOTICES.md"),
      join(pluginRoot, "THIRD_PARTY_NOTICES.md"),
    ),
    cp(
      join(pluginPackageRoot, "scripts", "embed-kit.mjs"),
      join(pluginRoot, "scripts", "embed-kit.mjs"),
    ),
    cp(join(packageRoot, "vendor", "sbtd-workflow-kit-upstream"), sourceRoot, {
      recursive: true,
    }),
  ]);
  await writeFile(
    join(sourceRoot, "CHANGELOG.md"),
    `${await readFile(join(sourceRoot, "CHANGELOG.md"), "utf8")}\nPromotion fixture revision.\n`,
    "utf8",
  );
  await mkdir(join(pluginRoot, "dist"), { recursive: true });
  await Promise.all([
    writeFile(
      join(pluginRoot, "package.json"),
      `${JSON.stringify(
        {
          name: "@kunolu/omp-sbtd-fixture",
          version: "0.0.0-fixture",
          license: "Apache-2.0",
          files: [
            "dist",
            "kit",
            "LICENSE",
            "README.md",
            "SECURITY.md",
            "CHANGELOG.md",
            "SBOM.spdx.json",
            "THIRD_PARTY_NOTICES.md",
          ],
        },
        null,
        2,
      )}\n`,
      "utf8",
    ),
    writeFile(
      join(pluginRoot, "README.md"),
      "Promotion fixture Plugin.\n",
      "utf8",
    ),
    writeFile(
      join(pluginRoot, "SECURITY.md"),
      "Promotion fixture security policy.\n",
      "utf8",
    ),
    writeFile(
      join(pluginRoot, "CHANGELOG.md"),
      "Promotion fixture changelog.\n",
      "utf8",
    ),
    writeFile(join(pluginRoot, "dist", "extension.js"), "export {};\n", "utf8"),
    writeFile(
      join(pluginRoot, "SBOM.spdx.json"),
      '{"spdxVersion":"SPDX-2.3","files":[]}\n',
      "utf8",
    ),
  ]);
  await execFileAsync("git", ["init", sourceRoot]);
  await execFileAsync("git", [
    "-C",
    sourceRoot,
    "config",
    "user.email",
    "test@kpi.invalid",
  ]);
  await execFileAsync("git", [
    "-C",
    sourceRoot,
    "config",
    "user.name",
    "KPi Test",
  ]);
  await execFileAsync("git", [
    "-C",
    sourceRoot,
    "remote",
    "add",
    "origin",
    "git@github.com:KunoLu/640-skills.git",
  ]);
  await execFileAsync("git", ["-C", sourceRoot, "add", "."]);
  await execFileAsync("git", ["-C", sourceRoot, "commit", "-m", "fixture"]);
  const { stdout } = await execFileAsync("git", [
    "-C",
    sourceRoot,
    "rev-parse",
    "HEAD",
  ]);
  const revision = stdout.trim();
  await execFileAsync("git", ["init", root]);
  await execFileAsync("git", [
    "-C",
    root,
    "config",
    "user.email",
    "test@kpi.invalid",
  ]);
  await execFileAsync("git", ["-C", root, "config", "user.name", "KPi Test"]);
  await execFileAsync("git", ["-C", root, "add", "kit", "plugin"]);
  await execFileAsync("git", [
    "-C",
    root,
    "commit",
    "-m",
    "promotion destinations baseline",
  ]);
  return {
    root,
    kitRoot,
    pluginRoot,
    sourceRoot,
    revision,
  };
}

async function promotionState(
  kitRoot: string,
  pluginRoot: string,
): Promise<readonly string[]> {
  return Promise.all([
    sourceTreeSha256(join(kitRoot, "vendor/sbtd-workflow-kit-upstream")),
    readFile(join(kitRoot, "upstream.lock.json"), "utf8"),
    readFile(join(kitRoot, "agents-section-map.yaml"), "utf8"),
    readFile(join(kitRoot, "overlays/AGENTS.project-omp.md"), "utf8"),
    readFile(join(kitRoot, "generated/manifest.json"), "utf8"),
    readFile(join(kitRoot, "omp-distribution-map.yaml"), "utf8"),
    readFile(
      join(
        kitRoot,
        "omp-overlays/onboard/runtime/templates/project/gitignore.template",
      ),
      "utf8",
    ),
    readFile(join(kitRoot, "generated-omp/manifest.json"), "utf8"),
    readFile(join(kitRoot, "generated-agent-plugin/manifest.json"), "utf8"),
    readFile(join(pluginRoot, "kit/manifest.json"), "utf8"),
    readFile(join(pluginRoot, "LICENSE"), "utf8"),
    readFile(join(pluginRoot, "THIRD_PARTY_NOTICES.md"), "utf8"),
    readFile(join(pluginRoot, "SBOM.spdx.json"), "utf8"),
  ]);
}

async function fixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-kit-"));
  temporaryRoots.push(root);
  await Promise.all([
    cp(join(packageRoot, "vendor"), join(root, "vendor"), { recursive: true }),
    cp(
      join(packageRoot, "upstream.lock.json"),
      join(root, "upstream.lock.json"),
    ),
    cp(
      join(packageRoot, "agents-section-map.yaml"),
      join(root, "agents-section-map.yaml"),
    ),
    cp(join(packageRoot, "overlays"), join(root, "overlays"), {
      recursive: true,
    }),
    cp(join(packageRoot, "LICENSE"), join(root, "LICENSE")),
  ]);
  return root;
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("Feature: Agent Plugin 可移植 Skill 投影", () => {
  it("Scenario: 审计全部 portable 候选", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const outputDirectory = join(root, "generated-agent-plugin");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });

    const result = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    });

    expect(result.audit.candidateCount).toBe(13);
    expect(result.audit.results).toHaveLength(13);
    expect(result.audit.results).toContainEqual(
      expect.objectContaining({
        name: "project-validation",
        disposition: "certified",
        runtimeDependencies: expect.arrayContaining([
          "conditional Python 3.10+",
          "conditional jsonschema",
        ]),
        checks: expect.objectContaining({
          "reference-script": expect.objectContaining({ status: "pass" }),
          "runtime-dependency": expect.objectContaining({ status: "pass" }),
        }),
      }),
    );
    expect(result.audit.results).toContainEqual(
      expect.objectContaining({
        name: "trellis-workflow",
        disposition: "onboard-owned",
      }),
    );
    expect(result.catalog.candidateCount).toBe(13);
    expect(result.catalog.certifiedCount).toBe(result.audit.certifiedCount);
    expect(result.catalog.entries).toContainEqual(
      expect.objectContaining({
        name: "trellis-workflow",
        certification: expect.objectContaining({
          disposition: "onboard-owned",
          projectionSha256: null,
        }),
      }),
    );
  });
  it("Scenario: 审计失败的 Skill 不进入投影", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const outputDirectory = join(root, "generated-agent-plugin");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });

    const result = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    });
    const certified = result.audit.results.filter(
      ({ disposition }) => disposition === "certified",
    );
    expect(result.audit.certifiedCount).toBe(certified.length);
    expect(result.manifest.certified).not.toContain("trellis-workflow");
    await expect(
      readFile(join(outputDirectory, "skills", "trellis-workflow", "SKILL.md")),
    ).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("Scenario: 审计阻塞不发布部分投影", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const outputDirectory = join(root, "generated-agent-plugin");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });
    await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    });
    const before = await readFile(
      join(outputDirectory, "manifest.json"),
      "utf8",
    );
    await rm(
      join(
        canonicalDirectory,
        "onboard/runtime/templates/skills/project-validation/SKILL.md",
      ),
    );

    const rejected = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    }).then(
      () => undefined,
      (cause: unknown) => cause,
    );
    expect(rejected).toMatchObject({
      code: "PROJECTION_POLICY_INVALID",
      details: {
        phase: "agent-plugin",
        candidates: ["project-validation"],
      },
    });
    const blocked = (
      rejected as {
        details: { audit: AgentPluginAuditReport };
      }
    ).details.audit.results.find(({ name }) => name === "project-validation");
    expect(blocked?.disposition).toBe("blocked");
    expect(
      Object.values(blocked?.checks ?? {}).every(
        ({ status }) => status === "blocked",
      ),
    ).toBe(true);
    expect(await readFile(join(outputDirectory, "manifest.json"), "utf8")).toBe(
      before,
    );
  });

  it("Scenario: 脚本语法无效时不认证候选", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const outputDirectory = join(root, "generated-agent-plugin");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });
    await writeFile(
      join(
        canonicalDirectory,
        "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py",
      ),
      "def broken(:\n",
      "utf8",
    );

    const result = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    });
    const projectValidation = result.audit.results.find(
      ({ name }) => name === "project-validation",
    );
    expect(projectValidation?.disposition).toBe("onboard-owned");
    expect(projectValidation?.checks["reference-script"]).toMatchObject({
      status: "fail",
    });
    expect(
      projectValidation?.checks["reference-script"].reasons.join("\n"),
    ).toContain("Python syntax error");
    expect(result.manifest.certified).not.toContain("project-validation");
    await expect(
      readFile(
        join(
          outputDirectory,
          "skills/project-validation/scripts/validate_validation_evidence.py",
        ),
      ),
    ).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("Scenario: 脚本依赖未声明时不认证候选", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const outputDirectory = join(root, "generated-agent-plugin");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });
    const scriptPath = join(
      canonicalDirectory,
      "onboard/runtime/templates/skills/project-validation/scripts/validate_validation_evidence.py",
    );
    await writeFile(
      scriptPath,
      `${await readFile(scriptPath, "utf8")}\nimport requests\n`,
      "utf8",
    );

    const result = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    });
    const projectValidation = result.audit.results.find(
      ({ name }) => name === "project-validation",
    );
    expect(projectValidation?.disposition).toBe("onboard-owned");
    expect(projectValidation?.checks["runtime-dependency"]).toMatchObject({
      status: "fail",
    });
    expect(
      projectValidation?.checks["runtime-dependency"].reasons.join("\n"),
    ).toContain("undeclared Python dependency: requests");
    expect(result.manifest.certified).not.toContain("project-validation");
    await expect(
      readFile(
        join(
          outputDirectory,
          "skills/project-validation/scripts/validate_validation_evidence.py",
        ),
      ),
    ).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("rejects projection paths outside the package root", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });

    await expect(
      generateAgentPluginProjection({
        packageRoot: root,
        canonicalDirectory,
        outputDirectory: join(root, "..", "generated-agent-plugin-outside"),
      }),
    ).rejects.toMatchObject({
      code: "PROJECTION_POLICY_INVALID",
      details: { phase: "agent-plugin" },
    });
  });

  it("Scenario: certified Skill 投影可复现", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const firstOutput = join(root, "generated-agent-plugin-first");
    const secondOutput = join(root, "generated-agent-plugin-second");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });

    const first = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory: firstOutput,
    });
    const second = await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory: secondOutput,
    });

    expect(second.manifest).toEqual(first.manifest);
    expect(await sourceTreeSha256(secondOutput)).toBe(
      await sourceTreeSha256(firstOutput),
    );
    const skill = await readFile(
      join(firstOutput, "skills", "project-validation", "SKILL.md"),
      "utf8",
    );
    const closing = skill.indexOf("\n---\n", 4);
    const attributes = parseYaml(skill.slice(4, closing)) as Record<
      string,
      unknown
    >;
    expect(Object.keys(attributes).sort()).toEqual([
      "allowed-tools",
      "compatibility",
      "description",
      "license",
      "metadata",
      "name",
    ]);
  });

  it("Scenario: 手工修改投影后检查失败", async () => {
    const root = await fixture();
    const canonicalDirectory = join(root, "generated");
    const outputDirectory = join(root, "generated-agent-plugin");
    await generateKit({
      packageRoot: root,
      outputDirectory: canonicalDirectory,
    });
    await generateAgentPluginProjection({
      packageRoot: root,
      canonicalDirectory,
      outputDirectory,
    });
    const skillPath = join(
      outputDirectory,
      "skills",
      "project-validation",
      "SKILL.md",
    );
    await writeFile(
      skillPath,
      `${await readFile(skillPath, "utf8")}\nmanual drift\n`,
      "utf8",
    );

    await expect(
      checkAgentPluginProjection({
        packageRoot: root,
        canonicalDirectory,
        outputDirectory,
      }),
    ).rejects.toMatchObject({
      code: "GENERATED_DRIFT",
      details: { phase: "agent-plugin" },
    });
  });
});

describe("Feature: 三目标 AGENTS 转换", () => {
  it("Scenario: 从完整 Section Mapping 生成三目标 AGENTS", async () => {
    const root = await fixture();
    const output = join(root, "generated");

    const result = await generateKit({
      packageRoot: root,
      outputDirectory: output,
    });

    expect(result.targets).toEqual([
      "AGENTS.global.md",
      "AGENTS.project-root.md",
      "AGENTS.project-omp.md",
    ]);
    expect(
      await readFile(join(output, "AGENTS.project-omp.md"), "utf8"),
    ).toContain("@../AGENTS.md");
    expect(
      await readFile(join(output, "AGENTS.project-omp.md"), "utf8"),
    ).toContain("sbtd-runtime.effective-control-state=active");
    expect(
      await readFile(join(output, "AGENTS.project-root.md"), "utf8"),
    ).not.toContain("## Trellis Channel");
    expect(
      await readFile(join(output, "AGENTS.project-omp.md"), "utf8"),
    ).toContain("### 主动 Preflight 场景");
    expect(result.manifest.assets).toMatchObject({
      "onboard/runtime/catalog.json": expect.stringMatching(/^[0-9a-f]{64}$/),
      "onboard/runtime/scripts/onboard.py":
        expect.stringMatching(/^[0-9a-f]{64}$/),
      LICENSE: expect.stringMatching(/^[0-9a-f]{64}$/),
      "THIRD_PARTY_NOTICES.md": expect.stringMatching(/^[0-9a-f]{64}$/),
      "third-party/sbtd-workflow-onboard/LICENSE":
        expect.stringMatching(/^[0-9a-f]{64}$/),
      "third-party/sbtd-workflow-onboard/NOTICE":
        expect.stringMatching(/^[0-9a-f]{64}$/),
    });
    expect(result.syncReport.unmapped).toEqual([]);
    expect(result.manifest.sourceId).toBe("sbtd-workflow-kit-upstream");
    expect(result.manifest.overlayDigests["AGENTS.project-omp.md"]).toMatch(
      /^[0-9a-f]{64}$/,
    );
    expect(
      JSON.parse(await readFile(join(output, "sync-report.json"), "utf8")),
    ).toMatchObject({
      generatedSha256: result.manifest.generatedSha256,
      inputReadSet: {
        sourceTreeSha256: result.manifest.sourceTreeSha256,
        overlayDigests: result.manifest.overlayDigests,
      },
    });
  });

  it("Scenario: 生成 Kit 以 Apache-2.0 标识并保留上游许可证通知", async () => {
    const root = await fixture();
    const output = join(root, "generated");

    await generateKit({ packageRoot: root, outputDirectory: output });

    await expect(readFile(join(output, "LICENSE"), "utf8")).resolves.toBe(
      await readFile(join(root, "LICENSE"), "utf8"),
    );
    await expect(
      readFile(
        join(output, "third-party/sbtd-workflow-onboard/LICENSE"),
        "utf8",
      ),
    ).resolves.toBe(
      await readFile(
        join(
          root,
          "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/LICENSE",
        ),
        "utf8",
      ),
    );
    await expect(
      readFile(
        join(output, "third-party/sbtd-workflow-onboard/NOTICE"),
        "utf8",
      ),
    ).resolves.toBe(
      await readFile(
        join(
          root,
          "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/NOTICE",
        ),
        "utf8",
      ),
    );
  });

  it("Scenario: 生成 Kit 使用可分发模板并保留目标忽略规则", async () => {
    const root = await fixture();
    const output = join(root, "generated");

    const result = await generateKit({
      packageRoot: root,
      outputDirectory: output,
    });
    const sourceRoot = join(
      root,
      "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/templates",
    );
    const projectTemplate =
      "onboard/runtime/templates/project/gitignore.template";
    const webUiTemplate =
      "onboard/runtime/templates/skills/web-ui-autotest-generator/gitignore.template";
    const catalog = JSON.parse(
      await readFile(join(output, "onboard/runtime/catalog.json"), "utf8"),
    ) as {
      entries: Array<{ id: string; source: string }>;
    };

    expect(await readFile(join(output, projectTemplate), "utf8")).toBe(
      await readFile(join(sourceRoot, "project/.gitignore"), "utf8"),
    );
    expect(await readFile(join(output, webUiTemplate), "utf8")).toBe(
      await readFile(
        join(sourceRoot, "skills/web-ui-autotest-generator/.gitignore"),
        "utf8",
      ),
    );
    expect(
      catalog.entries.find((entry) => entry.id === "project:gitignore"),
    ).toMatchObject({ source: "templates/project/gitignore.template" });
    expect(Object.hasOwn(result.manifest.assets, projectTemplate)).toBe(true);
    expect(Object.hasOwn(result.manifest.assets, webUiTemplate)).toBe(true);
    expect(
      Object.hasOwn(
        result.manifest.assets,
        "onboard/runtime/templates/project/.gitignore",
      ),
    ).toBe(false);
    const projectedOnboard = await readFile(
      join(output, "onboard/runtime/scripts/onboard.py"),
      "utf8",
    );
    expect(projectedOnboard).toContain("gitignore.template");
  });

  it("Scenario: 使用相同输入重复生成", async () => {
    const root = await fixture();
    const first = join(root, "first");
    const second = join(root, "second");

    await generateKit({ packageRoot: root, outputDirectory: first });
    await generateKit({ packageRoot: root, outputDirectory: second });

    expect(await readFile(join(first, "manifest.json"), "utf8")).toBe(
      await readFile(join(second, "manifest.json"), "utf8"),
    );
    expect(await readFile(join(first, "AGENTS.project-root.md"), "utf8")).toBe(
      await readFile(join(second, "AGENTS.project-root.md"), "utf8"),
    );
  });

  it("Scenario: 上游新增未映射 Section", async () => {
    const root = await fixture();
    const source = join(
      root,
      "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/templates/agents/AGENTS.project.md",
    );
    await writeFile(
      source,
      `${await readFile(source, "utf8")}\n## 未映射变更\n`,
      "utf8",
    );
    const lock = join(root, "upstream.lock.json");
    await writeFile(
      lock,
      JSON.stringify({
        ...(JSON.parse(await readFile(lock, "utf8")) as object),
        sourceTreeSha256: await sourceTreeSha256(
          join(root, "vendor/sbtd-workflow-kit-upstream"),
        ),
      }),
      "utf8",
    );

    await expect(
      generateKit({
        packageRoot: root,
        outputDirectory: join(root, "generated"),
      }),
    ).rejects.toMatchObject({
      code: "SECTION_UNMAPPED",
      details: {
        syncReport: {
          added: expect.arrayContaining([
            "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则 > 未映射变更",
          ]),
          unmapped: expect.arrayContaining([
            "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则 > 未映射变更",
          ]),
        },
      },
    });
  });

  it("Scenario: Mapping 引用不存在的 Section", async () => {
    const root = await fixture();
    const mapping = join(root, "agents-section-map.yaml");
    const missingSection =
      "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::不存在的 Section";
    await writeFile(
      mapping,
      `${await readFile(mapping, "utf8")}\n  - source: "${missingSection}"\n    policy: include\n    owner: project-root\n`,
      "utf8",
    );

    await expect(
      generateKit({
        packageRoot: root,
        outputDirectory: join(root, "generated"),
      }),
    ).rejects.toMatchObject({
      code: "SECTION_MAPPING_UNKNOWN",
      details: {
        syncReport: { removed: [missingSection] },
      },
    });
  });

  it("Scenario: 一个 Section 重复声明 Mapping policy", async () => {
    const root = await fixture();
    const mapping = join(root, "agents-section-map.yaml");
    const duplicateSection =
      "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则";
    await writeFile(
      mapping,
      `${await readFile(mapping, "utf8")}\n  - source: "${duplicateSection}"\n    policy: include\n    owner: project-omp\n`,
      "utf8",
    );

    await expect(
      generateKit({
        packageRoot: root,
        outputDirectory: join(root, "generated"),
      }),
    ).rejects.toMatchObject({
      code: "SECTION_MAPPING_CONFLICT",
      details: { source: duplicateSection },
    });
  });

  it("Scenario: 上游 source digest 与 lock 不一致", async () => {
    const root = await fixture();
    const lock = join(root, "upstream.lock.json");
    await writeFile(
      lock,
      JSON.stringify({
        ...(JSON.parse(await readFile(lock, "utf8")) as object),
        sourceTreeSha256: "0".repeat(64),
      }),
      "utf8",
    );

    await expect(
      generateKit({
        packageRoot: root,
        outputDirectory: join(root, "generated"),
      }),
    ).rejects.toMatchObject({ code: "SOURCE_DIGEST_MISMATCH" });
  });

  it("Scenario: 已生成快照发生漂移", async () => {
    const root = await fixture();
    const output = join(root, "generated");
    await generateKit({ packageRoot: root, outputDirectory: output });
    await writeFile(join(output, "catalog.json"), "{}\n", "utf8");

    await expect(
      checkGenerated({ packageRoot: root, outputDirectory: output }),
    ).rejects.toMatchObject({ code: "GENERATED_DRIFT" });
  });

  it("Scenario: 已生成桥接资产发生漂移", async () => {
    const root = await fixture();
    const output = join(root, "generated");
    await generateKit({ packageRoot: root, outputDirectory: output });
    await writeFile(
      join(output, "onboard/runtime/scripts/onboard.py"),
      "# drift\n",
      "utf8",
    );

    await expect(
      checkGenerated({ packageRoot: root, outputDirectory: output }),
    ).rejects.toMatchObject({
      code: "GENERATED_DRIFT",
      details: { target: "onboard/runtime/scripts/onboard.py" },
    });
  });
  it("Scenario: Mapping 明确声明 omit 与 replace-with-overlay 策略", async () => {
    const root = await fixture();
    const mapping = join(root, "agents-section-map.yaml");
    const finalGoal =
      '  - source: "sbtd-workflow-onboard/templates/agents/AGENTS.global.md::Codex 全局规则 > 最终目标"\n    policy: include\n    owner: global';
    await writeFile(
      mapping,
      (await readFile(mapping, "utf8")).replace(
        finalGoal,
        '  - source: "sbtd-workflow-onboard/templates/agents/AGENTS.global.md::Codex 全局规则 > 最终目标"\n    policy: omit\n    reason: "KPi target does not retain this upstream closing section"',
      ),
      "utf8",
    );

    await generateKit({
      packageRoot: root,
      outputDirectory: join(root, "generated"),
    });
    await expect(
      readFile(join(root, "generated", "AGENTS.global.md"), "utf8"),
    ).resolves.not.toContain("## 最终目标");

    const missingOverlayRoot = await fixture();
    await writeFile(
      join(missingOverlayRoot, "overlays", "AGENTS.project-omp.md"),
      "",
      "utf8",
    );
    await expect(
      generateKit({
        packageRoot: missingOverlayRoot,
        outputDirectory: join(missingOverlayRoot, "generated"),
      }),
    ).rejects.toMatchObject({ code: "SECTION_OVERLAY_MISSING" });
    const invalidOverlayRoot = await fixture();
    const invalidOverlayMap = join(
      invalidOverlayRoot,
      "agents-section-map.yaml",
    );
    await writeFile(
      invalidOverlayMap,
      (await readFile(invalidOverlayMap, "utf8")).replace(
        "overlay: AGENTS.project-omp.md",
        "overlay: ../outside.md",
      ),
      "utf8",
    );
    await expect(
      generateKit({
        packageRoot: invalidOverlayRoot,
        outputDirectory: join(invalidOverlayRoot, "generated"),
      }),
    ).rejects.toMatchObject({ code: "KIT_INPUT_INVALID" });

    const nestedPolicyRoot = await fixture();
    const nestedMapping = join(nestedPolicyRoot, "agents-section-map.yaml");
    const nestedSection =
      '  - source: "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则 > Trellis Channel > 主动 Preflight 场景"\n    policy: replace-with-overlay\n    owner: project-omp\n    overlay: AGENTS.project-omp.md';
    await writeFile(
      nestedMapping,
      (await readFile(nestedMapping, "utf8")).replace(
        nestedSection,
        '  - source: "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则 > Trellis Channel > 主动 Preflight 场景"\n    policy: include\n    owner: project-omp',
      ),
      "utf8",
    );
    await expect(
      generateKit({
        packageRoot: nestedPolicyRoot,
        outputDirectory: join(nestedPolicyRoot, "generated"),
      }),
    ).rejects.toMatchObject({ code: "SECTION_MAPPING_CONFLICT" });
  });

  it("Scenario: sync-upstream plan 不写入 Kit 或 Plugin", async () => {
    const promotion = await promotionFixture();
    const before = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );

    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    await writeFile(
      join(promotion.sourceRoot, "uncommitted-upstream-change.md"),
      "this file must not affect git archive staging\n",
      "utf8",
    );
    const repeatedPlan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });

    expect(plan.status).toBe("planned");
    expect(plan.resolvedRevision).toBe(promotion.revision);
    expect(plan.stagedPluginValidated).toBe(true);
    expect(plan.changedInputPaths).toContain(
      "vendor/sbtd-workflow-kit-upstream/CHANGELOG.md",
    );
    expect(plan.planDigest).toBe(repeatedPlan.planDigest);
    expect(plan.agentPluginProjection.candidateCount).toBe(13);
    expect(plan.agentPluginProjection.certifiedCount).toBeGreaterThan(0);
    expect(
      plan.changedInputPaths.some((path) =>
        path.startsWith("generated-agent-plugin/"),
      ),
    ).toBe(true);
    expect(plan.classifiedSections).toContainEqual(
      expect.objectContaining({ policy: "replace-with-overlay" }),
    );
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(before);
  }, 30_000);
  it("Scenario: 上游提升必须携带完整第三树", async () => {
    const promotion = await promotionFixture();
    const before = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });

    await expect(
      syncUpstream({
        mode: "apply",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
        planDigest: plan.planDigest,
        replacePath: async (source, destination) => {
          if (destination === join(promotion.kitRoot, "generated-agent-plugin"))
            return;
          await rename(source, destination);
        },
      }),
    ).rejects.toMatchObject({ code: "TRANSACTION_FAILED" });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(before);
  }, 30_000);

  it("Scenario: 过期的 sync-upstream plan 在写入前被拒绝", async () => {
    const promotion = await promotionFixture();
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    await writeFile(
      join(promotion.kitRoot, "overlays", "AGENTS.project-omp.md"),
      `${await readFile(
        join(promotion.kitRoot, "overlays", "AGENTS.project-omp.md"),
        "utf8",
      )}\n<!-- changed after plan -->\n`,
      "utf8",
    );
    await execFileAsync("git", [
      "-C",
      promotion.root,
      "add",
      "kit/overlays/AGENTS.project-omp.md",
    ]);
    await execFileAsync("git", [
      "-C",
      promotion.root,
      "commit",
      "-m",
      "reviewed overlay change after plan",
    ]);
    const beforeApply = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );

    await expect(
      syncUpstream({
        mode: "apply",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
        planDigest: plan.planDigest,
      }),
    ).rejects.toMatchObject({ code: "STALE_PLAN" });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(beforeApply);
  }, 30_000);

  it("Scenario: projection 输入变动使既有 plan 过期", async () => {
    const promotion = await promotionFixture();
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    expect(plan.projection.policySha256).toMatch(/^[0-9a-f]{64}$/);
    expect(plan.projection.decisionsSha256).toMatch(/^[0-9a-f]{64}$/);
    const mapPath = join(promotion.kitRoot, "omp-distribution-map.yaml");
    await writeFile(
      mapPath,
      `${await readFile(mapPath, "utf8")}\n# reviewed projection policy change\n`,
      "utf8",
    );
    await execFileAsync("git", [
      "-C",
      promotion.root,
      "add",
      "kit/omp-distribution-map.yaml",
    ]);
    await execFileAsync("git", [
      "-C",
      promotion.root,
      "commit",
      "-m",
      "reviewed projection policy change after plan",
    ]);
    const beforeApply = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );

    await expect(
      syncUpstream({
        mode: "apply",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
        planDigest: plan.planDigest,
      }),
    ).rejects.toMatchObject({ code: "STALE_PLAN" });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(beforeApply);
  }, 30_000);

  it("Scenario: sync-upstream 在 Plugin 候选验证失败前不替换输出", async () => {
    const promotion = await promotionFixture();
    const before = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );
    await writeFile(
      join(promotion.pluginRoot, "scripts", "embed-kit.mjs"),
      'throw new Error("invalid staged Plugin");\n',
      "utf8",
    );

    await expect(
      syncUpstream({
        mode: "plan",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
      }),
    ).rejects.toMatchObject({ code: "STAGED_PLUGIN_INVALID" });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(before);
  }, 30_000);

  it("Scenario: sync-upstream apply 嵌入与已提升 Kit 一致的 Plugin 快照", async () => {
    const promotion = await promotionFixture();
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });

    const applied = await syncUpstream({
      mode: "apply",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
      planDigest: plan.planDigest,
    });

    expect(applied.status).toBe("applied");
    expect(
      await readFile(
        join(promotion.pluginRoot, "kit", "manifest.json"),
        "utf8",
      ),
    ).toBe(
      await readFile(
        join(promotion.kitRoot, "generated-omp", "manifest.json"),
        "utf8",
      ),
    );
    const appliedManifest = JSON.parse(
      await readFile(
        join(promotion.pluginRoot, "kit", "manifest.json"),
        "utf8",
      ),
    ) as { schemaVersion: number; canonical: { resolvedRevision: string } };
    expect(appliedManifest.schemaVersion).toBe(2);
    expect(appliedManifest.canonical.resolvedRevision).toBe(promotion.revision);
    await expect(
      readFile(join(promotion.pluginRoot, "LICENSE"), "utf8"),
    ).resolves.toBe(
      await readFile(join(promotion.pluginRoot, "kit", "LICENSE"), "utf8"),
    );
    await expect(
      readFile(join(promotion.pluginRoot, "THIRD_PARTY_NOTICES.md"), "utf8"),
    ).resolves.toContain("kit/onboard/runtime/LICENSE");
    const appliedSbom = JSON.parse(
      await readFile(join(promotion.pluginRoot, "SBOM.spdx.json"), "utf8"),
    ) as { spdxVersion: string; files: readonly { fileName: string }[] };
    expect(appliedSbom.spdxVersion).toBe("SPDX-2.3");
    expect(
      appliedSbom.files.some((file) => file.fileName === "./kit/manifest.json"),
    ).toBe(true);
    expect(
      appliedSbom.files.some(
        (file) => file.fileName === "./kit/onboard/runtime/catalog.json",
      ),
    ).toBe(true);
  }, 30_000);

  it("Scenario: destination 备份失败时保留 Kit 与 Plugin", async () => {
    const promotion = await promotionFixture();
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    const before = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );

    await expect(
      syncUpstream({
        mode: "apply",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
        planDigest: plan.planDigest,
        backupPath: async () => {
          throw new Error("induced destination backup failure");
        },
      }),
    ).rejects.toMatchObject({ code: "TRANSACTION_FAILED" });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(before);
  }, 30_000);

  it("Scenario: 最后一个 Plugin 替换失败时恢复 Kit 与 Plugin", async () => {
    const promotion = await promotionFixture();
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    const before = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );
    let replacementCount = 0;

    await expect(
      syncUpstream({
        mode: "apply",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
        planDigest: plan.planDigest,
        replacePath: async (source, destination) => {
          replacementCount += 1;
          if (replacementCount === 10)
            throw new Error("induced final Plugin SBOM replacement failure");
          await rename(source, destination);
        },
      }),
    ).rejects.toMatchObject({ code: "TRANSACTION_FAILED" });
    expect(replacementCount).toBe(10);
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(before);
  }, 30_000);

  it("Scenario: sync-upstream plan 绑定 stable manifest 派生 provenance", async () => {
    const promotion = await promotionFixture();
    const before = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );

    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });

    expect(plan.status).toBe("planned");
    expect(plan.stableProvenance).toMatchObject({
      stableSet: STABLE_SET,
      manifestSha256: STABLE_MANIFEST_SHA256,
    });
    expect(
      plan.stableProvenance.repositories["mattpocock-skills"],
    ).toMatchObject({
      url: "https://github.com/mattpocock/skills.git",
      license: "MIT",
    });
    expect(
      plan.stableProvenance.repositories["mattpocock-skills"]?.revision,
    ).toMatch(/^[0-9a-f]{40}$/);
    expect(plan.projection.policySha256).toMatch(/^[0-9a-f]{64}$/);
    expect(plan.projection.decisionsSha256).toMatch(/^[0-9a-f]{64}$/);
    expect(plan.projection.retainedProvenanceManifestSha256).toMatch(
      /^[0-9a-f]{64}$/,
    );
    expect(plan.dirtyPreflight).toEqual({
      dirty: false,
      conflictingPaths: [],
    });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(before);

    const manifestPath = join(promotion.sourceRoot, STABLE_MANIFEST_PATH);
    const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
      stableSet: string;
    };
    manifest.stableSet = "2026-08-03.2";
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    await execFileAsync("git", ["-C", promotion.sourceRoot, "add", "."]);
    await execFileAsync("git", [
      "-C",
      promotion.sourceRoot,
      "commit",
      "-m",
      "stable set drift",
    ]);
    const { stdout } = await execFileAsync("git", [
      "-C",
      promotion.sourceRoot,
      "rev-parse",
      "HEAD",
    ]);
    const driftedRevision = stdout.trim();
    const beforeDriftedPlan = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );
    const driftedPlan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: driftedRevision,
    });

    expect(driftedPlan.stableProvenance.stableSet).toBe("2026-08-03.2");
    expect(driftedPlan.planDigest).not.toBe(plan.planDigest);
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(beforeDriftedPlan);
  }, 60_000);

  it("Scenario: stable manifest 漂移在生成或提升前被拒绝", async () => {
    const syncFixtureLock = async (root: string): Promise<void> => {
      const lock = join(root, "upstream.lock.json");
      await writeFile(
        lock,
        JSON.stringify({
          ...(JSON.parse(await readFile(lock, "utf8")) as object),
          sourceTreeSha256: await sourceTreeSha256(
            join(root, "vendor/sbtd-workflow-kit-upstream"),
          ),
        }),
        "utf8",
      );
    };

    const treeDrift = await fixture();
    const skillFile = join(
      treeDrift,
      "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/assets/external-skills/stable/skills/grill-me/SKILL.md",
    );
    await writeFile(
      skillFile,
      `${await readFile(skillFile, "utf8")}\ndrift\n`,
      "utf8",
    );
    await syncFixtureLock(treeDrift);
    await expect(
      generateKit({
        packageRoot: treeDrift,
        outputDirectory: join(treeDrift, "generated"),
      }),
    ).rejects.toMatchObject({
      code: "STABLE_MANIFEST_INVALID",
      details: { skill: "grill-me" },
    });

    const invalidRevision = await fixture();
    const manifestPath = join(
      invalidRevision,
      "vendor/sbtd-workflow-kit-upstream",
      STABLE_MANIFEST_PATH,
    );
    const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
      repositories: Record<string, { revision: string }>;
    };
    const repository = manifest.repositories["mattpocock-skills"];
    if (repository === undefined) throw new Error("fixture repository missing");
    repository.revision = "not-a-revision";
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    await syncFixtureLock(invalidRevision);
    await expect(
      generateKit({
        packageRoot: invalidRevision,
        outputDirectory: join(invalidRevision, "generated"),
      }),
    ).rejects.toMatchObject({ code: "STABLE_MANIFEST_INVALID" });

    const derived = await fixture();
    const output = join(derived, "generated");
    const result = await generateKit({
      packageRoot: derived,
      outputDirectory: output,
    });
    expect(result.manifest.stableProvenance).toMatchObject({
      stableSet: STABLE_SET,
      manifestSha256: STABLE_MANIFEST_SHA256,
    });
    expect(
      result.manifest.stableProvenance.repositories["mattpocock-skills"],
    ).toMatchObject({
      url: "https://github.com/mattpocock/skills.git",
      license: "MIT",
    });
    expect(result.syncReport.inputReadSet.stableManifestSha256).toBe(
      STABLE_MANIFEST_SHA256,
    );
    const notices = await readFile(
      join(output, "THIRD_PARTY_NOTICES.md"),
      "utf8",
    );
    expect(notices).toContain(
      `## Stable External Skills (stable set ${STABLE_SET})`,
    );
    expect(notices).toContain(
      "- Source: https://github.com/mattpocock/skills.git@",
    );
    expect(notices).toContain(
      "- Retained license: onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE",
    );

    const generatedManifest = JSON.parse(
      await readFile(join(output, "manifest.json"), "utf8"),
    ) as { stableProvenance: { stableSet: string } };
    generatedManifest.stableProvenance.stableSet = "1999-01-01.1";
    await writeFile(
      join(output, "manifest.json"),
      `${JSON.stringify(generatedManifest, null, 2)}\n`,
      "utf8",
    );
    await expect(
      checkGenerated({ packageRoot: derived, outputDirectory: output }),
    ).rejects.toMatchObject({ code: "GENERATED_DRIFT" });
  }, 60_000);

  it("Scenario: promotion-owned 脏路径在 Apply 前被拒绝", async () => {
    const promotion = await promotionFixture();
    const plan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    expect(plan.dirtyPreflight).toEqual({
      dirty: false,
      conflictingPaths: [],
    });

    const ownedManifest = join(promotion.kitRoot, "generated", "manifest.json");
    await writeFile(
      ownedManifest,
      `${await readFile(ownedManifest, "utf8")} \n`,
      "utf8",
    );
    const dirtyPlan = await syncUpstream({
      mode: "plan",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
    });
    expect(dirtyPlan.status).toBe("planned");
    expect(dirtyPlan.dirtyPreflight).toEqual({
      dirty: true,
      conflictingPaths: ["kit/generated/manifest.json"],
    });
    for (const path of dirtyPlan.dirtyPreflight.conflictingPaths) {
      expect(path.startsWith("/")).toBe(false);
      expect(path.includes("\\")).toBe(false);
    }

    const beforeApply = await promotionState(
      promotion.kitRoot,
      promotion.pluginRoot,
    );
    await expect(
      syncUpstream({
        mode: "apply",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: promotion.sourceRoot,
        revision: promotion.revision,
        planDigest: plan.planDigest,
      }),
    ).rejects.toMatchObject({
      code: "PROMOTION_DESTINATION_DIRTY",
      details: { conflictingPaths: ["kit/generated/manifest.json"] },
    });
    expect(
      await promotionState(promotion.kitRoot, promotion.pluginRoot),
    ).toEqual(beforeApply);

    await execFileAsync("git", [
      "-C",
      promotion.root,
      "checkout",
      "--",
      "kit/generated/manifest.json",
    ]);
    await writeFile(
      join(promotion.root, "maintainer-notes.md"),
      "unrelated uncommitted note\n",
      "utf8",
    );
    const applied = await syncUpstream({
      mode: "apply",
      packageRoot: promotion.kitRoot,
      pluginRoot: promotion.pluginRoot,
      sourceRoot: promotion.sourceRoot,
      revision: promotion.revision,
      planDigest: plan.planDigest,
    });
    expect(applied.status).toBe("applied");
    expect(applied.dirtyPreflight.dirty).toBe(false);
  }, 60_000);

  it("Scenario: Codex 运行时策略泄漏只检查三个 AGENTS 投影目标", async () => {
    const projectSourceRelative =
      "vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/templates/agents/AGENTS.project.md";

    const leaking = await fixture();
    const markdown = await readFile(
      join(leaking, projectSourceRelative),
      "utf8",
    );
    const sliceStart = markdown.indexOf("## Trellis\n");
    const sliceEnd = markdown.indexOf("\n## ", sliceStart + 1);
    const excludedSlice = markdown.slice(sliceStart, sliceEnd).trimEnd();
    expect(excludedSlice.length).toBeGreaterThan(0);
    const overlayPath = join(leaking, "overlays", "AGENTS.project-omp.md");
    await writeFile(
      overlayPath,
      `${await readFile(overlayPath, "utf8")}\n\n${excludedSlice}\n`,
      "utf8",
    );
    await expect(
      generateKit({
        packageRoot: leaking,
        outputDirectory: join(leaking, "generated"),
      }),
    ).rejects.toMatchObject({
      code: "SECTION_LEAKAGE",
      details: {
        target: "AGENTS.project-omp.md",
        policy: "replace-with-overlay",
      },
    });

    const legitimate = await fixture();
    const output = join(legitimate, "generated");
    await generateKit({ packageRoot: legitimate, outputDirectory: output });
    const runtimeTemplate = await readFile(
      join(output, "onboard/runtime/templates/agents/AGENTS.project.md"),
      "utf8",
    );
    expect(runtimeTemplate).toContain("## Trellis Channel");
    expect(runtimeTemplate).toContain("### 主动 Preflight 场景");
    const projectTarget = await readFile(
      join(output, "AGENTS.project-root.md"),
      "utf8",
    );
    expect(projectTarget).not.toContain("## Trellis Channel");
    const ompTarget = await readFile(
      join(output, "AGENTS.project-omp.md"),
      "utf8",
    );
    expect(ompTarget).toContain("### 主动 Preflight 场景");
  }, 60_000);

  it("Scenario: 默认 stable/auto 安装不访问 Git 或网络", async () => {
    const copyRuntimeSource = async (): Promise<string> => {
      const root = await mkdtemp(join(tmpdir(), "kpi-runtime-source-"));
      temporaryRoots.push(root);
      const sourceRoot = join(root, "upstream");
      await cp(
        join(packageRoot, "vendor", "sbtd-workflow-kit-upstream"),
        sourceRoot,
        { recursive: true },
      );
      return sourceRoot;
    };
    const onboardScript = (sourceRoot: string): string =>
      join(sourceRoot, "sbtd-workflow-onboard", "scripts", "onboard.py");

    const stableFirstSource = await copyRuntimeSource();
    const proof = await proveStableInstallPolicy(stableFirstSource);
    expect(proof.auto).toMatchObject({
      sourceUsed: "stable",
      stableSet: STABLE_SET,
    });
    expect(proof.stable).toMatchObject({
      sourceUsed: "stable",
      stableSet: STABLE_SET,
    });
    expect(proof.gitInvocations).toEqual([]);
    expect(proof.upstreamInvokedGit).toBe(true);
    expect(proof.upstreamRejectedWithoutFallback).toBe(true);

    const networkFirstSource = await copyRuntimeSource();
    const script = onboardScript(networkFirstSource);
    const onboard = await readFile(script, "utf8");
    const stableFirstAnchor = 'if requested_source in {"auto", "stable"}';
    expect(onboard).toContain(stableFirstAnchor);
    await writeFile(
      script,
      onboard.replace(stableFirstAnchor, 'if requested_source == "stable"'),
      "utf8",
    );
    await expect(
      proveStableInstallPolicy(networkFirstSource),
    ).rejects.toMatchObject({ code: "STABLE_INSTALL_POLICY_INVALID" });
  }, 120_000);

  it("Scenario: 绑定未来 revision 的 Section 分类不影响当前锁定生成", async () => {
    const root = await fixture();
    const mappingPath = join(root, "agents-section-map.yaml");
    const parsed = parseYaml(await readFile(mappingPath, "utf8")) as {
      sections: Record<string, unknown>[];
    };
    expect(parsed.sections).toContainEqual({
      source:
        "sbtd-workflow-onboard/templates/agents/AGENTS.global.md::Codex 全局规则 > 工具可用性判断 > Trellis 调度边界",
      policy: "include",
      owner: "global",
    });
    expect(parsed.sections).toContainEqual({
      source:
        "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则 > Trellis 调度层",
      policy: "replace-with-overlay",
      owner: "project-omp",
      overlay: "AGENTS.project-omp.md",
    });

    // An entry gated to a revision that is not pinned is ignored entirely:
    // even a key absent from the current source does not reject generation.
    const futureSection =
      "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::不存在的未来 Section";
    await writeFile(
      mappingPath,
      `${await readFile(mappingPath, "utf8")}  - source: "${futureSection}"\n    policy: omit\n    reason: "future fixture"\n    introducedRevision: "0000000000000000000000000000000000000000"\n`,
      "utf8",
    );
    const output = join(root, "generated");
    const gatedResult = await generateKit({
      packageRoot: root,
      outputDirectory: output,
    });

    const stripped = await fixture();
    const strippedMapping = parseYaml(
      await readFile(join(stripped, "agents-section-map.yaml"), "utf8"),
    ) as { schemaVersion: number; sections: Record<string, unknown>[] };
    strippedMapping.sections = strippedMapping.sections.filter(
      (entry) => entry.source !== futureSection,
    );
    await writeFile(
      join(stripped, "agents-section-map.yaml"),
      stringifyYaml(strippedMapping),
      "utf8",
    );
    const strippedOutput = join(stripped, "generated");
    const strippedResult = await generateKit({
      packageRoot: stripped,
      outputDirectory: strippedOutput,
    });

    expect(gatedResult.manifest).toEqual(strippedResult.manifest);
    for (const target of gatedResult.targets) {
      expect(await readFile(join(output, target), "utf8")).toBe(
        await readFile(join(strippedOutput, target), "utf8"),
      );
    }
    expect(gatedResult.syncReport.generatedSha256).toBe(
      strippedResult.syncReport.generatedSha256,
    );
    expect(gatedResult.syncReport.inputReadSet.mappingSha256).not.toBe(
      strippedResult.syncReport.inputReadSet.mappingSha256,
    );
  });

  it("Scenario: 绑定当前 revision 的未知 Section 分类仍然失败", async () => {
    const root = await fixture();
    const mappingPath = join(root, "agents-section-map.yaml");
    const lock = JSON.parse(
      await readFile(join(root, "upstream.lock.json"), "utf8"),
    ) as { resolvedRevision: string };
    const pinnedUnknown =
      "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::不存在的当前 Section";
    await writeFile(
      mappingPath,
      `${await readFile(mappingPath, "utf8")}  - source: "${pinnedUnknown}"\n    policy: omit\n    reason: "pinned fixture"\n    introducedRevision: "${lock.resolvedRevision}"\n`,
      "utf8",
    );

    await expect(
      generateKit({
        packageRoot: root,
        outputDirectory: join(root, "generated"),
      }),
    ).rejects.toMatchObject({
      code: "SECTION_MAPPING_UNKNOWN",
      details: {
        unknown: [pinnedUnknown],
        syncReport: { removed: [pinnedUnknown] },
      },
    });
  });

  const canonicalSourceRoot = process.env.KPI_PROMOTION_SOURCE_ROOT;
  it.skipIf(canonicalSourceRoot === undefined)(
    "Scenario: 提升以精确 HEAD Git 对象为来源",
    async () => {
      const promotion = await promotionFixture();
      const before = await promotionState(
        promotion.kitRoot,
        promotion.pluginRoot,
      );

      const plan = await syncUpstream({
        mode: "plan",
        packageRoot: promotion.kitRoot,
        pluginRoot: promotion.pluginRoot,
        sourceRoot: canonicalSourceRoot as string,
        revision: HEAD_REVISION,
      });

      expect(plan.status).toBe("planned");
      expect(plan.resolvedRevision).toBe(HEAD_REVISION);
      expect(plan.stableProvenance).toMatchObject({
        stableSet: HEAD_STABLE_SET,
        manifestSha256: HEAD_STABLE_MANIFEST_SHA256,
      });
      expect(
        plan.stableProvenance.repositories["mattpocock-skills"],
      ).toMatchObject({
        revision: HEAD_MATTPOCOCK_REVISION,
        license: "MIT",
      });
      expect(plan.classifiedSections).toContainEqual({
        source:
          "sbtd-workflow-onboard/templates/agents/AGENTS.project.md::Codex 项目级规则 > Trellis 调度层",
        policy: "replace-with-overlay",
      });
      expect(plan.classifiedSections).toContainEqual({
        source:
          "sbtd-workflow-onboard/templates/agents/AGENTS.global.md::Codex 全局规则 > 工具可用性判断 > Trellis 调度边界",
        policy: "include",
      });
      expect(plan.stagedPluginValidated).toBe(true);
      expect(
        await promotionState(promotion.kitRoot, promotion.pluginRoot),
      ).toEqual(before);
    },

    120_000,
  );

  it.skipIf(canonicalSourceRoot === undefined)(
    "Scenario: v1.0.6 Git 对象仍保持 stable-first 安装",
    async () => {
      const stableFirstSnapshot = await mkdtemp(
        join(tmpdir(), "kpi-v106-stable-policy-"),
      );
      temporaryRoots.push(stableFirstSnapshot);
      const archivePath = join(stableFirstSnapshot, "v1.0.6.tar");
      const { stdout: archive } = await execFileAsync(
        "git",
        [
          "-C",
          canonicalSourceRoot as string,
          "archive",
          "--format=tar",
          V106_REVISION,
        ],
        { encoding: "buffer", maxBuffer: 64 * 1024 * 1024 },
      );
      await writeFile(archivePath, archive);
      await execFileAsync("tar", [
        "-xf",
        archivePath,
        "-C",
        stableFirstSnapshot,
      ]);
      const stablePolicy = await proveStableInstallPolicy(stableFirstSnapshot);
      expect(stablePolicy.auto).toMatchObject({
        sourceUsed: "stable",
        stableSet: "2026-08-03.1",
      });
      expect(stablePolicy.stable).toMatchObject({
        sourceUsed: "stable",
        stableSet: "2026-08-03.1",
      });
      expect(stablePolicy.gitInvocations).toEqual([]);
      expect(stablePolicy.upstreamRejectedWithoutFallback).toBe(true);
    },

    120_000,
  );
});
