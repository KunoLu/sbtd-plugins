# CHANGELOG

本文件按 Git tag 记录用户可见变更，最新版本位于最上方。未发布章节在创建对应 tag 后补充发布日期。


## v1.0.13（2026-09-01）

### 修复

- `check --json` 在用户尚无 `~/.omp` 时不再执行 `omp plugin list`，避免只读检查创建 `.omp`；已配置 OMP 时仍完整检测官方 Ponytail plugin 冲突。
- 项目 `.gitignore` 增量合并后使用原生 `git check-ignore` 验证 Trellis 必须追踪 / 必须忽略路径；既有 `.trellis/` 等宽泛父目录排除会给出具体来源行并阻断，而非文本齐全却语义失效的假绿。探针按 NUL 分隔字段读取 git 给出的判定模式，`!.en[v:]` 这类含冒号模式的反向包含不会被反读成“已忽略”。
- `init` / `reset` / `init-projects` 等写入模式的 `--json` 现在只向 stdout 输出单个 JSON 文档。此前会先输出计划文档、再输出 Trellis 报告文档，并夹杂 `Backups:`、`Verification passed.` 等散文，`json.loads` 在每次成功运行上都会失败；计划字段仍留在根层，`mode` 与 `plan` / `check` 位置一致。
- 项目 `.gitignore` 模板补上裸 `.env`。此前只忽略 `.env.local` 和 `.env.*.local`，最常见的 `.env` 反而可被提交。
- External Skill 目录校验和不再把本地生成的 `__pycache__`、`*.pyc` 和工具缓存计入指纹。此前在仓库根运行一次 pytest 会在受管 stable 快照内写入字节码缓存，使后续安装与 promotion 报告校验和不匹配；干净快照的既有 pin 不受影响。
- book 门禁路由行补回被改写丢掉的触发词。`book-ddia-data-design` 的三处路由此前都漏掉规范中的 API 所有权，`book-release-readiness` 把「deployment / rollout / migration / runtime 运维行为」压缩成只剩 deployment，Trellis fallback 还把 background job 写成 job；只命中被丢掉那一段的改动会静默跳过强制 reviewer。全局路由表、project-only fallback 与 Trellis fallback 现在逐条覆盖各 `book-*/SKILL.md` 自己列出的触发词。
- `onboard.py` 每次 `run()` 开始时重置 `UNVERIFIED_CHECKS`。此前该模块级列表跨调用累积，同进程内连续运行多个模式时，后一次会报告自己从未跳过的检查。
- External Skill 目录的拷贝、指纹与比对现在对 `*.pyc` / `*.pyo` 采用一致的排除语义：只排除文件，不排除同名目录。此前名为 `pkg.pyc` 的目录会被拷贝阶段整棵丢弃，其中的文件却仍计入 `treeSha256`，导致拷贝结果与校验和互相矛盾。

### 变更

- 对齐 GitNexus 升级后必须用 CLI 重新 analyze 的索引语义。MCP repository allowlist 未覆盖时 GitNexus MCP 对该仓库不可用，不得当作 MCP 可读；fail-closed 只读不走 MCP 写入；二者均不阻止 CLI 刷新。同时对齐已移除的非功能 group matching 旋钮、`--self-commit` 与 Codex plugin marketplace 不能替代全局 `gitnexus-mcp` 的使用边界。
- 对齐 Codex 可选 MCP 启动宽限期、项目级 plugin catalog 合并，以及 extension 可在模型前检查或替换 MCP tool result 的可用性判断。
- `AGENTS.project.md` 收敛为 project-only fallback、项目路径和硬性边界，删除全局工具 / reviewer 状态的重复副本；正常 `init` / `reset` 与 project-only 的激活边界现在明确区分。
- book-derived 门禁改为单一事实源：全局 AGENTS 维护客观触发与 Gate lifecycle，各 `book-*/SKILL.md` 独占 reviewer 状态、输出 schema、修正回路和 stop condition；Trellis 负责编排，并保留全局路由不可见时可自举的最小 objective-trigger fallback。
- 精简项目 `.gitignore` 中已被 `.trellis/*` 覆盖的运行时重复行，并移除同样冗余的 `.trellis/workspace` 条目；目录 / symlink 语义改由无尾随斜杠的 `.trellis/*` 本身提供，workspace 目录、workspace 内容与顶级 workspace symlink 的忽略结果不变。报告目录仍保持本地忽略，不要求提交 Git。
- 项目 `.gitignore` 的 `output/` 收窄为 `/output/`，只忽略仓库根的构建输出目录；同名嵌套源码目录（例如 `src/output/`）不再被连带忽略。

### 验证

