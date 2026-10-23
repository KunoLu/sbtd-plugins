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
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.zh.md) | OMP SBTD workflow 插件。提供 `/sbtd`、内嵌 kit、`doctor` 与 `onboard`。已发布 **0.2.0-rc.2** 到 npm dist-tag `next` 与 `latest`。 |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.zh.md) | DSH SBTD 适配器：sbtd section、进程内状态、`sbtd_plan`、`sbtd_review`、hooks、`manuals/`。已发布 **0.2.0-rc.2** 到 npm dist-tag `next` 与 `latest`。宿主钉 `@deepseek-ai/dsh@0.2.0-rc.2`。 |

## 安装

`@kunolu/omp-sbtd@0.2.0-rc.2` 已于 2026-10-23 20:44:10 +08:00 发布到 npm，dist-tag `next` 与 `latest` 均指向该版本。以下命令固定该发布版本。该版本要求 omp `>=18 <19`；omp 17.x 用户须显式钉旧的 0.1.x 版本。

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.2
```

为便于复现，建议优先固定精确 RC 版本，而不是使用 `@latest` 等会移动的 dist-tag。**published** 不是 **installable** 不是 **certified**。兼容性认证与发布解耦。

对于 0.2.0-rc.2，宿主 peer 为 `@oh-my-pi/pi-coding-agent` `>=18 <19`；开发依赖钉为 `18.11.1`。

> 不再支持 omp 17.x；只在 18.11.1 上实测过；截至 2026-10-19 D11 锁定时，上游最新是 18.12.2

DSH 宿主固定 @deepseek-ai/dsh@0.2.0-rc.2。

DSH 插件 **0.2.0-rc.2** 已发布到 npm dist-tag `next` 与 `latest`（2026-10-23 17:08:50 +08:00）。保留现有安装指引：使用 `@kunolu/dsh-sbtd@next` 与宿主 `@deepseek-ai/dsh@0.2.0-rc.2`，不要使用 `@latest` 或 GitHub 路径。

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

- **omp-sbtd** `0.2.0-rc.2` 已发布到 npm dist-tag `next` 与 `latest`，GitHub prerelease 为 [`omp-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/omp-sbtd-v0.2.0-rc.2)。内嵌 kit 锁定 **640-skills v2.0.2**。同步、投影与生成现位于 `packages/omp-sbtd`，原私有 kit workspace 包已删除。兼容性认证与发布解耦。
- **dsh-sbtd** `0.2.0-rc.2` 已发布到 npm dist-tag `next` 与 `latest`，GitHub prerelease 为 [`dsh-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2)。采用 shell plugin scheme **2a**；**T0–T5** 及 [0.2.0-rc.1/rc.2 任务表 0–G 行](docs/prd/dsh-sbtd-0.2.0-rc.1.md#3-任务表) 均已完成。前代技术设计见 [`v1.2`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md)。
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
