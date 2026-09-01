# dsh-sbtd Quality Guidelines

> This package is a stub. Its conventions are **inherited**, not local. Do not restate inherited
> rules as package-local decisions, and do not attribute patterns to this package that its code
> does not demonstrate.

---

## Inherited Toolchain (from the monorepo root)

- **TypeScript**: `tsconfig.json` extends `../../tsconfig.base.json` — ES2024, NodeNext, `strict`,
  `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`. Only
  `outDir`/`rootDir`/`include` are package-local.
- **Biome**: root `lint` is `biome check .`; the package script is `biome check src`. The stub
  conforms: space indent, double quotes, semicolons, `as const` for the empty tuple.
- **Orchestration**: root `pnpm -r build|typecheck|test` runs this package's scripts.

Package scripts (all of them):

```
build:      tsc -p tsconfig.json
typecheck:  tsc -p tsconfig.json --noEmit
lint:       biome check src
test:       node --input-type=module -e "process.exit(0)"   # no-op placeholder — NOT real tests
```

## Observed Local Style (from `src/index.ts`)

- Unused parameter prefixed with underscore: `apply(_ctx: unknown)`.
- `unknown` rather than `any` for the host context the stub does not consume yet.
- The stub is honest: it exports the minimal host contract and says so in README. It does not
  export fake TODO-filled APIs, mock contexts, or placeholder registries. Keep that property —
  partial implementations land as real code or not at all.

## What This Package Must NOT Claim (until the code exists)

- No error-handling, logging, IO, validation/zod, or testing conventions "from dsh-sbtd".
- No directory layout beyond `src/` (no `test/`, `features/`, `skills/`, `validation/`).
- The `test` script is `process.exit(0)` — do not report it as test coverage.

## When Real Implementation Lands

Model the new code and its spec updates on the sibling packages, which share this repo's actual
conventions:

- Extension/host-integration patterns: `../../omp-sbtd/backend/` (single entry, registries as
  data, fail-closed posture, zod boundaries).
- Error type + fail-closed writes: `../../sbtd-workflow-kit/backend/error-handling.md`.
- vitest + BDD-mirrored titles + tmpdir fixtures: `../../omp-sbtd/backend/testing.md` or
  `../../sbtd-workflow-kit/backend/testing.md`.

Update these spec files in the same change that introduces the real behavior.

## Verification

```bash
pnpm --filter @kunolu/dsh-sbtd lint
pnpm --filter @kunolu/dsh-sbtd typecheck
pnpm --filter @kunolu/dsh-sbtd build
```
