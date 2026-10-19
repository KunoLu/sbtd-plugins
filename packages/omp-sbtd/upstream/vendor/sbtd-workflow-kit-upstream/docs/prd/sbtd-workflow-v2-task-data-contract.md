# SBTD v2 P0-03：任务数据、引用与状态历史契约

## 范围与交付

本契约落实主 [PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md) §7.3～7.5、§8.1 的数据要求，依赖已完成的 P0-02 与 [P0-10 模式路由](sbtd-workflow-v2-mode-routing-contract.md)。开发起点为 `main @ a5bf602f587ab89288e0bcf61820fbea54df6c7f`，任务分支 `p0-03-task-data-contract`。

交付包含 [JSON Schema](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/task-data.schema.json)、本语义契约与 `tests/test_sbtd_task_schema.py` 的边界验证。schema 使用项目既有 Draft 2020-12，不新增验证框架。当前只是 P0 的协议／case 设计与声明式数据校验；不宣称 Onboard 已能读写任务或恢复状态。按实施调整记录 D-IMP-05，schema经P0-04非discovery候选进入P0-07正式可安装目录，始终只有一个canonical副本且内容不变。P1-17／P1-18负责运行行为，P1-14／P1-15负责集成及真实host证明。

未完整调用 grill-with-docs：任务字段、事实源与恢复规则已在主 PRD 确认，无新增领域选择。DDD / DDIA Review 均 confirmed：task 拥有 mode/status，引用／索引／handoff 不拥有副本；单 writer；单文件原子更新；跨文件不承诺事务；未知历史保留未知；无锁服务、数据库、journal 或调度器。Legacy／Refactoring／Release Gate 对本项不修改既有生产执行路径的范围为 on-demand／not-required。

## 存储与事实源

| 资产 | 权威信息 | 不能承担的职责 |
|---|---|---|
| `.sbtd/tasks/<logical-id>/task.md` 或 `ai/tasks/<logical-id>/task.md` | 唯一有效任务的模式、来源、状态、时间、正文和历史事件 | 不能同时写两个有效副本 |
| `.sbtd/active-task.json` | 当前目录书签：schema、逻辑 ID、相对路径 | 不复制 mode/status/恢复正文；不是跨机器自动同步 |
| `ai/tasks/index.md` | 共享任务导航，状态可从 task 派生 | 不作为第二模式或状态事实源 |
| handoff | 带任务身份／分支／时间的恢复快照 | 不覆盖有效 task 中的新模式 |
| `legacy-task.json` | 迁移后的共享安全旧数据快照 | 普通状态写入不更新它；不是当前任务状态 |

执行模式与存储正交：default 通常本地，lite/strict 通常共享；明确提升共享的 default 仍是 default，降模式不自动删除或搬回历史。显式只读任务只在会话内处理，不创建或改写任何表内文件。首次本地写入还必须满足主 PRD 的 ignore／tracked 检查及窄授权。

## Schema 校验入口与边界

文件根默认验证 `taskFrontmatter`；其他对象选择对应 `$defs`，沿用同一 `$defs` 引用上下文，不复制定义。

| 入口 | 输入 | 能证明什么 |
|---|---|---|
| `taskFrontmatter` | 从 task.md 安全解析的 frontmatter 映射 | 核心字段类型、枚举、模式／来源组合、blocked 原因、未完成任务无当前完成时间 |
| `activeTask` | active-task.json 对象 | 仅三个字段、ID 与根内 task.md 相对路径的词法形状 |
| `stateEvent` | task.md 状态表的一行映射 | 五列、时间形状、理由／证据非空及允许的状态对；状态不变的元数据事件仍需语义核对 |
| `blockEntryEvent` | 一次**新进入 blocked** 的事件候选 | 复用 stateEvent；at 必须是带时区实际时间，from 只允许 planned／in-progress／checking → blocked，拒绝 blocked→blocked |

校验成功不证明文件存在、安全权限、symlink containment、真实授权、父子无环、历史顺序或实际工作已完成。运行消费者必须同时执行下文语义校验；不能以 schema 通过直接落盘或恢复。

### 时间与解析

