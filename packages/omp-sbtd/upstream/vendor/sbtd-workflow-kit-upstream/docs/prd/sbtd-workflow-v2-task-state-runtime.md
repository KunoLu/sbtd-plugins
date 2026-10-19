# P1-17：最小任务、active 引用、提升与恢复事件

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 基线与范围

- 从已完成P1-03实施/状态闭环的main `c0f2281c9cace8304506df3cf96bd68f7c133798`建立`p1-17-task-state-runtime`。
- 事实源：[任务数据契约](sbtd-workflow-v2-task-data-contract.md)、主PRD P1-17/AC-03/24/27/31/32，以及已安装sbtd-task的state reference。冻结schema不另起副本。
- 交付任务创建、选中、模式保存、合法状态变更、阻塞恢复、完成/祖先重开、共享提升与归档的实际文件系统行为。只读、分支绑定、路径/身份冲突和首次本地保护是写入安全前提。
- 不实现P1-18的host路由/跨分支选择/自动handoff，不建立developer身份，不执行真实迁移、全局sync或发布，不引入调度器、daemon、锁服务、数据库、journal或全局CLI。
- 由Onboard内Python任务状态模块提供公开操作接口，host-native工具调用；Skill描述真实可用入口，不伪造命令。既有Onboard check继续只读最小检查，不隐式升级成全历史扫描/修复。

## 门禁与移前证据

- 未完整调用grill-with-docs：已批准文档明确状态、事件、存储和授权边界；工程实现选择按用户预先授权的推荐答案推进，不替用户推断环境或真实数据授权。
- Legacy characterized：`python3 -m unittest tests.test_sbtd_project tests.test_sbtd_task_schema -v`，60 tests / 1.168s / exit 0。
- 基线报告：`tests/unit/reports/unit-report-task-state-baseline-p1-17-task-state-runtime-2026_09_18-21_53_00.json`及同stem中文MD/envelope；developer-local/exact/local-only，绑定上述base，不证明新功能。
- Refactoring proceed：公开复用现有安全frontmatter/schema/日期校验；迁移每个调用方，先保持既有检查行为，不复制parser、不增加浅包装。
- DDD confirmed：task是唯一有效状态；active只是目录书签，index/handoff不复制权威模式或状态。提升与模式正交，developer只在lesson写入时需要。工作流任务状态是支撑子域，安装/迁移/身份分别授权。无新的领域冲突；没有完整grill结果需要纠正。
- DDIA confirmed：单writer；单文件候选校验后同目录原子替换；比较预期旧内容并拒绝可检测冲突；不冒充跨文件事务或多进程隔离。提升/祖先重开/归档的跨文件部分成功必须可观察和安全重试。
- Release readiness ready：最终精确提交671项全量、完整安装副本/原生场景、报告与独立审查后通过；仅P1-17，不提前验收Windows/host/身份/迁移或整体v2。

## 数据与操作不变量

