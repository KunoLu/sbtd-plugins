# SBTD Workflow v2：部署共享根轻量存在性检查（P1-22）实施与验证

> 状态：设计已确认，实施进行中。本文只记录已执行事实；验证证据在完成前不预填。

## 1. 背景与设计缺口

P2-04 以 successor 批次（v2 manifest `cf5a4ecf…`）重做部署时，首条共享 deploy 操作（Orca 账户 home `AGENTS.md` copy-file）在 `started=True` 之前阻断，证据泛化为 `deployment resource precondition failed`。只读诊断实锤根因：

- `execute_resource`（sbtd_graft_deployment.py:411）对共享根调用 `snapshot(root)` 做**全树遍历**，只为判断根是否存在以决定 `mkdir`。
- live Orca 账户 home 含 4 个 2026-07-22 用户自建 symlink（`AGENTS.md.2026-08-26-1`／`hooks`／`plugins`／`prompts` → `~/.codex/…`），遍历遇 link 即 `ContractError: directory contains a link or special entry`。
- 与 2026-09-25 plan 扫描 OMP home 被无关 symlink 阻断（live-apply.md 第 52 行事件）同类：为轻量目的做全树扫描，被根内无关条目拒止。
- symlink 为清单外用户数据，不删除、不改动。

全仓审计：deploy／apply／cleanup／recovery 路径中 `snapshot(<根>)` 全树遍历仅此一处（`run_project_smoke` 不遍历项目根）；graft-mcp 的 `snapshot(installed_package)` 遍历的是受管安装副本，非用户根，不在本缺口内。

## 2. 续作血统设计（用户 2026-09-28 裁决路径）

修代码使 `runtime_versions()` 变化，已密封 v2 manifest 的 `tool_versions` 即 `version-conflict`；`_require_runtime_lineage`（sbtd_migration.py:684-697）拒绝零操作 apply（successor apply 恰为零操作），且 `_original_reference` 的 source_ref 漂移不可豁免（P1-22 必改 `sbtd-workflow-onboard` 目录内容）。因此「修一行直接续作 v2」不成立。采用恢复路径（advisory 认可的另一分支），全程有回执、不绕版本门：

1. **旧运行时恢复 v2 partial deploy**（已完成，见 §4）：`recovery plan a5fb7cb3`（2 步、零冲突）→ `recovery apply` → demo `AGENTS.md` 恢复暂停内容 `cb5f99ea…`、demo `graft/` 移除；回执 `5a2d6ae7…`。
2. **重 plan 可行性探针**（已完成）：恢复后以当时运行时跑 successor plan，`planned` 通过；探针 manifest 未保存、即弃（其 tool_versions 在 P1-22 合并后失效）。
3. **P1-22 修复合并**（本任务）。
4. **v3 successor 批次**（P2-04 续作，新运行时）：重新 plan→apply→deploy→smoke，各步用户显式确认；v3 仍绑定原批 `81a0c3d4…`/`9ad02916…`（绑定记录在后继 payload，原批无 successor 键，门不拒）；v2 批次标记 abandoned，证据全保留。

无需扩展 `_require_runtime_lineage`：v2 只被旧运行时消费（恢复），新运行时只消费自己密封的 v3。

## 3. 修复设计

`execute_resource` 根存在性检查改为不遍历的轻量检查：

- `_canonical(root)` 已逐组件拒绝 symlink／reparse（sbtd_migration_files.py:108-），根路径本身为 link 仍 fail-closed，保护不变。
- 新逻辑：`_lstat(_canonical(root)) is None` → `root.mkdir(parents=True, mode=0o700)`；已存在但非目录 → `_fail("unsafe-path", …)`（旧行为下文件根会在后续写入失败，提前 fail-closed 更严格，不改合法路径行为）。
- 不再对共享根做内容快照；根的「存在且为真目录」即为该处全部所需事实。目标资源的漂移核对仍由 `snapshot(target)` 与 recorded state 比对承担，不削弱。

边界：不修 planner 对 HOME 的整树扫描（2026-09-25 那类，属另一入口、已有 successor 批准绕过实例）；不改 graft-mcp 安装副本比对；不动 4 个 symlink。

## 4. 已执行事实（按时间）

