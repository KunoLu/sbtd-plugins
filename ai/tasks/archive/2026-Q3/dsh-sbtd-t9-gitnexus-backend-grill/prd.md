# PRD -- dsh-sbtd T9 GitNexus backend grill

## Background

Grill-only Round 1 of grill-with-docs for T9 GitNexus Backend Module. ROUND1_COMPLETE. Locks Q1B–Q6A later confirmed by DDD. Evidence: `/workspace/omp-tasks/t9-gitnexus-backend-grill.md`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t9-gitnexus-backend`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/49
- Grill-only artifact: product forks only. Implementation lives in the sibling ddd/coding task.

## Locked Q1-Q6 (user + group; not recommendations)

| Q | Lock | One-line |
|---|---|---|
| Q1 | B | `detect` = `{mcpVisible, indexPresent, stale}` independent; missing MCP does not flip `indexPresent`; never throws |
| Q2 | A | No MCP or no `.gitnexus/` ⇒ `skipped` (no throw). Stale after failed refresh ⇒ printable + `advisory:true`. Never hard-fail |
| Q3 | A | `impact(cwd, target, direction?)` / `detectChanges(cwd, scope?)` return `{ status, summary, advisory?, reason? }`; unavailable ⇒ `skipped`; never throw |
| Q4 | A | Best-effort in-process project refresh (`gitnexus analyze` / `run.cjs analyze` if present). Fail/timeout ⇒ `advisory:true`. Never write MCP config |
| Q5 | A | Deliver only `src/backends/gitnexus.ts` + module tests. No `apply()`, no `sbtd_validate`, no `docs/prd`, no MCP writes |
| Q6 | A | Read-only `serverName` (default `"gitnexus"`) → `mcp__<serverName>__*`; fallback `mcp__gitnexus__*`. Never write config |

## Non-goals

- Grill turn itself did not implement
- `index.ts` apply wiring / `sbtd_validate` / T10
- Channel / trellis init / MCP config writes
- omp config / providers / registry publish
- host pin retarget
- T7 API reopen / `docs/prd` rewrite

## Acceptance

- [x] Round 1 grill complete (6 independent questions)
- [x] Q1B–Q6A locked (user + group)
- [x] No production code in the grill turn
- [x] Sibling DDD Status **confirmed**
- [x] Scheme A coding PR #49 tip `df7abb2`; review r2 CLEAN; Quality=PASS; Security=pass; REQUIRED_CHANGES=none

## Closeout

Scheme A finish on #49. Archive this grill task with the ddd sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
