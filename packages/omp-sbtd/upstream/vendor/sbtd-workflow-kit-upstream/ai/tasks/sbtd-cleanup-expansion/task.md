---
schema_version: 1
id: sbtd-cleanup-expansion
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择 strict；新 feature 分支 sbtd-cleanup-expansion 开发
status: "done"
branch: sbtd-cleanup-expansion
created_at: '2026-10-01T17:43:32.962083+08:00'
updated_at: "2026-10-02T10:51:00.414208+08:00"
completed_at: "2026-10-02T10:51:00.414208+08:00"
---
# 目标

扩展 2.0 迁移后的旧资产清理：

1. migration 成功后主动询问用户是否清理并列出将清理的内容；确认则直接执行；拒绝则告知后续可用「sbtd cleanup」「清理工作流」或同向意图提示词再次触发。
2. 清理范围在现有 `.trellis` 与全局 `trellis-workflow`/`trellis-channel` 之上，增加项目内 `.gitnexus/` 目录，以及 codex/claude/kimi/omp 四个 host 全局配置中已配置的 gitnexus MCP 条目（按检测到的实际配置路径逐项检查确认）。`.trellis` 删除方式用户裁决用项目根终端 `tl uninstall` 实际执行。另增：项目根 `AGENTS.md` 中精确成对的 `<!-- TRELLIS:START -->`/`<!-- TRELLIS:END -->` 与 `<!-- gitnexus:start -->`/`<!-- gitnexus:end -->` 标记块（含块内文案）删除，块外内容逐字节保留；2.0 的 `<!-- graft:start/end -->` 围栏不动。
3. 清理不得要求迁移前版本恰好为 v1.0.15；按身份（SKILL.md frontmatter / 目录事实）而非固定校验值识别 1.0.x 各版本。

## 范围

- 仓库 `640-skills` 内 `sbtd-workflow-onboard/`（scripts、SKILL.md、REFERENCE.md、模板、测试）与必要的 README/CHANGELOG/prompt 评估。
- 不动 live HOME、不执行真实迁移或真实清理；验证用隔离环境。

## 边界

- 未完整调用 grill-with-docs：需求与清理边界已由用户明确选择；无额外领域歧义。DDD 的另一触发（领域/上下文歧义）亦不成立；不能仅凭“未完整 grill”豁免该触发。
- Book Gate Plan 见正文 Gate 表；`.feature` 依仓库规则不生成，行为规范落在本任务与设计文档。

## 用户裁决（2026-10-01，strict 任务内）

| 决策点 | 裁决 | 设计后果 |
|---|---|---|
| `.trellis` 删除方式 | 坚持 `tl uninstall` 实际执行 | 项目根运行真实 vendor 命令；预先计划并备份 `.trellis`、平台文件及配置的全部可变更范围。缺 CLI/manifest 时阻断；非零退出可能部分写入，必须记录逐资源实际结果、保留备份，不回退直删 |
| 延迟清理（「sbtd cleanup」） | 批次证据优先，缺证据新鲜检测兜底 | 同一检测/执行引擎两条入口：有保留批次证据走 `migration --phase cleanup --confirm-cleanup <verification_id>`；证据缺失/过保留期走新鲜检测+逐项展示+一次确认 |
| `AGENTS.md` 旧标记块 | 新增清理项（用户 2026-10-01 补充，示例 `/Users/lusonglin/github/keyboy-play/AGENTS.md`） | 精确匹配一对 `TRELLIS:START/END`（大写）与一对 `gitnexus:start/end`（小写）；删除唯一有序对及块内文案；零对=非候选；重复/交错/残缺=blocked 列出人工裁决；`graft:start/end` 及其他内容逐字节保留 |
| GitNexus 确认粒度 | 一次确认覆盖展示的全部候选 | 计划列出每个检测到的 host 条目与项目 `.gitnexus`；确认一次全部执行；只删 gitnexus 条目，同文件其他 MCP server 保留 |

