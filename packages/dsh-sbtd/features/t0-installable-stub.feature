Feature: DSH T0 stub 可安装
  用户需要把 @kunolu/dsh-sbtd 作为 T0 stub 装到 DSH 0.2.0-rc.2，
  加载时只打日志并注册非空中文 sbtd section，不写用户磁盘。

  Scenario: 插件加载时打印 T0 stub 日志并注册非空中文 sbtd section
    Given T0 stub 插件已被宿主加载
    When 宿主调用 apply
    Then 终端出现 "[dsh-sbtd] plugin loaded (T0 stub)"
    And 系统提示注册名为 "sbtd"、顺序为 50、正文为非空中文短规则的 section
    And 插件不写入 AGENTS.md 或用户磁盘

  Scenario: README 钉 0.2.0-rc.2 并说明 @next 安装命令
    Given 用户分别打开 packages/dsh-sbtd 的 README.md 与 README.zh.md
    Then 文档钉 @deepseek-ai/dsh@0.2.0-rc.2
    And 文档给出 dsh plugin --profile web add @kunolu/dsh-sbtd@next
    And 文档不出现裸包名安装或本地路径安装
    And 文档不出现 0.1.0-rc.7 或 0.1.2-alpha

  Scenario: README 区分 docs-only RC 与当前已发布版本
    Given 用户分别打开 packages/dsh-sbtd 的 README.md 与 README.zh.md
    Then 文档说明 0.2.0-rc.2 是尚未发布的 docs-only RC
    And 当前已发布 next 为 0.2.0-rc.1，latest 仍为 0.1.0-rc.1

  Scenario: 双语 README 顶部语言切换钉 release tag 且章节数量一致
    Given 用户分别打开 packages/dsh-sbtd 的 README.md 与 README.zh.md
    Then 两份文档顶部均链接到 https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.md
    And 两份文档顶部均链接到 https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.zh.md
    And 英文与中文文档的二级标题数量相同，三级标题数量也相同

  Scenario: 0.2.0-rc.2 包可发布且标记为 dsh-plugin
    Given 用户检查 packages/dsh-sbtd 的 package.json
    Then private 为 false、version 为 0.2.0-rc.2
    And keywords 包含 dsh-plugin

  @todo
  # blocked: this environment has no dsh CLI
  Scenario: 用本机 dsh CLI 把 stub 装进 web profile
    Given 本机已安装 @deepseek-ai/dsh@0.2.0-rc.2
    When 用户执行 dsh plugin --profile web add @kunolu/dsh-sbtd@next
    Then dump-config 能看到 id: sbtd
