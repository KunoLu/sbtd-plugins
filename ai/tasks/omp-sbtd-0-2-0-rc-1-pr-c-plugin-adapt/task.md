---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-22 指示执行行 C（插件适配 sbtd v2.0.2 + omp 18）
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-c-plugin-adapt
created_at: '2026-10-22T11:18:35+08:00'
updated_at: '2026-10-22T12:44:43+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 C：插件适配 v2.0.2 与 omp 18

## 目标

按 `docs/prd/omp-sbtd-0.2.0-rc.1.md` 行 C（L69）、D8、D11 与 §4「任务 C 宿主 smoke 硬门」执行：

- D11 宿主升级（行 C 独占）：`packages/omp-sbtd/package.json` peerDependencies `@oh-my-pi/pi-coding-agent` `>=17.3.5 <18` → `>=18 <19`；devDependency 精确钉 `17.3.5` → `18.11.1`；根 `pnpm-lock.yaml` 相应更新（pnpm@11.17.0）。
- 按 18.11.1 API 重跑 typecheck 与全部测试，修复破坏。
- 插件适配 sbtd v2.0.2（含行 B task.md 验证证据第 16 条遗留的 `src/extension.ts` trellis 能力映射 / profileCatalog optional `trellis` 项）。
- D8：若 5 个 Python 依赖 fail-closed 隔离预检尚未接线，则接线（不自动 pip install；验签缺 cryptography 拒跑；可降级 skipped 的普通入口：无）。
- HARD GATE：omp 18.11.1 真实宿主 smoke PASS（插件加载、工具/hooks 注册、onboard 冒烟）；parser fixture 不算；失败修到通过，不退回旧 range。

## 非目标

- 不触碰行 B 锁定的 p0-v4 transform（D14 三项）与 overlay catalog。
- 不开始行 D / R / E（不写 CHANGELOG Breaking 条目、不改 README 兼容说明、不 bump version、不 tag、不 publish）。
- 不 push、不开 PR、不评论 GitHub、不 merge；仅在本分支显式暂存范围内提交，由 orchestrator 推送。
- 如需契约或 PRD 变更：停止，记录 CONTRACT-CHANGE-NEEDED。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T11:18:35+08:00 | in-progress | in-progress | 创建事实：— → in-progress；无可证明前态，按 schema 使用同阶段快照，不捏造 planned transition | created_at；c9df45d（提交于 11:18:59+08:00） |
| 2026-10-22T11:41:30+08:00 | in-progress | in-progress | 宿主 pin/API 实现提交，未宣称阶段完成 | git commit 20acfc8 |
| 2026-10-22T11:42:01+08:00 | in-progress | in-progress | readiness 与 D8 实现提交 | git commit 4bad981 |
| 2026-10-22T11:48:46+08:00 | in-progress | in-progress | 真实宿主 smoke 与验证证据提交；仍有 strict blockers | git commit d3b7669 |
| 2026-10-22T11:52:43+08:00 | in-progress | in-progress | orchestrator 复核证据提交；用户确认远端 tip 为此提交，push 精确时刻未记录 | git commit 45e0278；本轮用户给定远端事实（约 11:52） |
| 2026-10-22T11:55:42.520306+08:00 | in-progress | in-progress | CI 报告 session_branch 与 handoff validator blockers，未把失败伪记为 done | run 39719390932；ci-39719390932-failed.log |
| 2026-10-22T12:09:16+08:00 | in-progress | in-progress | D11 evidence-only 补充：安装路径 smoke 通过并取代 wrapper gate；保留原 lifecycle / release blockers，不宣称 strict done | 验证证据 18–26；row-c-install-smoke.mjs；本事件为同阶段证据更新，未执行 TaskStore lifecycle transition |
| 2026-10-22T12:12:16+08:00 | in-progress | in-progress | install-discovery smoke 提交保留 | git commit 260d121 |
| 2026-10-22T12:20:20+08:00 | in-progress | in-progress | PR #107 Reviewy 修复轮进行中；用户明确 strict；模型节不改 | 当前会话；event red 5 failed；route red 2 failed / 10 passed；D8 cwd red 2 failed |
| 2026-10-22T12:28:13+08:00 | in-progress | in-progress | 中断后继续同任务 strict；遵从 orchestrator 修正：yaml 保持 build-time-only，撤回 runtime dependency 与 lock 变更 | 本轮用户纠正；package.json 与 pnpm-lock.yaml 恢复；重新生成最终验证 |
| 2026-10-22T12:41:03+08:00 | in-progress | in-progress | 独立 review 的两个 P2 已修复并复核关闭；最终包重建/安装通过，不捏造 done | EventReviewFinal 无发现；RouteReviewFinal 两项 closed；验证 34–36 |
| 2026-10-22T12:44:43+08:00 | in-progress | in-progress | 本轮本地修复与验证闭环；完整套件保留允许报告的 bun-offline 失败，CI 待运行；不标 done | 验证 35–38；884 passed / 1 failed / 3 skipped |

创建行是原始状态快照而非可证明的 lifecycle transition。canonical `task-data.schema.json` 使用 `in-progress`，不允许 `in_progress`、`—` 或 unknown→in-progress；因此 from/to 保持合法的同阶段值，缺失前态明确写在 reason。git commit 时间不冒充 push/review 时间；历史提交行也是同阶段证据事件。沿用既有 TaskStore 全库 schema blocker，不重新跑全库来确认已知失败；本轮仅验证当前 TaskDocument，不宣称全库恢复可靠或 strict done。

## 决策

