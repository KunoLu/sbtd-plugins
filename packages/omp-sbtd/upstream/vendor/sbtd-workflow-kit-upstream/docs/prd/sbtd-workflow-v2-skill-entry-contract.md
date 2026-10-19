# SBTD v2 P0-04：公共／lite 入口与 strict 按需分层

## 交付与阶段边界

任务从 `main @ 4dbcba1e9c675a2618157d0aaea253075b5e9cda` 创建 `p0-04-sbtd-task-skill`，依赖 P0-03。主 [PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md) §14 是状态事实源。

P0-04以非discovery的entrypoint.md交付完整候选，避免先于catalog激活；P0-07将其整体移入正式source，当前入口为 [SKILL.md](../../sbtd-workflow-onboard/templates/skills/sbtd-task/SKILL.md)，保留model-invoked的name／英文description、公共路由与lite清单，不保留候选副本或兼容alias。源目录切换不等于用户HOME已同步或完整v2运行验收通过。

## 按需加载面

| 资产 | 读取时机 | 责任 |
|---|---|---|
| [公共入口](../../sbtd-workflow-onboard/templates/skills/sbtd-task/SKILL.md) | SBTD 任务执行、继续或模式选择 | 模式来源、先推荐暂停、拒绝保持、只读例外、lite 清单、共同安全及明确交付 |
| [strict.md](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/strict.md) | 执行已确认 strict 任务的适用 Gate | before-dev／check／finish-work、Book顺序、BDD、Ponytail／可读性、验证、独立review及release gate |
| [state.md](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/state.md) | 持久读写、恢复、重开、提升、归档 | 唯一task、branch/ID/引用核对、完整事件历史、原子单文件写入与跨文件失败边界 |
| [handoff.md](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/handoff.md) | 真实暂停、上下文切换或续接需要 | 非计数触发、无变化不重写、只读不落盘、任务模式优先与opt-out保持 |
| [task-data.schema.json](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/task-data.schema.json) | 校验规范化任务／引用／事件数据时 | P0-03 的 canonical schema，原样搬迁，URN与内容不变 |
| LICENSE／NOTICE | 完整候选与最终安装 payload | 沿用仓库 Apache-2.0 和项目 Skill 归属说明 |

默认/lite 不因存在 strict reference 就全量读取，不生成三个重复 Skill。缺非必要工具／Skill 不冻结无关安全工作；strict 必需项缺失仍blocked。明确用户交付、项目原有要求、真实授权、数据安全、报告真实性不会按模式降级。

本候选使用 host-native 文件／shell工具，不发明 `sbtd` 命令或新的运行调度器。数据校验、实际写入、host是否加载／遵循提示词的证明分开：schema与文档不冒充P1-17/18的运行实现，P1-15仍须真实host×mode验证。

## 本项 Gate 判断

以下Gate与验证事实记录P0-04当时的快照；P0-05/06扩展及P0-07正式安装证明分别归其任务，不回写历史报告冒充当时已完成。

- 未完整调用 grill-with-docs：需求／模式规则已清楚；路径调整为满足已确认的两项交付约束，原因及后续原子切换记入 [D-IMP-05](sbtd-workflow-v2-implementation-decisions.md)。
- DDD／DDIA：保留P0-03已确认的事实源、来源优先级、单writer与失败保全语义；不新增数据模型、数据库、锁或journal。
- Refactoring Review：proceed；唯一结构调整为schema字节不变迁移与全部引用更新，迁移前后同一9项回归验证。未改既有生产执行函数。
- Legacy：既有catalog/安装行为仍保持；候选不使用SKILL.md，不进入当前15项bundled安装集合。Release readiness 对尚未激活的候选内容不作生产发布结论。
- Ponytail／Code Readability：一个公共入口、三个按使用分支加载的references、一个schema；无新框架、运行依赖或重复schema副本。

## 验证事实与后续证明

已执行schema迁移前后9项回归，结果均通过；Ruff与ty通过。schema SHA-256 保持 `e568fee70b2e795a05ba448c07fbb8ffd4d85e43fe248edb3d228572dd03aa2e`，旧路径已移除。

隔离包装smoke：复制完整候选到临时Skill根，仅在临时目录把入口命名为SKILL.md；验证frontmatter、8条内部链接、schema与LICENSE字节一致。候选源没有SKILL.md，当前catalog仍为15 bundled／19 external且未注册sbtd-task。这是包装／自包含证明，不是catalog安装、真实host执行或Graft接线证明；P0-07的实际catalog驱动安装仍须执行。

P0-04验收时公共入口为1165个空白分隔单词。未发现可用tiktoken；未为此安装新依赖，不把单词数／bytes换算为精确token。入口≤3k及实际加载成本仍按P1-15使用目标模型/tokenizer计量，不能提前声明token收益达标。

验收覆盖：AC-02/23的入口契约、AC-04的host独立指令设计、AC-20的按需分层设计。主PRD/P0-10场景用于独立review；这些不替代运行验收。

按 D-IMP-06，完整 grill-with-docs 后的具名 DDD reviewer 门禁对三模式共同必需；缺失不可用均阻断相关确认／设计，普通可选工具降级不因此取消。新增 MR-27 由本项复审，旧 P0-10 的26项完成记录不追认覆盖新边界。

README.md、README.html、版本化automation prompt本项不改：现行安装入口、工具选择和监控规则未切换。CHANGELOG只记录未发布候选准备及非discovery边界，不宣称已安装/激活。普通开发不触发workflow sync或live automation。

提交前原生全量回归：276 tests / 58.368s / OK / exit0。命名报告位于 `tests/unit/reports/unit-report-skill-candidate-p0-04-sbtd-task-skill-2026_09_17-16_05_01.json`，同stem中文摘要及v1 envelope齐全；该轮绑定开发起点 `4dbcba1e9c675a2618157d0aaea253075b5e9cda` 的dirty工作树，developer-local／unverified／local-only，不冒充最终PR head。最终提交另做精确HEAD复验。
