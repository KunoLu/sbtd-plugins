---
schema_version: 1
id: dsh-host-smoke-version-assert
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict、唯一 writer；先 records-only 回填，再最小 smoke 断言修复；仅本地提交，不执行远端或全局配置写入。
status: checking
branch: chore/dsh-host-smoke-version-assert
created_at: '2026-10-23T18:00:01+08:00'
updated_at: '2026-10-23T18:07:11+08:00'
completed_at: null
---
# dsh host register smoke：版本断言与追加式记录回填

## 目标与授权边界

- 编排方整理：授权根 `/workspace/sbtd-plugins-smoke-version`，实际分支与 frontmatter 一致；入口 clean，HEAD / origin/main 为 `67465db93e7c6f1e6f5f43704c1d4c22ae74306d`（#120 squash）。仅本地 conventional commits；不 push、开 PR、comment、tag、publish、merge、触发 workflow 或修改全局配置。
- 编排方整理：提交 1 仅回填 session_compact task/PRD、row G task/PRD 单元格及本 task/index。旧正文和状态事件 append-only；只更新允许的 frontmatter status/updated_at/completed_at；唯一正文替换例外是恢复 row G 状态格丢失的分支/范围前缀。旧 task branch 保留，不重绑定。
- 编排方整理：提交 2 起仅修改 `.github/workflows/scripts/dsh-host-register-smoke.mjs` 的 pin 断言及本记录；workflow 仅必要时调整，本轮设计无需调整。禁止修改 packages/**、任何 README/CHANGELOG、版本、依赖或 lockfile。
- 未完整调用 grill-with-docs：范围、根因、版本真源与锁定 range 已明确，无领域模型歧义；不重新裁决 session_compact D1–D5。
- 沿用既有 task 明示的 TaskStore 全库历史 schema blocker，不重跑、不调用 lifecycle、不写 active/developer/handoff/ignore。本文件是明确要求的共享文档产物，不声称 TaskStore 持久化或自动恢复通过。目标及父路径无 symlink，旧文件 tracked，新 task 不被 ignore；reports 命中 `/ai/tasks/**/reports`。

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、业务术语或模型歧义 | before-dev | not-required |
| book-ddia-data-design | 不改变数据模型、持久协议、跨服务流或所有权；记录沿用既有格式 | before-dev | not-required |
| book-legacy-change-safety | 既有 smoke 对 bump 后包版本误报 | 行为修改前 | planned |
| book-refactoring-pass | 修改既有可执行 smoke 脚本；仅合并重复 range 常量 | 实现前 | planned |
| book-release-readiness | 宿主兼容验证门禁变化；不等于发布包运行时变化 | project-validation 后 | planned |

## 验收与验证计划

- REQUIRED：安装包版本与 `${GITHUB_WORKSPACE}/packages/dsh-sbtd/package.json` 比较；workspace 缺失明确失败。peer 与 engines 分别等于一个命名常量 `>=0.2.0-rc.2 <0.3.0-0`，且二者相等；注释指向 PRD 第 17 行。
- 保持 advisory `DSH_PIN_SMOKE=0` 不执行上述断言，保留宿主版本、注册/schema、V4 pre-step 与 gate 检查；两个 workflow caller 均将脚本复制到临时 cell，不能依赖脚本相对目录找 repo。
- 用 `/tmp` 隔离 cell 复制当前 manifest，执行真实脚本的 assertion 前段；覆盖当前包通过、错误版本/错误 range/peer≠engines 拒绝、workspace 缺失拒绝、advisory 跳过。复制 manifest 仅证明断言逻辑，不冒充真实安装或完整宿主 smoke。
- 执行 `node --check`、Python/PyYAML 解析三份 changed task、追加式保护/row G 单元格/index/范围检查、冲突标记与仅新增行归因过滤、`git diff --check origin/main..HEAD`。记录代码改动的必要三条旧断言删除与 records 删除白名单分别检查，不把代码替换误称 records-only。
- 不重跑已知历史 lint/TaskStore 失败；无包代码变化，不运行包 build/test 或生成 dist。不新增永久测试文件；当前断言脚本本身是永久 smoke，负例以一次性 harness 验证。

## 本地历史核对

- `git log -S'0.1.0-rc.3' -- .github/workflows/scripts/dsh-host-register-smoke.mjs`：字面量来自 #89，`bbe11789eaf89c3eabad1987f1ff3326d58c09c2`，git %cI `2026-09-19T08:50:35+08:00`。
- `git log -1 -- ...`：最后触碰脚本的是 #97，`155982bf1992463556b06126b74aa275fd6839f9`，`2026-10-19T03:17:27+08:00`。#99 `1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831` 的 git %cI 为 `2026-10-19T04:39:44+08:00`，manifest 已 bump `0.2.0-rc.1`，故断言自该 bump 起陈旧。
- `git show b9328fa:packages/dsh-sbtd/package.json`：版本仍 `0.1.0-rc.3`；完整 SHA `b9328fa860375a7cfb18cd29aa82faab4455a89f`，commit 时间 `2026-10-19T03:12:05+08:00`。编排方整理：最后 green dsh-host-compat run `39157727639` 在该提交、PR 分支 `feat/dsh-sbtd-0.2.0-rc.1-pr-c-host`。
- 已读取 `.github/workflows/dsh-host-compat.yml`：仅 workflow_dispatch，PR CI 不执行；REQUIRED 第 134 行 `DSH_PIN_SMOKE: "1"`，advisory 第 214 行 `"0"`；两 caller 第 148/228 行从 GITHUB_WORKSPACE 复制脚本。本地 git 与 workflow 证据已复核；GitHub run 数据按编排方整理，不冒充本轮 gh 调用。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T18:00:01+08:00 | planned | in-progress | 编排方整理：建立 strict chore 共享记录，开始追加回填与最小修复 | 根/分支/基线及路径/ignore/tracked 检查通过；未调用 TaskStore lifecycle |
| 2026-10-23T18:07:11+08:00 | in-progress | checking | 编排方整理：records-only 提交完成，最小断言修复与本地正负例通过，进入独立复核及最终提交检查 | 34a9091c899752c76df416da1a5c6594fb81094f；10/10 assertion-only checks；node --check exit 0；七文件边界/追加保护/YAML/Markdown 检查通过 |

## 提交 1 与 before-dev review

- 提交 1：`34a9091c899752c76df416da1a5c6594fb81094f`，`docs(sbtd): backfill #120 merge and dsh host smoke records`，6 files changed / 101 insertions / 5 deletions；全部为明确授权记录。删除只有两份旧 task 的允许 frontmatter 字段与 row G 单元格整行替换；该单元格逐字仅新增丢失前缀，其他文本不变。
- **Legacy Change Safety Review — Status: characterized；Review mode: normal。** 修改行为是 bump 后 REQUIRED 错误拒绝。当前失败采用编排方 run `39933109206` 的两 cell 证据，不重跑已知失败来确认；本地 Git/源码建立旧字面量与当前 manifest 的冲突。保留 advisory 分支、宿主版本及后续注册/schema/V4/gate 检查。修改前已创建 `/tmp/dsh-host-version-assert-check.mjs`，直接抽取真实脚本断言前段，在独立 cwd/cell 执行；无需生产 seam。安全网是版本、range、单侧不一致、workspace 缺失/空值与 advisory 正负例。
- **Refactoring Review — Status: proceed；Review mode: normal。** 既有脚本结构足够清楚，无需重构；只在 REQUIRED 分支以既有 readJson/join 读取 GITHUB_WORKSPACE 下 manifest，以单一 `DSH_HOST_RANGE` 保留 PRD 第 17 行锁定范围并分别断言 peer/engines，再断言二者相等。没有新 helper、export、依赖或 env override；不触及两个 workflow caller。
- Book Gate Plan 更新：legacy **passed / characterized**；refactoring **passed / proceed**；DDD/DDIA 仍 **not-required**。初始 planned 行保留为历史，具体执行结论见本节。

