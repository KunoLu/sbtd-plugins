---
schema_version: 1
id: omp-sbtd-session-compact-code
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：按明确交付执行 strict；唯一 writer；由 feat/omp-sbtd-session-compact 分支及后续 PR 交付；不修改 PRD 裁决、全局 omp 或发布配置。
status: checking
branch: feat/omp-sbtd-session-compact
created_at: '2026-10-23T19:01:18+08:00'
updated_at: '2026-10-23T19:42:33+08:00'
completed_at: null
---
# session_compact v2 代码与隔离宿主验证

## 范围与入口

- 编排方整理：实现 PRD D1-B / D2-A / D3-B / D4-A / D5-A 与 §4.1 门禁；保留 peer `>=18 <19` 和认证目标 18.11.1。成功 handoff 无合格关联事件恢复硬失败；未尝试/触发失败仍 diagnostic，不算 handoff 覆盖。
- 基线 `684387835b27d46b3b96b01f2015e42fe7937b12`，入口工作区干净，根与分支匹配。#122 回填独立提交 `a485924`；旧任务日期历史仅追加。
- 未完整调用 grill-with-docs：裁决与验收明确；不新增裁决。BDD 沿用中文场景和英文 Gherkin keywords，测试 seam 为既有 adapter-edge、validator、runtime 注册与 frozen-tarball live cell。
- 历史认证证据/ledger 保持只读；不修改 PRD、dsh-sbtd、README_zh 命名、package version 或 release stamping。实跑缺 method 或 method 非 handoff 时停止后续提交，不放宽 schema。
- 路径与 ignore 已核对：共享 ai/tasks 可跟踪，reports 与 .sbtd 受保护。沿用既有 TaskStore 全库历史 schema blocker，不重跑已知失败；此为明确要求的共享 Markdown 交付，不声称 helper lifecycle 或自动恢复通过，不写 active/developer/handoff/ignore。
- LSP references 实际返回 No language server found for this action；使用源码调用面与 typecheck。Graft skipped：无已验证受管连接，不改接线。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 无完整 grill 或新领域歧义，沿用已决定 PRD | before-dev | not-required |
| book-ddia-data-design | observer/driver 跨进程证据与版本化 schema | before-dev | passed（confirmed：宿主 entry/事件为真源；单 observer 序列和同步落盘；同 session 基线差集与无竞争校验；旧记录只读、不重标） |
| book-legacy-change-safety | 既有 handoff 诊断改硬失败、跨流排序风险 | before-dev | passed（characterized：回归 red 准确暴露成功 handoff 无事件仍 diagnostic；保留旧 approval/session/compacting 安全网） |
| book-refactoring-pass | 修改既有 runtime 与 evidence validator | before-dev | passed（proceed / normal：复用现有 seam，无前置重构或新增依赖） |
| book-release-readiness | 宿主集成与运行门禁变化 | finish | passed（ready：必需本地命令、最终全量、真实18.11.1 cell、负例smoke及两项独立review闭环；不代表合并/发布或全18.x认证） |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T19:01:18+08:00 | planned | in-progress | 编排方整理：建立独立 strict 代码交付记录 | 分支/基线/路径/ignore 核对；完整 PRD、行 C 背景、testing spec 与 BDD 已读 |
| 2026-10-23T19:15:04+08:00 | in-progress | checking | 编排方整理：v2 实现与首轮真实 handoff 通过，进入完整验证及独立 review；完成只由合并回填确认 | 18.11.1 live run-1792753752427-7153a6ad；focused-handoff 74 passed / 1 env-gated skipped；focused-history 144 passed / 1 env-gated skipped |
| 2026-10-23T19:32:13+08:00 | checking | checking | 编排方整理：审查修正与最终完整套件、第二轮 frozen-tarball live 均通过；保留 checking 待合并回填 | 917 passed / 0 failed / 3 skipped；run-1792754760821-9e927e73 handoffObserved=true；VersionReview 两项闭环；WindowReview 结果另追加 |
| 2026-10-23T19:40:43+08:00 | checking | checking | 编排方整理：两项独立review无阻断项，release readiness在代码交付范围ready；完成时间留待合并回填 | WindowReview / VersionReview correct；917 passed / 3 skipped；最终live与负例smoke通过；183个源码/测试/契约文件摘要保持一致 |

