# OMP SBTD 上游提升与平台适配改造 PRD

## 1. 文档状态

| 项目 | 内容 |
|---|---|
| 状态 | Draft，待用户确认 |
| 编写日期 | 2026-07-29 |
| 规划源仓库 | `/Users/lusonglin/github/640-skills` |
| 规划目标仓库 | `/Users/lusonglin/github/KPi` |
| 上游模块 | `640-skills/sbtd-workflow-onboard` |
| Kit 模块 | `KPi/packages/sbtd-workflow-kit` |
| OMP Plugin 模块 | `KPi/plugins/omp-sbtd` |
| 实现状态 | 本文只记录方案；尚未开始 KPi 改造、上游提升、npm 发布或用户环境更新 |
| 配套文档 | [OMP SBTD 上游同步、发布与用户生效运行手册](../assets/omp-sbtd-upstream-sync-runbook.md) |

本文把前期评估形成的改造方案固化为可确认、可实现、可验收的技术 PRD。本文严格区分：

- **已核验现状**：当前源码已经存在且本轮重新读取确认的能力；
- **Proposed**：用户确认后才实现的能力；
- **未来运行流程**：改造完成后，维护者把新的 `640-skills/sbtd-workflow-onboard` 版本同步、构建、发布并让用户环境生效的标准流程。

未标注为“已核验现状”的命令、字段或状态，不得被解释为当前已经可用。

---

## 2. 背景与问题

`640-skills` 是 SBTD 全局规则、项目规则模板、Onboard 和 bundled Skills 的 canonical source。KPi 已经存在一条 OMP Plugin 供应链：

```text
640-skills/sbtd-workflow-onboard
  -> KPi/packages/sbtd-workflow-kit/vendor
  -> KPi/packages/sbtd-workflow-kit/generated
  -> KPi/plugins/omp-sbtd/kit
  -> @kunolu/omp-sbtd npm package
```

当前问题不是缺少 OMP Plugin，而是缺少一条安全、可审计、可重复的上游提升接口，同时现有 AGENTS section mapping 对混合 Codex/OMP 内容的表达能力不足。

### 2.1 已核验现状

| 事实 | 当前证据 | 结论 |
|---|---|---|
| KPi 已有 OMP Plugin | `plugins/omp-sbtd/package.json` 声明 `@kunolu/omp-sbtd` 和 `omp.extensions` | 不创建第二个 Plugin |
| KPi 已有内部 Kit 模块 | `packages/sbtd-workflow-kit/package.json` | 上游提升与转换归该模块负责 |
| Kit 当前锁定上游 revision | `upstream.lock.json` 的 `resolvedRevision` 为 `340f9dd4dc7a92e8b91c31e111de9a8de06cef36` | 当前制品可追溯，但提升入口仍缺失 |
| Kit 当前只有生成和漂移检查命令 | package scripts 只有 `generate`、`check-generated`，没有 `sync-upstream` | 上游提升目前不是一个公开、受控的深模块接口 |
| 当前 section map 只有 `owner` / `splitTargets` | `agents-section-map.yaml` 与 `sectionMapSchema` | 不能显式表达 omit 或 section-level overlay replacement |
| 未映射 section 会 fail closed | `KitError: SECTION_UNMAPPED` | 该安全属性必须保留 |
| 嵌套 section 必须与二级父标题使用相同 targets | `assignmentsFor()` | 混合平台内容无法在子 section 精细拆分 |
| Kit generation 已校验 vendor digest | `writeSnapshot()` 比对 `sourceTreeSha256` | 必须保留并扩展到 promotion 前置阶段 |
| Kit generation 已使用 staging + rename | `generateKit()` | 生成阶段已有原子替换与失败恢复基础 |
| Plugin build 从导出的 generated Manifest 嵌入 | `scripts/embed-kit.mjs` | Plugin 不得直接读取 vendor、mapping 或 Kit source |
| Plugin build 校验 asset 和 aggregate digest | `embed-kit.mjs` | 生成物完整性已有 fail-closed 基础 |
| Plugin 已通过 npm 安装 | `plugins/omp-sbtd/README.md` | 不需要在 `640-skills` 新建 marketplace 或安装器 |
| Python Onboard bridge 当前只运行 Plan | `src/onboard/python-bridge.ts` | Python Onboard 不得与 TypeScript Onboard 同时 Apply AGENTS |
| 当前 640 模板已区分 Codex / OMP 调度语义 | `AGENTS.global.md` 的“工具可用性判断 > Trellis 调度边界”、`AGENTS.project.md` 的“Trellis 调度层” | KPi 当前 mapping 必须显式接纳并转换这些新 section |

