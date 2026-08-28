# NeoX `omp-sbtd` 0.1.0-rc.6 内部引入 Code Review

评审日期：2026-08-09  
评审对象：npm 发布物 `@kunolu/omp-sbtd@0.1.0-rc.6`  
评审目的：判断是否适合在 NeoX 公司内推广  
评审结论：**CHANGES REQUIRED / 暂不批准全公司强制推广**

> 2026-08-14 复核说明：本文第 1–10 节保留为对 npm
> `@kunolu/omp-sbtd@0.1.0-rc.6` 发布物的历史评审记录。针对当前 KPi
> 工作树（`plugins/omp-sbtd/package.json` 版本为 `0.1.0-rc.10`）的变化，
> 以第 11 节为准；该复核不等于对 rc.10 npm 发布物或 CI provenance 的审核。

## 1. Executive Summary

该项目的工程治理意图是正确的，且在发布物完整性、Onboard 原子写入、事务恢复、路径与符号链接防护、规则状态持久化、显式安装确认等方面，明显高于一般个人插件水平。它解决的是“AI 编程缺少过程纪律和交付证据”的真实问题。

但是，当前 `0.1.0-rc.6` 不适合直接作为 NeoX 全公司统一强制流程。主要原因不是流程理念错误，而是：

1. 自动分类器不能可靠理解 NeoX 的日文和常用中文任务表达，导致该严格时不严格、该轻量时可能又过重。
2. Secret Read 审批字段连接错误，批准后仍无法通过对应门禁。
3. 发布包不包含测试代码，`package.json` 也没有公开源码仓库字段，无法从发布物完成覆盖率、CI 和源代码可追溯性审核。
4. BDD 完成判定只检查 `.feature` 文件修改时间，不能证明场景与本次代码变更相关或正确。
5. 流程模型偏 Web/移动端和 Trellis，对 NeoX 的 WPF、Windows Host/Viewer、OCR/算法、PHP/Laravel、Go 服务和现场设备项目缺少原生验证路径。
6. 强制门禁与公司现有 QA/Code Review 责任边界没有分开，可能让开发者或 AI 自己“记录 reviewer passed”，形成形式合规而非独立审核。

建议：**允许由测试经理负责，在 1–2 个非生产试点仓库中使用 advisory 模式；完成 P1 修复、测试与指标验证后，再决定是否推广。**

## 2. Scope 与限制

本次检查覆盖：

- npm 发布包内容、包元数据、SBOM、许可证和第三方声明
- 编译后 JavaScript 的静态审查
- workflow classifier、Book Gates、rule registry、session state、Onboard 事务和恢复逻辑
- 内置 AGENTS 规则及 26 个 Skill 的流程设计
- 针对 NeoX 日文/中文任务描述的分类器实测
- 与 NeoX 当前开发流程和主要技术栈的适配性

本次无法确认：

- 源码仓库中的单元测试数量、覆盖率和测试质量
- Git 提交历史、PR review 记录、分支保护和 CI 实际运行情况
- `0.1.0-rc.6` 构建是否可从公开源码完全复现
- 在真实 NeoX 项目中的 token、耗时、误阻断率和缺陷逃逸率

原因：npm 发布包没有包含测试目录；source map 没有 `sourcesContent`；`package.json` 没有 `repository`、`bugs`、`homepage` 或 commit provenance 字段。

## 3. Review Verdict

| 维度 | 评价 | 结论 |
|---|---|---|
| 工程理念 | 良好 | 值得保留 |
| 发布物完整性 | 较好 | 有 SBOM、hash、固定版本和第三方声明 |
| 安全设计 | 中上 | 有 fail-closed、路径和 symlink 防护，但存在审批字段缺陷 |
| 自动分类准确性 | 不合格 | 日文不支持，中文及英文大小写存在明显漏判 |
| NeoX 技术栈适配 | 不足 | Web/Mobile 较强，WPF/Windows/OCR/Go/PHP 不完整 |
| 测试可证明性 | 不合格 | 发布物不能证明测试覆盖与 CI |
| 流程效率 | 未证明 | 规则体量大，尚无 NeoX A/B 数据 |
| 公司治理适配 | 需修改 | AI 自记录门禁不能替代独立 Code Review/QA sign-off |
| 当前推广决定 | CHANGES REQUIRED | 仅允许受控试点，不允许默认 enforced 全员安装 |

