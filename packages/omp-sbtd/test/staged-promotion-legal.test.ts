import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  createNodeFileSystem,
  inspectPackageMetadata,
  type P0FileSystem,
  verifyEmbeddedKitReleaseIntegrity,
  verifyPluginReleaseArtifacts,
  writePluginSpdxSbom,
} from "../scripts/p0/release-validator.ts";
import type { EmbeddedKitManifestV2 } from "../src/kit/manifest.ts";
import { readReleaseFixture } from "./fixtures/release-fixtures.ts";

const stableRoot = "onboard/runtime/assets/external-skills/stable";
const ledgerPath = `${stableRoot}/MANIFEST.json`;
const stableNoticePath = `${stableRoot}/THIRD_PARTY_NOTICES.md`;
const topNoticePath = "THIRD_PARTY_NOTICES.md";
const phosphorPath = `${stableRoot}/skills/ui-ux-pro-max/data/phosphor-icons-upstream.json`;
const overlayPath = "onboard/runtime/templates/project/gitignore.template";
const oldRevision = "1d82494d74f6df9bca7dccef2da409f87091883e";
const newRevision = "2222222222222222222222222222222222222222";
const oldRoot =
  "b1e4bab0fa5bc30f874329773b099b486efed9eeec795022a904c5a65dd7dbf3";
const oldLedgerSha256 =
  "b502153cbb7e6bb4fa06fd3bc1459a4e2b586858cd22b53e6ffcf0f8f7c9d257";
const mhMessage =
  "Embedded Kit does not satisfy the schema-v2 projection integrity contract.";
const temporaryRoots: string[] = [];
const sha256 = (bytes: string | Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
const jsonBytes = (value: unknown) =>
  Buffer.from(`${JSON.stringify(value, null, 2)}\n`);

interface OldKitInput {
  root: string;
  manifestSha256: string;
  ledgerSha256: string;
  projectionReportSha256: string;
  files: Record<string, string | null>;
}

interface Ledger {
  schemaVersion: number;
  stableSet: string;
  promotedAt: string;
  repositories: Record<
    string,
    {
      url: string;
      revision: string;
      license: string;
      licenseFiles: Array<{ source: string; stablePath: string }>;
      [key: string]: unknown;
    }
  >;
  skills: Record<
    string,
    {
      repository: string;
      sourceSubpath: string;
      stablePath: string;
      treeSha256: string;
      [key: string]: unknown;
    }
  >;
  [key: string]: unknown;
}

interface Candidate {
  kit: Map<string, Buffer>;
  manifest: EmbeddedKitManifestV2;
  ledger: Ledger;
  report: {
    canonicalManifestSha256: string;
    generatedSha256: string;
    retainedProvenanceManifestSha256: string;
    [key: string]: unknown;
  };
}

interface Mutation {
  operation: "writeText" | "makeDirectory" | "move" | "remove";
  path: string;
  to?: string;
}

function required<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("Missing sealed test input");
  return value;
}

function projectionClaim(manifest: EmbeddedKitManifestV2): string {
  return sha256(
    [
      ...Object.entries(manifest.assets)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([path, hash]) => `${path}\0${hash}`),
      ...Object.entries(manifest.overlayDigests)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([path, hash]) => `overlay:${path}\0${hash}`),
    ].join("\n"),
  );
}

// These are attacker/candidate claims, never an expected legal identity.
function rebindClaims(
  candidate: Candidate,
  ledgerBytes = jsonBytes(candidate.ledger),
): void {
  const { kit, manifest, ledger, report } = candidate;
  kit.set(ledgerPath, ledgerBytes);
  manifest.assets = Object.fromEntries(
    [...kit]
      .filter(
        ([path]) =>
          path !== "manifest.json" && path !== "projection-report.json",
      )
      .map(([path, bytes]) => [path, sha256(bytes)]),
  );
  for (const path of Object.keys(manifest.overlayDigests))
    manifest.overlayDigests[path] = required(manifest.assets[path]);
  for (const path of Object.keys(manifest.targets))
    manifest.targets[path] = required(manifest.assets[path]);
  manifest.profileCatalogSha256 = required(manifest.assets["catalog.json"]);
  manifest.retainedProvenance = {
    stableSet: ledger.stableSet,
    manifestSha256: required(manifest.assets[ledgerPath]),
    repositories: Object.fromEntries(
      Object.entries(ledger.repositories).map(([name, repository]) => [
        name,
        {
          url: repository.url,
          revision: repository.revision,
          license: repository.license,
        },
      ]),
    ),
    skills: Object.fromEntries(
      Object.entries(ledger.skills).map(([name, skill]) => [
        name,
        {
          repository: skill.repository,
          sourceSubpath: skill.sourceSubpath,
          stablePath: skill.stablePath,
          treeSha256: skill.treeSha256,
        },
      ]),
    ),
  };
  manifest.projection.generatedSha256 = projectionClaim(manifest);
  report.generatedSha256 = manifest.projection.generatedSha256;
  report.canonicalManifestSha256 = manifest.canonical.manifestSha256;
  report.retainedProvenanceManifestSha256 =
    manifest.retainedProvenance.manifestSha256;
  kit.set("manifest.json", jsonBytes(manifest));
  kit.set("projection-report.json", jsonBytes(report));
}

