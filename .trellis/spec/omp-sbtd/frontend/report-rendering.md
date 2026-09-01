# omp-sbtd Report Rendering

> How validation reports and evidence descriptors are rendered and parsed. Source:
> `packages/omp-sbtd/src/report/index.ts`; tests in `test/report.test.ts`,
> `test/report-command.test.ts`; fixtures in `test/fixtures/p0-reports.ts`.

---

## Round-Trip Contract

`src/report/index.ts` defines the zod schemas (`validationReportSchema`,
`providerObservationSchema`, `evidenceEnvelopeSchema`) and the build/render/parse round-trip: a
rendered report must parse back into the same schema-valid object. `test/report.test.ts` exercises
this against frozen text fixtures (`test/fixtures/p0-reports.ts`) — when you change the rendered
format, update fixtures and round-trip tests together.

## Sanitization at the Boundary

Rendered identifiers pass through bounded schemas (`src/report/index.ts:4-30`):

- `safeIdentifierSchema`, `safeCodeSchema`, `safeRelativePathSchema` — regex- and length-bounded
  strings for anything interpolated into report text.
- `MAX_RENDERED_SBTD_REPORT_BYTES` (32 KiB) caps assembled output; `MAX_ENVELOPE_BYTES` (256 KiB)
  caps envelopes; `MAX_REPORT_TOOL_EVIDENCE_RECORDS` (24) bounds record counts.

Never interpolate unvalidated identifiers into report or marker text.

## Digests, Not Contents

Evidence descriptors persist only SHA-256 fingerprints (scenario locator digest, report digest,
sidecar digest, commit) — never file contents, secrets, or prompt text
(`validationEvidenceDescriptorSchema`; README "Data handling and telemetry"). The envelope fixture
shape (`test/fixtures/validation-evidence-v2/positive-changed-junit/envelope.json`) shows the
v2 contract: `schemaVersion: 2`, `sourceLocators[]` with `sourceLocatorDigest`, `reports[]` with
`sha256`/`status`/`reportFormat`, `scenarioLinks[]` binding locator ↔ report ↔ testCaseSelector,
`secretsRedacted: true`.

## Runtime Markers

Major-turn markers (`sbtd-runtime`) are machine contracts carrying state version, runtime mode,
policy profile, environment mode, effective control state, route, and stage. Mode-aware AGENTS
conditional sections key off `effective-control-state=active` — marker text changes are
contract changes; check `features/runtime-workflow-gates.feature` and the fail-closed append path
in `src/extension.ts` (blocked marker with `repair="/sbtd doctor"`) before editing.
