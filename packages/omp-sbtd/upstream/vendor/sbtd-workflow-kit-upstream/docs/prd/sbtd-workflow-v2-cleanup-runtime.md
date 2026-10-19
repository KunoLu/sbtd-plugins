# P1-13 受管旧资源退役与 cleanup 证据消费

## 范围与边界

- 交付 `migration --phase cleanup`：读取 manifest、apply receipt、deployment evidence、verification，可选累计 cleanup receipt；`--confirm-cleanup` 必须等于当前 `verification_id`。
- 执行范围只取 manifest 的 cleanup 操作与 verification 候选闭集；每个资源执行前复验当前状态，shared 资源只执行一次，结果写入累计 cleanup receipt。
- cleanup 永不删除备份、候选、manifest、apply/deployment/verification 证据或 retained assets；失败/阻断保留现场并返回统一 envelope。
- 不实现 recovery（P1-20）、安装器转发（P1-07/P1-08）、真实项目迁移或备份销毁。

## 门禁状态

- 未完整调用 `grill-with-docs`：需求边界由主 PRD §10.2.1、§14.5、F-08/F-18/F-28 固定。
- Legacy Change Safety Review: characterized；41 项 migration CLI/contract/apply/verify 基线通过，cleanup 当前明确 `unsupported-phase`。
- Refactoring Review: planned；仅在需要参数化既有 apply 执行器时做最小行为保持调整，优先新增 cleanup 私有执行器。
- DDD: not-required；无新统一语言。
- DDIA Data Design Review: planned；source of truth 为 manifest + 阶段收据 + verification，cleanup receipt 为最新累计事实，backup_root 不归 cleanup 所有。
- BDD: skipped（本配置源仓不新增 `.feature`）；可观察 CLI 行为用 unittest 与原生 smoke 固化。
- Release Readiness: planned；最终验证后执行。

## 设计契约

1. `cleanup_migration(...)` 先私域读取全部输入，raw bytes 与 ID 绑定经 `validate_declared_bindings`；confirm 缺失或过期直接 blocked。
2. `_validate_context`、源码备份、阶段备份和 retained assets 复验通过后，才允许任何删除；候选当前状态与 verification 记录不一致时 fail-closed。
3. 资源结果沿用 `resource_result`；cleanup 不创建新原件备份，`backup_ref` 继承最近可证明阶段/前次 cleanup 记录。
4. 每次正常成功或可处理失败都原子保存新的累计 receipt；不重写旧 receipt。重试只跳过已成功且后态未变资源。
5. 状态聚合为 `failed > blocked > cleaned/already-complete`；首次成功为 `cleaned`，携带可信成功记录且后态未变的重试为 `already-complete`。

## 验证计划

- 先写红测覆盖确认、完整清理、幂等重试、漂移拒绝、partial 续作、receipt 保存失败和 CLI 接线。
- 定点运行新增 cleanup 测试，再跑 migration apply/verify/contracts/CLI 影响范围，最后全量 unittest、Ruff、独立 review。
- 不触碰真实 HOME、真实项目迁移、sync/live automation、Windows 原生路径或备份销毁。

## 实施与验证结果

- 实现：`cleanup_migration` 接入 `run_migration` 与顶层 parser；四文档/可选 receipt 私域绑定，confirm_cleanup 当前确认；执行前复验 context、source/stage backups、retained assets 和 verification candidates；按资源生成累计 cleanup receipt 并原子保存。
- 测试：新增 `tests/test_sbtd_migration_cleanup.py` 11 项，覆盖确认缺失/过期、完整清理、候选或 retained 漂移、成功后 already-complete、失败续作、双项目失败隔离、receipt 保存失败和 CLI envelope；`tests/test_onboard_migration_cli.py` 增加 cleanup phase 暴露。
- 定点：cleanup/apply/verify/CLI/arguments/contracts 335 tests / 11.911s / OK。
- 最终全量：`python -B -m unittest discover -s tests -p 'test_*.py'`，964 tests / 248.312s / OK（6 项既有 skip）。
- 原生 CLI smoke：缺 confirmation 返回单一 blocked JSON/2；带当前 verification_id 返回 cleaned/0，`.trellis` 实际删除。
- 静态检查：`sbtd_migration_verify.py`、cleanup/CLI 测试 Ruff 通过；`sbtd_migration.py` 保留 main 基线相同 7 项既有诊断；`test_onboard_migration_cli.py` 保留 3 项既有 subprocess 诊断。
- 独立 review：两轮均 `NO P0/P1 REMAINING`；首轮 global_error 项目状态污染、reason 文案和可移植路径均已修复。shared cleanup 运行时覆盖按 D-IMP-13 记录为 deferred P2：`P1-13-R1-SHARED-001`。
- 未执行真实迁移、recovery、安装器转发、sync/live automation、Windows 原生操作或备份销毁。
