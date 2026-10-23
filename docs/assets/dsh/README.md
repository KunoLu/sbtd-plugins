# DSH 设计与 CI 笔记

- [上游 `dsh` 发新版时的宿主兼容校验](./ci-dsh-host-compat.md)
- [适配新 `640-skills` tag / 发 `dsh-sbtd` 新版前的校验](./ci-640-skills-adapt.md)

钉：`@kunolu/dsh-sbtd@0.2.0-rc.2`（已发布；npm `next` 与 `latest` 均指向该版本），开发宿主 `@deepseek-ai/dsh@0.2.0-rc.2`（peer / engines.dsh 为 `>=0.2.0-rc.2 <0.3.0-0`），manuals `640-skills` `2.0.2` / `1d82494d74f6df9bca7dccef2da409f87091883e`。独立 Actions：`.github/workflows/dsh-host-compat.yml`、`dsh-manuals-pin.yml`（不是 `omp-*`）。当前 REQUIRED 门以这些 workflow 与活队列 PRD 为准；上述 CI 笔记保留历史执行背景，勿用旧钉替代当前配置。

活队列：[`docs/prd/dsh-sbtd-0.2.0-rc.1.md`](../../prd/dsh-sbtd-0.2.0-rc.1.md)（进度真源已迁入该 PRD，0–G 行均已完成；旧 `docs/TODO.md` 已于 2026-10-18 退役，归档见 [`docs/legacy-archive/dsh-sbtd-todo-through-2026-09-19.md`](../../legacy-archive/dsh-sbtd-todo-through-2026-09-19.md)）。历史 P0–P3 / FU1–FU4 / T16 / CI：[`docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md`](../archive/dsh-sbtd-todo-archive-through-2026-09-13.md)。历史矩阵摘要见 [宿主兼容校验](./ci-dsh-host-compat.md)。
