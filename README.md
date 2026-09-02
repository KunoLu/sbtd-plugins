<p align="center"><a href="./README.md">EN</a> · <a href="./README_zh.md">中文</a></p>

# sbtd-plugins

SBTD host-plugin monorepo: a shared workflow kit plus OMP and DSH adapters.

## Contents

- [Packages](#packages)
- [Roadmap](#roadmap)
- [Install](#install)
- [Dev](#dev)
- [License](#license)

## Packages

| Package | Path | Role |
| --- | --- | --- |
| `@kunolu/sbtd-workflow-kit` | `packages/sbtd-workflow-kit` | Shared SBTD workflow kit. Not a host plugin. |
| `@kunolu/omp-sbtd` | `packages/omp-sbtd` | OMP host adapter. npm `next` = `0.1.0-rc.14`. npm `latest` = `0.1.0-rc.2`. |
| `@kunolu/dsh-sbtd` | `packages/dsh-sbtd` | DSH host adapter. Currently a stub. Target host: `@deepseek-ai/dsh@0.1.1-rc.2`. |

## Roadmap

- **kit** stays shared. It is not a host plugin.
- **omp-sbtd** is the current OMP host plugin (`next` `0.1.0-rc.14`, `latest` `0.1.0-rc.2`).
- **dsh-sbtd** is a stub. First milestone (T0): `dsh plugin --profile web add <path-or-github>`, then `dsh --profile web --dump-config` must show `id: sbtd`.

## Install

OMP host plugin:

```bash
omp plugin install @kunolu/omp-sbtd@0.1.0-rc.14
omp plugin install @kunolu/omp-sbtd@0.1.0-rc.2
```

Pin `0.1.0-rc.14` for npm `next`, or `0.1.0-rc.2` for npm `latest`.

DSH host adapter is still a stub. T0 is:

```bash
dsh plugin --profile web add <path-or-github>
dsh --profile web --dump-config
```

`dump-config` must show `id: sbtd`. Target host: `@deepseek-ai/dsh@0.1.1-rc.2`.

Do not install the kit as a host plugin.

## Dev

- Node.js 22 or newer
- pnpm 11.17

```bash
pnpm install
pnpm build
pnpm test
```

## License

Apache-2.0. See [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
