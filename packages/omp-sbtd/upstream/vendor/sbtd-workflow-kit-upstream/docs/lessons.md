# Lessons

本文件是本仓库唯一的 lessons 必读短入口，只保留阅读协议、topic 路由和少量高频提醒。每次操作前先读本文件；主题明确时按路由读取命中的 topic，需要按错误信息、工具名、tags 或 lesson ID 定位时查[完整索引](lessons/index.md)，不默认通读整个库。

完整 lesson 只保存在 `docs/lessons/topics/<topic>.md`；归档后只保存在索引指向的 `docs/lessons/archive/YYYY-QN.md`，不保留两份正文。索引负责检索，入口摘要不替代详情。

历史 lesson（含下方作者摘要）的旧路径、版本、测试数量和配置状态按记录当时理解，不授权恢复已退役流程。现行仓库定位与根 `.gitignore` 契约见 [README「Repository」](../README.md#repository)；版本检查与自动化权限见[版本化 automation prompt](../prompts/automations/sbtd-workflow-tools-version-check.md)。发生差异时按当前规则执行，保留历史详情。

写入新 lesson 时：

1. 先判断是否属于长期 lesson；普通任务总结和临时调研不要写入。
2. 按 `lessons-record` 核验身份，在对应 topic 的本人块保存完整记录，并更新索引；保留历史 ID、锚点与其他作者块。
3. 只有跨任务高频、缺失会反复导致错误的预防措施才补一句话摘要，并链接到具体详情；普通路径、版本和库存信息查当前配置，不在入口另存一份。

## 高频摘要

- 区分配置摘录源与真实项目模板：[仓库边界](lessons/topics/repository-workflow.md#lesson-20260701-config-excerpt-repo-boundary-config-excerpt-repo-boundary)。
- 区分普通修改、显式 `sync` 与 `update`：[维护与同步边界](lessons/topics/repository-workflow.md#lesson-20260718-automation-sync-trigger-separation-separate-prompt-maintenance-from-live-sync)。
- 编写一次性验证前查命中的经验，按目标文件职责与实际 schema 校验：[验证职责](lessons/topics/validation-scripts.md#lesson-20260701-structured-validation-by-file-role-structured-validation-by-file-role)。
- 报告产物存在不等于测试通过：[报告与结论分离](lessons/topics/bdd-e2e-reports.md#lesson-20260701-e2e-report-artifact-status-separation-e2e-report-artifact-status-separation)。

## Topic 路由

| topic | read_when | detail |
|---|---|---|
| repository-workflow | 仓库定位、版本检查、同步、AGENTS / ENTRYPOINT / README、安装与迁移、清理授权、历史 Trellis / GitNexus 问题 | [repository-workflow](lessons/topics/repository-workflow.md) |
| validation-scripts | 一次性脚本、Markdown / schema 解析、Shell / Python / Node、测试取证、编辑恢复、路径与事务验证 | [validation-scripts](lessons/topics/validation-scripts.md) |
| bdd-e2e-reports | BDD 语言、Web UI 资产、Playwright / Maestro 报告、E2E 状态与 revision 证据 | [bdd-e2e-reports](lessons/topics/bdd-e2e-reports.md) |

## 作者高频摘要

以下作者块保持原文；相关完整记录由[索引](lessons/index.md)按作者 ID 与关键词定位，历史数量和状态不作为当前验收基线。

<!-- lessons:640:start -->
- 作为通过证据的测试 / 验证命令优先无管道；若使用管道，按当前 shell 立即保存并返回 runner 状态（Bash `PIPESTATUS[0]` / zsh `pipestatus[1]`），仅打印退出码不够；后台 job 须等最终 summary。
- 编辑长行模板前先在私有临时目录保存完整文件快照；备用 Git patch 必须相对记录的 base commit 包含 staged + unstaged 差异，并另存未追踪内容。截断恢复只改工作树，不动用户暂存区；不得用仅含 unstaged 的 patch 从 HEAD 重建。
- 批量安装的身份校验必须覆盖整个替换集合，不能仅凭核心文件授权覆盖 sibling；外层组合安装结果时直接保留结构化 transaction 与恢复路径，不通过丢弃 stdout 维持 JSON 整洁。
- 全量验证（267 tests + 450 subtests）时长波动大：窗口 ≥600s 或按文件拆分；timeout 一律充足窗口重跑取证并记录最后进度点，不得直接当 pass/fail 证据，原因未证实前不归因为“环境问题”。
- CLI 参数或入口改动必须用真实解释器验证合法输入与拒绝输入；源码中删掉名字不等于运行时拒绝，负例非零也可能只是语法／编码错误。平台实测范围分别报告，不以 macOS PowerShell 代替 Windows。
<!-- lessons:640:end -->

<!-- lessons:kuno:start -->
- 取证命令不得在非正常 `umask` 下代表最终测试；权限相关失败须按正常 `umask` 分类复跑，关闭环境变量后仍要完整 suite。
- targeted rerun 只证明该失败项修复；最终交付必须单独证明同一修正环境下的 full suite。
- 审查建议先核对既有契约并走真实消费链；失败断言不自动证明产品违约或授权策略变更，夹具不能替被测行为完成工作。
- 明确未写入回执优先于同字节现场和更旧 checkpoint；intent 对应的未知现场须阻断恢复。
- 全量若封存当前安装包，先完成源码编辑、compileall及其他缓存写入再冻结运行；“检查命令”不等于只读，不能在验证期间改写封存输入。
<!-- lessons:kuno:end -->
