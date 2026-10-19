---
schema_version: 1
id: windows-ci-acl-optimization
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择strict用于Windows CI优化及ACL安全原语改动
status: "done"
branch: perf/windows-ci-acl
created_at: '2026-10-14T18:32:31.998550+08:00'
updated_at: "2026-10-14T20:34:17.036970+08:00"
completed_at: "2026-10-14T20:34:17.036970+08:00"
---
# v2.0.1 Windows CI耗时优化与进程内ACL证明

## 授权与范围

用户明确选择strict，并确认：Windows ACL进程内实现纳入v2.0.1；Windows按4分片，ACL改动完成后再评估；按“Windows实测行覆盖与分支覆盖完全一致、关键用例强制保留、移除清单经用户审阅后生效”去重；Linux/macOS同步评估优化空间。PR121/122的admin合并授权是既有明确范围，不自动扩展到PR124；本任务先交付实现、验证与去重审阅清单。未授权发布v2.0.1、移动tag、live同步、清理备份或修改用户本机安装。
未完整grill：目标、约束和取舍已由用户逐项确认，无领域歧义。

## 基线（原生CI，已保存逐例报告）

- 精确head CI38532355204/38538887444：Windows墙钟约56分钟，分片1/2/3为20.6/11.4/55.8分钟，测试总量5172秒/507例；Linux总量2489秒、最慢分片22.9分钟；macOS测试约5分钟。每个job准备步骤仅十几秒。
- 6个用例占Windows耗时59%，同一用例Windows比macOS慢30～60倍。先前诊断：一次恢复1250次PowerShell ACL调用耗时868.9秒，约0.7秒/次。
- `.github/test-weights.json`缺少`test_sbtd_cleanup_upgrade_integration`(1853秒)、`test_sbtd_cleanup_upgrade`(597秒)及Linux`test_sbtd_migration_cleanup_drift`的权重，导致分片严重不均；且只能按整模块分片。
- 507个Windows用例中495个同时在Linux/macOS执行（占Windows耗时99.7%）；最慢用例多为Windows关键验收，单靠去重收益有限。

## 设计与不变量

1. ACL证明改为进程内Win32安全API（ctypes），判定与原PowerShell脚本逐项一致：属主必须是当前用户；DACL每条ACE必须为允许型且主体属于当前用户/SYSTEM/Administrators；NULL DACL、未知ACE类型、无法读取或解析一律失败。按句柄读取并核对与lstat为同一目录对象，不跟随重解析点。创建时设置当前用户为属主及受保护DACL（仅当前用户FullControl，容器/对象继承），只作用于本次新建目录。不引入ACL缓存，不放宽900秒限制，不减少任何检查。原PowerShell脚本移入测试作为差分对照。
2. 分片：Windows改4片；无类级/模块级fixture的模块可按用例分配，带setUpClass/tearDownClass或setUpModule/tearDownModule的fixture整体保持在一个分片内；权重由最新原生报告生成，缺权重新例按已有实测中位数估算并明确列出，不遗漏新测试。
3. 去重：以ACL改动后的Windows实测覆盖为筛选条件，计算覆盖并集不变的候选子集（贪心算法不保证数学上的最小集合）；再逐项审查断言、输入边界、平台及状态转移，不能以覆盖重叠等同于行为冗余。`WINDOWS_CASES`、必需原生用例、全部PowerShell安装器用例及含Windows专属断言的用例强制保留；保留子进程、覆盖盲区与失败/跳过用例。移除用例仍在Linux/macOS执行；具体移除清单经用户审阅后才生效。
4. 先前计划的独立阶段0测量改为：以两轮已保存基线对比改动后逐例耗时；若某慢用例未明显下降再单独诊断。去重所需的覆盖测量在ACL改动后进行，避免以将被替换的代码路径为基准。

## Book Gate Plan

