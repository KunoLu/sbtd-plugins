---
schema_version: 1
id: sbtd-rc2-closeout
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict 收尾；四个逻辑提交；主会话唯一 writer；仅授权本地提交，不授权远端写入或发布。
status: done
branch: chore/omp-sbtd-rc2-closeout
created_at: '2026-10-23T21:12:56+08:00'
updated_at: '2026-10-23T22:31:43+08:00'
completed_at: '2026-10-23T22:31:43+08:00'
---
# SBTD rc.2 closeout

## 请求、范围与授权

- 用户 2026-10-23 21:06 +08:00 群内要求收尾提 PR，Lord 记录。
- 用户 2026-10-23 21:07 +08:00 群内要求仓内所有 README 和 CHANGELOG 更新到最新并集成到本 PR，Lord 记录。
- 用户 2026-10-23 21:08 +08:00 群内确认（PRD 任务状态同步并入收尾 PR），Lord 记录。
- 用户 2026-10-23 21:09 +08:00 群内要求 SBTD tasks 状态更新为最新（应均为 done），Lord 记录。
- 用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录。
- 编排方整理：本次执行边界为四个本地逻辑提交；禁止 push、开 PR、评论、tag、publish、release、merge、版本 bump、全局配置／全局 omp 修改。交付归属为由 chore/omp-sbtd-rc2-closeout 分支的 PR 交付，不预填 PR 编号。
- 基线 `origin/main` / `2393d10c3fb1a1f3cb756a351297a430fd2afc81`；入口工作树干净、实际分支匹配。旧任务获明确历史回填授权，保留历史 branch，不重绑定。
- 历史 task 事件、日期记录、per-run 验证、PRD 日期修订、既有 CHANGELOG 文本均追加式保留；只改允许的当前状态字段。不改 decisions、D/R 编号、contract、schema、peer、versions、lockfile。
- 未完整调用 grill-with-docs：需求、归因、提交边界与验收已明确，无新领域歧义。
- 路径安全与 ignore 已核对：ai/tasks 正常且可跟踪；`.sbtd` 和本任务 reports 受保护、未跟踪。沿用既有 TaskStore 全库历史 schema blocker，不重跑已知失败；本记录为明确要求的共享 Markdown 交付，不声称 helper lifecycle 或自动恢复通过，不写 active/developer/handoff/ignore。
- 主会话唯一 writer／验证 controller；DocsAudit、StatusAudit 只读调查，后续独立 review 只读。Graft=skipped：没有已验证受管连接，使用源码、Git、GitHub、npm 证据。rtk=skipped-for-report：原生命令保留报告。

## 四提交计划

1. #124 merge、FINAL 模型表、rc.2 release 回填；现有真实 pack 测试增加 `README.zh.md` 存在且 `README_zh.md` 不存在的断言；本任务及 index。编排方整理：OMP 自提 nit。
2. 根 README Roadmap／路线图更新；rc.2-prep checking → done，completed_at 采用 #124 GitHub mergedAt `2026-10-23T20:39:30+08:00`（与 `%cI` 的 20:39:29 分开记录）。`docs/prd/ROADMAP.md` 的 D12 archive 保持独立 chore，不移动。
3. 全仓自有 README／CHANGELOG 事实对齐；包内文档变化通过既有 build 生成 SBOM，再验证实际 tarball。保留根 `README_zh.md` 文件名。
4. PRD 仅当前状态字段同步；全任务状态扫尾；六处历史 blocked／ready 用追加状态补记，不改旧结论。扫尾不另建第五提交。

本任务最终保留 checking / completed_at null，直到本分支 PR 合并。用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、新业务规则或领域歧义 | before-dev | not-required |
| book-ddia-data-design | 仅既有文档／历史记录；无 schema、持久化机制或数据流设计变化 | before-dev | not-required |
| book-legacy-change-safety | 无运行时行为修复；断言使用既有真实 tarball 场景 | before-dev | not-required |
| book-refactoring-pass | 不修改生产代码，仅测试断言、文档与生成 SBOM | before-dev | not-required |
| book-release-readiness | 已发布状态记录与包内容一致性核对；不部署、不更改运行时 | finish | passed（ready，仅本次收尾交付；真实 pack/check、文档与历史边界、独立复核通过，不是发布授权） |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T21:12:56+08:00 | planned | in-progress | 编排方整理：建立 strict 收尾记录 | 实际分支／基线／路径／ignore 与 npm、GitHub 初次核验通过 |
| 2026-10-23T21:31:41+08:00 | in-progress | checking | 编排方整理：四类修改已实现，包测试／实际 tarball／历史边界检查通过，进入最终独立复核及提交绑定 | omp 917 passed / 3 env-gated skipped；dsh 342 passed；packed check 472 files；8 task YAML；旧历史保留及 PRD 单元格边界通过；用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录 |
| 2026-10-23T22:31:43+08:00 | checking | done | 用户 2026-10-23 21:15 +08:00 群内确认（合入后补该项回填 commit），Lord 记录；编排方整理：#125 已 squash-merge | 编排方整理：PR #125 https://github.com/KunoLu/sbtd-plugins/pull/125，merge SHA `d7d799b8b1e5aa91d986f74119b9d2d4e4c3b993`（`gh pr view 125 --repo KunoLu/sbtd-plugins --json mergedAt,mergeCommit`）；Git `%cI` = `2026-10-23T22:31:43+08:00`（`git show -s --format=%cI d7d799b`）；GitHub mergedAt = `2026-10-23T22:31:43+08:00`（原值 `2026-10-23T14:31:43Z`）；Reviewy CLEAN @ `234416d`（编排方整理）；CI run 39968589728 `omp-runtime-linux-probe`，head `234416db963660501a7e5b2f4575d768baff492c`，success，1/1 job success（`gh run view 39968589728 --repo KunoLu/sbtd-plugins --json conclusion,headSha,jobs`） |

