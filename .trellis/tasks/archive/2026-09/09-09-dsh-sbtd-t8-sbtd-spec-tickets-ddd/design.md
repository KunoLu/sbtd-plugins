# Design -- T8 sbtd_spec / sbtd_tickets

## Modules

- `packages/dsh-sbtd/src/tools/spec.ts` -- `sbtd_spec` (prd.md)
- `packages/dsh-sbtd/src/tools/tickets.ts` -- `sbtd_tickets` (implement.md)
- `packages/dsh-sbtd/src/tools/task-artifact.ts` -- shared write/draft/block path
- `packages/dsh-sbtd/src/index.ts` -- `apply()` registers both after plan/review/clarify

Consume T7: `detect` / `currentTask` / `writeArtifact`. Do not change T7.

## Decisions (locked)

1. Q1C -- explicit slug preferred; else strip `.trellis/tasks/` from pointer; never pass pointer into `writeArtifact`.
2. Q2A -- required ∧ unconfirmed DDD refuses before detect/write; same blocked object as T6 Complete (`suggestPrd: false`).
3. Q3A -- write vs draft uses `detect.exists` only. Never `docs/`. Never `trellis init`.
4. Q4A -- whitelist binding: spec=`prd.md`, tickets=`implement.md`. Slices are markdown, not Trellis children.
5. Q5A -- both files exist and both register from `apply()`.
6. Q6A -- no usable slug ⇒ draft + structured note; no throw.
7. Empty body -- throw before persistence (r1 required; sibling of `sbtd_plan` empty-summary guard).

## Out of scope

Child-task creation, physical-realpath symlink sandbox (FOLLOWUPS residual), T5 scenario title wording nit, `docs/prd` parent/child table, CONTEXT paste.