## 4. Findings

### P1-01：Secret Read 的审批字段没有接通

位置：

- `dist/rules/index.js`：`secret-read-guard` 检查 `facts.secretReadApproved`
- `dist/extension.js`：`beforeToolCall` 只传入 `installApproved: true`

问题：

`tool_approval_resolved` 会把批准过的 tool call ID 放入 `approvedToolCallIds`，但随后无论批准的是什么类型，都只转换成 `installApproved`。`secretReadApproved` 从未传给规则引擎。

影响：

- Secret read 一旦被识别，将始终命中 hard block。
- 用户批准也不能解除。
- 容易造成开发者绕开插件、改用未识别的命令读取，反而降低安全性。

建议修复：

- 将批准类型与 tool call 事实绑定，分别传递 `installApproved` 和 `secretReadApproved`。
- 增加 allow/deny/approval-expired/replay 的单元测试。
- 更推荐默认不读取 secret 内容，只验证 secret reference 是否存在；确需读取时做一次性、路径绑定审批。

### P1-02：任务分类器不支持 NeoX 的日文工作语言

位置：`dist/workflow/index.js` 的 `hasExplicitChangeIntent()` 与 `classifyTaskPrompt()`。

实测：

| Prompt | 实际结果 | 期望 |
|---|---|---|
| `患者名が表示されない不具合を修正してください` | `UNCLASSIFIED` | `bugfix` |
| `既存のWPFコードで患者名が表示されないバグを修正してください` | `UNCLASSIFIED` | `bugfix` + existing production code |
| `修复患者姓名不显示的问题` | `small-direct-change` | 至少 `bugfix` |
| `请修复现有生产代码中的患者姓名显示缺陷` | `bugfix` | `bugfix` |
| `Review this code` | `UNCLASSIFIED` | `review` |
| `请代码审查` | `review` | `review` |

根因：

- 正则主要覆盖英文和简体中文，没有日文动词和缺陷术语。
- `review` 检测没有 `i` 标志，首字母大写即漏判。
- 中文“修复……问题”虽然识别为 change intent，但 `existingBehaviorBug` 只识别“缺陷/回归”等有限词汇。
- 自动分类主要依赖 prompt 起始词，而 NeoX 的工作指示常含背景、客户说明、引用、@成员和多段文字。

影响：

- 宣称的 TDD、Legacy Safety、BDD 和 Release Gate 可能根本不触发。
- 流程是否严格取决于员工如何措辞，而不是代码风险。
- 日文工单和客户问题在 NeoX 环境中属于主流程，不是边缘场景。

建议修复：

- 不要仅靠正则做 hard-gate 分类。
- 采用“结构化 classifier + deterministic evidence”两阶段：模型输出严格 schema，代码再结合 changed files、项目类型和风险规则校验。
- 至少建立日/中/英分类语料集，覆盖 NeoX 的实际 Jira/Teams/客户问题表达。
- 在 hard block 前显示分类事实并允许人工修正。
- 分类器准确率达到既定阈值前，保持 advisory。

### P1-03：发布包无法证明测试和构建可信度

证据：

- npm 包中没有 `test/` 或测试产物。
- source map 只记录源文件路径，没有嵌入源码。
- `package.json` 没有 `repository`、`bugs`、`homepage`。
- 包内 README 只说明可执行 `vitest run`，但发布物无法执行或审查这些测试。
- 当前版本为 `rc.6`，npm `latest` 仍指向 `rc.2`，`next` 才是 `rc.6`。

影响：

- 公司无法确认关键门禁是否有边界测试。
- 无法确认 npm tarball 与被 review 的 Git commit 一致。
- 测试经理自己开发、自己定义门禁、自己发布时，缺少独立复核链。

建议修复：

- 提供公司可访问的 Git 仓库和固定 commit/tag。
- CI 必须发布：unit test、integration test、coverage、lint、typecheck、npm pack smoke、Windows/macOS smoke、SBOM、provenance attestation。
- 将 tarball hash 与 GitHub/内部 Release 对应。
- Code owner 至少包含一名非作者研发 reviewer 和一名安全/平台 reviewer。

### P1-04：BDD 证据判定只看 mtime，可能造成假阳性和假阴性

位置：`dist/extension.js` 的 `hasFreshBddCoverage()`。

当前逻辑：只要 `features/` 下任意 `.feature` 文件的 mtime 晚于本轮任务开始时间，就认为 BDD covered。

