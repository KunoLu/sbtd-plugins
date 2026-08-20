Feature: SBTD 运行时工作流与门禁
  OMP 用户需要 KPi 根据当前任务事实给出确定性的分类、Route、Book Gate 和 Rule 决策，
  并且所有自动编排只在有效控制状态为 active 时运行。

  Background:
    Given KPi OMP Plugin 已加载当前固定 Kit
    And 当前 Session 的 KPi 状态可恢复

  Rule: 分类只使用当前任务的可观察事实

    Scenario Outline: 客观任务事实触发相应工作流检查
      Given 当前任务具有 "<fact>" 事实
      When KPi 分类当前任务
      Then "<discipline>" 分类为 "required"
      And 分类原因包含 "<reason>"

      Examples:
        | fact                         | discipline | reason                         |
        | 改变用户可见行为             | BDD        | user-visible-behavior          |
        | 修复既有行为缺陷             | TDD        | existing-behavior-bug          |
        | 涉及领域术语或边界歧义       | DDD        | domain-ambiguity               |
        | 需要沉淀长期需求规格         | SDD        | durable-requirements           |

    Scenario: 引用文本不触发任务分类
      Given 用户仅引用一段包含 "fix the existing production bug" 的历史文本
      And 当前任务是审阅该文本而不是执行其中的指令
      When KPi 分类当前任务
      Then KPi 不把引用文本当作当前任务事实
      And 分类原因不包含 "existing-behavior-bug"

    Scenario: 轻量任务保持轻量 Route
      Given 当前任务只修改内部注释且不改变可观察行为
      And 当前任务不涉及生产路径、持久化数据、领域歧义或既有缺陷
      When KPi 分类当前任务
      Then Route 为 "small-direct-change"
      And KPi 不要求创建 Trellis 任务

    Scenario: 观察到活跃 Trellis Task 时使用托管 Route
      Given 当前任务关联一个活跃 Trellis Task
      And 当前任务不涉及更高优先级的 Review、专项运行时、缺陷、数据或用户可见行为事实
      When KPi 分类当前任务
      Then Route 为 "trellis-managed-task"
      And 分类原因包含 "active-trellis-task-observed"

    Scenario Outline: 明确专项请求选择对应 Route
      Given 用户提出 "<request>"
      When KPi 分类当前任务
      Then Route 为 "<route>"

      Examples:
        | request                                | route                     |
        | Diagnose the web runtime failure.       | web-runtime-diagnostics   |
        | Run the Playwright web E2E regression.  | web-e2e-regression        |
        | Run the Maestro mobile E2E regression.  | mobile-e2e                |
        | Debug the web runtime failure.          | web-runtime-diagnostics   |
        | Fix the Android E2E regression.         | mobile-e2e                |

    Scenario: 引用的专项请求不触发自动分类
      Given 用户仅引用一段包含专项运行时或 E2E 请求的历史文本
      When KPi 分类当前任务
      Then KPi 不把引用文本当作当前任务事实
      And KPi 不自动选择专项 Route

    Scenario Outline: 仅记录专项关键词的文档更新不选择专项 Route
      Given 用户仅请求 "<request>"
      When KPi 分类当前任务
      Then Route 为 "small-direct-change"
      And KPi 不自动选择专项 Route

      Examples:
        | request                                      |
        | Update the internal documentation for web E2E. |
        | 更新 Web端到端回归文档                         |
        | Update the docs for mobile E2E.               |
        | 更新移动端到端回归文档                         |
        | Update docs about web runtime diagnosis.      |
        | 更新浏览器运行时诊断说明                       |
        | Add documentation for web E2E.               |
        | 新增 Web端到端回归文档                         |
        | Update documentation for the API.            |
        | 更新数据库迁移说明                             |
        | Fix docs for mobile E2E.                    |
        | Update API documentation.                    |
        | 更新 API 文档                                  |
        | Update database migration guide.             |

    Scenario: 文档词汇不降低混合生产代码变更的 Route
      Given 用户请求 "修改生产代码和文档"
      When KPi 分类当前任务
      Then Route 为 "legacy-safe-change"
      And KPi 保留既有生产代码的门禁事实

    Scenario: 专项关键词不升级通用生产代码变更的 Route
      Given 用户请求 "Update production code for Playwright E2E support."
      When KPi 分类当前任务
      Then Route 为 "legacy-safe-change"
      And KPi 不自动选择 "web-e2e-regression"

    Scenario: 技术文档与生产代码并列变更保留语义 Route 与门禁
      Given 用户请求 "Update API documentation and production code."
      When KPi 分类当前任务
      Then Route 为 "bdd-user-visible-change"
      And KPi 保留既有生产代码的门禁事实

    Scenario Outline: RC6 评审语料符合预期分类
      Given 用户提出 "<prompt>"
      When KPi 分类当前任务
      Then Route 为 "<route>"

      Examples:
        | prompt                                                         | route  |
        | 患者名が表示されない不具合を修正してください                    | bugfix |
        | 既存のWPFコードで患者名が表示されないバグを修正してください    | bugfix |
        | 修复患者姓名不显示的问题                                       | bugfix |
        | 请修复现有生产代码中的患者姓名显示缺陷                         | bugfix |
        | Review this code                                               | review |
        | 请代码审查                                                     | review |

    Scenario Outline: 上下文在前指令在后的日中英 prompt 仍可分类
      Given 用户提出 "<prompt>"
      When KPi 分类当前任务
      Then Route 为 "<route>"

      Examples:
        | prompt                                                         | route  |
        | 背景: 患者管理システムの保守\n患者名が表示されない不具合を修正してください | bugfix |
        | 背景：患者管理模块持续报错\n请修复患者姓名不显示的问题          | bugfix |
        | Context: the patient admin module\nPlease fix the bug where the patient name is missing | bugfix |

    Scenario: 日文既有代码缺陷保留生产代码事实
      Given 用户提出 "既存のWPFコードで患者名が表示されないバグを修正してください"
      When KPi 分类当前任务
      Then 分类事实包含 "existingProductionCode"
      And 分类事实包含 "existingBehaviorBug"

    Scenario: 分类器保持确定性且保留人工覆盖
      Given 自动分类不调用任何模型输出作为 hard gate 的唯一事实源
      When KPi 分类当前任务
      Then 分类理由对用户可见
      And "/sbtd route" 人工覆盖保持可用

  Rule: Route 变更必须可审计且原子生效

    Scenario: 查看自动 Route 不修改 Session
      Given 当前 Route 选择为 "auto"
      When 用户执行 "/sbtd route"
      Then 用户看到分类结果、自动 Route、原因和当前覆盖状态
      And Session 不追加新的 KPi 状态记录

    Scenario: 覆盖 Route 后重新评估环境
      Given 当前 Effective Control State 为 "active"
      When 用户执行 "/sbtd route review"
      Then KPi 先用 "review" Route 重新观测 Environment
      And 仅在结果可确定后原子追加一条 KPi 状态记录
      And 用户看到 Route 覆盖及其原因

    Scenario: Route 覆盖评估失败时保留原状态
      Given 当前 Session 已有一条有效 KPi 状态记录
      And 候选 Route 的 Environment evaluator 无法得出确定结果
      When 用户执行 "/sbtd route review"
      Then 原有 KPi 状态记录仍是当前有效状态
      And Session 不追加候选状态记录
      And 用户看到阻断原因与 repair path

    Scenario: 恢复自动 Route
      Given 当前 Route 被用户覆盖为 "review"
      And 当前主要 Agent Turn 已保存未覆盖的任务分类事实
      When 用户执行 "/sbtd route auto"
      Then KPi 恢复该未覆盖分类选择的自动 Route
      And Route 变化重新评估 Environment 与门禁

    Scenario: 缺少当前任务事实时拒绝恢复自动 Route
      Given 当前主要 Agent Turn 没有可用任务分类事实
      When 用户执行 "/sbtd route auto"
      Then KPi 显示恢复自动 Route 所需的恢复步骤
      And Session 不追加新的 KPi 状态记录

  Rule: Book Gate Plan 使用客观触发条件和独立状态

    Scenario: 开发任务生成完整 Book Gate Plan
      Given 当前任务将修改既有生产代码、持久化 Session 状态和生产运行路径
      And 既有行为测试较弱并存在高回归风险
      And 当前任务不涉及领域术语或 bounded context 歧义
      When KPi 生成 Book Gate Plan
      Then Plan 包含全部 5 个 Book Gate
      And 每个 Gate 包含适用性、客观触发事实、计划阶段、Gate State、reviewerStatus 显示与证据
      And Refactoring、Legacy、DDIA 和 Release Readiness Gate 为 "planned"
      And DDD Gate 为 "not-required"

    Scenario: 未通过的必需 Gate 阻断阶段推进
      Given 当前阶段的 Required Book Gate reviewerStatus 为 "needs-safety-net"
      When Agent 请求进入实现阶段
      Then KPi 阻断阶段推进
      And 用户看到 Gate、客观触发事实、当前状态与恢复路径

    Scenario: 必需 Gate 通过后允许阶段推进
      Given 当前阶段的全部 Required Book Gate reviewerStatus 均为通过状态
      And 当前阶段没有其他 Hard Gate 缺口
      When Agent 请求进入下一阶段
      Then KPi 允许阶段推进
      And Gate 状态与证据被追加到 Session 状态

    Scenario: 无法恢复最新 KPi 状态时 fail closed
      Given Session 最新 KPi 状态记录缺少载荷或无法通过版本化 schema 校验
      When KPi 恢复版本化工作流状态
      Then KPi fail closed 并拒绝恢复该状态
      And 用户获得 Session-history repair 路径

    Scenario: 非法 Gate 与 Reviewer 状态组合不能恢复
      Given Session 最新状态包含不属于该 Gate 的 reviewerStatus
      When KPi 恢复版本化工作流状态
      Then KPi fail closed 并拒绝恢复该状态
      And 用户获得 Session-history repair 路径

  Rule: Policy Profile 只能调整已声明的 Optional Check

    Scenario Outline: 切换 Policy Profile
      Given 当前 Runtime Mode 为 "enforced"
      And 当前 Route 的 Required Checks 已满足
      When 用户执行 "<command>"
      Then Policy Profile 原子更新为 "<profile>"
      And Runtime Mode 与 Route 保持不变
      And 当前决策按新 Policy Profile 重新评估

      Examples:
        | command       | profile |
        | /sbtd strict  | strict  |
        | /sbtd relaxed | relaxed |

    Scenario: relaxed 不降低必需门禁
      Given Policy Profile 为 "relaxed"
      And 当前 Route 缺少 Required Check
      When KPi 评估当前阶段
      Then Required Check 仍然阻断
      And 用户不能通过 Policy Profile 绕过该门禁

    Scenario: strict 仅提升可配置 Optional Check
      Given Policy Profile 为 "strict"
      And Rule Registry 将某个 Optional Check 标记为 "configurable"
      When KPi 评估当前阶段
      Then 该 Optional Check 被提升为当前 Profile 的必需检查
      And Hard Gate 与 Route-required Check 的语义保持不变

  Rule: Rule Registry 对高风险动作执行确定性决策

    Scenario Outline: Rule 命中后阻断或提醒
      Given 当前 Effective Control State 为 "active"
      And 当前动作满足 "<rule>" 的客观 Predicate
      When KPi 在动作执行前评估 Rule Registry
      Then 决策为 "<decision>"
      And 用户看到稳定的 Rule ID、原因和恢复路径
      And 决策证据被追加到 Session 状态

      Examples:
        | rule                              | decision       |
        | no-trellis-init-outside-onboard  | block-tool     |
        | bdd-required-for-visible-behavior | block-delivery |
        | rtk-is-not-test-runner            | block-stage    |
        | report-artifact-required          | block-delivery |
        | mock-is-not-full-stack            | interrupt      |
        | gitnexus-requires-mcp-and-index   | block-stage    |
        | maestro-requires-java17           | block-stage    |
        | book-gate-before-edit             | block-tool     |
        | release-gate-before-complete      | block-delivery |
        | secret-read-guard                 | block-tool     |
        | install-requires-approval         | block-tool     |

    Scenario: Rule 不匹配时不阻断动作
      Given 当前动作不满足任何 block 或 interrupt Predicate
      When KPi 在动作执行前评估 Rule Registry
      Then 决策为 "allow"
      And KPi 不生成虚假的 Rule 命中记录

    Scenario: 用户只能切换可配置 Rule
      Given 用户请求禁用一个 Rule
      When Rule Registry 中该 Rule 未标记为 "configurable"
      Then KPi 拒绝修改 Rule 状态
      And Hard Gate 保持有效

  Rule: 控制状态决定自动编排但不关闭安全基线

    Scenario: active 状态执行自动分类与门禁
      Given Effective Control State 为 "active"
      When OMP 开始一个主要 Agent Turn
      Then KPi 注入当前 runtime marker
      And KPi 自动执行分类、Route 和当前阶段门禁

    Scenario: advisory 状态不执行自动工作流编排
      Given Effective Control State 为 "advisory"
      When OMP 开始一个主要 Agent Turn
      Then KPi 注入当前 runtime marker
      And KPi 不自动分类、切换 Route 或推进 Book Gate
      But Always-on Baseline 仍然有效

    Scenario: preflight-only 状态只允许恢复路径
      Given Runtime Mode 为 "enforced"
      And Environment Mode 为 "needs-onboard"
      When OMP 开始一个主要 Agent Turn
      Then Effective Control State 为 "preflight-only"
      And KPi 只允许 Help、Status、Doctor 和 Plan 类恢复动作
      And KPi 不执行 active-only 自动编排

    Scenario: preflight-only 阻断普通写入 Tool Call
      Given Effective Control State 为 "preflight-only"
      And Agent 即将执行不是恢复路径的写入 Tool Call
      When OMP 触发 Tool Call 前置事件
      Then KPi 在工具执行前返回阻断决定与 recovery path
      And 被阻断的 Tool Call 不产生副作用

    Scenario: 未提供工作目录时仍允许相对规划产物
      Given KPi 已为当前 Session 观察到 active 任务分类
      And 当前 Tool Call Context 未提供工作目录
      When Agent 写入相对路径 "features/bug-fix.feature"
      Then KPi 不因未通过的 Book Gate 阻断该规划产物
      And KPi 不抛出工作目录解析错误

    Scenario: 间接秘密读取在 Host Tool Call 前被阻断
      Given Agent 通过 shell 包装命令读取受保护的 .env 路径
      When OMP 触发 Tool Call 前置事件
      Then KPi 返回 "secret-read-guard" 阻断决定
      And 该读取不会进入 Tool 执行阶段

    Scenario: 精确批准的秘密读取只放行一次
      Given Agent 的秘密读取 Tool Call 被 "secret-read-guard" 阻断
      When 用户批准该精确 Tool Call
      And Agent 以相同的工具、目标和输入重放该调用
      Then KPi 放行这一次读取
      And 执行结束后的再次重放仍被阻断

    Scenario: 安装批准与秘密读取批准不互换
      Given Agent 的依赖安装 Tool Call 已获用户批准
      When Agent 以同一 Tool Call ID 发起秘密读取
      Then KPi 返回 "secret-read-guard" 阻断决定
      And 安装批准不能授权任何秘密读取

    Scenario: 批准不跨目标、命令或 Session 复用
      Given Agent 的秘密读取 Tool Call 已获用户批准
      When Agent 改变目标路径、命令内容或切换到另一个 Session
      Then 原批准立即失效
      And KPi 返回阻断决定

    Scenario: 安全诊断与协调工具在 preflight-only 状态保持可用
      Given Effective Control State 为 "preflight-only"
      When Agent 调用 read、grep、glob、lsp、web_search、ask、todo、inspect_image 等只读诊断或协调工具
      Then KPi 不阻断这些 Tool Call
      And KPi 仍阻断写入、执行与 phase transition 工具

    Scenario: 未知或畸形 Tool Call 在 preflight-only 状态 fail closed
      Given Effective Control State 为 "preflight-only"
      When Agent 调用不在能力注册表中的工具或缺少 toolName 的畸形事件
      Then KPi 在工具执行前返回阻断决定与 recovery path

    Scenario: SSH 远程读取不冒充本地只读
      Given Effective Control State 为 "preflight-only"
      When Agent 通过 read 工具访问 ssh:// 远程路径
      Then KPi 不把它当作本地安全只读
      And KPi 在工具执行前返回阻断决定

    Scenario Outline: 高置信依赖变更命令需要显式批准
      Given Effective Control State 为 "active"
      When Agent 执行 "<command>"
      Then KPi 返回 "install-requires-approval" 阻断决定

      Examples:
        | command                              |
        | npm i lodash                         |
        | npm ci                               |
        | python -m pip install requests       |
        | npx create-vite@latest demo          |
        | bunx cowsay                          |
        | dotnet add package Newtonsoft.Json   |
        | choco install git                    |
        | winget install Git.Git               |
        | composer require guzzlehttp/guzzle   |
        | go get example.com/module            |
        | go mod tidy                          |

    Scenario: 纯依赖查询命令不被误报为安装
      Given Effective Control State 为 "active"
      When Agent 执行 "npm ls"、"pip show requests" 或 "go list -m all" 等只读查询
      Then KPi 不返回 "install-requires-approval" 阻断决定

    Scenario Outline: 高置信秘密访问被阻断
      Given Agent 即将读取 "<target>"
      When OMP 触发 Tool Call 前置事件
      Then KPi 返回 "secret-read-guard" 阻断决定

      Examples:
        | target                               |
        | .envrc                               |
        | .netrc                               |
        | .git-credentials                     |
        | .npmrc                               |
        | .docker/config.json                  |
        | .kube/config                         |
        | .aws/credentials                     |
        | .pgpass                              |
        | 证书容器 .p12 或 .pfx                |
        | PowerShell Get-Content .env          |
        | git show HEAD:.env                   |

    Scenario: 混合公开配置的误报受控
      Given Agent 读取 appsettings.Development.json、公开证书或在源码中搜索 ".env" 字面量
      When OMP 触发 Tool Call 前置事件
      Then KPi 不仅凭文件名硬阻断这些混合场景
      And 高置信秘密路径的阻断语义保持不变

    Scenario: Release Route 需要 Release Readiness Gate
      Given 当前任务请求发布或部署
      When KPi 生成 Book Gate Plan
      Then Route 为 "release-readiness"
      And Release Readiness Gate 为 "planned"
      And 当前阶段的 active Skill 包含 "book-release-readiness"

    Scenario: 合法当前 evidence 使 Release Readiness ready 可达
      Given 当前 Route 的 Release Readiness Gate 已启动
      And 项目存在通过 schema 与语义校验的当前 revision validation evidence
      When 用户执行 "/sbtd gate record release-readiness ready" 并确认
      Then KPi 在记录前重新观测 evidence
      And state service 从持久化的 evidence descriptor 派生 validationVerified
      And Release Readiness Gate 记录为 "passed"

    Scenario: 缺失或失效 evidence 使 Release Readiness ready 被拒绝
      Given 当前 Route 的 Release Readiness Gate 已启动
      And validation evidence 缺失、blocked、failed、stale、mismatch、被篡改或悬挂
      When 用户执行 "/sbtd gate record release-readiness ready" 并确认
      Then KPi 拒绝记录 "ready"
      And 用户看到 evidence 恢复路径

    Scenario: 调用者不能自报 verification
      Given 当前 Route 的 Release Readiness Gate 已启动
      When 调用者试图不经 evidence 观测直接声明 validation 已验证
      Then 命令与 state service 均不接受 caller-supplied verification boolean
      And "ready" 只能由已验证的当前 evidence 派生

    Scenario: 仓库变更后陈旧 Release Readiness ready 不能继续放行
      Given Release Readiness Gate 已因当前 evidence 记录为 "passed"
      When Agent 随后执行写入或编辑生产代码的 Tool Call
      Then KPi 作废已持久化的 evidence descriptor
      And Release Readiness Gate 回到需要重新验证的状态
      And 后续阶段推进或交付不再把旧 "ready" 当作仍有效

    Scenario: PowerShell -Command 包装的依赖安装需要批准
      Given Effective Control State 为 "active"
      When Agent 执行 "powershell -Command \"npm install\"" 或 "pwsh -Command \"Install-Package Newtonsoft.Json\""
      Then KPi 返回 "install-requires-approval" 阻断决定

    Scenario: 正式交付证据必须是同名的新鲜常规文件
      Given 当前 Route 要求正式验证报告
      And 报告目录只包含同名的目录、陈旧文件或不匹配的 Markdown 摘要
      When KPi 评估交付证据
      Then KPi 不把该目录当作正式验证证据
      And KPi 阻断交付并显示报告恢复路径

    Scenario: 无关 .feature 修改不满足 BDD 交付
      Given 当前任务改变用户可见行为
      And 项目只有被触碰的无关 .feature 文件而没有通过校验的 v2 validation evidence
      When KPi 评估交付证据
      Then KPi 不把文件修改时间当作 BDD 证据
      And KPi 阻断交付并显示 BDD 恢复路径

    Scenario: 未修改的既有 Scenario 可通过当前绑定的报告满足追溯
      Given 当前任务改变用户可见行为
      And 项目存在 schema 与语义校验均通过的当前 revision v2 validation evidence
      And 该 evidence 将既有 Scenario 的 source locator 绑定到唯一 passed 测试用例
      When KPi 评估交付证据
      Then KPi 接受该可追溯 BDD 证据
      And 不要求修改任何 .feature 文件

    Scenario: v1 envelope 共存不满足 BDD scenario 追溯
      Given 当前任务改变用户可见行为
      And 项目只有 schemaVersion 1 的 validation evidence envelope
      When KPi 评估交付证据
      Then KPi 不把 v1 featureSources 与 reports 共存当作 scenario 追溯
      And KPi 阻断交付并显示 BDD 恢复路径

    Scenario: 以 .feature 命名的目录永远不是 BDD 证据
      Given v2 validation evidence 的 source locator 指向一个以 ".feature" 结尾的目录
      When KPi 评估交付证据
      Then 语义校验以 "FEATURE_NOT_FILE" fail closed
      And KPi 阻断交付

    Scenario: 陈旧或被篡改的 evidence 不满足 BDD 交付
      Given 当前任务改变用户可见行为
      And v2 validation evidence 的 sourceCommit 与当前 revision 不一致或报告 SHA-256 被篡改
      When KPi 评估交付证据
      Then KPi 拒绝该 evidence
      And KPi 阻断交付并显示 BDD 恢复路径

    Scenario: Specification 可追溯性与执行验证分别报告
      Given 当前任务改变用户可见行为
      When KPi 评估交付证据
      Then KPi 分别报告 specification traceability 与 execution verification 事实
      And 两者不能互相冒充

    Scenario: 非 active 控制状态拒绝工作流阶段请求
      Given Effective Control State 不为 "active"
      When Agent 通过 "sbtd_workflow" 请求进入实现阶段
      Then KPi 拒绝该阶段请求并显示当前控制状态与 recovery path
      And Session 不追加新的 KPi 状态记录


    Scenario: 秘密路径读取在 Host Tool Call 前被阻断
      Given Agent 即将读取一个受保护的 .env 路径
      When OMP 触发 Tool Call 前置事件
      Then KPi 返回 "secret-read-guard" 阻断决定
      And 该读取不会进入 Tool 执行阶段

    Scenario: Tool Call 在执行前被 Hard Rule 阻断
      Given Effective Control State 为 "active"
      And Agent 即将执行会绕过未满足 Hard Gate 的 Tool Call
      When OMP 触发 Tool Call 前置事件
      Then KPi 在工具执行前返回阻断决定与原因
      And 被阻断的 Tool Call 不产生副作用

  Rule: Session 的瞬态工作流状态相互隔离

    Scenario: 缺少稳定 Session ID 的并发 Context 不共享瞬态状态
      Given OMP 同时处理两个无法提供 Session ID 的 Context
      And 一个 Context 已产生 Tool 审批或交付阻断
      When 另一个 Context 执行同类 Tool Call 或交付事件
      Then 另一个 Context 不复用前一 Context 的审批、分类或交付状态
      And 两个 Context 的运行时串行队列彼此独立

    Scenario: 交错 Session 不复用分类或交付阻断
      Given OMP 同时处理多个 Session
      And 一个 Session 已产生用户可见行为的交付阻断
      When 另一个 Session 处理同一 Turn 标识的交付事件
      Then 该 Session 只使用自己的当前任务分类和交付状态
      And 已结束 Session 的瞬态状态不再保留

  Rule: Compaction 与 Resume 恢复选择并重新观测事实

    Scenario: Compaction 保存工作流状态摘要
      Given 当前 Session 已有分类、Route、Book Gate 和 Rule 决策
      When OMP 压缩当前 Session
      Then KPi 保存版本化工作流状态摘要
      And 摘要不把 Effective Control State 当作可恢复选择持久化

    Scenario: Resume 后重新派生控制状态
      Given Session 历史保存 Runtime Mode、Policy Profile、Route 覆盖和工作流状态
      And 恢复时项目事实已经变化
      When OMP Resume 当前 Session
      Then KPi 恢复 Session-owned 选择和兼容版本的工作流状态
      And KPi 重新观测 Environment Mode
      And Effective Control State 由恢复后的 Runtime Mode 与新 Environment Mode 派生
      And 过期的派生控制状态不被复用

    Scenario: 无法恢复有效工作流状态时 fail closed
      Given Session 最新 KPi 状态记录无法通过版本化 schema 校验
      When OMP Resume 当前 Session
      Then KPi 不执行 active-only 自动编排
      And 用户看到损坏状态、repair path 与可恢复的上一条有效记录信息

    Scenario: 无歧义 Draft enabled 与裸 mode 状态迁移到版本一
      Given Session 最新 KPi 状态记录没有 stateVersion
      And 该记录以 enabled 表示 Runtime Mode 并以裸 mode 表示 Policy Profile
      When OMP Resume 当前 Session
      Then KPi 恢复等价的 Runtime Mode 与 Policy Profile
      And KPi 以 stateVersion 一的严格状态继续重新观测环境

    Scenario: 冲突 Draft 状态或未知 stateVersion 保持修复阻断
      Given Session 最新 KPi 状态记录包含互相冲突的 enabled 与 Runtime Mode 或未知 stateVersion
      When OMP Resume 当前 Session
      Then KPi 拒绝该最新记录
      And 用户看到 Session history repair 路径
