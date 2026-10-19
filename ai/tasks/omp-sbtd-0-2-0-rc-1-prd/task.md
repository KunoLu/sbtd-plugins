---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd
workflow_mode: strict
mode_source: user
mode_note: 用户要求 omp-sbtd 0.2.0-rc.1 任务 0 用 strict；PRD 规则为每个任务都用 strict
status: "in-progress"
branch: docs/omp-sbtd-0.2.0-rc.1-prd
created_at: '2026-10-19T11:21:02+08:00'
updated_at: '2026-10-19T12:12:00+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 PRD（任务 0：grill + DDD）

## 目标

为 `@kunolu/omp-sbtd@0.2.0-rc.1` 跑完整 grill-with-docs 并交付独立 DDD Boundary Review，确认需求后落地 `docs/prd/omp-sbtd-0.2.0-rc.1.md`。本任务只写文档：不改代码、不改 `package.json`/lockfile、不动 `packages/`。

## 范围

- 本 strict 任务记录（`ai/tasks/omp-sbtd-0-2-0-rc-1-prd/task.md`）。
- Grill Round 1：`ai/tasks/omp-sbtd-0-2-0-rc-1-prd/grill-r1.md`（中文，每题 3–4 选项 + 推荐 + 仓内/上游事实依据）。
- PRD：`docs/prd/omp-sbtd-0.2.0-rc.1.md`，结构对齐 `docs/prd/dsh-sbtd-0.2.0-rc.1.md`。
- DDD draft 随 grill-r1 交付；grill 全部锁定后按 book-ddd-distilled-modeling 输出独立 Boundary Review 并等用户确认。

## 非目标

- 不实现任务 A–F 的任何代码改动（迁移、同步、适配、CHANGELOG、bump、回填均不在本任务）。
- 不执行 ROADMAP 归档 chore（`git mv docs/prd/ROADMAP.md` 与 conformance-matrix 53 条 source.path 更新是独立 chore，不在主序列）。
- 不 npm publish；不打 tag。

## 已锁定输入（用户 2026-10-19，本任务不重问）

- D1：sbtd-workflow-kit 走 option B——把 kit 的投影/生成逻辑迁入 `packages/omp-sbtd`，然后整体删除 `packages/sbtd-workflow-kit`（上游同步方式对齐 dsh-sbtd）。
- D2：顺序先迁移、后同步。
- D3：上游钉 640-skills `v2.0.2`（`1d82494d74f6df9bca7dccef2da409f87091883e`）。
- D4：npm 只发 dist-tag `next`；`latest`（`0.1.0-rc.2`）不动。
- D5：发布为 annotated tag `omp-sbtd-v0.2.0-rc.1` + 双语（EN/ZH）GitHub prerelease。
- 任务序列：0 grill+DDD → A 迁移并删除 kit 包 → B 同步上游到 1d82494 → C 插件适配 v2.0.2 与 omp 18 → D 双语 CHANGELOG → R 双语 README → E bump+tag+prerelease+publish next → F 回填 PRD 行。
- 任务 A 为纯搬移：`upstream.lock.json` 的 revision 与 `transformVersion=p0-v3` 不变，sourceId `sbtd-workflow-kit-upstream` 不变；CLEAN 门为嵌入 `kit/`、`skills/`、manifest 哈希、`npm pack --dry-run` 文件清单及逐文件 sha256 与 `4f7388c` 构建完全一致（唯一例外：package.json 恰好两处编辑——删 devDep `@kunolu/sbtd-workflow-kit`、`scripts.build` 仅替换 kit check-generated 调用为包内入口，peer/devDep omp 钉与 files/version 不变——与根 `pnpm-lock.yaml` 的 kit workspace 包移除）；check-generated、p0 validator、SBOM、全部测试绿；`docs/spec/sbtd-workflow-kit/` 路径与 conformance matrix 路径同 PR 更新；运行时 zod（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）、p0 `cli.ts` kitRoot、`release-validator.ts`、`write-sbom.ts` 同步更新。
- 每个任务用 strict；每个 PR 首个 commit 回填上一行的 PR、merge SHA、done 时间（Asia/Shanghai +08:00）；Reviewy 对 tip 评审 CLEAN 后 Lord squash-merge，合并后删本地+远程任务分支。

## 已核对事实（不作为新决策）

