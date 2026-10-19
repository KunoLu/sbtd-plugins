#!/usr/bin/env node
// omp-sbtd 0.2.0-rc.1 row A CLEAN gate comparison.
//
// Compares two packed tarballs of @kunolu/omp-sbtd:
//   --baseline  <path to tarball built at 4f7388c>
//   --candidate <path to tarball built on the row-A branch>
//
// Asserts:
//   1. File lists are identical.
//   2. Per-file sha256 identical for every file except package.json and
//      SBOM.spdx.json.
//   3. package.json diff contains exactly the three allowed edits:
//      (a) devDependency "@kunolu/sbtd-workflow-kit": "workspace:*" removed;
//      (b) scripts.build differs only by replacing the
//          `pnpm --filter @kunolu/sbtd-workflow-kit check-generated`
//          invocation with the in-package entry;
//      (c) devDependency "yaml": "2.8.2" added.
//   4. SBOM.spdx.json diff contains exactly the kit package node removal and
//      the single relationship whose relatedSpdxElement points at it, plus
//      (PRD R6) the documentNamespace change to
//      https://kpi.local/spdx/<new sourceTreeSha256>; every other entry is
//      deep-equal. The new digest is recomputed independently here with the
//      R6 formula { plugin: { name, version }, kit: { generatedSha256 },
//      files } and must equal the candidate documentNamespace suffix.
//   5. Embedded kit/, skills/, and kit/manifest.json hashes are identical
//      (covered by (2); reported separately for the gate record).
// The whole-tarball sha256 is expected to differ and is reported, not asserted.

import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { createHash } from "node:crypto";

function arg(name) {
  const index = process.argv.indexOf(`--${name}`);
  if (index === -1 || process.argv[index + 1] === undefined) {
    throw new Error(`missing --${name} <path>`);
  }
  return process.argv[index + 1];
}

const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

function extract(tarball, label) {
  const root = mkdtempSync(join(tmpdir(), `clean-gate-${label}-`));
  execFileSync("tar", ["-xzf", tarball, "-C", root]);
  return join(root, "package");
}

function listFiles(root, base = root) {
  const out = [];
  for (const entry of readdirSync(root)) {
    const path = join(root, entry);
    if (statSync(path).isDirectory()) out.push(...listFiles(path, base));
    else out.push(relative(base, path).split("\\").join("/"));
  }
  return out.sort();
}

function hashTree(root) {
  const map = new Map();
  for (const path of listFiles(root)) {
    map.set(path, sha256(readFileSync(join(root, path))));
  }
  return map;
}

function deepEqual(left, right) {
  if (Object.is(left, right)) return true;
  if (
    typeof left !== "object" ||
    typeof right !== "object" ||
    left === null ||
    right === null
  )
    return false;
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every(
    (key) => key in right && deepEqual(left[key], right[key]),
  );
}

const failures = [];
const notes = [];
const check = (ok, message) => {
  if (ok) notes.push(`PASS ${message}`);
  else failures.push(`FAIL ${message}`);
};

const baselineTarball = arg("baseline");
const candidateTarball = arg("candidate");
const baselineRoot = extract(baselineTarball, "baseline");
const candidateRoot = extract(candidateTarball, "candidate");

