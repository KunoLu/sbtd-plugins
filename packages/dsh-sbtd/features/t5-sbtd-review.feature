Feature: DSH T5 sbtd_review 五项 book gate
  模型通过 sbtd_review 提交规定标题的 Review，按源 skill 状态枚举推进 gate。
  不替代项目规范或测试。结论只在返回值。

  Scenario: apply 只注册 sbtd_plan 与 sbtd_review
    Given 插件已加载
    When 宿主枚举已注册 tools
    Then tools 恰好两个：sbtd_plan 与 sbtd_review
    And inject 仍为 tools 与 systemPrompt

  Scenario: 五个规范 kind 成功且拒绝别名
    Given session 已有 plan
    When 模型用 legacy、refactor、ddd、ddia、release 调用 sbtd_review
    Then 五个 kind 均成功
    When 模型用 skill-id 或别名调用 sbtd_review
    Then tool 抛错
    And 不推进任何 gate

  Scenario: 无 plan 时指向 sbtd_plan
    Given 当前 session 没有 plan
    When 模型调用 sbtd_review kind=legacy status=characterized
    Then tool 指出先调用 sbtd_plan
    And 不假装 passed
    And 不推进任何 gate

  Scenario: 各 kind 通过态元组
    Given session 已有 plan
    When 模型提交 legacy characterized、refactor proceed、ddd confirmed、ddia confirmed、release ready
    Then 对应 gate state 为 passed
    And reviewStatus 已存储
    And requirement 不变

  Scenario: 五个规定标题
    Given session 已有 plan
    When 模型完成各 kind 的 sbtd_review
    Then 返回值含 Legacy Change Safety Review、Refactoring Review、DDD Boundary Review、DDIA Data Design Review、Release Readiness Review

  Scenario: 错误 kind 的 status 被拒绝
    Given session 已有 plan
    When 模型用错误 kind 的 status 调用 sbtd_review
    Then tool 抛错
    And 不推进任何 gate

  Scenario: 空白填充的 characterized 被拒绝
    Given session 已有 plan
    When 模型提交带空白填充的 characterized
    Then tool 抛错
    And gate 不变

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

  Scenario: on-demand ddia 通过后提升 required 不继承 passed
    Given hello world 的 plan 中 ddia 为 on-demand
    When 模型以 confirmed 和空结论完成 sbtd_review kind=ddia
    And 同一 task_summary 再次 sbtd_plan 并给出 persist facts
    Then ddia 为 required 且 state 为 planned 而非 passed
    And reviewStatus 已清除
    And fact 写明 promoted from on-demand; reset inherited pass
    When 模型用 str_replace_editor 改 src/schema.sql
    Then 因 ddia 被 deny

  Scenario: 独特结论只在返回值不落盘
    Given session 已有 plan
    When 模型提交带独特结论的 sbtd_review
    Then 结论出现在返回值
    And 会话状态与 manuals 不包含该结论

  Scenario: 可观察地加载对应 manual
    Given session 已有 plan
    When 模型完成一次 sbtd_review
    Then 返回值含对应 SKILL.md 正文
    And 渲染文本含已加载 manual

  Scenario: legacy characterized 后允许生产 write
    Given plan 中仅 legacy 为 required
    When 模型以 characterized 完成 sbtd_review
    Then 对 src/foo.ts 的 write 被放行

  Scenario: required 未通过的 refactor 拦生产 write
    Given plan 中 legacy 与 refactor 均为 required
    And legacy 已 characterized
    When 模型写 src/foo.ts
    Then 因 refactor 被 deny

  Scenario: 更早门禁通过后 required 未通过的 ddd 仍拦 write
    Given plan 中 legacy 与 refactor 与 ddd 均为 required
    And legacy 已 characterized
    And refactor 已 proceed
    When 模型写 src/foo.ts
    Then 因 ddd 被 deny

  Scenario: required 未通过的 ddia 拦数据路径
    Given 仅 ddia 为 required 未 passed
    When 模型写 src/schema.sql
    Then 因 ddia 被 deny

  Scenario: required 未通过的 release 拦 publish-family bash
    Given 仅 release 为 required 未 passed
    When 模型写 src/foo.ts
    Then 放行
    When 模型执行 bash npm publish
    Then 因 release 被 deny