- 本次工作仅在授权 worktree/branch；不调用全局 omp、不修改 HOME 配置、不触碰其他 checkout。真实宿主只运行精确 18.11.1 且使用无凭据隔离环境。
- 需求由 PRD D8/D11/D14 与已锁定 grill 给定，未重新完整调用 grill-with-docs；沿用任务 0 领域边界。
- 历史发布证据、rc.12/rc.13 target identity、ledger 与 CHANGELOG 不重写；当前 packed compatibility.v2.json 只改 peer/dev pin，不改 schema/语义。
- 行 B B1 已完成 optionalCapabilitySkills.trellis → sbtd-task 与模板探测；保留 `trellis` capability key 和独立 CLI probe，不再把已移除 Skill 作为依赖。
- Graft skipped：无已验证受管连接；使用源码、类型检查与实际测试，不安装或改全局接线。
- 独立 review 受本次禁止 subagent 限制；主会话复核不冒充独立审查，最终需 orchestrator/人工 review。
- D8 入口审计：`createCanonicalOnboardRuntime.run` 只暴露 `check-omp-cli` 与 `install-stable-external-skills`，均为 onboard stdlib 正常路径，不应强加五依赖。需要依赖的上游 upgrade/migration/recovery/cleanup-legacy 与带 `--migration-manifest` 的 init 由用户经宿主 bash 调用；在既有 `tool_call` 边界接线，直接 migration/upgrade/recovery/cleanup/graft_deployment/reconciliation 模块调用同受检查。Python Ed25519 验签实现在 sbtd_migration.py 与 sbtd_migration_plan.py；Node p0 验证不依赖 Python cryptography。
- D8 预检绑定所选直接 Python executable，argv 为 `-I -B -c <import probe>`，timeout 30s、JSON 上限 4096 bytes；逐一 import 五个包，全部收集缺失列表。缺失、非零、killed、malformed、不可证明解释器的 shell 间接调用均拒跑；无安装、重试、成功缓存或 skipped。普通 onboard stdlib 路径仍正常运行。宿主进程 adapter 保留 `killed`，不再硬编码 false。
- D8 边界：这是可识别 SBTD Python 入口的 host guard，不是通用 shell sandbox；不声称覆盖用户自写程序、计算式 import、别名或宿主外执行。canonical 上游验签的 fail-closed 不变；不改 vendor、投影、upstream.lock、map 或 catalog。
- profileCatalog optional `trellis` 保留为兼容 key（catalog 不在本行写入范围）；其 Skill 映射为 sbtd-task，删除旧 `.trellis/workflow.md` 的 Skill readiness 前置和相应 fingerprint。现存 Trellis CLI、已存在项目 `.trellis` 的路由观测不是已删除 Skill 实体，按既有授权规则保留。
- 版本引用分类：当前源码、packed policy、dev fixtures、live-cell 默认值与当前候选 CI pin 改 18.11.1；rc.12/rc.13 published identities、ledger/evidence、历史测试 fixtures 与只遍历旧 published catalog 的 certification workflow 仍保留 17.x 历史语义，不用新 policy 重新解释旧 tarball。
- CONTRACT-CHANGE-NEEDED：无。packed compatibility.v2.json 仅更换 peer/dev pin；contract profile、ledger/schema、requiredEvidenceProfiles、四命令清单和发布授权语义均未改。
- 真实宿主 smoke 使用 Linux `/usr/bin/script` PTY：18.11.1 非交互 RPC 在没有 model 时于进入 RPC 前退出，因此用允许 no-model 的真实 interactive 启动。companion 转发全部真实注册并从宿主 getCommands/getAllTools 核对，使用真实 ExtensionContext；仅 UI 通知/确认由 harness 驱动，项目级 onboard 只批准 managed-files。不是模型 E2E 或完整事件认证。
- Code Readability Review / ponytail-review：无额外依赖、无新持久状态、无新 CLI/公共升级命令、无重试框架；沿用 process adapter、Zod、现有 host seam。仅删除已无意义的 readiness 读取，保留既有授权 seam。
- strict 状态限制：TaskDocument 已单独解析当前记录成功，但 TaskStore 全库 inspect 被其他历史记录 schema 阻断。未绕过 helper 改 active pointer 或伪称可靠恢复；task frontmatter 暂留 in-progress，完成/阻塞 transition 未通过 TaskStore 持久化。独立 review 等待 orchestrator/人工，不启动 subagent。

- D11 补充任务（strict）：安装 tarball 后由包自身 `omp.extensions` 发现的 `row-c-install-smoke.mjs` 才是 D11 gate；`row-c-smoke.mjs` 保留为 supplementary，前述第 10–11、17 条 wrapper smoke 不再作为 D11 gate 证据。需求明确，未重新完整调用 grill-with-docs；不改「使用的模型」。
- 安装入口实测：18.11.1 将裸绝对 `.tgz` 路径分类为 local directory/link，读取 `<tgz>/package.json` 导致 ENOTDIR；使用正常 npm named spec `@kunolu/omp-sbtd@file:<absolute-tarball>` 经同一 `omp plugin install` 成功。不是包 manifest/files/dist 缺陷，不修改 host 或包契约。
- 观察方案：`plugin list/doctor --json` 只证明安装/manifest；extension dashboard 的 capability 列表不枚举已注册 handlers。使用 pinned host 的 Bun loopback debugger，在 startup `formatExtensionLoadNotifications` 读取真实 loader errors 参数，在 `InteractiveMode.getUserInput` 调用帧读取 `this.session.extensionRunner.getLoadedExtensions()` 的 handlers/commands/tools Maps、`session.getAllToolInfos()`、`session.model` 与 `Bun.main`。另外真实键盘 `/tools` 验证 TUI 工具列表。不 import、wrap、proxy 插件，不改宿主源码，不注入 extension，不调用模型。
- PTY 继续适用：18.11.1 非交互 RPC 在未配置 model 时于进入 RPC 前退出；interactive 允许 no-model。真实键盘输入 `/sbtd onboard plan`、`/sbtd onboard init-projects`，仅批准 “Apply SBTD Onboard Plan” 的两个 project AGENTS targets，不替换 UI API。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 沿用任务 0 完整 grill 的领域边界；本行不新增领域术语 | before-dev | not-required |
| book-ddia-data-design | D8 跨进程预检与失败路径；不改变上游迁移数据格式或事务 | before-dev | passed（confirmed：canonical runtime 拥有迁移数据；预检在入口前、零写入、无缓存/重试；不改 schema） |
| book-legacy-change-safety | 宿主 API 升级与既有 capability readiness 改动 | before-dev | passed（characterized：45/45 既有安全网；新 readiness 与 D8 regression 先 red 后 green） |
| book-refactoring-pass | 首次既有生产代码编辑前 | before-dev | passed（proceed / normal：现有 process adapter 与 tool_call seam 足够，无需重构） |
| book-release-readiness | 宿主集成与 runtime 行为变化；本行不发布 | finish | blocked（本轮独立 review 已闭环；D11/D8 通过；全量仍有 bun-offline 前置失败、修复后事件 CI 未执行，不标 strict done/release-ready） |

本次 D11 evidence-only 补充的 Book Gate Plan：仅新增非打包 smoke 与更新本 task；DDD（无新领域歧义）、DDIA（无生产数据/所有权变更）、legacy（无生产行为修改）、refactoring（无既有生产代码编辑）均 not-required。Release readiness 沿用上表 blocked，不借新 smoke 改写全量环境失败或发布就绪状态；若需生产/打包修复则重新路由适用门禁。验证范围为真实 install/discovery/onboard、packed p0、项目 lint/typecheck；不重复运行已知 bun-offline 全量失败以确认用户事实。

本轮 Reviewy 修复 Gate：DDD not-required（无新领域边界、未完整 grill）；DDIA confirmed（host source 为事件 source of truth；任务文件只读观测，不修改 task schema/route key）；Legacy characterized（event red 5、route red 2、cwd red 2，保留严格拒绝/旧 Trellis 观测/依赖缺失拒跑）；Refactoring proceed / normal（复用既有 seam，无结构重构）；Release readiness 待本轮验证，既有 blockers 不改写为 passed。Biome 是唯一配置 LSP，不提供 TS references；使用源码调用点与 typecheck。未调用 Graft、全局 omp 或其他 checkout。

