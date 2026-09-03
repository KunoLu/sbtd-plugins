import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
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
const SOURCE_PATH_RE =
  /(?:templates|assets\/external-skills\/stable)\/skills\/([^/]+)\/(.+)$/;

function destFromSourcePath(sourcePath) {
  const match = sourcePath.match(SOURCE_PATH_RE);
  assert.ok(match, `sourcePath must be under a search root: ${sourcePath}`);
  return join(manuals, match[1], match[2]);
}

test("manuals whitelist and MANIFEST checksums", () => {
  const manifest = JSON.parse(readFileSync(join(manuals, "MANIFEST.json"), "utf8"));
  assert.equal(manifest.sourceRevision, PIN);
  assert.equal(manifest.source, "KunoLu/640-skills");
  assert.equal(manifest.version, "1.0.13");
  const dirs = readdirSync(manuals, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  assert.deepEqual(dirs, [...WHITELIST].sort());
  const hashedDest = new Set();
  for (const file of manifest.files) {
    assert.equal(file.sourceRevision, PIN);
    const dest = destFromSourcePath(file.sourcePath);
    assert.equal(statSync(dest).isFile(), true);
    const digest = createHash("sha256").update(readFileSync(dest)).digest("hex");
    assert.equal(digest, file.sha256);
    hashedDest.add(dest);
  }
  for (const id of dirs) {
    assert.equal(hashedDest.has(join(manuals, id, "SKILL.md")), true);
    assert.equal(existsSync(join(manuals, id, "agents")), false);
  }
  assert.equal(existsSync(join(manuals, "domain-modeling", "CONTEXT-FORMAT.md")), true);
  assert.equal(existsSync(join(manuals, "domain-modeling", "ADR-FORMAT.md")), true);
  assert.equal(existsSync(join(manuals, "install.sh")), false);
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /不要手改/);
  assert.match(readme, /f8aa0d7225a26c5e00b81d2f1b05121108e63630/);
  assert.match(readme, /skill-root markdown/);
  assert.deepEqual(readdirSync(join(pkgRoot, "src", "tools")).sort(), ["plan.ts"]);
});