### 2.2 核心缺口

1. **没有安全的 upstream promotion seam**：更新 vendor、lock、digest、mapping 和 generated 需要分散操作，容易漏项或把临时文件带入 snapshot。
2. **平台适配表达力不足**：`owner` / `splitTargets` 只能决定整段去向，不能清晰表达 `include`、`omit`、`replace-with-overlay`。
3. **供应链阶段容易被混淆**：`plugins/omp-sbtd/kit` 更新不等于 npm 已发布，也不等于用户已安装版本和 Managed AGENTS 已更新。
4. **运行时契约可能漂移**：AGENTS、bundled Skills 或 `onboard.py` 变化后，Plugin 的 workflow classification、Book Gate、rule registry、Python bridge 和 environment observation 可能仍保留旧语义。
5. **发布与回滚证据分散**：缺少一个统一验收矩阵证明 source revision、generated manifest、embedded kit、npm tarball 和用户生效状态是同一条版本链。

---

## 3. 目标与非目标

### 3.1 目标

1. 在 `@kunolu/sbtd-workflow-kit` 中提供单一、可审计的上游提升接口。
2. 正式上游输入只接受已提交的 `640-skills` 完整 commit SHA。
3. 使用 tracked export 或受控 allowlist 构造 snapshot，不把工作树缓存和本地产物纳入 source digest。
4. 以 Plan/Apply 和 plan digest 防止待应用内容在确认后漂移。
5. 保留未映射 section、未知 mapping、digest mismatch、generated drift 的 fail-closed 行为。
6. 扩展 section adapter，使 OMP 输出能包含平台无关规则、保留必要的 OMP 禁止性说明，并省略可执行的 Codex-only 调度指令。
7. 保持 Kit -> Plugin 单向 build dependency；Plugin 只消费 exported generated Manifest。
8. 明确源码落地、npm 发布、用户升级、Managed AGENTS 更新是四个独立状态。
9. 为每个阶段提供可验证证据、失败处理和回滚路径。
10. 将相同输入产生字节级一致输出作为幂等性要求。

### 3.2 非目标

1. 不在 `640-skills` 中创建新的 OMP Plugin。
2. 不在 `640-skills` 中创建 OMP marketplace。
3. 不让 `sbtd-workflow-onboard` 直接安装或发布 `@kunolu/omp-sbtd`。
4. 不直接修改 `KPi/plugins/omp-sbtd/kit`。
5. 不让 Plugin 在运行时依赖内部 `@kunolu/sbtd-workflow-kit` 包。
6. 不让 Python Onboard Apply OMP AGENTS；TypeScript Onboard 继续拥有 OMP Managed AGENTS Apply。
7. 不把 Codex `dispatch_mode` 解释、默认值或 Inline fallback 引入 OMP runtime。
8. 不因任务复杂而自动启动 Trellis Channel。
9. 不自动执行 npm publish、dist-tag 切换或用户本机 Plugin 升级。
10. 不在本 PRD 阶段修改 KPi 或本机实际生效配置。

---

## 4. 术语与模块职责

