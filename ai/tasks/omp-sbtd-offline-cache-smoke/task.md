---
schema_version: 1
id: omp-sbtd-offline-cache-smoke
workflow_mode: strict
mode_source: user
mode_note: 用户 2026-10-23 10:32 +08:00 明确启动 item 1 offline-cache chore；唯一 writer，仅本地显式路径提交，不 push/PR/comment/tag/publish/merge。
status: done
branch: chore/offline-cache-smoke
created_at: '2026-10-23T10:34:09+08:00'
updated_at: '2026-10-23T12:40:50+08:00'
completed_at: '2026-10-23T12:15:38+08:00'
---
# OMP offline-cache smoke chore

## 目标 / 范围 / 非目标

- 首提交仅回填 PRD 行 F 四个允许单元格、行 F task FINAL 计数和 fix batch 1 行 E 时间事实、三个 dsh task 完成状态；全部旧正文与事件保留，只追加说明/事件及更新当前 frontmatter。
- 修复 `test/p0-authorized-omp-rpc-harness.test.ts` 的 exact local OMP 18.11.1 smoke：准备测试拥有的 Bun cache，真实离线安装成功后保持无 provider 的 pre-RPC 拦截与文件不变断言；仅实际缺失 cache 且无法准备时使用 Vitest skip，清楚报告原因，不把 skip 写成 PASS。
- 修正 `docs/assets/omp/omp-plugin-host-acceptance.md` 的仓库名称/路径并补 pnpm workspace 指引；运行包 build/typecheck/lint/full tests 和单独 smoke。
- 不改 schema、CHANGELOG、无关源码/测试、全局 Bun/pnpm/OMP 配置，不读取 `.env` 或 secrets，不发布、不清理历史数据。诊断根 `plugins/` 不是仓库目录，保留；`KPI_OMP_RUNTIME_*` 等运行时变量名保留。
- 当前 checkout 与任务 branch 匹配，初始工作区 clean，基线 `aa885d7b7f621e136ef5ba02c2735ba00ab65a2d`。用户显式授权旧任务记录回填，不重绑定其历史 branch。
- 未完整调用 grill-with-docs：目标/验收已锁定，无领域歧义。沿用行 F 已记录的 TaskStore 全库历史 schema blocker，不重跑确认；本任务为显式授权共享文档记录，不写 active pointer，不声称 TaskStore lifecycle 或自动恢复已通过。相关父路径无 symlink，报告目录已 ignore 且未 tracked。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T10:34:09+08:00 | planned | in-progress | 用户指定 strict 开工；核实当前 worktree/branch/授权 | 入口 pwd、git status --short（空）、git branch --show-current、date --iso-8601=seconds |
| 2026-10-23T10:41:37+08:00 | in-progress | in-progress | 缓存修复首次真实 smoke 到达宿主，但既有报错文案断言失败；不转为 cache skip | smoke-focused raw：offline install completed，exit 1，1 failed / 55 name-filter skipped；宿主实际 No default model selected，原断言 No models available |
| 2026-10-23T10:52:34+08:00 | in-progress | in-progress | 保留无 Provider 时 RPC 前阻断及全部文件系统断言，将不稳定文案匹配改为真实退出生命周期断言，定点 smoke 通过 | exact OMP 18.11.1 源码 main.ts 的无模型出口位于 runRpcMode 前；Error.cause 断言 exitCode=1、signal=null、stdoutBytes=0；smoke-focused-behavior exit 0，1 passed / 55 name-filter skipped |
| 2026-10-23T11:02:17+08:00 | in-progress | checking | 实现、真实 smoke、全套验证与两项独立只读复核完成；保留历史失败，等待编排方 Reviewy PR-tip CLEAN + merge | build/typecheck/lint exit 0；harness 56 passed；full suite 890 passed / 3 skipped；smoke 1 passed；真实 cache-unavailable 1 runtime skip（不计 PASS）；本地报告见下方最终证据表；completed_at 保持 null |
| 2026-10-23T11:51:56+08:00 | checking | checking | Reviewy B1 @950df81：补充锚定 RPC 退出前缀及 OMP 18.11.1 两种无模型文案的消息正则，保留 cause，拒绝扩展加载失败 | build/typecheck/lint exit 0；healthy smoke 1 passed；注入 broken plugin 后 1 failed，received message 以 Failed to load extension 开始；重建后注入计数 0、smoke 1 passed；harness 56 passed；full suite 890 passed / 3 skipped、46 files passed；报告见 Reviewy B1 fix 节 |
| 2026-10-23T12:15:38+08:00 | checking | done | #116 squash-merged after Reviewy CLEAN @12fd0142f3c9dbf3efb4a6a04294646265675cce | merge SHA 25d7e83bbc25b6f7d2c5018d7f945376670a2d9a；git %cI 2026-10-23T12:15:38+08:00；gh mergedAt 2026-10-23T04:15:38Z = 2026-10-23T12:15:38+08:00；git log -1 --format='%H %cI' 25d7e83；gh pr view 116 --json state,mergedAt,mergeCommit,mergedBy,headRefName |

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill、无领域规则/边界变更 | before-dev | not-required |
| book-ddia-data-design | 测试跨进程 Bun cache 的写入/离线读取及失败恢复 | before-dev | running |
| book-legacy-change-safety | 既有 smoke 的缺 cache 失败及 skip 语义 | before-dev | running |
| book-refactoring-pass | 仅测试安装准备，不编辑生产源码 | before-dev | not-required |
| book-release-readiness | 测试安装外部依赖流程改变；不执行发布 | after-validation | planned |

