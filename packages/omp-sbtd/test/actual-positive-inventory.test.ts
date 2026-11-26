import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import {
  inspectPackageMetadata,
  type P0FileSystem,
  verifyEmbeddedKitReleaseIntegrity,
  verifyPluginReleaseArtifacts,
  writePluginSpdxSbom,
} from "../scripts/p0/release-validator.ts";
import { readReleaseFixture } from "./fixtures/release-fixtures.ts";

const ledgerPath =
  "onboard/runtime/assets/external-skills/stable/MANIFEST.json";
const stableNotice =
  "onboard/runtime/assets/external-skills/stable/THIRD_PARTY_NOTICES.md";
const adrPath =
  "onboard/runtime/assets/external-skills/stable/skills/domain-modeling/ADR-FORMAT.md";
const domainRoot =
  "38346247b16b399889dd630b3eb89d5baf5206f4c8f36221ee6add31bfddf058";
const mixedRoot =
  "03da9a165797514c0e8856e86cdeb4dd603bdcc1efe281e0f41a42561de2fa3f";
const rawLedger =
  "de7bccb8d8742b79b6fe43c43f4aae975d570189f49bfa983c71db89ec332022";
const semanticLedger =
  "1aa91bbeb371031be63b91f37d0e96163d3ae0ce9940d62188c4ca436258a823";
const pairedMessage =
  "The complete asset/overlay identity is not paired with its reviewed ledger/profile.";
const mhMessage =
  "Embedded Kit does not satisfy the schema-v2 projection integrity contract.";
const sha256 = (value: string | Uint8Array) =>
  createHash("sha256").update(value).digest("hex");

function requiredFixtureValue<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("Missing required fixture value");
  return value;
}

interface BoundFile {
  path: string;
  copy: string;
  sha256: string;
  bytes: number;
  license?: string;
}
interface InputData {
  actualKit: BoundFile[];
  outerInventory: BoundFile[];
  metadataOnly: Array<{
    name: string;
    copy: string;
    sha256: string;
    bytes: number;
  }>;
  expectedInventory: Array<{
    path: string;
    sha256: string;
    bytes: number;
    license: string;
  }>;
}
interface Mutation {
  operation: string;
  path: string;
  to?: string;
  sha256?: string;
  bytes?: number;
}
interface InventoryFixture {
  input: {
    workspaceRoot: string;
    pluginRoot: string;
    upstreamRoot: string;
    files: P0FileSystem;
  };
  kitRoot: string;
  sbomPath: string;
  stored: Map<string, Buffer>;
  mutations: Mutation[];
}

function ordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(ordered);
  if (value !== null && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, child]) => [key, ordered(child)]),
    );
  return value;
}

function vector(files: ReadonlyMap<string, Buffer>) {
  return [...files]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, bytes]) => ({
      path,
      bytes: bytes.length,
      sha256: sha256(bytes),
    }));
}

async function inputs() {
  const [inventory, sealedKit, sealedOuter, sealedMetadata] = await Promise.all(
    [
      readReleaseFixture("inventory"),
      readReleaseFixture("domain"),
      readReleaseFixture("outer"),
      readReleaseFixture("metadata"),
    ],
  );
  const data: InputData = JSON.parse(
    requiredFixtureValue(inventory.get("fixture-inputs.json")).toString("utf8"),
  );
  const kit = new Map<string, Buffer>();
  const outer = new Map<string, Buffer>();
  const metadata = new Map<string, Buffer>();
  for (const [records, target, nameKey, source] of [
    [data.actualKit, kit, "path", sealedKit],
    [data.outerInventory, outer, "path", sealedOuter],
    [data.metadataOnly, metadata, "name", sealedMetadata],
  ] as const) {
    for (const entry of records) {
      const name =
        nameKey === "path"
          ? (entry as BoundFile).path
          : (entry as InputData["metadataOnly"][number]).name;
      const bytes = requiredFixtureValue(source.get(name));
      expect(bytes.length).toBe(entry.bytes);
      expect(sha256(bytes)).toBe(entry.sha256);
      expect(target.has(name)).toBe(false);
      target.set(name, bytes);
    }
  }
  expect(kit.size).toBe(276);
  expect(outer.size).toBe(8);
  expect(metadata.size).toBe(5);
  return { data, kit, outer, metadata };
}

