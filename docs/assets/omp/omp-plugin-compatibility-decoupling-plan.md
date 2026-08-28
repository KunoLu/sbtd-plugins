# OMP Plugin 与 OMP Runtime 版本解耦方案

## 1. 文档状态

- 状态：Proposed
- 目标 Plugin：`@kunolu/omp-sbtd`
- 评审基线（2026-08-20）：`@kunolu/omp-sbtd@0.1.0-rc.12`，npm Registry `next` 指向该精确版本
- 评审基线依赖：peer 和 dev dependency 均精确为 OMP Runtime `17.3.5`
- 当前计划中的最低 OMP Runtime：`17.3.5`
- 已确认 peer 策略：限定当前 major，使用 `>=17.3.5 <18`
- 已确认发布合同（2026-08-24）：所有 RC 均以精确候选 tarball 的隔离四命令验收为唯一 publication compatibility Gate；三个 profile 只派生认证状态
- 已确认 evidence 保存（2026-08-24）：去敏后的 content-addressed bundle 随首次引用它的 assessment 受控 bot PR 入库；candidate PR 与 post-publication admission PR 严格分离
- 已确认 bot PR 审批（2026-08-24）：新 target、re-certification 和 revocation 均须 required checks 通过并由 1 名 release owner/maintainer 批准；具体 GitHub identity 不硬编码
- 已确认 GitHub hardening scope（2026-08-24）：只新增本任务的 certification/status protected environments、最小权限 Status GitHub App、required status、非管理员 bot 和 workflow 内第三方 action commit-SHA pin；不改全仓 allowed-actions/SHA-enforcement/admin-enforcement
- 已确认 bot validator（2026-08-24）：job-scoped `GITHUB_TOKEN` 只创建 PR；release owner 从受信 `main` 手工 `workflow_dispatch` validator；固定 status 只由独立 Status GitHub App 签发，branch protection 将 expected source 固定到该 App
- 已发布 rc.12 保持不可变；实施 widened peer 必须产生新的 Plugin candidate/version
- 非目标：本方案不发布 npm 包、不修改 Registry tag，也不把未经验证的 OMP 版本声明为 `certified`

## 2. 背景与问题

当前 Plugin 发布路径把多个不同概念绑定成一个精确版本：

```text
Plugin peer dependency
= Plugin dev dependency
= pnpm lock 安装版本
= compatibility manifest 当前版本
= host acceptance 目标版本
= README 公开支持版本
```

这导致每次 OMP Runtime 更新都需要同步修改 peer、lock、manifest、BDD、测试和文档，然后重新发布一个 Plugin 版本。

仅把 peer dependency 改成宽范围不能安全解决问题。OMP 的 `17.2.9` 和 `17.3.5` changelog 都包含 `Breaking Changes`，说明 patch/minor 更新也可能改变 Plugin 依赖的宿主行为。正确目标不是取消兼容验证，而是取消“新 OMP 版本必须对应新 Plugin tarball”的发布耦合。

目标流程为：

```text
OMP 发布新版本
→ 对既有 Plugin tarball 自动运行兼容认证
→ 通过时只更新兼容 ledger
→ 未通过时按唯一派生规则记录 `eligible`、`partially-verified` 或 `incompatible`
→ 只有 Plugin 代码需要修复时才发布新 Plugin
```

## 3. 核心决策

### 3.1 版本范围只负责安装资格

Plugin manifest 使用：

```json
{
  "peerDependencies": {
    "@oh-my-pi/pi-coding-agent": ">=17.3.5 <18"
  },
  "devDependencies": {
    "@oh-my-pi/pi-coding-agent": "17.3.5"
  }
}
```

含义：

- `peerDependencies` 定义可以尝试安装 Plugin 的 OMP 版本窗口。
- `devDependencies` 和 `pnpm-lock.yaml` 继续固定一个精确最低版本，保证构建和类型检查可复现。
- 后续 OMP 17.x 更新通过隔离 CI matrix 验证，不修改仓库 dev pin。
- OMP 18 默认不在安装范围内；扩展到新 major 需要单独评审和一次 Plugin 发布。
- 每个历史认证 identity 使用该精确 tarball 内、由 manifest digest 绑定的 peer range；后续 policy 变化不得重新解释历史 `out-of-range`。

禁止使用：

- `*`
- `latest`
- 无上限的 `>=17.3.5`
- 只依赖 `^17.3.5` 而没有 Host Contract 和真实宿主集成测试

### 3.2 安装、证据标签与公开状态分离

公开 overall state 只能按固定优先级唯一派生：

| 状态 | 定义 |
|---|---|
| `out-of-range` | OMP 版本不满足该精确 Plugin tarball 内、由 manifest digest 绑定的 peer range；优先级最高 |
| `revoked` | 受信任的 append-only revocation 已撤销该精确认证 identity |
| `incompatible` | 任一已执行的必需 profile 明确失败 |
| `certified` | 三个必需 profile 全部通过，且受信任 CI attestation 验证成功 |
| `partially-verified` | 有效受信任 assessment 中至少一个 profile 通过，但其余 profile missing/blocked，或任一 profile evidence trust missing/invalid |
| `eligible` | 精确 OMP 版本位于 peer range 内，但没有 profile 已通过 |

派生顺序固定为：

```text
out-of-range
> revoked
> incompatible
> certified
> partially-verified
> eligible
```

`contract-compatible` 只表示 Runtime capability probe 通过；
`local-observation` 只表示证据不是由受信任 CI 签发。两者都是证据标签，
不是并列 overall state。一个版本位于 peer range 内，也不等于已经公开认证。

### 3.3 认证身份绑定精确二元组

每项兼容结论必须绑定：

```text
Plugin tarball SHA-256 + OMP exact version
```

因此第一个采用 widened peer 的 Plugin tarball 可以独立取得：

```text
Plugin <first-widened-peer-version> + OMP 17.3.5 → certified
Plugin <same-tarball> + OMP 17.3.6 → certified
Plugin <same-tarball> + OMP 17.4.0 → certified
```

后两项只更新兼容证据，不产生新的 Plugin version 或 tarball。当前已发布
rc.12 的 peer 精确为 `17.3.5`，不能作为跨版本复用示例，也不能原位拓宽。

### 3.4 Publication 与认证状态独立

所有 RC（普通 exact-peer、peer widening 和未来新 major）继续采用现行合同：
精确候选 tarball 的隔离四命令验收是唯一 publication compatibility Gate。
`eligible`、`partially-verified`、`incompatible`、`certified` 或 Host/CI
infrastructure 状态不参与 npm 发布授权。发布仍需负责人另行明确授权；发布后
公开 support matrix 必须显示实际派生状态，没有受信 profile pass 时从
`eligible` 开始，不得因 published、installable、peer range 或 dist-tag 推断为
`certified`。

## 4. Compatibility Policy v2

当前 `plugins/omp-sbtd/validation/p0/compatibility.v1.json` 只表达一个 `currentRuntimeVersion`，无法表达版本范围和独立认证。

建议 clean cutover 到：

```text
plugins/omp-sbtd/validation/p0/compatibility.v2.json
```

建议 schema：

```json
{
  "schemaVersion": 2,
  "pluginPackage": "@kunolu/omp-sbtd",
  "peerRange": ">=17.3.5 <18",
  "minimumRuntimeVersion": "17.3.5",
  "contractProfile": "omp-extension-v1",
  "requiredEvidenceProfiles": [
    "omp-runtime-capabilities-v1",
    "omp-command-surface-v1",
    "omp-host-events-v1"
  ],
  "commands": [
    "help",
    "status",
    "report",
    "onboard plan"
  ]
}
```

不得把以下动态事实写入随 Plugin 发布的 policy：

- `currentRuntimeVersion`
- `latestRuntimeVersion`
- 动态 `testedVersions` 列表

否则每次 OMP 更新仍会改变 Plugin 源码或 tarball。

### 4.1 仓库侧认证目标目录

随 Plugin 发布的 Compatibility Policy 不选择“当前要认证哪个已发布 tarball”。
仓库侧新增、默认不进入 npm package `files` 白名单的目标目录：

```text
plugins/omp-sbtd/validation/p0/compatibility-targets.v1.json
```

每个 target entry 必须绑定不可变身份：

```json
{
  "pluginVersion": "0.1.0-rc.12",
  "pluginTarballSha256": "<sha256>",
  "packageIntegrity": "<SRI computed from tarball bytes>",
  "pluginManifestSha256": "<sha256>",
  "pluginPeerRange": "17.3.5"
}
```

规则：

