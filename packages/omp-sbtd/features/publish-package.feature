Feature: 安全发布 OMP Plugin
  发布负责人需要以受限访问令牌发布新构建的 Plugin tarball，同时不泄露或持久化凭据。

  Rule: 随包产品信息与文档可从实际 tarball 到达

    Scenario: 包 metadata 包含仓库、问题追踪与主页链接
      When 发布负责人生成 Plugin tarball
      Then 包 metadata 的 repository 为 "https://github.com/KunoLu/sbtd-plugins.git"
      And 包 metadata 的 bugs 为 "https://github.com/KunoLu/sbtd-plugins/issues"
      And 包 metadata 的 homepage 为 "https://github.com/KunoLu/sbtd-plugins"

    Scenario: 安全报告政策随包可达
      When 发布负责人生成 Plugin tarball
      Then tarball 包含 SECURITY 政策文件
      And 该文件指引敏感漏洞通过 "songlin.lu@neox-inc.com" 私密报告
      And 该文件禁止敏感漏洞提交公开 Issue

    Scenario: 产品变更记录与支持声明随包可达
      When 发布负责人生成 Plugin tarball
      Then tarball 包含 Plugin 自己的 changelog 与迁移说明
      And 随包文档声明 RC 无正式 SLA 且非敏感支持使用 GitHub Issues
      And 随包文档包含 telemetry/data-handling 声明
      And 随包 README 包含可执行的 uninstall/rollback 摘要并链接完整 host acceptance 文档

  Rule: 发布前必须验证本地输入

    Scenario: 缺少 npm access token 时发布被拒绝
      Given 发布负责人没有设置 "NPM_TOKEN"
      When 发布负责人运行 Plugin 发布脚本
      Then 脚本以非零状态退出并说明需要 "NPM_TOKEN"
      And 脚本不会调用 npm publish

    Scenario Outline: 无效的发布输入在调用 npm 前被拒绝
      Given 发布负责人设置了合格的 "NPM_TOKEN"
      When 发布负责人使用 <输入> 运行 Plugin 发布脚本
      Then 脚本以非零状态退出并给出可操作的错误
      And 脚本不会调用 npm publish

      Examples:
        | 输入 |
        | 不存在的 tarball 路径 |
        | 非 tarball 文件 |
        | 损坏的 .tgz 文件 |
        | 不合法的发布标签 |
        | 非 "next" 的发布标签 |
        | 非预发布 Plugin tarball |
        | 非 @kunolu/omp-sbtd 的 tarball |
        | Registry 中已存在的版本 |
        | 无法确认 Registry 版本可用性 |
  Rule: RC 发布只接受不可变候选

    Scenario: 仅未占用的预发布 Plugin 可发布到 next
      Given 发布负责人已完成精确 tarball 的本地四个只读命令验收
      And tarball 的包名是 "@kunolu/omp-sbtd" 且版本是预发布版本
      And npm Registry 明确表示该精确版本不存在
      When 发布负责人使用 "next" 标签运行 Plugin 发布脚本
      Then 脚本以 public access 发布到 npm Registry
      And npm 只通过临时 userconfig 接收令牌引用
      And Registry 可用性查询不会收到令牌
      And 脚本输出、仓库文件和残留 userconfig 都不包含令牌值

    Scenario: 根目录 .env 中的 NPM_TOKEN 优先于继承环境变量
      Given 发布仓库根目录的 ".env" 包含非空的 "NPM_TOKEN"
      And 继承环境变量也包含不同的 "NPM_TOKEN"
      When 发布负责人运行 Plugin 发布脚本
      Then npm 使用 ".env" 中的 "NPM_TOKEN"

    Scenario: 空的 .env NPM_TOKEN 回退到继承环境变量
      Given 发布仓库根目录的 ".env" 中 "NPM_TOKEN" 为空
      And 继承环境变量包含非空的 "NPM_TOKEN"
      When 发布负责人运行 Plugin 发布脚本
      Then npm 使用继承环境变量中的 "NPM_TOKEN"

    Scenario: .env 中的非 token 内容不会被执行
      Given 发布仓库根目录的 ".env" 包含非 token 的 shell 内容
      When 发布负责人运行 Plugin 发布脚本
      Then 非 token 内容不会执行

    Scenario: 根目录 .env 符号链接被拒绝
      Given 发布仓库根目录的 ".env" 是符号链接
      When 发布负责人运行 Plugin 发布脚本
      Then 脚本以非零状态退出并说明 ".env" 不能是符号链接
      And 脚本不会调用 npm publish


  Rule: 令牌只通过受控环境传递

    Scenario: 使用环境变量发布新的 tarball
      Given 发布仓库根目录不存在 ".env"
      And 发布负责人已构建新的 "0.1.0-rc.11" Plugin tarball
      And "NPM_TOKEN" 是具有发布权限且满足账户二次验证策略的 automation token
      When 发布负责人使用 "next" 标签运行 Plugin 发布脚本
      Then 脚本以 public access 发布到 npm Registry
      And npm 只通过临时 userconfig 接收令牌引用
      And 脚本输出、仓库文件和残留 userconfig 都不包含令牌值
