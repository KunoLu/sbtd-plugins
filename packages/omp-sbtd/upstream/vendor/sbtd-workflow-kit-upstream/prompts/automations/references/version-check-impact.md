# 版本检查：按主题加载的影响清单

本文件是主prompt的按需参考，不是每轮全套测试或部署操作清单。所有路径和命令受 `prompts/automations/references/version-check-scope.md` 限制；“验证安装/清理/同步合同”不授权执行真实安装/清理/同步。只读取上游变化命中的章节及其依赖；没有命中则记录不适用，不全文展开。

在 `UPDATE.md` 逐工具记录：上游证据 → 本地命中文件/符号 → 本节检查点 → 保持/修改/待人工决定。没有实际执行的检查写明静态评估或未验证；不能把CI绿色、合法fixture、目录存在或同名Skill当成真实宿主接受。

以下保留既有安全合同，历史工具名和版本仅表示兼容输入，不恢复退役路由；实时运行时pin和当前实现以允许范围内的源码为准。任何未列出资源只报告影响，不扩展权限。

<a id="task-state"></a>
## 任务状态、身份、模式与交接
- `sbtd-workflow-onboard/scripts/sbtd_project.py` 同样属于上述允许读取、关键词影响扫描与结构/依赖/安全检查范围，只读评估，不由无人值守版本检查修改。核对选中状态 containment、`legacyPresent` 未知值、bundled schema 错误指引和安装器源完整性清单。

- `docs/archive/sbtd-workflow-v2-findings.md` 是原 `findings.log` 的完整 Markdown 台账，仅可读取评估，不由无人值守版本检查修改状态。历史文档中的旧名称已通过入口指向新路径；不得重建根日志或删除 dismissed／历史裁决。

- P0-07的历史交付只证明catalog与bundled载荷原子切换，不能单凭它推断完整CLI、host或迁移验收。当前版本的实现、原生平台、宿主和发布状态须按各自真实证据核对；旧Trellis/GitNexus仅保留迁移与历史边界，不恢复旧bootstrap/Channel路由，也不把tag当真实项目切换授权。

- 迁移交接复用HandoffStore格式和publication批准，不自动摘要或选择active任务；核对固定旧session JSON、完整journal来源绑定、未完成任务覆盖、ignore保护与恢复原件。完整 private-only 跳过整个旧任务目录时不要求已发布 handoff；journal／session 本身获批 private-only 时留在私有层。实际迁移的未完成任务仍须批准摘要。不要把跳过例外当成始终必须发布 handoff。非API辅助报告的类型化内容／来源验证不能替代真实API smoke；未知格式必须明确拒绝，不把sha匹配等同于内容通过。

- 核对任务状态兼容性时区分成功终止 done 与取消终止 cancelled：取消的 completed_at 必须为 null，不级联取消子任务，归档／显式重开保留事件，取消不算 bootstrap 成功或未完成交接提醒。旧 cancelled／blocked 投影不得改成 done；缺失模式、时间、阻塞前态保持未知，恢复须显式选择，矛盾理由与父子关系仍拒绝。运行库、schema 与 Skill references 应成套对齐，旧读取器拒绝新状态不能靠改标签绕过；仅静态评估或隔离验证，不改真实任务。

- 验证 Ponytail required stable 集成契约：`catalog.json` 中 `ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt` 均为标准 required external entries（无 installation policy / group / 安装确认分支）；stable `MANIFEST.json` 的 `ponytail` repository 记录精确 40 位 commit、MIT license 和 license 文件映射，4 个 Skill tree 与 checksum 完整，`THIRD_PARTY_NOTICES.md` 含对应条目；`onboard.py check --json` 输出 `ponytailProvider`，官方 plugin 已启用时 `provider=conflict` 且 `check` / `init` / `reset` 阻断；缺失 `~/.omp` 时 OMP 明确为 `not-configured` 且不执行 CLI，plugin 禁用或 CLI 不可用时不伪造状态。`AGENTS.global.md` 含共同路由、代码可读性规则和 book-derived 客观触发；`AGENTS.project.md` 含三模式入口、project-only 最小 fallback（含 Book Gate Plan 客观触发与 Gate lifecycle）、项目路径和硬边界；bundled `sbtd-task/SKILL.md` 承载共同 / `default` / `lite` / `strict` 工作契约，只有 strict 加载完整适用 Gate，不得复制 reviewer 状态词表。`sbtd-task/references/methods.md` 和 `strict.md` 承载 Ponytail / Code Readability 顺序；`lessons-record/SKILL.md` 以 `.sbtd/developer` 为唯一自动身份来源（本地合法优先，仅确实缺失且已验证 linked worktree 才只读主 checkout，旧 `.trellis/.developer` 只经 `references/identity-migration.md` 在明确授权迁移时读取）；各 `book-*/SKILL.md` 独占 reviewer 状态与修正回路；`project-validation` 不承载可读性规则。