- `packageIntegrity` 是从精确 tarball bytes 计算的 SRI；候选发布前即可确定，发布后 Registry `dist.integrity` 必须与其完全相等。
- `pluginManifestSha256` 绑定从该精确 tarball 中提取的 `package.json` bytes；validator 必须证明其中 peer range 等于 entry 的 `pluginPeerRange`。
- target entry 只能追加；同一 version 或 tarball digest 出现冲突 identity 时 fail closed，不得原位改写。
- 发布 tag 只能作为一次性发现入口。本次迁移可用 `next` 定位 rc.12，但必须立即解析并固定 exact version、tarball SHA-256、package integrity 和 manifest identity。
- 预发布认证使用同一 schema 的不可变 candidate target envelope，但不把未发布对象写成 published catalog target；发布后先核对 Registry exact version/integrity，再追加对应 target entry。
- 定时/重跑认证只读取已固定的 published target identity，不重新解析 `next`、`latest` 或“最大 SemVer”；tag 后续移动不得改变认证对象。
- 未来 widened-peer tarball 通过新增 published target entry 进入后续矩阵。当前 Compatibility Policy 不得覆盖历史 target 的 `pluginPeerRange`。

## 5. Host Contract

### 5.1 `omp-extension-v1` 能力清单

`plugins/omp-sbtd/src/runtime/index.ts` 保持唯一 Host seam，不新增平行宿主注册框架。
以下表是 `omp-extension-v1` 的规范输入；capability probe 和 Host Event Surface
都必须引用同一版本化清单，禁止各自推断 required/optional。

| Capability | 等级 | 探测方式 | 缺失 reason code | 缺失时行为 |
|---|---|---|---|---|
| `ExtensionAPI.registerCommand` | required | `typeof === "function"` 并注册 `/sbtd` | `HOST_REGISTER_COMMAND_MISSING` | `unsupported`，Plugin 不加载 |
| `ExtensionAPI.on` | required | `typeof === "function"`，逐项订阅必需事件 | `HOST_EVENT_API_MISSING` | `unsupported`，Plugin 不加载 |
| `ExtensionAPI.exec` | required | 受控无副作用命令 smoke | `HOST_EXEC_MISSING` | `unsupported`，无法可靠观察仓库状态 |
| `ExtensionContext.sessionManager` | required | context 中为稳定 object | `HOST_SESSION_MANAGER_MISSING` | `unsupported`，禁止跨 Session 共用队列 |
| `sessionManager.getSessionId` | optional | `typeof === "function"` 且返回稳定 id | `HOST_SESSION_ID_UNAVAILABLE` | `degraded`，仅使用 manager-scoped anonymous key |
| `ExtensionAPI.registerTool` | optional | `typeof === "function"` | `HOST_REGISTER_TOOL_MISSING` | `degraded`，禁用 `sbtd_workflow` machine tool；slash commands 保留 |

必需事件：

| Event | 等级 | 缺失 reason code | 认证行为 |
|---|---|---|---|
| `session_start` | required | `HOST_EVENT_SESSION_START_MISSING` | `unsupported` |
| `session_switch` | required | `HOST_EVENT_SESSION_SWITCH_MISSING` | `unsupported` |
| `session_branch` | required | `HOST_EVENT_SESSION_BRANCH_MISSING` | `unsupported` |
| `session_tree` | required | `HOST_EVENT_SESSION_TREE_MISSING` | `unsupported` |
| `before_agent_start` | required | `HOST_EVENT_BEFORE_AGENT_START_MISSING` | `unsupported` |
| `session.compacting` | required | `HOST_EVENT_COMPACTING_MISSING` | `unsupported` |
| `tool_call` | required | `HOST_EVENT_TOOL_CALL_MISSING` | `unsupported` |
| `tool_approval_resolved` | required | `HOST_EVENT_APPROVAL_RESOLVED_MISSING` | `unsupported` |
| `tool_result` | required | `HOST_EVENT_TOOL_RESULT_MISSING` | `unsupported` |
| `turn_start` | required | `HOST_EVENT_TURN_START_MISSING` | `unsupported` |
| `turn_end` | required | `HOST_EVENT_TURN_END_MISSING` | `unsupported` |
| `session_stop` | required | `HOST_EVENT_SESSION_STOP_MISSING` | `unsupported` |
| `credential_disabled` | optional | `HOST_EVENT_CREDENTIAL_DISABLED_MISSING` | `degraded`，禁用 credential revocation 同步 |

事件存在不能只靠注册不抛错证明。Host Event Surface 必须让真实 Host 逐项触发
required event，并校验 payload 和顺序；optional event 缺失只能产生列明 reason code
的 `degraded` 诊断。

### 5.2 Runtime capability probe

定义结构探测 profile：

```text
omp-runtime-capabilities-v1
```

结果：

```ts
type HostContractAssessment =
  | {
      status: "compatible";
      contractProfile: "omp-extension-v1";
    }
  | {
      status: "degraded";
      contractProfile: "omp-extension-v1";
      missingOptionalCapabilities: string[];
    }
  | {
      status: "unsupported";
      contractProfile: "omp-extension-v1";
      missingRequiredCapabilities: string[];
    };
```

规则：

- 必需能力缺失时 fail closed。
- 可选能力缺失时只禁用表中对应功能，并输出固定 reason code。
- `compatible` 映射为 profile `passed`；`degraded` 只有在缺失项全部来自本表 optional 集合、被禁用功能与 reason code 完整记录时映射为 `passed-with-diagnostics`，并在 overall 派生中按 pass 计数；`unsupported` 映射为 `failed`。
- event payload 必须在 adapter edge 做 schema 校验。
- malformed 或 unknown payload 不得被解释成批准、验证完成或成功状态。
- 不进行隐式远程查询，不在运行时下载兼容规则。

Capability probe 只能证明结构存在，不能证明 Host 实际发送事件、payload 语义或事件顺序正确。

## 6. 分离的兼容证据 Scope

### 6.1 Command Surface

Profile：

```text
omp-command-surface-v1
```

由精确 tarball 四命令验收证明：

- Plugin 扩展能加载。
- `/sbtd` command 能注册。
- `/sbtd help` 完成。
- `/sbtd status` 完成。
- `/sbtd report` 完成。
- `/sbtd onboard plan` 完成。
- 不请求 Provider。
- 不触发 approval。
- 不产生意外写入。
- 不出现 `Failed to load extension`。

四命令只认证 Command Surface，不能认证 tool/session/compaction 事件契约。

### 6.2 Host Event Surface

Profile：

```text
omp-host-events-v1
```

必须使用真实 OMP Host integration suite，验证：

- 所有必需事件能成功订阅并实际触发。
- payload 满足 Plugin 的 schema。
- Session 和 turn 事件顺序符合约束。
- `tool_call` 可以被 Plugin 按策略阻断。
- `tool_approval_resolved` 与原始 `toolCallId`、risk class 和 fingerprint 正确绑定。
- `tool_result` 正确消费 one-shot approval。
- `session.compacting` 触发状态保存且不泄漏敏感内容。
- Session switch、branch 和 tree 之后会重新观察状态。
- malformed/unknown event fail closed。
- 不同 Session 的串行队列和 approval 不会交叉。

Host Event Surface 的 required events 全部通过、仅 optional
`credential_disabled` 缺失时，outcome 为 `passed-with-diagnostics`，并记录
`HOST_EVENT_CREDENTIAL_DISABLED_MISSING`；该结果在 overall 派生中按 pass
计数。任何 required event 失败仍为 `failed`。

Fake unit test 和静态类型检查只能作为前置安全网，不能替代真实 Host Event Surface 认证。

建议在隔离环境中使用确定性的本地 provider/model adapter 驱动真实 Host 产生受控 tool call、approval、tool result、turn 和 compaction 事件。测试只持久化事件名称、schema-valid 结论、顺序摘要、非敏感 reason code 和 digest；不得持久化 profile、token、原始 transcript、模型输出或 PII。

若 OMP 公共 SDK 无法可靠触发某个 Plugin 必需事件，则该 OMP 版本不能取得完整 `certified`。必须增加受控 Host adapter，或推动 OMP 提供稳定的 extension contract fixture / contract version。

### 6.3 整体认证派生规则

只有以下三项全部通过，且每个 profile evidence trust 都已验证，同时 ledger
assessment 本身具有受信任 CI 身份签发的 provenance/attestation：

```text
runtimeCapabilityProbe == passed | passed-with-diagnostics
commandSurface == passed
hostEventSurface == passed | passed-with-diagnostics
allProfileEvidenceTrust == verified
assessmentProvenance == verified
```

才能派生：

```text
overallOutcome == certified
```

`evidenceSha256` 和 `entrySha256` 只证明内容完整性，不能证明证据由受信任
执行者生成；编辑者可以修改内容后重算 hash。`certified` 必须额外验证签名
attestation 的 issuer、repository、workflow identity、run、source revision、
Plugin tarball digest、OMP exact version 和三个 evidence digest。

禁止调用者直接提交 `overallOutcome: certified`。所有公开 overall state 只从
最新有效的受信任 assessment/revocation successor chain 派生；本地或手工结果
只能记录为 `local-observation`，不能写入公开 ledger 或改变 support matrix。

