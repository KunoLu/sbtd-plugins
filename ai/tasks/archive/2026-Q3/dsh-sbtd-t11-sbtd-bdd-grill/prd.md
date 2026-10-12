# PRD -- dsh-sbtd T11 sbtd_bdd grill

## Background

Grill-only Round 1 of grill-with-docs for T11 `sbtd_bdd`. ROUND1_COMPLETE (LIVE). Locks Q1C–Q6A later confirmed by DDD. Evidence: `/workspace/omp-tasks/t11-sbtd-bdd-grill.md`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t11-sbtd-bdd`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/53
- Grill-only artifact: product forks only. Implementation lives in the sibling ddd/coding task.

## Locked Q1-Q6 (user + group; not recommendations)

| Q | Lock | One-line |
|---|---|---|
| Q1 | C | Model-visible: `intent` + capability slug or cwd-relative feature path; optional user-supplied extra repo paths for sync/read only. Host injects cwd / feature-root. Extra paths never invented; required-and-absent ⇒ blocked. T10 keys forbidden as model args |
| Q2 | B | Project conventions win (existing `.feature` / `features/` / BDD runner). AGENTS defaults only when none exist. Plugin fixtures are not a consumer second SoT |
| Q3 | A | Ship `bdd.ts` and `registerBddTool` from `apply()` this T11 |
| Q4 | A | Ordering/docs only: `.feature` before implement; spec/tickets never override `.feature`. No validate.ts change |
| Q5 | A | `read` = local catalog; Mutation none. No knowledge-server productization |
| Q6 | A | Fence = `bdd.ts` + tests + `apply()` registration. No manuals/gherkin-bdd. No `session.bdd` |

## Non-goals

- Grill turn itself did not implement
- T12/T13 Maestro/e2e; knowledge-base-integration productization
- Channel / trellis init / MCP config writes
- omp config / providers / registry publish
- host pin retarget
- T7/T8/T9/T10 reopen / `docs/prd` rewrite

## Acceptance

- [x] Round 1 grill complete (6 independent questions, LIVE)
- [x] Q1C–Q6A locked (user + group)
- [x] No production code in the grill turn
- [x] Sibling DDD Status **confirmed**
- [x] Scheme A coding PR #53 tip `975d878220e67a0a3b79f85461565079ee2edbc4`; Combined r5 CLEAN; Main+Pr53R5Reviewer CLEAN/correct; Advisor no content verdict (CLEAN ≠ advisor approval); REQUIRED_CHANGES=none
- [x] tests: 228/228 green (per r5)
- [x] locks Q1C Q2B Q3A Q4A Q5A Q6A

## Closeout

Scheme A finish on #53. Archive this grill task with the ddd sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
