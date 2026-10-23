---
schema_version: 1
id: dsh-sbtd-prd-readme-zh-shipped
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：本任务采用 strict、唯一 writer、两个本地提交；决策依据为 U2，先完成 PRD-only 对齐。
status: done
branch: docs/prd-dsh-readme-zh-shipped
created_at: '2026-10-23T16:20:38+08:00'
updated_at: '2026-10-23T16:43:53+08:00'
completed_at: '2026-10-23T16:37:30+08:00'
---
# dsh-sbtd 中文 README 命名与随包发布：PRD-only

## 目标 / 范围 / 非目标

- 编排方整理：提交 1 仅回填 `ai/tasks/sbtd-changelog-backfill/task.md` 的 #117 merge、FINAL 模型计数和 commit-1 SHA 纠正；只更新三个 frontmatter 当前值，旧事件与正文 append-only。
- 编排方整理：提交 2 对齐 omp PRD D6/D7、dsh PRD 行 G、grill Q6/Q7 与历史取代注记，追加两条独立修订日志、本 strict 记录及 index 排序一行。
- 编排方整理：只在本 worktree、当前分支写入；基线 `46680a5f6403d9c6032e1dd6a3d2cb49cb2ff842`，入口工作区 clean；不触碰其他 worktree 或 #118 分支。
- 编排方整理：不改代码、README、CHANGELOG、package.json、测试或 feature；不 push、开 PR、comment、tag、publish、merge。#118 代码 PR 在本 PRD 合并后跟进；本轮不操作该 PR。
- 编排方整理：`packages/omp-sbtd/README_zh.md` 尚未改名，改名属于后续版本；不声称已发布的 omp-sbtd 0.2.0-rc.1 包含 `README.zh.md`。仓库根 `README_zh.md` 不在改名范围。
- 未完整调用 grill-with-docs：编排方整理的措辞、历史保留规则与验收明确，无新增领域歧义；修改旧 grill 记录不等于进行新一轮完整 grill。
- 沿用既有 `sbtd-changelog-backfill/task.md` 记录的 TaskStore 全库历史 schema blocker，不重跑确认、不调用 lifecycle、不写 active pointer。本记录是明确要求的共享文档产物，不宣称 TaskStore 或自动恢复通过。现有目标 tracked、新记录未被 ignore，目标及父路径无 symlink；不写本地状态、身份或 handoff。旧任务历史 branch 保留，仅执行编排方整理的历史回填授权，不重绑定。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T16:20:38+08:00 | planned | in-progress | 编排方整理：strict、唯一 writer、两个本地文档提交；范围与历史保留规则明确 | 根、分支、HEAD 与 origin/main 匹配；入口 clean；路径/ignore/tracked 核验通过；时间来自 TZ=Asia/Shanghai date -Is |
| 2026-10-23T16:24:17+08:00 | in-progress | checking | 编排方整理：PRD-only 对齐与历史取代注记完成，交付保持 checking | npm 临时包实测通过；文档解析/渲染、历史保留、归因、索引与允许范围检查通过；git diff --check exit 0；completed_at null |
| 2026-10-23T16:37:30+08:00 | checking | done | 编排方整理：#119 已 squash-merge，PRD-only 任务完成；本轮回填保留历史正文与原 branch | merge 9ad277c35b5e4e61a6f7cb5fd959e6ce3a89de8f；GitHub mergedAt 与 git %cI 均为 2026-10-23T16:37:30+08:00；远端分支已删除；Reviewy CLEAN @ e44f1ee 为编排方整理，非 GitHub review |

## 决策来源

- U1：用户 2026-10-22 22:53 +08:00 群内确认（两个包的中文 README 都命名为 `README.zh.md`），Lord 记录。
- U2：用户 2026-10-23 16:15 +08:00 群内确认（选 B：保留 `README.zh.md` 随包发布，先开 PRD PR 改 D6/row G），Lord 记录。
- 编排方整理：npm 对包根 `README.*` 强制打包，不受 `files` / `.npmignore` 排除；OMP、Researchy、Reviewy 曾独立复现。此三方复现为编排方证据，不冒充本轮实测；本轮复现另记验证证据。

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、领域术语或模型边界变更 | before-dev | not-required |
| book-ddia-data-design | 仅既有 Markdown 文档记录，不改变数据 schema、运行时读写或恢复协议 | before-dev | not-required |
| book-legacy-change-safety | 无生产/测试行为修改；历史原文通过 append-only 比较保护 | before-dev | not-required |
| book-refactoring-pass | 无生产代码编辑 | before-dev | not-required |
| book-release-readiness | 本轮不改变 runtime、部署或发布，不执行发布 | after-validation | not-required |

