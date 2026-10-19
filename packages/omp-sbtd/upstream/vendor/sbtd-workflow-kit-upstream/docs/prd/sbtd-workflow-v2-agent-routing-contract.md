# P0-05 公共规则与独立 fallback 契约

## 交付与激活边界

本项完成 AC-04/05/22/23 的规则内容，不提前声称真实 host 行为通过。主 [PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md) 与 [模式场景](sbtd-workflow-v2-mode-routing-contract.md) 是验收依据。

- [全局规则正式源](../../sbtd-workflow-onboard/templates/agents/AGENTS.global.md)：共同模式路由、必要确认、只读／数据安全、方法与输出入口、实际验证和交付。
- [项目规则正式源](../../sbtd-workflow-onboard/templates/agents/AGENTS.project.md)：项目事实优先、同任务恢复、无全局 Skill 的最小可执行 fallback 与受限持久化。
- [方法](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/methods.md)、[工具](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/tooling.md)、[输出](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/presentation.md)：从常驻规则抽离的条件分支，已由 [Skill入口](../../sbtd-workflow-onboard/templates/skills/sbtd-task/SKILL.md) 接入。
- [状态](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/state.md) 与 [handoff](../../sbtd-workflow-onboard/templates/skills/sbtd-task/references/handoff.md)：继续复用 P0-04 的任务协议，不另造运行时或第二份 task 数据源。

按 [D-IMP-07](sbtd-workflow-v2-implementation-decisions.md)，P0-05交付时两份AGENTS为非生效候选；P0-07与Skill/catalog同批移入正式模板并移除候选目录，上述链接跟随canonical路径。P0-05的验证及文档维护判断仍是其历史快照；完整v2运行／真实HOME部署不因源目录切换而完成。

## 保留与迁移映射

| 既有责任 | 候选所有者 | 边界 |
|---|---|---|
| 项目规则／事实优先、最小可逆与真实验证 | 两份共同入口 | default/lite不减明确交付，不因非必要工具缺失冻结无关工作 |
| 先路由再决定grill、双向模式推荐 | 两份共同入口与Skill入口 | 当前选择优先；推荐先暂停；拒绝后无新实质风险不重复；旧模式未知询问 |
| 完整grill后DDD | 两份共同入口、methods、strict | 三模式具名reviewer、独立可见结果，缺失／证据不足blocked，无替代放行 |
| 完整Book／BDD等方法 | methods与strict | strict按客观触发；default/lite按必要风险／用户交付；调用后按真实方法结果，不伪造通过 |
| Graft替换图辅助能力 | 全局安全边界与tooling | 逐授权根、DNT、禁cloud/LLM、真实freshness；缺能力用源码而非空结果宣称安全 |
| RTK与安装确认 | tooling | 无工具可原生；正式报告优先native；不让缓存代替文件副作用 |
| connector/MCP配置、凭据与代理 | tooling和共同安全边界 | 当前可调用证据；不静默改环境；不复制凭据 |
| Web/Mobile/API职责及证据 | tooling、project-validation及专业Skill | MCP诊断不冒充CLI/CI；原生报告、同stem中文汇总、精确版本与mock范围 |
| UI、shadcn、React Bits、SEO | methods与专业Skill | 只在相应实际语境触发；项目设计优先；不扩大安装或复制全局Skill |
| Caveman与ADHD | presentation | 输出状态独立于workflow_mode；保留手动、auto-lite、保护区、退出及续接语义 |
| handoff与上下文续作 | handoff与两份入口 | 真正暂停／切换／上下文需要触发，非3/5计数；只读不写、旧快照不覆盖任务 |
| developer／lessons | 入口与后续P0-06所有者 | 新身份路径、合法名、只写己方块；按需询问不全量init、不推断历史身份 |
| 最终输出与代码可读性 | 共同入口与methods | 必需证据不因压缩消失；简化服从正确性、安全、清晰职责 |

没有复制旧调度、hooks或图工具命令作为兼容入口；旧运行时存在只构成迁移事实，不授权自动初始化。外部 stable Skill payload 完全不改，caller路由与其内部方法结果分别负责。

## 独立 fallback 验收案例

以下为规则内容与独立 review 的检查面，真实 host 执行仍由 P1-18/P1-15 证明：

