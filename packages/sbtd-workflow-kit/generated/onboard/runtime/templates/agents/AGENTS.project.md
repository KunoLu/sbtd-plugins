# Codex 项目级规则

本文件只保存项目事实、默认路径、project-only fallback 和项目级硬性 gate。全局工具边界、Skill 触发矩阵、reviewer 状态与执行细节由已安装的全局 `AGENTS.md` 和对应 `SKILL.md` 承接，不在此复制。

## 加载与激活边界

- 当前项目的代码、配置、测试、README、CI、任务产物和工具输出优先于通用假设；更深层 `AGENTS.md` 优先于本文件。
- 正常 `sbtd-workflow-onboard init` / `reset` 成功写入全局规则并安装 bundled / external Skills 后，才激活完整 Skill 路由和 book-derived 强制门禁。
- public Skills CLI bootstrap 与 `init-projects` 只处理 Onboard 或项目本地资产，不安装全局 Skills，也不单独激活完整运行时门禁。
- 全局规则与对应 Skill 可见时直接继承；本文件只补充项目路径和项目事实。Skill 不可见时使用下一节 fallback，不得声称已调用该 Skill。

## Project-only fallback

仅有本文件而全局规则 / Skills 不可见时，最低遵守：

- 修改前读取项目已有规范、测试、README 和 CI；不引入第二套约定。
- 修复既有行为 bug 时先复现并记录要保留的行为，再建立最小回归检查；未锁定行为不修改。
- 修改既有代码时保持公共契约，避免混入任务外重构；运行聚焦验证后再运行项目规定的验证。
- 新增或修改用户可见行为时遵守 `no new uncovered behavior`：先记录可观察场景，再实现和验证。
- 缺少专用 Skill 时按本文件的项目级最低规则继续；若当前会话的全局规则已把某 reviewer 标为强制门禁，则缺 Skill 必须 `blocked`，不能用 fallback 冒充 reviewer 通过。
- 即使全局路由表不可见，也按以下客观触发事实自评本轮任务；命中项必须在最终报告中给出结论，对应 bundled Skill 不存在时该项为 `blocked`，不得记为 `passed` 或静默跳过：
  - 修改既有生产代码 -> 行为保持型重构检查（`book-refactoring-pass`）。
  - 修复既有行为 bug，或弱测试、行为不清、隐藏依赖、高回归风险任一命中 -> 遗留代码安全修改检查（`book-legacy-change-safety`）。
  - 需求涉及业务术语、领域规则、上下文边界或模型歧义 -> 领域边界审核（`book-ddd-distilled-modeling`）。
  - 持久化 / 共享数据、schema / migration、shared / persistent / cross-request / cross-process cache、queue / event / stream / job、ETL / analytics、跨服务数据流、API 所有权、数据所有权、source of truth、事务边界、读写路径、backfill / replay / rollback / recovery 任一命中 -> 数据设计风险检查（`book-ddia-data-design`）。
  - service / API / auth / billing / notification / background job / queue / scheduler / 外部集成 / data pipeline / deployment / rollout / migration / runtime 运维行为变更任一命中，或即将合并到 staging、发布 preview / release 且改动不只是文档 -> 发布就绪检查（`book-release-readiness`），在项目验证之后、完成前执行；必需验证缺失只能 `blocked`。
- 变更命中 Web 页面 / 交互流程、API 集成、用户可见 bug 修复、发布前 smoke、Trellis E2E 验收，或 GitNexus 给出高影响结论时，必须显式评估是否需要 Web / Mobile E2E 证据，并给出 `required` / `not-needed` / `blocked` 结论与理由，不得默认省略。
- 需要 Web 回归时先检查项目已有 Playwright 依赖、配置、scripts 和 E2E 目录，未安装时询问用户再装到项目 devDependency；需要 Mobile E2E 时按 Java 17+ -> Maestro CLI -> Maestro MCP 顺序检查，项目已有设备矩阵或 appId / bundleId 时以项目事实为准。
- 工具或环境不可用时报告 `blocked` / `skipped` / `not-needed` 和替代检查，不声称对应能力已执行。

## 代码可读性

