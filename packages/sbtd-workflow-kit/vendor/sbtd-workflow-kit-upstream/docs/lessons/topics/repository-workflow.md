# Repository Workflow Lessons

本 topic 保存当前配置摘录仓库定位、AGENTS / ENTRYPOINT / README、同步、版本检查和仓库级规则相关 lessons。

## LESSON-20260701-entrypoint-version-baseline: ENTRYPOINT Version Baseline

- 日期：历史记录迁移，原始日期未记录
- 标签：automation, entrypoint, update
- 适用场景：每日版本检查、`ENTRYPOINT.md` 写回、`UPDATE.md` 生成
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：每日版本检查不得推进 ENTRYPOINT 当前版本
- 问题：每日版本检查自动化在发现 Codex 新版本后，把 `ENTRYPOINT.md` 中的当前版本从 `v0.131.0` 自动更新到了 `v0.132.0`，且 `UPDATE.md` 使用了英文内容。
- 根因：automation prompt 没有明确区分“每日检查”和用户手动输入 `更新` / `update` 后的写回动作，也没有要求 `UPDATE.md` 必须使用中文。
- 修复：每日自动化只读取 `ENTRYPOINT.md` 当前版本作为固定比对起点，只用中文刷新 `UPDATE.md`，不得写回 `ENTRYPOINT.md`；只有用户手动输入 `更新` / `update` 时才允许更新版本号并归档。
- 预防：后续涉及自动化写入项目基线文件时，必须在 prompt 和 `AGENTS.md` 中同时明确“只读基线”和“手动确认写回”的边界。

## LESSON-20260701-config-excerpt-repo-boundary: Config Excerpt Repo Boundary

- 日期：历史记录迁移，原始日期未记录
- 标签：repository, templates, scope
- 适用场景：判断当前仓库角色、修改 AGENTS / Skill 模板、迁移配置摘录
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：配置摘录仓库不得按真实业务项目判断
- 问题：维护 Codex 配置摘录时，容易把仓库内的 `AGENTS.md`、`skills/`、`ENTRYPOINT.md` 当成真实业务项目结构来解释，从而引入“当前仓库直接生效”“当前仓库事实源”等误导措辞。
- 根因：配置摘录仓库同时保存全局规则、项目级规则模板和 Skill 镜像，外观类似项目根目录，但其目标是为后续同步和复用配置，不代表正在开发的业务仓库。
- 修复：将相关文档改为“配置文件与 Skill 的摘录/同步源”，避免把配置摘录仓库误写成真实工作项目的事实源。
- 预防：后续修改本仓库时，先区分“配置摘录源”和“真实工作项目”；不要因为缺少 `.trellis/`、`.gitnexus/` 等目录就改写模板规则的适用边界。

## LESSON-20260701-project-agents-template-boundary: Project Agents Template Boundary

- 日期：历史记录迁移，原始日期未记录
- 标签：agents, templates, scope
- 适用场景：修改 `AGENTS.project.md`、根 `AGENTS.md` 或全局 / 项目模板
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：项目级 AGENTS 模板不得镜像配置仓库根 AGENTS
- 问题：`agents/AGENTS.project.md` 被错误改成了与本配置仓库根 `AGENTS.md` 基本相同的内容，丢失了它作为真实项目仓库根目录 `AGENTS.md` 模板的角色。
- 根因：没有区分三类文件：`agents/AGENTS.global.md` 是 Codex 全局规则模板，`agents/AGENTS.project.md` 是真实项目级规则模板，本仓库根 `AGENTS.md` 只是配置摘录仓库自身规则。
- 修复：重新将 `agents/AGENTS.project.md` 调整为真实项目级模板，承接全局规则并补充项目事实源、Trellis、GitNexus、Channel、验证和 Lessons 的项目级约束。
- 预防：后续同步规则时，不能把本仓库根 `AGENTS.md` 复制到 `agents/AGENTS.project.md`；两者加载位置、适用对象和内容职责不同。

## LESSON-20260701-local-sync-explicit-trigger: Local Sync Explicit Trigger

- 日期：历史记录迁移，原始日期未记录
- 标签：sync, local-config, scope
- 适用场景：同步本仓库配置到本机实际生效路径
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：本地配置同步必须显式触发
- 问题：本地同步规则曾写成全局规则或全局 Skill 发生修改后“还应同步到本地 PC”，容易导致普通编辑任务立即覆盖实际生效的本地 Codex 配置。
- 根因：没有区分“维护仓库源文件”和“落地到本地实际路径”两个动作，触发语义不够明确。
- 修复：将同步逻辑改为只有用户主动输入 `同步` 或 `sync` 时才执行；普通修改任务只更新仓库源文件。
- 预防：后续新增同步目标或同步规则时，必须明确触发词、同步范围、校验方式，并保持项目级模板 `agents/AGENTS.project.md` 不自动同步。

## LESSON-20260701-automation-rules-template-boundary: Automation Rules Template Boundary

- 日期：历史记录迁移，原始日期未记录
- 标签：automation, templates, agents
- 适用场景：根据自动化或 release notes 修改长期规则
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：自动化规则不得写入可复用模板
- 问题：每日版本更新中，为了约束本仓库自动化如何把 release 结论沉淀为通用规则，曾把该要求误写入 `agents/AGENTS.global.md` 和 `agents/AGENTS.project.md`，污染了给其他项目直接复用的全局/项目级模板。
- 根因：没有先判断规则的适用主体，把“本配置摘录仓库的自动化运行逻辑”和“真实项目会继承的长期 agent 行为规范”混为一谈。
- 修复：撤回两份 agents 模板中的自动化专用规则，只在根 `AGENTS.md` 保留每日版本检查自动化约束；`skills/trellis-channel/SKILL.md` 仅保留与 Trellis Channel 实际使用边界相关的通用规则。
- 预防：后续根据 release notes 修改规则时，先分类目标文件角色：根 `AGENTS.md` 可写本仓库自动化流程，`agents/AGENTS.global.md` / `agents/AGENTS.project.md` 只写对真实项目普遍成立的行为规范，`skills/**/SKILL.md` 只写该 Skill 自身长期有效的使用规则。

## LESSON-20260701-entrypoint-table-semantic-writeback: ENTRYPOINT Table Semantic Writeback

