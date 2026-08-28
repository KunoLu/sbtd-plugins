# 云端 §4 发布 Gate 与认证 Command Surface 分离方案

状态：**时代 A 云端 §4 已绿，rc.13 已 HITL `--tag next`。** 认证仍非发布许可。不是 `certified`。
仓库：`KunoLu/KPi`
目标 Plugin：`@kunolu/omp-sbtd`
给定约束（本方案按用户事实处理，不在此验证 OMP 上游）：**OMP 18.0.0 及以后不再使用 bun。**

可执行步骤：

- 云端 §4（时代 A，已验证）：本文件第 12 节
- 本机 §4 TUI（可选对照）：[`omp-plugin-host-acceptance.md`](./omp-plugin-host-acceptance.md)
- 认证：[`omp-plugin-compatibility-certification-runbook.md`](./omp-plugin-compatibility-certification-runbook.md)

Actions 绿只授权同一 digest 的 HITL `next`。不得把 `eligible` 写成 `certified`。


---

## 1. 要解决什么

把两件事都放到 GitHub Actions，且对后续每一个 Plugin 版本可重复：

1. **§4 四命令 = 唯一 npm 发布运行时 Gate**（授权 `--tag next`）。
2. **Command Surface = 认证三 profile 之一**（只进 ledger，不授权 npm）。

同时收掉已经确认的坑：

- 不能用「本机 SHA-256 / `.tmp/*.tgz`」当 Actions 输入。
- 新 runner 上空 cache 撑不住现行 `bun install --offline`。
- 仅有 cache/integrity 清单 + `npm install --offline` **不可重复**：npm 的离线可重复契约是验证过的诊断 `package-lock.json` + `npm ci --offline`。
- 认证 cell 的 `installSubjectPlugin()`（`run-live-cell.ts`）硬编码 `bun install --ignore-scripts`。只改 §4、不改这里，则 OMP 18 的 Command Surface 仍绑 bun。
- OMP 18 弃 bun 之后，任何流水线若仍 spawn bun，17.x 与 18.x 会裂成两套安装器。


---

## 2. 非目标

- 不自动 `latest`，不覆盖已发布版本。
- 不把 Command Surface / 整次认证 run 当成发布许可。
- 不把本机已打的 rc.13 `2d39226e…` 送进云端当输入。
- 不在本方案里宣称 Windows、非钉死的 OMP 版本、或 `certified`。
- 不取消 publish 的 token / 2FA / 环境审批。
- 不把 OMP 18 塞进当前 peer `>=17.3.5 <18` 的 tarball。18 必须是 **新 Plugin 身份 + 加宽 peer** 之后的另一条矩阵。

---

## 3. 两条流水线，授权永不合并

```text
[A 发布流水线]  只回答：这份 tarball 能不能 next？
  main 不可变 commit
  → 只 pack 一次
  → 第 5 节安装器（离线、钉依赖）
  → 非交互四命令 + SHA-256 写入对照
  → status 钉 commit SHA + tarball digest + installerGeneration
  → 允许对同一 digest 执行 publish-omp-sbtd.sh --tag next

[B 认证流水线]  只回答：已发布 tarball 对某个精确 OMP 的公开兼容状态？
  已 published 的 target 入 catalog
  → omp-compatibility-certification
     同一安装器装 subject
     Runtime Capability + Command Surface + Host Event
  → ledger-validate
  → 合入 ledger（eligible / partially-verified / certified / …）
  失败不得 unpublish，也不得挡已经 §4 授权的发布
```

BDD 必须继续保持：`精确 tarball 四命令是所有 RC 的唯一 npm 发布兼容性 Gate`；认证 profile 不是发布输入。改的是 **四命令在哪执行**（本机 TUI → 受信 Actions），不是两套 Gate 合成一套。

---

## 4. 工件身份：只 pack 一次，钉 commit + digest

受信 `workflow_dispatch`（仅 `KunoLu/KPi` + `refs/heads/main`）：

