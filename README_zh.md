<p align="center">
  <a href="./README.md">EN</a>
  ·
  <a href="./README_zh.md">中文</a>
</p>

# sbtd-plugins

SBTD 宿主插件 monorepo：OMP / DSH 宿主适配器，OMP workflow kit 内嵌在 `packages/omp-sbtd` 中。

## 目录

- [包](#包)
- [安装](#安装)
- [路线图](#路线图)
- [开发](#开发)
- [许可证](#许可证)

## 包

| 包 | 路径 | 说明 |
| --- | --- | --- |
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.zh.md) | OMP SBTD workflow插件，提供`/sbtd`、内嵌kit、doctor与onboard。仓库候选 **0.2.0-rc.3** 已通过 [PR132](https://github.com/KunoLu/sbtd-plugins/pull/132) 合入（`1f188641c594bb51e701c51b6d2692be65218214`，短 `1f18864`），但仍未发布；**0.2.0-rc.2** 为已记录的历史发布。 |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.zh.md) | DSH SBTD 适配器：sbtd section、进程内状态、`sbtd_plan`、`sbtd_review`、hooks、`manuals/`。**0.2.0-rc.3** 已发布：npm 2026-11-18 20:28:55 +08:00，GitHub prerelease [`dsh-sbtd-v0.2.0-rc.3`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.3) 2026-11-18 20:41:17 +08:00；2026-11-26 查询 `next` 与 `latest` 均指向 `0.2.0-rc.3`。历史已发布版本为 **0.2.0-rc.2**。宿主钉 `@deepseek-ai/dsh@0.2.0-rc.2`。 |

## 安装

**OMP 0.2.0-rc.3** 候选已由 [PR132](https://github.com/KunoLu/sbtd-plugins/pull/132) 合入为 `1f18864`，但仍未发布：2026-11-26 查询 `latest` 与 `next` 仍指向 `0.2.0-rc.2`。历史`@kunolu/omp-sbtd@0.2.0-rc.2`于2026-10-23 20:44:10 +08:00发布，当时记录的`next`与`latest`指向它。以下命令保留该历史pin，不是rc.3安装证据。

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.2
```

为便于复现，建议优先固定精确 RC 版本，而不是使用 `@latest` 等会移动的 dist-tag。**published** 不是 **installable** 不是 **certified**。兼容性认证与发布解耦。

rc.3候选仍声明peer `@oh-my-pi/pi-coding-agent` `>=18 <19`，开发pin为`18.11.1`。官方18.11.1要求 **Bun >=1.3.14** 及对应平台native依赖；Node/npm安装工具另计。经授权安装候选时须用精确受审本地rc.3 tgz，不得以假定Registry版本或源码目录链接替代。

> 此前18.11.1证据属于rc.2，包括本地`0375a386…`包的SDK/RPC四命令结果；CLI尝试停在默认模型前置。它们不证明rc.3 Host/CLI/TUI、模型或受信§4通过。历史2026-10-19 D11记录上游最新为18.12.2；omp 17.x仍不支持。

DSH 宿主固定 @deepseek-ai/dsh@0.2.0-rc.2。

DSH 插件 **0.2.0-rc.3** 已发布：npm 发布时间 2026-11-18 20:28:55 +08:00，GitHub prerelease [`dsh-sbtd-v0.2.0-rc.3`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.3) 发布时间 2026-11-18 20:41:17 +08:00；2026-11-26 查询 `next` 与 `latest` 均指向 `0.2.0-rc.3`。历史 **0.2.0-rc.2** 已于 2026-10-23 17:08:50 +08:00 发布，当时记录的查询中 `next` 与 `latest` 均指向它。保留现有安装指引：使用 `@kunolu/dsh-sbtd@next` 与宿主 `@deepseek-ai/dsh@0.2.0-rc.2`，不要使用 `@latest` 或 GitHub 路径。

```bash
npx @deepseek-ai/dsh@0.2.0-rc.2 plugin --profile web add @kunolu/dsh-sbtd@next
npx @deepseek-ai/dsh@0.2.0-rc.2 --profile web --dump-config
```

dump-config 应含 id: sbtd。

可选全局安装：

```bash
npm i -g @deepseek-ai/dsh@0.2.0-rc.2
dsh plugin --profile web add @kunolu/dsh-sbtd@next
dsh --profile web --dump-config
dsh web --no-open
```

可选说明：[docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md](docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md).


## 路线图

本仓库只交付 **两个宿主插件**：`omp-sbtd` 与 `dsh-sbtd`。

- **omp-sbtd** `0.2.0-rc.3`为未发布候选，已通过 [PR132](https://github.com/KunoLu/sbtd-plugins/pull/132) 合入（`1f188641c594bb51e701c51b6d2692be65218214`，`1f18864`）：R1是**四个Skill的六项文件操作**，不是整套上游升级。Canonical vendor/lock仍钉 **640-skills v2.0.2**（`1d82494d74f6df9bca7dccef2da409f87091883e`），配合闭合的`r1-manuals`部分选择。历史rc.2发布见[`omp-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/omp-sbtd-v0.2.0-rc.2)。2026-11-26 15:47 那次 pack tarball 已被授权的 afterEach 删除，该次运行没有留下可发布的包身份；`91f8ecf51ce89152874b0427f99ac7b9214bbb8b9fa8039f26be87c6b781158c`（或某次 CI probe pack 哈希）不得当作发布身份。本地build/pack不替代不可变main所产同一完整artifact digest的受信`omp-section4-publish-gate`证据；发布仍须单独授权，兼容性认证与发布解耦。
- **dsh-sbtd** `0.2.0-rc.3` 已发布：纳入 [PR127](https://github.com/KunoLu/sbtd-plugins/pull/127)，手册固定 **640-skills v2.1.0**，共享 smoke 已补齐 native executor 初始化。发布见 [`dsh-sbtd-v0.2.0-rc.3`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.3)：GitHub prerelease 发布时间 2026-11-18 20:41:17 +08:00；npm 发布时间 2026-11-18 20:28:55 +08:00；2026-11-26 查询 `next` 与 `latest` 均指向 `0.2.0-rc.3`。历史 `0.2.0-rc.2` 发布见 [`dsh-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2)。Shell plugin scheme **2a**、**T0–T5** 及已完成的 [0.2.0-rc.1/rc.2 任务表 0–G 行](docs/prd/dsh-sbtd-0.2.0-rc.1.md#3-任务表) 保留为历史；前代技术设计见 [`v1.2`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md)。
- **session_compact** 已随 `omp-sbtd 0.2.0-rc.2` 发布：PRD [#120](https://github.com/KunoLu/sbtd-plugins/pull/120)（`67465db`）、decisions [#122](https://github.com/KunoLu/sbtd-plugins/pull/122)（`6843878`）、code [#123](https://github.com/KunoLu/sbtd-plugins/pull/123)（`008cea7`）均已合并。它是 `omp-extension-v2` / `omp-host-events-v2` 的必需事件；handoff 证明须关联事件且满足 `compactionEntry.method === "handoff"`。

## 开发

- Node 22 或更高
- pnpm 11.17

```bash
pnpm install
pnpm build
pnpm test
```

仓库维护使用 SBTD `v2.0.0-rc.4` 项目模板及受管 Graft 块，不改变插件内嵌 kit 或已发布版本。修改组件或层之前先读 [docs/spec](docs/spec/) 对应规范，并按[lesson 索引](docs/lessons/index.md)查阅经验。共享历史位于 `ai/tasks/`，未归属具体任务的旧文档保留在 `docs/legacy-archive/`；报告与本地状态继续忽略。

## 许可证

Apache-2.0.
