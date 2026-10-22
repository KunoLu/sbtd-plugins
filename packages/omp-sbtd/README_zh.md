<p align="center">
  <a href="https://github.com/KunoLu/sbtd-plugins/blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README.md">EN</a>
  ·
  <a href="https://github.com/KunoLu/sbtd-plugins/blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md">中文</a>
</p>

# @kunolu/omp-sbtd

面向 KPi、运行于 OMP 宿主的 SBTD workflow 插件。提供 `/sbtd` 命令与固定、只读的 SBTD Kit 快照；安装插件时不会静默安装全局工具或修改项目。

## 环境要求

- `0.2.0-rc.1` 声明宿主 peer `@oh-my-pi/pi-coding-agent`
  为 `>=18 <19`；开发依赖精确钉为 **18.11.1**。
- 需要 provider 的命令要求已认证的 OMP provider profile。

> 不再支持 omp 17.x；只在 18.11.1 上实测过；截至 2026-10-19 D11 锁定时，上游最新是 18.12.2

Peer 范围只决定 *installable*。安装和 npm 发布都不代表宿主兼容性认证：
`published`、`installable` 与 `certified` 是不同状态。认证状态由仓库兼容性
记录跟踪，不由安装成功推导。

安装前检查已安装的宿主版本：

```bash
omp --version
```

## 安装

`@kunolu/omp-sbtd@0.2.0-rc.1` 已发布到 npm dist-tag `next` 与 `latest`。
不带版本的安装（`omp plugin install @kunolu/omp-sbtd`）现在会取得
0.2.0-rc.1，它要求 omp `>=18 <19`。omp 17.x 用户须显式钉旧的 0.1.x 版本。

