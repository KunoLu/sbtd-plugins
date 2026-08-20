# sbtd-plugins

SBTD 宿主插件 monorepo：共享 workflow kit，以及 OMP / DSH 适配器。

从 [KunoLu/KPi](https://github.com/KunoLu/KPi) `main` @ `5b6e13bf8b21` 导入；KPi 本身未改动。

## 包

| 包 | 路径 | 说明 |
| --- | --- | --- |
| `@kunolu/sbtd-workflow-kit` | `packages/sbtd-workflow-kit` | 共享 SBTD workflow kit |
| `@kunolu/omp-sbtd` | `packages/omp-sbtd` | OMP 宿主适配器 |
| `@kunolu/dsh-sbtd` | `packages/dsh-sbtd` | DSH 宿主适配器（当前仅为 stub） |

## Dev

- Node 22 or newer
- pnpm 11.17
pnpm install / build / test

## 许可证

Apache-2.0 plus third-party notices.
