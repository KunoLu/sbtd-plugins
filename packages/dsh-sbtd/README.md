# @kunolu/dsh-sbtd

DSH 宿主上的 SBTD workflow 适配器。当前为 T1：注册短中文 sbtd section 与进程内会话状态，尚未实现 tools / hooks。

目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

## 安装

使用 dist-tag `@next`，不要使用裸包名或本地路径：

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

加载时 `apply()` 打印 `[dsh-sbtd] plugin loaded (T0 stub)`，并注册短中文 sbtd section（name `sbtd`，order 50），不写用户磁盘或 `AGENTS.md`。
