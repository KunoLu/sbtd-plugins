<p align="center">
  <a href="https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.md">EN</a>
  ·
  <a href="https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.zh.md">中文</a>
</p>

# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器，提供短中文 sbtd section、hooks、九个模型工具、只读 manuals，以及人类命令 `/sbtd`。

## 环境要求

- 目标与开发宿主：`@deepseek-ai/dsh@0.2.0-rc.2`。
- `peerDependencies` 与 `engines.dsh` 均声明 `>=0.2.0-rc.2 <0.3.0-0`；本次仅文档 RC 不改变该范围。
- MCP 可选，缺失时降级。Graft 查询走已接线的 managed launcher；插件不初始化 Graft，也不写 MCP 配置。

搭配 `@deepseek-ai/dsh@0.2.1-rc.2` 时，npm 默认 peer 解析不包含跨 patch 预发布版本，可能报 `ERESOLVE`。推荐 pnpm 或 dsh 插件管理器；详见 [CHANGELOG.zh.md 的部署边界](CHANGELOG.zh.md#部署边界)。

## 安装

从 dist-tag `next` 安装。

`0.2.0-rc.2` 已于 2026-10-23 17:08:50 +08:00 发布到 npm；
`next` 与 `latest` 均指向该版本。GitHub prerelease：
[`dsh-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2)。
现有 `@next` 安装指引保持不变。

使用 `@next`，不要使用裸包名、`@latest` 或 GitHub 路径：

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

加载时 `apply()` 注册短中文 sbtd section（name `sbtd`，order 50）、hooks、下述全部九个工具与 `/sbtd`。注册不写用户文件或 `AGENTS.md`。插件不修改 `640-skills` 源仓、不执行 `trellis init`、不静默安装 app/JDK/Maestro，也不改宿主钉。

## 内嵌工作流

`apply()` 注册 `sbtd_plan`、`sbtd_review`、`sbtd_clarify`、`sbtd_spec`、`sbtd_tickets`、`sbtd_validate`、`sbtd_bdd`、`sbtd_e2e` 与 `sbtd_lessons`。

无 plan 时，生产代码 write/edit 会 ask 先调用 `sbtd_plan`；README 编辑放行。`strict` 下，适用的 required book gate 须经 `sbtd_review` 到通过态。`default`/`lite` 下，其他未通过的 book gate 只注入 notice、不拦截；完整 docs-grill 后的 DDD 在所有 workflow mode 下仍强制。缺少 workflow mode 时按 `default`，不会隐式要求 strict book 门禁。

模式解析顺序为工具参数／宿主注入 → active-task 指向的 `task.md`（只读）→ `default`。任务数据缺失、损坏或分支不匹配时降级并说明原因。`sbtd_plan`、`sbtd_review` 与 `sbtd_validate` 返回 `workflowMode`、`workflowModeSource`；`/sbtd` 与 hook notices 也显示模式及来源。

### /sbtd

人类命令（`ctx.commands`，非模型工具）：

- `/sbtd` — 只读：当前 Book Gate Plan 或 `no-plan`、workflow mode/来源与 maestro missing 摘要；不安装。
- `/sbtd plan` — 查看会话 plan；无 plan 时明确说明；不创建 plan。
- `/sbtd maestro` — 复用 T12 `preflight()`；安装指引要求先征得同意，不静默安装。

### sbtd_clarify

首次调用必须传 `mode`：`docs`（grill-with-docs）或 `generic`（grill-me）；之后省略则继承。换 mode 会抛错，直到 `reset: true`（Interview Reset）。compaction 快照还原保留 mode 与 `clarifyStatus`，不是 Reset。

每轮只问一个 `question`。`clarifyStatus=complete` 仅当 `frontier_empty` 且 `user_confirmed` 同时为真；只读 manuals 不是 Complete。Partial 可以没有 plan；Complete 必须先 `sbtd_plan`。docs Complete 加入 haystack 事实 `完整执行 grill-with-docs`，把 `ddd` 升为 required，并使用共享 `sbtd_review kind=ddd` 路径。generic Complete 不自动要求 DDD。Complete 且 required DDD 未 `confirmed` 时一次性返回 blocked，不再建议 PRD/实现；继续调用 clarify 不是恢复路径。

### sbtd_review

`kind` 仅接受五枚举：`legacy`、`refactor`、`ddd`、`ddia`、`release`。禁止别名与 skill-id。

| kind | status 枚举 | 3.4 通过态 |
|---|---|---|
| `legacy` | `characterized` `needs-safety-net` `seam-required` `blocked` | `characterized` → `passed` |
| `refactor` | `proceed` `refactor-first` `blocked` | `proceed` → `passed` |
| `ddd` | `confirmed` `needs-clarification` `blocked` | `confirmed` → `passed` |
| `ddia` | `confirmed` `needs-design-change` `blocked` | `confirmed` → `passed` |
| `release` | `ready` `needs-mitigation` `blocked` | `ready` → `passed` |

3.4 映射：`needs-*`、`seam-required` 与 `refactor-first` 保持 `running`；`blocked` → `blocked`。映射不改 `requirement`。

示例：

```js
await sbtd_review({
  kind: "legacy",
  status: "characterized",
  conclusions: "Safety net in t5-review.test.mjs",
});
```

### 其他工具

- `sbtd_plan` 建立会话 Book Gate Plan。`sbtd_spec` 与 `sbtd_tickets` 只返回草稿，不写任务文件。任务记录的所有权仍属于 sbtd-task 的 TaskStore。
- `sbtd_validate` 使用项目测试与可选 Graft 证据运行 pre/post 验证。Graft 缺失记为 `skipped`，不是 passed；strict 下该证据为未证明。空图不代表无影响。
- `sbtd_bdd` 支持 feature 发现与生成；`sbtd_e2e` 在本地前置条件与宿主提供的信任边界内支持 Web/Mobile 测试生成和执行。这些工具可写选定的 feature/test/report 文件，不静默安装缺失依赖。
- `sbtd_lessons` 匹配、读取与记录 lessons。身份来自 `.sbtd/developer`，不猜名字。写入使用 v2 分层库 `docs/lessons/{index,topics,archive}` 或已有 `docs/spec/lessons.md` 短入口，不新建短入口。旧 flat `docs/lessons.md` 与 `.trellis/lessons` 仍可读，但 record 要求迁移，不自动转换。

### 手册

`manuals/` 是从 `KunoLu/640-skills` **v2.0.2**（sourceRevision `1d82494d74f6df9bca7dccef2da409f87091883e`）只读同步的 skill 正文。每个 skill 只拷贝 `SKILL.md` 与该 skill 自己的 `references/`。不要手改 manuals 正文。

重新同步：给本地 SOURCE 目录，或省略参数让脚本 clone 到钉死 SHA。

```bash
packages/dsh-sbtd/scripts/sync-manuals.sh /path/to/640-skills
```

`manuals/MANIFEST.json` 每条记录含 `sourcePath`（640-skills 仓相对源路径）、`sha256` 与 `sourceRevision`。源缺失、SHA 不匹配、拷贝失败或 checksum 失败时退出非 0。

## 平台支持

本包未声明 `os` 或 `cpu` 限制。运行支持取决于 DSH 宿主及其 Node.js 环境，不代表平台认证。manuals 同步脚本要求 Bash。Mobile 执行还要求 `/sbtd maestro` 检查的本地 JDK/Maestro/device/app 前置条件。

## 发布 RC 版本

发布与本次 README/version bump 分开。评审与合并后，在 merge commit 上创建 annotated tag `dsh-sbtd-v0.2.0-rc.2`；打 tag 后、publish 前核验顶部两个语言链接，并创建双语 GitHub prerelease。

发布前运行包测试、lint、typecheck 与 `npm pack --dry-run`；中文镜像通过钉 release tag 的 URL 链接，且 `README.zh.md` 随 npm 包发布。在 `packages/dsh-sbtd` 下，发布操作为 `npm publish --tag next`，`latest` 保持不动。不要把 CHANGELOG 日期或本地版本 bump 当作发布证据。双语发布说明见 [CHANGELOG.md](CHANGELOG.md) 与 [CHANGELOG.zh.md](CHANGELOG.zh.md)。

## 支持

可复现问题提交至 <https://github.com/KunoLu/sbtd-plugins/issues>。请附插件/宿主版本、workflow mode 与脱敏复现步骤，不要包含凭据或私密会话内容。

## 数据处理与遥测

插件没有遥测客户端。会话 plan、gate、clarification 与 Maestro 状态保存在进程内 map，提供显式 serialize/restore 支持。注册本身不写用户文件；后续 BDD/E2E/lessons 操作可以写上述项目产物。插件只读任务文件。

可选 MCP 工具以及调用的项目测试、Playwright 或 Maestro 可能按各自配置访问外部系统。插件没有遥测不等于这些工具或 DSH 宿主保证无网络访问。

## 卸载与回滚

1. 通过安装时使用的 DSH profile/plugin 配置移除或禁用插件的 `sbtd` 条目，然后重启宿主。
2. 重启清除插件进程内状态；宿主管理的快照另行处理。保留已生成的 features、tests、reports 与 lessons，除非明确选择删除——卸载插件不会删除这些内容。
3. 回滚时通过 DSH 插件管理器恢复前一插件版本，并使用兼容宿主。旧 0.1.x 的宿主与工作流契约不同，须查阅对应 CHANGELOG，不要假定可直接降级。本次仅文档 RC 不引入数据迁移。

## 许可证

Apache-2.0。见 [LICENSE](./LICENSE)。