async function oldCandidate(): Promise<Candidate> {
  // Inert data copied from the already-reviewed c70 old fixture. No old test
  // module, producer helper or production legal-profile allowlist is imported.
  const inputBytesJson = required(
    (await readReleaseFixture("old-input")).get("staged-old-kit.json"),
  );
  expect(sha256(inputBytesJson)).toBe(
    "9925afe84f30534131cb8332375c34ee9adfe962b681c869acbc1d4641964bb0",
  );
  const input: OldKitInput = JSON.parse(inputBytesJson.toString("utf8"));
  expect(input.root).toBe(oldRoot);
  expect(input.ledgerSha256).toBe(oldLedgerSha256);
  expect(input.manifestSha256).toBe(
    "186106a9f8b97c3391f61169c4db419983a2534b43b2566f9811e3c7e4165345",
  );
  expect(input.projectionReportSha256).toBe(
    "b5fd0c318ae18153b93046b8f77ad372a43df84a0824bb769c7ebd81688067dc",
  );
  const frozenKit = await readReleaseFixture("old");
  const inputBytes = async (path: string): Promise<Buffer> => {
    const inline = input.files[path];
    if (inline === null) throw new Error(`Deleted old fixture member: ${path}`);
    return required(frozenKit.get(path));
  };
  const manifestBytes = await inputBytes("manifest.json");
  expect(sha256(manifestBytes)).toBe(input.manifestSha256);
  const manifest: EmbeddedKitManifestV2 = JSON.parse(
    manifestBytes.toString("utf8"),
  );
  expect(manifest.canonical.resolvedRevision).toBe(oldRevision);
  expect(manifest.projection.generatedSha256).toBe(oldRoot);
  expect(projectionClaim(manifest)).toBe(oldRoot);
  const kit = new Map<string, Buffer>();
  for (const [path, hash] of Object.entries(manifest.assets)) {
    const bytes = await inputBytes(path);
    expect(sha256(bytes), `sealed old asset: ${path}`).toBe(hash);
    kit.set(path, bytes);
  }
  const ledgerBytes = required(kit.get(ledgerPath));
  expect(sha256(ledgerBytes)).toBe(oldLedgerSha256);
  const reportBytes = await inputBytes("projection-report.json");
  expect(sha256(reportBytes)).toBe(input.projectionReportSha256);
  kit.set("manifest.json", manifestBytes);
  kit.set("projection-report.json", reportBytes);

  // The original old stable notice was the sealed 740-byte prefix. Add only
  // the complete fixed attribution suffix already present in its old TOP notice.
  const prefix = required(kit.get(stableNoticePath));
  expect(prefix.length).toBe(740);
  expect(sha256(prefix)).toBe(
    "3273fbf062b2b8a58f35882ff6360df09e17948961c2355f28dbe9bc9dd7b5ee",
  );
  const top = required(kit.get(topNoticePath));
  expect(top.length).toBe(2550);
  expect(sha256(top)).toBe(
    "05be994233a0eda13f3b321741233a05665ea75ec67b3026d154fef32640591f",
  );
  const marker = Buffer.from("\n## Retained metadata attribution\n");
  const start = top.indexOf(marker);
  expect(start).toBeGreaterThan(0);
  expect(top.indexOf(marker, start + 1)).toBe(-1);
  const suffix = top.subarray(start);
  const licenseStart = suffix.indexOf(Buffer.from("MIT License\r\n"));
  expect(licenseStart).toBeGreaterThan(0);
  const license = suffix.subarray(licenseStart);
  expect(license.length).toBe(1092);
  expect(sha256(license)).toBe(
    "ddbe6082ec3cf979db47e5af549d2849c5d6182b3e005ef91ce1dbb9eb122f11",
  );
  expect(license.toString("utf8").match(/\r\n/g)).toHaveLength(21);
  expect(license.toString("utf8").replaceAll("\r\n", "")).not.toContain("\n");
  expect(suffix.subarray(0, licenseStart).toString("utf8")).toBe(
    [
      "",
      "## Retained metadata attribution",
      "",
      "### @phosphor-icons/core@2.1.1",
      "",
      `- Applies to npm package member (relative to package root): kit/${phosphorPath}`,
      "- Scope: 1512 metadata records; no SVG assets.",
      "- Source archive: https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz",
      "- Source archive SHA256: 313332be6190b724da24107addd781799b48bf76b13963f24501112ffe1baadd",
      "",
      "",
    ].join("\n"),
  );
  const metadata = required(kit.get(phosphorPath));
  expect(metadata.length).toBe(823933);
  expect(sha256(metadata)).toBe(
    "2399325233b277b5c97a80e6a5e8941154f5d057beee4e7613db87c87d700236",
  );
  const metadataValue = JSON.parse(metadata.toString("utf8")) as {
    iconCount: number;
    icons: unknown[];
  };
  expect(metadataValue.iconCount).toBe(1512);
  expect(metadataValue.icons).toHaveLength(1512);
  kit.set(stableNoticePath, Buffer.concat([prefix, suffix]));
  return {
    kit,
    manifest,
    ledger: JSON.parse(ledgerBytes.toString("utf8")),
    report: JSON.parse(reportBytes.toString("utf8")),
  };
}

