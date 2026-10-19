# Graft 0.22.0 本机切换验收

## 授权与范围

用户先授权「切换mcp,path和stamp」，随后在已披露现用 launcher 固定0.21.1、共享包更新会影响新连接的前提下，明确选择「对齐 Onboard 后继续」。沿用 strict；TaskStore 已重开同一任务并保留此前源码验收完成事件。

本轮目标仅为：

- `~/.agent/skills/sbtd-workflow-onboard` 的完整受管包。
- 普通 Codex `~/.codex/config.toml` 与 OMP `~/.omp/agent/mcp.json` 中受管 `sbtd-graft`。
- `~/.zshenv`、`~/.zshrc` 中各一处既有 Graft PATH。
- 当前 640-skills worktree 的 `graft/` 结构图及 stamp。

不包含其他账户／配置域、其他项目、其他 Skills／全局 AGENTS、hooks opt-in、live automation、旧环境清理、备份销毁、提交／推送／发布。原会话不强停，不声明已经重载。

## 前置与实际切换

1. 现用 installed launcher 对新 CLI 实际返回 `runtime-version`、exit2。没有仅修改 entry 绕过旧守卫；用户补充授权后才对齐安装包。
2. Onboard 使用受管 upgrade，只有1个 replace、32个 keep。完整包的9个差异文件为 REFERENCE、SKILL、三份 Graft 资产、graft_runtime、onboard_contracts、sbtd_graft_entry、此前已验收的 sbtd_migration_files 修复。
3. 源工作目录的4个未跟踪 `.DS_Store` 不属于版本化交付。原文件保留；创建版本化文件的完整不可变安装基线，逐文件核对当前已验收字节，重新 plan 后执行。没有手工拼接新旧 launcher 模块。
4. Onboard apply 和 verify 完成后再计划／切换 Codex；随后以实际新 Codex 状态重新计划／切换 OMP，避免共享 provider 在同批内变化。
5. 两处 zsh PATH 各只替换一个旧前缀，其他字节与备份相同。
6. 从已安装的新 Onboard 调用受管 `build_project_graph`，生成当前仓库0.22.0 stamp 与结构图，没有手改 stamp。

最终绑定保持：

- launcher：已安装 Onboard 的 `scripts/sbtd_graft_entry.py`，不是仓库源码或暂存执行器。
- CLI：`~/.local/share/sbtd/runtime/graft-0.22.0-managed/lib/node_modules/@nanonets/graft/dist/cli.js`。
- Python：既有受管 Python；保留 `-E -s`；Node 路径不变。
- MCP 无固定 cwd 或 `--root`，仍按新连接实际 cwd 锁定仓库。
- stamp：version `0.22.0`、hosts `["agents"]`、global/mcp/hooks/statusline 均 false。

## 验证结果

| 层级 | 实际执行与结果 | 不代表 |
| --- | --- | --- |
| 包磁盘 | 受管 upgrade apply complete；final verify aligned | 发布、签名迁移或其他 Skills 升级 |
| MCP磁盘 | Codex、OMP各1个 replace；最终均 aligned；其他配置语义相同 | 原GUI或旧会话重载 |
| PATH | zsh `-c`、`-ic`、`-lic` 均选择新前缀，版本0.22.0 | 已运行 shell 的环境被反向修改 |
| stamp/图 | installed helper build exit0；validate_project 通过 | deep概念图生成 |
| 新MCP进程 | 按两份真实配置的 command/args/env 分别启动，握手均为 graft0.22.0、六工具；file API命中本仓 install_graft；结构 freshness为OK；退出0 | Codex/OMP主进程已重新读取配置 |
| 无自维护副作用 | 两次最终MCP smoke前后图和配置字节不变 | 任意并发写入隔离 |
| 原件 | 原始四文件hash与备份一致；三个native backup_ref与实际快照一致；旧图备份匹配 | 已执行回滚演练 |
| 恢复计划 | OMP、Codex、Onboard只读 recovery plan均 planned、exit0 | 已恢复现场 |

`graft_check_freshness` 的概念层提示 `NO GRAPH`，与结构层 `graph check: OK` 同时返回；本轮未启用 `--deep`、LLM 或 cloud，不把概念层缺失隐去。

