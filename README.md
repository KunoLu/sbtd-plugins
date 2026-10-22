<p align="center">
  <a href="./README.md">EN</a>
  ·
  <a href="./README_zh.md">中文</a>
</p>

# sbtd-plugins

SBTD host-plugin monorepo: OMP and DSH host adapters, with the OMP workflow kit embedded in `packages/omp-sbtd`.

## Contents

- [Packages](#packages)
- [Install](#install)
- [Roadmap](#roadmap)
- [Development](#development)
- [License](#license)

## Packages

| Package | Path | Role |
| --- | --- | --- |
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.md) | OMP SBTD workflow plugin. Provides `/sbtd`, an embedded kit, `doctor`, and `onboard`. Target release **0.2.0-rc.1** on `next`; publication is row E of the [release plan](docs/prd/omp-sbtd-0.2.0-rc.1.md). |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.md) | DSH SBTD adapter (T5): sbtd section, in-process state, `sbtd_plan`, `sbtd_review`, hooks, and `manuals/`. Published **0.2.0-rc.1** on dist-tag `next`. dist-tag `latest` is still **0.1.0-rc.1**. Host pin `@deepseek-ai/dsh@0.2.0-rc.2`. |

## Install

OMP target release: `@kunolu/omp-sbtd@0.2.0-rc.1`. The commands below apply **after row E publishes it to `next`**. Registry snapshot on 2026-10-22, before that publication: `next=0.1.0-rc.14`, `latest=0.1.0-rc.2`. Row E leaves `latest` unchanged.

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.1
```

Pin the exact RC for reproducibility; never recommend `@latest`. **published** is not **installable** is not **certified**. Compatibility certification is decoupled from publish.

For the 0.2.0-rc.1 target, the host peer is `@oh-my-pi/pi-coding-agent` `>=18 <19`; the development pin is `18.11.1`.

> No longer supports omp 17.x; tested only on 18.11.1; upstream latest is 18.12.2

DSH host pin: @deepseek-ai/dsh@0.2.0-rc.2.

DSH plugin **0.2.0-rc.1** is published on dist-tag `next`. dist-tag `latest` is still **0.1.0-rc.1**. Install with `@kunolu/dsh-sbtd@next` and host `@deepseek-ai/dsh@0.2.0-rc.2`. Never `@latest` or a github path.

```bash
npx @deepseek-ai/dsh@0.2.0-rc.2 plugin --profile web add @kunolu/dsh-sbtd@next
npx @deepseek-ai/dsh@0.2.0-rc.2 --profile web --dump-config
```

Expect dump-config id: sbtd.

Optional global install:

```bash
npm i -g @deepseek-ai/dsh@0.2.0-rc.2
dsh plugin --profile web add @kunolu/dsh-sbtd@next
dsh --profile web --dump-config
dsh web --no-open
```

Optional notes: [docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md](docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md).


## Roadmap

This repository ships **two host plugins** only: `omp-sbtd` and `dsh-sbtd`.

- **omp-sbtd** targets `0.2.0-rc.1` on `next`. The embedded kit is locked to **640-skills v2.0.2**. Sync, projection, and generation now live in `packages/omp-sbtd`; the former private kit workspace package was removed. Compatibility certification is decoupled from publish.
- **dsh-sbtd** uses shell plugin scheme **2a**. **T0–T5** are done on `main` (section, state, `sbtd_plan`, `sbtd_review`, hooks, manuals). Later tasks remain. Details: [`docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.1.md).

## Development

- Node 22 or newer
- pnpm 11.17

```bash
pnpm install
pnpm build
pnpm test
```

Repository maintenance uses the SBTD `v2.0.0-rc.4` project template and managed Graft block; this does not upgrade the plugins' embedded kit or published versions. Before changing a component or layer, read its guidelines under [docs/spec](docs/spec/), and consult the [lesson index](docs/lessons/index.md). Shared history is in `ai/tasks/`; unowned legacy documents are preserved under `docs/legacy-archive/`. Reports and local state remain ignored.

## License

Apache-2.0.
