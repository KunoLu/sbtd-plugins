# dsh-sbtd Frontend Guidelines

> Reshaped layer: this package has **no UI**. "Frontend" here means the **host-facing contract
> surface**: the cordis-style plugin exports and the bundle patch the DSH host consumes. Everything
> else about the (stub) package lives in [../backend/](../backend/index.md).

---

## Overview

The entire host-facing surface today:

| Surface | File |
|---|---|
| Plugin contract exports (`name`, `inject`, `apply`) | `packages/dsh-sbtd/src/index.ts` |
| Bundle patch | `packages/dsh-sbtd/cordis.patch.yml` |
| Patch locator key | `package.json` → `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }` |

The package is a stub (see `README.md`: "当前仅为 stub，尚未实现 tools / hooks。目标宿主：
dsh@0.1.0-rc.7。"). The stub comment names the planned surface: `sbtd_*` tools, hooks, and "the
short section".

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Host Contract](./host-contract.md) | The cordis plugin shape and patch file rules |

---

## Pre-Development Checklist

- [ ] Changes to the host-facing surface keep the three exports and the patch file consistent with
  each other and with `package.json#dsh.bundle.patch`.
- [ ] When `sbtd_*` tools/hooks land, their user-visible behavior gets `.feature` scenarios first,
  following the sibling convention (`packages/omp-sbtd/features/`).

## Quality Check

- [ ] `pnpm --filter @kunolu/dsh-sbtd lint` / `typecheck` / `build` pass.
- [ ] The package remains `"private": true`; nothing here is published.

---

**Language**: Spec documentation is written in **English**.
