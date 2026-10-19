# Graft 0.22.0 strict 验收

## 结论与边界

本轮**源码、独立安装包及隔离运行路径验收通过**。独立代码与安全复审均无剩余 findings。安装阶段用户明确选择新的独立前缀并保留现用配置；本次不切换 live MCP、PATH、stamp，不同步已安装 Onboard，不提交／推送／发布，不清理旧运行时或中断目录。

当前分支 `feat/graft-pin-0.22.0`，基线 SHA `3e13f97b28fa29bcfb1c17d5f1e60b445228ce45`。实际被测对象是 dirty 工作树，完整实现／测试文件指纹保存在 `reports/acceptance-20261015-181205/source-fingerprint.json`；全量运行前后相同。后续 task／lesson 记录不是新的生产代码修改。

首次实现之前没有按用户明确要求建立 strict 任务和完成前置门。这是执行偏差，已保留补录时间；下面的补验结果不倒填为历史前置门通过。未完整调用 grill-with-docs：固定包身份与安装／切换授权已明确，无新领域歧义；DDD 为 not-required，不虚构 DDD Boundary Review。

## 验收矩阵

| 验收项 | 证据 | 结论 |
| --- | --- | --- |
| 固定发布身份、URL、integrity；不伪造 gitHead | registry-tarball-proof；官方 0.22.0 JSON + tarball；661 个文件与新安装包逐字节一致 | 通过；gitHead 缺失如实保留 null，未声称验证 npm 发布者签名 |
| 官方 npm bin 可用；包外 shim 不执行 | 公共 check_graft 行为测试；真实 installed CLI；全量 unittest | 通过 |
| canonical 接线生成／消费一致 | all-binding-contracts：真实 verified_runtime → Codex MCP／OMP MCP／Codex hooks 渲染及 ownership 校验 | 通过；继续写同包 dist/cli.js |
| 旧运行时、旧 stamp fail-closed | old-runtime-refused、old-stamp-refused；实际 exit 2、固定错误、旧 stamp 字节保留 | 通过 |
| 确认门、遥测关闭、无隐式云能力 | 原受管安装报告；确认门／telemetry 单元测试；网络拒绝沙箱下 build/MCP/query/hook | 通过本轮范围；不声称永久网络沙箱已部署 |
| 品牌、自动接线迁移不受父环境操纵 | brand-before-fix-canonical-probe → brand-after-fix；helper + PATH Trail + hostile brand 的原生 MCP／hook | 通过；TRAIL_* 隔离，固定 graft/no-fetch/no-switch |
| 新 notes/skills 数据面不越界 | 笔记树、祖先 checkout、非 Git 根子 checkout、技能链接／hardlink／FIFO RED/GREEN；native-mcp-note-tamper | 通过；启动和每请求均校验 |
| 结构图可用，而非只有 --version 成功 | native-build、native-check；MCP file_api、trace_calls、find_code 返回合成项目符号与调用者 | 通过；graph.ok=true；未生成概念图，context.missing 不冒充完整概念图通过 |
| 独立审查 | review.md；PinCodeReview 与 PinSecurityReview 的最终复审 | 无剩余 findings |
| 项目完整本地回归 | full-unittest-clean-env | 2142 项执行，OK，原生 skipped=30，exit 0 |

官方证据：<https://registry.npmjs.org/@nanonets/graft/0.22.0>；<https://registry.npmjs.org/@nanonets/graft/-/graft-0.22.0.tgz>。源码迁移到 `trailhq/Trail-Code` 和 registry 缺少 gitHead 已由本任务用户接受，不从不同仓库的 tag 拼造 SHA。

## DDIA Data Design Review

- Status: **confirmed**。
- Data owner and source of truth：仓库固定包常量及策略资产；受管部署写 stamp，launcher 读包身份、stamp、图及新 notes/skills 输入。
- Write / read / async / failure paths：安装写独立前缀；受管 build 才写被选项目图／stamp；MCP/hook 先证明当前范围。拒绝发生在 native 子进程／请求转发前；不自动修复旧 stamp。上游自动 Trail 迁移被显式禁止。
- Consistency model：每次启动及 MCP 请求新鲜验证，状态不符即 fail-closed；没有引入跨进程缓存或声称无竞态的 filesystem CAS。
- Idempotency / ordering / retry / deduplication：安装计划先核对前缀，同一子进程环境执行 --yes；复验为 already-installed。失败记录保留，不自动覆盖未知部分安装。
- Schema / migration / backfill / rollback / replay：不改变持久 schema；策略摘要随资产变更。旧 runtime/stamp 不混用；新旧前缀共存，live 切换与整组回滚仍单独设计／授权。
- Observability and repair：真实 stdout/stderr/exit、固定拒绝错误、报告中的 before/after 保全。恢复不能手改 stamp 绕过守卫。
- Required tests：政策／binding／brand／notes 拒绝路径和原生 smoke、完整本地 unittest，均见验收矩阵。

