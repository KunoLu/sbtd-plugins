# P1-19：developer 按需建立与身份解析

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 基线与范围

- 基线main `45e9f363e6ef2a8716957f457e87e21ab8e210dd`；分支`p1-19-developer-identity`。P1-18实现/状态PR #35/#36已闭环，P1累计5项。
- 依据主PRD P1-19/AC-06/25与[LI身份契约](sbtd-workflow-v2-lessons-identity-contract.md)、lessons-record入口/identity-migration reference。旧身份迁移、lesson内容迁移/发布、历史ID改写不在本任务普通解析范围。
- 交付Onboard内`DeveloperStore`只读解析/计划/显式建立库，以及既有workflow `--developer`输入的真实初始化消费。不新增独立全局CLI、initializer、daemon或身份数据库。
- 普通任务创建/路由和无developer输入的onboard不要求名字、不建立身份；真实仓库lesson写入仍由用户提供合法分隔名并确认必要权限。当前会话的`640`仅是用户已提供的lesson分隔名，不能据此写入其他实际项目身份。

## 门禁与移前证据

- 未完整调用grill-with-docs：已批准LI矩阵清楚，环境/真实名字/迁移授权仍不得推断。
- Legacy characterized：fresh venv原生参数/AgentCLI/最小状态检查97 tests /5.701s /exit0，报告`tests/unit/reports/unit-report-developer-baseline-p1-19-developer-identity-2026_09_19-03_58_01.json`及中文MD/envelope，developer-local/exact/local-only。
- Refactoring proceed：复用安全TaskStore路径/Git/保护/原子writer，规范名字校验单一实现；既有check、无名字init/reset、项目范围和source安装行为不变。所有新caller先完整前置检查再写。
- DDD confirmed：developer是lesson命名分隔符，不是Git/OS身份、任务ID或权限授权。当前本地合法值优先；主checkout是Git元数据确认的实体，不是名为main的分支或猜测sibling。支撑子域，无新领域冲突，无完整grill结果需要修正。
- DDIA confirmed：local/main身份只读链有明确优先级，absent/conflict/unknown不混用。新建前复核拓扑/现存内容/ignore/tracked，非覆盖创建后回读；并发胜者不覆盖，失败不伪称身份已建立。reset不覆盖合法现值，批次名字使用必须来自明确列出的项目及该名字的确认。
- Release readiness planned，适用验证及独立review后运行。

## 身份链与写入边界

1. 读取本地`.sbtd/developer`：UTF-8普通安全文件，一条明确`name=`值，必须原样匹配`^[a-z0-9]+$`；不trim/小写化/去标点/猜作者。重复、异常类型、symlink、不可读或父路径不安全都是conflict，不作missing。
2. 本地合法立即使用，不为此调用Git或查主checkout。仅本地确实缺失后核对实际Git根、git-dir/common-dir及worktree registry；未知/不可用metadata返回blocked，不假设非linked。
3. 已验证linked worktree才读取同仓实际主checkout当前身份；主合法只读使用，不复制。本地/主异常均不绕过；主也确实缺失且父路径安全才允许首次建立。已证明非Git或普通checkout无需main来源，但不是Git失败就认定nonGit。
4. 普通resolve/plan/check/global安装不读取`.trellis/.developer`，无身份不妨碍无关安全任务。显式迁移将来消费本当前链优先级，不能以旧名覆盖当前或主身份。
5. `plan(name)`只读：报告既有来源、名字冲突、首次建立资格、身份目标及是否还需窄保护；不下载、不写HOME、不创建task或spec。`ensure(name, confirmed=False, protect=False)`未确认不写；protect必须独立显式允许，不能因名字文本存在推导保护授权。
6. 首次建立只允许正常缺失目标；`.sbtd`未知用户数据、tracked、symlink/目录同名等不隐藏、不untrack、不覆盖。复用根锚定保护，建立内容仅`name=<name>\n`，回读后才使用。
7. 同名重复调用幂等；不同名返回conflict，既有本地或主合法身份不改。reset无名字不触碰身份；显式名字与已有冲突在所有初始化写入之前拒绝。
8. Onboard `check/plan --developer`只读；init/reset/init-projects明确`--developer <name>`与`--yes`作用于列出的项目，完整计划必须展示每个目标/继承来源。缺项目时不得把名字写到cwd或HOME；多个项目的名单+相同名字必须在计划和确认范围内，不静默扩展。Python是唯一身份实现，外围安装器不重复实现Git/写入规则。
9. 初始化可以先按既有安全计划写必要ignore，再调用身份ensure；但身份冲突/未知worktree/目标类型等必须先检查，不能在全局安装或其他项目写入之后才发现。部分I/O失败如实记录，不假装跨项目事务。

