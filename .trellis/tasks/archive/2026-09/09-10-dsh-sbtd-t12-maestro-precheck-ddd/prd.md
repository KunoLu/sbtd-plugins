# PRD -- dsh-sbtd T12 Maestro 预检

## Background

T12 delivers the Maestro preflight **backend** at `packages/dsh-sbtd/src/backends/maestro.ts`. DDD Status **confirmed** (`/workspace/omp-tasks/t12-maestro-precheck-ddd.md`). Grill ROUND1_COMPLETE with Q1A–Q6A locked.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/t12-maestro-preflight`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/55
- Fence Q5A: `src/backends/maestro.ts` + `test/t12-maestro.test.mjs` (+ optional `docs/TODO.md` tip). No `apply()` e2e/maestro, no `maestro/flow/`, no manuals nest, no `maestro test` spawn, no silent install, no cloud run/upload, no validate/bdd/gitnexus/trellis edits, no MCP, no npm, no `docs/prd` rewrite.

## Locked Q1-Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | A | Hybrid six-step: live 1–3; declared 4–6; never `maestro test` |
| Q2 | A | Backend-only; no apply register |
| Q3 | A | preflight may write session.maestro; T13 must call; no flow |
| Q4 | A | Host cwd; model platform hint only; T10 keys forbidden |
| Q5 | A | maestro.ts + tests; stub detect |
| Q6 | A | Cloud declaration-only; no run/upload |

## Non-goals

- T13 `sbtd_e2e` generate/run/reports
- Channel / MCP / omp / npm / host retarget / docs/prd rewrite
- docs/TODO merge-SHA backfill (post-merge chore)

## Acceptance

- [x] Live 1–3 stubbed; missing declared 4–6 ⇒ blocked + missing
- [x] Local `deviceClass` is hint; live list still required; only cloud skips list
- [x] iOS success requires `(Booted)` state, not Booted-in-name Shutdown
- [x] Missing-device guidance: live Booted sim / adb `\tdevice`; only `deviceClass=cloud` is declaration-only
- [x] Unit tests stub detect; no live java/maestro/xcrun/adb in unit path (cloud defaultDetectDevice returns before probes)
- [x] `preflight()` writes session.maestro; handoff missing-only
- [x] No apply e2e/maestro; no maestro/flow/; no maestro test; no silent install; no cloud upload
- [x] r1 R1/R2 closed; r2 R2 residual / R3 guidance / R4 stub-detect closed at tip `a42ca4c0107e07001c4fd4364aa1e6009783c8a4`
- [x] Combined r3 CLEAN; Main+Pr55R3Reviewer+advisor CONTENT CLEAN; REQUIRED_CHANGES=none
- [x] locks Q1A Q2A Q3A Q4A Q5A Q6A
- [x] tests: 17/17 t12-maestro
- [x] Fence held

## Closeout

Scheme A finish on #55. Archive with the grill sibling. `docs/TODO.md` merge-SHA backfill is a post-squash chore if still pending.
