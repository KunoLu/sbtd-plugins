# OMP Plugin 与 OMP Runtime 版本解耦方案

## 1. 文档状态

- 状态：Proposed
- 目标 Plugin：`@kunolu/omp-sbtd`
- 当前计划中的最低 OMP Runtime：`17.3.5`
- 已确认 peer 策略：限定当前 major，使用 `>=17.3.5 <18`
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

禁止使用：

- `*`
- `latest`
- 无上限的 `>=17.3.5`
- 只依赖 `^17.3.5` 而没有 Host Contract 和真实宿主集成测试

### 3.2 安装、证据标签与公开状态分离

公开 overall state 只能按固定优先级唯一派生：

| 状态 | 定义 |
|---|---|
| `out-of-range` | OMP 版本不满足 peer range；优先级最高 |
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

因此同一个 Plugin tarball 可以独立取得：

```text
Plugin rc.11 + OMP 17.3.5 → certified
Plugin rc.11 + OMP 17.3.6 → certified
Plugin rc.11 + OMP 17.4.0 → certified
```

后两项只更新兼容证据，不产生新的 Plugin version 或 tarball。

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
  "pluginVersion": "0.1.0-rc.11",
  "pluginTarballSha256": "<sha256>",
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

`profiles[].outcome` 枚举为 `passed`、`passed-with-diagnostics`、`failed`、
`blocked`、`missing`；`passed-with-diagnostics` 仅允许 Runtime capability
或 Host Event profile 在 required scope 全部通过且只缺 optional scope 时使用。
`profiles[].evidenceTrust` 枚举为 `verified`、`missing`、`invalid`。
`blocked`/`missing` scope 的 `evidenceSha256` 与 `evidenceLocator` 为 `null`，
禁止伪造占位 digest。

`entrySha256` 的算法固定为：移除 `entrySha256` 字段后，按 RFC 8785
canonical JSON 序列化完整 entry，再计算 SHA-256。所有 `evidenceLocator` 和
`attestationBundleLocator` 必须指向仓库内 content-addressed、append-only
证据；只要 ledger 仍引用该内容，就不得按 CI artifact retention 自动删除。

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
- 允许事件：仅 `workflow_dispatch`、`schedule` 和 `registry_package`。
- 受保护 environment/job；只有该 job 拥有 attestation 签发和 ledger append 权限。

认证 runner 不执行 fork、PR head 或调用者可控的 workflow 定义。Validator
必须对签名、issuer、repository、workflow ref、source ref/revision、event、
run 和所有 subjects 做 allowlist/identity 校验；任一不符都不能派生
`certified`。

其他写入约束：

- Ledger append-only；不得原位把 failed 改成 passed。
- 每个 entry 绑定 Plugin tarball、OMP exact version、loaded Runtime identity、contract profile、scenario/command-set digest 和独立 evidence digests。
- `entrySha256`/`evidenceSha256` 负责完整性绑定，不作为执行者身份或真实性证明。
- fork、未受信 workflow、本地运行、手工文件和无法验证的 assessment provenance 只能生成独立的 `local-observation`，不得写入公开 ledger，也不得改变公开 overall state。
- 每次 assessment provenance 验证成功的 CI run 都必须 append assessment entry，包括 `incompatible` 和 `partially-verified`；support matrix 从最新有效 successor 唯一派生。
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

### 9.1 Plugin 发布时

对一个不可变候选 tarball 执行：

1. 使用精确 dev floor `17.3.5` build/typecheck。
2. 生成并冻结一个 tarball SHA-256。
3. 选择 Runtime matrix：
   - `minimum`：`17.3.5`
   - `latest-in-range`：Registry 当前最新 17.x
4. 对每个不同版本运行：
   - Runtime capability probe
   - Command Surface suite
   - Host Event Surface suite
