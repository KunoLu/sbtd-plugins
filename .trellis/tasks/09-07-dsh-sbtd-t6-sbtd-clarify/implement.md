# Implement — dsh-sbtd T6 `sbtd_clarify`

## Book Gate Plan

| Skill | required / on-demand | Hit | Stage | Gate state |
|---|---|---|---|---|
| book-ddd-distilled-modeling | on-demand | grill already confirmed in t6-ddd-r2; this slice is coding | — | not-required |
| book-ddia-data-design | on-demand | in-process session fields, not persistent store | — | not-required |
| book-legacy-change-safety | on-demand | not a bugfix; serialize/section/registration already tested | — | not-required |
| book-refactoring-pass | required | edit existing `state.ts` / `section.ts` / `index.ts` | before first prod edit | planned → running → passed |
| book-release-readiness | on-demand | no deploy/publish; T6 fence | after tests | not-required |

grill-with-docs this turn: **未完整调用**. Reason: locked DDD r2 already `confirmed`; user ordered implement; no new domain questions.

## Refactoring Review (mandatory)

Status: proceed. Review mode: normal.
Existing-code scope: `state.ts` serialize/restore, `section.ts` one line, `index.ts` register.
Behavior that must remain unchanged: T1–T5 plan/review/hooks; T3 ddd deny; PREDICATES; mapGateState.
Structural friction: none that blocks the additive tool.
Decision: **no refactor needed** — new file + optional fields + register.
Safety net: package `node --test test/*.test.mjs` after `tsc` build.
Deferred: none.

## Checklist

1. BDD `features/t6-sbtd-clarify.feature` (Chinese steps, English keywords)
2. `state.ts` fields + serialize/restore
3. `clarify.ts` + register in `index.ts`
4. Narrow `section.ts` + snapshot
5. Tests `t6-clarify.test.mjs`; update t2/t3/t5 tool-count; T3 ddd deny still green
6. README mention `sbtd_clarify` (keep host pin / 0.1.0-rc.1)
7. `docs/TODO.md` T6 in progress + changelog 2026-09-07 + live main SHA `ba72c75`
8. Verify: `biome check src`; `tsc --noEmit`; build; `node --test test/*.test.mjs`
9. PR; set-branch / pr_url; do not finish-work; do not merge

## Validation

```bash
pnpm --filter @kunolu/dsh-sbtd lint
pnpm --filter @kunolu/dsh-sbtd typecheck
pnpm --filter @kunolu/dsh-sbtd build
pnpm --filter @kunolu/dsh-sbtd test
```

## Fence

No T7/T8, FU3, hooks rewrite, CONTEXT/ADR, omp settings, publish, host retarget, `/review`, merge.
