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

  Scenario: 同一目标重复调用保留 passed
    Given 同一 taskId 的 plan 中某 required gate 已 passed
    When 再次调用 sbtd_plan 且触发事实仍在
    Then 该 gate 保持 passed
    And 若触发事实消失则写明原因并不再当作 required
