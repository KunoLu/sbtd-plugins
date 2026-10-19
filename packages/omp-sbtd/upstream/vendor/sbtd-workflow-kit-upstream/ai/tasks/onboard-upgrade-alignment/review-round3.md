# PR #110 第三轮审查修复

基线：1ae9c321cf9419204b30c7e4f6111c6a2f349995。用户要求三个P1优先，再按风险依次修复其余全部问题；沿用strict，分支feat/onboard-upgrade-alignment。本轮T01—T13对应最新13项，与旧R及N编号分开。

未完整调用grill-with-docs：需求明确，无领域歧义。保留缺失host即使preserve仍安装、受支持嵌套与canonical installed续作、restore intent+absent窗口、OMP user-wide probe四项契约。vault是受信历史，不自动执行旧代码、不删除备份。允许本分支提交／推送与草稿PR CI；不授权真实HOME应用、同步、旧资产清理、合并或发布。

## 风险顺序与验收

| 顺序 | 级别 | 项目 | 验收 |
|---|---|---|---|
| T01 | P1 | 未写入证据被错误认领 | retry与旧pending checkpoint均不认领已证明未写的用户文件 |
| T02 | P1 | Codex真实项目配置泄漏进探针 | 私有host探测不加载所选项目中的其他MCP／凭据，受管连接仍真实可加载 |
| T03 | P1 | APFS Unicode等价缺失目标 | NFC／NFD别名在目标写入前拒绝，preserve不被穿透 |
| T04 | P2高 | pending未知结果静默跳过 | 有intent且现场非before／非可归属desired时恢复blocked，保留现场与原件 |
| T05 | P2高 | Shell写集依赖漏检 | bin／命令解析目标与同批写集冲突先拒绝，不产生可预见partial |
| T06 | P2中 | config_home物理别名 | 合法别名封存一致；真实不同目录仍拒绝 |
| T07 | P2中 | 既有BOMless PowerShell Unicode | 不改无关原字节，受管PATH对5.1编码安全 |
| T08 | P2中 | PowerShell stdout编码 | 输出与Python解码一致，Unicode路径不误拒绝 |
| T09 | P2中 | Unicode换行路径 | 只按协议LF分割，保留U+2028／U+0085路径字符 |
| T10 | P2中 | npm shim标点路径 | 允许语言中真实字面字符，动态展开仍拒绝 |
| T11 | P2中 | OMP继承legacy | 在实际有效来源中检测旧入口，不扩未选provider |
| T12 | P3 | 非文件legacy | present非文件为unknown，不冒报none |
| T13 | P3 | unsupported汇总 | 保留已证明不支持，与unverified区别 |

## 方法与证据

BDD沿用REFERENCE Markdown中文场景＋英文Given/When/Then，不创建.feature。复用公开CLI、真实inventory、plan/apply/recovery、host render/verify seams。故障注入只改变真实I/O时机，不用FakeInventory推导生产契约。主会话是唯一writer／验证controller；独立reviewer只读。当前LSP未配置，源码调用点和契约作为影响证据。

Book Gate Plan：DDD not-required；DDIA在持久归属／隔离设计明确后confirmed；Legacy各切面red后characterized；Refactoring各切面沿用现有seam，生产编辑前proceed；Release在最终本地／原生CI／真实smoke与独立复核后评估，当前pending。不得复用旧head通过证明。

原始失败、green和同stem中文汇总位于reports/review-round3/。本地dirty只作为developer-local／local-only；原生CI另绑定精确SHA。平台skip不算证明。上一轮reviewer越界源码候选不作为本轮根因事实，逐项用当前真实消费者验证。

## 局部与真实验证

- T01—T13按优先级逐项red后修复并green，原始失败均保留。T01使用真实库存／文件写入检查和恢复；T02真实Codex app-server确实启动未选项目MCP的red，改为私有配置untrusted后未启动哨兵且受管peer connected；不是模拟Codex配置读取。
- T03普通APFS回归通过，Case-sensitive APFS独立卷10项（5 skip）互补验证Unicode等价拒绝与合法不同目标。镜像验证后已卸载，仅清理本次自有测试载体。
- T07本地为ANSI解码模型＋真实pwsh执行，原生Windows5.1旧profile用例等待CI；T08真实pwsh非UTF8输出、T09真实Bash特殊路径均red/green。实际npm cmd-shim生成器产出的O'Brien三种wrapper与sh／PS字面%目标绑定通过；不声称执行wrapper或Node证明。
- T11复用实际OMP来源发现器已启用sources，不把含设置文件／disabled候选的effective_inputs误当全可扫描配置列表；启用与禁用provider正反对照通过。
- 集成初跑317项出现两处旧FakeHost遗漏command_identity；只补测试producer必需元数据，不在生产放宽。修后完整升级回归317 tests，OK，16 skip。Ruff／ty、compileall和Bash语法通过。
- 独立host reviewer无发现；engine reviewer指出home身份会改写精确已选缺失AGENTS preserve键，真实red后改为精确选定拼写优先，复核已通过。两位均未运行验证。
- 最新包真实隔离37资源plan／apply、Codex／OMP各33Skills与6工具通过，installed retry与recovery完成，原profile与旧self内容恢复。真实Codex隔离测试额外以SBTD_NATIVE_CODEX=1执行通过。完整项目suite已启动，尚不计完成。

## 文档与门禁

README.md、README.html、REFERENCE U25—U30、版本化automation prompt与CHANGELOG均需同步并已更新；不改live automation、ENTRYPOINT或全局生效目录。README.html新增两个区块经实际Chrome DevTools隔离页可见性验证。无业务Web／Mobile变化，Playwright／Maestro专项not-needed；Ego沿用前轮不可用证据，不修改浏览器配置。

