# 更新日志

`@kunolu/omp-sbtd` 所有重要变更的完整中文对照，最新在前。
完整英文镜像：[CHANGELOG.md](CHANGELOG.md)。

## [0.2.0-rc.2] - 2026-10-23

### Breaking（破坏性变更）

- **Host Event 证据 v2。** 当前契约与证据 profile 为
  `omp-extension-v2` / `omp-host-events-v2`。证据消费者须使用 v2；
  历史 v1 ledger 记录保持只读，不重标为 v2。
- **必需的 handoff 证明。** `session_compact` 现为必需 Host Event：
  13 个必需事件加 1 个可选事件，共 14 个订阅。成功 handoff 必须由关联的
  `session_compact` 证明，且 `compactionEntry.method === "handoff"`。
  缺少 method 或窗口内存在竞争 compact 均失败；
  `HANDOFF_EVENT_UNOBSERVABLE` 恢复为硬失败。

### Changed（变更）

- 中文 README 从 `README_zh.md` 改名为 `README.zh.md`，随 npm 包发布；
  两个语言链接均钉 rc.2 release tag。

来源：[#123](https://github.com/KunoLu/sbtd-plugins/pull/123)（实现）
与 [#122](https://github.com/KunoLu/sbtd-plugins/pull/122)（契约决定）。
本条日期记录准备工作，不代表发布。

### 发布

- Annotated tag `omp-sbtd-v0.2.0-rc.2`；GitHub prerelease 发布时间 2026-10-23 20:41:17 +08:00；npm 发布时间 2026-10-23 20:44:10 +08:00；dist-tag `next` 与 `latest` 均指向 `0.2.0-rc.2`。

## [0.2.0-rc.1] - 2026-10-22

### Breaking（破坏性变更）

- 不再支持 omp 17.x；只在 18.11.1 上实测过；截至 2026-10-19 D11 锁定时，上游最新是 18.12.2
- 不带版本的安装（`omp plugin install @kunolu/omp-sbtd`）现在会取得
  0.2.0-rc.1，因为 npm dist-tag `latest` 与 `next` 均指向该版本；
  它要求 omp `>=18 <19`。omp 17.x 用户须显式钉旧的 0.1.x 版本。

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

## [0.1.0-rc.14] - 2026-09-01

### Changed（变更）

- 通过仅 workflow 的 `sync-upstream`，将嵌入 Kit 同步至 `640-skills`
  `v1.0.13`（`f8aa0d7225a26c5e00b81d2f1b05121108e63630`）。
- 更新 OMP distribution map，收录新稳定资产（ponytail、ui-ux-pro-max），
  并更新 AGENTS section map 以适配上游重命名。
- 将 `docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md` 的路径
  从 KPi 改为 sbtd-plugins 包路径。

## [0.1.0-rc.13] - 2026-08-27

扩宽 peer 范围的 RC，在云端 §4 run `33052112414` 后发布到 npm `next`。
Registry SHA-256 为
`b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185`。
状态不是 `certified`。candidate envelope 中的 tarball `61610988…f9c7`
是另一份发布前打包产物，不是 Registry 身份。

### Changed（变更）

- 对 `@oh-my-pi/pi-coding-agent` 的 peer dependency 从精确 `17.3.5`
  扩宽为 `>=17.3.5 <18`。开发依赖及 lockfile 安装的 OMP 仍精确钉
  `17.3.5`；OMP 18 仍不在范围内。
- Compatibility Policy v2（`validation/p0/compatibility.v2.json`）成为
  随包的可安装性契约，并列入 `package.json` 的 `files`。target catalog、
  ledger 和 evidence 留在仓库，不打包。移除 v1 exact-current policy 文件及语义。
- 兼容性认证（`published` / `installable` / `certified`）继续与 npm 发布
  解耦：release validator 仅从受信 profile evidence 推导整体兼容性状态，
  该状态从不授权或阻止发布。

## [0.1.0-rc.12] - 2026-08-20

Hybrid Plugin M2 包组装候选。在通过 handbook §4 隔离环境中的 exact-tarball
四命令验收后，于 2026-08-20 以 `next` dist-tag 发布到 npm；Registry tarball
SHA-256 为
`49edb4b7cab68f851359179b2c27bb53be8eff5682f16285f5caf9a351c39a33`。
peer dependency 仍精确钉 `17.3.5`，其身份保持不可变；兼容性认证状态从
`eligible` 开始，四命令结果仅保留为 Command Surface 基线。

### Added（新增）

- 根目录 `plugin.json`（Agent Plugins schema 1.0.0），包含迁移计划 §5
  的标准字段集。`plugin.json.version` 是唯一版本事实，与
  `package.json.version` 相等。
- 根目录 `skills/**`：在构建时由 `scripts/embed-agent-skills.mjs` 复制
  已认证的 portable Skill 投影（`generated-agent-plugin/skills/**`，
  Workflow Kit `4222b15`、`transformVersion=agent-plugin-p0-v1`、
  `certifiedCount=12`、digest `e97e283c…`）。副本归构建过程所有，并按
  Kit manifest 验证 digest；手改、缺失或多余目录、符号链接均使构建失败。
  `trellis-workflow` 仍由 onboard 管理；`sbtd-workflow-onboard` 和
  `trellis-channel` 仍明确不是候选，不随包分发。
- `plugin.json` 与 `skills/**` 加入 npm `files` 白名单及 SPDX SBOM 清单。

### Unchanged（不变）

- `kit/**` 仍只嵌入 `generated-omp/**` 投影；portable tree 不嵌入 `kit/**`。
- `/sbtd` 运行时语义、精确的 `@oh-my-pi/pi-coding-agent@17.3.5` peer，
  以及 Onboard/Doctor skill 来源均不变。
- 不新增 `mcp.json`，也不新增根目录 `commands/`、`hooks/`、`tools/`
  或 `runtime/`。

## [0.1.0-rc.11] - 2026-08-18

下一版 RC 候选。包含八项已确认的 RC6 findings、后续 reviewer 修复、
Workflow Kit `4222b15` 及精确钉版的 OMP `17.3.5`。

### Fixed（RC6 复核问题修复）

- **P1-01** 工具批准改为带类型的一次性 descriptor：依赖安装和 secret
  读取批准属于不同风险类别，绑定精确的 SHA-256 输入指纹，由工具结果消费，
  不可互换，也不跨越 deny、replay 或 turn 边界。
- **P1-02** 确定性任务分类器支持 EN/ZH/JA：逐行检测指令（上下文先于
  指令）、修正 `Review` 大小写处理、JA 变更意图/bug 词汇（`不具合`、
  `バグ`、`障害`、`修正してください`、`レビュー`）、ZH `问题/故障/错误`，
  并加入版本化合成回归语料。`/sbtd route` override 不变。
  NeoX 100+ 生产语料仍作为延期的 promotion evidence。
- **P1-04** BDD 交付证据不再使用 `.feature` 文件 mtime。版本感知 observer
  运行已晋级 Kit 的 `validate_validation_evidence.py`（由嵌入 manifest
  钉定 SHA），并绑定仓库 revision；v1 envelope 不能满足 BDD 场景可追溯性；
  specification 是否存在与执行证据分开报告。
- **P1-06** `release-readiness ready` 从已验证、当前、精确 revision 的
  evidence observation 及持久化 hash-bound descriptor 推导，不接受
  caller-supplied boolean。后续仓库变更会使 descriptor 失效，并将 gate
  重置为 `planned`。
- **P2-01** capability registry 决定工具阻断：安全诊断
  （read/grep/glob/lsp/ast_grep/debug/recall/web_search/todo/ask）在
  preflight-only/blocked 状态仍可用；未知工具和远端（`ssh://`）locator
  按 fail-closed 处理。
- **P2-02** 依赖变更检测覆盖 npm/pnpm/yarn/bun、pip/uv、cargo、brew、
  go、npx/bunx、dotnet、nuget、choco、winget、composer 及 PowerShell
  `Install-Package`，包括 `powershell`/`pwsh` 的 `-Command` 与
  `-CommandWithArgs` wrapper；支持 `&&`、`;`、`|`、换行，以及
  `sudo`/`corepack` 前缀。纯查询（`npm ls`、`pip show`、`go list`）不标记。
- **P2-03** secret 清单扩展至 `.envrc`、`.netrc`、`.git-credentials`、
  `.npmrc`、`.pypirc`、Docker/Kube/AWS/Azure/gcloud 凭据、
  `*.p12/pfx/keystore/jks`、usersecrets，以及重定向/git-show 读取形式。
  公共证书、`.env.example` 类模板、`appsettings.*` 和公钥属于可观测的
  mixed assets，不硬性阻断。
- **P3-01** 包元数据（repository/bugs/homepage）、SECURITY.md、本更新日志，
  以及 README 的支持、数据处理、卸载章节现随 tarball 分发。

### Changed（变更）

- 公开 OMP 目标精确钉为 `17.3.5`；`17.2.9` 为历史版本。在隔离四命令验收
  通过前，`17.3.5` 保持 `unverified`，发布仍被阻止。

### Fixed（实现后复核修复）

- 缺失 `jsonschema` 时返回 `VALIDATOR_UNAVAILABLE`（fail-closed）。
  嵌入 Skill 随包提供 `requirements.txt`。Kit lock 为 `4222b15`。
- staged promotion 复制 `SECURITY.md` 和 `CHANGELOG.md`，使 SBOM 清单
  与声明的包文件一致。

## [0.1.0-rc.10] - 2026-08-14

- 前一版 RC。Workflow Kit 后来在 0.1.0-rc.11 中从 `078267f` 重新绑定
  到 `4222b15`。

### Migration notes（迁移说明）

- 此版本之前的会话保留 `stateVersion = 1`；可选的 `validationEvidence`
  descriptor 字段为增量添加，旧 reader 会忽略它。
- 曾依赖“touch 任意 .feature 文件即可解除交付阻断”的宿主，现在必须提供
  按当前 commit 验证的 v2 evidence envelope（见 project-validation skill
  的 validation-evidence contract references）。
- 记录 `release-readiness ready` 后，后续 write/edit 会使其失效；
  推进前需重新观测当前证据。
- validator 宿主需要 `jsonschema`（从已安装的 `project-validation`
  Skill 根目录运行 `python3 -m pip install -r requirements.txt`）。

## [0.1.0-rc.6] - 2026-08-06

### Changed（变更）

- 将 OMP peer 从 rc.2 的 `17.1.3` 改为精确钉版 `17.2.9`。
- 发布包含 253 个文件的候选包，其 tarball 与归档的隔离 OMP `17.2.9`
  四命令验收记录中的 tarball 一致。
- 其他变更：已发布，变更明细不可考。

## [0.1.0-rc.2] - 2026-07-28

### Added（新增）

- 随包提供含安装与兼容指引的 README。与 rc.1 相比，已发布 tarball 仅新增
  `README.md`，仅修改 `package.json` 和 `SBOM.spdx.json`；运行时文件不变。

## [0.1.0-rc.1] - 2026-07-28

### Added（新增）

- 首次通过 npm 发布 OMP SBTD 插件，包含 `dist/extension.js`、嵌入的
  workflow Kit 和 SPDX SBOM（356 个文件）。
- peer dependency 精确钉为 `@oh-my-pi/pi-coding-agent@17.1.3`。
