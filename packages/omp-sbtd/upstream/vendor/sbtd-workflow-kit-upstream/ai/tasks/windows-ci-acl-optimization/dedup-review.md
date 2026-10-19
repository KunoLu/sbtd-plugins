# Windows 用例去重审阅清单

状态：用户已审阅并明确选择“全部保留，不增加排除规则”。本轮零排除，所有原用例继续执行；下方候选与证据仅保留为审查历史，不是待执行清单。

## 证据与判定

- Windows 原生覆盖诊断：run 38552310342，诊断 head `c0588c7c7fe41ea1ce3c39ae85cf6ef99fe4692f`；508个用例、四个成功分片，完整互斥记录已核对。
- 非覆盖插桩的实测耗时：PR124 run 38552195519，head `ca3d520e2aa6e3d78de487968fbd6bc5f94a262b`。
- 关键原生、全部安装器、已启动子进程、覆盖盲区及未通过项强制保留。其余100项仅在生产脚本行/分支覆盖上有重叠，合计12.849秒，不能等同于行为冗余。
- 独立审查 `DedupBehaviorReview` 展开fixture并比较调用链、输入边界和消费者断言，只有以下1项达到行为等价；其余99项保留，不以覆盖并集相同削弱权限、路径、Unicode、状态、漂移或保留行为验收。
- 覆盖只记录同进程生产脚本，不声称覆盖子进程、复制安装路径或Win32 API内部；其余native验证不能由本数据替代。

## 唯一可批准的排除项

| Windows排除候选 | 必须保留且实际通过的替代见证 | 同等输入与断言 | 实测候选耗时 |
|---|---|---|---:|
| `test_sbtd_upgrade_hosts.OmpAuthoritativeRegistryTests.test_structured_dump_tools_pass` | `test_sbtd_upgrade_hosts.VerifyProbeTests.test_omp_probe_pass` | `_aligned_omp`展开后与见证的runtime/package/beta-skill/project/host/config/default ProbeRig一致；两者均验overall pass及host_load verified；见证额外验session-connect、skills、精确beta-skill证据和脱敏 | 0.141秒 |

两者诊断覆盖完全相同：1552条生产代码行、2009条arc。相同调用链为 `verify_hosts` → `_verify_mcp_host` → `_host_load_check` → `_probe_omp` → `_omp_registered_tools`。两个类均直接继承unittest.TestCase，无不同的setup/teardown语义。

仅减少Windows重复执行；原用例代码保留，Linux/macOS仍执行。不得同时排除替代见证；若见证消失、被跳过或失败，必须阻断相应Windows验收。

## 收益与边界

0.141秒是一次原生case耗时，不是墙钟收益承诺；总Windows运行耗时的主要下降来自进程内ACL和均衡分片，不来自删除测试。此次审查不支持批量删除其余99项。

确认该具体清单后才应用Windows选择器，并对照完整选用集合、行/分支并集、原生必需项和三平台CI复验。未确认则保持现有508项基线加本轮新增回归，不自动执行去重。

## 最终决定

用户认为微小收益不足以引入排除规则，选择保留所有用例。该决定关闭本轮去重实施门，不要求后续再次确认；不得把本记录中的候选自动应用到Windows选择器。ACL及四分片优化独立交付。