<a id="installation"></a>
## 安装、catalog、stable来源与路径保护
- 使用 Draft 2020-12 校验 `sbtd-workflow-onboard/catalog.json` 符合 `catalog.schema.json`，目录 id 唯一，且恰好包含 14 个 bundled entries 和 19 个 external entries。`skill:trellis-workflow`、`skill:trellis-channel` entries 及对应 `templates/skills/trellis-workflow/`、`templates/skills/trellis-channel/` 源目录必须不存在；`skill:sbtd-task` 必须存在，source 必须为 `templates/skills/sbtd-task`，且该目录实际包含 `SKILL.md`、`references/state.md`、`handoff.md`、`methods.md`、`presentation.md`、`strict.md`、`tooling.md`、`task-data.schema.json`、`LICENSE` 和 `NOTICE`。`templates/agents/AGENTS.global.md`、`AGENTS.project.md` 与 `templates/skills/lessons-record/` 必须是 v2 canonical 内容：共同 / default / lite / strict 路由、`.sbtd/developer` 身份来源，以及仅在明确授权迁移时读取旧 `.trellis/.developer`；`docs/prd/` 不得残留 sbtd-task、AGENTS 或 lessons-record 候选副本。每个 bundled Skill local source 必须位于 Onboard Skill 根目录内且实际存在，每个 external Skill source 必须包含合法的上游 repo、受限相对 subpath 和 canonical alias。验证 External Skill 默认 `auto` 与显式 `stable` 均只使用受管 stable set 且不访问网络，只有显式 `upstream` 才直接获取当前上游并在失败时直接报错。仅在 external canonical rename 命中且允许的隔离验证条件满足时，在本轮临时 global Skill 目录中同时预置 predecessor 与更早 legacy alias，执行 reset 等价的 stable install / migration，断言 replacement `SKILL.md` 存在、每个 predecessor 均不存在，且 JSON 结果记录 `removed`；若 canonical 已存在，也必须验证 legacy-only cleanup 同样删除 predecessor。若本机存在 `AGENTS.md`，同步核对其“本地同步规则”表：仓库管理且要求全局同步的 bundled Skill 必须具有正确的 source / target 映射，包含 `web-ui-autotest-generator`，同时保持 `AGENTS.project.md` 不在普通 sync 范围内；sync 不得把 Ponytail stable 路径或 i-have-adhd stable 路径列为 cp/rsync 目标，必须用已同步 Onboard 的 `install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt,i-have-adhd --scope global --source auto` 安装并校验 5 个 `SKILL.md`；缺失时以 README 中已记录的 `web-ui-autotest-generator` 映射为准，不得因 `AGENTS.md` 缺失失败。

- 验证 OMP 全局 AGENTS 契约，不依赖根 `AGENTS.md` 是否存在：以 `README.md`、`README.zh.md`、`sbtd-workflow-onboard/SKILL.md` 和 `sbtd-workflow-onboard/REFERENCE.md` 为准。若用户主目录已存在 `.omp`（POSIX `~/.omp`，Windows `%USERPROFILE%\.omp`），sync / `init` / `reset` 必须把同一 `AGENTS.global.md` 覆盖写入 `~/.omp/agent/AGENTS.md`；不得创建缺失的 `.omp`，`check --json` 也不得通过 `omp plugin list` 产生副作用。`--global-agents-path` 只覆盖 Codex 目标；若该路径或项目 `AGENTS.md` 与 OMP/Codex 目标解析为同一文件，只保留一条写入操作。

- 验证 `init` / `reset` 写入契约：init 跳过合法 Skill 壳，不因安装依赖覆盖合法壳；reset 按既有策略重装受管 Skills。AGENTS 备份后覆盖，项目 ignore 只追加缺行并用真实 Git 正反探针验证。写入前检查全部所选项目，异常状态、非法目标或新增保护会隐藏未确认数据时阻断；保留 task、identity、spec、lessons、handoff 和旧数据，不默认创建 bootstrap 或完整目录。project-only 无全局安装。Python与两安装器均不得接受旧Trellis username/platform/skip参数或调用Trellis初始化；`sbtdInit`／`sbtdProjectSetup`保留逐项目status/reason/nextStep，`--json`运行结果单文档，非零结果不混散文。最小状态检查不冒充完整任务恢复或验收。

- 核对双语用户提示词是否分别覆盖v2 bootstrap/首次及重复init、明确reset、v1→v2的包upgrade与数据migration，以及upgrade plan/apply/verify、可选probe/authorize-link和独立recovery。提示词不得把合法壳跳过当版本对齐，不得把reset当迁移/恢复，不让用户手抄计划ID，不合并部署、探测、cleanup或备份销毁授权。现行host验证说明不得指导读取/复制真实认证文件；旧执行器若不符合受控认证边界应明确blocked，不以CI skip冒充host通过。

- 根安装器须在全局安装、MCP写入及可选项目安装前执行完整只读项目前置检查，不能仅在最终Python写入时检查；`check-projects`与`plan`复用状态/scaffold/保护判定，并传递`--skip-project-agents`范围。验证有效输入正向控制及冲突时零mutation；只读Agent version探测不能触发安装。

