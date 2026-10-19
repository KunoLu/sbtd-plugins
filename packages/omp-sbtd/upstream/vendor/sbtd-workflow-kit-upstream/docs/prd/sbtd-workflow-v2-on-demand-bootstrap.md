# P1-02：按需脚手架与 bootstrap 边界

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 状态与范围

- 实时状态以主 PRD 为准；完成时间与 merge SHA 只在实际合入后回填，不维护第二份完成状态。
- 基线：`172284e6415f464f91a6c76ce64b49b83555af4d`。
- 分支：`p1-02-on-demand-bootstrap`。
- 审查门禁：D-IMP-13；有效 P0/P1 阻断，P2 及以下记录到根 `findings.log`。
- 本项交付 PRD §7.3、§7.9、§10.1/10.2 中与按需安装和最小状态检查有关的行为，不宣称 AC-03/13/23 的跨任务验收全部完成。

## 实现边界

1. `check`、`check-projects`、`plan` 不初始化项目、不创建本地状态、不运行 Trellis 初始化。项目未 onboard、没有 `.sbtd` 或 bootstrap 不构成错误。
2. `init`、`reset`、`init-projects` 只维护已明确选择的安装资产。继续使用既有 AGENTS 与项目 ignore 安装机制；不预建 task、pointer、developer、spec、lessons、handoff、测试目录或图目录。全局调用未选择项目时不扫描其他项目。
3. 项目状态检查只读取当前 active pointer 及其目标，以及固定位置的显式 bootstrap 任务。检查 UTF-8、JSON/YAML 安全形状、v1 schema、真实时间格式、路径类型和 containment、指针与完整逻辑 ID 一致性。不得用目录存在冒充任务有效或完成；不扫描整个任务历史、不根据 mtime 选择任务。
4. 输出明确区分最小状态检查与任务执行许可。本项不转换状态、不重绑定分支、不恢复 blocked、不验证完整父子/事件历史；这些行为归 P1-17/18。检查通过不是任务恢复或完整工作流验收证据。
5. `ai/tasks/00-bootstrap-guidelines/task.md` 不存在时不要求 bootstrap；存在时读取实际任务记录，未完成记录报告 `bootstrap-required`。异常记录报告需处理的状态，不重建、不覆盖。旧 `.trellis` 保留并提示显式迁移，不调用旧运行时。
6. 项目检查或安装前置条件异常时保留每个项目的 `status`、`reason`、`nextStep`；阻断必要写入，不以聚合成功掩盖失败。安装前完成前置检查，避免先覆盖文件再发现状态冲突。
7. 激活此生产者时，Python 与 Bash/PowerShell 直接调用者同步移除四个旧 Trellis 参数及其提示/转发/初始化行为，无兼容别名。使用 `sbtdInit`、`sbtdProjectSetup` 替代旧 setup 字段；不注册尚未实现的 migration/recovery/developer handler。后续 Graft、host 接线和安装器完整迁移仍由原任务负责。
8. JSON 模式保持 stdout 一个 JSON 文档，诊断走 stderr；保留现有成功/阻断/验证失败/项目设置失败/bootstrap-required 的退出语义，不虚构成功。

## 数据与依赖

- task 的 `task.md` 是模式和状态事实源，active pointer 只有书签字段；不得复制 mode/status 到另一个状态源。
- `.sbtd/developer`、本地/共享任务、spec、lessons、handoff 与旧 `.trellis` 均是需保全的数据，不属于 reset 清理范围。
- 使用 bundled `task-data.schema.json`，不新建第二套 task schema。
- YAML 使用安全解析器，拒绝重复键、执行型/非 JSON 类型、循环和非有限数；时间戳作为字符串交给真实日期校验。错误不回显完整 task 正文或私有扩展值。
- 若使用 PyYAML，必须在 Onboard `requirements.txt` 声明版本边界；不能依赖当前机器碰巧安装的包。隔离安装副本要实际安装复制的 requirements，验证依赖缺失与正常两条路径。
- 仅操作合成项目和私有测试 HOME。未获准修改真实 HOME、实际项目、live automation 或执行迁移。

## 开发门禁

- `grill-with-docs`：未完整调用；PRD/schema/现有调用链已确定本项边界，没有新的产品待决问题。
- DDD：`confirmed`；区分安装资产、可选任务数据与任务执行，bootstrap 不等于必需初始化。
- Legacy：`characterized`；原生 `python3 -m unittest discover -s tests -p test_onboard_multi_projects.py -v`，59 tests / 29.697s / exit 0。
- 基线报告：`tests/unit/reports/unit-report-onboard-lifecycle-baseline-p1-02-on-demand-bootstrap-2026_09_18-15_57_18.json`；同 stem 中文汇总与 evidence envelope 已生成。
- Refactoring：`proceed`，normal；不做前置大重构，新只读检查模块复用 schema，现有编排接入。
- DDIA：`confirmed`；状态读取无写入、前置冲突阻断、现有数据保全，不新增异步/迁移/恢复子系统。
- Release readiness：`ready`，仅针对已验证的 P1-02 候选；完整 v2、Windows、host 与迁移仍由既定后续任务验收，不能提前发布。

