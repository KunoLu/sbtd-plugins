# Design — FU3 persist-across-replans + matching-set

## Boundaries

- Adapter: `packages/dsh-sbtd/src/tools/plan.ts` (`inferRequirements`, `mergeGate`, `sbtdPlan`)
- `clarifyStatus` is read only in the plan merge loop to decide Forced Docs DDD stickiness
- Do not change `hooks.ts`, `elevateDocsDdd`, `unpassedRequired`
- `state.ts` `fact?: string` stays; matching-set encoded as a stable string when needed

## Commit 1 — sticky required

In `sbtdPlan`, for `kind === "ddd"` when `sameGoal` and `session.clarifyStatus === "complete"`:

If previous `ddd.requirement === "required"` and inferred is `on-demand` (omitted grill facts), do not take the optional/disappear demote branches. Keep `required` + previous `state` + `reviewStatus`/`fact`.

Interview Reset deletes `clarifyStatus` → next same-summary plan may demote. New `taskId` (`sameGoal === false`) drops previous gates.

T3 continues to deny iff `unpassedRequired(plan.gates.ddd)`.

## Commit 2 — matching-set identity

Each predicate row has an `identity` (canonical concept). `inferRequirements` collects distinct matching identities (catalog order, unique), not `.find` first hit.

- ddd’s three grill-with-docs rows share identity `完整执行 grill-with-docs`
- Language aliases (persist/持久化, schema/数据库, …) share one identity
- Distinct concepts stay distinct (persistence vs database/schema)

Stored `fact`:

- one identity → that canonical string (backward compatible: persist-only remains `"persistence"`)
- several → sorted identities joined with `" + "` so existing `previous.fact !== inferred.fact` reset fires on expansion

## Rollback

Revert the two commits. T5 string-change and T6 Q8 tests remain the baseline contract.

## GitNexus

`mergeGate` / `inferRequirements` upstream risk LOW (caller `sbtdPlan` only). Index was 5 commits behind HEAD at analysis; treat as advisory vs tests.