问题：

- 任意无关 feature 被 touch，也可能通过。
- 既有 feature 已完整覆盖本次行为但无需修改，会被判定未覆盖。
- 没有关联 changed code、scenario、requirement、test runner 或执行结果。
- mtime 可被构建、解压、同步工具改变，不是可靠审计证据。

建议修复：

- 根据 Git diff 确认本次新增/修改的 feature。
- 建立 task/requirement → scenario → automated test → execution report 的可追溯关系。
- 允许“existing scenario reused”，但要求引用 scenario ID/路径和本轮测试结果。
- BDD 文档存在与 BDD 自动化通过必须分别建模。

### P1-05：门禁通过可由当前操作者直接记录，缺少独立审查身份

位置：`/sbtd gate start`、`/sbtd gate record` 与 `recordBookGateReview()`。

问题：

当前状态只记录 reviewer status，例如 `confirmed`、`proceed`、`ready`，但没有强制：

- reviewer 身份
- reviewer 与实现者不同
- 对应 PR/commit SHA
- review evidence/hash
- QA test run ID
- 审批时间与不可抵赖性

影响：

门禁可能退化成开发者或 AI 自己运行命令标记 passed。对于 NeoX 医疗相关生产软件，这不能替代正式 Code Review 或 QA sign-off。

建议修复：

- 将“Agent workflow gate”与“组织审批 gate”分开。
- AI 可以生成 review 建议，但生产合并必须由 Git PR branch protection、CODEOWNERS 和 CI 控制。
- Release Ready 必须引用不可变 commit SHA、CI run、测试报告和责任人。

### P2-01：Mutation 工具分类过宽，会阻断无副作用诊断

位置：`dist/extension.js` 的 `isMutationOrPhaseAdvancingTool()`。

除 `read/grep/glob/lsp` 外，所有工具都被视为 mutation/phase advancing。这样会把以下潜在只读工具一并视为变更：

- 只读 bash 命令
- web search
- image inspection
- debugger 观察操作
- ask/todo 等协调工具

在 `preflight-only` 或 `blocked` 状态下，这些工具可能全部被阻止，影响故障恢复。

建议：建立明确工具能力表：`read-only`、`workspace-write`、`external-write`、`destructive`、`phase-transition`，未知工具再 fail-closed。

### P2-02：依赖安装识别可被常见 shell 形式绕过

位置：`isDependencyInstall()`。

当前基于正则识别 npm/pnpm/bun/yarn/pip/brew/cargo。它不能可靠覆盖：

- `cd x && npm install`
- shell variable、alias、function、wrapper script
- PowerShell 形式
- `dotnet add package`、NuGet、Chocolatey、Winget
- Composer（NeoX PHP/Laravel）
- Go module 变化

这与其他用到的 Windows/.NET、PHP 和 Go 技术栈不匹配。

建议：优先使用 OMP 工具结构化元数据或 sandbox permission，而不是解析 shell 字符串。

### P2-03：Secret path 检测覆盖不完整且存在误判/漏判

当前主要识别 `.env`、`.ssh`、`id_rsa/ecdsa/ed25519`、`.pem/.key`。

未覆盖示例：

- Windows Credential Manager、DPAPI 相关文件
- `appsettings.*.json`、user-secrets
- npmrc、pypirc、NuGet.Config、composer auth.json
- kubeconfig、cloud credentials
- `.p12/.pfx`、数据库连接配置

同时，路径和 shell 命令用正则解析，面对转义、变量、PowerShell 和脚本语言不可靠。

建议：将 secret protection 下沉到文件访问/sandbox 层，并建立 secret inventory。

### P2-04：流程与 NeoX 技术栈不对称

内置流程重点支持：

- React/shadcn/UI
- Playwright Web E2E
- Maestro Mobile E2E
- SEO/GEO
- Trellis/GitNexus

NeoX 的核心生产路径还包括：

- WPF/C#/.NET 与 Windows installer/MSI
- Host/Viewer/Relay 桌面远程协助
- OCR/OpenCV 和识别模型回归
- 药名、用法、NSIPS/JAHIS 等匹配算法
- PHP/Laravel、MongoDB、Go 服务
- 扫描仪、打印机、Android USB、路由器与药局现场设备

当前没有与这些核心路径对等的强制验证模板。例如：

