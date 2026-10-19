# Validation And Script Lessons

本 topic 保存一次性验证脚本、Markdown 解析、shell quoting、Node / Python 脚本和结构化断言相关 lessons。

## LESSON-20260701-skill-enumeration-filter-directories: Skill Enumeration Filter Directories

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, skills, filesystem
- 适用场景：枚举 `skills/**/SKILL.md` 或写验证脚本
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：验证脚本枚举 Skill 时必须过滤目录
- 问题：每日版本检查的 Node 验证脚本直接遍历 `skills/` 并拼接 `SKILL.md`，把 macOS 产生的 `.DS_Store` 当成目录读取，导致验证脚本自身失败。
- 根因：验证脚本假设 `skills/` 下只有 Skill 目录，没有使用 `Dirent.isDirectory()` 或等价方式过滤文件。
- 修复：重新运行验证时只枚举目录，并保留 `.gitignore` 三行校验，确认 `.DS_Store` 仍被忽略。
- 预防：后续所有针对 `skills/**/SKILL.md` 的自动化检查都应先过滤目录或直接使用 `rg --files skills -g SKILL.md`，不要手写无类型的路径拼接。
- 状态更新（2026-07-16）：Python 验证会生成仓库根或 `tests/` 下的 `__pycache__/`，当前 canonical 契约已调整为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/` 四行；新验证必须使用当前契约，不得改写上方历史修复字段。
- 状态更新（2026-07-18）：fresh-clone 审核确认根 `AGENTS.md` 和 `ENTRYPOINT.md` 必须保持可恢复且由 Git 追踪，当前 `.gitignore` canonical 契约恢复为上述四行；验证除断言精确四行外，还必须直接检查两个控制文件存在于 Git 索引。
- 状态更新（2026-08-20）：当前 `.gitignore` canonical 契约为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/`、`AGENTS.md` 五行。验证应断言 `AGENTS.md` 不在 Git 索引、`ENTRYPOINT.md` 仍在索引；不得读取被忽略的本地 `AGENTS.md` 证明 fresh-clone 可恢复。

## LESSON-20260701-markdown-section-parse-headings: Markdown Section Parse Headings

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, markdown, parsing
- 适用场景：解析 Markdown 章节或表格
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：解析 Markdown 章节不得按裸分隔线切割
- 问题：每日版本检查的 Node 验证脚本用 `split("---")` 截取 `ENTRYPOINT.md` 版本监控章节，误把 Markdown 表格的 `|---|` 分隔行当作章节边界，导致脚本自身误报启用工具为空。
- 根因：验证脚本使用了过宽的字符串分隔，没有按 Markdown 标题层级或行首完整分隔线解析。
- 修复：改为按下一个二级标题截取章节，再解析表格行。
- 预防：后续解析 Markdown 章节时优先按标题层级、行首锚点或 Markdown parser 处理；不要用裸 `---` 这类会命中表格分隔行的字符串切割。

## LESSON-20260701-node-regex-anchor: Node Regex Anchor

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, node, regex
- 适用场景：写 Node / JavaScript 一次性验证脚本
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：Node 验证脚本不要使用非 JS 正则锚点
- 问题：每日版本检查的 Node 验证脚本用 `\z` 作为文末锚点，JavaScript 正则不支持该语义，导致最后一个 Markdown 章节匹配失败；随后用 `^...|$` 搭配 `m` 模式时，`$` 又匹配到行尾，导致章节被截成空段。
- 根因：把其他正则方言中的文末锚点直接移植到 Node.js，且没有意识到 JavaScript 正则 `m` 模式会改变 `$` 的匹配语义。
- 修复：校验脚本改用行扫描和标题索引截取 Markdown 章节，避免依赖跨行 lookahead 的文末锚点。
- 预防：后续一次性 Node 校验脚本只使用 JavaScript 正则明确支持的语法；复杂章节解析优先用行扫描或标题索引，避免跨语言正则习惯迁移。

## LESSON-20260701-rtk-wrapper-native-recheck: RTK Wrapper Native Recheck

- 日期：历史记录迁移，原始日期未记录
- 标签：rtk, shell, validation
- 适用场景：`rtk` 输出疑似包装器参数解析错误
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：rtk 包装器失败后必须原生命令复验
- 问题：每日版本检查中，`rtk git diff -- AGENTS.md ...` 会把 pathspec 误解析成 revision，`rtk test -d` / `rtk test -f` 也会输出 shell usage 并失败，容易被误读成仓库文件或目录状态异常。
- 根因：`rtk` 包装器对部分带 `--` pathspec 或 POSIX `test` 参数的命令解析不等价于原生命令；失败来自包装器参数处理，而不一定来自 Git 或文件系统事实。
- 修复：保持先尝试 `rtk` 的仓库规则；当 `rtk` 输出明显是包装器/参数解析错误时，立即用对应原生命令复验同一事实，并在最终输出说明 fallback。
- 预防：后续验证脚本和自动化总结中，要区分“rtk 包装器失败”和“底层验证失败”；只有原生命令或结构化脚本也失败时，才判定验证事实未通过。

## LESSON-20260704-rtk-report-producing-test-gate: RTK Report Producing Test Gate

- 日期：2026-07-04
- 标签：rtk, validation, reports, tests
- 适用场景：unit test、API / integration test、Playwright Web E2E、Maestro Mobile / Hybrid E2E 需要生成 coverage、JUnit、HTML、JSON、trace、raw report 或 Markdown 汇总时
- 严重级别：high
- 来源：用户指出 `rtk` 命中缓存后，测试执行内容可能没有写入落地报告文件，原生命令才能正常生成报告。
- 问题：默认用 `rtk` 包裹测试命令时，Agent 可能只看到缓存 / 回放 / 压缩后的终端结果，却没有刷新本轮需要保留的报告文件，最终把缺失或陈旧报告误判为已生成。
- 根因：旧规则把 `rtk` 作为所有 shell 命令的默认前缀，没有区分“只需要终端事实”的检查命令与“必须产生文件副作用”的报告型测试命令。
- 修复：对 unit / API / Playwright / Maestro 报告型测试先评估是否使用 `rtk`；需要报告落地时优先原生命令或项目明确的 no-cache / report-safe 命令。若已用 `rtk`，必须校验报告文件存在、mtime / size、本轮命令内容匹配；缺失、陈旧、空文件、内容不匹配或输出显示 cache hit / replay / skipped 写入时，立即原生命令重跑。
- 预防：最终输出或 check summary 必须记录 `rtk`: `used` / `skipped-for-report` / `fallback-native` / `not-available` / `not-needed`，不能只凭 `rtk` 输出声明测试通过或报告生成。

## LESSON-20260701-markdown-backtick-shell-quoting: Markdown Backtick Shell Quoting

- 日期：历史记录迁移，原始日期未记录
- 标签：shell, markdown, rg
- 适用场景：搜索含反引号、`$`、`!` 等 Markdown 文本
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：Markdown 反引号搜索必须安全引用
- 问题：验证模板是否残留旧文案时，`rg` 搜索模式包含 Markdown inline code 反引号，命令用双引号包裹后被 zsh 当成命令替换，出现 `command not found`，导致验证命令自身失败。
- 根因：双引号不会阻止 shell 对反引号执行命令替换；包含 ``code``、`$` 等 shell 元字符的 Markdown 搜索模式不能直接放在双引号里。
- 修复：改用单引号包裹 `rg` 搜索模式，并用结构化 Node 断言补充验证，区分“命令引用失败”和“模板内容失败”。
- 预防：后续验证 Markdown 文档中含反引号、`$`、`!` 等 shell 元字符的文本时，优先使用单引号、转义字符或 Node 结构化检查；最终报告中说明失败来自命令写法还是内容事实。

## LESSON-20260709-bash32-nounset-empty-array: Bash 3.2 Nounset Empty Array

- 日期：2026-07-09
- 标签：bash, shell, installer, validation
- 适用场景：修改 macOS 可直接执行的 Bash installer、`set -u` 脚本或数组参数转发
- 严重级别：high
- 来源：用户在另一台 Mac 的 skills 仓库直接执行 `bash install.sh` 时，preflight 阶段报 `TRELLIS_PLATFORMS[@]: unbound variable` 和 `COMMON_ARGS_OUT[@]: unbound variable`。
- 问题：`install.sh` 使用 `set -euo pipefail`，在没有传入 Trellis platform 或 common args 为空的路径上直接展开 `"${array[@]}"`，导致 macOS 默认 Bash 3.2 将已声明但为空的数组当作未绑定变量并中止脚本。
- 根因：开发验证只覆盖了较新 Bash 或非空数组路径，忽略了 macOS Bash 3.2 在 `nounset` 下的空数组兼容性差异。
- 修复：对可能为空的数组拷贝、循环、函数参数转发和 append 操作使用 `${array[@]+"${array[@]}"}` 兼容展开；对 NUL 参数输出增加非空计数保护，避免空数组时生成空参数。
- 预防：后续修改 `install.sh` 或其他面向 macOS 的 Bash installer 时，必须至少运行 `/bin/bash -uc 'a=(); for x in "${a[@]}"; do :; done'` 确认本机 Bash 行为，并用 Bash 3.2 执行无可选数组参数的 dry-run 路径。空数组展开不能只在当前新版 Bash 上验证。

## LESSON-20260719-bash-prompt-stdin-redirection: Interactive Bash Prompts Need a Dedicated Input FD

