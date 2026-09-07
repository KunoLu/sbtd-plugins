# Design — dsh-sbtd T6 `sbtd_clarify`

## Seams

- New `packages/dsh-sbtd/src/tools/clarify.ts` (model-facing tool)
- `state.ts` optional `clarifyMode` + `clarifyStatus` on session and snapshot
- `index.ts` register + re-export
- `section.ts` one-line Forced DDD narrowing
- Tests: `test/t6-clarify.test.mjs`; feature `features/t6-sbtd-clarify.feature`
- Callers of `apply` tool-count (t2/t3/t5) become three tools: plan, review, clarify

## Clarify Mode bind (Q1 B / Q11 B)

- Unbound: `mode` required (`docs|generic`); bind on session.
- Bound: omitted `mode` inherits; different `mode` throws until `reset: true`.
- `reset: true` deletes `clarifyMode` and `clarifyStatus` first, then the rest of the call proceeds as unbound (mode required unless reset-only).
- After Complete, further calls throw unless `reset` (Q10 A terminal).

## Complete dual gate (Q4 D / Q5 C)

Computed, never model self-declare:

`complete = frontier_empty === true && user_confirmed === true`

`load_manuals === true` without that pair stays Partial. Manuals may be returned on Partial.

Complete without `session.plan` throws (same family as review: ask for `sbtd_plan`). Partial never requires a plan.

## Forced Docs DDD (Q2 B / Q7 A / Q8 A)

On **docs** Complete only:

1. Re-call `sbtdPlan` with the live `plan.summary` plus prior catalog `fact`s and `完整执行 grill-with-docs` so `inferRequirements` sets `ddd` required. Do not rewrite PREDICATES. Do not set `requirement` inside review.
2. Call `sbtdReview({ kind: "ddd", status })`. `ddd_status` if `confirmed|needs-clarification|blocked`; else if live `reviewStatus === "confirmed"` re-record `confirmed`; else `blocked`.
3. Partial must not call `sbtdReview`.

Generic Complete skips both steps.

## One-shot blocked (Q10 A)

If Complete and `gates.ddd.requirement === "required"` and `reviewStatus !== "confirmed"`: return `clarifyStatus: "complete"` plus `blocked` payload (`resume: "not-clarify"`, `suggestPrd: false`, `suggestImplement: false`). Complete remains stored.

## Persistence (Q9 A)

`serialize`/`restore` copy `clarifyMode` and `clarifyStatus` with the same hydrate-not-merge rule as `plan` (absent snapshot key deletes live field). Compaction is not Reset.

## Current Question (Q3 B)

Schema has singular `question` (string). Output `currentQuestion` is that string or `null` (Complete / reset-only / manuals-only). No array.

## Section

Replace over-broad “完整澄清后必须有 DDD 复审通过态” with docs-mode Complete only. Snapshot file updates.

## Risks

- GitNexus `getSession` HIGH (hub). Additive optional fields; hooks still read `plan`/`validate` only.
- Tool-count tests in t2/t3/t5 must move to three tools; do not weaken T3 ddd deny.
- Index stale (2 commits behind) — treat GitNexus as advisory; confirm with tests.

## Rollback

Revert the feature branch. No schema/migration. In-process Map only.