- WPF UI 自动化/桌面回归
- Windows 多版本与权限/UAC测试
- MSI 安装、升级、卸载、回滚
- OCR golden dataset 与精度阈值
- 匹配算法 benchmark、误匹配/漏匹配分析
- NSIPS/JAHIS fixture、周次回放和一致率回归
- 弱网、断线重连、输入注入、IME 和多显示器验证

因此原样推广会出现“Web 流程非常详细，但公司最关键业务缺少对应门禁”的结构性偏差。

### P2-05：规则体量与 token/等待成本没有 A/B 数据

发布包包含：

- 178 个 Onboard runtime 文件
- 26 个 Skill
- 三份主要 AGENTS 规则合计 893 行、约 103 KB

这能证明治理规则体量很大，但不能单凭文件大小证明每次请求增加多少 token。公司推广前应实测：

- input/output token
- wall-clock time
- tool call 数
- 人工确认次数
- blocked/retry 次数
- 缺陷发现率
- PR lead time

没有这些数据，不应宣称该插件提升效率。

### P2-06：精确绑定 OMP 17.2.9，升级维护成本高

peer dependency 精确等于 `17.2.9`。优点是可复现，缺点是：

- OMP 安全修复或 API 升级会阻塞插件用户升级。
- 公司需要同时维护 OMP 和插件兼容矩阵。
- `rc` 期间频繁升级会增加终端环境差异。

建议定义支持窗口和自动兼容测试，而不是长期依赖单一精确版本。

### P2-07：公司内部使用 GPL 需要法务确认分发边界

发布包声明 `GPL-3.0-only`。纯公司内部使用通常与对外分发不同，但如果未来把修改版交付客户、合作伙伴、设备供应商或随产品安装包分发，需要法务确认源码义务和组合边界。

这不是当前代码缺陷，但属于正式推广前的合规事项。

### P3-01：包元数据和文档不满足平台产品标准

缺少：

- repository/bugs/homepage
- SECURITY.md 或漏洞报告渠道
- changelog/migration guide
- support owner/SLA
- compatibility matrix
- uninstall/rollback 用户文档
- telemetry/data handling 明示

## 5. 做得好的部分

以下设计建议保留：

1. 固定 OMP 与插件版本，降低不可复现升级。
2. npm 包有 integrity/signature、SBOM、第三方 notice 和固定上游 commit。
3. Onboard 安装需要明确确认，不在 plugin install 时静默改项目。
4. Onboard 使用临时文件、fsync、rename、transaction journal 和 rollback，考虑了中断恢复。
5. 对写入目标做 allowed-root 和 symlink 检查，降低路径逃逸风险。
6. session state 使用严格 Zod schema，非法最新状态采取 fail-closed。
7. 安装依赖、secret read、release readiness、BDD evidence 等风险点有明确治理意识。
8. 将 advisory/enforced、strict/relaxed 分开，具备渐进推广的基础。
9. 不把 mock-backed 测试冒充 full-stack E2E，方向正确。
10. 强调实际 diff、测试结果和项目事实优先于通用规则，符合 NeoX 的实践需要。

## 6. 与 NeoX 当前流程的适配判断

NeoX 当前推荐流程可概括为：

```text
需求/客户问题
→ ChatGPT/负责人澄清需求
→ Architecture.md / 方案 / 规格
→ Codex 实现
→ 自动测试与项目验证
→ 人工 Code Review
→ QA/测试经理验收
→ 发布
```

SBTD 与这一流程在方向上兼容，但角色边界需要调整：

| NeoX 阶段 | SBTD 可保留 | 需要修改 |
|---|---|---|
| 需求澄清 | `grill-with-docs`、`to-spec` | 仅中大型/高风险需求触发；小修复不要强制 PRD |
| 架构设计 | DDD/DDIA review | 只在领域边界、数据模型、跨服务变化时触发 |
| 实现 | TDD、legacy safety、impact analysis | 增加 WPF/OCR/算法/PHP/Go 专用 route |
| 行为定义 | Gherkin BDD | 客户可见关键行为使用；不要要求所有 UI 小改都新建 feature |
| Code Review | review route | 必须由独立 reviewer/PR 体系完成，不能由当前 Agent 自记录 passed |
| QA | formal evidence | 接入 NeoX 测试报告、fixture、精度与一致率数据，不局限于 Playwright/Maestro |
| 发布 | release readiness | 绑定 commit SHA、CI run、release owner 和 rollback plan |

