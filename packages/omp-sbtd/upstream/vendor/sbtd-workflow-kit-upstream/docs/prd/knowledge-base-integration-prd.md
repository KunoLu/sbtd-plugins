# 知识库集成 P0 / P1.0 / P1.1 / P2 落地方案

## 1. 文档目的

本文统一记录知识库集成前的老版本、P0 契约、已实现的 P1.0 / P1.1，以及后续分阶段实现的 P2。本文同时作为能力边界、实现状态、使用变化、验收和回滚的统一依据。

版本口径：

| 阶段 | 当前状态 | 定义 |
|---|---|---|
| 老版本 | 历史基线 | 知识库集成前的模板工作流；已有项目原生 API / TS / JS、Playwright、Maestro 测试和正式报告规则，但没有产品级 Knowledge Ingest、Revision Set 和中央 Evidence 生命周期 |
| P0 | 已实现契约 | 定义 `read / 读取`、Evidence 字段、状态、Schema 和阶段边界；不提供知识库服务器运行时 |
| P1.0 | 已实现运行基线 | 首次提供产品注册表、Workspace Mapping、Policy Resolver、精确 Revision Set、只读 ingest、派生目录和基础服务器 smoke 的可运行入口 |
| P1.1 | 已实现强化版本 | 在 P1.0 上补齐完整无 ID Gherkin 解析、工具无关绑定、分阶段 smoke、Runner Adapter、可信环境校验、报告完整性、幂等重试和指标 |
| P2 | 尚未实现 | 远端 Evidence 接收、存储、发布、PR 关联、自动失效、门禁和生命周期治理；必须分阶段上线 |

P1.0、P1.1 是本文用于说明实现演进的方案阶段名称，不代表当前仓库已经创建同名 Git Tag 或独立发布包。当前模板运行时以 P1.1 为准，并保持对 P1.0 的 Schema version `1` 可选字段兼容。

P0 已在模板工作流中定义以下契约：

- `gherkin-bdd` 保留原有 `sync / 同步` BDD Sync Mode，不改变其全量扫描和更新 `.feature` 的能力。
- 新增 `read / 读取` Knowledge Ingest；只有明确只读且不含新增、修改、更新或删除意图时才进入，只读指定仓库和目标 ref，并把 ref 固定为精确 commit SHA。
- 不修改现有 BDD `.feature` 规范，不要求 `feature_id`、`scenario_id`、新 tags、owner 字段或 BDD Runner。
- 开发者本地、CI 与知识库服务器报告使用不同 evidence source，并以 source ref、commit SHA、worktree state、revision set 和 environment alignment 证明版本来源。
- P0 只定义规则、状态和 JSON Schema；尚未实现知识库服务、服务器 runner、对象存储、PR provider adapter 或 evidence publish CLI。
- Evidence Policy 按阶段拆分：P1.0 / P1.1 实现配置 Schema、加载、优先级解析和 Evidence Decision；P2 消费该决策并执行发布、PR Check、知识库入库、失效和门禁。

## 2. 不可改变的架构边界

1. 每个仓库配置目标分支、tag 或 SHA；例如知识库可以把 `staging` 设为某仓库的行为 SOT ref。
2. SOT 是目标 ref 对应 commit 中的仓库自有 `.feature`，不是知识库生成的副本。
3. 知识库行为目录、场景页、关系图和覆盖统计全部是可重建派生数据。
4. 跨仓语义相似只能生成重复或冲突候选，不自动合并、移动、删除或改写 `.feature`。
5. 现有 TS / JS、API、Playwright、Maestro 和项目自定义 runner 继续作为执行工具；不新增 Gherkin Runner。
6. Knowledge Ingest 与测试运行不得直接切换开发者长期 clone 的活动分支。
7. 开发者本地证据和知识库服务器证据独立展示；`smoke-only` 不等于完整回归。

## 老版本 → P1.0 → P1.1 → P2 功能演进总览

| 维度 | 老版本 | P1.0 | 当前 P1.1 | 后续 P2 |
|---|---|---|---|---|
| 工作流定位 | 单仓开发、测试生成和本地验证辅助 | 产品级多仓只读摄取与基础集中 smoke | 可审计、可重复、可调度的产品级摄取与 smoke 运行时 | 组织级测试证据发布、查询和质量门禁平台 |
| `.feature` SOT | 各仓库 `features/` | 指定目标 ref 内的仓库自有 `.feature` | 保持 P1.0；固定到 Revision Set 精确 SHA | 保持 P1.1；只引用，不复制或改写 |
| BDD `sync / 同步` | 已有可写同步模式 | 保持不变 | 保持不变 | 保持不变 |
| Knowledge `read / 读取` | 无独立只读模式 | 新增确定性 ingest 入口 | 补齐完整解析、绑定、冲突候选和指标 | 消费摄取结果，不改变源仓 |
| 产品与仓库范围 | 当前仓库为主 | 产品注册表 + Workspace Mapping | 增加 runner、trust、binding manifests 和阶段配置 | 用于远端 Evidence 授权、索引和展示 |
| 版本身份 | 分支名、路径、报告时间 | 每仓 target ref 解析为完整 SHA | 不可变 Revision Set、幂等键、attempt 和 attestation | PR Provider 复核当前 Head，并自动失效旧证据 |
| Gherkin 解析 | 由 BDD Skill 处理业务场景 | 生成基础只读 Feature/Scenario 目录 | 保留 Feature、Rule、Background、Scenario Outline、Examples、tags、Doc String、Data Table、行号和 parser gap | 门户检索和历史跳转，不新增 ID |
| 测试绑定 | 测试名、注释或人工约定 | 可按仓库 suite 运行 | 静态扫描 + JSON/YAML manifest；缺失绑定时不虚报场景级覆盖 | 绑定索引进入 Evidence Store 和覆盖视图 |
| 测试执行 | 项目原生 TS / JS、API、Playwright、Maestro | 服务器在隔离 worktree 中执行基础 API/Web smoke | 分阶段命令 + 本地/命令式 Runner Adapter + Mobile labels | 继续使用原生 runner；P2 不替换执行框架 |
| 报告 | 已有原生报告、正式快照和同 stem 中文 Markdown 规则 | 收集服务器 smoke 报告并形成本地 bundle | 仅接收本轮刷新报告，增加 artifact manifest、checksums、基础敏感信息阻断 | 远端不可变存储、授权下载、quarantine 和 retention |
| Evidence 决策 | 无统一机器化判定 | Policy Resolver 生成不可变 Decision | 增加 digest、source/reason、CI 来源和 `not-configured` publication | Enforcer 消费 Decision；不重新解释策略 |
| PR 集成 | 人工说明、附件或项目自有 CI | 不写 PR Check | 仍不写 PR Check | 信息型 Check → 高风险 required gate → 扩大策略 |
| 新 Commit 失效 | 主要靠人工判断 | 记录精确 SHA，但无中央状态 | 明确发布前必须针对最终 PR Head 复验/刷新 | 自动 `invalidated` / `superseded` 并重新调度 |
| Evidence Store | 无统一中央存储 | 无；只生成本地/runtime bundle | 无；`Evidence Publication: not-configured` | 对象存储 + 元数据数据库 + 可重建索引 |
| 安全与治理 | 报告脱敏和禁止写入敏感数据 | 基础 Schema 和安全边界 | 基础敏感信息阻断、可信 issuer/digest/runner attestation | 深度扫描、隔离、最小权限、审计、签名链接和 legal hold |
| 使用者主要变化 | 运行项目原生命令并查看本地报告 | 需要配置产品、仓库目标 ref 和服务器路径 | 可运行确定性 ingest/smoke；本地测试命令仍不变 | required 时发布本地证据；PR Head 变化后重验；关注 Check 和 waiver |

