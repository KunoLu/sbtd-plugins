# Design -- T10 sbtd_validate

## Modules

- `packages/dsh-sbtd/src/tools/validate.ts` -- `sbtdValidate` / `discoverProjectTestCommand` / `resolveValidateHost` / `createToolsMcpBridge` / `bindBridgeOuter`
- `packages/dsh-sbtd/src/index.ts` -- `apply()` `registerValidateTool(ctx, resolveValidateHost(ctx))`
- `packages/dsh-sbtd/src/tools/plan.ts` -- `PlanToolExec` / `ToolsHost.execute` identity types for nested dispatch
- `packages/dsh-sbtd/test/t10-validate.test.mjs` -- tool tests
- T9 `packages/dsh-sbtd/src/backends/gitnexus.ts` consumed as-is

## Decisions (locked)

1. Q1A -- model-visible args = phase + optional target/direction/scope. Host injects cwd + GitNexusOptions.
2. Q2A -- pre = impact only; post = detectChanges then project tests.
3. Q3A + clar. -- skip/advisory never post=blocked; pre skipped vs done mapping; abort ≠ blocked.
4. Q4A -- Return Envelope; no-script never fake passed.
5. Q5A -- register from apply; no gitnexus.ts rewrite.
6. r1 -- production host GitNexus inject; non-Node AGENTS/README commands.
7. r2 -- multi-candidate docs: project-type then earliest position; cancel ≠ blocked on spawned runner.
8. r3 -- nested execute forwards agent + parent token + rootCallId; throwIfAborted before post; regex advance; package-lock.json Node marker.

## Out of scope

T9 gitnexus.ts rewrite, CONTEXT paste, `docs/prd` body, residuals listed in FOLLOWUPS.
