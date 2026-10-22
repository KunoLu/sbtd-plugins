---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd-d4-release-docs
workflow_mode: strict
mode_source: user
mode_note: 用户明确要求 strict，遵循 docs/prd/omp-sbtd-0.2.0-rc.1.md L59「每个任务都用 strict 模式；每个任务开工前新建对应 strict 任务记录。」；本次仅 PRD D4 修订与行 E/F 发布文档范围。
status: "done"
branch: docs/omp-sbtd-0.2.0-rc.1-prd-d4-release-docs
created_at: '2026-10-22T18:35:40+08:00'
updated_at: '2026-10-22T18:38:55+08:00'
completed_at: '2026-10-22T18:38:55+08:00'
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
| 2026-10-22T18:37:59+08:00 | in-progress | checking | 两个指定提交已完成，进入文档一致性与最终记录核验 | 928f596 创建记录并回填 #112；4209d2d 仅修改 PRD；两次提交前 git diff --check 均 exit 0 |
| 2026-10-22T18:38:55+08:00 | checking | done | PRD-only 验收成立，记录本地完成及提交前模型快照 | PRD 仅六行替换与 R10 追加；索引仅一行且排序正确；latest 全文核对无本版旧通道要求；git diff --check origin/main..HEAD 与 git diff --check 均 exit 0；本次 done 不代表合并或发布 |

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
- [x] PRD D4、行 E/F、§0/§4/§5 与 R10。
- [x] 文档精确范围、索引排序、latest 全文核对与模型快照完成；本任务转 done。
- 第三个提交仅保存本完成记录；提交后最终范围、干净工作区与三个提交核验结果在交付回复报告，不预填尚未执行的结果。

## 验证证据

入口：`git status --short` 无输出；`git branch --show-current` 与 frontmatter 一致；`git rev-parse --show-toplevel` 为授权 worktree；`git rev-parse origin/main` 与 #112 完整 merge SHA 一致。`git log -1 --format='%H %cI' 194dfa6` 输出上述 SHA 与 `2026-10-22T18:08:58+08:00`。创建时间来自 `TZ=Asia/Shanghai date -Is`。

### 提交前文档核验

Evidence Source：developer-local；PRD 已提交为 `4209d2d`，本记录的完成更新为提交前 working-tree 内容（Source Revision：dirty；Evidence Publication：local-only），不是 CI、Reviewy CLEAN 或发布证明。

| 命令 / 检查 | 实际结果 |
|---|---|
| `git diff --check origin/main..HEAD` | 2026-10-22T18:38:55+08:00，exit 0、无输出；当时 HEAD 为第二个提交 4209d2d |
| `git diff --check` | 同时 exit 0、无输出 |
| `git diff --name-only origin/main..HEAD` | 恰为 PRD、本记录、ai/tasks/index.md 三个授权文件 |
| `git status --short` | 当时仅本 task.md 为 modified，用于 checking/done 及证据更新；无其他修改 |
| `git log --oneline origin/main..HEAD` | 当时为 928f596（#112 回填）与 4209d2d（PRD）两个提交；第三个提交为本完成记录 |
| `grep -n latest docs/prd/omp-sbtd-0.2.0-rc.1.md` 等价检索（专用 grep 工具，保留行号） | L14/20/35/42/44/70/71/72/73/84/86/91/111/113；本版发布通道已统一为 next + latest；「latest 不动」仅留在独立 D13（L44）与 R10 的历史说明（L113）；宿主 latest 18.12.2 原文保留 |
| 范围 grep：`91efc23` / `ddcba13`，路径 docs/prd、ai/tasks（修改前） | 仅后继 d11-d9-sync/task.md 有先例，无 PRD 回填位置；据此不回填行 R |
| 内存逐行/逐字节比较 origin/main 与当前文档，不落地脚本 | PASS：PRD 仅 L14/35/72/73/86/91 六行替换，末尾追加 R10；其余字节不变，所有任务行优先级/状态/PR/SHA/done/记录路径列不变；D11/D13、标题与历史修订不变 |
| 索引精确比较 | PASS：仅新增本任务一行，所有 task ID 按 ASCII 排序；其他行不变 |

