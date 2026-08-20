# AI Tools 项目规则

本仓库是 Codex 配置文件与 Skill 的摘录/同步源，不代表一个真实业务项目结构。本文件只保留本配置摘录仓库自身直接生效的补充规则；可复用的全局规则、项目级规则和全局 Skill 模板集中维护在 `sbtd-workflow-onboard/`。

## Agent 规则文件路径

本配置集维护的 agent 规则文件路径如下：

- 根目录 `AGENTS.md`：保存本配置摘录仓库直接生效的补充规则，包括版本检查自动化和 `更新` / `update` 指令；该文件必须由 Git 追踪，保证新 clone 可直接恢复仓库规则。
- 根目录 `ENTRYPOINT.md`：保存版本监控配置和工作流总入口；该文件必须由 Git 追踪，作为版本检查与 `更新` / `update` 的可恢复基线。
- `sbtd-workflow-onboard/templates/agents/AGENTS.global.md`：保存迁移后的全局规则文档。
- `sbtd-workflow-onboard/templates/agents/AGENTS.project.md`：保存迁移后的项目规则文档。
- `sbtd-workflow-onboard/templates/skills/**`：保存迁移后的全局 Skill 模板及其 references / scripts / assets。
- `sbtd-workflow-onboard/SKILL.md`、`sbtd-workflow-onboard/REFERENCE.md`、`sbtd-workflow-onboard/scripts/onboard.py`：保存 onboard Skill 自身的说明和安装 / 重置自动化。
- `prompts/automations/sbtd-workflow-tools-version-check.md`：保存 Orca `SBTD Workflow Tools Version Check` 的版本化 prompt 源；每次仓库代码或工作流规则改动后都要评估是否需要同步调整。

每日版本检查自动化如需读取、评估或修改 agent 规则，只能使用上述路径和 `prompts/automations/sbtd-workflow-tools-version-check.md`。不要再读取或修改已删除的旧路径 `agents/`、`skills/`、根目录旧路径 `AGENTS.global.md` 和 `AGENTS.project.md`。


## Onboard Skill 公开安装边界

- `sbtd-workflow-onboard/` 必须保持为官方 `skills` CLI 可递归发现和整目录安装的自包含 Skill；根 `SKILL.md` 是唯一 discovery entrypoint，不要把 `templates/skills/**` 提升到仓库根，也不要新增重复 bootstrap Skill。
- 用户可用 `npx skills add` 把 Onboard Skill bootstrap 到用户级全局目录；该动作只安装 Onboard Skill，不等于执行 `scripts/onboard.py`，不得声称已安装其余 Skills、Trellis、GitNexus、AGENTS 或项目配置。
- Onboard 运行时的全局 Skill 目录优先级固定为：显式 `--global-skills-dir`、`$AGENT_SKILLS_DIR`、已安装 Onboard Skill 的受信父目录、既有平台默认目录；JSON `plan` / `check` 必须暴露实际路径来源。
- 本公开安装方式不改变下文仓库维护用 `同步` / `sync` gate；普通修改仍不得自动写入本机生效路径。

## Lessons 读取规则

本仓库的长期经验记录采用 `lessons-record` 的分层结构，但保留 `docs/lessons.md` 作为每次操作前的必读短入口：

- `docs/lessons.md`：必读短入口，只保存读取协议、topic 路由和高频摘要，不保存完整历史库。
- `docs/lessons/index.md`：完整索引，按 `id`、tags、适用场景和详情路径维护。
- `docs/lessons/topics/<topic>.md`：完整 lesson 详情。
- `docs/lessons/archive/YYYY-QN.md`：低频历史归档，默认不读。

每次执行本仓库操作前，必须先读取 `docs/lessons.md`，理解其中与当前任务相关的高频规则后再继续。
如果当前任务、错误信息、工具名或 tags 命中 `docs/lessons.md` 的 topic 路由或 `docs/lessons/index.md`，再读取对应 topic / archive；不要默认全文读取 `docs/lessons/topics/**`。
如果 `docs/lessons.md` 不存在或不可读取，不要假装已读取；必须在最终输出中说明跳过原因。

