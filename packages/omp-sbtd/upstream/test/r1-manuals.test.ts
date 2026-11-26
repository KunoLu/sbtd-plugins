import { createHash } from "node:crypto";
import {
  chmod,
  cp,
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  stat,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { sha256 } from "../src/index.ts";
import type { GenerateOmpProjectionOptions } from "../src/omp-projection.ts";
import {
  checkOmpProjection,
  generateOmpProjection,
} from "../src/omp-projection.ts";

const packageRoot = new URL("..", import.meta.url).pathname;
const temporaryRoots: string[] = [];
const capsule = "omp-source-selections/r1-manuals";
const domainCapsule = "omp-source-selections/domain-modeling";
const stableRoot = "onboard/runtime/assets/external-skills/stable";
const skillsRoot = `${stableRoot}/skills`;
const ledgerPath = `${stableRoot}/MANIFEST.json`;
const licensePath = `${stableRoot}/licenses/mattpocock-skills-LICENSE`;
const presentationPath =
  "onboard/runtime/templates/skills/sbtd-task/references/presentation.md";
const newRepository = "mattpocock-skills-r1-manuals";
const targetRevision = "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d";
const oldRevision = "3cca18b368ae95cdbdebbff572ccafa662551015";
// Independent identities from the fixed 640 supplier and Matt origin fetches.
const official = {
  grilling: {
    sha256: "a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2",
    blob: "d2f09a18e6a6c65c55f1271ba08dfeaf06f0bed3",
    bytes: 2077,
    tree: "3a7559839f45dfa4491f045d56647148c2b90f0e5ce0b5355301ef0e6d1bc428",
    sourceSubpath: "skills/productivity/grilling",
  },
  "to-tickets": {
    sha256: "56ec23c5b2782785d4e65bff9e315b6d3aeb4ef977c174a219e99489fada1995",
    blob: "9b77a01db9460c99c22d03c910c349f890f12c0e",
    bytes: 5812,
    tree: "98422855972ffb35bf33ce3eee1c1255f58e81cf801d6d3fc0185bb8e0351839",
    sourceSubpath: "skills/engineering/to-tickets",
  },
};

interface R1Fixture {
  readonly root: string;
  readonly kitRoot: string;
  readonly options: GenerateOmpProjectionOptions;
}

async function fixture(): Promise<R1Fixture> {
  const root = await mkdtemp(join(tmpdir(), "kpi-r1-manuals-"));
  temporaryRoots.push(root);
  const kitRoot = join(root, "package");
  await mkdir(kitRoot);
  for (const path of [
    "omp-distribution-map.yaml",
    "omp-overlays",
    domainCapsule,
    capsule,
  ]) {
    await cp(join(packageRoot, path), join(kitRoot, path), { recursive: true });
  }
  return {
    root,
    kitRoot,
    options: {
      packageRoot: kitRoot,
      canonicalDirectory: join(packageRoot, "generated"),
      outputDirectory: join(root, "output"),
      sourceSelection: "r1-manuals" as const,
    },
  };
}

function blob(bytes: Buffer): string {
  return createHash("sha1")
    .update(`blob ${bytes.length}\0`)
    .update(bytes)
    .digest("hex");
}

interface Identity {
  blob: string;
  mode: string;
  sha256: string;
  bytes: number;
}
interface SelectionRecord {
  scope: string;
  owner: string;
  supplier: { revision: string };
  origin: { repository: string };
  base: { repositoryRevision: string };
  target: { repositoryKey: string; repositoryRevision: string };
  domainSelection: { inputSha256: string };
  license: Identity;
  skills: {
    name: string;
    sourceSubpath: string;
    beforeTreeSha256: string;
    targetTreeSha256: string;
    files: {
      path: string;
      operation: string;
      before: Identity;
      target: Identity;
    }[];
  }[];
  presentation: { path: string; target: Identity };
}

async function changeRecord(
  root: string,
  change: (record: SelectionRecord) => void,
) {
  const path = join(root, capsule, "selection.json");
  const record: SelectionRecord = JSON.parse(await readFile(path, "utf8"));
  change(record);
  await writeFile(path, `${JSON.stringify(record, null, 2)}\n`);
}

async function rejectsWithoutPartialOutput(item: R1Fixture) {
  await mkdir(item.options.outputDirectory);
  const sentinel = join(item.options.outputDirectory, "keep.txt");
  await writeFile(sentinel, "existing-output\n");
  for (const run of [generateOmpProjection, checkOmpProjection]) {
    await expect(run(item.options)).rejects.toMatchObject({
      code: "PROJECTION_POLICY_INVALID",
    });
    expect(await readFile(sentinel, "utf8")).toBe("existing-output\n");
    expect(await readdir(item.options.outputDirectory)).toEqual(["keep.txt"]);
    expect((await readdir(item.root)).sort()).toEqual(["output", "package"]);
  }
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { recursive: true, force: true })),
  );
});

