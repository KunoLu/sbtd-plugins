# Codex 项目级规则

本文件只保存项目级补充、项目默认路径和硬性 gate。通用工具边界、状态枚举、报告细则和专项执行步骤由全局 `AGENTS.md` 与对应 Skill 承接；除非本项目需要覆盖默认行为，不在本文件重复展开。

## 项目事实源

- 当前项目的代码、配置、测试、README、CI、任务产物和工具输出优先于通用假设。
- 如果本项目有更深层 `AGENTS.md`，修改对应目录文件前必须读取并遵守。

---

## UI/UX 设计上下文

默认继承全局规则：`impeccable` 的项目上下文文件维护在 `docs/PRODUCT.md` 和 `docs/DESIGN.md`。

项目级补充：

- 如果本项目已有明确设计文档路径或更深层 `AGENTS.md` 指定其他路径，以项目事实为准。
- 不要在项目根目录、`.agents/context/`、`docs/` 中维护多份同名上下文文件。
- 如果 `docs/` 会被文档站公开发布，先确认这些设计上下文是否允许公开；不允许公开时，按项目发布配置排除，或由项目 `AGENTS.md` 指定其他路径。

UI/UX 任务编排：

- 涉及 UI、交互、布局、视觉、组件体验或前端可用性时，初稿计划默认先使用 `ui-ux-pro-max`，明确产品类型、目标用户、信息架构、交互模型、响应式策略、可访问性基线和项目设计系统约束。
- 如果项目存在 `components.json`、使用或准备初始化 shadcn/ui，或任务涉及 shadcn CLI、registry、preset、组件安装 / 更新 / diff、组件组合、表单、图标、Tailwind token、Base UI vs Radix 差异或 chat primitives，初稿方向确认后调用 `shadcn` Skill 处理组件来源和实现规则。
- 只有在目标项目已检测为 React + shadcn/ui（项目根目录存在 `components.json`）且任务需要 React Bits 风格组件、blocks 或 landing page sections 时，才询问 React Bits tier；默认保持 shadcn/ui only，React Bits Free 或付费 Starter / Pro / Ultimate 都需要用户明确确认。
- `impeccable shape` / `impeccable craft` 只在新视觉方向、高保真页面、大幅改版、品牌 / 营销强视觉页面、方向不清或用户明确要求时前置使用；其 brief 必须经用户确认后再进入实现。
- 常规 UI 实现完成后，先运行项目验证和浏览器 / 截图检查；如 `impeccable` 可用，再使用 `audit` / `critique` / `polish` 或 `layout`、`typeset`、`colorize`、`adapt`、`clarify`、`animate`、`harden`、`optimize` 等针对性命令做打磨。
- 如果 UI/UX 任务进入 Trellis，任务级设计结论写入 `prd.md`、`design.md` 或 `implement.md`；长期设计系统规则才写入 `docs/DESIGN.md` 或 `.trellis/spec`。

### shadcn Skill

`shadcn` 是官方 shadcn/ui 工作流 Skill，不是通用 UI 设计 Skill，也不是 React Bits Free / 付费 tier 的子集或替代品。

使用场景：

- 项目根目录存在 `components.json`，或用户要求初始化 / 维护 shadcn/ui。
- 需要执行或评估 `shadcn init/add/search/view/docs/diff/info/migrate/preset`、preset code、registry item、第三方 / 私有 / 付费 registry 或 shadcn MCP 配置。
- 需要修复 shadcn 组件组合、forms、icons、semantic tokens、Tailwind v3 / v4、Base UI vs Radix API、chat primitives、registry import path rewrite 或已安装组件更新策略。

执行规则：

- 在 UI/UX 任务中，先用 `ui-ux-pro-max` 明确产品方向、信息架构和设计系统约束，再用 `shadcn` 处理组件来源、CLI、registry 和具体实现规则。
- 按项目 package manager 选择 `npx shadcn@latest`、`pnpm dlx shadcn@latest` 或 `bunx --bun shadcn@latest`。
- 添加或更新组件前先检查 `components.json`、`shadcn info`、已安装组件和项目别名；涉及组件 API 时先查 `shadcn docs`。
- registry 未明确时先询问用户；更新已有组件时先用 `--dry-run` / `--diff`，未经用户明确确认不使用覆盖式更新。

跳过条件：

- 非 shadcn/ui 项目，且用户没有要求引入 shadcn。
- 只是通用 UI 设计判断、视觉 polish、后端、测试、文档或非 React UI 栈任务。
- React Bits Free / 付费 tier、付费 Skill 安装或 key 可用性判定；这些按 React Bits tier 规则单独处理。

### React Bits Tier 和 Pro Skill

React Bits 是可选前端 UI 增强，不是默认设计系统，也不是 shadcn/ui 的必装依赖。安装或重置工作流默认保持 shadcn/ui only；只有在目标项目已确认是 React + shadcn/ui 后，才向用户确认是否需要 React Bits Free 或付费 tier。

先决条件：

- 当前任务是前端 UI 开发，且明确需要 React Bits 风格 components、blocks、templates 或类似高级动画组件。
- 项目技术栈是 React 项目，包括 Next.js、Vite React、Remix、TanStack Start React、使用 TanStack Router 的 React 应用等，并已初始化 shadcn/ui。
- 本地 Node.js 18+ 可用，项目根目录存在 `components.json`。

Tier 确认：

- 简短说明：shadcn/ui 提供常规应用组件；React Bits Free / 付费 tier 只用于更强视觉表达、动画组件、blocks 或 landing sections。
- 询问用户选择：继续 shadcn/ui only、安装 React Bits Free，或使用已有付费 Starter / Pro / Ultimate。
- React Bits Free 只有在本工作流已有明确免费 source / registry / 安装命令时才安装；未配置时说明暂不可自动安装，不要退而使用付费 registry。
- Starter / Pro / Ultimate 属于付费路径；必须由用户确认，且执行 `shadcn` 或 Agent 的当前环境能读取 `REACTBITS_LICENSE_KEY`。Agent 不打印、不输出、不提交该 key。

