---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-2-pr-g-readme
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：沿用 strict、唯一 writer 与先 records-only 后 README/bump 的提交顺序；仅本 worktree 本地提交，不 push/PR/comment/tag/publish/merge。
status: checking
branch: feat/dsh-sbtd-0.2.0-rc.2-readme
created_at: '2026-10-23T13:10:17+08:00'
updated_at: '2026-10-23T13:59:56+08:00'
completed_at: null
---
# dsh-sbtd 行 G：0.2.0-rc.2 双语 README 与版本 bump

## 目标 / 范围 / 非目标

- README.md 改为英文默认，新增中文 README.zh.md；章节与内容镜像，顶部 EN · 中文切换沿用 omp 格式，两个绝对链接钉 dsh-sbtd-v0.2.0-rc.2。
- package.json 仅 version 升至 0.2.0-rc.2；最小调整版本断言/feature；双语 CHANGELOG 新增 2026-10-23 docs-only 条目；root README_zh.md 仅改 dsh 文档链接；PRD 行 G 标 in-progress，PR/merge/done 字段由后续 PR 回填。
- 不改 src、schema、契约、工具名、peer/engines/devDependencies、lockfile、omp 文件或旧 dsh-sbtd-readme-host-pin-0-2-0-rc-2 任务。不推送、开 PR、评论、打 tag、建 Release、发布、合并或修改全局配置。
- 授权根 /workspace/sbtd-plugins-rowg；基线 46680a5f6403d9c6032e1dd6a3d2cb49cb2ff842，入口 clean。首提交 0410bf1 仅回填 sbtd-changelog-backfill/task.md，23 insertions / 3 deletions；git diff HEAD~1 HEAD 确认删除仅 status/updated_at/completed_at，历史正文及 SNAPSHOT 保留，index 无状态列且未改。

## 决策与 PR-facing evidence

- 用户 2026-10-22 22:53 +08:00 群内确认（两个包的中文 README 都命名为 `README.zh.md`），Lord 记录。
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
| book-release-readiness | 版本与未来 tarball 文档变更，按行 E 先例审查发布边界 | after-validation | blocked（待用户裁决中文文件名/打包选项 A 或 B；既有 lint 失败非本分支引入） |

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
- 用户要求的 stop 边界已执行：不通过改名、移文件、prepack/lifecycle、打包 staging 或工具替换绕过冲突，不改契约/schema/runtime。publish 阻塞，待用户裁决：（A）按 PRD 行 G / omp D6 改名为 `README_zh.md`，使中文文件不进包；（B）按本次任务指令保留 `README.zh.md`，接受其随 tarball 发布，并修订行 G 的「不进包」要求。本次不代用户选择。
- `python3 -c <一次性检查>` 使用 markdown-it CommonMark + tables 实际渲染两文档：各 15 headings（9 个二级、5 个三级、1 个标题），层级/顺序匹配，3 个代码块逐字相同，完整 Markdown block token 结构相同；相对文件目标存在、双向链接精确钉 tag、未发布措辞正确；manifest 仅 version 不同、旧 CHANGELOG 条目逐字保留、index 字母序通过。`row-g-doc-smoke-delivery` 为最终通过；早期一次性脚本错误预设 bullet 数而失败的 `row-g-doc-smoke` 仍保留，修正为真实结构对比后通过。未新增永久文案断言。
- t0 保留包版本/host/files 契约断言，删除需随语言重钉的旧中文 README 字符串断言；fu4 仅改插件版本常量。代码可读性复核：无新抽象、无压缩表达式、无生产代码变化；ponytail-review 的生产重构复核不适用。
- BDD=traceable：`features/t0-installable-stub.feature` 沿用中文场景+英文关键词；版本场景对应 t0 测试，文档场景由本次 python3 smoke 验证。没有新增 Gherkin runner。既有真实 CLI 安装场景的 @todo 保留；未安装/运行 dsh CLI，不冒充宿主端到端认证。
- 原生输出 `.txt`、执行元数据 `.json` 与同 stem 九节中文汇总 `.md` 位于本 task 的 ignored `reports/`；失败轮次均保留。rtk=skipped-for-report；Final Test Report / Run Summary MD=generated；Targeted Rerun / Affected Subset Rerun / Final Full Rerun=passed（仅测试 suite，lint 与 pack 验收仍失败）。Cross-repo context/API Contract=not-needed，未新增 mock；既有 suite 的 fixture/mock 不被称为 full-stack。
- `git diff --check` 通过；首提交的精确 diff 机器检查删除行只有三条允许字段。新增行的禁词检查通过。未改 src/omp/lockfile/旧 host-pin task。提交后 `origin/main...HEAD` 与 clean status 另作最终核验。
- Lessons-record 已用于评估隔离失误：本地身份不存在，用户禁止访问主 checkout，不解析其他 worktree、不新建身份、不扩大共享 lesson 范围；未保存长期 lesson。防止重犯的运行条件及失败证据保留于本 task，不冒充 lesson 写入成功。

