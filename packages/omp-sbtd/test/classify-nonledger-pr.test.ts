// Trace: packages/omp-sbtd/features/p0-conformance-release.feature
//   Rule: 非账本生产 PR 的 required status 不得变成宽旁路
//
// Mock Strategy: contract-backed GitHub API fixtures. No network. Not full-stack.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  evaluateNonledgerStatus,
  LINUX_PROBE_CHECK_NAME,
  LINUX_PROBE_WORKFLOW_PATH,
  type NonledgerStatusInput,
} from "../scripts/p0/classify-nonledger-pr.ts";

const SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const OTHER_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

function ordinaryFiles(): NonledgerStatusInput["files"] {
  return [{ filename: "packages/omp-sbtd/src/index.ts" }];
}

function allowlistedSuccess(): Pick<
  NonledgerStatusInput,
  "checkRuns" | "workflowRuns" | "jobsByRunId"
> {
  return {
    checkRuns: [
      {
        name: LINUX_PROBE_CHECK_NAME,
        appSlug: "github-actions",
        status: "completed",
        conclusion: "success",
      },
    ],
    workflowRuns: [
      {
        id: 99,
        path: LINUX_PROBE_WORKFLOW_PATH,
        headSha: SHA,
        status: "completed",
        conclusion: "success",
      },
    ],
    jobsByRunId: {
      "99": [
        {
          name: LINUX_PROBE_CHECK_NAME,
          status: "completed",
          conclusion: "success",
        },
      ],
    },
  };
}

function baseOrdinary(
  overrides: Partial<NonledgerStatusInput> = {},
): NonledgerStatusInput {
  return {
    state: "open",
    headRepo: "KunoLu/sbtd-plugins",
    headRef: "feature/ordinary",
    baseRef: "main",
    headSha: SHA,
    expectedHeadSha: SHA,
    files: ordinaryFiles(),
    ...allowlistedSuccess(),
    ...overrides,
  };
}

describe("非账本生产 PR 的 required status 不得变成宽旁路", () => {
  it("兼容性账本自动化分支不能由非账本路径写入成功状态", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({ headRef: "omp-compatibility/33083037731" }),
    );
    expect(result.decision).toBe("reject-identity");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("控制面文件变更不能由非账本路径写入成功状态", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({
        files: [
          {
            filename:
              ".github/workflows/omp-compatibility-nonledger-validate.yml",
          },
        ],
      }),
    );
    expect(result.decision).toBe("reject-control-plane");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("从控制面路径改名到普通路径不能由非账本路径写入成功状态", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({
        files: [
          {
            filename: "packages/omp-sbtd/src/index.ts",
            previousFilename:
              ".github/workflows/omp-compatibility-ledger-validate.yml",
          },
        ],
      }),
    );
    expect(result.decision).toBe("reject-control-plane");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("空变更列表不能由非账本路径写入成功状态", () => {
    const result = evaluateNonledgerStatus(baseOrdinary({ files: [] }));
    expect(result.decision).toBe("reject-control-plane");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("allowlist 内的 linux-probe 检查未成功时不得写入成功状态", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({
        checkRuns: [
          {
            name: LINUX_PROBE_CHECK_NAME,
            appSlug: "github-actions",
            status: "in_progress",
            conclusion: null,
          },
        ],
        workflowRuns: [],
        jobsByRunId: {},
      }),
    );
    expect(result.decision).toBe("reject-prerequisites");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("无关的 GitHub Actions 成功不能替代 allowlist 检查", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({
        checkRuns: [
          {
            name: "unrelated-lint",
            appSlug: "github-actions",
            status: "completed",
            conclusion: "success",
          },
        ],
        workflowRuns: [
          {
            id: 7,
            path: ".github/workflows/unrelated.yml",
            headSha: SHA,
            status: "completed",
            conclusion: "success",
          },
        ],
        jobsByRunId: {
          "7": [
            {
              name: "unrelated-lint",
              status: "completed",
              conclusion: "success",
            },
          ],
        },
      }),
    );
    expect(result.decision).toBe("reject-prerequisites");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("普通生产 PR 在 exact head 与 allowlist 全成功时允许 Status App 写入成功状态", () => {
    const result = evaluateNonledgerStatus(baseOrdinary());
    expect(result.decision).toBe("allow-success");
    expect(result.mayWriteSuccess).toBe(true);
  });

  it("最终写入前 head SHA 变化则不得写入成功状态", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({ freshHeadSha: OTHER_SHA }),
    );
    expect(result.decision).toBe("reject-head-changed");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("同名检查来自其他工作流不能当作 allowlist 成功", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({
        workflowRuns: [
          {
            id: 3,
            path: ".github/workflows/other.yml",
            headSha: SHA,
            status: "completed",
            conclusion: "success",
          },
        ],
        jobsByRunId: {
          "3": [
            {
              name: LINUX_PROBE_CHECK_NAME,
              status: "completed",
              conclusion: "success",
            },
          ],
        },
      }),
    );
    expect(result.decision).toBe("reject-prerequisites");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("已取消的 linux-probe 运行即使残留成功 job 也不能当作 allowlist 成功", () => {
    const result = evaluateNonledgerStatus(
      baseOrdinary({
        workflowRuns: [
          {
            id: 99,
            path: LINUX_PROBE_WORKFLOW_PATH,
            headSha: SHA,
            status: "completed",
            conclusion: "cancelled",
          },
        ],
      }),
    );
    expect(result.decision).toBe("reject-prerequisites");
    expect(result.mayWriteSuccess).toBe(false);
  });

  it("relative tsx CLI path prints decision JSON", () => {
    const pluginRoot = fileURLToPath(new URL("..", import.meta.url));
    const spawned = spawnSync(
      "pnpm",
      ["exec", "tsx", "scripts/p0/classify-nonledger-pr.ts"],
      {
        cwd: pluginRoot,
        input: JSON.stringify(baseOrdinary()),
        encoding: "utf8",
      },
    );
    expect(spawned.status, spawned.stderr).toBe(0);
    const line = spawned.stdout.trim().split("\n").at(-1);
    expect(JSON.parse(line ?? "").decision).toBe("allow-success");
  });
});