- 日期：2026-07-19
- 标签：bash, installer, stdin, process-substitution, interactive, powershell
- 适用场景：交互式 Bash 脚本在 `while` / pipeline / process substitution 内调用 `read`，或出现无阻塞重复的 invalid choice / yes-no 提示
- 严重级别：high
- 来源：执行 `bash install.sh --init-projects /Users/lusonglin/github/KPi,/Users/lusonglin/github/keyboy-play`，选择 Codex 并确认安装项目 AGENTS 后，脚本无限输出 `Invalid choice.`。
- 问题：逐项目检查触发 React Bits 选择时，用户无法输入有效选项；循环高速输出错误，必须外部终止进程。
- 根因：`configure_project_optional_items` 使用 `while ... done < <(project_check_lines)`，整个循环的 fd 0 被项目清单 process substitution 替换。循环内 `select_one` 从项目清单读取下一行而不是从用户终端读取；清单耗尽后 `read` 持续返回 EOF，而选择循环没有检查返回值，遂永久输出 `Invalid choice.`。
- 修复：脚本启动时用专用 fd 保存原始 stdin，所有交互式 `read` 显式从该 fd 读取；每个交互读取都检查 EOF 并明确失败退出。新增真实 prompt 顺序回归测试，并以两个实际项目的 PTY dry-run 验证 `1`、`y`、React Bits `1`、最终 `y` 可正常完成。PowerShell 版本通过内存对象 `foreach` 和 `Read-Host` 遍历，不存在同一 stdin 重定向。
- 预防：交互函数不得隐式依赖调用方当前 fd 0；凡是在重定向循环、pipeline 或 process substitution 内调用提示函数，都必须使用启动时保留的输入 fd 或先把数据读入内存，并处理 EOF。测试必须让数据流和用户输入流同时存在，不能只覆盖空项目清单或全部 `--skip-*` 的非交互路径。

## LESSON-20260701-validation-script-check-lessons: Validation Script Check Lessons

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, lessons, scripts
- 适用场景：写一次性验证脚本前
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：一次性验证脚本必须对照已读 Lessons
- 问题：每日版本检查已经读取 `docs/lessons.md`，但结构化 Node 验证脚本仍重复使用了 JavaScript 不支持的 `\z` 文末锚点，导致验证脚本自身失败。
- 根因：读取 lessons 后没有把其中的脚本编写禁忌转化为当次验证脚本约束，只在事后依赖 rerun 纠正。
- 修复：改用行扫描和标题索引截取 Markdown 章节，避免跨语言正则锚点；重新执行结构化验证确认内容事实通过。
- 预防：后续编写一次性验证脚本前，先把已读 lessons 中与脚本、shell quoting、Markdown 解析相关的条目作为 checklist 核对；不要重复使用已明确记录为失败原因的写法。

## LESSON-20260701-node-one-liner-complexity: Node One Liner Complexity

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, node, scripts
- 适用场景：Node one-liner 逻辑较复杂时
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：复杂 Node one-liner 校验必须降低语法风险
- 问题：每日版本检查的结构化 Node 校验脚本写成过长 one-liner，手工嵌套 `for` / `if` 块时多写了一个闭合大括号，导致验证脚本先于内容检查失败。
- 根因：为了避免临时文件，把多段 Markdown 解析、表格解析和断言逻辑压缩进单条 `node -e`，缺少缩进和局部函数边界，语法错误不易肉眼发现。
- 修复：将脚本拆成更小的函数和更少的嵌套，重新运行结构化校验，区分“验证脚本语法失败”和“仓库内容事实失败”。
- 预防：后续一次性 Node 校验脚本应优先使用短函数、行扫描和早返回；如果逻辑超过几段断言，先拆成多个命令或清晰的多行脚本字符串，不要把复杂控制流压成不可审查的一行。

## LESSON-20260701-python-fstring-one-liner: Python FString One Liner

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, python, scripts
- 适用场景：Python one-liner 包含 f-string、嵌套引号或分支
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：Python one-liner 校验避免嵌套 f-string 转义
- 问题：一次性 Python 结构化断言脚本在 shell `python -c` 中嵌套 f-string、引号和反斜杠转义，导致脚本先发生 `SyntaxError`，没有执行到内容校验。
- 根因：为了把多分支断言压成一条命令，在 f-string 表达式里继续嵌套带转义的字符串字面量，触发 Python 对 f-string 表达式的语法限制。
- 修复：将嵌套表达式拆成普通变量赋值和字符串拼接，重新运行结构化断言并确认内容事实通过。
- 预防：后续 Python one-liner 校验只保留简单表达式；涉及条件分支、嵌套引号或多段断言时，先拆成局部变量和多行脚本字符串，不要在 f-string 表达式内继续写转义字符串。

## LESSON-20260701-importlib-dataclass-sys-modules: Importlib Dataclass Sys Modules

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, python, importlib
- 适用场景：动态导入含 dataclass / 运行时反射的模块
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：importlib 动态导入 dataclass 模块需先注册 sys.modules
- 问题：一次性 Python 校验脚本用 `importlib.util.module_from_spec()` 动态导入包含 `@dataclass` 的模块时，没有先写入 `sys.modules`，导致 dataclasses 处理类型注解时取不到模块命名空间并抛出 `AttributeError`。
- 根因：动态导入流程只创建了模块对象并执行 `exec_module()`，但没有模拟正常 import 机制中的 `sys.modules[name] = module` 注册步骤。
- 修复：在 `spec.loader.exec_module(module)` 前先执行 `sys.modules[name] = module`，重新运行外部 Skill 覆盖安装断言并确认通过。
- 预防：后续用 `importlib` 在一次性校验中加载带 dataclass、枚举注册、运行时注解或模块级反射的文件时，先注册到 `sys.modules`；如果只验证 CLI 行为，优先通过子进程调用脚本入口，减少动态导入差异。

## LESSON-20260701-skill-markdown-frontmatter: Skill Markdown Frontmatter

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, markdown, skills
- 适用场景：校验 `SKILL.md` Markdown 结构
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：Skill Markdown 校验必须允许 frontmatter
- 问题：每日版本检查的结构化 Node 校验脚本要求所有 Markdown 文件必须以 H1 开头，误判带 YAML frontmatter 的 `SKILL.md` 不可读。
- 根因：验证脚本把普通文档规则套用到 Skill 入口文件，忽略了 Skill 文件标准格式通常先包含 `---` frontmatter，再进入正文标题。
- 修复：将 Markdown 可读性校验改为同时接受 H1 开头和 YAML frontmatter 开头，并继续检查非空内容与代码围栏配对。
- 预防：后续校验 `SKILL.md` 时先识别文件类型；对 Skill 入口校验 frontmatter + 正文结构，不要强制套用普通项目文档的 H1 起始规则。

## LESSON-20260701-ast-literal-eval-expression-config: AST Literal Eval Expression Config

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, python, ast
- 适用场景：解析 Python 配置常量或表达式
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：ast.literal_eval 不适合解析含调用表达式的配置常量
- 问题：结构化校验 `onboard.py` 中 `SKILL_SOURCES` 时，用 `ast.literal_eval()` 直接解析包含 `TEMPLATE_DIR / "skills" / ...` 表达式的字典，验证脚本先抛出 `ValueError`，没有执行到内容一致性检查。
- 根因：`ast.literal_eval()` 只接受纯 Python 字面量；当字典值包含变量名、路径拼接、函数调用或其他表达式时，应改用 AST 遍历提取 key，或用源码文本 / 运行时导入的方式校验。
- 修复：改为遍历 AST 字典键，只提取字符串 key 来确认 Skill 名称登记情况，再用文件系统和 manifest 做交叉校验。
- 预防：后续一次性 Python 结构化校验中，只有目标表达式确认为纯字面量时才使用 `ast.literal_eval()`；否则优先做 AST 节点级提取、受控导入或直接文本/JSON 校验。

## LESSON-20260701-structured-validation-by-file-role: Structured Validation By File Role

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, templates, responsibilities
- 适用场景：写跨文件结构化校验
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：结构化校验必须按目标文件职责断言
- 问题：校验 5 个 book-derived Skill 接入时，脚本要求每个 Skill 名称都必须出现在 `project-validation/SKILL.md`，但该文件只负责修改后验证策略，合理范围只需要提到验证后相关的 `book-release-readiness` / `book-ddia-data-design`。
- 根因：一致性校验把“全局登记文件”和“阶段性职责文件”混为一类，过度要求所有目标文件都完整枚举全部 Skill。
- 修复：按文件职责拆分断言：manifest、安装脚本、全局 / 项目 AGENTS、onboard 文档和展示页必须覆盖全部新增 Skill；`trellis-workflow` 覆盖阶段编排；`project-validation` 只校验验证后相关 Skill。
- 预防：后续编写结构化校验时，先定义每个文件的责任面，再为不同责任面设置不同断言，不要用同一个 expected 列表无差别扫描所有文件。

## LESSON-20260701-config-schema-confirmation: Config Schema Confirmation

- 日期：历史记录迁移，原始日期未记录
- 标签：validation, schema, config
- 适用场景：校验 JSON / TOML / YAML 配置前
- 严重级别：medium
- 来源：迁移自 `docs/lessons.md`
- 原始标题：结构化配置校验前必须确认实际 schema
- 问题：校验 `templates/MANIFEST.json` 时，断言脚本凭记忆读取顶层 `files` 字段，但实际 schema 使用 `templates` 字段，导致脚本抛出 `KeyError`，没有执行到内容事实校验。
- 根因：编写一次性结构化校验时没有先读取目标配置的实际结构，把其他 manifest 习惯迁移到了当前仓库。
- 修复：先读取 `templates/MANIFEST.json`，确认顶层字段后，将断言脚本改为读取 `manifest["templates"]`。
- 预防：后续校验 JSON / TOML / YAML 配置前，先查看目标文件 schema 或用受控解析打印顶层 key；不要在未确认字段名时直接写断言。

## LESSON-20260702-chinese-markdown-validation-ignore-code: Chinese Markdown Validation Ignore Code

