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
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.md) | OMP SBTD workflow plugin. Provides `/sbtd`, an embedded kit, `doctor`, and `onboard`. Published **0.2.0-rc.2** on npm dist-tags `next` and `latest`. |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.md) | DSH SBTD adapter: sbtd section, in-process state, `sbtd_plan`, `sbtd_review`, hooks, and `manuals/`. Published **0.2.0-rc.2** on npm dist-tags `next` and `latest`. Host pin `@deepseek-ai/dsh@0.2.0-rc.2`. |

## Install

`@kunolu/omp-sbtd@0.2.0-rc.2` was published to npm on 2026-10-23 20:44:10 +08:00; dist-tags `next` and `latest` point to it. The command below pins that release. This version requires omp `>=18 <19`; omp 17.x users must explicitly pin an older 0.1.x version.

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.2
```

Prefer the exact RC over a moving dist-tag such as `@latest` for reproducibility. **published** is not **installable** is not **certified**. Compatibility certification is decoupled from publish.

For 0.2.0-rc.2, the host peer is `@oh-my-pi/pi-coding-agent` `>=18 <19`; the development pin is `18.11.1`.

> No longer supports omp 17.x; tested only on 18.11.1; as of the D11 lock on 2026-10-19, upstream latest was 18.12.2

DSH host pin: @deepseek-ai/dsh@0.2.0-rc.2.

DSH plugin **0.2.0-rc.2** is published on npm dist-tags `next` and `latest` (2026-10-23 17:08:50 +08:00). The existing installation guidance remains: use `@kunolu/dsh-sbtd@next` and host `@deepseek-ai/dsh@0.2.0-rc.2`, not `@latest` or a GitHub path.

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

- **omp-sbtd** `0.2.0-rc.2` is published on npm dist-tags `next` and `latest`, with GitHub prerelease [`omp-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/omp-sbtd-v0.2.0-rc.2). The embedded kit is locked to **640-skills v2.0.2**. Sync, projection, and generation now live in `packages/omp-sbtd`; the former private kit workspace package was removed. Compatibility certification is decoupled from publish.
- **dsh-sbtd** `0.2.0-rc.2` is published on npm dist-tags `next` and `latest`, with GitHub prerelease [`dsh-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2). It uses shell plugin scheme **2a**. **T0–T5** and the [0.2.0-rc.1/rc.2 task rows 0–G](docs/prd/dsh-sbtd-0.2.0-rc.1.md#3-任务表) are done. Earlier technical design: [`v1.2`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md).
- **session_compact** shipped in `omp-sbtd 0.2.0-rc.2`: PRD [#120](https://github.com/KunoLu/sbtd-plugins/pull/120) (`67465db`), decisions [#122](https://github.com/KunoLu/sbtd-plugins/pull/122) (`6843878`), and code [#123](https://github.com/KunoLu/sbtd-plugins/pull/123) (`008cea7`) are merged. It is a required event under `omp-extension-v2` / `omp-host-events-v2`; handoff proof requires a correlated event with `compactionEntry.method === "handoff"`.

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
