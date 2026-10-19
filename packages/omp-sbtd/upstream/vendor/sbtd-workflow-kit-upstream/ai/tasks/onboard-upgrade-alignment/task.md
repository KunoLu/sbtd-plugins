---
schema_version: 1
id: onboard-upgrade-alignment
workflow_mode: strict
mode_source: user
mode_note: 用户明确要求在新开发分支以 strict 完成已确认四阶段方案；本机应用、同步、旧资产清理、新分支合并及发布未授权。
status: "done"
branch: feat/onboard-upgrade-alignment
created_at: '2026-10-03T22:31:25.791160+08:00'
updated_at: "2026-10-05T18:38:11.700246+08:00"
completed_at: "2026-10-05T18:38:11.700246+08:00"
---
# Onboard 通用升级对齐、恢复与分层验收

## 授权与范围

用户确认完整四阶段方案。PR #109 经本轮明确 admin 授权合并为 f24fe3b59beb584e39a53683840a3be5c79ffe58；本地及远程旧分支已删除。本任务基于合并后的 main，新分支 feat/onboard-upgrade-alignment，禁止本机应用、同步、旧资产实际清理及新分支合并发布。

实现固定基线、完整内容差异、多配置域、upgrade plan/apply/verify、恢复、自升级、九个 GitNexus Skills 清理能力、运行时与 PATH 检查、真实宿主分层验收、两安装器和文档。现有 init/reset/migration 授权含义保持。

需求已由前轮方案确认，未完整调用 grill-with-docs；使用明确术语与持久行为场景，无额外领域假设。规格与门禁见本目录 design.md；持久场景见仓库 Onboard REFERENCE 的升级章节。

后续明确授权与信任选择见 [decisions.md](decisions.md)：允许提交/推送本分支及创建草稿 PR 运行三平台 CI；仍不合并或发布。私有 vault 由操作人独占管理并作为受信历史，hash 不抵御拥有写权限者整组伪造历史。隔离真实 host probe 不等于原GUI重载。

本轮审查修复沿用strict。用户补充确认保留R03/R09/R11/R12现有契约，纠正原审查；实际修复其余15项。独立跟踪、持久场景、开发前门禁与原始失败证据见[review-fixes.md](review-fixes.md)，用户选择见[decisions.md](decisions.md)。下方原始“19项”状态事件属于不可改写历史，不表示当前仍实施四项已撤回的行为变更。

第二轮审查（head 40b0dbf）保留14项，用户要求先修P1、再依优先级修复其余13项，已按顺序完成并修正独立复核两处路径遗漏。沿用strict，独立编号N01–N14及本轮证据见[review-round2.md](review-round2.md)，不覆盖上一轮历史。本地完整验证、两切面独立复核、真实隔离宿主／重试／恢复及36ee62e精确三平台CI全部通过；本机部署、同步、清理、合并和发布均未执行。

第三轮审查（head 1ae9c321）13项按用户要求先修三个P1，再依风险顺序完成其余项及独立复核／原生Windows反馈修正；独立编号T01—T13与本轮门禁／证据见[review-round3.md](review-round3.md)。本地1762项完整验证、317项升级回归、真实隔离生命周期、独立复核和7d360b6精确三平台CI全部通过；不覆盖两轮历史，未部署、同步、清理、合并或发布。

