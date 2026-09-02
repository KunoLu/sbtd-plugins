# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器。当前为 T3：注册短中文 sbtd section、进程内会话状态、`sbtd_plan`，以及 `tools/pre-execute` / `agent/pre-step` hooks 门禁。

目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

## 安装



> ⚠️ `@kunolu/dsh-sbtd` 尚未发布到 npm，当前无法从 registry 安装；在发布之前复制粘贴下面的命令会失败。
>
> 发布之后使用 dist-tag `@next`，不要使用裸包名或本地路径：

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

加载时 `apply()` 打印 `[dsh-sbtd] plugin loaded (T0 stub)`，注册短中文 sbtd section（name `sbtd`，order 50），注册 `sbtd_plan`，并注册 hooks。不写用户磁盘或 `AGENTS.md`。无 plan 时对生产代码的 write/edit 会 ask 先调用 `sbtd_plan`；README 编辑放行。