## 7. 推荐的 NeoX 版分级流程

### Level 0：Direct

适用：文案、注释、简单样式、低风险配置、明确且局部的小修改。

要求：

- 明确 diff
- 聚焦测试或构建
- 人工 review 按仓库既有规则

不强制：PRD、DDD、BDD、Trellis。

### Level 1：Standard Change

适用：普通 bug、小功能、现有 WPF/PHP/Go 模块修改。

要求：

- 根因说明
- 回归测试
- 影响范围检查
- PR Code Review
- QA 按风险抽测

BDD 仅在用户可见行为需要长期固化时使用。

### Level 2：High Risk

适用：药品/用法匹配算法、NSIPS/JAHIS、OCR精度、权限、远程输入、数据迁移、跨服务接口。

要求：

- 需求/规格确认
- 数据或领域设计 review
- golden dataset/fixture/回放测试
- 独立 Code Review
- QA sign-off
- 回滚与监控计划

### Level 3：Release Critical

适用：大客户上线、数据库迁移、核心识别模型替换、安装包升级、远程协助生产链路变化。

要求：

- Level 2 全部内容
- 固定 commit/build artifact
- 完整测试证据
- 发布负责人批准
- 灰度、监控、回滚和客户通知计划

## 8. 推广前必须完成的验收条件

### 必须完成（P1）

1. 修复 `secretReadApproved` 字段连接。
2. 建立日/中/英分类器测试集，覆盖至少 100 条 NeoX 真实脱敏任务。
3. 解决日文漏判、中文普通表达漏判和英文大小写问题。
4. 将 BDD evidence 从 mtime 改为可追溯证据。
5. 开放或提供公司可审计源码、测试、CI 和构建 provenance。
6. 组织 gate 与 Agent gate 分离，生产审批绑定真实 reviewer 和 CI evidence。
7. 增加 WPF、Windows、OCR/算法、PHP、Go 的 NeoX routes 与验证策略。

### 试点期间必须量化

1. 分类 precision/recall，尤其是 high-risk 漏判率。
2. 每任务 token 和耗时相对基线的变化。
3. 误阻断率、人工 override 次数和失败恢复时间。
4. PR lead time、返工次数和缺陷发现阶段。
5. QA 缺陷逃逸率是否下降。
6. 开发人员满意度和流程跳过原因。

### 建议推广阈值

- High-risk 漏判率：0；无法判定时必须人工确认。
- 普通任务错误 hard-block：低于 5%。
- P1/P2 自动测试全部通过，关键模块覆盖率目标由团队明确，建议不低于 80%，门禁/恢复/审批路径接近 100%。
- 试点项目不得出现因插件导致的代码丢失、错误发布或 secret 泄露。
- 相比基线，缺陷发现收益能够解释增加的时间和 token 成本。

## 9. 建议实施计划

### Phase A：两周修复与基线建立

- 修复 P1 findings。
- 建立真实脱敏 prompt corpus 和 classifier regression tests。
- 补齐公开/内部仓库、CI、coverage、release provenance。
- 定义 NeoX Level 0–3 风险模型。

### Phase B：两到四周受控试点

- 选择一个 WPF 项目和一个后端/算法项目。
- 默认 advisory，不允许插件阻止正式开发。
- 同类任务做普通 OMP 与 SBTD A/B 对比。
- 每周由开发负责人和测试经理共同复盘误判、漏判和流程成本。

### Phase C：有限 enforced

- 只对 Level 2/3 启用 hard gates。
- Level 0/1 保持现有仓库流程或 advisory。
- 组织审批继续由 Git/CI/QA 系统执行。

### Phase D：公司推广评审

- 根据指标决定推广、继续试点或终止。
- 不以“已安装人数”作为成功指标，以缺陷、交付时间和审计证据衡量。

## 10. 最终意见

`omp-sbtd` 是一个有价值的内部工程平台原型，作者对 AI 开发中的安全、流程漂移、证据不足和恢复问题做了认真设计。它值得继续投入，也适合由测试经理牵头试点。

但 `0.1.0-rc.6` 当前属于“治理框架原型”，还不是可直接全公司 enforced 的成熟平台。NeoX 最合理的路径不是否定它，也不是原样推广，而是：