1. default新任务默认`.sbtd/tasks/<id>/task.md`；lite/strict或明确共享在`ai/tasks/<id>/task.md`。新任务使用实际带时区时间，mode来源区分implicit default和明确user选择，不要求身份。
2. active只保存schema_version/task_id/task_path；ID在本地/共享/归档不变。路径物理contained、每级类型有效，父节点可解析且无环；重复ID/双有效副本不能按mtime裁决。
3. 所有写操作先核对只读、真实Git branch/detached SHA或已证实非Git、授权、ignore/tracked状态、预期旧内容和完整候选。分支不符返回可解释的阻断，不自动checkout、重绑定或继续写。
4. 复用安全JSON兼容YAML校验；拒绝重复键、cycles、非有限数、unsafe tags和非法日期。保留不属于本操作的frontmatter扩展、正文和附件，不通过重写整篇文档丢弃未知内容。
5. 状态字段与所属事件同一文件原子更新。唯一`## 状态事件`表采用at/from/to/reason/evidence；Markdown分隔符和换行可逆转义。完成时间等于真实完成事件时间，不伪造历史。
6. 首次blocked保存真实planned/in-progress/checking ingress；持续blocked只更新原因/时间。模式变化和元数据自转换不覆盖恢复前态。缺失/矛盾历史必须返回需要用户选择，显式选择后追加真实release，不补造ingress或直接done。
7. 重开保留原完成时间/证据，清空当前completed_at；已done祖先按祖先到子顺序处理。任一步失败停止后续并报告已完成步骤，不假装回滚全部。
8. 提升写完整目标候选并验证，再更新有效引用/必要索引，最后独立确认退役原本地记录；中断保留原件和可对账信息，不允许两个副本同时写。恢复检查引用、内容和用户改动，不覆盖新的用户修改。
9. 归档须确认，携带整个目录/历史；共享done按可靠日期进入archive/YYYY-QN，未知历史日期用undated。本地归档不自动公开；Git history不替代ignored原件保全。
10. 单次重复请求先核对实际记录与已有事件，不重复追加完成/解除事件；异常数据不是创建同名替身的许可。没有授权只返回实际未持久化原因。

## 测试与交付约束

- 已选择的公开seam：任务状态模块操作及读取结果、实际文件系统保全/副作用，另用既有Onboard inspection作为消费者验证。测试不固定内部helper调用或字段转发。
- 按垂直切片执行红→绿；保留能证明历史恢复、原子更新、内容保全、根边界、重复操作、每步失败和重试的回归。纯接口接线用实际Python smoke，不堆mock回声测试。
- 验证真实临时Git仓库/分支/detached、非Git、ignore/tracked/越界/symlink、父子/DAG及只读零写入。故障注入只控制实际I/O失败，不能用mock结果替代持久化证明。
- 完整安装副本必须包含运行依赖并实际调用；禁止仅源码目录能工作。测试报告原生运行，命名raw+中文MD+envelope；最终证据绑定精确提交，不重标旧报告。
- README.md/html、Onboard/Skill说明、versioned automation prompt与CHANGELOG按实际入口评估；不触碰live automation或真实用户HOME。
- 审查按D-IMP-13：有效P0/P1阻断；P2/P3原级记findings.log延期。实施PR实际合并与清理后，再独立status PR写done和真实merge SHA；该闭环前不启动下一任务。

## 冻结公开接口与工程边界（追加）

### 公开接口形态

新接口是Onboard `scripts/`内的Python库（`sbtd_task_document.py`、`sbtd_task_state.py`），由host-native工具调用，不注册新全局CLI、daemon、journal或后台服务，也不新增`onboard.py`子命令。helper副本或其声明依赖（PyYAML、jsonschema、markdown-it-py>=4,<5）未随安装副本就位时，调用方只能报告不可持久化并明确停止写入，不得假装已运行。

`TaskDocument.parse` / `updated`：在同一文档文本内解析并生成候选；保留不属于本操作的frontmatter扩展、正文和附件，维护正文唯一`## 状态事件`表（at/from/to/reason/evidence）；本模块不做文件系统写入。Markdown结构识别使用markdown-it-py的CommonMark token与table源行范围（parse-only，不渲染、不联网），Python>=3.10与既有语法下限一致；缺失该依赖时解析明确失败而不是退回手写扫描。

`TaskStore(root, read_only=False)`的公开操作：

- `inspect(task_id=None)`：只读；缺省解析active书签并核对其与逻辑记录一致。
- `create(task_id, body=..., mode=None, mode_note=None, parent=None, shared=False, confirmed=False)`
- `select(task_id, confirmed=False)`
- `transition(task_id, status, reason=..., evidence=..., confirmed=False)`
- `set_mode(task_id, mode, note=..., confirmed=False)`
- `resume(task_id, reason=..., evidence=..., target=None, confirmed=False)`
- `reopen(task_id, reason=..., evidence=..., confirmed=False)`
- `protect_local_state(confirmed=False)`：首次窄保护只向项目`.gitignore`追加`/.sbtd/`，不初始化整个项目。
- `promote(task_id, confirmed=False, retire_source=False, include_tasks=())`
- `archive(task_id, reason=..., evidence=..., confirmed=False, retire_source=False, include_tasks=())`

