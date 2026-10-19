# 变更日志

本文件按 Git tag 记录用户可见变更，最新版本位于最上方。未发布章节在创建对应 tag 后补充发布日期。

[English](CHANGELOG.md) · 简体中文

中英文变更日志逐版本、逐条目保持一致，仅语言不同；版本号、日期、链接、提交SHA和代码标识保持一致。未发布内容在两份文件中同步维护，历史事实不因翻译改写。

## v2.0.2（未发布）

### 变更

- 受管 Graft pin 从 `@nanonets/graft@0.21.1` 晋升到 `@nanonets/graft@0.22.0`。npm bin 现为 `dist/bin/graft.js`；registry `gitHead` 缺失，因此 pin 只保留 tarball URL 与 integrity，不再保存 git SHA。`openai` 与 `@anthropic-ai/sdk` 随包提供但不默认启用。受管安装仍须显式确认，拒绝 shell shim，并保持遥测关闭。旧 stamp 与旧 MCP 绑定在新 pin 下拒绝，须受管重建图并重部署。
- 生成的绑定继续使用包内 canonical `dist/cli.js`。受管子进程清除继承的 `TRAIL_*`、固定 Graft 品牌、禁用 Trail fetch／自动切换，并在启动及每次 MCP 请求前校验新增消费的项目 `.trail` 树；拒绝链接或特殊文件笔记，避免读取选定仓库之外的内容。构图策略摘要随固定资产同步更新。

### 修复

- 受管目录删除已失败时若释放本次操作的删除holder也失败，两个错误均保留可见：holder被保留时以携带 `retained_refs` 的 `RetainedObjectError` 报告，并以原始错误为其原因链；其他释放失败仅作为附注附加到原始错误，仍抛出原始错误。释放仍只对同一空holder使用 `rmdir`，不引入递归删除。

## v2.0.1（2026-10-14）