## Release Readiness Review

- Status: **blocked**。
- Production path and affected users / systems：未来 0.2.0-rc.2 tarball 的 README 与版本元数据；当前安装方仍取已发布 rc.1，未改变 dist-tags。
- Failure modes and safeguards：npm 自动收录 `README.*`，因此 `README.zh.md` 会进包；此前三次原生 pack 已证明排除探针无效。publish 阻塞，待用户选择 A（改为 `README_zh.md`，不进包）或 B（保留 `README.zh.md` 并接受随包发布，修订行 G）；不自行裁决。fix1 已从两份 shipped README 删除流程阻塞段落，并将 pack 指引改为中性表述；决策与失败证据只留在 PRD/task。版本/host/安装/双向链接契约由双语 README guards 保护。
- Capacity / backpressure / limits：not-applicable，无运行时变化。
- Observability / alerts / runbook：本地 raw reports、中文汇总与本记录保留证据；不新增遥测。
- Rollout / migration / rollback / cleanup：尚未发布，无数据迁移；本地 scoped commits 可回滚。不删除用户产物。后续须先取得用户对 A/B 的裁决，并处理发布所需验证，再评审/合并/tag/链接核验/双语 prerelease/publish；不是本任务授权。
- Required validation and result：fix1 包测试 **342 passed / 0 failed / 0 skipped**、typecheck、文档渲染通过；scratch baseline 11/11，8/8 负向变体均被 guards 拒绝。既有 dsh `biome check src` 11 errors / 根 `biome check .` 44 errors，与 origin/main `46680a5` 相同，本分支无 src 变更，非本次引入（编排方整理的基线结论；本次不重跑确认）。pack 命令成功但命名/打包要求冲突待裁决，故不得标 ready。
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

## Fix1 验证与修正

- 六文件限定修复：恢复 t0 对 README.md / README.zh.md 的 host pin、@next 安装、禁用裸安装/旧路径/旧版本、未发布 rc.2 与当前 dist-tags、顶部两个 tag-pinned 链接及二/三级标题数量 guards；原 package.json 断言保留。feature 沿用中文场景 + 英文关键词，补双语切换与章节 parity 场景，BDD=traceable，对应 t0 测试；真实宿主 CLI 场景仍为既有 @todo。
- 两份 README 删除发布阻塞段落，pack 指引不再宣称中文文件包含或排除；PRD 2026-10-23 行 G 注释保留用户指令/Lord 句，明确 A/B 待用户裁决。上方初轮验证与独立复核记录保留为历史证据，不将其旧断言当作 fix1 当前状态。
- `pnpm --filter @kunolu/dsh-sbtd test` 首次启动在执行测试前因 Corepack 尝试写 `/usr/local/share/corepack/v1` 而 EACCES（exit 1）；改用已有 `COREPACK_HOME=/home/box/.cache/node/corepack`，设置 `COREPACK_ENABLE_NETWORK=0`，不安装、不改全局配置。fixture 使用 `TMPDIR=/tmp` / `GIT_CEILING_DIRECTORIES=/tmp`。随后原生命令 **342 passed / 0 failed / 0 skipped，exit 0**；`pnpm --filter @kunolu/dsh-sbtd typecheck` **exit 0**。
- Python 3 scratch smoke：复制实际 t0 测试与文档到 `/tmp`，baseline **11 passed / 0 failed**；逐一移除两份文档的两个切换链接、各加一条裸安装命令、各加一个二级标题，**8/8** 变体均恰好触发一个测试失败。原始失败输出保留，scratch 已删除。markdown-it 实际渲染两份文档，各 9 个二级 / 5 个三级标题，完整 block token 结构相同。
- `git diff --check origin/main...HEAD` 与工作树 `git diff --check` 均 exit 0；README 发布状态词及限定文档禁词 grep 无匹配。提交后再次核验三提交链、原两提交不变、diff whitespace 与 clean status。
- 原生输出与同 stem 中文汇总位于 ignored `reports/fix1-{launch,tests,typecheck,smoke}.{txt,md}`。Evidence Source=developer-local、Source Revision=dirty（基于 `1c9b1bbfeefd11f3c3390e8dc2fcee0e3a872d7b` 的六文件变更）、Evidence Publication=local-only；不冒充 CI 或发布证据。rtk=skipped-for-report。
- Code Readability Review：沿用 node:test/assert/readFileSync，按文件生成有明确文件名的 guard 用例，单独比较两种标题级别；无生产代码/导出接口变更、无新依赖或抽象。此次仅 docs/tests，不触发 legacy/refactor/DDD/DDIA 新门禁；未运行 omp suite、lint/pack 已知失败重证、线上 tag 链接或真实宿主安装。Graft skipped；Cross-repo context/API Contract=not-needed，新增 Mock Strategy=none。TaskStore 的既有全库 schema blocker 继续保留，仅更新明确授权共享文档，不声称生命周期 helper 或自动恢复通过。

