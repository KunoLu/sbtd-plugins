---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd-d11-dated
workflow_mode: strict
mode_source: user
mode_note: 用户明确要求 strict（PRD 规则：每个任务都用 strict）；step 1 PRD-only 修订包括 D11 日期措辞及用户 17:01 追加的 D9 文件数注释
status: "done"
branch: docs/omp-sbtd-0.2.0-rc.1-d11-d9-wording
created_at: '2026-10-22T17:00:26+08:00'
updated_at: '2026-10-22T17:11:09+08:00'
completed_at: '2026-10-22T17:11:09+08:00'
---
# omp-sbtd 0.2.0-rc.1 PRD R8/R9：D11 日期措辞与 D9 文件数注释

## 目标

按用户 2026-10-22 16:57 Asia/Shanghai（+08:00）决定（采纳 Reviewy 建议，由 Lord 在 SBTD Plugins room 转达），将 D11 的上游 latest 陈述限定为 2026-10-19 D11 锁定时的历史事实；实测版本 18.11.1、peer `>=18 <19`、devDep 精确钉与全部支持结论不变。

追加用户 2026-10-22 17:01 Asia/Shanghai（+08:00）决定：在同一 PRD PR 中将 D9 文件数澄清为「八个模板文件（另含 LICENSE、NOTICE）」/ "eight template files (plus LICENSE and NOTICE)"；仅注释计数口径，模板内容不变（SKILL.md + 7 个 references 文件 + LICENSE + NOTICE = 10 个文件）。

## 范围

- `docs/prd/omp-sbtd-0.2.0-rc.1.md`：D11 行（含决定时间）、行 D、行 R 兼容说明、§4 任务 D 条目及 §6 R8 修订日志。
- 本 strict 任务记录与 `ai/tasks/index.md` 中排序插入的一行。
- D11 部分已由 orchestrator 提交为 `c846f32`，不 amend；本轮仅修改 PRD 的 D9 行、D14 交叉引用、追加 R9，以及本任务记录。`ai/tasks/index.md` 不再修改。

## 非目标

- R8 当时的 D9「八文件」不变是 Lord 的默认处理，非用户决定；17:01 新决定仅取代此措辞限制，R8 日志原文保留。L20 现状 baseline（observed snapshot）、标题状态行、D11 措辞、任务表状态/PR/SHA/done 时间列及其他行不改。
- 除本 PR 自己的任务记录外，既有 task.md、grill 与任务历史不改；不创建或编辑 `.omp-r12b-addendum.txt`、`ai/tasks/codex-verify/`。
- 不改 README、CHANGELOG、SBOM、package.json/lockfiles、packages 代码或 workflows；CHANGELOG/README/SBOM 同步留给单独的后续 step-2 PR。
- 不 commit、push、开 PR、tag、publish；不触碰其他 checkout、全局配置或工作区外文件；不改 `.sbtd/active-task.json`。

## 证据

- 用户决定：2026-10-22 16:57 Asia/Shanghai（+08:00），Reviewy 建议、Lord 转达；精确 EN/ZH 文本以本次指令为准。
- 已先读 `ai/tasks/omp-sbtd-0-2-0-rc-1-prd-r7-p0-v4/task.md`，执行 `git show --stat c041b2c` 核对 PRD-only 先例；本次不沿用其修改历史任务的范围。
- 入口 `git rev-parse --show-toplevel --abbrev-ref HEAD`：根与授权分支匹配；`git status --short` 初始无输出；HEAD 与 origin/main 均为 `4f8ed3ccdebee7a6f762520be26fbeac3eea6c37`（基线而非本次完成证据）。
- 已检查目标父目录为正常目录、现有文件为普通文件，新任务路径不存在且未被 ignore；索引为 tracked 普通文件。本次仅写明确授权的共享记录，不写本地接线。
- 时间取自 `TZ=Asia/Shanghai date -Iseconds`；验收证据为当前 working-tree diffs，不引用本次不存在的提交。
- 未完整调用 grill-with-docs：用户已给出精确措辞、位置与不变量，无需重复需求澄清。