已定边界：GitNexus npm 包与 `~/.gitnexus` 全局数据不动；「主动询问」为 Skill/Agent 行为（SKILL.md/REFERENCE/模板路由），migration CLI 保持单 JSON 契约；SKILL/REFERENCE/README 中 GitNexus「untouched」政策改为「仅经确认的 cleanup 删除」；1.0.x 身份识别=非 symlink 目录 + `SKILL.md` frontmatter `name` 匹配（LESSON-20260811-external-skill-legacy-identity 标准），不再要求 v1.0.15 校验值。

## Book Gate Plan

| Gate | 客观触发 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill-with-docs；需求由用户三条明确给出，领域词无歧义 | before-dev | not-needed（完整 grill 后强制条件未发生） |
| book-ddia-data-design | 逻辑 Skills 根授权与成功 vendor 后态/原件的重试消费 | before-dev | confirmed：逻辑根不得被物理 HOME 合并吞掉；仅成功且与封存预期一致的 vendor 结果能推动待处理资源当前态，原件不覆盖 |
| book-legacy-change-safety | 4 项已确认审查缺陷；删除/重试高风险 | before-dev | characterized：按审查路径作为问题事实；维持确认、身份、备份、漂移与失败调和门，新增对应隔离回归 |
| book-refactoring-pass | 既有迁移及卸载模块的定点修正 | before-dev | proceed：只改负责逻辑根、缺失路径复验、续作状态消费和授权减项的最窄层，不夹带无关重构 |
| TDD / 回归 | R1 越界重封、R2 备份期间出现缺失路径、R3 成功副作用后续作、R4 授权减项 | 实现/验证 | passed：本轮定点 458 tests / 1 skipped；最终全量 1367 tests / 8 skipped / exit 0；新增边界与对抗输入用例均包含在当前验证树 |
| ponytail + source/LSP/contract 影响分析 | 持久契约与跨资源重试 | check | passed：保留必要范围/状态 seam，无新服务或命令框架；源码/契约核对完成，LSP 未配置而非伪称通过 |
| 独立 review | 持久迁移、全局配置、授权边界 | check | passed：ReviewFixedMissingPaths、ReviewFixedConsent、ReviewFixedSkillRoot、ReviewFixedVendorRetry 的有效问题修复后独立复核关闭 |
| book-release-readiness | 迁移行为修复 | 最终验证后 | ready：仅仓库修复交付；本轮 sbtd-cleanup-review-fixes-izegevn_/full-1 为证据，未沿用重开前通过记录，不等于全局部署/同步/发布 |

## 验收

1. migration verify 为 verified 后，Skill 路由层主动询问是否清理并列出实际检测到的候选清单；确认则执行，拒绝则回复后续可用「sbtd cleanup」「清理工作流」或同向意图提示词触发。
2. 清理候选覆盖：项目 `.trellis`（经 `tl uninstall`）、全局 `trellis-workflow`/`trellis-channel`（身份识别后整目录删除）、项目 `.gitnexus/`、四个 host 检测到的 gitnexus MCP 条目；未检测到的项不出现在清单。
3. 迁移前版本为任意 1.0.x（校验值与 v1.0.15 不同）时，身份识别仍允许清理；身份不匹配（用户自维护同名目录）仍 blocked 保留。
4. `tl uninstall` 前置条件不足时不执行；运行失败可能部分写入，必须记录实际 before/after、备份、非零状态，不能宣称“失败=没有改动”。执行前备份全部卸载范围而不只是 `.trellis`。
5. GitNexus 条目删除只移除 gitnexus 键/表，同文件其他 server 数据不动：TOML 经 tomlkit 保格式往返，JSON 按既有 MCP 写入约定规范化重排（与 sbtd_codex_wiring/install.sh 同约定）；一次确认覆盖清单全部候选。
6. 「sbtd cleanup」提示词路由：有批次证据走批次 cleanup；无证据走新鲜检测兜底，两者同一确认与备份语义。
7. `AGENTS.md` 标记块删除仅移除 `TRELLIS`/`gitnexus` 两类唯一有序对及块内文案；块外（含 `graft` 围栏与项目自有内容）逐字节保留；残缺/重复标记 blocked 不猜。
8. 全程不动 live HOME；隔离环境证明检测、确认、删除、失败保留四条路径。

