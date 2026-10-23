---
schema_version: 1
id: omp-sbtd-0-2-0-rc-2-prep
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict release PREP；唯一 writer；两个逻辑提交；不执行远端写入或发布。
status: done
branch: chore/omp-sbtd-0.2.0-rc.2-prep
created_at: '2026-10-23T20:04:08+08:00'
updated_at: '2026-10-23T20:39:30+08:00'
completed_at: '2026-10-23T20:39:30+08:00'
---
# omp-sbtd 0.2.0-rc.2 release PREP

## 范围与决定

- 编排方整理：先回填 #123 合并与 FINAL 模型记录、修正 Reviewy P3 注释，再准备 rc.2 版本、双语 README/CHANGELOG、发布物清单和 SBOM。由 `chore/omp-sbtd-0.2.0-rc.2-prep` 分支的 PR 交付。
- 基线 `008cea74dfbab5ce2c688c2c42e4bd8cfeddfe5f`，入口工作树干净，分支与授权根匹配。旧任务仅获历史回填授权，保留其历史 branch，不重绑定。
- 编排方整理：最终保持 checking / completed_at null；no tag / no publish / no GitHub release；Lord 在合并后处理。顶部语言链接钉未来 `omp-sbtd-v0.2.0-rc.2`，不声称 tag 已存在；打 tag 后、publish 前须核验链接。
- 编排方整理：包内中文文档改名并随包发布；根中文 README 文件名不变。沿用已记录 R11/R12，不新增 PRD 裁决，不修改 docs/prd、packages/dsh-sbtd、peer、18.11.1 钉或 lockfile。
- 未完整调用 grill-with-docs：范围、归因、历史保留和验收明确，无新领域歧义。
- 路径与 ignore 已核对：ai/tasks 可跟踪、reports 与 .sbtd 受保护，现有父路径为正常目录。沿用既有 TaskStore 全库历史 schema blocker，不重跑；本记录是明确要求的共享 Markdown 交付，不声称 helper lifecycle 或自动恢复通过，不写 active/developer/handoff/ignore。
- 原生报告使用 native 命令，rtk=skipped-for-report。Graft=skipped，无已验证受管连接；不改全局接线或 ~/.bun。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、新业务规则或领域歧义 | before-dev | not-required |
| book-ddia-data-design | 仅已有发布清单新增文档；无 schema、数据所有权或跨服务流变化 | before-dev | not-required |
| book-legacy-change-safety | 首轮完整测试暴露 promotion staging 缺失新文档输入 | check 修复前 | passed（characterized / normal：既有 10 个真实 staging 用例 red；保留 plan/apply、回滚与脏路径拒绝；无新 seam） |
| book-refactoring-pass | runtime 注释与既有发布物清单 | before-dev | passed（proceed / normal：无前置重构；复用清单、build 和 pack 校验） |
| book-release-readiness | 新版本发布物与 SBOM 一致性 | finish | passed（ready，仅 PREP：最终完整测试、真实 tarball 校验、独立审查闭环；不代表 tag/publish/release） |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T20:04:08+08:00 | planned | in-progress | 编排方整理：建立 strict release PREP 记录 | 根、分支、基线、路径和 ignore 核对；现有发布先例与清单已读 |
| 2026-10-23T20:10:16+08:00 | in-progress | checking | 编排方整理：版本、文档与发布物清单准备完成，进入完整验证及独立复核 | build 已生成 rc.2 SBOM 且包含中文文档；原生命令序列运行中；PackageReview / DocsReview 只读复核 |
| 2026-10-23T20:23:06+08:00 | checking | checking | 编排方整理：验证及独立审查闭环，按范围保持 checking | 46 files / 917 passed / 3 env-gated skipped；真实 npm tarball 与 P0 check-package 通过；PackageReview / DocsReview correct；发布由 Lord 合并后处理 |
| 2026-10-23T20:39:30+08:00 | checking | done | 编排方整理：#124 已合并且 rc.2 发布完成；按本仓约定以 GitHub mergedAt 记完成时间 | #124 squash 2393d10c3fb1a1f3cb756a351297a430fd2afc81；本文追加发布记录：tag omp-sbtd-v0.2.0-rc.2，GitHub prerelease 20:41:17、npm 20:44:10（2026-10-23 +08:00），latest=next=0.2.0-rc.2 |

## 验证计划

执行 frozen install、typecheck、lint、build、完整 test、npm pack dry-run JSON 与实际 tarball smoke；检查新增行归因、冲突标记、YAML、历史逐字保留、剩余旧 README 引用与 HEAD 无 tag。build 先于完整 test，避免已知 SBOM/source 不一致。仅修 blockers，nits 记录不扩围。

