# KPi 实施路线图（ROADMAP）

> **文档版本**：0.7-draft  
> **文档日期**：2026-07-21  
> **对应 PRD**：`PRD.md`  
> **路线原则**：**OMP-first → KPi CLI → KPi Core → 双 Runtime → 必要时受控 Fork**  
> **SBTD 基线**：`SBTD Workflow Kit`（`sourceId=sbtd-workflow-kit-upstream`，`https://github.com/KunoLu/640-skills`）@ `340f9dd4dc7a92e8b91c31e111de9a8de06cef36`
> **说明**：P0～P3 是按依赖顺序排列的实施优先级，不是并行开发泳道，也不是缺陷等级。  
> **0.7 更新重点**：将项目规则拆为根 `AGENTS.md` 跨 Agent 事实层与 `.omp/AGENTS.md` OMP/KPi Adapter；增加 `@../AGENTS.md` 导入、双项目 Managed Block、Monorepo nearest-native 检测、三目标上游同步，以及由统一 Command Registry 生成的 `/sbtd help [command]`。

---

## 1. 路线总览

| 阶段 | 建议版本 | 核心路线 | 主要交付物 | 不做 |
|---|---|---|---|---|
| **P0** | `v0.1-alpha` | OMP-hosted SBTD MVP | Plugin、三层 AGENTS、`/sbtd help/on/off`、核心 Gate 与 Report | 不 Fork、不重写 Provider/Tool |
| **P1** | `v0.1-beta` → `v0.1` | KPi CLI 产品化 | `kpi`、Onboard/Provider/Session/Report CLI | 不抽离全部 Core |
| **P2** | `v0.2` | KPi Core 抽离 | Workflow/Rule/Policy/Validation/Provider/Core、TS Onboard | 不承诺双 Runtime 完整等价 |
| **P3** | `v0.3` | OMP/Pi 双 Runtime | `runtime-omp`、`runtime-pi`、兼容套件、Fork Gate | 未通过 Gate 不 Fork |

依赖关系：

```text
P0 OMP Plugin
  ↓
P1 KPi CLI
  ↓
P2 KPi Core
  ↓
P3 OMP/Pi Dual Runtime
  ↓
Controlled Fork（仅在必要时）
```

---

# P0 — OMP-hosted SBTD MVP

## 2. P0 目标

以最小的底层自研成本，把 `SBTD Workflow Kit` 中最关键的 SBTD 行为转换为 OMP 可执行插件，验证：

1. `/sbtd on` 是否能稳定改变后续每轮的工作流；
2. Book Gate、BDD、Trellis、GitNexus、Validation 与 Report 能否被结构化执行；
3. Dormant Rule 是否能减少模型偏航；
4. Session/Compaction/Resume 后状态是否连续；
5. SBTD 是否提升真实 Coding Task 的正确性，而不是只增加仪式。

## 3. P0 产品形态

```text
npm package: @kunolu/omp-sbtd

OMP
  └── plugin
      ├── command registry + /sbtd help
      ├── extensions/hooks
      ├── tools
      ├── rules
      ├── state
      ├── report renderer
      └── pinned read-only OMP Distribution Projection
          ├── canonical / projection provenance
          ├── OMP catalog / schema
          ├── Global / Root Project / OMP Project Adapter templates
          ├── OMP-compatible bundled Skills
          └── retained license / SBOM source metadata
```

P0 直接使用 OMP 的：

- Agent Loop；
- Provider 与 Model Roles；
- Tool Registry；
- TUI；
- Session；
- Compaction；
- Approval；
- LSP/DAP/Search/Edit；
- TTSR/Hook/Extension 能力；
- Plugin Manifest 和项目级 Override。

### P0-A：三层 AGENTS 与 Mode Contract（必须先完成）

```text
$PI_CODING_AGENT_DIR/AGENTS.md
  默认 ~/.omp/agent/AGENTS.md

<project-root>/AGENTS.md
  跨 Agent 项目事实

<project-root>/.omp/AGENTS.md
  OMP/KPi Adapter + @../AGENTS.md
```

范围：

- Platform-aware Global Path Resolver；
- Root Project Facts Template；
- OMP Project Adapter Template；
- `/sbtd on` = `enforced`；
- `/sbtd off` = `advisory`；
- 三类 Managed Block 与用户内容保留；
- `@../AGENTS.md` Import Validation；
- Context Bridge、Provider Shadow 和 nearest-native Detection；
- Onboard 同时处理根 AGENTS 与 `.omp/AGENTS.md`；
- OMP Onboard 不读取、迁移或删除非 OMP Runtime 配置；跨 Agent compatibility add-on 不属于 P0 base package。

P0-A 退出标准：

- normal Onboard 写入正确 OMP Global Path；
- 根 Project AGENTS 和 OMP Adapter 均写入正确路径；
- `/sbtd off` 停止自动 Gate，但保留 Root Facts/Always-on；
- `.omp/AGENTS.md` 正确导入根文件；
- `exists/discovered/loaded/effective/shadowedBy/imports` 可审计；
- 未知 Existing AGENTS 不被无确认覆盖。

### P0-B：上游 AGENTS 三目标转换与同步（P0 发布前完成）

```text
SBTD Workflow Kit locked source URI + resolved full SHA
  → Markdown Section Parse
  → agents-section-map.yaml
  → Global / Root Project / OMP Adapter Generator
  → Plugin Rule/Workflow/Skill Changes
  → Sync Report
  → Conformance Tests
```

范围：

- `upstream.lock.json`（`sourceId`、canonical source URI、resolved full SHA、可选 source tag、source digest）；
- `agents-section-map.yaml`；
- Transform Version；
- `AGENTS.global.md`；
- `AGENTS.project-root.md`；
- `AGENTS.project-omp.md`；
- Source/Generated Digests；
- Added/Changed/Removed/Unmapped Section 报告；
- Unmapped Section Release Blocker；
- 三类 Managed Block Update；
- Old-template Digest Migration；
- User-owned Content Preservation。

P0-B 退出标准：

- 上游两个 AGENTS 模板所有 Section 均有唯一 Owner 或显式 Split Targets；
- Generated 三类 AGENTS 与 Plugin/Skills 无语义漂移；
- 上游新增未知 Section 使 CI 失败；
- Plugin 更新后的 `/sbtd onboard plan/reset` 可安全同步三类 Managed Block。

## 4. P0 交付物

### SBTD Kit 制品生命周期与命名

`SBTD Kit` 是唯一产品制品名称；`SBTD Workflow Kit` 是由 `sourceId=sbtd-workflow-kit-upstream`、canonical source URI `https://github.com/KunoLu/640-skills` 与 resolved full SHA 锁定的外部上游基线和 provenance identity；`packages/sbtd-workflow-kit/` 是独立内部转换目录，负责将该基线转换为 SBTD Kit；`plugins/omp-sbtd` 中的 `@kunolu/omp-sbtd` 只表示 OMP Plugin 包。

| 阶段 | SBTD Kit 形态 | 发行边界 |
|---|---|---|
| P0 | 固定 Revision、只读、嵌入 `@kunolu/omp-sbtd` 的 Bootstrap Snapshot | 不独立安装或发布；Plugin 安装不写入用户/项目环境 |
| P1 | 同一 Bootstrap Snapshot 由不可变 Manifest、`kpi kit` 管理面和 Doctor 观察 | 仍随受支持 Plugin/CLI 分发，不承诺独立 Kit release |
| P2 | 包含 catalog、schemas、rules、workflows 和 licenses 的独立版本化 SBTD Kit | 可独立发布、升级和被 Runtime Adapter 消费 |

所有阶段均从 `upstream.lock.json` 中锁定的 sourceId、canonical source URI、resolved full SHA、可选 source tag 与 source digest 生成，并记录 Revision 与 Digest；不得使用 Floating Main、未审阅 remote fetch 或 Git submodule 作为用户消费路径（与 `PRD.md` 的 D-014 一致）。

### P0-E1：插件骨架

交付：

- `@kunolu/omp-sbtd` 包；
- OMP Plugin Manifest；
- Feature/Settings Schema；
- 固定 Revision、只读、嵌入 Plugin 的 SBTD Kit Bootstrap Snapshot；
- Plugin ↔ Kit Revision 映射；
- 插件安装、启用、禁用、Doctor 文档；
- 支持工作区当前锁定且正在使用的精确 OMP 版本；不由 peer range 推断历史或未来版本兼容性。

安装原则：

- 不定义会写用户/项目环境的 Package `postinstall`；
- 不复制 AGENTS、Skills 或模板；
- 不安装 Trellis、GitNexus、RTK、Java、Maestro、Playwright；
- 不配置 MCP、Provider、Model Role；
- 仅允许 OMP 自身 Plugin Registry/Lock/Cache 变化。

验收：

- `omp plugin install` 或等价流程可安装；
- 安装前后环境 Diff 证明没有非 Plugin 管理写入；
- Plugin Doctor 返回明确状态；
- Kit Revision 与文件摘要可校验；
- 插件禁用后不改变 OMP 默认行为；
- 不修改 OMP Core。

### P0-E2：Slash Commands

实现：

