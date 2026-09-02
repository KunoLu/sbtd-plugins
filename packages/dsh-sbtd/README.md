# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器。当前为 T0 stub：尚未实现 tools / hooks。

目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

## 安装

> ⚠️ `@kunolu/dsh-sbtd` 尚未发布到 npm，当前无法从 registry 安装；在发布之前复制粘贴下面的命令会失败。
>
> 发布之后使用 dist-tag `@next`，不要使用裸包名或本地路径：

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

加载时 `apply()` 只打印 `[dsh-sbtd] plugin loaded (T0 stub)`，并注册空的 `sbtd` systemPrompt section，不写用户磁盘或 `AGENTS.md`。