| 条件（按行顺序求值） | 派生状态 |
|---|---|
| OMP 不在 peer range | `out-of-range` |
| 存在受信任且有效的当前 revocation successor | `revoked` |
| 任一已执行必需 profile 为 fail | `incompatible` |
| 三个必需 profile 均 pass，全部 profile evidence trust 和 assessment provenance verified | `certified` |
| 无 profile fail，至少一个 pass，且其余 missing/blocked 或任一 profile evidence trust missing/invalid | `partially-verified` |
| 没有 profile pass 或 fail | `eligible` |

## 7. Compatibility Ledger

### 7.1 Source of Truth

新增仓库侧、默认不进入 npm package `files` 白名单的 ledger：

```text
plugins/omp-sbtd/validation/p0/compatibility-ledger.v1.json
```

每次受信任 CI 运行都追加一个可离线重放验证的 assessment entry；以下是完整
认证示例，部分通过或失败使用同一 schema，但 `profiles[].outcome`、
`profiles[].evidenceTrust` 和派生 `overallOutcome` 不同：

```json
{
  "schemaVersion": 1,
  "entryType": "assessment",
  "attemptId": "gha:<run-id>:<run-attempt>",
  "pluginPackage": "@kunolu/omp-sbtd",
  "pluginVersion": "0.1.0-rc.12",
  "pluginTarballSha256": "<sha256>",
  "pluginPackageIntegrity": "<SRI>",
  "pluginManifestSha256": "<sha256>",
  "pluginPeerRange": "17.3.5",
  "assessmentTargetSource": "published-catalog",
  "ompVersion": "17.3.5",
  "ompRegistryIntegrity": "<registry integrity>",
  "loadedRuntimeVersion": "17.3.5",
  "loadedRuntimeArtifactSha256": "<sha256>",
  "contractProfile": "omp-extension-v1",
  "commandSetSha256": "<sha256>",
  "hostEventScenarioSetSha256": "<sha256>",
  "previousEntrySha256": null,
  "profiles": {
    "runtimeCapabilityProbe": {
      "profile": "omp-runtime-capabilities-v1",
      "outcome": "passed",
      "evidenceTrust": "verified",
      "evidenceSha256": "<sha256>",
      "evidenceLocator": "validation/p0/evidence/<content-addressed-path>"
    },
    "commandSurface": {
      "profile": "omp-command-surface-v1",
      "outcome": "passed",
      "evidenceSha256": "<sha256>",
      "evidenceTrust": "verified",
      "evidenceLocator": "validation/p0/evidence/<content-addressed-path>"
    },
    "hostEventSurface": {
      "profile": "omp-host-events-v1",
      "outcome": "passed",
      "evidenceTrust": "verified",
      "evidenceSha256": "<sha256>",
      "evidenceLocator": "validation/p0/evidence/<content-addressed-path>"
    }
  },
  "provenance": {
    "format": "github-artifact-attestation-v1",
    "issuer": "https://token.actions.githubusercontent.com",
    "repository": "KunoLu/KPi",
    "workflowRef": ".github/workflows/omp-compatibility-certification.yml@refs/heads/main",
    "eventName": "workflow_dispatch",
    "runId": "<run id>",
    "sourceRef": "refs/heads/main",
    "sourceRevision": "<full commit sha>",
    "attestationBundleSha256": "<sha256>",
    "attestationBundleLocator": "validation/p0/evidence/<content-addressed-path>",
    "subjectDigests": {
      "pluginTarball": "<sha256>",
      "pluginManifest": "<sha256>",
      "ompArtifact": "<sha256>",
      "runtimeCapabilityProbe": "<sha256>",
      "commandSurface": "<sha256>",
      "hostEventSurface": "<sha256>"
    }
  },
  "overallOutcome": "certified",
  "entrySha256": "<sha256>"
}
```

该 rc.12 entry 只示例 `rc.12 + OMP 17.3.5` 的 schema。只有新运行的三个
profile、profile evidence trust 和 assessment provenance 全部满足 §6.3 时，
才能产生该 `certified` entry；既有四命令验收不得回填或升级为认证证据。
由于已发布 rc.12 的 tarball-bound peer 精确为 `17.3.5`，不得为其他 OMP
版本合成 rc.12 assessment。

`assessmentTargetSource` 枚举为 `candidate-envelope` 或 `published-catalog`。
两者使用同一 profile/trust/outcome 派生规则，但 candidate assessment 不进入公开
support matrix。只有相同 exact identity 完成 Registry 复核并出现在 published
target catalog 后，support matrix 才能消费其最新有效 assessment；无需也不得
把 candidate entry 原位改写为 published。

`profiles[].outcome` 枚举为 `passed`、`passed-with-diagnostics`、`failed`、
`blocked`、`missing`；`passed-with-diagnostics` 仅允许 Runtime capability
或 Host Event profile 在 required scope 全部通过且只缺 optional scope 时使用。
`profiles[].evidenceTrust` 枚举为 `verified`、`missing`、`invalid`。
`blocked`/`missing` scope 的 `evidenceSha256` 与 `evidenceLocator` 为 `null`，
禁止伪造占位 digest。

`entrySha256` 的算法固定为：移除 `entrySha256` 字段后，按 RFC 8785
canonical JSON 序列化完整 entry，再计算 SHA-256。P0 的所有
`evidenceLocator` 和 `attestationBundleLocator` 必须指向仓库内
`plugins/omp-sbtd/validation/p0/evidence/<content-addressed-path>` 下的
append-only 证据。新 bundle 必须与首次引用它的 assessment entry 在同一个
受控 bot PR 中原子审核，但 target 类型决定该 PR 的公开范围：

- Pre-publication candidate PR 只包含 evidence/attestation bundle 和
  `candidate-envelope` assessment，不得新增 published target 或更新公开
  support matrix。
- Post-publication admission PR 包含 Registry exact identity proof、published
  target catalog append 和由已入库 assessment 派生的 support matrix；它可以
  引用已入库 candidate evidence。若本次产生新 profile evidence，则新 bundle
  仍须与首次引用它的 assessment 同 PR。

只要 ledger 仍引用 bundle 就不得删除。GitHub Actions artifact 只可用于临时
传输/诊断，不得作为长期 locator 或唯一副本。

### 7.2 写入与信任约束

信任边界单独版本化：

```text
plugins/omp-sbtd/validation/p0/compatibility-trust-policy.v1.json
```

该 policy 必须 allowlist：

- issuer：`https://token.actions.githubusercontent.com`。
- repository：`KunoLu/KPi`。
- workflow identity：`.github/workflows/omp-compatibility-certification.yml@refs/heads/main`。
- source ref：受保护的 `refs/heads/main`。
- 允许事件：当前仅 `workflow_dispatch` 和 `schedule`。npmjs.org 不直接提供 GitHub `registry_package` 事件；若未来增加外部 Registry webhook，必须先设计受认证的 ingress、更新 trust policy 版本并单独评审。
- 受保护 certification environment 只授予 attestation 签发；独立 PR-creation job 只用 job-scoped `GITHUB_TOKEN` 创建受控 bot PR。两者都不拥有绕过 branch protection 直写 `main` 的权限。

认证 runner 不执行 fork、PR head 或调用者可控的 workflow 定义。Validator
必须对签名、issuer、repository、workflow ref、source ref/revision、event、
run 和所有 subjects 做 allowlist/identity 校验；任一不符都不能派生
`certified`。

Bot PR 的 branch-protection required status 必须由受信 `main` 上的独立
`.github/workflows/omp-compatibility-ledger-validate.yml` 验证，并由专用
Status GitHub App 签发。job-scoped `GITHUB_TOKEN` 只创建 bot PR 或只读验证，不拥有
`statuses: write`：

1. 独立 PR-creation job 用 job-scoped `GITHUB_TOKEN` 创建 bot PR；attestation job 只签发证据，不创建 PR。
2. Release owner 从 `refs/heads/main` 手工运行 validator，必填输入为
   `prNumber`、`expectedHeadSha` 和 `certificationRunId`。
3. Validator 的 `GITHUB_TOKEN` 权限固定为 `contents: read` 和
   `pull-requests: read`；不用 certification environment、`id-token` 或任何
   contents/pull-request/status write。
4. Validator job 引用独立 environment
   `omp-compatibility-ledger-status`。该 environment 不与 certification
   environment 共用，deployment branch policy 只允许 branch `main`、不允许
   tag，关闭 administrator bypass，并由 release owner reviewer 批准。
5. Status App 只安装在 `KunoLu/KPi`，权限固定为 Metadata read 和 Commit
   statuses read/write；不授予 contents、pull requests、checks、actions、
   attestations、deployments 或 administration 权限。
6. App private key 只保存在上述 environment secret；App ID/installation ID
   可作为 environment variables。不得复制到 repository/organization secret、
   artifact、cache、log 或 evidence。
7. App installation token 只在写 `pending`/最终 status 的受控 step 中注入；
   不传入解析 PR 内容的 validator step 或子进程，短期 token 随 job 结束失效。
8. 固定 commit-status context 为 `omp-compatibility-ledger-validate`，
   `target_url` 指向 validator run。Branch protection 将该 context 设为 required
   并把 expected source 固定到 Status App，而不是 GitHub Actions app。
