# P1-06：多项目／worktree 与 Graft 隔离

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 基线、范围与澄清

- 基线为 P1-05 状态合并后的 main `20fe332d4f1acf42046203b9753e3a9201ea09d7`；分支 `p1-06-worktree-graft-isolation`。
- 本项是累计第 10 个 P1；其完整实现、review、合并、状态 PR 和分支清理结束后，必须暂停后续 P1，评估全部 findings 并等待用户确认。
- 未完整调用 `grill-with-docs`：主 PRD §9.5、A12、AC-09 已明确只调显式仓根、父目录永不 init/build/MCP、未选 sibling 零写入、逐仓独立调用后只读汇总；无新产品边界。
- 本项不执行真实 HOME、live automation、sync/update、真实迁移、cleanup/recovery、Windows 原生证明，也不把 Graft 能力扩展到父目录联邦。

## 门禁实际状态

- Legacy characterized：当前 `sbtd_graft_entry` 已有 workspace index、workspace parent、生成树链接/特殊文件、stamp/图完整性和逐请求守卫；`sbtd_graft_deployment` 已有显式 build、逐仓 MCP binding、累计部署证据。当前分支 40 项相关既有测试在 `-B` 下通过；非 `-B` 的一次失败由源树 bytecode 侧效应触发，正式验证继续使用 `-B`，不作为产品失败。
- Refactoring proceed/normal：复用现有 `resolve_project_roots`、`_project_revision`、`validate_build_scope`、`launch_bindings`、累计证据和 candidate 渲染；不新增父目录入口、联邦索引或另一套运行时。
- DDD not-required：无新业务术语或 bounded context 歧义。
- DDIA confirmed：每个已选仓根拥有各自 `graft/` 图；active host 配置只聚合明确 binding；未选 sibling/父目录不是数据源也不是写目标。重复执行按既有 candidate/累计证据幂等；失败保留逐资源结果。
- Release planned：完成真实多仓/worktree 证据、全量验证、独立 review 和合并后再判定。

## 验收切片

1. 两个显式 Git 仓根加一个未选 sibling：普通 host 接线只构建/配置前两者；父目录无 `graft`、`.graft` 或 MCP 调用，sibling 字节级不变；MCP server 的 `cwd` 和 `--root` 均精确指向各自仓根。
2. 同仓 linked worktree 处于不同 branch：两者都作为显式根独立验证并接线；每个结果保留实际 source ref/head；不跨 worktree 复制状态。
3. 父目录形状、workspace index 和未 canonical 根继续 fail-closed；不新增对父目录的 init/build/MCP。
4. Graft runtime 缺失时保持 not-available；多仓证据不把它误报成已部署。
5. Codex 与 OMP 使用同一根隔离守卫；OMP 仍不写 hooks。正式验证报告按 branch/timestamp 保留；不以 stdout 代替报告。

## 非目标与延期

- 不实现跨服务 route map、跨仓调用边、父目录 workspace 支持或 `--follow-*` 授权入口。
- 不修复既有 P2/P3 findings；不修改 ENTRYPOINT、live automation 或真实用户配置。
- 若实现证明现有代码已全部满足 AC-09，则以持久行为回归和真实隔离证据收口，不制造无谓 API。

## Review 后措辞修正

- “runtime 探测前”精确为：固定 Graft runtime 验证和任何 root-scoped probe 之前；普通只读环境检测不是 root-scoped probe。其余 P3 观察入 findings.log。
