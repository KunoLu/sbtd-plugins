# make dsh-sbtd T0 stub installable on 0.1.1-rc.2

## Goal

Make the existing `@kunolu/dsh-sbtd` stub in `packages/dsh-sbtd` installable on `@deepseek-ai/dsh@0.1.1-rc.2`. `apply()` only logs and registers an empty `systemPrompt` section. No writes to user disk or `AGENTS.md`.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：T0 已由 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md` 的 T0 节和本轮明确约束钉死；用户要求 grill 时采用该 PRD 默认值。无领域模型或长期术语变更。

## Book Gate Plan

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand | 未调用 grill-with-docs；无术语/边界歧义 | — | not-required |
| `book-ddia-data-design` | on-demand | 无持久化/共享数据/cache/异步流 | — | not-required |
| `book-legacy-change-safety` | required | 既有 `cordis.patch.yml` `name: dsh-sbtd` 导致宿主 `Cannot find package dsh-sbtd`；apply()/export/`inject` 已有 node:test | before first behavior edit | passed |
| `book-refactoring-pass` | required | 本轮修改既有生产文件 `cordis.patch.yml`（不改 `src/index.ts` / `package.json` / README） | before first impl edit | passed |
| `book-release-readiness` | required | DSH 宿主插件 `apply()` 是生产路径加载入口 | after validation | passed |

## Requirements

- R1. Keep the package in `packages/dsh-sbtd`. Do not create a new repo. Do not run `trellis init --dsh`. Do not use dsh `0.1.2-alpha` or `0.1.0-rc.7`.
- R2. `export const name = "dsh-sbtd"`. `inject` is `tools` and `systemPrompt`.
- R3. All T0 logic stays in `src/index.ts`. Local `T0Context` type only. Do not import `0.1.2-alpha` packages. No `src/section.ts`, no `src/state.ts`.
- R4. `apply(ctx)` logs `[dsh-sbtd] plugin loaded (T0 stub)` then `ctx.systemPrompt.section({ name: "sbtd", order: 50, text: "" })`.
- R5. No writes to user disk or `AGENTS.md`. No real sbtd tools, hooks, commands, or backends. No Maestro, KPi, or dotenv files.
- R6. `package.json`: name `@kunolu/dsh-sbtd`, `type: module`, `main` `dist/index.js`, `dsh.bundle.patch`, `peerDependencies` `@deepseek-ai/dsh` `0.1.1-rc.2`, `files` includes `dist/`, `cordis.patch.yml`, `manuals/`, Apache-2.0, `private: true` OK.
- R7. `cordis.patch.yml` keeps `id: sbtd`, `name: @kunolu/dsh-sbtd` (Node import of the installed package). Plugin export stays `dsh-sbtd` (R2).
- R8. Create `manuals/.gitkeep`. Do not commit `dist/`.
- R9. README pins `@deepseek-ai/dsh@0.1.1-rc.2` and documents local `dsh plugin --profile web add <path>`.
- R10. Edit only `packages/dsh-sbtd` plus this task’s artifacts.

## Acceptance criteria

- [x] `apply()` logs `[dsh-sbtd] plugin loaded (T0 stub)` and registers empty section `{ name: "sbtd", order: 50, text: "" }`.
- [x] `name` is `dsh-sbtd`; `inject` includes `tools` and `systemPrompt`.
- [x] Peer and README pin `@deepseek-ai/dsh@0.1.1-rc.2` and never `rc.7` or `0.1.2-alpha`.
- [x] `package.json` `files` includes `dist/`, `cordis.patch.yml`, `manuals/`.
- [x] `cordis.patch.yml` has `id: sbtd` and `name: @kunolu/dsh-sbtd`.
- [x] `manuals/.gitkeep` exists. No T1 files, no disk/`AGENTS.md` writes, no real tools/hooks/backends.
- [x] Package `tsc` build succeeds (`./node_modules/.bin/tsc -p packages/dsh-sbtd/tsconfig.json`). `pnpm --filter` is blocked: new peer needs lockfile, R10 forbids lockfile edit.
- [x] README documents `dsh plugin --profile web add <path>`.
- [x] Live `dsh --profile web --dump-config` shows `id: sbtd` and `name: '@kunolu/dsh-sbtd'`. `timeout 12 dsh web` printed `[dsh-sbtd] plugin loaded (T0 stub)` and `dsh web: http://127.0.0.1:3080`. No `Cannot find package dsh-sbtd`. Nonzero exit is the intentional timeout after resolved import, not an import failure.

## Out of scope

- T1–T16 (`src/section.ts`, `src/state.ts`, tools, hooks, backends)
- New repository, `trellis init --dsh`, dsh `0.1.2-alpha`
- Maestro, KPi, dotenv, root README, other packages
- Git commit / push / merge / publish
- Live `dsh plugin add` / `dsh web` when the `dsh` CLI is absent (blocked in this environment)

## Notes

- Source of T0 defaults: `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md` § T0.
- BDD: plugin load log, empty section, and README install command are user-visible. Persistent `.feature` under `packages/dsh-sbtd/features/`. Patch-name contract is the node:test `cordis patch name 使用已安装的 npm 包名`. Live install: dump-config + timed-out `dsh web` after successful plugin load.
- This turn used `tdd` for the patch-name regression. Plugin export `name` stays `dsh-sbtd`; patch `name` is `@kunolu/dsh-sbtd`. `.trellis/spec` host-contract still says they match; not updated (R10).