> 保留其门禁、证据和恢复思想，将自动分类、组织审批、NeoX 技术栈验证和分级流程重新设计；先 advisory 试点，用数据证明效果后，仅对高风险开发启用强制门禁。


## 11. 2026-08-14 当前仓库复核

### 11.1 复核边界

本节将当前 KPi 工作树中的源码、测试、包元数据、验证资产和 Kit
投影规则与上述 rc.6 结论对照。原 rc.6 发布物的历史事实不回写或删除；
当前仓库存在的文件也不能反向证明当时的 npm tarball 已包含这些内容。

当前事实：

- `plugins/omp-sbtd/package.json` 的版本已为 `0.1.0-rc.10`。
- 当前仓库已有完整 Plugin 源码、27 个 `*.test.ts` 测试文件、P0
  conformance/release/value-study 资产和包发布测试。
- npm 包的 `files` 仍不包含测试；包元数据仍没有
  `repository`、`bugs`、`homepage`；仓库中未发现 CI workflow。
- GitNexus 当前索引刷新因 FTS 索引不一致失败，因此本节以当前源码、测试和
  文档直接检查及分类器实跑为准，图分析只作 advisory，不作为结论依据。

### 11.2 Finding 状态调整

| Finding | 当前状态 | 调整说明 |
|---|---|---|
| P1-01 | **仍成立** | `plugins/omp-sbtd/src/extension.ts:2598-2612` 仍把任意已批准 tool call 只映射为 `installApproved`，没有传递 `secretReadApproved`；审批在 `toolResult` 后删除，但风险类型和输入未绑定。 |
| P1-02 | **仍成立，已有部分缓解** | `src/workflow/index.ts:163-168,219,230-232` 仍不识别日文 bug 指令、普通中文“修复…问题”和大写 `Review`。对原六条 prompt 的当前实跑结果与 rc.6 表格一致。当前 `/sbtd status` 会显示分类理由，且 `/sbtd route` 可人工覆盖，所以“显示事实并允许修正”已部分具备。 |
| P1-03 | **部分成立** | 当前仓库已可审查源码、测试、P0 conformance/release validator 和发布脚本，不能继续表述为“当前仓库无测试可审查”；但发布包仍排除 test/features/validation，source map 未内嵌源码，包元数据仍无公开源码链接，仓库没有 CI/npm provenance，SBOM 也未把 Plugin tarball 绑定到自身 Git commit。`latest→rc.2` 只能保留为 2026-08-09 的历史 Registry 观察；当前仓库只能证明 RC 不发布到 `latest` 的新政策。 |
| P1-04 | **仍成立** | `src/extension.ts:951-968,2703-2707` 仍以 `.feature` mtime 判定本轮 BDD coverage。当前 Kit 已有 `validation-evidence.schema.json` 的 `featureSources` 与 `reports` 契约，但 Plugin 尚未消费它来建立可追溯关系。 |
| P1-05 | **仍成立；Release Readiness 不是反例** | 除 Release Readiness 外，Book Gate 仍只持久化 `reviewerStatus`/字符串 evidence，`/sbtd gate record` 可由当前操作者确认；没有 reviewer identity、实现者隔离、PR/commit、CI run 或不可抵赖审批。Release Readiness 的纯函数虽要求 `validationVerified`，但当前命令/state 接线没有传入该事实，不能视为已实现的组织证据加强。 |
| P1-06（新增） | **当前 P1 wiring 缺陷** | `src/gates/index.ts:260-278` 要求 `release-readiness ready` 必须有 `validationVerified=true`，但 `src/state/index.ts:528-538` 调用时永远使用默认 `false`；`/sbtd gate record release-readiness ready` 因而无法通过。现有 session-stop 观察还把“报告存在但结果未观察”记录为 blocked，没有可达的成功接线路径。 |
| P2-01 | **仍成立，并发现额外边界问题** | `src/extension.ts:839-843` 仍使用负面名单：除 `read/grep/glob/lsp` 外全部视为 mutation/phase advancing。OMP 17.2.9 内部已有 `read/write/exec` ToolTier，但 `tool_call` extension event 不暴露 tier，因此当前只能使用 Plugin-local capability table 或推动 OMP contract 变更。另有两个边界：SSH `read` 在 OMP 属 `exec` tier，却会被 Plugin 当作安全 read；缺少 `toolName` 的 malformed event 当前返回非 mutation，不是 fail-closed。 |
| P2-02 | **仍成立，但原评审含一个错误示例** | 当前正则从 rc.6 起就能识别 command segment，因此 `cd x && npm install` 不是有效绕过示例，必须从证据列表删除；PowerShell、变量/alias/function/wrapper、`.NET/NuGet/Chocolatey/Winget`、Composer 和 Go module mutation 仍未完整覆盖。新增确认的绕过还包括换行/前导空白、`npm i`/`npm ci`/bare `yarn`、`python -m pip install`、`npx`/`bunx`。OMP 的 shell tokenizer/approval parser 未暴露给 extension event。 |
| P2-03 | **仍成立，且 sandbox 下沉当前不可达** | `src/extension.ts:889-904` 的 secret inventory 和 shell/path 正则范围与 rc.6 结论基本一致；还缺 `.envrc/.netrc/.git-credentials`、Docker/cloud/Kubernetes、`.pgpass/.my.cnf`、包管理器凭据和 `.p12/.pfx`。`Get-Content`/`type`、`dd`/`base64`/`openssl`、`git show HEAD:.env` 等可绕过，公钥/文档搜索也可能误报。OMP 17.2.9 的 extension contract 没有文件访问 sandbox hook，因此“下沉到 sandbox 层”需要 OMP 能力扩展，不能作为当前 Plugin-only 修复承诺；审批死路同时依赖 P1-01。 |
| P2-04 | **核心仍成立，需修正绝对措辞** | 当前 `project-validation` 已提供通用 Go 命令，`ui-ux-pro-max` 有 WPF/Laravel UI 设计资料，因此不能再写成这些栈“完全没有任何支持”；但 classifier 的 `changedProductionPath` 仍只识别 JS/TS，且 route/Skill 集合没有与 Web/Mobile 对等的 .NET/WPF 桌面回归、MSI/UAC、PHP 后端、OCR/匹配算法、NSIPS/JAHIS 和现场设备验证路径。结构性不对称结论仍成立。 |
| P2-05 | **仍成立，新增基础设施不是效率证据** | 893 行/约 103 KB 和 26 Skills 的数字仍成立；Onboard runtime 文件当前为 179，不再是 178。仓库虽新增 value-study/conformance corpus、fixtures、authorized harness 和 release validator，但它们度量分类/route 正确性与契约完成度，不是 token、wall-clock、误阻断、PR lead time 或缺陷逃逸的 A/B 数据。 |
| P2-06 | **部分成立** | `plugins/omp-sbtd/package.json` 仍精确绑定 `@oh-my-pi/pi-coding-agent` `17.2.9`，升级耦合仍在；但当前质量规范已明确 `17.2.9=supported`、其他版本 `unverified`，扩大声明需为每个目标版本构建新 tarball 并完成四命令验收。仍缺时间支持窗口和自动多版本兼容 CI/matrix。 |
| P2-07 | **治理项，结论不变** | 当前 Plugin 和仓库仍为 `GPL-3.0-only`；对外分发边界继续需要法务决定。 |
| P3-01 | **部分成立，缺口收窄** | Plugin README 已说明精确 OMP 版本、平台支持和 RC 不使用 `latest`；仓库内 host acceptance 文档已有卸载、失败、回退与清理步骤，但该文档不随 npm tarball 发布，随包 README 也未提供卸载段落。仍缺 package `repository/bugs/homepage`、安全报告渠道、Plugin 自有 changelog/migration、support owner/SLA，以及 telemetry/data-handling 明示。 |

