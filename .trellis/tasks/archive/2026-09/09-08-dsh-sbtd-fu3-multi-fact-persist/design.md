# Design — FU3 persist-across-replans + matching-set

## Boundaries

- Adapter: `packages/dsh-sbtd/src/tools/plan.ts` (`inferRequirements`, `mergeGate`, `sbtdPlan`)
- `clarifyStatus` plus `clarifyCompleteTaskId` are read in the plan merge loop to decide Forced Docs DDD stickiness
- Do not change `hooks.ts`, `elevateDocsDdd`, `unpassedRequired`
- `state.ts` `fact?: string` stays; matching-set encoded as a stable string when needed
- docs Complete writes `clarifyCompleteTaskId` from the live plan; Interview Reset deletes it; serialize/restore hydrate-not-merge

## Commit 1 — sticky required

In `sbtdPlan`, for `kind === "ddd"` when `sameGoal`, `session.clarifyStatus === "complete"`, `clarifyMode === "docs"`, and `session.clarifyCompleteTaskId === taskId`:

If previous `ddd.requirement === "required"` and inferred is `on-demand` (omitted grill facts), do not take the optional/disappear demote branches. Keep `required` + previous `state` + `reviewStatus`/`fact`.

Interview Reset deletes `clarifyStatus` and `clarifyCompleteTaskId` → next same-summary plan may demote. New `taskId` (`sameGoal === false`) drops previous gates. A docs Complete from another taskId does not sticky.


T3 continues to deny iff `unpassedRequired(plan.gates.ddd)`.

## Commit 2 — matching-set identity

Each predicate row has an `identity` (canonical concept). `inferRequirements` collects distinct matching identities (catalog order, unique), not `.find` first hit.

- **DDD-only alias collapse (Q1D):** ddd’s three grill-with-docs rows share identity `完整执行 grill-with-docs` (EN/zh grill wording collapses here only)
- Do **not** claim persist/持久化 and schema/数据库 share one identity — those remain distinct ddia `predicate.fact` catalog rows
- Distinct ddia/legacy/release catalog rows stay distinct; set expansion (e.g. persistence → persistence + database/schema) resets `required+passed`

Stored `fact`:

- one identity → that canonical string (backward compatible: persist-only remains `"persistence"`)
- several → sorted identities joined with `" + "` so existing `previous.fact !== inferred.fact` reset fires on expansion

`normalizeDddFact` (fix trail) canonicalizes legacy stored EN DDD grill facts before pass-keep compare; non-DDD facts are unchanged.

## Commit framing (Q4B re-lock A)

Two *ordered feature* commits: (1) sticky persist-across-replans; (2) matching-set. Additional docs/review/fix commits are permitted (honest Codex fix trail). Do not rewrite history to squash them.

## Rollback

Revert the feature commits (and any fix/docs commits on this branch as needed). T5 string-change and T6 Q8 tests remain the baseline contract.

## GitNexus

`mergeGate` / `inferRequirements` upstream risk LOW (caller `sbtdPlan` only). Index was 5 commits behind HEAD at analysis; treat as advisory vs tests.
