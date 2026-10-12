# T15 implement follow-ups / residuals

Head at finish: r5 CLEAN `3529daf9e6660c302c37973f9f332dafc56aa171`. Product fence unchanged since `f8561bf`. Process r4b @ `70d3a60`; r4 security @ `8b61d5d`.

## Residual -- parked (non-blocking)

- Optional r1 `formatMissing(undefined)` currently renders none; a future change could distinguish “preflight has never run” from a completed preflight with an empty missing list. Not required for merge.
- T16 端到端验收

## Not in this PR

- No npm publish; host pin `@deepseek-ai/dsh@0.1.1-rc.2` unchanged
- No rewrite of hooks/tools/backends
- TODO merge-SHA backfill via post-squash tip chore `chore/todo-t15-done`
