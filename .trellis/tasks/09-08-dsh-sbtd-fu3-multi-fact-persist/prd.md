# PRD — FU3 multi-fact + persist-across-replans

## Background

After docs Clarify Complete, Forced Docs DDD is `required` (often `blocked`). A same-summary `sbtd_plan` that omits grill-with-docs facts currently lets `mergeGate` demote `ddd` to `on-demand`/`not-required`. T3 then allows production writes while `clarifyStatus` is still `complete`. That is the persist-across-replans write hole (Q2B).

Separately, `inferRequirements` uses `PREDICATES[kind].find` first-match, so persist→persist+schema does not reset a required pass, and extra language aliases of one concept can change the stored `fact` string and reset. Trigger identity must be the matching-set of distinct catalog facts (Q1D).

## Scope

- Package: `packages/dsh-sbtd` (`plan.ts` infer/merge, tests/features). `docs/TODO.md` + this Trellis implement task.
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-fu3-multi-fact-persist`
- Q4B (re-lock A): two *ordered feature* commits in one PR — (1) persist-across-replans sticky required; (2) multi-fact matching-set — plus permitted docs/review/fix commits (honest Codex fix trail). Do not rewrite history.

## Locked Q1–Q5

| Q | Lock | One-line |
|---|---|---|
| Q1 | D | Trigger identity = matching-set of distinct catalog facts; **only** ddd’s three grill-with-docs language aliases collapse to one identity; distinct ddia/legacy/release catalog rows stay distinct; set expansion resets `required+passed`; extra EN/中文 **ddd grill** alias does not |
| Q2 | B | Omission ≠ withdraw. `clarifyStatus=complete` ∧ same `taskId` → Forced Docs DDD stays `required` (blocked/running/planned/passed). Withdraw = Interview Reset and/or new summary/`taskId` |
| Q3 | A | T3 write deny stays Gate-only. No `clarifyStatus` / Complete write veto |
| Q4 | B | Sequential: two *feature* commits (persist-across-replans first, multi-fact second) in same PR; docs/review/fix additional commits allowed (re-lock A; no history rewrite) |
| Q5 | A | Fence = `packages/dsh-sbtd` only. Hooks frozen. No T7/T8, omp config, publish, host retarget |

## Behavior

### Persist-across-replans (commit 1)

While `clarifyStatus=complete` and `sameGoal` (same `taskId`), `mergeGate` must not demote Forced Docs DDD to on-demand when the haystack omits grill facts. Keep `requirement=required` and previous `state` plus `reviewStatus`/`fact` as appropriate.

`clarifyStatus` may inform merge stickiness. It must not become a second T3 predicate. `hooks.ts` is frozen. T6 Q8 `elevateDocsDdd` one-shot is unchanged.

Withdraw still demotes/drops: `sbtd_clarify reset=true` and/or a new `task_summary`/`taskId`.

### Multi-fact matching-set (commit 2)

For each `GateKind`, identity is the matching-set of distinct catalog facts, not first-match. **Q1D alias collapse is DDD-only**: ddd’s three grill-with-docs regexes share one identity (`完整执行 grill-with-docs`). Do **not** treat persist/持久化 and schema/数据库 as one identity — those are distinct ddia catalog rows. Set expansion (persist→persist+schema, or persistence→database/schema) resets `required+passed`. Extra EN/zh **ddd grill** alias wording does not reset pass. Distinct ddia/legacy/release catalog rows still reset on expansion of their matching-set.

Keep `fact?: string` backward-compatible when the set has one member.

## Non-goals

- `hooks.ts` / Complete write veto
- T7 / T8
- omp settings
- registry publish
- host retarget
- CONTEXT.md / ADR disk writes
- rewriting T6 Q8 elevateDocsDdd
- version bump unless required (keep `0.1.0-rc.1`)

## Acceptance

- [x] After docs Complete, same-summary replan omitting grill facts: `ddd` stays `required` (including `blocked`); T3 still denies production writes
- [x] Interview Reset or new taskId/summary: demote/drop allowed
- [x] Expansion persist→persist+schema (or persistence→database/schema): inherited pass resets
- [x] Extra **ddd grill** alias EN/zh: pass does not reset (not ddia persist/schema bilingual collapse)
- [x] Existing T5/T6 regressions green (string-change reset, Q8 elevate, Gate-only T3 deny)
- [x] `biome check src`; `tsc --noEmit`; `node --test test/*.test.mjs` (**116/116** at production tip `b33641f`)
- [x] Two *feature* commits (+ permitted docs/review/fix commits), one PR (#43)
- [ ] Closeout: not merged, not finish-work

Evidence at production tip `b33641f` (PR #43 Test plan already `[x]`; not 116/116 alone):

- sticky omit + T3 deny: `t6-clarify.test.mjs` `docs Complete 后同摘要省略 grill facts 时 ddd 保持 required 且 T3 仍 deny`; `t3-hooks.test.mjs` `docs Complete 后省略 grill facts 再 plan 仍因 ddd deny 生产 write`; `t2-plan.test.mjs` `Complete 且同 taskId 省略 grill facts 时 Forced Docs DDD 保持 required`
- Interview Reset demote: `t6-clarify.test.mjs` `Interview Reset 后同摘要省略 facts 允许 demote Forced Docs DDD`; `features/t2-sbtd-plan.feature` Interview Reset scenario
- persist→persist+schema reset: `t2-plan.test.mjs` `matching-set persist 后再加 schema 重置 inherited pass`
- extra ddd EN/zh alias no reset: `t2-plan.test.mjs` `matching-set 额外 ddd EN/zh 别名不重置 pass`
- T5/T6 regressions + lint/typecheck/116/116: `FOLLOWUPS.md` tip verify at `b33641f`