```text
/sbtd help [command]
/sbtd on
/sbtd off
/sbtd status
/sbtd route
/sbtd doctor
/sbtd onboard status
/sbtd onboard plan
/sbtd onboard init
/sbtd onboard reset
/sbtd onboard init-projects
/sbtd setup
/sbtd report
/sbtd strict
/sbtd relaxed
```

验收：

- `/sbtd help` 在所有 `environmentMode` 和 `runtimeMode` 下可用；
- `/sbtd help <nested command>` 支持如 `onboard init`；
- Help 不调用模型、不创建 Agent Turn、不修改 Session；
- `/sbtd on` 原子执行“准备目标 Runtime Mode、Onboard Profile 与 Route → 只读 Preflight → 可确定时提交 `runtimeMode=enforced` 与当前 Environment observation → 派生 Effective Control State”；evaluator 失败保留命令前状态并返回 repair path；
- 未完成 normal Onboard 且无 accepted-skip 时返回 `environmentMode=needs-onboard`，不自动安装；
- `/sbtd onboard plan` 零写入；
- Apply 类命令显示计划并获得确认；
- `/sbtd off` 只设置 `runtimeMode=advisory`，保留 Policy Profile、Onboard Profile、AGENTS、Skills、Tools 和历史报告；
- `/sbtd status` 按字段名显示 Environment Mode、Runtime Mode、Policy Profile、Onboard Profile、Effective Control State、Stage、Route、Book Gates、三层 AGENTS、Tool Evidence、Validation Status 和 Provider；
- `/sbtd strict|relaxed` 只修改 `policyProfile`，不得修改 Runtime Mode 或关闭 Route-required Checks；
- 命令在 Resume 后保持一致，Environment 重新观测，Effective Control State 重新派生。
- Route、Policy Profile 或 Onboard Profile 改变必须使用同一原子 re-observation 事务；在新 Environment observation 可确定前不得使用新的 Effective Control State。

### P0-E2A：首次使用与 Onboard UX

P0 标准链：

```text
OMP Provider/Login 已配置
  → omp plugin install @kunolu/omp-sbtd
  → 新 Session / Reload Plugin
  → /sbtd help
  → /sbtd doctor
  → /sbtd onboard plan
  → 用户确认
  → /sbtd onboard init|reset|init-projects
  → 新 Session / 完整资源 Reload
  → /sbtd on
```

要求：

- P0 不依赖尚未发布的 `kpi` CLI；
- Plugin Install 和 Onboard 是两个独立事务；
- `/sbtd setup` 是 Plan Wizard，不直接 Apply；
- Plan 显示 Kit Revision、锁定的上游 sourceId/URI/SHA、Global/Root/OMP Adapter 三类目标路径、Managed Digests、备份和可选项；仅 Optional 且非 Route-required 的省略目标可显示 `create-accepted-skip` action；
- Onboard 完成后，如果 Runtime 不能完整 Reload AGENTS/Skills/MCP，必须要求新 Session；
- `/sbtd on` 不得把 “configured” 当成 “callable”。

验收：

- Fresh OMP + Plugin + 缺 normal Onboard 基线可稳定进入 `environmentMode=needs-onboard`；
- 完成 Onboard 并新建 Session 后进入 `environmentMode=managed`；
- 无根 Project AGENTS 且无 accepted-skip 时进入 `environmentMode=needs-onboard`；
- 无 OMP Project Adapter 且无 accepted-skip 时进入 `environmentMode=needs-onboard`；
- 仅 Optional 项目上下文缺失、有效 `AcceptedSkipV1` 由独立确认的 `create-accepted-skip` Plan action 创建、且 Route 不依赖缺口时进入 `environmentMode=degraded`；
- 用户取消 Plan 后无任何环境变化；
- 同一 Plan 重复执行保持现有 Onboard 幂等和回滚语义。

### P0-E2B：Command Registry 与 `/sbtd help`

实现统一 `SbtdCommandSpec`：

```text
path / aliases
category
summary
usage
examples
mutates
requiresConfirmation
availableEnvironmentModes
```

同一 Registry 生成：

- 命令解析；
- `/sbtd help`；
- 未知命令建议；
- PRD/README 命令表；
- P1 Shell Completion；
- Command Contract Tests。

验收：

- 所有公开命令都有 Summary、Usage 和至少一个 Example；
- 写操作明确标记 `mutates=yes` 和 `confirmation=required`；
- Registry 与实际 Handler 一一对应；
- 删除或新增命令时，Help Snapshot 和文档测试同步变化；
- 帮助输出不依赖 LLM 文案生成。

### P0-E3：Session State 与 Event Bridge

挂接优先级：

```text
session_start
before_agent_start
context
tool_call
tool_result
turn_start
turn_end
session_before_compact / session.compacting
session_switch / branch / tree
session_shutdown
message_update / ttsr_triggered（可用时）
```

持久化状态：

```text
stateVersion: 1
runtimeMode: enforced | advisory
policyProfile: strict | relaxed
onboardProfileId: <catalog profile id>
securityBaseline: local-guarded
environmentMode: managed | needs-onboard | degraded | blocked
environmentObservedAt
stage
classification
route
activeSkills
bookGates:
  gateState: planned | running | passed | blocked | not-required
  reviewerStatus: <gate-specific>
toolEvidence
validation
provider
lessons
decisions
agents:
  global
  projectRoot
  ompProjectAdapter
  effectiveNativePath
  imports
  shadowedBy
```

`effectiveControlState: active|advisory|preflight-only|blocked` 只派生，不持久化。禁止持久化 `enabled` 或裸 `mode`。

统一状态字段必须与 PRD 8.9 完全一致：

| 字段 | 合法值 | 所有者 | 持久化 |
|---|---|---|---|
| `runtimeMode` | `enforced \| advisory` | Session / 用户命令 | 是 |
| `policyProfile` | `strict \| relaxed` | Session / Policy | 是 |
| `onboardProfileId` | SBTD Kit `catalog.json` 中定义的稳定 Profile 标识 | Session / Onboard selection | 是 |
| `securityBaseline` | `local-guarded` 等独立安全基线标识 | Policy / 安全配置 | 是，独立于 Policy Profile |
| `environmentMode` | `managed \| needs-onboard \| degraded \| blocked` | Preflight / Environment Management | 是，连同观测时间 |
| `effectiveControlState` | `active \| advisory \| preflight-only \| blocked` | 状态选择器 | 否，只派生 |
| `gateState` | `planned \| running \| passed \| blocked \| not-required` | Workflow / Gate Engine | 是 |
| `stageStatus` | `pending \| running \| passed \| blocked \| skipped \| not-needed` | Workflow Stage | 是 |
| `checkRequirement` | `required \| optional \| not-applicable` | Route 分类 | 是 |
| `validationStatus` | `passed \| failed \| blocked \| skipped \| not-needed` | Validation / Report | 是 |
| `capabilityStatus` | `native \| adapter \| degraded \| unsupported` | Runtime Adapter Evidence | 是 |
| `onboardProjectStatus` | `failed \| blocked \| needs-user \| bootstrap-required \| success \| skipped` | Environment Management | 是 |
| `managedAssetState` | `absent \| exact \| drifted \| merge-required \| blocked` | Provenance Inventory | 是 |
| `evidenceSource` | `developer-local \| ci \| knowledge-server \| not-needed` | Evidence Envelope | 是 |
| `sourceRevision` | `exact \| dirty \| unknown \| not-needed` | Evidence Envelope | 是 |
| `environmentAlignment` | `verified \| unverified \| mismatch \| not-needed` | Evidence Envelope | 是 |
| `evidencePublication` | `local-only \| published \| blocked \| not-configured \| not-needed` | Evidence Envelope | 是 |

Environment Mode 按 `blocked` → `needs-onboard` → `degraded` → `managed` 首个命中项唯一判定；`degraded` 要求当前 Route 的 Required 能力完整，并且每个 Optional 缺口都有匹配 scope、`onboardProfileId`、Kit major 且未过期的 accepted-skip provenance。

验收：

- Compaction 前后持久化字段不重置；
- Branch/Switch 后按 Session 重建；
- State 使用非 LLM Persistent Entry；
- 四种 Runtime Mode × Policy Profile 组合、所选 Onboard Profile 的 Required/Optional 基线矩阵，以及八种 Runtime Mode × Environment Mode 派生组合都有 Fixture；
- Resume 恢复 Runtime Mode、Policy Profile 与 `onboardProfileId`，重新观测 Environment Mode，并重算 Effective Control State；
- Draft `enabled`/裸 `mode` 只允许无歧义兼容迁移；冲突字段、未知版本和非法枚举 fail closed；
- 三层 AGENTS 状态和 Import/Shadow 信息可恢复；
- 关键变化同时产生可读 UI 状态。

### P0-E4：SBTD 分类与 Route

实现最小 Route：

```text
small-direct-change
bugfix
bdd-user-visible-change
trellis-managed-task
legacy-safe-change
refactoring-pass
data-design-risk
web-runtime-diagnostics
web-e2e-regression
mobile-e2e
release-readiness
review
```

分类输入：

- 用户请求；
- Repo Facts；
- AGENTS；
- Trellis；
- Diff/Task；
- 现有 Feature/Test；
- 风险 Predicate。

