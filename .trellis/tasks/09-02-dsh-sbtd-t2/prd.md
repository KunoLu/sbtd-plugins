# dsh-sbtd T2 sbtd_plan

## Goal

Models can register or update a Book Gate Plan via `sbtd_plan`. Required vs on-demand comes from PRD 3.4 objective predicates (summary + optional facts). The plan is stored in T1 in-process session state keyed by caller `sessionId`. `apply()` still does not write `AGENTS.md`. T3 hooks are out of scope.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：用户明确 Grill PRD defaults，T2 已由 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` T2 / 3.4 / 6.2 钉死。不进入交互澄清。

## Grill Q&A（本轮给定 PRD 默认值，全部记录）

- Q1 tool name / surface? A1 `sbtd_plan` registered from `apply()` via `ctx.tools.register`. Keep `inject` as `tools` + `systemPrompt` only (T1 A10; do not add `agents` yet).
- Q2 inputs? A2 required `task_summary: string`; optional `facts: string[]`. Caller may pass only the summary; the tool infers required from 3.4 predicates on summary+facts.
- Q3 required inference? A3 Objective predicates only. Hit → `required` + `planned`. Miss → `on-demand` + `not-required`. Forbidden: subjective “feels high risk” downgrade.
- Q4 3.4 triggers? A4 ddd: full `grill-with-docs` / clarify / DDD. ddia: persist / shared data / cache / async or cross-service data flow. legacy: existing-behavior bug / weak tests / unclear behavior / hidden deps / high regression. refactor: will edit existing production code. release: production path service / API / job / deploy.
- Q5 session key? A5 T1 `getSession(sessionId)`. `sessionId` from `exec.agent.id` when present, else `"default"`. No filesystem.
- Q6 return? A6 full `BookGatePlan` JSON plus human Markdown table. Five gates always have `requirement` and `state`.
- Q7 repeat calls? A7 same `taskId` (from summary slug): update facts; legal state transitions; do not reset `passed` unless the trigger fact disappeared, then write the reason.
- Q8 host / apply? A8 peer `@deepseek-ai/dsh@0.1.1-rc.2` only. `apply()` still logs T0 stub line, registers section + plan tool, never writes `AGENTS.md` or user disk. Package stays `private: true`.
- Q9 tests / BDD? A9 node:test on `dist/` after tsc; feature file Chinese scenarios + English Gherkin; cover isolation, predicates, passed keep/reset, apply register, README pin + `sbtd_plan`.
- Q10 T3? A10 No hooks. Do not start T3.

## Book Gate Plan

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand (selected) | 未完整 grill；Book Gate Plan / required 谓词是领域术语 | PRD | passed |
| `book-ddia-data-design` | required | 写 T1 session Map 的 `plan`；同一 session 重复调用更新 | design before impl | passed |
| `book-legacy-change-safety` | required | 改既有 `apply()` 增加 tool 注册 | first behavior edit | passed |
| `book-refactoring-pass` | required | 修改既有生产文件 `src/index.ts` | first impl edit | passed |
| `book-release-readiness` | required | DSH 插件 `apply()` 是生产加载入口 | after validation | passed |

## Requirements

- R1. Only `packages/dsh-sbtd` plus this task’s artifacts and `.trellis/spec/dsh-sbtd` layout notes. No new repo. No `trellis init`. No publish. Host pin `0.1.1-rc.2` only.
- R2. Keep `name = "dsh-sbtd"` and `inject` `tools` + `systemPrompt`. Local host types only.
- R3. Add `src/tools/plan.ts`, wire `registerPlanTool` from `apply()`. No `AGENTS.md` / disk writes.
- R4. `sbtd_plan` input `task_summary` + optional `facts`. Infer required from 3.4 objective predicates.
- R5. Write `state.plan` via T1 `getSession`. Five gates always present. Return JSON + Markdown.
- R6. Repeat same goal: keep `passed` unless trigger disappeared (write reason).
- R7. No hooks, no other `sbtd_*` tools, no Maestro execution.
- R8. README keeps unpublished warning, `@next`, pin `0.1.1-rc.2`, mentions `sbtd_plan`.
- R9. BDD feature + node:test.

## Acceptance criteria

- [x] Calling `sbtd_plan` leaves `state.plan` on the session; five gates have `requirement` and `state`.
- [x] Required comes from objective predicates; subjective risk does not force required.
- [x] Repeat same goal keeps `passed` until trigger disappears (reason recorded).
- [x] `apply()` registers `sbtd_plan` and still does not write `AGENTS.md`.
- [x] Host pin `0.1.1-rc.2`; `private: true`.
- [x] Package lint / typecheck / build / test pass.

## Out of scope

- T3 hooks, T4–T16
- Publish, `trellis init`, root README, `0.1.2-alpha` / `0.1.0-rc.7`

## Notes

- Source: v1.2 T2, 3.4, 6.2, 6.3 plus this turn’s Q/A.
