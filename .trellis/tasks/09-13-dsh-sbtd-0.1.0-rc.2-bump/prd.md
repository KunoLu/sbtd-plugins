# PRD — dsh-sbtd 0.1.0-rc.2 bump

## Goal

From origin/main tip `11571234ed109f2037f94615caefb6ecf5bd1d01`, bump `@kunolu/dsh-sbtd` to `0.1.0-rc.2`, run local REQUIRED tests/pack/manuals pin, open Scheme A PR. Do not npm publish.

## Users / scenarios

- Maintainers prepare a candidate tarball for a later publish run.
- Consumers of dist-tag `next` still install currently published `0.1.0-rc.1` until a later npm publish.

## In scope

- Branch `release/dsh-sbtd-0.1.0-rc.2` from the named tip
- `packages/dsh-sbtd/package.json` version `0.1.0-rc.2`
- In-repo pins that must match package.json version (tests, smoke, BDD, package README)
- `docs/TODO.md` pending-publish note
- Local REQUIRED: `pnpm --filter @kunolu/dsh-sbtd test`; pack and assert `package/dist/index.js`; manuals MANIFEST `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`
- Commit, push, open PR (Scheme A). Do not merge.

## Out of scope

- `npm publish`
- npm dist-tag `latest` or `next`
- omp config
- host pin `@deepseek-ai/dsh@0.1.1-rc.2`
- product behavior in `packages/dsh-sbtd/src`
- merge unless asked

## Constraints (locked)

- Host pin stays `@deepseek-ai/dsh@0.1.1-rc.2`
- Candidate package version `0.1.0-rc.2` is **not** published; `next` remains `0.1.0-rc.1` until a later run
- README / BDD must not claim rc.2 is already on `next`
- manuals pin: `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`

## Acceptance

- [x] `packages/dsh-sbtd/package.json` version is `0.1.0-rc.2`; peer host pin unchanged
- [x] Matching test/BDD/smoke pins updated; docs distinguish candidate vs published `next`
- [x] `pnpm --filter @kunolu/dsh-sbtd test` pass
- [x] Packed tarball contains `package/dist/index.js`; sha256 recorded
- [x] MANIFEST version `1.0.13` and sourceRevision `f8aa0d7225a26c5e00b81d2f1b05121108e63630`
- [ ] PR opened, not merged; TODO notes pending publish
- [x] No `npm publish`

## grill-with-docs

未完整调用。原因：User+Lord 已锁版本字符串与发布路径；无领域模型/术语变更。

## Book Gate Plan

| Skill | required/on-demand | Trigger | Phase | Gate state |
|---|---|---|---|---|
| book-refactoring-pass | on-demand | version strings only; no production module edit | — | not-required |
| book-legacy-change-safety | on-demand | not an existing-behavior bug | — | not-required |
| book-ddd-distilled-modeling | on-demand | no grill; no domain model change | — | not-required |
| book-ddia-data-design | on-demand | no persisted/shared data | — | not-required |
| book-release-readiness | required | publish-path version/rollout prep | after validation | planned |