- 日期：历史记录迁移，原始日期未记录
- 标签：entrypoint, update, markdown
- 适用场景：写回 `ENTRYPOINT.md` 版本字段
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：ENTRYPOINT 版本写回必须限定表格语义
- 问题：手动 `update` 写回 `ENTRYPOINT.md` 时，脚本用“第一列等于工具名”的宽泛表格正则替换版本，误改了“工具定位”表里的“是否进入主流程”列，并把“当前版本汇总”表压成一行。
- 根因：没有按 Markdown 章节和表头定位，只用工具名匹配任意表格行，导致同名工具在非版本表格中也被当成版本记录。
- 修复：立即用精确补丁恢复非版本表格，只保留版本监控表、工具当前关注版本和当前版本汇总中的版本更新。
- 预防：后续写回 `ENTRYPOINT.md` 时必须先按章节标题和表头定位目标表，再按列名更新“当前使用版本”或“当前版本记录”；不要对全文表格做工具名全局替换。

## LESSON-20260701-display-task-config-boundary: Display Task Config Boundary

- 日期：历史记录迁移，原始日期未记录
- 标签：docs, config, scope
- 适用场景：展示型 / 文档型任务中出现 `.gitignore`、`.gitattributes` 等配置片段
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：展示型任务中的参考配置不得直接写入当前仓库
- 问题：在规划模板/Skill 展示 HTML 时，用户提供 `.gitignore` 和 `.gitattributes` 参考规则，本应作为 HTML 中给其他代码仓库使用的配置说明，却被误写入当前配置摘录仓库。
- 根因：没有先确认用户提供的配置片段属于“展示内容”还是“当前仓库变更”，忽略了本仓库是配置摘录源且用户正在讨论 HTML 展示内容的上下文。
- 修复：立即恢复当前仓库 `.gitignore` 原内容，并删除误新增的 `.gitattributes`。
- 预防：后续展示型、文档型任务中，用户给出的配置片段默认先视为文档内容候选；只有用户明确要求修改当前仓库配置文件时，才落地到仓库根配置。

## LESSON-20260701-github-release-source-crosscheck: GitHub Release Source Crosscheck

- 日期：历史记录迁移，原始日期未记录
- 标签：github, release, update
- 适用场景：判断上游最新版本或 changelog
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：GitHub blob 页面不得作为唯一最新版本依据
- 问题：每日版本检查中，GitHub blob 页面和网页搜索片段一度显示某工具最新版本仍停在旧版本，但 GitHub Releases 与 raw changelog 已发布新版本。
- 根因：只看渲染后的 changelog blob 或搜索片段会受页面缓存、折叠和抓取结果影响，无法保证覆盖最新 release 条目。
- 修复：改用 GitHub Releases 页面和 raw changelog 交叉确认，校正本次版本区间。
- 预防：后续每日版本检查遇到 changelog / release 信息不一致时，至少交叉检查 GitHub Releases、raw changelog 或 tags；不要把 GitHub blob 渲染页或搜索片段当作唯一最新版本依据。

## LESSON-20260701-post-merge-hard-rule-validation: Post Merge Hard Rule Validation

- 日期：历史记录迁移，原始日期未记录
- 标签：git, repository, validation
- 适用场景：合并或快进远程分支后
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：合并远程分支后仍需校验仓库硬规则
- 问题：将远程 `main` 快进到本地后，远程历史中的 `.pi/` 被带入本地，违反本仓库 `.gitignore` 必须严格三行的规则。
- 根因：合并远程分支时只关注 Git 历史推进，容易忽略远程已有提交也可能与当前仓库硬规则冲突。
- 修复：推送前重新校验 `.gitignore` 精确内容，删除 `.pi/` 并保留 `.DS_Store`、`.gitnexus/`、`.trellis/` 三行。
- 预防：后续在 `main` 合并、快进或推送前，都要运行 `.gitignore` 精确三行检查；即使变更来自远程已有提交，也不能跳过本仓库规则验证。
- 状态更新（2026-07-16）：Python 验证会生成仓库根或 `tests/` 下的 `__pycache__/`，因此当前 canonical 契约已调整为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/` 四行；自动化和测试必须断言这四行，不得继续套用历史三行规则。
- 状态更新（2026-07-18）：并行审核确认，把仓库必需的 `AGENTS.md` 和 authoritative `ENTRYPOINT.md` 同时设为 ignored / untracked 会让新 clone 缺少启动规则和版本基线；已恢复二者由 Git 追踪，当前 canonical `.gitignore` 恢复为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/` 四行。
- 状态更新（2026-08-20）：用户要求根 `AGENTS.md` 加入 `.gitignore` 并从远程 `main` 删除；当前 canonical `.gitignore` 为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/`、`AGENTS.md` 五行。`ENTRYPOINT.md` 仍必须追踪。不得把 `AGENTS.md` 的存在当作 Gate。

## LESSON-20260718-required-controls-tracked-source: Required Controls Need a Tracked Source

- 日期：2026-07-18
- 标签：repository, controls, gitignore, bootstrap, review
- 适用场景：调整仓库启动规则、版本基线、根 `AGENTS.md` / `ENTRYPOINT.md` 的追踪或忽略策略
- 严重级别：high
- 来源：8-agent 未提交变更审核及 fresh-clone 契约测试复核
- 问题：将根 `AGENTS.md` 和 `ENTRYPOINT.md` 从索引移除并加入 `.gitignore`，同时又要求每次仓库操作在二者缺失时立即停止；当前工作站保留副本，但新 clone 无法取得规则和版本基线。
- 根因：只验证了既有工作树的“文件仍存在”，没有验证远程 clone 的可恢复性，也没有提供 tracked canonical source 和先于 Gate 执行的 bootstrap。
- 修复：恢复 `AGENTS.md` 和 `ENTRYPOINT.md` 由 Git 追踪，`.gitignore` 恢复四行；README、automation prompt 和契约测试同步改为断言 tracked controls，并让测试直接检查 Git 索引。
- 预防：任何启动前必需文件必须直接受版本控制，或同时提供受版本控制的 canonical source 与可在 Gate 前执行的 bootstrap；不得把文件设为 ignored / untracked 后又把其存在作为所有操作的前置条件。
- 状态更新（2026-08-20）：用户覆盖“根 `AGENTS.md` 必须追踪”。该文件现为 ignored / 本机可选；`ENTRYPOINT.md` 仍必须追踪。与本 lesson 的预防一致：ignored 文件不得再作为全操作前置条件。详见 LESSON-20260820-root-agents-local-only。

## LESSON-20260820-root-agents-local-only: Root AGENTS.md Is Local-Only

- 日期：2026-08-20
- 标签：repository, controls, gitignore, agents
- 适用场景：调整根 `AGENTS.md` 追踪策略、根 `.gitignore` canonical 内容，或编写读取根 `AGENTS.md` 的契约测试
- 严重级别：high
- 来源：用户明确要求将 `AGENTS.md` 加入 `.gitignore` 并从远程 `main` 删除，且不写入 CHANGELOG
- 问题：根 `AGENTS.md` 曾被当作启动必需的 tracked control；若继续让测试和 automation 读取本机忽略副本，会掩盖 fresh-clone 缺失。
- 根因：把本机工作树文件存在当成远程可恢复性。
- 修复：根 `.gitignore` 现为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/`、`AGENTS.md` 五行；从 Git 索引和远程 `main` 移除 `AGENTS.md`，本机可保留；`ENTRYPOINT.md` 仍必须追踪。测试、README、automation prompt 不得把 `AGENTS.md` 存在当作 Gate。
- 预防：不要把 ignored 本地文件当作 clone 可恢复证据；不要因旧四行契约把 `AGENTS.md` 重新加入索引。