- 2026-09-28T18:30:36+08:00：v2 部署部分执行后 blocked（demo 两私有 op succeeded，首条共享 op pre-started 阻断）；诊断实锤 symlink 根因；用户在「授权处理 symlink／立工具修复任务／暂停」中选择**立工具修复任务**。
- 2026-09-28T18:39:21+08:00：`recovery plan a5fb7cb352c4247c107c85efbc066784435e4f79e3eb406c82f03363fd805270`，2 步、conflicts 空、只读零写入。
- 用户明确「确认恢复」后：`recovery apply` exit 0、status `restored`、receipt `5a2d6ae76c8e1e15f1f1d8062317c3669224fc9ef265dd3d265af9fd3f5d26e9`；实测 demo `AGENTS.md`==`cb5f99ea…`、`graft/` absent、三份暂停路由 MATCH。
- 重 plan 可行性探针：successor plan exit 0、`planned`（探针 manifest 未保存即弃）。
- 运行环境保护：所有迁移／部署／恢复调用均 `PYTHONDONTWRITEBYTECODE=1`，防止 `__pycache__` 自更新再次造成源目录快照漂移。

## 5. 验证证据

- 红（pre-fix 代码，stash 定点复跑）：`test_shared_root_with_unrelated_symlink_deploys` 与 `test_full_deployment_with_symlinked_shared_root` 均 `blocked`／`deployment resource precondition failed`——与 live 失败签名一致；`test_absent_shared_root_is_created_private` 在旧代码下通过（无 symlink 时旧路径正常），符合预期。
- 绿（修复后）：`tests/test_sbtd_codex_deployment.py` 9 passed／4 subtests passed，含共享根带无关 symlink 部署成功且 symlink 原样保留、symlink 作为根／非目录根仍 fail-closed（blocked、零写入、原件不动）、缺失根创建 0700。
- 隔离端到端续作演练以组合证据替代：partial deploy→recovery→重 plan 的合法性与零 apply successor 消费由 P1-20/P1-21 既有隔离测试覆盖，真实现场恢复与重 plan 探针已在 §4 实跑通过；本任务新增行为仅为根存在性检查，由上述定点红绿覆盖，不重复搭建全链夹具。
- `ruff check` 两个改动文件：All checks passed。

- 全量（rebase 到 `2d674a2` 后，无 PYTHONPATH 正确调用）：`pytest tests/ -q -p no:cacheprovider` → **1177 passed, 8 skipped（既有平台 skip）, 815 subtests passed, 369.37s**。教训记录：相对 PYTHONPATH 会泄漏进测试子进程环境导致 `test_findings_cli_regressions` 假失败；本仓全量正确调用不设 PYTHONPATH（收集期由测试文件自举 sys.path）。

（独立审查与 PR 证据在闭环后补记。）

## 6. Review 与 findings

- 代码审查（reviewer）：**GO，零 P0/P1/P2/P3 发现**。一点范围澄清：非目录根用例在目标快照预检处先拦截，不能单独证明新增 elif 分支——该分支为纵深防御，测试已补注释说明断言的是 fail-closed 结果而非触发点（commit `fe8f526`）。
- 安全审查（security-reviewer）：**NO P0/P1 REMAINING**。逐环核实写链（_canonical 逐组件拒 link、_prepare_target_parents、提交时 _scope_root 重校验），无写范围逃逸；TOCTOU 窗口较旧代码收窄；fail-closed 完整；新测试不被 Windows CI 波及。2 条 P2 延期：P1-22-TOCTOU-ROOT-MKDIR（low）、P1-22-MKDIR-PARENTS-MODE（informational），已按 D-IMP-13 记入 `docs/archive/sbtd-workflow-v2-findings.md` record-222/223。

## 7. 任务合并与状态

任务 [PR #87](https://github.com/KunoLu/640-skills/pull/87) 于 2026-09-28 经三平台 CI（run 36419809696）全绿后合并，merge `f1b58f3c8640af06967b9f3948312c6fd5d4f281`；任务分支本地/远端已清理，main==origin/main。合并与分支清理按 `LESSON-20260928-pr-…` 分步执行（先证明 MERGED 再删分支）。独立状态 PR 登记台账与本节；P2-04 保持 blocked，v3 successor 批次重做需其自身逐步显式确认，本项完成不授权 live 部署、sync、cleanup 或删备份。
