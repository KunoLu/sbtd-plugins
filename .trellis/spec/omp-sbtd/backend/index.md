# omp-sbtd Backend Guidelines

> Conventions for `@kunolu/omp-sbtd` (`packages/omp-sbtd/`): the OMP host extension implementing
> KPi SBTD workflow gates — deterministic task classification, book gates, a rule registry,
> tool-risk guards, environment onboarding, and validation-evidence observation.

---

## Overview

This package is an **OMP extension**, not a standalone app. Its entire public surface is one
default export in `src/extension.ts` registered through `registerRuntimeController`. It has no UI,
no database, no network calls, and no telemetry. The dominant posture is **fail-closed**: unknown
→ blocked, malformed → rejected, integrity failure → blocked with a `/sbtd doctor` repair path.

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Real module layout, the single-entry architecture, registries-as-data |
| [Type Safety](./type-safety.md) | zod discipline: `.strict()` boundaries, `superRefine`, `z.input`/`z.output` |
| [Error Handling](./error-handling.md) | Throw vs result-object split, fail-closed host boundary |
| [Security Invariants](./security-invariants.md) | Trust boundaries that must hold: approvals, paths, digests, zero-write |
| [Quality Guidelines](./quality-guidelines.md) | Style, naming, immutability, IO, comments |
| [Testing](./testing.md) | vitest serial run, `.feature`-mirrored titles, fixtures, hand-rolled host fakes |
| [Build and Release](./build-and-release.md) | Build chain, build-owned artifacts, versioning, publish surface |

---

## Pre-Development Checklist

Before editing this package, confirm:

- [ ] The behavior you are adding has a `.feature` Rule/Scenario (or you are about to write one) —
  `features/*.feature` is the behavior source of truth (see [Testing](./testing.md)).
- [ ] You know which registry your change belongs to: gates (`src/gates/index.ts`), rules
  (`src/rules/index.ts`), commands (`src/commands/index.ts`), tool capabilities
  (`src/tool-risk/index.ts`). New behavior = new table entry + evaluator branch, not ad-hoc
  branching in `extension.ts` (see [Directory Structure](./directory-structure.md#registries-as-data)).
- [ ] New host event payloads get a `.strict()` zod schema with a `type` literal discriminator in
  `src/runtime/omp-extension-v1.ts` (see [Type Safety](./type-safety.md)).
- [ ] New host capabilities/events are added to `ompExtensionV1Inventory` — never side-step the
  fail-closed probe in `src/runtime/index.ts`.
- [ ] Your change does not persist anything outside the host session log
  (`kpi.sbtd.session.v1`), and persists digests rather than contents (see
  [Security Invariants](./security-invariants.md)).

## Quality Check

Before considering work done:

- [ ] `pnpm --filter @kunolu/omp-sbtd lint` passes (`biome check src test scripts` — scripts are
  linted too).
- [ ] `pnpm --filter @kunolu/omp-sbtd typecheck` passes.
- [ ] `pnpm --filter @kunolu/omp-sbtd test` passes (serial vitest; see [Testing](./testing.md)).
- [ ] Tests mirror the `.feature` Scenario titles verbatim; `// Trace:` comments cite the feature
  Rule where applicable.
- [ ] Full `pnpm --filter @kunolu/omp-sbtd build` passes — NOT bare `tsc`. The build chain runs
  the kit drift gate, embeds `kit/` and `skills/`, and writes the SBOM (see
  [Build and Release](./build-and-release.md)).
- [ ] No failure path converts into a pass; every catch lands in a blocked/blocked-with-repair
  state (see [Error Handling](./error-handling.md)).

---

**Language**: Spec documentation is written in **English**; Gherkin features and mirrored test
titles stay in **Chinese** (see [Testing](./testing.md)).