写入新 lesson 时，必须将完整记录写入对应 `docs/lessons/topics/<topic>.md` 并同步更新 `docs/lessons/index.md`；只有跨任务高频、缺失会反复导致错误的摘要才同步到 `docs/lessons.md`。不要把完整 lesson 历史重新堆回 `docs/lessons.md`。

## 本仓库 BDD 产物边界

本仓库是配置摘录和模板源，不是真实业务项目；不要在本仓库内生成 `.feature` 文件。
如需描述 BDD / Gherkin 规则，只能写入相关 AGENTS 模板、Skill、README 或对话说明，不要落地为本仓库的持久 `.feature` 产物。

## README 与自动化 Prompt 同步规则

后续每次仓库代码、`sbtd-workflow-onboard/`、工作流规则、安装 / reset 行为或用户可见路径发生改动，都必须在同一轮评估以下三个版本化文档入口是否需要同步调整：

- 根目录 `README.md`。
- 根目录 `README.html`。
- `prompts/automations/sbtd-workflow-tools-version-check.md`。

如果改动影响以下任一内容，必须同步更新实际受影响的 README 或 automation prompt，不得漏掉需要变化的入口；不受影响的文件不做无意义改写：

- 工作流主线、工具职责边界或最终验证工具栈。
- SDD、BDD、TDD、DDD 或 SBTD 的定义、触发条件、产物位置或协作顺序。
- Chrome DevTools MCP、Playwright CLI、Playwright MCP、Maestro CLI、Maestro MCP、`web-ui-autotest-generator` 或 `seo-geo` 的检测、安装、fallback、报告状态或使用时机。
- `sbtd-workflow-onboard/scripts/onboard.py` 的 init、reset、安装或检查行为。
- 模板 `.gitignore`、同步路径、AGENTS 模板路径、Skill 模板路径、用户可见文档入口、版本检查范围或验证契约。

普通代码或文档修改只维护仓库内的版本化 prompt，不直接读写 Orca live automation。只有用户明确执行 `sync` / `同步` 时，才在当前 Orca runtime 中按精确名称 `SBTD Workflow Tools Version Check` 重新定位 automation id，比较版本化 prompt 与 live prompt 的完整内容；仅在存在差异时把仓库版本同步到 live automation，并验证 prompt、enabled、schedule、timezone、workspace mode 和 workspace path。不得复用历史 automation id。

`update` / `更新` 只负责 `ENTRYPOINT.md` 版本写回和 `UPDATE.md` 归档，与版本化 prompt 和 Orca live automation 无关；不得在 update 流程中检查、修改或同步它们。

普通修改的最终输出必须分别说明 `README.md`、`README.html` 和版本化 automation prompt 的维护判断。`sync` / `同步` 的最终输出还必须说明 live automation 是内容一致无需写入、已同步成功，还是同步失败。判断任一版本化文档无需修改时，必须说明跳过原因。

## CHANGELOG 维护规则

- 根目录 `CHANGELOG.md` 是从 `v1.0.0` 起的发布变更事实源，必须由 Git 追踪并使用中文正文。
- 每个 Git tag 使用一个二级标题章节，按版本从新到旧排列；正在准备的下一个版本使用 `## <tag>（未发布）`，创建并推送 tag 后补充发布日期。
- 当前准备发布的改动必须写入最上方未发布章节，并按“修复 / 新增 / 变更 / 文档 / 验证”等实际类别组织；不要把一次性过程日志写成 release note。
- 已发布 tag 的章节视为历史记录，不因后续修复而改写；修复通过新的 patch / minor / major tag 章节追加。
- 每次新增用户可见能力、安装方式、兼容性边界、迁移、修复或发布前验证变化时，必须评估并更新 `CHANGELOG.md`；无需更新时在最终输出说明原因。

## 本地同步规则

普通修改任务只更新本配置摘录仓库内的源文件，不要立即同步到本地 PC 的实际生效路径。

只有当用户主动输入 `同步` 或 `sync` 时，才执行本节同步流程。

同步触发后，只同步以下全局规则和全局 Skill：