9. Required status 通过后，同一 release owner 再执行独立 PR approval；environment
   approval 与 PR approval 是两个审计动作，仓库不硬编码个人账号。

Environment branch policy 是 status-source 隔离的强制边界：从 PR/其他 ref
dispatch 的改写 workflow 即使复用 context，也无法取得 Status App private key；
删除 environment 后只能使用 GitHub Actions app 身份，branch protection 不接受。
Workflow 内 `github.ref == main` guard 仅作额外诊断，不能替代 environment policy
和 expected App source。

Validator 在写任何 status 前必须重新读取 PR 并确认：

- PR 仍 open，head repository 为 `KunoLu/KPi`，base 为 `main`，automation branch
  名符合约束，实际 head SHA 与 `expectedHeadSha` 完全相同。
- PR metadata 绑定 `certificationRunId`、受信 main certification source
  revision 和预期 candidate/admission 类型。
- 允许修改路径精确限制为生成的 evidence/target/ledger/support-matrix 范围；
  PR 修改 validator、workflow 或其依赖代码时 fail closed。

通过前置身份检查后，Status App 对该 validated head SHA 写 `pending`，再验证：

- 原始受信 main certification run 的 attestation/provenance、
  content-addressed bundle、canonical hash、successor chain 和所有 subject
  digests。
- candidate/admission 分离、append-only diff 和派生 support matrix。
- 触发 actor、source run/revision、允许路径与所有输入未被不受信 PR 内容替换。

失败时由同一 App 对 validated head SHA 写同 context `failure`；成功前再次读取 PR，
只有 actual head SHA 仍等于 `expectedHeadSha` 才写 `success`。取消、App token
签发失败或异常终止允许 `pending`/missing 保留并阻断合并，不能 fail open。每个
PR 的 validator run 用 concurrency group 串行化且不 cancel in progress；head
更新后旧 SHA 的 status 自然失效，必须对新 SHA 重新手工运行。

Gate 0.2 必须用真实 bot PR 证明：

- main dispatch + environment approval 可签发 Status App status。
- PR/其他 ref 的改写 workflow 无法取得 App credential；同 context 的 GitHub
  Actions status 不满足 expected-source branch protection。
- 错误/过期 SHA 不成功，head 更新使旧 status 失效，failure/pending/missing
  阻断合并。
- private key/token 不进入 log、artifact、evidence 或 validator child process。
- App key rotation/revocation 后旧 key 失效；App/status 不可用时保持阻断。移除
  required status 只能由 release owner 作为独立 rollback 决策执行。

Status App/environment/branch-protection 配置属于 implementation HITL。先创建并
安装 App、配置 environment，再运行首次 status dry run；App 已产生 status 后才把
context + expected App source 加入 `main` required status，随后运行完整阻断测试。
任一项失败则 Gate 0.2 为 `blocked`，不得退回 GitHub Actions app 同名 status。

其他写入约束：

- Ledger append-only；不得原位把 failed 改成 passed。
- Target、ledger 和派生 support matrix 只通过受控 bot PR 写回；bot credential 不得 bypass branch protection，合并仍需正常 required checks/review。
- 新 target、re-certification 和 revocation bot PR 统一要求 required checks 通过并由 1 名 release owner/maintainer 批准；实际 GitHub user/team 由 branch protection/environment 配置管理，不写入 trust policy 或代码。
- Bot PR 必须绑定产生它的受信 workflow run、source revision、attestation/evidence subjects 和完整生成 diff；validator 拒绝手改 hash、缺失 provenance 或越权文件。
- 每个 entry 绑定 Plugin tarball、tarball-bound manifest digest/peer range、OMP exact version、loaded Runtime identity、contract profile、scenario/command-set digest 和独立 evidence digests。
- `entrySha256`/`evidenceSha256` 负责完整性绑定，不作为执行者身份或真实性证明。
- fork、未受信 workflow、本地运行、手工文件和无法验证的 assessment provenance 只能生成独立的 `local-observation`，不得写入公开 ledger，也不得改变公开 overall state。
- 每次 assessment provenance 验证成功的 CI run 都必须 append assessment entry，包括 candidate、`incompatible` 和 `partially-verified`；support matrix 只消费已存在于 published target catalog 的 identity，并从其最新有效 successor 唯一派生。
- 重复 identity 是幂等 no-op。
- 显式 rerun 创建新 attempt，并通过 `previousEntrySha256` 建立同一 identity 的 successor chain。
- `overallOutcome` 由 validator 派生。
- 失败 profile 只能记录为 `failed`；同一 run 中已完成且通过的 scope 可以保留为 pass。非 `certified` assessment 绝不能产生 `overallOutcome: certified`。
- 修复错误证据的方式是重新运行并 append，不是删除历史。

### 7.3 撤销语义

已经公开的认证只能通过受信任 CI 签发的 append-only revocation 撤销：

```json
{
  "schemaVersion": 1,
  "entryType": "revocation",
  "pluginTarballSha256": "<sha256>",
  "ompVersion": "17.3.5",
  "contractProfile": "omp-extension-v1",
  "supersedesEntrySha256": "<assessment-or-successor-sha256>",
  "reasonCode": "HOST_REGRESSION_CONFIRMED",
  "effectiveAt": "<RFC3339 timestamp>",
  "provenance": "<same trusted CI identity fields>",
  "entrySha256": "<sha256>"
}
```

当前状态取该 identity 的最新有效 successor。有效 revocation 将当前状态派生为
`revoked`；历史 `certified` entry 保留，但 support matrix 必须显示撤销状态，
不得继续公开为 `certified`。恢复支持必须产生新的完整认证 attempt 并链接该
revocation，不能删除或覆盖历史。

## 8. Release Validator 改造

当前 validator 要求 lockfile specifier 和安装版本都是同一个精确版本，并要求 manifest 的 `currentRuntimeVersion` 与其完全相等。需要改成独立检查：

1. `package.json.peerDependencies` 等于 policy `peerRange`。
2. `package.json.devDependencies` 是一个精确版本。
3. lockfile 的精确 dev 安装版本与 dev dependency 一致。
4. dev pin 位于 peer range 内。
5. 本次 `--runtime-version` 是精确 SemVer。
6. 本次 exact Runtime 位于 peer range 内。
7. Host run 的结果只绑定本次 exact Runtime，不修改 policy。
8. Ledger entry 的三个 evidence scope 均为当前 tarball和当前 Runtime。
9. `certified` 必须验证受信任 CI attestation 的签名、issuer、repository、workflow、run、source revision 和所有 subject digests。
10. `overallOutcome` 只能由 profile evidence 和 provenance 验证结果派生。
11. publication authorization 只消费精确候选 tarball 的隔离四命令验收结果，不消费 `overallOutcome`。
12. compatibility validator 可以阻止错误认证或 ledger 更新，但不得阻止已满足四命令合同的 pack/publish 授权。

建议语义重命名：

- `currentRuntimeVersionSchema` → `runtimeVersionSchema`
- `resolveCurrentRuntimeVersionFromLockfile` → `resolveDevelopmentRuntimeVersionFromLockfile`
- `currentRuntimeVersion` 运行结果字段 → `testedRuntimeVersion`

所有调用者完成迁移后删除旧 exact-current 语义，不保留兼容 alias。

## 9. CI 与认证矩阵

每个 matrix cell 必须在全新隔离 harness 中安装冻结的 Plugin tarball 与目标
OMP exact Registry artifact，不使用 workspace dev dependency 或 lockfile。
运行任何 profile 前，真实 Host 进程必须报告实际加载的 OMP package version 和
artifact integrity/digest；runner 将它们与目标 Registry artifact 逐项断言并写入
三个 evidence scope 及 attestation subjects。version 或 digest 任一不一致时
立即 fail closed，禁止接受调用者传入的 `--runtime-version` 代替运行时证明。

### 9.0 初始迁移基线

1. 已发布 rc.12 保持精确 peer `17.3.5`，不得修改、重打或覆盖。
2. rc.12 既有四命令验收只保留为 Command Surface/public-supported 基线，不自动回填 `certified`。
3. 若要认证 `rc.12 + OMP 17.3.5`，必须从受信任 CI 重新运行三个 profile，并将精确 tarball、manifest、peer range、Runtime 和证据身份写入 target/ledger。
4. 第一个采用 `>=17.3.5 <18` 的 Plugin 必须是新的、尚未发布的候选版本；本方案不预先指定其版本号。
5. 只有该候选通过现行精确 tarball 四命令发布 Gate 并成为不可变 Registry tarball 后，后续 OMP 17.x 才能复用它、只更新 ledger。
6. npm tag 只用于发现候选或现有基线。预发布认证消费 immutable candidate target envelope；已发布重跑消费 `compatibility-targets.v1.json` 中的 exact version + package integrity + tarball/manifest digest。

### 9.1 Plugin 发布与独立兼容认证

对一个不可变候选 tarball 执行：

