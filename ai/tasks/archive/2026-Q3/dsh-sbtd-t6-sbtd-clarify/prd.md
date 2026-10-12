# PRD — dsh-sbtd T6 `sbtd_clarify`

## Background

DSH models must interview through `sbtd_clarify`, not by calling grill skills. Locked DDD r2 (`/workspace/omp-tasks/t6-ddd-r2.md`, Status **confirmed**) closes Q1–Q11.

Canonical names: **Clarify Mode**, **Interview Reset**, **Clarify Complete**, **Clarify Partial**, **Forced Docs DDD**, **Current Question**, **clarifyStatus**.

## Scope

- Package: `packages/dsh-sbtd`
- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2`
- Branch: `feat/dsh-sbtd-t6-sbtd-clarify`
- Package version stays `0.1.0-rc.1`

## Behavior

1. First `sbtd_clarify` in a session requires `mode` `docs|generic`. Later omitted `mode` inherits. A different `mode` throws until Interview Reset.
2. Interview Reset is an explicit `reset` flag on `sbtd_clarify`. Compaction is not Reset. A new DSH session id is a different Map entry.
3. One Current Question per call (singular input and output).
4. Clarify Complete = empty frontier **and** explicit user confirmation. Loading manuals / SKILL.md is never Complete by itself.
5. Partial may run with no Book Gate Plan. Attempting Complete without a plan throws.
6. Docs Complete only: emit a PREDICATES-matching haystack fact via `sbtdPlan` / `inferRequirements` so `ddd` becomes `required`; call shared `sbtdReview` (`kind=ddd`). No shadow write. No FU3 PREDICATES rewrite. Partial must not call review.
7. Generic Complete: no auto DDD, no grill-with-docs haystack fact, no forced `sbtdReview`.
8. Complete ∧ required DDD ≠ `confirmed` → one-shot blocked return (no PRD/实现 suggestion). Complete stays terminal; further `sbtd_clarify` is not the resume path unless Reset.
9. Persist Clarify Mode bind + `clarifyStatus` on `SbtdSessionState` and `SbtdHandoffSnapshot`; `serialize`/`restore` both.
10. Narrow section Forced DDD prose to docs-mode Complete only.

## Non-goals

- T7 Trellis backend, T8 spec/tickets stubs
- FU3 PREDICATES rewrite
- `hooks.ts` write-order / `mapGateState` / FU1 `remediationAllow`
- Weaken T3 ddd deny
- `docs/CONTEXT.md` / ADR disk writes
- Registry publish, omp settings, host retarget

## Locked Q1–Q11

| Q | Lock |
|---|---|
| Q1 B | First call binds `docs\|generic`; later omit inherits; switch throws until Reset |
| Q2 B | Forced DDD is `mode=docs` Complete only |
| Q3 B | One Current Question per call |
| Q4 D | Complete = empty frontier ∧ user confirm; manuals ≠ Complete |
| Q5 C | Partial without plan OK; Complete requires plan |
| Q6 A | Fence: clarify + register + tests/features |
| Q7 A | Docs Complete records DDD via shared `sbtdReview` |
| Q8 A | Docs Complete elevates `ddd` via PREDICATES haystack fact |
| Q9 A | Mode + `clarifyStatus` on state and snapshot; compaction restores both |
| Q10 A | Complete ∧ DDD ≠ confirmed → one-shot blocked; Complete terminal |
| Q11 B | Interview Reset = explicit reset flag |

## Acceptance

- [x] First call omit `mode` throws; bind `docs` then omit inherits (`t6-clarify.test.mjs` / `t6-sbtd-clarify.feature`)
- [x] Later `generic` while bound `docs` throws until explicit reset; after reset rebind allowed (covered)
- [x] Compaction/restore keeps mode bind and `clarifyStatus` (covered)
- [x] Docs Complete forces DDD via mapper **and** haystack elevate (`ddd` required) (covered)
- [x] Generic Complete does not auto-require DDD and does not emit grill-with-docs fact (covered)
- [x] Return shape is one Current Question (covered)
- [x] Empty frontier without user confirm stays Partial; manuals-only is not Complete (covered)
- [x] Partial without plan OK; Complete without plan throws (covered)
- [x] Complete ∧ DDD ≠ confirmed → one-shot blocked; further clarify not resume (covered)
- [x] T3 still denies production writes when required `ddd` is unpassed (covered; T3 deny unchanged)
- [x] Section prose is docs-Complete only (covered)
- [x] `biome check src`; typecheck; package tests **105/105** (verified on PR head `d2510c9`)
- [x] PR https://github.com/KunoLu/sbtd-plugins/pull/39 — scheme A same-PR finish; group vote **A**; `REQUIRED_CHANGES=none`; review concerns → FU3 persist-across-replans / mergeGate demote; host pin `@deepseek-ai/dsh@0.1.1-rc.2`; Q1–Q11 locked; package not published
