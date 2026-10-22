---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd-d4-release-docs
workflow_mode: strict
mode_source: user
mode_note: 用户明确要求 strict，遵循 docs/prd/omp-sbtd-0.2.0-rc.1.md L59「每个任务都用 strict 模式；每个任务开工前新建对应 strict 任务记录。」；本次仅 PRD D4 修订与行 E/F 发布文档范围。
status: in-progress
branch: docs/omp-sbtd-0.2.0-rc.1-prd-d4-release-docs
created_at: '2026-10-22T18:35:40+08:00'
updated_at: '2026-10-22T18:35:40+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 PRD R10：D4 与行 E/F 发布文档范围

## 目标

遵循 D11/D9 同步 PR #112（194dfa6），按用户 2026-10-22 18:07 Asia/Shanghai（+08:00）修订 D4：先发布 next，再将 latest 指向 0.2.0-rc.1；扩充行 E/F 的版本、SBOM、双语发布文档、发布顺序及发布后核验范围，同步 §0/§4/§5 并追加 R10。

回填：PR #112（分支 `docs/omp-sbtd-0.2.0-rc.1-d11-d9-sync`，D11/D9 step 2）已 squash-merge 至 main；完整 merge SHA `194dfa653f5e4f3d1bb34f2721af58c8200dba4f`；done 时间 `%cI` = `2026-10-22T18:08:58+08:00`（本地 git log 核验）；GitHub mergedAt = `2026-10-22T18:08:58+08:00`（原值 `2026-10-22T10:08:58Z`，orchestrator 提供）。本地及远程分支、worktree 已删除（orchestrator 提供，未独立远程查询）。

## 非目标

仅修改本记录、PRD 与索引新增一行；不改包版本、README、CHANGELOG、SBOM、代码或其他任务记录。尤其不改 `ai/tasks/omp-sbtd-0-2-0-rc-1-d11-d9-sync/task.md` 的两处旧未提交措辞及 fix-run 计数，留给行 E。不回填行 R，不改任务表状态/PR/merge SHA/done 时间列，不改 D11 或独立 dsh-sbtd 的 D13。不运行 build、pack、测试；不 push、开 PR、tag 或 publish。不触碰 `.omp-r12b-addendum.txt`、`ai/tasks/codex-verify/`、active pointer、ignore 或全局配置。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T18:35:40+08:00 | planned | in-progress | 创建用户授权的 strict PRD-only 后继记录并开始 #112 回填 | 根与分支匹配；初始 git status --short 无输出；origin/main 为 194dfa653f5e4f3d1bb34f2721af58c8200dba4f；merge %cI 已核验 |

## 决策

- 未完整调用 grill-with-docs：用户已给出精确决定、位置、顺序与不变量，无需重复澄清；本次不重开历史 DDD draft。
- 已搜索 `docs/prd` 与 `ai/tasks` 的 `91efc23` / `ddcba13`：#110/#111 回填只见于后继 `omp-sbtd-0-2-0-rc-1-d11-d9-sync/task.md` 的目标，PRD 无对应回填位置；遵循该先例，commit 1 仅创建本记录并加索引，不动 PRD 或行 R。
- 索引按 task ID ASCII 排序，新增行位于 prd-d11-dated 与 prd-r7-p0-v4 之间。
- 三个提交分工：#112 回填与开工记录；PRD R10；验收及 done 记录。仅显式 `git add <paths>`。
- 唯一 writer 与验证 controller 为本主会话，无 subagent。沿用指定任务先例的 edit/write 共享记录方式，不调用全库 TaskStore、不写 active pointer，不声称全库 lifecycle 或自动恢复已验证；本记录保留 checking 中间态。
- 已核对目标及父路径无 symlink、无路径逃逸，新任务目录不存在，索引已 tracked；`reports/probe.txt` 命中 `.gitignore:125 /ai/tasks/**/reports`，本次不创建报告文件。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；明确发布通道裁决，无领域模型歧义 | before-dev | not-required |
| book-ddia-data-design | 无数据/schema/迁移/缓存/跨服务数据设计；仅发布计划文档 | before-dev | not-required |
| book-legacy-change-safety | 无产品行为修改或 bug 修复 | before-dev | not-required |
| book-refactoring-pass | 无生产代码修改 | before-dev | not-required |
| book-release-readiness | 仅修订未来行 E/F 的发布要求，本次不执行发布或改变 runtime/部署 | finish | not-required；实际发布由行 E 执行适用门禁 |

## 进度

- [x] 核对根、分支、基线、路径、#110/#111 先例与 #112 merge 时间。
- [x] 创建 strict 记录并回填 #112。
- [ ] PRD D4、行 E/F、§0/§4/§5 与 R10。
- [ ] 文档范围、一致性、模型快照及最终三个提交核验。

## 验证证据

入口：`git status --short` 无输出；`git branch --show-current` 与 frontmatter 一致；`git rev-parse --show-toplevel` 为授权 worktree；`git rev-parse origin/main` 与 #112 完整 merge SHA 一致。`git log -1 --format='%H %cI' 194dfa6` 输出上述 SHA 与 `2026-10-22T18:08:58+08:00`。创建时间来自 `TZ=Asia/Shanghai date -Is`。

## CONTRACT-CHANGE-NEEDED

D4 原锁定的「latest 不动」由用户 2026-10-22 18:07 +08:00 明确修订；本 PRD-only 提交记录授权与影响，不自行实现发布。17.x 用户须钉旧版本，README/CHANGELOG/SBOM/版本修改归行 E；D11 支持范围与硬门不变。

## 使用的模型

提交完成记录前从本会话 jsonl 计算快照；未记录的字段保持 unknown，不借用 orchestrator 的 ASTRA_OK ping 计数。
