Feature: DSH T3 hooks 门禁
  模型在没有 Book Gate Plan 或强制 gate 未通过时，不能改生产代码。
  门禁走 tools/pre-execute 与 agent/pre-step，不新增 sbtd_* tool。

  Scenario: 无 plan 时写 src 被 ask 去 sbtd_plan
    Given 当前 session 没有 plan
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 返回 kind ask
    And reason 指出先调用 sbtd_plan

  Scenario: README 编辑放行
    Given 当前 session 没有 plan
    When 模型编辑 README.md
    Then pre-execute 调用 next 放行

  Scenario: view 与 git 只读或 commit 放行
    Given 任意 session
    When 模型调用 view 或 bash git commit status log diff show
    Then pre-execute 调用 next 放行

  Scenario: required gate 未 passed 时 deny 去 sbtd_review
    Given session 已有 plan 且 legacy 为 required 未 passed
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 返回 kind deny
    And reason 指出先调用 sbtd_review kind=legacy

  Scenario: 硬拦顺序为 legacy 然后 refactor 然后 ddd
    Given plan 中 legacy 与 refactor 均为 required 未 passed
    When 模型改生产实现文件
    Then 先因 legacy 被 deny
    And 仅当 legacy 已 passed 才因 refactor 被 deny
    And 仅当 refactor 已 passed 才因 ddd 被 deny

  Scenario: ddia 只拦数据路径
    Given plan 中仅 ddia 为 required 未 passed
    When 模型写 src/foo.ts
    Then pre-execute 调用 next 放行
    When 模型写 src/schema.sql
    Then pre-execute 返回 deny 并指出 sbtd_review kind=ddia

  Scenario: release 不拦编辑但拦 publish bash
    Given plan 中仅 release 为 required 未 passed
    When 模型写 src/foo.ts
    Then pre-execute 调用 next 放行
    When 模型执行 bash npm publish
    Then pre-execute 返回 deny 并指出 sbtd_review kind=release

  Scenario: 测试 features maestro trellis 不硬拦
    Given session 没有 plan
    When 模型写 test/foo.test.ts 或 features 或 maestro/flow 或 .trellis 文档
    Then pre-execute 返回 ask 而不是 deny
    Given session 已有 plan 且 legacy 为 required 未 passed
    When 模型写上述豁免路径
    Then pre-execute 调用 next 放行

  Scenario: rm 或包管理器改业务代码要 ask
    Given session 没有 plan
    When 模型 bash rm 生产路径或对 src/app/packages 做包管理器变更
    Then pre-execute 返回 kind ask
    And reason 指出先调用 sbtd_plan
    Given plan 中 legacy 与 refactor 均为 required 未 passed
    When 模型对生产 PathClass 做 bash rm 或对 src/app/packages 做包管理器变更
    Then 先因 legacy 被 deny
    And 仅当 legacy 已 passed 才因 refactor 被 deny
    And 仅当 refactor 已 passed 才因 ddd 被 deny
    Given plan 中仅 ddia 为 required 未 passed
    When 模型 bash rm src/foo.ts 或对 src/app/packages 做包管理器变更
    Then pre-execute 调用 next 放行
    When 模型 bash rm src/schema.sql
    Then pre-execute 返回 deny 并指出 sbtd_review kind=ddia
    Given plan 中仅 release 为 required 未 passed
    When 模型对生产 PathClass 做 bash rm 或对 src/app/packages 做包管理器变更
    Then pre-execute 调用 next 放行

  Scenario: pre-step 注入尚未计划提醒且不 reject
    Given session 没有 plan 且用户意图是开发任务
    When 宿主触发 agent/pre-step
    Then 处理器先 await next
    And 不返回 reject
    And 注入 source.kind 为 plugin 的 notice 要求先 sbtd_plan

  Scenario: 门禁按 T1 T2 session 隔离
    Given 两个不同 agent.id 的 session
    When 仅其中一个调用了 sbtd_plan
    Then 未计划 session 的生产 write 被 ask
    And 已计划但 required 未过的 session 被 deny

  Scenario: Loop1 legacy required running seam-required 允许生产 write
    Given session 已有 plan 且 legacy 为 required running 且 reviewStatus 为 seam-required
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 调用 next 放行
    # Known limitation: no byte-level seam-vs-feature classifier.
    # Whole-window scoped allow: all production-class writes are allowed
    # while this reviewStatus is set. Q4A still-deny-non-remediation is honor-only.

  Scenario: Loop2 refactor required running refactor-first 允许生产 write
    Given session 已有 plan 且 legacy 已 passed
    And refactor 为 required running 且 reviewStatus 为 refactor-first
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 调用 next 放行
    # Known limitation: no byte-level seam-vs-feature classifier.
    # Whole-window scoped allow: all production-class writes are allowed
    # while this reviewStatus is set. Q4A still-deny-non-remediation is honor-only.

  Scenario: legacy required running needs-clarification 仍 deny
    Given session 已有 plan 且 legacy 为 required running 且 reviewStatus 为 needs-clarification
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 返回 kind deny
    And reason 指出先调用 sbtd_review kind=legacy

  Scenario: legacy 未 remediation 时 refactor-first 仍先因 legacy deny
    Given plan 中 legacy 为 required 未 passed 且无 seam-required
    And refactor 为 required running 且 reviewStatus 为 refactor-first
    When 模型对 src/foo.ts 调用 write
    Then 先因 legacy 被 deny

  Scenario: EXEMPT 在 legacy 未 passed 时仍放行
    Given session 已有 plan 且 legacy 为 required 未 passed
    When 模型写 test/foo.test.ts 或 features 或 maestro/flow 或 .trellis 文档
    Then pre-execute 调用 next 放行

  Scenario: Loop 窗口开启时 ddd required unpassed 仍 deny 生产 write
    Given session 已有 plan 且 ddd 为 required 未 passed
    And legacy 为 required running 且 reviewStatus 为 seam-required
    And refactor 已 passed 不挡
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 返回 kind deny
    And reason 指出先调用 sbtd_review kind=ddd
    # Known limitation: no byte-level seam-vs-feature classifier.
    # Whole-window scoped allow does not skip other required unpassed gates.
    # Q4A still-deny-non-remediation is honor-only.
    Given legacy 已 passed 且 refactor 为 required running 且 reviewStatus 为 refactor-first
    When 模型对 src/foo.ts 调用 write
    Then pre-execute 返回 kind deny
    And reason 指出先调用 sbtd_review kind=ddd

  Scenario: Loop 窗口开启时 ddia required unpassed 仍 deny 数据路径
    Given session 已有 plan 且 ddia 为 required 未 passed
    And legacy 为 required running 且 reviewStatus 为 seam-required
    And refactor 已 passed 不挡
    When 模型写 src/schema.sql
    Then pre-execute 返回 deny 并指出 sbtd_review kind=ddia
    # Known limitation: no byte-level seam-vs-feature classifier.
    # Whole-window scoped allow does not skip other required unpassed gates.
    # Q4A still-deny-non-remediation is honor-only.
    Given legacy 已 passed 且 refactor 为 required running 且 reviewStatus 为 refactor-first
    When 模型写 src/schema.sql
    Then pre-execute 返回 deny 并指出 sbtd_review kind=ddia

  Scenario: Loop 窗口开启时 release required unpassed 仍 deny publish bash
    Given session 已有 plan 且 release 为 required 未 passed
    And legacy 为 required running 且 reviewStatus 为 seam-required
    And refactor 已 passed 不挡
    When 模型执行 bash npm publish
    Then pre-execute 返回 deny 并指出 sbtd_review kind=release
    # Known limitation: no byte-level seam-vs-feature classifier.
    # Whole-window scoped allow does not skip other required unpassed gates.
    # Q4A still-deny-non-remediation is honor-only.
    Given legacy 已 passed 且 refactor 为 required running 且 reviewStatus 为 refactor-first
    When 模型执行 bash npm publish
    Then pre-execute 返回 deny 并指出 sbtd_review kind=release