项目既有约定优先。正确性、安全、运行时特性和可读性高于源码行数、文件数或最小 diff。不要制造密集表达式、模糊命名、浅层包装（shallow wrappers）或移除真实 seam；最终验证前复核本轮修改的手写代码和测试。

Ponytail Skills 可见时，编码前按全局规则使用 `ponytail`，非平凡 diff 在定点 smoke 后使用 `ponytail-review`；Skills 不可见时跳过路由，不视为已完成 review。

## UI/UX 项目上下文

- 产品 / 设计上下文默认位于 `docs/PRODUCT.md` 与 `docs/DESIGN.md`；项目已有路径时沿用，不维护多份同名文件。
- 若 `docs/` 会公开发布，先确认设计上下文是否允许公开。
- UI 初稿方向由 `ui-ux-pro-max` 承接；高保真塑形和 polish 由可用的 `impeccable` 承接；项目 design system、tokens 和品牌规范优先。
- shadcn 路由仅在项目存在 `components.json`、已使用 / 准备初始化 shadcn/ui，或任务明确涉及 shadcn CLI、registry、preset、组件组合时启用。registry 未明确时先询问，覆盖式更新需用户确认。
- React Bits 仅在 React + shadcn/ui 且任务明确需要其 components / blocks 时询问 tier。付费路径需要项目级 `.agents/skills/react-bits-pro/SKILL.md` 与对应 tier 的 registry endpoint；两者缺失时先与用户确认再按所选 tier 落地，不把未预置当作不可用直接阻塞。
- 该 Skill 缺失且用户已选付费 tier 时，在项目根执行 `npx shadcn@latest add @reactbits-starter/skill --path .agents/skills/react-bits-pro --overwrite --yes`：项目级安装、直接覆盖既有同名 Skill、不保留备份。只有该 `SKILL.md` 就位且当前环境可读取 `REACTBITS_LICENSE_KEY` 后，才读取它并继续安装 components / blocks。
- `reset` 检测到既有 Free / Starter / Pro / Ultimate registry 或 Skill 时必须保留并输出检测到的 tier；未经用户确认不得用免费版覆盖已存在 tier。
- 写入 `components.json` 只增量合并 `registries`，不得覆盖既有 `$schema`、`style`、`tailwind`、`aliases` 等无关配置；`REACTBITS_LICENSE_KEY` 只从当前环境读取，不得输出、写入仓库或提交。

## Trellis

仅当项目存在 `.trellis/`、`.trellis/workflow.md`、Trellis 命令或更深层规则等强证据时使用 Trellis。已确认项目根存在本文件但 `.trellis/` 缺失时，提示尚未执行 `trellis init -u <username>`；普通项目任务不代用户初始化，Onboard `init` / `reset` 例外按其 Skill 执行。

Trellis 可用时：

- 优先加载 `trellis-workflow`；Skill 不可见时至少读取 `.trellis/workflow.md`、相关 `.trellis/spec` 和当前任务的 `prd.md` / `design.md` / `implement.md`，不得手动跳过 phase。
- `.trellis/spec/lessons.md` 仅作短入口；完整 lesson 通过 `.trellis/lessons/index.md` 和命中 topic 按需读取。
- 一次性任务结论进入 task artifacts，长期架构、API、数据模型、权限或业务规则才进入 `.trellis/spec`。
- 升级 CLI 后先运行 `trellis update`；涉及 hook 时重启对应 Agent host / IDE 后再验证新会话。`trellis update` 刷新 registry-backed `.trellis/spec` 时，先复核 hash、冲突和 diff 再接受，不得静默覆盖长期 spec。
- `trellis ablate` / `restore` 会删除或回填数据，执行前必须取得用户明确确认并说明影响范围；工作树干净只是前置条件，不构成免确认理由。
- `task.py rename`、archive / start / set-*、subtask 和 Channel 名称操作继承全局 filesystem-safety；不得绕过 dirty-data、manifest ownership、safe-name 或 pointer containment。
- `[workflow-state:task_error]` 时先修复当前 `task.json`；空 / seed-only jsonl 的启动与 `--allow-empty-context` 边界以 `.trellis/workflow.md` 为准。