try {
  // 1. File list identity (npm pack --dry-run inventory).
  const baselineFiles = listFiles(baselineRoot);
  const candidateFiles = listFiles(candidateRoot);
  check(
    deepEqual(baselineFiles, candidateFiles),
    `pack file list identical (${baselineFiles.length} files)`,
  );

  // 2. Per-file sha256, allowing exactly two differing files.
  const baselineHash = hashTree(baselineRoot);
  const candidateHash = hashTree(candidateRoot);
  const allowed = new Set(["package.json", "SBOM.spdx.json"]);
  const unexpected = [];
  for (const path of candidateFiles) {
    if (baselineHash.get(path) === candidateHash.get(path)) continue;
    if (!allowed.has(path)) unexpected.push(path);
  }
  check(
    unexpected.length === 0,
    unexpected.length === 0
      ? "per-file sha256 identical except package.json and SBOM.spdx.json"
      : `unexpected differing files: ${unexpected.join(", ")}`,
  );
  check(
    baselineHash.get("kit/manifest.json") ===
      candidateHash.get("kit/manifest.json"),
    "embedded kit/manifest.json hash identical",
  );
  const kitFiles = candidateFiles.filter((path) => path.startsWith("kit/"));
  const skillFiles = candidateFiles.filter((path) =>
    path.startsWith("skills/"),
  );
  check(
    kitFiles.every(
      (path) => baselineHash.get(path) === candidateHash.get(path),
    ),
    `embedded kit/ hashes identical (${kitFiles.length} files)`,
  );
  check(
    skillFiles.every(
      (path) => baselineHash.get(path) === candidateHash.get(path),
    ),
    `embedded skills/ hashes identical (${skillFiles.length} files)`,
  );

  // 3. package.json: exactly the three allowed edits.
  const baselinePkg = JSON.parse(
    readFileSync(join(baselineRoot, "package.json"), "utf8"),
  );
  const candidatePkg = JSON.parse(
    readFileSync(join(candidateRoot, "package.json"), "utf8"),
  );
  const expectedDevDeps = { ...baselinePkg.devDependencies };
  delete expectedDevDeps["@kunolu/sbtd-workflow-kit"];
  expectedDevDeps.yaml = "2.8.2";
  check(
    deepEqual(candidatePkg.devDependencies, expectedDevDeps),
    'package.json devDeps: kit workspace link removed, yaml "2.8.2" added, nothing else',
  );
  const expectedBuild = baselinePkg.scripts.build.replace(
    "pnpm --filter @kunolu/sbtd-workflow-kit check-generated",
    "node scripts/kit-check-generated.mjs",
  );
  check(
    baselinePkg.scripts.build.includes(
      "pnpm --filter @kunolu/sbtd-workflow-kit check-generated",
    ) && candidatePkg.scripts.build === expectedBuild,
    "package.json scripts.build: only the kit check-generated invocation replaced",
  );
  const restBaseline = { ...baselinePkg };
  const restCandidate = { ...candidatePkg };
  delete restBaseline.devDependencies;
  delete restCandidate.devDependencies;
  restBaseline.scripts = { ...restBaseline.scripts, build: "<ignored>" };
  restCandidate.scripts = { ...restCandidate.scripts, build: "<ignored>" };
  check(
    deepEqual(restCandidate, restBaseline),
    "package.json: every other field byte-identical (peer/devDep omp pin, dependencies, files, version)",
  );

  // 4. SBOM: only the kit package node and its relationship removed, plus the
  //    R6 documentNamespace change.
  const baselineSbom = JSON.parse(
    readFileSync(join(baselineRoot, "SBOM.spdx.json"), "utf8"),
  );
  const candidateSbom = JSON.parse(
    readFileSync(join(candidateRoot, "SBOM.spdx.json"), "utf8"),
  );
  const kitSpdxId = "SPDXRef-Package-kunolu-sbtd-workflow-kit";
  const expectedSbom = structuredClone(baselineSbom);
  expectedSbom.packages = expectedSbom.packages.filter(
    (pkg) => pkg.SPDXID !== kitSpdxId,
  );
  expectedSbom.relationships = expectedSbom.relationships.filter(
    (relationship) => relationship.relatedSpdxElement !== kitSpdxId,
  );
  check(
    baselineSbom.packages.some((pkg) => pkg.SPDXID === kitSpdxId) &&
      baselineSbom.relationships.some(
        (relationship) => relationship.relatedSpdxElement === kitSpdxId,
      ),
    "baseline SBOM contains the kit package node and relationship (sanity)",
  );
  // PRD R6: documentNamespace is allowed (and required) to change to
  // https://kpi.local/spdx/<new sourceTreeSha256>; everything else identical.
  expectedSbom.documentNamespace = candidateSbom.documentNamespace;
  check(
    deepEqual(candidateSbom, expectedSbom),
    "SBOM.spdx.json: only the kit package node, its relationship, and the R6 documentNamespace changed; all other entries identical",
  );
  const namespaceMatch = candidateSbom.documentNamespace.match(
    /^https:\/\/kpi\.local\/spdx\/([0-9a-f]{64})$/,
  );
  check(
    namespaceMatch !== null &&
      candidateSbom.documentNamespace !== baselineSbom.documentNamespace,
    `SBOM documentNamespace changed to kpi.local/spdx/<new digest> (baseline ${baselineSbom.documentNamespace})`,
  );
  // Independent recompute of the R6 digest from the candidate tree:
  // sha256(stableJson({ plugin: {name, version}, kit: {generatedSha256},
  // files })) where stableJson is JSON.stringify with recursively sorted
  // keys, 2-space indent, trailing newline; files is the declared-path
  // inventory { path, sha256, license: "Apache-2.0" } sorted by path.
  const sortedJson = (value) => {
    if (Array.isArray(value)) return value.map(sortedJson);
    if (value !== null && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([key, nested]) => [key, sortedJson(nested)]),
      );
    return value;
  };
  const declaredPaths = [
    "dist",
    "kit",
    "plugin.json",
    "skills",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "validation/p0/compatibility.v2.json",
  ];
  const inventory = [];
  for (const declaredPath of declaredPaths) {
    const full = join(candidateRoot, declaredPath);
    if (statSync(full).isDirectory()) {
      for (const path of listFiles(full)) {
        inventory.push({
          path: `${declaredPath}/${path}`,
          sha256: sha256(readFileSync(join(full, path))),
          license: "Apache-2.0",
        });
      }
    } else {
      inventory.push({
        path: declaredPath,
        sha256: sha256(readFileSync(full)),
        license: "Apache-2.0",
      });
    }
  }
  inventory.sort((left, right) => left.path.localeCompare(right.path));
  const candidateManifest = JSON.parse(
    readFileSync(join(candidateRoot, "kit/manifest.json"), "utf8"),
  );
  const recomputed = sha256(
    `${JSON.stringify(
      sortedJson({
        plugin: { name: candidatePkg.name, version: candidatePkg.version },
        kit: {
          generatedSha256: candidateManifest.projection.generatedSha256,
        },
        files: inventory,
      }),
      null,
      2,
    )}\n`,
  );
  notes.push(`INFO recomputed R6 sourceTreeSha256=${recomputed}`);
  check(
    namespaceMatch !== null && recomputed === namespaceMatch[1],
    "candidate documentNamespace digest equals independent R6 recompute",
  );

  // 5. Tarball sha256: expected to differ; reported only.
  const baselineTarballSha = sha256(readFileSync(baselineTarball));
  const candidateTarballSha = sha256(readFileSync(candidateTarball));
  notes.push(
    `INFO tarball sha256 baseline=${baselineTarballSha} candidate=${candidateTarballSha} (expected to differ: ${
      baselineTarballSha === candidateTarballSha ? "NO — investigate" : "yes"
    })`,
  );
} finally {
  rmSync(baselineRoot, { force: true, recursive: true });
  rmSync(candidateRoot, { force: true, recursive: true });
}

for (const note of notes) console.log(note);
for (const failure of failures) console.error(failure);
if (failures.length > 0) {
  console.error(`CLEAN GATE: FAIL (${failures.length} failure(s))`);
  process.exit(1);
}
console.log("CLEAN GATE: PASS");
