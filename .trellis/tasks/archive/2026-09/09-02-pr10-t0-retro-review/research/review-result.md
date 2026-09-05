# PR 10 T0 retro review evidence

Target: main `7253b29` (PR https://github.com/KunoLu/sbtd-plugins/pull/10). T0 files on HEAD match that commit.

## Required checks

| Check | Result | Evidence |
|---|---|---|
| `apply()` does not write disk or AGENTS.md | PASS | `packages/dsh-sbtd/src/index.ts` logs + empty `systemPrompt.section` only. No fs. Dump-config has no AGENTS. |
| dump-config id sbtd | PASS | Live `dsh --profile web --dump-config`: `- id: sbtd` / `name: '@kunolu/dsh-sbtd'`. `cordis.patch.yml` matches. |
| pin dsh@0.1.1-rc.2 | PASS | peerDependencies, package README, root README EN/ZH, `dsh --version`. No 0.1.0-rc.7 / 0.1.2-alpha in T0 README. |
| no trellis init --dsh | PASS | None in `packages/dsh-sbtd`. T0 PRD forbids it. |
| README no bare add / no local path / uses @kunolu/dsh-sbtd@next | FAIL | Root EN/ZH use `@kunolu/dsh-sbtd@next`. `packages/dsh-sbtd/README.md` still has local path add. Feature + test lock that in. |

## Findings

- Package README local-path install vs root `@kunolu/dsh-sbtd@next`. Feature + test lock the local-path contract.
- Stale empty pnpm importer / frozen install: `pnpm-lock.yaml` `packages/dsh-sbtd: {}`, no `@deepseek-ai/dsh`. CI `pnpm install --frozen-lockfile` (`.github/workflows/omp-runtime-linux-probe.yml`). PR 10 Codex P1 unresolved. Not T1.
- `private: true` vs root README published `@next` install. Local profile dump-config does not validate published-install.

## Notes

- `dist/` gitignored; no `prepare`. Local-path add without prior `tsc` has no entry (PR 10 Codex P1).
- Live dump-config scenario remains `@todo` in the feature.

## Tests

`node --test packages/dsh-sbtd/test/t0-stub.test.mjs` — 3 pass.

## Grill Q/A

none