| 源文件 | 本地目标路径 |
|---|---|
| `sbtd-workflow-onboard/templates/agents/AGENTS.global.md` | `/Users/lusonglin/.codex/AGENTS.md` |
| `sbtd-workflow-onboard/` | `/Users/lusonglin/.agent/skills/sbtd-workflow-onboard/` |
| `sbtd-workflow-onboard/templates/skills/trellis-workflow/` | `/Users/lusonglin/.agent/skills/trellis-workflow/` |
| `sbtd-workflow-onboard/templates/skills/trellis-channel/` | `/Users/lusonglin/.agent/skills/trellis-channel/` |
| `sbtd-workflow-onboard/templates/skills/project-validation/` | `/Users/lusonglin/.agent/skills/project-validation/` |
| `sbtd-workflow-onboard/templates/skills/web-ui-autotest-generator/` | `/Users/lusonglin/.agent/skills/web-ui-autotest-generator/` |
| `sbtd-workflow-onboard/templates/skills/gherkin-bdd/` | `/Users/lusonglin/.agent/skills/gherkin-bdd/` |
| `sbtd-workflow-onboard/templates/skills/knowledge-base-integration/` | `/Users/lusonglin/.agent/skills/knowledge-base-integration/` |
| `sbtd-workflow-onboard/templates/skills/maestro-mobile-e2e/` | `/Users/lusonglin/.agent/skills/maestro-mobile-e2e/` |
| `sbtd-workflow-onboard/templates/skills/lessons-record/` | `/Users/lusonglin/.agent/skills/lessons-record/` |
| `sbtd-workflow-onboard/templates/skills/book-refactoring-pass/` | `/Users/lusonglin/.agent/skills/book-refactoring-pass/` |
| `sbtd-workflow-onboard/templates/skills/book-legacy-change-safety/` | `/Users/lusonglin/.agent/skills/book-legacy-change-safety/` |
| `sbtd-workflow-onboard/templates/skills/book-ddd-distilled-modeling/` | `/Users/lusonglin/.agent/skills/book-ddd-distilled-modeling/` |
| `sbtd-workflow-onboard/templates/skills/book-ddia-data-design/` | `/Users/lusonglin/.agent/skills/book-ddia-data-design/` |
| `sbtd-workflow-onboard/templates/skills/book-release-readiness/` | `/Users/lusonglin/.agent/skills/book-release-readiness/` |
| `sbtd-workflow-onboard/templates/skills/seo-geo/` | `/Users/lusonglin/.agent/skills/seo-geo/` |

同步要求：

1. 先确认 Orca runtime 可用，并通过 `orca automations list --json` 按精确名称定位 `SBTD Workflow Tools Version Check`；任一前置条件失败时，在修改任何同步目标前停止。
2. 读取源文件 / 目录，确认路径正确。
3. 文件目标按文件复制；Skill 目录目标必须复制整个目录，包括 `SKILL.md`、`references/`、`scripts/`、`assets/` 等子内容。
4. `sbtd-workflow-onboard/` 成功复制并校验后，只有旧路径 `/Users/lusonglin/.agent/skills/kuno-workflow-onboard-skills/` 是目录，且其 `SKILL.md` frontmatter 的 `name` 仍为 `kuno-workflow-onboard-skills` 时才删除；同名文件、无效 / 不相关目录或身份不匹配必须停止 rename migration、保留原内容并报告冲突。旧目录只作为迁移输入，不保留 alias 或兼容副本。
5. 同步完成后，在本机实际使用的 external Skill 根目录 `/Users/lusonglin/.agent/skills` 上执行 mattpocock legacy migration：运行 `sbtd-workflow-onboard/scripts/onboard.py migrate-external-skills --scope global --source auto --global-skills-dir /Users/lusonglin/.agent/skills --yes`，只处理身份校验通过的受管旧目录；`diagnose`、`write-a-skill`、`writing-great-skills`、`to-prd`、`to-issues` 和已删除的 `zoom-out` 会被移除，前五者会先安装并提交 `diagnosing-bugs`、`writing-for-agents`、`to-spec`、`to-tickets`。
6. 文件使用 `cmp -s` 或等价方式确认一致；目录使用 `diff -qr`、递归 checksum 或等价方式确认源目录与目标目录一致；rename migration 使用旧 Onboard 目录不存在且 `sbtd-workflow-onboard/SKILL.md` 存在作为成功校验，或使用旧路径未变且冲突已报告作为阻断校验；external legacy migration 使用 `test ! -e` 确认每个受管旧目录不存在，并检查 `diagnosing-bugs/SKILL.md`、`writing-for-agents/SKILL.md`、`to-spec/SKILL.md`、`to-tickets/SKILL.md` 存在。
7. 比较 `prompts/automations/sbtd-workflow-tools-version-check.md` 与刚定位的 live automation prompt 完整内容；仅在存在差异时同步仓库版本，保留既有 enabled、schedule、timezone、workspace mode 和 workspace path，并在同步后复验一致。
8. 在最终输出中说明已同步的文件、Onboard rename migration、external legacy migration、live automation prompt 的比较 / 同步状态和全部校验结果。

