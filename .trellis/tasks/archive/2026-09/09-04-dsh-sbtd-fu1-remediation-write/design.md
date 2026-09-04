# Design — FU1 Remediation Write

## Boundaries

- Adapter: `packages/dsh-sbtd/src/hooks.ts` `gatePreExecute`
- Do not change `tools/review.ts` `mapGateState` / `RUNNING_STATUS` / `PASS_STATUS` / `ReviewInput`
- Session field already exists: `BookGatePlan.gates.*.reviewStatus?`

## Contract

After production PathClass checks, extend legacy/refactor unpassedRequired denies:

```
remediationAllow(gate, status) → gate.reviewStatus === status

if unpassedRequired(legacy) && !remediationAllow(legacy, "seam-required") → deny legacy
if unpassedRequired(refactor) && !remediationAllow(refactor, "refactor-first") → deny refactor
```

ddd/ddia/release unchanged. EXEMPT/readme unchanged. Legacy-first order stays.

## Honesty

Whole-window scoped allow. No classifier. Q4A honor-only.

## Rollback

Revert the hook helper and the two skip conditions. Existing T3 deny tests remain the contract for non-window writes.

## GitNexus (refreshed)

`gatePreExecute` / `unpassedRequired` upstream risk LOW. Callers: `registerHooks` → `apply`. Index refreshed this session.