付费配置要求：

- 如缺少 shadcn/ui，先让项目完成 `npx shadcn@latest init` 或遵循项目既有 shadcn 初始化流程。
- 在 `components.json` 中只合并 `registries`，不要覆盖 `$schema`、`style`、`tailwind`、`aliases` 等既有字段。
- `@reactbits-starter` registry URL 使用 `https://pro.reactbits.dev/api/r/starter/{name}.json`，Authorization header 使用 `Bearer ${REACTBITS_LICENSE_KEY}`。
- `@reactbits-pro` registry URL 使用 `https://pro.reactbits.dev/api/r/pro/{name}.json`，仅在需要 Pro / Ultimate blocks 时配置。
- 如果其他前提都满足，但项目环境中没有安装对应 React Bits Pro Skill，先在项目根目录执行 `npx shadcn@latest add @reactbits-starter/skill --path .agents/skills/react-bits-pro --overwrite --yes`。该命令是项目级安装，不是全局安装；已有 `.agents/skills/react-bits-pro/SKILL.md` 直接覆盖，不保留备份。
- 只有 `.agents/skills/react-bits-pro/SKILL.md` 安装成功，且当前环境能读取 `REACTBITS_LICENSE_KEY` 后，才读取该 Skill 并继续安装 components / blocks。
- 安装组件时优先使用 shadcn CLI；组件按项目样式栈选择 Tailwind `-tw` 或 CSS `-css` 变体，blocks 使用 `@reactbits-pro/<name>`。
- 在 `reset` 中如果检测到既有 React Bits Free、Starter、Pro 或 Ultimate registry / Skill，必须保留并输出检测到的 tier；未经用户确认，不用默认免费版覆盖已存在 tier。

跳过条件：

- 非 React 前端、TanStack 的 Vue / Solid / Svelte 等非 React adapter、Vue / Svelte / Angular / 原生 HTML 项目、后端任务、测试任务、文档任务。
- 项目未使用 shadcn/ui，且用户没有要求引入 shadcn。
- 当前环境无法满足所选 tier 的 source / registry / key 条件，或 React Bits Pro Skill 未安装且无法安装 / 安装失败。
- 项目已有明确组件库 / design system 且需求不要求 React Bits。

如果跳过 React Bits，应说明具体缺失前提，并继续使用项目已有组件库、`shadcn`、`ui-ux-pro-max`、`impeccable` 或普通前端实现流程。

---

## Trellis

高优先级未初始化提示：

- 如果已经确认当前目录是目标项目根目录，且项目根目录存在项目级 `AGENTS.md`，但项目根目录不存在 `.trellis/`，必须告诉用户：当前项目还没有进行 `trellis init` 操作。
- 默认不要替用户执行 `trellis init`。必须说明该命令包含项目初始化操作，请用户自行在命令行中执行，或明确进入 `sbtd-workflow-onboard` 的 `init` / `reset` 流程。

```bash
trellis init -u your-name
```

项目级模板不另行放宽 Trellis 初始化边界；只有用户明确进入 `sbtd-workflow-onboard` 的 `init` / `reset`，并满足该 Skill / `REFERENCE.md` 的 Trellis CLI、`.trellis/` 缺失、username / platform 确认条件时，才沿用 onboard 例外执行初始化和后置 bootstrap 检查。

仅当当前项目存在 Trellis 强证据时使用 Trellis：

- 存在 `.trellis/`
- 存在 `.trellis/workflow.md`
- 存在 `$trellis-*`
- 本项目更深层 `AGENTS.md` 明确说明使用 Trellis

如果 Trellis 可用：

- 调用 `trellis-workflow` Skill。
- 读取 `.trellis/workflow.md`。
- 读取相关 `.trellis/spec`；其中 `.trellis/spec/lessons.md` 只作为短入口和高优先级摘要。
- 不要默认读取完整 `.trellis/lessons/**`；先通过 `.trellis/lessons/index.md`、tags、错误信息或当前任务主题按需检索，再读取命中的 topic / archive 文件。
- 如果存在当前活跃任务，优先读取 `prd.md`、`design.md`、`implement.md`。
- 不要绕过 `.trellis/workflow.md` 或手动跳过 Trellis phase。
- 不要把一次性任务计划写入 `.trellis/spec`；长期规范、架构决策、业务规则变化才应沉淀到 `.trellis/spec`。
- 本项目继承全局 Trellis filesystem-safety 规则；升级 Trellis CLI 后按全局规则运行 `trellis update`，并不得绕过 dirty-data、manifest ownership、safe-name 或 active-task pointer containment guard。升级后不要假设 `trellis update` 会改写既有 session pointer；越权任务路径按无任务处理。
- 使用 registry-backed spec templates 时，`trellis update` 可能刷新 `.trellis/spec`；必须复核 hash / conflict 提示和实际 diff，不要静默覆盖项目长期规范。

需求进入 PRD / Trellis task 前：