1. Checkout **完整 commit SHA**（不可变 `main`）。
2. 在该 workflow **内** `pnpm --filter @kunolu/omp-sbtd build && pack` **恰好一次**。
3. 立刻计算 tarball 内容 SHA-256，上传 **这一份** artifact。
4. §4 job 只消费该 artifact，禁止再 pack、禁止读取 `.tmp/`、禁止按「输入 digest」去猜本地文件。
5. publish job 只许 `npm publish` **同一份** artifact 字节。digest 对不上则 fail closed。
6. commit status / attestation 的 subject 必须同时包含：
   - `sourceRevision` = 该 `main` commit
   - `pluginTarballSha256` = 该 artifact digest
   - 钉死的 OMP 精确版本（见第 6 节时代）
   - `installerGeneration`（见第 5 节）

本机偶然打出的包（例如当前 `2d39226e…`）只是开发者工作区产物。云端 Gate 一跑，身份以 **那次 workflow 打出的 digest** 为准。

---

## 5. 版本化安装器契约（§4 与认证共用）

现行有两处把 Plugin tarball 装进隔离目录，语义相同、实现分叉：

| 调用方 | 今天 |
|---|---|
| host-acceptance §4 | `bun install --ignore-scripts --offline` |
| `installSubjectPlugin()` ← `run-command-surface-cell.ts` 与 Host Event live cell | `spawn("bun", ["install", "--ignore-scripts"])`（**没有** `--offline`） |

诊断包形态都是 `file:$TARBALL` → 生产依赖 `zod@4.1.12`。这是 **Plugin 依赖安装**，不是启动 OMP。OMP 18 弃 bun 改变的是 Host 运行时；若安装器仍 spawn bun，发布 Gate 和 Command Surface 都会在 18 上失败。

**决定：一条版本化安装器契约，A（§4）和 B（认证三 profile 的 subject 安装）必须调用同一实现。**

契约（建议模块：`scripts/p0/install-subject-plugin.ts`，由 `installSubjectPlugin` 与 §4 job 共用）：

1. 输入：隔离目录、**安装器世代**（`npm-offline-v1`）、content-addressed npm cache、**npm 生成并校验过的诊断 `package-lock.json`**。
2. job 把 tarball 放到固定相对路径（例如 `$RUN_DIR/plugin.tgz`）。诊断 `package.json` 只有 `"@kunolu/omp-sbtd": "file:./plugin.tgz"`。禁止绝对路径 lock。
3. **禁止**把内容 SHA-256 手写进 lock 的 `integrity`。npm `integrity` 是 SRI（通常 `sha512-…`），必须由 npm 在该固定相对布局下生成。`pluginTarballSha256`（内容 SHA-256）在 lock **之外**单独记录并对照 tarball 字节。
4. pack 之后用同一相对布局让 npm 生成/刷新诊断 lock（可联网的受信 **lock 生成** job，与离线 §4 分开）。§4 / 认证只对这份 lock 跑 `npm ci --offline --ignore-scripts --no-audit`。禁止无 lock 的 `npm install --offline`。SRI 或 `pluginTarballSha256` 对不上则 fail closed。
5. 返回 `dist/extension.js`。禁止 `omp plugin link`，禁止 bun，禁止在 §4/认证 job 里联网。
6. 证据字段（§4 status 与认证 cell record 都要带）：
   - `installerGeneration`（`npm-offline-v1`）
   - `installerCacheSha256`
   - `packageLockSha256`
   - `pluginTarballSha256`（独立于 lock SRI）
   - 18 不得记录 bun 安装器。
7. Plugin 新增生产依赖 → 重新用 npm 生成诊断 lock 并刷新 cache。旧 lock/cache 对不上 fail closed。



本机手册在 Gate 搬家时改用同一契约。搬家完成前，本机现行 bun §4 仍有效；**认证 cell 在 18 矩阵出现前必须切走 bun**，否则时代 B 的 Command Surface 无法跑。

**Host 启动**始终用钉死 OMP 的官方 CLI 入口（17.x：`dist/cli.js`；18.x：非 bun 官方入口），**永远不用** `.bin/omp` shim，也 **不用 bun 去跑 OMP**。

---

## 6. 两个 Host 时代

### 6.1 时代 A — 当前 peer `>=17.3.5 <18`

| 项 | 规则 |
|---|---|
| §4 钉死的 OMP | **17.3.5** `dist/cli.js`（shebang 为 bun；§4 job 必须 pinned Bun，见第 12.2 节） |
| Plugin 安装 | 第 5 节 `npm-offline-v1`（§4 与 `installSubjectPlugin` 同一实现；**不得**用 bun 装 Plugin） |
| 认证矩阵 | catalog 里已 published 的 tarball × in-range 精确 17.x |
| OMP 18 | **out-of-range**。现有 `<18` tarball 不得拿去跑 18 |

