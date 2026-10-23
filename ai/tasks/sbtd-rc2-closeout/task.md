---
schema_version: 1
id: sbtd-rc2-closeout
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict 收尾；四个逻辑提交；主会话唯一 writer；仅授权本地提交，不授权远端写入或发布。
status: in-progress
branch: chore/omp-sbtd-rc2-closeout
created_at: '2026-10-23T21:12:56+08:00'
updated_at: '2026-10-23T21:12:56+08:00'
completed_at: null
---
# SBTD rc.2 closeout

## 请求、范围与授权

- 用户 2026-10-23 21:06 +08:00 群内要求收尾提 PR，Lord 记录。
- 用户 2026-10-23 21:07 +08:00 群内要求仓内所有 README 和 CHANGELOG 更新到最新并集成到本 PR，Lord 记录。
- 用户 2026-10-23 21:08 +08:00 群内确认（PRD 任务状态同步并入收尾 PR），Lord 记录。
- 用户 2026-10-23 21:09 +08:00 群内要求 SBTD tasks 状态更新为最新（应均为 done），Lord 记录。
- 用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录。
- 编排方整理：本次执行边界为四个本地逻辑提交；禁止 push、开 PR、评论、tag、publish、release、merge、版本 bump、全局配置／全局 omp 修改。交付归属为由 chore/omp-sbtd-rc2-closeout 分支的 PR 交付，不预填 PR 编号。
- 基线 `origin/main` / `2393d10c3fb1a1f3cb756a351297a430fd2afc81`；入口工作树干净、实际分支匹配。旧任务获明确历史回填授权，保留历史 branch，不重绑定。
- 历史 task 事件、日期记录、per-run 验证、PRD 日期修订、既有 CHANGELOG 文本均追加式保留；只改允许的当前状态字段。不改 decisions、D/R 编号、contract、schema、peer、versions、lockfile。
- 未完整调用 grill-with-docs：需求、归因、提交边界与验收已明确，无新领域歧义。
- 路径安全与 ignore 已核对：ai/tasks 正常且可跟踪；`.sbtd` 和本任务 reports 受保护、未跟踪。沿用既有 TaskStore 全库历史 schema blocker，不重跑已知失败；本记录为明确要求的共享 Markdown 交付，不声称 helper lifecycle 或自动恢复通过，不写 active/developer/handoff/ignore。
- 主会话唯一 writer／验证 controller；DocsAudit、StatusAudit 只读调查，后续独立 review 只读。Graft=skipped：没有已验证受管连接，使用源码、Git、GitHub、npm 证据。rtk=skipped-for-report：原生命令保留报告。

## 四提交计划

1. #124 merge、FINAL 模型表、rc.2 release 回填；现有真实 pack 测试增加 `README.zh.md` 存在且 `README_zh.md` 不存在的断言；本任务及 index。编排方整理：OMP 自提 nit。
2. 根 README Roadmap／路线图更新；rc.2-prep checking → done，completed_at 采用 #124 GitHub mergedAt `2026-10-23T20:39:30+08:00`（与 `%cI` 的 20:39:29 分开记录）。`docs/prd/ROADMAP.md` 的 D12 archive 保持独立 chore，不移动。
3. 全仓自有 README／CHANGELOG 事实对齐；包内文档变化通过既有 build 生成 SBOM，再验证实际 tarball。保留根 `README_zh.md` 文件名。
4. PRD 仅当前状态字段同步；全任务状态扫尾；六处历史 blocked／ready 用追加状态补记，不改旧结论。扫尾不另建第五提交。

本任务最终保留 checking / completed_at null，直到本分支 PR 合并。用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、新业务规则或领域歧义 | before-dev | not-required |
| book-ddia-data-design | 仅既有文档／历史记录；无 schema、持久化机制或数据流设计变化 | before-dev | not-required |
| book-legacy-change-safety | 无运行时行为修复；断言使用既有真实 tarball 场景 | before-dev | not-required |
| book-refactoring-pass | 不修改生产代码，仅测试断言、文档与生成 SBOM | before-dev | not-required |
| book-release-readiness | 已发布状态记录与包内容一致性核对；不部署、不更改运行时 | finish | planned（包文档变化后核对发布物边界） |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T21:12:56+08:00 | planned | in-progress | 编排方整理：建立 strict 收尾记录 | 实际分支／基线／路径／ignore 与 npm、GitHub 初次核验通过 |

## 事实核验（2026-10-23T21:12:56+08:00）

- `gh pr view 124 --json number,mergedAt,mergeCommit,url`：#124 squash `2393d10c3fb1a1f3cb756a351297a430fd2afc81`；GitHub mergedAt `2026-10-23T20:39:30+08:00`。`git log -1 --format='%H %cI' 2393d10`：`2026-10-23T20:39:29+08:00`。
- `npm view @kunolu/omp-sbtd dist-tags time dist --json`：latest=next=`0.2.0-rc.2`；npm time `2026-10-23T12:44:10.098Z`（20:44:10 +08:00）；dist.shasum `543fa7c3decdb0f6ca8faef98e90bd6eff3ad362`，dist.fileCount 472。
- `npm view @kunolu/dsh-sbtd dist-tags time --json`：latest=next=`0.2.0-rc.2`；npm time `2026-10-23T09:08:50.745Z`（17:08:50 +08:00）。完整版本清单与双语 CHANGELOG 覆盖核对随文档审计记录。
- `gh release list --limit 20`：omp/dsh 的 rc.1、rc.2 共四项，全部 prerelease；omp rc.2 publishedAt 20:41:17、dsh rc.2 17:55:13（均 2026-10-23 +08:00）。`gh api repos/KunoLu/sbtd-plugins/releases/latest` 返回预期 HTTP 404（命令 exit 1），无 latest release，不是 npm latest 不存在。
- `git for-each-ref`：omp rc.2 annotated tag object `d22a877b449cfde587f2f0041ab27256176df765` → `2393d10`，tagger `2026-10-23T20:40:57+08:00`。GitHub created_at 同时刻；published_at 晚 20 秒。
- 两个 tag-bound omp README 链接用 `curl -L` 均 HTTP 200。
- `gh run view 39954216679 --json headSha,conclusion,jobs`：head `7432be486b42c3b7326ed1b0574d0bab38b30739`，conclusion success，1/1 job success。这是 #124 历史 CI，不冒充本轮执行。
- `gh pr view 120/122/123/93` 分别核验：#120 `67465db93e7c6f1e6f5f43704c1d4c22ae74306d` 2026-10-23 17:56:19；#122 `684387835b27d46b3b96b01f2015e42fe7937b12` 18:58:43；#123 `008cea74dfbab5ce2c688c2c42e4bd8cfeddfe5f` 20:01:45；#93 `3fafd73f828b0f61c3310e4828cfb63bbced3f9a` 2026-10-18 09:11:01（均 +08:00）。
- 上述可在线重核的事实与编排方整理一致；模型调用、Reviewy CLEAN、发布操作者与发布前 clean worktree 操作属于编排方整理的历史记录，不冒充本轮重新执行。

## 验证计划

执行 frozen install；omp typecheck/lint/build/test/smoke、pack、packed check；dsh typecheck/build/test、双包 npm pack dry-run；新增行归因、冲突、YAML、历史保留、版本／lockfile／tag 不变检查。所有报告保留原始输出与同 stem 中文汇总；最终 HEAD 用输入哈希绑定证据，不将 dirty 本地验证称为 CI 或真实宿主 full-stack。