- 新增 `git check-ignore` 语义探针测试、`check --json` 不创建 `~/.omp` 的回归测试，以及 External Skill 目录指纹忽略字节码 / 工具缓存的回归测试；契约测试同步断言 book 门禁的单一事实源归属，并按各 `book-*/SKILL.md` 的规范 bullet 数量逐 token 校验三处路由行的触发词覆盖，新增规范触发词时未同步路由会直接失败。每个 token 只在承载该 gate 谓词的那一行内计命中，因此 `API`、`queue`、`migration` 这类短词不会被文件其他位置的无关提及满足；此前按 bullet 取单个代表短语的写法漏检 `queue / event / stream / job`、`ETL / analytics` 与 `data pipeline`，删掉这三段不会失败。
- 新增含冒号反向包含模式（`!.en[v:]`）必须判定为“未忽略”的回归测试，以及 `init-projects --json` 成功路径解析为单个 JSON 文档的回归测试；两者均以重新引入原缺陷的方式确认会失败。
- 收紧既有断言的判定力：宽泛父目录排除的失败信息按 `文件:行号:模式` 断言具体来源记录，不再用 `.trellis/` 子串（模板自身追加的反向包含行同样含该子串，会放过丢失来源的信息）；`git` 完全不在 PATH 时的降级单独覆盖，与既有 exit 128 桩分属 `run_project_command` 的两条分支；External Skill 缓存回归测试改为枚举全部 6 项排除（`__pycache__`、`.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`*.pyc`、`*.pyo`）并断言拷贝与指纹丢弃同一集合，同时覆盖名为 `pkg.pyc` 的目录必须保留——该拷贝 / 指纹一致性此前无回归测试；reviewer `Status:` 枚举归属改为按成员集合精确比对并禁止委托文档出现任何枚举形声明，此前的子串断言在枚举新增状态或委托文档抄录截断前缀时均不会失败。
- book 门禁 lifecycle 的跨文档断言拆为逐文档独立子测试。此前全部集中在一条断言链上，首个失败即中止，一份文档漂移会掩盖同批其余文档的状态；现在每份文档、每项主题单独判定并单独报告。

## v1.0.12（2026-08-28）

### 变更

- 对齐 Trellis 的空 jsonl 启动门禁：sub-agent-dispatch 平台上 `task.py validate` 对零条 curated 的 `implement.jsonl` / `check.jsonl` 失败，`task.py start` 默认拒绝，只有用户明确要求空上下文启动时才使用 `--allow-empty-context`。
- 对齐 Trellis 的路径变更与整仓移除命令：`task.py rename`、`trellis ablate` / `trellis restore` 纳入 filesystem-safety 与用户确认边界；`[workflow-state:task_error]` 时先修复现有 `task.json`，不得另建任务。
- 对齐 Trellis 的 OMP `prompt_injection.skip_keyword`：生成的 OMP extension 与 Python per-turn hook 使用同一配置关键词跳过当轮 workflow-state 注入，跳过不等于关闭 Trellis 规则。

## v1.0.11（2026-08-27）

### 修复

- `init` / `reset` / `init-projects` 不再把空平台列表交给 `trellis init --yes`（Trellis 会因此默认安装 Claude 和 Cursor）。`--platform codex|claude|kimi` 在未给 `--trellis-platform` 时作为默认 Trellis flag；显式 `--trellis-platform` 覆盖该默认。`oh-my-pi` 仍必须显式给出 `omp` 和/或 `pi`。
- `plan --json` 增加 `trellisInit`，写出将要执行的完整 `trellis init` 命令。
- Trellis 平台 allowlist 对齐 CLI 0.6.15：补上 `kimi`、`grok`、`snow`、`dsh`。

### 验证

- 新增 `test_init_projects_defaults_codex_from_agent_platform`、`test_init_projects_rejects_empty_trellis_flags`、`test_plan_json_includes_resolved_trellis_init_command` 与版本化 `TRELLIS_INIT_PLATFORMS` 契约测试；不解析本机 `trellis init --help`。


## v1.0.10（2026-08-27）


### 变更

- `init` 对已合法的 bundled / required external Skill 壳（普通目录、普通 `SKILL.md`、frontmatter `name` 匹配）跳过，不再无备份覆盖。
- `init` 安装缺失 required external Skill 时不再经 dependency closure 覆盖已合法依赖；公开 `install-external-skills --skills` 仍展开依赖。
- `reset` 仍无备份覆盖全部 bundled Skills，并从当前 stable snapshot 强制重装全部 required external Skills。
- `plan --json` 对 Skill 目录操作输出 `plannedActionOnInit` / `plannedActionOnReset`。
- 全局和项目 `AGENTS.md` 仍备份后覆盖；项目 `.gitignore` 仍只追加模板缺行；`init-projects` 仍不写全局 Skills。

### 验证

- 新增 / 强化 `test_init_skips_valid_bundled_and_external_skill_shells`、`test_reset_overwrites_valid_bundled_and_external_skills` 与 `plan` 的 Skill 写入动作断言。



## v1.0.9（2026-08-27）

### 变更

- `sync` / `同步` 在复制 Onboard 后必须用已同步 `onboard.py install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt --scope global --source auto` 从 stable mirror 安装 required Ponytail Skills，并校验 4 个 `SKILL.md`；不得把 `assets/external-skills/stable/skills/ponytail*` 加为同步表拷贝行。
- 正常 `init` / `reset` 与本仓库 `sync`：若用户主目录已存在 `.omp`（POSIX `~/.omp`，Windows `%USERPROFILE%\.omp`），把同一 `AGENTS.global.md` 备份后覆盖写入 `~/.omp/agent/AGENTS.md`；目录不存在则跳过且不创建 `.omp`。`--global-agents-path` 只覆盖 Codex 目标。
- `--global-agents-path` 指向 `~/.omp/agent/AGENTS.md` 时，`init` / `reset` 只保留一条写入操作，避免对同一文件做两次备份移动。
- External Skills stable set 升级为 `2026-08-27.1`：通过 `promote-external-skills-stable` 从上游 HEAD 刷新 mattpocock/skills、impeccable、ui-ux-pro-max-skill、shadcn-ui 与 ponytail 五个 repository 的原样快照、tree digest 和许可证文件。
- `init` / `reset` 对解析后相同路径的 `file` 操作只保留一条并只备份一次，覆盖 `--global-agents-path` 与项目 `AGENTS.md` 撞上 OMP/Codex 目标的情况。版本检查 prompt 的 OMP AGENTS 校验不再依赖被忽略的根 `AGENTS.md`。

### 验证

- 全量 Python unittest `180` 项全部通过（`python3 -m unittest discover -p 'test_*.py'`，97.278s）：`test_workflow_contracts` 37、`test_onboard_multi_projects` 34、`test_onboard_ponytail_integration` 29、`test_onboard_external_skills` 24、`test_install_sh_agent_cli_flow` 24、`test_knowledge_base_p1` 18、`test_validation_evidence_v2` 9、`test_onboard_agent_cli` 5。
- 本轮新增 OMP AGENTS 路径覆盖已包含在上述 `test_onboard_multi_projects` / `test_workflow_contracts` 中：无 `.omp` 跳过、存在则覆盖写入、`--global-agents-path` 同目标去重、项目根撞 OMP agent 目录只写一次并只备份一次、Windows `USERPROFILE` stub、fresh-clone prompt 不依赖根 `AGENTS.md`。


## v1.0.8（2026-08-26）

### 新增

- Ponytail 4 个核心 Skills（`ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt`）作为 required external Skills 接入：正常 `check` / `init` / `reset` 检查全部 18 个 required external Skills，缺失或损坏时不询问、直接从 vendored stable set 补装或修复，失败即阻断；stable set 升级为 `2026-08-26.1`，固定 Ponytail `v4.9.0` 上游 commit、MIT license、tree SHA-256 与第三方声明。
- `promote-external-skills-stable` 支持首次注册 manifest 中尚不存在的新 repository：新增 `--repo`、`--license` 与可重复 `--license-file SOURCE=STABLE_PATH`，从 catalog 选择与 `--repo` 精确匹配的 external entries 生成 candidate tree；既有 repository 只允许 `--repo` 一致性复核并拒绝 license 参数，杜绝静默改写元数据。
- `check --json` 新增 `ponytailProvider` 只读检测：Codex / OMP 官方 Ponytail plugin 已启用时报告 `provider=conflict`，`check` 失败且 `init` / `reset` 在写 stable copies 前阻断，根安装器同样停止；plugin 已安装但禁用只报告不阻断，CLI 不可用报告 `unknown`。Onboard 不执行任何 plugin 安装、启用、禁用、信任或卸载。
- 全局 `AGENTS.md` 模板新增 `Code Readability` canonical 规则：正确性、安全、运行时特性、明确需求和项目约定优先，可读性与可维护性高于源码行数、文件数和最小 diff；`AGENTS.project.md` 增加最小 fallback，`trellis-workflow` 明确 ponytail → 定点 smoke → ponytail-review → Code Readability Review → 最终 `project-validation` 的主动调用顺序。

### 变更

- 将全局 `AGENTS.md` 模板的 `Code Readability` 章节改为中文标题「代码可读性」，正文与英文版语义对齐；check summary 仍使用 `Code Readability Review` 协议字段。

### 验证

- 全量 Python unittest 160 项全部通过，其中 Ponytail 集成测试 18 项覆盖 catalog/stable manifest、promotion 首次注册与拒绝路径、provider 检测矩阵和 workflow 文档契约。
- 隔离 HOME smoke 8 个场景全部通过：Ponytail 缺失 / 完整 / 部分缺失 / 损坏修复、官方 plugin enabled 冲突阻断（check 与 init 均失败且零写入）、plugin disabled 放行、CLI 不可用报告 `unknown`、reset 前后 Ponytail config 文件字节一致。

## v1.0.7（2026-08-20）

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