未确认的 `promote` / `archive` 返回只读计划；其他写操作（包括 `rebind`、`protect_local_state`）缺少确认时抛出 `TaskStateError`，不写入。`promote` / `archive` 返回 `TaskTransfer(status, task, source_path, target_path, files, retained_original, completed_steps)`；`protect_local_state` 返回是否新增保护的布尔值；任务创建与更新操作返回 `TaskSnapshot`。失败以 `TaskStateError(reason, next_step, completed_steps)` 如实报告，包含底层任务解析错误。

### 相对原稿的工程边界

1. 候选复制只使用受保护的`.sbtd/task-transfer-candidates/<generated>`临时区，由本次操作own并在结束后自动清理；它不是第二个有效任务副本，事件历史只存在task.md内，没有独立journal服务。
2. 提升/归档两阶段：第一次confirmed准备完整目标候选并验证、更新有效active引用与必要共享index；`retire_source=True`要求目标已准备并经单独确认，原目录经原子rename移入`.sbtd/task-originals/<generated>/task`保留，不递归删除。未完成退役返回`retirement-required`；中断保留原件和可对账信息。
3. 任务目录内附带的其他逻辑task.md必须用`include_tasks`逐个显式授权；路径嵌套不代表所有权，scope与实际记录不符即阻断。
4. 新任务默认本地`.sbtd/tasks/<id>/task.md`；lite/strict或明确共享才写`ai/tasks/<id>/task.md`，模式与存储正交。Git项目绑定实际分支或`detached:<full-sha>`；非Git项目`branch=null`。
5. 分支/绑定不符、只读、授权缺失、ignore未保护、预期旧内容变化或部分写入均truthful报告：已完成步骤列入`completed_steps`，不假装回滚全部；重试先核对实际记录与已有事件，不重复追加完成/解除事件。
6. 未知或矛盾的blocked历史必须返回需要用户选择；用户在planned/in-progress/checking中选择后追加带明确前缀的真实release事件，不伪造ingress，也不直接回done。
7. Windows、host路由、身份建立与旧项目迁移仍属后续任务；本接口不宣称这些能力，也不宣称全量验证、真实host或发布已通过。

## 实施、审查与提交前证据

