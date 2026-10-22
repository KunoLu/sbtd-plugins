---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-e-release
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择 strict，按 PRD L59 与行 E；唯一 writer，仅显式路径提交，不 push/PR/tag/release/publish/dist-tag。
status: "checking"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-e-release
created_at: '2026-10-22T19:06:33+08:00'
updated_at: '2026-10-22T19:27:33+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 E：pre-tag release PR

## 目标 / 范围 / 非目标

- 首 commit 回填行 R、#110–#113 历史记录与行 D superseded 注释，PRD 仅改 R/E 两行，新增本 strict 记录与排序索引。
- package.json/plugin.json 升为 0.2.0-rc.1，五个钉版测试断言同步；双语 CHANGELOG 日期为 2026-10-22，四份 README 改为 next/latest 已发布措辞并说明 17.x 须钉旧 0.1.x。
- 文档/版本完成后一次正常 build 重生成 SBOM，实际 pack/check-package、typecheck、包 lint、focused/full tests，提交证据。
- 不改 dsh 内容、历史 fixture/CHANGELOG、D7 链接、D11 原句、lockfile、files/p0 清单或生产逻辑。不 push、开 PR、tag、GitHub release、npm publish/dist-tag，不暂存 .omp-r12b-addendum.txt 或 ai/tasks/codex-verify/。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T19:06:33+08:00 | planned | in-progress | 用户授权 strict 行 E 与前序回填 | 分支匹配、起点 clean；基线 007fb6c506e609050fedd1ed86db8696d8164e03；PRD L59–L62 |
| 2026-10-22T19:27:33+08:00 | in-progress | checking | pre-tag 内容、本地验收及两项独立复核完成；保留唯一已知环境失败，不标 done 或 release-ready | 2634fd1 / 5d5b7e7 / a7721bb / 18e4bee；实际 check-package exit 0；focused 38 passed；full 884 passed / 1 failed / 3 skipped；下方证据 |

## 决策

- 未完整调用 grill-with-docs：用户与 PRD 已明确锁定需求，无新领域歧义。
- #110 frontmatter branch 经 orchestrator 的 gh headRefName 核验正确，保留；#111 为单独 review-fix 分支，不重写历史归属。
- 根及包 README 按 D4/R10 写 expected released state，不当作本轮已发布事实；行 F 按最终 npm view 证据纠偏。
- 沿用指定先例的共享文档 edit/write；已知全库 TaskStore 历史 schema blocker 不重跑，不写 active pointer，不声称 TaskStore lifecycle/自动恢复可靠。新任务与父路径安全，reports 命中 .gitignore:125 /ai/tasks/**/reports。
- 主会话唯一 writer/验证 controller；独立 reviewer 只读，不运行 build/lint/tests/formatters。

## Side PR 合并回填

以下均由 orchestrator 提供；它们不是 PRD 任务行。五个远程分支（含 #109）均已删除；#113 本地分支及 worktree 已正常删除，无 force。

| PR | head branch | merge SHA | merge commit %cI | GitHub mergedAt |
|---|---|---|---|---|
| #110 | docs/omp-sbtd-0.2.0-rc.1-d11-d9-wording | 91efc235f273c7d8370f92210dd723d2ff8154ce | 2026-10-22T17:19:16+08:00 | 2026-10-22T17:19:17+08:00 |
| #111 | docs/omp-sbtd-0.2.0-rc.1-d11-d9-wording-fix | ddcba1322f1f2ef43981870cc2bab96f2887f705 | 2026-10-22T17:32:14+08:00 | 2026-10-22T17:32:15+08:00 |
| #112 | docs/omp-sbtd-0.2.0-rc.1-d11-d9-sync | 194dfa653f5e4f3d1bb34f2721af58c8200dba4f | 2026-10-22T18:08:58+08:00 | 2026-10-22T18:08:58+08:00 |
| #113 | docs/omp-sbtd-0.2.0-rc.1-prd-d4-release-docs | 007fb6c506e609050fedd1ed86db8696d8164e03 | 2026-10-22T18:59:19+08:00 | 2026-10-22T18:59:20+08:00 |

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；发布决策已锁定，无模型歧义 | before-dev | not-required |
| book-ddia-data-design | 无 schema/迁移/缓存/数据所有权设计；SBOM 仅按既有生成器派生 | before-dev | not-required |
| book-legacy-change-safety | 无生产逻辑或既有 bug 修复；实际 tarball 检查保护发布一致性 | before-dev | not-required |
| book-refactoring-pass | 无生产代码修改；仅 manifest 与测试版本常量 | before-dev | not-required |
| book-release-readiness | 发布元数据、安装通道文档与 SBOM | after-validation | blocked（实际发布；已完成 Review，见下方；不阻止用户指定的 pre-tag 本地交付） |

