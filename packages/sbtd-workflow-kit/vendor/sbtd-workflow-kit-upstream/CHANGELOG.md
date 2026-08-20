# CHANGELOG

本文件按 Git tag 记录用户可见变更，最新版本位于最上方。未发布章节在创建对应 tag 后补充发布日期。

## v1.0.7（未发布）


### 新增

- 为 scenario-backed 验证证据新增 `validation-evidence.v2.schema.json`、确定性语义 validator 和仓库级共享 fixtures（`tests/fixtures/validation-evidence/`）。v1 继续服务通用 / 历史 report evidence；BDD 可追溯性必须从 SHA-verified JUnit XML 或 Playwright JSON 中提取唯一 passed case，并要求 case 内 `sbtd.sourceLocatorDigest` 等于重算 locator。

### 变更

- 对齐 Trellis stable 更新后的 hook 生效边界：升级并运行 `trellis update` 后，如更新涉及 SessionStart、PreToolUse 或其他 hook 配置，现要求先重启对应 Agent host / IDE，再验证新会话身份或 hook 行为，避免将既有进程的旧配置误判为更新已生效。
- 对齐 Trellis 的 active-task pointer containment：`task.py start` / `set-*` / subtask 与平台读取器不得跟随解析到项目外的任务路径；升级后不要假设 `trellis update` 会改写既有 session pointer，越权 pointer 按无任务处理。

### 修复

- 将 mattpocock/skills stable 镜像提升到 `v1.2.3`，使 `diagnosing-bugs` 的命令、输出和捕获产物先脱敏，并采用跨 Agent harness 的 subagent 表述。
- 恢复 v1 报告 checksum / digest 一致性门，并写明 v1 Schema 只校验 digest 形状；补齐 locator 规范化：`ensure_ascii=False`、`./` 段丢弃、commit trim/lower、空 optional→`null`；把 stale-commit 收窄为 declared-SHA 一致性；统一 evidence schema / validator 路径到 `project-validation` Skill root；保留 untrusted environment 拒绝条件；把 v2 fixtures 移出 bundled Skill 树，避免 `init` / `reset` 整目录安装把 JUnit / HTML 样例写入项目。
- 修复 `writing-great-skills` 上游删除后的 reset 迁移：其自身及更早的 `write-a-skill` 目录现在都会在 `writing-for-agents` 完整校验并提交后删除；迁移失败保持 fail-closed 和 rollback 语义。
- 修复 `init` / `reset` 在发现 mattpocock legacy 目录身份冲突时仍会先安装 external Skills 并写入全局 / 项目文件的问题：现在在 bundled rename 检查之后、任何写入之前做 identity preflight，冲突时 fail-closed 并保留原目录。

### 变更

- `grilling` 改为 design tree / frontier 的分轮澄清；每轮只提出前置条件已满足的问题，环境事实可并行调查，用户决策仍需等待用户回答。
- 新增 `migrate-external-skills` 全局命令：先对所有受管 mattpocock legacy 目录做 frontmatter identity preflight，再安装 canonical replacement，并迁移或删除 `diagnose`、`write-a-skill`、`writing-great-skills`、`to-prd`、`to-issues` 和 `zoom-out`。

## v1.0.6（2026-08-03）

### 修复

- 修复项目 `.gitignore` 模板误忽略项目 `AGENTS.md`、`CLAUDE.md`、共享 `.agents/skills/**` 和 Trellis 生成的 `.claude/**` 平台集成：这些受管控制文件与生成资产现在默认可追踪，只保留 `.claude/projects/`、`.claude/worktrees/`、`.claude/settings.local.json`、`.omp/plugins/` 等明确的本地运行态忽略项。
- 修复根安装器目标平台参数容易被误解为全局规则平台选择器的问题：`--platform` / `-Platform` 只选择 Agent CLI 与 MCP adapter；默认全局 AGENTS 仍使用 Codex 路径，只有显式 global AGENTS path 才覆盖，project-only 不写全局 AGENTS。
- 修复版本检查自动化的写权限范围：安装器、Onboard 实现、catalog、项目 `.gitignore` 模板与契约测试只可读取、评估或验证；无人值守运行不得修改这些实现和测试资产。

### 迁移

- `init` / `reset` 不会自动删除旧模板已经写入项目 `.gitignore` 的 `.claude/`、`CLAUDE.md`、`.agents/` 或 `/AGENTS.md`；既有项目需要在确认追踪边界后手工移除这些旧行，并用 `git check-ignore` 复核。

### 变更

