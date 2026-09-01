# SBTD Workflow 模板配置说明

本仓库是 Codex / OMP 配置、Agent 规则模板、Skill 模板和 onboard 自动化的摘录/同步源，不代表一个真实业务项目结构。当前主流程收敛为：

```text
Codex / OMP + GitNexus + Trellis + Chrome DevTools MCP + Playwright + Maestro
```

其中 Chrome DevTools MCP 负责 Web 运行时诊断，Playwright CLI 负责 Web 可重复回归，Maestro 负责移动 App E2E 和可选跨端 smoke。bundled `web-ui-autotest-generator` 是可选专项分支，只在需要把 Web UI 回归路径固化为仓库内 Playwright 测试资产时启用；`shadcn` 是 shadcn/ui 项目的可选 external Skill，用于组件、registry、preset 和 CLI 工作流；`seo-geo` 是 bundled 的公开网站、落地页、文档站和营销页 SEO/GEO 搜索可见性检查分支；`maestro-mobile-e2e` 负责把 Mobile / Hybrid BDD 场景固化为仓库内 Maestro flow 资产。API、Web 和 Mobile / Hybrid 测试都以 BDD `.feature` 作为行为 SOT；前后端分仓或链路不完整时，先确认 contract、环境、账号、数据、设备和选择器事实，再决定 full-stack、contract-backed、mock-backed、app-mocked、smoke-only 或 blocked。

Codex plugin / connector、remote plugins、ChatGPT-hosted MCP 和 `tool_search` 属于 Agent 侧工具发现和授权能力，不是项目依赖。模板要求先确认当前会话实际暴露 callable tool，再依赖对应能力；catalog / marketplace / 本地远端版本展示只作为候选信号，session auth、OAuth、cookies 和 tokens 不写入仓库、日志、截图、报告或示例配置。

`rtk` 和 `caveman` 是上下文 / token 效率层，不是验证工具。`rtk` 作用于 shell / terminal 命令输出，普通非报告型命令默认优先作为命令前缀；unit / API / Playwright / Maestro 等报告型测试先评估缓存与文件写入风险。`caveman` 作用于 Agent 回复输出，安装后只表示可用，不会立即进入持久压缩模式。同一主要目标达到 3 次中间状态更新、5 个独立工具结果、长任务 / 上下文压力或重复自动化 / review / 验证轮次中的任一条件时，`autoLiteEligible` 单调锁存为 true；下一条普通重复状态必须进入任务级 `auto-lite`，不再附加主观资格判断。

自动生命周期由全局 AGENTS 规则负责，external `caveman` Skill 只负责手动模式的表达风格、强度和退出。自动模式不会进入 `full`、`ultra` 等更激进等级，也不改变代码、工具、测试、验证和工作流决策。安装 / 权限 / 破坏性操作确认、安全风险、需求与 review gate、长期文档、失败与剩余风险、最终验证报告和最终答复仍保持完整输出；保护区只覆盖当前回复，不清除计数、`autoLiteEligible` 或 `autoLiteActive`，下一条普通重复状态直接恢复且不重复首次提示。

`normal mode`、`stop caveman`、`恢复完整输出`、`不要压缩` 和 `本任务不要自动压缩` 会立即恢复正常输出并在当前任务内禁止自动重入；只有用户明确说 `本任务恢复自动压缩` 或 `重新启用自动压缩` 才清除任务级退出，原有计数和资格继续保留。手动 `/caveman` 不清除任务级或会话级自动退出；`本会话关闭自动压缩` 只能由 `本会话重新启用自动压缩` 清除。

只有用户建立新的主要目标时才重置任务级计数、资格、激活和退出状态；`继续`、`确认`、授权、状态询问、故障恢复和同一目标的补充不得重置。context compaction、历史归档、恢复同一 session 或 handoff 也保持状态。若 runtime 显式配置 `off`，自动和手动模式都禁用；没有配置接口或配置缺失时按 auto 处理。

## 安装及使用说明

### 1. 使用 `npx skills` 全局安装 Onboard Skill

只建议把 `sbtd-workflow-onboard` 安装到用户级全局 Skill 目录，使同一用户下的 Codex 会话都能发现它；不建议安装到单个项目目录，也不要省略 `--global` 后把 bootstrap Skill 变成项目依赖。

```bash
npx --yes skills@latest add \
  KunoLu/640-skills@sbtd-workflow-onboard \
  --global \
  --agent codex \
  --yes \
  --copy
```

其中 `skills@latest` 只表示使用 npm 上最新的 `skills` CLI；`KunoLu/640-skills@sbtd-workflow-onboard` source 没有 `#ref` 时，CLI 会读取仓库默认分支（当前是 `main`）的最新 commit，并不会自动选择最新 tag。需要固定 Skill 内容版本时，使用 `KunoLu/640-skills#<tag>@sbtd-workflow-onboard` 格式，把 Git tag 放在 repository shorthand 与 `@skill` filter 之间：

```bash
npx --yes skills@latest add \
  'KunoLu/640-skills#v1.0.0@sbtd-workflow-onboard' \
  --global \
  --agent codex \
  --yes \
  --copy
```

安装后检查 Codex 的全局 Skill：

```bash
npx skills list --global --agent codex
```

这一步只安装自包含的 `sbtd-workflow-onboard` Skill，不会自动执行 `scripts/onboard.py`，也不会安装 Trellis、GitNexus、其余 bundled / external Skills、写入项目 AGENTS 或初始化项目。私有仓库应使用本机 Git 已可认证的 `git+ssh://` source，不要在命令、仓库、日志或报告中写入凭据。

流程判定图：[npx skills 全局安装 Onboard Skill](docs/assets/npx-skills-global-onboard-install.md)。

### 2. 使用 Onboard Skill 执行 `init`

安装成功后，在 Codex 中明确调用该 Skill，并提供目标平台、一个或多个项目绝对路径和 Trellis 用户名。多个项目路径使用英语逗号 `,` 分隔，例如 `/abs/project-one,/abs/project-two`；每个路径必须已存在且是目录，重复路径会规范化后只处理一次。

```text
请使用 sbtd-workflow-onboard Skill，对 /abs/project-one,/abs/project-two 执行 init 初始化。
目标平台是 codex，Trellis 用户名是 your-name；多个项目路径以英语逗号分隔。
先输出 plan --json，确认计划后执行 init，并逐项目汇总 AGENTS、.gitignore 和 Trellis 状态。
```

Skill 会定位自身的全局安装目录并运行对应脚本。需要手动执行底层 CLI 时，先把实际全局 Skill 路径赋给变量；下面的路径只是示例，应以本机 `npx skills list --global --agent codex` 和 Skill 检测结果为准：

```bash
SBTD_ONBOARD_DIR="$HOME/.agents/skills/sbtd-workflow-onboard"
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" plan \
  --platform codex \
  --projects-root /abs/project-one,/abs/project-two \
  --json
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" init \
  --platform codex \
  --projects-root /abs/project-one,/abs/project-two \
  --trellis-user your-name \
  --yes
```

流程判定图：[Onboard Skill 执行 init](docs/assets/onboard-skill-init.md)。

### 3. 使用 Onboard Skill 执行 `reset`

后续需要更新或重置全局工具、Skills 和一个或多个项目配置时，再次明确调用同一 Skill。`reset` 的多个项目路径同样使用英语逗号分隔：

```text
请使用 sbtd-workflow-onboard Skill，对 /abs/project-one,/abs/project-two 执行 reset。
目标平台是 codex，Trellis 用户名是 your-name；多个项目路径以英语逗号分隔。
先输出 plan --json，保留已检测到的安全配置和 tier，再执行 reset 并逐项目汇总结果。
```

对应的底层命令示例：

```bash
SBTD_ONBOARD_DIR="$HOME/.agents/skills/sbtd-workflow-onboard"
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" plan \
  --platform codex \
  --projects-root /abs/project-one,/abs/project-two \
  --json
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" reset \
  --platform codex \
  --projects-root /abs/project-one,/abs/project-two \
  --trellis-user your-name \
  --yes
```

`reset` 不是无条件删除重装：它仍遵守路径 containment、canonical 身份、事务 rollback、legacy migration、Trellis filesystem-safety guard 和用户确认边界。

流程判定图：[Onboard Skill 执行 reset](docs/assets/onboard-skill-reset.md)。

### 4. 使用 `--init-projects` 只初始化项目

`--init-projects` 是根安装脚本的 project-only 模式：只对指定项目执行项目 AGENTS、模板 `.gitignore`、Trellis init / bootstrap、Playwright 适用性和 React Bits 条件检查，不检测、安装、更新或配置全局 Agent CLI、Trellis / GitNexus、全局 Skills、全局 AGENTS 或 MCP。

`--init-projects` 自身接收一个或多个已存在的项目绝对路径，多个路径同样用英语逗号分隔；它与普通模式的 `--projects-root` / `--action` 互斥。macOS / Linux 示例：

```bash
bash install.sh \
  --platform codex \
  --init-projects /abs/project-one,/abs/project-two \
  --yes
```

Windows PowerShell 示例：

```powershell
pwsh -File .\install.ps1 `
  -Platform codex `
  -InitProjects "C:\work\project-one,C:\work\project-two" `
  -Yes
```

通过已安装 Skill 调用同一 project-only 能力时，可以这样描述：

```text
请使用 sbtd-workflow-onboard Skill，以 init-projects project-only 模式初始化
/abs/project-one,/abs/project-two。多个项目路径以英语逗号分隔；
不要检查或修改任何全局 Agent CLI、工具、Skills、AGENTS 或 MCP。
```

对应底层命令：

```bash
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" init-projects \
  --platform codex \
  --projects-root /abs/project-one,/abs/project-two \
  --trellis-user your-name \
  --yes
