---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-d11-d9-sync
workflow_mode: strict
mode_source: user
mode_note: 用户明确要求 strict（docs/prd/omp-sbtd-0.2.0-rc.1.md L59：「每个任务都用 strict 模式；每个任务开工前新建对应 strict 任务记录。」）；run 1 误记 default，本次按 Reviewy blocker batch 修正，不追溯声称 run 1 已执行 strict 门禁。
status: "done"
branch: docs/omp-sbtd-0.2.0-rc.1-d11-d9-sync
created_at: '2026-10-22T17:34:47+08:00'
updated_at: '2026-10-22T17:53:26+08:00'
completed_at: '2026-10-22T17:53:26+08:00'
---
# omp-sbtd 0.2.0-rc.1 step 2：D11 日期措辞与 D9 模板树注释同步

## 目标

遵循 PRD #110（91efc23）与 #111（ddcba13），将 D11 日期措辞逐字同步到六份 README/CHANGELOG，将 D9 模板树计数注释逐字同步到四份包内文档；仅一次正常 build 重新生成 SBOM，验证实际 tarball。

## 非目标

不修改 docs/prd/**、代码、模板、版本、lockfile、全局配置或其他 checkout。不 add/commit/push/开 PR/tag/publish；不触碰 .omp-r12b-addendum.txt、ai/tasks/codex-verify/ 或 active pointer。不运行全量测试、lint-fix 或无关 formatter。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T17:34:47+08:00 | planned | in-progress | 创建用户指定的 step-2 共享记录；执行模式 default | 根与分支匹配；初始 git status --short 无输出；HEAD 与 origin/main 均为 ddcba1322f1f2ef43981870cc2bab96f2887f705 |
| 2026-10-22T17:53:26+08:00 | in-progress | done | 按 Reviewy blocker batch 完成本轮 task.md-only 修正：strict/user、done 与完成时间、run 1 最终计数、本轮模型快照及 ping 记录；保留原始事件 | PR #112 tip `10734e3a2b58e10c4a15855b0eda9c4fa4254904`（由 orchestrator 提交）；用户转达 Reviewy review「artifacts OK, task.md blocker batch」；本轮 strict/done 修正为该 tip 上的未提交 task.md 变更，不代表 merge 或发布 |

## 决策

- 精确措辞与范围已锁定，未完整调用 grill-with-docs，无领域歧义；run 1 曾误记 default 并称不继承其他任务的 strict 模式，本轮按 Reviewy 更正：本任务自身受 `docs/prd/omp-sbtd-0.2.0-rc.1.md` L59 的 strict 规则约束，不是继承其他任务模式；原始事件保留，不补造历史门禁证据。
- 保留原 Markdown 引用/列表前缀和缩进；根 README 不新增 D9；不查询当前 upstream latest 来替换历史快照。
- ASCII 排序中 d11-d9-sync 位于 pr-a-migrate-kit 之前，而不是 pr-r-readme 之后。
- 唯一 writer / validation controller 为主会话；无 subagent。按用户要求使用 edit/write 保存共享记录，不调用全库 TaskStore，不修改 active pointer，不声称全库 lifecycle 或自动恢复已验证。
- 路径与父目录已核对无 symlink；新任务目录初始不存在、无 tracked 内容；reports/probe.txt 命中 .gitignore:125 /ai/tasks/**/reports。
- 本轮仅直接编辑用户指定的 task.md；`mode_source: user` 符合 `packages/omp-sbtd/kit/onboard/runtime/templates/skills/sbtd-task/references/task-data.schema.json` L28 及既有 omp-sbtd 任务惯例。按用户要求和两个 done-task 先例追加 `in-progress → done`；该直接跃迁不符合当前 stateEvent schema 的 checking 中间态要求，未调用 TaskStore，不声称 lifecycle 校验通过。

