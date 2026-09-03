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
INDEX=""

die() {
  echo "sync-manuals: $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${CLONE_DIR}" && -d "${CLONE_DIR}" ]]; then
    rm -rf "${CLONE_DIR}"
  fi
  if [[ -n "${INDEX}" && -f "${INDEX}" ]]; then
    rm -f "${INDEX}"
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
  SOURCE="$(cd "${SOURCE}" && pwd)"

  if ! git -C "${SOURCE}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
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

record_file() {
  local source_rel="$1"
  local dest_rel="$2"
  printf '%s\t%s\n' "${source_rel}" "${dest_rel}" >> "${INDEX}"
}

copy_skill() {
  local id="$1"
  local src="$2"
  local dest_dir="${DEST}/${id}"
  local src_rel="${src#"${SOURCE}/"}"
  mkdir -p "${dest_dir}"
  cp -f "${src}/SKILL.md" "${dest_dir}/SKILL.md" || die "copy fail: ${id}/SKILL.md"
  record_file "${src_rel}/SKILL.md" "${id}/SKILL.md"
  if [[ -d "${src}/references" ]]; then
    rm -rf "${dest_dir}/references"
    cp -R "${src}/references" "${dest_dir}/references" || die "copy fail: ${id}/references"
    local f rel
    while IFS= read -r -d '' f; do
      rel="${f#"${src}/"}"
      record_file "${src_rel}/${rel}" "${id}/${rel}"
    done < <(find "${src}/references" -type f -print0)
  fi
}

write_and_verify_manifest() {
  python3 - "$DEST" "$PINNED_REVISION" "$PINNED_VERSION" "$SOURCE_ID" "$INDEX" "$SOURCE" <<'PY'
import hashlib, json, os, pathlib, sys

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
        source_file = os.path.join(source_root, source_path)
        dest_file = os.path.join(dest, dest_rel)
        if os.path.islink(source_file) or not os.path.isfile(source_file):
            raise SystemExit(f"sync-manuals: checksum fail: missing source file {source_path}")
        if os.path.islink(dest_file) or not os.path.isfile(dest_file):
            raise SystemExit(f"sync-manuals: checksum fail: non-regular file {dest_file}")
        source_digest = hashlib.sha256(pathlib.Path(source_file).read_bytes()).hexdigest()
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
        if name in {"MANIFEST.json", ".sync-index.tsv"}:
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
manifest_path = os.path.join(dest, "MANIFEST.json")
with open(manifest_path, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

resolve_source "${1:-}"
[[ -d "${DEST}" ]] || mkdir -p "${DEST}"
INDEX="${DEST}/.sync-index.tsv"

find "${DEST}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
: > "${INDEX}"

for id in "${WHITELIST[@]}"; do
  src_dir="$(find_skill_dir "${id}")"
  copy_skill "${id}" "${src_dir}"
done

if find "${DEST}" \( -name 'install.sh' -o -name 'onboard.py' \) | grep -q .; then
  die "copy fail: installer artifacts must not be copied"
fi

write_and_verify_manifest
echo "sync-manuals: wrote ${DEST}/MANIFEST.json sourceRevision ${PINNED_REVISION}"
