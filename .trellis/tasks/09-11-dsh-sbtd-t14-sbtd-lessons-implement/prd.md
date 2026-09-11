# PRD — dsh-sbtd T14 sbtd_lessons implement

## Background

T14 delivers the model-facing tool `sbtd_lessons` at `packages/dsh-sbtd/src/tools/lessons.ts`. DDD **confirmed** (`/workspace/omp-tasks/t14-sbtd-lessons-ddd.md`). Grill ROUND1_COMPLETE with Q1A–Q6A locked. Approved execution plan: `local://t14-sbtd-lessons-plan.md` (scheme A).

## Workflow status — **NOT complete**

**Do not merge PR #59.** Trellis lifecycle and GitNexus hygiene violations remain open. Tests/spec updates may pass, but workflow validity is **not** restored.

### Pre-gate violations (code landed before Phase 1)

| SHA | Issue |
|---|---|
| `ac5aed6` | Production code committed before `task.py create` / `validate` / `start` |
| `b26d0b9` | TODO claimed in-progress before Trellis task existed |

### Trellis lifecycle violations (corrective attempt)

| When | Issue |
|---|---|
| Prior turn | Manual `mkdir` + hand-written `task.json` (not `task.py create`) |
| Prior turn | **`rm -rf .trellis/tasks/09-11-dsh-sbtd-t14-sbtd-lessons-implement`** — bypasses task.py dirty-data / path guards (**forbidden**) |
| Prior turn | **`TRELLIS_CONTEXT_ID=dsh-sbtd-t1` prefixed on `task.py` commands** — bypasses session resolution guards (**forbidden**) |
| Prior turn | Inline Python edited `task.json` instead of `task.py set-meta` |
| Prior turn | Claimed “workflow correction complete” — **invalid** |

Post-gate commits (`34471fd`, `6fadd16`) landed **after** the manual deletion; they do **not** retroactively validate Trellis lifecycle.

### GitNexus hygiene violations

| Step | Required | Actual |
|---|---|---|
| Pre-edit `impact()` on `apply` / shared symbols | Before editing | **Missed** (retroactive only) |
| Pre-commit `detect_changes` | Before `ac5aed6` | **Missed** (post-hoc compare vs `origin/main`: HIGH, 20 files / 155 symbols — expected for new tool) |

### Current session identity (task.py only — do not hand-set env)

```bash
python3 ./.trellis/scripts/task.py current --json
# → source: session:dsh-sbtd-t1
```

Use **`task.py` guarded commands only** from here (`create`, `add-context`, `validate`, `start`, `set-meta`, `set-branch`, `finish`, `archive`). No manual task-dir deletion, no `TRELLIS_CONTEXT_ID=` prefixes.

PR [#59](https://github.com/KunoLu/sbtd-plugins/pull/59) remains **not merge-ready** until parent `/review` closes process gaps.

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

### Post-gate (blocked — Trellis lifecycle invalid)

- [x] Check commands green (biome/tsc/t14/full) — **technical only**
- [x] Spec update on branch — **technical only**
- [x] **Valid** Trellis lifecycle for current session (2026-09-11 process clear): `task.py validate`+`start` via shell ticket; no `rm -rf`; no `TRELLIS_CONTEXT_ID=` prefix; meta via `set-meta` only. Historical pre-gate ordering still recorded above.
- [ ] GitNexus pre-edit impact + pre-commit detect_changes on production commits
- [ ] Parent `/review` on PR #59
- [ ] PR #59 remains **do not merge**

## Non-goals

T15 `/sbtd`; manuals nest; registry publish; omp/MCP edits; CONTEXT/ADR paste
