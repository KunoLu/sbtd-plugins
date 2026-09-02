# T1 implement

## Order

1. Add `packages/dsh-sbtd/features/t1-section-state.feature` (Chinese scenario text, English keywords). Update T0 feature: empty section → non-empty Chinese `sbtd` section.
2. Add `src/section.ts` (static Chinese 6.1 text) and `src/state.ts` (Map + serialize/restore).
3. Wire `registerSection` from `src/index.ts`. Keep `name` / `inject`. No tools/hooks. No fs.
4. Update README: pin + `@next` + short Chinese section.
5. Update T0 node:test; add T1 tests (section snapshot, apply register, Map isolation, serialize roundtrip, restart re-import). Tests import `dist/` after tsc. Update `package.json` test glob.
6. Update `.trellis/spec/dsh-sbtd/backend` layout notes that still describe a single-file noop stub.
7. Validate: package lint, typecheck, build, test.

## Validation

```bash
# from packages/dsh-sbtd, using the main checkout toolchain
tsc -p tsconfig.json
tsc -p tsconfig.json --noEmit
biome check src
node --test test/*.test.mjs
```

Live `dsh plugin --profile web add` is not required for T1 (T0 live accept). Maestro E2E: not-needed (no mobile path). Playwright: not-needed.

Result (worktree `/workspace/sbtd-plugins-t1`): lint 0, typecheck 0, build 0, test 10 pass / 0 fail.

## Rollback

Revert `packages/dsh-sbtd` T1 files in `/workspace/sbtd-plugins-t1`. Do not keep `dist/`. Do not touch the dirty unpublished-claim worktree.

## Gate recording order (disclosure)

T0 characterization ran **before** production edits: `tsc` + `node --test test/t0-stub.test.mjs` → 3 pass, empty `{ name: "sbtd", order: 50, text: "" }`.

DDD / DDIA / Legacy / Refactoring judgments were made from that evidence and the v1.2 PRD, but **this file still had placeholders while src was edited**. Reviewer contracts below are recorded after implementation. Missed artifact-recording order; evidence itself is unchanged.

Release review is after validation.

## Gate reviews

```text
DDD Boundary Review
Status: confirmed
Ubiquitous language: sbtd section; BookGatePlan; GateState; SbtdSessionState; sessionId; serialize/restore
Bounded contexts: dsh-sbtd host plugin (this task) vs Trellis CLI vs 640-skills installer. T1 stays in the plugin shell.
Invariants and business rules: apply never writes AGENTS.md or disk; section name sbtd order 50 non-empty Chinese 6.1 only; sessions isolated by sessionId; restart drops Map
Core / supporting / generic subdomains: core = SBTD routing section; supporting = session state for later tools; generic = in-process Map
Corrections to the grill-with-docs result: A10 overrides PRD 5.3 inject agents — keep tools + systemPrompt only
Open conflicts and questions: none
```

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: dsh-sbtd module; live Map keyed by caller sessionId
Write / read / async / failure paths: getSession/restore write; getSession/serialize read; no async; restart empties Map
Consistency model: single-process strong consistency; no cross-process
Idempotency / ordering / retry / deduplication: getSession create-once per id; restore overwrites plan/maestro.missing; serialize copies missing[]
Schema / migration / backfill / rollback / replay: types only; no persistence; rollback = revert module
Observability and repair: unit tests; no production metrics
Required tests: isolation, serialize roundtrip, re-import restart
```

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: empty systemPrompt.section text → non-empty Chinese 6.1 body via section.ts
Behavior to preserve: name dsh-sbtd; inject tools+systemPrompt; console T0 log; no fs/AGENTS.md; no tools/hooks; private; peer 0.1.1-rc.2; cordis id sbtd / name @kunolu/dsh-sbtd
Current reproduction evidence: worktree tsc + node --test t0-stub.test.mjs — 3 pass, empty section (before src edits)
Safety net: updated t0 tests + t1 section/state tests against dist/
Hidden dependencies / seam: host loads apply dynamically; GitNexus apply upstream UNKNOWN (0 callers, 1 unresolved apply site); grep: only package tests import apply
Validation plan: biome check src; tsc --noEmit; tsc; node --test test/*.test.mjs
Review mode: normal
```

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/src/index.ts
Behavior that must remain unchanged: name, inject, no disk writes, no tools/hooks
Structural friction: none
Decision and smallest safe step: no refactor; extract section.ts/state.ts as specified T1 modules
Safety net and validation: node:test + tsc
Deferred refactors: none
```

```text
Release Readiness Review
Status: ready
Production path and affected users / systems: DSH web profile loads @kunolu/dsh-sbtd apply() and injects sbtd section
Failure modes and safeguards: apply assumes host injects systemPrompt; empty text would be dropped — T1 text is non-empty; Map is process-local
Capacity / backpressure / limits: in-process Map unbounded per sessionId; T1 has no tools writing large state
Observability / alerts / runbook: console.log on load only
Rollout / migration / rollback / cleanup: revert packages/dsh-sbtd; dist gitignored; private true unpublished
Required validation and result: package lint/typecheck/build/test all pass (10 tests)
Optional checks, accountable owner acceptance, and residual risk: live dsh web system/reminder not run (dsh CLI not used in this worktree); user prompt required package scripts only. Owner: this task. Residual: host-assembled reminder text unproven on 0.1.1-rc.2 in this environment.
```