- 如果用户只给出初始需求，且需求涉及本项目领域模型、业务术语、长期规则、已有文档或架构决策，先使用 `grill-with-docs` 澄清。
- `grill-with-docs` 阶段应先读取项目文档和相关代码；能从项目事实回答的问题，不要反问用户。
- 一次只问一个关键问题，并给出推荐答案；达成共识后先执行强制 post-grill DDD 二次审核，再输出需求确认摘要。
- 长期领域上下文默认写入 `docs/CONTEXT.md`，ADR 默认写入 `docs/adr/*.md`，多上下文项目使用 `docs/contexts/<context>/CONTEXT.md` 和 `docs/contexts/<context>/adr/*.md`；不要新建根目录 `CONTEXT.md`，除非本项目已采用该路径或更深层 `AGENTS.md` 明确指定。
- `grill-with-docs` 完整结束后必须先输出 `DDD Boundary Review`；其内嵌的 external `domain-modeling` dependency 不替代该审核，未达到全局规则定义的 `confirmed` 不得进入需求确认摘要、PRD、design、Trellis task 或实现。
- 需求确认摘要经用户确认后，再使用 `to-spec` 生成 Markdown spec / PRD，并用 `to-tickets` 拆成 Trellis-ready vertical slices。
- 在 Trellis 项目中，spec / PRD 终稿应写入 `.trellis/tasks/<task>/prd.md`；拆解后的 parent / child tasks 和实现切片应落到 `.trellis/tasks/<task>/...` 下的 task artifacts。未确定 task 路径前，不要把最终 spec / PRD 或 ticket / task 清单长期落到 `docs/`。
- 如果需求不依赖项目文档或领域术语，只是通用方案质询，可使用 `grill-me`。

---

## BDD / Gherkin

所有用户可见行为默认需要 BDD 场景。用户可见行为包括 UI、API、CLI、导出文件、通知、权限结果、错误响应、状态变化，以及外部集成系统能观察到的输入输出或副作用。纯内部实现变化、依赖 / 工具配置、机械格式化、无语义 UI polish 或 typo 可以跳过 BDD，但最终输出必须说明跳过原因。

### 持久规格路径

- 如果本项目已有 `.feature` 文件、`features/` 目录、Cucumber / behave / pytest-bdd / cucumber-js 等 BDD runner 配置，沿用既有路径、命名、语言和关键词。
- 如果没有既有约定，单应用项目默认使用 `<project-root>/features/<capability-slug>.feature`。
- 能力较多时可按功能区分组，例如 `features/authentication/login.feature`、`features/orders/order-cancellation.feature`。
- monorepo / 多应用项目默认落到拥有该用户可见行为的 app / package / service 根目录，例如 `apps/web/features/checkout/cart-update.feature`、`services/billing/features/invoice-export.feature`、`packages/cli/features/project-init.feature`。
- 跨 package 的行为放在最接近产品入口的 app / service 下，不拆到每个内部 package。
- Trellis task artifacts 可以草拟或引用 BDD 场景，但默认不作为长期行为 source of truth；项目级规则明确指定其他持久 BDD 规格路径时，以项目规则为准。

### 语言与内容

- 如果项目已有 `.feature`，沿用既有 Gherkin 语言和关键词。
- 如果没有 `.feature`，默认使用中文场景标题、描述和步骤文本，结构关键词使用英文 `Feature`、`Rule`、`Background`、`Scenario`、`Scenario Outline`、`Examples`、`Given`、`When`、`Then`、`And`、`But`。
- 默认不添加 `# language: zh-CN`；只有项目既有中文 Gherkin 关键词或用户明确要求中文关键词时才添加。
- 同一 bounded context 或功能区内尽量不混用中英文关键词。
- 场景里的领域词汇以项目 glossary、`docs/CONTEXT.md`、context docs、`.trellis/spec` 和既有 `.feature` 词汇为准。
- 场景描述可观察产品行为，不写 selector、mock、fixture、数据库字段、内部函数名或测试 helper，除非该层本身就是对外行为。

### 工作流规则

- 新增用户可见功能：先创建或更新持久 BDD 场景，再写测试和实现。
- 修改已有用户可见功能：补齐或更新相关能力的 BDD 场景。
- 用户可见 bug 修复：先写描述正确行为的场景，再写失败回归测试，再修复。
- 既有项目采用 `no new uncovered behavior`：未触碰的历史行为可以暂时没有 `.feature`，但新增或触碰的行为必须补齐。
- 当主动使用 `gherkin-bdd` 且用户请求包含 `sync` 或 `同步` 时，进入 BDD Sync Mode：全量扫描当前工作树（包含未提交内容）、项目 `features/` 目录和所有能定义用户可见行为的代码 / docs / tests，检查 `.feature` 是否与最新代码逻辑同步。多仓、前后端分离或 feature 汇总到前端入口仓库时，先确认其他端仓库是否有更新；有更新必须让用户提供路径并一起扫描，无更新则记录确认后只按当前仓库同步。同步报告必须列出更新、新建、删除、未变和候选删除的 feature 文件及概要。
- 当主动使用 `gherkin-bdd` 时，只有请求具有 explicit read-only intent（`read` / `读取`）、不含 `sync` / `同步`，并且不含 `add / change / update / delete` 或 `写入 / 新增 / 修改 / 更新 / 删除` 等变更意图，才调用 `knowledge-base-integration` 进入只读 Knowledge Ingest。要求“先读取再修改”的请求进入普通 BDD 写入流程；请求含有 `sync` / `同步` 时仍优先使用上一条既有 BDD Sync Mode。Knowledge Ingest 按产品注册表和服务器 Workspace Mapping 读取每个仓库的目标 branch / tag / SHA，并先解析为精确 commit SHA；不切换开发者活动工作树。只读取仓库自有 `.feature`，保留 Feature、Rule、Background、Scenario / Outline、Examples、Doc String、Data Table、tags 和 source line，并输出 Revision Set、可重建聚合视图、source locator、静态 / manifest 测试绑定、跨仓冲突候选、metrics 和幂等运行状态；不要求或补写 Feature ID、Scenario ID、新 tags 或 BDD runner；最终报告 `Knowledge Ingest`: `run` / `partial` / `blocked` 和 `Mutation: none`。
- 前后端分仓、跨服务、Web + API、Mobile + API 或 Hybrid 链路不完整时，先确认 `Cross-repo context`: contract、环境、账号、数据、选择器、设备和 app artifact；缺关键事实时标记 blocked 或 `@todo`，不要把猜测写成 source of truth。
- mock 只能基于 API contract、schema、真实响应样例、既有 fixture、launch arguments 或用户明确确认；mock-backed / app-mocked / contract-backed 测试不能报告为 full-stack 通过。
- 如果已有 Gherkin runner，场景应绑定 step definitions 或 runner 测试；没有 runner 时，使用项目已有测试框架，并用测试名、注释、目录结构或项目约定追踪到场景。
- 不默认引入新的 Gherkin runner；只有用户明确要求、项目已有方向或现有测试框架无法表达验收行为时才建议引入。
- Mobile / Hybrid E2E 场景需要设备级覆盖时，可通过 `maestro-mobile-e2e` 从对应 `.feature` 派生 Maestro flow；`.feature` 仍是行为 source of truth，Maestro flow 是可执行测试资产。
- 无法自动化的场景必须标记 `@todo` 或项目等价标记，并说明阻塞原因和临时人工验证方式。

