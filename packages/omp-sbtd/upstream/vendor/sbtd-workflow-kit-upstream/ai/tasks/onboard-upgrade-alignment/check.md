# 升级对齐验证与复核

## PR #110 第四轮7项修复（当前）

基线2b913a66，按F01—F07优先级完成封存范围、隔离依赖、Shell／RPC证据和legacy诊断修复；两切面独立复核已关闭F07边界与跨平台fixture问题。详细red／green、失败记录与证据边界见[review-round4.md](review-round4.md)。F02计划与两个执行入口都验证当前隔离解释器，真实CLI覆盖plan拒绝、合法计划、apply零写入拒绝和recovery保全拒绝；当前326项升级子集通过（18 skip）。最终生产源码的37资源真实安装／Codex／OMP／retry／recovery闭环通过，原字节恢复。

最终生产／测试提交`acaf83a39679f1f6605d54a9b6ce43847b3bbe31`的[三平台CI run37291867601](https://github.com/KunoLu/640-skills/actions/runs/37291867601)全部通过；同版本地原生完整1771项（27 skip）通过。Linux完整1771项（47 skip）及最低tomlkit56项通过；macOS安装器271项（2 skip）、升级326项（18 skip）通过；Windows安装器49项、PowerShell子集15项、升级326项（30 skip）通过，原生5.1 Unicode shim／Git Bash legacy实际执行。README两入口、REFERENCE、CHANGELOG和版本化automation prompt均维护，浏览器实际文档可见；未操作live automation、真实HOME或发布。最终记录提交须另取自身CI，不以旧head冒充。

第四轮Release Readiness：ready，仅仓库能力交付。计划与执行依赖检查限时30秒且不取消`-I`；原件、确认、写前守卫、RPC期限及私有恢复边界保持；无新增服务队列。真实37资源两次安装／重试／恢复、Codex／OMP各33 Skills与6工具通过，不声称原GUI重载或用户环境部署。两切面独立复核最终clean，Ponytail与可读性复核无待处理项。

BDD：traceable；REFERENCE U31—U36中文正文＋英文Given/When/Then，unittest映射在review-round4及命名用例；v1报告仅通用CI证据，不伪造v2场景执行绑定。Cross-repo context／API Contract：not-needed；Mock Strategy：contract-backed，真实宿主证据单列。rtk：skipped-for-report。Final Test Report／Run Summary MD：generated；Targeted Rerun／Final Full Rerun：passed。本地证据developer-local／dirty／local-only，CI证据ci／exact／verified；外部envelope发布器not-configured，GitHub原生Checks已发布。无业务Web／移动端变更，Playwright／Maestro不适用；静态README表面已用Chrome DevTools验证。

## PR #110 第三轮13项修复（历史）

基线1ae9c321，三个P1优先、其余按风险顺序完成13项及复核／原生Windows反馈修正；详细red／green见[review-round3.md](review-round3.md)。本地全量1762项（25 skip，启用真实Codex隔离）、317项升级回归（16 skip）、Ruff／ty、APFS与完整37资源真实宿主／重试／恢复通过。提交`7d360b65a2c82926ae683b4518e68cc7b2a2655e`的[三平台CI run37260456824](https://github.com/KunoLu/640-skills/actions/runs/37260456824)全部通过；Windows317项（28 skip）及PowerShell定点2项无skip通过，失败记录保留。Release Readiness: ready，仅仓库能力；最终记录提交另核对其自身CI。下方为历史，不作为本轮通过证据。

## PR #110 第二轮14项修复（历史）

基线40b0dbf；先修P1，后按路径／事务、协议可信度、Shell、CLI及诊断顺序完成14项及独立复核两处补充。逐项范围、red/green、证据限度和门禁见[review-round2.md](review-round2.md)。本地1750项全量（25 skip）、305项升级回归（15 skip）、Ruff／ty与37资源真实隔离生命周期通过；代码及CI配置提交`36ee62eb362ec671552eaf971815e1bb43b12441`的[三平台CI 37216126160](https://github.com/KunoLu/640-skills/actions/runs/37216126160)全部通过。Windows305项（26 skip）包含原生PowerShell5.1 Unicode与大小写敏感双根apply实际通过，不将平台skip当证明。Release Readiness: ready，仅仓库能力；未部署或发布。最终记录提交另核对其精确head CI。

## PR #110 上一轮15项修复（历史）

本轮相对ac34ee4修复15项；用户明确保留R03／R09／R11／R12原契约并纠正审查。详细场景、更正、故障分类和独立复核见[review-fixes.md](review-fixes.md)。

- 本地全量1732项通过、20项平台／opt-in跳过；之后的静态收口由当前287项升级回归（10 skip）、Ruff与ty通过复验。代码提交`99afbe89266ed4da456fd315f969caa0655d654f`的[三平台CI 37200497908](https://github.com/KunoLu/640-skills/actions/runs/37200497908)全部通过。
- 最终包真实隔离CLI完成37资源升级、Codex／OMP各33 Skills与6工具加载、已安装副本重试与恢复。缺失host的preserve仍安装；物理根别名只绑定一次；原profile与未选链接保留。不是GUI／既有会话重载。
- 库存、事务／CLI、shell、协议四个独立静态复核均已收口；作者与reviewer不代跑验证。当前实际验证证据在`reports/review-fixes/`，raw及同stem中文汇总保留、不上传本地路径。
- README两入口、REFERENCE U16—U19、版本化automation prompt、CHANGELOG及kuno lesson已维护。README HTML已用实际浏览器验证新增区块；Ego不可用时的失败证据保留。无业务Web／移动UI，Playwright／Maestro专项not-needed。
- BDD: traceable，中文正文＋英文Given/When/Then；API Contract: verified（升级schema、真实OMP响应）；Mock Strategy: contract-backed，仅用于协议／故障注入；真实隔离host单独报告。Cross-repo context: not-needed。rtk: skipped-for-report，普通Git事实查询使用rtk。
- 本轮Release Readiness: ready，仅针对已验收代码的仓库能力交付；没有合并、发布、sync、真实HOME应用或真实旧资产清理。最终验收记录提交后，交付head仍以PR页面对应的新一轮原生Checks为准，不把代码提交的CI冒称另一head。

### 本轮精确代码提交矩阵

| 平台／范围 | 99afbe8实际结果 |
|---|---|
| Linux全量 | 1732 tests，OK，32平台／opt-in skip |
| Linux最低tomlkit与大小写敏感路径 | 56＋1 tests，OK |
| macOS安装器／工作流 | 271 tests，OK，2 skip |
| macOS升级／恢复 | 287 tests，OK，10 skip |
| Windows安装器与PowerShell子集 | 49＋15 tests，OK |
| Windows根边界／TOML／junction／DACL | 22（1 skip）＋3＋1＋1 tests，OK |
| Windows升级／恢复 | 287 tests，OK，22平台／条件skip |

三个job均通过末次checkout清洁检查。原始元数据、各平台原生日志和同stem中文汇总见本地`reports/review-fixes/ci-repairs-code-99afbe8*`；generic v1 envelope已做schema及每份日志SHA复验，不将TXT／任意JSON伪装成v2场景执行绑定。Evidence Source: ci；Source Revision: exact；Environment Alignment: verified；自定义证据发布器not-configured，GitHub原生Checks与日志已可见。

### 本轮 Release Readiness Review

- Status: ready，作用域为本轮代码；正式部署／发布未授权。
- Production path：显式升级、恢复、所选host与profile；缺失host、嵌套安装、restore续作窗口和user-wide边界按用户确认保留。
- Failure modes：写后失败保留批次和unknown，原件／checkpoint不被旧成功替代；父路径与别名安全，动态shim和伪OMP证据拒绝。
- Capacity：本地串行操作；shim打开后最多读取65537字节，RPC写入／响应同期限；直接子进程／线程／管道正常及阻塞收尾已验证。异常后代继承管道仅限时尽力处理并警告，不声明进程组终止。
- Observability/runbook：分层JSON与REFERENCE；保留所有失败和修正报告，不新增后台遥测／服务告警设施。
- Rollout/recovery：仅草稿PR；实际隔离重试／恢复已通过，用户vault仍须独占且受信，不自动销毁备份或执行历史代码。
- Required validation：本轮矩阵、Ruff／ty、最终包真实Codex／OMP与完整CLI生命周期、四切面独立复核全部完成。业务Web／Mobile与真实GUI／账号部署不在本轮范围，无未获接受的可选检查豁免。
- Residual risk：UTF-16 BOM profile拒绝不转码；shim只证明CLI指向；原GUI／既有会话不由隔离probe证明。CI对既有Action的Node运行时和runner标签给出迁移提示，本轮未改其pin，也未将警告当成失败或悄悄升级。

以下各节为修复前历史记录，不作为本轮head的通过证据。

## 修复前证据边界（历史）

四阶段仓库能力实现、隔离运行和独立复核已完成；代码提交 `befa24eb7ef68c884a125af313528551b7d97af0` 的三平台 CI 全部通过（[run 37168994920](https://github.com/KunoLu/640-skills/actions/runs/37168994920)）。全部本地原始输出和同stem中文汇总保留在本目录 reports/；其中含本地运行路径，不随PR上传。提交前证据不冒充精确head；本机应用、同步、旧资产实际清理、新PR合并及发布均未执行。

## 已执行

- 原有参数/清理77项安全网通过；初次默认解释器缺tomlkit的失败保留，声明依赖解释器复跑。
- 升级CLI先red：缺upgrade入口。
- 完整受影响范围309项通过，1项原生Windows专用跳过；后续52项事务/CLI回归通过。
- 真实公开CLI在独立临时根完成33Skills、全局AGENTS、Codex/OMP与zsh profile安装；安装副本只读verify通过。
- 安装副本原生probe：Codex app-server及OMP RPC均加载33个受管Skills、6个固定Graft工具、版本0.21.1；zsh实际解析到选择的Graft路径。无模型请求，原GUI/既有会话未重载。
- 两根安装器真实plan均通过，非法phase均由实际Python拒绝；本机PowerShell不等于Windows证明。
- 真实完整包回归：旧安装对齐后删除测试bootstrap，使用已安装新CLI重试并恢复旧载荷通过；实际用户仓库或HOME未删除/覆盖。
- 新库存/host/CLI的ruff与ty通过。既有集成文件ruff基线27项、当前26项、新增0项，不夹带旧代码重构。
- 历史失败保留：4512758 原生Windows为23 failures/85 errors；2d8b474为canonical LICENSE换行不一致；141ba14为固定字节夹具、Git Bash省略.exe别名及完整生命周期180秒窗口不足。均已按真实失败修正；befa24e原生完整复跑通过，不以本地模拟替代。
- 首轮本地全量1643项含2 failures/5 errors/11 skipped；运行期间源码继续修正导致摘要及已加载模块不一致，该轮不得作为最终证明。失败原始报告保留；最终全量转到冻结提交的CI，避免边写边测。

## 独立复核修正

库存：排除缓存仍检查危险链接、跨平台稳定摘要顺序、bounded严格YAML身份、私密name不输出、来源schema/URL/自包校验、双向重叠。

宿主/CLI：已选OMP项目继承来源、安装目标launcher、继承连接验收、无跟随链接的Skills复制、真实shell解析、准确Skill启用/命令身份、隔离host不冒充live重载、空参数/partial退出码。

事务：逐资源恢复资格全字段绑定、当前scope派生、私有vault明确受信历史、未知部分改动保护、缓存稳定重试与恢复保守性、保留空父目录、同版安装位置迁移。库存、CLI/host、事务与Windows修正分别独立复核，最终无未解决的范围内问题。

## 方法与适用性

BDD: traceable，REFERENCE Upgrade Alignment的U01—U15中文场景，英文Given/When/Then；仓库禁止.feature，使用unittest。无跨业务服务/API，Cross-repo context与API Contract均not-needed。协议脚本化测试属contract-backed；原生宿主验收属isolated-host/selected-projection，不是live部署。Web/mobile测试工具not-needed；README.html仅文档内容更新，未改变交互。rtk: skipped-for-report，确保原生runner与raw证据。

Ponytail/Code Readability Review：保留真实库存、宿主差异和安全事务seam；无插件框架/daemon/密钥服务。使用既有catalog、文件事务、宿主候选和strict JSON能力，删除重复JSON解析器、无用变量与冗余断言，不因行数删掉恢复/授权保护。

## Final Full Rerun

| 原生平台／检查 | 代码提交 befa24e 的结果 |
|---|---|
| Linux 全量 unittest discover | 1650 tests，OK，19平台／条件skip |
| Linux 最低支持 TOML 编辑器 | 56 tests，OK |
| macOS 安装器及既有工作流 | 271 tests，OK，2 skip |
| macOS upgrade/recovery | 205 tests，OK，3原生Windows专用skip |
| Windows 安装器／工作流 | 49 tests，OK；PowerShell子集15 tests，OK |
| Windows upgrade/recovery | 205 tests，OK，5平台／条件skip；完整33Skills安装/已安装副本重试/恢复、DACL、Git Bash与PowerShell已执行 |

原始CI矩阵与每平台日志／同stem中文汇总：本地 `reports/ci-code-final*`。Evidence Source: ci；Source Revision: exact；Environment Alignment: verified（各自原生runner）；GitHub Checks已发布。Final Full Rerun: passed。没有把平台不适用skip视为该平台能力证明。

## 修复前 Release Readiness Review（历史）

- Status: ready，仅表示本次仓库能力交付，不代表v2正式发布或用户环境部署。
- Production path: 显式升级与恢复、选定Skills/配置域、独立清理能力；init/reset/migration既有含义保持。
- Safeguards: 受管来源/身份/路径校验，完整原件，写入意图，累计实测回执，失败停止，恢复资格与当前漂移保护；无整机原子承诺。
- Capacity: 本地串行文件操作；无服务队列/跨服务backpressure。宿主探测有协议与进程期限；Windows完整生命周期测试保留900秒窗口，未通过删测试或跳过Windows规避失败。
- Observability/runbook: JSON分阶段结果、备份/回执路径、REFERENCE升级与恢复说明、磁盘/协议/隔离host/清理分层状态。
- Rollout/recovery: PR保持draft，未应用HOME。恢复保留原件和空父目录。历史vault由操作人独占管理且显式受信，hash不认证整组伪造历史；来源存疑必须停。
- Required validation: 上表精确提交CI、公开CLI真实安装/重试/恢复、macOS真实Codex/OMP隔离宿主、独立复核均完成。Windows实际Codex/OMP GUI部署不属于本轮授权，不能据协议夹具宣称已完成该部署。
- Residual boundary: 原GUI/既有连接未重载，未知定制需要决定，跨版本旧计划可能source-stale；非发布承诺。没有未获接受的可选检查豁免。
