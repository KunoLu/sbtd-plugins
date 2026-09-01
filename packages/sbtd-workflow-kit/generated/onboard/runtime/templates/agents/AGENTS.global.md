# Codex 全局规则

## 优先级

- 当前仓库的 `AGENTS.md` 优先于全局规则。
- 当前目录更深层的 `AGENTS.md` 优先于上层规则。
- 项目已有规范、测试、配置和工作流优先于通用假设。
- 不要假设可选工具一定可用。
- 优先采用最小、可验证、可回滚的修改。
- 除非用户明确要求，不要扩大任务范围。

---

## 命令执行规则

- 执行 shell / terminal 命令时，优先使用 `rtk` 前缀。
- 如果 `rtk` 不可用，则回退到原生命令。
- 不要因为 `rtk` 不可用而中止任务。
- 当工作流检查、onboard 或首次执行命令时确认用户电脑没有可用 `rtk`，主动说明：`rtk` 用于压缩 terminal 命令输出、减少上下文占用，不改变底层命令语义。
- 说明后询问用户是否协助安装；用户确认后再执行安装。安装成功后复验 `rtk --version` 和 `rtk gain`，再继续任务。
- 用户拒绝安装或安装失败时，继续使用原生命令，并在最终输出说明 `rtk` 已回退或阻塞原因。
- 执行 unit test、API / integration test、Playwright Web E2E、Maestro Mobile / Hybrid E2E，或任何需要生成 / 刷新报告文件、coverage、JUnit、HTML、JSON、trace、raw report 的命令前，必须先评估是否使用 `rtk`。如果本轮验证需要依赖落地文件作为证据，默认优先使用原生命令或项目明确的 no-cache / report-safe 命令；只有确认 `rtk` 不会缓存、回放或跳过文件副作用时才加 `rtk`。
- 如果用 `rtk` 执行测试命令后，预期报告文件未生成、mtime / size 未变化、内容不对应本轮命令，或输出显示 cache hit / replay / skipped 写入，立即用原生命令重跑并以原生命令结果为准。
- 最终输出或 check summary 要说明 `rtk`: `used` / `skipped-for-report` / `fallback-native` 及原因；不要让 `rtk` 缓存输出成为测试通过或报告生成的唯一证据。

示例：

```bash
rtk git status
rtk rg "pattern"
rtk npm run build

# 报告型测试通常先按上面的规则评估，必要时使用原生命令
# branch_slug / stamp 按正式报告命名规则生成
npm run test
npx playwright test
maestro test --format junit --output ".maestro/reports/maestro-report-smoke-${branch_slug}-${stamp}.xml" maestro/flow/smoke.yml
```

---

## 交互压缩工具

`rtk` 和 `caveman` 都用于降低上下文 / token 压力，但作用层不同：

- `rtk` 是命令输出压缩工具，作用于 shell / terminal 命令执行层，默认按“命令执行规则”优先使用。
- `caveman` 是 Agent 回复压缩 Skill，作用于对话输出层；安装后默认只表示可用，不代表每轮自动启用。

### caveman

- 如果工作流检查或 onboard 发现用户级全局 Skill 中没有 `caveman`，主动说明：`caveman` 用于压缩 Agent 回复、减少输出 token，不改变代码、测试、验证、Trellis 阶段、GitNexus 分析或工作流决策。
- 说明后询问用户是否协助安装；用户确认后安装到用户级全局 Skill 环境，安装后重新检查 `caveman/SKILL.md` 是否可见。
- 手动模式与自动模式分开管理。外部 `caveman` Skill 只负责手动模式的表达风格、强度和手动退出；`auto-lite` 自动生命周期由本全局规则负责，只借用外部 Skill 的 `lite` 表达规则，不把自动状态写回或视为手动模式。
- 手动模式保持外部 Skill 的原有行为：只有用户说 `/caveman`、`use caveman`、`caveman mode`、`少说一点`、`减少 token`、`压缩输出` 或同等明确请求时才进入；用户未指定等级时使用 `full`，持续到用户说 `normal mode`、`stop caveman` 或会话结束。
- 自动模式要求 `caveman` Skill 当前可见，且当前回复是重复、非阻塞、无需用户决定的中间状态更新。若 runtime 明确暴露 caveman 配置，则显式 `off` 禁止自动和手动模式；没有暴露配置或配置缺失时按 `auto` 处理，不得把“无法证明不是 off”解释为 `off`。
- 同一主要目标维护任务级临时状态：`progressUpdateCount` 记录中间进度更新数，`toolResultCount` 记录已汇总的独立命令、diff、日志、文件读取或工具结果数，`autoLiteEligible` 是达到阈值后的单调资格锁存，`autoLiteActive` 记录是否已经自动进入并发送首次提示，`taskAutoExit` 和 `sessionAutoExit` 记录用户退出。状态只存在于当前会话上下文，不写入项目文件。
- 满足以下任一可观察条件时，必须立即设置 `autoLiteEligible=true`；同一主要目标内不得再改回 `false`，也不得附加“后续仍需继续”或“后续主要是重复状态”等主观条件：
  - `progressUpdateCount >= 3`；保护区内的中间进度更新也计数。
  - `toolResultCount >= 5`；结果不要求连续出现，保护区内汇总的结果也计数。
  - 任务已明确属于长任务或上下文压力较大。
  - 自动化、daily check、大型 review 或验证排障已经进入重复轮次。
- `autoLiteEligible=true` 后，下一条非保护区、非阻塞且无需用户决定的重复中间状态更新必须进入 `auto-lite`，设置 `autoLiteActive=true`，并在同一条回复内只提示一次“后续重复状态更新将自动使用 lite 压缩；说 normal mode 可恢复完整输出并在本任务内停用自动压缩”。首次自动进入时的一次性提示是外部 Skill“不宣布模式”规则的唯一例外，不得单独增加一条提示消息。
- 自动模式只能使用 `auto-lite`，不得自动进入 `full`、`ultra`、文言或其他更激进等级；只影响对话表达，不改变代码、工具调用、测试、验证、Trellis 阶段、GitNexus 分析或 workflow 决策，不得停止或跳过必须的中间状态更新，工具调用超过 60 秒时仍要按全局规则报告进度。
- 以下内容属于完整输出保护区，必须临时使用正常清晰表达：安装确认、权限确认、破坏性或不可逆操作确认、安全 / 隐私 / 密钥 / 生产数据风险、多步骤顺序或否定语义存在歧义、需求最终确认和用户选择、PRD / design / implement review gate、BDD / PRD / ADR / Trellis task artifacts、README、AGENTS 模板正文、失败原因、剩余风险、最终验证报告和最终答复；用户要求澄清、详细说明或重复提问时也必须完整回答。
- 保护区只覆盖当前回复的表达风格，不得清除计数器、`autoLiteEligible` 或 `autoLiteActive`。保护区结束后，若仍是同一主要目标且没有自动退出，下一条普通重复状态必须恢复 `auto-lite`，不重新计数、不重新判断阈值、不重复首次提示；`详细说明` 或 `展开说明` 只覆盖当前答复。
- 用户说 `normal mode`、`stop caveman`、`恢复完整输出`、`不要压缩` 或 `本任务不要自动压缩` 时，无论当前处于手动还是自动模式，都立即恢复正常输出并设置 `taskAutoExit=true`；当前任务内阈值不得触发自动重入。
- 只有用户明确说 `本任务恢复自动压缩` 或 `重新启用自动压缩` 时才清除 `taskAutoExit`。清除后保留原有计数器和资格锁存；若此前已 eligible 或 active，下一条普通重复状态直接进入或恢复 `auto-lite`。用户明确启动 `/caveman` 只进入手动模式，不清除任务级或会话级自动退出。
- 用户说 `本会话关闭自动压缩` 时设置 `sessionAutoExit=true`；只有用户明确说 `本会话重新启用自动压缩` 时才清除。会话级退出优先于任务级状态，但不阻止用户在配置不是显式 `off` 时手动启动 `/caveman`；退出手动模式后仍不得自动重入。
- 只有用户建立新的主要目标时，才重置 `progressUpdateCount`、`toolResultCount`、`autoLiteEligible`、`autoLiteActive` 和 `taskAutoExit`；`sessionAutoExit` 继续有效。`继续`、`确认`、授权、状态询问、故障恢复、回答 Agent 问题、补充同一目标的约束或证据、同一 parent outcome 下增加相关子任务，都属于同一主要目标，不得重置。
- context compaction、历史 turn 归档、恢复同一 session 或 handoff 不构成新的主要目标。为同一目标生成上下文摘要或 handoff 时，必须保留 `autoLiteEligible`、`autoLiteActive`、`taskAutoExit`、`sessionAutoExit` 和首次提示是否已发送；若摘要已证明任务处于长时间重复阶段但精确计数不可恢复，恢复为 `autoLiteEligible=true`，不得重置为未达阈值。
- 自动模式优先级固定为：runtime 显式 `off` > `sessionAutoExit` > `taskAutoExit` > `autoLiteEligible` / `autoLiteActive`。阈值不能覆盖退出状态；手动模式生命周期独立，除 runtime 显式 `off` 外不被自动状态改写。
- `caveman-compress` 等会改写长期文档或记忆文件的能力只在用户明确要求压缩文档时使用，不作为默认工作流步骤。

