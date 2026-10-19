# omp-sbtd 0.2.0-rc.1 升级方案（PRD）

> 状态：grill Round 1 已全部锁定（D1–D13；用户 2026-10-19 11:39/11:43/11:44，Asia/Shanghai）；DDD draft 已修复 Reviewy Boundary Review R1 全部 findings（2026-10-19），待用户确认后转 confirmed
> 日期：2026-10-19（Asia/Shanghai）
> strict 任务记录：`ai/tasks/omp-sbtd-0-2-0-rc-1-prd/task.md`

---

## 0. 元信息

| 项 | 值 |
|---|---|
| 版本 | `@kunolu/omp-sbtd@0.2.0-rc.1`（当前 `0.1.0-rc.14`） |
| 发布通道 | 只发 npm dist-tag `next`；`latest` 不动（实测仍 `0.1.0-rc.2`，`next=0.1.0-rc.14`） |
| 基线 | 分支 `docs/omp-sbtd-0.2.0-rc.1-prd`，基于 main `4f7388c` |
| 上游钉（目标） | 640-skills `v2.0.2` / `1d82494d74f6df9bca7dccef2da409f87091883e` |
| 上游钉（现状） | `upstream.lock.json` resolvedRevision `f8aa0d7225a26c5e00b81d2f1b05121108e63630`（v1.0.13），transformVersion `p0-v3`，sourceId `sbtd-workflow-kit-upstream` |
| 嵌入模板分叉（现状） | `kit/AGENTS.project-root.md` 钉 `4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb`；`kit/AGENTS.project-omp.md` 钉 `f8aa0d7…` |
| omp 宿主范围 | 现状：peerDependencies `@oh-my-pi/pi-coding-agent: >=17.3.5 <18`；devDep 精确钉 `17.3.5`；无 `engines` 字段（本 RC 不新增）。宿主 latest 实测 `18.12.2`，本机 `omp --version` 实测 `omp/18.11.1`（均在现行 range 之外）。D11 目标：peer `>=18 <19`（17.x 不再支持）、devDep 精确钉 `18.11.1` |
| 发布形态 | annotated tag `omp-sbtd-v0.2.0-rc.1` + 双语（EN/ZH）GitHub prerelease |
| 版本号说明 | 0.x 的 minor 表示 breaking：本版删除 `packages/sbtd-workflow-kit`（`private: true`，从未发布 npm）并把上游从 v1.0.13 升到 v2.0.2 |

## 1. 背景与目标

`packages/sbtd-workflow-kit` 是私有构建期包，承载 640-skills 上游的同步（sync-upstream）、OMP/agent-plugin 投影（projection）、生成校验（check-generated）；`packages/omp-sbtd` 通过 workspace devDep 消费其 `generated-omp` 产物并 embed 进自己的 `kit/`。本版按 D1 把投影/生成逻辑迁入 `packages/omp-sbtd`、删除 kit 包（供应链身份不变，同步方式对齐 dsh-sbtd），随后按 D3 把上游从 v1.0.13 同步到 v2.0.2（`scripts/` 1→33 个 `.py`、新增 5 个 Python 依赖、`assets/`、两个 schema json、`sbtd-task` 模板），再完成插件适配、双语 CHANGELOG 与发版。

## 2. 已锁定决策（用户 2026-10-19，status: locked）