## P0～P2 详细能力与集成矩阵

状态说明：`已实现` 表示当前模板已具备规则、Schema 或运行时；P1 列同时标明首次在 P1.0 交付还是在 P1.1 补齐；P2 列表示后续明确交付项；`沿用` 表示不改变现有项目能力；`不负责` 表示该阶段不实现此能力。

| 能力 | P0 契约 | P1.0 / P1.1 集成内容 | P2 集成内容 | 主要配置或产物 |
|---|---|---|---|---|
| BDD `sync / 同步` | 已实现规则；保持现有可写 BDD Sync Mode | 沿用，不改变 | 沿用，不改变 | `gherkin-bdd/SKILL.md` |
| Knowledge `read / 读取` | 已实现明确只读意图且无变更意图时触发的 Knowledge Ingest 契约 | 实现多仓、目标 ref、Git object / 隔离 worktree 的实际摄取 | 消费摄取结果展示，不改变源仓 | `Knowledge Ingest` 状态、`ingest-summary.json` |
| `.feature` 行为 SOT | 已明确仓库目标 ref 中的 `.feature` 是 SOT | 按 ref 固定 SHA 后读取 | 只引用，不复制为新的 SOT | repository key + ref + SHA + path |
| Feature / Scenario ID | 明确不要求、不补写 | 不引入 | 不引入 | 无新增 ID 字段 |
| Gherkin / BDD Runner | 明确不默认引入 | 不引入；继续调用原生测试 runner | 不引入 | TS / JS、API、Playwright、Maestro、项目自定义 runner |
| 产品与仓库注册 | 只有规则边界 | 实现产品注册表和仓库角色、remote、feature roots、target ref | 读取注册结果关联 Evidence / PR | `product.yaml` 或等价注册表 |
| 每仓库目标 ref | 已定义必须显式选择 ref 并解析 SHA | 实现配置 Schema、fetch、ref resolve 和错误处理 | 使用 resolved SHA 做 Evidence / PR 对齐 | `target_ref`、`resolved_commit` |
| Revision Set | 已定义 knowledge-server 必须提供精确 Revision Set | 实现不可变 Revision Set 创建和 run 内固定 | 存储、索引、展示并用于失效判断 | `revision-set.json` |
| 长期 clone / 隔离 worktree | 已禁止切换开发者活动 worktree | 实现 fetch cache、隔离 worktree、锁与清理 | 只引用运行结果 | `.kb-runtime/worktrees/<run-id>/` |
| Gherkin 解析与行为目录 | 已定义读取字段和只读边界 | P1.1 已实现 Feature、Rule、Background、Scenario / Outline、Examples、tags、Doc String、Data Table、行号和 parser gap | 门户展示和检索 | `features.json`、`scenarios.json` |
| 无 ID Source Locator | 已定义复合 locator | 实现 path/name/fingerprint/SHA 生成与历史关联 | 用于 Evidence 和门户跳转 | `source-locators.json` |
| 跨仓重复 / 冲突 | 已规定只能生成候选 | 实现 overlap/conflict 检测，不自动改源 | 展示、审计和人工处理状态 | `overlaps.json`、`conflicts.json` |
| Scenario-Test Binding | 已允许用测试名、注释、目录或项目约定追踪 | P1.1 已实现静态扫描和 JSON / YAML manifest 读取；缺失时仍可按 suite 运行 | 存储绑定索引和覆盖视图 | `bindings.json` / generated index |
| 开发者本地测试 | 沿用现有 API / Playwright / Maestro 运行方式 | 不接管本地 runner；只定义可接收的 evidence decision/envelope | 实现 collect、validate、publish 和 PR 关联 | native reports、同 stem Markdown、evidence envelope |
| 知识库服务器 Smoke | 已定义 `knowledge-server` evidence 契约 | P1.1 已实现 preflight / prepare / test / cleanup、API/Web 原生命令、本地 / 命令式 Runner Adapter，并按 labels 接入 Mobile | 存储、展示、关联 PR/知识库 | native commands、runner job/result、smoke evidence |
| 原生报告与中文汇总 | 已实现路径、命名、同 stem 和报告 Gate | P1.1 只收集本轮新建 / 刷新的报告及同 stem 中文汇总，并生成 artifact manifest 与 checksums | 接收、重校验、存储和授权访问 | API / Playwright / Maestro 报告、`.md`、artifact manifest |
| Evidence Envelope Schema | 已实现 `validation-evidence.schema.json` | 实现 envelope 生成器和 Schema 版本兼容 | 重新校验后发布和索引 | `.evidence.json` / aggregate envelope |
| Evidence Source | 已定义 `developer-local` / `ci` / `knowledge-server` | 根据运行 profile 生成；CI 使用 clean checkout 和精确 PR head | 分开存储和展示 | `evidenceSource` |
| Evidence Intent / Target | 尚未机器化；目前依赖工作流语义 | 实现显式 target、配置解析和 Evidence Decision | 根据 target 路由到 PR、知识库或两者 | `evidence-decision.json`、`evidenceTargets` |
| 项目 Evidence Policy | 尚未实现 | 实现产品级默认、仓库级收紧规则、Schema 和加载 | 使用已解析策略，不重新解释配置 | 产品注册表 `evidence_policy` |
| Evidence Policy 优先级 | 尚未实现 | 实现中央强制策略、产品默认、仓库收紧、trigger/profile、显式追加 target 的确定性合并 | 审计最终 decision source/reason | Policy Resolver |
| Evidence Policy 决策 | 尚未实现 | 输出 `required`、targets、source、reason；不执行远端门禁 | 消费决策并转换为发布与 Gate 状态 | `evidence-decision.json` |
| Evidence Policy 强制执行 | 不负责 | 不负责远端强制；最多生成 `not-configured` 本地/服务器 bundle | 实现 Publisher、PR Check、知识库发布、required gate 和 waiver | Policy Enforcer |
| PR Head SHA 匹配 | 已定义必须精确匹配 | 提交前只记录本地状态；提交后、发布前针对最终 PR head 重新生成或复验并更新 envelope | 调用 provider API 复核当前 head 并执行 Gate | PR provider adapter |
| 新 commit 后 Evidence 失效 | 只有规则描述 | 不负责跨系统失效 | 实现 `invalidated` / `superseded` 和重新调度 | PR webhook / event consumer |
| Evidence Store | 不负责 | 可生成待发布 bundle，不提供正式存储 | 实现对象存储、元数据数据库和索引重建 | object store + database |
| Environment Alignment | 已定义状态枚举与语义 | P1.1 已实现 Revision Set、可信路径 / issuer / digest、部署 metadata 和实际 runner / tool / image attestation 检查 | 存储、展示并作为 Gate 条件 | deployment manifest / image digest / runner attestation |
| Mobile Runner | 已保留 Java、Maestro、设备和 app artifact Gate | P1.1 已实现 Runner Adapter、job/result contract 和 labels 条件调度 | 聚合和发布 Mobile evidence | Android/iOS runner profile |
| 安全与脱敏 | 已规定 evidence 不得包含密钥、PII 和生产敏感数据 | 生成前基础校验和 bundle 脱敏 | 实现上传扫描、quarantine、最小权限和审计 | security scan / quarantine |
| 幂等、重试和去重 | 只有设计约束 | P1.1 已实现 ingest / smoke 幂等键、显式 attempt、陈旧锁回收和只对基础设施失败重试 | 实现 publish、webhook、索引回放和 dead-letter queue | idempotency registry、run ID、revision set ID、attempt |
| 保留与删除 | 不负责 | 清理 runtime 和可重建派生索引 | 实现 retention、tombstone、legal hold 和对象删除 | retention policy |
| PR Check / 合并门禁 | 不负责 | 只输出 Evidence Decision，不写远端 Check | 实现 informational → required 的渐进 Gate | GitHub/GitLab/内部平台 adapter |
| 知识门户 | 只定义派生视图边界 | 生成行为、覆盖、冲突和最新运行数据 | 聚合 Evidence、PR 状态、历史和权限视图 | portal index / API |
| 可观测性 | 规定最终状态输出 | P1.1 已生成 ingest / smoke `metrics.json`，包含耗时、数量、runner、retry、queue latency 和状态计数 | 实现 publish、PR invalidation、store、retention 指标与告警 | metrics、logs、alerts |
| 回滚边界 | 模板规则可回滚，不触碰业务源文件 | 停止调度并删除可重建 runtime/index | 将 Gate 降级为 non-blocking，停止发布并保留不可变 evidence | rollout / rollback runbook |

