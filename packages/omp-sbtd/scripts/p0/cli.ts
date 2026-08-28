import { createHash } from "node:crypto";
import type { Stats } from "node:fs";
import { lstat, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { createAuthorizedHostCommandAdapter } from "./authorized-host-adapter.ts";
import type {
  CompatibilityManifest,
  OmpProcessAdapter,
  PackedPackageFile,
} from "./release-validator.ts";
import {
  assertCandidateSourceTree,
  assertOmpDistributionClean,
  candidateIdentitySha256,
  candidateTechnicalCatalog,
  checkTechnicalConformance,
  createBlockedCompatibilityAdapter,
  createEvidenceStore,
  createNodeProcessRunner,
  createUnavailableOmpProcessAdapter,
  decideRelease,
  inspectPackedPluginTarball,
  loadConformanceCatalog,
  loadValueStudyCorpusBundle,
  P0ValidationError,
  preflightValueStudy,
  resolveDevelopmentRuntimeVersionFromLockfile,
  runCompleteValueStudy,
  runIdSchema,
  runTestedRuntimeCompatibility,
  runtimeVersionSchema,
  scanOmpDistributionLeaks,
  validateCompatibilityManifest,
  valueStudyRubricSha256,
  verifyEmbeddedKitReleaseIntegrity,
  verifyEvidenceSnapshot,
  verifyPackedPackageContents,
  verifyPackedPackageMetadata,
  verifyPluginReleaseArtifacts,
} from "./release-validator.ts";

const workspaceRoot = fileURLToPath(new URL("../../../..", import.meta.url));
const validationRoot = join(workspaceRoot, "packages/omp-sbtd/validation/p0");
const configuredEvidenceRoot = process.env.KPI_P0_EVIDENCE_ROOT;
const evidenceRoot = resolve(
  configuredEvidenceRoot ?? join(validationRoot, "evidence"),
);
const temporaryRoot = join(workspaceRoot, ".tmp/kpi-p0");
const commands = new Set([
  "check-catalog",
  "check-technical",
  "check-compatibility",
  "check-package",
  "run-value-study",
  "score-value-study",
  "decide-candidate",
  "decide-release",
  "record-candidate",
  "record-candidate-evidence",
  "all",
]);

function parseArguments(argv: readonly string[]): {
  readonly command: string;
  readonly options: Readonly<Record<string, string>>;
} {
  const [command, ...rest] = argv;
  const options: Record<string, string> = {};
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index];
    if (token === undefined || !token.startsWith("--"))
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Unexpected P0 validator argument: ${token}`,
        "Use only documented --name value options.",
      );
    const value = rest[index + 1];
    if (value === undefined || value.startsWith("--"))
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Missing value for ${token}`,
        "Supply a value for every P0 validator option.",
      );
    options[token.slice(2)] = value;
    index += 1;
  }
  if (command === undefined || !commands.has(command))
    throw new P0ValidationError(
      "CLI_COMMAND_INVALID",
      "P0 validator command is missing or unsupported.",
      "Use check-catalog, check-technical, check-compatibility, check-package, run-value-study, score-value-study, record-candidate, record-candidate-evidence, decide-candidate, decide-release, or all.",
    );
  return { command, options };
}

function requiredOption(
  options: Readonly<Record<string, string>>,
  name: string,
): string {
  const value = options[name];
  if (value !== undefined) return value;
  throw new P0ValidationError(
    "CLI_ARGUMENT_INVALID",
    `Missing required --${name} option.`,
    `Supply --${name} with an explicit non-sensitive value.`,
  );
}

function requiredRunId(options: Readonly<Record<string, string>>): string {
  const parsed = runIdSchema.safeParse(requiredOption(options, "run-id"));
  if (parsed.success) return parsed.data;
  throw new P0ValidationError(
    "CLI_ARGUMENT_INVALID",
    "P0 --run-id must be a safe lowercase stable identifier.",
    "Use a lowercase run ID with letters, digits, and hyphens only.",
  );
}

async function resolveTestedRuntimeVersion(
  options: Readonly<Record<string, string>>,
): Promise<string> {
  const explicit = options["runtime-version"];
  if (explicit !== undefined) return explicit;
  return resolveDevelopmentRuntimeVersionFromLockfile(
    await readFile(join(workspaceRoot, "pnpm-lock.yaml"), "utf8"),
  );
}