- 文件为 UTF-8 数据。frontmatter 使用 JSON 兼容的安全 YAML 映射；加载过程不执行 tag／对象构造／命令，拒绝重复键、循环引用与非有限数字，不能通过普通字典覆盖掩盖重复键。具体安全解析器由运行任务选择，不在本项引入依赖。
- `schema_version` 是整数 1，布尔值和未知版本拒绝；不自动补默认或解释未来版本。
- 时间字符串采用带时区的日期时间：`YYYY-MM-DDTHH:mm:ss[.fraction]Z` 或显式 `±HH:mm`。schema 的 pattern 保证形状，`format: date-time` 只是声明；验证端必须启用真实格式断言，或用标准库日历／时区解析补齐。未注册的 format checker 不能当成校验成功。现有聚焦测试显式用标准库日期解析注册 checker，避免依赖可选格式包是否安装。
- 新任务必须记录实际时间。历史无法证明时 frontmatter 时间为 null，并在正文写来源；只有历史补录的事件时间用 `unknown`，新入阻塞等新操作事件必须有实际时间。不得用当前时刻补历史。
- 时间先后、完成时间与完成事件相等、恢复事件链与当前状态一致都属于语义检查，不仅比较字符串或相信 schema。

### frontmatter 不变量

核心字段：`schema_version,id,workflow_mode,mode_source,mode_note,status,branch,created_at,updated_at,completed_at`。`parent` 可省略或为 null；它不随目录 basename 推导。

- `workflow_mode=null` 与 `mode_source=migration-unknown` 配套，只用于无法证明旧模式；恢复前询问。新选择立刻生效但写入仍受只读、分支和权限边界约束。
- `mode_source=default` 只能搭配 `workflow_mode=default`；用户明确选择 default 使用 `mode_source=user`。
- blocked 必须有非空、非纯空白的 `blocked_reason`；解除后清空或移除。`blocked_from` 禁止，以事件历史恢复前态。
- 非 done 的 `completed_at` 必须为 null；done 的历史未知时间允许 null，但新完成不能利用这个兼容分支伪造“时间未知”，必须有实际完成事件。
- branch 为原始分支；detached 使用 `detached:<full-sha>`，非 Git 为 null。schema 只检查基础类型；运行核对真实仓库绑定与完整 OID，不能按字符串相似忽略冲突。
- frontmatter 允许项目自己的 JSON 兼容扩展数据，保留但不执行、不作为核心字段 alias、不覆盖权威模式／状态。写操作必须无损保留不属于本操作的内容；异常扩展暂停相关写入，不能丢弃后继续。这里没有给旧 task.json 自动展开未知字段的许可，迁移仍使用 legacy sidecar 和隐私门。

### ID 与引用

逻辑 ID 可包含 `/` 表达父子身份，跨本地／共享／归档不变。schema 排除绝对／home 路径开头、Windows drive 开头、反斜杠、控制字符、空段和 `.`／`..` 段；它不是平台文件名合法性的完整证明。

active 引用只指向本项目 `.sbtd/tasks/` 或 `ai/tasks/` 下的 task.md，包括合法归档路径。读写前：解析真实根、检查路径与每级类型／symlink、确认目标在授权根内、核对 frontmatter.id 等于 task_id。目录路径与逻辑 ID 不必逐字符相同（例如归档），不能只检查 basename 或仅靠前缀字符串证明 containment。

父子关系须全部可解析、逻辑 ID 唯一且无环；一个 parent 可处于汇总 in-progress，但不能让多个执行叶子共享一个 writer／执行身份。缺父节点、多个候选或双副本都须解释冲突，不按 mtime 猜胜者。跨分支继续、只读查看与明确重绑定按 P0-10 的独立场景处理。

## 写入顺序与恢复

### 单任务变更

1. 核对模式／分支／授权、预期旧内容与有效引用；明确本次是状态变更、持续阻塞原因更新，还是归档／重绑定等元数据操作。
2. 在内存中形成 task.md 的完整候选。需要状态事件时，正文中的唯一 `## 状态事件` 表与当前字段一起更新；不写旁路状态文件。
3. 验证候选的核心字段、完整历史、路径／隐私与实际证据，再以同目录临时文件＋原子替换提交。写失败保留原文件及实际失败状态；检测到其他 writer 或预期内容变化则停止。
4. 重试先核对当前状态和已存在的实际事件，完成相同操作不重复追加。原子替换只覆盖一个文件，不构成跨文件隔离或授权服务。

### blocked 与恢复历史

新进入 blocked：只接受 `blockEntryEvent`，事件 from 是当时真实 planned/in-progress/checking；同一写入保存 blocked_reason 与 updated_at。持续 blocked：只更新原因／时间，**不追加新的阻塞事件**。

`stateEvent` 允许 from=to 的行，是为了保留主 PRD 已允许的归档／明确分支重绑定。特别是 blocked 任务重绑定仍可记录 blocked→blocked；这不是再次进入阻塞。运行写入者必须有相应真实操作和授权，不能把“仍然 blocked”包装成元数据事件。读取恢复历史时：

