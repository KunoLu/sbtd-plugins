# dsh-sbtd T15 /sbtd command README

## Goal

Implement human `/sbtd`, `/sbtd plan`, and `/sbtd maestro` on DSH `ctx.commands` (scheme A). Locks Q1A–Q6A. Package README only for docs.

## Requirements

- **Q1A** — Only three literals: bare `/sbtd`, `/sbtd plan`, `/sbtd maestro`. Not a model tool. No validate/e2e/lessons subcommands.
- **Q2A** — Bare `/sbtd` is read-only status: print current Book Gate Plan or no-plan plus maestro missing summary. No install side effects.
- **Q3A** — `/sbtd plan` is a human view of session plan state (if none, say so; do not invent). `/sbtd maestro` reuses T12 `preflight()` (approval-first; no silent install). Do not rewrite T2/T12.
- **Q4A** — `inject` adds `commands`; `apply()` calls `registerCommand`; human-only `ctx.commands`; reads host/session; forbid model-passed `cwd`/`mcp`; host pin `@deepseek-ai/dsh@0.1.1-rc.2`.
- **Q5A** — Update `packages/dsh-sbtd/README.md` only (install `@next`, pin dsh rc.2, 640-skills relationship, non-goals, MCP optional, `/sbtd` usage).
- **Q6A** — Fence: `registerCommand` + command module + `t15-*.test.mjs` + package README. Consume plan state / maestro preflight as-is. Do not rewrite hooks/tools/backends. No npm.

## Acceptance Criteria

- [x] Q1A–Q6A locks satisfied
- [x] R1–R4 REQUIRED_CHANGES closed
- [x] Review r4 CLEAN @ `8b61d5d` (`/workspace/omp-tasks/t15-pr62-review-r4.md`)
- [x] `/trellis:finish-work` (archive after r4 record)
- [ ] PR #62 merge to `main`

## Notes

- r2 @ `b7d346b` and premature finish-work @ `5670f14` are stale/reverted — do not credit.
- DDD confirmed in `/workspace/omp-tasks/t15-sbtd-command-ddd.md`.