## 验证与交付

- LI-01～10/21/24的真实普通仓库、linked worktree、nonGit、Git缺失/坏metadata、本地主优先级、合法/非法/重复/不可读/symlink、保护/tracked/竞态/idempotence、reset和批次前置屏障。
- 临时Git worktree使用明确私有fixture，不读取真实开发者项目/身份。完整Skill副本实际调用及缺依赖边界，原生报告+中文MD+envelope，最终精确SHA全量及独立review。
- 本源仓不生成.feature；行为追溯本taskdoc及LI矩阵，旧身份复制/删除和完整lesson发布不冒称通过。
- README.md/html、Onboard/lessons-record说明、versioned automation prompt与CHANGELOG按实际入口同步；live automation、ENTRYPOINT、真实HOME和真实身份不变。
- D-IMP-13：P0/P1闭环，P2/P3原级入findings延期；D-IMP-14：P1累计10项闭环后暂停全findings评估并等用户确认。实现PR/清理/独立status PR闭环前不展开P1-12。

## 已确认计划范围内的保护转发调整

- 初稿调用方固定`ensure(..., protect=False)`；真实非Git初始化在写完脚手架后仍返回needs-protection，因为现有TaskStore的保守非Git保护判据要求末尾准确的`/.sbtd/`，而通用模板末尾还有其他规则。把该失败当作非Git功能交付不满足LI首次建立契约。
- 调整：先完整只读计划，明确每个项目的`needsProtection`；用户以列出的projects、显式名字和`--yes`确认本次初始化后，调用方只在原计划该字段严格为true时传`protect=True`。其余项目仍false，不从后续新出现的需求扩张授权。保护仍由现有窄helper执行，不另写ignore规则算法，不初始化Git，不代替完整scaffold流程。
- 非Git真实CLI红测原退出2，调整后创建已确认身份且不生成.git；84项身份/CLI/多项目影响范围通过。该工程选择未授权任何实际用户项目写入。
- Git分类另经红绿修复：命令报“not a git repository”不能掩盖存在但损坏的.git标记；发现本级/祖先标记或不可检查时返回unknown/blocked，不假装已证明nonGit。合法本地身份仍无需Git即可优先读取。

## 独立审查与失败路径闭环