## 验证证据

### 记录回填

- 本地提交 `1b45e46`：`docs(sbtd): backfill row F (#115 / aa885d7) and fix stale dsh task statuses`；5 files，42 insertions / 13 deletions。
- #115 merge `%cI` = `2026-10-22T22:05:47+08:00`；GitHub mergedAt = `2026-10-22T22:05:48+08:00`。fix1 main jsonl 只读计数 FINAL 10 assistant / 29 toolCall。
- #93 `3fafd73f828b0f61c3310e4828cfb63bbced3f9a`：branch `docs/dsh-sbtd-0.2.0-rc.1-prd` 匹配，mergedAt / `%cI` 均为 `2026-10-18T09:11:01+08:00`。
- #96 `609766b1d911f1a4597e5ee7117877d2238a548f`：branch `feat/dsh-sbtd-0.2.0-rc.1-pr-b-backend` 匹配，mergedAt `2026-10-18T20:35:02+08:00`，`%cI` `2026-10-18T20:35:01+08:00`。
- #99 `1fdf9e8701afbb7d199c3f3ca5d10ac4a6a0a831`：branch `feat/dsh-sbtd-0.2.0-rc.1-pr-e-release` 匹配，mergedAt `2026-10-19T04:39:45+08:00`，`%cI` `2026-10-19T04:39:44+08:00`。
- 实际命令：`git log -1 --format='%H %cI' <merge>`，`gh pr view 115 --json mergedAt`，`gh pr view <93|96|99> --json state,mergedAt,mergeCommit,headRefName`。内存字节比较确认 PRD 仅 L73 的 status/PR/SHA/time 四列改变；旧 task 历史字节顺序不变，仅三当前字段替换及追加内容。index 无 status 字段。

### 环境与调查

- Node `v22.20.0`，Bun `1.4.2`。首次 `pnpm --version` exit 1：Corepack 尝试 `/usr/local/share/corepack/v1`，EACCES；未改全局配置。改用 repo-local `COREPACK_HOME=.tmp/corepack` 下载声明的 pnpm `11.17.0`，exit 0。
- LSP references 调用返回 `No language server found for this action`；改用源码确认 `installPackedPlugin` 仅一个 smoke 调用，`runCommand` 仅 pack/tar/install 使用。Graft 未挂载，skipped，源码替代。
- 历史失败采用 #114 / 行 F 的既有事实：`bun install --offline` 缺 zod / pi-coding-agent manifests，未到 RPC；不重复运行原失败确认。现有 child env 仅 PATH，未继承缓存定位变量。

## 使用的模型

| agent/session id | provider/model | purpose | assistant messages / tool calls |
|---|---|---|---|
| main / `01a1669b-a431-75c5-931b-9cb8276290c7` | openai-codex / gpt-6-astra | 唯一 writer、验证 controller | SNAPSHOT 尚未采集；提交前从本 session jsonl 只读计数 |

## 当前值 / 交付边界

- 最终本地交付状态须为 checking，completed_at = null；仅 Reviewy CLEAN + merge 后由编排方标 done。
- 本地验证不等于 CI、受信 §4 gate 或 release-ready；不自动恢复或执行远端操作。