- 协议模块／交换schema变更须核对严格解码、闭集字段、批准快照、资源归属／ID、累计证据和单JSON输出；不修改原生验证报告schema。检查公开入口与真实handler是否已原子接线，不能以文件存在或接口fixture通过冒充migration/deployment/recovery可执行，也不注册占位handler。目录复制或`npx skills add`不安装Python依赖；依赖须惰性加载、缺失fail-closed，必要时在完整隔离安装副本中分别验证无依赖和按副本requirements准备依赖的路径，不以宿主CI已有包推断用户副本可用，不改真实HOME或全局Python。

- 验证根 `.gitignore` 内容严格为十行且顺序一致：`.DS_Store`、`/.sbtd`、`/docs/handoffs`、`/ai/tasks/**/reports`、`/graft`、`/.graft`、`__pycache__/`、`AGENTS.md`、`.chrome-devtools-mcp/`、`.playwright-mcp/`；与业务项目模板独立。用原生Git正反检查本地根、文件／symlink和同名业务子目录，确认共享任务正文／spec／lessons及ENTRYPOINT可追踪，任务reports本地产物被忽略。旧工具根已不受该文件保护；检查磁盘与索引残留，未知或敏感内容先报告并等待授权，不自动删除、untrack或加入提交。保留历史lesson原文，只维护现行规则说明。验证 `git ls-files -- AGENTS.md ENTRYPOINT.md` 只包含 `ENTRYPOINT.md`。`AGENTS.md` 若存在可读取、评估或修改；缺失时跳过，不得把它的存在当作 Gate。

- 核对两份 README 与本 prompt 均指向 `docs/lessons.md` 短入口，入口路由和 `docs/lessons/index.md` 的 detail 文件及锚点可解析；每个 lesson ID 只对应一处 topic / archive 完整记录。topics 中的三／四／五行状态保留为历史，不覆盖上面的现行十行验收；入口只链接当前规则，不要求保留旧五行摘要，不为通过新验收改写历史详情。

- 验证 project-only 安装契约：付费 React Bits Skill 固定落在 `.agents/skills/react-bits-pro/SKILL.md` 且使用覆盖语义；项目 `.gitignore` 重复执行不产生重复行，现有通用保护保持，v2新模板无Trellis/GitNexus旧段。原生Git确认`/.sbtd`、`/docs/handoffs`、`/graft`、`/.graft`保护根级目录／文件／symlink且不误伤同名业务子目录；AGENTS/CLAUDE、共享`.agents`、ai/tasks正文含子任务和归档、docs/spec/lessons、CONTEXT/ADR、features、maestro/flow与三个可入库Web manifest可追踪。`/ai/tasks/**/reports`保护普通／嵌套／季度及undated归档任务的报告目录、同名文件／symlink与全部后代；`reports.md`、业务`src/reports/`和根`reports/`不受此规则影响。安装器探针与模板同批对齐；broad ai/docs/tests或重新包含冲突须返回具体来源，无规则覆盖则报告缺失规则，Git不可用不得报已验证。已有项目只追加新保护，不自动删除旧段、untrack数据或证明所有权／迁移完成；真实清理另经授权。报告原件与汇总本地留存，不自动公开或迁移其他runner报告目录；ignore不能替代脱敏或阻止强制添加。

- 共享路径验证还须覆盖公开固定分支：`docs/lessons.md`旧短入口、context ADR、季度／undated任务归档、任务附属产物及bootstrap、PRODUCT/DESIGN、测试源码、iOS／Android flow、受管React Bits Skill、根Git控制文件。精确排除这些分支也须返回真实规则来源并保留用户内容；代表性probe不是自定义路径穷举，也不授权恢复退役平台集成。

<a id="upgrade"></a>
## 升级、恢复、链接与多配置域
- 上述只读源清单另包含 `sbtd-workflow-onboard/scripts/sbtd_upgrade.py`、`sbtd_upgrade_inventory.py`、`sbtd_upgrade_hosts.py`、`sbtd_upgrade_cli.py`（后三者均位于同一 scripts 目录）与 `sbtd-workflow-onboard/upgrade.schema.json`。评估内容摘要、stable 来源校验、多配置域、未知漂移保护、私有原件与逐项回执、自升级隔离执行及独立恢复。版本检查不执行真实 upgrade/apply/recovery/probe，不将计划ID或重算摘要当作授权。

- 升级路径身份共享模块 `sbtd-workflow-onboard/scripts/sbtd_upgrade_paths.py` 同属只读影响扫描范围；核对缺失根别名在创建前后判断一致、当前隔离执行依赖在计划与执行写入前均可用，不能通过恢复 user-site 或取消 `-I` 绕过。

- `sbtd-workflow-onboard/scripts/sbtd_probe_links.py` 同属只读影响扫描范围。隔离 probe 的 Skill 链接授权仅为精确本地访问批准：核对原计划／宿主、逻辑路径、原始链接文本、链接对象身份、批准物理目录、目标 Skill／目录身份与内容摘要；默认不访问未授权目标，复制前后漂移、嵌套链接或特殊文件仍拒绝。只在临时投影物化普通目录，原链接、旧计划与回执不改；不得改成 follow-all、跳过 expected Skills 或宣称 live_reload 已验证。无人值守版本检查不创建实际目标授权或运行真实 probe。

