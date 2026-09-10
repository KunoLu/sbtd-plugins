# PRD -- dsh-sbtd T13 sbtd_e2e grill

## Background

Grill-only Round 1 of grill-with-docs for T13 `sbtd_e2e` (`src/tools/e2e.ts`). ROUND1_COMPLETE (LIVE). Locks Q1B–Q6A later confirmed by DDD. Evidence: `/workspace/omp-tasks/t13-sbtd-e2e-grill.md`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/t13-sbtd-e2e`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/57
- Grill-only: product forks. Implementation lives in the sibling ddd/coding task.

## Locked Q1-Q6 (user + group; not recommendations)

| Q | Lock | One-line |
|---|---|---|
| Q1 | B | Three actions; hybrid = 混合 App device-side Maestro, not serial Playwright+Maestro; mobile\|hybrid generate/run re-call T12; web skips T12 |
| Q2 | A | `apply()` `registerE2eTool`; manuals nest deferred |
| Q3 | A | Existing project dirs win; unit tests never spawn maestro/browser; fixture smoke live/验收 only |
| Q4 | A | Model: surface/action/optional relative path·slug/optional platform; Host: cwd+T12 facts+binaries+browser lock+creds; forbid T10 keys |
| Q5 | A | Fence e2e.ts + apply + t13-e2e tests; do not rewrite maestro.ts; no npm |
| Q6 | A | blocked=did not start; failed=ran and lost; skipped-by-user; mode labels; mock≠full-stack; never steal controller |

## Non-goals

- Grill turn did not implement
- T14 lessons; manuals nest; npm; omp/MCP; host retarget; docs/prd rewrite; maestro.ts rewrite

## Acceptance

- [x] Round 1 grill complete (6 independent questions, LIVE)
- [x] Q1B–Q6A locked (user + group)
- [x] No production code in the grill turn
- [x] Sibling DDD Status **confirmed**
- [x] Scheme A coding PR #57 tip `194a6620d8fbe501963b2b341d514944428bd6a3`; Combined r5 CLEAN; Main+Pr57R5Reviewer+advisor CONTENT CLEAN; REQUIRED_CHANGES=none
- [x] tests: t13-e2e (19+ through r1–r4; tip includes R2 anchored tests)
- [x] locks Q1B Q2A Q3A Q4A Q5A Q6A

## Closeout

Scheme A finish on #57. Archive with the ddd sibling. `docs/TODO.md` merge-SHA backfill is a post-squash chore if still pending.
