---
schema_version: 1
id: P3-03
workflow_mode: strict
mode_source: user
mode_note: 用户接受建议，明确选择strict用于v2.0.0最终发布审查
status: "done"
branch: "docs/v2.0.0-release-record"
created_at: '2026-10-14T00:02:56.566903+08:00'
updated_at: "2026-10-14T18:07:35.804056+08:00"
completed_at: "2026-10-14T18:07:35.804056+08:00"
---
# P3-03 最终 readiness、用户确认与 v2.0.0 发布

## 身份、模式与授权

用户要求开始P3-03并选择strict。P3-01/P3-02/P3-05已完成；首个候选PR119获明确授权合并。用户随后批准限定发布流程，并追加发布前全部受影响现行文档、双语v2初始化/v1迁移/init/reset/upgrade提示词及双语CHANGELOG；已明确授权docs/v2.0.0-release-docs分支/本任务rebind/commit/push/PR，独立复核和精确CI通过后仅该PR可管理员合并。稳定tag/Release改为新文档合并后的实际main SHA，须该SHA三平台CI全绿；发布后的docs/v2.0.0-release-record PR及原定同条件合并保留。不改保护规则，不授权本机sync/升级、生产部署、认证修改或备份销毁。
当前工作树已存在主PRD和关联MCP PRD的前序收口修改，保留不重置。目标为v2.0.0；P3-04仍planned，已接受的原位保留责任不变。
未完整调用grill-with-docs：发布目标、依赖、AC和安全合同已在PRD明确，无新领域建模或产品范围设计。

## 验收与验证计划

- 将主PRD AC-01至AC-37、P0/P1/P2/P3证明与当前候选逐项对照，区分历史、复用、新复跑及未通过。
- 核对真实tag/commit/CI与工作树，准备真实未发布说明；不以旧SHA或dirty测试冒充最终tag验证。
- 使用项目原生runner及已有依赖完成适用本机验证、隔离CLI/安装包smoke；三平台CI须精确绑定实际最终候选SHA。
- 独立复核发布范围/证据和安装载荷/文档一致性，合法发现修正后重验；无产品修改不强行新增测试或重构。
- 输出独立Release Readiness Review；required缺失不得改作风险接受。只有ready和用户精确发布确认后才执行发布，核对实际tag/远端/发布状态后登记done。

## Book Gate Plan

| Gate | 客观触发 | 阶段 | 状态 |
|---|---|---|---|
| DDD | 未完整grill、无新领域歧义 | before-dev | not-needed |
| DDIA | 本轮仅审查既有迁移/恢复证据，不设计或修改数据协议 | before-dev | not-needed；若新增迁移/恢复改动立即重评 |
| Legacy safety | 尚无既有行为修复 | before-dev | not-needed；发现需改产品时先刻画 |
| Refactoring | 尚无生产代码编辑 | before-dev | not-needed；不夹带重构 |
| TDD/BDD | 无新增行为，沿用主PRD及既有测试；源仓禁止.feature | check | traceable：AC-01～37映射及既有行为场景；无新增代码不做TDD |
| Project validation | 最终发布候选验证 | check | 实际发布SHA 8f6c469三平台main CI38500935539九job通过；原生报告/聚合核验通过，保留skip；本机686项、5步CLI及双语语义复核通过 |
| Code readability / Ponytail | 无生产diff，仅文档与删除固定中文措辞测试 | check | 无新手写运行代码；Ruff4项既有诊断与基线相同，不顺带重构 |
| Independent review | 发布文档/权限路由及完整双语历史 | check | 两路完整语义复核；只读路由、probe认证前提及5项翻译发现均修正并复审关闭 |
| Release readiness | 正式运行时/安装载荷发布 | finish | ready：实际main已验证，用户授权的v2.0.0 tag/正式Release已发布并读回核验；状态记录PR另行闭环，不移动tag |

## 发布边界

恢复只承诺已验收的受管数据/配置，不承诺旧Trellis可写回退。备份保管与2026-10-27或P3-03前人工复核节点沿用P3-05接受记录。计量不宣称跨模式节省比例；受控host样本不冒充五个独立自然业务任务。其他账户、生产业务部署、secret轮换、全机升级和备份销毁不在发布权限内。

## 候选准备与本机审查（2026-10-14）

