# PR #110 审查修正

基线：ac34ee4f009ea0fe6aa6dde46e2fdadbe28e70a1。用户最初要求修复最终保留的19项；补充复核后，用户明确选择“保留现有契约并纠正审查”，排除R03/R09/R11/R12的行为变更：实际修复15项，其余4项保留原契约并补充说明/证据。沿用strict，允许更新草稿PR及CI；禁止合并、发布、sync、真实HOME应用或旧资产清理。原始完成事件及失败证据保留，本任务已重新打开。

未完整调用grill-with-docs：15项修复及4项保留边界已明确，无新领域歧义。BDD正文中文、Given/When/Then英文，放在Markdown，不生成.feature。测试seam沿用公开CLI、build_inventory、host资源/render/verify及引擎公开upgrade/recovery；内部协议/文件故障注入只证明对应边界，不冒充真实host。

## 持久修正场景

| ID | Given / When / Then |
|---|---|
| R01 | Given带UTF-16 LE／BE BOM的PowerShell profile；When生成替换候选；Then写前拒绝，原件字节保持，不自动转码 |
| R02 | Given某资源已写入且后续持久化失败；WhenCLI返回；Then状态区分前置block与写后failed/partial，提供绑定本批的最后checkpoint/备份位置和不确定性 |
| R03（排除行为变更） | Given选中但不存在的host资源；When计划/应用；Then仍按既有契约安装；preserve用于既有差异，不新增“保持缺失”策略 |
| R04 | GivenCodex config不是config_home/config.toml；Whenplan；Then写前拒绝，不对未加载文件报对齐 |
| R05 | Given目标父目录有未选symlink/特殊文件；Whenapply预检；Then只检查父路径组件，既不递归读取也不因无关兄弟阻断；父路径自身链接仍拒绝 |
| R06 | Given受支持的npm sh／PS／cmd shim指向所选CLI；Whenprobe；Then绑定实际字面相对CLI指向，动态／未知／经链接的包装器不冒报匹配；不声称执行或Node证明 |
| R07 | GivenPowerShell profile定义同名alias/function；Whenprobe；Then检查实际赢得优先级的命令，不过滤遮蔽后报假通过 |
| R08 | Given.bashrc有非交互return守卫；Whenprofile probe；Then在隔离且真实交互加载条件下检查PATH，并保留超时 |
| R09（纠正审查） | Given受支持的嵌套安装；When从已安装的规范副本重试/恢复；Then保留分阶段执行的续作能力；旧bootstrap因自身变化得到source-stale不是已安装副本失效，不新增包含关系禁令 |
| R10 | Given两个路径拼写指向同一物理Skills根；Whenplan；Then只产生一个写集，决策可正确绑定；大小写敏感卷的真实不同目录不合并 |
| R11（排除行为变更） | Given已确认restore intent且目标absent；When恢复续作；Then保持原有确认窗口，不新增删除checkpoint作为必要条件 |
| R12（排除行为变更） | GivenOMP host probe；When隔离验收；Then明确仍限user-wide配置，不新增项目继承路线投影/私有图构建，也不冒充已验证项目级host加载 |
| R13 | Givenstate文本仅提及六个工具URI而未实际注册可调用；WhenOMP probe；Then不得通过；只能以权威注册/宿主实际调用结果为证据 |
| R14 | Given宿主停止读取stdin；When大型RPC请求超过管道容量；Then写入和响应共享期限，到期退出并结束自有探测进程 |
| R15 | GivenPOSIX bin包含冒号等PATH分隔符；Whenplan；Then写前拒绝不可表达的PATH项；Windows驱动器别名仍支持 |
| R16 | Given平台oh-my-pi；Whenplan/verify/probe；Then统一为omp，同一平台各层判断一致 |
| R17 | Given一个域blocked另一个drift；Whenaggregate；Thenblocked不丢失且保持逐域证据 |
| R18 | Given合法配置只有无关MCP；Whenlegacy检查；Then报告none，畸形配置仍unknown/blocked |
| R19 | Given文件系统根与后代；When范围/包含校验；Then正确识别根的后代与重叠，不使用双分隔符前缀 |

## 数据与恢复决定

- 当前受信包拥有目标基线，操作人选择且独占的私有vault拥有历史；hash只绑定一致性，不引入新签名或HOME存储。
- 写后异常只能报告实测或明确unknown；不能把旧完整回执误作本次成功，也不能丢弃已经持久的恢复引用。所有新增进度状态落在现有vault并绑定plan/recovery id。
- 用户确认保留既有恢复窗口：restore intent后的目标absent可继续原恢复目标，不新增删除checkpoint；不将此窗口扩大为对未知非空内容的覆盖授权。
- 源/目标、平台、物理路径标识保持单一归一化规则；已有schema版本行为若变更必须明确拒绝歧义，不添加永久兼容别名。
- 单一writer拥有每个模块，主会话独占验证。源冻结后跑全套，运行期间不继续写生产源码。

## 本轮Book Gate Plan