Command Surface / Host Event 继续非交互四命令与 12 事件，但 subject 安装必须改走第 5 节。`spawn("bun")` 不得带进 18 矩阵。认证不是发布许可。

### 6.2 时代 B — OMP 18.0.0 起（不使用 bun）

必须先有 **新 Plugin tarball**（新 SemVer，peer 加宽到包含 18）。旧 `<18` 包永远 out-of-range。

| 项 | 规则 |
|---|---|
| §4 钉死的 OMP | 该 tarball 声明的精确开发 floor |
| Host 启动 | 该版本 OMP 的官方 CLI 入口（不是 bun，不是 17.3.5 的 cli.js） |
| Plugin 安装 | 同一 `npm-offline-v1`。evidence 出现 bun 则该 profile fail closed |
| 认证 | 新 published identity 入 catalog 后跑三 profile；Command Surface 只换 Host CLI，安装器不另起一套 |

17 与 18 不得共用一个 §4 job 矩阵行。

---

## 7. 推荐 workflow 形状

### 7.1 `omp-section4-publish-gate`（新，发布授权）

`workflow_dispatch` only，`refs/heads/main`。同一 run、同一 artifact：

1. **pack** — checkout 指定 `main` SHA；build+pack 一次；计算并记录 **独立的** `pluginTarballSha256`；upload tarball。
2. **lock-and-cache** — 固定相对布局放下该 tarball；**用 npm 生成**诊断 `package-lock.json`（SRI 不得手写）；按 lock 物化 cache artifact。lock 与 cache 必须一起交给 §4。
3. **section4** — 只下载 tarball + lock + cache；校验 tarball 的 `pluginTarballSha256`；第 5 节 `npm ci --offline`；启动 Host 前 SHA-256 清单；非交互四命令；`section-4-write-check=passed`。
4. **status** — subject = commit + `pluginTarballSha256` + 钉死 OMP + `installerGeneration` + `packageLockSha256`。
5. **publish** — workflow **没有** npm publish job。整次 run `success` 只授权对**该 run** 的 `omp-section4-pack` 做 HITL `docs/deploy/publish-omp-sbtd.sh --tag next`（第 12 节）。无审批则停在「已授权、未发布」。

失败不得 publish。四命令 JSON `outcome=passed` 但 write-check 失败 = 整次 Gate 失败。section4 失败不是认证 `incompatible`。



### 7.2 `omp-compatibility-certification`（已有，不改授权语义）

仍只对 **已 published** target。不依赖 §4 artifact 是否还在（retention 会过期）。

每个 **唯一** `pluginTarballSha256` 先跑 **lock-and-cache**（可联网、与 §4 的 job 2 同一脚本）：

1. 从 Registry 取出该精确 published tarball（或 admission 已核验的字节），放到固定相对路径 `plugin.tgz`。
2. **用 npm 生成**诊断 lock（SRI 不得手写），物化 cache。
3. 产出按 digest 键名的 lock+cache artifact。

随后每个 cell 只下载 **该 digest** 的 lock+cache+tarball，调用第 5 节 `npm ci --offline`。禁止 cell 里 spawn bun，禁止 cell 里联网安装。

`installSubjectPlugin` 改为第 5 节契约。cell evidence 增加 `installerGeneration` / `installerCacheSha256` / `packageLockSha256` / 独立的 `pluginTarballSha256`。未切换安装器前不得打开 18.x 矩阵行。

没有跨 workflow 的“§4 把 cache 交给认证”的硬依赖；两套流水线用 **同一脚本 + 同一 digest** 各自生成 lock。同一 digest 的 SRI 必须一致，否则 fail closed。

```text
§4 GHA 绿 →（HITL）next → 认证（先 lock-and-cache，再 Command Surface）
```


---

## 8. 手册与 BDD 必须先改

未改下列文件之前，7.1 即使绿了也只是额外证据：

