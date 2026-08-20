import {
  cp,
  mkdtemp,
  readdir,
  readFile,
  rename,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { embedKit, pluginNoticesFor } from "../scripts/embed-kit.mjs";

const generatedManifest = import.meta.resolve(
  "@kunolu/sbtd-workflow-kit/generated-omp/manifest.json",
);
const generatedRoot = fileURLToPath(new URL(".", generatedManifest));
const pluginRoot = fileURLToPath(new URL("..", import.meta.url));

async function files(root: string, base = root): Promise<string[]> {
  const paths: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = `${root}/${entry.name}`;
    if (entry.isDirectory()) paths.push(...(await files(path, base)));
    else if (entry.isFile())
      paths.push(relative(base, path).split(sep).join("/"));
  }
  return paths.sort();
}

const temporaryRoots: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

async function snapshot(root: string): Promise<ReadonlyMap<string, Buffer>> {
  return new Map(
    await Promise.all(
      (await files(root)).map(async (path) => [
        path,
        await readFile(join(root, path)),
      ]),
    ),
  );
}

describe("Feature: 严格 OMP Plugin 发布视图", () => {
  it("Scenario: Plugin embedded tree 与 OMP Distribution Projection 逐字节一致", async () => {
    const embeddedRoot = `${pluginRoot}/kit`;
    expect(await files(embeddedRoot)).toEqual(await files(generatedRoot));
    for (const path of await files(generatedRoot)) {
      await expect(readFile(`${embeddedRoot}/${path}`)).resolves.toEqual(
        await readFile(`${generatedRoot}/${path}`),
      );
    }
    await expect(readFile(`${pluginRoot}/LICENSE`)).resolves.toEqual(
      await readFile(`${embeddedRoot}/LICENSE`),
    );
    await expect(
      readFile(`${pluginRoot}/THIRD_PARTY_NOTICES.md`, "utf8"),
    ).resolves.toContain("kit/onboard/runtime/LICENSE");
  }, 15_000);
  it("Scenario: 嵌入验证失败时保留 live Kit 并清理 staging", async () => {
    const root = await mkdtemp(join(tmpdir(), "kpi-embed-transaction-"));
    temporaryRoots.push(root);
    const source = join(root, "source");
    const destination = join(root, "kit");
    const pluginLicense = join(root, "LICENSE");
    const pluginNotices = join(root, "THIRD_PARTY_NOTICES.md");
    await cp(generatedRoot, source, { recursive: true });
    await cp(generatedRoot, destination, { recursive: true });
    await cp(join(destination, "LICENSE"), pluginLicense);
    await writeFile(
      pluginNotices,
      pluginNoticesFor(
        await readFile(join(destination, "THIRD_PARTY_NOTICES.md"), "utf8"),
      ),
      "utf8",
    );
    const liveKit = await snapshot(destination);
    const parentEntries = await readdir(root);

    const manifestPath = join(source, "manifest.json");
    const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as {
      schemaVersion: number;
    };
    manifest.schemaVersion = 1;
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

    await expect(
      embedKit({ source, destination, pluginLicense, pluginNotices }),
    ).rejects.toThrow("generated Kit manifest is invalid");

    expect(await snapshot(destination)).toEqual(liveKit);
    expect(await readdir(root)).toEqual(parentEntries);

    await rm(source, { force: true, recursive: true });
    await cp(generatedRoot, source, { recursive: true });
    await expect(
      embedKit({ source, destination, pluginLicense, pluginNotices }),
    ).resolves.toBeUndefined();
    expect(await snapshot(destination)).toEqual(await snapshot(source));
    await expect(readFile(pluginLicense)).resolves.toEqual(
      await readFile(join(destination, "LICENSE")),
    );
    await expect(readFile(pluginNotices, "utf8")).resolves.toEqual(
      pluginNoticesFor(
        await readFile(join(destination, "THIRD_PARTY_NOTICES.md"), "utf8"),
      ),
    );
    expect(await readdir(root)).toEqual(parentEntries);
  }, 30_000);
  it("Scenario: 后续 promotion 失败时还原所有 live 嵌入目标", async () => {
    const root = await mkdtemp(join(tmpdir(), "kpi-embed-promotion-"));
    temporaryRoots.push(root);
    const source = join(root, "source");
    const destination = join(root, "kit");
    const pluginLicense = join(root, "LICENSE");
    const pluginNotices = join(root, "THIRD_PARTY_NOTICES.md");
    await cp(generatedRoot, source, { recursive: true });
    await cp(generatedRoot, destination, { recursive: true });
    await writeFile(join(destination, "AGENTS.global.md"), "original Kit\n");
    await writeFile(pluginLicense, "original LICENSE\n");
    await writeFile(pluginNotices, "original notices\n");
    const liveKit = await snapshot(destination);
    const liveLicense = await readFile(pluginLicense);
    const liveNotices = await readFile(pluginNotices);
    const parentEntries = await readdir(root);
    let kitWasPromoted = false;
    let licenseWasPromoted = false;

    await expect(
      embedKit({
        source,
        destination,
        pluginLicense,
        pluginNotices,
        renameOperation: async (from: string, to: string) => {
          if (from.startsWith(`${root}/.kit.stage-`)) {
            kitWasPromoted ||= to === destination;
            licenseWasPromoted ||= to === pluginLicense;
            if (
              to === pluginNotices &&
              from.endsWith(".THIRD_PARTY_NOTICES.md")
            )
              throw new Error("injected later promotion failure");
          }
          await rename(from, to);
        },
      }),
    ).rejects.toThrow("injected later promotion failure");

    expect(kitWasPromoted).toBe(true);
    expect(licenseWasPromoted).toBe(true);
    expect(await snapshot(destination)).toEqual(liveKit);
    await expect(readFile(pluginLicense)).resolves.toEqual(liveLicense);
    await expect(readFile(pluginNotices)).resolves.toEqual(liveNotices);
    expect(
      (await readdir(root)).filter(
        (entry) => entry.includes(".stage-") || entry.includes("backup"),
      ),
    ).toEqual([]);
    expect(await readdir(root)).toEqual(parentEntries);
  }, 30_000);
  it("Scenario: 回滚还原失败时保留恢复备份并以 AggregateError 显式拒绝", async () => {
    const root = await mkdtemp(join(tmpdir(), "kpi-embed-rollback-"));
    temporaryRoots.push(root);
    const source = join(root, "source");
    const destination = join(root, "kit");
    const pluginLicense = join(root, "LICENSE");
    const pluginNotices = join(root, "THIRD_PARTY_NOTICES.md");
    await cp(generatedRoot, source, { recursive: true });
    await cp(generatedRoot, destination, { recursive: true });
    await writeFile(join(destination, "AGENTS.global.md"), "original Kit\n");
    await writeFile(pluginLicense, "original LICENSE\n");
    await writeFile(pluginNotices, "original notices\n");
    const liveLicense = await readFile(pluginLicense);
    const liveNotices = await readFile(pluginNotices);
    let kitWasPromoted = false;
    let licenseWasPromoted = false;

    const failure = await embedKit({
      source,
      destination,
      pluginLicense,
      pluginNotices,
      renameOperation: async (from: string, to: string) => {
        if (from.startsWith(`${root}/.kit.stage-`)) {
          kitWasPromoted ||= to === destination;
          licenseWasPromoted ||= to === pluginLicense;
          if (from.endsWith(".kit-backup"))
            throw new Error("injected rollback restoration failure");
          if (to === pluginNotices && from.endsWith(".THIRD_PARTY_NOTICES.md"))
            throw new Error("injected later promotion failure");
        }
        await rename(from, to);
      },
    }).then(
      () => {
        throw new Error("expected embedKit to reject");
      },
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(AggregateError);
    expect((failure as AggregateError).message).toBe(
      "embedded Kit replacement failed and rollback was incomplete",
    );
    expect((failure as AggregateError).errors).toHaveLength(2);
    expect(kitWasPromoted).toBe(true);
    expect(licenseWasPromoted).toBe(true);
    await expect(readFile(pluginLicense)).resolves.toEqual(liveLicense);
    await expect(readFile(pluginNotices)).resolves.toEqual(liveNotices);
    await expect(readdir(destination)).rejects.toThrow();
    expect(
      (await readdir(root)).filter((entry) => entry.endsWith(".kit-backup")),
    ).toHaveLength(1);
  }, 30_000);
  it("Scenario: manifest 声明的源资产被符号链接替换时拒绝嵌入并保留 live Kit", async () => {
    const root = await mkdtemp(join(tmpdir(), "kpi-embed-symlink-"));
    temporaryRoots.push(root);
    const source = join(root, "source");
    const destination = join(root, "kit");
    const pluginLicense = join(root, "LICENSE");
    const pluginNotices = join(root, "THIRD_PARTY_NOTICES.md");
    await cp(generatedRoot, source, { recursive: true });
    await cp(generatedRoot, destination, { recursive: true });
    await cp(join(destination, "LICENSE"), pluginLicense);
    await writeFile(
      pluginNotices,
      pluginNoticesFor(
        await readFile(join(destination, "THIRD_PARTY_NOTICES.md"), "utf8"),
      ),
      "utf8",
    );

    const symlinkedAsset = join(source, "AGENTS.global.md");
    const symlinkTarget = join(root, "AGENTS.global.md.original");
    await rename(symlinkedAsset, symlinkTarget);
    await symlink(symlinkTarget, symlinkedAsset);

    const liveKit = await snapshot(destination);
    const parentEntries = await readdir(root);

    await expect(
      embedKit({ source, destination, pluginLicense, pluginNotices }),
    ).rejects.toThrow();

    expect(await snapshot(destination)).toEqual(liveKit);
    expect(await readdir(root)).toEqual(parentEntries);
  }, 30_000);
});