```

流程判定图：[--init-projects 只初始化项目](docs/assets/onboard-init-projects.md)。

### 5. 使用安装脚本进行交互式安装

已克隆本仓库时，也可以运行根目录安装脚本进入完整交互式流程：

```bash
bash install.sh
```

```powershell
pwsh -File .\install.ps1
```

交互式流程会先选择普通 `init`、`reset` 或 project-only 初始化。普通 `init` / `reset` 会选择目标 Agent 平台并检查对应 CLI / npm，收集一个或多个以英语逗号分隔的项目绝对路径，按需检查或安装全局 Trellis、GitNexus、bundled / external Skills，写入允许的全局和项目模板并引导 MCP 配置；`init` 对已合法的 bundled / required external Skill 壳跳过，`reset` 无备份覆盖全部 bundled Skills 并从 stable 强制重装全部 required external Skills；project-only 只记录平台上下文并跳过所有全局检测、安装和配置。两种模式都会逐项目处理 `.gitignore`、Trellis init / bootstrap、Playwright 和 React Bits 条件项，最后输出计划、执行状态、阻断原因和验证汇总。Bash 安装器会保留脚本启动时的原始交互输入流，逐项目数据读取不会劫持后续用户选择；输入流提前关闭时会明确报错退出，不会无限重复 `Invalid choice.`。


这里的目标 Agent 平台只选择 CLI 与 MCP adapter，不会选择全局 AGENTS 目标。除非显式传入 `--global-agents-path` / `-GlobalAgentsPath`，正常模式始终把 Codex 全局规则模板写入解析后的 `$CODEX_HOME/AGENTS.md` 或 `~/.codex/AGENTS.md`。若用户主目录已存在 `.omp` 目录（POSIX `~/.omp`，Windows `%USERPROFILE%\.omp`），`init` / `reset` 会把同一模板备份后覆盖写入 `~/.omp/agent/AGENTS.md`；不存在则跳过且不创建 `.omp`。`--global-agents-path` 只覆盖 Codex 目标，不取消 OMP 附加写入。project-only 不写任何全局 AGENTS。

根安装器的 `--yes` / `-Yes` 会对每个 yes/no 提示回答 Yes 并跳过最终执行确认，因此默认会安装 project `AGENTS.md`，也会确认安装流程中出现的可选工具提示。该参数不会猜测无默认值的选项或文本；目标平台、普通模式 action、Trellis 用户名和 React Bits tier / registry 等仍须通过对应参数预先提供或保留交互。非交互执行必须二选一：普通模式提供 `--platform`、`--projects-root`、`--action init|reset` 和其余适用输入；project-only 提供 `--platform`、`--init-projects` 和其余适用输入；最后再加 `--yes` / `-Yes` 消除 yes/no 确认。

## 仓库定位

本仓库维护以下源文件：

| 路径 | 用途 |
|---|---|
| `ENTRYPOINT.md` | 由 Git 追踪的版本监控配置和工作流总入口，也是版本检查与 `update` / `更新` 的可恢复基线。 |
| `AGENTS.md` | 本机可选的仓库补充规则；根 `.gitignore` 忽略，不进入远程 `main`。新 clone 不包含该文件，缺失时不得作为操作前置条件。 |
| `README.md` | 当前工作流的详细说明文档。 |
| `README.html` | 当前工作流的静态 HTML 说明页。 |
| `CHANGELOG.md` | 从 `v1.0.0` 起按 Git tag、中文、最新版本在前的顺序维护发布变更。 |
| `LICENSE` | 本仓库原创内容适用的 Apache License 2.0 完整许可文本。 |
| `sbtd-workflow-onboard/LICENSE` / `NOTICE` | 自包含 Onboard Skill 的原创内容使用与仓库根一致的 Apache License 2.0，并声明 `Copyright 2026 KunoLu`；文件随公开安装和本地同步一起分发。 |
| `sbtd-workflow-onboard/templates/skills/*/LICENSE` / `NOTICE` | 除第三方衍生的 `seo-geo` 外，其余 bundled Skill 的原创内容均使用同一 Apache License 2.0 和 `Copyright 2026 KunoLu` 声明；既有第三方来源说明继续保留。 |
| `sbtd-workflow-onboard/templates/skills/web-ui-autotest-generator/LICENSE` / `NOTICE` | 个人独立实现的 bundled `web-ui-autotest-generator` 使用与仓库根一致的 Apache License 2.0；`NOTICE` 声明 `Copyright 2026 KunoLu`，两份文件随独立安装的 Skill 一起分发。 |
| `sbtd-workflow-onboard/templates/skills/seo-geo/LICENSE` / `NOTICE` | 第三方衍生的 bundled `seo-geo` 保留 ReScienceLab/opc-skills 的 Apache License 2.0；`NOTICE` 固定上游 source、revision 和本地修改范围，`Copyright 2026 KunoLu` 仅适用于本地修改。 |
| `install.sh` | macOS / Linux 交互式安装入口，直接以 `sbtd-workflow-onboard` 目录作为 `source-root`。 |
| `install.ps1` | Windows PowerShell 交互式安装入口，参数语义与 `install.sh` 对齐。 |
| `docs/lessons.md` | Lessons 必读短入口；执行仓库操作前必须先读取。 |
| `docs/lessons/index.md` | Lessons 完整索引，按 tags、适用场景和详情路径检索。 |
| `docs/lessons/topics/**` | Lessons 完整详情，按当前任务命中后读取。 |
| `docs/prd/knowledge-base-integration-prd.md` | P1 / P1.1 已实现能力与 P2 Evidence Store / PR Gate 实施方案。 |
| `docs/assets/npx-skills-global-onboard-install.md` 等 5 份流程判定图 | Onboard 安装 / init / reset / init-projects 与 SBTD 工作路径 mermaid；从「安装及使用说明」和「工作流主线」跳转。 |
| `prompts/automations/sbtd-workflow-tools-version-check.md` | Orca `SBTD Workflow Tools Version Check` 的版本化 prompt 源；每次仓库代码改动后评估是否需要调整，只有执行 `sync` 时才与 live automation 比较并按需同步。 |
| `sbtd-workflow-onboard/` | onboard Skill 目录；普通 `sync` 时会作为完整 Skill 同步到 `/Users/lusonglin/.agent/skills/sbtd-workflow-onboard/`。 |
| `sbtd-workflow-onboard/catalog.json` / `catalog.schema.json` | Bundled Skill、external Skill 上游源与模板源路径目录，以及对应 Draft 2020-12 结构契约。 |
| `sbtd-workflow-onboard/SKILL.md` | onboard Skill 入口说明。 |
| `sbtd-workflow-onboard/REFERENCE.md` | onboard、安装、检测和工具配置参考。 |
| `sbtd-workflow-onboard/scripts/onboard.py` | init、reset、安装、检测、Trellis init 和 bootstrap 检测自动化脚本。 |
| `sbtd-workflow-onboard/templates/agents/AGENTS.global.md` | 全局 Agent 规则模板。 |
| `sbtd-workflow-onboard/templates/agents/AGENTS.project.md` | 项目级 Agent 规则模板，不在普通 sync 中同步。 |
| `sbtd-workflow-onboard/templates/skills/**` | 全局 Skill 模板目录，包含 `SKILL.md`、`references/`、`scripts/`、`assets/` 等。 |
| `sbtd-workflow-onboard/templates/project/.gitignore` | 新项目模板 `.gitignore`。 |

仓库编排按产物类型分层和自包含 Skill 目录：版本化自动化 prompt 位于 `prompts/`，Onboard 运行实现位于 `scripts/`，可安装载荷保留在 `templates/`，第三方 fallback 保留在 `assets/`。`templates/` 不提升到 Onboard 根目录，因为它明确区分“安装器实现”和“将被复制到目标位置的模板载荷”。

`ENTRYPOINT.md` 必须由 Git 追踪，保存版本检查和 `update` / `更新` 使用的 authoritative baseline；新 clone 必须直接取得它。根 `AGENTS.md` 是本机可选补充规则，已加入根 `.gitignore` 并从 Git 索引移除，不进入远程 `main`；新 clone 不包含该文件，工作树缺失时继续使用已追踪规则，不得把它的存在当作 Gate。

普通修改任务只更新本仓库内的源文件。每次仓库代码或工作流规则改动后，都必须评估 `CHANGELOG.md`、`README.md`、`README.html` 和版本化 automation prompt 是否需要同步调整。只有用户明确输入 `sync` 或 `同步` 时，才把允许列表中的全局规则和 Skill 同步到本地生效路径；sync 允许列表明确包含 bundled `web-ui-autotest-generator` 完整目录到 `/Users/lusonglin/.agent/skills/web-ui-autotest-generator/` 的映射。required Ponytail Skills（`ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt`）不得作为同步表 `cp` / `rsync` 行；sync 在复制 Onboard 后必须用已同步的 `scripts/onboard.py install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt --scope global --source auto --global-skills-dir /Users/lusonglin/.agent/skills --yes` 从 stable mirror 安装，并确认 4 个 `SKILL.md` 存在。随后比较版本化 prompt 与 Orca `SBTD Workflow Tools Version Check` 的完整内容，仅在存在差异时同步到 live automation 并报告结果。`update` / `更新` 只处理版本写回和归档，与版本化 prompt 和 live automation 无关；`AGENTS.project.md` 不在普通 sync 范围内。

## 工作流主线

模板遵循“项目事实优先、工具强证据启用、修改最小可验证”的原则。

```text
读取 `docs/lessons.md` 短入口，并按需读取 lessons index / topic
  -> 澄清需求与 SBTD 判断
  -> Trellis / GitNexus / Skill 按证据启用
  -> 实现或配置修改
  -> 项目原生验证
  -> BDD / Web / Mobile / 发布风险补充验证
  -> 最终报告状态、跳过原因、剩余风险
```

全路径判定图：[SBTD 支持的工作路径](docs/assets/sbtd-workflow-paths.md)。

关键边界：

- Trellis 负责复杂任务生命周期、任务产物和阶段门禁，不强制用于所有小任务。
- 如果已确认当前目录是项目根目录，且存在项目级 `AGENTS.md`，但根目录没有 `.trellis/`，Agent 必须提示项目尚未执行 `trellis init`；普通项目操作默认不代用户执行。例外是 `sbtd-workflow-onboard` 的 `init` / `reset`：在 Trellis CLI 已可用、用户确认 username 后，onboard 使用 `--platform` 的精确 Trellis flag（`codex` / `claude` / `kimi`）或显式 `--trellis-platform` 运行 `trellis init -u <username> ... --yes --skip-existing`。空 flag 不会交给 `trellis init --yes`（否则 Trellis 会默认安装 Claude 和 Cursor）。`oh-my-pi` 必须显式给出 `omp` 和/或 `pi`。
  Trellis 平台标志相互独立：`omp` 只生成 `trellis init --omp`，`pi` 只生成 `--pi`，onboard 不得在两者之间替换。
- Trellis CLI 升级后，已有 `.trellis/` 的项目先运行 `trellis update` 刷新生成脚本和 filesystem-safety guard；如果更新涉及 SessionStart、PreToolUse 或其他 hook 配置，先重启对应 Agent host / IDE，再验证新会话身份或 hook 行为。对 uninstall、archive、task start / set-*、Channel 名称等删除 / 移动 / 路径解析操作，不绕过 dirty-data、manifest ownership、safe-name 和 active-task pointer containment guard。升级后不要假设 `trellis update` 会改写既有 session pointer；越权任务路径按无任务处理。
- `.trellis/config.yaml`、`.trellis/workflow.md` 和 task artifacts 只定义共享 workflow gate，不标识运行平台。当前 host 与其专属生成资产决定本次执行：Codex 使用 `.codex/**`，OMP 使用 `.omp/**`；二者共存时按当前 host 选择，纯静态文件不足时标记 unknown。仅当前 host 为 Codex 且 `.codex/**` 集成可用时解释 `codex.dispatch_mode`：`auto` 由主会话协调并按职责调度 role subagent，显式 Inline 与非法显式值的 fail-closed fallback 也仅属于 Codex。仅当前 host 为 OMP 且 `.omp/**` 集成可用时使用 OMP `task` worker 和生成的 agent 定义，不得套用 Codex dispatch。单个 platform role subagent 不构成 Channel 触发，Channel 仍须用户明确请求或 preflight 后确认；每项变更职责只允许一个写入执行者，用户请求的独立只读复核可并行。
- Codex remote plugins、connectors 和延迟加载工具以当前会话的 `tool_search`、工具列表或 MCP 可见性检查为准；候选 catalog 不等于已授权或已可调用。项目级 marketplace 无效不得否定其余有效 plugin；可选 MCP 首轮工具缺失可能只是启动宽限期。
- GitNexus 只有在 MCP 可用且项目索引有效时使用，作为影响分析和变更检测辅助。
- GitNexus 的 PDG、taint、trace、多分支索引和不同 MCP transport 属于显式 opt-in 能力；使用时必须记录模式 / 分支并回到源码与测试复核。CLI 升级若改变 receiver / import / interface 解析，必须重新 `gitnexus analyze` 后再依赖索引。MCP allowlist 未覆盖时 GitNexus MCP 对该仓库不可用，不得当作 MCP 可读；fail-closed 只读时不走 MCP 写入；二者都不跳过 CLI 重新 analyze。
- Skill 按场景调用，不替代项目规范、Trellis 产物、测试或人工判断。
- AGENTS 模板只承载常驻上下文必须知道的路由、触发条件、硬性安全边界和最终报告要求；详细流程、命令参数、检查清单和专项判断优先放入对应 Skill 延迟加载。
- Web 和 Mobile 验证工具分工明确，不把诊断、探索和可重复测试混为一谈。
- SEO/GEO 只面向公开 Web 搜索可见性，不替代 Web 运行时诊断、Playwright 回归、发布检查或人工内容评审。
- 跨仓或链路不完整时，mock 只能基于 contract、schema、真实响应样例、既有 fixture 或用户明确确认；mock-backed 不能冒充 full-stack 通过。
- `rtk` 是命令输出压缩层，不是测试 runner。unit test、API / integration test、Playwright Web E2E、Maestro Mobile / Hybrid E2E 或任何需要落地报告的命令，必须先评估缓存 / 回放是否会跳过文件写入；报告型正式验证默认使用原生命令或项目明确的 no-cache / report-safe 命令，缺报或旧报时原生命令复验。
- API / Web E2E / Mobile E2E / Hybrid E2E 调试轮次可以保留多份带业务名、分支名和时间戳的本地报告快照；一旦 Playwright 或 Maestro 运行产生 runner 原生报告，或 API / integration / unit runner 生成了本轮需要保留的报告，无论最终全量是否通过，都要在下一次可能清空输出的运行前生成该次运行的命名报告和同目录同 stem 的中文 Markdown 汇总。Playwright 的同 stem 以命名后的 HTML 为准，不以 `results.json` 为准。
- API / integration 的中文 Markdown 汇总必须包含 URI 覆盖矩阵，将每条覆盖范围描述映射到具体 `method + URI path`、测试脚本 / case、预期状态码或副作用，以及 `.feature` / contract / schema 依据。
- 任何工具不可用时，要标记 `blocked`、`skipped` 或 `not-needed`，不能声称对应验证已通过。

## SBTD：SDD、BDD、TDD、DDD

SBTD 是本模板对 SDD、BDD、TDD、DDD 的组合简称。它不是单独的新工具，而是用于组织需求、设计、实现和验证的协作框架。

| 概念 | 全称 | 在模板中的作用 |
|---|---|---|
| SDD | Specification-Driven Development | 用 PRD、design、implement、验收标准和长期规则说明“要做什么、为什么做、怎么验证”。在 Trellis 项目中，对应任务产物和 `.trellis/spec` 的长期规则。 |
| BDD | Behavior-Driven Development | 用 Given / When / Then 或项目已有 Gherkin 约定固化用户可见行为。新增或修改 UI、API、CLI、权限、错误、状态变化和外部集成可观察行为时，默认需要持久 BDD 场景；分仓或跨端链路先做上下文完整性 gate。主动使用 `gherkin-bdd` 且请求包含 `sync` / `同步` 时，原有 BDD Sync Mode 保持不变：全量扫描当前工作树与 `features/`，多仓时先确认其他仓库更新状态再同步 `.feature`。BDD / 知识库请求具有明确 `read` / `读取` 只读意图且不含变更意图时，进入 Knowledge Ingest，按目标 ref 固定精确 SHA 并生成派生行为目录。 |
| TDD | Test-Driven Development | 对 bug 修复、核心业务逻辑、算法、数据转换、高风险路径和回归敏感模块采用测试先行。BDD 固化可观察行为，TDD 把它转成可执行测试和红绿重构循环。 |

**强制 post-grill 审核**：无论由 Agent 自发调用还是用户主动调用，每次完整执行 `grill-with-docs` 结束后都必须立即调用 bundled `book-ddd-distilled-modeling` 独立二次审核，并单独输出 `DDD Boundary Review`。`grill-with-docs` 内嵌的 external `domain-modeling` dependency 不能替代该二次审核；状态为 `needs-clarification` 时先继续澄清并重审，状态为 `blocked` 时说明阻断。未达到 `confirmed` 不得进入需求确认、PRD、design、Trellis task 或实现。未使用 `grill-with-docs` 时仍按业务术语、领域规则和模型歧义独立判断是否调用 DDD Skill，并说明未调用原因；只有调用与跳过存在会改变需求、领域边界或实现决策的实质权衡时才询问用户，项目事实已消除歧义时直接推进，不制造重复确认门。


### Book-derived 开发门禁

进入开发任务时先输出 `Book Gate Plan`，依据项目事实为 5 个 bundled `book-*` Skill 标记 `required` / `on-demand`、命中原因、执行阶段和独立 Gate state。Gate state 只能是 `planned` / `running` / `passed` / `blocked` / `not-required`，并按 `planned` → `running` → `passed` / `blocked` 转换；具体 reviewer status 仅在 Skill 运行后填写。命中以下客观触发条件后必须调用并通过对应审核，不能再由 Agent 主观跳过：

| 审核 | 强制触发场景 | 最适合阶段与通过条件 |
|---|---|---|
| `DDD Boundary Review` | 每次完整执行 `grill-with-docs` | 需求确认 / PRD 前；`confirmed` |
| `DDIA Data Design Review` | 持久化 / 共享数据、schema / migration、shared / persistent / cross-request / cross-process cache、异步 / 跨服务数据流、数据所有权、事务边界、读写路径、backfill / replay / rollback / recovery 任一变化 | `design.md` / `implement.md` 稳定和实现开始前；`confirmed` |
| `Legacy Change Safety Review` | 修复既有行为 bug，或既有代码存在弱测试、行为不清、隐藏依赖、高回归风险任一项 | 首次行为修改前；`characterized`；安全网必须先有生产 seam 时进入 `seam-required` |
| `Refactoring Review` | 修改既有生产代码 | 首次实现编辑前；`proceed`，或先完成 `refactor-first` 并复审；legacy 为 `seam-required` 时可先用 `safety-seam-only` |
| `Release Readiness Review` | service / API / auth / billing / notification / job / queue / scheduler / external integration / data pipeline / deployment 等生产路径变化 | 所有适用 testing-tool gate 和 project validation 后、任务完成或最终发布决策前；`ready` |

同时命中 legacy 与 refactoring gate 时，正常顺序为 legacy `characterized` 后再执行 refactoring；唯一受控例外是 `seam-required` → `Refactoring Review` (`safety-seam-only`) → 最小行为保持测试 seam → legacy `characterized` → 常规 `Refactoring Review`。`needs-*`、`seam-required`、`refactor-first` 或 `blocked` 都会让 Gate state 保持 `running` 或转为 `blocked`，修正后必须重审。Release gate 中必需验证缺失只能 `blocked`，只有 optional check 可由明确 accountable owner 接受为 residual risk。未命中上述强制触发条件的其他场景仍按需调用。

推荐顺序不是死板流程，而是风险驱动：

1. 领域语言或边界不清时，先做 DDD 轻量建模。
2. 需求需要沉淀时，用 SDD 写清规格、范围和验收。
3. 有用户可见行为时，用 BDD 固化场景。
4. 需要高信心实现时，用 TDD 让测试驱动代码变化。

### BDD Knowledge Ingest

`gherkin-bdd` 的 `read / 读取` 是面向知识库的只读入口，与 `sync / 同步` 和普通 BDD 写入请求明确分开。只有请求具有明确只读意图、且不含新增、修改、更新或删除意图时才进入 Knowledge Ingest；“先读取再修改”仍走普通 BDD 工作流：

- 每个仓库由知识库或产品配置指定目标 branch、tag 或 SHA，例如 `staging`。
- 读取前把目标 ref 解析为精确 commit SHA；ref 表示选择策略，SHA 表示本次不可变快照。
- 从 Git object 或隔离 worktree 读取仓库自有 `.feature`，不切换开发者活动 worktree。
- 聚合结果是可重建派生视图；目标 ref 中的 `.feature` 仍是行为 SOT。
- 不要求或补写 `feature_id`、`scenario_id`、新 tags、owner 字段，也不引入 BDD Runner。
- 使用 repository key + path + Feature / Rule / Scenario 名称 + 可选 Examples fingerprint + SHA 作为读取 locator；跨仓相似或冲突只生成候选，不自动合并或改写。
- 输出 `Knowledge Ingest`: `run` / `partial` / `blocked` 和 `Mutation: none`。请求含 `sync` / `同步` 时，仍执行原有可写 BDD Sync Mode。

P1.1 已通过 bundled `knowledge-base-integration` Skill 落地产品注册表、Workspace Mapping、Evidence Policy 决策、目标 ref / Revision Set、完整无 ID Gherkin 目录、静态 / manifest 绑定、跨仓候选、幂等 ingest / smoke、隔离 worktree、分阶段 Smoke、基础设施重试、本地 / 命令式 Runner Adapter、可信环境对齐、artifact manifest、checksums 和 metrics。从本仓库根目录校验随 Skill 提供的示例配置：

```bash
python sbtd-workflow-onboard/templates/skills/knowledge-base-integration/scripts/knowledge_base_p1.py validate-config \
  --product sbtd-workflow-onboard/templates/skills/knowledge-base-integration/references/product.example.yaml \
  --workspace sbtd-workflow-onboard/templates/skills/knowledge-base-integration/references/workspace.local.example.yaml
```

同一 CLI 还提供 `decision`、`ingest` 和 `smoke` 子命令；各子命令的必需参数以 `--help` 和该 Skill 的说明为准。安装后则先定位 `knowledge-base-integration` Skill 根目录，再运行其 `scripts/knowledge_base_p1.py`。服务器只收集本轮命令新建或刷新的原生报告及同 stem 中文汇总，Mobile 等能力通过 Runner labels 调度。P1.1 只生成 `Evidence Publication: not-configured` 的待发布 bundle，Evidence Store、PR Check、自动失效、quarantine、retention 和远端 Gate 仍属于 P2。完整边界见 [知识库集成 P1 / P2 落地方案](docs/prd/knowledge-base-integration-prd.md)。

## 工具职责边界

| 工具 | 主责 | 不负责 |
|---|---|---|
| Codex `tool_search` / Plugin / Connector | 发现延迟加载工具、remote / local plugin、connector 和 ChatGPT-hosted MCP 能力。 | Catalog 或 marketplace 展示不等于已授权 / 已可调用；安装需用户明确请求，session auth / OAuth / cookies / tokens 不写入项目。 |
| Chrome DevTools MCP | Web 运行时诊断、真实 Chrome 检查、console、network、storage、performance trace、screenshot 证据。 | 不作为 CI gate，不替代 Playwright E2E。 |
| Playwright CLI / `@playwright/test` | 项目内 Web E2E、Web 回归、跨浏览器检查和 CI gate。 | 不默认全局安装；项目未安装时必须先询问。 |
| Playwright MCP | Agentic Web 探索、可访问性快照、locator 辅助和临时页面检查。 | 不替代项目内 `playwright test`。 |
| Maestro CLI | Android、iOS、React Native、Flutter、Hybrid App E2E，以及可选 Chromium Web smoke。 | 不作为 Web 回归主责；Web 只做 smoke。 |
| Maestro MCP | 设备检查、view hierarchy、截图、flow 辅助，以及终态 Cloud per-flow run 的状态与 artifact 诊断。 | 不单独替代 Maestro CLI；当前 Agent / IDE 的 MCP 配置需包含 `JAVA_HOME` / `PATH` env。 |
| `shadcn` | shadcn/ui 项目的组件、registry、preset、CLI、docs / diff 和组件组合规则。 | 不替代通用 UI/UX 设计判断、`impeccable` 视觉打磨或 React Bits Free / 付费 tier 判定。 |
| `web-ui-autotest-generator` | 生成和审计 repo-resident Playwright 测试资产、选择器和覆盖率报告。 | 不执行 E2E；执行底座仍是项目内 Playwright CLI。 |
| `seo-geo` | 公开网站、落地页、文档站、产品页、营销页的 SEO/GEO、schema、meta、robots / sitemap 和 AI 搜索可见性专项检查。 | 不替代 Chrome DevTools MCP、Playwright CLI、项目发布检查或内容评审；不用于内部后台、API、CLI、移动 App。 |
| `maestro-mobile-e2e` | 从 BDD `.feature` 派生和维护 repo-resident Maestro Mobile / Hybrid flow，约束报告路径，并按需加载真机排障 lesson。 | 不替代 BDD、项目验证或 Maestro CLI。 |
| `knowledge-base-integration` | 运行产品级 Knowledge Ingest、Evidence Policy、Revision Set、完整无 ID 行为目录、幂等分阶段 smoke、Runner Adapter 和证据完整性校验。 | 不修改源 `.feature`，不发布 Evidence，不写 PR Check；P2 负责远端治理。 |
| `rtk` | 用户级全局 CLI，用于压缩 terminal 命令输出，降低上下文占用；缺失时先说明作用并询问是否协助安装。 | 不替代测试 runner；报告型 unit / API / Playwright / Maestro 命令先评估缓存与文件写入风险，必要时使用原生命令或 fallback-native。 |
| `caveman` | 用户级全局 Agent Skill，用于压缩 Agent 回复和长任务状态更新；缺失时先说明作用并询问是否协助安装。同一主要目标达到 3 次中间状态更新、5 个独立工具结果、长任务 / 上下文压力或重复自动化 / review / 验证轮次中的任一条件时，`autoLiteEligible` 单调锁存，下一条普通重复状态必须进入任务级 `auto-lite`。 | 不替代项目 Skill、BDD、TDD、验证、GitNexus、Trellis 或最终报告；保护区只覆盖当前回复，只有新的主要目标重置。任务级 / 会话级退出按全局状态机处理，手动 `/caveman` 不清除自动退出。 |

同一浏览器上下文同一时间只允许一个 controller，避免 Chrome DevTools MCP、Playwright MCP 和 Playwright CLI 互相污染状态。

## Playwright 集成策略

Playwright CLI 是项目级 Web E2E 依赖，不是全局默认工具。

检测顺序：

1. 检查目标项目是否有 `package.json`。
2. 检查 `@playwright/test`、`playwright` 依赖、Playwright 配置、`tests/e2e` 或 E2E scripts。
3. 如果 Web 回归或 `web-ui-autotest-generator` 需要 Playwright，但项目内缺失 CLI，先询问用户是否安装到项目 devDependency。
4. 用户确认后按项目包管理器安装，安装成功后继续验证流程。
5. 用户拒绝或安装失败时，`Playwright CLI` 标记 `skipped-by-user` 或 `blocked`，`Playwright Web Tests` 标记 `blocked` 或 `skipped`。

Fallback：

- 可使用 Chrome DevTools MCP 做运行时诊断。
- 可使用 Playwright MCP 做页面探索、可访问性快照或 locator 辅助。
- 不能声称 Web E2E 或回归测试已通过。

Web E2E 报告规则：

- 完整环境可用时跑 full-stack Playwright E2E；只有 contract 或 mock 环境时标记 `contract-backed` 或 `mock-backed`。
- `--reporter=list` 只用于诊断或定点重跑；Web E2E 进入正式验证范围时，最终收尾必须再跑不覆盖项目 reporter 的计划范围命令，生成命名 HTML 和同 stem 中文 Markdown 汇总。
- Playwright HTML reporter 的 `outputFolder` 默认使用 runner 临时目录 `tests/e2e/reports/.playwright-html-current/`；该目录可能被每次 Playwright 运行清空，不保存正式命名报告。
- 最终正式 Playwright HTML 报告快照默认写入 `tests/e2e/reports/html/`，命名为 `playwright-report-{feature_file_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.html`，并生成同 stem 的中文 Markdown 汇总。`branch_slug` 取当前分支，`/`、空格和特殊字符替换为 `_`。多轮调试可以保留多份带业务名、分支名和时间戳的本地快照，最终是否通过仍由 `Final Full Rerun` 表达。
- `feature_file_name` 默认取关联 BDD `.feature` 文件名去掉扩展名；smoke test 使用 `smoke`；一次运行覆盖多个 `.feature` 时优先使用 suite 名，否则使用 `multi-feature`。
- Playwright Markdown 汇总必须与命名后的 HTML 报告完全同 stem；`results.json`、`junit.xml`、`test-results/` 和默认 `index.html` 不能决定正式 Markdown 文件名。`results.md`、`result.md`、`junit.md` 或 `index.md` 不能满足最终 `Run Summary MD`。
- 命名后的 HTML 是正式报告；Playwright 默认 `index.html` 只作为 `.playwright-html-current/` 中的复制源或工具兼容产物。只要 Playwright 已产生 `index.html`、`results.json`、`junit.xml` 或等价产物，最终输出前必须确认命名后的 HTML 和同 stem 中文 `.md` 实际存在。
- 调试轮次失败后先重跑失败 spec，再跑受影响子集，最后跑计划范围内全量验证；最终全量是否通过由 `Final Full Rerun` 表达，不能用“未全绿”跳过报告文件。

API / integration 报告规则：

- API 正式报告默认写入 `tests/api/reports/`，stem 使用 `api-report-{suite_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}`；自定义 API 脚本如果没有原生 reporter，正式验证时必须捕获 stdout、stderr、exit code、命令和时间戳为 raw report，并生成同 stem 中文 Markdown 汇总。
- API Markdown 汇总必须包含 URI 覆盖矩阵。每条覆盖范围描述都要映射到具体 `method + URI path`，并记录对应测试脚本 / case、期望状态码或副作用、关联 `.feature` / contract / schema；同一覆盖描述涉及多个 endpoint 时逐行列出。
- Base URL、环境名或服务名可以单独记录，但不能用脚本名、权限链路概括或业务域名称替代 URI path；无法确定 URI 的覆盖项必须标记 `blocked` 或 `missing-uri`。不要写入真实账号、token、敏感 query/body 或生产数据。

## Maestro 集成策略

Maestro 面向移动 App 和 Hybrid App E2E。模板不推荐用 Maestro 主做 Web 回归；Web 场景只适合做少量 Chromium smoke，主责仍在 Playwright CLI。

检测和安装顺序：

1. 需要 Maestro 前先检查 Java 17+。
2. 优先执行 `java --version`，失败时回退 `java -version`。
3. 当前 JDK 满足 17+ 时优先使用当前 JDK。
4. Java 缺失或低于 17 时，先扫描本机已有 JDK，优先选择已安装且满足 17+ 的 JDK。
5. 只有本机没有可用 17+ JDK 且用户确认后，才引导安装 JDK；默认建议安装 OpenJDK Temurin 21 最新 JDK，下载来源为 `https://github.com/adoptium/temurin21-binaries/releases`。
6. 用户指定其他 Java 版本时，只允许安装 Java 17 或更高版本，拒绝任何低于 17 的版本。
7. Java 通过后检查 Maestro CLI。
8. Maestro CLI 缺失时询问用户是否安装到开发环境或 CI runner。
9. Maestro CLI 可用后再检查 Maestro MCP，并引导当前 Agent / IDE 的 MCP 配置同时包含 `command`、`args` 和 env。
10. Maestro MCP 的 `JAVA_HOME` 使用选定的 JDK home，`PATH` 必须优先包含 Maestro bin 目录和 JDK `bin` 目录，再包含系统基础路径。

Fallback：

- Maestro MCP 缺失或 MCP env 未配置但 CLI 可用时，继续使用 `maestro test` 执行已有 flow，并单独报告 MCP 状态和缺失配置。
- Maestro CLI 缺失且用户拒绝安装时，`Maestro Mobile` 标记 `blocked` 或 `skipped`。
- Java 17+ 缺失且用户未确认安装时，只报告阻塞和安装引导，不自动安装。
- 设备、模拟器、app binary、appId、bundleId、测试账号或环境不可用时，必须记录阻塞原因。

Maestro flow 资产和报告规则：

- 需要从 Mobile / Hybrid BDD 场景生成或维护 Maestro flow 时，调用 `maestro-mobile-e2e`。
- Flow 固定写入 `maestro/flow/`，使用 `.yml` 扩展名。
- 文件名和 YAML `name` 使用英文业务场景名；文件名使用 lower-kebab-case，例如 `maestro/flow/login-success.yml`。
- iOS 和 Android 需要明显不同 flow 时，可使用 `maestro/flow/ios/*.yml` 和 `maestro/flow/android/*.yml`；平台 smoke 可使用 `maestro/flow/ios/smoke.yml` 和 `maestro/flow/android/smoke.yml`。
- 全量回归 / smoke flow 固定为 `maestro/flow/smoke.yml`。
- 每个 flow 必须追踪到源 `.feature` 路径、场景名称、平台范围和测试模式。
- Maestro CLI 最终正式 report 固定写入项目根目录 `.maestro/reports/`。
- 报告命名为 `maestro-report-{flow_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.xml` 或 `.html`，并生成同 stem 的中文 `.md` 运行汇总；`flow_name` 取 Maestro flow 文件名 stem，smoke flow 使用 `smoke`，是否生成 HTML 遵循项目或用户对人类可读报告的需要。
- 优先让 Maestro 直接输出到带分支名和时间戳的文件；如果项目 wrapper 只能输出到固定目录或固定文件，使用 `.maestro/reports/.maestro-current/` 作为临时输出，再复制 / 提升为 `maestro-report-{flow_name}-{branch_slug}-{timestamp}`。`~/.maestro/tests`、`.maestro-current/`、固定 `report.xml` / `report.html` 都不是正式保留报告。
- stdout-only Maestro run 只用于诊断或定点重跑，不能满足正式 Mobile / Hybrid E2E 报告 gate；正式验证收尾必须补跑 `--format` / `--output` 或项目等价 reporter，无法产出时标记 blocked。
- Maestro 官方默认运行 artifacts 仍在用户 home 下的 `~/.maestro/tests`；它不是仓库内测试资产。
- iOS 真机遇到 driver setup、端口转发、view hierarchy、tap crash 或版本已知问题时，`maestro-mobile-e2e` 按标签 / 关键字懒加载对应 lesson；未命中时不预先套用临时补丁。

移动端上下文 gate：

- 生成或运行 flow 前确认平台、app artifact、bundleId / appId、设备 / 模拟器 / 云测、后端依赖、base URL / launch args / deep link、账号、数据、权限、稳定 selector 和系统 UI。
- 缺少关键事实时，`Maestro Flow Assets` 标记 `blocked`，不生成脆弱 flow。
- contract-backed 或 app-mocked flow 只能证明对应 contract / mock 假设成立，不能报告为 full-stack Mobile E2E 通过。

## Chrome DevTools MCP 和 Playwright MCP

这两个 MCP 都是 Agent 交互能力，不是项目依赖。

- Chrome DevTools MCP：用于真实 Chrome 运行时诊断，适合白屏、console error、network、cookie、storage、性能 trace、截图和临时复现。
- Playwright MCP：用于 Agentic Web 探索、可访问性快照、locator 生成辅助和页面结构理解。

MCP 配置由 Agent 或 IDE 提供。`scripts/onboard.py` 只做检查和引导，不把 MCP 配置文件复制进业务项目；根目录安装脚本在用户明确选择平台和 MCP server 后，可以执行平台 CLI 配置或写入 Oh My Pi 的 `mcp.json`。Codex plugin / connector 与 ChatGPT-hosted MCP 也遵循同一边界：先确认当前会话可见 callable tool，授权状态由 Agent / connector 管理，不把 session auth 材料写入项目。

## `web-ui-autotest-generator` 使用边界

`web-ui-autotest-generator` 只在需要生成、审计或评估可入库 Web UI 测试资产时启用。

适用场景：

- 用户明确要求生成 Web UI 自动化测试、Playwright、E2E suite 或 UI 回归测试代码。
- 关键 Web UI 用户路径需要进入仓库长期维护。
- 项目已有 Playwright，需要扩展可维护覆盖。
- Trellis 验收要求可重复 UI 回归。
- Chrome DevTools MCP、Playwright MCP、Playwright CLI 或人工复核发现了应进入 CI / 本地 E2E 的覆盖缺口。

不适用场景：

- 只需要一次性页面诊断。
- 只需要截图或 console / network 证据。
- 不准备把测试资产长期维护到仓库。
- 项目不接受 Playwright CLI 或测试数据、账号、环境暂不可用。

默认沉淀路径：

- `tests/e2e/manifest/ui-test-manifest.json`
- `tests/e2e/manifest/ui-selector-audit.json`
- `tests/e2e/manifest/ui-test-coverage.json`

调用 `web-ui-autotest-generator` 的脚本时，模板要求显式传入 `tests/e2e/manifest/` 下的参数路径，不依赖 Skill 示例里的根目录默认值：

```bash
generate_manifest.py --root . --out tests/e2e/manifest/ui-test-manifest.json --pretty
audit_selectors.py --root . --out tests/e2e/manifest/ui-selector-audit.json --pretty
check_coverage.py --root . --manifest tests/e2e/manifest/ui-test-manifest.json --selector-audit tests/e2e/manifest/ui-selector-audit.json --tests-dir tests/e2e --out tests/e2e/manifest/ui-test-coverage.json --pretty
```

失败分析 `ui-test-repair-plan.json` 是运行产物，不是稳定测试资产；如生成，默认放到 `tests/e2e/manifest/ui-test-repair-plan.json` 并通过 `.gitignore` 忽略。验证或 Trellis check 收尾时，必须确认三个可入库 JSON 位于 `tests/e2e/manifest/`，且项目根目录没有残留同名 JSON。

## `shadcn` Skill 使用边界

`shadcn` 只在 shadcn/ui 项目、组件 registry、preset 或 CLI 工作流需要时启用。

适用场景：

- 项目存在 `components.json`，或用户要求初始化 / 维护 shadcn/ui。
- 需要执行或评估 `shadcn init/add/search/view/docs/diff/info/migrate/preset`、preset code、registry item、第三方 / 私有 / 付费 registry 或 shadcn MCP 配置。
- 需要修复 shadcn 组件组合、forms、icons、semantic tokens、Tailwind v3 / v4、Base UI vs Radix API、chat primitives、registry import path rewrite 或已安装组件更新策略。

执行和报告规则：

- UI/UX 任务中先用 `ui-ux-pro-max` 明确产品方向、信息架构、可访问性和设计系统约束，再用 `shadcn` 处理组件来源、CLI、registry 和具体实现规则。
- 按项目 package manager 选择 `npx shadcn@latest`、`pnpm dlx shadcn@latest` 或 `bunx --bun shadcn@latest`。
- 添加或更新组件前先检查 `components.json`、`shadcn info`、已安装组件和项目别名；涉及组件 API 时先查 `shadcn docs`。
- registry 未明确时先询问用户；更新已有组件时先用 `--dry-run` / `--diff`，未经用户明确确认不使用覆盖式更新。

不适用场景：

- 非 shadcn/ui 项目，且用户没有要求引入 shadcn。
- 只是通用 UI 设计判断、视觉 polish、后端、测试、文档或非 React UI 栈任务。
- React Bits Free / 付费 tier、付费 Skill 安装或 key 可用性判定；这些按 React Bits tier 规则单独处理。

## React Bits tier 选择边界

React Bits 不是 shadcn/ui 的必装依赖。安装和 reset 默认保持 shadcn/ui only；只有检测到目标项目是 React + shadcn/ui（存在 `components.json`），且任务需要更强视觉表达、动画组件、blocks 或 landing sections 时，才询问用户是否启用 React Bits。

确认顺序：

- 先说明 shadcn/ui 提供常规应用组件，React Bits Free / 付费 tier 只是可选增强。
- 询问用户选择继续 shadcn/ui only、安装 React Bits Free，或使用已有付费 Starter / Pro / Ultimate。
- React Bits Free 只有在本工作流已有明确免费 source / registry / 安装命令时才安装；未配置时说明暂不可自动安装。
- 付费 Starter / Pro / Ultimate 必须由用户确认，且当前环境能读取 `REACTBITS_LICENSE_KEY`；安装器固定把 Skill 写入项目的 `.agents/skills/react-bits-pro/SKILL.md`，已有目标直接覆盖且不保留备份，不打印、不输出、不提交 key。
- reset 时保留检测到的既有 React Bits Free、Starter、Pro 或 Ultimate tier / registry，不用默认免费版覆盖。

## `seo-geo` 使用边界

`seo-geo` 只在公开 Web 资产需要搜索可见性检查时启用。

适用场景：

- 用户明确要求 SEO、GEO、AI search visibility、ChatGPT / Perplexity / Google AI Overview 可见性、schema、JSON-LD、meta tags、robots.txt、sitemap.xml、canonical 或关键词研究。
- 当前变更影响公开网站、落地页、文档站、产品页、营销页、公开博客或公开 README 页面。
- 发布前验收标准明确包含搜索引擎、AI 搜索引用、社交分享预览、结构化数据或 crawl / indexing 检查。

不适用场景：

- 内部后台、登录后页面、API、CLI、移动 App、纯后端、测试资产、文档内部重排或无公开 URL 的一次性 UI 调整。
- 只需要 Web 运行时诊断、截图、console / network 证据或 Playwright 回归。
- `seo-geo` Skill 未安装且当前任务不以搜索可见性为主要目标。

执行和报告规则：

- 优先确认目标 URL、preview URL、生产 / staging 环境、是否允许抓取、是否已有 sitemap / robots / schema 约定。
- 没有公网 URL 或 preview URL 时，只做源码 / HTML 静态检查；最终报告 `SEO/GEO: static-only` 或 `blocked`，不能声称线上 SEO/GEO 已验证。
- 基础 audit 不要求 DataForSEO；DataForSEO login / password 只作为关键词、SERP、backlink、domain overview 等增强分析的可选凭据。
- 关键词量、SERP、AI 搜索可见性和平台抓取规则具有时效性，必须用当前可用来源核对。
- 不得把 DataForSEO login / password、Search Console 数据、付费报告、真实账号、密钥、PII 或生产敏感 URL 写入仓库、日志、截图、测试或正式报告。
- 最终输出或 Trellis check summary 必须报告 `SEO/GEO`: `audited` / `static-only` / `blocked` / `skipped` / `not-needed`。

## 跨仓测试模式和报告闭环

API、Web E2E、Mobile E2E、Hybrid E2E 或发布前 smoke 进入正式验证时，先选择测试模式：

| 模式 | 含义 | 报告边界 |
|---|---|---|
| `full-stack` | 真实前后端 / app / 环境 / 数据可用。 | 可报告完整链路通过。 |
| `contract-backed` | 完整链路不可用，但有可靠 API contract、schema、fixture 或真实响应样例。 | 只证明符合 contract。 |
| `mock-backed` / `app-mocked` | 使用 mock backend、fixture、launch args 或 app test mode。 | 只证明 mock 假设下的客户端 / app 行为。 |
| `backend-only` | 只验证 API provider 或服务端集成。 | 不等于 Web / Mobile E2E。 |
| `smoke-only` | 只验证启动、登录页、主导航等低依赖路径。 | 不等于完整回归。 |
| `blocked` | contract、环境、账号、数据、设备、artifact 或 selector 缺失。 | 不生成通过报告。 |

正式报告和 Markdown 汇总：

- API / integration 默认目录：`tests/api/reports/`。
- API / integration runner 临时输出默认目录：`tests/api/reports/.api-current/`。
- Playwright HTML reporter 临时输出默认目录：`tests/e2e/reports/.playwright-html-current/`。
- Playwright HTML 正式报告快照默认目录：`tests/e2e/reports/html/`。
- Maestro 默认目录：`.maestro/reports/`。
- Unit test 报告默认继承项目配置；缺少项目约定但需要本地正式证据时，使用 `tests/unit/reports/`，临时输出使用 `tests/unit/reports/.unit-current/`。
- 执行 unit / API / Playwright / Maestro 报告型测试前先记录 `rtk` 决策：`used` / `skipped-for-report` / `fallback-native` / `not-available` / `not-needed`。如果 `rtk` 后报告文件缺失、mtime / size 未变化、内容不对应本轮命令，或输出显示 cache hit / replay / skipped 写入，必须原生命令重跑并以原生结果为准。
- 调试轮次可以保留多份本地命名报告快照；一旦 Playwright 或 Maestro 运行产生 runner 原生报告，或 API / integration / unit runner 生成了本轮需要保留的报告，无论最终全量是否通过，都生成该次运行的命名报告和一份同目录同 stem 的中文 `.md` 汇总。API、Playwright 和 Maestro 的正式报告 stem 必须包含 `branch_slug`；`branch_slug` 取当前 git / CI 分支，detached HEAD 使用 `detached-{short_sha}`，非 git 环境使用 `unknown-branch`，并将 `/`、空格和特殊字符替换为 `_`。
- 正式报告要作为 PR 证据或被知识库读取时，额外生成同 report stem 的 `.evidence.json` 或由跨工具编排器生成聚合 envelope。先定位已安装的 `project-validation` Skill 根目录；通用 / 历史报告按该根目录下 `references/validation-evidence.schema.json`（v1）校验，v1 Schema 只检查 digest 形状，仍须重算报告 SHA-256；需要证明某个 Scenario 被执行时，必须使用同一根目录下的 `references/validation-evidence.v2.schema.json` 和 `scripts/validate_validation_evidence.py`，从 SHA-verified JUnit / Playwright JSON 中唯一匹配 passed case，并要求 case 内 `sbtd.sourceLocatorDigest` 等于重算 locator。证据记录 repository key、原始 source ref、完整 commit SHA、worktree state、trigger、evidence source、source revision、environment alignment、publication status、报告与同 stem 汇总的 SHA-256；`branch_slug` 只用于文件名，不是版本身份。
- `developer-local`、`ci` 和 `knowledge-server` 是三个独立 Evidence Source。dirty developer-local 结果只能是 `local-only`，不能证明 PR head；CI evidence 必须来自 clean checkout；knowledge-server 必须记录完整 Revision Set，且 `smoke-only`、contract 或 mock 结果不得提升为 full-stack。提交前的 evidence 只记录本地状态；创建最终提交后、发布或更新 PR Check 前，必须针对最终 PR head SHA 重新生成或复验并更新 sidecar / envelope，新 commit 使旧证据失效。CI 运行本身不等于已发布，只有目标系统接收后才标记 `published`。普通本地诊断不强制生成 evidence sidecar。v1 同 envelope 共存或 sidecar 自报 label 都不能当作 BDD 覆盖。
- 正式验证范围不能由 runner 是否已经产出报告倒推决定。API / Web E2E / Mobile E2E / Hybrid E2E 一旦进入正式验证范围，stdout-only、terminal-only 或 diagnostic-only 命令不能满足最终报告 gate：API 自定义脚本必须捕获 stdout / stderr / exit code 为 `api-report-*-{branch_slug}-*.txt` / `.json` raw report，Playwright `--reporter=list` 后必须补跑正式 reporter，Maestro stdout-only 后必须补跑 `--format` / `--output` 或项目等价 reporter；无法产出时标记 `Final Test Report: blocked` 和 `Run Summary MD: blocked`。
- 通用防覆盖规则：`coverage/`、`test-results/`、固定 `junit.xml`、runner 的 `current` / `latest` 目录和各工具临时输出目录都可能被下一轮运行清空、覆盖或重建；需要保留时，先复制 / 提升到正式快照目录和时间戳 stem，再启动下一轮会改写同一输出的命令。
- Playwright 报告命名为 `playwright-report-{feature_file_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.html`；smoke 使用 `smoke`，多 `.feature` 运行优先使用 suite 名，否则使用 `multi-feature`。
- Playwright `.md` 汇总必须使用命名 HTML 的同 stem，不得使用 `results.json` / `junit.xml` / 默认 `index.html` 的 stem。
- Maestro 报告继续使用 `maestro-report-{flow_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}` stem；`flow_name` 取 flow 文件名，不改成 `feature_file_name`。
- API 报告使用 `api-report-{suite_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}` stem；unit 报告使用 `unit-report-{suite_name}-{YYYY_mm_dd}-{HH_MM_SS}` stem。缺少明确 suite 时可以省略 `{suite_name}`，但不能省略 `{branch_slug}`，也不能使用会被下一轮覆盖的固定文件名作为正式报告。没有原生 reporter 的 API 正式验证至少保留 `.txt` / `.json` raw report 和同 stem `.md`。
- `.md` 汇总使用中文撰写，状态枚举值、命令、文件路径、case / spec / flow 名称、错误原文和技术标识符可以保留英文；内容记录运行 case / spec / flow 列表、关联 BDD `.feature` 路径和场景名、总轮次、每轮命令、失败 case / spec / flow、失败原因、修复动作、修改文件摘要、定点重跑、影响范围重跑、最终全量重跑、跳过项和剩余风险。
- 失败修复后先重跑失败 case / spec / flow，再跑受影响子集，最后跑计划范围内全量验证；fail-fast 停在首个失败时，修复后必须继续跑未覆盖测试或重跑全量。
- 汇总和报告不得写入真实账号、密钥、PII、生产数据、完整 token 或敏感请求头。

## 最终验证工具栈

最终验证阶段按以下顺序和风险叠加：

| 层级 | 工具 / 方法 | 触发条件 | 状态要求 |
|---|---|---|---|
| 项目原生验证 | lint、typecheck、unit、integration、build、项目 README / Makefile / CI 命令 | 修改代码后默认执行可用的最小有效验证 | 记录命令和结果 |
| BDD 追踪 | `gherkin-bdd`、`.feature`、BDD runner 或测试名追踪 | 新增或修改用户可见行为 | `BDD`: `run` / `traceable` / `blocked` / `skipped` |
| 跨仓上下文 | contract、环境、账号、数据、设备、selector、app artifact | API / Web / Mobile / Hybrid 链路不完整 | `Cross-repo context`: `complete` / `contract-only` / `environment-only` / `missing` |
| GitNexus | MCP 影响分析、变更检测 | GitNexus MCP 可用且项目索引有效 | 成功使用或说明跳过原因 |
| Web 诊断 | Chrome DevTools MCP | 需要真实浏览器现场证据 | `diagnosed` / `inspected` / `blocked` / `skipped` / `not-needed` |
| Web 回归 | Playwright CLI | Web UI、路由、表单、权限、跨页面流程、API 集成、浏览器兼容 | `Playwright Web Tests`: `run` / `failed` / `blocked` / `skipped` |
| Web 测试资产 | `web-ui-autotest-generator` | 需要把 Web UI 回归固化入仓库 | `generated` / `coverage-only` / `blocked` / `skipped` |
| SEO/GEO | `seo-geo` | 公开 Web 资产需要搜索可见性、schema、meta、robots / sitemap 或 AI 搜索引用检查 | `SEO/GEO`: `audited` / `static-only` / `blocked` / `skipped` / `not-needed` |
| Mobile / Hybrid E2E | Java 17+、Maestro CLI、Maestro MCP | Android、iOS、RN、Flutter、Hybrid App 用户旅程 | `Maestro Mobile`: `run-local` / `run-cloud` / `blocked` / `skipped` / `not-needed` |
| 发布风险 | `book-release-readiness`、Channel preflight | 生产路径、外部集成、部署敏感、高风险变更或高 reasoning 多 worker 并发 | 记录风险、fallback、rollback 和用量风险 |

`project-validation` 覆盖 Node / JavaScript / TypeScript、Python、Go、Dart / Flutter、Java、Kotlin、C++、Swift 和 Objective-C 的代码规范检查、typecheck / static analysis、unit test 与项目 CI 继承规则；unit test 报告路径默认继承项目配置，不由模板统一硬编码，但需要作为本轮证据保留的 unit 报告不能只停留在会被 runner 重写的 coverage / JUnit 固定路径。

全局工具状态建议在最终输出中集中列明：

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
- `rtk`: `used` / `skipped-for-report` / `fallback-native` / `not-available` / `not-needed`
- `Targeted Rerun`: `passed` / `failed` / `blocked` / `not-needed`
- `Final Full Rerun`: `passed` / `failed` / `blocked` / `skipped-with-risk` / `not-needed`
- `Evidence Source`: `developer-local` / `ci` / `knowledge-server` / `not-needed`
- `Source Revision`: `exact` / `dirty` / `unknown` / `not-needed`
- `Environment Alignment`: `verified` / `unverified` / `mismatch` / `not-needed`
- `Evidence Publication`: `local-only` / `published` / `blocked` / `not-configured` / `not-needed`
- `SEO/GEO`: `audited` / `static-only` / `blocked` / `skipped` / `not-needed`

## 模板 `.gitignore` 工具与测试产物策略

项目模板默认追踪项目级 `AGENTS.md`、`CLAUDE.md`、共享 `.agents/skills/**`，以及 Trellis 为 Claude / Codex / OMP 等平台生成的 agents、commands、skills、hooks、extensions 和共享 settings；只忽略 `.claude/projects/`、`.claude/worktrees/`、`.claude/settings.local.json` 与 `.omp/plugins/` 等已确认的本地运行态或机器本地设置。本项目模板用无尾随斜杠的 `.trellis/*` 覆盖 `.trellis` 下所有直接子项，因此 Trellis 生成的 workspace `index.md`、开发者 journal / trace，以及有意配置为 symlink 的顶级 workspace 都作为本地数据被忽略（无尾随斜杠同时匹配目录与指向目录的 symlink），再由 `!` 规则逐项放回需要追踪的 spec / agents / lessons / task 产物；这有意不同于上游 Trellis 默认会 stage workspace 内容的策略，并阻止 workspace 内容自动提交。初始化时按精确非空行比较项目原 `.gitignore` 与模板：已有行保持原位且不重复，只把缺失行追加到文件末尾；重复执行必须保持文件字节不变。写入后若目标是 Git worktree，Onboard 用 `git check-ignore` 验证 `.trellis/spec` / agents / lessons / task 产物确实可追踪，workspace / runtime 确实被忽略；既有 `.trellis/` 等宽泛父目录排除会给出具体来源行并使操作失败，不能以“模板文本已存在”冒充语义有效。模板同时忽略本地运行态和报告产物，报告默认本地留存而非 Git 入库。当前相关片段如下：

既有项目迁移：如果旧模板已经写入 `.claude/`、`CLAUDE.md`、`.agents/` 或 `/AGENTS.md`，`init` / `reset` 的“只追加缺失行”契约不会自动删除这些既有行；确认项目需要追踪对应控制文件与生成集成后，手工删除这些旧行，并用 `git check-ignore` 复核目标路径。

```gitignore
# ---------- Claude ----------
# Keep Trellis-generated agents, commands, skills, hooks, and shared settings versioned.
.claude/projects/
.claude/worktrees/
.claude/settings.local.json

# ---------- OMP ----------
# Keep Trellis-generated agents, commands, skills, and extensions versioned.
.omp/plugins/


# ---------- AI Tools ----------
# Keep project AGENTS.md and shared .agents/skills versioned.
.worktrees/

# ---------- Trellis ----------
# Ignore every direct child, including generated workspace data and an
# intentional workspace symlink; re-include tracked spec / agents / tasks.
.trellis/*
# ---------- Testing -----------
# MCP / browser controller local state
.chrome-devtools-mcp/
.playwright-mcp/

# Playwright runtime artifacts
playwright-report/
test-results/
blob-report/

# Web UI autotest generated run artifacts
tests/e2e/manifest/ui-test-repair-plan.json
tests/api/reports/
tests/unit/reports/
tests/e2e/reports/
tests/e2e/**/screenshots/
tests/e2e/**/videos/
tests/e2e/**/traces/
tests/e2e/**/*.trace.zip

