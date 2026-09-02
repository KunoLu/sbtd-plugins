# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器。当前为 T0 stub：可安装，尚未实现 tools / hooks。

目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

## 安装

本地路径安装（web profile）：

```bash
dsh plugin --profile web add /absolute/path/to/sbtd-plugins/packages/dsh-sbtd
```

加载时 `apply()` 只打印 `[dsh-sbtd] plugin loaded (T0 stub)`，并注册空的 `sbtd` systemPrompt section，不写用户磁盘或 `AGENTS.md`。