| 术语 | 定义 |
|---|---|
| Canonical source | 已提交到 `640-skills` 的 `sbtd-workflow-onboard` 及其受控依赖内容 |
| Upstream promotion seam | 维护者以一个接口完成 source 校验、候选导出、Plan、Apply、lock 更新和转换预检的位置 |
| Kit module | `KPi/packages/sbtd-workflow-kit`；拥有 vendor、lock、mapping、overlay、generated 和 conformance checks |
| OMP adapter | 把平台无关 SBTD 规则转换为 OMP global/project AGENTS，并隔离 Codex-only 语义的实现 |
| Plugin module | `KPi/plugins/omp-sbtd`；拥有 OMP ExtensionAPI、Session 生命周期、命令、运行时规则和 read-only Kit snapshot |
| Source-integrated | KPi vendor、lock、generated、Plugin kit 已指向同一上游 revision，但 npm 未必已发布 |
| Published | 新 npm 版本和目标 dist-tag 已发布，但用户未必已升级 |
| Installed | 用户环境已安装新 Plugin 版本，但 Managed AGENTS 未必已更新 |
| Active | 新 Plugin、最新 Managed AGENTS 和新 Session 均已生效，`/sbtd doctor` 通过且 `/sbtd on` 可进入 `active` |

模块职责必须保持：

```text
640-skills
  owns: canonical SBTD rules, Onboard, bundled Skills

KPi/packages/sbtd-workflow-kit
  owns: upstream promotion, immutable source identity, transformation, manifest

KPi/plugins/omp-sbtd
  owns: OMP runtime adapter, Session lifecycle, packaged read-only Kit
```

---

## 5. 关键决策

### 5.1 决策一：复用现有 KPi Plugin 供应链

采用：

```text
640-skills -> sbtd-workflow-kit -> omp-sbtd
```

拒绝：

```text
640-skills -> 新建第二个 OMP Plugin / marketplace
```

原因：当前 `@kunolu/omp-sbtd` 已具备 ExtensionAPI、`/sbtd` 命令、Session hooks、Onboard、rule gates 和 npm 包结构。第二个 Plugin 会形成重复 ownership、重复发布和运行时冲突。

### 5.2 决策二：上游提升接口落在 Kit 模块

`packages/sbtd-workflow-kit` 已拥有 lock、vendor、mapping、generated 和 manifest。把提升接口放在这里能把复杂度隐藏在一个深模块后，调用者只需理解：

```text
source root + full commit SHA + mode(plan/apply)
```

而不需要分别操作 vendor、digest、lock、mapping 和 staging。

### 5.3 决策三：正式输入只接受已提交 revision

正式 Apply 必须满足：

- revision 是 40 位小写 Git SHA；
- source checkout 能证明该 commit；
- source working tree clean；
- 导出内容来自该 commit 的 tracked tree，而不是目录递归复制。

不提供 dirty Revision Set 的正式发布路径。一次性实验可在临时目录执行，但不得更新 KPi lock 或发布制品。

### 5.4 决策四：mapping 从“去向”升级为“适配动作”

现有 `owner` / `splitTargets` 只表达去向。目标 schema 必须能表达：

- `include`：按原文包含到一个或多个 target；
- `omit`：明确省略并记录理由；
- `replace-with-overlay`：使用审查过的 OMP 文本替换混合平台 section。

未知 section、未知 target、缺失 overlay、重复 source 和无理由 omit 都必须失败。

### 5.5 决策五：Plugin kit 仍是生成制品

`plugins/omp-sbtd/kit` 继续由 `scripts/embed-kit.mjs` 在 build 时重建。任何人工复制或修改均视为错误路径。

### 5.6 决策六：发布与用户生效保持显式分离

- KPi build 不自动 npm publish；
- npm publish 不自动修改用户 OMP 配置；
- Plugin upgrade 不自动覆盖用户 Managed AGENTS；
- Managed AGENTS Apply 后仍需新 Session 重新观测。

该分离能避免普通开发命令产生外部副作用。

---

## 6. 目标架构与状态流

```mermaid
flowchart LR
    A[640-skills committed SHA] --> B[sync-upstream Plan]
    B --> C{Plan ready?}
    C -- no --> D[repair mapping/overlay/input]
    D --> B
    C -- yes --> E[sync-upstream Apply]
    E --> F[Kit vendor + lock]
    F --> G[Kit generate/check]
    G --> H[Plugin runtime alignment]
    H --> I[Plugin build/embed]
    I --> J[tests/smoke/pack]
    J --> K[npm publish]
    K --> L[user plugin upgrade]
    L --> M[/sbtd onboard plan/init]
    M --> N[new session active]
```

状态机：

