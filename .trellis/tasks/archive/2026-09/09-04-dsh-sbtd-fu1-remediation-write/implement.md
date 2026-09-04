# Implement — FU1 Remediation Write

## Book Gate Plan

| Skill | Role | Fact | Stage | Gate state |
|---|---|---|---|---|
| book-ddd-distilled-modeling | on-demand | grill + DDD already confirmed in fu1-ddd.md | — | not-required |
| book-ddia-data-design | on-demand | no persistence / schema / cache / queue | — | not-required |
| book-legacy-change-safety | required | existing production deny in gatePreExecute; high regression risk | before first production edit | passed |
| book-refactoring-pass | required | modifying existing production hooks.ts | before first production edit | passed |
| book-release-readiness | required | plugin pre-execute production-path blocking behavior | after tests | passed |

Skills not on `skill://`; run from `packages/dsh-sbtd/manuals/*/SKILL.md`.

## Steps

1. BDD: add 5 scenarios to `features/t3-hooks-gate.feature` (Chinese text, English keywords — existing convention).
2. Tests first in `test/t3-hooks.test.mjs`; set gates via `getSession` after `sbtdPlan`. Comments: whole-window allow, no classifier.
3. Safety net in place → Legacy characterized → Refactoring proceed (no refactor; add helper only).
4. Implement `remediationAllow` + skip denies.
5. Verify: `npx biome check src`, `npx tsc --noEmit`, `node --test test/t3-hooks.test.mjs` (from package).
6. Release readiness after green tests.
7. Commit only `packages/dsh-sbtd` intentional files. Push. Open PR. Do not merge. Skip registry publish.

## Validation

```
cd packages/dsh-sbtd && npx biome check src && npx tsc --noEmit && node --test test/t3-hooks.test.mjs
```

## Legacy Change Safety Review

Status: characterized
Behavior to change: required+unpassed legacy/refactor deny of production PathClass mutations even when reviewStatus is seam-required / refactor-first.
Behavior to preserve: needs-* still deny; legacy-first when legacy has no remediation window; ddd/ddia/release; EXEMPT/README; T5 mapGateState.
Current reproduction evidence: `node --test test/t3-hooks.test.mjs` — Loop1/Loop2 fail (nextCalled false); needs-clarification, legacy-first, EXEMPT pass.
Safety net: those five FU1 tests plus existing T3 suite. Tests added before production edit.
Hidden dependencies / seam: session `plan.gates.*.reviewStatus` already stored; hook did not read it.
Validation plan: biome check src, tsc --noEmit, node --test test/t3-hooks.test.mjs.
Review mode: normal

## Refactoring Review

Status: proceed
Review mode: normal
Existing-code scope: `gatePreExecute` unpassedRequired deny chain for legacy then refactor.
Behavior that must remain unchanged: all non-window T3 decisions; mapping in review.ts.
Structural friction: none blocking. Two sequential ifs remain.
Decision and smallest safe step: no refactor. Add `remediationAllow` (locked named helper) and two skip conditions.
Safety net and validation: FU1 tests (red before edit) + existing T3.
Deferred refactors: none.

## Release Readiness Review

Status: ready
Production path and affected users / systems: dsh-sbtd `tools/pre-execute` interceptor on host `@deepseek-ai/dsh@0.1.1-rc.2`; agents mutating production PathClass.
Failure modes and safeguards: window allows ALL production-class writes while reviewStatus is seam-required/refactor-first (no byte classifier). needs-* still deny. Legacy-first deny remains. ddd/ddia/release/EXEMPT/README unchanged. mapGateState unchanged.
Capacity / backpressure / limits: not-applicable (sync hook).
Observability / alerts / runbook: deny copy unchanged; no new metrics. Known limitation documented in tests and PR.
Rollout / migration / rollback / cleanup: PR only; skip package registry publish. Rollback: revert the commit.
Required validation and result: biome check src pass; tsc emit+noEmit pass; `node --test test/*.test.mjs` 80/80 pass.
Optional checks, accountable owner acceptance, and residual risk: Playwright/Maestro/Chrome not-needed (no UI). Residual: Q4A honor-only still-deny-non-remediation; FOLLOWUPS (b) and §3.4 combined parked. Accountable owner: this PR author.