平台调度最低边界：`.trellis/**` 只定义共享 workflow gate，不标识 host。Codex 只解释 `.codex/**` 和有效 `codex.dispatch_mode`；OMP 只解释 `.omp/**` 与生成 worker。两者不得互相套用。每项变更只有一个 writer，每个验证环境只有一个 controller。

显式 `codex.dispatch_mode` 取值非法时 fail-closed 到 Inline，由主会话直接执行；必须报告并修正该设置，fallback 生效期间不得调度 Codex role subagent。

### Trellis 目录

按项目策略保留或提交：

- `.trellis/spec/`
- `.trellis/lessons/`
- `.trellis/agents/`
- `.trellis/workflow.md`
- `.trellis/tasks/<task>/{prd,design,implement}.md`

默认不提交：`.trellis/.developer`、`.trellis/.runtime/`、`.trellis/.cache/`、`.trellis/worktrees/`、`.trellis/.backup-*`、`.trellis/channels/`、`~/.trellis/channels/`、`.gitnexus/`。

## BDD / Gherkin

所有用户、管理员、API / CLI 客户端、外部系统或导出文件消费者可见的新增 / 修改行为默认需要持久场景。纯内部重构、依赖 / 工具配置、机械格式化、无语义 UI polish 或 typo 可跳过，但最终说明原因。

### 持久路径与语言

- 已有 `.feature` / runner 时沿用项目路径、语言和关键词。
- 无约定时，单应用使用 `features/<capability>.feature`；monorepo 放到拥有该行为的 app / service 下。
- 默认中文场景文本 + 英文 Gherkin 关键词，不默认添加 `# language: zh-CN`。
- 场景描述可观察行为，不写 selector、mock、fixture、数据库字段或内部 helper。

### Source of truth

确认后的 `.feature` 是用户可见行为 SOT；PRD 负责意图和范围，design / implement 负责技术方案。冲突时先对齐 PRD 与 `.feature`，再改测试和代码。

新增行为先写场景；修改行为更新场景；用户可见 bug 先写正确行为场景和失败回归测试。无法自动化的场景标记 `@todo` 并记录人工验证与阻塞原因。

主动使用 `gherkin-bdd` 时：含 `sync` / `同步` 进入可写 BDD Sync；只有 explicit read-only intent，且不含 `add / change / update / delete` 或 `写入 / 新增 / 修改 / 更新 / 删除` 时，才进入只读 Knowledge Ingest。Knowledge Ingest 固定目标 ref 的精确 SHA，不切换活动工作树，不修改源仓，最终报告 `Mutation: none`。

## GitNexus

仅在 GitNexus MCP 可用且当前项目索引有效时使用；结果必须与源码、实际 diff、测试和 Trellis 产物交叉核对。

- 修改前优先做影响分析，修改后优先做变更检测；stale 或解析语义升级后先按项目约定用 CLI 刷新。
- MCP allowlist 未覆盖时，该仓库的 MCP 不可用；fail-closed 只读时不走 MCP 写入；两者都不阻止 CLI `gitnexus analyze`。
- 跨服务 API / route / consumer 结论必须回到真实路由和调用复核。
- 不静默新增 hook、不默认 `--self-commit`、不改 MCP transport。不可用时跳过且不阻塞任务。

## Skill 编排边界

- 全局 AGENTS 的 Skill 路由表是触发条件 SOT；每个 `SKILL.md` 独占执行步骤、reviewer 状态、输出 schema、修正回路和 stop condition。
- `Book Gate Plan`、Gate state 生命周期和跨 reviewer 顺序只按全局规则执行；本文件不复制 reviewer 状态词表。
- 每次完整 `grill-with-docs` 后仍须强制 post-grill DDD 二次审核；加载 `book-ddd-distilled-modeling` 并输出 `DDD Boundary Review` 后才能进入需求确认 / PRD。project-only 未激活完整门禁时，按 Project-only fallback 的客观触发自评并输出结论；`book-ddd-distilled-modeling` 不可用时记为 `blocked`，不冒充 Skill 审核。
- `mattpocock/skills` 的 canonical 名称、依赖和安装来源以 catalog / stable manifest / 全局规则为准，本文件不缓存清单。
- 交互压缩只引用全局状态机事实源；保护区只覆盖当前回复，不复制计数器或资格锁存。project-only 下无全局规则时不自动推断该状态机。

