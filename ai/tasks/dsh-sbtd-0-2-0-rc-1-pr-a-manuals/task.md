---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-pr-a-manuals
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "done"
branch: feat/dsh-sbtd-0.2.0-rc.1-pr-a-manuals
created_at: '2026-10-18T09:11:53+08:00'
updated_at: "2026-10-18T10:07:19+08:00"
completed_at: "2026-10-18T10:07:19+08:00"
---

# PR-A manuals：钉 640-skills v2.0.2 + 白名单换 sbtd-task

## 目标
按 PRD `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 A：
- `PINNED_REVISION` → `1d82494d74f6df9bca7dccef2da409f87091883e`（v2.0.2）
- 白名单删 `trellis-workflow`、加 `sbtd-task`
- 按现行规则同步 SKILL.md + 整个 `references/`（含 `task-data.schema.json`）
- MANIFEST 逐文件 sha256；t4 原始字节比对覆盖非 md 的 schema
- 顺手：PRD 表回填行 0（merge SHA `3fafd73` 全长、done 时间）；附录 nit 若低成本可顺手
- 范围外：docs/TODO.md 更新移至 docs/retire-todo 独立 PR（用户决策 2026-10-18），本任务不改 TODO

## Book Gate Plan
| Gate | 触发事实 / 阶段 | 生命周期与结论 |
|---|---|---|
| book-ddd-distilled-modeling | 无新 grill 或领域建模；既有 PRD §2.4 已 confirmed | not-required（本轮）；沿用计划任务边界，不冒称重跑 |
| book-ddia-data-design | schema 仅作为上游只读 blob 镜像；无 schema 语义设计、运行时存储或迁移 | not-required |
| book-legacy-change-safety | pin/白名单配置替换；同步算法不动，已有 T4 隔离 fixture 安全网 | not-required；非 bug 或弱测试高风险修改 |
| book-refactoring-pass | 同步脚本既有配置编辑；应在首次编辑前 | passed（补读后的 proceed / normal；无须重构）；首次编辑前未加载，不能追认事前通过 |
| book-release-readiness | 无运行时、部署、服务或后端算法变更；仅供应链镜像 | not-required；本任务不等于 0.2.0 发布就绪 |

## 实施与检查

- 未完整调用 grill-with-docs：用户步骤与 PRD 行 A 已清楚；无新需求访谈。
- 仅更改脚本 pin/version 与 12 项白名单中的一项；保留 SHA 失败拒绝、复制范围、checksum 校验与原子替换算法。
- `/workspace/640-skills` HEAD 为 `eaf26d3fb05f03bdf1fd5c322ed67ad405429976`，非 pin；实际以无 SOURCE 的 `bash packages/dsh-sbtd/scripts/sync-manuals.sh` 克隆并同步指定 SHA，退出 0。
- 同步后额外读取本地上游 Git object（不切换其 checkout）：19 个落盘文件逐一等于 pin Git blob，sha256 匹配；sbtd-task 全部 7 个 references 与上游树集合相等，含 JSON schema；无 trellis-workflow。
- T4 改用 sbtd-task；隔离 fixture 的 Git cat-file blob 与落盘 Buffer 逐字节比较同时覆盖 SKILL.md 与 task-data.schema.json。删除原 T4 的 README 文案、源码目录枚举和固定手册末字节断言，避免把偶然实现/措辞当契约。
- BDD：沿用 `packages/dsh-sbtd/features/t4-manuals-sync.feature` 中文场景 + 英文关键词，更新 pin、白名单与非 Markdown 字节场景；traceable 到两个 T4 测试文件。非全仓 BDD sync 任务。
- Trellis 后端、t7-trellis 与其它后端路径保持；t5 的 trellis-workflow 仅为拒绝非法 kind 输入/源码禁止引用断言，不依赖已移除手册。
- README pin 已更新；PRD 行 0/A 已更新。独立复核指出「merge commit 加一秒」无独立证据，已改为实际观察的 2026-10-18T09:11:01+08:00，并明示以 merge commit 时间记、非 API merged_at。附录说明锁定摘要优先，R2 Q6 最终 B、原推荐 A 仅历史。
- 范围边界：不修改 src、包版本、peer 或锁文件；不 commit/push/publish。

## 验证证据

- 首次 `cd packages/dsh-sbtd && npm test`：未进入用例，`sh: 1: tsc: not found`。
- 首次 `pnpm install --frozen-lockfile --ignore-scripts`：Corepack 缓存 `/usr/local/share/corepack/v1` 权限错误（EACCES）。
- 改用进程级 `COREPACK_HOME=/tmp/sbtd-pr-a-corepack`，同一 frozen-lockfile 安装命令成功；无全局配置更改，未执行依赖安装脚本。
- `node --test test/t4-manuals.test.mjs test/t4-sync-exit.test.mjs`：6 passed / 0 failed / 0 skipped，退出 0；raw 见 `reports/t4-focused-20261018-092850.txt`。
- `cd packages/dsh-sbtd && npm test`：TypeScript 编译成功，342 passed / 0 failed / 0 skipped，退出 0；raw `reports/package-full-20261018-092920.txt` 与同 stem 中文 `.md`。
- T4 raw 亦已有同 stem 中文汇总；初始环境失败保存在 `reports/environment-blockers.txt` + 同 stem `.md`，不抹去失败轮。
- `bash -n scripts/sync-manuals.sh`：退出 0。额外 `npm run lint`：退出 1，8 项诊断位于 6 个本轮未修改 src 文件（backends/maestro.ts、backends/gitnexus.ts、index.ts、tools/bdd.ts、tools/e2e.ts、tools/task-artifact.ts）；不夹带修复，不称所有检查全绿。
- 独立代码复核 ManualsCorrectness：无 patch-introduced findings；确认运行时只加载保留的 manuals、fixture 原始字节检查有效、改动可读且无多余抽象。StrictAcceptance：PRD 时间 P2 已修正且定点复核通过，无新增 findings；三个 raw/中文汇总的九节结构、数量、失败保留及本地证据边界均确认。仅文档真实性修正，无代码变化，不重跑无影响测试。
- Code Readability Review：手写修改只涉及 pin、白名单和现有 fixture；JSON 使用 Buffer 比较，不解析重写；回调保持多行可读。ponytail-review：Lean already. Ship.
- lessons-record 已评估：本次门禁时序失误由现有 strict 入口与事前 gate 规则直接覆盖，无新增可复用根因知识；不重复建 lesson，不解析或创建身份。
- Graft skipped：配置/镜像变更不需要图；直接源文件与 Git blob 证据足够，未调用图刷新或 wiring。Web/Mobile/API 工具 not-needed；宿主 T0、pack/publish 属后续 PR，本轮未运行。
- 证据边界：developer-local / dirty / local-only，未提交工作树，不能替代宿主提交后 CI。rtk skipped-for-report（保留原生输出）。
- 流程偏差：首次配置编辑前漏读 strict 与 Book gate；已补读并明确记录，非事前 gate 通过。没有因此跳过剩余验证。

## 跟进轮证据（用户/Lord/Reviewy 决策 2026-10-18）

- TODO 退出本 PR：`git checkout origin/main -- docs/TODO.md` 后 blob `012d5a8fe79f3d92efd9ca35d62bbbdc1cbbd3e8` 与 `origin/main`（`3fafd73f828b0f61c3310e4828cfb63bbced3f9a`）一致；`git diff origin/main -- docs/TODO.md` 为空。TODO 更新移至 docs/retire-todo 独立 PR。PRD 行 0/A 文本无 PR-A 的 TODO 提及（行 81 的 TODO 指针属行 D 范围，保留），PRD 无需改动。
- t4 字节比对覆盖 schema 的引用：`packages/dsh-sbtd/test/t4-sync-exit.test.mjs:152` 用例 "sync-manuals preserves SKILL.md and non-Markdown schema blob bytes"，第 180–189 行对 `references/task-data.schema.json` 做 `git cat-file` blob 与落盘文件的 Buffer `assert.deepEqual` 逐字节比较；另 `test/t4-manuals.test.mjs:88-90`（用例 "manuals whitelist and MANIFEST checksums"，第 33 行起）断言 MANIFEST sha256 校验覆盖该 schema 文件。

### trellis-workflow 引用逐条决定表

| 引用位置 | 决定 | 理由（一句话） |
|---|---|---|
| test/t4-manuals.test.mjs:86 `!dirs.includes("trellis-workflow")` | 保留 | 负向断言：已移除手册不得再随包发布 |
| test/t5-review.test.mjs:145 拒绝 kind 列表中的 `"trellis-workflow"` | 保留 | 负向断言：非法 kind 必须被拒绝，不依赖手册存在 |
| test/t5-review.test.mjs:444 src 禁止引用正则含 `trellis-workflow` | 保留 | 负向断言：源码不得引用已移除手册名 |
| features/t4-manuals-sync.feature:10 「不含 trellis-workflow」 | 保留 | 负向场景：与 t4 测试断言对应，手册不再发布 |
| test/t6-clarify.test.mjs / features/t6-sbtd-clarify.feature | 无需改动 | grep 证实无 `trellis-workflow` 引用；其断言的 grilling / grill-with-docs / grill-me 手册仍在白名单并随包发布 |
| test/t7-trellis.test.mjs（及 t8、t14、features 中的 `.trellis` / `backends/trellis.js`） | 保留 | 引用的是 trellis 后端与 `.trellis/` 目录契约，非已移除手册；后端改名/移除属 PR-B 范围，本轮不动 src |

- 复跑计数：`node --test test/t4-manuals.test.mjs test/t4-sync-exit.test.mjs test/t5-review.test.mjs test/t6-clarify.test.mjs test/t7-trellis.test.mjs` = 74 passed / 0 failed / 0 skipped，退出 0（raw `reports/t4-t7-focused-20261018-0944.txt` + 同 stem 中文 `.md`）；`cd packages/dsh-sbtd && npm test` = 342 passed / 0 failed / 0 skipped，退出 0（raw `reports/package-full-20261018-0944.txt` + 同 stem 中文 `.md`）。本轮无 src/测试代码改动，仅文档与 task.md。

### Reviewy r1 pin 修复证据（2026-10-18）

- 问题：`.github/workflows/dsh-manuals-pin.yml` 仍钉旧 640-skills 1.0.15 / `bc8eec1549928fb0966254751b96b611b6334183`，与已同步至 v2.0.2 的 MANIFEST 冲突，CI 报 `AssertionError: 2.0.2`。
- 修复：同一文件三处更新——line 3 注释、line 48–49 `pin_rev` / `pin_ver`、line 66 clone `pin=`，统一为 `2.0.2` / `1d82494d74f6df9bca7dccef2da409f87091883e`；与 `manuals/MANIFEST.json`、`scripts/sync-manuals.sh`（PINNED_REVISION/PINNED_VERSION）、两个 t4 测试的 PIN 一致。
- 遗漏排查：`rg -n "bc8eec15|1\.0\.15" .github packages/dsh-sbtd` 修复后无命中；历史命中无遗留（本轮范围内 docs 不在该两条路径下）。
- 验证：`python3 -c 'import yaml,sys;yaml.safe_load(open(sys.argv[1]))' .github/workflows/dsh-manuals-pin.yml` 退出 0；`cd packages/dsh-sbtd && npm test` = 342 passed / 0 failed / 0 skipped，退出 0。未 commit/push，本地 CI 等价步骤（YAML + npm test）通过不代表宿主 CI 已绿。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-18T09:11:53+08:00 | planned | in-progress | Lord 指示开 PR-A manuals | 群消息 2026-10-18 09:11 |
| 2026-10-18T09:29:20.048103+08:00 | in-progress | checking | pin 同步、T4 schema 字节回归与文档更新已完成，开始全包验证及独立复核 | 19 个 pin blob 与 sha256 校验通过；T4 focused 6 passed；reports/t4-focused-20261018-092850.txt |
| 2026-10-18T09:31:08.453656+08:00 | checking | in-progress | 独立验收复核发现 PRD 行 0 时间为 merge commit 加一秒，应改用实际观察时间并注明依据 | StrictAcceptance P2: docs/prd/dsh-sbtd-0.2.0-rc.1.md:77；Git commit cI=2026-10-18T09:11:01+08:00 |
| 2026-10-18T09:32:10.064183+08:00 | in-progress | checking | 独立验收 P2 时间证据修正完成且定点复核通过，进入最终验收 | ManualsCorrectness 无 findings；StrictAcceptance P2 已关闭；三份 raw 与中文汇总配对校验通过 |
| 2026-10-18T09:32:12.367686+08:00 | checking | done | PR-A 全部指定验收完成；仅本地实现就绪，不代表合并或发布 | pin 同步与19 blob/sha256 smoke；T4 6 passed；npm test 342 passed；bash -n passed；独立复核通过；既有 lint 8诊断/6未改文件已披露；无 commit/push |
| 2026-10-18T09:47:24.530816+08:00 | done | planned | 用户/Lord/Reviewy 2026-10-18 跟进决策明确重开：docs/TODO.md 更新移出本 PR 至 docs/retire-todo；Reviewy 复核 trellis-workflow 测试引用；重跑 t4/t5/t6/t7 与全包测试 | 用户跟进消息 2026-10-18；保留上轮完成证据于本表 |
| 2026-10-18T09:47:24.733238+08:00 | planned | in-progress | 执行跟进项：恢复 TODO 至 origin/main、task.md 范围/证据修订、逐条引用决定表、测试复跑 | git checkout origin/main -- docs/TODO.md；diff 为空 |
| 2026-10-18T09:47:24.935336+08:00 | in-progress | checking | 跟进修订完成，复跑验证完成，进入验收 | t4/t5/t6/t7 74 passed（reports/t4-t7-focused-20261018-0944.txt）；npm test 342 passed（reports/package-full-20261018-0944.txt） |
| 2026-10-18T09:47:25.136691+08:00 | checking | done | 跟进三项决策全部落实；仍仅本地就绪，不代表合并或发布 | TODO 与 origin/main 一致；t4 schema 字节比对引用确认（t4-sync-exit.test.mjs:152/180-189）；74+342 全绿；无 commit/push |
| 2026-10-18T10:04:19+08:00 | done | in-progress | Reviewy r1 blocking：dsh-manuals-pin.yml 仍钉旧 pin 1.0.15/bc8eec15…，CI AssertionError: 2.0.2；用户指示修复 | Reviewy r1 反馈；用户消息 2026-10-18 |
| 2026-10-18T10:06:19+08:00 | in-progress | checking | workflow 三处 pin 统一更新至 2.0.2/1d82494d…；rg 确认 CI/package 范围无其他 live 旧 pin 命中 | dsh-manuals-pin.yml:3,48-49,66；rg -n "bc8eec15\|1\.0\.15" .github packages/dsh-sbtd 无命中 |
| 2026-10-18T10:07:19+08:00 | checking | done | Reviewy r1 修复验收完成；本地验证全绿，仍不代表宿主 CI 或合并/发布 | YAML safe_load 退出 0；npm test 342 passed/0 failed；无 commit/push |
