<p align="center">
  <a href="./README.md">EN</a>
  ·
  <a href="./README_zh.md">中文</a>
</p>

# sbtd-plugins

SBTD 宿主插件 monorepo：共享 workflow kit，以及 OMP / DSH 宿主适配器。

## 目录

- [包](#包)
- [安装](#安装)
- [路线图](#路线图)
- [开发](#开发)
- [许可证](#许可证)

## 包

| 包 | 路径 | 说明 |
| --- | --- | --- |
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.md) | OMP SBTD workflow 插件。提供 `/sbtd`、内嵌 kit、`doctor` 与 `onboard`。版本 **0.1.0-rc.14**，发布在 `next` tag。 |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.md) | DSH SBTD 适配器（T5）：sbtd section、进程内状态、`sbtd_plan`、`sbtd_review`、hooks、`manuals/`。版本 **0.1.0-rc.1**，发布在 `next` tag。宿主钉 `@deepseek-ai/dsh@0.1.1-rc.2`。 |
| `@kunolu/sbtd-workflow-kit` | [`packages/sbtd-workflow-kit`](packages/sbtd-workflow-kit) | 共享 kit / 投影层。**不是**宿主插件。 |

## 安装

OMP 插件（发布在 dist-tag next，版本 0.1.0-rc.14）：

```bash
omp plugin install @kunolu/omp-sbtd@next
```

这是 dist-tag next 上的 0.1.0-rc.14。不要推荐 @latest。**published** 不是 **installable** 不是 **certified**。兼容性认证与发布解耦。

DSH 宿主固定 @deepseek-ai/dsh@0.1.1-rc.2。

DSH 插件版本 **0.1.0-rc.1**，发布在 dist-tag `next`。使用 `@kunolu/dsh-sbtd@next` 与宿主 `@deepseek-ai/dsh@0.1.1-rc.2` 安装。不要使用 `@latest` 或 github 路径。

```bash
npx @deepseek-ai/dsh@0.1.1-rc.2 plugin --profile web add @kunolu/dsh-sbtd@next
npx @deepseek-ai/dsh@0.1.1-rc.2 --profile web --dump-config
```

dump-config 应含 id: sbtd。

可选全局安装：

```bash
npm i -g @deepseek-ai/dsh@0.1.1-rc.2
dsh plugin --profile web add @kunolu/dsh-sbtd@next
dsh --profile web --dump-config
dsh web --no-open
```

可选说明：[docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md](docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md).


## 路线图

本仓库只交付 **两个宿主插件**：`omp-sbtd` 与 `dsh-sbtd`。

- **omp-sbtd** 已发布到 `next`，版本 `0.1.0-rc.14`。内嵌 kit 锁定 **640-skills v1.0.13**。兼容性认证与发布解耦。
- **dsh-sbtd** 采用 shell plugin scheme **2a**。**T0–T5** 已在 `main` 完成（section、state、`sbtd_plan`、`sbtd_review`、hooks、manuals）。后续任务仍待做。细节见 [`docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md)。

## 开发

- Node 22 或更高
- pnpm 11.17

```bash
pnpm install
pnpm build
pnpm test
```

## 许可证

Apache-2.0.
