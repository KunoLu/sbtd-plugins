import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  cpSync,
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

function initSourceRepo(label, extraRel, extraSrc) {
  const root = mkdtempSync(join(tmpdir(), `dsh-sbtd-${label}-`));
  git(root, ["init", "-q"]);
  layoutSkills(root, extraRel, extraSrc);
  git(root, ["add", "."]);
  git(root, ["commit", "-q", "-m", label]);
  const sha = git(root, ["rev-parse", "HEAD"]);
  return { root, sha };
}

function isolatedPkg(pin, corruptRel) {
  const root = mkdtempSync(join(tmpdir(), "dsh-sbtd-pkg-"));
  mkdirSync(join(root, "scripts"), { recursive: true });
  mkdirSync(join(root, "manuals"), { recursive: true });
  writeFileSync(join(root, "manuals", ".keep"), "\n");
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
