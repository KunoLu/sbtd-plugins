# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器。当前为 T6：注册短中文 sbtd section、进程内会话状态、`sbtd_plan`、`sbtd_review`、`sbtd_clarify`、`tools/pre-execute` / `agent/pre-step` hooks 门禁，以及从 640-skills 只读同步的 `manuals/`。

版本 **0.1.0-rc.1**，发布在 dist-tag `next`。目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

## 安装

使用 dist-tag `@next` 安装，不要使用裸包名、`@latest` 或 github 路径：

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

加载时 `apply()` 注册短中文 sbtd section（name `sbtd`，order 50），注册 `sbtd_plan`、`sbtd_review` 与 `sbtd_clarify`，并注册 hooks。不写用户磁盘或 `AGENTS.md`。无 plan 时对生产代码的 write/edit 会 ask 先调用 `sbtd_plan`；README 编辑放行。命中 book gate 须 `sbtd_review` 到通过态。仅 docs 模式 Clarify Complete 强制 DDD 复审。


## sbtd_clarify

首次调用必须传 `mode`：`docs`（grill-with-docs）或 `generic`（grill-me）；之后省略则继承。换 mode 会抛错，直到 `reset: true`（Interview Reset）。compaction 还原 mode 与 `clarifyStatus`，不是 Reset。

每轮只问一个 `question`。`clarifyStatus=complete` 仅当 `frontier_empty` 且 `user_confirmed` 同时为真；只读 manuals 不是 Complete。Partial 可以没有 plan；Complete 必须先 `sbtd_plan`。docs Complete 通过 haystack 事实 `完整执行 grill-with-docs` 把 `ddd` 升为 required，并调用共享 `sbtd_review kind=ddd`。generic Complete 不自动要求 DDD。Complete 且 required DDD 未 `confirmed` 时一次性 blocked，不再建议 PRD/实现。

## sbtd_review

`kind` 仅五枚举：`legacy`、`refactor`、`ddd`、`ddia`、`release`。禁止别名与 skill-id。

| kind | status 枚举 | 3.4 通过态 |
|---|---|---|
| `legacy` | `characterized` `needs-safety-net` `seam-required` `blocked` | `characterized` → `passed` |
| `refactor` | `proceed` `refactor-first` `blocked` | `proceed` → `passed` |
| `ddd` | `confirmed` `needs-clarification` `blocked` | `confirmed` → `passed` |
| `ddia` | `confirmed` `needs-design-change` `blocked` | `confirmed` → `passed` |
| `release` | `ready` `needs-mitigation` `blocked` | `ready` → `passed` |

3.4 映射：`needs-*` / `seam-required` / `refactor-first` 保持 `running`；`blocked` → `blocked`。不改 `requirement`。

示例：

```js
await sbtd_review({
  kind: "legacy",
  status: "characterized",
  conclusions: "Safety net in t5-review.test.mjs",
});
```

## manuals

`manuals/` 是从 `KunoLu/640-skills` v1.0.13（sourceRevision `f8aa0d7225a26c5e00b81d2f1b05121108e63630`）只读同步的 skill 正文。每个 skill 只拷贝 `SKILL.md` 与该 skill 自己的 `references/`。不要手改 manuals 正文。

重新同步：给本地 SOURCE 目录，或省略参数让脚本 clone 到钉死 SHA。

```bash
packages/dsh-sbtd/scripts/sync-manuals.sh /path/to/640-skills
```

`manuals/MANIFEST.json` 每条记录含 `sourcePath`（640-skills 仓相对源路径）、`sha256` 与 `sourceRevision`。源缺失、SHA 不匹配、拷贝失败或 checksum 失败时退出非 0。