1. 使用精确 dev floor `17.3.5` build/typecheck。
2. 生成并冻结 tarball SHA-256、package SRI、manifest SHA-256 和
   tarball-bound peer range，形成不可变 candidate target envelope。
3. 在发布手册规定的隔离 OMP `17.3.5` 环境中，对该精确 tarball执行
   `/sbtd help`、`/sbtd status`、`/sbtd report` 和 `/sbtd onboard plan`；
   该四命令结果是 RC publication 的唯一兼容性 Gate。
4. 四命令通过且发布负责人另行授权时，可以发布该同一 tarball；Runtime
   Capability 和 Host Event Surface 缺失、blocked 或 failed 不得阻断该授权，
   但也不得被隐藏或解释为 `certified`。
5. 三 profile 兼容认证可在发布前或发布后独立运行。运行时选择：
   - `minimum`：`17.3.5`
   - `latest-in-range`：Registry 当前最新稳定 17.x
6. 对每个不同 Runtime 运行 Runtime capability probe、Command Surface suite 和
   Host Event Surface suite；minimum 和 latest 相同时只执行一次。
7. 受信任 CI workflow 为 tarball、manifest、OMP version 和三个 evidence
   subjects 生成签名 artifact attestation，并为每个 profile 记录
   `evidenceTrust`。
8. 发布前运行时，Validator append `assessmentTargetSource:
   candidate-envelope` 的受信任 assessment，但不得更新公开 support matrix。
9. 发布后按 exact version 下载 Registry tarball，验证 bytes、SHA-256 和
   `dist.integrity` 等于 candidate target envelope，再把该 identity 追加到
   published target catalog；tag 位置不属于 identity。
10. target catalog 追加成功后，support matrix 消费相同 exact identity 的最新
    有效 assessment；没有受信任 profile pass 时从 `eligible` 开始，不得默认写成
    `certified`，也不得改写历史 assessment。
11. profile 失败创建 compatibility issue 和相应 ledger assessment，但不自动
    unpublish、移动 dist-tag 或重发 npm。

### 9.2 新 OMP 17.x 发布后

当前由 `schedule` 或受信任的 `workflow_dispatch` 启动；未来外部 Registry trigger 只有在受认证 ingress 和新 trust policy 已评审后才能启用：

1. 查询最新 OMP 17.x 稳定精确版本；prerelease 默认不进入公开认证矩阵。
2. 从 `compatibility-targets.v1.json` 读取一个或多个已固定 published Plugin target；每项必须包含 exact version、package integrity、tarball SHA-256、manifest SHA-256 和 tarball-bound peer range。
3. `next`/`latest` 只可用于一次性发现，不能作为长期 target selector。本次迁移可通过 `next` 发现 rc.12，但认证前必须解析并核对 catalog 中的不可变 identity。
4. 按 exact version 下载 tarball，验证 Registry `dist.integrity` 等于 target `packageIntegrity`，并验证 tarball SHA-256、manifest SHA-256 和 manifest peer range；任一不一致立即 fail closed。
5. 若目标 OMP 不满足该 tarball-bound peer range，派生 `out-of-range`，不运行任何 profile；不得读取当前 Compatibility Policy 覆盖历史 range。
6. 若 ledger 已有同一 tarball SHA + manifest SHA/peer range + OMP version + contract profile 的完整受信任结果，幂等跳过。
7. 在全新隔离 harness 中安装冻结的既有 Plugin tarball和目标 OMP exact Registry artifact。
8. 由真实 Host 证明实际加载 Runtime version/integrity 后，运行三个 profile。
9. 受信任 CI workflow 签发绑定 run、source revision、tarball、tarball manifest、实际 OMP artifact 和三个 evidence digests 的 assessment provenance，并记录每个 profile 的 `evidenceTrust`。
10. assessment provenance 验证成功时，无论派生为 `eligible`、`partially-verified`、`incompatible` 或 `certified`，都 append assessment，并重新生成仓库侧 support matrix。
11. 任一已执行必需 profile 失败：派生 `incompatible`；没有 profile 通过时保持 `eligible`；至少一个通过但其余 missing/blocked，或任一 profile evidence trust missing/invalid：派生 `partially-verified`。所有非认证结果都创建兼容 issue。
12. assessment provenance 自身无法验证时，不写公开 ledger、不改变 support matrix，并创建基础设施事件。
13. 不修改 Plugin package version、tarball、SBOM、target identity 或 npm dist-tag。
14. 只有修复 Plugin 代码或改变 peer range 时才发布新 Plugin。

### 9.3 OMP 18+

当前已发布 rc.12 的 peer 精确为 `17.3.5`，方案实施后首个 widened-peer tarball
使用 `>=17.3.5 <18`；这两个 tarball 对 OMP 18 都始终为 `out-of-range`。
未来扩展 major 时：

1. 准备新的、尚未发布的 Plugin candidate version，并让该候选 tarball-bound
   peer range 显式包含目标 OMP 18 exact version；旧 tarball和旧 peer range
   保持不变。
2. 运行任何 profile 前，§8 validator 必须先证明目标 OMP 18 exact version 位于
   新候选的 tarball-bound peer range。若不在 range，最高优先级结果仍为
   `out-of-range`；不得运行 profile，也不得用 profile pass 覆盖。
3. 使用位于新 peer range 内的精确 dev Runtime 构建，并从受保护 source revision
   冻结 candidate tarball identity。
4. 在发布合同规定的精确 Runtime 环境中运行同一 tarball 四命令验收。
5. 四命令通过且发布负责人另行授权时，可以发布该精确 tarball；三个 profile
   不是 npm publication Gate。
6. 仅对已通过 range 检查的 OMP 18 exact artifact 独立运行三 profile 与
   attestation；全部通过且 provenance 受信后才可公开为 `certified`。
7. profile 缺失或失败时按唯一规则派生 `eligible`、`partially-verified` 或
   `incompatible` 并创建 compatibility issue；不得把 published/installable
   自动解释为 certified，也不得自动重发 npm。

## 10. 公开文档策略

随 npm 包发布的 README 只保存稳定政策：

```text
Installable OMP range: >=17.3.5 <18.
Exact certified OMP versions are maintained in the repository compatibility matrix.
A version inside the install range is not automatically certified.
```

不得把每个新认证的 17.x 版本持续写入：

- Plugin README 版本清单
- Plugin changelog
- Plugin SBOM
- Plugin tarball
- `package.json` dev dependency

精确认证列表由仓库侧 ledger 和派生 support matrix 提供。Ledger 更新不是 Plugin 发布。

## 11. BDD 计划

沿用现有规则：场景文本使用简体中文，Gherkin 结构关键词使用英文。

### 11.1 `p0-conformance-release.feature`

新增或更新场景：

1. peer range 与精确 dev pin 分离。
2. dev pin 必须位于 peer range 内。
3. 新 OMP 17.x 对既有 tarball认证通过后，Plugin version 与 tarball SHA 不变。
4. overall state 按固定优先级唯一派生。
5. 新 OMP 版本只有部分 profile 通过时为 `partially-verified`。
6. Host Event Surface 未通过时不得从四命令结果派生 `certified`。
7. OMP 18 被 peer range 拒绝。
8. ledger entry 必须绑定精确 Plugin tarball、实际加载的 OMP artifact 和证据集。
9. 未受信 provenance 不能派生 `certified`。
10. append-only revocation 撤销当前认证但保留历史。
11. ledger 更新不得触发 pack、publish 或 dist-tag 变更。
12. 精确候选 tarball 的隔离四命令是所有 RC 的唯一 publication compatibility Gate；三个 profile outcome 不参与 npm 授权。
13. 已发布 target 没有受信 profile pass 时从 `eligible` 开始；认证缺失或失败不得触发自动 unpublish、重发或 dist-tag 移动。

### 11.2 `sbtd-control-bootstrap.feature`

新增或更新场景：

1. Host Contract 通过时注册完整 `/sbtd`。
2. 必需 capability 缺失时 fail closed。
3. 可选 capability 缺失时只降级相关功能。
4. malformed event 不得被解释成批准或完成。
5. tool approval 和 tool result 不跨 Session、turn、risk class 或 target 复用。
6. compaction 和 Session 切换保持状态隔离。

## 12. 自动测试计划

### 12.1 Policy 与 range

- `17.3.5` 位于 range。
- 最新 17.x 位于 range。
- `18.0.0` 不位于 range。
- prerelease Runtime 默认拒绝，除非单独显式授权实验路径。
- dev pin 和 lock 安装版本精确一致。
- dev pin 不在 range 时 fail closed。

### 12.2 Runtime capability

- 必需方法缺失。
- 可选 `registerTool`、`sessionManager.getSessionId` 或 `credential_disabled` 缺失。
- optional-only 缺失映射为 `passed-with-diagnostics`，且 reason code/disabled feature 完整。
- required 缺失或 optional 集合外的 degraded 不能按 pass 计数。
- 未知事件或 malformed payload。
- event subscription 抛错。
- Host registration 部分成功后失败时不得留下误导性 ready 状态。