### 11.3 当前建议实施范围

本轮最终确认实施范围为 P1-01、P1-02、P1-04、P1-06、
P2-01、P2-02、P2-03、P3-01 八项，并作以下范围校正：

1. **P1-01**：审批必须绑定 `toolCallId + risk class + normalized input
   fingerprint`，一次性消费；install approval 与 secret-read approval
   不得互换。
2. **P1-02**：先做确定性的日/中/英归一化、语料回归和 changed-path
   evidence；保留 `/sbtd route` 人工覆盖。模型 classifier 只能先在 advisory
   评估，不作为 hard gate 的单一事实源。
3. **P1-04**：复用当前 Kit 的 validation evidence v1
   `featureSources + reports`，分别记录 scenario 可追溯性与执行证据；不要求
   新增 Feature/Scenario ID。
4. **P1-06（新增）**：由 state service 根据已持久化且当前 revision
   匹配的 validation evidence 派生 `validationVerified`，不得让命令调用者传入
   可伪造布尔值；补齐 blocked/failed/stale/tampered/valid evidence 的端到端
   Gate 测试。
5. **P2-01**：建立显式 tool capability registry，至少区分 local read、
   external read、workspace write、external write、destructive、
   phase transition 和 unknown。
6. **P2-02**：从计划中删除 `cd x && npm install` 修复项；聚焦结构化
   application/argv metadata、PowerShell、.NET/NuGet、Composer、Go 和
   动态 wrapper 的剩余缺口。纯 shell 文本无法完全证明 wrapper 行为，必须
   保留 sandbox/host capability 限制说明。
