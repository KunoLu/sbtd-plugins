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
| `@kunolu/omp-sbtd` | [`packages/omp-sbtd`](packages/omp-sbtd/README.md) | OMP SBTD workflow plugin. Provides `/sbtd`, an embedded kit, `doctor`, and `onboard`. Repository candidate **0.2.0-rc.3** was merged via [PR132](https://github.com/KunoLu/sbtd-plugins/pull/132) (`1f188641c594bb51e701c51b6d2692be65218214`, short `1f18864`) but remains unpublished; **0.2.0-rc.2** is the recorded historical release. |
| `@kunolu/dsh-sbtd` | [`packages/dsh-sbtd`](packages/dsh-sbtd/README.md) | DSH SBTD adapter: sbtd section, in-process state, `sbtd_plan`, `sbtd_review`, hooks, and `manuals/`. **0.2.0-rc.3** is published: npm 2026-11-18 20:28:55 +08:00, GitHub prerelease [`dsh-sbtd-v0.2.0-rc.3`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.3) 2026-11-18 20:41:17 +08:00; the 2026-11-26 lookup found `next` and `latest` pointing to `0.2.0-rc.3`. Historical release: **0.2.0-rc.2**. Host pin `@deepseek-ai/dsh@0.2.0-rc.2`. |

## Install

The **OMP 0.2.0-rc.3** candidate was merged via [PR132](https://github.com/KunoLu/sbtd-plugins/pull/132) as `1f18864`, but remains unpublished: the 2026-11-26 lookup found `latest` and `next` still pointing to `0.2.0-rc.2`. Historical `@kunolu/omp-sbtd@0.2.0-rc.2` was published on 2026-10-23 20:44:10 +08:00, with `next` and `latest` pointing to it in that record. The command below retains that historical pin; it is not rc.3 installation evidence.

```bash
omp plugin install @kunolu/omp-sbtd@0.2.0-rc.2
```

Prefer the exact RC over a moving dist-tag such as `@latest` for reproducibility. **published** is not **installable** is not **certified**. Compatibility certification is decoupled from publish.

The rc.3 candidate retains peer `@oh-my-pi/pi-coding-agent` `>=18 <19` and development pin `18.11.1`. Official 18.11.1 requires **Bun >=1.3.14** and its platform-native dependencies; Node/npm installation tooling is separate. Authorized candidate installation must use the exact reviewed local rc.3 tgz, not an assumed Registry version or source-directory link.

> Prior 18.11.1 evidence belongs to rc.2, including the local `0375a386…` tarball's SDK/RPC four-command result. Its CLI attempt stopped at the default-model preflight. None of this establishes rc.3 Host/CLI/TUI, model or trusted §4 acceptance. Historical D11 on 2026-10-19 recorded upstream latest 18.12.2; omp 17.x remains unsupported.

DSH host pin: @deepseek-ai/dsh@0.2.0-rc.2.

DSH plugin **0.2.0-rc.3** is published: npm publish on 2026-11-18 20:28:55 +08:00 and GitHub prerelease [`dsh-sbtd-v0.2.0-rc.3`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.3) on 2026-11-18 20:41:17 +08:00; the 2026-11-26 lookup found both `next` and `latest` pointing to `0.2.0-rc.3`. Historical **0.2.0-rc.2** was published on 2026-10-23 17:08:50 +08:00, with `next` and `latest` pointing to it at the recorded lookup on that date. The installation guidance remains: use `@kunolu/dsh-sbtd@next` and host `@deepseek-ai/dsh@0.2.0-rc.2`, not `@latest` or a GitHub path.

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

- **omp-sbtd** `0.2.0-rc.3` is an unpublished candidate merged via [PR132](https://github.com/KunoLu/sbtd-plugins/pull/132) (`1f188641c594bb51e701c51b6d2692be65218214`, `1f18864`): R1 comprises **six file operations across four Skills**, not a whole-upstream upgrade. Canonical vendor/lock stays at **640-skills v2.0.2** (`1d82494d74f6df9bca7dccef2da409f87091883e`), with the closed `r1-manuals` partial selection. Historical rc.2 release: [`omp-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/omp-sbtd-v0.2.0-rc.2). The 2026-11-26 15:47 pack tarball was deleted by the authorized afterEach hook, leaving no publishable package identity from that run; `91f8ecf51ce89152874b0427f99ac7b9214bbb8b9fa8039f26be87c6b781158c` (or any CI probe pack hash) must not be treated as a release identity. Local build/pack results do not replace trusted `omp-section4-publish-gate` evidence for the same full artifact digest from immutable main; publication remains separately authorized. Compatibility certification stays decoupled from publication.
- **dsh-sbtd** `0.2.0-rc.3` is published: it includes [PR127](https://github.com/KunoLu/sbtd-plugins/pull/127), with manuals at **640-skills v2.1.0** and the shared native-executor smoke fix. Release: [`dsh-sbtd-v0.2.0-rc.3`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.3) — GitHub prerelease published 2026-11-18 20:41:17 +08:00; npm publish 2026-11-18 20:28:55 +08:00; at the 2026-11-26 lookup `next` and `latest` both point to `0.2.0-rc.3`. Historical `0.2.0-rc.2` release: [`dsh-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2). Shell plugin scheme **2a**, **T0–T5**, and the completed [0.2.0-rc.1/rc.2 task rows 0–G](docs/prd/dsh-sbtd-0.2.0-rc.1.md#3-任务表) remain documented history. Earlier technical design: [`v1.2`](docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md).
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