## Book Gate Plan（本轮记录修正）

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill，无领域规则或模型歧义 | before-dev | not-required |
| book-ddia-data-design | 仅更正既有任务记录，无数据/schema/恢复机制设计或实现 | before-dev | not-required |
| book-legacy-change-safety | 无产品行为修改，原始状态事件及产物证据保留 | before-dev | not-required |
| book-refactoring-pass | 无生产代码编辑 | before-dev | not-required |
| book-release-readiness | 无 runtime、部署或发布操作 | finish | not-required |

## 进度

- [x] 核对指定先例、PRD、六份文档、package scripts、路径与基线。
- [x] 完成六处 D11 与四处 D9、排序索引。
- [x] 精确计数、一次 build、SBOM JSON 路径比较、实际 pack/check-package。
- [x] run 1 保存模型快照与完整证据，当时保持 in-progress；随后由 orchestrator 提交为 PR #112 tip `10734e3a2b58e10c4a15855b0eda9c4fa4254904`。
- [x] 本轮按 Reviewy「artifacts OK, task.md blocker batch」完成 strict/done 与模型记录修正；仅 task.md 未提交，提交仍由 orchestrator 执行。

## 验证证据

入口时间：`TZ=Asia/Shanghai date -Is` = `2026-10-22T17:34:47+08:00`。命令环境统一为 `COREPACK_HOME=$HOME/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1`，未输出环境变量值。Evidence Source: developer-local；Source Revision: dirty；Evidence Publication: local-only；基线为 `ddcba1322f1f2ef43981870cc2bab96f2887f705` 加本地文档/SBOM 变更，不冒充 CI 或最终提交证据。

### 逐文件 grep -cF 计数

实际在 bash 中逐项执行 `grep -cF -- '<完整模式>' '<文件>'`，不是 Python 等价计数。完整 36 条命令、输出与退出码保存于 `reports/sync-grep.txt`；同 stem 中文汇总为 `.md`。计数 0 对应预期 exit 1，计数 1 对应 exit 0。

模式：

- old EN：`upstream latest is 18.12.2`
- old ZH：`实测过，上游最新是 18.12.2`
- D11 EN：`No longer supports omp 17.x; tested only on 18.11.1; as of the D11 lock on 2026-10-19, upstream latest was 18.12.2`
- D11 ZH：`不再支持 omp 17.x；只在 18.11.1 上实测过；截至 2026-10-19 D11 锁定时，上游最新是 18.12.2`
- D9 EN：`template tree (eight template files, plus LICENSE and NOTICE)`
- D9 ZH：`模板树（八个模板文件，另含 LICENSE、NOTICE）`

| 文件 | old EN | old ZH | D11 EN | D11 ZH | D9 EN | D9 ZH |
|---|---|---|---|---|---|---|
| README.md | 0 | 0 | 1 | 0 | 0 | 0 |
| README_zh.md | 0 | 0 | 0 | 1 | 0 | 0 |
| packages/omp-sbtd/README.md | 0 | 0 | 1 | 0 | 1 | 0 |
| packages/omp-sbtd/README_zh.md | 0 | 0 | 0 | 1 | 0 | 1 |
| packages/omp-sbtd/CHANGELOG.md | 0 | 0 | 1 | 0 | 1 | 0 |
| packages/omp-sbtd/CHANGELOG.zh.md | 0 | 0 | 0 | 1 | 0 | 1 |

根 README 的 D9 为 0 是指定边界。内存逐字节比较六份文档与 origin/main：恰为用户指定的十处替换，无其他措辞或换行变更；旧计数前缀随替换移除。索引仅增加一行，task ID 按 ASCII 排序，位于 pr-a-migrate-kit 之前。原生辅助结果：`reports/sync-scope.json`。范围脚本最初把 Markdown 整行（含 `]`）排序，触发断言；改为 task ID 排序后通过，未修改仓库来适应错误断言，未重建。

### install / build / SBOM