DDIA: confirmed；Legacy: characterized；Refactoring: proceed / normal；Ponytail／Code Readability：沿用既有回执、解析器、标准库与真实seam，无新增依赖／框架；独立复核已闭环。Release仍待完整项目和新head原生CI。BDD: traceable，中文场景＋英文Given/When/Then；Cross-repo context: not-needed；API Contract: verified（schema与原生协议）；Mock Strategy: contract-backed，真实宿主另列。RTK: skipped-for-report。

Lesson身份经installed helper只读确认local kuno；新增LESSON-20261005-kuno-no-write-evidence-precedence至topic／index，旧历史不改、短入口不堆详情。来源受限review必须隔离越界证据；本轮修复只使用真实消费者复现支撑的根因。

## 本地完整验收

`env SBTD_NATIVE_CODEX=1 python -B -m unittest discover -s tests -p 'test_*.py'`：1762 tests，1350.066秒，OK，25 skip。没有重复启动第二套全量；原生Codex隔离在本轮完整运行中实际执行。所有本地red、集成替身缺字段失败、修正与最终报告均保留。旧profile的Windows5.1实测仍待精确head CI；不将编码模型当原生结果。

## 原生Windows反馈与收口

首个修复提交d8c86c695f398c3ecf6bd2ac137862073c6814e0的CI run37256529384：Linux全量1762项（44 skip）、macOS升级317项（16 skip）通过；Windows317项出现唯一T08失败，原因是graft-not-resolved，而不是UTF-8解码失败。同轮Windows PowerShell5.1的新建及既有ANSI profile Unicode加载已实际通过。

隔离PowerShell环境原先没有PATHEXT，原生.exe选择因此无法按Windows规则解析。仅在该Windows shell探针保留扩展名列表，不向PATH加入受管bin，不执行wrapper。回归同时运行真实pwsh与powershell（可用者），Windows CI增加前置两项定位检查，完整套件不减少。独立host reviewer只读复核无新问题；本地相关61项（4 skip）及Ruff／ty通过，新head原生结果待完成。失败原始日志及schema/digest校验的generic v1证据保留在ci-d8c86c6*。

README两入口／REFERENCE／版本化prompt已明确真实命令优先级和输出编码，本次仅恢复Windows环境解析要素，不需重复改写这些说明；CHANGELOG记录验证顺序与PATHEXT边界。此前完整本地结果不冒充该Windows追加分支的实测，最终以新head Windows定点及完整CI为准。

## 最终代码验收

提交`7d360b65a2c82926ae683b4518e68cc7b2a2655e`的[原生三平台CI run37260456824](https://github.com/KunoLu/640-skills/actions/runs/37260456824)全部通过，三个job末次checkout清洁检查成功。

| 范围 | 真实结果 |
|---|---|
| 本地全量（启用真实Codex隔离） | 1762 tests，OK，25 skip |
| 本地升级／恢复 | 317 tests，OK，16 skip |
| Linux全量 | 1762 tests，OK，44 skip |
| Linux最低tomlkit／大小写敏感路径 | 56＋1 tests，OK |
| macOS安装器／工作流 | 271 tests，OK，2 skip |
| macOS升级／恢复 | 317 tests，OK，16 skip |
| Windows安装器／PowerShell子集 | 49＋15 tests，OK |
| Windows根边界／TOML／junction／DACL | 22（1 skip）＋3＋1＋1 tests，OK |
| Windows PowerShell编码／命令解析定点 | 2 tests，OK，无skip，涵盖实际可用pwsh与powershell |
| Windows升级／恢复完整范围 | 317 tests，OK，28 skip，2319.673秒 |

平台skip不计作该平台证明。原生Windows新旧profile的Unicode、非UTF8控制台输出、PATHEXT命令解析均实际通过；Codex项目配置隔离在本地显式启用的真实app-server中证明，不把CI opt-in skip当宿主通过。失败CI与本地失败均保留。

CI元数据／各job原始日志／同stem中文汇总见`reports/review-round3/ci-code-7d360b6*`，generic v1 envelope已通过schema及每份报告SHA校验；不把TXT声明为v2场景执行绑定。Evidence Source: ci；Source Revision: exact；Environment Alignment: verified；Evidence Publication: not-configured（GitHub原生Checks可见，无自定义publisher）。

### Release Readiness Review

- Status: ready，限本轮仓库能力交付；不是合并、部署或发布。
- Production path：显式升级／恢复、selected host/profile探测；三个P1及其余十项全部闭合，四项用户保留契约未变。
- Failure safeguards：明确no-write证据优先；未知intent现场blocked保全；缺失Unicode别名和Shell写集依赖写前拒绝；不自动执行历史vault代码或删除备份。
- Isolation/limits：Codex真实项目配置层不加载，OMP仍user-wide；有界RPC和既有超时不变。Darwin规范化等价缺失名称保守拒绝，不声称对所有外部文件系统证明可区分性。PowerShell只恢复所需扩展名解析，不预置bin；shim仍不证明Node或wrapper执行。
- Observability/runbook：分层JSON、REFERENCE U25—U30、README与完整raw证据；legacy只消费有效来源，unknown／unsupported不丢失；无新服务／遥测／后台设施。
- Rollout/recovery：草稿PR；真实隔离37资源升级、Codex／OMP各33Skills与6工具、installed retry及恢复原件通过。真实HOME／GUI重载、sync、旧资产退出、备份销毁均未授权且未执行。
- Required validation：局部、完整本地、独立复核、真实smoke和精确三平台CI通过。Web／Mobile业务专项not-needed；README浏览器实测通过，无必需检查豁免。

最终验收记录提交后，交付head使用自身原生CI结果，不将本节代码提交的绿灯冒充不同head。