不要同步：

- `sbtd-workflow-onboard/templates/agents/AGENTS.project.md`

`sbtd-workflow-onboard/templates/agents/AGENTS.project.md` 是用于复制到真实项目仓库根目录 `AGENTS.md` 的项目级模板，只在具体项目需要时由用户手动落地、通过 `sbtd-workflow-onboard` 安装，或由用户明确要求同步。
当 `sbtd-workflow-onboard/` 作为 Skill 目录整体同步到 `/Users/lusonglin/.agent/skills/sbtd-workflow-onboard/` 时，其中携带的 `templates/agents/AGENTS.project.md` 只作为该 Skill 的模板资产保留，不视为把项目级模板同步到任何真实项目。

### 同步指令

当用户输入 `同步` 或 `sync` 时：

1. 执行 Orca automation preflight。
2. 执行上面的本地同步流程。
3. 在本机 `/Users/lusonglin/.agent/skills/` 下执行第 5 项的完整 mattpocock legacy migration：使用 synced onboard Skill 的 `migrate-external-skills --scope global --source auto --global-skills-dir /Users/lusonglin/.agent/skills --yes`，而不是只处理 `to-prd` / `to-issues` 的 `install-external-skills` 调用。
4. 比较版本化 prompt 与 Orca `SBTD Workflow Tools Version Check` 的完整内容；仅在存在差异时同步仓库版本，验证完整内容和调度元数据，并在最终输出中报告“一致无需写入”或同步成功 / 失败。
5. 不修改 `ENTRYPOINT.md` 版本号。
6. 不归档 `UPDATE.md`。

mattpocock/skills 默认从 `sbtd-workflow-onboard/assets/external-skills/stable/` 中带精确上游 commit、checksum 和许可证的原样 stable 镜像安装；只有用户明确选择 `--source upstream` 做上游评估或升级验证时才直接获取上游。该镜像不是 fork，不得手工改写，只能通过 stable promotion 流程整组更新。除该受管 stable 镜像外，不要在本仓库内另行安装、fork 或改写这些官方 Skill。

## 版本检查自动化

版本检查自动化必须遵守：