type CompatibilityScope = "declared" | "experimental";

type CompatibilityInvocation = Readonly<{
  manifest: CompatibilityManifest;
  scope: CompatibilityScope;
  declaredRuntimeVersion: string;
  testedRuntimeVersion: string;
  pluginPackagePath: string;
  pluginTarballPath: string;
  pluginInput: "packed";
}>;

function parseRuntimeVersion(value: string, optionName: string): string {
  const parsed = runtimeVersionSchema.safeParse(value);
  if (parsed.success) return parsed.data;
  throw new P0ValidationError(
    "CLI_ARGUMENT_INVALID",
    `P0 --${optionName} must be an exact semantic version.`,
    `Supply --${optionName} as an exact semantic version such as 17.1.8.`,
  );
}

async function resolvePackedPluginPath(packed: string): Promise<string> {
  if (!isAbsolute(packed))
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 --packed must be an absolute extracted Plugin package directory.",
      "Extract the package and pass its absolute package directory through --packed.",
    );
  const path = resolve(packed);
  try {
    const [directory, packageJson] = await Promise.all([
      lstat(path),
      lstat(join(path, "package.json")),
    ]);
    if (
      !directory.isDirectory() ||
      directory.isSymbolicLink() ||
      !packageJson.isFile() ||
      packageJson.isSymbolicLink()
    )
      throw new Error("invalid packed Plugin directory");
  } catch {
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 --packed must reference an extracted Plugin package directory with a regular package.json.",
      "Extract the package to a regular directory and pass that absolute directory through --packed.",
    );
  }
  return path;
}

async function resolvePackedTarballPath(tarball: string): Promise<string> {
  if (!isAbsolute(tarball))
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 --tarball must be an absolute regular candidate tarball.",
      "Pass the exact absolute tarball used to produce the extracted Plugin package.",
    );
  const path = resolve(tarball);
  try {
    const details = await lstat(path);
    if (!details.isFile() || details.isSymbolicLink())
      throw new Error("invalid candidate tarball");
  } catch {
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 --tarball must reference one regular non-symbolic candidate tarball.",
      "Pass the exact tarball file through --tarball.",
    );
  }
  return path;
}

async function resolveCompatibilityInvocation(
  options: Readonly<Record<string, string>>,
): Promise<CompatibilityInvocation> {
  const manifest = validateCompatibilityManifest(
    JSON.parse(
      await readFile(join(validationRoot, "compatibility.v2.json"), "utf8"),
    ),
  );
  const experimentalRuntime = options["experimental-runtime"];
  if (
    experimentalRuntime !== undefined &&
    options["runtime-version"] === undefined
  )
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 --experimental-runtime requires --runtime-version.",
      "Pass one matching exact version through both --experimental-runtime and --runtime-version.",
    );
  const testedRuntimeVersion = parseRuntimeVersion(
    await resolveTestedRuntimeVersion(options),
    "runtime-version",
  );
  const packed = requiredOption(options, "packed");
  const pluginInput = "packed" as const;
  const pluginPackagePath = await resolvePackedPluginPath(packed);
  const pluginTarballPath = await resolvePackedTarballPath(
    requiredOption(options, "tarball"),
  );
  if (experimentalRuntime === undefined)
    return {
      manifest,
      scope: "declared",
      declaredRuntimeVersion: manifest.developmentRuntimeVersion,
      testedRuntimeVersion,
      pluginPackagePath,
      pluginTarballPath,
      pluginInput,
    };

  const parsedExperimentalRuntime = parseRuntimeVersion(
    experimentalRuntime,
    "experimental-runtime",
  );
  if (parsedExperimentalRuntime !== testedRuntimeVersion)
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 --experimental-runtime must exactly match --runtime-version.",
      "Pass the same exact semantic version through both experimental Runtime options.",
      {
        experimentalRuntime: parsedExperimentalRuntime,
        testedRuntimeVersion,
      },
    );
  // Both declared and experimental host certification run only against one
  // extracted package plus its exact parent-authorized tarball. The
  // experimental scope never mutates the packaged Policy v2.
  return {
    manifest,
    scope: "experimental",
    declaredRuntimeVersion: manifest.developmentRuntimeVersion,
    testedRuntimeVersion,
    pluginPackagePath,
    pluginTarballPath,
    pluginInput,
  };
}

