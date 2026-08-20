import { describe, expect, it } from "vitest";
import { loadEmbeddedKit } from "../src/kit/index.ts";

describe("Feature: SBTD Kit 生命周期", () => {
  it("memoizes one fully verified immutable Kit snapshot within a turn", async () => {
    const first = await loadEmbeddedKit("session:one:turn:1");
    const second = await loadEmbeddedKit("session:one:turn:1");
    const nextTurn = await loadEmbeddedKit("session:one:turn:2");

    expect(second).toBe(first);
    expect(nextTurn).not.toBe(first);
    expect(first.freshness).toBe("current");
    expect(first.provenance.resolvedRevision).toMatch(/^[0-9a-f]{40}$/);
    expect(first.provenance.manifestSha256).toMatch(/^[0-9a-f]{64}$/);
    expect(first.provenance.generatedSha256).toBe(first.kit.kitRevision);
  });

  it("Scenario: 状态显示 canonical Kit 来源与 projection 摘要", async () => {
    const embedded = await loadEmbeddedKit("session:provenance:turn:1");

    expect(embedded.provenance.sourceId).toBe("sbtd-workflow-kit-upstream");
    expect(embedded.provenance.canonicalSourceUri).toBe(
      "https://github.com/KunoLu/640-skills",
    );
    expect(embedded.provenance.canonicalManifestSha256).toMatch(
      /^[0-9a-f]{64}$/,
    );
    expect(embedded.provenance.projectionSha256).toMatch(/^[0-9a-f]{64}$/);
    expect(embedded.provenance.projectionSha256).toBe(
      embedded.provenance.generatedSha256,
    );
    expect(embedded.provenance.canonicalManifestSha256).not.toBe(
      embedded.provenance.manifestSha256,
    );
    expect(
      Object.keys(embedded.provenance.retainedProvenance.repositories).length,
    ).toBeGreaterThan(0);
    expect(
      Object.keys(embedded.provenance.retainedProvenance.skills).sort(),
    ).toEqual(
      expect.arrayContaining(["codebase-design", "tdd", "ui-ux-pro-max"]),
    );
    expect(
      embedded.provenance.retainedProvenance.skills["ui-ux-pro-max"],
    ).toMatchObject({
      repository: "ui-ux-pro-max-skill",
      sourceSubpath: ".claude/skills/ui-ux-pro-max",
      stablePath: "skills/ui-ux-pro-max",
    });
    expect(
      Object.values(embedded.provenance.retainedProvenance.repositories).map(
        (repository) => repository.url,
      ),
    ).toEqual(
      expect.arrayContaining([
        "https://github.com/mattpocock/skills.git",
        "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git",
      ]),
    );
  });
});