本轮契约纠正：误将现有 yaml devDependency 移至 runtime 的尝试已全部撤销，未提交；该候选的 build/pack/install 结果只保留失败过程证据，不能证明最终包。最终使用无新增依赖的严格 flat-scalar frontmatter 观测器；支持普通/单引号/JSON 双引号标量、BOM/CRLF，拒绝重复键、缺少结束分隔、未知 schema、嵌套/alias/tag/block 等不支持语法。它不是完整 YAML 或 TaskDocument 验证器，不选择任务、不写任务状态。`ai/tasks` 与 `.sbtd/tasks` 的 in-progress/checking 映射到现有兼容 route/key；index 只导航，archive/reports/symlink 不提供活动证据。`.trellis/tasks` 与 `.trellis/workflow.md` 保留只读 legacy 观测，不是 v2.0.2 前置。

Event 决策：18.11.1 `shared-events.ts` 的 session_branch reason 为 branch/fork/btw，session_switch 只有 new/resume/fork。`session-maintenance.ts:2038–2080,2485–2488` 证明 handoff 在原 Session 提交 compaction 并发 session_compact；现有 13-hook inventory 不订阅它。成功 RPC 只产生 `HANDOFF_EVENT_UNOBSERVABLE` diagnostic；拒绝/未尝试仍分别产生原有 diagnostic，不制造 event 或新增契约 hook。D8 采用 bash 显式 cwd（绝对/项目相对/~）解析 probe 目录，未指定时仍 ctx.cwd；不扩展 shell sandbox 或自动安装权限。

## 进度

- [x] 核对根、分支、clean worktree、PRD/grill/行 B B1 与当前 skeleton。
- [x] 宿主 pin/lock/API 与当前兼容性引用。
- [x] v2.0.2 capability 适配。
- [x] D8 隔离预检与拒跑测试。
- [x] 全量验证已完整执行并保留失败：848 passed / 1 failed / 3 skipped；packed p0 PASS。
- [x] 18.11.1 无凭据真实宿主加载、注册与 onboard smoke。
- [x] 实现、主会话复核、证据与 scoped commits；strict 独立 review / 全绿测试及 lifecycle transition 未完成，不伪称 done。

## 验证证据

1. 初始 `pwd && git rev-parse --show-toplevel --abbrev-ref HEAD && git status --short`：授权根/分支匹配，工作树 clean。
2. `COREPACK_HOME=$HOME/.cache/node/corepack pnpm install`：FAIL，CI 默认 frozen-lockfile 拒绝 manifest pin 与旧 lock 不一致；改用 `pnpm install --no-frozen-lockfile` 更新授权 lock。
3. TaskStore 只读 inspect：FAIL，仓内已有记录的 event schema 不兼容；独立 TaskDocument.parse 当前 skeleton：FAIL，缺 `completed_at`，且状态事件是 bullet 而不是表。只规范化本任务已知 skeleton，不改其他任务、不声称 active pointer/自动恢复可靠。
4. `pnpm install --no-frozen-lockfile` 成功（pnpm 11.17.0）；完整检查 lock diff：132 insertions / 265 deletions，唯一 importer 改动为 omp host pin，其余为 host 依赖树更新/剪枝、pnpm 解析出的 optional sherpa native patch 统一与 registry deprecation 元数据；未手工改 lock，其他 workspace importer 未改。Node 22.20.0。
5. 初始 `pnpm --filter @kunolu/omp-sbtd typecheck` PASS；既有安全网 `vitest run test/python-runtime.test.ts test/extension.test.ts test/omp-host-contract.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000`：3 files、45 passed。
6. 首轮全量 `PYTHONDONTWRITEBYTECODE=1 pnpm test`：45 files，9 failed / 828 passed / 3 skipped，301.84s；完整原生文件 `reports/unit-report-row-c-initial-20261022.txt`，同 stem 中文汇总。8 项旧 pin 测试已更新；失败名完整保留。第 9 项为 row A/B 同因 bun-offline：缺 zod 与 @oh-my-pi/pi-coding-agent cached manifest，`zod@4.1.12 failed to resolve`，不冒充 PASS。
7. readiness regression 初跑 red：缺 workflow 文件时旧表达式 `undefined !== 0` 甚至报告 ready；预期已改为任务 Skill 无项目 predicate 的 not-needed。删除旧检查后 extension 34/34 passed。D8 red：4 个入口 + cryptography-only 共 5 failed、stdlib 1 passed；实现后 11/11 passed，含真实 empty venv、PYTHONPATH 伪模块不能满足隔离 import、killed/nonzero/malformed 拒跑、无成功缓存、间接 shell 拒跑。
8. 影响子集 7 files：首轮 150 passed / 1 failed（发现 adapter 丢弃 killed）；保留 host ExecResult.killed 后 `vitest run test/dependency-preflight.test.ts test/host-event-surface.test.ts`：48 passed / 1 skipped。当前 host-event 的 1 skipped 是 env-gated live-cell，不把 parser fixtures 算 D11 真宿主。
9. `pnpm lint` PASS（98 files）；`pnpm typecheck` PASS；`PYTHONDONTWRITEBYTECODE=1 pnpm build` PASS（generated output is current）；`pnpm smoke` PASS（12 个命令/事件阶段：help/report/on/off、onboard plan/cancel/apply、skip plan/apply/recovery、session_start/reobserve）。中间 lint 格式错误已用项目 Biome 仅格式化本次改动文件，不改 vendor/generated。
10. D11 真宿主命令（于 packages/omp-sbtd）：`node scripts/p0/host-event/row-c-smoke.mjs`。绝对 binary `/workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp`，实际 `--version` 为 `omp/18.11.1`；依赖 package.json 同为 18.11.1。allowlist env 无任何 provider credential，HOME/XDG/PI_CODING_AGENT_DIR/AGENT_SKILLS_DIR 均指向新 `/tmp/row-c-omp-18.11.1-*`。
11. D11 输出（最终增强轮 scratch `/tmp/row-c-omp-18.11.1-YSmZ3n`）：`status=passed`、`model=null`、`commands=["sbtd"]`、`tools=["sbtd_workflow"]`、13 hooks、`extensionErrors=[]`；`Composite Onboard applied (agents: applied, ... skills: not-required ... mcp: not-required ...)`；实际 project/AGENTS.md 与 project/.omp/AGENTS.md 写入。批准仅 `Apply SBTD Onboard Plan`，2 managed targets。D8 同宿主真实 subprocess 对 empty venv 返回 `ISOLATED_DEPENDENCIES_UNAVAILABLE`，missingPackages 完整五项，installCommand 指向本 worktree kit/onboard/runtime/requirements.txt。原生 `reports/host-smoke-row-c-20261022.json` 与 `.console.txt`；初轮 harness 把 getter-backed ExtensionContext spread 后丢失 sessionManager，已改 Proxy 透明转发，失败未算通过。
12. packed p0：`pnpm pack --pack-destination /tmp/row-c-package-final-w2kUqK` → `tar -xzf .../kunolu-omp-sbtd-0.1.0-rc.14.tgz -C /tmp/row-c-package-final-w2kUqK` → `pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/row-c-package-final-w2kUqK/package`：exit 0，packedFileCount **471**，sourceTreeSha256 `c66992a8d60a5e78c9f04140583a20dd613142e5831576a7cf86966d648e1ea8`，sbomSha256 `6f1db49eb09af563b1195e55c321441f245fd64c5f6edb3694f904b1a57a7a30`。新增四个 dist dependency-preflight 编译文件由既有 files/SBOM 规则覆盖，不改 packaged schema。
13. 本地实现提交：`20acfc8`（host pin/lock/当前引用）与 `4bad9812bd152bf5d06ddf76f1c5bc6aeba47e5f`（readiness/D8/测试/重建 SBOM）；均显式 git add paths，无 push。验证为 developer-local / dirty / local-only，不冒充云端 CI 或已发布支持认证。
14. 最终全量（2026-10-22T11:40:02+08:00 起，302.47s）：`PYTHONDONTWRITEBYTECODE=1 pnpm test`，**46 files；848 passed / 1 failed / 3 skipped（852）**。唯一失败：`test/p0-authorized-omp-rpc-harness.test.ts` → `smoke-only: exact local OMP 18.11.1 blocks a dependency-resolved packed host before RPC without a provider`；仍在 `bun install --ignore-scripts --offline` 缺 zod/host cached manifest，未到 RPC，未出现不同的 18.11.1 失败。完整原生 `reports/unit-report-row-c-final-20261022.txt` 与同 stem 中文汇总；不截断失败名，不修 bun cache、不算 PASS。
15. BDD：traceable，沿用中文场景 + 英文 Gherkin；sbtd-control-bootstrap 新增 readiness/D8 场景，p0-conformance-release 当前候选的范围拒绝从 18 改为 17。最终全量中 D8 11/11 与 extension 34/34 PASS。Cross-repo context/API Contract：not-needed（只用已 vendored canonical 内容与安装的精确 host API）；测试 fake host 为 contract-backed，独立 D11 为真实宿主 smoke-only。rtk：skipped-for-report（原生命令保证完整 raw）。
16. Release Readiness Review：blocked。已落实超时、有界 JSON、无缓存/自动安装、拒跑先于入口；无数据格式、部署或迁移 rollout。本地 smoke 通过不等于发布支持认证；已知全量环境失败与禁止 subagent 下的独立 review 缺口不能改写为通过。主会话已完成可达交付；后续由 orchestrator/人工 review，并在具备所需离线缓存的环境复跑原样套件。普通 revert 可回滚本行源码与 lock；无真实用户环境迁移需要恢复。

