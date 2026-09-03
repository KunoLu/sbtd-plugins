#!/usr/bin/env bash
# Sync whitelist SKILL.md (+ references/) from KunoLu/640-skills into manuals/.
# Usage: sync-manuals.sh [SOURCE]
set -euo pipefail

PINNED_REVISION="f8aa0d7225a26c5e00b81d2f1b05121108e63630"
PINNED_VERSION="1.0.13"
SOURCE_REPO="https://github.com/KunoLu/640-skills.git"
SOURCE_ID="KunoLu/640-skills"

WHITELIST=(
  book-ddd-distilled-modeling
  book-ddia-data-design
  book-legacy-change-safety
  book-refactoring-pass
  book-release-readiness
  grill-with-docs
  grill-me
  grilling
  domain-modeling
  to-spec
  to-tickets
  trellis-workflow
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEST="${PKG_ROOT}/manuals"
CLONE_DIR=""

die() {
  echo "sync-manuals: $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${CLONE_DIR}" && -d "${CLONE_DIR}" ]]; then
    rm -rf "${CLONE_DIR}"
  fi
}
trap cleanup EXIT

resolve_source() {
  local given="${1:-}"
  if [[ -z "${given}" ]]; then
    CLONE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dsh-sbtd-640-skills.XXXXXX")"
    git clone --filter=blob:none --no-checkout "${SOURCE_REPO}" "${CLONE_DIR}" >/dev/null
    git -C "${CLONE_DIR}" fetch --depth=1 origin "${PINNED_REVISION}" >/dev/null
    git -C "${CLONE_DIR}" checkout --detach "${PINNED_REVISION}" >/dev/null
    SOURCE="${CLONE_DIR}"
  else
    SOURCE="${given}"
  fi

  [[ -d "${SOURCE}" ]] || die "missing source: ${SOURCE}"

  if [[ ! -d "${SOURCE}/.git" ]]; then
    die "SHA mismatch: source is not a git checkout (expected ${PINNED_REVISION})"
  fi

  local actual
  actual="$(git -C "${SOURCE}" rev-parse HEAD 2>/dev/null || true)"
  [[ "${actual}" == "${PINNED_REVISION}" ]] || die "SHA mismatch: got ${actual:-unknown}, expected ${PINNED_REVISION}"
}

find_skill_dir() {
  local id="$1"
  local templates="${SOURCE}/sbtd-workflow-onboard/templates/skills/${id}"
  local external="${SOURCE}/sbtd-workflow-onboard/assets/external-skills/stable/skills/${id}"
  local found=""

  if [[ -f "${templates}/SKILL.md" ]]; then
    found="${templates}"
  fi
  if [[ -f "${external}/SKILL.md" ]]; then
    if [[ -n "${found}" ]]; then
      die "duplicate skill source for ${id}"
    fi
    found="${external}"
  fi
  [[ -n "${found}" ]] || die "missing source skill: ${id}"
  printf '%s\n' "${found}"
}

copy_skill() {
  local id="$1"
  local src="$2"
  local dest_dir="${DEST}/${id}"
  mkdir -p "${dest_dir}"
  cp -f "${src}/SKILL.md" "${dest_dir}/SKILL.md" || die "copy fail: ${id}/SKILL.md"
  if [[ -d "${src}/references" ]]; then
    rm -rf "${dest_dir}/references"
    cp -R "${src}/references" "${dest_dir}/references" || die "copy fail: ${id}/references"
  fi
}

write_and_verify_manifest() {
  python3 - "$DEST" "$PINNED_REVISION" "$PINNED_VERSION" "$SOURCE_ID" <<'PY'
import hashlib, json, os, sys, pathlib

dest, revision, version, source_id = sys.argv[1:5]
files = []
for dirpath, dirnames, filenames in os.walk(dest):
    dirnames.sort()
    for name in sorted(filenames):
        if name == "MANIFEST.json":
            continue
        path = os.path.join(dirpath, name)
        if os.path.islink(path) or not os.path.isfile(path):
            raise SystemExit(f"sync-manuals: checksum fail: non-regular file {path}")
        rel = os.path.relpath(path, dest).replace(os.sep, "/")
        digest = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        files.append({"path": rel, "sha256": digest})

files.sort(key=lambda item: item["path"])
if not files:
    raise SystemExit("sync-manuals: checksum fail: no files copied")

manifest = {
    "source": source_id,
    "version": version,
    "revision": revision,
    "files": files,
}
manifest_path = os.path.join(dest, "MANIFEST.json")
with open(manifest_path, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

on_disk = {}
for dirpath, dirnames, filenames in os.walk(dest):
    dirnames.sort()
    for name in sorted(filenames):
        if name == "MANIFEST.json":
            continue
        path = os.path.join(dirpath, name)
        rel = os.path.relpath(path, dest).replace(os.sep, "/")
        on_disk[rel] = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

expected = {item["path"]: item["sha256"] for item in files}
if on_disk != expected:
    raise SystemExit("sync-manuals: checksum fail: dest does not match MANIFEST")
PY
}

resolve_source "${1:-}"
[[ -d "${DEST}" ]] || mkdir -p "${DEST}"

find "${DEST}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

for id in "${WHITELIST[@]}"; do
  src_dir="$(find_skill_dir "${id}")"
  copy_skill "${id}" "${src_dir}"
done

if find "${DEST}" \( -name 'install.sh' -o -name 'onboard.py' \) | grep -q .; then
  die "copy fail: installer artifacts must not be copied"
fi

write_and_verify_manifest
echo "sync-manuals: wrote ${DEST}/MANIFEST.json revision ${PINNED_REVISION}"
