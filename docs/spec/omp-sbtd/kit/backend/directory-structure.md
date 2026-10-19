# Kit Projection Directory Structure

> Real layout of `packages/omp-sbtd/upstream/`. Every entry below exists in the repo today.

---

## Layout

```
packages/omp-sbtd/upstream/
├── package.json                # moved supply-chain metadata (name/version kept as migration-preserved metadata, NOT part of the SBOM digest)
├── tsconfig.json               # extends ../../../tsconfig.base.json; includes ONLY src/**/*.ts (noEmit)
├── upstream.lock.json          # pinned upstream commit + tree sha256 + transformVersion (p0-v4)
├── agents-section-map.yaml     # schemaVersion 2; section→target classification (11 entries)
├── omp-distribution-map.yaml   # schemaVersion 1; 352 per-asset include/omit/replace-with-overlay decisions
├── overlays/                   # Kit-level target overlays (currently only AGENTS.project-omp.md)
├── omp-overlays/               # OMP projection overlays mirroring canonical asset paths
├── src/                        # 6 modules, flat — no subdirectories
│   ├── index.ts                # schemas, section transform, generateKit/checkGenerated, KitError (~1176 lines)
│   ├── generate.ts             # 33-line CLI driver behind `scripts/kit-generate.mjs`
│   ├── check-generated.ts      # 33-line CLI driver behind `scripts/kit-check-generated.mjs`
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

1. **`upstream/src/` stays flat.** Six modules, no nesting. New capability extends an existing module
   (`index.ts` for canonical transform, `omp-projection.ts` for OMP view, `sync-upstream.ts` for
   promotion) rather than creating new directories.
2. **CLI drivers are thin.** `generate.ts` and `check-generated.ts` are ~33-line wrappers that
   resolve the package root via `fileURLToPath(new URL("..", import.meta.url))` and delegate to
   library functions. Logic lives in the library modules so tests can call it directly.
3. **`sync-upstream.ts` is import-safe.** Its `main()` is guarded by a realpath comparison against
   `process.argv[1]` (`upstream/src/sync-upstream.ts:1109-1114`) so tests can import it without side effects.
   Keep that guard when editing the CLI path.
4. **Nothing here is a package export anymore.** The tree is consumed in-repo: the plugin build
   calls the thin wrappers `packages/omp-sbtd/scripts/kit-*.mjs`, and the embed scripts read the
   committed `generated-omp/` / `generated-agent-plugin/` manifests directly.
   `omp-projection.ts` / `agent-plugin-projection.ts` / `sync-upstream.ts` export symbols for tests
   only. The retained `package.json` is supply-chain metadata kept as migration-preserved metadata;
   its name/version are NOT part of the SBOM source-tree digest (per PRD R6 the digest input is
   exactly `{ plugin: { name, version }, kit: { generatedSha256 }, files }`), and it is not a
   publishable manifest.
5. **Generated trees are committed artifacts.** `generated/`, `generated-omp/`,
   `generated-agent-plugin/`, and the package-root `LICENSE` / `THIRD_PARTY_NOTICES.md` (copied out
   of `generated/` by `upstream/src/generate.ts`) are build outputs checked into git. They are covered by
   `check-generated` drift detection — see [Codegen Workflow](./codegen-workflow.md).

---

## Import Conventions

- ESM, `node:`-prefixed builtins everywhere (`node:fs/promises`, `node:crypto`, `node:path`, …).
- **`upstream/src/` imports use `.js` specifiers** (NodeNext): `import { generateKit } from "./index.js"`.
- **`test/` imports use `.ts` specifiers**: `import { checkGenerated, generateKit } from
  "../src/index.ts"` — tests run under vitest against TypeScript source, not `dist/`.
- `verbatimModuleSyntax`: type-only imports use `import type { Stats } from "node:fs"` or inline
  `type` qualifiers (`import { ..., type StableProvenance, sha256 } from "./index.js"`).
- Named exports only; no default exports, no barrel files beyond `index.ts`.

---

## Dependencies

Code deps are exactly two: `yaml@2.8.2` and `zod@4.1.12`, both declared by the enclosing
`@kunolu/omp-sbtd` package (`yaml` as devDependency, build-time only; runner `tsx@4.20.6`).
Everything else is Node builtins. Syntax/AST auditing of vendored scripts shells out to system `python3`,
`bash -n`, `node --check` (`upstream/src/agent-plugin-projection.ts`) instead of adding npm dependencies.
Do not add a dependency without confirming no system binary or builtin covers the need.
