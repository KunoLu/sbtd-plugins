---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-docs-changelog
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "in-progress"
branch: feat/dsh-sbtd-0.2.0-rc.1-docs-changelog
created_at: '2026-10-19T03:35:53+08:00'
updated_at: '2026-10-19T03:35:53+08:00'
completed_at: null
---

# PR-D 前置：文档/CHANGELOG 双语（PRD 行 D）

omp 正在实现。范围见 PRD `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 D。本任务只做文档与打包清单，**不** bump 版本、不 publish、不打 tag/Release（归行 E）。

**首个 commit 必须回填 PRD 行 C：**
- PR: #97
- merge SHA: `155982bf1992463556b06126b74aa275fd6839f9`
- done time: `2026-10-19T03:17:27+08:00`
- 行 C status → done；行 D → in-progress + 本 task 路径

## 范围（锁定：R1 Q8 双语 + Lord 2026-10-19）
- 新建 `packages/dsh-sbtd/CHANGELOG.md`（EN）与 `CHANGELOG.zh.md`（ZH），Keep a Changelog 风格，最新在前，标题 `## [Unreleased]`（不打 0.2.0-rc.1 日期，归行 E）
- EN/ZH 一一对应
- 内容覆盖本 RC 已合并事实：PR-A manuals 同步（#94）、PR-B 后端 Graft/sbtd-task/lessons v2（#96）、PR-C V4 kind + peer/engines 同范围 + 两行 REQUIRED CI（#97）；不编造
- 部署边界（必需）：`npm install` 本插件配 `@deepseek-ai/dsh@0.2.1-rc.2` 会 ERESOLVE（npm peer 默认无 includePrerelease，跨 patch rc）；pnpm host-compat 两行（0.2.0-rc.2 / 0.2.1-rc.2）均通过；range 保持 `>=0.2.0-rc.2 <0.3.0-0` 不退回；推荐 pnpm / dsh plugin manager 安装，npm 0.2.1-rc.2 用户可能需 overrides；双语写明
- 两个 CHANGELOG 加入 `packages/dsh-sbtd/package.json` `files`
- 不碰：version bump、npm publish、GitHub Release/tag、README（README 安装段归本任务外的既有口径——本次范围明确只 CHANGELOG + files）

## Book Gate Plan
| Gate | 触发 | 状态 |
|---|---|---|
| book-legacy-change-safety | 既有行为 bug/高回归 | not-required（纯文档+打包清单，无生产代码行为修改） |
| book-refactoring-pass | 修改既有生产代码 | not-required（仅新增文档文件与 manifest files 数组；Skill 明确 docs/config-only 不适用） |
| book-ddd-distilled-modeling | 完整 grill 后/领域歧义 | not-required（本任务无 grill，需求已由 PRD 锁定） |
| book-ddia-data-design | schema/持久/跨服务流 | not-required |
| book-release-readiness | 打包/部署行为变更 | planned（files 数组影响发布 tarball 内容，交付前执行） |

## 事实来源
- PR-A（#94, `0499af808ebe38a676668af98979c62355775542`）：manuals 钉 640-skills v2.0.2 / `1d82494d`；删 trellis-workflow 手册，加 sbtd-task（SKILL.md + 整个 references/ 含 task-data.schema.json）；MANIFEST 逐文件 sha256；五本 book 手册刷新；t4 字节比对覆盖 JSON schema
- PR-B（#96, `609766b1d911f1a4597e5ee7117877d2238a548f`）：删 Trellis/GitNexus 后端；Graft 后端（六 reason 词表，可降级不拒载）；sbtd-task 只读层 + workflow_mode 分层（工具参数/宿主注入 → task.md → default）；plan/review/validate 返回 workflowMode+workflowModeSource；lessons v2（身份 .sbtd/developer，layered/已有短入口/flat 迁移 skip 链，旧 .trellis 树只读）；spec/tickets/task-artifact 只回 draft；gitnexus→graft 字段改名
- PR-C（#97, `155982bf1992463556b06126b74aa275fd6839f9`）：V4 `kind:'dsh-sbtd'` 且识别兼容 `'plugin:dsh-sbtd'`；runPreStep 保留 `startsRequestSeries`；peerDependencies 与 engines.dsh 同范围 `>=0.2.0-rc.2 <0.3.0-0`；devDep 钉 0.2.0-rc.2；CI unit-pack 两行 REQUIRED 矩阵；T0：pnpm add 双行 exit 0，npm 下限 0.2.0-rc.2 无 ERESOLVE，npm 0.2.1-rc.2 ERESOLVE（只记不退）

## 验证（计划）
- `pnpm --filter @kunolu/dsh-sbtd pack --dry-run` 或等价：tarball 含 CHANGELOG.md 与 CHANGELOG.zh.md
- `pnpm --filter @kunolu/dsh-sbtd test`：不回归
- EN/ZH 条目一一对应人工核对

## 状态事件
| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T03:35:53+08:00 | planned | in-progress | 任务启动（首个 commit 回填 PRD 行 C） | 本分支首个 commit |