### Source Of Truth

对已确认的用户可见行为，持久 `.feature` 是行为 source of truth。`prd.md` 负责需求背景、范围、约束、非目标和验收意图；`design.md` / `implement.md` 负责技术方案和实现计划，不覆盖 `.feature` 中的产品行为。

如果 PRD、Trellis artifacts、`.feature`、测试和代码冲突，不要直接实现；先对齐 PRD 与 `.feature`，再更新测试和代码。

---

## GitNexus

本项目默认继承全局 GitNexus 规则：GitNexus 通过全局 `gitnexus-mcp` 提供能力，不作为 Skill 管理；只有 MCP 可用且当前项目已建立索引时才使用。stale index、分页、PDG / taint / trace、MCP transport、hook、optional grammar 和大仓库风险等细则以全局 `AGENTS.md` 为准。

项目级强证据包括：

- 当前项目存在 `.gitnexus/`
- `gitnexus status` 显示已有索引
- GitNexus MCP 的已索引仓库列表包含当前项目路径
- 本项目更深层 `AGENTS.md` 明确说明 GitNexus 已启用

项目级使用要求：

- 修改代码前，优先通过 GitNexus MCP 执行影响分析。
- 修改代码后，优先通过 GitNexus MCP 执行变更检测。
- GitNexus 结果必须与实际 diff、测试结果、Trellis 任务产物和项目规范交叉核对。
- 跨服务 API、HTTP route / consumer、gRPC 或前后端调用链结论，必须回到实际路由、客户端调用和 diff 复核。
- 如果全局 GitNexus 细则不可见，最低遵守：MCP + 当前项目索引同时可用才使用；stale 先按项目约定刷新；刷新失败时把 GitNexus 结果降级为 advisory；不静默新增 hook 或改写 MCP transport；不可用时跳过且不阻塞任务。

---

## mattpocock/skills 项目级编排

本项目只接入以下官方 mattpocock/skills，并默认原样使用；由 Onboard stable 镜像回退安装时同样不得改写上游内容：

- `diagnosing-bugs`
- `tdd`
- `grill-me`
- `grill-with-docs`
- `grilling`
- `domain-modeling`
- `codebase-design`
- `handoff`
- `writing-for-agents`
- `to-spec`
- `to-tickets`

旧官方 Skill `diagnose` 已迁移为 `diagnosing-bugs`；`write-a-skill` 与 `writing-great-skills` 已迁移为 `writing-for-agents`；`zoom-out` 已从上游移除，不再作为 mattpocock 官方 Skill 接入。

编排说明：

- 普通 bug、测试失败或运行时异常：`diagnosing-bugs` → GitNexus debugging（根因不清时）→ Codex fix → `tdd` / regression test → 项目测试。
- 线上问题、日志异常或数据不一致：`diagnosing-bugs` 先建立时间线、事实、假设和排除项，再进入修复或缓解。
- 中大型项目内需求：`grill-with-docs`（内部使用 `grilling` 的 design tree / frontier 分轮提问和 `domain-modeling`；每轮只问前置条件已满足的问题）→ `book-ddd-distilled-modeling` 独立二次审核与可见 `DDD Boundary Review` → 需求确认摘要 → `to-spec` → `gherkin-bdd`（用户可见行为场景）→ `to-tickets` 输出 Trellis-ready Markdown tasks → Trellis workflow → GitNexus impact-analysis → Codex implementation → 项目测试 → Chrome DevTools MCP（需要 Web 运行时诊断时）→ Playwright CLI（涉及 Web 回归时）→ Maestro（涉及移动 App E2E 时）；如果需要把 Web UI 回归路径固化为入库测试资产，再使用 `web-ui-autotest-generator`。
- 不依赖项目文档或领域术语的通用方案质询：`grill-me`（内部使用 `grilling` 的 design tree / frontier 分轮提问）→ 方案确认 → `to-spec` / `to-tickets`（需要时）→ Codex implementation。
- 需要回归测试的普通用户可见行为修改：Trellis `native` workflow → `gherkin-bdd` → 主动判定 `tdd` Skill → `codebase-design`（需要测试面 / seam 判断时）→ GitNexus impact-analysis → 项目测试。
- 高风险后端逻辑、算法、权限、计费、状态机或关键数据同步：`grill-with-docs` → `book-ddd-distilled-modeling` 独立二次审核与可见 `DDD Boundary Review` → `to-spec` → `gherkin-bdd`（外部可观察行为）→ `to-tickets` → Trellis TDD workflow → `tdd` / `codebase-design` → GitNexus impact-analysis → 回归测试。
- 陌生模块或上下文不清：代码阅读 / `codebase-design` → GitNexus exploring / impact-analysis → Codex implementation。
- 长任务暂停、`/clear`、新会话或交接前：`handoff`。
- 需要创建或维护 Agent 消费的 Skill、AGENTS、CLAUDE 或指针文档时：`writing-for-agents`。

