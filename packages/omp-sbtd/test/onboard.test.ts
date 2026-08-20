import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { renderManagedBlock, sha256 } from "../src/agents/index.ts";
import {
  createNodeFileAdapter,
  createOnboardService,
  type FileAdapter,
} from "../src/onboard/index.ts";

const projectRoot = "/work/project";
const agentDirectory = "/work/agent";
const kit = {
  sourceId: "sbtd-workflow-kit-upstream",
  sourceRevision: "340f9dd4dc7a92e8b91c31e111de9a8de06cef36",
  transformVersion: "p0-v1",
  kitRevision: "kit-digest",
  templates: {
    global: "# Global rules",
    "project-root": "# Root facts",
    "project-omp": "@../AGENTS.md\n# OMP adapter",
  },
};

function memoryFiles(
  initial: Record<string, string> = {},
  failurePath?: string,
): FileAdapter & {
  readonly files: Map<string, string>;
  readonly writes: string[];
  readonly symlinks: Set<string>;
} {
  const files = new Map(Object.entries(initial));
  const writes: string[] = [];
  const directories = new Set<string>();
  const symlinks = new Set<string>();
  return {
    files,
    writes,
    symlinks,
    async readText(path) {
      return files.get(path);
    },
    async writeAtomic(path, content) {
      if (path === failurePath) throw new Error("injected write failure");
      writes.push(path);
      files.set(path, content);
    },
    async makeDirectory(path) {
      if (directories.has(path)) throw new Error("lock already held");
      directories.add(path);
    },
    async exists(path) {
      return files.has(path) || directories.has(path);
    },
    async remove(path) {
      files.delete(path);
      directories.delete(path);
    },
    async isSymlink(path) {
      return symlinks.has(path);
    },
  };
}

function service(
  files: FileAdapter,
  now = () => "2026-07-24T00:00:00.000Z",
  scope: "all" | "projects" = "all",
) {
  return createOnboardService({
    projectRoot,
    scope,
    agentDirectory,
    kit,
    files,
    now,
    operationId: () => "operation-1",
  });
}

