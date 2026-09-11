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

- [x] Q1A: three literals only; not a model tool
- [x] Q2A: bare `/sbtd` read-only no-plan/plan + maestro missing; no install
- [x] Q3A: `/sbtd plan` view-only; `/sbtd maestro` calls T12 `preflight()`; no silent install
- [x] Q4A: `inject` includes `commands`; `registerCommand` in `apply()`; host-injected session; forbid model cwd/mcp; host pin rc.2
- [x] Q5A: package README updated only
- [x] Q6A: fence respected; no hooks/tools/backends rewrite
- [x] R1: `parseSbtdArgv` accepts only empty/`plan`/`maestro` rawInput (no command-name or leading-slash aliases, no trailing tokens)
- [x] R4: persistent `packages/dsh-sbtd/features/t15-sbtd-command.feature`
- [x] No npm publish
- [x] Review r2 CLEAN @ `b7d346b` (`/workspace/omp-tasks/t15-pr62-review-r2.md`)
- [ ] PR #62 merge / `/trellis:finish-work` (task stays `in_progress` until finish-work)

## Notes

- DDD confirmed in `/workspace/omp-tasks/t15-sbtd-command-ddd.md`.
- r1 review at `a83ffd07` was block / not CLEAN (Quality block, Security pass). R1–R4 fix pass addresses REQUIRED_CHANGES.