- 升级对齐与 init/reset/migration 分开：核对 `upgrade --phase plan|apply|verify` 和 `recovery --upgrade-*` 的实际CLI、两安装器转发、完整catalog载荷比较、未知漂移显式决定及身份冲突拒绝。plan/verify默认只读；保存计划、应用、恢复、host probe各有显式范围与确认。只读成功不等于真实宿主已加载，保留例外不等于完全对齐；逐配置域报告磁盘、协议、宿主和清理。自升级必须从独立校验副本执行；部分失败保留实测后态和原件；备份不自动销毁。九个 GitNexus Skills 只按闭集身份由现有 cleanup 独立处置，不得扩大为前缀删除。

- 升级修复边界：Codex 目标绑定实际 `config_home/config.toml`；UTF-16 profile 与不可表达的 PATH 项写前拒绝；Skills 物理别名与决定键一致，父目录只做逐组件 no-follow 检查、不扫描无关兄弟。Shell 以真实交互条件／优先级检查命令，npm shim 仅证明受限字面相对 CLI 指向，不执行未知包装器或伪称 Node 证明；OMP 以成功 RPC 响应的结构化工具注册表为据，prompt URI 不是工具证据。RPC 写入／读取共用期限并验证自有子进程收尾。

- 复核写后失败是否返回 failed／exit 3 与绑定本批的 checkpoint、备份及实测／unknown 状态，不因证据再次读取失败而冒称零写入；blocked 优先于 drift，合法无关 MCP 不误报非法配置。保留选中缺失 host 的安装语义、受支持的分阶段嵌套安装／规范已安装副本续作、restore intent 后 absent 窗口和 OMP user-wide probe 范围，不把这些既有契约改成额外禁令或新部署能力。

- 升级物理身份不可用平台字符串折叠代替：核对冲突目标别名与继承输入重叠在目标写入前拒绝，大小写敏感目录的选择、摘要缓存和包含关系保持独立，既有非 Skill／Onboard 子目录别名绑定规范选择。封存 blocked 优先于 host 语义比较。首行 UTF-8 BOM 识别与重写保留；新建空 PowerShell profile 兼容旧宿主 Unicode 解码；登录 profile 与 rc 的探测模式分开。method 回复不可消费 OMP 式 data 替代 result，MCP 初始化版本须在明确支持集合内，异常／强制关闭不报 verified；method-not-found 脱敏归为 unsupported。CLI 早期拒绝满足 failureDocument，home 展开错误由输入边界收口。仅静态评估或隔离验证，不扩大部署授权。

- 升级恢复的历史权威为操作人选定且独占管理的私有 vault；hash 只证明一致性，不宣称防御具备 vault 写权限者整组伪造历史。来源未知时停止自动恢复；仍须验证当前受信包、scope-derived资源、完整恢复资格/status/reason与当前漂移。不同执行包的旧计划安全拒绝，不自动执行历史暂存代码；空父目录保留，缓存不归本批新增所有权。

- 恢复归属复核不能以现场字节匹配覆盖明确的未写入回执，也不能用旧 pending checkpoint 忽略较新的未写入证据；intent 对应的未知现场须阻断，不报空恢复完成。核对缺失 Unicode 规范化别名、Shell 命令依赖与混合域决定键。Codex 隔离探针不得因信任真实项目而加载未选项目配置；只验证受管投影。既有 PowerShell profile 原字节保留、Unicode PATH 编码安全、探针输出编码明确；合法字面 shim 标点和路径 Unicode 分隔符不误拒绝。OMP legacy 只消费有效启用来源，非文件 unknown，unsupported 汇总不丢失。静态评估不等于真实宿主验证。

- 核对 POSIX 新 PATH 赋值不携带 CR、原 profile 字节保留、Windows POSIX 别名匹配完整所选目录；非 ASCII PowerShell shim 证明必须考虑实际引擎解码。直接 MCP 要求 JSON-RPC 2.0 envelope，Boolean ID 不等于 Number，Codex 无版本回显与 OMP 独立 envelope 不受误伤。OMP 发现／分析未完成时不能凭空报告 legacy none，也不得为补证扫描未选 provider。

<a id="migration"></a>
## 迁移、现态调和、清理与保留
- 上述只读源清单另包含 `sbtd-workflow-onboard/scripts/sbtd_cleanup_targets.py`、`sbtd-workflow-onboard/scripts/sbtd_cleanup_legacy.py`、`sbtd-workflow-onboard/scripts/sbtd_trellis_uninstall.py`：只读评估清理候选检测、身份识别（非固定校验值钉）、标记块精确配对、完整 vendor 足迹封存与备份先于执行、部分失败按实测逐项记录、fail-stop 与确认绑定契约；版本检查不得执行真实 `cleanup-legacy`、`tl uninstall` 或迁移 cleanup，不得触碰真实 HOME/项目配置，也不得把批次证据缺失以外的情况（陈旧/冲突/失败）当作新鲜兜底理由。