## 验证记录

- #122 回填：Python/PyYAML smoke PASS，检查 YAML 完成字段、原正文/历史逐行顺序保留、新增行归因零命中；git diff --check PASS。GitHub/模型/CI 历史事实按编排方材料记录，Git squash SHA 与 %cI 已实际核对。
- `pnpm install --frozen-lockfile` 已启动；结果随后追加。

## 实现与验证（2026-10-23T19:15:04+08:00）

- D1/D2：`src/runtime/omp-extension-v2.ts` 定义真实 `session_compact` 结构，独立保留 `session.compacting`；13 required + credential_disabled optional，共 14。普通/extension compact 的宿主结构允许 optional method，但 handoff 覆盖必须实测 `method="handoff"`，缺失/其他值硬失败，不从 fromExtension 推导。
- D3：版本化模块与公开符号按既有命名改 v2；当前 producer/schema/consumer/test/spec 改 v2，无旧语义 shim。ledger document 仅为历史只读解析保留 v1 原标识/摘要；新 append/finalize 只收 v2，当前支持矩阵/查询不把历史 v1 计为 v2。未修改历史 ledger/evidence。
- D4：observer 的只读 `/host-event-window` 在 idle barrier 后快照全量 compaction entry 摘要，同步 append 基线/完成边界；driver 一次 handoff，RPC 返回后取完成边界。仅比较 observer 的序列，不比较跨进程序号或墙钟；单一 entry 差集必须与窗口内全部 compaction 观测一致。重复 entry 不增加覆盖，竞争 compact 失败。
- D5：package peer/dev/lock 未改；真实宿主仅使用 worktree 的 `packages/omp-sbtd/node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js`，realpath 为 `/workspace/sbtd-plugins-session-compact-code/node_modules/.pnpm/@oh-my-pi+pi-coding-agent@18.11.1/node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js`；Node 读取其 package.json 得到 **18.11.1**。Bun 使用已有 `/usr/local/bin/bun`，全局 omp 不执行、不安装、不修改。
- 安装：原始 `pnpm install --frozen-lockfile` 因 Corepack 默认 `/usr/local/share/corepack/v1` EACCES，exit 1；`COREPACK_HOME=/home/box/.cache/node/corepack pnpm install --frozen-lockfile` **exit 0**，pnpm 11.17.0，新增 738 本地依赖，无 lock 改动。
- TDD red：`pnpm --filter @kunolu/omp-sbtd exec vitest run test/host-event-surface.test.ts -t 'Scenario: handoff 不冒充' --no-file-parallelism --maxWorkers=1 --testTimeout=30000`，1 failed / 38 filtered；旧 reasonCodes=[]，准确缺少硬失败。后续 focused-handoff 为 **2 files / 74 passed / 1 env-gated skipped**。
- 首轮定点：7 files，216 passed / 1 failed / 1 env-gated skipped；唯一失败为当前 parser 拒绝历史 v1 ledger。加入独立历史读取 schema、v2-only append/支持查询及不变性回归后，focused-history **3 files / 144 passed / 1 env-gated skipped**。不改旧 evidence 的标签或 bytes。
- `pnpm --filter @kunolu/omp-sbtd typecheck` **exit 0**。首轮 lint 为 9 个本改动文件格式错误，无其他 lint finding；限定这 9 文件 `pnpm exec biome check --write ...` **exit 0**，未格式化无关文件。完整 lint 结果随后追加。
- `pnpm --filter @kunolu/omp-sbtd build` **exit 0**；`pnpm --filter @kunolu/omp-sbtd pack --pack-destination /tmp/session-compact-pack-zslusxz5` **exit 0**。首轮 tarball `kunolu-omp-sbtd-0.2.0-rc.1.tgz` SHA256 `4437c6feffe49ceea3d5517c0f0f0754016c19b712eb38e3d5564ed2d850498f`；这是 dirty candidate 的 developer-local 证据，不冒充提交 SHA 或已发布认证。