- identity安全审查无P0/P1；三个P2（非Git前导空格ignore、保护helper失败丢completed_steps、尾空白Git根判定差异）原级延期。
- CLI审查两个P1已红绿关闭：身份阶段失败未报告已写脚手架；root在预检/写入间消失导致未捕获构造异常并丢批次先前成功项。三个真实文件/I/O红测修前均error，修后129项影响范围通过，独立只读复核确认无剩余P0/P1。
- 每项目lazy操作边界统一返回blocked/failed；身份阶段前固化operationResults，失败单份JSON包含写后sbtdProjectSetup、developerPlan、backups、unverifiedChecks。写后检查用原预检roots，不再为报告错误重新解析可能消失的项目。
- CLI文本最终仍只展示预检身份状态为第四个P2，未修；六条审查记录进入根findings.log（2 fixed P1、4 deferred P2），D-IMP-14统一评估。
- worker两次越界py_compile不计验证gate；所有正式证据由Main统一生成。复用既有parallel-validation-ownership lesson，不重复新增。
- Lessons新增`LESSON-20260919-640-identity-absence-and-phase-results`，使用用户已明确的640分隔名；未建立真实.sbtd/developer。
- [Git官方worktree文档](https://git-scm.com/docs/git-worktree)明确main worktree在list首项、porcelain稳定且`-z`保留含换行路径；实现仍用actual root/git-dir/common-dir交叉确认，不以main分支名或猜测sibling定位。

## 提交前验证与范围判断

- Main最后计划范围全量：`python -B -m unittest discover -s tests -v`，745 tests/183.192s，exit 0，无skip；报告`unit-report-identity-full-final-p1-19-developer-identity-2026_09_19-05_43_08`。原生10场景完整310文件Skill副本报告`api-report-identity-native-final-p1-19-developer-identity-2026_09_19-05_43_00`，exit 0。这些是dirty/developer-local/local-only，不能替代随后精确head验证。
- 真实Git/worktree、命令行与stdlib-only读取均已运行；无真实HOME/用户身份/旧身份迁移写入。浏览器、Web/Mobile E2E、Graft、host接线、Windows平台证明不属于此库/CLI切片验收，不据本轮通过冒称完整v2发布。
- 新模块与两测试Ruff/ty通过；首次ty漏设脚本搜索路径报unresolved-import，按实际`--extra-search-path sbtd-workflow-onboard/scripts`重跑通过。两个既有脚本基线Ruff 26/ty 93诊断保持不变，无新增，不扩修既有债务。
- Code Readability Review：统一逐项目构造/执行边界，复用字段投影、参数校验、单值action和既有Git/I/O；无浅层双重wrapper或scope外抽象。Ponytail无额外删除建议；接受可读性优先，不为减行密化解析逻辑。
- README.md/html已同步实际入口和失败结果；REFERENCE/Skill/lessons说明更新，CHANGELOG记录能力与失败语义；versioned automation仅扩充sbtd_identity.py评估库存。live automation/ENTRYPOINT/真实生效路径不动。HTML结构/ID静态检查通过，纯文档正文变化未做视觉验收。
- Release gate等待精确提交验证与最终独立证据审查；不会在该门前提前标done或展开下一任务。

## 最终复核补记

- 首个clean候选`cb0dcf5221f225e80115c378a3fea1721273300e`已完成fresh venv全量745 tests/184.923s与完整310文件安装副本10原生场景；21份envelope/schema/hash/中文汇总通过。证据review确认local-only，不提升为CI或其他平台证明。
- 文档review无P0/P1，新增P2：README把写后失败一概描述为exit 5，实际仅failed为5，其他阻断状态为2。按D-IMP-13登记延期，不修文案；累计2 fixed P1、5 deferred P2。
- 关于checking行仍记录提交前dirty的初步P2，经澄清“实现合入/清理→独立状态PR更新最终exact/done/时间/merge”约定后reviewer撤回；以dismissed保留记录，不提前改成done。
- 本补记与ledger登记不改生产实现；随后重新固定最终SHA并重跑计划范围。最终精确证据及Release gate结论由正式报告/PR说明与合并后独立状态PR留存，避免文档自指尚未生成的提交或未来合并事实。

## 实现合入与完成事实

- 最终head`498a4bd75113a468f2dd11946f57d77e09f3e5bb`，clean/exact/developer-local/local-only：原生745 tests/184.442s、310文件完整安装副本10原生场景均通过；最终报告stem为`unit-report-identity-pr-head-full-p1-19-developer-identity-2026_09_19-05_58_59`与`api-report-identity-pr-head-native-p1-19-developer-identity-2026_09_19-05_58_17`。
- 23份v1 envelope、raw checksum与同stem中文汇总通过。最终unit raw保留安装manifest、Python/依赖版本、静态结果、独立review与清理事实；只更新附加元数据及对应hash，不改原运行输出或sourceCommit。
- [实现PR #37](https://github.com/KunoLu/640-skills/pull/37)于2026-09-19T06:04:50+08:00实际合并；merge`4226f29b15de1f2c7378739e00e7bed66633a8f6`。2026-09-19T06:06:25+08:00完成main/origin/tree及本地/远端任务分支清理核对；四份源码快照与base一致后删除Main私有验证目录，69份正式报告保留。
- 独立实现/文档/证据复核无剩余P0/P1；2 fixed P1、5 deferred P2、1 dismissed P2保持真实。Release Readiness ready仅本任务；无Windows/真实host/旧身份迁移/完整v2发布声明，不自动删除已创建身份。
- README.md/html、CHANGELOG和versioned automation在实现PR已按真实入口维护；本状态PR只补完成事实，无新用户接口或安装行为，三入口与CHANGELOG均无需重复改写。未操作live automation、ENTRYPOINT、真实HOME、P0安装或用户迁移备份。
- P1累计6项；此完成事实仍须独立状态PR合入与分支清理后才能展开下一任务。累计10项后的全findings评估/用户确认门不变。