function hasValueStudyPreflightOptions(
  options: Readonly<Record<string, string>>,
): boolean {
  return ["execution-model", "judge-model", "runtime-version"].some(
    (name) => options[name] !== undefined,
  );
}

async function observeValueStudy(
  options: Readonly<Record<string, string>>,
  adapter: OmpProcessAdapter,
  requirePreflight: boolean,
) {
  if (!requirePreflight && !hasValueStudyPreflightOptions(options))
    return {
      schemaVersion: 1,
      status: "blocked" as const,
      blocker: {
        code: "VALUE_STUDY_EXECUTION_REQUIRED",
        reason:
          "No complete 40-arm, 20-pair value study was requested by this aggregate check.",
        recovery:
          "Run the parent-authorized paired execution with explicit execution-model, judge-model, and runtime-version options.",
      },
    };
  const preflight = await preflightValueStudy(adapter, {
    executionModelId: requiredOption(options, "execution-model"),
    judgeModelId: requiredOption(options, "judge-model"),
    runtimeVersion: requiredOption(options, "runtime-version"),
  });
  if (preflight.status === "blocked") return preflight;
  return {
    schemaVersion: 1,
    status: "blocked" as const,
    preflight,
    blocker: {
      code: "VALUE_STUDY_EXECUTION_REQUIRED",
      reason:
        "A ready preflight does not prove the required 40-arm, 20-pair value study.",
      recovery:
        "Run the parent-authorized paired execution, independent judging, scoring, and immutable evidence promotion.",
    },
  };
}

function contentSha256(content: Uint8Array): string {
  return createHash("sha256").update(content).digest("hex");
}

async function runAuthorizedValueStudy(
  options: Readonly<Record<string, string>>,
  adapter: OmpProcessAdapter | undefined,
) {
  if (adapter === undefined)
    return observeValueStudy(
      options,
      createUnavailableOmpProcessAdapter(),
      true,
    );
  const runId = requiredRunId(options);
  const execution = {
    runtimeVersion: requiredOption(options, "runtime-version"),
    modelId: requiredOption(options, "execution-model"),
  };
  const judge = { modelId: requiredOption(options, "judge-model") };
  const corpusPath = join(validationRoot, "value-study/corpus.v1.json");
  const catalogPath = join(validationRoot, "conformance-matrix.v1.json");
  const [catalogBytes, corpusBytes, study, source] = await Promise.all([
    readFile(catalogPath),
    readFile(corpusPath),
    loadValueStudyCorpusBundle(corpusPath, validationRoot),
    verifyPluginReleaseArtifacts({
      workspaceRoot,
      pluginRoot: join(workspaceRoot, "packages/omp-sbtd"),
      kitRoot: join(workspaceRoot, "packages/sbtd-workflow-kit"),
    }),
  ]);
  const store = createEvidenceStore({ evidenceRoot, temporaryRoot });
  const result = await runCompleteValueStudy(adapter, store, {
    runId,
    sourceTreeSha256: source.sourceTreeSha256,
    catalogSha256: contentSha256(catalogBytes),
    corpusSha256: contentSha256(corpusBytes),
    rubricSha256: valueStudyRubricSha256(study.fixtures),
    technicalStatus: "blocked",
    corpus: study.corpus,
    fixtures: study.fixtures,
    execution,
    judge,
  });
  if (result.run === undefined) return result;
  const latest = await store.promote(result.run);
  return {
    ...result,
    latest,
    releaseDecision: result.run.releaseDecision,
  };
}

async function collectPackedPackageFiles(
  root: string,
  prefix = "package",
): Promise<readonly PackedPackageFile[]> {
  const packedFiles: PackedPackageFile[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    const packedPath = `${prefix}/${entry.name}`;
    if (entry.isSymbolicLink())
      throw new P0ValidationError(
        "PACKAGE_CONTENT_INVALID",
        `Packed Plugin contains a symbolic link: ${packedPath}`,
        "Replace symbolic links with regular package files before inspection.",
      );
    if (entry.isDirectory()) {
      packedFiles.push(...(await collectPackedPackageFiles(path, packedPath)));
      continue;
    }
    if (!entry.isFile())
      throw new P0ValidationError(
        "PACKAGE_CONTENT_INVALID",
        `Packed Plugin contains a non-regular entry: ${packedPath}`,
        "Package only regular files and directories.",
      );
    const [content, stat] = await Promise.all([readFile(path), lstat(path)]);
    packedFiles.push({
      path: packedPath,
      sha256: createHash("sha256").update(content).digest("hex"),
      executable: (stat.mode & 0o111) !== 0,
    });
  }
  return packedFiles;
}