---

## 工具可用性判断

只有存在直接或强证据时，才认为某个工具可用。

### Codex 插件 / Connector / 延迟工具发现

Codex 可能通过本地插件、remote plugins、connectors、MCP 或 `tool_search` 暴露延迟加载工具。工具可用性仍以当前会话的强证据为准：

- 只有当前工具列表、`tool_search` 结果、MCP 可见性检查或项目文档明确暴露了对应 callable tool，才认为该 plugin / connector / MCP 能力可用。
- 如果用户要求使用某个库、框架、云服务、插件或 connector 的专门能力，且当前会话存在 `tool_search`，优先用 `tool_search` 发现延迟工具；未发现时再按任务需要使用项目文件、官方文档或普通检索。
- Remote plugin catalog、marketplace 行、已安装提示或本地 / 远端版本展示只说明候选能力存在，不等于当前会话已授权、已安装或已可调用。
- 只有用户明确要求使用某个具体 plugin / connector，且安装工具返回精确匹配时，才请求安装；不要为相邻能力、宽泛推荐或“看起来有用”的工具静默安装。
- ChatGPT-hosted MCP、OAuth、session authentication、connector token、cookies 和账号状态只能通过当前 Agent / connector 的受控工具使用；不要复制、打印、持久化或写入仓库、日志、截图、报告和 MCP 配置示例。
- Codex 可能通过系统代理处理认证和 API 流量；除非用户明确要求，不要替用户改操作系统代理、PAC、WPAD 或企业网络配置。网络失败时按可见错误诊断，并区分 runtime 代理行为和项目代码问题。
- 不要因为上游支持新的 remote plugin、connector、MCP transport 或 session auth 能力，就静默改写项目配置、用户级 MCP 配置、CI 配置或 hooks。
- 项目级 plugin / marketplace 配置会并入 catalog；某个 project marketplace 无效时，不得据此把其余有效 plugin 判定为不可用。
- 可选 MCP 服务器的工具发现可能受启动宽限期约束；首轮工具列表缺少某个已配置 optional MCP 不等于该 server 未安装，应再做一次可见性检查后再判定 missing。不要静默改写 `mcp_optional_startup_grace` 或 MCP server 配置。
- Codex extension 可能在 MCP tool result 到达模型前检查或替换结果；不要把 MCP 原始响应当作模型一定看到的内容，也不要因 extension 存在就静默改写 MCP 配置。

### Trellis

高优先级未初始化提示：

- 如果已经确认当前目录是目标项目根目录，且项目根目录存在项目级 `AGENTS.md`，但项目根目录不存在 `.trellis/`，必须告诉用户：当前项目还没有进行 `trellis init` 操作。
- 默认不要替用户执行 `trellis init`。必须说明该命令包含项目初始化操作，请用户自行在命令行中执行，或明确进入 `sbtd-workflow-onboard` 的 `init` / `reset` 流程。

```bash
trellis init -u your-name
```

例外：仅当用户明确进入 `sbtd-workflow-onboard` 的 `init` / `reset`，且已满足该 Skill / `REFERENCE.md` 的 Trellis CLI、`.trellis/` 缺失、username / platform 确认条件时，onboard workflow 可按其脚本执行 Trellis 初始化与后置 bootstrap 检查；不要把这条例外扩展到普通项目工作流。

满足以下任一条件时，认为 Trellis 可用：

- 存在 `.trellis/`
- 存在 `.trellis/workflow.md`
- 存在 `$trellis-*`
- 项目级 `AGENTS.md` 明确说明使用 Trellis

如果 Trellis 可用：
- 调用 `trellis-workflow` Skill。
- 遵循 .trellis/workflow.md。
- 不手动跳过 Trellis 阶段。
- 不绕过项目级 Trellis 规则。

### Trellis 调度边界

- `.trellis/config.yaml`、`.trellis/workflow.md` 与当前 task artifacts 只定义共享 workflow gate，不标识运行平台。必须由当前 host 与其专属生成资产判定：Codex 使用 `.codex/**`，OMP 使用 `.omp/**`；二者共存时按当前 host 选择，纯静态文件不足时标记 unknown。
- 以下 Codex 规则只适用于当前 host 为 Codex 且 `.codex/**` 集成可用的项目：`native` / `tdd` workflow 在有效 `codex.dispatch_mode=auto` 时，由主会话协调 phase，并按 `trellis-implement` → `trellis-check` 的必经顺序为每项职责调度一个 Trellis role subagent；role subagent 只执行分配职责，不等于启动 `trellis channel`。
- 以下 Codex fallback 规则不适用于 OMP：`inline` 是项目或用户显式选择的 Codex 主会话模式；非法显式 Codex dispatch 值也会 fail-closed 到有效 Inline。必须报告并修正非法设置，fallback 生效时不得调度 Codex role subagent。
- 当前 host 为 OMP 且 `.omp/**` 集成可用时，使用 OMP 自己的 `task` worker 和生成的 `trellis-implement` / `trellis-check` agent 定义；不得读取、写入或推断 `codex.dispatch_mode` / Codex Inline fallback，必须以该项目生成的 OMP extension 为准。
- Channel 是跨平台的持久、多轮、可中断、共享 event log 的协作 runtime；仅在用户明确请求或 Channel preflight 后明确确认时启动。
- 同一变更职责只能有一个写入执行者：当前平台的一个 Trellis role subagent、主会话或一个 Channel worker；不得对同一变更职责双重或递归 dispatch。用户明确请求的独立只读 review / cross-validation 可并行进行，但不得同时写入或充当同一 validation environment 的 controller。Codex 仅可使用其有效模式的执行者，OMP 仅可使用其生成的 worker 机制。


无论 Skill 是否可用，都必须遵守以下最低规则：

- 不要在未读取 `.trellis/workflow.md` 的情况下改变任务状态。
- 不要在未读取相关 `.trellis/spec` 的情况下实现长期规则相关修改；其中 `.trellis/spec/lessons.md` 只作为短入口和高优先级摘要。
- 不要默认读取完整 `.trellis/lessons/**`；先通过 `.trellis/lessons/index.md`、tags、错误信息或当前任务主题按需检索，再读取命中的 topic / archive 文件。
- 如果存在当前任务产物，优先读取 `prd.md`、`design.md`、`implement.md`。
- 升级 Trellis CLI 后，如果项目已有 `.trellis/`，先运行 `trellis update` 刷新生成脚本和 filesystem-safety guard；如果更新涉及 SessionStart、PreToolUse 或其他 hook 配置，在验证新会话身份或 hook 行为前重启对应 Agent host / IDE。
- 对 `trellis uninstall`、`trellis ablate` / `trellis restore`、`task.py archive`、`task.py rename`、`task.py start`、`task.py set-branch` / `set-scope` / `set-meta`、subtask 以及 `trellis channel create/spawn/rm` 等会删除、移动、整仓移除或按名称解析路径的操作，不要用环境变量、手工路径、`..` 或仓库外绝对路径绕过 Trellis 的 dirty-data、manifest ownership、safe-name 和 active-task pointer containment guard；guard 拒绝或把越权 pointer 降级为无任务时，先报告原因并让用户确认备份、清理或重试方案。升级后不要假设 `trellis update` 会改写既有 session pointer；若任务上下文指向项目外路径，按无任务处理，不要继续读取该路径。
- 当 per-turn breadcrumb 为 `[workflow-state:task_error]` 时，不要创建或激活另一个任务；先检查并修复现有 `task.json`（必须是带非空 `status` 的合法 JSON 对象），无法安全判断 status 时先询问用户。
- 对 sub-agent-dispatch 平台，空的或仅 seed 的 `implement.jsonl` / `check.jsonl` 会使 `task.py validate` 失败、`task.py start` 拒绝；只有用户明确要求空上下文启动时才使用 `--allow-empty-context`。

### GitNexus

GitNexus 通过全局安装的 `gitnexus-mcp` 提供能力，不作为 Skill 管理。

仅当同时满足以下条件时，才使用 GitNexus：

1. GitNexus MCP 可用。
2. 当前项目已建立 GitNexus 索引。

强证据包括：

- MCP 工具列表中存在 GitNexus 相关工具。
- 存在 `.gitnexus/`。
- `gitnexus status` 显示已有索引。
- `gitnexus index` 已经成功执行过。
- 项目级 `AGENTS.md` 明确说明 GitNexus 已启用。

使用规则：