## 验证证据

### 来源与命令

- Evidence Source: **developer-local**；Source Revision: **dirty**（运行时 HEAD `a7721bb09ea2190ac3dfef2e8a0a23a7e59e0369` + 待提交 SBOM）；Evidence Publication: **local-only**，不是 CI/PR-head 认证。运行环境 Linux x64、Node `v22.20.0`、pnpm `11.17.0`、Vitest `4.0.16`，worktree `/workspace/sbtd-plugins-pr-e`。
- 全部 pnpm 使用 `COREPACK_HOME=$HOME/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1`，cwd `packages/omp-sbtd`；未打印环境值或秘密。node_modules 已由 orchestrator 安装，本轮未主动重新 install；build 的 pnpm 前置输出有既有 lockfile policy 检查。
- 原生输出与同 stem 中文汇总在本任务 ignored `reports/row-e-{build,pack,unpack,check-package,typecheck,lint,focused,full-tests}.{txt,md}`；八组均已保存，中文汇总九节顺序/无占位符/原生配对已核对。未提交报告，不冒充公开 PR evidence。

| 命令 | exit | 实测结果 |
|---|---|---|
| `pnpm build` | 0 | 仅执行一次；generated output is current；正常 write-sbom 生成下列 hashes，6.50s |
| `pnpm pack --pack-destination /tmp/omp-sbtd-pr-e-pack-1NavPo` | 0 | 目录由 `mktemp -d /tmp/omp-sbtd-pr-e-pack-XXXXXX` 创建；产物 `kunolu-omp-sbtd-0.2.0-rc.1.tgz`，1.12s |
| `tar -xzf /tmp/omp-sbtd-pr-e-pack-1NavPo/kunolu-omp-sbtd-0.2.0-rc.1.tgz -C /tmp/omp-sbtd-pr-e-pack-1NavPo` | 0 | 实际解包成功，0.04s |
| `pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/omp-sbtd-pr-e-pack-1NavPo/package` | 0 | packedFileCount **471**；无 `SBOM_MISMATCH`，0.93s |
| `pnpm typecheck` | 0 | tsc --noEmit，2.86s |
| `pnpm lint` | 0 | Biome checked **99 files**，No fixes applied，0.66s |
| `pnpm exec vitest run test/agent-plugin-manifest.test.ts test/agent-plugin-pack.test.ts test/p0-dist-hygiene.test.ts test/p0-package-release.test.ts test/publish-package.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000` | 0 | **5 files / 38 passed**；runner 14.73s |
| `pnpm test` | 1 | **46 files：45 passed / 1 failed；888 tests：884 passed / 1 failed / 3 skipped**；19:12:07+08:00 开始，runner 296.74s |

完整 suite 唯一失败：`test/p0-authorized-omp-rpc-harness.test.ts > authorized OMP public-RPC harness > smoke-only: exact local OMP 18.11.1 blocks a dependency-resolved packed host before RPC without a provider`；Bun `--offline` 缺 `zod` / `@oh-my-pi/pi-coding-agent` cached manifest，`zod@4.1.12 failed to resolve`，未到 RPC。与用户允许保留的既有环境失败一致；未修全局缓存、未改测试、未重跑确认，不标 full PASS。3 skipped 为 upstream transform 两项与 env-gated host-event live cell 一项。

