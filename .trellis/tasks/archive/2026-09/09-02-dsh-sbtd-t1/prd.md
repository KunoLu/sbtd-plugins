# dsh-sbtd T1 short section and session state

## Goal

Every DSH session that loads `@kunolu/dsh-sbtd` carries a non-empty Chinese `sbtd` systemPrompt section (order 50, UTF-8 ≤ 2048 bytes). Session Book Gate Plan / Maestro missing state lives in an in-process Map keyed by caller `sessionId`, with `serialize()` for handoff. `apply()` still does not write `AGENTS.md` or user disk. T2 tools and T3 hooks are out of scope.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：用户明确 `Grill: do not wait`，并在本轮给出全部 Q/A；T1 已由 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` T1 / 5.2 / 5.3 / 6.1 / 6.3 钉死。不进入交互澄清。

## Grill Q&A（本轮给定，全部记录）

- Q1 section language/body? A1 Chinese; name `sbtd`; order 50; UTF-8 ≤ 2048 bytes; PRD 6.1 bullets only: `sbtd_plan` first, no prod edits before plan; `sbtd_clarify` then DDD passed; `sbtd_validate`/`sbtd_e2e` not raw MCP; `sbtd_review` to passed; final 结论/文件/验证/跳过原因/风险; Maestro missing Java/CLI/device/app/env blocked+guide. No AGENTS dump.
- Q2 also `systemPrompt.context` duplicate? A2 No. Only section name `sbtd` order 50. system/reminder means DSH assembled system/reminder shows that section. Empty sections drop so text must be non-empty.
- Q3 session key? A3 caller `sessionId` string; in-process Map; no fs; `serialize()` at least `plan` and `maestro.missing`; restart drops Map but API unit-testable after re-import.
- Q4 keep empty T0 section? A4 keep `name`/`inject`; replace empty text via `section.ts`; update T0 tests/feature; no tools/hooks.
- Q5 `sbtd_plan` or hooks now? A5 No. T2/T3 out of scope.
- Q6 import dsh types? A6 local context type only; peer `0.1.1-rc.2`; static string text.
- Q7 default state? A7 PRD 6.3 `GateState` `BookGatePlan` `SbtdSessionState` exactly; unknown id returns `{validate:{}}` isolated.
- Q8 tests? A8 node:test snapshot of section plaintext; apply registers it; Map isolation; serialize roundtrip; restart simulation; update `package.json` test glob; features/ BDD like T0; test dist after tsc.
- Q9 README? A9 keep `@deepseek-ai/dsh@0.1.1-rc.2` and `dsh plugin --profile web add @kunolu/dsh-sbtd@next`; mention short Chinese `sbtd` section; no path install; no alpha. Update `.trellis/spec/dsh-sbtd/backend` if stub layout outdated. No root README.
- Q10 inject agents? A10 keep `tools` and `systemPrompt` only.

## Book Gate Plan

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand (selected) | 未完整 grill；但 `BookGatePlan` / session 隔离是领域术语 | PRD | passed |
| `book-ddia-data-design` | required | 进程内 Map 是跨 request 的 session 状态；`serialize()` 给 handoff | design before impl | passed |
| `book-legacy-change-safety` | required | 改既有 `apply()` 空 section → 非空正文；宿主动态加载 | first behavior edit | passed |
| `book-refactoring-pass` | required | 修改既有生产文件 `src/index.ts` | first impl edit | passed |
| `book-release-readiness` | required | DSH 插件 `apply()` 是生产加载入口 | after validation | passed |

## Requirements

- R1. Only `packages/dsh-sbtd` plus this task’s artifacts and outdated `.trellis/spec/dsh-sbtd` layout notes. No new repo. No `trellis init`. No publish. No git commit. Host pin `@deepseek-ai/dsh@0.1.1-rc.2` only; never `0.1.2-alpha` or `rc.7`.
- R2. Keep `export const name = "dsh-sbtd"`. `inject` stays `tools` and `systemPrompt` only (A10). Local context type only; do not import `@deepseek-ai/dsh` types.
- R3. Add `src/section.ts` and `src/state.ts`, wired from `src/index.ts`. `apply()` must not write `AGENTS.md` or user disk.
- R4. Section: name `sbtd`, order 50, Chinese, non-empty, UTF-8 ≤ 2048 bytes, PRD 6.1 bullets only. Do not also register `systemPrompt.context`.
- R5. State: caller `sessionId` string; in-process `Map`; no fs; PRD 6.3 types exactly; unknown id returns isolated `{validate:{}}`; `serialize()` includes at least `plan` and `maestro.missing`; process restart drops Map.
- R6. No `sbtd_*` tools, no hooks, no backends, no Maestro execution.
- R7. Keep `private: true`. Keep peer `0.1.1-rc.2`. Update package `test` glob.
- R8. Update T0 feature/tests: empty section text is replaced. Add T1 BDD under `packages/dsh-sbtd/features/` like T0.
- R9. README keeps `@deepseek-ai/dsh@0.1.1-rc.2` and `dsh plugin --profile web add @kunolu/dsh-sbtd@next`; mentions short Chinese `sbtd` section; no path install; no alpha. No root README.

## Acceptance criteria

- [x] `apply()` registers `{ name: "sbtd", order: 50, text }` with non-empty Chinese 6.1 body, UTF-8 ≤ 2048 bytes.
- [x] `name` is `dsh-sbtd`; `inject` is `tools` + `systemPrompt` only.
- [x] `src/section.ts` and `src/state.ts` exist and are used from `src/index.ts`.
- [x] Unknown session id returns isolated `{ validate: {} }`; Map does not leak across ids.
- [x] `serialize()` roundtrips at least `plan` and `maestro.missing`; re-import after simulated restart has empty Map then API still works.
- [x] node:test covers section plaintext snapshot, apply registration, Map isolation, serialize roundtrip, restart simulation; tests import `dist/` after tsc.
- [x] T0 feature/tests no longer require empty section text.
- [x] README pin + `@next` install + short Chinese section; no path install; no alpha; `private: true`.
- [x] Package `lint`, `typecheck`, `build`, `test` pass.
- [x] `apply()` still has no `fs` / `AGENTS.md` writes.

## Out of scope

- T2 `sbtd_plan`, T3 hooks, T4–T16
- New repository, publish, git commit, `trellis init`, root README
- dsh `0.1.2-alpha` / `0.1.0-rc.7`
- Importing host types, `systemPrompt.context` duplicate, `inject` adding `agents`

## Notes

- Source: `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` T1, 5.2, 5.3, 6.1, 6.3, plus this turn’s Q/A.
- BDD: plugin section text and README are user-visible. Session Map is internal (node:test only).
- Implementation checkout: linked worktree `/workspace/sbtd-plugins-t1` on `feat/dsh-sbtd-t1` @ `0df41e0`. Original `/workspace/sbtd-plugins` stays on `fix/dsh-sbtd-t0-unpublished-claim` with unrelated dirty T0 files untouched.