- 修改代码前，优先通过 GitNexus MCP 执行影响分析。
- 修改代码后，优先通过 GitNexus MCP 执行变更检测。
- GitNexus 只作为影响分析和变更验证辅助，不替代 Trellis 任务产物、测试或代码评审。
- 如果项目存在 `.gitnexusrc` 或需要指定默认分支，遵循项目配置；必要时使用 `gitnexus analyze --default-branch <branch>` 重新分析。
- 手工检查 GitNexus 索引元数据时，优先查看 `.gitnexus/gitnexus.json`；`.gitnexus/meta.json` 是兼容镜像，分支索引下也可能存在 `branches/<branch>/gitnexus.json` 和 `branches/<branch>/meta.json`。不要仅因其中一个文件缺失就判断索引不存在；优先用 `gitnexus status`、MCP 输出和实际 metadata 内容交叉确认。
- 当 `gitnexus status`、MCP `list_repos` / `context` / `detect_changes` 或其他 GitNexus 输出提示索引 stale、`commitsBehind > 0`、或“索引落后 HEAD ... 个 commit”时，不要直接依赖过期结果；先按命令执行规则尝试在项目根刷新索引。
- 刷新索引时优先使用项目约定命令或本地 runner，例如存在 `.gitnexus/run.cjs` 时使用 `node .gitnexus/run.cjs analyze`；否则使用项目文档要求的 `gitnexus analyze` / `npx gitnexus analyze`。如果项目指定默认分支或 `.gitnexusrc`，必须带上相应配置。
- 如果 `analyze` 因沙箱、网络、native crash、索引损坏、耗时限制或权限问题失败，必须在最终输出中说明尝试的命令、失败原因、GitNexus 结果只能作为 advisory，以及实际用哪些 diff / 测试 / 构建 / 运行时检查替代。
- 如果 `analyze` 成功但 MCP 仍报告 stale，按 MCP 缓存或会话未刷新处理；重新检查 CLI status，必要时说明需要重启 / reload MCP 或新会话后再依赖 MCP 结果。
- 不要默认假设 GitNexus hook 会自动刷新索引；除非项目文档或用户明确要求并接受 commit / merge 被阻塞和索引写入风险，否则不要新增自动运行 `gitnexus analyze` 的 Git hook。
- 当影响分析结果存在同名符号、跨文件歧义或输出过大时，优先使用 GitNexus 提供的 `uid` / `file` / `kind` 约束和分页 / summary-only 能力缩小范围。
- 通过 GitNexus MCP 枚举已索引仓库时，`list_repos` 可能返回分页对象；使用 `limit` / `offset` 翻页直到 `pagination.hasMore` 为 false，不要把单页结果当作完整仓库列表。
- 如果项目启用了多分支索引，分析、查询和变更检测必须明确目标 branch / 默认分支，不要混用不同分支的索引结果；跨分支结论必须回到实际 diff 或对应分支源码复核。
- PDG-backed impact、taint analysis、`trace` 等高级图分析能力只作为显式 opt-in 辅助。使用前确认索引已用对应能力生成，记录采用的是默认 call-graph 模式还是 PDG / taint / trace 模式，并把结论与源码、测试和路由 / 调用链交叉核对。
- GitNexus MCP 可通过不同 transport 暴露；是否使用 stdio、Streamable HTTP 或 legacy SSE 由当前 Agent / IDE 配置决定。不要因为上游支持新的 MCP transport 就静默改写项目或用户级 MCP 配置。
- 对跨服务 API、HTTP route / consumer、gRPC 或前后端调用链的结论，必须回到实际路由、客户端调用和 diff 交叉核对。
- 如果需要移除 GitNexus 集成，优先使用 `gitnexus uninstall` 的 dry-run 查看将删除的 MCP 配置、Skill 和 hooks；只有用户明确确认后才加 `--force`，并复核配置 diff。
- 可选 tree-sitter grammar 缺失、跳过或回退构建不一定代表 `gitnexus analyze` 失败；若输出提示 optional grammar、prebuild / toolchain fallback 或 `GITNEXUS_SKIP_OPTIONAL_GRAMMARS`，把相关语言覆盖作为风险记录，并结合实际源码和查询结果复核。
- 大仓库分析中出现 skipped large files、内存墙、FTS 损坏或 repair 提示时，把这些作为索引完整性风险；需要时运行 GitNexus 提供的修复或重建命令后再依赖结果。
- GitNexus CLI 的 Node 运行时下限以当前官方 npm `engines.node` / release 为准；native load 或 analyze 失败时先核对本机 Node 是否满足该下限，再判断索引损坏。
- CLI 升级若改变 receiver / import / interface 解析或图边语义，既有索引不会自动带上新边；升级后先按项目约定重新 `gitnexus analyze`，再依赖 MCP 结果。
- 不要配置或依赖已移除且原本非功能的 group matching 旋钮：`matching.bm25_threshold`、`matching.embedding_threshold`、`detect.embedding_fallback`、`gitnexus group sync --skip-embeddings`、MCP `group_sync` 的 `skipEmbeddings`。
- GitNexus MCP 的 repository allowlist 与 fail-closed 只读是两类限制：当前仓库不在 allowlist 内时，GitNexus MCP 对该仓库不可用，不要调用 MCP 读或写工具，也不要把 MCP 结果当作可读证据；fail-closed 只读时不要走 MCP 写入路径。二者都不得跳过 CLI `gitnexus analyze` 或项目约定的索引刷新。`uninstall --force` 仍须用户明确确认。
- 不要默认使用 `gitnexus analyze --self-commit`；除非用户明确要求 GitNexus 提交 AGENTS.md / CLAUDE.md 等 agent guide 变更。
- Codex plugin marketplace、GitNexus hooks 或 `.agents/skills/` 中由 GitNexus 镜像出的 Skill 副本，不等于全局 `gitnexus-mcp` 已可用；不要把这些副本提交为项目 canonical Skill，除非项目明确设计要追踪它们。
- `impact` / `context` 若标记 incomplete 或因 output budget 截断，不得把空结果解释为“无依赖 / 无调用方”。

如果 GitNexus MCP 不可用或项目未建立索引：

- 跳过 GitNexus。
- 不阻塞任务。
- 不假设索引存在。
- 仅在该判断影响任务风险时，在最终输出中说明已跳过。

### Web / Mobile 验证工具

Chrome DevTools MCP、Playwright CLI、Playwright MCP、Maestro CLI、Maestro MCP 和 `web-ui-autotest-generator` 各自职责不同，不互相替代。

- Chrome DevTools MCP：Web 运行时诊断、真实 Chrome 检查、console / network / storage / performance trace / screenshot 证据；不作为 CI 测试通过依据。
- Playwright CLI / `@playwright/test`：项目内 Web E2E、Web 回归和 CI gate 的执行器。
- Playwright MCP：agentic Web 探索、可访问性快照和 locator 辅助；不替代项目内 `playwright test`。
- Maestro CLI：Android / iOS / React Native / Flutter / Hybrid App E2E 和可选 Chromium Web smoke 的执行器。
- Maestro MCP：依赖 `maestro mcp` 的 agent 增强入口，用于设备检查、view hierarchy、截图、flow 辅助，以及终态 Cloud per-flow run 的状态与 artifact 诊断；不单独替代 Maestro CLI。
- `web-ui-autotest-generator`：Playwright 测试资产生成、选择器审计和覆盖率报告；执行底座仍是项目内 Playwright CLI。
- `maestro-mobile-e2e`：从 BDD `.feature` 场景生成或维护可入库 Maestro Mobile / Hybrid flow 资产，并处理 Maestro 报告路径、最终运行汇总和按需排障 lesson；执行底座仍是 Maestro CLI。

涉及 Web UI、路由、表单、登录态、权限、跨页面流程、API 集成、浏览器回归、移动 App E2E、Hybrid App、发布前 smoke 或 Trellis 验收时，必须主动判定相关工具状态：

- `Chrome DevTools MCP`: `diagnosed` / `inspected` / `blocked` / `skipped` / `not-needed`
- `Playwright MCP`: `explored` / `locator-assisted` / `blocked` / `skipped` / `not-needed`
- `Playwright CLI`: `available` / `installed` / `missing` / `skipped-by-user` / `blocked`
- `Playwright Web Tests`: `run` / `failed` / `blocked` / `skipped`
- `Java`: `available` / `installed` / `missing` / `incompatible` / `blocked` / `skipped-by-user`
- `Maestro CLI`: `available` / `installed` / `missing` / `skipped-by-user` / `blocked`
- `Maestro MCP`: `available` / `configured` / `unavailable` / `blocked` / `skipped`
- `Maestro Mobile`: `run-local` / `run-cloud` / `blocked` / `skipped` / `not-needed`
- `Maestro Web Smoke`: `run` / `blocked` / `skipped` / `not-needed`
- `Maestro Flow Assets`: `generated` / `reused` / `blocked` / `skipped`
- `Web UI 测试资产`: `generated` / `coverage-only` / `blocked` / `skipped`
- `Knowledge Ingest`: `run` / `partial` / `blocked` / `not-needed`
- `Cross-repo context`: `complete` / `contract-only` / `environment-only` / `missing` / `not-needed`
- `API Contract`: `verified` / `user-provided` / `stale` / `missing` / `not-needed`
- `E2E Mode`: `full-stack` / `contract-backed` / `mock-backed` / `app-mocked` / `smoke-only` / `backend-only` / `blocked` / `not-needed`
- `Mobile Platform Scope`: `ios` / `android` / `both` / `hybrid` / `not-needed`
- `Mock Strategy`: `none` / `contract-backed` / `user-approved` / `blocked` / `not-needed`
- `Final Test Report`: `generated` / `blocked` / `not-supported` / `not-needed`
- `Run Summary MD`: `generated` / `blocked` / `not-needed`
- `Targeted Rerun`: `passed` / `failed` / `blocked` / `not-needed`
- `Final Full Rerun`: `passed` / `failed` / `blocked` / `skipped-with-risk` / `not-needed`
- `Evidence Source`: `developer-local` / `ci` / `knowledge-server` / `not-needed`
- `Source Revision`: `exact` / `dirty` / `unknown` / `not-needed`
- `Environment Alignment`: `verified` / `unverified` / `mismatch` / `not-needed`
- `Evidence Publication`: `local-only` / `published` / `blocked` / `not-configured` / `not-needed`
- `SEO/GEO`: `audited` / `static-only` / `blocked` / `skipped` / `not-needed`