# Maestro runtime artifacts
# Keep maestro/flow/*.yml flows versioned; ignore only local runtime output and reports.
.maestro/cache/
.maestro/tmp/
.maestro/runs/
.maestro/reports/
```

`maestro/flow/*.yml` flow 默认应可入库维护；`tests/api/reports/`、`tests/unit/reports/`、`tests/e2e/reports/` 和 `.maestro/reports/` 只保存正式报告快照、Markdown 汇总和本地 / CI 运行产物，默认不入库。Playwright report、trace、video、screenshot、coverage、JUnit 固定输出和一次性 repair plan 默认不入库。

## onboard / reset 检查范围

`sbtd-workflow-onboard` 的 init / reset / check 逻辑需要覆盖：

- 根安装器在用户选择或传入目标 Agent 平台后、询问 `init` / `reset` 和项目路径前，立即检测对应 CLI：`codex`、`claude`、`kimi` 或 `omp`。已通过 `<command> --version` 则继续；缺失或验证失败时先确保 npm 可用，再用 npm 全局安装官方 `@latest` 包并复验命令。
- 全局 Agent 规则，以及一个或多个项目根目录下的项目级 Agent 模板和 `.gitignore`。
- 15 个 bundled Skills 和 18 个 required external Skills 始终以全局 Skill 目录为目标，不再提供 project/none scope 选择。`init` 对已合法的 Skill 壳（普通目录、普通 `SKILL.md`、frontmatter `name` 匹配）跳过；缺失或身份无效才安装。`reset` 无备份覆盖全部 bundled Skills，并从当前 stable snapshot 强制重装全部 required external Skills。`catalog.json` 是 bundled Skill、external Skill 上游 repo/subpath/alias 和模板源路径的事实源，两个根安装器从 `check` 的 `group=referenced` 获取 external canonical 清单，不再各自维护重复数组。Catalog Schema 与运行时会在执行命令前同时拒绝绝对路径 / `..` 逃逸、错误 source 文件类型、bundled Skill frontmatter 身份不一致、非法 kind/id/target-role 组合和不完整的 HTTPS 仓库地址。

- Trellis CLI 和 GitNexus CLI 强制全局安装，不再提供项目内 CLI 安装；`.trellis/` 与 `.gitnexus/` 状态仍属于各项目。
- `init` / `reset` 对每个项目根目录独立检查 `.trellis/`，执行 `trellis init -u`，并检查 `.trellis/tasks/00-bootstrap-guidelines`；一个项目需要 bootstrap 不会阻止其余项目继续检查。
- `--init-projects` / `-InitProjects` 提供独立的 project-only 模式，只执行逐项目 AGENTS、`.gitignore`、Trellis、Playwright 和 React Bits 检查配置，不检测或安装任何全局 Agent CLI、runtime、tool、Skill 或 MCP。
- `AGENTS.project.md` 只保存 project-only fallback、项目路径和项目级硬边界；正常 `init` / `reset` 由全局 AGENTS + Skills 激活完整路由，public bootstrap / `init-projects` 不单独激活 book-derived 门禁。全局 AGENTS 维护客观触发和 Gate lifecycle，各 reviewer `SKILL.md` 独占状态、输出 schema、修正回路与 stop condition；`trellis-workflow` 只额外保留在全局路由不可见时可自举的最小 objective-trigger fallback，不复制 reviewer 状态。
- GitNexus MCP 手动配置检查；检测到本机 `gitnexus` CLI 路径时，输出并供安装脚本使用 `command = "<detected-gitnexus-path>"`、`args = ["mcp"]` 的配置。
- Chrome DevTools MCP 手动配置检查。
- Playwright MCP 手动配置检查。
- Playwright CLI 按每个项目独立检测和安装引导；只有既有 Playwright/E2E 标记使其适用时才询问。
- Java 17+、Maestro CLI 和 Maestro MCP 检测及安装引导，包含 Maestro MCP 的通用 `command` / `args` / `JAVA_HOME` / `PATH` 配置示例。
- bundled `seo-geo` 和 `web-ui-autotest-generator` Skill 的存在性检查；后者只在需要沉淀 Web UI 回归资产时调用。
- External Skill 默认使用 `--source auto` 从 `sbtd-workflow-onboard/assets/external-skills/stable/` 安装经过 review、精确上游 revision 和 checksum 固定的 stable set，不访问 Git 或网络；显式 `--source stable` 使用相同的确定性来源，只有用户明确选择 `--source upstream` 时才按上游仓库整组 clone、解析和验证当前版本，且失败时不回退。manifest、source subpath 和 license 路径必须被各自声明的根目录包含，拒绝绝对路径、`..` 和 symlink 逃逸。全部 Skill 先暂存和验证，再用临时 rollback backup 事务替换；canonical commit 成功后才删除 legacy 目录。
- stable External Skills 的 `MANIFEST.json` 记录 stable set、精确上游 commit、subpath、tree SHA-256 和许可证/NOTICE。stable 快照保持上游原样且不得手改；只有显式 `promote-external-skills-stable --repository ... --revision <full-sha> --stable-set ... --yes` 才能整组更新。
- mattpocock external Skill 使用上游 canonical 名称。`migrate-external-skills --scope global --yes` 会先对全部受管旧目录做 identity preflight，再以已选 source 事务安装所需 canonical replacement。需要 canonical replacement 的 legacy predecessor 会在成功 transaction commit 后随临时 rollback 目录删除；只有不需要 canonical install 的 legacy-only cleanup（已有有效 replacement，或无 replacement 的 `zoom-out`）才会在删除前保留 migration backup。任何身份冲突均在安装前 fail-closed。正常 `init` / `reset` 仍只做已发现 legacy 的自动迁移。
- bundled Onboard rename migration 在 canonical `sbtd-workflow-onboard/SKILL.md` 校验成功，且 legacy `kuno-workflow-onboard-skills/SKILL.md` 的 frontmatter 仍确认旧身份时才删除旧目录；同名文件、无效 / 不相关目录或身份不匹配会在任何 target 变更前阻断 `init` / `reset` 并保留原内容，删除异常会进入失败报告；`plan` 会报告迁移目标或 identity conflict，`init-projects` 不检查或修改全局 Skill 目录。
- `shadcn`、`ui-ux-pro-max`、`impeccable` 等 referenced external Skill 的存在性检查。
- `ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt` 与其他 external Skills 同为 required：缺失或损坏时不询问、直接从 stable set 补装或修复，失败即阻断。SBTD 统一使用 Onboard stable skill-only provider；`check --json` 输出 `ponytailProvider`，检测到 Codex / OMP 官方 Ponytail plugin 已启用时报告 `provider=conflict`，`check` 失败且 `init` / `reset` 在写 stable copies 前阻断，根安装器同样停止。OMP 只在 `~/.omp` 已存在时执行 `omp plugin list`；缺失目录报告 `not-configured`，不得由只读检查创建。plugin 已安装但禁用只报告不阻断，CLI 不可用报告 `unknown` 而不伪造状态。Onboard 不安装、启用、禁用、信任或卸载官方 plugin；`ponytail-gain` / `ponytail-help` 只属于官方 plugin，不由 Onboard 管理。
- 全局 `AGENTS.md` 模板包含 Code Readability canonical 规则：正确性、安全、运行时特性、明确需求和项目约定优先，可读性与可维护性高于源码行数、文件数和最小 diff。编码任务在适用开发门禁通过后、首次实现编辑前主动调用 `ponytail`；非平凡生产 diff 通过定点 smoke 后、最终 `project-validation` 前主动调用 `ponytail-review`，findings 必须经 Code Readability 裁决，随后执行 Code Readability Review；`ponytail-audit` 与 `ponytail-debt` 只按客观触发条件调用。`project-validation` 不承载可读性规则。
- React Bits tier 选择对每个 React + shadcn/ui 项目独立判断；仍保持项目级、可选并保留 license/registry 前置条件。
- `caveman` 用户级全局交互压缩 Skill 的存在性检查和安装引导。

`scripts/onboard.py` 本身仍只做 MCP 状态检查和配置指引，不直接写 Agent / IDE 的 MCP 设置。仓库根目录的 `install.sh` 和 `install.ps1` 是面向用户的交互式安装入口，会在用户选择单一目标平台并确认 MCP 选项后，调用对应平台命令或写入对应配置文件；其中 GitNexus MCP 优先使用 `check` 阶段检测到的本机 `gitnexus` 可执行文件路径和 `mcp` 参数，未检测到路径时才回退到人工输入：

目标 Agent CLI 的固定映射为：`codex → @openai/codex@latest`、`claude → @anthropic-ai/claude-code@latest`、`kimi → @moonshot-ai/kimi-code@latest`、`oh-my-pi` / `omp → @oh-my-pi/pi-coding-agent@latest`。检测和安装由 `check-agent-cli` / `install-agent-cli` 子命令承接。正常 onboarding 中 npm 同时是强制全局 Trellis/GitNexus 的前置条件；project-only `init-projects` 则完全跳过该全局门禁。

- `codex`：执行 `codex mcp add ...`。
- `claude`：固定执行 `claude mcp add ... --scope user`。
- `kimi`：执行 `kimi mcp add ...`。
- `oh-my-pi` / `omp`：固定写入全局 `~/.omp/agent/mcp.json`。

两个安装脚本的 `source-root` 都直接指向 `sbtd-workflow-onboard` 目录，而不是仓库根目录。默认值是当前执行目录下的 `./sbtd-workflow-onboard`；如果该目录不存在，或缺少 `SKILL.md`、`REFERENCE.md`、`catalog.json`、`catalog.schema.json`、`scripts/onboard.py`、`templates/`、`assets/external-skills/stable/MANIFEST.json`，脚本会直接输出未找到或不完整的 Onboard skill 并结束安装。脚本可以被复制到其他目录独立使用，但必须能通过默认值或显式参数定位完整的 `sbtd-workflow-onboard`：

```bash
./install.sh --source-root /absolute/path/to/sbtd-workflow-onboard --platform codex
```

```powershell
.\install.ps1 -SourceRoot C:\absolute\path\to\sbtd-workflow-onboard -Platform codex
```

正常 onboard 可传入一个或多个逗号分隔的绝对项目根目录；未传时，安装脚本会说明支持多个绝对路径并交互询问：

```bash
./install.sh --projects-root /abs/project-one,/abs/project-two --trellis-user your-name --trellis-platform codex
```

```powershell
.\install.ps1 -ProjectsRoot "C:\work\one,C:\work\two" -TrellisUser your-name -TrellisPlatform codex
```

只初始化项目、不触碰全局安装项：

```bash
bash install.sh --platform codex --init-projects /abs/project-one,/abs/project-two
```

```powershell
.\install.ps1 -Platform codex -InitProjects "C:\work\one,C:\work\two"
```

`caveman`、RTK、Java 和 Maestro 保持原来的条件确认规则；`caveman` 安装本身不会立即启用持久压缩对话模式。同一主要目标达到 3 次中间状态更新、5 个独立工具结果、长任务 / 上下文压力或重复自动化 / review / 验证轮次中的任一条件时，`autoLiteEligible` 单调锁存，下一条普通重复状态必须进入 `auto-lite`；保护区只覆盖当前回复，只有新的主要目标重置。任务级和会话级退出、手动模式与重新启用语义继承全局状态机。15 个 bundled Skills 和 18 个 required external Skills 在正常 `init` / `reset` 中作为必需全局能力处理：缺失 external Skills 默认从 Onboard 内置、经过 review 和 checksum 固定的 stable set 安装，不访问上游；只有显式 `--source upstream` 才获取并验证当前上游，任何失败都直接报错。bundled Skills 写入全局目录，两类 Skill 均不再询问 project scope。`sbtd-workflow-onboard` canonical Skill 写入且 frontmatter 校验通过后，旧 `kuno-workflow-onboard-skills` 目录会被删除，不保留 alias 或兼容副本。stable 自身完整性错误，以及目标侧 staging、权限、磁盘、commit 或 rollback 错误都直接失败，不存在自动 source fallback。`init` 对已合法 bundled / required external Skill 壳跳过；`reset` 无备份覆盖全部 bundled Skills，并从当前 stable snapshot 强制重装全部 required external Skills。External Skill 显式替换采用临时事务 rollback，完整恢复后删除临时备份，恢复不完整时保留并返回 rollback 路径；legacy migration 只处理旧名称。

逐项目 `init` / `reset` / `init-projects` 完成模板写入后会继续做 Trellis setup：每个缺少 `.trellis/` 的 root 都执行同一 username 和已解析平台 flags 的 `trellis init -u <username> --<flag> ... --yes --skip-existing`；`--platform codex|claude|kimi` 在未给 `--trellis-platform` 时提供默认 flag，`plan --json` 的 `trellisInit.command` 会写出完整命令。随后分别检查 `.trellis/tasks/00-bootstrap-guidelines`。汇总状态按 `failed > blocked > needs-user > bootstrap-required > success > skipped` 处理；命中的每个项目都必须按 `trellis-workflow` 完成 bootstrap guideline 后才算 onboarding 完成。
