---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-pr-e-release
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "in-progress"
branch: feat/dsh-sbtd-0.2.0-rc.1-pr-e-release
created_at: '2026-10-19T04:15:15+08:00'
updated_at: '2026-10-19T04:15:15+08:00'
completed_at: null
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
| book-release-readiness | 打包/部署行为变更 | planned（tarball 版本标识变更；publish 本身不在本 run） |

## 验证（实际）
（待填）

## Release Readiness Review
（待填）

## 状态事件
| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T04:15:15+08:00 | planned | in-progress | 任务启动（首个 commit 回填 PRD 行 D） | 分支 feat/dsh-sbtd-0.2.0-rc.1-pr-e-release @ 73f0ca525bf73577560b6ce86d9e7a43ccb94517 |