function replaceText(
  candidate: Candidate,
  path: string,
  from: string,
  to: string,
): void {
  const text = required(candidate.kit.get(path)).toString("utf8");
  expect(text).toContain(from);
  candidate.kit.set(path, Buffer.from(text.replaceAll(from, to)));
}

function advanceFirstParty(candidate: Candidate): void {
  candidate.manifest.canonical.resolvedRevision = newRevision;
  candidate.manifest.canonical.sourceTreeSha256 = sha256(
    "new canonical source claim",
  );
  candidate.manifest.canonical.manifestSha256 = sha256(
    "new canonical manifest claim",
  );
  candidate.manifest.canonical.generatedSha256 = sha256(
    "new canonical output claim",
  );
  replaceText(candidate, topNoticePath, oldRevision, newRevision);
  for (const path of ["AGENTS.project-omp.md", overlayPath]) {
    candidate.kit.set(
      path,
      Buffer.concat([
        required(candidate.kit.get(path)),
        Buffer.from("\n# Stage-only first-party content update.\n"),
      ]),
    );
  }
}

async function scaffold(candidate: Candidate) {
  const root = await mkdtemp(join(tmpdir(), "kpi-staged-legal-"));
  temporaryRoots.push(root);
  const pluginRoot = join(root, "plugin");
  const upstreamRoot = join(root, "upstream");
  const kitRoot = join(pluginRoot, "kit");
  await Promise.all([
    mkdir(kitRoot, { recursive: true }),
    mkdir(upstreamRoot, { recursive: true }),
    mkdir(join(pluginRoot, "validation/p0"), { recursive: true }),
    mkdir(join(root, "unrelated-destination")),
  ]);
  const [outer, metadata, payload] = await Promise.all([
    readReleaseFixture("outer"),
    readReleaseFixture("metadata"),
    readReleaseFixture("stage-package"),
  ]);
  const metadataTargets = [
    ["root-package.json", join(root, "package.json")],
    ["plugin-package.json", join(pluginRoot, "package.json")],
    ["upstream-package.json", join(upstreamRoot, "package.json")],
    ["root-LICENSE", join(root, "LICENSE")],
    ["upstream-LICENSE", join(upstreamRoot, "LICENSE")],
  ] as const;
  await Promise.all([
    ...metadataTargets.map(([name, target]) =>
      writeFile(target, required(metadata.get(name)), { mode: 0o644 }),
    ),
    ...[...outer, ...payload].map(async ([path, bytes]) => {
      const target = join(pluginRoot, path);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, bytes, { mode: 0o644 });
    }),
    ...[...candidate.kit].map(async ([path, bytes]) => {
      const target = join(kitRoot, path);
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, bytes);
    }),
  ]);
  const notices = required(candidate.kit.get(topNoticePath))
    .toString("utf8")
    .replaceAll(
      "Retained license: onboard/runtime/",
      "Retained license: kit/onboard/runtime/",
    )
    .replaceAll(
      "Retained notice: onboard/runtime/",
      "Retained notice: kit/onboard/runtime/",
    );
  await writeFile(join(pluginRoot, topNoticePath), notices);
  const untouchedPath = join(root, "unrelated-destination", "keep.bin");
  const untouchedBytes = Buffer.from([0, 255, 13, 10, 83, 66, 84, 68]);
  await writeFile(untouchedPath, untouchedBytes);
  const untouchedMode = (await stat(untouchedPath)).mode;
  const actual = createNodeFileSystem();
  const mutations: Mutation[] = [];
  const files: P0FileSystem = {
    ...actual,
    writeText: async (path, text) => {
      mutations.push({ operation: "writeText", path });
      await actual.writeText(path, text);
    },
    makeDirectory: async (path) => {
      mutations.push({ operation: "makeDirectory", path });
      await actual.makeDirectory(path);
    },
    move: async (path, to) => {
      mutations.push({ operation: "move", path, to });
      await actual.move(path, to);
    },
    remove: async (path) => {
      mutations.push({ operation: "remove", path });
      await actual.remove(path);
    },
  };
  return {
    input: { workspaceRoot: root, pluginRoot, upstreamRoot, files },
    kitRoot,
    sbomPath: join(pluginRoot, "SBOM.spdx.json"),
    mutations,
    async expectUntouched() {
      expect(await readFile(untouchedPath)).toEqual(untouchedBytes);
      expect((await stat(untouchedPath)).mode).toBe(untouchedMode);
      expect(await actual.list(dirname(untouchedPath))).toEqual([
        { name: "keep.bin", kind: "file" },
      ]);
    },
  };
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("staged-promotion legal identity", () => {
  it("staged-promotion accepts a new canonical revision and known first-party overlay without release approval", async () => {
    const candidate = await oldCandidate();
    advanceFirstParty(candidate);
    rebindClaims(candidate);
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    const mh = await verifyEmbeddedKitReleaseIntegrity({
      kitRoot: f.kitRoot,
      files: f.input.files,
    });
    expect(mh.canonical.resolvedRevision).toBe(newRevision);
    expect(mh.projection.generatedSha256).not.toBe(oldRoot);
    expect(mh.overlayDigests[overlayPath]).not.toBe(
      "4972b0fbb303c99a05f060b3a43c3860c8b88ff4ad9d32a9b1b27e07eb9fb2b9",
    );
    await expect(writePluginSpdxSbom(f.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message:
        "The first-party Apache source or retained license/notice is not the reviewed identity.",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    const written = await writePluginSpdxSbom({
      ...f.input,
      releaseRoot: "staged-promotion",
    });
    const bytes = await readFile(f.sbomPath);
    expect(written.sbomSha256).toBe(sha256(bytes));
    expect(written.sourceTreeSha256).toMatch(/^[0-9a-f]{64}$/);
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    const sbom: {
      spdxVersion: string;
      files: Array<{
        fileName: string;
        licenseConcluded: string;
        licenseInfoInFiles: string[];
      }>;
    } = JSON.parse(bytes.toString("utf8"));
    expect(sbom.spdxVersion).toBe("SPDX-2.3");
    expect(Object.keys(candidate.manifest.assets)).toHaveLength(274);
    expect(
      sbom.files.filter((file) => file.licenseConcluded === "MIT"),
    ).toHaveLength(110);
    for (const path of Object.keys(candidate.manifest.assets)) {
      const thirdParty =
        path.startsWith(`${stableRoot}/skills/`) ||
        path.startsWith(`${stableRoot}/licenses/`);
      const license = thirdParty ? "MIT" : "Apache-2.0";
      expect(
        sbom.files.filter((file) => file.fileName === `./kit/${path}`),
      ).toEqual([
        expect.objectContaining({
          licenseConcluded: license,
          licenseInfoInFiles: [license],
        }),
      ]);
    }
    const mutationsBeforeVerifier = f.mutations.length;
    await expect(verifyPluginReleaseArtifacts(f.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message:
        "The first-party Apache source or retained license/notice is not the reviewed identity.",
    });
    expect(f.mutations).toHaveLength(mutationsBeforeVerifier);
    expect(await readFile(f.sbomPath)).toEqual(bytes);
    await f.expectUntouched();
  });
});

function skillTreeClaim(candidate: Candidate, name: string): void {
  const skill = required(candidate.ledger.skills[name]);
  const prefix = `${stableRoot}/${skill.stablePath}/`;
  const hasher = createHash("sha256");
  const paths = [...candidate.kit.keys()]
    .filter((path) => path.startsWith(prefix))
    .map((path) => path.slice(prefix.length))
    .sort((left, right) => {
      const a = left.split("/");
      const b = right.split("/");
      for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
        const x = required(a[index]);
        const y = required(b[index]);
        if (x !== y) return x < y ? -1 : 1;
      }
      return a.length - b.length;
    });
  for (const path of paths) {
    for (const bytes of [
      Buffer.from(path),
      required(candidate.kit.get(`${prefix}${path}`)),
    ]) {
      const size = Buffer.alloc(8);
      size.writeBigUInt64BE(BigInt(bytes.length));
      hasher.update(size);
      hasher.update(bytes);
    }
  }
  skill.treeSha256 = hasher.digest("hex");
}

function mutateByte(candidate: Candidate, path: string): void {
  const original = required(candidate.kit.get(path));
  const changed = Buffer.from(original);
  changed[0] = required(changed[0]) ^ 1;
  expect(changed.length).toBe(original.length);
  expect(
    [...changed].filter((byte, index) => byte !== original[index]),
  ).toHaveLength(1);
  candidate.kit.set(path, changed);
}

const coherentAttacks: Array<{
  name: string;
  mutate: (candidate: Candidate) => void;
}> = [
  {
    name: "third-party single-byte change with recomputed skill tree",
    mutate(candidate) {
      mutateByte(candidate, `${stableRoot}/skills/diagnosing-bugs/SKILL.md`);
      skillTreeClaim(candidate, "diagnosing-bugs");
    },
  },
  {
    name: "third-party pin with matching source notice",
    mutate(candidate) {
      const repository = required(
        candidate.ledger.repositories["mattpocock-skills"],
      );
      replaceText(candidate, topNoticePath, repository.revision, newRevision);
      repository.revision = newRevision;
    },
  },
  {
    name: "third-party URL with matching source notice",
    mutate(candidate) {
      const repository = required(
        candidate.ledger.repositories["mattpocock-skills"],
      );
      const url = "https://github.com/unreviewed/skills.git";
      replaceText(candidate, topNoticePath, repository.url, url);
      repository.url = url;
    },
  },
  {
    name: "third-party skill reassigned to another retained owner",
    mutate(candidate) {
      required(candidate.ledger.skills["diagnosing-bugs"]).repository =
        "ponytail";
    },
  },
  {
    name: "third-party source subpath changed",
    mutate(candidate) {
      required(candidate.ledger.skills["diagnosing-bugs"]).sourceSubpath =
        "skills/other-owner";
    },
  },
  {
    name: "third-party license relabeled Apache in ledger and notice",
    mutate(candidate) {
      required(candidate.ledger.repositories["mattpocock-skills"]).license =
        "Apache-2.0";
      replaceText(
        candidate,
        topNoticePath,
        "- License: MIT",
        "- License: Apache-2.0",
      );
      replaceText(candidate, stableNoticePath, "| MIT |", "| Apache-2.0 |");
    },
  },
  {
    name: "unknown path below an otherwise known first-party prefix",
    mutate(candidate) {
      candidate.kit.set(
        "onboard/runtime/unreviewed-stage.md",
        Buffer.from("Unknown asset.\n"),
      );
    },
  },
  {
    name: "missing known first-party path",
    mutate(candidate) {
      expect(
        candidate.kit.delete("onboard/runtime/assets/graft-instructions.txt"),
      ).toBe(true);
    },
  },
  {
    name: "missing third-party path with recomputed skill tree",
    mutate(candidate) {
      expect(
        candidate.kit.delete(
          `${stableRoot}/skills/domain-modeling/ADR-FORMAT.md`,
        ),
      ).toBe(true);
      skillTreeClaim(candidate, "domain-modeling");
    },
  },
  {
    name: "overlapping retained skill ownership paths",
    mutate(candidate) {
      required(candidate.ledger.skills["diagnosing-bugs"]).stablePath =
        required(candidate.ledger.skills.tdd).stablePath;
      skillTreeClaim(candidate, "diagnosing-bugs");
    },
  },
  ...[
    "LICENSE",
    "onboard/runtime/LICENSE",
    "onboard/runtime/NOTICE",
    "third-party/sbtd-workflow-onboard/LICENSE",
    "third-party/sbtd-workflow-onboard/NOTICE",
    "onboard/runtime/templates/skills/seo-geo/LICENSE",
    "onboard/runtime/templates/skills/seo-geo/NOTICE",
    `${stableRoot}/licenses/mattpocock-skills-LICENSE`,
  ].map((path) => ({
    name: `retained legal bytes changed: ${path}`,
    mutate: (candidate: Candidate) => mutateByte(candidate, path),
  })),
  {
    name: "canonical source notice disagrees with manifest revision",
    mutate(candidate) {
      replaceText(candidate, topNoticePath, newRevision, oldRevision);
    },
  },
  {
    name: "Apache source attribution falsified outside a display field",
    mutate(candidate) {
      replaceText(
        candidate,
        topNoticePath,
        "- License: Apache-2.0",
        "- License: MIT",
      );
    },
  },
  ...[topNoticePath, stableNoticePath].flatMap((path) => [
    {
      name: `false Phosphor copyright: ${path}`,
      mutate: (candidate: Candidate) =>
        replaceText(
          candidate,
          path,
          "Copyright (c) 2023 Phosphor Icons",
          "Copyright (c) 2023 Unreviewed Owner",
        ),
    },
    {
      name: `Phosphor MIT single-byte tamper: ${path}`,
      mutate: (candidate: Candidate) =>
        replaceText(
          candidate,
          path,
          "Permission is hereby granted",
          "Qermission is hereby granted",
        ),
    },
    {
      name: `Phosphor CRLF normalized to LF: ${path}`,
      mutate: (candidate: Candidate) =>
        replaceText(candidate, path, "\r\n", "\n"),
    },
    {
      name: `false Phosphor scope: ${path}`,
      mutate: (candidate: Candidate) =>
        replaceText(
          candidate,
          path,
          "- Scope: 1512 metadata records; no SVG assets.",
          "- Scope: all SVG assets.",
        ),
    },
    {
      name: `missing full Phosphor attribution: ${path}`,
      mutate(candidate: Candidate) {
        const bytes = required(candidate.kit.get(path));
        const marker = bytes.indexOf(
          Buffer.from("\n## Retained metadata attribution\n"),
        );
        expect(marker).toBeGreaterThan(0);
        candidate.kit.set(path, bytes.subarray(0, marker));
      },
    },
    {
      name: `duplicated Phosphor attribution: ${path}`,
      mutate(candidate: Candidate) {
        const bytes = required(candidate.kit.get(path));
        const marker = bytes.indexOf(
          Buffer.from("\n## Retained metadata attribution\n"),
        );
        expect(marker).toBeGreaterThan(0);
        candidate.kit.set(path, Buffer.concat([bytes, bytes.subarray(marker)]));
      },
    },
  ]),
  {
    name: "Phosphor metadata changed with recomputed skill tree",
    mutate(candidate) {
      replaceText(
        candidate,
        phosphorPath,
        '"verifiedAt": "2026-08-13"',
        '"verifiedAt": "2026-08-14"',
      );
      skillTreeClaim(candidate, "ui-ux-pro-max");
    },
  },
  {
    name: "unknown overlay claims a known non-overlay path",
    mutate(candidate) {
      const path = "onboard/runtime/assets/graft-instructions.txt";
      candidate.manifest.overlayDigests[path] = sha256(
        required(candidate.kit.get(path)),
      );
    },
  },
  {
    name: "third-party asset relabeled as an overlay",
    mutate(candidate) {
      const path = `${stableRoot}/skills/diagnosing-bugs/SKILL.md`;
      candidate.manifest.overlayDigests[path] = sha256(
        required(candidate.kit.get(path)),
      );
    },
  },
  {
    name: "missing required known overlay binding",
    mutate(candidate) {
      delete candidate.manifest.overlayDigests[overlayPath];
    },
  },
  {
    name: "extra top-level ledger legal assertion",
    mutate(candidate) {
      candidate.ledger.licenseOverride = "Apache-2.0";
    },
  },
  {
    name: "extra retained repository ledger assertion",
    mutate(candidate) {
      required(candidate.ledger.repositories["mattpocock-skills"]).owner =
        "first-party";
    },
  },
  {
    name: "extra retained skill ledger assertion",
    mutate(candidate) {
      required(candidate.ledger.skills["diagnosing-bugs"]).license =
        "Apache-2.0";
    },
  },
  {
    name: "display fields used to smuggle a false attribution",
    mutate(candidate) {
      const before = candidate.ledger.stableSet;
      candidate.ledger.stableSet = `${before})\n\n- License: Apache-2.0\n\n## Injected (`;
      replaceText(
        candidate,
        topNoticePath,
        `(stable set ${before})`,
        `(stable set ${candidate.ledger.stableSet})`,
      );
    },
  },
];

describe("staged-promotion attack boundary", () => {
  it("accepts stableSet and promotedAt display changes without changing legal approval", async () => {
    const candidate = await oldCandidate();
    const before = candidate.ledger.stableSet;
    candidate.ledger.stableSet = "2026-08-03.2";
    candidate.ledger.promotedAt = "2026-11-21";
    replaceText(
      candidate,
      topNoticePath,
      `(stable set ${before})`,
      "(stable set 2026-08-03.2)",
    );
    rebindClaims(candidate);
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).resolves.toMatchObject({
      retainedProvenance: { stableSet: "2026-08-03.2" },
    });
    await expect(writePluginSpdxSbom(f.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message:
        "The complete retained source ledger is not a reviewed old or domain-only identity.",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).resolves.toMatchObject({
      sourceTreeSha256: expect.stringMatching(/^[0-9a-f]{64}$/),
      sbomSha256: expect.stringMatching(/^[0-9a-f]{64}$/),
    });
    const sbom = await readFile(f.sbomPath);
    expect(JSON.parse(sbom.toString("utf8")).spdxVersion).toBe("SPDX-2.3");
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    await expect(verifyPluginReleaseArtifacts(f.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message:
        "The complete retained source ledger is not a reviewed old or domain-only identity.",
    });
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    expect(await readFile(f.sbomPath)).toEqual(sbom);
    await f.expectUntouched();
  });

  it("accepts only the staged legal contract for a known overlay at the fixed canonical revision", async () => {
    const candidate = await oldCandidate();
    candidate.kit.set(
      overlayPath,
      Buffer.concat([
        required(candidate.kit.get(overlayPath)),
        Buffer.from("\n# Reviewed first-party overlay candidate.\n"),
      ]),
    );
    rebindClaims(candidate);
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    const mh = await verifyEmbeddedKitReleaseIntegrity({
      kitRoot: f.kitRoot,
      files: f.input.files,
    });
    expect(mh.canonical.resolvedRevision).toBe(oldRevision);
    expect(mh.projection.generatedSha256).not.toBe(oldRoot);
    await expect(writePluginSpdxSbom(f.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message: `Overlay has no reviewed first-party license identity: ${overlayPath}`,
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" });
    const sbom = await readFile(f.sbomPath);
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    await expect(verifyPluginReleaseArtifacts(f.input)).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message: `Overlay has no reviewed first-party license identity: ${overlayPath}`,
    });
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    expect((await readFile(f.sbomPath)).equals(sbom)).toBe(true);
    await f.expectUntouched();
  });

  it("does not release-trust a self-consistent notice-complete old stage root", async () => {
    const candidate = await oldCandidate();
    rebindClaims(candidate);
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    const mh = await verifyEmbeddedKitReleaseIntegrity({
      kitRoot: f.kitRoot,
      files: f.input.files,
    });
    expect(mh.canonical.resolvedRevision).toBe(oldRevision);
    expect(mh.projection.generatedSha256).not.toBe(oldRoot);
    const rejection = {
      code: "LICENSE_MISMATCH",
      message:
        "The complete asset/overlay identity is not paired with its reviewed ledger/profile.",
    };
    await expect(writePluginSpdxSbom(f.input)).rejects.toMatchObject(rejection);
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" });
    const sbom = await readFile(f.sbomPath);
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    await expect(verifyPluginReleaseArtifacts(f.input)).rejects.toMatchObject(
      rejection,
    );
    expect(f.mutations).toEqual([{ operation: "writeText", path: f.sbomPath }]);
    expect((await readFile(f.sbomPath)).equals(sbom)).toBe(true);
    await f.expectUntouched();
  });

  it.each(
    coherentAttacks,
  )("rejects coherent $name before every mutation API", async ({ mutate }) => {
    const candidate = await oldCandidate();
    advanceFirstParty(candidate);
    mutate(candidate);
    rebindClaims(candidate);
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    // Deliberately require genuine MH success: rehashed attacker claims must
    // reach legal classification, rather than pass the test via a stale digest.
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).resolves.toMatchObject({
      canonical: { resolvedRevision: newRevision },
      projection: {
        generatedSha256: candidate.manifest.projection.generatedSha256,
      },
    });
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).rejects.toMatchObject({
      name: "P0ValidationError",
      code: "LICENSE_MISMATCH",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await f.expectUntouched();
  });

  it("rejects raw ledger reserialization with unchanged legal facts and rebound aggregate claims", async () => {
    const candidate = await oldCandidate();
    rebindClaims(candidate);
    const before = new Map(
      [...candidate.kit].map(([path, bytes]) => [path, sha256(bytes)]),
    );
    const canonicalLedger = required(candidate.kit.get(ledgerPath));
    expect(sha256(canonicalLedger)).toBe(oldLedgerSha256);
    const reserialized = Buffer.from(
      `${JSON.stringify(candidate.ledger, null, 4)}\n`,
    );
    expect(JSON.parse(reserialized.toString("utf8"))).toEqual(
      JSON.parse(canonicalLedger.toString("utf8")),
    );
    expect(sha256(reserialized)).not.toBe(oldLedgerSha256);
    // Unlike stableSet/promotedAt, whitespace is not an authorized display
    // field. Rebind the hostile raw ledger without normalizing it back.
    rebindClaims(candidate, reserialized);
    expect(
      [...candidate.kit]
        .filter(([path, bytes]) => before.get(path) !== sha256(bytes))
        .map(([path]) => path)
        .sort(),
    ).toEqual([ledgerPath, "manifest.json", "projection-report.json"].sort());
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).resolves.toMatchObject({
      retainedProvenance: { manifestSha256: sha256(reserialized) },
      projection: {
        generatedSha256: candidate.manifest.projection.generatedSha256,
      },
    });
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).rejects.toMatchObject({
      name: "P0ValidationError",
      code: "LICENSE_MISMATCH",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await f.expectUntouched();
  });

  it.each([
    "package LICENSE",
    "package notice copyright",
    "package notice CRLF",
  ])("rejects %s outside the Kit without changing any destination", async (attack) => {
    const candidate = await oldCandidate();
    advanceFirstParty(candidate);
    rebindClaims(candidate);
    const f = await scaffold(candidate);
    const path = join(
      f.input.pluginRoot,
      attack === "package LICENSE" ? "LICENSE" : topNoticePath,
    );
    const original = await readFile(path, "utf8");
    const changed =
      attack === "package LICENSE"
        ? `${original}\nUnreviewed license addition.\n`
        : attack === "package notice copyright"
          ? original.replace(
              "Copyright (c) 2023 Phosphor Icons",
              "Copyright (c) 2023 Unreviewed Owner",
            )
          : original.replaceAll("\r\n", "\n");
    expect(changed).not.toBe(original);
    await writeFile(path, changed);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).resolves.toMatchObject({
      canonical: { resolvedRevision: newRevision },
    });
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).rejects.toMatchObject({
      name: "P0ValidationError",
      code: "LICENSE_MISMATCH",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    expect(await readFile(path, "utf8")).toBe(changed);
    await f.expectUntouched();
  });

  it.each([
    "unbound byte tamper",
    "missing retained manifest",
    "ledger and provenance disagreement",
    "malformed canonical revision",
  ])("rejects structurally incoherent %s at MH, not the legal gate", async (attack) => {
    const candidate = await oldCandidate();
    advanceFirstParty(candidate);
    rebindClaims(candidate);
    if (attack === "unbound byte tamper") {
      mutateByte(candidate, `${stableRoot}/skills/diagnosing-bugs/SKILL.md`);
    } else if (attack === "missing retained manifest") {
      candidate.kit.delete(ledgerPath);
    } else if (attack === "ledger and provenance disagreement") {
      candidate.manifest.retainedProvenance.stableSet = "unbound-display-value";
      candidate.kit.set("manifest.json", jsonBytes(candidate.manifest));
    } else {
      candidate.manifest.canonical.resolvedRevision = "main";
      candidate.kit.set("manifest.json", jsonBytes(candidate.manifest));
    }
    const f = await scaffold(candidate);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    const failure = { code: "PACKAGE_CONTENT_INVALID", message: mhMessage };
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).rejects.toMatchObject(failure);
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).rejects.toMatchObject(failure);
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await f.expectUntouched();
  });
});

