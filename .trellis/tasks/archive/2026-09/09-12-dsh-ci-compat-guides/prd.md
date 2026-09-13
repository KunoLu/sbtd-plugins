# PRD — dsh CI 兼容指南

## Goal

在 `docs/assets/dsh/` 落地两份中文 CI 指南，并优先补独立 `dsh-*` GitHub Actions。不发布 npm，不改 `packages/dsh-sbtd/src`，不改 `omp-compatibility-*` workflow。

## Users / scenarios

- 上游 `@deepseek-ai/dsh` 发新版时：如何校验当前 `@kunolu/dsh-sbtd@0.1.0-rc.1` 是否还能挂在钉 `0.1.1-rc.2` 或候选宿主上。
- 适配新 `640-skills` tag / 发 `dsh-sbtd` 新版前：如何校验 manuals pin 与 pack。

## In scope

- `docs/assets/dsh/ci-dsh-host-compat.md`
- `docs/assets/dsh/ci-640-skills-adapt.md`
- `docs/assets/dsh/README.md` 中文索引
- `.github/workflows/dsh-host-compat.yml`、`.github/workflows/dsh-manuals-pin.yml`（`workflow_dispatch` 可因私有 `@deepseek-ai/dsh` 注册表）
- 可选 `docs/TODO.md` 一行进度

## Out of scope

- npm publish
- 改 omp 配置或 `omp-compatibility-*`
- 改 `packages/dsh-sbtd/src`
- 合并本 PR
- `/review` 除非用户再要求

## Constraints (locked)

- Host pin: `@deepseek-ai/dsh@0.1.1-rc.2`
- Package: `@kunolu/dsh-sbtd@0.1.0-rc.1`
- manuals pin: `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`
- 人工最少：仅 `dsh web` 审批弹窗（T16 step3 类）发版前抽检
- 矩阵先 advisory

## Acceptance

- [x] 每份中文文档含：触发条件 → 自动化门禁清单 → 人工最少清单 → PASS/FAIL → 发版/不发版决策树 → 故障排查。
- [x] 开 PR #68；独立 `dsh-host-compat.yml` / `dsh-manuals-pin.yml`；不改 omp-*；不 npm。
- [x] Review r2 CLEAN @ `d6ff5385c67d20ad49876739d4b7d4ad86fb9f36`；`REQUIRED_CHANGES=none`；r1 nits closed。
- [x] `/trellis:finish-work` archive as completed（scheme A，same PR #68）。
- [ ] PR #68 merge to `main`（SHA pending squash）。

## grill-with-docs

未完整调用。原因：User+Lord 已锁方案；事实可由仓库种子与 T16 记录回答。

## Book Gate Plan

| Skill | required/on-demand | Trigger | Phase | Gate state |
|---|---|---|---|---|
| book-refactoring-pass | on-demand | 不改既有生产代码 | — | not-required |
| book-legacy-change-safety | on-demand | 非既有行为 bug | — | not-required |
| book-ddd-distilled-modeling | on-demand | 未 grill；无领域模型变更 | — | not-required |
| book-ddia-data-design | on-demand | 无持久化/共享数据变更 | — | not-required |
| book-release-readiness | on-demand | 非生产服务路径；CI 文档+dispatch | — | not-required |
