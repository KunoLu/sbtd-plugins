---
schema_version: 1
id: graft-pin-0.22.0
workflow_mode: strict
mode_source: user
mode_note: 用户声明初始即要求 strict。记录在实现开始后补写；补写前的源码改动不是 Gate 通过证据。
status: "in-progress"
branch: feat/graft-pin-0.22.0
created_at: '2026-10-15T16:57:23.053098+08:00'
updated_at: "2026-10-15T22:53:34.332846+08:00"
completed_at: null
"blocked_reason": null
---
把受管 Graft pin 从 `@nanonets/graft@0.21.1` 晋升到已核对的 `0.22.0`。

用户从一开始就明确要求 strict，但执行者漏做了任务持久化：没有 `ai/tasks/graft-pin-0.22.0/`，活动指针仍指向已完成的无关任务 `commit-repository-maintenance-main`。本记录是补写，不把补写前的源码改动记成 Gate 通过。

未完整调用 grill-with-docs。pin 身份、tarball integrity、`gitHead` 缺失，以及 npm bin 改为 `dist/bin/graft.js`，已由 registry 包内容和用户明确授权“更新仓库 pin，并更新本机已签约的 Graft”回答。没有新的领域歧义，因此不把本次补记伪装成 grill 或 DDD Boundary Review。

## 范围

- 仓库 pin：`GRAFT_PINNED_VERSION`、tarball URL、integrity；`gitHead` 缺失则不再保存 SHA。
- 身份校验接受包内 `dist/cli.js` 或 `dist/bin/graft.js`，仍拒绝 shell shim。
- 当前文档、安装回退、策略、契约测试与未发布 CHANGELOG 同步到 `0.22.0`。
- 用户先选择新的独立运行时目录并完成源码／隔离运行时验收，随后明确授权 MCP、PATH、stamp 切换，并补充授权对齐已安装 Onboard；本机切换范围与结果见 [cutover.md](cutover.md)。不把两阶段的授权或验收混为一谈。
- commit、push、tag／Release仍待最终确认，不授权sync或live automation变更。用户最新要求评估并清理冗余Graft安装目录；删除仅限展示实际清单并确认后的范围，备份销毁未授权。
- 历史 PRD、已发布 CHANGELOG、`graft-pin-0.21.1` 任务记录不改写。

## 验收

- pin、tarball URL、integrity 与 npm registry `0.22.0` 一致；不使用 latest，不伪造 gitHead。
- 官方 bin `dist/bin/graft.js` 能通过身份校验；shell shim 仍 fail-closed。
- 旧 `0.21.1` stamp / 错版本 CLI 在新 pin 下 fail-closed。
- 受管安装仍须显式确认，遥测保持关闭，不启用 LLM/cloud。
- 定向测试与本机安装探针绑定实际 SHA、worktree 和环境。

## Book Gate Plan

记录初建时适用 Gate 均未执行。以下为随后实际补验结果；首次实现早于前置门的历史偏差保留，未倒填时间。详情见 [check.md](check.md) 和 [review.md](review.md)。

| Reviewer | 客观触发／阶段 | Lifecycle | 实际结果与证据 |
|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill 或领域歧义，需求确认前 | not-required | 未完整调用 grill，pin 身份和本轮边界明确；不虚报 DDD review |
| book-ddia-data-design | pin／策略／stamp 跨进程持久合同，设计确认 | passed | confirmed；拒绝旧版本，不改现用 stamp；策略实际字节与消费链验证 |
| book-legacy-change-safety | 修改已有身份／原生启动守卫，修正前 | passed | characterized；策略、binding、品牌、笔记范围均有 RED/GREEN 和真实 smoke |
| book-refactoring-pass | 既有生产代码修改，修正前 | passed | proceed；保留 canonical 路径，复用既有 containment/nofollow，不引入替代架构 |
| book-release-readiness | 本轮源码和独立安装包，最终验证后 | passed | ready（限定本轮验收范围）；2142 项全量 exit 0，30 skip；非跨平台发布或 live 切换证明 |

## 已开始但未验收的实现

分支 `feat/graft-pin-0.22.0`，起点 `3e13f97b28fa29bcfb1c17d5f1e60b445228ce45`。补记前工作树已有 pin、文档、安装回退和测试改动。这些改动保留，但不构成 strict 前置门通过。

## 独立前缀安装结果（2026-10-15）