function fixture(
  kit: ReadonlyMap<string, Buffer>,
  outer: ReadonlyMap<string, Buffer>,
  metadata: ReadonlyMap<string, Buffer>,
): InventoryFixture {
  const root = "/positive-inventory-fixture";
  const pluginRoot = `${root}/plugin`;
  const upstreamRoot = `${root}/upstream`;
  const kitRoot = `${pluginRoot}/kit`;
  const sbomPath = `${pluginRoot}/SBOM.spdx.json`;
  const stored = new Map<string, Buffer>();
  const mutations: Mutation[] = [];
  const directories = new Set([`${pluginRoot}/dist`, `${pluginRoot}/skills`]);
  for (const [name, target] of [
    ["root-package.json", `${root}/package.json`],
    ["plugin-package.json", `${pluginRoot}/package.json`],
    ["upstream-package.json", `${upstreamRoot}/package.json`],
    ["root-LICENSE", `${root}/LICENSE`],
    ["upstream-LICENSE", `${upstreamRoot}/LICENSE`],
  ] as const)
    stored.set(target, Buffer.from(requiredFixtureValue(metadata.get(name))));
  for (const [path, bytes] of outer)
    stored.set(`${pluginRoot}/${path}`, Buffer.from(bytes));
  for (const [path, bytes] of kit)
    stored.set(`${kitRoot}/${path}`, Buffer.from(bytes));
  const get = (path: string) => {
    const value = stored.get(path);
    if (value === undefined)
      throw new Error(`Missing bound fixture file: ${path}`);
    return value;
  };
  const files: P0FileSystem = {
    readText: async (path) => get(path).toString("utf8"),
    readBytes: async (path) => Buffer.from(get(path)),
    inspect: async (path) => {
      if (stored.has(path)) return "file";
      if (
        directories.has(path) ||
        [...stored.keys()].some((p) => p.startsWith(`${path}/`))
      )
        return "directory";
      throw new Error(`Missing fixture path: ${path}`);
    },
    list: async (path) => {
      const found = new Map<string, "file" | "directory">();
      for (const key of stored.keys()) {
        if (!key.startsWith(`${path}/`)) continue;
        const suffix = key.slice(path.length + 1);
        found.set(
          requiredFixtureValue(suffix.split("/")[0]),
          suffix.includes("/") ? "directory" : "file",
        );
      }
      for (const directory of directories) {
        if (directory.startsWith(`${path}/`))
          found.set(
            requiredFixtureValue(
              directory.slice(path.length + 1).split("/")[0],
            ),
            "directory",
          );
      }
      return [...found].map(([name, kind]) => ({ name, kind }));
    },
    writeText: async (path, text) => {
      const bytes = Buffer.from(text);
      mutations.push({
        operation: "writeText",
        path,
        bytes: bytes.length,
        sha256: sha256(bytes),
      });
      stored.set(path, bytes);
    },
    makeDirectory: async (path) => {
      mutations.push({ operation: "makeDirectory", path });
      directories.add(path);
    },
    remove: async (path) => {
      mutations.push({ operation: "remove", path });
      for (const key of stored.keys())
        if (key === path || key.startsWith(`${path}/`)) stored.delete(key);
      for (const key of directories)
        if (key === path || key.startsWith(`${path}/`)) directories.delete(key);
    },
    move: async (path, to) => {
      mutations.push({ operation: "move", path, to });
      for (const [key, value] of [...stored])
        if (key === path || key.startsWith(`${path}/`)) {
          stored.delete(key);
          stored.set(to + key.slice(path.length), value);
        }
      for (const key of [...directories])
        if (key === path || key.startsWith(`${path}/`)) {
          directories.delete(key);
          directories.add(to + key.slice(path.length));
        }
    },
  };
  const handed = new Map(
    [...stored]
      .filter(([p]) => p.startsWith(`${kitRoot}/`))
      .map(([p, b]) => [p.slice(kitRoot.length + 1), b]),
  );
  expect([...handed.keys()].sort()).toEqual([...kit.keys()].sort());
  for (const [path, bytes] of kit)
    expect(handed.get(path)?.equals(bytes), `exact Kit handoff:${path}`).toBe(
      true,
    );
  return {
    input: { workspaceRoot: root, pluginRoot, upstreamRoot, files },
    kitRoot,
    sbomPath,
    stored,
    mutations,
  };
}

