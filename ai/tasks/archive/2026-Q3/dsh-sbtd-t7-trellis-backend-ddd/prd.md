# PRD -- dsh-sbtd T7 Trellis backend FS primitives

## Background

T7 delivers an internal Trellis Backend Module at `packages/dsh-sbtd/src/backends/trellis.ts` for filesystem primitives beside the SBTD control plane. DDD Status **confirmed** (`/workspace/omp-tasks/t7-trellis-backend-ddd.md`, session `01a08092`). Grill ROUND1_COMPLETE with Q1C-Q6B locked.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t7-trellis-backend`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/45
- Fence Q5A: **only** `src/backends/trellis.ts` + module tests. No `index.ts` apply wiring, no new `sbtd_*`, no `docs/prd` edits, no Channel, no `trellis init`, no T8.

## Locked Q1-Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | C | `detect` = `{exists, cliOnPath, workflowPresent}` independent; missing CLI does not flip `exists`; never throws |
| Q2 | B | FS-first I/O; `trellis` binary ONLY for `detect.cliOnPath` |
| Q3 | A | whitelist `prd.md`|`design.md`|`implement.md`; safe slug; sandbox escape throws |
| Q4 | A | session pointer only; never scan `in_progress` |
| Q5 | A | `trellis.ts` + tests only; no index apply; no `sbtd_*`; no docs/prd |
| Q6 | B | missing => structured; escape => throw (validate slug/name **before** missing-trellis) |

## Non-goals

- index apply / sbtd tools
- Channel / trellis init / T8
- omp config / providers / registry publish
- host pin retarget
- docs TODO backfill (later chore)

## Acceptance

- [x] detect returns three independent booleans; never throws; missing CLI does not flip exists
- [x] readWorkflow / currentTask / writeArtifact are filesystem-only
- [x] writeArtifact whitelist only prd.md|design.md|implement.md under safe slug; sandbox escape throws
- [x] Q6B: assertSafeSlug/whitelist before structured missing-trellis
- [x] currentTask is session pointer only; empty when absent; never scans in_progress
- [x] TRELLIS_CONTEXT_ID sanitizeKey matches Trellis _sanitize_key
- [x] No index apply / no new sbtd tools / host pin unchanged
- [x] PR #45 tip e9bc7cb; review r3 CLEAN REQUIRED_CHANGES=none; residual symlink-at-tasks-dir not REQUIRED
- [x] tests 136 pass (lint/typecheck/build/test green)

## Closeout

Scheme A finish on #45. Archive this task. docs/TODO.md SHA backfill is a separate post-merge chore (same pattern as #44 after #43).
