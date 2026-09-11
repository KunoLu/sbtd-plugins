# Design — T14 sbtd_lessons

## Modules

- `packages/dsh-sbtd/src/tools/lessons.ts` — `sbtdLessons` / `registerLessonsTool` / `resolveLessonsHost` / `pickLessonsInput`
- `packages/dsh-sbtd/src/index.ts` — `registerLessonsTool(ctx, resolveLessonsHost(ctx))` after `registerE2eTool`
- `packages/dsh-sbtd/test/t14-lessons.test.mjs` — unit tests (temp dirs only)
- `packages/dsh-sbtd/src/backends/trellis.ts` — **consume** `detect()` only; no edits

## Decisions (locked Q1A–Q6A)

1. **Q1A** — Three intents; five event kinds; ordinary/unknown record refused with no file.
2. **Q2A** — apply register; manuals nest deferred.
3. **Q3A** — Trellis present (`detect().exists || detect().workflowPresent`) → `.trellis/lessons/topics/<topic>.md` + `index.md`; no Trellis → `docs/lessons.md` or layered `docs/lessons/` when index exists; never root `lessons.md`; never `writeArtifact`.
4. **Q4A** — Model schema vs host cwd; T10 trust keys throw on pick.
5. **Q5A** — Fence: lessons.ts + apply + t14 tests; no backend rewrites.
6. **Q6A** — match/read filter index rows only; never enumerate topics/archive; no GitNexus import.

## Store layout

| Trellis | Index | Body |
|---|---|---|
| present | `.trellis/lessons/index.md` | `.trellis/lessons/topics/<topic>.md` |
| absent, layered | `docs/lessons/index.md` | `docs/lessons/topics/<topic>.md` |
| absent, flat | — | `docs/lessons.md` |

LESSON id: `LESSON-YYYYMMDD-<topic>`; duplicate same day → `-2`, `-3` from index rows.

## Pre-gate delivery note

Source files above were committed in `ac5aed6` before Trellis Phase 1 completed. This design doc retroactively records the boundary; no redesign unless check gate fails.
