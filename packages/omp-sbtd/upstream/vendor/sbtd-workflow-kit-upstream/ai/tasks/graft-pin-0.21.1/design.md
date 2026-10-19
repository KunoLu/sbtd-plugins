# graft-pin-0.21.1 设计

未完整调用 grill-with-docs。可行性评估和本轮关键路径 diff 已回答契约问题；用户已授权步骤和排除项。

## 审查事实

- 官方 tarball `https://registry.npmjs.org/@nanonets/graft/-/graft-0.21.1.tgz` sha512 integrity 与 registry 一致，且与 `/tmp/graft-eval/package/` 620 个文件字节相同。
- registry：version `0.21.1`，gitHead `375a37e0b6a21d28f12fce2d220d692726bb0730`，integrity `sha512-0CSgoGx+FyzgCkFDhM94pvPnYaTU9jL19BixqMmZ0eyQK618GINPHhQ5Xtto7LcHdNiBGl5RFQcwJob6Mxq4nA==`，bin `dist/cli.js`，engines `node >=20`。
- `package.json` 相对 0.18.0 只改 version。`dist/mcp/{tools,tool-names,server,instructions}.js`、`dist/telemetry/gate.js`、`dist/graph/check.js`、`dist/context/check.js`、`dist/claude/hooks.js`、`dist/hosts/mcp-config.js` 字节相同。
- MCP 规范工具仍是 6 个：`graft_find_code`、`graft_file_api`、`graft_check_freshness`、`graft_trace_calls`、`graft_find_all`、`graft_repo_map`。交接里的“13”与两版实际广告集合都不符，不以它为契约。
- `mcp` 仍在 `UPKEEP_SKIP`。受管启动器只跑 `mcp`，不跑 `graft init` / `graft trail`。
- CLI 差异集中在 init 输出和 `brain` → `trail`（`withLegacyNames` 仍把 `brain` 映射为 `trail`）。新 telemetry 事件只在 trail signup/pull。DNT gate 字节相同。
- `DEFAULT_WIRING_OPTS` 仍是四项 true。SBTD 继续写四项 false。
- `.graft/config.json` 新增可写键 `pendingSignup`。不加入受管允许集；出现时仍按 unmanaged key fail-closed。`brain` 键仍拒绝。
- 已证明 0.18.0 CLI 在隔离 HOME 下 `--version` 打印 `0.18.0`、exit 0，HOME 树不变。Node `v24.15.0`。

## 设计

- 只替换发布身份：`GRAFT_PINNED_VERSION`、tarball URL、integrity、gitHead，以及声明当前 pin 的文档、安装器回退文案和必须跟随常量的测试夹具。
- 不改启动器形状、DNT、stamp 精确匹配、`runtime-version` / `stamp-version` fail-closed。
- 历史 PRD 事件、已发布 CHANGELOG、P0 当时证据不改写。当前 ENTRYPOINT / README / SKILL / REFERENCE / 安装回退 / 受管资产里的“当前 pin”改为 0.21.1。
- 安装 0.21.1 到新的 TEMP proven prefix，保留 0.18.0 prefix 作回滚。demo 旧 stamp 视为 foreign，只通过受管重建和重部署恢复。
- 不执行 sync、live automation、hooks、tag、cleanup、备份处置、`--graft-bare`。不提交、不推送、不建 PR。

## DDIA Data Design Review

Status: confirmed

Data owner and source of truth: 受管 pin 的事实源是 npm registry `0.21.1` dist（integrity + gitHead），写入 `graft_runtime.py` 常量。wiring stamp 由部署器写入 `graft/.cache/wiring-stamp.json`，版本必须等于 pin。迁移 `tool_versions.graft` 在 plan 时取同一常量。图是可重建缓存，不是事实源。

Write / read / async / failure paths: 改常量不回写已有 stamp 或 live MCP。下次启动读 package.json 与 stamp，版本不符即 `runtime-version` / `stamp-version` fail-closed、零修复。新 prefix 安装成功后，demo 重部署才写新 stamp 和新绝对 CLI 路径，然后重建图。

Consistency model: pin、stamp、已安装包版本强一致。旧产物在代码 pin 改变后立即 foreign，不是最终一致。

Idempotency / ordering / retry / deduplication: 顺序固定为审查 → 改 pin → 测试 → 新 prefix 安装 → demo 重建与重部署。重复安装同一身份应幂等。旧 sealed manifest 仍记录 0.18.0，新运行时拒绝消费，不改历史回执。

Schema / migration / backfill / rollback / replay: stamp schema 不变。`pendingSignup` 不纳入允许集，出现即 unmanaged fail-closed。回滚是把 pin 与接线指回保留的 0.18.0 prefix，并按该版本重建图；不删除旧 prefix。

Observability and repair: 失败码保持 `runtime-version`、`stamp-version`、`runtime-unavailable`。证据绑定 SHA、worktree、prefix 和 registry integrity。

Required tests: pin 常量等于 registry 字面量；版本不符仍阻断；stamp 外版仍阻断；全量 pytest。

## Legacy Change Safety Review

Status: characterized

Behavior to change: 受管精确发布身份从 0.18.0 换到 0.21.1，包括 tarball URL、integrity、gitHead。

Behavior to preserve: 守门启动器、DNT、四项 false stamp、MCP 六工具、check 语义、外版 fail-closed、不自动升级、不接受 shim。

Current reproduction evidence: 隔离 HOME 下已证明 CLI `--version` 为 `0.18.0` 且不写 HOME；关键模块字节比较如上。

Safety net: 现有 `test_graft_runtime.py` 与 `test_sbtd_graft_entry.py` 契约，外加一条独立 registry 字面量断言。不新增生产 seam。

Hidden dependencies / seam: live MCP 绑定绝对 CLI 路径；demo stamp 版本精确等于旧 pin。安装不覆盖旧 prefix。

Validation plan: 红灯后改常量，再更新跟随当前 pin 的夹具和文档，然后全量 pytest。测试期间不编辑源码。

Review mode: normal

## Refactoring Review

Status: proceed

Review mode: normal

Existing-code scope: `graft_runtime.py` pin 常量及声明当前 pin 的注释、安装器回退文案、受管资产版本字段。

Behavior that must remain unchanged: 安装确认门、完整性校验、身份解析、stamp/runtime fail-closed。

Structural friction: 无。版本串散落是契约钉死，不是该抽取的新抽象。

Decision and smallest safe step: no refactor needed。只替换当前 pin 身份。

Safety net and validation: 同上。

Deferred refactors: 不把 `pendingSignup` 收成新错误码；unmanaged key 拒绝已经 fail-closed。