### 12.3 Host Event integration

- Session start/switch/branch/tree。
- before-agent-start、turn start/end。
- tool call block。
- approval resolved exact binding。
- tool result one-shot consumption。
- compaction preserve。
- session stop cleanup。
- 多 Session 串行与隔离。

### 12.4 Ledger

- duplicate no-op。
- out-of-order attempt。
- tampered digest。
- invalid/missing signature。
- wrong attestation issuer、repository、workflow identity、source ref 或 event。
- attestation run/source revision 与 ledger 不一致。
- attestation subject 与 tarball、实际 OMP artifact 或 profile evidence digest 不一致。
- fork/local/manual evidence 不写公开 ledger、不改变 support matrix。
- trusted partial/failed run 仍 append assessment，并唯一派生 `partially-verified`/`incompatible`。
- assessment provenance 无法验证时不 append、不改变既有公开状态。
- wrong tarball。
- wrong target OMP version。
- Host 实际加载 Runtime 与目标 version/integrity 不一致。
- failed → fresh rerun → passed append chain。
- certified → trusted revocation → `revoked`。
- revoked → fresh full certification → `certified` successor chain。
- Command pass + Event blocked 只能派生 `partially-verified`。
- 三个 profile 全绿但 profile evidence trust 无效时仍只能派生 `partially-verified`。
- 同一 tarball跨两个 OMP 版本认证。
- ledger 更新前后 Plugin version 和 tarball SHA 不变。

### 12.5 CI trust 与 bot PR

- Trusted certification 只响应受信 `main` 的 `workflow_dispatch`/`schedule`。
- Attestation job 与 PR-creation job 使用分离的 job-level permissions。
- PR-creation job 只使用 job-scoped `GITHUB_TOKEN`；validator 由 release owner 从 `main` 手工 `workflow_dispatch`，输入 PR number、expected head SHA 和 certification run ID。
- Validator 的 `GITHUB_TOKEN` 只读；Status App token 仅有 Commit statuses write，并只在 main-only protected environment 的 status steps 中可用。
- Validator workflow/code 必须来自受信 `main`，只通过 API 把 PR diff/files 当不受信数据读取；不得执行 PR head。
- Validator 拒绝错误 actor/head repository/base/branch/run/source revision/head SHA、非允许文件、篡改 bundle/hash/provenance 和 candidate/admission 混写。
- 同 PR runs 串行；成功前重读 head。错误/过期 SHA 不成功，head 更新后旧 status 失效，failure/pending/missing 阻断合并。
- Branch protection 只接受 Status App 签发的固定 context；GitHub Actions app 同名 status、非 main ref、environment bypass 和已撤销或轮换后的旧 key 均不能通过。
- Private key/token 不进入 PR parser、child process、log、artifact 或 evidence；validator 不签发 certification evidence、不 append。
- 所有第三方 action reference 固定 commit SHA。

### 12.6 Package 与发布

- typecheck
- lint
- Plugin full tests
- build
- generated Kit check
- SPDX SBOM
- pack dry-run
- packed-content inventory
- minimum + latest-in-range matrix
- wrong-Runtime installation fail-closed proof
- same-tarball/no-republish proof

## 13. 实施顺序

### Gate 0：建立安全且一致的实施基线

按用户确认，本方案在当前 `feature/p0-omp-sbtd-foundation` 分支实施，不另建
feature branch 或 worktree。开始实现前必须记录 baseline commit，并确认工作区
只有本任务拥有的修改；本计划文档的修改须先纳入该基线或明确作为 task-owned
变更。不得删除、reset、覆盖或隐式吸收无关 WIP；发现其他所有者修改时先停止并
移交。若 manifest 与 lock 不一致，先确认目标 manifest，再用项目 package
manager 重新生成 lockfile；禁止手工编辑 lockfile。

启动前必须记录并核对以下发布基线：

- 仓库 `package.json` version 是 `0.1.0-rc.12`。
- npm `next` 指向 `0.1.0-rc.12`，npm `latest` 仍是 `0.1.0-rc.2`；tag 仅用于发现，不能作为认证身份。
- rc.12 peer/dev dependency 均精确为 `17.3.5`。
- 从 Registry exact version 取得并核对 rc.12 tarball SHA-256、package integrity、manifest SHA-256 和 peer range，再写入 target catalog。
- README 仍引用 rc.11、CHANGELOG 仍写 rc.12 未发布、host acceptance 已记录 rc.12 发布；这些不一致必须列为发布文档 Slice 的显式输入，不能任选一份当 source of truth。
- GitHub Actions 已启用，但 repository 当前 `allowed_actions=all` 且 `sha_pinning_required=false`。
- `main` branch protection 当前要求 1 个 approval，符合已选 reviewer 数量；但 `required_status_checks=null`，尚无必须通过的 CI check。
- `main` 当前 `enforce_admins=false`。本任务只保证 bot credential 为非管理员且无 bypass 权限；不修改全仓 admin enforcement，该现状作为 residual risk 记录。
- 当前没有 GitHub environment 或专用 Status App；本任务新增 protected compatibility certification environment、独立 main-only status environment 和最小权限 Status App。所有外部设置变更仍需 implementation 阶段单独 HITL 授权。
- 已选择任务内最小加固：workflow 内所有第三方 action 固定 commit SHA；bot 保持非管理员；固定 required status 的 expected source 绑定 Status App。不修改 repository `allowed_actions=all`、`sha_pinning_required=false` 或 `enforce_admins=false` 的全仓设置。

### Gate 0.1：发布授权合同已确认

2026-08-24，发布负责人确认继续采用现有四命令发布合同：

1. 对普通 exact-peer、peer widening 和未来新 major RC，精确候选 tarball 的隔离
   四命令验收仍是 npm RC publication 的唯一兼容性门槛。
2. Runtime Capability、Command Surface 和 Host Event Surface 三个 profile 只
   派生兼容认证状态；它们不得阻断已经满足现行四命令合同的 RC。
3. 发布时没有受信任三 profile 结果的 target 从 `eligible` 开始；只有部分通过时
   为 `partially-verified`，任一已执行必需 profile 失败时为 `incompatible`，全部
   通过且 provenance 受信时才为 `certified`。
4. `published`、`installable` 和 `certified` 必须在 BDD、发布手册、quality
   guideline、README 和 support matrix 中保持为不同概念。
5. 该选择显式接受“RC 已发布但尚未 certified”的窗口；不得用 npm `next`、peer
   range 或四命令结果暗示完整 Host compatibility。

实现 Slice 1 必须删除 BDD、手册、长期规范和本计划中的 npm certification Gate
冲突。Ledger 只管理兼容认证，不控制 pack、publish 或 dist-tag。

### Slice 1：行为规格与 characterization

- 更新 BDD，明确四命令是所有 RC 的唯一 publication compatibility Gate。
- 增加“compatibility profile 结果不阻断 RC 发布，也不自动提升 certified”的场景。
- 固化当前 exact-version validator、host adapter、runtime registration 和发布授权行为。
- 先建立失败测试。

### Slice 2：Policy v2 与 validator clean cutover

- 实现 `compatibility.v2.json` schema 和 SemVer range。
- 分离 peer range、精确 dev pin、lock 安装版本和 tested Runtime 语义。
- 修改 release validator/CLI，迁移所有调用者和测试，删除 v1/exact-current alias。
- 保持 package peer/dev 精确 `17.3.5`，直到 Gate 2.1 通过。
- 固化发布只读取四命令结果、认证状态不参与 publication authorization 的合同。

### Gate 2.1：允许创建 widened-peer candidate

创建第一个 widened-peer candidate 只要求：

- Gate 0/0.1 和 Slices 1–2 已通过。
- peer range、精确 dev pin、lock 和 OMP 18 out-of-range 规则已有测试。
- 精确候选 tarball identity、四命令验收、发布文档和 rollback 路径可用。

Host Event、attestation、ledger 或三 profile matrix 缺失不阻止创建候选或后续
按四命令合同请求 RC publication；它们只阻止 `certified` 及公开认证矩阵更新。

### Slice 3：第一个 widened-peer candidate

- 选择一个新的、尚未发布的 Plugin version。
- 将候选 peer 改为 `>=17.3.5 <18`，dev dependency/lock 继续精确 `17.3.5`，并更新 Policy v2。
- 构建并冻结唯一候选 tarball及其 SHA-256、package SRI、manifest SHA-256/peer range，生成 candidate target envelope。
- 更新 README、host acceptance、quality-guidelines、CHANGELOG、package/release BDD 和测试；消除 rc.11/rc.12 发布状态冲突。
- 本方案不自动发布、不移动 tag；发布仍需单独授权。

### Gate 0.2：Host Event 与 CI feasibility spike（非 publication Gate）

小白化操作步骤见
[`omp-host-event-surface-beginner-guide.md`](./omp-host-event-surface-beginner-guide.md)。

在不读取真实凭据/profile 的隔离环境中证明：

