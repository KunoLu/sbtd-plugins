# FU3 follow-ups / locks (post-r2)

## Q4B re-lock (group+user, Locked A)

Original Q4B text read as “exactly two commits”. **Re-lock:** two *ordered feature* commits remain required —

1. persist-across-replans sticky Forced Docs DDD
2. multi-fact matching-set identity

— and **docs / review / fix** additional commits are permitted (honest Codex fix trail; tip includes `b33641f` canonicalize legacy DDD alias facts). **Do not rewrite history** to squash.

## Q1D alias scope (post-r2 artifact alignment)

Alias collapse is **DDD-only** (three grill-with-docs language rows → `完整执行 grill-with-docs`). persist/持久化 and schema/数据库 are **not** one identity; distinct ddia/legacy/release catalog rows stay distinct; set-expansion resets.

## Tip verify (post-`b33641f`)

Recorded on tip `b33641f97f15d694ebe29ecfe740ad9d5e550839` in `packages/dsh-sbtd`:

- `biome check src` pass
- `tsc --noEmit` pass
- `tsc` build pass
- `node --test test/*.test.mjs` **116/116**

No production logic change in the docs/verify follow-up.

## Owner exception — Book-gate Legacy/Refactoring order (r3)

Accountable owner: **640**. Exception accepted for this FU3 PR (#43) only.

Original order was **not** compliant: feature commits edited `packages/dsh-sbtd/src/tools/plan.ts` while written `book-legacy-change-safety` / `book-refactoring-pass` reviews were persisted **after** both feature commits (admitted in `implement.md` Timing breach).

Gates remain labeled `passed` with that honest timing-breach admission. `passed` after retrospective characterization is **not** a substitute for mandatory before-first-edit compliance.

Prevention: persist Legacy/Refactoring written reviews **before** the first behavior edit when those gates are required. See `.trellis/lessons/topics/dsh-sbtd.md` `LESSON-20260908-book-gate-before-first-edit`.

## r4 P2 — bind docs Complete to taskId

Quality r4 P2: `keepForcedDocsDdd` requires `clarifyCompleteTaskId` to match the live plan. docs Complete writes the field; Interview Reset and empty restore delete it.

Production tip: `d2194f5229e6f8b08fef3a6a69f9e8e3a41c9ba1`

Validation in `packages/dsh-sbtd` at that tip:

- `biome check src` pass
- `tsc --noEmit` pass
- `tsc` build pass
- `node --test test/*.test.mjs` **121/121**

GitNexus `detect_changes` scope=all: `risk_level=high` (stale index + touched `sbtdPlan`/`sbtdClarify`). Cross-check: only the bind field and sticky guard; `hooks.ts` untouched; Q3A Gate-only T3 deny preserved.

`rtk`: fallback-native (`rtk` not found).


