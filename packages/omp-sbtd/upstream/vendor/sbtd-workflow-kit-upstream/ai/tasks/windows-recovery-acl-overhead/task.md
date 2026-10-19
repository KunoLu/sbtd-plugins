---
schema_version: 1
id: windows-recovery-acl-overhead
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择strict用于Windows安全删除/恢复性能修复
status: "done"
branch: fix/windows-recovery-acl-overhead
created_at: '2026-10-14T15:18:51.142645+08:00'
updated_at: "2026-10-14T16:57:07.508361+08:00"
completed_at: "2026-10-14T16:57:07.508361+08:00"
---
# Windows恢复ACL往返性能修复

## 授权与范围

用户明确授权独立修复/验证/提交/推送/创建PR，并选择strict；不授权合并、patch发布、移动v2.0.0、live清理或备份销毁。分支fix/windows-recovery-acl-overhead基于已发布main8f6c469，不带诊断插桩/workflow，不整批带入PR121未合并的任务记录；仅按追加要求恢复双语CHANGELOG的真实已发布事实。
证据：P3-03私有windows-recovery-root-cause和独立诊断review；Windows隔离恢复1250次ACL往返868.900s，占900秒测试预算96.54%。旧失败/诊断保留。
未完整grill：问题、现行安全合同及用户要求明确，无领域歧义。

用户追加v2.0.1范围：纠正当前分支双语CHANGELOG的v2.0.0已发布状态；只读比较tokens的2026-10-13与9月MD报告，采用旧报告的清晰分节，固定未来Agent执行汇总模板并同步相关文档。不得改写tokens历史证据、不自动同步已安装Skill、不发布v2.0.1。

## 接口、设计与不变量

保持公开remove_reference/install_reference/upgrade recovery接口及文档schema不变。测试沿现有公开文件删除/替换及实际安装副本CLI生命周期，不用内部调用次数作为永久行为断言。
拟采用每次目录删除中的同父目录私有holder复用，减少新建/设ACL；每个文件仍重新验证holder私有性/身份、路径类型及内容，在capture后再核对原名无竞争者。holder仅本次操作拥有、空时复用，发生漂移/未知内容停止并保留；不做跨调用ACL缓存或延长900秒。
保留单文件删除原语、完整原件、并发新增/修改保护、非覆盖恢复、RetainedObjectError及真实部分回执。不同父目录分别持有同卷holder，避免跨挂载rename。中间holder必须在删除其父目录之前完成安全空目录回收，异常不递归清空。

## Book Gate Plan

| Gate | 触发 | 状态 |
|---|---|---|
| DDD | 未完整grill、无新领域规则 | not-needed |
| DDIA | 删除/恢复所有权与失败路径 | confirmed：原件/回执所有权不变，同操作同父目录分组复用；每文件重新证明权限/身份/内容，未知对象保留 |
| Legacy | 既有安全删除行为 | characterized：原生Windows900秒失败、25项安全基线；新增并发修改、holder替换/权限漂移/消失场景 |
| Refactoring | 修改生产删除原语 | proceed normally：仅私有holder生命周期，公开接口/schema不变，不做跨调用缓存 |
| TDD/BDD | 已证Windows900秒red；保留现有行为场景 | 源仓Markdown场景见cleanup设计§8；holder消失AssertionError red/green、公开冲突/漂移回归通过；原900秒Windows安装副本生命周期通过 |
| Project validation | 原生Windows、相关完整范围、三平台CI | 本地111安全/迁移项通过（2 skip）、macOS686通过（20 skip）；精确5b97c820候选CI run38532355204九job成功，Linux2133/macOS686/Windows507，原生skip事件48/20/33；七份分片完整互斥SHA复验通过 |
| Independent security/readability | 安全删除与权限边界 | RecoveryHolderSecurity、RecoveryHolderRegression最终均无发现；ReleasePackageReview报告合同复核无发现；不以审查替代Windows运行 |
| Release readiness | 安装/恢复运行路径 | ready：仅修复PR交付；适用检查已通过，无发布/合并授权，原备份保留及单controller边界不变 |

## 验收场景

- Given完整受管目录和原件已保全；When执行恢复；Then逐文件删除/还原正确，Windows完整安装副本生命周期在原900秒内结束，备份不删。
- Given删除期间其他文件被修改或新增；When继续；Then拒绝并保留用户字节，不以缓存ACL/初始hash接受漂移。
- Given私有holder被替换、权限变宽或出现未知内容；When下一文件执行；Then零新增越权删除并报告可恢复对象，不覆盖未知original。
- Given真实文件capture后原名被竞争者占用；When恢复冲突；Then两个对象都保留且回执真实。

