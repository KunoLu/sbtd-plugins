# dsh-sbtd Backend Guidelines

> Conventions for `@kunolu/dsh-sbtd` (`packages/dsh-sbtd/`): the DSH host adapter.
> T1 landed the short `sbtd` section and in-process session state. Tools / hooks are not implemented.

---

## Current State (T1)

Per `packages/dsh-sbtd/README.md`: DSH SBTD adapter registers a short Chinese `sbtd` section
and in-process session state. Target host: `@deepseek-ai/dsh@0.1.1-rc.2`. Tools / hooks are still
absent. `apply()` does not write `AGENTS.md` or user disk.

Source files:

- `src/index.ts` — `name`, `inject = ["tools", "systemPrompt"]`, `apply`
- `src/section.ts` — static Chinese section text, `name: "sbtd"`, `order: 50`
- `src/state.ts` — `Map` keyed by caller `sessionId`; `serialize()` / `restore()`

Do not import `@deepseek-ai/dsh` types. Local context type only.

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Layout and the DSH host boundary |
| [Quality Guidelines](./quality-guidelines.md) | Inherited toolchain conventions |

When later tasks add tools/hooks, model new guidance on the sibling specs
(`../../omp-sbtd/backend/`, `../../sbtd-workflow-kit/backend/`) rather than reinstating generic
templates.

---

## Pre-Development Checklist

- [ ] Confirm the task is implementing the remaining stub (tools/hooks) — T1 section/state already exist.
- [ ] When adding real behavior, check the DSH host contract first: `cordis.patch.yml` +
  `package.json#dsh.bundle.patch` + the `name`/`inject`/`apply` exports in `src/index.ts`.
- [ ] Tests use `node:test` against `dist/` after `tsc`, with BDD-mirrored titles under `features/`.

## Quality Check

- [ ] `pnpm --filter @kunolu/dsh-sbtd lint`, `typecheck`, `build`, and `test` pass.
- [ ] The package remains `"private": true`.
- [ ] `plugin.json`-style publish surface does NOT exist here — this package is not published in T1.
- [ ] `apply()` still does not write `AGENTS.md` or user disk.

---

**Language**: Spec documentation is written in **English**.