为便于复现，建议优先固定精确 RC 版本，而不是使用 `@latest` 等会移动的 dist-tag：

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.1
```

OMP 默认安装到用户范围。若只为当前项目安装：

```bash
omp plugin install --scope project @kunolu/omp-sbtd@0.2.0-rc.1
```

安装后打开新的 OMP 会话，然后验证插件与命令注册：

```bash
omp plugin list
omp plugin doctor
```

```text
/sbtd help
```

## 内嵌工作流

Kit 钉为 **640-skills v2.0.2**
（`1d82494d74f6df9bca7dccef2da409f87091883e`），transform 版本为
`p0-v4`。同步、投影与生成位于本包内，原私有 kit workspace 包已删除。
供应链 source ID `sbtd-workflow-kit-upstream` 保持不变。

随包内容包括全部 33 个上游 Python 脚本、九个 runtime assets、两个 schema，
以及 `sbtd-task` 模板树（八个模板文件，另含 LICENSE、NOTICE）。可识别且需要依赖的 SBTD Python 命令
（包括 upgrade 和 migration）会隔离预检 `kit/onboard/runtime/requirements.txt`
中五个钉版依赖：`jsonschema`、`PyYAML`、`markdown-it-py`、`tomlkit` 与
`cryptography`。缺少依赖即 fail-closed；缺少 `cryptography` 时验签拒绝运行。
不自动安装，也不降级为 skipped。仅依赖标准库的 onboard 命令仍可使用；
此宿主 guard 不是通用 shell sandbox。

Onboard Skill catalog 使用 `sbtd-task` 替代 `trellis-workflow` 与
`trellis-channel`。只读任务观测识别 `ai/tasks/**` 与 `.sbtd/tasks/**`
下的 `in-progress` 和 `checking`；legacy `.trellis` 观测仍为只读。
任务状态写入继续由 `sbtd-task` 负责。

**已知限制：** omp 18.x 上的 handoff 无法通过 `session_switch` 观测。
p0 host-event live cell 暂将 `HANDOFF_EVENT_UNOBSERVABLE` 报为 diagnostic，
而非硬失败。已登记的后续任务将更新契约、实现 `session_compact` 观测，
并恢复缺失 handoff 证据时的硬失败。omp 18.11.1 安装路径 smoke 不等于
模型端到端测试或完整 host-event 认证。

## 平台支持

本包未声明 `os` 或 `cpu` 限制，不含原生二进制依赖。因此其运行支持范围取决于
已安装的 OMP 宿主与 Node.js 环境，而非 npm 包本身。

- **macOS 和 Linux：** 未声明包级限制。
- **Windows：** 可在支持 OMP 及其所需 Node.js runtime 的环境安装插件。随包的 `/sbtd onboard` bootstrap 不会自动完成原生 Windows 的 Node.js/npm 安装；请先安装 Node.js/npm（例如使用 nvm-windows、nvs 或已批准的等效工具）。
- **发布 helper：** `docs/deploy/publish-omp-sbtd.sh` 是唯一获准的 Registry 写入入口。请在 macOS、Linux、WSL 或 Git Bash 的 Bash 环境运行，不要直接使用 `/bin/sh` 或 PowerShell。Windows 用户也必须从支持 Bash 的 shell 调用该 helper，不得改用直接 `npm publish`。

## 发布 RC 版本

已发布的 npm tarball 不可变。构建并打包一个新的预发布 tarball；
不要复用已经发布过的 tarball。

发布前，按仓库手册对精确 tarball 运行隔离的四命令验收：`/sbtd help`、
`/sbtd status`、`/sbtd report` 与 `/sbtd onboard plan`。命令必须在不发起
Provider 请求、不请求批准、没有意外写入的情况下完成。详细流程与清理边界见
[`docs/assets/omp/omp-plugin-host-acceptance.md`](../../docs/assets/omp/omp-plugin-host-acceptance.md)。

随后仓库 helper 仅将同一 tarball 发布到 `next`：

```bash
export NPM_TOKEN='npm access token'
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-<version>.tgz --tag next
```

在调用 `npm publish` 之前，helper 会拒绝稳定版本、其他包、`latest` 或任何
其他 dist-tag、已占用的版本，以及未知的 Registry 可用性结果。

`NPM_TOKEN` 必须是对 `@kunolu/omp-sbtd` 或其 scope 具有 **Read and write**
权限的 npm access token。若账号或组织要求 2FA，请为 token 配置
**Bypass two-factor authentication** 或提供所需 OTP；否则 `npm publish`
仍可能请求 OTP。

### 可选的仓库本地 `.env`

仓库已忽略根目录的 `.env`。其中可以仅保存本地秘密引用：

```dotenv
NPM_TOKEN=npm_your_token_value
```

保持该文件私密且仅所有者可读：

```bash
chmod 600 .env
```

Helper 按以下顺序解析凭据：

1. 仓库根 `.env` 中非空的字面量 `NPM_TOKEN=<token>` 赋值。
2. 当 `.env` 不存在或其中赋值为空时，使用继承的非空 `NPM_TOKEN` 环境变量。

Helper 将 `.env` 作为数据解析，不会 source 或执行它。只接受上述字面量赋值形式，
忽略其他行。因此 `.env` token 优先于继承的环境 token。直接调用 helper：

```bash
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-<version>.tgz --tag next
```

Helper 不接受 token 参数，不打印 token 值；传给 npm 的临时 userconfig 仅所有者
可访问，且只含字面量 `${NPM_TOKEN}` 引用。

## 支持

- Issues：<https://github.com/KunoLu/sbtd-plugins/issues>
- 安全报告：见 [SECURITY.md](./SECURITY.md)（邮箱 songlin.lu@neox-inc.com；未修复漏洞不要提交公开 issue）。
- RC 版本不提供正式 SLA；仅支持最新 RC 系列。

## 数据处理与遥测

本插件**不收集遥测**，自身**不发起网络调用**。所有观测都在本地执行：会话状态
追加到宿主 session entries（`kpi.sbtd.session.v1`）；验证证据描述符仅保存
SHA-256 指纹（scenario locator digest、report digest、sidecar digest、commit），
从不保存文件内容、秘密或 prompt 文本。内嵌 validator
（`python3 validate_validation_evidence.py`）只读取项目根内的文件。

## 卸载与回滚

1. 从 OMP 配置移除 extension（全局安装则运行 `npm uninstall -g @kunolu/omp-sbtd`）。
2. 删除会话状态：通过宿主会话管理移除 `kpi.sbtd.session.v1` entries，或开始新会话——插件不在 session log 外保存状态。
3. 回滚：安装前一个 RC（`npm install -g @kunolu/omp-sbtd@<previous-rc>`）。旧 reader 会忽略新增的 `validationEvidence` 描述符字段，因此仍可读取本版本写入的状态。

## 许可证

Apache-2.0。见 [LICENSE](./LICENSE) 与 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。