正式版 [v2.0.1 Release](https://github.com/KunoLu/640-skills/releases/tag/v2.0.1) 已发布。annotated tag 指向 `0aec5d3c9493a2010ad2a52b4894ccf7e0869224`，该精确提交的[三平台 main CI](https://github.com/KunoLu/640-skills/actions/runs/38572152150)通过。源码发布不执行本机安装、workflow sync、项目迁移或备份处置。

### 变更

- Windows私有目录ACL证明改为进程内调用Win32安全API，不再每次校验和创建都启动PowerShell。判定不变或更严格：属主必须是当前用户，每条ACE必须是授予当前用户、SYSTEM或Administrators的允许项，junction、未知ACE类型或任何API错误一律失败关闭。原PowerShell证明保留在测试中作为差分对照。不引入ACL缓存、超时放宽或检查缩减。
- CI分片按原生逐例实测秒数拆分无fixture的用例，类级和模块级fixture保留在同一分片，列出缺少权重的用例，Windows改为4个分片。`tests/run_ci.py --refresh-weights` 从同一修订的成功分片报告重建权重。每个发现的用例仍恰好执行一次。

### 修复

- 减少受管目录删除及升级恢复中重复创建私有holder的开销。文件按父目录分组并复用本次操作的空holder，每次捕获仍新鲜校验私有权限、对象身份、安全路径和内容；不引入跨调用ACL缓存、未知内容递归删除、超时放宽或备份处置。
- 通过唯一的 `project-validation` 模板固定 Agent 编写的中文 Markdown 执行汇总，分开呈现运行信息、命令、范围、结果表、失败轮次／复跑、产物和限制；Web UI 覆盖率评估作为附录，不改写历史报告，不把排版当作测试或发布证据。

## v2.0.0（2026-10-14）

正式版 [v2.0.0 Release](https://github.com/KunoLu/640-skills/releases/tag/v2.0.0) 已发布。annotated tag 指向 `8f6c46993e7546b68f949bd52ede806d9b1afa61`，该精确提交的[三平台 main CI](https://github.com/KunoLu/640-skills/actions/runs/38500935539)通过。本版累计包含 rc.1—rc.4 及下方基础能力；已发布 RC 章节保留原历史验证边界。源码发布不执行本机安装、workflow sync、项目迁移或备份处置。

### 正式版累计范围与验收边界

- 包含 RC 阶段的现态调和 `migration --phase reconcile`、跨运行时来源证明、精确 Skill 链接探测授权、旧批次 cleanup 的依赖分层和一次原生升级续接；具体兼容／拒绝边界见对应 RC 章节，不将版本号或内容摘要当授权。
- 当前主线为 Codex／OMP、default/lite/strict、单一任务状态事实源和每个有效宿主域一条通用 Graft MCP；Graft固定0.21.1，14 bundled／19 required external Skills，旧工具仅作为明确迁移输入或保留材料。
- P3观察与问题复跑已完成，模式建议／拒绝场景含受控真实宿主补证；计量有完整用量与明确tokenizer基准，但不宣称跨模式节省比例、全部常驻仅2k或五个独立自然业务样本。
- 受管数据／配置恢复、真实宿主接受和备份保留分别验收；不承诺旧Trellis可写回退。历史环境按已确认范围精准清理或原位保留，不把发布当作本机升级、sync、生产部署或备份销毁许可。
- 双语README改为引用发布tag和CHANGELOG，不再维护易过期的单个RC横幅；Onboard入口区分实现能力、版本证据与实际部署授权。
- 补齐双语v2 bootstrap/首次及重复init、明确reset、v1→v2包升级与数据迁移、upgrade分阶段及独立恢复的可复制提示词；统一现行初始化资产文档和工作路径图，移除旧Trellis/GitNexus任务路由。host smoke说明改为受控认证，明确旧复制凭据live入口不可用于当前真实认证验证，保留历史执行器/证据而不宣称已修改其代码。
- 变更日志分为英文`CHANGELOG.md`与中文`CHANGELOG.zh.md`，版本、条目、链接、代码标识及证据边界逐项对应；中文原发布历史保留，同步更新双语入口和版本化维护规则。

### 新增

- 新增显式 `upgrade --phase plan|apply|verify` 与升级专用 `recovery` 输入：按所选 Skills 根、全局规则、宿主配置域及 shell profile 生成固定载荷基线、完整差异和可确认计划；合法旧 Skill 壳不再被内容验收视为同版。未知定制须明确替换或保留，身份／路径冲突拒绝，原有 init/reset/migration 语义保持。
- 升级采用独立校验执行副本、完整原件、逐资源写入意图和累计实测回执；恢复独立确认，拒绝用户漂移，不自动销毁备份。MCP 指向选定的已安装 Onboard，而非仓库源码或暂存执行器。共享 Skills 根去重，OMP 有效继承来源封存；同批相互改写的继承依赖在写入前拒绝，按 provider 完成后重新规划 consumer。
- 内容、运行时协议、隔离真实 Codex／OMP 加载及历史清理分别报告；隔离 host probe 明确不证明原 GUI 或既有会话重载。显式 shell probe 实际解析所选 profile 并验证 Graft 命令解析。Bash／PowerShell 根安装器均转发升级与恢复，默认只读计划与验收不运行 host probe。
- 新鲜 `cleanup-legacy` 增加九个 GitNexus Skills 的闭集身份检测，仍先备份、展示清单并独立确认；不扩展不可变历史迁移清单，不使用前缀删除，不卸载 CLI 或删除全局数据、旧运行时及备份。
- 固定载荷摘要统一按相对 POSIX 路径字符串排序；整个自包含 Onboard 包及 canonical 根 LICENSE 在 Git checkout 中保留原始字节，避免 Windows 路径排序及自动换行转换破坏 stable pin。Windows 私有 vault 子目录与宿主探测夹具通过既有 DACL 初始化器创建，保留已有目录只验证、不自动修权限的边界；Git Bash 使用 `/c/...` PATH 别名并绑定独立的 shell 可执行目标，不混同 `graft.exe` 与 `graft.ps1`。
- 迁移后旧资产清理扩展（`sbtd-cleanup-expansion`）：migration verify 为 verified 后由 Skill 路由层主动询问是否清理——展示批次封存候选并实际运行 `cleanup-legacy --phase plan`，两份实际清单都展示后才请求合并确认，确认后执行；批次清理先执行，若改变新鲜计划封存的原件则重新生成并展示剩余清单；同一已确认流程内，仅减少由绑定回执证明已完成的项且其余目标/效果不变时沿用原同意，新增目标或改变效果才重新确认，未知消失、用户改动或失败证据仍停止调和，执行使用当前 plan_id；拒绝时告知后续可用「sbtd cleanup」「清理工作流」或同向意图再次触发；提示只授权只读检测/计划，看到清单后的明确同意才授权执行，`verification_id`/`plan_id` 由 Agent 从 CLI JSON 自取。清理候选新增项目 `.gitnexus/`、codex/claude/kimi/omp 四个 host 已配置路径中的 gitnexus MCP 条目（只删识别为 gitnexus 的键/表，邻居保留；全局配置影响其他项目须披露确认）与项目 `AGENTS.md` 精确成对的 `<!-- TRELLIS:START/END -->`、`<!-- gitnexus:start/end -->` 标记块（仅识别顶层 HTML 注释块，块外内容与 graft 围栏逐字节保留，零对非候选，残缺/重复/交错 blocked 待人工裁决）。新增 `cleanup-legacy --phase plan|apply` 新鲜检测路径：只读检测并封存私有 plan（含完整 vendor 足迹准备描述），以 `plan_id` 确认执行；执行前私有备份全部候选原件及完整 vendor 足迹，fail-stop、逐项校验目标后态、累计回执原子保存、同 plan 重试不重放已成功资源、部分结果调和前阻断重试；批次 manifest 不可变、永不新增目标类型，批次证据缺失才走新鲜兜底，陈旧/冲突/失败的批次证据不作为绕过门禁的兜底理由。GitNexus npm 包、CLI 与 `~/.gitnexus` 全局数据不动；正常 init/reset 不执行清理；两安装器直通 `cleanup-legacy`。
- P1-23 增加清理闭合后的 OMP follow-up 部署批次：五个 `--followup-*` 参数绑定完整 Codex 前批的 manifest/apply/deployment/verification/cleanup，要求显式 `init`/`omp`，不接受 hooks 或递归 followup。旧 successor 拒绝规则不变；完整部署集合可在受管前态证明下升级，空 apply 不重复迁移，恢复只撤销本批写入，前批备份继续保护。实际 HOME 接线与 host 验收仍需独立授权。
- P1-21加入后继部署批次：迁移plan新增`--successor-manifest`/`--successor-apply-receipt`成对输入（要求显式`--deployment-mode`，与publication/routing批准输入互斥），修复「plan密封漏deployment声明即永久无法部署」的一次性批次缺口。后继plan绑定`deployment`为null且apply完整成功的前批，重新实测每个前批apply后态与承接cleanup前态（任一漂移blocked），封存仅含未完成cleanup与部署闭包的successor manifest；manifest payload新增`successor`绑定（前批manifest_id/apply_id、全部succeeded apply结果嵌入，及钉住真实前批文件的`manifest_ref`/`apply_receipt_ref`内容哈希引用，链期内两文件不得移动或改写），retention逐字段继承前批。部署`before_requirement`的phase-after可跨manifest引用前批同资源结果，deploy/verify/cleanup/recovery以「嵌入结果∪本批回执」叠层解析期望前态，且每次消费都重载真实前批复验嵌入结果、承接集合与未覆盖后态。无前批绑定的manifest行为不变；未执行live部署。
- P1-01增加内部Onboard参数与交换契约层，覆盖严格JSON、批准快照、私有／共享操作、阶段收据、deployment evidence及恢复数据和envelope；它不注册尚未实现的公开迁移／恢复命令。jsonschema按Onboard requirements显式准备并惰性加载，目录复制不代表依赖已安装，缺失时校验fail-closed。
- P1-02加入只读SBTD最小状态检查与按需bootstrap：未onboard项目不因缺少task／身份而失败；已有指针与选中任务按schema、日期和物理路径检查，异常不重建。PyYAML显式纳入安装依赖。
- P1-03加入固定版本Graft本地检测和显式确认的全局安装入口；检查与npm/latest可达性分离，受管子进程DNT与dotenv/LLM环境隔离，安装后验证native启动及telemetry持久关闭，不提前激活host/MCP或迁移。
- P1-17加入Onboard内任务状态Python库：`scripts/sbtd_task_document.py`负责task.md解析与候选更新，保留未属本操作的frontmatter扩展／正文并维护唯一状态事件表；`scripts/sbtd_task_state.py`提供`TaskStore`的create／inspect／select／transition／set_mode／resume／reopen／protect_local_state／promote／archive，由host-native调用，不注册新全局CLI、daemon、journal或`onboard.py`子命令。Markdown结构识别使用新增声明依赖markdown-it-py>=4,<5的CommonMark token（parse-only、不渲染、不联网，Python>=3.10与既有语法下限一致），缺失时明确停止写入而不是退回手写扫描。提升／归档两阶段：先准备并验证目标候选、active引用与必要共享index，单独确认后原目录原子退役进`.sbtd/task-originals/`保留且不递归删除；候选复制只用受保护临时区并由本次操作清理，目录内附带逻辑任务须`include_tasks`逐个显式授权。非Git项目branch为null，首次窄保护只追加`/.sbtd/`；部分失败如实返回`completed_steps`，重试不重复追加事件，未知blocked历史必须用户选择恢复相位。不代表Windows、host路由、身份建立、真实迁移、全量验证或发布已通过。
- P1-18加入确定性路由与受保护交接库：`scripts/sbtd_task_routing.py`的`TaskRouter`把host已明确的意图（new/continue/question）、显式mode、推荐回应（accept/keep）与只读/确认标记转成确定性`RouteDecision`（ready、needs-task-choice、needs-mode-choice、needs-mode-decision、needs-branch-choice、needs-persistence-confirmation、persistence-failed、blocked），不做自然语言意图分类；续作先唯一确定task再定mode，推荐必须先返回待决定，拒绝以结构化mode_note按风险标识去重保存，保存失败保持会话内选择并如实标记未持久化。`TaskStore`新增公开的current_binding、recovery_candidates与rebind：跨分支不匹配要求正确worktree、明确rebind（expected_branch/reason/evidence/confirmed，只更新绑定与事件，不checkout、不stash、不重置blocked恢复历史）或只读选择。`scripts/sbtd_handoff.py`的`HandoffStore`只在真实pause/context-switch/branch-switch/context-pressure/manual触发，计数或checking不触发；task/session退出独立锁存且手动请求不清除；`save`结果状态为saved/suppressed/conversation-only/branch-conflict/unprotected/unchanged/pending-confirmation/needs-redaction，写入前核对`docs/handoffs/`窄保护与tracked状态并要求显式redaction_confirmed；文件名取完整逻辑任务ID UTF-8字节的小写hex（大小写不敏感文件系统上仍无冲突且可逆），同任务同内容快照（仅created_at除外）不重写、跨日不单独触发；主动提醒只取7天内按任务去重、root/分支匹配且未完成任务的快照，旧快照可显式手动恢复但绝不改写task；分支不匹配拒绝写入，handoff不是mode/status事实源。不代表Windows、host接线、自动SessionStart恢复、真实迁移、全量验证或发布已通过。
- P1-19加入按需developer身份库与显式CLI消费：`scripts/sbtd_identity.py`的`DeveloperStore(root, read_only=False)`提供只读`resolve()`／`plan(name)`与确认门控的`ensure(name, confirmed=False, protect=False)`，统一返回冻结`IdentityResult`（status／name／source／path／first_write_eligible／topology／reason／needs_protection／completed_steps，可`dataclasses.asdict`导出），不注册新全局CLI、daemon、initializer或身份数据库。本地`.sbtd/developer`合法值（单条`name=`、`^[a-z0-9]+$`原样匹配）直接胜出且不再查Git；仅本地确实缺失后才核验真实Git根、git-dir/common-dir与NUL分隔worktree registry，已验证linked worktree只读同仓主checkout当前身份且不复制回本地；现存异常（重复声明、非法值、错误类型、symlink、不可读或父路径不安全）是conflict而非缺失，Git未知或不可用是blocked而非非Git证明。名字校验复用单一`validate_developer_name`，不trim、不小写化、不从Git／OS／环境／历史目录猜作者；普通resolve/plan不读旧`.trellis/.developer`。首次建立只允许正常缺失目标：窄`/.sbtd/`ignore保护与名字授权分开确认，仅写`name=<name>\n`并回读验证，同名幂等、异名conflict、并发胜者不覆盖、失败如实返回completed_steps。`onboard.py`仅经显式`--developer <name>`消费：`check`／`plan`只读并在单JSON中展示`developerPlan`（requestedName、聚合status／reason及逐项目projectRoot／status／name／source／target／topology／needsProtection／completedSteps），conflict／blocked／needs-*或无项目范围时exit 2、绝不默认cwd或HOME；`init`／`reset`／`init-projects`要求`--developer`与`--yes`同现，在任何全局或项目写入之前完成全批次身份preflight，冲突先于副作用拒绝，写入后身份失败exit 5且保留部分结果。无`--developer`行为完全不变，reset不覆盖既有身份。根安装器本次不加flag（全量转发归P1-07／P1-08）；旧身份真实迁移仍是独立P1-12门。不代表Windows、真实host、全量验证、真实迁移或发布已通过。
- P1-12公开`migration --phase plan|apply|verify`：只读计划绑定已批准的私有候选；确认apply完整保留原件、发布投影、暂停受管旧路由并保存不可变累计回执；verify只读消费实际资源和部署报告。新增闭集旧身份提取、完整平面目录摘要、来源／暂存区先验证后发布、按真实已观察共享结果保存部分失败及显式重试。旧任务数字无损校验，直接share逐字保留；标准旧生成树与现存Codex/OMP全局路由均入清单，混合共享配置不因可变旧hash匹配而被整文件删除。部署producer、cleanup和recovery不在本项注册，合成部署证据不代表真实host通过。
- P1-04加入Codex项目接线与独立opt-in hooks：固定本地Node/Graft、按仓根MCP、模板后marker、保留foreign配置，不自动启用或信任host hooks；受管入口使用临时HOME并拒绝不安全自维护状态。迁移plan声明窄部署闭包，init/init-projects消费完整上下文并保存实际累计资源／原件／smoke证据，部分失败不丢弃此前写入；不新增migration阶段，也不提前提供cleanup/recovery。
- P1-05加入 OMP 接线与闭集图分析：完整部署按 active profile／`PI_CODING_AGENT_DIR` 写入 user MCP JSON，读取的 OMP、Codex、Claude来源及provider gate以只读快照绑定；等价继承按完整连接字段匹配且不制造空配置，disabled、managed前缀冲突、server/extension denylist、动态或漂移拒绝。manifest显式封存 deployment mode/platform/inputs，迁移支持 `--deployment-platform codex|omp`；OMP不声明Codex hooks。受管 `analyze` 仅映射 ask/map/skeleton/callers/check/grep/blast 的固定安全参数，不允许任意native argv、workspace、deep、LLM命名或export。
- P1-06加入多项目／worktree隔离守卫：普通Codex／OMP接线在固定runtime验证和任何root-scoped probe前拒绝嵌套或相互包含的已选仓根；多个显式根分别构建图并以各自`cwd`／`--root`写入MCP binding，父目录和未选sibling不写入。linked worktree不同branch可分别接线；仍不支持父目录联邦。
- P1-07在Bash安装器中完整转发Codex／OMP Graft接线、独立`--graft-hooks`、迁移deployment封存输入与显式developer参数；project-only继续保持不写HOME、用户级MCP或hooks，未知参数仍严格拒绝。
- P1-08在PowerShell安装器中提供对等转发与恢复参数，覆盖`--yes`／help和迁移deployment／developer输入；严格参数绑定继续拒绝已退役Trellis选项，不把内部project-only模式写入公开Action。
- P1-14新增仓库级 GitHub Actions `validation` 工作流：`actions/checkout` / `actions/setup-python` 按 commit SHA 固定并指定 Python `3.12.10`，PR 事件显式 checkout PR head SHA；Linux 运行全量 unittest/contract 与语法检查，macOS 运行 Bash installer／多项目／workflow contracts，Windows 运行 PowerShell installer／workflow contracts 并在 pwsh 可用时运行 `-k powershell` 真实安装器子集，三个 job 均断言 checkout 运行后干净。新增 `sbtd_backup_retention` 授权记录 helper：仅对删除范围外的既有私有准备记录或迁移报告读-改-写-回读，写入 custodian、候选归属、精确范围、本次独立授权和实际确认时间，逐项缺失、目标不存在、封闭 publication-decisions 任意加字段、写入失败或回读不一致均 blocked、零删除、不得 done；禁止新建处置文件，不注册处置 CLI，也不替代 P3-04 人工规程。CI 通过不代表真实 host、完整 Windows 原生或发布完成。
- P1-15 增加 Codex/OMP 三模式 host smoke 入口：默认 CI 跳过真实会话；`SBTD_P115_HOST=1` 才跑六个 host×mode 组合。另含 Gate 分层、跨会话 task 恢复与保存失败格；入口文件规模只作观察，不把字数换算成 AC-20 token 通过。

### 变更

- Graft MCP 改为每个有效 Codex／OMP 配置域一条全局 `sbtd-graft`，不固定 cwd／项目 root；全局安装可不选项目，项目初始化只维护本地图与 stamp，后续追加不增加连接。launcher 按实际启动 cwd 锁定最近真实 Git 仓／worktree，支持子目录；无项目、HOME、未初始化嵌套仓、旧 stamp、越界数据和不可信 Git PATH 明确拒绝，保留 pin、DNT、环境隔离与每请求校验。
- 旧固定项目 MCP 仅经 `--graft-retire-legacy` 明确切换；不同旧运行时须提供快照绑定的私有 `--graft-legacy-bindings` 契约。Bash／PowerShell 对等转发，保留原配置备份与无关 MCP；历史回执不改写，project-only 与历史密封部署拒绝混入本次退役。源码能力不代表 live 切换、TEMP 清理或备份销毁已执行。

- 迁移 cleanup 的 `.trellis` 删除统一改为在项目根实际执行 vendor `tl uninstall`，由专用适配器驱动（新封存与已封存批次一致，前后态校验不变）：计划时封存完整 vendor 足迹（含可能改写的平台配置/AGENTS），执行前私有备份全部足迹；CLI 缺失或准备失败 blocked 不执行，不完整卸载 failed 并按实测逐项记录 after 状态——vendor 失败可能部分改写，保留私有备份与实测证据、调和后才可重试，不回退引擎直删，不用 `rm -rf`。
- 退役 `trellis-workflow`/`trellis-channel` 全局目录的清理识别从固定版本校验值钉改为身份识别（非 symlink 目录 + 自身 `SKILL.md` frontmatter `name` 精确匹配），任意 1.0.x 内容漂移均可识别；symlink、SKILL.md 缺失/不可读或身份不匹配仍 blocked 保留。
- 受管 Graft pin 从 `@nanonets/graft@0.18.0` 晋升到 `0.21.1`：registry gitHead `375a37e0b6a21d28f12fce2d220d692726bb0730`，tarball integrity 与官方发布包一致。守门启动器、DNT、stamp 精确版本和 fail-closed 不变。旧 stamp 与旧 MCP 绑定在新 pin 下拒绝，须受管重建图并重部署。不改默认守门形态，不新增裸形态开关。
- 项目 `.gitignore` 模板忽略 `.impeccable/config.local.json`。该文件是 Impeccable 每人本机覆盖，含 hook consent；共享的 `.impeccable/config.json` 与 `.impeccable/design.json` 仍可追踪。安装器忽略探针同步检查这一路径。
- 配置源仓根 `.gitignore` 从七行改为九行，在 `AGENTS.md` 后增加 `.chrome-devtools-mcp/` 与 `.playwright-mcp/`。两条目录规则在本仓工作树匹配同名本机 MCP 日志目录（也匹配嵌套目录），不复制业务项目模板，也不改历史 lesson。
- GitHub Actions `linux-full` 的 `timeout-minutes` 从 20 提到 40；macOS 保持20。Windows 升级／恢复含真实私有目录 ACL 与双根安装回归，40分钟窗口已超时，扩大到90分钟并开启逐项 unittest 输出，保留完整验证范围。

### 修复

- 修复 OMP 继承等价配置无需新建文件时的部署回执校验：仅允许已绑定 OMP 的 `graft-omp-mcp` 保持前后均不存在；Codex MCP、hooks、项目 AGENTS 的缺失及已有文件消失仍拒绝。

- 迁移兼容已刻画的 Trellis 0.6.15／0.6.17 数据；0.6.15 中 lessons／runtime／杂项 hash 只作字节声明，不认领为生成资产、不豁免内容审批。未知版本、路径逃逸、生成文件漂移及共享配置归属冲突继续拒绝，不扩展 vendor 卸载 CLI 支持范围。
- 无已配置宿主的旧项目可生成空 platforms，但已有或计划后新增的未知宿主路径仍阻断；不递归读取外部宿主树，不因空操作绕过根规则 marker 的完整性检查。版本与 ownership 从封存清单／保留原件复验，保持恢复边界。
- 取消关闭旧阻塞恢复阶段；重开后新一轮阻塞只恢复本轮阶段。归档及原件退役检查目录外的逻辑子任务，未终止子任务仍阻断。
- 旧任务脱敏同时约束新增派生字段：已隐藏的阻塞理由不回填共享 frontmatter，已隐藏的取消／暂停时间不泄露到事件或归档季度；已证明时间早于创建时间仍拒绝，不以脱敏掩盖矛盾。
- `resume` 不再把 blocked→cancelled 当作恢复重试成功；取消态必须显式重开。旧创建日期只有日精度时，拒绝取消／暂停落在更早记录日期，同日仍保留时间未知，不补造午夜。
- 迁移识别补充受信安装包内精确官方模板路径／版本／内容依据，兼容已审核的旧登记 hash 与实际官方文件不一致；不刷新原元数据、不联网下载、不放宽共享配置、数据版本或 vendor 卸载 pin。
- 混合项目 `AGENTS.md` 的既有签名候选批准可绑定实际前态，不再被更旧整文件模板摘要抢先拒绝；缺批准、签名不符、内容漂移与原件复验继续 fail-closed，项目规则不变成生成文件所有权。
- 原件退役后的复验继续使用 checksum 绑定的 retained ignore 规则，覆盖已登记／未登记缓存及 incidental 文件；区分排除父目录与仅排除文件，保留有效否定规则，缺少 Git 证据时拒绝降级。重封 manifest 不再替代生成内容的字节归属证明。
- 迁移承接已逐字对齐的项目 AGENTS：封存 unchanged 前态与执行模板依据，不签名、不重复覆盖，漂移仍拒绝；不把混合规则加入生成文件钉。
- 仅文档历史目录可按精确源路径审批归档，不补造 task.json、身份、状态或日期；完整覆盖、内容／链接及真实任务归属检查保留。
- 历史任务分支与迁移 checkout 不同时保留真实绑定，通过明确的迁移取证与延后恢复说明导入交接；不自动 checkout、rebind 或选择活跃任务。
- 修复迁移部署将已批准项目规则正文重置为通用模板的问题：只解除精确维护暂停前缀并更新受管 Graft 段，批准来源、重试、验证和恢复保持一致；普通 init 的显式模板替换与已对齐 AGENTS no-touch 不变。
- 修复 OMP 迁移 apply 按计划移除旧宿主配置后，部署仍要求迁移前输入字节而误报漂移的问题：后续消费仅接受绑定成功回执、连续前后态及完整原件证明的变化；新增／缺失输入路径、未批准修改、部分结果与原件漂移继续拒绝，不放宽运行时签名续接门。
- 本仓及项目模板加入 `/ai/tasks/**/reports`，保护普通任务、嵌套子任务和季度／undated归档任务的原始报告与汇总，并覆盖同名文件／symlink；共享任务正文与业务报告源码保持可追踪。安装器补充真实 Git 保护检查，重新包含任务报告时返回冲突；保留原件，不自动取消追踪、搬迁其他测试报告或同步本机配置。

- 缺失 Skills 根的大小写／规范化别名重叠在封存前拒绝，避免创建目录后计划范围失效；升级／恢复的计划与执行均先校验当前 Python 的隔离依赖，仅 user-site 可见时受控拒绝，不取消 `-I` 或自动安装。
- Bash／zsh 新 PATH 块使用 LF，保留原 CRLF 和 PATH 末项；Windows POSIX 别名按完整所选目录检测旧 PATH，不误报同前缀或子目录。PowerShell 非 ASCII npm shim 按实际引擎编码限制证明，避免旧 ANSI 解码下误报 CLI matched。
- RPC ID 按 JSON 类型匹配，Boolean 不冒充 Number；直接 MCP 验证 JSON-RPC 2.0 envelope，保留 Codex 无版本回显兼容。OMP 来源未完成发现／分析且无旧入口证据时报告 unknown，不误报不存在。
- 恢复重试尊重明确未写入回执，旧 pending checkpoint 不得把用户同字节文件认领为本批；无法归属的 intent 现场保留为 blocked，不再报告空恢复完成。
- Codex 隔离验收不信任真实项目配置层，防止启动未选项目 MCP；Darwin 缺失 Unicode 等价目标及 Shell 命令与写集的依赖冲突写前拒绝，host-home 别名不改写已明确选中目标的决定。
- 既有 BOMless PowerShell profile 以 ASCII-only 表达式写入 Unicode PATH、不转码无关字节；探针固定 UTF-8 输出，按实际 LF 协议分割；npm shim 允许语言中的字面标点，动态展开仍拒绝。
- OMP legacy 报告纳入有效启用继承来源，不扫描未选 provider；非文件配置为 unknown，不支持的 RPC 状态保留到宿主和域汇总。
- 升级目标重叠与继承依赖预检识别物理路径别名，拒绝通过另一拼写覆盖 preserve 原件；Windows 大小写敏感目录不再被字符串折叠去重、误判包含或共享错误载荷摘要。已选配置／profile／Onboard 子目录的合法别名绑定封存目标。
- 封存 blocked 的 MCP／shell 决定先于宿主语义比较，磁盘后来匹配不能补足授权；probe 未确认的拒绝补齐 schema 引导字段，无法展开的 home 路径返回受控 JSON。
- Profile 重写识别并保留首行 UTF-8 BOM，新建空 PowerShell profile 使用 UTF-8 BOM 兼容 Windows PowerShell 5.1 Unicode 路径；Bash／zsh 登录 profile 按登录模式隔离探测，rc 文件保持非登录模式。
- MCP／Codex method 回复不再接受 data 冒充 result；MCP 检查初始化协商版本及正常收尾，缺失／不支持版本、非零或强制退出不得报告 verified；宿主缺少方法按结构化错误码脱敏报告 unsupported。
- 升级写后持久化／执行器失败不再冒充普通写前拒绝：返回 failed／exit 3、绑定批次的 checkpoint 与备份入口，并区分实测后态和 unknown；证据读取再次失败仍保留恢复上下文。
- 升级父目录预检改为逐组件 no-follow 检查，不递归扫描无关兄弟内容；修正文件系统根包含判断，按物理身份合并 Skills 根及已存在子目录的拼写别名，并绑定决定键，保留大小写敏感卷上的不同目录。
- 宿主对齐只接受 Codex 实际 `config.toml` 入口；统一 `oh-my-pi`／`omp`，blocked 不再被 drift 掩盖，合法无关 MCP 与非法配置分别报告 legacy none／unknown。
- Shell profile 拒绝 UTF-16 混写及不可表达的 PATH 项；Bash／zsh 按交互条件探测，PowerShell 检查真实命令优先级并兼容区分大小写的 PATH 环境。受支持 npm shim 仅按受限字面相对路径证明 CLI 指向，不执行任意包装器，也不冒充 Node 解释器证明。
- OMP 加载以成功 RPC 响应中的结构化工具注册表为据，不再将 prompt 中的 URI 当可调用证据；RPC 写入与读取共享期限，健康 EOF 与阻塞子进程的管道收尾分别处理。
- Codex MCP 候选兼容合法 TOML 中分散的 `mcp_servers` 表及 server 子表，不再把解析器的分散表代理误判为非法配置；最低 tomlkit 提高至已修复完整片段删除的 0.13.2，退役后复核序列化结果，避免返回残留旧项的半切换候选。无关设置、注释及幂等性保留，顶层 inline table 和未证明归属的旧条目仍拒绝。
- Windows MCP 根证明直接选择外部 PATH 目录中的原生 `git.exe`，拒绝批处理包装器及解析后非 `.exe` 目标，避免 CMD 参数解释和 cwd 隐式遮蔽；POSIX 同样使用明确目录内的 Git 候选，保留物理路径边界。
- Git 根证明在 Windows 显式按 UTF-8 解码路径输出，修复非 UTF-8 默认代码页下合法中文／重音字符仓库被误拒绝的问题；POSIX 保留原解码约定，各平台的输出解码失败均转为受控 `root-unsafe`，不放宽仓库边界检查。
- OMP 全局 MCP ownership/state 校验同时要求 launcher 与 CLI 路径为绝对路径；同名相对路径不能通过受管记录证明，合法全局配置与历史回执格式不变。
- README 两个入口补齐同作用域 plan／init 成对切换命令；版本化自动巡检统一为每个有效 host 配置域一条全局 MCP、逐项目本地图，不再把历史逐仓绑定当当前安装要求。
- 根安装器普通 `init`／`reset` 带 `--yes`／`-Yes` 而未指定项目参数时改为 global-only，不再自动把 cwd 纳入项目写入范围；显式项目参数、project-only 和未启用自动确认的交互选择保持不变。

- 图目录守卫在 Windows 使用 `os.stat(..., follow_symlinks=False)` 获取真实硬链接数，避免 `DirEntry.stat()` 的 `st_nlink=0` 哨兵导致普通文件被误拒绝；单链接、symlink、reparse 与 special-file 安全限制不变，原生启动回归同时覆盖合法图和真实硬链接拒绝。

- vendor 卸载拒绝将封存资源 `path` 替换为受检项目 `root/relative` 之外的诱饵；严格校验相对路径，并与 fresh planner 的实际路径核对，备份、前态复验和结果测量只消费已绑定路径。重算摘要不能绕过此门；正常旧计划的持久 scope fingerprint 形状及摘要算法不变。
- 清理复核修复：实际 Skills 根即使被更宽的共享 HOME 根覆盖也保留独立逻辑绑定，退役目标始终必须是该 Skills 根的直接子目录，防止同名但未选中的用户目录进入清理。
- vendor 卸载在备份结束、启动命令前重新验证计划中原先缺失的受管路径仍不存在；备份期间出现的文件保留并阻断卸载，不能让 vendor 在没有备份的情况下删除。
- 新鲜清理重试继承已成功 vendor 操作的逐路径 after-state 与原件备份，允许后续未改动失败项修复后继续；伪造、漂移或失败/部分成功的 vendor 结果仍阻断。批次已完成授权项导致剩余清单缩小时不重复确认，新增目标或改变效果仍须确认。
- 清理第二轮复核修复：`cleanup-legacy --phase plan` 接受可选 `--global-skills-dir`，Skills 根解析沿用既有优先级（显式参数 > `AGENT_SKILLS_DIR` > 受信已安装 Onboard 父目录 > 平台默认）并把选定根封存进计划；apply 只消费封存根，不接受重新指定根，也不被环境变化重定向；migration 各阶段与 `cleanup-legacy --phase apply` 参数不变。
- OMP 的 gitnexus MCP 检测新增现有 `active_omp_paths` 解析的有效配置：相对 `PI_CONFIG_DIR` 覆盖与 `OMP_PROFILE` 优先于 `PI_PROFILE` 的有效 profile；同一目录项的路径拼写别名去重，不合并不同硬链接目录项，默认位置仍按原规则保护。
- 清理 plan 与 apply 在任何目标写入前拒绝相等或互为祖先/后代的候选路径（如被选中的 `.gitnexus` 内含同被选中的退役 Skill 目录），不靠执行顺序掩盖冲突，父目录与其他候选原文保留。
- P1-24 follow-up 前态闸改为按受管节校验 configure-graft 结果，不再要求整文件相等：宿主可在受管 MCP／hooks／AGENTS 围栏外追加；section 目标把当前快照写入返回映射，图目录仍钉死历史 after。python／node／cli 只核对 argv 形状与跨条目一致（同形状路径对调仍通过）。未知 selector 与受管节漂移 fail-closed 为 `state-conflict`。不代表 live HOME 接线或 P2-07 已授权。
- P1-23将契约路径包含判断的祖先身份复用为同一次调用内的`samestat`，不再在嵌套比较中反复`samefile`/`stat`同一文件；新增文件从独立到硬链接再分离的重检回归，符号链接和大小写语义不变，且无跨调用缓存。
- P1-22修复部署共享根检查被根内无关符号链接阻断：迁移部署执行不再对共享根做全树快照来判断存在性，改为逐组件拒绝符号链接的轻量 lstat 检查；共享根本身是链接、文件或特殊项仍 fail-closed，缺失根仍以 0700 创建，目标资源的漂移核对不变。此前用户 home 根里任何无关 symlink（如 hooks/plugins 指向其他配置目录）都会让每条共享部署操作以泛化的 precondition 错误阻断。
- P2-05修复 migration cleanup 消费 failed verification 时删除先于回执成功门：cleanup 现在在任何删除之前拒绝 status 非 verified 的验证文档（`unverified-input`，exit 2，零删除）。此前首次 cleanup（无续作回执）会先执行资源删除，回执封存阶段才命中 verified 绑定门，导致删除已发生而 cleanup receipt 无法保存；带既有 cleanup receipt 的续作路径原本就在初始绑定拒绝，行为不变。verify 为 failed 状态封存验证文档的能力不变。
- 迁移 plan 判断 OMP 家目录是否存在时不再整树扫描。路径上每一级，包括父目录，都按 no-follow 拒绝符号链接；子目录里的无关符号链接不再阻断存在性检查。根本身是链接、文件或特殊项仍拒绝，不存在不创建，也不改共享路由文件。
- 迁移 apply 的路由批准只认调用方传入的 `--routing-approvals` 文件，不认重封 manifest 里的路径。该文件 SHA 必须等于 sealed 记录，操作从这份文件重建；路径也不能落在 evidence/apply 写入根里。没有这份文件时，必须显式传 `--no-routing-approvals`，并且不得对 `AGENTS.md` 追加暂停块或删除管理块。批准文件还必须带安装包 `assets/routing-approval.pub` 验得过的 Ed25519 签名。公钥不从 manifest 或调用方路径读取。调用方把批准路径指到攻击者文件时，签名对不上就拒绝。plan 只有显式 `--routing-approval-key` 才签名，且私钥路径不进 manifest。仓库不保存对应私钥。未写 live。
- 同一实现生成的迁移 apply，带回执重试时不再先用 live 当前字节对照批准前快照。已成功且 live 仍等于回执 `after` 的路由替换会跳过，不写第二次；live 被改后仍是 `retry-conflict`。首次 apply 仍对照批准前快照。旧 manifest 默认仍因 `runtime_versions` 不一致报 `version-conflict`。只有签名配对里的前驱，且当前 `onboard` 哈希等于该配对的后继，并传入完整成功回执、live 仍等于回执 `after`、非空备份仍匹配时，版本门才放行。配对文件不进运行时指纹，验签公钥 `assets/runtime-lineage.pub` 进入指纹。未列出的后继、坏签名、部分回执或漂移不放行。不使用路由批准私钥。
- 签名血统下的恢复续作不再在看恢复回执之前要求每个目标仍等于 apply 回执 `after`。已完成逆向步骤按绑定恢复回执的最新成功状态判断；未恢复资源按已绑定的最新正向阶段后态核对，没有后续阶段时才使用 apply `after`。未列出后继和坏签名仍拒绝。配对用内存独立密钥重签，私钥不落盘，不读取路由批准私钥；不授权 live 回滚。
- 同一资源的 cleanup、deploy、apply 逆向步骤都成功后，续作不再拿每个历史 `after` 去比当前文件。只校验计划顺序里该资源最后一次已成功步骤的当前态。更早的成功 `after` 只是中间态。只 mock 文档加载和绑定门的测试只证明预检选择，不是完整证据链。批准路由替换加 `init-projects` 部署会让同一 `AGENTS.md` 资源同时有 apply 和 deploy。该链经真实 plan、apply、部署证据、`plan_recovery` 和两次 `apply_recovery`，不 mock 绑定、上下文或累计校验；续作是 `already-complete`，文件未改。未执行 live 回滚，不标 done。
- 修复签名前驱 manifest 的 apply／deploy 同资源链在部署后被早先 apply 后态错误阻断的问题。上下文先验证阶段绑定，再按 apply→deploy→cleanup 的已知实际后态及成功逆向状态判断；未知状态不回退。失败但已知变更的部署仍禁止普通续写，只能在保留备份和明确恢复计划下逆向恢复。缺失阶段、错误 apply 绑定、漂移、未知后态或损坏／缺失备份仍拒绝；新增前驱重叠部署与真实写后故障恢复回归。
- 迁移血统回归不再把本机运维配对误当所有 CI 解释器的固定指纹：删除源码字符串／固定前驱／本机后继相等的偶然实现断言，前驱恢复场景使用独立签名夹具绑定执行环境的实际指纹。真实安装配对仍由授权环境只读核验，生产版本门不放宽，不以跳过测试处理跨平台差异。
- 迁移 plan 不再把 `.trellis` 下被 Git 忽略、且不在已知布局里的杂项当成未分类阻断。这些文件仍留在目录快照里，后续整目录 cleanup 会一起删掉。`tasks`、`spec`、`lessons` 即使被 ignore，也仍要走批准，避免漏掉被忽略的 `task.json`。未被忽略的未知文件会汇总后停下，不自动删除。

- 将完整 findings 台账归档为 `docs/archive/sbtd-workflow-v2-findings.md` 的问题／状态表和完整字段表：保留 199 项问题、22 条策略与审查记录、全部原级别与历史；用户确认的 16 项闭环后为 195 fixed、4 dismissed，移除旧 `findings.log` 并更新文档入口。
- 补充 Linux 大小写敏感路径与原生 Windows 私有目录 ACL 的明确 CI 步骤，保留 Windows junction 拒绝测试；平台条件 skip 不作为该平台验证通过。
- 原生 Windows ACL 补测发现新建私有目录仍可能保留显式非受信规则；改为仅对本次创建的目录构造干净 DACL、设置当前 owner。已有目录仍只校验、不自动修改权限；测试覆盖权限变宽后的拒绝与内容保全。
- 修复延期项中的遥测并发覆盖风险：不存在时原子创建，已关闭配置只读；需要修改的已有配置明确阻断，保留所有未知字段，不以本进程锁冒充跨进程CAS。
- 迁移未完成workspace/session上下文要求绑定已批准的私有handoff；复用既有摘要格式、保护规则及复制／恢复链，不自动选任务或生成批准。辅助报告补类型化内容及来源校验，仍不能替代真实API smoke。
- 补齐迁移 Markdown 链接/图片的 Windows 盘符相对路径拒绝：`C:secret.md` 不再被误当外部 scheme 放行，含编码形式同样校验；保留既有协议安全策略和退出码分类，不混入 HTTPS-only 或禁止全部 data URI 的策略变更。
- 全量复核 `findings.log` 后修正现存任务状态、迁移、Graft 接线及 CLI 报告缺陷；逐项保留原严重级别和历史，并记录本轮核验依据，不将历史已修复项重复计为新修复。
- 任务路由在持久化前先选择新任务 ID，保存已接受推荐的理由和风险，相同已持久化选择不再重复确认；handoff 仅与最新快照去重，新名称使用定长任务 ID 摘要，旧 hex 名称仍可读取。
- 安装器源完整性检查补齐状态模块；仅 telemetry 变更使用对应确认文案。迁移模块缺失返回脱敏 blocked JSON，文本 plan/check 展示 Graft 阻断原因，身份初始化展示实际写后结果，接线 blocked 保留退出码 2。
- PowerShell 使用严格参数绑定拒绝已移除参数，内部 project-only 执行模式不再写入公开 `Action` 的受限取值；真实解释器回归覆盖成功与拒绝路径。
- PowerShell workflow forwarding 把 Windows 拆开的 `--source-root=D:` / `--source-root=D` 与后续 `\\path` 重新拼成完整路径，避免 `D:\\...` 被解析成盘符 `D`。
- 两安装器在全局/可选项目安装和 MCP 写入之前执行完整项目前置检查，避免最终拒绝 scaffold 冲突时已经产生副作用；`check-projects` 同步支持实际 `--skip-project-agents` 检查范围。
- RTK真实性检查改在私有probe HOME/cwd执行，避免只读check创建用户history.db；报告明确隔离验证范围，不把结果当作用户历史目录权限证明。
- 显式developer初始化保留脚手架实际写入结果，身份阶段失败仍返回完整单份JSON；项目根中途消失按项目报告blocked/failed，保留此前成功结果，不冒称批次回滚。
- P1-04补救按每个MCP请求重新验证当前图，防止Stop／部署替换后被长连接绕过启动守卫读取；生成Python命令先隔离启动环境，旧未隔离hook不再被默认为foreign。失效仓根不影响无关hook事件，native提前退出和host慢读不再导致解释器崩溃或截断已接收响应。

### 文档
- 将 README 改为默认英文 `README.md` 与头部互链的 `README.zh.md`，参考 Jev Skills 的导航、技能目录和 Agent 提示词结构；前置安装、升级、项目初始化及三模式任务示例，覆盖全部 14 bundled／19 external Skills，并链接既有详细契约。
- 删除独立 `README.html`，将现行维护规则、版本化 automation prompt 与阅读入口切换为双语 Markdown；保留历史发布／任务／lesson 证据，不改变安装运行时或同步 live automation。
- 精简本仓 `docs/lessons.md`，保留阅读协议、topic 路由与少量带详情链接的高频提醒；索引仅负责检索，完整 lesson 与作者块保持原文。移除入口中过时的根 `.gitignore` 五行摘要，改为引用现行规则；同步两份 README 与版本化 automation prompt 的导航、历史边界及 lessons 只读范围，不同步 live automation。
- 升级参考与 README 两入口明确四项保留契约：缺失 host 仍安装，受支持的嵌套安装由同基线已安装副本续作，restore intent 后 absent 保持续作窗口，OMP 隔离探测仍限 user-wide。版本化巡检提示同步这些边界，不改 live automation。
- 主 PRD 补充 P3-05 验证环境与旧 Graft 接线退役任务，覆盖临时运行时、隔离 HOME 与受管旧 MCP 绑定；正式发布前完成运行依赖退役或必要保留交接，备份销毁仍归 P3-04。明确方案确认不等于替代已部署，不授权清空 TEMP 或整个宿主账户目录。
- 新增 `docs/assets/codex-omp-host-mode-smoke.md`：整理 P1-15 Codex/OMP host smoke 的复用验证口径（opt-in、skip≠绿、读事件与助手回复、persist 信号、AC-20 不再复测六格）。
- `ENTRYPOINT.md` 当前 canonical Skill 改为 `writing-for-agents`。`writing-great-skills` 只保留为迁移别名，不再作为当前安装名。


- 交付 P0-03 任务数据契约与声明式 schema，明确本地／共享任务的唯一事实源、active 引用、父子关系、状态历史及跨文件恢复边界；这是实施前协议资产，不代表 Onboard 已提供 v2 任务读写或迁移能力。
- 准备 P0-04 `sbtd-task` 公共／lite 入口及 strict、状态、handoff 按需 references；候选使用非 discovery 文件名，正式入口与 catalog 在 P0-07 原子切换，不提前宣称已安装或激活。
- 明确完整 `grill-with-docs` 后三模式共同执行具名 DDD reviewer 门禁：必须有独立可见通过结果，缺失不可用时阻断相关确认／设计；普通无关工具降级不受影响，不以 default/lite 替代检查绕过。
- 准备 P0-05 全局／项目公共路由和无全局 Skill 的安全 fallback；方法、工具与输出模式协议按需加载，输出压缩不改变执行模式。AGENTS 与 sbtd-task/catalog 在 P0-07 同批激活，避免先发布悬空调用。
- 准备 P0-06 lessons 身份与历史保留规则：本地新身份优先、仅缺失时读取主 checkout、首次写入窄授权、异常不绕过、ID／marker不改名；旧身份仅用于显式迁移。完整Skill候选与新路由在P0-07同批替换，不提前创建身份或迁移数据。
- P1-17同步实际入口文档：README两份入口、Onboard `SKILL.md`／`REFERENCE.md`、bundled `sbtd-task`的`SKILL.md`与`references/state.md`记录任务状态helper的真实调用形态与工程边界；版本化automation prompt把两个新脚本纳入只读评估范围，不同步live automation或真实HOME。
- P1-18同步实际入口文档：README两份入口、Onboard `SKILL.md`／`REFERENCE.md`、bundled `sbtd-task`的`SKILL.md`与`references/state.md`、`references/handoff.md`记录路由／重绑定／handoff helper的真实调用形态与工程边界；版本化automation prompt把`sbtd_task_routing.py`、`sbtd_handoff.py`纳入只读评估范围，不同步live automation或真实HOME。
- P1-19同步实际入口文档：README两份入口、Onboard `SKILL.md`／`REFERENCE.md`与bundled `lessons-record`的`SKILL.md`／`references/identity-migration.md`记录`DeveloperStore`只读链／plan／ensure与显式`--developer`入口的真实边界；版本化automation prompt把`sbtd_identity.py`纳入只读评估范围，不同步live automation或真实HOME。
- P1-11同步README两份入口、Onboard `SKILL.md`／`REFERENCE.md`、版本化automation prompt与CHANGELOG：当前主线改为`Codex / OMP + sbtd-task + Graft + Chrome DevTools MCP + Playwright + Maestro`，版本检查专用规则从Trellis监控改为Graft固定pin/source、native lifecycle、telemetry、MCP/hooks与平台接线核验；REFERENCE补充备份保留／人工授权销毁规程与恢复可用／证据不足边界，明确cleanup、恢复成功、任务完成均不删除备份，pre-manifest终止分支删除前须先保存并回读custodian、候选归属、精确范围、本次独立授权和实际确认时间，缺任一项或保存/回读失败均blocked、零删除、不得done。旧Trellis／GitNexus仅保留迁移与历史边界，不同步live automation或真实HOME。
- P1-12同步README两份入口、Onboard使用说明、身份迁移指针及版本化automation只读范围；明确私有子对象文件输入、同一apply批次内累计报告时间窗、已证明不存在的退役资源不属于保留资产，以及不改原生报告schema的无分支ref表示。声明tomlkit依赖及已安装副本的准备边界；不触碰真实HOME或live automation。
- P2-03 同步 README 两份入口、Onboard `REFERENCE.md` 与版本化 automation prompt 的恢复保证边界：恢复成功只表示绑定范围内受管数据／配置按回执 reconcile，不承诺已退役 Trellis 运行时可执行或可写，不调用、重装或恢复旧运行时，旧运行时 `runtime_readiness` 保持未验证；同一运行时部分回执重试与签名前驱—后继配对加完整成功回执的前驱接受是两条不同路径；live 回执证明实际状态，故障／部分重试／恢复续作由独立隔离测试分别证明，二者互不替代，文档不声称新证明已通过；部署接受前维护不自动结束，备份保留不变。不同步 live automation 或真实 HOME。

### 变更

- 迁移 plan 接受显式 `private-only` 跳过整个旧任务目录，或私有保全 spec 文件；不生成任务投影、不要求 handoff。session 指针只对完整跳过放行，未知、外部或部分跳过仍拒绝。lessons 仍必须 share/redact。缺批准或部分跳过仍然 blocked。不写死任务名，也不授权 apply。README 两份入口和版本化 automation prompt 同步该例外；live automation 不在本轮同步。
- P0-07将完整sbtd-task、全局／项目规则及lessons-record候选移入正式安装源，catalog由15个bundled调整为14个，19个required external保持；删除两旧Trellis Skill源目录，不保留alias或包内旧入口副本。
- 项目setup停止安装／调用Trellis，Python与两安装器移除旧username／platform／skip参数，结果使用`sbtdInit`／`sbtdProjectSetup`。安装前检查全部所选项目，保全既有task、identity、spec、lessons及旧数据；不默认生成bootstrap或完整目录树。
- 旧bootstrap提示改为保全数据并请求显式迁移，不再调用已退役Skill；README、Onboard说明和版本化automation prompt区分已切换payload与尚待P1完成的v2生命周期，本项不执行真实HOME部署或旧数据清理。
- P0-08项目ignore模板保留56条通用规则、移除14条旧Trellis/GitNexus规则并新增`/.sbtd`、`/docs/handoffs`、`/graft`、`/.graft`；安装器语义探针与模板同批对齐。共享任务／规范／lessons和manifest保持可追踪，旧项目规则仍仅追加不自动清理，不改源仓根ignore。
- P1-09完成bundled旧路由清理与模式分层：templates移除identity-migration reference外显Trellis/GitNexus/`$trellis-check`/Channel preflight与trellis匹配，book-*与BDD改为strict强制、default/lite按风险或项目规则明确交付；保留退役Skill仅作历史边界，不恢复旧路由。
- P1-10将ENTRYPOINT版本监控与可恢复sync source切到`Codex / OMP + sbtd-task + Graft`：新增Graft `v0.18.0`固定监控行，Trellis/GitNexus不再保留当前监控或使用要点；README、Onboard文档和版本化prompt的当前主线同步更新，旧内容仅保留迁移边界。
- 共享规则验收覆盖公开固定分支，避免精确忽略旧lessons入口、context ADR、undated归档、平台flow、React Bits、任务附属产物、UI上下文、测试源码或Git控制文件时误报通过；继续保留用户规则并报告来源，不恢复旧平台生成集成的无条件探针。
- P0-09将配置源仓根ignore独立切换为七行，保护`.sbtd`、handoff和Graft本地产物，保持根AGENTS本地化与ENTRYPOINT可追踪；切换前核对旧工具残留及Git索引，不复制业务项目模板，不执行真实数据迁移或全局同步。现行维护入口同步，历史lesson原文保留。

### 验证

- 原生 Windows 的 session-root MCP 回归使用带超时的后台管道读取，替代仅能处理 Windows socket 的 `select.select`；保留协议响应与项目隔离断言，不因测试辅助错误放宽生产根解析守卫。
- Windows CI 先执行原生 PowerShell Unicode profile／命令解析定点检查，再运行完整升级／恢复套件；PowerShell 隔离探针保留 Windows 的 PATHEXT 扩展名解析，不预置受管 bin 或绕过真实命令优先级。

- 增加任务 schema 的模式来源、阻塞原因、完成时间、入阻塞、路径形状、版本类型和日期边界回归；区分历史元数据事件与新入阻塞，显式配置日期断言，避免把可选格式检查缺失当成通过。
- 增加完整sbtd-task安装回归，核对references/schema/许可证及两旧目录在fresh安装中的缺席；保留存续公共文档合同、实际provider与Git marker检查，任务schema测试改读正式源。原生catalog smoke逐字验证已审查载荷到正式源及安装副本，不把安装层通过扩大为完整v2或host通过。
- 项目ignore增加真实CLI＋Git红绿验证、根级普通文件／symlink保护、同名业务子目录不误伤及共享路径冲突来源检查；原有NUL解析、环境秘密、追加幂等和未验证状态边界继续保留。
- P1-14增加 producer→verify→cleanup→recovery 集成回归：完整链恢复旧树且 cleanup/recovery 均保留原始备份；部分 cleanup 可从累计收据续作，缺 cleanup 证据的 recovery plan 为 blocked、零删除且不生成收据。新增 CI 工作流契约测试固定 clean SHA 验证命令。


## v2.0.0-rc.4（2026-10-12）

tag 已创建并推送，指向 PR #117 的实际合并提交 `34767ae497b29e30c1b96c41f83a99de9ce0aff8`；该 SHA 的完整三平台 [main CI](https://github.com/KunoLu/640-skills/actions/runs/38235028075) 全绿。正式版仍未发布；源码发布与本机／项目升级分别验收。

### 修复

- 将旧批次清理的当前依赖与历史部署发现输入分开：只有可证明不影响清理工具、作用域、所有权、实际 vendor footprint 或保留资产的配置变化才可继续退出；部署与现态验收仍保留原有漂移拒绝，不恢复用户配置、不改写旧 manifest。
- 清理首写前及回执发布前重新核对保留资产、项目根／分支／HEAD 和证据；晚期漂移保留已测得的删除结果与原件引用，不误报成功，也不因升级证据出现新 alias 而丢失失败回执。

### 新增

- `migration --phase cleanup` 可成对接收 `--upgrade-plan`／`--upgrade-receipt`，以一次完整原生 Onboard 替换的实际前后态和原件承接旧批次历史信任；不新增本机签名，不执行备份中的代码，不接受任意公钥或多跳续接。
- 升级续接证据只适用于已完成、已验收原始批次的清理，不授权 apply／deploy／recovery 或后继 followup；旧证据、失败记录与备份继续保留。

## v2.0.0-rc.3（2026-10-12）

tag 已在 `main` 创建并推送，指向 PR #115 的实际合并提交 `6c6e6637c00dc3ad7b0e9e6fcbeef6b4333ebb6f`；该 SHA 的完整三平台 [main CI](https://github.com/KunoLu/640-skills/actions/runs/38195096435) 全绿。正式版 v2.0.0 仍未发布。Onboard 分发载荷与 rc.2 相同，本次优化测试与取证，不包含本机／其他项目安装或真实宿主验收。

### 验证

- 调和与 followup 的目录无关边界测试使用较小安装目标集合，减少无关 Skill 目标触发的成对路径校验。仍调用真实清单选择，保留完整 Onboard 启动器包、两个兄弟 Skill 和全部非目录路由；完整清单生命周期、目录升级与已安装副本锚点不变。
- 不修改生产校验算法，不缓存安全结论，不复用路径绑定回执；每例的 HOME、vault、证据及漂移子场景保持独立，真实迁移／恢复阶段不省略。
- 同一 runner 内三组完整 Linux 配对，在候选承担全部共享准备／上传开销、原生 Linux 聚合及时间戳余量的保守口径下，中位成本由 39.48 分钟降至 30.61 分钟，下降 22.46%；三轮分别下降 15.15%、22.46%、27.06%，保留波动，不将分摊口径冒充独立作业耗时。
- 同一生产源码树的全量父解释器覆盖集合完全保持：17,403 个已执行行、7,682 个已执行分支；每轮 2,081 例及全部原生 skip／子场景身份与理由一致。隔离 CLI 继续由真实黑盒案例补证，不将父进程覆盖扩大为子进程或真实宿主验收。
- 实际发布 main CI 完整等待 17 分 33 秒，全部 runner 累计 67.95 分钟；两轮 PR CI 与该 main CI 的等待中位数为 19 分 32 秒，低于 25 分钟。原生 Linux 2,081 例／48 个 skip 事件、Windows 474／32、macOS 658／20；必需原生项全部实际通过。

### 文档

- 明确原生 skip 事件与父测试状态的统计边界，保留被跳过子场景的身份和理由，避免聚合摘要低报。

## v2.0.0-rc.2（2026-10-11）

tag 已创建并推送，指向 PR #113 的实际合并提交 `aabd23652a80b5ff3d04093189597b5e6aa75381`；该 SHA 的优化后三平台 [main CI](https://github.com/KunoLu/640-skills/actions/runs/38146905062) 全绿。正式版 v2.0.0 仍未发布，本机安装、签名及真实宿主验收不包含在本次源码发布中。

### 修复

- 隔离宿主 probe 增加精确 Skill 链接目标授权：`upgrade --phase authorize-link` 绑定原计划、宿主、链接与目标身份和内容摘要；verify 仅在明确 probe 批准后，将匹配目标安全物化为临时普通目录。原链接保留，未授权访问、嵌套链接、特殊文件、错误身份及复制漂移仍拒绝；不改变安装／迁移／清理链接政策。
- 对象身份同时封存纳秒级 ctime，拒绝 inode 号码被重用后的链接替换；不以相同链接文本或相同内容替代对象版本证明。
- 目标拼写不符时在元数据探查前拒绝；授权准备与消费都保留原始路径的完整 nofollow 证明，不因规范化比较而访问未批准的网络目标。

### 文档

- 补充两阶段授权命令、失效重审条件和持久行为场景；隔离物化、真实宿主加载与 `live_reload` 继续分别报告。同步双语 README、Onboard 使用入口与版本化 automation prompt，不操作本机安装或 live automation。

### 验证

- Linux 全量集合按模块分片，Windows 原生集合去除重叠选择器后分片；保持 macOS 原生范围、最低 TOML 编辑器变体及既有必需检查名称。聚合门拒绝失败、取消或未完成的分片；新测试仍由全量发现自动纳入。各原生分片在封存测试输入前完成 Python 字节码准备，聚合解释器同样固定版本。
- 路径选择回归保留真实公共升级 API、隔离执行器及两个可运行候选，使用小型临时测试载荷减少无关整包成本；真实完整包的已安装副本重试／恢复仍独立保留。同一失败边界用例的两阶段共享只读 bootstrap，目标和 vault 继续隔离。
- CI 保存逐例结果、耗时、skip 原因与中文摘要。只取消同一 PR 已被新提交替代的运行，不取消不同 main 提交的发布验证。
- 必需原生边界区分 pass 与 skip／预期失败；Windows 权限、路径与 Shell 及 Linux 大小写敏感检查未实际通过时，分片与聚合门不接受成功结论。
- 发布提交的完整 CI 等待为 21.97 分钟，较旧 main 同口径的 45.83 分钟降低 52.07%；总 runner 时间为 84.80 分钟，高于该旧样本的 80.23 分钟，成本下降未形成稳定证明。保留基线波动和新增覆盖，不把并行当作成本保证。
- 测试优化在相同旧生产源码上的已覆盖行／分支集合逐项不变（18,141 行、7,923 分支）；该覆盖只统计父解释器，隔离 CLI 子进程由真实黑盒回归补证。

## v2.0.0-rc.1（2026-10-11）

本候选包含下方 `v2.0.0` 草案的累计能力及本节变化；正式版草案继续保留，不代表稳定版已发布。tag 已创建并推送，指向 `c8a9b65ed7691622ae5aafbf1b3618084c807b47`；该实际发布提交的三平台 CI 均通过。发布日期为本机日期，源码／安装／原生检查与真实宿主验收仍分别报告。

### 新增

- 新增 `migration --phase reconcile`：在 apply 完整成功、部署证据缺失时，显式确认后直接验收当前配置、图和保留原件，不回滚、不重部署、不补造历史回执；只生成新鲜私有报告和全新现态证据，拒绝路径冲突、资源漂移、原件缺失或检查失败。
- 现态证据保留 `current-state`／`historical_execution: unknown` 来源及原输入哈希，标准 verify 明确报告 `acceptance_basis: current-state`；重试和后继消费保留来源及历史缺失路径保护，原有验签、安装、清理与恢复授权边界不变。
- 任务状态新增 `cancelled` 取消终止态：不冒充 done、completed_at 保持 null、不级联取消子任务；归档、显式重开及 handoff 提醒按终止语义处理，历史事件保留。
- 旧任务投影保留 cancelled／blocked 真值：只使用可证明的取消／暂停时间和理由，缺失事实保持未知，不伪造完成或恢复阶段；取消记录与历史阻塞快照要求配套的新任务 schema／运行库。

### 修复

- 现态证据发布前再次核对全部部署目标及新鲜报告引用，拒绝完整上下文验证期间发生的资源漂移、报告修改或删除，保留现场且不签发过期成功证据。
- 修复现态证据来源路径仅核对记录摘要的缺口：实际消费重新验证 manifest／apply 引用对象的安全路径、类型与内容摘要，拒绝不存在、异内容或链接替换；纯 JSON 契约保持无磁盘读取。
- 修复观察者 Onboard 指纹仅检查格式的缺口：只接受 manifest 同运行时或经签名批准的精确前驱→后继观察者，拒绝反向／无关配对和无效授权；历史后继消费不强制观察者等于当前运行时，累计来源不改写。
- 跨运行时现态观察内嵌原始验签授权 `observer_lineage`，后续配对从 A→B 轮换到 B→C 时仍可证明历史 A/B 观察者；只用已安装受信公钥验证，不接受证据自带信任根。旧无内嵌证明的记录仅按同运行时或仍可验证的当前配对消费，授权缺失时失败关闭。
- verify 在返回前、cleanup 在首次副作用前及回执保存前重新核对来源。晚期漂移发生在真实清理之后时，保留实测操作及原件引用并保存非成功累计回执，不丢弃结果或误报清理完成。
- 现态观察区分 OMP 原件的 file／absent：存在但零字节的 MCP JSON 按 `invalid-json` 拒绝，不能借现场已生成文件的非空大小绕过原输入校验；真正 absent 的写入与继承无写分支保持有效。
- 补齐恢复首写／回执发布、恢复计划、现态证据及 followup 计划的最终来源门；晚期恢复失败保留真实完成步骤和保护原件。间接依赖现态证据的 followup 同样复核一层祖先，不能因当前回执没有来源标记而绕过；部署发布失败保留实测 `operationResults`，不伪称存在可用回执。
- 将现态语义／来源链验证与最终快照复核分开：在较重验证之后刷新目标、原件、报告与已绑定来源，不在快照后重新解析祖先；verify 的现态接受同时覆盖真实观测到的 absent 资源，既有失败／阻塞结果不改判。快照复核不等于跨进程事务。
- 原生累计部署重试也在来源校验之后刷新成功目标、保留原件、报告和固定来源；晚期漂移返回失败并保留 `operationResults`，不发布过期累计证据。无现态来源的普通部署路径保持不变。
- 最终现态输入快照包含 `agents_no_touch` 的目标与模板引用，覆盖因无写承诺而不进入部署操作列表的 AGENTS；晚期漂移不得被累计重试或现态观察接受。
- AGENTS 标记移除后的重试按封存原始状态判别 no-touch，不把合法迁移后态误判为计划时已对齐；真正的 no-touch 保护不因伪造移除操作而绕过。

### 验证

- Linux 全量 CI 窗口从 40 分钟调至 60 分钟：实际运行已输出 2009 项无失败结果，但作业在 40 分钟上限被取消，后续兼容检查尚未完成；保留全量与后续检查，不以取消作业冒报通过。

### 候选边界与已知限制

- 代码提交、三平台 CI、安装载荷、原生工具检查、真实宿主加载与业务端到端验收分别报告；本机或历史 dirty 证据不冒充当前候选 SHA。完整宿主方法矩阵与 token 收益仍保留既有 partial／measured-not-met 边界，P3 观察和正式发布验收不因 RC 准备完成而关闭。
- 新安装／新计划使用所选包的运行时；旧 manifest 跨运行时续接仍需精确签名配对及完整证据。操作者的本机信任根覆盖不属于通用发布载荷，不将本机签名包或私有迁移报告复制回仓库。
- 原两项来源元数据 P2 及终审发现的历史授权保留／消费末端漂移问题均在根 `findings.log` 保留发现、修复状态与回归记录。被引用原输入须继续可安全读取且摘要匹配；新内嵌授权字段需要匹配的生产者／消费者。内容摘要仍不等于来源身份认证，现态验收仍不证明未知历史执行。
- 大批次校验可能长时间没有最终 JSON 输出；本机 994 项 apply 结果的样本中，reconcile 约 139 分钟、verify 约 110 分钟。这是特定环境实测，不是性能保证或瓶颈归因；应保留原生输出与最终退出码，避免超时后重复启动同一操作。
- RC 不授权真实安装、workflow sync、迁移／恢复、清理或备份处置。现态验收不补造历史执行记录，备份继续保留。

## v1.0.15（2026-09-16）

### 新增

- 新增第 19 个 required external Skill `i-have-adhd`：catalog 注册 `skill:i-have-adhd`（`ayghri/i-have-adhd`，subpath `skills/i-have-adhd`），经 `promote-external-skills-stable` 以 pin commit（`4092de07…`，MIT）冻存进 stable set；`init` / `reset` 从 stable 镜像离线自动安装 / 重装，`check` 报告缺失并提示 `install-external-skills` 修复（不阻断退出码）；安装完整 i-have-adhd Skill 目录（SKILL.md + agent metadata），不安装上游 plugin / hook / extension。全局 AGENTS 模板含使用规则（显式启用、`normal mode` 与 caveman 同时退出、输出契约保护区优先、时间估计服从 harness、错误原因 evidence-first）。此前的 opt-in 交互 Skill 方案与 `install-i-have-adhd` 子命令已按决策整体移除。
- `caveman` 增加钉版 workflow Skill payload 维护：缺失仍保持 opt-in，已安装 payload 按 v2.6.0 基线判定 `current` / `outdated` / `unknown-drift` / `abnormal`；已知较老副本备份后升级，可替换的非 symlink 异常副本修复（symlink fail-closed 报告），更新或自定义副本只报告不覆盖。替换 / 备份范围只含 `caveman`、`caveman-*`、`cavecrew`、`cavecrew-*`，更宽的 `caveman*` / `cavecrew*` 前缀仅用于 symlink 侦测；不触碰 hooks、statusline、plugin、extension；监控仅跟踪 `v*` installer / skill tag，基线升级需人工评审后同步 ref、revision、hash 与测试。
- 将 stable set 全量刷新到 2026-09-14.6：mattpocock/skills、impeccable、ui-ux-pro-max-skill、shadcn-ui、ponytail 与 i-have-adhd 均固定到当日 main revision；其中 impeccable 自 4.1.2 整体替换为 4.3.1，原脚本树由统一 `impeccable` CLI 启动器（随 `VERSION` 发布，按需下载或使用缓存 engine）取代，浏览器侧 `live-browser*.js` 保留；promotion 同步更新目录树 digest、LICENSE / NOTICE 与第三方归属。

### 修复

- 修复 `init` / `reset --json` 的嵌套安装报告丢失：安装事务与展示分离，父流程在单份根 JSON 的 `requiredExternalInstall` 中保留来源、transaction 状态、`rollbackPath` 与恢复错误；失败提前返回也不丢弃恢复信息，原退出码不变。
- Caveman symlink fail-closed 补全：`caveman/SKILL.md`、任意 `caveman*` / `cavecrew*` 前缀兄弟条目（含 `caveman.local` 这类非 `-` 分隔名、含 dangling）为 symlink 时统一判 `abnormal`，异常 core 内任意深度的嵌套 symlink 同样阻断修复；symlink 侦测用前缀匹配，替换 / 备份范围仍只限 `caveman` / `caveman-*` / `cavecrew` / `cavecrew-*`；staging 目录、staged 读取与源扫描阶段的文件系统错误也返回结构化 `failed`，`plan` 输出 `plannedAction: blocked` 与 `blockedReason`，`init` / `reset` / 显式 `install-caveman --yes` 均拒绝替换且不 clone；人类可读 `check` 现渲染 maintenance 状态、pinned ref、planned action 与 blocked reason。备份决策以 clone 后重算的 family 为准：clone 期间出现的已知旧版或可修复副本同样先备份再替换。
- `check` / preflight 的修复提示（`install-external-skills`、`install-caveman`、`ensure-npm`、`install-java`）改为通过 `onboard_command()` 生成已安装脚本的绝对路径命令，POSIX 用 `shlex.join` 使空格、`$`、反引号、glob 等元字符保持字面量；Windows 仅支持 PowerShell：普通参数不加引号，仅含特殊字符的参数用单引号包裹（`'` 翻倍），需要引用 argv[0] 时才以 `&` 调用，并在提示前标注 “Run in PowerShell:”，不承诺 cmd.exe；此前的 `python scripts/onboard.py …` 相对路径只能在 Skill 目录内执行。
- Caveman 版本识别增加完整受管 family 的目录集合与内容指纹校验：已知核心配自定义 sibling、部分安装或混合版本均停止覆盖；异常核心不能授权覆盖未知 companion，非 symlink 异常核心仅在不存在未知 companion 时可修复，任意顶层或嵌套 symlink 均保持 fail-closed 报告。staged source 校验完整 pin，下载后、替换前重新检查本地漂移，保留原备份 / 回滚机制与可选维护边界。
- 修复 Caveman 版本识别的 partial family 漏判：core `caveman/` 缺失但 companion 命中已知 family 时，不再判为普通缺失安装（`missing` 仅保留给完全无 family 内容的布局），统一归入 `unknown-drift` 并进入 `attention-required`，只报告不覆盖；新增回归测试覆盖该布局。
- 修复 impeccable stable 副本内 5 组问题（按用户决定在本仓直接修复，与 pinned 上游形成有意差异，建议上游修复后重新 pin）：`live-browser.js` 三处用户可见 `live-poll.mjs` 文案改为 `impeccable live-poll`，五处指向已删除模块的维护注释改为引用 compiled engine；Svelte 会话 reset 只清理当前会话的 handled 记录，不再清空全部历史；`impeccable.cmd` 在 delayed-expansion 子例程内校验 `IMPECCABLE_DOWNLOAD_BASE`（仅放行 URL 字符），并为 `.part` / `.sha256` 暂存文件加入进程唯一后缀。MANIFEST 的 impeccable `treeSha256` 同步重算。
- Caveman 文本 `plan`、显式安装及 `init` / `reset` 维护报告展示拒绝原因、备份路径和恢复错误，不再只给出笼统失败状态。

### 变更

- 将 `AGENTS.project.md` 标题从「Codex 项目级规则」改为「项目级规则」，避免把项目级模板误绑到 Codex host。
- `sync` / `同步` 的 required external Skill 安装步骤扩展到 `i-have-adhd`：sync 在复制 Onboard 后用已同步 `onboard.py install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt,i-have-adhd` 从 stable mirror 安装并校验 5 个 `SKILL.md`；`i-have-adhd` stable 路径同样不得作为同步表 `cp` / `rsync` 行。README 两份文件与版本化 automation prompt 同步更新。
- 对齐 GitNexus 可迁移索引存储、content retention 隐藏正文及 `gitnexus embeddings` 原地补向量边界。外部存储通过 `gitnexus status --repo <registered-target> --json` 的 `storagePath`（或带 `--repo` 的文本 `Index storage`）确认；该命令不证明工作树新鲜度。工作树 CLI `status --json` 使用 `up-to-date` / `stale`，与 MCP 的 `current` / `behind` / `diverged` / `unknown` 分开判断，不能因健康状态不是字面 `current` 而反复重建。
- 项目 `.gitignore` 模板增加 `/AGENTS.md.*`，忽略 Onboard backup-then-overwrite 留在仓库根的 `AGENTS.md.YYYY-MM-DD-N` 备份；活的 `AGENTS.md` 与共享 `.agents/skills/**`（含 React Bits）仍默认可追踪，未重新加入会覆盖该目录的 `.agents/`。

### 文档

- `README.md` / `README.html` 的项目 `.gitignore` 示例同步 `/AGENTS.md.*`。
- README 两份入口明确 Caveman 替换白名单与更宽的 symlink 侦测范围，并补充完整 family 身份和 JSON 恢复结果契约；版本化 automation prompt 将 family 指纹纳入人工 pin 评审边界，不同步 live automation。
- 修正恢复与验证 lessons：私有目录保存完整文件快照，备用 patch 包含 staged + unstaged 并另存未追踪文件；恢复不改用户索引。管道示例立即保存并返回 runner 退出码，而不是只打印状态。

### 验证

- 契约测试确认模板含 `/AGENTS.md.*`、不含 `.agents/`，并用 `git check-ignore` 证明根备份被忽略、`.agents/skills/**` 仍可追踪。
- 契约测试锁定 catalog 条目、stable manifest 仓库 / Skill 条目、冻存字节 SHA-256 == 已评审基线（`3170b16a…`）、LICENSE 存在与 `REFERENCED_SKILLS` 成员；`python -m unittest discover -s tests` 全量通过；隔离目录 `install-external-skills --skills i-have-adhd --source auto` 离线安装冒烟通过。
- Caveman 维护回归套件覆盖 family 指纹识别与 fail-closed 边界：嵌套 symlink（含异常 core 组合）、未知 companion、post-clone 漂移复查、备份 / 回滚恢复、以及 `run(init)` 与显式 `install-caveman` 从缺失状态的 JSON 派发路径（升级成功且保留备份）；i-have-adhd 套件覆盖缺失 / 部分安装的自动重装与 stable 镜像 checksum 拒绝。

## v1.0.14（2026-09-08）

### 修复

- 修正 `lessons-record` 把新 ID 格式写成仓库内全局唯一的声明：该格式只保证新 ID 之间互不相同，与保留的既有 ID 共用命名空间；写入前必须搜索 ID 及其派生锚点，命中则换 slug。可选 `merge=union` 只覆盖 index / topic / archive，刻意排除会被裁剪改写的 `.trellis/spec/lessons.md`。契约测试堵住分隔名解析顺序可被颠倒仍绿、owner 只作为 ID 子串命中、以及本仓库 post-cutover 记录落在标记块外等空转路径。

### 变更

- 对齐 Codex 内置 planning / `update_plan` 默认关闭：只有当前会话工具列表明确暴露时才可使用，不得静默写入 `tools.update_plan.enabled`。
- 对齐 Codex MCP 服务器名允许 package-style（`:`, `@`, `/`, `.`）；不要把这类名称当成非法并改写配置，也不要静默写入各 MCP tool 的 `output_token_limit`。
- 对齐 GitNexus 的 watch 命令边界：`gitnexus watch` 是保留入口，只说明 `analyze --watch` 与 `gitnexus auto-sync` 的分工且不启动任一者；不要默认启动长期 watcher，索引刷新仍用一次性 `gitnexus analyze`。
- 仓库内新增 OMP 版本监控，infra 优化。
- `lessons-record` 改为按 lessons 分隔名分片写入：分隔名只取当前仓库 `.trellis/.developer` 的 `name=`（必须匹配 `^[a-z0-9]+$`，读到不合规值同样停下询问而非改写），linked worktree 回读主 checkout，读不到则停下询问；追加内容包进 `<!-- lessons:<name>:start -->` / `<!-- lessons:<name>:end -->`，只写自己的块，显著减少多人 PR 合并时的 lessons 冲突；lesson ID 同步改为 `LESSON-YYYYMMDD-<name>-<slug>`，分隔名原样入 ID，避免两人同日同 slug 撞 ID。

## v1.0.13（2026-09-01）

### 修复

- `check --json` 在用户尚无 `~/.omp` 时不再执行 `omp plugin list`，避免只读检查创建 `.omp`；已配置 OMP 时仍完整检测官方 Ponytail plugin 冲突。
- 项目 `.gitignore` 增量合并后使用原生 `git check-ignore` 验证 Trellis 必须追踪 / 必须忽略路径；既有 `.trellis/` 等宽泛父目录排除会给出具体来源行并阻断，而非文本齐全却语义失效的假绿。探针按 NUL 分隔字段读取 git 给出的判定模式，`!.en[v:]` 这类含冒号模式的反向包含不会被反读成“已忽略”。
- `init` / `reset` / `init-projects` 等写入模式的 `--json` 现在只向 stdout 输出单个 JSON 文档。此前会先输出计划文档、再输出 Trellis 报告文档，并夹杂 `Backups:`、`Verification passed.` 等散文，`json.loads` 在每次成功运行上都会失败；计划字段仍留在根层，`mode` 与 `plan` / `check` 位置一致。
- 项目 `.gitignore` 模板补上裸 `.env`。此前只忽略 `.env.local` 和 `.env.*.local`，最常见的 `.env` 反而可被提交。
- External Skill 目录校验和不再把本地生成的 `__pycache__`、`*.pyc` 和工具缓存计入指纹。此前在仓库根运行一次 pytest 会在受管 stable 快照内写入字节码缓存，使后续安装与 promotion 报告校验和不匹配；干净快照的既有 pin 不受影响。
- book 门禁路由行补回被改写丢掉的触发词。`book-ddia-data-design` 的三处路由此前都漏掉规范中的 API 所有权，`book-release-readiness` 把「deployment / rollout / migration / runtime 运维行为」压缩成只剩 deployment，Trellis fallback 还把 background job 写成 job；只命中被丢掉那一段的改动会静默跳过强制 reviewer。全局路由表、project-only fallback 与 Trellis fallback 现在逐条覆盖各 `book-*/SKILL.md` 自己列出的触发词。
- `onboard.py` 每次 `run()` 开始时重置 `UNVERIFIED_CHECKS`。此前该模块级列表跨调用累积，同进程内连续运行多个模式时，后一次会报告自己从未跳过的检查。
- External Skill 目录的拷贝、指纹与比对现在对 `*.pyc` / `*.pyo` 采用一致的排除语义：只排除文件，不排除同名目录。此前名为 `pkg.pyc` 的目录会被拷贝阶段整棵丢弃，其中的文件却仍计入 `treeSha256`，导致拷贝结果与校验和互相矛盾。

### 变更

- 对齐 GitNexus 升级后必须用 CLI 重新 analyze 的索引语义。MCP repository allowlist 未覆盖时 GitNexus MCP 对该仓库不可用，不得当作 MCP 可读；fail-closed 只读不走 MCP 写入；二者均不阻止 CLI 刷新。同时对齐已移除的非功能 group matching 旋钮、`--self-commit` 与 Codex plugin marketplace 不能替代全局 `gitnexus-mcp` 的使用边界。
- 对齐 Codex 可选 MCP 启动宽限期、项目级 plugin catalog 合并，以及 extension 可在模型前检查或替换 MCP tool result 的可用性判断。
- `AGENTS.project.md` 收敛为 project-only fallback、项目路径和硬性边界，删除全局工具 / reviewer 状态的重复副本；正常 `init` / `reset` 与 project-only 的激活边界现在明确区分。
- book-derived 门禁改为单一事实源：全局 AGENTS 维护客观触发与 Gate lifecycle，各 `book-*/SKILL.md` 独占 reviewer 状态、输出 schema、修正回路和 stop condition；Trellis 负责编排，并保留全局路由不可见时可自举的最小 objective-trigger fallback。
- 精简项目 `.gitignore` 中已被 `.trellis/*` 覆盖的运行时重复行，并移除同样冗余的 `.trellis/workspace` 条目；目录 / symlink 语义改由无尾随斜杠的 `.trellis/*` 本身提供，workspace 目录、workspace 内容与顶级 workspace symlink 的忽略结果不变。报告目录仍保持本地忽略，不要求提交 Git。
- 项目 `.gitignore` 的 `output/` 收窄为 `/output/`，只忽略仓库根的构建输出目录；同名嵌套源码目录（例如 `src/output/`）不再被连带忽略。

### 验证

- 新增 `git check-ignore` 语义探针测试、`check --json` 不创建 `~/.omp` 的回归测试，以及 External Skill 目录指纹忽略字节码 / 工具缓存的回归测试；契约测试同步断言 book 门禁的单一事实源归属，并按各 `book-*/SKILL.md` 的规范 bullet 数量逐 token 校验三处路由行的触发词覆盖，新增规范触发词时未同步路由会直接失败。每个 token 只在承载该 gate 谓词的那一行内计命中，因此 `API`、`queue`、`migration` 这类短词不会被文件其他位置的无关提及满足；此前按 bullet 取单个代表短语的写法漏检 `queue / event / stream / job`、`ETL / analytics` 与 `data pipeline`，删掉这三段不会失败。
- 新增含冒号反向包含模式（`!.en[v:]`）必须判定为“未忽略”的回归测试，以及 `init-projects --json` 成功路径解析为单个 JSON 文档的回归测试；两者均以重新引入原缺陷的方式确认会失败。
- 收紧既有断言的判定力：宽泛父目录排除的失败信息按 `文件:行号:模式` 断言具体来源记录，不再用 `.trellis/` 子串（模板自身追加的反向包含行同样含该子串，会放过丢失来源的信息）；`git` 完全不在 PATH 时的降级单独覆盖，与既有 exit 128 桩分属 `run_project_command` 的两条分支；External Skill 缓存回归测试改为枚举全部 6 项排除（`__pycache__`、`.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`*.pyc`、`*.pyo`）并断言拷贝与指纹丢弃同一集合，同时覆盖名为 `pkg.pyc` 的目录必须保留——该拷贝 / 指纹一致性此前无回归测试；reviewer `Status:` 枚举归属改为按成员集合精确比对并禁止委托文档出现任何枚举形声明，此前的子串断言在枚举新增状态或委托文档抄录截断前缀时均不会失败。
- book 门禁 lifecycle 的跨文档断言拆为逐文档独立子测试。此前全部集中在一条断言链上，首个失败即中止，一份文档漂移会掩盖同批其余文档的状态；现在每份文档、每项主题单独判定并单独报告。

## v1.0.12（2026-08-28）

### 变更

- 对齐 Trellis 的空 jsonl 启动门禁：sub-agent-dispatch 平台上 `task.py validate` 对零条 curated 的 `implement.jsonl` / `check.jsonl` 失败，`task.py start` 默认拒绝，只有用户明确要求空上下文启动时才使用 `--allow-empty-context`。
- 对齐 Trellis 的路径变更与整仓移除命令：`task.py rename`、`trellis ablate` / `trellis restore` 纳入 filesystem-safety 与用户确认边界；`[workflow-state:task_error]` 时先修复现有 `task.json`，不得另建任务。
- 对齐 Trellis 的 OMP `prompt_injection.skip_keyword`：生成的 OMP extension 与 Python per-turn hook 使用同一配置关键词跳过当轮 workflow-state 注入，跳过不等于关闭 Trellis 规则。

## v1.0.11（2026-08-27）

### 修复

- `init` / `reset` / `init-projects` 不再把空平台列表交给 `trellis init --yes`（Trellis 会因此默认安装 Claude 和 Cursor）。`--platform codex|claude|kimi` 在未给 `--trellis-platform` 时作为默认 Trellis flag；显式 `--trellis-platform` 覆盖该默认。`oh-my-pi` 仍必须显式给出 `omp` 和/或 `pi`。
- `plan --json` 增加 `trellisInit`，写出将要执行的完整 `trellis init` 命令。
- Trellis 平台 allowlist 对齐 CLI 0.6.15：补上 `kimi`、`grok`、`snow`、`dsh`。

### 验证

- 新增 `test_init_projects_defaults_codex_from_agent_platform`、`test_init_projects_rejects_empty_trellis_flags`、`test_plan_json_includes_resolved_trellis_init_command` 与版本化 `TRELLIS_INIT_PLATFORMS` 契约测试；不解析本机 `trellis init --help`。


## v1.0.10（2026-08-27）


### 变更

- `init` 对已合法的 bundled / required external Skill 壳（普通目录、普通 `SKILL.md`、frontmatter `name` 匹配）跳过，不再无备份覆盖。
- `init` 安装缺失 required external Skill 时不再经 dependency closure 覆盖已合法依赖；公开 `install-external-skills --skills` 仍展开依赖。
- `reset` 仍无备份覆盖全部 bundled Skills，并从当前 stable snapshot 强制重装全部 required external Skills。
- `plan --json` 对 Skill 目录操作输出 `plannedActionOnInit` / `plannedActionOnReset`。
- 全局和项目 `AGENTS.md` 仍备份后覆盖；项目 `.gitignore` 仍只追加模板缺行；`init-projects` 仍不写全局 Skills。

### 验证

- 新增 / 强化 `test_init_skips_valid_bundled_and_external_skill_shells`、`test_reset_overwrites_valid_bundled_and_external_skills` 与 `plan` 的 Skill 写入动作断言。



## v1.0.9（2026-08-27）

### 变更

- `sync` / `同步` 在复制 Onboard 后必须用已同步 `onboard.py install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt --scope global --source auto` 从 stable mirror 安装 required Ponytail Skills，并校验 4 个 `SKILL.md`；不得把 `assets/external-skills/stable/skills/ponytail*` 加为同步表拷贝行。
- 正常 `init` / `reset` 与本仓库 `sync`：若用户主目录已存在 `.omp`（POSIX `~/.omp`，Windows `%USERPROFILE%\.omp`），把同一 `AGENTS.global.md` 备份后覆盖写入 `~/.omp/agent/AGENTS.md`；目录不存在则跳过且不创建 `.omp`。`--global-agents-path` 只覆盖 Codex 目标。
- `--global-agents-path` 指向 `~/.omp/agent/AGENTS.md` 时，`init` / `reset` 只保留一条写入操作，避免对同一文件做两次备份移动。
- External Skills stable set 升级为 `2026-08-27.1`：通过 `promote-external-skills-stable` 从上游 HEAD 刷新 mattpocock/skills、impeccable、ui-ux-pro-max-skill、shadcn-ui 与 ponytail 五个 repository 的原样快照、tree digest 和许可证文件。
- `init` / `reset` 对解析后相同路径的 `file` 操作只保留一条并只备份一次，覆盖 `--global-agents-path` 与项目 `AGENTS.md` 撞上 OMP/Codex 目标的情况。版本检查 prompt 的 OMP AGENTS 校验不再依赖被忽略的根 `AGENTS.md`。

### 验证

- 全量 Python unittest `180` 项全部通过（`python3 -m unittest discover -p 'test_*.py'`，97.278s）：`test_workflow_contracts` 37、`test_onboard_multi_projects` 34、`test_onboard_ponytail_integration` 29、`test_onboard_external_skills` 24、`test_install_sh_agent_cli_flow` 24、`test_knowledge_base_p1` 18、`test_validation_evidence_v2` 9、`test_onboard_agent_cli` 5。
- 本轮新增 OMP AGENTS 路径覆盖已包含在上述 `test_onboard_multi_projects` / `test_workflow_contracts` 中：无 `.omp` 跳过、存在则覆盖写入、`--global-agents-path` 同目标去重、项目根撞 OMP agent 目录只写一次并只备份一次、Windows `USERPROFILE` stub、fresh-clone prompt 不依赖根 `AGENTS.md`。


## v1.0.8（2026-08-26）

### 新增

- Ponytail 4 个核心 Skills（`ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt`）作为 required external Skills 接入：正常 `check` / `init` / `reset` 检查全部 18 个 required external Skills，缺失或损坏时不询问、直接从 vendored stable set 补装或修复，失败即阻断；stable set 升级为 `2026-08-26.1`，固定 Ponytail `v4.9.0` 上游 commit、MIT license、tree SHA-256 与第三方声明。
- `promote-external-skills-stable` 支持首次注册 manifest 中尚不存在的新 repository：新增 `--repo`、`--license` 与可重复 `--license-file SOURCE=STABLE_PATH`，从 catalog 选择与 `--repo` 精确匹配的 external entries 生成 candidate tree；既有 repository 只允许 `--repo` 一致性复核并拒绝 license 参数，杜绝静默改写元数据。
- `check --json` 新增 `ponytailProvider` 只读检测：Codex / OMP 官方 Ponytail plugin 已启用时报告 `provider=conflict`，`check` 失败且 `init` / `reset` 在写 stable copies 前阻断，根安装器同样停止；plugin 已安装但禁用只报告不阻断，CLI 不可用报告 `unknown`。Onboard 不执行任何 plugin 安装、启用、禁用、信任或卸载。
- 全局 `AGENTS.md` 模板新增 `Code Readability` canonical 规则：正确性、安全、运行时特性、明确需求和项目约定优先，可读性与可维护性高于源码行数、文件数和最小 diff；`AGENTS.project.md` 增加最小 fallback，`trellis-workflow` 明确 ponytail → 定点 smoke → ponytail-review → Code Readability Review → 最终 `project-validation` 的主动调用顺序。

### 变更

- 将全局 `AGENTS.md` 模板的 `Code Readability` 章节改为中文标题「代码可读性」，正文与英文版语义对齐；check summary 仍使用 `Code Readability Review` 协议字段。

### 验证

- 全量 Python unittest 160 项全部通过，其中 Ponytail 集成测试 18 项覆盖 catalog/stable manifest、promotion 首次注册与拒绝路径、provider 检测矩阵和 workflow 文档契约。
- 隔离 HOME smoke 8 个场景全部通过：Ponytail 缺失 / 完整 / 部分缺失 / 损坏修复、官方 plugin enabled 冲突阻断（check 与 init 均失败且零写入）、plugin disabled 放行、CLI 不可用报告 `unknown`、reset 前后 Ponytail config 文件字节一致。

## v1.0.7（2026-08-20）

### 新增

- 为 scenario-backed 验证证据新增 `validation-evidence.v2.schema.json`、确定性语义 validator 和仓库级共享 fixtures（`tests/fixtures/validation-evidence/`）。v1 继续服务通用 / 历史 report evidence；BDD 可追溯性必须从 SHA-verified JUnit XML 或 Playwright JSON 中提取唯一 passed case，并要求 case 内 `sbtd.sourceLocatorDigest` 等于重算 locator。

### 变更

- 对齐 Trellis stable 更新后的 hook 生效边界：升级并运行 `trellis update` 后，如更新涉及 SessionStart、PreToolUse 或其他 hook 配置，现要求先重启对应 Agent host / IDE，再验证新会话身份或 hook 行为，避免将既有进程的旧配置误判为更新已生效。
- 对齐 Trellis 的 active-task pointer containment：`task.py start` / `set-*` / subtask 与平台读取器不得跟随解析到项目外的任务路径；升级后不要假设 `trellis update` 会改写既有 session pointer，越权 pointer 按无任务处理。

### 修复

- 将 mattpocock/skills stable 镜像提升到 `v1.2.3`，使 `diagnosing-bugs` 的命令、输出和捕获产物先脱敏，并采用跨 Agent harness 的 subagent 表述。
- 恢复 v1 报告 checksum / digest 一致性门，并写明 v1 Schema 只校验 digest 形状；补齐 locator 规范化：`ensure_ascii=False`、`./` 段丢弃、commit trim/lower、空 optional→`null`；把 stale-commit 收窄为 declared-SHA 一致性；统一 evidence schema / validator 路径到 `project-validation` Skill root；保留 untrusted environment 拒绝条件；把 v2 fixtures 移出 bundled Skill 树，避免 `init` / `reset` 整目录安装把 JUnit / HTML 样例写入项目。
- 修复 `writing-great-skills` 上游删除后的 reset 迁移：其自身及更早的 `write-a-skill` 目录现在都会在 `writing-for-agents` 完整校验并提交后删除；迁移失败保持 fail-closed 和 rollback 语义。
- 修复 `init` / `reset` 在发现 mattpocock legacy 目录身份冲突时仍会先安装 external Skills 并写入全局 / 项目文件的问题：现在在 bundled rename 检查之后、任何写入之前做 identity preflight，冲突时 fail-closed 并保留原目录。

### 变更

- `grilling` 改为 design tree / frontier 的分轮澄清；每轮只提出前置条件已满足的问题，环境事实可并行调查，用户决策仍需等待用户回答。
- 新增 `migrate-external-skills` 全局命令：先对所有受管 mattpocock legacy 目录做 frontmatter identity preflight，再安装 canonical replacement，并迁移或删除 `diagnose`、`write-a-skill`、`writing-great-skills`、`to-prd`、`to-issues` 和 `zoom-out`。

## v1.0.6（2026-08-03）

### 修复

- 修复项目 `.gitignore` 模板误忽略项目 `AGENTS.md`、`CLAUDE.md`、共享 `.agents/skills/**` 和 Trellis 生成的 `.claude/**` 平台集成：这些受管控制文件与生成资产现在默认可追踪，只保留 `.claude/projects/`、`.claude/worktrees/`、`.claude/settings.local.json`、`.omp/plugins/` 等明确的本地运行态忽略项。
- 修复根安装器目标平台参数容易被误解为全局规则平台选择器的问题：`--platform` / `-Platform` 只选择 Agent CLI 与 MCP adapter；默认全局 AGENTS 仍使用 Codex 路径，只有显式 global AGENTS path 才覆盖，project-only 不写全局 AGENTS。
- 修复版本检查自动化的写权限范围：安装器、Onboard 实现、catalog、项目 `.gitignore` 模板与契约测试只可读取、评估或验证；无人值守运行不得修改这些实现和测试资产。

### 迁移

- `init` / `reset` 不会自动删除旧模板已经写入项目 `.gitignore` 的 `.claude/`、`CLAUDE.md`、`.agents/` 或 `/AGENTS.md`；既有项目需要在确认追踪边界后手工移除这些旧行，并用 `git check-ignore` 复核。

### 变更

- External Skill 安装改为 stable-first：默认 `auto` 与显式 `stable` 都从 Onboard 内经过 review、精确 revision 和 checksum 固定的 stable set 离线安装；只有显式 `--source upstream` 才直接获取当前上游，失败时不自动回退。
- 将 14 个受管 external Skills 提升到 stable set `2026-08-03.1`：固定 promotion 时的 mattpocock/skills、impeccable、ui-ux-pro-max-skill 与 shadcn-ui 上游 revision；通过 promotion 流程刷新 tree digest 和许可证文件。
- 项目模板选择以无尾随斜杠的 `.trellis/workspace` 忽略目录或顶级 symlink 及其所有内容，包括 workspace `index.md`、开发者 journal 与 trace；这有意不同于上游 Trellis 默认会 stage workspace 内容的策略。
- 对齐 Trellis 的 Codex hook 上下文恢复路径：bundled `trellis-workflow` 现在要求升级后保留单一 context prelude，并在注入标记不完整时依赖受管的 saved `SubagentStart` 恢复，而非手工粘贴任务数据或放宽注入上限。
- 明确 Trellis 的平台调度边界：共享 `.trellis/**` 只定义 workflow gate，不标识运行平台；当前 host 与 `.codex/**` 或 `.omp/**` 生成资产决定执行机制，二者共存时不得由静态审查强行选择。`codex.dispatch_mode`、Inline 与其 fail-closed fallback 仅属于 Codex；当前 OMP host 使用 OMP `task` worker 和 agent 定义。Channel 保持显式确认的持久协作 runtime；同一变更职责只能有一个写入执行者，用户请求的独立只读复核可以并行。
- 版本检查新增 stable-tag 配置、workflow、migration manifest 与平台集成的强制证据门；Trellis v0.6.10 的 `SubagentStart` 修复不再被误述为首次启用 Codex subagent。
- 移除 `sync` / `update` 流程禁止 Agent 提交和推送的限制；在用户明确指示时，Agent 可以提交并推送已验证的仓库变更。
- `grill-with-docs` 状态透明度不再无条件制造重复确认门：仍必须说明调用状态与原因，但只有调用与跳过存在会改变需求、领域边界或实现决策的实质权衡时才询问用户。
- 版本检查自动化的允许扫描、影响分析和验证范围扩展到根安装器、项目 `.gitignore` 模板与契约测试，并明确无人值守任务不得通过交互提问升级为 `update`、`sync`、commit 或 push。

### 文档

- 新增 OMP SBTD 上游提升 PRD 与运行手册，区分 `640-skills` 已提交上游、KPi Kit / Plugin 集成、npm 发布、用户安装和新 Session 生效等状态，并固定 Plan / Apply、证据与回滚边界。

### 验证

- 完整 Python 契约测试增至 121 项并全部通过；额外以默认 `auto` 实际安装全部 14 个 external Skills，确认统一使用 stable set、无需 fallback 且目标 `SKILL.md` 全部存在。

## v1.0.5（2026-07-28）

### 修复

- 修复手动 `update` / `更新` 将归档文件名后缀字面写为 `index` 的规则错误；归档现在按日期使用从 `1` 开始、当日递增的正整数序号，并已更正 2026-07-24 与 2026-07-25 的归档文件名。
- 修复 Onboard 将 Oh My Pi 与 Pi 混为 Trellis 初始化平台的缺口：`omp` 现在作为独立受支持 flag 透传为 `trellis init --omp`，并明确禁止替换为 `--pi`；`pi` 保持独立语义。

### 许可

- 为 bundled `web-ui-autotest-generator` 增加 `NOTICE`，声明 `Copyright 2026 KunoLu` 和 Apache License 2.0 适用边界；独立安装和本地同步后的 Skill 现在随目录分发完整许可与版权声明。

### 变更

- 对齐 Trellis 的 Pi shared-skills 迁移边界：当项目仍有 legacy `.pi/skills/` 时，bundled `trellis-workflow` 现在要求使用 `trellis update --migrate` 完成受管重命名，避免手工移动造成双重发现或破坏迁移安全检查。
- 对齐 Maestro MCP 的 Cloud 诊断能力：全局规则模板和 `maestro-mobile-e2e` 现在明确在 Cloud upload 终态后可读取 per-flow run 的状态与 artifacts；README 两种格式同步说明该能力只用于诊断，不替代 Maestro CLI 的正式 E2E 执行与报告。
- 对齐 Trellis 的受管更新边界：bundled `trellis-workflow` 和 `trellis-channel` 现在明确子代理上下文注入的默认字节上限、单次跳过关键词、受限的 linked-worktree 信任目录，以及 Codex 子代理模型设置在更新后的保留与复核要求，避免通过无限上下文或宽泛路径信任绕过安全边界。
- 更新 Playwright MCP 的 Onboard 安装引导：当所选 Playwright 发行版提供内置 MCP server 时优先使用 `npx playwright mcp`，否则继续要求选择兼容的专用 server；保留 MCP 可见性确认与项目级 Playwright CLI 不可替代的边界。

## v1.0.4（2026-07-19）

### 修复

- 修复根 Bash 与 PowerShell 安装器中 `--yes` / `-Yes` 仍会询问 `Install project AGENTS.md...` 等 yes/no 问题的语义缺口；两个入口现在统一对全部 yes/no 提示回答 Yes 并跳过最终确认，同时保留无默认值的选择和文本输入。

## v1.0.3（2026-07-19）

### 修复

- 锁定 bundled `web-ui-autotest-generator` 在仓库本地 sync 允许列表中的完整 source / target 映射，并让版本检查 automation 同时校验 bundled Skill 同步覆盖和最新 `CHANGELOG.md` 维护契约。
- 修复根 `install.sh` 在逐项目检查触发 React Bits 选择时误从项目清单 process substitution 读取输入、继而无限输出 `Invalid choice.` 的问题；交互提示现在固定读取脚本启动时保留的原始 stdin，并在输入流关闭时明确失败退出。
- 修复付费 React Bits Skill 被 shadcn CLI 写到项目根 `SKILL.md` 的问题；Bash 与 PowerShell 安装器现在固定写入 `.agents/skills/react-bits-pro/SKILL.md`，已有目标直接覆盖且不留备份，并校验目标实际生成。
- 修复项目 `.gitignore` 只按完整模板块判断、导致部分已有规则被整段重复追加的问题；现在按精确非空行求差集，只追加缺失内容，重复执行保持幂等。
- 将 Bash 与 PowerShell 安装器的启动标识升级为带前置空行的 91 列 `KUNO` / `Tips` 双栏欢迎面板，集中展示 `--platform`、`--projects-root`、`--init-projects`、`--action` 和 `--dry-run`；默认 TTY 延续紫色渐变，显式禁色或非 TTY 使用相同布局的无色版本。同时修复 Bash 将内部 `NO_COLOR=0` 状态误判为外部禁色请求、导致交互终端始终退化为无颜色字符画的问题。
- 修复审核发现的安装器兼容性与契约缺口：Bash 仅在参数解析后初始化交互输入 fd，closed stdin 的 `--help` / 非交互项目模式不再输出 `Bad file descriptor`；PowerShell 脚本恢复 UTF-8 BOM；React Bits 检查提示与自动化版本文件 allowlist 也与实际覆盖、版本基线和输出路径保持一致。
- 修复 UTF-8 BOM `.gitignore` 的逐行比较：比较时忽略首行 BOM、写回时保留原始字节前缀，完整模板第二次执行不再误追加首条规则。

## v1.0.2（2026-07-18）

### 许可

- 新增根目录 `LICENSE`，本仓库原创内容采用 Apache License 2.0。
- 确认 bundled `web-ui-autotest-generator` 为个人独立实现；将其目录内的 MIT License 替换为与仓库根一致的 Apache License 2.0，保证独立安装时许可文本随 Skill 一起分发。
- 为自包含 `sbtd-workflow-onboard` 的原创内容增加与仓库根完全一致的 Apache License 2.0 `LICENSE`，并增加 `Copyright 2026 KunoLu` 的 `NOTICE`，确保公开安装和本地同步后的独立 Skill 保留许可与版权声明。
- 为 `templates/skills/` 下除已单独许可的 `web-ui-autotest-generator` 和第三方衍生的 `seo-geo` 外的其余 bundled Skill 原创内容增加相同 `LICENSE` 和 `NOTICE`；既有第三方来源说明继续保留，不修改任何 `SKILL.md`、脚本、references、assets 或运行逻辑。
- 完成 bundled `seo-geo` 的来源和许可证核验：增加 Apache License 2.0 `LICENSE`，在 `NOTICE` 中固定 ReScienceLab/opc-skills 上游 source、revision 和本地修改范围，并将 `Copyright 2026 KunoLu` 严格限定于 frontmatter 适配、尾随空白清理和 bundled packaging。

### 变更

- 将 bundled `lessons-record`、`project-validation`、`trellis-channel` 和 `trellis-workflow` Skill 的中文说明逐句等义翻译为英文，保持触发条件、执行顺序、门禁、状态值和安全边界不变。
- 将 `web-ui-autotest-generator` 从受管 external stable 镜像迁移为 `sbtd-workflow-onboard/templates/skills/` 下的 bundled Skill，保持原 `SKILL.md`、脚本、references、assets 和功能逻辑不变；从 external stable manifest / notice 移除对应条目，将 bundled 目录的许可统一为 Apache License 2.0，将原中文 `README.md` 原样改名为 `README.zh-CN.md`，并新增逐句等义的英文 `README.md`。
- 为 bundled `web-ui-autotest-generator` 的 frontmatter `description` 补充与现有中文语义对应的英文触发词，覆盖 frontend / backend、pages、routes、components、APIs、user flows、Playwright UI tests、Chinese test reports 和跨页面覆盖检查。
- 修正长任务中 `caveman auto-lite` 达到阈值后仍可能不启动的问题：由全局 AGENTS 模板统一自动生命周期，增加单调 eligibility latch、消息级保护区、仅新主要目标重置、配置缺失默认 auto 和 compaction / handoff 状态连续性；external `caveman` Skill 保持上游原样。
- 强制每次完整执行 `grill-with-docs` 后立即调用 bundled `book-ddd-distilled-modeling` 做独立边界二次审核；`grill-with-docs` 内嵌的 external `domain-modeling` dependency 不再视为替代，必须向用户输出 `DDD Boundary Review`，未达到 `confirmed` 不得进入需求确认、PRD、design、Trellis task 或实现。
- 为其余 4 个 bundled `book-*` Skill 增加客观开发触发门禁和完整状态机：`Book Gate Plan` 使用 planned / running / passed / blocked / not-required，legacy 与 refactoring 通过受控 safety-seam-only 回路避免死锁，DDIA 只强制 shared / persistent / cross-request / cross-process cache，Release Readiness 位于所有适用测试工具 Gate 和项目验证之后并区分必需验证与可选检查；未命中场景仍保持按需调用。

## v1.0.1（2026-07-18）

### 修复

- 删除仓库根目录下指向不存在 `.agents/skills/sbtd-workflow-onboard` 的 `.claude/skills/sbtd-workflow-onboard` broken symlink，避免 Claude Code 误判项目级 Skill 来源。
- 保持根 `sbtd-workflow-onboard/` 为唯一公开 discovery entrypoint，不再提交由本地 Agent 安装器生成的项目级 alias。

### 文档

- README 同时提供默认分支最新内容和指定 Git tag 两种安装命令。
- 明确 `skills@latest` 固定的是 npm 上的 Skills CLI 版本通道；未带 `#ref` 的仓库 URL 安装默认分支 `main` 的最新 commit，而不是最新 tag。
- 明确正式 tag 保持不可变，修复通过新的 patch tag 发布。
- 新增根 `CHANGELOG.md`，从 `v1.0.0` 起按 tag、中文、倒序维护发布记录。

### 验证

- 增加仓库契约检查，禁止重新提交 `.claude` 项目级 Skill alias。
- 增加 README 最新版本 / 指定 tag 安装示例和 CHANGELOG 顺序检查。

## v1.0.0（2026-07-18）

### 新增

- 将 Onboard 能力收敛为根目录自包含 `sbtd-workflow-onboard` Skill，提供唯一 `SKILL.md` discovery entrypoint。
- 新增机器可读 `catalog.json`、Draft 2020-12 Schema、bundled Skill 模板和带来源校验的 external Skill stable fallback。
- 支持一个或多个项目路径的 `plan`、`init`、`reset` 和 project-only `init-projects` 流程。
- 支持通过官方 `npx skills add --global` bootstrap Onboard Skill，再由 Agent 执行完整初始化或重置。
- 纳入 Knowledge Base P1.1、Playwright / Maestro 验证契约、分层 lessons 和 SEO/GEO 等可选专项 Skill。

### 变更

- 仓库由旧 `kuno-workflow-onboard-skills` 布局迁移到 `sbtd-workflow-onboard`，canonical Skill 安装成功后按身份校验删除 legacy Onboard 目录。
- external Skill canonical 名称迁移为 `to-spec` / `to-tickets`，旧 `to-prd` / `to-issues` 仅作为迁移输入并在成功安装后删除。
- 根 `AGENTS.md` 和 `ENTRYPOINT.md` 保持 Git 追踪，分别作为仓库规则和版本监控的可恢复基线。
- 普通仓库维护、显式 `sync` 和手动 `update` 职责分离；只有 `sync` 按差异发布版本化 prompt 到 Orca live automation。
- 扩展 README 的全局安装、多项目、project-only、回滚、安全边界和响应式 HTML 说明。
- 将 Knowledge Base 集成方案移动到 `docs/prd/`，并归档 Codex `v0.144.5` 更新报告。

### 验证

- 增加 catalog、安装事务、legacy migration、多项目初始化、Agent CLI、Knowledge Base 和仓库工作流契约测试。
- 发布前全量 Python 测试共 88 项通过，并完成 README HTML 桌面端和移动端 Chromium smoke 验证。