function reportMarkdown(
  command: string,
  status: string,
  report: unknown,
): string {
  return [
    `# P0 发布校验报告 — ${command}`,
    "",
    `- 状态：${status}`,
    "- Evidence Source: developer-local",
    "- Evidence Publication: local-only",
    "",
    "## 机器可读结果",
    "",
    "```json",
    JSON.stringify(report, null, 2),
    "```",
    "",
  ].join("\n");
}

function isWithinReportRoot(path: string): boolean {
  return [temporaryRoot, evidenceRoot].some((root) => {
    const fromRoot = relative(root, path);
    return (
      fromRoot === "" ||
      (!fromRoot.startsWith(`..${sep}`) &&
        fromRoot !== ".." &&
        !isAbsolute(fromRoot))
    );
  });
}

function isWithinTemporaryRoot(path: string): boolean {
  const fromRoot = relative(temporaryRoot, path);
  return (
    fromRoot === "" ||
    (!fromRoot.startsWith(`..${sep}`) &&
      fromRoot !== ".." &&
      !isAbsolute(fromRoot))
  );
}
function assertConfiguredEvidenceRoot(): void {
  if (
    configuredEvidenceRoot === undefined ||
    isWithinTemporaryRoot(evidenceRoot)
  )
    return;
  throw new P0ValidationError(
    "CLI_ARGUMENT_INVALID",
    "An overridden P0 evidence root must stay below the local temporary directory.",
    "Use the canonical evidence root or an isolated directory below .tmp/kpi-p0.",
  );
}

async function readTemporaryRegularFile(
  options: Readonly<Record<string, string>>,
  optionName: string,
): Promise<Readonly<{ path: string; bytes: Buffer }>> {
  const path = resolve(requiredOption(options, optionName));
  if (!isWithinTemporaryRoot(path))
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 candidate artifacts must stay below the local temporary evidence directory.",
      "Place the extracted package and tarball below .tmp/kpi-p0 and retry.",
    );
  let stat: Stats;
  try {
    stat = await lstat(path);
  } catch {
    throw new P0ValidationError(
      "CLI_CANDIDATE_ARTIFACT_INVALID",
      "P0 candidate artifact is unavailable.",
      "Provide one regular tarball below .tmp/kpi-p0 and retry.",
    );
  }
  if (!stat.isFile() || stat.isSymbolicLink())
    throw new P0ValidationError(
      "CLI_CANDIDATE_ARTIFACT_INVALID",
      "P0 candidate tarball must be a regular non-symbolic file.",
      "Provide one regular tarball below .tmp/kpi-p0 and retry.",
    );
  return { path, bytes: await readFile(path) };
}

async function assertTarballMatchesPackedPackage(
  tarballBytes: Buffer,
  packedRoot: string,
): Promise<void> {
  const inspection = inspectPackedPluginTarball(tarballBytes);
  assertOmpDistributionClean(inspection.leaks);
  const tarballFiles: PackedPackageFile[] = [];
  for (const member of inspection.members) {
    if (member.kind !== "file") continue;
    if (member.sha256 === undefined)
      throw new P0ValidationError(
        "CANDIDATE_TARBALL_INVALID",
        "Candidate tarball member is missing its digest.",
        "Rebuild the packed Plugin tarball and retry.",
      );
    tarballFiles.push({
      path: member.path,
      sha256: member.sha256,
      executable: member.executable,
    });
  }
  const packedFiles = await collectPackedPackageFiles(packedRoot);
  const map = (files: readonly PackedPackageFile[]) =>
    JSON.stringify(
      [...files]
        .sort((left, right) => left.path.localeCompare(right.path))
        .map((file) => [file.path, file.sha256, file.executable]),
    );
  if (map(tarballFiles) !== map(packedFiles))
    throw new P0ValidationError(
      "CANDIDATE_TARBALL_MISMATCH",
      "Candidate tarball bytes do not match the inspected extracted package.",
      "Extract the exact supplied tarball and rerun candidate admission.",
    );
}