| Gate | 触发 | 状态 |
|---|---|---|
| DDD | 未完整grill、无新领域规则 | not-needed |
| DDIA | 私有目录所有权与证明语义 | confirmed（本轮补证）：权限决定无缓存、真实owner/DACL是事实源；trusted单controller命名空间与非原子mkdir+ACL旧边界不变，不冒充消除创建竞态 |
| Legacy | 既有ACL判定行为 | characterized：既有native脚本对照及失败基线保留；run38557031285已通过强制foreign-owner和empty/NULL DACL；读取失败为故障注入，未知ACE/创建竞态只做静态审查不冒充实测 |
| Refactoring | 修改生产ACL原语与CI调度 | proceed / normal：不再扩展生产结构；复用既有verify_reports防止测量消费未验证分片 |
| TDD/BDD | ACL判定与分片行为 | 源仓cleanup设计§9；选择器/权重六项review发现有red/green；97项本地通过（4 Windows skip），新增Windows必需ACL项实际passed |
| Project validation | 三平台原生CI、耗时对比 | ca3d520/run38552195519及9677eed/run38557031285连续两轮成功；后者十job全绿、八份分片下载复验，Windows509/Linux2139/macOS686，skip事件33/50/20 |
| Independent security/readability | ACL安全原语 | NativeAclSecurity、ShardRegressionReview、DedupBehaviorReview独立复核收敛，修正后无未解决changed finding；新native安全项已实际通过 |
| Release readiness | 安装/升级/恢复运行路径 | ready：仅实现PR交付，尚未合并/发布；数据schema、备份归属、单controller/非原子创建边界保持 |

## 实施记录

- 实现：`sbtd_migration_files` 以ctypes调用Win32安全API替换`_run_privacy_script`（两个调用点），原PowerShell脚本移入测试作差分对照；新增Windows必需用例`test_windows_native_acl_proof_matches_the_powershell_oracle`。实现保留在原模块内，因为运行时文件清单逐一列出脚本名，新增模块需改动多处清单。
- 分片：`run_ci.partition`按fixture单元分配（无fixture用例逐个，setUpClass/tearDownClass类或setUpModule模块整体），同片内保持发现顺序；权重改为逐例秒数，由`--refresh-weights`从同一修订的成功分片报告生成（初始来源fd9f5d3，PR#122最终head）；Windows改4片。
- 设计调整：原计划“缺权重即报错”改为“按中位数估算、在分片清单与摘要中列出”。原因：新增用例在首次CI实测前不可能有权重，硬性报错会让每个新增测试的PR在执行前失败，并与既有“新增测试不遗漏”契约冲突。
- 原生Windows诊断（临时分支diag/windows-acl-native，不合并）：
  - run 38551130307：差分测试与网关测试通过；在main旧实现上新测试失败，原因为“ACL proof must not start a process”（红灯成立）；恢复全流程用例915.3→74.5秒；slow-2/slow-3因诊断脚本缺少PYTHONPATH而导入失败，与改动无关，失败轮次保留。
  - run 38551669218：4个清理升级集成用例473/469/458/454→52.0/49.7/44.3/44.2秒；大小写敏感provider用例296→12.9秒；main旧实现上整个模块同样报5个错误（`mkdir(0o700)`夹具在Windows不可证明私有），证明非回归，且这些用例不在Windows CI范围。