- 已实现公开操作及实际文件持久化；95项状态/文档/schema影响范围通过。测试覆盖未知mode选择、持续blocked与跨对象恢复、历史未知/矛盾显式选择、完成/祖先重开、共享/私有归档、真实Git分支约束、路径/重复ID/父子冲突、FIFO拒绝、正文保全、预期旧内容冲突及两阶段传输。
- 复制、index、active、原件退役四个I/O故障点分别保留实际已写前缀与原件，新实例重试可继续；source/target同尺寸同mtime的内容变化仍拒绝退役，不按mtime挑副本。
- 完整307文件Onboard副本与私有venv实测：10个独立Python进程场景覆盖完整生命周期、两次确认、原件保留、归档被现有Onboard check消费、分支拒绝及只读无写入；隔离HOME未新增文件。缺markdown-it-py而YAML/schema可用的真实venv也明确停止持久化，项目/HOME不变。
- 依赖实际版本为markdown-it-py 4.2.0、mdurl 0.1.2、PyYAML 6.0.3、jsonschema 4.26.0；Markdown使用显式`.enable("table")`，不使用未启用table的裸CommonMark配置。
- 第一轮文档审查3项P1经红绿和独立复核关闭；完整状态/表面审查再发现3项P1：整棵私有树保护、旧完成补录顺序、同状态节多表漏读，均经真实红测修复并独立复核关闭。历史完成前插只用于有据旧完成，保留旧metadata事件顺序，并在写入前复核完整候选历史；共同保护门证明`.sbtd/`目录本身被排除且无tracked内容。
- 根findings.log当前本任务8 fixed P1（含2项advisor）与16 deferred P2；没有零问题声明。P2保持原级，按D-IMP-14累计十项确认门统一评估，未顺带处理。
- 提交前完整回归：`tests/unit/reports/unit-report-task-full-p1-17-task-state-runtime-2026_09_19-01_01_21.json`，666 tests / 176.904s / exit 0；其后P1修复的影响范围为95 tests / 6.357s。最终提交仍须全量重跑，不能把这两轮dirty证据提升为最终SHA。
- 修复后原生证据：`tests/api/reports/api-report-task-reviewed-native-processes-p1-17-task-state-runtime-2026_09_19-01_27_14.json`及`tests/api/reports/api-report-task-reviewed-missing-markdown-p1-17-task-state-runtime-2026_09_19-01_27_16.json`；同stem中文MD/envelope保留，developer-local/dirty/local-only。早期driver转义失败已留报告，未伪装通过。
- Ponytail/Code Readability Review覆盖手写模块和测试：无需要引入或删除的框架；保留单一校验/传输实现，目录遍历改为流式，故障fixture隔离callback绑定。新模块/测试Ruff、format和ty通过；既有模块按base比较，不声称全仓静态零诊断。
- README.md、README.html、Onboard说明、sbtd-task入口/state reference、版本化automation prompt与CHANGELOG已同步实际库/依赖/权限边界；live automation、真实HOME和ENTRYPOINT未操作。D-IMP-14是计划内确认门，不推广到全局规则。

## 最终精确验证与实际合并

- 验证head：`eb5a27272f886bc02b57e4fa28b6fa33d1adac29`，clean；原生671 tests / 156.971s / exit 0，无skip。新模块/测试Ruff、format、ty通过；既有修改范围Ruff26→26、ty93→93，无新增诊断。
- 最终报告：`tests/unit/reports/unit-report-task-exact-full-p1-17-task-state-runtime-2026_09_19-01_38_15.json`；`tests/api/reports/api-report-task-exact-native-processes-p1-17-task-state-runtime-2026_09_19-01_39_19.json`；`tests/api/reports/api-report-task-exact-missing-markdown-p1-17-task-state-runtime-2026_09_19-01_39_22.json`。同stem中文MD/envelope齐备；本轮62份envelope全通过。全部developer-local/exact/local-only，不冒充CI或远端已发布。
- 精确git archive完整307文件Skill与fresh venv真实安装requirements；10原生进程场景及真实缺Markdown依赖零写入通过，执行前后source checksums一致。旧报告、失败与red/green不重标；最终unit raw另保留独立review及清理证明。
- Release Readiness Review：ready，仅本任务。写入需确认、单文件原子、跨文件保留原件并如实报告部分成功；无自动卸载/真实数据回滚。16 P2按用户D-IMP-13延期，单writer不冒充跨进程事务，未来Windows/host/迁移门保持。
- [PR #33](https://github.com/KunoLu/640-skills/pull/33) 于2026-09-19T01:44:27+08:00实际合并；merge `ea252e44534cf3f104add50d81755e3c5140ac58`。main与origin/main同步，合并tree与精确候选一致，本地/远端任务分支删除并prune。
- 2026-09-19T01:45:29+08:00完成私有验证清理：7份源码快照先按manifest/base核验，只移除Main拥有的临时环境/副本/runner/合成数据；186正式报告保留，仅最终unit raw/envelope补实际清理和review记录。P0保留安装、真实HOME、用户任务、真实迁移备份与live automation未触碰。
- 本完成记录通过独立status PR审查/合入；闭环前不启动P1-18。P1累计4项，D-IMP-14累计十项后全量findings评估并等待用户确认的门禁保持。
