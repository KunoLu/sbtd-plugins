# Implement — FU3 multi-fact + persist-across-replans

## Book Gate Plan

| Skill | Select | Hit fact | Stage | Gate state |
|---|---|---|---|---|
| book-ddd-distilled-modeling | on-demand | grill already confirmed; no new interview | — | not-required |
| book-ddia-data-design | on-demand | in-memory session `fact?: string`; no durable schema | — | not-required |
| book-legacy-change-safety | required | existing `mergeGate` demote write hole | before first behavior edit | planned |
| book-refactoring-pass | required | edit existing `plan.ts` | after legacy characterized | planned |
| book-release-readiness | required | `sbtd_plan` production tool | after validation | planned |

`grill-with-docs`: 未完整调用 — locked DDD already confirmed; implement-only turn.

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