## 实际验证

- `node /tmp/dsh-host-version-assert-check.mjs /workspace/sbtd-plugins-smoke-version`：`2026-10-23T18:05:48.202+08:00`，exit 0，**10/10 checks 符合预期，251 ms**。3 个接受（当前 checkout、未来版本 checkout、advisory 跳过），7 个拒绝（错误安装版本、两 range 同错、peer 单侧错误、engines 单侧错误、workspace unset、workspace empty、安装包自洽但与 checkout 不同）。
- harness 在 `/tmp` 复制当前 manifest 到 `node_modules/@kunolu/dsh-sbtd`，只提供宿主版本 manifest，运行真实脚本开头至 host imports 前；版本期望来自另一目录的真实 checkout。未来 bump fixture 为 `0.2.0-rc.99` 且路径含空格，证明不依赖 `0.2.0-rc.2` 新字面量或脚本相对目录；负例 stderr 均保留。上述为 **assertion-only / contract-backed manifest fixture**，不是 npm pack/install 或完整宿主 smoke。
- `node --check .github/workflows/scripts/dsh-host-register-smoke.mjs`：exit 0。Python 3.13.5 / PyYAML 6.0.3 / markdown-it 检查：三份 changed task YAML 可解析，schema_version=1、strict、时间 +08:00、旧 branch 不变；记录旧行与顺序保留；row G 精确仅恢复前缀；index 字母序/唯一性/链接目标；Markdown 实际渲染均通过。
- Python 等价检查新增 diff 行的归因禁词：**0 matches**；changed files 冲突标记 **0**。范围为 **7 files**，仅 ai/tasks、docs/prd 和 smoke 脚本。records 删除白名单通过；代码仅替换原有三条断言，不能把这三行合法代码删除混同记录删除。`git diff --check` 及 `git diff --check origin/main` 均 exit 0；提交后 `origin/main..HEAD` 检查尚待最终提交后执行，不预写成功。
- 原生报告及同 stem 中文汇总：ignored `reports/assertion-smoke.json`、`reports/assertion-smoke.md`。Linux / Node v22.20.0 / Git 2.47.3；Evidence Source=developer-local、Source Revision=dirty（基于 `34a9091c899752c76df416da1a5c6594fb81094f` 的脚本修改）、Evidence Publication=local-only；被测脚本 SHA-256 `a2ffd3c89d793277a7b905316cecea7bb6e081c073c68608ca0d6b603215e8b7`。提交后以字节一致性重新绑定证据，不冒充 CI。
- 完整 dsh host smoke **未运行**：本 worktree 未安装 `@deepseek-ai/dsh`，采用明确允许的 manifest-copy 验证，不尝试获取/安装宿主，不虚报 fetch 失败。未运行包 build/test、既有失败 lint、CI、Web/Mobile E2E；不生成 packages 下 dist，不修改任何 package/README/CHANGELOG。后续两个 REQUIRED 宿主 cell 的真实结果仍未知。
- rtk=skipped-for-report（原生 Node 输出）；BDD=skipped（内部 CI 断言，无插件用户行为/.feature 变化）；Cross-repo context=contract-only；API Contract=not-needed；Mock Strategy=contract-backed（仅 manifest fixture）。Graft=skipped（源码/workflow/PRD 足够，无 callable managed Graft 连接，不启动或接线）。Final Test Report / Run Summary MD=generated；Targeted / Affected Subset / Final Full Rerun=passed，**仅指本地 assertion-only 计划范围**。
- 临时 harness 的时间输出行曾用错误行号编辑，工具保留语法边界并提示；立即回读实际范围，修正重复输出后才执行，未影响仓库代码或旧记录。临时 fixture 已自动清理，harness 等独立审查完成后删除。lessons-record 已评估：遵守已有锚点回读规则即可，不新增重复长期规范；限定范围不包含 lesson/身份写入，本轮未解析或写入身份。

