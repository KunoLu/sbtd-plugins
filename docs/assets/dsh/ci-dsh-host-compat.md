# 上游 `dsh` 发新版：宿主兼容校验

适用包：`@kunolu/dsh-sbtd@0.1.0-rc.1`。现行 `peerDependencies`：`@deepseek-ai/dsh: 0.1.1-rc.2`。本指南不替代合主线审查，也不授权 npm 发布。

现有 GitHub Actions 全部是 `omp-*`。dsh **拟**用独立 workflow 名 `dsh-host-compat`、`dsh-manuals-pin`，禁止改 `omp-compatibility-*`。**本 PR 未入库** `.github/workflows/dsh-*.yml`（OAuth 缺 `workflow` scope）；在文件进仓之前，不要 `workflow_dispatch` 这些名字，跑下面「本地等价」命令。

## 触发条件

出现任一情况即跑本清单：

1. 上游发布新的 `@deepseek-ai/dsh`（含 rc / alpha），准备评估当前插件能否继续用。
2. 准备把 `peerDependencies` / 兼容矩阵从 `0.1.1-rc.2` 扩到候选版本。
3. 怀疑宿主 schema / Cordis `register` / tool `output.schema` 行为变了（T16 / FU4 同类）。
4. 拟议手动 `workflow_dispatch`：`.github/workflows/dsh-host-compat.yml`（**pending / 本 PR 未入库**）。未入库前用本地 `pnpm --filter @kunolu/dsh-sbtd test` + pack。

未触发：只改 omp 文档、只改 manuals pin、只改无关 markdown。

## 自动化门禁清单

| 门 | 命令 / Actions | 级别 | 期望 |
|---|---|---|---|
| 单测 | `pnpm --filter @kunolu/dsh-sbtd test`（=`tsc` + `node --test test/*.test.mjs`） | **REQUIRED** | 退出码 0。含 `test/fu4-host-schema.test.mjs` |
| FU4 pinned-host register smoke | 套件内 `fu4-host-schema.test.mjs`；拟议 `dsh-host-compat` job `unit-pack` temp cell（**pending**） | **REQUIRED（命令）** | 钉死 `@deepseek-ai/dsh@0.1.1-rc.2` 与 `@kunolu/dsh-sbtd@0.1.0-rc.1`；Cordis `register/load` 接受 `sbtd_clarify` / `sbtd_spec` / `sbtd_tickets` 的 `output.schema`；`properties.*.type` 不是数组。YAML 未入库前只跑本地 `pnpm --filter @kunolu/dsh-sbtd test` |
| pack 含 `dist/` | `pnpm --filter @kunolu/dsh-sbtd pack --pack-destination <tmp>` 后检查 tarball | **REQUIRED** | tarball 内有 `package/dist/` 且至少有 `package/dist/index.js`（T16 坑：漏 `dist/` 的包无法加载） |
| pack→temp install→smoke | 同一 tarball：`pnpm add @deepseek-ai/dsh@0.1.1-rc.2 <tgz>` 到空目录再跑 register smoke | **REQUIRED** | 证明 pack 产物可被钉死宿主加载。复用 omp-runtime-linux-probe 的 pack→临时目录→smoke 模式，不改 omp workflow |
| 独立 Actions | 拟议名 `dsh-host-compat`（`.github/workflows/dsh-host-compat.yml`） | **pending** | **本 PR 未入库**。意图：`workflow_dispatch`；job `unit-pack` 红即停。有 `workflow` scope 后再推 YAML |
| 候选矩阵 | 拟议 job `advisory-dsh-matrix` | **advisory / pending** | **同一 pack tarball** × 候选 `dsh` 的 temp cell register smoke。**不**跑仓库全量 `test`（FU4 硬断言 `0.1.1-rc.2`，候选宿主会假红）。YAML 未入库前可在本机对候选宿主做同样 temp cell。矩阵绿 **不是** 唯一合主线门 |

前置（GHA，**YAML 本 PR 未入库**）：将来 runner 必须能按 lockfile 安装 `@deepseek-ai/dsh@0.1.1-rc.2`。若 GitHub 没有该 registry，入库后也不要把拟议 workflow 改成 `pull_request` 必绿；保持 `workflow_dispatch`。现在用本机命令。禁止为打通 CI 去 npm publish。

本地等价：

```bash
pnpm --filter @kunolu/dsh-sbtd test

pack_dir="$(mktemp -d)"
pnpm --filter @kunolu/dsh-sbtd pack --pack-destination "$pack_dir"
tgz="$(echo "$pack_dir"/kunolu-dsh-sbtd-*.tgz)"
tar tzf "$tgz" | grep -E '^package/dist/index\.js$'
```

