Feature: Hybrid Plugin M2 组包
  维护者需要从 clean worktree 打出同时携带 Portable Capability Layer
  （根 plugin.json 与根 skills/**）和 OMP Runtime Control Plane 的
  Hybrid Plugin tarball，且 manifest 版本、certified skills 数量与
  digest 都绑定 Workflow Kit 第三树的当前 certified set。

  Rule: 根 plugin.json 必须符合 Agent Plugins schema 1.0.0

    Scenario: 根 manifest 通过 schema 1.0.0 校验且版本与 package.json 一致
      Given Plugin 根目录存在 "plugin.json"
      When 维护者运行 manifest 校验
      Then "$schema" 精确为 Agent Plugins 1.0.0 schema URL
      And "name" 为 "omp-sbtd"
      And "version" 与 "package.json" 的 "version" 完全一致且为 "0.1.0-rc.12"
      And description、license、keywords、homepage、repository 字段类型合法

    Scenario Outline: 非法 manifest 形状被校验拒绝
      Given Plugin 根目录存在 "plugin.json"
      When 维护者校验一个 <非法形状> 的 manifest
      Then 校验失败并说明拒绝原因

      Examples:
        | 非法形状 |
        | "$schema" 指向其他版本 |
        | 含非标准顶层字段 |
        | 缺少必填标准字段 |
        | "name" 不是 "omp-sbtd" |
        | "version" 与 package.json 漂移 |
        | description 不是字符串 |
        | keywords 不是字符串数组 |

  Rule: 根 skills/** 是 certified 投影的 digest 校验副本

    Scenario: 组包把 certified set 复制到根 skills 目录
      Given Workflow Kit 第三树清单声明当前 certified set
      When 维护者运行 Plugin 组包
      Then 根 "skills/" 下每个目录名等于一个 certified skill 名
      And 目录数量等于清单的 certifiedCount
      And 每个文件字节与第三树投影一致且 digest 匹配清单
      And 复制结果不含符号链接

    Scenario: onboard-owned 与 explicit non-candidates 不进根 skills
      When 维护者检查组包后的根 "skills/" 目录
      Then "trellis-workflow" 不出现
      And "sbtd-workflow-onboard" 不出现
      And "trellis-channel" 不出现

    Scenario Outline: 投影漂移或手改使检查失败
      Given 根 "skills/" 已由组包生成
      When 维护者对投影施加 <漂移>
      And 运行投影校验
      Then 校验以非零结果失败并指出漂移位置

      Examples:
        | 漂移 |
        | 手改某个 SKILL.md 的一个字节 |
        | 删除一个 certified skill 目录 |
        | 添加一个非 certified 目录 |
        | 把某个文件换成符号链接 |

    Scenario: certified skill 名含路径穿越时校验失败
      Given Workflow Kit 第三树清单声明当前 certified set
      When 维护者校验一个 certified 名为 "../x" 的投影清单
      Then 校验以非零结果失败并指出不安全的 skill 名
      And 组包不得把文件写到根 "skills/" 目录之外

  Rule: Plugin 作用域 pack 断言保护 tarball 形状

    Scenario: clean pack 的 tarball 通过 manifest/skill/containment gate
      Given Plugin 已完成构建且版本冻结为 "0.1.0-rc.12"
      When 维护者在 Plugin 作用域执行 pack 到隔离目录
      Then tarball 含 "plugin.json" 且通过 schema 1.0.0 校验
      And tarball 内 "plugin.json" 的 version 与 packed package.json 一致
      And tarball 内 "skills/" 数量等于 certifiedCount
      And tarball 内每个 skill 文件 digest 与第三树清单一致
      And tarball 不含 "commands/"、"hooks/"、"tools/"、"runtime/" 目录
      And tarball 不含 "mcp.json"

  Rule: Kit embed 边界不因 M2 改变

    Scenario: kit 目录仍只嵌入 generated-omp 投影
      When 维护者对比 Plugin 的 "kit/" 与 Kit 的 "generated-omp/"
      Then 两棵树字节一致
      And "generated-agent-plugin/**" 不出现在 "kit/" 内