验收：

- 小型文档/配置任务不会自动进入完整 Trellis；
- 用户可见变化必定标记 BDD；
- Existing Production Code 标记 Refactoring Gate；
- Existing Behavior Bug 标记 Legacy Gate；
- Data/Async/Cross-service 标记 DDIA Gate；
- Production Path 标记 Release Gate；
- Route 输出包含客观原因。

### P0-E5：Book Gate Plan

实现 5 个 Gate：

1. DDD Boundary Review；
2. DDIA Data Design Review；
3. Legacy Change Safety Review；
4. Refactoring Review；
5. Release Readiness Review。

验收：

- 每个开发任务输出 Gate Plan；
- `gateState` 符合 `planned|running|passed|blocked|not-required`；
- Gate-specific `reviewerStatus` 与 `gateState` 分字段持久化；

Gate-specific `reviewerStatus` 的状态域与恢复路径必须与 PRD 11.2 完全一致：

| Gate | `reviewerStatus` | 恢复到通过 |
|---|---|---|
| DDD Boundary Review | `confirmed \| needs-clarification \| blocked` | 澄清后复审至 `confirmed` |
| DDIA Data Design Review | `confirmed \| needs-design-change \| blocked` | 修正数据设计后复审至 `confirmed` |
| Legacy Change Safety Review | `characterized \| needs-safety-net \| seam-required \| blocked` | 安全网或最小 safety seam 后复审至 `characterized` |
| Refactoring Review | `proceed \| refactor-first \| blocked` | 最小行为保持重构后复审至 `proceed` |
| Release Readiness Review | `ready \| needs-mitigation \| blocked` | 缓解与必需验证后复审至 `ready` |
- `grill-with-docs` 完成后强制 DDD 二次审核；
- Legacy/Refactoring `safety-seam-only` 回路可执行；
- Release Gate 必须位于验证之后；
- Required Gate 未通过时阻断相应阶段。

### P0-E6：SBTD Kit Bootstrap Snapshot Loader

加载：

- Plugin 内固定 Revision、只读、不可独立安装的 SBTD Kit Bootstrap Snapshot；
- OMP Global AGENTS、根 Project AGENTS、OMP Project Adapter 与 Deep AGENTS；
- 15 Bundled Skills；
- 14 External Skills；
- Lessons 短入口与命中 Topic；
- Trellis Workflow/Spec/Task；
- BDD Feature；
- Project Validation；
- Knowledge Base P1.1 说明。

策略：

- 安装 Plugin 时不把 Kit 内容复制到用户或项目目录；
- `/sbtd onboard` 才把固定 Kit 作为显式安装源；
- 不在每次 `/sbtd on` 时联网拉取仓库 `main`；
- 常驻只放 Route、Hard Boundary、Status Contract；
- Skill 内容按需；
- 不默认读取全部 Lessons；
- 缺失 Skill 标记 Blocked 或按规则降级。

验收：

- Context 使用可观察；
- 重复 Turn 不重复注入完整 Skill；
- Skill 版本和来源进入 Doctor；
- 固定 revision migration map 中的旧 Onboard Skill ID 不作为别名保留。

### P0-E6A：三层 AGENTS Contract Bridge

实现：

- OMP Global Path Resolver：`$PI_CODING_AGENT_DIR/AGENTS.md`，fallback `~/.omp/agent/AGENTS.md`；
- Root Project Resolver：`<project-root>/AGENTS.md`；
- OMP Project Adapter Resolver：`<project-root>/.omp/AGENTS.md`；
- `@../AGENTS.md` Import Validation；
- Global/Root/Adapter/Deep AGENTS 发现；
- Root Facts Context Bridge 与内容摘要去重；
- OMP Provider Shadow/nearest-native Detection；
- 包含 `runtime-mode`、`policy-profile`、`onboard-profile-id`、`environment-mode`、`effective-control-state` 和 `state-version` 的 Runtime Marker；
- 三类 Managed Block Parse/Replace；
- 用户内容保留；
- 旧已知模板迁移；
- 未知 Existing File 的 `merge-required`；
- 旧 `--skip-project-agents` → `--skip-project-root-agents` 弃用映射。

验收：

- Global Path 支持 `PI_CODING_AGENT_DIR`；
- 根和 `.omp/AGENTS.md` 均写入正确位置；
- Adapter 必须导入根 AGENTS；
- `.omp/AGENTS.md` 或其他 Provider Shadow 状态可见；
- 更近 Workspace Adapter 被识别，不静默忽略根 Adapter；
- `/sbtd on` 仅在确定性 Preflight 后原子提交 `runtimeMode=enforced` 与当前 Environment observation，并从已提交字段派生 `effectiveControlState`；evaluator 失败保留命令前状态；
- `/sbtd off` 设置 `runtimeMode=advisory` 并保留 Root Facts/Always-on；
- 三类 Managed Block 外内容字节级保留；
- Marker/Import 损坏时得到 `environmentMode=blocked` 并安全阻断。

### P0-E6B：Upstream AGENTS 三目标同步流水线

实现：

```text
upstream.lock.json
agents-section-map.yaml
transform-version.json
generated/agents/omp/AGENTS.global.md
generated/agents/omp/AGENTS.project-root.md
generated/agents/omp/AGENTS.project-omp.md
sync-report.json
sync-report.md
```

Section Owner：

```text
omp-global-agents
project-root-agents
omp-project-agents
plugin-rule
plugin-workflow
skill:<name>
onboard
ignored-with-reason
```

同步流程：

1. 固定 `SBTD Workflow Kit` 的 resolved full SHA（可选记录来源 Tag）；
2. 比较 AGENTS/Catalog/Skills；
3. Markdown AST 按 Heading/Section Digest 识别；
4. 应用 Owner 或显式 Split Targets；
5. 生成三类 AGENTS；
6. 输出 Plugin Rule/Skill 影响清单；
7. 运行 Golden/Conformance Tests；
8. Unmapped Section 阻断 Release；
9. 发布 Plugin/Kit；
10. 用户通过 `/sbtd onboard plan/reset` 更新三类 Managed Block。

验收：

- 上游每个 Section 唯一映射或显式 Split；
- Removed/Renamed Section 有迁移结果；
- 未映射新增内容使 CI 失败；
- Sync Report 包含 Source Commit、Digest、Owner、Transform Version 和三个 Generated Digest；
- Installed 三类 Managed Block 可从旧 Kit 安全更新；
- 不在 `/sbtd on` 时联网拉取 `main`。

### P0-E7：Rule/Policy Gate

P0 规则：

- 禁止普通任务自动 `trellis init`；
- BDD 缺失阻断可见行为交付；
- Required Book Gate 未通过阻断编辑/交付；
- RTK 报告风险；
- Report Artifact Gate；
- Mock/Contract/App-mocked 不得冒充 Full-stack；
- GitNexus 强证据；
- Maestro Java 17+；
- Dependency/Global Install Approval；
- Secret Path Guard；
- Release Gate。

验收：

- Tool Call 可 Block；
- Rule Match 可 Remind/Interrupt；
- Block Reason 对用户可见；
- Rule 在 Compaction 后仍有效；
- Rule 不误匹配代码块、路径或示例文本；
- 可通过项目配置禁用 Optional Rule，Hard Rule 不能静默关闭。
- `policyProfile=relaxed` 不提升 Optional Checks，`policyProfile=strict` 只提升已声明 Optional Checks；两者均不能降低 Route-required Checks。

### P0-E8：Validation 与 Report

实现：

- Focused validation → affected-scope validation → planned final full validation → 对该 final run 执行 formal artifact/freshness/sanitization gate；
- Project-defined Commands；
- RTK/Native Gate；
- BDD Language/Trace；
- Playwright/Maestro/API Formal Report；
- Evidence 的 `evidenceSource`、`sourceRevision`、`environmentAlignment` 与 `evidencePublication` 独立状态；
- Final Full Rerun；
- Structured JSON + Chinese Markdown Report。

验收：

- 报告文件 mtime/size/content 可验证；
- stdout-only 不满足 Formal Gate；
- 同 stem 中文 Markdown；
- E2E Mode 不升级；
- Dirty Revision 不作为 PR Head 证据；
- `validationStatus=failed|blocked|skipped|not-needed` 可区分，并与 `checkRequirement` 分字段记录。

### P0-E9：OMP-native TypeScript Onboard

支持：

```text
status
plan
init
reset
init-projects
```

P0 原则：

- Plugin 内固定 schema-v2 OMP Distribution Projection 与 TypeScript `OnboardService` 是 P0 Source of Truth；它管理 Global、Root Project 与 OMP Project Adapter 三类目标；
- `/sbtd onboard` 是 P0 用户入口，`kpi onboard` 属于 P1；
- Plugin Install/Load 不调用 Onboard；
- 写操作必须 `plan` 后确认；
- `--yes` 语义由经验证的 TypeScript Plan/Apply 契约定义；
- 多项目状态与诊断经 typed P0 contract 输出；
- Onboard 不执行或输出 Python bridge；canonical vendored `onboard.py` 不是 Plugin 载荷。

验收：

