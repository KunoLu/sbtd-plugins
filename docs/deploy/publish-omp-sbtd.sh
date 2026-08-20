#!/usr/bin/env bash
set -euo pipefail

readonly REGISTRY="https://registry.npmjs.org/"
readonly DEFAULT_TAG="next"
readonly REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"

usage() {
  cat <<'USAGE'
Usage: publish-omp-sbtd.sh <package.tgz> [--tag next]

Publishes one already-built @kunolu/omp-sbtd prerelease tarball to the public
npm registry under the next dist-tag. Before running this command, complete the
authoritative local exact-tarball four-command acceptance procedure.

Credential source, in priority order:
  1. <repository-root>/.env: a non-empty NPM_TOKEN=<token> assignment
  2. An inherited non-empty NPM_TOKEN environment variable

The .env file is parsed as data; it is never sourced or executed. Do not pass a
token as an argument or save one in this script.
USAGE
}

fail() {
  printf 'publish-omp-sbtd: %s\n' "$1" >&2
  exit 1
}

load_dotenv_npm_token() {
  local dotenv_path=$1
  local line value

  [[ -L $dotenv_path ]] &&
    fail "repository .env must not be a symbolic link: $dotenv_path"
  [[ -e $dotenv_path ]] || return 1
  [[ -f $dotenv_path && -r $dotenv_path ]] ||
    fail "repository .env must be a readable regular file: $dotenv_path"

  while IFS= read -r line || [[ -n $line ]]; do
    case $line in
      NPM_TOKEN=*)
        value=${line#NPM_TOKEN=}
        ;;
      *)
        continue
        ;;
    esac

    if [[ -n $value ]]; then
      NPM_TOKEN=$value
      export NPM_TOKEN
      return 0
    fi
  done < "$dotenv_path"

  return 1
}

[[ $# -ge 1 ]] || {
  usage >&2
  exit 2
}

artifact=$1
shift
tag=$DEFAULT_TAG

while [[ $# -gt 0 ]]; do
  case $1 in
    --tag)
      [[ $# -ge 2 ]] || fail "--tag requires a value"
      tag=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

if ! load_dotenv_npm_token "$REPOSITORY_ROOT/.env"; then
  [[ -n ${NPM_TOKEN:-} ]] ||
    fail "NPM_TOKEN is missing from $REPOSITORY_ROOT/.env and the environment"
fi
export NPM_TOKEN
[[ -f $artifact ]] || fail "tarball does not exist: $artifact"
[[ $artifact == *.tgz ]] || fail "tarball must have a .tgz extension: $artifact"
command -v tar >/dev/null 2>&1 || fail "tar is required on PATH"
tar -tzf "$artifact" >/dev/null 2>&1 || fail "tarball is not a readable gzip archive: $artifact"
[[ $tag == "$DEFAULT_TAG" ]] ||
  fail "only the $DEFAULT_TAG dist-tag is allowed for RC publication"
command -v node >/dev/null 2>&1 || fail "node is required on PATH"
command -v npm >/dev/null 2>&1 || fail "npm is required on PATH"

package_metadata=$(
  tar -xOzf "$artifact" package/package.json 2>/dev/null |
    node -e '
let source = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { source += chunk; });
process.stdin.on("end", () => {
  try {
    const manifest = JSON.parse(source);
    if (
      typeof manifest.name !== "string" ||
      typeof manifest.version !== "string"
    )
      process.exit(1);
    process.stdout.write(`${manifest.name}\t${manifest.version}\n`);
  } catch {
    process.exit(1);
  }
});
'
) || fail "tarball must contain a valid package/package.json manifest"
IFS=$'\t' read -r package_name package_version <<< "$package_metadata"
[[ $package_name == "@kunolu/omp-sbtd" ]] ||
  fail "tarball must contain @kunolu/omp-sbtd"
[[ $package_version =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-((0|[1-9][0-9]*)|([0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))(\.((0|[1-9][0-9]*)|([0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)))*(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$ ]] ||
  fail "tarball version must be a SemVer prerelease"

artifact_directory=$(cd -- "$(dirname -- "$artifact")" && pwd -P)
artifact="$artifact_directory/$(basename -- "$artifact")"

umask 077
npm_root=$(mktemp -d "${TMPDIR:-/tmp}/omp-sbtd-npm.XXXXXX")
availability_output="$npm_root/availability-output"
availability_userconfig="$npm_root/availability.npmrc"
globalconfig="$npm_root/global.npmrc"
userconfig="$npm_root/publish.npmrc"
mkdir -p "$npm_root/cache" "$npm_root/home"
: > "$availability_userconfig"
: > "$globalconfig"
cleanup() {
  rm -rf -- "$npm_root"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

if (
  cd "$npm_root"
  env -i \
    PATH="$PATH" \
    HOME="$npm_root/home" \
    npm_config_userconfig="$availability_userconfig" \
    npm_config_globalconfig="$globalconfig" \
    npm_config_cache="$npm_root/cache" \
    npm_config_registry="$REGISTRY" \
    npm view "$package_name@$package_version" version --json --registry "$REGISTRY"
) >"$availability_output" 2>&1; then
  fail "tarball version is already published: $package_name@$package_version"
fi
grep -Eq '(^|[[:space:]])E404([[:space:]]|$)' "$availability_output" ||
  fail "could not confirm whether tarball version is unoccupied"

printf '%s\n' '//registry.npmjs.org/:_authToken=${NPM_TOKEN}' > "$userconfig"

(
  cd "$npm_root"
  env -i \
    PATH="$PATH" \
    HOME="$npm_root/home" \
    NPM_TOKEN="$NPM_TOKEN" \
    npm_config_userconfig="$userconfig" \
    npm_config_globalconfig="$globalconfig" \
    npm_config_cache="$npm_root/cache" \
    npm_config_registry="$REGISTRY" \
    npm publish "$artifact" \
      --tag "$tag" \
      --access public \
      --registry "$REGISTRY" \
      --userconfig "$userconfig"
)
