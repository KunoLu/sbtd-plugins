import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  symlink,
  utimes,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";
import extension from "../src/extension.ts";
import { createBookGatePlan } from "../src/gates/index.ts";
import {
  defaultSessionState,
  SBTD_STATE_CUSTOM_TYPE,
} from "../src/state/index.ts";
import { classifyTask } from "../src/workflow/index.ts";

const fixtureRoot = resolve(
  import.meta.dirname,
  "fixtures",
  "validation-evidence-v2",
);

describe("Feature: SBTD 控制引导", () => {
  it("Scenario: Extension factory 只注册一个 sbtd 命令且不执行运行时动作", async () => {
    const commands: Array<{
      name: string;
      options: {
        handler: (args: string, ctx: unknown) => Promise<void>;
        getArgumentCompletions?: (prefix: string) => unknown;
      };
    }> = [];
    const events: string[] = [];
    let appends = 0;
    extension({
      registerCommand(
        name: string,
        options: {
          handler: (args: string, ctx: unknown) => Promise<void>;
          getArgumentCompletions?: (prefix: string) => unknown;
        },
      ) {
        commands.push({ name, options });
      },
      on(name: string) {
        events.push(name);
      },
      appendEntry() {
        appends += 1;
      },
    } as never);
    expect(commands).toHaveLength(1);
    expect(commands[0]?.name).toBe("sbtd");
    expect(events).toEqual([
      "session_start",
      "session_switch",
      "session_branch",
      "session_tree",
      "before_agent_start",
      "session.compacting",
      "tool_call",
      "tool_approval_resolved",
      "tool_result",
      "turn_start",
      "turn_end",
      "session_stop",
      "credential_disabled",
    ]);
    expect(appends).toBe(0);
    expect(commands[0]?.options.getArgumentCompletions?.("onboard ")).toEqual([
      { value: "onboard bootstrap", label: "onboard bootstrap" },
      { value: "onboard init", label: "onboard init" },
      { value: "onboard init-projects", label: "onboard init-projects" },
      { value: "onboard plan", label: "onboard plan" },
      { value: "onboard reset", label: "onboard reset" },
      { value: "onboard skip apply", label: "onboard skip apply" },
      { value: "onboard skip list", label: "onboard skip list" },
      {
        value: "onboard skip plan create",
        label: "onboard skip plan create",
      },
      {
        value: "onboard skip plan expire",
        label: "onboard skip plan expire",
      },
      {
        value: "onboard skip plan revoke",
        label: "onboard skip plan revoke",
      },
      { value: "onboard status", label: "onboard status" },
    ]);
  });

  it("Scenario: 已提交 AcceptedSkip Plan 重放不重复写入", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const notices: string[] = [];
    const entries: unknown[] = [];
    const entryTypes: string[] = [];
    const sessionManager = { getBranch: () => entries };
    const root = await mkdtemp(resolve(tmpdir(), "kpi-skip-plan-root-"));
    const changedScopeRoot = await mkdtemp(
      resolve(tmpdir(), "kpi-skip-plan-changed-scope-"),
    );
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-skip-plan-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-07-25T00:00:00.000Z"));
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry(type: string, data: unknown) {
          entryTypes.push(type);
          entries.push(data);
        },
      } as never);
      await commands[0]?.options.handler(
        'onboard skip plan create ui --scope project --expires 2026-08-01T00:00:00.000Z --reason "temporary local exemption"',
        {
          cwd: root,
          ui: {
            notify(message: string) {
              notices.push(message);
            },
          },
          sessionManager,
        },
      );

      const plan = JSON.parse(notices.at(-1) as string);
      expect(plan).toMatchObject({
        action: "create",
        create: {
          capability: "ui",
          reason: "temporary local exemption",
        },
        confirmation: "required for Apply",
      });
      await expect(
        readFile(
          resolve(agentDirectory, "kpi/provenance/accepted-skips-v1.json"),
          "utf8",
        ),
      ).rejects.toMatchObject({ code: "ENOENT" });
      expect(entries).toEqual([]);
      let confirmations = 0;
      await commands[0]?.options.handler(`onboard skip apply ${plan.digest}`, {
        cwd: root,
        ui: {
          async confirm() {
            confirmations += 1;
            return true;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      expect(confirmations).toBe(1);
      await expect(
        readFile(
          resolve(agentDirectory, "kpi/provenance/accepted-skips-v1.json"),
          "utf8",
        ),
      ).resolves.toContain('"status": "active"');
      const skipStorePath = resolve(
        agentDirectory,
        "kpi/provenance/accepted-skips-v1.json",
      );
      const activeStore = JSON.parse(await readFile(skipStorePath, "utf8")) as {
        records: Array<Record<string, unknown>>;
      };
      const activeRecordCount = activeStore.records.length;
      expect(activeRecordCount).toBe(1);
      const storeBeforeExactReplay = await readFile(skipStorePath, "utf8");
      vi.setSystemTime(new Date("2026-07-25T00:06:00.000Z"));
      await commands[0]?.options.handler(`onboard skip apply ${plan.digest}`, {
        cwd: root,
        ui: {
          async confirm() {
            confirmations += 1;
            return true;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      expect(confirmations).toBe(2);
      await expect(readFile(skipStorePath, "utf8")).resolves.toBe(
        storeBeforeExactReplay,
      );
      expect(entries).toHaveLength(2);
      expect(notices.at(-1)).toContain("is active");
      expect(notices.at(-1)).toContain(plan.create.recordId);
      expect(entryTypes[1]).toBe(SBTD_STATE_CUSTOM_TYPE);
      expect(entries[1]).toMatchObject({
        environmentObservation: {
          mode: "needs-onboard",
          observedAt: "2026-07-25T00:06:00.000Z",
        },
      });
      await commands[0]?.options.handler("onboard skip list", {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      const replayedList = JSON.parse(notices.at(-1) as string) as {
        records: Array<{ recordId: string }>;
      };
      expect(replayedList.records).toHaveLength(1);
      expect(replayedList.records[0]?.recordId).toBe(plan.create.recordId);
      activeStore.records[0] = {
        ...activeStore.records[0],
        createdAt: "2000-01-01T00:00:00.000Z",
        confirmedAt: "2000-01-01T00:00:00.000Z",
        expiresAt: "2000-01-02T00:00:00.000Z",
      };
      await writeFile(skipStorePath, JSON.stringify(activeStore, null, 2));
      await commands[0]?.options.handler(
        `onboard skip plan expire ${plan.create.recordId} --reason "expiry reconciliation"`,
        {
          cwd: root,
          ui: {
            notify(message: string) {
              notices.push(message);
            },
          },
          sessionManager,
        },
      );
      const expiryPlan = JSON.parse(notices.at(-1) as string);
      expect(expiryPlan).toMatchObject({
        action: "expire",
        target: { recordId: plan.create.recordId },
        confirmation: "required for Apply",
      });
      await commands[0]?.options.handler(
        `onboard skip apply ${expiryPlan.digest}`,
        {
          cwd: root,
          ui: {
            async confirm() {
              confirmations += 1;
              return true;
            },
            notify(message: string) {
              notices.push(message);
            },
          },
          sessionManager,
        },
      );
      expect(confirmations).toBe(3);
      await expect(readFile(skipStorePath, "utf8")).resolves.toContain(
        '"status": "expired"',
      );
      await commands[0]?.options.handler("doctor", {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      expect(notices.at(-1)).toContain("AcceptedSkip");
      expect(entries).toHaveLength(3);
      const storeBeforeStaleReplay = await readFile(skipStorePath, "utf8");
      const entriesBeforeStaleReplay = entries.length;
      const confirmationsBeforeStaleReplay = confirmations;
      await commands[0]?.options.handler(`onboard skip apply ${plan.digest}`, {
        cwd: changedScopeRoot,
        ui: {
          async confirm() {
            confirmations += 1;
            return true;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      expect(confirmations).toBe(confirmationsBeforeStaleReplay);
      expect(entries).toHaveLength(entriesBeforeStaleReplay);
      await expect(readFile(skipStorePath, "utf8")).resolves.toBe(
        storeBeforeStaleReplay,
      );
      expect(notices.at(-1)).toContain(
        "bound scope, Profile, Route, capability, or Kit facts changed",
      );
      expect(notices.at(-1)).toContain("Create a new Plan.");
    } finally {
      vi.useRealTimers();
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
      await rm(changedScopeRoot, { force: true, recursive: true });
    }
  });

  it("Scenario: 有相同派生 capability 的 Route 改变时 AcceptedSkip Plan 不能重放", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const notices: string[] = [];
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: { ...defaultSessionState(), route: "small-direct-change" },
      },
    ];
    const sessionManager = { getBranch: () => entries };
    const root = await mkdtemp(resolve(tmpdir(), "kpi-skip-plan-route-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-skip-plan-route-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-07-25T00:00:00.000Z"));
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry(type: string, data: unknown) {
          entries.push({ customType: type, data });
        },
      } as never);
      await commands[0]?.options.handler(
        'onboard skip plan create ui --scope project --expires 2026-08-01T00:00:00.000Z --reason "temporary local exemption"',
        {
          cwd: root,
          ui: {
            notify(message: string) {
              notices.push(message);
            },
          },
          sessionManager,
        },
      );
      const createPlan = JSON.parse(notices.at(-1) as string);
      expect(createPlan.context.route).toBe("small-direct-change");
      let confirmations = 0;
      await commands[0]?.options.handler(
        `onboard skip apply ${createPlan.digest}`,
        {
          cwd: root,
          ui: {
            async confirm() {
              confirmations += 1;
              return true;
            },
            notify(message: string) {
              notices.push(message);
            },
          },
          sessionManager,
        },
      );
      const skipStorePath = resolve(
        agentDirectory,
        "kpi/provenance/accepted-skips-v1.json",
      );
      const latestSessionState = (
        entries.at(-1) as { data: Record<string, unknown> }
      ).data;
      entries.push({
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: { ...latestSessionState, route: "bugfix" },
      });
      const storeBeforeRouteReplay = await readFile(skipStorePath, "utf8");
      const entriesBeforeRouteReplay = entries.length;
      const confirmationsBeforeRouteReplay = confirmations;
      await commands[0]?.options.handler(
        `onboard skip apply ${createPlan.digest}`,
        {
          cwd: root,
          ui: {
            async confirm() {
              confirmations += 1;
              return true;
            },
            notify(message: string) {
              notices.push(message);
            },
          },
          sessionManager,
        },
      );
      expect(confirmations).toBe(confirmationsBeforeRouteReplay);
      expect(entries).toHaveLength(entriesBeforeRouteReplay);
      await expect(readFile(skipStorePath, "utf8")).resolves.toBe(
        storeBeforeRouteReplay,
      );
      expect(notices.at(-1)).toContain(
        "bound scope, Profile, Route, capability, or Kit facts changed",
      );
    } finally {
      vi.useRealTimers();
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: 状态显示锁定 Kit 来源与摘要", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const notices: string[] = [];
    const entries: unknown[] = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-kit-status-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-kit-status-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry(_type: string, data: unknown) {
          entries.push(data);
        },
      } as never);

      await commands[0]?.options.handler("status", {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: { getBranch: () => entries },
      });

      expect(notices.at(-1)).toContain(
        "Kit Source: sbtd-workflow-kit-upstream",
      );
      expect(notices.at(-1)).toContain(
        "Kit Revision: 4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb",
      );
      expect(notices.at(-1)).toMatch(/Kit Manifest Digest: [0-9a-f]{64}/);
      expect(notices.at(-1)).toMatch(
        /Kit Canonical Manifest Digest: [0-9a-f]{64}/,
      );
      expect(notices.at(-1)).toMatch(/Kit Projection Digest: [0-9a-f]{64}/);
      expect(notices.at(-1)).toContain("Kit Freshness: current");
      expect(notices.at(-1)).toContain(
        "Tool Evidence core-gate-skills: installation=installed configuration=configured callability=not-needed",
      );
      expect(notices.at(-1)).toContain(
        "Tool Evidence ui: installation=missing configuration=not-configured callability=not-needed",
      );
      expect(entries).toHaveLength(0);
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: OMP Tool 只在全部必需 Gate 通过后推进阶段", async () => {
    const entries: unknown[] = [];
    const tools: Array<{
      readonly name: string;
      readonly execute: (
        toolCallId: string,
        params: { readonly stageId: string },
        signal: AbortSignal | undefined,
        onUpdate: undefined,
        ctx: {
          readonly sessionManager: {
            readonly getBranch: () => readonly unknown[];
          };
        },
      ) => Promise<{ readonly content: readonly { readonly text: string }[] }>;
    }> = [];
    const classification = classifyTask({
      userVisibleBehavior: false,
      existingProductionCode: true,
      existingBehaviorBug: true,
      dataRisk: false,
      productionPathRisk: false,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });
    const plan = createBookGatePlan(classification);
    entries.push({
      customType: SBTD_STATE_CUSTOM_TYPE,
      data: {
        ...defaultSessionState("2026-07-25T00:00:00.000Z"),
        runtimeMode: "enforced",
        environmentObservation: {
          observedAt: "2026-07-25T00:00:00.000Z",
          mode: "managed",
          evidence: ["all managed"],
          repairPath: "/sbtd status",
        },
        classification,
        bookGates: plan,
      },
    });
    extension({
      registerCommand() {},
      zod: z,
      registerTool(tool: (typeof tools)[number]) {
        tools.push(tool);
      },
      on() {},
      appendEntry(customType: string, data: unknown) {
        entries.push({ customType, data });
      },
    } as never);
    const tool = tools.find((candidate) => candidate.name === "sbtd_workflow");
    const ctx = { sessionManager: { getBranch: () => entries } };

    await expect(
      tool?.execute(
        "stage-1",
        { stageId: "implementation" },
        undefined,
        undefined,
        ctx,
      ),
    ).resolves.toMatchObject({
      content: [
        {
          text: expect.stringContaining("Stage transition blocked"),
        },
      ],
    });

    const passedPlan = plan.map((gate) =>
      gate.id === "legacy-change-safety"
        ? {
            ...gate,
            gateState: "passed" as const,
            reviewerStatus: "characterized" as const,
          }
        : gate.id === "refactoring"
          ? {
              ...gate,
              gateState: "passed" as const,
              reviewerStatus: "proceed" as const,
            }
          : gate,
    );
    entries.push({
      customType: SBTD_STATE_CUSTOM_TYPE,
      data: {
        ...defaultSessionState("2026-07-25T00:00:00.000Z"),
        runtimeMode: "enforced",
        environmentObservation: {
          observedAt: "2026-07-25T00:00:00.000Z",
          mode: "managed",
          evidence: ["all managed"],
          repairPath: "/sbtd status",
        },
        classification,
        bookGates: passedPlan,
      },
    });

    await expect(
      tool?.execute(
        "stage-2",
        { stageId: "implementation" },
        undefined,
        undefined,
        ctx,
      ),
    ).resolves.toMatchObject({
      content: [
        {
          text: expect.stringContaining("Stage implementation is running"),
        },
      ],
    });
    expect(entries.at(-1)).toMatchObject({
      data: { stage: { id: "implementation", stageStatus: "running" } },
    });
  });

  it("Scenario: 非活动控制状态不能通过 OMP Tool 推进阶段", async () => {
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: defaultSessionState("2026-07-25T00:00:00.000Z"),
      },
    ];
    const tools: Array<{
      readonly name: string;
      readonly execute: (
        toolCallId: string,
        params: { readonly stageId: string },
        signal: AbortSignal | undefined,
        onUpdate: undefined,
        ctx: {
          readonly sessionManager: {
            readonly getBranch: () => readonly unknown[];
          };
        },
      ) => Promise<{ readonly content: readonly { readonly text: string }[] }>;
    }> = [];
    extension({
      registerCommand() {},
      zod: z,
      registerTool(tool: (typeof tools)[number]) {
        tools.push(tool);
      },
      on() {},
      appendEntry(customType: string, data: unknown) {
        entries.push({ customType, data });
      },
    } as never);
    const tool = tools.find((candidate) => candidate.name === "sbtd_workflow");

    await expect(
      tool?.execute(
        "stage-advisory",
        { stageId: "implementation" },
        undefined,
        undefined,
        { sessionManager: { getBranch: () => entries } },
      ),
    ).resolves.toMatchObject({
      content: [
        {
          text: expect.stringContaining("SBTD is advisory"),
        },
      ],
    });
    expect(entries).toHaveLength(1);
  });

  it("Scenario: 每个主要 Turn 注入 Runtime Marker 且 Hard Rule 可阻断工具", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-24T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-24T00:00:00.000Z",
            mode: "managed",
            evidence: ["all managed"],
            repairPath: "/sbtd status",
          },
        },
      },
    ];
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
    } as never);
    const ctx = {
      sessionManager: { getBranch: () => entries },
    };

    await expect(
      events.get("before_agent_start")?.(
        {
          prompt: "Fix an existing production bug.",
          systemPrompt: ["Host system contract"],
        },
        ctx,
      ),
    ).resolves.toEqual({
      systemPrompt: [
        "Host system contract",
        expect.stringMatching(
          /^<sbtd-runtime\b.*\bkit-revision="[0-9a-f]{64}".*\beffective-control-state="active".*\/>$/,
        ),
      ],
    });
    expect(entries.at(-1)).toMatchObject({
      customType: SBTD_STATE_CUSTOM_TYPE,
      data: {
        classification: { route: "bugfix" },
        bookGates: expect.arrayContaining([
          expect.objectContaining({
            id: "legacy-change-safety",
            gateState: "planned",
          }),
        ]),
      },
    });
    await expect(
      events.get("session.compacting")?.({}, ctx),
    ).resolves.toMatchObject({
      preserveData: {
        [SBTD_STATE_CUSTOM_TYPE]: {
          route: "auto",
          classification: { route: "bugfix" },
        },
      },
    });
    await expect(
      events.get("tool_call")?.(
        { toolName: "write", input: { path: "features/bug-fix.feature" } },
        ctx,
      ),
    ).resolves.toBeUndefined();
    await expect(
      events.get("tool_call")?.(
        { toolName: "write", input: { path: "test/legacy-safety.test.ts" } },
        ctx,
      ),
    ).resolves.toBeUndefined();
    await expect(
      events.get("tool_call")?.(
        {
          toolName: "edit",
          input: {
            patch: "[src/service.ts#ABCD]\n+content [features/not-a-path]",
          },
        },
        ctx,
      ),
    ).resolves.toEqual(
      expect.objectContaining({
        block: true,
        reason: expect.stringContaining("book-gate-before-edit"),
      }),
    );
    await expect(
      events.get("tool_call")?.(
        { toolName: "bash", input: { command: "trellis init -u test" } },
        ctx,
      ),
    ).resolves.toEqual(
      expect.objectContaining({
        block: true,
        reason: expect.stringContaining("no-trellis-init-outside-onboard"),
      }),
    );
  });

  it("Scenario: Delivery gap blocks; a bare .feature touch never satisfies BDD; verified current v2 evidence releases it", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-delivery-root-"));
    const fixtureCommit = "a".repeat(40);
    const execMock = async (
      command: string,
      args: string[],
      options: { cwd: string; timeout?: number },
    ): Promise<{ code: number; stdout: string; stderr: string }> => {
      if (command === "git" && args[0] === "rev-parse")
        return { code: 0, stdout: `${fixtureCommit}\n`, stderr: "" };
      if (command === "git") return { code: 0, stdout: "", stderr: "" };
      if (command === "python3") {
        const { promise, resolve: settle } = Promise.withResolvers<{
          code: number;
          stdout: string;
          stderr: string;
        }>();
        execFile(
          command,
          args,
          { cwd: options.cwd, timeout: options.timeout },
          (error, stdout, stderr) => {
            settle({
              code:
                error === null
                  ? 0
                  : typeof error.code === "number"
                    ? error.code
                    : 1,
              stdout: String(stdout),
              stderr: String(stderr),
            });
          },
        );
        return promise;
      }
      return { code: 1, stdout: "", stderr: "" };
    };
    try {
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
        exec: execMock,
      } as never);
      const ctx = { cwd: root, sessionManager: { getBranch: () => entries } };
      await events.get("before_agent_start")?.(
        { prompt: "Add a user-visible UI change." },
        ctx,
      );
      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          ctx,
        ),
      ).resolves.toMatchObject({
        decision: "block",
        reason: expect.stringContaining("bdd-required-for-visible-behavior"),
      });
      // A bare .feature write (the old mtime heuristic) must NOT satisfy BDD.
      await mkdir(resolve(root, "features"));
      await writeFile(
        resolve(root, "features", "ui-change.feature"),
        "Feature: UI change\n",
      );
      await expect(
        events.get("session_stop")?.(
          { turn_id: 2, stop_hook_active: false },
          ctx,
        ),
      ).resolves.toMatchObject({
        decision: "block",
        reason: expect.stringContaining("bdd-required-for-visible-behavior"),
      });
      // Verified, revision-current v2 evidence releases the delivery block.
      await cp(resolve(fixtureRoot, "positive-ci-junit"), root, {
        recursive: true,
      });
      await rename(
        resolve(root, "envelope.json"),
        resolve(root, "validation.evidence.json"),
      );
      await expect(
        events.get("session_stop")?.(
          { turn_id: 3, stop_hook_active: false },
          ctx,
        ),
      ).resolves.toBeUndefined();
      expect(
        entries.some(
          (entry) =>
            typeof entry === "object" &&
            entry !== null &&
            "data" in entry &&
            (
              entry as {
                data: {
                  validationEvidence?: {
                    evidenceVersion?: number;
                    sourceCommit?: string;
                  };
                };
              }
            ).data.validationEvidence?.evidenceVersion === 2 &&
            (
              entry as {
                data: { validationEvidence?: { sourceCommit?: string } };
              }
            ).data.validationEvidence?.sourceCommit === fixtureCommit,
        ),
      ).toBe(true);
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 更新的未跟踪生产文件成为分类事实", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-untracked-source-"));
    try {
      await mkdir(resolve(root, "src"));
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
        async exec(_command: string, args: string[]) {
          return {
            code: 0,
            killed: false,
            stderr: "",
            stdout: args[0] === "ls-files" ? "src/untracked.ts\n" : "",
          };
        },
      } as never);
      await events.get("before_agent_start")?.(
        { prompt: "Update module behavior." },
        { cwd: root, sessionManager: { getBranch: () => entries } },
      );

      expect(entries.at(-1)).toMatchObject({
        data: {
          classification: {
            existingProductionCode: true,
            reasons: expect.arrayContaining(["changed-paths-observed"]),
          },
        },
      });
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 任一新鲜正式报告配对满足交付证据", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-formal-report-"));
    const reports = resolve(root, "tests", "e2e", "reports", "html");
    try {
      await mkdir(reports, { recursive: true });
      await Promise.all([
        writeFile(resolve(reports, "playwright-report-aaa-stale.html"), "old"),
        writeFile(resolve(reports, "playwright-report-aaa-stale.md"), "old"),
      ]);
      const staleAt = new Date(Date.now() - 1_000);
      await Promise.all([
        utimes(
          resolve(reports, "playwright-report-aaa-stale.html"),
          staleAt,
          staleAt,
        ),
        utimes(
          resolve(reports, "playwright-report-aaa-stale.md"),
          staleAt,
          staleAt,
        ),
      ]);
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
      const context = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
      };
      await events.get("before_agent_start")?.(
        { prompt: "Run the Playwright web E2E regression." },
        context,
      );
      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          context,
        ),
      ).resolves.toMatchObject({
        decision: "block",
        reason: expect.stringContaining("report-artifact-required"),
      });
      await Promise.all([
        writeFile(resolve(reports, "playwright-report-zzz-fresh.html"), "new"),
        writeFile(
          resolve(reports, "playwright-report-unrelated.md"),
          "中文汇总",
        ),
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
      await symlink(
        "playwright-report-unrelated.md",
        resolve(reports, "playwright-report-zzz-fresh.md"),
      );
      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          context,
        ),
      ).resolves.toMatchObject({
        decision: "block",
        reason: expect.stringContaining("report-artifact-required"),
      });
      await rm(resolve(reports, "playwright-report-zzz-fresh.md"));
      await writeFile(
        resolve(reports, "playwright-report-zzz-fresh.md"),
        "中文汇总",
      );

      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          context,
        ),
      ).resolves.toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 两个交错 Session 不共享瞬态分类或交付阻断", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const root = await mkdtemp(
      resolve(tmpdir(), "kpi-session-isolation-root-"),
    );
    const sessionAEntries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const sessionBEntries = structuredClone(sessionAEntries);
    const sessionCEntries = structuredClone(sessionAEntries);
    try {
      extension({
        registerCommand() {},
        on(
          name: string,
          handler: (event: unknown, ctx: unknown) => Promise<unknown>,
        ) {
          events.set(name, handler);
        },
        appendEntry() {},
      } as never);
      const contextFor = (sessionId: string, entries: unknown[]) => ({
        cwd: root,
        sessionManager: {
          getSessionId: () => sessionId,
          getBranch: () => entries,
        },
      });
      const sessionA = contextFor("session-a", sessionAEntries);
      const sessionB = contextFor("session-b", sessionBEntries);
      const sessionC = contextFor("session-c", sessionCEntries);

      await events.get("before_agent_start")?.(
        { prompt: "Add a user-visible UI change." },
        sessionA,
      );
      await events.get("before_agent_start")?.(
        { prompt: "Add a user-visible UI change." },
        sessionB,
      );
      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          sessionA,
        ),
      ).resolves.toMatchObject({ decision: "block" });
      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: true },
          sessionB,
        ),
      ).resolves.toMatchObject({ decision: "block" });
      await expect(
        events.get("session_stop")?.(
          { turn_id: 1, stop_hook_active: false },
          sessionC,
        ),
      ).resolves.toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: Explicit Tool approval is scoped to one dependency install", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
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
    } as never);
    const ctx = { sessionManager: { getBranch: () => entries } };
    const install = {
      toolCallId: "install-1",
      toolName: "bash",
      input: { command: "pnpm add example-package" },
    };
    await expect(
      events.get("tool_call")?.(install, ctx),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });
    await events.get("tool_approval_resolved")?.(
      { toolCallId: "install-1", approved: true },
      ctx,
    );
    await expect(
      events.get("tool_call")?.(install, ctx),
    ).resolves.toBeUndefined();
    await events.get("tool_result")?.({ toolCallId: "install-1" }, ctx);
    await expect(
      events.get("tool_call")?.(install, ctx),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("install-requires-approval"),
    });
    await expect(
      events.get("tool_call")?.(
        { toolCallId: "secret-1", toolName: "read", input: { path: ".env" } },
        ctx,
      ),
    ).resolves.toMatchObject({
      block: true,
      reason: expect.stringContaining("secret-read-guard"),
    });
  });

  it("Scenario: 自动Route恢复需要当前任务事实而不复用陈旧分类", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const notices: string[] = [];
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const ctx = {
      cwd: process.cwd(),
      ui: {
        notify(message: string) {
          notices.push(message);
        },
      },
      sessionManager: { getBranch: () => entries },
    };
    extension({
      registerCommand(
        _name: string,
        options: { handler: (args: string, ctx: unknown) => Promise<void> },
      ) {
        commands.push({ options });
      },
      on(
        name: string,
        handler: (event: unknown, ctx: unknown) => Promise<unknown>,
      ) {
        events.set(name, handler);
      },
      appendEntry(customType: string, data: unknown) {
        entries.push({ customType, data });
      },
    } as never);

    await events.get("turn_start")?.({ turnIndex: 1 }, ctx);
    await events.get("before_agent_start")?.(
      { prompt: "Fix an existing production bug." },
      ctx,
    );
    await events.get("turn_end")?.({ turnIndex: 1 }, ctx);
    const entriesBeforeRecovery = entries.length;

    await commands[0]?.options.handler("route auto", ctx);

    expect(entries).toHaveLength(entriesBeforeRecovery);
    expect(notices.at(-1)).toContain("needs current task facts");
  });

  it("Scenario: Route 查询在未完成 Onboard 时不写入且保留可见状态", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const entries: unknown[] = [];
    const notices: string[] = [];
    extension({
      registerCommand(
        _name: string,
        options: { handler: (args: string, ctx: unknown) => Promise<void> },
      ) {
        commands.push({ options });
      },
      on() {},
      appendEntry(customType: string, data: unknown) {
        entries.push({ customType, data });
      },
    } as never);

    await commands[0]?.options.handler("route", {
      cwd: process.cwd(),
      ui: { notify: (message: string) => notices.push(message) },
      sessionManager: { getBranch: () => entries },
    });

    expect(entries).toHaveLength(0);
    expect(notices.at(-1)).toContain("Route: auto");
  });

  it("Scenario: Route 覆盖拒绝多余参数且 Policy Profile 不需要自动分类恢复", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const notices: string[] = [];
    extension({
      registerCommand(
        _name: string,
        options: { handler: (args: string, ctx: unknown) => Promise<void> },
      ) {
        commands.push({ options });
      },
      on() {},
      appendEntry(customType: string, data: unknown) {
        entries.push({ customType, data });
      },
    } as never);
    const context = {
      cwd: process.cwd(),
      ui: { notify: (message: string) => notices.push(message) },
      sessionManager: { getBranch: () => entries },
    };
    const countBeforeInvalidRoute = entries.length;

    await commands[0]?.options.handler("route review unexpected", context);
    expect(entries).toHaveLength(countBeforeInvalidRoute);
    expect(notices.at(-1)).toContain("Usage: /sbtd route [auto|route-id]");
    await commands[0]?.options.handler("route invalid-route", context);
    expect(entries).toHaveLength(countBeforeInvalidRoute);
    expect(notices.at(-1)).toContain("Unknown Route");

    await commands[0]?.options.handler("strict", context);
    expect(notices.at(-1)).not.toContain("needs current task facts");
  });
  it("Scenario: 自动Route恢复忽略上一条用户Route覆盖", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const root = await mkdtemp(resolve(tmpdir(), "kpi-route-auto-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-route-auto-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced",
          route: "review",
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed",
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const ctx = {
      cwd: root,
      ui: { notify() {} },
      sessionManager: { getBranch: () => entries },
    };
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on(
          name: string,
          handler: (event: unknown, ctx: unknown) => Promise<unknown>,
        ) {
          events.set(name, handler);
        },
        appendEntry(customType: string, data: unknown) {
          entries.push({ customType, data });
        },
      } as never);

      await events.get("before_agent_start")?.(
        { prompt: "Fix an existing production bug." },
        ctx,
      );
      expect(entries.at(-1)).toMatchObject({
        data: { route: "review", classification: { route: "review" } },
      });

      await commands[0]?.options.handler("route auto", ctx);

      expect(entries.at(-1)).toMatchObject({
        data: { route: "auto", classification: { route: "bugfix" } },
      });
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: reobserve failure persists blocked environment evidence", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<void>
    >();
    const entries: unknown[] = [];
    const notices: string[] = [];
    extension({
      registerCommand() {},
      on(
        name: string,
        handler: (event: unknown, ctx: unknown) => Promise<void>,
      ) {
        events.set(name, handler);
      },
      appendEntry(_type: string, data: unknown) {
        entries.push({ customType: "kpi.sbtd.session.v1", data });
      },
    } as never);

    await events.get("session_start")?.(
      {},
      {
        cwd: undefined,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return entries;
          },
        },
      },
    );

    expect(entries.at(-1)).toMatchObject({
      data: {
        environmentObservation: {
          mode: "blocked",
          repairPath: "/sbtd doctor",
        },
      },
    });
    expect(notices[0]).toContain("environment observation failed");
  });

  it("Scenario: Resume 当前 Route 所需 Trellis 能力缺失时进入 blocked", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<void>
    >();
    const root = await mkdtemp(resolve(tmpdir(), "kpi-resume-route-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-resume-route-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-24T00:00:00.000Z"),
          runtimeMode: "enforced",
          route: "auto",
          classification: classifyTask({
            userVisibleBehavior: false,
            existingProductionCode: false,
            existingBehaviorBug: false,
            dataRisk: false,
            productionPathRisk: false,
            crossRepoScope: false,
            domainAmbiguity: false,
            durableRequirements: true,
          }),
          environmentObservation: {
            observedAt: "2026-07-24T00:00:00.000Z",
            mode: "managed",
            evidence: ["previously managed"],
            repairPath: "/sbtd status",
          },
        },
      },
    ];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand() {},
        on(
          name: string,
          handler: (event: unknown, ctx: unknown) => Promise<void>,
        ) {
          events.set(name, handler);
        },
        appendEntry(customType: string, data: unknown) {
          entries.push({ customType, data });
        },
      } as never);

      await events.get("session_start")?.(
        {},
        {
          cwd: root,
          ui: { notify() {} },
          sessionManager: { getBranch: () => entries },
        },
      );

      expect(entries.at(-1)).toMatchObject({
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          runtimeMode: "enforced",
          route: "auto",
          environmentObservation: { mode: "blocked" },
        },
      });
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: 帮助不创建 Agent Turn 或 KPi 状态记录", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    let appends = 0;
    const notices: string[] = [];
    extension({
      registerCommand(
        _name: string,
        options: { handler: (args: string, ctx: unknown) => Promise<void> },
      ) {
        commands.push({ options });
      },
      on() {},
      appendEntry() {
        appends += 1;
      },
    } as never);
    await commands[0]?.options.handler("help", {
      ui: {
        notify(message: string) {
          notices.push(message);
        },
      },
      sessionManager: {
        getBranch() {
          return [];
        },
      },
    });
    expect(appends).toBe(0);
    expect(notices[0]).toContain("/sbtd onboard plan");
  });

  it("Scenario: 预览三层 AGENTS Onboard 计划", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const calls: Array<{ command: string; args: string[] }> = [];
    const notices: string[] = [];
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-omp-plan-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {},
        async exec(command: string, args: string[]) {
          calls.push({ command, args });
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      } as never);

      await commands[0]?.options.handler("onboard plan", {
        cwd: "/work/project",
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      });

      expect(calls.map((call) => call.command)).toEqual([
        "python3",
        "trellis",
        "gitnexus",
      ]);
      expect(notices).toHaveLength(1);
      const payload = JSON.parse(notices[0] ?? "{}") as {
        sourceId: string;
        canonicalRevision: string;
        canonicalManifestSha256: string;
        projectionSha256: string;
        mcpConfigPath: string;
        targets: Array<{ target: { role: string; path: string } }>;
        digest: string;
        pythonOnboard?: unknown;
      };
      expect(payload.pythonOnboard).toBeUndefined();
      expect(payload.sourceId).toBe("sbtd-workflow-kit-upstream");
      expect(payload.canonicalRevision).toBe(
        "4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb",
      );
      expect(payload.canonicalManifestSha256).toMatch(/^[0-9a-f]{64}$/);
      expect(payload.projectionSha256).toMatch(/^[0-9a-f]{64}$/);
      expect(payload.targets.map((entry) => entry.target.role)).toEqual([
        "global",
        "project-root",
        "project-omp",
      ]);
      expect(notices[0]).not.toMatch(/codex/i);
      expect(notices[0]).not.toContain("onboard.py");
      expect(payload.digest).toMatch(/^[0-9a-f]{64}$/);
      expect(payload.mcpConfigPath).toBe(resolve(agentDirectory, "mcp.json"));
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });
  it("Scenario: 未完成 Onboard 时 bootstrap 不执行 AGENTS Apply 或 Agent Turn", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-bootstrap-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-bootstrap-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const notices: string[] = [];
    let appends = 0;
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {
          appends += 1;
        },
        async exec() {
          throw new Error("bootstrap must not start a subprocess");
        },
      } as never);

      await commands[0]?.options.handler("onboard bootstrap plan-digest", {
        cwd: root,
        ui: {
          async confirm() {
            throw new Error("bootstrap must not request confirmation");
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      });

      expect(notices).toHaveLength(1);
      expect(notices[0]).toContain("No completed composite Onboard operation");
      expect(appends).toBe(0);
      await expect(
        readFile(resolve(root, "AGENTS.md"), "utf8"),
      ).rejects.toMatchObject({
        code: "ENOENT",
      });
      await expect(
        readFile(resolve(agentDirectory, "AGENTS.md"), "utf8"),
      ).rejects.toMatchObject({ code: "ENOENT" });
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: 无中断事务时 reset 仍 Plan-first 安装 Managed Blocks", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-reset-root-"));
    const agentDirectory = await mkdtemp(resolve(tmpdir(), "kpi-reset-agent-"));
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const notices: string[] = [];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {},
      } as never);

      await commands[0]?.options.handler("onboard reset", {
        cwd: root,
        ui: {
          async confirm() {
            return true;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      });

      await expect(
        readFile(resolve(root, "AGENTS.md"), "utf8"),
      ).resolves.toContain("kpi:managed-begin role=project-root");
      expect(notices.at(-1)).toContain("Managed blocks installed");
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: Status and Doctor report the effective AGENTS chain without changing session state", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-status-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-status-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const entries: unknown[] = [];
    const notices: string[] = [];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry(_type: string, data: unknown) {
          entries.push({ customType: "kpi.sbtd.session.v1", data });
        },
      } as never);
      const context = {
        cwd: root,
        ui: {
          async confirm() {
            return true;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return entries;
          },
        },
      };

      await commands[0]?.options.handler("onboard reset", context);
      await commands[0]?.options.handler("route review", context);
      expect(notices.at(-1)).toContain("unavailable until Environment Mode");
      expect(entries.at(-1)).toMatchObject({
        data: {
          route: "auto",
          environmentObservation: { mode: "needs-onboard" },
        },
      });
      await commands[0]?.options.handler("status", context);
      await commands[0]?.options.handler("doctor", context);

      expect(entries).toHaveLength(1);
      expect(notices.at(-1)).toContain("Root Project Facts Import: valid");
      expect(notices.at(-1)).toContain(
        "AGENTS project-omp: exists=true discovered=true loaded=true effective=true",
      );
      expect(notices.at(-1)).toContain(
        "Tool Evidence core-gate-skills: installation=installed configuration=configured callability=not-needed",
      );
      expect(notices.at(-1)).toContain("Agent Plugin:");
      expect(notices.at(-1)).toContain("schema: 1.0.0");
      expect(notices.at(-1)).toContain("discovered: source-unverified");
      expect(notices.at(-1)).toMatch(/packaged: \d+/);
      expect(notices.at(-1)).toContain("portableMcp: absent");
      expect(notices.at(-1)).toContain("ompRuntimeExtension: loaded");
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: 缺失选定 Profile 基线时启用进入 Onboard Preflight", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-route-root-"));
    const agentDirectory = await mkdtemp(resolve(tmpdir(), "kpi-route-agent-"));
    const skillsDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-route-skills-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const previousSkillsDirectory = process.env.AGENT_SKILLS_DIR;
    const entries: unknown[] = [];
    const notices: string[] = [];
    const sessionManager = {
      getBranch() {
        return entries;
      },
    };
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry(_type: string, data: unknown) {
          entries.push({ customType: "kpi.sbtd.session.v1", data });
        },
      } as never);
      await commands[0]?.options.handler("onboard reset", {
        cwd: root,
        ui: {
          async confirm() {
            return true;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      process.env.AGENT_SKILLS_DIR = skillsDirectory;
      await Promise.all(
        [
          "book-ddd-distilled-modeling",
          "book-ddia-data-design",
          "book-legacy-change-safety",
          "book-refactoring-pass",
          "book-release-readiness",
        ].map(async (name) => {
          const directory = resolve(skillsDirectory, name);
          await mkdir(directory, { recursive: true });
          await writeFile(resolve(directory, "SKILL.md"), `${name}\n`);
        }),
      );

      await commands[0]?.options.handler("on", {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });

      expect(entries.at(-1)).toMatchObject({
        data: {
          environmentObservation: { mode: "needs-onboard" },
          runtimeMode: "enforced",
        },
      });
      expect(notices.at(-1)).toContain("SBTD is preflight-only");
      for (const capability of [
        "trellis",
        "gitnexus",
        "bdd-tdd",
        "ui",
        "web-mobile-e2e",
      ]) {
        await commands[0]?.options.handler(
          `onboard skip plan create ${capability} --scope project --expires 2099-01-01T00:00:00.000Z --reason "preflight optional gap"`,
          {
            cwd: root,
            ui: {
              notify(message: string) {
                notices.push(message);
              },
            },
            sessionManager,
          },
        );
        const skipPlan = JSON.parse(notices.at(-1) as string);
        expect(skipPlan).toMatchObject({ action: "create" });
        await commands[0]?.options.handler(
          `onboard skip apply ${skipPlan.digest}`,
          {
            cwd: root,
            ui: {
              async confirm() {
                return true;
              },
              notify(message: string) {
                notices.push(message);
              },
            },
            sessionManager,
          },
        );
        expect(notices.at(-1)).toContain("AcceptedSkip");
      }
      expect(notices.at(-1)).toContain("Environment Mode is degraded");
      expect(entries.at(-1)).toMatchObject({
        data: { environmentObservation: { mode: "degraded" } },
      });
      await expect(
        readFile(
          resolve(agentDirectory, "kpi/provenance/accepted-skips-v1.json"),
          "utf8",
        ),
      ).resolves.toContain('"status": "active"');
      const entryCount = entries.length;
      await commands[0]?.options.handler("off", {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager,
      });
      expect(entries).toHaveLength(entryCount + 1);
      expect(notices.at(-1)).toContain("SBTD is advisory");
      await expect(
        readFile(resolve(root, "AGENTS.md"), "utf8"),
      ).resolves.toContain("kpi:managed-begin role=project-root");
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      if (previousSkillsDirectory === undefined)
        delete process.env.AGENT_SKILLS_DIR;
      else process.env.AGENT_SKILLS_DIR = previousSkillsDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
      await rm(skillsDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: 环境观察失败时 Doctor 仍输出 Agent Plugin 块", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-doctor-fail-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-doctor-fail-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const notices: string[] = [];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {},
      } as never);
      const brokenCwd = resolve(root, "not-a-directory");
      await writeFile(brokenCwd, "not a directory");
      await commands[0]?.options.handler("doctor", {
        cwd: brokenCwd,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: { getBranch: () => [] },
      });
      expect(notices.at(-1)).toContain("Agent Plugin:");
      expect(notices.at(-1)).toContain("schema: 1.0.0");
      expect(notices.at(-1)).toMatch(/packaged: \d+/);
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: Onboard Plan 把 Skills 安装到环境观测验证的同一目录", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-skillsdir-agent-"),
    );
    const skillsOverride = await mkdtemp(
      resolve(tmpdir(), "kpi-skillsdir-override-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const previousSkillsDirectory = process.env.AGENT_SKILLS_DIR;
    const notices: string[] = [];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {},
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      } as never);
      const context = {
        cwd: "/work/project",
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      };

      process.env.AGENT_SKILLS_DIR = skillsOverride;
      await commands[0]?.options.handler("onboard plan", context);
      const withOverride = JSON.parse(notices.at(-1) ?? "{}") as {
        skills: { targetDir: string; source: string; network: boolean };
      };
      expect(withOverride.skills.targetDir).toBe(skillsOverride);
      expect(withOverride.skills.source).toBe("embedded-stable");
      expect(withOverride.skills.network).toBe(false);

      delete process.env.AGENT_SKILLS_DIR;
      await commands[0]?.options.handler("onboard plan", context);
      const withDefault = JSON.parse(notices.at(-1) ?? "{}") as {
        skills: { targetDir: string };
      };
      expect(withDefault.skills.targetDir).toBe(
        resolve(agentDirectory, "skills"),
      );
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      if (previousSkillsDirectory === undefined)
        delete process.env.AGENT_SKILLS_DIR;
      else process.env.AGENT_SKILLS_DIR = previousSkillsDirectory;
      await rm(agentDirectory, { force: true, recursive: true });
      await rm(skillsOverride, { force: true, recursive: true });
    }
  });

  it("Scenario: 项目级确认只描述项目范围效果而完整确认保留 Skills 替换说明", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-scope-root-"));
    const agentDirectory = await mkdtemp(resolve(tmpdir(), "kpi-scope-agent-"));
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const confirmations: Array<{ title: string; message: string }> = [];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {},
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      } as never);
      const context = {
        cwd: root,
        ui: {
          async confirm(title: string, message: string) {
            confirmations.push({ title, message });
            return false;
          },
          notify() {},
        },
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      };

      await commands[0]?.options.handler("onboard init-projects", context);
      expect(confirmations).toHaveLength(1);
      expect(confirmations[0]?.message).toContain("managed AGENTS targets");
      expect(confirmations[0]?.message).not.toContain(
        "replace retained Skills",
      );
      expect(confirmations[0]?.message).toContain("out of scope");

      await commands[0]?.options.handler("onboard init", context);
      expect(confirmations).toHaveLength(2);
      expect(confirmations[1]?.message).toContain("replace retained Skills");
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: Trellis init 确认列出每个绝对项目根目录与用户名", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-trellis-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-trellis-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const confirmations: Array<{ title: string; message: string }> = [];
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry() {},
        async exec() {
          return { stdout: "", stderr: "", code: 0, killed: false };
        },
      } as never);
      await commands[0]?.options.handler("onboard init --trellis-user dev640", {
        cwd: root,
        ui: {
          async confirm(title: string, message: string) {
            confirmations.push({ title, message });
            return false;
          },
          notify() {},
        },
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      });

      const trellisConfirm = confirmations.find(
        (entry) => entry.title === "Initialize Trellis Projects",
      );
      expect(trellisConfirm?.message).toContain("dev640");
      expect(trellisConfirm?.message).toContain(root);
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: Status 与 Doctor 显示中断 bootstrap 的恢复路径且不写入", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-bootstatus-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-bootstatus-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    const entries: unknown[] = [];
    const notices: string[] = [];
    const planDigest = "a".repeat(64);
    const handoffRecord = JSON.stringify({
      schemaVersion: 1,
      operationId: "bootstrap-op-1",
      planDigest,
      projectRoot: root,
      state: "scheduled",
      scheduledAt: "2026-08-12T00:00:00.000Z",
      lastObservedAt: "2026-08-12T00:00:00.000Z",
      taskState: "pending",
    });
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      await mkdir(resolve(agentDirectory, "kpi/bootstrap"), {
        recursive: true,
      });
      await writeFile(
        resolve(agentDirectory, "kpi/bootstrap/bootstrap-op-1.json"),
        handoffRecord,
        "utf8",
      );
      extension({
        registerCommand(
          _name: string,
          options: { handler: (args: string, ctx: unknown) => Promise<void> },
        ) {
          commands.push({ options });
        },
        on() {},
        appendEntry(_type: string, data: unknown) {
          entries.push({ customType: SBTD_STATE_CUSTOM_TYPE, data });
        },
      } as never);
      const context = {
        cwd: root,
        ui: {
          async confirm() {
            return false;
          },
          notify(message: string) {
            notices.push(message);
          },
        },
        sessionManager: {
          getBranch() {
            return entries;
          },
        },
      };

      await commands[0]?.options.handler("status", context);
      const statusNotice = notices.at(-1) ?? "";
      expect(statusNotice).toContain("bootstrap-required");
      expect(statusNotice).toContain(`/sbtd onboard bootstrap ${planDigest}`);

      await commands[0]?.options.handler("doctor", context);
      const doctorNotice = notices.at(-1) ?? "";
      expect(doctorNotice).toContain("bootstrap-required");
      expect(doctorNotice).toContain(`/sbtd onboard bootstrap ${planDigest}`);

      expect(entries).toHaveLength(0);
      await expect(
        readFile(
          resolve(agentDirectory, "kpi/bootstrap/bootstrap-op-1.json"),
          "utf8",
        ),
      ).resolves.toBe(handoffRecord);
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });
});

