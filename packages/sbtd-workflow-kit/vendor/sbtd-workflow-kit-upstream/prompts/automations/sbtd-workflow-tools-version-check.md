你在 ~/github/640-skills 中执行工具版本更新检查。

仓库定位：

- 本仓库是 Coding Agent 配置文件与 Skill 的摘录 / 同步源，不是真实业务项目。
- 本文件是 Orca 自动化 `SBTD Workflow Tools Version Check` 的版本化 prompt 源；每次仓库代码或工作流规则改动后都要评估是否需要同步调整。只有用户明确执行 `sync` / `同步` 时，才比较本文件与 live automation 并按差异同步；`update` / `更新` 与二者无关。
- 如发现路径匹配不上情况，以当前仓库文件、本 prompt 和根 `AGENTS.md` 为准。

严格遵守：

- 先读取项目根目录的 `docs/lessons.md`；如果当前任务命中 repository-workflow、validation-scripts 或其他 topic 路由，再读取对应 `docs/lessons/topics/*.md`。
- 读取项目根目录的 `AGENTS.md` 和 `ENTRYPOINT.md`。
- Agent 规则文件路径以 `AGENTS.md` 中“Agent 规则文件路径”章节为准。
- 当前可读取、评估或验证的本仓库版本化规则、文档、安装器、模板、Skill 或契约测试源路径仅限：`AGENTS.md`、`ENTRYPOINT.md`、`UPDATE.md`、`CHANGELOG.md`、`README.md`、`README.html`、`install.sh`、`install.ps1`、`sbtd-workflow-onboard/catalog.json`、`sbtd-workflow-onboard/catalog.schema.json`、`sbtd-workflow-onboard/SKILL.md`、`sbtd-workflow-onboard/REFERENCE.md`、`sbtd-workflow-onboard/scripts/onboard.py`、`sbtd-workflow-onboard/templates/agents/AGENTS.global.md`、`sbtd-workflow-onboard/templates/agents/AGENTS.project.md`、`sbtd-workflow-onboard/templates/project/.gitignore`、`sbtd-workflow-onboard/templates/skills/**`、`tests/**`、`prompts/automations/sbtd-workflow-tools-version-check.md`。
- 无人值守自动化仅可创建或修改：`UPDATE.md`；以及在第 11、12 步的证据和范围满足时可修改的 `AGENTS.md`、`CHANGELOG.md`、`README.md`、`README.html`、`prompts/automations/sbtd-workflow-tools-version-check.md`、`sbtd-workflow-onboard/SKILL.md`、`sbtd-workflow-onboard/REFERENCE.md`、`sbtd-workflow-onboard/templates/agents/**`、`sbtd-workflow-onboard/templates/skills/**`。其余允许路径只能读取、评估或验证。
- `install.sh`、`install.ps1`、`sbtd-workflow-onboard/scripts/onboard.py`、`sbtd-workflow-onboard/catalog.json`、`sbtd-workflow-onboard/catalog.schema.json`、`sbtd-workflow-onboard/templates/project/.gitignore` 与 `tests/**` 只能读取、评估或验证，不得由无人值守自动化修改。
- 不要读取或修改已删除的旧路径：`kuno-workflow-onboard-skills/`、根目录旧 `AGENTS.global.md`、根目录旧 `AGENTS.project.md`、顶层 `agents/`、顶层 `skills/`。
- `UPDATE.md` 的正文内容必须使用中文。
- 不要修改 `ENTRYPOINT.md` 中任何工具的当前版本号；`ENTRYPOINT.md` 只作为版本比对基线读取。
- 只有用户在交互中手动输入“更新”或“update”时，才允许把 `UPDATE.md` 中的最新版本写回 `ENTRYPOINT.md`；定时自动化任务绝不执行这个写回动作。
- 不要执行 `git commit`、`git push`、`gh repo create` 或任何远程写入动作。
- 不要自行提交或推送变更；自动化完成后保留工作区 diff，等待用户手动确认。
- 无人值守自动化不得通过提问请求 `update` / `sync` / commit / push 授权，也不得把未回答的确认当作继续依据；这些动作只有用户在交互会话中明确要求时才属于独立工作流，定时任务本身不得升级权限。
- 执行 shell 命令时优先使用 `rtk` 前缀；`rtk` 不可用时再回退原生命令。若 `rtk` 出现包装器参数解析异常，必须用原生命令复验同一事实。
- 如果 `.trellis/` 不存在或 `.trellis/workflow.md` 不存在，不要假装 Trellis 阶段已执行；记录为跳过原因。

任务流程：

