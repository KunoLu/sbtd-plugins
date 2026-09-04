# PRD — FU1 Remediation Write scoped allow

## Background

T5 maps `seam-required` / `refactor-first` to GateState `running`. T3 `gatePreExecute` still denies all production PathClass mutations while a required gate is unpassed. That deadlocks the manuals' remediation loop (FOLLOWUPS (a)).

Canonical name: **Remediation Write**. Mechanism: **scoped allow** keyed off `reviewStatus`. Kind: Gate-internal allowed transition. Not Accepted Skip, not fake `passed`, not a new `GateState`.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-fu1-remediation-write`
- Loops 1 and 2 only, independently

## Behavior

When a required gate is unpassed (`requirement === required` && `state !== passed`) **and** that gate's `reviewStatus` is:

- `legacy` + `seam-required` → do not deny that gate for production PathClass mutations (Loop 1)
- `refactor` + `refactor-first` → do not deny that gate for production PathClass mutations (Loop 2)

Gate stays `required` + `running`. `mapGateState` / `RUNNING_STATUS` / `requirement` / `review.ts` mapping unchanged.

`needs-*` statuses do **not** open the window. Legacy-first deny order stays. ddd / ddia / release / EXEMPT / README unchanged.

## Known limitation (honesty)

There is **no** byte-level seam-vs-feature classifier. Opening the window allows **all** production-class writes while that `reviewStatus` is set. Q4A still-deny-non-remediation is prompt/honor only. Tests, comments, and PR body must say this explicitly.

## Non-goals

- FOLLOWUPS (b) `sbtd_review` order
- §3.4 combined loop / recorded `safety-seam-only`
- `reviewMode` persistence
- Package registry publish
- omp config edits
- `mapGateState` changes

## Acceptance

- [x] Loop1: legacy required running `seam-required` allows production write (implemented + covered in `t3-hooks.test.mjs` / `t3-hooks-gate.feature`).
- [x] Loop2: legacy passed; refactor required running `refactor-first` allows production write (implemented + covered).
- [x] Negative: legacy required running `needs-clarification` still denies legacy (implemented + covered).
- [x] Negative: legacy unpassed without remediation plus refactor `refactor-first` still denies legacy first (implemented + covered).
- [x] EXEMPT still free when legacy unpassed (implemented + covered).
- [x] Window-open r2 nits: with Loop window open, `ddd` / `ddia` / release publish still deny when those gates are required unpassed (covered).
- [x] `npx biome check src` pass; `npx tsc --noEmit` pass; `node --test test/*.test.mjs` **83/83** pass (verified on this finish).
- [x] FOLLOWUPS(a) marked **resolved** in T5 `FOLLOWUPS.md` + T5 `prd.md` (commit `fc373f3`).
- [x] PR #33 r2 `/review` **CLEAN** (Quality + Security + Advisor pass); head `fc373f34c161c667188817114ee7a322dbe968b3`.
- [x] Known limitation documented: whole-window allow, Q4A honor-only, no byte-level seam-vs-feature classifier.
- [x] No package registry publish; no omp-config edits.

## Locked Q1–Q8

| Q | Lock |
|---|---|
| Q1 B | Name: Remediation Write |
| Q2 A | Scoped allow; Gate stays running; hook keys off reviewStatus; T5 mapping unchanged |
| Q3 B | Loops 1 and 2 only |
| Q4 A | Still deny non-remediation — honor/prompt only this round |
| Q5 A | safety-seam-only is Review mode; FU1 does not persist it |
| Q6 C | Live T3 deny + explicit FU1 allow; EXEMPT stays free |
| Q7 A | Gate-internal allowed transition |
| Q8 A | Park FOLLOWUPS (b) |