| # | 决策 | 状态 |
|---|---|---|
| D1 | sbtd-workflow-kit option B：sync 脚本、transform 与 overlays 迁入 `packages/omp-sbtd/scripts/` 与 `packages/omp-sbtd/upstream/`；版本钉（`upstream.lock.json`）与 manifest 记录进插件内；然后整体删除 `packages/sbtd-workflow-kit`（sync upstream 方式对齐 dsh-sbtd）；sourceId `sbtd-workflow-kit-upstream` 不变；`scripts/`/`upstream/` 内部确切子布局与 `docs/spec/sbtd-workflow-kit/` 落点按 D10（grill-r1 Q3 已锁定） | locked（用户 2026-10-19） |
| D2 | 顺序：先迁移，后同步 | locked（用户 2026-10-19） |
| D3 | 上游钉 640-skills `v2.0.2`（`1d82494d74f6df9bca7dccef2da409f87091883e`） | locked（用户 2026-10-19） |
| D4 | npm 只发 dist-tag `next`；`latest`（`0.1.0-rc.2`）不动 | locked（用户 2026-10-19） |
| D5 | 发布：annotated tag `omp-sbtd-v0.2.0-rc.1` + 双语（EN/ZH）GitHub prerelease | locked（用户 2026-10-19） |
| D6 | 插件目录的中文 README 文件名用 `README_zh.md`（同仓库根 `README_zh.md` 先例），不用 `README.zh.md` | locked（用户 2026-10-19） |
| D7 | grill-r1 Q6 A：zh README 语言切换链接钉 release tag 绝对链接（`blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md`），打 tag 后、publish 前点击核验；`README_zh.md` 不进 npm 包；`package.json` files 与 p0 发布物清单不变，任务 A 字节级 CLEAN 门不受影响 | locked（用户 2026-10-19 11:39） |
| D8 | grill-r1 Q1 A：随包发布 `requirements.txt`（5 个钉版依赖）；需要依赖的入口执行前隔离预检，不自动 pip install；upgrade 与 migration 路径缺任一依赖即中止（对齐上游 fail-closed）；任何验签路径缺 cryptography 一律拒绝运行；只有明确列出的普通入口才可降级 skipped（当前清单：无） | locked（用户 2026-10-19 11:43） |
| D9 | grill-r1 Q2 A：`scripts/` 33 个 `.py` 全部 include；`assets/` 与两个 schema json 逐文件审，按「OMP 投影是否有消费方」逐个 include/omit 并逐条记录 reason（`requirements.txt` 不在逐文件审清单：D8 已锁定随包发布）；`sbtd-task` 模板 8 文件随模板树收录 | locked（用户 2026-10-19 11:43） |
| D10 | grill-r1 Q3 A：`packages/omp-sbtd/scripts/` 放薄入口 CLI 包装（与既有 `scripts/embed-kit.mjs`、`scripts/p0/` 并列）；投影/生成实现与供应链资产全部进 `packages/omp-sbtd/upstream/`（`src/`、`vendor/`、`omp-distribution-map.yaml`、`overlays/`、`omp-overlays/`、`upstream.lock.json`、`features/`、`test/`）；投影产物仍先出 `generated-omp/` 再经 embed-kit 拷入 `kit/`（发布物布局不变）；`docs/spec/sbtd-workflow-kit/{backend,frontend}` 移到 `docs/spec/omp-sbtd/kit/{backend,frontend}`（避免与既有 backend/frontend 撞名） | locked（用户 2026-10-19 11:43） |
| D11 | grill-r1 Q4（用户 11:44 选定 `>=18 <19`，替代原推荐 B）：peerDependencies `@oh-my-pi/pi-coding-agent` 升为 `>=18 <19`（17.x 不再支持）；devDependency 精确钉 `18.11.1`（对齐真实宿主 smoke 版本）；omp 18.11.1 真实宿主 smoke 为 HARD GATE、无退路——任务 C 验收项、任务 E（发布）前置，失败则修到通过，不退回旧 range；任务 D 双语 CHANGELOG 须带 **Breaking** 条目（EN: "No longer supports omp 17.x; tested only on 18.11.1; upstream latest is 18.12.2"；ZH: 「不再支持 omp 17.x；只在 18.11.1 上实测过，上游最新是 18.12.2」）；任务 R README 兼容说明同步更新；omp 18 升级（peer 改 `>=18 <19`、devDep 钉 `18.11.1`、对应 `pnpm-lock.yaml` 更新、按 18.11.1 API 重跑 typecheck 与全部测试、18.11.1 真实宿主 smoke 硬门）由行 C 独占执行，行 A/B 不触碰 peer/devDep omp 范围及相关 lockfile 条目 | locked（用户 2026-10-19 11:44） |
| D12 | grill-r1 Q5 A：ROADMAP 归档为 `docs/legacy-archive/kpi-roadmap-0.7-draft-2026-07-21.md`（版本与日期取自文档自身头部）；同步更新 `packages/omp-sbtd/validation/p0/conformance-matrix.v1.json` 的 53 条 `source.path` | locked（用户 2026-10-19 11:43） |
| D13 | grill-r1 Q7 是：执行 dsh-sbtd 行 G（`docs/prd/dsh-sbtd-0.2.0-rc.1.md`）——双语 README + 仅文档 `0.2.0-rc.2` 发布（annotated tag `dsh-sbtd-v0.2.0-rc.2`、双语 prerelease、`npm publish --tag next`、`latest` 不动）；独立 PR、独立 release；不进入本 PRD 任务表，行 G 状态由「推荐，待用户确认」改为 planned | locked（用户 2026-10-19 11:43） |