async function writePairedReport(
  outputPath: string,
  command: string,
  status: string,
  report: unknown,
): Promise<void> {
  const target = resolve(outputPath);
  const stem = target.endsWith(".json") ? target.slice(0, -5) : target;
  if (!isWithinReportRoot(`${stem}.json`) || !isWithinReportRoot(`${stem}.md`))
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 report outputs must stay below the local evidence or temporary directory.",
      "Pass an output path below the local evidence or temporary directory.",
    );
  await mkdir(dirname(stem), { recursive: true });
  await Promise.all([
    writeFile(`${stem}.json`, `${JSON.stringify(report, null, 2)}\n`, "utf8"),
    writeFile(`${stem}.md`, reportMarkdown(command, status, report), "utf8"),
  ]);
}

async function currentPackedCandidate(
  options: Readonly<Record<string, string>>,
) {
  const packedRoot = resolve(requiredOption(options, "packed"));
  if (!isWithinTemporaryRoot(packedRoot))
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "P0 extracted candidate package must stay below the local temporary evidence directory.",
      "Extract the packed Plugin below .tmp/kpi-p0 and retry.",
    );
  let packedStat: Stats;
  try {
    packedStat = await lstat(packedRoot);
  } catch {
    throw new P0ValidationError(
      "CLI_CANDIDATE_ARTIFACT_INVALID",
      "P0 extracted candidate package is unavailable.",
      "Extract the packed Plugin below .tmp/kpi-p0 and retry.",
    );
  }
  if (!packedStat.isDirectory() || packedStat.isSymbolicLink())
    throw new P0ValidationError(
      "CLI_CANDIDATE_ARTIFACT_INVALID",
      "P0 extracted candidate package must be a non-symbolic directory.",
      "Extract the packed Plugin below .tmp/kpi-p0 and retry.",
    );
  const tarball = await readTemporaryRegularFile(options, "tarball");
  await assertTarballMatchesPackedPackage(tarball.bytes, packedRoot);
  const packageResult = await runCommand("check-package", options);
  if (packageResult.status !== "passed")
    throw new P0ValidationError(
      "CANDIDATE_PACKAGE_EVIDENCE_REQUIRED",
      "Current packed-package inspection did not pass for the candidate.",
      "Correct the packed Plugin and rerun the package inspection before recording the candidate.",
    );
  const [artifacts, sourcePackage] = await Promise.all([
    verifyPluginReleaseArtifacts({
      workspaceRoot,
      pluginRoot: join(workspaceRoot, "packages/omp-sbtd"),
      kitRoot: join(workspaceRoot, "packages/sbtd-workflow-kit"),
    }),
    readFile(join(workspaceRoot, "packages/omp-sbtd/package.json"), "utf8"),
  ]);
  let manifestSource: unknown;
  try {
    manifestSource = JSON.parse(sourcePackage);
  } catch {
    throw new P0ValidationError(
      "CANDIDATE_PACKAGE_EVIDENCE_REQUIRED",
      "Current Plugin package metadata is not valid JSON.",
      "Restore the Plugin package manifest and rerun package inspection.",
    );
  }
  if (
    manifestSource === null ||
    typeof manifestSource !== "object" ||
    !("name" in manifestSource) ||
    !("version" in manifestSource)
  )
    throw new P0ValidationError(
      "CANDIDATE_PACKAGE_EVIDENCE_REQUIRED",
      "Current Plugin package metadata has no candidate identity.",
      "Restore the Plugin package manifest and rerun package inspection.",
    );
  return {
    candidate: {
      sourceTreeSha256: artifacts.sourceTreeSha256,
      packedTarballSha256: createHash("sha256")
        .update(tarball.bytes)
        .digest("hex"),
      packageName: manifestSource.name,
      packageVersion: manifestSource.version,
    },
    packageReport: packageResult.report,
  };
}

async function currentSourceTreeSha256(): Promise<string> {
  return (
    await verifyPluginReleaseArtifacts({
      workspaceRoot,
      pluginRoot: join(workspaceRoot, "packages/omp-sbtd"),
      kitRoot: join(workspaceRoot, "packages/sbtd-workflow-kit"),
    })
  ).sourceTreeSha256;
}

