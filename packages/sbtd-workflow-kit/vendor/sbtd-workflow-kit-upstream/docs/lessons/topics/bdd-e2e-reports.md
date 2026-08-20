# BDD And E2E Report Lessons

本 topic 保存 BDD 语言、Web UI 测试资产、Playwright / Maestro 报告与 E2E 运行汇总相关 lessons。

## LESSON-20260701-bdd-first-feature-language-gate: BDD First Feature Language Gate

- 日期：历史记录迁移，原始日期未记录
- 标签：bdd, gherkin, validation
- 适用场景：新增首个 `.feature` 或修改 BDD 语言规则
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：BDD 首个 .feature 语言规则必须有写入前和验证门
- 问题：项目规则和 `gherkin-bdd` Skill 已写明“无既有 `.feature` 时，场景文案默认中文、Gherkin 结构关键词用英语”，但实际新建 `.feature` 时仍生成了全英文文案。
- 根因：语言要求只作为描述性规则存在，没有在 `gherkin-bdd` 写入流程、Trellis BDD overlay 和 `project-validation` 检查中形成必须报告和验证的 gate；英文 PRD、design、代码标识符和英语 Gherkin 关键词容易把输出带向全英文。
- 修复：在 `gherkin-bdd` 增加写入前语言决策门，在 `trellis-workflow` 纳入 BDD overlay 阶段要求，并在 `project-validation` 增加 `.feature` 语言一致性检查和 blocked 条件。
- 预防：后续把“默认规则”沉淀为 Skill 时，必须同时覆盖生成前决策、生成后验证和最终输出状态；特别是语言、路径、source of truth 这类容易被上下文漂移覆盖的规则，不能只写成静态说明。

## LESSON-20260701-web-ui-test-assets-path-gate: Web UI Test Assets Path Gate

- 日期：历史记录迁移，原始日期未记录
- 标签：e2e, web-ui, assets
- 适用场景：生成 Web UI 测试资产或 selector audit
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：Web UI 测试资产路径规则必须有参数和验证门
- 问题：项目规则只写明 `web-ui-autotest-generator` 的 JSON 测试资产应整理到 `tests/e2e/manifest/`，但 Skill 示例脚本默认仍会把 `ui-test-manifest.json`、`ui-selector-audit.json`、`ui-test-coverage.json` 输出到项目根目录。
- 根因：只把目标路径写成项目约定，不能保证后续 agent 或人工执行脚本时自动带上 `--out`、`--manifest`、`--selector-audit` 等参数；缺少收尾检查时，根目录残留也可能被误认为完成。
- 修复：在全局 / 项目 AGENTS 模板中固化 `tests/e2e/manifest/` 目标路径和必须加载 `project-validation` 的路由，在 `project-validation` Skill 中固化完整脚本参数，在 `trellis-workflow`、README 和模板 `.gitignore` 中固化路径契约引用、repair plan 忽略路径和根目录残留检查。
- 预防：后续沉淀工具输出路径、source of truth 或测试资产目录时，必须同时覆盖脚本调用参数、生成后存在性检查、根目录 / 旧路径残留检查和最终状态报告；不要只写“推荐放到某目录”。

## LESSON-20260701-e2e-report-artifact-status-separation: E2E Report Artifact Status Separation

- 日期：历史记录迁移，原始日期未记录
- 标签：e2e, reports, playwright
- 适用场景：Playwright / Maestro 运行产生报告产物但测试未全绿
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：E2E 报告文件生成与测试通过状态必须解耦
- 问题：Playwright 已生成 `index.html`、`results.json` 和 `junit.xml` 时，Agent 因最终全量 rerun 未全绿而报告“未生成正式报告”，没有把 HTML 重命名为当时模板要求的 `playwright-report-{feature_file_name}-{stamp}.html`，也没有生成同 stem 的 Markdown 汇总。
- 根因：模板规则把“最终全量通过后才能生成正式报告”和“最后一次运行必须留下命名报告产物”混在一起，导致失败运行已有 runner 产物时仍可能跳过报告归档；同时没有强制 Markdown 汇总使用中文。
- 修复：将 `Final Test Report` 定义为报告文件是否实际生成，将 `Final Full Rerun` 定义为最终全量是否通过；只要 Playwright 或 Maestro 产生原生 runner 报告，就必须生成命名报告和同 stem 中文 Markdown 汇总，失败状态写入汇总而不是跳过文件。
- 预防：后续修改测试报告规则时，必须分别检查“报告产物存在性”和“测试结论状态”，最终输出前用文件存在性校验确认命名报告和同 stem `.md` 都存在；不要把 `Run Summary MD` 标记为 `not-needed` 来绕过失败运行的汇总。