## 设计与安全网复审（已执行）

### DDIA Data Design Review

- Status: confirmed（首次测试行为编辑前已在主会话输出）。
- Data owner/source of truth：测试临时根独占 Bun HOME/cache/安装目录；本地 tarball + 精确 OMP 18.11.1 清单由 Bun 解析，在线生成的 lock 支持同轮离线重装；不把 pnpm store 或缓存目录存在当作可用证明。
- Write/read/failure：先真实 offline 安装；只识别已实测的缺 manifest/包缓存错误；一次 online 准备后删本测试 node_modules，再 offline 安装。准备成功后 offline 失败必须 FAIL；准备失败且最后 offline 仍明确缺缓存才 Vitest skip。无全局写入、共享并发、迁移或持久回滚；临时根由 afterEach 清理。
- Observability：日志包含 cache 绝对路径、包名和准备失败原因；不继承 credentials。Bun 文档核对：<https://bun.com/docs/pm/global-cache>，默认 `~/.bun/install/cache`，`BUN_INSTALL_CACHE_DIR` 可覆盖。
- Required tests：manifest 缺失、包缓存缺失、未知/混合错误不得 skip；真实 host cold-cache 准备→离线安装；受控 registry ConnectionRefused 的真实 skipped 分支。

### Legacy Change Safety Review

- Status: characterized；Review mode: normal。#114 历史失败为用户已确认事实，不重跑确认。
- 独立微型真实 Bun 探针：空 cache 对 zod@4.1.12 返回 `error: --offline: no cached manifest for "zod" (run once online, or use --prefer-offline)`；在线准备 exit 0，保留 manifest、删除测试缓存中的包目录后返回 `error: --offline: "zod" is not in the cache`。这两种实际错误构成探针分类边界，不依赖内部缓存命名协议。
- 保留面：packed package、project、其他 Runtime 目录前后相等；agent 目录变化且生成 agent.db；隔离 HOME/agent、无凭据、disabled local providers。可用缓存不再因为环境准备缺失而失败；真实宿主/未知安装错误仍失败。
- 首轮真实宿主暴露旧文案断言：精确 18.11.1 的 `src/main.ts` 在 `!session.model` 分支退出 1，先打印 SDK modelFallbackMessage，未设置时才打印旧字符串；`src/sdk.ts` 无默认模型/凭据时设置另一条文案。没有改宿主、伪造输出、归一化消息或换另一条字符串；改为同一语义的真实退出码/信号/零 RPC 输出断言，原四个目录断言及 agent.db 断言全部保留。

## 验证轮次（历史失败保留）

- 环境安装：`pnpm install --frozen-lockfile --store-dir /workspace/sbtd-plugins-offline-cache/.tmp/pnpm-store`，exit 0，18.799s；显式本地 pnpm 11.17.0 bin 前置 PATH，Corepack 缓存 `.tmp/corepack`，不改全局配置。
- 第一轮静态验证：包目录 `pnpm build` exit 0 / 6.800s；`pnpm typecheck` exit 0 / 3.743s；`pnpm lint` exit 0 / 0.639s，99 files，无修复。
- 第一轮定点 smoke：exit 1，1 failed / 55 name-filter skipped，Vitest 6.80s / 命令 7.527s；离线安装成功后因旧文案断言失败。
- 第一轮完整 harness 文件：exit 1，55 passed / 1 failed / 0 skipped，Vitest 126.23s / 命令 127.018s；失败同上。
- 第一轮包全套 `pnpm test`：exit 1，889 passed / 1 failed / 3 skipped（893 tests，45 passed / 1 failed files），Vitest 323.89s / 命令 327.559s；唯一失败同上，不将既有 3 skipped 写为 PASS。
- 受控断网分支：测试专属 Bun wrapper 将 registry 指向 `http://127.0.0.1:9`，无全局配置修改；同一 smoke 命令 exit 0，**56 skipped、0 passed tests**（其中 55 是 name filter，1 是实际 runtime skip），Vitest 1.90s / 命令 2.595s。日志明确缺 zod / pi-coding-agent manifests、cache 路径及 ConnectionRefused。文件级 Vitest 图标为 passed 不代表 smoke PASS。
- 行为断言修正后的真实定点 smoke：exit 0，**1 passed / 55 name-filter skipped**，Vitest 6.33s / 命令 6.999s。日志：`offline install completed using .../bun-cache`；`OMP 18.11.1 exited 1 before any RPC output without a provider; directory assertions passed`。
- 所有原生输出保留于本任务 ignored `reports/`，每个命令有同 stem 中文汇总；developer-local / dirty / local-only，不冒充最终 PR head CI。后续最终全套结果另行追加，不覆盖失败记录。