## DDIA 补充复核

- `AGENTS.md` 是新增持久写入路径：只接受两类独立唯一有序对；残缺、重复、嵌套阻断。删除前备份完整原文；按字节切除目标标记行及块内内容，块外空行、项目规则、Graft 围栏不动。
- `tl uninstall` 可能先修改同一 AGENTS：先备份全部候选，再核对 vendor 计划中的预期状态，最后基于原文完成两类旧标记删除；不把新状态当成无条件授权。
- fresh plan 的 hash 只绑定展示内容，不是身份鉴权；执行前重新检测候选类型、根、Skill 身份、配置形状与 before 状态。重算 hash 后的任意目标替换仍拒绝。
- 独立 fresh plan/receipt 使用独立版本与验证，不伪装 `onboard-contracts.schema.json` 的 migration 文档。缺批次证据可以 fresh plan；已知批次冲突/失败不得靠 fallback 绕过。
- 状态：confirmed（上述保留语义明确，最终执行安全仍以测试及独立复核为准）。

## 此前验证与交付边界（重开前历史）

- 原生全量命令：`python -B -m unittest discover -s tests -p 'test_*.py' -v`；最终 full-5：**1347 tests，OK (skipped=8)，exit 0**。原有模板边界契约保留，普通非零失败与外部部分失败的 private evidence/backup 引用均有回归。
- 跳过：5 个需 `SBTD_P115_HOST=1` 的真实宿主用例、2 个 Native Windows ACL/junction 用例、1 个大小写敏感文件系统用例。macOS PowerShell 实测不替代 Native Windows。
- 真实隔离场景：fresh CLI plan/拒绝/确认/重试；实际 `tl uninstall`；四 host MCP 清理；两类 AGENTS 标记块及 Graft/块外保留；Bash 和 macOS PowerShell 显式 source-root 转发；10 个资源的私有备份恢复。
- batch cleanup 接真实 vendor 的 smoke 通过，但部署报告来自 contract fixture，不冒充真实业务全链迁移。fresh 回执仍不输入旧 recovery CLI；备份已证明可用既有受管文件恢复 primitive 恢复。
- 静态检查：scripts/tests compileall、Bash syntax、新 cleanup 模块/测试 ruff、新三个模块 ty 均通过。`rtk: skipped-for-report`；BDD traceable 至设计 §4 与上述 Python 用例，本仓不新增 `.feature`。Cross-repo context / API Contract / Web-Mobile tool gates：not-needed。
- 私有证据目录逻辑名：`sbtd-cleanup-expansion-ajno8aj7`；入口 `delivery.md`，最终 `full-5.{txt,json,md}`，源码字节绑定 `final-tested-source.json`。失败与取消轮次保留。full-3 仅为缺少完整契约时的诊断通过，不作为最终验收。
- Source ref：`sbtd-cleanup-expansion`；基线 SHA：`229c75ceab1f40773aa9cb24d48f48caf9dfd1d0`；Source Revision：dirty；Evidence Source：developer-local；Evidence Publication：local-only。
- README.md、README.html 均更新清理能力/范围；版本化 automation prompt 更新只读检查范围与清理安全条件；CHANGELOG 在未发布章节记录变更。ENTRYPOINT 版本、live automation、本机生效 HOME/Skills 未改。
- 旧 in-flight 密封批次仍需原运行时或独立授权的签名转换；不绕过 lineage，不修改签名资产。不自动卸载 npm CLI、删除全局 GitNexus 数据、备份、未知身份或不支持的 vendor 资源。
- 未 commit/push、未创建 tag、未 sync、未对真实用户项目执行 cleanup；不关闭 P3-01 观察窗口。

