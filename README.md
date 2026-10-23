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
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.md) | OMP SBTD workflow plugin. Provides `/sbtd`, an embedded kit, `doctor`, and `onboard`. Version **0.2.0-rc.2**; publication is separate from the version bump. |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.md) | DSH SBTD adapter (T5): sbtd section, in-process state, `sbtd_plan`, `sbtd_review`, hooks, and `manuals/`. Published **0.2.0-rc.1** on dist-tag `next`. dist-tag `latest` is still **0.1.0-rc.1**. Host pin `@deepseek-ai/dsh@0.2.0-rc.2`. |

## Install

The command below pins `@kunolu/omp-sbtd@0.2.0-rc.2` for use once that version is published. A version bump does not prove registry availability or dist-tag state. This version requires omp `>=18 <19`; omp 17.x users must explicitly pin an older 0.1.x version.

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.2
```

Prefer the exact RC over a moving dist-tag such as `@latest` for reproducibility. **published** is not **installable** is not **certified**. Compatibility certification is decoupled from publish.

For 0.2.0-rc.2, the host peer is `@oh-my-pi/pi-coding-agent` `>=18 <19`; the development pin is `18.11.1`.

> No longer supports omp 17.x; tested only on 18.11.1; as of the D11 lock on 2026-10-19, upstream latest was 18.12.2

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

- **omp-sbtd** version `0.2.0-rc.2`: publication is separate from the version bump. The embedded kit is locked to **640-skills v2.0.2**. Sync, projection, and generation now live in `packages/omp-sbtd`; the former private kit workspace package was removed. Compatibility certification is decoupled from publish.
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