## 独立复核（当前已收到）

- RecordsReview：session `01a166a4-59da-77e9-8af6-a514098d574a`，kimi-code/k3，Verdict correct，0 findings；复核 records commit 全量 diff、PRD 仅四列、历史追加、时间来源、分支字段、index 单行、验收文档路径/变量边界。其结果当时列出的报错文案 blocker 已由上述行为断言修正处理；该复核不冒充最终 PR-tip Reviewy CLEAN。
- 2026-10-23T10:54:40+08:00 范围核对：记录提交后 tracked diff 仅测试文件、验收文档、index；新 task 另为 untracked 产物。install/build/tests 没有改变 schema、CHANGELOG、SBOM、lockfile 或其他 tracked 文件。

## 最终 Book Gate Plan / Release Readiness Review

上方初始 running/planned 表及验证轮次均保留为历史；本节为当前值。

| Reviewer | 最终状态 | 结论 / 证据 |
|---|---|---|
| book-ddd-distilled-modeling | not-required | 未完整 grill；无领域模型/术语歧义 |
| book-ddia-data-design | passed | confirmed；测试独占 cache，缺项识别、一次准备、真正离线重装及不可用 skip 已实跑 |
| book-legacy-change-safety | passed | characterized；保留无 Provider pre-RPC 行为和所有目录断言，历史失败及后续修正有原生证据 |
| book-refactoring-pass | not-required | 无生产代码修改；只改本测试 helper/断言与文档 |
| book-release-readiness | passed | ready（仅本次测试改动）；必需命令已通过，不授权 Registry/远端发布 |

- Production path：无生产代码或包身份变化；只改变本地测试依赖准备和可观察生命周期断言，受信 §4 gate 不变。
- Failure modes / safeguards：未知安装错误、成功准备后的离线失败继续 FAIL；真正缺 cache 且准备失败才 SKIP，理由可见。30s 子进程上限，单次准备，无全局 HOME/cache 写入；本测试 temporaryRoots 清理。完整 smoke 的 90s 总界和宿主 15s 生命周期界保留。
- Rollback / cleanup：回退本次测试/文档提交即可；无 schema、migration、SBOM、lockfile、生产数据或 global config 改动。微型探针与网络故障 wrapper 已删除；repo-local pnpm/Corepack cache 为复跑保留，ignored，不入提交。
- Residual risk：每次 smoke 使用新测试 cache，网络确不可用时允许带原因的 native skip；不承诺离线机器首次运行也能下载。消息正则锚定 RPC 退出前缀及 OMP 18.11.1 的两种文案 `No default model selected` / `No models available`，并保留 cause 的 exitCode=1、signal=null、stdoutBytes=0 检查；本地仅在 built dist 注入损坏插件，已证明 `Failed to load extension` 导致 smoke 失败，重建后健康插件恢复通过。此为 smoke-only，不能替代 §4 trusted gate。

## 最终验证证据（当前值）

命令均由唯一 controller 在本 worktree 执行；除 install 外 cwd 为 `packages/omp-sbtd`。PATH 前置 `.tmp/bin` 的 pnpm 11.17.0，Corepack cache 为 `.tmp/corepack`。命令耗时含启动，Vitest 原生 duration 单列。source 基线 `1b45e463ae6a7cfbc885fe886a762aa0be284677` + 本次测试/文档 dirty changes；developer-local / dirty / local-only，不冒充 PR head CI。最终提交 SHA 由交付回复提供，避免自引用。

