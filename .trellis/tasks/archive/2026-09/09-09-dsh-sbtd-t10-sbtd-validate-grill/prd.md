# PRD -- dsh-sbtd T10 sbtd_validate grill

## Background

Grill-only Round 1 of grill-with-docs for T10 `sbtd_validate`. ROUND1_COMPLETE (LIVE). Locks Q1A–Q5A later confirmed by DDD. Evidence: `/workspace/omp-tasks/t10-sbtd-validate-grill.md`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t10-sbtd-validate`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/51
- Grill-only artifact: product forks only. Implementation lives in the sibling ddd/coding task.

## Locked Q1-Q5 (user + group; not recommendations)

| Q | Lock | One-line |
|---|---|---|
| Q1 | A | Model may pass `phase` plus optional `target` / `direction` / `scope` only. Host injects `cwd` and all `GitNexusOptions`. Model cannot supply `cwd` / `mcp` / `runRefresh` / `serverName` / `toolNames` |
| Q2 | A | `pre`: T9 `impact` only (skip if T9 skipped / missing target). `post`: `detectChanges` then project tests. Missing GitNexus does not omit tests |
| Q3 | A | GitNexus skipped/advisory never sets `validate.post=blocked`. Post tests still run. `post=blocked` only if tests fail. Advisory is printed, not a session block |
| Q3 clar. | LOCK | `skipped` → `validate.pre="skipped"`; `ok` or `advisory` → `validate.pre="done"` |
| Q4 | A | Return `{ phase, gitnexus, tests?, validate }`. No test script ⇒ skipped/not-applicable + residual risk, never fake passed. Failed tests ⇒ `post=blocked` |
| Q5 | A | `validate.ts` + `registerValidateTool` from `apply()`. Import T9 `gitnexus.ts` as-is. No gitnexus rewrite, no docs/prd rewrite, no MCP/omp/npm |

## Non-goals

- Grill turn itself did not implement
- T9 `gitnexus.ts` rewrite / T9 r2 residuals
- Channel / trellis init / MCP config writes
- omp config / providers / registry publish
- host pin retarget
- T7/T8/T9 reopen / `docs/prd` rewrite

## Acceptance

- [x] Round 1 grill complete (5 independent questions, LIVE)
- [x] Q1A–Q5A locked (user + group) including Q3 clarification
- [x] No production code in the grill turn
- [x] Sibling DDD Status **confirmed**
- [x] Scheme A coding PR #51 tip `7a660af`; review r4 CLEAN; Quality=pass (0.98); Security=pass; Advisor CLEAN; REQUIRED_CHANGES=none

## Closeout

Scheme A finish on #51. Archive this grill task with the ddd sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
