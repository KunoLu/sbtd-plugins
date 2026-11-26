<p align="center">
  <a href="./README.md">EN</a>
  ·
  <a href="./README.zh.md">中文</a>
</p>

# @kunolu/omp-sbtd

面向 KPi、运行于 OMP 宿主的 SBTD workflow 插件。提供 `/sbtd` 命令与固定、只读的 SBTD Kit 快照；安装插件时不会静默安装全局工具或修改项目。

**当前源码候选：`0.2.0-rc.3`，尚未发布。** 未核验 Registry 可用性、当前
dist-tag 或 rc.3 release/tag。本地构建及包检查不等于发布就绪或受信§4验收。

## 环境要求

- `0.2.0-rc.3` 声明宿主 peer `@oh-my-pi/pi-coding-agent`
  为 `>=18 <19`；开发依赖仍精确钉为 **18.11.1**。
- 官方 OMP **18.11.1** 的 `dist/cli.js` 使用 **Bun >=1.3.14** 及对应平台
  native 依赖。Node.js/npm 安装工具与 Host 解释器分开，不能用 Node 启动该CLI。
- 需要 provider 的命令要求对应已配置的 profile；即使运行本地命令，
  CLI启动也可能先要求默认模型。

> 历史D11/rc.2说明：不支持omp 17.x；此前实测目标为18.11.1；截至2026-10-19 D11锁定时，上游最新是18.12.2。这不是rc.3宿主证据。

Peer 范围只决定 *installable*。安装和 npm 发布都不代表宿主兼容性认证：
`published`、`installable` 与 `certified` 是不同状态。认证状态由仓库兼容性
记录跟踪，不由安装成功推导。

安装前检查已安装的宿主版本：

```bash
omp --version
```

## 安装

历史发布：`@kunolu/omp-sbtd@0.2.0-rc.2` 于2026-10-23 20:44:10 +08:00
发布到npm，当时记录的`next`与`latest`指向它；此处不重新查询当前Registry。
以下命令保留该已发布pin，**不是**安装尚未发布的rc.3候选。
它要求omp `>=18 <19`；omp 17.x用户须显式钉旧0.1.x。

后续经授权验证rc.3候选时，应在隔离npm tarball安装流程中使用精确受审的
`kunolu-omp-sbtd-0.2.0-rc.3.tgz`，不得以源码目录链接或假定Registry
`@0.2.0-rc.3`替代。本轮候选准备本身不安装插件。

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.2
```

OMP 默认安装到用户范围。若只为当前项目安装：

```bash
omp plugin install --scope project @kunolu/omp-sbtd@0.2.0-rc.2
```

安装后打开新的 OMP 会话，然后验证插件与命令注册：

```bash
omp plugin list
omp plugin doctor
```

```text
/sbtd help
```

此前云端安装/会话证据使用本地 **rc.2** tgz，SHA256为
`0375a386b98d3f79aa512681e842ecc8b62539a2c4b1320d6ea6d4031f347610`，
运行于官方18.11.1/Bun。四命令经官方SDK/RPC会话完成；CLI尝试因未配置默认
模型，在调度前停止。两者都不能转借给新rc.3包，也不证明受信§4、CLI/TUI、
模型或完整宿主验收通过。

## 内嵌工作流

Canonical vendor/lock基底仍为 **640-skills v2.0.2**
（`1d82494d74f6df9bca7dccef2da409f87091883e`），transform为`p0-v4`。
闭合的`r1-manuals`是**四个Skill的六项文件操作**：domain-modeling的SKILL更新、
CONTEXT-FORMAT删除与GLOSSARY-FORMAT新增，grilling/to-tickets的SKILL更新，
以及sbtd-task的presentation reference更新；不是整套上游v2.1.0升级。
精确来源/许可身份继续保存在Kit provenance中。同步、投影与生成位于本包，
供应链source ID `sbtd-workflow-kit-upstream`保持不变。

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

**Handoff 证据：** `omp-extension-v2` 契约与 `omp-host-events-v2` profile
要求 `session_compact`（13 个必需事件加 1 个可选事件）。成功 handoff
须由关联事件证明，且 `compactionEntry.method === "handoff"`；缺少 method
或窗口内存在竞争 compact 均失败。`HANDOFF_EVENT_UNOBSERVABLE` 为硬失败。
omp 18.11.1 安装路径 smoke 不等于
模型端到端测试或完整 host-event 认证。

## 平台支持

本包未声明`os`或`cpu`限制，自身不含原生二进制依赖。实际运行取决于官方OMP
宿主及其Bun解释器/平台native依赖；Node.js/npm安装工具是另一项要求。

- **macOS 和 Linux：** 未声明包级限制。
- **Windows：** 安装要求受支持的官方OMP/Bun/native环境，此处不声明已通过Windows验收。随包`/sbtd onboard` bootstrap不会自动完成原生Windows的Node.js/npm安装；请先安装Node.js/npm（例如nvm-windows、nvs或已批准的等效工具）。
- **发布 helper：** `docs/deploy/publish-omp-sbtd.sh` 是唯一获准的 Registry 写入入口。请在 macOS、Linux、WSL 或 Git Bash 的 Bash 环境运行，不要直接使用 `/bin/sh` 或 PowerShell。Windows 用户也必须从支持 Bash 的 shell 调用该 helper，不得改用直接 `npm publish`。

## 发布 RC 版本

已发布的 npm tarball 不可变。构建并打包一个新的预发布 tarball；
不要复用已经发布过的 tarball。

发布前须由受信`omp-section4-publish-gate` workflow从不可变`main` SHA
构建并pack，并针对**同一完整tarball digest**通过`/sbtd help`、`/sbtd status`、
`/sbtd report`和`/sbtd onboard plan`四命令验收：无Provider请求、批准请求或
意外写入。本地SDK/API测试、build检查或本地候选pack不能替代该受信run。
精确流程见仓库[手册§3/§4](../../docs/assets/omp/omp-plugin-host-acceptance.md)。

随后仓库 helper 仅将同一 tarball 发布到 `next`：

```bash
export NPM_TOKEN='npm access token'
docs/deploy/publish-omp-sbtd.sh /absolute/path/kunolu-omp-sbtd-<version>.tgz --tag next
```

在调用 `npm publish` 之前，helper 会拒绝稳定版本、其他包、`latest` 或任何
其他 dist-tag、已占用的版本，以及未知的 Registry 可用性结果。
操作人还须独立核对受信run、source SHA与完整artifact digest：helper自身
不验证§4证据。实际获授权发布还要求新鲜且明确的Registry可用性结果。

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
