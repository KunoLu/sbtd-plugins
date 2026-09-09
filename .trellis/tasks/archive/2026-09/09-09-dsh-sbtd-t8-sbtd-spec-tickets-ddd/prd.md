# PRD -- dsh-sbtd T8 sbtd_spec / sbtd_tickets

## Background

T8 delivers model-facing tools `sbtd_spec` / `sbtd_tickets` that persist PRD/slices through the T7 Trellis Backend. DDD Status **confirmed** (`/workspace/omp-tasks/t8-sbtd-spec-tickets-ddd.md`). Grill ROUND1_COMPLETE with Q1C–Q6A locked.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t8-spec-tickets`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/47
- Fence Q5A: `src/tools/spec.ts` + `tickets.ts` + shared `task-artifact.ts` + `apply()` register both + tests/features. Consume T7. No extra `sbtd_*`. No `docs/prd` rewrite. No T7 reopen.

## Locked Q1-Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | C | Explicit `task` preferred; else derive safe slug from `currentTask` pointer (strip `.trellis/tasks/`). Invalid pointer ⇒ Q6A draft |
| Q2 | A | Same as T6 Complete: `ddd.requirement=required` ∧ `reviewStatus≠confirmed` ⇒ refuse write, `blocked.kind=ddd-unconfirmed` (not host ask) |
| Q3 | A | Draft-only iff `detect.exists=false`. `cliOnPath` / `workflowPresent` do not flip write vs draft. Never write `docs/` |
| Q4 | A | `sbtd_spec` writes only `prd.md`. `sbtd_tickets` writes only `implement.md` in the same task dir (markdown slices, not child tasks) |
| Q5 | A | Add `spec.ts` + `tickets.ts` and register both from `apply()`. Import T7 backend. No extra `sbtd_*`. No `docs/prd` rewrite |
| Q6 | A | Undetermined task path ⇒ markdown draft + structured note, no disk, no throw |

## Non-goals

- T7 API / whitelist / throw-vs-structured reopen
- Channel / trellis init / GitHub-Linear / child `task.py` create
- omp config / providers / registry publish
- host pin retarget
- `docs/prd` rewrite (design §6.2 parent/child wording remains docs debt)

## Acceptance

- [x] Explicit `task` wins over differing `currentTask` pointer
- [x] No explicit task + ok pointer ⇒ write under derived slug
- [x] Invalid/missing pointer + no explicit task ⇒ draft, no disk, no throw
- [x] `exists=false` ⇒ draft; never `docs/`; `exists=true` with `cliOnPath=false` still writes
- [x] Required DDD unconfirmed ⇒ `ok:false` `mode:blocked` `blocked.kind=ddd-unconfirmed`; on-demand/absent ddd does not refuse
- [x] `sbtd_spec` writes only `prd.md`; `sbtd_tickets` writes only `implement.md`; no `design.md` / child dirs
- [x] Both tools registered from `apply()`
- [x] Empty/whitespace markdown/body throws before persistence; existing artifact bytes unchanged
- [x] Persistent BDD `features/t8-sbtd-spec-tickets.feature`
- [x] No extra `sbtd_*` / no docs/prd / host pin unchanged
- [x] PR #47 tip `3fd773f`; review r3 CLEAN REQUIRED_CHANGES=none; Quality=pass; Security=pass
- [x] tests 150/150 (lint/typecheck/build/test green)

## Closeout

Scheme A finish on #47. Archive this task with the grill sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
