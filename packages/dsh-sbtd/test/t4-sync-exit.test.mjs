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
  const mismatch = spawnSync("bash", [script, pkgRoot], { encoding: "utf8" });
  assert.notEqual(mismatch.status, 0);
  assert.match(mismatch.stderr, /SHA mismatch/);
});