- 用户在安装目标选择中明确选择「新的独立运行时目录」；本轮仅安装，不改 MCP、shell PATH、stamp，不清理旧目录。
- 新前缀为 `~/.local/share/sbtd/runtime/graft-0.22.0-managed`。保持真实 HOME，仅子进程设置 `NPM_CONFIG_PREFIX` 和 PATH；受管计划确认目标前缀及真实遥测路径后执行 `install-graft --json --yes`。
- 安装 exit 0、`status=installed`、`after.status=available`、版本 `0.22.0`；官方 bin 解析到 `dist/bin/graft.js`。相同环境下不带 `--yes` 复验 exit 0、`already-installed`。
- 遥测原已关闭，安装结果 `changed=false`。Codex/OMP 配置、zshenv/zshrc、npmrc、仓库 stamp 和遥测文件前后字节一致；旧运行时包仍为 `0.21.1`。
- 原始安装结果及同 stem 中文汇总：`reports/managed-install-20261015-180026.json`、`reports/managed-install-20261015-180026.md`（本地忽略，不发布）。
- 纠正此前测试统计：历史原生结果为 154 项执行、2 项跳过，其余 152 项成功；本轮没有重跑该测试。
- 当时安装完成不等于现用宿主切换，任务保留 in-progress；后续 strict 验收结果见下节，不把安装补记成此前 Gate 已通过。

## Strict 验收结论

- 当前实现、独立运行时及独立审查已完成本轮验收。全量首次失败由 smoke 用 `PYTHONPATH` 污染隔离测试引起；移除该变量后，失败项 1 项、所在模块 5 项及相同完整范围 2142 项均通过，原生 skip 30；前后源码指纹一致。
- 两位独立只读 reviewer 最后结论均无剩余 findings；父执行者唯一负责运行证明。真实网络拒绝沙箱、原生 MCP/query/hook、旧运行时／stamp 拒绝和请求间笔记篡改均已验证。
- 正式记录：[check.md](check.md)、[review.md](review.md)；原始报告及同 stem 中文汇总在 `reports/acceptance-20261015-181205/`。Evidence Source 为 developer-local，Source Revision 为 dirty，Evidence Publication 为 local-only。
- 上述源码验收完成时未包含 live 接线和安装副本对齐；后续独立授权的现场切换见下节。跨平台 CI 与正式发布仍未执行；旧运行时与中断目录继续保留。

## 追加授权后的本机切换

- 用户授权切换 MCP、PATH 和 stamp，并在已安装0.21.1 launcher拒绝新包后，明确选择「对齐 Onboard 后继续」。同一 strict 任务通过 TaskStore 重开，保留此前完成事件。
- Onboard原生upgrade为1替换／32保持；Codex provider先切换，OMP按新前态重新计划后切换，最终三者均aligned。launcher绑定已安装包，而非仓库或暂存执行器。
- 两处zsh PATH各只替换旧前缀；普通／交互／登录shell实际解析到新运行时0.22.0。本仓stamp由已安装的受管构图生成0.22.0，结构图freshness为OK。
- 两份真实MCP配置的command/args/env均通过新进程协议smoke：graft0.22.0、六工具、当前仓库代码查询和结构freshness成功；查询前后图／配置不变。其他MCP配置语义保持，其他Skills未更新。
- 两位独立reviewer对切换计划／回执／恢复证据复核无剩余findings，Release Readiness为ready（本轮现场范围）。没有证明旧宿主会话重载，也没有执行真实回滚。
- 本地原件、回执、失败、恢复计划和同stem中文汇总：`reports/cutover-20261015-195645/`；完整交付及恢复顺序见 [cutover.md](cutover.md)。整个私有批次须保留。未sync、commit/push、发布或清理；未扫描其他账户／项目。

## npm 默认全局统一（追加需求）