## 事实核验（2026-10-23T21:12:56+08:00）

- `gh pr view 124 --json number,mergedAt,mergeCommit,url`：#124 squash `2393d10c3fb1a1f3cb756a351297a430fd2afc81`；GitHub mergedAt `2026-10-23T20:39:30+08:00`。`git log -1 --format='%H %cI' 2393d10`：`2026-10-23T20:39:29+08:00`。
- `npm view @kunolu/omp-sbtd dist-tags time dist --json`：latest=next=`0.2.0-rc.2`；npm time `2026-10-23T12:44:10.098Z`（20:44:10 +08:00）；dist.shasum `543fa7c3decdb0f6ca8faef98e90bd6eff3ad362`，dist.fileCount 472。
- `npm view @kunolu/dsh-sbtd dist-tags time --json`：latest=next=`0.2.0-rc.2`；npm time `2026-10-23T09:08:50.745Z`（17:08:50 +08:00）。完整版本清单与双语 CHANGELOG 覆盖核对随文档审计记录。
- `gh release list --limit 20`：omp/dsh 的 rc.1、rc.2 共四项，全部 prerelease；omp rc.2 publishedAt 20:41:17、dsh rc.2 17:55:13（均 2026-10-23 +08:00）。`gh api repos/KunoLu/sbtd-plugins/releases/latest` 返回预期 HTTP 404（命令 exit 1），无 latest release，不是 npm latest 不存在。
- `git for-each-ref`：omp rc.2 annotated tag object `d22a877b449cfde587f2f0041ab27256176df765` → `2393d10`，tagger `2026-10-23T20:40:57+08:00`。GitHub created_at 同时刻；published_at 晚 20 秒。
- 两个 tag-bound omp README 链接用 `curl -L` 均 HTTP 200。
- `gh run view 39954216679 --json headSha,conclusion,jobs`：head `7432be486b42c3b7326ed1b0574d0bab38b30739`，conclusion success，1/1 job success。这是 #124 历史 CI，不冒充本轮执行。
- `gh pr view 120/122/123/93` 分别核验：#120 `67465db93e7c6f1e6f5f43704c1d4c22ae74306d` 2026-10-23 17:56:19；#122 `684387835b27d46b3b96b01f2015e42fe7937b12` 18:58:43；#123 `008cea74dfbab5ce2c688c2c42e4bd8cfeddfe5f` 20:01:45；#93 `3fafd73f828b0f61c3310e4828cfb63bbced3f9a` 2026-10-18 09:11:01（均 +08:00）。
- 上述可在线重核的事实与编排方整理一致；模型调用、Reviewy CLEAN、发布操作者与发布前 clean worktree 操作属于编排方整理的历史记录，不冒充本轮重新执行。

## 验证计划

执行 frozen install；omp typecheck/lint/build/test/smoke、pack、packed check；dsh typecheck/build/test、双包 npm pack dry-run；新增行归因、冲突、YAML、历史保留、版本／lockfile／tag 不变检查。所有报告保留原始输出与同 stem 中文汇总；最终 HEAD 用输入哈希绑定证据，不将 dirty 本地验证称为 CI 或真实宿主 full-stack。

## README／CHANGELOG 审计与包验证（2026-10-23，编排方整理）

| 文件 | 旧 → 新／核对结果 | 依据 |
|---|---|---|
| `README.md` | omp 未发布条件句、dsh rc.1/旧 latest → 两包 rc.2 next+latest；Roadmap 增 session_compact 已交付；dsh v1.1 → v1.2 前代设计 + 当前 PRD 任务表 | npm time/dist-tags、GitHub prerelease、#120/#122/#123、dsh PRD 0–G |
| `README_zh.md` | 与英文同步；根文件名不变 | 同上；命令块镜像一致 |
| `packages/omp-sbtd/README.md` | 发布后才可用 → npm 已发布 20:44:10 +08:00；peer >=18 <19、实测 18.11.1 不变 | npm time/dist-tags、package manifest |
| `packages/omp-sbtd/README.zh.md` | 与英文同步 | 同上 |
| `packages/omp-sbtd/CHANGELOG.md` | rc.2 条目末尾追加 tag、prerelease 20:41:17、npm 20:44:10、next/latest；原准备日期句及旧条目全部保留 | Git/GitHub/npm；10/10 npm 版本均有条目 |
| `packages/omp-sbtd/CHANGELOG.zh.md` | rc.2 末尾追加中文镜像；旧文保留 | 同上 |
| `packages/dsh-sbtd/README.md` | 安装节补 rc.2 npm 17:08:50、next/latest、prerelease 链接；保留 @next 指引 | npm/GitHub；不新增安装策略 |
| `packages/dsh-sbtd/README.zh.md` | 与英文同步 | 同上 |
| `packages/dsh-sbtd/CHANGELOG.md` | rc.2 条目末尾追加 tag、prerelease 17:55:13、npm 17:08:50、next/latest | Git/GitHub/npm；5/5 npm 版本均有条目 |
| `packages/dsh-sbtd/CHANGELOG.zh.md` | rc.2 末尾追加中文镜像；旧文保留 | 同上 |
| `docs/assets/dsh/README.md` | 当前索引：旧插件/宿主/manuals 钉 → rc.2 / 0.2.0-rc.2 / 2.0.2 + 1d82494d；标明旧 CI 笔记历史边界 | 标题无快照标识、链接当前 PRD；git log 有 ae636e8 版本更新和 ce8e23a 活队列迁移；package.json 与 manuals/MANIFEST.json |
| `packages/omp-sbtd/validation/p0/evidence/README.md` | 已核对无需改 | 仅 append-only evidence 布局／信任边界，无发布版本状态；不改 ledger 契约 |