- External Skill 安装改为 stable-first：默认 `auto` 与显式 `stable` 都从 Onboard 内经过 review、精确 revision 和 checksum 固定的 stable set 离线安装；只有显式 `--source upstream` 才直接获取当前上游，失败时不自动回退。
- 将 14 个受管 external Skills 提升到 stable set `2026-08-03.1`：固定 promotion 时的 mattpocock/skills、impeccable、ui-ux-pro-max-skill 与 shadcn-ui 上游 revision；通过 promotion 流程刷新 tree digest 和许可证文件。
- 项目模板选择以无尾随斜杠的 `.trellis/workspace` 忽略目录或顶级 symlink 及其所有内容，包括 workspace `index.md`、开发者 journal 与 trace；这有意不同于上游 Trellis 默认会 stage workspace 内容的策略。

- 对齐 Trellis 的 Codex hook 上下文恢复路径：bundled `trellis-workflow` 现在要求升级后保留单一 context prelude，并在注入标记不完整时依赖受管的 saved `SubagentStart` 恢复，而非手工粘贴任务数据或放宽注入上限。
- 明确 Trellis 的平台调度边界：共享 `.trellis/**` 只定义 workflow gate，不标识运行平台；当前 host 与 `.codex/**` 或 `.omp/**` 生成资产决定执行机制，二者共存时不得由静态审查强行选择。`codex.dispatch_mode`、Inline 与其 fail-closed fallback 仅属于 Codex；当前 OMP host 使用 OMP `task` worker 和 agent 定义。Channel 保持显式确认的持久协作 runtime；同一变更职责只能有一个写入执行者，用户请求的独立只读复核可以并行。
- 版本检查新增 stable-tag 配置、workflow、migration manifest 与平台集成的强制证据门；Trellis v0.6.10 的 `SubagentStart` 修复不再被误述为首次启用 Codex subagent。
- 移除 `sync` / `update` 流程禁止 Agent 提交和推送的限制；在用户明确指示时，Agent 可以提交并推送已验证的仓库变更。
- `grill-with-docs` 状态透明度不再无条件制造重复确认门：仍必须说明调用状态与原因，但只有调用与跳过存在会改变需求、领域边界或实现决策的实质权衡时才询问用户。
- 版本检查自动化的允许扫描、影响分析和验证范围扩展到根安装器、项目 `.gitignore` 模板与契约测试，并明确无人值守任务不得通过交互提问升级为 `update`、`sync`、commit 或 push。


### 文档

- 新增 OMP SBTD 上游提升 PRD 与运行手册，区分 `640-skills` 已提交上游、KPi Kit / Plugin 集成、npm 发布、用户安装和新 Session 生效等状态，并固定 Plan / Apply、证据与回滚边界。

### 验证

- 完整 Python 契约测试增至 121 项并全部通过；额外以默认 `auto` 实际安装全部 14 个 external Skills，确认统一使用 stable set、无需 fallback 且目标 `SKILL.md` 全部存在。

## v1.0.5（2026-07-28）

### 修复

- 修复手动 `update` / `更新` 将归档文件名后缀字面写为 `index` 的规则错误；归档现在按日期使用从 `1` 开始、当日递增的正整数序号，并已更正 2026-07-24 与 2026-07-25 的归档文件名。
- 修复 Onboard 将 Oh My Pi 与 Pi 混为 Trellis 初始化平台的缺口：`omp` 现在作为独立受支持 flag 透传为 `trellis init --omp`，并明确禁止替换为 `--pi`；`pi` 保持独立语义。

### 许可

- 为 bundled `web-ui-autotest-generator` 增加 `NOTICE`，声明 `Copyright 2026 KunoLu` 和 Apache License 2.0 适用边界；独立安装和本地同步后的 Skill 现在随目录分发完整许可与版权声明。

### 变更

- 对齐 Trellis 的 Pi shared-skills 迁移边界：当项目仍有 legacy `.pi/skills/` 时，bundled `trellis-workflow` 现在要求使用 `trellis update --migrate` 完成受管重命名，避免手工移动造成双重发现或破坏迁移安全检查。
- 对齐 Maestro MCP 的 Cloud 诊断能力：全局规则模板和 `maestro-mobile-e2e` 现在明确在 Cloud upload 终态后可读取 per-flow run 的状态与 artifacts；README 两种格式同步说明该能力只用于诊断，不替代 Maestro CLI 的正式 E2E 执行与报告。
- 对齐 Trellis 的受管更新边界：bundled `trellis-workflow` 和 `trellis-channel` 现在明确子代理上下文注入的默认字节上限、单次跳过关键词、受限的 linked-worktree 信任目录，以及 Codex 子代理模型设置在更新后的保留与复核要求，避免通过无限上下文或宽泛路径信任绕过安全边界。