- `sbtd-workflow-onboard/scripts/sbtd_cleanup_upgrade.py` 同属只读影响扫描范围。核对 cleanup 成对消费原生 `--upgrade-plan`／`--upgrade-receipt`：只接受一个完整 canonical Onboard 替换、精确规范字节与摘要命名的 vault 文档、当前 after 和旧包 before／完整原件；只读验旧公钥与指纹，不执行旧代码、不补签。清理回执保留 `upgrade_context`，重试不得丢弃或换链，followup／部署／迁移恢复不得借此消费。只对与实际 vendor 足迹及清理依赖无关、且发现路径集合和 profile／工具绑定不变的 file／absent 变化采用 cleanup-only 判定；其他阶段仍严格拒绝。核对最后写前和发布前的保留资产／revision 复验，以及晚期漂移下实测结果仍可保存；无人值守检查不得执行真实清理或升级。

- 评估迁移/部署变更时区分 successor 与 cleanup 闭合后的 OMP followup：后者由五个 `--followup-*` 输入绑定前批 manifest/apply/deployment/verified verification/cleanup，仅允许显式 init/omp、完整部署闭包与本批恢复；不得建议省略证据、放宽旧 successor 门或把计划成功当作 live 接线授权。无人值守自动化仅检查契约，不执行 followup 部署、sync 或备份处置。

- 五个`sbtd_migration*.py`运行模块和三份migration资产仅可读取评估，不能在版本检查中执行真实迁移或变更原件；旧格式／所有权pin是兼容性依据，不随latest自动升级。检查plan/apply/verify实际接线、私有候选与原件、累计部分回执、Codex/OMP完整共享依赖和真实报告消费；不把合法fixture当作部署、cleanup或recovery已实现，不改原生报告schema，不写真实HOME/live automation。恢复成功只表示受管数据／配置按绑定回执 reconcile，不等于已退役 Trellis 可执行或可写，旧运行时 `runtime_readiness` 保持未验证；同一运行时部分回执重试不替代签名前驱—后继配对加完整成功回执的前驱接受；live 实际回执与独立隔离故障／恢复测试证据互不替代，不得把任一侧写成另一侧已通过。`sbtd_reconciliation.py` 同属只读评估范围：核对 `migration --phase reconcile` 的显式 `--yes` 同意门先于任何写入／smoke、历史证据路径真实缺失、输出全新不覆盖且二者位于原 manifest 私有目录、`payload.reconciliation` 的 `current-state`／`historical_execution: unknown` 标记、before 由保留原件证明而 after 为新鲜实测、不伪造历史退出码／成功事实／旧时间戳、写入仅限新鲜私有报告与新证据；后续标准 verify 的 `acceptance_basis: current-state` 与证据精确绑定且普通证据无标记仍有效。版本检查不得执行真实 reconcile 或 verify，不写入任何证据文件，不把 typed current-state 证据当作原进程已完成或 live 安装／清理授权。

- 现态来源兼容性复核须区分纯契约的原始字节绑定与实际消费者的文件／血统校验：manifest/apply 引用必须是安全且摘要匹配的真实文件；观察者须属于 manifest 同运行时或精确验签的前驱→后继配对，不能接受反向／无关配对，也不能把历史观察者强制等同当前消费者。仅静态评估或隔离验证，不重封旧证据、不自动生成血统签名或安装运行时。

- 新跨运行时现态证据的 `observer_lineage` 须保留原始已验签授权，历史消费使用已安装受信公钥，不以当前配对文件替代历史授权，也不信任证据内嵌密钥；旧无证明记录不取得无条件放行。核对 verify 返回前及 cleanup 写前／发布前的来源复验，晚期漂移仍保留真实非成功累计结果，不丢失已发生操作。这些仅为兼容性影响检查，不授权重封、重新签名或真实清理。

- 现态来源的末端校验覆盖直接消费及一层 followup 祖先：恢复首写／回执发布、恢复计划、reconcile 和 followup 计划的最终输出均复核来源；当前普通回执不能绕过历史现态来源门。晚期拒绝保留完成步骤／保护原件或部署 `operationResults`，不宣称回滚成功或伪造可用回执；不回放已被合法取代的祖先目标后态，也不扩展到递归 followup。

- 现态接受的最终顺序应为较重语义／来源链验证在先、纯快照复核在后；固定来源引用可再验而无需重读并解析整个祖先链。核对目标、原件、报告、来源及absent观测的末端刷新，不把这种有界检查称作跨进程CAS，也不通过反复交换检查顺序掩盖另一侧的实际漂移回归。

