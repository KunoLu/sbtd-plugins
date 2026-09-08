## LESSON-20260903-t4-manuals-copy-whitelist: T4 manuals copy only SKILL.md and references/

- Date: 2026-09-03
- Tags: dsh-sbtd, t4, manuals, sync-manuals
- Applicable scenarios: Syncing 640-skills whitelist into `packages/dsh-sbtd/manuals/`
- Severity: medium
- Source: `feat/dsh-sbtd-t4` HEAD `fba44da` copied `domain-modeling/ADR-FORMAT.md` and `CONTEXT-FORMAT.md`; `e01643c` reintroduced skill-root markdown except README.md
- Problem: T4 manuals tree included skill-root markdown and MANIFEST entries that are not `SKILL.md` or `references/`.
- Root cause: Copy policy treated skill-root `*.md` as templates instead of the locked whitelist (`SKILL.md` + optional `references/` only). Tests that required those files let the regression land.
- Fix: `scripts/sync-manuals.sh` copies only `SKILL.md` and `references/` via pin-SHA git blobs; MANIFEST records `sourcePath`, `sha256`, `sourceRevision`; dest sha256 must equal source sha256 or exit 1.
- Prevention: Tests must assert every MANIFEST file sha256 matches dest, reject ADR-FORMAT.md / CONTEXT-FORMAT.md / agents/, and walk `packages/dsh-sbtd` skipping `node_modules` and `dist` for no `install.sh`.

## LESSON-20260908-book-gate-before-first-edit: Persist Legacy/Refactoring reviews before first behavior edit

- Date: 2026-09-08
- Tags: dsh-sbtd, book-gate, legacy, refactoring, trellis, fu3
- Applicable scenarios: When `book-legacy-change-safety` and/or `book-refactoring-pass` are required for a task that will edit existing production code
- Severity: high
- Source: FU3 PR #43 r3; `09-08-dsh-sbtd-fu3-multi-fact-persist/implement.md` Timing breach; owner=640 exception
- Problem: Feature commits edited `plan.ts` while written Legacy/Refactoring reviews were persisted after both feature commits. Retrospective analysis then labeled the gates `passed`.
- Root cause: Treating a later favorable written review as if it closed a mandatory before-first-edit gate. Original order was not compliant.
- Fix: Owner=640 accepted an exception for this FU3 PR only. Gates keep the timing-breach admission. Retrospective `characterized`/`proceed` does not rewrite history into compliance.
- Prevention: Persist Legacy/Refactoring written reviews **before** the first behavior-changing edit when those gates are required. Retrospective favorable analysis does not close a mandatory before-first-edit gate.