## LESSON-20260701-playwright-summary-html-stem: Playwright Summary HTML Stem

- 日期：历史记录迁移，原始日期未记录
- 标签：e2e, playwright, reports
- 适用场景：生成 Playwright HTML / JSON / JUnit 报告汇总
- 严重级别：high
- 来源：迁移自 `docs/lessons.md`
- 原始标题：Playwright Markdown 汇总不得以 results.json 为 stem
- 问题：在会话 `019f1628-6776-77f0-9d32-3a867477eb96` 中，Playwright 已生成 `tests/e2e/reports/html/index.html`、`tests/e2e/reports/results.json` 和 `junit.xml`，但最终只围绕 `results.json` 生成了 `results.md`，没有把 `index.html` 提升 / 复制为带时间戳的 `playwright-report-*.html`，也没有生成同 stem 的 `playwright-report-*.md`。
- 根因：模板虽然要求“命名 HTML + 同 stem Markdown”，但没有明确排除 `results.json` / `junit.xml` 这类 reporter 产物作为 Markdown stem；Agent 把“同 stem”错误绑定到 JSON reporter，而不是绑定到正式 HTML 报告。
- 修复：在全局 / 项目 AGENTS 模板、`project-validation`、`trellis-workflow` 和 README 中明确 Playwright 的 canonical stem 只能来自命名后的 HTML 报告；`results.md`、`result.md`、`junit.md` 或 `index.md` 不能满足 `Run Summary MD: generated`。
- 预防：以后只要 Playwright 产生 runner 原生报告，收尾 gate 必须检查 `tests/e2e/reports/html/playwright-report-*.html` 与同名 `.md` 成对存在；`results.json`、`junit.xml` 和默认 `index.html` 只能作为辅助产物或复制源，不能替代正式报告。

## LESSON-20260701-playwright-runner-output-dir-separate: Playwright Runner Output Dir Separate

- 日期：2026-07-01
- 标签：e2e, playwright, reports, output-dir
- 适用场景：Playwright HTML 报告被下一轮运行清空，或设计正式报告保存目录
- 严重级别：high
- 来源：会话 `019f1c83-9275-7591-be9c-0f5ea71800ea` 发现 `tests/e2e/reports/html` 中前一轮命名报告被下一轮 Playwright CLI 运行清空
- 问题：当时模板要求把 Playwright 默认 `index.html` 复制为 `playwright-report-{feature}-{timestamp}.html` 和同 stem `.md`，但同时把 Playwright HTML reporter 的 `outputFolder` 和正式命名报告目录都设为 `tests/e2e/reports/html/`。下一轮 Playwright 运行重建 reporter 输出目录时，会把上一轮已经重命名的正式报告一起删除。
- 根因：没有区分 runner 管理的临时输出目录和需要保留的正式报告快照目录；`.gitignore` 忽略 `tests/e2e/reports/` 只表示报告不入库，不会阻止 Playwright 清理自己的 `outputFolder`。
- 修复：将模板默认改为双目录：Playwright HTML reporter 的临时 `outputFolder` 使用 `tests/e2e/reports/.playwright-html-current/`；正式命名报告快照保存到 `tests/e2e/reports/html/`，命名为 `playwright-report-{feature_file_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.html` 和同 stem `.md`，其中 `branch_slug` 使用 `_` 替换 `/`、空格和特殊字符。多轮调试可以保留多份本地快照，最终通过状态仍由 `Final Full Rerun` 表示。
- 预防：后续配置 Playwright 报告时，永远不要把需要保留的 `playwright-report-*` 放进 Playwright 的 `outputFolder`。如果 HTML reporter 目录中存在 `data/`、trace、附件或其他相对资源，复制完整资源目录，或生成 `playwright-report-{feature}-{branch_slug}-{timestamp}/index.html` 形式的完整快照目录，并让 Markdown 汇总指向该入口。

## LESSON-20260704-diagnostic-run-formal-report-gate: Diagnostic Run Formal Report Gate