## 第一轮审核修复（已完成历史）

用户要求本轮修复全部 4 项，不延期 P2；仍为 strict、同一 feature 分支。源实现/测试由各自唯一 writer 维护，最终验证由主会话统一控制。

1. **R1 / P1**：封存实际 Skills 根的独立逻辑范围并贯穿根合并，退役目标必须是其直接子目录；不恢复 v1.0.15 校验值限制，不以 ambient HOME/环境重新解释旧证据。
2. **R2 / P2**：备份结束后启动 vendor 之前复验原先缺失的受管路径仍不存在；出现文件/目录/链接时保留并阻断，避免长备份窗口漏检。
3. **R3 / P2**：只从已成功且与封存预期及备份一致的 vendor 结果派生待处理资源当前态；续作复用原件、处理剩余标记，不重放成功卸载；失败 vendor、伪造后态与用户改动仍阻断。
4. **R4 / P2**：同一已确认流程内，目标/效果不变，或只减少有绑定回执证明已完成的项且其余目标/效果不变时免再次确认；新目标/新效果仍确认，未知消失先调和，永远使用当前 plan_id。

本轮行为规范见设计 §5；不新建 `.feature`。只进行隔离运行，无真实 HOME/项目清理、sync、签名迁移或发布授权。

### 本轮结果与证据

- 全部 4 项修复完成。R1 新增 covering shared_root 的可选 `skills_root`；物理独立 `kind=skills` 仍以 path 为权威，合并保留逻辑根，竞争逻辑根拒绝。变更整份声明范围必须取得新的范围授权，不能复用原 manifest/verification；hash 不冒充身份认证。
- R2 备份后复验所有 `skipped_missing`；R3 只接受完整成功 vendor 资源记录（整数 exit 0、身份/状态/预期 after、私有原件均匹配），以已证明 after 和原件续作，保持原先渲染文件的目标（包括空文件）；R4 的相同/完成减项/新增效果/未知消失四分支已由独立复核确认。
- 本轮唯一最终全量：`python -B -m unittest discover -s tests -p 'test_*.py' -v`，**1367 tests，OK (skipped=8)，exit 0**。原模板边界与 vendor 失败证据契约保留。
- 8 个跳过仍为 5 个真实宿主 opt-in、2 个 Native Windows、1 个大小写敏感文件系统用例；未在 macOS 冒称这些平台验证通过。
- 定点首轮：453 tests / 1 error / 1 skipped，保留失败记录；错误是部署夹具改变了已封存部署环境。保留部署集合闸门，分离无部署的逻辑根用例后，定点 458 tests / 1 skipped / exit 0。
- 实际运行：原生 migration plan CLI 封存逻辑根并拒绝同名目录越界；真实 vendor 在备份间隙出现缺失路径时没有启动删除；真实 tl 成功后注入后续 I/O 失败，回执重试从原件生成正确 AGENTS，后续再重试幂等。
- 静态：五个受影响运行模块 ty check、cleanup/vendor 模块与测试 ruff check、scripts/tests compileall、Bash syntax 均通过。报告用原生 runner，`rtk: skipped-for-report`。
- 证据目录逻辑名：`sbtd-cleanup-review-fixes-izegevn_`；`delivery.md` 汇总，`full-1.{txt,json,md}` 为当前全量，`tested-source.json` 绑定测试期间未改变的核心源码/schema。Source Revision dirty，Evidence Source developer-local，Evidence Publication local-only。
- README.md、README.html、SKILL、REFERENCE、两份 AGENTS 模板已对齐减项免重复确认；CHANGELOG 记录修复；版本化 automation prompt 增补逻辑根/缺失状态/成功后态与确认规则的只读核验。未改 live automation、ENTRYPOINT 版本或本机生效配置。
- 原件备份与旧失败记录保留；未签名转换旧批次、未执行真实 HOME/项目清理、未 sync、未 commit/push/tag/release；P3-01 观察状态不变。

