Feature: 验证报告与 Provider 观察
  OMP 用户需要在不改变当前 Session 选择的前提下，查看可复核且不含凭据的 SBTD 验证与 Provider 状态。

  Background:
    Given OMP 17.1 已加载与当前 SBTD Kit 匹配的 KPi Plugin

  Rule: 报告如实呈现当前 Session 的可复核状态

    Scenario: 查看当前 SBTD 报告
      Given 当前 Session 包含有效的工作流、验证、Evidence Envelope 与工具证据
      And 当前 Provider 观察只包含可公开的 provider 和 model 标识
      When 用户执行 "/sbtd report"
      Then 用户看到同一报告模型导出的确定性 JSON 和中文 Markdown
      And 报告包含工作流、验证、Evidence Envelope、工具证据与 Provider Coordination 分区
      And 当前 Session 不产生新的 KPi 状态记录
      And Runtime Mode、Policy Profile、Route 与门禁状态保持不变

    Scenario: 报告如实保留非完整链路验证模式
      Given 当前验证的实际 E2E Mode 为 "mock-backed"
      When 用户执行 "/sbtd report"
      Then 报告将 E2E Mode 显示为 "mock-backed"
      And 报告不将该验证显示为完整链路通过

    Scenario: 脏工作区的本地证据不冒充已发布证据
      Given 当前 Evidence Envelope 的来源为 "developer-local"
      And Source Revision 为 "dirty"
      And Evidence Publication 为 "local-only"
      When 用户执行 "/sbtd report"
      Then 报告显示 "developer-local"、"dirty" 与 "local-only"
      And 报告不将该证据显示为 CI 或已发布的 PR Head 证据

  Rule: 正式验证证据必须可追踪且保持新鲜

    Scenario: 同 Stem 的新鲜正式报告与中文 Markdown 可作为报告证据
      Given 当前验证需要正式报告
      And 当前运行创建了新鲜的常规正式报告文件
      And 同一目录存在同 Stem 的中文 Markdown 汇总
      When KPi 观察验证证据
      Then 验证状态保留正式报告与 Markdown 的相对路径、时间、大小和完整性标识
      And 交付门禁仍可按既有规则使用该报告对

    Scenario: 陈旧、目录或不同 Stem 的报告配对保持阻断
      Given 当前验证需要正式报告
      And 报告文件陈旧、是目录或缺少同 Stem 的 Markdown 汇总
      When KPi 观察验证证据
      Then 验证状态为 "blocked"
      And 该证据不成为正式交付证据

  Rule: Provider 观察不接触凭据或改变选择

    Scenario: Provider 不可用时保留显式阻断
      Given OMP 发出当前 provider 的 credential-disabled 通知
      When KPi 观察该 Provider 状态
      Then Provider Availability 为 "unavailable"
      And Fallback 为 "unavailable"
      And Selection Result 为 "blocked"
      And KPi 不选择能力不等价的替代模型

    Scenario: Provider 报告不保留 credential-disabled 原因
      Given OMP 发出包含敏感 disabledCause 的 credential-disabled 通知
      When 用户执行 "/sbtd report"
      Then Session 状态和报告不包含该 disabledCause
      And Session 状态和报告不包含凭据、Provider Header 或 Provider Response Metadata

  Rule: 版本化状态安全恢复

    Scenario: 有效版本化验证与 Provider 状态在 Session 重放后保留
      Given 当前 Session 记录了有效的版本化验证与 Provider 观察
      When OMP 重放该 Session
      Then KPi 恢复相同的验证、Evidence Envelope 与 Provider 状态

    Scenario: 无效的版本化验证或 Provider 状态失败关闭
      Given 最新 KPi Session 状态包含格式错误或不兼容的验证或 Provider 字段
      When OMP 重放该 Session
      Then KPi 拒绝使用较旧的状态作为回退
      And 用户看到 Session history repair 路径
