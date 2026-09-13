# PRD — dsh @next pitfall

## Goal

Same-PR scheme A finish for docs-only pitfall: `docs/assets/dsh/ci-dsh-host-compat.md` 故障排查 notes that `@kunolu/dsh-sbtd@next` can stick to an older RC via profile pnpm lock; prefer explicit `@kunolu/dsh-sbtd@<version>`.

## Users / scenarios

Operator installs from `next` after a new RC is published and still gets the previous RC because the DSH profile lock resolved `@next` to an old version.

## In scope

- Already landed: one 故障排查 row in `docs/assets/dsh/ci-dsh-host-compat.md` @ `615c5dd`
- Trellis closeout + `docs/TODO.md` progress (merge SHA pending until squash)
- Archive this task on PR #72

## Out of scope

- npm publish / retag `latest`
- omp config / MCP writes / `omp-compatibility-*`
- `packages/dsh-sbtd/src`
- Re-running full `/review`

## Constraints (locked)

- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2`
- Package: `@kunolu/dsh-sbtd@0.1.0-rc.2` on `next`; `latest` stays `0.1.0-rc.1`
- Branch: `docs/dsh-next-pitfall`
- PR: https://github.com/KunoLu/sbtd-plugins/pull/72
- Tip at review: `615c5dd21e4340aa7bb3b42eaf04268449544b33`

## Acceptance

- [x] Pitfall row in `ci-dsh-host-compat.md`: prefer explicit `@kunolu/dsh-sbtd@<version>`; `@next` can stick via profile pnpm lock.
- [x] Review r1 CLEAN @ `615c5dd`; `REQUIRED_CHANGES=none`; Quality=pass Security=pass Advisor=PASS.
- [x] `/trellis:finish-work` archive as completed (scheme A, same PR #72).
- [ ] PR #72 merge to `main`（SHA pending squash）.

## grill-with-docs

未完整调用。原因：docs-only closeout；坑点已由现有 CI 指南与 PR #72 事实回答；不涉及新领域模型。

## Book Gate Plan

| Skill | required/on-demand | Trigger | Phase | Gate state |
|---|---|---|---|---|
| book-refactoring-pass | on-demand | 不改既有生产代码 | — | not-required |
| book-legacy-change-safety | on-demand | 非既有行为 bug | — | not-required |
| book-ddd-distilled-modeling | on-demand | 未 grill；无领域模型变更 | — | not-required |
| book-ddia-data-design | on-demand | 无持久化/共享数据变更 | — | not-required |
| book-release-readiness | on-demand | 非生产服务路径；仅文档 | — | not-required |