- 真实 OMP `17.3.5` Host 能逐项触发并观察清单中的 12 个 required events，而不只是注册不抛错。
- Host 能报告实际加载的 Runtime version 和 artifact digest；当前只读取 `omp --version` 的证明不足。
- 确定性本地 provider/model adapter 可以驱动 tool call、approval、tool result、turn 和 compaction。
- 受保护 main workflow 能签发并验证 candidate target、三个 profile 和 assessment provenance 的 attestation。
- target/ledger 只通过受控 bot PR 写回；测试 job 不能直接写 `main`，bot credential 不能绕过 branch protection，合并必须经过最小权限 ledger validator required status 和 1 名 release owner/maintainer review。
- Base-branch validator 的 `GITHUB_TOKEN` 只读，不执行 PR head；独立 Status GitHub App 只在 main-only protected environment 的 status steps 中取得 Commit statuses write，branch protection 将固定 context expected source 绑定到该 App。

Spike 输出只能为 `feasible` 或 `blocked`，并记录缺失 Host fixture/API、CI 权限或
写入路径。`blocked` 不阻止符合四命令合同的 RC publication，但会阻止 Host Event
profile `passed`、公开 `certified` 和受信 support matrix 更新。此时先增加受控
Host adapter，或推动 OMP 提供稳定 extension contract fixture/version。

### Slice 4：Runtime Host Contract

- 深化 `src/runtime/index.ts`。
- 集中 capability assessment。
- 区分 required/optional capabilities。
- adapter edge schema validation。
- fail-closed/degraded diagnostics。

### Slice 5：Host Event integration suite

- 将 Gate 0.2 的可行性证明固化为真实 OMP Host integration suite。
- 触发全部 12 个 required lifecycle/tool/approval/compaction 事件。
- 输出消毒、hash-bound evidence。

### Slice 6：Target、Ledger、attestation 与矩阵 runner

- 实现 append-only published target catalog 和 ledger validator/writer。
- 实现 candidate target envelope 以及 exact version/integrity/tarball/manifest/peer-range 绑定。
- 实现 tag 移动不改变 target、历史 policy 不重解释 peer range 的验证。
- 实现三个 profile 的独立 evidence binding。
- 配置受信任 CI artifact attestation，并固定 issuer/repository/workflow trust policy。
- 配置独立 base-trusted `workflow_dispatch` ledger validator；PR 内容只经 API 作为数据读取，不执行 head。输入固定为 PR number、expected head SHA 和 certification run ID。
- 创建最小权限 Status GitHub App 和独立 main-only protected environment；App credential 仅注入 status steps，branch protection 将固定 context expected source 绑定到该 App。
- Workflow 内第三方 actions 全部固定 commit SHA；App key/token 不进入 validator parser、child process、artifact、log 或 evidence。
- Status App、protected environments 和 `main` required status 属于 implementation HITL 配置；未获外部设置授权时保持 Gate 0.2 `blocked`，不静默修改。
- 实现签名、workflow identity、run、source revision 和 subject digest 验证。
- 实现 derived overall outcome 和 minimum/latest/new-runtime job。
- 三 profile infrastructure 缺失或失败不能反向改变 Slice 1 固定的 publication contract。

### Slice 7：完整验证与独立发布决策

- 运行项目验证和独立 Release Readiness Review。
- 对同一候选 tarball运行精确四命令验收；这是 publication compatibility Gate。
- Host/CI infrastructure 可用时运行 minimum/latest 三 profile matrix；结果只更新
  compatibility assessment，不决定能否请求 npm 发布授权。
- 只有发布负责人另行明确授权时才发布 npm `next`；本方案本身不发布、不移动 tag。
- 若获授权，只发布通过四命令的同一 tarball；发布后验证 Registry exact identity，
  再追加 published target catalog entry。公开状态按实际 evidence 派生，允许从
  `eligible` 开始，不得默认写成 `certified`。

## 14. Rollback

发布前 rollback：

- revert range/policy/runtime/ledger 相关提交；
- 恢复 exact peer 和 compatibility v1；
- 不删除已经生成的失败/诊断证据；
- 未发布 tarball直接废弃。

发布后 rollback：

- 不覆盖、不重打已发布 Plugin 版本；
- 已认证 identity 出现回归时，通过 7.3 的受信任 append-only revocation 派生 `revoked`；
- support matrix 必须立即停止把被撤销 identity 公开为 `certified`；
- 必要时发布新的 Plugin 修复版本；
- npm 已发布 tarball和 ledger 历史保持不可变。

Ledger rollback：

- 新 reader 出现问题时可回退到旧 reader；
- append-only entries 保留但可由旧实现忽略；
- 不通过删除或原位修改伪造一致性；
- 恢复支持只能运行新的完整认证 attempt 并链接 revocation。

## 15. DDIA Data Design Review

```text
DDIA Data Design Review
Status: confirmed

Data owner and source of truth:
  The repository target catalog owns which immutable Plugin artifacts are
  eligible for certification runs: exact version, package integrity, tarball
  digest, manifest digest and tarball-bound peer range. The compatibility
  ledger owns exact Plugin-target + OMP-version assessments and revocations.
  Compatibility Policy v2 owns the installation/contract policy for a newly
  built Plugin, but never rewrites a historical target's peer range. The
  versioned trust policy owns accepted CI issuer/workflow/ref/event boundaries.
  Trusted CI attestation owns execution authenticity; npm tags, package.json
  in the current checkout and README do not own historical certification.

Write / read / async / failure paths:
  An authorized catalog update resolves a discovery tag or published version
  once, downloads the exact tarball and verifies Registry dist.integrity
  against the bound package integrity, plus tarball digest, extracted manifest
  digest and peer range, before appending the immutable published target.
  Pre-publication certification uses the same immutable identity in a candidate
  target envelope and records candidate assessments without exposing them in
  the public support matrix. It admits the identity to the catalog only after
  Registry verification; the matrix may then consume the matching immutable
  assessment without rewriting it. Scheduled CI reads only cataloged exact
  identities, intersects each
  target's bound peer range with the OMP matrix, verifies the loaded Runtime
  identity from the real Host, executes the exact host suites, signs assessment
  provenance, then appends every trusted assessment, including partial and
  failed outcomes. Passing scopes remain attributable to that attempt; a failed
  scope is never rewritten as passed. Untrusted local observations never alter
  catalog, ledger or the generated support matrix.

Consistency model:
  Target identities and ledger evidence are monotonic and append-only. Tag
  movement has no effect after target resolution. Each profile binds the exact
  tarball and manifest digest/peer range, loaded OMP artifact, contract profile,
  scenario/command set and result digest. Historical out-of-range derivation
  reads the tarball-bound peer range, never a newer Compatibility Policy.
  Hashes provide integrity; signed provenance and trust-policy verification
  provide execution authenticity. A valid revocation supersedes but never
  deletes historical certification.

Idempotency / ordering / retry / deduplication:
  A duplicate target or assessment identity is a no-op. The same Plugin version
  or tarball digest with conflicting integrity, manifest digest or peer range
  fails closed. Explicit reruns create a new attempt linked to the preceding
  entry digest. Revocation and re-certification append linked successors; no
  in-place outcome replacement.

Schema / migration / backfill / rollback / replay:
  Introduce target catalog schema v1, ledger schema v1, trust policy v1 and
  compatibility policy v2. Canonical entry hashing uses RFC 8785 after removing
  entrySha256. Existing 17.2.9 and rc.11 records remain historical. The
  published rc.12 four-command result proves only its current Command Surface
  baseline for OMP 17.3.5 and must not be synthesized into certified status.
  A certified rc.12 + OMP 17.3.5 identity requires a fresh trusted three-profile
  assessment; no rc.12 identity may be synthesized for another OMP version
  because its published peer is exact 17.3.5. Rollback ignores new records but
  does not delete them. Content-addressed evidence remains retained while
  referenced.

Observability and repair:
  CI reports missing, duplicate, conflicting, tag-drift, partial, stale-tarball,
  manifest/peer mismatch, historical-policy reinterpretation,
  wrong-loaded-runtime, tampered, unsigned, untrusted-workflow/ref/event,
  subject-mismatch and invalid-successor entries. Repair is a fresh target
  append or trusted CI run and ledger append, never hand-editing a passing
  result.

Required tests:
  Duplicate/conflicting target, tag movement after resolution, tarball or
  manifest mismatch, historical peer range after a future policy change,
  out-of-range profile suppression, out-of-order/tampered ledger, invalid
  signature, wrong issuer/workflow/ref/event, run/revision/subject mismatch,
  wrong loaded Runtime, partial-profile, failed-to-passed rerun,
  certified-to-revoked, revoked-to-recertified, same-tarball multi-host
  certification, candidate assessment hidden before catalog admission and
  visible only after matching Registry verification/target append.
```

## 16. Book Gate Plan

