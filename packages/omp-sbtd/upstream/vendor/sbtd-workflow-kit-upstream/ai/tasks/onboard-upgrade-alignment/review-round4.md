# PR #110 第四轮7项修复

基线2b913a66d6deabc042f46eb7d536e7f93b731c9b，沿用strict、feat/onboard-upgrade-alignment。用户确认按优先级修复全部七项；编号F01—F07对应本轮审查，不混用旧R/N/T记录。未完整调用grill-with-docs：需求明确且无领域歧义。

## 顺序与验收

| 顺序 | 级别 | 验收 |
|---|---|---|
| F01 | P2高 | 缺失Skills根与AGENTS的物理别名重叠在计划时拒绝，不生成应用后无法恢复的封存范围 |
| F02 | P2高 | 计划使用的依赖环境在隔离执行器也可用，或计划阶段明确拒绝；不取消隔离安全边界 |
| F03 | P2 | CRLF原行保留，新增POSIX PATH赋值不包含CR，不破坏原有PATH目录 |
| F04 | P2 | 实际PowerShell5.1编码无法证明Unicode npm shim指向时不得报告matched；不扩展为wrapper执行或Node证明 |
| F05 | P2 | RPC拒绝Boolean ID冒充Number，MCP要求jsonrpc2 envelope，Codex兼容独立 |
| F06 | P2 | OMP继承来源未发现时legacy不能报none，可报告unknown，不扩大未选provider |
| F07 | P3 | Windows Bash/zsh旧PATH检测识别所选bin的POSIX别名 |

## 约束与方法

保留缺失host的安装、受支持staged嵌套/canonical installed续作、restore intent+absent窗口、OMP user-wide探测四项契约。私有vault为受信历史，不自动执行历史代码或销毁备份。只维护仓库源；允许既有授权的当前草稿PR提交/推送/CI，不授权合并、发布、sync、真实HOME应用或旧资产清理。

BDD在REFERENCE Markdown持久场景，中文正文/英文Given-When-Then，不创建.feature。测试沿用公开CLI、真实inventory、host render/verify；协议注入仅证明协议边界。唯一验证controller为主会话。LSP实测未配置，使用源码调用点和契约。

Book Gate Plan：DDD not-required；DDIA在范围/依赖/隔离设计明确后confirmed；Legacy每项真实red后characterized；Refactoring生产编辑前proceed，F01共享路径判断若提取需行为保全前后证明；Release待完整验证和独立复核后评估。原始失败与同stem中文汇总保留reports/review-round4/；本地dirty不冒充精确CI。

## 已实施与定点证据

- F01：共享 `sbtd_upgrade_paths.py` 抽取同一物理包含判断；提取前后61项均通过，缺失根别名新回归由未拒绝变为写前拒绝，inventory100项通过（6平台跳过）。U20/U27删除提前拒绝后失去意义的精确错误码断言，原件与vault保全断言保留。
- F02：真实临时解释器证明父user-site可导入tomlkit而`-I`不可；原计划成功的red修为明确拒绝。向隔离环境补齐同一包后真实CLI计划成功、vault仍为空；不更改真实解释器安装。
- F03：真实Bash/zsh red均不能找到原PATH末目录命令；LF新增块修复后13项profile回归通过（1 Windows跳过），原CRLF保留。
- F04：协议边界夹具复现5.1非UTF8仍matched；实际引擎版本／代码页证据门修复后16项通过（3 Windows跳过）。原生5.1及现有合法ASCII shim等待Windows CI，不用macOS证据替代。
- F05：Boolean ID、缺失／错误MCP版本均有公开verify red；Number表示与Codex无版本回显正向控制保持。20项协议／OMP回归通过；真实子进程管道负例拒绝，numeric／valid通过，标记contract-backed而非真实Graft。
- F06：合法不完整runtime、active文件不存在且继承有旧项时由none改为unknown。首个无效scope夹具错误已保留并纠正；12项legacy回归通过。
- F07：POSIX别名旧PATH可检测。独立复核的同前缀／子目录误报和zsh数组括号漏报均有red／green；完整目录边界正反控制通过。
- 集成升级326项通过（18平台／opt-in跳过）。ruff、显式受管Python环境ty、Python compileall、Bash语法通过；首个ty使用了错误工具环境、ruff闭包/import错误均已保留并修正。

## 独立复核与真实消费链

ScopeDependencyReview、HostEvidenceReview只读，不运行测试、不写代码。前者对新helper未追踪提出交付提醒，确认显式纳入提交后撤回为源代码缺陷；最终F01/F02 clean。后者F07两个边界修正复核关闭，F03—F07最终clean。Code Readability Review通过，Ponytail没有可合理删除的安全seam或抽象。