`to-spec` 默认输出 Markdown spec / PRD；`to-tickets` 默认输出 vertical-slice Markdown tasks / tickets。在 Trellis 项目中，这些产物最终应进入 `.trellis/tasks/<task>/prd.md`、`design.md`、`implement.md` 或 parent / child task artifacts。除非用户明确要求，不自动发布到 GitHub、Linear 或任何 issue tracker。

---

## 交互压缩工具项目级边界

本项目继承全局 `rtk` / `caveman` 规则；项目级只保留运行时边界：

- `caveman` 是用户级全局 Agent 回复压缩 Skill，不是项目依赖、测试工具、设计工具或验证工具。
- 不要把 `caveman` 写入 BDD、TDD、GitNexus、Trellis、发布验证或项目运行时链路；它只影响 Agent 给用户的对话表达。
- `rtk` 是命令输出压缩层，不是测试 runner；unit / API / Playwright / Maestro 等报告型测试先按全局 `rtk` 与报告型测试 Gate 判断，必要时使用原生命令或 fallback-native。
- 自动压缩只引用全局状态机事实源：项目级不复制计数器、资格锁存、任务连续性或重置逻辑；不得自动进入更激进等级，也不得把自动状态写入项目文件。
- 需求最终确认、review gate、安装 / 权限 / 破坏性操作确认、失败与剩余风险、最终验证报告、最终答复和长期项目文档属于完整输出保护区；保护区只覆盖当前回复，不清除或重置全局任务级自动状态。
- `normal mode`、`stop caveman`、`恢复完整输出`、`不要压缩` 和 `本任务不要自动压缩` 建立当前任务的自动退出；手动 `/caveman` 不清除自动退出。会话级退出、重新启用、配置 `off`、新的主要目标和 context compaction / handoff 语义全部继承全局规则。

---

## agent-rules-books 派生 Skill 编排

本项目默认只接入以下 bundled book-derived skills：

- `book-refactoring-pass`
- `book-legacy-change-safety`
- `book-ddd-distilled-modeling`
- `book-ddia-data-design`
- `book-release-readiness`

这些 Skill 在全局规则定义的客观开发触发条件命中时是强制门禁，未命中时才是按需专项审查；它们不替代项目事实、Trellis workflow、task artifacts、`.trellis/spec`、GitNexus、`tdd`、项目测试、`project-validation`、Playwright、Maestro 或人工评审。

默认不接入 APoSD、Clean Architecture、PoEAA 等项目风格更强的扩展；如果具体项目明确需要，由项目级 `AGENTS.md` 或更深层规则单独声明。

开发任务在进入对应阶段前必须输出 `Book Gate Plan`，按全局触发矩阵标记每个 Skill 的 `required` / `on-demand`、命中事实、执行阶段和独立 Gate state；Gate state 使用 `planned` / `running` / `passed` / `blocked` / `not-required`，且只能按 `planned` → `running` → `passed` / `blocked` 转换。具体 reviewer status 仅在实际运行后补充，项目级不得复制或放宽全局枚举和阻断语义。

编排说明：

- 需求 / PRD 阶段：无论是 Agent 自发调用还是用户主动调用，每次 `grill-with-docs` 完整结束后都必须执行 `book-ddd-distilled-modeling` 独立二次审核，向用户输出 `DDD Boundary Review` 并达到 `confirmed`，再进入 `to-spec` → `to-tickets` → Trellis workflow；没有调用 `grill-with-docs` 时，才按业务术语、领域规则或 bounded context 风险独立判断是否调用。
- 设计阶段——数据密集型变更在设计稳定前强制审核：持久化 / 共享数据、schema / migration、shared / persistent / cross-request / cross-process cache、异步 / 跨服务数据流、数据所有权、事务 / 读写路径或 backfill / replay / rollback / recovery 任一变化时，`book-ddia-data-design` 必须输出 `DDIA Data Design Review` 并达到 `confirmed`，再稳定 `design.md` / `implement.md` 或开始实现。
- 修改前——遗留 / bug 风险在行为修改前强制审核：修复既有行为 bug，或弱测试、行为不清、隐藏依赖、高回归风险任一命中时，`diagnosing-bugs` / 代码证据 → `book-legacy-change-safety` → safety net，`Legacy Change Safety Review` 达到 `characterized` 后才能修改行为；安全网必须先引入生产 seam 时进入 `seam-required`。
- 实现前——既有生产代码在首次实现编辑前强制审核：任何既有生产代码修改都必须执行 `book-refactoring-pass`；`Refactoring Review` 为 `refactor-first` 时先完成最小行为保持重构并复审，为 `proceed` 后再实现。legacy 为 `seam-required` 时允许先运行 `safety-seam-only` 模式。
- 同时命中 legacy 和 refactoring gate 时，正常顺序为 `Legacy Change Safety Review` → `Refactoring Review` → Codex implementation；受控例外为 `seam-required` → `Refactoring Review` (`safety-seam-only`) → 建立 safety net → legacy `characterized` → 常规 `Refactoring Review`，避免测试 seam 死锁且禁止普通重构抢跑。
- 验证 / 发布前——生产路径变更在项目验证后强制审核：service、API、auth、billing、notification、job、queue、scheduler、external integration、data pipeline 或 deployment behavior 任一变化时，先完成所有适用 testing-tool gate 和 project validation，再执行 `book-release-readiness` → `Release Readiness Review`；达到 `ready` 后再进入可选 Channel preflight 和完成 / 发布决策。必需验证缺失只能 `blocked`，optional check 仅可由明确 accountable owner 接受为 residual risk。
- 未命中强制触发条件时，5 个 book-derived Skill 继续按主风险选择最相关的 1-2 个；不要把全套门禁机械套入 docs-only、test-only、简单 UI polish、local-only script 或全新隔离代码。

