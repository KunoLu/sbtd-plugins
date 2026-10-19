---
schema_version: 1
id: graft-pin-0.21.1
workflow_mode: strict
mode_source: user
mode_note: 用户明确选择 strict：版本 pin 是受管晋升，触碰安装工具和迁移运行时
status: "done"
branch: main
created_at: '2026-09-30T14:18:24.667787+08:00'
updated_at: "2026-09-30T20:12:10.830726+08:00"
completed_at: "2026-09-30T20:12:10.830726+08:00"
"blocked_reason": null
---
# graft pin 0.18.0 → 0.21.1

## 目标

把受管 Graft 精确 pin 从 `@nanonets/graft@0.18.0` 晋升到 `0.21.1`。这是同一守门契约换已证明的发布身份，不是裸形态，也不是需求 2 的 `--graft-bare`。

## 范围

- 先 diff 审查 `/tmp/graft-eval/package/` 相对已证明 0.18.0 的关键路径：CLI 启动、telemetry、MCP server、check、wiring stamp、package 身份。
- 仅在审查与适用 Book Gate 通过后，更新 `GRAFT_PINNED_VERSION` 及必须一起换的 tarball URL、integrity、registry gitHead、文档和测试钉死的版本串。
- 全量 pytest 期间不编辑源码。
- 测试通过后安装 0.21.1 proven 副本，在 demo 重建图并重部署接线，采集新证据链。

## 验收

- pin、tarball integrity、registry gitHead 与 npm registry `0.21.1` 发布事实一致，不使用 latest。
- 守门启动器、身份 pin、ephemeral HOME、DNT、根绑定、stamp 精确版本、`runtime-version` / `stamp-version` fail-closed 保持。
- 旧 0.18.0 stamp / MCP 条目在新 pin 下 fail-closed；demo 现有图按 foreign 处理，只通过受管重建和重部署恢复。
- 全量测试与 demo 新证据链绑定实际 SHA、worktree 和环境。
- 不执行 sync、live automation、hooks 修改、tag、cleanup、备份处置、需求 2。

## 澄清

未完整调用 grill-with-docs。可行性评估已只读完成，用户已明确授权上述步骤和排除项；没有未解领域问题需要访谈。完整 grill 后的 DDD 门因此未触发。

## Book Gate Plan

| Reviewer | 触发 | 客观谓词 | 阶段 | 状态 |
|---|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill，或领域术语/规则有歧义 | 本任务不改变“受管精确 pin / stamp 外版 fail-closed / 守门启动器”的领域规则，只替换已证明发布身份；无完整 grill | 需求稳定前 | not-needed |
| book-ddia-data-design | wiring stamp、迁移身份和已建图是持久数据 | 写明 stamp 版本所有权、foreign 图处理、重建顺序、回滚和重放；确认后才能改 pin | 设计稳定前 | confirmed |
| book-legacy-change-safety | 高回归风险的既有安装/运行时行为 | 先用现有契约测试和版本不符 fail-closed 表征保留行为；characterized 后才能改行为 | 首次行为改动前 | characterized |
| book-refactoring-pass | 既有生产代码编辑 | 确认这是常量/契约替换而不是结构调整；通过后才能实现 | 实现前 | proceed |
| book-release-readiness | 安装工具、迁移运行时和 demo 重部署 | 测试与项目验证之后、完成声明之前运行 | 验证后 | ready |

## 非目标

不改默认守门形态。不新增 `--graft-bare`。不把观察期 P3-01 标完成。不提交、不推送、不建 PR，除非用户另行授权。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-09-30T14:31:24.266586+08:00 | planned | in-progress | 关键路径审查与适用 Book Gate 已确认，开始按 registry 身份替换 pin | ai/tasks/graft-pin-0.21.1/design.md; registry 0.21.1 integrity verified; isolated 0.18.0 --version exit 0 |
| 2026-09-30T15:22:51.894448+08:00 | in-progress | blocked | 0.21.1 proven 副本已安装并隔离 build/check 通过；demo 重部署被阻断：P2-07 无 cleanup receipt，且受管 OMP writer 拒绝替换已存在且 argv 不同的 graft 条目。未手改 live MCP，也未改 demo stamp。 | /Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/redeploy-block.md |
| 2026-09-30T16:09:33.378314+08:00 | blocked | in-progress | 用户授权替换该 live MCP 绑定；恢复后把 launcher、CLI 与 demo stamp 一起切到 0.21.1 | /Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/redeploy-block.md |
| 2026-09-30T16:21:13.139820+08:00 | in-progress | checking | live 绑定、stamp 和 fence 已切到 0.21.1，launcher 握手与 fail-closed 证明已记录；OMP 进程重载未观察，不能声明完成 | /Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/redeploy-0211.md |
| 2026-09-30T20:12:10.830726+08:00 | checking | done | 当前 HEAD 全量 pytest 与 demo 0.21.1 复证通过，发布就绪为 ready | /Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/unit-report-graft-pin-head-main-2026_09_30-19_54_03.md |

