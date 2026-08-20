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
- 根因：双引号不会阻止 shell 对反引号执行命令替换；包含 `` `code` ``、`$` 等 shell 元字符的 Markdown 搜索模式不能直接放在双引号里。
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
