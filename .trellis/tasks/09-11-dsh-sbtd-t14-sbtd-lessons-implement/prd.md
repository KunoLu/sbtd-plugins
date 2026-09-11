# PRD — dsh-sbtd T14 sbtd_lessons implement

## Background

T14 delivers the model-facing tool `sbtd_lessons` at `packages/dsh-sbtd/src/tools/lessons.ts`. DDD **confirmed** (`/workspace/omp-tasks/t14-sbtd-lessons-ddd.md`). Grill ROUND1_COMPLETE with Q1A–Q6A locked. Approved execution plan: `local://t14-sbtd-lessons-plan.md` (scheme A).

## Workflow correction

Implementation commits landed **before** this Trellis task existed (manual task dir + out-of-order coding). Those commits are **pre-gate work** — not workflow-complete until this task passes Phase 2 check and Phase 3 spec-update gates.

| SHA | Role |
|---|---|
| `ac5aed6` | **Pre-gate** — feat(dsh-sbtd): T14 sbtd_lessons (scheme A) |
| `b26d0b9` | **Pre-gate** — docs: TODO sync T14 #59 in progress |

PR [#59](https://github.com/KunoLu/sbtd-plugins/pull/59) is **not merge-ready** and **not workflow-valid** until post-gate commit lands on branch.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/t14-sbtd-lessons`
- Fence Q5A: `lessons.ts` + `registerLessonsTool` + `t14-lessons.test.mjs` (+ tools.length whitelist + optional `docs/TODO.md`). No trellis/e2e/maestro/validate/bdd/gitnexus rewrite.

## Locked Q1–Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | A | `record\|match\|read` + five events; ordinary/unknown `record` → skipped, no write |
| Q2 | A | `registerLessonsTool` from `apply()`; manuals nest deferred |
| Q3 | A | Trellis → topic+index; no root `lessons.md`; no `writeArtifact`; no `trellis init` |
| Q4 | A | Model: intent/event/summary/tags/topic; host cwd + T7 `detect`; forbid T10 keys |
| Q5 | A | Fence lessons.ts + apply + t14 tests only |
| Q6 | A | match/read on-demand; no GitNexus inside lessons |

## Acceptance criteria

### Pre-gate (already on branch — verify only)

- [ ] `lessons.ts` implements record/match/read per Q1A–Q6A
- [ ] `apply()` registers `sbtd_lessons` after `sbtd_e2e` (`tools.length === 9`)
- [ ] `test/t14-lessons.test.mjs` covers DDD §7 angles
- [ ] Full package tests green
- [ ] Forbidden files untouched in diff vs `origin/main`

### Post-gate (this task must produce)

- [ ] Trellis task created via `task.py create` (not manual mkdir)
- [ ] `design.md` + `implement.md` + curated `implement.jsonl` / `check.jsonl`
- [ ] `task.py validate` + `task.py start` before treating code as gated
- [ ] `trellis-check` equivalent: biome + tsc + t14 + full test suite green
- [ ] `trellis-update-spec`: `.trellis/spec/dsh-sbtd/backend/index.md` documents T14
- [ ] Post-gate commit on branch documenting gate completion
- [ ] PR #59 remains **do not merge** until parent `/review`

## Non-goals

T15 `/sbtd`; manuals nest; registry publish; omp/MCP edits; CONTEXT/ADR paste