- 可显示 Plugin Version、canonical/projection provenance、Global/Root/OMP Adapter 三类路径、Import/Shadow 状态、Managed Digests 与 Plan；
- Plan/status 不调用子进程，且只使用已加载 OMP projection capability inventory；
- Plan 保持零写入；确认 Apply 后才修改目标；
- Exit Code 与逐项目 `onboardProjectStatus` 及其 aggregate precedence 正确；
- 不吞掉 Rollback Path；
- Project-only 不触碰 Global State。

### P0-E9A：Onboard/Runtime 工具生命周期

按 PRD 8.9 的 Tool Evidence schema 独立记录：

```text
installation: installed | missing | broken | not-needed
configuration: configured | not-configured | not-needed
callability: callable | unavailable | blocked | not-needed
projectReadiness: ready | not-ready | blocked | not-needed
freshness: current | stale | unknown | not-needed
observedAt
evidence
blockedReason
```

`AcceptedSkipV1` 由 Environment Management / Provenance Inventory 按 `schemaVersion`、`recordId`、asset-or-capability、scope、`onboardProfileId`、Kit major、confirmation actor/time、expiry、`active|revoked|expired` status、reason、evidence reference 与 provenance/version metadata 保存。仅当所选 Onboard Profile 将目标标为 Optional、且当前 Route 不依赖缺口时，`/sbtd onboard plan` 才可添加 `create-accepted-skip` action；该 action 必须列出 asset-or-capability、scope、`onboardProfileId`、Kit major、expiry 与 reason，并在 Apply 前独立确认。Environment observer 只接受 active、未过期、精确匹配 scope/`onboardProfileId`/Kit major 的记录；Route-required capability 永远不能跳过。创建、撤销、过期均为 Plan-first 版本化操作，Doctor/Report/Evidence 输出 owner、validity、provenance 与 repair path。

`managedAssetState=merge-required` 时，Plan 只允许保留并阻断、用户手工合并后重新 Plan，或由 recorded prior digest 授权的已知模板迁移。Apply 立即重验 provenance/digest，按适用情况写入或保留 backup，记录 operation id、selected action 与 residuals，并以 `exact|merge-required|blocked` 终结；completed operation 重试返回既有结果，陈旧 digest 必须重做 Plan，Rollback 只恢复重验过的精确 prior block。

#### Plugin 安装与 Onboard 的写入矩阵

| 目标 | Plugin Install | `/sbtd on` | normal Onboard | project-only |
|---|---|---|---|---|
| OMP Plugin/Kit | 安装 | 加载 | 不重复安装 | 不涉及 |
| OMP Global AGENTS/Skills/Tools/MCP | 不写 | 只读检测 | Plan+确认后处理 | 禁止处理 |
| 根 Project AGENTS | 不写 | 读取项目事实 | Managed Block 逐项目处理 | Managed Block 逐项目处理 |
| OMP Project Adapter | 不写 | 读取 Mode/Import Contract | Managed Block 逐项目处理 | Managed Block 逐项目处理 |
| Project `.gitignore` / `.trellis/` | 不写 | 只读检测 | 逐项目处理 | 逐项目处理 |
| GitNexus Index/Hook | 不写 | 检测 | 默认不自动创建 | 不涉及 |
| Provider/Login/Model | 不改 | 只读报告 | 不修改 | 不涉及 |

#### Trellis

- Onboard 可在确认条件下初始化；
- 普通 Runtime 只检测，不自动 `trellis init`；
- 加载 `workflow.md`、Task/Spec、Bootstrap 状态；
- 小任务/非 Trellis 项目继续 Native Route。

#### GitNexus

- Onboard 安装 CLI、可选配置用户级 OMP MCP；
- Runtime 必须同时确认 MCP callable、Index、Branch 与 Freshness；
- Stale 刷新失败时降级 Advisory，并回到源码/Diff/测试。

#### Playwright/Maestro/MCP

- Playwright 只按项目适用性安装到 devDependency；
- Maestro 区分 Java、CLI、MCP、设备和 App Artifact；
- MCP 配置存在不等于当前 Session 可调用；
- Auth/Token 不进入项目和报告。

验收：

- Tool Evidence 五个 facet 的交叉组合都有 Fixture，任何 facet 都不能推出另一个 facet；
- Project-only 不触碰 Global Tool/Skill/MCP；
- Tool 不可用时先记录对应 Tool Evidence facet；依赖它的 Check 再记录 `validationStatus=blocked|skipped|not-needed`，不得把两者合成一个状态。

### P0-E10：Provider Delegation

P0 不自研 Provider 执行或认证；OMP Runtime 管理 BYOK、OAuth/Plan/Local、Model Role、Fallback 与兼容 Provider。KPi 插件只观察并记录不敏感的 Provider Coordination 结果：

```text
provider profile
model role
availability
fallback used
runtime selection result
```

验收：

- 不读取 OMP 凭据文件；
- 不把 Key 注入 LLM Context；
- Provider 不可用时给出明确 Blocker；
- Codex/Claude/Kimi Subscription 仅由 Runtime 或用户控制的官方 CLI 管理；
- DeepSeek 通过 Runtime-compatible Provider 配置验证；
- KPi 不拥有认证、凭据刷新、模型执行或 Streaming Transport。
### P0-E11：测试矩阵

必须覆盖：

1. 小型 Docs/Config；
2. 新用户可见 Feature；
3. Existing Behavior Bug；
4. Existing Production Code 修改；
5. Data/Schema/Async 变更；
6. Production API/Job/Integration；
7. Web E2E；
8. Mobile E2E Blocked/Available；
9. Cross-repo Contract-only；
10. Session Resume/Compaction；
11. Multi-project Onboard；
12. Provider Unavailable/Fallback；
13. Global + Root + OMP Adapter + Plugin → `environmentMode=managed`；
14. 缺 OMP Global AGENTS、无 accepted-skip → `environmentMode=needs-onboard`；
15. 缺 OMP Project Adapter、无 accepted-skip → `environmentMode=needs-onboard`；
16. 缺根 Project AGENTS、无 accepted-skip → `environmentMode=needs-onboard`；
17. 仅 Optional 上下文缺失、由独立确认的 `create-accepted-skip` action 创建的 accepted-skip 有效且 Route 不依赖缺口 → `environmentMode=degraded`；
18. `/sbtd on` 与 `/sbtd off` 只改变 `runtimeMode`；
19. `/sbtd strict` 与 `/sbtd relaxed` 只改变 `policyProfile`；
20. Runtime Mode × Policy Profile 四种持久化/Resume 组合；
21. Runtime Mode × Environment Mode 八种 `effectiveControlState` 派生组合；
22. Route 变化使原 `degraded` 缺口变成 Required → `environmentMode=blocked`；
23. accepted-skip 过期或 scope/`onboardProfileId`/Kit major 不匹配 → `environmentMode=needs-onboard`；
24. `/sbtd off` 后 Root Facts/Always-on 仍有效；
25. `.omp/AGENTS.md` 的 `@../AGENTS.md` 导入；
26. 同层 Native Adapter 对根独立 AGENTS 的预期 Shadow；
27. 更近 Workspace `.omp/AGENTS.md` nearest-native Detection；
28. Managed Block 外用户内容保持；
29. Old-template Digest 迁移与未知文件 `managedAssetState=merge-required`；
30. Upstream 新增 Unmapped Section 阻断 CI；
31. Plugin Update → Plan → Reset → New Session 的三文件同步闭环；
32. Plugin Install 环境 Diff 为零非 Plugin 写入；
33. `/sbtd onboard plan` 零写入；
34. Onboard 后未 Reload 时不得声称新 Skills/MCP `callability=callable`；
35. `/sbtd help` 全命令与嵌套命令 Snapshot；
36. Help 零模型调用、零 Session Mutation；
37. Registry/Handler/Help/Docs 一致性；
38. Unknown Command 的候选和 Help 提示；
39. Draft `enabled`/裸 `mode` 的无歧义迁移、冲突拒绝和未知 `stateVersion` repair path。

## 5. P0 退出标准

P0 完成必须满足：

- 核心场景端到端通过；
- 无已知 Hard Gate 静默绕过；
- 无敏感凭据落盘/日志泄露；
- 工作区当前锁定 OMP 版本的兼容测试可自动运行；升级前必须重新执行该精确版本检查。
- `/sbtd help`、Parser、Handler、文档和测试共享同一 Registry；
- OMP Global、根 Project、OMP Project Adapter 三层 Contract 通过；
- `.omp/AGENTS.md` 导入根事实并正确处理 nearest-native；
- Plugin Install/Load 与 `/sbtd on` 通过零环境写入测试；
- `/sbtd onboard` 是 P0 唯一产品化 Onboard 入口；
- Fresh Install 的 `environmentMode=needs-onboard`、完整配置后的 `environmentMode=managed`、accepted-skip 条件满足后的 `environmentMode=degraded` 可重复；
- Runtime Mode、Policy Profile 与 Effective Control State 的独立语义和组合矩阵可验证；
- 上游三目标转换/同步流水线通过，所有 Section 已映射且无语义漂移；
- Onboard 与 Runtime 对 Trellis/GitNexus/MCP 的职责没有交叉写入；
- P0 价值 Gate 同时满足：确定性 Contract Gate 通过；至少 20 个代表性任务在同一 Runtime/Model 基线下配对执行；盲评正确性不低于基线；严重工作流遗漏至少减少 30%；Mandatory Gate recall 为 100%；不必要的重 Route 激活不超过 5%。

