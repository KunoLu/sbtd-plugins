# Changelog

All notable changes to `@kunolu/dsh-sbtd` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); newest
first. Chinese mirror: [CHANGELOG.zh.md](CHANGELOG.zh.md).

## [0.2.0-rc.1] - 2026-10-19

### Added

- **Graft analysis backend** (`sbtd_validate` pre/post phases). Read-only
  queries go through the already-wired managed launcher (default server
  name `sbtd-graft`), probed by the `mcp__<server>__graft_*` tool prefix;
  the backend calls `graft_check_freshness` and, gated on freshness,
  `graft_find_code`. The plugin never spawns, initializes, or configures
  Graft itself. Every unavailable path returns `status: "skipped"` with
  one of six reasons —
  `launcher-missing`, `version-unsupported`, `call-failed`,
  `guard-failed`, `graph-missing`, `graph-stale` — and never blocks plugin
  load. Under `strict` workflow mode a skipped Graft phase is reported as
  `graftEvidence: "未证明"` (unproven), never as passed. An empty graph
  result is not treated as proof of no impact.
- **sbtd-task read layer and layered workflow mode resolution.** Mode is
  resolved from: tool argument / host-injected `workflow_mode` → the
  `workflow_mode` field of the task file pointed at by the active-task
  pointer (read-only) → `default`. `sbtd_plan`, `sbtd_review`, and
  `sbtd_validate` now return `workflowMode` and `workflowModeSource`; the
  `/sbtd` status output shows them; hook notices carry the mode and its
  source layer. A missing pointer, missing/corrupt task file, or a branch
  mismatch falls back to `default` with the reason stated (branch mismatch
  additionally notes the task belongs to another branch) — no error, no
  load refusal.
- **Lessons v2.** Identity file is `.sbtd/developer` (`name=<name>`,
  `^[a-z0-9]+$`, never guessed; linked worktrees probe the main checkout
  read-only; symlinked identity sources are refused). Record resolution
  chain: existing `docs/lessons/index.md` layered store → existing
  `docs/spec/lessons.md` short entry → flat `docs/lessons.md` returns a
  migration skip (match/read still work) → otherwise a new
  `docs/lessons/` layered store is created. A legacy `.trellis` lessons
  tree is read-only, recognized by `.trellis/lessons/index.md` alone.
  Lesson event kind `gitnexus-mismatch` is renamed to `graft-mismatch`.
- **V4 host adaptation.** Pre-step notices are emitted with the V4 source
  kind `'dsh-sbtd'` while the legacy kind `'plugin:dsh-sbtd'` is still
  recognized on read; `runPreStep` preserves `startsRequestSeries` so the
  host's request-series semantics survive the decision round-trip.
- **sbtd-task manual** synced from `640-skills` `v2.0.2`
  (`1d82494d74f6df9bca7dccef2da409f87091883e`): `SKILL.md` plus the full
  `references/` tree including `task-data.schema.json`.
- **Two-row REQUIRED host-compat CI.** The `dsh-host-compat.yml` unit-pack
  gate now runs a pinned register smoke against both `@deepseek-ai/dsh`
  `0.2.0-rc.2` and `0.2.1-rc.2` (both REQUIRED, `workflow_dispatch`, red
  stops the line).

### Changed

- **Host range.** `peerDependencies["@deepseek-ai/dsh"]` and
  `engines.dsh` carry the same range `>=0.2.0-rc.2 <0.3.0-0`; the
  devDependency stays exactly pinned at `0.2.0-rc.2`. dsh 0.2.0-rc.2
  checks only `peerDependencies`; from 0.2.1-rc.2 on, `engines.dsh`
  decides and peers are ignored — the two fields must therefore match.
- **`sbtd_validate` contract field rename:** the analysis result field
  `gitnexus` is now `graft` (same `AnalysisResult` shape:
  `ok | skipped | advisory` + `summary` + optional `reason`). No dual
  field is kept; migrate consumers to `graft`.