---

# P1.0 / P1.1：只读知识摄取与服务器 Smoke 编排

## 3. P1.0 / P1.1 目标与实现状态

> 实现状态（2026-07-17）：P1.0 与 P1.1 已在 bundled `knowledge-base-integration` Skill 中落地。确定性入口为 `scripts/knowledge_base_p1.py`，公开子命令为 `validate-config`、`decision`、`ingest`、`smoke`。当前实际使用 P1.1 runtime；P2 仍未实现。

P1.0 把 P0 的文本契约实现为可运行基线，P1.1 再将其强化为当前只读产品级摄取与 smoke 编排能力：

- 注册一个产品下的多个前端、后端、Mobile 和测试仓库。
- 为每个仓库独立配置目标 ref 和 feature roots。
- 解析目标 ref 到精确 SHA，生成 Revision Set。
- 从 Git 对象或隔离 worktree 读取 `.feature`，建立只读行为目录。
- 根据仓库已有测试命令运行服务器 smoke，并生成 `knowledge-server` evidence。
- 不要求更改任何 `.feature` 文件格式。

### 3.1 P1.0 与 P1.1 实现差异

| 能力域 | P1.0 首次可运行基线 | P1.1 当前已实现强化 | 对使用者的影响 |
|---|---|---|---|
| CLI 入口 | 提供 `validate-config`、`decision`、`ingest`、`smoke` | 保持同一组公开子命令，避免新增第二套入口 | 原有调用方式不需要切换 |
| 产品配置 | 产品注册表、仓库 remote/role/target ref/feature roots、Workspace Mapping | 增加 binding manifests、trust roots/issuers、local/remote runner、stage、retry 和正式报告声明 | 配置更完整；未配置高级能力时仍可使用基础路径 |
| Evidence Policy | 解析 product/repository/trigger/profile/explicit target，输出 Decision | Decision 增加稳定 digest、source/reason、CI 来源和不可降级 required target 约束 | 不再根据报告目录或分支名猜测是否用于 PR/知识库 |
| Revision Set | 将每仓 target ref 固定为完整 SHA | Revision Set 同时进入幂等键、Runner job、部署校验、artifact 和 evidence envelope | 同一次 run 的多仓版本组合可复现 |
| Gherkin 摄取 | 只读读取目标 ref 的 `.feature`，生成 Feature/Scenario 目录 | 完整保留 Rule、Background、Outline、Examples、tags、Doc String、Data Table、行号、language 和 parser gap | 不修改 `.feature`，但目录信息更完整 |
| Source Locator | repository/ref/SHA/path/name/line 复合定位 | 增加 fingerprint 和更完整结构上下文 | 仍不是持久业务 ID；移动或改名需要重新关联 |
| 测试绑定 | 没有可靠映射时按仓库 smoke suite 运行 | 测试名/注释/文件组织静态扫描 + JSON/YAML binding manifests | 可形成工具无关绑定；缺失时不虚报场景级覆盖 |
| Smoke 执行 | detached worktree 中运行基础原生 API/Web 命令 | `preflight / prepare / test / cleanup`；前序失败后 cleanup 仍运行 | 服务、数据准备和清理边界更明确 |
| Runner | 以知识库服务器本地执行为主 | 本地 Adapter + 命令式 Adapter；job/result manifest 支持 CI、Android、iOS/macOS 和设备池 | Mobile 不要求知识库主机本身具备全部设备条件 |
| 环境对齐 | 记录 Revision Set 和运行环境 | 校验可信 metadata 路径、issuer、canonical digest、部署 SHA、runner/tool/image attestation | `verified` 有可检查依据；无法证明时保持 `unverified` 或 `mismatch` |
| 报告收集 | 生成或收集本地 evidence bundle | 只接受本轮创建/刷新报告；要求原生报告与同 stem 中文 Markdown；生成 artifact manifest 和 checksums | 旧报告不能被误当作本轮通过证据 |
| 安全 | 遵守不写入密钥、PII、生产数据边界 | 增加基础敏感信息命中阻断 | P2 前仍没有 quarantine 和授权下载 |
| 幂等与重试 | 基础 run 语义 | ingest/smoke 幂等键、attempt、陈旧 PID lock 回收、基础设施失败重试、断言失败不自动重试 | 重复事件不再无界创建 run；显式重跑不覆盖旧 evidence |
| 可观测性 | 运行摘要 | `metrics.json` 记录耗时、数量、状态、retry、runner 类型和 queue latency | 为 P2 告警和容量规划提供数据基础 |
| 发布 | 不提供远端 Publisher | 仍固定为 `Evidence Publication: not-configured` | P1.1 完成不代表 PR Check、知识库入库或远端 Gate 已经完成 |

### 3.2 当前 P1.1 已实现产物

| P1.1 能力 | 实现位置或产物 |
|---|---|
| 产品注册表与 Workspace Mapping 加载 | `knowledge-base-integration/scripts/knowledge_base_p1.py` |
| 配置、Evidence Decision、Revision Set Schema | `knowledge-base-integration/references/*.schema.json` |
| Evidence Policy Resolver | `decision` 子命令；输出不可变 decision ID、digest、source 和 reason |
| 目标 ref 与 Revision Set | `ingest` / `smoke`；缺失 ref 直接 `blocked`，不回退默认分支 |
| 无 ID Gherkin 摄取 | Git object 读取；保留 Feature、Rule、Background、Scenario / Outline、Examples、tags、Doc String、Data Table、行号与 parser gap |
| 派生行为目录 | `features.json`、`scenarios.json`、`source-locators.json`、`bindings.json` |
| 跨仓候选 | `overlaps.json`、`conflicts.json`，只生成候选，不修改 SOT |
| 服务器 Smoke | `preflight / prepare / test / cleanup` 分阶段执行；隔离 detached worktree 中调用原生 argv，cleanup 保证收尾 |
| Runner Adapter | 默认本地执行；命令式 Adapter 通过 job/result manifest 调度 CI、Android、iOS/macOS 或设备池，并校验实际 attestation |
| 环境与 Runner 对齐 | `--deployment-manifest` 校验 Revision Set、可信 metadata 路径、issuer、digest，以及 runner ID/version/image/labels/tools |
| 正式报告收集 | 只收集当前命令开始后生成或刷新的 runner 报告与同 stem 中文 Markdown，计算 SHA-256、size、mtime 并做基础敏感信息扫描 |
| Artifact 完整性 | 每仓库生成 `artifact-manifest-<repository-key>.json` 与 `checksums-<repository-key>.sha256` |
| P1.1 Evidence Bundle | 每仓库 `evidence-<repository-key>.json`，引用 Decision、完整 Revision Set、artifact manifest digest 和 runner attestation，publication 为 `not-configured` |
| 幂等、重试与并发 | ingest / smoke 使用内容幂等键；重复逻辑运行复用原结果；显式重跑增加 attempt；只对基础设施失败重试；陈旧 PID lock 可回收 |
| 可观测性 | ingest / smoke 生成 `metrics.json`，记录耗时、数量、状态、retry、runner 类型和 queue latency |