- 日期：2026-07-02
- 标签：validation, markdown, i18n
- 适用场景：校验中文 Markdown 文档、`UPDATE.md`、运行报告或含大量 URL / 版本号 / 技术标识符的中文说明
- 严重级别：medium
- 来源：每日版本检查自动化校验脚本误判
- 问题：校验 `UPDATE.md` 是否使用中文时，脚本用全文件 CJK 字符数与 Latin 字符数粗略比较。文档虽然正文为中文，但包含大量 GitHub URL、工具名、版本号、release tag、英文 API 名和技术标识符，导致脚本误报 `UPDATE.md does not look primarily Chinese`。
- 根因：中文文档校验把代码、URL、命令、版本号和专有英文标识符当成普通英文正文计数，没有按 Markdown 行角色和字段语义区分自然语言内容与技术标识。
- 修复：将校验改为按章节和段落检查：忽略 URL、代码围栏、inline code-heavy 行和纯技术列表后，要求每个工具章节的说明性正文包含中文，并继续用结构化断言校验标题、区间和字段。
- 预防：后续校验中文 Markdown 时，不要用全文件 CJK/Latin 总量比作为唯一依据；应先过滤 URL、代码、命令、版本号和技术标识符，再按必需章节或说明性字段判断中文可读性。

## LESSON-20260715-html5-validator-capability: HTML5 Validator Capability

- 日期：2026-07-15
- 标签：validation, html, tooling
- 适用场景：校验包含 `header`、`main`、`section`、`article`、`aside`、`footer` 等 HTML5 语义标签的静态说明页
- 严重级别：low
- 来源：P0 Knowledge Ingest / evidence 文档同步验证
- 问题：使用系统 `xmllint --html --noout` 校验 `README.html` 时，legacy HTML parser 把合法的 HTML5 语义标签全部报告为 invalid；随后尝试的 BeautifulSoup/html5lib 和 lxml 在当前环境未安装，额外产生了与页面内容无关的验证失败。
- 根因：执行前没有先确认 validator 的 HTML 标准覆盖范围和 Python 可选依赖可用性，把“XML/legacy HTML 可解析”误当成“HTML5 结构校验”能力。
- 修复：使用 Python 标准库 `html.parser` 完成无第三方依赖的语法读取，并用结构化断言检查新增标题、文本和成对容器；将 `xmllint` 的 unknown-tag 输出归类为工具能力限制，而不是页面损坏。
- 预防：后续校验 HTML5 静态页时，优先使用项目已有 HTML5 validator；没有时先探测依赖，再选择标准库解析 + 结构化断言。不要用 legacy `xmllint --html` 的 HTML5 unknown-tag 报错作为失败结论，也不要在未探测模块前直接依赖 BeautifulSoup、html5lib 或 lxml。

## LESSON-20260717-gate-fixture-preserve-prerequisites: Gate 夹具必须保留前置不变量

- 日期：2026-07-17
- 标签：validation, tests, fixtures, gates
- 适用场景：为多层校验、Schema、报告契约或顺序 Gate 编写负向测试
- 严重级别：medium
- 来源：P1 knowledge-server Smoke 报告缺失回归测试
- 问题：测试想验证“正式报告缺失会返回 blocked summary”，但只把 XML 路径改为不存在的 stem，Markdown 仍保留原 stem，实际先命中了“报告与汇总必须同 stem”的更早 Gate。
- 根因：负向夹具破坏了目标 Gate 之前的前置不变量，使失败信号虽然正确，但没有经过预期代码路径。
- 修复：同时把报告和 Markdown 改成同一个不存在的 stem，保留同 stem 前置条件，再断言缺失报告的 blocked 原因和 worktree 清理。
- 预防：为第 N 层 Gate 写负向测试时，先列出并满足 1..N-1 层不变量；断言具体错误原因，避免“任何失败都算通过”的弱测试。

## LESSON-20260717-shell-example-option-list: 可执行命令示例不得用 Shell 元字符枚举选项

- 日期：2026-07-17
- 标签：docs, shell, commands, validation
- 适用场景：README、HTML、Skill 或运维文档同时说明多个 CLI 子命令或互斥参数
- 严重级别：medium
- 来源：P1.1 未提交变更第二轮 Review
- 问题：README 把 `validate-config`、`decision`、`ingest`、`smoke` 四个可选子命令写成 `validate-config|decision|ingest|smoke` 并放入可复制的 inline code，POSIX Shell 会把 `|` 当成管道而不是“任选其一”。
- 根因：文档为了压缩子命令列表，把说明性元语法混入了看起来可以直接执行的命令片段，没有区分“语法枚举”和“可复制示例”。
- 修复：Markdown 和 HTML 同步改成一条包含必需参数、已经实际执行通过的 `validate-config` 完整示例；其余子命令只在普通正文中列出，并补充回归测试禁止恢复管道形式。
- 预防：代码围栏或 inline code 一旦呈现完整命令，就必须按目标 Shell 的真实语义可执行；互斥子命令使用普通列表、独立完整命令或明确的非 Shell 语法说明，不使用 `|`、`&&`、`;` 等 Shell 元字符充当自然语言分隔符。

## LESSON-20260716-macos-resolved-temp-path: Resolve Expected Paths Before Comparing CLI JSON

- 日期：2026-07-16
- 标签：validation, python, macos, paths, tempfile
- 适用场景：测试 CLI 输出的 canonical / resolved 绝对路径，尤其是 `TemporaryDirectory`、`/var` 和 `/private/var`
- 严重级别：medium
- 来源：SBTD Onboard bundled rename migration 的 plan JSON 回归测试。
- 问题：测试把 CLI 输出的 `/private/var/...` 与未解析的 `TemporaryDirectory` 路径 `/var/...` 直接比较，在 macOS 上失败；两者实际指向同一目录。
- 根因：生产代码对目标路径调用了 `resolve()`，测试期望值只做字符串拼接，忽略 macOS `/var` 到 `/private/var` 的 symlink canonicalization。
- 修复：所有与 resolved CLI JSON 字段比较的期望路径同样调用 `Path.resolve()`；legacy target 列表也逐项使用 canonical path。
- 预防：路径契约测试先确认接口返回 logical path 还是 canonical path；canonical 接口的 actual / expected 必须使用相同解析策略，不用原始字符串掩盖或制造平台差异。

## LESSON-20260716-mutating-subcommand-help: Mutating Subcommand Help Must Be Proven Non-Executing

- 日期：2026-07-16
- 标签：cli, validation, npm, skills, side-effects
- 适用场景：探查第三方 CLI 的安装、删除、迁移或其他可写子命令参数
- 严重级别：medium
- 来源：评估 `npx skills add` 时误以为 `add . --help` 只会显示帮助。
- 问题：`npx skills add . --help` 没有进入帮助模式，而是执行了项目级安装，创建 `.agents/skills/sbtd-workflow-onboard` 和 `skills-lock.json`；虽已立即删除并确认无残留，但污染了评估工作树。
- 根因：把常见 CLI 的 `--help` 语义套用到未验证的第三方子命令，没有先确认 parser 是否在解析 source 后仍识别帮助标志。
- 修复：删除本轮生成的 `.agents/` 与 `skills-lock.json`，使用官方 README / Context7 核对参数，并将真实安装验证放入隔离的临时 `HOME`。
- 预防：第三方可写子命令的参数探查优先读官方文档；如必须执行，先用无副作用的 `--list` / dry-run，或同时隔离 `cwd`、`HOME` 和配置目录。不要假设 `<mutating-command> ... --help` 不会执行其主动作。

## LESSON-20260716-capture-before-teardown: Capture Validation Evidence Before Teardown

- 日期：2026-07-16
- 标签：validation, cleanup, tempfile, npm, skills
- 适用场景：在隔离 `HOME`、临时目录或测试 fixture 中安装、生成并随后删除验证对象
- 严重级别：medium
- 来源：验证 `npx skills add` 全局安装、`npx skills list`、Onboard plan 和 remove 闭环。
- 问题：首轮验证在执行 remove 后才读取 `SKILL.md`、catalog 和脚本存在性，导致安装其实成功但证据字段全部为 false；plan 已成功只能间接证明安装内容曾存在。
- 根因：验证脚本把安装态断言延迟到最终结果对象构造时求值，清理动作已经改变了被观察状态。
- 修复：在 remove / cleanup 前立即快照所有安装态事实，再执行 list、运行时 smoke 和 remove，最后单独断言清理态。
- 预防：有 teardown 的端到端验证必须按 `setup → capture installed state → exercise → capture runtime state → teardown → capture removed state` 排序；不要用 teardown 后的文件系统代替安装态证据。

## LESSON-20260718-reader-metadata-not-raw-body: Reader Metadata Is Not Raw HTTP Body

- 日期：2026-07-18
- 标签：validation, http, read, exact-copy, licensing
- 适用场景：把许可证、校验清单或其他必须逐字一致的远程文本写入仓库
- 严重级别：medium
- 来源：新增 Apache License 2.0 时，直接把 eval `read(URL:raw)` 的返回值写入 `LICENSE`。
- 问题：eval reader 返回值包含 `URL`、`Content-Type`、`Method` 等读取元数据；直接写文件会把包装信息混入要求逐字一致的许可证正文。
- 根因：把用于 Agent 阅读的结构化 reader 输出误当成裸 HTTP response body，且首次写入前没有检查文件头或 checksum。
- 修复：改用 HTTP `fetch(...).text()` 获取原始正文，覆盖 `LICENSE`，再比较本地内容与官方 response body 完全一致并固定 SHA-256 契约。
- 预防：复制必须逐字一致的远程资产时，不直接持久化 reader 展示输出；使用能明确返回 response body 的下载接口，并在完成前校验首行、字节数和可信来源 checksum。

