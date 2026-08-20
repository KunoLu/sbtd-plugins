# Validation Evidence Contract

Use this contract only when a formal test report is intended to become pull-request evidence or be ingested by a knowledge system. Ordinary local diagnostics and reports that remain local do not need an evidence sidecar.

The native runner report and its same-stem Chinese Markdown summary remain the primary test artifacts. The evidence document is a provenance envelope. It does not replace the report, the summary, or the runner result.

## Source and revision rules

- `developer-local`, `ci`, and `knowledge-server` are separate evidence sources and must never overwrite or masquerade as one another. `ci` means a CI runner created the evidence; it is not an alias for developer-local upload or knowledge-server smoke.
- Record the repository key, raw source ref, full commit SHA when available, worktree state, trigger, and creation time. `branch_slug` is only a filename-safe label; it is not revision identity.
- A dirty developer worktree uses `sourceRevision: dirty` and `evidencePublication: local-only`. It may assist diagnosis, but it cannot attest a PR head.
- Developer evidence used by a PR must use `sourceRevision: exact`, match the current PR head SHA, and be invalidated by every new commit.
- CI evidence uses a clean checkout and `sourceRevision: exact`. When its target is a pull request, the recorded commit must equal the final PR head SHA; a new commit invalidates the evidence and requires a new run or a provider-backed revalidation.
- Evidence created before the final commit records local validation state only. After the commit and before publication or PR Check update, regenerate or revalidate against the final PR head SHA and update the report sidecar or aggregate envelope; pre-commit and older-head evidence cannot attest the PR.
- Knowledge-server evidence must include an exact multi-repository `revisionSet`. A configured branch such as `staging` is resolved to a commit SHA before execution.
- Record whether the runtime environment is aligned with the revisions under test. `unverified` or `mismatch` must not be reported as verified full-stack evidence.
- Preserve the actual test mode. `smoke-only`, `contract-backed`, `mock-backed`, and `app-mocked` evidence cannot be promoted to `full-stack` by publication.

## Feature trace rules

Do not require Feature IDs or Scenario IDs. Each feature source uses repository key, path, optional Feature / Rule / Scenario names, optional Examples fingerprint, source ref, and resolved commit SHA. These fields locate the behavior snapshot without modifying the `.feature` file.

## Artifact rules

- Place a per-report sidecar next to the formal report using the same report stem plus `.evidence.json`, for example `playwright-report-order-staging-2026_07_15-12_00_00.evidence.json`.
- A cross-tool orchestrator may instead create one envelope in its isolated runtime or evidence bundle, provided it references every report and summary.
- Every referenced formal report records its path, same-stem Markdown summary path, SHA-256 digest, status, test type, and actual execution mode.
- Evidence publication must redact secrets, tokens, accounts, PII, sensitive request data, production data, screenshots, traces, and attachments before upload.
- `published` means the envelope and referenced artifacts were accepted by the configured evidence destination. It does not mean the tests passed.
- CI publication is separate from CI execution: use `published` only after the PR or knowledge destination accepts the evidence, `not-configured` when no publisher exists, and `blocked` when publication was required but failed. CI evidence cannot use `local-only`.

## Schema versions

- `validation-evidence.schema.json` remains schemaVersion 1. Its `featureSources[]` and `reports[]` arrays stay independent. v1 is valid for generic or historical report evidence and for knowledge-base report-only smoke. Co-membership in a v1 envelope is not BDD traceability.
- Scenario-backed execution evidence must use `validation-evidence.v2.schema.json` (`schemaVersion: 2`) and `scripts/validate_validation_evidence.py`. JSON Schema shape checks are not sufficient.

`scripts/validate_validation_evidence.py` requires the Python package listed in
`requirements.txt` (`jsonschema`). Missing `jsonschema` is
`VALIDATOR_UNAVAILABLE` and fail-closed for both v1 and v2. Do not skip schema
validation. Install with `python3 -m pip install -r requirements.txt` from the
installed `project-validation` Skill root.
- Paths in this contract (`references/*.json`, `scripts/validate_validation_evidence.py`) are relative to the `project-validation` Skill root.
- Shared validator fixtures live in the config-excerpt repo at `tests/fixtures/validation-evidence/validation-evidence-v2/`. They are not Skill runtime assets and must not be copied into installed project or global Skill trees.
- v1 Schema validation checks digest format only. Generic evidence still requires recomputing each report SHA-256 against file bytes.
- Do not upgrade, rewrite, or synthesize v1 envelopes into v2 links. If a producer cannot emit a valid v2 binding, mark scenario execution evidence `blocked`.

## v2 locator and report binding

Canonical `sourceLocatorDigest` is SHA-256 over UTF-8 JSON with `ensure_ascii=False`, `sort_keys=True`, and separators `( ",", ":" )`, using this exact key order after sorting:

`examplesFingerprint`, `feature`, `path`, `repositoryKey`, `rule`, `scenario`, `sourceCommit`, `sourceRef`.

- `path` is a repository-relative POSIX path. Before hashing, replace `\` with `/`, reject absolute / `~` prefixes, drop empty and `.` segments (so `features/./login.feature` becomes `features/login.feature`), and reject `..` or symlink escape outside the repository root.
- Missing, empty, or omitted optional `rule` / `examplesFingerprint` serialize as JSON `null`, not `""`.
- `sourceCommit` is stripped and lowercased before hashing; the result must be hex of length 40 or more.
- The digest hex is lowercase and has no `sha256:` prefix. Producers must hash this normalized payload, not the raw envelope spellings.

A v2 `scenarioLink` binds `sourceLocatorDigest` to `reportSha256`, a versioned `reportFormat`, and a structured `testCaseSelector`. Initial formats that can satisfy scenario traceability:

- `junit-xml-v1`
- `playwright-json-v1`

HTML, TXT, arbitrary JSON, and other reports may remain as `human-readable` or `generic` artifacts. They cannot appear as the linked `reportFormat` for a v2 scenario link.

The semantic validator must:

1. Recompute every locator digest.
2. Resolve only regular files inside the repository root.
3. Hash the linked report bytes and require equality with `reportSha256`.
4. Parse the SHA-verified report with DTD/external-entity disabled for JUnit.
5. Match exactly one passed test case with the structured selector.
6. Extract the case-local `sbtd.sourceLocatorDigest` JUnit property or Playwright annotation and require it to equal the recomputed locator digest.

Reject fabricated labels, real passed cases bound to another locator, missing or duplicate bindings, zero or multiple selector matches, unsupported formats, unsafe paths, declared-SHA mismatches, tampered bytes, and dangling links. The semantic validator compares locator / repository / attestation commit strings; it does not inspect Git HEAD or a trusted source manifest. Stale trees remain a workflow / publication gate: regenerate or revalidate against the attested revision before publication.

KPi `plugins/omp-sbtd` is a consumer of this contract after a reviewed promotion. It must not invent a private mapping that differs from this validator.

## Required status output

- `Evidence Source`: `developer-local` / `ci` / `knowledge-server` / `not-needed`
- `Source Revision`: `exact` / `dirty` / `unknown` / `not-needed`
- `Environment Alignment`: `verified` / `unverified` / `mismatch` / `not-needed`
- `Evidence Publication`: `local-only` / `published` / `blocked` / `not-configured` / `not-needed`

Validate generic envelopes with `validation-evidence.schema.json`. Validate scenario-backed envelopes with `validation-evidence.v2.schema.json` plus `scripts/validate_validation_evidence.py`. Storage, publishing commands, PR provider adapters, retention, and server orchestration are outside the P0 contract and belong to later integration phases.
