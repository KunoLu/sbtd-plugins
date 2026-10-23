---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-2-pr-g-readme
workflow_mode: strict
mode_source: user
mode_note: 用户本次明确指定 strict、唯一 writer 与先 records-only 后 README/bump 的提交顺序；仅本 worktree 本地提交，不 push/PR/comment/tag/publish/merge。
status: checking
branch: feat/dsh-sbtd-0.2.0-rc.2-readme
created_at: '2026-10-23T13:10:17+08:00'
updated_at: '2026-10-23T13:27:36+08:00'
completed_at: null
---
# dsh-sbtd 行 G：0.2.0-rc.2 双语 README 与版本 bump

## 目标 / 范围 / 非目标

- README.md 改为英文默认，新增中文 README.zh.md；章节与内容镜像，顶部 EN · 中文切换沿用 omp 格式，两个绝对链接钉 dsh-sbtd-v0.2.0-rc.2。
- package.json 仅 version 升至 0.2.0-rc.2；最小调整版本断言/feature；双语 CHANGELOG 新增 2026-10-23 docs-only 条目；root README_zh.md 仅改 dsh 文档链接；PRD 行 G 标 in-progress，PR/merge/done 字段由后续 PR 回填。
- 不改 src、schema、契约、工具名、peer/engines/devDependencies、lockfile、omp 文件或旧 dsh-sbtd-readme-host-pin-0-2-0-rc-2 任务。不推送、开 PR、评论、打 tag、建 Release、发布、合并或修改全局配置。
- 授权根 /workspace/sbtd-plugins-rowg；基线 46680a5f6403d9c6032e1dd6a3d2cb49cb2ff842，入口 clean。首提交 0410bf1 仅回填 sbtd-changelog-backfill/task.md，23 insertions / 3 deletions；git diff HEAD~1 HEAD 确认删除仅 status/updated_at/completed_at，历史正文及 SNAPSHOT 保留，index 无状态列且未改。

## 决策与 PR-facing evidence

- 用户本次任务指令明确中文文件名为 `README.zh.md`（不同于 PRD 行 G / omp D6 的 `README_zh.md` 文字），Lord 记录。
- 未完整调用 grill-with-docs：用户与 PRD 已锁定范围，无新领域规则或模型歧义。
- 沿用行 R/backfill 已记录的 TaskStore 全库历史 schema blocker，不重跑确认、不调用 lifecycle、不写 active pointer；本文件为用户明确要求的共享文档产物，不声称 TaskStore/自动恢复通过。父路径无 symlink、目标初始不存在且不被 ignore，reports 命中 /ai/tasks/**/reports；不建立其他任务记录。
- 0.2.0-rc.2 是尚未发布的 docs-only RC；当前已发布 next=0.2.0-rc.1、latest=0.1.0-rc.1，不把 bump 当作 publish。宿主钉 0.2.0-rc.2、range >=0.2.0-rc.2 <0.3.0-0 不变。
- CHANGELOG 按行 E 先例在 bump 提交打日期戳；若实际 npm publish 日期不同，后续须纠正标题日期。
- 源码核对发现旧 README 的 book gate 说明省略 default/lite 降级；翻译同时按现有 hooks/CHANGELOG 写清 strict 强制、default/lite 告警及完整 docs-grill DDD 共同例外，不改运行时。

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、领域规则或边界歧义 | before-dev | not-required |
| book-ddia-data-design | 无数据/schema/跨服务流设计；共享 task 仅记录既有格式 | before-dev | not-required |
| book-legacy-change-safety | 无生产行为修改，版本元数据与文档由现有 suite/pack 保护 | before-dev | not-required |
| book-refactoring-pass | 不改既有生产代码 | before-dev | not-required |
| book-release-readiness | 版本与未来 tarball 文档变更，按行 E 先例审查发布边界 | after-validation | blocked（中文 README 排除验收失败；既有 lint 失败） |

## 验证证据

- 已读取两份 PRD、行 E/R/backfill 记录、index、两包 README 与 dsh manifest/CHANGELOG/tests/features。git log -p 核对 PRD 后续回填惯例；git log 确认 46680a5 的 %cI 与实际首提交 2058673；远程旧分支查询为空。
- 验证计划：缺 node_modules 时 frozen install；dsh test/lint/typecheck、root biome lint；npm pack --dry-run --json；python3 一次性 Markdown 渲染/标题与内容结构镜像、链接/版本/历史保护检查；独立只读审查；diff --check 与提交边界/clean status。
- 主会话是唯一 writer 与验证 controller；审查只读，不运行 build/lint/tests/formatters。Graft skipped：文档与元数据任务采用源码/manifest/契约，不启动或配置额外服务。

### 实际本地验证

