Feature: SBTD 控制引导
  OMP 用户需要先了解并安全准备 SBTD 环境，再决定是否启用自动工作流控制。

  Background:
    Given OMP 17.3.5 已加载与当前 SBTD Kit 匹配的 KPi Plugin

  Rule: 帮助和诊断不改变用户状态

    Scenario: 在未完成 Onboard 时查看帮助
      Given 当前 Session 尚无 KPi 状态记录
      And 所选 Onboard Profile 的必需基线不完整
      When 用户执行 "/sbtd help"
      Then 用户看到受支持命令的用途、Usage、示例、写入和确认标记
      And 当前 Session 不产生新的 Agent Turn 或 KPi 状态记录
      And 用户或项目文件保持不变

    Scenario: 首次加载时查看默认状态
      Given 当前 Session 尚无 KPi 状态记录
      And 所选 Onboard Profile 的必需基线不完整
      When 用户执行 "/sbtd status"
      Then 状态显示 Runtime Mode 为 "advisory"
      And 状态显示 Policy Profile 为 "strict"
      And 状态显示 Onboard Profile 为 "omp-p0-standard-v1"
      And 状态显示 Environment Mode 为 "needs-onboard"
      And 状态显示 Effective Control State 为 "advisory"

    Scenario: 查看已加载的 AGENTS 事实链
      Given Global、Root Project 和 OMP Project Adapter 都包含当前 Kit 的完整 Managed Block
      And OMP Project Adapter 导入 "@../AGENTS.md"
      When 用户执行 "/sbtd status"
      Then 状态显示 Root Project Facts Import 为 "valid"
      And 状态分别显示 Global、Root Project 和 OMP Project Adapter 的 exists、discovered、loaded 与 effective 事实
      And 当前 Session 不产生新的 KPi 状态记录

    Scenario: Doctor 观察事实但不写入 Session
      Given 当前 Session 尚无 KPi 状态记录
      When 用户执行 "/sbtd doctor"
      Then Doctor 显示当前 Environment Mode、AGENTS 事实与恢复信息
      And 当前 Session 不产生新的 KPi 状态记录


  Rule: 公共报告如实表示 Route 状态

    Scenario: 新 Session 查看未分类的 SBTD 报告
      Given 当前 Session 尚无 KPi 状态记录
      And 所选 Onboard Profile 的必需基线不完整
      When 用户执行 "/sbtd report"
      Then 用户看到 Runtime Mode 为 "advisory"
      And 用户看到 Route 为 "auto"
      And 报告包含与所示状态一致的脱敏结构化数据
      And 报告不把未分类 Session 表示为具名工作流 Route

    Scenario: 自动分类不改写用户选择的 Route
      Given 当前 Session 的 Route 选择为 "auto"
      And 当前 Agent Turn 已分类为 "bugfix"
      When 用户执行 "/sbtd report"
      Then 用户仍看到 Route 为 "auto"
      And 报告显示自动分类的 Route 为 "bugfix"
      And 自动分类 Route 只有在当前分类存在时才出现

    Scenario: OMP 宿主认证未分类的公开报告
      Given OMP 17.3.5 已从隔离环境加载当前候选的精确 tarball
      And 当前 Session 尚未分类为具名工作流 Route
      When 授权宿主依次执行 "/sbtd help"、"/sbtd status"、"/sbtd report" 与 "/sbtd onboard plan"
      Then 宿主从 "/sbtd report" 获得与公开报告一致的脱敏结构化状态
      And 宿主将 Route "auto" 记录为未分类而非伪造 route cost
      And 宿主只保留 Onboard Plan 的 digest 与目标数量，不保留含本地路径的原始通知
      And 宿主只确认与当前 Plan 绑定的 Managed Blocks，拒绝额外的依赖、MCP 或 Trellis 写入确认
      And 四条命令都不调用 Agent 模型且不修改隔离工作区

  Rule: 启用控制必须先完成只读 Preflight

    Scenario: 缺少必需基线时请求启用 SBTD
      Given 当前 Runtime Mode 为 "advisory"
      And 所选 Onboard Profile 的必需基线不完整
      When 用户执行 "/sbtd on"
      Then Runtime Mode 原子更新为 "enforced"
      And Environment Mode 为 "needs-onboard"
      And Effective Control State 为 "preflight-only"
      And KPi 不安装工具或修改用户与项目文件
      And 用户看到完成 Onboard 的恢复路径

    Scenario: Preflight 评估失败时保持原状态
      Given 当前 Session 已有一条有效 KPi 状态记录
      And Environment evaluator 无法得出确定结果
      When 用户执行 "/sbtd on"
      Then 原有 KPi 状态记录仍是当前有效状态
      And Session 不追加候选状态记录
      And 用户看到阻断原因与 repair path

  Rule: Onboard 始终 Plan-first 并保护用户内容

    Scenario: 预览三层 AGENTS Onboard 计划
      Given Global、Root Project 和 OMP Project Adapter 目标尚未由 KPi 管理
      When 用户执行 "/sbtd onboard plan"
      Then 用户看到锁定的 canonical source、完整 revision、canonical manifest digest、OMP projection digest 和三个目标路径
      And 每个目标显示当前状态、来源、digest、计划动作、备份与恢复方式
      And 所有目标文件与 Session 状态保持逐字节不变

    Scenario: 用户取消 Onboard Apply
      Given 用户已查看一个当前有效的 Onboard Plan
      When 用户拒绝执行该 Plan
      Then 三个 AGENTS 目标保持逐字节不变
      And Session 状态保持不变
      And KPi 不创建 accepted skip

    Scenario: 用户确认安装三层 Managed Block
      Given 用户已查看一个当前有效的 Onboard Plan
      And 三个目标文件包含各自的用户自有内容
      When 用户确认执行该 Plan
      Then Global、Root Project 和 OMP Project Adapter 各包含一个来源可验证的 KPi Managed Block
      And OMP Project Adapter 导入 "@../AGENTS.md"
      And 每个 Managed Block 外的用户自有内容保持逐字节不变
      And 用户看到需要 Reload 或新建 Session 的明确结果

    Scenario: 重复执行相同 Onboard Plan
      Given 三个目标已经包含与当前 Kit 完全一致的 Managed Block
      When 用户再次执行并确认相同 Onboard Plan
      Then 三个目标文件保持逐字节不变
      And 结果显示所有 Managed Asset 均为 "exact"

    Scenario: Managed Block 标记损坏时拒绝覆盖
      Given 任一目标包含损坏、重复或所有权不明的 Managed Block 标记
      When 用户执行 "/sbtd onboard plan"
      Then 对应 Managed Asset 状态为 "blocked" 或 "merge-required"
      And Plan 不提供静默覆盖动作
      And 用户看到安全修复路径

    Scenario: 目标在 Plan 后发生变化
      Given 用户已确认一个尚未执行的 Onboard Plan
      And 任一目标或 Provenance Inventory 在 Plan 后发生变化
      When KPi 准备执行该 Plan
      Then Apply 将该 Plan 判定为 stale
      And 三个 AGENTS 目标与 Provenance Inventory 均不产生新写入
      And 用户看到重新生成 Plan 的恢复路径

    Scenario: 另一个 Onboard Apply 正在写相同目标
      Given 另一个有效 Onboard operation 已持有相同 target set 的排他锁
      When 用户确认执行新的 Onboard Plan
      Then 新 Apply 在写入前返回 "blocked"
      And KPi 不静默破坏现有锁
      And 用户看到当前 operation 与安全恢复信息

    Scenario: 上一次 Apply 在提交中中断
      Given Provenance transaction journal 记录一个未完成 operation
      When 用户执行 "/sbtd doctor"
      Then Doctor 显示已完成阶段、未完成阶段、backup 与 residuals
      And KPi 不自动采用未记录的 Managed Block 所有权
      And 用户看到 rollback 或 reconcile 的明确 repair path

  Rule: Reload 后控制状态由当前事实派生

    Scenario: 完成 Onboard 后启用 SBTD
      Given 当前 Session 已在完整 Reload 后重新加载三层 AGENTS 与必需 Skills
      And 所选 Onboard Profile 的当前 Route 必需能力完整
      When 用户执行 "/sbtd on"
      Then Runtime Mode 为 "enforced"
      And Environment Mode 为 "managed"
      And Effective Control State 为 "active"

    Scenario: 关闭自动控制但保留基础约束
      Given Effective Control State 为 "active"
      When 用户执行 "/sbtd off"
      Then Runtime Mode 为 "advisory"
      And Effective Control State 为 "advisory"
      And Policy Profile 与 Onboard Profile 保持不变
      And Root Project Facts、Always-on Baseline 与已加载资产保持有效

    Scenario: Resume 时环境已经漂移
      Given Session 历史保存 Runtime Mode、Policy Profile 与 Onboard Profile
      And Resume 前某个必需 Managed Asset 已经漂移
      When OMP Resume 当前 Session
      Then KPi 恢复保存的 Session 选择
      And KPi 重新观测 Environment Mode
      And 当已启用的当前 Route 的必需能力不完整时 Environment Mode 为 "blocked"
      And Effective Control State 由新的观测结果重新派生
      And KPi 不信任旧观测而继续报告 "active"

  Rule: Kit 与 Tool Evidence 必须来自当前可验证事实

    Scenario: 状态显示 canonical Kit 来源与 projection 摘要
      Given Plugin 内嵌的 OMP Distribution Projection Manifest 与全部发布资产 digest 一致
      When 用户执行 "/sbtd status"
      Then 状态显示 canonical source、完整 Revision、canonical manifest digest、projection digest 与当前性
      And 当前 Session 不产生新的 KPi 状态记录

    Scenario: 状态显示五类工具证据
      Given 当前 Profile 与 Route 已选择
      When 用户执行 "/sbtd status"
      Then 每项相关能力分别显示 installation、configuration、callability、project readiness 与 freshness
      And 非可执行 Skill 的 callability 明确显示为 "not-needed"
      And 可执行能力绝不以 "not-needed" 代替 callability 观测
      And 当前 Session 不产生新的 KPi 状态记录

    Scenario: 同一主要 Turn 复用仍然新鲜的工具证据
      Given 当前 Tool Evidence 的 probe fingerprint、Kit Revision 与有效期仍匹配
      When 同一主要 Turn 再次需要环境观测
      Then KPi 复用当前 Tool Evidence 而不重复执行安全探针
      And Environment Mode 仍由当前 Profile 与 Route 要求派生

    Scenario: 当前 Route 依赖的能力不可调用
      Given 当前 Profile 将该能力标记为 Optional
      And 当前 Route 将同一能力标记为 Required
      And Tool Evidence 显示该能力不可调用
      When KPi 重新观测环境
      Then Environment Mode 为 "blocked"
      And accepted skip 不能覆盖该 Route-required 缺口
      And Doctor 显示精确阻断原因与 repair path

  Rule: Onboard 事务覆盖所有声明目标并保持项目隔离

    Scenario: 预览完整 Environment Onboard 计划
      Given 当前 Profile 需要 AGENTS、Skills、Tool 配置与环境记录目标
      When 用户执行 "/sbtd onboard plan"
      Then Plan 列出每个声明目标、资源锁、当前 digest、计划动作、确认类别与恢复路径
      And Plan digest 绑定当前读集、Kit Revision、Profile 与 Route
      And 所有候选输出只在事务拥有的 staging 目录生成
      And 最终目标保持逐字节不变

    Scenario: 用户确认当前完整 Onboard Plan
      Given 用户已查看一个未过期且读集未变化的完整 Onboard Plan
      When 用户执行 "/sbtd onboard init <plan-digest>" 并确认匹配的写入类别
      Then KPi 只提升 Plan 声明且已验证的候选输出
      And Provenance Inventory、Tool Evidence 与事务 journal 以同一 operation 记录结果
      And 任一阶段失败时已提升目标按逆序恢复
      And 未声明输出、网络缓存或包管理器缓存不作为成功证据

    Scenario: 多项目初始化隔离每个项目结果
      Given 用户提供多个互不重叠的绝对项目根目录
      And 每个项目都有独立的当前 Plan digest
      When 用户执行 "/sbtd onboard init-projects <absolute-root>... <plan-digest>"
      Then 每个项目独立提交或恢复自己的目标、Inventory、Tool Evidence 与 journal
      And 一个项目失败不回滚另一个已经成功的项目
      And 汇总逐项目显示 "failed"、"blocked"、"needs-user"、"bootstrap-required"、"success" 或 "skipped"

    Scenario: Project-only Onboard 不写全局目标
      Given 用户选择 project-only Onboard
      When 用户预览并确认当前 Plan
      Then Plan 与结果都不包含 Global AGENTS、全局 Skills 或全局 Tool 配置
      And Root Project Facts 与 OMP Project Adapter 仍按当前 Kit 管理

  Rule: AcceptedSkip 必须 Plan-first、精确匹配且可撤销

    Scenario: 为 Optional 缺口创建 AcceptedSkip
      Given 当前能力是 Profile Optional 且当前 Route 不依赖该能力
      When 用户执行 "/sbtd onboard skip plan create <capability> --scope <scope> --expires <ISO-8601> --reason <text>"
      Then KPi 返回只读 Plan digest 且不创建 AcceptedSkip
      When 用户执行 "/sbtd onboard skip apply <plan-digest>"
      Then KPi 创建一个带 actor、时间、expiry、Profile、Kit major、scope 与 provenance 的 "AcceptedSkipV1"
      And Environment Mode 可以为 "degraded"

    Scenario: 已提交且 Route 未变的 AcceptedSkip Plan 可在同一 Session 重放
      Given 用户已确认一个 AcceptedSkip Plan 且当前 scope、Profile、Route 及其派生的 required、optional 与 route-required capability 和 Kit 事实未改变
      When 用户在该 Plan 的有效期结束后再次执行 "/sbtd onboard skip apply <plan-digest>" 并确认
      Then KPi 返回原始 AcceptedSkip 的结果
      And "/sbtd onboard skip list" 不增加新的记录
      And AcceptedSkip 持久化存储保持不变
      And KPi 重新观测 Environment Mode
      And 重放写入带有该次重观测时间的 SBTD Session 记录

    Scenario: 有相同派生 capability 的 Route 改变时 AcceptedSkip Plan 不能重放
      Given 用户已显示一个尚未重新确认的 AcceptedSkip Plan
      And 当前 Route 与 Plan 的 Route 不同但派生相同的 required、optional 与 route-required capability
      When 用户执行 "/sbtd onboard skip apply <plan-digest>"
      Then KPi 在请求确认前拒绝该 Plan 为 stale 并要求创建新 Plan
      And KPi 不创建或重放 AcceptedSkip
      And AcceptedSkip 持久化存储保持不变
      And KPi 不写入 SBTD Session 记录

    Scenario: 事实改变的 AcceptedSkip Plan 不能重放
      Given 用户已显示一个尚未重新确认的 AcceptedSkip Plan
      When 当前 scope 或 Profile、Route 或其派生的 required、optional 或 route-required capability 与该 Plan 不匹配
      And 用户执行 "/sbtd onboard skip apply <plan-digest>"
      Then KPi 在请求确认前拒绝该 Plan 为 stale 并要求创建新 Plan
      And KPi 不创建或重放 AcceptedSkip
      And AcceptedSkip 持久化存储保持不变
      And KPi 不写入 SBTD Session 记录

    Scenario: Preflight 中确认剩余 Optional AcceptedSkip
      Given enforced Session 因一个或多个 Profile Optional 缺口处于 "preflight-only"
      And 当前 Route 不依赖这些 Optional capability
      When 用户为每个剩余 Optional capability 创建并确认 "/sbtd onboard skip apply <plan-digest>"
      Then Apply 在 "preflight-only" 中保持可用
      And Environment Mode 在全部剩余 Optional 缺口已被覆盖后重新观测为 "degraded"

    Scenario: AcceptedSkip 不能掩盖不匹配或必需缺口
      Given AcceptedSkip 的 capability、scope、Profile、Kit major、provenance 或有效期与当前事实不匹配
      When KPi 重新观测环境
      Then 该 AcceptedSkip 不参与 Environment Mode 判定
      And Profile-required 缺口为 "needs-onboard"
      And Route-required 缺口为 "blocked"

    Scenario: 撤销或到期 AcceptedSkip
      Given 当前存在一个有效 AcceptedSkip
      When 用户为该记录生成并应用 revoke 或 expire Plan
      Then 该记录保留历史与 provenance 但立即不再有效
      And KPi 重新观测 Environment Mode
      And "/sbtd onboard skip list" 显示 active、revoked 或 expired 状态


  Rule: 完整 Onboard 安装保持来源、审批与恢复边界

    Scenario: 正常 Onboard 从内嵌 Stable 集合覆盖选中的 Skills
      Given 当前 Profile 选择 C1 Skills catalog
      And 已选择的 Bundled 与 External Skill 目标包含有效旧版本
      When 用户确认执行正常 "/sbtd onboard init <plan-digest>"
      Then Plan 中选择的全部 Skill 从内嵌 Stable 来源完成替换
      And 安装过程不访问 GitHub 或其他网络来源
      And Skills 安装目标目录与环境观测验证的目录一致
      And 无关 Skill 目录保持逐字节不变
      And 任一 Skill 提交失败时所有已选择目标恢复到执行前版本

    Scenario: 可选上游 Skills 需要独立网络确认
      Given 用户选择安装 "impeccable" 与 "shadcn"
      When 用户查看完整 Onboard Plan
      Then Plan 显示 allowlisted repository、固定 commit、source subpath 与预期 tree digest
      And Plan 单独要求 "network-skill-install" 确认
      When 用户确认网络安装
      Then 两个 Skill 只有在来源与 tree digest 验证通过后才原子替换
      And 获取失败时 C1 安装结果保持成功且可选安装报告为 "degraded"

    Scenario: CLI 安装失败不能伪装为可调用
      Given 当前 Plan 包含用户已确认的 required CLI 安装
      When allowlisted 安装命令超时、非零退出或 post-install 探针失败
      Then 对应 CLI 状态为 "blocked"
      And KPi 不报告该 CLI 为 "callable"
      And 结果包含脱敏失败原因与可执行恢复路径

    Scenario: 只合并用户选择的 MCP 配置
      Given 用户级 MCP 配置包含未知且无关的 server entries
      And 用户只选择一个受支持的 MCP server
      When 用户确认 "mcp-config" 写入类别
      Then KPi 只新增或更新选中的 user-level server entry
      And 未知与无关 entries 保持不变
      And 新配置在 Reload 前只报告为 "configured" 而非 "callable"

    Scenario: 为未初始化项目执行 Trellis init
      Given 用户确认 developer username 与一个尚无 ".trellis" 的绝对项目根目录
      When 用户确认当前项目的 Trellis 初始化
      Then KPi 执行带有该 username、"--omp"、"--yes" 与 "--skip-existing" 的 Trellis init
      And KPi 验证项目已生成有效 workflow
      And Project-only Onboard 不安装全局 Trellis CLI

  Rule: Trellis bootstrap 只有真实任务完成后才就绪

    Scenario: 初始化后调度需要 Provider 的 bootstrap
      Given Trellis init 生成 "00-bootstrap-guidelines" 任务
      Then 项目状态为 "bootstrap-required"
      When 用户单独确认 Provider 与模型使用
      Then Plugin 通过 OMP Session 调度固定 bootstrap Agent turn
      And 项目状态依次可观察为 "scheduled" 与 "running"

    Scenario: bootstrap 中断后保持可恢复
      Given bootstrap Agent turn 已调度但中断或失败
      When 用户查看 Status 或 Doctor
      Then 项目状态保持 "bootstrap-required" 或 "blocked"
      And 用户看到继续同一 Trellis task 的恢复路径
      And KPi 不报告真实 bootstrap 已完成

    Scenario: 真实 Trellis task 完成后项目才就绪
      Given bootstrap Agent turn 已完成
      When Plugin 重新检查 Trellis task 与必需 workflow/spec 文件
      Then 只有 task 已完成或归档且必需文件存在时项目状态才为 "ready"
      And 安装器写入或 contract-backed 测试结果不能单独证明真实 bootstrap 已完成

  Rule: Host Contract 决定 /sbtd 注册的完整性与降级边界

    Scenario: Host Contract 通过时注册完整 /sbtd
      Given OMP Host 提供 "omp-extension-v1" 清单中的全部必需 capability 与必需事件
      When Plugin 完成宿主注册
      Then "/sbtd" 命令、全部必需事件订阅与声明的 Tool 都完成注册
      And Plugin 进入可用的 ready 状态

    Scenario: 必需 capability 缺失时 fail closed
      Given OMP Host 缺少 "omp-extension-v1" 清单中的一个必需 capability 或必需事件
      When Plugin 尝试宿主注册
      Then 注册 fail closed 并给出结构化原因代码
      And Plugin 不进入 ready 状态
      And 部分注册成功不得留下误导性的可用状态

    Scenario: 可选 capability 缺失时只降级相关功能
      Given OMP Host 只缺少 "omp-extension-v1" 清单中的可选 capability 或可选事件
      When Plugin 完成宿主注册
      Then 只有依赖该可选能力的功能被降级
      And 其余命令与事件订阅保持可用
      And 该结果被记录为带完整原因代码的 "passed-with-diagnostics"

  Rule: 宿主事件不被伪造解释且跨边界不复用

    Scenario: malformed event 不得被解释成批准或完成
      Given Plugin 收到未知类型或载荷畸形的宿主事件
      When Plugin 处理该事件
      Then 该事件被拒绝且 fail closed
      And 不得被解释为 tool approval、tool result 完成或任何状态推进

    Scenario: tool approval 与 tool result 不跨 Session、turn、risk class 或 target 复用
      Given 一个 tool approval 或 tool result 已绑定到精确的 Session、turn、risk class 与 target
      When 另一个 Session、turn、risk class 或 target 出现相同标识的请求
      Then Plugin 拒绝复用既有的 approval 或 result
      And 每个审批与结果只被一次性精确消费

    Scenario: compaction 与 Session 切换保持状态隔离
      Given 当前 Session 经历 compaction 或切换到另一个 Session
      When Plugin 处理后续事件
      Then compaction 只保留允许的 Session 状态摘要
      And 一个 Session 的瞬态状态、approval 与 result 不泄漏到另一个 Session
