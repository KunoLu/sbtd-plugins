# T1 design

## Boundary

Host-facing Cordis plugin in `packages/dsh-sbtd` only. T1 adds the short resident section and in-process session state. Tools, hooks, commands, backends stay absent.

DSH 0.1.1-rc.2 loads `name` / `inject` / `apply`. Section registration uses `ctx.systemPrompt.section`. Empty section text is dropped by the host, so T1 text is non-empty.

## Contract

```ts
type PluginContext = {
  systemPrompt: {
    section: (opts: { name: string; order: number; text: string }) => void;
  };
};

export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export function apply(ctx: PluginContext): void {
  // log + registerSection(ctx); no fs, no AGENTS.md
}
```

Local `PluginContext` only. Do not import `@deepseek-ai/dsh`, `@deepseek-ai/cordis`, or any 0.1.2-alpha package.

### section.ts

- Export static Chinese plaintext plus `registerSection(ctx)`.
- `{ name: "sbtd", order: 50, text }`.
- Body = PRD 6.1 bullets only. UTF-8 byte length ≤ 2048. Non-empty.
- No `systemPrompt.context` registration.

### state.ts

PRD 6.3 types exactly:

- `GateState = "planned" | "running" | "passed" | "blocked" | "not-required"`
- `BookGatePlan` with `taskId`, `summary`, `gates` for `ddd|ddia|legacy|refactor|release`, optional `taskAutoExit`
- `SbtdSessionState` with optional `plan`, required `validate`, optional `maestro` (`missing: string[]` required when maestro present)

Runtime:

- Module-level `Map<string, SbtdSessionState>` keyed by caller `sessionId`.
- `getSession(sessionId)`: unknown id creates and returns isolated `{ validate: {} }`.
- `serialize(sessionId)`: at least `plan` and `maestro.missing`; no filesystem.
- `restore(sessionId, snapshot)` for roundtrip / handoff hydrate.
- Process restart / ESM re-import drops the Map.

## Data flow

Write: caller passes `sessionId` → Map entry (created on first get).
Read: same id returns the same object; other ids do not share it.
Handoff: `serialize` → JSON-safe snapshot → later `restore` after restart.
Failure: no persistence; restart is empty Map, not an error.
Source of truth: in-process Map for the live session; snapshot is a copy, not a second store.

## Package surface

- Keep `private: true`, peer `@deepseek-ai/dsh` `0.1.1-rc.2`, `files`: `dist/`, `cordis.patch.yml`, `manuals/`.
- `cordis.patch.yml` unchanged: `id: sbtd`, `name: @kunolu/dsh-sbtd`.
- `package.json` `test` glob covers `test/*.test.mjs`.
- README: pin + `@next` command + short Chinese `sbtd` section; no path install; no alpha.
- `.trellis/spec/dsh-sbtd/backend` directory layout updated for `section.ts` / `state.ts` / `test/` / `features/`.

## Non-goals

No tools, hooks, commands, backends, disk writes, `AGENTS.md`, `inject: agents`, `systemPrompt.context`, T2/T3, root README, publish.

## Compatibility / rollback

Pin is exact `0.1.1-rc.2`. Rollback is revert the package files in the T1 worktree. `dist/` stays gitignored. Original dirty unpublished-claim checkout is not part of this change.
