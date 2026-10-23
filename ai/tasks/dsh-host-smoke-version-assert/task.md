---
schema_version: 1
id: dsh-host-smoke-version-assert
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict、唯一 writer；先 records-only 回填，再最小 smoke 断言修复；仅本地提交，不执行远端或全局配置写入。
status: in-progress
branch: chore/dsh-host-smoke-version-assert
created_at: '2026-10-23T18:00:01+08:00'
updated_at: '2026-10-23T18:00:01+08:00'
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