```text
upstream-ready
  -> planned
  -> source-integrated
  -> package-verified
  -> published
  -> installed
  -> managed
  -> active
```

任何阶段失败不得把后续状态报告为成功。

---

## 7. 功能需求

### FR-001：不可变上游身份

系统必须记录并校验：

```json
{
  "sourceId": "sbtd-workflow-kit-upstream",
  "canonicalSourceUri": "https://github.com/KunoLu/640-skills",
  "resolvedRevision": "<40-char-sha>",
  "sourceTreeSha256": "<64-char-sha256>"
}
```

验收：同一 revision 的 tracked export 必须得到同一 `sourceTreeSha256`；工作树临时文件不得改变该 digest。

### FR-002：Plan/Apply 接口

Proposed 命令：

```bash
pnpm --filter @kunolu/sbtd-workflow-kit sync-upstream -- \
  --source-root <absolute-640-skills-root> \
  --revision <full-sha> \
  --plan
```

Apply：

```bash
pnpm --filter @kunolu/sbtd-workflow-kit sync-upstream -- \
  --source-root <absolute-640-skills-root> \
  --revision <full-sha> \
  --apply <plan-digest>
```

约束：

- `sync-upstream` 当前尚不存在；实现后才可执行；
- Plan 必须零写入；
- Apply 必须重新计算输入并匹配 plan digest；
- Plan 后 source、mapping 或 overlay 变化时，旧 digest 必须失效；
- Apply 不接受交互过程中临时变更输入。

### FR-003：安全 source export

导出必须以 Git tracked tree 或等价受控 allowlist 为输入，至少排除：

```text
.git/
.trellis/
.gitnexus/
__pycache__/
.ruff_cache/
node_modules/
coverage/
test-results/
*.log
本地报告和临时 stage/backup
```

路径必须经过 containment 校验，拒绝：

- 绝对 target path；
- `..` 路径穿越；
- symlink 逃逸；
- 非 canonical source root；
- 导出过程中 source revision 变化。

### FR-004：候选预检与原子 Apply

Plan 必须在 staging candidate 上执行：

1. source export；
2. source tree digest；
3. lock candidate；
4. section parse；
5. mapping/overlay validation；
6. generated candidate；
7. manifest 和 license material validation。

Apply 仅在所有预检通过后原子替换：

```text
vendor/sbtd-workflow-kit-upstream/
upstream.lock.json
```

替换失败时必须恢复原 vendor 与 lock；恢复不完整时保留 backup 并返回其路径，禁止清理唯一 rollback 副本。

### FR-005：section adapter schema

Proposed schema 语义：

```yaml
schemaVersion: 2
sections:
  - source: "<source section key>"
    action: include
    targets: [global]

  - source: "<source section key>"
    action: omit
    reason: "Codex-only runtime dispatch instructions"

  - source: "<source section key>"
    action: replace-with-overlay
    targets: [project-omp]
    overlay: "overlays/sections/trellis-dispatch-omp.md"
```

必须满足：

- 每个 source section 恰好一条 assignment；
- `include` 至少有一个 target；
- `omit` 必须有非空 reason；
- `replace-with-overlay` 必须指定存在且受 package root containment 保护的文件；
- nested section 能独立适配，但不得产生重复标题、断裂层级或相互矛盾的父子内容；
- source 新增、删除、重命名均进入 sync report；
- schema v1 -> v2 使用一次性、可测试迁移，不保留双写解析路径。

### FR-006：OMP 平台语义

生成的 OMP AGENTS 必须保留：

- 当前项目 `.trellis/config.yaml`、`.trellis/workflow.md` 和 task artifacts 决定有效工作流；
- `trellis init --omp` 项目使用 OMP `task` worker 与生成 agent 定义；
- OMP 不读取、写入或推断 `codex.dispatch_mode`；
- Codex Inline fallback 不适用于 OMP；
- Channel 是独立、持久、多轮、可中断 runtime；
- 单个 OMP role worker 不触发 Channel；
- 同一职责只能由主会话、一个平台 role worker 或一个 Channel worker 执行。

生成的 OMP AGENTS 不得包含会让 OMP 执行的以下指令：