## Legacy Change Safety Review

- Status: **characterized**；Review mode: **normal**。
- Behavior to change：晋升固定包身份、接受官方 npm 入口，并约束新版原生输入／自动迁移面。
- Behavior to preserve：确认门、SRI 校验、DNT、private HOME、canonical 持久绑定、逐请求守卫、旧版拒绝、无自动接线／云操作。
- Current reproduction evidence：实际复现策略摘要 state-conflict、binding ownership 拒绝、brand=trail/switch=true，以及笔记／技能范围拒绝缺失；临时探针语法和 canonical 路径错误单列，不算产品 RED。
- Safety net：保留既有行为测试，新增 notes/skills 实际安全边界回归；原生包 smoke 直接执行消费者，不依赖复制版本常量。
- Hidden dependencies / seam：上游新增 Trail env、notes 与 skill lookup；复用已有 `_contained`、nofollow tree 和 request guard。没有新增测试专用生产 seam。
- Validation plan/result：修正前 RED、修正后 GREEN、真实路径 smoke、完整本地回归完成。首次实现没有红灯先行的历史缺口仍记录，不声称整项最初符合 TDD 顺序。

## Refactoring Review

- Status: **proceed**；Review mode: **normal**。
- Existing-code scope：runtime 环境隔离、launcher 输入范围、策略常量与相关测试。
- Behavior that must remain unchanged：持久绑定与 ownership 合同、root 和 DNT 边界。
- Structural friction：此前增加的入口候选选择改变了持久合同且无必要，已撤回。
- Decision and smallest safe step：沿用 canonical cli.js；新增单职责 notes scope helper，复用既有路径／树验证；不扩展 ownership 接受范围，不改 vendor。
- Safety net and validation：现有配置消费者、原生 build/MCP/hook、scope 回归与全量 unittest。
- Deferred refactors：无本任务必需的剩余重构。Code Readability 与 Ponytail 最后审查无额外整改项。

## 验证轮次与正式证据

报告目录：`reports/acceptance-20261015-181205/`。执行记录每项有 `.json` 原始 argv/stdout/stderr/exit 和同 stem 中文 `.md`。`source-fingerprint.json` 与 `ruff-baseline.json` 为辅助证据，不伪装为测试 runner 报告。

- 定向影响集：158 项，exit 0，2 skipped。此轮在最后的有效 notes-root 修正之前；最终完整范围覆盖全部最终代码。
- notes/root/skills 最终定向回归：5 项，exit 0，保留之前直接树 5 个及有效根／技能 6 个失败子场景。
- 全量首轮：2142 项，1 failure、30 skipped，exit 1。原因是执行者给 smoke 设置的 PYTHONPATH 被带入测试子进程，导致删去模块的安装副本从源仓补载模块；不是 pin 产品缺陷，也没有删除该回归过门。
- 移除 PYTHONPATH 后：失败项 1 项通过，所在模块 5 项通过；相同完整范围再次运行 2142 项、OK、skipped=30、exit 0。原生 skip 是事件统计，未简单相减伪造父用例成功数。
- 全量命令：使用已有受管 Python 执行 `python -B -m unittest discover -s tests -p 'test_*.py'`，正常 umask 022；最终测试环境不含 PYTHONPATH。
- `ty check` 三个受影响生产模块：exit 0。
- `ruff check --no-cache`：最终仍有 6 项既有诊断，与 HEAD 同文件诊断比较新增为 0；首次新增 B023 已修正。未宣称整个文件集 lint 全绿，也未夹带基线清理。
- `/bin/bash -n install.sh`、PowerShell parser：exit 0。macOS pwsh 不等于 Windows 原生证明。
- 真网络正反控制：普通 loopback bind 成功；sandbox-exec deny network 下同一操作 PermissionError。相同网络拒绝沙箱中原生 build、MCP、source query、hook 均成功。
- Markdown／本地链接与双语未发布条目技术标识校验通过，已发布 CHANGELOG 历史字节保持。第一版文档检查错误地要求翻译中技术标识顺序相同，改为逐条目集合核验后通过；原失败保留。