## 6. P0 明确不做

- 独立 KPi Provider 执行、认证或 Credential 管理；
- 完整 TypeScript Onboard 重写；
- Pi Runtime；
- OMP Fork；
- 自研 LSP/DAP/Search；
- 云端 Evidence Store；
- 默认 Channel Spawn；
- 删除或废弃全局/项目 AGENTS；
- 在 Package `postinstall`、Plugin Load 或 `/sbtd on` 时静默安装、初始化或改写 AGENTS、Skills、External Tools、MCP 或项目；
- 使用 P1 的 `kpi onboard` 作为 P0 必需流程。

---

# P1 — KPi CLI 产品化

## 7. P1 目标

让用户无需理解 OMP Plugin 安装细节即可使用 KPi；`kpi` 默认请求 `runtimeMode=enforced`，但只有 `managed` 或合规 `degraded` 才派生 `effectiveControlState=active`：

```text
kpi
  → 检查 Runtime
  → 检查/安装 Plugin
  → 加载 SBTD Kit Bootstrap Snapshot
  → 执行只读 Preflight
  → needs-onboard：显示 Onboard Plan
      → 用户确认 Apply → 验证 → 完整 Reload / 新 Session → enforced + managed → active
      → 用户拒绝 → 启动 runtimeMode=enforced、environmentMode=needs-onboard 的 Session → preflight-only
  → managed：启动 OMP Session 并提交 runtimeMode=enforced → active
  → degraded：仅在有效 AcceptedSkipV1 覆盖 Optional 非 Route-required 缺口时启动 → active
```

P1 建立品牌、配置、安装、Doctor、Onboard、Provider、Session 和 Report 的产品边界。

## 8. P1 交付物

### P1-E1：独立 CLI

命令：

```text
kpi
kpi run -- <prompt>
kpi plan
kpi review
kpi validate
kpi doctor
```

要求：

- TypeScript ESM；
- Node.js LTS；
- 显式 Command Table；
- 裸 `kpi` 只启动交互 Session；只有 `kpi run -- <prompt>` 接收单次自然语言；未匹配 KPi 命令返回候选和 Help，不创建 Agent Turn；
- Management Reserved Words Guard；
- Exit Code 稳定；
- JSON Output 可选。

### P1-E2：默认 SBTD 体验

- `kpi` 与 `kpi run` 默认设置 `runtimeMode=enforced`；
- `--sbtd=off|on` 只覆盖 Runtime Mode；
- 项目配置提供 Runtime Mode、Policy Profile 与 Onboard Profile 默认值，Session 命令分别覆盖；
- 直接 OMP 仍需 `/sbtd on`；
- 首屏分别显示 Runtime、Provider、Runtime Mode、Policy Profile、Onboard Profile、Environment Mode、Effective Control State、Project、Trellis 和 Kit Version。

### P1-E3：Runtime Bootstrap

实现：

```text
kpi runtime doctor
kpi runtime install omp
kpi runtime update omp
```

要求：

- 检查 OMP 版本；
- 检查 Plugin Version；
- 检查兼容区间；
- 不静默升级；
- 安装/升级需确认；
- 支持本地开发 Link。

### P1-E4：Onboard CLI

```text
kpi onboard check
kpi onboard check-projects
kpi onboard plan
kpi onboard init
kpi onboard reset
kpi onboard init-projects
```

要求：

- 默认 `--platform omp`；
- 保留 `codex/claude/kimi/omp`；
- 多项目绝对路径；
- `--json`；
- Plan/Confirm；
- 逐项目输出；
- Project-only 硬隔离；
- 传递 External Skill Source Policy；
- 传递 Trellis Username/Platform；
- 处理 `bootstrap-required`。

### P1-E4A：AGENTS 与 Workflow Doctor

```text
kpi doctor
kpi rules doctor
kpi kit doctor
```

必须显示：

- OMP Global、根 Project、OMP Project Adapter 三类路径、是否加载、Managed Digest、模板/Kit 版本；
- `@../AGENTS.md` Import、Provider Shadow、nearest-native Adapter 与 Deep AGENTS 层级；
- Plugin 是否加载；
- `environmentMode: managed|needs-onboard|degraded|blocked`；
- `runtimeMode: enforced|advisory`；
- `policyProfile: strict|relaxed` 与派生 `effectiveControlState: active|advisory|preflight-only|blocked`；
- Required Skills；
- Trellis/GitNexus/MCP 的 Tool Evidence 五个独立 facet：installation/configuration/callability/projectReadiness/freshness；
- AGENTS 与 Kit Machine Rules 的冲突；
- 建议的 Onboard 修复命令，但未经确认不执行写入。

### P1-E5：Kit/Skill/Tool 管理

```text
kpi kit list|install|doctor
kpi skills list|doctor
kpi tools check|install|doctor
kpi rules list|enable|disable|doctor
```

要求：

- SBTD Kit Version、Manifest Revision 与 Digest 可见；
- Catalog/Schema 校验；
- Bundle/External 来源可见；`SBTD Workflow Kit` 作为外部上游基线与 provenance identity 展示；
- Stable Set 与 Revision 可见；
- Tool Evidence 的 installation、configuration、callability、projectReadiness 与 freshness 全部分离。

`enable|disable` 只允许修改 Command Registry 标记为 configurable 的 Optional Rule，且必须显式指定 `session|project|user` scope；Mandatory、Always-on、安全、Evidence-truth 与 Gate-owning Rule 一律 immutable。`doctor` 输出 Rule 的 owner、effective value、scope、source 与拒绝修改原因。

### P1-E6：Provider UX

```text
kpi provider list
kpi provider doctor
kpi provider add
kpi provider login
kpi provider role
```

P1 仍委托 OMP，但提供统一 UX：

- BYOK 引导；
- Runtime OAuth/Plan 状态；
- Official CLI Delegation 状态；
- DeepSeek Compatible 配置；
- Role Mapping；
- Fallback 状态；
- Secret Reference。

`login` 只允许调用 Runtime/官方 CLI 提供的登录流程，不处理 Token。

`kpi provider login` 只启动用户控制的 Runtime/官方 CLI 登录流程并读取不敏感状态；P1 不创建外部 CLI Coding Session Adapter，也不读取、复制或存储 Token。

### P1-E7：Config

建议层级：

```text
~/.kpi/config.jsonc
<project>/.kpi/config.jsonc
environment
CLI flags
```

优先级：

```text
CLI > Project > User > Defaults
```

配置：

- Runtime；
- Runtime Mode；
- Policy Profile；
- Kit；
- Model Roles；
- Provider References；
- Rules；
- Reports；
- Lessons；
- Onboard Defaults。

### P1-E8：Session 与 Report

```text
kpi session list|show|export
kpi report latest|export
```

要求：

- 不暴露敏感 Prompt/Credential；
- JSON/Markdown；
- 报告引用真实 Artifact；
- 可从 OMP Session 重建；
- 支持 Resume Selector；
- 支持工作流摘要。

### P1-E9：发行与完成度

- npm 安装；
- macOS/Linux/Windows；
- Shell Completions（从 Command Registry 生成）；
- Upgrade/Uninstall；
- `kpi doctor --json`；
- Smoke Test；
- 安装方法 CI；
- License/NOTICE 传播。

P1 Upgrade/Uninstall 以 Provenance Inventory 为选择依据，提供 `project|user|runtime|all-managed` scope 的 dry-run Plan 和确认 Apply；只处理精确 KPi-managed target，默认保留 backup，drifted/unknown/shared/out-of-scope/failed target 必须保留为 residual。重复 completed operation 返回原终结结果；陈旧 digest 必须重做 Plan；purge 使用独立 flag 与再次确认。输出 changed、retained、backup、residuals、repair path，并要求 Reload/new Session 后才可声明 context 已移除。

## 9. P1 退出标准

- 新用户安装/运行 KPi 后，可完成显式 Plan/confirmation、Reload/new Session 与状态验证，并在 `managed` 或合规 `degraded` 环境中完成首个 SBTD Task；
- KPi 能准确修复或引导 Runtime/Plugin/Kit 缺失；
- Onboard 完整兼容当前 Python 接口；
- Provider Doctor 不误报订阅/Key 可用；
- CLI 管理命令不会被发送给 LLM；
- 所有平台安装方式有 Smoke Test；
- `v0.1` 使用文档完整。

## 10. P1 明确不做

- 将所有 OMP Provider 代码复制进 KPi；
- 移除 Python；
- Pi Runtime；
- 组织级 Evidence Store；
- 默认自动安装可选 MCP/Playwright/Maestro；
- OMP Fork。

---

# P2 — KPi Core 抽离

## 11. P2 目标

把 P0/P1 已验证的行为从 OMP 插件中抽离为 Runtime 无关 TypeScript Core，使：

- OMP 只是 Adapter；
- Workflow 状态可 Headless 测试；
- Onboard、Provider、Rule、Validation 有稳定 API；
- Pi Runtime 可在 P3 接入；
- SBTD Kit 可独立版本化。