### R8 验证结果（当时的 working-tree diffs，developer-local）

以下保留 D11 阶段原始验收证据；该阶段随后由 orchestrator 提交为 `c846f32d469a76e4332cfd95b18d2b014cbb57fe`。下列三文件状态描述属于提交前，不代表本轮 D9 的工作树；不是 CI 或已发布 PR head 的证明：

| 命令 / 检查 | 实际结果 |
|---|---|
| `grep -cF 'upstream latest is 18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 0；exit 1 为预期无匹配 |
| `grep -cF '实测过，上游最新是 18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 0；exit 1 为预期无匹配 |
| `grep -cF 'No longer supports omp 17.x; tested only on 18.11.1; as of the D11 lock on 2026-10-19, upstream latest was 18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 3；exit 0；D11、行 D、§4，完整引文无末尾句点 |
| `grep -cF '不再支持 omp 17.x；只在 18.11.1 上实测过；截至 2026-10-19 D11 锁定时，上游最新是 18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 3；exit 0；D11、行 D、§4 |
| `grep -n '18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | L20、42、70、71、84、111；R8 在 L111 另记双语日期分句，L20 baseline 未改 |
| `git diff --check` | 无输出，exit 0 |
| `git status --short --untracked-files=all` | 仅两个 modified：PRD、index；一个 untracked：本 task.md；无其他变更 |
| `git diff --stat` | `ai/tasks/index.md`：1 +；PRD：9 +++++----；合计 2 files changed, 6 insertions(+), 4 deletions(-)；未跟踪的新 task.md 不计入此命令，未暂存或提交以改变统计 |
| `git diff --quiet -- ai/tasks/omp-sbtd-0-2-0-rc-1-prd ai/tasks/omp-sbtd-0-2-0-rc-1-pr-d-changelog ai/tasks/omp-sbtd-0-2-0-rc-1-pr-r-readme` | 无输出，exit 0；指定历史文件未改 |
| 内存 Python 精确比较（读取 `git show HEAD:<path>` 与当前文件，不落地脚本） | PASS：PRD 原内容仅四个指定行替换，末尾仅追加 R8；其余字节全部保留，另断言 L3/L20/D9 与行 D/R 元数据相等；索引恰好插入一行，位于 prd 与 prd-r7-p0-v4 之间 |

- 已读取 `project-validation`；rtk：not-needed，本次按指定 native 命令保留直接计数与退出码。
- Biome：skipped；本地 `node_modules/.bin/biome` 不存在；`biome.json` 的 includes 仅覆盖 packages、package.json、tsconfig.base.json，不覆盖 docs/prd 或 ai/tasks，故本次 Markdown 不在 Biome lint 范围，未运行可选命令或安装依赖。
- BDD、单元测试、build/typecheck、integration/API/E2E、运行时 smoke：skipped（仅 PRD 日期措辞，无代码或运行行为变化）；无新增 `.feature` 或持久测试。实际文档验收由上述命令与精确比较覆盖。
- 独立评审、生产代码可读性复核与 Graft：not-required / skipped（无生产代码、全局配置、持久迁移、跨服务契约或三处既有子系统变更）。
- Cross-repo context、API Contract：not-needed；Mock Strategy：none；Evidence Source：developer-local；Source Revision：dirty；Evidence Publication：local-only；正式测试报告与中文报告伴本：not-needed（本次为文档检查，证据直接记录在此）。
- 剩余边界：CHANGELOG/README/SBOM 尚未同步，明确属于后续 step-2 PR；本任务不代表实现、部署或发布完成。所有修改保留在这三个未提交文件中，无其他 checkout 或全局恢复操作。

### R9 磁盘清单与验证结果（working-tree diffs，developer-local）

本轮入口 HEAD 为 `c846f32d469a76e4332cfd95b18d2b014cbb57fe`，同一授权分支，初始 `git status --short` 无输出。D11 提交不 amend；以下证据对应其后的 D9 未提交修改，不使用 R8 的旧结果代替本轮验证。

修改前先通过文件 glob 定位并列出四份模板；内存 Python 使用 `Path.rglob`、`lstat` 与 SHA-256 核验，未创建脚本文件。四份目录均为 10 个正常文件（SKILL.md + 7 个 references 文件 + LICENSE + NOTICE），相对路径清单完全相同；修改后再次比较 40 个文件的 SHA-256，全部不变。

| 副本 | 实际目录 | 文件数 |
|---|---|---|
| kit | `packages/omp-sbtd/kit/onboard/runtime/templates/skills/sbtd-task` | 10 |
| generated | `packages/omp-sbtd/upstream/generated/onboard/runtime/templates/skills/sbtd-task` | 10 |
| generated-omp | `packages/omp-sbtd/upstream/generated-omp/onboard/runtime/templates/skills/sbtd-task` | 10 |
| vendor | `packages/omp-sbtd/upstream/vendor/sbtd-workflow-kit-upstream/sbtd-workflow-onboard/templates/skills/sbtd-task` | 10 |

上述每份目录的完整排序清单：

```text
LICENSE
NOTICE
SKILL.md
references/handoff.md
references/methods.md
references/presentation.md
references/state.md
references/strict.md
references/task-data.schema.json
references/tooling.md
```

| 命令 / 检查 | 本轮实际结果 |
|---|---|
| PRD 修改前搜索 `8 文件`、`八文件`、`8 个文件`、`八个文件`（grep 工具） | 仅 L40 D9、L45 D14 与 L111 R8；仅前两处为待注释计数，R8 是保留的历史记录 |
| `grep -cF '八个模板文件（另含 LICENSE、NOTICE）' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 3，exit 0：L40 D9、L45 D14、L112 R9 |
| `grep -nE '8 文件' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 0 hits，exit 1 为预期无匹配 |
| `grep -cF 'upstream latest is 18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 0，exit 1 为预期无匹配 |
| `grep -cF '实测过，上游最新是 18.12.2' docs/prd/omp-sbtd-0.2.0-rc.1.md` | 0，exit 1 为预期无匹配 |
| 对完整新 EN/ZH 分别执行 `grep -cF`（同上 R8 表中的两条完整命令，本轮重新执行） | 各 3，均 exit 0；D11 措辞不变 |
| `git diff --check` | 无输出，exit 0 |
| `git status --short` | 仅 PRD 与本 task.md 两个 modified 文件 |
| `git diff --quiet c846f32 -- ai/tasks/index.md ai/tasks/omp-sbtd-0-2-0-rc-1-prd ai/tasks/omp-sbtd-0-2-0-rc-1-pr-d-changelog ai/tasks/omp-sbtd-0-2-0-rc-1-pr-r-readme` | 无输出，exit 0；索引与指定历史未改 |
| 内存 Python 与 `git show c846f32:docs/prd/omp-sbtd-0.2.0-rc.1.md` 精确比较 | PASS：仅 D9 指定措辞/状态、D14 指定措辞和末尾 R9 新行；包括 R8、L20、D11、D14 状态在内，其余字节全部保留 |