运行环境需要 `requirements.txt` 中的 PyYAML 与 jsonschema。普通本地诊断仍可不进入 P1；只有产品级读取、知识库服务器 Smoke 或 Evidence Policy 明确要求时使用这些入口。

## 4. 配置模型

产品逻辑配置与服务器本地路径必须分开。

### 4.1 产品注册表

建议由知识库控制仓库维护：

```yaml
schema_version: 1
product_key: smart
display_name: Smart药局

repositories:
  - key: smart-fuzi-web
    remote: ssh://git.example/smart/fuzi-frontend.git
    role: web
    target_ref: refs/heads/staging
    feature_roots:
      - features
    binding_manifests:
      - tests/e2e/manifest/ui-test-manifest.json

  - key: smart-guangsi-web
    remote: ssh://git.example/smart/guangsi-frontend.git
    role: web
    target_ref: refs/heads/staging
    feature_roots:
      - features

  - key: smart-backend
    remote: ssh://git.example/smart/backend.git
    role: backend
    target_ref: refs/heads/staging
    feature_roots:
      - features

smoke:
  retry_policy:
    infrastructure: 1
  commands:
    smart-fuzi-web:
      - key: web-preflight
        stage: preflight
        command: [npm, run, e2e:doctor]
      - key: web-smoke
        stage: test
        command: [npm, run, test:e2e:smoke]
        reports:
          - path: tests/e2e/reports/html/playwright-report-smoke-*.html
            summary_md: tests/e2e/reports/html/playwright-report-smoke-*.md
    smart-backend:
      - key: api-smoke
        stage: test
        command: [npm, run, test:api:smoke]
      - key: cleanup
        stage: cleanup
        command: [npm, run, smoke:cleanup]
```

规则：

- `target_ref` 必须显式配置；不存在时该仓库摄取为 `blocked`，不得静默改读默认分支。
- remote、role、feature roots 和 native smoke command 属于共享逻辑配置。
- 配置不得包含服务器绝对路径、账号、token、密码或生产测试数据。

### 4.2 服务器 Workspace Mapping

服务器本地配置不提交业务仓库：

```yaml
schema_version: 1
product_key: smart
product_root: /home/kb/Smart

paths:
  smart-fuzi-web: fuzi/frontend
  smart-guangsi-web: guangsi/frontend
  smart-backend: backend

runtime_root: /home/kb/Smart/.kb-runtime

trust:
  deployment_metadata_roots:
    - /home/kb/deployments
  allowed_issuers:
    - internal-deployer

local_runner:
  id: smart-kb-linux
  version: 2026.07
  labels: [api, web, playwright]

runners:
  ios-pool:
    command:
      - /opt/kb/bin/dispatch-ios
      - --job
      - "{job_manifest}"
      - --result
      - "{result_manifest}"
      - --artifacts
      - "{artifact_dir}"
```

长期 clone 只作为 fetch cache。每次任务使用：

```text
<runtime_root>/worktrees/<run-id>/<repository-key>/
```

### 4.3 Evidence Policy 配置与决策

P1.0 / P1.1 必须把“项目配置明确要求 Evidence”实现为结构化配置和确定性决策，不能继续依赖 Agent 根据报告目录、分支名或自然语言自行猜测。Evidence Policy 的权威配置放在产品注册表；仓库差异仍写在同一注册表的 repository entry 中，避免在多个业务仓库复制另一套策略 SOT。

建议配置：

```yaml
schema_version: 1
product_key: smart

evidence_policy:
  defaults:
    developer_local:
      required: false

    ci:
      required: true
      targets:
        - pull-request
      require_clean_worktree: true
      require_exact_head_sha: true

    pull_request:
      required: true
      targets:
        - pull-request
      require_clean_worktree: true
      require_exact_head_sha: true

    knowledge_server:
      required: true
      targets:
        - knowledge-base
      require_revision_set: true
      require_environment_alignment: true

    scheduled_smoke:
      required: true
      targets:
        - knowledge-base

repositories:
  - key: smart-fuzi-web
    evidence_policy:
      pull_request:
        required: true

  - key: smart-backend
    evidence_policy:
      scheduled_smoke:
        required: true
```

P1.0 / P1.1 已交付：

- 在产品注册表 Schema 中增加 `evidence_policy`。
- 增加 `evidence-decision.schema.json`，定义解析结果，而不是让每个 Publisher 重复解释配置。
- 实现 Policy Resolver，根据 product、repository、trigger、execution profile、显式 target 和中央策略生成一次不可变 Evidence Decision。
- 对规范化后的 Decision 计算内容 digest，并记录 policy version；P2 必须验证同一份 Decision，而不是在发布时重新求值。
- 中央或产品级 `required` 策略不得被仓库配置、用户参数或本地命令降级；低层配置只能收紧要求，显式参数只能增加 target。
- 如果配置冲突、target 不受支持或 required policy 无法满足，输出 `blocked`，不得回退为普通本地报告后继续声称门禁满足。
- 普通开发者本地诊断在没有 required policy 和显式 target 时输出 `not-required`，不强制生成 evidence envelope。

确定性优先级：

```text
中央强制策略
  -> 产品默认策略
  -> 同一产品注册表中的仓库级收紧规则
  -> 当前 trigger / execution profile
  -> 显式追加的 Evidence Target
  -> 默认 not-required
```

不得使用以下弱信号单独判定 Evidence 用途：

- 报告位于正式目录。
- 文件名包含 `branch_slug`。
- 当前分支是 `feature/*`。
- 仓库已经存在 PR。
- 当前命令运行在任意 CI 中。
- 执行了 Knowledge Ingest。

建议决策结构：

```yaml
schema_version: 1
decision_id: evd-decision-smart-20260715-0001
policy_version: 1
decision_digest: sha256:<canonical-decision-json-digest>
product_key: smart
repository_key: smart-fuzi-web
trigger: pull-request
execution_profile: developer-local

evidence_contract: required
evidence_intent: pull-request
evidence_targets:
  - pull-request

decision_source:
  level: product-policy
  rule: evidence_policy.defaults.pull_request
decision_reason: pull-request-evidence-required

requirements:
  clean_worktree: true
  exact_head_sha: true
  revision_set: false
  environment_alignment: false
```

CI 生成 PR 正式证据时使用 `execution_profile: ci`；同样要求 clean checkout 和精确 PR head SHA，并按 `ci` 与 `pull_request` 两层规则合并要求。

建议状态：