## LESSON-20260701-entrypoint-detail-section-contract: ENTRYPOINT Detail Section Contract

- 日期：历史记录迁移，原始日期未记录
- 标签：entrypoint, validation, markdown
- 适用场景：校验 `ENTRYPOINT.md` 详情章节
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：ENTRYPOINT 详情章节校验不得硬编码行名
- 问题：手动 `update` 后的结构化验证脚本硬编码检查 GitNexus 详情章节必须存在 `当前关注版本` 行，但 `ENTRYPOINT.md` 的 GitNexus 章节并不使用该行名，导致校验脚本误报失败。
- 根因：校验脚本没有继续沿用“以版本监控表和当前版本汇总表为主数据源”的规则，而是对单个详情章节写了脆弱的文本包含断言。
- 修复：把验证改回按 Markdown 表格语义解析 `## 0. 版本监控配置`、归档文件区间和 `## 8. 当前版本汇总`，只对确实存在且有稳定结构的字段做断言。
- 预防：后续验证 `ENTRYPOINT.md` 写回结果时，以章节标题、表头和列名为准；不要为某个工具详情章节硬编码一整行文案或假设所有工具章节都有同名字段。

## LESSON-20260709-installer-mcp-generated-config: Installer MCP Generated Config

- 日期：2026-07-09
- 标签：installer, mcp, workflow
- 适用场景：修改根安装脚本、`onboard.py` manualChecks 或已知 MCP server 配置
- 严重级别：medium
- 来源：用户在另一台 Mac 运行 `bash install.sh` 时选择 GitNexus MCP 后，脚本要求手动输入已可从全局 `gitnexus` CLI 推断的 MCP 命令。
- 问题：GitNexus CLI 已经全局安装，MCP 配置实际只需要本机 `gitnexus` 可执行文件路径和 `mcp` 参数，但安装器仍把 GitNexus 当作完全自定义 stdio server，让用户手输命令。
- 根因：`onboard.py check` 没有为 GitNexus MCP 产出结构化 `mcpServerConfig`，根安装脚本也只对 Maestro MCP 读取生成配置，导致已知 server 的配置事实和交互式安装流程脱节。
- 修复：让 `onboard.py check` 在检测到本机 `gitnexus` CLI 路径时生成 `command = <detected path>`、`args = ["mcp"]` 和 JSON / TOML 示例；`install.sh` / `install.ps1` 消费这份配置，只有路径缺失时才回退到人工输入。
- 预防：后续新增或维护已知 MCP server 时，优先在 `onboard.py` 的 manual check 中沉淀 `mcpServerConfig`，根安装器只适配选定 platform；不要把可检测的 command / args / env 重新变成人工输入。

## LESSON-20260709-external-skill-rename-canonical: External Skill Rename Canonical

- 日期：2026-07-09
- 标签：installer, skills, workflow, migration
- 适用场景：维护 external Skill 列表、mattpocock/skills 映射、install/reset 迁移逻辑
- 严重级别：medium
- 来源：用户在另一台 Mac 运行 `bash install.sh` 时，`to-prd` 和 `to-issues` 安装失败；上游 mattpocock/skills 已改为 `to-spec` 和 `to-tickets`。
- 问题：本仓库仍把旧 Skill 名称和旧 subpath 当作 canonical，安装器克隆上游后找不到唯一匹配目录，fallback 扫描列出大量候选并失败。
- 根因：external Skill 配置没有跟随上游 frontmatter / 目录名更新，也没有把旧名作为 legacy alias 纳入迁移删除流程。
- 修复：将默认外部 Skill、模板编排和 subpath 映射迁到 `to-spec` / `to-tickets`；`to-prd` / `to-issues` 只作为 legacy alias；`init` / `reset` 和直接 external install 检测到旧目录时先删除，再安装 canonical 新目录。
- 预防：后续维护 external Skill 时，先用上游仓库当前 `SKILL.md` frontmatter 和目录结构确认 canonical 名称；旧名只能进入 alias / migration，不要继续放在默认安装列表或长期 workflow 主链路中。

## LESSON-20260711-external-skill-transaction-path-safety: External Skill Transaction Path Safety

- 日期：2026-07-11
- 标签：installer, skills, rollback, path-traversal, validation
- 适用场景：修改 External Skill stable manifest、上游 source promotion、canonical 存在性检查、legacy migration 或事务替换逻辑
- 严重级别：critical
- 来源：External Skills stable fallback 实现后的独立 review handoff 与回归测试
- 问题：stable manifest 和 promotion 配置中的绝对路径或 `..` 可逃逸声明根目录；只有文件存在但 frontmatter 无效的 canonical 会阻止重装并导致有效 legacy 被删除；事务恢复失败后 finally 仍删除 rollback 目录，可能销毁唯一可恢复副本。
- 根因：路径由多个调用点直接拼接而没有统一 containment seam，canonical 检测只判断 `SKILL.md` 文件存在，rollback 生命周期没有区分“完整恢复”和“恢复仍有错误”。
- 修复：集中使用解析后 containment 校验拒绝绝对路径、`..` 和 symlink 逃逸；canonical 与安装源使用同一完整 Skill 验证；rollback 仅在 commit 成功或完整恢复后清理，恢复不完整时在结果中返回并保留目录路径。
- 后续策略：External Skill 默认 `auto` 与显式 `stable` 均从受管 stable set 离线安装；只有显式 `upstream` 才获取当前上游，且任一来源验证失败都直接报错，不做自动 fallback。维护安装器时必须同时验证 source root containment、完整 canonical 语义和最坏情况下的备份所有权；回归测试至少覆盖 `auto` 不调用 Git、显式 upstream 独立行为、路径逃逸、无效 canonical + 有效 legacy，以及 restore 二次失败后备份仍存在。

