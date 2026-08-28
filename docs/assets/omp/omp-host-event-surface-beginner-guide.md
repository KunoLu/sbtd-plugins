# OMP Host Event Surface Profile 小白操作指南

## 1. 这项验证到底在证明什么

`Host Event Surface Profile` 不是检查“代码里有没有 `pi.on(...)`”，也不是让人手工伪造事件。它要证明：

1. 指定的真实 OMP Runtime 会在真实操作发生时发出约定事件。
2. 事件 payload 和顺序符合 Plugin 依赖的合同。
3. 精确候选 Plugin tarball 收到事件后会正确阻断、授权、消费和隔离状态。
4. 证据来自受信任 CI，且绑定精确 Plugin tarball 和精确 OMP artifact。

一句话理解：**用自动化脚本像用户一样操作真实 OMP，同时由只读观察器记录 OMP 实际发出的事件，再检查 Plugin 的响应是否正确。**

## 2. 你需要提供什么

产品或发布负责人不需要手工构造 12 个事件，也不需要提供真实 Provider token。

已确认：

1. target、ledger 和派生 support matrix 只通过受控 bot PR 写回，CI/bot 不直写
   `main`，也不绕过 branch protection。
2. 去敏后的 content-addressed bundle 写入
   `plugins/omp-sbtd/validation/p0/evidence/`，并与首次引用它的 assessment 同 PR。
3. Pre-publication candidate PR 只含 evidence + candidate assessment；
   post-publication admission PR 才含 Registry proof + published target + 公开矩阵。
4. GitHub Actions artifact 只作临时传输/诊断，不是长期唯一副本。
5. 新 target、re-certification 和 revocation bot PR 均要求 required checks 通过，并由 1 名 release owner/maintainer 批准。
6. Bot PR 的固定 required status 只由独立 Status GitHub App 签发；validator
   `GITHUB_TOKEN` 只读，branch protection 将 expected source 固定到该 App。

仍需平台或发布负责人按顺序配置：

1. 创建只能签发 attestation、不能创建 PR、不能 direct-push 的 protected
   compatibility certification environment/job。独立 PR-creation job 只用
   job-scoped `GITHUB_TOKEN` 开 bot PR。
2. 创建 Status GitHub App，只安装到 `KunoLu/KPi`，只授予 Metadata read 和
   Commit statuses read/write。生成 private key 后不得提交、打印或放入 artifact。
3. 创建独立 `omp-compatibility-ledger-status` environment：deployment branch
   只允许 `main`、不允许 tag、关闭 administrator bypass，并绑定 1 名 release
   owner/maintainer reviewer。App private key 只放在该 environment secret。
4. Workflow 内所有第三方 actions 固定完整 commit SHA；bot credential 保持非管理员、
   无 branch-protection bypass。
5. Validator workflow 合入 `main` 后，由 release owner 从 `main` 手工
   `workflow_dispatch`，输入 PR number、expected head SHA 和 certification run ID。
   先完成一次 test-only Status App dry run。
6. App 已实际产生固定 context 后，再把
   `omp-compatibility-ledger-validate` 加入 `main` required status，并把 expected
   source 固定到 Status App；同名 GitHub Actions app status 不得被接受。
7. 在 branch protection/environment 中绑定实际 reviewer；不把个人用户名硬编码进
   仓库。environment approval 与随后 PR approval 是两个独立审计动作。
8. 本任务不修改全仓 `allowed_actions=all`、SHA enforcement 或
   `enforce_admins=false`；这些保留为明确 residual risk。

工程实现负责自动触发事件、收集证据和执行断言。真实账号、真实 Provider token、原始 transcript 和 PII 都不应进入测试证据。

## 3. 当前仓库已经有什么

截至本方案评审基线：