只读搜索确认 step-2 的计数同步点为 `packages/omp-sbtd/CHANGELOG.md:18`、`CHANGELOG.zh.md:16`、`README.md:69`、`README_zh.md:66`；根 `README.md`、`README_zh.md` 无此计数，均未修改。

rtk：not-needed（指定 native 验证）；BDD、代码测试、build/typecheck、运行时 smoke、Biome：skipped（docs-only 注释，无代码或模板内容变更；沿用 R8 已核实的 Markdown lint 范围限制）。本轮未完整 grill：用户已给出精确措辞和边界；Book Gates 仍全部 not-required。Evidence Source：developer-local；Source Revision：dirty；Evidence Publication：local-only。未 commit/push/开 PR/tag/publish；剩余同步仅属于独立 step-2 PR，不将本文档完成视为发布完成。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 仅日期措辞与文件数注释修订，无领域模型歧义，本次未完整 grill | R8/R9 | not-required（docs-only） |
| book-ddia-data-design | 无 schema、迁移、缓存或跨服务数据设计变更 | R8/R9 | not-required（docs-only） |
| book-legacy-change-safety | 不改代码行为或模板内容 | R8/R9 | not-required（docs-only） |
| book-refactoring-pass | 不改生产代码 | R8/R9 | not-required（docs-only） |
| book-release-readiness | 不发布、不改 runtime 或部署行为 | R8/R9 | not-required（docs-only） |

