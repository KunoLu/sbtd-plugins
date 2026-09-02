<p align="center"><a href="./README.md">EN</a> · <a href="./README_zh.md">中文</a></p>

# sbtd-plugins

SBTD 宿主插件 monorepo：共享 workflow kit，以及 OMP 与 DSH 适配器。

## Contents

- [Packages](#packages)
- [Roadmap](#roadmap)
- [Install](#install)
- [Dev](#dev)
- [License](#license)

## Packages

| Package | Path | Role |
| --- | --- | --- |
| `@kunolu/sbtd-workflow-kit` | `packages/sbtd-workflow-kit` | 共享 SBTD workflow kit。不是宿主插件。 |
| `@kunolu/omp-sbtd` | `packages/omp-sbtd` | OMP 宿主适配器。npm `next` = `0.1.0-rc.14`。npm `latest` = `0.1.0-rc.2`。 |
| `@kunolu/dsh-sbtd` | `packages/dsh-sbtd` | DSH 宿主适配器。当前仅为 stub。目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。 |

## Roadmap

- **kit** 保持共享，不是宿主插件。
- **omp-sbtd** 是当前 OMP 宿主插件（`next` `0.1.0-rc.14`，`latest` `0.1.0-rc.2`）。
- **dsh-sbtd** 当前为 stub。第一项里程碑（T0）：`dsh plugin --profile web add <path-or-github>`，然后 `dsh --profile web --dump-config` 必须显示 `id: sbtd`。

## Install

OMP 宿主插件：

```bash
omp plugin install @kunolu/omp-sbtd@0.1.0-rc.14
omp plugin install @kunolu/omp-sbtd@0.1.0-rc.2
```

npm `next` 钉 `0.1.0-rc.14`；npm `latest` 钉 `0.1.0-rc.2`。

DSH 宿主适配器仍为 stub。T0 是：

```bash
dsh plugin --profile web add <path-or-github>
dsh --profile web --dump-config
```

`dump-config` 必须显示 `id: sbtd`。目标宿主：`@deepseek-ai/dsh@0.1.1-rc.2`。

不要把 kit 当作宿主插件安装。

## Dev

- Node.js 22 或更新
- pnpm 11.17

```bash
pnpm install
pnpm build
pnpm test
```

## License

Apache-2.0。见 [LICENSE](./LICENSE) 与 [NOTICE](./NOTICE)。