| 命令 | exit | pass / fail / skip | 命令耗时 / Vitest duration | 原生 raw（均在 `reports/`，同 stem `.md` 中文汇总） |
|---|---|---|---|---|
| `pnpm install --frozen-lockfile --store-dir /workspace/sbtd-plugins-offline-cache/.tmp/pnpm-store`（repo root） | 0 | 非测试命令 | 18.799s / — | `pnpm-install-2026-10-23T103820_0800.txt` |
| `pnpm build` | 0 | 非测试命令 | 6.800s / — | `build-2026-10-23T104121_0800.txt` |
| `pnpm typecheck` | 0 | 非测试命令 | 3.087s / — | `typecheck-final-2026-10-23T105311_0800.txt` |
| `pnpm lint` | 0 | 99 files，0 fixes | 0.597s / — | `lint-final-2026-10-23T105314_0800.txt` |
| `pnpm exec vitest run test/p0-authorized-omp-rpc-harness.test.ts -t "exact local OMP 18.11.1"` | 0 | 1 / 0 / 55（仅 name filter） | 6.999s / 6.33s | `smoke-focused-behavior-2026-10-23T105234_0800.txt` |
| `pnpm exec vitest run test/p0-authorized-omp-rpc-harness.test.ts` | 0 | 56 / 0 / 0 | 127.057s / 126.40s | `harness-subset-final-2026-10-23T105315_0800.txt` |
| `pnpm test` | 0 | 890 / 0 / 3；46 files passed | 331.372s / 327.86s | `full-suite-final-2026-10-23T105522_0800.txt` |
| 同一定点 smoke，测试专属 wrapper 注入不可达 registry `http://127.0.0.1:9` | 0 | 0 / 0 / 56（1 runtime skip + 55 name filter） | 2.595s / 1.90s | `smoke-cache-unavailable-2026-10-23T105150_0800.txt` |

真实 host 输出摘录（同一 cold-cache 实跑；临时根已由测试清理）：

```text
[packed-host smoke] preparing Bun cache /tmp/kpi-authorized-rpc-harness-ABeNO8/bun-cache: error: --offline: no cached manifest for "@oh-my-pi/pi-coding-agent" (run once online, or use --prefer-offline); error: --offline: no cached manifest for "zod" (run once online, or use --prefer-offline)
[packed-host smoke] offline install completed using /tmp/kpi-authorized-rpc-harness-ABeNO8/bun-cache
[packed-host smoke] OMP 18.11.1 exited 1 before any RPC output without a provider; directory assertions passed
Tests  1 passed | 55 skipped (56)
```

- 全套 3 个既有 skip：`upstream/test/transform.test.ts` 两项需 `KPI_PROMOTION_SOURCE_ROOT`；`test/host-event-surface.test.ts` live cell 需 `SPIKE_OMP_BIN` + `HOST_EVENT_PLUGIN_TARBALL`。本次未伪造这些外部来源；本项 exact-local smoke 在全套也实际通过，不包含在这 3 项中。
- `offlineCacheMiss` 新增 5 项边界单测均通过：manifest 缺失、包缓存缺失、integrity 错误、仅 failed-to-resolve、缺缓存混合 EACCES；未知错误不分类为 cache-unavailable。
- 原失败 raw `smoke-focused-*`、`harness-subset-*`、`full-suite-*` 保留，不以最后成功覆盖。`cache-probe-observed.json` + `.md` 保存两类真实 Bun 错误观察。
- Final Test Report / Run Summary MD：generated / generated；Targeted Rerun / Affected Subset Rerun / Final Full Rerun：passed / passed / passed；rtk skipped-for-report（原生命令）。BDD skipped：内部测试准备变更，无新产品行为或 .feature，既有 harness 场景仍跑；API Contract / Cross-repo context not-needed；Mock Strategy：新 smoke/probe none，既有 harness fixtures contract-backed。
- Web/Mobile/Graft skipped：无对应改动表面或挂载；LSP not-available，以源代码/契约补充。dsh 测试未跑：用户允许 package full suite，本次代码变更仅 omp 测试。无 CI/发布操作。

## 最终独立复核与可读性

- CacheReview：session `01a166a4-229f-7254-ac77-bb7a772d92f0`，kimi-code/k3，最终 Verdict correct，0 findings；直接核对 exact 18.11.1 source、缓存 probe fail-closed 分类、prepare/rm/reinstall、隔离、timeout、native skip 和行为断言传播。确认旧文案是 incidental，同义行为保留；理论上的其他 pre-RPC exit 1 风险已在上方明示，不是 observed defect。
- Code Readability / ponytail-review：独立复核结论 `Lean already. Ship.`，net -0；现有 runCommand 复用，不新增依赖/通用 cache 框架；本地 install 闭包三处调用保持 flags/env 一致，非一次性别名。
- RecordsReview 仍覆盖已提交记录及此前文档边界；两项均是原生只读 reviewer，不是 orchestrator 的最终 Reviewy PR-tip CLEAN。主会话保持唯一 writer/验证 controller。

