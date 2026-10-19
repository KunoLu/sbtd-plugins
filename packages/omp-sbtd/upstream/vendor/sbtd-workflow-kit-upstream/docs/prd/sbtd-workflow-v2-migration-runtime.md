# P1-12：批次迁移、隐私门与 verify 消费

## 基线与边界

- 基线main `794059214beed7970f37878cfbb098b832f95f63`；分支`p1-12-migration-runtime`。P1-19实现/状态PR #37/#38及清理已闭环；P1累计6项。累计10项闭环后暂停全findings评估并等待用户确认，不提前展开后续任务。
- 依据主PRD §10.2/11及AC-17/18/25/26/29/30/33/34/35/36相应子项；复用P1-01的严格codec/批准快照/资源模型、P1-17任务解析和P1-19身份链。
- 交付真实只读migration plan、确认apply、只读verify及共用不可变累计证据保存。部署producer归P1-04/05，cleanup归P1-13，恢复执行归P1-20；本项用冻结合法/非法证据fixture验证消费者，不冒充真实部署或恢复通过。不注册未实现的cleanup/recovery handler。
- 无真实项目迁移授权；全部开发验证使用明确私有fixture与隔离HOME。不执行Trellis、不建.feature、不同步生效路径/live automation、不更改ENTRYPOINT版本。

## 门禁与事实

- 未完整grill-with-docs：批准契约已定义数据、授权与阶段职责；技术格式以固定源码核对，不猜实际项目、平台或责任人。用户已预授权推荐方案的设计回答，不代替真实环境/权限确认。
- Legacy characterized：既有protocol/参数/任务/身份400 tests/22.016s通过；真实check-projects返回0/单JSON，尚未接入migration返回2/空stdout，隔离项目/vault/HOME快照不变。
- Refactoring proceed/normal：复用既有codec、TaskDocument、DeveloperStore及nofollow读取；只增加外部私有vault所需内聚文件操作，不重写原安装器或扩修延期P2。
- DDD confirmed：resource为物理资源、operation为阶段/selector操作；私有原件与批准共享投影分离；批准快照不认证操作者；plan/apply/部署/verify/cleanup/recovery职责分离。迁移是支撑子域，JSON/文件操作为通用能力，无新增业务术语冲突。
- DDIA confirmed：完整前置核对、单controller、每资源备份/写入、不可变自包含累计receipt；无跨资源事务、journal、锁或自动发现收据。漂移、未知来源或不可证明后态阻断，不推断成功/恢复可用。
- Release ready（仅P1-12合并范围）：适用原生验证、精确安装副本及独立复核已通过；完整Ruff非阻断样式项按用户D-IMP-13延期，Windows／真实host／完整v2发布不在本结论内。
- 报告：`unit-report-migration-baseline-p1-12-migration-runtime-2026_09_19-06_19_36`与API修改前刻画均为真实基线。sidecar初次遗漏status/mode，按真实schema补齐后通过；原运行结果不重写。后续runner必须沿用完整report-entry结构。

## 固定旧格式依据

- Trellis v0.6.17，commit `833a5846d18ad7a5ccd8c41c876d89cc936f5fd9`；不以浮动main推断旧格式。
- `packages/cli/src/templates/trellis/scripts/common/developer.py`真实写入`name=<name>\ninitialized_at=<datetime>\n`。迁移必须显式提取唯一合法name，保留完整旧原件；不能直接复制为当前身份，也不放宽普通DeveloperStore解析。
- `common/task_store.py`的旧task字段包括id/name/title/description/status、createdAt/completedAt、branch/base_branch、parent/children/subtasks及meta等；已知映射和未知内容均受同一隐私门。日期只有日粒度不能伪造带时区时刻；archive目录/归档动作不能单独证明完成。
- `common/active_task.py`的session JSON `current_task`是旧书签，不是task状态；多执行候选、关系冲突和未知结构必须显式阻断，不按mtime挑选。

## 实现决策

