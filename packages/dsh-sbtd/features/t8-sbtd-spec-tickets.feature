Feature: DSH T8 sbtd_spec / sbtd_tickets Trellis artifacts
  模型通过 sbtd_spec 写 prd.md、通过 sbtd_tickets 写 implement.md。
  有 .trellis/ 且可解析 task slug 时写入；否则 draft；DDD required 未 confirmed 则 blocked。
  空 markdown/body 拒绝写入，不静默覆写已有 artifact。

  Scenario: apply 注册 sbtd_spec 与 sbtd_tickets
    Given 插件已加载
    When 宿主枚举已注册 tools
    Then tools 含 sbtd_plan、sbtd_review、sbtd_clarify、sbtd_spec、sbtd_tickets
    And inject 仍为 tools 与 systemPrompt

  Scenario: 可写路径写入 prd.md
    Given 工作树存在 .trellis/
    And 已给出安全 task slug 或可用 current-task pointer
    And plan 未把 ddd 拦在 required 未 confirmed
    When 模型以非空 markdown 调用 sbtd_spec
    Then mode 为 written
    And 仅写入 .trellis/tasks/<slug>/prd.md
    And 不写 docs/ 下文件

  Scenario: 可写路径写入 implement.md
    Given 工作树存在 .trellis/
    And 已给出安全 task slug
    When 模型以非空 markdown 调用 sbtd_tickets
    Then mode 为 written
    And 仅写入 .trellis/tasks/<slug>/implement.md
    And 不创建 child task 目录

  Scenario: 无 .trellis 时 draft 不落盘
    Given 工作树不存在 .trellis/（detect.exists=false）
    When 模型调用 sbtd_spec 或 sbtd_tickets 并给出非空 markdown
    Then mode 为 draft
    And 返回原 markdown
    And 不创建 .trellis/
    And 不写 docs/

  Scenario: 无法解析 task 路径时 draft
    Given 工作树存在 .trellis/
    And 未给 explicit task 且 pointer 不可用或非法
    When 模型调用 sbtd_spec
    Then mode 为 draft
    And 不创建 tasks 目录
    And tool 不抛错

  Scenario: required DDD 未 confirmed 则 blocked
    Given plan.gates.ddd 为 required 且 reviewStatus 不是 confirmed
    When 模型调用 sbtd_spec 或 sbtd_tickets
    Then mode 为 blocked
    And ok 为 false
    And blocked.kind 为 ddd-unconfirmed
    And suggestPrd 与 suggestImplement 均为 false
    And 不写 prd.md 或 implement.md

  Scenario: 空 markdown 或 body 拒绝并保留已有 artifact
    Given .trellis/tasks/<slug>/ 下已有 prd.md 或 implement.md
    When 模型省略 markdown 与 body，或以空白串调用 sbtd_spec 或 sbtd_tickets
    Then tool 抛错
    And 已有 artifact 字节不变
