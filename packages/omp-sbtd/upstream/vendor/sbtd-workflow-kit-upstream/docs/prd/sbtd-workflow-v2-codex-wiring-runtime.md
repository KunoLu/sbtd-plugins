# P1-04：Codex 接线、hooks opt-in 与部署证据

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 基线与边界

- 基线main `61be864ba6dfb5ad26a9246c972790c4fd6c880a`；分支`p1-04-codex-wiring`。P1-12实现PR #39及状态PR #40已闭环，P1累计7项；累计第10项P1-06完整闭环后暂停评估findings并等待用户确认。
- 本项依据主PRD §9.2/9.3、§10.1/10.2及AC-08/18/29/33/35相应子项；独占Graft版本／cache／stamp reconciliation安全证明。OMP host、两wrapper、cleanup/recovery与真实项目部署仍为独立范围；不能把fixture冒充host事件通过。
- 错误初稿已撤回；经真实固定包刻画、用户隔离hooks独立授权及修正版DDD/DDIA/Refactoring复核后进入实现。未修改真实HOME、P0保留环境、ENTRYPOINT或live automation。

## 门禁实际状态

- 已读取`grill-with-docs`、`grilling`、`domain-modeling`及项目事实，但尚未完整执行frontier访谈。此前“已完整调用”和DDD confirmed表述已撤回；技术推荐仍须经过事实与边界检查，真实授权/环境不代填。
- Legacy characterized（修正版）：398项既有基线及六种真实固定包cache/stamp/host副作用刻画；已有问题作为明确负例，新增生产seam逐项红绿。
- Refactoring proceed/normal（修正版）：复用P1-12安全文件/累计codec，先全批scope/证据预检再执行，项目模板后接线；不把迁移校验追加在普通init副作用之后。
- DDD confirmed（修正版独立审核）：安装授权、派生缓存、host信任、实际执行和部署验收分离；未完整grill，不冒称后置访谈门已执行。
- DDIA confirmed（修正版）：共享物理资源一次写入，每仓MCP明确绑定；固定策略生成操作、原件/实际前后态/真实smoke及累计不可变证据闭合，缺失或升级stamp不自动恢复权限。
- Release planned：只有完成适用原生验证、精确安装副本和独立复核后才能判断本任务ready。

## 已核对的固定事实

- Graft固定`@nanonets/graft@0.18.0`，Node>=20。包root没有公开init/upkeep/host writer API；内部dist导出不能自动当作稳定公共API。
- `dist/upkeep.js`的默认wiring opts四项均为true；缺stamp或缺opts字段会恢复这些默认。正常安全init传入`--no-global --no-mcp --no-hooks --no-statusline --no-build`时四项opts应为false。版本变化重放已有stamp/disk host集合，缺stamp不能被当成安全默认。
- `graft init`会先撤回未选host的已有接线，即使`--no-global`仍可能改项目内未选host文件；不得直接在含这些内容的live tree盲跑。
- Graft用户路径按home/.codex，不支持CODEX_HOME；Codex支持实际CODEX_HOME。需要明确唯一writer和active配置根，不以仅设置环境变量宣称Graft隔离。
- MCP必须绑定实际选中仓根；仅设GRAFT_DIR不等价于repo root绑定。多个项目不能让全局单个server全部落到最后一个或第一个项目。
- 上游Codex hook shim为动态生成，并会搜索最高版本安装，不是可直接复制的预构建固定文件。DNT、dotenv/LLM环境隔离及精确版本约束必须持续覆盖hook/MCP启动，不能只保护安装进程。
- hooks必须保留每个event的全部foreign entries；不能只保留Stop而丢弃UserPromptSubmit。真实Codex事件payload/feature gate仍须核对实际安装版本。
- 部署输出必须是manifest所在已授权私有目录内的新文件，不是随意放入backup_root。现有closed change-kind/schema不得被未经设计的graft-specific标签替换；selector与change kind不是同一概念。
- 迁移init必须在任何普通安装副作用前核验完整manifest/apply/previous/out范围，只执行声明的deploy资源。非空report_refs不证明smoke成功，必须验证真实报告；普通init没有deploymentEvidence字段。

## 已执行证据与修正记录

