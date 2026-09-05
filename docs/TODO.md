# dsh-sbtd / sbtd-plugins — TODO & Progress

> **维护规则（强制）**：本文件是进度真源（living progress SOT）。每次里程碑 PR（合入功能/chore、开/关任务、改计划、发 npm）必须同步更新本文件；优先与对应功能/chore PR 同进 `main`，否则紧随单独 docs PR。由 Lord 协调，OMP 落地代码仓改动。

## Meta

| 字段 | 值 |
|---|---|
| 仓库 | `KunoLu/sbtd-plugins` |
| 设计文档 | `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` |
| 上次同步 | 2026-09-05（上海） |
| 同步时 main | ≈ `69a6acf`（#34 archive 合入后） |
| 包 | `@kunolu/dsh-sbtd@0.1.0-rc.1` → dist-tag **`next`**；`latest` **保留不动**，安装/文档**只推** `@next` |
| 宿主钉 | `@deepseek-ai/dsh@0.1.1-rc.2` |

---

## 1. 总览（P0–P3）

| 层级 | 范围 | 状态 |
|---|---|---|
| **P0** | T0–T3 骨架 + 硬门禁 | ✅ 完成 |
| **P1** | T4–T8 核心闭环 | 🟡 T4–T5 完成；T6–T8 未开；FU2 进行中 |
| **P2** | T9–T14 验证 / 移动端 | ⬜ 未开 |
| **P3** | T15–T16 入口 + 整包验收 | ⬜ 未开 |

---

## 2. P0（已完成）

| 任务 | 内容 | 状态 | 备注 |
|---|---|---|---|
| T0 | 可安装 stub（`dsh@0.1.1-rc.2`，`id: sbtd`） | ✅ | #10 等 |
| T1 | 短中文 section + session 状态 | ✅ | #16 / #17 |
| T2 | `sbtd_plan` | ✅ | #20 |
| T3 | hooks 门禁（生产路径 / rm 链等） | ✅ | #21 / #23 / #24 |

---

## 3. P1

| 任务 | 内容 | 状态 | 备注 |
|---|---|---|---|
| T4 | manuals 同步（640-skills v1.0.13 / `f8aa0d7`） | ✅ | #26–#29 |
| T5 | `sbtd_review` | ✅ | #30 → `b23b0f9` |
| T6 | `sbtd_clarify` | ⬜ 未开 | 依赖 T5；FU2 不挡澄清闭环 |
| T7 | Trellis 后端 | ⬜ 未开 | |
| T8 | `sbtd_spec` / tickets | ⬜ 未开 | 依赖 T6 / T7 |

---

## 4. P2 / P3（未开）

| 优先级 | 任务 | 内容 |
|---|---|---|
| P2 | T9 | GitNexus 后端 |
| P2 | T10 | `sbtd_validate` |
| P2 | T11 | `sbtd_bdd` |
| P2 | T12 | Maestro 预检 |
| P2 | T13 | `sbtd_e2e` |
| P2 | T14 | `sbtd_lessons` |
| P3 | T15 | `/sbtd` 命令与 README |
| P3 | T16 | 端到端验收 |

---

## 5. Follow-ups（T5 已知缺口）

| ID | 内容 | 状态 | 备注 |
|---|---|---|---|
| FU1 | Remediation Write：`seam-required` / `refactor-first` ↔ T3 `passed` 死锁 | ✅ | #33 → `7352071`；整窗 scoped allow；无字节级 seam/feature 分类器（Q4A honor） |
| FU2 | `sbtd_review` 强制 legacy-before-refactor | 🔄 **grill in progress** | 用户 2026-09-05 拍板；grill-with-docs 进行中（并行，不挡本 docs PR） |
| FU3 | multi-fact：`PREDICATES.find` 匹配集合 / 集合扩展重置 | ⬜ 未开 | T5 advisor 采纳后置 |

---

## 6. 发布与约定

### 发布

| 项 | 状态 |
|---|---|
| lockfile 补 `@deepseek-ai/dsh@0.1.1-rc.2` | ✅ #31；`omp-runtime-linux-probe` 已绿 |
| npm `@kunolu/dsh-sbtd@0.1.0-rc.1` → `next` | ✅ #32；冒烟 PASS |
| `latest=0.1.0-rc.1` | 🟡 **保留**（npm 往往删不掉 `latest`）；文档/安装**只推** `@kunolu/dsh-sbtd@next` |
| Trellis 历史积压 archive | ✅ #34 → `69a6acf`（T5/T4/pr10/pr12/v1.2） |
| OMP 配置（provider / fallback / 模型别名） | 🔒 **只读**；未经用户明确允许不得改 |

---

### 约定

1. **OMP 配置只读**：provider / fallback / 模型别名等未经用户明确允许不得改。
2. **开发**：全程 `omp` CLI；grill Q&A、`/review` 结论贴 SBTD Plugins 群；CLEAN 前不合。
3. **Trellis 方案 A**：开 PR → `/review` → 修到 CLEAN → **同 PR** `/trellis-finish-work` → 再合。新 task 不得长期停在 `in_progress`。
4. **模型汇报**：以 `omp` 实际输出 / session / stats 可核验清单为准；未知标未知，不用配置默认值补齐。
5. **本文件**：进度变更后实时同步（见文首维护规则）。

---

## 7. 下一步队列

| 顺序 | 项 | 状态 |
|---|---|---|
| 1 | **FU2** legacy-before-refactor（grill → 群投 → DDD → 编码 → review → 同 PR finish → 合） | 🔄 |
| 2 | **FU3** multi-fact 匹配集合 | ⬜ |
| 3 | **T6** `sbtd_clarify` | ⬜ |
| 4 | **T7–T8** → **P2/P3** | ⬜ |

---

## 8. 变更日志（本文件）

| 日期 | 说明 |
|---|---|
| 2026-09-05 | FU1 合入 `#33` → `7352071`；archive `#34` → main `69a6acf`；本文件 `docs/TODO.md` 初生为 living progress SOT；FU2（legacy-before-refactor）grill 已启动 |
