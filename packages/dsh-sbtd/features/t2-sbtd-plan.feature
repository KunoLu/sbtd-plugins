Feature: DSH T2 sbtd_plan Book Gate Plan
  模型需要登记一份 Book Gate Plan：五项 gate 都有 requirement 和 state，
  写入 T1 按 session 隔离的进程内状态，不写 AGENTS.md。

  Scenario: 调用 sbtd_plan 后会话中有完整五项 gate
    Given T1 会话状态已按 sessionId 隔离
    When 模型调用 sbtd_plan 并给出 task_summary
    Then 该 session 的 state.plan 存在
    And 五项 gate 都有 requirement 与 state
    And 返回完整 plan JSON 和给人看的 Markdown 表

  Scenario: required 由客观谓词推断
    Given 调用方只给摘要或客观 facts
    When sbtd_plan 按 PRD 3.4 谓词推断
    Then 命中触发事实的 gate 为 required 且 state 为 planned
    And 未命中的 gate 为 on-demand 且 state 为 not-required
    And 不因主观高风险降级
    And 仅完整执行 grill-with-docs 后 DDD 为 required
    And 仅出现裸 ddd 时 DDD 仍为 on-demand

  Scenario: 空 task_summary 被拒绝
    Given 调用方未给出非空 task_summary
    When 调用 sbtd_plan
    Then tool 抛错且不写入 plan

  Scenario: 新 taskId 开新 plan
    Given 会话中已有另一摘要 slug 的 passed plan
    When 使用不同 task_summary 再次调用 sbtd_plan
    Then 写入新 plan 且不保留上一目标的 passed

  Scenario: restore hydrate 且空 snapshot 清除 plan
    Given T1 restore 已按 snapshot hydrate
    When 传入空 snapshot
    Then plan 被清除
    And T2 不改写 restore 实现

  Scenario: 同一目标重复调用保留 passed
    Given 同一 taskId 的 plan 中某 required gate 已 passed
    When 再次调用 sbtd_plan 且触发事实仍在
    Then 该 gate 保持 passed
    And 若触发事实消失则写明原因并不再当作 required


  Scenario: required passed 触发事实变化则重置 planned
    Given 同一 taskId 的 required gate 已 passed
    When 再次调用 sbtd_plan 且触发事实字符串已变
    Then 该 gate 为 required planned
    And reviewStatus 已清除
    And fact 写明 trigger fact changed 及旧到新
    And 若触发事实字符串相同则保持 passed 与 reviewStatus
    And 若先前 fact 是 reason 字符串则保持 passed 并可更新为推断 fact

  Scenario: on-demand passed 提升 required 时重置 planned
    Given 同一 taskId 的 on-demand gate 已 passed
    When 再次调用 sbtd_plan 且该 gate 现为 required
    Then 该 gate 为 required planned
    And 不继承 on-demand 的 passed
    And fact 写明 promoted from on-demand; reset inherited pass
    And 若先前已是 required 的 running blocked 或 planned 则保持该 state

  Scenario: 宿主看到的 sbtd_plan 参数是 JSON Schema 对象根
    Given 插件已向宿主注册 sbtd_plan
    When 宿主读取该 tool 的 parameters 与输出 schema
    Then parameters 根节点 type 为 object
    And task_summary 在 properties 中且出现在 required
    And 返回值 plan 的 type 为 object 而不是 json
