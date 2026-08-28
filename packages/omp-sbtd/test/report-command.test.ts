import { mkdir, mkdtemp, rm, utimes, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import extension from "../src/extension.ts";
import {
  defaultSessionState,
  SBTD_STATE_CUSTOM_TYPE,
} from "../src/state/index.ts";

function fillHostEvent(
  name: string,
  payload: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const defaults: Record<string, Record<string, unknown>> = {
    session_start: { type: "session_start" },
    session_switch: { type: "session_switch" },
    session_branch: { type: "session_branch" },
    session_tree: { type: "session_tree", newLeafId: null, oldLeafId: null },
    before_agent_start: { type: "before_agent_start", systemPrompt: [] },
    "session.compacting": {
      type: "session.compacting",
      sessionId: "session-test",
      messages: [],
    },
    tool_call: { type: "tool_call", toolCallId: "test-call", input: {} },
    tool_approval_resolved: {
      type: "tool_approval_resolved",
      sessionId: "session-test",
      toolName: "unknown",
    },
    tool_result: {
      type: "tool_result",
      toolName: "unknown",
      input: {},
      content: [],
      isError: false,
      details: null,
    },
    turn_start: { type: "turn_start", timestamp: 0 },
    turn_end: { type: "turn_end", message: null, toolResults: [] },
    session_stop: {
      type: "session_stop",
      messages: [],
      turn_id: 0,
      session_id: "session-test",
      stop_hook_active: false,
      signal: null,
    },
    credential_disabled: { type: "credential_disabled" },
  };
  const out: Record<string, unknown> = {
    ...(defaults[name] ?? { type: name }),
    type: name,
  };
  if (payload) {
    for (const key of Reflect.ownKeys(payload)) {
      const desc = Object.getOwnPropertyDescriptor(payload, key);
      if (desc) Object.defineProperty(out, key, desc);
    }
  }
  out.type = name;
  return out;
}

const hostContract = {
  zod: z,
  registerTool() {},
} as const;

describe("Feature: 验证报告与 Provider 观察", () => {
  it("Scenario: 查看当前 SBTD 报告", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: defaultSessionState("2026-07-26T00:00:00.000Z"),
      },
    ];
    const notices: string[] = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-report-command-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-report-command-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        ...hostContract,
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
      const before = JSON.stringify(entries.at(-1));

      await commands[0]?.options.handler("report", {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        models: {
          current: () => ({ provider: "openai", id: "gpt-5.6" }),
        },
        sessionManager: { getBranch: () => entries },
      });

      expect(entries).toHaveLength(1);
      expect(JSON.stringify(entries.at(-1))).toBe(before);
      expect(notices.at(-1)).toContain("# SBTD 当前报告");
      expect(notices.at(-1)).toContain("## 工作流");
      expect(notices.at(-1)).toContain("## 验证");
      expect(notices.at(-1)).toContain("## Evidence Envelope");
      expect(notices.at(-1)).toContain("## 工具证据");
      expect(notices.at(-1)).toContain("## Provider Coordination");
      expect(notices.at(-1)).toContain('"provider": "openai"');
      expect(notices.at(-1)).toContain("```json");
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: Provider 报告不保留 credential-disabled 原因", async () => {
    const commands: Array<{
      options: { handler: (args: string, ctx: unknown) => Promise<void> };
    }> = [];
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: defaultSessionState("2026-07-26T00:00:00.000Z"),
      },
    ];
    const notices: string[] = [];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-provider-report-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-provider-report-agent-"),
    );
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        ...hostContract,
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
      const context = {
        cwd: root,
        ui: {
          notify(message: string) {
            notices.push(message);
          },
        },
        models: { current: () => undefined },
        sessionManager: { getBranch: () => entries },
      };

      const credentialDisabledEvent = Object.defineProperties(
        { provider: "openai" },
        {
          disabledCause: {
            enumerable: true,
            get: (): never => {
              throw new Error("disabledCause must not be read");
            },
          },
        },
      );
      await events.get("credential_disabled")?.(
        fillHostEvent("credential_disabled", credentialDisabledEvent),
        context,
      );
      const entriesAfterProviderEvent = entries.length;
      expect(entries.at(-1)).toMatchObject({
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          providerObservation: {
            provider: "openai",
            availability: "unavailable",
            fallback: "unavailable",
            selection: "blocked",
            blockerCode: "provider-unavailable",
          },
        },
      });
      expect(JSON.stringify(entries)).not.toContain("disabledCause");

      await commands[0]?.options.handler("report", context);

      expect(entries).toHaveLength(entriesAfterProviderEvent);
      expect(notices.at(-1)).toContain("Availability：unavailable");
      expect(notices.at(-1)).toContain("Fallback：unavailable");
      expect(notices.at(-1)).toContain("Selection Result：blocked");
      expect(notices.at(-1)).not.toContain("disabledCause");
      expect(notices.at(-1)).not.toContain("credential_disabled");
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });

  it("Scenario: 同 Stem 的新鲜正式报告与中文 Markdown 可作为报告证据", async () => {
    const events = new Map<
      string,
      (event: unknown, ctx: unknown) => Promise<unknown>
    >();
    const entries: unknown[] = [
      {
        customType: SBTD_STATE_CUSTOM_TYPE,
        data: {
          ...defaultSessionState("2026-07-26T00:00:00.000Z"),
          runtimeMode: "enforced" as const,
          environmentObservation: {
            observedAt: "2026-07-26T00:00:00.000Z",
            mode: "managed" as const,
            evidence: ["managed"],
            repairPath: "/sbtd doctor",
          },
        },
      },
    ];
    const root = await mkdtemp(resolve(tmpdir(), "kpi-report-artifact-root-"));
    const agentDirectory = await mkdtemp(
      resolve(tmpdir(), "kpi-report-artifact-agent-"),
    );
    const reports = resolve(root, "tests", "e2e", "reports", "html");
    const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
    try {
      process.env.PI_CODING_AGENT_DIR = agentDirectory;
      extension({
        ...hostContract,
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
        models: { current: () => undefined },
        sessionManager: { getBranch: () => entries },
      };
      await events.get("before_agent_start")?.(
        fillHostEvent("before_agent_start", {
          prompt: "Run the Playwright web E2E regression.",
        }),
        context,
      );
      await mkdir(reports, { recursive: true });
      const reportPath = resolve(reports, "playwright-report-report-main.html");
      const markdownPath = resolve(reports, "playwright-report-report-main.md");
      await Promise.all([
        writeFile(reportPath, "formal report"),
        writeFile(markdownPath, "English summary"),
      ]);
      const freshAt = new Date(Date.now() + 1_000);
      await Promise.all([
        utimes(reportPath, freshAt, freshAt),
        utimes(markdownPath, freshAt, freshAt),
      ]);

      await events.get("session_stop")?.(
        fillHostEvent("session_stop", { turn_id: 1, stop_hook_active: false }),
        context,
      );
      expect(entries).toContainEqual(
        expect.objectContaining({
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: expect.objectContaining({
            validationReport: expect.objectContaining({
              formalArtifact: expect.objectContaining({ status: "blocked" }),
            }),
          }),
        }),
      );

      await writeFile(markdownPath, "中文汇总");
      const chineseAt = new Date(Date.now() + 2_000);
      await utimes(markdownPath, chineseAt, chineseAt);
      await events.get("session_stop")?.(
        fillHostEvent("session_stop", { turn_id: 2, stop_hook_active: false }),
        context,
      );

      expect(entries).toContainEqual(
        expect.objectContaining({
          customType: SBTD_STATE_CUSTOM_TYPE,
          data: expect.objectContaining({
            validationReport: expect.objectContaining({
              checkRequirement: "required",
              validationStatus: "blocked",
              e2eMode: "blocked",
              formalArtifact: expect.objectContaining({
                status: "available",
                reportPath:
                  "tests/e2e/reports/html/playwright-report-report-main.html",
                markdownPath:
                  "tests/e2e/reports/html/playwright-report-report-main.md",
                report: expect.objectContaining({
                  sha256: expect.stringMatching(/^[0-9a-f]{64}$/),
                }),
                markdown: expect.objectContaining({
                  sha256: expect.stringMatching(/^[0-9a-f]{64}$/),
                }),
              }),
            }),
          }),
        }),
      );
    } finally {
      if (previousAgentDirectory === undefined)
        delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
      await rm(root, { force: true, recursive: true });
      await rm(agentDirectory, { force: true, recursive: true });
    }
  });
});
