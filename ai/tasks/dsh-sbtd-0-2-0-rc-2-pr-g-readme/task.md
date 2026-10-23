---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-2-pr-g-readme
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：沿用 strict、唯一 writer 与先 records-only 后 README/bump 的提交顺序；仅本 worktree 本地提交，不 push/PR/comment/tag/publish/merge。
status: done
branch: feat/dsh-sbtd-0.2.0-rc.2-readme
created_at: '2026-10-23T13:10:17+08:00'
updated_at: '2026-10-23T18:00:01+08:00'
completed_at: '2026-10-23T17:03:32+08:00'
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
| 2026-10-23T16:46:38+08:00 | checking | checking | 编排方整理：align #118 与已合并 #119；U2/R12 解除命名/打包阻塞，其他既有阻塞保留；本轮不标 done | #119 merge 9ad277c35b5e4e61a6f7cb5fd959e6ce3a89de8f，2026-10-23T16:37:30+08:00；typecheck/build exit 0；全包 342 passed / 0 failed / 0 skipped；pack entryCount 103，含 README.zh.md；双语渲染、历史保留、YAML 与差异检查通过；reports/align-*；completed_at null |
| 2026-10-23T16:53:59+08:00 | checking | checking | 编排方整理：D6/D7 状态单元格去掉「locked（…）」外壳，改为「用户 2026-10-19 原锁定；现行命名见 R11，随包发布见 R12」/「用户 2026-10-19 11:39 原锁定；…」，修正上一 align 提交 1df186a 仍保留 locked 前缀 | 追加本事件前 `git diff --stat`：docs/prd/omp-sbtd-0.2.0-rc.1.md，1 file changed, 2 insertions(+), 2 deletions(-)；`git diff --check` 无输出、exit 0 |
| 2026-10-23T17:03:32+08:00 | checking | done | 编排方整理：#118 squash-merge，完成该 PR 的 README/bump 交付；本轮追加历史回填，不重绑定原分支 | squash 548a0bf125e3b3fe1407de11094409e55c2e779e；GitHub mergedAt 2026-10-23T17:03:32+08:00；git %cI 2026-10-23T17:03:31+08:00；Reviewy CLEAN @ 40dc46d；不据此清除历史 lint 门禁 |

## Align：合并 #119 后的当前状态

- 编排方整理：本轮沿用 strict，入口 HEAD `56e43afe6e9b8896ef144fe7b81cd0b394820ff0`，唯一 writer，仅在原分支做一个本地 alignment commit；#119 历史回填保留原 branch，不重绑定。沿用既有 TaskStore 全库 schema blocker，不重跑、不调用 lifecycle、不写 active pointer，不声称自动恢复通过。未完整调用 grill-with-docs：范围和验收明确，无新领域歧义。
- U1：用户 2026-10-22 22:53 +08:00 群内确认（两个包的中文 README 都命名为 `README.zh.md`），Lord 记录。
- U2：用户 2026-10-23 16:15 +08:00 群内确认（选 B：保留 `README.zh.md` 随包发布，先开 PRD PR 改 D6/row G），Lord 记录。
- 编排方整理：#119 已于 `2026-10-23T16:37:30+08:00` squash-merge 为 `9ad277c35b5e4e61a6f7cb5fd959e6ce3a89de8f`，并已合入本分支。现行 PRD R11/R12 规定 `README.zh.md` 随 npm 包发布；U2 与 #119 已解除历史 A/B 待决及 Release Readiness 的命名/打包阻塞。旧正文、旧门禁表和旧事件保留为历史，不再代表当前命名/打包要求；其他既有阻塞（包括 lint）不变，不宣称 release-ready。
- 编排方整理：行 G 仅恢复状态单元格为本分支 in-progress / 本次仅 README/bump，保留 2026-10-19 11:43、D13、U2/R12 来源；任务描述保持合并后 main 原文。任务仍 checking / completed_at null，不在 #118 合并前标 done。
- 编排方整理：收到的 B2 发布状态/时机描述与「Fix2 验证与修正」编号不符；该记录中发布状态与 dist-tag 版本断言是 B1，22:53 命名归属及 PRD 行 G 注释删除是 B2。本轮同时满足两项：双语 README 保持不含 rc.2 已发布/未发布、发布日期或 after row X 时机声明，保留 RC 发布流程；仅在原镜像链接句补明 `README.zh.md` 随包发布，顶部 EN/中文 tag-pinned 互链和英文默认不变；U1/U2 分列，操作材料归属编排方整理，不恢复旧 PRD 注释。
- 编排方整理：D6/D7 状态措辞区分历史原锁定与现行 R11/R12；D6 只保留 2026-10-19，D7 保留 11:39，不补造精度；§6 不新增修订行。
- Book Gate Plan（本轮）：DDD/DDIA/legacy/refactor 均 not-required（无完整 grill、领域/数据设计、生产代码或运行时修改）；Release Readiness 在本轮验证后更新，仅解除有 U2/#119 依据的命名/打包项，既有 lint 阻塞保留。