### 首轮隔离 live cell 原生命令与结果

```sh
COREPACK_HOME=/home/box/.cache/node/corepack \
SPIKE_OMP_BIN=/workspace/sbtd-plugins-session-compact-code/packages/omp-sbtd/node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js \
HOST_EVENT_PLUGIN_TARBALL=/tmp/session-compact-pack-zslusxz5/kunolu-omp-sbtd-0.2.0-rc.1.tgz \
HOST_EVENT_RUNS_ROOT=/tmp/session-compact-pack-zslusxz5/live \
HOST_EVENT_TARGET_VERSION=18.11.1 \
pnpm --filter @kunolu/omp-sbtd exec tsx scripts/p0/host-event/run-live-cell.ts
```

- **exit 0 / passed-with-diagnostics**，profile `omp-host-events-v2`，13 required 均 observed，`handoffObserved=true`；reasonCodes=[]，唯一 diagnostic `OPTIONAL_EVENT_ABSENT:credential_disabled`。真实宿主+实际 tarball，模型端沿用现有 loopback deterministic stub，无真实 provider credential；不是全模型 E2E、不是 public certified。
- runId `run-1792753752427-7153a6ad`；同 session digest `f824fcccd9823c919d6164ea11a82bd6269937c3a98a6f9115459b4327315bd8`。窗口 digest `d6fdfd7a1af1a34153fc9ae1a0338e164f18d7871790807e326c066c38b257a6`：baseline **55** → event **56** → complete **57**；前快照 []，后快照仅一个 entry digest `f73878cf4b73802fef5982adb6ea3d6883784a9a0132437bfce6c823b2dfd82d`，事件完全匹配，窗口内无其他 compact。
- 实际 event top-level fields `compactionEntry/fromExtension/type`；`schemaValid=true`、`compactionMethod="handoff"`、`fromExtension=false`。entry field list 含 `method`、`id`、`parentId`、`type`、`timestamp`、`runtime`、`summary`、`shortSummary`、`firstKeptEntryId`、`tokensBefore`、`tokensAfter`、`details`、`preserveData`、`providerReplayThroughEntryId`、`fromExtension`；只记录字段名与摘要，不存正文。先前普通 compact 在 seq 38，位于窗口外，不作 handoff 证据。
- driver `attempted=true / ok=true / attempts=1`，边界 55/57。18.11.1 源码 `session-maintenance.ts:2076,2484–2497` 证明 handoff 带 method、await emit；observer 同步 append 在返回前完成，后续 idle-boundary 证明可见排空。**STOP 未触发**。
- 原生报告存于受保护的本 task `reports/`：build-initial、pack-initial、live-initial、focused-initial、focused-handoff、focused-history、typecheck-initial、lint-initial、format-scoped。每轮失败保留；最终汇总随后生成。rtk=skipped-for-report，使用原生 runner。
- 独立 read-only reviewers：WindowReview（窗口/隐私/宿主边界）与 VersionReview（版本/历史/认证消费者）；主会话唯一 writer 与验证 controller，reviewer 不运行测试或修改文件。

## 审查修正与最终验证（2026-10-23T19:32:13+08:00）

