# P1-20 Manifest-scoped recovery plan／receipt 与恢复执行

## 范围与边界

- 交付 `recovery --phase plan` 与 `recovery --phase apply`：manifest 范围内按 cleanup→deploy→apply 逆序恢复受管资源，支持显式 receipt 续作。
- plan 只读：读取明确传入的 manifest/apply/deployment/cleanup 证据，输出 sealed recovery plan；不写项目、HOME 或证据目录。
- apply 需要 `--confirm-recovery == plan_id`；每步执行前复验 expected_current，先保护当前内容，再恢复 `restore_to`，原子保存累计 recovery receipt。
- 不安装旧工具、不恢复 Git 历史/业务数据/npm 包、不删除备份、不实现 runtime readiness 验证；`runtime_readiness` 固定 `not-verified`。
- 不改真实 HOME、真实项目、sync/live automation、Windows 原生路径。

## 门禁状态

- 未完整调用 `grill-with-docs`：需求由主 PRD §10.2.3、§14.5、D-37、F-16/F-18/F-28 固定。
- Legacy Change Safety Review: characterized；335 项 migration/contract/CLI 基线通过，recovery 当前无 live runtime。
- Refactoring Review: planned；新增 `sbtd_recovery.py`，仅把 `onboard_arguments.py` 的 recovery parser 抽成共享 helper 供 live CLI 复用。
- DDD: not-required。
- DDIA Data Design Review: planned；plan/receipt 均为不可变私有文档，receipt 为累计事实，protection_ref 只保全恢复前当前态。
- BDD: skipped（本配置源仓不新增 `.feature`）；CLI 行为由 unittest 与原生 smoke 固化。
- Release Readiness: planned。

## 设计契约

1. plan 的 resources 覆盖选中资源闭包；shared dependents 不完整时 blocked，不静默缩小范围。
2. 每个 before≠after 的已证明阶段生成一个逆向 step；expected_current/restore_to/backup_ref 直接绑定阶段结果，同资源步骤形成连续状态链。
3. apply 初次 previous_receipt_id 为 null；重试只保留已完成且后态未变步骤，续作 pending 步骤；任何 unknown/partial write blocked。
4. protection_ref 保存恢复前当前态；restore_to 为 absent 才调用安全 remove，非 absent 用 checksum-bound install。
5. receipt 保存失败返回 failed/5；bindings/chronology/cumulative 校验先于保存。

## 验证计划

- 红测覆盖 parser、plan blocked/closed closure、完整恢复、漂移拒绝、partial 续作、already-complete、保存失败和 CLI envelope。
- 定点 migration/cleanup/contracts/arguments/CLI + 新 recovery 套件，最终全量 unittest、Ruff、独立 review。

## 复审调整记录

- `apply` 的 recovery plan 必须与 manifest 位于同一授权私有目录；receipt 与 `protection/` 只写该目录。
- `_validate_context` 复核整个 manifest 批次（含未选中项目）；这是 fail-closed 的严格口径，选中子集恢复也会受未选项目漂移阻断。
- 同相位步骤按 `gitignore` 类资源优先、再按目标路径排序，确保必要 ignore 先于内容恢复；相位顺序仍固定 cleanup→deploy→apply。
- plan 期漂移与 unknown write 生成 blocked plan；apply 期单步漂移诚实记录 failed receipt/exit 5，因为前序资源可能已按非事务边界恢复。
- rejection/save-failure envelope 均经 `write_json_response` 校验；`runtime_versions()` 已纳入 `scripts/sbtd_recovery.py`。
- shared cleanup 运行时 fixture 仍缺 byte-exact pinned legacy Skill 内容，shared closure 聚合/报告层覆盖按 D-IMP-13 deferred；contracts 层闭包绑定和 `_groups` 单次执行保持 fail-closed。

## 验证与审查结果

- 实现：新增 `sbtd_recovery.py`，共享 `add_recovery_parser`/`validate_recovery_args`，live CLI 注册 recovery plan/apply；`runtime_versions()` 纳入 recovery runtime。
- 测试：`tests/test_sbtd_migration_cleanup.py` 15 项覆盖 plan、漂移、unknown write、projects_root 越界、完整恢复、partial/already-complete、protection 保全、保存失败、CLI dispatch/rejection envelope；`tests/test_onboard_migration_cli.py` 覆盖 recovery help。
- 定点：recovery/cleanup/arguments/contracts/CLI 344 tests / 13.969s / OK。
- 最终全量：`python -B -m unittest discover -s tests -p 'test_*.py'`，980 tests / 224.892s / OK（6 项既有 skip）。
- 原生 CLI smoke：plan/0；缺 confirm blocked/2 且单 JSON；confirm 后 restored/0，`.trellis` 实际恢复。
- 静态检查：`sbtd_recovery.py`、`onboard_arguments.py`、recovery 测试 Ruff 与 format 通过；`test_onboard_migration_cli.py` 保留 3 项既有 subprocess 诊断。
- 独立 review：两轮均 NO P0/P1；rejection envelope、plan 漂移/unknown write、ignore ordering、plan 目录绑定均已修复并补测；protection retry 复核通过。shared closure fixture 覆盖不足记录为 deferred P2：`P1-20-R1-SHARED-001`。
- 未执行真实迁移、工具安装、sync/live automation、Windows 原生操作、runtime readiness 验证或备份销毁。
