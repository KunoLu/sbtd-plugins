# dsh-sbtd / sbtd-plugins — TODO & Progress

> **维护规则（强制）**：本文件是进度真源摘要。每次里程碑（合 PR、开/关任务、改计划、发 npm）后必须同步更新；优先与对应功能/chore PR 同进 `main`，否则紧随单独 docs PR。由 Lord 协调，OMP 落地代码仓改动。

| 字段 | 值 |
|---|---|
| 仓库 | `KunoLu/sbtd-plugins` |
| 设计文档 | `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` |
| 上次同步 | 2026-09-11（上海） |
| 同步时 main | `0dbe135`（#62 T15 → `0dbe135`；#61 gitignore；#59 T14 → `2b7cf61`；#57 T13 → `9289798`；#55 T12 → `61026a1`；#53 T11 → `d729d6e`；T10 #51 → `014f480`） |
| 包 | `@kunolu/dsh-sbtd@0.1.0-rc.1` dist-tag `next`（`latest` 暂留同版本） |
| 宿主钉 | `@deepseek-ai/dsh@0.1.1-rc.2` |

---

## 1. 总览（P0–P3）

| 层级 | 范围 | 状态 |
|---|---|---|
| **P0** | T0–T3 骨架 + 硬门禁 | ✅ 完成 |
| **P1** | T4–T8 核心闭环 | ✅ T4–T8 完成（T8 #47 → `a90a96f`；T7 `b73ece9`）；FU2 ✅；FU3 ✅ #43 → `2a82e63` |
| **P2** | T9–T14 验证 / 移动端 | ✅ T9 ✅ #49 → `314c345`；T10 ✅ #51 → `014f480`；T11 ✅ #53 → `d729d6e`；T12 ✅ #55 → `61026a1`；T13 ✅ #57 → `9289798`；T14 ✅ #59 → `2b7cf61` |
| **P3** | T15–T16 入口 + 整包验收 | ✅ T15 ✅ #62 → `0dbe135`；T16 ⬜ |

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
| T6 | `sbtd_clarify` | ✅ | #39 → `4e76ae8`；scheme A finish；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T7 | Trellis 后端 | ✅ | #45 → `b73ece9`；scheme A finish；CLEAN r3；tests 136；locks Q1C Q2B Q3A Q4A Q5A Q6B；archive `09-09-dsh-sbtd-t7-trellis-backend-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T8 | `sbtd_spec` / tickets | ✅ | #47 → `a90a96f`；scheme A finish；CLEAN r3；tests 150/150；locks Q1C Q2A Q3A Q4A Q5A Q6A；archive `09-09-dsh-sbtd-t8-sbtd-spec-tickets-grill` + `09-09-dsh-sbtd-t8-sbtd-spec-tickets-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |

---

## 4. P2 / P3

| 任务 | 内容 | 状态 | 备注 |
|---|---|---|---|
| T9 | GitNexus 后端 | ✅ | #49 → `314c345`；scheme A finish；CLEAN r2；locks Q1B Q2A Q3A Q4A Q5A Q6A；REQUIRED_CHANGES=none；r1 REQUIRED closed（`--index-only` + skip-before-analyze）；archive `09-09-dsh-sbtd-t9-gitnexus-backend-grill` + `09-09-dsh-sbtd-t9-gitnexus-backend-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T10 | `sbtd_validate` | ✅ | #51 → `014f480`；scheme A finish；CLEAN r4；locks Q1A Q2A Q3A(+clar) Q4A Q5A；REQUIRED_CHANGES=none；r1–r3 REQUIRED closed；archive `09-09-dsh-sbtd-t10-sbtd-validate-grill` + `09-09-dsh-sbtd-t10-sbtd-validate-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T11 | `sbtd_bdd` | ✅ | #53 → `d729d6e`；scheme A finish；CLEAN r5；locks Q1C Q2B Q3A Q4A Q5A Q6A；REQUIRED_CHANGES=none；r1–r5 REQUIRED closed；archive `09-10-dsh-sbtd-t11-sbtd-bdd-grill` + `09-10-dsh-sbtd-t11-sbtd-bdd-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T12 | Maestro 预检 | ✅ | #55 → `61026a1`；scheme A finish；CLEAN r3；locks Q1A Q2A Q3A Q4A Q5A Q6A；REQUIRED_CHANGES=none；r1–r2 REQUIRED closed；archive `09-10-dsh-sbtd-t12-maestro-precheck-grill` + `09-10-dsh-sbtd-t12-maestro-precheck-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T13 | `sbtd_e2e` | ✅ | #57 → `9289798`；scheme A finish；CLEAN r5；locks Q1B Q2A Q3A Q4A Q5A Q6A；REQUIRED_CHANGES=none；r1–r4 REQUIRED closed；archive `09-10-dsh-sbtd-t13-sbtd-e2e-grill` + `09-10-dsh-sbtd-t13-sbtd-e2e-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T14 | `sbtd_lessons` | ✅ | #59 → `2b7cf61`；scheme A finish；product CLEAN r3 @ `e4bf2b1`；process clear tip `ffb081d`；locks Q1A Q2A Q3A Q4A Q5A Q6A；REQUIRED_CHANGES=none；r1–r3 REQUIRED closed；process gaps cleared；archive `09-11-dsh-sbtd-t14-sbtd-lessons-grill` + `09-11-dsh-sbtd-t14-sbtd-lessons-ddd` + `09-11-dsh-sbtd-t14-sbtd-lessons-implement`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T15 | `/sbtd` 命令与 README | ✅ | #62 → `0dbe135`；scheme A finish；CLEAN r5 @ `3529daf`；product r3b CLEAN @ `f8561bf`；process r4b CLEAN @ `70d3a60`；locks Q1A–Q6A；REQUIRED_CHANGES=none；R1–R4 CLOSED；tests 322/322（t15 12/12）；archive `09-11-dsh-sbtd-t15-sbtd-command` + `09-11-dsh-sbtd-t15-sbtd-command-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2` |
| T16 | 端到端验收 | ⬜ | P3 |

