# Fix PR12 T0 path-only live accept

## Goal

Correct v1.2 T0 live accept: local path plus dump-config `id: sbtd`. GitHub add is not T0-accepted.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：用户明确要求不要停下来 grill，本轮 prompt 即规划与实现批准；只纠正 T0 安装验收事实。

Grill Q/A: none.

## Book Gate Plan

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand | 未调用 grill-with-docs；无术语/边界歧义 | — | not-required |
| `book-ddia-data-design` | on-demand | 无持久化/共享数据变更 | — | not-required |
| `book-legacy-change-safety` | on-demand | 非 bug 修复；只改正文事实 | — | not-required |
| `book-refactoring-pass` | on-demand | 不修改既有生产代码 | — | not-required |
| `book-release-readiness` | on-demand | 不改 production path runtime | — | not-required |

## Requirements

- R1. T0 live accept is local path plus dump-config `id: sbtd`. GitHub add is not T0-accepted.
- R2. Change `dsh plugin --profile web add <path-or-github>` to a local `packages/dsh-sbtd` placeholder. Never `/workspace`.
- R3. Keep scheme 2a, the T1–T16 graph, and dump-config `id: sbtd`.
- R4. Edit only `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` plus this task’s Trellis files. Do not edit v1.1, README, packages, or `.env`. Do not start T1. Do not merge.

## Acceptance criteria

- [x] T0 live-accept text is local path + dump-config `id: sbtd`; GitHub add is stated not T0-accepted.
- [x] T0 验收 `plugin add` uses `/absolute/path/to/sbtd-plugins/packages/dsh-sbtd` (never `/workspace`, never `<path-or-github>`).
- [x] Scheme 2a and T1–T16 graph unchanged.
- [x] Commit `docs(prd): T0 live accept is path-only, not github` and push `origin docs/dsh-sbtd-v1.2-facts` without merge.

## Out of scope

- v1.1, README, packages, `.env`
- T1 implementation
- Merge / publish / `trellis init`
- Unrelated untracked files