## 实现与文档 smoke（2026-10-23T20:10:16+08:00）

- 首提交 `6687564`：#123 当前完成字段、追加 done 事件及 FINAL 记录；保留旧正文与所有日期事件顺序。Python/PyYAML smoke 验证通过，新增行归因禁词零命中；runtime 改动仅两行注释。
- 包版本、plugin manifest、当前 manifest/pack 版本断言及四份 README 的 omp 安装钉统一 rc.2。根双语 dsh 行未动。README 用发布后可用的条件式安装措辞，不推断 registry 或 dist-tag。
- 包中文文档用 Git rename 改名；npm 原生自动收录该命名，无需修改 package.json files。P0 `inventoryDeclaredPackageContent` 增加中文文档，两个真实 staging fixture 同步输入；沿用既有清单/SBOM 校验，不加 shim 或第二套打包逻辑。
- 双语 CHANGELOG 在 rc.1 上方新增 rc.2，日期沿用 dsh rc.2 的 2026-10-23 准备日先例，明确日期不等于发布；rc.1 及更早内容逐字保持。#123/#122 使用实际 PR 链接。
- MarkdownIt 实际渲染四份 README；双语 fenced commands 一致、相对链接目标存在。旧版 CHANGELOG 内容字节比较通过。原始证据和中文汇总：`reports/docs-smoke.json/.md`。
- 全仓旧中文文件名引用使用专用 grep 工具（等价 `rg -n`，遵守工具策略）盘点：19 文件、60 命中；逐路径/行号/理由保存在 `reports/readme-reference-audit.json/.md`。分类为根中文文件语言切换 2、dsh 目标项目根文档检查 1、历史 task/归档/PRD 55、本次有日期的双语改名日志 2。没有现行包文档旧路径；不重写历史 PRD。
- `git diff --exit-code origin/main -- pnpm-lock.yaml packages/dsh-sbtd docs/prd` exit 0；`git diff --check` exit 0；`git tag --points-at HEAD` 为空。Node v22.20.0，npm 10.9.3。最终提交后的检查另记录，不将此时点证据冒充最终 HEAD。
- 独立复核分工：PackageReview 负责身份、清单、SBOM、fixture 与注释；DocsReview 负责镜像、发布措辞、历史保留和归因。主会话唯一 writer/验证 controller，reviewer 不运行测试或修改文件。

## 首轮失败与审查修正（2026-10-23T20:15:15+08:00）

- 首轮 `COREPACK_HOME=/home/box/.cache/node/corepack pnpm install --frozen-lockfile` exit 0（2.33s）；typecheck exit 0（3.20s）；lint exit 0（0.62s）；build exit 0（5.10s）。正常 build 生成 rc.2 SBOM，不手工改生成文件。
- 首轮完整 `pnpm --filter @kunolu/omp-sbtd test`：**45 files passed / 1 failed；907 passed / 10 failed / 3 skipped，299.48s，exit 1**。失败全部位于 `upstream/test/transform.test.ts`，原因 `STAGED_PLUGIN_INVALID: staged Plugin SBOM is invalid`。原生失败保留 `reports/test.json/.md`，不覆盖、不重写。
- 根因：发布物清单已要求中文 README，但 `upstream/src/sync-upstream.ts` 的 `stageCandidate` 只复制英文 README；其 fixture 同样只有英文输入。这是本次清单扩展漏同步调用面，不是可豁免环境失败。最小修复为 staging 同步复制中文文档及 fixture 增加相应文件/清单项；不改 transaction/rollback/schema/上游 vendor，不放宽必需文件校验。
- Legacy Change Safety Review：characterized / normal；本轮真实 red 已提供安全网，无需重复造相同失败或增加 mock。Refactoring Review：proceed / normal；只补现有复制清单，无结构重构。先执行失败文件全部场景，再执行 typecheck/lint/build/完整 test/smoke/pack；后续证据独立存于 `reports/final/`。
- DocsReview P2：双语 README 仍携带旧 handoff diagnostic/future-work 描述，与 rc.2 日志冲突。已改为 v2 必需事件、关联 method=handoff 与硬失败，保留 install-path smoke 不等于模型 E2E/完整认证的 caveat。reviewer 重新读取后关闭，最终 **correct / 无剩余 blockers 或 nits**。
- 修正后文档 smoke：Markdown 渲染、双语命令镜像和当前 handoff 契约断言通过，`reports/docs-smoke-final.json/.md`。未新增措辞型永久测试。

## 最终验证与发布边界（2026-10-23T20:23:06+08:00）

