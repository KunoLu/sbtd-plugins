# Design — FU2 Review Recording Order

## Boundaries

- Adapter: `packages/dsh-sbtd/src/tools/review.ts` `sbtdReview`
- Do not change `mapGateState`, `PASS_STATUS`, `RUNNING_STATUS`, `requirement`
- Do not change `hooks.ts` Write Deny Order or FU1 `remediationAllow`
- No new persisted fields (`reviewMode` stays unpersisted)

## Contract

After kind/status/plan validation, before `gate.state = mapGateState(status)`:

```
if kind === "refactor"
  && gates.legacy.requirement === "required"
  && gates.refactor.requirement === "required":
    if legacy.state === "passed" → allow
    else if legacy.reviewStatus === "seam-required" && status === "refactor-first" → allow
    else throw Q5B Error (no mutate)
```

Q5B copy shape:

`sbtd_review: refactor recording is blocked until legacy.state is passed (live legacy.state=…, legacy.reviewStatus=…). Call sbtd_review kind=legacy first.`

Must not reuse T3 `required gate 未 passed，请先调用 sbtd_review kind=…`. Must not name skill ids.

## Rollback

Revert the order predicate in `sbtdReview` plus T5 feature/test cases. Existing single-kind proceed tests remain the contract.

## GitNexus

`sbtdReview` upstream risk LOW. Direct caller: `createReviewTool.execute`. Index 3 commits behind HEAD; `review.ts` unchanged since grill. Advisory only if analyze cannot refresh.