## LESSON-20260718-fixture-baseline-not-current-version: Failed-Mutation Tests Must Capture Their Fixture Baseline

- 日期：2026-07-18
- 标签：validation, tests, fixtures, manifest, promotion, inventory
- 适用场景：验证 manifest promotion / migration 的失败回滚，或检查 catalog 驱动的动态安装集合
- 严重级别：medium
- 来源：迁移 bundled Skill 并推进 stable set 后，promotion 失败测试仍硬编码旧 stable set，external stable 安装测试仍硬编码迁移前 Skill 数量。
- 问题：被测 promotion 正确拒绝了越界 source subpath，external stable 安装也正确安装了 catalog 中全部 Skill，但静态版本和数量断言失败，掩盖了真正要验证的“不变”与“完整集合”契约。
- 根因：测试把当前仓库版本值和派生库存数量当成行为不变量，既没有从本轮临时 fixture 捕获 mutation 前基线，也没有从 catalog 事实源计算预期集合。
- 修复：失败 promotion 与操作前捕获的 `stableSet` 比较；完整安装数量从当前 catalog 的 external entries 推导，不再耦合具体发布编号或历史库存规模。
- 预防：验证失败回滚或 no-mutation 时，expected state 必须来自同一 fixture 的操作前快照；验证 catalog 驱动集合时，从 authoritative catalog 推导预期。只有字面版本或固定数量本身是公共契约时才硬编码。

## LESSON-20260718-readme-dual-format-semantic-assertion: README Dual-format Contracts Must Respect Markup

- 日期：2026-07-18
- 标签：validation, tests, markdown, html, readme
- 适用场景：同一用户可见说明同时维护在 `README.md` 和 `README.html`，并为两份文件编写文本契约测试
- 严重级别：medium
- 来源：为 Onboard `LICENSE` / `NOTICE` 增加双格式文档契约时，测试错误要求原始 Markdown 和 HTML 都包含同一连续路径字符串；HTML 的两个 `<code>` 元素会自然打断该字符串，导致内容正确但测试失败。
- 问题：把渲染后的连续可见语义当成两种源格式都应包含的原始连续文本，会让合法 HTML 标记产生假阴性。
- 根因：契约只定义了显示语义，没有分别定义 Markdown 和 HTML 的源结构，也没有在需要跨标签比较时解析 DOM / text content。
- 修复：为 `README.md` 和 `README.html` 分别断言符合各自格式的完整片段；浏览器验证继续检查渲染后的可见文本。
- 预防：双格式文档契约必须选择其一：按格式分别断言源码结构，或解析 Markdown / HTML 后比较规范化语义；不得要求跨标签内容在原始 HTML 中保持连续。

## LESSON-20260719-shell-env-and-cli-state-names: Shell Environment Contracts Need Separate Internal State

- 日期：2026-07-19
- 标签：shell, installer, environment, cli, color, state
- 适用场景：Shell 脚本同时支持标准环境变量约定和对应 CLI flag
- 严重级别：high
- 来源：`install.sh` 同时用 `NO_COLOR` 保存内部数值状态并检查外部 `NO_COLOR` 环境变量，导致默认交互终端永远禁色。
- 问题：脚本启动时执行 `NO_COLOR=0` 覆盖了外部环境值；`supports_color` 随后同时要求该值数值等于 `0` 且字符串为空，这两个条件不可能同时成立，彩色 banner 分支无法执行。
- 根因：把外部环境契约和内部解析状态复用为同名变量，形成自覆盖和互斥断言。
- 修复：内部 CLI 状态改为 `NO_COLOR_REQUESTED`，标准 `NO_COLOR` 仅作为只读环境输入；用真实 PTY smoke 确认默认终端含 ANSI 色码和大型 `KUNO` 字形。
- 预防：实现 `NO_COLOR`、`CI`、`DEBUG` 等环境约定时，内部 flag 必须使用不同名称；测试同时覆盖默认 TTY、环境变量禁用和 CLI flag 禁用，不能只在 capture pipe 中验证 fallback。

## LESSON-20260719-block-edit-resolved-range: Verify Structural Edit Resolved Ranges Immediately

- 日期：2026-07-19
- 标签：editing, ast, tests, recovery, validation
- 适用场景：使用结构化 block edit 替换类中的单个方法或相邻声明
- 严重级别：high
- 来源：替换 PowerShell banner 契约测试方法时，`SWAP.BLK` 实际解析并消费了该方法之后的整个剩余类体，连带删除三个无关测试。
- 问题：编辑请求的语义范围小于工具实际解析范围；若只继续运行定点测试，删除的无关测试可能不会被发现。
- 根因：对 block resolver 的节点边界做了假设，没有优先使用已知的精确行范围，也没有把工具返回的 `resolved lines` 当成必须立即核对的变更证据。
- 修复：在编辑结果返回后立即识别异常的 56 行消费范围，停止后续实现，读取类尾并恢复三个测试；随后运行完整测试类确认测试数量和契约恢复。
- 预防：替换单个方法且结束行已知时优先使用精确 `SWAP N.=M`；使用 block edit 后必须核对 resolved range 是否只覆盖预期声明，范围异常时先恢复再继续，定点测试之外还要运行所属测试类。

## LESSON-20260719-installer-compatibility-contracts: Installer Compatibility Needs Boundary Fixtures

- 日期：2026-07-19
- 标签：shell, powershell, installer, stdin, encoding, bom, contracts
- 适用场景：跨 Bash / PowerShell 安装器修改输入、编码、文件合并或外部 CLI 落点
- 严重级别：high
- 来源：代码审核发现 Bash 顶层 stdin fd 复制、PowerShell 无 BOM、BOM `.gitignore` 比较、React Bits 已有目标覆盖提示和 automation 路径 allowlist 五类边界缺口。
- 问题：正常交互 happy path 和普通 UTF-8 fixture 均能通过，但 closed stdin、Windows PowerShell 5.1、UTF-8 BOM、已有目标覆盖和版本基线输出路径没有被同一套回归契约覆盖。
- 根因：实现和测试都聚焦主要流程，忽略了脚本解析时机、宿主默认编码、比较视图与写回字节的差异，以及文档化 allowlist / overwrite 语义。
- 修复：参数解析后再安全复制 stdin 并回退只读 `/dev/null`；PowerShell 保存为 UTF-8 BOM；`.gitignore` 比较时只规范化首行 BOM、写回保留原字节；React Bits 检查始终要求目标覆盖；automation allowlist 包含其实际读取的版本基线与输出文件。
- 预防：安装器回归必须包含 closed-stdin 命令、PowerShell 编码字节断言、普通与 BOM 文件幂等 fixture、已有目标覆盖和版本化路径 allowlist；比较规范化不得改变持久化字节。
- 状态更新（2026-07-19）：closed-stdin 回归最初通过显式 `--skip-project-agents` 绕过了 project AGENTS 提示，未证明 `--yes` 本身能够完成非交互执行；后续真实调用因此仍在 `[Y/n]` 提示处失败。非交互 flag 的回归必须保留默认确认和默认拒绝两类提示，验证 `--yes` 对两者都明确回答 Yes，而不是靠额外 skip 参数提前删除提示。

## LESSON-20260831-paginated-edit-source-truncation: Never Rewrite Large Files From Paginated Tool Output

- 日期：2026-08-31
- 标签：editing, tools, pagination, truncation, tests, recovery
- 适用场景：编辑超长 AGENTS / test / script 文件，工具读取结果含 `Showing lines`、省略号或分页 footer
- 严重级别：critical
- 来源：用文本替换工具编辑 1733 行 `test_workflow_contracts.py`
- 问题：编辑工具把分页展示的前 300 行和 `[Showing lines ...]` footer 当作完整文件写回，文件缩短到 370 行并出现 SyntaxError；若只跑新增定点测试，可能把大批既有测试静默删除。
- 根因：在未取得完整、未省略 source 的情况下执行 whole-file / fuzzy replacement，且没有把返回后的行数、footer 搜索和语法解析作为即时 gate。
- 修复：从 Git 恢复未预期改动；后续大文件仅使用行锚定小补丁，或使用带唯一 anchor / match-count 断言的一次性脚本，并在执行后立即删除脚本。
- 预防：任何读取含分页 / elision 标记的文件都不得作为整文件写回来源。每次大文件编辑后立即运行 `wc -l`、语法解析、`git diff --stat` 和 footer 搜索；行数异常先恢复，再运行所属完整测试文件而非只跑定点测试。
<!-- lessons:640:start -->
- 状态更新（2026-09-07）：同类截断在 475 行文件上复现，且插入的新内容完全正确、只有文件尾部 174 行被静默删除，因此“替换看起来成功”不构成完整性证据。判定必须看 `git diff --numstat` 的删除列：纯插入型编辑的删除数应与实际替换行数一致，出现意料外的大额删除立即 `git checkout --` 恢复。
- 状态更新（2026-09-07）：同一会话中，字符串匹配类编辑 / 搜索工具在含 967 字符长行的 UTF-8 文件上无法命中已确认存在的 CJK 文本。对确认存在的内容反复匹配失败时不要继续重试或放宽匹配，改用行锚定的一次性脚本（读取后断言目标行前缀 / 后缀再插入），并在执行后核对 numstat 与文件尾部。
<!-- lessons:640:end -->

<!-- lessons:640:start -->

## LESSON-20260914-640-piped-backgrounded-test-exit-code: Piped and Backgrounded Runs Hide the Real Exit Code

