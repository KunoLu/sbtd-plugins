# dsh-sbtd T2 sbtd_plan

## Goal

Models can register or update a Book Gate Plan via `sbtd_plan`. Required vs on-demand comes from PRD 3.4 objective predicates on `task_summary` plus optional `facts`. The plan is stored in T1 in-process session state. `apply()` does not write `AGENTS.md`. T3 hooks are out of scope.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：用户明确 Grill PRD defaults；T2 已由 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` T2 / 3.4 / 6.2 / 6.3 钉死。不进入交互澄清。

## Grill Q&A（PRD 默认值，逐条记录）

- Q1 task_summary required; optional facts string[]; infer from both.
  A1 `task_summary: string` is required. `facts: string[]` is optional. Infer required gates from both the summary and the facts.

- Q2 required from PRD 3.4 objective predicates only; never subjective high risk; hit required planned; miss on-demand not-required.
  A2 Required comes only from PRD 3.4 objective predicates. Never subjective “high risk”. Hit → `required` + `planned`. Miss → `on-demand` + `not-required`.

- Q3 DDD required only after completed grill-with-docs; bare ddd without that fact stays on-demand.
  A3 DDD is `required` only after completed `grill-with-docs`. Bare `ddd` without that fact stays `on-demand`.

- Q4 DDIA persist shared data cache async cross-service.
  A4 DDIA is `required` when persist / shared data / cache / async / cross-service facts hit. This T2 change does not add persist, cache, async, or cross-service work.

- Q5 legacy existing behavior bug weak tests unclear behavior hidden deps high regression.
  A5 Legacy is `required` when existing-behavior bug / weak tests / unclear behavior / hidden deps / high regression hit.

- Q6 refactor modify existing production code.
  A6 Refactor is `required` when the task will modify existing production code.

- Q7 release production path service API job deploy.
  A7 Release is `required` when production path / service / API / job / deploy hit. This T2 change does not add those production paths. Order of simultaneous legacy+refactor is a later task.

- Q8 session exec.agent.id; missing default; no import of dsh package types.
  A8 Session id from `exec.agent.id`, else `"default"`. Local host types only. No import of `@deepseek-ai/dsh` package types.

- Q9 same taskId slug keeps passed unless trigger disappeared with reason; new taskId new plan.
  A9 Same `taskId` slug keeps `passed` unless the trigger disappeared, then write the reason. A new `taskId` starts a new plan.

- Q10 return plan JSON plus markdown table; five gates always present.
  A10 Return plan JSON plus a markdown table. All five gates are always present.

- Q11 apply registers tool; JSON Schema object root; no alpha APIs.
  A11 `apply` registers the tool. Parameters are a JSON Schema object root (`type: "object"`, `properties`, `required: ["task_summary"]`). No 0.1.2-alpha APIs.

- Q12 T0 T1 apply tests must stub tools.register.
  A12 T0 and T1 `apply` tests must stub `tools.register`.

- Q13 restore already hydrates; empty snapshot already clears plan; add tests; do not rework restore.
  A13 T1 `restore` already hydrates; an empty snapshot already clears `plan`. Add tests. Do not rework `restore`.

- Q14 no hooks and no other sbtd tools.
  A14 No hooks and no other `sbtd_*` tools.

- Q15 no AGENTS.md writes; no publish; no trellis init dsh flag; no 0.1.2-alpha.
  A15 No `AGENTS.md` writes. No publish. No `trellis init --dsh`. No 0.1.2-alpha.

- Q16 README mention sbtd_plan; keep pin and @next unpublished; no path install; update spec backend; no root README.
  A16 README mentions `sbtd_plan`. Keep pin `0.1.1-rc.2`, `@next`, unpublished warning. No path install. Update spec backend. No root README.

- Q17 feature t2-sbtd-plan.feature and test t2-plan.test.mjs vs dist after tsc.
  A17 `features/t2-sbtd-plan.feature` plus `test/t2-plan.test.mjs` against `dist/` after `tsc`.

- Q18 output plan object and markdown string; object additionalProperties false; isConcurrencySafe false.
  A18 Output `{ plan: object, markdown: string }` object with `additionalProperties: false`. `plan` schema type is `object`, not `json`. `isConcurrencySafe` is `false`.

- Q19 empty summary throws.
  A19 Empty `task_summary` throws.

- Q20 both legacy and refactor required if both hit; order is later task.
  A20 If both legacy and refactor hit, both are `required`. Their ordering is a later task.

## Book Gate Plan (this T2 implementation)

| Gate | Requirement | State | Fact |
|---|---|---|---|
| ddd | on-demand | not-required | no completed grill-with-docs |
| ddia | on-demand | not-required | no persist / shared data / cache / async / cross-service in this change |
| legacy | required | planned | existing apply()/T0-T1 test behavior (tools.register stub) |
| refactor | required | planned | modify existing production `src/tools/plan.ts` |
| release | on-demand | not-required | no production path service / API / job / deploy |

Q20: both legacy and refactor are required. Order is a later task.

## Requirements

- R1. Only `packages/dsh-sbtd` plus this task’s artifacts and `.trellis/spec/dsh-sbtd` backend. No new repo. No `trellis init`. No publish. Host pin `0.1.1-rc.2` only.
- R2. Keep `name = "dsh-sbtd"` and `inject` `tools` + `systemPrompt`. Local host types only. No `@deepseek-ai/dsh` type imports.
- R3. `src/tools/plan.ts` registered from `apply()` via `ctx.tools.register`. No `AGENTS.md` / disk writes.
- R4. Input `task_summary` + optional `facts`. Infer required from 3.4 objective predicates. Bare `ddd` is on-demand.
- R5. Write `state.plan` via T1 `getSession`. Five gates always present. Return JSON + Markdown.
- R6. Same `taskId` keeps `passed` unless trigger disappeared (reason recorded). New `taskId` is a new plan.
- R7. No hooks, no other `sbtd_*` tools.
- R8. README keeps unpublished warning, `@next`, pin `0.1.1-rc.2`, mentions `sbtd_plan`.
- R9. BDD feature + node:test vs `dist/` after `tsc`.

## Acceptance criteria

- [x] Calling `sbtd_plan` leaves `state.plan` on the session; five gates have `requirement` and `state`.
- [x] Required comes from objective predicates; subjective risk does not force required.
- [x] Bare `ddd` stays on-demand; completed `grill-with-docs` makes DDD required.
- [x] Repeat same goal keeps `passed` until trigger disappears (reason recorded). New `taskId` is a new plan.
- [x] Empty `task_summary` throws.
- [x] `apply()` registers `sbtd_plan` (JSON Schema object-root parameters; output `plan` type `object`; `additionalProperties: false`; `isConcurrencySafe` false) and does not write `AGENTS.md`.
- [x] T0/T1 apply tests stub `tools.register`. Restore hydrate / empty-snapshot tests exist without reworking `restore`.
- [x] Host pin `0.1.1-rc.2`; `private: true`.
- [x] Package lint / typecheck / build / test pass.

## Out of scope

- T3 hooks, T4–T16
- Publish, `trellis init`, root README, `0.1.2-alpha` / `0.1.0-rc.7`
- Importing `@deepseek-ai/dsh` types
- Persist / cache / async / cross-service / production deploy work