## 第二轮审核修复

本次继续 strict，修复最新审核确认的全部 3 项 P2；不处理已撤回的 PowerShell `-Yes` 候选。完整 grill 未触发，领域边界未变；持久行为规范见设计 §6。

| Gate | 触发与决定 | 状态 |
|---|---|---|
| DDIA | 精确清理范围归封存计划所有；plan 与 apply 均拒绝父子候选；Skills 根只解析一次，不由 apply 环境重定向 | confirmed |
| Legacy safety | 审核已实际复现：父目录删除后子项失败且重试 blocked；自定义 OMP 配置候选为空；自定义 Skills CLI 根被拒绝 | characterized；保留确认、身份、前态、原件与回执闸门 |
| Refactoring | 复用有效 OMP/Skills 解析器；抽取 plan/apply 共用候选范围检查，无新 schema/服务 | proceed |
| 回归与实际运行 | 既有检测、plan/apply 和实际 CLI 接口；新增重叠拒绝、配置路径、参数优先级及封存根隔离用例 | passed：focused-2 共 101 tests；runtime-smoke-2 共 9 次实际命令调用，均 exit 0 |
| Ponytail / 可读性 / 独立复核 | 不简化真实安全 seam；全局清理和授权边界需独立检查 | passed：两份独立复核关闭；新增目录别名问题修复后再复核，保持不同硬链接分别清理；删除重复渲染测试 |
| 最终全量 / Release readiness | 此轮单独取证，不复用第一轮 1367 项通过状态 | passed / ready（仅仓库交付）：full-1 共 1378 tests、8 skipped、exit 0；随后仅文档精确化，docs-final 46 tests 通过，运行源码/测试未变 |

1. plan 和 apply 在删除前拒绝候选相等及父子路径重叠，不能用执行排序掩盖冲突。
2. OMP MCP 检测包含现有解析器计算出的 `PI_CONFIG_DIR` / profile 有效路径；保留固定路径扫描与去重。
3. `cleanup-legacy --phase plan` 接受 `--global-skills-dir`，沿用显式参数优先规则；apply 不接受新根参数，只操作计划封存的根。

验证由主会话统一控制；源码、测试、文档各一 writer。证据目录逻辑名 `sbtd-cleanup-review2-c1us9o73`；只使用隔离 HOME/项目，不 sync、签名、发布或修改真实配置。

### 第二轮交付证据

