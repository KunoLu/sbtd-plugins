# DSH 设计与 CI 笔记

- [上游 `dsh` 发新版时的宿主兼容校验](./ci-dsh-host-compat.md)
- [适配新 `640-skills` tag / 发 `dsh-sbtd` 新版前的校验](./ci-640-skills-adapt.md)

当前仓库准备版本：`@kunolu/dsh-sbtd@0.2.0-rc.3`，尚未发布；`0.2.0-rc.2` 的已发布及 npm `next`/`latest` 记录保留为有日期的历史，不作为当前 registry 重新核验。开发宿主仍为 `@deepseek-ai/dsh@0.2.0-rc.2`，peer / engines.dsh 仍为 `>=0.2.0-rc.2 <0.3.0-0`。PR127 已将 manuals 固定为 `640-skills 2.1.0` / `3c835303c23d59d3157ca84121a92f1bd87d4997`，本次不重新同步。独立 Actions：`.github/workflows/dsh-host-compat.yml`、`dsh-manuals-pin.yml`（不是 `omp-*`）；两个 REQUIRED 宿主为 `0.2.0-rc.2`、`0.2.1-rc.2`，候选 `0.2.2-rc.3` 也必须自身通过。上述 CI 笔记保留历史背景，当前门禁以真实 workflow 与本轮任务为准。

当前准备任务：[`dsh PR2 0.2.0-rc.3`](../../../ai/tasks/dsh-sbtd-0-2-0-rc-3-pr2-release-prep/task.md)。历史任务表：[`docs/prd/dsh-sbtd-0.2.0-rc.1.md`](../../prd/dsh-sbtd-0.2.0-rc.1.md)（0–G 行均已完成；旧 `docs/TODO.md` 已于 2026-10-18 退役，归档见 [`docs/legacy-archive/dsh-sbtd-todo-through-2026-09-19.md`](../../legacy-archive/dsh-sbtd-todo-through-2026-09-19.md)）。历史 P0–P3 / FU1–FU4 / T16 / CI：[`docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md`](../archive/dsh-sbtd-todo-archive-through-2026-09-13.md)。历史矩阵摘要见 [宿主兼容校验](./ci-dsh-host-compat.md)。本准备任务不授权合入或任何 tag/release/npm/dist-tag 操作。
