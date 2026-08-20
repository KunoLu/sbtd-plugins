import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import extension from "../src/extension.ts";
import { createBookGatePlan } from "../src/gates/index.ts";
import {
  createStateService,
  defaultSessionState,
  SBTD_STATE_CUSTOM_TYPE,
} from "../src/state/index.ts";
import { classifyTask } from "../src/workflow/index.ts";

const managedState = () => ({
  ...defaultSessionState("2026-07-25T00:00:00.000Z"),
  runtimeMode: "enforced" as const,
  environmentObservation: {
    observedAt: "2026-07-25T00:00:00.000Z",
    mode: "managed" as const,
    evidence: ["managed"],
    repairPath: "/sbtd doctor",
  },
});

function registerExtension(entries: unknown[]) {
  const events = new Map<
    string,
    (event: unknown, ctx: unknown) => Promise<unknown>
  >();
  extension({
    registerCommand() {},
    on(
      name: string,
      handler: (event: unknown, ctx: unknown) => Promise<unknown>,
    ) {
      events.set(name, handler);
    },
    appendEntry(customType: string, data: unknown) {
      entries.push({ customType, data });
    },
    async exec() {
      return { code: 0, killed: false, stderr: "", stdout: "" };
    },
  } as never);
  return events;
}

describe("Feature: SBTD 运行时工作流与门禁", () => {
  it("Scenario: preflight-only 阻断普通写入 Tool Call", async () => {
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
        },
      },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };

    await expect(
      events.get("tool_call")?.(
        { toolName: "write", input: { path: "src/changed.ts" } },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("preflight-only"),
    });
  });

  it("Scenario: 间接秘密读取和安装别名在 Host Tool Call 前被阻断", async () => {
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };

    await expect(
      events.get("tool_call")?.(
        { toolName: "bash", input: { command: "bash -c 'cat .env'" } },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("secret-read-guard"),
    });
    await expect(
      events.get("tool_call")?.(
        {
          toolName: "bash",
          input: { command: "corepack pnpm add example-package" },
        },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });
  });

  it("Scenario: 绝对路径的规划产物不被未通过 Book Gate 阻断", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-planning-path-"));
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    try {
      const events = registerExtension(entries);
      const context = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
      };
      await events.get("before_agent_start")?.(
        { prompt: "Fix an existing production bug." },
        context,
      );

      await expect(
        events.get("tool_call")?.(
          {
            toolName: "write",
            input: { path: resolve(root, "features", "bug-fix.feature") },
          },
          context,
        ),
      ).resolves.toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 未提供工作目录时相对规划产物不被未通过 Book Gate 阻断", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-planning-path-no-cwd-"));
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    try {
      const events = registerExtension(entries);
      const context: {
        cwd: string | undefined;
        sessionManager: { getBranch: () => unknown[] };
      } = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
      };
      await events.get("before_agent_start")?.(
        { prompt: "Fix an existing production bug." },
        context,
      );
      context.cwd = undefined;

      await expect(
        events.get("tool_call")?.(
          { toolName: "write", input: { path: "features/bug-fix.feature" } },
          context,
        ),
      ).resolves.toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 正式交付证据必须是同名的新鲜常规文件", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-report-file-type-"));
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    try {
      const events = registerExtension(entries);
      const context = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
      };
      await events.get("before_agent_start")?.(
        { prompt: "Run the Playwright web E2E regression." },
        context,
      );
      const reports = resolve(root, "tests", "e2e", "reports", "html");
      await Promise.all([
        mkdir(resolve(reports, "playwright-report-fresh.html"), {
          recursive: true,
        }),
        mkdir(resolve(reports, "playwright-report-fresh.md"), {
          recursive: true,
        }),
      ]);

      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          context,
        ),
      ).resolves.toMatchObject({
        decision: "block",
        reason: expect.stringContaining("report-artifact-required"),
      });
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: BDD 交付证据必须是新鲜常规文件", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-bdd-file-type-"));
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    try {
      const events = registerExtension(entries);
      const context = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
      };
      await events.get("before_agent_start")?.(
        { prompt: "Add a user-visible UI change." },
        context,
      );
      await mkdir(resolve(root, "features", "ui-change.feature"), {
        recursive: true,
      });

      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          context,
        ),
      ).resolves.toMatchObject({
        decision: "block",
        reason: expect.stringContaining("bdd-required-for-visible-behavior"),
      });
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 缺少稳定 Session ID 的并发 Context 不共享 Tool 审批", async () => {
    const entriesA: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    const entriesB = structuredClone(entriesA);
    const events = registerExtension(entriesA);
    const contextA = {
      cwd: "/project-a",
      sessionManager: { getBranch: () => entriesA },
    };
    const contextB = {
      cwd: "/project-b",
      sessionManager: { getBranch: () => entriesB },
    };

    await events.get("tool_approval_resolved")?.(
      { toolCallId: "install-1", approved: true },
      contextA,
    );
    await expect(
      events.get("tool_call")?.(
        {
          toolCallId: "install-1",
          toolName: "bash",
          input: { command: "npm install example-package" },
        },
        contextB,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });
  });

  it("Scenario: Release Route 需要 Release Readiness Gate", () => {
    const entries: unknown[] = [];
    const service = createStateService({
      replay: () => entries,
      append: (customType, data) => {
        entries.push({ customType, data });
      },
    });
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: false,
      existingBehaviorBug: false,
      dataRisk: false,
      productionPathRisk: false,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
      releaseOrDeploy: true,
    });

    const plan = createBookGatePlan(classification);
    expect(classification).toMatchObject({ route: "release-readiness" });
    expect(plan).toContainEqual(
      expect.objectContaining({
        id: "release-readiness",
        required: true,
        gateState: "planned",
      }),
    );
    expect(service.recordWorkflow(classification, plan).activeSkills).toContain(
      "book-release-readiness",
    );
  });

  it("Scenario: 终态阶段重放保持终态", () => {
    const entries: unknown[] = [];
    const service = createStateService(
      {
        replay: () => entries,
        append: (customType, data) => {
          entries.push({ customType, data });
        },
      },
      () => "2026-07-25T00:00:00.000Z",
    );
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: false,
      existingBehaviorBug: false,
      dataRisk: false,
      productionPathRisk: false,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    const initial = service.recordWorkflow(
      classification,
      createBookGatePlan(classification),
    );
    entries.push({
      customType: SBTD_STATE_CUSTOM_TYPE,
      data: {
        ...initial,
        stage: {
          id: "implementation",
          stageStatus: "passed",
          completedAt: "2026-07-25T00:00:00.000Z",
        },
      },
    });
    const entryCount = entries.length;

    expect(
      service.requestStageTransition("implementation").stage,
    ).toMatchObject({
      id: "implementation",
      stageStatus: "passed",
    });
    expect(entries).toHaveLength(entryCount);
  });

  it("Scenario: 精确批准的秘密读取只放行一次", async () => {
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };
    const secretCall = {
      toolCallId: "call-secret-1",
      toolName: "read",
      input: { path: ".env" },
    };

    await expect(
      events.get("tool_call")?.(secretCall, context),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("secret-read-guard"),
    });
    await events.get("tool_approval_resolved")?.(
      { toolCallId: "call-secret-1", toolName: "read", approved: true },
      context,
    );
    await expect(
      events.get("tool_call")?.(secretCall, context),
    ).resolves.toBeUndefined();
    await events.get("tool_result")?.(
      {
        toolCallId: "call-secret-1",
        input: { path: ".env" },
        content: [],
        isError: false,
      },
      context,
    );
    // One-shot: the exact same call is blocked again after the result.
    await expect(
      events.get("tool_call")?.(secretCall, context),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("secret-read-guard"),
    });
  });

  it("Scenario: 安装批准与秘密读取批准不互换", async () => {
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };
    const secretCall = {
      toolCallId: "call-cross-1",
      toolName: "read",
      input: { path: ".env" },
    };
    await expect(
      events.get("tool_call")?.(secretCall, context),
    ).resolves.toMatchObject({ block: true });
    await events.get("tool_approval_resolved")?.(
      { toolCallId: "call-cross-1", toolName: "read", approved: true },
      context,
    );
    // Reusing the approval for a dependency install stays blocked and evicts
    // the mismatched descriptor.
    await expect(
      events.get("tool_call")?.(
        {
          toolCallId: "call-cross-1",
          toolName: "bash",
          input: { command: "npm install example-package" },
        },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });
    await expect(
      events.get("tool_call")?.(secretCall, context),
    ).resolves.toMatchObject({ block: true });
  });

  it("Scenario: 批准后变更命令或拒绝批准保持阻断", async () => {
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };

    await expect(
      events.get("tool_call")?.(
        {
          toolCallId: "call-install-1",
          toolName: "bash",
          input: { command: "npm install example-package" },
        },
        context,
      ),
    ).resolves.toMatchObject({ block: true });
    await events.get("tool_approval_resolved")?.(
      { toolCallId: "call-install-1", toolName: "bash", approved: true },
      context,
    );
    // Changed target after approval: fingerprint mismatch stays blocked.
    await expect(
      events.get("tool_call")?.(
        {
          toolCallId: "call-install-1",
          toolName: "bash",
          input: { command: "npm install other-package" },
        },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });

    await expect(
      events.get("tool_call")?.(
        {
          toolCallId: "call-denied-1",
          toolName: "bash",
          input: { command: "brew install wget" },
        },
        context,
      ),
    ).resolves.toMatchObject({ block: true });
    await events.get("tool_approval_resolved")?.(
      { toolCallId: "call-denied-1", toolName: "bash", approved: false },
      context,
    );
    await expect(
      events.get("tool_call")?.(
        {
          toolCallId: "call-denied-1",
          toolName: "bash",
          input: { command: "brew install wget" },
        },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });
  });

  it("Scenario: preflight-only 下安全诊断 Tool Call 保持可用", async () => {
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
        },
      },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };

    for (const event of [
      { toolName: "read", input: { path: "src/app.ts" } },
      { toolName: "grep", input: { pattern: "TODO", path: "src" } },
      { toolName: "glob", input: { pattern: "src/**/*.ts" } },
      { toolName: "ast_grep", input: { pattern: "console.log($$$)" } },
      { toolName: "mcp__gitnexus__debug", input: { query: "auth flow" } },
    ])
      await expect(
        events.get("tool_call")?.(event, context),
      ).resolves.toBeUndefined();
  });

  it("Scenario: preflight-only 下未知与远程 Tool Call fail closed", async () => {
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
        },
      },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };

    await expect(
      events.get("tool_call")?.(
        { toolName: "mcp__unknown__custom", input: { path: "src/app.ts" } },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("preflight-only"),
    });
    await expect(
      events.get("tool_call")?.(
        { toolName: "read", input: { path: "ssh://deploy-host/app/logs" } },
        context,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("preflight-only"),
    });
  });

  it("Scenario: 混合公开配置的读取不被误判为秘密访问", async () => {
    const entries: unknown[] = [
      { customType: SBTD_STATE_CUSTOM_TYPE, data: managedState() },
    ];
    const events = registerExtension(entries);
    const context = {
      cwd: "/project",
      sessionManager: { getBranch: () => entries },
    };

    for (const path of [
      "appsettings.Development.json",
      "certs/localhost.crt",
      ".env.example",
      ".ssh/id_rsa.pub",
    ])
      await expect(
        events.get("tool_call")?.(
          { toolName: "read", input: { path } },
          context,
        ),
      ).resolves.toBeUndefined();
    // Mention-style search over a quoted pattern is not a secret read.
    await expect(
      events.get("tool_call")?.(
        {
          toolName: "bash",
          input: { command: "grep '.env' src/config.ts" },
        },
        context,
      ),
    ).resolves.toBeUndefined();
  });
});