1. `UPDATE.md` 的正文内容必须使用中文。
2. 自动化只读取 `ENTRYPOINT.md` 中的当前版本作为比对基线；不要修改 `ENTRYPOINT.md` 中任何工具的当前版本号。
3. 对同一工具多次执行自动化时，`UPDATE.md` 中的版本区间必须始终保持为：`ENTRYPOINT.md` 中该工具当前版本号 -> 最新检测并完成比对分析的版本号。
4. 如果同一工具、同一起始版本已有更新区间，后续检测到更高版本时，只更新该段二级标题的目标版本号和段落内容，不新增重复区间。
5. 如果 GitHub release body 缺失、为空或明显不足以判断变更，不要直接写成“无可追溯变更”；必须继续从以下维度补充获取版本更新信息，并在 `UPDATE.md` 中说明哪些来源有依据、哪些来源缺失：
   - 官方 docs / changelog 页面或文档仓库对应版本条目。
   - GitHub compare 区间。
   - 具体 commit diff 和变更文件列表。
   - migration manifest、upgrade manifest 或等价迁移元数据。
   - npm 包 metadata、tarball 内容、发布文件结构或本地包结构推断。
   - 对 Trellis、Codex dispatch、sub-agent、hook 或 Channel 变更，还必须读取目标 stable tag 的有效配置、workflow 模板和 migration manifest，明确区分功能首次引入、默认值变化与既有能力的 bug fix；不得以未发布 `main` 分支文本覆盖 tagged stable 版本结论。`.trellis/config.yaml`、`.trellis/workflow.md` 和 task artifacts 只定义共享 workflow gate，不标识运行平台；必须由当前 host 与其专属生成资产判定：Codex 使用 `.codex/**`，OMP 使用 `.omp/**`。两者可共存；纯静态审查不得选择其中一个运行时，证据不足时标记 unknown。若这些平台调度证据中任一项不可取得，必须在 `UPDATE.md` 记录缺失项和不确定性，且不得据此形成或更新平台调度规则。更新规则时，Codex 的 `auto` 必须表述为主会话协调、按职责调度 role subagent；Codex Inline 与其非法值的 fail-closed fallback 不适用于 OMP。当前 OMP host 使用其 `.omp/**` extension 与 worker 机制，单个 platform role subagent 不触发 Channel；同一变更职责只允许一个写入执行者，用户请求的独立只读复核可并行进行。
6. 评估是否需要修改本仓库规则时，不要只检查是否存在与上游同名的模板或配置文件；还必须用 release 中出现的关键概念、命令、配置项和兼容性关键词扫描以下本地文件，并在 `UPDATE.md` 的影响分析中说明命中结果和处理决定：
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
7. 如果 release 改动影响某个工具的使用边界、命令建议、配置禁用项、兼容性风险或迁移步骤，即使本仓库没有对应模板文件，也要最小化更新相关 AGENTS 或 Skill 规则。
8. 由 release 触发的 AGENTS 或 Skill 规则更新必须沉淀为长期通用规则，不要在长期执行规则里写入具体版本号、一次性版本区间或临时 release 叙述；版本号和依据保留在 `UPDATE.md` 的版本分析段落中。只有当规则本身必须表达明确兼容边界时，才允许写最低/最高版本要求。
9. 除非用户手动输入 `更新` 或 `update`，否则不要把 `UPDATE.md` 中的最新版本写回 `ENTRYPOINT.md`。

## 更新指令

当用户输入 `更新` 或 `update` 时：

1. 读取 `docs/lessons.md`，并按命中情况读取 `docs/lessons/index.md` 或相关 topic，再继续执行更新流程。
2. 检查项目根目录 `archive/` 下已有的 `UPDATED-yyyy-mm-dd-<正整数序号>.md` 文件：
   - 以文件名中的 `yyyy-mm-dd` 作为归档日期。
   - 删除归档日期早于当前本地日期 14 天前的文件。
   - 只删除符合上述命名格式的归档文件；格式不匹配的文件不要删除，并在最终输出中说明。
3. 读取项目根目录下的 `UPDATE.md`。
4. 以 `ENTRYPOINT.md` 的 `## 0. 版本监控配置` 作为主数据源，将 `UPDATE.md` 中各工具章节记录的最新版本号写回该表格中对应工具的当前使用版本。
5. 同步更新 `ENTRYPOINT.md` 全文中同一工具对应的当前版本记录，包括“当前版本汇总”和各工具说明章节里的当前版本字段。
6. 不要误改历史对比版本、曾对比版本、release 区间、归档记录或示例文本中的版本号。
7. 将 `UPDATE.md` 重命名为 `UPDATED-yyyy-mm-dd-<正整数序号>.md` 并移动到项目根目录下的 `archive/`；如果目录不存在，则先创建：
   - 使用当前本地日期作为 `yyyy-mm-dd`。
   - 扫描当日已有的合规归档文件，使用其最大正整数序号加一；若没有当日归档文件，则从 `1` 开始。
8. `update` / `更新` 不检查、不修改也不同步 `prompts/automations/sbtd-workflow-tools-version-check.md` 或 Orca `SBTD Workflow Tools Version Check`。
9. 最终输出必须说明版本写回、归档和 README 维护判断。