## 2.1 DDD（draft）

> 状态：draft，已反映 Round 1 锁定（D7–D13）与 Reviewy Boundary Review R1 findings 修复（2026-10-19，修订日志 R3）。grill Round 1（`ai/tasks/omp-sbtd-0-2-0-rc-1-prd/grill-r1.md`）已全部锁定（用户 2026-10-19 11:39/11:43/11:44）；经用户确认后本节改为 confirmed 摘要。

- 限界上下文：omp 宿主（版本范围是本插件的对外声明，按 D11 升为 `>=18 <19`，17.x 放弃，唯一实测点 18.11.1；适配 18.x 是行 C 的工作：peer/devDep/lockfile 升级、按 18.11.1 API 重跑 typecheck 与测试、真实宿主 smoke 硬门均归行 C）/ omp-sbtd 插件（随包 `requirements.txt`，Python 依赖按 D8 fail-closed 预检）/ kit 投影管线（迁移后并入 omp-sbtd，布局按 D10）/ 640-skills 上游供应链 / p0 验证与 conformance / npm 发布通道。
- 关键术语：迁移（D1 纯搬移 + CLEAN 门）≠ 同步（任务 B 升钉）；sourceId `sbtd-workflow-kit-upstream` 是供应链身份，迁移与同步均不变；distribution map 逐文件 include/omit/replace-with-overlay；CLEAN 门 = 嵌入 `kit/`、`skills/`、manifest 哈希、pack 清单与逐文件 sha256 对 `4f7388c` 构建完全一致（唯一例外：package.json 恰好两处编辑——删 kit devDep、scripts.build 仅替换 kit check-generated 调用为包内入口，peer/devDep/files/version 不变——与根 `pnpm-lock.yaml` 的 kit workspace 包移除；详见行 A）；回填 = 每个 PR 首 commit 回填上一行。
- 草案全文见 grill-r1.md 末节。

## 3. 任务表

规则（锁定）：

- 每个任务都用 strict 模式；每个任务开工前新建对应 strict 任务记录。
- 每个 PR 的第一个 commit 回填**上一行**的 PR、merge SHA 与 done 时间（Asia/Shanghai +08:00，以 merge commit 时间记）；行 F 回填行 E。
- Reviewy 对 PR tip 评审 CLEAN 后由 Lord squash-merge；合并后删除本地与远程任务分支。
- 每完成一行更新本表状态。