这些 Skill 的结论优先写入当前 task 的 `prd.md`、`design.md`、`implement.md` 或 check summary。只有形成长期架构、API、数据模型、权限、业务规则或技术约定时，才进入 `.trellis/spec`。

---

## Trellis 调度层

- `.trellis/config.yaml`、`.trellis/workflow.md` 和 task artifacts 只定义共享 workflow gate，不标识运行平台。当前 host 与其专属生成资产决定本次执行：Codex 使用 `.codex/**`，OMP 使用 `.omp/**`；二者共存时按当前 host 选择，纯静态文件不足时标记 unknown。
- 以下规则只适用于当前 host 为 Codex 且 `.codex/**` 集成可用的项目：标准 `native` / `tdd` workflow 在有效 `codex.dispatch_mode=auto` 时，由主会话协调 phase，并按 `trellis-implement` → `trellis-check` 顺序为每项职责调度一个 Trellis role subagent；role subagent 只执行分配职责，不等于 Channel runtime。
- 以下 fallback 只适用于 Codex：`inline` 在项目或用户显式选择时由主会话直接执行；非法显式 Codex dispatch 值也会 fail-closed 到有效 Inline。必须报告并修正非法设置，fallback 生效时不得调度 Codex role subagent。
- 当前 host 为 OMP 且 `.omp/**` 集成可用时，使用 OMP 自己的 `task` worker 和生成的 Trellis agent 定义；不要把 `codex.dispatch_mode`、Codex Inline fallback 或 Codex role dispatch 套用到 OMP。以该项目生成的 OMP extension 为准。
- 同一变更职责只能由当前平台的一个 Trellis role subagent、主会话或一个 Channel worker 写入；不得对同一变更职责双重或递归 dispatch，也不得让 Channel worker 与平台 role subagent 并发写入同一 checkout。用户明确请求的独立只读 review / cross-validation 可并行进行，但不得同时充当同一 validation environment 的 controller。单个 platform role subagent 不是启动 Channel 的理由。

---


## Trellis Channel

普通任务不要使用 `trellis channel`。

仅当用户明确要求多 Agent、多模型、worker、forum、thread、并行评审、交叉验证、外部 orchestrator 协作，或在 Channel preflight 后明确确认时，才启动 Channel runtime。

### 主动 Preflight 场景

以下场景应主动调用 `trellis-channel` Skill 做 Channel preflight，但不得静默 spawn worker：

- 用户要求代码 review、提交前 review、测试验证审查、验证覆盖检查、并行评审、交叉验证或多个 reviewer 视角。
- `$trellis-check` 或项目验证后仍存在高风险验证缺口。
- GitNexus impact / detect_changes 返回 HIGH 或 CRITICAL，或提示索引 stale 且实际 diff 涉及关键流程。
- 变更跨越前端、后端、数据库、部署、测试资产、外部服务或发布流程。
- 验证失败后经过修复，需要独立复核失败原因、覆盖范围和剩余风险。
- Trellis PRD / design / implement 与实际 diff、验证结果或回滚策略需要独立一致性检查。

preflight 只输出是否推荐启用 Channel、建议 worker 角色、输入、输出、权限边界和清理计划。除非用户已明确要求 Channel，或在 preflight 后明确确认，否则不得启动 Channel runtime 或 spawn worker。

### Review / Validation 用法

Channel 适合作为代码 review、测试验证审查和交叉验证层，不替代 `$trellis-check`、项目验证命令、GitNexus、Playwright、Maestro、Chrome DevTools MCP、浏览器检查或人工最终判断。

默认 reviewer / validator worker 只读。推荐角色包括：

- `architecture-reviewer`
- `test-coverage-reviewer`
- `ui-ux-reviewer`
- `api-data-contract-reviewer`
- `release-risk-reviewer`

如果需要使用 Channel runtime：

- 调用 `trellis-channel` Skill。
- 不要仅因任务复杂、文件多或跨模块就启用 Channel。
- 同一 checkout 同一时间只允许一个 writer worker；默认所有 worker 只读。
- 同一验证环境同一时间只允许一个 validation controller；Docker、数据库迁移、浏览器 E2E、Vercel deploy 等环境敏感验证由主会话串行控制。
- worker 不得 stage、commit、archive、finish-work、push、deploy，除非用户明确授权且该 worker 是唯一 writer / controller。
- 多个 worker 都需要改代码时，优先拆 parent / child tasks 或使用独立 worktree，不在同一工作树并发写入。
- 如果 channel workflow 或 `trellis channel spawn` 提示缺少 `.trellis/agents/<name>.md`，先运行 `trellis update` 生成 channel runtime agent 定义，再继续。
- Channel 结论必须整理回 task artifacts 或 `.trellis/spec`。
- Channel runtime、events、forum、thread、原始 worker 日志默认不要提交到远程仓库。
- Channel 结束前必须检查 worker 存活状态、runtime 清理状态和 dirty path，确认没有越界写入。

---

## 目录规则

按项目策略保留或提交：

- `.trellis/spec/`
- `.trellis/lessons/`
- `.trellis/agents/`
- `.trellis/workflow.md`
- `.trellis/tasks/<task>/prd.md`
- `.trellis/tasks/<task>/design.md`
- `.trellis/tasks/<task>/implement.md`

默认不要提交：