## 逐行 before → after

以下为相对 origin/main 的完整零上下文 diff：`-` 是原行，`+` 是对应新行；纯新增行的 before 为空。包含两个 PRD 与作为 PRD 一部分的 grill 记录，未省略长行。

```diff
--- before/docs/prd/omp-sbtd-0.2.0-rc.1.md
+++ after/docs/prd/omp-sbtd-0.2.0-rc.1.md
@@ -37,2 +37,2 @@
-| D6 | 插件目录的中文 README 文件名用 `README_zh.md`（同仓库根 `README_zh.md` 先例），不用 `README.zh.md` | locked（用户 2026-10-19） |
-| D7 | grill-r1 Q6 A：zh README 语言切换链接钉 release tag 绝对链接（`blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md`），打 tag 后、publish 前点击核验；`README_zh.md` 不进 npm 包；`package.json` files 与 p0 发布物清单不变，任务 A 字节级 CLEAN 门不受影响 | locked（用户 2026-10-19 11:39） |
+| D6 | 插件目录的中文 README 命名为 `README.zh.md`，随 npm 包发布（npm 强制打包 `README.*`；证据：编排方整理）；英文 `README.md` 保持默认，顶部 EN/中文互相语言切换链接；仓库根 `README_zh.md` 不变 | locked（用户 2026-10-19；README.zh.md 命名见 R11，随包发布见 R12） |
+| D7 | EN/中文 README 顶部互相语言切换链接钉对应 release tag 的绝对链接，打 tag 后、publish 前点击核验；中文 `README.zh.md` 随 npm 包发布（npm 强制打包 `README.*`；证据：编排方整理），取代 grill-r1 Q6 A 的「不进包」前提；旧版任务 A/R 的 files、p0 清单与 CLEAN 验收仅作历史保留，不据此承诺后续版本发布物不变 | locked（用户 2026-10-19 11:39；README.zh.md 命名见 R11，随包发布见 R12） |
@@ -71 +71 @@
-| R | 双语 README（仅根 + omp-sbtd；dsh-sbtd README 不在本 PRD，见 `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G）：更新根 `README.md` 与 `README_zh.md` 到两个插件最新版本；`packages/omp-sbtd/README.md` 改 EN 默认 + 新增 `packages/omp-sbtd/README_zh.md`（D6 命名），两者顶部互相语言切换链接；链接按 D7 钉 `blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md` 绝对链接，`README_zh.md` 不进包，`package.json` files 与 p0 发布物清单不变，任务 A 字节级 CLEAN 门不受影响；兼容说明按 D11 更新（peer `>=18 <19`，17.x 不再支持，实测 18.11.1，截至 2026-10-19 D11 锁定时上游 latest 为 18.12.2） | 6 | done | #109 | 4f8ed3ccdebee7a6f762520be26fbeac3eea6c37 | 2026-10-22T16:22:52+08:00 | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-r-readme/task.md` |
+| R | 双语 README（仅根 + omp-sbtd；dsh-sbtd README 不在本 PRD，见 `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G）：更新根 `README.md` 与 `README_zh.md` 到两个插件最新版本；`packages/omp-sbtd/README.md` 改 EN 默认 + 新增 `packages/omp-sbtd/README_zh.md`（D6 命名），两者顶部互相语言切换链接；链接按 D7 钉 `blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md` 绝对链接，`README_zh.md` 不进包，`package.json` files 与 p0 发布物清单不变，任务 A 字节级 CLEAN 门不受影响；兼容说明按 D11 更新（peer `>=18 <19`，17.x 不再支持，实测 18.11.1，截至 2026-10-19 D11 锁定时上游 latest 为 18.12.2）（编排方整理：本行保留 #109 历史；2026-10-23 R12 起，插件中文 README 规则由 R11 命名 `README.zh.md`、R12 随包发布取代，见 §6；不追改本版发布物） | 6 | done | #109 | 4f8ed3ccdebee7a6f762520be26fbeac3eea6c37 | 2026-10-22T16:22:52+08:00 | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-r-readme/task.md` |
@@ -89 +89 @@
-- **任务 R README**：EN/ZH 内容一一对应；版本钉与宿主钉（`@kunolu/omp-sbtd@0.2.0-rc.1`、peer `>=18 <19`，D11）正确；`npm pack --dry-run` 清单含更新后的 `README.md`（npm 自动收录）且不含 `README_zh.md`（D7：files 与 p0 清单不变）；语言切换链接在任务 E 打 tag 后、publish 前点击核验。
+- **任务 R README**：EN/ZH 内容一一对应；版本钉与宿主钉（`@kunolu/omp-sbtd@0.2.0-rc.1`、peer `>=18 <19`，D11）正确；`npm pack --dry-run` 清单含更新后的 `README.md`（npm 自动收录）且不含 `README_zh.md`（D7：files 与 p0 清单不变）；语言切换链接在任务 E 打 tag 后、publish 前点击核验。（编排方整理：保留本版历史验收；2026-10-23 R12 起的当前规则为 `README.zh.md` 随 npm 包发布，命名见 R11、随包发布见 R12；不追改本版发布物。）
@@ -115,0 +116,2 @@
+| 2026-10-22 | R11 | 用户 2026-10-22 22:53 +08:00 群内确认（两个包的中文 README 都命名为 `README.zh.md`），Lord 记录。编排方整理：取代 D6 原插件目录 `README_zh.md` 命名；根 `README_zh.md` 不在范围内；仅记录命名决定，不与 R12 的随包发布决定合并。 |
+| 2026-10-23 | R12 | 用户 2026-10-23 16:15 +08:00 群内确认（选 B：保留 `README.zh.md` 随包发布，先开 PRD PR 改 D6/row G），Lord 记录。编排方整理：npm 强制打包包根 `README.*`，不受 `files` / `.npmignore` 排除；本轮 npm 10.9.3 临时包复现包含 `README.md`、`README.zh.md`、`index.js`、`package.json`，不含 `README_zh.md`。更新 D6/D7、dsh PRD 行 G；行 R、§4 任务 R 验收与 grill-r1 开头、Q6 题干/选项/推荐、Q7 A、README 切换链接汇总保留历史并追加取代注记。英文 `README.md` 默认与顶部 EN/中文互链、tag 后 publish 前点击核验不变；旧行 E、R1b/R9 的包路径仅作历史，不是当前命名规则。本次 PRD-only，#118 代码 PR 在本 PRD 合并后跟进；`packages/omp-sbtd/README_zh.md` 尚未改名，留待后续版本，不声称已发布 0.2.0-rc.1 包含 `README.zh.md`。 |
--- before/docs/prd/dsh-sbtd-0.2.0-rc.1.md
+++ after/docs/prd/dsh-sbtd-0.2.0-rc.1.md
@@ -85 +85 @@
-| G | dsh-sbtd 双语 README：`packages/dsh-sbtd/README.md` 改 EN 默认 + 新增 `README_zh.md`（`README_zh.md` 命名钉见 omp-sbtd PRD D6），顶部互相语言切换链接（钉 release tag `blob/dsh-sbtd-v0.2.0-rc.2/...` 绝对链接，`README_zh.md` 不进包，链接在打 tag 后、publish 前点击核验）+ 仅文档的 `0.2.0-rc.2` 发布（annotated tag `dsh-sbtd-v0.2.0-rc.2`、双语 prerelease、`npm publish --tag next`、`latest` 不动）；独立 PR、独立 release | 8 | planned（用户 2026-10-19 11:43 确认，Asia/Shanghai；omp-sbtd PRD D13） | — | — | — | `ai/tasks/dsh-sbtd-0-2-0-rc-2-pr-g-readme/task.md` |
+| G | dsh-sbtd 双语 README：`packages/dsh-sbtd/README.md` 改 EN 默认 + 新增 `README.zh.md`（`README.zh.md` 命名钉见 omp-sbtd PRD D6/R11），顶部互相语言切换链接（钉 release tag `blob/dsh-sbtd-v0.2.0-rc.2/...` 绝对链接，`README.zh.md` 随 npm 包发布（npm 强制打包 `README.*`；证据：编排方整理），链接在打 tag 后、publish 前点击核验）+ 仅文档的 `0.2.0-rc.2` 发布（annotated tag `dsh-sbtd-v0.2.0-rc.2`、双语 prerelease、`npm publish --tag next`、`latest` 不动）；独立 PR、独立 release | 8 | planned（用户 2026-10-19 11:43 确认，Asia/Shanghai；omp-sbtd PRD D13；用户 2026-10-23 16:15 +08:00 群内确认（选 B：保留 `README.zh.md` 随包发布），Lord 记录；见 omp-sbtd PRD R12） | — | — | — | `ai/tasks/dsh-sbtd-0-2-0-rc-2-pr-g-readme/task.md` |
--- before/ai/tasks/omp-sbtd-0-2-0-rc-1-prd/grill-r1.md
+++ after/ai/tasks/omp-sbtd-0-2-0-rc-1-prd/grill-r1.md
@@ -5,0 +6,2 @@
+
+> 编排方整理：上段为 2026-10-19 历史锁定；插件中文 README 命名已由 omp PRD §6 R11 改为 `README.zh.md`，2026-10-23 R12 起随 npm 包发布；根 `README_zh.md` 不变。
@@ -76,0 +79,2 @@
+> 编排方整理：Q6 题干及下列 A/B/C/D 选项保留当时历史，不作为当前命名/打包规则。2026-10-23 R12 起采用 `README.zh.md` 随 npm 包发布（npm 强制打包包根 `README.*`，不受 `files` / `.npmignore` 排除）；命名决定见 omp PRD §6 R11，随包发布决定见 R12。此处历史选项 B 不等同 2026-10-23 群内选 B。
+
@@ -82,0 +87,2 @@
+
+> 编排方整理：上述推荐及下列原锁定仅记历史；其「不进包」前提已由 omp PRD §6 R12 取代。英文 `README.md` 默认、顶部 EN/中文互链及 tag 后 publish 前点击核验保持；不追改 omp-sbtd 0.2.0-rc.1 发布物。
@@ -90,0 +97,3 @@
+
+> 编排方整理：Q7 A 保留历史；当前行 G 使用 `README.zh.md` 并随 npm 包发布，命名见 omp PRD §6 R11、随包发布见 R12；独立 PR / docs-only 0.2.0-rc.2 release 与其余门禁不变。
+
@@ -125 +134 @@
-| README 切换链接（D7） | 钉 release tag 的绝对链接（`blob/omp-sbtd-v0.2.0-rc.1/...`），打 tag 后、publish 前点击核验；`README_zh.md` 不进 npm 包，files 与 p0 清单不变 | `blob/main` 漂移链接 / 进包改 files 与 p0 清单 |
+| README 切换链接（D7） | 钉 release tag 的绝对链接（`blob/omp-sbtd-v0.2.0-rc.1/...`），打 tag 后、publish 前点击核验；`README_zh.md` 不进 npm 包，files 与 p0 清单不变（编排方整理：本格及右格保留历史；2026-10-23 R12 起由 `README.zh.md` 随包发布取代，见 omp PRD §6 R11/R12） | `blob/main` 漂移链接 / 进包改 files 与 p0 清单 |
```

### 历史与最小范围判断

- D6/D7 为当前锁定规则、行 G 为 planned，直接更新；行 R、§4 任务 R 验收、grill 汇总只在原文后追加取代说明，没有改写历史命题。Q6 题干/选项/推荐/锁定与 Q7 A 原行逐字保留，用相邻注记覆盖；2026-10-23 的选 B 不是旧 Q6 B。
- 其余搜索命中：omp 行 E 为已完成发布步骤，R1b/R9 为历史日志，保持原文，R12 明确其旧包路径不是当前规则；根 README 引用不改。旧 PRD task.md 的命中属于禁止修改的历史状态事件，保持不变。
- dsh PRD 没有单独决策日志；不新建重复日志，用行 G 的旧确认 + U2 与 omp §6 R11/R12 交叉引用，避免第二套记录。

## 验证证据

- #117：`gh pr view 117 --json mergedAt,mergeCommit,headRefOid,commits` 与 `git log` 核对 merge/head/两提交顺序、两个 commit-1 SHA 的日期和相同 stat。GitHub reviews 为 `[]`，两条评论作者均 chatgpt-codex-connector，其中一条含 usage limit。Reviewy CLEAN 与标题模型链按编排方整理记录，不冒充独立验证。
- `python3 ~/.omp/logs/sbtd-changelog-backfill/count.py <jsonl...>`：ping **1/0**、main **39/75**、OmpHistory **2/78**、DshHistory **3/203**、fix1 **11/23**，全部匹配。标题日志未重读，main/fix1 无 fallback 的路由声明仅按编排方整理记录。
- 提交 1 为 `8b8ad0c`；提交前 `git diff --check` 无输出、exit 0。Python diff 断言删除行恰为三个 frontmatter 当前值，旧正文/事件/SNAPSHOT 与原第 138 行保留。首次检查脚本误用 ndiff 前缀切片 `[1:]` 导致断言失败，改为 `[2:]` 后通过；不是文档失败。
- npm 实测：10.9.3；在 `/tmp` 新临时目录创建 `{"name":"sbtd-readme-pack-probe","version":"1.0.0","files":["index.js"]}`、index.js、三种 README；`.npmignore` 内容为 `README.*` 与 `README_zh.md` 两行。运行 `npm pack --dry-run --json --ignore-scripts --cache <tmp>/cache --userconfig <tmp>/user.npmrc --globalconfig <tmp>/global.npmrc`，两个 npmrc 都为空；exit 0，文件路径排序结果为 `['README.md', 'README.zh.md', 'index.js', 'package.json']`。首次两个配置都用 `/dev/null`，失败 `double-loading config "/dev/null" as "global", previously loaded as "user"`；改用两个独立空配置后通过。临时 fixture/cache/configs 已删除，没有读取或打印凭据。
- 文档 smoke：Python `markdown_it.MarkdownIt('commonmark').enable('table').render(...)` 实际渲染六个 Markdown；`yaml.safe_load` 解析两份 task frontmatter，schema_version 均为整数 1。当前 PRD 精确比较：omp 仅旧行 37/38/71/89 变化及追加 R11/R12，dsh 仅行 85；grill 历史题干/选项/推荐/锁定保留；index 只插入排序一行且所有 task 链接解析到文件。
- 新增行归因禁词检查：对 diff 的新增行用与编排方验收相同的正则搜索，**0 hits**（不在本记录复写模式，避免自匹配）；两份 task 的新增行也覆盖。`git diff --check` 再次 exit 0。
- `git diff --name-only origin/main` 输出五个 tracked 路径：`ai/tasks/index.md`、`ai/tasks/omp-sbtd-0-2-0-rc-1-prd/grill-r1.md`、`ai/tasks/sbtd-changelog-backfill/task.md`、`docs/prd/dsh-sbtd-0.2.0-rc.1.md`、`docs/prd/omp-sbtd-0.2.0-rc.1.md`；另用 `git ls-files --others --exclude-standard` 得到唯一未跟踪的新 task。联合范围恰为六个允许路径；提交后最终 SHA、两提交顺序与 clean tree 在交付对话报告，不提前宣称。

## 跳过 / 剩余风险 / 恢复边界

- 已读取 project-validation；rtk not-needed：本轮使用编排方要求的原生 Git 命令和一次性内存文档检查。没有改生产代码，ponytail、生产代码可读性复核、独立代码 review、BDD/feature、单元/集成/E2E、lint/build/typecheck 与 runtime smoke 均 not-required / skipped；不声称 CI 或正式 runner 通过。npm 临时包实验是打包规则实测，不是两个真实包的 release 验收。
- Graft skipped：无代码影响且不需要图证据，不启动/配置。Cross-repo context / API Contract not-needed；Mock Strategy none；Evidence Source developer-local；提交前 Source Revision dirty；Evidence Publication local-only；正式测试报告及同 stem 中文伴本 not-needed，本任务保留实际命令、失败与通过证据。
- 无新领域歧义或生产接口变化，Book Gates 全部 not-required；既有 grill 历史不构成本轮完整 grill。未执行远端写操作，未改其他 worktree。
- 编排方整理：本次只交付 PRD，任务停 checking / completed_at null；#118 实现与后续发布仍须独立验证。omp-sbtd 包 README 改名尚未执行，留待后续版本；不追改已发布包，不保证新文件在旧 release tag 上存在。
- 恢复边界：两个本地 docs-only 提交及共享 task 记录；未操作 TaskStore lifecycle、active pointer、handoff 或身份，不承诺自动恢复；无生产回滚动作。

## 使用的模型（SNAPSHOT）

只读采集于 2026-10-23T16:24:17+08:00；按 `type=message`、`message.role=assistant` 及其 content 的 `toolCall` 项计数。该 SNAPSHOT 不含之后的记录、提交与交付；FINAL 由编排方后续填写。

| session | provider/model | assistant msgs / tool calls | 用途 |
|---|---|---|---|
| `01a167d8-3147-710b-8688-a042a28b4047` | openai-codex/gpt-6-astra | SNAPSHOT **18 / 35** | 唯一 writer / 验证 controller |

- 日志：`~/.omp/logs/sbtd-prd-readme-zh/sessions/main/2026-10-23T08-19-44-071Z_01a167d8-3147-710b-8688-a042a28b4047.jsonl`；模型字段实测为 openai-codex/gpt-6-astra。thinking/fallback/title-gen 本轮未统计，不补造；未调用子代理。

## #119 合并回填

- 编排方整理：`gh pr view 119 --json state,mergedAt,mergeCommit,headRefOid` 实测 state=MERGED，mergeCommit=`9ad277c35b5e4e61a6f7cb5fd959e6ce3a89de8f`，headRefOid=`e44f1eebad669277f8d8e4203e298eba6bcbfb4f`，mergedAt=`2026-10-23T08:37:30Z`（同一时刻为 `2026-10-23T16:37:30+08:00`）；`git log -1 --format='%H %cI' 9ad277c` 返回该 merge SHA 与 `2026-10-23T16:37:30+08:00`。
- 编排方整理：`gh pr view 119 --json headRefName` 确认远端分支名 `docs/prd-dsh-readme-zh-shipped`；`git ls-remote --heads origin docs/prd-dsh-readme-zh-shipped` 无输出、exit 0，确认该远端分支已删除。Reviewy CLEAN @ `e44f1ee` 按编排方整理回填，不是 GitHub review，未声称本轮重做 Reviewy。
- 编排方整理：本轮在 #118 分支做明确授权的历史回填，保留原 branch 与旧正文/SNAPSHOT；仅更新 status/updated_at/completed_at 并追加事件/证据，不操作 TaskStore lifecycle 或 active pointer。PRD-only 完成不等于 #118 合并、omp README 改名或 npm 发布。

## 使用的模型（FINAL）

编排方整理：以下为最终使用量回填，非本轮重新计数；原 SNAPSHOT 保持原样。

| run | session | model | assistant msgs / tool calls |
|---|---|---|---|
| ping | `01a167d6-ff82-7392-a878-b730ad470c65` | openai-codex/gpt-6-astra:high (`--no-tools`) | 1 / 0 |
| main | `01a167d8-3147-710b-8688-a042a28b4047` | openai-codex/gpt-6-astra:high | 27 / 46 (SNAPSHOT 18 / 35) |

- 编排方整理：无 subagents，无 fallback model；fix1 在启动前中止，usage=0。此处主任务模型路由与下列 title-gen fallback 分开统计。
- 编排方整理：title-gen 日志 `~/.omp/logs/omp.2026-10-23.<pid>.log`：pid 224808（ping）0 requests；pid 225930（main）8 requests，先 composer-2.5 success ×1，再经历未产出标题的 7-model chain：composer-2.5 → kimi-code/k3-256k → deepseek-flash（401 provider-response-error）→ gpt-6-astra → grok-4.7 → grok-4.6 → gpt-6.1-sol；grok-4.7/4.6 计为 fallback。不把标题生成统计当主任务模型计数，也不冒充本轮日志复核。
