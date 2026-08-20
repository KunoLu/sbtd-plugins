Feature: P0 一致性研究与不可变证据
  发布负责人可以在不调用 Provider 或读取凭据的前提下，复核 P0 的技术一致性、不可变证据和研究决策；这些内部结果不授权 npm RC 或 stable 发布。

  Rule: 每个 P0-E11 要求都保持可单独追踪

    Scenario: 39 个测试矩阵条目都具有稳定证据定位器
      Given P0 发布目录包含版本化的一致性矩阵
      When 发布校验器加载该矩阵
      Then P0-E11-01 到 P0-E11-39 各出现一次
      And 每个条目具有可解析的证据定位器或明确的阻断恢复路径
      And 聚合结果不会隐藏任一编号条目

  Rule: 无法运行的宿主兼容性保持阻断

    Scenario: 不可用的当前 OMP Runtime 兼容宿主不被当作通过
      Given 从当前工作区锁定版本确定的 OMP Runtime 宿主无法在隔离沙箱中启动
      When 发布校验器执行该当前 Runtime 的兼容性检查
      Then 该当前 Runtime 的结果为 "blocked"
      And 报告包含安全的阻断代码和恢复操作
      And 结果不声称已执行 Provider 请求

  Scenario: 已配置的受控宿主 adapter 只接收脱敏协议并验证结果
    Given 发布负责人配置了绝对路径的受控 OMP host adapter
    When 发布校验器向 adapter 发送一个隔离兼容性或价值研究请求
    Then adapter 只接收受限的 JSON 请求和最小环境变量
    And 非法、敏感或多余的 adapter 输出使该检查保持 "blocked"
    And 有效的 adapter 结果仍须通过既有兼容性或价值研究证据校验


  Scenario: 精确 tarball 依赖解析安装后的四个只读命令不调用模型
    Given 发布负责人提供一个已解压的打包 Plugin 目录和匹配的精确 tarball
    And 受控 OMP host 在任务专属的隔离 HOME 中安装该 tarball
    When 发布校验器在受控宿主中执行兼容性检查
    Then "/sbtd help"、"/sbtd status"、"/sbtd report" 和 "/sbtd onboard plan" 都完成
    And 每个命令都保留 "agentInvoked" 为 false
    And 受控宿主不会执行 Provider 请求或保留 tarball 以外的 Plugin 依赖来源

  Rule: 显式实验 Runtime 检查不扩展已声明支持

    Scenario: 发布负责人验证未声明 Runtime 的已打包 Plugin
      Given 兼容性清单仍声明 OMP Runtime "17.3.5"
      And 发布负责人提供一个已解压的 Plugin 包目录和匹配的精确候选 tarball
      When 发布负责人以相同的实验 Runtime 和检查 Runtime "17.1.8" 运行兼容性命令
      Then 受控宿主接收 Runtime "17.1.8"、该已打包 Plugin 目录和该精确候选 tarball
      And 机器可读结果标记该检查为 "experimental"
      And 结果同时保留声明 Runtime "17.3.5" 与检查 Runtime "17.1.8"
      And 兼容性清单和公开支持声明保持不变

    Scenario: 未声明 Runtime 需要显式实验授权
      Given 兼容性清单仍声明 OMP Runtime "17.3.5"
      When 发布负责人仅以检查 Runtime "17.1.8" 运行兼容性命令
      Then 命令以非零状态和结构化 "CURRENT_RUNTIME_MISMATCH" 错误失败
      And 受控宿主不会收到兼容性请求

    Scenario Outline: 实验 Runtime 参数错误时兼容性命令失败关闭
      Given 兼容性清单仍声明 OMP Runtime "17.3.5"
      When 发布负责人以 <错误参数> 运行实验兼容性命令
      Then 命令以非零状态和结构化参数错误失败
      And 受控宿主不会收到兼容性请求

      Examples:
        | 错误参数 |
        | 不同的实验 Runtime 与检查 Runtime |
        | 非语义版本的实验 Runtime |
        | 缺少检查 Runtime |
        | 缺少已打包 Plugin 目录 |


  Rule: 显式认证 profile 保持隔离和零泄漏

    Scenario: 发布负责人显式授权专用 OMP profile
      Given 发布负责人已通过官方 OMP 登录创建任务所有且可丢弃的验证 profile
      When 发布负责人为兼容性检查显式提供该 profile
      Then 受控宿主只接收该 profile 与 PATH
      And 私有环境变量、凭据和 profile 路径不会进入公共结果
      And 兼容性子进程使用其余隔离的项目、HOME 与缓存目录

    Scenario: 可丢弃 profile 的变更生成 profile-isolated 证据
      Given 一个已授权的任务所有且可丢弃验证 profile 在兼容性检查期间发生变化
      When 发布负责人运行兼容性检查
      Then 检查成功结果标记为 "profile-isolated"
      And 结果保留 "agentInvoked" 为 false 和 caller-supplied sandbox 的零写入证明
      And 不会产生可用于公开支持声明的兼容性通过证据

    Scenario: 无效的受控认证 profile 在启动 OMP 前失败关闭
      Given 发布负责人提供不存在或符号链接的验证 profile
      When 发布负责人运行兼容性检查
      Then 检查返回结构化 "OMP_HARNESS_COMPAT_AGENT_DIR_INVALID" 阻断
      And OMP Runtime 进程不会启动

    Scenario: 仅本地命令的兼容性检查不等待隐式本地 Provider 发现
      Given 发布负责人使用专用 OMP profile 和已打包 Plugin 验证实验 Runtime
      When 受控兼容性子进程启动只读 "/sbtd" 命令检查
      Then 检查不会等待不可用的隐式本地 Provider 发现
      And 已打包 Plugin、专用 profile、caller-supplied sandbox 与用户配置保持不变
      And 子进程在不调用 Provider 的前提下完成 "help"、"status"、"report" 与 "onboard plan"

  Rule: 打包内容的身份和归属必须完整

    Scenario: SBOM 或许可证通知漂移时包检查失败关闭
      Given 打包 Plugin 的许可证、第三方通知或 SPDX SBOM 与已验证清单不一致
      When 发布校验器检查实际 tarball 内容
      Then 包检查结果为 "failed"
      And 报告列出漂移的文件和修复操作
      And 上游第三方许可证与 NOTICE 仍保持在保留路径

    Scenario: 删除的 Onboard 源文件不能以陈旧 dist 产物进入 tarball
      Given Plugin 的当前 TypeScript 源树不再包含一个 Onboard bridge
      And 上一次编译留下该 bridge 的 JavaScript、声明或 source-map 文件
      When 发布负责人构建或校验 Plugin 发布内容
      Then 编译前跨平台清理 dist
      And 每个保留的 dist 文件都能映射到当前 TypeScript 源文件
      And 校验器以结构化 "PACKAGE_CONTENT_INVALID" 拒绝未映射的陈旧 bridge 产物
      And SBOM 与候选 tarball 不能把该产物自洽地提升为可发布内容

    Scenario: 已打包的 Projection 保留项目与 retained Skill 的忽略规则
      Given 一个包含 Onboard 项目模板和 retained OMP-compatible Skill 的 Plugin tarball
      When 使用 tarball 内的 Onboard 工具初始化项目和 Skill
      Then 项目收到预期的 ".gitignore" 规则
      And retained Skill 保留其 ".gitignore" 规则
      And 项目与 retained Skill 的安装目标中不遗留中性模板文件名
      And bundled self-Onboard 保留可用于重复初始化的中性模板

  Rule: 发布身份绑定受控 npm scope

    Scenario: 已支持的 Plugin 只声明 kunolu scope
      Given 当前 OMP Plugin 的包清单和发布候选身份
      When 发布负责人检查可安装包名
      Then 包名为 "@kunolu/omp-sbtd"
      And 旧 "@kpi/omp-sbtd" 不会被声明为当前可发布身份
      And 包检查继续绑定该精确包名、版本和 tarball 摘要

  Rule: 完整且相互独立的配对研究才能产生可提升的价值证据

    Scenario: 完成的 20 个配对研究提升经过验证的规范证据
      Given 一个冻结的 20 个价值研究 fixture 语料
      And 每个 fixture 都具有一个已接受的 control arm 和 treatment arm 结果
      And 研究记录具有恰好 40 个 arm 结果和 20 个盲评结果
      And 所有固定资源限制、重试谱系、来源摘要和阈值均通过验证
      When 发布校验器重新计算研究评分并提升该运行
      Then 规范证据保留每个 arm 和盲评的摘要及摘要绑定
      And 最新完整证据指针指向这个不可变运行
      And 原始事件、接受工件内容和本地路径不会进入规范证据

    Scenario: 盲评与执行保持模型和进程独立
      Given 一个包含同一冻结 fixture 两个 arm 结果的待评估配对
      When 独立 Judge 对随机化且已掩码的配对进行评分
      Then Judge 只接收接受工件、工件摘要和冻结 rubric
      And Judge 不接收 arm 标签、运行模式、Route、Gate、Session、Provider、路径或用量元数据
      And 执行与 Judge 使用不同的固定模型标识和进程标识
      And Judge 结果绑定两个接受工件摘要和自身评分摘要

  Rule: 不完整、伪造或有污染的配对证据不能建立价值结论

    Scenario: Judge 响应必须逐项绑定冻结 rubric
      Given 一个待盲评的掩码配对和对应的冻结 rubric
      When 独立 Judge 返回缺失、重复、额外准则或与 rubric 权重不一致的评分
      Then 价值研究执行结果保持 "blocked"
      And 报告指出 Judge 响应未满足严格契约
      And 不会创建或更新规范运行、最新指针或批准指针

    Scenario: 不完整或非独立的配对研究保持阻断
      Given 一个价值研究缺少一个 arm、独立 Judge 或完整的重试记录
      When 发布校验器评分该研究
      Then 价值 Gate 为 "blocked"
      And 不会更新最新完整证据指针
      And 原始事件仍只保留在本地临时目录

    Scenario: 摘要绑定被篡改的配对研究保持阻断
      Given 一个形式完整的 20 对价值研究记录
      And 一个 arm 接受工件摘要、盲评摘要或来源摘要与其绑定记录不一致
      When 发布校验器重新验证该研究
      Then 价值 Gate 为 "blocked"
      And 不会创建或覆盖规范运行、最新指针或批准指针

    Scenario: 不可追溯的完整评分输入不能宣称价值 Gate 通过
      Given 一个手工构造但形式完整的 20 对价值研究评分输入
      And 该输入没有控制器产生的不可变完成来源证明
      When 发布负责人运行评分命令
      Then 命令结果保持 "blocked"
      And 报告要求父级授权的完整研究执行和证据提升
      And 不会更新当前规范证据或批准指针


  Rule: 预检只授权显式的完整研究

    Scenario: 已就绪的预检不使未执行的聚合检查通过
      Given 一个受控 OMP host 已确认执行模型和独立 Judge 预检就绪
      And 尚未记录完整的 40 个 arm、20 次盲评和不可变研究证据
      When 发布负责人运行不请求研究执行的综合校验
      Then 命令结果保持 "blocked"
      And 报告保留预检就绪事实和完成研究的恢复操作
      And 不会更新当前规范证据或批准指针

  Rule: 授权 RPC harness 保持执行与盲评分离

    Scenario: 固定 Runtime 和模型只通过隔离的 OMP RPC 执行
      Given 发布负责人提供精确 Runtime、打包 Plugin、执行模型和不同的 Judge 模型标识
      When 授权 harness 执行一个 control arm、一个 treatment arm 和对应盲评
      Then 每个 arm 使用独立 Session 并分别验证 advisory 或 enforced 状态
      And 执行过程只能访问隔离工作区和静态文件工具，不能执行模型请求的验证进程
      And Judge 只接收随机化验收产物和冻结 rubric 且不能使用工具
      And harness 输出不包含凭据、Provider 私有元数据、绝对开发者路径或未约束的原始 RPC

    Scenario: 不安全的模型输出不能越过 RPC harness
      Given Runtime 请求执行模型生成的验证目标、写入越过隔离工作区的符号链接，或在公共命令输出中返回通用绝对本地路径、file URI 和裸 token
      When 授权 harness 处理该 arm 的公共 RPC
      Then arm 结果保持 "blocked"
      And 不会执行模型生成的验证代码或跟随写入、精确替换的最终符号链接
      And 公共输出、adapter 交换、规范证据候选和报告都不包含该路径、file URI 或 token

  Rule: P0 研究就绪需要技术和价值 Gate 同时通过

    Scenario: 较新的阻断运行使旧批准证据不再代表当前 P0 研究就绪状态
      Given approved.json 指向一个旧的通过运行
      And latest.json 指向同一来源快照的较新阻断运行
      When 发布校验器决定当前 P0 研究状态
      Then 发布决定为 "blocked"
      And 报告指出最新运行的阻断原因
      And 不会将旧批准证据解释为当前 P0 研究就绪

  Rule: P0 候选协议证据只可在 P0 研究内通过精确候选等价证明服务稳定候选

    Scenario: 通过当前技术和包检查的不可变预发布候选具备内部 P0 RC 资格
      Given 一个包含来源摘要、打包 tarball 摘要、包名和预发布版本的候选
      And 该候选的当前技术一致性和打包包检查都为 "passed"
      When 发布校验器决定该候选状态
      Then 决定为 "rc-eligible"
      And 该结果只表示内部 P0 候选资格，不授权 npm 发布
      And 非预发布版本或 "latest" dist-tag 不能作为 RC 资格证据

    Scenario: 较新的非通过候选 Gate 证据保持失败关闭
      Given 一个 RC 候选已有较早的通过技术 Gate 证据
      And 同一候选具有较新的阻断技术 Gate 证据
      When 发布校验器决定该候选状态
      Then 决定为 "blocked"
      And 较早的通过证据不能掩盖当前阻断

    Scenario: 受控 CLI 记录精确 RC 候选及其不可变 Gate 证据
      Given 发布负责人在本地临时证据目录中准备一个已解压的打包 RC Plugin 和对应 tarball
      And 候选命令从当前已验证的 Plugin 清单和 tarball 字节导出精确候选身份
      And 候选技术证据命令重新执行矩阵中所有可执行的 "automated" 技术要求，并显式保留外部、手工或阻断项
      When 发布负责人依次运行候选记录命令、两个候选证据记录命令和候选决定命令
      And 候选决定为 "rc-eligible"
      And 命令不会读取凭据、调用 Provider、接受调用者提供的 Gate 状态或覆盖已有证据

    Scenario: RC 候选拒绝不一致、歧义、不安全或含泄漏载荷的 tarball
      Given 发布负责人在本地临时证据目录中准备一个已解压的打包 RC Plugin
      And 所提供的 tarball 与该解压目录不一致、含链接成员、重复成员或文件与目录同名
      Or tarball 成员包含绝对路径、反斜杠、空段、"." 或 ".." 段
      Or tarball 任一原始 regular payload 或路径以大小写不敏感方式匹配 "codex"，唯一例外是 "package/kit/onboard/runtime/scripts/onboard.py" 成员且其字节 SHA-256 与同一 tarball 内 "package/kit/manifest.json" 的 assets["onboard/runtime/scripts/onboard.py"] 声明完全一致
      When 发布负责人运行候选记录命令
      Then 命令以非零退出码和结构化 "CANDIDATE_TARBALL_MISMATCH"、"CANDIDATE_TARBALL_INVALID" 或 "OMP_DISTRIBUTION_LEAKAGE" 错误失败
      And 归档检查逐一验证 raw member 而不依赖解包覆盖结果
      And 该 canonical 例外在清单缺失、未声明该成员或声明摘要与成员字节不匹配时失效，成员按普通泄漏载荷拒绝
      And 诊断只定位相对成员路径和匹配计数，不输出原始载荷
      And 不创建候选记录或候选 Gate 证据

    Scenario: 冲突的候选重新记录保持失败关闭
      Given 一个精确 RC 候选已经具有不可变候选记录
      When 发布负责人尝试以相同候选身份记录不同的 channel、dist-tag 或时间戳
      Then 命令以非零退出码和结构化 "CANDIDATE_ALREADY_EXISTS" 错误失败
      And 原始候选记录和已绑定证据保持不变

    Scenario: 观察记录不能提升任何发布 Gate
      Given 一个候选只具有脱敏且追加写入的试用观察记录
      When 发布校验器决定该候选状态
      Then 决定为 "blocked"
      And 观察记录不会改变技术、包、兼容性或价值 Gate

    Scenario: 仅解析并验证封闭候选元数据差异可以建立候选等价证明
      Given 一个 RC 包和稳定包的所有打包文件映射相同
      And 校验器逐项验证 package manifest 名称/版本、SPDX 文档名称/包版本、候选来源身份 namespace 和绑定对应 package manifest 字节的 SHA-256
      And 除这些封闭字段中按各候选身份规范化的字节外，所有打包字节均相同
      When 发布校验器验证 RC 到稳定候选的等价证明
      Then 证明绑定这两个精确候选和规范化载荷摘要
      And 该证明可以作为该稳定候选复用 RC 协议证据的唯一依据

    Scenario: 新增、删除、重排、不可解析或不透明的打包内容差异不能建立候选等价证明
      Given 一个 RC 包和稳定包存在新增、删除、重排、不可解析或未被允许的字节差异
      When 发布校验器验证候选等价证明
      Then 证明结果为 "blocked"
      And 该 RC 的协议证据不能提升稳定候选的任何 Gate

    Scenario: 候选绑定不允许跨 RC 或跨稳定包复用协议证据
      Given 一个完整 RC 协议证据和一个不匹配的 RC 或稳定候选
      When 发布校验器决定该稳定候选状态
      Then 决定为 "blocked"
      And 报告指出精确候选绑定缺失并给出恢复操作

    Scenario: 已证明等价的当前 Runtime RC 兼容性证据可满足匹配稳定候选的兼容性 Gate
      Given 一个 RC 候选具有同一打包工件上的当前 Runtime 兼容性结果
      And 该结果绑定从当前已安装环境确定的精确 Runtime 版本
      And 该 RC 与一个稳定候选具有有效的精确候选等价证明
      When 发布校验器决定该稳定候选状态
      Then 匹配稳定候选的兼容性 Gate 可以使用该 RC 结果
      And 其他候选不能使用该结果

    Scenario: 已证明等价的完整 40 arm 和 20 对 RC 价值研究可满足匹配稳定候选的价值 Gate
      Given 一个 RC 候选具有同一打包工件上的完整 40 arm 和 20 对独立价值研究
      And 该 RC 与一个稳定候选具有有效的精确候选等价证明
      When 发布校验器决定该稳定候选状态
      Then 匹配稳定候选的价值 Gate 可以使用该 RC 价值证据
      And 观察记录不能替代该完整研究

    Scenario: 稳定候选始终重新运行技术和打包包检查
      Given 一个稳定候选具有有效的 RC 候选等价证明和可转发的协议证据
      And 该稳定候选缺少当前技术一致性或打包包检查
      When 发布校验器决定该稳定候选状态
      Then 决定为 "blocked"
      And 报告要求对该精确稳定候选重新运行缺少的 Gate
