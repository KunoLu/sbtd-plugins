# 更新日志

`@kunolu/dsh-sbtd` 的所有重要变更记录于此。格式遵循
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，最新在前。
英文对照：[CHANGELOG.md](CHANGELOG.md)。

## [0.2.0-rc.1] - 2026-10-19

### Added（新增）

- **Graft 分析后端**（`sbtd_validate` 的 pre/post 相位）。只读查询走已接
  线的 managed launcher（默认 server 名 `sbtd-graft`），按
  `mcp__<server>__graft_*` 工具前缀探测；后端调用
  `graft_check_freshness`，并在 freshness 通过后调用
  `graft_find_code`。插件自身不 spawn、不
  init、不写 Graft 配置。所有不可用路径都返回 `status: "skipped"` 并带六
 个 reason 之一——`launcher-missing`、`version-unsupported`、
  `call-failed`、`guard-failed`、`graph-missing`、`graph-stale`——且不
 阻断插件加载。`strict` 模式下 Graft skipped 记为
  `graftEvidence: "未证明"`，绝不记为 passed。空图结果不算无影响的证明。
- **sbtd-task 只读层与 workflow_mode 分层解析。** 模式解析顺序：工具参数
  ／宿主注入的 `workflow_mode` → active-task 指针指向的 task.md 里的
  `workflow_mode`（只读）→ `default`。`sbtd_plan`、`sbtd_review`、
  `sbtd_validate` 现在返回 `workflowMode` 与 `workflowModeSource`；
  `/sbtd` status 显示两者；hooks notice 文案带模式与来源层。指针缺失、
  task.md 缺失或损坏、branch 不一致时按 `default` 处理并写明原因（branch
  不一致额外提示任务属于其他分支）——不抛错、不拒载。
- **lessons v2。** 身份文件为 `.sbtd/developer`（`name=<name>`，
  `^[a-z0-9]+$`，永不猜测；linked worktree 只读探测主 checkout；symlink
  身份来源拒绝）。record 落点解析链：已有 `docs/lessons/index.md`
  layered 库 → 已有 `docs/spec/lessons.md` 短入口 → flat
  `docs/lessons.md` 返回迁移 skip（match/read 仍可读）→ 都没有时新建
  `docs/lessons/` layered 库。旧 `.trellis` lessons 树只读，只凭
  `.trellis/lessons/index.md` 存在即识别。lesson 事件类型
  `gitnexus-mismatch` 改名为 `graft-mismatch`。
- **V4 宿主适配。** pre-step notice 以 V4 source kind `'dsh-sbtd'` 发出，
  读取侧仍识别兼容旧 kind `'plugin:dsh-sbtd'`；`runPreStep` 保留
  `startsRequestSeries`，宿主 request-series 语义在决策往返后不丢。
- **sbtd-task 手册**，同步自 `640-skills` `v2.0.2`
  （`1d82494d74f6df9bca7dccef2da409f87091883e`）：`SKILL.md` 加整个
  `references/` 树，含 `task-data.schema.json`。
- **两行 REQUIRED 宿主兼容 CI。** `dsh-host-compat.yml` 的 unit-pack 门
  现在对 `@deepseek-ai/dsh` `0.2.0-rc.2` 与 `0.2.1-rc.2` 两行跑钉版
  register smoke（两行均 REQUIRED，`workflow_dispatch`，红即停）。

### Changed（变更）

- **宿主范围。** `peerDependencies["@deepseek-ai/dsh"]` 与 `engines.dsh`
  写同一范围 `>=0.2.0-rc.2 <0.3.0-0`；devDependency 仍精确钉
  `0.2.0-rc.2`。dsh 0.2.0-rc.2 只检查 `peerDependencies`；0.2.1-rc.2 起
  由 `engines.dsh` 决定、peers 被忽略——两个字段因此必须一致。
- **`sbtd_validate` 契约字段改名：** 分析结果字段 `gitnexus` 改为
  `graft`（`AnalysisResult` 形状不变：`ok | skipped | advisory` +
  `summary` + 可选 `reason`）。不留双字段；消费方请迁到 `graft`。
- **按模式分级的强制。** `strict` 下：无计划的生产 edit 仍 ask，required
  book gate 未过仍 deny。`default`／`lite` 下：无计划 edit 仍 ask，但
  required book gate 未过降级为 inject notice、不拦截。sbtd section 文案
  改为中性静态文案，同时描述两种行为，不再是无条件强制语气。
- **规划类工具只回草稿。** `sbtd_spec`、`sbtd_tickets` 与 task-artifact
  不再写 `.trellis/**`、`.sbtd/**`、`ai/tasks/**` 或任何任务文件——只返
  回草稿。任务记录的唯一 writer 仍是 sbtd-task 的 TaskStore。
- **手册供应链。** `sync-manuals.sh` 钉到 `640-skills` `v2.0.2`
  （`1d82494d`）；MANIFEST 现在对每个同步文件记录逐文件 sha256，字节比
  对测试覆盖非 Markdown 的 `task-data.schema.json`。五本 `book-*` 手册刷
  新到同一钉。

### Removed（移除）

- **Trellis 后端**与 **GitNexus 后端**，含 `trellis-workflow` 手册。插件
  不再写 `.trellis/**` 产物；旧 `.trellis` lessons 树仍可读（见上文
  lessons v2）。

### 部署边界

- 用 `npm install` 安装本插件并搭配 `@deepseek-ai/dsh@0.2.1-rc.2` 可能
  报 `ERESOLVE`：npm 默认 peer 解析不带 `includePrerelease`，跨 patch 级
  预发布（`0.2.0-rc.2` 对 `0.2.1-rc.2`）不满足 peer 范围。pnpm 宿主兼容
  的 `0.2.0-rc.2` 与 `0.2.1-rc.2` 两行 REQUIRED 均通过。
- **支持范围保持 `>=0.2.0-rc.2 <0.3.0-0`，不退回。** 推荐经 pnpm 或 dsh
  插件管理器路径安装；使用 `@deepseek-ai/dsh@0.2.1-rc.2` 的 npm 用户可能
  需要依赖 override（如 `package.json` 的 `overrides`）才能解析 peer。
