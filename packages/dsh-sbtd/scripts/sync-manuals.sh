#!/usr/bin/env bash
# Sync whitelist SKILL.md and that skill's references/ from KunoLu/640-skills into manuals/.
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
ORIG_DEST="${PKG_ROOT}/manuals"
DEST=""
CLONE_DIR=""
STAGE=""
DEST="${ORIG_DEST}"
INDEX=""

die() {
  echo "sync-manuals: $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${CLONE_DIR}" && -d "${CLONE_DIR}" ]]; then
    rm -rf "${CLONE_DIR}"
  fi
  if [[ -n "${STAGE}" && -d "${STAGE}" ]]; then
    rm -rf "${STAGE}"
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

  local inside
  inside="$(git -C "${SOURCE}" rev-parse --is-inside-work-tree 2>/dev/null || true)"
  [[ "${inside}" == "true" ]] || die "SHA mismatch: source is not a git work tree (expected ${PINNED_REVISION})"

  SOURCE="$(git -C "${SOURCE}" rev-parse --show-toplevel)"

  local actual
  actual="$(git -C "${SOURCE}" rev-parse HEAD 2>/dev/null || true)"
  [[ "${actual}" == "${PINNED_REVISION}" ]] || die "SHA mismatch: got ${actual:-unknown}, expected ${PINNED_REVISION}"
}

find_skill_prefix() {
  local id="$1"
  local templates="sbtd-workflow-onboard/templates/skills/${id}"
  local external="sbtd-workflow-onboard/assets/external-skills/stable/skills/${id}"
  local found=""

  if git -C "${SOURCE}" cat-file -e "${PINNED_REVISION}:${templates}/SKILL.md" 2>/dev/null; then
    found="${templates}"
  fi
  if git -C "${SOURCE}" cat-file -e "${PINNED_REVISION}:${external}/SKILL.md" 2>/dev/null; then
    if [[ -n "${found}" ]]; then
      die "duplicate skill source for ${id}"
    fi
    found="${external}"
  fi
  [[ -n "${found}" ]] || die "missing source skill: ${id}"
  printf '%s\n' "${found}"
}

should_copy() {
  local rel="$1"
  [[ "${rel}" == "SKILL.md" || "${rel}" == references/* ]]
}

copy_skill() {
  local id="$1"
  local prefix="$2"
  local dest_dir="${DEST}/${id}"
  mkdir -p "${dest_dir}"
  local copied=0 path rel dest_path list
  list="${DEST}/.sync-list"
  git -C "${SOURCE}" ls-tree -r --name-only "${PINNED_REVISION}" "${prefix}" > "${list}" || die "copy fail: ${id} (ls-tree)"
  while IFS= read -r path; do
    [[ -n "${path}" ]] || continue
    rel="${path#"${prefix}/"}"
    should_copy "${rel}" || continue
    dest_path="${dest_dir}/${rel}"
    mkdir -p "$(dirname "${dest_path}")"
    git -C "${SOURCE}" cat-file blob "${PINNED_REVISION}:${path}" > "${dest_path}" || die "copy fail: ${id}/${rel}"
    printf '%s\t%s\n' "${path}" "${id}/${rel}" >> "${INDEX}"
    copied=1
  done < "${list}"
  [[ "${copied}" -eq 1 ]] || die "copy fail: ${id} (no files)"
  [[ -f "${dest_dir}/SKILL.md" ]] || die "copy fail: ${id}/SKILL.md"
}

write_and_verify_manifest() {
  python3 - "$DEST" "$PINNED_REVISION" "$PINNED_VERSION" "$SOURCE_ID" "$INDEX" "$SOURCE" <<'PY'
import hashlib, json, os, pathlib, subprocess, sys

dest, revision, version, source_id, index_path, source_root = sys.argv[1:7]
mapped = []
with open(index_path, encoding="utf-8") as fh:
    for raw in fh:
        line = raw.rstrip("\n")
        if not line:
            continue
        source_path, dest_rel = line.split("\t", 1)
        source_path = source_path.replace("\\", "/")
        dest_rel = dest_rel.replace("\\", "/")
        if not (
            "/templates/skills/" in f"/{source_path}"
            or "/assets/external-skills/stable/skills/" in f"/{source_path}"
        ):
            raise SystemExit(f"sync-manuals: checksum fail: sourcePath outside search roots: {source_path}")
        dest_file = os.path.join(dest, dest_rel)
        if os.path.islink(dest_file) or not os.path.isfile(dest_file):
            raise SystemExit(f"sync-manuals: checksum fail: non-regular file {dest_file}")
        blob = subprocess.check_output(
            ["git", "-C", source_root, "cat-file", "blob", f"{revision}:{source_path}"]
        )
        source_digest = hashlib.sha256(blob).hexdigest()
        dest_digest = hashlib.sha256(pathlib.Path(dest_file).read_bytes()).hexdigest()
        if dest_digest != source_digest:
            raise SystemExit(f"sync-manuals: checksum fail: dest does not match source: {dest_rel}")
        mapped.append(
            {
                "sourcePath": source_path,
                "sha256": source_digest,
                "sourceRevision": revision,
                "_dest": dest_rel,
            }
        )

if not mapped:
    raise SystemExit("sync-manuals: checksum fail: no files copied")

on_disk = {}
for dirpath, dirnames, filenames in os.walk(dest):
    dirnames.sort()
    for name in sorted(filenames):
        if name in {"MANIFEST.json", ".sync-index.tsv", ".sync-list"}:
            continue
        path = os.path.join(dirpath, name)
        rel = os.path.relpath(path, dest).replace(os.sep, "/")
        on_disk[rel] = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

expected = {item["_dest"]: item["sha256"] for item in mapped}
if on_disk != expected:
    raise SystemExit("sync-manuals: checksum fail: dest does not match MANIFEST")

files = [
    {
        "sourcePath": item["sourcePath"],
        "sha256": item["sha256"],
        "sourceRevision": item["sourceRevision"],
    }
    for item in sorted(mapped, key=lambda item: item["sourcePath"])
]
manifest = {
    "source": source_id,
    "version": version,
    "sourceRevision": revision,
    "files": files,
}
with open(os.path.join(dest, "MANIFEST.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

resolve_source "${1:-}"
STAGE="$(mktemp -d "${ORIG_DEST}.stage.XXXXXX")"
DEST="${STAGE}"
INDEX="${DEST}/.sync-index.tsv"
: > "${INDEX}"

for id in "${WHITELIST[@]}"; do
  prefix="$(find_skill_prefix "${id}")"
  copy_skill "${id}" "${prefix}"
done

if find "${DEST}" \( -name 'install.sh' -o -name 'onboard.py' \) | grep -q .; then
  die "copy fail: installer artifacts must not be copied"
fi

rm -f "${DEST}/.sync-list"
write_and_verify_manifest
rm -f "${INDEX}"
BACKUP="$(mktemp -d "${ORIG_DEST}.bak.XXXXXX")"
rmdir "${BACKUP}"
mv "${ORIG_DEST}" "${BACKUP}"
if ! mv "${STAGE}" "${ORIG_DEST}"; then
  mv "${BACKUP}" "${ORIG_DEST}"
  die "replace fail: restored last-known-good manuals"
fi
rm -rf "${BACKUP}"
STAGE=""
DEST="${ORIG_DEST}"
DEST="${ORIG_DEST}"
echo "sync-manuals: wrote ${DEST}/MANIFEST.json sourceRevision ${PINNED_REVISION}"
