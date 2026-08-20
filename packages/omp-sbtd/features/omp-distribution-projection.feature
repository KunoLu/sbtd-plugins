Feature: 严格 OMP Plugin 发布视图
  OMP 用户和发布负责人需要安装只包含 OMP Runtime 所需内容、同时保留完整来源证明的 Plugin。

  Background:
    Given 发布负责人已经从固定完整 SHA 的 Canonical SBTD Kit 生成 OMP Distribution Projection

  Rule: OMP npm distribution 不携带非 OMP Runtime 内容

    Scenario: 发布候选的路径和内容满足严格零 Codex
      Given 发布负责人已经构建新的 "@kunolu/omp-sbtd" tarball
      When 发布校验器以大小写不敏感方式检查 tarball 内每个路径和文件内容
      Then 检查结果中 "codex" 匹配数为 0
      And 通过检查的 tarball 才能成为发布候选

    Scenario: 非 OMP 内容使发布候选失败关闭
      Given 一个 Plugin tarball 的任一路径或文件内容包含非 OMP Runtime 标识 "codex"
      When 发布校验器检查实际 tarball
      Then 包检查结果为 "failed"
      And 报告定位违规路径但不输出敏感文件内容
      And 该 tarball 不能成为 RC 或 stable 候选

  Rule: 每个 canonical asset 都需要显式 projection 决策

    Scenario: 未分类的新 canonical asset 阻断 projection
      Given Canonical SBTD Kit 新增一个没有 projection 决策的 asset
      When 发布负责人生成 OMP Distribution Projection
      Then 生成以结构化未分类错误失败
      And 现有 Plugin embedded assets 保持逐字节不变

    Scenario: 相同输入产生相同 projection
      Given canonical revision、canonical manifest、projection policy 和 OMP overlays 均未改变
      When 发布负责人重复生成 OMP Distribution Projection
      Then 两次 projection manifest 和全部 asset 字节完全相同
      And 两次 projection digest 相同

  Rule: 发布候选验证 v2 projection manifest 绑定

    Scenario: manifest v2 绑定漂移使实际发布候选失败关闭
      Given 一个已从实际 "@kunolu/omp-sbtd" tarball 解压的发布候选
      And 候选的 embedded projection manifest 为 schema v1 或其 asset、provenance、target 或 Profile Catalog 绑定已漂移
      When 发布校验器验证候选的 embedded Kit
      Then 包检查结果为 "failed"
      And 候选不能成为 RC 或 stable 候选

  Rule: projection provenance 同时证明 canonical 来源和实际发布内容

    Scenario: Plugin 状态显示双层来源证明
      Given Plugin 内嵌的 projection manifest 与全部发布 asset digest 一致
      When 用户执行 "/sbtd status"
      Then 状态显示 canonical source、完整 revision、canonical manifest digest 和 projection digest
      And 状态只把实际内嵌的 OMP-compatible 能力报告为 available
      And 当前 Session 不产生新的 KPi 状态记录

    Scenario: 被排除的 Optional Skill 不被报告为 bundled
      Given 一个 Optional Skill 因不满足严格 OMP distribution 约束而被排除
      When 用户执行 "/sbtd status" 或 "/sbtd doctor"
      Then 该能力明确显示为 unavailable 或 optional missing
      And Environment Mode 仍按当前 Profile 与 Route 的 Required 能力派生

  Rule: OMP Onboard 只观察和管理 OMP 目标

    Scenario: 已打包 Plugin 的 Onboard Plan 不读取非 OMP 配置
      Given OMP 用户在隔离 HOME 中安装已通过检查的 Plugin tarball
      And HOME 中存在与 OMP 无关的其他 Runtime 配置
      When 用户执行 "/sbtd onboard plan"
      Then Plan 只列出 OMP Global、Root Project、OMP Project Adapter 和当前 Profile 的 OMP-compatible 目标
      And 其他 Runtime 配置保持逐字节不变
      And 输出不包含其他 Runtime 的配置路径

    # @todo actual-host blockers: OMP 17.1.3 and 17.2.5 reject
    # `plugin install <local .tgz>`, and 17.1.3 exits before RPC ready without
    # an account/provider after initializing its agent state. The smoke
    # test packs/extracts and characterizes that no-provider block without
    # fabricating a credentialed or networked success.
    @todo @smoke-only
    Scenario: 已打包 Plugin 在隔离 OMP host 中完成只读命令
      Given OMP host 从实际 tarball 解压出的 Plugin 加载已编译 extension
      And 隔离 HOME 中存在与 OMP 无关的其他 Runtime 配置
      When 用户依次执行 "/sbtd help"、"/sbtd status"、"/sbtd report" 和 "/sbtd onboard plan"
      Then 所有命令在不调用 Provider 或 Tool 的前提下返回结构化结果
      And 其他 Runtime 配置保持逐字节不变
      And Plugin、项目和 OMP agent directory 保持允许范围内的零写入
