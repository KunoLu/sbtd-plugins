# PRD -- dsh-sbtd T12 Maestro precheck grill

## Background

Grill-only Round 1 of grill-with-docs for T12 Maestro 预检 (`backends/maestro.ts`). ROUND1_COMPLETE (LIVE). Locks Q1A–Q6A later confirmed by DDD. Evidence: `/workspace/omp-tasks/t12-maestro-precheck-grill.md`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/t12-maestro-preflight`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/55
- Grill-only: product forks. Implementation lives in the sibling ddd/coding task.

## Locked Q1-Q6 (user + group; not recommendations)

| Q | Lock | One-line |
|---|---|---|
| Q1 | A | Hybrid six-step: live 1–3; declared 4–6; envelope lastPreflight/missing/guidance/probes?; never `maestro test` |
| Q2 | A | Backend-only `maestro.ts` + tests; no `apply()` registration; T13 mounts `sbtd_e2e` |
| Q3 | A | `preflight()` may write `session.maestro`; T13 must call+stop if not ok; validate/bdd do not; no flow |
| Q4 | A | Host cwd; model `platform` hint only; identity/env/accounts user-confirmed; T10 keys + silent install forbidden |
| Q5 | A | Fence maestro.ts+tests; no manuals; no apply e2e; tests stub detect |
| Q6 | A | Cloud first-class step 3 by declaration; no cloud run/upload |

## Non-goals

- Grill turn did not implement
- T13 generate/run/reports; Playwright web; manuals embed
- MCP / omp config / npm / host retarget / docs/prd rewrite

## Acceptance

- [x] Round 1 grill complete (6 independent questions, LIVE)
- [x] Q1A–Q6A locked (user + group)
- [x] No production code in the grill turn
- [x] Sibling DDD Status **confirmed**
- [x] Scheme A coding PR #55 tip `a42ca4c0107e07001c4fd4364aa1e6009783c8a4`; Combined r3 CLEAN; Main+Pr55R3Reviewer+advisor CONTENT CLEAN; REQUIRED_CHANGES=none
- [x] tests: 17/17 t12-maestro
- [x] locks Q1A Q2A Q3A Q4A Q5A Q6A

## Closeout

Scheme A finish on #55. Archive with the ddd sibling. `docs/TODO.md` merge-SHA backfill is a post-squash chore if still pending.
