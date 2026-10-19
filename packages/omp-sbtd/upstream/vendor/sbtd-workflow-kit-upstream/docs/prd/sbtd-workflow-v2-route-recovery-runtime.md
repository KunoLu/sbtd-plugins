# P1-18：公共路由、跨分支恢复与只读交接

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 范围与基线

- 基线main `255c5ce7535c55339726b8b52b5119bcfbea2ace`；分支`p1-18-route-recovery`。P1-17实现/状态PR #33/#34已闭环，P1当前累计4项。
- 依据主PRD P1-18/AC-05/22/24/27/28、模式路由MR-01～27、sbtd-task state/handoff reference。新全局CLI、scheduler、daemon、hook和自动意图分类不在范围。
- 交付host-native Python可调用的确定性路由结果、任务候选/分支绑定核对、明确重绑定、模式保存与失败口径、只读恢复以及受保护handoff保存/读取/提醒筛选。Agent是否真实先推荐暂停、调用grill/DDD和按模式执行完整方法仍由既有Skill规则与P1-15实际host证明，不用函数返回值冒充LLM行为证据。
- D-IMP-14保持：P1累计10项完整闭环后暂停，评估全部findings并等待用户确认。当前顺序第10项P1-06；本项闭环前不展开P1-19。

## 门禁与保留行为

- 未完整调用grill-with-docs：已批准契约明确意图/授权边界，工程选择按用户已授权推荐项推进；真实环境、数据和权限不能推断。
- Legacy characterized：fresh venv按requirements实际安装，既有状态/文档/schema原生95 tests /5.675s/exit0。报告`tests/unit/reports/unit-report-route-recovery-baseline-p1-18-route-recovery-2026_09_19-01_52_43.json`，同stem中文MD/envelope，developer-local/exact/local-only。
- Refactoring proceed：复用TaskStore单一状态实现、共享解析和原子I/O；不复制parser或另造状态事实源。新增接口保持无副作用读取和受确认写入分别可测。
- DDD confirmed：任务选择优先于询问未知模式；当前明确选择优先于同任务有效记录，新独立任务缺省default。推荐不是选择、继续不是重绑定、handoff不是模式源、表达压缩不是执行模式。工作流支撑子域，无新的领域冲突，无完整grill结果需要修正。
- DDIA confirmed：task是唯一mode/status源，active是书签，handoff是快照；单writer原子文件写，缺少保护或分支选择时零写入。保存失败不撤销当前会话选择，必须标记未持久化/恢复不可靠。快照与task不同步时以有效task为准，不按mtime覆盖。
- Release readiness ready：精确提交713项全量、309文件/11原生场景、报告及独立复核后通过，仅P1-18；不提前验收Windows/host/迁移或整体v2。

## 决策与持久化不变量

1. 显式只读及纯问答优先：mode/临时选择只在会话，不改task/active/handoff/developer/ignore，也不调用有图副作用的查询。
2. 续作先唯一确定task：显式ID、有效active或单一明确候选；多候选先询问task，不按mtime选，不先猜mode。损坏记录不作为新任务default入口。
3. 当前明确mode优先；否则继承选定task有效mode；只有真正独立新任务才默认default。unknown legacy mode询问，旧handoff不覆盖当前task。
4. Agent提供推荐mode、实质原因/风险标识和用户接受/拒绝事实。建议变更必须先返回待决定，不先落盘或执行任务；拒绝保持原mode并保存原因，无新实质风险不重复提示。输入不是自然语言分类器，不猜用户意愿。
5. 当前选择尽早保存；写失败返回有效会话mode及未持久化原因，不回退旧mode，不冒充恢复可靠。只读/分支冲突不写，后续必要gate是否满足仍由实际证据决定。
6. Git根/普通branch/detached完整SHA/已证明非Git分别核对。普通branch同名正常提交不触发冲突；不同branch/detached/绑定类型必须正确worktree、明确重绑定或只读选择。重绑定保存原/新绑定及实际时间事件，不checkout/stash，不重置blocked恢复前态。
7. Handoff仅真实pause/context-switch/branch-switch/context-pressure/manual等续接事件触发，计数或进入checking不触发。task/session自动退出独立锁存，session优先；手动请求不清除退出，normal mode不修改handoff或执行mode。
8. 可写handoff先核对docs/handoffs整棵私有路径保护和tracked状态；缺失需独立窄授权，不全量init。编码完整逻辑ID避免父/子basename冲突；同日同任务同内容不写，日期变化本身不触发新快照。
9. 内容含实际任务ID/path/mode/source/拒绝决定、root/branch/fullHEAD或unknown、时间、目标/事实决策/完成/剩余/失败/下一步/不得重复操作、退出快照及脱敏声明。只接收经调用者明确审查的安全摘要，不读取或复制账号/密钥/raw graph/原始私有payload。
10. 续作读取task后再读handoff；匹配身份/分支时用户continue足够，不重复确认。主动提醒只选7天内匹配且未完成任务的快照，旧记录仍可手动恢复；无host能力证据不声称自动SessionStart读取。

