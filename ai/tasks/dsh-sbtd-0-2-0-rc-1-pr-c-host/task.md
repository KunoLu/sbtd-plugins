---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-pr-c-host
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "checking"
branch: feat/dsh-sbtd-0.2.0-rc.1-pr-c-host
created_at: '2026-10-18T20:35:53+08:00'
updated_at: '2026-10-19T01:37:49+08:00'
completed_at: null
---

# PR-C 宿主适配 + T0

omp 正在实现。范围见 PRD 行 C。

**首个 commit 必须回填 PRD 行 B：**
- PR: #96
- merge SHA: `609766b1d911f1a4597e5ee7117877d2238a548f`
- done time: `2026-10-18T20:35:02+08:00`
- 并将行 B status → done；行 C → in-progress + 本 task 路径

## 范围（锁定）
- V4 `kind:'dsh-sbtd'` 且识别兼容 `'plugin:dsh-sbtd'`
- runPreStep 保留 `startsRequestSeries`
- peerDependencies.dsh 与 engines.dsh 同范围，初始 `>=0.2.0-rc.2 <0.3.0-0`；T0 按锁退回则改 `>=0.2.1-rc.2 <0.3.0-0`
- devDep 精确钉 `@deepseek-ai/dsh@0.2.0-rc.2`（退回时改钉 0.2.1-rc.2）
- CI：`dsh-host-compat.yml` unit-pack 两行 REQUIRED（0.2.0-rc.2 + 0.2.1-rc.2），workflow_dispatch，红即停
- T0 判据：R1 Q6 B（npm 下限 ERESOLVE → 退 range；pnpm add 失败才算 T0 失败；peer 警告只记）；R2 Q1 A 两行矩阵双失败不发
- 不碰：bump/publish/CHANGELOG（PR-D/文档 PR）、手动改 ~/.omp

## Book Gate Plan
| Gate | 触发 | 状态 |
|---|---|---|
| book-legacy-change-safety | 改 hooks/宿主适配既有行为 | passed（characterized） |
| book-refactoring-pass | 改生产代码 | passed（proceed，no refactor needed） |
| book-release-readiness | 运行时/peer/CI 变更 | passed（ready） |
| TDD | kind / startsRequestSeries / peer 范围 | passed（red→green 记录如下） |
| ponytail-review | 非平凡生产 diff | passed（Lean already, net -0） |
| 独立 review | peer 安装契约 + 3 子系统 | passed（reviewer CLEAN, confidence 0.9） |

## 宿主事实（PR-C 执行期核实，源码证据）
- V4 = session format v4（dsh-session SESSION_FORMAT_VERSION=4）。V4 原生 admission 拒绝 `kind:'plugin'` wrapper（dsh-session-format-v3-to-v4 `source()`："format v4 message requires a producer-owned source kind"）。
- V3→V4 迁移把 `{kind:'plugin',plugin:'dsh-sbtd'}` 改写为 `{kind:'plugin:dsh-sbtd'}`（`producerKind()`：dsh-sbtd 不在 RENAMED/SAME_NAME 表 → `plugin:<name>`）。
- V4 `PreStepDecision.enter` 带 `startsRequestSeries?: true`（dsh-agent runtime-types.d.ts:98）；宿主自己的 pre-step listener 用 `...decision` 保留。
- 兼容检查：0.2.0-rc.2 只查 peerDependencies（semver includePrerelease:true）；0.2.1-rc.2 起 `engines.dsh` 单独决定、peers 被忽略（dsh-app-boot `unmetRequirements`）。两版本 range 必须一致 → peer 与 engines.dsh 写同范围。
- `tools/pre-execute` 决策词表 allow/ask/deny 不变（dsh-tools 0.2.0-rc.2 scheduler）。
- dist-tags：latest=0.2.0-rc.2，next=0.2.1-rc.2。

## TDD red→green
- Red（3 fail/301）：fu4 与 t3 import 缺 `isSbtdSource`/`LEGACY_SBTD_SOURCE_KIND`（SyntaxError）；t0 peer 断言 mismatch。改造前行为实证：`runPreStep` 丢 `startsRequestSeries`（preserved=false）、notice source 为退役 wrapper `{"kind":"plugin","plugin":"dsh-sbtd"}`。
- Green：`pnpm --filter @kunolu/dsh-sbtd test` 335/335（tsc + node --test；基线 332 + 净增 3：startsRequestSeries、isSbtdSource、fu4 真实宿主 pre-step）。

