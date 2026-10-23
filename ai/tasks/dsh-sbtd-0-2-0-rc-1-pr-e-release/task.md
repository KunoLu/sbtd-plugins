---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-pr-e-release
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "done"
branch: feat/dsh-sbtd-0.2.0-rc.1-pr-e-release
created_at: '2026-10-19T04:15:15+08:00'
updated_at: '2026-10-23T10:35:03+08:00'
completed_at: '2026-10-19T04:39:44+08:00'
---

# PR-E 前半：release bump PR（PRD 行 E，仅 bump，不 publish）

omp 正在实现。范围见 PRD `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 E。**本 run 只做 release bump PR**：bump 版本 + CHANGELOG 打日期戳 + 开 PR。HARD STOP：不 `npm publish`、不打 git tag、不建 GitHub Release；Lord squash-merge 且 Reviewy CLEAN 后由后续任务执行 `npm publish --tag next`（绝不用 `latest`）+ 按 `bilingual-release-notes` 做双语 Release/annotated tag（prerelease）。

**首个 commit 必须回填 PRD 行 D：**
- PR: #98
- merge SHA: `73f0ca525bf73577560b6ce86d9e7a43ccb94517`
- done time: `2026-10-19T04:11:26+08:00`
- 行 D status → done；行 E → in-progress + 本 task 路径

## 范围
- `packages/dsh-sbtd/package.json` version `0.1.0-rc.3` → `0.2.0-rc.1`；只改必须匹配的引用，不发明
- 双语 CHANGELOG：`## [Unreleased]` → `## [0.2.0-rc.1] - 2026-10-19`（`CHANGELOG.md` + `CHANGELOG.zh.md`），保持最新在前；不把完整双语 Release body 粘进 CHANGELOG
- 钉版本的测试断言随 bump 更新（t0-stub、fu4-host-schema 的 `pkg.version`）
- README（根与包内）不改：其描述的是 npm 已发布态（next=0.1.0-rc.3、latest=0.1.0-rc.1），publish 前仍为真；publish 后由后续任务更新
- PRD 行 E notes 更新为「bump PR 与 publish 分离」，本行仍无 publish 证据
- 包测试保持绿；push + 开 PR 到 main

## Book Gate Plan
| Gate | 触发 | 状态 |
|---|---|---|
| book-legacy-change-safety | 既有行为 bug/高回归 | not-required（无生产行为修改；版本元数据+文档戳+测试钉版断言） |
| book-refactoring-pass | 修改既有生产代码 | not-required（不改 src；仅 manifest version、CHANGELOG 标题、测试断言常量） |
| book-ddd-distilled-modeling | 完整 grill 后/领域歧义 | not-required（本任务无 grill，需求已由 PRD 锁定） |
| book-ddia-data-design | schema/持久/跨服务流 | not-required |
| book-release-readiness | 打包/部署行为变更 | passed（ready，见末节 Review） |

## 验证（实际）
- `pnpm --filter @kunolu/dsh-sbtd test`：335/335 绿（t0-stub 与 fu4-host-schema 的 `pkg.version` 钉版断言更新为 `0.2.0-rc.1` 后通过；t0-stub 另加注释说明 README 描述 npm 当前 dist-tag 态）。
- `pnpm --filter @kunolu/dsh-sbtd pack --dry-run`：Tarball Details 显示 `kunolu-dsh-sbtd-0.2.0-rc.1.tgz`，Tarball Contents 含 `CHANGELOG.md`、`CHANGELOG.zh.md`、`package.json`；dry-run 未落盘 tarball。
- 版本引用盘点：仓库内 `0.1.0-rc.3` 其余出现均为历史记录（既有 task.md、PRD 背景、legacy-archive）或 npm 已发布态描述（三个 README，publish 前仍为真，按范围不改）；`pnpm-lock.yaml` 无该版本引用，无需改动。
- 双语戳一致：两 CHANGELOG 均为 `## [0.2.0-rc.1] - 2026-10-19`，各仅一处 `[Unreleased]` 被替换，无其他 diff。
- 未执行（HARD STOP）：`npm publish`、git tag、GitHub Release。

## Release Readiness Review
- Status: ready
- Production path and affected users / systems: 未来 `@kunolu/dsh-sbtd@0.2.0-rc.1` npm tarball 的版本标识与随包 CHANGELOG；本 PR 合并且后续 publish 前不影响任何安装方（npm dist-tag 未动）。运行时无代码变化（src 零改动）。
- Failure modes and safeguards: 版本钉错 → t0-stub/fu4-host-schema 钉版断言 + pack --dry-run tarball 名双重核对；CHANGELOG 漏戳 → 双语逐文件 diff 核对各仅一处替换；peer/engines/devDep 均未动，宿主兼容面与 PR-C 已验一致。
- Capacity / backpressure / limits: not-applicable（元数据变更）。
- Observability / alerts / runbook: not-applicable。
- Rollout / migration / rollback / cleanup: 本 PR 只改仓库内版本元数据，回滚即 revert；publish/tag/Release 属后续任务，其 rollout（`--tag next`，`latest` 不动）已在 PRD 行 E 注与任务范围写明。
- Required validation and result: 包测试 335/335 通过；pack --dry-run 通过。
- Optional checks / residual risk: `dsh-host-compat.yml` 为 workflow_dispatch，双行 REQUIRED 绿以 PR-C 已跑证据为准（本 PR 不动宿主兼容面）；README 仍描述 0.1.0-rc.3 npm 发布态，publish 后需由后续任务更新——已写入范围与测试注释。

## 状态事件
| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T04:15:15+08:00 | planned | in-progress | 任务启动（首个 commit 回填 PRD 行 D） | 分支 feat/dsh-sbtd-0.2.0-rc.1-pr-e-release @ 73f0ca525bf73577560b6ce86d9e7a43ccb94517 |
| 2026-10-19T04:18:02+08:00 | in-progress | checking | bump + 双语戳 + 钉版断言完成，335/335 绿、pack dry-run 名实相符 | commit 2（本任务分支）；测试输出 pass 335 / fail 0 |
| 2026-10-19T04:39:44+08:00 | checking | done | 记录回填：PR #99 已合并 | gh pr view 99：MERGED，headRefName=feat/dsh-sbtd-0.2.0-rc.1-pr-e-release 与 branch 一致；merge SHA 1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831；mergedAt=2026-10-19T04:39:45+08:00；git %cI=2026-10-19T04:39:44+08:00；于 2026-10-23T10:35:03+08:00 回填 updated_at |

## 当前值（offline-cache chore 记录回填）

- PR #99 release bump 已合并，status = done；completed_at 取 merge commit 时间，不代表本任务执行了 publish。上文进度保留为历史。用户明确授权本次仅修正文档状态，不重绑定历史 branch，不补造旧事件或重跑历史门禁。