- 定点复跑：`COREPACK_HOME=/home/box/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1 pnpm --filter @kunolu/omp-sbtd exec vitest run upstream/test/transform.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000`，**35 passed / 0 failed / 2 skipped，57.45s，exit 0**；真实 promotion plan/apply、回滚、漂移与脏路径拒绝场景恢复。`reports/final/focused.json/.md`。
- 最终命令均带上述 COREPACK_HOME 与 PYTHONDONTWRITEBYTECODE：`pnpm --filter @kunolu/omp-sbtd typecheck` **exit 0**；`lint` **exit 0**；`build` **exit 0**；`test` **46 files passed，917 passed / 0 failed / 3 skipped（920），331.72s，exit 0**；`smoke` **exit 0**，compiled extension 12 个命令/事件阶段通过。这是 hand-rolled host seam smoke，不冒充真实宿主完整事件认证。原生报告及中文汇总为 `reports/final/{typecheck,lint,build,test,smoke}.json/.md`；首轮失败保留。
- 3 个 skip：两个 upstream promotion 场景缺 `KPI_PROMOTION_SOURCE_ROOT`；一个真实 host-event 场景需 `SPIKE_OMP_BIN` 与 `HOST_EVENT_PLUGIN_TARBALL`。本轮仅准备发布物，不重新声明真实 18.11.1 live/full-model E2E 或全部 18.x 认证；#123 的 CI/live 是历史回填，不冒充本轮执行。
- `npm pack --dry-run --json`（cwd `packages/omp-sbtd`）**exit 0**：`@kunolu/omp-sbtd@0.2.0-rc.2`，`kunolu-omp-sbtd-0.2.0-rc.2.tgz`，**472 files**，size **1575878** bytes，unpackedSize **8466017** bytes；包含 `README.md` 和 `README.zh.md`，不含旧中文包文件。sha1 `543fa7c3decdb0f6ca8faef98e90bd6eff3ad362`。`reports/final/pack-dry.json/.md`。
- 实际 smoke：`npm pack --json --pack-destination <tmp>` → 安全解包 → `pnpm --filter @kunolu/omp-sbtd exec tsx scripts/p0/cli.ts check-package --packed <tmp>/package`，两命令 **exit 0**，中文 README 与源码逐字节一致，packedFileCount **472**。tarball SHA256 `3b6c696e15798146251712498672f92bc01a089d3e536273d00ec3d23f49604b`；sourceTreeSha256 `d45faca21edbe2f5d580942a6739499c343a5811697cdb889d7c8788a5634870`；SBOM SHA256 `06eac22d3d5a7170e2b21002cf5d954692aefaa3d9e89fb51b93e4b1d71f14e1`。`reports/actual-tarball-smoke.json/.md`。
- PackageReview 最终 **correct / 无 blockers**，P1 staging 缺输入已关闭；DocsReview 最终 **correct / 无 blockers 或 nits**，P2 旧诊断文案已关闭。独立只读原始记录与中文汇总保留于 `reports/PackageReview*`、`reports/DocsReview*`。
- Nit（P3，记录不实施）：可在 agent-plugin-pack 增加中文文档显式包含断言；现有 exact inventory↔tarball gate 与本轮真实 tarball smoke 已覆盖。按编排方整理的仅修 blockers 范围，不重复增加清单型测试。
- ponytail-review：Lean already；既有清单/复制/fixture 最小增量，无新依赖、抽象或 shim。Code Readability Review：沿用原 Promise.all 与逐项路径格式，manifest 版本比较用 toMatchObject，不新增 inline shape cast。无独立新长期规范需要固化，不新增身份或 lesson。
- BDD=traceable：沿用既有中文场景+英文 keywords 与 `features/sbtd-control-bootstrap.feature`、upstream transform 场景；无新运行时行为或 .feature 修改。实际命令为完整包 test 与定点 upstream 测试。Cross-repo context/API Contract=not-needed（不改变宿主 API）；Mock Strategy=contract-backed（既有测试）；Web/Mobile=not-needed。rtk=skipped-for-report，Graft=skipped。
- Release Readiness Review：**ready（仅 PREP）**。风险为包身份、文件清单、SBOM/staging 一致性，已通过校验；容量/背压/新遥测不适用，无服务、迁移、全局配置或运行时逻辑变化。回滚为本次范围内提交，无用户数据回滚。no tag / no publish / no GitHub release；Lord 在合并后处理发布及语言链接核验，本记录不声称在线链接通过。
- 最终运行输入共 **1975** 个 package/workspace 文件取 SHA256；提交后与 Git blob 逐项绑定。证据为 developer-local / dirty / local-only，不冒充 CI；提交后核对结果单独保留 `reports/final-repository-checks.json/.md`，交付对话列明最终 SHA 与检查结果。
- 偏差仅为必要 blockers 修复：补齐 promotion 源路径与 fixture、替换陈旧 handoff 文案；build 先于 test 以避免已知 SBOM 漂移。package.json files 无需改，lockfile 无需改；docs/prd 与 dsh-sbtd 保持不变。专用 grep 替代 shell rg，不降低扫描范围。TaskStore 历史 schema blocker 保留，不能承诺自动恢复或跨机 ignored reports 可用。

