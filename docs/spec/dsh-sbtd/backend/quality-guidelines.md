# dsh-sbtd Quality Guidelines

> Conventions are **inherited** from the monorepo root unless this package demonstrates a local
> pattern. Do not invent extra conventions ahead of backends/commands.

---

## Inherited Toolchain (from the monorepo root)

- **TypeScript**: `tsconfig.json` extends `../../tsconfig.base.json` — ES2024, NodeNext, `strict`,
  `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`. Only
  `outDir`/`rootDir`/`include` are package-local.
- **Biome**: root `lint` is `biome check .`; the package script is `biome check src`. Space indent,
  double quotes, semicolons, `as const` for the `inject` tuple.
- **Orchestration**: root `pnpm -r build|typecheck|test` runs this package's scripts.

Package scripts:

```
build:      tsc -p tsconfig.json
typecheck:  tsc -p tsconfig.json --noEmit
lint:       biome check src
test:       node --test test/*.test.mjs
```

Tests import `dist/` after `tsc`. They are not a no-op.

## Observed Local Style

- Local host context types (`SectionHost`, `ToolsHost`, `HooksHost`); do not import `@deepseek-ai/dsh` types.
- `apply(ctx)` logs then registerSection + registerPlanTool + registerHooks. No `fs`, no AGENTS.md.
- Session state is a module-level `Map` keyed by caller `sessionId` (dynamic keys). Restart drops it.
- Partial implementations land as real code or not at all — no fake tool/hook registries.

## What This Package Must NOT Claim

- No error-handling, logging, IO, or zod conventions "from dsh-sbtd" beyond `console.log` on load.
- No backends/commands until those files exist. T4 adds manuals sync only; do not add tools.
- Do not report live `dsh plugin add` as passing unless the `dsh` CLI was actually run.

## Verification

```bash
pnpm --filter @kunolu/dsh-sbtd lint
pnpm --filter @kunolu/dsh-sbtd typecheck
pnpm --filter @kunolu/dsh-sbtd build
pnpm --filter @kunolu/dsh-sbtd test
```