- [`omp-plugin-host-acceptance.md`](./omp-plugin-host-acceptance.md) §3 / §4：唯一运行时发布验收改为 7.1；本机 TUI 改为可选对照；诊断安装改为第 5 节契约。明确禁止用认证 Command Surface 代替 §4。
- `plugins/omp-sbtd/features/p0-conformance-release.feature`：同一 Rule 的 When 改为受信 `omp-section4-publish-gate` 对 **该 digest** 通过。
- 认证 runbook：发布授权看 7.1；Command Surface / Host Event 的 bun 安装器替换为第 5 节，evidence 带 `installerGeneration`。

---

## 9. 仍然不是全自动

即使 7.1 / 7.2 都在 Actions 里：

| 仍要人 | 原因 |
|---|---|
| 派发 §4 / 认证（或保护环境） | 受信 `workflow_dispatch` + 部署保护 |
| npm token / 2FA / `--tag next` | 发布脚本与 registry 权限 |
| ledger 合入 | bot PR + validate status，不推 main |
| 加宽 peer、钉死新 OMP floor | 新产品身份，不是开关 |

后续 Plugin 版本「都能用这套自动化」，当且仅当：

1. 手册/BDD 已搬家；
2. 每次从新的 `main` commit pack 一次；
3. 诊断 `package-lock.json` 已验证，且 §4 / 认证都走 `npm ci --offline`（不是「只有 cache」或 `npm install --offline`）；
4. §4 与认证 **共用** 第 5 节安装器（`installSubjectPlugin` 不再 spawn bun）；
5. Host 使用该版本钉死的 OMP `dist/cli.js`（17.x）或 18 官方非 bun 入口。

缺第 3 或第 4 条就不能写「后续版本都能云端 §4 / 云端 Command Surface」。


---

## 10. 落地顺序

1. 确认本方案（诊断安装弃 bun、安装器契约共用、17/18 分时代）。
2. 改手册 + `.feature`（第 8 节）。
3. 实现第 5 节模块；`installSubjectPlugin` 改为调用它；§4 workflow 只 pack 一次并消费同一 cache（第 7.1 节）。
4. ~~用 workflow 自己打出的第一份 rc.13 digest 跑通 §4~~ **已完成**（第 12 节；digest `b0e1f133…28185`）。
5. ~~HITL `next`~~ **已完成**（`0.1.0-rc.13`，不得 `latest`）。

6. 认证 runbook（安装器已切换的 Command Surface）。
7. OMP 18：另开 Plugin SemVer + peer 加宽 + 新的钉死 Host；旧 `<18` 包保持 out-of-range。未完成第 3 步不得开 18 认证行。

---

## 11. 对当前仓库的含义

| 项 | 现状 |
|---|---|
| `@kunolu/omp-sbtd@0.1.0-rc.13` | Registry 已发布；`next` → `0.1.0-rc.13`；SHA-256 `b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185` |
| 云端身份 | 以绿 run `33052112414`（`main` `ae5a413`）的 pack 为准，不是本机 `2d39226e…` |
| 现行发布 Gate | 受信 `omp-section4-publish-gate`（第 12 节）；本机 TUI 为可选对照 |
| 时代 A subject 安装 | `npm-offline-v1`（`installSubjectPlugin` 与 §4 共用） |
| 17.x Host 启动 | 钉死 OMP 17.3.5 `dist/cli.js` + §4 job pinned Bun 1.3.14 |
| 认证 / ledger | 独立流水线；rc.13 发布 **不是** `certified` |

**grill-with-docs：** 未完整调用（发布/CI 工序设计，术语沿用已有手册）。
不是 `certified`。

---

## 12. 已验证路径：从 `main` dispatch §4 到 `--tag next`

时代 A 第一次绿门（2026-08-27）。后续 RC 重复此路径；换 commit 就会换 digest。

### 12.1 成功步骤

1. 只从 **已经合入 `origin/main` 的 SHA** 派发。feature 分支、未合入的 driver 修复，都不算这次 Gate。
2. 确认 `main` 含第 12.2 节四项修复（Bun、失败评分 artifact、plan notify 投影、Host-project write-check）。
3. 受信 dispatch：

```bash
gh workflow run omp-section4-publish-gate --repo KunoLu/KPi --ref main
```

4. 等 **整次 workflow `success`**。必须全绿：`guard`、`pack`、`lock-and-cache`、`section4`（四命令 **和** write-check）、`status`。
5. 记下 `run_id`、`headSha`、`pluginTarballSha256`。按 **该 run_id** 下载 artifact `omp-section4-pack`（唯一 `.tgz`）。
6. fail-closed 对照：