## 验收

- 旧 EN/ZH 无日期措辞各 0 处；完整新 EN/ZH 各 3 处（D11、行 D、§4）；R8 另记双语日期分句。
- 行 R 仅兼容说明加日期，D11 状态追加用户决定时间；R8 记录全部边界与 step-2 分离。
- R8 验收：L20、D9、标题状态、任务表其他列与既有历史逐字节保留，变更为原先授权的三个文件；证据见 `c846f32`。R9 追加后仅允许 D9 指定注释与状态时间、D14 指定注释及 R9 新行，其余 PRD 字节保持不变。
- `git diff --check` 无错误；指定历史目录 `git diff --quiet` 返回 0；记录 `git diff --stat` 与未跟踪新任务的区别。
- R9：四份 sbtd-task 模板目录各 10 个文件；新中文计数注释在 PRD 恰有 3 处（D9、D14、R9），旧 `8 文件` 无匹配；D11 旧 EN/ZH 各 0，新 EN/ZH 各 3。
- R9：仅 PRD 与本任务记录有 working-tree diff；索引、指定历史目录及模板/代码/README/CHANGELOG/SBOM 不变，R8 原文保留；R9 明确 step-2 同步四处包内文档计数，根 README 无此计数。

## 进度

- [x] 核对根、分支、基线、先例与路径安全，保存 strict 模式。
- [x] 更新 PRD 五处与排序索引。
- [x] 执行指定验证并记录 working-tree diff 证据。
- [x] 本任务转 done。
- [x] R9：核对四份模板清单、更新 D9/D14 并追加 R9，验证范围与 D11 不变量。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T17:00:26+08:00 | planned | in-progress | 按用户明确 strict 要求执行 D11 日期措辞的 PRD-only step 1 | 用户 2026-10-22 16:57 +08:00 决定；初始工作区干净、分支与基线匹配；R7 记录与 git show --stat c041b2c 先例 |
| 2026-10-22T17:04:38+08:00 | in-progress | done | D11 双语 Breaking 与行 R 兼容说明加日期，追加 R8；支持结论、D9、L20、标题状态及任务表状态列不变；仅完成 PRD-only step 1 | working-tree diffs：旧 EN/ZH 计数 0/0，新 EN/ZH 3/3；git diff --check exit 0；指定历史目录 git diff --quiet exit 0；git diff --stat 为两个 tracked 文件 +6/-4，另有本 untracked task.md；精确比较通过；未 commit/push/开 PR/tag/publish |
| 2026-10-22T17:07:41+08:00 | done | in-progress | 按用户本次明确要求重开同一任务，纳入 2026-10-22 17:01 Asia/Shanghai（+08:00）的 D9 文件数注释决定；保留 D11 完成历史 | D11 已由 orchestrator 提交 c846f32；入口分支匹配、HEAD 为 c846f32、工作区干净；四份模板目录各 10 个正常文件，内容不改；本轮仅授权 PRD 与本 task.md |
| 2026-10-22T17:11:09+08:00 | in-progress | done | D9 文件数注释与 D14 交叉引用完成，追加 R9；仅措辞取代 R8 的 D9 不变说明，模板内容与 D11 均不改 | 四份模板各 10 个文件、40 个文件 SHA-256 不变；新注释计数 3，旧 8 文件 0；D11 旧 EN/ZH 0/0、新 EN/ZH 3/3；git diff --check exit 0；相对 c846f32 的索引/指定历史 git diff --quiet exit 0；working-tree diff 仅 PRD 与本 task.md，精确范围比较 PASS |