- 真实基线：`unit-report-codex-wiring-baseline-p1-04-codex-wiring-2026_09_19-13_13_08`，398 tests/334.995s，exit0，1 skip。此前聊天中的787 tests/9.062s及错误stem并无证据，已明确撤回。
- 初始新测试存在错误前置条件和错误断言：未确认写入却期待成功、空manifest却期待部署成功、丢弃foreign hooks、错误stamp值及语法错误。这些失败不能算产品红测；原报告保留，错误测试文件已私有留存并从仓库撤回。
- 过早暴露未接入处理器的参数和不完整helper重命名已撤回；`onboard.py`及`onboard_arguments.py`恢复基线。两个writer已要求停止；新实现前重新确认完整接口，不用占位或no-op补齐。
- 报告型命令原生运行并保留raw／同stem中文MD／evidence，RTK skipped-for-report；所有后续验证由Main单独控制。

## 修正后的设计与新增前置证据

- 六种真实固定包刻画已完成：current stamp及旧version完整false opts未改HOME；旧version缺opts、缺stamp、缺cache都会创建Codex和未选Gemini／Antigravity全局接线；init会改变未选host的旧Graft fence。报告`api-report-codex-native-upkeep-characterization-p1-04-codex-wiring-2026_09_19-13_42_14`。这是上游危险路径事实，不是修复通过。
- 用户本轮明确选择“授权隔离 hooks 验证”：仅本任务临时Codex HOME、合成项目、经审查hook及精确hash信任；无真实账号/API key/生效HOME，不使用trust bypass。私有Codex0.154.0实际app-server已证明untrusted不执行、精确hash trusted后真实SessionStart执行。无模型成功声明；后续必须用真正的Graft接线重新做该验证。
- 技术推荐沿既有预授权采纳：保留Graft0.18.0；包内窄启动守卫要求明确仓根、固定Node/CLI、完整current安全stamp和真实图，缺失／升级状态停止而不自动重建；native子进程使用临时HOME与完整DNT/dotenv/LLM环境隔离。上游init仅用于隔离生成候选，不在live树撤回其他host接线。
- shared配置一次合并、MCP按每仓根稳定key绑定cwd及完整启动参数，不能用单GRAFT_DIR代替repo root。hooks每event全部foreign handlers保留，仅精确本包launcher argv作为受管身份；超时使用秒；定义写入不代替Codex信任。
- 数据写入顺序：全批只读预检→私有原件→受管模板/接线→显式图构建→真实smoke→原子累计证据；迁移上下文先于普通init副作用，只执行manifest声明deploy操作，输出在manifest所在私有目录。
- 现有copy-kind不能表示原生图生成或配置合并，新增窄`build-graft`／`configure-graft`闭集kind，仅deploy，固定安装包策略path+SHA、来源/ownership完全一致、严格目标与selector；不读取任意命令、不改原生报告schema。先codec红绿再接实际生产者，不把schema通过冒充运行通过。

## 完整部署与失败证据进展

- 完整隔离 `plan→apply→init→verify→显式retry` 已执行，报告 `api-report-codex-full-global-deployment-p1-04-codex-wiring-2026_09_19-15_38_28`：canonical全局规则／完整bundled目录、active HOME MCP及foreign MCP/hooks保留，未新增OMP MCP。普通init原有的现存OMP公共AGENTS镜像规则仍保留；这是全局公共规则安装，不是P1-05的OMP MCP/event接线。所有共享部署写入均在plan封存。
- `Operation.kind` 实际为 `dir`；配置schema的资源类型才是 `directory`，不能混改。project-only含HOME旧操作本来就应阻断；codec已统一拒绝重复ID及template-source同资源多操作。相关advisor逐项裁决记录在 `findings.log`，不靠重复专项校验替代现有codec。
- 共享scope创建失败的真实文件故障注入先红后绿：此前已写项目规则／图却跳过证据保存；目录准备现在进入resource错误边界，保留累计实际结果。报告 `unit-report-codex-partial-scope-{red,green}-p1-04-codex-wiring-2026_09_19-{15_42_22,15_43_24}`；后续还要覆盖显式部分重试与保存失败。
- 普通 `init→init→reset→reset→init-projects --skip-project-agents` 首轮执行到末尾；最后的临时测试按原始TOML子串计数，误把env子表计为第二个server。报告 `api-report-codex-normal-native-first-p1-04-codex-wiring-2026_09_19-15_46_54` 保留为失败，不算通过；已改用结构解析，待完整重跑。
- 独立review确认五项P1：workspace索引／父目录扩大native范围、生成树链接越界写、图／extract缓存／span指针越界、Stop预算低于真实同步build、Windows命令被POSIX quoting破坏。全部阻断，修复与原生复验前不得关闭本任务。候选合并的四项P2原级延期，见ledger。
- `README.md`、`README.html`、Onboard Skill／REFERENCE、CHANGELOG及版本化automation范围同步描述实际新入口；不改live automation、ENTRYPOINT、两wrapper或真实HOME。原生Graft结构smoke和真实Codex事件证明分别记录，不能相互替代；Windows／OMP／完整workflow仍由相应任务验收。

