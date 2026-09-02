# dsh-sbtd Directory Structure

> Real layout of `packages/dsh-sbtd/` after T2 (sbtd_plan on T1 session state).
> Hooks, backends, and commands are still absent.

---

## Layout

```
packages/dsh-sbtd/
├── cordis.patch.yml
├── LICENSE                 # Apache-2.0
├── package.json
├── README.md               # pin @deepseek-ai/dsh@0.1.1-rc.2; @next install; short Chinese sbtd section
├── features/
│   ├── t0-installable-stub.feature
│   ├── t1-section-state.feature
│   └── t2-sbtd-plan.feature
├── manuals/.gitkeep
├── src/
│   ├── index.ts            # name / inject / apply; section + plan tool
│   ├── tools/
│   │   └── plan.ts         # sbtd_plan
│   ├── section.ts          # static Chinese sbtd section, order 50
│   └── state.ts            # in-process Map session state + serialize/restore
├── test/
│   ├── t0-stub.test.mjs
│   ├── t1-section.test.mjs
│   ├── t1-state.test.mjs
│   ├── t2-plan.test.mjs
│   └── snapshots/sbtd-section.txt
└── tsconfig.json           # extends ../../tsconfig.base.json; outDir dist, rootDir src
```

There is no `skills/`, no committed `dist/`, no codegen. `apply()` does not write `AGENTS.md` or user disk.

## The DSH Host Boundary

1. **Plugin exports** in `src/index.ts`: `name = "dsh-sbtd"`, `inject = ["tools", "systemPrompt"] as const`, `apply(ctx)` logs then registerSection + registerPlanTool.
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
