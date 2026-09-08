# PRD — FU3 multi-fact + persist-across-replans

## Background

After docs Clarify Complete, Forced Docs DDD is `required` (often `blocked`). A same-summary `sbtd_plan` that omits grill-with-docs facts currently lets `mergeGate` demote `ddd` to `on-demand`/`not-required`. T3 then allows production writes while `clarifyStatus` is still `complete`. That is the persist-across-replans write hole (Q2B).

Separately, `inferRequirements` uses `PREDICATES[kind].find` first-match, so persist→persist+schema does not reset a required pass, and extra language aliases of one concept can change the stored `fact` string and reset. Trigger identity must be the matching-set of distinct catalog facts (Q1D).

## Scope

- Package: `packages/dsh-sbtd` (`plan.ts` infer/merge, tests/features). `docs/TODO.md` + this Trellis implement task.
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-fu3-multi-fact-persist`
- Two commits in one PR (Q4B): (1) persist-across-replans sticky required; (2) multi-fact matching-set

## Locked Q1–Q5

| Q | Lock | One-line |
|---|---|---|
| Q1 | D | Trigger identity = matching-set of distinct catalog facts; ddd’s three grill-with-docs regexes collapse to one identity; set expansion resets `required+passed`; extra EN/中文 alias does not |
| Q2 | B | Omission ≠ withdraw. `clarifyStatus=complete` ∧ same `taskId` → Forced Docs DDD stays `required` (blocked/running/planned/passed). Withdraw = Interview Reset and/or new summary/`taskId` |
| Q3 | A | T3 write deny stays Gate-only. No `clarifyStatus` / Complete write veto |
| Q4 | B | Sequential: persist-across-replans first, multi-fact second; same PR |
| Q5 | A | Fence = `packages/dsh-sbtd` only. Hooks frozen. No T7/T8, omp config, publish, host retarget |

## Behavior

### Persist-across-replans (commit 1)

While `clarifyStatus=complete` and `sameGoal` (same `taskId`), `mergeGate` must not demote Forced Docs DDD to on-demand when the haystack omits grill facts. Keep `requirement=required` and previous `state` plus `reviewStatus`/`fact` as appropriate.

`clarifyStatus` may inform merge stickiness. It must not become a second T3 predicate. `hooks.ts` is frozen. T6 Q8 `elevateDocsDdd` one-shot is unchanged.

Withdraw still demotes/drops: `sbtd_clarify reset=true` and/or a new `task_summary`/`taskId`.

### Multi-fact matching-set (commit 2)

For each `GateKind`, identity is the matching-set of distinct catalog facts, not first-match. Language aliases of one concept collapse to one member. Set expansion (persist→persist+schema) resets `required+passed`. Extra EN/zh alias wording does not reset pass. Distinct ddia/legacy/release catalog rows still reset on expansion of their matching-set.

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

- [ ] After docs Complete, same-summary replan omitting grill facts: `ddd` stays `required` (including `blocked`); T3 still denies production writes
- [ ] Interview Reset or new taskId/summary: demote/drop allowed
- [ ] Expansion persist→persist+schema (or persistence→database/schema): inherited pass resets
- [ ] Extra ddd alias EN/zh: pass does not reset
- [ ] Existing T5/T6 regressions green (string-change reset, Q8 elevate, Gate-only T3 deny)
- [ ] `biome check src`; `tsc --noEmit`; `node --test test/*.test.mjs`
- [ ] Two commits, one PR, not merged, not finish-work