## PR #41 后补救范围

- PR #41已合入`747b27024556a1c284b955883f9635ec93e5a3f0`；精确head`11b00a3a680def23aba3f14958194537203d18ac`全量886 tests/768.439s/exit0（6 skip）。其证明仅属于该快照，不代表后续修复版本。
- 后置复核发现4项P1，P1-04不done、不推进P1-05；从最新main建立`p1-04-codex-runtime-hardening`修复。GitHub分支规则`REVIEW_REQUIRED`与已执行三路独立源码复核是不同状态，用户明确允许admin；不虚构“未review”的归因，也不隐藏后置新发现。
- 图消费者改为每个MCP请求先复验当前图再转发，保留`GRAFT_NO_REFRESH=1`；Stop／显式部署生成的新图不能仅靠长连接启动时证明被读取。拒绝请求不泄露正文；仍是单controller边界，不宣称OS沙箱或任意并发写入隔离。
- Python生成命令使用`-E -s`，在脚本加载前禁用环境与user-site注入，保持受信脚本目录邻接模块。全局hook先判断payload所属范围，无关事件不因已删除绑定仓根失败；相关事件继续严格校验。
- Legacy characterized、Refactoring proceed/normal、DDIA confirmed；无新领域歧义，不重新完整grill；Release仍需最终全部适用验证后运行。补救产物不向真实HOME同步，不执行真实迁移或cleanup。

## 补救验证与复核（提交前）

- `unit-report-codex-hardening-full-p1-04-codex-runtime-hardening-2026_09_19-19_52_58`：899 tests/899.483s/exit0，6 skip（PowerShell runtime缺失5项、Windows ACL专用1项），实际结束`2026-09-19T20:08:00.457612+08:00`。这是dirty源树结果，不重标为最终PR head。
- `api-report-codex-hardening-native-all-p1-04-codex-runtime-hardening-2026_09_19-20_00_08`：12个独立私有原生driver均通过；包含新旧stamp/cache拒绝及明确重建、完整／project-only部署与retry、无Graft降级、catalog漂移拒绝、bootstrap删除后的installed MCP、长连接Stop／失败build图替换拒绝。driver源码和每例真实输出保留于raw；不是Windows或模型成功证明。
- 长连接两条baseline原生红测实际返回仓外合成secret；修复后两条均拒绝且不返回该内容。native先退出时主进程SIGABRT已通过dup输入fd/raw输出修复；1MiB慢读响应不再按5秒计时截断。先前不安全hook命令只识别用于拒绝，不作为兼容alias继续执行。
- `api-report-codex-hardening-real-host-p1-04-codex-runtime-hardening-2026_09_19-19_52_35`：真实Codex0.154的untrusted不执行、精确hash信任、SessionStart/UserPromptSubmit通过；`api-report-codex-hardening-missing-deps-p1-04-codex-runtime-hardening-2026_09_19-20_01_51`证明新bare解释器help正常、接线缺依赖写前拒绝且无HOME／模板变化。
- P104HardeningProtocolReview及P104HardeningCommandReview在修正后均无剩余P0/P1；累计ledger现有20项P1 fixed、10项P2延期，P3中1项静态债务延期、1项删除建议已撤回（历史行保留）。Code Readability Review：范围为修改的手写生产／测试；无额外阻断结构问题，原生边界保持具名；Ponytail的删除建议撤回，其余P2/P3不扩修。Ruff55项非零如实保留，无E9/F63/F7/F82；ty当前与基线均93项，新增差集为空。
- worker违反skip-all-validation自行跑测试；其结果不计gate。P104PythonStartupFix承认未隔离`uv run`写入真实`~/.cache/uv`，已向用户披露且不擅删共享缓存；没有全局site-packages/Codex配置/trust写入。另一worker留下未打印精确路径的tmp fixture／可能的临时HOME，无法证明唯一归属则保留，不猜测清理。
- README两份、Onboard REFERENCE、Graft指令asset、CHANGELOG和版本化automation已同步修复边界；live automation、ENTRYPOINT、真实项目迁移和P0保留环境不变。精确提交、整目录fresh依赖副本、最终release gate、补救PR与状态PR/清理仍未完成；P1累计闭环仍为7。

