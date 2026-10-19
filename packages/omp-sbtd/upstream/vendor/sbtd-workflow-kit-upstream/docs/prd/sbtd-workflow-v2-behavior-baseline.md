# SBTD v2 P0-02：既有行为基线与保留契约

## 范围与证据边界

本文件交付主 [PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md) 的 P0-02，服务 AC-02、AC-14、AC-23。任务状态与实际完成时间只由主 PRD §14 维护。本清单是迁移设计输入，不是提前安装到用户环境的 v2 规则。

- 产品比较基线：`v1.0.15`，`bc8eec1549928fb0966254751b96b611b6334183`。
- 本项开发起点：`main`，`34a15499e8c13301ec5da7cf172bd9a94915a73d`；任务分支 `p0-02-behavior-baseline`。
- 两个快照之间的安装器、catalog、模板和生产测试相同；差异为文档、监控记录和归档，不代表 v2 已实现。
- 当前 catalog 仍有 15 个 bundled、19 个 external Skill，仍使用 Trellis／GitNexus。`sbtd-task`、三模式执行规则和 Graft Onboard 接线尚未交付。
- 现有规则中的“必须”不等于已有运行时强制证明。源码／规则盘点、单元／fixture 测试、真实 CLI smoke、真实 host 行为分别记录，不互相冒充。

## 术语与三类处置

- **保留**：保留可观察安全或证据语义，必要时迁移其实现位置。
- **替换**：旧工具命令、目录、路由及输出字段按主 PRD 干净切换，不保留运行时 alias；旧输入、备份与历史记录仍受保护。
- **按模式调整**：改变方法调用时机与产物厚度，不降低用户明确交付、项目原有规范、真实权限或数据安全要求。

`default/lite/strict` 是任务执行模式；`init/reset/init-projects` 是安装命令，两者正交。`caveman lite` 是表达压缩，不能切换执行模式。public bootstrap 只安装 Onboard Skill，不能宣称已激活全局运行规则。

## 保留／替换清单

下表来源简写约定：`scripts/`、`templates/`、`catalog.json` 与顶层 `SKILL.md` 均位于 `sbtd-workflow-onboard/`；`<skill>/SKILL.md` 位于其 `templates/skills/`。`tests/`、安装脚本及 README／ENTRYPOINT 相对仓库根。未来行为以主 PRD 为准；本表不引入新的审批层或调度器。

