# dsh-sbtd T3 hooks gate

## Goal

Models cannot change production code until a Book Gate Plan exists and required gates are `passed`. T3 adds `tools/pre-execute` and `agent/pre-step` on T2 `sbtd_plan`. No extra `sbtd_*` tools. Package stays private. Host pin `@deepseek-ai/dsh@0.1.1-rc.2`.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：用户明确 Grill PRD defaults；T3 已由 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` T3 / 6.4 钉死，Q/A 记在 `implement.md`。不进入交互澄清。

## Grill Q&A（PRD 默认值）

- Q1 host 0.1.1-rc.2
- Q2 hooks.ts
- Q3 pre-execute and pre-step
- Q4 no plan src write ask sbtd_plan
- Q5 README allow
- Q6 required unpassed deny sbtd_review
- Q7 legacy then refactor
- Q8 ddia data-path only
- Q9 release no edit block; deny publish bash
- Q10 ddd blocks impl edits
- Q11 exempt test features maestro trellis
- Q12 write edit str_replace_editor bash
- Q13 git commit allowed
- Q14 rm pkg-mgr ask
- Q15 T1 T2 session
- Q16 no extra sbtd tools
- Q17 no AGENTS.md no publish no trellis init --dsh
- Q18 inject tools systemPrompt
- Q19 allow via next()
- Q20 cwd src app packages
- Q21 passed means state passed
- Q22 pre-step inject reminder never reject
- Q23 t3-hooks tests vs dist
- Q24 T3 only
- Q25 README mention hooks pin rc.2
- Q26 bash heuristics
- Q27 PreToolDecision allow deny ask
- Q28 HooksHost on()

## Book Gate Plan (this T3 implementation)

| Gate | Requirement | State | Fact |
|---|---|---|---|
| ddd | on-demand | not-required | no completed grill-with-docs |
| ddia | on-demand | not-required | hooks only read `getSession`; no persist / schema / cache |
| legacy | required | characterized | existing `apply()` host contract; T0/T1/T2 tests now stub `on()` |
| refactor | required | proceed | modify existing production `src/index.ts` `apply()` |
| release | on-demand | not-required | package remains private unpublished; no production deploy |

## Requirements

- R1. Only `packages/dsh-sbtd` plus this task’s artifacts and `.trellis/spec/dsh-sbtd` backend. No new repo. No `trellis init`. No publish. Host pin `0.1.1-rc.2` only.
- R2. Keep `name = "dsh-sbtd"` and `inject` `tools` + `systemPrompt`. Local host types only. No `@deepseek-ai/dsh` type imports.
- R3. `src/hooks.ts` registered from `apply()` via `ctx.on`. Allow via `next()`. No `AGENTS.md` / disk writes. No extra `sbtd_*` tools.
- R4. Intercept `write` / `edit` / `str_replace_editor` / mutating `bash`. `git commit|status|log|diff|show` allow. README / `*.md` allow.
- R5. No plan + production path under cwd `src/` `app/` `packages/` → `{ kind: "ask" }` pointing at `sbtd_plan`.
- R6. Required gate unpassed → `{ kind: "deny" }` pointing at `sbtd_review kind=…`. Order: legacy, then refactor, then ddd. DDIA only on data paths. Release does not block edits; blocks publish-class bash.
- R7. `*.test.*` / `*.spec.*` / `features/` / `maestro/flow/` / `.trellis/` skip hard deny (still ask without plan).
- R8. `rm` production path or package-manager business-code change → ask.
- R9. `agent/pre-step` awaits `next()` first; if no plan, inject plugin notice; this hook does not originate `reject`.
- R10. Session id from `exec.agent.id` via `sessionIdFromExec` + `getSession`.
- R11. README mentions hooks, keeps unpublished warning, `@next`, pin `0.1.1-rc.2`. T0/T1/T2 apply tests stub `on()`.

## Acceptance criteria

- [x] No plan: `write src/foo.ts` is ask toward `sbtd_plan`.
- [x] README / markdown edits call `next()` allow.
- [x] Required unpassed production write is deny toward `sbtd_review`; legacy before refactor before ddd.
- [x] DDIA only data path; release does not block edits; `npm publish` denied when release required unpassed.
- [x] Exempt paths are not hard-denied; `rm` / pkg-mgr business ask.
- [x] pre-step injects reminder when no plan; does not originate reject.
- [x] `apply()` registers both hooks; inject stays `tools` + `systemPrompt`; `private: true`.
- [x] Package lint / typecheck / build / test pass.

## Out of scope

- T4–T16
- Publish, `trellis init`, root README, lockfile, `0.1.2-alpha` / `0.1.0-rc.7`
- Importing `@deepseek-ai/dsh` types
- Extra `sbtd_*` tools