- 首轮完整 `COREPACK_HOME=/home/box/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1 pnpm --filter @kunolu/omp-sbtd test`：**46 files，910 passed / 1 failed / 3 skipped，317.52s，exit 1**。唯一失败 `test/p0-package-release.test.ts` 的「受控 CLI 只从当前验证结果记录精确 RC 候选证据」返回 `SBOM_MISMATCH`；原因是最终源码晚于首轮 build。保留 `reports/unit-full-initial.txt/.md`，按项目原 build 重新生成 SBOM，不绕过 gate。
- 窗口连续性补强：新增 Session 中途切换回归先 red（1 failed / 57 filtered，handoffObserved 错为 true），随后要求窗口中 observer 序列无缺口、所有事件同 session 且无 session_start/switch/branch/tree；前后恢复同一 Session 不能隐藏竞争 entry。四个负例覆盖切换、分支、树及缺记录。定点 `focused-review` **149 passed / 1 env-gated skipped**；BDD 与 testing spec 同步此证明边界。
- VersionReview 独立审查：P1 为 certification runner predecessor 只按 tarball/runtime 选取，可能让第一条 v2 链链接旧 v1。已追加 `contractProfile === "omp-extension-v2"` 分区，reviewer 再读关闭。另报的覆盖 refine crash 路径由 live runner 先返回结构化 `blocked / HANDOFF_COVERAGE_UNVERIFIED` 截断，保留原诊断 verdict/bundle；reviewer 复核后关闭，最终 `correct`。当前 append/finalize 严格 v2，历史读取保持原标识，不构造升级 shim。
- 当前 runbook/acceptance 的 contract 指针已改 v2；早期 beginner guide 只追加现行判据指针，保留 v1 feasibility 示例及历史结果，不把旧示例重标为认证。
- 最终 build：`pnpm --filter @kunolu/omp-sbtd build` **exit 0**；sourceTreeSha256 `b83bba930ca740b2b9b3c09b1e8262204062a0bbd2cd5209a01576200f0ed48f`，SBOM SHA256 `84175ca4fc81b033d0d0013894115c4ba8645b698faaee2e9cec5b67df5540cb`。
- `pnpm --filter @kunolu/omp-sbtd smoke` **exit 0**，compiled extension 的 12 个命令/事件阶段通过；这是 hand-rolled host seam smoke，不冒充真实宿主投递。
- 最终影响子集：`pnpm --filter @kunolu/omp-sbtd exec vitest run test/p0-package-release.test.ts test/host-event-surface.test.ts test/p0-three-profile-certification.test.ts test/p0-compatibility-ledger.test.ts test/omp-host-contract.test.ts test/runtime.test.ts test/extension.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000`：**7 files，242 passed / 1 env-gated skipped，25.56s，exit 0**；原 SBOM 失败文件 14/14 通过。
- 最终完整命令同首轮：**46 files 全部 passed；917 passed / 0 failed / 3 skipped（920）；325.91s；exit 0**。3 skipped 为两个 `KPI_PROMOTION_SOURCE_ROOT` upstream promotion 场景与一个 env-gated live 场景；后者已由下方独立实际 live 命令执行，另外两个缺相应上游环境，不计作通过。既有 bun-offline smoke 在其独立 `/tmp` cache 准备后通过；未修改全局 Bun/OMP 安装。
- 最终 `pnpm --filter @kunolu/omp-sbtd typecheck` **exit 0**；`pnpm --filter @kunolu/omp-sbtd lint` **exit 0 / 99 files / no fixes**。没有剩余 lint failure，因此不需要 origin/main clean-checkout 豁免。
- 最终 pack：`pnpm --filter @kunolu/omp-sbtd pack --pack-destination /tmp/session-compact-final-j99vzh4x` **exit 0**；`kunolu-omp-sbtd-0.2.0-rc.1.tgz` SHA256 `280fe87b40b4ba88958abe69cbd69675688e9d19f79b202480eea57d13ae2553`。包版本与 peer/dev/lock 均未改。

### 最终隔离 live 证据

执行与首轮相同原生命令，替换 `HOST_EVENT_PLUGIN_TARBALL=/tmp/session-compact-final-j99vzh4x/kunolu-omp-sbtd-0.2.0-rc.1.tgz`、`HOST_EVENT_RUNS_ROOT=/tmp/session-compact-final-j99vzh4x/live`；SPIKE_OMP_BIN 仍为同一隔离 **18.11.1** realpath，目标版本不变。