- 环境：Linux，Node v22.20.0 / pnpm 11.17.0 / npm 10.9.3 / Python 3.13.5。基于 `0410bf1b85b2f462268e2309aad03d01d7402268` 加工作树变更；Evidence Source=developer-local、Source Revision=dirty、Evidence Publication=local-only，不冒充 CI 或已发布 PR-head 证据。
- `pnpm install --frozen-lockfile`：exit 0，738 packages reused、0 downloaded，lockfile 未修改。原生输出 `reports/row-g-install.txt`。
- 测试临时目录与 npm cache 设在本 task 的 ignored reports 内。首轮 `pnpm --filter @kunolu/dsh-sbtd test` 为 334 passed / 1 failed：`t14-lessons.test.mjs:879` 的 missing identity fixture 放在 Git worktree 内，向上 Git discovery 使“无身份”前提失效。这是本轮隔离设置错误，不是 README/bump 回归；没有读取/打印身份值或改运行时代码。后续设置 `GIT_CEILING_DIRECTORIES=$TMPDIR` 阻止 fixture 越界向上发现。
- 修正环境后，`node --test --test-name-pattern='missing .sbtd/developer skips' test/t14-lessons.test.mjs`：1/1；完整 t14：38/38；随后完整包测试 335/335。最后在 release-blocked 双语段落写入后，`pnpm --filter @kunolu/dsh-sbtd test` 再次 **335 passed / 0 failed / 0 skipped，exit 0**（13:24:24+08:00 开始，7.91s）。原生失败、定点、子集、最终输出均保留：`row-g-tests`、`row-g-lessons-isolated`、`row-g-lessons-subset`、`row-g-tests-final`、`row-g-tests-delivery`。
- `pnpm --filter @kunolu/dsh-sbtd lint`：**exit 1**，Biome checked 19 files，11 errors / 4 warnings / 1 info；均为未改 src 的格式/import/style 诊断。不擅改生产代码或运行自动修复。`reports/row-g-package-lint.txt`。
- `pnpm --filter @kunolu/dsh-sbtd typecheck`：**exit 0**。`reports/row-g-typecheck.txt`。
- 根 `pnpm lint`（`biome check .`）：**exit 1**，checked 190 files，44 errors / 9 warnings / 19 infos，输出上限另省略 52 条诊断。该结果与行 R 已记录的既有 dsh lint 数量一致；本轮不修越界格式问题，不报全绿。`reports/row-g-root-lint.txt`。
- `npm pack --dry-run --json`（cwd packages/dsh-sbtd）：命令 **exit 0**，**打包验收失败**。版本 0.2.0-rc.2，103 files = dist 76 + manuals 20 + README.md + README.zh.md + LICENSE + cordis.patch.yml + package.json + 两份 CHANGELOG。README.md 已收录，但 README.zh.md 也被收录。允许范围内尝试 `files: "!README.zh.md"`，再加 `.npmignore` 同名排除，两次仍为 103 files / 两份 README；无效探针均已撤回，最终 files 与基线完全相同，不保留 .npmignore。原生三次结果为 `row-g-pack-dry`、`row-g-pack-files-exclusion`、`row-g-pack-ignore-exclusion`。
- 用户要求的 stop 边界已执行：不通过改名、移文件、prepack/lifecycle、打包 staging 或工具替换绕过冲突，不改契约/schema/runtime。本次 **README.zh.md 不进包未达成**，不得发布；需要用户明确裁决文件名/打包要求冲突，不将 blocked 伪称通过。
- `python3 -c <一次性检查>` 使用 markdown-it CommonMark + tables 实际渲染两文档：各 15 headings（9 个二级、5 个三级、1 个标题），层级/顺序匹配，3 个代码块逐字相同，完整 Markdown block token 结构相同；相对文件目标存在、双向链接精确钉 tag、未发布措辞正确；manifest 仅 version 不同、旧 CHANGELOG 条目逐字保留、index 字母序通过。`row-g-doc-smoke-delivery` 为最终通过；早期一次性脚本错误预设 bullet 数而失败的 `row-g-doc-smoke` 仍保留，修正为真实结构对比后通过。未新增永久文案断言。
- t0 保留包版本/host/files 契约断言，删除需随语言重钉的旧中文 README 字符串断言；fu4 仅改插件版本常量。代码可读性复核：无新抽象、无压缩表达式、无生产代码变化；ponytail-review 的生产重构复核不适用。
- BDD=traceable：`features/t0-installable-stub.feature` 沿用中文场景+英文关键词；版本场景对应 t0 测试，文档场景由本次 python3 smoke 验证。没有新增 Gherkin runner。既有真实 CLI 安装场景的 @todo 保留；未安装/运行 dsh CLI，不冒充宿主端到端认证。
- 原生输出 `.txt`、执行元数据 `.json` 与同 stem 九节中文汇总 `.md` 位于本 task 的 ignored `reports/`；失败轮次均保留。rtk=skipped-for-report；Final Test Report / Run Summary MD=generated；Targeted Rerun / Affected Subset Rerun / Final Full Rerun=passed（仅测试 suite，lint 与 pack 验收仍失败）。Cross-repo context/API Contract=not-needed，未新增 mock；既有 suite 的 fixture/mock 不被称为 full-stack。
- `git diff --check` 通过；首提交的精确 diff 机器检查删除行只有三条允许字段。新增行的禁词检查通过。未改 src/omp/lockfile/旧 host-pin task。提交后 `origin/main...HEAD` 与 clean status 另作最终核验。
- Lessons-record 已用于评估隔离失误：本地身份不存在，用户禁止访问主 checkout，不解析其他 worktree、不新建身份、不扩大共享 lesson 范围；未保存长期 lesson。防止重犯的运行条件及失败证据保留于本 task，不冒充 lesson 写入成功。

