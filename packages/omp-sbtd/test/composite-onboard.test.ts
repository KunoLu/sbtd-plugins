import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  type CompositeOnboardIdentity,
  createCompositeOnboardService,
  emptyApprovalSet,
} from "../src/onboard/composite.ts";
import {
  type ApplyResult,
  createNodeFileAdapter,
  type FileAdapter,
  type OnboardPlan,
  type OnboardRecovery,
  type OnboardService,
} from "../src/onboard/index.ts";
import type { CanonicalOnboardRuntime } from "../src/onboard/python-runtime.ts";

const projectRoot = "/work/project";
const agentDirectory = "/work/agent";
const now = "2026-08-11T00:00:00.000Z";
const digest = "a".repeat(64);

function memoryFiles(initial: Record<string, string> = {}): FileAdapter & {
  readonly contents: Map<string, string>;
  readonly writes: string[];
  readonly accesses: string[];
} {
  const contents = new Map(Object.entries(initial));
  const directories = new Set<string>();
  const writes: string[] = [];
  const accesses: string[] = [];
  const touch = (path: string): void => {
    accesses.push(path);
  };
  return {
    contents,
    writes,
    accesses,
    async readText(path) {
      touch(path);
      return contents.get(path);
    },
    async writeAtomic(path, content) {
      touch(path);
      writes.push(path);
      contents.set(path, content);
    },
    async makeDirectory(path) {
      touch(path);
      directories.add(path);
    },
    async exists(path) {
      touch(path);
      return contents.has(path) || directories.has(path);
    },
    async remove(path) {
      touch(path);
      contents.delete(path);
      directories.delete(path);
    },
    async isSymlink(path) {
      touch(path);
      return false;
    },
  };
}

function agents(): OnboardService {
  const plan: OnboardPlan = {
    schemaVersion: 1,
    operationId: "agents-operation",
    createdAt: now,
    expiresAt: "2026-08-11T00:10:00.000Z",
    digest,
    kit: {
      sourceId: "sbtd-workflow-kit-upstream",
      sourceRevision: "0".repeat(40),
      transformVersion: "p0-v3",
      kitRevision: "kit-revision",
    },
    inventoryPath: resolve(agentDirectory, "kpi/provenance/inventory-v1.json"),
    inventoryDigest: digest,
    targets: [],
    proposedFiles: {},
  };
  const result: ApplyResult = {
    kind: "applied",
    message: "Managed AGENTS applied.",
    reloadRequired: true,
    residuals: [],
  };
  const recovery: OnboardRecovery = {
    kind: "none",
    backups: [],
    residuals: [],
    repairPath: "/sbtd onboard plan",
  };
  return {
    plan: async () => plan,
    apply: async () => result,
    inspectRecovery: async () => recovery,
    recover: async () => result,
  };
}

const identity: CompositeOnboardIdentity = {
  sourceId: "sbtd-workflow-kit-upstream",
  sourceRevision: "0".repeat(40),
  transformVersion: "p0-v3",
  kitRevision: "kit-revision",
  projectionSha256: digest,
  pluginVersion: "0.1.0-rc.8",
  stableSet: "2026-08-03",
  canonicalRuntimeSha256: digest,
};

