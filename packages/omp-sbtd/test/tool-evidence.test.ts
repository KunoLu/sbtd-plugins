import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  createToolEvidenceObserver,
  type ToolEvidenceProbe,
  toolEvidenceCapabilityIsReady,
} from "../src/environment/tool-evidence.ts";
import { createNodeFileAdapter } from "../src/onboard/index.ts";

const roots: string[] = [];
const facet = <T extends string>(value: T, evidence: string) => ({
  value,
  evidence,
});

afterEach(async () => {
  await Promise.all(
    roots.splice(0).map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("Feature: Tool Evidence lifecycle", () => {
  it("Scenario: 同一主要 Turn 复用仍然新鲜的工具证据", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-tool-evidence-"));
    roots.push(root);
    let probeRuns = 0;
    const observedAt = "2026-07-25T00:00:00.000Z";
    const probe = (fingerprint: string): ToolEvidenceProbe => ({
      toolId: "trellis",
      capability: "trellis",
      subject: "external-tool",
      inputFingerprint: fingerprint,
      validityMs: 60_000,
      async observeInstallation() {
        probeRuns += 1;
        return facet("installed", "Trellis installation is present");
      },
      async observeConfiguration() {
        return facet("configured", "Trellis configuration is present");
      },
      async observeCallability() {
        return facet("callable", "bounded trellis --version probe passed");
      },
      async observeProjectReadiness() {
        return facet("ready", "project workflow is present");
      },
      async observeFreshness() {
        return facet("current", "probe inputs are current");
      },
    });
    const inputs = {
      files: createNodeFileAdapter(),
      storePath: resolve(root, "tool-evidence-v1.json"),
      kitRevision: "a".repeat(64),
      scope: "project" as const,
      projectRoot: root,
      probeRegistryVersion: "p0-v1",
      now: () => observedAt,
    };

    const first = await createToolEvidenceObserver(inputs).observe([
      probe("fingerprint-v1"),
    ]);
    const second = await createToolEvidenceObserver(inputs).observe([
      probe("fingerprint-v1"),
    ]);
    const changed = await createToolEvidenceObserver(inputs).observe([
      probe("fingerprint-v2"),
    ]);

    expect(probeRuns).toBe(2);
    expect(second.records).toEqual(first.records);
    expect(changed.records[0]?.inputFingerprint).toBe("fingerprint-v2");
    expect(toolEvidenceCapabilityIsReady(first.records[0])).toBe(true);
    await expect(
      inputs.files.readText(inputs.storePath),
    ).resolves.not.toContain(root);
  });

  it("reruns a probe when current evidence expires", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-tool-evidence-"));
    roots.push(root);
    let probeRuns = 0;
    let observedAt = "2026-07-25T00:00:00.000Z";
    const inputs = {
      files: createNodeFileAdapter(),
      storePath: resolve(root, "tool-evidence-v1.json"),
      kitRevision: "c".repeat(64),
      scope: "project" as const,
      projectRoot: root,
      probeRegistryVersion: "p0-v1",
      now: () => observedAt,
    };
    const probe: ToolEvidenceProbe = {
      toolId: "trellis",
      capability: "trellis",
      subject: "external-tool",
      inputFingerprint: "fingerprint-v1",
      validityMs: 1_000,
      async observeInstallation() {
        probeRuns += 1;
        return facet("installed", "Trellis installation is present");
      },
      async observeConfiguration() {
        return facet("configured", "Trellis configuration is present");
      },
      async observeCallability() {
        return facet("callable", "bounded trellis --version probe passed");
      },
      async observeProjectReadiness() {
        return facet("ready", "project workflow is present");
      },
      async observeFreshness() {
        return facet("current", "probe inputs are current");
      },
    };
    const observer = createToolEvidenceObserver(inputs);

    await observer.observe([probe]);
    observedAt = "2026-07-25T00:00:01.000Z";
    await observer.observe([probe]);

    expect(probeRuns).toBe(2);
  });

  it("does not collapse unavailable callability into another facet", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-tool-evidence-"));
    roots.push(root);
    const observer = createToolEvidenceObserver({
      files: createNodeFileAdapter(),
      storePath: resolve(root, "tool-evidence-v1.json"),
      kitRevision: "b".repeat(64),
      scope: "project",
      projectRoot: root,
      probeRegistryVersion: "p0-v1",
      now: () => "2026-07-25T00:00:00.000Z",
    });

    const result = await observer.observe([
      {
        toolId: "gitnexus",
        capability: "gitnexus",
        subject: "external-tool",
        inputFingerprint: "installed-but-unavailable",
        validityMs: 60_000,
        async observeInstallation() {
          return facet("installed", "GitNexus installation is present");
        },
        async observeConfiguration() {
          return facet("configured", "GitNexus configuration is present");
        },
        async observeCallability() {
          return facet("unavailable", "safe callability probe failed");
        },
        async observeProjectReadiness() {
          return facet("ready", "project graph is indexed");
        },
        async observeFreshness() {
          return facet("current", "probe inputs are current");
        },
      },
    ]);

    expect(result.records[0]).toMatchObject({
      installation: "installed",
      configuration: "configured",
      callability: "unavailable",
      projectReadiness: "ready",
      freshness: "current",
    });
    expect(toolEvidenceCapabilityIsReady(result.records[0])).toBe(false);
  });

  it("does not infer configuration from an installed external tool", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-tool-evidence-"));
    roots.push(root);
    const observer = createToolEvidenceObserver({
      files: createNodeFileAdapter(),
      storePath: resolve(root, "tool-evidence-v1.json"),
      kitRevision: "e".repeat(64),
      scope: "project",
      projectRoot: root,
      probeRegistryVersion: "p0-v2",
      now: () => "2026-07-25T00:00:00.000Z",
    });

    const result = await observer.observe([
      {
        toolId: "gitnexus",
        capability: "gitnexus",
        subject: "external-tool",
        inputFingerprint: "installed-but-unconfigured",
        validityMs: 60_000,
        async observeInstallation() {
          return facet("installed", "GitNexus installation is present");
        },
        async observeConfiguration() {
          return facet(
            "not-configured",
            "GitNexus MCP configuration is absent",
          );
        },
        async observeCallability() {
          return facet("callable", "bounded GitNexus probe passed");
        },
        async observeProjectReadiness() {
          return facet("ready", "project graph is indexed");
        },
        async observeFreshness() {
          return facet("current", "probe inputs are current");
        },
      },
    ]);

    expect(result.records[0]).toMatchObject({
      installation: "installed",
      configuration: "not-configured",
      callability: "callable",
      projectReadiness: "ready",
      freshness: "current",
    });
    expect(toolEvidenceCapabilityIsReady(result.records[0])).toBe(false);
  });

  it("does not create evidence storage for a read-only observation", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-tool-evidence-"));
    roots.push(root);
    const files = createNodeFileAdapter();
    const observer = createToolEvidenceObserver({
      files,
      storePath: resolve(root, "kpi", "tool-evidence-v1.json"),
      kitRevision: "c".repeat(64),
      scope: "project",
      projectRoot: root,
      probeRegistryVersion: "p0-v2",
      now: () => "2026-07-25T00:00:00.000Z",
      persist: false,
    });

    const result = await observer.observe([
      {
        toolId: "trellis",
        capability: "trellis",
        subject: "non-executable-skill",
        inputFingerprint: "read-only",
        validityMs: 60_000,
        async observeInstallation() {
          return facet("installed", "Trellis workflow is present");
        },
        async observeConfiguration() {
          return facet("configured", "Trellis workflow is configured");
        },
        async observeCallability() {
          return facet("not-needed", "Skill is non-executable");
        },
        async observeProjectReadiness() {
          return facet("ready", "Project is ready");
        },
        async observeFreshness() {
          return facet("current", "Probe inputs are current");
        },
      },
    ]);

    expect(result.records).toHaveLength(1);
    expect(await files.exists(resolve(root, "kpi"))).toBe(false);
  });

  it("rejects not-needed callability for an executable capability", async () => {
    const root = await mkdtemp(resolve(tmpdir(), "kpi-tool-evidence-"));
    roots.push(root);
    const observer = createToolEvidenceObserver({
      files: createNodeFileAdapter(),
      storePath: resolve(root, "tool-evidence-v1.json"),
      kitRevision: "d".repeat(64),
      scope: "project",
      projectRoot: root,
      probeRegistryVersion: "p0-v2",
      now: () => "2026-07-25T00:00:00.000Z",
    });

    await expect(
      observer.observe([
        {
          toolId: "gitnexus",
          capability: "gitnexus",
          subject: "external-tool",
          inputFingerprint: "no-callability-probe",
          validityMs: 60_000,
          async observeInstallation() {
            return facet("installed", "GitNexus installation is present");
          },
          async observeConfiguration() {
            return facet("configured", "GitNexus configuration is present");
          },
          async observeCallability() {
            return facet("not-needed", "callability is unavailable");
          },
          async observeProjectReadiness() {
            return facet("ready", "project graph is indexed");
          },
          async observeFreshness() {
            return facet("current", "probe inputs are current");
          },
        },
      ]),
    ).rejects.toThrow(
      "only a non-executable Skill may record callability as not-needed",
    );
  });
});
