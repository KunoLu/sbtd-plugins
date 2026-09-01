# omp-sbtd Command Surface

> How `/sbtd` commands are defined and rendered. Source: `packages/omp-sbtd/src/commands/index.ts`.

---

## One Table Drives Everything

`sbtdCommandSpecs` is a declarative readonly table. Each `SbtdCommandSpec` carries:

- `path` (e.g. the `/sbtd …` subcommand path), `aliases`
- `category: "Control" | "Onboard" | "Information"`
- `summary`, `usage`, `examples` — the help text shown to users
- `mutates: boolean | "conditional"` and `requiresConfirmation`
- `availableIn: readonly EnvironmentMode[]` — which environment modes expose the command

Four functions derive from this one table: `parseSbtdCommand` (discriminated `ParseResult`,
unknown input returns suggestions), `completeSbtdCommand`, `suggestSbtdCommand`,
`renderSbtdHelp`. Dispatch in `src/extension.ts` (`handleCommand`) matches on
`parsed.spec.path.join(" ")`. **Help, completion, suggestions, and dispatch cannot drift** —
adding a command means adding one table entry, not touching four places.

## Rules

1. **New command = new table entry + dispatch branch + `.feature` Scenario + mirrored test.**
   Do not add free-standing help strings or separate completion lists.
2. **Help paths never call the model and never mutate session state** — `mutates: false`
   informational commands must stay side-effect free.
3. **Read-only commands get the rejecting adapter.** `handleCommand` hands status/doctor-class
   commands a `readOnlyFiles` FileAdapter whose `writeAtomic` / `makeDirectory` / `remove` reject
   (`src/extension.ts:1505-1525`). If your command is read-only, wire it through that path.
4. **Unknown commands fail with candidates, not silence** — the parser returns suggestions derived
   from the table; keep `aliases` accurate so suggestion quality stays high.
5. **User-facing messages** go through `ctx.ui.notify(message, "info" | "warning")`
   (`src/extension.ts:1472-1485`). Never `console.log`.

## Tests

Command surface behavior is covered by `test/commands-state.test.ts`,
`test/command-surface-notify.test.ts`, and `test/report-command.test.ts`, mirroring
`features/sbtd-control-bootstrap.feature` and `features/validation-report-provider.feature`.
