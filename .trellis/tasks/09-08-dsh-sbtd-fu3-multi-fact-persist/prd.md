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

While `clarifyStatus=complete`, `clarifyMode=docs`, `sameGoal` (same `taskId`), and `clarifyCompleteTaskId` equals that `taskId`, `mergeGate` must not demote Forced Docs DDD to on-demand when the haystack omits grill facts. Keep `requirement=required` and previous `state` plus `reviewStatus`/`fact` as appropriate.

`clarifyStatus` may inform merge stickiness only together with the completing `taskId`. It must not become a second T3 predicate. `hooks.ts` is frozen. T6 Q8 `elevateDocsDdd` one-shot is unchanged.

Withdraw still demotes/drops: `sbtd_clarify reset=true` and/or a new `task_summary`/`taskId`. A docs Complete from task A must not sticky task B.


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
- [x] A docs Complete does not sticky a later task: B supplies then omits grill facts → ddd demotes; T3 does not deny from A's Complete
- [x] Expansion persist→persist+schema (or persistence→database/schema): inherited pass resets
- [x] Extra **ddd grill** alias EN/zh: pass does not reset (not ddia persist/schema bilingual collapse)
- [x] Existing T5/T6 regressions green (string-change reset, Q8 elevate, Gate-only T3 deny)
- [x] `biome check src`; `tsc --noEmit`; `node --test test/*.test.mjs` (**121/121** at production tip `d2194f5229e6f8b08fef3a6a69f9e8e3a41c9ba1`)
- [x] Two *feature* commits (+ permitted docs/review/fix commits), one PR (#43)
- [ ] Closeout: not merged, not finish-work

Evidence for r4 P2 at production tip `d2194f5229e6f8b08fef3a6a69f9e8e3a41c9ba1`:

- `t2-plan.test.mjs` `新 taskId 丢弃 Forced Docs DDD 不粘滞`; `他任务 docs Complete 后新任务省略 grill 可 demote DDD`
- `t3-hooks.test.mjs` `他任务 docs Complete 后新任务省略 grill 不因陈旧 Complete deny`
- `t6-clarify.test.mjs` `docs Complete 绑定 taskId；compaction restore 匹配；Reset 清除`; `他任务 docs Complete 后新任务省略 grill 可 demote 且 T3 不因陈旧 Complete deny`
- features: t2/t3/t6 cross-task scenarios