- 清理扩展模块 `sbtd_cleanup_targets.py`、`sbtd_cleanup_legacy.py` 与 vendor 卸载适配器 `sbtd_trellis_uninstall.py` 仅可读取评估：核对 `cleanup-legacy --phase plan|apply` 接线、私有备份根封存/消费 plan 与累计回执、`--confirm-cleanup` 等于当前 plan_id、apply 重检测范围漂移即 blocked、plan 可选 `--global-skills-dir`（仅 plan 阶段）且选定 Skills 根封存进计划、apply 只消费封存根且无根参数/不受环境重定向、migration 批次参数不变、plan/apply 在任何目标写入前拒绝相等或互相嵌套的候选路径、OMP 检测含 `active_omp_paths` 按相对 `PI_CONFIG_DIR` 与 `OMP_PROFILE` 优先于 `PI_PROFILE` 解析的有效配置、同一目录项的路径拼写别名去重而不同硬链接目录项分开处理、计划时封存完整 vendor 足迹且执行前私有备份全部足迹、部分失败按实测逐项记录且调和前阻断重试、fail-stop、重试不重放；不把合法 fixture 当作清理已实现，不执行真实清理，不写真实 HOME/live automation。

- 复核清理安全修复时，检查实际 Skills 根的逻辑绑定在物理共享根合并后仍存在、退役目标只允许其直接子目录；检查 vendor 在备份完成后复验 `skipped_missing` 仍为 absent；检查重试只继承已成功且与封存预期相符的 vendor after-state 和原件备份；同一确认流程内，仅减少由绑定回执证明已完成的项且其余目标/效果不变时不重复询问，新增或改变效果仍要确认。以上仅静态评估或隔离验证，不执行真实清理。

- 复核 vendor prepared 资源的 `path` 与受检项目 `root/relative` 精确绑定，拒绝非法相对路径和重封后的诱饵替换；fresh replay 路径须一致，备份及测量只能消费已绑定路径。核对合法历史计划的 scope fingerprint 兼容性，不把摘要重算视作授权；仅静态评估或隔离验证，不执行 live 卸载。

- 评估发布前环境保留风险时区分主 PRD P3-05（验证环境／旧 Graft 接线的退役与必要保留交接）和 P3-04（私有备份的独立处置）；TEMP 名称、方案确认或任务 done 均不能证明无运行／恢复依赖。自动化仅只读评估，不执行环境删除、Orca HOME 清理或 MCP 替换，不提前宣称 planned 任务完成。

- 评估旧数据兼容性时，区分受支持数据布局与 vendor 卸载 CLI pin；0.6.15 特定用户内容 hash 声明不得升级为生成文件所有权，也不得豁免发布／私有保全批准，0.6.17 原有拒绝边界保留。无宿主项目的空 platforms 只在宿主根真实缺失时成立；验证阶段仍复核宿主出现／漂移与根 marker 操作完整性，不用空列表或可重算 manifest 摘要掩盖缺失操作。版本和元数据须从封存 inventory／原件解析，不能在原件上改版本号过门。

- 精确模板兼容只接受受信 ownership 资产记录的路径／发行版本／完整内容摘要及可复核来源；评估旧登记不符时，不改项目 `.template-hashes.json`、不动态获取或跟随 latest 扩大钉。混合 AGENTS 只能由既有验签、实际前态及精确候选批准承接，不加入生成文件钉；复核 plan、apply／重试及 retained-original 消费的一致拒绝边界。官方模板版本、旧数据布局和 vendor 卸载 CLI pin 三者分开报告。

- 复核 retained-original 时，已登记生成内容与未登记／incidental 文件均须沿用可证明的 ignore 语义：保留真实 index 的 tracked 保护，只消费 checksum 绑定的 retained `.gitignore`；排除父目录不被后代否定覆盖，有效否定仍生效。Git／规则证据缺失不能退回更弱的 live-only ignored 结论，重新计算 manifest 摘要不能证明外来生成字节。

- 已对齐 AGENTS 的 no-touch 仅限执行包项目模板逐字一致并封存独立不变证据，不能把任意规则认领为生成资产或跳过后续漂移复验。仅文档历史按逐文件源路径归档，不伪造 task 元数据，不转移真实 task 附件逃避闭包。历史分支交接须区分计划 HEAD 取证与旧分支事实、明确后续恢复选择，不自动切分支或重绑定；仅静态／隔离验证，真实文件发布和部署仍需审批。

- 复核已批准项目AGENTS从迁移apply到部署的正文保真：必须绑定已验签候选及实际前态，只解除精确维护暂停前缀、更新受管Graft段，不能用通用模板覆盖项目约束，也不能仅凭pause文本认领未批准正文；原始批次、后继批次、重试、验证与恢复同一判定，普通init及no-touch语义保持。

- 复核 OMP 迁移配置输入的阶段后态：apply 按计划移除旧宿主文件后，部署／重试／验证／恢复只能消费已绑定成功回执、连续前后态和完整原件证明的变化；输入路径集合及无关漂移仍严格核对。不能重封 manifest、恢复旧入口或放宽 runtime-lineage 签名来绕过拒绝；只做静态／隔离验证，不执行真实续部署。