## LESSON-20260717-mode-exit-reentry-contract: Mode Exit Must Define Re-entry Lifecycle

- 日期：2026-07-17
- 标签：agents, workflow, caveman, state-machine, validation
- 适用场景：修改 Agent 自动模式、手动模式、退出 / 恢复指令、任务级或会话级状态，以及相应文本契约测试
- 严重级别：medium
- 来源：Caveman auto-lite 实现后的 Review handoff
- 问题：通用 `normal mode` 等退出指令只恢复了当前答复，没有禁止已经满足阈值的自动模式在同一任务内再次进入；测试只断言孤立关键词，删除完整资格条件或退出生命周期后仍可能通过。
- 根因：规则没有把手动模式、任务级自动退出、会话级自动退出和配置 `off` 建模成有优先级的状态；文本契约测试也没有按完整行为子句锁定前置条件、作用域和重入条件。
- 修复：明确通用退出建立任务级自动退出，会话级退出优先于任务级状态，显式手动启动不清除自动退出，配置 `off` 优先级最高；回归测试改为断言成组资格条件、退出作用域、显式恢复和新任务重算语义。
- 预防：后续新增任何自动模式或退出命令时，必须同时定义状态作用域、优先级、何时清除、是否允许重入和新任务 / 新会话边界；文本契约测试必须断言完整行为子句，不能只检查模式名或命令词存在。

## LESSON-20260716-orca-hub-tool-boundary: Orca CLI and Hub Have Separate Control Planes

- 日期：2026-07-16
- 标签：orca, hub, tools, worktree, automation
- 适用场景：修改 Orca worktree 元数据、检查或运行 Orca automation、向当前 harness peer 发送消息
- 严重级别：medium
- 来源：本次 SBTD Onboard 重命名任务中，创建 Orca feature branch 后尝试用 Hub `send` 更新 worktree 状态。
- 问题：Hub `send` 因没有有效 peer recipient 而失败；它不能更新 Orca worktree comment，也不能替代 Orca automation / worktree 命令。
- 根因：把当前 harness 的 peer 协调控制面与 Orca 应用持久化的 worktree / automation 控制面混为一谈。
- 修复：worktree comment 使用 `orca worktree set --worktree active --comment ... --json`；automation 使用 `orca automations show/edit/run`；Hub 只在 `hub list` 返回精确 peer id 后用于会话内 peer 消息。
- 预防：任务涉及 Orca 状态时先读取 `orca-cli` Skill 并使用 `orca`；涉及 subagent peer 协调时才使用 Hub，且发送前先确认 roster。一个控制面的成功或失败不得推断另一个控制面的状态。

## LESSON-20260716-orca-automation-live-lookup: Orca Automation Mutation Requires Live Lookup

- 日期：2026-07-16
- 标签：orca, automation, cli, prompt, validation
- 适用场景：读取、修改或验证 Orca live automation，尤其是把版本化 prompt 同步到定时任务时
- 严重级别：medium
- 来源：同步 `SBTD Workflow Tools Version Check` prompt 时，复用了先前会话中的 automation id，并误用不存在的 `--prompt-file` 参数。
- 问题：缓存的 automation id 已失效，`orca automations edit` 返回 `Automation not found`；当前 CLI 也不支持 `--prompt-file`，首次同步未生效。
- 根因：把先前查询到的 live id 和假设的文件参数当作稳定接口，没有先用当前 Orca runtime 重新枚举 automation 并检查命令返回的有效参数。
- 修复：先运行 `orca automations list --json`，按精确名称定位当前 id；再用 `orca automations edit --id <id> --prompt <完整内容> --json` 更新，并用 `show --json` 逐字段确认 prompt、enabled、schedule、timezone、workspace mode 和 workspace path。
- 预防：每次修改 live automation 都必须在当前 runtime 中按名称重新定位 id，不复用历史会话 id；参数错误时以 CLI 返回的 `validFlags` 为准；修改后必须比较完整 prompt 并复核调度元数据。

## LESSON-20260718-automation-sync-trigger-separation: Separate Prompt Maintenance From Live Sync

- 日期：2026-07-18
- 标签：automation, prompt, sync, update, workflow
- 适用场景：修改版本化 automation prompt、普通仓库变更、执行 `sync` / `同步` 或 `update` / `更新`
- 严重级别：high
- 来源：用户纠正 automation prompt 的同步触发语义
- 问题：规则曾要求版本化 prompt 一经修改就立即写入 Orca live automation，并把每次 `update` 也绑定到 live prompt 重同步，超出了用户期望的触发范围。
- 根因：混淆了“普通代码改动后评估仓库内版本化 prompt 是否需要维护”“显式 sync 时把版本化 prompt 发布到 Orca”和“update 只推进版本基线并归档”三个独立动作。
- 修复：普通仓库改动只评估并按需更新 README 两份文件和版本化 prompt；只有显式 `sync` / `同步` 才读取 live automation、比较完整 prompt 并仅在存在差异时同步；`update` / `更新` 不检查、不修改也不同步版本化 prompt 或 live automation。
- 预防：新增维护或发布规则时，必须分别定义仓库源文件维护触发器、外部系统发布触发器和无关流程，不能用“每次修改后立即同步”把三者合并。

## LESSON-20260718-generated-agent-alias-target: Generated Agent Aliases Need a Live Canonical Target

