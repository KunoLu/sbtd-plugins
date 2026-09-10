# Design -- T12 Maestro 预检

## Modules

- `packages/dsh-sbtd/src/backends/maestro.ts` -- `preflight` / `defaultDetectJava` / `defaultDetectCli` / `defaultDetectDevice` / `pickModelInput` / `simctlHasBootedDevice`
- `packages/dsh-sbtd/test/t12-maestro.test.mjs`
- `state.ts` `session.maestro` consumed as-is (no slice schema change)

## Decisions (locked)

1. Q1A -- hybrid six-step; never `maestro test`.
2. Q2A -- backend-only; no apply register.
3. Q3A -- preflight may write session.maestro; no flow files.
4. Q4A -- host cwd; model platform hint only.
5. Q5A -- tests stub detect.
6. Q6A -- cloud declaration-only.
7. r1–r3 -- local class is hint; `(Booted)` only; guidance; stub detect.

## Out of scope

T13 e2e, CONTEXT paste, `docs/prd` body, residuals in FOLLOWUPS.