17. orchestrator 独立复核（2026-10-22T11:52+08:00，tip `d3b7669`）：`HOME=/tmp/rowc-ver-home /workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp --version` → `omp/18.11.1`（shim exec bun → `node_modules/.pnpm/@oh-my-pi+pi-coding-agent@18.11.1/.../dist/cli.js`；全局 `omp --version` 仍 `omp/18.12.5`，未使用、未改动）；`node scripts/p0/host-event/row-c-smoke.mjs` exit 0，scratch `/tmp/row-c-omp-18.11.1-7kBBki`，`status=passed`、`model=null`、commands `["sbtd"]`、tools `["sbtd_workflow"]`、13 hooks、artifacts `AGENTS.md`/`.omp/AGENTS.md`；`pnpm typecheck` PASS；`pnpm lint` PASS（98 files）。注意：smoke 经 `--extension row-c-smoke-extension.mjs`（Proxy 包装并转发真实 `dist/extension.js` 的注册）加载插件，未走包 `omp.extensions` 的安装发现路径。

18. **D11 install-path gate PASS**（本次起点 `45e0278053b533a1a5b07adf3421eb8aeecfe2fd`；developer-local / dirty / local-only）。所有宿主调用均为 `/workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp`；隔离环境中 `--version` 输出精确 `omp/18.11.1`。最终运行 2026-10-22T04:08:34.368Z–04:08:46.004Z，scratch `/tmp/row-c-install-smoke-3I3R84`，exit 0。没有使用全局 omp、修改全局配置、访问其他 checkout、push、PR 操作或发布。
19. build / pack / unpack / packed p0 的实际命令（cwd `packages/omp-sbtd`）：

    ```sh
    export COREPACK_HOME=$HOME/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1
    pnpm build
    pnpm pack --pack-destination /tmp/row-c-install-smoke-fT4VDb
    mkdir /tmp/row-c-install-smoke-fT4VDb/unpacked
    tar -xzf /tmp/row-c-install-smoke-fT4VDb/kunolu-omp-sbtd-0.1.0-rc.14.tgz -C /tmp/row-c-install-smoke-fT4VDb/unpacked
    pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/row-c-install-smoke-fT4VDb/unpacked/package
    node scripts/p0/host-event/row-c-install-smoke.mjs /tmp/row-c-install-smoke-fT4VDb/kunolu-omp-sbtd-0.1.0-rc.14.tgz
    ```

    `unpacked` 目录实际由 harness `fs.mkdir` 创建（上列 mkdir 为等价复现）。build / pack / packed p0 全部 exit 0；packedFileCount **471**，sourceTreeSha256 `c66992a8d60a5e78c9f04140583a20dd613142e5831576a7cf86966d648e1ea8`，sbomSha256 `6f1db49eb09af563b1195e55c321441f245fd64c5f6edb3694f904b1a57a7a30`。包仍为 `0.1.0-rc.14`，按本任务禁止 version bump；新 smoke 不在 packed files 中。
20. 每次 smoke 新建 `/tmp/row-c-install-smoke-*`；HOME、XDG_CACHE_HOME / CONFIG_HOME / DATA_HOME / STATE_HOME / RUNTIME_DIR、PI_CODING_AGENT_DIR、AGENT_SKILLS_DIR、TMPDIR 均在该 root。宿主 env 为脚本 allowlist，不继承 provider credentials、model、NODE_OPTIONS 或全局配置；仅关闭 isolated setup wizard / splash 与三个本地 provider 自动探测。PATH 优先授权 worktree 的 `.bin`，无 `/home/box/.bun/bin`。安装允许联网，非 offline 模拟。
21. 原生安装命令由脚本在隔离 env / scratch project 下执行：

    ```text
    /workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp plugin --help
    /workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp plugin install @kunolu/omp-sbtd@file:/tmp/row-c-install-smoke-fT4VDb/kunolu-omp-sbtd-0.1.0-rc.14.tgz
    ✔ Installed @kunolu/omp-sbtd@0.1.0-rc.14
    ```

    默认 user scope，实际安装到 `$HOME/.omp/plugins/node_modules/@kunolu/omp-sbtd`，realpath 断言不是源目录 symlink。宿主 `PluginManager.install` 内部运行 `bun install --no-cache <named-spec>`；stdout 不透传 Bun 的下载日志，因此不捏造请求数。真实 package.json 保存 tarball `file:` dependency；隔离 node_modules 中 zod 为 **4.1.12**。Bun 也自动解析 broad peer `>=18 <19` 为 **18.12.6** 并写入隔离 `bun.lock`，该依赖的 CLI **未执行**；debugger 另断言运行中 `Bun.main` realpath 正是 worktree `.pnpm/@oh-my-pi+pi-coding-agent@18.11.1/.../dist/cli.js`，不是 installer peer 或全局 binary。
