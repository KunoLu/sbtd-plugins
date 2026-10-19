---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd-r7-p0-v4
workflow_mode: strict
mode_source: user
mode_note: 用户 2026-10-19 ~20:31 +08:00 选定 option 2（团队投票 4× option 2）：先修 PRD，transformVersion 升 p0-v4；strict 沿用 PRD 规则「每个任务都用 strict」
status: "in-progress"
branch: docs/omp-sbtd-0.2.0-rc.1-prd-r7-p0-v4
created_at: '2026-10-19T20:34:00+08:00'
updated_at: '2026-10-19T20:34:00+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 PRD R7：p0-v4 授权（PRD-only 修订）

## 目标

按用户 2026-10-19 ~20:31 +08:00 决定（option 2，团队投票 4× option 2）修订 `docs/prd/omp-sbtd-0.2.0-rc.1.md`（R7），把行 B 命中的 CONTRACT-CHANGE-NEEDED 转化为 PRD 锁定授权：

1. 行 B transformVersion `p0-v3` → `p0-v4`（sourceId `sbtd-workflow-kit-upstream` 不变）；行 B 不再「只改 resolvedRevision + sourceTreeSha256」，而是同时执行 p0-v4 transform 变更。
2. p0-v4 零泄漏门禁（`omp-projection.ts` PROJECTION_FORBIDDEN_TOKEN）豁免从单一 digest 绑定 `onboard/runtime/scripts/onboard.py` 扩为 digest 绑定的 canonical onboard runtime 包路径集：`onboard/runtime/scripts/*.py`、`onboard/runtime/assets/*`、两个 schema json（`onboard-contracts.schema.json`、`upgrade.schema.json`）；内容仍经 sourceTreeSha256 / 生成 digest 逐字节绑定，overlay 不得借豁免走私非 canonical 内容。
3. p0-v4 `agent-plugin-projection.ts` CANDIDATES 删除 `trellis-workflow`（上游 v2.0.2 已删该实体）；缺候选 ENOENT 仍 fail-closed。
4. overlay catalog（行 B 范围，不推迟到行 C）：删 `skill:trellis-workflow` 与 `skill:trellis-channel`，增 `skill:sbtd-task`（对齐已收录模板树）。
5. 行 C 仍只拥有 omp peer/devDep 18.11.1 升级与真实宿主 smoke（D11），不拥有 catalog 的 sbtd-task 新增。
6. 任务表：行 A 回填 done（PR #104 / merge SHA `f1bba41d168af04807914914ad8dce27dfc8688b` / 2026-10-19T17:13:57+08:00）；行 B 状态更新为 PRD R7 已授权 p0-v4、待本 PRD 合并后在行 B 分支继续。
7. 修订日志 R7 与状态事件记录用户决定 + 团队投票（+08:00）。

## 范围

- `docs/prd/omp-sbtd-0.2.0-rc.1.md`（R7 修订）。
- 本任务记录；任务 0 记录 `ai/tasks/omp-sbtd-0-2-0-rc-1-prd/task.md` 追加状态事件。
- `ai/tasks/index.md` 与 `.sbtd/active-task.json` 接线。

## 非目标

- 不改 `packages/` 任何代码、不跑 sync、不 push、不开 PR。
- 不编辑行 B 分支 `feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream`（tip f420cc4）上的任何文件；其 blocked 记录仅作证据引用。
- 不改 D1–D13 既有锁定内容（仅行 B 边界按 D14 修订）。

## 证据（只读引用，不复制进 packages）

- 行 B blocked 记录：`git show feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream:ai/tasks/omp-sbtd-0-2-0-rc-1-pr-b-sync-upstream/task.md`（status blocked，blocked_reason CONTRACT-CHANGE-NEEDED；墙 1 CANDIDATES trellis-workflow ENOENT；墙 2 PROJECTION_FORBIDDEN_TOKEN 1 pathViolation + 19 payloadViolations；新 sourceTreeSha256 实测 `c1fc3f679c375a22c6272de92c3377ac04ea8edb996acd314ea76f73257739b0`）。
- 用户决定：2026-10-19 ~20:31 +08:00，option 2（团队投票 4× option 2），catalog 跟随 row B。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill 后 DDD 已在任务 0 执行；R7 为供应链 transform 授权修订，无领域模型变更（sourceId 不变） | R7 | not-required（沿用任务 0 DDD） |
| book-ddia-data-design | 无 schema/迁移/跨进程数据设计变更 | R7 | not-required |
| book-legacy-change-safety | 不改代码行为（docs-only） | R7 | not-required |
| book-refactoring-pass | 不改生产代码 | R7 | not-required |
| book-release-readiness | 不发布、不改 runtime 交付 | R7 | not-required |

## 验收

- PRD R7 落地 A–F 六项锁定（transformVersion p0-v4、门禁豁免扩展、CANDIDATES 删 trellis-workflow、overlay catalog 增删、行 C 边界、行 A/行 B 任务表状态）。
- 修订日志 R7 与两处状态事件含用户决定时间（~20:31 +08:00）与团队投票 4× option 2。
- 纯 docs diff：`git status` 仅 `docs/prd/`、`ai/tasks/`、`.sbtd/active-task.json`。

## 进度

- [x] 任务记录落地 + index/active 接线
- [ ] PRD R7 修订（§0/§2/§2.1/§3/§4/§5/§6）
- [ ] 任务 0 task.md 状态事件
- [ ] 本任务转 done

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T20:34:00+08:00 | planned | in-progress | 用户选定 option 2（团队投票 4× option 2）：先修 PRD，行 B transformVersion 升 p0-v4，catalog 跟随 row B | 用户 2026-10-19 ~20:31 +08:00 指令；行 B blocked 记录（feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream tip f420cc4）CONTRACT-CHANGE-NEEDED 两墙实测 |
