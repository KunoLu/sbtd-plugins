import { createHash } from "node:crypto";
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  pluginNoticesFor,
  validateEmbeddedKit,
} from "../scripts/embed-kit.mjs";

const sha256 = (value: string | Uint8Array): string =>
  createHash("sha256").update(value).digest("hex");

const generatedManifestUrl = import.meta.resolve(
  "@kunolu/sbtd-workflow-kit/generated-omp/manifest.json",
);
const generatedRoot = fileURLToPath(new URL(".", generatedManifestUrl));
const STABLE_MANIFEST_KIT_PATH =
  "onboard/runtime/assets/external-skills/stable/MANIFEST.json";

const temporaryRoots: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

interface EmbeddedFixture {
  readonly source: string;
  readonly destination: string;
  readonly pluginLicense: string;
  readonly pluginNotices: string;
}

async function embeddedFixture(): Promise<EmbeddedFixture> {
  const root = await mkdtemp(join(tmpdir(), "kpi-embed-provenance-"));
  temporaryRoots.push(root);
  const source = join(root, "source");
  const destination = join(root, "destination");
  await cp(generatedRoot, source, { recursive: true });
  await cp(source, destination, { recursive: true });
  const pluginLicense = join(root, "LICENSE");
  const pluginNotices = join(root, "THIRD_PARTY_NOTICES.md");
  await cp(join(destination, "LICENSE"), pluginLicense);
  await writeFile(
    pluginNotices,
    pluginNoticesFor(
      await readFile(join(destination, "THIRD_PARTY_NOTICES.md"), "utf8"),
    ),
    "utf8",
  );
  return { source, destination, pluginLicense, pluginNotices };
}

describe("Feature: 严格 OMP Plugin 发布视图", () => {
  it("Scenario: 生成与嵌入 manifest 与 embedded stable manifest 交叉验证", async () => {
    const fixture = await embeddedFixture();

    await expect(validateEmbeddedKit(fixture)).resolves.toBeUndefined();

    for (const root of [fixture.source, fixture.destination]) {
      const stableManifestPath = join(root, STABLE_MANIFEST_KIT_PATH);
      const drifted = `${await readFile(stableManifestPath, "utf8")} \n`;
      await writeFile(stableManifestPath, drifted, "utf8");
      const manifestPath = join(root, "manifest.json");
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
        assets: Record<string, string>;
      };
      manifest.assets[STABLE_MANIFEST_KIT_PATH] = sha256(
        Buffer.from(drifted, "utf8"),
      );
      await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    }

    await expect(validateEmbeddedKit(fixture)).rejects.toThrow(
      /stable manifest digest does not match derived provenance/,
    );
  }, 30_000);

  it("rejects embedded retained provenance with an omitted repository", async () => {
    const fixture = await embeddedFixture();

    for (const root of [fixture.source, fixture.destination]) {
      const manifestPath = join(root, "manifest.json");
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
        retainedProvenance: { repositories: Record<string, unknown> };
      };
      const repository = Object.keys(
        manifest.retainedProvenance.repositories,
      )[0];
      if (repository === undefined)
        throw new Error("fixture repository missing");
      delete manifest.retainedProvenance.repositories[repository];
      await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    }

    await expect(validateEmbeddedKit(fixture)).rejects.toThrow(
      /stable provenance drifted from the embedded stable manifest/,
    );
  }, 30_000);

  it("rejects embedded retained provenance with a drifted skill tree digest", async () => {
    const fixture = await embeddedFixture();

    for (const root of [fixture.source, fixture.destination]) {
      const manifestPath = join(root, "manifest.json");
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
        retainedProvenance: { skills: Record<string, { treeSha256: string }> };
      };
      const skill = Object.keys(manifest.retainedProvenance.skills)[0];
      if (skill === undefined) throw new Error("fixture skill missing");
      const entry = manifest.retainedProvenance.skills[skill];
      if (entry === undefined) throw new Error("fixture skill entry missing");
      entry.treeSha256 = "0".repeat(64);
      await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    }

    await expect(validateEmbeddedKit(fixture)).rejects.toThrow(
      /stable provenance drifted from the embedded stable manifest/,
    );
  }, 30_000);

  it("rejects an embedded kit whose manifest omits the canonical runtime binding", async () => {
    const fixture = await embeddedFixture();

    for (const root of [fixture.source, fixture.destination]) {
      const manifestPath = join(root, "manifest.json");
      const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
        assets: Record<string, string>;
      };
      delete manifest.assets["onboard/runtime/scripts/onboard.py"];
      await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    }

    await expect(validateEmbeddedKit(fixture)).rejects.toThrow(
      /canonical Onboard runtime/,
    );
  }, 30_000);

  it("rejects a canonical runtime payload that drifts from its approved digest", async () => {
    const fixture = await embeddedFixture();

    for (const root of [fixture.source, fixture.destination]) {
      const runtimePath = join(root, "onboard/runtime/scripts/onboard.py");
      const drifted = `${await readFile(runtimePath, "utf8")}\n# additional CoDeX marker\n`;
      await writeFile(runtimePath, drifted, "utf8");
    }

    await expect(validateEmbeddedKit(fixture)).rejects.toThrow(
      /forbidden non-OMP Runtime identifiers/,
    );
  }, 30_000);

  it("Scenario: Plugin 通知保留 retained 归属路径的 kit 前缀", () => {
    const kitNotices = [
      "# Third-Party Notices",
      "",
      "- Retained license: onboard/runtime/LICENSE",
      "- Retained notice: onboard/runtime/NOTICE",
      "- Retained license: onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE",
      "",
    ].join("\n");

    const pluginNotices = pluginNoticesFor(kitNotices);

    expect(pluginNotices).toContain(
      "- Retained license: kit/onboard/runtime/LICENSE",
    );
    expect(pluginNotices).toContain(
      "- Retained notice: kit/onboard/runtime/NOTICE",
    );
    expect(pluginNotices).toContain(
      "- Retained license: kit/onboard/runtime/assets/external-skills/stable/licenses/mattpocock-skills-LICENSE",
    );
  });
});
