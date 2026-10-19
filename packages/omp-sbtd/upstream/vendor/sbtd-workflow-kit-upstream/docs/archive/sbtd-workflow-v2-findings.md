# SBTD Workflow v2 Findings

- 归档时间：2026-09-21T21:46:29+08:00
- 来源：根目录 `findings.log`；经用户确认更新 16 项处置后转换为本文件，旧文件不再保留。
- 总计 **199 项 finding：195 fixed、0 deferred、4 dismissed**。另外完整保留 22 条策略、advisory、审查及证据修正记录。
- 原严重级别、原 ID、原顺序、历史裁决和证据字段全部保留。当前状态看总表与各项 `status`；本轮闭环看新增 `closure`。历史 `decision`／`current_code_review` 中的 deferred 表述不覆盖后续闭环。
- LEAN-004 删除的是不可达迁移分支；`tomlkit` 仍被当前 Codex／OMP 消费者使用，因此保留依赖，不将“删除依赖”错误记作已执行。
- 本轮修复的验证为 developer-local / dirty / local-only。归档不代表 PR 已合并、跨平台 CI 已通过或 SBTD v2 已发布。
- 更新前 JSONL SHA-256：`10910a3cdf44b9490d552421c27f58a747294a2d2415bfedae1ae06554219d85`。

## P2-02 独立审查延期项

2026-09-21 归档的 199 项计数不改。以下是其后 P2-02 planner 审查的延期项，不阻塞本轮；不降级，也不计入上方历史总数。

| ID | 级别 | 状态 | 位置 | 问题 |
|---|---|---|---|---|
| P2-02-R1-PLAN-001 | P2 | deferred | `sbtd_migration_plan.py` `_classify_project_items` | `required=True` 的 private task／spec skip 会拒绝，但没有直接测试。 |
| P2-02-R1-PLAN-002 | P2 | deferred | `_session_targets_complete_skip` | session 指向任务文件而不是任务目录时 fail-closed，未覆盖该负例。 |
| P2-02-R1-PLAN-003 | P2 | deferred | `_classify_project_items` | private-only 且 `target_path` 为空时，不拒绝非空 `candidate_ref`。不会发布，但批准形状不一致。 |

## 补充 CI 的后续修正

PR #68 的原生 Windows ACL 步骤在 `563abb9` 失败；`9846200` 的脱敏诊断证明 owner 已为当前用户、继承已关闭，但仍有 1 条非受信主体规则。后续修复仅对本次创建的目录使用干净 `DirectorySecurity` 并设置当前 owner；预先存在的目录继续只读拒绝，回归同时覆盖私有备份和权限变宽后不修写。原生复验结论以 PR 精确 head 的 CI 为准，不将 macOS 的 skip 当作 Windows 通过；本段不改写下方原始 199 项和 22 条历史记录。

## 问题与当前状态