1. 读取 `ENTRYPOINT.md`，并优先解析“## 0. 版本监控配置”表格中“是否启用监控”为“是”的工具。
2. 每个工具至少读取这些字段：工具、GitHub 仓库、当前使用版本、版本通道策略、备注。
3. 将 `ENTRYPOINT.md` 中的“当前使用版本”作为该工具本次比对的固定起始版本；即使 `UPDATE.md` 里已有旧的更新区间，也不要把起始版本推进到 `UPDATE.md` 里的目标版本。
4. 对每个启用工具，从对应 GitHub 仓库获取 releases 或 tags，找出应比较的最新版本。
5. 版本规范化要求：
  - `v` / `V` 前缀大小写不影响比较。
  - 当前版本是 stable 且策略为 stable-only 时，只比较更新的 stable 版本。
  - 当前版本是 prerelease 且策略为 same-prerelease-channel 时，只比较同一 prerelease 通道内的新版本，例如 `v0.6.0-beta.18` 只比较 `v0.6.0-beta.x` 中更高 beta 序号，不主动跳到 stable。
  - 如果跨越多个版本，汇总从 `ENTRYPOINT.md` 当前版本到最新版本之间所有 release notes。
6. 如果 GitHub release body 缺失、为空或明显不足以判断变更，不要直接写成“无可追溯变更”；必须继续从官方 docs / changelog、GitHub compare、具体 commit diff 和变更文件列表、migration / upgrade manifest、npm metadata / tarball / 发布文件结构等来源补充证据，并在 `UPDATE.md` 中说明哪些来源有依据、哪些来源缺失。
6.1. 对 Trellis、Codex dispatch、sub-agent、hook 或 Channel 的变更，必须额外核验目标 stable tag 的有效配置、workflow 模板和 migration manifest；区分功能首次引入、默认值变化与既有能力的 bug fix。`.trellis/**` 是共享 workflow gate，不是平台身份；若结论涉及平台调度，还必须读取对应生成的平台集成与 agent / worker 定义，并区分“已配置平台目录”与“当前 host”。`.codex/**` 与 `.omp/**` 可共存；静态 tag 工件不得选择运行时。不得把 Codex `codex.dispatch_mode`、Inline 或其 fallback 泛化到 OMP，不得以未发布 `main` 分支文本覆盖 tagged stable 版本结论。若这些依据无法完整取得，必须在 `UPDATE.md` 中逐项说明缺失依据和剩余不确定性，不得以 release body 充分为由跳过；缺少任一项时不得形成或更新平台调度规则。
7. 创建或刷新 `UPDATE.md`，结构必须为：
 `# UPDATE`
 `## <工具名> <起始版本> -> <目标版本>`
 其中起始版本必须等于 `ENTRYPOINT.md` 中当前版本，目标版本必须等于最新检测并完成比对分析的版本；然后用中文写入 release 汇总、破坏性变更、迁移说明、对 agent harness workflow 的影响分析。
8. 如果 `UPDATE.md` 中已有同一工具、同一起始版本的旧区间，例如 `## Codex v0.1.0 -> v0.1.5`，而本次最新版本为 `v0.1.6`，则把该二级标题更新为 `## Codex v0.1.0 -> v0.1.6`，并用中文替换该段落正文，不新增重复区间。
9. 如果 `ENTRYPOINT.md` 中的工具当前版本一直没有被用户手动更新，则无论自动化执行多少次，该工具在 `UPDATE.md` 中的区间起点都必须保持为 `ENTRYPOINT.md` 中的当前版本，终点为最新检测并完成比对分析的版本。
10. 评估是否需要修改本仓库规则时，不要只检查是否存在与上游同名的模板或配置文件；还必须用 release 中出现的关键概念、命令、配置项和兼容性关键词扫描以下本地文件，并在 `UPDATE.md` 的影响分析中说明命中结果和处理决定：
  - `AGENTS.md`
  - `prompts/automations/sbtd-workflow-tools-version-check.md`
  - `sbtd-workflow-onboard/catalog.json`
  - `sbtd-workflow-onboard/catalog.schema.json`
  - `sbtd-workflow-onboard/SKILL.md`
  - `sbtd-workflow-onboard/REFERENCE.md`
  - `sbtd-workflow-onboard/scripts/onboard.py`
  - `sbtd-workflow-onboard/templates/agents/AGENTS.global.md`
  - `sbtd-workflow-onboard/templates/agents/AGENTS.project.md`
  - `sbtd-workflow-onboard/templates/skills/**`
  - `install.sh`
  - `install.ps1`
  - `sbtd-workflow-onboard/templates/project/.gitignore`
  - `tests/**`