| 字段 | 允许值 | 含义 |
|---|---|---|
| `evidence_contract` | `not-required` / `required` / `blocked` | 是否必须应用 Evidence Contract |
| `evidence_intent` | `local-only` / `pull-request` / `knowledge-base` / `pull-request-and-knowledge-base` / `not-needed` / `blocked` | 本次 Evidence 的业务用途 |
| `evidence_targets` | `pull-request` / `knowledge-base` | 一个 Evidence 可以有一个或两个发布目标 |
| `decision_source.level` | `central-policy` / `product-policy` / `repository-policy` / `execution-profile` / `explicit-target` / `default` | 哪一层规则决定了结果 |

P1.1 的 Policy Resolver 只决定“是否需要、用于哪里、为什么需要”，并生成本地或服务器 evidence bundle。P1.1 不写 PR Check，不把 `required` 转换为远端合并阻断；如果 P2 Publisher 尚未部署，publication 状态应为 `not-configured`，不能写成 `published`。

## 5. Revision Set

摄取或测试开始前执行：

```text
读取产品注册表
  -> fetch 已配置 remote/ref
  -> 将每个 target_ref 解析为完整 commit SHA
  -> 写入不可变 Revision Set
  -> 后续解析、测试和证据只使用该 Revision Set
```

建议结构：

```yaml
schema_version: 1
revision_set_id: revset-smart-20260715-0001
product_key: smart
created_at: 2026-07-15T12:00:00+08:00
repositories:
  - repository_key: smart-fuzi-web
    requested_ref: refs/heads/staging
    resolved_commit: 0123456789abcdef0123456789abcdef01234567
  - repository_key: smart-backend
    requested_ref: refs/heads/staging
    resolved_commit: 89abcdef0123456789abcdef0123456789abcdef
```

一致性语义：一次 run 内 Revision Set 不变。run 进行期间目标分支前进，不改变当前 run；下一次 run 创建新的 Revision Set。

## 6. Knowledge Ingest 实现

### 6.1 读取路径

优先级：

1. 对只需读取文本的任务使用 Git object API，例如读取 `<sha>:<path>`。
2. 解析器需要目录树或工具只支持文件系统时创建 detached、隔离、只读语义的 worktree。
3. 禁止在长期 clone 中 `checkout staging` 后执行任务。

### 6.2 Gherkin 解析结果

解析：

- Gherkin language。
- Feature、Rule、Background。
- Scenario、Scenario Outline、Examples。
- tags、doc strings、data tables。
- 文件路径、行号、目标 ref、精确 SHA。

不解析或写回：

- 强制 Feature ID / Scenario ID。
- 新 owner / scope tag。
- Step Definition 或 BDD Runner binding。

### 6.3 无 ID Source Locator

派生目录使用复合定位信息：

```yaml
repository_key: smart-fuzi-web
source_ref: refs/heads/staging
source_commit: 0123456789abcdef0123456789abcdef01234567
path: features/prescription/order-submit.feature
feature: 处方药订单提交
rule: 缺少处方不得下单
scenario: 用户未提供有效处方时提交订单
examples_fingerprint: null
line: 18
```

定位器不是持久业务 ID。场景改名或移动后可以被视为新的 locator，再通过 Git diff、内容 fingerprint 和人工确认建立历史连续性。

## 7. 聚合目录与冲突候选

P1.1 生成：

```text
generated/products/<product-key>/
├── revision-set.json
├── features.json
├── scenarios.json
├── source-locators.json
├── overlaps.json
├── conflicts.json
├── metrics.json
└── ingest-summary.json
```

`overlaps.json` 和 `conflicts.json` 只记录候选：

- 相同或近似标题。
- 相似 Given / When / Then。
- 同业务术语但预期结果冲突。
- 一个前端场景与后端规则可能描述同一业务不变量。

每条候选必须带来源 locator、证据、算法版本和置信度。P1.1 不自动修改源仓。

## 8. 服务器 Smoke 编排

服务器不执行 `.feature`，而是执行各仓库已有 native command：

```text
Product Registry + trigger + execution profile
  -> Evidence Policy Resolver
  -> Revision Set
  -> isolated worktrees
  -> environment preflight
  -> service/data preparation
  -> registered API / TS / JS / Playwright / Maestro smoke commands
  -> native reports + Chinese summaries
  -> validation evidence envelope
  -> cleanup
```

如果 Evidence Decision 为 `not-required`，测试仍可按调度策略运行，但不必生成用于 PR/知识库发布的 evidence envelope。如果 Decision 为 `required`，P1.1 必须生成满足 P0 Schema、包含 target 和 decision reference 的 bundle；如果 required 条件无法满足，运行结果标记为 `blocked`，不能降级成无 Evidence 的成功结果。

如果尚无可靠 scenario-to-test mapping，P1.1 可以先按仓库级 smoke suite 运行，不声称精确场景选择。P1.1 已支持基于测试名、注释、文件组织及 JSON / YAML manifest 建立工具无关 binding；仍不要求修改 `.feature`。

Mobile 测试必须通过具备 Android、iOS、Java、Maestro 和 app artifact 的 runner 执行。P1.1 的命令式 Runner Adapter 以 job manifest 下发精确 Revision Set、原生 argv 和 required labels，以 result manifest 返回实际 runner / tool / image attestation、queue latency、状态和报告；知识库服务器只负责调度、校验与聚合，不假设本机具备所有设备条件。

正式报告必须由当前命令新建或刷新，并与同 stem 中文 Markdown 成对出现。每仓库 bundle 同时生成 artifact manifest 和 checksums；stale、缺失、非中文、敏感信息命中或 digest 不一致时，Evidence 为 `blocked`。P1.1 只做基础敏感信息阻断，P2 才实现 quarantine 和授权访问。

## 9. 数据与失败语义

### 9.1 Source of truth

- 行为：目标 ref 的 `.feature`。
- 可执行测试：各仓库测试源码和 native test command。
- 单次执行证据：不可变原生报告、同 stem Markdown 和 evidence envelope。
- 聚合索引：可删除、可重建派生数据。

### 9.2 幂等、重试和去重

- 摄取幂等键：`product_key + revision_set_id + parser_version`。
- smoke 幂等键：`revision_set_id + suite_key + environment_profile + attempt`。
- 基础设施失败允许按策略重试；断言失败默认不自动重试。
- 重复 webhook / schedule 事件先检查幂等键，避免重复运行。
- 重跑产生新 attempt，不覆盖旧 evidence。

### 9.3 部分失败

- 单仓 ref 解析失败：产品 ingest 为 `partial`；依赖该仓的跨仓结论为 unavailable。
- 关键行为仓库无法读取：按产品策略提升为 `blocked`。
- parser 不支持语法：保留原文件 locator，记录 parser gap，不跳过不报。
- smoke 环境失败：测试状态 `blocked`，与 assertion `failed` 分开。

## 10. P1.0 / P1.1 验收标准

P1.0 首次可运行基线要求：

- 四个公开子命令 `validate-config`、`decision`、`ingest`、`smoke` 可用。
- 能加载产品注册表和服务器 Workspace Mapping，并拒绝缺失的显式 target ref。
- 能将每仓 ref 固定为完整 SHA，生成 run 内不可变 Revision Set。
- 能只读解析无 ID 的 `.feature`，生成可重建目录且不修改源仓。
- 能在隔离 detached worktree 中调用至少 API 与 Web 的项目原生 smoke command。
- 能生成 Evidence Decision 和本地/runtime evidence bundle；publication 明确为 `not-configured`。