- 本地 OMP Runtime 为 `17.3.5`。
- Plugin 已注册计划认证的 Host events。
- OMP 17.3.5 的公开 extension API 定义了这些事件。
- 现有 `authorized-omp-rpc-harness.ts` 能驱动真实 OMP RPC、接收 `turn_start`、`turn_end` 和 `host_tool_call` 等 Host RPC frame。
- 现有 `verifyRuntime()` 只核对 `omp --version` 文本。
- GitHub Actions 已启用，但当前允许所有 actions，未强制 action SHA pin。
- `main` 已要求 1 个 approval，但没有 required status checks，且管理员可绕过。
- 当前没有 GitHub environment 或专用 Status GitHub App。

仍然缺少：

- 证明实际加载的 OMP package artifact digest。
- 从真实 Host 操作稳定触发全部 required extension events 的 driver。
- 记录 extension event schema、顺序和 Plugin 响应的只读观察器。
- 受信任 CI attestation 和受保护 ledger 写入链路。

注意：Host RPC frame 与 `pi.on(...)` extension event 不是同一层。现有 harness 看到了 `turn_start` frame，不等于已经证明 Plugin 收到了 `turn_start` extension event。

## 4. 最终自动化由哪几部分组成

```text
Scenario Driver
  像用户一样启动 OMP、发消息、切 Session、分支、压缩和处理 approval
        |
        v
真实 OMP Host + 精确 OMP Registry artifact
        |
        +--> 精确候选 Plugin tarball：执行真实策略
        |
        +--> 只读 Event Observer：只记录事件名称、schema 结论和顺序摘要
        |
        v
Evidence Validator
  检查 12 个 required events、Plugin 行为、Session 隔离和 artifact identity
        |
        v
受信任 CI Attestation
  绑定 source revision、workflow、run、Plugin/OMP/evidence digests
```

### 4.1 Scenario Driver

负责操作真实 OMP。它不能直接调用 Plugin handler，也不能直接 `emit` 一个伪造事件来冒充 Host 证据。

### 4.2 Event Observer

作为测试 companion extension 与候选 Plugin 一起加载。它只调用公开 `pi.on(...)` 订阅事件，不返回策略结果，不改变 Plugin 状态，不加入发布 tarball。

它只保存：

- event name
- schema 是否有效
- 非敏感 reason code
- Session/turn/toolCall 的不可逆 digest
- 顺序摘要
- pass/fail 结论

它不能保存：

- 用户 prompt 或原始 transcript
- 模型原始输出
- tool input/output 原文
- token、cookie、credential
- 本机路径、用户名或其他 PII

### 4.3 Evidence Validator

负责把“事件出现了”提升为“合同成立”：检查 payload、顺序、关联关系、Plugin 响应、隔离性和目标 artifact identity。

## 5. Gate 0.2 的实际执行步骤

### 步骤 1：冻结本次测试对象

1. 构建一次候选 Plugin tarball。
2. 计算 package integrity（SRI）、tarball SHA-256、manifest SHA-256。
3. 从 tarball 内 manifest 读取 peer range。
4. 把上述值写入只读 candidate target envelope。
5. 后续所有 profile 必须使用同一组 bytes；任何重新打包都产生新 identity，旧结果不能复用。

Gate 0.2 feasibility spike 可以使用不发布的实验 tarball，但仍必须固定 digest，防止测试中途换包。

### 步骤 2：创建一次性 Host 环境

1. 创建临时 HOME 和临时 project directory。
2. 从 Registry 安装一个精确 OMP version；不使用 workspace dev dependency。
3. 安装步骤 1 的精确 Plugin tarball。
4. 加载只读 Event Observer。
5. 禁用真实外部 Provider credential，使用确定性本地 provider/model adapter。
6. Host 启动后读取实际加载的 OMP package version 和 artifact digest，并与目标 Registry artifact 比较。
7. version 或 digest 不一致时立即停止，结果为 `failed`。

### 步骤 3：先做最小连通性验证

