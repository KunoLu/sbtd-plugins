Feature: 三目标 AGENTS 转换
  KPi 维护者需要从一个固定且可验证的 SBTD Workflow Kit 上游快照生成可发布、可审计且无语义遗漏的三目标 AGENTS 制品。

  Background:
    Given 上游来源为 "https://github.com/KunoLu/640-skills"
    And sourceId 为 "sbtd-workflow-kit-upstream"
    And upstream.lock.json 锁定一个显式 committed revision

  Rule: 相同锁定输入必须产生相同制品

    Scenario: 从完整 Section Mapping 生成三目标 AGENTS
      Given 上游 source tree digest 与 lock 一致
      And 两份上游 AGENTS 的每个 Section 都有 include、omit 或 replace-with-overlay 分类
      When 维护者运行 AGENTS transformation
      Then 生成 Global、Root Project 和 OMP Project Adapter 三个目标
      And OMP Project Adapter 导入 "@../AGENTS.md"
      And Root Project Facts 不被 OMP Project Adapter 重新取得所有权
      And manifest 记录 source、overlay 与 generated digests
      And sync report 不包含 Unmapped Section

    Scenario: 使用相同输入重复生成
      Given 上一次 generation 已经成功
      When 维护者使用相同 lock、source、mapping、overlay 与 transform version 再次生成
      Then 三个目标、manifest、digests 与 sync report 均逐字节一致

  Rule: 未审阅的上游变化必须阻断发布

    Scenario: 上游新增未映射 Section
      Given 锁定的上游 AGENTS 中出现一个 mapping 未声明的新 Section
      When 维护者运行 AGENTS transformation conformance
      Then conformance 失败
      And sync report 将该 Section 标记为 Added 和 Unmapped
      And 生成结果不能作为可发布 SBTD Kit

    Scenario: Mapping 引用不存在的 Section
      Given agents-section-map 包含上游中不存在的 Section key
      When 维护者运行 AGENTS transformation conformance
      Then conformance 失败
      And sync report 将该 mapping 标记为 Removed 或 Unknown

    Scenario: 一个 Section 重复声明 Mapping policy
      Given agents-section-map 对同一 Section 声明多个 explicit policy
      When 维护者运行 AGENTS transformation conformance
      Then conformance 失败
      And 错误指出冲突的 Section 与目标

    Scenario: 上游 source digest 与 lock 不一致
      Given vendored source tree digest 与 upstream.lock.json 不一致
      When 维护者运行 generation 或 conformance
      Then 操作在生成目标前失败
      And 错误报告预期与实际 digest
      And 既有 generated output 不被改写

  Rule: 上游提升是可验证的本地事务

    Scenario: sync-upstream plan 不写入 Kit 或 Plugin
      Given 维护者提供本地 canonical Git source root 与显式 committed revision
      When 维护者运行 "sync-upstream --plan"
      Then 结果状态为 "planned" 且包含确定性的 plan digest
      And Kit vendor、lock、mapping、generated output 与 Plugin snapshot 均不被写入
      And plan 报告 source tree、mapping、overlay、generated digest 与已分类 Section

    Scenario: 过期的 sync-upstream plan 在写入前被拒绝
      Given 维护者已经获得一个 sync-upstream plan digest
      And source、revision、mapping 或 overlay 在 plan 后发生变化
      When 维护者使用旧 digest 运行 "sync-upstream --apply"
      Then 操作以 typed stale-plan 错误失败
      And Kit 与 Plugin 的现有输出不被替换

    Scenario: Mapping 明确声明 omit 与 replace-with-overlay 策略
      Given 每个 source Section 都有明确 policy
      When 维护者运行 AGENTS transformation conformance
      Then omit Section 不出现在任何生成目标中
      And replace-with-overlay Section 只由其 KPi-owned target overlay 提供
      And 缺少 required overlay 会以 typed error 失败

    Scenario: sync-upstream 在 Plugin 候选验证失败前不替换输出
      Given Plugin candidate 的 embedded Kit、LICENSE 或 notices 不能通过验证
      When 维护者运行 sync-upstream plan 或 apply
      Then 操作以 typed Plugin stage 错误失败
      And Kit 与 Plugin 的现有输出不被替换

    Scenario: sync-upstream apply 嵌入与已提升 Kit 一致的 Plugin 快照
      Given 维护者提供与 plan digest 相同的 committed source inputs
      When 维护者运行 "sync-upstream --apply"
      Then 结果状态为 "applied"
      And Kit vendor、lock、mapping 与 generated output 从同一 source revision 更新
      And Plugin kit、LICENSE 与 THIRD_PARTY_NOTICES 与生成 Kit 一致

    Scenario: sync-upstream plan 绑定 stable manifest 派生 provenance
      Given 维护者提供本地 canonical Git source root 与显式 committed revision
      When 维护者运行 "sync-upstream --plan"
      Then 结果报告 stable set、stable manifest digest 与派生的 repository revision 和 license provenance
      And plan digest 绑定 stable manifest provenance
      And Kit vendor、lock、mapping、generated output 与 Plugin snapshot 均不被写入

    Scenario: stable manifest 漂移在生成或提升前被拒绝
      Given vendored stable manifest 的 Skill tree digest、repository revision 或 license 文件与 pinned source 不一致
      When 维护者运行 generation 或 sync-upstream
      Then 操作以 typed stable-manifest 错误失败
      And 既有 generated output 不被改写
      And 派生 provenance 不作为可编辑输入接受

    Scenario: promotion-owned 脏路径在 Apply 前被拒绝
      Given 一个 promotion-owned destination 存在未提交修改
      When 维护者运行 "sync-upstream --apply"
      Then 操作在 staging 前以 typed dirty-destination 错误失败
      And 错误只报告 repository-relative 冲突路径
      And 非 owned 路径的未提交修改不阻断 Apply
      And plan 报告 dirty-preflight 结果但不因此失败

    Scenario: Codex 运行时策略泄漏只检查三个 AGENTS 投影目标
      Given 一个 source Section 被 mapping 分类为 omit 或 replace-with-overlay
      When 被排除 Section 的原文逐字出现在任一生成目标中
      Then generation 以 typed leakage 错误失败
      And 相同原文保留在 embedded onboard/runtime 资产中不触发该检查

    Scenario: 默认 stable/auto 安装不访问 Git 或网络
      Given 维护者使用默认 auto 或 stable 外部 Skill 安装路径
      When Git 与网络不可用
      Then 安装从 vendored stable set 解析且不调用 Git
      And 显式 upstream 选择失败时没有静默 stable 回退

    Scenario: 绑定未来 revision 的 Section 分类不影响当前锁定生成
      Given agents-section-map 包含以 introducedRevision 绑定未来 committed revision 的 Section 分类
      When 维护者对当前锁定 revision 运行 AGENTS transformation
      Then 未生效的分类不参与 Section 映射验证
      And 生成目标与 manifest 和不带该分类时逐字节一致

    Scenario: 绑定当前 revision 的未知 Section 分类仍然失败
      Given agents-section-map 包含以 introducedRevision 绑定当前锁定 revision 的未知 Section 分类
      When 维护者运行 AGENTS transformation conformance
      Then conformance 失败
      And sync report 将该 mapping 标记为 Removed 或 Unknown

    Scenario: 提升以精确 HEAD Git 对象为来源
      Given 本地 canonical 仓库包含 committed revision "4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb"
      And live mapping 与 OMP distribution map 已按该 revision 分类
      When 维护者对该 commit 运行 "sync-upstream --plan"
      Then 结果 resolvedRevision 等于该 commit
      And 结果报告 stable set "2026-08-11.1" 与 manifest digest "5d607007086b671866142ce3d0edd0a896e8c878e5566cf7ca9b1592e7c844ca"
      And 三个投影目标不包含可执行 Codex 调度指令
      And Kit 与 Plugin 输出不被写入

    Scenario: v1.0.6 Git 对象仍保持 stable-first 安装
      Given 本地 canonical 仓库包含 annotated v1.0.6 tag commit "1f019e070d1ca41f064572febe055643d8dbc1ce"
      When 维护者对该 commit 运行 git archive 并检查默认 auto 或 stable 外部 Skill 安装路径
      Then 安装从该历史 stable set "2026-08-03.1" 解析且不调用 Git
      And 显式 upstream 选择失败时没有静默 stable 回退
      And 维护者不得用当前 live writing-for-agents map 对该历史 commit 运行全量 "sync-upstream --plan"

    Scenario: destination 备份失败时保留 Kit 与 Plugin
      Given 完整 Kit 与 Plugin candidate 已经完成 stage validation
      And 一个 destination 的 Apply 前备份被诱发失败
      When 维护者运行 "sync-upstream --apply"
      Then 操作以 typed transaction 错误失败
      And 失败 destination 与其他 Kit 和 Plugin destination 保持 Apply 前的内容

    Scenario: 最后一个 Plugin 替换失败时恢复 Kit 与 Plugin
      Given 完整 Kit 与 Plugin candidate 已经完成 stage validation
      And Plugin THIRD_PARTY_NOTICES 的最终替换被诱发失败
      When 维护者运行 "sync-upstream --apply"
      Then 操作以 typed transaction 错误失败
      And 每个 Kit 与 Plugin destination 恢复到 Apply 前的内容

  Rule: Runtime 只消费经过验证的 Bootstrap Snapshot

    Scenario: 生成与嵌入 manifest 与 embedded stable manifest 交叉验证
      Given generated manifest 含有派生 stable provenance
      When Plugin 加载嵌入 Kit 或 embed validation 运行
      Then embedded stable manifest 字节 digest 与派生 manifest digest 一致
      And stable manifest 字节或 provenance 漂移时加载或验证失败

    Scenario: Plugin 通知保留 stable 许可证的 kit 前缀路径
      Given generated notices 含有派生 stable External Skills 许可证条目
      When Plugin embed 派生 Plugin notices
      Then stable 许可证路径以 "kit/onboard/runtime/" 前缀保留
      And 既有 third-party 保留路径仍以 "kit/third-party/" 前缀保留

    Scenario: Plugin 构建嵌入验证通过的 Kit
      Given 三目标 generation 与 conformance 已通过
      When 维护者构建 "@kunolu/omp-sbtd"
      Then Plugin 包含固定 Kit Revision、Profile Catalog、三目标模板、Onboard assets 与 license material
      And Plugin-to-Kit revision mapping 可校验
      And Plugin Runtime 不需要访问上游仓库或网络

    Scenario: Generated output 已经漂移
      Given 工作树中的 generated target 与 manifest digest 不一致
      When 维护者运行 generated-output check
      Then check 失败
      And 失败结果列出漂移目标
      And check 不自动接受或覆盖该漂移
