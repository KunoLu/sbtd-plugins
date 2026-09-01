# omp-sbtd Frontend Guidelines

> Reshaped layer: this package has **no UI / no React**. "Frontend" here means the
> **agent-facing and user-facing surface** of the extension: `/sbtd` command text, help and
> completion, rendered reports, runtime markers, and `ctx.ui.notify` messages. Implementation
> conventions (registries, zod, errors, testing) live in [../backend/](../backend/index.md).

---

## Overview

Everything the user or the agent sees is produced by three places:

| Surface | Source |
|---|---|
| `/sbtd` command parsing, help, completion, suggestions | `packages/omp-sbtd/src/commands/index.ts` |
| Rendered validation reports | `packages/omp-sbtd/src/report/index.ts` |
| Runtime markers + notifications | `packages/omp-sbtd/src/extension.ts` (`ctx.ui.notify`, marker append) |

Behavioral source of truth for this surface: `packages/omp-sbtd/features/*.feature` (Chinese
Gherkin) — see [../backend/testing.md](../backend/testing.md).

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Command Surface](./command-surface.md) | The declarative `/sbtd` spec table; help/completion/dispatch derivation |
| [Report Rendering](./report-rendering.md) | Render/parse round-trip, sanitization schemas, byte caps |

---

## Pre-Development Checklist

- [ ] New or changed `/sbtd` behavior starts as a `.feature` Rule/Scenario, then a table entry in
  `sbtdCommandSpecs` — never ad-hoc dispatch branches in `extension.ts`.
- [ ] Help text, completion, and unknown-command suggestions stay derived from the same table
  (they cannot drift — keep it that way).
- [ ] New user-visible text respects the report sanitization schemas and byte caps (see
  [Report Rendering](./report-rendering.md)).

## Quality Check

- [ ] `pnpm --filter @kunolu/omp-sbtd test` passes; mirrored Scenario titles updated.
- [ ] Read-only commands still receive the rejecting `readOnlyFiles` FileAdapter
  (`src/extension.ts:1505-1525`).
- [ ] No `console.*` introduced — user-facing output goes through `ctx.ui.notify` only.

---

**Language**: Spec documentation is written in **English**.