- 日期：2026-07-18
- 标签：repository, skills, symlink, claude, discovery
- 适用场景：运行 Skills CLI、调整 Skill discovery 路径、提交 `.claude/skills` / `.agents/skills` 或迁移 canonical Skill 目录
- 严重级别：high
- 来源：`v1.0.0` 发布后检查根 `.claude/` 目录时发现 tracked broken symlink
- 问题：仓库提交了 `.claude/skills/sbtd-workflow-onboard -> ../../.agents/skills/sbtd-workflow-onboard`，但 `.agents/skills/sbtd-workflow-onboard` 不存在；Claude Code 无法通过该 alias 加载 Skill，且该路径与根目录自包含 Skill 的公开安装边界冲突。
- 根因：布局迁移时保留了本地 Skills CLI 生成的项目级 Agent alias，却没有验证 symlink target、Git 追踪状态和当前 canonical discovery entrypoint 是否一致。
- 修复：从仓库删除 `.claude` broken symlink，继续以根 `sbtd-workflow-onboard/SKILL.md` 为唯一公开 discovery entrypoint，并增加仓库契约测试禁止重新提交该 alias。
- 预防：提交任何 Agent-specific Skill alias 前必须同时验证 link target 存在、target 是当前 canonical source、alias 属于仓库设计而非本地安装副作用；全局安装模式不得把 `.claude/skills`、`.agents/skills` 等项目级生成物加入版本控制。

## LESSON-20260718-auto-lite-monotonic-state: Auto-lite Needs Monotonic Task State

- 日期：2026-07-18
- 标签：caveman, auto-lite, agents, conversation, compaction
- 适用场景：修改对话自动模式、任务连续性、完整输出保护区、用户退出或 context compaction / handoff 规则
- 严重级别：high
- 来源：其他项目使用本仓库 SBTD workflow 执行长时间 G5 任务时，已经超过 3 次中间更新、5 个工具结果并进入重复验证轮次，但整个会话从未自动进入 `auto-lite`。
- 问题：数字阈值已经满足，外围资格条件仍在每次回复重新主观判断；保护区结束后要求再次满足资格，“新的用户请求”又会把继续、确认、授权和故障恢复误当成任务重置，导致自动模式可以无限推迟。
- 根因：规则只有触发条件，没有单调 eligibility latch、明确的任务身份和消息级保护覆盖；prompt-level 临时状态也没有定义 compaction / handoff 连续性，且 external Skill 的手动“不宣布模式”语义与全局首次提示没有明确职责 seam。
- 修复：由全局 AGENTS 模板独立拥有自动生命周期；达到任一阈值即锁存 `autoLiteEligible=true`，下一条 eligible commentary 必须进入；保护区只覆盖当前回复并保留状态，只有新的主要目标重置，配置缺失按 auto 处理，compaction / handoff 保留任务状态。external `caveman` Skill 保持上游原样，只负责手动风格。
- 预防：任何提示词驱动的自动模式都必须定义单调资格、强制转换、状态保持、精确重置事件和优先级；保护区不得隐式清空状态，静态文本契约之外还要在部署后的真实消费会话中验证触发和恢复证据。

## LESSON-20260718-grill-post-ddd-gate: Composite Skills Need Explicit Post-review Gates

- 日期：2026-07-18
- 标签：grill-with-docs, domain-modeling, ddd, workflow, review-gate
- 适用场景：修改需求澄清、PRD / design / Trellis 入口、领域建模或 composite Skill 的后置审核编排
- 严重级别：high
- 来源：其他项目使用 SBTD workflow 时，完整执行 `grill-with-docs` 后有时会继续调用 `book-ddd-distilled-modeling`，有时因 `grill-with-docs` 内嵌的 external `domain-modeling` dependency 已运行或 Agent 主观认为边界清晰而直接进入下一阶段。
- 问题：现有规则只把 `book-ddd-distilled-modeling` 描述为有领域歧义时的按需步骤，没有把它定义为每次完成 `grill-with-docs` 的强制后置条件，也没有规定独立、可见、可阻断的审核输出。
- 根因：composite Skill 的内部依赖与后置 reviewer 职责没有建立明确 seam；项目模板和 Trellis Skill 仍使用条件式流程，导致 Agent 能把 interview-time modeling 误当成 independent review。
- 修复：全局规则统一定义 post-grill gate；无论 Agent 自发调用还是用户主动调用，每次完整结束后立即运行 bundled `book-ddd-distilled-modeling`，输出状态为 `confirmed` / `needs-clarification` / `blocked` 的 `DDD Boundary Review`，未确认则回到澄清或阻断后续阶段。external `grill-with-docs` 和 `domain-modeling` 保持上游原样。
- 预防：任何 composite Skill 要求后置独立审核时，必须同时定义无条件触发事件、内部步骤不可替代、可见输出 schema、失败回路、阻断边界，并在全局规则、项目模板、生命周期 Skill 和 reviewer Skill 中保持一致。

## LESSON-20260718-objective-book-development-gates: Mandatory Risk Gates Need Objective Triggers

- 日期：2026-07-18
- 标签：book-derived, workflow, development, mandatory-gate, risk
- 适用场景：修改 book-derived Skill 的开发阶段编排、风险审核、阶段门禁或按需边界
- 严重级别：high
- 来源：其余 4 个 bundled `book-*` Skill 起初虽增加了客观触发与通过状态，但交叉审查发现仍缺少可执行 lifecycle、缺 Skill 的阻断优先级、legacy/refactoring 死锁回路、testing-tool gate 顺序和 Onboard 激活边界。
- 问题：只有 `required` / `on-demand` 与 reviewer 状态会让 Plan 在执行前虚构结论；legacy 要求先装安全网、refactoring 又要求安全网先存在时会互相阻断；release readiness 过早运行会在验证证据尚未完成时给出 `ready`；通用“Skill 不可用直接跳过”还可能覆盖强制门禁。
- 根因：触发条件、Plan 状态机、reviewer 结果、修正回路、跨 Gate 依赖顺序和安装激活条件没有作为一个完整 contract 设计。
- 修复：`Book Gate Plan` 独立记录 `planned` / `running` / `passed` / `blocked` / `not-required`，reviewer status 只在实际运行后填写；命中门禁缺 Skill 或证据时一律 `blocked`。legacy 的 `seam-required` 只允许 refactoring 进入 `safety-seam-only`，建立并验证最小行为保持 seam 后回到 characterization，再正常重跑 refactoring。Release Readiness 固定在所有适用 testing-tool gate 与 project validation 后执行，并区分不可豁免的 required validation 与可由 accountable owner 接受的 optional check。Onboard contract 明确只有正常 `init` / `reset` 成功写入全局规则并安装 bundled / external Skills 后才激活，public Skills CLI bootstrap 与 `init-projects` 不单独激活运行时门禁。
- 预防：强制风险审核必须同时定义 objective trigger、execution stage、Plan lifecycle、visible reviewer result、pass state、retry loop、blocked priority、cross-gate dependency order、missing-Skill semantics、activation boundary 和 unmatched on-demand boundary；测试必须覆盖修正回路与顺序，而不只是静态关键词。