## 验证与交付

- 测试公开路由/状态结果与实际文件，不断言内部转发。模式优先/拒绝重复/保存失败/多候选/未知mode/只读/普通branch推进/detached/重绑定blocked历史/handoff退出和时间窗口分别证明。
- 真实临时Git仓库、多进程续作、完整安装副本/fresh依赖、缺依赖fail-closed、HOME与项目快照；不触碰真实用户环境。
- 文档与模板复用既有公共路由规则；对新增可调用接口同步README.md/html、Onboard及sbtd-task说明、versioned automation prompt和CHANGELOG的实际受影响入口。P1-17/P1-03既有deferred P2不顺带修复。
- 全量、原生smoke、报告/中文汇总/envelope、精确SHA、独立review以及实现PR→清理→独立status PR闭环完整执行。P0/P1必须修复；P2/P3原级入findings.log待用户评估。

## 接口与边界对照（P1-18 文档同步）

本子节只记录本项交付的可调用接口与文档入口对应关系，不改变上文范围、门禁或验证归属。

- 路由接口：`sbtd_task_routing.py` 的 `TaskRouter.route(RouteRequest)` 返回确定性 `RouteDecision`；`RouteRequest` 只承载 host 已明确的事实（intent、task_id、explicit_mode、read_only、confirmed、body、mode_note、recommendation、recommendation_response、refusal_reason），`ModeRecommendation` 必须含实质 reason 与 risk_id。状态全集为 ready／needs-task-choice／needs-mode-choice／needs-mode-decision／needs-branch-choice／needs-persistence-confirmation／persistence-failed／blocked；needs-* 与失败状态是向用户的提示，不是已执行动作。拒绝决定保存在任务自有结构化 mode_note 并按 mode+risk_id 去重。
- 恢复接口：`TaskStore` 新增公开 current_binding()、recovery_candidates(task_id=None)、rebind(task_id, expected_branch, reason, evidence, confirmed)；rebind 只更新绑定及同相位事件，不 checkout／stash，不重置 blocked 历史。
- 交接接口：`sbtd_handoff.py` 的 `HandoffStore(tasks)` 提供 protect(confirmed)、save(task_id, *, content, trigger, policy, confirmed, redaction_confirmed)、load(relative_path)、reminders(now=None)；`HandoffPolicy` 的 task/session 退出为独立显式锁存（session 优先报告），manual 触发不清除。save 状态全集为 saved／suppressed／conversation-only／branch-conflict／unprotected／unchanged／pending-confirmation／needs-redaction；unchanged 比较覆盖除 created_at 外全部字段，跨日不单独重写。文件名取完整逻辑任务 ID UTF-8 字节的小写 hex（大小写不敏感文件系统仍无冲突、可逆，文件名本身不作权威）；快照含 task_status、固定 caller-reviewed redaction 声明，content 键集合封闭（可选 presentation 须 JSON 兼容）。protect 返回 bool（已保护为 False），read-only／未确认／tracked／会隐藏既有数据时抛 TaskStateError；非 Git 根把规则插入最终 `/.sbtd/` 之前，绝不初始化 Git。load 严格校验 schema_version==1、hex 解码等于 task_id、project_root 等于本 root，任何年龄可显式恢复但绝不改 task；reminders 只取 7 天内按任务去重、root／分支匹配且未完成的快照，畸形／外来文件跳过。
- 文档入口：README.md／README.html 新增 P1-18 段并更新共同路由与 handoff 概述；CHANGELOG.md 记录新增能力与文档同步；Onboard SKILL.md／REFERENCE.md 记录 helper 真实调用形态；bundled sbtd-task 的 SKILL.md、references/state.md、references/handoff.md 对齐路由、rebind 与 HandoffStore 边界；版本化 automation prompt 仅把两个新模块纳入只读评估清单，不同步 live automation。以上均不声称 Windows、host 接线、自动 SessionStart、全量验证或发布已通过；P1-17／P1-03 既有 deferred P2 保持原级记录，不在本项修复。