人工对照用户清单：D4 保留原锁定及新裁决时间，写明无版本安装影响；行 E 覆盖两份版本文件、build/SBOM/实际 tarball、双语 CHANGELOG 与四份 README、17.x 钉版说明、旧任务修正、合并后 tag 与发布顺序及 fail-stop；行 F/§4 对齐 dist-tags、主页、两向链接、回填与文档纠偏；§5 移除本版不 bump latest 的旧非目标。E/F 均仍 planned。

### 跳过与恢复边界

- 已读取 sbtd-task 的 strict/state 与 project-validation；rtk：not-needed，按要求使用 native Git 和专用 grep 的只读文档检查。
- build、pack、单元/集成测试、typecheck、运行时 smoke、npm view、浏览器链接点击：skipped；用户明确限定纯文档，不执行构建/打包/测试或行 E/F 发布操作。未运行 lint/formatter，无代码变化且不重排 Markdown。
- BDD：skipped，无运行行为或 .feature 修改；无 BDD runner 执行。Web/Mobile、Graft、独立生产代码评审/可读性复核：not-required / skipped，无代码、安装、全局配置、跨服务契约或多子系统实现变更；未声称独立 Reviewy 已评审本次提交。
- Cross-repo context / API Contract：not-needed；Mock Strategy：none；Environment Alignment：not-needed。正式测试报告/中文伴本、Targeted Rerun、Final Full Rerun：not-needed，仅文档检查，原生输出在会话中，本节记录中文证据；未新增报告或脚本。
- 本次仅文档完成；README/CHANGELOG/SBOM/版本及旧任务修正明确归行 E，实际 npm 页面与 tags、发布链接尚未核验。未 push、开 PR、tag、publish 或改其他 checkout。三个本地提交可按明确授权后单独 revert；本次未执行回滚，不承诺自动恢复或全库 TaskStore 校验。

## CONTRACT-CHANGE-NEEDED

D4 原锁定的「latest 不动」由用户 2026-10-22 18:07 +08:00 明确修订；本 PRD-only 提交记录授权与影响，不自行实现发布。17.x 用户须钉旧版本，README/CHANGELOG/SBOM/版本修改归行 E；D11 支持范围与硬门不变。

## 使用的模型

> **提交前快照**：`TZ=Asia/Shanghai date -Is` = `2026-10-22T18:38:55+08:00`。只统计本主会话截至该次读取的 jsonl，包含进行中的 eval 调用；其后的编辑、检查、提交和最终回复不计入，不冒充全会话最终计数。

| agent/session | provider/model | thinkingLevel | assistant messages / tool calls | purpose | resolvedModelIsFallback | title-generation count | job-widget entries |
|---|---|---|---|---|---|---|---|
| 主会话 `01a1632d-a586-76a4-a030-abc92cf300f5` | openai-codex / gpt-6-astra | high | 12 / 27（提交前快照） | #112 回填、PRD R10、唯一 writer/验证 controller、三次本地提交及记录 | false | 0（title_change） | 0（type=model_usage purpose=job-widget） |
| 自动标题模型（无生成事件） | 未记录 / unknown | 未记录 / unknown | 未记录 / unknown | title-generation | 未记录 / unknown | 0（同一快照，不另加总） | 不适用 |

来源：`~/.omp/agent/sessions/--workspace-sbtd-plugins-prd-d4--/2026-10-22T10-34-58-310Z_01a1632d-a586-76a4-a030-abc92cf300f5.jsonl`；session header 的 cwd 与授权 worktree 一致。provider/model 来自 model_change 与 assistant message，thinkingLevel 来自 thinking_level_change，resolvedModelIsFallback 来自 model_change；未推断 unknown 字段。

统计定义：assistant messages 为 `type=message` 且 `message.role=assistant`；tool calls 为其 content 中的 `type=toolCall`，不重复计 eval 内操作或 custom tool_execution_start。工具分布：read 9、bash 5、todo 3、grep 2、glob 1、eval 3、write 1、edit 3，共 27。`title` 头部不算 title-generation；本快照无 title_change、无 job-widget model_usage；无 subagent。

orchestrator 在本轮前另执行 astra connectivity ping，日志 `~/.omp/logs/sbtd-prd-d4/ping.log` 含 `ASTRA_OK`（本轮只读确认）。独立 ping session `2026-10-22T10-34-06-283Z_01a1632c-da4b-77ba-8ae9-8e7fc191de31.jsonl` 为 1 assistant / 0 tools，回复 ASTRA_OK；用途仅 connectivity ping，不计入上表主会话统计，未再次执行 ping。