## LESSON-20260718-sync-table-current-source: Sync Tables Must Use Current Tracked Rules

- 日期：2026-07-18
- 标签：sync, agents, source-of-truth, automation, skills
- 适用场景：执行本地 sync、增加 bundled Skill、维护同步允许列表或版本检查 automation 的验证范围
- 严重级别：high
- 来源：显式 `sync` 已执行时，当前 tracked `AGENTS.md` 的同步表已经包含 bundled `web-ui-autotest-generator`，但执行过程依赖了会话中较早注入的规则副本，实际目标清单漏掉该 Skill。
- 问题：最终报告把 `web-ui-autotest-generator` 误报为“不在显式同步表”，导致 tracked source 与本地落地行为不一致；版本化 automation prompt 也没有验证同步表覆盖 catalog 中要求全局同步的 bundled Skills。
- 根因：把会话注入或历史摘要当成当前工作树事实，没有在写入本地目标前重新读取 tracked `AGENTS.md` 的同步表并从表中生成清单。
- 修复：确认当前同步表已经包含 `web-ui-autotest-generator` 的 source / target 映射，不重复写入；README / HTML 明确该允许列表项，contract test 锁定精确表格行；版本检查 prompt 增加 bundled Skill 同步表覆盖检查，并把最新 CHANGELOG 维护契约纳入评估、验证和最终报告。
- 预防：每次显式 sync 都必须在 preflight 后读取当前工作树 `AGENTS.md`，从表格生成目标清单，再逐项复制和校验；缓存上下文只用于定位，不能替代 tracked source。新增 bundled Skill 时同步更新 catalog、同步表、README、automation validation 和 contract test。

## LESSON-20260719-orca-automation-detached-agent-pty: Blank Automation Tabs Can Hide a Detached Agent PTY

- 日期：2026-07-19
- 标签：orca, automation, terminal, pty, renderer, debugging
- 适用场景：手动执行 Orca automation 后新建了终端标签，但标签只显示旧 shell prompt、空白画面或没有 Agent 进度
- 严重级别：high
- 来源：手动执行 `SBTD Workflow Tools Version Check` run 7 时，Orca UI 中的新标签持续空白，但 automation 最终成功完成并生成了完整 output snapshot。
- 问题：空白标签容易被误判为 prompt 未发送或 Agent 没有启动，进而重复点击运行；本次相邻 run 6 在已有大量 TUI 输出后以 `Automation process exited with code -1` 结束。
- 根因：同一个 automation tab / leaf 同时关联了两个 live PTY。UI renderer 绑定到空闲 shell PTY，显示 15:06 的旧 prompt；run record 的 `terminalPtyId` 指向另一个实际运行 `omp` 的 PTY。后者的 `terminal show` preview、terminal-history checkpoint 和进程树持续更新，但 `paneRuntimeId` 为 `-1`，没有绑定到可见 pane。
- 修复：先用 `orca automations runs --id <id> --json` 取得 run 的 `terminalPtyId`，再与 `orca terminal list/show` 的 `ptyId`、`tabId`、`leafId` 和 `paneRuntimeId` 交叉核对；运行中以 run status、agent PTY preview 和最终 `outputSnapshot` 判断真实状态，不修改 prompt，也不因空白标签盲目重跑或终止。只有 run 已完成并确认 output snapshot 后，才可清理重复的空闲 shell pane。可见输出的根治需要 Orca runtime 保证 automation tab 只绑定 Agent PTY，或在检测到重复 PTY 时把 renderer 重新绑定到 run 的 `terminalPtyId`。
- 预防：排查 automation 空白终端时必须区分“run 未 dispatch”“Agent PTY 无输出”和“Agent PTY 有输出但 renderer 绑定到另一个 shell PTY”三种情况；UI 截图、run record、terminal metadata、terminal-history checkpoint 和进程 TTY 必须互证，不能只看空白 pane。

## LESSON-20260719-installer-output-and-line-merge-contracts: Installer Writes Need Explicit Output And Merge Contracts

- 日期：2026-07-19
- 标签：installer, skills, gitignore, idempotency, paths, validation
- 适用场景：第三方 CLI 生成项目文件，或把模板内容增量合并到已有配置文件
- 严重级别：high
- 来源：`--init-projects` 把 React Bits Skill 写到项目根，并把 `.gitignore` 模板整段重复追加的用户反馈与回归测试
- 问题：`npx shadcn add @reactbits-starter/skill` 按 registry 默认 target 在项目根创建 `SKILL.md`，而预期位置是 `.agents/skills/react-bits-pro/SKILL.md`；项目 `.gitignore` 只要与完整模板块不完全相同，安装器就再次追加整个模板，复制已有规则。
- 根因：安装器把“命令成功”和“目标产物位于正确路径”等同，并把声明型配置的包含关系建模为整段字符串包含，而不是模板原子条目的差集。
- 修复：React Bits 安装显式传入 `--path .agents/skills/react-bits-pro --overwrite --yes`，随后校验目标 `SKILL.md` 存在；`.gitignore` 按精确非空行求有序差集，只追加缺失行，校验也复用同一差集函数。
- 预防：第三方生成命令必须显式指定并复验最终产物路径、覆盖和备份语义；增量模板合并必须按配置格式的原子条目比较，并用“部分已有内容 + 连续执行两次”的回归测试证明不删除、不重复和幂等。

## LESSON-20260726-update-archive-sequence: Update Archive Suffixes Must Be Numeric

- 日期：2026-07-26
- 标签：update, archive, workflow, validation
- 适用场景：维护或执行手动 `update` / `更新` 的 `UPDATE.md` 归档规则
- 严重级别：medium
- 来源：发现 2026-07-24 与 2026-07-25 的归档文件被命名为 `UPDATED-...-index.md`
- 问题：规则将 `index` 写成文件名格式中的字面量，实际归档没有数字序号，且同日多次归档会发生命名冲突。
- 根因：占位符语义没有写清，也没有针对规则文本和现有归档名的契约测试。
- 修复：将格式改为 `UPDATED-yyyy-mm-dd-<正整数序号>.md`，规定当日最大序号加一、无当日归档时从 `1` 开始，并更正错误归档名。
- 预防：任何由 Agent 直接执行的文件命名模板必须区分字面量和占位符，明确生成算法；契约测试同时验证规则文本与受管目录中的实际文件名。