## 实施与审查证据

- 路由/rebind/handoff已实现；提交前完整回归`tests/unit/reports/unit-report-route-full-p1-18-route-recovery-2026_09_19-03_04_11.json`为707 tests /164.976s /exit0，无skip。这是review修复前dirty基线，不冒充最终提交证明。
- 集成发现并修复：正文重复快照时间导致每次重写、提醒误收未来时间/当前任务绑定不匹配、身份校验与expected bytes二次读取混用。真实文件红/绿证明新用户内容保全，同次读取的已验证bytes用于原子写入。
- 独立handoff安全review无P0/P1，4项P2延期；独立路由review的4项P1均先红测后修复并复核关闭，5项P2延期。含开发中错位编辑advisor，根findings.log本任务共5 fixed P1/9 deferred P2；不声明零问题。
- 修复将explicit mode及accept/keep都在分支/推荐暂停前保存在会话；未落盘ID也保留选择，partial create可按原mode重试。保存失败仍不声称persisted；真正新的持久mode使旧会话basis失效，普通状态/分支事件不抹掉已明确模式。
- TaskStore.create的PyYAML导入复用共享`require_dependency`，无依赖时由路由返回persistence-failed而非未处理ImportError。137 tests /11.790s影响范围通过，包含keep/accept后分支选择、task已写但pointer失败和新任务未确认重试。
- 完整309文件Onboard副本：10原生Python进程场景通过；fresh no-YAML解释器实际只有jsonschema，连续创建重试保持strict且项目/HOME零写入。报告`tests/api/reports/api-report-route-reviewed-native-p1-18-route-recovery-2026_09_19-03_29_51.json`、`tests/api/reports/api-report-route-missing-yaml-p1-18-route-recovery-2026_09_19-03_29_53.json`，同stem中文MD/envelope，developer-local/dirty/local-only。
- Ponytail/Code Readability Review：删除重复JSON递归校验和不必要的fixture参数灵活性；复用既有安全parser/Git/原子writer，无新框架。新模块/测试Ruff、format、ty通过，原有state/parser与base比较Ruff0→0、ty0→0。正式最终门仍在固定提交后重跑。
- README.md/html、Onboard/Skill文档、versioned automation prompt和CHANGELOG已维护实际库入口；真实HOME、live automation、ENTRYPOINT版本与旧用户数据未动。D-IMP-14累计十项评估/用户确认门保持，当前本任务未完成，P1累计仍4项。

## 最终精确证据与合并

- 验证head `3fbb85db02821b64295af77ca4827583258fe98e`，clean；713 tests /161.141s /exit0，无skip。本轮修改Python代码/测试Ruff、format、ty全通过；既有state/parser与base均0新增。
- 最终报告：`tests/unit/reports/unit-report-route-exact-full-p1-18-route-recovery-2026_09_19-03_40_16.json`、`tests/api/reports/api-report-route-exact-native-p1-18-route-recovery-2026_09_19-03_41_04.json`、`tests/api/reports/api-report-route-exact-missing-yaml-p1-18-route-recovery-2026_09_19-03_41_06.json`。同stem中文MD/envelope齐全，本轮33份envelope校验通过；developer-local/exact/local-only，不冒充CI/远端publication。
- 完整git archive309文件安装副本，fresh venv实际安装副本requirements；10原生多进程场景和真正缺PyYAML环境的创建/重试零写入通过，执行前后每文件checksum一致。旧707项dirty全量不重标；修复后精确全量独立保存。
- 两路独立审查及routing P1修复后复核无剩余P0/P1；5fixed P1/9deferred P2保留原级。Release Readiness ready仅本任务；9项残余风险按用户D-IMP-13延期，不将单writer原子替换夸大为多进程事务。
- [PR #35](https://github.com/KunoLu/640-skills/pull/35)于2026-09-19T03:45:48+08:00实际合并，merge`a4ae34786af102b263a2c63e8c534593481c9811`。main/origin同步，合并tree与已验证head一致，任务分支本地/远端删除并prune。
- 2026-09-19T03:46:33+08:00完成Main私有验证清理；7份base源码快照先核验，99正式报告保留，仅最终unit raw/envelope补独立review和实际清理证明。P0保留安装、真实HOME、用户任务/快照、迁移备份与live automation未动。
- 完成登记走独立status PR，闭环前不展开P1-19。本项闭环后P1累计5项，D-IMP-14第10项闭环后暂停全findings评估并等待用户确认的门保持。