7. **P2-03**：扩展高置信 secret inventory、路径归一化和 Windows
   分隔符支持；`appsettings.*.json` 等混合配置应可配置，避免全量硬阻断。
8. **P3-01**：只补当前仍缺的产品元数据、Security、Plugin changelog/
   migration、support/SLA、telemetry/data handling，并在随包 README 提供
   可执行的卸载/回退摘要及现有完整 host acceptance 文档链接。

P1-06 已由用户明确加入本轮范围。以下问题仍不纳入本轮八项计划，也不得因
八项完成而宣称原公司推广 verdict 已解除：

- P1-03：可审计 CI/build/release provenance；
- P1-05：独立 Code Review/QA 身份和不可变 evidence；
- P2-04：NeoX 的 .NET/WPF/PHP/OCR/设备专项验证；
- P2-05：真实 NeoX 试点数据与阈值；
- P2-06：OMP 版本支持窗口与自动多版本兼容矩阵；
- P2-07：法务分发结论。

### 11.4 `packages/sbtd-workflow-kit` 与上游 Onboard Skills

八项中只有 **P1-04** 需要上游 Onboard 同步；其余七项保持 Plugin-only：

- P1-01、P1-02、P1-06、P2-01、P2-02、P2-03 属于
  `plugins/omp-sbtd/src/**` 的 OMP host/runtime 适配逻辑。
- P3-01 属于 Plugin `package.json`、README 和 KPi 产品发布文档。
- P1-04 当前使用的 validation evidence v1 只有并列的 `featureSources[]` 与
  `reports[]`，没有机器可验证的 scenario/source-locator → report/test-case
  关联。仅要求它们出现在同一 envelope 仍可让无关场景和报告共同通过，不能完整
  修复 mtime-only finding；在 Plugin 内另造 mapping 又会形成第二事实源。

P1-04 的推荐同步方案是：在 canonical `640-skills` 的
`project-validation` 中保留 v1，并新增具有显式 scenario-report link 的 v2
schema、contract、Skill 指引、versioned machine-readable report/binding profile、
确定性语义 validator 和共享 fixtures。JSON Schema 只能校验字段形状，不能单独
保证跨数组引用、locator digest、报告文件 SHA 或 test case binding。validator
必须从 SHA-verified JUnit XML/Playwright JSON report bytes 中提取唯一 passed case，
并要求该 case 内嵌的 `sourceLocatorDigest` property/annotation 等于重算 locator；
sidecar label、真实但绑定其他 scenario 的 passed case、unsupported report 均不得
通过。同步更新直接产生该类证据的 `maestro-mobile-e2e` 指引；若其 JUnit 输出无法
携带所需 binding，则 scenario-backed v2 evidence 应标记 blocked，不得伪造 link。
`knowledge-base-integration` 当前 report-only smoke 继续产出 v1，并增加兼容性
断言，不能据此满足 BDD traceability；`gherkin-bdd` 不增加持久 ID 或新语义。
KPi 为所有新增 v2 schema/validator/fixture assets 更新
`omp-distribution-map.yaml`，固定上游完整 commit，通过
`sync-upstream --plan` 审查候选，再在独立 clean worktree 经明确批准执行
`--apply`。Apply 负责更新 vendor、`upstream.lock.json`、`generated/**`、
`generated-omp/**` 和 `plugins/omp-sbtd/kit/**`；这些 promotion-owned 路径仍
禁止手工修改。

Plugin 同时读取 v1/v2：v1 继续兼容普通历史 validation evidence；需要证明 BDD
scenario 与执行报告关系的 P1-04，以及依赖该事实的 P1-06，只允许 v2 的显式关联
满足对应 Gate。promotion、Plugin 修复、npm 发布继续作为三个独立决策。