## 验证计划

- 保留并调整真正发生变化的生命周期行为测试；不把旧 Trellis 调用次数当成新行为契约。
- 无状态项目、有效本地/共享指针、坏 JSON/YAML、重复键、非有限值、循环、非法 schema/日期、悬空/越界/symlink 路径、ID 不符、显式 bootstrap 未完成/已记录完成/损坏。
- 实际 Python CLI 的只读快照、项目级初始化、重复 init/reset、已有数据 byte 保全、单 JSON、错误退出、项目隔离与零全局安装。
- Bash 3.2 与私有 macOS PowerShell 实际执行；Windows 真执行仍归 P1-08，不以本轮 macOS 结果替代。
- 复制安装目录和 fresh venv，不继承本机 site-packages；安装 requirements 后运行实际入口，记录依赖版本和源 revision。
- 最终项目验证、Code Readability/Ponytail review、独立审查；P2+ 按 D-IMP-13 入账。
- README.md、README.html、Onboard docs、版本化 automation prompt 与 CHANGELOG 同轮评估并只改受影响内容；不操作 live automation。

## 实施期说明

- YAML 采用显式依赖 `PyYAML>=6.0.3,<7`，与既有 jsonschema 一并由安装副本 requirements 准备；本机 6.0.3/4.26.0 的可用性不是副本安装证据。
- 新增保护规则前，已有保留路径必须已可证明忽略且没有 tracked 内容；无法确认时需用户处理，不静默隐藏数据。安装目标 symlink／异常类型及多硬链接 `.gitignore` 先阻断。
- 未完整采用 test-first TDD；采用既有生命周期行为刻画及新增解析／保全边界回归，不把移后测试冒充红绿证据。独立并行切面完成后由主线程集中执行正式验证。
- 两个 worker 自行报告运行过定点命令，违反本批“禁止在途验证”的要求；这些结果不计验收，正式证据由主线程重新生成。
- 使用[官方 PowerShell release](https://github.com/PowerShell/PowerShell/releases/tag/v7.6.6)的 macOS ARM64 archive，SHA-256 `6df833d094ebac1c1a74340d7b3437f4aaf5e03ce640484a1c4359f3ce8b3db1`；仅私有临时解压，无全局安装或 PATH symlink。实际帮助、参数绑定及 project-only 成功／阻断路径已运行，不替代 Windows 验收。
- 移除本轮触及的安装器源码字符串/调用顺序断言，不把静态文本检查换个拼写继续当行为测试；旧参数拒绝以实际 CLI smoke 覆盖。

## 验证与审查结果

### 提交前验证

- 状态与生命周期定点：108 tests / 22.284s / exit 0。
- 真实 PowerShell 暴露并修复两项问题：普通参数绑定默许旧参数；内部 `init-projects` 错写入公开 `Action` 的 ValidateSet。未知参数回归有真实 red→green；首次修复的双 BOM 错误由正常 Help 控制发现，负例单独非零的报告明确标为无效通过证据。
- 修复后的定点 3 tests / 1.727s、影响范围 165 tests / 23.324s 均通过。文案固定断言删除，实际 Git 索引边界保留；新增状态测试不绑定诊断措辞。
- 全量范围诊断：587 tests / 59.839s / exit 0，报告 `tests/unit/reports/unit-report-onboard-full-p1-02-on-demand-bootstrap-2026_09_18-17_23_54.json`。之后的类型／lint 收尾仍须最终精确提交复验，不能沿用为 PR head 证据。
- 11 组真实 CLI smoke 通过：`tests/api/reports/api-report-onboard-real-cli-complete-p1-02-on-demand-bootstrap-2026_09_18-18_36_54.json`；覆盖 Python/Bash/macOS PowerShell、旧参数拒绝、成功和失败退出码、诊断保留、状态/目录/mtime保全、真实 Git ignore、禁止全局命令与未选项目（含 Git 元数据）零变化。
- 完整安装副本 304 个文件，两个不继承系统包的 fresh venv：缺 jsonschema、缺 PyYAML、按副本 requirements 离线安装完整依赖、有效状态、缺 schema、源内容保全及全部 11 CLI 场景通过。版本：Python 3.13.11、PyYAML 6.0.3、jsonschema 4.26.0；报告 `tests/api/reports/api-report-onboard-installed-copy-p1-02-on-demand-bootstrap-2026_09_18-18_43_08.json`。
- 新状态模块/测试 Ruff 与 ty 通过；全部受影响 Python 范围 Ruff 存量 41→41、ty 存量 123→104，按文件/符号/规则/消息比较无新增。ty 使用 scripts 搜索路径与实际 Python 解释器；不宣称既有全量静态诊断清零。
- 所有报告为 developer-local / dirty / local-only，保留 raw、同 stem 中文汇总及 envelope；精确提交验证和独立 review 尚未完成。
- Lessons split name：`640`；Source：`user-provided`。新增记录位于 `docs/lessons/topics/validation-scripts.md` 与索引，只追加本人标记块；历史记录不改写。

### 可读性与简化审查

- 返回结构用 `StateInspection` / `TaskSummary` 精确表达，不用 Any 掩盖消费方类型错误。
- 删除无必要的跨调用 schema 缓存；检查当前安装副本，不依赖过期缓存。`_guard` 直接接收函数与路径，避免循环闭包。
- 保留安全解析、错误消毒、实际路径检查的内聚边界，不合并成密集表达式，也不引入任务执行/历史扫描框架。
- README.md、README.html、三个直接流程图、Onboard docs、版本化 prompt 和 CHANGELOG 已按本项行为更新；不操作 live automation，不修改 ENTRYPOINT 版本。
- 独立 review 与 release readiness 结果在实际完成后补充；P2+ 按 D-IMP-13 入账，不伪造零发现。

### 第一轮独立审查与修复

- `P102StateReviewOne`：无 P0/P1，3 条 P2；`P102IntegrationReviewOne`：1 条 P1、1 条 P2。4 条 P2 全部原级别写入 `findings.log`，保持 deferred，不修复、不声称零发现。
- P1 为外围安装先于完整 scaffold 检查。真实 Bash red 已证明可选 npx 写入合成 marker 后才退出 2；共享 `inspect_project_setup` 后，同一复现先退出 2 且 marker 不存在。
- `check` / `check-projects` / `plan` 复用完整只读判定；两 root installers 在任何全局、MCP 或可选项目 mutation 之前检查。普通模式保留可提前的只读 Agent 查询，实际安装延后至项目 gate 通过；写入前再次复验。`check-projects --skip-project-agents` 与公开/内部 parser、两端 preflight/final-check 同批接入，未选目标不扩张。
- 定点 3 tests / 3.232s、受影响 121 tests / 30.412s、全量 589 tests / 60.855s 通过。全量报告 `tests/unit/reports/unit-report-preflight-full-p1-02-on-demand-bootstrap-2026_09_18-19_16_39.json`。
- 完整副本／两 fresh venv／13 组实际 CLI 通过，增加两安装器的 skip-project-agents 范围；报告 `tests/api/reports/api-report-preflight-installed-copy-p1-02-on-demand-bootstrap-2026_09_18-19_15_00.json`。已有有效 task fixture 显式具备安装保护条件，缺依赖测试不绕过新增前置条件。
- Ruff 仍 41→41、ty 123→104，无新增诊断。删除安装器固定调用数组断言，不重钉新的内部顺序；真正的前置屏障与文件保全回归保留。
- 所有上述证据仍为 dirty/local-only；第二轮完整复审与最终精确提交验证尚待完成。

### 第二轮审查与精确提交证明

- 冻结候选 `bb5e3f2f0c0fde0fb012899c1f2b03c632311225`：`P102PreflightReviewTwo` 确认首轮 P1 关闭、无新 P0/P1；`P102EvidenceReviewTwo` 同样无 P0/P1，新增 4 条 P2 与 1 条 P3。全部入 `findings.log`，本项累计 8 条 P2、1 条 P3 保持 deferred，不按旧零发现门槛继续修复。
- 同一 clean SHA 原生全量 589 tests / 61.595s / exit 0，13 组实际 CLI 通过；`git archive` 完整 304 文件安装副本、两个 fresh venv、声明依赖与缺失分支全部通过。正式报告 stem 分别为 `unit-report-onboard-exact-p1-02-on-demand-bootstrap-2026_09_18-19_22_18`、`api-report-onboard-exact-cli-p1-02-on-demand-bootstrap-2026_09_18-19_22_18`、`api-report-onboard-exact-installed-p1-02-on-demand-bootstrap-2026_09_18-19_22_18`，位于既有 unit/API reports 目录；raw/中文MD/envelope成套保留。证据是 developer-local / exact / local-only，不是 CI 或 Windows。
- Code Readability/Ponytail：两路独立复审未发现需继续重构的结构问题；精确结果类型、共享只读 gate 和公开参数/内部模式分离均有实际用途，无新增执行框架。既有 Ruff/ty 诊断保持基线范围，不声称全仓静态全绿。
- Release Readiness：`ready`，范围仅 P1-02。本地同步 CLI，无新增队列/后台服务；失败早于安装副作用，保留数据并输出逐项目诊断；代码回退不授权删除项目数据。用户 D-IMP-13 已明确低优先级事项留待后续评估；完整 v2 仍不具备发布声明。
- 本次收尾仅补审查与验证记录，不改变已验证生产代码。若记录产生新 commit，按最终 head 重跑精确验证；不将上述旧 SHA 报告改写成新提交证据。实际完成与 merge 事实只在实施 PR 合并并清理分支后进入独立状态 PR。
