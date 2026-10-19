---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-prd
workflow_mode: strict
mode_source: user
mode_note: 用户要求 omp-sbtd 0.2.0-rc.1 任务 0 用 strict；PRD 规则为每个任务都用 strict
status: "done"
branch: docs/omp-sbtd-0.2.0-rc.1-prd
created_at: '2026-10-19T11:21:02+08:00'
updated_at: '2026-10-19T20:34:00+08:00'
completed_at: '2026-10-19T13:44:27+08:00'
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
- 任务 A 为纯搬移：`upstream.lock.json` 的 revision 与 `transformVersion=p0-v3` 不变，sourceId `sbtd-workflow-kit-upstream` 不变；CLEAN 门为嵌入 `kit/`、`skills/`、manifest 哈希、`npm pack --dry-run` 文件清单及逐文件 sha256 与 `4f7388c` 构建完全一致（例外恰为三处：package.json 恰好三处编辑——删 devDep `@kunolu/sbtd-workflow-kit`、`scripts.build` 仅替换 kit check-generated 调用为包内入口、新增 devDep `yaml: 2.8.2` 精确钉（build-time only，不进 dependencies；迁入投影脚本读取 `omp-distribution-map.yaml`/`agents-section-map.yaml`，pnpm 严格隔离下须自行声明；4f7388c SBOM 无 yaml 条目，SBOM 不含 devDependencies 故不受影响），peer/devDep omp 钉与 dependencies/files/version 不变；`SBOM.spdx.json` 仅移除 kit 包条目与指向它的那一条 relationship，另允许第 12 行 `documentNamespace` 从 4f7388c 值 `https://kpi.local/spdx/f05806c0a00894a487b4361861770dc18791ab056b7404aa86685b96c711f176` 变为 `https://kpi.local/spdx/${sourceTreeSha256}`（新 digest；实测旧值仅在该行、不在 `validation/p0/compatibility.v2.json` 或任何其他打包文件，为唯一新增打包文件差异），其余逐字节等于 `4f7388c` 构建，行 A 不把迁入代码在 SBOM 中改归属 omp-sbtd（纯搬移，如需改归属属行 B 或 C）；新 digest 必须指定且可复现：`writePluginSpdxSbom` 的输入从 `{ plugin: { name, version }, kit: { name, version, generatedSha256 }, files }` 改为 `{ plugin: { name, version }, kit: { generatedSha256 }, files }`（精确表达式见 PRD 行 A），保留 `kit.generatedSha256`、仅删除 `kit.name` 与 `kit.version`，`plugin`/`files` 部分、canonical 序列化 `stableJson` 与哈希 `digest` 均沿用 4f7388c；明确不放宽：`kit/manifest.json` 第 8 行 `sourceTreeSha256`（a513e976…）是不同的上游来源树 digest，位于 `kit/`、须逐字节不变；根 `pnpm-lock.yaml` 移除 kit workspace 包 importer 并把 yaml importer 条目从 kit 移到 omp-sbtd）；check-generated、p0 validator、SBOM、全部测试绿；行 A 证据必须包含真实 p0 release-validator 运行，证明新值通过 `release-validator.ts` 约第 790 行 documentNamespace 校验与约第 4023/4042 行 candidate/approval 记录一致性校验，记录于行 A 的 `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-a-migrate-kit/task.md`（不是以本次 PRD-only 核验代替）；`docs/spec/sbtd-workflow-kit/` 路径与 conformance matrix 路径同 PR 更新；运行时 zod（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）、p0 `cli.ts` kitRoot 同步更新；SBOM 生成器同 PR 修改（`write-sbom.ts` 第 13–16 行 kitRoot/env `KPI_SBOM_KIT_ROOT`、`release-validator.ts` 第 4320 行 kitSpdxId `SPDXRef-Package-kunolu-sbtd-workflow-kit`、第 4428 行 `join(kitRoot,"package.json")`），停止生成/期待 kit 包节点与其 relationship（两脚本不在 package.json `files` 中，不影响 pack 身份）。
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
| 2026-10-19T12:36:00+08:00 | in-progress | in-progress | 修复 Reviewy 剩余 blocker（用户指令）：行 A CLEAN 门新增第三例外 `packages/omp-sbtd/SBOM.spdx.json`——仅允许删除 kit 包条目（4f7388c 第 6195 行包 `@kunolu/sbtd-workflow-kit`、第 6196 行 SPDXID `SPDXRef-Package-kunolu-sbtd-workflow-kit`）与 relatedSpdxElement 指向它的那一条 relationship（第 8252 行），其余条目逐字节等于 `4f7388c` 构建；明确行 A 不把迁入代码在 SBOM 中改归属 omp-sbtd（纯搬移，如需改归属属行 B 或 C）；PRD §2.1、行 A、§4 与本任务任务 A 验收行同步为「例外恰为三处」；PRD 修订日志 R4 | 用户 2026-10-19 指令（含 `4f7388c:packages/omp-sbtd/SBOM.spdx.json` 实测行号 6195/6196/8252）；PRD 修订日志 R4 |
| 2026-10-19T13:06:00+08:00 | in-progress | in-progress | 并入 Researchy 两项实测 findings（用户指令）：行 A package.json 例外由恰好两处编辑改为恰好三处编辑——新增 (c) devDep `yaml: 2.8.2` 精确钉（build-time only、不进 dependencies；4f7388c kit 包 dependencies 含 yaml 2.8.2/zod 4.1.12、devDep tsx 4.20.6，omp-sbtd 已有后两者但无 yaml；4f7388c SBOM 无 yaml 条目，SBOM 不含 devDependencies，(c) 不影响 SBOM）；根 `pnpm-lock.yaml` 例外明确为移除 kit workspace 包 importer 并把 yaml importer 条目从 kit 移到 omp-sbtd；SBOM 生成器同 PR 修改明确化（`write-sbom.ts` 13–16 kitRoot/env `KPI_SBOM_KIT_ROOT`；`release-validator.ts` 4320 kitSpdxId、4428 `join(kitRoot,"package.json")`；删 kit 后 build 会直接失败，须同 PR 停止生成/期待 kit 节点与其 relationship；两脚本不在 files 中，不影响 pack 身份）；PRD §2.1、行 A、§4 与本任务任务 A 验收行同步更新 | 用户 2026-10-19 指令（Researchy 实测：4f7388c kit 包依赖与 omp-sbtd 依赖、4f7388c SBOM 无 yaml 条目、write-sbom.ts/release-validator.ts 行号）；PRD 修订日志 R5 |
| 2026-10-19T13:44:27+08:00 | in-progress | done | 用户批准「开始 A 行」（2026-10-19 13:42 +08:00）并指令回填：行 0 由 PR #102 squash-merge 完成，任务 0 转 done | 用户 2026-10-19 指令；PR #102 merge SHA `1d9a5cd1d36c64381b1a95f8254fd217f2bcdba5`（merge commit 时间 2026-10-19T13:39:54+08:00）；PRD 任务表行 0 已回填 done |
| 2026-10-19T14:40:10+08:00 | in-progress | in-progress | R6：并入 Researchy finding（SBOM documentNamespace 须随新来源 digest 更新）与 Reviewy 核验（旧值仅在 4f7388c SBOM 第 12 行，为唯一新增打包文件差异）；明确可复现 digest 规则（保留 kit.generatedSha256、仅移除 kit.name/version，plugin/files 与 canonical 序列化、哈希不变）、kit/manifest.json 上游 digest 不放宽、行 A 真实 p0 证据要求；用户 14:14 决定「先单独开」，本次仅两份文档与一个 commit，不回填行 0、不改任务表状态列、不 push/不开 PR | 用户 2026-10-19 14:14 +08:00 决定及本次指令；当前修订分支 `docs/omp-sbtd-0.2.0-rc.1-prd-r6` 基于 main `1d9a5cd`；实测 `git show 4f7388c:packages/omp-sbtd/SBOM.spdx.json` 第 12 行、全树检索仅命中该文件；`git show 4f7388c:packages/omp-sbtd/kit/manifest.json` 第 8 行；`git show 4f7388c:packages/omp-sbtd/scripts/p0/release-validator.ts` 第 790、4023、4042、5420/5440–5450 行；PRD 修订日志 R6。TaskStore.rebind 因仓内记录 `task state event fails the bundled stateEvent schema` 未写入，保留原 branch 元数据；本次事件是显式要求的文档记录，不声称自动恢复已重绑定 |
| 2026-10-19T15:39:43+08:00 | done | done | 更正（不改写上一条）：上一条 R6 事件中「不 push/不开 PR」的措辞已过时——R6 PR 实际已开出为 PR #103 并经 Reviewy 评审后由 Lord squash-merge 为 main `c7356291047a436cf1feae99a9d5fbe71dea1267`（merge commit 时间 2026-10-19T15:11:54+08:00）；行 A 分支已 rebase 到 `c735629` | 用户 2026-10-19 指令；`git log -1 --format='%cI %H' c735629` = `2026-10-19T15:11:54+08:00 c7356291…`；行 A 分支 `git reflog` rebase (finish) 2026-10-19T15:26:01+08:00 |
| 2026-10-19T20:34:00+08:00 | done | done | R7（PRD-only，docs 分支 `docs/omp-sbtd-0.2.0-rc.1-prd-r7-p0-v4`，基于 main `f1bba41`）：裁决行 B CONTRACT-CHANGE-NEEDED——用户 2026-10-19 ~20:31 +08:00 选定 option 2（团队投票 4× option 2），行 B transformVersion 升 `p0-v4` 并授权 D14 三项 transform 变更（门禁豁免扩为 digest 绑定 canonical onboard runtime 包路径集；CANDIDATES 删 trellis-workflow；overlay catalog 删 trellis 两项、增 sbtd-task，不推迟行 C）；PRD 任务表回填行 A done（#104 / `f1bba41d168af04807914914ad8dce27dfc8688b` / 2026-10-19T17:13:57+08:00），行 B 状态改 in-progress（待本 PRD 合并后解除 blocked）；不改 packages/、不跑 sync、不 push、不开 PR | 用户 2026-10-19 ~20:31 +08:00 指令（option 2，团队投票 4×）；行 B blocked 证据 `feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream` tip f420cc4 任务记录（PROJECTION_FORBIDDEN_TOKEN 1 pathViolation + 19 payloadViolations；CANDIDATES trellis-workflow blocked/ENOENT；新 sourceTreeSha256 `c1fc3f679c375a22c6272de92c3377ac04ea8edb996acd314ea76f73257739b0`）；PRD 修订日志 R7；R7 任务记录 `ai/tasks/omp-sbtd-0-2-0-rc-1-prd-r7-p0-v4/task.md` |