- 独立审查：本轮实际调用NativeAclSecurity、ShardRegressionReview、DedupBehaviorReview。此前“子代理不可用”判断不成立，自审不算独立审查；已修复静默省略foreign-owner及调度/权重六项缺陷并补充有意义的回归。Gate历史顺序缺口如实保留，不倒填此前before-dev通过。
- PR：#124，保持OPEN，未获本PR合并/发布授权。PR121/122已独立合并，不把其授权扩展到本PR。
- 首轮完整原生CI：Windows508项/33skip事件，四片测试90.234/217.047/125.125/136.141秒；Linux2136项/49skip事件，三片544.075/854.212/812.598秒；macOS686项/20skip事件，280.639秒。未做任何去重删减。原始分片及比较证据保存在本任务私有reports；计时存在runner环境差异，不宣称受控性能实验。
- 已用首轮native结果刷新权重并复跑：Windows四片测试133.703/141.781/193.047/201.578秒，最慢job墙钟235秒；Linux最慢job998秒；macOS349秒。恢复完整生命周期68.578秒通过，原900秒子进程期限不变。两轮Windows最慢job约244/235秒，保持批准的四片，不为微小额外收益增加并发。Linux保持三片，macOS单job。
- 去重：508项完整诊断中筛出100个覆盖重叠候选，12.849秒；行为审查仅确认1项同等fixture且被更强断言覆盖，0.141秒。用户审阅具体清单后明确选择“全部保留，不增加排除规则”，本轮零排除，见dedup-review.md。先前六慢例合计253秒的口头数值有误，按已记录六个值合计277.6秒；最终以完整native报告为准。
- README双语入口及CHANGELOG已更新，长期场景写入cleanup设计§9；版本化automation prompt现有第27行已约束完整互斥/同SHA/原生行为与成本，不需无意义改写；live automation未触碰。

## 验收场景

- Given新建私有目录；When在原生Windows创建并校验；Then进程内实现与PowerShell对照结论一致，且无需启动PowerShell。
- Given目录被加入非受信Everyone/Users或Deny ACE、属主不符或为重解析点；When校验；Then拒绝且不改动目录。继承开启本身不是拒绝条件：按继承ACE的实际主体及类型判断，与旧PowerShell合同一致；新建私有目录的DACL仍主动保护以阻止继承。
- Given分片计算；When新增用例无权重；Then按中位数估算并列出，不遗漏；When用例重复或分片遗漏；Then拒绝并集校验，保持平台计划范围及fixture生命周期。
- Given覆盖及行为冗余审查完成；When用户选择全部保留；Then不新增Windows排除规则，原用例全部保持并增加本轮回归，强制保留用例实际执行通过。
- Given最终head；When三平台CI；Then全部通过，Windows墙钟显著下降，900秒恢复期限不变。

## 最终交付边界

实现验收提交`9677eed1419fe18f0de1a2207f2f44a21c49f6d4`，CI [38557031285](https://github.com/KunoLu/640-skills/actions/runs/38557031285)；raw/native与中文汇总保留本任务私有reports。最终记录提交只更新任务、用户去重选择及lesson，不更改载荷/测试，仍需以实际新head CI核验远端状态，不能套用旧SHA声称新head验证。

用户选择保留全部用例是本轮去重的正式结果，不是遗漏。主收益来自进程内ACL；Linux分片再均衡、macOS保持不变已完成。双语README/CHANGELOG及长期场景完成；automation prompt第27行合同适用，无需改写；无live同步。长期lesson使用合法本地kuno身份，仅写自己topic/index marker。

无本机真实安装或生产迁移，无备份销毁，不创建v2.0.1 tag/Release；诊断分支/原始失败证据保留，不并入PR。安全证明不承诺消除既有同UID并发换目录竞态或新增线程impersonation支持。性能数字来自原生CI观察，不是同机控制实验。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-14T18:32:34.668168+08:00 | planned | in-progress | 用户确认ACL纳入v2.0.1、Windows4分片、覆盖一致去重及strict；开始实现 | 基线CI38532355204/38538887444；诊断run38522065660 |
| 2026-10-14T20:34:12.024830+08:00 | in-progress | checking | 三路独立复核已闭环，精确候选三平台nativeCI通过；用户完成去重清单审阅 | run38557031285；97项本地验证；独立security/scheduling/behavior审查；用户选择全部保留 |
| 2026-10-14T20:34:17.036970+08:00 | checking | done | ACL、四分片及权重优化完成；用户选择零去重；双语文档和原生验证齐备，PR124仅交付未合并发布 | 9677eed精确CI十job通过，Windows509/Linux2139/macOS686；八分片复验；Release Readiness ready |
