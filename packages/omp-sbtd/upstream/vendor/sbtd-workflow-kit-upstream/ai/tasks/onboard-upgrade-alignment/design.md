# Onboard 通用升级对齐设计

## 已确认范围

完整交付固定基线/差异、多配置域、升级/恢复/自升级、运行时与PATH检查、旧Skill清理能力、两安装器和分层验收。仅仓库实现与隔离验证；不应用用户HOME、不sync、不清理真实旧资产、不合并或发布本分支。

## 术语与决定

基线由安装包catalog、模板、stable manifest和运行时约束生成；内容摘要绑定实际载荷而不是模糊latest。配置域是显式选择的宿主配置路径及Skills根；发现不等于选择。资源是一次备份/写入/恢复的最小文件或目录。对齐是受管内容/语义匹配；宿主加载和清理分别报告。只读plan/verify不启动宿主、不创建缓存或目录。

## 公共接口与模块责任

新增 scripts/sbtd_upgrade.py：plan_upgrade(scope, backup_root, *, package_root=None)、apply_upgrade(plan, *, confirmed, receipt=None)、verify_upgrade(plan, *, receipt=None, probe=False)、plan_recovery(plan, receipt)、apply_recovery(recovery_plan, *, confirmed, receipt=None)。均返回JSON-safe dict；安全拒绝用现有ContractError。run_upgrade(args)->int拥有CLI envelope和退出码。

scripts/sbtd_upgrade_inventory.py：build_inventory(scope, *, package_root=None)->dict，返回 baseline、resources、domains。baseline包含schema_version=1、baseline_id、catalog摘要、载荷/来源/运行时pin；baseline_id不依赖安装绝对路径/mtime。resources包含id（稳定目标身份）、kind（skill/agents）、target绝对路径、source绝对路径、before/desired（现有snapshot形状）、classification（missing/current/known-old/unknown-drift/identity-conflict）、decision（install/keep/replace/preserve/blocked）、details（仅相对文件名和摘要，不含内容）。普通合法但不同内容默认unknown-drift，只有可验证历史证据才可known-old；不凭版本字符串判断。scope.decisions以绝对目标路径为键，值replace/preserve；不可将identity/path冲突批准为replace。所有源来自catalog，完整校验stable来源/许可证/摘要；完整文件树比较，既有排除仅用于已声明生成缓存；未知额外文件必须显式列出。所有选定根处理一次，拒绝重叠/跨根逃逸/symlink或Windows junction。不得读取未选HOME。

scripts/sbtd_upgrade_hosts.py：build_host_resources(scope, *, package_root=None)->list[dict]，返回同一资源形状，kind=mcp/shell，增加host/profile描述与desired摘要，不把全配置内容写入plan；render_resource(resource, *, package_root=None)->bytes在前态校验后通过现有结构化candidate重新生成；verify_hosts(scope, *, package_root=None, probe=False)->dict按disk/runtime/host/legacy维度返回每域状态。MCP只使用既有Codex/OMP candidate，不给Claude/Kimi发明Graft接线。全配置/认证值不进入输出。显式probe才运行原生协议和真实host命令；无真实加载证据绝不标pass。PATH只改明确选择的bash/zsh/powershell profile，有唯一配对marker及shell quoting、幂等；MCP固定绝对runtime独立于PATH。纯检查不启动用户shell。scope中的host config必须在host提供的config_home内。

## Scope v1

JSON对象：schema_version=1；skills_roots=[绝对目录]；agents_targets=[绝对文件]；hosts=[{id,platform,config_home,config,skills_roots:[绝对目录],runtime:{python,node,cli},project_roots:[绝对仓根]}]；shell_profiles=[{path,shell,bin}]；decisions={绝对目标:replace|preserve}。数组可省略为空，但至少一个选定资源；未知键/重复host id/错误类型拒绝。host的skills_roots必须也存在顶层skills_roots中。Orca通过显式config_home纳入，不枚举账号认证；OMP使用现有resolver时必须绑定解析输入，显式路径不猜profile。未选目标零写入。agents_targets只表示全局受管AGENTS；混合未知内容必须replace/preserve，不无声整文件覆盖。