### Align 验证证据

- 编排方整理：原生命令 cwd=`packages/dsh-sbtd`。`../../node_modules/.bin/tsc -p tsconfig.json --noEmit`：exit 0；`../../node_modules/.bin/tsc -p tsconfig.json && TMPDIR=/tmp GIT_CEILING_DIRECTORIES=/tmp node --test test/*.test.mjs`：exit 0，**342 passed / 0 failed / 0 skipped / 0 cancelled / 0 todo，total 342**，测试耗时 6051.622153 ms。没有改测试、feature、package.json、lockfile 或 src。
- `npm pack --dry-run --json`：exit 0，`@kunolu/dsh-sbtd@0.2.0-rc.2`，**entryCount=103**；含 `README.md` 与 `README.zh.md`，符合现行 R11/R12；完整清单见下。本次为 dry-run，不是 publish 或已发布 tarball 证据。
- Python 3 + markdown-it CommonMark/tables 实际渲染双语 README：各 15 headings，完整 block token 结构一致；英文默认、顶部 EN/中文 release-tag-pinned 互链与发布流程保留；无 rc.2 发布状态、发布日期、dist-tag 版本赋值或 after row X 时机断言。仅 README 第 104 行各补一处随包说明。
- `git diff --check origin/main..HEAD` 与工作树 `git diff --check`：均无输出、exit 0；`git grep -n -E '^(<<<<<<<|>>>>>>>)'`：无输出、exit 1（无冲突标记）。对 `git diff HEAD~1` 的新增行用 Python 执行所要求的归因正则过滤（等价于两层 grep）：无输出、0 matches。提交后同范围检查结果在最终交付给出，不预写提交后成功。
- 两个修改 task 的 YAML frontmatter 均由 `yaml.safe_load` 解析通过；逐行比较确认旧正文、旧事件及 SNAPSHOT 全部原样保留、顺序未变，原 branch 保留。PRD 逐单元格检查仅 dsh 行 85 状态和 omp 行 37/38 状态变化；描述及 §6 修订日志不变。修改范围恰为六个获授权 Markdown 文件。
- 证据环境：Linux / Node v22.20.0 / npm 10.9.3；基于 `56e43afe6e9b8896ef144fe7b81cd0b394820ff0` 加本轮工作树变更，Evidence Source=developer-local、Source Revision=dirty、Evidence Publication=local-only，不冒充 CI 或提交后 exact SHA 测试。原生 raw 与同 stem 中文汇总：ignored `reports/align-{typecheck,tests,pack,verification}.{txt,md}`；rtk=skipped-for-report。
- BDD=skipped：本轮仅文档事实对齐，没有行为或 feature 变化；既有 t0 等 guard 随全包测试执行，未新增文案测试。Cross-repo context/API Contract=not-needed，新增 Mock Strategy=none；未运行 Web/Mobile E2E、真实宿主安装或线上 tag 链接。Graft skipped：无代码影响，使用文档/manifest/pack 证据，不接线或启动额外服务。

### Release Readiness Review（Align）