describe("Feature: SBTD 运行时工作流与门禁 - Release Readiness Gate evidence", () => {
  const gateFixtureCommit = "a".repeat(40);

  const gateExecMock = async (
    command: string,
    args: string[],
    options: { cwd: string; timeout?: number },
  ): Promise<{ code: number; stdout: string; stderr: string }> => {
    if (command === "git" && args[0] === "rev-parse")
      return { code: 0, stdout: `${gateFixtureCommit}\n`, stderr: "" };
    if (command === "git") return { code: 0, stdout: "", stderr: "" };
    if (command === "python3") {
      const { promise, resolve: settle } = Promise.withResolvers<{
        code: number;
        stdout: string;
        stderr: string;
      }>();
      execFile(
        command,
        args,
        { cwd: options.cwd, timeout: options.timeout },
        (error, stdout, stderr) => {
          settle({
            code:
              error === null
                ? 0
                : typeof error.code === "number"
                  ? error.code
                  : 1,
            stdout: String(stdout),
            stderr: String(stderr),
          });
        },
      );
      return promise;
    }
    return { code: 1, stdout: "", stderr: "" };
  };

  function gateTestSetup(entries: unknown[]) {
    let commandHandler:
      | ((args: string, ctx: unknown) => Promise<void>)
      | undefined;
    const notices: { message: string; level?: string }[] = [];
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    extension({
      registerCommand(
        _name: string,
        spec: { handler: (args: string, ctx: unknown) => Promise<void> },
      ) {
        commandHandler = spec.handler;
      },
      on(
        name: string,
        handler: (event: unknown, ctx: unknown) => Promise<unknown>,
      ) {
        events.set(name, handler);
      },
      appendEntry(customType: string, data: unknown) {
        entries.push({ customType, data });
      },
      exec: gateExecMock,
    } as never);
    return { commandHandler: () => commandHandler, notices, events };
  }

  const gateClassification = () =>
    classifyTask({
      userVisibleBehavior: true,
      existingProductionCode: true,
      existingBehaviorBug: false,
      dataRisk: false,
      productionPathRisk: true,
      crossRepoScope: false,
      domainAmbiguity: false,
      durableRequirements: false,
    });

  function gateStateEntries(rootClassification = gateClassification()) {
    const bookGates = createBookGatePlan(rootClassification).map((gate) =>
      gate.id === "release-readiness"
        ? { ...gate, gateState: "running" as const }
        : gate,
    );
    return [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-25T00:00:00.000Z"),
          runtimeMode: "enforced" as const,
          classification: rootClassification,
          bookGates,
          environmentObservation: {
            observedAt: "2026-07-25T00:00:00.000Z",
            mode: "managed" as const,
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
  }

  const releaseGateOf = (entries: unknown[]) =>
    entries
      .map((entry) =>
        typeof entry === "object" && entry !== null && "data" in entry
          ? (
              entry as {
                data: {
                  bookGates?: { id: string; reviewerStatus?: string }[];
                };
              }
            ).data.bookGates?.find((gate) => gate.id === "release-readiness")
          : undefined,
      )
      .filter((gate) => gate !== undefined)
      .at(-1);

  it("Scenario: 未验证的当前 evidence 下 ready 不可达", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-gate-empty-"));
    const entries = gateStateEntries();
    try {
      const setup = gateTestSetup(entries);
      const ctx = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
        ui: {
          notify(message: string, level?: string) {
            setup.notices.push({ message, level });
          },
          async confirm() {
            return true;
          },
        },
      };
      await setup.commandHandler()?.(
        "gate record release-readiness ready",
        ctx,
      );
      expect(
        setup.notices.some(
          (notice) =>
            notice.level === "warning" &&
            notice.message.includes(
              "release-readiness cannot be recorded as ready",
            ),
        ),
      ).toBe(true);
      expect(releaseGateOf(entries)?.reviewerStatus).toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 已验证当前 exact v2 evidence 使 ready 可达并持久化 descriptor", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-gate-evidence-"));
    const entries = gateStateEntries();
    try {
      await cp(resolve(fixtureRoot, "positive-ci-junit"), root, {
        recursive: true,
      });
      await rename(
        resolve(root, "envelope.json"),
        resolve(root, "validation.evidence.json"),
      );
      const setup = gateTestSetup(entries);
      const ctx = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
        ui: {
          notify(message: string, level?: string) {
            setup.notices.push({ message, level });
          },
          async confirm() {
            return true;
          },
        },
      };
      await setup.commandHandler()?.(
        "gate record release-readiness ready",
        ctx,
      );
      expect(releaseGateOf(entries)?.reviewerStatus).toBe("ready");
      expect(
        entries.some(
          (entry) =>
            typeof entry === "object" &&
            entry !== null &&
            "data" in entry &&
            (
              entry as {
                data: {
                  validationEvidence?: {
                    evidenceVersion?: number;
                    sourceCommit?: string;
                    scenarioLinks?: unknown[];
                  };
                };
              }
            ).data.validationEvidence?.evidenceVersion === 2 &&
            (
              entry as {
                data: { validationEvidence?: { sourceCommit?: string } };
              }
            ).data.validationEvidence?.sourceCommit === gateFixtureCommit,
        ),
      ).toBe(true);
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: 仓库变更后陈旧 Release Readiness ready 不能继续放行", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-gate-stale-"));
    const entries = gateStateEntries();
    try {
      await cp(resolve(fixtureRoot, "positive-ci-junit"), root, {
        recursive: true,
      });
      await rename(
        resolve(root, "envelope.json"),
        resolve(root, "validation.evidence.json"),
      );
      const setup = gateTestSetup(entries);
      const ctx = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
        ui: {
          notify(message: string, level?: string) {
            setup.notices.push({ message, level });
          },
          async confirm() {
            return true;
          },
        },
      };
      await setup.commandHandler()?.(
        "gate record release-readiness ready",
        ctx,
      );
      expect(releaseGateOf(entries)?.reviewerStatus).toBe("ready");
      await expect(
        setup.events.get("tool_call")?.(
          {
            toolCallId: "write-1",
            toolName: "write",
            input: { path: "src/app.ts", content: "export {}\n" },
          },
          ctx,
        ),
      ).resolves.toBeUndefined();
      await setup.events.get("tool_result")?.({ toolCallId: "write-1" }, ctx);
      const latest = entries.at(-1);
      expect(
        latest &&
          typeof latest === "object" &&
          "data" in latest &&
          latest.data !== null &&
          typeof latest.data === "object" &&
          !(
            "validationEvidence" in latest.data &&
            latest.data.validationEvidence !== undefined
          ),
      ).toBe(true);
      expect(releaseGateOf(entries)?.gateState).toBe("planned");
      expect(releaseGateOf(entries)?.reviewerStatus).toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });

  it("Scenario: v1 通用 evidence 永不满足 BDD 语义追溯", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-gate-v1-"));
    const entries = gateStateEntries();
    try {
      // A v1 generic envelope with a passed report: execution evidence exists,
      // but it can never satisfy BDD scenario traceability for this task.
      await mkdir(resolve(root, "reports"), { recursive: true });
      const reportBytes = Buffer.from('{"suites":[]}\n', "utf8");
      await writeFile(
        resolve(root, "reports", "api-report-1.json"),
        reportBytes,
      );
      await writeFile(resolve(root, "reports", "api-report-1.md"), "# api\n");
      const envelope = {
        schemaVersion: 1,
        runId: "run-v1",
        createdAt: "2026-08-17T00:00:00Z",
        evidenceSource: "ci",
        trigger: "pull-request",
        repository: {
          repositoryKey: "demo",
          sourceRef: "refs/heads/main",
          sourceCommit: gateFixtureCommit,
          worktreeState: "clean",
        },
        sourceRevision: "exact",
        environmentAlignment: "verified",
        e2eMode: "full-stack",
        mockStrategy: "none",
        featureSources: [],
        reports: [
          {
            testType: "api",
            path: "reports/api-report-1.json",
            summaryMd: "reports/api-report-1.md",
            sha256: createHash("sha256").update(reportBytes).digest("hex"),
            status: "passed",
            mode: "full-stack",
          },
        ],
        evidencePublication: "not-configured",
        secretsRedacted: true,
      };
      await writeFile(
        resolve(root, "reports", "run.evidence.json"),
        JSON.stringify(envelope, null, 2),
      );
      const setup = gateTestSetup(entries);
      const ctx = {
        cwd: root,
        sessionManager: { getBranch: () => entries },
        ui: {
          notify(message: string, level?: string) {
            setup.notices.push({ message, level });
          },
          async confirm() {
            return true;
          },
        },
      };
      await setup.commandHandler()?.(
        "gate record release-readiness ready",
        ctx,
      );
      expect(
        setup.notices.some(
          (notice) =>
            notice.level === "warning" &&
            notice.message.includes(
              "release-readiness cannot be recorded as ready",
            ),
        ),
      ).toBe(true);
      expect(releaseGateOf(entries)?.reviewerStatus).toBeUndefined();
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });
});
