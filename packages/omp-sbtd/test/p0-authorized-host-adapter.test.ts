import { spawn } from "node:child_process";
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { createAuthorizedHostCommandAdapter } from "../scripts/p0/authorized-host-adapter.ts";
import type { OmpProcessAdapter } from "../scripts/p0/release-validator.ts";
import { acceptanceArtifactSha256 } from "../scripts/p0/release-validator.ts";

const workspaceRoot = fileURLToPath(new URL("../../..", import.meta.url));
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const p0CliPath = join(pluginRoot, "scripts/p0/cli.ts");
const tsxCliPath = join(pluginRoot, "node_modules/tsx/dist/cli.mjs");
const temporaryRoots: string[] = [];

type HarnessBehavior =
  | "valid"
  | "invalid-json"
  | "multiple-json"
  | "sensitive-output"
  | "stderr"
  | "nonzero"
  | "unknown-field"
  | "home-path"
  | "private-path"
  | "workspace-path"
  | "bare-token"
  | "file-uri-path"
  | "hang"
  | "invalid-tokens"
  | "missing-compatibility-proof"
  | "filesystem-drift"
  | "invalid-execute-binding"
  | "invalid-judge-binding"
  | "invalid-judge-rubric-substitution"
  | "invalid-judge-rubric-duplicate"
  | "invalid-judge-rubric-total"
  | "unexpected-profile-mode"
  | "missing-profile-mode"
  | "unclassified-report"
  | "slow-compatibility";

// macOS may inject this non-sensitive encoding variable after Node applies its explicit environment.
function hasAllowedChildEnvironment(
  environment: readonly string[],
  options?: Readonly<{
    compatibilityAgentDirectory?: string;
    pluginTarballPath?: string;
  }>,
): boolean {
  return (
    environment.includes("PATH") &&
    (options?.compatibilityAgentDirectory === undefined ||
      environment.includes("KPI_OMP_COMPAT_AGENT_DIR")) &&
    (options?.pluginTarballPath === undefined ||
      environment.includes("KPI_OMP_PLUGIN_TARBALL")) &&
    environment.every(
      (key) =>
        key === "PATH" ||
        key === "__CF_USER_TEXT_ENCODING" ||
        (options?.compatibilityAgentDirectory !== undefined &&
          key === "KPI_OMP_COMPAT_AGENT_DIR") ||
        (options?.pluginTarballPath !== undefined &&
          key === "KPI_OMP_PLUGIN_TARBALL"),
    )
  );
}

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-p0-authorized-host-"));
  temporaryRoots.push(root);
  return root;
}

