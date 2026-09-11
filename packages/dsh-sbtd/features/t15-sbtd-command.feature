Feature: DSH T15 /sbtd 人类命令
  人类通过 ctx.commands 使用 /sbtd，而不是模型 tool。
  仅三个形式：裸 /sbtd、/sbtd plan、/sbtd maestro。

  Scenario: apply 注册人类 sbtd 命令且不注册同名模型 tool
    Given 宿主已加载 dsh-sbtd
    When 宿主调用 apply
    Then inject 含 commands
    And ctx.commands 注册名为 sbtd 的人类命令
    And tools 列表没有名为 sbtd 的模型 tool

  Scenario: 空会话裸 /sbtd 只读 no-plan 且给出 maestro missing
    Given 会话尚无 Book Gate Plan
    When 人类输入 /sbtd
    Then 输出含 no-plan
    And 输出含 maestro missing
    And 不创建 plan
    And 不安装 JDK 或 Maestro

  Scenario: 有 plan 时裸 /sbtd 打印该 plan 与 maestro missing
    Given 会话已有 Book Gate Plan
    When 人类输入 /sbtd
    Then 输出含该 plan 的 taskId 与 summary
    And 输出含 maestro missing 摘要
    And 不改写 plan

  Scenario: /sbtd plan 只查看会话 plan 不创建
    Given 会话可有可无 plan
    When 人类输入 /sbtd plan
    Then 无 plan 时输出 no-plan
    And 有 plan 时只打印 Book Gate Plan
    And 输出不含 maestro missing
    And 命令模块不调用 sbtdPlan

  Scenario: /sbtd maestro 复用 T12 preflight 且不静默安装
    Given 宿主可注入 preflight
    When 人类输入 /sbtd maestro
    Then 只调用注入的 preflight
    And 不执行 maestro test
    And 不静默安装

  Scenario: 拒绝命令名别名、前导斜杠别名与多余参数
    Given 人类命令只接受空输入、plan、maestro 三个 rawInput
    When rawInput 为 sbtd、/sbtd、/plan、/maestro、plan x 或 maestro anything
    Then 命令以 unknown subcommand 失败
    And 用法提示 /sbtd | /sbtd plan | /sbtd maestro