## 合并与 FINAL 执行记录补记（2026-10-23，编排方整理）

- 由 #124 交付；squash merge `2393d10c3fb1a1f3cb756a351297a430fd2afc81`。Git `%cI` 为 `2026-10-23T20:39:29+08:00`；GitHub mergedAt 为 `2026-10-23T20:39:30+08:00`，分别核验，不混用。
- 编排方整理：Reviewy CLEAN @ `7432be486b42c3b7326ed1b0574d0bab38b30739`。GitHub CI `omp-runtime-linux-probe` run `39954216679` 在同一 head 上 1/1 success，收尾会话已通过 `gh run view` 重核。
- 编排方整理：下表为 #124 FINAL 模型记录，不是收尾会话的模型统计。执行窗口 20:03:22 → 20:27:12（2026-10-23 +08:00），exit 0；无 advisor、无执行模型 fallback，watchdog 未触发。

| 角色 | 实际模型／effort | assistant msgs | tool calls |
|---|---|---|---|
| ping | openai-codex/gpt-6-astra:high | 1 | 0 |
| main | openai-codex/gpt-6-astra:high | 50 | 101 |
| PackageReview | reviewer subagent kimi-code/k3；agent default @slow=k3:max；spawned effort=hi，实际 max | 67 | 74 |
| DocsReview | reviewer subagent kimi-code/k3；spawned effort=hi，实际 max | 13 | 20 |

- 编排方整理：title-gen ping pid 428237 为 0；main pid 428413：main 7 次、无 title，依序 composer-2.5 → k3-256k → deepseek-flash response error → gpt-6-astra → grok-4.7 → grok-4.6 → gpt-6.1-sol，均无 title；grok-4.7/4.6 计入 title-gen fallback。PackageReview 1 次（composer-2.5 success）；DocsReview 2 次（composer-2.5 none、k3-256k success）。title-gen fallback 与执行模型无 fallback 是不同统计口径。

## rc.2 发布补记（2026-10-23，编排方整理）

- 编排方整理：发布由 Lord 执行。annotated tag `omp-sbtd-v0.2.0-rc.2`，tag object `d22a877b449cfde587f2f0041ab27256176df765` → `2393d10c3fb1a1f3cb756a351297a430fd2afc81`，tagger `2026-10-23T20:40:57+08:00`；收尾会话已通过 Git 重核。
- [GitHub prerelease](https://github.com/KunoLu/sbtd-plugins/releases/tag/omp-sbtd-v0.2.0-rc.2) createdAt `2026-10-23T20:40:57+08:00`，publishedAt `2026-10-23T20:41:17+08:00`，prerelease=true；releases/latest HTTP 404。收尾会话已通过 GitHub API 重核。
- 编排方整理：publish 前两个 tag-bound README 链接均 HTTP 200；收尾会话再次请求 `blob/omp-sbtd-v0.2.0-rc.2/packages/omp-sbtd/README.md` 和 `README.zh.md`，均 HTTP 200。
- 编排方整理：从 `2393d10` clean worktree 重新 pack，472 files，check-package exit 0，tarball SHA256 `3b6c696e15798146251712498672f92bc01a089d3e536273d00ec3d23f49604b`。npm dist.shasum `543fa7c3decdb0f6ca8faef98e90bd6eff3ad362`、dist.fileCount 472 已通过 `npm view` 重核。
- npm `time['0.2.0-rc.2']` 为 `2026-10-23T12:44:10.098Z`，即 `2026-10-23T20:44:10+08:00`（保留原始毫秒值作为证据）。编排方整理：先发布到 next，再将 latest 指向 rc.2；收尾会话查询结果 latest=next=`0.2.0-rc.2`。
- 编排方整理：OMP 自提 nit，由 chore/omp-sbtd-rc2-closeout 分支的 PR 交付：在既有真实 pack 场景显式断言包含 `README.zh.md` 且不含 `README_zh.md`，不再增加第二次 pack。
- 以上发布事实解除历史 PREP-only 发布边界；历史验证与限制原文保留。checking → done 事件在收尾提交 2 追加，completed_at 采用 #124 GitHub mergedAt（20:39:30），事件证据同时引用本节稍后完成的发布记录，不将 npm 发布时间当作合并时间。
