Feature: DSH T5 sbtd_review 五项 book gate
  模型通过 sbtd_review 提交规定标题的 Review，按源 skill 状态枚举推进 gate。
  不替代项目规范或测试。结论只在返回值。

  Scenario: apply 只注册 sbtd_plan 与 sbtd_review
    Given 插件已加载
    When 宿主枚举已注册 tools
    Then tools 恰好两个：sbtd_plan 与 sbtd_review
    And inject 仍为 tools 与 systemPrompt

  Scenario: kind 只有五枚举
    Given session 已有 plan
    When 模型用 skill-id 或别名调用 sbtd_review
    Then tool 抛错
    And 不推进任何 gate

  Scenario: 无 plan 时指向 sbtd_plan
    Given 当前 session 没有 plan
    When 模型调用 sbtd_review kind=legacy status=characterized
    Then tool 指出先调用 sbtd_plan
    And 不假装 passed
    And 不推进任何 gate

  Scenario: 通过态映射为 passed
    Given session 已有 plan
    When 模型提交 characterized 或 proceed 或 confirmed 或 ready
    Then 对应 gate state 为 passed
    And reviewStatus 已存储
    And requirement 不变

  Scenario: 未通过态保持 running 或 blocked
    Given session 已有 plan
    When 模型提交 needs-* 或 seam-required 或 refactor-first
    Then 对应 gate state 为 running
    When 模型提交 blocked
    Then 对应 gate state 为 blocked

  Scenario: on-demand review 不升为 required
    Given plan 中 legacy 为 on-demand
    When 模型调用 sbtd_review kind=legacy status=characterized
    Then requirement 仍为 on-demand
    And reviewStatus 为 characterized

  Scenario: 返回规定标题与 requirement 和 state
    Given session 已有 plan
    When 模型完成一次 sbtd_review
    Then 返回值含规定标题
    And 含该 gate 的 requirement 与 state
    And 结论只出现在返回值
    And 从 import.meta.url 只读加载对应 SKILL.md

  Scenario: legacy characterized 后允许生产 write
    Given plan 中仅 legacy 为 required
    When 模型以 characterized 完成 sbtd_review
    Then 对 src/foo.ts 的 write 被放行

  Scenario: required 未通过的其他门禁仍生效
    Given plan 中 legacy 与 refactor 与 ddd 均为 required
    And legacy 已 characterized
    When 模型写 src/foo.ts
    Then 因 refactor 被 deny
    Given 仅 ddia 为 required 未 passed
    When 模型写 src/schema.sql
    Then 因 ddia 被 deny
    Given 仅 release 为 required 未 passed
    When 模型写 src/foo.ts
    Then 放行
    When 模型执行 bash npm publish
    Then 因 release 被 deny