- 更新 Playwright MCP 的 Onboard 安装引导：当所选 Playwright 发行版提供内置 MCP server 时优先使用 `npx playwright mcp`，否则继续要求选择兼容的专用 server；保留 MCP 可见性确认与项目级 Playwright CLI 不可替代的边界。
## v1.0.4（2026-07-19）

### 修复

- 修复根 Bash 与 PowerShell 安装器中 `--yes` / `-Yes` 仍会询问 `Install project AGENTS.md...` 等 yes/no 问题的语义缺口；两个入口现在统一对全部 yes/no 提示回答 Yes 并跳过最终确认，同时保留无默认值的选择和文本输入。

## v1.0.3（2026-07-19）

### 修复

- 锁定 bundled `web-ui-autotest-generator` 在仓库本地 sync 允许列表中的完整 source / target 映射，并让版本检查 automation 同时校验 bundled Skill 同步覆盖和最新 `CHANGELOG.md` 维护契约。
- 修复根 `install.sh` 在逐项目检查触发 React Bits 选择时误从项目清单 process substitution 读取输入、继而无限输出 `Invalid choice.` 的问题；交互提示现在固定读取脚本启动时保留的原始 stdin，并在输入流关闭时明确失败退出。
- 修复付费 React Bits Skill 被 shadcn CLI 写到项目根 `SKILL.md` 的问题；Bash 与 PowerShell 安装器现在固定写入 `.agents/skills/react-bits-pro/SKILL.md`，已有目标直接覆盖且不留备份，并校验目标实际生成。
- 修复项目 `.gitignore` 只按完整模板块判断、导致部分已有规则被整段重复追加的问题；现在按精确非空行求差集，只追加缺失内容，重复执行保持幂等。
- 将 Bash 与 PowerShell 安装器的启动标识升级为带前置空行的 91 列 `KUNO` / `Tips` 双栏欢迎面板，集中展示 `--platform`、`--projects-root`、`--init-projects`、`--action` 和 `--dry-run`；默认 TTY 延续紫色渐变，显式禁色或非 TTY 使用相同布局的无色版本。同时修复 Bash 将内部 `NO_COLOR=0` 状态误判为外部禁色请求、导致交互终端始终退化为无颜色字符画的问题。
- 修复审核发现的安装器兼容性与契约缺口：Bash 仅在参数解析后初始化交互输入 fd，closed stdin 的 `--help` / 非交互项目模式不再输出 `Bad file descriptor`；PowerShell 脚本恢复 UTF-8 BOM；React Bits 检查提示与自动化版本文件 allowlist 也与实际覆盖、版本基线和输出路径保持一致。
- 修复 UTF-8 BOM `.gitignore` 的逐行比较：比较时忽略首行 BOM、写回时保留原始字节前缀，完整模板第二次执行不再误追加首条规则。

## v1.0.2（2026-07-18）

### 许可

- 新增根目录 `LICENSE`，本仓库原创内容采用 Apache License 2.0。
- 确认 bundled `web-ui-autotest-generator` 为个人独立实现；将其目录内的 MIT License 替换为与仓库根一致的 Apache License 2.0，保证独立安装时许可文本随 Skill 一起分发。
- 为自包含 `sbtd-workflow-onboard` 的原创内容增加与仓库根完全一致的 Apache License 2.0 `LICENSE`，并增加 `Copyright 2026 KunoLu` 的 `NOTICE`，确保公开安装和本地同步后的独立 Skill 保留许可与版权声明。
- 为 `templates/skills/` 下除已单独许可的 `web-ui-autotest-generator` 和第三方衍生的 `seo-geo` 外的其余 bundled Skill 原创内容增加相同 `LICENSE` 和 `NOTICE`；既有第三方来源说明继续保留，不修改任何 `SKILL.md`、脚本、references、assets 或运行逻辑。
- 完成 bundled `seo-geo` 的来源和许可证核验：增加 Apache License 2.0 `LICENSE`，在 `NOTICE` 中固定 ReScienceLab/opc-skills 上游 source、revision 和本地修改范围，并将 `Copyright 2026 KunoLu` 严格限定于 frontmatter 适配、尾随空白清理和 bundled packaging。

### 变更