- 全仓 README／CHANGELOG 名称盘点的其余内容均 out of scope，逐组列明：`packages/omp-sbtd/upstream/vendor/sbtd-workflow-kit-upstream/{README.md,README.zh.md,CHANGELOG.md,CHANGELOG.zh.md}`；该 vendor 下 `sbtd-workflow-onboard/templates/skills/web-ui-autotest-generator/{README.md,README.zh-CN.md}` 与 `docs/lessons/archive/README.md`；`packages/omp-sbtd/upstream/{omp-overlays,generated,generated-omp}/onboard/runtime/templates/skills/web-ui-autotest-generator/{README.md,README.zh-CN.md}`；`upstream/generated-agent-plugin/skills/web-ui-autotest-generator/{README.md,README.zh-CN.md}`；`packages/omp-sbtd/{kit/onboard/runtime/templates/skills,skills}/web-ui-autotest-generator/{README.md,README.zh-CN.md}`。它们为上游／模板／生成镜像，不把插件发布状态写入上游内容；dsh manuals 盘点无 README／CHANGELOG。没有遗漏其他自有 README。
- dsh 的 `@next`、不用裸名／`@latest`／GitHub 路径是既有安装指引，而非 registry 事实；保留指引与命令，仅纠正 latest 的实际值。omp 原精确 RC 建议同样保留。
- npm 版本覆盖：omp `0.1.0-rc.{1,2,6,10,11,12,13,14}`、`0.2.0-rc.{1,2}`；dsh `0.1.0-rc.{1,2,3}`、`0.2.0-rc.{1,2}`，双语条目均齐全，逐条事实由既有历史条目保留，不使用变更不可考占位。完整 npm time 原始结果为 `reports/{omp,dsh}-registry.json`；与编排方整理时间清单一致。
- 专用 grep 等价执行所要求旧措辞检索：根和 package README 零命中；`docs/assets` 仍有三处历史文件命中：`dsh/ci-640-skills-adapt.md:3`、`dsh/ci-dsh-host-compat.md:3`、`omp/SBTD_OMP_SBTD_Agent_Plugins_1.0_Migration_Plan.md:1516`。前两者为 FU5/0.1.x 版本指南（Git 最后更新 2026-09-18 / #87、09-14 / #83），后者为明确 2026-08-20 日期历史；本任务只审计 README/CHANGELOG，不重写这些历史。当前 dsh 索引已明确以 workflow 与活 PRD 为准。
- 文档 smoke：MarkdownIt CommonMark + table 实际渲染 12/12 文件；三对 README fenced commands 逐字一致；双语 changelog npm 版本覆盖 omp 10/10、dsh 5/5。PublicationReview 独立只读结论 **correct / 无 qualifying findings**，确认新增 release 事实镜像、旧 CHANGELOG 零删除、pack 断言复用已有真实 tarball、SBOM 三个文档 checksum 与 namespace 一致。其检查范围不包含历史 docs/assets 全量 grep，以上三处保留命中以主会话实际结果为准。
- **发布物差异边界**：由本分支 PR 交付后，main 的 omp `README.md`／`README.zh.md`／`CHANGELOG.md` 及 SBOM、dsh README/CHANGELOG 四文件将与已经发布的 `0.2.0-rc.2` tarball 不同，直到下一次发布。已发布 tarball 不可覆盖；不 bump、不 publish、不把本轮新 tarball 当作已发布物。

### 实际验证结果

所有命令使用 `COREPACK_HOME=/home/box/.cache/node/corepack`、`PYTHONDONTWRITEBYTECODE=1`；原始 stdout/退出码/命令/实际 HEAD/时间与同 stem 九节中文汇总保留 `reports/*.json/.md`。Evidence Source=developer-local、Source Revision=dirty、Evidence Publication=local-only；不是 CI 或真实模型 full-stack。

| 命令 | 实际结果 | 报告 stem |
|---|---|---|
| `pnpm install --frozen-lockfile` | exit 0；pnpm 11.17.0；lockfile 无需更新 | install |
| `pnpm --filter @kunolu/omp-sbtd typecheck` | exit 0 | omp-typecheck |
| `pnpm --filter @kunolu/omp-sbtd lint` | exit 0；99 files，0 fixes | omp-lint |
| `pnpm --filter @kunolu/omp-sbtd build` | exit 0；既有 write-sbom.ts 自动生成，无手改 hashes | omp-build |
| `pnpm --filter @kunolu/omp-sbtd test` | exit 0；46 files，917 passed / 0 failed / 3 skipped；338.16s runner / 342.25s command | omp-tests |
| `pnpm --filter @kunolu/omp-sbtd smoke` | exit 0；compiled extension 12 个命令／事件阶段 | omp-smoke |
| `../../node_modules/.bin/tsc -p tsconfig.json --noEmit`（dsh 包目录） | exit 0 | dsh-typecheck |
| `pnpm --filter @kunolu/dsh-sbtd build` | exit 0 | dsh-build |
| `TMPDIR=/tmp GIT_CEILING_DIRECTORIES=/tmp node --test test/*.test.mjs`（dsh 包目录） | exit 0；342 passed / 0 failed / 0 skipped；6056.79ms | dsh-tests |
| `npm pack --dry-run --json`（两个包各执行） | omp 472 files；dsh 103 files；均 exit 0 | omp-dry-pack / dsh-dry-pack |
| `pnpm --filter @kunolu/omp-sbtd pack --pack-destination <tmp> --json`；安全解包；`pnpm --filter @kunolu/omp-sbtd exec tsx scripts/p0/cli.ts check-package --packed <tmp>/package` | 均 exit 0；packedFileCount 472；中文 README 与源码字节一致，旧名不存在 | omp-actual-pack / omp-packed-check |
| `pnpm --filter @kunolu/dsh-sbtd pack --pack-destination <tmp> --json` | exit 0；实际 tarball 含 dist/index.js，四个 shipped 文档与源码字节一致；沿用 dsh-host-compat 的 pack-dist 门，无 dsh SBOM/check-package 等价脚本 | dsh-actual-pack |

