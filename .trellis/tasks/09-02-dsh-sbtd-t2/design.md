# T2 design

## Boundary

Host-facing Cordis plugin in `packages/dsh-sbtd`. T2 adds `sbtd_plan` on T1 section + session Map. Hooks stay absent.

## Contract

`apply(ctx)` logs, `registerSection(ctx)`, `registerPlanTool(ctx)`.

`ctx.tools.register(definition)` with name `sbtd_plan`, `task_summary` required, `facts` optional array.

`execute(args, exec)` → `sbtdPlan(sessionIdFromExec(exec), args)`.

Session: T1 `getSession`. `sessionId` = `exec.agent.id` or `"default"`.

`taskId` = slug of `task_summary`.

Infer each of ddd|ddia|legacy|refactor|release from objective regex predicates on summary+facts.

Merge on same `taskId`: keep previous `running|blocked|planned|passed` when still required; if required→on-demand after `passed`, set `not-required` and fact `trigger fact disappeared; reset passed`.

Return `{ plan, markdown }`. Markdown is a Book Gate Plan table.

No fs. No AGENTS.md. Validate default on session is untouched by the tool except `plan`.

## Non-goals

Hooks, other tools, inject agents, publish, T3.