async function writeTrustedHarness(
  root: string,
  capturePath: string,
  behavior: HarnessBehavior,
): Promise<string> {
  const executable = join(root, "trusted-omp-host");
  const source = `#!${process.execPath}
const { appendFileSync } = require("node:fs");
const capturePath = ${JSON.stringify(capturePath)};
const behavior = ${JSON.stringify(behavior)};

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value !== null && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, stable(nested)]),
    );
  return value;
}

function digest(value) {
  return require("node:crypto")
    .createHash("sha256")
    .update(JSON.stringify(stable(value), null, 2) + "\\n")
    .digest("hex");
}

function validResponse(request) {
  if (request.operation === "compatibility")
    return {
      schemaVersion: 1,
      operation: "compatibility",
      result: {
        currentRuntimeVersion: request.input.currentRuntimeVersion,
        status: "passed",
        agentInvoked: false,
        filesystemBeforeSha256: "a".repeat(64),
        filesystemAfterSha256: "a".repeat(64),
        packageSha256: "c".repeat(64),
        ...((process.env.KPI_OMP_COMPAT_AGENT_DIR !== undefined &&
          behavior !== "missing-profile-mode") ||
        behavior === "unexpected-profile-mode"
          ? {
              acceptanceMode: "profile-isolated",
              supportDecision: "requires-separate-support-review",
            }
          : {}),
        commandResults: {
          help: "passed",
          status: "passed",
          report: "passed",
          "onboard plan": "passed",
        },
      },
    };
  if (request.operation === "preflight")
    return {
      schemaVersion: 1,
      operation: "preflight",
      result: {
        status: "ready",
        runtimeVersion: request.input.runtimeVersion,
        executionModelId: request.input.executionModelId,
        judgeModelId: request.input.judgeModelId,
        executionProcessId: "execution-process",
        judgeProcessId: "judge-process",
        supportsUsageEvents: true,
      },
    };
  if (request.operation === "runtime-mode")
    return {
      schemaVersion: 1,
      operation: "runtime-mode",
      result: { status: "ready" },
    };
  if (request.operation === "execute") {
    const acceptanceArtifact = {
      finalResponse: "完成",
      patch: "diff --git a/fixture b/fixture\\n",
      commandOutcomes: [{ command: "fixture-check", status: "passed" }],
    };
    return {
      schemaVersion: 1,
      operation: "execute",
      result: {
        status: "completed",
        runId: request.input.runId,
        fixtureId: request.input.fixture.id,
        arm: request.input.arm,
        attempt: request.input.attempt,
        fixtureSha256: request.input.fixtureSha256,
        executionProcessId: "execution-process",
        events: [
          { kind: "usage", turns: 1, tokens: 2 },
          {
            kind: "report",
            requiredGates: request.input.fixture.expected.requiredGates,
            routeCost: request.input.fixture.expected.routeCost,
          },
          { kind: "terminal", outcome: "completed", finalResponse: "完成" },
        ],
        acceptanceArtifact,
        acceptanceArtifactSha256: digest(acceptanceArtifact),
      },
    };
  }
  const score = {
    total: 80,
    severeAcceptanceFailure: false,
    criteria: request.input.rubric.map((criterion) => ({
      id: criterion.id,
      score: 80,
      reason: "满足固定验收标准",
    })),
  };
  const judgeResult = {
    fixtureId: request.input.fixtureId,
    firstArtifactSha256: request.input.first.artifactSha256,
    secondArtifactSha256: request.input.second.artifactSha256,
    first: score,
    second: {
      ...score,
      criteria: score.criteria.map((criterion) => ({ ...criterion })),
    },
  };
  return {
    schemaVersion: 1,
    operation: "judge",
    result: {
      status: "completed",
      runId: request.input.runId,
      fixtureId: request.input.fixtureId,
      fixtureSha256: request.input.fixtureSha256,
      judgeProcessId: "judge-process",
      ...judgeResult,
      judgeResultSha256: digest(judgeResult),
    },
  };
}

let requestText = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  requestText += chunk;
});
process.stdin.once("end", () => {
  const request = JSON.parse(requestText);
  appendFileSync(
    capturePath,
    JSON.stringify({
      request,
      environment: Object.keys(process.env).sort(),
      compatibilityProfileProvided: process.env.KPI_OMP_COMPAT_AGENT_DIR !== undefined,
      pluginTarballPath: process.env.KPI_OMP_PLUGIN_TARBALL ?? null,
    }) + "\\n",
  );
  if (behavior === "hang") {
    setInterval(() => {}, 1_000);
    return;
  }
  if (behavior === "invalid-json") {
    process.stdout.write("not-json");
    return;
  }
  const response = validResponse(request);
  if (behavior === "invalid-tokens" && request.operation === "execute")
    response.result.events[0].tokens = "not-a-number";
  if (behavior === "invalid-execute-binding" && request.operation === "execute")
    response.result.fixtureId = "P0-VS-OTHER-01";
  if (behavior === "invalid-judge-binding" && request.operation === "judge")
    response.result.firstArtifactSha256 = "f".repeat(64);
  if (
    behavior === "invalid-judge-rubric-substitution" &&
    request.operation === "judge"
  )
    response.result.first.criteria = [
      { id: "not-in-rubric", score: 80, reason: "未绑定冻结验收标准" },
    ];
  if (
    behavior === "invalid-judge-rubric-duplicate" &&
    request.operation === "judge"
  )
    response.result.first.criteria.push({
      ...response.result.first.criteria[0],
      reason: "重复冻结验收标准",
    });
  if (
    behavior === "invalid-judge-rubric-total" &&
    request.operation === "judge"
  ) {
    response.result.second.total = 81;
    if (response.result.first.total !== 80)
      throw new Error("weighted-total fixture mutated both Judge scores");
  }
  if (
    [
      "invalid-judge-rubric-substitution",
      "invalid-judge-rubric-duplicate",
      "invalid-judge-rubric-total",
    ].includes(behavior) &&
    request.operation === "judge"
  )
    response.result.judgeResultSha256 = digest({
      fixtureId: response.result.fixtureId,
      firstArtifactSha256: response.result.firstArtifactSha256,
      secondArtifactSha256: response.result.secondArtifactSha256,
      first: response.result.first,
      second: response.result.second,
    });
  if (
    behavior === "missing-compatibility-proof" &&
    request.operation === "compatibility"
  )
    delete response.result.packageSha256;
  if (behavior === "filesystem-drift" && request.operation === "compatibility")
    response.result.filesystemAfterSha256 = "d".repeat(64);
  if (behavior === "sensitive-output") response.token = "token=must-not-cross";
  if (behavior === "unknown-field") response.unexpected = "not-allowed";
  if (behavior === "home-path")
    response.unexpected = "/Users/release-owner/private";
  if (behavior === "private-path")
    response.unexpected = "/private/var/folders/release-owner/private";
  if (behavior === "workspace-path")
    response.unexpected = "/workspace/release-owner/private";
  if (behavior === "file-uri-path")
    response.unexpected = "file:///private/var/folders/release-owner/private";
  if (behavior === "bare-token")
    response.unexpected = "token=must-not-cross";
  if (behavior === "unclassified-report" && request.operation === "execute") {
    const reportEvent = response.result.events.find(
      (event) => event.kind === "report",
    );
    delete reportEvent.routeCost;
  }
  const write = () => {
    if (behavior === "multiple-json") {
      process.stdout.write(JSON.stringify(response));
      process.stdout.write(JSON.stringify(response));
      return;
    }
    process.stdout.write(JSON.stringify(response));
    if (behavior === "stderr") process.stderr.write("untrusted diagnostic");
    if (behavior === "nonzero") process.exitCode = 2;
  };
  if (
    behavior === "slow-compatibility" &&
    request.operation === "compatibility"
  ) {
    setTimeout(write, 16_000);
    return;
  }
  write();
});
`;
  await writeFile(executable, source, "utf8");
  await chmod(executable, 0o700);
  return executable;
}