11. 根据 `UPDATE.md` 中可追溯到 release notes 或其他官方 tagged evidence 的内容，最小化修改 `AGENTS.md` 或 `sbtd-workflow-onboard/` 下相关模板 / Skill 文件：
  - 只修改 workflow、命令、配置、兼容性或工具使用规则相关内容。
  - 不做无关重写。
  - 每处修改都应能追溯到 release notes 或记录在 `UPDATE.md` 中的其他官方 tagged evidence。
  - 规则更新必须沉淀为长期通用规则，不要在长期执行规则里写入具体版本号、一次性版本区间或临时 release 叙述；版本号和依据保留在 `UPDATE.md` 的版本分析段落中。
  - 上游 external Skill 删除或重命名 canonical 名称时，必须在影响分析中确认 catalog、stable manifest、安装器 canonical / legacy 映射、全局与项目模板、README、CHANGELOG 和契约测试一致；正常 `init` / `reset` 必须先完整验证 replacement canonical，再删除所有已知 predecessor 目录。不得保留 predecessor alias、双 canonical 或未经身份确认的删除路径。
  - 自动化专用规则只能写入本仓库根 `AGENTS.md`、本 prompt 或其他自动化说明，不要污染可复用的全局 / 项目 AGENTS 模板。
  - 不要因为发现新版本就修改 `ENTRYPOINT.md` 的版本字段。
12. 如果仓库代码、`sbtd-workflow-onboard/`、工作流规则、安装 / reset 行为或用户可见路径有更新，必须在同一轮评估 `CHANGELOG.md`、`README.md`、`README.html` 和本 prompt 是否需要同步调整；新增用户可见能力、安装方式、兼容性边界、迁移、修复或发布前验证变化时更新 `CHANGELOG.md`，其他入口只更新实际受影响的版本化文件，无需修改时在最终输出说明原因。版本检查自动化不直接读取或写入 Orca live automation。
13. 运行验证：
  - `git status --short`
  - 检查 `ENTRYPOINT.md`、`UPDATE.md`、`AGENTS.md`、`CHANGELOG.md`、`README.md`、`README.html`、`install.sh`、`install.ps1`、`prompts/automations/sbtd-workflow-tools-version-check.md`、`sbtd-workflow-onboard/catalog.json`、`sbtd-workflow-onboard/catalog.schema.json`、`sbtd-workflow-onboard/SKILL.md`、`sbtd-workflow-onboard/REFERENCE.md`、`sbtd-workflow-onboard/scripts/onboard.py`、`sbtd-workflow-onboard/templates/agents/AGENTS.global.md`、`sbtd-workflow-onboard/templates/agents/AGENTS.project.md`、`sbtd-workflow-onboard/templates/project/.gitignore`、`sbtd-workflow-onboard/templates/skills/**/SKILL.md`、`tests/**` 的结构是否可读。
  - 使用 Draft 2020-12 校验 `sbtd-workflow-onboard/catalog.json` 符合 `catalog.schema.json`，目录 id 唯一；每个 bundled Skill local source 必须位于 Onboard Skill 根目录内且实际存在，每个 external Skill source 必须包含合法的上游 repo、受限相对 subpath 和 canonical alias。验证 External Skill 默认 `auto` 与显式 `stable` 均只使用受管 stable set 且不访问网络，只有显式 `upstream` 才直接获取当前上游并在失败时直接报错。对任何 external canonical rename，隔离 global Skill 目录中同时预置 predecessor 与更早 legacy alias，执行 reset 等价的 stable install / migration，断言 replacement `SKILL.md` 存在、每个 predecessor 均不存在，且 JSON 结果记录 `removed`；若 canonical 已存在，也必须验证 legacy-only cleanup 同样删除 predecessor。同步核对 `AGENTS.md` 的“本地同步规则”表：仓库管理且要求全局同步的 bundled Skill 必须具有正确的 source / target 映射，包含 `web-ui-autotest-generator`，同时保持 `AGENTS.project.md` 不在普通 sync 范围内。
  - 验证能从 `ENTRYPOINT.md` 正确解析受监控工具表。
  - 验证 `UPDATE.md` 使用中文，且各工具区间起点等于 `ENTRYPOINT.md` 中该工具当前版本。
  - 验证 `ENTRYPOINT.md` 没有因为定时自动化而更新工具版本号。
  - 验证根 `.gitignore` 内容严格为四行：`.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/`。
  - 验证 project-only 安装契约：付费 React Bits Skill 固定落在 `.agents/skills/react-bits-pro/SKILL.md` 且使用覆盖语义；项目 `.gitignore` 按精确非空行只追加模板缺失项，重复执行不产生重复行；项目 `AGENTS.md`、`CLAUDE.md`、`.agents/**` 与 Trellis 生成的 Agent 集成保持可追踪，只忽略明确的本地运行态和机器本地设置。
14. 最终输出必须说明：发现的版本区间、修改的文件、`CHANGELOG.md` / `README.md` / `README.html` / 本 prompt 的维护判断、验证命令和结果、跳过项及原因、剩余风险、`rtk` 使用状态。再次强调：不要 commit，不要 push，不要把最新版本写回 `ENTRYPOINT.md`。