- 设置或解释 Codex `dispatch_mode=auto|inline`；
- 调度 Codex `trellis-implement` / `trellis-check` subagent；
- 把非法 Codex dispatch 值恢复为 Inline 的操作流程。

### FR-007：Kit manifest 和报告

`manifest.json` 必须继续包含：

- source identity；
- source tree digest；
- transform version；
- overlay digests；
- generated aggregate digest；
- target digests；
- profile catalog digest；
- 所有 assets digest。

`sync-report.json` 必须扩展为真实反映 promotion 差异，至少包含：

```json
{
  "sourceRevision": "<full-sha>",
  "previousRevision": "<full-sha>",
  "files": {
    "added": [],
    "changed": [],
    "removed": []
  },
  "sections": {
    "added": [],
    "changed": [],
    "removed": [],
    "omitted": [],
    "replaced": [],
    "unmapped": []
  },
  "inputReadSet": {
    "sourceTreeSha256": "<digest>",
    "mappingSha256": "<digest>",
    "overlayDigests": {}
  },
  "generatedSha256": "<digest>"
}
```

### FR-008：Plugin runtime 契约对齐

每次 promotion 必须按变更类型检查：

| 上游变化 | 必查 Plugin 位置 |
|---|---|
| `onboard.py plan --json` schema 或参数 | `src/onboard/python-bridge.ts` |
| Skill 新增、删除、重命名、required/optional 改变 | environment observation、capability skill registry |
| Workflow route 或 Book Gate 语义 | `src/workflow`、`src/gates`、`src/rules`、`src/state` |
| OMP/Trellis 调度规则 | classification、worker/Channel gate、session lifecycle |
| Managed AGENTS profile 或 target | `src/onboard`、agent discovery、doctor output |
| license 或 external assets | embed script、NOTICE、SBOM、pack tests |

Python bridge 必须继续只运行 non-AGENTS Plan；除非后续另有已确认 PRD，不得运行 Python Apply。

### FR-009：生成物嵌入

Plugin build 必须：

1. 运行 Kit `check-generated`；
2. 通过 package export 解析 generated Manifest；
3. 删除并重建 `plugins/omp-sbtd/kit`；
4. 校验 safe relative paths；
5. 校验所有 asset SHA-256；
6. 校验 aggregate digest；
7. 校验三个 AGENTS target 和 catalog digest；
8. 更新 Plugin license/NOTICE；
9. 生成 SBOM。

不得引入 sibling-relative Kit source lookup 或运行时 Kit package dependency。

### FR-010：发布与用户生效

发布必须使用新、未发布过的 npm version。npm 发布后仍需：

1. 用户升级或安装明确版本的 `@kunolu/omp-sbtd`；
2. 开启新 OMP Session；
3. 运行 `/sbtd doctor`；
4. 运行 `/sbtd onboard plan`；
5. 用户确认后运行 `/sbtd onboard init`；
6. 再次开启新 Session；
7. `/sbtd on` 进入 `active`。

### FR-011：幂等与恢复

- 相同 revision + mapping + overlays 连续 Plan 必须产生同一 plan digest；
- 相同输入连续 generation 必须字节级一致；
- 已应用的相同 revision 再次 Plan 应报告 no-op；
- Plan 失败不得修改 KPi；
- Apply 失败不得留下 vendor/lock 半完成状态；
- build 失败不得发布 tarball；
- publish 失败不得把用户状态报告为 installed/active。

---

## 8. 非功能需求

### 8.1 安全

- 不读取、打印或持久化 npm token、provider token、账号、PII 或生产数据；
- promotion 只读 source repository；
- 所有写入限定在 KPi Kit package root；
- backup 生命周期必须显式；
- tarball 不包含 `.env`、测试报告、缓存或本地路径信息。

### 8.2 可审计性

一次 promotion 必须能回答：

```text
来自哪个 640-skills commit？
导出了哪些 tracked files？
哪些 section 被 include/omit/replace？
生成的 manifest digest 是什么？
哪个 Plugin version 包含该 Kit？
npm 发布到哪个 dist-tag？
用户是否只升级了 Plugin，还是 Managed AGENTS 也已更新？
```