host可选executable指定绝对宿主CLI路径，onboard_root指定已安装Onboard包目录。单一host.skills_root派生包目录；多个根必须显式选其中一个；无Skills根的host-only必须显式已有受信包。最终MCP launcher绑定安装目标，执行器stage只用于执行代码，不进入持久配置。OMP所有选定project_roots的有效继承来源须封存并核对。shell bin是只读执行输入，允许bin/graft为正常npm命令链接，但不复制/扫描整个bin；profile与写入根仍拒绝链接。

## CLI（两根安装器原样转发）

- upgrade --phase plan --scope <scope.json> --backup-root <existing-private-dir> [--output <new-plan.json>] --json
- upgrade --phase apply --plan <plan.json> --confirm-plan <plan_id> --yes [--receipt <previous.json>] --json
- upgrade --phase verify --plan <plan.json> [--receipt <receipt.json>] [--probe --yes] --json
- recovery --upgrade-plan <plan.json> --upgrade-receipt <receipt.json> --phase plan [--output <new-recovery.json>] --json
- recovery --upgrade-recovery-plan <recovery.json> --phase apply --confirm-recovery <recovery_id> [--recovery-receipt <previous.json>] --json

既有recovery grammar不变；upgrade参数与旧migration参数互斥。计划默认stdout只读；--output仅写已选私有vault的新文件。所有输出一个JSON对象；exit 0表示该阶段通过，不代表host loaded；2表示拒绝/冲突/未确认；3表示执行或恢复失败；verify存在必需漂移应非零。参数不合法用argparse拒绝。

## 安全与恢复

复用sbtd_migration_files的snapshot、require_private_directory、backup_reference、install_reference、write_file、save_document、remove_reference；不宣称跨域原子事务。plan密封baseline、scope、backup_root、resources和输入前态；ID绑定不授权。apply重新从scope/当前源推导目标，拒绝任意改路径后重算hash的伪造plan。backup_root必须与源、所有目标互不嵌套；先预检整个集合再写，保留全量原件。每个资源写前检查前态，写后测量，持久保存不可变累计回执；失败保留原件、真实after和已完成项。重试仅跳过live匹配prior after的成功项；状态不明/用户漂移拒绝。恢复plan只针对本批实际写过的资源，重新封存当前after；恢复必须独立确认，未知改动不覆盖，原来不存在的资源只移除已测量本批内容，备份永不自动销毁。中断在写后receipt前必须有可识别intent/原件，不能伪称未写。

自升级：应用入口在私有vault中完整校验/暂存Onboard包，由独立子进程执行apply，不能在被覆盖目录中继续动态导入新旧混合模块。若运行包不是写入目标也使用同一安全路径避免双实现。源stage不可由用户scope指向任意代码；只从已校验当前包创建。

### 用户确认的历史信任模型

2026-10-04 用户在“独立密钥认证”与“将私有 vault 作为受信历史”之间明确选择后者。操作人明确选择、独占管理的已有私有 vault 是历史事实来源；不承诺抵御具备其写权限者整组一致地伪造计划、回执、意图和checkpoint。hash证明一致性，不认证历史身份。保留当前受信包推导、选择范围/资源/预期载荷校验、完整恢复资格与阻断状态绑定、当前漂移拒绝，不能把单个文档ID当授权。若vault来源/控制权存疑，停止自动恢复并人工核对。没有外部密钥、daemon或新增HOME状态。

当前受信执行包发生独立内容变化时旧计划返回source-stale，不能自动执行vault里的历史代码。需使用可信原包核对证据或重新规划；已失败的旧批次证据保留。成功重试可跳过仅生成缓存变化的同载荷目录，但新缓存不归本批所有，恢复仍检查完整机械后态。恢复保留新建空父目录，不推断可删除的父目录所有权。

