# T2 design

## Boundary

Host-facing Cordis plugin in `packages/dsh-sbtd` only. T2 adds `sbtd_plan` on T1 section + in-process session Map. Hooks, other tools, backends, commands stay absent.

DSH 0.1.1-rc.2 loads `name` / `inject` / `apply`. Tool registration uses `ctx.tools.register` with a local ParameterSchemaSpec rc.2 shape. Do not import `@deepseek-ai/dsh` types.

## Contract

```ts
export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export function apply(ctx: PluginHost): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  registerSection(ctx);
  registerPlanTool(ctx);
}
```

Local `PluginHost = SectionHost & ToolsHost` only.

### plan.ts

- Name `sbtd_plan`.
- Parameters (ParameterSchemaSpec rc.2, implicit open object): `task_summary` `{ type: "string", required: true }`; optional `facts` `{ type: "array", items: { type: "string" } }`.
- Output: `{ type: "object", additionalProperties: false, properties: { plan: { type: "json" }, markdown: { type: "string" } } }`.
- `isConcurrencySafe` returns `false`.
- `execute(args, exec)` → `sbtdPlan(sessionIdFromExec(exec), args)`.
- Session id = `exec.agent.id` if non-empty string, else `"default"`.
- `taskId` = slug of trimmed `task_summary`. Empty / whitespace summary throws.
- Infer each of `ddd|ddia|legacy|refactor|release` from objective regexes on summary+facts (PRD 3.4).
  - DDD required only after completed `grill-with-docs`; bare `ddd` stays on-demand.
  - DDIA: persist / shared data / cache / async / cross-service.
  - Legacy: existing behavior bug / weak tests / unclear behavior / hidden deps / high regression.
  - Refactor: modify existing production code.
  - Release: production path / service / API / job / deploy.
- Same `taskId`: merge; keep `passed` (and `running|blocked|planned`) while still required; if a passed trigger disappears, set on-demand / not-required and write the disappeared reason.
- New `taskId`: new plan (do not keep previous passed).
- If both legacy and refactor hit, both are required. Order is a later task.
- No filesystem. No `AGENTS.md`.

## Data flow

Write: `sbtdPlan` → T1 `getSession(sessionId).plan`.
Read: same session id returns the same Map entry.
Handoff: T1 `serialize` / `restore` already hydrate; empty snapshot already clears `plan`. T2 does not rework `restore`.
Source of truth: in-process Map. No persist, cache, async, or cross-service store.

## Non-goals

No hooks, no other `sbtd_*` tools, no `inject: agents`, no publish, no `trellis init --dsh`, no 0.1.2-alpha, no root README, no path install.

## Compatibility / rollback

Pin is exact `0.1.1-rc.2`. Rollback is revert the package files. `dist/` stays gitignored.

## Book Gate Plan

| Gate | Requirement | State | Fact |
|---|---|---|---|
| ddd | on-demand | not-required | no completed grill-with-docs |
| ddia | on-demand | not-required | no persist / shared data / cache / async / cross-service in this change |
| legacy | required | planned | existing DDD predicate fires on bare ddd |
| refactor | required | planned | modify existing production `src/tools/plan.ts` |
| release | on-demand | not-required | no production path service / API / job / deploy |

## Gate reviews (design-time)

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: T1 in-process Map via getSession; T2 only assigns session.plan
Write / read / async / failure paths: sbtdPlan writes plan; getSession/serialize read; no async; no persist/cache/cross-service
Consistency model: single-process; same taskId merge; new taskId replaces plan
Idempotency / ordering / retry / deduplication: same taskId keeps passed while trigger remains
Schema / migration / backfill / rollback / replay: types only; rollback = revert module
Observability and repair: unit tests
Required tests: isolation, predicate, passed keep/reset, new taskId
```

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: DDD required must not fire on bare ddd; only after completed grill-with-docs
Behavior to preserve: name/inject; T0 log; section; T1 Map serialize/restore; no fs/AGENTS.md; no hooks; peer 0.1.1-rc.2
Current reproduction evidence: leftover PREDICATES.ddd includes /\bddd\b/i
Safety net: t2-plan.test.mjs vs dist/ after tsc; T0/T1 apply stubs tools.register
Hidden dependencies / seam: host ctx.tools.register; local ParameterSchemaSpec only
Validation plan: biome check src; tsc --noEmit; tsc; node --test test/*.test.mjs
Review mode: normal
```

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/src/tools/plan.ts PREDICATES.ddd; apply() already registers the tool
Behavior that must remain unchanged: session isolation; five gates; ParameterSchemaSpec rc.2; restore hydrate
Structural friction: none
Decision and smallest safe step: no extra refactor; delete non-3.4 DDD predicates
Safety net and validation: node:test + tsc
Deferred refactors: none
```