## LESSON-20260726-orca-managed-codex-home: Diagnose MCPs In Active Codex Home

- 日期：2026-07-26
- 标签：orca, codex, mcp, configuration, debugging
- 适用场景：OMP / Orca 新会话启动 MCP 失败，或 `codex mcp` 与 `~/.codex/config.toml` 的内容不一致
- 严重级别：high
- 来源：新 OMP 会话的 GitNexus transport 与 computer-use spawn 失败排查
- 问题：先修改了 `~/.codex/config.toml`，但 Orca 会话实际通过 `$CODEX_HOME` 使用受管 home；`codex mcp get` 仍展示旧的 computer-use 相对路径。
- 根因：把用户默认 home 误当成当前 Orca 会话的 active Codex home，没有先读取 `CODEX_HOME` 并核对 CLI 的有效 MCP 配置。
- 修复：先读取 `CODEX_HOME`，在该目录的 `config.toml` 修正 MCP 定义，再用 `codex mcp get <name> --json` 和实际 MCP initialize probe 验证。GitNexus transport closed 则直接探测 `gitnexus mcp` 的 stderr，按其安装脚本补齐缺失 native module。
- 预防：任何 OMP MCP 启动异常都先以 `CODEX_HOME` 和 `codex mcp get` 确认有效配置；不要仅修改 `~/.codex` 或依据文件存在性推断当前会话会加载它。

## LESSON-20260728-trellis-omp-pi-flag-separation: Keep OMP And Pi Trellis Flags Distinct

- 日期：2026-07-28
- 标签：onboard, trellis, omp, pi, installer, validation
- 适用场景：维护 Onboard 的 Trellis 平台参数、安装器帮助或全局 Skill 初始化引导
- 严重级别：high
- 来源：用户发现要求初始化 OMP 与 Codex 时，实际 Trellis 命令错误使用了 `--pi --codex`。
- 问题：Onboard 的 Trellis allow-list 只接受 `pi`，虽然当前 Trellis CLI 已提供独立的 `--omp`；Skill 和安装器帮助未明确两者不得替换。
- 根因：把相近的产品名和包名误当作同一 Trellis 平台标志，且没有在真实 `trellis init` argv seam 上锁定 OMP、Pi 与其他平台的顺序和独立性。
- 修复：将 `omp` 加入 Trellis allow-list，明确 `omp → --omp` 与 `pi → --pi`，并用记录 fake `trellis` argv 的 `init-projects` 回归测试断言 `--omp --pi --codex`。
- 预防：平台名跨 Agent CLI、npm 包和下游 CLI 时必须按命名空间分别建模；对相近名称必须查询下游 CLI help，并用 argv 级集成测试同时覆盖各自 flag 和顺序。

## LESSON-20260827-trellis-init-empty-yes-defaults: Empty Trellis Init Flags Are Not Neutral

- 日期：2026-08-27
- 标签：onboard, trellis, init, platform, installer, validation
- 适用场景：维护 Onboard `init` / `plan` 的 Trellis 平台参数、Agent `--platform` 与 `trellis init` 的映射
- 严重级别：high
- 来源：demo 项目指定目标平台 Codex 后，`onboard.py init` 生成 `.claude/` / `.cursor/` 而没有 `.codex/`
- 问题：用户给了 Agent 平台 `codex`，但 `trellis init -u ... --yes --skip-existing` 未带 `--codex`。Trellis 在 `--yes` 且无平台 flag 时默认安装 Claude 和 Cursor。
- 根因：Skill 把 Trellis flags 写成可选独立命名空间，Agent 因此省略 `--trellis-platform`；Onboard 把空列表原样交给 `trellis init --yes`。`plan --json` 也不展示将要执行的 `trellis init` 命令。
- 修复：`--platform codex|claude|kimi` 在未给 `--trellis-platform` 时作为默认 Trellis flag；空列表不再交给 `trellis init --yes`；`oh-my-pi` 仍须显式 `omp`/`pi`；`plan --json` 增加 `trellisInit.command`。
- 预防：不要把“不得从 Oh My Pi 推断 `--pi`”扩成“用户指定 Codex 也不传 `--codex`”。对会改变下游默认安装集的 CLI，空 flag 必须视为危险默认，而不是中性省略。

## LESSON-20260811-stable-promotion-candidate-prune-safety: Stable Promotion Pruning Must Stay Contained

- 日期：2026-08-11
- 标签：onboarding, stable-mirror, promotion, symlink, migration, validation
- 适用场景：修改 external Skill stable promotion、清理上游删除的 Skill 目录或实现 stable prune
- 严重级别：high
- 来源：mattpocock/skills `v1.2.3` promotion 删除 `writing-great-skills` 时的安全复核
- 问题：stable promotion 需要清理已不在 manifest 中的旧 Skill 目录；若直接修改 live mirror，或先对 `stable/skills` 调用 `resolve()` 再检查 symlink，删除可能越过 mirror 边界。
- 根因：把 candidate tree 的受管清理和 live tree 的直接删除混同，并且忽略 `Path.resolve()` 会隐藏路径本身是 symlink 的事实。
- 修复：只在 promotion candidate 中计算 manifest 的受管 direct-child Skill 目录并 prune，校验未解析的 `skills/` 是非 symlink 目录后才 resolve；解析后的每个 manifest `stablePath` 必须仍位于该受管根下。通过测试覆盖 retired Skill prune 和 symlink root 拒绝，再原子替换 stable mirror。
- 预防：任何受管镜像删除都必须先在候选目录完成、验证后 swap；不对 live stable tree 使用直接递归删除。路径安全检查必须在解析前拒绝 symlink，并在解析后重新验证 containment。

## LESSON-20260811-external-skill-legacy-identity: Legacy Skill Deletion Needs Identity Proof

