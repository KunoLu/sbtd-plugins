# T0 design

## Boundary

Host-facing Cordis plugin stub in `packages/dsh-sbtd` only. DSH 0.1.1-rc.2 loads `name` / `inject` / `apply` plus `dsh.bundle.patch` → `cordis.patch.yml`.

## Contract

```ts
type T0Context = {
  systemPrompt: {
    section: (opts: { name: string; order: number; text: string }) => void;
  };
};

export const name = "dsh-sbtd";
export const inject = ["tools", "systemPrompt"] as const;

export function apply(ctx: T0Context): void {
  console.log("[dsh-sbtd] plugin loaded (T0 stub)");
  ctx.systemPrompt.section({ name: "sbtd", order: 50, text: "" });
}
```

Local `T0Context` only. Do not import `@deepseek-ai/dsh`, `@deepseek-ai/cordis`, or any 0.1.2-alpha package.

## Package surface

- `package.json`: `@kunolu/dsh-sbtd`, `type: module`, `main: ./dist/index.js`, `dsh.bundle.patch`, peer `@deepseek-ai/dsh` `0.1.1-rc.2`, `files`: `dist`, `cordis.patch.yml`, `manuals`, Apache-2.0, `private: true`.
- `cordis.patch.yml`: insert `id: sbtd`, `name: @kunolu/dsh-sbtd` (Node import of the installed package). Plugin export `name` stays `dsh-sbtd`.
- `manuals/.gitkeep` only. No real manuals content.
- README pins `0.1.1-rc.2` and documents `dsh plugin --profile web add <path>`.

## Non-goals in this change

No `src/section.ts`, `src/state.ts`, tools, hooks, commands, backends, disk writes, `AGENTS.md`, Maestro, KPi, dotenv, `trellis init --dsh`.

## Compatibility / rollback

Pin is exact `0.1.1-rc.2`. Rollback is revert the package files. `dist/` stays gitignored.