### SBOM 与实际包

| 字段 | 实测值 |
|---|---|
| packedFileCount | 471 |
| sourceTreeSha256 | `06b01ba05f97e91ff979f11ae76664ab5375e80f84bfa33ab92d4c40f1014a06` |
| sbomSha256 | `b654e0be249c9200d94a6d0d9497d90a5dc4520fdc8de8740a38ae5f154f7b14` |

build / check-package 的两 hashes 相同；SBOM 文件实际 SHA-256 等于 sbomSha256；focused 与 full tests 后 SBOM 均未改变。SBOM 已提交为 `18e4beee8c2a676fb5a0447247cf25ace80b246d`，提交后未重建。解包 SBOM、当前文件与提交 blob 字节一致。

对 origin/main SBOM 递归 JSON 比较恰六个值变化（无 key/list 长度变化），原生 `reports/row-e-sbom-diff.json`：

| JSON path | 含义 / 新值 |
|---|---|
| `/documentNamespace` | `https://kpi.local/spdx/` + 上列 sourceTreeSha256 |
| `/files/0/checksums/0/checksumValue` | `./CHANGELOG.md` → `434c31b1af9d045ab2f7d2196f3ca1f3387a0dfc04401b3a3e7f4a48251e52f3` |
| `/files/370/checksums/0/checksumValue` | `./plugin.json` → `3c3839c2fccf0c1ad63f86ac388cf7ed6e3c6ef73cb75d81187137b5e65c5ef6` |
| `/files/371/checksums/0/checksumValue` | `./README.md` → `761f261c62efcf588496b5b86c6020e91389f3e73e0ca314f450440c444dfd01` |
| `/name` | `@kunolu/omp-sbtd-0.2.0-rc.1` |
| `/packages/0/versionInfo` | `0.2.0-rc.1` |

三个文件 checksum 均与磁盘实际 SHA-256 相等；package.json 版本参与既有 source digest / package identity，不额外新增 SBOM file 条目。实际 471 文件含 README.md、不含 README_zh.md，files/p0 清单不变。提交后内存字节核验：470 项与当前树完全相同；package.json 为 pnpm 去除末尾 LF（1957 vs 1958 bytes），JSON 全值相同。初次辅助断言错误地要求此文件也逐字节相同而失败；读取真实 packed manifest 后精确确认仅末尾 LF 差异，修正检查判据，未改产品或重建/重跑 suite。

### 检索、保留边界与独立复核

- 四份 README 专用 grep 等价执行 `grep -nE '行 E|row E|Row E|target release|Target release|0\.1\.0-rc\.14|rc\.14|目标版本'`：**No matches found**，无例外；独立 reviewer 额外搜索 `target` 也为 0。
- `packages/omp-sbtd` 版本 grep `0\.1\.0-rc\.14`：最终仅 `CHANGELOG.md:74: ## [0.1.0-rc.14] - 2026-09-01`，历史条目按要求保留。初次 grep 另有 manifest/test pins、README 快照与生成 SBOM，均随本次更新消除；无其他必须匹配的引用。
- `ReleaseDocsReview`：**CLEAN**；四 README/两 CHANGELOG 双语一一对应，D4 next+latest/17.x 影响齐全，D11 verbatim、D7 tag 链接、dsh 根内容及历史 CHANGELOG 不变；helper 只 publish next 与后续单独 dist-tag latest promotion 不冲突。未执行 build/lint/tests。
- `ReleaseRecordReview`：**CLEAN**；核对 `2634fd1` 全部回填与 `5d5b7e7` 版本-only slice。PRD 仅 R/E 元数据、行 D 仅 superseded 注释、历史正文保留、#110 branch 正确、#111 分支归属/五个 merge %cI/模型计数及索引排序符合指令。mergedAt 与历史 session finals 来源为 orchestrator，不冒充重新查 GitHub。未执行 build/lint/tests。
- Code Readability Review：两个测试仅五个版本常量替换，不改结构、控制流或已有 type assertion；无新 abstraction/依赖/永久测试。book-refactoring-pass 与 ponytail-review 的生产代码触发不成立，无无关重构。
- D11 前置：已合并行 C 记录 `task.md` 验证证据 36/39 明确真实 **18.11.1 install-path smoke PASS**（plugin install/discovery、sbtd、sbtd_workflow、13 hooks、两项目 onboard targets）。本轮读取继承，不声称对新 tarball 重跑该宿主 smoke；本轮实际 smoke 为 check-package CLI。