22. `/workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp plugin list --json`，exit 0：

    ```json
    {"npm":[{"name":"@kunolu/omp-sbtd","version":"0.1.0-rc.14","path":"/tmp/row-c-install-smoke-3I3R84/home/.omp/plugins/node_modules/@kunolu/omp-sbtd","manifest":{"extensions":["./dist/extension.js"],"version":"0.1.0-rc.14"},"enabledFeatures":null,"enabled":true}],"marketplace":[]}
    ```

    同 binary `plugin doctor --json`，exit 0：`plugins_directory=ok`（Found at `/tmp/row-c-install-smoke-3I3R84/home/.omp/plugins`）、`package_manifest=ok`（Found）、`node_modules=ok`（Found）、`plugin:@kunolu/omp-sbtd=ok`（v0.1.0-rc.14；完整 description 见 raw）。四项均 assert `ok`，未运行 doctor --fix。
23. 宿主启动参数：`/usr/bin/script --quiet --return --command '<absolute-bin> --no-session --no-tools --no-skills --no-rules --no-lsp --no-pty --no-title' /dev/null`，子进程仅额外设置 `BUN_OPTIONS=--inspect-wait=127.0.0.1:0/rowc`。没有 `--extension` / `-e` / `--hook` / `--no-extensions`；没有 observer extension 或 preload。外部 Node WebSocket 通过 Bun 原生 `Debugger.setBreakpointByUrl` / `evaluateOnCallFrame` 只读宿主对象；两个断点由已钉住 bundle 的唯一 source anchors 定位，变更会 fail closed。依据：host `main.ts` 调用 `formatExtensionLoadNotifications(extensionsResult.errors)`；`extensions/runner.ts` 的 `getLoadedExtensions` 返回真实 registry；`InteractiveMode.getUserInput` 在启动完成后进入输入循环。`plugin doctor` 检查文件/manifest，dashboard `state-manager.ts` 读 capabilities，均不枚举 runtime handlers。
24. 四项断言与 onboard 输出：

    ```text
    status=passed; model=null; extensionErrors=[]
    installed extension path=.../home/.omp/plugins/node_modules/@kunolu/omp-sbtd/dist/extension.js
    commands=["sbtd"]; tools=["sbtd_workflow"]
    hooks=["session_start","session_switch","session_branch","session_tree","before_agent_start","session.compacting","tool_call","tool_approval_resolved","tool_result","turn_start","turn_end","session_stop","credential_disabled"]
    ```

    精确 13 hooks，只统计安装包实例，不把宿主 `<inline-0>` / `<inline-1>` 内建 hooks 混入。宿主 tool metadata 的 sourceInfo.path 也须匹配安装路径。真实键盘 `/tools` 显示 `sbtd_workflow`；`/sbtd onboard plan` 输出 per-class confirmation；`/sbtd onboard init-projects` 弹出 “Apply SBTD Onboard Plan” / “2 managed AGENTS targets” / global Skills 不检查、不修改；仅此框输入 Enter。结果 `Composite Onboard applied (agents: applied, ... skills: not-required ... mcp: not-required ...)`，实际读回 `project/AGENTS.md`、`project/.omp/AGENTS.md` 含 managed sbtd 内容。最后 `/exit`，exit 0；无模型调用。
25. 失败保留与修复：裸 tgz 安装 ENOTDIR（host 把 local path 当 directory link）改用 named npm spec，未改生产包。初版脚本 `/tmp/row-c-install-smoke-16wRII` 在输入循环 ready 前输入 `/tools`，断点等待超时、exit 1；改为在唯一 `getUserInput` 入口观察。第二轮 `/tmp/row-c-install-smoke-E9n97B` 遇 Bun inspector `Object has too long reference chain (must not be longer than 1000)`、exit 1；改为 debugger 内 `JSON.stringify` 后返回字符串，外部 JSON.parse。第三轮 `/tmp/row-c-install-smoke-AyeO2W` PASS；增强记录 installer peer 和实际 Bun.main 后最终 `/tmp/row-c-install-smoke-3I3R84` PASS。最终新增长路径触发一次 Biome format error，`pnpm exec biome check --write scripts/p0/host-event/row-c-install-smoke.mjs` 修正后 `pnpm lint` PASS（99 files）。
26. 其他验证：`pnpm typecheck` PASS；`pnpm exec vitest run test/agent-plugin-manifest.test.ts test/agent-plugin-pack.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000` **2 files / 11 passed**；packed p0 PASS。Code Readability Review：单个非打包脚本、Node stdlib + 原生 WebSocket、无依赖/observer extension/生产 seam 改动；所有安装与宿主命令 bounded timeout，失败保留 result/terminal 输出并非零退出。BDD：traceable 到既有 manifest/pack 场景及 D11；不新增生产行为或 `.feature`。rtk：skipped-for-report；Mock Strategy：none；E2E Mode：smoke-only；Graft：skipped（源码证据足够）。正式本地 raw / 同 stem 中文汇总：`reports/install-smoke-validation-20261022.json` / `.md`（相对此 task 目录，ignored，未提交）；包含 install/list/doctor 全文、失败记录、验证与最终结果。未重跑已知 bun-offline 全量失败，未把局部通过写成全量/release-ready；原 TaskStore / 独立 review blockers 保留，未重复全库检查。CONTRACT-CHANGE-NEEDED：**无**。风险：debugger anchors 与 Bun inspector 绑定 18.11.1；npm peer/transitive resolution 随 registry 变化；仅验证注册与 onboard，不证明每个 hook 的运行行为或 provider/model E2E。仅新增本 smoke 与更新本 task，可按提交回滚；scratch 为隔离测试产物，无用户环境迁移。