- **exit 0 / passed-with-diagnostics**；runId `run-1792754760821-9e927e73`；profile `omp-host-events-v2`；13 required 均 observed；`handoffObserved=true`；reasonCodes=[]，唯一 diagnostic `OPTIONAL_EVENT_ABSENT:credential_disabled`。没有 skip/bypass/continue-on-error；workflow 现有硬门原样调用扩展后的 cell，无需修改 `.github`。
- 同 session digest `4ae2d8a2cb92cd01d4bc75b745e69b231887059a7dba5550a0f9b8e60f966218`，window digest `4d0b3b10377f96b6e47f95d7ab943738a0954e0a3c54aa4a98a15b07fa27e430`；baseline seq **55** 的 entry 集合为 []，event seq **56**，complete seq **57** 的集合仅含 `0e39ef664d74fa409ea9688a8d12f746974053fc2ed2406744d8eb00146440b8`，与事件 entry digest 一致。窗口序列连续，无第二 compact、无竞争 entry、无 Session/tree 切换。
- 实际 top-level fields `compactionEntry/fromExtension/type`；entry fields 与首轮同一允许清单，含真实 `method`；`schemaValid=true`、`compactionMethod="handoff"`、`fromExtension=false`。driver `attempted=true / ok=true / attempts=1`，边界55/57。**STOP 未触发**。
- `real-capture-negative-smoke` 直接加载此真实 v2 run 的 observer/scenario，用实际 host identity 再验：原捕获通过；删除 method 或改为 other 均得到 **failed + HANDOFF_EVENT_UNOBSERVABLE（非 diagnostic）**，exit 0。不改真实日志，不把构造负例当真实宿主发射。
- 原生完整输出与同 stem 中文九节汇总：`reports/unit-full-final.txt/.md`、`live-final.txt/.md`、`focused-final.txt/.md`、`build-final.txt/.md`、`pack-final.txt/.md`、`smoke-final.txt/.md`、`typecheck-final.txt/.md`、`lint-final.txt/.md`；失败轮原件仍在。同 stem 负例 smoke 汇总及最终提交绑定检查随后补齐。
- 范围检查：新增行禁词=0、冲突标记=0；两份 task YAML 解析通过；PRD、package.json、pnpm-lock 与 origin/main 字节一致。没有 dsh-sbtd、README_zh、CHANGELOG、历史 ledger/evidence 修改。提交后的 `origin/main..HEAD` 检查另追加。

### 简化、可读性与剩余边界

- ponytail-review：复用既有 Zod/Node stdlib/driver/observer seam，无新依赖、平行 registry、兼容 shim 或 retry 框架；两次只读 snapshot 与有界观测等待用于必要证明，不能删。Code Readability Review：窗口校验用具名 prior/after/added/windowEvents/uninterrupted 分阶段表达；删除 inventory-copy 断言，改为14订阅边界拒绝与真实覆盖断言。
- Nits（独立后续文档 PR 可处理）：旧方案/手册还有 KPi/17.x feasibility 时代的路径和示例；已明确历史边界，此交付不重写日期历史或已认证结果。没有为这些编辑性问题扩大实现。
- 历史 v1 认证被排除在当前 v2 支持派生之外，不等于撤销旧历史事实；当前 v2 append/revocation 不改旧链。若需要新的历史展示或历史链操作，需独立范围，不能在本任务添加旧语义 shim。
- BDD=traceable，中文场景+英文 keywords；API Contract=verified（隔离18.11.1类型/awaited emit源码与真实投递）；Cross-repo context=complete（目标宿主这一条链），并非所有18.x；Mock Strategy=contract-backed（单元与loopback模型端），real-host smoke与compiled fake-host smoke分开。rtk=skipped-for-report；Graft=skipped；Web/Mobile工具 not-needed。
- 回滚范围为代码/契约/spec/SBOM 提交；无用户数据迁移或全局配置变更。报告为 developer-local / dirty / local-only，提交后以源文件摘要核对绑定；不冒充 CI 或公开 certified。TaskStore 全库历史 blocker 保留，不声称 active/handoff 自动恢复可靠。