- `.trellis/.developer`
- `.trellis/.runtime/`
- `.trellis/.cache/`
- `.trellis/worktrees/`
- `.trellis/.backup-*`
- `.trellis/channels/`
- `~/.trellis/channels/`
- `.gitnexus/`

---

## Web / Mobile 验证工具

默认继承全局 Web / Mobile 工具边界：Chrome DevTools MCP 负责 Web 运行时诊断，Playwright CLI 负责项目内 Web 可重复回归，Playwright MCP 负责探索和 locator 辅助，Maestro CLI 负责移动 / Hybrid E2E，Maestro MCP 负责设备检查和 flow 辅助，`web-ui-autotest-generator` 负责可入库 Web UI Playwright 测试资产。

项目级规则只补充触发和落地约束：

- 端到端业务流程变更：登录、注册、权限、账号空间、保存、发布、上传 / 下载、跨页面流转、多步骤流程、CRUD。
- 前后端 / API 集成变更：前端操作触发后端 API、API route / client contract、数据持久化、表单提交、列表查询、错误态或权限校验。
- Trellis `prd.md` / `design.md` / `implement.md` / `$trellis-check` 的验收标准包含 UI、E2E、API、回归验证或发布前 smoke。
- 用户可见 bug 修复后需要回归验证。
- 合并到 staging、发布 preview 或 release 前，且改动不只是文档。
- GitNexus impact / detect_changes 为 HIGH / CRITICAL，且影响 Web、API 或发布流程。

执行约束：

- 需要 Web 回归时，先检查项目已有 Playwright 依赖、配置、scripts 和 E2E 目录；未安装时按全局规则询问是否安装到项目 devDependency。
- 需要 Maestro 时，按全局 Java 17+ -> Maestro CLI -> Maestro MCP 顺序检查；本项目已有移动测试文档、设备矩阵、appId / bundleId、模拟器或云测策略时，以项目事实为准。
- 需要根据 BDD 生成或维护 Maestro flow 时，加载 `maestro-mobile-e2e` Skill；flow 资产固定落到 `maestro/flow/`，并在最终输出报告 `Maestro Flow Assets` 状态。
- API、Web E2E、Mobile E2E 或 Hybrid E2E 的模式、mock、重跑顺序、报告命名、Markdown 汇总内容和状态枚举默认遵循全局 AGENTS 与 `project-validation` Skill。
- 项目级最低报告门禁：只要 Playwright、Maestro、API / integration 或 unit test runner 产生了需要作为本轮证据保留的原生报告，就必须在下一次可能清空输出的运行前保留该次运行的命名报告和同 stem 中文 Markdown 汇总；API、Playwright 和 Maestro 的正式报告文件名必须包含当前分支的 `branch_slug`，其中 `/`、空格和特殊字符统一替换为 `_`；`Final Test Report` 只表示报告文件是否生成，`Final Full Rerun` 才表示最终是否全绿。多轮调试可以保留多份本地命名报告快照，但最终结论只以最后一次计划范围内运行判断。
- 正式报告要作为 PR 证据或被知识库读取时，按 `project-validation/references/validation-evidence-contract.md` 记录 `Evidence Source`、repository key、原始 source ref、完整 commit SHA、worktree state、trigger、`Source Revision`、`Environment Alignment` 和 `Evidence Publication`，并用 Schema 校验 `.evidence.json`。`branch_slug` 只用于文件名；dirty 本地结果只能是 `local-only`；CI evidence 使用 `Evidence Source: ci`、clean checkout 和最终 PR head SHA，目标系统接收后才是 `published`；知识库服务器结果必须记录精确 revision set。普通本地诊断不强制生成 evidence sidecar。
- 项目级 spec 可以允许诊断轮次使用 stdout-only、terminal-only 或轻量 reporter，但不得把这类命令当作最终正式验证证据。API / Web E2E / Mobile E2E / Hybrid E2E 一旦进入正式验证范围，收尾前必须使用项目 reporter 生成命名报告；没有原生 reporter 的 API 自定义脚本必须捕获 stdout / stderr / exit code 为 `tests/api/reports/` 下的时间戳 raw report 并生成同 stem 中文 Markdown 汇总；Playwright `--reporter=list` 和 stdout-only Maestro run 只能算诊断或定点重跑。
- Playwright 的正式报告快照目录仍是 `tests/e2e/reports/html/`，且 Markdown 汇总必须跟随命名后的 `playwright-report-*-{branch_slug}-*.html` stem；不得用 `results.md`、`result.md`、`junit.md` 或 `index.md` 满足 `Run Summary MD: generated`。Playwright HTML reporter 的 `outputFolder` 应使用 runner 临时目录 `tests/e2e/reports/.playwright-html-current/`，不要把需要保留的正式命名报告放进该目录，因为下一次 Playwright 运行可能清空它。
- API / integration 默认正式快照目录为 `tests/api/reports/`，正式报告 stem 使用 `api-report-{suite_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}`；unit test 报告默认继承项目配置。如果 runner 使用会重建的 `coverage/`、`test-results/`、固定 `junit.xml` 或 `current` 输出目录，必须先复制 / 提升到项目归档目录或 `tests/unit/reports/` 的时间戳快照，不能把 runner 托管目录当作正式报告。
- API / integration 的中文 Markdown 汇总必须提供 URI 覆盖矩阵；每条覆盖范围描述都要映射到具体 `method + URI path`、测试脚本 / case、期望状态码或副作用，以及关联 `.feature` / contract / schema。缺少 URI 的覆盖项标记 `blocked` 或 `missing-uri`，不得只用脚本名或业务概括替代 endpoint 证据。
- 最终输出或 Trellis check summary 必须报告 `E2E Mode`、`Mock Strategy`、`Final Test Report`、`Run Summary MD`、`Targeted Rerun` 和 `Final Full Rerun` 状态；涉及 PR / 知识库证据时，额外报告 `Evidence Source`、`Source Revision`、`Environment Alignment` 和 `Evidence Publication`。
- MCP 项均为 check-and-guide；项目模板不复制 MCP 配置，不把 MCP 诊断当作项目测试通过。
- 最终输出按全局状态枚举报告相关工具、执行命令、阻塞原因和 fallback。

