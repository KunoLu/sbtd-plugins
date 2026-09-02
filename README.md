<p align="center">
  <a href="./README.md">EN</a>
  ·
  <a href="./README_zh.md">中文</a>
</p>

# sbtd-plugins

SBTD host-plugin monorepo: a shared workflow kit plus OMP and DSH host adapters.

## Contents

- [Packages](#packages)
- [Install](#install)
- [Roadmap](#roadmap)
- [Development](#development)
- [License](#license)

## Packages

| Package | Path | Role |
| --- | --- | --- |
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.md) | OMP SBTD workflow plugin. Provides `/sbtd`, an embedded kit, `doctor`, and `onboard`. Version **0.1.0-rc.14** on the `next` tag. |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.md) | DSH SBTD adapter. Current stub is **T0**. No tools or hooks yet. Target host `@deepseek-ai/dsh@0.1.1-rc.2`. |
| `@kunolu/sbtd-workflow-kit` | [`packages/sbtd-workflow-kit`](packages/sbtd-workflow-kit) | Shared kit / projection layer. **Not** a host plugin. |

## Install

Install the OMP plugin from `next`:

```bash
omp plugin install @kunolu/omp-sbtd@next
```

`next` is `0.1.0-rc.14`; `latest` is still `0.1.0-rc.2` (alternative: `omp plugin install @kunolu/omp-sbtd@latest`). **published** is not **installable** is not **certified**. Compatibility certification is decoupled from publish.

`@kunolu/dsh-sbtd` is a T0 stub and is not a complete DSH SBTD workflow yet.

Optional notes: [`docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md`](docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md).

## Roadmap

This repository ships **two host plugins** only: `omp-sbtd` and `dsh-sbtd`.

- **omp-sbtd** is published on `next` as `0.1.0-rc.14`. The embedded kit is locked to **640-skills v1.0.13**. Compatibility certification is decoupled from publish.
- **dsh-sbtd** uses shell plugin scheme **2a**. **T0** is a stub: `dsh plugin add` plus `dump-config` reports `id: sbtd`. **T1–T16** are not done. Details: [`docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md).

## Development

- Node 22 or newer
- pnpm 11.17

```bash
pnpm install
pnpm build
pnpm test
```

## License

Apache-2.0.