- Status: **blocked**（仅既有未解决发布门禁，不再包含命名/打包 A/B 冲突）。
- Production path and affected users / systems：未来 npm 包内的双语 README；本轮无 runtime、API、依赖或发布操作。
- Failure modes and safeguards：U2 与 #119 / R11/R12 已将 `README.zh.md` 随包发布确认为现行要求；本轮真实 pack 103 files 包含该文件，故命名/打包阻塞 cleared。双语无时间敏感发布断言，互链、渲染与原包 suite 通过；既有 lint 11/44 errors 按旧记录保留，未重跑或清除。
- Capacity / backpressure / limits：not-applicable，无运行时变化。
- Observability / alerts / runbook：保留本地 raw 与同 stem 中文报告，无新增遥测。
- Rollout / migration / rollback / cleanup：仅本地 scoped alignment commit；无数据迁移、生产变更或清理，不执行 push、PR 操作、tag、publish。#118 合并及后续发布仍属后续授权，不能由本轮验证替代。
- Required validation and result：typecheck/build exit 0，全包 342/342，pack 与 Markdown smoke 通过；lint 既有阻塞仍在，不标 ready。测试和生产代码未改，无新代码可读性/重构门禁。
- Optional checks / residual risk：CI、线上 tag 链接与真实宿主安装未执行；#119 的 Reviewy 与模型统计按编排方整理回填，不冒充本轮独立复核。TaskStore 既有 schema blocker 不变，不承诺自动恢复。

### npm pack 完整文件清单（entryCount=103）

```text
CHANGELOG.md
CHANGELOG.zh.md
LICENSE
README.md
README.zh.md
cordis.patch.yml
dist/backends/graft.d.ts
dist/backends/graft.d.ts.map
dist/backends/graft.js
dist/backends/graft.js.map
dist/backends/maestro.d.ts
dist/backends/maestro.d.ts.map
dist/backends/maestro.js
dist/backends/maestro.js.map
dist/backends/sbtd-task.d.ts
dist/backends/sbtd-task.d.ts.map
dist/backends/sbtd-task.js
dist/backends/sbtd-task.js.map
dist/commands/sbtd.d.ts
dist/commands/sbtd.d.ts.map
dist/commands/sbtd.js
dist/commands/sbtd.js.map
dist/hooks.d.ts
dist/hooks.d.ts.map
dist/hooks.js
dist/hooks.js.map
dist/host-context.d.ts
dist/host-context.d.ts.map
dist/host-context.js
dist/host-context.js.map
dist/index.d.ts
dist/index.d.ts.map
dist/index.js
dist/index.js.map
dist/section.d.ts
dist/section.d.ts.map
dist/section.js
dist/section.js.map
dist/state.d.ts
dist/state.d.ts.map
dist/state.js
dist/state.js.map
dist/tools/bdd.d.ts
dist/tools/bdd.d.ts.map
dist/tools/bdd.js
dist/tools/bdd.js.map
dist/tools/clarify.d.ts
dist/tools/clarify.d.ts.map
dist/tools/clarify.js
dist/tools/clarify.js.map
dist/tools/e2e.d.ts
dist/tools/e2e.d.ts.map
dist/tools/e2e.js
dist/tools/e2e.js.map
dist/tools/lessons.d.ts
dist/tools/lessons.d.ts.map
dist/tools/lessons.js
dist/tools/lessons.js.map
dist/tools/plan.d.ts
dist/tools/plan.d.ts.map
dist/tools/plan.js
dist/tools/plan.js.map
dist/tools/review.d.ts
dist/tools/review.d.ts.map
dist/tools/review.js
dist/tools/review.js.map
dist/tools/spec.d.ts
dist/tools/spec.d.ts.map
dist/tools/spec.js
dist/tools/spec.js.map
dist/tools/task-artifact.d.ts
dist/tools/task-artifact.d.ts.map
dist/tools/task-artifact.js
dist/tools/task-artifact.js.map
dist/tools/tickets.d.ts
dist/tools/tickets.d.ts.map
dist/tools/tickets.js
dist/tools/tickets.js.map
dist/tools/validate.d.ts
dist/tools/validate.d.ts.map
dist/tools/validate.js
dist/tools/validate.js.map
manuals/book-ddd-distilled-modeling/SKILL.md
manuals/book-ddia-data-design/SKILL.md
manuals/book-legacy-change-safety/SKILL.md
manuals/book-refactoring-pass/SKILL.md
manuals/book-release-readiness/SKILL.md
manuals/domain-modeling/SKILL.md
manuals/grill-me/SKILL.md
manuals/grill-with-docs/SKILL.md
manuals/grilling/SKILL.md
manuals/MANIFEST.json
manuals/sbtd-task/references/handoff.md
manuals/sbtd-task/references/methods.md
manuals/sbtd-task/references/presentation.md
manuals/sbtd-task/references/state.md
manuals/sbtd-task/references/strict.md
manuals/sbtd-task/references/task-data.schema.json
manuals/sbtd-task/references/tooling.md
manuals/sbtd-task/SKILL.md
manuals/to-spec/SKILL.md
manuals/to-tickets/SKILL.md
package.json
```