5. 受信任 CI workflow 为 tarball、OMP version 和三个 evidence subjects 生成签名 artifact attestation，并为每个 profile 记录 `evidenceTrust`。
6. Validator 验证 assessment provenance；每个 provenance 有效的 run 都 append 受信任 assessment，并按 3.2 派生唯一状态。
7. minimum 和 latest 相同时只执行一次。
8. RC publication 只允许使用已经派生为 `certified` 的同一 tarball。

### 9.2 新 OMP 17.x 发布后

定时或 Registry-triggered job：

1. 查询最新 OMP 17.x 精确版本。
2. 查询当前已发布 Plugin tarball及其 Registry integrity。
3. 若 ledger 已有同一 tarball SHA + OMP version + contract profile 的完整、受信任结果，幂等跳过。
4. 在全新隔离 harness 中安装冻结的既有 Plugin tarball和目标 OMP exact Registry artifact。
5. 由真实 Host 证明实际加载 Runtime version/integrity 后，运行三个 profile。
6. 受信任 CI workflow 签发绑定 run、source revision、tarball、实际 OMP artifact 和三个 evidence digests 的 assessment provenance，并记录每个 profile 的 `evidenceTrust`。
7. assessment provenance 验证成功时，无论派生为 `eligible`、`partially-verified`、`incompatible` 或 `certified`，都 append assessment，并重新生成仓库侧 support matrix。
8. 任一已执行必需 profile 失败：派生 `incompatible`；没有 profile 通过时保持 `eligible`；至少一个通过但其余 missing/blocked，或任一 profile evidence trust missing/invalid：派生 `partially-verified`。所有非认证结果都创建兼容 issue。
9. assessment provenance 自身无法验证时，不写公开 ledger、不改变 support matrix，并创建基础设施事件。
10. 不修改 Plugin package version、tarball、SBOM 或 npm dist-tag。
11. 只有修复 Plugin 代码或改变 peer range 时才发布新 Plugin。

### 9.3 OMP 18+

现有 peer range 是 `>=17.3.5 <18`，因此现有已发布 tarball 对 OMP 18 始终为
`out-of-range`，不得绕过 §8 validator 运行兼容认证。扩展 major 的流程：

1. 在隔离分支准备新的、尚未发布的 Plugin candidate version 和 widened-peer policy。
2. 通过正常 review 将未发布 candidate/policy 原样合并到受保护 `main`；分支运行结果不能认证。
3. 受信任 main workflow 从该 clean commit 构建并冻结 candidate tarball digest。
4. 对该精确 candidate tarball和 OMP 18 exact artifact 运行三类 profile 与 attestation。
5. 全部派生为 `certified` 后，只发布该已认证的精确 digest。
6. 任一失败时不发布，先增加 Host adapter 或修复 Plugin；旧 tarball和旧 peer range 保持不变。

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

### 12.5 Package 与发布

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

实施必须在单独的干净 worktree/branch 上，从评审时确认并记录的基线 commit
开始。不得删除、reset、覆盖或隐式吸收当前工作区中的未提交修改；发现既有 WIP
时先保存并移交给其所有者。若 manifest 与 lock 不一致，在隔离 worktree 中先
确认目标 manifest，再用项目 package manager 重新生成 lockfile；禁止手工编辑
lockfile，也不在长期方案中硬编码一次性的本地 WIP 或基线 SHA。

### Slice 1：行为规格与 characterization

- 更新 BDD。
- 固化当前 exact-version validator、host adapter 和 runtime registration 行为。
- 先建立失败测试。

### Slice 2：Compatibility Policy v2

- 新增 `compatibility.v2.json`。
- peer range 与 dev pin 分离。
- 修改 release validator 和 CLI。
- 迁移所有调用者和测试。
- 删除 v1 manifest 和 exact-current 语义。

### Slice 3：Runtime Host Contract

- 深化 `src/runtime/index.ts`。
- 集中 capability assessment。
- 区分 required/optional capabilities。
- adapter edge schema validation。
- fail-closed/degraded diagnostics。

