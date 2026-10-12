# dsh-sbtd Host Contract

> The cordis-style plugin surface the DSH host consumes. All of it lives in three files.

---

## Plugin Exports (`src/index.ts`)

```ts
export const name = "dsh-sbtd";
export const inject = [] as const;

export function apply(_ctx: unknown): void {
  // Stub: sbtd_* tools, hooks, and the short section land in a later change.
}
```

Rules:

1. **`name` equals the directory name** (`dsh-sbtd`) — keep this invariant.
2. **`inject` declares service dependencies.** Empty today; when real dependencies appear, add them
   to the tuple (`as const`) rather than reaching into the host ad hoc.
3. **`apply(ctx)` is the only lifecycle hook.** It currently takes `_ctx: unknown` and does
   nothing. When implemented, narrow the context type to the real DSH host contract and keep
   registration fail-closed, mirroring `packages/omp-sbtd/src/runtime/index.ts`
   (`registerRuntimeController` probes capabilities and throws before any registration).

## Bundle Patch (`cordis.patch.yml`)

```yaml
- insert:
    - id: sbtd
      name: dsh-sbtd
```

- Top-level list of patch operations; the only observed operation is `insert` with entries
  `{id, name}`.
- Referenced via `package.json` → `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`.
- **No in-repo validator consumes this file** — its schema is defined host-side. Do not assume
  operations beyond `insert {id, name}` are supported until the DSH host documents them.

## Consistency

The three artifacts move together: plugin `name`, patch entry `name`, and the `id: sbtd` block.
A rename or new patch operation means updating all three plus the README's target-host line
(`dsh@0.1.0-rc.7`) in one change.