## #118 合并与 0.2.0-rc.2 发布回填

- 编排方整理：本轮在 docs/omp-sbtd-session-compact-prd 分支按历史回填授权追加；保留原 branch、旧正文、旧事件及旧门禁结论，不调用 TaskStore lifecycle、不写 active pointer、不声称自动恢复通过。
- 编排方整理：#118 squash 为 `548a0bf125e3b3fe1407de11094409e55c2e779e`；本轮 `git show -s --format='%H %cI' 548a0bf` 核对 commit 时间为 `2026-10-23T17:03:31+08:00`。GitHub mergedAt 为 `2026-10-23T17:03:32+08:00`，Reviewy CLEAN @ `40dc46d` 均按编排方整理记录，未在本轮查询 GitHub 或重做 Reviewy。completed_at 采用 mergedAt，不混同 commit 时间。
- 编排方整理：Lord 于 2026-10-23 17:04 +08:00 将 `@kunolu/dsh-sbtd@0.2.0-rc.2` 发布至 dist-tag `next`，随后执行 `npm dist-tag add … latest`；`latest` 与 `next` 均指向 `0.2.0-rc.2`，registry time 为 `2026-10-23T17:08:50+08:00`。发布秒级时刻及 latest 操作的精确时刻未知；registry time 不冒充两项操作时间。
- 编排方整理：tarball 在 main `548a0bf` 的 clean worktree 构建，测试 **342/342**；103 files，含 `README.md` 与 `README.zh.md`；shasum `3e414ff4440cee1e7a1bb59fb58cc1e548912239`。发布由 Lord 执行，token 未写入磁盘或日志。本轮未运行 publish、读取 token、重新查询 registry 或复跑该发布验证。
- 编排方整理：上述已发生的 latest 更新与历史「latest 不动」计划不同，仅追加实际结果，不改写旧计划或补造新的群内裁决。annotated tag、双语 prerelease、在线语言链接核验及既有 lint 门禁如何处置的新增证据未知；不把合并/发布事实冒充本轮 release-ready 审查通过。

## Reviewy 四项记录补正

- 编排方整理：BilingualFacts / ReleaseContracts（主进程 pid 101611）配置为 `kimi-code/k3:max`，实际 thinking 为 high。原因按已核验的 omp 18.12.6 源码结论记录：「配置为 k3:max，主代理 spawn 时传 effort=med，按 omp 优先级覆盖后映射为 high」。`task/executor.ts` 优先级为 caller effort > `:level` suffix > agent default；pi-tui `thinking.ts` 的 `resolveTaskEffortLevel` 把 med 映射到 supported `[low, high, max]` 的中位 high；`task.maxEffort` 仅封顶。本轮未重新核验该宿主源码，不把配置 max 写成实际 max。
- 编排方整理：#119 原 task 第 144 行的 fix1 启动/usage 断言无法核验，已在 `ai/tasks/dsh-sbtd-prd-readme-zh-shipped/task.md` 末尾追加「未知」纠正，不改原行。
- 编排方整理：本 task「Fix2 验证与修正」B3（基线第 104 行）记载的两条旧 backfill 纠正，后来在 merge `56e43af` 被丢弃；不是当前 main 中仍保留的两行。合并选择 main wins，合并后 `ai/tasks/sbtd-changelog-backfill/task.md` 与当时 main 字节一致。来源 `~/.omp/logs/sbtd-rowg-dsh-rc2/pr118-body.v2.md`「Merge choices」第 38–46 行：旧归因目标行已不存在，pid 79530 两位子代理标题成功已包含于 main FINAL。旧 B3 与当时 smoke 记录保留为历史，不回写。
- 编排方整理：四项补正中的第 (d) 项即下方「使用的模型（FINAL，#118）」完整回填；前三条分别对应 (a) effort、(b) #119 未知使用量、(c) merge 56e43af 丢弃 B3 纠正。此处追加对应关系，不改写原标题或前三条。