## Release Readiness Review

- Status: **blocked**。
- Production path and affected users / systems：未来 0.2.0-rc.2 tarball 的 README 与版本元数据；当前安装方仍取已发布 rc.1，未改变 dist-tags。
- Failure modes and safeguards：`README.zh.md` 被 npm 自动收录，违背 row G 排除要求；三次原生 pack 已证明允许排除手段无效，停止进一步打包变更，两份 README 均明确写出发布阻塞。版本/host 契约、双语镜像由现有测试与文档 smoke 验证。
- Capacity / backpressure / limits：not-applicable，无运行时变化。
- Observability / alerts / runbook：本地 raw reports、中文汇总与本记录保留证据；不新增遥测。
- Rollout / migration / rollback / cleanup：尚未发布，无数据迁移；本地 scoped commits 可回滚。不删除用户产物。后续须先裁决打包冲突、解决必需验证失败，再评审/合并/tag/链接核验/双语 prerelease/publish；不是本任务授权。
- Required validation and result：测试 335/335、typecheck、文档渲染通过；package/root lint 失败，pack 命令成功但排除验收失败，故不得标 ready。
- Optional checks / residual risk：未运行 omp suite（未改 omp）、线上 tag 链接（tag 尚未建立）、CI、真实宿主安装；不把后续发布步骤当已完成。TaskStore 全库恢复仍不可靠。

## 独立复核

- `ReleaseContracts`：一项 P1，README.zh.md 被强制打包；其余首提交保护、manifest、tests/features、CHANGELOG、links、root/PRD/task/index 范围检查无发现。P1 接受并记录为未解决发布阻塞，不宣称 CLEAN 或验收完成。该 reviewer 只读，未执行 build/lint/tests/formatters。
- `BilingualFacts`：最终两份 README factual/parity review **CLEAN**；源码核对九工具、hooks/模式、clarify/review、manuals pin、遥测、卸载、平台说明，无需修正。新加 release-blocked 段落双语一致，准确区分排除要求与当前失败事实；此 CLEAN 不解决 ReleaseContracts 的 P1 打包验收阻塞。
- 两位 reviewer 均为原生只读审查，没有成为 writer/验证 controller。最终 task frontmatter（strict/user/checking/null 与实际 branch）、状态事件表 Markdown 渲染、15 组 raw/同 stem 中文报告九节结构检查通过；已删除本轮自建临时 fixture/npm cache，保留命名失败输出与执行元数据。

## 后续发布步骤（本任务未执行）

1. 后续 PR 评审与 CI，通过后 squash-merge；回填 PR、merge SHA 与时间。
2. 在 merge commit 上创建 annotated tag `dsh-sbtd-v0.2.0-rc.2`。
3. 打 tag 后、publish 前点击核验两份 README 的 pinned 语言链接；本轮不声称链接在线可达。
4. 创建双语 GitHub prerelease，再执行 `npm publish --tag next`；`latest` 保持不动。
5. 核验 npm dist-tags/tarball/README，必要时纠正 CHANGELOG publish 日期，再按 merge + publish 证据完成 row G。本轮最终仅 checking、completed_at null。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T13:12:28+08:00 | planned | in-progress | 首提交完成，建立 strict 记录并开始 row G 文档/元数据实现 | 0410bf1；index 新增一行；授权根/分支与路径检查通过 |
| 2026-10-23T13:25:38+08:00 | in-progress | checking | 本地实现与验证完成，按用户要求保留 checking；发布门被 pack 排除失败与既有 lint 失败阻塞，不标 done | 测试 335/335、typecheck/文档 smoke 通过；三次 pack 均含 README.zh.md；ReleaseContracts P1；completed_at null |