- 基础main为`c91a66f1aef83d10db37440768a62811719611fc`。GitHub实际validation run38239933475九个job均success，原生artifacts下载后SHA/成功状态/必需原生用例核验一致；只证明基础提交，不冒充本轮dirty候选。远端已有rc.1～rc.4，尚无v2.0.0；rc.4已有GitHub prerelease。
- 修正双语README过期RC横幅，改为发布tag/CHANGELOG事实源；稳定版未发布章节移至CHANGELOG顶部并说明累计RC范围与证据限制；Onboard SKILL/REFERENCE改为区分能力、版本证据及独立部署授权，不提前声称发布。automation prompt无需改，监控/同步契约未变；未修改生产代码、templates或签名资产。
- 发布内容由ReleaseEvidenceReview和ReleasePackageReview独立只读复核，无新增范围内内容/实现缺陷。Onboard Markdown不进入迁移runtime指纹，但完整upgrade包baseline会变化；旧plan必须按真实包校验，不能用文档变更绕过source-stale。两种指纹的含义不混淆。
- 原生`python -B tests/run_ci.py --platform macos`首轮687项有1失败/20skip：测试期望0755目录被拒绝，但077下实际创建为0700。仅改变子进程umask的定点对照证明077失败/022通过；首轮mask未单独采集，不伪造确切当时值。固定子进程umask022后同范围完整687项exit0、20原生skip，221.500秒；完整Onboard快照前后不变。失败、定点诊断和最终全量分别保留。
- 完整Onboard副本的实际CLI preflight、相同根去重、非绝对路径拒绝及/bin/bash入口smoke通过；临时HOME保持空，副本逐文件一致并已清理。首轮验证器误把重复根当拒绝输入，已按现行规范纠正并保存失败，不改产品。无新增安装/模型请求/真实HOME写入。
- 20个macOS原生skip包含Windows专属路径/PowerShell/Git Bash、大小写敏感卷及opt-in Codex；不当作对应平台通过。最终候选三平台CI仍为必需，历史base CI和本机dirty证据不替代。
- 私有原生报告/中文汇总位于本任务被忽略的`reports/readiness-main-2026_10_14-00_03_03/`：含37AC映射、两路review原文、baseline CI原生报告、首轮失败、诊断、完整复跑、CLI smoke、Release Readiness Review和分阶段publication-plan。不发布raw/HOME/账号/图。
- 既有LESSON-20260930-kuno-umask-sensitive-test-evidence及同日full-suite lesson覆盖本次环境教训，不另造重复lesson。本机准备完成时readiness为blocked；随后用户明确授权候选PR阶段，TaskStore于2026-10-14T07:39:18.007306+08:00将main绑定改为release/v2.0.0。最终精确SHA三平台CI仍待取得，合并/tag/稳定GitHub Release另行确认。

## 发布前关联文档追加范围

- 用户要求完整检查根README和所有受v2发布影响的现行关联文档，并明确补齐双语初始化、v1→v2迁移、init/reset及upgrade各阶段提示词；不是执行这些用户环境操作的授权。
- 首个PR119 head `eb656ebe490b7fac41026e775a9981019228b16d`九job CI38485923170通过，实际merge `4c375d94467917ab1ca752f9635a2b3463b77d97`与审查树一致。因追加文档门，该SHA不直接打稳定tag；新候选必须重新绑定验证。
- 修正现行工作路径图的旧Trellis/GitNexus调度，统一sbtd-task/Graft和按模式方法门；只读仍经过模式/澄清/适用门，仅免除写入。独立复核发现的只读绕路P2已修正并复审关闭。
- host smoke手册不再指导复制真实auth.json，明确旧P1-15 live执行器仍有此代码、不得按该路径做现行真实认证验证；未运行或修改其live逻辑。保留无host单测和受控真实证据边界，AC-20按文本与usage分层，不沿用早期“OMP无usage”或整场input直接对比2k的判断。
- 双语README现有upgrade probe提示词一度误加真实认证前提；按真实实现纠正为免真实认证、无模型请求的隔离加载，真实模型行为smoke另行授权。plan/apply/verify/authorize-link/独立upgrade recovery与实际CLI参数对应。
- 当前源原生upgrade plan→apply→verify aligned→独立recovery plan→apply五步均exit0；只操作新临时Skills/vault，无agents/hosts/shell目标或真实认证，恢复后目标移除且计划/回执保留；证据保存后临时现场清理。不是v1用户数据或live恢复证明。
- 用户明确要求中文原CHANGELOG改名CHANGELOG.zh.md，英文CHANGELOG.md逐项全译；两份只语言不同，版本/日期/链接/SHA/代码保持，历史不摘要或改写。旧单测仅钉固定中文标题/日期/字面量，删除而不重钉英文；本次另用结构/元数据对照和独立翻译复核。
- README双语、ENTRYPOINT发布导航、Onboard REFERENCE、五份现行docs/assets、版本化automation prompt及当前PRD合同同轮维护；外部监控版本不推进，live automation不写。独立KPi/Runtime Dashboard规划、已发布历史及第三方镜像不属于本次SBTD发布状态改写范围。
- 双语CHANGELOG集成21个版本、325个条目、766个代码字面量；逐版本数字、链接及代码对应，中文20个已发布章节与原基线逐字保留。两路独立语义复核覆盖全部内容，5项误译/7处英文纠正后无遗留；不把结构校验当语义证明。
- 新文档候选在compileall后冻结完整来源，子进程显式umask022：原生macOS完整686项、20个skip、185.304秒、exit0，Onboard前后snapshot一致；较前轮少1项是删除固定中文标题/旧日期的措辞测试，不删运行行为回归。Ruff exit1的4项UP022/PLW1510与原合并基线同code/源码行，无新增诊断，未声称全绿。
- 12份现行Markdown的CommonMark/table解析、相对文件链接及details配对通过；本地ignored AGENTS维护规则同步为双语CHANGELOG，但不提交或全局同步。此前旧main CI38492338717的watch因GitHub接口500退出，run摘要实际completed/success；该旧SHA仍不替代新文档候选。