- 当前最终全量：`sbtd-cleanup-review2-c1us9o73/full-1.{txt,json,md}`；命令 `python -B -m unittest discover -s tests -p 'test_*.py' -v`，**1378 tests，OK (skipped=8)，exit 0**。与首轮同名文件分属不同目录，不混用。
- 8 个跳过为真实宿主 opt-in 5 项、Native Windows 2 项、大小写敏感文件系统 1 项。本机大小写别名回归实际运行通过，不能代替 Windows 验收。
- 独立 `ReviewRound2Scope` 与 `ReviewRound2OmpDocs` 已关闭；额外修复 `.OMP`/`.omp` 等目录拼写别名重复候选，符号链接检查先于去重，不以文件 inode 合并不同硬链接目录项。
- 最终 Ruff、ty、Bash syntax 通过；最初 RUF022 导出顺序失败记录保留。`rtk: skipped-for-report`，所有正式结果由原生 runner 保存。
- 全量后仅精确化六处文档的别名/硬链接语义；`docs-final` 文档契约 46 项通过。运行源码/测试与全量快照一致；`tested-source.json` 保留全量输入，收尾文档摘要另存，不覆盖原证据。
- README.md、README.html、版本化 automation prompt 均已同步三项修复契约；CHANGELOG、SKILL、REFERENCE、设计与项目模板相应维护。未改 ENTRYPOINT 版本或 live automation。
- Lessons split name `kuno` 经本地 `.sbtd/developer` 验证；`LESSON-20261002-kuno-cleanup-target-set` 写入 repository-workflow topic 并同步 index，原历史记录不改名。
- 临时 runner/smoke 脚本在验证后移除，原始报告、失败记录、私有原件保留；不 commit/push/tag、不 sync、不执行真实 HOME/项目清理，不新增自动 fresh recovery，也不关闭 P3-01 观察窗口。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-01T18:14:42.612399+08:00 | planned | in-progress | User decisions resolved and before-dev DDIA, legacy and refactoring reviews completed | docs/prd/sbtd-cleanup-expansion-design.md; isolated 33 focused tests |
| 2026-10-01T20:43:36.176825+08:00 | in-progress | checking | Implementation and independent review fixes complete; final native full suite running | real fresh CLI, real batch tl cleanup, Bash/macOS pwsh forwarding and 10-resource backup restore smoke passed; private evidence sbtd-cleanup-expansion-ajno8aj7 |
| 2026-10-01T21:56:03.402389+08:00 | checking | done | Strict feature implementation complete; full restored-contract suite passed; independent findings closed; no live cleanup/sync/release | /Users/lusonglin/TEMP/sbtd-cleanup-expansion-ajno8aj7/full-5.txt: Ran 1347 tests, OK (skipped=8); native CLI and backup restoration smoke reports; no outstanding scoped review findings |
| 2026-10-01T23:25:27.399004+08:00 | done | planned | User requests fixing all four findings from uncommitted-code review | P1 logical Skills-root constraint; P2 skipped vendor path drift; P2 successful vendor side effects on retry; P2 redundant consent on already-completed subset |
| 2026-10-01T23:33:56.964995+08:00 | planned | in-progress | Four review findings accepted; before-dev safety and data-boundary design confirmed | ReviewFinding R1 logical Skills root; R2 absent-path drift; R3 successful vendor retry transitions; R4 monotonic consent scope |
| 2026-10-02T00:53:39.314885+08:00 | in-progress | checking | All four review fixes implemented and independently re-reviewed; focused regressions and native isolated smoke passed | sbtd-cleanup-review-fixes-izegevn_/focused-2.txt: 458 tests, skipped=1; runtime-smoke-run exit0; r1-cli-smoke passed; ruff/ty/syntax passed |
| 2026-10-02T01:15:43.411843+08:00 | checking | done | All four review fixes complete; current full suite passed and independent review findings closed | /Users/lusonglin/TEMP/sbtd-cleanup-review-fixes-izegevn_/full-1.txt: Ran 1367 tests, OK (skipped=8); focused 458 tests passed; native isolated smoke and independent re-review complete; local-only, no sync or release |
| 2026-10-02T09:50:24.066498+08:00 | done | planned | User requests fixing all three newly confirmed P2 review findings | Prior read-only review isolated reproductions: nested candidate apply failed then retry blocked; custom OMP config not detected; explicit Skills root unsupported |
| 2026-10-02T09:50:25.367384+08:00 | planned | in-progress | DDIA, legacy safety and refactoring gates confirmed for second review remediation | docs/prd/sbtd-cleanup-expansion-design.md section 6; prior reproduced failures; preserve confirmation and sealed roots |
| 2026-10-02T10:27:45.233371+08:00 | in-progress | checking | All three second-round P2 fixes and independent alias finding resolved; current targeted and native runtime proof passed | sbtd-cleanup-review2-c1us9o73/focused-2: 101 tests passed; runtime-smoke-2: 9 native calls passed; independent ReviewRound2Scope and ReviewRound2OmpDocs closed; final full suite follows |
| 2026-10-02T10:51:00.414208+08:00 | checking | done | Second-round three P2 fixes and independent alias finding complete; current full validation passed | /Users/lusonglin/TEMP/sbtd-cleanup-review2-c1us9o73/full-1.txt: Ran 1378 tests, OK (skipped=8), exit 0; focused-2 101 passed; runtime-smoke-2 9 native calls passed; docs-final 46 passed after wording clarification only; independent reviews closed; no sync or release |