describe("staged-promotion already reviewed release profile", () => {
  it("rejects false package attribution even when the domain Kit has a trusted release root", async () => {
    const frozenKit = await readReleaseFixture("domain");
    const manifestBytes = required(frozenKit.get("manifest.json"));
    const manifest: EmbeddedKitManifestV2 = JSON.parse(
      manifestBytes.toString("utf8"),
    );
    expect(manifest.projection.generatedSha256).toBe(
      "38346247b16b399889dd630b3eb89d5baf5206f4c8f36221ee6add31bfddf058",
    );
    expect(projectionClaim(manifest)).toBe(manifest.projection.generatedSha256);
    const kit = new Map<string, Buffer>();
    for (const [path, expected] of Object.entries(manifest.assets)) {
      const bytes = required(frozenKit.get(path));
      expect(sha256(bytes)).toBe(expected);
      kit.set(path, bytes);
    }
    kit.set("manifest.json", manifestBytes);
    const reportBytes = required(frozenKit.get("projection-report.json"));
    kit.set("projection-report.json", reportBytes);
    const candidate: Candidate = {
      kit,
      manifest,
      ledger: JSON.parse(required(kit.get(ledgerPath)).toString("utf8")),
      report: JSON.parse(reportBytes.toString("utf8")),
    };
    const f = await scaffold(candidate);
    const noticePath = join(f.input.pluginRoot, topNoticePath);
    const original = await readFile(noticePath, "utf8");
    const changed = original.replace(
      "Copyright (c) 2023 Phosphor Icons",
      "Copyright (c) 2023 Unreviewed Owner",
    );
    expect(changed).not.toBe(original);
    await writeFile(noticePath, changed);
    await expect(inspectPackageMetadata(f.input)).resolves.toMatchObject({
      plugin: { license: "Apache-2.0" },
    });
    await expect(
      verifyEmbeddedKitReleaseIntegrity({
        kitRoot: f.kitRoot,
        files: f.input.files,
      }),
    ).resolves.toMatchObject({
      projection: {
        generatedSha256:
          "38346247b16b399889dd630b3eb89d5baf5206f4c8f36221ee6add31bfddf058",
      },
    });
    await expect(
      writePluginSpdxSbom({ ...f.input, releaseRoot: "staged-promotion" }),
    ).rejects.toMatchObject({
      code: "LICENSE_MISMATCH",
      message:
        "The staged root notice is not the exact embedded Kit attribution.",
    });
    expect(f.mutations).toEqual([]);
    await expect(stat(f.sbomPath)).rejects.toMatchObject({ code: "ENOENT" });
    await f.expectUntouched();
  });
});
