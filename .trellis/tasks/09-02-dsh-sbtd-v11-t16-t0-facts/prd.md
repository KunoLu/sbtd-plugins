# record v1.1 T16 default repo and T0 unpublished registry facts

## Goal

Update `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md` with 2026-09-02 facts: T16 default real-repo e2e is this repo (`sbtd-plugins`); T0 registry package is unpublished, so live accept is local path or github.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：用户明确要求不要停下来 grill，采用本轮 prompt 的 PRD 默认值；本任务只纠正验收仓与 T0 发布事实，不改领域模型或长期术语。

## Book Gate Plan

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand | 未调用 grill-with-docs；无术语/边界歧义 | — | not-required |
| `book-ddia-data-design` | on-demand | 无持久化/共享数据/cache/异步流 | — | not-required |
| `book-legacy-change-safety` | on-demand | 非 bug 修复；只改正文事实 | — | not-required |
| `book-refactoring-pass` | on-demand | 不修改既有生产代码 | — | not-required |
| `book-release-readiness` | on-demand | 不改 production path runtime | — | not-required |

## Requirements

- R1. T16 验收仓：默认用本仓 `sbtd-plugins` 做真实仓库 e2e（仓内已有 `.trellis/`）。不要优先用 KunoLu/KPi（该仓现为 private）。
- R2. onboard / `trellis init` 前必须人类确认；不要未提示代跑。
- R3. 不要改 `640-skills`。
- R4. T0：registry 包未发布。现场验收用本地 path 或 github。
- R5. 只改 v1.1 PRD 与本任务 Trellis 产物。不要改 README、代码、`.env`；不要 publish；不要 `trellis init --dsh`；不要做 T1；不要 git commit。不要改 v1.2 PRD。
- R6. 纠正 §0.4「仓内故意没有 `.trellis/`」，与 2026-09-02 事实一致。

## Acceptance criteria

- [x] Header 日期为 `2026-09-02`。
- [x] §0 有 2026-09-02 事实，覆盖 T16 默认验收仓与 T0 未发布 registry。
- [x] §0.4 不再写「仓内故意没有 `.trellis/`」。
- [x] T16 **验收仓**不再优先 KPi；默认本仓 `sbtd-plugins`；onboard / `trellis init` 需人类确认；不改 `640-skills`。
- [x] T0 验收正文写明 registry 未发布，必须用本地 path 或 GitHub URL 安装，不是 registry 包名。
- [x] 未改 README、代码、`.env`、v1.2 PRD；未 publish；未 `trellis init --dsh`；未做 T1；未 git commit。

## Out of scope

- README
- v1.2 PRD
- 生产代码、测试、`.env`
- publish / registry 发包
- `trellis init --dsh`、T1、onboard 代跑
- `640-skills`
- Git commit / push / merge

## Notes

- Lightweight docs task; PRD-only.
- BDD skipped: documentation-only fact correction; no user-visible product behavior change in this turn.
- GitNexus skipped: no production symbol edits.
- v1.1 曾被 worktree 重命名为 v1.2；本任务从 HEAD 恢复 v1.1 后只改该文件。