## 可读性、简化与发布边界

- Code Readability Review：源版本变量 `sourcePkg` 与安装包 `pluginPkg` 分开，路径明确；唯一锁定常量有 PRD 注释；沿用现有断言/同步 JSON 读取模式。无导出符号、类型接口或引用迁移；源码精确检索确认仅 workflow 的两个 caller。
- ponytail-review：**Lean already. Ship.** 无可删除的 speculative abstraction；保留 workspace 明确失败与显式 peer===engines，是本轮验收而非冗余清理目标。
- Release Readiness 适用性复核：初始 Book Gate Plan 的 planned 更新为 **not-required**。本次只改内部 CI 测试断言，不改生产运行时、宿主集成实现、依赖、部署、rollout 或发布流程；无容量/重试/事务/迁移风险，不制造生产 ready 结论。已发布 rc.1/rc.2 的 REQUIRED host 认证缺口仍在，只有后续获授权的完整 workflow 可以提供结果；本 chore 的局部通过不能解除该缺口。
- 恢复/回滚边界：仅本地两阶段提交；回退脚本修复会恢复已知旧断言问题，不会改变已发布包。记录继续 append-only，若需纠错追加新说明，不删除历史。TaskStore lifecycle 未运行，自动恢复可靠性不作保证；没有远端写入、全局修改或清理用户资产。