| 序号 | ID | 任务 | 原级别 | 当前状态 | 问题 | 完整记录 |
|---:|---|---|---|---|---|---|
| 1 | P1-01-R11-P2-001 | P1-01 | P2 | fixed | Deployment报告文件路径可互为父子 | [详情](#record-2) |
| 2 | P1-01-R01-ProtocolReviewOne-07 | P1-01 | P2 | fixed | Bind recovery receipt scope and evidence to its plan | [详情](#record-3) |
| 3 | P1-01-R01-ProtocolReviewOne-08 | P1-01 | P2 | fixed | Tie recovery project outcomes to dependent step results | [详情](#record-4) |
| 4 | P1-01-R01-ProtocolReviewOne-09 | P1-01 | P2 | fixed | Require diagnostics for failed or blocked project records | [详情](#record-5) |
| 5 | P1-01-R02-ProtocolReviewTwo-02 | P1-01 | P2 | fixed | Reject conflicting preconditions in the manifest itself | [详情](#record-6) |
| 6 | P1-01-R02-ProtocolReviewTwo-05 | P1-01 | P2 | fixed | Require candidates for every project marked verified | [详情](#record-7) |
| 7 | P1-01-R02-ProtocolReviewTwo-10 | P1-01 | P2 | fixed | Match successful envelope status to the embedded artifact | [详情](#record-8) |
| 8 | P1-01-R02-ProtocolReviewTwo-11 | P1-01 | P2 | fixed | Make the private-owner regression reach the ownership check | [详情](#record-9) |
| 9 | P1-01-R02-SurfaceReviewTwo-01 | P1-01 | P2 | fixed | Sanitize argparse diagnostics before writing stderr | [详情](#record-10) |
| 10 | P1-01-R03-ProtocolReviewThree-05 | P1-01 | P2 | fixed | Clear generated artifact IDs when an envelope has no artifact | [详情](#record-11) |
| 11 | P1-01-R03-ProtocolReviewThree-06 | P1-01 | P2 | fixed | Reject duplicate project roots in recovery receipts | [详情](#record-12) |
| 12 | P1-01-R03-ProtocolReviewThree-07 | P1-01 | P2 | fixed | Reject private resources repeated across project records | [详情](#record-13) |
| 13 | P1-01-R03-ProtocolReviewThree-09 | P1-01 | P2 | fixed | Enforce timestamp order across bound stages | [详情](#record-14) |
| 14 | P1-01-R04-IntrinsicReviewFour-05 | P1-01 | P2 | fixed | Bind batch retained assets to project snapshots | [详情](#record-15) |
| 15 | P1-01-R04-IntrinsicReviewFour-06 | P1-01 | P2 | fixed | Require diagnostics for blocked recovery readiness | [详情](#record-16) |
| 16 | P1-01-R04-IntrinsicReviewFour-07 | P1-01 | P2 | fixed | Normalize oversized integers into a contract error | [详情](#record-17) |
| 17 | P1-01-R04-IntrinsicReviewFour-08 | P1-01 | P2 | fixed | Reject non-JSON object keys before canonicalization | [详情](#record-18) |
| 18 | P1-01-R04-RecoveryReviewFour-02 | P1-01 | P2 | fixed | Preserve recovery result scope across retries | [详情](#record-19) |
| 19 | P1-01-R04-RecoveryReviewFour-05 | P1-01 | P2 | fixed | Bind the cleanup-wide retained-assets summary | [详情](#record-20) |
| 20 | P1-01-R05-IntrinsicReviewFive-04 | P1-01 | P2 | fixed | Reject conflicting states for reused publication paths | [详情](#record-21) |
| 21 | P1-01-R05-IntrinsicReviewFive-05 | P1-01 | P2 | fixed | Reject POSIX double-slash path aliases | [详情](#record-22) |
| 22 | P1-01-R05-IntrinsicReviewFive-06 | P1-01 | P2 | fixed | Validate raw_documents before converting it | [详情](#record-23) |
| 23 | P1-01-R06-IntrinsicReviewSix-05 | P1-01 | P2 | fixed | Validate identifier input before coercing it to a dictionary | [详情](#record-24) |
| 24 | P1-01-R06-IntrinsicReviewSix-06 | P1-01 | P2 | fixed | Keep each operation ID bound to one resource result | [详情](#record-25) |
| 25 | P1-01-R06-RecoveryReviewSix-04 | P1-01 | P2 | fixed | Reject conflicting recovery protection paths | [详情](#record-26) |
| 26 | P1-01-R07-IntrinsicReviewSeven-06 | P1-01 | P2 | fixed | Bind each verification operation ID to one cleanup resource | [详情](#record-27) |
| 27 | P1-01-R07-IntrinsicReviewSeven-07 | P1-01 | P2 | fixed | Reject conflicting manifest source snapshots | [详情](#record-28) |
| 28 | P1-01-R07-IntrinsicReviewSeven-08 | P1-01 | P2 | fixed | Bind each cleanup target to one verification resource | [详情](#record-29) |
| 29 | P1-01-R07-RecoveryReviewSeven-01 | P1-01 | P2 | fixed | Bind recovery steps to their phase-specific dependents | [详情](#record-30) |
| 30 | P1-01-R07-RecoveryReviewSeven-04 | P1-01 | P2 | fixed | Reject one evidence path claimed by multiple document kinds | [详情](#record-31) |
| 31 | P1-01-R08-IntrinsicReviewEight-01 | P1-01 | P2 | fixed | Reject targets equal to any declared shared root | [详情](#record-32) |
| 32 | P1-01-R08-IntrinsicReviewEight-02 | P1-01 | P2 | fixed | Unify manifest-time snapshots by path | [详情](#record-33) |
| 33 | P1-01-R08-IntrinsicReviewEight-03 | P1-01 | P2 | fixed | Convert recursive Python values to ContractError | [详情](#record-34) |
| 34 | P1-01-R08-IntrinsicReviewEight-04 | P1-01 | P2 | fixed | Bind nested private targets to the most-specific project | [详情](#record-35) |
| 35 | P1-01-R08-IntrinsicReviewEight-05 | P1-01 | P2 | fixed | Reject publication targets equal to any selected project root | [详情](#record-36) |
| 36 | P1-01-R09-IntrinsicReviewNine-02 | P1-01 | P2 | fixed | Reject cleanup candidates that overlap retained assets | [详情](#record-37) |
| 37 | P1-01-R09-IntrinsicReviewNine-03 | P1-01 | P2 | fixed | Preserve full RFC 3339 precision in temporal checks | [详情](#record-38) |
| 38 | P1-01-R09-IntrinsicReviewNine-04 | P1-01 | P2 | fixed | Convert recursive values at every public JSON boundary | [详情](#record-39) |
| 39 | P1-01-R10-IntrinsicReviewTen-02 | P1-01 | P2 | fixed | Validate verified cleanup candidate types from the manifest | [详情](#record-40) |
| 40 | P1-01-R12-P2-001 | P1-01 | P2 | fixed | PRD尾部仍引用历史零新发现循环 | [详情](#record-41) |
| 41 | P1-01-R12-P2-002 | P1-01 | P2 | fixed | Deployment报告可与受管目标或manifest输入重叠 | [详情](#record-42) |
| 42 | P1-01-R12-P2-003 | P1-01 | P2 | fixed | Deployment evidence输出路径可覆盖其引用对象 | [详情](#record-43) |
| 43 | P1-02-R1-P1-001 | P1-02 | P1 | fixed | 完整项目前置检查晚于安装器写入 | [详情](#record-44) |
| 44 | P1-02-R1-P2-001 | P1-02 | P2 | fixed | 未选择的任务根异常会阻断有效目标 | [详情](#record-45) |
| 45 | P1-02-R1-P2-002 | P1-02 | P2 | fixed | 项目根不可检查时legacy存在性被写成false | [详情](#record-46) |
| 46 | P1-02-R1-P2-003 | P1-02 | P2 | fixed | 损坏的bundled schema产生错误修复指引 | [详情](#record-47) |
| 47 | P1-02-R1-P2-004 | P1-02 | P2 | fixed | 安装器完整性清单未包含新状态模块 | [详情](#record-48) |
| 48 | P1-02-R2-P2-001 | P1-02 | P2 | fixed | 项目检查字段清单仍列旧trellis对象 | [详情](#record-49) |
| 49 | P1-02-R2-P2-002 | P1-02 | P2 | fixed | 部分说明仍把CLI修复或项目前置检查放错顺序 | [详情](#record-50) |
| 50 | P1-02-R2-P2-003 | P1-02 | P2 | fixed | 历史Trellis段仍被称为现有过渡实现 | [详情](#record-51) |
| 51 | P1-02-R2-P2-004 | P1-02 | P2 | fixed | automation只读范围漏掉新的状态模块 | [详情](#record-52) |
| 52 | P1-02-R2-P3-001 | P1-02 | P3 | fixed | 检查中台账仍引用较早验证数量 | [详情](#record-53) |
| 53 | P1-03-R1-P1-001 | P1-03 | P1 | fixed | 包名文本与邻接metadata不能证明执行身份 | [详情](#record-54) |
| 54 | P1-03-R1-P1-002 | P1-03 | P1 | fixed | 可选Graft进入强制安装管线并推荐绕过handler | [详情](#record-55) |
| 55 | P1-03-R1-P2-001 | P1-03 | P2 | fixed | 最终比较与replace不是CAS | [详情](#record-56) |
| 56 | P1-03-R1-P2-002 | P1-03 | P2 | fixed | dotenv调试输出可污染版本探测 | [详情](#record-57) |
| 57 | P1-03-R1-P2-003 | P1-03 | P2 | fixed | 已有CLI成功分支忽略明确不兼容Node | [详情](#record-58) |
| 58 | P1-03-R1-P2-004 | P1-03 | P2 | fixed | human plan遗漏Graft状态 | [详情](#record-59) |
| 59 | P1-03-R1-P2-005 | P1-03 | P2 | fixed | npm条件依赖仍被报告为必须修复 | [详情](#record-60) |
| 60 | P1-03-R1-P2-006 | P1-03 | P2 | fixed | 流程图未完整区分Graft探针状态 | [详情](#record-61) |
| 61 | P1-03-R1-P2-007 | P1-03 | P2 | fixed | telemetry-only动作仍显示完整安装确认 | [详情](#record-62) |
| 62 | P1-03-R1-P2-008 | P1-03 | P2 | fixed | Graft blocked在generic输出误显示missing | [详情](#record-63) |
| 63 | P1-03-R2-P2-001 | P1-03 | P2 | fixed | metadata复核措辞可能混淆实现收口与状态PR审查 | [详情](#record-64) |
| 64 | P1-17-R1-DOC-001 | P1-17 | P1 | fixed | 未闭合代码围栏吞掉新增状态事件 | [详情](#record-65) |
| 65 | P1-17-R1-DOC-002 | P1-17 | P1 | fixed | 代码示例被当作权威事件表 | [详情](#record-66) |
| 66 | P1-17-R1-DOC-003 | P1-17 | P1 | fixed | 可选外侧pipe导致后续历史被截断 | [详情](#record-67) |
| 67 | P1-17-R1-DOC-004 | P1-17 | P2 | fixed | 事件codec仍会拒绝部分合法首尾空白文本 | [详情](#record-68) |
| 68 | P1-17-R1-DOC-005 | P1-17 | P2 | fixed | 既有表末行没有换行时无法追加 | [详情](#record-69) |
| 69 | P1-17-R1-DOC-006 | P1-17 | P2 | fixed | 非循环YAML别名DAG可触发重复指数遍历 | [详情](#record-70) |
| 70 | P1-17-R1-DOC-007 | P1-17 | P2 | fixed | flow YAML尾逗号后注释会使新增字段失败 | [详情](#record-71) |
| 71 | P1-17-R1-DOC-008 | P1-17 | P2 | fixed | 块标量头部注释未保全 | [详情](#record-72) |
| 72 | P1-17-A1-P1-001 | P1-17 | P1 | fixed | 多个私有目标未取得独立ignore证明 | [详情](#record-73) |
| 73 | P1-17-A1-P1-002 | P1-17 | P1 | fixed | 目录嵌套曾隐式扩大到其他逻辑任务 | [详情](#record-74) |
| 74 | P1-17-R2-STATE-001 | P1-17 | P1 | fixed | [P1] 私有传输没有验证实际目标及附件的完整 ignore 保护 | [详情](#record-75) |
| 75 | P1-17-R2-STATE-002 | P1-17 | P1 | fixed | [P1] 归档后的无完成事件历史任务被重开为自相矛盾的事件链 | [详情](#record-76) |
| 76 | P1-17-R2-STATE-003 | P1-17 | P2 | fixed | [P2] 创建新子任务不会使已完成祖先退出 done | [详情](#record-77) |
| 77 | P1-17-R2-STATE-004 | P1-17 | P2 | fixed | [P2] 提升 index.md/ 子路径会先把共享索引路径建成目录 | [详情](#record-78) |
| 78 | P1-17-R2-STATE-005 | P1-17 | P2 | fixed | [P2] archive 允许把目标发布到原任务目录内部，随后无法重试 | [详情](#record-79) |
| 79 | P1-17-R2-STATE-006 | P1-17 | P2 | fixed | [P2] catalog 静默跳过无法遍历的目录，仍允许建立重复逻辑 ID | [详情](#record-80) |
| 80 | P1-17-R2-STATE-007 | P1-17 | P2 | fixed | [P2] 子任务重开会绕过未知模式祖先的用户选择门 | [详情](#record-81) |
| 81 | P1-17-R2-STATE-008 | P1-17 | P2 | fixed | [P2] create 接受与固定 planned 状态冲突的正文历史并落盘 | [详情](#record-82) |
| 82 | P1-17-R2-STATE-009 | P1-17 | P2 | fixed | [P2] nullable 历史字段使未来事件绕过时钟门并生成倒序新历史 | [详情](#record-83) |
| 83 | P1-17-R2-STATE-010 | P1-17 | P2 | fixed | [P2] 候选清理失败会漏报已经发布的传输目标 | [详情](#record-84) |
| 84 | P1-17-R2-SURFACE-001 | P1-17 | P2 | fixed | Document which unconfirmed operations return previews | [详情](#record-85) |
| 85 | P1-17-R2-SURFACE-002 | P1-17 | P1 | fixed | Reject a second event table in the same section | [详情](#record-86) |
| 86 | P1-17-R2-SURFACE-003 | P1-17 | P2 | fixed | Document the boolean return from local protection | [详情](#record-87) |
| 87 | P1-17-R2-SURFACE-004 | P1-17 | P2 | fixed | Describe document parse failures at the public error boundary | [详情](#record-88) |
| 88 | P1-18-R1-ROUTE-001 | P1-18 | P1 | fixed | 在返回推荐确认前锁存显式模式 | [详情](#record-89) |
| 89 | P1-18-R1-ROUTE-002 | P1-18 | P1 | fixed | 在分支裁决前保留已接受或拒绝的推荐 | [详情](#record-90) |
| 90 | P1-18-R1-ROUTE-003 | P1-18 | P1 | fixed | 把新任务缺少 PyYAML 转成持久化失败结果 | [详情](#record-91) |
| 91 | P1-18-R1-ROUTE-004 | P1-18 | P1 | fixed | 为新任务保存失败保留会话模式 | [详情](#record-92) |
| 92 | P1-18-R1-ROUTE-005 | P1-18 | P2 | fixed | 按实际确认语义说明 `rebind` | [详情](#record-93) |
| 93 | P1-18-R1-ROUTE-006 | P1-18 | P2 | fixed | 先选择新任务 ID 再请求持久化确认 | [详情](#record-94) |
| 94 | P1-18-R1-ROUTE-007 | P1-18 | P2 | fixed | 避免把合法的自由文本 `mode_note` 当成损坏记录 | [详情](#record-95) |
| 95 | P1-18-R1-ROUTE-008 | P1-18 | P2 | fixed | 持久化接受推荐时的新理由 | [详情](#record-96) |
| 96 | P1-18-R1-ROUTE-009 | P1-18 | P2 | fixed | 不要为已持久化的相同模式再次请求确认 | [详情](#record-97) |
| 97 | P1-18-R1-HANDOFF-001 | P1-18 | P2 | fixed | [P2] 历史任一相同快照会抑制新的上下文回退，提醒仍返回较新的旧状态 | [详情](#record-98) |
| 98 | P1-18-R1-HANDOFF-002 | P1-18 | P2 | fixed | [P2] 非 Git 保护检查固定使用第一条正向规则，窄修复后仍永久判为未保护 | [详情](#record-99) |
| 99 | P1-18-R1-HANDOFF-003 | P1-18 | P2 | fixed | [P2] 非 Git 规则预处理删除有意义的前导空格，误称 handoff 已受保护 | [详情](#record-100) |
| 100 | P1-18-R1-HANDOFF-004 | P1-18 | P2 | fixed | [P2] 合法任务 ID 的完整 hex 可超过单文件名限制，导致交接无法保存 | [详情](#record-101) |
| 101 | P1-18-A1-P1-001 | P1-18 | P1 | fixed | 开发中错位编辑导致候选与分支逻辑不可达 | [详情](#record-102) |
| 102 | P1-19-R1-CLI-001 | P1-19 | P1 | fixed | Report completed scaffold writes in partial identity JSON | [详情](#record-103) |
| 103 | P1-19-R1-CLI-002 | P1-19 | P1 | fixed | Convert developer-store construction failures into JSON results | [详情](#record-104) |
| 104 | P1-19-R1-CLI-003 | P1-19 | P2 | fixed | Print the final developer result for text-mode writes | [详情](#record-105) |
| 105 | P1-19-R1-IDENTITY-001 | P1-19 | P2 | fixed | [P2] 非 Git 保护判断误认带前导空格的无效根规则 | [详情](#record-106) |
| 106 | P1-19-R1-IDENTITY-002 | P1-19 | P2 | fixed | [P2] 保护写入后验证失败会漏报已修改的 .gitignore | [详情](#record-107) |
| 107 | P1-19-R1-IDENTITY-003 | P1-19 | P2 | fixed | [P2] 合法尾空白 Git 根在 resolve 后被 plan 错误拒绝 | [详情](#record-108) |
| 108 | P1-19-R2-DOCS-001 | P1-19 | P2 | fixed | Document post-write identity exit codes by status | [详情](#record-109) |
| 109 | P1-19-R2-EVIDENCE-001 | P1-19 | P2 | dismissed | Checking行仍记录提交前dirty证据 | [详情](#record-110) |
| 110 | P1-12-R1-FS-003 | P1-12 | P2 | fixed | P2: Recursive scans follow Windows directory junctions | [详情](#record-111) |
| 111 | P1-12-R1-LEGACY-001 | P1-12 | P2 | fixed | Reject non-integer sidecar schema versions | [详情](#record-112) |
| 112 | P1-12-R1-LEGACY-002 | P1-12 | P2 | fixed | Keep unknown legacy keys out of current frontmatter | [详情](#record-113) |
| 113 | P1-12-R1-LEGACY-003 | P1-12 | P2 | fixed | Treat the archive root as an archived position | [详情](#record-114) |
| 114 | P1-12-R1-LEGACY-004 | P1-12 | P2 | fixed | Bind completion evidence to the legacy source | [详情](#record-115) |
| 115 | P1-12-R1-LEGACY-005 | P1-12 | P2 | fixed | Require provenance when migrated timestamps become null | [详情](#record-116) |
| 116 | P1-12-R1-PLAN-004 | P1-12 | P2 | fixed | Validate every migrated local link before publication | [详情](#record-117) |
| 117 | P1-12-R1-PLAN-005 | P1-12 | P2 | fixed | Permit optional attachments to remain private-only | [详情](#record-118) |
| 118 | P1-12-R1-PLAN-006 | P1-12 | P2 | fixed | Ignore unrelated directories in the global Skill root | [详情](#record-119) |
| 119 | P1-12-R1-PLAN-007 | P1-12 | P2 | fixed | Resolve current identity before parsing the legacy name | [详情](#record-120) |
| 120 | P1-12-R1-PLAN-008 | P1-12 | P2 | fixed | Require a handoff for unfinished workspace context | [详情](#record-121) |
| 121 | P1-12-R1-PLAN-009 | P1-12 | P2 | fixed | Bind archived tasks to the required archive destination | [详情](#record-122) |
| 122 | P1-12-R1-PLAN-010 | P1-12 | P2 | dismissed | Assign nested selected projects to the most-specific root | [详情](#record-123) |
| 123 | P1-12-R1-PLAN-011 | P1-12 | P2 | fixed | Classify files by the deepest nested task folder | [详情](#record-124) |
| 124 | P1-12-R1-RUN-003 | P1-12 | P2 | fixed | Preserve the checksum-failure exit code during apply | [详情](#record-125) |
| 125 | P1-12-R1-RUN-004 | P1-12 | P2 | fixed | Handle migration-module import failures in the live dispatch | [详情](#record-126) |
| 126 | P1-12-R1-VERIFY-005 | P1-12 | P2 | fixed | Apply the genuine-mode gate only to the API smoke | [详情](#record-127) |
| 127 | P1-12-R1-VERIFY-006 | P1-12 | P2 | fixed | Checksum-bind each Markdown report summary | [详情](#record-128) |
| 128 | P1-12-R1-VERIFY-007 | P1-12 | P2 | fixed | Reject timezone-less report timestamps before comparison | [详情](#record-129) |
| 129 | P1-12-R1-VERIFY-008 | P1-12 | P2 | fixed | Bind raw-run provenance to its evidence envelope | [详情](#record-130) |
| 130 | P1-12-R1-PLAN-001 | P1-12 | P1 | fixed | Accept the pinned v0.6.17 generated tree | [详情](#record-131) |
| 131 | P1-12-R1-PLAN-002 | P1-12 | P1 | fixed | Enforce byte preservation for share decisions | [详情](#record-132) |
| 132 | P1-12-R1-PLAN-003 | P1-12 | P1 | fixed | Require a real pause for customized global routing | [详情](#record-133) |
| 133 | P1-12-R1-RUN-002 | P1-12 | P1 | fixed | Fail closed on mixed Codex configuration files | [详情](#record-134) |
| 134 | P1-12-R2-LEAN-001 | P1-12 | P3 | fixed | Reuse the existing deployment report fixture | [详情](#record-135) |
| 135 | P1-12-R2-LEAN-002 | P1-12 | P3 | fixed | Delete the second legacy-project fixture builder | [详情](#record-136) |
| 136 | P1-12-R2-LEAN-003 | P1-12 | P3 | fixed | Remove unused migration runtime scaffolding | [详情](#record-137) |
| 137 | P1-12-R2-LEAN-004 | P1-12 | P2 | fixed | Remove the unreachable TOML editing dependency | [详情](#record-138) |
| 138 | P1-12-R2-LEAN-005 | P1-12 | P3 | fixed | Inline the one-call stage result adapter | [详情](#record-139) |
| 139 | P1-12-R2-LEAN-006 | P1-12 | P3 | fixed | Flatten speculative nested-source backup routing | [详情](#record-140) |
| 140 | P1-12-R2-SEC-002 | P1-12 | P2 | fixed | P2: Duplicate legacy task IDs are discarded before relationship validation | [详情](#record-141) |
| 141 | P1-12-R1-RUN-001 | P1-12 | P1 | fixed | Record only attempted shared operations in partial receipts | [详情](#record-142) |
| 142 | P1-12-R1-VERIFY-001 | P1-12 | P1 | fixed | Initialize the blocked-project set before verification | [详情](#record-143) |
| 143 | P1-12-R1-VERIFY-002 | P1-12 | P1 | fixed | Define a verifiable report identity for null source refs | [详情](#record-144) |
| 144 | P1-12-R1-VERIFY-003 | P1-12 | P1 | fixed | Validate carried reports against their producing attempt | [详情](#record-145) |
| 145 | P1-12-R1-VERIFY-004 | P1-12 | P1 | fixed | Validate the complete raw runner report before accepting it | [详情](#record-146) |
| 146 | P1-12-R2-SEC-001 | P1-12 | P1 | fixed | P1: Existing OMP global legacy routing is omitted from the migration batch | [详情](#record-147) |
| 147 | P1-12-R1-FS-001 | P1-12 | P1 | fixed | P1: Failed directory readback deletes user-modified files | [详情](#record-148) |
| 148 | P1-12-R1-FS-002 | P1-12 | P1 | fixed | P1: File candidates are checksum-validated only after publication | [详情](#record-149) |
| 149 | P1-12-R2-STATIC-001 | P1-12 | P3 | fixed | 迁移代码的非阻断样式诊断待统一整理 | [详情](#record-150) |
| 150 | P1-12-R3-WORKFLOW-001 | P1-12 | P1 | fixed | 自定义旧workflow缺少批准且重复校验可被重封装绕过 | [详情](#record-151) |
| 151 | P1-04-R1-GUARD-001 | P1-04 | P1 | fixed | workspace索引或父目录识别可扩大native刷新范围 | [详情](#record-152) |
| 152 | P1-04-R1-GUARD-002 | P1-04 | P1 | fixed | 图内未验证链接可让Stop覆盖外部文件 | [详情](#record-153) |
| 153 | P1-04-R1-GUARD-003 | P1-04 | P1 | fixed | 图、extract缓存及有效concept指针可越界读写 | [详情](#record-154) |
| 154 | P1-04-R1-WIRING-001 | P1-04 | P1 | fixed | Stop超时短于真实同步build预算 | [详情](#record-155) |
| 155 | P1-04-R1-WIRING-002 | P1-04 | P1 | fixed | POSIX quoting不适用于Codex Windows cmd.exe | [详情](#record-156) |
| 156 | P1-04-R1-WIRING-003 | P1-04 | P2 | fixed | 受管hook去重可能移动foreign trust索引 | [详情](#record-157) |
| 157 | P1-04-R1-WIRING-004 | P1-04 | P2 | fixed | 保留畸形hook容器可能导致host拒绝整文件 | [详情](#record-158) |
| 158 | P1-04-R1-WIRING-005 | P1-04 | P2 | fixed | SessionStart matcher未覆盖clear事件 | [详情](#record-159) |
| 159 | P1-04-R1-WIRING-006 | P1-04 | P2 | fixed | project-only指令假定存在全局MCP注册 | [详情](#record-160) |
| 160 | P1-04-R1-DEPLOY-001 | P1-04 | P1 | fixed | 共享scope创建失败丢弃先前资源结果 | [详情](#record-161) |
| 161 | P1-04-R2-CLOSURE-001 | P1-04 | P2 | fixed | 已经完整保护的ignore仍被要求新增保护操作 | [详情](#record-166) |
| 162 | P1-04-R2-CLOSURE-002 | P1-04 | P2 | fixed | 新增Codex HOME父scope未合并现有子Skill根 | [详情](#record-167) |
| 163 | P1-04-R2-PRODUCER-001 | P1-04 | P1 | fixed | 完整安装接线绑定临时bootstrap源码 | [详情](#record-168) |
| 164 | P1-04-R2-PRODUCER-002 | P1-04 | P1 | fixed | 部署时钟早于输入证据仍先写后拒绝保存 | [详情](#record-169) |
| 165 | P1-04-R2-PRODUCER-003 | P1-04 | P1 | fixed | smoke后观察异常丢弃已写资源结果 | [详情](#record-170) |
| 166 | P1-04-R2-PRODUCER-004 | P1-04 | P1 | fixed | 可选Graft缺失阻断普通安装 | [详情](#record-171) |
| 167 | P1-04-R2-PRODUCER-005 | P1-04 | P2 | fixed | 普通接线blocked退出2被外层映射为5 | [详情](#record-172) |
| 168 | P1-04-R2-PRODUCER-006 | P1-04 | P2 | fixed | 非JSON计划缺少接线阻断原因 | [详情](#record-173) |
| 169 | P1-04-R2-PRODUCER-007 | P1-04 | P2 | fixed | 覆盖模板前按旧AGENTS预渲染会拒绝本可替换的畸形fence | [详情](#record-174) |
| 170 | P1-04-R3-PRODUCER-001 | P1-04 | P1 | fixed | init接受project-only封存部署却伪装完整模式 | [详情](#record-175) |
| 171 | P1-04-R3-PRODUCER-002 | P1-04 | P1 | fixed | catalog选出的部署模板未被runtime身份绑定 | [详情](#record-176) |
| 172 | P1-04-R3-DOCS-001 | P1-04 | P1 | fixed | 旧P1-03文档否认已实现接线并漏列project-only图写入 | [详情](#record-177) |
| 173 | P1-04-R3-LEAN-001 | P1-04 | P3 | dismissed | 生产调用方未消费图构建返回详情 | [详情](#record-178) |
| 174 | P1-04-R3-STATIC-001 | P1-04 | P3 | fixed | 静态样式诊断与既有类型债务保留 | [详情](#record-184) |
| 175 | P1-04-R4-REFRESH-001 | P1-04 | P1 | fixed | MCP查询可在守卫后重建并消费新指针 | [详情](#record-185) |
| 176 | P1-04-R5-LIVE-GRAPH-001 | P1-04 | P1 | fixed | Stop新生成图可被长连接绕过一次性守卫读取 | [详情](#record-188) |
| 177 | P1-04-R5-LIVE-GRAPH-002 | P1-04 | P1 | fixed | 失败部署生成图仍可能被既存消费者读取 | [详情](#record-189) |
| 178 | P1-04-R5-PYTHON-001 | P1-04 | P1 | fixed | Python启动环境注入先于守卫 | [详情](#record-190) |
| 179 | P1-04-R5-HOOK-SCOPE-001 | P1-04 | P1 | fixed | 失效仓根导致无关项目全局hook失败 | [详情](#record-191) |
| 180 | P1-04-R6-OLD-HOOK-001 | P1-04 | P1 | fixed | 旧未隔离受管hook被误当foreign而并存 | [详情](#record-193) |
| 181 | P1-04-R6-STDIO-001 | P1-04 | P1 | fixed | native先退出使阻塞标准输入线程在Python收尾崩溃 | [详情](#record-194) |
| 182 | P1-04-R6-STDIO-002 | P1-04 | P2 | fixed | native关闭输入时EPIPE被映射为守卫拒绝2 | [详情](#record-195) |
| 183 | P1-04-R7-EVIDENCE-001 | P1-04 | P1 | fixed | 清理后运行输入来源证明保留不足 | [详情](#record-199) |
| 184 | P1-05-R1-SOURCE-001 | P1-05 | P1 | fixed | OMP来源继承、等价与部署关闭条件不足 | [详情](#record-200) |
| 185 | P1-05-R2-TRANSPORT-001 | P1-05 | P1 | fixed | JSON继承源注入type=stdio遮蔽transport字段 | [详情](#record-201) |
| 186 | P1-05-R3-PROJECT-DENYLIST-001 | P1-05 | P1 | fixed | project/Claude settings的disabledExtensions绕过阻断 | [详情](#record-202) |
| 187 | P1-05-R4-EQUIV-DENYLIST-001 | P1-05 | P1 | fixed | 非期望名称的denylist可压制等价匹配 | [详情](#record-203) |
| 188 | P1-05-R4-RESIDUAL-P3 | P1-05 | P3 | fixed | OMP接线的低风险残余观察 | [详情](#record-208) |
| 189 | P1-06-R1-CASE-ALIAS-001 | P1-06 | P3 | fixed | 大小写别名路径不会被识别为同一仓库 | [详情](#record-210) |
| 190 | P1-06-R1-TEST-STRENGTH-001 | P1-06 | P3 | fixed | linked worktree测试未逐项断言MCP root/cwd | [详情](#record-211) |
| 191 | P1-06-R1-WORDING-001 | P1-06 | P3 | fixed | “任何runtime探测前”措辞可能覆盖普通只读环境检测 | [详情](#record-212) |
| 192 | P1-12-R2-VERIFY-009 | P1-12 | P2 | fixed | Auxiliary non-API reports are not content-parsed | [详情](#record-213) |
| 193 | P1-01-R13-P2-001 | P1-01 | P2 | fixed | Recovery report references are outside the nesting guard | [详情](#record-214) |
| 194 | P1-01-R13-P2-002 | P1-01 | P2 | fixed | Path containment remains lexical only | [详情](#record-215) |
| 195 | P1-12-R2-VERIFY-010 | P1-12 | P2 | dismissed | Historical evidence without bound summaries now fails closed | [详情](#record-216) |
| 196 | P1-13-R1-SHARED-001 | P1-13 | P2 | fixed | Shared cleanup lacks runtime coverage | [详情](#record-217) |
| 197 | P1-20-R1-SHARED-001 | P1-20 | P2 | fixed | Recovery shared-closure runtime fixture remains thin | [详情](#record-218) |
| 198 | P1-08-R1-PS-001 | P1-08 | P3 | fixed | PowerShell --yes:$true form is swallowed by parameter binding | [详情](#record-219) |
| 199 | P1-08-R1-PS-002 | P1-08 | P3 | fixed | PowerShell accepts uppercase workflow modes while Bash requires lowercase | [详情](#record-220) |

## 策略与审查历史索引

| 原序号 | 类型 | ID／任务 | 状态／结论 | 完整记录 |
|---:|---|---|---|---|
| 1 | policy | — | 无有效P0/P1 findings后可推进；P2及以下记录后留待用户评估 | [详情](#record-1) |
| 162 | advisory | P1-04-ADVISOR-OP-KIND | dismissed | [详情](#record-162) |
| 163 | advisory | P1-04-ADVISOR-PROJECT-ONLY-SHARED | dismissed | [详情](#record-163) |
| 164 | advisory | P1-04-ADVISOR-OMP-MIRROR | dismissed | [详情](#record-164) |
| 165 | advisory | P1-04-ADVISOR-DUPLICATE-COPY | dismissed | [详情](#record-165) |
| 179 | advisory | P1-04-ADVISOR-MODE-FIELD | dismissed | [详情](#record-179) |
| 180 | advisory | P1-04-ADVISOR-EDIT-RECOVERY | resolved | [详情](#record-180) |
| 181 | review-closure | P1-04 | 三路最终源码复核无剩余P0/P1；有效指针、入口及catalog绑定、文档范围已关闭。P2延期；全量和精确head证明仍须完成。 | [详情](#record-181) |
| 182 | advisory | P1-04-ADVISOR-PRECOMMIT-PROOF | accepted | [详情](#record-182) |
| 183 | review-disposition | P1-04 | withdrawn-by-reviewer | [详情](#record-183) |
| 186 | evidence-correction | P1-04 | failed-retained | [详情](#record-186) |
| 187 | advisory-disposition | P1-04 | corrected | [详情](#record-187) |
| 192 | evidence-correction | P1-04 | misnamed-not-red | [详情](#record-192) |
| 196 | advisory-disposition | P1-04 | dismissed | [详情](#record-196) |
| 197 | process-observation | P1-04 | recorded | [详情](#record-197) |
| 198 | process-observation | P1-04 | disclosed | [详情](#record-198) |
| 204 | advisory-disposition | P1-05-ADVISOR-DEPLOYMENT-NULL | accepted | [详情](#record-204) |
| 205 | advisory-disposition | P1-05-ADVISOR-SCHEMA-BRACES | corrected | [详情](#record-205) |
| 206 | advisory-disposition | P1-05-ADVISOR-MANIFEST-OPTION | corrected | [详情](#record-206) |
| 207 | advisory-disposition | P1-05-ADVISOR-RENDER-DENYLIST | corrected | [详情](#record-207) |
| 209 | review-closure | P1-06 | NO P0/P1 REMAINING | [详情](#record-209) |
| 221 | review-closure | findings-current-code-review | 见完整记录 | [详情](#record-221) |

## 完整字段与历史

以下字段表逐条保留结构化记录；值用 JSON 表示以保留字符串、数值、null、数组与对象的原类型。记录顺序与原 JSONL 一致。

<a id="record-1"></a>
### 1. policy

| 字段 | 内容 |
|---|---|
| `type` | <code>"policy"</code> |
| `effective_date` | <code>"2026-09-18"</code> |
| `scope` | <code>"当前P1-01及本计划后续任务、状态文档PR"</code> |
| `review_gate` | <code>"无有效P0/P1 findings后可推进；P2及以下记录后留待用户评估"</code> |
| `source` | <code>"用户本轮明确调整；D-IMP-13"</code> |
| `notes` | <code>"finding严重级别与PRD任务阶段分开。既有修复不回滚；不得擅自降级P0/P1。"</code> |
| `historical_backfill` | <code>"回填当前P1-01已完成审查轮次的已修复P2；新门槛生效后的P2及以下默认deferred。保留原审查级别与原文，不根据影响自行降级。"</code> |

<a id="record-2"></a>
### 2. P1-01-R11-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R11-P2-001"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>11</code> |
| `source` | <code>"P101RecoveryReviewEleven"</code> |
| `source_commit` | <code>"d424a7b711542417dab917ad33310b64c7e849fd"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:958-963"</code> |
| `title` | <code>"Deployment报告文件路径可互为父子"</code> |
| `problem` | <code>"不同项目的report_refs可同时声明/private/reports/run.json和/private/reports/run.json/details.json为file；现有状态一致性只比较完全相同的路径，两个文件不能同时存在。"</code> |
| `impact` | <code>"可能接受无法在文件系统中同时满足的deployment证据清单。"</code> |
| `recommendation` | <code>"拒绝deployment report_refs之间的严格祖先/后代关系；同一路径且state一致的共享报告引用继续允许。"</code> |
| `verification` | <code>"独立只读review发现；未执行针对性复现，未实现修复。此前新增但未运行的对应测试已按新边界移除。"</code> |
| `decision` | <code>"按用户P0/P1推进门槛记账，不阻塞；后续由用户评估是否处理。"</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Deployment stage validation rejects nested report paths.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-3"></a>
### 3. P1-01-R01-ProtocolReviewOne-07

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R01-ProtocolReviewOne-07"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P101ProtocolReviewOne"</code> |
| `source_commit` | <code>"db58bae22326fb0a889b89e6ced062b290d3c603"</code> |
| `original_review` | <code>{"title": "Bind recovery receipt scope and evidence to its plan", "body": "After matching `plan_id`, `_bind_recovery_receipt` starts directly with step IDs and never compares the receipt's `projects` or `input_evidence` with the plan. A resealed receipt can therefore replace the selected roots or stage-evidence refs/hashes and still bind to the original plan, contradicting the fixed recovery scope and the requirement that the latest receipt remain self-contained. Require the exact selected project-root set and input-evidence object from the bound plan before validating results.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1454, "line_end": 1461}</code> |
| `verified_fixed_by` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1454-1461"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recovery binding checks plan scope and input evidence before result binding.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-4"></a>
### 4. P1-01-R01-ProtocolReviewOne-08

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R01-ProtocolReviewOne-08"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P101ProtocolReviewOne"</code> |
| `source_commit` | <code>"db58bae22326fb0a889b89e6ced062b290d3c603"</code> |
| `original_review` | <code>{"title": "Tie recovery project outcomes to dependent step results", "body": "Recovery validation checks failed/pending results only against the overall success status, then aggregates independently supplied project labels. In a partial receipt, a failed step dependent on project A can coexist with A marked `restored` as long as project B is marked failed so the outer status is also failed. This hides the affected project in the required per-project report; derive each project status from completed/pending results whose `dependent_projects` contains that root before aggregating.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 942, "line_end": 951}</code> |
| `verified_fixed_by` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:942-951"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Per-project recovery status is checked against dependent result severity.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-5"></a>
### 5. P1-01-R01-ProtocolReviewOne-09

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R01-ProtocolReviewOne-09"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P101ProtocolReviewOne"</code> |
| `source_commit` | <code>"db58bae22326fb0a889b89e6ced062b290d3c603"</code> |
| `original_review` | <code>{"title": "Require diagnostics for failed or blocked project records", "body": "Project `reason` and `nextStep` fields use unrestricted `text`, and only the outer envelope has a nonblank failure check. A failed or blocked deployment project—and likewise apply, cleanup, verification, recovery, or envelope project entries—can therefore validate with both fields empty, despite the normative per-project contract requiring the failure reason and next action. Add status-conditional nonblank constraints (or one shared semantic check) for every project record type.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/onboard-contracts.schema.json", "line_start": 1245, "line_end": 1250}</code> |
| `verified_fixed_by` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/onboard-contracts.schema.json:1245-1250"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "All failed/blocked project records require nonblank diagnostics.", "evidence": ["sbtd-workflow-onboard/onboard-contracts.schema.json", "sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-6"></a>
### 6. P1-01-R02-ProtocolReviewTwo-02

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R02-ProtocolReviewTwo-02"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P101ProtocolReviewTwo"</code> |
| `source_commit` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `original_review` | <code>{"title": "Reject conflicting preconditions in the manifest itself", "body": "Manifest validation does not compare `before_requirement` values for multiple selectors of the same resource and phase. Cloning an apply operation with a new selector/operation ID but a different expected state produces a sealed, planned manifest even though those selectors must be merged into one resource write with one pre-state; the disagreement is noticed only if a caller later invokes `validate_declared_bindings`. Group operations by `(resource_id, phase)` in `_check_manifest_payload` and require one identical precondition before sealing the manifest.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 528, "line_end": 531}</code> |
| `verified_fixed_by` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:528-531"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Manifest rejects conflicting before requirements by resource and phase.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-7"></a>
### 7. P1-01-R02-ProtocolReviewTwo-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R02-ProtocolReviewTwo-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P101ProtocolReviewTwo"</code> |
| `source_commit` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `original_review` | <code>{"title": "Require candidates for every project marked verified", "body": "Candidate completeness is gated on the batch `payload.status`, not each project's status. If Beta is failed and the batch is failed, Alpha may remain `verified` while omitting all of Alpha's declared private cleanup candidates; the binding succeeds and the per-project diagnostic falsely claims verification. Apply the completeness check whenever `project[\"status\"] == \"verified\"`, while retaining the batch-level shared-candidate rule appropriate to the dependency closure.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1438, "line_end": 1443}</code> |
| `verified_fixed_by` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1438-1443"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Verified completeness is gated per project, not only aggregate batch status.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-8"></a>
### 8. P1-01-R02-ProtocolReviewTwo-10

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R02-ProtocolReviewTwo-10"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P101ProtocolReviewTwo"</code> |
| `source_commit` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `original_review` | <code>{"title": "Match successful envelope status to the embedded artifact", "body": "Envelope/artifact comparison uses only failed/blocked severity. An `already-complete` apply receipt can be emitted in an envelope labeled `applied` (or a restored receipt as `already-complete`), and both aggregate and per-project checks pass because all successful statuses have severity zero. Require exact success-variant agreement with the embedded artifact while retaining any intentional outer failure escalation, so consumers can distinguish work performed from a proven no-op retry.", "priority": 2, "confidence": 0.97, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 995, "line_end": 997}</code> |
| `verified_fixed_by` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:995-997"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Successful envelopes require exact artifact success-variant agreement.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-9"></a>
### 9. P1-01-R02-ProtocolReviewTwo-11

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R02-ProtocolReviewTwo-11"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P101ProtocolReviewTwo"</code> |
| `source_commit` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `original_review` | <code>{"title": "Make the private-owner regression reach the ownership check", "body": "The test inserts Alpha's `r1` target into Beta's private operations. It is rejected first because the target is outside Beta, so the test would still pass if the duplicate-resource ownership guard were removed. Build a fixture where both ownership claims independently satisfy containment before colliding, or otherwise isolate and assert the intended ownership failure; the adjacent private/shared test has the same early-containment problem.", "priority": 2, "confidence": 1, "file_path": "tests/test_onboard_contracts.py", "line_start": 331, "line_end": 339}</code> |
| `verified_fixed_by` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"tests/test_onboard_contracts.py:331-339"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Ownership regression uses independently contained claims and reaches ownership guard.", "evidence": ["tests/test_onboard_contracts.py", "sbtd-workflow-onboard/scripts/onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-10"></a>
### 10. P1-01-R02-SurfaceReviewTwo-01

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R02-SurfaceReviewTwo-01"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P101SurfaceReviewTwo"</code> |
| `source_commit` | <code>"1eaa9878c3b05b5e06feab2ed50ec213b603e3d6"</code> |
| `original_review` | <code>{"title": "Sanitize argparse diagnostics before writing stderr", "body": "`parse_args()` lets argparse interpolate rejected raw tokens into diagnostics (for example an unknown option emits `unrecognized arguments: --option &lt;value&gt;`, and an invalid choice echoes the supplied choice). A malformed invocation can therefore copy a private path, digest, or JSON value into stderr/logs, contradicting the new contract that parser errors report only fixed fields and rules without rejected values. Override/sanitize argparse errors or prevalidate names and enum values so diagnostics identify the offending option without reproducing its value.", "priority": 2, "confidence": 0.96, "file_path": "sbtd-workflow-onboard/scripts/onboard_arguments.py", "line_start": 403, "line_end": 403}</code> |
| `verified_fixed_by` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_arguments.py:403-403"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Argparse diagnostics sanitize rejected values.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_arguments.py", "sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-11"></a>
### 11. P1-01-R03-ProtocolReviewThree-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R03-ProtocolReviewThree-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>3</code> |
| `source` | <code>"P101ProtocolReviewThree"</code> |
| `source_commit` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `original_review` | <code>{"title": "Clear generated artifact IDs when an envelope has no artifact", "body": "The artifact branch has no corresponding empty-artifact check, so a blocked/failed envelope can advertise an arbitrary generated ID without carrying the object it identifies. For example, recovery apply with `recovery: {}` and `receipt_id: \"a\" * 64` passes, even though no recovery receipt exists; recovery plan can similarly invent `plan_id`, and migration plan/verify can invent `manifest_id`/`verification_id`. Require the ID produced by the current phase to be null whenever its artifact holder is empty, while retaining IDs for already-supplied inputs such as a recovery apply `plan_id` or cleanup `verification_id`.", "priority": 2, "confidence": 0.96, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1025, "line_end": 1029}</code> |
| `verified_fixed_by` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1025-1029"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Absent current artifacts have null generated IDs.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-12"></a>
### 12. P1-01-R03-ProtocolReviewThree-06

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R03-ProtocolReviewThree-06"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>3</code> |
| `source` | <code>"P101ProtocolReviewThree"</code> |
| `source_commit` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `original_review` | <code>{"title": "Reject duplicate project roots in recovery receipts", "body": "Recovery receipts are the only project-bearing document whose semantic validator does not enforce unique roots, and plan binding compares root sets, which discards duplicates. Appending a second copy of Alpha to a valid restored receipt therefore survives sealing and `validate_declared_bindings` against the original two-project plan. This makes the cumulative per-project outcome ambiguous and lets consumers process one project twice; add the same duplicate-root rejection used for stage, verification, plan, and envelope documents before aggregating receipt statuses.", "priority": 2, "confidence": 1, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 899, "line_end": 906}</code> |
| `verified_fixed_by` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:899-906"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recovery receipt rejects duplicate roots before aggregation.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-13"></a>
### 13. P1-01-R03-ProtocolReviewThree-07

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R03-ProtocolReviewThree-07"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>3</code> |
| `source` | <code>"P101ProtocolReviewThree"</code> |
| `source_commit` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `original_review` | <code>{"title": "Reject private resources repeated across project records", "body": "Private resource uniqueness is tracked only inside each project, so the same physical `resource_id` can appear once under Alpha and once under Beta and still seal as a successful stage document; the verification validator has the same per-project-only gap for cleanup candidates. This violates the contract's single-owner rule before any manifest binding occurs and allows a valid success envelope to report two writes/cleanup claims for one resource. Track private resource IDs globally with their owning root in both validators and reject reuse by another project (as well as the existing private/shared collision).", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 690, "line_end": 699}</code> |
| `verified_fixed_by` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:690-699"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Private resource uniqueness is global across project records.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-14"></a>
### 14. P1-01-R03-ProtocolReviewThree-09

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R03-ProtocolReviewThree-09"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>3</code> |
| `source` | <code>"P101ProtocolReviewThree"</code> |
| `source_commit` | <code>"c9c86f3835e8f17a2f0c4d882f132c8299156ac8"</code> |
| `original_review` | <code>{"title": "Enforce timestamp order across bound stages", "body": "Cross-document binding never compares timestamps, so a verification can be sealed with `verified_at` before the bound deployment (or even before manifest creation), and cleanup/recovery records can likewise predate their prerequisites while the full family still validates. That undermines the evidence claim that deploy/smoke completed before verify and cleanup. When both objects are supplied, require manifest creation ≤ stage start/finish, apply finish ≤ deployment start, deployment finish ≤ verification time, verification time ≤ cleanup start, and source/plan times ≤ recovery plan/receipt execution.", "priority": 2, "confidence": 0.94, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1789, "line_end": 1798}</code> |
| `verified_fixed_by` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1789-1798"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Supplied document timestamps are checked causally with precision-preserving comparison.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-15"></a>
### 15. P1-01-R04-IntrinsicReviewFour-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R04-IntrinsicReviewFour-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>4</code> |
| `source` | <code>"P101IntrinsicReviewFour"</code> |
| `source_commit` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `original_review` | <code>{"title": "Bind batch retained assets to project snapshots", "body": "`_bind_retained_assets` compares only each cleanup project's list with verification and ignores required `cleanup.payload.retained_assets`. A cleaned receipt can set that batch list to empty or to unrelated object refs while every per-project snapshot remains correct, so consumers of the self-contained batch field receive contradictory preservation evidence. Require the batch list to contain the deduplicated union of the project retained assets (at minimum, it must not omit any project asset).", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1869, "line_end": 1878}</code> |
| `verified_fixed_by` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1869-1878"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Batch retained assets equal deduplicated project observations.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-16"></a>
### 16. P1-01-R04-IntrinsicReviewFour-06

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R04-IntrinsicReviewFour-06"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>4</code> |
| `source` | <code>"P101IntrinsicReviewFour"</code> |
| `source_commit` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `original_review` | <code>{"title": "Require diagnostics for blocked recovery readiness", "body": "The receipt validator only requires report references when `runtime_readiness` is `verified`. A receipt may therefore report all filesystem projects `restored`, set `runtime_readiness: \"blocked\"`, and leave `payload.reason` plus every project reason/nextStep empty, providing no explanation for the missing CLI, package, or host that blocked readiness. Require a nonblank receipt reason for blocked readiness and for failed/blocked receipt outcomes.", "priority": 2, "confidence": 0.97, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1048, "line_end": 1055}</code> |
| `verified_fixed_by` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1048-1055"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Blocked readiness/failed recovery requires explanation.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-17"></a>
### 17. P1-01-R04-IntrinsicReviewFour-07

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R04-IntrinsicReviewFour-07"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>4</code> |
| `source` | <code>"P101IntrinsicReviewFour"</code> |
| `source_commit` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `original_review` | <code>{"title": "Normalize oversized integers into a contract error", "body": "`_decode_strict` leaves `parse_int` at Python's default and catches only `JSONDecodeError`. On the supported Python 3.13 runtime, an integer literal beyond the configured digit limit raises plain `ValueError`, so an invalid document such as one with an oversized `schema_version` escapes the promised `ContractError` boundary and can crash callers that handle contract failures. Supply a bounded `parse_int` or translate the parser's `ValueError` into a sanitized contract error.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 260, "line_end": 268}</code> |
| `verified_fixed_by` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:260-268"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Oversized/invalid strict JSON numbers become ContractError.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-18"></a>
### 18. P1-01-R04-IntrinsicReviewFour-08

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R04-IntrinsicReviewFour-08"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>4</code> |
| `source` | <code>"P101IntrinsicReviewFour"</code> |
| `source_commit` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `original_review` | <code>{"title": "Reject non-JSON object keys before canonicalization", "body": "`canonical_json_bytes` delegates directly to `json.dumps`, which coerces integer, boolean, float, and null mapping keys into strings. Consequently distinct Python values such as `{1: \"x\"}` and `{\"1\": \"x\"}` produce identical supposedly canonical bytes instead of rejecting the non-JSON input, undermining the exported canonical hashing primitive. Run the strict JSON-safety check before serialization so object keys must already be strings.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 160, "line_end": 168}</code> |
| `verified_fixed_by` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:160-168"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Canonical JSON checks safety before serialization and rejects non-string keys.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-19"></a>
### 19. P1-01-R04-RecoveryReviewFour-02

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R04-RecoveryReviewFour-02"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>4</code> |
| `source` | <code>"P101RecoveryReviewFour"</code> |
| `source_commit` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `original_review` | <code>{"title": "Preserve recovery result scope across retries", "body": "The recovery-specific succeeded-result comparison preserves status, states, and `protection_ref`, but not `operation_ids` or `dependent_projects`. A linked retry can keep a completed private step's canonical `step_id` while replacing its operation ID with an arbitrary digest or moving its dependency from Alpha to Beta; the receipt still passes `validate_document` and `validate_cumulative` because those fields are not part of `step_id`. The latest cumulative receipt then rewrites which operation and project completed under the unchanged plan. Require immutable phase/resource/operation/dependency identity for every carried recovery result, including failed-to-succeeded transitions.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 2221, "line_end": 2225}</code> |
| `verified_fixed_by` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:2221-2225"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recovery retry preserves operation/dependency identity.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-20"></a>
### 20. P1-01-R04-RecoveryReviewFour-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R04-RecoveryReviewFour-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>4</code> |
| `source` | <code>"P101RecoveryReviewFour"</code> |
| `source_commit` | <code>"7c39776c7d665602754712a4d1a603ef7d8adcd9"</code> |
| `original_review` | <code>{"title": "Bind the cleanup-wide retained-assets summary", "body": "The binding compares only each cleanup project's `retained_assets` with verification and never reads `cleanup.payload.retained_assets`. Clearing only the batch-level list in the valid fixture therefore passes while Alpha still records r4 as retained, leaving one successful receipt with contradictory project and batch preservation results. Require the batch list to equal the deduplicated union of retained assets recorded by successful project entries.", "priority": 2, "confidence": 0.97, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1875, "line_end": 1882}</code> |
| `verified_fixed_by` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1875-1882"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Cleanup-wide retained summary is bound to project observations.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-21"></a>
### 21. P1-01-R05-IntrinsicReviewFive-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R05-IntrinsicReviewFive-04"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>5</code> |
| `source` | <code>"P101IntrinsicReviewFive"</code> |
| `source_commit` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `original_review` | <code>{"title": "Reject conflicting states for reused publication paths", "body": "Publication validation deduplicates source paths only within each item and never reconciles object references across items. Two approved items can therefore claim the same source or candidate path with different types/checksums and both validate, even though a single plan-time path cannot satisfy both snapshots; the resulting manifest can bind two incompatible copy sources. Track path-to-state claims across all `sources` and non-null `candidate_ref` values and reject conflicting reuse while still allowing identical shared-source references.", "priority": 2, "confidence": 0.97, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 422, "line_end": 427}</code> |
| `verified_fixed_by` | <code>"e3bb1ff4c425d06d936c47359e8358296aea002e"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:422-427"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Publication path/state claims are reconciled globally.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-22"></a>
### 22. P1-01-R05-IntrinsicReviewFive-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R05-IntrinsicReviewFive-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>5</code> |
| `source` | <code>"P101IntrinsicReviewFive"</code> |
| `source_commit` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `original_review` | <code>{"title": "Reject POSIX double-slash path aliases", "body": "On POSIX, `os.path.normpath` deliberately preserves exactly two leading slashes, so paths such as `//private/work/alpha` pass this format check. On the supported Darwin host they address the same filesystem location as `/private/work/alpha`, while `Path` ownership checks and canonical ID hashing keep the two spellings distinct; duplicate project roots or resource targets can therefore evade conflict detection. Reject the double-leading-slash spelling on POSIX (or canonicalize it before every comparison and ID calculation).", "priority": 2, "confidence": 0.96, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 340, "line_end": 345}</code> |
| `verified_fixed_by` | <code>"e3bb1ff4c425d06d936c47359e8358296aea002e"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:340-345"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "POSIX double-leading-slash aliases are rejected by normalized path validation.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-23"></a>
### 23. P1-01-R05-IntrinsicReviewFive-06

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R05-IntrinsicReviewFive-06"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>5</code> |
| `source` | <code>"P101IntrinsicReviewFive"</code> |
| `source_commit` | <code>"e53d623838aaea8094b15292a936015b3810ae01"</code> |
| `original_review` | <code>{"title": "Validate raw_documents before converting it", "body": "`raw_documents` is coerced with `dict(raw_documents or {})` before any runtime type check. A malformed nonempty value such as bytes raises a plain `TypeError`/`ValueError` outside the promised sanitized `ContractError` boundary, while an empty list is silently accepted as though no raw evidence was supplied. Require `None` or a `Mapping` before copying it, matching the existing validation for `documents`.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 2135, "line_end": 2139}</code> |
| `verified_fixed_by` | <code>"e3bb1ff4c425d06d936c47359e8358296aea002e"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:2135-2139"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "raw_documents is checked as Mapping before use.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-24"></a>
### 24. P1-01-R06-IntrinsicReviewSix-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R06-IntrinsicReviewSix-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>6</code> |
| `source` | <code>"P101IntrinsicReviewSix"</code> |
| `source_commit` | <code>"e3bb1ff4c425d06d936c47359e8358296aea002e"</code> |
| `original_review` | <code>{"title": "Validate identifier input before coercing it to a dictionary", "body": "`make_envelope` calls `dict(identifiers or {})` without enforcing the annotated mapping shape. Empty lists and strings are silently treated as no identifiers, list-of-pairs aliases are accepted, and malformed nonempty inputs can raise native `TypeError`/`ValueError` instead of the promised sanitized `ContractError`. Require `identifiers` to be `None` or a `Mapping` before copying it, matching the strict check already used for `raw_documents`.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 2557, "line_end": 2562}</code> |
| `verified_fixed_by` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:2557-2562"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Operation IDs are globally mapped to one resource.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-25"></a>
### 25. P1-01-R06-IntrinsicReviewSix-06

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R06-IntrinsicReviewSix-06"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>6</code> |
| `source` | <code>"P101IntrinsicReviewSix"</code> |
| `source_commit` | <code>"e3bb1ff4c425d06d936c47359e8358296aea002e"</code> |
| `original_review` | <code>{"title": "Keep each operation ID bound to one resource result", "body": "Standalone stage validation tracks duplicate resource IDs but never tracks operation IDs across results. The same operation digest can therefore appear in results for two different resource IDs (including one private and one shared), and the receipt can seal and be embedded in a successful envelope even though `operation_id` canonically includes exactly one `resource_id`. Track every result operation ID globally within the stage document and reject reuse under a different resource.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 835, "line_end": 844}</code> |
| `verified_fixed_by` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:835-844"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recovery protection paths cannot be reused with conflicting state.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-26"></a>
### 26. P1-01-R06-RecoveryReviewSix-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R06-RecoveryReviewSix-04"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>6</code> |
| `source` | <code>"P101RecoveryReviewSix"</code> |
| `source_commit` | <code>"e3bb1ff4c425d06d936c47359e8358296aea002e"</code> |
| `original_review` | <code>{"title": "Reject conflicting recovery protection paths", "body": "Recovery results validate each `protection_ref` independently, so two completed steps can name the same absolute protection path with different states and still bind to the plan. One physical file cannot preserve both originals; the later copy has overwritten the earlier protection even though the cumulative receipt claims both remain usable. Track protection path-to-state claims across all results and reject conflicting reuse, matching the existing stage-backup consistency check.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1114, "line_end": 1123}</code> |
| `verified_fixed_by` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1114-1123"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recovery receipt validation now tracks protection paths globally and rejects conflicting state reuse, preserving one physical protection object per declared original state.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-27"></a>
### 27. P1-01-R07-IntrinsicReviewSeven-06

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R07-IntrinsicReviewSeven-06"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>7</code> |
| `source` | <code>"P101IntrinsicReviewSeven"</code> |
| `source_commit` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `original_review` | <code>{"title": "Bind each verification operation ID to one cleanup resource", "body": "Standalone verification validation deduplicates `resource_id` values but never tracks `operation_ids` across candidates. Two private/shared cleanup candidates with different resource IDs and targets can reuse the same operation digest, then seal successfully and appear in a valid successful envelope even though an operation ID canonically belongs to exactly one resource. Add the same global operation-ID-to-resource check used by `_check_stage_payload` to all cleanup candidates.", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 954, "line_end": 973}</code> |
| `verified_fixed_by` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:954-973"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Verification candidates reject operation ID reuse across resources.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-28"></a>
### 28. P1-01-R07-IntrinsicReviewSeven-07

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R07-IntrinsicReviewSeven-07"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>7</code> |
| `source` | <code>"P101IntrinsicReviewSeven"</code> |
| `source_commit` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `original_review` | <code>{"title": "Reject conflicting manifest source snapshots", "body": "`manifest_project.sources` is never included in the manifest's semantic path-state checks. A project can list the same absolute source path twice with different types or checksums, and the manifest still seals even though both refs describe the one plan-time object and downstream consumers cannot satisfy both snapshots. Track source path-to-state claims (at least within the manifest's project source arrays) and reject conflicting reuse; the current valid fixture leaves every `sources` array empty, so it does not exercise this field.", "priority": 2, "confidence": 0.97, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 694, "line_end": 700}</code> |
| `verified_fixed_by` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:694-700"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Manifest source snapshots participate in path/state consistency.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-29"></a>
### 29. P1-01-R07-IntrinsicReviewSeven-08

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R07-IntrinsicReviewSeven-08"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>7</code> |
| `source` | <code>"P101IntrinsicReviewSeven"</code> |
| `source_commit` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `original_review` | <code>{"title": "Bind each cleanup target to one verification resource", "body": "`_verification_observations` treats repeated paths as valid whenever their states match, while `_check_verification_payload` deduplicates candidates only by `resource_id`. Two cleanup candidates can therefore carry different resource IDs and operation sets for the same target path/state and still seal in a successful verification envelope, describing two owners and two cleanup actions for one physical object. Keep shared retained observations reusable, but enforce a target-to-resource mapping across cleanup candidates.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 934, "line_end": 943}</code> |
| `verified_fixed_by` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:934-943"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Cleanup targets map to one verification resource.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-30"></a>
### 30. P1-01-R07-RecoveryReviewSeven-01

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R07-RecoveryReviewSeven-01"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>7</code> |
| `source` | <code>"P101RecoveryReviewSeven"</code> |
| `source_commit` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `original_review` | <code>{"title": "Bind recovery steps to their phase-specific dependents", "body": "`dependents` is the all-phase union for a shared resource, and `_check_recovery_plan_payload` requires every step to repeat that resource-wide set. When a resource's apply and cleanup operations have different `dependent_projects`, a step carrying the exact dependencies of its own phase is rejected, while an accepted cleanup step overstates the projects attached to its original operation IDs. Keep the all-phase union for the resource entry and selected-project authorization closure, but bind each step to the dependent-project union of its phase-specific operation IDs.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 2018, "line_end": 2026}</code> |
| `verified_fixed_by` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `resolution` | <code>"已修正step阶段依赖归因；Beta-only放宽共享资源授权闭包的建议经reviewer撤回，resource仍保持跨阶段完整依赖并集。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:2018-2026"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recovery step dependencies are phase-specific while resource closure remains all-phase.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-31"></a>
### 31. P1-01-R07-RecoveryReviewSeven-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R07-RecoveryReviewSeven-04"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>7</code> |
| `source` | <code>"P101RecoveryReviewSeven"</code> |
| `source_commit` | <code>"c10b2b417b3042012130ba9260d4fc19627dc681"</code> |
| `original_review` | <code>{"title": "Reject one evidence path claimed by multiple document kinds", "body": "`_bind_input_evidence` validates each kind independently and never checks path reuse. A recovery plan can claim the same absolute file as both the manifest and an apply receipt with different checksums; even supplying two valid raw byte strings keyed by kind passes, although one path cannot hold both required documents when recovery later revalidates the plan. Require every non-null input-evidence kind to name a distinct path and reject conflicting repeated path/state claims.", "priority": 2, "confidence": 0.97, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1500, "line_end": 1509}</code> |
| `verified_fixed_by` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1500-1509"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Input evidence kinds require distinct non-overlapping paths.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-32"></a>
### 32. P1-01-R08-IntrinsicReviewEight-01

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R08-IntrinsicReviewEight-01"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>8</code> |
| `source` | <code>"P101IntrinsicReviewEight"</code> |
| `source_commit` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `original_review` | <code>{"title": "Reject targets equal to any declared shared root", "priority": 2, "summary_zh": "嵌套shared_roots时，目标等于内层根仍可借外层根通过；应禁止目标等于任一已声明共享根。", "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "symbol": "_check_manifest_payload"}</code> |
| `verified_fixed_by` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `recovered_from` | <code>"本会话原review全文及history://P101IntrinsicReviewEight（原3项＋后续确认2项）；最新agent payload被补充输出覆盖且截断"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py::_check_manifest_payload"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Managed targets equal to shared roots are rejected.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-33"></a>
### 33. P1-01-R08-IntrinsicReviewEight-02

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R08-IntrinsicReviewEight-02"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>8</code> |
| `source` | <code>"P101IntrinsicReviewEight"</code> |
| `source_commit` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `original_review` | <code>{"title": "Unify manifest-time snapshots by path", "priority": 2, "summary_zh": "project/publication/change/ownership及具体初态可对同一路径声明矛盾状态；统一计划时点快照，不能混入phase-after。", "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "symbol": "_check_manifest_payload"}</code> |
| `verified_fixed_by` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `recovered_from` | <code>"本会话原review全文及history://P101IntrinsicReviewEight（原3项＋后续确认2项）；最新agent payload被补充输出覆盖且截断"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py::_check_manifest_payload"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Manifest snapshots are unified by path at plan time.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-34"></a>
### 34. P1-01-R08-IntrinsicReviewEight-03

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R08-IntrinsicReviewEight-03"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>8</code> |
| `source` | <code>"P101IntrinsicReviewEight"</code> |
| `source_commit` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `original_review` | <code>{"title": "Convert recursive Python values to ContractError", "priority": 2, "summary_zh": "validate_document直接Python循环／过深值逃逸RecursionError；转换为受控ContractError。", "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "symbol": "validate_document"}</code> |
| `verified_fixed_by` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `recovered_from` | <code>"本会话原review全文及history://P101IntrinsicReviewEight（原3项＋后续确认2项）；最新agent payload被补充输出覆盖且截断"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py::validate_document"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recursive values are converted to sanitized ContractError.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-35"></a>
### 35. P1-01-R08-IntrinsicReviewEight-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R08-IntrinsicReviewEight-04"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>8</code> |
| `source` | <code>"P101IntrinsicReviewEight"</code> |
| `source_commit` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `original_review` | <code>{"title": "Bind nested private targets to the most-specific project", "priority": 2, "summary_zh": "外层项目可将嵌套已选项目中的目标声明为自身private操作；显式owner必须为最具体已选项目，不自动改派。", "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "symbol": "_check_manifest_payload"}</code> |
| `verified_fixed_by` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `recovered_from` | <code>"本会话原review全文及history://P101IntrinsicReviewEight（原3项＋后续确认2项）；最新agent payload被补充输出覆盖且截断"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py::_check_manifest_payload"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Nested private targets require explicit most-specific ownership.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-36"></a>
### 36. P1-01-R08-IntrinsicReviewEight-05

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R08-IntrinsicReviewEight-05"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>8</code> |
| `source` | <code>"P101IntrinsicReviewEight"</code> |
| `source_commit` | <code>"2076d1cd65af5a5ab24e071f2192146eb16c30ba"</code> |
| `original_review` | <code>{"title": "Reject publication targets equal to any selected project root", "priority": 2, "summary_zh": "嵌套项目中publication目标等于内层项目根，可借外层根contains通过；禁止等于任一已选项目根。", "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "symbol": "_check_manifest_payload"}</code> |
| `verified_fixed_by` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `recovered_from` | <code>"本会话原review全文及history://P101IntrinsicReviewEight（原3项＋后续确认2项）；最新agent payload被补充输出覆盖且截断"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py::_check_manifest_payload"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Publication targets equal to selected roots are rejected.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-37"></a>
### 37. P1-01-R09-IntrinsicReviewNine-02

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R09-IntrinsicReviewNine-02"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>9</code> |
| `source` | <code>"P101IntrinsicReviewNine"</code> |
| `source_commit` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `original_review` | <code>{"title": "Reject cleanup candidates that overlap retained assets", "body": "Starting from the valid verification fixture, adding the current cleanup candidate `{path, state}` to the same verified project's `retained_assets` passes because `setdefault` accepts the identical state and `_bind_verification` only checks that required retained resources are present. The record is then marked `verified` while a real cleanup that changes that candidate cannot produce a valid successful receipt: carrying the asset violates the cleanup result, while dropping it differs from verification. Reject exact and parent/child overlap between retained assets and cleanup candidates for verified scope.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 1014, "line_end": 1021}</code> |
| `verified_fixed_by` | <code>"b8a9d76a4ea65b152fa4bd4a68dda525f3f2d6a2"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1014-1021"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Verified cleanup candidates cannot overlap retained assets.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-38"></a>
### 38. P1-01-R09-IntrinsicReviewNine-03

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R09-IntrinsicReviewNine-03"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>9</code> |
| `source` | <code>"P101IntrinsicReviewNine"</code> |
| `source_commit` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `original_review` | <code>{"title": "Preserve full RFC 3339 precision in temporal checks", "body": "The timestamp format accepts arbitrary fractional digits, but `datetime.fromisoformat` represents only microseconds. Thus a valid receipt with `started_at=2026-09-18T01:00:00.0000002Z` and `finished_at=2026-09-18T01:00:00.0000001Z` parses both instants identically and passes even though it runs backward; the same truncation weakens cross-document chronology. Parse the fractional component without losing precision, or explicitly reject precision beyond six digits before comparison.", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 876, "line_end": 883}</code> |
| `verified_fixed_by` | <code>"b8a9d76a4ea65b152fa4bd4a68dda525f3f2d6a2"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:876-883"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "RFC3339 fractional precision is preserved in temporal checks.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-39"></a>
### 39. P1-01-R09-IntrinsicReviewNine-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R09-IntrinsicReviewNine-04"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>9</code> |
| `source` | <code>"P101IntrinsicReviewNine"</code> |
| `source_commit` | <code>"564d29908bd95a23ad8717b997c9931449730e89"</code> |
| `original_review` | <code>{"title": "Convert recursive values at every public JSON boundary", "body": "`validate_document` converts cyclic/deep Python values to `ContractError`, but `validate_deployment_result` calls `_check_json_safe` unguarded, and the non-envelope branch of `write_json_response` does the same. Adding `result[\"loop\"] = result` to an otherwise valid deployment result, or a cycle below an otherwise valid pass-through response, therefore raises raw `RecursionError` and crashes the caller instead of honoring the module's sanitized contract-failure API. Use the same recursion-safe wrapper at both remaining public entry points (the writer can also rely on `canonical_json_bytes`, which already converts this error).", "priority": 2, "confidence": 0.99, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 2887, "line_end": 2893}</code> |
| `verified_fixed_by` | <code>"b8a9d76a4ea65b152fa4bd4a68dda525f3f2d6a2"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:2887-2893"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Deployment result and writer boundaries are recursion-safe.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-40"></a>
### 40. P1-01-R10-IntrinsicReviewTen-02

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R10-IntrinsicReviewTen-02"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>10</code> |
| `source` | <code>"P101IntrinsicReviewTen"</code> |
| `source_commit` | <code>"b8a9d76a4ea65b152fa4bd4a68dda525f3f2d6a2"</code> |
| `original_review` | <code>{"title": "Validate verified cleanup candidate types from the manifest", "body": "With only a manifest and verification supplied, change the `state` of a verified directory cleanup candidate to a valid file state and reseal the verification. For the common `phase-after` requirement, `_expected_before` returns `None` when the predecessor document is absent, so the candidate passes even though the manifest already identifies the resource as a directory; this is a declared type contradiction, not an inference about an omitted stage, and can authorize cleanup against the wrong physical kind. When `verified` is true, require `candidate.state.type` to match the manifest resource's owner category (and apply the existing predecessor equality check when that evidence is supplied).", "priority": 2, "confidence": 0.98, "file_path": "sbtd-workflow-onboard/scripts/onboard_contracts.py", "line_start": 2026, "line_end": 2036}</code> |
| `verified_fixed_by` | <code>"d424a7b711542417dab917ad33310b64c7e849fd"</code> |
| `resolution` | <code>"用户调整门槛前已纳入修复并通过对应后续冻结提交验证；保留历史，不回滚，也不作为待处理项。详见P1-01任务记录。"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:2026-2036"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Verified candidate type is checked against manifest owner kind without predecessor evidence.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-41"></a>
### 41. P1-01-R12-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R12-P2-001"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>12</code> |
| `source` | <code>"P101SurfaceReviewTwelve"</code> |
| `source_commit` | <code>"2239fcdd777ef28e7c6c30864f346f5e1ca72ae7"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md:1582"</code> |
| `reported_location` | <code>"审查原锚点为1105；实际歧义语句位于1582，已用源码定位核对。"</code> |
| `title` | <code>"PRD尾部仍引用历史零新发现循环"</code> |
| `problem` | <code>"§22.2在说明历史复审直至零新发现后，要求实施任务执行该修复／复审循环，可能让读者误把P2/P3继续视为阻塞。"</code> |
| `impact` | <code>"计划执行文案可能产生歧义；最新用户授权、§14.1及D-IMP-13已明确P0/P1门槛，当前流程按新规则执行。"</code> |
| `recommendation` | <code>"后续评估是否将§22.2的实施句明确指向§14.1/D-IMP-13停止条件，仅把零新发现保留为R-09历史。"</code> |
| `verification` | <code>"独立只读review，已定位实际句子；不涉及运行验证。"</code> |
| `decision` | <code>"按用户新门槛作为P2留待评估，不因该项阻塞当前任务。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"PRD §22.2 明确历史零新发现循环不覆盖实施任务；当前门槛指向 §14.1/D-IMP-13。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "PRD §22.2 明确历史零新发现循环不覆盖实施任务；当前门槛指向 §14.1/D-IMP-13。", "evidence": ["docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md", "sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-42"></a>
### 42. P1-01-R12-P2-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R12-P2-002"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>12</code> |
| `source` | <code>"P101IntrinsicReviewTwelve"</code> |
| `source_commit` | <code>"2239fcdd777ef28e7c6c30864f346f5e1ca72ae7"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1858-1867"</code> |
| `title` | <code>"Deployment报告可与受管目标或manifest输入重叠"</code> |
| `problem` | <code>"stage report_refs与manifest输入／受管目标没有直接空间隔离；报告可指向已批准candidate、copy source或受管目标，并声明不同checksum。"</code> |
| `impact` | <code>"声明链可能同时要求一个路径容纳报告和保留输入，报告写入可能替换候选或其他输入。"</code> |
| `recommendation` | <code>"后续评估是否拒绝stage报告与manifest操作目标、输入引用的等同及祖先/后代关系；需保持各角色和时点语义清晰。"</code> |
| `verification` | <code>"独立只读review；本轮未运行针对性复现或实施修复。"</code> |
| `decision` | <code>"原审查级别P2；按D-IMP-13登记留待用户评估，不阻塞当前合并门槛。"</code> |
| `also_reported_by` | <code>[{"source": "P101RecoveryReviewTwelve", "severity": "P2", "source_commit": "2239fcdd777ef28e7c6c30864f346f5e1ca72ae7", "location": "sbtd-workflow-onboard/scripts/onboard_contracts.py:1858-1866", "additional_scope": "补充报告与受管目标的碰撞，与原输入路径隔离属于同根因。"}]</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Deployment reports are isolated from managed targets and manifest inputs.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-43"></a>
### 43. P1-01-R12-P2-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R12-P2-003"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>12</code> |
| `source` | <code>"P101RecoveryReviewTwelve"</code> |
| `source_commit` | <code>"2239fcdd777ef28e7c6c30864f346f5e1ca72ae7"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:3114-3123"</code> |
| `title` | <code>"Deployment evidence输出路径可覆盖其引用对象"</code> |
| `problem` | <code>"validate_deployment_result只校验wrapper和内嵌evidence，未排除输出path与内嵌report_ref/backup_ref等同或互为父子。"</code> |
| `impact` | <code>"保存deployment evidence时可能覆盖其引用的报告或原始备份，使返回证据链失效。"</code> |
| `recommendation` | <code>"后续评估输出path与内嵌_immutable_stage_references之间的词法重叠检查。"</code> |
| `verification` | <code>"独立只读review；本轮未复现或修改生产代码。"</code> |
| `decision` | <code>"按D-IMP-13记录为P2待用户评估，不阻塞当前推进。"</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Evidence output path cannot overlap embedded immutable report/backup references.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-44"></a>
### 44. P1-02-R1-P1-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R1-P1-001"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P102IntegrationReviewOne"</code> |
| `source_commit` | <code>"172284e6415f464f91a6c76ce64b49b83555af4d"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"install.sh:refresh_projects_json/main; install.ps1:Update-ProjectsCheck/main; onboard.py:inspect_project_setup"</code> |
| `title` | <code>"完整项目前置检查晚于安装器写入"</code> |
| `problem` | <code>"check-projects只检查SBTD状态，外围可能先做全局或可选项目写入，再发现scaffold冲突。"</code> |
| `impact` | <code>"最终退出2但已有副作用，违反前置冲突零写入契约。"</code> |
| `recommendation` | <code>"共享完整只读判定，在所有外围mutation前执行，保持skip-project-agents目标范围。"</code> |
| `verification` | <code>"真实Bash red：可选npx写入合成marker后退出2；同一green不再写marker。两安装器×normal/project-only、范围定点、121项影响范围、589项全量及两fresh venv/13组CLI通过。tracer为受控替身，不冒充第三方安装。"</code> |
| `reviewed_commit` | <code>"bb5e3f2f0c0fde0fb012899c1f2b03c632311225"</code> |
| `closed_by` | <code>["P102PreflightReviewTwo", "P102EvidenceReviewTwo"]</code> |
| `decision` | <code>"两路独立复审确认P1关闭；保留原P1严重级别。最终提交验证仍按证据版本边界执行。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Complete project preflight runs before installer mutations and is rechecked at Python write boundary.", "evidence": ["install.sh", "install.ps1", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-45"></a>
### 45. P1-02-R1-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R1-P2-001"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P102StateReviewOne"</code> |
| `source_commit` | <code>"172284e6415f464f91a6c76ce64b49b83555af4d"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_project.py:456-459"</code> |
| `title` | <code>"未选择的任务根异常会阻断有效目标"</code> |
| `problem` | <code>"_read_task_record在读取选中记录前resolve两个任务根；无关根的symlink loop等异常也会使有效选中任务或bootstrap被blocked。"</code> |
| `impact` | <code>"只检查选中目标的边界被扩大，无关异常可能冻结本可安全进行的检查。"</code> |
| `recommendation` | <code>"按relative选择实际任务根，只解析该根后再执行contained-file检查。"</code> |
| `verification` | <code>"独立只读review；未执行针对性复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13记录，留待用户评估，不作为P0/P1门槛阻断。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Selected task containment is resolved first; unusable unrelated allowed roots are skipped while any valid physical task root still authorizes containment."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Selected task containment is resolved first; unusable unrelated allowed roots are skipped while any valid physical task root still authorizes containment.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-46"></a>
### 46. P1-02-R1-P2-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R1-P2-002"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P102StateReviewOne"</code> |
| `source_commit` | <code>"172284e6415f464f91a6c76ce64b49b83555af4d"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_project.py:582-583"</code> |
| `title` | <code>"项目根不可检查时legacy存在性被写成false"</code> |
| `problem` | <code>"_checked_root失败后使用_result默认legacy_present=False，虽然尚未检查.trellis；与后续不可检查legacy时返回null的语义不一致。"</code> |
| `impact` | <code>"JSON消费方可能把未知状态误解为已确认不存在。"</code> |
| `recommendation` | <code>"项目根不可检查的blocked分支传legacy_present=None。"</code> |
| `verification` | <code>"独立只读review；未执行针对性复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13作为P2保留，不擅自修复或降级为不存在。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Root-inspection failure now returns legacyPresent=None."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Root-inspection failure now returns legacyPresent=None.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-47"></a>
### 47. P1-02-R1-P2-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R1-P2-003"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P102StateReviewOne"</code> |
| `source_commit` | <code>"172284e6415f464f91a6c76ce64b49b83555af4d"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_project.py:126-134"</code> |
| `title` | <code>"损坏的bundled schema产生错误修复指引"</code> |
| `problem` | <code>"_bundled_schema只转换文件I/O错误；非法UTF-8/JSON或无效schema经通用_guard返回任务记录修复提示，而不是恢复安装内schema。"</code> |
| `impact` | <code>"用户可能被引导修改原本有效的项目状态，而真正故障在安装副本。"</code> |
| `recommendation` | <code>"识别schema解码/JSON/meta-schema失败并返回固定的schema恢复指引。"</code> |
| `verification` | <code>"独立只读review；未执行针对性复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13记录供后续评估；当前仍fail-closed，不作为合并阻断。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Unreadable, invalid UTF-8/JSON, non-object, and meta-schema-invalid bundled schemas direct repair to the bundle."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Unreadable, invalid UTF-8/JSON, non-object, and meta-schema-invalid bundled schemas direct repair to the bundle.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-48"></a>
### 48. P1-02-R1-P2-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R1-P2-004"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P102IntegrationReviewOne"</code> |
| `source_commit` | <code>"172284e6415f464f91a6c76ce64b49b83555af4d"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:26; install.sh/ install.ps1 source-root required lists"</code> |
| `title` | <code>"安装器完整性清单未包含新状态模块"</code> |
| `problem` | <code>"onboard.py启动即导入sbtd_project，但两个安装器的source-root必需文件列表未增加scripts/sbtd_project.py；部分复制会先通过完整性检查再以ModuleNotFoundError失败。"</code> |
| `impact` | <code>"损坏安装副本缺少既有清晰的incomplete-source诊断。"</code> |
| `recommendation` | <code>"后续评估将新模块加入两端必需source-root条目及相应行为验证。"</code> |
| `verification` | <code>"独立只读review；未执行针对性复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13作为P2保留，不扩大本轮修复范围。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"两端 source-root 清单均要求 scripts/sbtd_project.py；不完整源在启动 Python 前拒绝。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "两端 source-root 清单均要求 scripts/sbtd_project.py；不完整源在启动 Python 前拒绝。", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "install.sh", "install.ps1", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-49"></a>
### 49. P1-02-R2-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R2-P2-001"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P102EvidenceReviewTwo"</code> |
| `source_commit` | <code>"bb5e3f2f0c0fde0fb012899c1f2b03c632311225"</code> |
| `location` | <code>"sbtd-workflow-onboard/REFERENCE.md:311-313"</code> |
| `reported_location` | <code>"review锚点422；实际旧字段清单位于311-313"</code> |
| `title` | <code>"项目检查字段清单仍列旧trellis对象"</code> |
| `problem` | <code>"Project Checks早期字段清单仍列trellis.initialized/bootstrapRequired，现行build_project_check只输出sbtd；同文后段已描述新字段。"</code> |
| `impact` | <code>"按旧清单实现的消费者会读取不存在的键。"</code> |
| `recommendation` | <code>"后续将该清单改为真实sbtd status/reason/nextStep/validationScope/activeTask/bootstrapTask/legacyPresent。"</code> |
| `verification` | <code>"独立只读review并定位旧清单；本轮不改文案。"</code> |
| `decision` | <code>"按D-IMP-13保留P2供用户后续评估。"</code> |
| `verified_fixed_by` | <code>"7f64a281fee5af28aa3dede02fe56992ec5570b7"</code> |
| `resolution` | <code>"复核发现基线已包含修复，不重复实现。Current REFERENCE project check list already names sbtd and explicitly removes trellis.* aliases (lines 306-313)."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "already-fixed", "decision": "Current REFERENCE project check list already names sbtd and explicitly removes trellis.* aliases (lines 306-313).", "evidence": ["sbtd-workflow-onboard/REFERENCE.md", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-50"></a>
### 50. P1-02-R2-P2-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R2-P2-002"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P102EvidenceReviewTwo"</code> |
| `source_commit` | <code>"bb5e3f2f0c0fde0fb012899c1f2b03c632311225"</code> |
| `location` | <code>"sbtd-workflow-onboard/REFERENCE.md:107-108,144; README.md:724; install.sh/install.ps1 help"</code> |
| `title` | <code>"部分说明仍把CLI修复或项目前置检查放错顺序"</code> |
| `problem` | <code>"REFERENCE步骤10写全局资产后步骤11才写“Python写入前”检查；部分README和两端help仍描述收集项目输入前立即修复CLI。实际只读查询可提前，所有mutation已在完整项目gate之后。"</code> |
| `impact` | <code>"公开文档对实际前置屏障顺序描述不一致。"</code> |
| `recommendation` | <code>"后续统一早期只读查询与延后安装的边界，删除或移动过时步骤。"</code> |
| `verification` | <code>"独立只读review确认实现顺序正确；本轮不修复低优先级文案。"</code> |
| `decision` | <code>"P2 deferred，不阻断P0/P1门槛。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"REFERENCE、README 和 Bash/PowerShell help 对齐：只读 CLI 探测可提前，所有修复安装须等完整项目前置检查。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "REFERENCE、README 和 Bash/PowerShell help 对齐：只读 CLI 探测可提前，所有修复安装须等完整项目前置检查。", "evidence": ["sbtd-workflow-onboard/REFERENCE.md", "README.md", "install.sh", "install.ps1", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-51"></a>
### 51. P1-02-R2-P2-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R2-P2-003"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P102EvidenceReviewTwo"</code> |
| `source_commit` | <code>"bb5e3f2f0c0fde0fb012899c1f2b03c632311225"</code> |
| `location` | <code>"README.md:266; prompts/automations/sbtd-workflow-tools-version-check.md:18"</code> |
| `reported_location` | <code>"review锚点README.md:284；实际过时引言位于266"</code> |
| `title` | <code>"历史Trellis段仍被称为现有过渡实现"</code> |
| `problem` | <code>"README引言和automation维护边界仍称Trellis安装/bootstrap为当前v1过渡实现，与P1-02已移除调用及HTML历史边界不一致。"</code> |
| `impact` | <code>"后续文档维护可能误恢复已移除的执行建议。"</code> |
| `recommendation` | <code>"后续将相关旧段统一标为历史部署说明，不再称现行实现。"</code> |
| `verification` | <code>"独立只读review并核对具体段落；未修改。"</code> |
| `decision` | <code>"按用户P2门槛记录待评估，不追加修复。"</code> |
| `verified_fixed_by` | <code>"7f64a281fee5af28aa3dede02fe56992ec5570b7"</code> |
| `resolution` | <code>"复核发现基线已包含修复，不重复实现。Current README and automation describe Trellis/GitNexus only as retired migration/history; prior transitional wording was superseded."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "already-fixed", "decision": "Current README and automation describe Trellis/GitNexus only as retired migration/history; prior transitional wording was superseded.", "evidence": ["prompts/automations/sbtd-workflow-tools-version-check.md", "README.md", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-52"></a>
### 52. P1-02-R2-P2-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R2-P2-004"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P102EvidenceReviewTwo"</code> |
| `source_commit` | <code>"bb5e3f2f0c0fde0fb012899c1f2b03c632311225"</code> |
| `location` | <code>"prompts/automations/sbtd-workflow-tools-version-check.md:source/read/keyword/structural inventories;91-92"</code> |
| `title` | <code>"automation只读范围漏掉新的状态模块"</code> |
| `problem` | <code>"新增验证要求覆盖状态解析，但exclusive read allowlist及读取/关键词/结构检查清单没有scripts/sbtd_project.py。"</code> |
| `impact` | <code>"按允许清单执行的自动化不能读取sbtd结果生产者与依赖处理实现。"</code> |
| `recommendation` | <code>"后续在相关自动化读取/验证清单加入新模块；与source-root完整性P2分开处理。"</code> |
| `verification` | <code>"独立只读review；未运行或修改live automation。"</code> |
| `decision` | <code>"P2 deferred；本轮不修改其清单。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"版本化 automation 的只读允许、关键词影响、结构检查范围纳入 sbtd_project.py；未操作 live automation。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "版本化 automation 的只读允许、关键词影响、结构检查范围纳入 sbtd_project.py；未操作 live automation。", "evidence": ["prompts/automations/sbtd-workflow-tools-version-check.md", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-53"></a>
### 53. P1-02-R2-P3-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-02-R2-P3-001"</code> |
| `task` | <code>"P1-02"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P102EvidenceReviewTwo"</code> |
| `source_commit` | <code>"bb5e3f2f0c0fde0fb012899c1f2b03c632311225"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md:1153"</code> |
| `title` | <code>"检查中台账仍引用较早验证数量"</code> |
| `problem` | <code>"checking行保留587 tests/11场景，而同提交任务记录已有修复后589 tests/13场景。"</code> |
| `impact` | <code>"属于低报而非伪造通过，但读者需要对照两个历史快照。"</code> |
| `recommendation` | <code>"后续更新为最新数值或不在临时状态行重复计数；实际merge后的完成登记仍按既有必经流程执行。"</code> |
| `verification` | <code>"独立只读review；当前不为P3追加修复。"</code> |
| `decision` | <code>"按D-IMP-13记录，完成登记自然发生前保持deferred，不提前填写done或merge事实。"</code> |
| `verified_fixed_by` | <code>"7f64a281fee5af28aa3dede02fe56992ec5570b7"</code> |
| `resolution` | <code>"复核发现基线已包含修复，不重复实现。Current master PRD P1-02 row is done with final merged validation evidence; original checking count is retained only in historical events."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "already-fixed", "decision": "Current master PRD P1-02 row is done with final merged validation evidence; original checking count is retained only in historical events.", "evidence": ["docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md", "sbtd-workflow-onboard/scripts/sbtd_project.py", "tests/test_sbtd_project.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-54"></a>
### 54. P1-03-R1-P1-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P1-001"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103RuntimeReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/graft_runtime.py:_locate_package/_verify_installation"</code> |
| `title` | <code>"包名文本与邻接metadata不能证明执行身份"</code> |
| `problem` | <code>"小型非symlink脚本只需含包名注释就被信任；包内其他文件和post-install旧binary也可绕过目标绑定。"</code> |
| `impact` | <code>"未确认check或安装验证可执行不属于受支持CLI的代码。"</code> |
| `recommendation` | <code>"绑定实际package-owned CLI并由检测和安装验证共用；未知shim不得执行。"</code> |
| `verification` | <code>"两个真实marker红测修前均错误available；修后含post-install的三个非执行回归与44项影响范围通过。reviewer源码复核关闭，未自行运行验证。"</code> |
| `decision` | <code>"有效P1已修复；Windows未知shim保守blocked，Windows适配/真执行仍归P1-08。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Exact package-owned dist/cli.js and pinned metadata required; unknown shim blocked.", "evidence": ["sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-55"></a>
### 55. P1-03-R1-P1-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P1-002"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103IntegrationReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:build_check_results/build_installation_report/print_check_results; graft_runtime.py:globalInstall"</code> |
| `title` | <code>"可选Graft进入强制安装管线并推荐绕过handler"</code> |
| `problem` | <code>"generic tools/missing/report丢弃Graft状态并生成原始npm全局安装建议。"</code> |
| `impact` | <code>"消费者可能绕过唯一handler的SRI、DNT/CI、native allowlist、telemetry安全门。"</code> |
| `recommendation` | <code>"保留tools投影但明确optional，排除required缺失/安装报告，独立human状态；仅建议受管入口。"</code> |
| `verification` | <code>"missing与conflict两状态红测修前失败；修后44项影响范围通过，独立review源码复核关闭。"</code> |
| `decision` | <code>"有效P1已修复，不改变普通任务可降级与显式安装失败非零的边界。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Graft optional and excluded from generic required install report.", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-56"></a>
### 56. P1-03-R1-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-001"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103RuntimeReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/graft_runtime.py:_persist_telemetry_disabled"</code> |
| `title` | <code>"最终比较与replace不是CAS"</code> |
| `problem` | <code>"真实Graft无锁writer可在最后read与os.replace之间提交更新；旧快照会覆盖新增未知字段，readback无法发现已丢变化。"</code> |
| `impact` | <code>"telemetry并发状态保全存在窗口，不涉及项目或GitNexus数据删除。"</code> |
| `recommendation` | <code>"后续评估所有写入方共享的条件更新/锁协议，或明确停止并发Graft写入；仅Python加锁不约束上游。"</code> |
| `verification` | <code>"独立源码分析；未运行实际竞争测试或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期，留待用户评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Compare/replace race exists, but no shared upstream lock/CAS is proven; no demonstrated project/data-loss path.", "evidence": ["sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "按用户明确选择：已有 mutable telemetry 零写入拒绝；缺失时 hard-link no-clobber 创建；已关闭时只读", "verification": "已有字段／权限保全、并发创建者不被覆盖、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-57"></a>
### 57. P1-03-R1-P2-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-002"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103RuntimeReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/graft_runtime.py:_managed_env/_first_line"</code> |
| `title` | <code>"dotenv调试输出可污染版本探测"</code> |
| `problem` | <code>"继承DOTENV_CONFIG_DEBUG=1或QUIET=false时，固定dotenv在版本前输出日志，第一行被当成版本。"</code> |
| `impact` | <code>"正常check误blocked，安装完成后误报verify-install失败并跳过telemetry持久化。"</code> |
| `recommendation` | <code>"后续隔离dotenv日志开关并覆盖相应真实探测。"</code> |
| `verification` | <code>"独立核对固定包dotenv stdout路径；未运行复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"移除继承的 dotenv debug/quiet 控制，受管子进程强制 DOTENV_CONFIG_QUIET=true，避免 stdout 横幅污染版本。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "移除继承的 dotenv debug/quiet 控制，受管子进程强制 DOTENV_CONFIG_QUIET=true，避免 stdout 横幅污染版本。", "evidence": ["sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-58"></a>
### 58. P1-03-R1-P2-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-003"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103RuntimeReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/graft_runtime.py:_check_graft/_install_graft"</code> |
| `title` | <code>"已有CLI成功分支忽略明确不兼容Node"</code> |
| `problem` | <code>"若旧Node仍能运行--version，check仅记录compatible=false却仍available，已有安装分支绕过新安装Node门。"</code> |
| `impact` | <code>"不符合冻结包Node&gt;=20支持契约；实际旧Node触发未运行，置信medium。"</code> |
| `recommendation` | <code>"后续区分未知与明确unsupported Node，在已有CLI成功前拒绝明确不兼容。"</code> |
| `verification` | <code>"源码审查，未作真实旧Node实验或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期，不把未验证假设当运行失败。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"check_graft now blocks an otherwise verified pinned CLI when node.compatible is explicitly false; unknown Node remains unchanged."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "check_graft now blocks an otherwise verified pinned CLI when node.compatible is explicitly false; unknown Node remains unchanged.", "evidence": ["sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-59"></a>
### 59. P1-03-R1-P2-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-004"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103IntegrationReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:build_plan_payload/print_plan"</code> |
| `title` | <code>"human plan遗漏Graft状态"</code> |
| `problem` | <code>"JSON payload含graft，但print_plan未消费；直接human plan及安装器Final plan丢弃可用/阻断状态。"</code> |
| `impact` | <code>"文本计划不能完整呈现本地能力；JSON仍有真实状态。"</code> |
| `recommendation` | <code>"后续增加human Graft渲染并保持init-projects不探测全局能力。"</code> |
| `verification` | <code>"独立源码审查；未修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"human plan 输出 Graft status/reason/nextStep，与 JSON 口径一致。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "human plan 输出 Graft status/reason/nextStep，与 JSON 口径一致。", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-60"></a>
### 60. P1-03-R1-P2-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-005"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103IntegrationReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:build_installation_report/print_check_results"</code> |
| `title` | <code>"npm条件依赖仍被报告为必须修复"</code> |
| `problem` | <code>"已有Agent/Graft而npm缺失时，generic runtime报告仍放入failedOrMissing并无条件提示安装npm；并未选择npm-backed安装动作。"</code> |
| `impact` | <code>"报告可能驱动不必要的npm准备，虽然本地工具探测已解耦。"</code> |
| `recommendation` | <code>"后续按选定动作报告条件性需求，未选择安装不生成强制bootstrap建议。"</code> |
| `verification` | <code>"独立源码审查；未修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"未选 npm-backed 操作的 runtime 缺失归入 conditionalRuntime，不进入 missing.runtime 或失败计数；实际安装仍检查依赖。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "未选 npm-backed 操作的 runtime 缺失归入 conditionalRuntime，不进入 missing.runtime 或失败计数；实际安装仍检查依赖。", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-61"></a>
### 61. P1-03-R1-P2-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-006"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103IntegrationReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"docs/assets/onboard-skill-init.md:35-40; docs/assets/onboard-skill-reset.md"</code> |
| `title` | <code>"流程图未完整区分Graft探针状态"</code> |
| `problem` | <code>"图按是否已验证CLI分流，未体现blocked警告继续与已装但telemetry未关闭仍需确认。"</code> |
| `impact` | <code>"文档分支与实际already-installed/blocked/needs-confirmation契约有偏差。"</code> |
| `recommendation` | <code>"后续按三种真实status绘制两张图，不从二值installed推断授权路径。"</code> |
| `verification` | <code>"独立源码与图表对照；未修改低优先级文案。"</code> |
| `decision` | <code>"按D-IMP-13原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"init/reset 流程图按 already-installed/blocked/needs-confirmation 分流，明确仅 telemetry 的确认分支。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "init/reset 流程图按 already-installed/blocked/needs-confirmation 分流，明确仅 telemetry 的确认分支。", "evidence": ["docs/assets/onboard-skill-init.md", "docs/assets/onboard-skill-reset.md", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-62"></a>
### 62. P1-03-R1-P2-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-007"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103IntegrationReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"install.sh:ensure_graft_cli; install.ps1:Ensure-GraftCli"</code> |
| `title` | <code>"telemetry-only动作仍显示完整安装确认"</code> |
| `problem` | <code>"已有pinned CLI但缺telemetry opt-out时，实际确认后仅写telemetry，wrapper仍展示npm/native安装计划并询问Install CLI。"</code> |
| `impact` | <code>"用户可能误以为将重装；telemetry目标和enabled=false仍已展示。"</code> |
| `recommendation` | <code>"后续按before.installed分别展示telemetry-only与完整安装确认。"</code> |
| `verification` | <code>"独立源码审查；未修改。"</code> |
| `decision` | <code>"按D-IMP-13原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"两端展示 telemetry-only 计划并传 --telemetry-only，handler 复核 CLI 后只执行该动作；状态变化时阻断，不扩大为安装。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "两端展示 telemetry-only 计划并传 --telemetry-only，handler 复核 CLI 后只执行该动作；状态变化时阻断，不扩大为安装。", "evidence": ["install.sh", "install.ps1", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-63"></a>
### 63. P1-03-R1-P2-008

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R1-P2-008"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P103IntegrationReviewOne"</code> |
| `source_commit` | <code>"dc5fe800e573232237ddd1e3e923bb327972e755"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:print_check_results"</code> |
| `title` | <code>"Graft blocked在generic输出误显示missing"</code> |
| `problem` | <code>"unknown binary/native/版本冲突的blocked被二值installed渲染成missing。"</code> |
| `impact` | <code>"状态展示不准确。"</code> |
| `recommendation` | <code>"保留专属status/reason/nextStep。"</code> |
| `verification` | <code>"P1-002修复必需的optional独立展示同时消除此问题；独立review确认关闭。"</code> |
| `decision` | <code>"不是为P2扩展修复，而是同一P1安全消费者切面的直接结果。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Optional Graft excluded from generic missing-required output, preserving blocked status.", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-64"></a>
### 64. P1-03-R2-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-03-R2-P2-001"</code> |
| `task` | <code>"P1-03"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P103StatusReview (independent stateless completion)"</code> |
| `source_commit` | <code>"908a8a65952ee82ce0381a5955000c3b26daab15"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md:P1-03 checking→done event"</code> |
| `title` | <code>"metadata复核措辞可能混淆实现收口与状态PR审查"</code> |
| `problem` | <code>"状态review认为“独立源码及metadata复核”可能被理解为当前status PR已完成审查。"</code> |
| `impact` | <code>"审查对象与时序的表述有潜在歧义，不构成已证实P0/P1。"</code> |
| `recommendation` | <code>"后续评估是否分别具名实现review、candidate metadata review和status review。"</code> |
| `verification` | <code>"实际在实现PR前已完成独立stateless candidate evidence/metadata review且无新增P0/P1；本次status review也已执行并通过。该上下文保留，不将措辞意见冒充缺少审查的运行事实。"</code> |
| `decision` | <code>"按D-IMP-13保留原P2供用户评估，不为此改写已核实完成事实。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Historical PRD review wording ambiguity, not runtime/data defect.", "evidence": ["docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md", "sbtd-workflow-onboard/scripts/graft_runtime.py", "tests/test_graft_runtime.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "总 PRD 追加审查对象澄清，区分实现候选源码／metadata 与后续状态 PR；不改历史时间和 SHA", "verification": "文档核对、workflow contracts、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-65"></a>
### 65. P1-17-R1-DOC-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-001"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:_event_table/TaskDocument.updated"</code> |
| `title` | <code>"未闭合代码围栏吞掉新增状态事件"</code> |
| `problem` | <code>"旧手写扫描允许把事件表追加到未闭合fence中，状态字段可落盘但新事件无法回读。"</code> |
| `impact` | <code>"状态与事件失配，阻塞/完成历史可能丢失。"</code> |
| `recommendation` | <code>"按真实Markdown块识别权威表，写入前验证完整旧事件加新事件。"</code> |
| `verification` | <code>"真实TaskStore文件路径红测复现；CommonMark显式table规则和精确回读修复后77项影响范围通过，独立源码复核确认P1关闭。"</code> |
| `decision` | <code>"修复仅使用parse/token map，不渲染或联网；声明markdown-it-py并在私有venv实际安装。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "CommonMark token parsing and exact candidate reread prevent unclosed fences swallowing events.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-66"></a>
### 66. P1-17-R1-DOC-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-002"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:_event_table"</code> |
| `title` | <code>"代码示例被当作权威事件表"</code> |
| `problem` | <code>"strip去掉代码缩进，并把带正文后缀的fence行误判为闭合；示例表可成为历史并被修改。"</code> |
| `impact` | <code>"用户正文被改写，虚构示例事件进入任务状态。"</code> |
| `recommendation` | <code>"仅采用顶层可见h2与table的真实Markdown token范围。"</code> |
| `verification` | <code>"四空格代码、伪closer与HTML注释三种真实文件反例先失败；修后示例保持原文且只有真实事件进入历史，独立复核确认关闭。"</code> |
| `decision` | <code>"不使用输入特判或删除用户示例规避问题。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Only a top-level 状态事件 h2 plus top-level table is authoritative; examples remain body bytes.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-67"></a>
### 67. P1-17-R1-DOC-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-003"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:_cells/_event_table"</code> |
| `title` | <code>"可选外侧pipe导致后续历史被截断"</code> |
| `problem` | <code>"旧循环遇无前导pipe的合法表数据行即成功结束，忽略其后事件并在错误位置追加。"</code> |
| `impact` | <code>"恢复可能采用过时ingress或漏掉矛盾历史。"</code> |
| `recommendation` | <code>"消费完整table token.map，接受可选外侧pipe，完整回读校验。"</code> |
| `verification` | <code>"旧实现把冲突历史截断并恢复planned；新实现完整读取后要求用户选择，显式选择checking再保存，既有三行保留。77项影响范围通过，独立复核确认关闭。"</code> |
| `decision` | <code>"集成fixture本身有历史矛盾，修正测试为先询问再选择；没有放宽消费者历史规则。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Full token table range is consumed and exact reread rejects truncation.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-68"></a>
### 68. P1-17-R1-DOC-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-004"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:_cells/_event_row"</code> |
| `title` | <code>"事件codec仍会拒绝部分合法首尾空白文本"</code> |
| `problem` | <code>"写入未对首尾空白做可逆编码，读取cell.strip会规范化；新增精确回读门将这些合法事件拒绝。"</code> |
| `historical_observation` | <code>"原审查的Unicode内部换行误拆与静默空白丢失已随P1行映射/完整回读修复消除，不再当作当前事实。"</code> |
| `impact` | <code>"部分合法reason/evidence不能保存；当前不会静默丢失后继续提交。"</code> |
| `recommendation` | <code>"后续评估可逆边界空白编码与文本覆盖，不随本轮P1扩展。"</code> |
| `verification` | <code>"独立修复后源码复核收窄剩余问题；未追加P2修复或运行其专项测试。"</code> |
| `decision` | <code>"按D-IMP-13原P2延期，十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Added reversible edge-whitespace entity encoding in _event_cell/_event_row."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Added reversible edge-whitespace entity encoding in _event_cell/_event_row.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-69"></a>
### 69. P1-17-R1-DOC-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-005"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:TaskDocument.updated event insertion"</code> |
| `title` | <code>"既有表末行没有换行时无法追加"</code> |
| `problem` | <code>"既有完整事件行位于EOF且无最终换行时，新行直接与旧行拼接，候选解析失败。"</code> |
| `impact` | <code>"合法旧任务的状态写入被拒绝，原文仍保留。"</code> |
| `recommendation` | <code>"后续评估在既有表末行与新事件之间补必要分隔换行。"</code> |
| `verification` | <code>"独立源码审查；未修改或运行专项复现。"</code> |
| `decision` | <code>"P2原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Adds one required newline before appending an event after an EOF table row without a final newline."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Adds one required newline before appending an event after an EOF table row without a final newline.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-70"></a>
### 70. P1-17-R1-DOC-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-006"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_project.py:_check_json_compatible"</code> |
| `title` | <code>"非循环YAML别名DAG可触发重复指数遍历"</code> |
| `problem` | <code>"兼容性检查只维护当前递归路径，共享的非循环alias子树可被反复遍历。"</code> |
| `impact` | <code>"小型合法YAML可能造成较高CPU消耗；循环仍被拒绝。"</code> |
| `recommendation` | <code>"后续评估已完成节点去重或明确预算，保持cycle判断与语义校验。"</code> |
| `verification` | <code>"独立源码分析；未做性能实验或修复。"</code> |
| `decision` | <code>"P2原级延期，不扩大当前parser修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"validate_json_compatible now uses per-call seen-node tracking while retaining active-path cycle detection and non-JSON checks."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "validate_json_compatible now uses per-call seen-node tracking while retaining active-path cycle detection and non-JSON checks.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_project.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-71"></a>
### 71. P1-17-R1-DOC-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-007"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:TaskDocument.updated flow additions"</code> |
| `title` | <code>"flow YAML尾逗号后注释会使新增字段失败"</code> |
| `problem` | <code>"用rstrip().endswith(',')判断尾逗号会看到注释而误判，新增blocked_reason可能形成双逗号。"</code> |
| `impact` | <code>"合法flow frontmatter候选解析失败，原文件安全保留。"</code> |
| `recommendation` | <code>"后续按YAML token/span处理插入边界，保留注释。"</code> |
| `verification` | <code>"独立源码审查；未修改或运行专项测试。"</code> |
| `decision` | <code>"P2原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Flow-map additions inspect the final value's lexical trailer, so a comma before a comment remains recognized."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Flow-map additions inspect the final value's lexical trailer, so a comma before a comment remains recognized.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-72"></a>
### 72. P1-17-R1-DOC-008

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R1-DOC-008"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P117DocumentSafetyReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:TaskDocument.updated scalar replacement"</code> |
| `title` | <code>"块标量头部注释未保全"</code> |
| `problem` | <code>"替换完整ScalarNode span时，mode_note: &#124;-等块标量头部的用户注释也被替换。"</code> |
| `impact` | <code>"字段值可正确更新，但该头部注释丢失；普通scalar旁注保全不受此项影响。"</code> |
| `recommendation` | <code>"后续区分值与块标量头注释跨度，补保全行为覆盖。"</code> |
| `verification` | <code>"独立源码审查；未修改或运行专项测试。"</code> |
| `decision` | <code>"P2原级延期。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Block-scalar header comments are retained when replacing owned scalar values."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Block-scalar header comments are retained when replacing owned scalar values.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-73"></a>
### 73. P1-17-A1-P1-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-A1-P1-001"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>0</code> |
| `source` | <code>"advisor and Main validation"</code> |
| `original_severity` | <code>"blocker"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_state.py:local protection; onboard.py:gitignore_verdicts"</code> |
| `title` | <code>"多个私有目标未取得独立ignore证明"</code> |
| `problem` | <code>"首稿用同一quiet调用检查多个目标，合法创建失败，也没有实际目标逐项保护证据。"</code> |
| `impact` | <code>"必要的首次持久化不可用；不能把任一匹配或探针汇总码当作全体私有路径安全。"</code> |
| `recommendation` | <code>"复用既有逐路径Git verdict解析，对实际task路径及active指针分别验证，保留受控Git环境。"</code> |
| `verification` | <code>"合法创建先失败；改用实际目标和共享verdict后，pointer-only/tasks-only/精确否定规则反例均零写入，状态与既有Onboard调用方影响验证通过。"</code> |
| `decision` | <code>"不声称已观察到未保护数据泄漏；记录实际失败与安全门缺口，后续完整review仍覆盖该路径。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Actual .sbtd, active, and task paths receive individual gitignore verdicts; tracked/unknown state blocks writes.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-74"></a>
### 74. P1-17-A1-P1-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-A1-P1-002"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>0</code> |
| `source` | <code>"advisor and Main validation"</code> |
| `original_severity` | <code>"blocker"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_state.py:transfer scope"</code> |
| `title` | <code>"目录嵌套曾隐式扩大到其他逻辑任务"</code> |
| `problem` | <code>"提升foo目录会把foo/bar/task.md的独立逻辑任务一并发布/退役，不能仅从路径关系推断所有权。"</code> |
| `impact` | <code>"可越过任务级共享/迁移授权范围。"</code> |
| `recommendation` | <code>"默认拒绝额外task.md；确需多任务时以include_tasks逐个显式授权并核对闭集。"</code> |
| `verification` | <code>"默认提升嵌套任务的真实文件红测复现；修后拒绝且源/引用/目标零变化，显式完整scope才通过两阶段提升。"</code> |
| `decision` | <code>"同一scope守卫复用于归档；退休仍须目标准备后的独立确认，不递归删除原件。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Transfer scope is explicit rather than inferred recursively from directory nesting.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-75"></a>
### 75. P1-17-R2-STATE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-001"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._transfer / _publish_tree private destination protection"</code> |
| `title` | <code>"[P1] 私有传输没有验证实际目标及附件的完整 ignore 保护"</code> |
| `problem` | <code>"Git 项目使用选择性 ignore 时，_transfer 只验证 source_file；本地 archive 的新目标从未送入 ignore 校验。候选区与原件退役区也只验证 task/task.md，却复制或移动整个目录。因此现有检查全部通过后，私有 task.md 或附件仍可落到 Git 可见路径；原件退役后的附件暴露是持久的，不依赖并发 writer。"</code> |
| `recommendation` | <code>"任何 copy/rename 前，用现有 manifest 与逐路径 Git verdict 验证全部实际私有目标：本地 archive 目标、候选树、原件保留树及每个文件；或证明相应完整目录被忽略且子项不能重新暴露。不能用源路径或 task.md 的 ignore 结论替代整个目标树；缺保护时零发布并提示窄授权。"</code> |
| `verification` | <code>"Main真实红/绿及known/null历史、local archive变体通过；95项影响范围和修复后的307文件/10原生进程smoke通过。对应独立reviewer只读复核确认无剩余P0/P1；未冒称reviewer执行验证。"</code> |
| `decision` | <code>"P1已修复并独立闭环；本轮低级finding保持原级延期。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Transfer validates temporary/destination protection and complete manifests before rename.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-76"></a>
### 76. P1-17-R2-STATE-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-002"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore.reopen historical completion insertion after archive metadata"</code> |
| `title` | <code>"[P1] 归档后的无完成事件历史任务被重开为自相矛盾的事件链"</code> |
| `problem` | <code>"合法历史 done 任务可以只有 completed_at 而没有完成事件。archive 会先写一个当前时间 done→done 归档事件；随后 reopen 发现没有完成事件，把旧时间 unknown→done 补录追加在归档事件后，再追加 done→planned 并成功落盘。该顺序既把已知 done 链接到 from=unknown，又可能倒退时间；下一次 transition 必被 _history 拒绝。所有步骤均可由受支持的单 writer 调用触发。"</code> |
| `recommendation` | <code>"无完成事件但已有 done→done 元数据历史时，把有来源的旧完成事实插入到这些元数据事件之前，保持已有行/证据不变；或在首次添加归档元数据前统一建立正确的完成历史。发布前校验完整候选链，不能只让语法回读通过，也不能仅拒绝掉已承诺支持的历史重开。"</code> |
| `verification` | <code>"Main真实红/绿及known/null历史、local archive变体通过；95项影响范围和修复后的307文件/10原生进程smoke通过。对应独立reviewer只读复核确认无剩余P0/P1；未冒称reviewer执行验证。"</code> |
| `decision` | <code>"P1已修复并独立闭环；本轮低级finding保持原级延期。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "reopen prepends missing historical completion and validates candidate history before saving.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-77"></a>
### 77. P1-17-R2-STATE-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-003"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore.create completed ancestor check"</code> |
| `title` | <code>"[P2] 创建新子任务不会使已完成祖先退出 done"</code> |
| `problem` | <code>"只用公开 API 即可先把父任务完成，再 create 新的 planned 子任务并指定该 parent。create 只验证父引用存在/无环，不检查祖先状态，因而父级仍保留 done/completed_at，尽管新增后代尚未完成。这绕过现有 transition 的后代完成门以及 reopen 的祖先联动；新子任务本身不是 done，不能用 reopen(child)补救。"</code> |
| `recommendation` | <code>"新增带 parent 的任务前检查祖先链；若存在 done 祖先，零写入并要求用户先显式 reopen 相应祖先。无需把 create 扩成新的跨文件自动重开事务。按 D-IMP-13 以 P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"TaskStore.create rejects a newly created child below any done ancestor before writes."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "TaskStore.create rejects a newly created child below any done ancestor before writes.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-78"></a>
### 78. P1-17-R2-STATE-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-004"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._transfer reserved index namespace guard"</code> |
| `title` | <code>"[P2] 提升 index.md/ 子路径会先把共享索引路径建成目录"</code> |
| `problem` | <code>"create 对共享路径使用完整 index.md/ 前缀排除，但 promote 只排除 target_dir 恰好等于 ai/tasks/index.md。合法本地 ID index.md/child 因此能够进入发布阶段：目标复制把 ai/tasks/index.md 建成目录，随后索引写入失败。原件和目标同时存在，重试永久被非普通文件索引阻断，正常 catalog 也因重复 ID 不能使用。"</code> |
| `recommendation` | <code>"发布前复用 create 对共享索引整个保留路径空间的判定，拒绝 index.md 自身及其任何后代，保留大小写不敏感文件系统处理。已有冲突时零写入。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"_transfer reserves ai/tasks/index.md and every descendant."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "_transfer reserves ai/tasks/index.md and every descendant.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-79"></a>
### 79. P1-17-R2-STATE-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-005"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._transfer source/target ancestry preflight"</code> |
| `title` | <code>"[P2] archive 允许把目标发布到原任务目录内部，随后无法重试"</code> |
| `problem` | <code>"逻辑 ID archive 合法且可以通过 create 建立；其原目录恰好是 &lt;storage&gt;/archive。归档目标 &lt;storage&gt;/archive/&lt;quarter&gt;/archive 位于原目录内部。预检没有排除这种包含关系；发布目标先改变原目录，紧接着源 manifest 核对失败，留下嵌套双副本。后续普通操作因重复 ID 阻断，archive 自身也无法通过完整树对账。"</code> |
| `recommendation` | <code>"任何文件系统写入前比较规范化源/目标目录；拒绝相同或互为祖先的转移，并说明路径冲突。不要等发布后依赖 manifest 把自身造成的变动识别成并发冲突。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"_transfer rejects source/target directory ancestry overlap before transfer preparation."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "_transfer rejects source/target directory ancestry overlap before transfer preparation.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-80"></a>
### 80. P1-17-R2-STATE-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-006"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._records os.walk error handling"</code> |
| `title` | <code>"[P2] catalog 静默跳过无法遍历的目录，仍允许建立重复逻辑 ID"</code> |
| `problem` | <code>"_records 使用没有 onerror 的 os.walk，权限或扫描 I/O 错误被 Python 默认忽略。_catalog 因而把不完整扫描当成完整记录集，继续做唯一性与 DAG 校验。一个不可读本地任务子目录中已有 ID 的情况下，create 可以在可写共享目录创建同 ID 新任务并报告成功；恢复权限后两个记录都被判定冲突。"</code> |
| `recommendation` | <code>"给 catalog 的 os.walk 设置 onerror，转成可解释的 TaskStateError 并中止依赖完整扫描的写操作；不能将无法读取当作不存在。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"_records raises on os.walk errors instead of omitting unreadable subtrees."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "_records raises on os.walk errors instead of omitting unreadable subtrees.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-81"></a>
### 81. P1-17-R2-STATE-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-007"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore.reopen ancestor mode validation"</code> |
| `title` | <code>"[P2] 子任务重开会绕过未知模式祖先的用户选择门"</code> |
| `problem` | <code>"reopen 只对被点名的子任务调用 _require_known_mode。祖先联动循环检查 branch、ignore 与历史，但不检查 workflow_mode。若已完成祖先为 schema 合法的 migration-unknown/null，而已完成子任务模式已知，reopen(child) 会把祖先写成 planned 并清空 completed_at，尽管用户从未选择该祖先的模式；直接 reopen(parent) 则会被正确拒绝。"</code> |
| `recommendation` | <code>"在任何祖先写入前，对所有要重开的 done 祖先复用 _require_known_mode；有未知模式即要求用户先选择并零写入，不自动默认模式。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"reopen checks every ancestor's workflow mode before preparing or writing reopen candidates."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "reopen checks every ancestor's workflow mode before preparing or writing reopen candidates.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-82"></a>
### 82. P1-17-R2-STATE-008

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-008"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore.create complete candidate history validation"</code> |
| `title` | <code>"[P2] create 接受与固定 planned 状态冲突的正文历史并落盘"</code> |
| `problem` | <code>"create 的 body 是调用方输入，能够包含真正顶层的状态事件表。TaskDocument.parse 只验证每行 schema/日期，create 没有验证完整链与其新建 planned frontmatter 一致。因此正文含合法 unknown→done 等历史时，新任务仍以 planned 成功创建并成为 active；下一次 transition 才发现历史矛盾并阻断。"</code> |
| `recommendation` | <code>"首次写入前验证完整事件链与新任务状态/时间的一致性；如果 create 不支持导入历史，则明确拒绝正文中非空的权威历史，而不是存入冲突状态。保留正文，不尝试自动改写或伪造历史。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"create rejects body event histories inconsistent with planned frontmatter."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "create rejects body event histories inconsistent with planned frontmatter.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-83"></a>
### 83. P1-17-R2-STATE-009

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-009"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._now event timestamp boundary"</code> |
| `title` | <code>"[P2] nullable 历史字段使未来事件绕过时钟门并生成倒序新历史"</code> |
| `problem` | <code>"历史 created_at/updated_at 可以为 null。只要最后事件时间在未来，_history 在 updated_at=null 时不做上界检查，_now 又只检查这两个 frontmatter 字段，状态操作就会把当前时间的新事件追加到未来事件后。写入返回成功，但新历史随即因时间倒退而不能继续推进。"</code> |
| `recommendation` | <code>"追加实际时间事件前，将文档内已知事件时间及相关完成时间纳入当前时钟边界检查；未知值仍保持未知，不用当前时间修补旧事件。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"_now rejects future created/updated/completed timestamps and future known events."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "_now rejects future created/updated/completed timestamps and future known events.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-84"></a>
### 84. P1-17-R2-STATE-010

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-STATE-010"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117StateFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._publish_tree committed publication versus cleanup failure"</code> |
| `title` | <code>"[P2] 候选清理失败会漏报已经发布的传输目标"</code> |
| `problem` | <code>"_publish_tree 先把候选目录 rename 到正式目标，再在 finally 清理候选容器。若这一步清理因文件系统错误或目录 ACL 失败，函数不会返回；调用方直到返回后才 append(target_dir)，因此 TaskStateError.completed_steps 被报告为空，尽管正式目标已存在、双副本冲突已经形成。原件保全仍有效，但部分成功报告不真实。"</code> |
| `recommendation` | <code>"在 rename 成功处记录并向调用方保留已发布事实；清理失败作为独立、可观察失败传播，但不能抹掉 target_dir 已完成步骤。无需回滚或删除正式目标。P2 原级延期。"</code> |
| `verification` | <code>"独立只读源码审查；未执行专项复现或修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期；P1累计十项门统一评估，未经用户确认不修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Post-publish candidate cleanup failures report the published target in completed_steps."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Post-publish candidate cleanup failures report the published target in completed_steps.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-85"></a>
### 85. P1-17-R2-SURFACE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-SURFACE-001"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117SurfaceFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/REFERENCE.md:370-370"</code> |
| `title` | <code>"Document which unconfirmed operations return previews"</code> |
| `problem` | <code>"The new public contract says every call with `confirmed=False` returns a read-only planned result, but `create`, `select`, `transition`, `set_mode`, `resume`, `reopen`, and `protect_local_state` all reach `_authorize()` and raise `TaskStateError`; only `promote` and `archive` return `TaskTransfer(status=\"needs-confirmation\", ...)`. A host-native caller following this reference cannot obtain the promised preview for the ordinary task operations. Either add explicit preview results for those operations or narrow this statement (and the identical `state.md`/P1-17 task-document statements) to the two transfer operations."</code> |
| `verification` | <code>"只读源码/文档审查；未修改。"</code> |
| `decision` | <code>"按D-IMP-13原级延期，不随P1修复扩大变更。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"REFERENCE、state.md 和 P1-17 说明区分仅 transfer 提供预览；普通写调用缺确认抛 TaskStateError 且零写入。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "REFERENCE、state.md 和 P1-17 说明区分仅 transfer 提供预览；普通写调用缺确认抛 TaskStateError 且零写入。", "evidence": ["sbtd-workflow-onboard/REFERENCE.md", "sbtd-workflow-onboard/templates/skills/sbtd-task/references/state.md", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-86"></a>
### 86. P1-17-R2-SURFACE-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-SURFACE-002"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117SurfaceFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_document.py:91-93"</code> |
| `title` | <code>"Reject a second event table in the same section"</code> |
| `problem` | <code>"After finding the single `## 状态事件` heading, `_event_table` parses only the first token at `headings[0] + 3` and never checks the remainder of that section for another top-level table. A task containing two event tables under that heading is therefore accepted with every row in the second table silently omitted; `resume()` can then derive a stale blocked ingress, and the complete-history check also passes because both the old and rewritten parses ignore the same rows. Scan until the next top-level h2 (or EOF) and reject any additional top-level event table before allowing an update."</code> |
| `verification` | <code>"Main真实红/绿及known/null历史、local archive变体通过；95项影响范围和修复后的307文件/10原生进程smoke通过。对应独立reviewer只读复核确认无剩余P0/P1；未冒称reviewer执行验证。"</code> |
| `decision` | <code>"P1已修复并独立闭环；本轮低级finding保持原级延期。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Remaining top-level section tokens are scanned and a second table is rejected.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_document.py", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-87"></a>
### 87. P1-17-R2-SURFACE-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-SURFACE-003"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117SurfaceFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-task-state-runtime.md:64-64"</code> |
| `title` | <code>"Document the boolean return from local protection"</code> |
| `problem` | <code>"The frozen API description groups every non-transfer operation under `TaskSnapshot`, but `protect_local_state()` returns `True` when it appends the rule and `False` when protection already exists. A caller using the task document as the public signature can therefore treat a boolean as a snapshot. List this operation's `bool` return separately (and keep the snapshot statement limited to `inspect`/create/select/state-changing methods)."</code> |
| `verification` | <code>"只读源码/文档审查；未修改。"</code> |
| `decision` | <code>"按D-IMP-13原级延期，不随P1修复扩大变更。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"文档单列 protect_local_state 的 bool 返回，不再把它列为 TaskSnapshot。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "文档单列 protect_local_state 的 bool 返回，不再把它列为 TaskSnapshot。", "evidence": ["docs/prd/sbtd-workflow-v2-task-state-runtime.md", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-88"></a>
### 88. P1-17-R2-SURFACE-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-17-R2-SURFACE-004"</code> |
| `task` | <code>"P1-17"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P117SurfaceFullReview"</code> |
| `source_commit` | <code>"c0f2281c9cace8304506df3cf96bd68f7c133798"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-task-state-runtime.md:64-64"</code> |
| `title` | <code>"Describe document parse failures at the public error boundary"</code> |
| `problem` | <code>"The API contract says failures are reported as `TaskStateError`, but `TaskStore._read()` lets `TaskDocument.parse()` raise the base `TaskDataError` directly; this is observable for malformed frontmatter/event sections and even the open-fence regression expects `TaskDataError` from `transition()`. A caller catching the documented exception will miss these fail-closed paths. Either normalize parser failures to `TaskStateError` at the store boundary or document `TaskDataError` as the common public base/error type."</code> |
| `verification` | <code>"只读源码/文档审查；未修改。"</code> |
| `decision` | <code>"按D-IMP-13原级延期，不随P1修复扩大变更。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"TaskStore._read converts parser TaskDataError to public TaskStateError."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "TaskStore._read converts parser TaskDataError to public TaskStateError.", "evidence": ["docs/prd/sbtd-workflow-v2-task-state-runtime.md", "sbtd-workflow-onboard/scripts/sbtd_task_state.py", "sbtd-workflow-onboard/scripts/sbtd_task_document.py", "tests/test_sbtd_task_state.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-89"></a>
### 89. P1-18-R1-ROUTE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-001"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:196-204"</code> |
| `title` | <code>"在返回推荐确认前锁存显式模式"</code> |
| `problem` | <code>"当已有任务记录为 `lite`、请求显式选择 `default` 且同时给出不同模式推荐时，首次调用在 203 行直接返回 `needs-mode-decision`，没有执行后面的 `_session_modes` 保存；用户随后以不重复 `explicit_mode` 的 `keep` 回应时，下一次调用会重新从磁盘取回 `lite` 并把它持久化，覆盖刚刚明确的 `default` 选择。`TaskRouter` 已承担跨调用会话选择（保存失败和重绑定路径也依赖它），因此应在任何待决定早退之前锁存显式模式/备注，并在后续推荐回应中继续以该会话模式为当前模式。"</code> |
| `verification` | <code>"真实4项红测后修复，accept/keep分支与partial创建变体、137项影响范围和真实缺YAML环境通过；独立只读复核关闭。"</code> |
| `decision` | <code>"P1已闭环，不把修复前全量重标为最终证据。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Session explicit/recommendation choice is stored before recommendation early return.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-90"></a>
### 90. P1-18-R1-ROUTE-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-002"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:141-150"</code> |
| `title` | <code>"在分支裁决前保留已接受或拒绝的推荐"</code> |
| `problem` | <code>"分支不匹配时这里在处理 `recommendation_response` 之前返回；若用户本次已经 `accept` 了新模式，`_session_modes` 不会记录该选择，明确 `rebind` 后的普通续作又采用磁盘旧模式；若用户 `keep`，拒绝原因同样丢失并会对相同风险再次提示。该路径只特判了 `explicit_mode`，但推荐回应也是已经明确的模式决定；应在仍保持零磁盘写入的前提下先把 accept/keep 的会话模式和结构化拒绝备注锁存，再返回 `needs-branch-choice`。"</code> |
| `verification` | <code>"真实4项红测后修复，accept/keep分支与partial创建变体、137项影响范围和真实缺YAML环境通过；独立只读复核关闭。"</code> |
| `decision` | <code>"P1已闭环，不把修复前全量重标为最终证据。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Recommendation accept/keep is processed before branch mismatch return while disk remains untouched.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-91"></a>
### 91. P1-18-R1-ROUTE-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-003"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:274-282"</code> |
| `title` | <code>"把新任务缺少 PyYAML 转成持久化失败结果"</code> |
| `problem` | <code>"确认创建新任务时，`route()` 调用 `TaskStore.create()`，但后者在校验 metadata 后直接 `import yaml`；如果解释器已有 jsonschema 但缺少 PyYAML（目录安装明确允许依赖尚未准备的状态），`ModuleNotFoundError` 不属于此处捕获的 `TaskDataError`，因此不会返回文档承诺的确定性 `persistence-failed`，而是让 host 调用崩溃。应让 `TaskStore.create()` 用共享依赖门或把该 ImportError 转为 `TaskStateError`，使路由层能保持失败契约。"</code> |
| `verification` | <code>"真实4项红测后修复，accept/keep分支与partial创建变体、137项影响范围和真实缺YAML环境通过；独立只读复核关闭。"</code> |
| `decision` | <code>"P1已闭环，不把修复前全量重标为最终证据。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "create uses require_dependency and route catches TaskDataError, yielding persistence-failed for missing PyYAML.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-92"></a>
### 92. P1-18-R1-ROUTE-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-004"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:228-235"</code> |
| `title` | <code>"为新任务保存失败保留会话模式"</code> |
| `problem` | <code>"`save_choice` 只在 `task is not None` 时写入 `_session_modes`，而 `intent=\"new\"` 也从不读取该映射；因此新任务以显式 `strict` 创建失败后虽然返回 `persistence-failed`，同一 router 的下一次不带重复 `explicit_mode` 的重试会退回 `default`。若失败发生在 task.md 已写、active 指针未写之间，重试还会用 default 路径/内容与已落下的 strict 记录冲突。文档对“保存失败保持会话内选择”的承诺没有排除新任务，应为尚未持久化的 task ID 保存并恢复无磁盘 stamp 的会话选择，直到成功写入或被真正的新持久记录取代。"</code> |
| `verification` | <code>"真实4项红测后修复，accept/keep分支与partial创建变体、137项影响范围和真实缺YAML环境通过；独立只读复核关闭。"</code> |
| `decision` | <code>"P1已闭环，不把修复前全量重标为最终证据。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "New request task_id keys are stored/read for retry after persistence failure.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-93"></a>
### 93. P1-18-R1-ROUTE-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-005"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/REFERENCE.md:369-373"</code> |
| `title` | <code>"按实际确认语义说明 `rebind`"</code> |
| `problem` | <code>"新增的 `rebind(..., confirmed=False)` 条目仍被下一句“Unconfirmed calls only report the planned result”涵盖，但实现一进入方法就调用 `_authorize(False)` 并抛出 `TaskStateError`，测试也明确断言该异常；它没有可返回的计划结果。安装副本的 host 调用方据此文档编排会把正常的待确认阶段当成异常契约漂移。应将说明拆开：`promote`/`archive` 可返回预览状态，而 `rebind` 等确认型写操作在未确认时明确失败且零写入。"</code> |
| `verification` | <code>"独立只读审查；未专项修复，原级保留。"</code> |
| `decision` | <code>"按D-IMP-13延期；D-IMP-14累计十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"明确 rebind 缺确认时异常且零写入，只有 promote/archive 返回预览。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "明确 rebind 缺确认时异常且零写入，只有 promote/archive 返回预览。", "evidence": ["sbtd-workflow-onboard/REFERENCE.md", "sbtd-workflow-onboard/templates/skills/sbtd-task/references/state.md", "sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-94"></a>
### 94. P1-18-R1-ROUTE-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-006"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:251-259"</code> |
| `title` | <code>"先选择新任务 ID 再请求持久化确认"</code> |
| `problem` | <code>"`RouteRequest.task_id` 是可选值且本方法已有缺失 ID 的 `needs-task-choice` 分支，但未确认的新任务会先在这里返回 `needs-persistence-confirmation`；用户确认后第二次调用才在 267 行得知还需选择 ID，形成无法执行的确认顺序。应在请求确认前检查新任务的逻辑 ID，使 `needs-task-choice` 始终先于对尚不存在目标的持久化确认。"</code> |
| `verification` | <code>"独立只读审查；未专项修复，原级保留。"</code> |
| `decision` | <code>"按D-IMP-13延期；D-IMP-14累计十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"可写 new 请求缺 task_id 时先返回 needs-task-choice，不先请求持久化确认。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "可写 new 请求缺 task_id 时先返回 needs-task-choice，不先请求持久化确认。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-95"></a>
### 95. P1-18-R1-ROUTE-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-007"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:51-59"</code> |
| `title` | <code>"避免把合法的自由文本 `mode_note` 当成损坏记录"</code> |
| `problem` | <code>"`mode_note` 的公开 schema 只要求非空字符串，但 `_note_parts` 把任何以 `SBTD mode decisions: ` 开头的文本都占用为私有 JSON 格式；因此一个合法的既有说明（例如以该短语开头的普通句子）会在所有续作路由中被判为 malformed 并返回 `blocked`。应让结构化格式具有无歧义的封装/版本判据，或把不满足完整封装的前缀碰撞按原始 note 保全，而不是让新增路由拒绝 schema 合法的历史任务。"</code> |
| `verification` | <code>"独立只读审查；未专项修复，原级保留。"</code> |
| `decision` | <code>"按D-IMP-13延期；D-IMP-14累计十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"带保留前缀但不符合结构化决策的文字保留为合法自由文本 note。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "带保留前缀但不符合结构化决策的文字保留为合法自由文本 note。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-96"></a>
### 96. P1-18-R1-ROUTE-008

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-008"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:208-216"</code> |
| `title` | <code>"持久化接受推荐时的新理由"</code> |
| `problem` | <code>"`accept` 只替换 `mode` 并置 `save_choice`，后续 `note` 仍取旧任务的 `prior_note`；例如原 `lite` 的说明为“小范围改动”，用户因“破坏性迁移”接受 `strict` 后，task.md 会记录 `workflow_mode: strict`，却继续保留旧 lite 理由且完全丢失本次 recommendation 的 reason/risk_id。`mode_note` 是跨会话解释选择的持久字段，应在接受推荐时写入本次模式、实质原因和风险标识，同时保全仍适用的历史拒绝记录。"</code> |
| `verification` | <code>"独立只读审查；未专项修复，原级保留。"</code> |
| `decision` | <code>"按D-IMP-13延期；D-IMP-14累计十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"接受建议保存理由和风险标识，并移除同一风险已撤销的拒绝记录。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "接受建议保存理由和风险标识，并移除同一风险已撤销的拒绝记录。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-97"></a>
### 97. P1-18-R1-ROUTE-009

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-ROUTE-009"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118RoutingSurfaceReview"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_task_routing.py:251-259"</code> |
| `title` | <code>"不要为已持久化的相同模式再次请求确认"</code> |
| `problem` | <code>"`save_choice` 只依据是否传入 `explicit_mode`，所以即使 task.md 已是相同 mode、`mode_source=user` 且 `mode_note` 也相同，未带 `confirmed` 的续作仍返回 `needs-persistence-confirmation`。REFERENCE 只承诺“changed choice”需要确认；当前行为会让 host 在用户重复说明现有模式时制造无实际写入的确认。应先与选中任务的持久三元组比较，完全相同时直接返回 `ready/persisted=True`。"</code> |
| `verification` | <code>"独立只读审查；未专项修复，原级保留。"</code> |
| `decision` | <code>"按D-IMP-13延期；D-IMP-14累计十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"最终 mode/source/note 与磁盘一致时，包括显式选择和重放 keep，均不重复确认或写入。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "最终 mode/source/note 与磁盘一致时，包括显式选择和重放 keep，均不重复确认或写入。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-98"></a>
### 98. P1-18-R1-HANDOFF-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-HANDOFF-001"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118HandoffSecurityReview"</code> |
| `source_rule_id` | <code>"P118-HANDOFF-HISTORY-DEDUP"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"HandoffStore.save historical equality versus HandoffStore.reminders latest selection"</code> |
| `title` | <code>"[P2] 历史任一相同快照会抑制新的上下文回退，提醒仍返回较新的旧状态"</code> |
| `problem` | <code>"触发条件：同一未完成任务在同根/同 branch/同 HEAD、mode、status、policy 下，第一天保存 content A，第二天保存不同的 content B，随后当前实际上下文恢复为 A。save 遍历所有历史，遇第一天 A 即返回 unchanged/persisted=True，不更新第二天文件或生成新的当前快照；reminders 按 created_at 仍选 B，续作因此得到已经被撤回的 remaining/next_action/do_not_repeat。这不是日期变化本身，而是相对最新快照确有信息变化；单 writer 即成立，不需要并发或恶意文件。P2：误导恢复摘要，但不更改权威任务状态或执行模式。"</code> |
| `recommendation` | <code>"只将当前候选与该任务的最新有效快照做 unchanged 比较；最新快照为 B 时 A 应按已有同日更新/跨日新文件规则保存。保持连续 A 跨日零重写，补 A→B→A 的回归用例。"</code> |
| `verification` | <code>"独立源码推导，未运行专项复现或修复；不冒充已发生数据泄漏。"</code> |
| `decision` | <code>"P2原级延期，等待累计十项后的用户评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"只与最新快照去重，A→B→A 会保存当前 A，提醒不返回过期 B。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "只与最新快照去重，A→B→A 会保存当前 A，提醒不返回过期 B。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-99"></a>
### 99. P1-18-R1-HANDOFF-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-HANDOFF-002"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118HandoffSecurityReview"</code> |
| `source_rule_id` | <code>"P118-HANDOFF-NONGIT-RULE-ORDER"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"HandoffStore._protected first-positive rule selection"</code> |
| `title` | <code>"[P2] 非 Git 保护检查固定使用第一条正向规则，窄修复后仍永久判为未保护"</code> |
| `problem` | <code>"触发条件：已证明非 Git 的 root，.gitignore 为 `/docs/handoffs/\\n!/docs/handoffs/\\n/.sbtd/\\n`，且 handoff 目录尚空。protect(confirmed=True) 正确在最后 `/.sbtd/` 前插入新的 `/docs/handoffs/`，但 _protected 仍从最早正向规则立即返回并看到旧否定规则，导致写入后抛错；后续 save 仍返回 unprotected，再调用 protect 又追加重复规则。单 writer、无恶意竞争即可使获授权保护无法完成。P2 可用性问题，不会把未保护数据写出。"</code> |
| `recommendation` | <code>"保留保守的非 Git 判定，但应从最后一条准确的根锚定正向规则评估其后否定，确保 protect 插入的最终规则可以建立保护；补正向→否定→protect 的往返用例。"</code> |
| `verification` | <code>"独立源码推导，未运行专项复现或修复；不冒充已发生数据泄漏。"</code> |
| `decision` | <code>"P2原级延期，等待累计十项后的用户评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"非 Git 检查按最后相关根规则判定保护，窄规则修复不被历史否定永久覆盖。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "非 Git 检查按最后相关根规则判定保护，窄规则修复不被历史否定永久覆盖。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-100"></a>
### 100. P1-18-R1-HANDOFF-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-HANDOFF-003"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118HandoffSecurityReview"</code> |
| `source_rule_id` | <code>"P118-HANDOFF-NONGIT-PATTERN-WHITESPACE"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"HandoffStore._protected non-Git lexical normalization"</code> |
| `title` | <code>"[P2] 非 Git 规则预处理删除有意义的前导空格，误称 handoff 已受保护"</code> |
| `problem` | <code>"触发条件：非 Git root 的 .gitignore 含 ` /docs/handoffs/`（开头一个空格），最后另有有效的 `/.sbtd/`。TaskStore 可正常创建任务；HandoffStore._protected 对行 strip() 后把该模式当成准确的 `/docs/handoffs/`，protect 返回 False，save 可返回 saved，但 Git 模式中的前导空格并不会被忽略，该规则实际不保护 docs/handoffs。当前可观察问题是错误的保护判定和跳过窄授权修复；若以后正常纳入 Git，先前摘要可能被 add。没有当前仓库已泄露的证据，因此维持 P2，不升级为 P1。"</code> |
| `recommendation` | <code>"非 Git 路径仅认可原始行中准确的根锚定模式，不删除有意义的前导空白；不能证明的模式一律走 unprotected 和已有独立 protect 授权。补带前导空格规则不会放行的用例。"</code> |
| `verification` | <code>"独立源码推导，未运行专项复现或修复；不冒充已发生数据泄漏。"</code> |
| `decision` | <code>"P2原级延期，等待累计十项后的用户评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"保留 ignore 前导空格语义，不把无效根规则冒充保护。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "保留 ignore 前导空格语义，不把无效根规则冒充保护。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-101"></a>
### 101. P1-18-R1-HANDOFF-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-R1-HANDOFF-004"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P118HandoffSecurityReview"</code> |
| `source_rule_id` | <code>"P118-HANDOFF-FULLHEX-NAME-LIMIT"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"HandoffStore._task_key flattened basename length"</code> |
| `title` | <code>"[P2] 合法任务 ID 的完整 hex 可超过单文件名限制，导致交接无法保存"</code> |
| `problem` | <code>"触发条件：已存在且受保护的 docs/handoffs 下，对合法的 121 个 ASCII 字符任务 ID 调用 save。TaskStore 和 logicalId schema 接受该 ID，任务自身仅占一个 121 字符目录；但 handoff 文件名长度变为 10 日期 + 1 连字符 + 242 hex + 3 扩展名 = 256，超过常见 APFS/POSIX 文件系统的 255 字符/字节分量限制。多段完整 ID 或 41 个三字节汉字也会达到该边界。结果是在路径检查/写入时抛 TaskStateError，合法任务不能持久化交接；不是碰撞或数据覆盖，也不涉及 Windows，因此定为 P2 功能边界问题。"</code> |
| `recommendation` | <code>"为完整可逆 hex 文件键明确长度策略并前置检查，不能仅宣称 OS-safe。若保持当前平铺路径契约，应在公开接口准确报告这一保存限制；如要求覆盖所有合法逻辑 ID，后续需单独批准可分段保存完整编码的路径契约，勿改成截断/有损键。"</code> |
| `verification` | <code>"独立源码推导，未运行专项复现或修复；不冒充已发生数据泄漏。"</code> |
| `decision` | <code>"P2原级延期，等待累计十项后的用户评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"新文件名使用完整任务 ID 的定长 SHA-256；读取保留已存 hex 文件的身份核验，不自动改名。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "新文件名使用完整任务 ID 的定长 SHA-256；读取保留已存 hex 文件的身份核验，不自动改名。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-102"></a>
### 102. P1-18-A1-P1-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-18-A1-P1-001"</code> |
| `task` | <code>"P1-18"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>0</code> |
| `source` | <code>"advisor and Main inspection"</code> |
| `original_severity` | <code>"blocker"</code> |
| `source_commit` | <code>"255c5ce7535c55339726b8b52b5119bcfbea2ace"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_task_routing.py:candidate and branch decision paths"</code> |
| `title` | <code>"开发中错位编辑导致候选与分支逻辑不可达"</code> |
| `problem` | <code>"一次过期行号编辑将候选处理插到except返回后，并替换掉branch比较；advisor与实际代码读取均指出不可达逻辑。"</code> |
| `verification` | <code>"立即按完整范围恢复控制流；候选先于模式、多分支选择、只读/明确重绑定的公开行为回归通过，独立完整review及修复复核无存续问题。"</code> |
| `decision` | <code>"已修复，不隐藏工具错位或把语法通过当运行契约通过。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Candidate resolution precedes mode; branch/recommendation/read-only/confirmation control flow is reachable and ordered.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_task_routing.py", "sbtd-workflow-onboard/scripts/sbtd_handoff.py", "tests/test_sbtd_task_routing.py", "tests/test_sbtd_handoff.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-103"></a>
### 103. P1-19-R1-CLI-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R1-CLI-001"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P119CliSurfaceReview"</code> |
| `source_commit` | <code>"45e9f363e6ef2a8716957f457e87e21ab8e210dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:6669-6681"</code> |
| `title` | <code>"Report completed scaffold writes in partial identity JSON"</code> |
| `problem` | <code>"When every scaffold operation succeeds but `ensure_developer_identities()` then returns `failed`, `conflict`, or `needs-protection` (for example after a post-preflight filesystem race), this branch emits only the original operation plan plus backups. `operation_results` and a post-write `sbtdProjectSetup` are omitted, so the single JSON document cannot tell an automation which AGENTS, Skill, or `.gitignore` writes already completed even though stderr says those writes are “kept and reported.” Add the completed operation results and post-write project state to `plan_payload` before this early return so the partial nonzero result is machine-auditable."</code> |
| `verification` | <code>"3项真实文件/I/O红测后修复，129项影响范围通过；独立只读复核确认无剩余P0/P1。"</code> |
| `decision` | <code>"已关闭P1；后续精确提交验证不使用旧dirty报告代替。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Partial JSON preserves operation_results and post-write project state after identity failure.", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-104"></a>
### 104. P1-19-R1-CLI-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R1-CLI-002"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P119CliSurfaceReview"</code> |
| `source_commit` | <code>"45e9f363e6ef2a8716957f457e87e21ab8e210dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:5765-5770"</code> |
| `title` | <code>"Convert developer-store construction failures into JSON results"</code> |
| `problem` | <code>"`resolve_project_roots()` checks each directory before this code constructs a `DeveloperStore`, but `TaskStore.__init__` resolves the root again with `strict=True` and raises `TaskStateError` if the directory disappears or becomes inaccessible in between. Neither this preflight comprehension nor the post-scaffold loop catches that exception, so `check`/`plan` can terminate with a traceback and, more critically, a write mode can do all scaffold writes and then terminate without its promised single partial JSON document. Catch construction/call failures per project, return a `blocked` entry during preflight and a `failed` entry during ensure, and preserve already completed entries."</code> |
| `verification` | <code>"3项真实文件/I/O红测后修复，129项影响范围通过；独立只读复核确认无剩余P0/P1。"</code> |
| `decision` | <code>"已关闭P1；后续精确提交验证不使用旧dirty报告代替。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "DeveloperStore construction/ensure failures are per-project JSON blocked/failed entries, preserving completed entries.", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-105"></a>
### 105. P1-19-R1-CLI-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R1-CLI-003"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P119CliSurfaceReview"</code> |
| `source_commit` | <code>"45e9f363e6ef2a8716957f457e87e21ab8e210dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:6663-6667"</code> |
| `title` | <code>"Print the final developer result for text-mode writes"</code> |
| `problem` | <code>"A successful non-JSON `init`, `reset`, or `init-projects --developer ... --yes` prints `print_developer_plan()` only before mutations, so the user sees `status: planned`; after `ensure_developer_identities()` changes that status to `created` or `unchanged`, the updated plan is never rendered. The command can therefore finish with “Verification passed” while its only identity report still says the write is merely planned. Print the updated developer plan after ensure (or label the first rendering strictly as preflight) in text mode."</code> |
| `verification` | <code>"独立源码审查；未修复。"</code> |
| `decision` | <code>"按D-IMP-13原级延期，累计十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"文本写入流程输出写后 developerPlan，不仅打印 preflight planned。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "文本写入流程输出写后 developerPlan，不仅打印 preflight planned。", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-106"></a>
### 106. P1-19-R1-IDENTITY-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R1-IDENTITY-001"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P119IdentitySecurityReview"</code> |
| `source_rule_id` | <code>"P119-IDENTITY-NONGIT-PATTERN-WHITESPACE"</code> |
| `source_commit` | <code>"45e9f363e6ef2a8716957f457e87e21ab8e210dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore._local_protected: non-Git strip()"</code> |
| `title` | <code>"[P2] 非 Git 保护判断误认带前导空格的无效根规则"</code> |
| `problem` | <code>"[INFERENCE] 已确认非 Git 的项目，身份缺失，.gitignore 最后一条为 ` /.sbtd/`（开头有空格）：TaskStore._local_protected 对原始规则 strip() 后误判已保护，DeveloperStore.plan 返回 needs_protection=False，ensure('dev01', confirmed=True, protect=False) 因而可建立身份。Git 模式中的前导空格有意义，该规则不保护根 .sbtd；以后纳入 Git 时身份可能被 add。当前问题是错误保护证明及跳过所需窄保护授权，不声称已发生泄漏。这是新 API 复用的既有 TaskStore 弱点，与 P1-18-R1-HANDOFF-003 同类但不在同一实现；保持 P2，不扩修旧 handoff。"</code> |
| `recommendation` | <code>"非 Git 保守判断仅认可未删除有意义前导空白的准确根规则；无法证明则返回 needs_protection=True，由独立 protect 授权追加真实规则。补前导空格规则不能放行身份创建的行为用例；原级延期。"</code> |
| `verification` | <code>"独立静态路径推导，未运行专项复现或修复；不把潜在未来公开写成已发生泄漏。"</code> |
| `decision` | <code>"P2原级延期，不扩修旧TaskStore/handoff路径；D-IMP-14统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Non-Git ignore protection no longer strips leading/trailing whitespace from rules."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Non-Git ignore protection no longer strips leading/trailing whitespace from rules.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-107"></a>
### 107. P1-19-R1-IDENTITY-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R1-IDENTITY-002"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P119IdentitySecurityReview"</code> |
| `source_rule_id` | <code>"P119-IDENTITY-PARTIAL-COMPLETION-LOSS"</code> |
| `source_commit` | <code>"45e9f363e6ef2a8716957f457e87e21ab8e210dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"DeveloperStore.ensure: exception completion propagation"</code> |
| `title` | <code>"[P2] 保护写入后验证失败会漏报已修改的 .gitignore"</code> |
| `problem` | <code>"[INFERENCE] ensure(name, confirmed=True, protect=True) 需要新增保护，TaskStore 已发布 .gitignore，但后置 check-ignore 验证发生 I/O/进程启动失败或返回未保护：helper 尚未返回，ensure 的 completed.append('.gitignore') 不执行；外层捕获也不保留 TaskStateError.completed_steps，最终 failed/completed_steps=()，而磁盘文件已修改。无需并发写者即可触发，违反实际部分成功报告契约；仍失败退出、不覆盖身份，定 P2。"</code> |
| `recommendation` | <code>"在 helper 发布边界记录实际完成步骤，确保后置验证抛错也携带这些步骤；ensure 合并/去重异常 completed_steps 与本地步骤，保持失败状态且不回滚其他内容。补保护写成功而验证失败的行为用例；原级延期。"</code> |
| `verification` | <code>"独立静态路径推导，未运行专项复现或修复；不把潜在未来公开写成已发生泄漏。"</code> |
| `decision` | <code>"P2原级延期，不扩修旧TaskStore/handoff路径；D-IMP-14统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"保护实际写入后验证异常也携带 .gitignore completed_steps，IdentityResult 不丢弃部分完成事实。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "保护实际写入后验证异常也携带 .gitignore completed_steps，IdentityResult 不丢弃部分完成事实。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-108"></a>
### 108. P1-19-R1-IDENTITY-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R1-IDENTITY-003"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>1</code> |
| `source` | <code>"P119IdentitySecurityReview"</code> |
| `source_rule_id` | <code>"P119-IDENTITY-ROOT-WHITESPACE"</code> |
| `source_commit` | <code>"45e9f363e6ef2a8716957f457e87e21ab8e210dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"TaskStore.current_binding: top.stdout.strip()"</code> |
| `title` | <code>"[P2] 合法尾空白 Git 根在 resolve 后被 plan 错误拒绝"</code> |
| `problem` | <code>"[INFERENCE] 公共 DeveloperStore API 的 root 为合法 Git checkout '/tmp/project '（目录名末尾空格；末尾 LF 同理），身份链缺失：_topology 仅 removesuffix('\\n')，resolve 可正确返回 needs-name；plan 随后调用 current_binding，其 top.stdout.strip() 删除目录名自身尾空白，误报不是实际 Git 根，返回 blocked，无法首次建立身份。属于既有 shared helper 被新身份流程继承的可用性缺陷，不绕过安全门，定 P2。"</code> |
| `recommendation` | <code>"Git 路径输出只删除协议附加的一次终止换行，保留目录名原始空白，与 _topology 一致；补 public DeveloperStore 在尾空白根的 resolve→plan→ensure 场景。原级延期。"</code> |
| `verification` | <code>"独立静态路径推导，未运行专项复现或修复；不把潜在未来公开写成已发生泄漏。"</code> |
| `decision` | <code>"P2原级延期，不扩修旧TaskStore/handoff路径；D-IMP-14统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Git top-level parsing removes only Git's terminal newline, preserving trailing whitespace in valid root paths."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Git top-level parsing removes only Git's terminal newline, preserving trailing whitespace in valid root paths.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-109"></a>
### 109. P1-19-R2-DOCS-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R2-DOCS-001"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P119DocsFinalReview"</code> |
| `source_commit` | <code>"cb0dcf5221f225e80115c378a3fea1721273300e"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"README.md:15;README.html:412"</code> |
| `title` | <code>"Document post-write identity exit codes by status"</code> |
| `problem` | <code>"The new CLI contract says every post-write identity failure exits 5, but `developer_plan_exit_code()` returns 5 only for aggregate `failed`; a post-preflight race that produces `conflict`, `blocked`, `needs-confirmation`, or `needs-protection` exits 2. For example, if another writer creates a different identity after preflight, scaffold results are preserved but the process returns 2, so automation following this documentation will misclassify the documented result. State exit 5 only for `failed` and exit 2 for the other blocking statuses."</code> |
| `verification` | <code>"独立源码/文档对照；未修复退出码文案。"</code> |
| `decision` | <code>"按D-IMP-13保留P2延期，十项确认门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"README 两份与 REFERENCE 按实际状态区分 failed=5、conflict/blocked/needs-*=2，均保留部分结果。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "README 两份与 REFERENCE 按实际状态区分 failed=5、conflict/blocked/needs-*=2，均保留部分结果。", "evidence": ["README.md", "README.html", "sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-110"></a>
### 110. P1-19-R2-EVIDENCE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-19-R2-EVIDENCE-001"</code> |
| `task` | <code>"P1-19"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"dismissed"</code> |
| `review_round` | <code>2</code> |
| `source` | <code>"P119DocsFinalReview/P119EvidenceFinalReview"</code> |
| `source_commit` | <code>"cb0dcf5221f225e80115c378a3fea1721273300e"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md:1171"</code> |
| `title` | <code>"Checking行仍记录提交前dirty证据"</code> |
| `problem` | <code>"复核初认为精确报告已有而当前行仍待精确提交是不一致。"</code> |
| `decision` | <code>"澄清用户两PR约定后reviewer撤回：这是05:46 checking快照，最终exact/done/真实时间/merge由实现合入与清理后的独立状态PR更新；不是意外遗漏。不改写历史事件、不提前done。"</code> |
| `resolution` | <code>"Finding decision explicitly withdraws it: referenced line was intentional pre-merge checking evidence under the two-PR convention, not a missing final update."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "dismissed", "disposition": "dismissed", "decision": "Finding decision explicitly withdraws it: referenced line was intentional pre-merge checking evidence under the two-PR convention, not a missing final update.", "evidence": ["docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md", "sbtd-workflow-onboard/scripts/sbtd_identity.py", "tests/test_sbtd_identity.py", "tests/test_onboard_developer.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-111"></a>
### 111. P1-12-R1-FS-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-FS-003"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112FilesystemReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `source_rule_id` | <code>"P112-FS-03"</code> |
| `location` | <code>[{"path": "sbtd-workflow-onboard/scripts/sbtd_migration_files.py", "start_line": 179, "end_line": 186, "role": "Recursive snapshot accepts reparse directories"}, {"path": "sbtd-workflow-onboard/scripts/sbtd_migration_files.py", "start_line": 521, "end_line": 529, "role": "Copy enumeration follows unchecked directory entries"}, {"path": "sbtd-workflow-onboard/scripts/sbtd_project.py", "start_line": 248, "end_line": 258, "role": "Reused reader checks the final file, not junction ancestors"}]</code> |
| `title` | <code>"P2: Recursive scans follow Windows directory junctions"</code> |
| `problem` | <code>"The root path is screened for FILE_ATTRIBUTE_REPARSE_POINT, but recursive directory entries are classified only by st_mode. An NTFS directory junction is a directory with the reparse attribute, so both snapshot traversal and copy enumeration descend through it. A directory reference can therefore include and copy files outside its declared physical tree instead of rejecting the unsupported link."</code> |
| `decision` | <code>"依D-IMP-13保留原P2，不并入本轮P1修正；Windows实际行为尚未作为通过证据。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"迁移扫描/复制及共用 regular-file reader 均在读取前拒绝 Windows reparse/junction；原生 Windows junction 用例已接入 CI，POSIX 内部安全链接语义保留。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "迁移扫描/复制及共用 regular-file reader 均在读取前拒绝 Windows reparse/junction；原生 Windows junction 用例已接入 CI，POSIX 内部安全链接语义保留。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_files.py", "sbtd-workflow-onboard/scripts/sbtd_project.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-112"></a>
### 112. P1-12-R1-LEGACY-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-LEGACY-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LegacyReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py:504-506"</code> |
| `title` | <code>"Reject non-integer sidecar schema versions"</code> |
| `problem` | <code>"`_decode_legacy` parses `1.0` and `1e0` as `Decimal`, and those values compare equal to integer `1`, so this check accepts a `legacy-task.json` whose `schema_version` is not the required integer type. Such a malformed shared sidecar is then treated as schema v1; require an exact non-boolean `int` equal to 1."</code> |
| `decision` | <code>"依D-IMP-13原级延期，累计十项门统一评估；未宣称已修。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"schema_version now requires exact int 1."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "schema_version now requires exact int 1.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-113"></a>
### 113. P1-12-R1-LEGACY-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-LEGACY-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LegacyReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py:628-632"</code> |
| `title` | <code>"Keep unknown legacy keys out of current frontmatter"</code> |
| `problem` | <code>"This blacklist catches only known legacy spellings. Because current task frontmatter permits extensions, an unknown source key such as `custom_unknown` can be copied into the migrated frontmatter and still pass, turning historical legacy data into live task state even though the contract confines all known and unknown old fields to `legacy-task.json`. Reject source-key/frontmatter-extension overlap outside the explicitly mapped current fields."</code> |
| `decision` | <code>"依D-IMP-13原级延期，累计十项门统一评估；未宣称已修。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"拒绝旧未知字段进入当前扩展字段；由 schema/映射独立确定的固定字段允许同名但不继承旧值，mode_note 使用已公开规范值。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "拒绝旧未知字段进入当前扩展字段；由 schema/映射独立确定的固定字段允许同名但不继承旧值，mode_note 使用已公开规范值。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-114"></a>
### 114. P1-12-R1-LEGACY-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-LEGACY-003"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LegacyReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py:754-758"</code> |
| `title` | <code>"Treat the archive root as an archived position"</code> |
| `problem` | <code>"The archive test excludes the task directory itself via `parts[:-2]`, so `.trellis/tasks/archive/task.json` with an unfinished status is accepted as a normal task. The planner classifies that reserved archive-root path as a task folder, making this reachable and silently migrating structurally ambiguous archived data instead of blocking it; include the immediate parent in archive detection or validate the pinned active/archive layouts explicitly."</code> |
| `decision` | <code>"依D-IMP-13原级延期，累计十项门统一评估；未宣称已修。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Archive root is now an archived position."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Archive root is now an archived position.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-115"></a>
### 115. P1-12-R1-LEGACY-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-LEGACY-004"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LegacyReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py:703-712"</code> |
| `title` | <code>"Bind completion evidence to the legacy source"</code> |
| `problem` | <code>"The completion check validates only `from`, `to`, and `at`, so any nonempty `reason` and `evidence` accepted by the generic task schema can claim facts absent from the old record while this projection still passes. The migration contract permits `unknown → done` only as a sourced historical completion record; require the canonical legacy completion reason/evidence (or otherwise bind those fields to the actual source fact)."</code> |
| `decision` | <code>"依D-IMP-13原级延期，累计十项门统一评估；未宣称已修。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"历史完成事件绑定已验证源事实，使用规范 reason/evidence；任意伪造事件文案被拒绝，格式已公开。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "历史完成事件绑定已验证源事实，使用规范 reason/evidence；任意伪造事件文案被拒绝，格式已公开。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-116"></a>
### 116. P1-12-R1-LEGACY-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-LEGACY-005"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LegacyReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py:674-683"</code> |
| `title` | <code>"Require provenance when migrated timestamps become null"</code> |
| `problem` | <code>"Date-only or absent legacy times map to `null`, and these checks verify only that the frontmatter also contains `null`; they never verify the task body records why the historical time is unknown. A candidate containing only frontmatter and a heading therefore passes despite the current task-data contract requiring the source to be recorded in the body, leaving readers without the mandated provenance, especially when the sidecar is root-private. Require a canonical body provenance note for each unprovable migrated timestamp."</code> |
| `decision` | <code>"依D-IMP-13原级延期，累计十项门统一评估；未宣称已修。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"每个 null 时间用唯一顶层 JSON provenance fence 记录来源；严格解析，不用关键词猜测，兼容脱敏/私有原件来源说明。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "每个 null 时间用唯一顶层 JSON provenance fence 记录来源；严格解析，不用关键词猜测，兼容脱敏/私有原件来源说明。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-117"></a>
### 117. P1-12-R1-PLAN-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-004"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:296-305"</code> |
| `title` | <code>"Validate every migrated local link before publication"</code> |
| `problem` | <code>"The shared-text gate only rejects the literal retired layout and obvious private values; it never parses or resolves Markdown links. A task, attachment, spec, or lesson candidate can therefore contain a missing or escaping relative link and still be copied, revalidated, and eventually cleaned up. Resolve every local candidate link against the approved target closure and reject missing, escaping, or retired targets while leaving external URLs untouched."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"7be29e2e418771c2ae0bdcb2ce6e54bd2003aabe"</code> |
| `resolution` | <code>"markdown-it parses local links; escaping, missing, file-URL, or unapproved targets block while approved local and external URLs pass. Follow-up: reject every decoded ASCII drive prefix before the external-scheme exemption, including drive-relative links and images; preserve existing protocol safety and exit-code policies."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T16:32:48.578047+08:00", "source_commit": "7be29e2e418771c2ae0bdcb2ce6e54bd2003aabe", "previous_status": "deferred", "disposition": "fixed-now", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "tests/test_sbtd_migration_plan.py", "sbtd-workflow-onboard/REFERENCE.md"], "verification": "Drive-relative link/image subcases failed before the fix and pass after it. The existing migration-plan suite passes all 42 tests; 15 native CLI plan smoke cases pass with unchanged fixture trees. Rejections retain target-conflict / exit 2. Local evidence is dirty developer-local, not proof of the future PR head; CI remains separately authoritative."}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}, {"at": "2026-09-21T16:19:20.662276+08:00", "from": "fixed", "to": "deferred", "reason": "Advisor复核发现盘符相对链接 C:secret.md 绕过本地链接校验；用户授权独立 fix PR 补修，不改协议允许范围或退出码分类。", "evidence": "14c256c07f15e3e22f5c49b1e3fd9bf93ef91240"}, {"at": "2026-09-21T16:32:48.578047+08:00", "from": "deferred", "to": "fixed", "reason": "Independent drive-relative follow-up repaired and verified; broader URI and exit-code policy changes remain out of scope.", "evidence": "7be29e2e418771c2ae0bdcb2ce6e54bd2003aabe"}]</code> |
| `follow_up_reviews` | <code>[{"reviewed_at": "2026-09-21T16:19:20.662276+08:00", "source_commit": "14c256c07f15e3e22f5c49b1e3fd9bf93ef91240", "status": "fixed", "boundary": "Windows drive-relative Markdown destinations, including percent-encoded forms", "preserved_policy": "Keep existing markdown-it safe-link behavior; no HTTPS-only/all-data-URI ban and no exit-code taxonomy change.", "fixed_at": "2026-09-21T16:32:48.578047+08:00", "verified_fixed_by": "7be29e2e418771c2ae0bdcb2ce6e54bd2003aabe", "verification": {"migration_plan_tests": 42, "native_cli_plan_cases": 15, "protocol_compatibility": "HTTP, HTTPS, mailto and safe image data URI accepted; unsafe schemes, unapproved local paths and all drive prefixes rejected.", "evidence_source": "developer-local", "publication": "local-only"}}]</code> |
| `code_review_history` | <code>[{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "markdown-it parses local links; escaping, missing, file-URL, or unapproved targets block while approved local and external URLs pass.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}]</code> |

<a id="record-118"></a>
### 118. P1-12-R1-PLAN-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-005"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:478-487"</code> |
| `title` | <code>"Permit optional attachments to remain private-only"</code> |
| `problem` | <code>"All records in a task closure are forced to share one `share`/`redact` decision and every record must be required, so a valid shared task with an optional sensitive attachment marked `private-only` is always blocked. Keep the task document and sidecar mandatory, but count an approved optional private-only attachment as privately preserved coverage without creating a publication operation."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Explicit optional private-only task attachments count as private coverage but produce no publication operation."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Explicit optional private-only task attachments count as private coverage but produce no publication operation.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-119"></a>
### 119. P1-12-R1-PLAN-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-006"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1595-1602"</code> |
| `title` | <code>"Ignore unrelated directories in the global Skill root"</code> |
| `problem` | <code>"`consumers` is built from every top-level entry in the resolved global Skill directory, so any unrelated installed Skill causes `unknown-consumers` even though cleanup only targets the two pinned Trellis directories. This blocks otherwise safe migrations in ordinary multi-Skill installations. Inspect only the named legacy Skill targets for exact ownership and preserve every other directory without treating it as a migration consumer."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Only exact pinned Skill names are examined for retirement; unrelated global Skills are preserved."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Only exact pinned Skill names are examined for retirement; unrelated global Skills are preserved.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-120"></a>
### 120. P1-12-R1-PLAN-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-007"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1423-1431"</code> |
| `title` | <code>"Resolve current identity before parsing the legacy name"</code> |
| `problem` | <code>"The legacy `.developer` file is parsed before `DeveloperStore.resolve()`, so a malformed legacy name blocks even when a valid local identity or verified main-worktree identity must take priority. Resolve the current chain first and return for an authoritative valid identity where the PRD permits it; only parse the old name when deciding whether a new local identity can be created, while retaining the malformed old file in the private inventory."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Current DeveloperStore resolution now precedes reading old .developer; legacy bytes are parsed only when a current identity must be created."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Current DeveloperStore resolution now precedes reading old .developer; legacy bytes are parsed only when a current identity must be created.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-121"></a>
### 121. P1-12-R1-PLAN-008

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-008"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:435-441"</code> |
| `title` | <code>"Require a handoff for unfinished workspace context"</code> |
| `problem` | <code>"Every source outside tasks/spec/lessons is forced to `private-only`, which makes an approved handoff derived from `.trellis/workspace` or the current-task journal impossible. Such a project can proceed with only the raw private backup, disable the old runtime, and later remove the legacy tree without the required resumable handoff. Classify pinned workspace/current-task data, require a safe handoff projection for uniquely identified unfinished work, and block conflicting or multiple execution candidates."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "真实契约缺口：旧 workspace/.current-task 继续私有保全；未完成上下文的私有 handoff 批准、固定 session-JSON 解析与恢复证明尚需明确，不在本批引入新的共享发布协议。P2 准备/真实迁移前必须解决，不能以 plan 成功代替。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。", "required_before": "P2 真实迁移/清理；先明确私有 handoff 批准、固定 session-JSON 解析与恢复证据。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "解析固定 session JSON；未完成 journal/context 必须有完整来源绑定、批准且可读取的私有 HandoffStore 摘要；以真实 Git 验证计划 ignore 及嵌套规则", "verification": "journal 缺摘要红绿、计划零写入、apply/read/retry/recovery 原生 CLI、否定 ignore 回归", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-122"></a>
### 122. P1-12-R1-PLAN-009

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-009"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:461-466"</code> |
| `title` | <code>"Bind archived tasks to the required archive destination"</code> |
| `problem` | <code>"Task targets are checked only for being below `ai/tasks` and for ending in the logical ID, so a completed legacy archive can be published as an active task and an active task can be placed under an arbitrary archive path. Derive and enforce `archive/YYYY-QN/&lt;id&gt;` from a proven completion date, use `archive/undated/&lt;id&gt;` when completion timing is unknown, and reject archive placement for unfinished tasks."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Done tasks require ai/tasks/archive/YYYY-QN/&lt;id&gt; from a proven completion day/time, or archive/undated/&lt;id&gt;."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Done tasks require ai/tasks/archive/YYYY-QN/&lt;id&gt; from a proven completion day/time, or archive/undated/&lt;id&gt;.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-123"></a>
### 123. P1-12-R1-PLAN-010

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-010"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"dismissed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1710-1716"</code> |
| `title` | <code>"Assign nested selected projects to the most-specific root"</code> |
| `problem` | <code>"The planner rejects every ancestor/descendant pair before applying the P1-01 scope semantics, even when both are explicitly selected independent project roots. This safely blocks a supported nested-project batch rather than preventing cross-ownership. Allow canonical nested roots, assign sources and targets to the most-specific selected root, and retain the existing exclusive-root checks so the outer project cannot own inner-project operations."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `resolution` | <code>"P1-06 固定 Graft 的批次接线契约明确禁止嵌套或互相包含的已选仓根；通用 codec exclusive_roots 能力不代表端到端迁移已支持该范围。本批保留拒绝，不以旧建议扩大范围。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "superseded", "decision": "P1-06 固定 Graft 的批次接线契约明确禁止嵌套或互相包含的已选仓根；通用 codec exclusive_roots 能力不代表端到端迁移已支持该范围。本批保留拒绝，不以旧建议扩大范围。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "docs/prd/sbtd-workflow-v2-worktree-graft-isolation.md", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "dismissed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-124"></a>
### 124. P1-12-R1-PLAN-011

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-011"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1347-1354"</code> |
| `title` | <code>"Classify files by the deepest nested task folder"</code> |
| `problem` | <code>"When a legacy task directory contains a nested child task, each child file matches both the parent folder and the child folder, so `len(matches) != 1` rejects the entire inventory. The migration contract explicitly supports flat or nested parent/child layouts based on metadata. Attribute each file to its deepest enclosing task folder, then validate parent/child relationships from `task.json` rather than treating prefix overlap as loose data."</code> |
| `decision` | <code>"依D-IMP-13保留审查原级，不在P1修正中夹带修复；累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Nested attachments/inventory files attribute to the deepest enclosing task folder."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Nested attachments/inventory files attribute to the deepest enclosing task folder.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-125"></a>
### 125. P1-12-R1-RUN-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-RUN-003"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112RuntimeReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration.py:707-708"</code> |
| `title` | <code>"Preserve the checksum-failure exit code during apply"</code> |
| `problem` | <code>"On a retry, `_check_source_backups()` raises `ContractError(exit_code=3)` when a retained original is missing or has changed, but this broad handler erases that classification and the function later returns 5 for the resulting failed project. The CLI therefore reports a preservation/checksum failure as an actual filesystem-operation failure, breaking the documented exit-code contract used to choose remediation even though no resource write is attempted. Preserve the caught `ContractError.exit_code` (or let the pre-write preservation failure propagate) instead of always deriving 5 from project status."</code> |
| `decision` | <code>"依D-IMP-13保留原级，不夹带修复，累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"原件准备、逐资源 apply 与 cleanup 均把保全/checksum 错误保留为 exit 3；其他执行失败保持 exit 5，收据 schema 未改变。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "原件准备、逐资源 apply 与 cleanup 均把保全/checksum 错误保留为 exit 3；其他执行失败保持 exit 5，收据 schema 未改变。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-126"></a>
### 126. P1-12-R1-RUN-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-RUN-004"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112RuntimeReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard.py:6385-6388"</code> |
| `title` | <code>"Handle migration-module import failures in the live dispatch"</code> |
| `problem` | <code>"If an installed copy is incomplete enough that any eager migration-only import is unavailable (for example `sbtd_migration_files.py` is missing), the `from sbtd_migration import run_migration` failure occurs before `run_migration()`'s `ImportError` handler and escapes as a traceback. A `migration ... --json` call then violates the promised single sanitized JSON envelope, and `runtime_versions()` never gets a chance to report the incomplete runtime. Catch the lazy-import failure at this dispatch boundary and emit the same fixed blocked response used for unavailable declared dependencies."</code> |
| `decision` | <code>"依D-IMP-13保留原级，不夹带修复，累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"缺失迁移运行模块时 live dispatch 返回脱敏 blocked 单 JSON/2，不抛 traceback。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "缺失迁移运行模块时 live dispatch 返回脱敏 blocked 单 JSON/2，不抛 traceback。", "evidence": ["sbtd-workflow-onboard/scripts/onboard.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-127"></a>
### 127. P1-12-R1-VERIFY-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-005"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:231-237"</code> |
| `title` | <code>"Apply the genuine-mode gate only to the API smoke"</code> |
| `problem` | <code>"`_accept_report` rejects every entry whose mode is not one of the three smoke modes before checking `testType`. A schema-valid aggregate envelope containing the required passed `smoke-only` API report plus an auxiliary passed unit report with its normal `not-needed` mode is therefore rejected, although acceptance only requires at least one genuine API smoke. Keep checksum/status validation for every entry, but enforce `_GENUINE_MODES` only on the API report used to satisfy the smoke gate."</code> |
| `decision` | <code>"依D-IMP-13保留原级，不夹带修复，累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Genuine-mode restriction is now limited to API smoke; auxiliary passed reports remain integrity-checked.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-128"></a>
### 128. P1-12-R1-VERIFY-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-006"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:250-253"</code> |
| `title` | <code>"Checksum-bind each Markdown report summary"</code> |
| `problem` | <code>"The native evidence contract treats the same-stem Markdown summary as a primary artifact, but this code only opens `summaryMd` by path and never requires that path to appear in `report_refs` or match a recorded checksum. Replacing the summary after deployment evidence is sealed still passes verification, so the accepted evidence set is not the exact formal report pair; resolve the summary through the checksum-bound reference map just like the raw report and enforce the same-stem relationship."</code> |
| `decision` | <code>"依D-IMP-13保留原级，不夹带修复，累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Summary Markdown is now checksum-bound via report_refs and same-stem checked.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-129"></a>
### 129. P1-12-R1-VERIFY-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-007"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:128-132"</code> |
| `title` | <code>"Reject timezone-less report timestamps before comparison"</code> |
| `problem` | <code>"`_parse_timestamp` accepts a timestamp with no UTC offset and returns a naive `datetime`; `_attempt_time` then lets it escape. Comparing that value with an offset-aware deployment/report timestamp raises an uncaught `TypeError`, so malformed evidence makes `migration --phase verify --json` traceback instead of returning the required sanitized JSON rejection. Require an explicit timezone/UTC offset in `_attempt_time` before returning the parsed value."</code> |
| `decision` | <code>"依D-IMP-13保留原级，不夹带修复，累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Timezone-less timestamps are rejected before aware/naive comparison.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-130"></a>
### 130. P1-12-R1-VERIFY-008

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-008"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:200-211"</code> |
| `title` | <code>"Bind raw-run provenance to its evidence envelope"</code> |
| `problem` | <code>"The raw report is compared with the envelope only indirectly for ref/SHA, environment, mock strategy, and mode; its repository key, evidence source, trigger, source-revision/worktree state, and publication status are ignored. A developer-local dirty run can therefore be wrapped as a clean CI or knowledge-source envelope while both files remain checksum-valid, violating the native rule that evidence sources must not masquerade as one another. After validating the complete raw shape, require these provenance fields to agree with the enclosing evidence record."</code> |
| `decision` | <code>"依D-IMP-13保留原级，不夹带修复，累计十项门统一评估。"</code> |
| `verified_fixed_by` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `resolution` | <code>"已在证据边界修复分支按原 recommendation 修复；274 项受影响测试、952 项全量测试通过，独立 review 无 P0/P1。保留原始问题记录，不删除。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Raw smoke now validates complete execution fields/provenance before acceptance.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-131"></a>
### 131. P1-12-R1-PLAN-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:81-90"</code> |
| `title` | <code>"Accept the pinned v0.6.17 generated tree"</code> |
| `problem` | <code>"The legacy allowlist omits normal v0.6.17 entries such as `.gitignore`, `config.yaml`, `scripts/`, `agents/`, and `.current-task`. The same pinned format also records `.trellis/**` plus `.agents`, `.cursor`, `.opencode`, and `.pi` paths in `.template-hashes.json`, while `_parse_template_hashes` rejects `.trellis/**` and `_PLATFORM_PREFIX` cannot classify those hosts. A standard generated project therefore cannot produce a plan; classify the complete pinned tree into generated, runtime/user, and supported host assets instead of validating against the reduced fixture vocabulary."</code> |
| `resolution` | <code>"对应生成/共享字节/旧路由门已修正，独立审查确认关闭；8个原P2未改。"</code> |
| `evidence` | <code>["unit-report-migration-planner-review-red-p1-12-migration-runtime-2026_09_19-10_08_30", "unit-report-migration-planner-pin-isolated-green-p1-12-migration-runtime-2026_09_19-10_28_57"]</code> |
| `review_closure` | <code>{"reviewer": "P112PlannerReview", "at": "2026-09-19T10:32:18.250432+08:00", "result": "All three assigned P1 findings closed; shared-config pin gate also closed through plan and semantic revalidation; no new P0/P1; eight P2 deferred unchanged; no review validation commands."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Pinned v0.6.17 generated tree is now allowlisted/classified.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-132"></a>
### 132. P1-12-R1-PLAN-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:692-697"</code> |
| `title` | <code>"Enforce byte preservation for share decisions"</code> |
| `problem` | <code>"For spec and lessons candidates, the validator only runs privacy checks (plus marker/ID presence for lessons) and never compares `source_raw` with `candidate_raw` when `decision == \"share\"`; task attachments have the same gap. A share-labeled candidate can therefore alter or drop approved content and still be applied and later verified. Require exact source bytes for directly copied share members, reserving rewritten content for `redact` and the explicitly structured task conversion."</code> |
| `resolution` | <code>"对应生成/共享字节/旧路由门已修正，独立审查确认关闭；8个原P2未改。"</code> |
| `evidence` | <code>["unit-report-migration-planner-review-red-p1-12-migration-runtime-2026_09_19-10_08_30", "unit-report-migration-planner-pin-isolated-green-p1-12-migration-runtime-2026_09_19-10_28_57"]</code> |
| `review_closure` | <code>{"reviewer": "P112PlannerReview", "at": "2026-09-19T10:32:18.250432+08:00", "result": "All three assigned P1 findings closed; shared-config pin gate also closed through plan and semantic revalidation; no new P0/P1; eight P2 deferred unchanged; no review validation commands."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Share publication now compares direct candidate bytes to source bytes.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-133"></a>
### 133. P1-12-R1-PLAN-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-PLAN-003"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112PlannerReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1573-1576"</code> |
| `title` | <code>"Require a real pause for customized global routing"</code> |
| `problem` | <code>"The shared planner emits the maintenance pause only when the entire global `AGENTS.md` equals the pinned v1.0.15 checksum; any file that still contains the legacy routing plus foreign user entries is silently omitted from the manifest. Apply can then report success while the old global routing remains active, violating the apply-stage stop-old boundary. Preserve foreign text while updating a provably owned selector, or block the plan for explicit reconciliation when that ownership cannot be established."</code> |
| `resolution` | <code>"对应生成/共享字节/旧路由门已修正，独立审查确认关闭；8个原P2未改。"</code> |
| `evidence` | <code>["unit-report-migration-planner-review-red-p1-12-migration-runtime-2026_09_19-10_08_30", "unit-report-migration-planner-pin-isolated-green-p1-12-migration-runtime-2026_09_19-10_28_57"]</code> |
| `review_closure` | <code>{"reviewer": "P112PlannerReview", "at": "2026-09-19T10:32:18.250432+08:00", "result": "All three assigned P1 findings closed; shared-config pin gate also closed through plan and semantic revalidation; no new P0/P1; eight P2 deferred unchanged; no review validation commands."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Customized legacy global routing is blocked or explicitly paused, no longer silently omitted.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-134"></a>
### 134. P1-12-R1-RUN-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-RUN-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112RuntimeReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1299-1303"</code> |
| `title` | <code>"Fail closed on mixed Codex configuration files"</code> |
| `problem` | <code>"The v0.6.17 template inventory includes `.codex/config.toml` and `.codex/hooks.json`, but matching the digest recorded in `.template-hashes.json` proves only that the current bytes match that legacy record; it does not prove the whole shared configuration contains no foreign entries. A legacy project whose metadata records a customized/mixed config therefore reaches this `whole-resource` remove, and apply deletes every unrelated MCP/hook/config entry in that file. Restrict whole-file retirement to exact pinned official template bytes (including the supported rendered Python-command variants) and block customized/mixed files for reconciliation."</code> |
| `resolution` | <code>"匹配可变旧hash不再授权整文件删除共享配置；只接受固定官方模板/Python渲染变体，混合配置保留并阻断。"</code> |
| `evidence` | <code>["unit-report-migration-config-ownership-red-p1-12-migration-runtime-2026_09_19-10_17_19", "unit-report-migration-planner-pin-isolated-green-p1-12-migration-runtime-2026_09_19-10_28_57"]</code> |
| `review_closure` | <code>{"reviewer": "P112PlannerReview", "at": "2026-09-19T10:32:18.250432+08:00", "result": "All three assigned P1 findings closed; shared-config pin gate also closed through plan and semantic revalidation; no new P0/P1; eight P2 deferred unchanged; no review validation commands."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Whole-file removal is restricted to exact official template ownership, preserving mixed configs.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-135"></a>
### 135. P1-12-R2-LEAN-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-LEAN-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LeanFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"tests/test_sbtd_migration_verify.py:26-35"</code> |
| `title` | <code>"Reuse the existing deployment report fixture"</code> |
| `problem` | <code>"tests/test_sbtd_migration_verify.py:L26-60: shrink: this test rebuilds the same project/private files, raw report, native envelope, report references, and `save()` routine implemented immediately below by `ReportFixture`; move `ReportFixture` above the test and express the case as `fixture = ReportFixture(base); fixture.save(); ...`, for an estimated net reduction of about 30 lines without changing coverage."</code> |
| `decision` | <code>"可读性裁决：发现有依据，保留安全seam优先；依D-IMP-13本轮不删改P2/P3，累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Duplicated test fixture is readability-only; no observable migration defect.", "evidence": ["tests/test_sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "复用 deployment report fixture，删除重复构造", "verification": "verifier 子集、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-136"></a>
### 136. P1-12-R2-LEAN-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-LEAN-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LeanFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"tests/test_sbtd_migration_verify.py:419-428"</code> |
| `title` | <code>"Delete the second legacy-project fixture builder"</code> |
| `problem` | <code>"tests/test_sbtd_migration_verify.py:L419-450: delete: `_legacy_project` duplicates `legacy_project` from `test_sbtd_migration_apply.py` field-for-field, including the same identity, journal, binary, ignore file, owned routes, and template hashes; import and reuse that helper (as this suite already imports helpers across migration test modules), for an estimated net reduction of about 30 lines."</code> |
| `decision` | <code>"可读性裁决：发现有依据，保留安全seam优先；依D-IMP-13本轮不删改P2/P3，累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Duplicate legacy-project helper is test debt only.", "evidence": ["tests/test_sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "删除第二个 legacy fixture，迁移 verify 和 cleanup 调用方，不保留 alias", "verification": "cleanup/recovery/verify 子集、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-137"></a>
### 137. P1-12-R2-LEAN-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-LEAN-003"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LeanFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration.py:113-117"</code> |
| `title` | <code>"Remove unused migration runtime scaffolding"</code> |
| `problem` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration.py:L113-117: delete: `_file_reference` has no caller anywhere in production or tests; the same repository-wide trace also leaves `importlib.util`, `os`, `directory_snapshot`, `TaskStateError`, and `_PHASE_ORDER` unused in this module. Remove them rather than carrying a speculative API, for a grounded net reduction of 10 source lines."</code> |
| `decision` | <code>"可读性裁决：发现有依据，保留安全seam优先；依D-IMP-13本轮不删改P2/P3，累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Unused helper/import cleanup has no current correctness impact.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "删除无调用的迁移 helper/import/常量与不可达分支", "verification": "Ruff、类型检查、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-138"></a>
### 138. P1-12-R2-LEAN-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-LEAN-004"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LeanFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/requirements.txt:4-4"</code> |
| `title` | <code>"Remove the unreachable TOML editing dependency"</code> |
| `problem` | <code>"sbtd-workflow-onboard/requirements.txt:L4: delete: `tomlkit` is used only by `_remove_config_members`, reached only for apply-time `remove` operations owned by `json` or `toml`; the public planner emits no such operation, and `validate_legacy_inputs` rejects every private/shared operation outside publications, identity extraction, ignore protection, platform file/marker removals, legacy-tree cleanup, routing pause, and skill cleanup. Delete the dependency and the unreachable `_json_object`/`_toml_document`/`_config_member`/`_remove_config_members` branch, for an estimated net reduction of about 64 source lines and one external package."</code> |
| `decision` | <code>"可读性裁决：发现有依据，保留安全seam优先；依D-IMP-13本轮不删改P2/P3，累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "tomlkit/config-removal branch deletion is structural cleanup, not current defect.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "删除不可达迁移 TOML/config remover；**保留 tomlkit 依赖**，当前 Codex／OMP 已有真实消费者，删除整个依赖的旧前提不再成立", "verification": "生产消费者读取、依赖环境、接线和迁移全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-139"></a>
### 139. P1-12-R2-LEAN-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-LEAN-005"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LeanFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:443-447"</code> |
| `title` | <code>"Inline the one-call stage result adapter"</code> |
| `problem` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:L443-447: yagni: `_stage_results(*documents)` has one caller and hides a fixed positional `apply`/`deploy` pairing behind `zip`; build `{\"apply\": migration._result_index(apply_document), \"deploy\": migration._result_index(deployment)}` at the call site and delete the wrapper, for a grounded net reduction of 2 lines and clearer receipt routing."</code> |
| `decision` | <code>"可读性裁决：发现有依据，保留安全seam优先；依D-IMP-13本轮不删改P2/P3，累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "One-call stage adapter simplification is readability-only.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "删除单调用 stage adapter，直接构造固定 apply/deploy 结果映射", "verification": "verifier 子集、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-140"></a>
### 140. P1-12-R2-LEAN-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-LEAN-006"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112LeanFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration.py:319-328"</code> |
| `title` | <code>"Flatten speculative nested-source backup routing"</code> |
| `problem` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration.py:L319-328: shrink: `_source_backup_paths` searches for topmost source ancestors and `_backup_sources` separately skips descendant sources, but the accepted public manifest is already closed by `_validate_project_operations` to exactly one `.trellis` directory source per non-overlapping project. Map each source directly to `originals/&lt;sha256(source path)&gt;` and back it up once; this removes the nested containment/`next()` machinery for an estimated net reduction of about 17 lines."</code> |
| `decision` | <code>"可读性裁决：发现有依据，保留安全seam优先；依D-IMP-13本轮不删改P2/P3，累计十项门统一评估。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Nested-source backup simplification is optimization-only; current closure is guarded.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "按已校验的单旧树来源直接构造备份槽，删除不可达嵌套路由", "verification": "原件与空目录保全、cleanup/recovery 子集、原生恢复、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-141"></a>
### 141. P1-12-R2-SEC-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-SEC-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112SecurityFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:736"</code> |
| `title` | <code>"P2: Duplicate legacy task IDs are discarded before relationship validation"</code> |
| `problem` | <code>"Two valid legacy task folders can reuse the same logical id—for example active and archived tasks—with separate approved targets ai/tasks/foo and ai/tasks/archive/2026-Q3/foo. _validate_project_closures overwrites the first projection before validate_projection_graph runs. Both publication operations remain, but only the last task participates in uniqueness and relationship checks. Plan/apply can publish an ambiguous task set that the current TaskStore then refuses to load. Verification repeats the same lossy validation. This is a legacy-data/corruption trigger, not a forged-receipt scenario. Defer at P2 under D-IMP-13."</code> |
| `decision` | <code>"保留独立安全审查原P2级别，依D-IMP-13不夹带修复，累计十项门评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Duplicate logical legacy IDs reject before a projection map overwrite."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Duplicate logical legacy IDs reject before a projection map overwrite.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-142"></a>
### 142. P1-12-R1-RUN-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-RUN-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112RuntimeReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration.py:551-554"</code> |
| `title` | <code>"Record only attempted shared operations in partial receipts"</code> |
| `problem` | <code>"When an earlier private resource fails before a declared shared resource is attempted (for example, a project `.gitignore` write fails before the shared HOME `AGENTS.md` pause), `results` correctly omits that shared resource but every project still lists all manifest shared operation IDs here. `validate_declared_bindings()` then rejects the cumulative receipt because those IDs have no observed shared result, so the runtime returns a generic blocked envelope instead of saving the required partial receipt and preserving retry evidence for already-written resources. Populate `shared_operation_ids` from shared resources actually present in `results`; completed projects will still require the full declared set."</code> |
| `resolution` | <code>"真实部分失败红测与累计重试绿测通过；只引用已观察共享结果，完成仍需全部依赖。"</code> |
| `review_closure` | <code>{"reviewer": "P112RuntimeReview", "at": "2026-09-19T11:24:23.133419+08:00", "result": "Two P1s closed, no validation or edits; two P2s deferred."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Partial apply receipts now list only shared operations actually observed, while completed projects still require the full declared dependency set; this preserves retry evidence after an earlier private failure.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-143"></a>
### 143. P1-12-R1-VERIFY-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:513-513"</code> |
| `title` | <code>"Initialize the blocked-project set before verification"</code> |
| `problem` | <code>"Every otherwise valid `verify_migration` call reaches `root in blocked_roots`, but `blocked_roots` is never defined anywhere in the module. This raises `NameError` before a verification envelope can be returned, so the integrated `migration --phase verify` path cannot succeed; initialize an empty set alongside `failed_roots` and populate it for observation failures."</code> |
| `resolution` | <code>"修改前源码回放红测及影响范围绿测；按任务契约裁决实现，未改原生schema、未新增raw闭集格式，P2另行保留。"</code> |
| `review_closure` | <code>{"reviewer": "P112VerifierReview", "at": "2026-09-19T11:24:23.133419+08:00", "result": "Four P1s closed including branchless labels with unchanged native schemas, apply-epoch retries, execution essentials and proven retired absence; no new P0/P1; no validation or edits."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "The verifier initializes and populates blocked_roots, so valid verification returns an envelope instead of NameError.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-144"></a>
### 144. P1-12-R1-VERIFY-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:307-310"</code> |
| `title` | <code>"Define a verifiable report identity for null source refs"</code> |
| `problem` | <code>"The migration contract permits both non-Git projects `(source_ref=null, head=null)` and detached Git projects `(source_ref=null, head=&lt;OID&gt;)`, but the native v1/v2 evidence schemas require `repository.sourceRef` to be a non-empty string. A null value fails native schema validation, while any string fails this equality check against the outer null, so these supported projects can never reach `verified`; define one explicit native representation for null refs across schema, producer, and consumer while retaining the outer null values."</code> |
| `resolution` | <code>"修改前源码回放红测及影响范围绿测；按任务契约裁决实现，未改原生schema、未新增raw闭集格式，P2另行保留。"</code> |
| `review_closure` | <code>{"reviewer": "P112VerifierReview", "at": "2026-09-19T11:24:23.133419+08:00", "result": "Four P1s closed including branchless labels with unchanged native schemas, apply-epoch retries, execution essentials and proven retired absence; no new P0/P1; no validation or edits."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Null source refs are represented consistently for native evidence while outer migration records retain null, allowing non-Git and detached projects to verify.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-145"></a>
### 145. P1-12-R1-VERIFY-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-003"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:190-196"</code> |
| `title` | <code>"Validate carried reports against their producing attempt"</code> |
| `problem` | <code>"`deployment_evidence` retries may legally carry an unchanged successful project's report references forward, while the retry's `started_at`/`finished_at` describe only the new attempt. This comparison rejects those cumulative reports because their raw timestamps precede the retry start even though `validate_cumulative` accepts the unchanged refs; any partial retry preserving a prior successful smoke therefore cannot verify. Bind each retained report to its producing attempt window, or require and cumulatively validate fresh replacement reports on every retry."</code> |
| `resolution` | <code>"修改前源码回放红测及影响范围绿测；按任务契约裁决实现，未改原生schema、未新增raw闭集格式，P2另行保留。"</code> |
| `review_closure` | <code>{"reviewer": "P112VerifierReview", "at": "2026-09-19T11:24:23.133419+08:00", "result": "Four P1s closed including branchless labels with unchanged native schemas, apply-epoch retries, execution essentials and proven retired absence; no new P0/P1; no validation or edits."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Cumulative retries may carry prior successful reports and verifier binds them to their producing attempt rather than incorrectly requiring timestamps inside the new retry window.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-146"></a>
### 146. P1-12-R1-VERIFY-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-VERIFY-004"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112VerifierReview"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:182-189"</code> |
| `title` | <code>"Validate the complete raw runner report before accepting it"</code> |
| `problem` | <code>"`_accept_raw_smoke` only probes a subset of fields, so a resealed object can omit the required executed command, stdout/stderr, test type, provenance, and actual `processExitCode`, or declare `exitCode: 0` beside `processExitCode: 1`, and still authorize a verified cleanup. Validate the raw bytes against a closed, shared runner-report contract and require every authoritative process-success field to agree before applying the scope checks."</code> |
| `resolution` | <code>"修改前源码回放红测及影响范围绿测；按任务契约裁决实现，未改原生schema、未新增raw闭集格式，P2另行保留。"</code> |
| `review_closure` | <code>{"reviewer": "P112VerifierReview", "at": "2026-09-19T11:24:23.133419+08:00", "result": "Four P1s closed including branchless labels with unchanged native schemas, apply-epoch retries, execution essentials and proven retired absence; no new P0/P1; no validation or edits."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Raw runner reports are validated against a closed contract and authoritative exit fields before cleanup can be authorized.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-147"></a>
### 147. P1-12-R2-SEC-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-SEC-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112SecurityFinal"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1619"</code> |
| `title` | <code>"P1: Existing OMP global legacy routing is omitted from the migration batch"</code> |
| `problem` | <code>"For an authorized OMP or dual-host migration with an existing legacy ~/.omp/agent/AGENTS.md, plan inventories only Codex AGENTS and the global Skill root. The OMP router is never declared, backed up, paused, or subsequently observed. Apply can report applied while a supported host still has its old routing active, violating the maintenance-window stop-old gate. No artifact forgery or concurrent writer is required: ordinary onboarding writes the same global template to both host paths, and a byte-exact legacy OMP installation is sufficient."</code> |
| `resolution` | <code>"OMP现存全局router纳入nofollow盘点、所有权/暂停/备份与完整依赖；缺失根不创建；原生文件红绿及独立复核关闭。"</code> |
| `review_closure` | <code>{"reviewer": "P112SecurityFinal", "at": "2026-09-19T11:24:23.133419+08:00", "result": "OMP P1 closed; no remaining P0/P1 in assigned scope; duplicate ID P2 deferred; no validation or edits."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Existing OMP router is now included in shared discovery, ownership, pause, backup, and dependents; absent OMP root is not created.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-148"></a>
### 148. P1-12-R1-FS-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-FS-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"independent-filesystem-review"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"P1: Failed directory readback deletes user-modified files"</code> |
| `problem` | <code>"A concurrent edit to a newly copied file is detected by install_reference's directory readback, but rollback then calls _remove_created, which unconditionally unlinks every recorded file path. The changed bytes are neither the approved candidate nor covered by the original-target backup. Consequently an explicitly detected user edit is permanently deleted. The same cleanup helper is used by failed backup copies and replacement staging."</code> |
| `resolution` | <code>"完整stage发布前验证；本次创建项按实际字节摘要守卫清理，变化内容保留。真实文件/目录故障注入红绿通过，原filesystem独立复核已关闭两P1。"</code> |
| `evidence` | <code>["unit-report-migration-fs-independent-review-red-p1-12-migration-runtime-2026_09_19-09_28_15", "unit-report-migration-directory-before-publication-red-p1-12-migration-runtime-2026_09_19-09_40_25", "unit-report-migration-fs-publication-complete-green-p1-12-migration-runtime-2026_09_19-09_43_46"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Rollback cleanup now removes only unchanged created entries, preserving concurrent user edits.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-149"></a>
### 149. P1-12-R1-FS-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R1-FS-002"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"independent-filesystem-review"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"P1: File candidates are checksum-validated only after publication"</code> |
| `problem` | <code>"install_reference hashes the source before copying it, but does not compare the completed staging file with the approved source checksum before _commit_staged publishes it. If the source changes during that interval, the replacement is installed and only then rejected by target readback. This can publish unapproved/private bytes to a shared target and replace the original even though the candidate fails validation."</code> |
| `resolution` | <code>"完整stage发布前验证；本次创建项按实际字节摘要守卫清理，变化内容保留。真实文件/目录故障注入红绿通过，原filesystem独立复核已关闭两P1。"</code> |
| `evidence` | <code>["unit-report-migration-fs-independent-review-red-p1-12-migration-runtime-2026_09_19-09_28_15", "unit-report-migration-directory-before-publication-red-p1-12-migration-runtime-2026_09_19-09_40_25", "unit-report-migration-fs-publication-complete-green-p1-12-migration-runtime-2026_09_19-09_43_46"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "File candidate is checksum-validated in staging before publication.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-150"></a>
### 150. P1-12-R2-STATIC-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-STATIC-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"Main-static-validation"</code> |
| `source_commit` | <code>"794059214beed7970f37878cfbb098b832f95f63"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"迁移代码的非阻断样式诊断待统一整理"</code> |
| `problem` | <code>"完整Ruff检查非零；除已登记unused代码候选及有意显式UTF-8/日期粒度表达外，仍有上下文合并、导入顺序、未用局部变量等样式建议。无E9/F63/F7/F82诊断；ty已按真实JSON类型修正并通过。"</code> |
| `decision` | <code>"依D-IMP-13不修延期P2/P3，不新增ignore/禁用项目规则，不把全量Ruff非零报成通过；细项在累计十项门评估。"</code> |
| `locations` | <code>[{"path": "sbtd-workflow-onboard/scripts/sbtd_migration_files.py", "line": 890, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "line": 32, "code": "UP035", "message": "Import from `collections.abc` instead: `Mapping`"}, {"path": "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "line": 370, "code": "RUF007", "message": "Prefer `itertools.pairwise()` over `zip()` when iterating over successive pairs"}, {"path": "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "line": 1201, "code": "SIM102", "message": "Use a single `if` statement instead of nested `if` statements"}, {"path": "tests/test_onboard_migration_cli.py", "line": 27, "code": "PLW1510", "message": "`subprocess.run` without explicit `check` argument"}, {"path": "tests/test_onboard_migration_cli.py", "line": 61, "code": "PLW1510", "message": "`subprocess.run` without explicit `check` argument"}, {"path": "tests/test_onboard_migration_cli.py", "line": 70, "code": "PLW1510", "message": "`subprocess.run` without explicit `check` argument"}, {"path": "tests/test_sbtd_migration_apply.py", "line": 40, "code": "PLR1704", "message": "Redefining argument with the local name `name`"}, {"path": "tests/test_sbtd_migration_contracts.py", "line": 1, "code": "I001", "message": "Import block is un-sorted or un-formatted"}, {"path": "tests/test_sbtd_migration_files.py", "line": 99, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_files.py", "line": 160, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_files.py", "line": 191, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_files.py", "line": 257, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1, "code": "I001", "message": "Import block is un-sorted or un-formatted"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 17, "code": "I001", "message": "Import block is un-sorted or un-formatted"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 202, "code": "UP032", "message": "Use f-string instead of `format` call"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 203, "code": "UP032", "message": "Use f-string instead of `format` call"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 544, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 554, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 560, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 652, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 725, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 745, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 775, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 805, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 823, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 842, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 857, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 887, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 917, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 931, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 946, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 959, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1023, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1066, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1086, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1111, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1147, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1183, "code": "RUF059", "message": "Unpacked variable `project` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1183, "code": "RUF059", "message": "Unpacked variable `vault` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1221, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1228, "code": "RUF059", "message": "Unpacked variable `project` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1228, "code": "RUF059", "message": "Unpacked variable `vault` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1237, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1254, "code": "RUF059", "message": "Unpacked variable `project` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1254, "code": "RUF059", "message": "Unpacked variable `vault` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1262, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1275, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1282, "code": "RUF059", "message": "Unpacked variable `project` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1282, "code": "RUF059", "message": "Unpacked variable `vault` is never used"}, {"path": "tests/test_sbtd_migration_plan.py", "line": 1331, "code": "SIM117", "message": "Use a single `with` statement with multiple contexts instead of nested `with` statements"}]</code> |
| `existing_script_added` | <code>[["onboard_contracts.py", "I001", "Import block is un-sorted or un-formatted"], ["onboard_contracts.py", "UP012", "Unnecessary UTF-8 `encoding` argument to `encode`"], ["onboard_contracts.py", "SIM102", "Use a single `if` statement instead of nested `if` statements"]]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Remaining Ruff diagnostics are style/nonblocking; no E9/F63/F7/F82 or data defect.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "清理记录所涉迁移代码／测试的导入、无用局部变量、with、日期粒度及表达诊断；不新增 suppression", "verification": "Ruff 23 文件、ty 11 生产模块通过", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-151"></a>
### 151. P1-12-R3-WORKFLOW-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R3-WORKFLOW-001"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P112DocsExactReview / P112SecurityFinal"</code> |
| `source_commit` | <code>"b810ef0da419f9c741705590000e2c8be49c71cd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:768-818,1457"</code> |
| `title` | <code>"自定义旧workflow缺少批准且重复校验可被重封装绕过"</code> |
| `problem` | <code>"固定旧配置器将non-native workflow.md作为用户内容并移除template hash；此前plan未要求其明确裁决，重复校验也未再次核对完整原目录覆盖，可能把未批准规则交给后续整树清理。"</code> |
| `resolution` | <code>"所有generated-runtime类别含workflow.md均需模板所有权或逐项明确批准；重复校验先验证操作/闭包，再从匹配完整摘要的live原目录或确定性私有原件读取同一库存、绑定metadata摘要并复用完整覆盖门；.gitkeep只取该库存。"</code> |
| `evidence` | <code>["unit-report-migration-custom-workflow-red-p1-12-migration-runtime-2026_09_19-12_15_31", "unit-report-migration-original-inventory-red-p1-12-migration-runtime-2026_09_19-12_19_52", "unit-report-migration-custom-workflow-green-p1-12-migration-runtime-2026_09_19-12_19_52", "unit-report-migration-custom-workflow-affected-p1-12-migration-runtime-2026_09_19-12_20_51"]</code> |
| `review_closure` | <code>{"reviewers": ["P112DocsExactReview", "P112SecurityFinal"], "recordedAt": "2026-09-19T12:24:42.438143+08:00", "result": "Both independently closed P1; no remaining P0/P1; no reviewer execution or edits."}</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Customized workflow.md now requires ownership/approval and complete inventory revalidation, closing reseal bypass.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-152"></a>
### 152. P1-04-R1-GUARD-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-GUARD-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104GuardAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"workspace索引或父目录识别可扩大native刷新范围"</code> |
| `problem` | <code>"完整stamp不排除workspace索引，native可刷新未选child或删除父图。"</code> |
| `resolution` | <code>"共享build/launch拒绝workspace索引与native父目录形状；P104FinalGuardReview复核关闭。"</code> |
| `evidence` | <code>["api-report-codex-native-guard-pre-fix-red-p1-04-codex-wiring-2026_09_19-16_42_51", "api-report-codex-native-guard-matrix-p1-04-codex-wiring-2026_09_19-16_40_20"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Workspace index/parent rejected before native launch.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-153"></a>
### 153. P1-04-R1-GUARD-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-GUARD-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104GuardAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"图内未验证链接可让Stop覆盖外部文件"</code> |
| `problem` | <code>"仅检查wiring/stamp不能阻止其他输出链接被native writer跟随。"</code> |
| `resolution` | <code>"完整生成树拒绝symlink/hardlink/reparse/special条目，原件不变；reparse按stat属性检查。P104FinalGuardReview关闭，Windows原生未实测。"</code> |
| `evidence` | <code>["api-report-codex-native-guard-matrix-p1-04-codex-wiring-2026_09_19-16_40_20"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Generated tree requires ordinary non-linked entries.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-154"></a>
### 154. P1-04-R1-GUARD-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-GUARD-003"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104GuardAudit/P104FinalGuardReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"图、extract缓存及有效concept指针可越界读写"</code> |
| `problem` | <code>"原始path检查不能覆盖强制转换、comma-join、span解析及fallback形成的最终指针。"</code> |
| `resolution` | <code>"按固定native sink证明raw/span/精确joined指针和fallback，拒绝未支持可转换值；safe missing source保留。独立复核关闭。"</code> |
| `evidence` | <code>["api-report-codex-concept-pointer-red-p1-04-codex-wiring-2026_09_19-17_10_13", "api-report-codex-concept-pointer-green-p1-04-codex-wiring-2026_09_19-17_31_30", "unit-report-codex-context-mode-concept-green-p1-04-codex-wiring-2026_09_19-17_35_40"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Final graph/cache/concept pointers and coercions are guarded.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-155"></a>
### 155. P1-04-R1-WIRING-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-WIRING-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104CandidatesAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"Stop超时短于真实同步build预算"</code> |
| `problem` | <code>"10秒host预算会截断native最多120秒build。"</code> |
| `resolution` | <code>"Stop预算130秒；真实native dirty Stop重建并观察新符号。非实际Codex Stop事件证明。"</code> |
| `evidence` | <code>["api-report-codex-native-dirty-stop-p1-04-codex-wiring-2026_09_19-16_40_20"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Stop timeout 130s exceeds native 120s cap.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-156"></a>
### 156. P1-04-R1-WIRING-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-WIRING-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104CandidatesAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"POSIX quoting不适用于Codex Windows cmd.exe"</code> |
| `problem` | <code>"单引号编码使Windows hook无法启动。"</code> |
| `resolution` | <code>"Windows采用stdlib编码及对应所有权解析，拒绝cmd扩展/操作符路径；独立源码与方言回归通过，不冒称Windows原生验收。"</code> |
| `evidence` | <code>["unit-report-codex-review-fixes-focused-p1-04-codex-wiring-2026_09_19-16_39_24"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Windows quoting is dialect-specific and rejects cmd operators.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-157"></a>
### 157. P1-04-R1-WIRING-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-WIRING-003"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104CandidatesAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_wiring.py:_merge_hook_event"</code> |
| `title` | <code>"受管hook去重可能移动foreign trust索引"</code> |
| `problem` | <code>"删除旧受管handler或空group会改变后续foreign handler的group/handler index，Codex按索引持久化的trust/enablement可能失效。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不在本轮修复；第十项P1闭环后统一评估。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"普通 singleton 受管 hook 原位更新保留 foreign 索引；混合或重复布局先拒绝，不隐式移动信任索引。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "普通 singleton 受管 hook 原位更新保留 foreign 索引；混合或重复布局先拒绝，不隐式移动信任索引。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-158"></a>
### 158. P1-04-R1-WIRING-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-WIRING-004"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104CandidatesAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_wiring.py:_merge_hook_event"</code> |
| `title` | <code>"保留畸形hook容器可能导致host拒绝整文件"</code> |
| `problem` | <code>"非object group、非array hooks或非object handler被跳过并保留；Codex可能拒绝该配置但候选仍报告configured。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不在本轮修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"合法 foreign group 可省略 hooks；null、非数组或非对象 handler 先拒绝且不改原配置。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "合法 foreign group 可省略 hooks；null、非数组或非对象 handler 先拒绝且不改原配置。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-159"></a>
### 159. P1-04-R1-WIRING-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-WIRING-005"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104CandidatesAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_wiring.py:SessionStart matcher"</code> |
| `title` | <code>"SessionStart matcher未覆盖clear事件"</code> |
| `problem` | <code>"Codex0.154包含startup/resume/clear/compact，当前matcher漏clear，清空上下文后缺少Graft定向提示。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不在本轮修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Pinned local finding identifies Codex 0.154 SessionStart clear; matcher now is startup&#124;resume&#124;clear&#124;compact."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Pinned local finding identifies Codex 0.154 SessionStart clear; matcher now is startup&#124;resume&#124;clear&#124;compact.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-160"></a>
### 160. P1-04-R1-WIRING-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-WIRING-006"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104CandidatesAudit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"assets/graft-instructions.txt:3"</code> |
| `title` | <code>"project-only指令假定存在全局MCP注册"</code> |
| `problem` | <code>"同一fence用于不写HOME的project-only，但指令引用active config中的sbtd-graft server；未必存在。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不在本轮修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"指令区分 project-only 与已注册 MCP，并接受 OMP 在其他名称下启用的等价 managed-launcher/root 绑定。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "指令区分 project-only 与已注册 MCP，并接受 OMP 在其他名称下启用的等价 managed-launcher/root 绑定。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-161"></a>
### 161. P1-04-R1-DEPLOY-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R1-DEPLOY-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"Main-regression"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_deployment.py:execute_migration_deployment"</code> |
| `title` | <code>"共享scope创建失败丢弃先前资源结果"</code> |
| `problem` | <code>"mkdir位于resource错误边界外；此前项目规则和图已写入，异常却直接跳过累计证据保存。"</code> |
| `resolution` | <code>"目录准备进入execute_resource受控错误边界，保存已观察结果；正常接线原件目录准备也复用该边界。"</code> |
| `evidence` | <code>["unit-report-codex-partial-scope-red-p1-04-codex-wiring-2026_09_19-15_42_22", "unit-report-codex-partial-scope-green-p1-04-codex-wiring-2026_09_19-15_43_24"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Shared preparation failure persists cumulative prior results.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-162"></a>
### 162. P1-04-ADVISOR-OP-KIND

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-OP-KIND"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"dismissed"</code> |
| `problem` | <code>"提醒称Operation类型应为directory而不是dir。"</code> |
| `decision` | <code>"实际onboard.py build_operations在5993-5998以dir创建Skill操作，copy_operation和verify_operation也以dir分支；保留真实约定。完整global部署真实运行通过。"</code> |

<a id="record-163"></a>
### 163. P1-04-ADVISOR-PROJECT-ONLY-SHARED

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-PROJECT-ONLY-SHARED"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"dismissed"</code> |
| `problem` | <code>"提醒称拒绝shared apply但无deploy会破坏合法project-only清单。"</code> |
| `decision` | <code>"PRD10.2.1明确project-only遇HOME操作拒绝；attach_codex_deployment原已拒绝含shared_operations的project-only。当前测试与真实project-only路径均通过；不恢复会放过重封装缺失shared deploy的早退。"</code> |

<a id="record-164"></a>
### 164. P1-04-ADVISOR-OMP-MIRROR

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-OMP-MIRROR"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"dismissed"</code> |
| `problem` | <code>"提醒称Codex完整部署包含现存OMP公共AGENTS镜像即越权OMP接线。"</code> |
| `decision` | <code>"普通init保留语义及既有明确OMP global AGENTS契约要求现存.omp镜像，版本化automation第105条和PRD10.3仍保留该规则。现有build_operations统一选择，全共享资源在plan封存并确认；未创建缺失.omp，不写OMP MCP/events。REFERENCE明确两种写入不同，真实完整部署确认OMP MCP未新增。"</code> |

<a id="record-165"></a>
### 165. P1-04-ADVISOR-DUPLICATE-COPY

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-DUPLICATE-COPY"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"dismissed"</code> |
| `problem` | <code>"提醒称copied字典会允许同target重复copy并重复执行。"</code> |
| `decision` | <code>"seal_document前置codec已在onboard_contracts.py:821拒绝重复operation_id；改变selector仍由_check_operation_group:673-689拒绝template-source的同资源多操作。保持既有统一校验，不添加重复专用规则。"</code> |

<a id="record-166"></a>
### 166. P1-04-R2-CLOSURE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-CLOSURE-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ClosureReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_migration_plan.py:_validate_project_operations"</code> |
| `title` | <code>"已经完整保护的ignore仍被要求新增保护操作"</code> |
| `problem` | <code>"已有全部migration-local-ignore规则时_ignore_operation返回None，但任何deploy存在都会要求恰好一条gitignore操作，安全的现存保护因此被拒绝。结论来自源码，未执行该场景。"</code> |
| `decision` | <code>"D-IMP-13原级延期；后续应绑定并复验已满足的保护，而非放宽缺失保护。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Revalidation derives whether an ignore operation is currently necessary; already complete protection accepts no redundant operation, while altered/redundant operations still reject."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Revalidation derives whether an ignore operation is currently necessary; already complete protection accepts no redundant operation, while altered/redundant operations still reject.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-167"></a>
### 167. P1-04-R2-CLOSURE-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-CLOSURE-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ClosureReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_deployment.py:attach_codex_deployment"</code> |
| `title` | <code>"新增Codex HOME父scope未合并现有子Skill根"</code> |
| `problem` | <code>"active HOME的AGENTS缺失或current，而其skills目录含受管旧Skill时，旧计划只有子skills根；新完整部署再加HOME父根，同一target被两个根覆盖，codec拒绝。与P1-12无关Skill消费者限制不同；源码结论，未执行该场景。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不在本轮扩大共享根重构。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"所有 Codex/OMP host 根加入后，仅合并依赖项目集合相同的嵌套 Skills 根；不放宽共享授权闭包。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "所有 Codex/OMP host 根加入后，仅合并依赖项目集合相同的嵌套 Skills 根；不放宽共享授权闭包。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-168"></a>
### 168. P1-04-R2-PRODUCER-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"完整安装接线绑定临时bootstrap源码"</code> |
| `problem` | <code>"删除执行安装的checkout后MCP/hooks仍指向它，已安装Skill不能独立运行。"</code> |
| `resolution` | <code>"完整安装绑定canonical installed package，normal init先核验保留壳与当前版本；迁移先完成安装资源，再发布MCP/hooks并验证整个launcher目录。"</code> |
| `evidence` | <code>["api-report-codex-installed-launcher-pre-fix-red-p1-04-codex-wiring-2026_09_19-16_42_52", "api-report-codex-installed-launcher-p1-04-codex-wiring-2026_09_19-16_40_20"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Published bindings use canonical installed launcher.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-169"></a>
### 169. P1-04-R2-PRODUCER-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"部署时钟早于输入证据仍先写后拒绝保存"</code> |
| `problem` | <code>"apply或previous finish在当前时钟之后，旧preflight放行，最终累计校验才拒绝，可能产生无新证据写入。"</code> |
| `resolution` | <code>"开始时间在全预检内捕获，复用codec精确时间比较，早于apply/previous完成均写前拒绝。"</code> |
| `evidence` | <code>["unit-report-codex-context-mode-concept-green-p1-04-codex-wiring-2026_09_19-17_35_40"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Start time captured in preflight; stale evidence rejected before writes.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-170"></a>
### 170. P1-04-R2-PRODUCER-003

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-003"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"smoke后观察异常丢弃已写资源结果"</code> |
| `problem` | <code>"读后snapshot异常或报告Unicode/ValueError在保存累计证据前逃逸；已有写入结果不返回。"</code> |
| `resolution` | <code>"smoke异常与资源复验失败标记依赖项目failed，保留真实已完成resource proof；保存失败仍返回null及全部已观察结果，不伪造可恢复收据。"</code> |
| `evidence` | <code>["unit-report-codex-review-fixes-focused-p1-04-codex-wiring-2026_09_19-16_39_24"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Smoke/save failures retain observed resources and do not fabricate receipt.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-171"></a>
### 171. P1-04-R2-PRODUCER-004

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-004"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"可选Graft缺失阻断普通安装"</code> |
| `problem` | <code>"普通init显式Codex项目在未安装Graft时被wiring preflight拒绝，破坏拒绝可选工具仍继续无关安全工作的契约。"</code> |
| `resolution` | <code>"只对runtime-unavailable且无hooks授权的普通路径报告not-available并继续；显式hooks与迁移部署仍拒绝，无安装或伪接线。"</code> |
| `evidence` | <code>["api-report-codex-optional-graft-fallback-p1-04-codex-wiring-2026_09_19-17_03_22"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Normal init continues with optional Graft unavailable unless explicit hooks/migration requires it.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-172"></a>
### 172. P1-04-R2-PRODUCER-005

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-005"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"onboard.py:wiring_exit"</code> |
| `title` | <code>"普通接线blocked退出2被外层映射为5"</code> |
| `problem` | <code>"写前态冲突返回blocked/2，但外层统一标setup failed后返回5。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不改既有状态聚合。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"保留 wiring 返回的 blocked=2，不把它映射为 failed=5；部分 setup 状态同步报告。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "保留 wiring 返回的 blocked=2，不把它映射为 failed=5；部分 setup 状态同步报告。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-173"></a>
### 173. P1-04-R2-PRODUCER-006

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-006"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"onboard.py:plan/check human output"</code> |
| `title` | <code>"非JSON计划缺少接线阻断原因"</code> |
| `problem` | <code>"graftWiring写入JSON对象，但print_plan/print_check_results不展示其reason，用户只见退出2。"</code> |
| `decision` | <code>"D-IMP-13原级延期；不借非JSON文案扩大本轮修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"human check/plan 展示接线 status/reason/nextStep；标为安装可行性，不冒充现有配置健康证明。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "human check/plan 展示接线 status/reason/nextStep；标为安装可行性，不冒充现有配置健康证明。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-174"></a>
### 174. P1-04-R2-PRODUCER-007

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R2-PRODUCER-007"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104ProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_deployment.py:plan_normal_wiring"</code> |
| `title` | <code>"覆盖模板前按旧AGENTS预渲染会拒绝本可替换的畸形fence"</code> |
| `problem` | <code>"非skip模式仍用旧字节预渲染；无效UTF8/畸形marker会阻断已授权模板覆盖。"</code> |
| `decision` | <code>"D-IMP-13原级延期；Main曾误开始修此P2，已完整撤销renderBefore及其状态改写，未保留泄露原始配置的中间实现。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"选中 AGENTS 替换时 check/plan/init 使用规范模板预渲染；skip-project-agents 保留当前字节校验。输出仅声明安装可行性，原文件未提前写入。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "选中 AGENTS 替换时 check/plan/init 使用规范模板预渲染；skip-project-agents 保留当前字节校验。输出仅声明安装可行性，原文件未提前写入。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-175"></a>
### 175. P1-04-R3-PRODUCER-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R3-PRODUCER-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104FinalProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"init接受project-only封存部署却伪装完整模式"</code> |
| `problem` | <code>"模式检查只有单向HOME拒绝，init可以消费无共享deploy的清单。"</code> |
| `resolution` | <code>"复验闭集部署集合后要求graft-mcp存在当且仅当入口init；不添加重复可漂移模式字段。"</code> |
| `evidence` | <code>["unit-report-codex-context-mode-red-p1-04-codex-wiring-2026_09_19-17_34_16", "unit-report-codex-context-mode-concept-green-p1-04-codex-wiring-2026_09_19-17_35_40"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Init requires shared graft-mcp; project-only cannot masquerade full init.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-176"></a>
### 176. P1-04-R3-PRODUCER-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R3-PRODUCER-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104FinalProducerReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"catalog选出的部署模板未被runtime身份绑定"</code> |
| `problem` | <code>"project-only计划后改变catalog的project模板source，可在固定文件哈希未变时部署另一份未计划字节。"</code> |
| `resolution` | <code>"runtime identity纳入catalog及schema，并纳入实际选中项目模板的完整字节摘要；真实隔离安装副本修改catalog后写前拒绝，恢复原catalog后完成部署。"</code> |
| `evidence` | <code>["api-report-codex-catalog-binding-green-p1-04-codex-wiring-2026_09_19-17_35_40"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Catalog and selected template bytes sealed into runtime identity.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-177"></a>
### 177. P1-04-R3-DOCS-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R3-DOCS-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104FinalDocsLeanReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"旧P1-03文档否认已实现接线并漏列project-only图写入"</code> |
| `problem` | <code>"README/HTML/Skill/REFERENCE旧段称Graft接线尚未提供或project-only仅AGENTS/ignore，会误报写入范围。"</code> |
| `resolution` | <code>"同步各入口的已实现Codex范围、项目fence/图写入和剩余OMP/wrapper/Windows/cleanup门，安装证明仍不扩大为host/完整v2验收；等待独立最终复验。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Docs describe Codex fence/graph behavior and retain OMP/Windows/cleanup limits.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-178"></a>
### 178. P1-04-R3-LEAN-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R3-LEAN-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"dismissed"</code> |
| `source` | <code>"P104FinalDocsLeanReview"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd_codex_deployment.py:build_project_graph"</code> |
| `title` | <code>"生产调用方未消费图构建返回详情"</code> |
| `problem` | <code>"生产execute_resource丢弃返回的state/command结果，导致额外图摘要与返回构造；私有原生smoke仍观察此返回。"</code> |
| `decision` | <code>"Code Readability：职责内可简化但不是安全修复，依D-IMP-13延期，不为缩行删除已验证边界。"</code> |
| `resolution` | <code>"Reviewer withdrew deletion after confirming native smoke consumes build return detail; review-disposition record retained. No API removal justified."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "dismissed", "decision": "Reviewer withdrew deletion after confirming native smoke consumes build return detail; review-disposition record retained. No API removal justified.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "dismissed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-179"></a>
### 179. P1-04-ADVISOR-MODE-FIELD

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-MODE-FIELD"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"dismissed"</code> |
| `problem` | <code>"提醒直接读取sealed payload.deployment_mode。"</code> |
| `decision` | <code>"当前closed schema没有该字段；参数只在plan生成完整或project-only资源闭包。validate_codex_declarations已重推两种精确集合，入口按唯一graft-mcp成员绑定足以表达当前契约；不添加无需求重复状态。"</code> |

<a id="record-180"></a>
### 180. P1-04-ADVISOR-EDIT-RECOVERY

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-EDIT-RECOVERY"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"resolved"</code> |
| `problem` | <code>"Main在收尾行号编辑中产生过误删括号/import、Path当bytes、缺少code局部变量、误删hooksAuthorized及原始renderBefore泄露候选。"</code> |
| `decision` | <code>"停止运行并按实际文件重读恢复；P2预渲染修改全部撤销，renderBefore不再存在，dataclass/import和hooksAuthorized恢复，concept使用固定错误码；后续28项定点与concept原生负例通过。失败编辑不冒充已验证版本；最终全量仍需重跑。"</code> |

<a id="record-181"></a>
### 181. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"review-closure"</code> |
| `task` | <code>"P1-04"</code> |
| `source_revision` | <code>"dirty"</code> |
| `reviewers` | <code>["P104FinalGuardReview", "P104FinalProducerReview", "P104FinalDocsLeanReview"]</code> |
| `result` | <code>"三路最终源码复核无剩余P0/P1；有效指针、入口及catalog绑定、文档范围已关闭。P2延期；全量和精确head证明仍须完成。"</code> |

<a id="record-182"></a>
### 182. P1-04-ADVISOR-PRECOMMIT-PROOF

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory"</code> |
| `id` | <code>"P1-04-ADVISOR-PRECOMMIT-PROOF"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"accepted"</code> |
| `problem` | <code>"首轮全量失败不能由定点通过代替。"</code> |
| `decision` | <code>"先完整修正版全量，再提交并复验精确head；首轮885项/1error/6skip保留失败。"</code> |

<a id="record-183"></a>
### 183. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"review-disposition"</code> |
| `task` | <code>"P1-04"</code> |
| `finding_id` | <code>"P1-04-R3-LEAN-001"</code> |
| `status` | <code>"withdrawn-by-reviewer"</code> |
| `source` | <code>"P104FinalDocsLeanReview"</code> |
| `decision` | <code>"复核得知私有native build smoke实际观察返回结果后撤回删除要求；保留原finding历史，不在本轮删除API。"</code> |

<a id="record-184"></a>
### 184. P1-04-R3-STATIC-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R3-STATIC-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"Main-static-validation"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"静态样式诊断与既有类型债务保留"</code> |
| `problem` | <code>"完整Ruff52项非零，含既有及新增导入排序、unused、等价简化/显式check建议；没有E9/F63/F7/F82。ty在相同解释器及module roots下，基线和当前均93项，新增差集为空。"</code> |
| `decision` | <code>"依D-IMP-13不修P2/P3、不新增ignore/exit-zero；新类型契约已对齐，完整静态命令不报全绿。完整诊断保存于本轮私有static-final-dirty.json，关闭前提升摘要。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Static debt is not an individual proven behavior defect; no critical Ruff classes/new type difference identified.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "清理记录所涉部署代码及类型流；不把全仓其他历史债务宣称已清零", "verification": "同上；Codex/OMP 接线回归、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-185"></a>
### 185. P1-04-R4-REFRESH-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R4-REFRESH-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104FinalGuardReview/native-source-audit"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"mcp/tools.js freshness tool dispatch + sbtd_graft_entry.py:managed_environment"</code> |
| `title` | <code>"MCP查询可在守卫后重建并消费新指针"</code> |
| `problem` | <code>"工具调用先ensureFreshGraph再执行；普通源码相对import经verbatim string_fragment和未解析相对spec保留span，同一请求可读仓外路径。启动前校验不覆盖这次原生重建。"</code> |
| `resolution` | <code>"managed child无条件GRAFT_NO_REFRESH=1，freshness读取已证明图；显式build仍是唯一原生重建入口。reviewer确认source关闭；JS stale-source initialize→find_all→find_code在路径label存在时无私有内容且项目树不变。"</code> |
| `evidence` | <code>["unit-report-codex-no-refresh-focused-clean-p1-04-codex-wiring-2026_09_19-17_57_25", "api-report-codex-no-refresh-js-sink-green-p1-04-codex-wiring-2026_09_19-18_05_04"]</code> |
| `failedRetained` | <code>["api-report-codex-no-refresh-js-sink-p1-04-codex-wiring-2026_09_19-18_03_32"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Managed children disable native refresh and explicit freshness reads validated graph only.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-186"></a>
### 186. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"evidence-correction"</code> |
| `task` | <code>"P1-04"</code> |
| `report` | <code>"api-report-codex-no-refresh-js-sink-p1-04-codex-wiring-2026_09_19-18_03_32"</code> |
| `status` | <code>"failed-retained"</code> |
| `decision` | <code>"第一轮精确JS fixture因断言同时禁止响应中的私有文件名label而失败；该label是目标路径说明，不等于私有内容泄露。断言改为只禁止PRIVATE SENTINEL，保留失败报告；下一轮才作为最终query证据。"</code> |

<a id="record-187"></a>
### 187. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory-disposition"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"corrected"</code> |
| `source` | <code>"Main"</code> |
| `source_commit` | <code>"747b27024556a1c284b955883f9635ec93e5a3f0"</code> |
| `title` | <code>"区分GitHub规则状态与已执行独立复核"</code> |
| `problem` | <code>"此前仅依据REVIEW_REQUIRED将已获授权的admin合并写成未review违约，该归因不成立。"</code> |
| `decision` | <code>"合并前三路源码复核及后续修正复核确已执行，用户已授权--admin；GitHub REVIEW_REQUIRED不等于该复核缺失。不要求用户接受虚构违约。后置review实际发现4项P1，因此任务真实原因是需补救PR，不能done或推进后续。Release gate和最终证据/清理仍须完成。"</code> |
| `evidence` | <code>["PR #41 head 11b00a3a680def23aba3f14958194537203d18ac", "merge 747b27024556a1c284b955883f9635ec93e5a3f0", "P104FinalGuardReview/P104FinalProducerReview/P104FinalDocsLeanReview", "P104PostMergeGuardReview"]</code> |

<a id="record-188"></a>
### 188. P1-04-R5-LIVE-GRAPH-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R5-LIVE-GRAPH-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104PostMergeGuardReview/P104HardeningProtocolReview"</code> |
| `location` | <code>"graft-hook-entry.mjs:94-99"</code> |
| `title` | <code>"Stop新生成图可被长连接绕过一次性守卫读取"</code> |
| `problem` | <code>"MCP按mtime重载；Stop build后旧消费者不重新校验。"</code> |
| `resolution` | <code>"在每个可执行MCP请求前重新校验当前图，no-refresh保留。真实native baseline返回仓外合成secret，补救后拒绝且不返回secret；独立复核关闭。"</code> |
| `evidence` | <code>["api-report-codex-live-consumer-baseline-red-p1-04-codex-runtime-hardening-2026_09_19-19_25_39", "api-report-codex-live-consumer-green-p1-04-codex-runtime-hardening-2026_09_19-19_40_21"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Every MCP request revalidates current graph.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-189"></a>
### 189. P1-04-R5-LIVE-GRAPH-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R5-LIVE-GRAPH-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104PostMergeGuardReview/P104HardeningProtocolReview"</code> |
| `location` | <code>"sbtd_codex_deployment.py:build_project_graph"</code> |
| `title` | <code>"失败部署生成图仍可能被既存消费者读取"</code> |
| `problem` | <code>"build先写后guard拒绝，既存MCP仍可读取拒绝图。"</code> |
| `resolution` | <code>"与LIVE-GRAPH-001统一在实际消费者请求边界修复；原件和失败结果保留，未证明图不转发到native。native部署路径红绿与独立复核关闭。"</code> |
| `evidence` | <code>["api-report-codex-live-consumer-baseline-red-p1-04-codex-runtime-hardening-2026_09_19-19_25_39", "api-report-codex-live-consumer-green-p1-04-codex-runtime-hardening-2026_09_19-19_40_21"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Same per-request guard prevents reading failed/unsafe deployment graph.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-190"></a>
### 190. P1-04-R5-PYTHON-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R5-PYTHON-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104PostMergeGuardReview/P104HardeningCommandReview"</code> |
| `location` | <code>"sbtd_codex_wiring.py:generated argv"</code> |
| `title` | <code>"Python启动环境注入先于守卫"</code> |
| `problem` | <code>"PYTHONHOME/PYTHONPATH/user-site在守卫前生效。"</code> |
| `resolution` | <code>"MCP/hook统一-E -s先隔离启动，保留受信邻接模块；实际生成命令在污染环境下启动成功且无marker注入，合并baseline负例失败。独立复核关闭。"</code> |
| `evidence` | <code>["unit-report-codex-python-startup-baseline-red-p1-04-codex-runtime-hardening-2026_09_19-19_52_03", "unit-report-codex-hardening-ownership-shutdown-green-p1-04-codex-runtime-hardening-2026_09_19-19_48_32"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Owned argv uses -E -s and managed env scrubs startup injection.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-191"></a>
### 191. P1-04-R5-HOOK-SCOPE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R5-HOOK-SCOPE-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104PostMergeGuardReview/P104HardeningProtocolReview"</code> |
| `location` | <code>"sbtd_graft_entry.py:_run_hook"</code> |
| `title` | <code>"失效仓根导致无关项目全局hook失败"</code> |
| `problem` | <code>"绑定根验证先于事件分流，删除仓根影响无关项目。"</code> |
| `resolution` | <code>"先解析payload和绝对绑定范围，无关事件不访问缺失根/runtime；相关事件保留严格校验。真实CLI和永久边界回归通过，独立复核关闭。"</code> |
| `evidence` | <code>["api-report-codex-hook-stale-root-p1-04-codex-runtime-hardening-2026_09_19-19_40_21"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Payload cwd classified before bound-root validation; unrelated events no-op after root deletion.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-192"></a>
### 192. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"evidence-correction"</code> |
| `task` | <code>"P1-04"</code> |
| `report` | <code>"unit-report-codex-python-startup-red-p1-04-codex-runtime-hardening-2026_09_19-19_28_32"</code> |
| `status` | <code>"misnamed-not-red"</code> |
| `decision` | <code>"该报告运行于修复后的文件，suite标签中的red是调用错误；它仅证明10项测试通过，不证明旧argv失败。worker的私有throwaway probes不能作为仓库报告，最终真实回归必须重跑。"</code> |

<a id="record-193"></a>
### 193. P1-04-R6-OLD-HOOK-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R6-OLD-HOOK-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104HardeningCommandReview"</code> |
| `title` | <code>"旧未隔离受管hook被误当foreign而并存"</code> |
| `problem` | <code>"新增-E -s后解析器只识别新形状，旧同root/event受管命令继续执行并被追加新命令掩盖。"</code> |
| `resolution` | <code>"仅识别精确前身以便拒绝授权重配；同root/event返回ownership-conflict，不执行或保留为兼容入口，真正foreign root保留。独立复核关闭。"</code> |
| `evidence` | <code>["unit-report-codex-old-hook-ownership-red-p1-04-codex-runtime-hardening-2026_09_19-19_47_21", "unit-report-codex-hardening-ownership-shutdown-green-p1-04-codex-runtime-hardening-2026_09_19-19_48_32"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Exact legacy owned commands become ownership conflicts; foreign roots remain foreign.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-194"></a>
### 194. P1-04-R6-STDIO-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R6-STDIO-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"Main/P104HardeningProtocolReview"</code> |
| `title` | <code>"native先退出使阻塞标准输入线程在Python收尾崩溃"</code> |
| `problem` | <code>"host保持stdin打开而native exit7时，守卫SIGABRT -6；后台标准BufferedReader持锁，解释器无法完成收尾。stdout5秒超时也可能截断慢读者完整响应。"</code> |
| `resolution` | <code>"输入使用独立dup fd的BufferedReader，输出串行raw fd写；按pipe backpressure等待输出，不用固定时间截断。真实进程退出和1MiB慢读响应回归通过，独立源码复核关闭。"</code> |
| `evidence` | <code>["unit-report-codex-native-exit-diagnostic-red-p1-04-codex-runtime-hardening-2026_09_19-19_44_06", "unit-report-codex-native-exit-green-p1-04-codex-runtime-hardening-2026_09_19-19_46_27", "unit-report-codex-hardening-ownership-shutdown-green-p1-04-codex-runtime-hardening-2026_09_19-19_48_32"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Independent descriptors and backpressure-aware drain prevent deadlock/truncation.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-195"></a>
### 195. P1-04-R6-STDIO-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R6-STDIO-002"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P104HardeningProtocolReview"</code> |
| `title` | <code>"native关闭输入时EPIPE被映射为守卫拒绝2"</code> |
| `problem` | <code>"已验证请求转发write/flush期间native退出，广义OSError处理追加refusal_exit=2，掩盖真实退出码；不是剩余守卫绕过。"</code> |
| `decision` | <code>"D-IMP-13原级延期，不在本轮扩大错误码修复。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"BrokenPipe/EPIPE from a verified native child closing stdin no longer records launcher refusal 2 or terminates that child; normal child exit propagation remains authoritative."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "BrokenPipe/EPIPE from a verified native child closing stdin no longer records launcher refusal 2 or terminates that child; normal child exit propagation remains authoritative.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-196"></a>
### 196. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory-disposition"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"dismissed"</code> |
| `title` | <code>"无id工具通知绕过与id反射的安全级别"</code> |
| `decision` | <code>"固定native server.js:123-125明确对无id tools/call直接返回，故不会未校验调工具；调用者提供id反射是协议相关数据，不是向其泄露未知秘密。独立security reviewer核对，无P1；不凭通用JSON-RPC假设修改固定消费者语义。"</code> |

<a id="record-197"></a>
### 197. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"process-observation"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"recorded"</code> |
| `title` | <code>"writer越界执行局部验证不计gate"</code> |
| `decision` | <code>"P104PythonStartupFix与P104LiveConsumerFix违反skip-all-validation指令自报局部运行；不采纳为正式证明。Main已重新执行原生long-consumer红绿、startup/事件/协议/退出用例并保留报告。"</code> |

<a id="record-198"></a>
### 198. P1-04

| 字段 | 内容 |
|---|---|
| `type` | <code>"process-observation"</code> |
| `task` | <code>"P1-04"</code> |
| `status` | <code>"disclosed"</code> |
| `source` | <code>"P104PythonStartupFix"</code> |
| `title` | <code>"worker未经允许在真实HOME写入uv缓存"</code> |
| `problem` | <code>"worker自报执行未隔离HOME/UV_CACHE_DIR的uv run --with tomlkit --no-project，写入~/.cache/uv的wheel和ephemeral环境；还产生仓库__pycache__。"</code> |
| `decision` | <code>"已向用户披露，不采纳worker运行作为gate，不擅删共享cache；未改全局site-packages/CODEX_HOME/信任配置。Main独立原生验证为唯一验收。后续精确安装不再假定源目录没有bytecode；只清理明确本任务创建的字节码。"</code> |

<a id="record-199"></a>
### 199. P1-04-R7-EVIDENCE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-04-R7-EVIDENCE-001"</code> |
| `task` | <code>"P1-04"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `category` | <code>"evidence-provenance"</code> |
| `source` | <code>"P104StatusEvidenceReview"</code> |
| `location` | <code>"docs/prd/sbtd-workflow-v2-codex-wiring-runtime.md:77"</code> |
| `title` | <code>"清理后运行输入来源证明保留不足"</code> |
| `problem` | <code>"目录名称不能证明fresh环境、完整archive或CLI版本；初始closure仅一份未标注来源manifest。"</code> |
| `resolution` | <code>"从Main内核仍保留的原始archive bytes/副本hash/pip和npm进程结果补存独立sourceArchive与installedCopy manifests及真实创建/安装输出；Codex限定为固定版本npm安装，binaryDigest=null，不补造二进制哈希。独立状态证据复核关闭。"</code> |
| `evidence` | <code>["unit-report-codex-hardening-pr-head-full-p1-04-codex-runtime-hardening-2026_09_19-20_11_54.closure.json"]</code> |
| `productCodeChanged` | <code>false</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Closure evidence includes sourceArchive/installedCopy manifests and process outputs without invented digest.", "evidence": ["docs/prd/sbtd-workflow-v2-codex-wiring-runtime.md", "sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py", "tests/test_sbtd_codex_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-200"></a>
### 200. P1-05-R1-SOURCE-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-05-R1-SOURCE-001"</code> |
| `task` | <code>"P1-05"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"P105IndependentReview"</code> |
| `source_commit` | <code>"e734775559e38461f518712e4e209dac43da9b04"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"OMP来源继承、等价与部署关闭条件不足"</code> |
| `problem` | <code>"首轮review发现分析值可注入native选项、provider disable未覆盖全部级别、active .mcp.json及denylist缺失、等价判断不完整、active/inherited managed冲突可绕过、Codex/OMP manifest可混杂、Claude fallback提前停止等。"</code> |
| `resolution` | <code>"逐项红绿修复：闭集argv拒绝option形值；provider/native禁用及动态overlay/.env/legacy/project设置阻断；读取active alternate与Claude fallback；完整连接等价、server/extension denylist和managed冲突；Codex manifest拒绝OMP操作；实际OMP18.2.5八场景SDK query复核通过。"</code> |
| `evidence` | <code>["unit-report-exact-reviewed-p1-05-omp-wiring-p1-05-omp-wiring-2026_09_20-08_03_26"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "OMP rejects dynamic overlays/providers/denylist settings, reads active/Claude fallback, and uses complete equivalence.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py", "tests/test_sbtd_omp_wiring.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-201"></a>
### 201. P1-05-R2-TRANSPORT-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-05-R2-TRANSPORT-001"</code> |
| `task` | <code>"P1-05"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"BumpyMongoose"</code> |
| `source_commit` | <code>"3e7bd8fb06bd30800de31e499a88ddc48b6fff81"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_omp_sources.py:201-202"</code> |
| `title` | <code>"JSON继承源注入type=stdio遮蔽transport字段"</code> |
| `problem` | <code>"继承JSON记录默认注入type，若host读取transport别名会导致等价误判。"</code> |
| `resolution` | <code>"按固定OMP18.2.5源码确认JSON parser只读type、不读transport；删除注入和Python侧别名，增加transport键不改变结果的回归。"</code> |
| `evidence` | <code>["unit-report-exact-final-review-p1-05-omp-wiring-p1-05-omp-wiring-2026_09_20-08_21_01"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "No synthetic type injection masks transport; parser follows pinned type contract.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_omp_sources.py", "sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py", "tests/test_sbtd_omp_wiring.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-202"></a>
### 202. P1-05-R3-PROJECT-DENYLIST-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-05-R3-PROJECT-DENYLIST-001"</code> |
| `task` | <code>"P1-05"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"ExactChipmunk"</code> |
| `source_commit` | <code>"c7531d941572a0380a015d7b2c2398ba272a0017"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_omp_sources.py:_guard_dynamic_sources"</code> |
| `title` | <code>"project/Claude settings的disabledExtensions绕过阻断"</code> |
| `problem` | <code>"用户agent settings以外的项目或Claude settings可删除生成MCP identity，部署仍报成功。"</code> |
| `resolution` | <code>"native project config/settings、project Claude settings及启用Claude user settings中含disabledExtensions均fail-closed并纳入只读快照；红绿回归通过。"</code> |
| `evidence` | <code>["unit-report-exact-final2-p1-05-omp-wiring-p1-05-omp-wiring-2026_09_20-08_48_41"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Project/Claude disabledExtensions/provider settings fail closed in dynamic-source guards.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_omp_sources.py", "sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py", "tests/test_sbtd_omp_wiring.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-203"></a>
### 203. P1-05-R4-EQUIV-DENYLIST-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-05-R4-EQUIV-DENYLIST-001"</code> |
| `task` | <code>"P1-05"</code> |
| `severity` | <code>"P1"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"ImaginativeHyena"</code> |
| `source_commit` | <code>"d2810dcc624ba1c381ef58b3f99b5051ebc600dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py:analyze_omp_configuration"</code> |
| `title` | <code>"非期望名称的denylist可压制等价匹配"</code> |
| `problem` | <code>"disabledServers/disabledExtensions只检查生成名，foreign同名连接被host禁用却仍被当作已接线。"</code> |
| `resolution` | <code>"denylist在active/inherited匹配前生效；managed denylist冲突，普通foreign被禁则不匹配并写入受管目标。VoluntaryCrayfish复核NO P0/P1 REMAINING。"</code> |
| `evidence` | <code>["unit-report-exact-denylist-p1-05-omp-wiring-p1-05-omp-wiring-2026_09_20-09_14_16"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Denylist precedes equivalence; managed conflict blocks and disabled foreign entry does not suppress managed write.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py", "tests/test_sbtd_omp_wiring.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-204"></a>
### 204. P1-05-ADVISOR-DEPLOYMENT-NULL

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory-disposition"</code> |
| `id` | <code>"P1-05-ADVISOR-DEPLOYMENT-NULL"</code> |
| `task` | <code>"P1-05"</code> |
| `status` | <code>"accepted"</code> |
| `source` | <code>"Main-advisor"</code> |
| `title` | <code>"缺失deployment不得暗指旧行为"</code> |
| `decision` | <code>"schema要求deployment键存在且可为null；生产端、fixture和测试同批迁移，缺失拒绝。"</code> |

<a id="record-205"></a>
### 205. P1-05-ADVISOR-SCHEMA-BRACES

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory-disposition"</code> |
| `id` | <code>"P1-05-ADVISOR-SCHEMA-BRACES"</code> |
| `task` | <code>"P1-05"</code> |
| `status` | <code>"corrected"</code> |
| `source` | <code>"Main-advisor"</code> |
| `title` | <code>"manifest schema properties块括号错误"</code> |
| `decision` | <code>"按提示恢复tool_versions闭合、deployment属性和properties闭合，并以契约测试复核。"</code> |

<a id="record-206"></a>
### 206. P1-05-ADVISOR-MANIFEST-OPTION

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory-disposition"</code> |
| `id` | <code>"P1-05-ADVISOR-MANIFEST-OPTION"</code> |
| `task` | <code>"P1-05"</code> |
| `status` | <code>"corrected"</code> |
| `source` | <code>"Main-advisor"</code> |
| `title` | <code>"deployment_platform插入误删migration manifest选项"</code> |
| `decision` | <code>"恢复_MIGRATION_VALUE_OPTIONS中的manifest并保留allowed-set单一注册，参数测试通过。"</code> |

<a id="record-207"></a>
### 207. P1-05-ADVISOR-RENDER-DENYLIST

| 字段 | 内容 |
|---|---|
| `type` | <code>"advisory-disposition"</code> |
| `id` | <code>"P1-05-ADVISOR-RENDER-DENYLIST"</code> |
| `task` | <code>"P1-05"</code> |
| `status` | <code>"corrected"</code> |
| `source` | <code>"Main-advisor"</code> |
| `title` | <code>"render未传递disabledExtensions"</code> |
| `decision` | <code>"render_configuration把discovery的disabled_extensions传入analysis，新增render红绿回归；premature commit已amend，不推送缺口提交。"</code> |

<a id="record-208"></a>
### 208. P1-05-R4-RESIDUAL-P3

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-05-R4-RESIDUAL-P3"</code> |
| `task` | <code>"P1-05"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"VoluntaryCrayfish"</code> |
| `source_commit` | <code>"d2810dcc624ba1c381ef58b3f99b5051ebc600dd"</code> |
| `source_revision` | <code>"dirty"</code> |
| `title` | <code>"OMP接线的低风险残余观察"</code> |
| `problem` | <code>"剩余项包括candidate内可选denylist复查、无关畸形entry的保守fail-closed、Claude cwd/enabled建模方向、claude-plugins源未建模、测试名timeout与EXTRA不符、OMP human输出仍沿用Codex措辞、OMP full部署保留codex-home共享root以承载全局模板。"</code> |
| `decision` | <code>"均不改变固定host下的写入安全或证据真伪；按原级延期规则记录，十项P1门评估时统一复核。"</code> |
| `locations` | <code>["sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py:omp_mcp_candidate", "sbtd-workflow-onboard/scripts/sbtd_omp_sources.py:discover_omp_sources", "sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py:attach_deployment", "sbtd-workflow-onboard/scripts/onboard.py:run output", "tests/test_sbtd_omp_wiring.py:test_inherited_timeout_difference_does_not_suppress_native_write"]</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "逐子项评估：human 输出 Codex wiring 已改为 Host wiring；OMP 全局模板所需 codex-home 为既有正常初始化契约；无关畸形配置继续保守拒绝；candidate denylist 重复复查、Claude cwd/enabled/plugin 来源建模及旧测试命名未证明当前固定 host 的安全/证据缺陷，保留 P3，不声称全部子项已修。", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py", "tests/test_sbtd_omp_wiring.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "candidate 复验 denylist；保留明确 malformed fail-closed；实现 forced-enabled/cwd 对等；补 plugin 默认、profile、XDG、override 与项目来源拒绝；修正测试名", "verification": "OMP 来源与不写入回归、独立复核、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-209"></a>
### 209. P1-06

| 字段 | 内容 |
|---|---|
| `type` | <code>"review-closure"</code> |
| `task` | <code>"P1-06"</code> |
| `source` | <code>"VocalMonkey"</code> |
| `source_commit` | <code>"3316c08f35718c2e591fe7574fc3b2b979a10659"</code> |
| `source_revision` | <code>"exact"</code> |
| `result` | <code>"NO P0/P1 REMAINING"</code> |
| `evidence` | <code>["unit-report-exact-p1-06-worktree-isolation-p1-06-worktree-graft-isolation-2026_09_20-10_07_51", "api-report-native-worktree-isolation-p1-06-head-p1-06-worktree-graft-isolation-2026_09_20-10_09_08"]</code> |
| `decision` | <code>"独立review核对嵌套根守卫、runtime前顺序、迁移manifest路径、Codex/OMP两仓和linked worktree测试真实性；无P0/P1，低级别项单独记录。"</code> |

<a id="record-210"></a>
### 210. P1-06-R1-CASE-ALIAS-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-06-R1-CASE-ALIAS-001"</code> |
| `task` | <code>"P1-06"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"VocalMonkey"</code> |
| `source_commit` | <code>"3316c08f35718c2e591fe7574fc3b2b979a10659"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py:_validate_selected_root_batch; onboard.py:resolve_project_roots"</code> |
| `title` | <code>"大小写别名路径不会被识别为同一仓库"</code> |
| `problem` | <code>"路径经resolve后按词法比较；macOS APFS/Windows大小写不敏感路径别名可能重复接线同一物理仓库。影响是同仓重复配置，不是跨仓污染。"</code> |
| `decision` | <code>"原级延期；后续可在路径规范层统一normcase/samefile，十项评估时复核。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Selected-root batch validation rejects samefile physical aliases while retaining distinct linked-worktree directories."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Selected-root batch validation rejects samefile physical aliases while retaining distinct linked-worktree directories.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "tests/test_sbtd_graft_isolation.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-211"></a>
### 211. P1-06-R1-TEST-STRENGTH-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-06-R1-TEST-STRENGTH-001"</code> |
| `task` | <code>"P1-06"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"VocalMonkey"</code> |
| `source_commit` | <code>"3316c08f35718c2e591fe7574fc3b2b979a10659"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"tests/test_sbtd_graft_isolation.py:test_linked_worktrees_on_different_branches_are_distinct_selected_roots"</code> |
| `title` | <code>"linked worktree测试未逐项断言MCP root/cwd"</code> |
| `problem` | <code>"该测试证明两个不同branch可接线，但只检查server数量；两仓Codex/OMP测试已覆盖相同绑定形状。"</code> |
| `decision` | <code>"作为强度增强延期；不冒充缺失安全洞，十项评估时可补断言。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"Linked-worktree regression now asserts each generated MCP server has matching per-worktree cwd and --root."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "Linked-worktree regression now asserts each generated MCP server has matching per-worktree cwd and --root.", "evidence": ["tests/test_sbtd_graft_isolation.py", "sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-212"></a>
### 212. P1-06-R1-WORDING-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-06-R1-WORDING-001"</code> |
| `task` | <code>"P1-06"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"VocalMonkey"</code> |
| `source_commit` | <code>"3316c08f35718c2e591fe7574fc3b2b979a10659"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"README.md/README.html/REFERENCE.md/CHANGELOG.md"</code> |
| `title` | <code>"“任何runtime探测前”措辞可能覆盖普通只读环境检测"</code> |
| `problem` | <code>"check模式的只读check_graft环境检测先于plan；该检测不访问所选根也不写入，守卫实际先于固定runtime验证和root-scoped probe。"</code> |
| `resolution` | <code>"公开文档改为固定runtime验证和任何root-scoped probe之前；不改变代码路径。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "fixed", "disposition": "already-fixed", "decision": "Docs now limit claim to fixed-runtime validation/root-scoped probes, matching actual ordering.", "evidence": ["README.md", "README.html", "sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py", "tests/test_sbtd_graft_isolation.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |

<a id="record-213"></a>
### 213. P1-12-R2-VERIFY-009

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-VERIFY-009"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"EvidenceBoundaryReview"</code> |
| `source_commit` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:316-321"</code> |
| `title` | <code>"Auxiliary non-API reports are not content-parsed"</code> |
| `problem` | <code>"VERIFY-005 修复后，非 API 辅助报告只校验 status、sha256 和 bound summary，不解析其文件内容或 provenance。"</code> |
| `impact` | <code>"辅助报告内容本身不构成 smoke 证据；若未来消费者把辅助报告当作额外证明，需要更深校验。"</code> |
| `recommendation` | <code>"后续评估是否为非 API 报告定义类型化内容校验；当前 acceptance 仍依赖至少一个 genuine API smoke。"</code> |
| `decision` | <code>"本轮授权边界仅要求辅助报告不误触发 genuine-mode gate；记录延期。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Auxiliary reports are integrity-bound but intentionally not acceptance-bearing; typed parsing would be a new evidence contract.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "辅助报告要求 v2 JUnit／Playwright 类型化内容、case binding 及仓库/ref/OID 一致；不升级为 API smoke；保持 OID 大小写等价", "verification": "forged/stale/foreign-ref/foreign-repository 拒绝、mixed-case 正向、mock-backed auxiliary 正向", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-214"></a>
### 214. P1-01-R13-P2-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R13-P2-001"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"EvidenceBoundaryReview"</code> |
| `source_commit` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:1103-1110"</code> |
| `title` | <code>"Recovery report references are outside the nesting guard"</code> |
| `problem` | <code>"本轮按授权只覆盖 deployment_evidence 的跨项目 report_refs；recovery plan/receipt 与 runtime_readiness 的 report_refs 仍允许父子路径。"</code> |
| `impact` | <code>"若恢复证据未来使用同一路径树，仍可能声明无法同时存在的报告文件。"</code> |
| `recommendation` | <code>"后续评估是否把同一嵌套守卫推广到 recovery/runtime readiness report_refs，并补对应红测。"</code> |
| `decision` | <code>"P1-01-R11-P2-001 原文限定 deployment report_refs；不越权扩大本轮修复。"</code> |
| `verified_fixed_by` | <code>"7f64a281fee5af28aa3dede02fe56992ec5570b7"</code> |
| `resolution` | <code>"复核发现基线已包含修复，不重复实现。Current recovery receipt validator rejects report/evidence path ancestry at lines 1496-1509 and protected output overlap at 2583-2614."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "already-fixed", "decision": "Current recovery receipt validator rejects report/evidence path ancestry at lines 1496-1509 and protected output overlap at 2583-2614.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-215"></a>
### 215. P1-01-R13-P2-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-01-R13-P2-002"</code> |
| `task` | <code>"P1-01"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"EvidenceBoundaryReview"</code> |
| `source_commit` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/onboard_contracts.py:415-416"</code> |
| `title` | <code>"Path containment remains lexical only"</code> |
| `problem` | <code>"_path_contains 使用 Path.is_relative_to，不解析 symlink，也不处理大小写不敏感文件系统的别名。"</code> |
| `impact` | <code>"通过 symlink 或大小写变体绕过词法重叠检查的路径不会被这些 guard 捕获；该行为与既有调用一致。"</code> |
| `recommendation` | <code>"如后续需要防御文件系统别名，应单独设计 canonicalization 策略并覆盖 macOS/Windows 语义。"</code> |
| `decision` | <code>"既有词法语义未由本轮授权改变；记录延期。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "Lexical containment is documented contract semantics; symlink/case canonicalization needs cross-platform filesystem policy and runtime ownership.", "evidence": ["sbtd-workflow-onboard/scripts/onboard_contracts.py", "tests/test_onboard_contracts.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "路径包含／重叠检查识别可证明的 symlink 与文件系统大小写别名；同资源同状态报告仍可跨项目共享", "verification": "公共契约 alias 拒绝、共享报告正向／冲突反向、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-216"></a>
### 216. P1-12-R2-VERIFY-010

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-12-R2-VERIFY-010"</code> |
| `task` | <code>"P1-12"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"dismissed"</code> |
| `source` | <code>"EvidenceBoundaryReview"</code> |
| `source_commit` | <code>"0ab13a96ce392f89580c1bd534db6d1b7cca40f5"</code> |
| `source_revision` | <code>"exact"</code> |
| `location` | <code>"sbtd-workflow-onboard/scripts/sbtd_migration_verify.py:308-315"</code> |
| `title` | <code>"Historical evidence without bound summaries now fails closed"</code> |
| `problem` | <code>"VERIFY-006 要求 summaryMd 必须是 checksum-bound report_refs；此前未声明 summary 的已封存 deployment evidence 重新验证会被拒绝。"</code> |
| `impact` | <code>"这是有意 fail-closed 兼容性变化；旧证据不能继续冒充正式 report/summary 对。"</code> |
| `recommendation` | <code>"若必须复核历史证据，使用原历史版本工具或显式生成迁移证明；不要放宽当前绑定。"</code> |
| `decision` | <code>"按本轮授权修复记录兼容性边界；不自动迁移历史证据。"</code> |
| `resolution` | <code>"Fail-closed rejection of historical evidence lacking bound summaries is intentional compatibility policy, not a current defect."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "dismissed", "decision": "Fail-closed rejection of historical evidence lacking bound summaries is intentional compatibility policy, not a current defect.", "evidence": ["sbtd-workflow-onboard/scripts/sbtd_migration_verify.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration_legacy.py", "tests/test_sbtd_migration_plan.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "dismissed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-217"></a>
### 217. P1-13-R1-SHARED-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-13-R1-SHARED-001"</code> |
| `task` | <code>"P1-13"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"ExpensiveFlea"</code> |
| `source_commit` | <code>"aa9a2c690d2928c1b1d9b16a3474558fa3ea2180"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"tests/test_sbtd_migration_cleanup.py:33-47; sbtd-workflow-onboard/scripts/sbtd_migration_plan.py:1670-1701"</code> |
| `title` | <code>"Shared cleanup lacks runtime coverage"</code> |
| `problem` | <code>"cleanup fixture uses an empty isolated AGENT_SKILLS_DIR, so planner emits no shared cleanup operations and shared_cleanup_candidates remains empty."</code> |
| `impact` | <code>"The shared_results payload, shared_operation_ids aggregation, and multi-dependent shared-failure propagation are not exercised; the cleanup execution path itself is the same code as the covered private cleanup and _groups enforces one execution per resource_id."</code> |
| `recommendation` | <code>"Add a fixture containing byte-exact pinned legacy Skill directories in the isolated AGENT_SKILLS_DIR, then assert nonempty shared_results, consistent shared_operation_ids across dependent projects, and shared failure propagating to every dependent project."</code> |
| `decision` | <code>"依 D-IMP-13 原级延期；本轮 private cleanup 已证明执行路径，shared 差异限聚合/报告层。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"补共享 Skill 双项目清理成功/失败运行覆盖，并修复 cleanup-only 资源首次删除前缺原件备份的真实缺陷。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "补共享 Skill 双项目清理成功/失败运行覆盖，并修复 cleanup-only 资源首次删除前缺原件备份的真实缺陷。", "evidence": ["tests/test_sbtd_migration_cleanup.py", "sbtd-workflow-onboard/scripts/sbtd_migration_plan.py", "sbtd-workflow-onboard/scripts/sbtd_migration.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-218"></a>
### 218. P1-20-R1-SHARED-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-20-R1-SHARED-001"</code> |
| `task` | <code>"P1-20"</code> |
| `severity` | <code>"P2"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"StandardOstrich"</code> |
| `source_commit` | <code>"09ce1c64892dec67cecd6d30485b72a57741bfce"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"tests/test_sbtd_recovery.py; sbtd-workflow-onboard/scripts/sbtd_recovery.py:222-231"</code> |
| `title` | <code>"Recovery shared-closure runtime fixture remains thin"</code> |
| `problem` | <code>"The current isolated migration fixture has no byte-exact pinned legacy Skill directories, so shared recovery operations and dependent-project closure rejection lack a direct runtime fixture."</code> |
| `impact` | <code>"Contract validators already fail incomplete shared closures and `_groups` prevents duplicate execution; the remaining risk is limited to runtime aggregation/report coverage regressions."</code> |
| `recommendation` | <code>"Add a fixture with byte-exact pinned legacy Skill directories in isolated AGENT_SKILLS_DIR, then assert a subset plan is blocked and full-scope recovery preserves shared dependent closure."</code> |
| `decision` | <code>"依 D-IMP-13 原级延期；contracts 层已有闭包 fail-closed 回归，后续补真实 pinned fixture。"</code> |
| `verified_fixed_by` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `resolution` | <code>"补共享恢复运行覆盖：子集拒绝且零写入，完整依赖闭包只生成一次共享恢复步骤。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "fixed-now", "decision": "补共享恢复运行覆盖：子集拒绝且零写入，完整依赖闭包只生成一次共享恢复步骤。", "evidence": ["tests/test_sbtd_recovery.py", "sbtd-workflow-onboard/scripts/sbtd_recovery.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `status_history` | <code>[{"at": "2026-09-21T15:30:15.134689+08:00", "from": "deferred", "to": "fixed", "reason": "用户授权的当前代码全量评估与验证；原级别/原文保留。", "evidence": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb"}]</code> |

<a id="record-219"></a>
### 219. P1-08-R1-PS-001

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-08-R1-PS-001"</code> |
| `task` | <code>"P1-08"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"YoungErmine"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"install.ps1:Invoke-WorkflowMode"</code> |
| `title` | <code>"PowerShell --yes:$true form is swallowed by parameter binding"</code> |
| `problem` | <code>"In workflow forwarding mode, `--yes:$true` binds to the installer switch without adding `--yes` to forwarded arguments; only bare `--yes` is forwarded."</code> |
| `impact` | <code>"A rare PowerShell spelling silently drops migration apply consent, leaving the Python handler blocked instead of producing an argparse error."</code> |
| `recommendation` | <code>"If needed later, detect `$PSBoundParameters` spelling metadata or document that only bare `--yes` is supported on the forwarding path."</code> |
| `decision` | <code>"依 D-IMP-13 原级延期；当前 documented forwarding contract uses bare --yes and has real pwsh coverage."</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "PowerShell --yes:$true is wrapper parity outside documented bare -Yes/--yes forwarding and safely remains unconsented.", "evidence": ["install.ps1", "tests/test_install_sh_agent_cli_flow.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "从实际脚本 switch 值转发 true，false 不授权；避免函数内 PSBoundParameters 丢失脚本绑定", "verification": "真实 pwsh 绑定及实际 migration handler：false blocked/2、true already-complete/0", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-220"></a>
### 220. P1-08-R1-PS-002

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-08-R1-PS-002"</code> |
| `task` | <code>"P1-08"</code> |
| `severity` | <code>"P3"</code> |
| `status` | <code>"fixed"</code> |
| `source` | <code>"YoungErmine"</code> |
| `source_revision` | <code>"dirty"</code> |
| `location` | <code>"install.ps1:WorkflowMode; install.sh:forward_workflow_mode"</code> |
| `title` | <code>"PowerShell accepts uppercase workflow modes while Bash requires lowercase"</code> |
| `problem` | <code>"PowerShell normalizes `-WorkflowMode MIGRATION` to `migration`; Bash preserves the exact token and dies before Python."</code> |
| `impact` | <code>"Both fail or succeed safely; the only difference is where case errors are rejected and how diagnostics read."</code> |
| `recommendation` | <code>"If strict parity is desired later, align Bash or PowerShell mode normalization and add a shared contract test."</code> |
| `decision` | <code>"依 D-IMP-13 原级延期；不扩大本轮转发修复。"</code> |
| `current_code_review` | <code>{"reviewed_at": "2026-09-21T15:30:15.134689+08:00", "source_commit": "89152dfdfa895266979f7bb58b68aff3bbe5cdcb", "previous_status": "deferred", "disposition": "deferred", "decision": "PowerShell normalizes mode case while Bash rejects uppercase; both safely reject or execute and this is diagnostic parity only.", "evidence": ["install.sh", "install.ps1", "tests/test_install_sh_agent_cli_flow.py"], "verification": "本批验证：1104 tests / 7 skip 全量通过；最后接线与文档补充后 105 项通过。该统计不冒充每条独立复现；最终 PR head 仍由三平台 CI 核验。"}</code> |
| `closure` | <code>{"previous_status": "deferred", "approved_at": "2026-09-21T21:46:29+08:00", "approval": "用户确认修复报告，授权先归档 findings，再创建 PR，补充 CI 通过后合并。", "resolution": "PowerShell 与 Bash 都拒绝大写 workflow mode", "verification": "两真实解释器拒绝路径、installer 子集、全量", "source_ref": "fix/deferred-p2-p3-findings", "source_base_commit": "903403bab2ec7987e2ed3f6bbc3f0cca47fc1db9", "source_revision": "dirty", "evidence_source": "developer-local", "full_validation": "1126 tests / 8 skip / OK；Ruff 23 文件、ty 11 生产模块通过；真实迁移/恢复及 PowerShell smoke 通过。", "report": "tests/unit/reports/unit-report-deferred-accepted-full-fix_deferred-p2-p3-findings-2026_09_21-20_28_49.md", "ci_boundary": "此处记录已确认的本地修复，不预填尚未运行的精确 PR SHA 多平台 CI；合并前另外核验。"}</code> |

<a id="record-221"></a>
### 221. findings-current-code-review

| 字段 | 内容 |
|---|---|
| `type` | <code>"review-closure"</code> |
| `task` | <code>"findings-current-code-review"</code> |
| `reviewed_at` | <code>"2026-09-21T15:30:15.134689+08:00"</code> |
| `source_commit` | <code>"89152dfdfa895266979f7bb58b68aff3bbe5cdcb"</code> |
| `base_commit` | <code>"7f64a281fee5af28aa3dede02fe56992ec5570b7"</code> |
| `scope` | <code>"全部199条finding及21条既有控制/历史记录；不只抽样deferred。"</code> |
| `findings` | <code>199</code> |
| `dispositions` | <code>{"already-fixed": 107, "fixed-now": 72, "deferred": 16, "dismissed": 3, "superseded": 1}</code> |
| `validation` | <code>{"full": "1104 tests / 7 skip / OK", "affected_final": "105 tests / OK", "native_cli": "隔离fixture下状态、A-B-A handoff、check-projects、cleanup/recovery通过；不是host proof", "native_graft": "本机 tree-sitter-kotlin 缺当前 Node ABI native build，正向探测blocked；未修改全局安装", "static": "Ruff/ty历史诊断仍在，基线对比无新增诊断类型/消息；未冒称全仓静态检查全绿"}</code> |
| `boundary` | <code>"PLAN-008仍为真实迁移前置缺口；本批不执行P1-16/P2/P3、不迁移真实项目、不sync、不发布、不处置备份。"</code> |

<a id="record-222"></a>
### 222. P1-22-TOCTOU-ROOT-MKDIR

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-22-TOCTOU-ROOT-MKDIR"</code> |
| `task` | <code>"P1-22"</code> |
| `severity` | <code>"P2/low"</code> |
| `status` | <code>"deferred"</code> |
| `source` | <code>"security-reviewer（P1-22 独立安全审查）"</code> |
| `source_revision` | <code>"5f26c52（rebase 后提交）"</code> |
| `location` | <code>"sbtd_graft_deployment.py:414-417; sbtd_migration.py:944-963; sbtd_migration_files.py:458-473"</code> |
| `title` | <code>"Residual TOCTOU: symlink-swap of shared root between lstat check and parent mkdir can create directories outside intended root"</code> |
| `problem` | <code>"一次性 `_lstat(_canonical(root))` 与 `_prepare_target_parents` 之间，同权限攻击者把根换成 symlink 可在其目标下建空 0700 目录；所有文件内容写入在提交时经 `_scope_root`/`_canonical` 重校验 fail-closed，影响上限为空目录。"</code> |
| `impact` | <code>"旧 `snapshot(root)` 全树遍历存在同一窗口且更长；本改动收窄而非扩大竞态。部署为单写入者用户发起操作，同权限攻击者前提超出本威胁模型。"</code> |
| `recommendation` | <code>"可选加固：`_prepare_target_parents` 入口对 scope 自身 lstat，或在其调用前以 `_scope_root` 等价重验；否则记录接受。"</code> |
| `decision` | <code>"依 D-IMP-13 原级延期；窗口较旧代码收窄且内容写入仍 fail-closed，不扩大本轮修复范围。"</code> |

<a id="record-223"></a>
### 223. P1-22-MKDIR-PARENTS-MODE

| 字段 | 内容 |
|---|---|
| `type` | <code>"finding"</code> |
| `id` | <code>"P1-22-MKDIR-PARENTS-MODE"</code> |
| `task` | <code>"P1-22"</code> |
| `severity` | <code>"informational"</code> |
| `status` | <code>"deferred"</code> |
| `source` | <code>"security-reviewer（P1-22 独立安全审查）"</code> |
| `source_revision` | <code>"5f26c52（rebase 后提交）"</code> |
| `location` | <code>"sbtd_graft_deployment.py:416"</code> |
| `title` | <code>"Intermediate parents of a missing shared root are created with umask-default permissions, not 0700"</code> |
| `problem` | <code>"`root.mkdir(parents=True, mode=0o700)` 的 mode 只作用于叶子；缺失的中间父级按进程 umask 创建。共享根父级通常是已存在的用户 home/config 目录，实际影响最小；私有备份 vault 由 require_private_directory 独立加固。"</code> |
| `impact` | <code>"与 mkdir -p 常见语义一致；非 vault 共享作用域，不降低私有区域保护。"</code> |
| `recommendation` | <code>"如需一致隐私，按 `_prepare_target_parents` 方式逐级 0700 创建；否则接受并记录。"</code> |
| `decision` | <code>"依 D-IMP-13 原级延期；共享根中间父级为既有用户目录的场景为主，不扩大本轮修复范围。"</code> |
