# DSH 设计与 CI 笔记

- [上游 `dsh` 发新版时的宿主兼容校验](./ci-dsh-host-compat.md)
- [适配新 `640-skills` tag / 发 `dsh-sbtd` 新版前的校验](./ci-640-skills-adapt.md)

钉：`@kunolu/dsh-sbtd@0.1.0-rc.2`（已发布到 `next`；`latest` 仍为 `0.1.0-rc.1`），宿主 `@deepseek-ai/dsh@0.1.1-rc.2`，manuals `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`。拟议独立 Actions 名：`dsh-host-compat`、`dsh-manuals-pin`（不是 `omp-*`）。独立 Actions：`.github/workflows/dsh-host-compat.yml`、`dsh-manuals-pin.yml`（已入库本 PR）。REQUIRED 门以本指南命令 + 这些 workflow 为准；勿改 `omp-*`。

活队列：[`docs/TODO.md`](../../TODO.md)（FU5 Round1 收口 Q1A/Q2A：peer 仍 `0.1.1-rc.2`，advisory tip `0.1.5-rc.2` → 640-skills v1.0.15）。历史 P0–P3 / FU1–FU4 / T16 / CI：[`docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md`](../archive/dsh-sbtd-todo-archive-through-2026-09-13.md)。矩阵摘要见 [宿主兼容校验](./ci-dsh-host-compat.md)。
