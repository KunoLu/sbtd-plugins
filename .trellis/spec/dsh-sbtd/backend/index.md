# dsh-sbtd Backend Guidelines

> Conventions for `@kunolu/dsh-sbtd` (`packages/dsh-sbtd/`): the DSH host adapter. **This package
> is currently a stub** — nearly every topic has no real code. Do not invent conventions here;
> inherit them from the monorepo root and the sibling packages.

---

## Current State (as of bootstrap, 2026-08)

Per `packages/dsh-sbtd/README.md`: "DSH 宿主上的 SBTD workflow 适配器。当前仅为 stub，尚未实现
tools / hooks。目标宿主：dsh@0.1.0-rc.7。" The root `README.md` package table agrees:
"DSH 宿主适配器（当前仅为 stub）".

The entire source is one file, `src/index.ts`, exporting the cordis-style plugin contract:

```ts
export const name = "dsh-sbtd";
export const inject = [] as const;

export function apply(_ctx: unknown): void {
  // Stub: sbtd_* tools, hooks, and the short section land in a later change.
}
```

Planned work (from the stub comment and README): `sbtd_*` tools, hooks, and "the short section".

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Real (minimal) layout and the DSH host boundary |
| [Quality Guidelines](./quality-guidelines.md) | Inherited toolchain conventions; what this package must NOT claim |

Templates for database, error handling, logging, and frontend topics were **deleted**: there is no
code in this package to back them. When real implementation lands, model new guidance on the
sibling specs (`../../omp-sbtd/backend/`, `../../sbtd-workflow-kit/backend/`) rather than
reinstating generic templates.

---

## Pre-Development Checklist

- [ ] Confirm the task is actually implementing the stub (tools/hooks/section) — until then, most
  changes here should be version bumps or metadata only.
- [ ] When adding real behavior, check the DSH host contract first: `cordis.patch.yml` +
  `package.json#dsh.bundle.patch` + the `name`/`inject`/`apply` exports in `src/index.ts`.
- [ ] When adding tests, follow the sibling conventions (vitest, BDD-mirrored titles) instead of
  extending the current no-op `test` script.

## Quality Check

- [ ] `pnpm --filter @kunolu/dsh-sbtd lint` and `typecheck` pass.
- [ ] The package remains `"private": true`.
- [ ] `plugin.json`-style publish surface does NOT exist here — this package is never published.
- [ ] No claims in docs or specs attribute error-handling, logging, validation, or testing
  conventions to this package until the code exists.

---

**Language**: Spec documentation is written in **English**.
