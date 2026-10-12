# sbtd-workflow-kit Backend Guidelines

> Conventions for `@kunolu/sbtd-workflow-kit` (`packages/sbtd-workflow-kit/`): the private build-time
> package that pins the vendored upstream SBTD workflow source, transforms it, and emits the three
> committed generated trees consumed by `@kunolu/omp-sbtd`.

---

## Overview

This package is a **deterministic code generator**, not a runtime service. It has no server, no
database, no UI, and no network access of its own. Everything it produces is committed to git and
guarded by a byte-exact drift check. If you take one rule away: **never hand-edit generated
output — change inputs, regenerate, keep `check-generated` green.**

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Real module layout, inputs vs generated outputs |
| [Codegen Workflow](./codegen-workflow.md) | `generate` / `check-generated` / `sync-upstream`, pipeline order, maps and overlays |
| [Error Handling](./error-handling.md) | `KitError` closed code union, wrap-with-cause, fail-closed writes |
| [Quality Guidelines](./quality-guidelines.md) | Style, zod schema discipline, determinism, no-logger IO |
| [Testing](./testing.md) | vitest conventions, BDD-mirrored titles, tmpdir fixtures, byte assertions |

---

## Pre-Development Checklist

Before editing this package, confirm:

- [ ] You know whether your change touches an **input** (`vendor/`, `upstream.lock.json`,
  `agents-section-map.yaml`, `omp-distribution-map.yaml`, `overlays/`, `omp-overlays/`,
  `src/`) or an **output** (`generated/`, `generated-omp/`, `generated-agent-plugin/`, root
  `LICENSE` / `THIRD_PARTY_NOTICES.md`). Outputs are never edited directly.
- [ ] If you add an upstream AGENTS section, it is classified in `agents-section-map.yaml`
  (see [Codegen Workflow](./codegen-workflow.md#adding-inputs)).
- [ ] If you add an asset to the canonical Kit, it has exactly one decision in
  `omp-distribution-map.yaml` (plus an `omp-overlays/<same-path>` file for
  `replace-with-overlay`).
- [ ] New error paths use `KitError` with an existing code, or extend the union in
  `src/index.ts` (see [Error Handling](./error-handling.md)).
- [ ] New external input is parsed through a zod `.strict()` schema (see
  [Quality Guidelines](./quality-guidelines.md#zod-schema-discipline)).

## Quality Check

Before considering work done:

- [ ] `pnpm --filter @kunolu/sbtd-workflow-kit lint` passes (`biome check src test`).
- [ ] `pnpm --filter @kunolu/sbtd-workflow-kit typecheck` passes.
- [ ] `pnpm --filter @kunolu/sbtd-workflow-kit test` passes (`vitest run`).
- [ ] If inputs changed: `pnpm --filter @kunolu/sbtd-workflow-kit generate` was run and
  `check-generated` passes. Remember `packages/omp-sbtd`'s build runs `check-generated`
  first — stale generated output breaks the sibling build.
- [ ] New behavior has a `Scenario:`-titled test mirroring `features/*.feature` (see
  [Testing](./testing.md)).
- [ ] No `codex` token (any case) was introduced into any path or payload that reaches
  `generated-omp/` — the projection scans for it and fails closed.

---

**Language**: Spec documentation is written in **English**; Gherkin features and mirrored test
titles stay in **Chinese** (see [Testing](./testing.md)).
