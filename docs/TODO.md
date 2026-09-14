# dsh-sbtd / sbtd-plugins — TODO & Progress

> **维护规则（强制）**：本文件是进度真源摘要。每次里程碑（合 PR、开/关任务、改计划、发 npm）后必须同步更新；优先与对应功能/chore PR 同进 `main`，否则紧随单独 docs PR。由 Lord 协调，OMP 落地代码仓改动。

| 字段 | 值 |
|---|---|
| 仓库 | `KunoLu/sbtd-plugins` |
| 设计文档 | `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` |
| 上次同步 | 2026-09-14（上海；T16 acceptance 归档 #85 squash `953109d`） |
| 同步时 main | `953109d`（#85 archive T16 acceptance → `953109d`；#84 TODO #83 merge SHA backfill → `149f759`；#83 FU5 Round3 closeout no bump → `e6bc4c8`；#82 host-compat ask gate vs Q3C → `bba3040`；#81 TODO #80 merge SHA backfill → `afe6da6`；#80 FU5-C Round2 closeout Q3C/Q4A/Q5A → `081866b`；#79 TODO #78 merge SHA backfill → `93f853d`；#78 Mac ask PASS latest=`0.1.5-rc.1` → `12d2610`；#77 TODO #76 merge SHA backfill → `d9b3e5f`；#76 FU5-C Round1 closeout → `1fd43c4`；#75 TODO #74 merge SHA backfill → `7e9d5ac`；#74 TODO archive/FU5 → `1a9e809`；#73 TODO backfill after #72 @next pitfall → `578251b`；#70 rc.2 → `ae636e8`；#68 dsh CI → `c6c1d80`） |
| 包 | `@kunolu/dsh-sbtd@0.1.0-rc.2` dist-tag `next`（`latest` 仍 `0.1.0-rc.1`） |
| 宿主钉（peer） | `@deepseek-ai/dsh@0.1.1-rc.2`（本文件规划行**不**改 `peerDependencies`） |
| 上游 registry `@deepseek-ai/dsh` | `latest=0.1.5-rc.1`，`next=0.1.5-rc.2`（FU5-B 已核；advisory tip = `0.1.5-rc.2`，**不**升 REQUIRED） |
| manuals pin | `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630` |
| 历史 P0–P3 / FU1–FU4 / T0–T16 / CI / rc.2 / @next pitfall | [`docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md`](./assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md) |

---

## 1. 现行约定

1. **开发**：全程 `omp` CLI；grill Q&A、`/review` 结论贴 SBTD Plugins 群；CLEAN 前不合。
2. **归档（方案 A）**：开 PR → `/review` → 修到 CLEAN → **同 PR** `/trellis-finish-work` → 再合。新 task 不得长期停在 `in_progress`。
3. **模型汇报**：以 `omp` 实际输出 / session / stats 可核验清单为准；未知标未知，不用配置默认值补齐。
4. **本文件**：进度变更后实时同步（见文首维护规则）。

---

## 2. 包与宿主钉现状

- 插件：`@kunolu/dsh-sbtd@0.1.0-rc.2` → `next`；`latest` 仍 `0.1.0-rc.1`（保留；文档/安装只推 `next` 或显式版本）。
- 宿主 peer 仍钉 `@deepseek-ai/dsh@0.1.1-rc.2`（FU5-C Round1 **Q1A** + Round2 **Q4A**：不放宽 peerRange）。REQUIRED / FU4 仍钉 `0.1.1-rc.2`（**Q5A**）。advisory tip（**Q2A**）= `0.1.5-rc.2`（registry `next`）；**禁止**升 REQUIRED / FU4 钉。Mac ask latest-line（dsh=`0.1.5-rc.1`）2026-09-14 **PASS**（**Q3C**：只覆盖该版本；把 `0.1.5-rc.2` 写入 peerRange 仍要 tip ask）。Round3 已收口：明确 **不 bump** / 不发新 RC；FU5 ✅ 收口。
- manuals 仍钉 `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`。不单独跟 `v1.0.14`；目标 `v1.0.15`（等 tag）。
- Mac / 本机装新 RC：优先显式 `dsh plugin --profile web add @kunolu/dsh-sbtd@<version>`。`@next` 可能被 profile pnpm 锁粘到旧 RC（见 `docs/assets/dsh/ci-dsh-host-compat.md` 故障排查；#72）。同版本先 `remove` 再 `add`。

---

## 3. 下一步队列

| 顺序 | 项 | 状态 |
|---|---|---|
| 1 | **FU5** 宿主兼容调研（`0.1.1-rc.2` → `0.1.5-rc.1` / `0.1.5-rc.2`，含中间 0.1.2/0.1.3） | ✅ Round3 收口：**不 bump**；FU5 正式关闭；tip `0.1.5-rc.2` ask 留 optional；下一主线等 640 `v1.0.15` |
| 2 | **640-skills** pin → **v1.0.15** | ⬜ 主序优先 / 现行主线；等 tag；跳过单独同步 v1.0.14 |

### FU5 — 宿主兼容调研（✅ Round3 已收口）

目标：调研现有 `@kunolu/dsh-sbtd@0.1.0-rc.2` 相对宿主 `0.1.1-rc.2` → `0.1.5-rc.1` / `0.1.5-rc.2`（及中间 0.1.2 / 0.1.3）的 break surface。

遵循 [`docs/assets/dsh/ci-dsh-host-compat.md`](./assets/dsh/ci-dsh-host-compat.md)。步骤：changelog / API surface → advisory 矩阵（**同一 pack** × 候选 dsh）→ 决定 peer bump / 是否发新插件 RC。