describe("R1 manuals bounded source selection", () => {
  it("generates and checks six source operations, exact official trees and MIT while preserving eight old identities", async () => {
    const item = await fixture();
    const old = await generateOmpProjection({
      packageRoot: item.kitRoot,
      canonicalDirectory: item.options.canonicalDirectory,
      outputDirectory: join(item.root, "old"),
    });
    const domain = await generateOmpProjection({
      ...item.options,
      sourceSelection: "domain-modeling",
      outputDirectory: join(item.root, "domain"),
    });
    const { manifest, report } = await generateOmpProjection(item.options);
    const ledgerBytes = await readFile(
      join(item.options.outputDirectory, ledgerPath),
    );
    const ledger = JSON.parse(ledgerBytes.toString("utf8"));
    const domainLedger = JSON.parse(
      await readFile(join(item.root, "domain", ledgerPath), "utf8"),
    );
    expect(ledger.sourceSelection).toMatchObject({
      kind: "mixed-source",
      scope: "r1-manuals",
      inputPath: `${capsule}/selection.json`,
      inputSha256:
        "290bdc6379f3f55376ac24ac660598c3013408f376834d6d96ca92b739cd90c4",
      domain: {
        role: "validated-component-input",
        receipt: domainLedger.sourceSelection,
      },
      record: {
        owner: "third-party",
        supplier: { revision: "3c835303c23d59d3157ca84121a92f1bd87d4997" },
        target: {
          repositoryKey: newRepository,
          repositoryRevision: targetRevision,
        },
        domainSelection: {
          inputSha256:
            "6cb1e695b18e76aa771be1ab052085878763a96197205bc4a0f5874384814684",
        },
      },
    });
    const finalOwnership = {
      "domain-modeling": newRepository,
      grilling: newRepository,
      "to-tickets": newRepository,
      "codebase-design": "mattpocock-skills",
      "diagnosing-bugs": "mattpocock-skills",
      "grill-me": "mattpocock-skills",
      "grill-with-docs": "mattpocock-skills",
      handoff: "mattpocock-skills",
      tdd: "mattpocock-skills",
      "to-spec": "mattpocock-skills",
      "writing-for-agents": "mattpocock-skills",
    };
    expect(ledger.sourceSelection.finalOwnership).toEqual(finalOwnership);
    expect(report.sourceSelection?.scope).toBe("r1-manuals");
    if (report.sourceSelection?.scope !== "r1-manuals")
      throw new Error("missing R1 receipt");
    expect(report.sourceSelection.finalOwnership).toEqual(finalOwnership);
    for (const [name, repository] of Object.entries(finalOwnership)) {
      expect(manifest.retainedProvenance.skills[name]?.repository).toBe(
        repository,
      );
    }
    expect(manifest.assets[ledgerPath]).toBe(sha256(ledgerBytes));
    expect(manifest.retainedProvenance.manifestSha256).toBe(
      sha256(ledgerBytes),
    );
    expect(manifest.canonical).toEqual(old.manifest.canonical);
    expect(manifest.overlayDigests).toEqual(old.manifest.overlayDigests);
    expect(report.counts).toEqual(old.report.counts);
    expect(report.decisions).toEqual(old.report.decisions);
    expect(ledger.stableSet).toBe("2026-09-14.6");
    expect(ledger.promotedAt).toBe("2026-09-14");
    expect(manifest.retainedProvenance.repositories[newRepository]).toEqual({
      url: "https://github.com/mattpocock/skills.git",
      revision: targetRevision,
      license: "MIT",
    });
    expect(
      ledger.repositories["mattpocock-skills-domain-modeling"],
    ).toBeUndefined();
    for (const name of ["domain-modeling", "grilling", "to-tickets"]) {
      expect(manifest.retainedProvenance.skills[name]?.repository).toBe(
        newRepository,
      );
    }
    const unselected = Object.entries(
      old.manifest.retainedProvenance.skills,
    ).filter(
      ([name, skill]) =>
        skill.repository === "mattpocock-skills" &&
        !["domain-modeling", "grilling", "to-tickets"].includes(name),
    );
    expect(unselected.map(([name]) => name).sort()).toEqual([
      "codebase-design",
      "diagnosing-bugs",
      "grill-me",
      "grill-with-docs",
      "handoff",
      "tdd",
      "to-spec",
      "writing-for-agents",
    ]);
    for (const [name, skill] of unselected) {
      expect(manifest.retainedProvenance.skills[name]).toEqual(skill);
    }
    expect(
      manifest.retainedProvenance.repositories["mattpocock-skills"]?.revision,
    ).toBe(oldRevision);
    for (const [name, expected] of Object.entries(official)) {
      const path = `${skillsRoot}/${name}/SKILL.md`;
      const bytes = await readFile(join(item.options.outputDirectory, path));
      expect(bytes).toEqual(
        await readFile(join(item.kitRoot, capsule, name, "SKILL.md")),
      );
      expect(sha256(bytes)).toBe(expected.sha256);
      expect(blob(bytes)).toBe(expected.blob);
      expect(bytes.length).toBe(expected.bytes);
      expect(
        (await stat(join(item.options.outputDirectory, path))).mode & 0o7777,
      ).toBe(0o644);
      expect(
        Object.keys(manifest.assets)
          .filter((p) => p.startsWith(`${skillsRoot}/${name}/`))
          .sort(),
      ).toEqual([path, `${skillsRoot}/${name}/agents/openai.yaml`]);
      expect(
        await readFile(
          join(
            item.options.outputDirectory,
            skillsRoot,
            name,
            "agents/openai.yaml",
          ),
        ),
      ).toEqual(
        await readFile(
          join(
            item.options.canonicalDirectory,
            skillsRoot,
            name,
            "agents/openai.yaml",
          ),
        ),
      );
      expect(manifest.retainedProvenance.skills[name]).toMatchObject({
        treeSha256: expected.tree,
        sourceSubpath: expected.sourceSubpath,
      });
    }
    expect(manifest.assets[`${skillsRoot}/domain-modeling/SKILL.md`]).toBe(
      "7b925d7b1e341a2eeae33ad68a8a8c0ab889a38ddd22a7598e4c240e5a7556a3",
    );
    expect(
      manifest.assets[`${skillsRoot}/domain-modeling/GLOSSARY-FORMAT.md`],
    ).toBe("21dcc40cdec8e151a829b98ab1517c1867bc444e3665134a98c6983411996801");
    expect(
      manifest.assets[`${skillsRoot}/domain-modeling/CONTEXT-FORMAT.md`],
    ).toBeUndefined();
    expect(manifest.assets[presentationPath]).toBe(
      "3a9be511b307210f9ed3a4d5f793a9ed07854652871e05deac07bdab745cf7f5",
    );
    expect(
      report.sourceSelection.sourceOperations.map(
        ({ path, operation, source }) => ({ path, operation, source }),
      ),
    ).toEqual([
      {
        path: `${skillsRoot}/domain-modeling/CONTEXT-FORMAT.md`,
        operation: "delete",
        source: "domain-modeling",
      },
      {
        path: `${skillsRoot}/domain-modeling/GLOSSARY-FORMAT.md`,
        operation: "add",
        source: "domain-modeling",
      },
      {
        path: `${skillsRoot}/domain-modeling/SKILL.md`,
        operation: "replace",
        source: "domain-modeling",
      },
      {
        path: `${skillsRoot}/grilling/SKILL.md`,
        operation: "replace",
        source: "r1-manuals",
      },
      {
        path: `${skillsRoot}/to-tickets/SKILL.md`,
        operation: "replace",
        source: "r1-manuals",
      },
      { path: presentationPath, operation: "replace", source: "omp-overlay" },
    ]);
    for (const operation of report.sourceSelection.sourceOperations) {
      expect(manifest.assets[operation.path] ?? null).toBe(
        operation.targetSha256,
      );
    }
    expect(
      report.decisions.find(({ path }) => path === presentationPath),
    ).toMatchObject({ owner: "kpi", policy: "replace-with-overlay" });
    const license = await readFile(
      join(item.options.outputDirectory, licensePath),
    );
    expect(sha256(license)).toBe(
      "0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5",
    );
    expect(blob(license)).toBe("f1dd2c09108dde1a5f56097cee8461b3ea834499");
    expect(license.toString("utf8")).toContain(
      "Copyright (c) 2026 Matt Pocock",
    );
    expect(ledger.repositories[newRepository].licenseFiles).toEqual([
      { source: "LICENSE", stablePath: "licenses/mattpocock-skills-LICENSE" },
    ]);
    const notices = await readFile(
      join(item.options.outputDirectory, "THIRD_PARTY_NOTICES.md"),
      "utf8",
    );
    expect(notices).toContain(
      `https://github.com/mattpocock/skills.git@${targetRevision}`,
    );
    expect(notices).toContain(
      `https://github.com/mattpocock/skills.git@${oldRevision}`,
    );
    expect(notices).toContain(`### ${newRepository}\n\n- Source:`);
    expect(notices).toContain("- License: MIT");
    expect(notices).toContain(licensePath);
    expect(
      await readFile(
        join(
          item.options.outputDirectory,
          `${stableRoot}/THIRD_PARTY_NOTICES.md`,
        ),
        "utf8",
      ),
    ).toContain(
      "`mattpocock/skills` | MIT | `licenses/mattpocock-skills-LICENSE`",
    );
    // No other assets or task-state payloads are added, removed or changed.
    expect(Object.keys(manifest.assets)).toEqual(
      Object.keys(domain.manifest.assets),
    );
    const changed = Object.keys(manifest.assets)
      .filter((path) => manifest.assets[path] !== domain.manifest.assets[path])
      .sort();
    expect(changed).toEqual(
      [
        "THIRD_PARTY_NOTICES.md",
        ledgerPath,
        `${skillsRoot}/grilling/SKILL.md`,
        `${skillsRoot}/to-tickets/SKILL.md`,
      ].sort(),
    );
    for (const path of [
      "onboard/runtime/templates/skills/sbtd-task/SKILL.md",
      "onboard/runtime/templates/skills/sbtd-task/references/state.md",
    ]) {
      expect(manifest.assets[path]).toBe(old.manifest.assets[path]);
      expect(await readFile(join(item.options.outputDirectory, path))).toEqual(
        await readFile(join(item.root, "old", path)),
      );
    }
    await checkOmpProjection(item.options);
    ledger.sourceSelection.domain.receipt.record.owner = "kpi";
    await writeFile(
      join(item.options.outputDirectory, ledgerPath),
      JSON.stringify(ledger),
    );
    await expect(checkOmpProjection(item.options)).rejects.toMatchObject({
      code: "GENERATED_DRIFT",
    });
  });
});

