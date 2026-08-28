#!/usr/bin/env bash
# Build evaluateNonledgerStatus stdin JSON from the GitHub API.
# Never checkouts the PR head. Requires GH_TOKEN and GITHUB_REPOSITORY.
set -euo pipefail

if [ "${#}" -lt 2 ]; then
  echo "usage: collect-nonledger-pr-input.sh <prNumber> <expectedHeadSha> [freshHeadSha]" >&2
  exit 1
fi

pr_number="$1"
expected_sha="$2"
fresh_sha="${3:-}"
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
tmp="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
pr_json="${tmp}/nonledger-pr.json"
files_json="${tmp}/nonledger-files.json"
checks_json="${tmp}/nonledger-checks.json"
runs_json="${tmp}/nonledger-runs.json"
jobs_json="${tmp}/nonledger-jobs.json"

gh api "repos/${repo}/pulls/${pr_number}" > "${pr_json}"

gh api --paginate "repos/${repo}/pulls/${pr_number}/files" \
  --jq '.[] | {filename: .filename} + (if .previous_filename != null and .previous_filename != "" then {previousFilename: .previous_filename} else {} end)' | jq -s . > "${files_json}"

head_from_pr="$(jq -r .head.sha "${pr_json}")"
check_sha="${expected_sha}"
if [ -n "${fresh_sha}" ]; then
  head_sha_out="${expected_sha}"
  fresh_out="${head_from_pr}"
else
  head_sha_out="${head_from_pr}"
  fresh_out=""
fi
gh api --paginate "repos/${repo}/commits/${check_sha}/check-runs" \
  --jq '.check_runs[] | {name: .name, appSlug: .app.slug, status: .status, conclusion: .conclusion}' \
  | jq -s . > "${checks_json}"

gh api --paginate "repos/${repo}/actions/runs?head_sha=${check_sha}" \
  --jq '.workflow_runs[] | {id: .id, path: .path, headSha: .head_sha, status: .status, conclusion: .conclusion}' \
  | jq -s . > "${runs_json}"

echo '{}' > "${jobs_json}"
jq -r '.[].id' "${runs_json}" | while read -r run_id; do
  [ -n "${run_id}" ] || continue
  gh api --paginate "repos/${repo}/actions/runs/${run_id}/jobs" \
    --jq '.jobs[] | {name: .name, status: .status, conclusion: .conclusion}' \
    | jq -s . > "${tmp}/nonledger-jobs-${run_id}.json"
  jq --arg id "${run_id}" --slurpfile jobs "${tmp}/nonledger-jobs-${run_id}.json" \
    '.[$id] = $jobs[0]' \
    "${jobs_json}" > "${tmp}/nonledger-jobs.next.json"
  mv "${tmp}/nonledger-jobs.next.json" "${jobs_json}"
done

jq -n \
  --argjson pr "$(cat "${pr_json}")" \
  --slurpfile files "${files_json}" \
  --slurpfile checks "${checks_json}" \
  --slurpfile runs "${runs_json}" \
  --slurpfile jobs "${jobs_json}" \
  --arg expected "${expected_sha}" \
  --arg fresh "${fresh_out}" \
  --arg head "${head_sha_out}" \
  '{
    state: $pr.state,
    headRepo: $pr.head.repo.full_name,
    headRef: $pr.head.ref,
    baseRef: $pr.base.ref,
    headSha: $head,
    expectedHeadSha: $expected,
    files: $files[0],
    checkRuns: $checks[0],
    workflowRuns: $runs[0],
    jobsByRunId: $jobs[0]
  }
  + (if $fresh == "" then {} else {freshHeadSha: $fresh} end)'