| 序号 | 任务 | 优先级 | 状态 | PR | merge SHA | done 时间 | strict 任务记录路径 |
|---|---|---|---|---|---|---|---|
| 0 | grill + DDD（本任务） | 1 | in-progress（grill R1 已锁定；DDD Boundary Review 待 Reviewy） | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-prd/task.md` |
| A | 迁移 kit 进 omp-sbtd 并删除 `packages/sbtd-workflow-kit`。Move only：`upstream.lock.json` revision 与 `transformVersion=p0-v3` 不变、sourceId `sbtd-workflow-kit-upstream` 不变。CLEAN 门：嵌入 `kit/`、`skills/`、manifest 哈希、`npm pack --dry-run` 文件清单及逐文件 sha256 与 `4f7388c` 构建完全一致——唯一例外（实测 `4f7388c:packages/omp-sbtd/package.json`）为 package.json 恰好两处编辑：(a) 删除 devDependency `"@kunolu/sbtd-workflow-kit": "workspace:*"`（4f7388c 第 47 行）；(b) `scripts.build` 中仅把 `pnpm --filter @kunolu/sbtd-workflow-kit check-generated`（4f7388c 第 62 行）替换为插件包内新入口；package.json 其余字段全部不变（peerDependencies `@oh-my-pi/pi-coding-agent: >=17.3.5 <18`、devDep omp 精确钉 `17.3.5`、`files`、`version` 等），根 `pnpm-lock.yaml` 变更预期且仅限移除该 workspace 包；除此之外 `kit/`、`skills/`、manifest 哈希、pack 清单与每个其他文件 sha256 均与 `4f7388c` 构建完全一致；check-generated、p0 validator、SBOM、全部测试绿；`docs/spec/sbtd-workflow-kit/` 路径与 conformance matrix 路径同 PR 更新；运行时 zod（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）、p0 `cli.ts` kitRoot、`release-validator.ts`、`write-sbom.ts` 同步更新 | 2 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-a-migrate-kit/task.md` |
| B | 同步上游到 `1d82494`：对 distribution map 的每个新文件逐个决定收录；统一两个嵌入 AGENTS 模板的上游版本（现 `4222b15` 与 `f8aa0d7` 分叉）；重新生成 third-party notices | 3 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-b-sync-upstream/task.md` |
| C | 插件适配 v2.0.2 与 omp 18：独占执行 D11 宿主升级——peerDependencies `@oh-my-pi/pi-coding-agent` 改 `>=18 <19`、devDependency 精确钉 `18.11.1`、`pnpm-lock.yaml` 相应更新、按 18.11.1 API 重跑 typecheck 与全部测试；验收含 omp 18.11.1 真实宿主 smoke PASS（D11：HARD GATE、无退路，是行 E 发布前置；失败则修到通过） | 4 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt/task.md` |
| D | 双语 CHANGELOG（`CHANGELOG.md` EN + `CHANGELOG.zh.md` ZH，一一对应、最新在前）；须带双语 **Breaking** 条目（D11）：EN "No longer supports omp 17.x; tested only on 18.11.1; upstream latest is 18.12.2"／ZH 「不再支持 omp 17.x；只在 18.11.1 上实测过，上游最新是 18.12.2」 | 5 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-d-changelog/task.md` |
| R | 双语 README（仅根 + omp-sbtd；dsh-sbtd README 不在本 PRD，见 `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G）：更新根 `README.md` 与 `README_zh.md` 到两个插件最新版本；`packages/omp-sbtd/README.md` 改 EN 默认 + 新增 `packages/omp-sbtd/README_zh.md`（D6 命名），两者顶部互相语言切换链接；链接按 D7 钉 `blob/omp-sbtd-v0.2.0-rc.1/packages/omp-sbtd/README_zh.md` 绝对链接，`README_zh.md` 不进包，`package.json` files 与 p0 发布物清单不变，任务 A 字节级 CLEAN 门不受影响；兼容说明按 D11 更新（peer `>=18 <19`，17.x 不再支持，实测 18.11.1，上游 latest 18.12.2） | 6 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-r-readme/task.md` |
| E | bump `0.2.0-rc.1`、annotated tag `omp-sbtd-v0.2.0-rc.1`、双语 GitHub prerelease、`npm publish --tag next`；打 tag 后、publish 前点击核验 README 语言切换链接（D7 闭环步骤）；前置：行 C 的 omp 18.11.1 真实宿主 smoke 已 PASS（D11 硬门，不通过则不发） | 7 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-pr-e-release/task.md` |
| F | 回填 PRD 行（行 E 的 PR、merge SHA、done 时间与 publish/tag 证据） | 8 | planned | — | — | — | `ai/tasks/omp-sbtd-0-2-0-rc-1-prd-f-backfill/task.md` |

