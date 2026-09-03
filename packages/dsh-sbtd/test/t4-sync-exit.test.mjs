import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const script = join(pkgRoot, "scripts", "sync-manuals.sh");

test("sync-manuals exits non-zero on missing source or SHA mismatch", () => {
  const missing = spawnSync("bash", [script, "/no/such/640-skills"], { encoding: "utf8" });
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /missing source/);
  const repoRoot = join(pkgRoot, "..", "..");
  const mismatch = spawnSync("bash", [script, repoRoot], { encoding: "utf8" });
  assert.notEqual(mismatch.status, 0);
  assert.match(mismatch.stderr, /SHA mismatch: got /);
  assert.match(mismatch.stderr, /expected f8aa0d7225a26c5e00b81d2f1b05121108e63630/);
});

test("sync-manuals succeeds twice against pinned SOURCE", () => {
  const source = "/tmp/640-skills";
  const first = spawnSync("bash", [script, source], { encoding: "utf8" });
  assert.equal(first.status, 0, first.stderr);
  const second = spawnSync("bash", [script, source], { encoding: "utf8" });
  assert.equal(second.status, 0, second.stderr);
});