1. 状态不变的元数据行不建立或覆盖阻塞前态。
2. 从真实入阻塞事件与随后的解除事件配对，找到最近尚未匹配解除的那次入阻塞。
3. 默认恢复它的 from，只允许 planned/in-progress/checking；模式切换不改变该依据。
4. 记录缺失、链冲突或前态不可证明时，保存现有数据并询问本次恢复阶段；不能猜旧前态、伪造 ingress，或直接 done。

历史未知完成只允许 `from=unknown,to=done` 的补录，必须有旧完成事实及来源说明。schema 不认证该事实；新操作禁止借此跳过生命周期。

### 重开、提升与归档

- 重开 done：先保留可证明的原完成时间／证据，缺事件时按原来源补录，再追加 done→planned 并清空当前 completed_at。已 done 祖先先按祖先到子顺序重开；部分失败停止后续步骤并保留已写事实，不假装批量回滚。
- 共享提升：目标候选→完整校验→更新有效引用与共享索引→确认后退役原本地记录。逻辑 ID 不变，原本地内容不丢；任一步失败保留可恢复信息，不允许两个副本同时写。恢复时核对明确引用、内容和用户修改，不以最新时间自动选副本。
- 归档：用户确认后携带整个任务目录和事件历史；共享已完成任务按可靠完成日期进入 `archive/YYYY-QN/`，未知日期用 undated。本地历史不因归档自动公开，Git history 不代替 ignored 原件保全。
- task 损坏、模式未保存或引用失效时，如实报告；default/lite 可继续与损坏内容无关的安全工作，strict 的必需产物仍未完成。不能新建同名替身假装修复。

## 分层验收

| 场景 | P0-03 当前可验证范围 | 后续实际行为证明 |
|---|---|---|
| 模式未知／来源与默认值冲突 | schema 接受／拒绝边界 | P1-17 保存、P1-18 询问与恢复 |
| blocked 原因、重复入阻塞、直接 done | schema 与 blockEntryEvent 的拒绝边界 | P1-17 持续阻塞零新增事件、原态匹配恢复 |
| 重开后当前完成时间 | schema 拒绝非 done 的非空 completed_at | P1-17 旧时间/证据保留、祖先顺序及部分失败 |
| active 路径与模式副本 | schema 拒绝词法逃逸与多余权威字段 | P1-17 实际 symlink/根边界、ID核对、损坏指针 |
| 父子缺失／环／同名不同父 | 语义规则与最小案例已明确，非单对象 schema 能证明 | P1-17 跨文件唯一性／DAG 与冲突拒绝 |
| 日期、未知历史、格式包缺失 | 显式格式断言与 nullable 历史边界 | P1-17 真实当前时间、历史来源及完成事件一致 |
| 提升中断／用户并发改动 | 操作顺序与失败契约 | P1-17 隔离文件系统的每步失败／重试证明 |
| 只读、跨分支、mode 立即生效但保存失败 | P0-10 对应 MR 场景 | P1-18／P1-15 机器与真实 host 分层验收 |

`tests/test_sbtd_task_schema.py` 使用项目既有 unittest/jsonschema，通过真实 schema 接口验证边界，不读取源码断言措辞、不创建伪 runtime。模式来源、blocked 原因、当前完成时间、新入阻塞及日期 checker 均有 red→green 记录；路径、尾随及 DEL/C1 控制字符、未知版本等字段边界额外验证。语义顺序和跨文件失败仍必须在 P1 补运行证明。

本项不修改现行 CLI、安装逻辑或真实项目。README.md、README.html、版本化 automation prompt 暂不改：尚无可使用的 v2 运行能力；CHANGELOG 在本项记录新增协议／验证资产，不把它写成迁移或恢复已可运行。

## 提交前验证记录

新增9项聚焦测试、Ruff与ty检查通过；schema消费者smoke接受合法引用／首次阻塞并拒绝路径逃逸／重复入阻塞。原生全量 `python3 -m unittest discover -s tests -p 'test_*.py' -v`：276 tests / 61.787s / OK / exit 0。

本地报告：`tests/unit/reports/unit-report-task-data-contract-p0-03-task-data-contract-2026_09_17-15_02_10.json`，同stem中文 `.md` 与v1 `.evidence.json`。该轮绑定开发起点 `a5bf602f587ab89288e0bcf61820fbea54df6c7f`、dirty工作树、developer-local／unverified／local-only，不证明最终PR head；提交后另做精确HEAD复验，不回写本历史记录。