describe("R1 manuals rejection and branch isolation", () => {
  it.each([
    undefined,
    "domain-modeling",
  ] as const)("keeps the %s branch byte-identical when the unused R1 capsule is invalid", async (sourceSelection) => {
    const item = await fixture();
    const options = {
      packageRoot: item.kitRoot,
      canonicalDirectory: item.options.canonicalDirectory,
      outputDirectory: item.options.outputDirectory,
      ...(sourceSelection === undefined ? {} : { sourceSelection }),
    };
    const before = await generateOmpProjection(options);
    const beforeManifest = await readFile(
      join(options.outputDirectory, "manifest.json"),
    );
    const beforeReport = await readFile(
      join(options.outputDirectory, "projection-report.json"),
    );
    await writeFile(join(item.kitRoot, capsule, "selection.json"), "{invalid");
    await writeFile(
      join(item.kitRoot, capsule, "runtime-profile.json"),
      '{"trusted":true}',
    );
    const after = await generateOmpProjection(options);
    expect(after).toEqual(before);
    expect(
      await readFile(join(options.outputDirectory, "manifest.json")),
    ).toEqual(beforeManifest);
    expect(
      await readFile(join(options.outputDirectory, "projection-report.json")),
    ).toEqual(beforeReport);
    expect(
      after.manifest.retainedProvenance.repositories[newRepository],
    ).toBeUndefined();
    await checkOmpProjection(options);
  });

  const recordCases: {
    name: string;
    mutate: (record: SelectionRecord) => void;
  }[] = [
    {
      name: "supplier pin",
      mutate: (r) => {
        r.supplier.revision = "0".repeat(40);
      },
    },
    {
      name: "origin URI",
      mutate: (r) => {
        r.origin.repository = "https://example.invalid/skills";
      },
    },
    {
      name: "origin pin",
      mutate: (r) => {
        r.target.repositoryRevision = "0".repeat(40);
      },
    },
    {
      name: "old pin",
      mutate: (r) => {
        r.base.repositoryRevision = "0".repeat(40);
      },
    },
    {
      name: "repository alias",
      mutate: (r) => {
        r.target.repositoryKey = "mattpocock-skills-domain-modeling";
      },
    },
    {
      name: "scope widening",
      mutate: (r) => {
        r.scope = "all-skills";
      },
    },
    {
      name: "false ownership",
      mutate: (r) => {
        r.owner = "kpi";
      },
    },
    {
      name: "missing skill",
      mutate: (r) => {
        r.skills.pop();
      },
    },
    {
      name: "duplicate skill",
      mutate: (r) => {
        r.skills = [required(r.skills[0]), required(r.skills[0])];
      },
    },
    {
      name: "extra skill",
      mutate: (r) => {
        r.skills.push(required(r.skills[0]));
      },
    },
    {
      name: "wrong source path",
      mutate: (r) => {
        required(r.skills[0]).sourceSubpath = "skills/engineering/to-tickets";
      },
    },
    {
      name: "before tree",
      mutate: (r) => {
        required(r.skills[0]).beforeTreeSha256 = "0".repeat(64);
      },
    },
    {
      name: "target tree",
      mutate: (r) => {
        required(r.skills[0]).targetTreeSha256 = "0".repeat(64);
      },
    },
    {
      name: "missing kept file",
      mutate: (r) => {
        required(r.skills[0]).files.pop();
      },
    },
    {
      name: "escaped file path",
      mutate: (r) => {
        required(required(r.skills[0]).files[0]).path = "../SKILL.md";
      },
    },
    {
      name: "stale preimage hash",
      mutate: (r) => {
        required(required(r.skills[0]).files[0]).before.sha256 = "0".repeat(64);
      },
    },
    {
      name: "target blob",
      mutate: (r) => {
        required(required(r.skills[0]).files[0]).target.blob = "0".repeat(40);
      },
    },
    {
      name: "target bytes",
      mutate: (r) => {
        required(required(r.skills[0]).files[0]).target.bytes++;
      },
    },
    {
      name: "declared mode",
      mutate: (r) => {
        required(required(r.skills[0]).files[0]).target.mode = "100755";
      },
    },
    {
      name: "MIT identity",
      mutate: (r) => {
        r.license.sha256 = "0".repeat(64);
      },
    },
    {
      name: "domain receipt binding",
      mutate: (r) => {
        r.domainSelection.inputSha256 = "0".repeat(64);
      },
    },
    {
      name: "presentation target injection",
      mutate: (r) => {
        r.presentation.path =
          "onboard/runtime/templates/skills/sbtd-task/SKILL.md";
      },
    },
    {
      name: "presentation hash injection",
      mutate: (r) => {
        r.presentation.target.sha256 = "0".repeat(64);
      },
    },
    {
      name: "runtime template injection",
      mutate: (r) => {
        Object.assign(r, { runtimeTemplate: "payload" });
      },
    },
    {
      name: "legal profile injection",
      mutate: (r) => {
        Object.assign(r, { legalProfile: { trusted: true } });
      },
    },
  ];
  it.each(
    recordCases,
  )("generate and check reject $name without replacing prior output", async ({
    mutate,
  }) => {
    const item = await fixture();
    await changeRecord(item.kitRoot, mutate);
    await rejectsWithoutPartialOutput(item);
  });

  it.each([
    "malformed-json",
    "missing-record",
    "record-mode",
    "record-symlink",
    "missing-skill",
    "skill-hash",
    "skill-mode",
    "skill-symlink",
    "directory-symlink",
    "extra-root",
    "extra-skill",
    "missing-domain",
    "domain-receipt-drift",
    "presentation-drift",
  ])("generate and check reject capsule %s without partial output", async (kind) => {
    const item = await fixture();
    const record = join(item.kitRoot, capsule, "selection.json");
    const skill = join(item.kitRoot, capsule, "grilling/SKILL.md");
    if (kind === "malformed-json") await writeFile(record, "{invalid");
    if (kind === "missing-record") await rm(record);
    if (kind === "record-mode") await chmod(record, 0o755);
    if (kind === "record-symlink") {
      await rm(record);
      await symlink(join(packageRoot, capsule, "selection.json"), record);
    }
    if (kind === "missing-skill") await rm(skill);
    if (kind === "skill-hash") await writeFile(skill, "forged skill\n");
    if (kind === "skill-mode") await chmod(skill, 0o755);
    if (kind === "skill-symlink") {
      await rm(skill);
      await symlink(join(packageRoot, capsule, "grilling/SKILL.md"), skill);
    }
    if (kind === "directory-symlink") {
      await rm(dirname(skill), { recursive: true });
      await symlink(join(packageRoot, capsule, "grilling"), dirname(skill));
    }
    if (kind === "extra-root")
      await writeFile(join(item.kitRoot, capsule, "profile.json"), "{}\n");
    if (kind === "extra-skill")
      await writeFile(join(dirname(skill), "extra.md"), "extra\n");
    if (kind === "missing-domain")
      await rm(join(item.kitRoot, domainCapsule), { recursive: true });
    if (kind === "domain-receipt-drift") {
      const domainRecord = join(item.kitRoot, domainCapsule, "selection.json");
      await writeFile(
        domainRecord,
        `${await readFile(domainRecord, "utf8")}\n`,
      );
    }
    if (kind === "presentation-drift") {
      await writeFile(
        join(item.kitRoot, "omp-overlays", presentationPath),
        "forged presentation\n",
      );
    }
    await rejectsWithoutPartialOutput(item);
  });

  it.each([
    "grilling",
    "to-tickets",
  ])("rejects forged %s per-file and whole-tree hashes against independent source pins", async (name) => {
    const item = await fixture();
    const filename = join(item.kitRoot, capsule, name, "SKILL.md");
    const bytes = Buffer.concat([
      await readFile(filename),
      Buffer.from("\nforged\n"),
    ]);
    await writeFile(filename, bytes);
    await changeRecord(item.kitRoot, (record) => {
      const skill = required(
        record.skills.find((entry) => entry.name === name),
      );
      const file = required(skill.files[0]);
      file.target = {
        bytes: bytes.length,
        sha256: sha256(bytes),
        blob: blob(bytes),
        mode: "100644",
      };
    });
    await rejectsWithoutPartialOutput(item);
    // A forged target tree cannot upgrade the record into a new authorized source.
    await changeRecord(item.kitRoot, (record) => {
      required(
        record.skills.find((entry) => entry.name === name),
      ).targetTreeSha256 = "f".repeat(64);
    });
    await expect(generateOmpProjection(item.options)).rejects.toMatchObject({
      code: "PROJECTION_POLICY_INVALID",
    });
    expect(
      await readFile(join(item.options.outputDirectory, "keep.txt"), "utf8"),
    ).toBe("existing-output\n");
  });

  it.each([
    `${skillsRoot}/grilling/SKILL.md`,
    `${skillsRoot}/grilling/agents/openai.yaml`,
    `${skillsRoot}/to-tickets/agents/openai.yaml`,
    licensePath,
  ])("rejects canonical mode drift at %s before writing output", async (path) => {
    const item = await fixture();
    const canonicalDirectory = join(item.kitRoot, "canonical");
    await cp(item.options.canonicalDirectory, canonicalDirectory, {
      recursive: true,
    });
    await chmod(join(canonicalDirectory, path), 0o755);
    await rejectsWithoutPartialOutput({
      ...item,
      options: { ...item.options, canonicalDirectory },
    });
  });

  it("rejects a missing canonical manual or MIT input without creating output", async () => {
    for (const path of [
      `${skillsRoot}/to-tickets/agents/openai.yaml`,
      licensePath,
    ]) {
      const item = await fixture();
      const canonicalDirectory = join(item.kitRoot, "canonical");
      await cp(item.options.canonicalDirectory, canonicalDirectory, {
        recursive: true,
      });
      await rm(join(canonicalDirectory, path));
      await expect(
        generateOmpProjection({ ...item.options, canonicalDirectory }),
      ).rejects.toThrow();
      expect((await readdir(item.root)).sort()).toEqual(["package"]);
    }
  });

  it("rejects arbitrary API selection strings without reading an untrusted profile", async () => {
    const item = await fixture();
    await expect(
      generateOmpProjection({
        ...item.options,
        sourceSelection: "runtime-profile" as "r1-manuals",
      }),
    ).rejects.toMatchObject({ code: "PROJECTION_POLICY_INVALID" });
    expect((await readdir(item.root)).sort()).toEqual(["package"]);
  });
});

function required<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("fixture member missing");
  return value;
}
