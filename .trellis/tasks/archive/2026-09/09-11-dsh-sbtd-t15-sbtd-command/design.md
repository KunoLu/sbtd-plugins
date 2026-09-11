# Design — T15 /sbtd human command

## Handler contract

- Input: `CommandInvocation` (`rawInput` + `agent.id`) from `@deepseek-ai/dsh-commands@0.1.1-rc.2`.
- Output: `CommandResult` (`{ kind: "success", text }` | `{ kind: "error", text }`).
- Session id from `invocation.agent.id`, not slash argv.

## Modules

- `packages/dsh-sbtd/src/commands/sbtd.ts` — `parseSbtdArgv`, `runSbtdCommand`, `executeSbtdCommand`, `registerCommand`
- `packages/dsh-sbtd/src/index.ts` — `inject` adds `commands`; `apply()` calls `registerCommand`
- `packages/dsh-sbtd/test/t15-sbtd-command.test.mjs` — unit tests
- `packages/dsh-sbtd/features/t15-sbtd-command.feature` — persistent BDD (Chinese text, English keywords)

## Decisions (locked Q1A–Q6A)

1. **Q1A** — Three literals; not a model tool.
2. **Q2A** — Bare `/sbtd` read-only status via `getSession`/`serialize`.
3. **Q3A** — `/sbtd plan` views plan only (no `sbtdPlan`); `/sbtd maestro` calls injected `preflight()`.
4. **Q4A** — `FORBIDDEN_MODEL_KEYS` re-exported from `backends/maestro.ts`; host-injected `commandHost` for cwd/preflight.
5. **Q5A** — Package README only.
6. **Q6A** — Fence: command module + tests + README; consume T2/T12 as-is.

## R1 argv shape

DSH passes `rawInput` as text after the command name:

- `/sbtd` → `""` → status
- `/sbtd plan` → `"plan"`
- `/sbtd maestro` → `"maestro"`

`parseSbtdArgv` accepts only `""`, `"plan"`, or `"maestro"`. Rejects `sbtd`, `/sbtd`, `/plan`, `/maestro`, and trailing tokens.

## Q4A inject-pin fallout

Eleven existing tests assert `inject` includes `commands` and `commandHost` injection. These are required fallout of Q4A, not new product forks.
