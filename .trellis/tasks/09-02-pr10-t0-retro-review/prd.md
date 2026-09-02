# Retro review PR10 T0 stub

## Goal

Retro `/review` of T0 already on main `7253b29` (PR 10, `packages/dsh-sbtd` T0 stub). Produce `REVIEW_RESULT`. On FINDINGS, fix the T0 README install contract and open a fix PR. Do not start T1. Do not merge.

## grill-with-docs

未完整调用 `grill-with-docs`。原因：检查项已钉死；本轮是对已落地 T0 的 retro review 与 README 安装文案修正，不涉及新领域模型或长期术语。

Grill Q/A: none.

## Book Gate Plan

Review + docs/test/feature fix。不改 `apply()` 生产逻辑。

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | on-demand | 未调用 grill-with-docs；无术语/边界变更 | — | not-required |
| `book-ddia-data-design` | on-demand | 无持久化/共享数据 | — | not-required |
| `book-legacy-change-safety` | on-demand | 不改 runtime 行为；README 合同有测试覆盖 | — | not-required |
| `book-refactoring-pass` | on-demand | 只改 README / `.feature` / 测试，不改既有生产代码 | — | not-required |
| `book-release-readiness` | on-demand | 不发布、不合并 | — | not-required |

## Confirmed facts

- Review target: `7253b29` / PR 10. Later `16acd38` is docs-only v1.2 facts; T0 stub files on HEAD match `7253b29` except this fix.
- `packages/dsh-sbtd/src/index.ts` `apply()` only `console.log("[dsh-sbtd] plugin loaded (T0 stub)")` then `ctx.systemPrompt.section({ name: "sbtd", order: 50, text: "" })`. No `fs`, no `AGENTS.md`.
- Live `dsh --version` = `0.1.1-rc.2`. Live `dsh --profile web --dump-config` contains `- id: sbtd` / `name: '@kunolu/dsh-sbtd'`.
- `cordis.patch.yml` `id: sbtd`, `name: "@kunolu/dsh-sbtd"`. Peer `@deepseek-ai/dsh` = `0.1.1-rc.2`.
- `packages/dsh-sbtd` has no `trellis init --dsh`.
- Root `README.md` / `README_zh.md` already install `add @kunolu/dsh-sbtd@next` on `dsh@0.1.1-rc.2`. No bare package add. No local path.
- `packages/dsh-sbtd/README.md` still documents local path `dsh plugin --profile web add /absolute/path/to/sbtd-plugins/packages/dsh-sbtd`. Feature + `t0-stub.test.mjs` still require that local-path README contract. **This is the required-check FAIL.**
- No T1 files (`src/section.ts` / `src/state.ts` absent).

## Requirements

- R1. Review PR 10 / `7253b29` T0 stub only. Do not start T1. Do not merge.
- R2. Required checks: `apply()` does not write disk or `AGENTS.md`; dump-config `id: sbtd`; pin `dsh@0.1.1-rc.2`; no `trellis init --dsh`; README has no bare package add and no local path (uses `@kunolu/dsh-sbtd@next`).
- R3. Record grill Q/A. Do not stop for grill.
- R4. Print `REVIEW_RESULT=CLEAN` or `REVIEW_RESULT=FINDINGS`. On FINDINGS, fix `packages/dsh-sbtd` README + feature + test to `@kunolu/dsh-sbtd@next`, open a new PR, print `FIX_PR=<number>`.
- R5. Edit only `packages/dsh-sbtd/README.md`, `packages/dsh-sbtd/features/t0-installable-stub.feature`, `packages/dsh-sbtd/test/t0-stub.test.mjs`, plus this task’s Trellis files. Do not change `apply()`, lockfile, `private`, root README, or T1 files.

## Acceptance criteria

- [x] Required checks executed against `packages/dsh-sbtd` + root README EN/ZH + live dump-config.
- [x] Grill Q/A recorded (none).
- [x] Package README documents `dsh plugin --profile web add @kunolu/dsh-sbtd@next`. No local path. No bare package add.
- [x] Feature + `t0-stub.test.mjs` lock the `@next` contract.
- [x] `node --test packages/dsh-sbtd/test/t0-stub.test.mjs` passes.
- [ ] Fix PR opened. No T1 started. No merge.

## Out of scope

- T1–T16 implementation
- Merge / publish / lockfile / `private` / root README / `apply()` edits
- Channel workers (static review; markdown + prompt enough)

## Notes

- Channel preflight: not spawned.
- GitNexus: docs/test/feature only; index stale (2 behind HEAD, lastCommit `5a459c1`). Advisory.
- `rtk`: evaluate at test time.
- Original T0 PRD R9 required package README local path; this retro check requires `@next` and no local path.
