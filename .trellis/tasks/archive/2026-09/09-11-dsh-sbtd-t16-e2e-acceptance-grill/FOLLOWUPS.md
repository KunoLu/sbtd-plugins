# T16 grill follow-ups / residuals

Head at finish: r2 CLEAN `97e365cbbf34dac658af33dceaab6e325a9765a8`.
Review: `/workspace/omp-tasks/t16-pr64-review-r2-extract.md`.
PR: https://github.com/KunoLu/sbtd-plugins/pull/64

Under-test subject (acceptance): `98edd712efa46274fce7644b650937c9f5361929` (FU4 merged). PR tip also adds root `.gitignore` `*.tgz`. `docs/acceptance.md` blob unchanged from r1 `99a1c41`.

## Residual — parked (non-blocking)

- Optional later-docs naming: step 6 could also name `validate.post` / `phase=post`; step 7 could name `lastPreflight`/`outcome`. Same acceptance blob already passed r1/r2; not required for merge.
- Mac pack hash, live `dsh --version`, Bypass A UI, and 640-skills porcelain remain record-only (not recomputed in this Linux session).

## Not in this PR

- No npm publish; host pin `@deepseek-ai/dsh@0.1.1-rc.2`; package `0.1.0-rc.1`
- No product / tools / hooks / backends rewrite
- TODO merge-SHA backfill via post-squash tip chore `chore/todo-t16-done`
