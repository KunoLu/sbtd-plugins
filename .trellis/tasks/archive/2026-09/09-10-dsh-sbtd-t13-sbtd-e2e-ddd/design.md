# Design -- T13 sbtd_e2e

## Modules

- `packages/dsh-sbtd/src/tools/e2e.ts` -- `sbtdE2e` / `registerE2eTool` / `resolveE2eHost` / `preflight` consumer of T12
- `packages/dsh-sbtd/test/t13-e2e.test.mjs`
- `index.ts` `apply()` `registerE2eTool`

## Decisions (locked)

1. Q1B -- three actions; hybrid = 混合 App; web skips T12; mobile|hybrid re-call T12.
2. Q2A -- apply register; manuals deferred.
3. Q3A -- convention-win; unit tests stub.
4. Q4A -- model knobs vs host trust.
5. Q5A -- fence e2e.ts + apply + tests; no maestro.ts rewrite.
6. Q6A -- blocked vs failed; mode labels; no steal.

## Out of scope

T14 lessons, manuals nest, `docs/prd` body, residuals in FOLLOWUPS.
