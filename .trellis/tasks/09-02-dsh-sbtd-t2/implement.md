# T2 implement

## Order

1. Add `packages/dsh-sbtd/features/t2-sbtd-plan.feature`.
2. Add `src/tools/plan.ts` (predicates, merge, markdown, register).
3. Wire `registerPlanTool` from `src/index.ts`. Keep name/inject. No fs.
4. README: T2 + `sbtd_plan`; keep unpublished warning + pin + `@next`.
5. Tests: t2-plan.test.mjs; t0/t1 apply mocks gain `tools.register`.
6. Update `.trellis/spec/dsh-sbtd/backend` layout.
7. Validate: lint, typecheck, build, test.

## Validation

```bash
# packages/dsh-sbtd
biome check src
tsc -p tsconfig.json --noEmit
tsc -p tsconfig.json
node --test test/*.test.mjs
```

## Gate reviews

```text
DDD Boundary Review
Status: confirmed
Ubiquitous language: sbtd_plan; BookGatePlan; required/on-demand; GateState; objective predicate
Bounded contexts: dsh-sbtd plugin shell vs Trellis vs 640-skills. T2 stays in the plugin.
Invariants: apply never writes AGENTS.md; required only from 3.4 predicates; sessions isolated
Corrections to grill-with-docs: skipped with PRD defaults; A1 keeps inject without agents
Open conflicts: none
```

```text
DDIA Data Design Review
Status: confirmed
Data owner: T1 in-process Map via getSession
Write path: sbtdPlan assigns session.plan
Consistency: single-process; same taskId merge
Required tests: isolation, predicate, passed keep/reset
```

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: apply registers sbtd_plan
Behavior to preserve: section, pin, unpublished README, no AGENTS.md, inject tools+systemPrompt
Safety net: t0/t1 updated mocks + t2 tests
```

```text
Refactoring Review
Status: proceed
Existing-code scope: src/index.ts apply()
No extra abstraction beyond plan.ts module
```

```text
Release Readiness Review
Status: ready
private true; peer 0.1.1-rc.2; tests on dist/; no publish
```