describe("Feature: SBTD 控制引导", () => {
  it("Scenario: 首次 Apply 可创建事务锁父目录", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-lock-"));
    const lockPath = resolve(root, "kpi/transactions/target.lock");
    try {
      const files = createNodeFileAdapter();
      await files.makeDirectory(lockPath);
      await expect(files.makeDirectory(lockPath)).rejects.toMatchObject({
        code: "EEXIST",
      });
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 预览三层 AGENTS Onboard 计划", async () => {
    const files = memoryFiles();
    const before = new Map(files.files);
    const plan = await service(files).plan();
    expect(plan.targets).toHaveLength(3);
    expect(plan.targets.every((target) => target.action === "write")).toBe(
      true,
    );
    expect(plan.kit).toMatchObject({
      sourceId: kit.sourceId,
      sourceRevision: kit.sourceRevision,
      kitRevision: kit.kitRevision,
    });
    expect(files.files).toEqual(before);
    expect(files.writes).toEqual([]);
  });

  it("Scenario: Project-only Plan 不写入全局 AGENTS", async () => {
    const plan = await service(
      memoryFiles(),
      () => "2026-07-24T00:00:00.000Z",
      "projects",
    ).plan();
    expect(plan.targets.map((target) => target.target.role)).toEqual([
      "project-root",
      "project-omp",
    ]);
  });

  it("Scenario: 用户取消 Onboard Apply", async () => {
    const files = memoryFiles({
      [resolve(projectRoot, "AGENTS.md")]: "user root\n",
    });
    const onboard = service(files);
    const plan = await onboard.plan();
    const before = new Map(files.files);
    expect(await onboard.apply(plan, false)).toMatchObject({
      kind: "cancelled",
    });
    expect(files.files).toEqual(before);
    expect(files.writes).toEqual([]);
  });

  it("Scenario: 用户确认安装三层 Managed Block", async () => {
    const global = resolve(agentDirectory, "AGENTS.md");
    const root = resolve(projectRoot, "AGENTS.md");
    const omp = resolve(projectRoot, ".omp/AGENTS.md");
    const files = memoryFiles({
      [global]: "global user\n",
      [root]: "root user\n",
      [omp]: "omp user\n",
    });
    const onboard = service(files);
    const result = await onboard.apply(await onboard.plan(), true);
    expect(result).toMatchObject({ kind: "applied", reloadRequired: true });
    expect(files.files.get(global)).toContain(
      "global user\n<!-- kpi:managed-begin role=global",
    );
    expect(files.files.get(root)).toContain(
      "root user\n<!-- kpi:managed-begin role=project-root",
    );
    expect(files.files.get(omp)).toContain("@../AGENTS.md");
    expect(files.files.get(omp)).toContain(
      "<!-- kpi:managed-begin role=project-omp",
    );

    const journal = JSON.parse(
      files.files.get(
        resolve(agentDirectory, "kpi/transactions/operation-1.journal.json"),
      ) as string,
    );
    expect(journal).toMatchObject({
      operationId: "operation-1",
      phase: "complete",
      written: [
        global,
        root,
        omp,
        resolve(agentDirectory, "kpi/provenance/inventory-v1.json"),
      ],
      residuals: [],
    });
  });

  it("Scenario: Project-only Apply 保留全局 Managed Asset 的 provenance", async () => {
    const files = memoryFiles();
    const initial = service(files);
    await expect(
      initial.apply(await initial.plan(), true),
    ).resolves.toMatchObject({
      kind: "applied",
    });
    const upgradedKit = {
      ...kit,
      templates: {
        ...kit.templates,
        "project-root": `${kit.templates["project-root"]}\nupdated\n`,
      },
    };
    const projectOnly = createOnboardService({
      projectRoot,
      scope: "projects",
      agentDirectory,
      kit: upgradedKit,
      files,
      now: () => "2026-07-24T00:00:00.000Z",
      operationId: () => "operation-2",
    });
    await expect(
      projectOnly.apply(await projectOnly.plan(), true),
    ).resolves.toMatchObject({ kind: "applied" });
    const fullPlan = await createOnboardService({
      projectRoot,
      agentDirectory,
      kit: upgradedKit,
      files,
      now: () => "2026-07-24T00:00:00.000Z",
      operationId: () => "operation-3",
    }).plan();

    expect(
      fullPlan.targets.find((target) => target.target.role === "global"),
    ).toMatchObject({ priorState: "exact", action: "skip" });
  });

  it("Scenario: 目标在 Plan 后发生变化", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const files = memoryFiles({ [root]: "original\n" });
    const onboard = service(files);
    const plan = await onboard.plan();
    files.files.set(root, "changed after plan\n");
    const beforeWrites = files.writes.length;
    expect(await onboard.apply(plan, true)).toMatchObject({ kind: "stale" });
    expect(files.writes).toHaveLength(beforeWrites);
    expect(files.files.get(root)).toBe("changed after plan\n");
  });

  it("Scenario: Managed Block 标记损坏时拒绝覆盖", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const files = memoryFiles({
      [root]: "<!-- kpi:managed-begin role=project-root source=x -->\n",
    });
    const plan = await service(files).plan();
    expect(
      plan.targets.find((target) => target.target.path === root),
    ).toMatchObject({ priorState: "blocked", action: "blocked" });
  });

  it("Scenario: 不安全或符号链接目标被阻止", async () => {
    const files = memoryFiles();
    files.symlinks.add(resolve(projectRoot, "AGENTS.md"));
    const plan = await service(files).plan();
    expect(
      plan.targets.find((target) => target.target.role === "project-root"),
    ).toMatchObject({ action: "blocked" });
    expect(files.writes).toEqual([]);
  });

  it("Scenario: 上一次 Apply 写入失败后回滚并保留 repair facts", async () => {
    const global = resolve(agentDirectory, "AGENTS.md");
    const root = resolve(projectRoot, "AGENTS.md");
    const files = memoryFiles(
      { [global]: "keep global\n", [root]: "keep root\n" },
      resolve(projectRoot, ".omp/AGENTS.md"),
    );
    const onboard = service(files);
    const result = await onboard.apply(await onboard.plan(), true);
    expect(result).toMatchObject({ kind: "rolled-back", residuals: [] });
    expect(files.files.get(global)).toBe("keep global\n");
    expect(files.files.get(root)).toBe("keep root\n");
    expect(
      files.files.get(
        resolve(agentDirectory, "kpi/transactions/operation-1.journal.json"),
      ),
    ).toBeUndefined();
  });

  it("Scenario: 无 Provenance Inventory 的 Managed Block 不被覆盖", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const files = memoryFiles({
      [root]: renderManagedBlock({
        role: "project-root",
        sourceId: kit.sourceId,
        sourceRevision: kit.sourceRevision,
        transformVersion: kit.transformVersion,
        content: kit.templates["project-root"],
      }),
    });

    const plan = await service(files).plan();

    expect(
      plan.targets.find((target) => target.target.path === root),
    ).toMatchObject({ priorState: "merge-required", action: "blocked" });
    expect(files.files.get(root)).toContain("kpi:managed-begin");
  });

  it("Scenario: 已记录 Managed Block 内容漂移时要求显式修复", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const installed = kit.templates["project-root"];
    const files = memoryFiles({
      [root]: renderManagedBlock({
        role: "project-root",
        sourceId: kit.sourceId,
        sourceRevision: kit.sourceRevision,
        transformVersion: kit.transformVersion,
        content: `${installed}\nuser changed managed content`,
      }),
      [resolve(agentDirectory, "kpi/provenance/inventory-v1.json")]:
        JSON.stringify({
          schemaVersion: 1,
          revision: sha256("inventory-v1"),
          operationId: "previous-operation",
          assets: [
            {
              path: root,
              role: "project-root",
              sourceId: kit.sourceId,
              sourceRevision: kit.sourceRevision,
              transformVersion: kit.transformVersion,
              digest: sha256(installed),
            },
          ],
        }),
    });

    const plan = await service(files).plan();

    expect(
      plan.targets.find((target) => target.target.path === root),
    ).toMatchObject({ priorState: "merge-required", action: "blocked" });
  });

  it("Scenario: Doctor 将残留 target-set lock 报告为显式修复", async () => {
    const lockKey = sha256(
      [
        resolve(agentDirectory, "AGENTS.md"),
        resolve(projectRoot, ".omp/AGENTS.md"),
        resolve(projectRoot, "AGENTS.md"),
      ]
        .sort()
        .join("\u0000"),
    );
    const lockPath = resolve(
      agentDirectory,
      `kpi/transactions/${lockKey}.lock`,
    );
    const files = memoryFiles();
    await files.makeDirectory(lockPath);
    const onboard = service(files);

    await expect(onboard.inspectRecovery()).resolves.toMatchObject({
      kind: "repair-required",
      residuals: [lockPath],
    });
    await expect(onboard.recover()).resolves.toMatchObject({
      kind: "rolled-back",
      residuals: [],
    });
    await expect(onboard.inspectRecovery()).resolves.toMatchObject({
      kind: "none",
    });
  });

  it("Scenario: Doctor 可从持久备份恢复中断的 Apply", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const journalPath = resolve(
      agentDirectory,
      "kpi/transactions/operation-1.journal.json",
    );
    const recoveryPath = resolve(
      agentDirectory,
      "kpi/transactions/recovery-v1.json",
    );
    const backupPath = resolve(
      agentDirectory,
      "kpi/transactions/operation-1.backups/0.backup",
    );
    const original = "root before\n";
    const files = memoryFiles({
      [root]: "partial replacement\n",
      [backupPath]: original,
      [journalPath]: JSON.stringify({
        schemaVersion: 1,
        operationId: "operation-1",
        phase: "writing",
        planDigest: sha256("plan"),
        backups: [
          {
            path: root,
            backupPath,
            digest: sha256(original),
            exists: true,
          },
        ],
        written: [root],
        residuals: [],
      }),
      [recoveryPath]: JSON.stringify({ schemaVersion: 1, journalPath }),
    });
    const onboard = service(files);
    await expect(onboard.inspectRecovery()).resolves.toMatchObject({
      kind: "repair-required",
      operationId: "operation-1",
      phase: "writing",
      journalPath,
      backups: [backupPath],
      residuals: [],
    });
    expect(files.files.get(root)).toBe("partial replacement\n");

    await expect(onboard.recover()).resolves.toMatchObject({
      kind: "rolled-back",
      residuals: [],
    });
    expect(files.files.get(root)).toBe(original);
    expect(files.files.get(journalPath)).toBeUndefined();
    expect(files.files.get(recoveryPath)).toBeUndefined();
  });
  it("Scenario: Doctor 清理完成事务的遗留 lock 而不回滚目标", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const operationId = "operation-complete";
    const journalPath = resolve(
      agentDirectory,
      `kpi/transactions/${operationId}.journal.json`,
    );
    const recoveryPath = resolve(
      agentDirectory,
      "kpi/transactions/recovery-v1.json",
    );
    const lockPath = resolve(
      agentDirectory,
      `kpi/transactions/${sha256(
        [
          resolve(agentDirectory, "AGENTS.md"),
          resolve(projectRoot, ".omp/AGENTS.md"),
          root,
        ]
          .sort()
          .join("\u0000"),
      )}.lock`,
    );
    const files = memoryFiles({
      [root]: "installed managed block\n",
      [journalPath]: JSON.stringify({
        schemaVersion: 1,
        operationId,
        phase: "complete",
        planDigest: sha256("plan"),
        backups: [],
        written: [],
        residuals: [],
      }),
      [recoveryPath]: JSON.stringify({ schemaVersion: 1, journalPath }),
    });
    await files.makeDirectory(lockPath);
    const onboard = service(files);

    await expect(onboard.recover()).resolves.toMatchObject({
      kind: "rolled-back",
      residuals: [],
    });
    expect(files.files.get(root)).toBe("installed managed block\n");
    expect(files.files.get(journalPath)).toBeUndefined();
    expect(files.files.get(recoveryPath)).toBeUndefined();
    await expect(onboard.inspectRecovery()).resolves.toMatchObject({
      kind: "none",
    });
  });

  it("Scenario: Doctor 拒绝越过事务备份根目录的伪造恢复日志", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const journalPath = resolve(
      agentDirectory,
      "kpi/transactions/operation-1.journal.json",
    );
    const recoveryPath = resolve(
      agentDirectory,
      "kpi/transactions/recovery-v1.json",
    );
    const files = memoryFiles({
      [root]: "partial replacement\n",
      [journalPath]: JSON.stringify({
        schemaVersion: 1,
        operationId: "operation-1",
        phase: "writing",
        planDigest: sha256("plan"),
        backups: [
          {
            path: root,
            backupPath: "/outside/secret.backup",
            digest: sha256("secret"),
            exists: true,
          },
        ],
        written: [root],
        residuals: [],
      }),
      [recoveryPath]: JSON.stringify({ schemaVersion: 1, journalPath }),
    });
    const onboard = service(files);

    await expect(onboard.inspectRecovery()).resolves.toMatchObject({
      kind: "repair-required",
      residuals: [journalPath],
    });
    await expect(onboard.recover()).resolves.toMatchObject({
      kind: "repair-required",
    });
    expect(files.files.get(root)).toBe("partial replacement\n");
  });

  it("Scenario: Apply 忽略被篡改的 Plan 文件内容", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const files = memoryFiles();
    const onboard = service(files);
    const plan = await onboard.plan();
    const tampered = {
      ...plan,
      proposedFiles: { ...plan.proposedFiles, [root]: "tampered\n" },
    };

    expect(await onboard.apply(tampered, true)).toMatchObject({
      kind: "applied",
    });
    expect(files.files.get(root)).toContain("# Root facts");
    expect(files.files.get(root)).not.toBe("tampered\n");
  });

  it("Scenario: 锁定后目标变化使 Apply 失效", async () => {
    const root = resolve(projectRoot, "AGENTS.md");
    const files = memoryFiles();
    const originalMakeDirectory = files.makeDirectory.bind(files);
    const onboard = service({
      ...files,
      async makeDirectory(path) {
        await originalMakeDirectory(path);
        files.files.set(root, "changed while acquiring lock\n");
      },
    });
    const plan = await onboard.plan();

    expect(await onboard.apply(plan, true)).toMatchObject({ kind: "stale" });
    expect(files.files.get(root)).toBe("changed while acquiring lock\n");
  });

  it("Scenario: 完成的 Onboard operation 可安全重试", async () => {
    const files = memoryFiles();
    const onboard = service(files);
    const plan = await onboard.plan();
    await expect(onboard.apply(plan, true)).resolves.toMatchObject({
      kind: "applied",
    });
    const writes = files.writes.length;

    await expect(onboard.apply(plan, true)).resolves.toMatchObject({
      kind: "applied",
    });
    expect(files.writes).toHaveLength(writes);
  });

  it("Scenario: 完成的 operation 在 Plan 过期后仍可安全重试", async () => {
    let now = "2026-07-24T00:00:00.000Z";
    const files = memoryFiles();
    const onboard = service(files, () => now);
    const plan = await onboard.plan();
    await expect(onboard.apply(plan, true)).resolves.toMatchObject({
      kind: "applied",
    });
    const writes = files.writes.length;
    now = "2026-07-24T00:11:00.000Z";

    await expect(onboard.apply(plan, true)).resolves.toMatchObject({
      kind: "applied",
      reloadRequired: true,
    });
    expect(files.writes).toHaveLength(writes);
  });
});