## 12. P2 包结构

```text
apps/
  kpi-cli/                 # P1, created only when implemented
plugins/
  omp-sbtd/                # P0 OMP-hosted extension
packages/
  sbtd-workflow-kit/       # current Kit supply chain
  core/                    # P2, created only when implemented
    src/
      command-registry/    # internal Core module
      workflow-engine/     # internal Core module
      rule-engine/         # internal Core module
      policy/              # internal Core module
      validation/          # internal Core module
      context/             # internal Core module
      provider-coordination/ # internal Core module
      session/             # internal Core module
      reporting/           # internal Core module
      kit-registry/        # internal Core module
      skill-registry/      # internal Core module
      onboard/             # internal Core module
  runtime-omp/             # P2, deferred until implemented
  runtime-pi/              # P3, deferred until implemented
```

## 13. P2 交付物

### P2-E1：Core Event Contract

统一事件：

```text
session.start
session.resume
session.compacting
session.compacted
turn.start
turn.end
context.request
tool.before
tool.after
workflow.transition
rule.triggered
validation.updated
provider.changed
session.end
```

Runtime Adapter 负责翻译，Core 不使用 OMP 私有 Event 类型。

### P2-E2：Workflow Engine

- State Machine；
- Route Registry；
- SBTD Classifier；
- Book Gate Planner；
- Decision Log；
- Transition Guard；
- Headless Replay；
- `SBTDSessionStateV1` 与 Versioned State Migration；
- Runtime Mode、Policy Profile、`onboardProfileId`、Security Baseline、Environment Mode 五个持久化维度及派生 Effective Control State；
- Gate/Reviewer、Check/Validation、Capability、Tool Evidence 和 Evidence Envelope 的 namespaced state types；
- 未知版本、非法枚举和冲突兼容字段的 fail-closed repair path。

### P2-E3：Rule Engine

- Text/Tool/Result/Workflow Condition；
- Remind/Interrupt/Block；
- Repeat Policy；
- Scope/Glob；
- Rule Priority；
- Project Override；
- Compaction Persistence；
- False-positive Test Corpus。

不要求 P2 自研 OMP 等价的 Token-level TTSR；Adapter 可使用宿主能力，Core 提供语义。

### P2-E4：Policy Engine

- Path Guard；
- Command Classifier；
- Approval Gate；
- Network Policy；
- Secret Redactor；
- Install/Deploy/Migration Policy；
- Sandbox Profile；
- Audit Record。

### P2-E5：Validation Engine

- Command Discovery；
- Project-native Selection；
- RTK Policy；
- Report Artifact Guard；
- BDD Trace；
- Web/Mobile/API；
- Evidence 的 `evidenceSource`、`sourceRevision`、`environmentAlignment` 与 `evidencePublication`；
- 使用 `checkRequirement` 和 `validationStatus` 的 Final Report Schema；
- Artifact Sanitization。

### P2-E6：Context Engine

- AGENTS Hierarchy；
- Repo Map；
- Lazy Skill；
- Lessons Index/Topic；
- Trellis Artifacts；
- BDD Feature；
- Context Budget；
- Compaction Preserve Data；
- Internal URI：

```text
skill://
workflow://
rule://
trellis://
bdd://
report://
lesson://
session://
```

### P2-E7：SBTD Kit 独立发布制品

将 P0/P1 的 SBTD Kit 演进为可独立发布的版本化制品。`SBTD Workflow Kit` 仍是外部上游基线与 provenance identity；`packages/sbtd-workflow-kit/` 仍是独立内部转换目录：

```text
kpi-kit.json
catalog.json
prompts/
agents/
skills/
rules/
workflows/
schemas/
assets/
licenses/
```

要求：

- 保留源 License/NOTICE；
- Snapshot/Revision 可追踪；
- Schema 校验；
- Bundled/External 分离；
- Upstream/Stable Source Policy；
- Legacy Migration；
- Runtime Target Mapping。

### P2-E7A：三目标 AGENTS Renderer、Section Mapping 与 Conformance

实现：

- Runtime-specific Global Path Adapter；
- 根 Project Facts Renderer；
- Runtime-specific Project Adapter Renderer；
- Markdown AST Section Owner Mapping；
- `@` Import Contract；
- 三类 Managed Block Merge；
- User-owned Content Preservation；
- Source/Generated Digests；
- Semantic Drift Test；
- Template Version Migration；
- Shadow/nearest-native Contract；
- 统一 `runtime-mode`、`policy-profile`、`onboard-profile-id`、`environment-mode`、`effective-control-state` 与 `state-version` Marker Contract。

验收：

- AGENTS、Plugin/Core Gate 和 Skills 来自同一版本化 Kit；
- 文本规则变更必须伴随 Owner/机器规则/测试评估；
- 未映射 Section 阻断发布；
- 三类 Managed Block 外内容不被覆盖；
- OMP、Pi 使用各自 Global/Project Adapter，但共享根 Project Facts Contract；
- Runtime Adapter 能表达 Import/Inheritance 或提供等价 Context Bridge；
- 项目事实仍以根 Project AGENTS、深层规则和结构化项目配置为准。
- Conditional Section 只读取 `effective-control-state=active`，不能各自重新推导 Mode。

### P2-E8：Onboard TypeScript 迁移

步骤：

1. 固定 Python JSON Golden Fixtures；
2. TS 实现 Read-only `check/plan`；
3. 双跑并 Diff；
4. 迁移 Project-only；
5. 迁移 Template Operations；
6. 迁移 External Skill Transaction；
7. 迁移 Agent CLI/Tool Installer；
8. 仅在 Golden Fixture、differential、rollback 与跨平台验收通过后切换 TypeScript 为默认；
9. Python 保留到首个 P3 compatibility release，且仅作为显式 `--engine python` fallback；
10. TS 写操作失败不得自动回退 Python；移除 Python 必须由后续独立兼容性决策和迁移计划批准。

等价范围：

- Path Canonicalization；
- Multi-project；
- Catalog Validation；
- `.gitignore` BOM/幂等；
- Backup；
- Rollback；
- Legacy Identity；
- Source Fallback；
- Trellis Aggregate Exit；
- `--yes`；
- JSON Shape。

### P2-E9：Provider Coordination

接口只定义 Runtime-neutral 的声明式输入和不敏感输出：

```ts
interface ProviderProfile {}
interface SecretReference {}
interface RoleCapabilityRequirement {}
interface ProviderAvailability {}
interface FallbackPolicy {}
interface RuntimeSelectionResult {}
```

交付：

- OpenAI、Anthropic、Compatible、DeepSeek、Local/Enterprise Runtime 的 Profile、Capability、Fallback 与动态 Model Catalog 描述；
- Role Mapping 与 `RuntimeSelectionResult`；
- Secret Reference 的不透明传递；
- Runtime-owned Provider/Model 执行、认证、Credential Refresh 与 Streaming Transport；
- Subscription 登录只保留 Runtime/官方 CLI ownership；P2 不创建外部 CLI Coding Session Adapter。
### P2-E10：Knowledge P1.1 Adapter

- Decision；
- Ingest；
- Smoke；
- Revision Set；
- Artifact Manifest；
- Checksum；
- Metrics；
- Evidence State；
- 输出进入 KPi Report；
- 不提前实现云端 Evidence Publication。

### P2-E11：Compatibility Fixtures

建立跨层 Fixture：

- SBTD Classification；
- Gate Plans；
- Rule Matches；
- Tool Evidence；
- Onboard JSON；
- Validation Artifacts；
- Provider Doctor；
- Session Resume；
- Report Snapshot。

### P2-E12：冻结 Runtime Contract v1 与正式 `runtime-omp` Adapter

P2 必须冻结 Runtime Contract v1，并交付正式 `runtime-omp` Adapter，作为 P3 的不可变起点：

- Contract 覆盖 Session 生命周期、Context Injection、Command/Tool 注册、Event Subscription、Approval、Turn Abort/Continue、State Persistence、Compaction、Shutdown 与 Capability Evidence；
- Adapter 只把 OMP 公开事件/能力映射到 Core Contract，不重命名 `SBTDSessionStateV1` 字段、不扩展枚举、不持久化 `effectiveControlState`；
- P0 Plugin Host 的 Golden Fixture、migration fixture、Capability Matrix 和 Compatibility Test 必须通过；
- Contract v1 发布后，兼容性修复只能新增明确版本化的后续 Contract；P3 不得隐式改变 v1 语义。

## 14. P2 退出标准

- Core 包不依赖 OMP/Pi 私有模块；
- Runtime Contract v1 已冻结，正式 `runtime-omp` Adapter 通过 Contract、migration 与 compatibility fixture；
- Headless Replay 可重放关键 Task；
- TS Onboard 与 Python Golden Fixture 等价，Python fallback 遵守显式 `--engine python` 生命周期；
- Provider Coordination 只输出 Profile、Secret Reference、Requirement、Availability、Fallback 与 Selection Result，Provider/Secret 测试无泄露；
- SBTD Kit 可独立发布与升级；
- P0/P1 用户可无破坏迁移。

## 15. P2 明确不做