- 新 omp sourceTreeSha256 `8a6bf2cc7640fe55cda562dfe0094b327d683fa75a4d9a4e43b85782554139f8`；SBOM SHA256 `4840dbc483308e30bd29861961e9ebad14915f000a4933847976e2fe4ad61d67`；实际 pnpm tarball SHA256 `9b830083906ac7a52897987e03a1b89f2db1b16a4e6aa9dc9bacb574b61bc565`。npm dry-pack omp shasum `0ec574a075ca6a05f3fc8b43073a7b2a02133fcf`；dsh `7e9dd6a5602c672b7e4b6a236564d7962354e039`。
- 从 npm registry 只读下载已发布 omp tarball 并计算 SHA256，实得 `3b6c696e15798146251712498672f92bc01a089d3e536273d00ec3d23f49604b`，与编排方整理一致；该旧包不是本轮新文档包。临时 pack／解包目录已清除。
- 3 skipped：upstream transform 两项缺 `KPI_PROMOTION_SOURCE_ROOT`，host-event 一项需 `SPIKE_OMP_BIN` / `HOST_EVENT_PLUGIN_TARBALL`。本轮不新增 runtime，不重复真实宿主 live／CI；#123/#124 CI 是经 gh 重核的历史证据。DSH/root lint 的既有失败不重跑确认，未触及 src，不声称这些 lint 通过。
- Code Readability Review：仅两条沿用 `entries` 的明确断言，无第二次 pack、无新抽象／fixture。BDD=traceable（既有中文 Scenario + 英文关键词），pack 场景随完整 suite 执行；无新 .feature。Cross-repo context/API Contract=not-needed；Mock Strategy=contract-backed（既有套件，无新 mock）。Web/Mobile=not-needed；Graft=skipped；rtk=skipped-for-report。

## PRD 当前状态逐项核对（2026-10-23，编排方整理）

| 文件:行（本轮结果） | 旧状态 → 新状态／核对结果 | 依据 |
|---|---|---|
| `docs/prd/omp-sbtd-session-compact.md:3` | PRD-only、代码/CI/硬失败未执行 → (a)/(b)/(c) 完成并随 rc.2 发布 | #120/#122/#123 合并；#123 `008cea74dfbab5ce2c688c2c42e4bd8cfeddfe5f`，2026-10-23 20:01:45 +08:00；tag/npm |
| 同文件 `:136`，步骤 (a) | 决定已交付但仍带代码未执行 → done，补 #122 SHA/18:58:43 +08:00 | #122 `684387835b27d46b3b96b01f2015e42fe7937b12` |
| 同文件 `:137`，步骤 (b) | 未开始 → done | #123 SHA/20:01:45 +08:00；CI run 39949600365 success |
| 同文件 `:138`，步骤 (c) | 未执行 → done，main 恢复 HANDOFF_EVENT_UNOBSERVABLE 硬失败，rc.2 已发布 | #123；Git %cI = GitHub mergedAt；#124 与 npm/tag |
| 同文件 `:144` | 追加新日期更新；旧 :140/:142 原样保留 | 21:08 确认；#123/#124、rc.2 tag/prerelease/npm |
| `docs/prd/omp-sbtd-0.2.0-rc.1.md:66–73` | 0/A/B/C/D/R/E/F 均 done：已核对无需改 | 既有 #102/#104/#106/#107/#108/#109/#114/#115 合并字段；本轮不改旧验收 |
| 同文件 `:120` | 缺 rc.2 后续记录 → 追加「状态同步（编排方整理）」修订行，不新增 R 编号 | #123、#124、tag omp-sbtd-v0.2.0-rc.2、prerelease 20:41:17/npm 20:44:10 +08:00 |
| `docs/prd/dsh-sbtd-0.2.0-rc.1.md:78–85` | 0/A/B/C/D/E/F/G 均 done：已核对无需改 | 既有合并记录；G 状态格末尾已补「前述未知为历史快照」，故不重写它；#118 548a0bf / 17:03:32 +08:00 与发布核验一致 |
| `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md` | 已核对无需改 | 前代版本设计／宿主 rc.2 引用，不是本轮插件 0.2.0-rc.2/session_compact 当前状态表 |
| `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md` | 已核对无需改 | 前代设计基线，活进度已迁至 dsh rc.1 PRD；不改合同／验收／历史现状 |
| `docs/prd/ROADMAP.md` | 已核对无需改，不移动 | D12 archive 明确独立 chore；根 README Roadmap 才是本轮状态面 |