跨仓、mock 与报告规则：

- 前后端分仓、跨服务、Web + API、Mobile + API 或 Hybrid 链路不完整时，先确认 contract、环境、账号、数据、选择器、设备和 app artifact；缺关键事实时标记 `missing` 或 `blocked`，不要生成猜测型 `.feature`、mock 或测试。
- mock 只能基于 API contract、schema、真实响应样例、既有 fixture、launch arguments 或用户明确确认；mock-backed / app-mocked / contract-backed 测试不能报告为 full-stack 通过。
- API / Web E2E / Mobile E2E / Hybrid E2E 调试轮次可以保留多份带业务名、分支名和时间戳的本地报告快照；最终结论仍以最后一次计划范围内运行记录 `Final Full Rerun`。一旦 Playwright 或 Maestro 运行产生 runner 原生报告，或 API / integration / unit runner 生成了本轮需要保留的原生报告，无论最终全量是否通过，都必须在收尾前把该次运行提升 / 复制为命名报告，并生成同目录同 stem 的 Markdown 汇总。`Final Test Report` 表示报告文件是否已生成，`Final Full Rerun` 才表示最终全量是否通过；不要因最终未全绿而跳过报告文件。
- 正式验证范围不能由是否已经产生 runner 报告倒推决定。API / Web E2E / Mobile E2E / Hybrid E2E 一旦进入本轮正式验证范围，stdout-only、terminal-only 或 diagnostic-only 命令不能满足最终报告 gate：Playwright 的 `--reporter=list`、只向终端打印的 API 自定义脚本、以及未指定 `--format` / `--output` 或项目等价 reporter 的 Maestro run 都只能算诊断或定点重跑。收尾前必须再跑一次启用项目 reporter 的计划范围验证，或把 API stdout / stderr / exit code 捕获为正式 raw report 后提升，或在确实无法产出报告时将 `Final Test Report` / `Run Summary MD` 标记为 `blocked` 并说明原因。
- 测试报告必须区分 runner 管理的临时输出和需要保留的正式快照。凡是 runner 可能在下一次运行前清空、覆盖或重建的目录 / 文件，都不能作为正式报告保存位置；需要保留时，必须在下一次运行前复制 / 提升到带业务名、分支名和时间戳的正式快照路径。报告文件名中的分支使用 `branch_slug`：优先取当前 git branch 或 CI branch ref；detached HEAD 使用 `detached-{short_sha}`；非 git 环境使用 `unknown-branch`；只保留字母、数字、`.`、`_`、`-`，将 `/`、空格和其他特殊字符替换为 `_`。API / integration 默认正式快照目录为 `tests/api/reports/`，如 runner 需要临时目录则使用 `tests/api/reports/.api-current/`；没有原生 reporter 的 API / integration 命令若属于本轮正式验证，必须至少捕获 stdout、stderr 和 exit code 为 `api-report-{suite_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.txt` / `.json` 等 raw report，并生成同 stem 中文 Markdown 汇总；unit test 默认继承项目配置，但若本轮生成的 JUnit、coverage、HTML 或 JSON 报告需要作为本地证据保留，则使用项目既有归档目录或 `tests/unit/reports/`，不要把 `coverage/`、`test-results/`、固定 `junit.xml` 或 runner `current` 目录当作长期报告。
- 正式报告要作为 PR 证据或被知识库读取时，必须按 `project-validation` 的验证证据契约记录 repository key、原始 source ref、完整 commit SHA、worktree state、evidence source、trigger、source revision、environment alignment 和 publication status；`branch_slug` 只用于文件名，不是版本身份。dirty 的开发者本地运行只能是 `local-only`，不能证明 PR head；CI evidence 必须来自 clean checkout、绑定最终 PR head SHA，且只有目标系统接收后才是 `published`；知识库服务器运行必须固定并记录完整 revision set，且不得把 `smoke-only`、contract 或 mock 结果提升为 full-stack。
- API / integration 的中文 Markdown 汇总必须包含 API URI 覆盖矩阵。每条覆盖范围描述必须映射到具体 `method + URI path`，并记录对应测试脚本 / case、期望状态码或副作用、关联 `.feature` / contract / schema 依据；同一覆盖描述涉及多个 endpoint 时逐行列出。Base URL、环境名或服务名可单独记录，但 URI path 不得只写成业务概括；不得写入真实账号、token、敏感 query/body 或生产数据。
- Playwright HTML reporter 的 `outputFolder` 是 runner 管理的临时目录，默认使用 `tests/e2e/reports/.playwright-html-current/`；Playwright 每次运行可能清空该目录，不得把需要保留的正式命名报告放在这里。Playwright HTML 正式报告快照默认位于 `tests/e2e/reports/html/`，命名为 `playwright-report-{feature_file_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.html`，并生成同 stem 的 `.md` 汇总；命名后的 HTML 是正式报告，默认 `index.html` 只作为临时复制源或工具兼容产物。
- 对 Playwright，Markdown 汇总的 stem 必须与命名后的 HTML 报告完全一致；`results.json`、`junit.xml`、`test-results/` 和 Playwright 默认 `index.html` 都只是 runner / 兼容产物，不能作为正式 Markdown stem。不得用 `results.md`、`result.md`、`junit.md` 或 `index.md` 满足 `Run Summary MD: generated`；这些文件即使存在也只能作为辅助材料，最终报告 gate 必须检查 `playwright-report-*.html` 与同名 `playwright-report-*.md` 成对存在。
- 如果 Playwright 已产生 `index.html`、`results.json`、`junit.xml` 或等价 runner 产物，最终输出前必须确认命名后的 HTML 和同 stem `.md` 实际存在；缺失时先补生成，不能把 `Run Summary MD` 标记为 `not-needed`。
- `feature_file_name` 默认取关联 BDD `.feature` 文件名去掉扩展名；smoke test 固定使用 `smoke`；一次运行覆盖多个 `.feature` 时优先使用明确 suite 名，否则使用 `multi-feature`。
- 失败修复后先重跑失败 case / spec / flow，再跑受影响子集，最后跑计划范围内全量验证；fail-fast 停在首个失败时，修复后必须继续跑未覆盖测试或重跑全量验证。
- Markdown 汇总必须使用中文撰写，只有状态枚举值、命令、文件路径、case / spec / flow 名称、错误原文和技术标识符可以保留英文。汇总记录运行 case 列表、关联 BDD `.feature` 路径和场景名、总轮次、每轮失败 case、失败原因、修复动作、定点重跑、影响范围重跑、最终全量重跑、跳过项和剩余风险；API / integration 汇总还必须记录 URI 覆盖矩阵，保证覆盖范围描述和 `method + URI path` 一一映射；不得写入真实账号、密钥、PII、生产数据、完整 token 或敏感请求头。

Playwright CLI 检测规则：

- 先静态检查 `package.json`、`playwright.config.*`、package scripts、`tests/e2e` / `e2e` 等既有约定。
- 如果 Web 回归或 `web-ui-autotest-generator` 需要 Playwright，但项目内未安装 Playwright CLI，必须询问用户是否安装到项目 devDependency；用户确认后按项目包管理器安装并继续流程。
- 用户拒绝安装或安装失败时，不声称 Playwright 测试已运行；可用 Chrome DevTools MCP / Playwright MCP 做诊断，但 `Playwright Web Tests` 必须标记 `blocked` 或 `skipped` 并说明原因。

Web UI 测试资产路径规则：

- 当 `web-ui-autotest-generator` 生成或维护可入库机器可读 JSON 资产时，默认必须写入 `tests/e2e/manifest/`：`ui-test-manifest.json`、`ui-selector-audit.json`、`ui-test-coverage.json`。
- 调用该 Skill 的脚本前，必须加载 `project-validation` Skill 并遵循其中的 Web UI 测试资产路径契约；不要依赖 external Skill 示例或脚本默认输出路径。
- `ui-test-repair-plan.json` 是失败分析运行产物；默认路径和忽略策略遵循 `project-validation` Skill 与项目 `.gitignore`。
- 将 `Web UI 测试资产` 报告为 `generated` 或 `coverage-only` 前，必须检查目标 JSON 实际存在于 `tests/e2e/manifest/`，并确认项目根目录没有残留 `ui-test-manifest.json`、`ui-selector-audit.json`、`ui-test-coverage.json`；无法确认时标记 `blocked` 或说明跳过原因。

