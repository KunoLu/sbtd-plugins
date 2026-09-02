# T0 implement

## Order

1. Add `packages/dsh-sbtd/features/t0-installable-stub.feature` (Chinese scenario text, English keywords).
2. Update `src/index.ts` with local `T0Context`, `inject`, log + empty section.
3. Update `package.json` peer / files. Keep `cordis.patch.yml`.
4. Add `manuals/.gitkeep`. Update README pin + local install command.
5. Add a node:test that traces the feature: `apply()` log + empty section, no extra files.
6. `pnpm --filter @kunolu/dsh-sbtd build` then `test` / `typecheck`.

## Validation

```bash
pnpm --filter @kunolu/dsh-sbtd lint
pnpm --filter @kunolu/dsh-sbtd typecheck
pnpm --filter @kunolu/dsh-sbtd build
pnpm --filter @kunolu/dsh-sbtd test
```

Live `dsh plugin --profile web add` is blocked: `dsh` CLI missing.

## Rollback

Revert `packages/dsh-sbtd` to the pre-T0 stub. Do not keep `dist/`.

## Gate reviews

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: apply() no-op; inject empty; README pins rc.7; package.json lacks files/peer.
Behavior to preserve: name "dsh-sbtd"; cordis insert id sbtd / name dsh-sbtd; private Apache-2.0; no AGENTS.md or disk writes; no T1 modules.
Current reproduction evidence: pnpm --filter @kunolu/dsh-sbtd build then node import of dist: name=dsh-sbtd inject=[] apply=noop.
Safety net: node:test of apply() log + empty section after tsc; no production seam.
Hidden dependencies / seam: host-loaded only; GitNexus apply callers=0 (UNKNOWN); grep found no in-repo imports.
Validation plan: pnpm --filter @kunolu/dsh-sbtd build && test && typecheck && lint
Review mode: normal
```

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/src/index.ts (noop stub), package.json, README.md
Behavior that must remain unchanged: name export, cordis patch id/name, no disk writes
Structural friction: none
Decision and smallest safe step: replace stub body in place; apply(ctx: T0Context) with unconditional section call; no refactor
Safety net and validation: node:test + tsc
Deferred refactors: none
```

```text
Release Readiness Review
Status: blocked
Production path and affected users / systems: DSH web profile loads @kunolu/dsh-sbtd apply()
Failure modes and safeguards: apply() assumes host injects systemPrompt; unproven on 0.1.1-rc.2
Capacity / backpressure / limits: not-applicable (T0 stub, no IO)
Observability / alerts / runbook: console.log on load only
Rollout / migration / rollback / cleanup: revert packages/dsh-sbtd; dist gitignored
Required validation and result: live DSH acceptance did not run (dsh CLI missing)
Optional checks, accountable owner acceptance, and residual risk: none accepted; required check cannot be waived
Unblock:
  dsh plugin --profile web add <path-to-packages/dsh-sbtd>
  dsh --profile web --dump-config   # must show id: sbtd
  dsh web                           # process starts, no failOnStartupError
```
