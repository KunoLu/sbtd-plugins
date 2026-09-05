# T5 known gaps / follow-ups (accepted deferred)

Park-as-follow-ups-only except Follow-up (a), which is **resolved by PR #33**.
**Not** CLEAN concealment. Do **not** implement (b) or (c) in this T5 task / PR 30 docs pass.

Head: `87572c5e5cde9ef23a65bd19ff369530978e6f97` on `feat/dsh-sbtd-t5`.

Same content as `prd.md` section **Known gaps / follow-ups (accepted deferred)**.

## Locked fixed on this head (Security already passed)

Do not reopen as T5 product work:

- On-demand → required promotion resets an inherited pass.
- Required + passed resets when the catalog trigger fact changes.
- A → B → C catalog-fact keep-pass hole is closed: catalog fact is retained on the gate across reset / review.

## Follow-up (a) — remediation deadlock — resolved by PR #33

Resolved by PR #33 on `feat/dsh-sbtd-fu1-remediation-write`.

- Hooks now scoped-allow production writes when `reviewStatus` is `seam-required` (legacy) or `refactor-first` (refactor).
- Gate stays `running`: `mapGateState` / `RUNNING_STATUS` / `requirement` / `review.ts` untouched.
- Whole-window allow: no byte-level seam-vs-feature classifier. Opening the window allows all production-class writes while that `reviewStatus` is set.
- Q4A still-deny-non-remediation is honor/prompt only (not hook-enforced).

## Follow-up (b) — review order not enforced

`sbtd_review` does not enforce legacy-before-refactor when both are `required`. Follow-up.

T3 deny still points at legacy first; that is not `sbtd_review` enforcement.

## Follow-up (c) — multi-fact / `PREDICATES[kind].find` first-match

When facts accumulate (e.g. persist then persist+schema), only the first catalog fact is stored via `PREDICATES[kind].find`, so expanded triggers may not reset a required pass.

Deferred follow-up. Locked T5 tests replace facts arrays per re-plan. Adjudicated **not** a merge blocker this round. No code change to `plan.ts` in this docs pass.

