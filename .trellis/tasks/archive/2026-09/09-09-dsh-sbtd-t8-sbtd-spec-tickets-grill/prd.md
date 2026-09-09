# PRD -- dsh-sbtd T8 sbtd_spec / sbtd_tickets grill

## Background

Grill-only Round 1 of grill-with-docs for T8 model-facing tools `sbtd_spec` / `sbtd_tickets`. ROUND1_COMPLETE. Locks Q1C–Q6A later confirmed by DDD. Evidence: `/workspace/omp-tasks/t8-sbtd-spec-tickets-grill.md`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t8-spec-tickets`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/47
- Grill-only artifact: product forks only. Implementation lives in the sibling ddd/coding task.

## Locked Q1-Q6 (user + group; not recommendations)

| Q | Lock | One-line |
|---|---|---|
| Q1 | C | Explicit `task` preferred; else derive slug from `currentTask` pointer (strip `.trellis/tasks/`) |
| Q2 | A | `ddd.requirement=required` ∧ `reviewStatus≠confirmed` ⇒ refuse write, `blocked.kind=ddd-unconfirmed` |
| Q3 | A | Draft-only iff `detect.exists=false`; never write `docs/`; CLI/workflow do not flip |
| Q4 | A | `sbtd_spec` → `prd.md` only; `sbtd_tickets` → `implement.md` only (same dir; not child tasks) |
| Q5 | A | Add + register both tools from `apply()`; consume T7; no extra `sbtd_*`; no `docs/prd` rewrite |
| Q6 | A | Undetermined path ⇒ markdown draft + structured note; no disk; no throw |

## Non-goals

- Grill turn itself did not implement
- Channel / trellis init / GitHub-Linear
- omp config / providers / registry publish
- host pin retarget
- T7 API reopen

## Acceptance

- [x] Round 1 grill complete (6 independent questions)
- [x] Q1C–Q6A locked (user + group)
- [x] No production code in the grill turn
- [x] Sibling DDD Status **confirmed**
- [x] Scheme A coding PR #47 tip `3fd773f`; review r3 CLEAN; tests 150/150

## Closeout

Scheme A finish on #47. Archive this grill task with the ddd sibling.