PRD 归因：用户 2026-10-23 21:08 +08:00 群内确认（PRD 任务状态同步并入收尾 PR），Lord 记录。机器核对：session PRD 恰好删除／替换 4 条旧当前状态行（header + a/b/c），三行任务内容列逐字相等；omp rc.1 PRD 零删除，仅追加新日期修订。D/R、contracts、acceptance、non-goals、既有日期行均未改。

## 全任务状态扫尾（2026-10-23，编排方整理）

扫描范围为全部 `ai/tasks/*/task.md`，不含 archive；30 个原有任务 + 1 个新收尾任务。旧值取 `origin/main`；新值取本轮文件，YAML 解析 frontmatter 并按文件顺序识别事件行，包含 dsh plan 孤立附录事件（不是 TaskStore lifecycle 操作）。只有两个原有任务最后事件不是 done，与编排方整理一致。

| task id | 旧 frontmatter / 最后事件 → 新 | 处理 |
|---|---|---|
| docs-retire-todo | done/done → done/done | 已核对无需改 |
| dsh-host-smoke-version-assert | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-1-docs-changelog | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-1-plan | done/in-progress → done/done | 仅在最后附录链追加 done；#93 3fafd73 / 2026-10-18 09:11:01 +08:00；不重复主表、不改 frontmatter |
| dsh-sbtd-0-2-0-rc-1-pr-a-manuals | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-1-pr-b-backend | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-1-pr-c-host | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-1-pr-e-release | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-1-prd-f-backfill | done/done → done/done | 已核对无需改 |
| dsh-sbtd-0-2-0-rc-2-pr-g-readme | done/done → done/done | 状态已核对无需改；追加两处历史门禁补记 |
| dsh-sbtd-prd-readme-zh-shipped | done/done → done/done | 已核对无需改 |
| dsh-sbtd-readme-host-pin-0-2-0-rc-2 | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-d11-d9-sync | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-pr-a-migrate-kit | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-pr-b-sync-upstream | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt | done/done → done/done | 状态已核对无需改；追加历史门禁补记 |
| omp-sbtd-0-2-0-rc-1-pr-d-changelog | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-pr-e-release | done/done → done/done | 状态已核对无需改；追加历史门禁补记 |
| omp-sbtd-0-2-0-rc-1-pr-r-readme | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-prd | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-prd-d11-dated | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-prd-d4-release-docs | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-prd-f-backfill | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-1-prd-r7-p0-v4 | done/done → done/done | 已核对无需改 |
| omp-sbtd-0-2-0-rc-2-prep | checking/checking → done/done | 提交 2；#124 + rc.2 发布；completed_at 取 GitHub mergedAt 20:39:30，不取 %cI 20:39:29 |
| omp-sbtd-offline-cache-smoke | done/done → done/done | 已核对无需改 |
| omp-sbtd-session-compact-code | done/done → done/done | 已核对无需改 |
| omp-sbtd-session-compact-decisions | done/done → done/done | 状态已核对无需改；追加历史门禁补记 |
| omp-sbtd-session-compact-prd | done/done → done/done | 状态已核对无需改；追加历史门禁补记 |
| sbtd-changelog-backfill | done/done → done/done | 已核对无需改 |
| sbtd-rc2-closeout | 新建 → checking/checking | completed_at null；用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录 |

### 六处历史门禁补记

| 旧文件:行（均相对 ai/tasks） | 旧结论 | 追加解决证据／边界 |
|---|---|---|
| `omp-sbtd-0-2-0-rc-1-pr-e-release/task.md:122` | blocked（实际发布） | #114/tag/npm rc.1 已发布；当前 rc.2 亦发布。Bun 旧失败由 #116 后续修复，不追改旧轮 PASS |
| `omp-sbtd-session-compact-decisions/task.md:54` | blocked（后续稳定实现设计） | #123 008cea7 / 20:01:45 +08:00，CI 39949600365 success；code task 真实 live／负例证据解除后续等待 |
| `omp-sbtd-session-compact-prd/task.md:79` | blocked（稳定设计与实现） | #122 6843878 / 18:58:43 +08:00 决定，#123 实现／live；不声称草案当轮 DDIA 重跑 |
| `dsh-sbtd-0-2-0-rc-2-pr-g-readme/task.md:67` | blocked | U2/#119 9ad277c / 16:37:30 +08:00 解命名冲突；#118 合并、npm 17:08:50、tag 17:55:10、prerelease 17:55:13；旧 lint 未证明通过 |
| 同文件 `:151` | blocked（Align） | 发布等待解除；双语链接本轮 HTTP 200；lint 11/44 errors 没有新通过证据，**仍未解除**，不改判整个旧 review |
| `omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt/task.md:129` | Release Readiness blocked | 本文后续 D11 install-path gate/独立核对、#107 合并、#116 offline 修复、#123 handoff 完成及 rc.2 发布；保留原失败和当轮认证边界 |

六条旧 blocked 原文未重写；状态补记不添加多余 done 事件。扫尾归因：用户 2026-10-23 21:09 +08:00 群内要求 SBTD tasks 状态更新为最新（应均为 done），Lord 记录。

## 最终审查、检查与交付边界（2026-10-23，编排方整理）

