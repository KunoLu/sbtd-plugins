# sbtd-workflow-kit Quality Guidelines

> Style, schema, and IO conventions observed across all six `src/` modules. Enforced by Biome
> (`biome check src test`) and `tsc --noEmit`; the rest is convention with strong precedent.

---

## Style

- 2-space indent, double quotes, semicolons (Biome formatter, root `biome.json`).
- camelCase functions/variables; SCREAMING_SNAKE_CASE module-level constants (`SOURCE_ROOT`,
  `AGENTS_SOURCES`, `TARGETS`, `CHECK_NAMES`, `DERIVED_OUTPUTS`, `PROMOTION_OWNED_PACKAGE_PATHS`).
- Explicit return types on exported and most internal async functions.
- Underscore prefix for intentionally unused bindings (`_AGENTS_TARGET_PATHS` in
  `test/omp-projection.test.ts`).
- Long functions are accepted when they form one transaction (`writeSnapshot` ~200 lines). Comments
  are sparse but explain **why** for non-obvious invariants — e.g. the derived-output single-writer
  comment (`src/omp-projection.ts:38-41`) and the forbidden-token exemption comment
  (`src/omp-projection.ts:891-899`). Match that: comment invariants, not mechanics.

## Immutability

- `readonly` on virtually every interface field and array (`readonly string[]`,
  `Readonly<Record<string, string>>`).
- `as const` for constant tuples; `as const satisfies readonly CandidateDefinition[]` for the
  13-entry candidate table (`src/agent-plugin-projection.ts:58-189`).
- `exactOptionalPropertyTypes` shapes construction: optional fields are conditionally spread, e.g.
  `...(entry.policy === "replace-with-overlay" ? { overlay: entry.overlay } : {})`
  (`src/index.ts:638-642`). Do not assign `undefined` to optional fields.
- `noUncheckedIndexedAccess` shows up as `?? ""` / `?? lines.length` guards after indexing.

## Zod Schema Discipline

zod 4.1.12 is the only validation library; every external/config input goes through a schema:

- **`.strict()` on every object** — unknown keys are rejected (`stableManifestSchema`,
  `upstreamLockSchema`, `sectionMapSchema`, `kitManifestSchema` in `src/index.ts`;
  `ompDistributionMapSchema` in `src/omp-projection.ts`).
- **Cross-field rules via `.superRefine`** — e.g. "stable Skill references an unknown repository"
  (`src/index.ts:66-76`) and "include requires exactly one of owner or splitTargets"
  (`src/index.ts:118-126`).
- **Discriminated unions on `policy`**: `z.discriminatedUnion("policy", [includedSectionSchema,
  omittedSectionSchema, overlaidSectionSchema])` (`src/index.ts:147-155`).
- **Format regexes**: digests `/^[0-9a-f]{64}$/`, revisions `/^[0-9a-f]{40}$/`, URLs `z.url()`.
- **Types are derived, never duplicated**: `export type KitManifest = z.infer<typeof
  kitManifestSchema>`. No hand-written interface mirroring a schema.
- **Generated output is self-validating**: manifests are built by passing a literal through
  `kitManifestSchema.parse(...)` / `ompProjectionManifestSchema.parse(...)` before being written —
  the schema is a construction-time contract, not just input parsing.
- **Path safety in schema**: `decisionPathSchema` `.refine()` rejects absolute paths, backslashes,
  empty/`..` segments (`src/omp-projection.ts:46-54`); `assertContainedStablePath` does the same at
  runtime for stable manifest paths (`src/index.ts:460-470`).

Known as-is deviations (do not copy without reason): `agent-plugin-projection.ts` hand-rolls
frontmatter parsing checks without zod, and `sync-upstream.ts`'s `classifiedSections` does loose
typed narrowing of the mapping YAML. Both are documented tech debt.

## IO and Output

- **No logger, no `console.log`.** Scripts write exactly one line of JSON to stdout
  (`src/generate.ts:30-41` prints the digests object; `src/check-generated.ts` prints
  `generated output is current\n`; `src/sync-upstream.ts` prints the full `UpstreamSyncResult`).
- All file IO via `node:fs/promises`; concurrent IO is always `await Promise.all(...)` — no
  floating promises.
- Child processes go through `promisify(execFile)` with explicit `maxBuffer: 64 * 1024 * 1024` and
  env allowlisting; git is invoked as `git -C <root> ...` (`src/sync-upstream.ts:240-255`).
  `agent-plugin-projection.ts` shells to `python3 -c`, `bash -n`, `node --check` with 10s timeouts.
- **No symlinks** — every tree walker rejects them (`src/index.ts`, `src/omp-projection.ts`,
  `src/agent-plugin-projection.ts`).

## Anti-Patterns (observed as consistently avoided)

- No partial writes / in-place mutation of outputs (stage + rename + rollback everywhere).
- No `any` — `unknown` + narrowing at catch and JSON boundaries.
- No environment-dependent output — sorted iteration, `\0` separators, fixed JSON formatting.
- No new dependencies — 2 runtime deps total; reuse Node builtins and system binaries.
- No hand-editing generated trees — enforced mechanically by `check-generated`.
- No errors-as-values — exceptions only, via `KitError`.

## Verification

```bash
pnpm --filter @kunolu/sbtd-workflow-kit lint        # biome check src test
pnpm --filter @kunolu/sbtd-workflow-kit typecheck   # src only — tests are NOT typechecked (known debt)
pnpm --filter @kunolu/sbtd-workflow-kit test        # vitest run
pnpm --filter @kunolu/sbtd-workflow-kit check-generated
```