| Gate | 触发/时点 | 状态 |
|---|---|---|
| DDD | 15项修复及4项保留边界明确且未full grill | not-required |
| DDIA | 写后失败证据变更，开发前 | passed：confirmed，绑定本批证据与unknown状态策略明确；R11新增删除checkpoint已撤回 |
| Legacy | 修复既有行为，开发前 | passed：characterized；真实red及正向控制均保留，原R03／R09等策略性red已更正，不作为缺陷证据 |
| Refactoring | 既有生产代码变更，Legacy后 | passed：proceed / normal，沿用现有安全原语，不做广泛重构 |
| Release | 新head完整验证与独立复核后 | passed：ready，代码99afbe89266ed4da456fd315f969caa0655d654f三平台CI 37200497908通过；不代表部署／发布 |

## 验证记录

原始red/green、真实隔离smoke与同stem中文汇总保留本任务reports/review-fixes/；未发布的本地路径不上传。最后一次冻结提交的Linux/macOS/原生Windows CI是精确head证据，不复用上一轮绿灯。

### 审查结论更正

用户已明确确认上述四项保留契约。R09以冻结的原始ac34ee4运行真实公开CLI：plan/apply均exit0；旧bootstrap重试exit2/source-stale；**已安装副本的retry、recovery-plan、recovery-apply全部exit0**。原始证据见`reports/review-fixes/r09-old-*.json`及同stem中文汇总。撤回本轮新增的包含关系拒绝实现及拒绝测试，不把已有绿灯当成错误禁令的理由。R03/R11/R12的拟议新行为同样撤回，原始red不删除；它们不计入15项修复的失败/通过统计。

### 修复与局部复核收口

15项实现已完成，四项保留契约不计作代码修复。R10补齐物理根／现存Skill子目录别名与冲突绑定，并保留已选非Skill文件／目录的决定拼写；只在目录设备号／inode相同才采用catalog拼写，不用列举父目录的实际大小写替代catalog身份。真实现存大小写目录、profile文件及host目录分别留有red/green。

R06撤回本轮额外引入的Node推断与PATH预置：它们不是原有shell探测契约，还会让未执行受管PATH块的profile假通过。保留CLI指向证明，并收紧字面路径、链接包装器和打开后有界读取。实际npm生成的`.cmd`暴露模板漏写`%dp0%\`分隔符；按真实生成字节修正，而非继续依赖同样有误的夹具。

R02增加证据读取再次失败时的unknown批次；R13只消费匹配成功OMP响应的`data`注册表；R18保留null／非对象及读取冲突的unknown状态。R14健康EOF和阻塞写入均回收直接子进程、线程和管道；异常后代继承管道仅限时尽力处理并显式警告，不声称进程组终止。

独立静态复核最终均无未解决的范围内问题：库存、事务／CLI、宿主shell、宿主协议四个切面；每位reviewer均未运行测试，验证由主会话执行。Ruff最后只修正本轮导入、未用变量及上下文写法；类型检查要求checkpoint先取得非空阶段ID，不改有效调用者语义。

### 当前本地验证

- `final-full-unittest-local`：冻结源码全量1732项，OK，20项平台／opt-in跳过；之后仅做上述静态收口，最终代码全量以99afbe8的原生CI为权威。
- `final-upgrade-gate-after-static-cleanup`：当前四个upgrade模块287项，OK，10项平台条件跳过。
- `final-all-changed-python-lint`、`final-type-check-green`：本轮8个Python文件Ruff与4个生产模块ty均通过；既有compileall／Bash语法门通过。
- `post-static-native-*`：最终当前包真实公开CLI完成37资源plan／apply、已安装副本Codex及OMP probe（各33 Skills、6工具）、retry与recovery；平台别名和共享物理根规范化生效，缺失host的preserve仍安装，未选悬空链接与原profile保留。
- `shim-literal-and-bounded-growth-green`：打开后增长的wrapper只读取65537字节并拒绝；真实生成shim及Bash／zsh／PowerShell正反例见`native-generated-npm-shell-final-v2`。
- `native-omp-all-response-envelopes`：真实OMP三个命令均为匹配command的成功response；`readme-html-browser-fallback`证明新增HTML内容实际渲染。Ego CLI两次超时及首次捕获缺口单独保留，不安装或修写浏览器配置。
- `docs-lesson-and-scenario-validation`：kuno lesson唯一ID、索引锚点与U16—U19场景结构通过。BDD为traceable；不生成`.feature`，无新测试框架。README.md／README.html／版本化automation prompt／CHANGELOG均同步；不触碰live automation。

以上均为developer-local／dirty／local-only。没有把本地macOS、协议夹具或旧PR绿灯冒充新的原生Windows／Linux／精确head证明。

### 精确代码提交CI

`99afbe89266ed4da456fd315f969caa0655d654f`的[run 37200497908](https://github.com/KunoLu/640-skills/actions/runs/37200497908)全部通过：Linux1732项（32 skip）＋最低tomlkit56＋大小写1；macOS271项（2 skip）＋升级287项（10 skip）；Windows安装器49＋PowerShell15、边界22（1 skip）、TOML3、junction1、DACL1、升级287（22 skip）。三个job末次checkout均clean，平台skip不冒充执行。

原始CI元数据／日志／中文汇总及通过schema／digest验证的generic v1 envelope在`reports/review-fixes/ci-repairs-code-99afbe8*`。本地dirty证据不升级为exact，任意JSON／TXT不宣称v2场景执行绑定。最终记录提交后的head还须使用其自身PR Checks；代码CI与交付CI分别留存，不复用旧绿灯。