- HistoryReview 独立只读结论 **correct**：PRD 仅 header／a/b/c 当前状态列及追加日期记录，旧任务历史保留，30+1 任务扫尾与主会话一致；唯一 P3 为 `docs/assets/dsh/README.md:6` 方位词，下列 → 上述，已纳入提交 3，不影响任何 package 验证输入。PublicationReview **correct / 无 qualifying findings**。原始 review 与中文汇总位于 `reports/{PublicationReview,HistoryReview}.json/.md`。
- 静态检查：24 个改动文件；8 份 changed task YAML 均可解析；新增行归因禁词 0、冲突标记 0；所有旧 task 正文与事件按有序子序列逐字保留；四份 CHANGELOG 旧文本全部保留。PRD 当前状态删除白名单仅 session header + a/b/c，内容列不变；omp rc.1 PRD 只有追加。`pnpm-lock.yaml`、全部 package.json/plugin.json、`docs/prd/ROADMAP.md` 与 origin/main 无差异。
- 文档实际渲染和新增相对链接验证通过：12/12 README/CHANGELOG，20 个新增相对链接目标存在；三个双语 README 命令块逐字一致。最后方位词修正不改变链接或代码块。
- `git diff --check origin/main` 与 `git diff --check origin/main..HEAD` 已执行 exit 0；tag 清单保持入口四个既有 tag，没有新建 tag。最终提交后同范围检查及 clean worktree、四提交列表、输入 SHA256 绑定结果另存 `reports/final-input-binding.json/.md` 并在交付对话报告，不在提交内预填自身 SHA。
- 全部 2055 个 tracked package／workspace 验证输入已保存 SHA256 于 `reports/validation-inputs.json`；最终 Git blob 逐项相等才复用本轮 suite 结果。该绑定是本地结果与源码的一致性证明，不是重跑测试或 CI，也不升级历史 full-stack／认证结论。
- Release Readiness Review：**ready（仅收尾交付）**。生产面仅包内文档，漂移风险由自动 SBOM、真实 tarball、packed validator、文档镜像核对覆盖；无服务、容量、背压、迁移或新监控适用项。四个范围内提交可逐项回退，未执行回退；npm 已发布物不可覆盖。剩余限制为 main 与已发布 rc.2 文档不同、历史 DSH lint 未证明通过、3 个 env-gated skip，以及 TaskStore 历史 schema blocker；没有权限或事实缺口被伪装为通过。
- 检查状态：Final Test Report=generated、Run Summary MD=generated、Final Full Rerun=passed（本轮计划包测试范围）、Targeted Rerun=not-needed；真实宿主 live／新 CI／Web/Mobile=未执行（无 runtime/UI 变化且不冒充历史运行）。不产生新长期 lesson，未读取／建立身份，未改全局配置。
- 与编排方整理可重核事实无差异：npm tags/time、GitHub prereleases、tag object/time、merge SHA/time、#124 CI 与已发布 omp tarball SHA256 一致。模型 FINAL/title-gen/Reviewy 历史统计标明编排方整理，未假称独立重跑。审计 scout 的 shell 在其环境不可用，registry/merge/pack 验证均由主会话实际执行；未据此缩减验证。
- 偏差与明确保留：无第五提交；提交 2 写 prep done；D12 archive 不执行；DSH 安装策略不变；旧措辞检索的三处历史文件命中已逐文件解释；dsh lint 及原已知失败不重跑确认；没有为 docs-only 变更新增生产重构、schema 或契约修改。TaskStore 既有 blocker 使 helper lifecycle／自动恢复仍未获证明，交付为已校验共享 Markdown 记录。
- 最终 task 保持 checking / completed_at null；由 chore/omp-sbtd-rc2-closeout 分支的 PR 交付。用户 2026-10-23 21:15 +08:00 群内确认：合入后补一个仅改本收尾 task 状态的回填 commit，Lord 记录。

## fix3（2026-10-23，编排方整理）：Reviewy #125 @ a443f35 NOT CLEAN

### 范围、归因与门禁计划

- 起点 `a443f35869886d71dac1cd55ed38d43e03198b8e`，分支 `chore/omp-sbtd-rc2-closeout`，入口工作树干净；沿用 strict。此次授权只在该基线上新增一个 commit，不 amend/rebase，不 push/comment/tag/publish/merge，不 bump 版本；本节是后续 fix3 授权记录，不改上文四提交历史。
- Blocker：dsh 双语 README 发布节仍保留 rc.2 合并后打 tag、`latest` 不动的计划，缺少就地发布事实。Nits：docs-changelog 与 pr-e-release 两处 `Status: ready`／未来发版缺后续发布补记。所有旧句逐字保留，只在对应节末追加。
- README／CHANGELOG 归因：用户 2026-10-23 21:07 +08:00 群内要求仓内所有 README 和 CHANGELOG 更新到最新并集成到本 PR，Lord 记录。
- tasks 归因：用户 2026-10-23 21:09 +08:00 群内要求 SBTD tasks 状态更新为最新（应均为 done），Lord 记录。
- 未完整调用 grill-with-docs：需求、证据来源、追加位置与验收清楚，无领域歧义。主会话唯一 writer／验证 controller；仅 Markdown 追加，无新生产代码或契约。
- Book Gate Plan：DDD、DDIA、legacy、refactoring 均 not-required（无完整 grill、领域／数据设计、行为修改或生产代码编辑）；release-readiness 按 Skill 的 docs-only 排除规则 not-required（仅记录已发生的发布，不改变 rollout/runtime，不把旧 ready 当作本轮门禁）。Code Readability、TDD、BDD/Web/Mobile 新场景 not-required；既有 dsh suite 与 pack 按此次要求执行。
- 三份 task frontmatter／原状态事件均不变；本 task 保持 `checking` / `completed_at: null`，不新增 done 事件，原 21:15 确认原样保留。沿用已记录的 TaskStore 历史 schema blocker，不重跑已知失败；本轮仅追加共享 Markdown，不声称 helper lifecycle 或自动恢复通过。

### 实时证据（查询于 2026-10-23 22:10 +08:00）

