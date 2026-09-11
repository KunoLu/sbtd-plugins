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
- [x] Review r3b CLEAN @ `f8561bf` (`/workspace/omp-tasks/t15-pr62-review-r3b.md`; T15QualityR3b pass)
- [ ] Review r4 process commits (pending after artifact fix)
- [ ] `/trellis:finish-work` (after r4 CLEAN)
- [ ] PR #62 merge to `main`

## Notes

- r2 @ `b7d346b`, premature archives @ `5670f14`/`7f273d7`, `/workspace/omp-tasks/t15-pr62-review-r3.md`, `/workspace/omp-tasks/t15-pr62-review-r4.md` are void — do not credit.
- T15QualityR3 **blocked** (stale GitNexus); only T15QualityR3b pass counts for product.
- DDD confirmed in `/workspace/omp-tasks/t15-sbtd-command-ddd.md`.
