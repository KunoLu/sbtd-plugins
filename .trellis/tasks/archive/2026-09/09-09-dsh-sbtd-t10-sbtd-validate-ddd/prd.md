# PRD -- dsh-sbtd T10 sbtd_validate

## Background

T10 delivers the model-facing tool `sbtd_validate` at `packages/dsh-sbtd/src/tools/validate.ts`, consuming T9 `backends/gitnexus.ts` as-is. DDD Status **confirmed** (`/workspace/omp-tasks/t10-sbtd-validate-ddd.md`). Grill ROUND1_COMPLETE with Q1A–Q5A locked.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t10-sbtd-validate`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/51
- Fence Q5A: `src/tools/validate.ts` + `apply()` `registerValidateTool` + `test/t10-validate.test.mjs` (+ `plan.ts` ToolsHost types for nested dispatch identity + tools.length / tools-dir whitelist). No `gitnexus.ts` rewrite, no MCP config, no npm, no `docs/prd` rewrite.

## Locked Q1-Q5

| Q | Lock | One-line |
|---|---|---|
| Q1 | A | Model may pass `phase` plus optional `target` / `direction` / `scope` only. Host injects `cwd` and all `GitNexusOptions` |
| Q2 | A | `pre`: T9 `impact` only. `post`: `detectChanges` then project tests. Missing GitNexus does not omit tests |
| Q3 | A | GitNexus skipped/advisory never `validate.post=blocked`. `post=blocked` only if tests fail |
| Q3 clar. | LOCK | `skipped` → `validate.pre="skipped"`; `ok` or `advisory` → `validate.pre="done"` |
| Q4 | A | Return `{ phase, gitnexus, tests?, validate }`. No script ⇒ skipped + residual risk, never fake passed |
| Q5 | A | Register from `apply()`. Import T9 as-is. No gitnexus rewrite / docs/prd / MCP / omp / npm |

## Non-goals

- T9 `gitnexus.ts` rewrite / T9 r2 residuals
- Channel / `trellis init` / MCP config writes
- omp config / providers / registry publish
- host pin retarget
- T7/T8/T9 reopen / `docs/prd` rewrite
- docs/TODO merge-SHA backfill (post-merge chore)

## Acceptance

- [x] Model schema: `phase` + optional `target` / `direction` / `scope` only; host injects cwd + GitNexusOptions
- [x] `pre` → T9 `impact`; missing target or T9 skipped ⇒ `validate.pre="skipped"`; no tests on pre
- [x] `post` → `detectChanges` then project tests; missing GitNexus does not omit tests / never `post=blocked`
- [x] `ok` or `advisory` ⇒ `validate.pre="done"`; advisory printed
- [x] Return `{ phase, gitnexus, tests?, validate }`; no-script ⇒ skipped + residual risk, never fake passed; failed tests ⇒ `post=blocked`
- [x] Cancel ≠ test failure; abort does not persist `post=blocked` (spawned runner, no-command, injected failed-after-abort)
- [x] `apply()` `registerValidateTool`; T9 consumed as-is
- [x] r1 REQUIRED closed: host GitNexus inject + non-Node docs tests
- [x] r2 REQUIRED closed: multi-candidate project-marker-first; cancel≠blocked on spawned runner
- [x] r3 REQUIRED closed in `7a660af`: (1) nested `tools.execute` forwards agent + parent token + rootCallId; (2) `throwIfAborted` before post + no-command AbortError + injected failed-after-abort no post; (3) `collectDocCandidates` advances regex before reject/continue; (4) `package-lock.json` Node marker
- [x] Fence held: `packages/dsh-sbtd/src/tools/validate.ts` + `src/index.ts` apply register + `src/tools/plan.ts` ToolsHost types + `test/t10-validate.test.mjs` (+ legacy test adjustments)
- [x] No extra `sbtd_*` beyond `sbtd_validate` / no docs/prd / host pin unchanged / no MCP writes / no npm
- [x] PR #51 tip `7a660af6404cd14bf5f8eaddc7de3abedb689406`; review r4 CLEAN; Quality=pass (0.98); Security=pass; Advisor CLEAN; REQUIRED_CHANGES=none
- [x] locks Q1A Q2A Q3A(+clar) Q4A Q5A
- [x] tests: 201 green (per r4 tldr)

## Closeout

Scheme A finish on #51. Archive this task with the grill sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
