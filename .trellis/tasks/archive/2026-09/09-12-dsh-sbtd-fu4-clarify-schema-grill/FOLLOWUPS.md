# FU4 grill follow-ups / residuals

Head at finish: r3 CLEAN `ca9eb8fc79d31d8abd7bfc1096d1b8a713a3a025`.
Review: `/workspace/omp-tasks/fu4-pr65-review-r3-extract.md`.
PR: https://github.com/KunoLu/sbtd-plugins/pull/65

## Residual — parked (non-blocking)

- Q5A pending post-merge T16: rebuild tarball; re-run T16 from step 2. Do not rewrite `docs/acceptance.md`.
- Non-blocking review nits: `=== null` vs `!= null` in omit helpers; lone `node --test test/fu4-host-schema.test.mjs` without package `test` can load pre-existing `dist/`; t8 written-path does not assert `mode === "written"`.

## Not in this PR

- No npm publish; host pin `@deepseek-ai/dsh@0.1.1-rc.2`; package `0.1.0-rc.1`
- No merge of PR #64
- TODO merge-SHA backfill via post-squash tip chore `chore/todo-fu4-done`
