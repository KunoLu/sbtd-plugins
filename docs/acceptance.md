# dsh-sbtd T16 端到端验收记录

| Field | Fact |
|---|---|
| Verdict | **T16 PASS** (all 8 steps) |
| Date | 2026-09-12 (Asia/Shanghai) |
| Subject | `sbtd-plugins` only |
| HEAD / tip under test | `98edd712efa46274fce7644b650937c9f5361929` (short `98edd71`) |
| Tip provenance | After FU4 #65 → merge `2fc31b4` + tip chore #66 |
| Host pin | `@deepseek-ai/dsh@0.1.1-rc.2` (`dsh --version`) |
| Package | `@kunolu/dsh-sbtd@0.1.0-rc.1` via local `npm pack` (**not** registry `@next`) |
| Tarball sha256 | `ffb67d6f4cc36ef7dd031e38ff0655a560566f67c46cf339d7403cd2eb191237` |
| Pack | 93 files including `dist/` |
| Install | remove then add tarball under dsh profile `web` |
| Venue | User's Mac (Mac-mini), human + `dsh web`; OMP did not proxy `dsh web` |
| Locks | Scheme A docs-only record; **no** product / tool / hooks / backends edit this PR; **no** npm publish |
| Supersedes | Prior #64 FAIL record (stopped at step 2 clarify type arrays). FU4 fixed schemas; T16 re-ran from step 2. FU4 closed #65 merge `2fc31b4` / tip `98edd71`. |

## Provenance

1. Prior FAIL was step 2: host `dsh@0.1.1-rc.2` rejected `sbtd_clarify` output schema type arrays.
2. FU4 (#65 → `2fc31b4`, tip chore #66 → `98edd71`) fixed schemas, then T16 re-ran from step 2.
3. This document is the final PASS Acceptance Record. It supersedes the previous FAIL content on this PR. Not a KPi Evidence Envelope. No npm publish.

## Step results

| Step | Result | Evidence |
|---|---|---|
| 1 DSH pin | **PASS** | DSH pin `0.1.1-rc.2` |
| 2 bundle + section / command visible | **PASS** | Bypass A (Lord/Researchy lock): plugin list shows `@kunolu/dsh-sbtd` enabled + `/` shows `/sbtd` + no schema reject. `systemPrompt.section` is model-injected; UI does not show Chinese section text. Not the old T0 stub log line. |
| 3 hook blocks src edit | **PASS** | `kind=ask`; approval popup reason「尚未 sbtd_plan，请先调用 sbtd_plan。」; write to `packages/dsh-sbtd/src/section.ts` with no plan (workspace `sbtd-plugins`). Note: `frontend/src` under other repos does **not** trigger. |
| 4 plan→clarify→DDD→spec/tickets | **PASS** | Disposable pipeline → `.trellis/tasks/09-12-sbtd-pipeline-drill/` (`prd.md` + `implement.md`); order plan→clarify docs Complete→`sbtd_review kind=ddd` confirmed→spec/tickets; no `trellis init` |
| 5 required review before code | **PASS** | deny; reason contains「required gate 未 passed，请先调用 sbtd_review kind=legacy。」; plan with「fix existing behavior」; edit `packages/dsh-sbtd/src/section.ts` |
| 6 sbtd_validate skip-and-explain | **PASS** | `sbtd_validate phase=pre`; GitNexus skipped mcp-unavailable; `validate.pre=skipped` (skip-and-explain) |
| 7 mobile preflight blocked | **PASS** | `sbtd_e2e surface=mobile action=preflight` → blocked; missing includes device/app/appEnv/identity; runner not started (not T13 failed) |
| 8 640-skills git status clean | **PASS** | 640-skills clean; SHA `1019fec3c1f003dfb229fcb55e146ed4f64cec7c`; porcelain empty |

## Residuals / next

- Overall: **T16 PASS** (all 8 steps).
- This PR (#64) previously recorded FAIL; this revision supersedes that FAIL record. Leave Scheme A **open**; parent decides next. Do not merge this turn.
- This document is the Q4A Acceptance Record only. Not a KPi Evidence Envelope. No npm publish.

## README pointer

Canonical T16 record is this file. No extra README edit in this revision (docs-only fence).

## Models

Record-update session only (not T16 Mac/`dsh web` operators). Unverifiable entries use 模型未知 / 调用次数未知.

| Model | Purpose | Calls |
|---|---|---|
| xai-oauth/grok-4.6 | Main OMP session: rewrite T16 PASS record and update PR #64 | 调用次数未知 |