## 使用的模型（FINAL，#118）

编排方整理：已读取并逐项核对 `~/.omp/logs/sbtd-rowg-dsh-rc2/pr118-body.v2.md` 第 80–114 行；下列 assistant messages / tool calls 及 title-gen 数字与该来源一致，无数字差异。本轮未重数原始 session JSONL；astra 指 `openai-codex/gpt-6-astra:high`。配置 max / 实际 high 的原因由本节上方补正说明。

| run | model | assistant msgs / tool calls |
|---|---|---|
| ping | astra | 1 / 0 |
| main | astra | 39 / 103 |
| BilingualFacts | kimi-code/k3（配置 max，实际 high） | 33 / 54 |
| ReleaseContracts | kimi-code/k3（配置 max，实际 high） | 14 / 19 |
| fix1 | astra | 17 / 41 |
| ping2 | astra | 1 / 0 |
| fix2 | astra | 19 / 52 |
| ping3 | astra | 1 / 0 |
| fix3 | astra | 9 / 19 |
| merge ping | astra | 1 / 0 |
| merge-main | astra | 9 / 20 |
| align ping | astra | 1 / 0 |
| align | astra | 14 / 35 |
| align-fix1 ping | astra | 1 / 0 |
| align-fix1 | astra | 12 / 20 |

| title-gen run | pid | requests | result |
|---|---|---|---|
| ping / ping2 / ping3 / merge ping / align ping / align-fix1 ping | 100933 / 138612 / 147903 / 244747 / 247275 / 255342 | 各 0 | 无标题请求 |
| main | 101611 | main 7 + BilingualFacts 1 + ReleaseContracts 2 | main 无标题；BilingualFacts composer-2.5 success；ReleaseContracts k3-256k success |
| fix1 | 116081 | 7 | 无标题 |
| fix2 | 139153 | 7 | 无标题 |
| fix3 | 148170 | 8 | composer-2.5 success ×1 |
| merge-main | 245555 | 8 | composer-2.5 success ×1 |
| align | 247469 | 7 | 无标题 |
| align-fix1 | 255501 | 7 | 无标题 |

- 编排方整理：title-gen 链为 composer-2.5 → k3-256k → deepseek-flash（401 provider-response-error）→ gpt-6-astra → grok-4.7 → grok-4.6 → gpt-6.1-sol；grok-4.7/4.6 计为 fallback，均未产出标题。不把 title-gen fallback 计为主任务 fallback。
- 编排方整理：无 advisor，无 k3:max main fallback，watchdog 未触发；仅 main 派生上述两位子代理。以上来源为 PR body FINAL，不冒充本轮会话模型统计。

## 发布时刻、tag/prerelease 与 host-compat 回填（2026-10-23）

- 编排方整理：纠正基线第 272 行「17:04 … 发布至 dist-tag next」的完成语气：应为「约 17:04 开始发布」，完成时间按 registry time `2026-10-23T17:08:50+08:00` 记录；不改写旧行，latest 操作精确时刻仍未知。
- 编排方整理（约 17:58 +08:00 已由编排方以 git/gh/curl 核验，本轮不冒充独立线上核验）：Lord 已补建 annotated tag `dsh-sbtd-v0.2.0-rc.2` → `548a0bf125e3b3fe1407de11094409e55c2e779e`，tagger date `2026-10-23T17:55:10+08:00`；双语 prerelease https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2 创建于 `2026-10-23T17:55:10+08:00`、发布于 `2026-10-23T17:55:13+08:00`，prerelease=true，未标 latest；仓库没有 latest release，GET releases/latest = 404。
- 编排方整理：prerelease notes 已明确 tag/prerelease 晚于 npm publish，且该提交的 dsh-host-compat run `39933109206` 两个 REQUIRED 宿主 cell 为红。未重新发布 npm 包；dist-tags `latest=next=0.2.0-rc.2`，registry time 仍为 `2026-10-23T17:08:50+08:00`。
- 编排方整理：约 17:58 +08:00 curl 核验 `https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.md` → 200；`https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.zh.md` → 200。本轮未复跑 curl；这是编排方核验，不是本地 smoke 结果。
- 编排方整理：行 G 历史计划为「先打 tag 再 publish」，实际顺序相反：约 17:04 开始 publish、17:08:50 registry 完成，17:55:10 才打 tag。旧计划保留；上述事实更新基线第 274 行及 PRD row G 中「tag/prerelease/链接核验新增证据未知」的历史快照，不据此宣布旧 lint/host 门禁通过。PRD 状态格只恢复 #120 丢失的 `feat/dsh-sbtd-0.2.0-rc.2-readme` / 本次仅 README/bump 前缀，其余原文保留。