## 使用的模型（当前 SNAPSHOT）

下表为 `2026-10-23T11:02:17+08:00` 从本次 session jsonl 只读抽取的快照，不含此后的记录、提交、验证元数据与回复；上方「尚未采集」行保留为创建时历史，不代表当前值。assistant 计数为 type=message / role=assistant，toolCall 计数为这些消息 content 中的 toolCall。

| agent/session id | provider/model（实测） | purpose | assistant messages / tool calls |
|---|---|---|---|
| main / `01a1669b-a431-75c5-931b-9cb8276290c7` | openai-codex / gpt-6-astra | 唯一 writer、验证 controller | SNAPSHOT **58 / 109** |
| RecordsReview / `01a166a4-59da-77e9-8af6-a514098d574a` | kimi-code / k3 | 只读历史记录/文档复核 | SNAPSHOT **10 / 16** |
| CacheReview / `01a166a4-229f-7254-ac77-bb7a772d92f0` | kimi-code / k3 | 只读缓存/断言/可读性复核 | SNAPSHOT **28 / 44** |

来源：`~/.omp/logs/sbtd-offline-cache/sessions/run1/2026-10-23T02-33-58-577Z_01a1669b-a431-75c5-931b-9cb8276290c7.jsonl`；同 stem 子目录 `RecordsReview.jsonl` / `CacheReview.jsonl`。仅提取元数据，不复制完整会话或秘密。

## 最终交付边界

- 当前 status = **checking**，completed_at = **null**；本地验收无阻塞项，后续 Reviewy CLEAN + merge 仍由编排方负责。未 push、开 PR、comment、tag、publish 或 merge。
- 只对指定共享文档及测试作显式路径本地提交；不改历史事件、schema、CHANGELOG、全局配置。报告和缓存 ignored，不进入提交；同机保留 raw，跨机器恢复不可假定。

## Reviewy B1 fix（@950df81）

- 本轮沿用 strict、唯一 writer/验证 controller；仅 B1 测试断言及指定文档，deferred nit 不动。未完整调用 grill-with-docs：需求与验收明确，无领域歧义。
- 源码确认 `runPackedHostSmoke` 将完整 stderr 接到 `actual OMP host ended during its public RPC exchange: ` 后；采用 `^actual OMP host ended during its public RPC exchange: No (?:default model selected|models available)\b`，保留 cause 及目录/agent.db 断言。现有 console.info 仍准确，未改。
- `extractPackedPlugin` 直接 `pnpm pack`，package 无 prepack/build hook，安装使用 `--ignore-scripts`；注入只改 ignored `dist/extension.js` 首行，未改生产源码。negative 的 received message 为 `actual OMP host ended during its public RPC exchange: Failed to load extension /tmp/kpi-authorized-rpc-harness-Wy12OP/installed-plugins/node_modules/@kunolu/o…: Failed to load extension: B1 injected broken plugin`；其后仍有 `No default model selected`，但锚定消息检查正确拒绝。
- 首轮 build 在 runner 启动前因 repo-local pnpm 缺 `dist/pnpm.mjs` 失败；保留原生报告。通过 `npm pack pnpm@11.17.0 --ignore-scripts --pack-destination .tmp` 取得同版包，仅补回缺失 runtime，`pnpm --version` 为 11.17.0；未改全局配置。随后 build 按现有 pnpm 行为恢复依赖并成功。
- 验证均在本 worktree 的 `packages/omp-sbtd`，PATH 前置 `.tmp/bin`，COREPACK_HOME 为 `.tmp/corepack`。证据基线 `950df81d947aa30bf554757db1df84eb0b35f838` + B1 dirty changes，developer-local / local-only，不冒充最终 PR head CI。下列 raw 均位于本任务 `reports/`，各有同 stem 中文 `.md`，旧失败未覆盖。