- 日期：2026-09-14
- 标签：rtk, validation, shell, exit-code, background
- 适用场景：测试 / 验证命令经管道（如 `| tail`）或后台 job 执行，并据其输出或退出码判定通过
- 严重级别：high
- 来源：i-have-adhd opt-in 集成任务的全量 unittest 验证
- 问题：`rtk python3 -m unittest discover -s tests 2>&1 | tail -6` 没有 `pipefail`，shell 只返回 `tail` 的 0；命令被后台化后也只能看到进行中的局部输出。两种形态下“测试通过”都没有真实 exit code 支撑。
- 根因：把管道末端命令的退出码和后台交付的过程输出当成了 runner 的最终判定；`rtk` 层还可能叠加缓存 / 回放风险（见 LESSON-20260704-rtk-report-producing-test-gate）。
- 修复：权威验证优先使用无管道原生命令并取得真实 exit code。确需管道时，在独立脚本或子 shell 内运行完整管道，紧接着保存 runner 状态，中间不得插入其他命令：Bash 用 `rc=${PIPESTATUS[0]}`，zsh 用 `rc=${pipestatus[1]}`；随后可打印该值，但必须以 `exit "$rc"` 返回它（函数中用 `return "$rc"`）。只执行 `echo` 会把整个命令的退出状态重新变为 0。后台 job 必须等待最终 summary，不得把中途快照当结论。
- 预防：作为通过证据的命令必须保持完整退出码链路：优先无管道；需要管道时明确使用 `pipefail`，或按当前 shell 保存并返回 runner 状态。Bash 的 `PIPESTATUS[0]` 与 zsh 的 `pipestatus[1]` 不可互换；报告文件仍需核验本轮写入，后台化只用于等待。

## LESSON-20260914-640-assertion-survives-line-wrapping: Text Assertions Must Survive Source Line Wrapping

- 日期：2026-09-14
- 标签：validation, tests, assertions, text-contract
- 适用场景：对源码注释、文档或模板写 `assertIn` 类文本包含断言
- 严重级别：medium
- 来源：i-have-adhd opt-in 集成任务的契约测试首跑失败
- 问题：断言 `"update BOTH the pinned commit and this hash"` 失败——该短语在源码注释里被换行打断为两行，文本包含永远不可能命中。
- 根因：按“读起来通顺的整句”写断言，没有核对目标字符串在源文件中是单行存在；断行位置是作者可自由重排的非契约细节。
- 修复：把断言改为同一物理行内的短串（`"pinned commit and this hash; changing only one"`）；结构化事实（常量形态、正则、解析结果）优先于自然语言整句。
- 预防：写文本断言前先 grep 目标文件确认候选串单行存在；长句拆成各自单行独立的多个短断言；行宽重排不应能让契约测试变红。

## LESSON-20260914-640-str-replace-tail-truncation-recovery: String-Replace Edits Can Truncate Long-Line Templates; Recover From Pre-Edit Byte Snapshot

- 日期：2026-09-14
- 标签：editing, truncation, templates, utf-8, git, recovery
- 适用场景：用字符串替换类编辑工具修改含超长 CJK 行的大 Markdown 模板（如 `AGENTS.global.md`）
- 严重级别：high
- 来源：i-have-adhd 集成 review 修复：两次 `StrReplace` 命中正确，但文件从 569 行静默截断到 301 行，`## Skills 调用规则` 之后全部丢失；reviewer 复查才发现
- 问题：`LESSON-20260831-paginated-edit-source-truncation` 描述的尾部截断第三次复现；替换命中且内容正确不构成完整性证据，定点测试也不覆盖模板尾部
- 根因：编辑工具在含近千字符 UTF-8 长行的文件上写回不完整；未在每次编辑后立即核对 `wc -l` / `git diff --numstat`
- 修复：优先从编辑前保存的逐字节文件快照恢复工作树文件，保留文件模式且不修改 Git 索引，再用锚定编辑重放本轮目标修改。只有已保存完整基线差异时才使用备用方案：在隔离目录重建记录的 base commit 文件，再应用相对该 commit 保存的完整 staged + unstaged patch；不得把仅有 `git diff -- <path>` 的补丁套到 HEAD 上。未追踪文件必须从文件快照恢复；缺少完整快照时停止，不猜测或丢弃原有工作。
- 预防：编辑前用 `mktemp -d` 或 `tempfile.mkdtemp` 创建私有备份目录，保存文件当前全部字节及模式，确认成功后再编辑；符号链接应保存链接身份而非追读目标。备份覆盖编辑、校验和恢复全过程，仅在验证成功且不再需要恢复后清理，失败时保留并报告路径。可另外保存 `git diff --binary HEAD -- <path>` 及对应 base commit SHA，但该补丁不包含未追踪文件，不能替代原始快照。禁止覆盖固定 `/tmp/<name>.patch`。编辑后立即核对行数、删除范围与文件尾部，异常时只恢复工作树，保持用户原有暂存区不变。

## LESSON-20260915-640-install-family-and-reporting: Bulk Install Identity And Recovery Reports

- 日期：2026-09-15
- 标签：onboard, caveman, identity, rollback, json, reporting
- 适用场景：按一个核心文件识别并批量替换多个目录，或在外层 CLI 中组合安装结果
- 严重级别：high
- 来源：本仓库安装器审查与回归修复
- 问题：核心文件属于已知旧版时，自定义 sibling 仍可能被批量覆盖；外层为保持单份 JSON 而丢弃子安装器 stdout，会同时丢弃失败恢复路径。
- 根因：身份验证的范围小于实际替换范围；事务结果只存在于展示副作用中，组合调用方拿不到结构化恢复信息。
- 修复：校验所有受管目录及 payload 指纹，未知或自定义 family 停止覆盖，staged source 与替换前目标都要检查；安装结果直接返回结构化数据，由独立展示函数渲染，外层成功和失败响应都保留 transaction 与恢复路径。
- 预防：回归使用已知核心与自定义 sibling 的混合状态，以及外层 init/reset 的真实回滚失败路径；检查文件保留和可读取的备份，不用只回显 mock 消息的测试证明恢复契约。

## LESSON-20260916-640-full-suite-timeout-window: Full-Suite Validation Windows Must Cover Duration Variance

- 日期：2026-09-16
- 标签：validation, pytest, timeout, full-suite
- 适用场景：本仓全量 pytest（267 tests + 450 subtests）作为修改后验证证据，或出现验证超时
- 严重级别：medium
- 来源：impeccable stable 修复后全量复跑，首次在 300s 窗口超时（停在 47% 中段，非失败测试），充足窗口下 343s 全绿
- 问题：按基线时长设定固定验证窗口会偶发超时；若据超时直接判定验证失败，属证据误用
- 根因：本仓全量 suite 时长波动大（125s → 343s），波动原因未证实（疑环境争抢，无 tight loop 可复现），按单次基线时长设定窗口必然偶发不足
- 修复：验证窗口按 ≥600s 设定或按文件拆分跑；任何 timeout 一律以充足窗口重跑取证后再下结论
- 预防：全量验证先估算当前实际时长再上窗口上限；timeout 必须记录最后进度点与真实 runner 输出，不得作为 pass/fail 证据；时长波动原因未证实前不得归因为“环境问题”

## LESSON-20260918-640-powershell-runtime-binding: PowerShell Parameter Contracts Need Runtime Proof

- 日期：2026-09-18
- 标签：powershell, cli, parameter-binding, validation, positive-control
- 适用场景：删除 PowerShell 参数、区分公开选项与内部执行模式，或以源码断言验证安装器
- 严重级别：high
- 来源：P1-02 的真实 macOS PowerShell 入口验证
- 问题：删除参数声明后，普通 `param` 仍接受未知参数；源码中不存在旧名字并不证明入口拒绝它。实际 project-only 执行还暴露了把内部 `init-projects` 赋给只允许 `init/reset` 的 `Action` 参数所触发的校验错误。
- 根因：把声明文本当作参数绑定行为，以及复用公开参数承载更宽的内部状态。
- 修复：使用高级参数绑定拒绝未知参数，公开 `Action` 与内部执行模式分离；保留实际 PowerShell 帮助正向控制、未知参数负例和 project-only 安装回归。
- 预防：测试真实解释器和入口，不用源码字符串／调用顺序断言代替行为。负例非零必须伴随有效输入成功，否则语法错误也会造成假阳性；macOS PowerShell 证据不能冒充 Windows 验收。

## LESSON-20260918-640-editing-boundary-and-bom: Editing Tools Can Preserve Hidden Structure

- 日期：2026-09-18
- 标签：editing, ast, bom, recovery, validation
- 适用场景：用块编辑修改类内方法，或修改已有 UTF-8 BOM 的 PowerShell 文件首行
- 严重级别：high
- 来源：P1-02 的测试区块恢复与 PowerShell 正向控制失败
- 问题：单方法块替换实际吞掉同类后续方法；首行替换中手工携带 BOM 又被工具保留一次，导致双 BOM 和解析失败。仅看新增正文正确或负例退出非零都未能发现问题。
- 根因：未把工具返回的实际替换范围、隐藏编码和可执行正向控制作为独立证据。
- 修复：从原始写入内容恢复相邻三个测试方法，之后使用已读取的精确范围；首行正文不重复加入工具维护的 BOM，验证实际字节仅一个 BOM，再重跑正常帮助与失败参数。
- 预防：沿用既有完整快照及 resolved-range 规则；编辑类内单方法优先精确结束行。编码类修改验证实际 bytes 和原生解释器；出现 read/edit hash 不一致时重新读取并保留错误证据，不放宽匹配或猜测丢失内容。

## LESSON-20260918-640-parallel-validation-ownership: Parallel Workers Do Not Own Final Validation