async function metadataAndMH(f: InventoryFixture) {
  await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
    plugin: { license: "Apache-2.0" },
  });
  return await verifyEmbeddedKitReleaseIntegrity({
    kitRoot: f.kitRoot,
    files: f.input.files,
  });
}

async function rejection(run: () => Promise<unknown>) {
  try {
    await run();
  } catch (error) {
    return error as Error & { code: string };
  }
  throw new Error("Expected rejection, but operation resolved");
}

function rebindHostileClaims(kit: Map<string, Buffer>, changedAsset: string) {
  const manifest = JSON.parse(
    requiredFixtureValue(kit.get("manifest.json")).toString("utf8"),
  );
  const report = JSON.parse(
    requiredFixtureValue(kit.get("projection-report.json")).toString("utf8"),
  );
  manifest.assets[changedAsset] = sha256(
    requiredFixtureValue(kit.get(changedAsset)),
  );
  if (changedAsset === ledgerPath) {
    manifest.retainedProvenance.manifestSha256 = manifest.assets[ledgerPath];
    report.retainedProvenanceManifestSha256 = manifest.assets[ledgerPath];
  }
  const root = sha256(
    [
      ...Object.entries(manifest.assets as Record<string, string>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([p, h]) => `${p}\0${h}`),
      ...Object.entries(manifest.overlayDigests as Record<string, string>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([p, h]) => `overlay:${p}\0${h}`),
    ].join("\n"),
  );
  manifest.projection.generatedSha256 = root;
  report.generatedSha256 = root;
  kit.set(
    "manifest.json",
    Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`),
  );
  kit.set(
    "projection-report.json",
    Buffer.from(`${JSON.stringify(report, null, 2)}\n`),
  );
  return root;
}

async function assertPairedRejection(f: InventoryFixture) {
  const mh = await metadataAndMH(f);
  expect([mixedRoot, domainRoot]).not.toContain(mh.projection.generatedSha256);
  expect(f.stored.has(f.sbomPath)).toBe(false);
  const start = f.mutations.length;
  const error = await rejection(() => writePluginSpdxSbom(f.input));
  expect(error).toMatchObject({
    code: "LICENSE_MISMATCH",
    message: pairedMessage,
  });
  expect(f.mutations.slice(start)).toEqual([]);
  expect(f.stored.has(f.sbomPath)).toBe(false);
}

async function noticeTamper(target: string, offset: number) {
  const { data, kit, outer, metadata } = await inputs();
  const clean = fixture(kit, outer, metadata);
  const cleanManifest = await metadataAndMH(clean);
  expect(cleanManifest.projection.generatedSha256).toBe(domainRoot);
  const before = vector(kit);
  const original = requiredFixtureValue(kit.get(target));
  expect(sha256(original)).toBe(
    requiredFixtureValue(data.actualKit.find((x) => x.path === target)).sha256,
  );
  expect(original[offset]).toBe(0x50);
  expect(
    original
      .subarray(offset, offset + "Permission is hereby granted".length)
      .toString("utf8"),
  ).toBe("Permission is hereby granted");
  const changed = Buffer.from(original);
  changed[offset] = 0x51;
  expect(changed.length).toBe(original.length);
  expect([...changed].filter((b, i) => b !== original[i])).toHaveLength(1);
  kit.set(target, changed);
  const after = vector(kit);
  const modified = after
    .filter(
      (row, index) => row.sha256 !== requiredFixtureValue(before[index]).sha256,
    )
    .map((row) => row.path);
  expect(modified).toEqual([target]);
  const f = fixture(kit, outer, metadata);
  await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
    plugin: { license: "Apache-2.0" },
  });
  const mh = await rejection(() =>
    verifyEmbeddedKitReleaseIntegrity({
      kitRoot: f.kitRoot,
      files: f.input.files,
    }),
  );
  expect(mh).toMatchObject({
    code: "PACKAGE_CONTENT_INVALID",
    message: mhMessage,
  });
  expect(f.stored.has(f.sbomPath)).toBe(false);
  const start = f.mutations.length;
  const writer = await rejection(() => writePluginSpdxSbom(f.input));
  expect(writer).toMatchObject({
    code: "PACKAGE_CONTENT_INVALID",
    message: mhMessage,
  });
  expect(f.mutations.slice(start)).toEqual([]);
  expect(f.stored.has(f.sbomPath)).toBe(false);
}

describe("Actual inventory consumption", () => {
  it("accepts bound domain inventory", async () => {
    const { data, kit, outer, metadata } = await inputs();
    const f = fixture(kit, outer, metadata);
    const before = vector(f.stored);
    const mh = await metadataAndMH(f);
    expect(mh.projection.generatedSha256).toBe(domainRoot);
    expect(f.stored.has(f.sbomPath)).toBe(false);
    const expected = [...data.expectedInventory].sort((a, b) =>
      a.path.localeCompare(b.path),
    );
    expect(expected).toHaveLength(284);
    expect(new Set(expected.map((x) => x.path)).size).toBe(284);
    expect(expected.filter((x) => x.license === "Apache-2.0")).toHaveLength(
      174,
    );
    expect(expected.filter((x) => x.license === "MIT")).toHaveLength(110);
    const plugin = JSON.parse(
      requiredFixtureValue(metadata.get("plugin-package.json")).toString(
        "utf8",
      ),
    );
    const sourceIdentityInput = {
      plugin: { name: plugin.name, version: plugin.version },
      kit: { generatedSha256: domainRoot },
      files: expected.map(({ path, sha256, license }) => ({
        path,
        sha256,
        license,
      })),
    };
    const independentlyExpectedSourceHash = sha256(
      `${JSON.stringify(ordered(sourceIdentityInput), null, 2)}\n`,
    );
    const start = f.mutations.length;
    const written = await writePluginSpdxSbom(f.input);
    const writerCalls = f.mutations.slice(start);
    expect(writerCalls).toHaveLength(1);
    expect(writerCalls[0]).toMatchObject({
      operation: "writeText",
      path: f.sbomPath,
    });
    const sbomBytes = requiredFixtureValue(f.stored.get(f.sbomPath));
    const sbom = JSON.parse(sbomBytes.toString("utf8"));
    expect(written.sourceTreeSha256).toBe(independentlyExpectedSourceHash);
    expect(written.sbomSha256).toBe(sha256(sbomBytes));
    expect(sbom.documentNamespace).toBe(
      `https://kpi.local/spdx/${independentlyExpectedSourceHash}`,
    );
    expect(sbom.files).toHaveLength(284);
    expect(
      new Set(sbom.files.map((x: { fileName: string }) => x.fileName)).size,
    ).toBe(284);
    expect(
      sbom.files.map((x: { fileName: string }) => x.fileName).sort(),
    ).toEqual(expected.map((x) => `./${x.path}`).sort());
    for (const item of expected) {
      const actual = sbom.files.find(
        (x: { fileName: string }) => x.fileName === `./${item.path}`,
      );
      expect(actual.checksums).toEqual([
        { algorithm: "SHA256", checksumValue: item.sha256 },
      ]);
      expect(actual.licenseConcluded).toBe(item.license);
      expect(actual.licenseInfoInFiles).toEqual([item.license]);
    }
    expect(sbom.packages[0]).toMatchObject({
      licenseConcluded: "Apache-2.0",
      licenseDeclared: "Apache-2.0",
    });
    expect(
      sbom.files.map((x: { fileName: string }) => x.fileName),
    ).not.toContain("./SBOM.spdx.json");
    expect(
      sbom.files.map((x: { fileName: string }) => x.fileName),
    ).not.toContain("./package.json");
    const verifierStart = f.mutations.length;
    const verified = await verifyPluginReleaseArtifacts(f.input);
    expect(verified).toEqual(written);
    expect(verified.sourceTreeSha256).toBe(independentlyExpectedSourceHash);
    expect(verified.sbomSha256).toBe(
      sha256(requiredFixtureValue(f.stored.get(f.sbomPath))),
    );
    expect(f.mutations.slice(verifierStart)).toEqual([]);
    const afterWithoutSbom = vector(
      new Map([...f.stored].filter(([p]) => p !== f.sbomPath)),
    );
    expect(afterWithoutSbom).toEqual(before);
  });

  it("rejects unreviewed self-consistent root", async () => {
    const { kit, outer, metadata } = await inputs();
    const before = vector(kit);
    const original = requiredFixtureValue(kit.get(adrPath));
    expect(sha256(original)).toBe(
      "944c92aa790e8fbdc9199640b170979abb8a34ba8d0fe18c2a01a63bce140ca0",
    );
    const manifestBefore = JSON.parse(
      requiredFixtureValue(kit.get("manifest.json")).toString("utf8"),
    );
    expect(manifestBefore.overlayDigests[adrPath]).toBeUndefined();
    kit.set(
      adrPath,
      Buffer.concat([
        original,
        Buffer.from("\nUNREVIEWED INVENTORY BOUNDARY FIXTURE\n"),
      ]),
    );
    const root = rebindHostileClaims(kit, adrPath);
    expect([mixedRoot, domainRoot]).not.toContain(root);
    expect(sha256(requiredFixtureValue(kit.get(ledgerPath)))).toBe(rawLedger);
    expect(
      sha256(
        `${JSON.stringify(ordered(JSON.parse(requiredFixtureValue(kit.get(ledgerPath)).toString("utf8"))), null, 2)}\n`,
      ),
    ).toBe(semanticLedger);
    const after = vector(kit);
    expect(
      after
        .filter((v, i) => v.sha256 !== requiredFixtureValue(before[i]).sha256)
        .map((v) => v.path)
        .sort(),
    ).toEqual([adrPath, "manifest.json", "projection-report.json"].sort());
    const f = fixture(kit, outer, metadata);
    await assertPairedRejection(f);
  });

  it("rejects raw ledger reserialization", async () => {
    const { kit, outer, metadata } = await inputs();
    const before = vector(kit);
    const originalLedger = requiredFixtureValue(kit.get(ledgerPath));
    expect(sha256(originalLedger)).toBe(rawLedger);
    const value = JSON.parse(originalLedger.toString("utf8"));
    const semantic = sha256(`${JSON.stringify(ordered(value), null, 2)}\n`);
    expect(semantic).toBe(semanticLedger);
    const reserialized = Buffer.from(`${JSON.stringify(value, null, 4)}\n`);
    expect(sha256(reserialized)).not.toBe(rawLedger);
    expect(
      sha256(
        `${JSON.stringify(ordered(JSON.parse(reserialized.toString("utf8"))), null, 2)}\n`,
      ),
    ).toBe(semantic);
    kit.set(ledgerPath, reserialized);
    const root = rebindHostileClaims(kit, ledgerPath);
    expect([mixedRoot, domainRoot]).not.toContain(root);
    const after = vector(kit);
    expect(
      after
        .filter((v, i) => v.sha256 !== requiredFixtureValue(before[i]).sha256)
        .map((v) => v.path)
        .sort(),
    ).toEqual([ledgerPath, "manifest.json", "projection-report.json"].sort());
    const f = fixture(kit, outer, metadata);
    await assertPairedRejection(f);
    // Raw ledger and aggregate both changed; this does not isolate the raw guard.
  });

  it("rejects top notice byte tamper", async () => {
    await noticeTamper("THIRD_PARTY_NOTICES.md", 1758);
  });
  it("rejects stable notice byte tamper", async () => {
    await noticeTamper(stableNotice, 1314);
  });
});