- 根 `pnpm install --frozen-lockfile`：exit 0；入口 node_modules 缺失，安装 738 packages、738 reused、0 downloaded，pnpm 11.17.0。原生 `reports/sync-install.txt` 与同 stem 中文汇总 `.md`。
- `packages/omp-sbtd` 中 `pnpm build`：**仅执行一次，exit 0**；`generated output is current`，最后一步 `tsx scripts/p0/write-sbom.ts` 正常生成 SBOM。未另行执行 write-sbom、未再次 build。原生 `reports/sync-build.txt` 与同 stem `.md`。
- SBOM 相对 `origin/main:packages/omp-sbtd/SBOM.spdx.json` 递归 JSON 比较恰好三个值，其余键、列表长度和值不变；README / CHANGELOG 新 checksum 与实际文件 SHA-256 相等。原生 `reports/sync-sbom-diff.json`。

| 精确 JSON 路径 | 对象 | 新值 |
|---|---|---|
| `/documentNamespace` | 来源树 namespace | `https://kpi.local/spdx/2d76b562920d56734ece887bbe916ba7d98501d018bf3ee968db3d96fdf7f128` |
| `/files/0/checksums/0/checksumValue` | `./CHANGELOG.md` | `747b7e7a1ef081c70dbc6bbc0289d06aed6e05bd96f47e4a3bf7ec33e384af81` |
| `/files/371/checksums/0/checksumValue` | `./README.md` | `82540930256b14a445efb85ce5e8a568c9f3c89670c0d944e9de46bb1500cd70` |

### 实际打包产物 smoke

`mktemp -d /tmp/omp-sbtd-d11-d9-pack-XXXXXX` 创建 `/tmp/omp-sbtd-d11-d9-pack-ORla07`；包目录依次执行：

```sh
pnpm pack --pack-destination /tmp/omp-sbtd-d11-d9-pack-ORla07
tar -xzf /tmp/omp-sbtd-d11-d9-pack-ORla07/kunolu-omp-sbtd-0.1.0-rc.14.tgz -C /tmp/omp-sbtd-d11-d9-pack-ORla07
pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/omp-sbtd-d11-d9-pack-ORla07/package
```

三个命令均 **exit 0**；输出分别保存在 `reports/sync-pack.txt`、`reports/sync-unpack.txt`、`reports/sync-check-package.txt`，均有同 stem 中文汇总 `.md`。check-package 结果：

| 字段 | 实测值 |
|---|---|
| packedFileCount | 471 |
| sourceTreeSha256 | `2d76b562920d56734ece887bbe916ba7d98501d018bf3ee968db3d96fdf7f128` |
| sbomSha256 | `0766910ddce38a87633319f0c065ae3af934ddaae7531e27ca0e431ff3086214` |
| SBOM_MISMATCH | 输出无此字符串 |

build / check-package 两个 hash 完全一致，SBOM 文件实际 SHA-256 也等于 sbomSha256。包版本仍为 0.1.0-rc.14，本次不 bump 或发布。

### 跳过与恢复边界

- rtk: skipped-for-report，按用户要求保存原生命令输出。全量测试、lint-fix、formatter：按范围不运行；独立 lint、BDD、宿主 smoke：skipped，纯文档同步，无代码或 .feature 变化，实际 tarball 检查覆盖本次派生一致性。
- Graft、Web/Mobile：skipped，不涉及结构/界面变更；Cross-repo context / API Contract: not-needed；Mock Strategy: none。无生产代码、schema、迁移或部署行为变更，Book gates 不触发；未声明 release-ready。
- 原生输出及中文报告在 ignored reports/，不会随共享 task 自动提交；临时包保留在上列 /tmp 路径，未创建 throwaway 脚本或永久测试。
- run 1 的文档与产物已由 orchestrator 提交为 PR #112 tip `10734e3a2b58e10c4a15855b0eda9c4fa4254904`；用户转达 Reviewy review「artifacts OK, task.md blocker batch」。本轮仅修正 task.md 并记 done，修正仍未暂存、未提交，不代表 PR 已合并、CI、宿主重新认证或发布；不改 PRD 或历史任务。未验证全库 TaskStore 恢复。
- 本轮未运行 build、pack、write-sbom、formatter、全量测试或运行时 smoke：仅任务元数据与证据记录修正，且用户明确禁止重建产物。BDD、Graft、独立生产代码复核、Cross-repo context / API Contract：not-needed；Mock Strategy：none；rtk：not-needed，使用只读原生命令与内存校验，不生成新报告文件。

