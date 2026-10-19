# P0-08 项目 ignore 规则与安装检查对齐

## 交付范围

从`main @ 15a4049ac521729b07732598d9ea23f6681b1cbd`建立`p0-08-project-ignore`，落实主[PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md) §11.7／AC-12/26的模板、Git语义及直接消费者子项。

- [项目模板](../../sbtd-workflow-onboard/templates/project/.gitignore)保留全部通用规则，移除旧Trellis/GitNexus段及失效注释，新增且仅新增四个根保护：`/.sbtd`、`/docs/handoffs`、`/graft`、`/.graft`。
- 根锚定避免误伤同名业务子目录；无尾随斜杠覆盖保留路径的目录、普通文件和symlink。忽略某路径不授权安装器使用异常文件类型或隐藏用户业务内容。
- 安装器`GITIGNORE_MUST_TRACK_PROBES`／`GITIGNORE_MUST_IGNORE_PROBES`与模板同批切换，检查SBTD共享路径、新本地根及既有环境秘密；不再拿已退役Trellis路径验收新模板。
- 继续使用原生Git的NUL四字段结果；不改冒号／否定规则解析、缺Git未验证、Git错误／不完整结果阻断的语义。
- `ensure_file_contains`仍只追加缺失行。旧项目保留旧保护和未知自定义规则，重复执行字节幂等；本项不做旧段清理、untrack或真实项目迁移。
- 源仓根`.gitignore`保持原五行，P0-09另行处理；不以项目模板覆盖本仓根。

项目规则应使AGENTS/CLAUDE、共享.agents、ai/tasks含子任务／归档、docs/spec/lessons、CONTEXT/ADR、features、maestro/flow和三个可入库Web manifest保持可追踪；报告／repair plan继续本地忽略。宽泛ai/docs/tests排除必须提示真实来源，不能自动撤销用户规则。

## Gate与实现选择

| Skill | 选择／触发事实 | 阶段 | Gate state |
|---|---|---|---|
| book-legacy-change-safety | required：ignore保护与既有安装检查有隐藏耦合 | 首次生产编辑前 | passed |
| book-refactoring-pass | required：生产探针集合／提示调整 | legacy刻画后 | passed |
| book-ddia-data-design | required：本地／共享数据保护和规则事实源 | 设计稳定前 | passed |
| book-release-readiness | required：安装器可观察验收改变 | 适用验证后，仅限P0模板／规则检查层 | passed |
| book-ddd-distilled-modeling | on-demand：目录与数据归属已确认，无新领域歧义 | 不触发 | not-required |

Legacy Change Safety Review：characterized。移前19个原生Git probe证明旧Trellis/GitNexus保护、环境秘密和报告保护有效，而四个新本地根未被保护。现有追加／NUL解析／错误来源是保留行为。

Refactoring Review：proceed，normal。使用现有`init-projects`与真实Git seam，无新解析器或规则框架；只换探针、过时提示及相关fixtures。测试复用已有Git helper并关闭fixture的用户全局excludes文件影响，生产检查仍尊重项目实际规则。

DDIA Data Design Review：confirmed。模板定义新规则，Git提供实际判定；旧数据、已有规则和索引不自动改写。普通init/reset不承担迁移清理；规则语义检查不证明保留路径的业务归属，也不证明已有本地文件已退出索引。实际所有权／tracked检测／迁移写入门禁仍属P1对应任务，不把P0交付用于真实项目的完整迁移。

未完整调用grill-with-docs：PRD已明确精确规则和阶段边界。TDD采用已确认的真实CLI安装与Git判定seam；不写测试专用ignore算法，不以源码词串代替Git行为。

## 行为检查面

| 场景 | 期望 | 证明 |
|---|---|---|
| fresh模板／CLI安装 | 四根本地数据被忽略，共享资产可追踪 | 真实CLI＋git check-ignore |
| 文件／symlink保留路径 | 四条规则均覆盖；不把忽略当文件类型授权 | 原生Git实际文件／symlink fixture |
| 嵌套业务路径 | packages/graft、packages/.graft、packages/.sbtd、packages/docs/handoffs不被新规则误伤 | 原生Git负向匹配 |
| 既有旧规则与自定义内容 | 追加新保护但旧段不删除，重复执行字节相同 | 现有CLI幂等fixture迁移 |
| broad ai/docs/tests | 非零并报告具体.gitignore来源与被隐藏路径，原规则保留 | 真实Git冲突fixture |
| 本地根被重新包含 | 每个根独立发现泄漏并报告来源 | 真实Git否定规则fixture |
| 环境秘密／冒号模式／短响应 | 保留既有失败／解析边界 | 既有回归不删除 |
| 无Git／非Git仓 | 明确未验证，不虚称语义通过 | 既有CLI回归 |
| 通用缓存／报告保护 | 相对次序和规则内容保留，Git判定保持 | 模板保留集合核对与原生probe |

## 已观察的开发证据

首个tracer在生产修改前运行1test/6个失败subtest：`.sbtd`下三路径、handoff、graft与.graft均可追踪，正好命中缺保护。修改模板及探针后，同一test在2.331s内通过；红测报告保留。相关18项子集在40.256s内通过，覆盖新Git边界、共享冲突、追加/BOM、缺Git／错误Git；冒号否定和NUL短响应仍须后续完整模块／全量复验，不能算作该18项已执行。

