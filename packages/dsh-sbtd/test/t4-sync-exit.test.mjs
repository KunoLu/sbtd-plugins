import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const script = join(pkgRoot, "scripts", "sync-manuals.sh");
const fixtures = join(pkgRoot, "test", "fixtures", "sync-manuals");
const PIN = "f8aa0d7225a26c5e00b81d2f1b05121108e63630";
const scriptBody = readFileSync(script, "utf8");
const WHITELIST = scriptBody
  .match(/WHITELIST=\(([\s\S]*?)\)/)[1]
  .split("\n")
  .map((line) => line.trim())
  .filter((line) => line && !line.startsWith("#"));

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

function git(cwd, args) {
  const result = spawnSync("git", ["-c", "user.name=t4", "-c", "user.email=t4@test", ...args], {
    cwd,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout.trim();
}

function layoutSkills(sourceRoot, extraRel, extraSrc) {
  const stub = join(fixtures, "SKILL.md");
  for (const id of WHITELIST) {
    const dir =
      id.startsWith("book-") || id === "trellis-workflow"
        ? join(sourceRoot, "sbtd-workflow-onboard", "templates", "skills", id)
        : join(
            sourceRoot,
            "sbtd-workflow-onboard",
            "assets",
            "external-skills",
            "stable",
            "skills",
            id,
          );
    mkdirSync(dir, { recursive: true });
    cpSync(stub, join(dir, "SKILL.md"));
  }
  if (extraRel) {
    const dest = join(sourceRoot, extraRel);
    mkdirSync(dirname(dest), { recursive: true });
    cpSync(extraSrc, dest);
  }
}

function initSourceRepo(label, extraRel, extraSrc, tweak) {
  const root = mkdtempSync(join(tmpdir(), `dsh-sbtd-${label}-`));
  try {
    git(root, ["init", "-q"]);
    layoutSkills(root, extraRel, extraSrc);
    if (tweak) tweak(root);
    git(root, ["add", "."]);
    git(root, ["commit", "-q", "-m", label]);
    const sha = git(root, ["rev-parse", "HEAD"]);
    return { root, sha };
  } catch (err) {
    rmSync(root, { recursive: true, force: true });
    throw err;
  }
}

function isolatedPkg(pin, corruptRel, { destAbsent = false } = {}) {
  const root = mkdtempSync(join(tmpdir(), "dsh-sbtd-pkg-"));
  try {
    mkdirSync(join(root, "scripts"), { recursive: true });
    if (!destAbsent) {
      mkdirSync(join(root, "manuals"), { recursive: true });
      writeFileSync(join(root, "manuals", ".keep"), "\n");
    }
    let body = readFileSync(script, "utf8").replace(`PINNED_REVISION="${PIN}"`, `PINNED_REVISION="${pin}"`);
    if (corruptRel) {
      body = body.replace(
        "rm -f \"${DEST}/.sync-list\"\nwrite_and_verify_manifest",
        `rm -f "\${DEST}/.sync-list"\nprintf x >> "\${DEST}/${corruptRel}"\nwrite_and_verify_manifest`,
      );
    }
    const isolatedScript = join(root, "scripts", "sync-manuals.sh");
    writeFileSync(isolatedScript, body, { mode: 0o755 });
    return { root, script: isolatedScript };
  } catch (err) {
    rmSync(root, { recursive: true, force: true });
    throw err;
  }
}

test("sync-manuals exits non-zero on copy-fail from in-repo fixture", () => {
  const source = initSourceRepo(
    "copy-fail",
    "sbtd-workflow-onboard/assets/external-skills/stable/skills/grill-me/references/install.sh",
    join(fixtures, "blocked-install.sh"),
  );
  const pkg = isolatedPkg(source.sha);
  try {
    const result = spawnSync("bash", [pkg.script, source.root], { encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /copy fail:/);
    assert.equal(source.root.includes("/tmp/640-skills"), false);
  } finally {
    rmSync(source.root, { recursive: true, force: true });
    rmSync(pkg.root, { recursive: true, force: true });
  }
});

test("sync-manuals exits non-zero on checksum-fail from in-repo fixture", () => {
  const source = initSourceRepo("checksum-fail");
  const pkg = isolatedPkg(source.sha, "grill-me/SKILL.md");
  try {
    const result = spawnSync("bash", [pkg.script, source.root], { encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /checksum fail:/);
    assert.equal(source.root.includes("/tmp/640-skills"), false);
  } finally {
    rmSync(source.root, { recursive: true, force: true });
    rmSync(pkg.root, { recursive: true, force: true });
  }
});

test("sync-manuals copies fixture blobs with and without trailing newline", () => {
  const nonewline = join(fixtures, "SKILL.nonewline.md");
  const source = initSourceRepo("ok-bytes", undefined, undefined, (root) => {
    const trellis = join(
      root,
      "sbtd-workflow-onboard",
      "templates",
      "skills",
      "trellis-workflow",
      "SKILL.md",
    );
    cpSync(nonewline, trellis);
  });
  const pkg = isolatedPkg(source.sha);
  try {
    const result = spawnSync("bash", [pkg.script, source.root], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    const destTrellis = readFileSync(join(pkg.root, "manuals", "trellis-workflow", "SKILL.md"));
    const destBook = readFileSync(join(pkg.root, "manuals", "book-ddd-distilled-modeling", "SKILL.md"));
    assert.notEqual(destTrellis[destTrellis.length - 1], 0x0a);
    assert.equal(destBook[destBook.length - 1], 0x0a);
    const blob = spawnSync(
      "git",
      [
        "-C",
        source.root,
        "cat-file",
        "blob",
        `${source.sha}:sbtd-workflow-onboard/templates/skills/trellis-workflow/SKILL.md`,
      ],
    );
    assert.equal(blob.status, 0);
    assert.deepEqual(destTrellis, blob.stdout);
    assert.equal(source.root.includes("/tmp/640-skills"), false);
  } finally {
    rmSync(source.root, { recursive: true, force: true });
    rmSync(pkg.root, { recursive: true, force: true });
  }
});

test("sync-manuals promotes when manuals dest is absent", () => {
  const source = initSourceRepo("dest-absent");
  const pkg = isolatedPkg(source.sha, undefined, { destAbsent: true });
  try {
    const result = spawnSync("bash", [pkg.script, source.root], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(existsSync(join(pkg.root, "manuals", "MANIFEST.json")), true);
    assert.equal(existsSync(join(pkg.root, "manuals", "grill-me", "SKILL.md")), true);
  } finally {
    rmSync(source.root, { recursive: true, force: true });
    rmSync(pkg.root, { recursive: true, force: true });
  }
});
