Feature: DSH T6 sbtd_clarify 澄清适配器
  模型通过 sbtd_clarify 做 grilling 访谈。Clarify Mode 会话绑定；
  Complete 需要空 frontier 且用户确认；仅 docs Complete 强制 DDD。

  Scenario: 首次调用必须绑定 mode
    Given 当前 session 尚未绑定 Clarify Mode
    When 模型省略 mode 调用 sbtd_clarify
    Then tool 抛错
    When 模型以 mode=docs 调用
    Then 绑定 docs
    When 模型省略 mode 再次调用
    Then 继承 docs

  Scenario: 切换 mode 直到 Interview Reset 才允许
    Given session 已绑定 docs
    When 模型以 mode=generic 调用 sbtd_clarify
    Then tool 抛错
    When 模型传入 reset=true
    Then Clarify Mode 已解绑
    When 模型以 mode=generic 调用
    Then 绑定 generic

  Scenario: compaction 还原 mode 与 clarifyStatus 且不是 Reset
    Given session 已绑定 docs 且 clarifyStatus 为 partial
    When 序列化再 restore 到另一 session
    Then mode 仍为 docs
    And clarifyStatus 仍为 partial
    And 该 restore 不解绑 mode

  Scenario: docs Complete 经共享 mapper 提升 ddd
    Given session 已有不含 grill-with-docs 的 plan
    And Clarify Mode 为 docs
    When 模型在空 frontier 且用户确认下 Complete
    Then ddd 为 required
    And 已调用共享 sbtdReview kind=ddd
    And Partial 路径不会调用 sbtdReview

  Scenario: generic Complete 不自动要求 DDD
    Given session 已有 plan
    And Clarify Mode 为 generic
    When 模型 Complete
    Then ddd 仍为 on-demand
    And 未写入 grill-with-docs haystack 事实
    And 未强制调用 sbtdReview

  Scenario: 每次调用只有一个当前问题
    Given session 已绑定 mode
    When 模型传入单个 question
    Then 返回值 currentQuestion 为该字符串
    And 返回值不是问题列表

  Scenario: Complete 双门与 manuals
    Given session 已绑定 mode 且已有 plan
    When 仅 frontier 为空但用户未确认
    Then clarifyStatus 为 partial
    When 仅加载 manuals
    Then clarifyStatus 为 partial
    And 加载 manuals 不等于 Complete

  Scenario: Partial 可无计划 Complete 必须有计划
    Given 当前 session 没有 plan
    When 模型 Partial 提问
    Then 成功且 clarifyStatus 为 partial
    When 模型尝试 Complete
    Then tool 指出先调用 sbtd_plan

  Scenario: Complete 且 DDD 未 confirmed 一次性 blocked
    Given docs Complete 后 required ddd 不是 confirmed
    Then 返回 clarifyStatus 为 complete
    And 返回 blocked 且不建议 PRD 或实现
    When 模型再次调用 sbtd_clarify 且未 reset
    Then tool 抛错指出 Complete 已是终态

  Scenario: required 未通过的 ddd 仍拦生产 write
    Given docs Complete 已把 ddd 升为 required 且未 confirmed
    When 模型写 src/foo.ts
    Then 因 ddd 被 deny
    And 同摘要省略 grill facts 再 plan 后 ddd 仍为 required blocked
    And 生产 write 仍因 ddd 被 deny

  Scenario: Interview Reset 后省略 facts 允许 demote Forced Docs DDD
    Given docs Complete 后 ddd 为 required
    When 模型传入 reset=true
    And 以同一摘要省略 grill facts 调用 sbtd_plan
    Then ddd 可降为 on-demand

  Scenario: docs Complete 只粘滞完成澄清的那份任务
    Given 任务 A 已 docs Clarify Complete
    When 切换到任务 B 并先带 grill-with-docs 事实再省略
    Then B 的 Forced Docs DDD 可撤回
    And 生产 write 不因 A 的 Complete 被 deny

  Scenario: 宿主看到的 sbtd_clarify 输出 schema 不含 type 数组
    Given 插件已向宿主注册 sbtd_clarify
    When 宿主读取 output.schema
    Then mode 与 currentQuestion 的 type 为 string 且不是数组
    And execute 在 Complete 或 reset-only 时省略值为 null 的键