### 跳过与恢复边界

- rtk: **skipped-for-report**（native 完整输出）；BDD: **skipped**（无新运行行为或 .feature 修改；既有中文场景测试随 suite 执行）；Cross-repo context / API Contract: **not-needed**；Mock Strategy: **none**（本轮未新增 mock，沿用原 suite fixtures）。Graft / Web / Mobile: **skipped**（无结构/UI 改动，D7 在线点击待 tag）；未重复根 lint 的已知越界失败，按用户只跑包 lint。
- Final Test Report / Run Summary MD: **generated**；Targeted Rerun: **not-needed**；Final Full Rerun: **failed**（唯一已知环境失败）；Environment Alignment: **not-needed**（本地包验证，不声称部署对齐）。
- 未 push/PR/tag/release/npm publish/dist-tag；未修改全局配置或其他 checkout。测试无新失败、无生产逻辑变更，不产生新长期 lesson；无 throwaway 脚本留在仓库。临时 tarball 与 ignored 原生报告保留供核验，不提交；不把记录保存称为全库 TaskStore 恢复通过。
- 已提交：`2634fd1` 回填 8 文件；`5d5b7e7` 版本/测试 4 文件；`a7721bb` 双语发布文档 6 文件；`18e4bee` SBOM。末次提交仅本任务证据，不改变已验证发布字节。提交前均运行 `git diff --check` 成功并显式 git add 路径。最终 status/log/stat/range whitespace 检查结果在交付回复报告，不预填尚未执行结果。

## Release Readiness Review

- **Status: blocked（实际发布）**；用户指定 pre-tag 本地交付已完成，行 E 保持 checking、completed_at null，合并与 publish 后由行 F 回填 done。不把允许保留的环境失败改称 required-check PASS。
- Production path / affected users: npm `@kunolu/omp-sbtd@0.2.0-rc.1`；D4 promotion 后无版本安装切到 omp `>=18 <19`，17.x 需显式钉旧 0.1.x。六份双语文档已说明。
- Failure modes / safeguards: 版本/包漂移由 manifest/pack focused tests 与真实 check-package 防护；SBOM hashes 与文件 checksum 已核对；D11 原句、D7 链接和发布顺序保留。不得因本地包检查通过绕过 CI、链接或 OTP。
- Capacity / backpressure / limits: not-applicable，无 runtime 逻辑变更。
- Observability / alerts / runbook: 不新增运行监控；本记录保存命令退出码、hashes、失败、后续发布核验步骤。
- Rollout / migration / rollback / cleanup: 按下方六步，tag 只在 main merge commit；发布前可按 scoped commits revert，未执行回滚；发布后 npm tarball 不可变，不能覆盖重发。无数据/全局配置迁移，无清理授权扩张。
- Required validation / result: build、实际 pack/check-package、typecheck、包 lint、focused 全通过；full suite 已执行但保留唯一 Bun offline 环境失败；D11 已合并前置 PASS。实际发布仍缺本 PR CI green、最终 Reviewy PR-tip CLEAN、tag 后 D7 在线点击，必须由后续责任方闭环。
- Owner acceptance / residual risk: 用户明确允许本轮保留上述既有环境失败，仅用于 pre-tag 范围验收；未豁免真实发布门禁。Lord 负责合并/tag/publish，Reviewy 负责最终评审与链接验证，行 F 负责 registry/主页/证据回填。