| ID | 既有事实与来源 | v2 处置与共同边界 | 实现归属 |
|---|---|---|---|
| B01 | `scripts/onboard.py` 的 `build_projects_check_results` 仅输出逐项目检查；`tests/test_onboard_multi_projects.py` 覆盖 project-only 全局隔离 | 保留：project-only 不安装／检查／修改全局工具、Skill、AGENTS 或 MCP；缺本地 CLI 不转成全局安装 | P1-02、P1-03、P1-07、P1-08 |
| B02 | `catalog.json` 与 `SKILL.md` 区分 bundled、external、agent-template、project-template；安装入口自包含 | 替换两个 Trellis entries 为一个 sbtd-task，15→14 bundled；19 external 不变。目录与 catalog 原子交付；bootstrap 不等于执行 Onboard | P0-07、P1-09 |
| B03 | `tests/test_onboard_external_skills.py` 覆盖 stable 来源、身份冲突、symlink、回滚失败保留与嵌套 JSON 结果 | 保留 stable mirror 当前内容与 pin，不以工具迁移顺带升级或改写镜像。受管身份、路径与类型共同决定替换资格；唯一恢复副本不能删除 | P0-07、P1-12、P1-13 |
| B04 | `tests/test_onboard_multi_projects.py` 覆盖 init 跳过有效 shell、reset 替换、全局目标去重与 OMP 根缺失 | 保留现有安装模式区别和文件所有权；新任务／spec／lessons／developer 不得被 reset 当模板覆盖。既有目录存在不是整目录删除授权 | P1-02、P1-04、P1-05、P1-19 |
| B05 | `templates/agents/AGENTS.project.md` 的 Project-only fallback 与全局触发规则；`trellis-workflow/SKILL.md` 的 before/check/finish 流程 | 按模式调整：strict 保留完整适用流程；default/lite 保留风险判断与必要验证，不因旧常驻句子强制全套产物。任何模式不取消项目本来要求的 Gate | P0-04、P0-05、P1-09 |
| B06 | 全局 Skill 路由、五个 `book-*` reviewer 及 `trellis-workflow/SKILL.md` 的 Book-derived Skill Gate | 按模式调整调用强度；实际采用 reviewer 时保留其状态词表、证据要求、修正回路。完整 grill 后仍独立 DDD；数据安全不能按模式豁免 | P0-04、P0-10、P1-09 |
| B07 | `trellis-workflow/SKILL.md` 的 Ponytail and Code Readability Sequence | strict 保留 smoke→简化审查→可读性裁决→验证→适用 release review；其他模式避免形式化重复。简化不能删真实 seam、安全或明确交付 | P0-04、P1-09 |
| B08 | `templates/agents/AGENTS.project.md` 的 BDD / Gherkin、`gherkin-bdd` Skill；本源仓库另有不建 `.feature` 的边界 | 按模式调整产物需求；strict 保留适用 no-new-uncovered-behavior。所有模式遵守项目已有 BDD 约定和用户明确场景交付；本仓不新增 `.feature` | P0-04、P1-09、P1-14 |
| B09 | `project-validation`、Maestro、Web UI Skills 与项目规则区分 CLI 执行和 MCP 诊断 | 保留真实工具职责；MCP 探索、mock 或截图不能冒充 Playwright／Maestro CLI 回归、CI 或 full-stack。缺环境如实报告 | P1-09、P1-14、P1-15 |
| B10 | `project-validation` 的报告、Evidence v1/v2；`tests/test_validation_evidence_v2.py` 校验报告摘要、locator 与真实 passed case 绑定 | 保留原生报告、同 stem 中文摘要、source ref／SHA／worktree／环境／publication；失败报告仍留存，dirty local 不证明 PR head | P1-09、P1-14、P1-15 |
| B11 | `tests/test_knowledge_base_p1.py` 覆盖固定 ref 摄取、不切活动分支、幂等、runner、陈旧报告与环境对齐 | 保留只读 ingest、Revision Set、Evidence Decision、manifest／checksum／attestation；不将缺图或轻模式当成放宽证据的理由 | P1-09、P1-14 |
| B12 | 旧 `.trellis` task/context/journal 和生成角色；全局／项目规则与两个 Trellis Skills 持有旧路由 | 替换运行依赖，保留受管旧输入和私有历史。新 task 唯一拥有 mode/status，handoff 为快照；禁止重建 Channel／调度服务或兼容 alias | P0-03～P0-07、P1-09、P1-12、P1-17、P1-18 |
| B13 | GitNexus 的影响分析、MCP、graph、route/PDG 能力在原规则中有各自前置；当前 Onboard 尚无 Graft | 替换为已证明的 Graft 结构能力；不承诺工具对等。禁 deep/name/cloud、受管入口 DNT、显式仓根、无父目录联邦。图失败不证明无依赖 | P1-03～P1-06 |
| B14 | `tests/test_onboard_agent_cli.py` 与多项目测试区分平台 CLI、MCP scope 和 active HOME；repo lessons 记录 GUI PATH 与只读 probe 副作用 | 保留未选平台零写入、HOME containment、唯一配置写入者与真实握手。check/plan 零副作用；hooks 默认关闭且单独持久授权，OMP 不翻译 Codex hooks | P1-03～P1-06、P1-14 |
| B15 | `lessons-record` 的名字合法性、来源顺序、marker 与 ID 查重；历史资产分层保存 | 替换身份位置为 `.sbtd/developer`，不追溯改名。按需建立、缺失询问、异常不绕过；缺身份不冻结 default/lite 的无关安全工作 | P0-06、P1-19、P1-12 |
| B16 | `tests/test_workflow_contracts.py` 的真实 Git ignore 探针、多项目测试的 append-only 与冲突检测 | 保留 secrets／报告／缓存保护和用户规则；替换旧工具段必须经显式迁移、保全验收与再次确认。源仓现行九行（P0-09 七行基线加两个 MCP 本地日志目录）和业务模板四条新增分别验证 | P0-08、P0-09、P1-12 |
| B17 | 全局表达规则、`test_onboard_caveman_maintenance.py`、`test_onboard_i_have_adhd.py`、`test_onboard_ponytail_integration.py` | 保留 provider conflict、可选 Caveman 维护、19 external 安装和手动启用边界。表达压缩不改变执行模式；handoff 取消计数触发不等于取消 auto-lite 表达状态机 | P0-05、P1-09、P1-14 |
| B18 | `install.sh`／`install.ps1` 共用 Python；`tests/test_install_sh_agent_cli_flow.py` 覆盖 project-only、EOF 和 scope，部分 PowerShell 检查为静态 | 保留单实现与两端退出码／JSON一致、逐项目错误与恢复信息；替换 Trellis 参数及字段。Bash 3.2 实测与 Windows PowerShell 实测仍需独立证明 | P1-01、P1-07、P1-08、P1-14 |
| B19 | 根 ENTRYPOINT、README 双入口、版本化 automation prompt，以及 sync/update 的分离契约 | 保留普通开发不写 live／真实 HOME；文档如实随实现变化。Git 分支同步不等于本机 workflow sync；PR 合入不等于发布或迁移完成 | P1-10、P1-11、P2、P3 |

## 三模式冲突裁决表