async function checkCandidateTechnicalConformance() {
  const catalog = await loadConformanceCatalog(
    join(validationRoot, "conformance-matrix.v1.json"),
    workspaceRoot,
  );
  const scope = candidateTechnicalCatalog(catalog);
  const report = await checkTechnicalConformance(
    scope.catalog,
    workspaceRoot,
    createNodeProcessRunner(),
  );
  return {
    status: report.entries.every((entry) => entry.status === "passed")
      ? "passed"
      : "blocked",
    report: {
      schemaVersion: 1,
      scope: "candidate-automated-v1",
      entries: report.entries,
      excludedExternalEntryIds: scope.excludedExternalEntryIds,
    },
  };
}

async function runCommand(
  command: string,
  options: Readonly<Record<string, string>>,
): Promise<Readonly<{ status: string; report: unknown }>> {
  assertConfiguredEvidenceRoot();
  const catalogPath = join(validationRoot, "conformance-matrix.v1.json");
  if (command === "check-catalog") {
    const catalog = await loadConformanceCatalog(catalogPath, workspaceRoot);
    return {
      status: "passed",
      report: {
        schemaVersion: 1,
        status: "passed",
        entries: catalog.entries.map((entry) => ({
          id: entry.id,
          evidenceRequirement: entry.evidenceRequirement,
        })),
      },
    };
  }
  if (command === "check-technical") {
    const catalog = await loadConformanceCatalog(catalogPath, workspaceRoot);
    const report = await checkTechnicalConformance(
      catalog,
      workspaceRoot,
      createNodeProcessRunner(),
    );
    return {
      status: report.entries.every((entry) => entry.status === "passed")
        ? "passed"
        : report.entries.some((entry) => entry.status === "failed")
          ? "failed"
          : "blocked",
      report,
    };
  }
  if (command === "check-compatibility") {
    const invocation = await resolveCompatibilityInvocation(options);
    const hostAdapter = await createAuthorizedHostCommandAdapter();
    const report = await runTestedRuntimeCompatibility(
      invocation.manifest,
      hostAdapter ?? createBlockedCompatibilityAdapter(),
      {
        pluginPackagePath: invocation.pluginPackagePath,
        pluginTarballPath: invocation.pluginTarballPath,
        sandboxRoot: join(
          temporaryRoot,
          "compatibility",
          requiredRunId(options),
        ),
        testedRuntimeVersion: invocation.testedRuntimeVersion,
        scope: invocation.scope,
      },
    );
    return {
      status: report.result.status,
      report: {
        ...report,
        compatibility: {
          scope: invocation.scope,
          declaredRuntimeVersion: invocation.declaredRuntimeVersion,
          testedRuntimeVersion: invocation.testedRuntimeVersion,
          pluginInput: invocation.pluginInput,
        },
      },
    };
  }
  if (command === "check-package") {
    const report = await verifyPluginReleaseArtifacts({
      workspaceRoot,
      pluginRoot: join(workspaceRoot, "packages/omp-sbtd"),
      kitRoot: join(workspaceRoot, "packages/sbtd-workflow-kit"),
    });
    const packedRoot = options.packed;
    if (packedRoot === undefined)
      return {
        status: "blocked",
        report: {
          ...report,
          blocker: {
            code: "PACKED_TARBALL_REQUIRED",
            recovery:
              "Pack the built Plugin, extract the tarball into an isolated directory, and pass its package directory through --packed.",
          },
        },
      };
    const [sbom, sourcePackage, kitPackage, packedPackageRoot] =
      await Promise.all([
        readFile(
          join(workspaceRoot, "packages/omp-sbtd/SBOM.spdx.json"),
          "utf8",
        ),
        readFile(join(workspaceRoot, "packages/omp-sbtd/package.json"), "utf8"),
        readFile(
          join(workspaceRoot, "packages/sbtd-workflow-kit/package.json"),
          "utf8",
        ),
        Promise.resolve(resolve(packedRoot)),
      ]);
    const packedPackage = await readFile(
      join(packedPackageRoot, "package.json"),
      "utf8",
    );
    assertOmpDistributionClean(
      await scanOmpDistributionLeaks(packedPackageRoot),
    );
    await verifyEmbeddedKitReleaseIntegrity({
      kitRoot: join(packedPackageRoot, "kit"),
    });
    const parsedSbom = JSON.parse(sbom) as {
      files: readonly {
        fileName: string;
        checksums: readonly { algorithm: string; checksumValue: string }[];
      }[];
    };
    verifyPackedPackageContents(
      parsedSbom.files.map((file) => ({
        path: file.fileName.replace(/^\.\//, ""),
        sha256:
          file.checksums.find((checksum) => checksum.algorithm === "SHA256")
            ?.checksumValue ?? "",
      })),
      await collectPackedPackageFiles(packedPackageRoot),
      report.sbomSha256,
    );
    verifyPackedPackageMetadata(
      JSON.parse(sourcePackage),
      JSON.parse(packedPackage),
      { "@kunolu/sbtd-workflow-kit": JSON.parse(kitPackage) },
    );
    return {
      status: "passed",
      report: { ...report, packedFileCount: parsedSbom.files.length + 2 },
    };
  }
  if (command === "run-value-study") {
    const report = await runAuthorizedValueStudy(
      options,
      await createAuthorizedHostCommandAdapter(),
    );
    return { status: report.status, report };
  }
  if (command === "score-value-study")
    return {
      status: "blocked",
      report: {
        schemaVersion: 1,
        status: "blocked",
        blocker: {
          code: "VALUE_STUDY_EXECUTION_REQUIRED",
          reason:
            "Caller-supplied score input cannot establish completed value-study provenance.",
          recovery:
            "Run the parent-authorized paired execution, independent judging, scoring, and immutable evidence promotion.",
        },
      },
    };
  if (command === "record-candidate") {
    const store = createEvidenceStore({ evidenceRoot, temporaryRoot });
    const current = await currentPackedCandidate(options);
    const record = await store.recordCandidate({
      schemaVersion: 1,
      candidate: current.candidate,
      channel: "rc",
      distTag: requiredOption(options, "dist-tag"),
      createdAt: requiredOption(options, "created-at"),
    });
    return {
      status: "passed",
      report: {
        schemaVersion: 1,
        status: "recorded",
        candidateId: candidateIdentitySha256(record.candidate),
        record,
      },
    };
  }
  if (command === "record-candidate-evidence") {
    const store = createEvidenceStore({ evidenceRoot, temporaryRoot });
    const candidateId = requiredOption(options, "candidate-id");
    const record = await store.readCandidate(candidateId);
    if (record === undefined)
      throw new P0ValidationError(
        "CANDIDATE_MISSING",
        "Candidate-bound evidence requires an immutable candidate admission record.",
        "Record the exact candidate before appending its gate evidence.",
        { candidateId },
      );
    const gate = requiredOption(options, "gate");
    const evidenceId = requiredOption(options, "evidence-id");
    let report: unknown;
    if (gate === "technical") {
      const sourceTreeSha256 = await currentSourceTreeSha256();
      assertCandidateSourceTree(record.candidate, sourceTreeSha256);
      const technical = await checkCandidateTechnicalConformance();
      if (technical.status !== "passed")
        throw new P0ValidationError(
          "CANDIDATE_TECHNICAL_EVIDENCE_REQUIRED",
          "Current executable technical conformance did not pass for the candidate.",
          "Correct every executable candidate technical conformance failure before recording candidate evidence.",
        );
      assertCandidateSourceTree(
        record.candidate,
        await currentSourceTreeSha256(),
      );
      report = { ...technical.report, sourceTreeSha256 };
    } else if (gate === "package") {
      const current = await currentPackedCandidate(options);
      if (
        candidateIdentitySha256(current.candidate) !==
        candidateIdentitySha256(record.candidate)
      )
        throw new P0ValidationError(
          "CANDIDATE_BINDING_MISMATCH",
          "Current packed package does not match the immutable candidate identity.",
          "Rebuild and record evidence for the exact admitted candidate.",
          { candidateId },
        );
      report = current.packageReport;
    } else
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        "P0 candidate evidence gate must be technical or package.",
        "Use --gate technical or --gate package.",
      );
    const evidence = await store.recordCandidateEvidence({
      schemaVersion: 1,
      evidenceId,
      candidate: record.candidate,
      status: "passed",
      recordedAt: requiredOption(options, "recorded-at"),
      reportSha256: createHash("sha256")
        .update(JSON.stringify(report))
        .digest("hex"),
      blockers: [],
      gate,
    });
    return {
      status: "passed",
      report: { schemaVersion: 1, status: "recorded", evidence },
    };
  }
  if (command === "decide-candidate") {
    const store = createEvidenceStore({ evidenceRoot, temporaryRoot });
    const report = await store.decideCandidate(
      requiredOption(options, "candidate-id"),
    );
    return { status: report.decision, report };
  }
  if (command === "decide-release") {
    for (const forbidden of [
      "technical-status",
      "value-gate-status",
      "latest-decision",
    ]) {
      if (options[forbidden] !== undefined)
        throw new P0ValidationError(
          "CLI_ARGUMENT_INVALID",
          `--${forbidden} cannot override immutable release evidence.`,
          "Run the technical and value gates, then decide from the current checksum-verified evidence run.",
        );
    }
    const store = createEvidenceStore({ evidenceRoot, temporaryRoot });
    const latest = await store.readLatest();
    const run =
      latest === undefined
        ? undefined
        : await verifyEvidenceSnapshot(evidenceRoot, latest.runId);
    if (
      latest !== undefined &&
      run !== undefined &&
      latest.sourceTreeSha256 === run.sourceTreeSha256 &&
      run.releaseDecision === "ready" &&
      run.technicalStatus === "passed" &&
      run.valueGateStatus === "passed"
    )
      await store.approveLatest();
    const report = decideRelease({
      sourceTreeSha256: requiredOption(options, "source-tree-sha"),
      technicalStatus: run?.technicalStatus ?? "blocked",
      valueGateStatus: run?.valueGateStatus ?? "blocked",
      latest:
        latest === undefined || run === undefined
          ? undefined
          : {
              runId: latest.runId,
              sourceTreeSha256: latest.sourceTreeSha256,
              releaseDecision: run.releaseDecision,
            },
      approved: await store.readApproval(),
    });
    return { status: report.decision, report };
  }
  const catalog = await loadConformanceCatalog(catalogPath, workspaceRoot);
  const invocation = await resolveCompatibilityInvocation(options);
  const authorizedHostAdapter = await createAuthorizedHostCommandAdapter();
  const compatibility = await runTestedRuntimeCompatibility(
    invocation.manifest,
    authorizedHostAdapter ?? createBlockedCompatibilityAdapter(),
    {
      pluginPackagePath: invocation.pluginPackagePath,
      pluginTarballPath: invocation.pluginTarballPath,
      sandboxRoot: join(temporaryRoot, "compatibility", requiredRunId(options)),
      testedRuntimeVersion: invocation.testedRuntimeVersion,
      scope: invocation.scope,
    },
  );
  const valueStudy = await observeValueStudy(
    options,
    authorizedHostAdapter ?? createUnavailableOmpProcessAdapter(),
    false,
  );
  return {
    status: "blocked",
    report: {
      schemaVersion: 1,
      catalogEntries: catalog.entries.length,
      compatibility: {
        ...compatibility,
        scope: invocation.scope,
        declaredRuntimeVersion: invocation.declaredRuntimeVersion,
        testedRuntimeVersion: invocation.testedRuntimeVersion,
        pluginInput: invocation.pluginInput,
      },
      valueStudy,
      blocker: {
        code: "EXTERNAL_P0_PREREQUISITES_REQUIRED",
        recovery:
          "Run the technical, compatibility, package, and real value-study commands after parent-controlled prerequisites are available.",
      },
    },
  };
}

try {
  const parsed = parseArguments(process.argv.slice(2));
  const result = await runCommand(parsed.command, parsed.options);
  if (parsed.options.out !== undefined)
    await writePairedReport(
      parsed.options.out,
      parsed.command,
      result.status,
      result.report,
    );
  process.stdout.write(`${JSON.stringify(result.report)}\n`);
  if (
    result.status !== "passed" &&
    result.status !== "ready" &&
    result.status !== "rc-eligible"
  )
    process.exitCode = 1;
} catch (error) {
  const normalized =
    error instanceof P0ValidationError
      ? {
          code: error.code,
          message: error.message,
          recovery: error.recovery,
          details: error.details,
        }
      : {
          code: "P0_VALIDATOR_UNEXPECTED_FAILURE",
          message: "The P0 validator stopped before producing a safe result.",
          recovery:
            "Inspect the local report and correct the deterministic validation input.",
        };
  process.stderr.write(`${JSON.stringify(normalized)}\n`);
  process.exitCode = 1;
}
