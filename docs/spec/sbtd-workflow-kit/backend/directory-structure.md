# sbtd-workflow-kit Directory Structure

> Real layout of `packages/sbtd-workflow-kit/`. Every entry below exists in the repo today.

---

## Layout

```
packages/sbtd-workflow-kit/
├── package.json                # scripts: build/typecheck/lint/test/generate/check-generated/sync-upstream
├── tsconfig.json               # extends ../../tsconfig.base.json; includes ONLY src/**/*.ts
├── upstream.lock.json          # pinned upstream commit + tree sha256 + transformVersion (p0-v3)
├── agents-section-map.yaml     # schemaVersion 2; section→target classification (49 entries)
├── omp-distribution-map.yaml   # schemaVersion 1; 360 per-asset include/omit/replace-with-overlay decisions
├── overlays/                   # Kit-level target overlays (currently only AGENTS.project-omp.md)
├── omp-overlays/               # OMP projection overlays mirroring canonical asset paths
├── src/                        # 6 modules, flat — no subdirectories
│   ├── index.ts                # schemas, section transform, generateKit/checkGenerated, KitError (~1176 lines)
│   ├── generate.ts             # 33-line CLI driver for `pnpm generate`
│   ├── check-generated.ts      # 33-line CLI driver for `pnpm check-generated`
│   ├── omp-projection.ts       # OMP distribution projection (~1037 lines)
│   ├── agent-plugin-projection.ts  # portable Skill audit + projection (~1066 lines)
│   └── sync-upstream.ts        # plan/apply upstream promotion (~1132 lines)
├── test/
│   ├── transform.test.ts       # Kit transform + agent-plugin + sync-upstream
│   └── omp-projection.test.ts  # OMP projection
├── features/                   # Gherkin behavior specs (Chinese), mirrored 1:1 by test titles
│   ├── agents-transformation.feature
│   └── agent-plugin-projection.feature
├── vendor/sbtd-workflow-kit-upstream/  # 455-file pinned snapshot of KunoLu/640-skills
├── generated/                  # canonical Kit output — COMMITTED, never hand-edit
├── generated-omp/              # OMP projection of generated/ — COMMITTED, never hand-edit
└── generated-agent-plugin/     # certified Skill projection — COMMITTED, never hand-edit
```

There is deliberately **no** `README.md` or `AGENTS.md` inside this package; design docs live in the
vendored tree (`vendor/sbtd-workflow-kit-upstream/docs/assets/omp-sbtd-upstream-sync-runbook.md`,
`docs/prd/omp-sbtd-upstream-promotion-prd.md`).

---

## Rules

1. **`src/` stays flat.** Six modules, no nesting. New capability extends an existing module
   (`index.ts` for canonical transform, `omp-projection.ts` for OMP view, `sync-upstream.ts` for
   promotion) rather than creating new directories.
2. **CLI drivers are thin.** `generate.ts` and `check-generated.ts` are ~33-line wrappers that
   resolve the package root via `fileURLToPath(new URL("..", import.meta.url))` and delegate to
   library functions. Logic lives in the library modules so tests can call it directly.
3. **`sync-upstream.ts` is import-safe.** Its `main()` is guarded by a realpath comparison against
   `process.argv[1]` (`src/sync-upstream.ts:1109-1114`) so tests can import it without side effects.
   Keep that guard when editing the CLI path.
4. **Only `index.ts` is a package export.** `package.json` exposes `"."` → `dist/index.js` plus five
   JSON subpaths for the generated manifests. `omp-projection.ts` / `agent-plugin-projection.ts` /
   `sync-upstream.ts` export symbols for tests but are NOT package subpath exports. Do not add
   subpath exports without a consumer.
5. **Generated trees are committed artifacts.** `generated/`, `generated-omp/`,
   `generated-agent-plugin/`, and the package-root `LICENSE` / `THIRD_PARTY_NOTICES.md` (copied out
   of `generated/` by `src/generate.ts`) are build outputs checked into git. They are covered by
   `check-generated` drift detection — see [Codegen Workflow](./codegen-workflow.md).

---

## Import Conventions

- ESM, `node:`-prefixed builtins everywhere (`node:fs/promises`, `node:crypto`, `node:path`, …).
- **`src/` imports use `.js` specifiers** (NodeNext): `import { generateKit } from "./index.js"`.
- **`test/` imports use `.ts` specifiers**: `import { checkGenerated, generateKit } from
  "../src/index.ts"` — tests run under vitest against TypeScript source, not `dist/`.
- `verbatimModuleSyntax`: type-only imports use `import type { Stats } from "node:fs"` or inline
  `type` qualifiers (`import { ..., type StableProvenance, sha256 } from "./index.js"`).
- Named exports only; no default exports, no barrel files beyond `index.ts`.

---

## Dependencies

Runtime deps are exactly two: `yaml@2.8.2` and `zod@4.1.12` (devDependency `tsx@4.20.6`). Everything
else is Node builtins. Syntax/AST auditing of vendored scripts shells out to system `python3`,
`bash -n`, `node --check` (`src/agent-plugin-projection.ts`) instead of adding npm dependencies.
Do not add a dependency without confirming no system binary or builtin covers the need.
