---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-prd-f-backfill
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "checking"
branch: docs/dsh-sbtd-0.2.0-rc.1-prd-f-backfill
created_at: '2026-10-19T04:46:30+08:00'
updated_at: '2026-10-19T04:52:00+08:00'
completed_at: null
---

# PR-F：PRD 行 E 回填小 docs PR（PRD 行 F）

范围见 PRD `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 F 与 §2.1 Q7 B 回填规则（PR-D 合并后由一个小 docs PR 回填行 E）。**只改文档与一处 README 钉版测试断言**：不 bump `package.json` version、不 publish、不打 tag、不建 Release。

## 范围
- PRD 行 E → done：PR #99、merge SHA `1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831`（full 40）、done 时间 `2026-10-19T04:39:45+08:00`（merge commit 时间，非 API merged_at）
- PRD 行 E 注追加 publish 证据（均为已核实事实）：
  - `npm publish --tag next` → `@kunolu/dsh-sbtd@0.2.0-rc.1`；dist-tags `next=0.2.0-rc.1`，`latest` 仍 `0.1.0-rc.1`（`npm view` 实测核对）
  - registry shasum `0b4f3ef93703963757cd8cb991a65bb1d0cd35e6`（`npm view ... dist.shasum` 实测核对）
  - annotated tag + GitHub prerelease `dsh-sbtd-v0.2.0-rc.1`：https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.1
- PRD 行 F → in-progress，记本任务路径；F 行的 merge SHA 与 done 时间按回填规则在本 PR 合并后记录（本 PR 无法预知自身 SHA）
- README npm 版本提及 `0.1.0-rc.3` → `0.2.0-rc.1`（包 README 与根 README 共 3 处；`latest` 仍为 `0.1.0-rc.1` 的注保持不动且仍为真）；`t0-stub` 对应钉版断言同步更新
- 注册本任务进 `ai/tasks/index.md`
- 明确不改：宿主钉 `@deepseek-ai/dsh@0.1.1-rc.2` 的 README 行（超出本次明确范围；其对 peer range `>=0.2.0-rc.2` 已过时，作为剩余风险上报）

## Book Gate Plan
| Gate | 触发 | 状态 |
|---|---|---|
| book-legacy-change-safety | 既有行为 bug/高回归 | not-required（无生产行为修改） |
| book-refactoring-pass | 修改既有生产代码 | not-required（仅文档与一处测试断言常量） |
| book-ddd-distilled-modeling | 完整 grill 后/领域歧义 | not-required（本任务无 grill，需求已由 PRD 锁定） |
| book-ddia-data-design | schema/持久/跨服务流 | not-required |
| book-release-readiness | 部署/运行时行为变更 | not-required（docs-only；无发版、无部署、无运行时变化） |

## 验证（实际）
- PR #99 事实核对：`gh pr view 99` → state=MERGED，mergeCommit=`1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831`，mergedAt=`2026-10-18T20:39:45Z`（= 2026-10-19T04:39:45+08:00）。
- publish 证据核对：`npm view @kunolu/dsh-sbtd@0.2.0-rc.1 dist.shasum` → `0b4f3ef93703963757cd8cb991a65bb1d0cd35e6`；`npm view @kunolu/dsh-sbtd dist-tags` → `next=0.2.0-rc.1`、`latest=0.1.0-rc.1`。
- `pnpm --filter @kunolu/dsh-sbtd test`：335/335 绿（t0-stub README 钉版断言更新为 0.2.0-rc.1 后通过）。
- README 版本提及盘点：包 README 1 处、根 README 2 处 `0.1.0-rc.3` 已全部改为 `0.2.0-rc.1`；omp-sbtd 的 `0.1.0-rc.14` 与历史文档中的 rc.3 不动。
- 未执行（范围外/HARD STOP）：version bump、`npm publish`、git tag、GitHub Release；宿主钉 `0.1.1-rc.2` 行未改（见范围节剩余风险）。

## 状态事件
| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T04:46:30+08:00 | planned | in-progress | 任务启动（小 docs PR 回填 PRD 行 E） | 分支 docs/dsh-sbtd-0.2.0-rc.1-prd-f-backfill @ 1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831 |
| 2026-10-19T04:52:00+08:00 | in-progress | checking | 行 E 回填 + publish 证据 + README 版本提及完成，335/335 绿 | gh pr view 99 / npm view 实测核对；测试输出 pass 335 / fail 0 |