- 日期：2026-09-18
- 标签：agents, parallel, validation, evidence, ownership
- 适用场景：多个 worker 修改互相依赖的生产代码、调用者或测试
- 严重级别：medium
- 来源：P1-02 两个 worker 在明确禁止在途验证的批次中仍自行报告定点运行
- 问题：worker 自报通过容易被误当作完整集成或最终版本证据，且在途运行可能读到其他写入者尚未完成的文件。
- 根因：作者局部检查与主线程拥有的统一验证职责没有在结果验收时严格区分。
- 修复：不采纳这些自报结果作为 gate；等写入切面完成后由主线程生成原生定点、影响范围、全量和实际 CLI 报告。
- 预防：任务明确全部验证归属、稳定接口和文件所有权；收回结果时检查是否越界执行。违反分工的输出只保留为过程事实，不能替代固定 revision、完整范围和可回读报告。

## LESSON-20260918-640-preflight-before-side-effects: Preflight Must Precede Every Caller Side Effect

- 日期：2026-09-18
- 标签：installer, preflight, side-effects, cli, validation
- 适用场景：共享写入器有安全前置检查，但外围安装器还会执行可选安装、全局工具或配置写入
- 严重级别：high
- 来源：P1-02 独立审查 P1 与真实 Bash 复现
- 问题：Python 最终写入器拒绝不安全 `.gitignore`，但 root installer 已调用可选 React Bits 安装；最终退出 2 不能证明此前零写入。
- 根因：外围 `check-projects` 只检查部分状态，完整 scaffold guard 太晚，且没有覆盖所有写入调用者。
- 修复：共享完整只读项目前置判定；两安装器在全局安装、MCP 与可选项目安装之前执行，Python 写入前再次复验，并一致传递 `--skip-project-agents` 的已选目标范围。
- 预防：覆盖每个 caller 的 normal/project-only 分支，使用受控副作用 tracer 与文件保全断言证明冲突时没有 mutation；保留合法正向控制，不能只断言最终非零或只检查核心 writer。

## LESSON-20260918-640-executable-identity-binding: Bind CLI Identity to the Executed Target

- tags：cli, security, identity, shim, validation, installer
- 适用：第三方 CLI 检测或安装后校验需要先证明命令属于指定包，且检测不能执行未知命令。
- 现象：仅凭 wrapper 内出现包名以及邻近 package.json，会把写有包名注释的任意脚本当作官方 CLI；仅限制目标落在包目录内也会接受其他文件。
- 根因：文本包含和目录相邻不是执行目标绑定；安装后校验若只检查元数据，再直接运行 PATH/prefix 命令，会绕过检测层的身份保护。
- 修复：解析后命令必须绑定受支持包的实际 CLI 路径，检测与安装后校验复用同一判定；未证明的 shim 不执行。平台适配与平台通过证据独立，不为便利放宽身份判断。
- 验证：两个真实临时可执行文件红测均错误返回 available；修复后包含 post-install 路径的三个 marker 非执行回归通过。RTK/global check 同轮另证完整隔离 HOME 零持久写入；不把第三方查询子命令名称当成只读证明。
- 预防：正向控制覆盖真实包 CLI，反例覆盖包名注释 wrapper、包内错误目标和安装后旧 binary；报告只允许受管安装入口，不向用户展示绕过安全门的原始包管理命令。

## LESSON-20260919-640-state-event-integrity: Parse and Preserve the Complete Event History

- tags：markdown, state, history, yaml, recovery, validation
- 适用：Markdown正文承担权威状态事件，且原文允许代码/HTML示例或历史补录。
- 现象：手写围栏/标题扫描把示例当历史、漏掉无外侧pipe的数据行，或将新事件放入未闭合围栏；只读第一张表还会漏掉同一状态节的后续表。旧完成补录追加在归档事件后，则会形成倒序/断链。
- 根因：把文本命中、前缀可解析和单行schema通过当作完整文档与事件顺序证明。
- 修复：使用声明依赖的CommonMark token与显式table规则识别顶层完整区段；拒绝多表歧义；候选必须回读全部旧事件和本次事件。有据旧完成在已有metadata事件前补录，写前再验证完整状态/时间链。
- 验证：真实文件红/绿覆盖未闭合围栏、缩进/伪closer/HTML示例、可选pipe、多表以及known/null旧完成的archive→reopen→继续工作；原文与历史均保留。不能只断言保存命令退出0。
- 预防：parser依赖实际安装、缺依赖零写入与完整安装副本同轮证明；解析器不渲染或联网，失败不得退回不安全手写扫描。

## LESSON-20260919-640-private-tree-protection: Prove Privacy for the Whole Transfer Tree

- tags：gitignore, privacy, filesystem, transfer, originals, validation
- 适用：把整个任务目录复制到私有候选区、本地归档区或原件保留区。
- 现象：源task.md及目标task.md均被忽略，附带二进制等文件却可能Git可见；只查源文件也不能证明新archive路径受保护。
- 根因：把单个文件的保护结论扩张为整棵目录的保护；忽略权限必须对实际写入范围成立。
- 修复：共同保护门核对整个私有父目录的Git排除语义、全部tracked状态和具体路径；不能证明全部后代仍私有时，copy/rename前拒绝并请求窄保护授权。
- 验证：metadata-only ignore与源目录受保护但archive目标未保护的真实Git反例均零发布；不能用命名为“private”的目录或一个探针返回码代替逐范围证明。
- 预防：授权scope也按实际逻辑任务闭集核对，路径嵌套不代表另一个task.md的所有权；保留原件不等于授权发布或删除。

## LESSON-20260919-640-handoff-verified-snapshot: Bind Overwrites to the Verified Snapshot

- tags：handoff, ownership, atomic-write, snapshot, validation
- 适用：先解析持久快照确认身份，再按预期旧内容原子覆盖的写入路径。
- 现象：身份校验读取一次、稍后又读取一次作为expected bytes时，用户在两次读取之间的新内容会被当成已授权旧版本，随后被覆盖。
- 根因：权限/身份判断与乐观并发比较绑定到不同版本，而不是同一次读取的原始字节。
- 修复：一次读取同时返回已验证结构和原始bytes，写入沿用这些bytes；变化时拒绝，不能重新读取后默许新内容。
- 验证：真实文件故障注入在身份读取后替换内容，修前覆盖、修后保留用户版本并拒绝；不以mock回声代替文件保全断言。
- 同轮相关边界：有意义内容比较排除生成时间时，不能在生成正文重复该时间；提醒窗口要排除未来时间，并同时核对快照与当前有效任务的root/branch/path，不让旧快照变成当前模式/状态来源。
- 限制：该修复关闭可检测的版本混用，不将单writer原子替换描述为对不合作进程的完整CAS或跨文件事务。

## LESSON-20260919-640-identity-absence-and-phase-results: Prove Absence and Retain Phase Results

- tags：identity, git, worktree, preflight, authorization, partial-results
- 适用：仅在身份真正缺失时首次建立，或把只读计划、脚手架与逐项目写入组合成一次初始化。
- 现象：损坏的.git仍会产生“not a git repository”；固定拒绝全部保护会让已确认nonGit初始化在脚手架写后失败；身份异常若只保留计划，机器调用者看不到已发生写入，目录中途消失还可能直接traceback。
- 根因：把无法识别当作已证明不存在；未区分原计划授权与后来新增需求；异常边界只包方法正文而遗漏对象构造，结果没有逐阶段累积。
- 修复：Git失败后核对本级/祖先marker，未知保持blocked；只有原计划needsProtection严格为true才转发已确认窄保护；先保存实际operationResults，逐项目覆盖构造/执行错误，失败报告写后状态及此前完成项。
- 验证：损坏.git与真实nonGit CLI红绿；真实文件原子link失败后保留脚手架并回读单份JSON；预检时移走root及批次首项成功、次项root缺失均结构化报告。影响范围129项通过；这不是跨项目事务或完整Windows证明。
- 预防：正向控制验证非Git首次建立仍可完成，负例验证未知不是缺失；结果与权限均绑定实际阶段，不从最终非零推断零副作用。既有ignore判定和保护helper部分步骤遗漏的P2保留独立findings，不借本修复扩修。

## LESSON-20260919-640-migration-native-closure: Prove the Complete Native Migration Closure

- 日期：2026-09-19
- 标签：migration, cli, fixtures, ownership, receipts, evidence
- 适用场景：把冻结交换契约接入真实迁移阶段，或迁移多host旧目录。
- 严重级别：high
- 来源：P1-12真实安装副本、旧固定源码和独立审查红绿。
- 问题：精简fixture遗漏正常旧生成目录与OMP全局路由；局部report/codec通过仍未发现完整verify的未初始化变量，以及“成功退役后不存在”被误判成“漏报保留资产”。私有步骤失败前未执行的共享操作又会使部分回执无法保存。
- 根因：用各层能解析代替真实阶段闭环，把声明操作、已观察结果和仍存在资产视为同一集合。
- 修复：从固定上游源码构造旧布局，真实执行公开phase参数的plan/apply/verify；完整盘点共享host资源；收据只引用观察到的结果，完成仍要求全部依赖；仅以末次成功后态证明的非publication缺席排除保留资产。
- 预防：保留“正常路径真正成功”的原生正向控制与实际部分失败／重试；用修改前源码快照回放新回归，并区分消费者夹具、真实部署和Windows证据。不得为适配夹具静默放宽既定原生schema。

## LESSON-20260919-640-staging-before-publication: Verify Staging Before Publication and Guard Cleanup

- 日期：2026-09-19
- 标签：filesystem, migration, staging, checksum, race, ownership
- 适用场景：文件／目录复制、备份、原子发布与失败后清理本次创建内容。
- 严重级别：high
- 来源：P1-12文件发布与目录回滚的真实故障注入。
- 问题：在目标发布后才检查来源会短暂或永久发布未批准内容；失败清理若只看路径／类型，会删掉同路径已被用户改写的文件。
- 根因：校验与可见性顺序颠倒，创建所有权未绑定实际写入字节；单文件证明被错误扩张到整棵目录。
- 修复：文件先核验实际暂存摘要，目录先构建并核验完整私有stage再发布；记录本次创建条目的实际类型与摘要，清理前捕获并比较，变化时保留并报告。
- 预防：保留源／stage中途变化、目录中后续文件变化、失败清理前同名内容变化的真实文件回归；目录摘要采用完整规范平面条目且包含空目录。不可证明的残留不能凭名字删除，也不能把局部原子性说成多资源事务。

