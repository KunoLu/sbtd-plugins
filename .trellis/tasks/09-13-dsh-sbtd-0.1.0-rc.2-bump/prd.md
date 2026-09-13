# PRD — dsh-sbtd 0.1.0-rc.2 bump

## Goal

From origin/main tip `11571234ed109f2037f94615caefb6ecf5bd1d01`, bump `@kunolu/dsh-sbtd` to `0.1.0-rc.2`. Registry fact: `0.1.0-rc.2` **was** published to dist-tag `next`; `latest` remains `0.1.0-rc.1`. Do not run a second `npm publish`. Keep host pin `@deepseek-ai/dsh@0.1.1-rc.2`.

## Users / scenarios

- Maintainers keep the already-published `0.1.0-rc.2` tarball aligned with in-repo pins and consumer docs.
- Consumers of dist-tag `next` install published `0.1.0-rc.2`.
- Consumers of dist-tag `latest` still install `0.1.0-rc.1`.

## In scope

- Branch `release/dsh-sbtd-0.1.0-rc.2` from the named tip
- `packages/dsh-sbtd/package.json` version `0.1.0-rc.2`
- In-repo pins that must match package.json version (tests, smoke, BDD, package README)
- Consumer README / BDD claim `next=0.1.0-rc.2` and `latest=0.1.0-rc.1`
- `docs/TODO.md` pending-publish note (publish to `next` already happened)
- Local REQUIRED: `pnpm --filter @kunolu/dsh-sbtd test`; pack and assert `package/dist/index.js`; manuals MANIFEST `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`
- Commit, push, open PR (Scheme A). Do not merge. Do not `npm publish` again.

## Out of scope

- Second `npm publish`
- Moving dist-tag `latest` off `0.1.0-rc.1`
- omp config
- changing host pin `@deepseek-ai/dsh@0.1.1-rc.2`
- product behavior in `packages/dsh-sbtd/src`
- merge unless asked

## Constraints (locked)

- Host pin stays `@deepseek-ai/dsh@0.1.1-rc.2`
- `0.1.0-rc.2` **was** published to dist-tag `next`
- `latest` remains `0.1.0-rc.1`
- No second `npm publish`
- Consumer README / BDD correctly claim `next=0.1.0-rc.2`
- manuals pin: `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`

## Acceptance

- [x] `packages/dsh-sbtd/package.json` version is `0.1.0-rc.2`; peer host pin unchanged
- [x] Matching test/BDD/smoke pins updated; consumer README/BDD claim `next=0.1.0-rc.2` and `latest=0.1.0-rc.1`
- [x] `pnpm --filter @kunolu/dsh-sbtd test` pass
- [x] Packed tarball contains `package/dist/index.js`; sha256 `95d199e435cf917cd2045e8ba0a7feb29a80fad16fd376f7df5101d408bfd0ed`
- [x] MANIFEST version `1.0.13` and sourceRevision `f8aa0d7225a26c5e00b81d2f1b05121108e63630`
- [x] PR opened, not merged: https://github.com/KunoLu/sbtd-plugins/pull/70
- [x] No second `npm publish`; `next=0.1.0-rc.2`; `latest=0.1.0-rc.1`

## grill-with-docs

未完整调用。原因：User+Lord 已锁版本字符串与发布路径；无领域模型/术语变更。

## Book Gate Plan

| Skill | required/on-demand | Trigger | Phase | Gate state |
|---|---|---|---|---|
| book-refactoring-pass | on-demand | version strings only; no production module edit | — | not-required |
| book-legacy-change-safety | on-demand | not an existing-behavior bug | — | not-required |
| book-ddd-distilled-modeling | on-demand | no grill; no domain model change | — | not-required |
| book-ddia-data-design | on-demand | no persisted/shared data | — | not-required |
| book-release-readiness | required | publish-path version/rollout prep | after validation | passed |

## Release Readiness Review

Status: ready

Production path and affected users / systems: `@kunolu/dsh-sbtd@0.1.0-rc.2` is already on npm dist-tag `next`. `latest` consumers still get `0.1.0-rc.1`. Host pin stays `@deepseek-ai/dsh@0.1.1-rc.2`.

Failure modes and safeguards: a second `npm publish` would duplicate or retag; claiming `next` is still `0.1.0-rc.1` would mis-install. README/BDD now correctly claim `next=0.1.0-rc.2`. This PR does not publish.

Capacity / backpressure / limits: not-applicable.

Observability / alerts / runbook: 331 tests; pack `package/dist/index.js`; tarball sha256 `95d199e435cf917cd2045e8ba0a7feb29a80fad16fd376f7df5101d408bfd0ed`; MANIFEST `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`.

Rollout / migration / rollback / cleanup: Scheme A PR #70 only; do not merge unless asked. Registry already has `next=0.1.0-rc.2`. Rollback: leave unmerged; do not republish; do not move `latest`.

Required validation and result: `pnpm --filter @kunolu/dsh-sbtd test` 331/331; pack_dist=yes. r2: PRD publish-state language aligned with registry; npm=no.

Optional checks, accountable owner acceptance, and residual risk: second npm publish forbidden (User+Lord). Residual: `latest` remains `0.1.0-rc.1` by design.