当前 P1.1 完整验收要求：

- 能按产品注册表读取多个仓库的独立目标 ref。
- 每个 ref 在 run 开始时解析并记录完整 SHA。
- 不切换或污染长期 clone / 开发者 worktree。
- 能解析无 ID 的现有 `.feature`，且不改写源文件。
- 能生成 Revision Set、只读行为目录和冲突候选。
- 能运行至少 API 与 Web 的项目原生 smoke command，并生成 `knowledge-server` evidence。
- 能按阶段执行 preflight、prepare、test 和 cleanup，且前置阶段失败后仍执行 cleanup。
- 能通过本地或命令式 Runner Adapter 调度原生命令；远端结果必须绑定同一 Revision Set 并返回可校验 attestation。
- 只接收当前命令生成或刷新的正式报告和同 stem 中文 Markdown，并生成 artifact manifest 与 checksums。
- 能验证可信 deployment metadata 的路径、issuer、digest、仓库 SHA 和 runner/tool/image attestation；无法证明时保持 `unverified` 或 `mismatch`。
- 能加载和校验产品注册表中的 Evidence Policy，并生成符合 Schema 的不可变 Evidence Decision。
- 能区分 `not-required`、`required` 和 `blocked`，记录 target、decision source 和 decision reason。
- 中央 / 产品 required policy 不能被仓库规则或显式参数降级；显式 target 只能增加发布目标。
- P2 尚未部署时，P1.1 生成的待发布 bundle 必须标记 `Evidence Publication: not-configured`，不能声称已经发布或满足远端 PR Gate。
- 所有产物可追溯到 repository key + ref + SHA。
- 重复事件不会无界地产生重复 run。
- 显式重跑通过新 attempt 保存，不覆盖原结果；基础设施失败可按策略重试，断言失败默认不重试。
- 生成可机器读取的 ingest / smoke metrics。
- 清理 runtime 后可从 SOT 与 evidence 重新构建目录。

---

# P2：多来源 Evidence Store 与 PR Gate

## 11. P2 目标

P2 在 P1.1 上增加证据发布、索引、PR 关联、失效与治理：

- 接收开发者本地上传的正式报告和 evidence envelope。
- 接收 CI runner 生成、绑定精确 PR head 的正式 evidence。
- 接收知识库服务器 smoke evidence。
- 在 PR 上按 `developer-local`、`ci`、`knowledge-server` 分别显示证据来源。
- PR head 变化时让旧 developer-local 和 CI evidence 失效。
- 将大型原始报告存入对象存储，元数据和索引存入数据库。
- 提供保留期、权限、脱敏、审计、重试和修复能力。

P1.1 与 P2 的职责差异：

| 能力 | P1.1 当前状态 | P2 计划状态 | 功能差异 |
|---|---|---|---|
| Evidence 生成 | 生成 Decision、原生报告、中文汇总、manifest、checksums 和 envelope | 重校验后接收并发布 | P1.1 证明 bundle 完整；P2 赋予远端身份和状态 |
| Evidence Publication | 固定 `not-configured` | 支持 `pull-request`、`knowledge-base` 或两者 | P2 才能声称已发布 |
| Evidence Store | runtime/local bundle | 不可变对象存储 + 元数据数据库 | P2 提供跨机器查询和长期保存 |
| Policy | Resolver 产生不可变 Decision | Enforcer 消费 Decision | P2 不重新解释 product policy |
| PR Head | bundle 记录 SHA，发布前需复验 | Provider Adapter 读取当前 Head 并比较 | P2 自动拒绝旧 SHA |
| PR Check | 无 | informational → required | P2 才改变 PR 页面和合并条件 |
| 自动失效 | 无跨系统状态 | `invalidated` / `superseded`，并触发重跑 | 新 Commit 后旧证据不再满足 Gate |
| 双目标状态 | Decision 可要求两个 target | 分目标记录 enforcement，全部满足才通过 | 单个 target 成功不能冒充整体满足 |
| 开发者本地 Evidence | 项目原生验证负责生成报告 | `collect / validate / publish` 关联 PR 或知识库 | 只有 Policy required 或显式 target 时才新增发布操作 |
| CI / Knowledge Server Evidence | 可生成精确 revision bundle | 自动发布和更新远端状态 | 通常不要求开发者手工操作 |
| 安全 | 基础敏感信息阻断 | 深度扫描、quarantine、授权、审计和签名链接 | P2 处理报告的远端暴露风险 |
| 生命周期 | runtime 清理 | retention、legal hold、tombstone、异步删除 | P2 管理长期证据成本和合规 |
| 可靠性 | run 幂等、attempt、基础设施重试 | publish/webhook 幂等、CAS、DLQ、replay、Schema 双读 | P2 处理分布式事件和远端状态一致性 |
| 门户 | 生成可消费目录和指标 | 展示当前/历史证据、PR 状态、失效原因和权限 | 门户从派生静态视图升级为证据查询入口 |

## 12. Evidence Policy Enforcer

P2 不重新读取并解释产品 Evidence Policy；它消费 P1.1 已生成并通过 Schema 校验的 Evidence Decision，把“required + targets”转换成实际发布和门禁动作。这样可以避免本地 CLI、知识库服务器和不同 PR Provider 各自实现一套不一致的策略解析。

执行流程：

```text
Evidence Decision
  -> 校验 decision schema version、policy version、content digest 和当前上下文
  -> 收集并校验 native reports、同 stem Markdown、checksums、evidence envelope
  -> 按 evidence_targets 路由 Publisher
  -> 写入 Evidence Store
  -> 更新 Knowledge Index / PR Check
  -> 计算 policy enforcement status
```

P2 应实现以下状态：

| 状态 | 含义 | 默认动作 |
|---|---|---|
| `not-required` | P1 决定本次不要求正式 Evidence | 不创建 required gate；可保留普通测试结果 |
| `required-pending` | Evidence 必须提供，但尚未完成收集、上传或服务器复验 | PR Check 保持 pending，知识库显示处理中 |
| `satisfied` | 所有 required target 已发布，版本、模式和环境条件满足 | 对应 Gate 通过 |
| `blocked` | 报告缺失、SHA 不匹配、环境 mismatch、脱敏失败或发布失败 | Gate 失败并给出可操作原因 |
| `invalidated` | PR head、Revision Set 或策略版本已变化 | 旧 Evidence 不再满足 Gate，触发新运行 |
| `waived` | 获授权的例外临时放行 | 记录审批人、原因、范围和过期时间 |

强制规则：

- `pull-request` target 必须由 PR Provider Adapter 重新读取当前 head SHA；不能只信任上传者提供的 PR 信息。
- `knowledge-base` target 必须在 Evidence Store 和知识索引均成功后才能标记该 target 已满足。
- 同时要求两个 target 时，必须两个都成功，整体状态才是 `satisfied`。
- `published` 只表示 artifact 已被目标接收；最终 Gate 还要验证测试状态、E2E Mode、环境对齐和 policy requirements。
- `smoke-only`、contract、mock、backend-only 只能满足允许该模式的 policy，不能自动满足要求 full-stack 或 release regression 的 Gate。
- 显式 publish 命令不能删除 P1.1 Decision 中的 required target。
- waiver 必须有授权主体、原因、适用仓库/PR、风险说明和到期时间；过期后恢复原 required policy。
- 每次 enforcement 必须记录 decision ID、policy version、decision source/reason、provider response 和最终状态，支持审计和重放。