## CONTRACT-CHANGE-NEEDED

无；仅同步已锁定文档及其 SBOM 派生值，不改变发布物清单、运行时或 PRD。

## 使用的模型

> run 1 已结束，以下为全会话最终计数（orchestrator 提供，本轮从原 jsonl 复算一致），不再使用旧快照的 11 / 24。`reports/sync-model-usage.json` 仅保留为 run 1 历史快照，本轮未改写。fix run 1 的 jsonl 快照时间为 **2026-10-22T17:53:26+08:00**（`TZ=Asia/Shanghai date -Is`）；此后编辑、验证与回复不计入，不冒充全会话最终计数。两轮均无 subagent。

| agent/session | provider/model | thinkingLevel | assistant messages / tool calls | purpose | resolvedModelIsFallback | title-generation count | job-widget entries |
|---|---|---|---|---|---|---|---|
| run 1 主会话 `01a162f6-5626-7665-973d-79c645e05e31` | openai-codex / gpt-6-astra | high | 16 / 28（全会话最终计数） | 文档同步、唯一 writer、构建/包检查与证据记录 | false | 1（auto title_change） | 0（type:model_usage purpose=job-widget） |
| run 1 自动标题（同会话事件） | 未记录 / unknown | 未记录 / unknown | 未记录 / unknown | title-generation | 未记录 / unknown | 1（同一事件，不另加总） | 不适用 |
| fix run 1 主会话 `01a16306-a700-75e6-9959-afc1152ace79` | openai-codex / gpt-6-astra | high | 4 / 17（2026-10-22T17:53:26+08:00 快照） | Reviewy blocker fix，仅 task.md | false | 0（title_change） | 0（type:model_usage purpose=job-widget） |

run 1 jsonl：`~/.omp/agent/sessions/--workspace-sbtd-plugins-d11-d9-sync--/2026-10-22T09-34-33-510Z_01a162f6-5626-7665-973d-79c645e05e31.jsonl`。fix run 1 jsonl：`~/.omp/agent/sessions/--workspace-sbtd-plugins-d11-d9-sync--/2026-10-22T09-52-22-784Z_01a16306-a700-75e6-9959-afc1152ace79.jsonl`（同目录除 run 1 外最新文件）。两个 session header 的 cwd 均与授权 worktree 匹配；本轮发现上述两份 jsonl，无子代理会话。

统计定义：assistant 消息取 `type=message` 且 `message.role=assistant`；tool calls 取其 content 内 `type=toolCall`，包括快照时仍在执行的 eval，不把 eval 内调用重复算作 assistant toolCall。run 1 最终工具分布：read 12、bash 1、todo 1、grep 1、eval 8、glob 2、write 1、edit 2。fix run 1 快照工具分布：read 9、bash 1、todo 2、grep 2、glob 1、eval 2。thinkingLevel 来自各自 `thinking_level_change`；provider/model 与 fallback 来自各自 `model_change`（`resolvedModelIsFallback=false`）。`title` 头部不是生成事件；run 1 的 `title_change source=auto` 为 1 条，fix run 1 快照为 0 条。两轮均未发现 `type=model_usage purpose=job-widget` 条目；标题模型未记录，不推断。

每轮开始前均由 orchestrator 执行 astra 连通性 ping：`omp -p --no-session --model openai-codex/gpt-6-astra:high`，临时调用、无 session jsonl，均回复 `ASTRA_OK`；日志分别为 `~/.omp/logs/sbtd-d11-d9-sync/ping.log`（run 1）及 `~/.omp/logs/sbtd-d11-d9-sync/ping-fix1.log`（fix run 1）。调用方式与归属据本轮用户提供，本轮只读确认两份日志均含 `ASTRA_OK`，未重新执行 ping；不计入上述 session 计数。
