# SBTD Runtime API 与本地工作流可视化 Dashboard PRD

> 文档版本：v0.1 · 评审稿  
> 编写日期：2026-09-23  
> 面向项目：KunoLu/640-skills，SBTD Workflow v2 扩展  
> 实施顺序：**需求一 Runtime API／审计统计 → 需求二 Local Dashboard／四格式导出**  
> 产品定位：**Local-first、Codex/OMP-first；Dify-ready，但不依赖 Dify。**

---

## 文档导航

- [0. 执行摘要与决策结论](#section-0)
- [1. 基线核对、现状与问题](#section-1)
- [2. 目标、非目标与使用者](#section-2)
- [3. 总体方案与实施边界](#section-3)
- [4. 需求一：SBTD Runtime API](#section-4)
- [5. 数据模型：事实源、标识与实体](#section-5)
- [6. 事件、状态与证据协议](#section-6)
- [7. 采集方案、数据覆盖与审计可靠性](#section-7)
- [8. 统计维度、指标定义与时间口径](#section-8)
- [9. API 契约、查询快照与错误处理](#section-9)
- [10. 本地存储、安全与保留策略](#section-10)
- [11. 未来 Dify／团队平台的预留设计](#section-11)
- [12. 需求二：SBTD Workflow Local Dashboard](#section-12)
- [13. 导出产品规格](#section-13)
- [14. 非功能要求与技术取舍](#section-14)
- [15. 实施阶段、依赖与交付门](#section-15)
- [16. 验收标准与需求追踪矩阵](#section-16)
- [17. 关键验收场景示例](#section-17)
- [18. 测试与证据交付要求](#section-18)
- [19. 风险、替代方案与未决实现项](#section-19)
- [20. 最终交付清单与发布定义](#section-20)
- [21. 来源与证据索引](#section-21)
- [22. 修订记录](#section-22)

---

<a id="section-0"></a>

## 0. 执行摘要与决策结论

本 PRD 规划一个部署在开发者本地 PC 上的 SBTD 可观测性扩展：先为现有运行时建立统一访问接口、可追溯事件及统计模型，再使用同一套 API 构建 `http://localhost:6400` 本地单页 Dashboard。

本次不是把 SBTD 迁移到服务器，也不是用 Dify 替代 Codex/OMP。开发、Git/worktree、测试设备、任务状态及原始验证产物继续在开发者本机运行和保存。未来 Dify 只能通过另行授权的适配层消费这些接口；本期不建立云端连接、不上传数据、不远程控制开发机。

### 0.1 已确认的用户需求

| 编号 | 用户要求 | 本 PRD 的落地方式 |
|---|---|---|
| U-01 | 先实现 SBTD Runtime API | 需求一独立可验收；没有 UI 时也可通过本地接口查询、统计及核验 |
| U-02 | 统计各任务、步骤、组件、状态，支持详细审计及汇总 | 建立任务、执行轮次、步骤、组件调用、Gate、验证、用量、操作事件及数据质量模型 |
| U-03 | 为未来 Dify 预留字段／结构 | 版本化协议、来源／身份／关联 ID、权限 scope、外部引用、同步游标及适配接口；当前不启用集成 |
| U-04 | 本地 Dashboard，默认 localhost:6400 | 显式启动的 loopback 服务；不要求 Docker，不成为日常开发前置条件 |
| U-05 | UI 与时间筛选参考 OMP `/stats` | 参考其主题、卡片、表格、分段时间选择；增加自定义起止时间 |
| U-06 | 时间筛选在右上角导出按钮左侧 | 时间范围控件与导出按钮相邻；刷新、主题等控件放在它们之前 |
| U-07 | 单次选择 HTML／JPEG／PDF／CSV 导出 | 一个导出菜单，四个格式；每次生成一个目标格式文件 |
| U-08 | HTML／JPEG／PDF 导出页面全部展示内容 | 导出完整逻辑报告页，包含滚动区域下方所有 Panel，而不只是当前视口 |
| U-09 | CSV 导出指定范围内全部统计数据，不含图示 | 导出完整筛选范围的结构化统计和审计明细；不受 Top N、页面分页或图表采样限制 |
| U-10 | 不采用按维度切换内容的左侧边栏 | 单页纵向报告 + 横向锚点导航；所有核心维度在同一文档流中 |

### 0.2 本文建议并作为实施基线的设计决定

1. **保留原有任务事实源。** `task.md` 继续拥有任务 mode/status/history；统计数据库不反向驱动任务状态。
2. **补齐执行事件，而不是只读当前文件。** 单独的审计事件记录“什么时间、哪个主体、在哪个任务／步骤、使用了什么组件、结果和证据是什么”。
3. **不把统计库全部当作可重建缓存。** 任务／报表投影可重建；新采集的原始执行事件通常不能从 `task.md` 完整重建，必须保护。
4. **一份筛选、一份快照、四种导出。** Panel、详情和导出共用后端统计口径与 `snapshot_id`，禁止前端各自计算不同总数。
5. **本期 UI 以只读为主。** 可以筛选、刷新统计、查看、导出；不提供“切模式、继续任务、标记完成、运行验证、迁移／清理”等业务控制按钮。

### 0.3 应避免的误解

- “已安装组件”不是“调用过组件”；“读取了 SKILL.md”也不是“该方法执行通过”。
- “任务 done”不是“所有 Gate 有有效证据”，更不是“已经发布”。
- “没有采集到记录”不是“使用者没有执行”；必须呈现 `not-observed`／覆盖不足。
- “本地数据已导出”不是“已上传到团队”；浏览器下载触发也不是接收者已保存或打开。
- “接口为 Dify 预留”不是“服务器端 Dify 能直接访问开发者的 localhost”。

---

<a id="section-1"></a>

## 1. 基线核对、现状与问题

### 1.1 本次参考的代码范围

| 对象 | 核对基线 | 本次用途与边界 |
|---|---|---|
| 640-skills | `main`，`03541a97f3804f8966cd5c4ff3f579793f9d4175`；提交时间 2026-09-21 15:28:56 UTC | 核对 TaskStore、TaskRouter、strict Gate 和验证证据契约；不是宣称 v2 已正式发布 |
| OMP Stats | 2026-09-23 读取的 `can1357/oh-my-pi` `packages/stats` 源码；当次 main ref 为 `e4151593ace2781d1dc2f06d760301f88af3e9dc` | 参考界面源码及时间控件，不声称已进入使用者本机 `/stats` 页面截图比对 |
| Dify | 当日官方 Tool Node、HTTP Request 文档 | 仅确认未来通过结构化接口调用外部能力的方向；不以特定新 Agent 版本为依赖 |

OMP 参考文件的读取内容指纹：`RangeControl.tsx` blob `622f90213e717ef7bf0856752d649418e395c99d`；`TopBar.tsx` blob `a3196c4655956602d07f308cd8fadc11c7c0768b`；`styles.css` blob `0b4a5c3fe944a7a0f916e4a9ae2ee90ed3e51827`。实施时先核对这些文件，而不是盲目跟随浮动 main。（来源：[S1]、[S5]、[S6]、[S7]）

### 1.2 与现有 SBTD 的关系

现有 `TaskStore` 是 host-native Python 库，声明不提供自动跨项目发现或后台工作；任务文档拥有状态，active JSON 仅为书签。`TaskRouter` 将已经明确的意图、模式、推荐回应等转成确定性结果，不负责自然语言意图分类。（来源：[S2]、[S3]）

因此本次应增加一个**薄 Facade 和可选采集层**，而不是复制现有状态机、重写一套任务数据库，或让 Dashboard 解析 Agent 自由文本后直接改文件。

现有 strict Gate 是按实际触发条件执行的，不是所有任务都要经过相同固定流水线；正式验证区分原生执行、证据文件、来源版本、环境及发布状态。（来源：[S4]、[S8]）

### 1.3 当前问题

| 问题 | 只读取 task.md 是否能解决 | 本期补充能力 |
|---|---|---|
| 查看当前模式、状态 | 大体可以，但需要安全解析和作用域核验 | 统一任务读取 API |
| 知道每次运行的开始、结束、重试和中断 | 不能保证 | 执行轮次与步骤事件 |
| 统计哪些 Skill／Tool 被实际使用 | 不能 | 主动埋点、宿主可观察调用、来源分级 |
| 追踪 Gate 适用性、执行次数及证据有效性 | 仅靠状态散文不足 | Gate 决策／执行／证据分离 |
| 汇总多项目、多 worktree 使用情况 | 缺统一标识和索引 | 显式项目注册、身份映射、维度 API |
| 导出某一时间范围的可复核结果 | 当前值不足以重现历史 | 事件时间、快照、水位和统计版本 |
| 为未来团队查询／Dify 使用准备接口 | 当前库不是可远程消费协议 | 版本化 API、外部引用和权限预留 |

**重要范围声明：**本 PRD 新增的是可选的观察记录存储与显式启动的本地服务。必须在仓库文档中明确这项边界变化；不能仍声称整个扩展“绝无持久事件存储／服务”，也不能把观察事件库包装成任务恢复 journal 或新调度器。

---

<a id="section-2"></a>

## 2. 目标、非目标与使用者

### 2.1 产品目标

| 编号 | 目标 | 成功标准 |
|---|---|---|
| G-01 | 统一访问现有 SBTD 运行时 | Codex／OMP 适配层与 UI 复用 Facade，不各自重实现任务规则 |
| G-02 | 支持细粒度使用审计 | 每条可采集执行事实有来源、主体、时间、关联实体、结果和证据等级 |
| G-03 | 提供可信统计 | 指标有明确分母、去重粒度、时间归属和未知数据说明 |
| G-04 | 提供可一次导出的本地全页报告 | 单页覆盖各主要维度；四种格式数据范围一致、可离线使用 |
| G-05 | 保持轻量、隐私和可退出 | 关闭 UI／采集不影响原工作流；不默认联网、不读取秘密 |
| G-06 | 降低未来集成成本 | 相同模型可由后续 CLI／MCP／HTTP Gateway／Dify Adapter 消费 |

### 2.2 本期非目标

不开发 Dify 插件、云端控制中心、远程命令队列、跨设备自动同步、统一登录或组织级 RBAC；不提供可拖拽修改执行语义的工作流设计器；不重建 Codex／OMP 对话系统；不采集完整提示词、思维过程、源码、键盘行为、聊天情绪或个人绩效评分；不强制引入 BDD runner；不因为查看统计而自动安装工具、建立身份或初始化项目。

### 2.3 使用者与场景

| 使用者 | 核心场景 | 本期可见边界 |
|---|---|---|
| 开发者 | 查看自己本机近期任务、Gate、工具调用、阻塞、测试及用量 | 当前本地配置明确登记且有权限的项目／来源 |
| 工作流维护者 | 判断组件使用覆盖、失败热点、采集盲区、模式选择和版本差异 | 已获得授权的本地元数据；不默认获得个人原始内容 |
| QA／技术负责人 | 接收开发者主动导出的周报／审计摘要 | 导出文件所包含的时间和筛选范围；不是在线控制开发机 |
| 未来团队平台／Dify | 查询授权汇总、关联任务与验证结果 | 本期仅预留契约，能力状态为 `not-configured` |

“使用者维度”不是默认读取系统用户名或统计全公司员工。本机存在多个明确归属主体时可以分别展示；无法归属的数据进入“未绑定主体”，不强行归人。

---

<a id="section-3"></a>

## 3. 总体方案与实施边界

### 3.1 逻辑架构

```text
开发者本机
┌─────────────────────────────────────────────────────────────────────┐
│ Codex / OMP / 显式本地调用者                                         │
│             │                                                       │
│             ▼                                                       │
│ SBTD Runtime Facade ────────────────► 现有 TaskStore / TaskRouter       │
│   │                                     HandoffStore / 身份解析      │
│   │                                               │                 │
│   │                                               ▼                 │
│   │                                  task.md / active / 原生报告     │
│   ▼                                                                 │
│ 受控事件采集 + 来源适配器                                             │
│   ▼                                                                 │
│ 本地审计事件库 + 可重建统计投影 + 数据质量记录                         │
│   ▼                                                                 │
│ Query / Metrics / Snapshot API                                      │
│   ▼                                                                 │
│ 显式启动 HTTP 服务 ───► localhost:6400 单页 Dashboard                  │
│                          └──► HTML / JPEG / PDF / CSV 导出           │
└─────────────────────────────────────────────────────────────────────┘

未来，另行授权：本地出站 Adapter → Team Gateway → Dify / 其他客户端
```

### 3.2 四层职责

| 层 | 职责 | 禁止事项 |
|---|---|---|
| Runtime Facade | 包装现有任务读取、路由、状态操作；返回稳定 DTO | 不成为第二任务状态机 |
| Observation & Audit | 记录已观察事件、证据和数据质量 | 不根据猜测制造执行、模式选择或人类授权 |
| Query & Snapshot | 去重、统计、历史视图和一致性快照 | 不以页面需要为由改 task.md、Gate 或测试结果 |
| Dashboard & Export | 呈现同一快照、筛选、查看和导出 | 不绕过 Runtime 直接操作业务文件或执行 shell |

### 3.3 运行方式

- **Facade／采集 SDK 不依赖 HTTP。** 正常本地 Agent 调用可以在进程内完成；UI 未开启时仍能记录已授权的事件。
- **HTTP 服务显式启动。** 只有用户打开 Dashboard／调用本地 API 服务时监听端口；本期不设置开机自启，不添加常驻 daemon。
- **启动命令为新增能力。** 建议公开入口为 `sbtd-runtime serve --port 6400`，这是本 PRD 提议，不是当前 640-skills 已有命令。安装方式、命令注册及卸载必须有独立文档。
- Codex／OMP 内可增加“打开 SBTD Dashboard”的可选入口，复用同一启动器；不占用或改写 OMP 自身 `/stats`。
- 本机服务读取的是已经登记的根目录；不得递归扫描 HOME、所有 Git 项目或未选 sibling 来“自动补齐统计”。

### 3.4 开关与失效模式

| 开关 | 默认建议 | 语义 |
|---|---|---|
| `observation.enabled` | 安装时明确确认后启用；未选择前关闭 | 允许保存最小化本地工作流观察元数据 |
| `observation.level` | `metadata` | 不记录完整消息／源码／命令参数 |
| `observation.failure_policy` | `best-effort` | 采集失败不撤销已成功的开发动作，但必须报告审计缺口 |
| `dashboard.auto_start` | `false` | 不开机常驻；显式启动 |
| `network.remote_sync` | `false` | 本期无云端上传 |
| `remote_commands.enabled` | `false`，本期不可开启 | 不接受 Dify／外部执行命令 |

用户明确要求“完全只读／不落盘”的任务，不因全局开启采集而写审计文件。只有另行明确授权“项目只读，但允许独立用户目录统计记录”时才可采集；两种只读语义须在调用上下文中区分。无法确认时采用更严格的不落盘行为。

---

<a id="section-4"></a>

## 4. 需求一：SBTD Runtime API

### 4.1 API 产品范围

需求一包含四部分，必须共同交付，不能只做读取 `task.md` 的 HTTP 包装：

| 子需求 | 必须实现 |
|---|---|
| R1-A 统一运行时门面 | 任务／路由／handoff／身份只读能力；已有状态操作的兼容包装及结构化结果 |
| R1-B 观察与审计 | 执行事件、宿主采集、验证产物导入、来源等级、缺口和去重 |
| R1-C 查询与指标 | 多维筛选、历史状态、趋势、组件／Gate／验证／主体汇总 |
| R1-D 消费契约 | 本地 HTTP、OpenAPI、固定快照、分页／游标、CSV 数据集及未来适配字段 |

### 4.2 Facade 的接口边界

建议逻辑能力如下；具体 Python 模块路径由实现 ADR 固定，现有脚本导入保持兼容。

```text
Projects:    inspect_project / list_registered_projects
Tasks:       list_tasks / inspect_task / get_task_history
Routing:     preview_route / apply_route
State:       create / select / transition / set_mode / resume / reopen
Transfer:    prepare_promote / retire_original / prepare_archive
Binding:     current_binding / recovery_candidates / rebind
Handoff:     inspect / list / prepare / save（遵守既有触发条件）
Identity:    resolve（不隐式 ensure）
Observation: emit / ingest / reconcile / inspect_coverage
Analytics:   query_metrics / query_timeseries / query_events
Reports:     create_snapshot / describe_dataset / export_csv
```

**接口分为两个面：**

1. **宿主内部操作面：**已有任务操作仍可由本机 Codex／OMP 通过 Facade 调用，继承原确认、分支、保护及单 writer 规则。
2. **HTTP／UI 查询面：**本期只开放查询、显式统计刷新、快照与导出，以及仅供受信采集器使用的 ingest。**不公开任务写操作。**未来远程控制必须另立安全设计与验收。

`preview_route` 必须是独立无副作用的预测能力；不能直接调用一个会保存状态的现有方法，再声称“只是预览”。所有预览响应必须包含 `executed=false`。

### 4.3 兼容性要求

- 不改变 `task.md` 的现有必填 schema，不为统计要求强制写入 task_uid、session_id 或组织字段。
- 不改变 default／lite／strict 选择优先级、不强制升级模式。
- 任务提升、归档、原件保留及 branch rebind 继续由现有 Runtime 处理。
- 关闭观察能力后，原工作流输出和副作用保持等价。
- 索引／观察库损坏不得被解释成任务本身损坏；反之 task.md 不合法也不得被统计库的旧值掩盖。
- Runtime 返回中必须分别说明业务操作结果、持久化结果和审计结果，例如 `operation_status`、`state_persisted`、`audit_status`。

---

<a id="section-5"></a>

## 5. 数据模型：事实源、标识与实体

### 5.1 事实源矩阵

| 数据 | 权威来源 | 统计层保存方式 | 可否从其他数据完整重建 |
|---|---|---|---|
| 任务当前 mode/status、任务状态事件 | 有效 task.md | 带来源修订的只读投影 | 在源文件存在且历史完整时可重建相应部分 |
| active task | active-task.json 指向的有效记录 | 引用投影 | 可以，不拥有 mode/status |
| 真正运行过的步骤／工具调用 | 受信宿主或 Runtime 产生的执行事件 | 原始观察事件 + 执行投影 | 通常不可以，不能当缓存随意清空 |
| Gate 的声明结论 | 对应 reviewer／人工记录 | 原值 + 规范化值 + 来源等级 | 取决于原始证据是否保留 |
| 测试结果 | 原生 runner 报告与有效证据契约 | 指标与安全引用 | 取决于报告是否仍在 |
| 审计查询／导出行为 | 本扩展产生的操作事件 | 独立类别事件 | 不可从 task.md 重建 |
| 各 Dashboard 指标 | 已验证数据与版本化口径 | 可重建聚合投影 | 可以，在源数据保留范围内 |
| 导出报告 | 固定查询快照 | 不可变 ReportSnapshot | 由该快照重现；不能依赖不断变化的当前数据 |

审计事件仅陈述“采集器观察到了某个事实”，不自动成为业务真相或授权证明。不得从观察事件回放并强制恢复／覆盖 task.md。

### 5.2 全局标识原则

使用不包含个人信息的 opaque ID，例如 UUID；ID 的唯一性不依赖事件时间。示例中的 `task_demo_01` 等仅用于说明。

| 标识 | 规则 |
|---|---|
| `installation_id` | 每次已授权安装生成的本地随机标识；不得用 MAC、机器序列号、邮箱或用户名派生 |
| `device_id` | 当前设备注册标识；重装后的跨设备关联必须显式建立 |
| `actor_id` | 统计主体标识；可为空，不等同操作系统账户、Git 作者或真实身份认证 |
| `project_id` | 本地项目注册记录 ID，不使用绝对路径作外部主键 |
| `repository_id` | 显式映射的仓库逻辑标识；不同 worktree 可关联同仓，但不能仅凭目录名／remote URL 自动跨人合并 |
| `worktree_id` | 区分同仓不同 checkout，包含有效性和历史别名映射 |
| `task_uid` | 观察域任务标识；关联 `repository_id + logical_task_id`，冲突时隔离，不按 mtime 选胜者 |
| `logical_task_id` | 保留 SBTD 原完整 ID，包括合法父子路径；不要求 basename 与身份相同 |
| `task_run_id` | 一次实际执行轮次；重开、重新执行可产生新 run；跨会话续接可保持同 run |
| `session_id` | 宿主会话标识，必须附带 `host_kind`／宿主实例命名空间 |
| `step_definition_id` / `step_run_id` | 区分步骤模板与某次执行实例 |
| `component_id` / `component_version` | 区分逻辑组件与实际版本／源码 revision |
| `invocation_id` / `attempt_id` | 逻辑调用与真实重试分开；每次真实尝试只计一次 |
| `event_id` / `source_event_id` | 接收事件与原来源事件标识；实现幂等去重 |
| `snapshot_id` / `export_id` | 固定数据视图与某次输出作业 |

路径移动、任务提升／归档和同仓 worktree 迁移通过显式映射维持身份；复制目录不自动宣称是同一任务实例。未来中央汇总先做授权 ID 映射，不能直接用本机路径或不同设备的本地 ID 推断全局唯一身份。

### 5.3 实体清单

| 实体 | 关键字段 | 作用 |
|---|---|---|
| Project | id、alias、product_id、repository_id、registration_state | 项目／产品统计入口 |
| WorktreeContext | id、project_id、branch、commit_sha、dirty、valid_from/to | 执行所处代码上下文 |
| ActorBinding | actor_id、display_alias、binding_source、identity_assurance、valid_from/to | 使用者归属和授权级别 |
| WorkflowDefinition | workflow_id、version、source_revision、component_registry_revision | 解释当时使用的工作流版本 |
| TaskProjection | task_uid、logical_id、parent_uid、mode、status、source_revision、observed_at | 原任务的非权威读取投影 |
| TaskRun | run_id、task_uid、run_kind、start/end、status、resume_link | 任务执行与恢复轮次 |
| SessionBinding | session_id、run_id、host、agent_role、binding_start/end、confidence | 会话与任务多对多时间绑定 |
| StepDefinition | definition_id、kind、component_id、display_order、contract_version | 可版本化步骤目录 |
| StepRun | step_run_id、run_id、parent_step_run_id、attempt_no、status、timing | 步骤时序及重试 |
| Component | component_id、kind、name、version、source_revision、ownership | Skill／工具／runner／宿主等组件 |
| Invocation | invocation_id、attempt_id、component_id、step_run_id、result、error_code | 可观察的真实调用 |
| GateEvaluation | gate_eval_id、scope_revision、applicability、lifecycle、raw_result、evidence_status | Gate 适用性、结论和证据 |
| ValidationRun | validation_id、runner、scope、source_revision、counts、result、evidence_source | 一轮测试执行 |
| ValidationCase | case_id、validation_id、scenario_locator、attempt_no、result | 用例／场景级结果 |
| ArtifactReference | artifact_id、kind、safe_alias、digest、exists、verification_status | 原生报告／证据安全引用 |
| UsageRecord | usage_id、request_id、provider、model、tokens、cost、billing_basis | 可选且可证明的用量 |
| AuditEvent | event_id、event_type、subject、actor、source、time、result、correlation | 不可变观察记录 |
| CollectionHealth | source_id、capabilities、coverage_window、lag、gaps、error_code | 采集覆盖和盲区 |
| ReportSnapshot | snapshot_id、filters、watermarks、metrics_version、panels、dataset_manifest | 页面与导出唯一数据视图 |
| ExternalReference | system、object_type、external_id、mapping_version | 未来 Dify／团队平台关联 |

`WorkflowDefinition`／`StepDefinition` 是观察层的展示和解释元数据，不是可执行 DSL，不重新拥有 Gate 的判定规则。

### 5.4 关系与重复统计防线

```text
Project → WorktreeContext
Task → 多个 TaskRun → 多个 StepRun → 多个 Invocation / GateEvaluation
Session ↔ TaskRun（通过有时间边界的 SessionBinding）
TaskRun → ValidationRun → ValidationCase / ArtifactReference
TaskRun / StepRun / Invocation → AuditEvent
以上经同一 QueryScope → ReportSnapshot → 四种导出
```

父任务可汇总子任务，但默认吞吐与耗时指标使用**可执行叶子任务**，父任务单列为“汇总任务”，避免父子重复计数。并行子 Agent 的统计通过 parent_run／parent_step 关联；不能同时加总父级汇总用量和相同请求的子级用量。

### 5.5 主体归属与身份兼容

- 优先使用用户明确配置的统计主体映射；存在合规可读的 SBTD developer 身份时，可以作为映射候选，但不自动建立或修改它。
- 统计不调用 `DeveloperStore.ensure()`；不从 Git 作者、OS 名称、HOME 路径猜人。
- `identity_assurance` 为 `unbound | local-declared | host-verified | organization-verified`；最后一项本期不得自动使用。
- `initiated_by`、`executed_by`、`requested_by` 分开；未来 Dify 发起不意味着 Dify 就是实际执行主体。
- 历史未归属事件保留未归属。后续映射调整以版本化记录呈现，不无提示重写历史归属。

### 5.6 不同“版本／修订”的明确区分

不得用一个模糊的 `source_revision` 同时代表工作流源码、业务代码、任务文件和统计口径。实体所属上下文不同，至少区分：

| 字段 | 所属内容 | 变化后的处理 |
|---|---|---|
| `workflow_source_revision` | 640-skills／规则载荷的固定 revision | 历史事件保留旧规则版本，不能按新规则重新判旧 Gate |
| `source_commit_sha` | 正在开发的业务仓库完整 Git SHA | 新提交不自动继承旧 PR-head 证据 |
| `worktree_revision` | 已授权范围内工作树状态的安全身份 | 同 SHA 下 dirty 内容变化也要区分；不把 dirty=true 当完整版本身份 |
| `task_document_revision` | 某次读取到的 task.md 字节版本 | 用于来源对账和过期检测，不取代 task_uid |
| `scope_revision` | 本次 Gate／验证所评价的明确输入范围与修订 | 新范围产生新评估实例；旧结论保留，但不能自动用于新范围 |
| `metrics_version` | 统计公式和归一化映射版本 | 新旧口径显式区分；旧快照不变 |

敏感源内容摘要只在有授权的本地记录中保存；对外导出可使用不泄露内容的稳定别名／不透明修订引用。无法证明精确工作树版本时标记 unknown，不允许因此宣称当前代码已经验证。

---

<a id="section-6"></a>

## 6. 事件、状态与证据协议

### 6.1 标准事件信封

下面是目标协议示例，不代表仓库当前已有这些字段：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_demo_01",
  "event_type": "step.finished",
  "occurred_at": "2026-09-23T05:50:00.000Z",
  "recorded_at": "2026-09-23T05:50:00.120Z",
  "ingest_seq": 1204,
  "installation_id": "inst_demo_01",
  "device_id": "device_demo_01",
  "actor": {
    "actor_id": null,
    "kind": "agent",
    "identity_assurance": "unbound"
  },
  "scope": {
    "tenant_id": null,
    "workspace_id": null,
    "project_id": "project_demo_01",
    "repository_id": "repo_demo_01",
    "worktree_id": "wt_demo_01",
    "task_uid": "task_demo_01",
    "logical_task_id": "api/import",
    "task_run_id": "run_demo_01",
    "session_id": "session_demo_01",
    "step_run_id": "step_demo_03"
  },
  "workflow": {
    "workflow_id": "sbtd",
    "version": "v2-development",
    "source_revision": "03541a97f3804f8966cd5c4ff3f579793f9d4175",
    "mode_at_event": "strict",
    "mode_source": "user",
    "scope_revision": "scope_demo_01"
  },
  "component": {
    "component_id": "runner:unit",
    "kind": "test-runner",
    "version": null
  },
  "state": {
    "previous": "running",
    "current": "succeeded",
    "raw_result": "passed",
    "reason_code": null
  },
  "measurement": {
    "duration_ms": 2400,
    "duration_basis": "monotonic",
    "attempt_no": 1
  },
  "provenance": {
    "source_kind": "runtime-instrumented",
    "source_id": "source_demo_01",
    "source_event_id": "native_demo_01",
    "producer_version": "0.1.0",
    "observation_level": "execution-observed",
    "evidence_status": "validated",
    "artifact_ids": ["artifact_demo_01"]
  },
  "correlation": {
    "request_id": "req_demo_01",
    "operation_id": "op_demo_01",
    "trace_id": null,
    "span_id": null,
    "parent_span_id": null,
    "causation_event_id": "evt_demo_00"
  },
  "privacy": {
    "classification": "local-metadata",
    "redaction_policy_version": "1",
    "exportable": true
  },
  "external_refs": [],
  "extensions": {}
}
```

### 6.2 字段与兼容规则

| 字段组 | 必须规则 |
|---|---|
| 时间 | `occurred_at` 为实际发生时间；不知道历史发生时间时为 null，不能用导入时间冒充；`recorded_at` 始终为实际记录时间 |
| 顺序 | `ingest_seq` 为本地入库顺序，不当作跨设备全局时间；宿主序号另存 |
| 作用域 | 与事件无关字段可为空，例如纯工具调用不一定能绑定任务；不为填字段创建任务 |
| 来源 | 保存 producer／parser 版本、原始事件 ID、安全源修订引用；来源不可伪装 |
| 扩展 | `extensions` 只允许命名空间和白名单 JSON 标量／小对象，设置大小限制；禁止任意大文本及秘密 |
| 未知字段 | 同主版本未知扩展可保存但不执行；未知核心枚举进入兼容隔离区，不能默认为 succeeded |
| 更正 | 原观察事件不覆盖；用 `event.corrected`／`supersedes_event_id` 声明更正，默认指标只计有效版本 |
| 隐私 | 正文进入持久层前完成白名单过滤与脱敏；默认不保存原始消息副本 |

### 6.3 事件目录

| 类别 | 事件例子 | 统计用途 |
|---|---|---|
| 任务状态 | `task.created`、`task.state_changed`、`task.reopened`、`task.binding_changed` | 生命周期、重开与历史状态 |
| 模式决策 | `mode.recommended`、`mode.accepted`、`mode.kept`、`mode.persist_failed` | 推荐回应与持久化失败 |
| 执行轮次 | `run.started`、`run.paused`、`run.resumed`、`run.finished`、`run.interrupted` | 运行次数、时长、暂停、中断 |
| 步骤 | `step.planned`、`step.started`、`step.finished`、`step.blocked`、`step.skipped` | 步骤分布、瓶颈、重试 |
| 组件 | `component.available`、`skill.loaded`、`invocation.started`、`invocation.finished` | 安装可用、载入、实际调用三层统计 |
| Gate | `gate.applicability_decided`、`gate.started`、`gate.result_recorded`、`gate.evidence_invalidated` | 应执行／已执行／有效证据区分 |
| 验证 | `validation.started`、`validation.finished`、`artifact.registered`、`artifact.verified` | 测试结果与证据完整性 |
| 用量 | `usage.recorded`、`usage.corrected` | Token／耗时／费用，防重复计费统计 |
| 交接 | `handoff.saved`、`handoff.restored` | 续接行为，不将快照当任务状态 |
| 采集健康 | `collection.gap_detected`、`collection.recovered`、`source.unavailable` | 审计可信度和覆盖窗口 |
| 本扩展操作 | `query.executed`、`export.requested`、`export.generated`、`export.download_served`、`settings.changed` | 本地查询和导出审计；与开发活动分开 |

查询审计只保存规范化筛选和摘要，默认不保留含用户内容的完整查询字符串。采集器不得因读取 `query.executed` 再无限生成相同查询事件。

### 6.4 状态命名空间必须分开

| 对象 | 标准状态／属性 |
|---|---|
| Task | 保留原 `planned / in-progress / checking / blocked / done` |
| TaskRun | `running / paused / succeeded / failed / cancelled / interrupted / unknown` |
| StepRun | `planned / running / succeeded / failed / blocked / skipped / cancelled / interrupted / unknown` |
| Gate applicability | `required / not-required / undecided` |
| Gate lifecycle | `planned / running / completed / blocked / unknown` |
| Gate normalized result | `passed / needs-clarification / failed / unknown`，并保留 reviewer 原词表 |
| Evidence | `missing / declared / present / validated / stale / invalid / unknown` |
| Source health | `healthy / delayed / partial / paused / unavailable / unsupported` |
| Export | `queued / generating / ready / failed / cancelled / expired` |

例如 reviewer 的 `confirmed` 可在其映射版本下规范化为 passed，但仍保存 `raw_result=confirmed`；文件存在只能证明 present，不能自动升级为 validated。

**任务 done 与 run succeeded、Gate passed、测试 passed、产物 published 是不同状态，任何一个都不能隐式修改另一个。**

### 6.5 证据分级与采集来源

| 等级 | 典型来源 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| `configured` | 安装目录／catalog | 组件存在或已配置 | 本次运行可调用、被使用 |
| `loaded` | 宿主文件读取事件 | 指令文件被载入 | 方法完成或 Gate 通过 |
| `declared` | Agent 结构化自报／人工声明 | 有人给出了这个结论 | 实际执行或独立验证 |
| `execution-observed` | 可信调用开始／结束／退出码 | 某个动作确实被运行时观察到 | 业务正确性或所有范围通过 |
| `artifact-verified` | 原生报告 + 已执行校验器 | 对应已声明范围的机器证据符合契约 | 未覆盖环境／最新代码自动通过 |

来源类型使用 `runtime-instrumented / host-observed / artifact-imported / user-declared / reconstructed`；等级和类型分别保存。不得用单个“可信度百分比”替代来源事实。

---

<a id="section-7"></a>

## 7. 采集方案、数据覆盖与审计可靠性

### 7.1 采集能力矩阵

| 来源 | 默认方法 | 应覆盖数据 | 必须承认的限制 |
|---|---|---|---|
| 现有 Runtime 操作 | Facade 事件回调／包装 | task 状态、模式选择、分支拒绝、handoff、操作结果 | 未经 Facade 的手工修改需后续对账 |
| Codex／OMP | 各自版本化适配器，仅使用实际可获取的结构化事件 | session、tool call、子 Agent、可用 usage | 不预设两个宿主的 hook／日志字段完全相同 |
| Skill／Gate 语义执行 | 工作流显式结构化阶段回执 | planned、started、结论、适用范围、证据引用 | 仅靠 SKILL.md 读取无法证明执行；自报仍是 declared |
| 原生测试报告 | 安全解析已有报告和 sidecar | runner、case、结果、revision、证据状态 | 不因 HTML 标题有 passed 就相信结果 |
| task.md 历史导入 | 安全读取状态事件及时间 | 已有任务状态历史 | 无法补出从未记录的 Skill／Tool 时长和次数 |
| 手工状态修改 | 明确触发的对账或服务运行期间的受限监听 | 发现来源修订变化 | 不知道操作者及精确时间时保留 unknown |

旧版宿主不支持某能力时，返回 `unsupported`。必须提供当前安装版本的能力报告和实际 smoke 证据，而不是在 README 写“全量覆盖”即算完成。

### 7.2 最小采集集

第一阶段必须端到端覆盖：task 状态变化、执行轮次起止、步骤起止、组件真实调用、Gate 适用性和结论、测试执行及证据状态、采集健康。模型 token／费用属于条件性字段：来源提供则采集，不能因此阻止本期主功能验收，但缺失状态必须可见。

对于难以机器识别的纯自然语言方法步骤，应提供显式步骤回执接口；UI 单独标注“结构化声明”，不得将这些数据混入“机器观察到的成功率”。

### 7.3 去重与关联

- 优先唯一键为 `(source_id, source_event_id)`；相同键、相同规范化内容的重放只确认，不重复计数。
- 相同键但内容不同必须 conflict，禁止静默覆盖。
- 来源无事件 ID 时用稳定记录偏移／来源段标识及安全摘要建立去重键；时间戳本身不够。
- 同一个调用同时被 Facade 与宿主观察时，通过 invocation／operation ID 合并为一个执行对象，保留两个来源引用；不能简单把事件数当调用数。
- 对于日志 rotation、截断、重解析和升级，checkpoint 记录来源实例／分段／偏移／parser 版本；不只依赖 mtime。
- 不确定属于哪个任务的事件留在“未关联活动”；禁止使用“最近打开的任务”或相近时间强行关联。

### 7.4 写入一致性与失败

业务文件、审计数据库、宿主进程之间不存在天然跨资源事务。本期不得承诺 exactly-once 业务执行或任意并发下的原子同步。

推荐执行顺序：

```text
验证作用域／确认／期望版本
    → 记录操作意图（获得 operation_id）
    → 调用现有 Runtime 的单 writer 操作
    → 按实际结果记录 observation outcome
    → 更新统计投影
```

| 异常 | 必须行为 |
|---|---|
| 审计写入失败，但任务写入成功 | 返回 `state_persisted=true, audit_status=pending-or-gap`；不能告诉用户任务失败并盲目再执行 |
| 任务写入失败 | 保存真实失败／部分完成步骤，不制造成功事件 |
| 意图有记录、结束事件缺失 | 标记 incomplete／unknown，启动对账；不直接判 failed 或重跑业务 |
| 进程崩溃／机器休眠 | 未闭合 span 标记 interrupted／unknown；不把整个离线间隔算执行时长 |
| 磁盘满／权限异常 | 最佳努力模式保留原开发语义，显式报告采集缺口；连缺口文件也写不了时不能宣称缺口已持久化 |
| 多个业务 writer | 继承原 Runtime 拒绝／冲突边界；观察数据库锁不等于业务文件锁 |

可选 `strict-audit` 模式：审计意图不能持久化时，在业务动作前阻断；若业务已成功而末尾审计失败，仍如实报告已成功副作用，并暂停后续需要强审计的操作。该选项不改变 SBTD strict 工作模式，两者独立。

### 7.5 历史导入与重建

首次启用提供**只读项目扫描计划**，由用户批准项目和来源范围后导入；不自动全盘扫描。导入的历史发生时间不可证明时为 null，UI 展示“导入时观察到”，不绘制到伪造的过去时间桶。

重建统计投影不删除原始审计事件。任务被删／路径失效时保留 tombstone 和最后观察时间，不把历史统计归零，也不尝试恢复业务文件。

### 7.6 采集覆盖必须单独展示

每个 host／source／project 至少报告：

```text
capabilities_supported
collection_enabled
first_observed_at / last_observed_at
complete_intervals[] / gap_intervals[]
last_source_checkpoint
pending_events / rejected_events / unlinked_events
clock_quality / parser_version / last_error_code
```

已知分母的覆盖率才计算百分比。例如声明 5 个 required Gate，仅 3 个有有效证据，可以显示 `3/5`；不知道应有多少工具调用时，不得显示“工具采集覆盖率 100%”。应改为展示“当前已捕获 N 次；该宿主不提供完整调用总数”。

---

<a id="section-8"></a>

## 8. 统计维度、指标定义与时间口径

### 8.1 必备筛选维度

| 维度 | 字段／分组 |
|---|---|
| 时间 | preset／自定义 from/to、timezone、bucket |
| 项目 | product_id、project_id、repository_id、worktree_id |
| 任务 | task_uid、parent_uid、run_id、task type、叶子／汇总任务 |
| 模式 | 事件发生时 default／lite／strict／unknown；mode_source |
| 执行阶段 | step_definition_id、step_kind、step_status |
| 组件 | component_kind、component_id、version、source_revision |
| 宿主与 Agent | host_kind、host_version、agent_role、parent_run |
| 使用者 | actor_id／未绑定、initiated_by／executed_by |
| Gate／验证 | applicability、normalized_result、evidence_status、runner、E2E scope |
| 模型／用量 | provider、model、model_role、billing_basis、currency |
| 数据质量 | source_kind、observation_level、coverage_state、unlinked／incomplete |

过滤条件作用于相应事实对象；不能将“组件筛选”粗暴用于抹掉任务的其他状态。响应为每个 Panel 指明 `filter_semantics`，例如“包含该组件活动的任务集合”与“仅该组件调用记录”是两个不同指标集。

### 8.2 指标目录与公式

以下每个指标必须配置 `metric_id`、中文名称、单位、统计粒度、过滤规则、分母、空值策略、版本和来源要求。

| metric_id | 含义与口径 | 注意事项 |
|---|---|---|
| `tasks.touched` | 范围内有可信活动事件，或执行区间与范围相交的 distinct 叶子 task_uid | 同一任务多次运行只算一个；无时间依据的数据单列 |
| `tasks.created` | created 事件发生在范围内的 distinct task_uid | 不用文件 mtime 代替创建时间 |
| `tasks.completed_unique` | 范围内至少发生一次真实 done 转换的 distinct task_uid | 与“范围末仍为 done”不同 |
| `tasks.completion_events` | 范围内 done 转换事件数 | 重开后再完成可增加事件，不增加 unique |
| `tasks.reopened` | 范围内 done→planned 事件数 | 不等同新任务数 |
| `tasks.status_at_end` | 可证明的范围结束时状态分布 | 历史不足进入 unknown；不使用当前值冒充历史 |
| `runs.started` | 范围内真实开始的 run 数 | 与续接 session 数分开 |
| `runs.interrupted` | 有可靠中断事实的 run 数 | 仅缺少结束事件时计 unknown，不默认失败 |
| `steps.attempts` | 范围内开始的 step attempt 数 | 同一次重放不增加 |
| `steps.success_rate_observed` | 机器观察到的 succeeded / (succeeded + failed) 终结 attempt | cancelled、blocked、unknown 单列，不藏入成功 |
| `steps.retry_count` | 同一 logical step 的 attempt_no>1 次数 | 区分用户重跑与宿主自动重试原因 |
| `duration.execution_ms` | 有可靠计时的执行区间与范围的交集时长 | 原始单调时钟优先；排除已知暂停／等待 |
| `duration.blocked_ms` | 已证明阻塞区间与范围的交集时长 | 未知结束时仅标右删失，不假定已解除 |
| `duration.step_p50/p95` | 结束于范围内、完整可测的 step attempt duration 分位数 | 返回 sample_count；未完整样本不混入 |
| `components.available` | 观察时有效可用组件数 | 不显示为使用次数 |
| `components.loaded` | 范围内可证明载入事件数 | 与 invocations 分开 |
| `components.invocations` | 范围内 started 的 distinct invocation attempt 数 | 工具、Skill、MCP、runner 分类别 |
| `components.failure_rate` | 终结调用的 failed / (succeeded + failed) | error reason 使用规范化 code |
| `gates.required` | 选定任务作用域修订下明确 required 的 Gate 实例数 | 不把每个重试都增加 required 分母 |
| `gates.evidence_coverage` | 范围末 required 且结果 passed、证据符合该 Gate 契约的实例 / required 实例 | undecided、declared-only 单列；不是通用“合规率” |
| `gates.rework` | 同一 Gate/作用域内需要修正后的再次评审次数 | 新代码／需求修订的重新评估独立标识 |
| `validations.runs` | 范围内开始的 validation run 数 | 通过、失败、阻塞和未终结分开 |
| `validations.run_pass_rate` | 结束于范围内的 passed / (passed + failed) run | narrow smoke 与 full-stack 必须分层 |
| `tests.first_attempt_pass_rate` | 测试计划中首次尝试 passed case / 有可判定首次结果的 case | 不用最后通过掩盖首次失败 |
| `tests.final_result_distribution` | 每轮验证各 case 最后已知结果 | 显示 flaky／retry；有完整证据才给结论 |
| `evidence.stale_count` | 不再匹配所声明源修订／有效性的证据数 | “对旧版本有效”与“可用于当前版本”区分 |
| `modes.distribution` | run 开始时选择的 mode；事件级分析用 mode_at_event | 模式中途改变不反向重写历史 |
| `modes.recommendation_response` | accept／keep／pending 的决策次数 | 推荐不是命令，不将拒绝视为错误 |
| `usage.requests` | distinct billable/source request ID 的请求数 | 父子汇总、stream chunk 与重放不重复算 |
| `usage.tokens` | 保留提供方原 input/output/cache/reasoning 语义，经明确映射后汇总 | 无兼容映射时分组展示；缺失不为 0 |
| `usage.cost_reported` | 提供方实际返回费用按币种加总 | 不等于用户实际订阅账单 |
| `usage.cost_estimated` | 版本化价格表×已知用量的估算 | 明确 estimated；与 reported 分列 |
| `audit.unlinked_count` | 无法绑定任务／主体的观察记录数 | 不强行补齐关联 |
| `audit.gap_intervals` | 来源已发现的采集缺口 | 不用“0 次活动”掩盖缺口 |

### 8.3 不得误导的统计规则

- 并行步骤的累加执行时长可以大于任务墙钟时长，两个指标分别命名；任务墙钟时长不得通过加总子步骤得出。
- 不把 Agent 运行时长、等待时长或提交次数当作开发者劳动时长／绩效。
- Token 的 cache-read 可能包含在某来源 input 中；标准化必须保存 `input_includes_cache` 等语义，不重复相加。
- 订阅调用、OAuth 调用或没有费用字段时标记 `cost_unknown`／`subscription`，不能显示“免费”或费用 0。
- 不同币种不能直接相加；本期不自动汇率换算。
- 成功率分母为 0 时显示 `—（无可判定样本）`，不是 0% 或 100%。
- 指标的部分采集结果带 `partial=true`，并展示 observed_count／unknown_count／分母依据。

### 8.4 统一时间契约

1. 底层保存 UTC、带时区时间；展示和自然日分桶使用 IANA 时区。
2. 默认时区取本机系统时区，可在 UI 明确切换；取不到时使用 UTC 并提示。示例使用 `Asia/Tokyo`，不是为所有开发者硬编码东京。
3. 统一查询区间为 **`[from, to)`**：包含开始，不包含结束。
4. `1h/24h/7d/30d/90d` 为以快照 anchor 为终点的滚动窗口；自定义日期支持精确时间，并清楚显示起止时刻。
5. 选择“截至某日”的日历语义时，转成该时区次日 00:00 的排他上界；不靠 23:59:59.999 猜边界。
6. `All` 指当前获授权且仍保留的全部可用记录，不宣称包含启用采集前或已清理的全部历史。
7. 长期 span 在区间外开始、区间内持续时，要计入相交活动和裁切后的时长，但不计为范围内新启动。
8. 未知 occurred_at 的历史记录进入“时间不可定位”附属集合，默认不混入指定时间段活动；All 可包含，并明确标记。
9. DST／时钟回拨依真实时区处理；负时长隔离为质量异常，不能强制修正成 0 后当正常样本。

### 8.5 趋势分桶与历史状态

建议默认：1h 使用 5 分钟桶；24h 使用小时；7d 使用 6 小时或日；30d／90d 使用日；All 自动选择日／周／月，使图表通常不超过 300 个桶。响应保留真实 bucket start/end 和空桶原因。

历史状态需要已知基线与可验证状态链。只有当前文件状态而没有对应过去证据时，过去的 `status_at_end=unknown`。页面可另展示“最新观察状态”，但必须带 `observed_at`，不能与所选历史区间混淆。

迟到事件按 occurred_at 归属，但只进入接收水位之后创建的新快照；已导出的旧快照不得悄悄变化。


---

<a id="section-9"></a>

## 9. API 契约、查询快照与错误处理

### 9.1 协议要求

- 本地 HTTP 使用 `/api/v1` 前缀；输出 JSON；提供 `/api/v1/openapi.json`。
- `schema_version`、`api_version`、`metrics_version`、`projection_version` 分开演进。
- ID 作为标识，不接收任意绝对路径、任意 SQL、任意 shell 命令或任意可执行代码。
- 所有列表采用稳定排序和不透明 cursor；默认每页 100，最大每页 1,000；批量导出使用完整迭代，不复用 UI 页限制。
- 多条件同字段 OR，不同字段 AND；不支持的组合返回明确错误，不能静默忽略。
- GET 不修复项目、不建立任务、不刷新图索引、不重新跑测试；显式刷新统计使用单独 POST。
- 项目注册／取消注册仅改变本扩展的授权来源清单；注册前展示范围，取消注册不删除原项目或审计历史。

### 9.2 目标端点清单

下列是本 PRD 规定的新接口，不是现有仓库已实现的 API。

| 方法 | 路径 | 作用 | 本期权限 |
|---|---|---|---|
| GET | `/api/v1/health` | 服务活性，最小响应，不泄露项目列表 | 本地最小探活 |
| GET | `/api/v1/capabilities` | 采集／导出／来源适配能力及版本 | `metadata:read` |
| GET | `/api/v1/openapi.json` | 当前实际开放接口定义 | `metadata:read` |
| GET | `/api/v1/projects` | 已授权项目与可用性 | `metadata:read` |
| GET | `/api/v1/actors` | 本地已绑定主体／未绑定维度 | `metadata:read` |
| GET | `/api/v1/components` | 组件目录、版本、可用性 | `metadata:read` |
| GET | `/api/v1/tasks` | 任务列表；支持范围内活动／范围末状态查询 | `tasks:read` |
| GET | `/api/v1/tasks/{task_uid}` | 任务来源、投影、关联 run 与质量 | `tasks:read` |
| GET | `/api/v1/tasks/{task_uid}/history` | 任务状态／模式／分支历史 | `audit:read` |
| GET | `/api/v1/runs` | run 列表及筛选 | `audit:read` |
| GET | `/api/v1/runs/{run_id}/steps` | 步骤、调用和证据关系 | `audit:read` |
| GET | `/api/v1/gates` | Gate 适用性／结果／有效证据 | `audit:read` |
| GET | `/api/v1/validations` | 原生测试运行及范围 | `audit:read` |
| GET | `/api/v1/events` | 已脱敏审计明细 | `audit:read` |
| GET | `/api/v1/collection-health` | 能力、延迟、缺口及未关联情况 | `metadata:read` |
| GET | `/api/v1/metrics/catalog` | 指标定义、维度及分母口径 | `stats:read` |
| POST | `/api/v1/statistics/query` | 结构化指标／分组查询，非任意 SQL | `stats:read` |
| POST | `/api/v1/statistics/timeseries` | 相同 QueryScope 的趋势查询 | `stats:read` |
| POST | `/api/v1/collection/refresh` | 读取获授权来源并更新本扩展投影 | `collection:refresh` |
| POST | `/api/v1/ingest/events` | 受信本地 producer 批量上报 | `events:ingest`，UI 不持有 |
| POST | `/api/v1/report-snapshots` | 固定筛选、统计水位和页面数据 | `stats:read` + 快照写入授权 |
| GET | `/api/v1/report-snapshots/{snapshot_id}` | 获取不可变报告快照 | `stats:read` |
| GET | `/api/v1/report-snapshots/{snapshot_id}/dataset` | 完整筛选数据集 cursor 读取 | `audit:read` |
| POST | `/api/v1/exports` | 为已有快照生成指定格式 | `export:create` |
| GET | `/api/v1/exports/{export_id}` | 进度、状态、数量、错误及有效期 | `export:read` |
| GET | `/api/v1/exports/{export_id}/file` | 下载同一用户授权的目标文件 | `export:read` |
| DELETE | `/api/v1/exports/{export_id}` | 取消未完成作业或清理本作业临时产物 | `export:create` |

`tasks:write`、`validation:run`、`migration:apply`、`remote-command:execute` 仅作为未来保留权限名，本期 HTTP 不注册相应执行路由。知道这些 scope 名称不代表可以使用。

### 9.3 QueryScope 示例

```json
{
  "schema_version": "1.0",
  "range": {
    "preset": "custom",
    "from": "2026-09-15T15:00:00Z",
    "to": "2026-09-22T15:00:00Z",
    "timezone": "Asia/Tokyo"
  },
  "filters": {
    "project_ids": ["project_demo_01"],
    "actor_ids": [],
    "host_kinds": ["omp", "codex"],
    "workflow_modes": [],
    "component_ids": [],
    "evidence_levels": []
  },
  "task_granularity": "executable-leaf",
  "include_unlinked": true,
  "include_unknown_time": false,
  "group_by": ["component_id"],
  "metrics": ["components.invocations", "components.failure_rate"]
}
```

此示例对应东京时间 2026-09-16 00:00 至 2026-09-23 00:00，右端点不包含。空数组代表该维度不过滤，不代表没有授权限制；服务端授权必须另行求交集。

### 9.4 标准响应

```json
{
  "api_version": "1",
  "request_id": "req_demo_01",
  "snapshot_id": "snapshot_demo_01",
  "data": {},
  "meta": {
    "as_of": "2026-09-23T06:00:00Z",
    "effective_from": "2026-09-15T15:00:00Z",
    "effective_to": "2026-09-22T15:00:00Z",
    "timezone": "Asia/Tokyo",
    "metrics_version": "1.0",
    "projection_version": "1.0",
    "watermark_seq": 1204,
    "query_hash": "digest-of-canonical-filter",
    "complete": false,
    "coverage_state": "partial",
    "warnings": ["OMP_USAGE_NOT_AVAILABLE"],
    "next_cursor": null
  }
}
```

`complete=false` 表示观测覆盖不足或已声明数据缺口，不代表允许接口把查询结果静默截断。分页是否还有数据由 `next_cursor` 和总数表达；服务出错必须走明确 error，不返回一个看似成功的空数组。

### 9.5 ReportSnapshot 与 DatasetManifest

快照至少包含：

| 字段 | 作用 |
|---|---|
| `snapshot_id / created_at / expires_at` | 固定数据视图身份与本地临时保留期 |
| `query_scope / query_hash` | 精确过滤条件和语义 |
| `as_of / effective_to / watermark_seq` | 冻结相对时间锚点、接收水位和取数上界 |
| `source_watermarks[]` | 各来源 checkpoint、最近观察、parser 版本和覆盖状态 |
| `metrics_version / component_registry_revision` | 固定指标和组件解释版本 |
| `panel_manifest[]` | Panel ID、数据引用、行数、Top N、Others、可见／展开状态 |
| `dataset_manifest[]` | 各数据族总数、过滤边界、未知时间集合及导出字段版本 |
| `quality_summary / warnings[]` | 缺口、来源不可用、身份未知、时长不完整等 |
| `report_document_version / render_profile` | 页面结构、主题、宽度和布局规则 |
| `redaction_policy_version` | 导出安全处理版本 |
| `snapshot_digest` | 固定安全数据包摘要；不是独立可信时间戳 |

快照读取使用一致性事务获取观察库水位，随后尽快形成不可变数据文件／临时表并释放读取事务。不要为了长时间生成 PDF 或下载 CSV 一直持有数据库读事务。

快照证明的是“截至这些已记录来源水位的观察视图”，不是对多个正在变化的项目文件执行了跨资源原子拍照。未同步最新源文件时必须标明 stale／last_observed_at。

### 9.6 错误与重试

| 错误 | 建议 HTTP | 必须行为 |
|---|---:|---|
| 无效时间／维度／指标 | 400 | 指明字段；不替换成默认范围 |
| 无凭证／scope 不足 | 401／403 | 不泄露受限对象是否存在 |
| 对象不存在或不可见 | 404 | 保留隐私边界 |
| 来源冲突、快照筛选不匹配 | 409 | 返回可操作原因，不自动覆盖 |
| 快照已过期 | 410 | 要求重新获取；不拿新快照冒充旧 snapshot_id |
| 请求体或导出规模超出已验证上限 | 413／422 | 预检失败、明确限制，不截断 |
| 同格式作业过多 | 429 | 返回 retry-after，不启动无限 renderer |
| 数据库／renderer 不可用 | 503 | 区分只读查询、HTML／CSV 与图像／PDF 能力 |

有副作用的 refresh、ingest、snapshot、export 请求支持 `Idempotency-Key`。同 key 同 payload 返回同结果；同 key 不同 payload 返回 409。导出重试不得产生多个无法追踪的文件。

---

<a id="section-10"></a>

## 10. 本地存储、安全与保留策略

### 10.1 存储布局

建议设置独立、可配置的 `SBTD_RUNTIME_HOME`，默认用户 HOME 下 `.sbtd-runtime/`。它不同于项目 `.sbtd/` 和 OMP／Codex 私有目录，不覆盖任何已有 HOME 资产。

```text
~/.sbtd-runtime/
  config.json                  # 授权来源、观察开关、展示偏好，不放业务秘密
  registry.json                # 项目／主体／设备映射，用户私有
  audit.db                     # SQLite：原始观察事件与操作记录
  projections.db               # 可重建查询投影；可在首版合并为 audit.db 内独立表
  spool/                       # 仅当前获授权 producer 的待入库事件
  snapshots/<snapshot_id>/     # 固定安全数据包
  exports/<export_id>/         # 单次导出产物及 manifest
  backups/                     # 升级前的受保护数据库备份
```

首版建议使用**一个 SQLite 文件、明确分开的 raw／projection 表**，减少分布式一致性复杂度；上图的独立 projections.db 只是可选部署结构，不要求一开始拆成两个数据库。

SQLite 适合本地嵌入式数据存储；WAL 具有单 writer 等边界，不能把同一个 WAL 数据库放到多机共享网络文件系统来充当团队数据库。（来源：[S11]）

### 10.2 本地权限与浏览器安全

- 服务仅绑定 loopback（127.0.0.1／按平台明确配置 ::1）；禁止默认绑定 `0.0.0.0`。
- Host／Origin 白名单拒绝外部域名和 DNS rebinding；不能因为“请求来自本机”就无条件信任网页请求。
- 浏览器通过短时一次性配对凭证换取本地会话；启动器不得将长期 token 写入 URL、浏览器历史、日志或导出。若使用 URL fragment 传一次性票据，读取后立即移除并销毁。
- API 使用会话／Bearer 鉴权，限制 CORS，拒绝任意外部 Origin；修改统计配置、refresh、export 使用 CSRF／Origin 防护。
- 浏览器 UI 不持有 `events:ingest` 凭证；不能让前端伪造 Tool 成功事件。
- SDK／本地采集器验证来源身份，但本地管理员仍可能修改数据，因此不宣称防篡改合规审计系统。
- 用户目录和数据库创建时设置最小文件权限，Windows 校验 ACL；拒绝 symlink／junction 越界和未知所有权路径。
- 下载使用随机 export_id 与当前会话授权；不接受任意 `file_path` 下载参数，不开放用户目录静态文件服务。

### 10.3 敏感信息最小化

默认保存：时间、匿名／已授权别名、稳定 ID、组件版本、枚举状态、计数、耗时、规范化错误码、安全报告引用。

默认禁止保存：API key、OAuth token、cookie、密码、原始环境变量、完整命令参数、完整 prompt／对话、思维文本、源码／diff、Graft 原始图输出、真实患者／客户数据、包含秘密的网络请求体。

错误信息先映射为安全 code；详细 stderr、报告正文及绝对路径不直接进入 Dashboard。需要本地查看原始报告时，由独立授权的安全预览能力处理，不在导出中自动包含它。

HTML／JPEG／PDF／CSV 均应用相同脱敏规则；CSV 不能成为绕过页面脱敏的通道。“全部数据”始终指**指定范围内、已采集、已授权且属于本协议的安全统计／审计数据**。

### 10.4 保留、容量与清理

| 数据 | 默认策略 |
|---|---|
| 原始审计事件／任务历史投影 | 首版不自动删除历史；500 MB 提醒，2 GB 强提示容量处理建议 |
| 临时 ReportSnapshot | 默认 24 小时；创建时告知有效期；过期清理仅触及本扩展生成目录 |
| 导出临时副本 | ready 后默认保留 24 小时；用户浏览器下载文件不由服务清理 |
| 数据库升级备份 | 不自动删除；用户确认后按明确备份 ID 处置 |
| 源 task.md／测试报告／handoff | 永远不由统计清理功能删除 |

以后启用历史保留期时，必须预览受影响数据范围、取得明确确认，并记录 `history_floor`、删除时间和原始明细不可用区间。只保留聚合不等于仍能导出原始明细。

数据库升级使用版本化 migration、事务和一致性备份；不得仅复制正在写入的主 DB 文件而遗漏 WAL。降级遇到未来 schema 拒绝修改。原始事件受损时停止涉及它的可信统计，不能默默清库重建并宣称完整。

### 10.5 审计可信度边界

可在本地事件中保存前序摘要／批次摘要，用于检测意外损坏和明显修改；它们不能阻止同一设备管理员重写数据库、密钥和整条链，也不证明外部时间、真实用户或法律意义的不可抵赖。

本期目标是**可追溯的工程审计与使用汇总**。独立可信签名、远端只追加存储、法务保留和组织审计策略属于未来中央平台能力。

---

<a id="section-11"></a>

## 11. 未来 Dify／团队平台的预留设计

### 11.1 必须现在预留，不能现在启用

| 预留项 | 当前语义 | 未来用途 |
|---|---|---|
| `tenant_id / workspace_id` | null 或本地明确命名空间；不能自报即获得权限 | 团队隔离和权限求交集 |
| `installation_id / device_id / actor_id` | 本地 ID 与显式绑定 | 跨设备来源、主体映射 |
| `initiated_by / requested_by / executed_by` | 当前本地来源 | 区分 Dify 发起、用户批准、本机实际执行 |
| `external_refs[]` | 默认空数组 | Dify app／conversation／workflow_run／message，以及其他平台对象引用 |
| `request_id / operation_id / causation_event_id` | 本地请求关联 | 跨系统幂等、请求追踪 |
| `trace_id / span_id / parent_span_id` | 可为空；不伪造宿主 trace | 后续观测链关联 |
| `permissions / capability scopes` | 本地查询与导出 scope | 服务端权限治理 |
| `approval_ref / authorization_context` | 本期无远程写入；必要时记录本地确认来源 | 未来绑定动作、对象、版本、有效期的授权 |
| `schema_version / producer_version / metrics_version` | 当前版本化 | 多版本客户端与数据迁移 |
| `source_watermark / delivery_cursor` | 已记录游标；无上云动作 | 后续增量投递和 at-least-once 去重 |
| `privacy.classification / exportable` | 本地安全数据分级 | 未来离机同步白名单 |

`external_refs` 示例：

```json
[
  {
    "system": "dify",
    "object_type": "workflow_run",
    "external_id": "opaque-external-id",
    "mapping_version": 1
  }
]
```

这是协议形状示例，不是本期自动写入内容。外部引用不携带 API key、完整对话或授权 token。

### 11.2 未来接入方式

官方 Dify Tool／HTTP Request 能消费外部接口，因此本期提供稳定 OpenAPI 和窄输入／输出模型即可；无需依赖 Dify 内部数据库、节点 ID 或新 Agent Sandbox 生命周期。（来源：[S9]、[S10]）

未来推荐演进顺序：

```text
本地 Facade / 查询模型
    → 可选本地只读 MCP Adapter
    → 经授权的本机主动 HTTPS 出站投递
    → Team Gateway 的只读投影
    → Dify 查询／摘要／通知
    → 单独安全设计后再考虑远程命令
```

云端 Dify 无法通过自己的 `localhost:6400` 访问开发者 PC。即使都部署在本机，Docker 容器的 localhost 也不自动等于宿主机；网络接线必须单独配置，不能通过把服务暴露到公网来“解决集成”。

### 11.3 外部写操作的未来限制

本期只定义扩展原则，不交付执行端点。未来命令至少需要独立 `command_id`、目标 device/project/worktree/task、期望源版本、动作白名单、请求者身份、一次性批准／有效期、幂等键和结果回执。

外部传入 `confirmed=true` 不是授权；Dify 的工作流跑成功不是本机动作完成。未来也必须保留业务 SOT，不让中央数据库与 task.md 双向任意写入。

---

<a id="section-12"></a>

## 12. 需求二：SBTD Workflow Local Dashboard

### 12.1 产品形态

默认打开 `http://localhost:6400`，显示**一个可滚动的完整报告页**。不是 Dify 画布，不是 IDE，不是新增任务管理系统。

OMP Stats 的参考点是：主题化卡片、紧凑数据布局、深浅主题、清晰状态和右上角分段时间控件。其当前 `RangeControl` 包含 `1h / 24h / 7d / 30d / 90d / All`；样式源码使用深紫表面、粉色强调和青色焦点提示。（来源：[S5]、[S6]、[S7]）

**保留视觉语言，改变信息架构：不复制 OMP 的按维度切换侧栏。**

### 12.2 总体布局

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ SBTD Workflow Dashboard        更新/主题   [1h 24h 7d 30d 90d All 自定义] [导出▾]│
├──────────────────────────────────────────────────────────────────────────────┤
│ 项目[全部▾] 使用者[全部▾] 宿主[全部▾] 模式[全部▾]  组件[全部▾]  更多筛选       │
│ 时间：2026-09-16 00:00 → 2026-09-23 00:00，Asia/Tokyo，结束不包含              │
│ 快照时间 / 来源水位 / 数据覆盖 / 尚未关联 / 数据缺口                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ 横向锚点：总览  任务  步骤  Gate  组件  验证  用量  项目/使用者  审计          │
├──────────────────────────────────────────────────────────────────────────────┤
│ [活动任务] [完成任务] [执行轮次] [有效 Gate 证据] [验证结果] [数据完整性]        │
├──────────────────────────────────────────────────────────────────────────────┤
│ 任务状态分布（整行；非转化漏斗）                                             │
│ 任务／运行趋势                              │ 模式分布与模式决策             │
├──────────────────────────────────────────────┼───────────────────────────────┤
│ 步骤耗时与重试                              │ 阻塞／中断及原因               │
├──────────────────────────────────────────────┴───────────────────────────────┤
│ Gate 适用性 × 执行结论 × 证据状态矩阵；覆盖不足提示                           │
├──────────────────────────────────────────────┬───────────────────────────────┤
│ 组件使用：已配置／已载入／已调用              │ 组件失败、版本与宿主分布        │
├──────────────────────────────────────────────┴───────────────────────────────┤
│ 验证与证据：Unit / API / Web / Mobile / 原生报告 / 源码版本 / 场景范围         │
├──────────────────────────────────────────────┬───────────────────────────────┤
│ 宿主／模型请求与 Token（条件性）             │ 报告费用／估算费用／未知        │
├──────────────────────────────────────────────┴───────────────────────────────┤
│ 项目／仓库／worktree 汇总表；使用者／未绑定主体汇总表                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ 任务清单摘要 / 当前展开的任务步骤时间线 / 审计事件预览                        │
│ 数据质量、采集器状态、指标定义、快照 ID、版本、导出说明                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

该框图是布局规格，不是已实现页面或像素级视觉稿。

### 12.3 版式规则

| 项目 | 要求 |
|---|---|
| 网格 | 桌面 12 列，主要图表 6+6，Gate／验证／明细表占满 12 列 |
| 宽度 | 浏览器响应式；标准导出报告宽度 1,440 CSS px |
| 留白 | 页面 padding 24px、Panel gap 16px 为起始建议；避免高密度挤压表格 |
| 字号 | 正文／表格默认 14px 以上；指标数值 24–32px；不能为了塞内容降到不可读 |
| 主题 | OMP 风格的暗色主题与浅色主题；默认跟随系统，用户可切换并记忆 |
| 页面滚动 | 一个主纵向滚动区域；核心 Panel 不使用内部独立滚动隐藏内容 |
| 导航 | 横向锚点只滚动定位，不切换或卸载 Panel；导出时导航可省略，但不能少内容 |
| 状态 | 颜色 + 文字 + 必要图标；unknown／partial 不用通过绿色 |
| 响应式 | 窄屏折为单列，控件可换行；时间选择和导出保持同一操作组、时间在前 |
| 可访问性 | 键盘操作、可见焦点、状态朗读、图表文本摘要，不能只靠 hover 显示关键数值 |

顶部可 sticky，但导出时取消 sticky/fixed，避免反复盖住图表。首版不提供拖拽布局、可隐藏核心 Panel 的自定义 Dashboard 或图表编辑器，以确保导出文档结构稳定。

### 12.4 Panel 明细与字段依赖

| Panel ID | 内容 | 必需字段／指标 | 数据不足时 |
|---|---|---|---|
| `overview` | 六个核心 KPI 与样本规模 | tasks、runs、gate evidence、validation、coverage | 展示 unknown／partial 与原因 |
| `task-lifecycle` | 范围末状态及范围内完成／重开 | task_uid、状态历史、as_of | 明确区分最新观察与历史范围末 |
| `activity-trend` | 活动、完成、调用的分桶趋势 | occurred_at、bucket、source health | 缺口桶用断线／阴影，不伪造 0 |
| `mode-decisions` | 模式分布、推荐／保留／接受 | mode_at_event、mode_source、decision events | 未绑定模式单列 |
| `step-performance` | 各步骤次数、p50/p95、重试 | step_definition、attempt、duration_basis | 样本不足时不给有误导性的分位数 |
| `blockers` | 阻塞、暂停、中断、原因 | interval、reason_code、closure_quality | 未闭合区间标示仍在观察／未知 |
| `gate-matrix` | required／not-required／undecided 与结果、证据 | GateEvaluation、scope_revision | declared-only 与 validated 明显区分 |
| `component-usage` | Skill／Tool／MCP／runner 的载入和调用 | component_kind、invocation、version | 安装存在不算调用 |
| `validation-evidence` | runner/case/重试、E2E scope、来源版本 | validation、artifact、source revision | HTML存在或诊断输出不能自动通过 |
| `host-model-usage` | 宿主／模型角色、请求、token／费用 | request_id、raw usage mapping、billing_basis | 未提供 usage 显示不支持／未知 |
| `project-actor-summary` | 项目、worktree、主体汇总 | IDs、actor binding、leaf task scope | 本机未绑定主体独立行 |
| `task-audit-detail` | 任务摘要、步骤时间线、事件预览 | task/run/step/event关联 | 标记当前预览行数和完整数据总量 |
| `data-quality` | 来源、缺口、延迟、错误、口径版本 | CollectionHealth、DatasetManifest | 必须始终存在，不能随导出隐藏 |

**工作流可视化不是假定的固定流水线。**多个任务汇总页显示状态分布；点击任务后在同页内联显示真实 StepRun 时间线和依赖／父子关系，支持并行、重试、阻塞和续接。default／lite 不显示未要求执行的 strict Gate 为失败。

### 12.5 时间筛选与交互

- 右上角顺序：可选刷新／主题 → **时间范围 → 导出**。
- 分段按钮沿用 OMP 的预置范围；新增“自定义”打开起止日期／时间和时区选择。
- 默认 `24h`；记忆上次 preset，但每次新查询重新解析相对窗口 anchor。
- 应用筛选后全页 Panel 与详情使用同一 snapshot；加载中保留上一份已完成视图并标明“正在更新”，不混合新旧数据。
- 无效起止、未来全空范围或 unsupported 组合有明确提示；不能 silently 回退 24h。
- 项目、宿主、模式等筛选与时间共同生效，当前范围摘要必须写出完整条件。
- 图表点击默认只在同页展开明细；若明确选择“筛选此项”，必须更新顶部 filter chip、全页快照和导出范围。
- 面板查询错误不显示 0；显示 error／retry。只有真正完成所有核心取数的页面才允许正常导出。

### 12.6 刷新、过期与分页

服务运行时可每 30 秒检查是否有新的已入库数据；更新采用整份快照替换。手动“刷新来源”只刷新统计数据，不执行 Graft rebuild／测试／业务动作。

底部明细允许分页／内联展开，默认提供任务摘要 Top 20、事件预览最新 50 条，并明确显示“展示 N 条／范围内总 M 条”。这些是**页面表达范围**，不是 API／CSV 的数据截断。汇总图表可用 Top 10 + Others，但总量要闭合且可查完整分组。

页面底部标注：

> 全页报告导出包含所有统计 Panel、其图表／表格，以及当前展开的详情；CSV 包含筛选范围内全部安全结构化记录，不受预览行数限制。

---

<a id="section-13"></a>

## 13. 导出产品规格

### 13.1 四种格式的语义边界

| 格式 | 输出 | 包含 | 不包含 |
|---|---|---|---|
| HTML | 单个 `.html`，可离线打开 | 全页报告、内联样式／图表、显示的数据、筛选、质量说明、快照版本 | 外部 API 依赖、用户秘密、未展示的原始日志／源码 |
| JPEG | 单个 `.jpeg` 长图 | 与报告页一致的全部视觉内容，自上而下完整捕获 | 当前屏幕外被裁掉的内容、伪造的分页截图拼包 |
| PDF | 单个 `.pdf`，可多页 | 同一报告内容，合理分页、标题／图表／表格／页码 | 只截第一页、只含图表不含解释、把所有内容压成不可读一页 |
| CSV | 单个 `.csv` | 同一筛选范围全部授权统计和审计数据族、完整分组／明细 | 图表图片、页面布局、仅当前表格页／Top N 的子集 |

“全页”指所有逻辑报告 Panel，包括当前视口以下的区域；不要求用户先滚动到页底。折叠的核心 Panel 在导出文档中展开；tooltip 中的必要指标转换为常驻文字／图例。

HTML／JPEG／PDF 不自动追加几百万条底层事件。底部预览／当前展开详情按页面明确展示的行集导出，并保留“展示 N／总 M”说明；完整明细由 CSV 导出。这避免把“全部页面内容”误实现为“无限长原始数据转图片”。

### 13.2 导出菜单与主路径

菜单仅提供四个主要选项：`HTML 网页`、`JPEG 长图`、`PDF 文档`、`CSV 数据`。用户选择一种格式即可开始生成，无需进入第二个设置表单；常用导出参数已由本 PRD 固定。

```text
点击导出 → 选择格式
    → 固定当前已完成 snapshot_id + 页面展示状态
    → 预检数据完整性、renderer／容量、授权与脱敏
    → 生成目标文件
    → 校验格式、范围、Panel／行数及摘要
    → 浏览器下载一个文件
```

导出期间自动刷新不改变所选快照；用户之后更改页面筛选，也不能影响正在生成的文件。界面显示本次导出的固定时间范围与格式，可以取消；不能把后一次筛选写到前一次文件名中。

正常已授权导出无需再次确认。只有首次启用 renderer、敏感数据例外或显式放宽范围才走独立确认；不在每次导出时重复问已确认设置。

### 13.3 单一 ReportDocument

前端应提供可复用 `ReportDocument(snapshot, presentation_state)`，页面主体与导出共用相同 Panel 定义和数据绑定。建议图表优先使用安全 SVG／原生可序列化图形；使用 Canvas 的图表必须在快照导出时正确栅格化。

不能直接“保存整个 SPA 的 outerHTML”就声称 HTML 可离线：动态图表、外部 CSS／JS、Canvas 内容和 localhost API 都需要被替换为内联、安全、固定的报告内容。

`presentation_state` 至少记录主题、标准报告宽度、展开的明细对象、表格排序、当前预览行集、Panel 顺序和图例状态。隐藏某条系列属于显示状态，导出必须保留说明；不得因此改变 CSV 数据范围。

### 13.4 HTML

必须：

- 单文件，自包含 CSS 和图表；默认静态内容，不加载外部脚本、CDN、字体或 localhost 数据。
- 文件复制到另一台离线设备，仍可看到全部 Panel、关键数字、图例和文字。
- 可选择／搜索正文文字，图表附带文本摘要；使用系统字体及明确 CJK fallback，不把当前机器字体路径写入文件。
- 用户可控标题、错误文本、任务名与 SVG 内容先转义／净化，不能执行脚本或触发外链请求。
- 不嵌入隐藏的完整审计数据库、秘密字段或原始对话 JSON。

允许少量无网络的可信展示脚本，但没有脚本时仍须显示完整报告；核心数据不能依靠执行 JavaScript 才出现。

### 13.5 JPEG

推荐受控 Chromium 渲染同一静态报告，使用 JPEG full-page 截图；Playwright 官方提供 JPEG、full-page 等截图能力。（来源：[S12]、[S13]）

目标默认值：报告宽度 1,440 CSS px、2x 输出、quality 90、不透明背景、当前主题。结果应为一个完整长图，不含浏览器边框和滚动条。

导出前等待字体、图表和图片完成；关闭动画、虚拟列表、内容延迟渲染、sticky／fixed 遮挡和会变动的时间显示。不能只截图 viewport。

**超长页面限制：**单张图片受编码器、内存与解码器限制，不能承诺无限长度。首版产品建议预检上限为单边 32,000 px、总像素 80 MP，并在目标平台实测后冻结。这是产品支持上限，不是宣称所有浏览器都保证该值。

若 2x 超限，可在仍保持完整内容和至少 1x 标准宽度时降为 1x，并在生成前显示说明；若仍超限则返回 `EXPORT_IMAGE_SIZE_LIMIT`，不截断、不拆成多个文件、不伪造成功。提示该页面可改用 HTML／PDF 或收窄展示详情。默认核心汇总页必须在验收支持范围内完成 JPEG 导出。

### 13.6 PDF

推荐使用受控 Chromium 的 PDF 能力。`page.pdf()` 支持页面输出、背景等参数，导出时需明确 screen／print 样式，而不是假设浏览器打印会与页面相同。（来源：[S13]）

首版默认 **A3 横向、10mm 页边距、保留当前主题／背景**，使用与 1,440px 报告接近的可读网格；PDF 可以多页，但只有一个文件。以内容完整和可读优先，不要求所有内容挤进单张 PDF 页面。

必须：

- 全部 Panel 在文档中有序出现；图表尽量整块分页。
- 长表按行跨页，重复表头；不截行、不横向裁切。
- 内容超过一页的 Panel 可以合理拆分，不滥用 `break-inside: avoid` 造成溢出或空白整页。
- 页脚写报告标题、范围、snapshot_id 简写和页码；第一部分写明时区、覆盖与未知数据。
- 优先保留可搜索文字／矢量图表，不用一张极长位图塞入 PDF 冒充正式文档。
- 中／日／英混合文字可显示；实际导出字号与对比度通过视觉验收。

### 13.7 Renderer 依赖与隔离

HTML／CSV 不依赖浏览器 renderer。JPEG／PDF 的受控浏览器是本扩展专用导出依赖，不是业务项目的 Playwright 测试依赖；不得在用户项目安装包或改变其 lockfile。

安装 Dashboard 时明确说明可选导出运行时的磁盘与依赖，并取得授权。用户选择安装完整功能后，JPEG／PDF 必须在离线环境可用；缺依赖时菜单标注不可用及原因，不能说四格式已经验收通过。

Renderer 使用独立临时 profile，不复用用户 Chrome／Codex／OMP 登录态。只渲染服务器生成的安全报告，不接受任意 URL／HTML；禁止外部网络及任意 `file://` 读取。每次最多一个图像／PDF 作业运行，避免抢占本地开发资源。

### 13.8 CSV 数据集：一个文件，多个明确数据族

单 CSV 没有多 sheet。采用 **统一固定表头 + `record_type` 数据族 + 明确粒度**，而不是四处拼接不同表头、ZIP 多文件或把整个对象塞到一个 JSON 单元格。

| record_type | 一行表示什么 | 是否受页面 Top N／分页限制 |
|---|---|---|
| `metadata` | 本次查询、版本、范围、质量、数据族总数等命名元数据 | 否 |
| `metric` | 一个 metric_id × bucket × 分组组合的统计值 | 否，导出完整分组与桶 |
| `task` | 一个任务在该快照下的状态／归属／来源 | 否 |
| `run` | 一个执行轮次，含范围相交信息 | 否 |
| `step` | 一个步骤 attempt | 否 |
| `gate` | 一个 Gate 作用域评估实例 | 否 |
| `component` | 一个逻辑组件／版本的可用性与来源 | 否 |
| `invocation` | 一个真实调用 attempt | 否 |
| `validation_run` | 一次原生验证运行 | 否 |
| `validation_case` | 一个 case 的一次原生尝试 | 否 |
| `usage` | 一个去重后的 usage 记录 | 否 |
| `artifact` | 一个获授权的安全产物引用与校验状态，不含原始文件正文 | 否 |
| `event` | 一条有效审计观察／必要更正关联 | 否 |
| `data_quality` | 一个来源缺口、限制或不可关联记录说明 | 否 |

此设计让一个 CSV 包含所有需要审计的关联数据，但**不是让使用者把全文件所有数值直接相加**。`record_type=metric` 为汇总；明细族用于核验。数据字典必须明确可加性，防止汇总行和明细行双算。

#### 固定字段分组

首版实际 CSV schema 由机器可读文档发布；至少包括以下稳定列，未适用字段留空：

```text
export_schema_version, snapshot_id, record_type, record_id, row_grain,
range_from, range_to, timezone, as_of, metrics_version,
project_id, repository_id, worktree_id, actor_id, actor_alias,
host_kind, host_version, branch_alias, task_uid, logical_task_id, task_run_id,
session_id, step_run_id, parent_step_run_id,
component_id, component_kind, component_version,
invocation_id, attempt_id, attempt_no,
gate_id, gate_eval_id, gate_scope_revision, validation_run_id, case_id, artifact_id,
event_id, event_type, source_id, source_event_id, occurred_at, recorded_at,
started_at, ended_at, duration_ms, duration_basis,
workflow_mode, mode_source, previous_status, status, raw_result, normalized_result, reason_code,
operation_status, state_persisted, audit_status,
applicability, evidence_status, observation_level, source_kind,
validation_scope, tests_total, tests_passed, tests_failed, tests_skipped, tests_unknown,
provider, model, billing_basis, currency,
input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
cost_reported, cost_estimated,
metric_id, metric_value, unit, numerator, denominator,
bucket_start, bucket_end, group_dimensions,
workflow_source_revision, source_commit_sha, worktree_revision, task_document_revision,
scope_revision, revision_state, relation_role,
coverage_state, warning_code, metadata_key, metadata_value
```

`group_dimensions` 可为固定规范的 JSON 小对象，仅用于可变分组键；主要分析字段必须独立列，不用它替代 project／actor／component 等常用维度。多维复杂扩展后续版本新增列，不能悄悄改变既有列含义。

`relation_role=activity | context | quality` 区分范围内事实、为关联而附带的实体／起始状态、数据质量说明。范围外的 run 起始上下文只作为 context 附带，不制造范围内开始次数。

#### CSV 内容与安全要求

- UTF-8 BOM、标准 CSV 引号／逗号／换行转义，方便常见电子表格应用打开；内部字段和枚举稳定使用英文，用户别名可为中日文。
- 时间为 ISO 8601；数值不带千分位和货币符号；币种独立列；null 留空，不能替换成 0。
- 用户可控文本中可能触发公式的 `= + - @` 及前导控制字符按文本安全策略处理，并记录转义策略版本；负的**合法数值列**不作为恶意文本处理。CSV 公式注入风险是已知风险。（来源：[S14]）
- 不通过构造 `="..."` 的 Excel 公式来保留 ID；opaque ID 用非纯数字格式，原逻辑 ID 按安全字符串输出。
- 同一数据族按稳定字段排序；元数据记录每族行数、来源覆盖和过滤范围，方便完整性核对。
- 全量遍历 snapshot dataset cursor 或服务端流式生成，不能只导出浏览器已加载内容。
- 超出本期已验证的数据规模时预检并明确失败，不输出“成功但只保留前 10,000 行”的文件。

简化示例（实际文件使用完整固定列）：

```csv
record_type,record_id,metric_id,metric_value,unit,task_uid,status,relation_role
metric,metric_demo_01,tasks.completed_unique,1,count,,,activity
task,task_demo_01,,,,task_demo_01,done,context
event,event_demo_01,,,,task_demo_01,done,activity
```

上例的一条 metric 与一条 event 表示同一完成事实的两个视角，不是完成了两次。

### 13.9 文件命名与结果审计

建议：

```text
sbtd-report_<project-or-multi>_<from-local>_<to-local>_<timezone-slug>_<snapshot-short>.<ext>
```

文件名清理路径分隔符、控制字符及 Windows 不允许字符；不包含邮箱、HOME 绝对路径或凭证。All 的范围使用实际 earliest_available 与 effective_to。

生成结果记录 MIME、字节数、摘要、范围、Panel 列表、各数据族行数、renderer_version、脱敏版本和 warning。`export.generated` 表示文件生成成功；`export.download_served` 只表示服务已响应下载，不宣称用户已经保存、打开或发送给第三方。

本次导出操作事件晚于已固定水位，不回流到当前文件而导致“导出一次就修改自己统计”的递归。

### 13.10 导出失败与恢复

| 场景 | 处理 |
|---|---|
| 正在切换筛选、页面还没有完整新快照 | 导出按钮禁用，并显示正在更新；不导出混合数据 |
| 某核心 Panel 请求失败 | 阻断正常导出；用户可显式选择“包含错误说明的诊断导出”，文件明显标记 partial，不冒充完整报告 |
| 来源覆盖本来就是 partial，但所有查询成功 | 允许导出，完整保留覆盖不足说明 |
| 字体／图表未完成渲染 | 等待确定性 ready 信号；超时则失败，不输出空白图 |
| renderer 崩溃／磁盘不足 | 保留作业错误，不返回零字节“成功文件”；清理本次拥有的半成品 |
| 用户取消 | 停止本作业并删除其临时文件；不终止其他业务测试或 Agent |
| 快照过期 | 返回 410；重新取数生成新 snapshot_id，并告知不是同一次数据 |
| 下载中断 | 在有效期内下载同一产物，摘要不变；不能重新取实时数据替换 |


---

<a id="section-14"></a>

## 14. 非功能要求与技术取舍

### 14.1 性能目标

以下是**待实现验收的产品目标，不是已经实测的性能结论**。固定参考机建议为 4 个逻辑 CPU、8 GB RAM、本地 SSD；使用 macOS 和 Windows 实机记录版本、数据规模与结果。

| 对象 | 目标 |
|---|---|
| 本地采集 SDK | 正常路径附加延迟 p95 ≤ 20ms；I/O 异常不得无限等待 |
| 查询规模 | 参考数据集 100 万条安全事件、1 万任务、10 万步骤；大小分布在测试报告明确 |
| 常用 24h／7d 汇总 | 热查询 p95 ≤ 1 秒；冷查询 p95 ≤ 3 秒 |
| 审计分页 | 100 行查询 p95 ≤ 500ms，使用索引／游标，不每次全表扫描 |
| UI 首次可用 | 服务已启动、本地正常数据条件下 ≤ 3 秒显示核心 Panel；后续变化不闪屏清空全页 |
| 已采集事件到可见 | 正常采集与服务开启下 ≤ 30 秒；必须同时显示实际延迟 |
| 导出基准 | 13 个核心 Panel、1,440px 标准宽度、典型报告高度 ≤ 12,000 CSS px |
| HTML 导出 | 基准报告 ≤ 5 秒 |
| JPEG／PDF 导出 | 已安装且可启动 renderer 的基准报告 ≤ 20 秒；超时可配置、可取消 |
| CSV 导出 | 100 万行基准数据流式生成目标 ≤ 60 秒；不要求一次加载全部数据到内存 |
| 并发 | 允许多个只读浏览器页面；同一用户一个重型 renderer 作业执行，其他有界排队 |
| 资源控制 | 重型导出设置内存／像素／时间／临时磁盘上限；上限经过平台验证并展示，不静默降数据 |

大数据导出属于有进度的本地作业，不阻塞用户继续用 OMP／Codex。这里描述的是待开发产品行为，不是本 PRD 的交付等待时间。

### 14.2 平台与浏览器

| 平台 | 核心 API／采集 | Dashboard | JPEG／PDF |
|---|---|---|---|
| macOS Apple Silicon | 首发必验 | Chromium／Safari 访问 | 使用已验证的隔离 Chromium renderer |
| Windows 11 x64 | 首发必验，含 ACL／路径 | Edge／Chrome 访问 | 使用已验证的隔离 Chromium renderer |
| Linux x64 | CI 必验；本地运行支持 | Chrome／Firefox 基础访问 | 安装明确依赖后验证 |
| iOS／Android | 不提供本机运行时 | 不作为远程访问需求 | 不直接运行 exporter |

最终最低系统、Python、浏览器和依赖版本在实现初期锁定到实际验证版本；本 PRD 不虚构用户已经安装的版本。Windows 原生测试不能被 Linux 模拟路径测试替代。

### 14.3 推荐技术结构

| 项目 | 建议 | 理由与约束 |
|---|---|---|
| 核心 Runtime／Facade | Python，兼容现有 helper 接口 | 尽量复用 TaskStore／TaskRouter 等，不平行重写 |
| HTTP 层 | 轻量 ASGI 服务，候选 FastAPI；通过 ADR 定案 | JSON/OpenAPI；API 类型来自同一 schema，不复制协议 |
| 本地数据 | SQLite，原始事件与投影表职责分明 | 无外部数据库运维，方便本机部署；遵守 WAL／备份边界 |
| 前端 | React + TypeScript 的静态构建 | 与 OMP 视觉参考接近；由同一服务提供静态资源，不要求生产 Node Web 服务 |
| 图表 | 优先可序列化 SVG 渲染方案 | HTML 离线／PDF 可读性更容易保证；禁止从 CDN 加载 |
| 导出运行时 | 独立 Playwright／Chromium 适配器 | 统一 JPEG/PDF 渲染；不侵入业务项目测试环境 |
| 协议 | 版本化 JSON Schema／OpenAPI | 支持 CLI、UI、后续 MCP／Dify Adapter |
| 统计 | 确定性代码查询 | 不使用 LLM 计算计数、成功率、时间或生成审计事实 |

不引入 Redis、消息中间件、向量数据库、复杂 DAG 引擎或专用云端监控平台作为本期必需组件。使用现有项目成熟依赖时优先复用，最终选择以可部署性与验收为准。

### 14.4 可观测性扩展自身的可观测性

采集器／API／导出服务记录规范化错误码、作业耗时、积压、失败次数和最后成功时间。默认不将它们混入“开发工作流使用量”；提供单独 `activity_domain=workflow | runtime-observability` 分类。

若存储不可写，健康接口和本机会话提示仍尽可能暴露故障；但不能保证故障期间的全部记录都已保存。恢复后在已知边界上声明缺口，不伪造期间事件。

---

<a id="section-15"></a>

## 15. 实施阶段、依赖与交付门

本 PRD 的阶段名称为 **R1／R2**，避免与仓库现有 P0／P1／P2／P3 迁移和发布任务编号混淆。

### 15.1 实施顺序

```text
R1.0 数据与权限契约
  → R1.1 Facade／来源注册／事件存储
  → R1.2 Codex／OMP／Runtime／报告采集
  → R1.3 指标／查询／快照／完整 CSV 数据集
  → R1.4 Runtime API 独立验收
  → R2.0 单页报告模型／OMP 风格 UI
  → R2.1 四格式导出菜单与实现
  → R2.2 跨平台、隐私、安全、性能及导出一致性验收
```

UI 样式探索可以使用标明为 demo 的夹具提前进行，但不能算 R2 完成；R2 必须对接已经通过 R1 验收的真实接口，不能把 mock panel 数字当作最终产品。

### 15.2 需求一工作包

| ID | 工作包 | 依赖 | 产物 | 完成门 |
|---|---|---|---|---|
| R1.0 | 数据字典、事实源、事件 schema、指标目录、授权模型 | 无 | JSON Schema、API 草案、ADR、golden dataset | 名词、分母和去重规则可执行测试通过 |
| R1.1 | Facade 与旧 helper 兼容包装、显式项目注册 | R1.0 | 库接口、调用适配、权限／只读测试 | 开关关闭前后业务副作用等价 |
| R1.2a | 事件库、去重、spool、checkpoint、质量记录 | R1.0–1 | 本地存储与恢复机制 | 重放、乱序、截断、崩溃、部分失败验证 |
| R1.2b | Codex／OMP 与 Runtime 来源适配器 | R1.1–2a | 宿主 capability matrix、结构化回执 | 两宿主真实 smoke；不支持能力如实标记 |
| R1.2c | task 历史与验证产物导入 | R1.2a | 安全解析器、证据关系 | 不伪造历史时间／通过状态 |
| R1.3 | 统计 API、历史状态、快照、数据集与 CSV | R1.2 | OpenAPI、分页查询、CSV serializer | 对 golden dataset 计数一致且不截断 |
| R1.4 | 安全、审计边界和版本兼容验收 | 全 R1 | 本地 API 包、文档、报告 | UI 尚不存在时所有 R1 用户场景可完成 |

### 15.3 需求二工作包

| ID | 工作包 | 依赖 | 产物 | 完成门 |
|---|---|---|---|---|
| R2.0a | OMP 视觉参考与单页布局 | R1 schema 固定 | Panel registry、ReportDocument、设计规格 | 无维度侧栏，所有核心维度在同页 |
| R2.0b | 时间／维度筛选、数据质量、内联详情 | R1.4、R2.0a | 本地 Dashboard | 同一 snapshot 全页更新、无混合数据 |
| R2.1a | 静态 HTML 与 CSV 菜单接入 | R2.0b | 单文件离线 HTML／全量 CSV | 内容／行数／脱敏验收 |
| R2.1b | 隔离 renderer、JPEG／PDF | R2.1a | 完整长图、分页 PDF | 无截断／空白图，中文和日文可读 |
| R2.2 | 跨平台 E2E、安全、性能、导出对账 | 全 R2 | 发布候选、测试证据、安装卸载手册 | 四格式都通过，不能以浏览器打印手工操作替代 |

### 15.4 各阶段不允许延期到下一阶段的事项

- 原始审计与可重建投影的边界、稳定 ID、时间口径、Dify 预留结构：**必须在 R1.0 固定。**
- 宿主实际采集与证据等级：**不能等 UI 做完再补。**
- Snapshot／全量数据集／CSV schema：**属于 R1，不由前端临时拼出来。**
- 四格式选择与一键导出：**属于本期 R2 的完整范围，不只交 HTML／CSV。**
- Dify 真实接入、远程控制、组织权限：**不属于 R1／R2 完成门，不可为了它们拖延本地产品。**

---

<a id="section-16"></a>

## 16. 验收标准与需求追踪矩阵

每条 AC 需有实际测试名称、命令、预期结果、证据路径、源代码 revision 和平台。本文编号是目标验收清单，不代表已经通过。

### 16.1 Runtime 与审计

| AC | 要求 | 验证方式 |
|---|---|---|
| AC-01 | 观察库／UI 不修改任务 mode/status/history | 对查询前后业务文件摘要与 Git diff 对比 |
| AC-02 | 关闭扩展后原工作流仍可使用 | Codex／OMP 各一轮受控任务，验证无 API 服务前置 |
| AC-03 | 完全只读任务不落审计／状态文件 | 显式只读场景，全授权目录前后比对 |
| AC-04 | 只统计明确注册根，不扫描 sibling／HOME | 访问拦截与目录诱饵测试 |
| AC-05 | 并列 worktree 分开，已授权同仓任务映射不重复 | 移动／归档／复制／worktree 场景 |
| AC-06 | 同 source_event_id 重放不重复计数 | 同批次重复 ingest 三次，计数不变 |
| AC-07 | 相同来源 ID 内容冲突被拒绝 | 返回 409，原记录完整保留 |
| AC-08 | 乱序／迟到事件进入新快照，不修改旧快照 | 固定 snapshot 后补迟到事件，比较新旧水位 |
| AC-09 | 加载 Skill 不等于调用成功 | 仅 file-read 事件只能增加 loaded 指标 |
| AC-10 | Gate 自报 passed 不能自动成为有效证据 | 无原生证据回执／缺失报告／stale 报告场景 |
| AC-11 | default／lite 不机械出现所有 strict Gate 失败 | 确认模式与 required plan 的对照测试 |
| AC-12 | task done 不等于发布／全部验证通过 | 独立结果字段与 Panel 显示断言 |
| AC-13 | 未关联任务／主体保留 unknown | 混合 session 不自动按时间猜 task |
| AC-14 | 父子 Agent 与 usage 去重 | 父级含子级汇总的夹具，账目不双算 |
| AC-15 | 成功 task 写入后审计失败不重复业务执行 | 在末尾审计持久化位置故障注入 |
| AC-16 | 历史未知时间不补当前时间 | 无历史时间 task 导入，趋势不伪造活动 |
| AC-17 | 中断／休眠不被算成长时间持续工作 | start 后中断／恢复，无结束证据时状态明确 |
| AC-18 | 覆盖不足和 unsupported 可查询／导出 | 每类来源 capability matrix 与 gap fixture |
| AC-19 | 没有费用／token 时不填 0 | 缺 usage 宿主的真实 smoke |
| AC-20 | 任务和报表投影可重建，原始事件不被清空 | 重建命令前后原始事件计数／摘要一致 |

### 16.2 时间、统计与接口

| AC | 要求 | 验证方式 |
|---|---|---|
| AC-21 | `[from,to)` 边界一致 | 边界前／等于 from／等于 to／to 后事件 |
| AC-22 | IANA 时区与 DST 正确 | 东京、UTC、含 DST 时区 golden cases |
| AC-23 | 跨边界 run 的次数与时长不混淆 | 范围前启动、范围内结束的 span |
| AC-24 | 历史范围末状态不使用现在状态 | 过去 done、后来 reopened，查询两个时间点 |
| AC-25 | required Gate 分母有依据，无分母显示未知 | 未定 applicability 与已知 plan 对照 |
| AC-26 | 0 样本成功率不是 100% | 零样本／全部 blocked 的数据集 |
| AC-27 | 任务 unique、完成事件和父任务不双算 | 完成→重开→完成 + parent/child 夹具 |
| AC-28 | 所有 Panel 的指标来自同一快照和版本 | 多接口返回 snapshot/watermark 一致 |
| AC-29 | cursor 全量遍历不漏不重 | 跨多页导出后与源快照总数核对 |
| AC-30 | 不支持的 filter／metric 明确拒绝 | OpenAPI 负向用例 |
| AC-31 | Dify 字段可以为空，未来 refs 可无损透传 | schema v1 的外部引用 fixture |
| AC-32 | 本期不存在远程业务控制端点 | 路由清单、安全扫描与 capability 响应 |

### 16.3 Dashboard

| AC | 要求 | 验证方式 |
|---|---|---|
| AC-33 | 显式启动后 localhost:6400 可打开 | macOS／Windows 原生启动与退出测试 |
| AC-34 | 端口占用不杀其他进程、不静默换地址 | 占用 6400，显示冲突及显式替代端口选项 |
| AC-35 | 无按维度切换主内容的侧栏 | DOM／截图检查，全部核心 Panel 同一文档流 |
| AC-36 | 时间筛选位于导出按钮左侧 | 桌面与窄屏布局测试 |
| AC-37 | 预置范围 + 自定义 + 时区共同生效 | 1h/24h/7d/30d/90d/All/custom 全部 E2E |
| AC-38 | 切筛选不混合新旧 Panel | 人工延迟部分接口，snapshot 一致性断言 |
| AC-39 | partial／unknown／error 不显示假 0 或绿灯 | 三类非完整数据视觉测试 |
| AC-40 | 任务真实步骤、重试、并行和阻塞可内联查看 | 有分支与重试的真实／受控执行数据 |
| AC-41 | 主要统计无内部滚动截断 | 默认报告及长内容场景截图 |
| AC-42 | 中日英、键盘及深浅主题可用 | 文本渲染、focus、radio/menu 和可访问性检查 |

### 16.4 导出与安全

| AC | 要求 | 验证方式 |
|---|---|---|
| AC-43 | 一个菜单有且仅有四种主要格式 | 逐项点击后生成正确扩展名／MIME 的单个文件 |
| AC-44 | 全页导出不受当前滚动位置影响 | 在顶部直接导出，底部 sentinel／Panel 仍存在 |
| AC-45 | 所有逻辑 Panel 被导出，无漏图 | Panel manifest 对账 + JPEG/PDF 视觉检查 |
| AC-46 | HTML 离线、服务关闭仍完整可读 | 网络禁用、拷贝目录／另一环境打开，零外部请求 |
| AC-47 | JPEG 真正为一张完整长图 | 文件解码、尺寸、上下边界标记及图表检查 |
| AC-48 | JPEG 超限明确失败，不截断、不分包 | 超长详情构造、预检错误与无半成品成功文件 |
| AC-49 | PDF 单文件多页不漏 Panel／表格行 | 逐页渲染检查、文本提取、长表跨页对账 |
| AC-50 | CSV 包含全部范围数据，不限 Top N／当前页 | 10,001+ 条明细与多维分组，按数据族逐行核对 |
| AC-51 | 同快照四格式关键数值一致 | HTML/PDF 文本／JPEG 显示与 CSV metric 行比对 |
| AC-52 | 导出期间新数据不影响当前文件 | 并发 ingest，旧 export 摘要／范围固定 |
| AC-53 | CSV 分隔／换行／公式注入安全 | 中日文、逗号、引号、换行、危险前缀、合法负数 |
| AC-54 | 导出无秘密、绝对路径、隐含原始对话 | 字节搜索与隐私 fixture；HTML 禁止隐藏敏感 JSON |
| AC-55 | 恶意任务名不能执行 HTML／SVG 代码 | XSS 和外部资源探针，离线打开不发请求 |
| AC-56 | 外部网页无法读取／伪造本地 API 数据 | CORS、Origin、CSRF、Host／DNS rebinding 测试 |
| AC-57 | 下载不能越界读取任意文件 | 路径穿越、猜测 export_id、跨会话下载测试 |
| AC-58 | renderer 不复用浏览器登录态、不联网 | 独立 profile 与网络拦截测试 |
| AC-59 | 导出取消／崩溃不损坏业务或审计数据 | 故障注入、原文件摘要对比 |
| AC-60 | 查询／导出自身不污染工作流活动统计 | 同一快照连续导出，开发活动指标不增加 |
| AC-61 | 原始事件清理有独立授权与范围说明 | 取消清理不动数据，批准后保留缺口／history_floor |
| AC-62 | 平台／性能目标有实际报告而非 README 自报 | 参考规模压测、原生 Windows／macOS 报告 |

---

<a id="section-17"></a>

## 17. 关键验收场景示例

以下是产品行为规格示例。实施仓库若允许 `.feature`，遵循其既有位置与语言；如果 640-skills 源仓有“不生成 .feature”的明确政策，使用指定规范路径，不为本 PRD 另行强制安装 Cucumber 等 runner。现有验证 Skill 也要求优先使用项目已有测试框架与可追溯场景。（来源：[S8]）

```gherkin
Feature: SBTD 本地统计与固定快照导出

  Scenario: 只读取 Skill 不代表执行通过
    Given 已观察到 Agent 读取 book-ddia-data-design 的 SKILL.md
    And 没有该 Gate 的执行回执或有效证据
    When 查询当前范围的组件与 Gate 统计
    Then 该 Skill 的 loaded 计数增加
    And 不增加 execution-observed 的成功计数
    And 该 Gate 不显示为证据有效的 passed

  Scenario: 切换时间范围时整个页面保持同一数据快照
    Given Dashboard 正在显示 snapshot-A 的 24h 数据
    When 用户选择 7d
    And 新快照的一部分 Panel 仍在加载
    Then 页面不混合 snapshot-A 和新快照的 Panel 数值
    And 导出新范围暂不可用
    When 新快照全部核心查询完成
    Then 全页切换到同一个 snapshot-B

  Scenario: 从页面顶部导出完整长图
    Given 报告页包含顶部至底部的全部核心 Panel
    And 用户从未滚动到页面底部
    When 用户点击导出并选择 JPEG
    Then 生成一个 JPEG 文件
    And 图片包含底部的数据质量与口径说明
    And 没有只捕获浏览器当前视口

  Scenario: CSV 不受页面预览行数影响
    Given 筛选范围内有 10001 条已授权审计事件
    And 页面只预览其中最新 50 条
    When 用户导出 CSV
    Then CSV 的 event 数据族包含全部 10001 条有效事件
    And metadata 记录相同的数据族行数
    And 文件不包含图表图片或页面 HTML

  Scenario: 导出期间继续开发不会改变本次报告
    Given 用户正在查看 snapshot-A
    When 用户开始导出 PDF
    And 本地 Agent 又产生一个新的 task.state_changed 观察事件且目标状态为 done
    Then 导出的 PDF 仍使用 snapshot-A 的水位与指标
    And 新事件仅在后续刷新后的新快照中出现

  Scenario: 模式已切换但保存失败时不伪造持久化
    Given Runtime 确认当前会话选择 strict
    And task.md 保存失败
    When 采集该操作结果并展示审计详情
    Then 显示当前会话选择 strict
    And 显示 state_persisted 为 false
    And 不把磁盘旧模式修改为 strict

  Scenario: 来源覆盖不足不等于没有使用
    Given 选定范围内 OMP 来源存在采集缺口
    When 查看组件调用趋势并导出 HTML
    Then 缺口区间有明确标识
    And 不显示该区间为已证明的零调用
    And HTML 包含相同的缺口说明

  Scenario: 没有 Dify 也能完整运行
    Given 用户未安装或配置 Dify
    And 本机断开外部网络
    And 完整导出运行时已获授权安装
    When 用户启动 Dashboard 并分别导出四种格式
    Then 本地页面与四种导出均可工作
    And 没有访问 Dify 或外部统计服务
```

测试场景使用事件目录中的 `task.state_changed`，以 `state.current=done` 表达任务完成；不新增平行的完成事件别名。

---

<a id="section-18"></a>

## 18. 测试与证据交付要求

### 18.1 测试分层

| 层级 | 必需覆盖 |
|---|---|
| 数据单元测试 | 状态映射、时间边界、时区、去重、父子归属、指标分母、CSV 编码 |
| 文件／数据库集成 | 原 helper 包装、只读、权限、symlink／junction、并发冲突、升级／备份／恢复 |
| 来源适配器测试 | 固定版本夹具、rotation、截断、未知字段、unsupported、重复事件 |
| 真实宿主 smoke | Codex／OMP 的实际读取／调用／状态操作／可用 usage，不能以 parser fixture 冒充 |
| API 契约测试 | 每个实际 method + path 的权限、范围、分页、错误与幂等 |
| 浏览器 E2E | 筛选、全页 Panel、详情、刷新、四格式导出、下载、失败恢复 |
| 导出视觉测试 | 暗／浅主题、长页、跨页表格、中日文字体、顶部／底部完整性 |
| 安全测试 | XSS、CSV 注入、CSRF、Host／Origin、任意文件读取、renderer 外联 |
| 故障与性能 | 采集失败、磁盘满、作业取消、休眠／崩溃、100 万事件查询／导出 |

### 18.2 Golden Dataset

建立一个不含真实账号／业务秘密的确定性数据集，至少包含：同任务完成两次、父子任务、两个 worktree、两个宿主、未绑定主体、并行子 Agent、重复／迟到事件、模式中途切换、Gate 不适用／不确定、declared-only、stale evidence、测试首次失败后通过、usage 缺失、跨时区边界、未闭合 span 和采集缺口。

Golden Dataset 为每个 metric 提供预期值及来源 ID 集；API、Panel、HTML、JPEG、PDF、CSV 都使用它验证一致性。JPEG 通过渲染前数据对账与视觉检查验证，不把高风险 OCR 当作唯一数值校验手段。

### 18.3 报告要求

每轮正式验证按现有项目惯例保存原生报告及同 stem 中文摘要，注明 source revision、worktree／dirty 状态、平台、真实命令、用例范围与未验证项。新 HTTP API 的测试矩阵必须逐条列出 `method + URI path`，而不是只列“统计接口已测”。

导出测试报告应附四格式样本、snapshot manifest、CSV 各数据族行数、Panel 对账结果、敏感数据扫描结果和 renderer 版本。测试样本使用合成数据，未经授权不提交开发者真实统计文件。

---

<a id="section-19"></a>

## 19. 风险、替代方案与未决实现项

### 19.1 主要风险

| 风险 | 影响 | 本 PRD 的应对 |
|---|---|---|
| 自然语言 Skill 很难自动证明执行 | 审计可能形成假通过 | loaded／declared／execution／evidence 分级；显式回执 + 真实来源 |
| 原状态文件与观察库不同步 | 页面展示过期事实 | 单向投影、来源 revision、reconcile、partial／stale 可见 |
| 为统计侵入原 SBTD 太深 | 增加开发失败面 | 可选采集、薄 Facade、旧路径兼容；UI 不参与任务控制 |
| 所有原始事件都放进单页 | 页面失控，图片无法导出 | 页面为完整汇总报告，细节明确预览；CSV 提供全量 |
| CSV 多数据族造成重复相加 | 汇总结果失真 | record_type、row_grain、metric 与明细分离及字典 |
| 字体／图表／PDF 分页差异 | 四种文件缺字／漏图 | 同一 ReportDocument、隔离 renderer、离线与跨平台验收 |
| JPEG 超长／大内存 | 崩溃或截断 | 固定支持边界、预检、可取消、明确失败，不伪造完整 |
| 本地 API 被恶意网页访问 | 泄露开发元数据 | loopback + Host/Origin + 鉴权 + CSRF + 最小 scope |
| 本地管理员可改统计 | 不具备独立可信审计 | 明确非不可抵赖；未来独立中央审计另行设计 |
| 为 Dify 过度建设团队平台 | v2 范围膨胀 | 本期仅协议、ID、权限和 refs 预留，不建云服务／控制面 |

### 19.2 已否决或降级的方案

| 方案 | 处理 | 原因 |
|---|---|---|
| 直接把所有统计放进 Dify | 本期否决 | 本地数据与控制不应以 Dify 为依赖 |
| 让 Dify DB 保存任务权威状态 | 否决 | 破坏 task.md SOT |
| 只解析 task.md 当前值做所有审计 | 否决 | 无法证明调用、耗时、重试及历史执行 |
| 把全部自然语言对话上传／交给 LLM 推断活动 | 否决 | 隐私风险高且不可靠，不是确定性审计 |
| 复制 OMP 的侧栏多路由统计页 | 否决 | 全页一键导出语义不清 |
| 所有图表各有独立时间范围 | 否决 | 很难形成可对账的统一报告 |
| CSV 只导出当前表格页 | 否决 | 不满足全部指定范围数据 |
| 依赖浏览器“另存网页／打印”作为唯一导出 | 否决 | 不能保证单文件离线、全 Panel 和一键体验 |
| 首版实现远程控制／工作流图编辑 | 延后 | 非当前两项需求，增加授权与业务写入风险 |

### 19.3 实现前需要通过 ADR 固定的事项

这些事项有本文默认建议，不要求用户重新确认已提出的产品需求：

| 事项 | 本文默认建议 | 何时固定 |
|---|---|---|
| 代码放置／打包 | 独立可选 runtime 扩展，兼容原 scripts，避免大范围移动既有文件 | R1.0 |
| 本地服务框架 | Python 轻量 ASGI + 类型化 DTO | R1.0 |
| 采集器版本矩阵 | 对目标 Codex／OMP 实际版本做能力探测；unsupported 明示 | R1.2 |
| 精确指标 schema | 本文目录作为初版，字段与计算代码同版本发布 | R1.0–3 |
| 身份和项目映射文件 | 用户私有 registry，不默认写项目 tracked 文件 | R1.0 |
| renderer 包分发 | 独立管理的 Chromium，安装时授权，业务项目零依赖变更 | R2.1 前 |
| 长图／CSV 最大支持规模 | 本文性能和容量目标通过真实平台试验冻结 | R2.2 前 |
| OMP 视觉复用程度 | 先参考视觉语言；复制代码时核验并保留适用许可证／声明 | R2.0 |

---

<a id="section-20"></a>

## 20. 最终交付清单与发布定义

### 20.1 需求一交付物

| 产物 | 必需内容 |
|---|---|
| Runtime Facade | 稳定方法、旧 helper 兼容层、只读／写入边界、结构化结果 |
| 采集组件 | Codex／OMP／Runtime／报告来源适配、版本和覆盖矩阵 |
| 存储模型 | 事件 schema、身份／关联模型、投影、checkpoint、备份／恢复 |
| 指标目录 | metric_id、维度、分母、去重、时间、未知数据、版本 |
| API | OpenAPI、接口样例、鉴权、错误码、cursor、幂等 |
| 数据集与 CSV | 完整范围提取、固定列字典、类型粒度、注入防护 |
| 安装／使用文档 | 可选启用、项目授权、统计关闭、升级、卸载和数据保留 |
| 测试证据 | 不依赖 UI 的 R1 全套测试和真实宿主 smoke |

### 20.2 需求二交付物

| 产物 | 必需内容 |
|---|---|
| Local Dashboard | localhost:6400、无维度侧栏的单页、全部核心 Panel |
| 筛选与详情 | OMP 风格时间控件 + 自定义、维度筛选、同页真实步骤／审计详情 |
| 导出 | 右上角四格式菜单、固定快照、单文件产物和一致性 manifest |
| ReportDocument | 页面与导出共用的渲染模型、离线 HTML、完整 JPEG、可读 PDF |
| 跨平台交付 | macOS／Windows 安装运行和导出证据；Linux CI |
| 运维／排障 | 端口冲突、来源不可用、库损坏、导出依赖、取消和容量限制 |
| 回归资产 | API／浏览器／视觉／CSV／安全／故障注入测试 |

### 20.3 完成定义

**需求一完成**：不启动 Dashboard 的情况下，能对真实获授权的本地 SBTD 执行进行采集、追溯、分级、去重、查询、固定快照和完整 CSV 数据提取，并如实说明不能采集的范围。

**需求二完成**：同一用户在本机打开 Dashboard，选择任意受支持时间和维度范围后，能看到同一快照的全部核心统计 Panel，并从一个菜单分别导出完整 HTML、JPEG、PDF 或全部范围 CSV；不要求连接 Dify，不改变原开发流程。

**整体发布完成**：上述功能、权限、隐私和真实平台验收通过，已知缺陷与容量边界写入说明。仅文档完成、mock 图表可展示、局部导出成功或单平台通过，均不等于整体发布完成。

---

<a id="section-21"></a>

## 21. 来源与证据索引

以下来源用于核对现有项目边界和外部能力。本文新接口、新字段、性能目标、布局及分期均为产品设计提案，不能误读为这些仓库当前已实现的能力。

| 来源 | 内容与使用位置 |
|---|---|
| [S1] | 640-skills 固定提交，作为本次项目基线 |
| [S2] | TaskStore 源码：任务事实源、单 writer、路径／分支／确认边界 |
| [S3] | TaskRouter 源码：确定性路由、显式输入、会话选择与持久化分离 |
| [S4] | strict Gate 参考：条件性评审、验证与完成门 |
| [S5] | OMP RangeControl 源码：预置时间范围和 radio 分段交互 |
| [S6] | OMP TopBar 源码：时间控件、更新状态、主题与同步布局参考 |
| [S7] | OMP Stats styles：主题 token、卡片和侧栏样式参考；本 PRD 不复制侧栏布局 |
| [S8] | project-validation Skill：项目命令、BDD traceability、原生报告与证据契约 |
| [S9] | Dify 官方 Tool Node：外部工具接口消费方向 |
| [S10] | Dify 官方 HTTP Request：HTTP 方法、鉴权、超时与响应处理 |
| [S11] | SQLite 官方 WAL：本地读写、单 writer 和部署边界 |
| [S12] | Playwright 官方截图／PDF说明：full-page、JPEG 与 PDF 能力 |
| [S13] | Playwright Page API：screenshot／pdf 参数与渲染行为 |
| [S14] | OWASP CSV Injection：表格公式注入风险 |

[S1]: https://github.com/KunoLu/640-skills/commit/03541a97f3804f8966cd5c4ff3f579793f9d4175
[S2]: https://github.com/KunoLu/640-skills/blob/03541a97f3804f8966cd5c4ff3f579793f9d4175/sbtd-workflow-onboard/scripts/sbtd_task_state.py
[S3]: https://github.com/KunoLu/640-skills/blob/03541a97f3804f8966cd5c4ff3f579793f9d4175/sbtd-workflow-onboard/scripts/sbtd_task_routing.py
[S4]: https://github.com/KunoLu/640-skills/blob/03541a97f3804f8966cd5c4ff3f579793f9d4175/sbtd-workflow-onboard/templates/skills/sbtd-task/references/strict.md
[S5]: https://github.com/can1357/oh-my-pi/blob/e4151593ace2781d1dc2f06d760301f88af3e9dc/packages/stats/src/client/app/RangeControl.tsx
[S6]: https://github.com/can1357/oh-my-pi/blob/e4151593ace2781d1dc2f06d760301f88af3e9dc/packages/stats/src/client/app/TopBar.tsx
[S7]: https://github.com/can1357/oh-my-pi/blob/e4151593ace2781d1dc2f06d760301f88af3e9dc/packages/stats/src/client/styles.css
[S8]: https://github.com/KunoLu/640-skills/blob/03541a97f3804f8966cd5c4ff3f579793f9d4175/sbtd-workflow-onboard/templates/skills/project-validation/SKILL.md
[S9]: https://docs.dify.ai/en/cloud/use-dify/nodes/tools
[S10]: https://docs.dify.ai/en/cloud/use-dify/nodes/http-request
[S11]: https://sqlite.org/wal.html
[S12]: https://playwright.dev/agent-cli/commands/screenshots-pdf
[S13]: https://playwright.dev/docs/api/class-page
[S14]: https://community.owasp.org/attacks/CSV_Injection

---

<a id="section-22"></a>

## 22. 修订记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v0.1 | 2026-09-23 | 首次形成 Runtime API／审计统计 → Local Dashboard／四格式导出的完整 PRD；明确 local-first、事实源、来源分级、单页报告、时间快照、CSV 全量与 Dify 预留边界 |

**最终建议：先把“数据能采到、来源能证明、统计能对账”做好，再把这些可信数据做成易查看、易导出的单页报告。Dify 保持未来适配选项，而不是本期产品的依赖。**