报告位于本地`tests/unit/reports/unit-report-project-ignore-{red,green,subset}-p0-08-project-ignore-*`，这些开发快照为dirty，不冒充最终PR head。最终提交后重新运行计划范围并生成精确head证据。

## 文档与安全边界

README.md、README.html和版本化automation prompt同步新模板／探针、旧保护保留和Git语义边界；不改根五行验证要求，不操作live automation。Onboard SKILL/REFERENCE的通用“追加缺失行”说明仍准确，不作无意义改写。CHANGELOG记录新规则和实际验收变化。

修改前Git基线的受管源备份在私有临时目录保存，保留到最终head验证、独立review和任务PR合并之后；不提前清理，也不处理任何真实迁移备份。当前过渡CLI的完整v2初始化／数据所有权与迁移能力仍待P1，本项不会静默把这些未完成部分标成通过。

## 主线程完整验证与 scoped readiness

在中间提交`7a6a51a4712cf1114c3ba9e01aba9c4df4bf9227`上，主线程原生全量265 tests/535.719s/exit0，正式报告及envelope通过校验；包含18项子集之外的冒号否定、NUL短响应和其他安装路径。原生CLI／Git smoke证明fresh与legacy场景的12个本地路径、19个共享／嵌套路径与重复字节幂等；旧完整模板和自定义规则保留；docs/冲突exit3并报告来源、保留用户规则；隔离HOME无新增内容。

两种README实际发布的gitignore代码片段分别通过11个原生Git probe；仅修改说明与配置片段，不改CSS或交互，不把该语义检查称作浏览器视觉／Web E2E通过。没有新增浏览器调用、Web测试框架或live automation操作。

Ruff同配置按函数／诊断比较：生产文件26→26、workflow tests12→5、multi-project tests2→2，无新增；全文件扫描并未清零。不修改函数签名／返回结构，不为本项扩大既有类型债务清理。Code Readability Review无新增结构问题，复用原有Git helper并隔离测试全局excludes影响；Ponytail pass无额外抽象或需要删减的生产层。

Release Readiness Review：ready，仅限P0-08模板和直接规则检查消费者。故障模式由真实Git／CLI覆盖，继续使用原解析与追加策略，没有服务、队列、外部安装或新容量限制；报告保存命令／stdout／stderr／退出码和版本身份。回滚限定受管源提交，用户旧规则、索引和数据未被清理。完整v2初始化、保留路径业务所有权、tracked私有数据识别／处置和迁移仍由P1承担，当前过渡生命周期不能因此用于真实项目。

本记录提交后，必须对新的最终head重跑计划全量及原生smoke，再独立review；不把上述中间提交报告重标为最终head。私有编辑备份和临时验证脚本继续保留，直到最终验证、review及任务PR合并完成。

## 首轮独立 review 修正

`P008ReviewOne`在完整冻结diff中指出一处P2矛盾：版本化automation prompt前面的init/reset段仍要求验证旧Trellis ignore路径，与下方已更新的project-only SBTD/Graft探针契约不一致。已把前者改为引用下方同一共享／本地探针集，保留其他安装、JSON和根仓库五行契约，不同步live automation。该问题修复前的`71478ed76bf2deff7b46d217207041fee6f29343`全量265 tests/391.213s与原生smoke均通过，但不能据此把后续修复head直接标成已验证；修复后重新绑定报告并独立复审。

## 第二轮 review 与 advisor 修正

`P008ReviewTwo`的正式结果和后续advisor合计九组已采纳问题：支持的固定共享路径被精确忽略时，原代表性探针集合不完整。覆盖旧`docs/lessons.md`入口、context ADR、undated归档、iOS/Android flow、受管React Bits Skill、任务附属产物/bootstrap、UI上下文、测试源码、根Git控制文件。新增一个真实CLI回归，共18个独立契约反例：第一批6项在补生产前全部red、补后green；后补12项也在对应生产修复前全部red，最终18项1.598s全部green。生产仍只有同一探针集合扩展，不新增解析器或检查框架；共享探针由19增至37，本地12项不变。

补查的第十条建议（强制所有项目追踪旧Claude生成集成）经PRD§11.7及README条件说明复核撤回：保留旧缓存不代表接入平台，人工移除旧`.claude/`排除以项目确实需要追踪为前提。README两入口明确此边界；不把旧Trellis集成恢复成v2必需条件。代表性探针保证已声明固定分支，不能声称穷举任意自定义文件名或替代P1实际迁移清单。

同轮local-only API汇总曾宣称TMPDIR隔离，但raw未记录可独立核验证据；已缩窄为脚本显式HOME/CODEX_HOME/USERPROFILE/XDG隔离及HOME空态，不改raw/时间/退出码/SHA。该报告由`.git/info/exclude`忽略，未追踪；修正后envelope再次通过，不存在重标源提交。新增生产探针将另提交并重跑最终head全量与扩展原生smoke，然后独立复审。

扩展后的影响范围重跑出现1个测试失败：broad `tests/`冲突诊断只预览前三个路径，旧测试把某个manifest是否出现在预览里当成契约。删除该偶然成员断言，而非换钉另一个路径；保留非零退出、具体规则来源、用户规则不删除。失败case定点通过后，原18项子集在5.363s全部通过；扩展原生smoke的21场景通过，fresh/legacy各检查12本地与37共享／嵌套路径，另含19条冲突。未提交阶段报告保持dirty标识，最终head全量和scope readiness须在冻结后复验。
