# PRD -- dsh-sbtd T9 GitNexus backend

## Background

T9 delivers an internal GitNexus Backend Module at `packages/dsh-sbtd/src/backends/gitnexus.ts` for optional analysis primitives over MCP + `.gitnexus/`. DDD Status **confirmed** (`/workspace/omp-tasks/t9-gitnexus-backend-ddd.md`). Grill ROUND1_COMPLETE with Q1B–Q6A locked.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t9-gitnexus-backend`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/49
- Fence Q5A: **only** `src/backends/gitnexus.ts` + `test/t9-gitnexus.test.mjs`. No `index.ts` apply wiring, no `sbtd_validate`, no `docs/prd` rewrite, no MCP config edits.

## Locked Q1-Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | B | `detect` = `{mcpVisible, indexPresent, stale}` independent; missing MCP does not flip `indexPresent`; never throws |
| Q2 | A | No MCP or no `.gitnexus/` ⇒ `skipped` (no throw). Stale after failed refresh ⇒ printable + `advisory:true`. Never hard-fail |
| Q3 | A | `impact(cwd, target, direction?)` / `detectChanges(cwd, scope?)` return `{ status: "ok"\|"skipped"\|"advisory", summary, advisory?, reason? }`; unavailable ⇒ `skipped`; never throw |
| Q4 | A | Best-effort in-process project refresh (`gitnexus analyze --index-only` / `node .gitnexus/run.cjs analyze --index-only` if present). Fail/timeout ⇒ `advisory:true`. Never write MCP config |
| Q5 | A | `gitnexus.ts` + module tests only; no index apply; no `sbtd_validate`; no docs/prd; no MCP writes |
| Q6 | A | Read-only `serverName` (default `"gitnexus"`) → `mcp__<serverName>__*`; fallback `mcp__gitnexus__*`. Never write config |

## Non-goals

- index `apply()` / model-facing `sbtd_*` / T10 `sbtd_validate`
- Channel / `trellis init` / MCP config writes
- omp config / providers / registry publish
- host pin retarget
- T7 API reopen / `docs/prd` rewrite
- docs/TODO merge-SHA backfill (post-merge chore)

## Acceptance

- [x] `detect(cwd)` returns three independent booleans; never throws; missing MCP does not flip `indexPresent`
- [x] No MCP or no `.gitnexus/` ⇒ `impact` / `detectChanges` `status: "skipped"`, no throw
- [x] Stale after failed/timed-out refresh ⇒ printable summary + `advisory:true`, not skip
- [x] `impact` / `detectChanges` return locked `{ status, summary, advisory?, reason? }`
- [x] Refresh does not write MCP config
- [x] r1 REQUIRED closed in `df7abb2`: (1) `defaultRunRefresh` argv → `analyze --index-only` (CLI + `run.cjs`); (2) THIS-op MCP tool + `options.mcp` validate BEFORE `ensureRefreshIfStale`
- [x] Fence held: `packages/dsh-sbtd/src/backends/gitnexus.ts` + `packages/dsh-sbtd/test/t9-gitnexus.test.mjs` only
- [x] No extra `sbtd_*` / no docs/prd / host pin unchanged
- [x] PR #49 tip `df7abb2cf3bc8ef0a3cfc3532057ebe0f166082e`; review r2 CLEAN; Quality=PASS; Security=pass; Advisor weighed non-blocker; REQUIRED_CHANGES=none
- [x] locks Q1B Q2A Q3A Q4A Q5A Q6A

## Closeout

Scheme A finish on #49. Archive this task with the grill sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
