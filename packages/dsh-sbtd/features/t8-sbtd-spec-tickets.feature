Feature: DSH T8 sbtd_spec / sbtd_tickets draft-only artifacts
  R1 Q2 A：sbtd_spec 返回 PRD draft、sbtd_tickets 返回 implement draft，一律 draft-only。
  插件不写任何 task 文件：没有 mode: written，不写 .trellis/tasks/<slug>/prd.md|implement.md，
  不写 docs/，也不创建 task 目录；draft 由调用方自行持久化。
  DDD required 未 confirmed 则 blocked；空 markdown/body 拒绝。

  Scenario: apply 注册 sbtd_spec 与 sbtd_tickets
    Given 插件已加载
    When 宿主枚举已注册 tools
    Then tools 含 sbtd_plan、sbtd_review、sbtd_clarify、sbtd_spec、sbtd_tickets
    And inject 仍为 tools 与 systemPrompt

  Scenario: 始终 draft，即使存在可写 legacy task pointer 也不落盘
    Given 工作树存在 .trellis/tasks/<slug>/ 与可解析的 current-task pointer
    And prd.md 与 implement.md 已存在且内容为宿主所有
    When 模型以非空 markdown 调用 sbtd_spec 或 sbtd_tickets
    Then mode 为 draft
    And ok 为 true
    And 返回原 markdown
    And 工作树文件与目录完全不变
    And 不写 .trellis/ 或 docs/ 下任何文件

  Scenario: required DDD 未 confirmed 则 blocked
    Given plan.gates.ddd 为 required 且 reviewStatus 不是 confirmed
    When 模型调用 sbtd_spec 或 sbtd_tickets
    Then mode 为 blocked
    And ok 为 false
    And blocked.kind 为 ddd-unconfirmed
    And suggestPrd 与 suggestImplement 均为 false
    And 不写任何文件
    When DDD review 被 confirmed
    Then 再次调用 mode 为 draft
    When DDD review 再次变为 blocked
    Then 再次调用 mode 为 blocked

  Scenario: 空 markdown 或 body 拒绝
    When 模型省略 markdown 与 body，或以空白串调用 sbtd_spec 或 sbtd_tickets
    Then tool 抛错
    And 显式空 markdown 不回退到 body

  Scenario: 宿主看到的 spec/tickets 输出 schema 只有 mode 与 artifact
    Given 插件已向宿主注册 sbtd_spec 与 sbtd_tickets
    When 宿主读取 output.schema
    Then mode 与 artifact 的 type 为 string
    And schema 不含 slug 或 source 字段
    And 所有属性的 type 均不是数组