### 8.3 可维护性

- promotion 逻辑集中在一个模块，不把 digest、copy、lock 和 rollback 分散到 shell snippets；
- CLI wrapper 只负责参数解析和结果输出；
- interface 同时服务真实调用与测试；
- 不创建空的 future package 或重复 adapter。

### 8.4 兼容性

- 当前 Plugin peer dependency 仍以实际 `package.json` 为准；
- mapping schema 升级必须一次性迁移当前 map 并更新 tests；
- npm tarball 不可变；已发布版本不得覆盖；
- Trellis CLI 自身升级与 Plugin Kit 更新分开处理，项目生成资产需要时执行 `trellis update`。

---

## 9. Proposed 接口

### 9.1 package scripts

在 `packages/sbtd-workflow-kit/package.json` 增加：

```json
{
  "scripts": {
    "sync-upstream": "tsx src/sync-upstream.ts"
  }
}
```

### 9.2 模块接口

建议由一个深模块承担实现：

```ts
interface UpstreamPromotionRequest {
  sourceRoot: string;
  revision: string;
  mode: "plan" | "apply";
  planDigest?: string;
}

interface UpstreamPromotionResult {
  status: "ready" | "noop" | "applied" | "mapping-required" | "blocked";
  sourceRevision: string;
  previousRevision: string;
  sourceTreeSha256: string;
  planDigest: string;
  fileChanges: ChangeSet;
  sectionChanges: SectionChangeSet;
  backupPath?: string;
  reasons: string[];
}
```

CLI 不得自行实现 copy/digest/rollback；这些行为全部位于 promotion module 内部。

### 9.3 错误码

至少包含：

```text
SOURCE_ROOT_INVALID
SOURCE_REVISION_INVALID
SOURCE_REVISION_MISMATCH
SOURCE_WORKTREE_DIRTY
SOURCE_EXPORT_UNSAFE
SOURCE_CHANGED_DURING_PLAN
SOURCE_DIGEST_MISMATCH
PLAN_DIGEST_MISMATCH
SECTION_UNMAPPED
SECTION_MAPPING_UNKNOWN
SECTION_MAPPING_CONFLICT
SECTION_OVERLAY_INVALID
LICENSE_MATERIAL_INVALID
PROMOTION_APPLY_FAILED
PROMOTION_RECOVERY_INCOMPLETE
GENERATED_DRIFT
```

错误必须包含可操作的恢复说明，但不得泄漏 secret 或不受控绝对路径内容。

---

## 10. 计划修改范围

### 10.1 KPi Kit 模块

预计修改或新增：

```text
packages/sbtd-workflow-kit/package.json
packages/sbtd-workflow-kit/src/index.ts
packages/sbtd-workflow-kit/src/sync-upstream.ts              # Proposed CLI wrapper
packages/sbtd-workflow-kit/src/upstream-promotion.ts          # Proposed deep module
packages/sbtd-workflow-kit/agents-section-map.yaml
packages/sbtd-workflow-kit/overlays/**                        # 按 section 适配需要
packages/sbtd-workflow-kit/test/**
packages/sbtd-workflow-kit/vendor/**                          # Apply 生成
packages/sbtd-workflow-kit/upstream.lock.json                 # Apply 生成
packages/sbtd-workflow-kit/generated/**                       # generate 生成
```

最终文件拆分可根据现有 KPi 约定调整，但必须保留单一 promotion interface 和 CLI/implementation 分离。

### 10.2 KPi Plugin 模块

必查、按实际契约变化修改：

```text
plugins/omp-sbtd/src/onboard/python-bridge.ts
plugins/omp-sbtd/src/workflow/**
plugins/omp-sbtd/src/gates/**
plugins/omp-sbtd/src/rules/**
plugins/omp-sbtd/src/state/**
plugins/omp-sbtd/src/extension.ts
plugins/omp-sbtd/test/**
plugins/omp-sbtd/features/**
plugins/omp-sbtd/package.json
plugins/omp-sbtd/kit/**                                       # build 生成，不手改
plugins/omp-sbtd/SBOM.spdx.json                               # build 生成
plugins/omp-sbtd/THIRD_PARTY_NOTICES.md                       # build 生成
```