- 将 bundled `lessons-record`、`project-validation`、`trellis-channel` 和 `trellis-workflow` Skill 的中文说明逐句等义翻译为英文，保持触发条件、执行顺序、门禁、状态值和安全边界不变。
- 将 `web-ui-autotest-generator` 从受管 external stable 镜像迁移为 `sbtd-workflow-onboard/templates/skills/` 下的 bundled Skill，保持原 `SKILL.md`、脚本、references、assets 和功能逻辑不变；从 external stable manifest / notice 移除对应条目，将 bundled 目录的许可统一为 Apache License 2.0，将原中文 `README.md` 原样改名为 `README.zh-CN.md`，并新增逐句等义的英文 `README.md`。
- 为 bundled `web-ui-autotest-generator` 的 frontmatter `description` 补充与现有中文语义对应的英文触发词，覆盖 frontend / backend、pages、routes、components、APIs、user flows、Playwright UI tests、Chinese test reports 和跨页面覆盖检查。
- 修正长任务中 `caveman auto-lite` 达到阈值后仍可能不启动的问题：由全局 AGENTS 模板统一自动生命周期，增加单调 eligibility latch、消息级保护区、仅新主要目标重置、配置缺失默认 auto 和 compaction / handoff 状态连续性；external `caveman` Skill 保持上游原样。
- 强制每次完整执行 `grill-with-docs` 后立即调用 bundled `book-ddd-distilled-modeling` 做独立边界二次审核；`grill-with-docs` 内嵌的 external `domain-modeling` dependency 不再视为替代，必须向用户输出 `DDD Boundary Review`，未达到 `confirmed` 不得进入需求确认、PRD、design、Trellis task 或实现。
- 为其余 4 个 bundled `book-*` Skill 增加客观开发触发门禁和完整状态机：`Book Gate Plan` 使用 planned / running / passed / blocked / not-required，legacy 与 refactoring 通过受控 safety-seam-only 回路避免死锁，DDIA 只强制 shared / persistent / cross-request / cross-process cache，Release Readiness 位于所有适用测试工具 Gate 和项目验证之后并区分必需验证与可选检查；未命中场景仍保持按需调用。

## v1.0.1（2026-07-18）

### 修复

- 删除仓库根目录下指向不存在 `.agents/skills/sbtd-workflow-onboard` 的 `.claude/skills/sbtd-workflow-onboard` broken symlink，避免 Claude Code 误判项目级 Skill 来源。
- 保持根 `sbtd-workflow-onboard/` 为唯一公开 discovery entrypoint，不再提交由本地 Agent 安装器生成的项目级 alias。

### 文档

- README 同时提供默认分支最新内容和指定 Git tag 两种安装命令。
- 明确 `skills@latest` 固定的是 npm 上的 Skills CLI 版本通道；未带 `#ref` 的仓库 URL 安装默认分支 `main` 的最新 commit，而不是最新 tag。
- 明确正式 tag 保持不可变，修复通过新的 patch tag 发布。
- 新增根 `CHANGELOG.md`，从 `v1.0.0` 起按 tag、中文、倒序维护发布记录。

### 验证

- 增加仓库契约检查，禁止重新提交 `.claude` 项目级 Skill alias。
- 增加 README 最新版本 / 指定 tag 安装示例和 CHANGELOG 顺序检查。

## v1.0.0（2026-07-18）

### 新增

- 将 Onboard 能力收敛为根目录自包含 `sbtd-workflow-onboard` Skill，提供唯一 `SKILL.md` discovery entrypoint。
- 新增机器可读 `catalog.json`、Draft 2020-12 Schema、bundled Skill 模板和带来源校验的 external Skill stable fallback。
- 支持一个或多个项目路径的 `plan`、`init`、`reset` 和 project-only `init-projects` 流程。
- 支持通过官方 `npx skills add --global` bootstrap Onboard Skill，再由 Agent 执行完整初始化或重置。
- 纳入 Knowledge Base P1.1、Playwright / Maestro 验证契约、分层 lessons 和 SEO/GEO 等可选专项 Skill。

### 变更

- 仓库由旧 `kuno-workflow-onboard-skills` 布局迁移到 `sbtd-workflow-onboard`，canonical Skill 安装成功后按身份校验删除 legacy Onboard 目录。
- external Skill canonical 名称迁移为 `to-spec` / `to-tickets`，旧 `to-prd` / `to-issues` 仅作为迁移输入并在成功安装后删除。
- 根 `AGENTS.md` 和 `ENTRYPOINT.md` 保持 Git 追踪，分别作为仓库规则和版本监控的可恢复基线。
- 普通仓库维护、显式 `sync` 和手动 `update` 职责分离；只有 `sync` 按差异发布版本化 prompt 到 Orca live automation。
- 扩展 README 的全局安装、多项目、project-only、回滚、安全边界和响应式 HTML 说明。
- 将 Knowledge Base 集成方案移动到 `docs/prd/`，并归档 Codex `v0.144.5` 更新报告。

### 验证

- 增加 catalog、安装事务、legacy migration、多项目初始化、Agent CLI、Knowledge Base 和仓库工作流契约测试。
- 发布前全量 Python 测试共 88 项通过，并完成 README HTML 桌面端和移动端 Chromium smoke 验证。