## LESSON-20260919-640-native-effective-pointer: Validate the Effective Native Pointer

- 日期：2026-09-19
- 标签：native, cache, path, coercion, hooks, validation
- 适用场景：通过窄守卫调用第三方原生工具，读取其图／缓存／Markdown指针或配置。
- 严重级别：high
- 来源：P1-04固定Graft路径守卫独立复核及真实文件红绿验证；分隔名640为用户本会话明确提供。
- 问题：验证JSON字段原值仍可被下游字符串强制转换、数组拼接、行号解析、文件名fallback绕过；只校验主要图文件也无法保护其他生成文件的链接写入。
- 根因：守卫校验的路径不是原生消费者最终使用的路径；版本／stamp证明被扩大成数据和文件系统安全证明。
- 修复：按固定版本实际sink证明完整有效指针，拒绝未支持的可强制转换值，核对拼接后路径与fallback；完整生成树拒绝链接／硬链接／特殊文件，workspace索引不授权扫描其他仓。
- 预防：负例覆盖转换链而非仅`../`原串；使用真实native图验证启动拒绝、原件不变，再单独证明正常查询与hook执行。安装返回成功不等于host信任，原生payload调用不等于真实host事件；不声称OS沙箱或并发隔离。

## LESSON-20260921-640-deferred-repair-proof: Revalidate Deferred Findings Against Current Consumers

- 日期：2026-09-21
- 标签：findings, concurrency, dependencies, powershell, validation
- 适用场景：修复历史延期项，尤其涉及第三方共享文件、依赖删除及安装器参数转发。
- 严重级别：high
- 来源：延期项修复；分隔名沿用主 PRD 记录的用户明确授权 640。
- 问题：历史“未使用”依赖后来已有生产消费者；read/compare/replace 无法保护不遵守本地锁的外部 writer；PowerShell 函数内的 `$PSBoundParameters` 不包含脚本入口的绑定。
- 修复：按当前调用方保留 tomlkit、仅删真正不可达迁移分支；经用户确认，对已有可变遥测配置拒绝覆盖，缺失文件采用 no-clobber 创建；从实际 switch 值转发确认，真实解释器验证 true／false。
- 预防：历史 finding 是调查线索，不是删除授权证明。运行报告使用显式隔离解释器及声明依赖；新增测试先证明失败原因来自目标行为，不能把错误入口、遗漏 import、缺依赖或残留空目录造成的失败当作红测。
- Windows 原生补测：关闭 ACL 继承并替换当前用户规则，并不保证已清除新目录中的显式非受信规则。安全诊断只输出 owner 是否匹配、继承开关与规则类别计数，不输出账号／SID；仅对本次创建的目录构造干净 DACL，已有目录只校验不修写。macOS 上跳过的 Windows ACL 用例必须在 Windows runner 实际执行。

  <!-- lessons:640:end -->

<!-- lessons:kuno:start -->
## LESSON-20260930-kuno-umask-sensitive-test-evidence: Umask Sensitive Tests Need Normal Evidence Runs

- 日期：2026-09-30
- 标签：validation, pytest, umask, privacy, filesystem
- 适用场景：取证命令修改 `umask`，或全量测试含目录权限/私有目录拒绝断言
- 严重级别：high
- 来源：graft pin 0.21.1 九行根 ignore 验收前的失败分类
- 问题：取证命令先设 `umask 077`，测试里 `mkdir(mode=0o755)` 实际生成 `0o700`，三项隐私/私有目录测试没有触发预期 `ContractError`，全量出现 4 failed；其中只有根 `.gitignore` 契约是真实工作树失败。
- 根因：测试环境改变了被测文件模式语义，又把环境造成的拒绝缺失与产品行为失败并列统计。
- 修复：在 `umask 022` 下重跑失败项确认三项隐私测试通过，再用相同正常 umask 跑完整 `tests/`，得到 1240 passed、8 skipped；原生 JUnit、stdout/stderr/exit 与同 stem 中文摘要都保留。
- 预防：涉及权限的验证必须先声明并复核 `umask`；不正常的取证环境只能作为失败线索，不能替代正常环境下的小范围复跑与最终全量重跑。

## LESSON-20260930-kuno-contract-rerun-not-full-suite: Contract Rerun Is Not a Full Suite Pass

- 日期：2026-09-30
- 标签：validation, pytest, contracts, evidence, gitignore
- 适用场景：只修改契约测试或根 `.gitignore`，并用单条失败测试重跑作为通过证据
- 严重级别：medium
- 来源：graft pin 0.21.1 根 `.gitignore` 七行/九行验收
- 问题：只修复并复跑 `test_repository_gitignore_keeps_canonical_generated_paths` 可以证明该契约已匹配，但不能把此前 4 failed 的全量结果改记为通过；后来全量又因取证 umask 混入三项环境失败，若只看单条测试会掩盖剩余风险。
- 根因：把 targeted rerun 的结果扩张到整个测试套件，没有区分“失败项已修复”和“最终全量已验证”。
- 修复：先分类旧失败，再在正常环境下运行完整 `tests/`；九行契约调整后得到 1240 passed、8 skipped，并将报告与旧失败记录并列保留。
- 预防：最终交付必须分别报告 targeted rerun 与 final full rerun；只有同一修正环境下的最终全量通过，才能关闭 suite-level 验证缺口。

## LESSON-20261003-kuno-windows-direntry-link-count: Validate Native Link Counts Without Weakening Ownership