- 用户最新目标改为npm默认全局0.22.0，而非独立前缀；同时要求统一本机已配置环境及此前四项目，评估冗余安装并在全部完成后确认v2.0.2发布准备。
- 已完成npm默认全局安装、普通／已知Orca Codex及OMP绑定、zsh解析和四项目Graft围栏／结构图；15次宿主配置×仓库新进程验证通过。源码及业务代码未改，项目分支／HEAD和围栏外正文保留。
- 三个独立目录已完整归档；用户批准精确清单并重载后，实际复查无进程／打开文件／配置引用，内容与归档一致，现均已删除。归档、受管Python、Onboard及历史备份保留；未结束用户进程。
- 当前进度、独立审查和发布前置见 [global-consolidation.md](global-consolidation.md)。精确四项目／宿主范围、原件、回执及报告在私有批次 `~/.local/share/sbtd/cutovers/20261015-211351-graft-npm-global-bupzmkzh/`。
- 删除后npm全局版本、三种zsh、15次已配置MCP组合及本会话MCP调用均通过。本机工作完成；发布仍缺包含当前修改的最终提交及其精确SHA CI，向用户单独确认提交／PR／tag／Release准备。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-15T16:57:25.832904+08:00 | planned | in-progress | 用户要求补写 strict 记录；pin 实现已开始但验收与 Gate 均未完成 | feat/graft-pin-0.22.0 工作树已有未提交 pin 改动；无 graft-pin-0.22.0 目录是本次补写前的事实 |
| 2026-10-15T18:54:42.505352+08:00 | in-progress | checking | 独立代码与安全复审发现已关闭；进入冻结源码的最终验证，保留首次全量的环境污染失败 | review.md; reports/acceptance-20261015-181205/ |
| 2026-10-15T19:25:22.463939+08:00 | checking | done | 用户确认的新独立前缀及当前源码 strict 验收完成；最终本地全量2142项通过，独立复审无剩余发现；live切换与发布不在本轮范围 | check.md; review.md; reports/acceptance-20261015-181205/full-unittest-clean-env.json |
| 2026-10-15T19:51:18.152936+08:00 | done | planned | 用户新增授权切换MCP、PATH和stamp；保留此前源码验收完成事件 | 用户本轮明确授权；check.md记录此前未切换现场 |
| 2026-10-15T19:51:23.776856+08:00 | planned | in-progress | 开始切换前态和已安装launcher兼容性核对；未修改live配置 | 已知Codex/OMP MCP及zsh PATH仍使用旧运行时 |
| 2026-10-15T20:16:45.650869+08:00 | in-progress | checking | 追加授权范围内Onboard/MCP/PATH/本仓stamp均已切换；新shell和真实配置MCP验证通过，独立复核无剩余发现 | cutover.md; reports/cutover-20261015-195645/ |
| 2026-10-15T20:16:51.564326+08:00 | checking | done | 本机切换验收完成；原件和只读恢复计划已验证；未强制重载旧会话或发布，旧环境保留 | cutover.md; reports/cutover-20261015-195645/configured-mcp-smoke-final.json; vault recovery plans |
| 2026-10-15T21:09:47.440422+08:00 | done | planned | 用户改为npm默认全局0.22.0并要求本机统一、恢复四项目范围、评估冗余目录及发布前确认 | 本轮用户明确需求；删除须展示实际候选后确认，tag/Release待最终确认 |
| 2026-10-15T21:09:53.282183+08:00 | planned | in-progress | 沿用strict推进npm全局统一；已从历史任务恢复四个项目，先核对前态和既有宿主域 | .sbtd/tasks/four-project-v2-preparation/task.md; .sbtd/tasks/official-rc3-four-project/task.md |
| 2026-10-15T22:03:36.486621+08:00 | in-progress | blocked | npm全局统一、三宿主配置和四项目图已通过；三个独立目录删除已获清单确认，但旧tokens及本仓MCP仍占用，等待用户重载后复验删除；不授权结束进程 | global-consolidation.md; private global batch cleanup-authorization.json and cleanup-post-consent-check.json; 15 configured MCP proofs |
| 2026-10-15T22:42:43.065681+08:00 | blocked | in-progress | 用户重载后实际复查三个候选无进程或open-file占用，配置无旧目录引用，归档和目录内容均匹配；沿用已批准清单 | global-consolidation.md; private batch cleanup-ready-20261015-224222.json |
| 2026-10-15T22:47:09.296523+08:00 | in-progress | checking | 重载后无旧引用，三个批准目录已删除且归档完整；npm/zsh和15组合及当前MCP复验通过 | global-consolidation.md; cleanup-execution-20261015-224309.json and verification |
| 2026-10-15T22:47:15.269003+08:00 | checking | done | 本机npm全局统一、四项目图和获准清理完成；发布准备确认单独进行，未commit/push/tag/Release | global-consolidation.md; private batch cleanup reports and retained archive proofs |
| 2026-10-15T22:53:28.360123+08:00 | done | planned | 用户授权提交推送PR、CI通过后合并，并在确认MERGED后删除本地和远程开发分支；tag/Release仍待确认 | 用户本轮授权；源码及本机部署已完成验收 |
| 2026-10-15T22:53:34.332846+08:00 | planned | in-progress | 开始发布写集和隐私核对，仅640-skills仓库，不提交四业务项目或私有报告 | feat/graft-pin-0.22.0 branch; git status; gh repo identity |