P1.1 和 P2 的交接契约：

```yaml
decision_id: evd-decision-smart-20260715-0001
evidence_contract: required
evidence_targets:
  - pull-request
  - knowledge-base

enforcement:
  pull-request: satisfied
  knowledge-base: required-pending
  overall: required-pending
```

## 13. Evidence Store 分层

### 13.1 对象存储

保存不可变 artifact：

```text
evidence/<product>/<source>/<repository>/<commit-or-revision-set>/<run-id>/
├── evidence.json
├── checksums.sha256
├── reports/
├── summaries/
└── attachments/
```

不把 HTML、trace、视频、截图和大体积 JSON 长期提交到知识库 Git。

### 13.2 元数据数据库

索引：

- run、evidence source、trigger、repository、PR、revision set。
- 报告状态、测试模式、环境对齐状态。
- feature source locators。
- artifact URI、checksum、size、retention class。
- publication、superseded、invalidated、quarantined 状态。

数据库不是报告内容 SOT。丢失后可从对象存储 manifest 重建索引。

## 14. 开发者本地 Evidence 发布

后续可实现 CLI：

```text
sbtd evidence collect
sbtd evidence validate
sbtd evidence publish --target pull-request --pr <number>
sbtd evidence publish --target knowledge-base
```

P2 才实现这些命令；P0 没有提供命令。

发布 Gate：

- worktree 必须 clean。
- `sourceCommit` 必须为完整 SHA。
- PR repository 与 repository key 匹配。
- source commit 必须等于当前 PR head。
- 原生报告、同 stem Markdown 和 checksum 齐全。
- Schema 通过且 `secretsRedacted: true`。
- mock / smoke / backend-only 模式保持真实标记。
- publish target 必须是 P1.1 Evidence Decision 已允许或要求的 target；命令可以补充允许的目标，但不能删除 required target。
- Publisher 必须记录 `decision_id`，不能接受没有决策来源的 required-gate 上传。

不满足条件时可以保存本地诊断，但不能创建通过的 PR evidence check。

## 15. PR Check 模型

建议分别显示：

```text
Developer Validation Evidence
  source: developer-local
  head SHA: ...
  API: passed
  Web: passed
  Mobile: not-needed

Knowledge Server Smoke
  source: knowledge-server
  revision set: ...
  environment alignment: verified
  mode: smoke-only
  status: passed
```

新 commit 到达 PR 后：

- 旧 developer-local evidence 标记 `invalidated`，不得继续满足 gate。
- 与新 Revision Set 不匹配的服务器结果标记 `superseded`。
- 后台创建新 smoke run；不删除历史 evidence。

P0/P1/P2 均不规定必须使用 GitHub；provider adapter 可以实现 GitHub Check、GitLab Pipeline/MR widget 或内部代码平台接口。

## 16. 环境对齐

`Environment Alignment: verified` 必须有可检查依据，例如：

- 部署 manifest 记录的前端、后端和 app artifact SHA 与 Revision Set 匹配。
- 测试启动的本地服务直接来自 Revision Set worktree / image digest。
- 预发布环境提供受信任的 deployment metadata endpoint。

只有 URL 可访问但无法确认部署版本时，标记 `unverified`。已知版本不一致时标记 `mismatch`，不能声称服务器已独立验证目标 Revision Set。

## 17. 安全与权限

- 证据上传使用短期身份或 workload identity，不使用共享长期 PAT。
- 源仓读取、对象写入、PR Check 写入采用最小权限分离。
- 上传前扫描 token、cookie、账号、PII、生产数据、敏感 header、query/body、截图和 trace。
- 命中敏感信息的 bundle 进入 quarantine，不发布链接。
- Evidence Store 按仓库 / 产品权限授权，不能因中央门户聚合而扩大访问范围。
- 对象下载使用短时签名 URL；审计读取、下载、删除和 retention override。

## 18. 保留、删除与修复

建议保留策略由业务和合规确认：

- 普通 developer-local evidence：短周期。
- PR server smoke：中周期。
- release evidence：长周期或按审计要求。
- 失败报告可比成功报告保留更短，但关键缺陷调查可 legal hold。

删除采用两阶段：先 tombstone 元数据，再异步删除对象；失败任务可重试并可审计。索引损坏时从对象 manifest 重放；对象缺失时将 evidence 标记 `corrupt`，不得继续满足 gate。

## 19. 幂等、乱序、回放和 Schema 演进

- publish 幂等键：`run_id + evidence schema version + artifact manifest digest`。
- PR webhook 可能重复或乱序；以 provider event time、PR head SHA 和数据库 compare-and-set 决定当前状态。
- 旧 run 后到达时保存历史，但不能覆盖新 head 的 current evidence。
- 每次重试保留同一 logical run 和新的 attempt / transport record，避免重复对象。
- Schema 只做向后兼容增加；破坏性变更发布新 major schema version。
- reader 至少支持当前版本和前一版本；迁移前先双读验证，再切换写版本。
- Evidence Store 必须支持按 manifest replay 重建索引，并提供 dead-letter queue 处理长期失败事件。

## 20. 可观测性

至少监控：

- ingest 成功率、partial / blocked 比例、ref resolve 延迟。
- Revision Set 创建与 worktree 清理失败。
- smoke queue latency、runner availability、环境对齐失败。
- evidence upload、checksum、Schema、脱敏失败。
- PR head invalidation 延迟和 stale evidence 比例。
- 对象与数据库索引不一致数量。
- retention backlog、quarantine 数量、dead-letter queue 深度。

所有日志使用 run ID、revision set ID、repository key 和 PR key 关联，不记录敏感 payload。

## 21. P2 验收标准

- 能消费并校验 P1.1 生成的 Evidence Decision，不在不同 Publisher 中重复解释产品策略。
- 能按 `pull-request`、`knowledge-base` 或两者路由发布，并分别记录 target enforcement 状态。
- 所有 required target 都满足后才能把整体状态标记为 `satisfied`；任一 target 缺失、失败或失效时保持 pending/blocked。
- 能执行 `not-required`、`required-pending`、`satisfied`、`blocked`、`invalidated` 和带期限的 `waived` 状态迁移。
- 显式命令、仓库配置和上传请求都不能移除中央 / 产品策略要求的 target。
- developer-local、CI 与 knowledge-server evidence 分开存储、展示和授权。
- 开发者与 CI evidence 只能匹配当前 PR head，head 改变后自动失效。
- 服务器 evidence 能显示精确 Revision Set 与环境对齐状态。
- 原始报告不进入知识库 Git；对象与索引可校验、可审计、可重建。
- published 状态与 passed 状态完全分离。
- 重复、乱序 webhook 不会让旧证据覆盖新证据。
- Schema 升级、索引重放、对象缺失和发布失败均有恢复路径。
- 安全扫描失败的证据不会通过 PR Gate。

## 22. 分阶段上线与回滚

### 22.1 P1.0 / P1.1 已完成上线状态

| 阶段 | 已完成内容 | 对使用者的变化 | 回滚边界 |
|---|---|---|---|
| P1.0 | 产品/仓库配置、Evidence Policy、精确 Revision Set、只读 ingest、基础目录、隔离 API/Web smoke、待发布 bundle | 新增产品级配置与 `read / 读取`；项目原生测试命令不变 | 停止调度并删除派生目录/runtime worktree；不影响源 `.feature` 和业务仓库 |
| P1.1 | 完整解析、bindings、冲突候选、分阶段 smoke、Runner Adapter、Mobile labels、可信环境、报告完整性、幂等重试、metrics | 可获得更可靠的集中 smoke 和证据 bundle；仍没有远端发布或 PR Gate | 停用高级 runner/trust/stage 配置并回到 P1.0 基础路径；保留 Schema version `1` 兼容 |

