---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-22 指示执行行 C（插件适配 sbtd v2.0.2 + omp 18）
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-c-plugin-adapt
created_at: '2026-10-22T11:18:35+08:00'
updated_at: '2026-10-22T11:18:35+08:00'
---
# omp-sbtd 0.2.0-rc.1 行 C：插件适配 v2.0.2 与 omp 18

## 目标

按 `docs/prd/omp-sbtd-0.2.0-rc.1.md` 行 C（L69）、D8、D11 与 §4「任务 C 宿主 smoke 硬门」执行：

- D11 宿主升级（行 C 独占）：`packages/omp-sbtd/package.json` peerDependencies `@oh-my-pi/pi-coding-agent` `>=17.3.5 <18` → `>=18 <19`；devDependency 精确钉 `17.3.5` → `18.11.1`；根 `pnpm-lock.yaml` 相应更新（pnpm@11.17.0）。
- 按 18.11.1 API 重跑 typecheck 与全部测试，修复破坏。
- 插件适配 sbtd v2.0.2（含行 B task.md 验证证据第 16 条遗留的 `src/extension.ts` trellis 能力映射 / profileCatalog optional `trellis` 项）。
- D8：若 5 个 Python 依赖 fail-closed 隔离预检尚未接线，则接线（不自动 pip install；验签缺 cryptography 拒跑；可降级 skipped 的普通入口：无）。
- HARD GATE：omp 18.11.1 真实宿主 smoke PASS（插件加载、工具/hooks 注册、onboard 冒烟）；parser fixture 不算；失败修到通过，不退回旧 range。

## 非目标

- 不触碰行 B 锁定的 p0-v4 transform（D14 三项）与 overlay catalog。
- 不开始行 D / R / E（不写 CHANGELOG Breaking 条目、不改 README 兼容说明、不 bump version、不 tag、不 publish）。
- 不开 PR、不 merge（用户指示：仅 push 分支）。
- 如需契约或 PRD 变更：停止，记录 CONTRACT-CHANGE-NEEDED。

## 状态事件

- 2026-10-22T11:18:35+08:00 created：worktree `/workspace/sbtd-plugins-row-c` 基于 origin/main `02d93ccc9f263b0733d41ef86fab1496aba28977`；首 commit 回填行 B（PR #106 / merge SHA `02d93ccc9f263b0733d41ef86fab1496aba28977` / mergedAt `2026-10-19T20:14:20Z` = 2026-10-20T04:14:20+08:00，`gh pr view 106 --json mergedAt,mergeCommit` 实测一致），行 C 标 in-progress。

## 决策

（待补）

## 验证证据

（待补：typecheck、全量测试、18.11.1 真实宿主 smoke 命令/二进制绝对路径/`--version`/输出摘录）

## 使用的模型

（待补：按 session jsonl 记录 provider/model、resolvedModel、是否 fallback、消息/工具计数、subagent）