- 日期：2026-07-04
- 标签：e2e, reports, api, playwright, maestro, validation
- 适用场景：API / Web E2E / Mobile E2E / Hybrid E2E 使用 stdout-only、terminal-only、`--reporter=list` 或未启用 reporter 的诊断命令后收尾
- 严重级别：high
- 来源：会话 `019f2cb3-f162-7521-a072-0dfab44738ae` 中 Playwright focused run 使用 `--reporter=list`，最终先只报告终端测试结果，未生成正式 HTML / Markdown 报告
- 问题：模板虽然要求 Playwright / Maestro / API runner 产生原生报告后必须提升为命名报告，但没有覆盖“正式验证范围内只跑了不产报告的诊断命令”这一缝隙。API 自定义脚本 stdout-only、Playwright `--reporter=list`、Maestro stdout-only 都可能让最终状态停留在终端输出。
- 根因：旧规则以“runner 已产物”为触发条件，缺少“正式验证范围本身必须产出报告或 blocked”的前置 gate；项目级 spec 允许诊断命令时，也没有强制收尾前补正式 reporter。
- 修复：将模板规则改为正式验证范围驱动：diagnostic-only 命令只能算诊断或定点重跑；正式收尾必须补跑启用项目 reporter 的计划范围验证，或把 API stdout / stderr / exit code 捕获并提升为 `api-report-*` raw report，或将 `Final Test Report` / `Run Summary MD` 标记为 `blocked`。
- 预防：以后新增测试报告规则时，必须同时覆盖“已有 runner 产物如何归档”和“正式验证只跑了不产物命令时如何补跑 / 捕获 / blocked”；不要让 terminal output 成为 API、Playwright 或 Maestro 的最终正式报告替代品。

## LESSON-20260717-readonly-mode-mutation-intent-gate: Read-only Mode Mutation Intent Gate

- 日期：2026-07-17
- 标签：bdd, knowledge-ingest, routing, skills
- 适用场景：为 Skill 增加 `read`、inspect、audit、dry-run 等只读模式，或设计多个模式的关键词路由
- 严重级别：high
- 来源：P1 Knowledge Ingest 未提交变更 review；请求 `read the existing feature and add a scenario` 会被只读分支吞掉。
- 问题：Knowledge Ingest 只检查请求包含 `read / 读取` 且不含 `sync / 同步`，没有排除同一句请求里的新增、修改、更新或删除意图，因此“先读再改”会错误进入 `Mutation: none` 模式。
- 根因：模式路由只使用正向触发词，没有同时定义互斥意图和优先级；只读关键词并不等于整个请求都是只读。
- 修复：把 Knowledge Ingest 的入口改为“明确只读意图 + 无变更意图”，并保持 `sync / 同步` 优先；带 read 与 mutation 的混合请求进入普通 BDD 写入流程。
- 预防：以后新增只读模式时，入口必须同时定义正向触发、变更意图排除、与其他模式的优先级，并用混合意图请求做回归测试；不要只按一个关键词切换模式。

## LESSON-20260717-evidence-post-commit-revision-boundary: Evidence Post-commit Revision Boundary

- 日期：2026-07-17
- 标签：evidence, git, pr, validation, ci
- 适用场景：正式测试报告、evidence sidecar / envelope、PR Check 或任何需要证明 PR head 的验证流程
- 严重级别：high
- 来源：P1 Evidence 契约 review；Phase 3.4 commit plan 前生成的证据无法证明随后创建的新 commit SHA。
- 问题：工作流要求在 commit plan 前生成 PR evidence，但创建提交会改变版本身份，导致报告记录的 dirty 工作树或旧 SHA 与最终 PR head 不一致。
- 根因：把“提交前本地验证状态”和“可发布的 PR revision attestation”视为同一生命周期阶段，没有把 Git commit 设为证据版本边界。
- 修复：提交前只记录本地 evidence 状态和发布计划；创建最终提交后、发布或更新 PR Check 前，针对最终 PR head SHA 重新生成或复验，并更新 sidecar / envelope；旧 head 证据失效。CI evidence 同样要求 clean checkout、exact revision，并与 publication 状态分离。
- 预防：凡证据声明精确 revision，工作流必须识别所有会改变 revision identity 的动作（commit、rebase、merge、amend），在这些动作之后设置 refresh / invalidation gate；执行成功不等于证据已发布。
