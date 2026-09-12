# DSH 设计与 CI 笔记

- [上游 `dsh` 发新版时的宿主兼容校验](./ci-dsh-host-compat.md)
- [适配新 `640-skills` tag / 发 `dsh-sbtd` 新版前的校验](./ci-640-skills-adapt.md)

钉：`@kunolu/dsh-sbtd@0.1.0-rc.1`，宿主 `@deepseek-ai/dsh@0.1.1-rc.2`，manuals `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`。拟议独立 Actions 名：`dsh-host-compat`、`dsh-manuals-pin`（不是 `omp-*`）。**本 PR 未入库** `.github/workflows/dsh-*.yml`（push 需要 GitHub token `workflow` scope）；REQUIRED 门以本指南命令为准，不要当作仓库里已有可 dispatch 的 workflow。