- 日期：2026-10-03
- 标签：windows, filesystem, hardlink, stat, validation, subprocess
- 适用场景：用目录项元数据拒绝硬链接，或把 POSIX 子进程测试扩展到原生 Windows。
- 严重级别：high
- 来源：全局会话 Graft MCP 的 Windows CI 原生日志与 Python 标准库契约。
- 问题：测试先因 `select.select` 读取匿名管道而报 `WinError 10038`；修正读取并保全 stderr 后，才显露普通图文件被硬链接守卫误拒绝。
- 根因：Windows 的 `DirEntry.stat()` 将 `st_nlink` 返回为 0，不能用于证明单链接文件；Windows `select()` 也只支持 socket，不能直接迁用 POSIX 管道测试。
- 修复：使用 `os.stat(entry.path, follow_symlinks=False)` 获取真实链接数，继续要求 `st_nlink == 1`、拒绝 symlink/reparse/special；测试采用有超时的后台 `readline`，早退保全退出码与 stderr。
- 预防：先让原生失败报告指出实际守卫，再修正元数据来源；不能把 0 放行为安全值或跳过原生平台测试。正向用普通真实文件，反向用实际硬链接并断言外部原件不变。依据：[Python DirEntry.stat](https://docs.python.org/3.12/library/os.html#os.DirEntry.stat)。

## LESSON-20261003-kuno-git-path-decoding: Decode Paths At The Producing Process Boundary

- 日期：2026-10-03
- 标签：windows, git, unicode, subprocess, encoding, validation
- 适用场景：通过子进程输出的路径证明项目边界，且生产者编码与父进程默认代码页可能不同。
- 严重级别：medium
- 来源：PR #108 原生 Windows 回归；UTF-8 模式关闭、默认 cp1252 时，真实 Git 的 Unicode 仓库被 launcher 以边界不匹配拒绝。
- 问题：`text=True` 没有声明生产者输出编码；ASCII 路径的 Windows CI 通过不能证明中文或重音字符路径可用。
- 根因：Git for Windows 输出 UTF-8，但父 Python 使用默认代码页解码；传给子进程的 `LC_ALL` 不改变父进程解码器。fail-closed 避免串仓，却不能消除合法仓库不可用的缺陷。
- 修复：仅对 Windows Git 探针明确 UTF-8，保留 POSIX 原解码约定；解码错误转换为受控拒绝，路径相等和信任边界检查不变。
- 预防：在真实 Windows 核对默认编码与 UTF-8 模式后测试 Unicode 路径；记录同一场景的原生 red/green，不把其他平台成功或 skip 当作该条件的证明。畸形输出负例检查退出码、无 traceback、无下游启动和无项目副作用，而非锁定错误文案。

## LESSON-20261004-kuno-owned-temp-canonicalization: Canonicalize Owned Temporary Roots Before Nofollow Operations

- 日期：2026-10-04
- 标签：macos, tempfile, nofollow, symlink, isolation, validation
- 适用场景：工具主动创建临时 HOME／宿主夹具，再调用拒绝链接祖先的文件备份或复制原语。
- 严重级别：high
- 来源：Onboard 升级宿主探测的真实失败与修正后回归。
- 问题：安全复制尚未接触 Skill 内容，就因系统临时路径的 `/var` 链接祖先返回 `unsafe-path`，使 Codex／OMP 探测无法获得宿主证据。
- 根因：将本次操作创建的临时目录的逻辑拼写直接传入 nofollow 原语，没有区分系统临时别名与用户提交的源／目标路径。
- 修复：仅在 `mkdtemp` 成功后立即解析本次拥有的临时根，再向下创建和访问夹具。用户提供的 Skills 根、源、目标继续逐级拒绝 symlink／junction，不用 resolve 绕过所有权检查。
- 预防：回归同时覆盖“自有临时父目录通过系统别名访问仍可探测”和“用户提供的链接／越界 sibling 仍拒绝”。真实宿主探测与脚本化协议测试分别报告；不得通过放宽所有路径链接守卫来修正夹具。

## LESSON-20261004-kuno-review-red-is-not-a-contract-defect: Review Red Is Not A Contract Defect

- 日期：2026-10-04
- 标签：review, validation, contracts, fixtures, scope, recovery
- 适用场景：把审查 finding 转成回归测试，尤其涉及安装策略、分阶段执行和中断恢复窗口。
- 严重级别：high
- 来源：Onboard 升级审查复核与冻结原版公开 CLI／已安装副本的真实续作。
- 问题：新写的 red 将缺失 host 的 preserve、源目标包含关系等拟议策略当成既有缺陷；只看已改变的旧 bootstrap 返回 source-stale，又错误扩大为安装后不能重试或恢复。
- 根因：先把审查建议写成预期，未先证明预期属于既有契约，也未沿真正的已安装消费者走完整生命周期。断言失败只能证明实现不同于断言，不能自动证明产品违约。
- 修正：冻结原版执行 plan／apply，再从同基线已安装规范副本完成 retry／recovery；向用户说明策略差异并取得明确选择，撤回未经需要的行为变更，保留原始 red 和更正结论。
- 预防：每条 red 先证明有效输入、前置条件与目标 seam，排除 schema、依赖、夹具顺序或更早门禁造成的失败；正向控制必须实际成功。探测只报告已证明的层级，不顺便增加更广的验证或预置环境，让测试替被测行为完成工作。

## LESSON-20261004-kuno-path-spelling-is-not-identity: Path Spelling Is Not Filesystem Identity

- 日期：2026-10-04
- 标签：filesystem, windows, macos, aliases, cache, preflight, validation
- 适用场景：按路径去重、载荷缓存、选定目标包含判断或批次依赖预检。
- 严重级别：high
- 来源：PR #110 第二轮公开 CLI 与大小写敏感 APFS 隔离回归。
- 问题：大小写不敏感卷的两个拼写绕过重叠保护，replace 可以改写 preserve 所指原件；反向用 normcase 归并，又会丢弃大小写敏感目录中的不同目标并复用错误摘要。继承输入别名漏检会在 provider 写入后才令 consumer 失败。
- 根因：把路径字符串比较、操作系统默认大小写习惯与实际文件系统身份混为一个判定；缓存、授权和祖先关系拥有不同需求。
- 修复：缓存与已绑定选择采用精确拼写，别名归并／祖先包含使用实际非零 device/inode 证据；完整写集与继承输入在目标写入前复核。继续逐组件拒绝链接，不用 resolve 放宽用户路径。
- 预防：同时运行“不同拼写同一对象”和“仅大小写不同的两个对象”正反例；测试应走真实库存与公开消费者，验证原件和写集不变。平台字符串折叠模拟只证明算法边界，必须与原生平台证据分开报告。

## LESSON-20261005-kuno-no-write-evidence-precedence: No-Write Evidence Outranks Matching Bytes

- 日期：2026-10-05
- 标签：recovery, ownership, intent, receipts, concurrency, validation
- 适用场景：由 intent、现场内容和历史回执共同判断中断写入／重试／恢复归属。
- 严重级别：high
- 来源：PR #110 第三轮真实库存、文件写入检查和恢复消费链 red／green。
- 问题：用户在 intent 后创建与 desired 相同的内容，写入检查已记录未写入；重试或旧 pending checkpoint 却仅凭相同字节重新认领，进而生成删除用户文件的恢复步骤。未知 pending 现场也可能被直接跳过后冒报恢复完成。
- 根因：把内容相等当作操作归属，未给明确的未写入证据优先级，也未保留不能归属的现场。
- 修复：最新可信未写入结果不能被旧 checkpoint 或匹配内容覆盖；无明确归属但现场不同于 before 时保持 blocked，保留用户内容与原件。
- 预防：用真实消费者分别覆盖 intent 前后竞态、明确未写入后相同内容、旧 checkpoint、成功写后回执中断与新增缓存；不能只测理想 desired 状态或把 partial／unknown 当作零写入。

## LESSON-20261005-kuno-freeze-sealed-inputs: Freeze All Sealed Inputs During Validation

- 日期：2026-10-05
- 标签：validation, migration, source-snapshot, compileall, concurrency
- 适用场景：测试把当前仓库的完整安装包封存为来源，或全量验证与编辑／编译检查并行。
- 严重级别：high
- 来源：第四轮升级修复的真实followup来源封存检查与隔离目录快照实验。
- 问题：前两次全量期间分别发生源码编辑和compileall，followup夹具出现来源漂移拒绝；仅冻结手写源码不能阻止字节码写入。原错误未保留具体来源路径，不能把推断表述为逐路径已证明的根因。
- 机制：真实followup计划确实把catalog中source为`.`的当前Onboard包作为directory来源封存；目录snapshot不排除缓存。隔离实验直接证明compileall创建字节码会改变同一目录的snapshot，即使Python本身以`-B`启动。
- 修正：编辑、compileall、格式化等写入步骤先完成，再冻结所有封存输入运行完整suite；只读观察器和随后原生全量均通过，保留最初失败与归因边界，不放宽`_original_reference`。
- 预防：验证调度按实际文件写集而非“检查命令”名称分类；唯一controller也不能在自己的全量运行期间改写输入。来源漂移先抓具体路径与前后态；重跑通过不是原错误根因证明。

## LESSON-20261009-kuno-isolate-host-overrides: Isolate Effective Host Paths Before Fixture Writes

- 日期：2026-10-09
- 标签：validation, fixtures, environment, omp, paths, isolation
- 适用场景：隔离 HOME 后运行真实配置写入，或验证默认 Skills／provider 路径选择。
- 严重级别：high
- 来源：现态调和测试的 OMP 路径解析与完整套件环境修正。
- 问题：只替换 HOME 仍会继承绝对 agent/provider 覆盖；反过来，控制器统一设置 AGENT_SKILLS_DIR 会改变测试要覆盖的默认根，实际完整测试因此出现目标目录断言失败。另一次夹具把 PI_CONFIG_DIR 设为绝对路径，被实际解析器正确拒绝。
- 根因：隔离位置与保持被测配置分支是两个约束；环境变量的相对目录名／绝对路径语义不能凭名称猜测。
- 修复：外层去掉无关配置重定向并使用私有 HOME；OMP 夹具按实际解析契约设置 PI_CONFIG_DIR=.omp、临时绝对 agent/provider 路径及默认 profile，在任何部署前断言解析目标属于夹具。取消外层 Skills 根覆盖后，原失败测试通过，未改产品默认值或测试断言。
- 预防：先读取实际优先级与值类型；隔离器不要替所有测试强制选择显式配置分支。可写夹具在调用生产写入器前检查完整实际写集，不能把“环境看起来私有”当作越界不会发生的证明。定点修正之后仍需同环境全量验证。

## LESSON-20261011-kuno-validation-worktrees-outside-task-tree: Keep Validation Checkouts Outside Task Trees

- 日期：2026-10-11
- 标签：validation, worktree, task-state, identity, isolation
- 适用场景：在同一仓库保存冻结源码、覆盖对比 checkout 或完整项目夹具，同时使用 TaskStore 更新任务状态。
- 严重级别：high
- 来源：源码覆盖基线的实际 TaskStore 写入拒绝与任务发现代码核对。
- 问题：把完整 checkout 放在 `.sbtd/tasks/<任务>/` 内后，其复制的共享 `task.md` 被再次发现，状态更新返回 `multiple task records have the same logical ID`；初始模式记录仍在，但新的状态未保存。
- 根因：任务树是逻辑任务发现边界，不是任意临时文件容器。TaskStore 递归读取 `.sbtd/tasks` 与 `ai/tasks` 下的任务正文；Git ignore、独立 worktree 的 `.git` 或目录名带 baseline 都不会将其中的记录排除。
- 修正原则：完整验证 checkout 放在任务树外的受保护位置，例如 `.sbtd/validation/` 或独立私有临时目录。若运行已绑定错误位置，先保全原任务和运行证据，不在执行中移动输入；完成后只移除本次自建 checkout，再用状态 helper 复验。不得改任务 ID、覆盖真实任务或放宽目录发现规则绕过冲突。
- 验证：完成的 checkout 非破坏性移出任务树后，同一 TaskStore 成功保存 checking；源码与失败证据保留，原任务 ID 和发现规则均未改写。
- 预防：创建副本前检查是否携带任务记录及其发现边界；ignore 只证明 Git 保护，不证明任务语义隔离。明确区分会话内阶段与实际保存的状态，保存失败不得声称恢复可靠。

## LESSON-20261012-kuno-native-skip-events: Count Unittest Skip Events Not Only Parent Cases

- 日期：2026-10-12
- 标签：validation, unittest, subtest, skip, reports, ci
- 适用场景：聚合分片报告、比较优化前后执行范围，或由逐例状态生成测试摘要。
- 严重级别：medium
- 来源：Linux CI 取证对原生跳过明细与 `RecordedResult` 的核对。
- 问题：仅统计 `cases[].status == skipped` 得到 Linux 46、Windows 30，但原生报告分别为 48、32；这不是环境新增跳过，而是摘要低报。
- 根因：一个父测试方法的三个 zsh 配置子场景分别调用 skip；`unittest` 保存三个跳过事件，逐例记录却只有一个父例状态。父例数与跳过事件数不是同一口径。
- 修正：只更正派生摘要，原生报告不改；使用 runner 的 `skipped` 和完整 `skip_details`，同时保留父例状态。优化对照逐项比较父例身份／状态与跳过子场景身份／理由，不仅比较一个总数。
- 预防：先确认 runner 对父例、subTest、跳过和失败的记录粒度；不能从 `testsRun` 或父例状态推导原生事件总数。摘要纠正不得改写原件或被表述为补跑通过。

<!-- lessons:kuno:end -->

