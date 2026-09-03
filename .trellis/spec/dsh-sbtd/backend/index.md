# dsh-sbtd Backend Guidelines

> Conventions for `@kunolu/dsh-sbtd` (`packages/dsh-sbtd/`): the DSH host adapter.
> T4 landed read-only manuals sync from 640-skills v1.0.13 on T3 hooks.

---

## Current State (T4)

Per `packages/dsh-sbtd/README.md`: DSH SBTD adapter registers a short Chinese `sbtd` section,
in-process session state, sbtd_plan, and hooks, plus manuals/. Target host: `@deepseek-ai/dsh@0.1.1-rc.2`.
`apply()` does not write `AGENTS.md` or user disk. No extra sbtd_* tools.

Source files:

- `src/index.ts` — `name`, `inject = ["tools", "systemPrompt"]`, `apply`
- `src/section.ts` — static Chinese section text, `name: "sbtd"`, `order: 50`
- `src/state.ts` — `Map` keyed by caller `sessionId`; `serialize()` / `restore()`
- `src/tools/plan.ts` — sbtd_plan registers/updates BookGatePlan. DDD is required only after completed `grill-with-docs`; bare `ddd` stays on-demand.
- `src/hooks.ts` — `ctx.on("tools/pre-execute")` and `ctx.on("agent/pre-step")`. Allow via `next()`. Local host types only.
- `scripts/sync-manuals.sh` + `manuals/**` — 640-skills v1.0.13 whitelist SKILL.md + references/ + skill-root markdown; MANIFEST.json sourcePath + sha256 + sourceRevision

Do not import `@deepseek-ai/dsh` types. Local context type only.

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Layout and the DSH host boundary |
| [Quality Guidelines](./quality-guidelines.md) | Inherited toolchain conventions |

When later tasks add tools or backends, model new guidance on the sibling specs
(`../../omp-sbtd/backend/`, `../../sbtd-workflow-kit/backend/`) rather than reinstating generic
templates.

---

## Pre-Development Checklist

- [ ] Confirm the task is T4 manuals only — do not start T5 sbtd_review.
- [ ] When adding real behavior, check the DSH host contract first: `cordis.patch.yml` +
  `package.json#dsh.bundle.patch` + the `name`/`inject`/`apply` exports in `src/index.ts`.
- [ ] Tests use `node:test` against `dist/` after `tsc`, with BDD-mirrored titles under `features/`.

## Quality Check

- [ ] `pnpm --filter @kunolu/dsh-sbtd lint`, `typecheck`, `build`, and `test` pass.
- [ ] The package remains `"private": true`.
- [ ] `plugin.json`-style publish surface does NOT exist here — this package is not published in T4.
- [ ] `apply()` still does not write `AGENTS.md` or user disk.

---

**Language**: Spec documentation is written in **English**.