### dsh-host-compat run 39933109206：失败边界与时间差异

- 用户 2026-10-23 17:38 +08:00 群内确认（跑 dsh-host-compat），Lord 记录。
- 编排方整理：该 run 为 workflow_dispatch，main `548a0bf125e3b3fe1407de11094409e55c2e779e`，actor KunoLu，candidateDshVersions advisory `0.2.1-rc.3`。GitHub API 显示 created/started `2026-10-23T17:36:37+08:00`、finished `2026-10-23T17:37:41+08:00`；触发约比记录的 17:38 确认早 1.5 分钟，结束也早于确认。群内确认与触发的精确关系**未知**，不声称按 17:38 确认之后触发。
- 编排方整理：Parse advisory candidate versions success；REQUIRED unit + pack dist/ success；Advisory dsh `0.2.1-rc.3` success。但 `.github/workflows/dsh-host-compat.yml:214` 的 `DSH_PIN_SMOKE: \"0\"` 跳过版本/peer/engines 断言（也跳过 dsh-tools 钉版），其绿色只证明 schema/registration 与前置检查通过，不是 REQUIRED pin smoke 通过。
- 编排方整理：REQUIRED dsh `0.2.0-rc.2` 和 `0.2.1-rc.2`（workflow 第 134 行 `DSH_PIN_SMOKE: \"1\"`）都在 `smoke.mjs:23` 失败：`assert.equal(pluginPkg.version, \"0.1.0-rc.3\")`，actual `0.2.0-rc.2`。本轮已读取 workflow 与脚本核对分支；GitHub 结果按编排方整理，不声称本轮触发或复跑 CI。
- 本轮 git 核对：字面量由 #89 `bbe11789eaf89c3eabad1987f1ff3326d58c09c2` 于 `2026-09-19T08:50:35+08:00` 引入；最后改脚本的是 #97 `155982bf1992463556b06126b74aa275fd6839f9`，`2026-10-19T03:17:27+08:00`；#99 `1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831` 于 `2026-10-19T04:39:44+08:00` bump `0.2.0-rc.1` 后断言即陈旧。核验命令：`git log -S'0.1.0-rc.3' -- .github/workflows/scripts/dsh-host-register-smoke.mjs`、`git log -1 -- ...`、`git show` 对应 commit/manifest。
- 编排方整理：最后 green run `39157727639` 位于 `b9328fa860375a7cfb18cd29aa82faab4455a89f`，PR 分支 `feat/dsh-sbtd-0.2.0-rc.1-pr-c-host`；本轮 git 核对其 commit 时间 `2026-10-19T03:12:05+08:00`、包版本仍 `0.1.0-rc.3`。已发布 `0.2.0-rc.1` 和 `0.2.0-rc.2` 从未通过 REQUIRED host smoke；修复合并后的重新运行将是首个真正检查 0.2.x 插件的 host-compat 结果，成败未知。workflow 仅 workflow_dispatch，PR CI 不运行该门禁，因而未在 bump PR 中暴露。
- 编排方整理：修复与本地断言证据由 [dsh-host-smoke-version-assert](../dsh-host-smoke-version-assert/task.md) 承接；本轮不重新发布、不修宿主适配、不将 assertion-only 检查称为完整 host smoke。