- `git for-each-ref`：rc.2 annotated tag `dsh-sbtd-v0.2.0-rc.2` 对象 `43798d6518d6c7fd2a8bfdbe8b7e1a3839ae983e` → `548a0bf125e3b3fe1407de11094409e55c2e779e`，tagger 为 2026-10-23 17:55:10 +08:00。`gh release view ... --json createdAt,publishedAt,isPrerelease`：createdAt 17:55:10、publishedAt 17:55:13（同日 +08:00），isPrerelease=true。
- `npm view @kunolu/dsh-sbtd time --json`：rc.2 为 2026-10-23 17:08:50.745 +08:00，rc.1 为 2026-10-19 04:43:02.349 +08:00。`npm view @kunolu/dsh-sbtd dist-tags --json`：本次查询时 `next = latest = 0.2.0-rc.2`；不是永久不变的 tag 保证。另以 `npm view @kunolu/{dsh,omp}-sbtd time dist-tags --json` 归档复核，两包均为 rc.2。
- `gh pr view 98 --repo KunoLu/sbtd-plugins --json mergedAt,mergeCommit`：`73f0ca525bf73577560b6ce86d9e7a43ccb94517`，mergedAt 2026-10-19 04:11:26 +08:00；#99：`1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831`，mergedAt 2026-10-19 04:39:45 +08:00。
- rc.1 annotated tag `dsh-sbtd-v0.2.0-rc.1` 对象 `73d4c0a4cc37fb6b445809aa164a382a20b681b8` → #99 merge SHA，tagger 2026-10-19 04:43:55 +08:00；GitHub prerelease createdAt 04:43:55、publishedAt 04:43:59（同日 +08:00），isPrerelease=true。
- `npm view @kunolu/dsh-sbtd@0.2.0-rc.1 dist.fileCount` 为 102；`npm pack @kunolu/dsh-sbtd@0.2.0-rc.1 --dry-run --json` 核验该已发布 tarball 含 `CHANGELOG.md` 5508 bytes、`CHANGELOG.zh.md` 5087 bytes，entryCount=102。不是拿当前工作树 pack 冒充历史发布物。

### fixed：逐文件旧 → 追加新

行号为此次结果；旧句未替换，箭头仅表示追加事实对旧当前态描述的澄清。

| 文件:旧行 → 新行 | 原文／旧状态 → 追加事实 |
|---|---|
| `packages/dsh-sbtd/README.md:107,109 → 111` | “Publication is separate … After review and merge …”／“leave `latest` untouched” → rc.2 已发布，完整 tag 对象／target／tagger、GitHub created/published、npm time 与有查询时点的 next/latest；旧段明确为发布前计划 |
| `packages/dsh-sbtd/README.zh.md:107,109 → 111` | “发布与本次 README/version bump 分开。评审与合并后……”／“`latest` 保持不动” → 与英文相同事实、时间和证据命令的中文镜像 |
| `ai/tasks/dsh-sbtd-0-2-0-rc-1-docs-changelog/task.md:53–60 → 62` | `Status: ready`／未来发版 → 状态补记：PRD D / #98 merge SHA、mergedAt、rc.1 npm time、已发布 tarball 双语 CHANGELOG 验证；不改旧验证与 frontmatter |
| `ai/tasks/dsh-sbtd-0-2-0-rc-1-pr-e-release/task.md:49–56 → 58` | `Status: ready`／未来 tarball → 状态补记：#99 merge SHA、mergedAt、rc.1 npm time、annotated tag 与 prerelease；区分 Git commit 时间，不改旧验证与 frontmatter |
| `ai/tasks/sbtd-rc2-closeout/task.md:199 → 201 起` | 原收尾记录缺 fix3 → 追加本节问题、归因、实时证据、全部变更／扫描分类与验证；旧文及 checking/null 保留 |

### checked-not-stale：全仓 README／CHANGELOG 复扫

名称盘点共 31 文件：12 自有、19 上游／模板／生成镜像。对全部文件执行大小写不敏感关键词检索（will tag / will be tagged / after … merge / latest … stay 或 untouched / leave … latest / not yet published / publication is separate / publication remains blocked / next RC candidate，以及合并后、发布后、保持不动、尚未发布、未发布、待发布、发布仍被阻止、未来发布）；另对 12 自有文件扩大到 publish/release/tag/合并/发布/latest/next。追加后再次扫描：dsh 旧命中因 append-only 留存，已由紧随的补记澄清，不误报为零命中。

