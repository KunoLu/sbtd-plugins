# dsh-sbtd T4 manuals sync

## Goal

把 `KunoLu/640-skills` v1.0.13（SHA `f8aa0d7225a26c5e00b81d2f1b05121108e63630`）白名单 skill 的 `SKILL.md` 与该 skill 自己的 `references/` 只读同步进 `packages/dsh-sbtd/manuals/<skill-id>/`，用 `manuals/MANIFEST.json` 记录 `sourcePath`、`sha256`、`sourceRevision`。供后续 tool 加载。本轮不实现 T5。

## grill-with-docs

本轮未重新执行 `grill-with-docs`。用户已声明 **Grill+DDD LOCKED**（白名单 12 ids、pin SHA、copy 范围、失败语义均已钉死）。不重开澄清。

Grill Q/A: none this turn (locked).

## DDD Boundary Review

```text
DDD Boundary Review
Status: confirmed
Ubiquitous language: manuals = 640-skills skill 正文的只读副本；MANIFEST = sourcePath + sha256 + sourceRevision 校验目录；whitelist = 12 个钉死 skill id；sourceRevision = 640-skills 钉死 commit；templates/skills 与 assets/external-skills/stable/skills 都是检索根，不可跳过后者。
Bounded contexts: (1) dsh-sbtd DSH 宿主适配器；(2) 640-skills 源仓。manuals 不是 live skill 安装，也不进入 agents/ 或 onboard 安装器。Trellis task artifacts 不是行为 SOT。
Invariants and business rules: HEAD 必须等于 pin SHA；拷 SKILL.md、references/ 与 skill-root markdown（不含 README.md）；不拷整棵树、git 历史、onboard.py、install.sh、agents/；源缺失 / SHA mismatch / copy fail / checksum fail 必须非 0；包保持 unpublished 且 private；宿主钉 0.1.1-rc.2；不改 hooks.ts、不加 sbtd_* tool、不做 T5。
Core / supporting / generic subdomains: supporting（只读同步桥）；core 仍是 T3 Book Gate 门禁。
Corrections to the grill-with-docs result: none（沿用锁定边界）。
Open conflicts and questions: none.
```

## Book Gate Plan

编码任务。不改 `src/hooks.ts`。校正既有 `scripts/sync-manuals.sh`、manuals、测试、package README、Trellis artifacts、backend spec。

| Skill | Applicability | Trigger fact | Phase | Gate state |
|---|---|---|---|---|
| `book-ddd-distilled-modeling` | required | Grill+DDD LOCKED；本轮输出锁定边界审核 | requirements | passed |
| `book-ddia-data-design` | on-demand | MANIFEST 是 checksum 目录，不是应用持久化/共享数据 | — | not-required |
| `book-legacy-change-safety` | required | HEAD `fba44da` 把 `domain-modeling` 根 `ADR-FORMAT.md` / `CONTEXT-FORMAT.md` 拷进 manuals，违反只拷 `SKILL.md`+`references/` | before first script edit | passed |
| `book-refactoring-pass` | required | 将改既有 `scripts/sync-manuals.sh` | before first script edit | passed |
| `book-release-readiness` | on-demand | 不发布、不改生产 API/job/deploy | — | not-required |

Legacy Change Safety Review: `characterized`（见 `implement.md`）。当前行为已用 `t4-manuals.test.mjs` / `t4-sync-exit.test.mjs` 锁住；本轮改的是 copy 范围与 MANIFEST 字段，不改 hooks。
Refactoring Review: `proceed`（见 `implement.md`）。无结构提取。MANIFEST 每条为 origin `sourcePath` + source `sha256` + `sourceRevision`；拷后 dest digest 必须等于 source。

## Confirmed facts

- Pin: `KunoLu/640-skills` v1.0.13 SHA `f8aa0d7225a26c5e00b81d2f1b05121108e63630`。本地源 `/workspace/640-skills`。
- 白名单 12 ids: `book-ddd-distilled-modeling` `book-ddia-data-design` `book-legacy-change-safety` `book-refactoring-pass` `book-release-readiness` `grill-with-docs` `grill-me` `grilling` `domain-modeling` `to-spec` `to-tickets` `trellis-workflow`。
- 检索根：`sbtd-workflow-onboard/templates/skills` 与 `sbtd-workflow-onboard/assets/external-skills/stable/skills`。不得跳过 external-skills。
- 当前 pin 下白名单 skill **没有** `references/`。`domain-modeling` 根上的 `ADR-FORMAT.md` / `CONTEXT-FORMAT.md` 与 `agents/` **不拷**。
- 宿主 `@deepseek-ai/dsh@0.1.1-rc.2`。包 `"private": true`，unpublished。包 version 保持 `0.1.0-rc.0`。不翻 private。不改根 README。
- HARD: 不改 `src/hooks.ts`。不加 extra tools。不做 T5。

## Requirements

- R1. `scripts/sync-manuals.sh`：参数为 SOURCE 目录，或省略参数 clone 到 pin SHA。
- R2. 只拷白名单 `SKILL.md` 与该 skill 的 `references/`。不拷整棵树、git 历史、`onboard.py`、`install.sh`、`agents/`。
- R3. `manuals/MANIFEST.json` 每条文件记录含 `sourcePath`（640-skills 仓相对源路径）、`sha256`、`sourceRevision`。
- R4. 源缺失、SHA mismatch、copy fail、checksum fail → 非 0。
- R5. `node:test` 断言 dest sha256 == MANIFEST。`packages/dsh-sbtd` 树内无 `install.sh`。
- R6. Package README 写 pin SHA、如何跑 sync、不要手改 manuals。保持 unpublished 与宿主 `0.1.1-rc.2`。
- R7. 填本任务 `prd.md` / `design.md` / `implement.md`。backend spec 更新到 T4。不 commit。

## Acceptance criteria

- [x] 12 个白名单目录均在 `manuals/<id>/` 且各有 `SKILL.md`，含 external-skills 来源的 grill/domain/to-*。
- [x] MANIFEST `sourceRevision` 等于钉死 SHA；每条 `sourcePath` 能映射 dest 且 sha256 与文件字节一致。
- [x] 跑 `scripts/sync-manuals.sh /workspace/640-skills` 成功。
- [x] 缺失 SOURCE 或 SHA 不对时脚本非 0。
- [x] `packages/dsh-sbtd` 内无 `install.sh` / `onboard.py`。`src/tools/` 仍只有 `plan.ts`。
- [x] package lint/typecheck/build/test 通过（`pnpm --filter` frozen-lockfile 失败，改用仓库 `biome`/`tsc`/`node --test`；未改 lockfile）。
- [x] 未改 `hooks.ts`、根 README、`private`、未做 T5、未 commit。

## Out of scope

- T5 `sbtd_review` 及任何新 `sbtd_*` tool
- `hooks.ts` 行为
- 发布 / private 翻转 / 根 README
- 拷贝 `ADR-FORMAT.md`、`CONTEXT-FORMAT.md`、`agents/`、LICENSE、NOTICE
- 手改 manuals 正文

## Notes

- BDD: `packages/dsh-sbtd/features/t4-manuals-sync.feature`（中文场景 + 英文关键词，沿用 T0–T3）。
- GitNexus: index stale（3 behind，MCP 仍在 `feat/dsh-sbtd-t3-rm-pkg`）；T4 不改 `apply`。Advisory。
- `rtk`: not-available，验证用原生命令。
- Channel: 不启动。