### 22.2 P2 必须分阶段实现

P2 涉及远端有状态系统、PR 合并条件、安全权限和数据生命周期，不能作为一个整体直接启用。推荐依赖顺序：

```text
P2.1 接收与存储
  -> P2.2 Publisher 与 Shadow Enforcer
  -> P2.3 PR 集成与自动失效
  -> P2.4 高风险 Required Gate 与 Waiver
  -> P2.5 治理、可观测性与规模化
```

阶段名称是实施建议；每阶段必须独立部署、验收和回滚，上一阶段未达标不得开启下一阶段的阻断能力。

| 阶段 | 主要交付 | 使用者变化 | PR 状态 | 退出条件 | 阶段回滚 |
|---|---|---|---|---|---|
| P2.1 Evidence Intake & Store | Evidence 接收 API；Schema/checksum/Decision digest 校验；不可变对象存储；元数据索引；manifest 重建；幂等上传；基础 `collect / validate / publish` | 需要发布 developer-local evidence 时可显式上传；CI/服务器可自动上传；测试命令不变 | 不创建 Check，不阻断 | 重复上传返回同一逻辑结果；对象不可覆盖；数据库可从 manifest 重建；大型报告不进入 Git | 停止接收新上传；保留已接收不可变对象并按临时 retention 处理 |
| P2.2 Publisher & Shadow Enforcer | target 路由；分目标 publication；Enforcer 状态机；Decision 与实际发布 shadow 对账；`published` 与 `passed` 分离 | 可查看“策略要求”和“实际发布”的差异；不需要改变合并操作 | 无或仅内部 shadow，不阻断 | Enforcer 不重新解释 Policy；两个 target 独立记账；shadow 误判率和失败原因可观测 | 关闭 Enforcer，Evidence Store 继续只接收和查询 |
| P2.3 PR Integration & Invalidation | PR Provider Adapter；Webhook；当前 Head SHA 复核；信息型 PR Check；新 Commit 自动 `invalidated`；服务器结果 `superseded`；重调度 | PR 页面显示三类 Evidence；push/rebase 后需要重新验证或等待自动运行 | Informational，不阻断 | 重复/乱序事件不能让旧结果覆盖新 Head；失效延迟和重调度可监控；Check 给出可操作原因 | 关闭/移除信息型 Check；停止 webhook 消费；Store 保留历史数据 |
| P2.4 Required Gate & Waiver | 选择 P0/P1 高风险仓库/场景试点 required check；模式/环境/双目标校验；限时 waiver | 试点 PR 只有在匹配当前 Head 的 required Evidence 满足后才能合并；豁免需要负责人、原因和期限 | 仅试点范围阻断 | 无错误阻断；`smoke-only`/mock 不越权满足 full-stack；waiver 过期自动恢复；有紧急降级 runbook | 将 required Check 降级为 informational；暂停新 Gate；不删除历史 Evidence |
| P2.5 Governance & Scale | 扩大 required policy；深度扫描与 quarantine；最小权限、审计、签名链接；retention/legal hold/tombstone；DLQ/replay；Schema 双读；告警；Portal 历史/权限视图 | 更多仓库进入正式门禁；管理员获得隔离、保留、审计和恢复入口 | 按已批准 Policy 阻断 | 安全事件可隔离；删除和 legal hold 可审计；对象/索引不一致可修复；关键 SLO 有告警 | 按产品/仓库降级 Gate；暂停删除任务和新上传；保留审计与不可变 Evidence |

### 22.3 P2 分阶段实施原则

1. **先存储，再判断**：P2.1 只验证接收、不可变存储和索引恢复，不接入 PR。
2. **先 shadow，再展示**：P2.2 用实际数据验证 Enforcer，不影响开发者合并。
3. **先展示，再阻断**：P2.3 的 Check 只提供信息，待 Head 失效和乱序事件稳定后再启用 required。
4. **先小范围，再扩面**：P2.4 只选择高风险且已有稳定 P1.1 Evidence 的仓库试点。
5. **远端发布失败不等同测试失败**：必须分别展示 test status、publication status 和 enforcement status。
6. **阻断能力必须可快速降级**：Provider、Store 或 Enforcer 故障时可将 required Check 降为 informational，但不能伪造 `satisfied`。
7. **历史证据不可被新 run 覆盖**：失效和 supersede 只改变当前有效性，不删除既有记录。
8. **每阶段保留 P1.1 回退路径**：关闭 P2 后仍能本地生成、校验和查看 P1.1 bundle。

### 22.4 P2 对使用者的渐进变化

| 上线阶段 | 开发者 | QA / 产品 | 知识库与平台维护者 |
|---|---|---|---|
| P2.1 | Policy required 或显式 target 时执行/触发 publish；原生测试命令不变 | 可查询已上传 Evidence，但不能据此判断 Gate | 运维对象存储、索引、上传身份和基础扫描 |
| P2.2 | 无新的阻断操作 | 可对比 Decision 与发布结果 | 观察 shadow 差异并修正 Publisher/Enforcer，不修改 P1.1 Policy 语义 |
| P2.3 | PR 可见 Evidence Check；push/rebase 后旧证据失效，需要重验 | 可查看 developer-local、CI、knowledge-server 三条独立证据链 | 维护 Provider Adapter、Webhook、失效和重调度 |
| P2.4 | 试点高风险 PR 需要当前 Head 的 required Evidence；必要时申请限时 waiver | 审核证据模式、环境和剩余风险 | 负责 Gate 降级、waiver 审计和误阻断处置 |
| P2.5 | 更多仓库按已批准策略执行 | 使用 Portal 查看历史、覆盖和发布证据 | 负责 retention、quarantine、权限、审计、DLQ/replay 和 SLO |

### 22.5 P2 开工前置条件

- P1.1 在至少一个真实产品上稳定运行，能够持续生成完整 bundle、Decision、Revision Set、artifact manifest、checksums 和 metrics。
- 明确首个 Provider、对象存储、元数据数据库和工作负载身份方案；不要在 P2.1 同时实现多个代码托管平台。
- 明确 Evidence 数据分级、保留期限、访问主体、quarantine 和 legal hold 的责任人。
- 为 P2.1～P2.5 分别建立任务、验收数据和回滚演练；不得用“完成 P2”作为一个不可拆分任务。
- 当前仓库尚未初始化 Trellis；正式开发 P2 前应由使用者执行 `trellis init -u <username>`，或明确进入 onboard `init / reset` 流程，再把每个阶段落为独立任务产物。

## 23. 明确不在 P1.0 / P1.1 / P2 默认范围

- 自动生成、改写或集中复制产品 `.feature`。
- 为 `.feature` 添加 Feature ID、Scenario ID、owner 或 scope tag。
- 引入 Cucumber、Behave、pytest-bdd、cucumber-js 或其他 BDD Runner。
- 自动合并或删除跨仓重复行为。
- 把开发者本地通过直接当作服务器独立验证。
- 把服务器 smoke 当作完整回归或发布回归。
- 把大型报告、视频、trace、搜索索引或生产数据提交到知识库 Git。