### 10.3 `640-skills`

本改造默认不修改 canonical source 的模块归属，也不增加 Plugin/marketplace。只有发现上游同一 section 内的平台无关规则本身互相矛盾时，才提出最小 source 修订并另行确认。

---

## 11. 实施阶段

### Phase 0：确认与安全门禁

1. 用户确认本 PRD 和配套运行手册；
2. 在 KPi 读取 `.trellis/workflow.md` 和当前 task artifacts；
3. 建立实现 task；
4. 对现有 Kit/Plugin 行为建立 characterization；
5. 运行实施前 Book Gate。

### Phase 1：Upstream promotion seam

1. 先写 Plan 零写入、dirty source 拒绝、tracked export 和 plan digest 测试；
2. 实现 promotion module；
3. 实现 CLI wrapper；
4. 实现 staging、atomic Apply、backup 和 recovery；
5. 验证相同输入幂等。

### Phase 2：Section adapter v2

1. 锁定 schema v1 当前行为；
2. 设计并迁移到 v2；
3. 实现 include/omit/replace-with-overlay；
4. 为 nested section、未知 key、缺失 overlay、重复 assignment 添加测试；
5. 更新 sync report。

### Phase 3：提升当前 `640-skills` commit

1. 将准备提升的工作树修改提交为完整 SHA；
2. 运行 Plan；
3. 处理新增 Trellis dispatch sections；
4. Apply vendor/lock；
5. generate/check-generated；
6. 审核三个 AGENTS targets。

### Phase 4：Plugin runtime alignment

1. 检查 Python Plan schema；
2. 检查 Skill/capability registry；
3. 检查 workflow/Book Gate/rule registry；
4. 检查 OMP worker 与 Channel 的单执行者规则；
5. 更新 BDD 和 runtime tests。

### Phase 5：Build、Pack 与发布验收

1. Plugin test/typecheck/lint/build/smoke；
2. Kit generated 与 Plugin kit 一致性检查；
3. KPi 全仓验证；
4. 版本提升、pack、tarball 内容检查；
5. 隔离 real-host OMP acceptance；
6. 人工 npm publish；
7. 用户升级和 Managed AGENTS 更新。

---

## 12. 实施前 Book Gate Plan

本表记录实施阶段预期门禁，不代表本轮文档任务已经执行这些 reviewer。

| Skill | 计划 | 客观触发事实 | 阶段 | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand | 当前问题是技术供应链和平台 Adapter，没有未决业务领域模型 | 需求或术语发生业务化变化时 | `not-required` |
| `book-ddia-data-design` | required | 修改持久化 vendor、lock、manifest、generated snapshot、恢复和跨仓数据流 | design 稳定后、实现前 | `planned` |
| `book-legacy-change-safety` | required | 修改现有 Kit generator、mapping、Plugin runtime 和发布链，存在隐藏兼容风险 | 首次行为修改前 | `planned` |
| `book-refactoring-pass` | required | 将修改现有生产代码 | legacy characterization 后、首次实现编辑前 | `planned` |
| `book-release-readiness` | required | 修改并发布生产路径 Plugin、外部 npm distribution 和 runtime behavior | 全部验证后、发布前 | `planned` |

此外：

- promotion module 和 mapping v2 采用 TDD；
- 用户可见 `/sbtd` 状态、Doctor、Onboard 和错误行为变化，在 KPi 中更新既有 BDD feature；
- 当前 `640-skills` 仓库不生成 `.feature` 文件。

---

## 13. 验收标准

### 13.1 Promotion

- [ ] 当前 package 中存在 `sync-upstream` script；
- [ ] Plan 零写入；
- [ ] Apply 要求匹配 plan digest；
- [ ] dirty source、非 full SHA、source/revision mismatch 均 blocked；
- [ ] tracked export 不包含 ignored/cache/report 文件；
- [ ] 同一输入 Plan digest 稳定；
- [ ] Apply 原子更新 vendor 和 lock；
- [ ] recovery 不完整时保留 backup 路径。

### 13.2 Mapping 与生成