```bash
test "$(sha256sum "$TARBALL" | cut -d' ' -f1)" = "$EXPECTED_DIGEST"
```

`EXPECTED_DIGEST` 必须等于该 run 记录的 `pluginTarballSha256`。对不上则停，不得 publish。
7. 单独 HITL 发布（workflow 不发 npm）：

```bash
docs/deploy/publish-omp-sbtd.sh "$TARBALL" --tag next
```

脚本只接受 `@kunolu/omp-sbtd` prerelease 和 `next`。凭据来自仓库根 `.env` 的 `NPM_TOKEN=`，不入参数、日志或报告。
8. 手册第 6 节身份复核（只读）：`npm view @kunolu/omp-sbtd@$VERSION dist --json`；`npm pack` 到隔离目录且恰好一个 `.tgz`；下载件 SHA-256 = 本地 tarball；SHA-1 = `dist.shasum`；`sha512-…` = `dist.integrity`。任一项不定则停，**不得第二次 `npm publish` / retag**。
9. 发布后立刻 `npm view` 得到 E404 时：等待传播后再做第 8 步只读查询。这不是失败，也不是重发许可。

首个绿门事实（只描述这一次，不作为下一 RC 的身份）：

| 项 | 值 |
|---|---|
| workflow run | `33052112414` |
| `main` SHA | `ae5a413d80adf7b293c3f26435830d285cd02334` |
| tarball | `kunolu-omp-sbtd-0.1.0-rc.13.tgz` |
| SHA-256 | `b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185` |
| Host | OMP `17.3.5` `dist/cli.js` |
| installer | `npm-offline-v1` |
| `next` | `0.1.0-rc.13` |

### 12.2 失败 run 不得授权 `next`

失败 artifact `omp-section4-pack` **不是**可发布物。不要用失败 run 的 digest 去 `--tag next`。

| 现象 | 不是什么 | 根因 | 现契约 | Lesson |
|---|---|---|---|---|
| ~12s `DRIVER_EXIT_NONZERO` / `COMMAND_SURFACE_FAILED`；lock-and-cache 已绿 | 不是安装器失败 | 17.3.5 `dist/cli.js` 为 `#!/usr/bin/env bun`；§4 job 未装 Bun | 17.x Host job pinned Bun **1.3.14**（`oven-sh/setup-bun`）。Plugin 仍 `npm ci --offline`。major ≥18 不得装 Bun | `LESSON-20260827-section4-host-needs-bun` |
| Host 跑了数十秒，`outcome=failed`，日志没有评分 JSON | 不是「Host 起来了就能发」 | 失败未上传 `command-surface.json` | CLI JSON 带 `sbtdCommandRegistered` / `driverError` / UI / `sanitizationViolations` / `commands[]`；`if: always()` 上传 `omp-section4-command-surface` | `LESSON-20260827-section4-scored-failed-no-publish` |
| 四命令均 `contentValidated`，`sanitizationViolations: 1`；onboard plan `outputSha256` 为空串哈希 | 不是 Plugin 文案 bug，也不是放宽 sanitizer | driver 对 schema 通过的 plan `notify` 仍 `recordText`；passthrough/`targets` 带 `/home/runner/work/...` | `consumeNotifyMessage` 只留 `{digest, targetCount}`，不 `recordText`。非 plan 路径通知仍 fail-closed | `LESSON-20260827-section4-plan-notify-not-text` |
| 四命令 JSON `passed`，job 仍红：`unexpected project write: .../templates/project/gitignore.template` | 不是 Host 写了隔离 `project/` | write-check 用 `"/project/" in rel` | `is_unexpected_host_project_write` 只认 `host-run/<runId>/project/`，仅允许 `.omp/config.yml` | `LESSON-20260827-section4-write-check-host-project` |

对应修复必须先合 `main` 再 dispatch。未合入的 SHA 上再派发，只会重复同一失败。

其它硬规则（与上表同类，已在契约里）：

- Host 入口是包内 `dist/cli.js`，不是 `node_modules/.bin/omp`（`LESSON-20260826-omp-shim-host-identity`）。
- lock-and-cache 绿 ≠ §4 绿。
- 未受信 / 非 `main` dispatch：guard fail-closed。
- 认证 profile 失败不得 unpublish，也不得挡已经 §4 授权的发布。


