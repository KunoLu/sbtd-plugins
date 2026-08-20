import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  type CanonicalOnboardProcess,
  type CanonicalOnboardRuntimeError,
  createCanonicalOnboardRuntime,
} from "../src/onboard/python-runtime.ts";

const runtimeRoot = resolve(
  "../../packages/sbtd-workflow-kit/vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard",
);
const runtimeScriptSha256 =
  "2aeaa3038f7bfdcca86c121a73a8568cf573fe7805aaba1fee0ca971b153a7d7";

function processFor(result: {
  readonly stdout: string;
  readonly stderr?: string;
  readonly code?: number | null;
  readonly killed?: boolean;
}) {
  const calls: Array<{
    command: string;
    args: readonly string[];
    options: { readonly cwd: string; readonly timeout: number };
  }> = [];
  const process: CanonicalOnboardProcess = {
    async exec(command, args, options) {
      calls.push({ command, args, options });
      return {
        stdout: result.stdout,
        stderr: result.stderr ?? "",
        code: result.code ?? 0,
        killed: result.killed ?? false,
      };
    },
  };
  return { process, calls };
}

const agentCliJson = JSON.stringify({
  mode: "check-agent-cli",
  platform: "oh-my-pi",
  label: "Oh My Pi",
  command: "omp",
  path: "/bin/omp",
  version: "omp/17.3.5",
  installed: true,
  npmPackage: "@oh-my-pi/pi-coding-agent",
  installCommand: "npm install -g @oh-my-pi/pi-coding-agent@latest",
  verifyCommand: "omp --version",
  advice: "verified",
  runtime: {},
});

const installJson = JSON.stringify({
  mode: "install-external-skills",
  scope: "global",
  requestedSource: "auto",
  targetDir: "/skills",
  forceOverwriteExisting: true,
  backupExistingTargets: "temporary-rollback",
  replaceFlagProvided: false,
  plan: {},
  results: [
    {
      name: "tdd",
      repo: "https://github.com/mattpocock/skills.git",
      target: "/skills/tdd",
      status: "replaced",
      phase: "commit",
      replacedExisting: true,
      sourceUsed: "stable",
      sourceRevision: "4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb",
      stableSet: "2026-08-11.1",
      fallbackReason: null,
    },
  ],
  transaction: {
    status: "committed",
    rolledBack: false,
    rollbackErrors: [],
    rollbackPath: null,
  },
  postCheck: {},
  installationReport: {},
});

describe("Feature: Canonical Python Onboard runtime", () => {
  it("Scenario: only a typed OMP CLI probe reaches python without a shell", async () => {
    const { process, calls } = processFor({ stdout: agentCliJson });
    const runtime = await createCanonicalOnboardRuntime({
      runtimeRoot,
      runtimeScriptSha256,
      process,
    });

    await expect(
      runtime.run({ kind: "check-omp-cli", cwd: "/project" }),
    ).resolves.toMatchObject({ command: "omp", installed: true });
    expect(calls).toEqual([
      {
        command: "python3",
        args: [
          resolve(runtimeRoot, "scripts/onboard.py"),
          "check-agent-cli",
          "--platform",
          "omp",
          "--json",
        ],
        options: { cwd: "/project", timeout: 120_000 },
      },
    ]);
  });

  it("Scenario: stable external-skill commits expose only validated target facts", async () => {
    const { process, calls } = processFor({ stdout: installJson });
    const runtime = await createCanonicalOnboardRuntime({
      runtimeRoot,
      runtimeScriptSha256,
      process,
    });

    await expect(
      runtime.run({
        kind: "install-stable-external-skills",
        cwd: "/project",
        globalSkillsDirectory: "/skills",
      }),
    ).resolves.toMatchObject({
      transaction: { status: "committed" },
      results: [{ name: "tdd", status: "replaced" }],
    });
    expect(calls[0]?.args.slice(1)).toEqual([
      "install-external-skills",
      "--all",
      "--scope",
      "global",
      "--source",
      "auto",
      "--global-skills-dir",
      "/skills",
      "--yes",
      "--json",
    ]);
  });

  it("Scenario: mismatched embedded script, nonzero execution, and malformed output fail closed", async () => {
    await expect(
      createCanonicalOnboardRuntime({
        runtimeRoot,
        runtimeScriptSha256: "0".repeat(64),
        process: processFor({ stdout: agentCliJson }).process,
      }),
    ).rejects.toMatchObject<Partial<CanonicalOnboardRuntimeError>>({
      code: "INVALID_RUNTIME_PATH",
    });

    const failed = await createCanonicalOnboardRuntime({
      runtimeRoot,
      runtimeScriptSha256,
      process: processFor({ stdout: agentCliJson, code: 1 }).process,
    });
    const malformed = await createCanonicalOnboardRuntime({
      runtimeRoot,
      runtimeScriptSha256,
      process: processFor({ stdout: "not-json" }).process,
    });
    await expect(
      failed.run({ kind: "check-omp-cli", cwd: "/project" }),
    ).rejects.toMatchObject<Partial<CanonicalOnboardRuntimeError>>({
      code: "PROCESS_FAILED",
    });
    await expect(
      malformed.run({ kind: "check-omp-cli", cwd: "/project" }),
    ).rejects.toMatchObject<Partial<CanonicalOnboardRuntimeError>>({
      code: "MALFORMED_OUTPUT",
    });
  });
});
