# dsh-sbtd Directory Structure

> Complete, real layout of `packages/dsh-sbtd/`. The package is a stub; this list is exhaustive.

---

## Layout

```
packages/dsh-sbtd/
├── cordis.patch.yml   # DSH host bundle patch (46 bytes, see below)
├── LICENSE            # Apache-2.0
├── package.json
├── README.md          # 3 lines: stub admission + target host dsh@0.1.0-rc.7
├── src/index.ts       # the ONLY source file (8 lines)
└── tsconfig.json      # extends ../../tsconfig.base.json; outDir dist, rootDir src
```

There is no `test/`, no `features/`, no `skills/`, no committed `dist/`, no codegen. Compare the
siblings before assuming structure: `packages/omp-sbtd/` (13 `src/` subdirs, `features/`,
`validation/`) and `packages/sbtd-workflow-kit/` (`vendor/`, `generated*/`, `test/`).

## The DSH Host Boundary

The entire host contract consists of:

1. **Plugin exports** in `src/index.ts`: `name = "dsh-sbtd"`, `inject = [] as const` (zero service
   dependencies), `apply(_ctx: unknown): void` (no-op).
2. **`cordis.patch.yml`** — a top-level list of patch operations; the only observed operation:

   ```yaml
   - insert:
       - id: sbtd
         name: dsh-sbtd
   ```

3. **`package.json#dsh.bundle.patch`** → `"./cordis.patch.yml"` — the non-standard `dsh` key is how
   the DSH bundler locates the patch.

No in-repo validator consumes `cordis.patch.yml`; its schema is defined host-side. Do not claim
operations beyond `insert {id, name}` are supported.

## Package Facts

- `"type": "module"`, `"main": "./dist/index.js"`, `"types": "./dist/index.d.ts"` — compiled then
  consumed; never imported from `src`.
- Zero dependencies, zero devDependencies.
- `"private": true` — never published despite the `@kunolu` scope and `repository` field.
- Version `0.1.0-rc.0`; target host pinned in README: `dsh@0.1.0-rc.7`.
- Plugin `name` constant equals the directory name (`dsh-sbtd`); keep that invariant when the
  implementation grows.