1. plan不生成候选，不写项目/HOME/vault。验证已授权私有准备的publication-decisions、真实源/候选/目标、必要输出与关系，并记录资源、所有权、共享闭包及原件保留位置。当前拒绝退休布局／显然私有内容；完整相对Markdown链接解析属于已记录延期P2，不能声称已全部核对。
2. 私有原件按manifest已有backup_root、项目/源路径和checksum确定唯一位置；真实完整目录摘要包含空目录，不沿用排除cache的Skill tree摘要，不创建额外索引或lifecycle文件。首次apply前完整验证；成功原件/资源跨重试不覆盖。
3. 实际旧身份格式需要同批codec+schema+runtime支持的闭集身份提取操作；只允许apply、当前项目缺失的.sbtd/developer、原样合法名字与真实旧源绑定。不引入任意文本/命令DSL；未知操作仍拒绝。
4. apply只迁移已批准候选、必要保护与受管旧路由停用；不安装新接线或运行smoke。每资源执行前复验；实际失败与累计已完成结果如实保存，保存失败不得冒称有可用receipt。
5. verify校验完整成功apply、部署对象ID/raw hash/scope/status、实际资源/批准投影/原件备份、当前报告与清理候选；合法fixture只证明消费者边界，不能证明真实host或部署发生。
6. 不从共享config选择当前host。实际平台/共享根/依赖以授权范围及可核对的具体生成资产盘点；不确定或未选依赖不猜测、不自动扩大范围。
7. Tests采用用户推荐方案预授权下的明确seams：真实onboard.py迁移CLI/阶段函数、文件原件保存、旧任务/身份投影验证。Main执行红/绿与最终验证，worker不得运行测试/格式/lint/build。

## 协作接口（本轮内部实现约定）

### 文件操作：scripts/sbtd_migration_files.py

复用`ContractError`与`open_regular_file`，错误不回显敏感原值。调用者负责manifest授权/操作归属，本模块负责真实类型、nofollow、scope、完整状态、私有存储和写入比较。

- `snapshot(path: Path) -> dict`：absent/file/directory的契约state；目录按PRD完整规范条目摘要；未知/链接/特殊类型不是absent。
- `read_file(path: Path, expected: Mapping | None = None) -> bytes`：从同次安全读取验证可选file state。
- `require_private_directory(path: Path, *, create: bool = False) -> Path`：只读检查或明确创建专用私有目录；不把Windows chmod当ACL证明。
- `backup_reference(source_ref: Mapping, destination: Path, *, private_root: Path) -> dict`：完整复制并回读，保留原件/空目录；目标已有且不可证明同一完整原件时拒绝，不能覆盖。
- `write_file(path: Path, content: bytes, expected: Mapping, *, scope: Path) -> None`：scope内、比较预期前态、同目录暂存及原子文件提交；原本absent使用无覆盖创建。
- `install_reference(source_ref: Mapping, target: Path, expected: Mapping, *, scope: Path) -> None`：验证完整来源后复制文件/目录，原件备份由阶段调用者先完成；不承诺目录替换/多资源事务。
- `save_document(path: Path, document: Mapping, *, private_root: Path) -> dict`：canonical JSON新文件原子保存/回读，不覆盖旧receipt；返回实际object_ref。

### 旧数据验证：scripts/sbtd_migration_legacy.py

纯数据/投影校验，不读取HOME、不创建候选或写源。Main先用文件接口读取并绑定实际bytes，再调用；`ContractError`保持脱敏。

- `read_legacy_identity(raw: bytes) -> str`：唯一明确name声明；接受固定旧格式的其他metadata，不规范化名字，重复/非法/不可解析拒绝。
- `validate_task_projection(source_raw: bytes, task_raw: bytes, sidecar_raw: bytes, *, source_path: str, decision: str) -> TaskProjection`：验证真实旧JSON、current TaskDocument与legacy-task.json的语义/隐私/时间/已知及未知字段保全。source_path是实际项目相对旧路径；decision为已完成批准绑定的share/redact。
- `TaskProjection`提供`legacy_id: str`、`parent: str | None`、`children: tuple[str, ...]`、`document: TaskDocument`，供当前批次关系核对；不引入第二状态源。
- `validate_projection_graph(projections: Mapping[str, TaskProjection]) -> None`：逻辑身份唯一、父子引用一致且无环；旧路径层级不代替metadata。

