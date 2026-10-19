---
schema_version: 1
id: dsh-sbtd-readme-host-pin-0-2-0-rc-2
workflow_mode: strict
mode_source: user
mode_note: 用户明确指定 strict（Lord chore 指令）
status: "checking"
branch: chore/dsh-sbtd-readme-host-pin-0.2.0-rc.2
created_at: '2026-10-19T07:41:49+08:00'
updated_at: '2026-10-19T07:46:19+08:00'
completed_at: null
---

# chore：README 宿主钉重定向 0.2.0-rc.2 + PRD 行 F 回填

用户明确指定的 strict chore。基于 origin/main @ `1090378b9318635d868c8b26152d40ff5231779c`。

## 范围
- 第一组变更：PRD `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 F → done：PR #100、merge SHA `1090378b9318635d868c8b26152d40ff5231779c`（full 40）、done 时间 `2026-10-19T05:04:58+08:00`（= PR #100 mergeCommit mergedAt `2026-10-18T21:04:58Z`，`gh pr view 100` 实测核对一致）
- 宿主钉 `@deepseek-ai/dsh@0.1.1-rc.2` → `@deepseek-ai/dsh@0.2.0-rc.2`（对齐 peer/devDep 下限；永不钉 0.2.1-rc.2）：
  - `packages/dsh-sbtd/README.md`
  - 根 `README.md`（表 + install 的 `npx`/`npm i -g` 示例）及双语镜像 `README_zh.md` 的同一钉
  - `packages/dsh-sbtd/test/t0-stub.test.mjs` 断言与标题
  - `packages/dsh-sbtd/features/t0-installable-stub.feature`、`t1-section-state.feature`
  - `packages/dsh-sbtd/` 下其余会因钉版变化而 break 的 live（非 archive）断言（盘点结果：仅上述 t0 测试）
- 注册本任务进 `ai/tasks/index.md`

## HARD STOP（不改）
- 不改 peer/engines range、不改 package version；不 publish、不打 tag
- 不重写 `ai/tasks/archive/**` 历史钉

## Book Gate Plan
| Gate | 触发 | 状态 |
|---|---|---|
| book-legacy-change-safety | 既有行为 bug/高回归 | not-required（无生产行为修改；钉版断言变更由 t0 测试直接覆盖） |
| book-refactoring-pass | 修改既有生产代码 | not-required（仅文档、feature 文案与测试断言常量） |
| book-ddd-distilled-modeling | 完整 grill 后/领域歧义 | not-required（本任务无 grill；需求由用户逐文件锁定，无领域歧义） |
| book-ddia-data-design | schema/持久/跨服务流 | not-required |
| book-release-readiness | 部署/运行时行为变更 | not-required（docs/测试断言-only；无发版、无部署、无运行时变化） |

## 验证（实际）
- PR #100 事实核对：`gh pr view 100` → state=MERGED，mergeCommit=`1090378b9318635d868c8b26152d40ff5231779c`，mergedAt=`2026-10-18T21:04:58Z`（= 2026-10-19T05:04:58+08:00），与用户给定值一致。
- 钉版盘点：live 范围内 `0.1.1-rc.2` 出现于根 `README.md`（6 处）、`README_zh.md`（6 处）、`packages/dsh-sbtd/README.md`（1 处）、t0 feature（4 处）、t1 feature（1 处）、t0-stub 测试（标题+断言）；另有 4 处转义正则断言（t2-plan、t5-review、t6-clarify、t15-sbtd-command）首轮 grep 未命中（转义点），由首跑 4 红暴露后一并重定向。全部改为 `0.2.0-rc.2` 后 live 范围无残留。
- `pnpm --filter @kunolu/dsh-sbtd test`：首跑 331/335（上述 4 处转义断言红）；修复后 **335/335 绿**（pass 335 / fail 0，tip `2551f038b5d2e09dbd4e52952526294e41814a3c` 的工作树）。
- peer/engines/devDep 未改（t0 断言仍验证 `>=0.2.0-rc.2 <0.3.0-0` / `0.2.0-rc.2`）；未 publish、未打 tag；`ai/tasks/archive/**` 未动。
- 持久化说明：`sbtd_task_state.py` TaskStore 因两条既有记录（`ai/tasks/docs-retire-todo/task.md`、`ai/tasks/dsh-sbtd-0-2-0-rc-1-pr-a-manuals/task.md`）不符合随包 stateEvent schema 而无法建 catalog，本任务记录按项目 fallback 手工写入，未改动这两条历史记录。

## 剩余风险（范围外，仅上报）
- `README_zh.md` 插件版本仍写 `0.1.0-rc.3`（上一轮回填未同步中文镜像，先于本任务存在）。
- t0 feature 的「README 声明 0.1.0-rc.3 已发布」scenario 与现断言（0.2.0-rc.1）不一致，先于本任务存在。
- `docs/spec/dsh-sbtd/backend/*.md`、`docs/assets/dsh/*.md`、历史 PRD v1.1/v1.2 仍提宿主 `0.1.1-rc.2`（历史/设计文档，不在本次钉版重定向范围）。
- 无 `0.2.1-rc.2` 钉出现（HARD STOP 遵守）。

## 状态事件
| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T07:41:49+08:00 | planned | in-progress | 任务启动（PRD 行 F 回填 + README 宿主钉重定向） | 分支 chore/dsh-sbtd-readme-host-pin-0.2.0-rc.2 @ 1090378b9318635d868c8b26152d40ff5231779c |
| 2026-10-19T07:46:19+08:00 | in-progress | checking | 行 F 回填 + 钉版重定向完成，335/335 绿 | 提交 a43634f（行 F + 任务注册）、2551f03（钉版）；测试输出 pass 335 / fail 0 |
