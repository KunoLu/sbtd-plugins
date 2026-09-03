import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const manuals = join(pkgRoot, "manuals");
const PIN = "f8aa0d7225a26c5e00b81d2f1b05121108e63630";
const script = join(pkgRoot, "scripts", "sync-manuals.sh");
const WHITELIST = readFileSync(script, "utf8")
  .match(/WHITELIST=\(([\s\S]*?)\)/)[1]
  .split("\n")
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith("#"));
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
    const rest = file.sourcePath.match(SOURCE_PATH_RE)[2];
    assert.ok(
      rest === "SKILL.md" || rest.startsWith("references/"),
      `MANIFEST must only list SKILL.md or references/: ${file.sourcePath}`,
    );
    assert.equal(statSync(dest).isFile(), true);
    const digest = createHash("sha256").update(readFileSync(dest)).digest("hex");
    assert.equal(digest, file.sha256);
    hashedDest.add(dest);
  }
  for (const id of dirs) {
    const skillDir = join(manuals, id);
    assert.equal(hashedDest.has(join(skillDir, "SKILL.md")), true);
    const rootNames = readdirSync(skillDir).sort();
    const allowed = rootNames.includes("references")
      ? ["SKILL.md", "references"]
      : ["SKILL.md"];
    assert.deepEqual(rootNames, allowed, `${id} root must be SKILL.md and optional references/`);
    if (allowed.includes("references")) {
      assert.equal(statSync(join(skillDir, "references")).isDirectory(), true);
    }
  }
  const skip = new Set(["node_modules", "dist"]);
  const stack = [pkgRoot];
  while (stack.length) {
    const dir = stack.pop();
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (skip.has(entry.name)) continue;
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(path);
        continue;
      }
      assert.notEqual(entry.name, "install.sh");
      assert.notEqual(entry.name, "onboard.py");
    }
  }
  const readme = readFileSync(join(pkgRoot, "README.md"), "utf8");
  assert.match(readme, /不要手改/);
  assert.match(readme, /f8aa0d7225a26c5e00b81d2f1b05121108e63630/);
  assert.match(readme, /SKILL\.md/);
  assert.match(readme, /references\//);
  assert.doesNotMatch(readme, /skill-root markdown/);
  assert.deepEqual(readdirSync(join(pkgRoot, "src", "tools")).sort(), ["plan.ts"]);
  const trellis = readFileSync(join(manuals, "trellis-workflow", "SKILL.md"));
  assert.notEqual(trellis.length, 0);
  assert.notEqual(trellis[trellis.length - 1], 0x0a, "trellis-workflow SKILL.md must match pin blob (no trailing newline)");
  const book = readFileSync(join(manuals, "book-ddd-distilled-modeling", "SKILL.md"));
  assert.equal(book[book.length - 1], 0x0a);
});