- `packages/sbtd-workflow-kit/upstream.lock.json`：sourceId `sbtd-workflow-kit-upstream`，resolvedRevision `f8aa0d7225a26c5e00b81d2f1b05121108e63630`（CHANGELOG 记为 v1.0.13 同步），transformVersion `p0-v3`；kit 包 `private: true`，从未发布 npm。
- 嵌入模板分叉：`packages/omp-sbtd/kit/AGENTS.project-root.md` 头钉 `4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb`，`AGENTS.project-omp.md` 头钉 `f8aa0d7…`；manifest canonical 同为 `f8aa0d7…`。
- 上游 diff（f8aa0d7→1d82494，`sbtd-workflow-onboard/`，本机 clone 实测）：229 文件变更（67 新增 / 107 删除 / 53 修改）；`scripts/` 由 1 个 `onboard.py` 增至 33 个 `.py`；新增顶层 `requirements.txt`（jsonschema、PyYAML、markdown-it-py、tomlkit、cryptography 五依赖）、`onboard-contracts.schema.json`、`upgrade.schema.json`、`assets/` 9 个顶层文件、`templates/skills/sbtd-task/` 8 个文件。
- 现行嵌入 kit 只带 `scripts/onboard.py`（stdlib 先例，无 requirements.txt），由 `src/onboard/python-runtime.ts` 执行。
- `packages/omp-sbtd/package.json`：version `0.1.0-rc.14`；peerDependencies `@oh-my-pi/pi-coding-agent: >=17.3.5 <18`；devDep 精确钉 `17.3.5`；无 `engines` 字段。npm 实测：宿主 latest `18.12.2`；`@kunolu/omp-sbtd` dist-tags `latest=0.1.0-rc.2`、`next=0.1.0-rc.14`。
- `packages/omp-sbtd/validation/p0/conformance-matrix.v1.json` 有 53 条 `source.path = docs/prd/ROADMAP.md`；ROADMAP 头部为「文档版本 0.7-draft / 文档日期 2026-07-21」。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill-with-docs 为本任务目标；DDD draft 已随 grill-r1 交付并反映 Round 1 锁定 | grill 已锁定，待 Reviewy 独立复审 | planned |
| book-ddia-data-design | 本任务不稳固 schema、迁移或跨进程数据设计 | 本轮 grill | not-required |
| book-legacy-change-safety | 本轮不改既有行为 | 本轮 grill | not-required |
| book-refactoring-pass | 本轮不改生产代码 | 本轮 grill | not-required |
| book-release-readiness | 本轮不发布、不改 runtime 交付 | 本轮 grill | not-required |

grill Round 1 已全部锁定（用户 2026-10-19 11:39/11:43/11:44，Asia/Shanghai；见 `grill-r1.md` 锁定标注与 PRD D7–D13）。Reviewy Boundary Review R1 findings 已于 2026-10-19 全部修复（见 PRD 修订日志 R3 与本任务状态事件）；DDD draft 仍待用户确认后才转 confirmed。

## 验收

- 三个文档落地：本 task.md、`grill-r1.md`、`docs/prd/omp-sbtd-0.2.0-rc.1.md`。
- grill-r1 每题 3–4 选项、有推荐、理由引用仓内或上游实测事实；无法核验处标「待核验」。
- PRD 含版本钉、D1–D13 锁定决策表、DDD draft 节、按优先级排序的任务表（8 列），并写明回填与分支规则。
- grill 锁定 + DDD confirmed 后本任务才可进 done；需求未经 DDD 通过不得进入任务 A。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T11:21:02+08:00 | planned | in-progress | 用户要求新建 strict 任务 0 并立即交付 grill-r1 + PRD 草案 | 用户 2026-10-19 指令；分支 docs/omp-sbtd-0.2.0-rc.1-prd 基于 main `4f7388c` |
| 2026-10-19T11:40:08+08:00 | in-progress | in-progress | 用户指令修订 R1b：D1 写明目标布局并收窄 Q3、新增锁定 D6、任务表插行 R、grill 新增 Q6/Q7、Q1 按上游 fail-closed 重写、Q4 改推荐 B、dsh PRD 追加行 G | 用户 2026-10-19 R1b 指令；事实核验：上游 `1d82494` 实测（sbtd_migration.py:589-596 validator-unavailable、sbtd_upgrade.py:1272-1284 isolated-dependencies-unavailable、assets 含两个 .pub 签名钥）；`omp --version` 实测 omp/18.11.1；两包 files 均不含 README_zh.md；p0 发布物清单硬编码于 release-validator.ts `inventoryDeclaredPackageContent`；omp 宿主是否读 engines 仍待核验 |
| 2026-10-19T11:44:00+08:00 | in-progress | in-progress | grill Round 1 全部锁定并回填 PRD：Q6 A（11:39），Q1/Q2/Q3/Q5 A 与 Q7 是（11:43），Q4 用户 11:44 选定 `>=18 <19`（替代原推荐 B，devDep 钉 18.11.1，omp 18.11.1 真实宿主 smoke 为无退路硬门）；PRD 新增锁定 D7–D13，dsh PRD 行 G 转 planned；DDD Boundary Review 待 Reviewy，任务保持 in-progress | 用户 2026-10-19 11:39/11:43/11:44 确认（Asia/Shanghai）；`grill-r1.md` 各题 ✅ 锁定标注与 Round 1 选定汇总；`docs/prd/omp-sbtd-0.2.0-rc.1.md` D7–D13、行 0/C/D/R/E、验收要点、非目标与修订日志 R2；`docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G 状态 planned |
| 2026-10-19T12:12:00+08:00 | in-progress | in-progress | 修复 Reviewy DDD Boundary Review R1 findings（用户指令一批）：行 A 字节级 CLEAN 例外精确化（例外恰为 package.json 两处编辑 + pnpm-lock.yaml kit 移除）；omp 18 升级归行 C 独占并写入行 A/B 非目标、D11 与 DDD；D9 与行 B 逐文件审清单移除 requirements.txt（D8 已锁随包）；DDD omp 宿主措辞修正；本任务去除 stale「不 commit/push/开 PR」（PR #102 已开）、任务序列补行 R、验收改 D1–D13 | 用户 2026-10-19 指令；实测 `git show 4f7388c:packages/omp-sbtd/package.json`（第 47 行 devDep `"@kunolu/sbtd-workflow-kit": "workspace:*"`、第 62 行 `scripts.build` 含 `pnpm --filter @kunolu/sbtd-workflow-kit check-generated`、peer `>=17.3.5 <18`、devDep omp `17.3.5`）；根 `pnpm-lock.yaml` 存在实测；PRD 修订日志 R3 |
