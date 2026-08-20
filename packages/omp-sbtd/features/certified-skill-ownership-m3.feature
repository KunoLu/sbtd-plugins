Feature: Certified Skill 所有权切交（M3）
  维护者需要 certified set（根 skills/** 的 12 个 portable Skills）只由
  Agent Plugins 路径拥有：Onboard 不再把 certified 名拷进全局 skills 目录，
  Runtime 证据改从包内 portable set 读取，cleanup 只删除已证明的
  Onboard-managed 旧副本且可回滚，Doctor 分开报告 packaged 与
  source-unverified 的 discovered。版本保持 0.1.0-rc.12。

  Rule: Onboard 不再安装或再加载 certified 名

    Scenario: OMP Onboard catalog 不再把 certified 名列为 bundled copy 来源
      Given Workflow Kit 的 OMP catalog overlay
      When 维护者重新生成 generated-omp 并重新嵌入 kit
      Then catalog 不含任何 certified 名的 bundled-skill 条目
      And "trellis-workflow"、"trellis-channel"、"sbtd-workflow-onboard" 仍为 bundled 条目
      And 12 个 external stable 条目保持不变
      And "kit/onboard/runtime/catalog.json" 与 "generated-omp" 字节一致

    Scenario: Runtime 证据从包内 portable set 读取 certified Skills
      Given 全局 skills 目录不含任何 certified Skill
      When Runtime 观察 core-gate-skills 与 route 相关 Skill 能力
      Then 认证 Skill 的安装事实来自包内 "skills/**"
      And 非 certified 名（trellis-workflow、tdd、ui-ux-pro-max）仍读全局目录

  Rule: Cleanup 只删除已证明的 Onboard-managed certified 旧副本

    Scenario: digest 匹配的 certified 旧副本被备份后删除
      Given 全局 skills 目录中存在内容与当时 Kit bundled source 逐字节一致的 certified 名目录
      When 用户确认 composite Onboard apply
      Then 该目录被移入 cleanup 备份区
      And 结果报告备份路径作为回滚入口

    Scenario: 同名但内容不匹配的目录必须保留并报冲突
      Given 全局 skills 目录中存在内容被用户修改过的 certified 名目录
      When 用户确认 composite Onboard apply
      Then 该目录保持原样、零写入
      And Doctor 将该名列入 certified 同名冲突

    Scenario: 符号链接或非目录同名目标不得删除
      Given 全局 skills 目录中的 certified 名是符号链接
      When 用户确认 composite Onboard apply
      Then 该目标保持原样并被记为冲突

    Scenario: cleanup 中途失败时回滚已移动的目录
      Given 多个已证明的 certified 旧副本
      When 备份移动在中途失败
      Then 已移动的目录被恢复回全局 skills 目录
      And 结果报告 failed 且不留下部分删除

    Scenario: 无 certified 旧副本时 cleanup 为零写
      Given 全局 skills 目录没有任何 certified 名目录
      When 用户确认 composite Onboard apply
      Then cleanup participant 报告 not-required
      And 没有任何文件写入

    Scenario: Project 范围 Onboard 不触碰全局 certified 旧副本
      When 维护者执行 project-only Onboard
      Then certified cleanup 不参与且不检查全局 skills 目录

    Scenario: cleanup 不因外部 Skills installer 失败而推迟
      Given 存在 digest 匹配的 certified 旧副本
      And 外部 stable Skills installer 将会失败
      When 用户确认 full-scope composite Onboard apply
      Then leftover 在 installer 被调用之前已经搬走
      And cleanup participant 为 applied 并报告回滚路径

    Scenario: 未批准 managed-files 时不搬走 leftover
      Given 存在 digest 匹配的 certified 旧副本
      When 用户未批准 managed-files 就 Apply
      Then leftover 保持原样
      And cleanup participant 为 skipped-not-approved

    Scenario: 无效 packaged certified 名不得回落到全局 leftover
      Given packaged inventory 将某 certified 名列为 invalid
      And 全局目录存在同名 leftover
      When Runtime 观察该 Skill 的安装事实
      Then 不得把全局 leftover 当作已安装

  Rule: Doctor 分开报告 packaged、discovered 与冲突

    Scenario: Doctor 输出 Agent Plugins §22 字段
      When 用户运行 "/sbtd doctor"
      Then 输出包含 Agent Plugin schema "1.0.0"
      And manifest 状态为 valid、invalid 或 missing 之一
      And packaged 计数来自包内 "skills/**" 清点而非 plugin.json
      And 包含 packaged digest
      And 包含 invalidSkills 列表
      And 包含 portable MCP 状态
      And 包含 OMP runtime extension 状态

    Scenario: Host 无法证明 resolved source 时 Doctor 报 source-unverified
      Given 当前 Host 扩展 API 不提供 Agent Plugins discovery 事实
      When 用户运行 "/sbtd doctor"
      Then discovered 输出 "source-unverified"
      And 不得把 runtime policy registry 的条目计入 discovered

    Scenario: 同名冲突出现在 Doctor 输出中
      Given 全局 skills 目录存在未证明的 certified 同名目录
      When 用户运行 "/sbtd doctor"
      Then 冲突名出现在 Doctor 输出中且注明该目录被保留

    Scenario: 环境观察失败时 Doctor 仍输出 Agent Plugin 块
      Given Onboard 环境观察失败
      When 用户运行 "/sbtd doctor"
      Then 输出仍包含 Agent Plugin schema 与 packaged 清点

  Rule: Runtime policy registry 只是策略映射

    Scenario: registry 覆盖且仅覆盖 packaged certified set
      Given 包内 "skills/**" 的 certified 清点
      When 读取 runtime policy registry
      Then registry 条目名集合与 packaged certified 名集合完全一致

    Scenario: registry 的 route 与 gate 映射与 Runtime 常量一致
      When 对比 registry 与 routeRequiredCapabilities、optionalCapabilitySkills、coreGateSkillNames、bookGateIds
      Then registry 不引入任何未知 route 或 gate
      And 承担 route 能力的 certified Skill 在 registry 中带有相同 route 映射
      And 5 个 core gate Skills 各自映射到对应 Book Gate
