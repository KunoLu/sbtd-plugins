# PRD -- dsh-sbtd T11 sbtd_bdd

## Background

T11 delivers the model-facing tool `sbtd_bdd` at `packages/dsh-sbtd/src/tools/bdd.ts`. DDD Status **confirmed** (`/workspace/omp-tasks/t11-sbtd-bdd-ddd.md`). Grill ROUND1_COMPLETE with Q1C–Q6A locked.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2` (do not retarget)
- Branch: `feat/dsh-sbtd-t11-sbtd-bdd`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/53
- Fence Q6A: `src/tools/bdd.ts` + `apply()` `registerBddTool` + `test/t11-bdd.test.mjs` (+ tools.length / tools-dir whitelist + optional `docs/TODO.md` tip). No manuals/gherkin-bdd nest, no `session.bdd`, no `validate.ts` rewrite, no MCP, no npm, no `docs/prd` rewrite.

## Locked Q1-Q6

| Q | Lock | One-line |
|---|---|---|
| Q1 | C | Model: `intent` + slug or cwd-relative `.feature` path; extra_paths for sync/read only, host-validated. Host injects cwd. T10 keys forbidden |
| Q2 | B | Existing features/ conventions win; plugin fixtures not consumer SoT |
| Q3 | A | `bdd.ts` + `registerBddTool` from `apply()` |
| Q4 | A | Spec/tickets never override `.feature`; no validate.ts change |
| Q5 | A | `read` local catalog, Mutation none |
| Q6 | A | No manuals nest; no `session.bdd` |

## Non-goals

- T12/T13 Maestro/e2e; knowledge-base-integration productization
- Channel / `trellis init` / MCP config writes
- omp config / providers / registry publish
- host pin retarget
- T7/T8/T9/T10 reopen / `docs/prd` rewrite
- docs/TODO merge-SHA backfill (post-merge chore)

## Acceptance

- [x] Model schema: `intent` + `target` + optional content/body; extra_paths / cross_repo_required only for sync/read; host injects cwd
- [x] T10 keys (`cwd` / `mcp` / `runRefresh` / `serverName` / `toolNames`) not model-visible
- [x] extra_paths default-deny without host `allowedExtraRoots` (R1)
- [x] `intent=sync` blocked (`sync-not-capable`); inventory-only is not success (R2)
- [x] Relative write targets require `.feature` suffix (R3)
- [x] Multi-tree: no `found[0]`; discovery-cap does not hide a second tree (R4)
- [x] Realpath containment; `cwd/specs` dir-symlink blocked; symlink `features/` not convention root; dangling `.feature` symlink rejected (R5)
- [x] `read` ⇒ Mutation none; S1 Chinese 功能/场景 catalog keywords
- [x] `apply()` `registerBddTool`; no manuals/gherkin-bdd; no `session.bdd`; no validate rewrite
- [x] r1–r5 REQUIRED closed at tip `975d878220e67a0a3b79f85461565079ee2edbc4`
- [x] Combined r5 CLEAN; Main+Pr53R5Reviewer CLEAN/correct; Advisor no content verdict (CLEAN ≠ advisor approval); REQUIRED_CHANGES=none
- [x] locks Q1C Q2B Q3A Q4A Q5A Q6A
- [x] tests: 228/228 green (per r5)
- [x] Fence held: `packages/dsh-sbtd/src/tools/bdd.ts` + `src/index.ts` apply register + `test/t11-bdd.test.mjs` (+ related tools.length/whitelist)
- [x] No extra `sbtd_*` beyond `sbtd_bdd` / no docs/prd / host pin unchanged / no MCP writes / no npm

## Closeout

Scheme A finish on #53. Archive this task with the grill sibling. `docs/TODO.md` merge-SHA backfill is a separate post-merge chore if still pending after squash.