`test` 已包含 `tsc`，pack 前不要跳过它。`dist/` 默认 gitignore，pack 依赖当场编译结果。

## 人工最少清单

**只抽检** `dsh web` 审批弹窗（T16 step3 类）。CLI / 单测能证的不要进人工：plugin list、`/sbtd`、`sbtd_validate` skip-and-explain、`sbtd_e2e` blocked。

逐步：

1. 本机 `dsh --version` 为 `0.1.1-rc.2`（评估新宿主时再换候选，但对照组仍钉 rc.2）。
2. 在仓库根执行上一节 pack；确认 tarball 含 `package/dist/`。
3. 同版本已装过必须先卸再装：

   ```bash
   dsh plugin --profile web remove @kunolu/dsh-sbtd
   dsh plugin --profile web add "$tgz"
   ```

   不要对同一版本直接 `add` 覆盖。不要用 registry `@next` 代替本轮 tarball（本指南不发 npm）。
4. 打开 `dsh web`，工作区指向含 `packages/.../src/` 的仓库（T16 用的是 `sbtd-plugins`）。
5. **无** `sbtd_plan` 时，对生产路径发起 write/edit，例如 `packages/dsh-sbtd/src/section.ts`。
6. 期望：`kind=ask` 审批弹窗，原因含「尚未 sbtd_plan，请先调用 sbtd_plan。」

不要用 `frontend/src` 当抽检路径。`classifyRel` 只把相对 cwd、以 `src/`、`app/`、`packages/` 开头且非 `.md` 的路径当 production；`frontend/src` 落在 `other`，不会弹 step3 问询。

## PASS / FAIL 判定

**PASS**（可进入决策树「兼容」支）：

- REQUIRED 单测 + FU4 smoke + pack 含 `dist/` 全绿。
- 人工弹窗抽检出现上述 `ask` 文案（发版前才强制；仅评估宿主、不发版时可记「人工未跑」）。
- advisory 矩阵失败 **不** 单独把 REQUIRED 打红。

**FAIL**：

- `tsc` / `node --test` 非 0。
- FU4 断言宿主版本不是 `0.1.1-rc.2`，或 `output.schema` 被拒 / `type` 变成数组。
- pack 没有 `package/dist/`（T16 坑）。
- 人工抽检：无弹窗、直接写成功、或对 `frontend/src` 误判为已覆盖生产路径。

## 发版 / 不发版决策树

```
REQUIRED 绿？
 ├─ 否 → 不发版。开适配 PR（schema / register / peer 行为），修到 FU4+单测绿，再谈 bump。
 └─ 是 → 候选宿主与钉 0.1.1-rc.2 行为是否兼容？
      ├─ 兼容 → 可不发版。只更新矩阵注释、本文件、必要时放宽 peerRange。包版本可停在 0.1.0-rc.1。
      └─ 不兼容 → 不发当前 tarball。适配 PR + 版本 bump 后再发。禁止只改文档假装兼容。

advisory 矩阵绿？
 ├─ 否 → 记录候选版本失败；不升 REQUIRED；不单凭矩阵红/绿合主线。
 └─ 是（需绿一段时间）→ 仍不是唯一合主线门。还要 PR 审查、本指南人工抽检（若发版）、以及既有 omp-* 门（与 dsh 独立）。
```

合主线：矩阵绿 ≠ 唯一门。dsh workflow 与 omp compatibility ledger / certification 互不替代。

## 故障排查

| 现象 | 先查 |
|---|---|
| GHA `pnpm install` 拉不下 `@deepseek-ai/dsh` | 预期。YAML 入库后保持 `workflow_dispatch`；现在用本机 lockfile 跑 `pnpm --filter @kunolu/dsh-sbtd test`。不要改 omp workflow。 |
| 单测绿但宿主拒 schema | 对照 `test/fu4-host-schema.test.mjs`；确认装的就是 `0.1.1-rc.2`，不是本机另一个 rc。 |
| pack 只有 `cordis.patch.yml` / `manuals/` | 没跑 `tsc` 或 `files` 漏 `dist/`。`package.json` 的 `files` 必须含 `dist/`。 |
| `dsh plugin add` 同版本无效果 | 先 `remove` 再 `add`。 |
| 抽检无弹窗 | 路径是不是 `frontend/src`；cwd 是不是仓库根；有没有已有 plan。 |
| 有人把本检查写进 `omp-compatibility-*` | 撤回。拟议独立文件是 `dsh-host-compat.yml`（本 PR **未入库**）。 |
