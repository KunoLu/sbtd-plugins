# Implement — FU2 Review Recording Order

## Book Gate Plan

| Skill | Select | Hit fact | Stage | Gate state |
|---|---|---|---|---|
| book-ddd-distilled-modeling | on-demand | grill already confirmed; no new interview | — | not-required |
| book-ddia-data-design | on-demand | no persist/schema/cache/queue | — | not-required |
| book-legacy-change-safety | on-demand | not a bug fix; T5 covers current `sbtdReview` | — | not-required |
| book-refactoring-pass | required | edit existing `review.ts` | before first prod edit | passed (record lagged first prod edit) |
| book-release-readiness | required | `sbtd_review` tool API | after validation | passed |

`grill-with-docs`: 未完整调用 — locked DDD already confirmed; implement-only turn.

## Refactoring Review

Status: proceed
Review mode: normal
Existing-code scope: `packages/dsh-sbtd/src/tools/review.ts` `sbtdReview` (kind/status/plan validation already present; assignment `gate.state` / `gate.reviewStatus`).
Behavior that must remain unchanged: `mapGateState` / `PASS_STATUS` / `RUNNING_STATUS`; `requirement` never changed by review; T5 single-kind `PASS_TUPLES` refactor proceed when legacy is on-demand; invalid kind/status/no-plan throw-no-mutate; hooks Write Deny Order.
Structural friction: none. Insertion point is already a clear seam after plan lookup.
Decision and smallest safe step: no refactor needed. Add the both-required predicate immediately before mutate.
Safety net and validation: `features/t5-sbtd-review.feature` + `test/t5-review.test.mjs` order cases (red before predicate; full `node --test test/*.test.mjs` after).
Deferred refactors: none.

Timing breach: analysis concluded `proceed` before the predicate insert, but this written review was not persisted until after `review.ts` was edited. No extra structural change. Gate state: passed.

## Release Readiness Review

Status: ready
Production path and affected users / systems: `sbtd_review` session tool on dsh-sbtd adapter; models recording book-gate reviews.
Failure modes and safeguards: out-of-order `kind=refactor` throws Error and does not mutate gates; same fail-closed family as invalid kind/status/no-plan. On-demand legacy still unconstrained.
Capacity / backpressure / limits: not-applicable (in-process session state).
Observability / alerts / runbook: error copy includes live `legacy.state` and `legacy.reviewStatus` and points at `sbtd_review kind=legacy`.
Rollout / migration / rollback / cleanup: revert this PR. No repair of already-recorded early proceed. No new persisted fields.
Required validation and result: `biome check src` pass; `tsc --noEmit` pass; `node --test test/*.test.mjs` **88/88**.
Optional checks, accountable owner acceptance, and residual risk: CLI `node .gitnexus/run.cjs analyze --index-only` succeeded this session; MCP `impact` still reported commitsBehind=3 (session cache). `detect_changes` after CLI refresh: risk low, `sbtdReview` touched. `rtk` missing → fallback-native. No registry publish. GitNexus is advisory relative to 88/88 tests.

## Code Readability Review

Scope: modified hand-written production code and tests (`review.ts`, `t5-review.test.mjs`, `t5-sbtd-review.feature`)
Findings: none
Ponytail conflicts resolved: none (`ponytail` / `ponytail-review` Skills not visible this host)
Changes applied: none
Revalidation required: no

## Phase 3.3 spec update

No durable `.trellis/spec` change. Review Recording Order is adapter-local; CONTEXT.md language remains Lord-paste / docs-sync later.



## Checklist

1. Feature + T5 tests (red)
2. Predicate in `sbtdReview` (green)
3. `docs/TODO.md` FU2 in-progress + changelog + main SHA `226d4e3`
4. `biome check src`; `tsc --noEmit`; `node --test test/*.test.mjs`
5. Commit, push, open PR (do not merge, do not finish-work)

## Validation

```bash
npm run lint
npm run typecheck
npm run build
node --test test/*.test.mjs
```

cwd: `packages/dsh-sbtd`
