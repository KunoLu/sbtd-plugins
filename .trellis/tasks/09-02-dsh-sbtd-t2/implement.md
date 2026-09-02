# T2 implement

## Order

1. Restrict `PREDICATES.ddd` to completed / 完整执行 / full `grill-with-docs`. Bare `ddd` stays on-demand. Do not treat “after grill-with-docs” as completion.
2. Keep `registerPlanTool` from `apply()`. Local ParameterSchemaSpec rc.2. No `@deepseek-ai/dsh` imports. No hooks / other tools / fs / `AGENTS.md`.
3. README already mentions `sbtd_plan`; keep unpublished warning + pin `0.1.1-rc.2` + `@next`. No path install. No root README.
4. Tests: `test/t2-plan.test.mjs` vs `dist/` after `tsc`. Cover isolation, predicates (including bare ddd), passed keep/reset, new taskId, empty summary, restore hydrate / empty snapshot (do not rework `restore`), apply register + schema, README. T0/T1 apply tests stub `tools.register`.
5. Feature: `features/t2-sbtd-plan.feature`.
6. `.trellis/spec/dsh-sbtd/backend` layout already lists `src/tools/plan.ts`.
7. Validate: lint, typecheck, build, test.

## Validation

```bash
# packages/dsh-sbtd
biome check src
tsc -p tsconfig.json --noEmit
tsc -p tsconfig.json
node --test test/*.test.mjs
```

Live `dsh plugin add` is not required (T0). Maestro / Playwright: not-needed.

Result (worktree `/workspace/sbtd-plugins-t2`): lint 0, typecheck 0, build 0, test 23 pass / 0 fail.
`rtk`: fallback-native (`rtk` not on PATH). `pnpm --filter` blocked on frozen lockfile vs peer `@deepseek-ai/dsh@0.1.1-rc.2`; ran package biome/tsc/node --test via the worktree pnpm store. GitNexus skipped (no `.gitnexus/`).

## Rollback

Revert `packages/dsh-sbtd` T2 files. Do not keep `dist/`. Do not publish.

## Gate reviews

```text
DDD Boundary Review
Status: not-required
Ubiquitous language: sbtd_plan; BookGatePlan; required/on-demand; GateState; objective predicate; completed grill-with-docs
Bounded contexts: dsh-sbtd plugin shell vs Trellis vs 640-skills. T2 stays in the plugin.
Invariants: DDD required only after completed grill-with-docs; bare ddd stays on-demand
Corrections to grill-with-docs: 未完整调用; PRD defaults recorded as Q1–Q20
Open conflicts: none
```

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: T1 in-process Map via getSession; T2 assigns session.plan only
Write / read / async / failure paths: sbtdPlan writes plan; no persist/cache/async/cross-service
Consistency model: single-process; same taskId merge; new taskId new plan
Required tests: isolation, passed keep/reset, new taskId, restore hydrate
```

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: DDD must not fire on bare ddd; only completed/full/完整执行 grill-with-docs
Behavior to preserve: name/inject; T0 log; section; T1 Map serialize/restore; no fs/AGENTS.md; no hooks; peer 0.1.1-rc.2; ParameterSchemaSpec rc.2
Current reproduction evidence: leftover PREDICATES.ddd included /\bddd\b/i
Safety net: t2-plan.test.mjs vs dist/; T0/T1 apply stubs tools.register
Validation plan: biome check src; tsc --noEmit; tsc; node --test test/*.test.mjs
Review mode: normal
```

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/src/tools/plan.ts PREDICATES.ddd
Behavior that must remain unchanged: session isolation; five gates; restore hydrate; apply register
Structural friction: none
Decision and smallest safe step: no extra refactor; delete non-completion DDD predicates
Safety net and validation: node:test + tsc
Deferred refactors: none
```

```text
Release Readiness Review
Status: not-required
Production path: none added (no service / API / job / deploy). Package remains private unpublished.
```

Q20: legacy and refactor are both required for this change. Order is a later task.