| 命令 / 轮次 | exit | 结果 | 原生报告文件 |
|---|---|---|---|
| `pnpm build`（初次） | 1 | 环境失败：pnpm runtime 缺失，未执行 build | `b1-build-2026-10-23T114239+0800.txt` |
| `npm pack pnpm@11.17.0 --ignore-scripts --pack-destination .tmp`（repo root） | 0 | 获取同版 runtime | `b1-pnpm-runtime-fetch-2026-10-23T114255+0800.txt` |
| `pnpm --version` | 0 | 11.17.0 | `b1-pnpm-version-2026-10-23T114256+0800.txt` |
| `pnpm build` | 0 | 通过 | `b1-build-2026-10-23T114257+0800.txt` |
| `pnpm typecheck` | 0 | 通过 | `b1-typecheck-2026-10-23T114316+0800.txt` |
| `pnpm lint` | 0 | 99 files，0 fixes | `b1-lint-2026-10-23T114319+0800.txt` |
| `pnpm exec vitest run test/p0-authorized-omp-rpc-harness.test.ts -t "exact local OMP 18.11.1"`（healthy） | 0 | 1 passed / 55 name-filter skipped | `b1-smoke-healthy-2026-10-23T114319+0800.txt` |
| 同一定点命令（built dist 首行注入 `throw new Error("B1 injected broken plugin");`） | 1 | 预期 1 failed / 55 name-filter skipped；消息断言显示 `Failed to load extension` | `b1-smoke-injected-broken-2026-10-23T114337+0800.txt` |
| `pnpm build`（恢复） | 0 | 重建通过；随后文本计数及 grep 均证明 `B1 injected` 为 0 | `b1-build-restore-2026-10-23T114343+0800.txt` |
| `git status --short`（恢复后，repo root） | 0 | 仅指定 test/doc，未出现 dist | `b1-status-after-restore-2026-10-23T114347+0800.txt` |
| 同一定点命令（restored healthy） | 0 | 1 passed / 55 name-filter skipped | `b1-smoke-restored-2026-10-23T114348+0800.txt` |
| `pnpm exec vitest run test/p0-authorized-omp-rpc-harness.test.ts` | 0 | 56 passed / 0 skipped；126.72s | `b1-harness-2026-10-23T114408+0800.txt` |
| `pnpm test` | 0 | 890 passed / 3 skipped，46 files passed；331.21s | `b1-full-suite-2026-10-23T114616+0800.txt` |

- B1 Book Gate Plan / 结果：legacy safety before-dev 已 characterized（Reviewy 已确认的 false positive + 源码 + 既有 smoke safety net），本轮注入负向及恢复正向均通过预期；DDD、DDIA、production refactoring、release readiness 为 not-required：无领域/数据流/缓存机制/生产运行或发布变化。手写断言可读性复核：直接复用 `toMatchObject`，无新增抽象。独立复核沿用编排方 Reviewy 流程，本轮不声称新 PR-tip CLEAN。
- BDD skipped（仅内部测试断言，无新 .feature）；rtk skipped-for-report；Graft/Web/Mobile skipped（无对应变更表面或挂载）；API Contract / Cross-repo context not-needed；真实 smoke Mock Strategy none。3 个既有环境门控 skip 不计 PASS；CI live cell 只运行 `run-live-cell.ts`，不运行本 Vitest，本轮真实本地证据证明 B1。仍为 smoke-only，不替代 §4 gate。

### 本轮模型（SNAPSHOT）

`2026-10-23T11:51:56+08:00` 只读抽取 RD/session 下本会话 JSONL：计数 `type=message` 且 `message.role=assistant`，toolCall 为这些消息 content 的同名项。计数不含此后文档/提交/回复，最终计数由编排方补充。

| session | model / thinking | purpose | assistant messages / tool calls |
|---|---|---|---|
| ping / `01a166d8-e39e-7510-8b86-d118fa3ff68e` | openai-codex/gpt-6-astra:high | reachability ping | 1 / 0 |
| main / `01a166d9-a19f-75e1-b35a-f6e1e0009143` | openai-codex/gpt-6-astra:high | sole writer B1 fix | SNAPSHOT **15 / 37** |

来源：`/home/box/.omp/logs/sbtd-offline-cache/run-fix1/session/2026-10-23T03-41-41-151Z_01a166d9-a19f-75e1-b35a-f6e1e0009143.jsonl`；ping 为同 RD 的 `ping-session/2026-10-23T03-40-52-510Z_01a166d8-e39e-7510-8b86-d118fa3ff68e.jsonl`。沿用既有 TaskStore 历史 schema blocker，不重跑、不声称 lifecycle/自动恢复通过；本次仅显式授权的共享记录更新。status 保持 checking，completed_at 保持 null，无远端操作。

