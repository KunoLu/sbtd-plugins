---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-e-release
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择 strict，按 PRD L59 与行 E；唯一 writer，仅显式路径提交，不 push/PR/tag/release/publish/dist-tag。
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-e-release
created_at: '2026-10-22T19:06:33+08:00'
updated_at: '2026-10-22T19:06:33+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 E：pre-tag release PR

## 目标 / 范围 / 非目标

- 首 commit 回填行 R、#110–#113 历史记录与行 D superseded 注释，PRD 仅改 R/E 两行，新增本 strict 记录与排序索引。
- package.json/plugin.json 升为 0.2.0-rc.1，五个钉版测试断言同步；双语 CHANGELOG 日期为 2026-10-22，四份 README 改为 next/latest 已发布措辞并说明 17.x 须钉旧 0.1.x。
- 文档/版本完成后一次正常 build 重生成 SBOM，实际 pack/check-package、typecheck、包 lint、focused/full tests，提交证据。
- 不改 dsh 内容、历史 fixture/CHANGELOG、D7 链接、D11 原句、lockfile、files/p0 清单或生产逻辑。不 push、开 PR、tag、GitHub release、npm publish/dist-tag，不暂存 .omp-r12b-addendum.txt 或 ai/tasks/codex-verify/。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T19:06:33+08:00 | planned | in-progress | 用户授权 strict 行 E 与前序回填 | 分支匹配、起点 clean；基线 007fb6c506e609050fedd1ed86db8696d8164e03；PRD L59–L62 |

## 决策

- 未完整调用 grill-with-docs：用户与 PRD 已明确锁定需求，无新领域歧义。
- #110 frontmatter branch 经 orchestrator 的 gh headRefName 核验正确，保留；#111 为单独 review-fix 分支，不重写历史归属。
- 根及包 README 按 D4/R10 写 expected released state，不当作本轮已发布事实；行 F 按最终 npm view 证据纠偏。
- 沿用指定先例的共享文档 edit/write；已知全库 TaskStore 历史 schema blocker 不重跑，不写 active pointer，不声称 TaskStore lifecycle/自动恢复可靠。新任务与父路径安全，reports 命中 .gitignore:125 /ai/tasks/**/reports。
- 主会话唯一 writer/验证 controller；独立 reviewer 只读，不运行 build/lint/tests/formatters。

## Side PR 合并回填

以下均由 orchestrator 提供；它们不是 PRD 任务行。五个远程分支（含 #109）均已删除；#113 本地分支及 worktree 已正常删除，无 force。

| PR | head branch | merge SHA | merge commit %cI | GitHub mergedAt |
|---|---|---|---|---|
| #110 | docs/omp-sbtd-0.2.0-rc.1-d11-d9-wording | 91efc235f273c7d8370f92210dd723d2ff8154ce | 2026-10-22T17:19:16+08:00 | 2026-10-22T17:19:17+08:00 |
| #111 | docs/omp-sbtd-0.2.0-rc.1-d11-d9-wording-fix | ddcba1322f1f2ef43981870cc2bab96f2887f705 | 2026-10-22T17:32:14+08:00 | 2026-10-22T17:32:15+08:00 |
| #112 | docs/omp-sbtd-0.2.0-rc.1-d11-d9-sync | 194dfa653f5e4f3d1bb34f2721af58c8200dba4f | 2026-10-22T18:08:58+08:00 | 2026-10-22T18:08:58+08:00 |
| #113 | docs/omp-sbtd-0.2.0-rc.1-prd-d4-release-docs | 007fb6c506e609050fedd1ed86db8696d8164e03 | 2026-10-22T18:59:19+08:00 | 2026-10-22T18:59:20+08:00 |

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；发布决策已锁定，无模型歧义 | before-dev | not-required |
| book-ddia-data-design | 无 schema/迁移/缓存/数据所有权设计；SBOM 仅按既有生成器派生 | before-dev | not-required |
| book-legacy-change-safety | 无生产逻辑或既有 bug 修复；实际 tarball 检查保护发布一致性 | before-dev | not-required |
| book-refactoring-pass | 无生产代码修改；仅 manifest 与测试版本常量 | before-dev | not-required |
| book-release-readiness | 发布元数据、安装通道文档与 SBOM | after-validation | planned |

## 验证计划

按用户要求在 packages/omp-sbtd 依次 build、pack、解包及 check-package，再 typecheck、lint、五文件 focused suite、完整 pnpm test；所有 pnpm 使用 COREPACK_HOME=$HOME/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1。保留 raw 与同 stem 中文汇总；实际结果后填，不把计划当通过。仅允许已知 Bun offline 缓存导致的 exact local OMP 18.11.1 smoke-only 失败。

## 合并后步骤（尚未执行）/ post-merge steps (not yet done)

1. Reviewy CLEAN + CI green → Lord squash-merges。
2. 在 main merge commit（不在分支）创建 annotated tag `omp-sbtd-v0.2.0-rc.1`。
3. 打 tag 后 Reviewy 点击核验两个 D7 语言切换链接：`blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README.md` 与 `README_zh.md`；两者均通过后才创建双语 EN/ZH GitHub prerelease。
4. 从 tagged tree 执行 `npm publish --tag next`，npm OTP 届时由用户提供。
5. `npm dist-tag add @kunolu/omp-sbtd@0.2.0-rc.1 latest`，OTP 由用户提供。
6. 行 F：`npm view @kunolu/omp-sbtd dist-tags` 核验 latest = next = 0.2.0-rc.1，npmjs.com 包页显示新 README、链接有效；回填行 E。任一步失败即停止并报告，不强行发布。

发布前只读 registry 快照（orchestrator，2026-10-22T19:04+08:00）：`npm whoami` 成功，已登录（不记录用户名）；`npm view @kunolu/omp-sbtd dist-tags` 为 `{"latest":"0.1.0-rc.2","next":"0.1.0-rc.14"}`。本轮未执行登录或 registry 写入；快照仅在任务记录，不进入 README。