function createExecutionInput(
  wallClockMs: number,
): Parameters<OmpProcessAdapter["execute"]>[0] {
  return {
    runId: "adapter-run",
    fixture: {
      schemaVersion: 1,
      id: "P0-VS-HOST-01",
      category: "docs-config",
      prompt: "验证受控 OMP host 协议",
      startingFiles: { "README.md": "fixture" },
      startingSnapshotSha256: "a".repeat(64),
      expected: {
        route: "small-direct-change",
        routeCost: "light",
        requiredGates: ["bdd"],
        obligations: ["返回已脱敏事件"],
      },
      rubric: [
        {
          id: "sanitized-events",
          description: "返回已脱敏事件",
          weight: 1,
          severe: false,
        },
      ],
      cleanupBoundary: "删除临时 fixture",
      permittedNetwork: "none",
    },
    fixtureSha256: "b".repeat(64),
    arm: "treatment",
    mode: "enforced",
    attempt: 1,
    workspacePath: "/tmp/kpi-p0/adapter-run/P0-VS-HOST-01/treatment",
    limits: { wallClockMs, maxTurns: 1, maxTokens: 100 },
  };
}

function createJudgeInput(): Parameters<OmpProcessAdapter["judge"]>[0] {
  const artifact = {
    finalResponse: "完成",
    patch: "diff --git a/fixture b/fixture\n",
    commandOutcomes: [{ command: "fixture-check", status: "passed" as const }],
  };
  return {
    runId: "adapter-run",
    fixtureId: "P0-VS-HOST-01",
    fixtureSha256: "b".repeat(64),
    rubric: [
      {
        id: "sanitized-events",
        description: "返回已脱敏事件",
        weight: 100,
        severe: false,
      },
    ],
    first: {
      artifact,
      artifactSha256: acceptanceArtifactSha256(artifact),
    },
    second: {
      artifact,
      artifactSha256: acceptanceArtifactSha256(artifact),
    },
  };
}

async function runP0Cli(
  arguments_: readonly string[],
  environment: NodeJS.ProcessEnv,
): Promise<
  Readonly<{ exitCode: number | null; stdout: string; stderr: string }>