- **Mode-gated enforcement.** Under `strict`: production edits without a
  plan still ask, and failed required book gates still deny. Under
  `default`/`lite`: the no-plan edit still asks, but a failed required
  book gate downgrades to an injected notice and does not block. The
  sbtd section text is now neutral static wording describing both
  behaviors instead of unconditional enforcement language.
- **Draft-only planning tools.** `sbtd_spec`, `sbtd_tickets`, and
  task-artifact writes no longer touch `.trellis/**`, `.sbtd/**`,
  `ai/tasks/**`, or any task file — they return drafts only. The task
  record writer stays sbtd-task's TaskStore.
- **Manuals supply chain.** `sync-manuals.sh` is pinned to `640-skills`
  `v2.0.2` (`1d82494d`); the MANIFEST now records a per-file sha256 for
  every synced file, and the byte-compare test covers the non-Markdown
  `task-data.schema.json`. The five `book-*` manuals are refreshed to the
  same pin.

### Removed

- **Trellis backend** and **GitNexus backend**, including the
  `trellis-workflow` manual. The plugin no longer writes `.trellis/**`
  artifacts; legacy `.trellis` lessons trees remain readable (see Lessons
  v2 above).

### Deployment boundary

- `npm install` of this plugin together with `@deepseek-ai/dsh@0.2.1-rc.2`
  can fail with `ERESOLVE`: npm's default peer resolution does not apply
  `includePrerelease`, so a prerelease peer range does not satisfy across
  patch-level prereleases (`0.2.0-rc.2` vs `0.2.1-rc.2`). The pnpm
  host-compat REQUIRED rows for both `0.2.0-rc.2` and `0.2.1-rc.2` pass.
- **The supported range stays `>=0.2.0-rc.2 <0.3.0-0`** — no retreat.
  Prefer installing via pnpm or the dsh plugin manager path; npm users on
  `@deepseek-ai/dsh@0.2.1-rc.2` may need a dependency override (e.g.
  `overrides` in `package.json`) to resolve the peer.

## [0.1.0-rc.3] - 2026-09-19

### Changed

- Synced manuals to `640-skills` `v1.0.15`
  (`bc8eec1549928fb0966254751b96b611b6334183`).
- Lesson writes resolve the author's split name from `.trellis/.developer`
  or the main worktree, append within that author's markers, and use
  `LESSON-YYYYMMDD-<name>-<slug>` IDs.

### Fixed

- Lesson lookup matches exact headings rather than longer-ID prefixes;
  topic fallback uses the enclosing author marker. Sanitization neutralizes
  forged lesson markers so content cannot escape its author's block.

## [0.1.0-rc.2] - 2026-09-13

### Added

- `sbtd_clarify`, `sbtd_spec`, `sbtd_tickets`, `sbtd_validate`, `sbtd_bdd`,
  `sbtd_e2e`, and `sbtd_lessons`, plus the human-facing `/sbtd` command.
- Trellis filesystem primitives, optional GitNexus analysis, and Maestro
  preflight support.

### Fixed

- Permit remediation writes while legacy/refactor gates require a safety
  seam or refactoring; enforce legacy review before refactoring.
- Preserve gate facts across replans and bind them to the matching set.
- Omit null `output.schema` values from clarify/spec/tickets results for
  host compatibility.

## [0.1.0-rc.1] - 2026-09-04

### Added

- Initial npm release for `@deepseek-ai/dsh@0.1.1-rc.2`, with a Chinese
  `sbtd` section, session state and handoff restoration.
- `sbtd_plan` and `sbtd_review`, plus `tools/pre-execute` and
  `agent/pre-step` hooks enforcing the Book Gate Plan.
- Read-only manuals synced from `640-skills` `v1.0.13`
  (`f8aa0d7225a26c5e00b81d2f1b05121108e63630`).
