Feature: DSH T1 短 sbtd section 与会话状态
  用户需要在每条 DSH 会话的 system / reminder 里看到非空中文 sbtd 短规则，
  且插件不写 AGENTS.md。会话 Book Gate 状态只存在进程内。

  Scenario: apply 注册非空中文 sbtd section
    Given T0 stub 插件已被宿主加载
    When 宿主调用 apply
    Then 系统提示注册名为 "sbtd"、顺序为 50 的 section
    And section 正文为非空中文，且包含 sbtd_plan、sbtd_clarify、sbtd_validate、sbtd_e2e、sbtd_review、Maestro
    And section 正文 UTF-8 不超过 2048 字节
    And 插件不写入 AGENTS.md 或用户磁盘

  Scenario: README 说明短中文 sbtd section
    Given 用户打开 packages/dsh-sbtd 的 README
    Then 文档钉 @deepseek-ai/dsh@0.1.1-rc.2
    And 文档给出 dsh plugin --profile web add @kunolu/dsh-sbtd@next
    And 文档提到短中文 sbtd section
    And 文档不出现裸包名安装或本地路径安装
    And 文档不出现 0.1.0-rc.7 或 0.1.2-alpha
