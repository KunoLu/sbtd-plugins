# P1-01：Onboard 协议基础与接入边界

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

当前审查门槛以用户更新后的[D-IMP-13](sbtd-workflow-v2-implementation-decisions.md#d-imp-13审查门槛与低优先级发现台账)为准：无有效P0／P1即可推进；P2及以下记入[findings 台账](../archive/sbtd-workflow-v2-findings.md)留待评估。下文历史“零新发现”保留为旧轮次事实，不再要求低优先级问题全部清零。

## 交付与非目标

本项交付可实际调用的纯Python参数解析、版本化交换对象校验、canonical ID和单JSON输出契约；不是新的迁移执行器。按主PRD §10.2及§14，包含publication-decisions批准快照、manifest的私有／共享操作、阶段收据、deployment-evidence及init迁移上下文、recovery plan／receipt、migration／recovery envelope。

实现放在自包含Onboard目录内，由同一Python实现供后续生产者／消费者接入。现有`onboard.py`公开入口与两种安装器本项保持原行为；不注册没有执行实现的命令，不放置返回伪成功／占位blocked的handler。新增模块不提供第二个CLI入口。接入相关行为时须同批迁移直接调用者、删除被替代参数／字段，不留兼容alias；见[D-IMP-12](sbtd-workflow-v2-implementation-decisions.md#d-imp-12协议基础与可执行入口原子接入分开)。接口验证通过不能标记P1-04/05/12/13/20行为或AC-35完成。

## Book Gate Plan 与首次编辑前结果

| Skill | 触发／范围 | 阶段 | Gate state |
|---|---|---|---|
| book-legacy-change-safety | mandatory：既有公开CLI、JSON和退出码边界必须保持 | 首次实现前 | passed |
| book-refactoring-pass | mandatory：已核对现有parser/run/计划与两端消费者，避免半切换 | 首次实现前 | passed |
| book-ddd-distilled-modeling | required：资源／操作／批准快照／阶段结果的模型边界 | schema稳定前 | passed |
| book-ddia-data-design | mandatory：持久交换对象、ID、共享归属和累计证据 | schema稳定前 | passed |
| book-release-readiness | required：新增协议解析／校验／输出语义，仅限接口层 | 完整验证及按D-IMP-13独立复审 | passed |

未完整grill-with-docs：产品边界已由PRD收敛，当前落地机器字段及原子接入时序，不推断新的用户授权或真实环境。

Legacy Change Safety Review：characterized，normal。基线`9e45e867e9be850e93ab7f2133172da142faf013`上的真实CLI四场景证明：check-projects单JSON／两个项目无全局检查；参数错误stderr+2且不写入；未注册migration明确拒绝；旧plan帮助仍可用。隔离HOME和两项目均保持为空。正式本地证据为`tests/api/reports/api-report-onboard-interface-baseline-p1-01-interface-contracts-2026_09_18-01_02_56.json`及同stem中文汇总／已验证envelope；这是现有行为刻画，不是新协议通过。

Refactoring Review：proceed，normal。既有build_parser/run/build_plan_payload和Bash/PowerShell消费者已定位；本项新增内聚契约模块，不为接口阶段改造旧执行生命周期。已有jsonschema验证模式可复用，不自制通用schema引擎，不先抽取无实际可变性的adapter。安全网是现有公开入口刻画、现有回归及新增真实契约调用；运行接线重构随对应行为任务完成。

DDD Boundary Review：confirmed。resource是物理资源；operation是phase/resource/selector逻辑操作；state是路径类型与摘要，不是阶段status。approval.scope只保存声明的批准结构快照，hash/JSON合法不代表人的授权。协议层、实际资源盘点／授权、执行／证据生产分开；共享资源只有一个拥有者，私有操作只属于本项目，未知状态不当absent，未执行不当成功。核心是迁移／恢复工作流，协议是支撑，JSON和摘要是通用能力。grill修正not-applicable；没有阻塞性产品问题。

DDIA Data Design Review：confirmed。版本化schema和同一Python语义校验是机器契约事实源；本项不读取object_ref所指内容来声称它存在、安全或已被授权，不改项目／HOME。严格UTF-8、闭集、类型、枚举、重复键和非有限数检查；ID按规范payload JSON派生，数组顺序与批准快照保留。累计收据、阶段依赖及绑定只定义/校验声明关系；真实文件、symlink/权限/物理别名、授权、smoke和恢复由既定阶段验证。没有新的journal、锁、调度器或证据索引。

## 实现约束

- 复用已在owned project-validation/knowledge代码中采用的Draft 2020-12 `jsonschema`；在Onboard目录声明同一受限major依赖。缺失时fail-closed，不自动pip安装或回退为弱验证；本机已有依赖，无本轮全局安装。
- 所有列明字段必填，允许null的分支显式建模；未知版本／键／枚举、重复JSON键、非有限数、错误类型和非法摘要拒绝，不自动改名或补默认值。
- publication-decisions逐项核对approval.scope的sources/target_path/decision/candidate_ref，检查ID及目标冲突。结构快照和哈希只证明声明未漂移，真实授权独立。
- manifest私有／共享操作使用同一结构；resource/operation ID按PRD计算。owner_kind表示实际资源所有者／格式，而非读取它的Agent；重复拥有、重复ID、无效前阶段引用及依赖集合冲突拒绝。change只能是已定义的受管结构化操作，不接收shell字符串或另造命令DSL。
- deploymentEvidence仅在显式init/init-projects迁移上下文出现；必需参数成组，previous单独提供不能补成上下文。普通init不得因此扩张范围；本项只固定参数与返回结构，不执行部署或保存receipt。
- migration/recovery阶段参数闭集按PRD；cleanup普通--yes不能代替confirm-cleanup，recovery apply不能临时改变项目范围。参数错误遵循argparse stderr+2；实际授权/绑定/文件失败的envelope由已进入处理器的生产者负责。
- 错误诊断只报告固定字段／规则，不把敏感原值、私有哈希或原始JSON拼进公开错误。原生验证证据schema和external stable镜像均不修改。

## 验证策略

新增可保留回归只覆盖真实接口边界：严格解码、合法round-trip、canonical顺序/Unicode/伪造ID、闭集与类型、批准scope漂移、私有/共享ID及依赖冲突、阶段参数误用、累计结果和envelope约束。采用真实纯函数与真实子进程调用，不用mock回声或源码字符串断言充当新行为证明。本仓不生成.feature，按中文PRD追溯。

冻结完整变更后重跑项目计划全量和独立契约smoke，保留正式命名报告、中文汇总、envelope及真实SHA；接口fixture/合法hash不能升级成迁移、部署、恢复或host通过。私有编辑备份保留到最终head验证、独立review和实施PR合并以后。

## 安装副本与依赖证明

Onboard目录复制／`npx skills add`只交付文件，不执行pip。jsonschema必须惰性加载，不能让新协议依赖破坏现有CLI或纯参数解析；缺依赖校验明确失败，不回退为只检查几个字段。使用者通过实际运行解释器执行`python -m pip install -r <installed-onboard>/requirements.txt`准备校验依赖；该步骤不是本项对用户全局环境的隐式授权。

完成证据必须包括完整隔离安装副本：无第三方site-packages的进程能运行原有CLI/参数解析，但契约校验fail-closed；独立私有venv从副本requirements真实安装依赖后，加载副本自身schema并通过契约调用。记录解释器与实际包版本，不能仅用源码目录或宿主已装jsonschema的CI结果声称安装副本已可用。

## 模块协作接口

- `scripts/onboard_arguments.py`提供`parse_workflow_args(argv)`：返回argparse Namespace，覆盖check/check-projects/plan/init/reset/init-projects及完整目标migration/recovery语法。只解析与检查参数组合，不读写用户路径；不是现行onboard.py入口接线。保留已有非Trellis公共选项，拒绝旧四个Trellis参数、缩写alias、重复单值证据参数和跨phase参数。
- `scripts/onboard_contracts.py`负责严格解码、schema/内部不变量、sealed payload摘要、声明间绑定与累计保全、envelope及单JSON序列化；schema为`onboard-contracts.schema.json`。参考项目已有jsonschema模式，但依赖惰性加载，错误不包含被拒绝的原值。
- 结构化change只复用当前文件／目录复制、ignore缺行追加与已受管删除四类低层操作：`copy-file/copy-directory/ensure-file-block/remove`；不会解释任意shell文本。后续实际执行器如需要新的受管种类，须以真实实现同批扩展闭集schema与校验，不能用自由字段提前放开。owner_kind是file/directory/markdown/gitignore/json/toml实际资源类别，不以消费Agent给同一物理路径重复命名；真实格式／归属仍在阶段入口确认。
- manifest补齐未在PRD逐字命名的机器载体：projects中的platforms/sources，shared_roots记录HOME/Skill根与依赖项目；源引用与before_requirement承载源／目标状态；retention只记录正常／明确终止的人工保留要求，不新增生命周期配置或自动处置入口。
- recovery step_id使用规范JSON数组`["recovery",manifest_id,phase,resource_id]`的SHA-256，保持同一逻辑资源／原阶段稳定；不替代原operation_ids。recovery共享结果仅集中引用同一资源的step_ids，不复制到每个项目。
- 校验声明的关联与累计字段不代表引用对象已读取／实际状态匹配。绑定函数仅处理调用方明确提供的对象和raw bytes，不扫描文件，也不把缺阶段证据推断成未执行；提供recovery plan时，每个inverse步骤必须有非空来源引用及同时提供的对应阶段结果，不能跳过未提供阶段的provenance校验。其他未提供对象不作运行事实推断；实际命令须按PRD要求提供并核对完整证据链。

## 集成检查与证据边界

参数worker曾违反显式skip-validation要求运行scoped测试，该结果未计入验收。主线程在两个写入者结束后统一验证：参数38项通过；codec首轮因9个类初始化失败只执行62项，不能视为完整覆盖。恢复fixture修复后原文件实际99项；首次冻结head的codec为121项，独立review后继续补充关系回归。

主线程修复了实际复现的声明漏洞：成功结果缺失／错配原始备份、恢复保护与计划状态不符、共享单依赖归属丢失、前阶段引用缺失、同目标所有者冲突、私有／备份／发布路径声明越界、raw bytes与对象不一致、失败严重程度被envelope掩盖、累计原始引用或上游证据可替换、成功缺报告及未完成步骤。真实partial允许省略未执行结果，但成功项目不能借整体failed逃避本阶段完整覆盖。各回归保留red/green与定点／影响范围报告；反例曾未真正改变时间字段，已改为显式不同时间及不同ID，不把无效变异当可靠red证明。

目录／候选／状态均为合成契约fixture；所有这些通过只证明结构与声明一致性，不证明对应路径、权限、授权、操作或报告真实存在。已准备并实际执行完整隔离candidate安装副本：无jsonschema时原CLI帮助／纯解析仍可用且校验validator-unavailable；私有venv按副本requirements实际安装jsonschema 4.26.0后14份对象及绑定／单JSON通过；暂移副本schema后schema-unavailable，未回读源码，随后恢复。该阶段为dirty本地证据，最终head必须另行完整重跑。

Code Readability Review：新模块与测试已按项目Ruff格式整理；去掉收集／排序全部错误后只消费首项的多余工作，真实无site-packages子进程替代对私有validator缓存的修改。类型修正采用Mapping只读参数、准确NoReturn和真实模块装载检查，不加ignore/cast掩盖错误。新5个Python文件Ruff/ty通过；受影响旧workflow测试的Ruff为5→5，无新增。公共自动化范围测试保留只读／可写集合安全边界，不再钉整句路径顺序，也不声称证明LLM执行。

200项影响范围及提交前完整425 tests/83.124s/exit0通过；现行onboard.py、install.sh、install.ps1与开发基线一致。该轮仍为dirty本地证据，提交后必须重新生成最终head全量与完整安装副本报告，再独立review；不提前填写本任务done或后续行为验收。

## Scoped Release Readiness Review

- Status：ready（仅P1-01内部接口层）。第十二轮三路独立review均无P0／P1，满足D-IMP-13；4条deferred P2在根目录findings.log留待用户评估，不宣称已修复，也不代表公开CLI、部署、迁移或恢复执行就绪。
- Production path／影响：新解析、版本化数据及输出函数；现行Python入口／两安装器未激活它们。
- Failure modes／防护：严格输入、ID／批准／归属／累计／失败状态约束，依赖或副本schema缺失fail-closed；不执行不可信命令，不把合法hash当授权。
- Capacity／backpressure：无服务、队列或后台任务；仅进程内解析／校验，compiled schema不缓存用户数据。
- Observability／runbook：ContractError保留明确code/exit_code且不回显被拒绝原值；requirements与缺依赖处理已在实际安装副本验证和文档说明。
- Rollout／rollback／cleanup：仍按D-IMP-12由对应生产者原子接入，真实引用/权限/别名/授权/报告真实性必须另验；当前只改受管源，源码备份保持至实施PR合并之后，不触碰真实迁移备份。
- Required validation：冻结实现提交`2239fcdd777ef28e7c6c30864f346f5e1ca72ae7`原生539 tests／146.737s、新5个Python文件Ruff／格式／ty、精确完整副本三路径、19组实际API smoke及21份unit/API envelope通过；旧workflow测试Ruff5→5。后续审查记录／日志提交不改实现，证据继续明确绑定实际运行revision，不冒充CI。
- Optional checks／剩余边界：无本项服务、Web交互或设备链路；未声明Windows真执行、Codex/OMP运行或跨阶段恢复通过，这些归既定P1验证任务，不把缺失证明转成通过。

## 首轮独立 review 与修正

冻结head `db58bae22326fb0a889b89e6ced062b290d3c603` 的425项全量、精确安装副本及静态证据保留为历史。`P101SurfaceReviewOne`在参数／文档／安装证据范围零新发现；`P101ProtocolReviewOne`提出9项协议关系finding，全部采纳。前述冻结head不具备合并许可；新head必须重新完整验证并独立review。

修正范围：阶段结果before与manifest／明确提供的上阶段after相符；部署／验收／清理／恢复执行的已提供前置对象成功门；恢复inverse精确来源于阶段结果；私有／共享失败严重性不能降级；partial备份／保护引用与已知before一致；shared target落入唯一且依赖闭包兼容的shared root；恢复receipt与plan的项目scope及input_evidence一致；项目恢复状态不能掩盖依赖失败／pending；所有failed／blocked逐项目记录必须有reason与nextStep。

红测构造曾发生错位编辑及不相关ID/fixture错误；已恢复提交中的原121项，再逐块追加并语法检查。只计修正后隔离反例：8项测试、20个预期assertion失败、无fixture error。未知before的失败fixture不再携带虚构备份；专用可续作fixture明确提供原始before/backup。首轮修复后这些反例通过，不以损坏或提前失败的反例声称覆盖。

恢复状态边界经原reviewer再次核对PRD §10.2.1／§10.2.3：不要求每个源资源status均为succeeded；failed／blocked但前后态已知、确有变化、原始备份完整的部分写入仍可恢复。inverse必须精确复制after/before/backup，未知状态、备份不完整及before==after不产生可执行逆向动作；真实文件证明仍属执行阶段。额外正向／负向测试先证明合法partial未被拒绝，并复现两种no-op被误接受后修复。

F3补充正向边界实际复现：只有apply阶段证据的合法恢复plan曾被“资源必须列出manifest全部阶段operation”拒绝。资源现在只需列出manifest内已证明步骤的operation子集，步骤本身仍须完整匹配相应phase/resource声明，资源与步骤集合继续精确一致；不补造deploy/cleanup动作。此项定点red/green后，完整协议131项通过，提交前全量435项／61.548s通过。以上均为dirty证据，不能替代修复后冻结head证明。

本轮Code Readability／Ponytail复核：保留原始备份／保护引用这一共享不变量，删除仅单行转发的旧result wrapper；阶段前态绑定与恢复inverse证据保持独立职责，不增加通用validation框架。新修改代码／测试Ruff与ty通过；wrapper删除后纳入最终全量重跑。README.md／README.html及版本化automation prompt无需再次改写：既有内部接口、依赖准备和只读边界不变；CHANGELOG已有未发布协议能力条目，本次为同一未合并能力的关系校验修正，不新增用户可见命令或发布叙述。

## 第二轮独立 review

冻结head `1eaa9878c3b05b5e06feab2ed50ec213b603e3d6` 已取得435项／118.184s全量、精确安装副本、静态和envelope验证，仍因第二轮review不得合并。`P101SurfaceReviewTwo`指出argparse会回显未知token／非法choice／无值flag的显式输入；三分支以合成sentinel复现后统一覆盖error诊断，保留静态usage、退出2和空stdout，parser39项与实际三分支smoke通过。移除47处incidental wording pins，不重钉新文案。该修正只改parser及其测试，协议review范围保持冻结直至其返回。

`P101ProtocolReviewTwo`的11项finding均采纳，进入新修复轮：最新前序阶段衔接、manifest同资源同阶段前态一致、完成状态的ref/HEAD快照绑定、verified候选状态绑定、逐项目verified候选完整性、每步恢复的已提供来源、plan内no-op拒绝、首次already-complete拒绝、累计pending步骤宇宙保全、成功envelope与artifact精确一致、私有／共享ownership反例不被无关containment提前拒绝。新head须重新全量／安装副本验证并独立review，当前不标ready或done。

另一个advisory提出所有failed／blocked的已知before都应强制非空备份，未采纳该扩大限制：原reviewer据PRD727/729/765/788确认，备份／保护创建本身失败时须允许保存真实失败与nullable引用；已提供引用不得矛盾，自动inverse另须完整来源。已用真实函数验证未写入缺备份、已写入缺备份时inverse拒绝、恢复保护创建失败三场景；不会把nullable失败收据当作可恢复证明。

第二轮协议反例先取得10项测试／18个预期失败；pending反例曾因共享可变payload污染旧ID而假绿，已先deepcopy保留旧收据，修正后真实复现丢失pending。ownership两项先通过无冲突scope正向控制，再引入满足containment且具有独立operation ID的重复claim，避免无关拒绝。来源门收紧后同步更新全部受影响恢复测试调用者，补齐实际source stages；单依赖共享恢复另建完整合法证据链及正向控制，不让缺来源门掩盖原来的ownership/state/scope负面场景。

阶段状态索引现在一次构建，供前态、verified候选和恢复inverse复用；manifest先保证同资源同阶段只有一个前态，并按本资源最新已声明阶段衔接。已完成／verified项目同时绑定source_ref/head；failed／blocked诊断仍可记录观察差异。候选状态仅在声明verified的相应项目／共享依赖上要求与已提供前序一致，不阻止失败验收记录真实漂移。累计already-complete须有对应前次成功，恢复completed/pending总集合不得丢失；成功envelope及逐项目摘要不得改写artifact的完成变体。

同一消费边界补充证明：canonical ID合法但无前收据identity的already-complete项目，在load_document中曾仍可进入；三类收据均已复现并把该内在矛盾前置到对象校验，重试时仍核对实际传入的前收据成功状态。恢复receipt另核对completed步骤的全部显式depends_on都已completed；以完整来源复现“deploy inverse仍pending、后置apply inverse却完成”后修复，逐项目归因反例改选叶步骤以避免无关依赖错误造成假绿。

F5的合法续作边界再次获原reviewer确认并实测：before/after均已知且相等、原件非absent、旧backup_ref/protection_ref为空时，重试可建立首份匹配before的引用；未知状态或已落地变化不能事后补拍所谓原件；任何已有非空原始引用保持不变。三类收据的合法无写入失败曾被拒绝，已取得真实red并修正，unknown/changed负面边界保留。当前协议144项全部通过，最终head全量／安装副本与下一轮独立review仍待执行。

第二轮修复后的提交前验证：parser39项、协议144项及全量449项／61.674s通过；新5个Python文件Ruff、格式与ty通过。可读性复核保留集中不变量的helper，移除临时共享字典和测试中未用状态的提前构造，已纳入该全量。以上是dirty本地证据；不把它重标为后续冻结commit结果，安装副本、诊断隐私及nullable失败smoke须在新head重新执行后再发起第三轮独立review。

## 第三轮独立 review

冻结head `c9c86f3835e8f17a2f0c4d882f132c8299156ac8` 的449项／115.111s全量、精确安装副本、parser隐私和nullable失败各3场景、静态及四份envelope均通过；`P101SurfaceReviewThree`零新发现。Main另以完整来源复现“仅逆cleanup却声明restored/pre-apply，4个资源仍非初态”，已保留失败报告；`P101ProtocolReviewThree`确认该P1并共提出9项finding，当前head仍禁止合并。

本轮修正边界：批准的share/redact候选须关联apply目标／来源及成功后态；planned恢复须覆盖选定资源的已证明变更链并最终到达manifest具体初态，不能空链／省略资源虚报恢复；成功恢复refs绑定plan；change与文件／目录owner类别相容；无产物时当前阶段生成的ID必须为空；恢复项目根唯一；阶段／验收私有资源不能跨项目重复；成功cleanup保留资产与verification快照一致；已提供证据的阶段时间保持因果顺序，重试时间属于本次执行，不倒置于输入收据。

补充领域／数据判断：publication candidate是已批准的完整投影，operation是逻辑操作、resource是一次物理写入的单元，三者不能各自悬空。target pre-apply是恢复终态承诺，不等于“选中的逆向步骤执行完”。当前资源快照与已知无写入／no-op可证明无需动作；未知／无原件的已落地变化不能猜测。字段与ID算法不改，不新增journal/锁/索引，不把声明合法当实际文件／授权／运行时证明。

为避免fixture继续掩盖缺口，required shared-notes补为新的r4：Alpha内的markdown apply-only资源，初态absent、候选和apply后态为同一file checksum；不加入deploy/cleanup删除集合，verification/cleanup保留它，recovery以有保护的apply inverse撤销新文件。现有r1/r2/r3/s1次序及状态向量保持。Fixture与测试分属两个写入者，均禁止自行验证；Main统一运行red/green、静态、全量及安装副本，并在结束后再次独立review。

两个写入者均跳过验证。Main首轮实际执行为15项、30个预期失败及5个fixture错误（不是worker所述17项已通过控制）；修正blocked envelope空诊断、no-action资源错误清空operation_ids、以及ref/head非合法配对后，取得15项／35个预期失败／无fixture错误。错误和原报告保留，不以无关前置拒绝当作目标覆盖。

9项修复后定点15项与全协议159项通过；新增“完整初态快照可无动作／空快照不可猜测”和“只有后续阶段证据不能止于中间态”两条边界。它们在保留的c9安装副本真实codec上均失败，文件hash与该head静态报告一致；未改活动工作树来重现，也未mock返回值。当前实现通过对应定点。原4资源终态反例已在新增r4保留完整apply inverse后重跑，正确返回binding拒绝，不能靠漏r4的无关错误冒充修复。

可读性／Ponytail复核删除了一个仅检查fixture自洽的重复正向测试及field-copy断言，保留真实API正向控制和负面边界；现有144项行为测试未删除，当前协议共160项通过。跨项目唯一性检查使用逐资源集合查找，避免移动到全局集合后产生反复全量相交；阶段／恢复时序只核对声明因果，不证明真实执行或授权。Ruff发现的一处嵌套with及ty发现的可空ID索引／fixture absent哨兵类型已修正，未使用ignore/cast压制；新5个Python文件静态检查通过。

第三轮修复后的提交前全量465项／72.127s通过，parser39项、协议160项；新5个Python文件Ruff／格式／ty通过。该轮为dirty本地证据；冻结新head后仍须重新执行全量、精确安装副本及各实际smoke，再进行第四轮独立review，当前不填写ready／done。

## 第四轮独立 review

冻结head `7c39776c7d665602754712a4d1a603ef7d8adcd9` 的465项／125.788s、安装副本、四组实际smoke、静态和六份envelope通过；surface零新发现。Intrinsic的8项与Recovery的5项合并去重为11项，全部采纳：selector／合并写入冲突、成功结果类型、备份位置／冲突复用、retained资源完整性／状态／总表、已部分写入或未知结果不可续作、累计恢复结果身份不可变、blocked readiness／失败原因、超大整数错误边界、非JSON key的canonical拒绝。

批次retained语义已与原reviewer核对：是所有项目实际观察的去重并集，不丢弃failed／blocked项目的观察；只有成功项目必须等于verification。恢复按apply→deploy→verification观察→cleanup结果／观察更新最新状态，不能用较早写入结果掩盖后来的资产漂移。原始非空备份和结果身份不变；失败结果已写或未知时原样保留，只有已证明未写入的结果才可推进。

Main先得到11项／29个预期失败及1个目标缺陷（超大整数ValueError逃逸），再修复并转绿。完整协议171项通过；旧多selector反例改为真正不相交的ownership，旧失败恢复补齐root reason，旧retained绑定反例同步项目／总表观察，避免新前置规则造成假绿。canonical有限数兼容保持，非有限值原稳定错误码不重钉；不引入新的真实运行、授权或文件存在证明。

清理后将累计身份／成功态／原件／unsafe partial规则集中为一个转移校验，移除重复成功分支与共享集合；补充原样保留partial及失败→成功时身份不漂移的正向／负向控制。对应3项定点及提交前全量476项／63.725s通过，新5个Python文件Ruff／格式／ty通过。仍为dirty本地证据；冻结新head后重跑正式证明，再进行下一轮独立review。

## 第五轮独立 review

冻结head `e53d623838aaea8094b15292a936015b3810ae01` 的476项／119.757s、安装副本、五组实际smoke、静态和七份envelope通过；surface零新发现。Recovery的2项和Intrinsic的6项全部纳入：重复deployment文件摘要必须一致；verification实际候选状态进入恢复观察；共享物理结果按各逻辑operation的dependent_projects分配项目引用；候选及其父子路径不能被cleanup管理；whole-resource remove成功后必须absent；发布路径复用不能声明矛盾快照；POSIX拒绝双前导斜杠；raw_documents先检查Mapping类型。

共享路由最初fixture复用了两项目的同一list，已拆开并重跑；raw list-of-pairs改用有效manifest bytes，避免无关schema拒绝。有效red为8项／10个预期失败及2个目标错误（合法共享路由被拒、raw bytes原生TypeError逃逸）。修复后8项及完整179项协议回归通过，实际4场景smoke同时证明安全拒绝和一个共享物理结果下的合法逐操作项目路由；未修改或重标原失败报告。

可读性复核保留明确的摘要一致性与verification观察职责，不加框架；fixture源头为两项目分别复制shared ID列表，序列化内容不变，去掉隐蔽可变别名。新5个Python文件静态通过，提交前全量484项／231.478s通过。当前仍为dirty本地证明；后续冻结head正式验证及独立review未被替代。

## 第六轮独立 review

冻结head `e3bb1ff4c425d06d936c47359e8358296aea002e` 的484项／347.973s、安装副本、六组实际smoke、静态和八份envelope通过；surface零新发现。两路协议共10项全部采纳：发布目标及候选均受cleanup保护；无apply对象时下游apply ID仍一致；共享cleanup候选按cleanup操作依赖而非跨阶段并集；恢复保护路径不可矛盾复用；具体初态类型匹配owner；目录必须完整资源／完整归属；managed目标与备份／保护对象不得父子重叠；identifier先验Mapping；一个operation ID不得属于两个资源结果。

目录cleanup fixture改为完整skill ownership，不再用file config-entry冒充目录归属。Main取得10项／16个预期失败及3个目标错误（非法identifier原生异常、两种合法cleanup-phase依赖场景被拒）；修复后10项及完整189项协议回归通过，实际4场景安全拒绝smoke通过。保留全部历史，不把字段／路径合法当真实文件或授权证明。

验证顺序收敛为定点／影响范围与实际smoke、静态、提交、该最终head一次全量及精确安装副本，再独立review；取消内容相同的提交前全量重复运行，不减少最终完整gate。新head尚未完成正式全量或review前仍不得标ready/done或创建PR。

## 第七轮独立 review

冻结head `c10b2b417b3042012130ba9260d4fc19627dc681` 的494项／473.325s、安装副本、七组实际smoke、静态和九份envelope通过；surface零新发现。两路协议共19项进入修复，涉及whole-resource归属、copy精确后态、retained父子写入冲突、备份／保护／候选与输入证据隔离、独立plan身份与类型、报告／源快照一致性、严格目标子路径、恢复观察时序和累计保全。

授权裁决单独记录：原reviewer已撤回“Beta-only恢复可放宽资源闭包”的建议。PRD741/767/784要求完整共享资源授权，因此resource.dependent_projects及selected-project闭包保持manifest跨阶段并集；step.dependent_projects按本阶段operation来源精确记录，属于resource闭包的子集。不能把修正步骤归因变成扩大写入许可。

copy-file/copy-directory的source_ref明确表示已准备好的完整复制候选，不是尚待渲染的模板；ownership.reference仍可指原模板归属证据。Fixture分开每个候选路径并使source.state等于实际after，保留原before/after向量与5资源/14文档接口；manifest项目sources补为一致的初始快照。保护重叠只检查当前确实提供的目标／原件／输入证据及manifest候选，不编造plan中不存在的候选清单或实际文件权限证明。

第七轮实际红测为208项：原有189项通过，新增19个方法产生38个预期断言失败和1个目标错误（合法阶段依赖被资源级相等判断拒绝），无fixture错误。修复后19项定点及412项Onboard影响范围通过；实际API消费smoke的6场景证明完整链、copy内容拒绝、保护／候选隔离、证据路径唯一、阶段恢复归因与完整授权闭包、absent原件无备份retry。全部为dirty本地证据，保留原始报告，不替代新提交全量。

Code Readability／Ponytail复核：路径快照与operation归属各集中为复用校验，不新增schema字段、执行层或通用框架；共享receipt依赖取其实际记录步骤的并集，资源授权范围不变。Ruff指出累计守卫可化简，使用具名`unprotected_change`说明现有原件丢失风险而不压成密集表达式；未使用ignore/cast。修改后208项协议回归及新5个Python文件Ruff／格式／ty通过。报告汇总曾误传Path给接收raw对象的helper，实际smoke退出0的原始记录未重跑／重标；已按原记录补正同stem中文汇总。

README.md／README.html及版本化automation prompt无需额外改写：内部接口分阶段接入、复制安装后的依赖准备、无真实HOME／迁移授权的边界未变。CHANGELOG既有未发布协议能力覆盖这些尚未合并的语义校验修正，不追加一次性过程日志。Release readiness仍等待新head全量、精确安装副本及下一轮独立review，当前不标ready／done。

## 第八轮独立 review

冻结head `2076d1cd65af5a5ab24e071f2192146eb16c30ba` 的513项／142.508s、精确安装副本、8组实际smoke、静态和10份envelope通过；surface零发现。Intrinsic首份报告3项及其后确认的2项scope问题，与Recovery的5项合为10项，全部纳入修正。新发现不被旧覆盖的全绿结果掩盖；嵌套共享根、manifest矛盾快照和直接Python递归值均先保留独立实际红色报告。

范围裁决：共享目标不得等于任何已声明共享根，不能借外层根绕过内层边界。仍允许选择嵌套项目；私有操作必须显式归属于包含目标的最具体已选项目，不自动改派owner，不增加整批嵌套禁令。发布目标不得等于任何已选项目根。该规则只使用已声明根，不发现或假定未提供的嵌套仓库。

数据／恢复边界：project／publication／operation change／ownership的所有manifest输入引用，以及具体初始目标快照，在同一计划时点按路径保持一致；后续phase-after状态不混入该表。只读输入清单同时供阶段备份和恢复保护隔离复用，不再仅保护publication candidate。恢复计划的原始备份与输入证据不得等同或父子覆盖；保护引用还要避开收据自身的input evidence／report refs。备份对象必须严格位于vault之下，不能是vault本身。planned plan和receipt包含所有已记录依赖；blocked plan仍可记录未满足的授权闭包，但不是可执行计划。

10个新回归方法在未改生产codec时产生18个预期断言失败和2个目标RecursionError（cycle／depth），无fixture错误；修复后10项定点及完整218项协议回归通过。四组实际API smoke确认共享根、矛盾快照、受控递归拒绝和7个恢复输入／scope隔离边界，全部退出0；此前失败报告保留。向reviewer发送一次诊断报告指针时误猜时间戳，已立即以实际路径更正，不以该错误指针作为证据。

Code Readability／Ponytail复核：分别命名manifest只读输入清单与初态快照流，避免把后续状态或可写对象混入同一不变量；复用路径／状态校验，不引入动态路由、schema字段、缓存或通用框架。递归异常仅在公开Python-value边界转换为固定ContractError，不输出输入对象。新5个Python文件Ruff／格式／ty通过，无ignore/cast。README.md／README.html／版本化automation prompt的内部接入与安装边界未变，无需重复改写；CHANGELOG不追加未合并能力的逐轮过程日志。新head正式全量、安装副本和独立review尚待执行，不能预填ready／done。

## 第九轮独立 review

冻结head `564d29908bd95a23ad8717b997c9931449730e89` 的523项／125.983s、精确安装副本、12组实际smoke、静态及14份envelope通过；surface零发现。Intrinsic与Recovery各4项全部纳入：managed目标不能包含已声明scope根；verified清理候选与retained资产隔离；完整RFC3339小数时间比较；所有公开JSON入口的递归错误边界；独立plan的target／backup／evidence空间隔离；恢复报告保护；已提供stage的内嵌报告／retained／backup引用保护；证据文件路径与该证据内部对象不能互相覆盖。

时间格式不通过缩窄合法小数位数规避问题：比较带时区的整秒与保留前导零、去掉尾零的小数字符串，避免microsecond截断和Decimal context舍入限制。递归转换集中在所有JSON入口复用的安全边界，内部walker仅遍历；保留原有非递归错误码与通用writer有限小数行为。

恢复仅索引实际提供（含已解码raw）的源对象，仍不推测缺失阶段；同一状态的可复用备份引用保持允许，但不同角色的target／backup／evidence路径以及父子覆盖拒绝。report与protection作为不同输出共同避开manifest、plan和已提供stage的保留输入。verified scope拒绝清理／保留冲突，failed verification仍能报告冲突诊断。

8个新方法首轮得到24个预期失败和2个目标递归异常；两条证据路径反例曾被无关guard提前挡住，已将native报告放到独立子目录，并让blocked无步骤plan保留合法resource operation IDs。修正后真实red为26个断言失败／2个目标RecursionError，无fixture错误。修复后8项定点与完整226项协议通过；实际消费smoke的9个场景通过，其中小数精度与独立Decimal比较的24组输入及跨时区控制一致。

smoke后的Code Readability／Ponytail复核保留具名输入引用遍历和阶段边界，不新增schema／依赖／缓存／执行框架。旧cleanup保留约束回归改为不传verification，避免新前置校验掩盖cleanup自身的独立约束；调整后226项协议及新5个Python文件Ruff／格式／ty通过。README.md、README.html、版本化automation prompt的内部接入／安装／无真实主机声明不变，无需重复改写；CHANGELOG不记录未合并能力的逐轮过程。新head全量／安装副本／独立review仍须重跑，当前不得标ready／done。

## 第十轮正式验证前检查

`e6200df5ce6915de0fa23e92849bc0a747ef4df0`准备全量前收到“verification候选未进入引用清单”的阻断建议，正式全量尚未启动。该建议经源码与实际调用判定不成立：候选target在verified／failed两种情况下都必须绑定manifest资源，恢复输出已保护全部manifest目标；4个私有／共享候选的24种等同／祖先／后代报告与保护覆盖均被拒绝，另2个脱离manifest的候选也被拒绝。保留此诊断，不重复建立候选清单，也不把诊断当作新head全量结果。

检查同时发现另一项真实条件差异：共享候选原有状态校验按“任一依赖verified”执行，新retention校验却要求“全部verified”。一个依赖failed不能掩盖另一verified依赖的已知保留冲突。实际API红色诊断及1项回归先复现，再将条件统一为any；无冲突partial与全部failed诊断仍可接受。修复后该定点、227项协议、实际API重跑及新5个Python文件静态检查通过。需要冻结新head重新启动全量／安装副本／独立review；`e6200df`没有被冒充为已完成该正式周期。

## 第十轮独立 review

冻结head `b8a9d76a4ea65b152fa4bd4a68dda525f3f2d6a2` 的532项／126.107s、精确安装副本、15组实际smoke、静态及17份envelope通过；surface零发现。Intrinsic的3项和Recovery的1项全部纳入：发布目标保护覆盖deploy等所有非apply阶段；私有操作不得侵入更具体的已声明共享根；verified的present候选类型即使缺少前序也须符合manifest owner；不可变证据／报告／备份不能跨文档同位或父子覆盖。阶段备份与其他已提供阶段报告碰撞作为最后一项的同根因advisory一并修复。

边界保持：较宽HOME下的更具体项目仍可拥有私有目标，不自动改派操作；absent候选与failed类型漂移诊断仍合法；后续具体状态只在提供前序证据时比较。不把随阶段变化的retained／current观察全局强制为同一checksum。不可变stage引用与历史观察分开遍历，仅检查实际提供的数据，不读取其路径或添加新schema字段。

反例构造中曾误认fixture owner、把checksum传给整数digest助手、误删原有operation却仍使用通用receipt，以及局部patch范围错误；前三份candidate脚本和前三轮四项测试含构造错误，不计为完整回归证据，原raw保留并补正中文分类。最终保留完整合法fixture，仅追加r4 deploy或更具体共享根下的私有操作；跨文档备份用无步骤blocked plan隔离已有plan-backup guard。有效red为4个方法／8个预期断言失败／零errors。修复后4项定点及231项协议通过。

三组实际API smoke通过：发布／归属6场景（含宽HOME与absent正向控制）、完整raw源下的跨文档别名、无前序的present候选类型。单独candidate脚本的旧absent说明字段不是该次观测，已在汇总注明并从后续脚本删除；原raw不改。smoke后补充宽HOME项目与failed类型漂移控制，231项协议和新5个Python文件Ruff／格式／ty再次通过。可读性复核保留具名不可变引用流与观察流，不新增执行框架、缓存或锁。

README.md／README.html／版本化automation prompt的公开接入和安装边界不变，不重复改写；CHANGELOG已有未发布能力条目，不加入逐轮过程日志。当前仍待新head全量、精确副本和独立review，不能预填ready／done或创建PR。

## 第十一轮审查与用户门槛调整

冻结head `d424a7b711542417dab917ad33310b64c7e849fd` 的536项／126.571s、精确安装副本、18组实际smoke、静态及20份envelope通过。Surface零发现；Intrinsic最终保留P1“共享写入侵入更具体项目”，并明确撤回改变“唯一shared root”规则的建议。Recovery提出P1“累计重试覆盖前次报告”及P2“deployment报告文件父子嵌套”。

用户在本轮明确修改当前及后续任务的推进门槛：仅P0／P1阻塞；P2及以下记录后由用户评估。P2报告嵌套项已写入`findings.log`为deferred，对应新增但未执行的测试移除，不为该项修改生产代码。当前P1-01已完成轮次的38条P2审查记录同时回填为fixed，保持原级别与来源，不回滚旧修复。两项P1仍须修复、验证并独立复审；不能把低级别问题记账当作跳过必要验收。

累计报告保留按reviewer确认限定为已提供的previous/current：保留前次已知报告路径，允许相同引用继续使用与新的不相交报告，不要求current追加所有历史report_refs，不推测未提供的旧历史。

本次只调整该实施计划的执行门槛及台账，不改变产品接口、安装／reset、公开工具职责或版本监控范围；README.md、README.html、版本化automation prompt和CHANGELOG无需随之重复改写。全局AGENTS、项目模板、live automation均不修改。

两项P1先以3个方法取得9个预期断言失败／零errors，再修复并通过3项定点和234项完整协议。共享操作仍要求唯一匹配shared root，再排除归属于更具体项目的目标；更具体共享根可继续拥有其资源，不自动路由。累计校验保留已提供前次报告的路径与内容，允许相同引用、新的不相交报告及从当前列表移除旧引用，但新备份／保护／报告不能覆盖前次已知报告。

实际API smoke的6个正反场景通过，新5个Python文件Ruff／格式／ty通过。可读性复核将累计报告保留集中为一个有实际复用的检查，不新增历史索引、字段或存储布局；未处理`findings.log`中的P2报告嵌套。下一步只按D-IMP-13要求验证新冻结head并复审P0／P1，不再追求P2清零。

## 第十二轮独立复审结论

冻结实现提交`2239fcdd777ef28e7c6c30864f346f5e1ca72ae7`的539项／146.737s、精确安装副本、19组实际smoke、静态及21份envelope通过。`P101IntrinsicReviewTwelve`、`P101RecoveryReviewTwelve`、`P101SurfaceReviewTwelve`均明确没有P0／P1，按D-IMP-13达到当前推进门槛。

本轮新增低优先级建议已记录到根目录`findings.log`：PRD尾部历史循环措辞、deployment报告与受管目标／manifest输入的隔离、deployment evidence输出与内嵌artifacts的隔离；两名reviewer提出的报告路径问题按同根因合并并保留两个来源。台账共42条P2：38条历史fixed、4条deferred。未修复这些P2，不以登记代替修复或运行证明。当前仍为checking，真实任务合并后才按D-IMP-02更新完成状态和时间。