Main独占计划/阶段编排、CLI、schema/codec接入及共享文档，worker仅拥有各自模块和测试。接口实质变化先向Main说明，不能并行改共用文件。

## 本轮审查修正与契约裁决

- 实际固定源码确认旧生成树还含config/scripts/agents、运行态.current-task、忽略文件及空tasks/.gitkeep；`.agents/skills`归Codex。生成的`.trellis`内容不在apply删除，未选旧host不自动扩大范围。
- 直接share的task附件/spec/lessons逐字一致；redact才可改写。旧JSON数字按Decimal保全比较，目录摘要按完整平面条目而非递归子树摘要；暂存区在发布前完整核验，清理只删除仍属于本次创建且摘要未变的内容。
- 可变旧hash不能授权整文件删除混合共享配置；仅固定官方模板及已知Python命令渲染变体可整文件退役。未知全局旧路由阻断；Codex及已存在OMP全局路由均按同一所有权门纳入备份/暂停/批次依赖，缺失OMP根不创建。
- 部分失败回执只引用已实际观察的共享结果，完成状态仍要求全部声明依赖。已证明成功退役的absent资源不是present retained asset；codec仅在末次成功阶段后态明确absent且不属于publication时允许省略，不能掩盖丢失的新资产。
- 原生证据schema恢复为修改前逐字内容，未增加schema字段/版本。迁移外层null ref不变；报告用明确HEAD/non-git标签并核对OID/根。首轮严格部署窗口，累计重试接受同一绑定apply epoch内的报告；不自动发现前驱收据。
- raw必须有实际command和stdout/stderr，exitCode为0且未超时；兼容旧raw缺省processExitCode，但显式存在时必须为非bool整数0，null不是“未提供”。重复provenance字段等P2不在本轮夹带修复。
- Main原生验证：351项影响范围通过（1项Windows专用跳过）；安装副本真实CLI通过plan/apply/verify、detached、漂移拒绝和显式重试，部署记录为contract-backed夹具。兼容性及OMP补充后61项通过；后续最终全量与精确head证明另记，不把上述局部结果冒充最终验收。
- 独立planner/runtime/verifier/security复核已关闭其P1；Ponytail/readability确认安全seam与状态循环可维护，约141行可删及一项依赖为P2/P3候选，依D-IMP-13全部保留原级延期，不为缩行削弱安全边界。最终报告须继续列明这些残余限制。
- 两名writer曾违背单验证controller约定运行临时探针；其输出不采纳为验收证据。Main保留修改前代码checksum清单、逐项红测及当前绿测；临时目录仅在归属明确后清理，未知内容不得猜删。

## 收尾验证策略

- Main独占原生报告runner：失败、定点、影响范围与全量均保存raw JSON、同stem中文MD及evidence；RTK对报告型命令skipped-for-report，对格式／静态工具used。没有把worker临时探针或缓存输出计为通过。
- 完整Ruff不是全绿：新增模块／测试59项样式诊断，既有脚本26→29；关键E9/F63/F7/F82为0。未删除已延期的unused代码／TOML分支，也未加入ignore或关闭规则。细项列入P3台账；日期粒度解析及显式UTF-8有其契约理由。
- 新代码ty全部通过；既有脚本93→93，按文件／规则／消息多重集比较无新增。12份新Python文件format检查通过；JSON容器类型与聚合调用按实际接口澄清，没有把类型错误压成ignore。
- 首次全量854 tests/521.706s仅旧scope拒绝测试的argparse措辞断言失败，另有1项Windows专用skip。删除对`invalid choice`的文字锁定并改验精确退出2；失败用例1项与所属模块58项重跑通过，随后完整重跑。不重写失败报告为通过。
- 318文件完整安装副本的实际CLI、依赖缺失／同输入正向控制、schema/catalog、HTML ID／迁移链接、automation库存和lesson索引检查已执行；Windows只做真实macOS PowerShell解析，不冒充Windows ACL／host验证。
- BDD按本配置源仓例外不生成.feature；由PRD、实际CLI和持久回归追踪。Web/Mobile、Knowledge Ingest、跨仓HTTP、SEO及真实部署不属此切片。报告保持developer-local/local-only；dirty运行不证明PR head，固定提交后必须重新生成精确证据。

