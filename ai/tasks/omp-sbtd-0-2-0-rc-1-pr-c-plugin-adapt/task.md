---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-22 指示执行行 C（插件适配 sbtd v2.0.2 + omp 18）
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-c-plugin-adapt
created_at: '2026-10-22T11:18:35+08:00'
updated_at: '2026-10-22T11:47:47+08:00'
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

原 skeleton 的创建事实（不是可证明的 planned→in-progress transition）：2026-10-22T11:18:35+08:00 创建记录时 status 已为 in-progress；worktree 基于 origin/main `02d93ccc9f263b0733d41ef86fab1496aba28977`；首 commit `c9df45d` 已回填行 B #106、merge SHA 与 2026-10-20T04:14:20+08:00。原文未记录前态，本次不补造。TaskStore 全库校验受阻，因此本次未持久化 lifecycle transition；当前会话的 strict 完成状态见 Book Gate Plan。

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

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 沿用任务 0 完整 grill 的领域边界；本行不新增领域术语 | before-dev | not-required |
| book-ddia-data-design | D8 跨进程预检与失败路径；不改变上游迁移数据格式或事务 | before-dev | passed（confirmed：canonical runtime 拥有迁移数据；预检在入口前、零写入、无缓存/重试；不改 schema） |
| book-legacy-change-safety | 宿主 API 升级与既有 capability readiness 改动 | before-dev | passed（characterized：45/45 既有安全网；新 readiness 与 D8 regression 先 red 后 green） |
| book-refactoring-pass | 首次既有生产代码编辑前 | before-dev | passed（proceed / normal：现有 process adapter 与 tool_call seam 足够，无需重构） |
| book-release-readiness | 宿主集成与 runtime 行为变化；本行不发布 | finish | blocked（D11/D8 已通过；全量仍有既有 bun-offline 前置失败，独立 review 未执行，不标 strict done/release-ready） |

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

## 修改文件与交付范围

- Host/打包：`packages/omp-sbtd/package.json`、根 `pnpm-lock.yaml`、`validation/p0/compatibility.v2.json`、生成的 `SBOM.spdx.json`。
- 生产源码：`src/extension.ts`、`src/onboard/dependency-preflight.ts`、`src/runtime/omp-extension-v1.ts`、`src/tool-risk/index.ts`。
- 宿主脚本：`scripts/p0/host-event/{drive.mjs,run-command-surface-cell.ts,run-live-cell.ts,validate.ts,row-c-smoke.mjs,row-c-smoke-extension.mjs}`。
- Tests：`test/{agent-plugin-manifest,agent-plugin-pack,compatibility-publication-contract,composite-onboard,extension,host-event-surface,p0-authorized-host-adapter,p0-authorized-omp-rpc-harness,p0-release-validator,python-runtime,dependency-preflight}.test.ts`。
- BDD：`features/{p0-conformance-release,sbtd-control-bootstrap}.feature`。
- CI：`.github/workflows/{omp-runtime-linux-probe,omp-section4-publish-gate}.yml`（仅本地改 pin，未运行/触发 GitHub）。
- 文档：`docs/assets/omp/omp-plugin-host-acceptance.md`、`docs/spec/omp-sbtd/backend/{build-and-release,directory-structure,security-invariants,testing}.md` 与本 task。
- 未改：README、CHANGELOG、package/plugin version、D14 transform、upstream.lock、distribution map、overlay catalog、历史 ledger/evidence；未提交 reports、`.omp-r12b-addendum.txt` 或 `ai/tasks/codex-verify/**`。无 subagent；「使用的模型」留给 orchestrator。

## 使用的模型

| 会话 | 用途 | provider/model | resolvedModel | resolvedModelIsFallback | 计数 | subagent |
|---|---|---|---|---|---|---|
| omp 主会话 `01a161a0-41ce-70a1-875b-090fda897233`（`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-c--/2026-10-22T03-20-54-990Z_01a161a0-41ce-70a1-875b-090fda897233.jsonl`；runtime 18.12.5，2026-10-22T11:20:56–11:50:45+08:00） | 行 C 全部实现、测试、smoke、task 证据（prompt `/workspace/scripts/omp/runs/prompt-pr-c.md`，`--model openai-codex/gpt-6-astra:high --auto-approve --tools=read,bash,grep,glob,edit,write,todo`） | `openai-codex/gpt-6-astra`（thinking high） | jsonl 未写 `resolvedModel` 字段；model_change 1 条 `openai-codex/gpt-6-astra`，77 条 assistant 消息全部 provider `openai-codex` / model `gpt-6-astra` | false | 1 user / 77 assistant / 192 toolResult；工具 192 次（read 94、bash 33、grep 26、edit 21、todo 9、write 7、glob 2）；`stopReason:error` 0；无 403 | 无（会话目录内 0 个 subagent jsonl；`task` 工具未启用） |
| orchestrator（Grok Bot） | 分支/worktree、首个 docs commit、prompt、监控、独立复核（typecheck/lint/18.11.1 smoke 复跑）、本节与 push | — | — | — | — | — |

18.11.1 宿主 smoke 进程本身无 provider 凭据、`model=null`，不调用任何模型。