## Fix2 验证与修正

- B1：双语 README 安装状态改为不随时间失效的 dist-tag `next` 指引；删除版本发布状态与 dist-tag 当前版本断言，保留宿主 pin、@next 命令、禁止裸包名/绝对路径/旧版本、顶部 tag-pinned 语言链接和 EN/ZH 标题 parity guards。t0 增加不含未发布措辞或 dist-tag 版本赋值的反向 guard；feature 同步为「安装指引不依赖版本发布状态」，沿用中文场景 + 英文关键词，BDD=traceable。
- B2：决策条目保留用户 2026-10-22 22:53 +08:00 群内确认的命名归属，Lord 记录；mode_note 与 fix1 入场事件的操作要求归属为编排方整理，不使用该命名确认时间。删除 PRD 行 G 解释注及其空行，同时去掉状态单元格中的悬空「见下注」。`git diff origin/main -- docs/prd/dsh-sbtd-0.2.0-rc.1.md` 及 Python 逐行/逐单元格比较证明仅行 G 的状态单元格变化。
- B3：既有 lint 基线结论明确为编排方整理；旧 backfill 任务仅追加两条 done → done / record correction 事件，分别纠正材料来源与标题生成统计范围。只读日志确认 pid 79530 的 OmpHistory、DshHistory 各有一次 cursor/composer-2.5 success；不改既有事件、0410bf1 内容或历史分支绑定。
- 时间：fix1 两条事件按同一时刻转换至 +08:00；本轮 updated_at 与新事件使用实际 +08:00 时间。当前 completed_at 保持 null。本任务的 **FINAL 模型统计段在合并后回填，不在本轮填写或猜测**。
- 原生验证 cwd 为 `packages/dsh-sbtd`，命令按要求使用 `../../node_modules/.bin/tsc -p tsconfig.json --noEmit`，再 `../../node_modules/.bin/tsc -p tsconfig.json && node --test test/*.test.mjs`。首轮 typecheck exit 0，完整测试 **341 passed / 1 failed / 0 skipped（342 tests）**：`test/t6-clarify.test.mjs:423` 仍断言 README 含 `0.1.0-rc.1`，与 B1 冲突。仅删除此陈旧断言，保留 clarify 与宿主 pin 检查；这是本轮第八个修改文件，未改运行时代码。
- 修正后的定点命令 `node --test --test-name-pattern='README 提到 sbtd_clarify' test/t6-clarify.test.mjs`：**1/1**；`node --test test/t0-stub.test.mjs test/t6-clarify.test.mjs`：**37/37**；再次执行上述 noEmit 与 build + 全包测试：**exit 0，342 passed / 0 failed / 0 skipped**。fixture 隔离沿用 `TMPDIR=/tmp` / `GIT_CEILING_DIRECTORIES=/tmp`，未安装依赖或改全局配置。
- Python 3 + markdown-it 一次性 smoke 实际渲染双语 README：各 **15 headings**，Markdown block token 结构一致，渲染后仍为 next 安装且无发布状态声明；两个任务的事件表均正常渲染。`git diff d60b4c1 -- ai/tasks/sbtd-changelog-backfill/task.md` 为 **2 insertions / 0 deletions**，Python 比较确认每条旧行逐字保留。
- `git diff --check origin/main...HEAD` 与工作树 `git diff --check` 均 exit 0；README 未发布措辞与 dist-tag 版本赋值无匹配，新任务 UTC 零偏移时间无匹配，八个修改文件的禁止来源措辞无匹配。最终新增提交后的 whitespace、clean status、四提交链及前三提交不变由提交后命令核验，不预写其成功。
- 本轮 raw 与同 stem 中文报告为 ignored `reports/fix2-{typecheck,tests,verification}.{txt,md}`，首轮失败保留。Linux / Node v22.20.0 / Python 3.13.5；Evidence Source=developer-local、Source Revision=dirty（基于 d60b4c1d4ce28134be14ea443e0c8aadfb49a6ee）、Evidence Publication=local-only；不冒充 CI 或新提交 exact SHA 证据。rtk=skipped-for-report；Final Test Report / Run Summary MD=generated；Targeted / Affected Subset / Final Full Rerun=passed。
- Code Readability Review：仅删除陈旧断言、沿用 node:test/assert/readFileSync，无生产/导出接口变更、依赖或新抽象。Book Gate Plan 沿用：DDD/DDIA/legacy/refactor 无新触发；Release Readiness Review 仍 **blocked**，名称/打包 A/B 待用户裁决，既有 lint 阻塞未变；容量/重试/遥测不适用，回滚边界为本地 scoped commit。未重跑已知 lint/pack 失败、omp suite、线上 tag 链接、CI 或真实宿主安装；既有 CLI @todo 保留。Graft skipped，Cross-repo context/API Contract=not-needed，新增 Mock Strategy=none。TaskStore 全库 schema blocker 沿用，不调用 lifecycle，不声称自动恢复通过。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T13:12:28+08:00 | planned | in-progress | 首提交完成，建立 strict 记录并开始 row G 文档/元数据实现 | 0410bf1；index 新增一行；授权根/分支与路径检查通过 |
| 2026-10-23T13:25:38+08:00 | in-progress | checking | 本地实现与验证完成，按用户要求保留 checking；发布门被 pack 排除失败与既有 lint 失败阻塞，不标 done | 测试 335/335、typecheck/文档 smoke 通过；三次 pack 均含 README.zh.md；ReleaseContracts P1；completed_at null |
| 2026-10-23T13:31:04+08:00 | checking | in-progress | fix1: restore README guards, remove README blocker text, PRD note accuracy | 编排方整理：fix1 限定六文件修复；入口 clean，HEAD 1c9b1bbfeefd11f3c3390e8dc2fcee0e3a872d7b；沿用 strict 与既有 TaskStore 限制，仅编辑获授权共享记录 |
| 2026-10-23T13:33:28+08:00 | in-progress | checking | fix1: 双语 guards、README 中性发布指引与 PRD 冲突记录修正并验证；publish 待用户 A/B 裁决 | 包测试 342/342、typecheck exit 0、scratch 8/8 拒绝、双语渲染 parity 通过；reports/fix1-*；既有 lint 11/44 errors 非本次引入；completed_at null |
| 2026-10-23T13:51:14+08:00 | checking | in-progress | fix2: Reviewy findings B1–B3 + nits | 入口 clean，HEAD d60b4c1d4ce28134be14ea443e0c8aadfb49a6ee；沿用 strict 与既有 TaskStore 限制，仅编辑明确授权共享记录；本轮只新增一个本地提交，不改 README.zh.md 文件名、不执行远端写入 |
| 2026-10-23T13:54:49+08:00 | in-progress | checking | fix2: Reviewy B1–B3 + nits 修正并完成本地验证 | 定点 1/1、子集 37/37、最终全包 342/342、typecheck/build exit 0；双语渲染 smoke 通过；旧任务仅新增两行、PRD 仅行 G 状态单元格变化；reports/fix2-* 保留首轮失败；completed_at null；FINAL 模型统计合并后回填 |
| 2026-10-23T13:59:56+08:00 | checking | checking | fix3: attribution correction (Lord/Reviewy 13:58) | mode_note 与 fix1 事件改为「编排方整理」；22:53 归属仅保留于命名决策（:24）；未找到本项 strict 的可核验用户群内确认时间。 |