旧0.21.1前缀和最初中断的0.22.0目录保留。报告／备份批次的私有路径没有进入新结构图节点。

## 独立复核与 Gate

- DDIA：confirmed。先固定可恢复原件，再按包 → provider → consumer → PATH／图的顺序切换。跨资源不是原子事务；版本不匹配时保持 fail-closed，不承诺无中断切换。
- Legacy safety：characterized。旧 launcher拒绝新包的真实前置证据保留；新包源码已有完整strict验收，现场以native plan/receipt/verify验证。
- Refactoring：not-needed，本轮未改生产源码，只部署已验收完整包并精确改配置。
- 独立代码复核 `PinCodeReview`：当前批次计划、回执、canonical绑定及运行证据无剩余 findings；ready for approved scoped cutover。
- 独立安全／恢复复核 `PinSecurityReview`：findings=[]。确认完整原件、checkpoint／write intent、三份 actionable restore 计划及保留executor；未执行真实回滚。
- Release Readiness：ready，限定已授权本机切换及记录的恢复证据；两位复核者均未运行测试或读取完整敏感配置。没有以此执行tag、Release或全机升级。

## 原始报告、失败保留与恢复

本地批次：`reports/cutover-20261015-195645/`。每条执行命令的原生JSON和同stem中文汇总保留。`vault/` 存放原件、不可变plan、receipt、恢复计划及 before/after 映射；`baseline/` 保留实际执行基线，供恢复验证，不是live launcher。

- Onboard计划：`vault/onboard-plan-versioned.json`；成功receipt以 `ab8043fe…` 开头。
- Codex计划：`vault/codex-plan.json`；成功receipt以 `481140ed…` 开头。
- OMP有效计划：`vault/omp-plan-resolved.json`；成功receipt以 `64ce6126…` 开头。早先 blocked 的 `omp-plan.json` 未执行。
- 图备份：`vault/graph-before/`；四份配置／PATH原件映射：`vault/live-originals.json`；最终状态：`vault/live-after.json`。
- 恢复计划：`vault/omp-recovery-plan.json`、`codex-recovery-plan.json`、`onboard-recovery-plan.json`。

如需回滚，须先停止依赖这次切换的新操作并重新核对现场／原件，先恢复 OMP consumer，再恢复 Codex provider，保留新恢复执行器直至宿主恢复完成；随后配套恢复 Onboard、两份PATH和旧图/stamp，使旧launcher、旧CLI及旧stamp一致。三份 native recovery plan 不包含 shell 与图的恢复，不能漏掉这两类原件。不能只还原entry或stamp，也不能把原件同名文件当作有效备份。当前只验证原件和只读恢复计划，没有执行恢复；后续恢复或销毁仍需单独授权。必须保留整个私有批次，而不只是最终receipt。

保留的中间失败：首次计划把 `-I` 用于直接脚本入口，sibling导入失败，改为受支持的 `-E -s -B`；首次OMP scope的config_home误用agent层，被解析器拒绝，改为`.omp`后重新计划。两者未产生对应目标写入，没有放宽生产守卫。

## 文档与剩余边界

- README.md、README.zh.md：无需改，本轮只是执行既有部署能力，无新产品用法。
- CHANGELOG.md、CHANGELOG.zh.md：无需再增release note，本地切换不是另一项源码能力，也未发布v2.0.2。
- 版本化automation prompt及其live定义：均未改，本轮没有版本检查／sync授权。
- 本批只更新当前仓库stamp。其他仓库如果仍是0.21.1 stamp，使用新全局MCP启动时会安全拒绝，需要各自明确授权后受管重建；未遍历它们。
- 现有宿主会话可能仍持有旧MCP定义或进程。新进程证明与原会话重载不同；需要用户重新连接／重启会话，本轮不代为强停。
- Evidence Source: developer-local；Source Revision: dirty；Evidence Publication: local-only；rtk: skipped-for-report。没有重复全仓测试：部署的版本化实现字节与此前验收一致，本轮增加的是磁盘、shell、真实配置MCP及恢复证据。