## 提交前检查结论

- `2026-09-19T11:47:07+08:00`进入checking，尚不done；P1累计仍6。12 fixed P1、22 deferred P2及6 deferred P3均保留真实级别，独立复核无剩余P0/P1。
- 最后dirty全量：`unit-report-migration-reviewed-full-rerun-p1-12-migration-runtime-2026_09_19-11_33_55`，854 tests/574.542s，exit0，1 Windows专用skip。旧失败报告及1项定点／58项影响范围结果全部保留。
- 完整318文件副本：`api-report-migration-reviewed-dual-host-p1-12-migration-runtime-2026_09_19-11_42_55`；使用固定上游模板族及逐字旧全局AGENTS，真实plan/apply/verify、两个全局router私有备份/暂停、detached、发布后漂移拒绝和显式重试均通过。部署证据仍是明确contract-backed消费者夹具。
- 配套证明：`api-report-migration-reviewed-dependencies-p1-12-migration-runtime-2026_09_19-11_37_05`的fresh无四项依赖／同输入正常解释器正向控制；`api-report-migration-reviewed-structure-p1-12-migration-runtime-2026_09_19-11_39_41`的schema/catalog、Python AST、HTML/链接、自动化只读库存与lesson索引；副本逐文件checksum执行后未变。
- README.md、README.html及版本化automation prompt均已维护实际入口/范围；CHANGELOG补未发布能力与安全边界；lessons使用既有用户提供的640（主PRD既有授权事件可核对），只追加本owner块，不创建身份。live automation、ENTRYPOINT版本和真实生效路径均未动。
- 下一门：固定提交、从git archive复制完整Skill并用fresh解释器按副本requirements准备依赖，重新执行精确head全量和原生证明；随后独立证据核对、Release gate、实现PR/admin合并、main/分支/归属明确临时文件清理及独立状态PR。此结论不能代替这些尚未执行步骤。

## 收尾新增P1与候选失效

- `b810ef0da419f9c741705590000e2c8be49c71cd`的精确全量854 tests/603.307s和318文件git-archive/fresh依赖/原生证明真实通过，58组174文件schema/checksum/中文配对审计通过；这仅证明该快照，不能被重标为后续修正提交的证据。
- 固定旧`configurators/workflow.ts:65-70`明确non-native workflow.md会移除template hash并成为用户内容。收尾发现该文件未进入未知runtime裁决门；只补plan仍可被重封装manifest删除private-only批准绕过。
- 现复用同一完整库存覆盖门：所有generated-runtime类别含workflow.md都必须有模板所有权或逐项明确裁决；apply/verify语义重验在操作/闭包校验后读取精确匹配的live原目录或确定性私有原件，整目录摘要相等才取库存，metadata按该库存条目摘要读取，空.gitkeep亦来自同一库存。不新增wire字段、索引、服务或cleanup/recovery行为。
- 红测：未批plan／重封装漏批2项，以及修改前冻结源码接受腐坏私有workflow原件1项。当前3项回归和66项plan/apply/verify/codec影响范围通过，ty通过。P112DocsExactReview与P112SecurityFinal只读复核关闭，固定P1共13；原22 P2/6 P3不变。
- 新候选仍处checking；必须重新固定提交并执行精确全量与原生证明，再进入实现PR/admin合并和清理/状态PR。此前报告原样保留，不把旧候选通过冒充新head。

## 最终精确证明与实际合并