1. 启动真实 OMP Host。
2. 等待 `session_start`。
3. 执行一个不会调用工具的确定性 prompt。
4. 等待 `before_agent_start -> turn_start -> turn_end`。
5. 正常停止本次 agent Session，等待 `session_stop`。

如果这条最短链路不能稳定重复，先修 Host driver/adapter；不要继续做完整认证。

### 步骤 4：逐项触发 12 个 required events

下表的“用户动作”描述产品语义，不预设尚未验证的 CLI/RPC 命令。Gate 0.2 spike 必须为每项找到稳定的公开 Host 驱动入口；找不到时标记 `blocked`，不能改用直接调用 handler。

| Required event | 自动化模拟的用户动作 | 必须检查的核心证据 |
|---|---|---|
| `session_start` | 启动一个新的真实 OMP Session | 只出现于目标 Session；Context 可用 |
| `session_switch` | 新建、恢复或切换 Session | `reason` 合法；previous/current Session 不混淆 |
| `session_branch` | 从当前 Session 创建 branch/fork | previous Session 信息有效；新分支状态隔离 |
| `session_tree` | 在 Session tree 中切换活动节点 | old/new leaf 关系有效；状态按新节点重建 |
| `before_agent_start` | 提交确定性 prompt | 发生在 turn/tool 之前；payload schema 有效 |
| `session.compacting` | 通过 Host 的显式 compact 入口触发压缩 | 绑定当前 Session；压缩后敏感状态不泄漏 |
| `tool_call` | 让确定性 model 请求一个受控测试 tool | tool name/id/input schema 有效；Plugin 能阻断 |
| `tool_approval_resolved` | 对需要 approval 的受控 tool 选择允许或拒绝 | 与 Session、turn、toolCallId、risk class、target 精确绑定 |
| `tool_result` | 让已允许的受控 tool 完成或返回受控错误 | 与同一 toolCallId 绑定；approval 只消费一次 |
| `turn_start` | 开始处理一条用户消息 | turn index 合法；位于 agent start 之后 |
| `turn_end` | 完成同一轮响应 | 与 turn start 成对；包含受控 tool result 摘要 |
| `session_stop` | 正常完成或受控停止 agent Session | 状态完成收口；不能用仅关闭 Host 的 `session_shutdown` 替代 |

### 步骤 5：运行正常路径

至少运行以下正常场景：

1. 无 tool 的单轮对话。
2. 允许一个低风险受控 tool。
3. 拒绝一个需要 approval 的受控 tool。
4. 同一 Session 的下一 turn 不能复用上一次 approval。
5. 创建新 Session，旧 Session 状态不能泄漏。
6. branch/tree 后状态按新上下文重建。
7. compaction 后仍保持安全边界，但不保留可复用 approval。
8. 正常停止 Session。

### 步骤 6：运行反例和隔离路径

至少故意制造以下错误，确认 fail closed：

1. event payload 缺字段或字段类型错误。
2. 未知 event name。
3. `tool_result` 使用错误的 `toolCallId`。
4. approval 来自另一个 Session 或 turn。
5. approval 的 risk class 或 target fingerprint 不匹配。
6. 同一 approval 被消费两次。
7. `tool_result` 早于对应 `tool_call`。
8. Session switch/branch/compaction 后尝试复用旧状态。
9. 实际加载的 OMP version 或 digest 与目标不一致。
10. observer 或 event subscription 抛错。

反例测试必须证明 Plugin 没有把 malformed event 当成“已批准”或“已完成”。

### 步骤 7：校验事件顺序

每个场景定义允许的偏序，而不是依赖无意义的全局时间戳。例如一个含 tool 的正常 turn 至少满足：

```text
before_agent_start
  < turn_start
  < tool_call
  < tool_approval_resolved（仅需要 approval 时）
  < tool_result
  < turn_end
```

Session 变更场景必须额外证明变更前后的 Session identity 不混用。没有合同要求的独立事件不要强行规定唯一总顺序，避免测试绑定 Host 内部实现细节。