27. Reviewy 本轮起点 `260d1213515b476043b454e5b4a4fb7f284e3848`；原 install-smoke commit 保留。event red：`pnpm exec vitest run test/omp-host-contract.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000` 为 **5 failed / 13 passed**，准确暴露三种 branch reason 拒绝、缺 reason 通过、handoff switch 通过。route 正确 red：`pnpm exec vitest run test/extension.test.ts -t '原生和 legacy' ...` 为 **2 failed / 10 passed / 34 filtered**；D8 cwd 两个真实 venv 用例 red。失败输出保留于本任务 `reports/*-review-round-20261022.txt`。最初 route fixture 的非动作提示与旧 marker fixture 缺 cwd 均已修正，未把这些 harness 失败冒充生产根因。
28. 无新增 runtime 依赖的最终影响子集（12:28:52+08:00）：`pnpm exec vitest run test/extension.test.ts test/dependency-preflight.test.ts test/omp-host-contract.test.ts test/host-event-surface.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000`：**4 files / 122 passed / 0 failed / 1 skipped**。其中 extension 54、D8 13、host-contract 18、host-event 37 passed + 1 env-gated skipped。`pnpm typecheck` PASS；`pnpm lint` PASS（99 files）；`PYTHONDONTWRITEBYTECODE=1 pnpm build` PASS（generated current）；`pnpm smoke` PASS（12 stages）。以上所有 pnpm 前均 `export COREPACK_HOME=$HOME/.cache/node/corepack`；Python 相关均设置 `PYTHONDONTWRITEBYTECODE=1`。Raw / 中文汇总：`reports/checks-review-final-20261022.txt` / `.md`。
29. 最终 `pnpm pack --pack-destination /tmp/row-c-review-final-pack-864l0_c6` → `tar -xzf /tmp/row-c-review-final-pack-864l0_c6/kunolu-omp-sbtd-0.1.0-rc.14.tgz -C /tmp/row-c-review-final-pack-864l0_c6` → `pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/row-c-review-final-pack-864l0_c6/package`：**PASS / packedFileCount 471**。sourceTreeSha256 `a5b7d1e34f5c6efb41efcfb74d0b53a8783e17b48b48dedc801c38c0ff52dd08`；sbomSha256 `9c86842fe6a8ecdba0b875d9c3a5cc8f46468b2f7ce178e257d1a7c2b07f6a3d`。packed manifest 实测 dependencies 精确 `{zod: "4.1.12"}`，yaml `2.8.2` 为 devDependency；package.json 与 pnpm-lock.yaml 已逐字节对比起点恢复，无版本 bump。
30. 最终 `node scripts/p0/host-event/row-c-install-smoke.mjs /tmp/row-c-review-final-pack-864l0_c6/kunolu-omp-sbtd-0.1.0-rc.14.tgz`：**PASS / exit 0**；唯一执行宿主 `/workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp`，`--version` 为 `omp/18.11.1`。scratch `/tmp/row-c-install-smoke-gN1odK`，无凭据隔离 HOME；包自身 omp.extensions 发现，非 wrapper/--extension；`extensionErrors=[]`、`model=null`、sbtd command、sbtd_workflow tool、13 hooks（含 session_start/tool_call）。真实 `/sbtd onboard plan` / `init-projects` 成功写入两个项目 AGENTS targets。Raw / 中文汇总：`reports/install-review-final-20261022.txt` / `.md`。
31. compiled route smoke：`node --input-type=module` 临时内存脚本加载 `dist/extension.js`，将本任务完整 canonical task.md 复制到临时 `ai/tasks/current/task.md`，通过已注册 before_agent_start 确认 `trellis-managed-task`；加入重复 status 后为 `small-direct-change`；原任务字节不变，临时目录 finally 删除。**PASS / exit 0**，`reports/route-smoke-review-final-20261022.txt` / `.md`。这是 contract-backed compiled smoke，不称真实模型 E2E。
32. 本地 live cell **env-gated / skipped**（默认全量与定点测试）；事件流修复仍以 CI frozen-tarball job 为验证。已尝试同 runner：`SPIKE_OMP_BIN=/workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp HOST_EVENT_PLUGIN_TARBALL=/tmp/row-c-review-pack-3h8d_8li/kunolu-omp-sbtd-0.1.0-rc.14.tgz HOST_EVENT_RUNS_ROOT=/tmp/row-c-review-pack-3h8d_8li/live HOST_EVENT_TARGET_VERSION=18.11.1 pnpm exec tsx scripts/p0/host-event/run-live-cell.ts` → **blocked / exit 2 / OMP_PACKAGE_IDENTITY_UNAVAILABLE**（授权 .bin shim 无可供 runner 向上识别的 host package identity）。失败发生在宿主启动前；未绕过用户 binary 限制改用 CI 的 dist/cli.js，未使用任何 provider credential。`reports/live-review-round-20261022.txt` 保留；此 setup 失败不依赖后来撤销的 yaml candidate，也不证明最终事件通过。CI run 39719390932 原失败日志已读；本轮未 push/触发 CI，不声称修复后 CI PASS。
33. 最终完整 `PYTHONDONTWRITEBYTECODE=1 pnpm test` 已按用户要求后台执行，完整 stdout/stderr 写入 `reports/unit-review-final-20261022.txt`，同 stem 中文 `.md`。**46 files：45 passed / 1 failed；883 tests：879 passed / 1 failed / 3 skipped；292.28s；exit 1**（12:29:25+08:00 开始）。唯一失败全名：`test/p0-authorized-omp-rpc-harness.test.ts > authorized OMP public-RPC harness > smoke-only: exact local OMP 18.11.1 blocks a dependency-resolved packed host before RPC without a provider`。原生错误：`--offline: no cached manifest for "zod"`、`--offline: no cached manifest for "@oh-my-pi/pi-coding-agent"`、`zod@4.1.12 failed to resolve`。仍是用户允许保留的 bun-offline harness 前置失败，未到 RPC，不修全局缓存、不降级断言。3 skipped：两个 `KPI_PROMOTION_SOURCE_ROOT` env-gated upstream 场景与一个 Host Event live cell；不计作通过。

34. 本轮原生独立 review：`EventReviewFinal` 对 event/schema/validator/observer 核对 pinned host，**无发现**；`RouteReviewFinal` 找到两项 P2（frontmatter colon 后缺分隔仍被接受；tilde cwd 丢失/误解 home 前缀）。补测试后 `pnpm exec vitest run test/extension.test.ts test/dependency-preflight.test.ts -t 'status:in-progress|bash tilde' --no-file-parallelism --maxWorkers=1 --testTimeout=30000` 为 **4 failed / 1 passed / 67 filtered**；修复 colon lookahead 与 pinned expandTilde 拼接语义后 reviewer 只读复核确认 **两项 closed / 无剩余具体问题**。中断前两名 reviewer 没有有效结果，不计作通过。所有 reviewer 未运行测试/宿主、未改文件；主会话唯一写入与验证 controller。Code Readability Review / ponytail-review：保留严格子集 reader 与现有 hook/process seam，无新 runtime dependency、无缓存/重试/额外公共接口；无需额外重构。
35. **独立 review 修正后的最终检查，取代第 28 条**：相同四文件 `pnpm exec vitest run ... --no-file-parallelism --maxWorkers=1 --testTimeout=30000` 为 **127 passed / 0 failed / 1 skipped（128）**，extension 55、D8 17、host-contract 18、host-event 37 passed + 1 skipped。`pnpm typecheck`、`pnpm lint`（99 files）、`PYTHONDONTWRITEBYTECODE=1 pnpm build`、`pnpm smoke`（12 stages）全部 PASS；compiled route smoke 重跑 PASS。Raw / 同 stem 中文汇总为 `reports/checks-review-closure-20261022.txt` / `.md`、`reports/route-smoke-review-closure-20261022.txt` / `.md`。
36. **独立 review 修正后的最终 tarball，取代第 29–30 条**：`pnpm pack --pack-destination /tmp/row-c-review-closure-pack-8etozmsc` → `tar -xzf /tmp/row-c-review-closure-pack-8etozmsc/kunolu-omp-sbtd-0.1.0-rc.14.tgz -C /tmp/row-c-review-closure-pack-8etozmsc` → `pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/row-c-review-closure-pack-8etozmsc/package` → `node scripts/p0/host-event/row-c-install-smoke.mjs /tmp/row-c-review-closure-pack-8etozmsc/kunolu-omp-sbtd-0.1.0-rc.14.tgz`：**全部 PASS / 471 packed files / host 18.11.1**。sourceTreeSha256 `6ede0ec8ba02bc6ba82d08e56a88f9b37146f4c3b82605e5373b52c18e6b2839`；sbomSha256 `2e3dbf0965a37defa3542a5ba2c7beb37cd1c42d120a405eb8868dc7d9d247ae`。scratch `/tmp/row-c-install-smoke-ytb1Bq`；extensionErrors=[]、model=null、sbtd、sbtd_workflow、13 hooks、两个项目 AGENTS onboard targets 均通过；授权 binary 与原生 install/discovery 路径不变。`reports/install-review-closure-20261022.txt` / `.md`。
37. **独立 review 修正后的最终全量，取代第 33 条**：后台 `PYTHONDONTWRITEBYTECODE=1 pnpm test` 完整输出 `reports/unit-review-closure-20261022.txt`，同 stem 中文 `.md`；**46 files：45 passed / 1 failed；888 tests：884 passed / 1 failed / 3 skipped；293.44s；exit 1**（12:39:28+08:00 开始）。唯一失败全名仍为 `test/p0-authorized-omp-rpc-harness.test.ts > authorized OMP public-RPC harness > smoke-only: exact local OMP 18.11.1 blocks a dependency-resolved packed host before RPC without a provider`；Bun offline 缺 zod / @oh-my-pi/pi-coding-agent cached manifest，未到 RPC。3 skipped 的来源同 33，完整失败原件保留。无新增产品失败，不把套件称为通过。
38. 最终 strict check/finish：BDD **traceable**（既有中文/English keywords；源码、feature、Vitest 与 pinned host source 一致）；Mock Strategy **contract-backed**，真实 install **smoke-only / none**；rtk **skipped-for-report**；Graft **skipped**。Release Readiness Review **blocked**：已闭环两项独立 review，保留 fail-closed、隔离、超时/有界输出与禁止自动安装；必须在所需离线缓存环境重跑原套件，并由 CI 验证修复后的 live event cell。无部署/数据迁移，按本轮 commit 可回滚源码/tests/docs/SBOM；隔离 smoke 不改用户配置。CONTRACT-CHANGE-NEEDED：**无**（yaml runtime 尝试已撤回，未改锁定依赖契约/route vocabulary/inventory/PRD）。没有代码 follow-up；未新增 lesson（纠正已由既有 row A 契约覆盖，过程与防回归断言保留本任务，不复制长期规则）。当前 TaskDocument 独立解析通过、模型节逐字节不变；既有 TaskStore 全库历史 schema blocker 不冒充已修复，状态仍 in-progress / completed_at null。全部报告 developer-local / dirty / local-only，未当作新提交的云端 CI 或发布认证。无 push、PR 操作、publish/tag/version bump。