Maestro 检测规则：

- 需要 Maestro 前先检查 Java 17+，优先 `java --version`，失败时回退 `java -version`。
- Java 缺失或版本低于 17 时，说明 Maestro 需要 Java 17+；默认建议安装 OpenJDK Temurin 21 最新 JDK。用户指定其他版本时，只允许安装 Java 17+，拒绝任何低于 17 的版本。
- Java 通过后再检查 Maestro CLI；CLI 缺失时询问用户是否安装到开发环境或 CI runner。Maestro CLI 可用后再检查 Maestro MCP。
- Maestro MCP 缺失但 CLI 可用时，继续用 `maestro test` 跑已有 flow；CLI 缺失时 MCP 也视为不可用。
- Mobile / Hybrid E2E 需要从 BDD 场景生成或维护 Maestro flow 时，调用 `maestro-mobile-e2e` Skill；没有 BDD 场景时先回到 `gherkin-bdd`。
- Maestro flow 作为仓库内测试资产默认写入 `maestro/flow/`，文件名和 YAML `name` 使用英文业务场景名；平台差异明显时可使用 `maestro/flow/ios/*.yml` 和 `maestro/flow/android/*.yml`；全量回归 / smoke flow 固定为 `maestro/flow/smoke.yml` 或平台 smoke flow。
- Maestro 正式报告默认写入项目根目录 `.maestro/reports/`；报告命名为 `maestro-report-{flow_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.xml` 或 `.html`，并生成同 stem 的中文 `.md` 运行汇总；`flow_name` 取 Maestro flow 文件名 stem，smoke flow 使用 `smoke`，是否生成 HTML 遵循项目或用户对人类可读报告的需要。优先让 Maestro 直接输出到包含分支名和时间戳的报告；如项目 wrapper 只能输出到固定路径或 runner-managed 目录，使用 `.maestro/reports/.maestro-current/` 作为临时输出并在下一次运行前复制 / 提升。只要 Maestro 运行产生原生报告，失败运行也必须保留命名报告和同 stem `.md`；stdout-only Maestro run 只算诊断，不能满足正式 Mobile / Hybrid E2E 报告 gate。
- iOS 真机 Maestro 运行遇到 driver、transport、view hierarchy、tap crash 或版本已知问题时，先由 `maestro-mobile-e2e` 按标签 / 关键字懒加载对应 lesson；未命中时不要预先套用临时补丁。

MCP 边界：

- MCP items 是 check-and-guide，不复制 MCP 配置，不声称自动完成安装。
- 只有用户完成配置并在后续检查中确认工具可见，才把 MCP 视为可用。
- 同一浏览器上下文同一时间只允许一个 controller，避免 Chrome DevTools MCP、Playwright MCP 和 Playwright CLI 互相污染状态。

真实账号、密钥、PII、生产数据不得写入仓库、PRD、测试代码、日志、截图、trace、video 或报告。

## Skills 调用规则

**规则**：相关 Skill 可用且任务场景明确匹配时，优先调用对应 Skill；不可用时直接跳过，不阻塞任务。

不要因为任务简单就跳过已明确匹配的 Skill。
如果任务场景与 Skill 的使用场景不匹配，或仅存在弱关联，则不要强行调用 Skill。

Skill 不替代项目规范、任务产物、测试和人工判断。
如果 Skill 与项目 `AGENTS.md`、`.trellis/workflow.md` 或 `.trellis/spec` 冲突，以项目规则为准。

职责划分：`AGENTS.md` 优先保存常驻上下文必须知道的路由、触发条件、硬性安全边界和最终报告要求；可延迟加载的详细流程、命令参数、检查清单和专项判断，应优先放入对应 Skill，并由 `AGENTS.md` 指向何时调用。

### grill-with-docs 使用状态透明度

在准备开始开发需求、进入 PRD / Trellis task、需求最终确认、PRD / design / implement review gate、或询问是否开始实现前，必须对 `grill-with-docs` 的使用状态做用户可见说明：

- 如果已完整执行 `grill-with-docs` 的按 design tree frontier 分轮澄清流程，明确说明“已调用 `grill-with-docs`”，并简述已解决的关键产品 / 领域边界。
- 如果只读取了 `grill-with-docs` Skill 文件、只借用了其中 evidence-first 原则，或仅通过代码 / 文档自行判断，不得声称已调用；必须明确说明“未完整调用 `grill-with-docs`”。
- 未完整调用时，必须给出具体原因，例如：需求不涉及项目领域模型或长期术语；问题可完全由现有文档 / 代码回答；只是 Trellis 启动实现的 review gate；Skill 不可用 / 不可读取；用户明确要求跳过。
- 只有调用与跳过之间存在会实质改变需求、领域边界或实现决策的权衡时，才询问用户是否先完整调用；如果现有项目事实已消除歧义，说明未调用原因后直接推进，不得仅为状态透明度制造确认门。

### grill-with-docs 后置 DDD 边界审核

- 无论是 Agent 自发调用还是用户主动调用，每次完整执行 `grill-with-docs` 结束后，必须立即调用 `book-ddd-distilled-modeling` 做独立的二次边界审核；调用来源和 Agent 是否认为需求已足够清晰都不构成跳过理由。
- `grill-with-docs` 内嵌的 external `domain-modeling` dependency 已运行也不得替代这次后置审核。前者负责访谈中的主动建模和长期术语沉淀，后者必须重新读取本次澄清结果与项目事实，检查统一语言、bounded context、业务不变量、子域归属、术语混用和未决冲突。
- 二次审核必须向用户输出独立的 `DDD Boundary Review`，并覆盖对本次 `grill-with-docs` 结果的修正；不得只说“已审核”或把结果隐含在需求摘要中。审核状态枚举、输出字段、重跑回路和 stop condition 以 `book-ddd-distilled-modeling/SKILL.md` 为唯一事实源，本文件不复制。
- 本门禁只固定时序：审核未达到该 Skill 定义的通过状态前，不得进入需求确认、PRD、design、Trellis task 或实现；Skill 不可用、不可读取或证据不足时按该 Skill 的阻断状态处理，不得跳过。
- 如果没有调用 `grill-with-docs`，仍按任务自身的业务术语、领域规则和模型歧义判断是否独立调用 `book-ddd-distilled-modeling`；本后置门禁不把所有普通任务强制改为 DDD 流程。

### book-derived 开发阶段强制门禁

- 进入开发任务时先输出任务级 `Book Gate Plan`：逐项记录 5 个 bundled book-derived Skill 的 `required` / `on-demand`、客观触发事实、执行阶段和 Gate state。Gate state 仅为 `planned` / `running` / `passed` / `blocked` / `not-required`，正常转换是 `planned` → `running` → `passed` / `blocked`；未选中的 on-demand 项为 `not-required`，不得预填 reviewer 终态。
- 下方 Skill 路由表是客观触发条件的唯一常驻事实源；各 `book-*/SKILL.md` 独占 reviewer 状态、输出 schema、修正回路和 stop condition。本文件只额外固定跨 Skill 的时序，例如上一节“grill-with-docs 后置 DDD 边界审核”规定该审核何时必须运行、必须先通过才能进入哪些阶段，reviewer 契约本身仍属对应 Skill。命中触发条件后不得主观降级；未命中时保持 on-demand。
- 同时命中 legacy / refactoring 时，顺序和 `seam-required` 的受控例外以两份 reviewer Skill 为准；未通过 reviewer 不得进入行为修改。Release readiness 仍在适用 testing-tool gate 与 `project-validation` 后运行。
- 强制门禁命中但 Skill 缺失、不可读取或证据不足时，Gate state 为 `blocked`；普通 on-demand Skill 缺失才允许按“Skill 不可用时”降级。