- 保证 Pi 与 OMP 全工具等价；
- 直接复制 OMP Native Core；
- 无法律审核的第三方订阅 OAuth；
- 默认多 Agent；
- 无必要 Fork。

---

# P3 — 双 Runtime 与 Fork-last

## 16. P3 目标

让同一 KPi Core 与 SBTD Kit 可运行于：

```text
runtime-omp
runtime-pi
```

用户可选择：

```bash
kpi run --runtime omp
kpi run --runtime pi
```

Runtime 差异通过 Capability Matrix 显式呈现，而不是隐藏。

## 17. P3 交付物

### P3-E1：消费冻结的 Runtime Contract v1

P3 从 P2 已发布的 Runtime Contract v1 开始接入 Pi 和双 Runtime 兼容性；不得重命名 `SBTDSessionStateV1` 字段、扩展既有枚举或持久化 `effectiveControlState`。若 P3 发现 v1 缺口，必须走明确版本化的兼容方案，而不是回写或暗改 P2 Contract。
### P3-E2：`runtime-omp` 兼容性维护

正式 `runtime-omp` Adapter 已在 P2 交付。P3 只维护它与冻结 Contract v1、`runtime-pi` 和 Compatibility Suite 的语义一致性，修复 Capability Evidence、Fixture 或兼容性问题；不把 P0 Plugin Host 的临时行为重新定义为新的 Runtime Contract。
### P3-E3：runtime-pi

实现：

- Pi Extension；
- `before_agent_start`/等价 Context Injection；
- Tool Bridge；
- Session State；
- Command/Prompt Template；
- Start Prompt Fallback；
- Capability Detection；
- Policy Wrapper；
- Validation/Report；
- 缺失 TTSR 时的 Turn-level Rule 降级；
- 加载/渲染 Pi 对应的 AGENTS/SYSTEM/Skill/Prompt 资源；
- 保持项目 AGENTS 作为项目事实层，必要时由 Runtime Adapter 转换为等价上下文。

### P3-E4：Runtime Capability Matrix

示例：

| 能力 | OMP | Pi | KPi 行为 |
|---|---|---|---|
| Slash Command | 原生 | Extension/Prompt | Adapter |
| Token-level Interrupt | TTSR | 视版本/扩展能力 | OMP 原生；Pi 降级 |
| LSP/DAP | 丰富 | 可选 | Capability Gate |
| Provider Plan/OAuth | 丰富 | 视 Runtime | Provider/Runtime Doctor |
| Session State | 原生 | 原生/扩展 | 统一序列化 |
| Approval | 原生 | KPi Policy Wrapper | 统一语义 |
| Subagents | 原生 Task | 可扩展 | Channel Bridge |
| Custom UI | 丰富 | TUI Extension | 最小公共集 |

每个 Runtime/能力组合必须输出 `capabilityStatus=native|adapter|degraded|unsupported` 和证据。`degraded` 只允许用于 Optional capability 的契约化弱路径；缺失 Required capability 必须让依赖 Route 得到 `environmentMode=blocked`，Prompt 模拟不得冒充能力等价。

### P3-E5：双 Runtime Compatibility Suite

核心场景在两 Runtime 执行：

- SBTD On；
- BDD Gate；
- Book Gates；
- Tool Block；
- Validation Report；
- Session Resume；
- Provider Unavailable；
- Onboard；
- Lessons；
- Channel Preflight。

比较：

- `runtimeMode`、`policyProfile`、`onboardProfileId`、`environmentMode` 与派生 `effectiveControlState`；
- `stageStatus` 与 Route；
- `gateState` 与 Gate-specific `reviewerStatus`；
- Tool Evidence 五个 facet；
- `checkRequirement` 与 `validationStatus`；
- Runtime `capabilityStatus`；
- Evidence Envelope 状态；
- Report Schema。

允许 UI/Tool Detail 不同，不允许语义静默不同。

### P3-E6：可选外部 CLI Runtime

在不扩大 P3 核心范围的前提下评估：

```text
runtime-codex-cli
runtime-claude-cli
runtime-kimi-cli
```

定位为 **Delegation Adapter**，不是偷取订阅凭据。每个 Adapter 必须：

- 调用官方 CLI；
- 由用户完成官方登录；
- 不解析私有 Token；
- 有版本与 Terms Gate；
- 能力不足时明确降级。

### P3-E7：Channel/Subagent Bridge

- Trellis Channel 仍是协作事实源；
- OMP Task/Subagent 与 Pi Extension Worker 通过统一 Worker Contract；
- Preflight；
- 单 Writer；
- 单 Validation Controller；
- Worktree Isolation；
- Typed Output；
- Cleanup；
- Cost/Concurrency Guard。

### P3-E8：Sandbox 与 Native 优化（可选）

仅在 Profile 数据证明需要时：

- Container/Sandbox；
- Workspace Isolation；
- Native Repo Map；
- AST Search/Edit；
- Secret Scan；
- Report Scanner。

不以追平 OMP Native Core 为目标。

### P3-E9：Evidence P2（可选独立里程碑）

评估：

- Evidence Store；
- PR Check；
- Head SHA Invalidation；
- Retention；
- Quarantine；
- Publication；
- Gate；
- Organization Policy。

该工作可独立于 Runtime 双适配推进，不应阻塞核心 v0.3。

### P3-E10：Fork Decision ADR

如果发现 OMP 缺口，必须输出：

```text
Problem
Reproduction
Why Plugin/Extension/Hook/Tool/SDK/RPC fails
Upstream proposal
Minimal patch
Merge strategy
Security/update ownership
Release cost
Exit strategy
Decision
```

Fork 仅允许：

- 关键 Hard Gate 无法实现；
- 上游扩展点不可得；
- 最小 Patch 可维护；
- 有长期 Owner；
- 有自动 Upstream Sync/Compatibility Suite。

## 18. P3 退出标准

- OMP/Pi 两 Runtime 通过语义兼容测试；
- Runtime 缺口可见、可降级；
- KPi Core 和 Kit 不依赖宿主；
- Provider/Credential 跨 Runtime 保持安全；
- Channel/Session/Report 可重建；
- Fork 结论有证据；
- 未通过 Gate 时保持无 Fork。

---

## 19. 跨阶段关键路径

```text
OMP Plugin Event Bridge
  → SBTD State
  → Classifier/Book Gates
  → Rule/Validation
  → P0 实测
  → KPi CLI
  → Config/Onboard/Provider UX
  → Core Contracts
  → TS Onboard / Provider Coordination / frozen Runtime Contract v1 / formal runtime-omp
  → Pi Adapter
  → Compatibility Suite
  → Fork Decision
```

任何阶段不得跳过前置：

- 未验证 P0，不应提前重写全部 Core；
- 未有 CLI 产品边界，不应让用户直接依赖内部插件路径；
- 未抽离 Core，不应同时维护两个 Runtime；
- 未有 Compatibility Suite，不应 Fork。

---

## 20. 质量门禁

### 20.1 每阶段必须通过

```text
Type Check
Lint
Unit Tests
Integration Tests
CLI Help/Version Smoke
Install Smoke
Secret Scan
License/NOTICE Check
Documentation Check
Compatibility Check
```

### 20.2 SBTD 专项测试

- Classification Golden Cases；
- Book Gate Predicate Cases；
- Rule False Positive/Negative；
- BDD Language；
- BDD Trace；
- RTK Report Gate；
- Report Staleness；
- E2E Mode；
- GitNexus Evidence；
- Trellis Init Boundary；
- Multi-project Aggregation；
- External Skill Rollback；
- Session Compaction；
- Provider Credential Redaction；
- Global/Root/OMP Adapter Hierarchy、Import、Shadow/nearest-native 与 `environmentMode` 判定；
- Runtime Mode × Policy Profile 四组合 Resume Conformance；
- Runtime Mode × Environment Mode 八组合 Effective Control State Conformance；
- accepted-skip scope/`onboardProfileId`/Kit-major/expiry 与 Route-change Cases；
- `securityBaseline` 与 `policyProfile` 独立的配置/Resume conformance；
- `/sbtd help` Registry/Handler/Docs Snapshot；
- Trellis Onboard-vs-Runtime Boundary；
- GitNexus Tool Evidence/Index Freshness/Compatibility Matrix；
- Tool Evidence 五 facet 独立组合 Matrix；
- Draft State Migration、冲突字段、未知版本和 repair path。

### 20.3 Release Blockers

以下任一项阻断 Release：

- Hard Gate 可被静默跳过；
- 报告陈旧仍显示 Passed；
- 非 Full-stack 被显示为 Full-stack；
- 凭据进入日志/报告/Context；
- Project-only 修改 Global State；
- External Skill Transaction 无法恢复且不报告；
- Resume 丢失 Runtime Mode、Policy Profile、Stage/Gate，或未重新观测 Environment；
- 管理命令被发送给模型；
- Runtime capability 未记录 `capabilityStatus`，或 Optional 降级被用于缺失 Required capability；
- P0 Runtime 静默删除/覆盖 AGENTS，或破坏 Managed Block 外内容；
- `.omp/AGENTS.md` 缺少/错误导入根 Project AGENTS；
- `/sbtd help` 与实际命令 Handler 漂移；
- Project-only 修改 Global AGENTS/Skills/Tools/MCP；
- GitNexus 仅凭 CLI/目录即声称 MCP 影响分析已完成；
- License/NOTICE 缺失。
- 同一环境事实可得到多个 `environmentMode`，或 `degraded` 缺少 accepted-skip provenance；
- 持久化 `enabled`、裸 `mode` 或派生 `effectiveControlState`；
- Gate/Reviewer、Check/Validation、Capability/Environment 或 Tool Evidence facets 被合并为单一状态；