39. orchestrator 独立复核（tip `b427bc4`，2026-10-22T12:48–12:55+08:00，packages/omp-sbtd，`COREPACK_HOME=$HOME/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1`）：`pnpm build` exit 0；`pnpm pack --pack-destination /tmp/rowc-orch-pack-7ppC` → `node scripts/p0/host-event/row-c-install-smoke.mjs /tmp/rowc-orch-pack-7ppC/kunolu-omp-sbtd-0.1.0-rc.14.tgz` exit 0（scratch `/tmp/row-c-install-smoke-s2sqyS`）：binary `/workspace/sbtd-plugins-row-c/packages/omp-sbtd/node_modules/.bin/omp`，`--version` `omp/18.11.1`，hostEntry `…/.pnpm/@oh-my-pi+pi-coding-agent@18.11.1/…/dist/cli.js`；`plugin install @kunolu/omp-sbtd@file:<tgz>` → `✔ Installed @kunolu/omp-sbtd@0.1.0-rc.14`；`plugin list --json` manifest `extensions ["./dist/extension.js"]`、enabled true；extension path `<isolated HOME>/.omp/plugins/node_modules/@kunolu/omp-sbtd/dist/extension.js`；`extensionErrors=[]`、`model=null`、tool `sbtd_workflow`、13 hooks（含 session_start、tool_call）、onboard artifacts `AGENTS.md`/`.omp/AGENTS.md`；`pnpm typecheck` exit 0；`pnpm lint` 99 files 无问题；全量 `pnpm test`（12:50:38 起，298.49s）：**46 files，884 passed / 1 failed / 3 skipped（888）**，唯一失败仍为 `test/p0-authorized-omp-rpc-harness.test.ts > smoke-only: exact local OMP 18.11.1 blocks a dependency-resolved packed host before RPC without a provider`（bun-offline 缓存前置，同行 A/B）。`package.json`/`pnpm-lock.yaml` 相对 `260d121` 无变化（runtime dependencies 仍仅 zod）。

## 修改文件与交付范围

- Host/打包：`packages/omp-sbtd/package.json`、根 `pnpm-lock.yaml`、`validation/p0/compatibility.v2.json`、生成的 `SBOM.spdx.json`。
- 生产源码：`src/extension.ts`、`src/onboard/dependency-preflight.ts`、`src/runtime/omp-extension-v1.ts`、`src/tool-risk/index.ts`。
- 宿主脚本：`scripts/p0/host-event/{drive.mjs,run-command-surface-cell.ts,run-live-cell.ts,validate.ts,row-c-smoke.mjs,row-c-smoke-extension.mjs}`。
- Tests：`test/{agent-plugin-manifest,agent-plugin-pack,compatibility-publication-contract,composite-onboard,extension,host-event-surface,p0-authorized-host-adapter,p0-authorized-omp-rpc-harness,p0-release-validator,python-runtime,dependency-preflight}.test.ts`。
- BDD：`features/{p0-conformance-release,sbtd-control-bootstrap}.feature`。
- CI：`.github/workflows/{omp-runtime-linux-probe,omp-section4-publish-gate}.yml`（仅本地改 pin，未运行/触发 GitHub）。
- 文档：`docs/assets/omp/omp-plugin-host-acceptance.md`、`docs/spec/omp-sbtd/backend/{build-and-release,directory-structure,security-invariants,testing}.md` 与本 task。
- 未改：README、CHANGELOG、package/plugin version、D14 transform、upstream.lock、distribution map、overlay catalog、历史 ledger/evidence；未提交 reports、`.omp-r12b-addendum.txt` 或 `ai/tasks/codex-verify/**`。无 subagent；「使用的模型」留给 orchestrator。
- 本次 D11 evidence-only 补充仅修改本 task，新增 `packages/omp-sbtd/scripts/p0/host-event/row-c-install-smoke.mjs`；其余上述历史范围均未再次修改。
- 本轮 Reviewy 修复范围另计：`src/runtime/omp-extension-v1.ts`、`src/extension.ts`；host-event `drive.mjs` / `observer.mjs` / `validate.ts`；六个 test 文件（omp-host-contract、host-event-surface、extension、dependency-preflight、report-command、review-regressions）；`sbtd-control-bootstrap.feature`；生成的 `SBOM.spdx.json`；`docs/spec/omp-sbtd/backend/testing.md`；本 task。`package.json` / `pnpm-lock.yaml` 与起点完全一致；既有 install-smoke 脚本与 commit 260d121 未改。上文“无 subagent”为历史轮次事实；本轮的独立只读 reviewer 证据见 34，不改 orchestrator-owned 模型节。