### Slice 4：Host Event integration suite

- 使用真实 OMP Host 和确定性本地 provider/model adapter。
- 触发必需 lifecycle/tool/approval/compaction 事件。
- 输出消毒、hash-bound evidence。

### Slice 5：Ledger、attestation 与矩阵 runner

- 实现 append-only ledger validator/writer。
- 实现三个 profile 的独立 evidence binding。
- 配置受信任 CI artifact attestation，并固定 issuer/repository/workflow trust policy。
- 实现签名、workflow identity、run、source revision 和 subject digest 验证。
- 实现 derived overall outcome。
- 实现 minimum/latest 和新 OMP 版本 job。

### Slice 6：发布政策和文档

- README
- `docs/assets/omp-plugin-host-acceptance.md`
- `.trellis/spec/backend/quality-guidelines.md`
- changelog
- package/release BDD 与测试

### Slice 7：完整验证和发布决策

- 运行项目验证。
- 对同一候选 tarball执行 minimum/latest 三 profile matrix。
- 运行独立 Release Readiness Review。
- 只有完整 `certified` evidence 才允许请求单独的 npm `next` 发布授权。

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
  KPi repository compatibility ledger owns exact Plugin-tarball + OMP-version
  certification and revocation records. The versioned trust policy owns the
  accepted CI issuer/workflow/ref/event boundary. Trusted CI attestation owns
  execution authenticity; package.json and README do not own exact certified
  versions.

Write / read / async / failure paths:
  Trusted CI installs the exact immutable artifacts, verifies the Runtime
  identity from the real Host process, executes the exact host suites, signs
  assessment provenance, then appends every trusted assessment, including
  partial and failed outcomes. Passing scopes remain attributable to that
  attempt; a failed scope is never rewritten as passed. Release tooling
  verifies the trust policy before reading the ledger; untrusted local
  observations never alter public state or the generated support matrix.

Consistency model:
  Monotonic append-only evidence and successor chains. Each profile binds the
  exact tarball digest, loaded OMP artifact, contract profile, scenario/command
  set and result digest. Hashes provide integrity; signed provenance and
  trust-policy verification provide execution authenticity. A valid revocation
  supersedes but never deletes historical certification.

Idempotency / ordering / retry / deduplication:
  Duplicate identity is a no-op. Explicit reruns create a new attempt linked
  to the preceding entry digest. Revocation and re-certification also append
  linked successors; no in-place outcome replacement.

Schema / migration / backfill / rollback / replay:
  Introduce ledger schema v1, trust policy v1 and compatibility policy v2.
  Canonical entry hashing uses RFC 8785 after removing entrySha256. Existing
  17.2.9 records remain historical; do not synthesize rc.11 support from old
  or unsigned evidence. Rollback ignores new ledger records but does not delete
  them. Content-addressed evidence remains retained while referenced.

Observability and repair:
  CI reports missing, duplicate, conflicting, partial, stale-tarball,
  wrong-loaded-runtime, tampered, unsigned, untrusted-workflow/ref/event,
  subject-mismatch and invalid-successor entries. Repair is a fresh trusted CI
  run and append, never hand-editing a passing result.

Required tests:
  Duplicate, out-of-order, tampered, invalid signature, wrong issuer/workflow/
  ref/event, run/revision/subject mismatch, wrong loaded Runtime,
  partial-profile, failed-to-passed rerun, certified-to-revoked,
  revoked-to-recertified, wrong tarball, out-of-range host and same-tarball
  multi-host certification.