| Skill | 使用场景 | 调用时机 |
|---|---|---|
| `trellis-workflow` | Trellis 生命周期、任务产物、阶段检查 | 发现项目使用 Trellis 后 |
| `trellis-channel` | Trellis Channel / 多 Agent / 多模型协作、代码 review / 验证 preflight | 用户明确要求 Channel、worker、forum、thread、并行评审，或项目级高风险 review / validation gate 需要 Channel preflight 时 |
| `project-validation` | 判断代码修改后的验证策略 | 修改代码后、执行验证前 |
| `gherkin-bdd` | 用户可见行为的 BDD / Gherkin 场景、`.feature`、Given/When/Then 验收规格 | 新增 / 修改 UI、API、CLI、导出文件、通知、权限、错误、状态变化或外部集成可观察行为前 |
| `knowledge-base-integration` | 产品级 Knowledge Ingest、目标 ref 行为目录、Evidence Policy、Revision Set 和服务器 Smoke | BDD / 知识库语境的 `read` / `读取`、多仓知识摄取或 knowledge-server smoke 时 |
| `maestro-mobile-e2e` | BDD 场景到 Maestro Mobile / Hybrid flow 资产、报告路径和真机排障 lesson | 需要生成 / 维护 / 执行 Maestro flow，或 iOS 真机 Maestro E2E 排障时 |
| `lessons-record` | 记录长期经验教训 | bug 修复、回滚、工具误判、验证失败、上下文丢失后 |
| `book-refactoring-pass` | 行为保持型重构检查 | 修改既有生产代码时在首次实现编辑前强制调用；legacy 为 `seam-required` 时可先以 `safety-seam-only` 模式建立安全网所需 seam；其他结构摩擦或 review 场景按需调用 |
| `book-legacy-change-safety` | 遗留 / 弱测试代码安全修改 | 修复既有行为 bug，或弱测试、行为不清、隐藏依赖、高回归风险任一命中时，在首次行为修改前强制调用；其他场景按需调用 |
| `book-ddd-distilled-modeling` | 轻量领域建模、统一语言和 bounded context 二次审核 | 每次完整执行 `grill-with-docs` 后强制调用；未调用 `grill-with-docs` 时，需求涉及业务术语、领域规则、上下文边界或模型歧义则在 PRD / design 前调用 |
| `book-ddia-data-design` | 数据密集型设计风险检查 | 持久化 / 共享数据、schema / migration、shared / persistent / cross-request / cross-process cache、queue / event / stream / job、ETL / analytics、跨服务数据流、API 所有权、数据所有权、source of truth、事务边界、读写路径、backfill / replay / rollback / recovery 任一命中时，在设计稳定前强制调用；其他场景按需调用 |
| `book-release-readiness` | 生产就绪与发布风险检查 | service / API / auth / billing / notification / background job / queue / scheduler / 外部集成 / data pipeline / deployment / rollout / migration / runtime 运维行为变更任一命中时，在所有适用 testing-tool gate 和 project validation 后、完成或发布前强制调用；其他场景按需调用 |
| `diagnosing-bugs` | 诊断 bug、测试失败、运行时错误、性能回归、日志异常、线上问题或数据不一致 | 问题根因不清或需要系统化排障时 |
| `tdd` | 测试先行、回归测试、复杂逻辑验证、高风险修改 | 需要用测试固化行为再实现时；依赖 `codebase-design` |
| `grill-me` | 通用需求澄清、方案质询、计划压力测试 | 用户希望先打磨计划、决策或设计时；依赖 `grilling` |
| `grill-with-docs` | 结合项目文档澄清需求、术语、领域模型和 ADR / CONTEXT 沉淀 | 项目内需求或方案进入 PRD / Trellis 前；依赖 `grilling` 和 `domain-modeling` |
| `grilling` | 可复用的 design tree / frontier 分轮访谈 | 作为 `grill-me` / `grill-with-docs` 的底层依赖；每轮只问前置条件已满足的问题 |
| `domain-modeling` | 项目语言、glossary、CONTEXT.md / ADR 建模辅助 | `grill-with-docs` 需要维护项目语言或长期上下文时 |
| `codebase-design` | 模块、接口、seam、adapter 和测试面设计 | `tdd`、陌生模块理解或结构性修改前 |
| `handoff` | 长会话交接、上下文压缩、跨会话继续任务 | `/clear`、新会话、Trellis 暂停或多会话交接前 |
| `writing-for-agents` | 创建或维护 Agent 消费的 Skill、AGENTS、CLAUDE 或指针文档 | 用户要求新增、改造或沉淀这些文档时 |
| `to-spec` | 将当前对话和代码库理解整理为 Markdown spec / PRD | 需求需要沉淀为 spec 或 PRD 时 |
| `to-tickets` | 将 spec、PRD、plan 拆成实现任务 | 需要 Trellis-ready Markdown task、tickets 或 vertical slices 时 |
| `ui-ux-pro-max` | UI/UX 初稿计划、修改前设计判断和体验质量检查 | 涉及 UI/UX 的需求进入实现或 Trellis 任务设计前 |
| `impeccable` | 前端 UI/UX 塑形、审计、打磨、反模板化和视觉质量收尾 | `ui-ux-pro-max` 明确初稿方向后按条件前置 `shape` / `craft`，或实现后的 `audit` / `critique` / `polish` 阶段；仅在 Skill 可用且上下文可用时 |
| `shadcn` | shadcn/ui 项目组件、registry、preset、CLI 和组件组合规则 | 项目存在 `components.json`、使用 / 初始化 shadcn/ui，或需要 `shadcn init/add/search/view/docs/diff/info/migrate/preset`、registry 组件、preset、Base / Radix 差异、表单 / 图标 / chat primitives 等 shadcn 规则时 |
| `web-ui-autotest-generator` | Web UI Playwright 测试资产生成、选择器审计和覆盖率报告 | 用户明确要求生成 Web UI 自动化测试，或测试阶段发现关键 Web UI 回归路径需要固化为仓库内可维护测试资产时 |
| `seo-geo` | 公开网站 / 落地页 / 文档站 SEO 与 GEO 可见性专项检查 | 用户明确要求 SEO、GEO、AI search visibility、schema、meta tags、robots / sitemap 或公开 Web 发布前搜索可见性检查时；仅在 Skill 可用时 |
| `ponytail` | 编码任务的最小正确实现选择（YAGNI、复用优先、stdlib 优先） | 所有编码任务在需求、设计和适用开发门禁确定后、首次实现编辑前主动调用 |
| `ponytail-review` | 非平凡生产代码 diff 的过度设计 / 赘余审查 | 完整 diff 形成且定点 smoke 通过后、最终 `project-validation` 前主动调用；findings 必须经 Code Readability 裁决 |
| `ponytail-audit` | 全仓只读 over-engineering / bloat 候选清单 | 用户明确要求全仓审计、验收明确包含全仓整改或跨模块架构整改需要只读候选清单时 |
| `ponytail-debt` | `ponytail:` marker 台账收集 | 新增 / 修改或触及 `ponytail:` marker，或用户明确要求列出 shortcuts 台账时；默认不落盘 |
| `React Bits tier / Pro Skill` | React / shadcn UI 项目中选择 React Bits Free 或付费 components、blocks、landing page sections | 目标项目已确认 React + shadcn/ui 后，用户明确需要 React Bits；Free 和付费 Starter / Pro / Ultimate 都需确认，付费还需 registry、项目内 Skill 和可读取 license key |

### 自定义 Skills 使用边界