- 日期：2026-08-11
- 标签：onboarding, skills, migration, safety, data-preservation, validation
- 适用场景：修改 external Skill rename、legacy cleanup 或 reset migration
- 严重级别：high
- 来源：mattpocock/skills `writing-great-skills` → `writing-for-agents` canonical 迁移安全复核
- 问题：仅按旧目录名识别 predecessor，会把用户在同名目录中维护的不同 Skill 备份并删除；仅以 `Path.exists()` 检测则会忽略 dangling legacy symlink，而 preflight 早退可能留下完整 staging tree。
- 根因：路径名称被错误视为受管内容的所有权证明，normal install transaction 与 canonical 已存在时的 legacy-only cleanup 都没有校验 `SKILL.md` frontmatter；代码把“可删除 filesystem entry”误建模为“存在且可跟随的路径”，且 cleanup scope 没有覆盖 preflight return。
- 修复：在所有 predecessor 的 transaction commit、backup 或 delete 前验证其是非 symlink 常规目录、包含非 symlink `SKILL.md`，且 `name` 等于预期 legacy identity；对存在或 symlink 的 entry 都执行该检查，不一致时记录 `preflight-legacy-identity` 失败、清理 staging、保留目标并阻断迁移。
- 预防：任何迁移删除都必须同时验证路径、文件类型和内部身份；目录名、存在性或 replacement canonical 有效都不能单独授权删除。所有 owned staging 目录必须由覆盖每个 early return 的 cleanup scope 释放；测试必须同时覆盖 matching predecessor 的成功删除、user-owned identity conflict 保留和 dangling symlink 拒绝。


## LESSON-20260814-gitnexus-native-module-transport: GitNexus MCP Needs Its Native Module

- 日期：2026-08-14
- 标签：gitnexus, mcp, node, native-module, transport
- 适用场景：GitNexus MCP 报 `Transport closed`、全局 GitNexus 安装或 MCP stdio 启动诊断
- 严重级别：high
- 来源：当前 OMP/Codex session 的 GitNexus MCP transport 启动失败
- 问题：MCP client 显示 `gitnexus: Transport closed`，但 `codex mcp get gitnexus` 仍显示有效 stdio command，容易误判为 MCP 配置或仓库索引问题。
- 根因：`@ladybugdb/core/lbugjs.node` 未由 GitNexus 全局安装的 lifecycle 产物写入 package directory；进程在 MCP `initialize` 之前退出。
- 修复：从当前 `CODEX_HOME` 定位生效 MCP command 后，运行该 GitNexus 安装目录内 `node_modules/@ladybugdb/core/install.js`，再以 JSON-RPC `initialize` 握手验证 serverInfo 响应。
- 预防：先用 `CODEX_HOME` 和 `codex mcp get gitnexus` 确认生效 command；再运行真实 MCP handshake 区分 transport 启动失败与“Repository not indexed”。不要因索引缺失重装或修改 MCP 配置。
- 状态更新（2026-08-24）：全局 `gitnexus@1.6.9` 在当天 09:20 被重装后，`lbugjs.node` 再次从 `@ladybugdb/core` 消失，但 `@ladybugdb/core-darwin-arm64/lbugjs.node` 仍在。`npm config get ignore-scripts` 为 `false`，说明重装仍可能跳过或未持久化 `@ladybugdb/core` 的 `install` 脚本。不要把“已经修过一次”当成模块仍在。

## LESSON-20260824-gitnexus-claude-json-shebang-path: Pin Claude GitNexus MCP To Explicit Node

- 日期：2026-08-24
- 标签：gitnexus, mcp, claude, omp, path, shebang, transport
- 适用场景：OMP 报 `Failed: gitnexus [config: ~/.claude.json]: Transport closed`，或 GUI / 干净 PATH 下启动 `gitnexus mcp`
- 严重级别：high
- 来源：OMP 从 `~/.claude.json` 导入 GitNexus MCP 失败；同一错误在 2026-08-20 只修了 native module 后又复发
- 问题：`~/.claude.json` 使用绝对路径 `.../bin/gitnexus` + `args=["mcp"]`，在本机 nvm PATH 下 handshake 成功，但 OMP 仍报 `Transport closed`。
- 根因：`gitnexus` 是 `#!/usr/bin/env node` 脚本。OMP 导入 Claude 配置时 PATH 往往只有 `/usr/bin:/bin:...`，没有 nvm 的 `node`，进程以 exit 127 / `env: node: No such file or directory` 立即退出，被汇总成 Transport closed。这与缺失 `lbugjs.node` 是独立根因，可同时存在。
- 修复：把 `~/.claude.json` 的 command 改成 nvm 绝对 `node`，args 改成 GitNexus CLI 绝对路径 + `mcp`，并设置 `env.PATH` 包含该 nvm `bin`。用干净 PATH 复跑 JSON-RPC `initialize`，确认不再依赖 `/usr/bin/env node`。
- 预防：诊断 OMP `config: ~/.claude.json` 失败时，必须同时做带 nvm PATH 和干净 PATH 的 handshake。不要只在当前 shell 里跑通 `gitnexus mcp` 就认为 Claude 配置对 GUI 启动安全。

## LESSON-20260831-readonly-cli-probe-side-effect: Read-only Checks Must Not Bootstrap CLI State

- 日期：2026-08-31
- 标签：onboard, cli, omp, side-effect, validation, read-only
- 适用场景：`check` / preflight / provider detection 调用第三方 CLI 查询版本、plugin 或配置
- 严重级别：high
- 来源：`onboard.py check --json` 在隔离 HOME 下探测 OMP Ponytail provider
- 问题：只读 `check --json` 在用户尚无 `~/.omp` 时执行 `omp plugin list --json`；OMP CLI 启动即创建 `.omp`，违反“缺失则跳过且不得创建”的契约，现有回归测试以 `FileExistsError` 暴露副作用。
- 根因：把语义上只读的子命令当成进程级无副作用，没有先检查平台配置根是否存在，也没有在检测契约中验证 HOME 字节状态。
- 修复：OMP provider 探测仅在 `~/.omp` 已存在时执行 CLI；缺失时报告 per-platform `not-configured`。保留 configured OMP 的官方 plugin 冲突检测，并用隔离 HOME 聚焦测试覆盖。
- 预防：调用第三方 CLI 的 read-only 子命令前，先验证它不会 bootstrap 配置 / cache；无法证明时先检查既有配置根或在隔离 HOME 运行。check/preflight 测试必须断言目标 HOME 没有新增路径。