## Release Readiness Review

Status: superseded。这是 16:21 提交前审查，当时不能完成。当前结论见文末「当前 HEAD 收口」。

Production path：用户本机 OMP 的 `sbtd-graft-e57e2f8eb34a0624`，以及 demo 的 wiring stamp 和 AGENTS fence。受影响的是重载 `mcp.json` 之后的 OMP 会话。

Failure modes：stamp、CLI、launcher 快照已同时切到 0.21.1。旧 launcher 对新 stamp 返回 `stamp-version`；新 launcher 对旧 CLI 返回 `runtime-version`。其余 MCP server 对象未改。受管 writer 仍对不等价既有条目返回 `ownership-conflict`，本次是授权后的外科替换。

Capacity / backpressure：不适用，单个本地 stdio server。

Observability：launcher 拒绝时写固定 stderr。没有新增告警。直接握手已看到 `graft 0.21.1` 和 6 个工具。本会话又通过宿主工具清单调用了 `graft_check_freshness`。

Rollout / rollback：`mcp.json` 以 `os.replace` 替换。回滚必须同时还原 `mcp.json.before`、`AGENTS.md.before`、`wiring-stamp.before.json` 和 `graft-before.tgz`。cleanup 未授权。

Required validation：图重建 exit 0，项目/运行时校验通过，直接握手 exit 0。2026-09-30 16:38:27 启动的 omp 2922 已读取新绑定并 spawn launcher 2941 与 cli 2972；本会话 `graft_check_freshness` 返回 `graph check: OK`。九行根 ignore 调整后的全量 pytest 已在 `umask 022` 下通过；完成声明仍 blocked：受管 writer 不能重复这次替换，源码未提交，旧 host 未授权处置。

## 本会话 host 证明

用户选择只记录证明，不标 done，状态保持 checking。

- omp 2922 在 16:38:27 启动时读取新绑定。子进程 2941 是 0.21.1 launcher，2972 是 0.21.1 `cli.js`。
- 宿主工具清单挂载 `sbtd-graft-e57e2f8eb34a0624` 的 6 个工具。
- 本会话只读调用 `graft_check_freshness`：`graft check: NO GRAPH`，无 `graft/manifest.json`，`graph check: OK — the wiring graph is in sync with the code.`
- 证据：`/Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/redeploy-0211.md`。未终止旧 host，未改 writer，未提交。

## 全量 pytest 失败分类

2026-09-30 重新跑了 `tests`，命令是 venv `python -m pytest tests -q -p no:cacheprovider --tb=line`，exit 1，720.46s。HEAD 仍是 `1b3acd07da71d7f766f680e7440c8bc21b933a60`。日志在 `/Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/pytest-r1.stdout`。

- `tests/test_workflow_contracts.py::WorkflowContractTests::test_repository_gitignore_keeps_canonical_generated_paths` 失败。契约要求根 `.gitignore` 恰好七行，工作树多了 `.chrome-devtools-mcp/` 和 `.playwright-mcp/`。这是未提交差异，HEAD 仍是七行。pin 设计没有要求改根 `.gitignore`。它不是版本断言，但让当前工作树的全量测试不能算通过，因此挡住 pin 验收。
- 同一次全量还有 3 个 `ContractError not raised`：`test_install_reference_replaces_a_directory_only_behind_a_verified_backup`、`test_private_directory_gateway_fails_closed`、`test_vault_must_exist_be_private_and_outside_projects`。取证命令先设了 `umask 077`，`mkdir(0o755)` 实际变成 `0o700`，隐私拒绝没有触发。`umask 022` 下这三个 exit 0。它们不计入 pin 失败。
- 计数：`umask 077` 全量为 4 failed、1236 passed、8 skipped。`umask 022` 只复跑了上述 3 个隐私测试。未改源码，未标 done。

## 根 .gitignore 复跑

按用户要求删除工作树根 `.gitignore` 多出的 `.chrome-devtools-mcp/` 和 `.playwright-mcp/`。`git diff -- .gitignore` 为空，已回到 HEAD 七行。

`umask 022` 下复跑 `test_repository_gitignore_keeps_canonical_generated_paths`，exit 0。日志：`/Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/pytest-gitignore.stdout`。没有重跑全量，因此不能把全量测试改记为通过。状态仍是 checking。

删除忽略行后，仓库根 `.playwright-mcp/` 变成未跟踪本地日志目录。未删除、未提交。

## 九行根 ignore 验收

用户随后明确要求保留两条 MCP 日志忽略，并同步现行契约。2026-09-30 在 `umask 022` 下全量运行 venv `python -m pytest tests -q -p no:cacheprovider --junitxml=<同 stem>.xml`，exit 0：1240 passed、8 skipped、860 subtests passed，755.43 秒。JUnit 为 2108 tests、0 failures、0 errors。原生 JUnit、stdout/stderr/exit 与同 stem 中文摘要：`/Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/unit-report-root-ignore-nine-main-2026_09_30-18_13_50.{xml,stdout,stderr,exit,md}`。

