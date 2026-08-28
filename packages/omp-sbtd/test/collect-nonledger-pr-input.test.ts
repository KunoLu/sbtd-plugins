// Trace: packages/omp-sbtd/features/p0-conformance-release.feature
//   Rule: 非账本生产 PR 的 required status 不得变成宽旁路
//
// Mock Strategy: fake `gh` returns GitHub-shaped JSON and applies `--jq`
// like `gh api --paginate --jq`. Not full-stack.

import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  LINUX_PROBE_CHECK_NAME,
  LINUX_PROBE_WORKFLOW_PATH,
} from "../scripts/p0/classify-nonledger-pr.ts";

const SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const pluginRoot = fileURLToPath(new URL("..", import.meta.url));
const collector = join(pluginRoot, "scripts/p0/collect-nonledger-pr-input.sh");

const dirs: string[] = [];

afterEach(() => {
  for (const dir of dirs.splice(0))
    rmSync(dir, { recursive: true, force: true });
});

function fakeGhScript(): string {
  return `#!/usr/bin/env bash
set -euo pipefail
jq_prog=""
path=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--jq" ]; then
    jq_prog="$2"
    shift 2
    continue
  fi
  if [[ "$1" == repos/* ]]; then
    path="$1"
  fi
  shift
done
emit() {
  if [ -n "\${jq_prog}" ]; then
    jq -c "\${jq_prog}"
  else
    cat
  fi
}
if [[ "\${path}" == *"/files"* ]]; then
  echo '[{"filename":"packages/omp-sbtd/src/index.ts","previous_filename":".github/workflows/omp-compatibility-ledger-validate.yml"},{"filename":"README.md"}]' | emit
  exit 0
fi
if [[ "\${path}" == *"/check-runs"* ]]; then
  echo '{"check_runs":[{"name":"${LINUX_PROBE_CHECK_NAME}","app":{"slug":"github-actions"},"status":"completed","conclusion":"success"},{"name":"page-two-unrelated","app":{"slug":"github-actions"},"status":"completed","conclusion":"success"}]}' | emit
  exit 0
fi
if [[ "\${path}" == *"/jobs"* ]]; then
  echo '{"jobs":[{"name":"${LINUX_PROBE_CHECK_NAME}","status":"completed","conclusion":"success"}]}' | emit
  exit 0
fi
if [[ "\${path}" == *"/actions/runs"* ]]; then
  echo '{"workflow_runs":[{"id":99,"path":"${LINUX_PROBE_WORKFLOW_PATH}","head_sha":"${SHA}","status":"completed","conclusion":"success"}]}' | emit
  exit 0
fi
if [[ "\${path}" == *"/pulls/"* ]]; then
  echo '{"state":"open","head":{"sha":"${SHA}","ref":"feature/ordinary","repo":{"full_name":"KunoLu/sbtd-plugins"}},"base":{"ref":"main"}}'
  exit 0
fi
echo "unexpected gh path: \${path}" >&2
exit 1
`;
}

describe("collect-nonledger-pr-input pagination", () => {
  it("merges two paginated file and check-run pages into classifier JSON", () => {
    const dir = mkdtempSync(join(tmpdir(), "nonledger-gh-"));
    dirs.push(dir);
    const ghPath = join(dir, "gh");
    writeFileSync(ghPath, fakeGhScript(), "utf8");
    chmodSync(ghPath, 0o755);
    const spawned = spawnSync("bash", [collector, "37", SHA], {
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: `${dir}:${process.env.PATH ?? ""}`,
        GITHUB_REPOSITORY: "KunoLu/sbtd-plugins",
        RUNNER_TEMP: dir,
      },
    });
    expect(spawned.status, spawned.stderr).toBe(0);
    const payload = JSON.parse(spawned.stdout) as {
      files: Array<{ filename: string; previousFilename?: string }>;
      checkRuns: Array<{ name: string }>;
      workflowRuns: Array<{ id: number }>;
      jobsByRunId: Record<string, Array<{ name: string }>>;
    };
    expect(payload.files).toEqual([
      {
        filename: "packages/omp-sbtd/src/index.ts",
        previousFilename:
          ".github/workflows/omp-compatibility-ledger-validate.yml",
      },
      { filename: "README.md" },
    ]);
    expect(payload.checkRuns.map((run) => run.name)).toEqual([
      LINUX_PROBE_CHECK_NAME,
      "page-two-unrelated",
    ]);
    expect(payload.workflowRuns).toEqual([
      {
        id: 99,
        path: LINUX_PROBE_WORKFLOW_PATH,
        headSha: SHA,
        status: "completed",
        conclusion: "success",
      },
    ]);
    expect(payload.jobsByRunId["99"]?.[0]?.name).toBe(LINUX_PROBE_CHECK_NAME);
  });
});
