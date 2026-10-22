# 更新日志

`@kunolu/omp-sbtd` 本次重要变更的中文对照，最新在前。
英文对照及旧版历史：[CHANGELOG.md](CHANGELOG.md)。

## [Unreleased]

### Breaking（破坏性变更）

- 不再支持 omp 17.x；只在 18.11.1 上实测过；截至 2026-10-19 D11 锁定时，上游最新是 18.12.2

### Added（新增）

- **扩展 onboard runtime 随包内容。** 收录全部 33 个上游 Python 脚本、
  9 个 runtime assets、`onboard-contracts.schema.json`、
  `upgrade.schema.json`，以及 `sbtd-task` 模板树（八个模板文件，另含 LICENSE、NOTICE）。
- **Python 依赖预检。** 随包提供 `kit/onboard/runtime/requirements.txt`，
  含 5 个钉版依赖：`jsonschema`、`PyYAML`、`markdown-it-py`、`tomlkit`
  和 `cryptography`。对可识别且需要依赖的 SBTD Python 命令（含 upgrade
  与 migration），执行前进行隔离检查；缺任一依赖即 fail-closed 拒跑，
  验签缺 `cryptography` 也拒跑。不自动安装，不降级为 skipped。
  仅用标准库的 onboard 命令仍可用；此宿主 guard 不是通用 shell sandbox。
- **安装路径宿主 smoke。** 已在 omp `18.11.1` 上验证打包插件的安装、
  经 `omp.extensions` 发现、真实命令/工具/hook 注册及项目 onboard。
  这是 smoke 证据，不是模型端到端测试或完整宿主事件认证。

### Changed（变更）

- **Kit 归属。** 同步、投影与生成迁入 `packages/omp-sbtd/scripts/` 和
  `packages/omp-sbtd/upstream/`，随后删除私有 workspace 包
  `packages/sbtd-workflow-kit`。供应链 `sourceId` 保持
  `sbtd-workflow-kit-upstream`。
- **上游同步。** 升至 `640-skills` `v2.0.2`
  （`1d82494d74f6df9bca7dccef2da409f87091883e`），
  `transformVersion` 为 `p0-v4`。两个嵌入 AGENTS 模板统一到该 revision，
  third-party notices 已重新生成。
- **Canonical runtime 投影。** `PROJECTION_FORBIDDEN_TOKEN` 豁免从
  `onboard.py` 扩展到 canonical onboard runtime 的 Python 脚本、assets
  与两个 schema。内容仍以 digest 绑定 canonical manifest；overlay
  不能借该豁免引入非 canonical 内容。
- **Portable Skill 候选。** 移除上游已删除的 `trellis-workflow` 候选；
  缺失候选仍 fail-closed。
- **Onboard Skill catalog。** 用 `skill:sbtd-task` 替换
  `skill:trellis-workflow` 与 `skill:trellis-channel`。
- **omp 18 宿主契约。** peer 范围为 `>=18 <19`，开发依赖精确钉
  `18.11.1`。事件 schema 接受 `session_branch` 的 `branch`、`fork`、
  `btw` reason，以及 `session_switch` 的 `new`、`resume`、`fork` reason。
- **v2.0.2 任务路由。** optional `trellis` capability 现映射到
  `sbtd-task`，Skill readiness 不再要求 `.trellis/workflow.md`。
  只读任务观测识别 `ai/tasks/**` 与 `.sbtd/tasks/**` 下状态为
  `in-progress` 或 `checking` 的记录；旧 `.trellis` 观测保持只读。
  任务状态仍由 sbtd-task 写入。

### Known limitations（已知限制）

- **omp 18.x 的 handoff 证据。** handoff 无法作为 `session_switch`
  观测；p0 host-event live cell 暂将 `HANDOFF_EVENT_UNOBSERVABLE`
  记为 diagnostic，而非硬失败。已登记后续：先更新 PRD，再以独立代码 PR
  实现 `session_compact` 观测；该代码 PR 合并后，恢复对缺失 handoff
  证据的硬失败。
