# PRD -- dsh-sbtd T13 sbtd_e2e

## Background

T13 delivers the model-facing tool `sbtd_e2e` at `packages/dsh-sbtd/src/tools/e2e.ts`. DDD Status **confirmed** (`/workspace/omp-tasks/t13-sbtd-e2e-ddd.md`). Grill ROUND1_COMPLETE with Q1B–Q6A locked. Consume T12 `preflight()` as-is (#55 → `61026a1`).

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/t13-sbtd-e2e`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/57
- Fence Q5A: `src/tools/e2e.ts` + `apply()` `registerE2eTool` + `test/t13-e2e.test.mjs` (+ optional `docs/TODO.md` tip + companion tools.length/whitelist). No `maestro.ts` rewrite, no manuals nest, no validate/bdd/gitnexus/trellis rewrite, no MCP, no npm, no `docs/prd` rewrite.

## Locked Q1-Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | B | Three actions; hybrid = 混合 App Maestro; mobile\|hybrid re-call T12; web skips T12 |
| Q2 | A | registerE2eTool; manuals nest deferred |
| Q3 | A | Existing dirs win; unit tests never spawn maestro/browser |
| Q4 | A | Model surface/action/path·slug/platform; host cwd+facts+binaries+lock+creds; no T10 keys |
| Q5 | A | e2e.ts + apply + t13-e2e tests; no maestro.ts rewrite |
| Q6 | A | blocked vs failed vs skipped-by-user; mode labels; mock≠full-stack; no steal |

## Non-goals

- T14 `sbtd_lessons`
- Channel / MCP / omp / npm / host retarget / docs/prd rewrite / maestro.ts rewrite
- docs/TODO merge-SHA backfill (post-merge chore)

## Acceptance

- [x] `mobile|hybrid` generate/run re-call T12; not ok ⇒ blocked; no maestro test process
- [x] `web` generate/run skip T12
- [x] hybrid is Maestro-class, not serial Playwright+Maestro
- [x] `apply()` registers `registerE2eTool`
- [x] Unit tests stub runners; no live maestro/browser spawn in unit path
- [x] Generate confined to flow/Playwright roots; symlink/realpath-safe
- [x] Missing/wildcard-only selector facts block generate (`.*`, `(.*)`, `^(.*)$`)
- [x] Production default runners injectable; timeout → failed; npx no Playwright → blocked
- [x] Named reports only when native reporter file exists
- [x] r1–r4 REQUIRED closed at tip `194a6620d8fbe501963b2b341d514944428bd6a3`
- [x] Combined r5 CLEAN; Main+Pr57R5Reviewer+advisor CONTENT CLEAN; REQUIRED_CHANGES=none
- [x] locks Q1B Q2A Q3A Q4A Q5A Q6A
- [x] Fence held

## Closeout

Scheme A finish on #57. Archive with the grill sibling. `docs/TODO.md` merge-SHA backfill is a post-squash chore if still pending.