## 使用的模型

> 主会话计数为 **2026-10-22T19:17:55+08:00 快照**（时间来自 `TZ=Asia/Shanghai date -Is`），不是最终数，不含此后编辑、验证、提交和回复；最终数由 orchestrator 报告。两位 reviewer 已结束，记录 FINAL。assistant = `type=message` 且 role assistant；tools = assistant content 的 toolCall，不重复计 eval 内操作；thinking/fallback 分别来自 thinking_level_change/model_change，provider/model 来自 assistant 消息。原生 `reports/row-e-model-usage.json`。

| agent/session | provider/model | thinkingLevel | assistant messages / tool calls | purpose | resolvedModelIsFallback | title-generation count | job-widget entries |
|---|---|---|---|---|---|---|---|
| astra ping `01a16348-31ee-719e-b613-a83d815a66db` | openai-codex / gpt-6-astra | high | FINAL 1 / 0（orchestrator 提供） | ASTRA_OK，connectivity OK → astra:high；`~/.omp/logs/sbtd-pr-e/ping.log` | false | 未提供 | 未提供 |
| 主会话 `01a16349-f750-71d0-9d74-7fa45d5c5736` | openai-codex / gpt-6-astra | high | SNAPSHOT 20 / 51 | 唯一 writer、验证 controller、回填/发布内容/本地 commits | false | 0（快照） | 0（快照） |
| ReleaseDocsReview `01a1634e-6d95-7647-81da-281c5cf73ed1` | kimi-code / k3 | high | FINAL 10 / 16 | 只读双语发布文档复核 CLEAN | false | 0 | 0 |
| ReleaseRecordReview `01a1634e-6e24-765e-a0ea-0e22c5626511` | kimi-code / k3 | high | FINAL 23 / 24 | 只读历史回填与版本 slice 复核 CLEAN | false | 0 | 0 |

主会话工具快照分布：read 26、bash 5、todo 2、eval 7、write 1、edit 3、grep 4、task 1、glob 2 = 51；ReleaseDocsReview：read 5、bash 6、grep 5 = 16；ReleaseRecordReview：read 4、bash 19、grep 1 = 24。未 override 子代理模型。主 jsonl：`~/.omp/agent/sessions/--workspace-sbtd-plugins-pr-e--/2026-10-22T11-05-54-256Z_01a16349-f750-71d0-9d74-7fa45d5c5736.jsonl`，两个 reviewer 在同 stem 目录内。仅抽取计数/模型元数据，不打印完整会话或秘密。

## 合并后步骤（尚未执行）/ post-merge steps (not yet done)

1. Reviewy CLEAN + CI green → Lord squash-merges。
2. 在 main merge commit（不在分支）创建 annotated tag `omp-sbtd-v0.2.0-rc.1`。
3. 打 tag 后 Reviewy 点击核验两个 D7 语言切换链接：`blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README.md` 与 `README_zh.md`；两者均通过后才创建双语 EN/ZH GitHub prerelease。
4. 从 tagged tree 执行 `npm publish --tag next`，npm OTP 届时由用户提供。
5. `npm dist-tag add @kunolu/omp-sbtd@0.2.0-rc.1 latest`，OTP 由用户提供。
6. 行 F：`npm view @kunolu/omp-sbtd dist-tags` 核验 latest = next = 0.2.0-rc.1，npmjs.com 包页显示新 README、链接有效；回填行 E。任一步失败即停止并报告，不强行发布。

发布前只读 registry 快照（orchestrator，2026-10-22T19:04+08:00）：`npm whoami` 成功，已登录（不记录用户名）；`npm view @kunolu/omp-sbtd dist-tags` 为 `{"latest":"0.1.0-rc.2","next":"0.1.0-rc.14"}`。本轮未执行登录或 registry 写入；快照仅在任务记录，不进入 README。