- `ui-ux-pro-max`：仅在涉及 UI、交互、布局、视觉、组件体验、前端可用性时调用。作为 UI/UX 任务的默认初稿计划入口，用于产品类型、目标用户、信息架构、交互模型、风格、配色、字体、可访问性、栈约束和设计系统方向判断；不替代项目已有 design system、tokens、组件库和品牌规范。
- `impeccable`：仅在前端 UI/UX 任务需要塑形、审计、批判、打磨、反模板化、视觉层级、排版、配色、动效、响应式、可访问性或最终 polish 时调用。默认作为 `ui-ux-pro-max` 的下游执行与质检 Skill：`ui-ux-pro-max` 先形成初稿计划和设计系统方向，`impeccable` 再按条件形成高保真 brief、实现检查项或 polish backlog。
- `impeccable` 为可选 Skill；如果未出现在可用 Skill 列表、Skill 文件不可读取、引用脚本不可执行，或其 setup 需要初始化项目上下文但用户未明确要求初始化，则跳过 `impeccable`，继续使用 `ui-ux-pro-max`、项目设计规范和浏览器验证，不阻塞任务。
- `shadcn`：仅在 shadcn/ui 相关任务中调用，包括项目存在 `components.json`、使用或初始化 shadcn/ui、执行 shadcn CLI、配置或使用 registry / preset、安装 / 更新 / diff 组件、修复 shadcn 组件组合、表单、图标、Tailwind token、Base UI vs Radix API、chat primitives 或 registry import path 问题。UI/UX 任务中默认先由 `ui-ux-pro-max` 明确产品方向和设计约束，再用 `shadcn` 处理组件来源、CLI、registry 和实现规则；`shadcn` 不替代通用 UI 设计判断、`impeccable` 视觉打磨、项目设计系统，也不替代 React Bits Free / 付费 tier 判定。
- `web-ui-autotest-generator`：仅在 Web UI / E2E 测试需要生成、审计或评估可入库测试资产时调用。测试阶段如果改动关键 Web UI 业务流、修复用户可见 UI 回归、项目已有 Playwright / Cypress 需扩展覆盖、或 Trellis 验收要求可重复 UI 回归，必须主动判定是否调用；不需要长期测试资产时可跳过但要说明。机器可读 JSON 资产默认沉淀到 `tests/e2e/manifest/`，正式 Playwright HTML 报告和 Markdown 汇总默认进入 `tests/e2e/reports/html/`，具体执行、参数路径和验证策略遵循项目级 `AGENTS.md` 和 `project-validation` Skill。
- `seo-geo`：仅在公开 Web 资产需要搜索可见性检查时调用，包括网站、落地页、文档站、产品页、营销页、公开博客或公开 README 页面。普通内部 UI、API、CLI、移动 App、后台管理页、一次性浏览器诊断或纯 Web 回归不要触发 `seo-geo`。基础页面 audit、meta / schema / robots / sitemap 检查不要求 DataForSEO；DataForSEO 账号只作为关键词、SERP、backlink、domain overview 等增强分析的可选凭据。没有公网 URL 或 preview URL 时，只能做源码 / HTML 静态检查并将 `SEO/GEO` 标记为 `static-only` 或 `blocked`，不能声称线上 SEO/GEO 已验证。关键词、SERP、AI 搜索可见性和平台抓取规则具有时效性，必须通过当前可用来源核对；不要把外部账号、API login / password、真实搜索控制台数据或付费报告写入仓库、测试、日志、截图或报告。
- `maestro-mobile-e2e`：仅在 Mobile / Hybrid E2E 需要生成、维护或执行 Maestro flow，或 Maestro iOS 真机运行出现 driver / transport / view hierarchy / tap crash 等排障信号时调用。BDD `.feature` 仍是行为 source of truth；Maestro flow 默认沉淀到 `maestro/flow/`，平台差异明显时可拆到 `maestro/flow/ios/` 和 `maestro/flow/android/`；最终正式 report 和 Markdown 汇总默认进入 `.maestro/reports/`；已知问题 lesson 必须按标签 / 关键字懒加载，不预先套用临时补丁。
- `gherkin-bdd`：所有用户可见行为默认需要持久 BDD 场景。覆盖 UI、API、CLI、导出文件、通知、权限结果、错误响应、状态变化和外部集成可观察行为。新项目或无既有约定时默认使用 `.feature` 文件；已有 `.feature`、BDD runner 或项目级规则时沿用项目路径。前后端分仓、跨服务、Mobile + API 或 Hybrid 链路必须先确认 contract、环境、账号、数据、设备和选择器事实；缺关键事实时标记 blocked 或 `@todo`，不要把猜测写成 source of truth。既有项目采用 `no new uncovered behavior`：新增行为先写场景，修改既有行为时补齐 / 更新相关场景，用户可见 bug 修复先写正确行为场景再写失败回归测试。当主动使用 `gherkin-bdd` 且用户请求包含 `sync` 或 `同步` 时，进入 BDD Sync Mode：全量扫描当前工作树（含未提交内容）和项目 `features/`，判断 `.feature` 是否与最新代码行为一致；多仓 / 前后端分离时先确认其他仓库是否有更新，有更新则必须收集路径并一起扫描，无更新则记录确认后只按当前仓库同步；报告更新、新建、删除、未变和候选删除的 feature 文件。该同步功能保持可写行为审计语义不变。仅包含 BDD / 知识读取语境的 `read` 或 `读取`、且不包含 `sync` / `同步` 时，进入只读 Knowledge Ingest：按配置目标 ref 解析精确 commit SHA，读取仓库自有 `.feature` 并生成可重建聚合视图；不得切换活动工作树、修改源仓、要求或补写 Feature / Scenario ID、自动合并跨仓行为，最终报告 `Knowledge Ingest` 和 `Mutation: none`。纯内部重构、依赖 / 工具配置、机械格式化、无语义 UI polish 或 typo 可跳过，但最终输出要说明原因。BDD 不替代 PRD、DDD、TDD、项目验证、Playwright、Maestro 或人工评审；PRD 说明意图，DDD 稳定语言，BDD 固化可观察行为，TDD 将场景转为红测和绿码。
- `knowledge-base-integration`：执行 P1.1 只读摄取和服务器 Smoke。读取产品注册表与服务器 Workspace Mapping，固定每仓库目标 ref 的完整 SHA，生成 Revision Set、完整无 ID Gherkin 目录、静态 / manifest 绑定和冲突候选；正式运行先生成不可变 Evidence Decision。Smoke 使用 `preflight / prepare / test / cleanup` 阶段，通过本地或命令式 Runner Adapter 执行仓库原生命令，并校验本轮报告、同 stem 中文汇总、artifact manifest、checksums、runner attestation 和环境对齐。重复逻辑运行按幂等键复用，显式重跑增加 attempt；P1 Evidence Publication 固定为 `not-configured`，远端发布和 PR Gate 留给 P2。
- `agent-rules-books` 派生 Skill 通常作为按需专项审查视角，不替代项目规范、Trellis task artifacts、`.trellis/spec`、GitNexus、`tdd`、项目测试、`project-validation`、Playwright、Maestro 或人工评审。上述 5 个客观开发门禁命中时转为强制调用；未命中时才按当前主风险选择最相关的 1-2 个，不要把 5 个当作所有任务的固定 checklist。默认只纳入 `book-refactoring-pass`、`book-legacy-change-safety`、`book-ddd-distilled-modeling`、`book-ddia-data-design`、`book-release-readiness`，不默认纳入 APoSD、Clean Architecture、PoEAA 等项目风格更强的扩展。
- `trellis-channel` 可以被项目级规则主动用于高风险代码 review / 验证覆盖 preflight，但 preflight 不等于启动 Channel runtime。除非用户已明确要求 Channel，或在 preflight 后明确确认，否则不得静默 spawn worker。
- `React Bits tier / Pro Skill`：普通安装和 reset 默认保持 shadcn/ui only，不询问也不安装 React Bits。只有在目标项目已确认是 React + shadcn/ui、项目根目录存在 `components.json`，且前端 UI 任务明确需要 React Bits 风格组件、blocks 或 landing page sections 时，才询问用户选择 shadcn/ui only、React Bits Free 或付费 Starter / Pro / Ultimate。React Bits Free 只有在免费 source / registry 已明确配置且用户确认后才安装；付费 tier 必须确认 registry / `REACTBITS_LICENSE_KEY` / 项目内 React Bits Pro Skill 均可用，且不得读取、输出、提交 license key。reset 时保留检测到的既有 tier 和 registry，未经确认不使用默认免费版覆盖。
- 如果使用 `impeccable` 生成或维护项目上下文，默认将 `PRODUCT.md` 和 `DESIGN.md` 放在项目根目录的 `docs/` 下，即 `docs/PRODUCT.md` 和 `docs/DESIGN.md`；不要在项目根目录创建重复副本。`.impeccable/design.json` sidecar 仍按 `impeccable` 默认保留在项目根目录 `.impeccable/` 下。
- `impeccable` 上下文文件必须避免多源冲突：如果项目根目录、`.agents/context/`、`docs/` 中同时存在 `PRODUCT.md` 或 `DESIGN.md`，以项目 `AGENTS.md` 指定路径为准；在读取和写入前先确认实际采用的上下文目录，避免同名文件分散在多个位置。
- UI/UX Skill 编排：
    - 初始需求 / 初稿计划：先用 `ui-ux-pro-max` 判断产品类型、目标用户、信息架构、交互模型、风格、配色、字体、布局、响应式策略和可访问性基线；如果任务进入 Trellis，将结论写入任务级 `prd.md`、`design.md` 或 `implement.md`。
    - 前置设计升级：只有在新视觉方向、高保真页面、大幅改版、品牌 / 营销强视觉页面、方向不清或用户明确要求时，才在实现前使用 `impeccable shape`；`impeccable craft` 只在 brief 已确认且需要完整设计执行时使用，并遵守其中的用户确认 gate。
    - shadcn/ui 实现：目标项目存在 `components.json`、已使用或准备初始化 shadcn/ui，或任务涉及 shadcn registry / preset / CLI / 组件组合时，在 `ui-ux-pro-max` 明确方向后调用 `shadcn`；先确认项目 package runner、`npx shadcn@latest info` / `docs` / `search` / `view` 结果和已安装组件，再执行 add / diff / preset / registry 操作。registry 未明确时先询问，不默认替用户选择第三方 registry。
    - 既有 UI 审查：先用 `ui-ux-pro-max` 的优先级清单覆盖可访问性、交互、性能、响应式、排版和颜色；再在 `impeccable` 可用时用 `audit` / `critique` 生成问题 backlog。
    - 实现后收尾：功能完成后，先运行项目验证和浏览器 / 截图检查；如 `impeccable` 可用，用 `polish` 或 `layout`、`typeset`、`colorize`、`adapt`、`clarify`、`animate`、`harden`、`optimize` 等针对性命令做最终质量 pass。
    - 冲突处理：项目 `AGENTS.md`、设计系统、tokens、组件库和已确认品牌规范优先；可访问性、响应式和项目验证不可降级。`impeccable` 的硬性反模板化规则可否决 `ui-ux-pro-max` 的泛化风格建议，除非项目既有品牌规范明确要求该设计语言。