| 场景 | default | lite | strict | 共同验收／归属 |
|---|---|---|---|---|
| 清楚的小任务 | 按需调查、修改和聚焦验证 | 短清单逐项完成 | 完整适用 Gate | 不缩减明确交付；P0-10、P1-18 |
| 普通任务缺非必要 Skill／图／索引 | 换可用方法继续相关安全工作 | 同左，清单标注局限 | 必需 Gate 未满足就不报通过 | 不伪造工具调用；AC-02/23 |
| 危险迁移缺备份或授权 | 暂停危险动作 | 暂停危险动作 | 暂停危险动作 | 模式不能放宽数据安全；AC-17/18/29 |
| 用户明确要求 PRD／BDD／报告 | 完整交付 | 完整交付 | 完整交付 | 明确需求优先于轻量偏好；AC-23 |
| 完整 grill 已执行 | 必须调用具名 DDD reviewer 并可见通过；缺失 blocked | 同左 | 同左 | D-IMP-06 收紧共同后置门禁；不以访谈内建模或替代检查冒充；P0-04/05 |
| 已进入正式验证 | 满足对应报告／隐私契约 | 同左 | 同左并完成适用 Gate | 运行失败与报告是否生成分别记录；AC-14 |
| 用户明确只读 | 对话内状态，零持久写入 | 同左 | 同左，不冒充完整开发流程 | 不运行会写缓存／接线的查询；AC-27 |
| 用户拒绝模式建议 | 保存选择，继续原模式 | 同左 | 同左 | 无新实质风险不重复劝升；AC-22 |
| 同一任务继续／恢复 | 继承任务已确认模式 | 同左 | 同左 | 分支冲突独立确认；handoff 不覆盖 task；AC-24/28 |
| 缺 lessons 名字 | 不猜名，相关 lesson 暂未保存 | 同左 | 必需 lesson 未完成则 Gate 未完成 | 身份不足不授权创建整套环境；AC-25 |

## 旧强制句子的迁移落点

P0-02 不提前改现行模板。后续任务须同时处理相互引用的入口，不能只添加一个 mode router：

1. **P0-04／P0-05**：新 sbtd-task 与 global/project 公共入口持有模式路由；before/check/finish 的完整流程放 strict reference。
2. **P1-09**：book reviewer、BDD、project-validation、Knowledge、Maestro、SEO 等 bundled caller 的无条件触发按模式裁决；Skill 内真实执行协议不被调用强度变化削弱。
3. **外部 stable 镜像**：只读保留；出现旧工具或无条件流程文字，由 SBTD caller 界定是否调用，不 fork 或批量替换镜像。
4. **P1-14／P1-15**：分别证明机器可检查契约与真实 host×mode 行为；文本匹配成功不代表 LLM 已按流程执行。

## 验收方式与局限

复用现有 `python3 -m unittest discover -s tests -p 'test_*.py' -v` 获取开发起点的行为基线；现有测试中既有实际 Python／Bash fixture，也有文本和 schema 断言，证据级别按真实检查区分。另运行隔离 HOME、两个临时项目的真实 `check-projects --json`，证明逐项目单 JSON 输出、不包含全局检查、项目与 HOME 零写入；`/bin/bash -n install.sh` 只证明语法。

本项不添加复述模板文字的永久测试，不改现有测试以迎合尚未实现的 v2。旧工具专用断言在对应实现任务切换时按行为迁移；有真实安全价值的负面回归保留，纯措辞断言不因本次基线通过而取得永久保留资格。

尚未证明的范围：Codex/OMP 实际模型执行、Windows PowerShell 真执行、Graft 升级／断网、迁移／恢复、用户环境切换、token 收益与 P3 观察。P0-02 只验收行为基线及模式保留契约，不宣称这些后续 AC 已通过。

## P0-02 运行证据

- 原生命令全量基线：首次诊断 267 tests / 167.158s / OK；正式报告轮次 267 tests / 73.575s / exit 0。两轮均无失败 case；不是两轮不同覆盖范围。
- 正式本地原始报告：`tests/api/reports/api-report-sbtd-baseline-p0-02-behavior-baseline-2026_09_17-13_19_47.json`，同 stem 中文 `.md` 列出全部 267 个 case、运行时间、命令、URI not-needed 矩阵及限制。
- 真实只读 CLI smoke：两个隔离项目，单 JSON、逐项目结果、无全局检查、隔离 HOME／项目零写入，exit 0。原始 stdout/stderr 及开始／结束时间包含在上述 JSON。
- `/bin/bash -n install.sh` exit 0；既有 Bash fixture 由全量套件执行，PowerShell 部分静态检查不能冒充 Windows 真执行。
- 报告身份：`developer-local`、source ref `p0-02-behavior-baseline`、起点 SHA `34a15499e8c13301ec5da7cf172bd9a94915a73d`、`worktreeState=dirty`（仅任务文档）、`environmentAlignment=unverified`、`evidencePublication=local-only`。不作为最终 PR head／CI 的正式发布证据。
- `rtk: skipped-for-report`；正式报告使用原生 subprocess 捕获结果。报告由既有 `.git/info/exclude` 的 `tests/api/` 规则保持本地，不改项目 `.gitignore`。

README.md、README.html、版本化 automation prompt 与 CHANGELOG 本项均不改：P0-02 只交付基线／契约清单，不改变现行安装、工具路由、产品能力或发布门禁。后续实现按主 PRD P1-11 同步实际受影响入口。
