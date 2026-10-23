---
schema_version: 1
id: sbtd-rc2-closeout
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict 收尾；四个逻辑提交；主会话唯一 writer；仅授权本地提交，不授权远端写入或发布。
status: in-progress
branch: chore/omp-sbtd-rc2-closeout
created_at: '2026-10-23T21:12:56+08:00'
updated_at: '2026-10-23T21:12:56+08:00'
completed_at: null
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
| book-release-readiness | 已发布状态记录与包内容一致性核对；不部署、不更改运行时 | finish | planned（包文档变化后核对发布物边界） |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T21:12:56+08:00 | planned | in-progress | 编排方整理：建立 strict 收尾记录 | 实际分支／基线／路径／ignore 与 npm、GitHub 初次核验通过 |

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