## T0 记录（R1 Q6 B + R2 Q1 A）
- 包管理器：pnpm 11.17.0（corepack，COREPACK_HOME=$HOME/.cache/corepack；裸 cell 无 packageManager 字段时 corepack 幻影 pnpm 12.14.0，cell 已钉 `packageManager: pnpm@11.17.0`）；node v22.20.0；npm 10.9.3。
- strict-peer-dependencies：未设置（pnpm 11 默认 false），cell 无 .npmrc；npm 为默认严格 peer 解析。
-  tarball：`pnpm --filter @kunolu/dsh-sbtd pack` → kunolu-dsh-sbtd-0.1.0-rc.3.tgz（含 package/dist/index.js，T16 无回归）。
- 行 0.2.0-rc.2（REQUIRED）：cell `pnpm add @deepseek-ai/dsh@0.2.0-rc.2 <tarball>` exit 0，无 peer 警告；register smoke exit 0（九工具 + sbtd section + /sbtd + output.schema + pre-step notice kind=dsh-sbtd/startsRequestSeries 保留 + 无 plan 生产 write ask）。
- 行 0.2.1-rc.2（REQUIRED）：同上，exit 0 / smoke exit 0。
- npm 下限探测：`npm install @deepseek-ai/dsh@0.2.0-rc.2 <tarball>` exit 0，无 ERESOLVE → 不退 range。
- npm 跨 patch rc 记录：`npm install @deepseek-ai/dsh@0.2.1-rc.2 <tarball>` exit 1 ERESOLVE（npm 默认不带 includePrerelease 的已知坑）→ 按锁只记，留 PR-D 写 CHANGELOG 部署边界，不触发退回。
- 判定：保留 `>=0.2.0-rc.2 <0.3.0-0` + devDep 精确钉 0.2.0-rc.2（无退回）。
- 额外尝试（不计入判据）：真实 `dsh plugin --profile t0prc add <tarball>` 在沙箱 HOME 下首次被 corepack 幻影 pnpm 阻断，修正 PATH 后 exit 0 但 profile 无变动，结论 inconclusive；锁定机制是 host-compat 的 pnpm add（已绿）。人工最少项 dsh web ask 未执行（需交互宿主，留人工）。

## 验证
- `pnpm --filter @kunolu/dsh-sbtd test`：335/335 绿。
- `pnpm install --frozen-lockfile`：干净（CI 同路径）。
- `pnpm lint`（biome 2.3.15）：base commit 同样红（全仓 formatter drift，无 CI lint 门禁）；PR-C 变更文件违规类别与 base 完全一致，未新增。
- 根 `pnpm test`：omp-sbtd 既有环境性失败（bun --offline 全局缓存缺 zod/pi-coding-agent manifest；该文件 a5e0220 后未动；单跑同失败），与 PR-C 机制无关；dsh-sbtd 包全绿。用户承担该残余风险。
- BDD：features/t3-hooks-gate.feature 同步 V4 kind + startsRequestSeries + isSbtdSource 场景（中文场景+英文关键词，可追溯到 t3 测试）。t0/t1 feature 的 README 钉保持不变（README 按锁不动，留给文档 PR）。
- 独立 review（reviewer 子代理）：CLEAN，五面无 finding；其残余项（0.2.1-rc.2 waterfall 字段保留）已被 T0 行 2 真实宿主 smoke 覆盖。

## 文件
- packages/dsh-sbtd/src/hooks.ts（SBTD_SOURCE_KIND/LEGACY_SBTD_SOURCE_KIND/isSbtdSource、spread 保留、notice kind 切换、删孤儿 PLUGIN_NAME）
- packages/dsh-sbtd/src/index.ts（导出三符号）、src/commands/sbtd.ts（结构匹配注释版本刷新）
- packages/dsh-sbtd/package.json（peer/engines.dsh 同范围 + devDep 钉 0.2.0-rc.2）、pnpm-lock.yaml
- packages/dsh-sbtd/test/{t3-hooks,t0-stub,fu4-host-schema}.test.mjs、features/t3-hooks-gate.feature
- .github/workflows/dsh-host-compat.yml（unit-pack 拆 pin-smoke 两行 REQUIRED 矩阵）、.github/workflows/scripts/dsh-host-register-smoke.mjs（pin 参数化 + 完整 A 清单）

## 剩余风险 / 交接
- README 仍描述已发布 0.1.0-rc.3（pair dsh 0.1.1-rc.2），对 npm 现状为真；0.2 安装文档归文档 PR（PRD 行 D）。
- CHANGELOG 部署边界（npm 跨 patch rc ERESOLVE）归 PR-D。
- dsh-host-compat.yml 为 workflow_dispatch，合并后需人工触发一次取 CI 双行绿。

## 状态事件
| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-18T20:35:53+08:00 | planned | in-progress | PR-C 开发开始（首个 commit 回填 PRD 行 B） | 7b5ba89 |
| 2026-10-19T01:37:49+08:00 | in-progress | checking | 实现+T0+门禁完成，进入交付（commit/push/PR） | 本文件「T0 记录」「验证」节 |
