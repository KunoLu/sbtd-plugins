# T3 design

## Boundary

Host-facing Cordis plugin in `packages/dsh-sbtd` only. T3 adds `src/hooks.ts` and registers it from `apply()` on T2 `sbtd_plan` + T1 session Map. No extra `sbtd_*` tools, backends, or commands.

DSH 0.1.1-rc.2 loads `name` / `inject` / `apply`. Hooks use local `HooksHost.on`. Do not import `@deepseek-ai/dsh` types. `inject` stays `["tools", "systemPrompt"]`.

## Contract

```ts
export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export function apply(ctx: PluginHost): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  registerSection(ctx);
  registerPlanTool(ctx);
  registerHooks(ctx);
}
```

Local `PluginHost = SectionHost & ToolsHost & HooksHost`.

### hooks.ts

- `ctx.on("tools/pre-execute", (exec, next) => …)`
- `ctx.on("agent/pre-step", (payload, next) => …)`
- Allow by returning `next()`. Intercept with `{ kind: "ask" | "deny", reason }`.
- Session: `sessionIdFromExec` + T1 `getSession`.
- Mutation tools: `write` / `edit` / `str_replace_editor` / mutating `bash`.
- Production path: under cwd `src/` `app/` `packages/`, non-`*.md`.
- README / `*.md`: allow via `next()`.
- `git commit|status|log|diff|show` (no chain): allow.
- No plan + production or exempt path: ask `sbtd_plan`.
- Required unpassed: deny `sbtd_review kind=legacy|refactor|ddd|ddia|release`.
- Order on impl edits: legacy → refactor → ddd. DDIA only data path. Release does not block edits; publish-class bash denied.
- Exempt from hard deny: `*.test.*` / `*.spec.*` / `features/` / `maestro/flow/` / `.trellis/` (still ask without plan).
- `rm` production/other or pkg-mgr touching `src|app|packages`: ask.
- pre-step: `await next()` first. If no plan and development intent, append plugin notice. Do not originate `reject`; pass through non-enter from `next()`.
- `passed` means `state === "passed"`.

## Data flow

Read-only: `getSession(sessionId).plan`. No new persisted store.

## Non-goals

No extra `sbtd_*` tools, no publish, no `trellis init --dsh`, no 0.1.2-alpha, no root README, no lockfile, no path install.

## Compatibility / rollback

Pin is exact `0.1.1-rc.2`. Rollback is revert the package files. `dist/` stays gitignored. T0/T1/T2 apply tests stub `on()`.

## Book Gate Plan

| Gate | Requirement | State | Fact |
|---|---|---|---|
| ddd | on-demand | not-required | no completed grill-with-docs |
| ddia | on-demand | not-required | read-only session.plan |
| legacy | required | characterized | apply() now requires host `on()` |
| refactor | required | proceed | existing `src/index.ts` apply |
| release | on-demand | not-required | private unpublished package |

## Gate reviews (design-time)

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: T1 in-process Map; T3 only reads plan
Write / read / async / failure paths: none written; getSession read
Consistency model: same sessionId as sbtd_plan
Required tests: t3-hooks.test.mjs vs dist/
```

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: apply() also registers hooks via ctx.on
Behavior to preserve: name/inject tools+systemPrompt; T0 log; section; sbtd_plan; no fs/AGENTS.md; peer 0.1.1-rc.2
Current reproduction evidence: T0/T1/T2 apply hosts lacked on()
Safety net: stub on() in those tests; t3-hooks.test.mjs vs dist/
Hidden dependencies / seam: host ctx.on
Validation plan: biome check src; tsc --noEmit; tsc; node --test test/*.test.mjs
Review mode: normal
```

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/src/index.ts apply()
Behavior that must remain unchanged: section + sbtd_plan registration; inject tuple
Structural friction: none
Decision and smallest safe step: no extra refactor; add registerHooks(ctx)
Safety net and validation: node:test + tsc
Deferred refactors: none
```