describe("Feature: SBTD 控制引导", () => {
  const tempRoots: string[] = [];
  afterEach(async () => {
    await Promise.all(
      tempRoots
        .splice(0)
        .map((root) => rm(root, { recursive: true, force: true })),
    );
  });

  it("Scenario: 预览完整 Environment Onboard 计划保持所有目标不变", async () => {
    const mcpPath = resolve(agentDirectory, "mcp.json");
    const files = memoryFiles({
      [mcpPath]: JSON.stringify({
        mcpServers: { preserved: { command: "keep" } },
      }),
    });
    const runtime: CanonicalOnboardRuntime = {
      async run(request) {
        if (request.kind === "check-omp-cli")
          return {
            mode: "check-agent-cli",
            platform: "oh-my-pi",
            label: "Oh My Pi",
            command: "omp",
            path: "/bin/omp",
            version: "17.3.5",
            installed: true,
            npmPackage: "@oh-my-pi/pi-coding-agent",
            installCommand: "npm install -g @oh-my-pi/pi-coding-agent",
            verifyCommand: "omp --version",
            advice: "verified",
          };
        return {
          mode: "install-external-skills",
          scope: "global",
          requestedSource: "auto",
          targetDir: request.globalSkillsDirectory,
          forceOverwriteExisting: true,
          backupExistingTargets: "temporary-rollback",
          replaceFlagProvided: true,
          results: [],
          transaction: {
            status: "committed",
            rolledBack: false,
            rollbackErrors: [],
            rollbackPath: null,
          },
        };
      },
    };
    const scheduled: string[] = [];
    const serviceInputs = {
      agents: agents(),
      scope: "all" as const,
      projectRoot,
      agentDirectory,
      globalSkillsDirectory: resolve(agentDirectory, "..", "skills"),
      kitBundledSkillsRoot: resolve(agentDirectory, "kit-bundled-skills"),
      mcpConfigPath: mcpPath,
      identity,
      onboardProfileId: "omp-p0-standard-v1",
      route: "auto",
      runtime,
      files,
      now: () => now,
      operationId: () => "composite-operation",
      handoff: {
        schedule: async (prompt: string) => void scheduled.push(prompt),
      },
      listDir: async () => [],
      process: {
        async exec(command: string, args: readonly string[]) {
          if (command === "trellis" && args[0] === "init") {
            files.contents.set(
              resolve(projectRoot, ".trellis/workflow.md"),
              "workflow",
            );
            files.contents.set(
              resolve(
                projectRoot,
                ".trellis/tasks/00-bootstrap-guidelines/task.json",
              ),
              JSON.stringify({ status: "planning" }),
            );
          }
          return { stdout: "17.3.5\n", stderr: "", code: 0, killed: false };
        },
      },
    };
    const service = createCompositeOnboardService(serviceInputs);

    const plan = await service.plan({
      mcpSelections: ["gitnexus"],
      trellisUsername: "640",
    });
    expect(plan.schemaVersion).toBe(2);
    expect(plan.certifiedSkills.packagedCount).toBe(12);
    expect(plan.certifiedSkills.names).toHaveLength(12);
    expect(plan.certifiedSkills.invalidSkills).toEqual([]);
    expect(plan.mcpEntries).toMatchObject([
      { id: "gitnexus", action: "merge" },
    ]);
    expect(plan.trellisProjects).toMatchObject([
      { action: "init", username: "640" },
    ]);
    expect(plan.approvalClasses).toEqual(
      expect.arrayContaining(["managed-files", "mcp-config", "trellis-init"]),
    );
    expect(files.writes).toEqual([]);

    const approvals = emptyApprovalSet();
    approvals["managed-files"] = true;
    const changedContextService = createCompositeOnboardService({
      ...serviceInputs,
      agents: agents(),
      route: "review",
    });
    const writesBeforeStaleApply = files.writes.length;
    await expect(
      changedContextService.apply(plan, approvals),
    ).resolves.toMatchObject({
      kind: "stale",
      participants: {},
    });
    expect(files.writes).toHaveLength(writesBeforeStaleApply);
    approvals["mcp-config"] = true;
    approvals["trellis-init"] = true;
    const applied = await service.apply(plan, approvals);

    expect(applied.kind).toBe("applied");
    expect(applied.participants).toMatchObject({
      agents: { status: "applied" },
      skills: { status: "applied" },
      mcp: { status: "applied" },
      [`trellis:${projectRoot}`]: { status: "applied" },
    });
    expect(applied.bootstrapRequired).toBe(true);
    expect(JSON.parse(files.contents.get(mcpPath) ?? "{}")).toMatchObject({
      mcpServers: {
        preserved: { command: "keep" },
        gitnexus: { command: "gitnexus", args: ["mcp"] },
      },
    });

    await expect(
      service.requestBootstrap(plan.digest, false),
    ).resolves.toMatchObject({
      kind: "cancelled",
    });
    await expect(
      service.requestBootstrap(plan.digest, true),
    ).resolves.toMatchObject({
      kind: "scheduled",
      taskState: "pending",
    });
    expect(scheduled).toHaveLength(1);
    files.contents.set(
      resolve(projectRoot, ".trellis/tasks/00-bootstrap-guidelines/task.json"),
      JSON.stringify({ status: "in_progress" }),
    );
    await expect(
      service.requestBootstrap(plan.digest, false),
    ).resolves.toMatchObject({
      kind: "scheduled",
      taskState: "running",
    });

    files.contents.set(
      resolve(projectRoot, ".trellis/tasks/00-bootstrap-guidelines/task.json"),
      JSON.stringify({ status: "completed" }),
    );
    await expect(
      service.requestBootstrap(plan.digest, false),
    ).resolves.toMatchObject({
      kind: "ready",
      taskState: "completed",
    });
  });

  it("Scenario: Project 范围 Onboard 不触碰全局 certified 旧副本", async () => {
    const mcpPath = resolve(agentDirectory, "mcp.json");
    const leftover = resolve(
      agentDirectory,
      "..",
      "skills",
      "gherkin-bdd",
      "SKILL.md",
    );
    const files = memoryFiles({
      [mcpPath]: JSON.stringify({ mcpServers: {} }),
      [leftover]: "user leftover",
    });
    const service = createCompositeOnboardService({
      agents: agents(),
      scope: "projects",
      projectRoot,
      agentDirectory,
      globalSkillsDirectory: resolve(agentDirectory, "..", "skills"),
      kitBundledSkillsRoot: resolve(agentDirectory, "kit-bundled-skills"),
      mcpConfigPath: mcpPath,
      identity,
      onboardProfileId: "omp-p0-standard-v1",
      route: "auto",
      runtime: undefined,
      files,
      now: () => now,
      operationId: () => "composite-operation",
      listDir: async () => [],
      process: {
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      },
    });
    const plan = await service.plan({});
    expect(plan.skills.action).toBe("out-of-scope");
    const approvals = emptyApprovalSet();
    approvals["managed-files"] = true;
    const applied = await service.apply(plan, approvals);
    expect(applied.participants.certifiedCleanup).toMatchObject({
      status: "not-required",
    });
    expect(files.contents.get(leftover)).toBe("user leftover");
    const globalRoot = resolve(agentDirectory, "..", "skills");
    expect(
      files.accesses.filter(
        (path) =>
          path === globalRoot ||
          path.startsWith(`${globalRoot}/`) ||
          path.includes("certified-cleanup"),
      ),
    ).toEqual([]);
  });

  it("Scenario: cleanup 不因外部 Skills installer 失败而推迟", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-composite-cleanup-"));
    tempRoots.push(root);
    const leftoverName = "gherkin-bdd";
    const leftover = join(root, "skills", leftoverName);
    await mkdir(join(root, "skills"), { recursive: true });
    await mkdir(join(root, "kit", leftoverName), { recursive: true });
    await mkdir(leftover, { recursive: true });
    await writeFile(join(leftover, "SKILL.md"), "same\n");
    await writeFile(join(root, "kit", leftoverName, "SKILL.md"), "same\n");
    const mcpPath = join(root, "agent", "mcp.json");
    await mkdir(join(root, "agent"), { recursive: true });
    await writeFile(mcpPath, JSON.stringify({ mcpServers: {} }));
    const files = createNodeFileAdapter();
    let leftoverPresentWhenInstallerRan: boolean | undefined;
    const runtime: CanonicalOnboardRuntime = {
      async run() {
        leftoverPresentWhenInstallerRan = await files.exists(leftover);
        throw new Error("installer blocked");
      },
    };
    const service = createCompositeOnboardService({
      agents: agents(),
      scope: "all",
      projectRoot: join(root, "project"),
      agentDirectory: join(root, "agent"),
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      mcpConfigPath: mcpPath,
      identity,
      onboardProfileId: "omp-p0-standard-v1",
      route: "auto",
      runtime,
      files,
      now: () => now,
      operationId: () => "composite-operation",
      listDir: async () => [],
      process: {
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      },
    });
    const plan = await service.plan({});
    const approvals = emptyApprovalSet();
    approvals["managed-files"] = true;
    const applied = await service.apply(plan, approvals);
    expect(leftoverPresentWhenInstallerRan).toBe(false);
    expect(applied.participants.certifiedCleanup).toMatchObject({
      status: "applied",
    });
    expect(applied.participants.skills.status).toBe("failed");
    expect(
      applied.residuals.some((path) => path.includes("certified-cleanup")),
    ).toBe(true);
    expect(await files.exists(leftover)).toBe(false);
  });

  it("Scenario: 未批准 managed-files 时不搬走 leftover", async () => {
    const root = await mkdtemp(join(tmpdir(), "m3-composite-skip-"));
    tempRoots.push(root);
    const leftover = join(root, "skills", "gherkin-bdd");
    await mkdir(leftover, { recursive: true });
    await mkdir(join(root, "kit", "gherkin-bdd"), { recursive: true });
    await writeFile(join(leftover, "SKILL.md"), "same\n");
    await writeFile(join(root, "kit", "gherkin-bdd", "SKILL.md"), "same\n");
    const mcpPath = join(root, "agent", "mcp.json");
    await mkdir(join(root, "agent"), { recursive: true });
    await writeFile(mcpPath, JSON.stringify({ mcpServers: {} }));
    const files = createNodeFileAdapter();
    const service = createCompositeOnboardService({
      agents: agents(),
      scope: "all",
      projectRoot: join(root, "project"),
      agentDirectory: join(root, "agent"),
      globalSkillsDirectory: join(root, "skills"),
      kitBundledSkillsRoot: join(root, "kit"),
      mcpConfigPath: mcpPath,
      identity,
      onboardProfileId: "omp-p0-standard-v1",
      route: "auto",
      runtime: undefined,
      files,
      now: () => now,
      operationId: () => "composite-operation",
      listDir: async () => [],
      process: {
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      },
    });
    const plan = await service.plan({});
    const approvals = emptyApprovalSet();
    approvals["mcp-config"] = true;
    const applied = await service.apply(plan, approvals);
    expect(applied.kind).not.toBe("cancelled");
    expect(applied.participants.certifiedCleanup).toMatchObject({
      status: "skipped-not-approved",
    });
    expect(await files.exists(join(leftover, "SKILL.md"))).toBe(true);
  });

  it("Scenario: packaged inventory 变化后 Apply 因 certifiedSkills 过期而 stale", async () => {
    const mcpPath = resolve(agentDirectory, "mcp.json");
    const files = memoryFiles({
      [mcpPath]: JSON.stringify({ mcpServers: {} }),
    });
    const service = createCompositeOnboardService({
      agents: agents(),
      scope: "all",
      projectRoot,
      agentDirectory,
      globalSkillsDirectory: resolve(agentDirectory, "..", "skills"),
      kitBundledSkillsRoot: resolve(agentDirectory, "kit-bundled-skills"),
      mcpConfigPath: mcpPath,
      identity,
      onboardProfileId: "omp-p0-standard-v1",
      route: "auto",
      runtime: undefined,
      files,
      now: () => now,
      operationId: () => "composite-operation",
      listDir: async () => [],
      process: {
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      },
    });
    const plan = await service.plan({});
    const approvals = emptyApprovalSet();
    approvals["managed-files"] = true;
    const tampered = {
      ...plan,
      certifiedSkills: {
        ...plan.certifiedSkills,
        names: [...plan.certifiedSkills.names, "forged-skill"],
        packagedCount: plan.certifiedSkills.packagedCount + 1,
      },
    };
    await expect(service.apply(tampered, approvals)).resolves.toMatchObject({
      kind: "stale",
      participants: {},
    });
  });
});