<a id="graft"></a>
## Graft、平台接线、协议与隐私
- 上述只读源清单另包含 `sbtd-workflow-onboard/scripts/sbtd_graft_deployment.py`、`sbtd-workflow-onboard/scripts/sbtd_codex_wiring.py`、`sbtd-workflow-onboard/scripts/sbtd_omp_wiring.py`、`sbtd-workflow-onboard/scripts/sbtd_omp_sources.py`、`sbtd-workflow-onboard/scripts/sbtd_graft_entry.py`、`sbtd-workflow-onboard/assets/graft-build-policy.json`、`sbtd-workflow-onboard/assets/graft-instructions.txt`、`sbtd-workflow-onboard/assets/graft-hook-entry.mjs`；它们不得由无人值守版本检查修改或执行host接线。

- `.gitattributes` 仅作为载荷原始字节边界的只读评估对象：`sbtd-workflow-onboard/** -text` 防止 checkout 改写固定摘要输入；检查目录摘要统一按相对 POSIX 字符串排序，不按平台路径对象排序。不得为消除校验失败而转换 stable 镜像字节、重写 pin 或放宽私有目录 DACL。

- 对 Graft、Codex dispatch、sub-agent、hook 或平台接线的变更，必须额外核验目标 stable tag 的固定包版本、native lifecycle、telemetry、MCP/hooks 边界与部署 producer 行为；区分功能首次引入、默认值变化与既有能力的 bug fix。Graft 结论必须回到固定 pin/source、源码、LSP / contract 定位或真实 host 证据，不得用 latest、缓存元数据或旧 GitNexus 规则替代。`.trellis/**` 与旧平台 dispatch 只作为历史迁移输入，不是现行平台身份；若结论涉及平台调度，还必须读取当前 host 与其专属生成资产，并区分“已配置平台目录”与“当前 host”。不得以未发布 `main` 分支文本覆盖 tagged stable 版本结论。若这些依据无法完整取得，必须在 `UPDATE.md` 中逐项说明缺失依据和剩余不确定性，不得以 release body 充分为由跳过；缺少任一项时不得形成或更新平台调度规则。
- ENTRYPOINT 的 Graft 当前版本不是官方 latest 的写回目标。`update` 不写回 Graft。只有已发布 SBTD workflow tag 中 `GRAFT_PINNED_VERSION` 与 `graft-build-policy.json` 的 `version` 一致且与 ENTRYPOINT 不同时，版本检查才同步 ENTRYPOINT 的 Graft 版本字段；不改运行 pin、gitHead、integrity 或接线。

- Codex部署模块与三份Graft资产只读评估：核对固定policy绑定、模板后接线、active HOME中每个有效host配置域一条全局MCP定义及逐项目本地图/stamp、hooks独立opt-in及host信任分离、临时HOME与拒绝危险自维护；init迁移上下文必须先验证完整证据，只执行plan已声明的部署资源并保存实际累计结果。普通init的全局规则/Skills仍复用既有选择，OMP公共AGENTS镜像不等于OMP MCP/event接线；project-only不得写HOME或新增全局连接。历史逐仓绑定只按退役输入／旧回执识别，不作为当前安装要求。不把结构图check报告当作真实host事件通过。

- 受管MCP必须在每个可执行请求前复验当前图，不能只依赖启动证明或native no-refresh；Stop／部署替换后的长连接也须拒绝未证明图。Python启动环境隔离应先于守卫脚本，旧未隔离受管hook不得被当作foreign静默并存；无关hook事件不依赖已失效仓根。核对真实子进程退出／慢读响应，不把thread实现存在当作生命周期通过。

- Graft候选版本以运行模块的精确pin/gitHead/integrity与官方固定版本证据为准，不静默升级latest。check/plan仅验证本地版本且HOME/项目零副作用；已有本地能力不因npm不可达而被判定缺失。安装必须展示计划并确认，验证native与telemetry持久状态；所有受管子进程DNT、dotenv及LLM/cloud环境边界必须真实验证，CI不能作为DNT通过的唯一理由。离线必须有真实网络正反控制与空cache，不用缓存latest冒充联网/断网证明；不提前生成Graft host/MCP配置，不清理用户旧GitNexus资源。
- 上游新增品牌别名、自动迁移或笔记检索时，核对 canonical 绑定路径与 ownership 消费者一致、父进程品牌／HOME／cloud 参数隔离、匹配 stamp 是否仍足以阻止自动改写，以及新增读取树是否经过启动与逐请求范围校验。Graft/Trail 的 `TRAIL_*`、`GRAFT_NO_TRAIL_SWITCH`、`.trail` 只按固定包证据评估，不执行迁移、联网 fetch 或 live 接线。

- 当前受管 Graft MCP 为每个有效 host 配置域一条 `sbtd-graft`，无固定 cwd/项目 root；launcher 从实际会话 cwd 选择并锁定最近真实 Git 仓/worktree，缺项目/图/旧 stamp/越界均拒绝，不能回退 demo 或父目录。只读评估全局无项目安装、批量与追加等价、项目初始化不写 HOME、Git 探针环境/PATH 隔离和旧项显式退役契约。`--graft-retire-legacy` 与不同旧运行时的私有 `--graft-legacy-bindings` 只由独立确认执行；无人值守版本检查不生成批准、不切换 live 配置、不停止连接或删除 TEMP/备份。

