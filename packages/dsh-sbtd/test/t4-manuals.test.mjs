import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const manuals = join(pkgRoot, "manuals");
const PIN = "f8aa0d7225a26c5e00b81d2f1b05121108e63630";
const WHITELIST = [
  "book-ddd-distilled-modeling",
  "book-ddia-data-design",
  "book-legacy-change-safety",
  "book-refactoring-pass",
  "book-release-readiness",
  "grill-with-docs",
  "grill-me",
  "grilling",
  "domain-modeling",
  "to-spec",
  "to-tickets",
  "trellis-workflow",
];

test("manuals whitelist and MANIFEST checksums", () => {
  const manifest = JSON.parse(readFileSync(join(manuals, "MANIFEST.json"), "utf8"));
  assert.equal(manifest.revision, PIN);
  assert.equal(manifest.source, "KunoLu/640-skills");
  assert.equal(manifest.version, "1.0.13");
  const dirs = readdirSync(manuals, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
  assert.deepEqual(dirs, [...WHITELIST].sort());
  const onDisk = {};
  for (const id of dirs) {
    const body = readFileSync(join(manuals, id, "SKILL.md"));
    onDisk[`${id}/SKILL.md`] = createHash("sha256").update(body).digest("hex");
  }
  const expected = Object.fromEntries(manifest.files.map((f) => [f.path, f.sha256]));
  assert.deepEqual(onDisk, expected);
  assert.equal(existsSync(join(manuals, "install.sh")), false);
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /不要手改/);
  assert.match(readme, /f8aa0d7225a26c5e00b81d2f1b05121108e63630/);
  assert.deepEqual(readdirSync(join(pkgRoot, "src", "tools")).sort(), ["plan.ts"]);
});
