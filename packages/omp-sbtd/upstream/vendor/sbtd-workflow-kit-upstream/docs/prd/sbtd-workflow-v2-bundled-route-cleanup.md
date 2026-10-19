# P1-09 Bundled 旧路由清理与模式分层

## 范围与边界

- 清理 bundled 生产模板中的有效旧路由：`Trellis`、`GitNexus`、`$trellis-check`、Channel preflight 和 `.trellis/spec`。
- 将 book-* 与 BDD 的无条件 Mandatory/hard-rule 句子改为模式分层：strict 强制；default/lite 按风险、项目规则或明确交付按需调用。完整 grill 后的 DDD 复核保持共同例外。
- `onboard.py` 的 retired `zoom-out` 推荐改走当前 repo exploration/codebase-design/refactoring 路由。
- 保留迁移器、REFERENCE/SKILL 否定句、CHANGELOG/README/ENTRYPOINT 历史区、lessons identity-migration reference 和 external stable mirror 的允许旧词；ENTRYPOINT/README/CHANGELOG 的当前发布文案归 P1-10/P1-11。

## 门禁状态

- 未完整调用 `grill-with-docs`：范围由 scout 精确盘点和主 PRD §12/§13、D-08/D-13/D-15/D-22 固定。
- Legacy Change Safety Review: characterized；179 项 workflow/install/external/caveman/Ponytail 基线通过。
- Refactoring Review: proceed；只做措辞/路由清理，不改运行逻辑。
- DDD: not-required；无新领域语义。
- DDIA: not-required；不改持久/共享数据或恢复。
- BDD: skipped（本配置源仓不新增 `.feature`）；用户可见模板行为由 workflow contract 测试固化。
- Release Readiness: planned；这是发布模板路径变更。

## 验证计划与结果

- 新增 `test_bundled_templates_do_not_route_to_retired_workflows`：`templates/**` 除 `lessons-record/references/identity-migration.md` 外零旧路由匹配，非 UTF-8 资产 fail-skip 不误判。
- 新增 `test_bundled_method_gates_are_layered_by_mode`：book-* 使用 `Strict Development Gate` 且声明 default/lite；BDD 无无条件 default hard rule。
- 新增 `test_removed_zoom_out_recommendation_uses_current_route`：retired skill 提示不含 GitNexus。
- 既有 `test_other_book_skills_have_mandatory_development_gates` 改为 strict 标题断言，同时保留原 reviewer 输出 schema/触发短语。
- 定点：workflow contracts + external skills + installer 107 tests / 36.467s / OK。
- 未改 catalog（已是 14 bundled/19 external）、external stable mirror、迁移输入或历史文档。

## 复审与最终结果

- 首轮独立 review 无 P0/P1；P2-1（BDD backfill 分层歧义）与 P2-3（GitNexus/Channel 变体扫描缺口）已修复并复核。P2-2 保留泛化否定句，精确 legacy 路径由 `identity-migration.md` 承载。
- 定点：107 tests / 36.818s / OK；宽变体扫描仅命中允许 reference。
- 最终全量：988 tests / 298.753s / OK（1 项 Windows ACL 既有 skip）。
- `rtk`: used；未生成 runner 原生报告，报告 gate not-needed。
