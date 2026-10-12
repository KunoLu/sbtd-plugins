# T6 known gaps / follow-ups (accepted deferred)

Park-as-follow-ups-only. **Not** CLEAN concealment. Do **not** implement FU3 in this T6 task / PR 39.

Head: `d2510c966d3f0db13cbe20f34bccdcce1aa28fae` on `feat/dsh-sbtd-t6-sbtd-clarify`.

Advisor Advise2 / group vote **A**. `REQUIRED_CHANGES=none`. Do **not** patch `mergeGate` / `plan.ts` PREDICATES in #39.

## Locked on this head

Q1–Q11 remain locked. Q8 is **one-shot haystack elevate** on docs Clarify Complete (`完整执行 grill-with-docs` via `sbtdPlan` / `inferRequirements`). That one-shot is in scope for T6; persist-across-replans is not.

## Follow-up — persist-across-replans / mergeGate demote → FU3

After docs Clarify Complete, a later `sbtd_plan` with the **same summary** and **omitted facts** can drop Forced Docs DDD via `mergeGate` (`packages/dsh-sbtd/src/tools/plan.ts` ~256–263):

- Complete can leave `ddd` `required` + `blocked` (Q10 one-shot blocked; `clarifyStatus` stays `complete`).
- A replan whose haystack no longer matches the grill-with-docs PREDICATE infers `ddd` as on-demand.
- `mergeGate` then writes `requirement: "on-demand"`, `state: "not-required"`.
- T3 then allows production writes while `clarifyStatus` remains `complete`.

This is the same FU3 bucket as the existing T5 multi-fact `PREDICATES.find` first-match / set-expansion reset debt. Do not start FU3 coding from this PR.

## Not in this PR

- No `mergeGate` / PREDICATES rewrite
- No T7 / T8
- No hooks / `mapGateState` / FU1 `remediationAllow` change
