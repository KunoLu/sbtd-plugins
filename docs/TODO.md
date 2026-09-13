# dsh-sbtd / sbtd-plugins — TODO & Progress

> **维护规则（强制）**：本文件是进度真源摘要。每次里程碑（合 PR、开/关任务、改计划、发 npm）后必须同步更新；优先与对应功能/chore PR 同进 `main`，否则紧随单独 docs PR。由 Lord 协调，OMP 落地代码仓改动。

| 字段 | 值 |
|---|---|
| 仓库 | `KunoLu/sbtd-plugins` |
| 设计文档 | `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` |
| 上次同步 | 2026-09-13（上海） |
| 同步时 main | `1a9e809`（#74 TODO archive/FU5 → `1a9e809`；#73 TODO backfill after #72 @next pitfall → `578251b`；#70 rc.2 → `ae636e8`；#68 dsh CI → `c6c1d80`） |
| 包 | `@kunolu/dsh-sbtd@0.1.0-rc.2` dist-tag `next`（`latest` 仍 `0.1.0-rc.1`） |
| 宿主钉（peer） | `@deepseek-ai/dsh@0.1.1-rc.2`（本文件规划行**不**改 `peerDependencies`） |
| 上游 registry `@deepseek-ai/dsh` | `latest=0.1.5-rc.1`，`next=0.1.5-rc.2`（本轮未跑 `npm view`；按 Lord 绑定） |
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
- 宿主 peer 仍钉 `@deepseek-ai/dsh@0.1.1-rc.2`。上游 registry 已到 `0.1.5-rc.1` / `0.1.5-rc.2`；是否 bump peer / 发新插件 RC **等 FU5 锁完再编码**。
- manuals 仍钉 `640-skills` `1.0.13` / `f8aa0d7225a26c5e00b81d2f1b05121108e63630`。不单独跟 `v1.0.14`；目标 `v1.0.15`（等 tag）。
- Mac / 本机装新 RC：优先显式 `dsh plugin --profile web add @kunolu/dsh-sbtd@<version>`。`@next` 可能被 profile pnpm 锁粘到旧 RC（见 `docs/assets/dsh/ci-dsh-host-compat.md` 故障排查；#72）。同版本先 `remove` 再 `add`。

---

## 3. 下一步队列

| 顺序 | 项 | 状态 |
|---|---|---|
| 1 | **FU5** 宿主兼容调研（`0.1.1-rc.2` → `0.1.5-rc.1` / `0.1.5-rc.2`，含中间 0.1.2/0.1.3） | ⬜ 主序优先；本行不改 peer |
| 2 | **640-skills** pin → **v1.0.15** | ⬜ 次优先；等 tag；跳过单独同步 v1.0.14 |

### FU5 — 宿主兼容调研（主序优先）

目标：调研现有 `@kunolu/dsh-sbtd@0.1.0-rc.2` 相对宿主 `0.1.1-rc.2` → `0.1.5-rc.1` / `0.1.5-rc.2`（及中间 0.1.2 / 0.1.3）的 break surface。

遵循 [`docs/assets/dsh/ci-dsh-host-compat.md`](./assets/dsh/ci-dsh-host-compat.md)。步骤：changelog / API surface → advisory 矩阵（**同一 pack** × 候选 dsh）→ 决定 peer bump / 是否发新插件 RC。

**本规划行禁止立刻改 `peerDependencies`。** 编码只在 locks 之后。

| 子任务 | 内容 | 状态 |
|---|---|---|
| FU5-A | grill / locks（调研范围、候选版本、不改 peer 的冻结） | ⬜ |
| FU5-B | advisory 矩阵证据（same pack × 候选 dsh；不跑会因 FU4 硬钉假红的全量仓库 test 当唯一门） | ⬜ |
| FU5-C | 决策：compat 不 bump vs 适配 PR + 仅 `next` 发新 RC | ⬜ |

### 640-skills pin → v1.0.15（次优先；等 tag）

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
| 2026-09-13 | TODO archive/FU5 #74 → main `1a9e809`（TODO merge-SHA backfill） |
| 2026-09-13 | TODO archive/FU5 #74 scheme A finish/merge：r1 CLEAN @ `f64f726`；REQUIRED_CHANGES=none；squash `1a9e809`；不发布包 |
| 2026-09-13 | 归档 P0–P3 / FU1–FU4 / T0–T16 / CI / rc.2 / @next pitfall 至 `docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md`；活队列改为 FU5 + 640-skills v1.0.15；同步时 main `1c0903b`（#73） |