## 使用的模型

> 计数全部取自 session jsonl（orchestrator 以脚本 `/workspace/scripts/omp/runs/sess-stats.py` 统计：assistant 消息按 provider/model 计数，工具调用按 assistant `toolCall` 计数，辅助模型按 `type:model_usage` 的 `purpose` 计数）。jsonl 中 model_change 不写 `resolvedModel` 字段（记为「未写入」），只写 `resolvedModelIsFallback`。所有 omp 进程 runtime 均为全局 omp 18.12.5（编码引擎；18.11.1 只用于无凭据宿主 smoke）。时间为 +08:00。

| # | 会话 / 来源 | 用途 | provider/model | resolvedModel | resolvedModelIsFallback | 计数 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | omp 主会话 `01a161a0-41ce-70a1-875b-090fda897233`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T03-20-54-990Z_01a161a0-41ce-70a1-875b-090fda897233.jsonl`，11:20:56–11:50:45） | 行 C 首轮实现：D11 pin/lock、v2.0.2 readiness、D8 预检、wrapper smoke、证据（prompt `/workspace/scripts/omp/runs/prompt-pr-c.md`，`--tools=read,bash,grep,glob,edit,write,todo`） | openai-codex / gpt-6-astra（thinking high） | 未写入 | false | 1 user / 77 assistant / 192 toolResult；工具 192（read 94、bash 33、grep 26、edit 21、todo 9、write 7、glob 2）；model_usage 0；error 0 | subagent 0 |
| 2 | omp 主会话 `01a161bf-ae1d-7173-808e-d95e44a7f757`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T03-55-14-333Z_01a161bf-ae1d-7173-808e-d95e44a7f757.jsonl`，11:55:15–12:13:44） | tarball 安装发现 smoke（prompt `prompt-pr-c-install-smoke.md`）→ commit 260d121 | openai-codex / gpt-6-astra（high） | 未写入 | false | 1 user / 83 assistant / 105 toolResult；工具 105（read 28、eval 29、grep 21、bash 10、todo 6、edit 6、write 3、glob 2）；model_usage 0；error 0 | subagent 0 |
| 3 | astra 连通性测试 `01a161d2-a9c3-743c-a84b-7201ed682061`（`~/.omp/agent/sessions/-tmp-rowc-astra-ping/2026-10-22T04-15-58-403Z_01a161d2-a9c3-743c-a84b-7201ed682061.jsonl`，12:15:59–12:16:01） | 修复轮前 Lord 要求的连通性检查（`omp -p "Reply with exactly: PONG" --no-tools`），输出 PONG，无 403 | openai-codex / gpt-6-astra（high） | 未写入 | false | 1 user / 1 assistant；工具 0；error 0 | 结果：OK → 修复轮用 astra:high |
| 4 | omp 主会话 `01a161d2-daca-71a2-9219-89a3ec20902c`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T04-16-10-954Z_01a161d2-daca-71a2-9219-89a3ec20902c.jsonl`，12:16:12–12:46:46；12:25 被 orchestrator 中断纠正「yaml 不得进 runtime dependencies」后以 `--resume` 续跑同一会话，第二段 prompt `prompt-pr-c-review-fix-resume.md`） | Reviewy #107 修复轮：blocker 1–4、v2.0.2 路由、D8 cwd、全量验证 → commit b427bc4（prompt `prompt-pr-c-review-fix.md`） | openai-codex / gpt-6-astra（high） | 未写入 | false | 2 user / 102 assistant / 198 toolResult；工具 198（read 80、edit 25、grep 25、bash 24、eval 19、todo 11、glob 5、wait 4、write 3、task 2）；error 0 | 4 个 subagent（行 6–9）+ 辅助 model_usage（行 5） |
| 5 | 同会话 4 的辅助用量（`type:model_usage`） | purpose `job-widget`（omp 自身后台任务 widget 摘要；按 omp 配置的 smol 角色，非主会话、非 fallback） | cursor / composer-2.5（api cursor-agent） | — | — | model_usage 2 条（首条 12:34:04） | 12:34 orchestrator 旧版 guard 将其误判为主会话非 astra 并杀掉 timeout 包装进程 124836；bun 子进程 124845 未受影响继续跑完（12:47 退出）。guard 已改为只看主会话 model_change/assistant |
| 6 | subagent `EventReview`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T04-16-10-954Z_01a161d2-daca-71a2-9219-89a3ec20902c/EventReview.jsonl`，session `01a161d8-c473-764e-95c7-01508af1dc3e`，12:22:38–12:25:15） | 只读独立评审：18.11.1 session_branch/session_switch schema 与 host-event validator 修复（task 调用「Reviewing two independent fix boundaries」） | kimi-code / k3（omp 配置 task 角色分配） | 未写入 | false | 1 user / 24 assistant / 27 toolResult；工具 27（read 11、grep 9、bash 7） | 12:25 随中断被截断，结果丢失 |
| 7 | subagent `RouteReview`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T04-16-10-954Z_01a161d2-daca-71a2-9219-89a3ec20902c/RouteReview.jsonl`，session `01a161d8-da31-7362-8691-e7a4d08a612e`，12:22:44–12:25:15） | 只读独立评审：v2.0.2 task 路由 + D8 cwd（同一 task 调用） | kimi-code / k3 | 未写入 | false | 1 user / 15 assistant / 19 toolResult；工具 19（bash 15、read 4） | 同上被截断 |
| 8 | subagent `EventReviewFinal`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T04-16-10-954Z_01a161d2-daca-71a2-9219-89a3ec20902c/EventReviewFinal.jsonl`，session `01a161de-5304-7711-83d3-c21a2639f6ff`，12:28:42–12:33:56） | 续跑后重做 event 评审（task 调用「Restoring required independent review evidence」）；结论无发现 | kimi-code / k3 | 未写入 | false | 1 user / 36 assistant / 58 toolResult；工具 58（read 38、grep 9、glob 5、bash 4、web_search 2） | — |
| 9 | subagent `RouteReviewFinal`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T04-16-10-954Z_01a161d2-daca-71a2-9219-89a3ec20902c/RouteReviewFinal.jsonl`，session `01a161de-6404-7560-9438-59c88e913e47`，12:28:47–12:40:13） | 续跑后重做路由/cwd 评审；提出 2 个 P2（frontmatter 冒号、tilde cwd），主会话修复后复核关闭 | kimi-code / k3 | 未写入 | false | 1 user / 37 assistant / 35 toolResult；工具 35（read 15、grep 12、glob 4、bash 3、write 1 → `agent://Main` 回报，非文件） | — |
| 10 | orchestrator（Grok Bot，非 omp 会话，无 jsonl） | 分支/worktree、首个 docs commit c9df45d、prompt 编写、omp 启动/监控/中断纠正、独立复核（typecheck、lint、build、wrapper smoke 与 install smoke 复跑、全量测试复跑）、本节、push、CI 跟踪 | Grok Bot | — | — | 不适用（不经 omp 计数） | 不写功能代码 |

18.11.1 宿主 smoke 进程本身无 provider 凭据、`model=null`，不调用任何模型。
