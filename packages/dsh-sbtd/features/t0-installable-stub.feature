Feature: DSH T0 stub 可安装
  用户需要把 @kunolu/dsh-sbtd 作为 T0 stub 装到 DSH 0.1.1-rc.2，
  加载时只打日志并注册非空中文 sbtd section，不写用户磁盘。

  Scenario: 插件加载时打印 T0 stub 日志并注册非空中文 sbtd section
    Given T0 stub 插件已被宿主加载
    When 宿主调用 apply
    Then 终端出现 "[dsh-sbtd] plugin loaded (T0 stub)"
    And 系统提示注册名为 "sbtd"、顺序为 50、正文为非空中文短规则的 section
    And 插件不写入 AGENTS.md 或用户磁盘

  Scenario: README 钉 0.1.1-rc.2 并说明 @next 安装命令
    Given 用户打开 packages/dsh-sbtd 的 README
    Then 文档钉 @deepseek-ai/dsh@0.1.1-rc.2
    And 文档给出 dsh plugin --profile web add @kunolu/dsh-sbtd@next
    And 文档不出现裸包名安装或本地路径安装
    And 文档不出现 0.1.0-rc.7 或 0.1.2-alpha

  @todo
  # blocked: this environment has no dsh CLI
  Scenario: 用本机 dsh CLI 把 stub 装进 web profile
    Given 本机已安装 @deepseek-ai/dsh@0.1.1-rc.2
    When 用户执行 dsh plugin --profile web add @kunolu/dsh-sbtd@next
    Then dump-config 能看到 id: sbtd