- 最终验证head：`a6f45574754357b12c17ebc022323f44104fac69`，clean。原生全量857 tests/605.698s，exit0；1项Windows ACL专用skip。实际运行未被重标；此前b810及所有红／失败轮次均保留。
- 最终报告stem：`unit-report-migration-final-head-full-p1-12-migration-runtime-2026_09_19-12_29_23`；`api-report-migration-final-head-native-p1-12-migration-runtime-2026_09_19-12_29_23`；同时间戳的`migration-final-head-dependencies`与`migration-final-head-structure`。66组198文件schema／raw SHA-256／同stem中文汇总审计通过，developer-local/exact/local-only，environment alignment为unverified，不冒充CI或远端publication。
- git archive完整318文件安装副本与实际提交匹配；本任务新建的隔离解释器与前候选requirements逐字相同，按修正副本再次准备。真实双host旧router原件/暂停、11场景CLI、缺依赖与同输入正向控制、结构检查均通过；部署输入始终明确为contract-backed消费者夹具。原生报告schema保持原字节。
- 独立源码／文件安全／旧格式／plan／runtime／verifier／最终文档与证据复核无剩余P0/P1。共13 fixed P1、22 deferred P2、6 deferred P3；ty、关键Ruff、format通过，完整Ruff59项新文件样式及3项既有文件增量未被抑制或写成全绿。
- 实现[PR #39](https://github.com/KunoLu/640-skills/pull/39)于`2026-09-19T12:45:45+08:00`实际admin合并，merge `4360305c7eeb3acc4fa030ddc392bd27aad82288`。main与origin/main一致，merge tree等于最终验证head；实现分支本地及远端均已删除并prune。
- `2026-09-19T12:51:01+08:00`在上述合并/分支核验及临时文件清理后记录done：5份移前源码与base逐字一致，冻结原始/最终318文件副本hash复验后清理Main私有验证workspace、确认归属的worker目录及本任务生成字节码；未动共享旧缓存。1处归属不明临时目录保留，不凭相似内容猜删。P0 spike环境、真实HOME/用户项目/迁移原件和live automation未动。
- 本地旁证：最终unit报告同stem的`.closure.json`保留精确安装manifest、静态检查、合并与清理事实；它不是新的运行结果，原raw/evidence校验和未改。README.md/html、versioned automation prompt与CHANGELOG已在实现PR维护；本状态PR只记录完成事实，无新的公开行为，不额外改写它们。
- P1计数为第7项；只有本独立状态PR亦完成review/admin合并及清理后才进入P1-04。D-IMP-14仍在累计第10项P1-06完整闭环后暂停，评估全部findings并等待用户确认。

## 后续修复：未完成上下文交接验收

以下补充当前运行契约，不改写上面的历史验证快照。固定旧 `common/active_task.py` 实际使用 `.trellis/.runtime/sessions/*.json` 的 `current_task`；`.current-task` 非空路径行不作为该版本的有效指针。

| 场景 | Given | When | Then | 验证入口 |
|---|---|---|---|---|
| 缺交接批准 | journal 存在且迁移任务未完成 | 执行 plan | 返回 approval-required、零写入；仅备份不能替代交接 | `MigrationContextHandoffTests.test_unfinished_context_requires_approved_handoff_without_writes` |
| 批准的恢复入口 | 私有候选采用既有 HandoffStore 格式，批准绑定完整 context 和具体 task | 执行 apply 并读取摘要 | docs/handoffs 中可读取剩余工作；原件仍在私有备份；不创建 active-task | `MigrationContextHandoffTests.test_approved_handoff_is_readable_after_apply_and_originals_are_recoverable` |
| 多任务不猜选 | journal 及多个未完成任务 | 仅批准一个摘要后 plan | 缺失任务仍阻断；逐个批准后才通过，不按 mtime 或 session 顺序自动选任务 | `MigrationContextHandoffTests.test_journals_require_each_unfinished_task_without_selecting_one` |
| 异常旧指针 | session 指向范围外、未知任务或未知 JSON 结构 | 执行 plan | graph-conflict／invalid-config，不从 journal 猜测关联 | `MigrationContextHandoffTests.test_invalid_session_reference_is_not_guessed_from_journal`、`test_unknown_session_structure_and_legacy_path_line_fail_closed` |
| 审批缺来源 | 摘要只绑定部分原始 journal/session | 执行 plan | approval-conflict；批准不能遗漏上下文输入 | `MigrationContextHandoffTests.test_handoff_approval_must_cover_every_original_context_file` |

摘要内容仍由有权限的调用者审查并批准；机器仅验证格式、来源、任务状态、分支／HEAD 和精确候选，不承诺自动理解 journal 或生成摘要。原任务 mode 未证明时继续为 null，摘要不能选择 mode。恢复、清理和真实项目迁移仍遵守独立授权门。
