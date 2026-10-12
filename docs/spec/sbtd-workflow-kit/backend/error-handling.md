# sbtd-workflow-kit Error Handling

> One error class, a closed code union, fail-closed everywhere. No result-object pattern exists in
> this package — exceptions only.

---

## The `KitError` Contract

`KitError extends Error` (`src/index.ts:213-256`) carries:

- `code`: one of a **closed union of 25 SCREAMING_SNAKE codes** (e.g. `SOURCE_DIGEST_MISMATCH`,
  `SECTION_UNMAPPED`, `GENERATED_DRIFT`, `PROJECTION_FORBIDDEN_TOKEN`, `TRANSACTION_FAILED`,
  `STALE_PLAN`). Adding a new code means extending the union type in `src/index.ts` — do not invent
  ad-hoc string codes at throw sites.
- `message`: human-readable sentence.
- `details`: `Readonly<Record<string, unknown>>` machine-usable payload. Callers and tests consume
  `details`; never encode data into `message` for later parsing.

Representative payloads: `SECTION_UNMAPPED` includes `{ unmapped, syncReport: { added: unmapped,
… } }` (`src/index.ts`); drift errors include `{ expectedFiles, actualFiles }`.

## Pattern 1: Wrap foreign causes, never leak them raw

Parse/read failures are caught and rethrown as `KitError` with the original error reduced to a
message string:

- `readUpstreamLock` → `new KitError("KIT_INPUT_INVALID", "Kit upstream lock is invalid",
  { cause: cause instanceof Error ? cause.message : "unknown" })` (`src/index.ts:410-424`).
- Same shape in `parseInputs` (`src/index.ts`) and `readOmpDistributionMap`
  (`src/omp-projection.ts:507-530`).

The narrowing idiom `cause instanceof Error ? cause.message : "unknown"` is mandatory — `catch`
variables are `unknown` under `strict` and never assumed to be `Error`.

## Pattern 2: Projection-local error factories

`omp-projection.ts` narrows the code union to its 9 `PROJECTION_*` codes via a local
`projectionError(code, message, details)` factory (`src/omp-projection.ts:246-264`) that returns
`new KitError(...)`. Example: duplicate policy decisions → `PROJECTION_POLICY_INVALID` with
`{ duplicates: [...new Set(duplicates)].sort() }` (note: sorted for determinism).

## Pattern 3: Transactional rollback errors

`applyCandidate` (`src/sync-upstream.ts:966-991`) catches apply failures, attempts
`rollback(completed)`, and if rollback itself fails throws `TRANSACTION_FAILED` with BOTH `cause`
and `rollbackCause` in `details`. A successful rollback still throws `TRANSACTION_FAILED` ("upstream
promotion failed and restored every destination") — a failed apply is never reported as success.

## CLI Boundary

`sync-upstream.ts`'s CLI layer catches everything, normalizes to `KitError`, writes a **single-line
JSON** object `{"status":"failed","error":{code,message,details}}` to stderr, and sets
`process.exitCode = 1`. There is no logger and no pretty-printed stack in normal operation.

## Fail-Closed Posture

Invalid input, drift, or policy violations throw **before any output is written** — generation
builds into stage dirs and only renames on success (see
[Codegen Workflow](./codegen-workflow.md#write-mechanics-all-generators)). There is no partial
write, no silent fallback. `proveStableInstallPolicy` (`src/sync-upstream.ts`) exists specifically
to assert that an explicit upstream install request fails closed instead of falling back to stable.