> {
  const { promise, reject, resolve } =
    Promise.withResolvers<
      Readonly<{ exitCode: number | null; stdout: string; stderr: string }>
    >();
  const child = spawn(
    process.execPath,
    [tsxCliPath, p0CliPath, ...arguments_],
    {
      cwd: pluginRoot,
      env: environment,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  child.once("error", reject);
  child.once("close", (exitCode) => {
    resolve({ exitCode, stdout, stderr });
  });
  return promise;
}

function completeSyntheticScoreInput() {
  return {
    schemaVersion: 1,
    sourceTreeSha256: "a".repeat(64),
    execution: {
      runtimeVersion: "17.1.3",
      modelId: "execution-model",
      processId: "execution-process",
    },
    judge: {
      modelId: "judge-model",
      processId: "judge-process",
    },
    pairs: Array.from({ length: 20 }, (_, index) => ({
      fixtureId: `fixture-${String(index + 1).padStart(2, "0")}`,
      expectedRequiredGates: ["bdd"],
      expectedRouteCost: "standard",
      control: {
        status: "completed",
        observedRequiredGates: ["bdd"],
        actualRouteCost: "standard",
        severeWorkflowOmissions: [],
        attempts: [{ attempt: 1, outcome: "completed" }],
      },
      treatment: {
        status: "completed",
        observedRequiredGates: ["bdd"],
        actualRouteCost: "standard",
        severeWorkflowOmissions: [],
        attempts: [{ attempt: 1, outcome: "completed" }],
      },
      judge: {
        control: {
          total: 80,
          severeAcceptanceFailure: false,
          criteria: [{ id: "complete", score: 80, reason: "满足固定验收标准" }],
        },
        treatment: {
          total: 80,
          severeAcceptanceFailure: false,
          criteria: [{ id: "complete", score: 80, reason: "满足固定验收标准" }],
        },
      },
    })),
  };
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("Feature: P0 发布一致性与证据", () => {
  it("Scenario: 不可用的当前 OMP Runtime 兼容宿主不被当作通过", async () => {
    const root = await temporaryRoot();
    await writeFile(
      join(root, "package.json"),
      JSON.stringify({ name: "@kunolu/omp-sbtd", version: "0.1.0-rc.2" }),
      "utf8",
    );
    const tarball = join(root, "plugin.tgz");
    await writeFile(tarball, "fixture tarball", "utf8");
    const environment = { ...process.env };
    delete environment.KPI_OMP_HARNESS_PATH;
    expect(
      await createAuthorizedHostCommandAdapter({
        KPI_OMP_HARNESS_PATH: "relative-harness",
        PATH: "/usr/bin:/bin",
      }),
    ).toBeUndefined();

    const result = await runP0Cli(
      [
        "check-compatibility",
        "--run-id",
        "adapter-fallback",
        "--packed",
        root,
        "--tarball",
        tarball,
      ],
      environment,
    );

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stdout)).toMatchObject({
      currentRuntimeVersion: "17.3.5",
      result: {
        status: "blocked",
        blocker: { code: "OMP_HOST_UNAVAILABLE" },
      },
    });
    const preflight = await runP0Cli(
      [
        "run-value-study",
        "--execution-model",
        "execution-model",
        "--judge-model",
        "judge-model",
        "--runtime-version",
        "17.1.3",
      ],
      environment,
    );
    expect(preflight.exitCode).toBe(1);
    expect(JSON.parse(preflight.stdout)).toMatchObject({
      status: "blocked",
      blocker: {
        code: "OMP_VALUE_STUDY_PREREQUISITE_UNAVAILABLE",
      },
    });
  }, 10_000);

  it("Scenario: 发布负责人验证未声明 Runtime 的已打包 Plugin", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    await writeFile(
      join(root, "package.json"),
      JSON.stringify({ name: "@kunolu/omp-sbtd", version: "0.1.0-rc.2" }),
      "utf8",
    );
    await writeFile(join(root, "plugin.tgz"), "fixture tarball", "utf8");

    const result = await runP0Cli(
      [
        "check-compatibility",
        "--run-id",
        "experimental-runtime",
        "--runtime-version",
        "17.1.8",
        "--experimental-runtime",
        "17.1.8",
        "--packed",
        root,
        "--tarball",
        join(root, "plugin.tgz"),
      ],
      { ...process.env, KPI_OMP_HARNESS_PATH: executable },
    );

    expect(result.exitCode).toBe(0);
    expect(JSON.parse(result.stdout)).toMatchObject({
      currentRuntimeVersion: "17.1.8",
      compatibility: {
        scope: "experimental",
        declaredRuntimeVersion: "17.3.5",
        testedRuntimeVersion: "17.1.8",
        pluginInput: "packed",
      },
      result: { status: "passed" },
    });
    const capture = JSON.parse(await readFile(capturePath, "utf8"));
    expect(capture).toMatchObject({
      request: {
        operation: "compatibility",
        input: {
          currentRuntimeVersion: "17.1.8",
          pluginPackagePath: root,
          pluginTarballPath: join(root, "plugin.tgz"),
        },
      },
    });
    expect(
      hasAllowedChildEnvironment(capture.environment, {
        pluginTarballPath: join(root, "plugin.tgz"),
      }),
    ).toBe(true);
    expect(capture.pluginTarballPath).toBe(join(root, "plugin.tgz"));
  });

  it("Scenario: 未声明 Runtime 需要显式实验授权", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    await writeFile(
      join(root, "package.json"),
      JSON.stringify({ name: "@kunolu/omp-sbtd", version: "0.1.0-rc.2" }),
      "utf8",
    );
    const tarball = join(root, "plugin.tgz");
    await writeFile(tarball, "fixture tarball", "utf8");
    const result = await runP0Cli(
      [
        "check-compatibility",
        "--run-id",
        "declared-runtime",
        "--runtime-version",
        "17.1.8",
        "--packed",
        root,
        "--tarball",
        tarball,
      ],
      { ...process.env, KPI_OMP_HARNESS_PATH: executable },
    );

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stderr).code).toBe("CURRENT_RUNTIME_MISMATCH");
    await expect(readFile(capturePath, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("Scenario Outline: 实验 Runtime 参数错误时兼容性命令失败关闭", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");

    for (const arguments_ of [
      [
        "check-compatibility",
        "--run-id",
        "mismatched-runtime",
        "--runtime-version",
        "17.1.8",
        "--experimental-runtime",
        "17.1.7",
        "--packed",
        root,
      ],
      [
        "check-compatibility",
        "--run-id",
        "malformed-runtime",
        "--runtime-version",
        "17.1.8",
        "--experimental-runtime",
        "17.1",
        "--packed",
        root,
      ],
      [
        "check-compatibility",
        "--run-id",
        "missing-runtime",
        "--experimental-runtime",
        "17.1.8",
        "--packed",
        root,
      ],
      [
        "check-compatibility",
        "--run-id",
        "missing-packed",
        "--runtime-version",
        "17.1.8",
        "--experimental-runtime",
        "17.1.8",
      ],
    ]) {
      const result = await runP0Cli(arguments_, {
        ...process.env,
        KPI_OMP_HARNESS_PATH: executable,
      });
      expect(result.exitCode).toBe(1);
      expect(JSON.parse(result.stderr).code).toBe("CLI_ARGUMENT_INVALID");
    }
    await expect(readFile(capturePath, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("Scenario: 不安全的运行 ID 不会逃逸到受控宿主", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    const result = await runP0Cli(
      ["check-compatibility", "--run-id", "../../outside-kpi-p0"],
      { ...process.env, KPI_OMP_HARNESS_PATH: executable },
    );

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stderr)).toMatchObject({
      code: "CLI_ARGUMENT_INVALID",
    });
    await expect(readFile(capturePath, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("Scenario: 报告输出不能逃逸本地证据目录", async () => {
    const root = await temporaryRoot();
    const outside = join(root, "outside", "release-report");
    const environment = { ...process.env };
    delete environment.KPI_OMP_HARNESS_PATH;
    const result = await runP0Cli(
      ["check-compatibility", "--run-id", "report-safe", "--out", outside],
      environment,
    );

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stderr)).toMatchObject({
      code: "CLI_ARGUMENT_INVALID",
    });
    await expect(readFile(`${outside}.json`, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
    await expect(readFile(`${outside}.md`, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("Scenario: 已配置的受控宿主 adapter 只接收脱敏协议并验证结果", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
      PRIVATE_TOKEN: "must-not-reach-the-harness",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    const compatibility = await adapter.runCurrentRuntime({
      currentRuntimeVersion: "17.1.3",
      pluginPackagePath: "/workspace/packages/omp-sbtd",
      pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
      sandboxRoot: "/tmp/kpi-p0/17.1.3",
      commands: ["help", "status", "report", "onboard plan"],
    });
    const preflight = await adapter.preflight({
      executionModelId: "execution-model",
      judgeModelId: "judge-model",
      runtimeVersion: "17.1.3",
    });
    const runtimeMode = await adapter.setRuntimeMode({
      fixtureId: "P0-VS-HOST-01",
      mode: "enforced",
    });
    const execution = await adapter.execute(createExecutionInput(1_000));
    const judgment = await adapter.judge(createJudgeInput());

    expect(compatibility).toMatchObject({
      currentRuntimeVersion: "17.1.3",
      status: "passed",
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
    expect(preflight).toEqual({
      status: "ready",
      runtimeVersion: "17.1.3",
      executionModelId: "execution-model",
      judgeModelId: "judge-model",
      executionProcessId: "execution-process",
      judgeProcessId: "judge-process",
      supportsUsageEvents: true,
    });
    expect(runtimeMode).toEqual({ status: "ready" });
    expect(execution).toMatchObject({
      status: "completed",
      runId: "adapter-run",
      fixtureId: "P0-VS-HOST-01",
      arm: "treatment",
      acceptanceArtifact: {
        finalResponse: "完成",
      },
    });
    expect(judgment).toMatchObject({
      status: "completed",
      runId: "adapter-run",
      fixtureId: "P0-VS-HOST-01",
      first: { total: 80 },
      second: { total: 80 },
    });

    const captures = (await readFile(capturePath, "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    expect(captures.map((capture) => capture.request.operation)).toEqual([
      "compatibility",
      "preflight",
      "runtime-mode",
      "execute",
      "judge",
    ]);
    expect(captures[0]).toMatchObject({
      request: {
        schemaVersion: 1,
        operation: "compatibility",
        input: {
          currentRuntimeVersion: "17.1.3",
          pluginPackagePath: "/workspace/packages/omp-sbtd",
          pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
          sandboxRoot: "/tmp/kpi-p0/17.1.3",
          commands: ["help", "status", "report", "onboard plan"],
        },
      },
    });
    expect(
      hasAllowedChildEnvironment(captures[0].environment, {
        pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
      }),
    ).toBe(true);
    expect(captures[0].pluginTarballPath).toBe(
      "/workspace/packages/omp-sbtd.tgz",
    );
    expect(captures[0].compatibilityAgentDirectory).toBeUndefined();
    expect(
      captures
        .slice(1)
        .every(
          (capture) =>
            hasAllowedChildEnvironment(capture.environment) &&
            capture.pluginTarballPath === null,
        ),
    ).toBe(true);
    expect(JSON.stringify(captures[4].request.input)).not.toMatch(
      /"arm"|"mode"|"route"|"gate"|"session"|"provider"|"workspace"|"turns"|"tokens"/i,
    );
  });

  it("Scenario: 发布负责人显式授权专用 OMP profile", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    const agentDirectory = join(root, "dedicated-agent");
    await mkdir(agentDirectory);
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      KPI_OMP_COMPAT_AGENT_DIR: agentDirectory,
      PATH: "/usr/bin:/bin",
      PRIVATE_TOKEN: "must-not-reach-the-harness",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    await expect(
      adapter.runCurrentRuntime({
        currentRuntimeVersion: "17.1.3",
        pluginPackagePath: "/workspace/packages/omp-sbtd",
        pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
        sandboxRoot: "/tmp/kpi-p0/17.1.3",
        commands: ["help", "status", "report", "onboard plan"],
      }),
    ).resolves.toMatchObject({
      status: "passed",
      acceptanceMode: "profile-isolated",
      supportDecision: "requires-separate-support-review",
    });

    await expect(
      adapter.preflight({
        executionModelId: "execution-model",
        judgeModelId: "judge-model",
        runtimeVersion: "17.1.3",
      }),
    ).resolves.toMatchObject({ status: "ready" });

    const captures = (await readFile(capturePath, "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    expect(
      hasAllowedChildEnvironment(captures[0].environment, {
        compatibilityAgentDirectory: agentDirectory,
        pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
      }),
    ).toBe(true);
    expect(captures[0].pluginTarballPath).toBe(
      "/workspace/packages/omp-sbtd.tgz",
    );
    expect(captures[0].compatibilityProfileProvided).toBe(true);
    expect(hasAllowedChildEnvironment(captures[1].environment)).toBe(true);
    expect(captures[1].pluginTarballPath).toBeNull();
    expect(captures[1].compatibilityProfileProvided).toBe(false);
    expect(JSON.stringify(captures)).not.toContain(agentDirectory);
  });

  it("Scenario: 显式 profile 缺少 profile-isolated 证据时失败关闭", async () => {
    const root = await temporaryRoot();
    const agentDirectory = join(root, "dedicated-agent");
    await mkdir(agentDirectory);
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: await writeTrustedHarness(
        root,
        join(root, "captured.jsonl"),
        "missing-profile-mode",
      ),
      KPI_OMP_COMPAT_AGENT_DIR: agentDirectory,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    await expect(
      adapter.runCurrentRuntime({
        currentRuntimeVersion: "17.1.3",
        pluginPackagePath: "/workspace/packages/omp-sbtd",
        pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
        sandboxRoot: "/tmp/kpi-p0/17.1.3",
        commands: ["help", "status", "report", "onboard plan"],
      }),
    ).resolves.toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HOST_COMMAND_RESPONSE_INVALID" },
    });
  });

  it.each([
    ["invalid JSON", "invalid-json", "OMP_HOST_COMMAND_RESPONSE_INVALID"],
    [
      "profile isolation without an explicit profile",
      "unexpected-profile-mode",
      "OMP_HOST_COMMAND_RESPONSE_INVALID",
    ],
    [
      "unknown response field",
      "unknown-field",
      "OMP_HOST_COMMAND_RESPONSE_INVALID",
    ],
    [
      "missing compatibility proof",
      "missing-compatibility-proof",
      "OMP_HOST_COMMAND_RESPONSE_INVALID",
    ],
    [
      "filesystem drift",
      "filesystem-drift",
      "OMP_HOST_COMMAND_RESPONSE_INVALID",
    ],
    [
      "multiple JSON values",
      "multiple-json",
      "OMP_HOST_COMMAND_RESPONSE_INVALID",
    ],
    [
      "sensitive output",
      "sensitive-output",
      "OMP_HOST_COMMAND_SENSITIVE_OUTPUT",
    ],
    ["absolute home path", "home-path", "OMP_HOST_COMMAND_SENSITIVE_OUTPUT"],
    [
      "absolute macOS temporary path",
      "private-path",
      "OMP_HOST_COMMAND_SENSITIVE_OUTPUT",
    ],
    [
      "absolute workspace path",
      "workspace-path",
      "OMP_HOST_COMMAND_SENSITIVE_OUTPUT",
    ],
    [
      "absolute local file URI",
      "file-uri-path",
      "OMP_HOST_COMMAND_SENSITIVE_OUTPUT",
    ],
    ["bare token", "bare-token", "OMP_HOST_COMMAND_SENSITIVE_OUTPUT"],
    ["stderr", "stderr", "OMP_HOST_COMMAND_STDERR_REJECTED"],
    ["non-zero exit", "nonzero", "OMP_HOST_COMMAND_FAILED"],
  ] as const)("Scenario: 已配置的受控宿主 adapter 对 %s 保持阻断且不泄露子进程输出", async (_label, behavior, blockerCode) => {
    const root = await temporaryRoot();
    const executable = await writeTrustedHarness(
      root,
      join(root, "captured.jsonl"),
      behavior,
    );
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    const result = await adapter.runCurrentRuntime({
      currentRuntimeVersion: "17.1.3",
      pluginPackagePath: "/workspace/packages/omp-sbtd",
      pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
      sandboxRoot: "/tmp/kpi-p0/17.1.3",
      commands: ["help", "status", "report", "onboard plan"],
    });

    expect(result).toMatchObject({
      status: "blocked",
      blocker: { code: blockerCode },
    });
    const serializedResult = JSON.stringify(result);
    expect(serializedResult).not.toContain("untrusted diagnostic");
    expect(serializedResult).not.toContain("token=must-not-cross");
    expect(serializedResult).not.toContain("/Users/release-owner/private");
    expect(serializedResult).not.toContain(
      "/private/var/folders/release-owner/private",
    );
  });

  it("Scenario: 非数值 usage tokens 仍被协议拒绝", async () => {
    const root = await temporaryRoot();
    const executable = await writeTrustedHarness(
      root,
      join(root, "captured.jsonl"),
      "invalid-tokens",
    );
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    await expect(
      adapter.execute(createExecutionInput(1_000)),
    ).resolves.toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HOST_COMMAND_RESPONSE_INVALID" },
    });
  });

  it("Scenario: execute 和 judge 的响应绑定必须与请求完全一致", async () => {
    const root = await temporaryRoot();
    const executeHarness = await writeTrustedHarness(
      root,
      join(root, "execute.jsonl"),
      "invalid-execute-binding",
    );
    const executeAdapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executeHarness,
      PATH: "/usr/bin:/bin",
    });
    if (executeAdapter === undefined)
      throw new Error("expected authorized harness");
    await expect(
      executeAdapter.execute(createExecutionInput(1_000)),
    ).resolves.toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HOST_COMMAND_RESPONSE_INVALID" },
    });

    const judgeHarness = await writeTrustedHarness(
      root,
      join(root, "judge.jsonl"),
      "invalid-judge-binding",
    );
    const judgeAdapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: judgeHarness,
      PATH: "/usr/bin:/bin",
    });
    if (judgeAdapter === undefined)
      throw new Error("expected authorized harness");
    await expect(judgeAdapter.judge(createJudgeInput())).resolves.toMatchObject(
      {
        status: "blocked",
        blocker: { code: "OMP_HOST_COMMAND_RESPONSE_INVALID" },
      },
    );
  });

  it.each([
    ["缺失并替换 criterion", "invalid-judge-rubric-substitution"],
    ["重复 criterion ID", "invalid-judge-rubric-duplicate"],
    ["加权 total 不一致", "invalid-judge-rubric-total"],
  ] as const)("Scenario: judge 响应必须逐项绑定冻结 rubric（%s）", async (_case, behavior) => {
    const root = await temporaryRoot();
    const judgeHarness = await writeTrustedHarness(
      root,
      join(root, `${behavior}.jsonl`),
      behavior,
    );
    const judgeAdapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: judgeHarness,
      PATH: "/usr/bin:/bin",
    });
    if (judgeAdapter === undefined)
      throw new Error("expected authorized harness");

    await expect(judgeAdapter.judge(createJudgeInput())).resolves.toMatchObject(
      {
        status: "blocked",
        blocker: { code: "OMP_HOST_COMMAND_RESPONSE_INVALID" },
      },
    );
  });

  it("Scenario: 超出批准范围的执行时限不会调用受控宿主", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    await expect(
      adapter.execute(createExecutionInput(600_001)),
    ).resolves.toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HOST_COMMAND_REQUEST_INVALID" },
    });
    await expect(readFile(capturePath, "utf8")).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  // This integration test uses the OS clock because fake timers cannot advance a child process.
  it("Scenario: 执行受控宿主超过用户声明时限后被阻断", async () => {
    const root = await temporaryRoot();
    const executable = await writeTrustedHarness(
      root,
      join(root, "captured.jsonl"),
      "hang",
    );
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    await expect(
      adapter.execute(createExecutionInput(1)),
    ).resolves.toMatchObject({
      status: "blocked",
      blocker: { code: "OMP_HOST_COMMAND_TIMEOUT" },
    });
  }, 8_000);

  it("Scenario: 未分类 auto 主机的报告事件不携带 routeCost 仍被接受", async () => {
    const root = await temporaryRoot();
    const executable = await writeTrustedHarness(
      root,
      join(root, "captured.jsonl"),
      "unclassified-report",
    );
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    const execution = await adapter.execute(createExecutionInput(1_000));

    expect(execution.status).toBe("completed");
    if (execution.status !== "completed") return;
    const reportEvent = execution.events.find(
      (event) => event.kind === "report",
    );
    expect(reportEvent).toEqual({ kind: "report", requiredGates: ["bdd"] });
  });

  // This integration test uses the OS clock because fake timers cannot advance a
  // child process: the host deadline must exceed the per-command certification
  // budgets, which only a genuinely slower allowed sequence can prove.
  it("Scenario: 有界但较慢的四命令认证不被过短的总时限误杀", async () => {
    const root = await temporaryRoot();
    const executable = await writeTrustedHarness(
      root,
      join(root, "captured.jsonl"),
      "slow-compatibility",
    );
    const adapter = await createAuthorizedHostCommandAdapter({
      KPI_OMP_HARNESS_PATH: executable,
      PATH: "/usr/bin:/bin",
    });
    if (adapter === undefined) throw new Error("expected authorized harness");

    await expect(
      adapter.runCurrentRuntime({
        currentRuntimeVersion: "17.1.3",
        pluginPackagePath: "/workspace/packages/omp-sbtd",
        pluginTarballPath: "/workspace/packages/omp-sbtd.tgz",
        sandboxRoot: "/tmp/kpi-p0/17.1.3-slow",
        commands: ["help", "status", "report", "onboard plan"],
      }),
    ).resolves.toMatchObject({
      status: "passed",
      commandResults: {
        help: "passed",
        status: "passed",
        report: "passed",
        "onboard plan": "passed",
      },
    });
  }, 30_000);

  it("Scenario: 受控宿主预检就绪不使未请求研究的综合检查通过", async () => {
    const root = await temporaryRoot();
    const capturePath = join(root, "captured.jsonl");
    const executable = await writeTrustedHarness(root, capturePath, "valid");
    const packedRoot = join(root, "packed");
    await mkdir(packedRoot);
    await writeFile(
      join(packedRoot, "package.json"),
      JSON.stringify({ name: "@kunolu/omp-sbtd", version: "0.1.0-rc.2" }),
      "utf8",
    );
    const tarball = join(root, "plugin.tgz");
    await writeFile(tarball, "fixture tarball", "utf8");
    const environment = {
      ...process.env,
      KPI_OMP_HARNESS_PATH: executable,
      PRIVATE_TOKEN: "must-not-reach-the-harness",
    };

    const compatibility = await runP0Cli(
      [
        "check-compatibility",
        "--run-id",
        "authorized-host",
        "--packed",
        packedRoot,
        "--tarball",
        tarball,
      ],
      environment,
    );
    expect(compatibility.exitCode).toBe(0);
    expect(JSON.parse(compatibility.stdout)).toMatchObject({
      currentRuntimeVersion: "17.3.5",
      result: { status: "passed" },
    });

    const all = await runP0Cli(
      [
        "all",
        "--run-id",
        "authorized-host",
        "--execution-model",
        "execution-model",
        "--judge-model",
        "judge-model",
        "--runtime-version",
        "17.3.5",
        "--packed",
        packedRoot,
        "--tarball",
        tarball,
      ],
      environment,
    );
    expect(all.exitCode).toBe(1);
    expect(JSON.parse(all.stdout)).toMatchObject({
      compatibility: {
        currentRuntimeVersion: "17.3.5",
        result: { status: "passed" },
      },
      valueStudy: {
        status: "blocked",
        preflight: { status: "ready" },
        blocker: { code: "VALUE_STUDY_EXECUTION_REQUIRED" },
      },
      blocker: { code: "EXTERNAL_P0_PREREQUISITES_REQUIRED" },
    });

    const captures = (await readFile(capturePath, "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    expect(captures).toHaveLength(3);
    expect(captures.map((capture) => capture.request.operation)).toEqual([
      "compatibility",
      "compatibility",
      "preflight",
    ]);
    expect(
      captures.slice(0, 2).every((capture) =>
        hasAllowedChildEnvironment(capture.environment, {
          pluginTarballPath: tarball,
        }),
      ),
    ).toBe(true);
    expect(
      captures
        .slice(0, 2)
        .every((capture) => capture.pluginTarballPath === tarball),
    ).toBe(true);
    expect(
      hasAllowedChildEnvironment(captures[2].environment) &&
        captures[2].pluginTarballPath === null,
    ).toBe(true);
  });
  it("Scenario: 不可追溯的完整评分输入不能宣称价值 Gate 通过", async () => {
    const root = await temporaryRoot();
    const inputPath = join(root, "synthetic-score.json");
    await writeFile(
      inputPath,
      `${JSON.stringify(completeSyntheticScoreInput())}\n`,
      "utf8",
    );

    const result = await runP0Cli(
      ["score-value-study", "--input", inputPath],
      process.env,
    );

    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stdout)).toMatchObject({
      status: "blocked",
      blocker: { code: "VALUE_STUDY_EXECUTION_REQUIRED" },
    });
  });
});