```

## 16. Book Gate Plan

| Skill | 触发事实 | Gate state |
|---|---|---|
| `book-ddd-distilled-modeling` | 无业务领域边界变化 | `not-required` |
| `book-ddia-data-design` | 新增持久 compatibility ledger/schema | `passed` |
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
- `plugins/omp-sbtd/validation/p0/compatibility-ledger.v1.json`
- `plugins/omp-sbtd/validation/p0/compatibility-trust-policy.v1.json`
- `plugins/omp-sbtd/validation/p0/evidence/` content-addressed evidence/attestation bundles
- Plugin BDD 和测试
- `plugins/omp-sbtd/README.md`
- `plugins/omp-sbtd/CHANGELOG.md`
- `docs/assets/omp-plugin-host-acceptance.md`
- `.trellis/spec/backend/quality-guidelines.md`

### 17.2 不修改

- `packages/sbtd-workflow-kit`
- 上游 `640-skills`
- Workflow Kit vendor/generated/embedded 内容

当前 Workflow Kit 中没有 `17.2.9`、`currentRuntimeVersion`、Public OMP Support 或四命令发布策略耦合。本方案属于 Plugin release/host compatibility 基础设施，不属于 Onboard Skills 上游。

## 18. 验收标准

- [ ] Plugin peer 为 `>=17.3.5 <18`，dev dependency 和 lock 固定精确 `17.3.5`。
- [ ] Policy v2 不包含动态 current/latest/tested version 列表。
- [ ] Release validator 不再要求 peer range 等于 lock exact version。
- [ ] Runtime capability probe 按 `omp-extension-v1` 单一清单区分 required/optional，并对必需能力 fail closed。
- [ ] 四命令只认证 Command Surface。
- [ ] 真实 Host Event integration suite 覆盖清单中的全部必需事件和 payload。
- [ ] 每个 matrix cell 使用全新 harness，并证明真实 Host 加载的 Runtime version/integrity 与目标 artifact 一致；故意装错 Runtime 时必须拒绝认证。
- [ ] 三个 evidence profile 分别绑定 scenario/command set、实际 tarball和 Runtime artifact digest。
- [ ] Ledger entry 包含 attempt/successor、content-addressed evidence locator 和 RFC 8785 canonical hash 所需字段。
- [ ] 被 ledger 引用的 evidence/attestation bundle 可重新取得并验证，不能被临时 CI retention 删除。
- [ ] Hash 只作为完整性证据，不作为执行者身份或真实性证明。
- [ ] 版本化 trust policy 固定 issuer、repository、workflow identity、受保护 source ref、允许 event 和签发/append 权限。
- [ ] Validator 拒绝 fork、PR head、非允许 workflow/ref/event 和 subject mismatch。
- [ ] `certified` 只能由三个 profile 全部通过、所有 profile evidence trust 验证成功且 assessment provenance 受信后派生。
- [ ] 每个 assessment provenance 有效的 CI run 都 append assessment，包括 partial/failed；failed scope 不能标成 passed。
- [ ] 本地、fork、手工或 assessment provenance 无效的 observation 不写公开 ledger、不改变 support matrix。
- [ ] overall state 按 3.2 固定优先级唯一派生，不产生 `unverified` 等未定义状态。
- [ ] Runtime capability 或 Host Event 仅缺 optional scope 时可产生带完整 reason code 的 `passed-with-diagnostics` 并按 pass 计数；required 缺失必须 failed。
- [ ] 受信任 append-only revocation 将当前状态派生为 `revoked`；恢复必须追加新的完整认证 successor。
- [ ] 新 OMP 17.x 认证能复用已经发布的 Plugin tarball。
- [ ] 认证通过只更新 ledger/support matrix，不修改 Plugin version、tarball、SBOM 或 dist-tag。
- [ ] 认证失败仍保留受信任 assessment，但不会产生 `certified`、不会修改 Plugin，也不会自动重试 npm publish。
- [ ] 现有 `<18` tarball 对 OMP 18 始终 `out-of-range`；只有 widened-peer 的新候选 tarball认证通过后才能另行发布。
- [ ] Plugin minimum/latest-in-range matrix 全绿。
- [ ] Workflow Kit 和上游 Onboard Skills 保持不变。
