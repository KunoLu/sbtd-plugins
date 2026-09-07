# PRD — FU2 Review Recording Order (legacy-before-refactor)

## Background

T3 Write Deny Order already denies unpassed required `legacy` before unpassed required `refactor` on production writes. `sbtd_review` still records any legal `kind=refactor` status with no cross-gate check. When both Gates are `required`, a model can record `proceed` first and mark refactor `passed` before legacy is cleared.

Canonical name: **Review Recording Order**. Seam: `sbtd_review` only. Not Write Deny Order. Not a `PreToolDecision`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-fu2-legacy-before-refactor`
- File: `src/tools/review.ts` `sbtdReview` after kind/status/plan validation and before `gate.state` / `gate.reviewStatus` assignment

## Behavior

When **both** `legacy` and `refactor` have `requirement === "required"` on the live plan, and `kind === "refactor"`:

- If `legacy.state === "passed"` → allow any legal refactor status.
- Else if `legacy.reviewStatus === "seam-required"` and `status === "refactor-first"` → allow (`state=running`).
- Else throw `Error` (Q5B). Do **not** write `gate.state` / `gate.reviewStatus` for the rejected kind.

When `kind !== "refactor"` or either gate is on-demand: no new constraint. T5 single-kind `PASS_TUPLES` refactor `proceed` on `"edit existing production module"` stays legal.

When both required and outside the seam-required window, `kind=refactor status=blocked` is also out of order.

## Error copy (Q5B)

Dedicated sentence, distinct from T3 `required gate 未 passed，请先调用 sbtd_review kind=…`. Must:

- say refactor **recording** is blocked until the predecessor (`legacy.state === "passed"`)
- include live `legacy.state` and `legacy.reviewStatus`
- point at `sbtd_review kind=legacy` (not skill ids)

## Non-goals

- `hooks.ts`, `mapGateState`, `PASS_STATUS`, `RUNNING_STATUS`, FU1 `remediationAllow`
- ddd / ddia / release recording order (Q6A)
- FU3 / T6
- Repairing already-recorded early `proceed`
- `reviewMode` persistence
- Registry publish / omp config / host retarget

## Locked Q1–Q6

| Q | Lock |
|---|---|
| Q1 A | Both-required applicability only |
| Q2 A | Predecessor = `legacy.state === "passed"` |
| Q3 A | Seam-required → record `refactor-first` only; reject `proceed` |
| Q4 A | Throw Error; no mutate rejected kind |
| Q5 B | Dedicated order copy with live state + reviewStatus + `kind=legacy` |
| Q6 A | Park ddd/ddia/release recording order |

## Acceptance

- [x] Both required, legacy planned / no review → `kind=refactor status=proceed` throws; both kinds' `state`/`reviewStatus` unchanged
- [x] Both required, legacy passed/characterized → refactor proceed OK
- [x] Both required, legacy seam-required → refactor-first OK (`state=running`); proceed throws; legacy row unchanged on reject
- [x] Only refactor required (legacy on-demand) → proceed still OK
- [x] Error contains live `legacy.state` + `legacy.reviewStatus` and `kind=legacy`, not skill ids
- [x] Existing T5 regressions green
- [x] `biome check src`; `tsc --noEmit`; `node --test test/*.test.mjs` **88/88**