### 步骤 8：生成最小证据

每个 scenario 输出一个去敏摘要，例如：

```json
{
  "schemaVersion": 1,
  "profile": "omp-host-events-v1",
  "scenarioId": "approval-denied-is-session-bound",
  "pluginTarballSha256": "<sha256>",
  "ompVersion": "17.3.5",
  "ompArtifactSha256": "<sha256>",
  "requiredEventsObserved": [
    "before_agent_start",
    "turn_start",
    "tool_call",
    "tool_approval_resolved",
    "tool_result",
    "turn_end"
  ],
  "schemaValid": true,
  "orderingValid": true,
  "isolationValid": true,
  "outcome": "passed"
}
```

真实 schema 还要记录 evidence digest、scenario digest、reason code 和 attestation subject，但不能写原始 prompt/tool 文本。

### 步骤 9：在 Runtime matrix 上重跑

对候选 tarball运行：

1. `minimum = 17.3.5`
2. `latest-in-range = Registry 当前最新稳定 17.x`

如果两者相同，只运行一次。每个不同 Runtime 都使用全新临时环境并重新证明实际加载 artifact identity。

### 步骤 10：由受信任 CI 签发

只有 allowlist 中的 repository、workflow identity、protected source ref 和 event 可以签发认证 evidence。CI attestation 必须绑定：

- run 和 source revision
- candidate target envelope
- Plugin tarball/manifest digests
- OMP exact version/artifact digest
- Host Event evidence digest

本地运行只叫 `local-observation`，可用于排障，但不能写公开 ledger，也不能把状态派生为 `certified`。

### 步骤 11：用独立 Status App 验证 bot PR

PR-creation job 用 job-scoped `GITHUB_TOKEN` 创建 test-only bot PR。Release owner
从受信 `main` 手工启动 validator；validator 的 `GITHUB_TOKEN` 只有
`contents: read` 和 `pull-requests: read`，PR diff/files 只作为不受信数据解析，
不 checkout 或执行 PR head。

Status App credential 只在 `omp-compatibility-ledger-status` environment 的
status steps 中使用。先对已核对的 immutable PR head SHA 写固定 context
`pending`；验证 attestation、允许路径、append-only diff 和 candidate/admission
边界后，重读当前 head，只有 SHA 未变才写 `success`，否则写 `failure` 或保留
`pending` 阻断。

真实 dry run 必须证明：

- PR/其他 ref 上的改写 workflow 无法取得 App credential。
- GitHub Actions app 写同名 context 不能满足 expected-source required status。
- 错误/过期 SHA 不成功；更新 head 后旧 SHA status 失效。
- App token 签发失败、validator 异常、`failure`、`pending` 或 missing 均阻断合并。
- App private key/token 不进入 parser 子进程、log、artifact、evidence。
- key rotation/revocation 后旧 key 失效；App 不可用时不能 fail open。

## 6. Gate 0.2 怎样才算通过

Gate 0.2 只证明“完整认证路径可实现”，spike 本身不发布包、不拓宽 peer。它不是 npm publication Gate；`blocked` 只阻止 Host Event `passed`、公开 `certified` 和受信矩阵更新，不阻止满足四命令合同的 RC 另行申请发布。

必须同时满足：