---

## 5. Follow-ups（T5 已知缺口）

| ID | 内容 | 状态 | 备注 |
|---|---|---|---|
| FU1 | Remediation Write：`seam-required` / `refactor-first` ↔ T3 `passed` 死锁 | ✅ | #33 → `7352071`；整窗 scoped allow；无字节级 seam/feature 分类器（Q4A honor） |
| FU2 | `sbtd_review` 强制 legacy-before-refactor | ✅ | #37 → `f039a99`；Review Recording Order on `sbtd_review` only；88/88；archive `09-07-dsh-sbtd-fu2-legacy-before-refactor` |
| FU3 | multi-fact matching-set + persist-across-replans | ✅ | [#43](https://github.com/KunoLu/sbtd-plugins/pull/43) scheme A finish；CLEAN r5；tip `bdc25f3` / prod `d2194f5`；tests 121/121；locks Q1D Q2B Q3A Q4B Q5A；archive `09-08-dsh-sbtd-fu3-multi-fact-persist`；#43 → `2a82e63` |
| FU4 | clarify JSON schema host-compatible omit-null | 🟡 ready | [#65](https://github.com/KunoLu/sbtd-plugins/pull/65) scheme A finish；CLEAN r3 @ `ca9eb8f`；tests 331/331；locks Q1B Q2B Q3C Q4A PASS；Q5A pending post-merge T16；R1 CLOSED；R2 CLOSED；REQUIRED_CHANGES=none；archive `09-12-dsh-sbtd-fu4-clarify-schema-grill` + `09-12-dsh-sbtd-fu4-clarify-schema-ddd`；host `@deepseek-ai/dsh@0.1.1-rc.2`；**未合**（merge SHA pending） |

---

## 6. 发布与工程杂项

| 项 | 状态 |
|---|---|
| lockfile 补 `@deepseek-ai/dsh@0.1.1-rc.2` | ✅ #31；`omp-runtime-linux-probe` 已绿 |
| npm `@kunolu/dsh-sbtd@0.1.0-rc.1` → `next` | ✅ #32；冒烟 PASS |
| `latest=0.1.0-rc.1` | 🟡 **保留**（npm 往往删不掉 `latest`）；文档/安装**只推** `@kunolu/dsh-sbtd@next` |
| Trellis 历史积压 archive | ✅ #34 → `69a6acf`（T5/T4/pr10/pr12/v1.2） |
| OMP 配置（provider / fallback / 模型别名） | 🔒 **只读**；未经用户明确允许不得改 |
| `omp-compatibility-certification` | workflow_dispatch-only（无 cron）；Environments Required reviewers 移除为用户侧（2026-09-08） |

---

## 7. 现行约定

1. **开发**：全程 `omp` CLI；grill Q&A、`/review` 结论贴 SBTD Plugins 群；CLEAN 前不合。
2. **归档（方案 A）**：开 PR → `/review` → 修到 CLEAN → **同 PR** `/trellis-finish-work` → 再合。新 task 不得长期停在 `in_progress`。
3. **模型汇报**：以 `omp` 实际输出 / session / stats 可核验清单为准；未知标未知，不用配置默认值补齐。
4. **本文件**：进度变更后实时同步（见文首维护规则）。

---

## 8. 下一步队列

| 顺序 | 项 | 状态 |
|---|---|---|
| 1 | **T6** `sbtd_clarify` | ✅ #39 → `4e76ae8` |
| 2 | **FU3** multi-fact 匹配集合 + persist-across-replans / mergeGate demote | ✅ #43 → `2a82e63` |
| 3 | **T7** Trellis 后端 | ✅ #45 → `b73ece9` |
| 4 | **T8** `sbtd_spec` / tickets | ✅ #47 → `a90a96f` |
| 5 | **T9** GitNexus 后端 | ✅ #49 → `314c345` |
| 6 | **T10** `sbtd_validate` | ✅ #51 → `014f480` |
| 7 | **T11** `sbtd_bdd` | ✅ #53 → `d729d6e` |
| 8 | **T12** Maestro 预检 | ✅ #55 → `61026a1` |
| 9 | **T13** `sbtd_e2e` | ✅ #57 → `9289798` |
| 10 | **T14** `sbtd_lessons` | ✅ #59 → `2b7cf61` |
| 11 | **T15** `/sbtd` 命令与 README | ✅ #62 → `0dbe135` |
---

## 9. 变更日志（本文件）

| 日期 | 说明 |
|---|---|
| 2026-09-12 | FU4 #65 ready：r3 CLEAN @ `ca9eb8f`；Q1B Q2B Q3C Q4A PASS；Q5A pending T16；REQUIRED_CHANGES=none；R1/R2 CLOSED；finish-work ✅；archive grill+DDD+FOLLOWUPS；**未合**（merge SHA pending） |
| 2026-09-11 | T15 #62 → main `0dbe135`（TODO merge-SHA backfill） |
| 2026-09-11 | T15 #62 scheme A finish/merge：CLEAN r5 @ `3529daf`；product r3b @ `f8561bf`；locks Q1A–Q6A；REQUIRED_CHANGES=none；R1–R4 CLOSED；squash `0dbe135`；不发布包；下一队列 T16（未开） |
| 2026-09-11 | T15 #62 ready：r5 CLEAN @ `3529daf`（T15QualityR5+T15SecurityR5）；product r3b @ `f8561bf`；process r4b @ `70d3a60`；finish-work ✅；archive implement+DDD+FOLLOWUPS；**未合**（merge SHA pending） |
| 2026-09-11 | T15 #62 finish-work @ `663e0e5`：product r3b CLEAN @ `f8561bf`（T15QualityR3b）；process r4b CLEAN @ `70d3a60`（T15QualityR4b）；void invalid r3/r4 manual claims；archive implement+DDD；**未合** |
| 2026-09-11 | T15 开 PR #62 `feat/t15-sbtd-command`：`/sbtd` 人类命令 + package README；locks Q1A–Q6A；r1 block @ `a83ffd07`；R1–R4 fix pass in flight；未合 / 未 npm / 未 claim CLEAN |
| 2026-09-11 | T14 #59 → main `2b7cf61`（TODO merge-SHA backfill） |
| 2026-09-11 | T14 #59 scheme A finish/merge：product CLEAN r3 @ `e4bf2b1`；process clear tip `ffb081d`；locks Q1A–Q6A；REQUIRED_CHANGES=none；r1–r3 REQUIRED closed；process gaps cleared；不发布包；下一队列 T15（未开） |
| 2026-09-11 | T14 #59 **流程违规记录**：pre-gate ac5aed6+b26d0b9；Trellis manual `rm -rf` + `TRELLIS_CONTEXT_ID` bypass + 误报 workflow complete；GitNexus pre-commit 缺失；task meta `process_violations_open`；**勿合并** |
| 2026-09-11 | T14 #59 Trellis gate（技术验证 only）：check 299/299 + spec update @ 34471fd/6fadd16 — **非 workflow-valid** |
| 2026-09-10 | T13 #57 → main `9289798`（TODO merge-SHA backfill） |
| 2026-09-10 | T13 #57 scheme A finish/merge：CLEAN r5；tip `194a662`；locks Q1B–Q6A；REQUIRED_CHANGES=none；r1–r4 REQUIRED closed；Main+Pr57R5Reviewer+advisor CONTENT CLEAN；squash `9289798`；不发布包；不改写 maestro.ts；下一队列 T14（未开） |
| 2026-09-10 | T12 #55 → main `61026a1`（TODO merge-SHA backfill） |
| 2026-09-10 | T12 #55 scheme A finish/merge：CLEAN r3；tip `a42ca4c`；locks Q1A–Q6A；REQUIRED_CHANGES=none；r1 R1/R2 + r2 R2/R3/R4 closed；tests 17/17 t12-maestro；Main+Pr55R3Reviewer+advisor CONTENT CLEAN；squash `61026a1`；不发布包；下一队列 T13（未开） |
| 2026-09-10 | T11 #53 → main `d729d6e`（TODO merge-SHA backfill） |
| 2026-09-10 | T11 #53 scheme A finish/merge：CLEAN r5；tip `975d878`；locks Q1C–Q6A；REQUIRED_CHANGES=none；r1–r5 REQUIRED closed；tests 228；Main+Pr53R5Reviewer CLEAN；Advisor no content verdict；squash `d729d6e`；不发布包；下一队列 T12（未开） |
| 2026-09-10 | T10 #51 → main `014f480`（TODO merge-SHA backfill） |
| 2026-09-10 | T10 #51 scheme A finish/merge：CLEAN r4；tip `7a660af`；locks Q1A–Q5A；REQUIRED_CHANGES=none；r1–r3 REQUIRED closed；tests 201；不发布包；下一队列 T11（未开） |
| 2026-09-09 | T10 #51 r2 fix：apply/PluginHost 注入 cwd+GitNexus MCP；AGENTS 非 Node 测试命令；P2 timeout/signal/bun run test/SIGTERM wait；未合 / 未 finish-work / 未 npm |
| 2026-09-09 | T10 scheme A coding：`sbtd_validate` + apply 注册 + tests；locks Q1A–Q5A；消费 T9 gitnexus as-is；未合 / 未 finish-work / 未 npm |
| 2026-09-09 | T9 #49 → main `314c345`（TODO merge-SHA backfill） |
| 2026-09-09 | T9 #49 scheme A finish/merge：CLEAN r2；tip `df7abb2`；locks Q1B–Q6A；REQUIRED_CHANGES=none；r1 REQUIRED closed（`--index-only` + skip-before-analyze）；residuals detect() outer catch / injected runRefresh timeout / SIGTERM-only / T10 cwd-mcp-runRefresh；不发布包；下一队列 T10（未开） |
| 2026-09-09 | T8 #47 → main `a90a96f`（TODO merge-SHA backfill） |
| 2026-09-09 | T8 #47 scheme A finish/merge：CLEAN r3；tip `3fd773f` + archive `a0f669a`；tests 150/150；locks Q1C–Q6A；REQUIRED_CHANGES=none；residual T5 scenario title nit + T7 symlink-at-tasks-dir；不发布包；下一队列 P2 T9（未开） |
| 2026-09-09 | T7 #45 → main `b73ece9`（TODO merge-SHA backfill） |
| 2026-09-09 | T7 #45 scheme A finish/merge：CLEAN r3；tip `e9bc7cb` + archive `625dc8c`；tests 136；locks Q1C–Q6B；REQUIRED_CHANGES=none；residual symlink-at-tasks-dir；不发布包；下一队列 T8（未开） |
| 2026-09-08 | FU3 #43 → main `2a82e63`（TODO merge-SHA backfill） |
| 2026-09-08 | FU3 #43 scheme A finish/merge：CLEAN r5；tip `bdc25f3` / prod `d2194f5`；tests 121/121；locks Q1D Q2B Q3A Q4B Q5A；vote A；`REQUIRED_CHANGES=none`；不发布包；下一队列 T7 然后 T8（未开） |
| 2026-09-08 | FU3 #43 post-r2：Q4B re-lock（2 feature + docs/review/fix，不改写历史）；Q1D 文档收窄为 DDD-only alias；tip `b33641f` 验证 116/116 |
| 2026-09-08 | FU3 开 PR #43：main 同步 `86bcdce`（#42）；Q4B 先 persist-across-replans sticky required，后 multi-fact matching-set；hooks 冻结；不改 omp/不发布/不改宿主钉 |
| 2026-09-07 | T6 scheme A finish on #39 → `4e76ae8`；FU3 增 persist-across-replans / mergeGate demote 债；不改 `plan.ts` |
| 2026-09-07 | FU2 合入 #37 → `f039a99`；Trellis archive + TODO 回填 merge SHA |
| 2026-09-07 | FU2 开 PR #37：Review Recording Order 仅 `sbtd_review`；main 同步为 `226d4e3` |
| 2026-09-05 | 初版：自群进度表落地；含 P0–P3、FU1–FU3、发布与约定；FU2 进行中 |