## 实际正式发布（2026-10-14）

- 新文档PR120 head `250922673a4c1cdc85408b672d78998a44594b5d`精确CI38497113728及两路复核通过后按用户限定授权合并；实际main `8f6c46993e7546b68f949bd52ede806d9b1afa61`与审查树相同。
- 该实际main的CI38500935539九job全绿，原生报告source_sha和完整无重叠聚合核对通过：Linux2128/48skip、macOS686/20skip、Windows502/33skip；必需原生检查未被skip冒充。watch曾因API EOF中断，重接同一run而非重跑测试，失败记录保留。
- 用户已批准的annotated `v2.0.0` tag已创建并推送，远端tag对象解引用到上述实际发布SHA；GitHub正式Release于2026-10-14T11:30:23+08:00发布，draft=false、prerelease=false，latest ID读回一致：[Release](https://github.com/KunoLu/640-skills/releases/tag/v2.0.0)。
- 双语CHANGELOG只在真实tag/Release成功后补同一日期、SHA和CI链接；双语README声明实际稳定版并提供v2.0.0 bootstrap提示词。历史20章节未改，不重打或移动tag。
- 原有恢复/计量/受控host限制保留；P3-04仍planned，下一人工复核2026-10-27。正常备份保留至少到2026-10-28T11:30:23+08:00，之后也需独立精确处置授权；不自动删除。
- 本状态记录走用户批准的docs/v2.0.0-release-record窄范围PR，精确CI/复核通过后合并；闭环前不声称记录已合入main。仅原来批准的release/v2.0.0与本记录分支在确认MERGED后清理；追加文档分支保留，不扩大删除范围。

## 发布记录CI阻塞与获准隔离诊断

- 记录PR121 head `c3d050ca8a1d29e2ce7274ed65e1856c1920d226`的CI38507559057 attempts1/2均在真实安装副本recovery apply子进程超过900秒；不改期限、不跳过测试、不在红灯合并。Onboard包/测试/CI/安装器与已发布SHA完全相同，根发布记录不是该夹具输入；不能仅凭相同源码判定失败可忽略。
- 用户明确授权专用Windows隔离诊断，未授权生产修复或新patch发布。诊断分支`diagnose/windows-upgrade-recovery-timeout`不合并/不发布；首轮在记录提交上已推送取证，不强推改写历史。后续所有堆栈/ACL计时仅由`SBTD_UPGRADE_TRACE=1`启用，专用workflow只跑一个合成用例，保留900秒和全部断言。
- 原生诊断run38519740668取得恢复子进程周期堆栈；run38522065660进一步实测：plan2.891s、apply396.531s、retry15.515s、recovery plan7.610s，recovery apply900.000s超时。隔离恢复进程完成1250次PowerShell ACL调用（create593/check657），累计868.900s；资源动作仍持续推进，不是已证明死锁。
- 代码及堆栈闭环：`remove_reference`逐文件调用`_capture_and_remove_file`，每次新建`_private_sibling`并以独立PowerShell进行ACL创建/校验。此重复进程开销主导恢复期限；不归因于认证/模型或单次30秒ACL门失败。外层只是在等待隔离恢复子进程。
- 建议独立修复重复私有holder/ACL启动开销，必须保留逐文件capture-before-delete、nofollow、checksum、并发新增/修改拒绝、原件及部分回执；不得简单提高900秒、削减fixture或取消ACL检查。修复范围和v2.0.1等后续发布尚待用户确认，v2.0.0 tag保持不动。
- 原生/raw和中文汇总保存在本任务私有reports，核心为`windows-recovery-root-cause`，两次记录CI失败和两次诊断原文均保留。仅已确认MERGED的原release/v2.0.0分支按原授权删除；记录、追加文档与诊断分支保留。未知未追踪文件`nonexistent`保留且未入库。
- 阻塞解除：独立strict任务`windows-recovery-acl-overhead`按父目录复用本次操作的空私有holder，逐文件仍重新证明ACL/身份/空目录/内容，未放宽900秒、未删减fixture或ACL检查。[PR122](https://github.com/KunoLu/640-skills/pull/122)经三路独立复核、精确head CI38538887444三平台九job通过（Windows安装副本完整生命周期用例通过），用户授权admin合并为main`8996d9e290ba689da1e9982f5389785319222ae7`；v2.0.1仍未发布。
- 记录PR121合入新main：双语CHANGELOG冲突仅在标题区，main版本为PR121发布段落的超集（另含v2.0.1未发布段落），按main取用；README仅保留PR121的发布横幅与v2.0.0安装来源两处差异。用户授权admin审批合并PR121，合并以该合并head的三平台CI通过为前提，红灯不合并。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-14T00:03:03.769895+08:00 | planned | in-progress | 用户要求开始P3-03并选择strict；P3-02/P3-05依赖已done，启动发布审查与候选验证，发布写入另行确认 | 主PRD §14.6 P3-03、§15/16及本轮模式选择 |
| 2026-10-14T07:39:18.007306+08:00 | in-progress | in-progress | Explicit branch rebinding from "main" to "release/v2.0.0": 用户明确授权创建release/v2.0.0候选分支并重绑定本任务，仅commit/push/PR取证，不合并或发布 | 本轮用户选择：授权候选PR阶段；九文件范围已展示 |
| 2026-10-14T08:58:31.477350+08:00 | in-progress | in-progress | Explicit branch rebinding from "release/v2.0.0" to "docs/v2.0.0-release-docs": 用户追加现行关联文档及双语v2使用示例要求，并明确授权发布前docs/v2.0.0-release-docs分支/PR及同条件管理员合并；稳定tag延后至新main精确CI通过 | 用户选择先补齐文档再发布；追加初始化、v1到v2、init/reset提示词要求 |
| 2026-10-14T09:38:14.874428+08:00 | in-progress | checking | 用户追加的现行文档/双语提示词/双语CHANGELOG全部完成并独立复核收敛；原生686项和upgrade/recovery闭环通过，进入新精确候选PR/main CI及授权发布核对 | P3-03私有reports：pretag-docs-native-macos-run、bilingual-changelog-final-verification、upgrade-prompt-native-lifecycle |
| 2026-10-14T11:31:55.790362+08:00 | checking | checking | Explicit branch rebinding from "docs/v2.0.0-release-docs" to "docs/v2.0.0-release-record": 已按授权发布v2.0.0并核验远端tag/正式Release；进入用户已批准的docs/v2.0.0-release-record窄范围日期/状态记录分支 | v2.0.0指向8f6c46993e7546b68f949bd52ede806d9b1afa61，main CI38500935539通过，GitHub Release已发布 |
| 2026-10-14T11:35:20.508935+08:00 | checking | done | 用户限定授权的v2.0.0正式发布已完成：实际main精确三平台CI通过、annotated tag已推送并解引用正确、正式Release/latest已读回；双语文档/提示词/变更日志与保留责任验收完成，本窄范围状态PR继续按授权闭环 | https://github.com/KunoLu/640-skills/releases/tag/v2.0.0 ; SHA8f6c46993e7546b68f949bd52ede806d9b1afa61 ; CI38500935539 ; private stable-release-verified.json |
| 2026-10-14T14:03:05.116358+08:00 | done | planned | 正式Release已发布事实保留，但用户授权的记录PR121闭环因Windows恢复用例两次超时未完成，恢复整体任务为未完成并开展已授权隔离诊断 | CI38507559057 attempts1/2 recovery apply exceeded900s；用户选择授权隔离诊断 |
| 2026-10-14T14:03:10.069511+08:00 | planned | in-progress | 继续原生Windows隔离诊断，保留旧done事件/真实发布与未合并记录PR；不在红灯合并，不移动tag | 专用diagnose/windows-upgrade-recovery-timeout；记录PR121仍OPEN |
| 2026-10-14T18:07:30.591310+08:00 | in-progress | checking | 记录PR121阻塞根因已由独立修复PR122解决并经用户授权admin合并；记录PR合入新main待精确head三平台CI | PR122 merge 8996d9e；CI38538887444三平台九job通过；windows-recovery-acl-overhead done |
| 2026-10-14T18:07:35.804056+08:00 | checking | done | v2.0.0发布事实与记录收口完成：PR121合入新main，双语CHANGELOG取main超集；用户授权admin审批合并，以合并head三平台CI通过为前提，红灯不合并并重开 | PR121合并head CI（待登记于PR）；PR122 merge 8996d9e；原发布CI38500935539 |