## 独立复核闭环与交付门禁（2026-10-23T19:40:43+08:00）

- WindowReview 最终 **correct / 0 blocking findings**：独立核对 pinned 18.11.1、最终真实run、`getEntries()`全量语义、awaited emit、同步落盘、同session/tree连续窗口、前置到达、重复/竞争/缺方法、脱敏、诊断与certification隔离。
- P3 nit（按编排方整理的“只修 blockers”范围留后续 PR）：`src/runtime/omp-extension-v2.ts:44–45` 沿用旧注释 `REQUIRED_HOST_EVENTS`，该常量已不存在；未来仅将注释改指 `test/runtime.test.ts` 注册面锁，不影响实际 inventory/注册行为。未为此再变更已验证生产源码。
- Release Readiness Review：**ready（仅代码交付验证范围）**。必需命令 exit 0、完整suite 917/0/3、真实live `handoffObserved=true`、真实捕获的缺method/other负例硬失败、独立review闭环。已覆盖超时、有界等待、串行一次handoff、证据隔离、失败拒绝；无新依赖/持久服务/数据迁移/全局变更。回滚为本交付代码/spec/SBOM提交；发布与合并需各自流程，不把peer范围当逐版本认证。
- Native/raw 与同stem中文汇总均保留在受保护 `reports/`，包括 `WindowReview`、`VersionReview`、`real-capture-negative-smoke`；生成报告不冒充公开认证。未生成长期lesson：本轮修正已有PRD/契约的执行缺口，行为规则已落入BDD/testing，不复制身份相关长期记录。
- 源码绑定：最终静态检查后对183个源码/脚本/测试/feature/当前契约/manifest/lock文件取SHA256，最终suite、live与review后逐一核对不变；提交后继续与Git blob核对，避免用旧HEAD冒充新源码验证。
- task保持 **checking / completed_at null**；由 `feat/omp-sbtd-session-compact` 分支及后续 PR 交付。后续合并回填另追加done事件；不将实现、验证、部署、发布混为一项完成。

## 提交绑定与范围终检（2026-10-23T19:42:33+08:00）

- 代码提交：`2311a410ca739899b0ad3eaf0e14d4ef7d78ac3d`（35 files，包含runtime模块76%相似度重命名）；首个独立历史回填提交 `a48592459cfd6d01825629f7c27c395ca7e7d01f`。代码提交只在两轮真实18.11.1 live method=handoff证明、完整验证与独立审查闭环后创建。
- 已将最终验证时保存的183个源码/脚本/测试/feature/当前契约/manifest/lock摘要逐一与 `2311a41` Git blob核对：**全部一致**。这是已有本地运行与代码提交的字节绑定，不捏造在新SHA上重新执行完整suite或远端CI。
- `git diff --check origin/main..HEAD` **exit 0**；`git diff --stat origin/main..HEAD` 为 **36 files，1157 insertions / 302 deletions**（包含首个回填）；完整stat保留 `reports/committed-diff-stat.txt`。后续仅此task追加终检证据，因此最终stat行数可以增加，不把该历史计数覆盖。
- `git diff origin/main..HEAD -- docs/prd/omp-sbtd-session-compact.md` **empty**；package.json、pnpm-lock同样empty。无 dsh-sbtd、README_zh rename、CHANGELOG release stamping、历史ledger/evidence修改。
- committed新增行禁词检索 **0 hits**；所有changed文件冲突标记 **0**；两份task frontmatter YAML可解析，当前task严格为checking且completed_at null；#122原正文与历史事件逐行、顺序保留（只更新其当前完成字段并追加记录）。
- 本节是文档证据追加，不改变上述已验证代码；最终提交列表与最后HEAD范围检查由交付输出列明。受保护reports不是公开认证材料，源码字节绑定不承诺TaskStore自动恢复或跨机本地报告可用。