DDIA Data Design Review（复核）：confirmed。数据owner为操作人；当前代码/catalog是目标载荷权威，选定私有vault为获确认的历史权威。逐资源读写/备份/意图/回执、失败可见性与恢复门不变。新增测试覆盖资格状态篡改、越界资源、部分证据不一致与当前用户漂移；整组受信历史伪造明确不在防御范围。

## Book Gate Plan

| Gate | 客观触发 | 时点 | 生命周期 |
|---|---|---|---|
| DDD | 术语已由确认方案定义，未full grill，无未决领域歧义 | 需求 | not-required |
| DDIA | 计划/回执持久化、全局写入与恢复 | 开发前 | passed：confirmed；逐资源前态/备份/实测回执，不承诺跨域事务 |
| Legacy | 安装/清理/CLI既有行为高回归风险 | 开发前 | passed：characterized；声明依赖解释器77项通过，保留初次缺tomlkit失败 |
| Refactoring | 修改既有生产CLI/清理代码 | Legacy后 | passed：proceed / normal；复用现有安全原语，无先行重构 |
| Release | 安装、迁移、运行时行为 | 验证与独立复核后 | passed：ready；befa24e原生三平台CI通过，详见check.md；不代表live部署或发布 |

## 持久行为场景（本仓库禁止.feature）

| ID | Given / When / Then | 验证接口 |
|---|---|---|
| U01 | Given空选定Skills根；When只读plan；Then返回catalog完整资产及固定摘要，不创建目标/缓存/备份 | CLI plan |
| U02 | Given合法旧壳/定制脚本；Whenplan；Then列出完整差异并待决策，不将合法壳误报current | inventory + CLI |
| U03 | Given未知差异明确replace；When获批apply后verify；Then受管内容与同基线全新安装相同，原件可恢复 | CLI生命周期 |
| U04 | Given未知差异preserve；Whenverify；Then报告保留例外且不声称完全对齐 | CLI verify |
| U05 | Given多个域共享根；Whenapply；Then一次写入，全部已选域分别报告，未选域不变 | 多域CLI |
| U06 | Given计划后源/用户内容/路径改变；Whenapply；Then拒绝且无新覆盖 | CLI apply |
| U07 | Given已完成本批；When重试/重新plan；Then相同内容不改写，无重复备份/条目 | CLI幂等 |
| U08 | Given部分写入失败；When重试/独立确认恢复；Then实测状态可追踪，用户新增不丢，备份保留 | 故障与恢复 |
| U09 | Given被升级Onboard正在运行；Whenapply；Then独立已验证副本执行，不混用新旧模块 | 安装副本subprocess |
| U10 | GivenCodex/OMP现存其他MCP与注释；When对齐；Then仅受管连接改变，未知所有权拒绝 | 既有candidate+CLI |
| U11 | Given配置一致但未重载；When只读verify；Thendisk可通过而host为未验证；显式probe才能报告实际观察结果 | verify/probe |
| U12 | Given9个GitNexus Skills及身份冲突；When清理plan/apply；Then精确闭集、独立确认、备份；冲突保留 | cleanup-legacy |
| U13 | Given所选shell profile及旧PATH；When显式计划并应用；Then仅受管marker幂等修改，shell与MCP分开验收 | profile candidate/CLI |
| U14 | Given中文/空格路径、symlink/junction、目标重叠；Whenplan/apply；Then安全路径成功、不安全路径拒绝 | 跨平台CLI |
| U15 | Given配置域含秘密；Whenplan/verify/错误；Then输出只有受管元数据/摘要，不打印秘密或整个配置 | 隐私回归 |

## 验证与报告

现有unittest为主，新增测试按场景追踪。公开CLI red先证明无upgrade命令；既有external/arguments/cleanup测试建立安全网。主控制器独占运行测试；子agent只编写，不在中途运行测试/lint/formatter。隔离真实文件系统和真实CLI smoke；实际Codex/OMP仅使用隔离HOME，不动用户live HOME。Linux/原生Windows检查若当前无可用执行环境，必须blocked而非macOS假冒。每轮保留raw+同stem中文摘要。LSP当前未配置，使用源码/contract引用取证，不宣称LSP通过。
