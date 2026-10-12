# dsh CI compat guides follow-ups / residuals

Head at finish: r2 CLEAN `d6ff5385c67d20ad49876739d4b7d4ad86fb9f36`.
Review: `/workspace/omp-tasks/dsh-pr68-review-r2-extract.md`.
PR: https://github.com/KunoLu/sbtd-plugins/pull/68

## Residual — parked (non-blocking)

- README / host guide still say 拟议独立 Actions though YAML is in-tree; drop 拟 after merge so the index is not stale.
- `ci-640-skills-adapt.md` 故障排查 still says keep `workflow_dispatch` if GitHub cannot clone 640-skills; locked YAML already has `pull_request` paths.

## Not in this PR

- No npm publish; host pin `@deepseek-ai/dsh@0.1.1-rc.2`; package `0.1.0-rc.1`
- No omp config / MCP / `omp-compatibility-*` edits
- TODO merge-SHA backfill via post-squash tip chore `chore/todo-dsh-ci-docs-done`