- 遥测持久化采用不覆盖并发创建者的原子创建；已有disabled配置只读，需要改写的已有配置安全阻断。上游没有共同锁／条件更新协议时，不接受read-compare-replace或readback作为CAS证明，不因更新release而静默恢复覆盖写入。

<a id="reports"></a>
## Web、Mobile与执行报告
- 报告兼容性评估另包含 `sbtd-workflow-onboard/templates/skills/project-validation/references/run-summary.zh-CN.md.template`：Agent 执行汇总采用固定中文章节及结果表，Web UI 覆盖率模板仅作附录；核对 native/raw 与同 stem 汇总、失败复跑和源码／部署证据边界，不因上游工具升级改写历史报告或把排版当成新测试。遵守现有允许写入范围，不修改 live automation。

<a id="ci-native"></a>
## CI调度、原生平台与文件权限
- CI 只读影响范围另包含 `.github/workflows/validation.yml`、`.github/test-weights.json`、`tests/run_ci.py`、`tests/test_sbtd_followup_batch.py` 和 `tests/test_sbtd_reconciliation.py`。评估分片的完整发现集合、互斥 test ID、同 SHA 成功回执与聚合门禁；保留平台原生权限／路径／Shell 行为和最低 TOML 编辑器变体。耗时权重只影响分配，不决定是否运行用例；不能以删安全用例、增加 skip 或只核对 shard 数量冒充覆盖保持。缩小边界夹具输入时保留完整清单生命周期与已安装副本锚点，不缓存安全结论、不复用回执、不省略新鲜校验或漂移阶段；区分并行等待与总 runner 成本，以同环境完整样本验证性能。汇总保留原生 skip 与 subTest 明细，不从父例状态推导跳过事件总数。版本检查不触发 CI、不修改上述文件。

### CI与Win32新增核对点

- fixture单元分片：`tests/run_ci.py`、`tests/test_ci_selection.py`和实际workflow矩阵三者一致；模块/类fixture（包括继承或staticmethod形式）不能被拆散，同片恢复发现顺序。缺权重新例仍被选中并报告估算，不把新例静默遗漏。
- 权重证据消费：刷新只接受同一非空源码修订、完整互斥范围、各分片最新且唯一的attempt；非规范数字文件名、失败、额外/缺失分片、重复测量和selected/cases不一致均拒绝。检查者与消费计时者必须使用同一集合。这里只读评估 `--refresh-weights` 合同，不执行会改写权重文件的命令。
- Windows ACL：`sbtd_migration_files.py`的Win32调用绑定缓存不是ACL决定缓存。每次检查新鲜owner/DACL；NULL/无效DACL、非受信主体、Deny/未知ACE、无法读取均拒绝，空有效DACL与NULL区分。继承标志本身不是拒绝条件；新建私有目录仍保护DACL。句柄身份检查不等于原子mkdir＋ACL设置，不宣称消除可信单controller父目录边界之外的换目录竞态。
- 原生验收不能静默省略属主或ACL夹具；设置失败、skip/xfail不算必需native通过。真实Windows证明、PowerShell差分对照和故障注入分别报告，未知ACE或竞态的静态审查不冒充已实测。
- 目录holder复用只限本操作/同父目录；每文件仍检查身份、权限、空目录、路径和内容，未知对象保留，不递归删除。失败清理不得覆盖主失败的精准retained引用或把部分结果写成成功。
- 覆盖重叠不等于行为冗余：逐例行/分支集合只能筛选，仍须比较fixture、输入、消费者断言、状态转移及平台语义。子进程/复制安装包/原生API的覆盖盲区和必需native案例保留；具体减少测试范围需要独立审阅，版本检查本身不删除测试或修改选择器。

<a id="host-loading"></a>
## 宿主发现与配置来源

- 当Codex/OMP/Orca更新涉及Skill发现、全局规则、配置层、账户home或启动参数时，以目标tag源码/官方文档确认各自行为，不能把本机当前版本的规则硬套到所有版本。
- 区分工作区源码、已安装Skill、同名副本、包内模板和实际宿主发现路径；按名称相同不代表同一路径或“新版覆盖旧版”。核对去重按路径还是名称、禁用规则、显式路径选择及缓存刷新边界。
- `CODEX_HOME`、`HOME`、配置profile和启动参数可能改变资源入口；TOML配置合并、AGENTS指令链和Skill发现不是同一种优先级。共享目录链接只影响它指向的资源，不意味着配置或认证也回退共享路径。
- Orca可能为账户维护配置投影或启动前同步，文件复制成功不代表已有GUI会话重新加载。只分析版本兼容性，不枚举本机账户、不读认证文件、不启动真实宿主、不复制凭据，也不执行其prepare/install入口。
- 已由用户退役的账户Skill副本不是自动补装的缺口。无人值守版本检查不重新建立账户镜像、链接或一套额外Skills；发现实际运行依赖不明确时在报告说明待独立核验。