| 情境 | 必须行为 |
|---|---|
| 新普通任务无全局Skill | default，读项目事实，完成明确工作和聚焦验证；不强制onboard |
| 已有lite继续 | 继承有效记录，不因缺工具或normal mode变回default |
| 推荐strict被拒绝 | 原模式继续，保留决定，不重复劝说；未决安全事实仍限制相关动作 |
| 完整grill后DDD不可用 | 所有模式阻断依赖确认／设计，不把缺Skill当放行 |
| strict触发必需Book但不可用 | 指明缺失与blocked，不冒充fallback已经完成review |
| readonly／跨分支未决定 | 不写task/active/identity/handoff/ignore，不跑未经证明的有副作用查询 |
| 任务可安全保存 | 唯一task持有mode/status，active仅引用，schema1、真实时间、保护后的路径 |
| schema未知／不安全路径／无法原子写 | 不覆盖，明确未持久化；允许继续不依赖它的安全工作 |
| blocked历史未知 | 用户选择合法恢复阶段，记录未知历史和真实解除事件；不伪造ingress或直接done |
| 新lesson缺身份 | 只问必要合法名字／保护授权，先不写，不冻结无关default/lite工作 |
| 同目标多次续作或handoff | 输出资格／退出快照保留，handoff不改模式或变成第二事实源 |
| formal test或明确外部交付 | 按真实契约验证和归档；轻模式不缩减交付、不把本地mock标成full-stack |

## 验证与不宣称事项

验证分层：临时最终目录布局的链接／资产／schema摘要检查；PRD台账与依赖检查；项目原有unit回归；独立语义review。正式报告按本仓证据契约存于忽略的本地unit报告目录，最终绑定被评审commit，不纳入产品资产。

字符、UTF-8字节和空白分词只作文件规模观察，不换算token、不用于通过约2k/3k目标。未安装tokenizer，实际host加载路径／token量由P1-15测量；本项不得声称已降到目标或节省某百分比。

本轮未完整调用grill-with-docs：已确认PRD和既有契约消除了实现边界歧义，无需重新访谈。候选尚未激活，不修改现有生产执行逻辑；不以本任务宣称新Onboard安装、Graft集成或Codex/OMP自动恢复已实现。

README.md、README.html、版本化automation prompt本项保持不变：实际安装／运行／监控入口未改变，候选不是可用发布功能；P0-07及后续实际切换任务仍须同步受影响说明。CHANGELOG未发布文档节记录候选交付与激活边界。未执行workflow sync或触碰live automation。

## 首轮 review 修正

P005ReviewOne 指出七项遗漏，全部纳入规则候选：完整 strict 客观触发集合及阶段、纯问答不持久化、不为问答请求ignore改动、detached绑定完整SHA、mode_note保存建议拒绝与理由、handoff任务／会话退出和显式恢复、Graft原始结果禁止发布及最小脱敏、相关时报告Graft状态与根／版本／范围。其中纯问答保护属于同一发现项；本段为修正追溯，不把既有unit通过当作这些语义的执行证明。

对应复审场景：隐藏依赖触发legacy；跨进程cache／migration触发DDIA；可写仓库中的概念问答不新建记录；不同detached SHA必须另行裁决；跨会话读取拒绝理由后不重复建议；关闭自动交接后暂停不写但手动请求仍可执行；请求图报告只产生安全摘要并披露实际结构证据边界。

本轮收到的顺序advisor已处理：review尚未结束时停止P0-06预读，没有创建／修改该任务资产；下一任务只在本任务review、合并、台账更新与分支清理全部结束后开始。

## 第二轮 review 修正

P005ReviewTwo确认首轮七项修正存在，并发现入口间三项遗漏：project-only补齐Graft的持续DNT、deep/name禁令及继承provider/cloud阻断；canonical state明确新建detached记录使用完整SHA；canonical handoff明确任务／会话退出的锁存、匹配范围恢复、会话优先及手动请求不清除退出。修正同时覆盖全局已装但项目模板缺失的真实支持组合，不依赖只在另一入口出现的规则。

同轮将独立fallback的handoff文件名、必要快照、7天主动提示和手动恢复边界显式对齐canonical reference，防止无全局Skill时另造文件布局或扩大自动恢复范围。
