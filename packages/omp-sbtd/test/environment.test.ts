import { describe, expect, it } from "vitest";
import { discoverAgentContext } from "../src/agents/index.ts";
import { evaluateProfileEnvironment } from "../src/environment/index.ts";

const observedAt = "2026-07-24T00:00:00.000Z";

describe("Feature: SBTD 控制引导", () => {
  it("Scenario: 缺失选定 Profile 基线进入 Onboard Preflight", () => {
    expect(
      evaluateProfileEnvironment(
        {
          profile: {
            id: "omp-p0-standard-v1",
            required: ["plugin-kit-alignment", "project-omp-adapter"],
            optional: [],
          },
          capabilities: {
            "plugin-kit-alignment": true,
            "project-omp-adapter": false,
          },
          routeRequiredCapabilities: [],
          acceptedOptionalSkips: [],
        },
        observedAt,
      ),
    ).toMatchObject({
      mode: "needs-onboard",
      evidence: ["project-omp-adapter"],
      repairPath: "/sbtd onboard plan",
    });
  });
  it("Scenario: 缺失 Route 专属能力仍会阻断", () => {
    expect(
      evaluateProfileEnvironment(
        {
          profile: {
            id: "omp-p0-standard-v1",
            required: ["plugin-kit-alignment"],
            optional: [],
          },
          capabilities: {
            "plugin-kit-alignment": true,
            "web-e2e-runner": false,
          },
          routeRequiredCapabilities: ["web-e2e-runner"],
          acceptedOptionalSkips: [],
        },
        observedAt,
      ),
    ).toMatchObject({
      mode: "blocked",
      evidence: ["web-e2e-runner"],
      repairPath: "/sbtd doctor",
    });
  });

  it("Scenario: 精确 Optional AcceptedSkip 只使匹配缺口降级", () => {
    expect(
      evaluateProfileEnvironment(
        {
          profile: {
            id: "omp-p0-standard-v1",
            required: ["plugin-kit-alignment"],
            optional: ["ui"],
          },
          capabilities: {
            "plugin-kit-alignment": true,
            ui: false,
          },
          routeRequiredCapabilities: [],
          acceptedOptionalSkips: [
            { capability: "ui", expiresAt: "2026-08-01T00:00:00.000Z" },
          ],
        },
        observedAt,
      ),
    ).toMatchObject({
      mode: "degraded",
      evidence: ["accepted skip: ui"],
    });
    expect(
      evaluateProfileEnvironment(
        {
          profile: {
            id: "omp-p0-standard-v1",
            required: ["ui"],
            optional: [],
          },
          capabilities: { ui: false },
          routeRequiredCapabilities: ["ui"],
          acceptedOptionalSkips: [
            { capability: "ui", expiresAt: "2026-08-01T00:00:00.000Z" },
          ],
        },
        observedAt,
      ).mode,
    ).toBe("blocked");
  });

  it("Scenario: OMP Adapter 通过根项目事实导入成为有效入口", async () => {
    const context = await discoverAgentContext({
      targets: [
        { role: "global", path: "/agent/AGENTS.md" },
        { role: "project-root", path: "/project/AGENTS.md" },
        { role: "project-omp", path: "/project/.omp/AGENTS.md" },
      ],
      readText: async (path) =>
        ({
          "/agent/AGENTS.md": "global\n",
          "/project/AGENTS.md": "project facts\n",
          "/project/.omp/AGENTS.md": "@../AGENTS.md\nOMP adapter\n",
        })[path],
    });

    expect(context.targets).toEqual([
      expect.objectContaining({
        role: "global",
        exists: true,
        discovered: true,
        loaded: true,
        effective: true,
      }),
      expect.objectContaining({
        role: "project-root",
        exists: true,
        loaded: true,
        effective: true,
        shadowedBy: "project-omp",
      }),
      expect.objectContaining({
        role: "project-omp",
        exists: true,
        loaded: true,
        effective: true,
        imports: ["@../AGENTS.md"],
      }),
    ]);
    expect(context.importValid).toBe(true);
  });
  it("Scenario: 缺失根项目事实时 OMP Adapter 导入不被视为有效", async () => {
    const context = await discoverAgentContext({
      targets: [
        { role: "project-root", path: "/project/AGENTS.md" },
        { role: "project-omp", path: "/project/.omp/AGENTS.md" },
      ],
      readText: async (path) =>
        path === "/project/.omp/AGENTS.md" ? "@../AGENTS.md\n" : undefined,
    });

    expect(context.importValid).toBe(false);
    expect(context.targets).toEqual([
      expect.objectContaining({
        role: "project-root",
        exists: false,
        loaded: false,
        effective: false,
        shadowedBy: "project-omp",
      }),
      expect.objectContaining({
        role: "project-omp",
        exists: true,
        loaded: true,
        effective: false,
      }),
    ]);
  });

  it("Scenario: 未导入根项目事实的 OMP Adapter 使根项目事实失效", async () => {
    const context = await discoverAgentContext({
      targets: [
        { role: "project-root", path: "/project/AGENTS.md" },
        { role: "project-omp", path: "/project/.omp/AGENTS.md" },
      ],
      readText: async (path) =>
        ({
          "/project/AGENTS.md": "project facts\n",
          "/project/.omp/AGENTS.md": "malformed adapter\n",
        })[path],
    });

    expect(context.importValid).toBe(false);
    expect(context.targets).toEqual([
      expect.objectContaining({
        role: "project-root",
        exists: true,
        loaded: true,
        effective: false,
        shadowedBy: "project-omp",
      }),
      expect.objectContaining({
        role: "project-omp",
        exists: true,
        loaded: true,
        effective: false,
      }),
    ]);
  });
});