## BDD、工具与发布边界

- BDD: **traceable**。场景位于 `sbtd-workflow-onboard/REFERENCE.md#graft-pin-acceptance-scenarios`；中文场景 + 英文关键词，不生成 .feature，不引入新 runner。
- Cross-repo context: **not-needed**（单仓受管集成；精确上游包作为外部依赖证明）。
- API Contract: **verified**（真实 stdio MCP initialize/tools/list/tools/call）；无业务 HTTP API。
- Mock Strategy：单元测试沿用契约型隔离夹具；原生包 smoke 为 **none**。
- Web/Mobile 工具：**not-needed**，本次没有 Web/Mobile UI。
- rtk: **skipped-for-report**；原生执行保存完整证据。LSP 实际调用返回无语言服务器，使用源码／消费者合同和运行证据补充。
- Evidence Source: **developer-local**；Source Revision: **dirty**；Evidence Publication: **local-only**。
- Windows／Linux 原生 CI、其他架构、真实宿主重新加载：本轮未执行，不将本地全量或已安装包成功扩张为这些证明。

## Release Readiness Review

- Status: **ready（限定当前源码与本机独立运行时验收）**。不是正式版本发布就绪声明；跨平台 CI 与 live 部署仍有各自门禁。
- Production path and affected users/systems：受管 Graft installer、构图、分析、MCP 和 Codex hook；当前真实宿主仍运行旧版本，未更改它们。
- Failure modes and safeguards：错误包／stamp 拒绝；策略内容绑定；父环境污染隔离；自动 Trail migration/fetch 禁止；越界 notes/skills 拒绝；请求间变化新鲜验证。npm 退出0不单独算成功。
- Capacity/backpressure/limits：沿用现有超时、stdio 有界行／backpressure 与每请求检查；note 子 checkout 按上游排序过滤后最多64个，树校验复用现有 nofollow 原语。无服务扩容／队列迁移。
- Observability/alerts/runbook：固定错误与原生报告；新包部署应走受管流程，不通过手改 stamp、放宽 ownership 或直接修改 live 配置消除拒绝。
- Rollout/migration/rollback/cleanup：新前缀与旧运行时保留，尚未 live cutover，因此当前用户运行链无需回滚；以后切换必须同时安排 launcher、CLI、图/stamp 与配置的匹配及备份。旧前缀、中断目录与备份均不清理。
- Required validation/result：本轮必需本地回归、拒绝边界、真实原生 smoke、独立复审已通过，源码指纹冻结。
- Optional checks/accountable owner/residual risk：没有把本轮必需项豁免为 residual risk。跨平台发布和现用宿主切换是用户明确分离的后续交付层级；不上报为已通过。现存 Ruff 基线诊断独立保留，本轮新增为0。

## 文档维护与经验

- `README.md`、`README.zh.md`：同步新增受管 Graft／Trail 隔离和新读取范围说明及场景入口。
- `CHANGELOG.md`、`CHANGELOG.zh.md`：Graft 晋升仍在 Changed／变更；补充 canonical 绑定、环境防护、数据面约束及策略摘要。两份逐条同义，已发布章节不改。
- `prompts/automations/sbtd-workflow-tools-version-check.md`：入口无需改，原本已路由 Graft 主题到 impact reference；实际更新 `references/version-check-impact.md` 对新增品牌／迁移／读取面的评估要求，不扩大自动化写权限，不接触 live automation。
- Onboard REFERENCE：更新明确的入口／环境／notes scope 合同及持久场景。
- Lessons split name: **kuno**；Source: **.sbtd/developer**，由已安装 DeveloperStore 只读解析为 ready。
- 新增经验 `LESSON-20261015-kuno-pin-promotion-contract-closure` 和 `LESSON-20261015-kuno-strict-record-before-edit`，正文仅在 `docs/lessons/topics/repository-workflow.md`，索引在 `docs/lessons/index.md`；不改他人 marker 或复制旧正文。