真实私有临时域完成37资源plan→staged apply→已安装副本verify/probe→retry→recovery plan/apply。真实Codex、OMP均加载33 Skills／6工具；shell对齐，整体aligned。恢复后旧Skill壳与CRLF profile逐字节一致，新配置与安装代码移除，vault原件保留。错误传入recovery不支持的`--yes`仅CLI拒绝，正确确认命令后完成；失败报告不删除。不触碰真实HOME配置或原GUI会话。

README.html实际浏览器新段落可见、无横向溢出；README.md、README.html、版本化automation prompt与CHANGELOG均维护第四轮边界；live automation未访问／同步。

## 完整验证进度

初次与冻结手写源码后的本地full各1771项、27跳过、1 error，均为不同followup夹具的来源漂移拒绝。两次失败证据保留；失败项及11项followup前置类定点均通过。未放宽来源守卫。

完整观察器1771项（27跳过）通过，随后无观察器的原生full1771项（27跳过）也通过。后续取证确认真实followup计划封存catalog `source: "."`对应的当前Onboard包directory，且目录snapshot包含缓存；隔离实验复现compileall改变该snapshot。首轮源码编辑、第二轮compileall均与全量并发，这是已确认的验证输入污染机制；原始错误未保存具体来源路径，故不把机制证据冒充两次失败的逐路径归因。最终无写入完整重跑通过，生产守卫未变。

后续静态复核修正F04测试隔离：只stub显式`selected-powershell`，真实Windows ACL子进程仍委托原run；失败控制要求编码未证明原因，不能让更早隐私拒绝冒充目标red。定点／ruff通过，reviewer再次clean。代码9ee8b317ce5148cf6634abd4b986b8a2ab0990ee与测试修正ea62faa已推送；这一测试修正本身未改变生产实现。

macOS原生CI9ee8b31的U32在父解释器正向控制失败：fixture硬编码user-site布局不适用于framework Python。改由临时解释器的`site.getusersitepackages()`／`sysconfig.get_path("purelib")`取得两路径，保留真实父／`-I`负例及补依赖正向控制；本地U32、ruff及326项升级全子集通过，独立复核clean。布局修正已包含在acaf83a及其精确原生CI通过证据中；0e682f2不是最终交付head。

Lessons split name: kuno；来源`.sbtd/developer`只读resolve为ready。新增`LESSON-20261005-kuno-freeze-sealed-inputs`到validation-scripts topic、index与高频短入口，只记已证实机制与归因限制；不记录猜测根因。

最终F02执行消费链补充：两个public apply在校验封存ID确认后、stage／vault写入前复用当前隔离依赖门，防止由不同解释器执行时沿用旧计划环境证明。U32真实CLI执行red原为误导性plan-stale；修后升级apply缺依赖为exit2且空vault／无配置，恢复apply缺依赖为exit2且既有vault与配置原字节不变。恢复输出必须位于vault的夹具错误已修正，原始scope-violation保留。326项升级子集、ruff／ty／语法以及再次37资源真实宿主／重试／恢复均通过；独立复核clean。此后冻结源码，最终完整重跑与精确新head CI不复用旧0e682f2结果。

## 最终验收与交付

生产／测试提交`acaf83a39679f1f6605d54a9b6ce43847b3bbe31`：本地最终1771 tests／27 skip通过；精确[run37291867601](https://github.com/KunoLu/640-skills/actions/runs/37291867601)三平台全绿。

| 平台 | 原生结果 |
|---|---|
| Linux | 全量1771 tests／47 skip；最低tomlkit56项；大小写敏感路径控制通过 |
| macOS | 安装器271 tests／2 skip；升级326 tests／18 skip；U32真实解释器布局及plan/apply/recovery控制通过 |
| Windows | 安装器49项、PowerShell15项、升级326 tests／30 skip；原生PowerShell5.1 Unicode shim、Git Bash alias legacy和真实ACL路径通过 |

原始CI日志、同stem中文汇总、通用v1 envelope及schema／报告摘要校验均在`reports/review-round4/ci-code-acaf83a*`；历史9ee8b31的Windows fixture／macOS布局失败和ea62faa的macOS失败另存，不覆盖。Final Full Rerun passed；生产代码之后不再修改，最终记录提交另跑精确head CI。

Release Readiness Review：ready（仅仓库修复交付）。依赖检查30秒期限；RPC原期限、原件与确认、受信vault和独立恢复不变；无服务队列／跨服务背压需求。JSON原因和回执可观测，REFERENCE给出运行／恢复边界；真实临时域恢复证明已取得。原GUI、真实HOME部署、live automation同步、旧资产清理、合并与发布均未执行，不属于本次通过声明。

README.md、README.html均更新用户可见计划／执行与证据边界；版本化automation prompt新增路径模块扫描并更新同一边界；CHANGELOG中文未发布章节已维护。Lessons为已验证本地kuno身份的单条追加，历史块不改写。任务关闭证据指向本段与check.md，所有scope外本机路径保持未写。
