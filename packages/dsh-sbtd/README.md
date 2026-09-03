# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器。当前为 T5：注册短中文 sbtd section、进程内会话状态、`sbtd_plan`、`sbtd_review`、`tools/pre-execute` / `agent/pre-step` hooks 门禁，以及从 640-skills 只读同步的 `manuals/`。

目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

## 安装



> ⚠️ `@kunolu/dsh-sbtd` 尚未发布到 npm，当前无法从 registry 安装；在发布之前复制粘贴下面的命令会失败。
>
> 发布之后使用 dist-tag `@next`，不要使用裸包名或本地路径：

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

加载时 `apply()` 打印 `[dsh-sbtd] plugin loaded (T0 stub)`，注册短中文 sbtd section（name `sbtd`，order 50），注册 `sbtd_plan` 与 `sbtd_review`，并注册 hooks。不写用户磁盘或 `AGENTS.md`。无 plan 时对生产代码的 write/edit 会 ask 先调用 `sbtd_plan`；README 编辑放行。命中 book gate 须 `sbtd_review` 到通过态。

## manuals

`manuals/` 是从 `KunoLu/640-skills` v1.0.13（sourceRevision `f8aa0d7225a26c5e00b81d2f1b05121108e63630`）只读同步的 skill 正文。每个 skill 只拷贝 `SKILL.md` 与该 skill 自己的 `references/`。不要手改 manuals 正文。

重新同步：给本地 SOURCE 目录，或省略参数让脚本 clone 到钉死 SHA。

```bash
packages/dsh-sbtd/scripts/sync-manuals.sh /path/to/640-skills
```

`manuals/MANIFEST.json` 每条记录含 `sourcePath`（640-skills 仓相对源路径）、`sha256` 与 `sourceRevision`。源缺失、SHA 不匹配、拷贝失败或 checksum 失败时退出非 0。