---

## 21. Provider 路线

| 阶段 | Provider 目标 |
|---|---|
| P0 | 继承 Runtime；观察不敏感 Provider Profile/Role/availability/fallback；不触碰凭据 |
| P1 | 统一 `kpi provider` UX、Doctor、Secret Reference 与用户控制的官方 Login 委托；不创建外部 CLI Coding Session Adapter |
| P2 | Runtime-neutral Provider Coordination：Profile、Secret Reference、Requirement、Availability、Fallback 与 Selection Result；实际执行仍属 Runtime |
| P3 | 消费 P2 Provider Coordination；可选 Codex/Claude/Kimi CLI Delegation Adapter 仅在 Gate 通过时启用 |

合规检查持续要求：

- Codex ChatGPT 登录只由官方 CLI/Runtime 管理；
- Claude Subscription 不内嵌第三方 OAuth，不代理订阅凭据；
- Kimi 使用官方 CLI 或官方提供的 API Key；
- DeepSeek 使用官方兼容 API；
- Model Catalog 动态，不硬编码已弃用模型；
- 凭据永不进入项目、报告和 LLM Context。

---

## 22. Onboard 演进路线

| 阶段 | 实现 |
|---|---|
| P0-A | TypeScript `OnboardService` + schema-v2 OMP Distribution Projection；Global 写 `$PI_CODING_AGENT_DIR/AGENTS.md`，项目写根 `AGENTS.md` 与 `.omp/AGENTS.md` |
| P0-B | 建立三目标 Section Mapping、Generated Templates、Managed Blocks 和 Sync Report |
| P1 | `kpi onboard` 在已验证的 TypeScript 契约上增加 CLI UX、确认、输出、路径发现、Import/Shadow Doctor |
| P2-A | 仅在批准的多 Runtime 需求出现后，抽取 Runtime-neutral Onboard contract；不得复活 Python bridge 作为默认或 fallback |
| P2-B | Project-only、Root/Adapter Template Operations |
| P2-C | External Skill Transaction/Stable Fallback |
| P2-D | 经批准的 Agent CLI/Tool Installers |
| P2-E | Golden Fixture、differential、rollback 与跨 Runtime 验收通过后才扩展共享实现 |
| P3 | Pi 使用自己的 Runtime-specific Project Adapter；任何额外 Python compatibility 路径需要独立兼容性决策 |

迁移必须保持：

- Catalog Schema、Multi-project、`--yes`、Project-only；
- Backup、Rollback、Legacy Identity、Stable Digest/License；
- Trellis Exit Code、JSON Contract、`.gitignore` BOM/幂等；
- OMP Global `PI_CODING_AGENT_DIR` 路径；
- 根 `<project-root>/AGENTS.md`；
- `<project-root>/.omp/AGENTS.md` 与 `@../AGENTS.md`；
- 三类 Managed Block 和块外内容保留；
- 旧 `--skip-project-agents` 的弃用映射；
- Section Mapping、三个 Generated Digests 和 Unmapped Release Gate；
- `/sbtd on/off` 的 `runtimeMode`、`/sbtd strict/relaxed` 的 `policyProfile`、所选 `onboardProfileId`、Preflight 的 `environmentMode` 与派生 `effectiveControlState`；
- `/sbtd help` Registry Contract；
- Trellis Onboard 初始化例外；
- MCP 用户级 Scope；
- Project-only Global State 隔离。
- `stateVersion`、namespaced state fields、兼容迁移和 fail-closed repair path。

## 23. 兼容性与升级策略

### 23.1 OMP

- Pin 支持区间；
- CI 测试最低/推荐/最新兼容版；
- Plugin API Feature Detection；
- 升级前 Compatibility Suite；
- 不自动修改用户 OMP 配置；
- Breaking Change 先提示和迁移。

### 23.2 SBTD Workflow Kit

- Kit 记录 sourceId、canonical source URI、resolved full SHA、可选显示其来源 Tag 与 Digest；
- 用户消费路径只允许固定 SHA 的 Vendored Snapshot 或不可变 Kit Manifest；禁止 Floating Main；
- Catalog/Schema 版本迁移；
- Bundled/External Skill Diff；
- License/NOTICE 校验；
- Runtime Gate Contract 变更需要 Changelog。

### 23.3 Pi

- P3 以前不作为生产默认；
- Adapter 只使用公开 API；
- 启动 Context 注入存在 Fallback；
- 缺少 Token-level Rule 时明确能力降级；
- 不为追求形式一致而绕过 Pi 安全边界。

---

## 24. 里程碑交付清单

### P0

- [ ] OMP Plugin Skeleton
- [ ] Zero-mutation Plugin Install
- [ ] Pinned Read-only SBTD Kit
- [ ] `/sbtd` Commands
- [ ] Command Registry + `/sbtd help [command]`
- [ ] `/sbtd onboard` Commands/Setup Wizard
- [ ] Canonical Session State v1 + State Conformance
- [ ] Classifier/Routes
- [ ] Book Gate Plan
- [ ] Kit Loader
- [ ] OMP Native Global Path Resolver
- [ ] Root Project Facts Contract
- [ ] OMP Project Adapter + `@../AGENTS.md`
- [ ] Mode-aware AGENTS（Effective Control State）
- [ ] Managed Block Merge/Preservation
- [ ] Shadow Detection
- [ ] Upstream AGENTS 三目标 Section Mapping（P0-B）
- [ ] AGENTS Sync Report/Release Gate
- [ ] Rules/Policy
- [ ] Validation/Report
- [ ] OMP-native TypeScript Onboard Service
- [ ] Onboard/Runtime Tool Lifecycle
- [ ] Provider Delegation
- [ ] P0 Test Matrix
- [ ] P0 User Guide

### P1

- [ ] `kpi` CLI
- [ ] Default SBTD On
- [ ] Runtime Bootstrap
- [ ] `kpi onboard`
- [ ] AGENTS/Workflow Doctor
- [ ] Kit/Skill/Tool/Rule Doctor
- [ ] Provider UX
- [ ] Config Layering
- [ ] Session/Report Export
- [ ] Completion
- [ ] Cross-platform Install Tests
- [ ] v0.1 Documentation

### P2

- [ ] Core Event Contract
- [ ] Workflow Engine
- [ ] Versioned State Migration/Repair
- [ ] Rule Engine
- [ ] Policy Engine
- [ ] Validation Engine
- [ ] Context Engine
- [ ] SBTD Kit 独立发布制品
- [ ] AGENTS Renderer/Conformance
- [ ] TS Onboard
- [ ] Provider Coordination
- [ ] Knowledge P1.1 Adapter
- [ ] Runtime Contract v1 + formal `runtime-omp` Adapter
- [ ] Migration Guide

### P3

- [ ] Frozen Runtime Contract v1 Compatibility Fixtures
- [ ] Runtime Pi
- [ ] Capability Status Matrix
- [ ] Compatibility Suite
- [ ] CLI Delegation Feasibility
- [ ] Channel/Subagent Bridge
- [ ] Sandbox/Native Profiling
- [ ] Evidence P2 Decision
- [ ] Fork ADR
- [ ] v0.3 Migration/Release Guide

---

## 25. Definition of Done

一个阶段只有在以下条件全部满足时才算完成：

1. 功能代码、Schema、文档和测试同步；
2. 所有用户可见行为均有持久 BDD；`checkRequirement=not-applicable` 只用于客观 predicate 证明为内部、非用户可见的检查，不能替代行为 BDD 或完成路径；
3. Required Book Gates 的 `gateState=passed` 且 reviewer status 达到对应通过值；
4. 项目原生验证已执行并记录 `validationStatus`；
5. 正式报告满足 Artifact Gate；
6. `validationStatus=failed|skipped|blocked`、`onboardProjectStatus` 和剩余风险按字段列出；
7. Provider/Credential 无泄露；
8. 安装、升级、回滚路径可验证；
9. License/NOTICE 完整；
10. 下一阶段依赖已形成稳定 Contract。

---

## 26. 最终路线结论

```text
P0-A：固定 OMP Global、根 Project Facts、OMP Project Adapter 和 Mode-aware Contract
P0-B：建立上游 AGENTS 三目标 Section Mapping、生成模板、Managed Blocks 与同步流水线
P1：用 KPi CLI 建立独立产品入口
P2：抽离 Runtime 无关 KPi Core
P3：支持 OMP/Pi 双 Runtime
Fork：仅在插件、SDK、RPC 均无法实现关键门禁时进行
```

该路线优先验证 SBTD 的真实价值，同时避免过早承担 OMP Fork、Provider 重造、Native Tool 和双 Runtime 的维护成本。