> 独立 chore（不在主序列）：`git mv docs/prd/ROADMAP.md docs/legacy-archive/`（文件名按 D12 锁定：`kpi-roadmap-0.7-draft-2026-07-21.md`）并同步更新 `packages/omp-sbtd/validation/p0/conformance-matrix.v1.json` 的 53 条 `source.path`；p0 validator 与测试全绿。ROADMAP.md 头部实测为「文档版本 0.7-draft／文档日期 2026-07-21」。

## 4. 验收要点

- **任务 A CLEAN 门**（引用锁定，不复制）：嵌入 `kit/`、`skills/`、manifest 哈希、`npm pack --dry-run` 文件清单与逐文件 sha256 全部等于 `4f7388c` 构建；唯一例外为 package.json 恰好两处编辑（删 `@kunolu/sbtd-workflow-kit` devDep；`scripts.build` 仅把 kit check-generated 调用替换为包内新入口，peer/devDep omp 钉与 `files`/`version` 不变）与根 `pnpm-lock.yaml` 的 kit workspace 包移除（详见行 A）；check-generated、p0 validator、SBOM、全部测试绿；路径更新（`docs/spec/sbtd-workflow-kit/`、conformance matrix、zod 两处、`cli.ts` kitRoot 4 处、`release-validator.ts`、`write-sbom.ts`）与搬移同 PR。
- **任务 B 收录决策**（D9）：v2.0.2 diff 实测 229 文件变更（67 新增 / 107 删除 / 53 修改）；`scripts/` 33 个 `.py` 全 include；`assets/` 与两个 schema json 逐文件 include/omit 并逐条记录 reason（`requirements.txt` 由 D8 锁定随包发布，不在逐文件审清单）；AGENTS 模板统一到 `1d82494`；third-party notices 重新生成。
- **任务 C 宿主 smoke 硬门**（D11）：omp 18.11.1 真实宿主 smoke（插件加载、工具/hooks 注册、onboard 冒烟）PASS 是行 C 验收项、行 E 发布前置；失败则修到通过，无退回旧 range 的退路。
- **任务 D Breaking 条目**（D11）：双语 CHANGELOG 必须含 **Breaking**：EN "No longer supports omp 17.x; tested only on 18.11.1; upstream latest is 18.12.2"；ZH 「不再支持 omp 17.x；只在 18.11.1 上实测过，上游最新是 18.12.2」。
- **供应链身份不变量**：sourceId `sbtd-workflow-kit-upstream`、transformVersion `p0-v3` 在任务 A 中不变；任务 B 只改 resolvedRevision 与 sourceTreeSha256。
- **发布**：`npm publish --tag next`；`latest` 保持 `0.1.0-rc.2`（发布后 `npm view` 实测核对）；annotated tag + 双语 prerelease。
- **任务 R README**：EN/ZH 内容一一对应；版本钉与宿主钉（`@kunolu/omp-sbtd@0.2.0-rc.1`、peer `>=18 <19`，D11）正确；`npm pack --dry-run` 清单含更新后的 `README.md`（npm 自动收录）且不含 `README_zh.md`（D7：files 与 p0 清单不变）；语言切换链接在任务 E 打 tag 后、publish 前点击核验。

## 5. 非目标