| Skill | 触发事实 | Gate state |
|---|---|---|
| `book-ddd-distilled-modeling` | 无业务领域边界变化 | `not-required` |
| `book-ddia-data-design` | 新增持久 target catalog、compatibility ledger/schema 和历史 peer-range 所有权 | `passed` |
| `book-legacy-change-safety` | 修改现有发布与兼容行为，回归风险高 | `planned` |
| `book-refactoring-pass` | 修改现有生产和发布代码 | `planned` |
| `book-release-readiness` | 修改 Plugin 发布、host integration 和兼容认证路径 | `planned` |

## 17. 文件影响

### 17.1 预计修改

- `plugins/omp-sbtd/package.json`
- `pnpm-lock.yaml`，只固定 dev floor
- `plugins/omp-sbtd/src/runtime/index.ts`
- 必要的 Plugin adapter edge
- `plugins/omp-sbtd/scripts/p0/release-validator.ts`
- `plugins/omp-sbtd/scripts/p0/cli.ts`
- authorized host adapter / RPC harness
- `plugins/omp-sbtd/validation/p0/compatibility.v2.json`
- `plugins/omp-sbtd/validation/p0/compatibility-targets.v1.json`
- `plugins/omp-sbtd/validation/p0/compatibility-ledger.v1.json`
- `plugins/omp-sbtd/validation/p0/compatibility-trust-policy.v1.json`
- `.github/workflows/omp-compatibility-certification.yml`
- `.github/workflows/omp-compatibility-ledger-validate.yml`
- `plugins/omp-sbtd/validation/p0/evidence/` content-addressed evidence/attestation bundles
- Plugin BDD 和测试
- `plugins/omp-sbtd/README.md`
- `plugins/omp-sbtd/CHANGELOG.md`
- `docs/assets/omp/omp-plugin-host-acceptance.md`
- `docs/assets/omp/omp-host-event-surface-beginner-guide.md`
- `.trellis/spec/backend/quality-guidelines.md`

### 17.2 不修改

- `packages/sbtd-workflow-kit`
- 上游 `640-skills`
- Workflow Kit vendor/generated/embedded 内容

当前 Workflow Kit 中没有 `17.2.9`、`currentRuntimeVersion`、Public OMP Support 或四命令发布策略耦合。本方案属于 Plugin release/host compatibility 基础设施，不属于 Onboard Skills 上游。

## 18. 验收标准

- [ ] 已发布 `0.1.0-rc.12` 的 Registry tarball/version、peer metadata 和历史证据保持不可变，且既有四命令结果不被自动升级为 `certified`；本次迁移不修改 dist-tag，但未来 `next` 正常移动不得改变已固定 target identity。
- [ ] Gate 0.1 已固定“四命令是所有 RC 的唯一 publication compatibility Gate”，BDD、发布手册、长期质量规范、validator 和 release behavior 不再引用 npm certification Gate。
- [ ] Gate 0.2 对 12 个 required Host events、实际 Runtime artifact identity、受信任 attestation 和受控 bot PR 写入路径输出 `feasible` 或 `blocked`；测试 job/bot 不可直写或绕过 branch protection。`blocked` 只阻止 Host Event `passed`、公开 `certified` 和受信矩阵更新，不阻止 widened candidate 或另行授权的四命令合规 RC。
- [ ] 新 target、re-certification 和 revocation bot PR 均须 required checks 通过及 1 名 release owner/maintainer 审批；具体账号/team 不硬编码。
- [ ] Bot validator 使用受信 `main` 的手工 `workflow_dispatch`；真实 dry run 证明固定 context `omp-compatibility-ledger-validate` 由独立 Status GitHub App 签发并绑定 immutable PR head SHA，GitHub Actions app 同名 status 不被接受，错误/过期 SHA 不成功，head 更新使旧 status 失效，failure/pending/missing 阻断合并。
- [ ] Status App 仅有 Metadata read + Commit statuses read/write，credential 只在独立 main-only、无 admin bypass 的 protected environment status steps 中可用；validator `GITHUB_TOKEN` 只读且不执行 PR head。PR-ref workflow、PR parser、child process、log、artifact 和 evidence 均无法读取 App key/token。
- [ ] 第三方 actions 固定 commit SHA；本任务不修改全仓 `allowed_actions=all`、`sha_pinning_required=false` 或 `enforce_admins=false`，这些保留为 residual risk。
- [ ] Gate 2.1 之前 package peer/dev 保持精确 `17.3.5`；Gate 2.1 只依赖 range/dev/lock、精确 tarball 四命令、文档和 rollback，不依赖 Host/CI/ledger。
- [ ] widened peer 只出现在新的、尚未发布的 Plugin candidate 中；本方案不预先指定其版本号。
- [ ] 新候选 Plugin peer 为 `>=17.3.5 <18`，dev dependency 和 lock 固定精确 `17.3.5`。
- [ ] Policy v2 不包含动态 current/latest/tested version 列表。
- [ ] target catalog 按 exact version、package integrity、tarball SHA-256、manifest SHA-256 和 tarball-bound peer range 选择不可变认证对象；tag 移动不得改变 target。
- [ ] Release validator 不再要求 peer range 等于 lock exact version。
- [ ] Runtime capability probe 按 `omp-extension-v1` 单一清单区分 required/optional，并对必需能力 fail closed。
- [ ] 四命令只认证 Command Surface，并作为所有 RC 的唯一 publication compatibility Gate；三个 profile outcome 不参与 npm 授权。
- [ ] 真实 Host Event integration suite 覆盖清单中的全部必需事件和 payload。
- [ ] 每个 matrix cell 使用全新 harness，并证明真实 Host 加载的 Runtime version/integrity 与目标 artifact 一致；故意装错 Runtime 时必须拒绝认证。
- [ ] 三个 evidence profile 分别绑定 scenario/command set、实际 tarball、tarball manifest/peer range 和 Runtime artifact digest。
- [ ] `out-of-range` 只从该精确 tarball 绑定的历史 peer range 派生，未来 Compatibility Policy 不得重新解释既有 assessment。
- [ ] Ledger entry 包含 attempt/successor、content-addressed evidence locator 和 RFC 8785 canonical hash 所需字段。
- [ ] 新 evidence/attestation bundle 与首次引用它的 assessment 在同一个受控 bot PR 写入仓库 content-addressed path；candidate PR 不含 published target/公开矩阵，post-publication admission PR 才包含 Registry proof、published target 和派生矩阵。引用 bundle 可重新取得并验证，不能仅依赖临时 CI artifact retention。
- [ ] Hash 只作为完整性证据，不作为执行者身份或真实性证明。
- [ ] candidate assessment 使用 `candidate-envelope` identity 并保持在公开 support matrix 之外；只有 Registry exact identity 复核和 published target catalog 追加完成后才可公开派生状态。
- [ ] 版本化 trust policy 固定 issuer、repository、workflow identity、受保护 source ref、允许 event 和签发/append 权限。
- [ ] Validator 拒绝 fork、PR head、非允许 workflow/ref/event 和 subject mismatch。
- [ ] `certified` 只能由三个 profile 全部通过、所有 profile evidence trust 验证成功且 assessment provenance 受信后派生。
- [ ] 每个 assessment provenance 有效的 CI run 都 append assessment，包括 partial/failed；failed scope 不能标成 passed。
- [ ] 本地、fork、手工或 assessment provenance 无效的 observation 不写公开 ledger、不改变 support matrix。
- [ ] overall state 按 3.2 固定优先级唯一派生，不产生 `unverified` 等未定义状态。
- [ ] Runtime capability 或 Host Event 仅缺 optional scope 时可产生带完整 reason code 的 `passed-with-diagnostics` 并按 pass 计数；required 缺失必须 failed。
- [ ] 受信任 append-only revocation 将当前状态派生为 `revoked`；恢复必须追加新的完整认证 successor。
- [ ] 新 OMP 17.x 认证只能复用已发布且 peer range 覆盖目标 Runtime 的 widened-peer Plugin tarball，不错误复用 exact-peer rc.12。
- [ ] 认证通过只更新 ledger/support matrix，不修改 Plugin version、tarball、SBOM、target identity 或 dist-tag。
- [ ] 认证失败仍保留受信任 assessment，但不会产生 `certified`、不会修改 Plugin，也不会自动重试 npm publish。
- [ ] 当前已发布 rc.12 只接受精确 OMP `17.3.5`；首个 `>=17.3.5 <18` tarball 对 OMP 18 始终 `out-of-range`。
- [ ] widening 到 OMP 18 必须产生 peer range 显式覆盖目标 OMP 18 exact version 的新候选 tarball；否则始终为 `out-of-range` 且不得运行 profile。其 RC 仍按精确 tarball 四命令合同另行发布，三 profile 独立决定能否公开为 `certified`。
- [ ] Registry target 选择显式绑定 exact version/package-integrity/tarball/manifest identity，不读取默认 `latest`，也不长期跟随可变 `next`。
- [ ] Plugin minimum/latest-in-range 三 profile matrix 全绿后才能完成兼容认证验收，但 matrix 结果不阻断满足四命令合同的 RC publication。
- [ ] Workflow Kit 和上游 Onboard Skills 保持不变。