- **mattpocock/skills** 仅纳入 `diagnosing-bugs`、`tdd`、`grill-me`、`grill-with-docs`、`grilling`、`domain-modeling`、`codebase-design`、`handoff`、`writing-for-agents`、`to-spec`、`to-tickets`。
- **mattpocock/skills** 默认从 Onboard 中经过 checksum 和来源校验的 stable 镜像安装，并保持上游内容不变；只有用户明确选择 upstream source 做评估或升级验证时才直接获取上游。除非用户明确要求，不 fork、不改写官方 Skill 文件。
- **mattpocock/skills** 相关 skill 使用边界说明：
    - `diagnosing-bugs` 用于系统化排障；代码级问题根因不清时结合 GitNexus debugging，修复前有风险时结合 GitNexus impact-analysis，并补充或更新回归测试。
    - `tdd` 适用于 bug 修复、核心业务逻辑、算法行为、数据转换、导入 / 导出 / 同步逻辑和高风险修改；这些场景必须主动判定是否使用 `tdd`，跳过时说明原因。不要强制用于简单文案、样式、配置说明或一次性脚本。`tdd` 依赖 `codebase-design`。
    - `grill-me` 用于通用计划、设计和决策的质询；如果问题可通过读取当前项目文件回答，先探索项目文件。`grill-me` 依赖 `grilling`。
    - `grill-with-docs`：
        - 用于项目内需求澄清、领域术语对齐、CONTEXT.md 或 ADR 沉淀；需求进入 PRD / Trellis 前优先使用；先读项目文档和代码，能从项目事实回答的问题不要反问用户；长期领域上下文默认写入 `docs/CONTEXT.md`，ADR 默认写入 `docs/adr/*.md`，多上下文项目使用 `docs/contexts/<context>/CONTEXT.md` 和 `docs/contexts/<context>/adr/*.md`；不要新建根目录 `CONTEXT.md`，除非项目已采用该路径或项目级规则明确指定；不要把 CONTEXT.md 写成临时规格书。`grill-with-docs` 依赖 `grilling` 和 `domain-modeling`。
        - 使用状态必须遵守上文“grill-with-docs 使用状态透明度”；读取 Skill 文件或只按 evidence-first 原则自行判断，不等于完整调用。
        - 每次完整执行结束后都必须遵守“grill-with-docs 后置 DDD 边界审核”，立即调用 bundled `book-ddd-distilled-modeling` 并向用户输出独立审核结果；`grill-with-docs` 内嵌的 external `domain-modeling` dependency 不构成替代。
    - `handoff` 交接内容应包含当前目标、已完成工作、关键决策、文件 / 产物、已尝试命令、开放问题、建议下一步 Skill、不要重复事项和敏感信息脱敏说明。
    - `writing-for-agents` 用于创建或维护 Agent 消费的文档；Skill 使用 `SKILL.md` 作为入口，按需把 Skill 机制拆到 reference，确定性操作优先脚本化，description 和文档指针必须写清触发分支。环境中的配置、命令和目录是事实源，文档只缓存无法直接查到的约定、理由或陷阱。
    - `zoom-out` 已从 mattpocock/skills 上游移除；陌生模块理解默认通过代码阅读、`codebase-design`、GitNexus exploring / impact-analysis 和按需 `book-refactoring-pass` 完成。
    - `to-spec` 默认输出 Markdown spec / PRD；在 Trellis 项目中，最终 spec / PRD 应写入或更新 `.trellis/tasks/<task>/prd.md`，未确定 task 路径前只保留为对话草稿或用户明确指定的临时文件；不要发布到 GitHub、Linear 或任何 issue tracker，除非用户明确要求。
    - `to-tickets` 中的 ticket 视为通用实现任务；在 Trellis 项目中，vertical slices 应落为 `.trellis/tasks/<task>/...` 下的 parent / child task artifacts，标注 AFK / HITL、依赖顺序、验收标准和测试策略；不要默认在 `docs/` 下维护最终 ticket / task Markdown，也不要自动发布到 issue tracker。

### Skill 不可用时

如果相关 Skill 不存在、不可读取或不可执行，先判断是否已命中“book-derived 开发阶段强制门禁”：

- 已命中强制门禁：不得直接跳过；按对应 reviewer contract 输出 `blocked`、缺失项和解除阻断条件，不得越过对应阶段。
- 未命中强制门禁的普通按需 Skill：可以跳过且不阻塞任务，按当前 `AGENTS.md`、项目文件、`.trellis/workflow.md`、`.trellis/spec` 和已有上下文继续执行。
- 仅在 Skill 对结果有明显影响时，在最终输出中说明普通按需跳过；强制门禁的 `blocked` 必须始终报告。
---

## 范围控制

- 不做与任务无关的重构。
- 不在生产代码中引入 mock。
- 除非任务需要，不修改 lock 文件。
- 除非任务与工具配置相关，不修改工具配置。
- 不绕过已有项目工作流文件。
- 不手动跳过 Trellis 阶段。
- 不创建不必要的 parent / child task。
- 不把一次性任务计划写入长期项目规范。
- 不让未受 `.trellis/workflow.md`、task artifacts 和生成 role guard 管理的 Codex sub-agent dispatcher 替代项目工作流；有效 Trellis 调度模式内的 role subagent 仍遵循该工作流。

---

## 代码可读性

正确性、安全、运行时特性、明确需求和项目约定优先。可读性与可维护性优先于减少源码行数、文件数或 diff 体积。

1. 每个函数或模块应有一个内聚职责。不要仅为了让函数更短而拆开内聚逻辑。

2. 当具名辅助函数（helper）能实质降低认知负担、捕获可复用概念、或建立已验证的接缝（seam）时，再抽取它。避免只是把代码挪到别处的浅层包装（shallow wrappers）。

3. 当守卫子句（guard clauses）和提前返回能让主路径更清晰时，优先使用。当结构化清理、对称性或错误聚合更易跟随理解时，不要强行使用它们。

4. 避免巧妙、过度紧凑或依赖运算符优先级的表达式。

5. 当具名中间变量能揭示复杂条件或转换的含义时，引入它们。不要仅为增加行数给平凡值命名。

6. 领域代码使用领域意图命名；基础设施代码使用具体角色命名。

7. 避免 `data`、`info`、`tmp`、`result`、`handle`、`process`、`doSomething` 这类含糊名称，除非在极窄范围内含义已经明确无歧义。

8. 当真实接缝（seam）能改善局部性、可测试性或变更隔离时，把领域决策与 I/O、数据库、HTTP、缓存和日志分开。不要为单一平凡路径引入假想的端口（ports）、适配器（adapters）或服务层（service layers）。

9. 注释应解释理由、不变量、约束、协议要求或非显而易见的权衡。不要复述代码。

10. 仅当抽象能实质改善可读性、集中不变量、消除有意义的重复、隔离易变依赖、或建立已验证的接缝（seam）时，才引入抽象。

11. 在套用通用建议之前，先遵循现有项目的命名、模块、错误处理和结构约定。

12. 最终验证前，专门从可读性角度复核所有已修改的手写代码和测试。不要修改第三方打包或生成代码（vendor / generated code）。

当存在多种正确实现时，选择新维护者能最快理解并安全修改的方案，且不得恶化运行时行为或违反项目约定。

### Ponytail 与代码可读性审查

- `ponytail` 的最小化偏好受本节约束：删繁不能以密集表达式、模糊命名、浅层包装（shallow wrappers）或移除真实接缝（seam）为代价。
- `ponytail-review` 的每个删除 / 内联 / 合并发现项必须按本节裁决；接受后重跑受影响验证。
- Code Readability Review 在最终验证前覆盖本轮修改的手写生产代码和测试，不修改第三方打包或生成代码（vendor / generated code）；需要大范围行为保持重构时回到 `book-refactoring-pass`，不在收尾阶段静默扩大任务。

```text
Code Readability Review
Scope: modified hand-written production code and tests
Findings: none | <concrete locations and issues>
Ponytail conflicts resolved: none | <accepted/rejected finding and reason>
Changes applied: none | <task-scoped readability edits>
Revalidation required: yes | no
```

---

## 验证最低要求

修改代码后必须进行验证。

验证优先级：

1. 项目级 `AGENTS.md` 中定义的命令。
2. 项目 README / package scripts / Makefile / CI 配置中的命令。
3. `project-validation` Skill 中的默认策略。
4. 根据修改范围选择的聚焦检查。

如果无法执行验证，必须说明：

- 尝试执行的命令
- 失败或跳过的原因
- 已执行的替代检查
- 剩余风险

---

## 上下文控制

仅在上下文污染或过大时使用 `/clear`。

执行 `/clear`、长任务暂停、新会话切换或交接前，如当前任务存在未完成上下文，优先使用 `handoff` Skill 生成交接摘要。

如果 `handoff` 不可用，按以下字段手工总结：

- 当前结论
- 关键决策
- 已完成工作
- 剩余工作
- 下一步
- 当前 Trellis 任务 / 阶段，如果存在

---

## 最终输出规则

实现类任务结束时，必须包含：

- 结论
- 修改的文件
- 验证命令和结果
- 跳过的检查及原因
- 风险或回滚说明

如果相关，再补充：

- Trellis 任务 / 阶段
- GitNexus 状态
- Channel 状态
- Lessons 记录位置

---

## Lessons 规则

出现以下情况时，调用 `lessons-record` Skill：

- bug 修复
- 回滚
- 工具判断错误
- 工作流阶段错误
- 验证失败
- GitNexus 影响分析不匹配
- Channel / worker 上下文丢失

Trellis 项目默认采用 `lessons-record` Skill 定义的分层结构：`.trellis/spec/lessons.md` 只作为短入口，完整内容进入 `.trellis/lessons/index.md`、`topics/` 或按需归档。只有确认项目没有使用 Trellis 时，才默认写入 `docs/lessons.md`。不要在普通任务中滥写 lesson。

---

## 最终目标

保持任务可验证、可维护、最小化、可回滚，并与项目规范一致。