- [ ] 12 个 required events 都能由真实 Host 操作稳定触发。
- [ ] 每个事件的 payload 和必要偏序可以验证。
- [ ] tool block、approval、result 和 one-shot consumption 可以验证。
- [ ] Session、turn、branch、tree、compaction 隔离可以验证。
- [ ] 实际 OMP artifact identity 可以由 Host 证明。
- [ ] observer 不改变 Plugin 行为，也不进入发布 tarball。
- [ ] 去敏 evidence/attestation bundle 写入仓库 content-addressed path，并与首次引用它的 assessment 同 bot PR；CI artifact 不是长期唯一副本。
- [ ] Candidate PR 不更新 published target/公开矩阵；post-publication admission PR 才追加 Registry proof、published target 和派生矩阵。
- [ ] CI/bot 不能直写 `main` 或绕过 branch protection；所有写回经过 required checks/review。
- [ ] 新 target、re-certification 和 revocation PR 均有 required checks 和 1 名 release owner/maintainer 审批。
- [ ] 错误 Runtime、malformed event、subject mismatch 和非受信 workflow 都会 fail closed。
- [ ] 固定 required status 由独立 Status GitHub App 签发，branch protection expected source 不接受 GitHub Actions app 同名 status。
- [ ] App 仅有 Metadata read + Commit statuses read/write；credential 只在 main-only protected environment 的 status steps 中可用。
- [ ] 真实 bot PR 证明 stale-head、head update、failure/pending/missing、key rotation/revocation 和非 main ref 均 fail closed。

任一 required event 只能靠直接调用 handler、伪造 `emit` 或不稳定 UI 操作触发时，Gate 状态为 `blocked`。正确处理是增加受控 Host adapter，或推动 OMP 提供稳定 extension contract fixture/version；不能把 required event 改成 optional。

## 7. 哪些做法不能算通过

以下结果都不能叫 Host Event Surface `passed`：

- 单元测试直接调用 Plugin handler。
- 只检查 `typeof pi.on === "function"`。
- 只看到 Host RPC frame，没有证明 extension event。
- 只运行四条 `/sbtd` 命令。
- 只比较调用者传入的 Runtime version 字符串。
- 使用 workspace Plugin 源码代替冻结 tarball。
- 使用 workspace OMP dependency 代替精确 Registry artifact。
- 手工点击一次成功，但没有可重复 driver 和证据。
- 使用本地或 fork/PR workflow 结果生成公开 `certified`。
- 证据包含原始 transcript、token、credential 或 PII。
- 由 GitHub Actions app 从任意 ref 写同名 status，或只靠 workflow 内 `github.ref == main` 判断来源。
- 把 Status App private key/token 传给 PR parser、子进程、缓存、日志、artifact 或 evidence。

## 8. 推荐先做的最小 feasibility spike

不要一开始实现完整 ledger。按以下顺序最省返工：

1. 在临时目录加载精确 OMP 17.3.5、实验 tarball和只读 observer。
2. 证明 `session_start`。
3. 通过确定性 adapter 证明 `before_agent_start -> turn_start -> turn_end -> session_stop`。
4. 证明一个受控 tool 的 `tool_call -> approval -> tool_result`，并验证阻断和拒绝路径。
5. 证明 `session_switch` 后 approval 不可复用。
6. 分别寻找 branch、tree 和 explicit compaction 的稳定 Host 驱动入口。
7. 证明实际加载的 OMP artifact digest，不只读取 `omp --version`。
8. 在 GitHub Actions 中完成一次不写 ledger 的 attestation dry run。
9. 创建最小权限 Status App 和 main-only status environment；用 test-only bot PR
   证明固定 context、immutable head、expected App source 和 fail-closed 行为。

第 1–5 步失败说明基本 Host driver 不成立；第 6 步任一 required event 无稳定入口说明需要 Host adapter；第 7–9 步失败说明认证只能是本地 observation，不能进入公开 ledger。

## 9. 与完整解耦计划的关系

本指南只展开 `docs/assets/omp/omp-plugin-compatibility-decoupling-plan.md` 的 Gate 0.2 和 Host Event Surface，不替代该计划中的：

- release-authority contract
- Runtime Capability Profile
- Command Surface Profile
- target catalog / candidate envelope
- compatibility ledger / trust policy
- minimum/latest-in-range matrix
- publication 和 rollback gate

完成本指南的 feasibility spike 后，才能判断 widened-peer target 的完整兼容认证是否可执行；RC publication 仍由独立四命令合同决定。
