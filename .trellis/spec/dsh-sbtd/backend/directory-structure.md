# dsh-sbtd Directory Structure

> Real layout of `packages/dsh-sbtd/` after T4 (manuals sync on T3 hooks).
> Backends and commands are still absent.

---

## Layout

```
packages/dsh-sbtd/
├── cordis.patch.yml
├── LICENSE                 # Apache-2.0
├── package.json
├── README.md               # pin @deepseek-ai/dsh@0.1.1-rc.2; @next install; hooks
├── features/
│   ├── t0-installable-stub.feature
│   ├── t1-section-state.feature
│   ├── t2-sbtd-plan.feature
│   ├── t3-hooks-gate.feature
│   └── t4-manuals-sync.feature
├── manuals/              # SKILL.md + references/ + skill-root markdown + MANIFEST.json (sourcePath/sha256/sourceRevision)
├── scripts/
│   └── sync-manuals.sh
├── src/
│   ├── index.ts            # name / inject / apply; section + plan tool + hooks
│   ├── tools/
│   │   └── plan.ts         # sbtd_plan
│   ├── hooks.ts            # pre-step / pre-execute
│   ├── section.ts          # static Chinese sbtd section, order 50
│   └── state.ts            # in-process Map session state + serialize/restore
├── test/
│   ├── t0-stub.test.mjs
│   ├── t1-section.test.mjs
│   ├── t1-state.test.mjs
│   ├── t2-plan.test.mjs
│   ├── t3-hooks.test.mjs
│   ├── t4-manuals.test.mjs
│   ├── t4-sync-exit.test.mjs
│   └── snapshots/sbtd-section.txt
```

There is no `skills/`, no committed `dist/`, no codegen. `apply()` does not write `AGENTS.md` or user disk.

## The DSH Host Boundary

1. **Plugin exports** in `src/index.ts`: `name = "dsh-sbtd"`, `inject = ["tools", "systemPrompt"] as const`, `apply(ctx)` logs then registerSection + registerPlanTool + registerHooks.
2. **`cordis.patch.yml`**:

   ```yaml
   - insert:
       - id: sbtd
         name: "@kunolu/dsh-sbtd"
   ```

   Plugin export `name` stays `dsh-sbtd` (directory name). Patch `name` is the installed npm package.
3. **`package.json#dsh.bundle.patch`** → `"./cordis.patch.yml"`.

No in-repo validator consumes `cordis.patch.yml`. Do not claim operations beyond `insert {id, name}` are supported.

## Package Facts

- `"type": "module"`, `"main": "./dist/index.js"`, `"types": "./dist/index.d.ts"` — tests import `dist/` after `tsc`.
- `"private": true`. Peer `@deepseek-ai/dsh` `0.1.1-rc.2`.
- Version `0.1.0-rc.0`. Target host pinned in README: `@deepseek-ai/dsh@0.1.1-rc.2`.
- Plugin `name` constant equals the directory name (`dsh-sbtd`).