## Trellis Channel

普通任务不启动 Channel。用户明确要求多 Agent / 多模型 / worker / forum / 并行评审，或高风险 review / validation 需要 preflight 时，加载 `trellis-channel`；preflight 不等于 spawn，必须有用户明确请求或确认。worker 不得 stage、commit、archive、finish-work、push、deploy，除非用户明确授权且该 worker 是唯一 writer / controller。

默认 worker 只读。一个 checkout 只有一个 writer，一个环境只有一个 validation controller。结束 Channel 前必须确认没有仍在运行的 worker，清理 runtime / worktree 残留，并复核是否留下未预期的 dirty 路径。Channel 结论整理回 task artifacts 或长期 spec，runtime / events / 原始日志默认不提交。

## Web / Mobile 验证与测试资产

继承全局分工：Chrome DevTools MCP 负责 Web 现场诊断，Playwright CLI 负责可重复 Web 回归，Playwright MCP 负责探索 / locator，Maestro CLI 负责 Mobile / Hybrid E2E，Maestro MCP 负责设备 / flow 辅助，`web-ui-autotest-generator` 负责可入库 Web UI 测试资产。

项目级路径：

- BDD 场景：项目 `features/` 约定。
- Maestro flow：`maestro/flow/`，平台差异明显时拆 `ios/` / `android/`；smoke 用 `smoke.yml`。
- Web UI manifest：`tests/e2e/manifest/{ui-test-manifest,ui-selector-audit,ui-test-coverage}.json`。
- API 正式本地快照：`tests/api/reports/`。
- Playwright 临时 HTML：`tests/e2e/reports/.playwright-html-current/`；正式本地快照：`tests/e2e/reports/html/`。
- Maestro 本地报告：`.maestro/reports/`。

报告命名、branch_slug、重跑顺序、状态枚举、evidence sidecar、URI 覆盖矩阵和 publication 语义由 `project-validation` 及专项 Skill 承接。本文件只固定以下硬边界：

- runner 可能清空的目录不能作为正式本地快照；下一轮运行前先复制 / 提升需要保留的报告。
- stdout-only / terminal-only / Playwright list reporter 只算诊断，不算最终正式验证。
- mock 必须有 contract / schema / 真实样例 / 既有 fixture 或用户确认；mock-backed 不得冒充 full-stack。
- 报告默认本地留存且由 `.gitignore` 排除；PR / 知识库 evidence publication 是独立流程，不等于把报告提交到 Git。
- 真实账号、token、PII、生产数据不得进入测试、日志、截图、trace、video 或报告。

缺稳定 selector、账号、环境、数据准备 / 清理、设备、app artifact 或 API contract 时，不生成脆弱测试资产，报告 `blocked`。

## SEO / GEO

变更影响公开网站、落地页、文档站、产品页、营销页或公开 README 时即触发 `seo-geo`；用户明确要求或验收包含 crawl / indexing / schema / meta 时同样触发。无公网 / preview URL 只能 `static-only` 或 `blocked`；内部后台、API、CLI、移动 App 和纯回归不触发。不得写入付费凭据、Search Console 数据或敏感 URL。

## 验证命令

优先级：项目 / 深层 `AGENTS.md` → README / scripts / Makefile / CI → `project-validation` → 聚焦检查。

常见回退：

```bash
rtk npm run lint
rtk npm run build
rtk ruff check .
rtk ruff format .
rtk ty check .

# 报告型测试按全局 rtk gate 判断，必要时使用原生命令
npm run test
pytest
uv run pytest        # 仅 uv 项目
go test ./...
```

`rtk` 不可用时回退原生命令；报告缺失、陈旧或不可证明时必须原生命令复验。

## Lessons

bug 修复、回滚、工具误判、工作流错误、验证失败、GitNexus 不匹配或 Channel 上下文丢失时，加载 `lessons-record`。Trellis 项目中 `.trellis/spec/lessons.md` 只作短入口，完整 lesson 进入 `.trellis/lessons/index.md` 与 topic；非 Trellis 项目沿用已有分层结构，否则使用 `docs/lessons.md`。
