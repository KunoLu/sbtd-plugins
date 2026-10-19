# P1-10 ENTRYPOINT 监控与可恢复 sync source

## 范围与边界

- `ENTRYPOINT.md` 的主流程改为 `Codex / OMP + sbtd-task + Graft + Chrome DevTools MCP + Playwright + Maestro`。
- 版本监控表移除 Trellis/GitNexus 当前监控，新增固定 `Graft v0.18.0`；版本汇总记录 `sbtd-task=bundled`、`Graft=v0.18.0`。
- 工作流图、工具表、mattpocock 编排和当前使用要点改走 sbtd-task 三模式与固定 Graft/源码-LSP-contract 边界；`update` 仍是版本写回，不变成迁移、sync 或 live automation。
- README.md/html、automation prompt、CHANGELOG 同步归 P1-11；不执行 `update`、sync、live automation 或真实迁移。

## 门禁状态

- 未完整调用 `grill-with-docs`：范围由主 PRD §14 P1-10、AC-15/16、D-34 固定。
- Legacy Change Safety Review: characterized；`tests.test_workflow_contracts` 基线通过。
- Refactoring Review: proceed；仅文档基线更新。
- DDD/DDIA: not-required；不改领域或持久数据。
- BDD: skipped（本配置源仓不新增 `.feature`）。
- Release Readiness: planned；版本基线影响发布文档。

## 验证计划与结果

- 新增 `test_entrypoint_tracks_current_workflow_and_graft_monitoring`：断言新主流程、Graft 监控行、版本汇总、sbtd-task/Graft 使用章节存在，且 Trellis/GitNexus 不再作为当前监控或使用章节。
- `tests.test_workflow_contracts`：44 tests / 1.091s / OK。
- 未改 `UPDATE.md`、archive、live automation、版本写回或本机实际生效路径。

## 复审与最终结果

- 首轮独立 review 发现编辑误删 `tdd` / `writing-great-skills` 行和高风险流 `tdd` / `Codex implementation` 步骤（P1）；已全部恢复。ponytail 步骤、§2.1 与 2.2 空行也恢复，测试补防回归。
- 复审 NO P0/P1/P2；automation prompt 的 Trellis 规则与 Graft 监控收口仍归 P1-11。
- 定点：`tests.test_workflow_contracts` 44 tests / 1.069s / OK。
- 最终全量：989 tests / 235.806s / OK（1 项 Windows ACL 既有 skip）。
- `rtk`: used；未生成 runner 原生报告，报告 gate not-needed。