## #116 合并回填（当前值）

- #116 已在 Reviewy CLEAN @`12fd0142f3c9dbf3efb4a6a04294646265675cce` 后 squash-merge；merge SHA `25d7e83bbc25b6f7d2c5018d7f945376670a2d9a`，mergedBy `KunoLu`。`git log -1 --format='%H %cI' 25d7e83` 与 `gh pr view 116 --json state,mergedAt,mergeCommit,mergedBy,headRefName` 核实 MERGED、历史 head `chore/offline-cache-smoke` 及上方时间。
- status 当前为 done，completed_at 取 merge commit 的 `2026-10-23T12:15:38+08:00`；上方 checking、等待合并、SNAPSHOT 等原文均保留为历史，不代表当前状态。本次为用户明确授权的记录回填，不重绑定历史 branch。

### 模型计数 FINAL 补充

来源：#116 PR body 的 Models 表（编排方于 2026-10-23 只读采集的 `gh pr view 116 --json body` 输出 `pr116-body.md`）。计数口径仍为 `type=message` 且 `message.role=assistant`，tool calls 为这些消息 content 中的 `toolCall`。

| session | model / thinking | purpose | assistant messages / tool calls |
|---|---|---|---|
| main / `01a1669b-a431-75c5-931b-9cb8276290c7` | openai-codex/gpt-6-astra:high | 首轮唯一 writer、验证 controller | FINAL **69 / 121** |
| CacheReview / `01a166a4-229f-7254-ac77-bb7a772d92f0` | kimi-code/k3:max | 缓存修复只读复核 | FINAL **28 / 44** |
| RecordsReview / `01a166a4-59da-77e9-8af6-a514098d574a` | kimi-code/k3:high | 历史记录只读复核 | FINAL **10 / 16** |
| main / `01a166d9-a19f-75e1-b35a-f6e1e0009143` | openai-codex/gpt-6-astra:high | B1 唯一 writer、真实宿主注入与验证 | FINAL **22 / 47** |

B1 的 `2026-10-23T11:51:56+08:00` SNAPSHOT **15 / 37** 原样保留；首轮及 reviewer 的旧快照同样保留，不以快照冒充 FINAL。

### 会话标题生成纠正 / 补充

以下逐字镜像 #116 PR body 的 session-title-generation 表；来源为 `~/.omp/logs/omp.2026-10-23.<pid>.log`，时间均 Asia/Shanghai。标题生成不属于代码/记录写入模型表；本节纠正/补充本任务此前任何「no grok」或「标题模型未知/未记录」的读法，旧模型表只是省略了 title-gen。

| omp pid / session | title-gen requests (Asia/Shanghai) | result | fallback |
|---|---|---|---|
| 806930 run1 main `01a1669b` (10:34:09–10:34:53) | composer-2.5 ×2, k3-256k ×1, deepseek-flash ×1, gpt-6-astra ×1, grok-4.7 ×1, grok-4.6 ×1, gpt-6.1-sol ×1 (8) | composer-2.5 1 success ("Execute attached prompt task"); the other 7 returned no title (grok-4.7 replied 10:34:47, grok-4.6 replied 10:34:48, no title) | true (grok replied) |
| 806930 CacheReview (10:43:15–10:43:43) | composer-2.5 ×1, k3-256k ×1 | composer no title; k3-256k success | k3 (not grok) |
| 806930 RecordsReview (10:43:29–10:43:59) | composer-2.5 ×1, k3-256k ×1 | composer no title; k3-256k success | k3 (not grok) |
| 26506 B1 main `01a166d9` (11:41:51–11:42:35) | composer-2.5 ×2, k3-256k ×1, deepseek-flash ×1, gpt-6-astra ×1, grok-4.7 ×1, grok-4.6 ×1, gpt-6.1-sol ×1 (8) | composer-2.5 1 success ("Execute attached prompt task"); deepseek-flash response error (401); the others returned no title (grok-4.7 replied 11:42:32, grok-4.6 replied 11:42:33, no title) | true (grok replied) |

两次 main 均发出 8 次标题请求；grok-4.7 / grok-4.6 有回复但无标题，计为 title-only fallback，未写代码或记录。deepseek-flash 在 pid 26506 为 401 response error，在 pid 806930 未产出标题。CacheReview / RecordsReview 均在 composer-2.5 无标题后由 k3-256k 生成标题。