根 `.gitignore` 现为九行；`.playwright-mcp/` 已重新被忽略，未删除其本地日志。任务状态仍是 checking，不因该规则变更标 done。

## 九行契约提交

2026-09-30 已按用户授权，仅把根 ignore 九行契约提交为 `f7e3cc719f8c8c3290748b4d937a4410729e2ff2`，提交主题 `chore(repo): widen root ignore to nine lines`。提交包含 `.gitignore`、契约测试、README 双入口、现行 PRD/行为基线、版本化 automation prompt 和未发布 CHANGELOG；不含 pin 源码、`ai/` 任务目录、历史 lessons 或 MCP 本地日志。提交前九行契约测试 exit 0；提交后 `git ls-files` 确认两个 MCP 日志目录均无 tracked 文件。任务仍是 checking，pin 晋升未提交。

## Lesson 写入

2026-09-30 按用户提供的合法分隔名 `kuno` 建立本机 `.sbtd/developer`，文件为 `name=kuno\n`、regular file、0600、受 `/.sbtd` 忽略且未 tracked；没有执行 onboard 或改历史身份。写入两条长期 lesson：`LESSON-20260930-kuno-umask-sensitive-test-evidence` 与 `LESSON-20260930-kuno-contract-rerun-not-full-suite`，完整记录位于 `docs/lessons/topics/validation-scripts.md`，索引行位于 `docs/lessons/index.md`，短入口高频摘要位于 `docs/lessons.md`，均只写 `lessons:kuno` 块。索引链接按本库既有 anchor 规则复核通过；workflow contracts 全文件 exit 0。

## Lesson 提交

2026-09-30 已按用户授权，仅把三条 lesson 文件提交为 `4b705eae9e7496055a36c80b5dafdef64e890938`，主题 `docs(lessons): record umask and suite evidence`。不含 pin 源码、`.sbtd/developer`、本机 MCP 日志或 `ai/`。任务仍是 checking。

## 源码提交

2026-09-30 按用户授权分两笔提交，未标 done，未推送，未改 demo。

- pin：`05818d161cc3d936e06da4c4658c824d55c3991e`，`feat(graft): pin managed CLI to 0.21.1`。13 个文件。提交前 `tests/test_graft_runtime.py` 与 `tests/test_sbtd_graft_entry.py` exit 0，69 passed、38 subtests passed。policy SHA256 与声明值一致。
- 模板：`b9f03ef4450497c4e00c7772c86c754d8ee2cf19`，`chore(template): ignore impeccable local config`。`templates/project/.gitignore` 与 `onboard.py` 的忽略探针一起提交，避免探针和模板脱节。提交前对应契约测试 exit 0。

640-skills 工作树只剩未跟踪 `ai/`。demo `AGENTS.md` 仍未提交。任务仍是 checking。

## 当前 HEAD 收口

Release Readiness Review

Status: ready。可以声明本任务完成。不是 v2 发布就绪，不授权 push、PR、sync、tag、cleanup 或备份处置。

Production path：用户本机 OMP 的 `sbtd-graft-e57e2f8eb34a0624`，以及 demo 的 wiring stamp 和 AGENTS fence。新 OMP 会话读取的是 0.21.1 绑定。

Failure modes：当前 HEAD launcher 对旧 CLI 返回 `runtime-version`，exit 2。0.18.0 launcher 对现 stamp 返回 stamp 外版固定文案，exit 2。`pendingSignup` 仍不在允许集。其余 MCP server 名称未改。受管 writer 对不等价既有条目仍 `ownership-conflict`；本次 live 替换是已授权外科替换。

Capacity / backpressure：not-applicable，单个本地 stdio server。

Observability：拒绝写固定 stderr，无新增告警。直接握手看到 `graft 0.21.1` 和 6 个工具。进程扫描没有 0.18.0 host。

Rollout / rollback：live 绑定已切到 0.21.1。回滚必须同时还原 `mcp.json.before`、`AGENTS.md.before`、`wiring-stamp.before.json` 和 `graft-before.tgz`。cleanup 未授权。旧 prefix 保留。

Required validation：registry 身份与常量一致。`validate_runtime` / `validate_project` 通过。握手 exit 0。`umask 022` 全量 pytest exit 0：1240 passed、8 skipped、860 subtests passed，803.45 秒。JUnit 2108 tests、0 failures、0 errors。报告 `/Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/unit-report-graft-pin-head-main-2026_09_30-19_54_03.md`。复证 `/Users/lusonglin/TEMP/sbtd-v2-graft-pin-0211-evidence/revalidate-head-b9f03ef.md`。

Optional checks：demo `AGENTS.md` 未提交，用户未授权提交。独立 review 无 blocker。ponytail-review：Lean already. Ship. net: 0。

Residual risk：外科替换不可由受管 writer 重复。demo fence 未进 git。四份备份未清理。
