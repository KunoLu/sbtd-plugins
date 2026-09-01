# sbtd-workflow-kit Testing

> vitest 4.0.16, no config file, BDD-mirrored titles, real tmpdir fixtures, byte-level assertions.

---

## Runner and Layout

- `pnpm --filter @kunolu/sbtd-workflow-kit test` = `vitest run`. There is **no vitest.config** —
  all defaults.
- Tests live in `test/*.test.ts`, one file per concern: `transform.test.ts` (Kit transform +
  agent-plugin + sync-upstream) and `omp-projection.test.ts` (OMP projection).
- Tests import source with `.ts` specifiers (`../src/index.ts`) and run against TypeScript source,
  not `dist/`. Note: `tsconfig.json` includes only `src/**`, so tests are linted but **not
  typechecked** — known as-is debt; be careful with types in test files.

## BDD-Mirrored Naming

`features/*.feature` (Chinese Gherkin) is the behavior source of truth. Tests mirror it 1:1 by
title:

- `describe("Feature: 三目标 AGENTS 转换", …)` + `it("Scenario: 上游新增未映射 Section", …)`
  (`test/transform.test.ts:609-610` ↔ `features/agents-transformation.feature`).
- `test/omp-projection.test.ts` uses an English describe (`describe("OMP Distribution Projection")`)
  but keeps `Scenario:`-prefixed titles.

There is no Gherkin runner; the binding is the naming convention. **New behavior starts as a
`.feature` Scenario; the test adopts the Scenario title verbatim.**

## Fixtures: Real Filesystem, No Mocks

- `fixture()` copies `vendor/`, `upstream.lock.json`, `agents-section-map.yaml`, `overlays/`,
  `LICENSE` into `mkdtemp(join(tmpdir(), "kpi-kit-"))` (`test/transform.test.ts:272-289`).
- `promotionFixture()` builds two real git repos with `git init`/`git commit`
  (`test/transform.test.ts:50-208`).
- `test/omp-projection.test.ts` adds a fully synthetic builder (`syntheticFixture`,
  `test/omp-projection.test.ts:90-187`) that fabricates a canonical tree with hand-computed manifest
  digests so edge cases (symlinks, forbidden tokens, partial stable trees) can be induced without
  the real upstream.
- Every temp root is pushed to a shared `temporaryRoots: string[]` and removed in a single
  `afterEach` (`test/transform.test.ts:283-289`, `test/omp-projection.test.ts:236-241`). Follow this
  pattern — do not leave temp dirs behind.

## Assertion Style

- Plain `expect(...)` with `.toEqual`, `.toBe`, `.toMatchObject`, `.toContain` / `.not.toContain`
  on generated file contents; `expect.stringMatching(/^[0-9a-f]{64}$/)` for digest slots.
- **Assert on written bytes, not just return values.** Representative: generate twice into two
  temp dirs, then assert `second.manifest` deep-equals `first.manifest` AND the persisted
  `manifest.json` bytes are equal (`test/omp-projection.test.ts:243-270`). Another test recomputes
  sha256 over every recorded `manifest.assets[path]` from disk and re-parses the persisted manifest
  with `ompProjectionManifestSchema.parse` — the artifact must satisfy its own schema
  (`test/omp-projection.test.ts:303-343`).
- Error paths use the local `expectKitError(run, code)` helper: catches, asserts
  `instanceof KitError`, asserts `error.code`, returns the error for further `details` checks
  (`test/omp-projection.test.ts:189-205`).
- Long-running promotion tests carry explicit timeouts: `}, 30_000);`
  (`test/transform.test.ts:1025`).

## Test Seams in Production Code

Failure injection goes through explicit options, not monkey-patching:
`SyncUpstreamOptions.backupPath` / `replacePath` (`src/sync-upstream.ts:56-59`) let tests induce
backup/replacement failures (`test/transform.test.ts:1247-1315`). When you need to force a failure
path, add a narrow seam option like this rather than a mock framework.

## Known Debt (as-is, do not propagate)

- `test/transform.test.ts:663` scenario title says "KPi GPLv3 标识" but the shipped LICENSE is
  Apache-2.0 — the title outlived a license change.
- Tests are outside `typecheck` coverage (see Runner above).