第四轮审查（head 2b913a66）7项及独立复核／原生CI反馈均已修复，F02覆盖计划与升级／恢复执行环境，F07完整目录边界与zsh数组均保持。证据见[review-round4.md](review-round4.md)及[check.md](check.md)：最终本地1771项、326项升级子集、真实37资源生命周期、两切面独立复核及`acaf83a39679f1f6605d54a9b6ce43847b3bbe31`精确三平台CI全部通过。早期失败与输入污染机制证据保留，不放宽守卫；未部署、同步、清理、合并或发布。最终记录提交另验自身CI。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-03T22:31:26.747654+08:00 | planned | in-progress | 已完成旧分支合并清理，在新分支启动获批 strict 实施 | PR #109 MERGED; 用户已确认四阶段方案 |
| 2026-10-04T08:19:54.113257+08:00 | in-progress | checking | 完整升级与恢复及真实隔离宿主已验证，进入最终回归与精确head三平台CI | final-native-*报告；公开installed-copy跨路径retry/recovery回归通过；独立复核已修正 |
| 2026-10-04T10:14:38.220261+08:00 | checking | done | 四阶段实现、隔离CLI及真实host证明、独立复核和精确代码提交三平台CI全部完成；未部署或发布 | befa24eb7ef68c884a125af313528551b7d97af0; GitHub run 37168994920; ai/tasks/onboard-upgrade-alignment/check.md |
| 2026-10-04T12:37:01.748191+08:00 | done | planned | 用户要求修复PR #110审查保留的全部19项问题 | 本轮用户明确修复授权；审查基线ac34ee4 |
| 2026-10-04T12:37:03.495081+08:00 | planned | in-progress | 沿用strict，恢复开发前门禁并逐项闭合19项审查问题 | PR #110的19项最终审查清单 |
| 2026-10-04T19:27:13.033399+08:00 | in-progress | checking | 15项修复及4项保留契约已核对，冻结源码进入全量与精确head三平台验证 | review-fixes.md; final-native-upgrade/installed-host/recovery报告;287项升级回归及末次host131项通过;独立复核已收口 |
| 2026-10-04T20:32:45.703308+08:00 | checking | done | 15项修复及4项保留契约完成，原生隔离闭环、独立复核与精确代码提交三平台CI通过 | 99afbe89266ed4da456fd315f969caa0655d654f;GitHub run37200497908;check.md;review-fixes.md |
| 2026-10-04T22:27:35.132581+08:00 | done | planned | 用户要求优先修复新审查P1并依优先级修复其余13项 | PR110 head40b0dbf；本轮14项审查及用户修复授权 |
| 2026-10-04T22:27:37.106458+08:00 | planned | in-progress | 沿用strict，按P1、路径事务、验证协议、Shell、CLI顺序修复 | 本轮修复范围明确；旧四项契约保留 |
| 2026-10-04T23:26:17.258511+08:00 | in-progress | checking | 14项顺序修复完成，局部回归和真实隔离宿主及恢复已通过，冻结实现进入完整验收 | review-round2.md；302tests；native-round2-*；原生Windows仍待CI |
| 2026-10-05T01:06:13.545781+08:00 | checking | done | 第二轮14项及独立复核遗漏全部修复；本地完整验证、真实隔离闭环和精确三平台CI通过 | 36ee62eb362ec671552eaf971815e1bb43b12441；GitHub run37216126160；review-round2.md；1750tests；305升级回归 |
| 2026-10-05T09:04:33.152975+08:00 | done | planned | 用户要求先修复第三轮三个P1再依风险顺序修复其余10项 | PR110 head1ae9c321；第三轮13项审查；用户明确修复授权 |
| 2026-10-05T09:04:35.203059+08:00 | planned | in-progress | 沿用strict，真实复现后依优先级修复 | 第三轮13项清单；原四项契约保留 |
| 2026-10-05T10:25:09.830888+08:00 | in-progress | checking | 第三轮13项及独立复核修正完成，真实隔离生命周期已通过，进入完整项目与精确head CI | review-round3.md；317tests；native-*；原生Windows待CI |
| 2026-10-05T12:24:31.867839+08:00 | checking | done | 第三轮13项、独立复核及Windows反馈全部闭合；完整本地、真实隔离与精确三平台CI通过 | 7d360b65a2c82926ae683b4518e68cc7b2a2655e；GitHub run37260456824；review-round3.md；1762tests；317升级回归 |
| 2026-10-05T15:02:04.878812+08:00 | done | planned | 用户确认按优先级修复第四轮7项审查问题 | PR110 head2b913a66；本轮7项与用户授权 |
| 2026-10-05T15:02:07.080119+08:00 | planned | in-progress | 沿用strict，按封存范围/依赖/Shell/协议/诊断顺序复现修复 | 第四轮范围已确认；保留既有四项契约 |
| 2026-10-05T16:25:52.744853+08:00 | in-progress | checking | 第四轮7项及独立复核边界修正完成，真实隔离生命周期通过，继续诊断全量followup漂移并准备原生CI | review-round4.md；326升级回归；37资源native生命周期；full失败原始报告保留 |
| 2026-10-05T18:38:11.700246+08:00 | checking | done | 第四轮7项、独立复核与原生CI反馈全部闭合；完整本地、真实隔离生命周期及精确三平台CI通过 | acaf83a39679f1f6605d54a9b6ce43847b3bbe31；GitHub run37291867601；review-round4.md；check.md；1771tests及326升级回归 |
