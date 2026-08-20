# P1.1 Runtime Contract

Read this reference when configuring `ingest`, `smoke`, a command Runner Adapter, trusted deployment metadata, or P1 artifacts.

## Logical run identity

- Ingest key: `product_key + revision_set_id + parser_version`.
- Smoke key: `revision_set_id + suite_key + environment_profile + attempt`.
- A duplicate key reuses the recorded result. A deliberate rerun increments `--attempt`; the prior evidence remains immutable.
- Infrastructure retries stay inside one logical attempt. Assertion failures do not retry automatically. Configure retry counts with `smoke.retry_policy.infrastructure` and identify infrastructure exit codes per command.

## Gherkin ingest

The parser preserves language, Feature, Rule, Background, Scenario, Scenario Outline, Examples, tags, Doc Strings, step Data Tables, paths, lines, refs and exact SHAs. It derives locators and fingerprints without adding IDs or changing source files.

Bindings use scenario-name static scans and optional repository `binding_manifests`. A manifest entry can use `scenario` / `scenarioName` / `bddScenario`, `featurePath` / `feature_path` / `sourceFeature`, and `testPath` / `test_path` / `path`.

## Smoke stages

Commands use `stage: preflight | prepare | test | cleanup`; omitted stages default to `test`. Preflight or preparation failure skips later non-cleanup stages. Cleanup always runs. A command can declare `timeout_seconds`, `required_runner_labels`, `infrastructure_exit_codes`, `retry_policy`, test type, mode and formal report pairs.

## Runner seam

`runner: local` is the default Adapter and preserves the existing detached-worktree execution. Its attestation comes from `workspace.local_runner`.

A non-local runner key resolves through `workspace.runners`. The command Adapter receives three placeholders:

- `{job_manifest}`: exact Revision Set, repository SHA, native argv and requested labels.
- `{result_manifest}`: the path where the Adapter writes a Schema-valid result.
- `{artifact_dir}`: the contained directory where the Adapter materializes reports.

The Adapter may bridge to a CI system, queue, Android device pool or iOS/macOS runner. It returns status, failure class, queue latency, runner/tool/image attestation and report paths. The orchestrator validates the result and collects the reports; it does not execute `.feature` files.

## Trusted environment alignment

`verified` requires all of the following:

1. Deployment repository SHAs equal the Revision Set.
2. The deployment manifest is inside a configured `workspace.trust.deployment_metadata_roots` path.
3. Its issuer is in `allowed_issuers`.
4. Its canonical digest is valid.
5. The actual Adapter runner ID, version, image digest, labels and tool versions match the manifest entry for that runner key.

A version mismatch is `mismatch`; missing or untrusted provenance is `unverified`. A policy requiring alignment turns either state into `blocked`.

## Report and artifact integrity

- Reports and same-stem Markdown summaries must be created or refreshed after the current command starts.
- Markdown summaries must contain Chinese text.
- Every collected file records path, SHA-256, size and modified time in `artifact-manifest-<repository>.json`.
- `checksums-<repository>.sha256` covers the reports, summaries and artifact manifest.
- Basic sensitive-data matches block collection.

`metrics.json` records run duration, repository/command/report counts, retry count, runner type, queue latency and final status counters. Logs and metrics contain identifiers and statuses, not sensitive payloads.

## Schema compatibility

P1.1 extends schema version `1` with optional fields, so existing valid version-1 evidence remains readable. There is no earlier major runtime schema to migrate. P2 owns dual-reading the current and previous major versions before any future breaking writer change.