## 最终交付与保留风险

- 原实现PR #41、补救PR #42均已合入；最终merge为`daa191115ff5830ab11f74e2b53e2ccfa77d82d6`，tree与精确验证head`0da6015144d57f928cef77c71d671d0088c62374`一致。两个实现分支均已本地／远端删除。Main明确归属的workspace及两个新bytecode已清理，完成时间`2026-09-19T20:32:06+08:00`。
- 最终全量：`unit-report-codex-hardening-pr-head-full-p1-04-codex-runtime-hardening-2026_09_19-20_11_54`，899 tests/970.721s/exit0，6 skip。配套`.closure.json`保留324文件安装manifest、编辑前6文件摘要、完整静态结果和清理事实。
- 同时间戳`api-report-codex-hardening-pr-head-native-*`和`api-report-codex-hardening-pr-head-dependencies-*`通过；实际解释器为fresh `exact-venv`，源为git-archive全部324文件。`api-report-codex-hardening-pr-head-host-*-2026_09_19-20_12_10`证明实际隔离CLI（通过固定`@openai/codex@0.154.0`安装）的两个事件及精确hook hash信任；不声明Codex二进制hash身份、模型成功或真实Stop/PostToolUse事件。
- 状态复核要求补齐清理后的来源证明，已从Main内核保留的原始archive bytes、实际副本摘要及原始pip/npm进程结果追加到同一closure：`sourceArchive`与`installedCopy`为独立且相等的324文件manifest，另存venv创建命令／exit0及pip输出。Codex版本依据是实际成功的`@openai/codex@0.154.0`私有安装记录和同路径CLI使用，不声称已保留或校验Codex二进制hash（`binaryDigest=null`）。这些是清理前已观察数据的补存，不是重新运行或补造过去状态。
- 该状态证据P1于`2026-09-19T20:46:26+08:00`复核关闭，为任务最终完成时间；`20:32:06`仅是实现分支／Main临时文件清理完成时间。累计关闭21项P1（20实现、1证据），不将来源证明缺口隐含为早已完成。
- `api-report-codex-hardening-final-evidence-audit-*-2026_09_19-20_28_25`核对81组既有报告，audit自身另保留。报告均developer-local/exact或其原始dirty状态/local-only，不冒称CI或已发布证据；所有失败轮次和先前版本报告保留，不重标。
- P104ExactRuntimeReview、P104ExactDocsReview对冻结head无新P0/P1；Release Readiness ready仅当前源码交付。三模式完整host执行、OMP、Windows、两wrapper转发、cleanup/recovery和真实项目迁移仍按原PRD后续任务，不被本结论覆盖。
- README.md、README.html、REFERENCE、指令asset、CHANGELOG和版本化automation已同步；Skill入口已有REFERENCE指针，本次补救不重复新增路由。ENTRYPOINT与live automation不改。Ruff55项非零和ty93项基线诊断如实保留；无新增类型或关键runtime诊断，不禁用规则。10项P2及静态P3按用户指令延期。
- worker未隔离uv造成共享cache写入已披露，不擅删；另一worker未记录精确路径的fixture／可能临时HOME保留。不能将“明确归属已清理”写成“所有tmp均删除”。本次没有真实HOME配置、trust或生产数据写入。
- P1累计实现闭环8项；本状态记录的独立PR完成并清理后才可开始P1-05。P1-06成为第10项后暂停评估全部findings并等待用户确认，不能自动进入P1-13。
