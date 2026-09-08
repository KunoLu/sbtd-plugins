# Implement — FU3 multi-fact + persist-across-replans

## Book Gate Plan

| Skill | Select | Hit fact | Stage | Gate state |
|---|---|---|---|---|
| book-ddd-distilled-modeling | on-demand | grill already confirmed; no new interview | — | not-required |
| book-ddia-data-design | on-demand | in-memory session `fact?: string`; no durable schema | — | not-required |
| book-legacy-change-safety | required | existing `mergeGate` demote write hole | before first behavior edit | passed |
| book-refactoring-pass | required | edit existing `plan.ts` | after legacy characterized | passed |
| book-release-readiness | required | `sbtd_plan` production tool | after validation | passed |

`grill-with-docs`: 未完整调用 — locked DDD already confirmed; implement-only turn.

## Legacy Change Safety Review

Status: characterized
Behavior to change: same-summary omitted grill facts demoted Forced Docs DDD; first-match hid persist+schema expansion.
Behavior to preserve: T5 string-change reset, Q8 elevateDocsDdd, Gate-only T3 deny, Interview Reset / new taskId demote, generic Complete never Forced Docs DDD.
Current reproduction evidence: t2/t3/t6 omit-replan tests failed pre-fix (`required` → `on-demand`); persist+schema kept `passed` under first-match.
Safety net: `t2-plan.test.mjs` / `t3-hooks.test.mjs` / `t6-clarify.test.mjs` + matching features.
Hidden dependencies / seam: `clarifyStatus` + `clarifyMode` on session; `mergeGate` now takes `keepRequired`. No production seam.
Validation plan: `npm run lint && npm run typecheck && npm run build && node --test test/*.test.mjs`
Review mode: normal

## Refactoring Review

Status: proceed
Review mode: normal
Existing-code scope: `plan.ts` `inferRequirements` / `mergeGate` / `sbtdPlan`.
Behavior that must remain unchanged: Q8 elevate; hooks `unpassedRequired`; T5 replacement reset; on-demand promotion reset.
Structural friction: none. Sticky branch is a guard before existing merge; matching-set is local to infer.
Decision and smallest safe step: no refactor needed.
Safety net and validation: package tests 115/115.
Deferred refactors: none.

## Release Readiness Review

Status: ready
Production path and affected users / systems: `sbtd_plan` session tool; models re-planning after docs Complete.
Failure modes and safeguards: omitted grill facts no longer open T3 writes while docs Complete; Interview Reset and new taskId still demote; generic Complete does not sticky.
Capacity / backpressure / limits: not-applicable (in-process Map).
Observability / alerts / runbook: markdown still records trigger-fact-changed notes on matching-set expansion.
Rollout / migration / rollback / cleanup: revert the two commits. `fact?: string` encoding stays compatible for single-member sets.
Required validation and result: `biome check src` pass; `tsc --noEmit` pass; `node --test test/*.test.mjs` **115/115**.
Optional checks, accountable owner acceptance, and residual risk: GitNexus `detect-changes --scope all` risk medium (`inferRequirements`, `mergeGate`; SbtdClarify haystack/merge flows). Index refreshed this session. `rtk` missing → fallback-native. No registry publish. Host remains `@deepseek-ai/dsh@0.1.1-rc.2`.


## Checklist

1. Features + tests for sticky Forced Docs DDD (red)
2. `mergeGate`/`sbtdPlan` sticky required (green) — commit 1
3. Features + tests for matching-set / alias collapse / expansion (red)
4. `inferRequirements` matching-set (green) — commit 2
5. `docs/TODO.md` FU3 in-progress + changelog + main SHA `86bcdce`
6. `biome check src`; `tsc --noEmit`; `node --test test/*.test.mjs`
7. Push, open PR (do not merge, do not finish-work, do not slash-review)

## Validation

```bash
npm run lint
npm run typecheck
npm run build
node --test test/*.test.mjs
```

cwd: `packages/dsh-sbtd`