## 验证计划

先运行现有文件原语安全集与新增有意义的漂移边界；实现后定点、完整相关模块、真实CLI smoke与Windows原生命令。原生CI仍保留原900秒、完整包、全部断言，无skip/临时诊断代码。两路独立复核通过后仅提交推送创建PR，合并和v2.0.1等发布另行确认。

报告格式验收：Given旧报告和10月13日原生证据均保留；When读取固定模板生成独立中文预览；Then九个章节依序呈现，统计/用例/失败轮次对应原生记录，保留旧SHA/环境/发布时间且明确未重跑，历史文件哈希不变。API覆盖矩阵只引用已保存的真实记录；缺失字段写原因，不虚构零值或通过。模板为Agent输出约束，不冒充确定性原生reporter。

## 本地检查与文档维护

- 实际文件系统smoke：12个名称交错的受管文件移除成功；快照后修改的用户字节拒绝删除。单文件/目录冲突恢复均验证精准retained文件与非覆盖行为。
- 生产helper与安全测试ruff通过；CI runner仅追加case清单，既有I001/两项UP017在HEAD与当前一致，未夹带重构。compileall通过，冻结安装载荷后执行验证。
- 报告预览读取保留原生JSON：2个case、16项URI、3轮退出码1/0/0；九章节/八表解析及五份旧报告哈希不变。它不是新E2E运行；一次性校验脚本误写表数7的失败保留，纠正为从模板解析后通过。
- 双语CHANGELOG的22版本/327条目/代码标识及URL一致，v2.0.0日期2026-10-14、v2.0.1未发布；Markdown本地链接核验通过。
- README.md与README.zh.md增加固定模板入口；版本化automation prompt增加报告兼容性评估；Web UI/Maestro相关合同同步。未修改live automation、HOME或已安装副本。
- 长期lesson使用本地合法身份kuno，新增固定执行汇总记录于bdd-e2e-reports topic及索引，不重写历史作者块。
- 私有证据根为本任务reports；保留失败及修正记录。PR提交前为dirty本地证据，后续只以精确head原生CI证明远端候选。

## 交付与发布边界

修复PR：[122](https://github.com/KunoLu/640-skills/pull/122)。实现候选`5b97c8200c5095de823c258da6029de335d60fa5`的[三平台CI](https://github.com/KunoLu/640-skills/actions/runs/38532355204)通过；原生Windows安装副本完整升级/重试/恢复用例672.687秒通过，相关子进程原900秒限制未改。这是完整用例时长，不冒充单独recovery阶段计时或通用性能保证。

完成记录仅改任务正文/导航；安装载荷与测试保持已验证候选字节，新head按实际CI另验。报告与下载原件保持私有，不上传证据正文。v2.0.0已发布且tag不动；v2.0.1未发布；PR121仍是独立未合并发布记录，P3-03整体收口与本修复PR交付分开，不在此分支伪写P3-03完成。

Release Readiness Review：ready（修复交付范围）；同卷捕获、逐文件权限/身份/空目录/内容证明及非覆盖恢复；未知对象保留、部分结果真实；无新的schema/常驻进程/权限缓存。无部署，因此源码回退不改变持久备份。真实HOME/live认证/生产负载不在本次验证范围；没有合并、发布patch、workflow sync或备份销毁授权。既有同UID并发TOCTOU与单controller约束保留，不宣称事务性删除。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-14T15:18:58.555854+08:00 | planned | in-progress | 用户授权独立修复验证和PR，并明确选择strict；已定位重复PowerShell ACL往返，禁止合并发布 | P3-03 windows-recovery-root-cause；原生Windows诊断run38522065660 |
| 2026-10-14T16:01:13.255507+08:00 | in-progress | checking | 实现、报告模板与本地验证完成，独立复核无发现；等待精确PR head三平台CI | 本地111安全迁移测试、macOS686、public removal smoke、report-layout-assessment及三路review |
| 2026-10-14T16:57:07.508361+08:00 | checking | done | 修复与固定报告合同已交付PR122；三平台原生CI和独立复核通过，未合并或发布 | run38532355204；精确候选5b97c820；Windows完整用例672.687s；exact-head-ci及readiness私有报告 |