- [ ] schema v2 支持 include/omit/replace-with-overlay；
- [ ] 未映射/未知/冲突/overlay 缺失均 fail closed；
- [ ] 新 Trellis dispatch sections 已明确适配；
- [ ] OMP targets 无可执行 Codex dispatch 指令；
- [ ] `sync-report.json` 真实记录 file/section 差异；
- [ ] `manifest.resolvedRevision` 等于提升的 `640-skills` SHA；
- [ ] 连续 generation 字节级一致；
- [ ] `check-generated` 通过。

### 13.3 Plugin

- [ ] Plugin 只从 exported generated Manifest 嵌入；
- [ ] `packages/.../generated` 与 `plugins/.../kit` 递归一致；
- [ ] Python bridge 仍只执行 Plan；
- [ ] AGENTS、Skill、workflow、gate、rule registry 语义一致；
- [ ] 单个 OMP role worker 不触发 Channel；
- [ ] 同一职责不存在双重 dispatch；
- [ ] test、typecheck、lint、build、smoke 全通过；
- [ ] tarball 包含 extension、manifest、Onboard runtime、license、NOTICE 和 SBOM。

### 13.4 发布与用户生效

- [ ] npm 使用新版本并发布到预期 dist-tag；
- [ ] registry tarball 与验收 tarball digest 一致；
- [ ] 用户已升级明确 Plugin version；
- [ ] 新 Session 能发现 Plugin；
- [ ] `/sbtd onboard plan` 显示新 Kit revision；
- [ ] `/sbtd onboard init` 后 Managed AGENTS 为 exact；
- [ ] 再次新 Session 后 `/sbtd doctor` 通过；
- [ ] `/sbtd on` 可进入 `active`。

---

## 14. 失败处理与回滚

| 失败点 | 必须结果 | 恢复动作 |
|---|---|---|
| source dirty 或 revision 不匹配 | Plan blocked，KPi 零写入 | 提交/清理 source 后重新 Plan |
| candidate 包含不安全路径 | Plan blocked | 修复 export/containment，不加绕过参数 |
| section unmapped | Plan 为 `mapping-required` | 更新 mapping/overlay 后重新 Plan |
| plan digest 失效 | Apply blocked | 重新 Plan 和人工复核 |
| vendor/lock Apply 失败 | 恢复旧 snapshot；必要时保留 backup | 修复失败原因后重新 Apply |
| generated drift | build blocked | 运行受控 generate 并审核差异 |
| Plugin runtime contract 不一致 | test/build blocked | 更新 bridge/gates/rules/tests |
| tarball 缺少 asset 或 digest 不一致 | 不发布 | 修复 build/pack 后生成新 tarball |
| npm publish 失败 | 不改变用户状态 | 修复认证/版本/dist-tag 后重试 |
| 已发布版本有缺陷 | 不覆盖原版本 | 发布新 patch/RC，必要时移动 dist-tag |
| 用户升级后 Onboard 未执行 | 状态保持 installed/preflight-only | `/sbtd onboard plan`、确认、init、重开 Session |
| 新 Managed AGENTS 有问题 | 回退到前一已发布 Plugin 并重新 Onboard | 保留 journal/backup，验证旧 revision 恢复 |

---

## 15. 待用户确认的实施边界

本 PRD 默认采用以下选择：

1. 上游提升接口命名为 `sync-upstream`；
2. 正式 Apply 只接受 clean、committed full SHA；
3. 使用 Plan/Apply 两阶段和 plan digest；
4. section map 升级为单一 schema v2，不长期保留 v1/v2 双解析；
5. 平台适配落在 KPi Kit mapping/overlay，不在 `640-skills` 复制 OMP 模板；
6. npm publish 和用户升级始终是人工、独立步骤；
7. Plugin kit 继续只由 build 生成；
8. Python Onboard 继续 Plan-only；
9. 本轮不创建 marketplace、不改变现有 Plugin 安装模型；
10. 实现工作在 KPi 中按其 Trellis workflow 建立任务后开始。

用户确认本文后，才进入 KPi 实现；确认前不执行 promotion、build、publish、Plugin upgrade 或本机 AGENTS Apply。
