# T3 implement

Grill PRD defaults. Q/A listed below.
Q1 host 0.1.1-rc.2
Q2 hooks.ts
Q3 pre-execute and pre-step
Q4 no plan src write ask sbtd_plan
Q5 README allow
Q6 required unpassed deny sbtd_review
Q7 legacy then refactor
Q8 ddia data-path only
Q9 release no edit block; deny publish bash
Q10 ddd blocks impl edits
Q11 exempt test features maestro trellis
Q12 write edit str_replace_editor bash
Q13 git commit allowed
Q14 rm pkg-mgr ask
Q15 T1 T2 session
Q16 no extra sbtd tools
Q17 no AGENTS.md no publish no trellis init --dsh
Q18 inject tools systemPrompt
Q19 allow via next()
Q20 cwd src app packages
Q21 passed means state passed
Q22 pre-step inject reminder never reject
Q23 t3-hooks tests vs dist
Q24 T3 only
Q25 README mention hooks pin rc.2
Q26 bash heuristics
Q27 PreToolDecision allow deny ask
Q28 HooksHost on()

## Order

1. Keep inspected `packages/dsh-sbtd/src/hooks.ts`. Local types. `registerHooks` from `apply()`. Allow via `next()`.
2. Keep `inject = ["tools", "systemPrompt"]`. No extra `sbtd_*` tools. No `@deepseek-ai/dsh` imports. No fs / `AGENTS.md`.
3. Stub `on()` in T0 T1 T2 apply tests.
4. Feature `features/t3-hooks-gate.feature`. Tests `test/t3-hooks.test.mjs` vs `dist/` after `tsc`.
5. README mention hooks; keep unpublished warning + pin `0.1.1-rc.2` + `@next`. No path install. No root README. No lockfile.
6. Update `.trellis/spec/dsh-sbtd/backend` to T3. Expand this task’s prd/design/implement. Do not add other untracked trellis dirs.
7. Validate: lint, typecheck, build, test. One commit. Do not push. Do not open a PR.

## Validation

```bash
# packages/dsh-sbtd
biome check src
tsc -p tsconfig.json --noEmit
tsc -p tsconfig.json
node --test test/*.test.mjs
```

Live `dsh plugin add` is not required (T0). Maestro / Playwright: not-needed.

Result: lint 0, typecheck 0, build 0, test 36 pass / 0 fail.
`rtk`: not-available (`rtk` not on PATH); fallback-native biome/tsc/node --test.
`pnpm --filter` blocked on frozen lockfile vs peer `@deepseek-ai/dsh@0.1.1-rc.2`; ran package biome/tsc/node --test via repo `node_modules/.bin`.
GitNexus impact on `packages/dsh-sbtd/src/index.ts:apply`: UNKNOWN (0 graph callers); tests import `apply` from `dist/`. Index 3 commits behind HEAD; results advisory.
detect_changes --scope all: HIGH (apply now registers hooks; 7 flows). Covered by t3-hooks tests.

## Rollback

Revert `packages/dsh-sbtd` T3 files and `.trellis/spec/dsh-sbtd/backend` T3 edits. Do not keep `dist/`. Do not publish.

## Gate reviews

```text
DDD Boundary Review
Status: not-required
Ubiquitous language: tools/pre-execute; agent/pre-step; PreToolDecision allow/deny/ask; sbtd_plan; sbtd_review
Bounded contexts: dsh-sbtd plugin shell vs Trellis vs 640-skills. T3 stays in the plugin.
Invariants: no plan → ask sbtd_plan; required unpassed → deny sbtd_review; allow via next()
Corrections to grill-with-docs: 未完整调用; PRD defaults recorded as Q1–Q28
Open conflicts: none
```

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: T1 in-process Map via getSession; T3 reads plan only
Write / read / async / failure paths: no persist/cache/async/cross-service
Consistency model: sessionIdFromExec → getSession
Required tests: t3-hooks.test.mjs vs dist/
```

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: apply() registers hooks via ctx.on
Behavior to preserve: name/inject; T0 log; section; sbtd_plan; no fs/AGENTS.md; peer 0.1.1-rc.2
Current reproduction evidence: T0/T1/T2 apply hosts lacked on()
Safety net: stub on(); t3-hooks.test.mjs vs dist/
Validation plan: biome check src; tsc --noEmit; tsc; node --test test/*.test.mjs
Review mode: normal
```

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/src/index.ts apply()
Behavior that must remain unchanged: section + sbtd_plan; inject tuple
Structural friction: none
Decision and smallest safe step: no extra refactor; call registerHooks(ctx)
Safety net and validation: node:test + tsc
Deferred refactors: none
```

```text
Release Readiness Review
Status: not-required
Production path: none added (no service / API / job / deploy). Package remains private unpublished.
```