**本规划行禁止立刻改 `peerDependencies`。** FU5-C Round1 已锁 Q1A：精确钉 `0.1.1-rc.2`。Round2 已锁 **Q3C / Q4A / Q5A**：不放宽 peerRange；REQUIRED/FU4 仍 `0.1.1-rc.2`；latest ask PASS 不覆盖 tip。Round3 已收口：明确 **不 bump** / 不发新 RC；FU5 ✅ 关闭；tip `0.1.5-rc.2` ask 留 optional。

| 子任务 | 内容 | 状态 |
|---|---|---|
| FU5-A | grill / locks（调研范围、候选版本、不改 peer 的冻结） | ✅ Q1B / Q2B / Q3C / Q4A / Q5B / Q6A |
| FU5-B | advisory 矩阵证据（same pack × 候选 dsh；不跑会因 FU4 硬钉假红的全量仓库 test 当唯一门） | ✅ 钉 + 解析格全 PASS（`0.1.2`→`0.1.2-rc.1`，`0.1.3`→`0.1.3-alpha.2` 非稳定，`0.1.5-rc.1`/`rc.2`）；见 [`ci-dsh-host-compat.md`](./assets/dsh/ci-dsh-host-compat.md) |
| FU5-C | 决策：compat 不 bump vs 适配 PR + 仅 `next` 发新 RC | ✅ Round1 锁 **Q1A / Q2A**（精确钉 + advisory tip `0.1.5-rc.2`）；#76 文档收口。Mac ask **PASS** on `latest=0.1.5-rc.1` #78（2026-09-14 上海；plugin `@kunolu/dsh-sbtd@0.1.0-rc.2` 显式 add；workspace=`sbtd-plugins`；无 `sbtd_plan`；edit `packages/dsh-sbtd/src/section.ts`；`kind=ask` 含「尚未 sbtd_plan，请先调用 sbtd_plan。」）。tip `0.1.5-rc.2` 仍 tip-only、人工未跑。Round2 锁 **Q3C / Q4A / Q5A** #80 → `081866b`：peer/REQUIRED/FU4 仍精确钉 `0.1.1-rc.2`（不放宽 peerRange）；latest PASS 只覆盖 `0.1.5-rc.1`；写入 `0.1.5-rc.2` 到 peerRange 仍要 tip ask；本锁集无新插件 RC。Round3 收口 #83 → `e6bc4c8`（不 bump；FU5 ✅；tip ask optional；无 peer/npm/src） |

### 640-skills pin → v1.0.15（主序优先 / 现行主线；等 tag）

- 现行 pin：`v1.0.13`。
- **跳过单独同步到 v1.0.14**（已有 tag；先跟 14 再跟 15 = 双次 sync-manuals）。
- 目标：**v1.0.15** 在 tag 存在时；遵循 [`docs/assets/dsh/ci-640-skills-adapt.md`](./assets/dsh/ci-640-skills-adapt.md)。
- 在 15 tag 之前：可选只读 tip / 14 scan（Researchy），不落地。

| 子任务 | 内容 | 状态 |
|---|---|---|
| 15-A | 等待 `640-skills` **v1.0.15** tag | ⬜ |
| 15-B | `sync-manuals` + MANIFEST + t4 / 全量 test | ⬜ |
| 15-C | 若 skill 契约变了：适配 + 可能新插件 RC（仅 `next`）；契约兼容默认可不发 | ⬜ |

---

## 4. 变更日志（本文件）

| 日期 | 说明 |
|---|---|
| 2026-09-14 | T16 acceptance 归档 #85：`docs/acceptance.md` → `docs/assets/archive/dsh-sbtd-acceptance-t16.md`；r1 CLEAN @ `5a1354f`；squash `953109d`；无 npm；无 peer/src |
| 2026-09-14 | FU5 Round3 收口：**不 bump**；FU5 ✅ 关闭；tip `0.1.5-rc.2` ask 留 optional；下一主线等 640 `v1.0.15`；无 peer/npm/src：r1 CLEAN @ `d84f5ad`；squash `e6bc4c8` |
| 2026-09-14 | FU5-C Round2 文档收口 #80：r1 CLEAN @ `71525a8`；squash `081866b`；锁 Q3C/Q4A/Q5A（Round1 Q1A/Q2A 仍有效）；peer 仍 `0.1.1-rc.2`；无 npm；无新 RC |
| 2026-09-14 | FU5 Mac ask PASS #78（`latest=0.1.5-rc.1`）：r1 CLEAN @ `ffe4b9d`；squash `12d2610`；Mac；plugin `@kunolu/dsh-sbtd@0.1.0-rc.2` 显式 add；workspace=`sbtd-plugins` 无 `sbtd_plan`；edit `packages/dsh-sbtd/src/section.ts`；`kind=ask` 含「尚未 sbtd_plan，请先调用 sbtd_plan。」；advisory tip `0.1.5-rc.2` 仍 tip-only；peer 未改；无 npm |
| 2026-09-14 | FU5-C Round1 文档收口 #76：r2 CLEAN @ `a1c3716`；squash `1fd43c4`；锁 Q1A/Q2A；peer 仍 `0.1.1-rc.2`；无 npm |
| 2026-09-13 | TODO archive/FU5 #74 → main `1a9e809`（TODO merge-SHA backfill） |
| 2026-09-13 | TODO archive/FU5 #74 scheme A finish/merge：r1 CLEAN @ `f64f726`；REQUIRED_CHANGES=none；squash `1a9e809`；不发布包 |
| 2026-09-13 | 归档 P0–P3 / FU1–FU4 / T0–T16 / CI / rc.2 / @next pitfall 至 `docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md`；活队列改为 FU5 + 640-skills v1.0.15；同步时 main `1c0903b`（#73） |