- 不 bump `latest`（仍 `0.1.0-rc.2`）。
- 任务 A 不改任何投影/生成逻辑、不改上游钉（Move only）。
- 任务 A 与 B 不触碰 omp 宿主版本声明：`peerDependencies` 的 omp range（`>=17.3.5 <18` → `>=18 <19`）、devDependency `17.3.5` → `18.11.1` 及相关 `pnpm-lock.yaml` 条目均属行 C（D11）。
- 不为 omp 17.x 保留支持（D11：peer 锁定 `>=18 <19`，devDep 钉 `18.11.1`）；engines 字段本 RC 不新增。
- 不在主序列内执行 ROADMAP 归档 chore（文件名按 D12 锁定）。
- dsh-sbtd 的双语 README 不在本 PRD 任务表（D13 已确认执行，见 `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G，独立 PR、独立 release）。
- 不自动 pip install Python 依赖（D8 fail-closed：预检失败即结构化拒跑；验签缺 cryptography 拒跑；允许降级 skipped 的普通入口当前为无）。

## 6. 修订日志

| 日期 | 修订 | 内容 |
|---|---|---|
| 2026-10-19 | R1b | D1 写明目标布局（`scripts/` + `upstream/`，钉与 manifest 进插件，sourceId 不变）并据此收窄 Q3；新增锁定 D6（插件目录用 `README_zh.md`）；任务表插入行 R（双语 README，D 后 E 前，E/F 优先级顺延）；grill 新增 Q6（语言切换链接与打包，推荐 A 待确认）、Q7（dsh-sbtd 行 G 是否执行，推荐 A 待确认）；Q1 按上游 v2.0.2 fail-closed 实测重写（推荐 A：预检失败拒绝运行）；Q4 补充 `omp --version` 实测 `omp/18.11.1` 事实并改推荐 B（扩 range 含 18.x）；`docs/prd/dsh-sbtd-0.2.0-rc.1.md` 追加行 G（推荐，待用户确认） |
| 2026-10-19 | R2 | grill Round 1 全部锁定并回填：新增锁定 D7（Q6 A，用户 11:39）、D8（Q1 A）、D9（Q2 A）、D10（Q3 A）、D12（Q5 A）、D13（Q7 是，dsh 行 G 转 planned）（均用户 11:43）；D11（Q4，用户 11:44 选定 `>=18 <19`，替代原推荐 B：devDep 精确钉 18.11.1，omp 18.11.1 真实宿主 smoke 为无退路 HARD GATE，行 E 前置；任务 D 双语 **Breaking** 条目、任务 R 兼容说明同步）；行 0/C/D/R/E、验收要点、非目标、元信息宿主范围同步更新；DDD draft 更新为反映锁定、待 Reviewy 独立 Boundary Review；`docs/prd/dsh-sbtd-0.2.0-rc.1.md` 行 G 状态改 planned |
| 2026-10-19 | R3 | 修复 Reviewy DDD Boundary Review R1 findings：行 A 字节级 CLEAN 门例外精确化（实测 `4f7388c:packages/omp-sbtd/package.json`：唯一例外为两处编辑——删第 47 行 devDep `@kunolu/sbtd-workflow-kit`、第 62 行 `scripts.build` 仅替换 kit check-generated 调用为包内入口；peerDependencies `>=17.3.5 <18`、devDep omp `17.3.5`、`files`、`version` 均不变；根 `pnpm-lock.yaml` 变更仅限移除该 workspace 包）；omp 18 升级（peer/devDep/lockfile、按 18.11.1 API 重跑 typecheck+测试、18.11.1 真实宿主 smoke 硬门）明确为行 C 独占，行 A/B 非目标新增不触碰，D11 与 DDD 同步；D9 与行 B 逐文件审清单移除 `requirements.txt`（D8 已锁随包，保留 `assets/` 与两个 schema json）；DDD omp 宿主上下文措辞改为「版本范围是插件对外声明，适配 18.x 是行 C 的工作」；task.md 去除 stale「不 commit/push/开 PR」（PR #102 已开）、任务序列补行 R、验收改 D1–D13 并追加状态事件 |