---

## Mobile / Hybrid E2E 测试资产

Maestro flow 是可入库测试资产；详细生成、命名、报告和真机排障流程由 `maestro-mobile-e2e` Skill 承接。

项目级 gate：

- 只有 Mobile / Hybrid 用户旅程需要设备级回归时，才从 BDD 场景生成或维护 Maestro flow。
- 默认 flow 根目录为 `maestro/flow/`；平台差异明显时使用 `maestro/flow/ios/` 和 `maestro/flow/android/`；全量回归 / smoke flow 固定使用 `smoke.yml`。
- 每个 flow 必须追踪源 `.feature`、场景名、平台范围和测试模式。
- 缺少稳定选择器、账号、环境、设备、app binary、appId / bundleId、数据准备或清理策略时，不生成脆弱 flow；标记 `Maestro Flow Assets: blocked`。
- Maestro 原生报告和同 stem 中文 Markdown 汇总按全局规则与 `maestro-mobile-e2e` 写入 `.maestro/reports/`，正式报告 stem 使用 `maestro-report-{flow_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}`。

---

## Web UI / E2E 测试资产

普通 UI 检查优先使用项目已有验证、Chrome DevTools MCP 诊断和 Playwright CLI 回归；只有需要把 Web UI 回归路径固化为仓库内可维护测试资产时，才启用 `web-ui-autotest-generator`。

项目级 gate：

- 启用前先加载 `project-validation`，并使用其中的 Web UI 测试资产路径契约。
- 优先沿用项目已有 Playwright / Cypress / 测试目录 / fixture / mock / CI 约定，不为默认模板切换测试框架。
- 可入库 JSON 资产必须位于 `tests/e2e/manifest/`；标记 `generated` / `coverage-only` 前，确认项目根目录没有残留 `ui-test-manifest.json`、`ui-selector-audit.json`、`ui-test-coverage.json`。
- 没有稳定账号、环境、数据准备、清理策略或业务规则时，只输出阻塞说明，不生成脆弱测试；只有用户明确同意时才补充产品代码选择器。
- Playwright 正式 HTML report 和 Markdown 汇总遵循全局规则，默认进入 `tests/e2e/reports/html/`，正式报告 stem 使用 `playwright-report-{feature_file_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}`；Playwright reporter 临时输出目录默认使用 `tests/e2e/reports/.playwright-html-current/`；trace、video、screenshot、默认 `index.html` 和 repair plan 默认不入库。

---

## SEO / GEO 发布检查

`seo-geo` 是公开 Web 资产的可选搜索可见性专项 Skill；详细 audit 流程由该 Skill 承接，不替代项目原生验证、Chrome DevTools MCP、Playwright CLI、发布检查或人工内容评审。

项目级 gate：

- 仅在用户明确要求 SEO/GEO/AI search visibility，或变更影响公开网站、落地页、文档站、产品页、营销页、公开博客 / README，或验收标准包含 crawl/indexing/schema/meta 时启用。
- 内部后台、登录后页面、API、CLI、移动 App、纯后端、测试资产、文档内部重排或纯 Web 回归不触发 `seo-geo`。
- 没有公网 URL 或 preview URL 时，只能做源码 / HTML 静态检查，并报告 `SEO/GEO: static-only` 或 `blocked`。
- 不得把 DataForSEO、Search Console、付费报告、真实账号、密钥、PII 或生产敏感 URL 写入仓库、日志、截图、测试或报告。
- 最终输出或 Trellis check summary 必须报告 `SEO/GEO`: `audited` / `static-only` / `blocked` / `skipped` / `not-needed`。

---

## 验证命令

优先使用当前项目已有命令：

1. 项目 `AGENTS.md` 或更深层规则定义的命令。
2. README、package scripts、Makefile、CI 配置中的命令。
3. `project-validation` Skill 根据修改范围建议的命令。

常见回退命令：

```bash
rtk npm run lint
rtk npm run build
rtk ruff check .
rtk ruff format .
rtk ty check .

# 测试命令先按全局 rtk 与报告型测试 Gate 判断；需要报告落地时优先原生命令
npm run test
pytest
# uv 管理的项目才使用：
uv run pytest
# Poetry / PDM 等项目按项目脚本或工具链执行，例如：
poetry run pytest
pdm run pytest

go test ./...
```

如果 `rtk` 不可用，回退为项目原生命令；如果报告型测试使用 `rtk` 后报告缺失、陈旧或不可证明，立即用原生命令复验。Python 项目应按实际包管理器选择 `pytest`、`uv run pytest`、`poetry run pytest`、`pdm run pytest` 或项目脚本。

---

## Lessons

出现 bug 修复、回滚、工具判断错误、工作流阶段错误、验证失败、GitNexus 影响分析不匹配或 Channel / worker 上下文丢失时，调用 `lessons-record` Skill。

Trellis 项目默认采用 `lessons-record` Skill 定义的分层结构：`.trellis/spec/lessons.md` 只保存短入口和高优先级摘要，完整 lesson 写入 `.trellis/lessons/index.md`、`topics/` 或按需归档。非 Trellis 项目若已在 `AGENTS.md`、`docs/lessons.md` 或 README 声明分层 lessons 结构，则遵循项目结构；否则才默认写入 `docs/lessons.md`。