| 文件:行 | checked, not stale／保留理由 |
|---|---|
| `README.md:23–42,67–69`；`README_zh.md:23–42,67–69` | 两包 rc.2 已发布／next+latest 与本轮 registry 一致；精确版本或 @next 为安装策略，不断言 latest 仍为旧版本；D11 日期引用为明确历史快照 |
| `packages/dsh-sbtd/README.md:21–28,109,111`；`packages/dsh-sbtd/README.zh.md:21–28,109,111` | 安装节当前发布事实仍真；:109 测试、打包、链接核验与“不把日期当发布证据”为通用程序；仅 rc.2 将来态和 latest 计划由 :111 澄清，其他句不改；:111 引用旧措辞用于否定其当前态含义 |
| `packages/dsh-sbtd/CHANGELOG.md:19`；`packages/dsh-sbtd/CHANGELOG.zh.md:18` | rc.2 发布补记与 npm/GitHub 相符；其余 dated 版本条目是历史，不重写 |
| `packages/omp-sbtd/README.md:17–22,32–37,99–119`；`packages/omp-sbtd/README.zh.md:19–21,31–36,95–113` | 当前 rc.2 事实仍真；兼容认证与发布解耦；发布 helper 只接受 next 是通用操作约束，不声称 registry latest 没有 rc.2，不改通用流程 |
| `packages/omp-sbtd/CHANGELOG.md:28,32`；`packages/omp-sbtd/CHANGELOG.zh.md:26,30` | “日期记录准备工作，不代表发布”限定的是日期证据；后面已有真实发布补记，不是尚未发布声明 |
| `packages/omp-sbtd/CHANGELOG.md:39–42,93–98`；`packages/omp-sbtd/CHANGELOG.zh.md:37–39,85–89` | rc.1 日期条目中的旧 dist-tag 与后续 session_compact 计划是历史；rc.2 条目已记录后续交付，保留旧文 |
| `packages/omp-sbtd/CHANGELOG.md:167–170,215–217`；`packages/omp-sbtd/CHANGELOG.zh.md:153–156,195–196` | rc.11 日期条目中的 candidate／发布阻止门槛为历史，不是 rc.2 当前状态 |
| `docs/assets/dsh/README.md:3–8` | 文档索引与当前 rc.2/next/latest 已对齐；“发新版前”是通用校验链接，不是待发布声明 |
| `packages/omp-sbtd/validation/p0/evidence/README.md:1–30` | 仅证据存储／信任边界，无当前发布状态声明，旧措辞扫描无命中 |

排除但报告命中（均不修改，不以本轮插件发布状态改写上游）：

- `packages/omp-sbtd/upstream/vendor/sbtd-workflow-kit-upstream/README.zh.md:272,509,511`：规则保持不动、维护未发布章节／版本检查程序。
- `packages/omp-sbtd/upstream/vendor/sbtd-workflow-kit-upstream/CHANGELOG.md:355`：`.gitignore` incremental merge，非发布合并。
- `packages/omp-sbtd/upstream/vendor/sbtd-workflow-kit-upstream/CHANGELOG.zh.md:3,7,9,212,226,242,356`：上游未发布章节／上游 dated release 历史／`.gitignore` 合并。
- 其余 16 个排除文件关键词无命中：同 vendor 的 `README.md`、`docs/lessons/archive/README.md`，及七组 `web-ui-autotest-generator/{README.md,README.zh-CN.md}`（vendor 的 `sbtd-workflow-onboard/templates/skills`、`upstream/{omp-overlays,generated,generated-omp}/onboard/runtime/templates/skills`、`upstream/generated-agent-plugin/skills`、`kit/onboard/runtime/templates/skills`、`skills`；各路径均位于 `packages/omp-sbtd` 下）。

### fix3 实际检查与边界

- `COREPACK_HOME=/home/box/.cache/node/corepack TMPDIR=/tmp GIT_CEILING_DIRECTORIES=/tmp node --test test/*.test.mjs`（`packages/dsh-sbtd`）：exit 0；342 passed / 0 failed / 0 skipped，runner 6056.596244 ms。
- `COREPACK_HOME=/home/box/.cache/node/corepack npm pack --dry-run --json`（`packages/dsh-sbtd`）：exit 0，103 files；README.md、README.zh.md、CHANGELOG.md、CHANGELOG.zh.md 均在包内，大小与工作树一致。manifest files 显式列双语 CHANGELOG，npm pack 实测自动包含双语 README。dsh 无 SBOM。
- 未修改任何 omp-sbtd packaged file：因此不触发 omp build/SBOM 重生成、actual pack/check-package --packed、agent-plugin-pack 或 full omp test；不运行这些无变化范围。dsh 既有 lint 失败不重跑确认；无 src/types/config 变化，不运行额外 lint/typecheck/build，不声称其通过。
- 文档 smoke：MarkdownIt CommonMark + table 实际渲染五个修改文件，发布补记在各自发布节内且先于 Support／支持；双语新增代码标识、时间、原命令块一致。三份 task YAML 可解析，frontmatter 字节与旧事件完全不变；旧句零删除。全仓受跟踪范围冲突标记扫描为零。
- 原始实时查询、dsh tests、pack 与同 stem 中文汇总保留 `reports/fix3-publication.{json,md}`、`reports/fix3-dsh-tests.{json,md}`、`reports/fix3-dsh-dry-pack.{json,md}`；静态检查与最终提交绑定保留 `reports/fix3-final-checks.{json,md}`。82 个 dsh/workspace 验证输入 SHA256 保留 `reports/fix3-validation-inputs.json`，提交后与 Git blob 核对，不将本地测试冒充远端 PR CI。
- 提交前／后分别核验 whitespace、追加行归因禁词、禁用英文时间短语、归因时间专用性、YAML、零删除及唯一子提交；确切 commit SHA 和最终检查结果在交付及本地报告记录，不在提交内预填自身 SHA。
- rtk=skipped-for-report（原生命令保存真实输出）；Graft=skipped（文档事实取 Git/GitHub/npm，无需结构图）；BDD=skipped（docs-only，无新行为／场景）；Cross-repo context/API Contract=not-needed；Mock Strategy=none（发布查询／pack／Markdown smoke，无新 mock；既有 suite 内部测试替身不冒充 full-stack）。Evidence Source=developer-local、Source Revision=dirty（执行时）、Evidence Publication=local-only；无新 CI、真实宿主或 Web/Mobile 执行。
- 发布与恢复边界：已发布 npm rc.2 tarball 不可覆盖，本次 README 只随本 PR 进入仓库，不声称 registry 已包含新补记；此次无发布授权、无新版本。任务仍 checking/null，后续合并回填遵守原确认；本轮不新建 lesson/身份/handoff，不修改任何全局配置。
