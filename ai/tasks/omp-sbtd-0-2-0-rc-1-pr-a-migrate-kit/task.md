---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-a-migrate-kit
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-19 13:42 +08:00 批准「开始 A 行」
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-a-migrate-kit
created_at: '2026-10-19T13:44:27+08:00'
updated_at: '2026-10-19T15:14:38+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 A：迁移 kit 进 omp-sbtd 并删除 packages/sbtd-workflow-kit

## 目标

按 `docs/prd/omp-sbtd-0.2.0-rc.1.md` 行 A（L65）执行 Move only 迁移：把 `packages/sbtd-workflow-kit` 的投影/transform 代码迁入 `packages/omp-sbtd/scripts/`（薄入口 CLI 包装）与 `packages/omp-sbtd/upstream/`（`src/`、`vendor/`、`omp-distribution-map.yaml`、`overlays/`、`omp-overlays/`、`upstream.lock.json`、`features/`、`test/`，布局按 D10），然后整体删除 `packages/sbtd-workflow-kit`。

## 范围

- 迁入：`packages/omp-sbtd/scripts/` 薄入口 + `packages/omp-sbtd/upstream/` 供应链资产与实现；`docs/spec/sbtd-workflow-kit/{backend,frontend}` → `docs/spec/omp-sbtd/kit/{backend,frontend}`。
- 同 PR 更新（行 A 点名）：
  - `packages/omp-sbtd/package.json` 恰好三处编辑：(a) 删 devDep `"@kunolu/sbtd-workflow-kit": "workspace:*"`；(b) `scripts.build` 仅把 `pnpm --filter @kunolu/sbtd-workflow-kit check-generated` 替换为包内新入口；(c) 新增 devDep `"yaml": "2.8.2"` 精确钉（build-time only，不进 dependencies）。
  - `packages/omp-sbtd/SBOM.spdx.json` 仅移除 kit 包条目（SPDXID `SPDXRef-Package-kunolu-sbtd-workflow-kit`）与 relatedSpdxElement 指向它的那一条 relationship，其余逐字节等于 `4f7388c` 构建；行 A 不把迁入代码在 SBOM 中改归属 omp-sbtd。
  - 根 `pnpm-lock.yaml` 仅移除 kit workspace 包 importer 并把 yaml importer 条目从 kit 移到 omp-sbtd。
  - `scripts/p0/write-sbom.ts`（第 13–16 行 kitRoot / env `KPI_SBOM_KIT_ROOT`）与 `scripts/p0/release-validator.ts`（第 4320 行 kitSpdxId、第 4428 行 `join(kitRoot,"package.json")`）停止生成/期待 kit 包节点与其 relationship。
  - 运行时 zod（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）、p0 `cli.ts` kitRoot 4 处、`conformance-matrix.v1.json` 第 835/1412 行 transform.test.ts 路径、`docs/spec/sbtd-workflow-kit/` 路径。
  - 对比脚本写在本任务文件夹并随 PR 提交。

## 非目标（行 A 明确）

- 不改任何投影/生成逻辑；`upstream.lock.json` revision 与 `transformVersion=p0-v3` 不变；sourceId `sbtd-workflow-kit-upstream` 不变（任务 B 才升钉）。
- 不触碰 omp 宿主版本声明：peerDependencies `>=17.3.5 <18`、devDep omp 精确钉 `17.3.5` 及相关 lockfile 条目均归行 C（D11）；package.json 其余字段（`dependencies`/`files`/`version` 等）全部不变。
- SBOM 不把迁入代码改归属 omp-sbtd（如需改归属属行 B 或 C）。
- 不执行 ROADMAP 归档 chore（D12 独立 chore）。
- 不 push、不开 PR。

## 验收（行 A CLEAN 门，逐字）

迁移 kit 进 omp-sbtd 并删除 `packages/sbtd-workflow-kit`。Move only：`upstream.lock.json` revision 与 `transformVersion=p0-v3` 不变、sourceId `sbtd-workflow-kit-upstream` 不变。CLEAN 门：嵌入 `kit/`、`skills/`、manifest 哈希、`npm pack --dry-run` 文件清单及逐文件 sha256 与 `4f7388c` 构建完全一致——例外恰为三处（实测 `4f7388c:packages/omp-sbtd/package.json` 与 `4f7388c:packages/omp-sbtd/SBOM.spdx.json`）：(1) package.json 恰好三处编辑：(a) 删除 devDependency `"@kunolu/sbtd-workflow-kit": "workspace:*"`（4f7388c 第 47 行）；(b) `scripts.build` 中仅把 `pnpm --filter @kunolu/sbtd-workflow-kit check-generated`（4f7388c 第 62 行）替换为插件包内新入口；(c) 新增 devDependency `"yaml": "2.8.2"` 精确钉（build-time only，不进 dependencies，发布 runtime deps 不变）；package.json 其余字段全部不变（peerDependencies `@oh-my-pi/pi-coding-agent: >=17.3.5 <18`、devDep omp 精确钉 `17.3.5`、`dependencies`、`files`、`version` 等）；(2) `packages/omp-sbtd/SBOM.spdx.json` 仅允许删除 kit 包条目（4f7388c 第 6195 行包 `@kunolu/sbtd-workflow-kit`，SPDXID `SPDXRef-Package-kunolu-sbtd-workflow-kit` 第 6196 行）与 relatedSpdxElement 指向它的那一条 relationship（4f7388c 第 8252 行），其余每个条目逐字节与 `4f7388c` 构建一致——行 A 不把迁入代码在 SBOM 中改归属 omp-sbtd（纯搬移）；(3) 根 `pnpm-lock.yaml` 变更预期且仅限：移除该 workspace 包的 importer 条目，并把 yaml importer 条目从 kit 包移到 omp-sbtd；除此之外 `kit/`、`skills/`、manifest 哈希、pack 清单与每个其他文件 sha256 均与 `4f7388c` 构建完全一致；check-generated、p0 validator、SBOM、全部测试绿；`docs/spec/sbtd-workflow-kit/` 路径与 conformance matrix 路径（`packages/omp-sbtd/validation/p0/conformance-matrix.v1.json` 第 835/1412 行 transform.test.ts 路径）同 PR 更新；运行时 zod（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）、p0 `cli.ts` kitRoot 同步更新；SBOM 生成器同 PR 修改（`write-sbom.ts` 第 13–16 行 kitRoot/env `KPI_SBOM_KIT_ROOT`；`release-validator.ts` 第 4320 行 kitSpdxId、第 4428 行 `join(kitRoot,"package.json")`——同 PR 更新两脚本停止生成/期待 kit 包节点与其 relationship；这两个脚本不在 package.json `files` 中，不影响 pack 身份。整个 tarball sha256 预期不同，不声称一致。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill 后 DDD 已在任务 0 执行（draft，Reviewy R1 findings 已修复） | 行 A 为纯搬移、无领域模型变更 | not-required（沿用任务 0 DDD） |
| book-ddia-data-design | 本任务稳固 lockfile/SBOM 资产归属，但行 A 明确定义为纯搬移、无新数据设计 | 行 A | not-required |
| book-legacy-change-safety | 删除既有包并改动构建管线，高回归风险；CLEAN 门字节级对比即安全网 | 行 A | passed（CLEAN 门 11×PASS + 全量测试/p0 validator 绿；唯一失败为基线同因环境性失败） |
| book-refactoring-pass | 首次修改既有生产代码（脚本路径与生成器）前 | 行 A | passed（搬移代码逐字节保留，仅路径/env 重命名；biome 全绿） |
| book-release-readiness | 本行不发布、不改 runtime 交付 | 行 A | not-required |

## 进度

- [x] 基线 worktree `4f7388c` 构建与 pack 逐文件 sha256 捕获（412 文件；`/workspace/.worktrees/baseline-4f7388c/`）
- [x] kit 代码迁入 omp-sbtd（scripts/ 3 个薄入口 + upstream/ + docs/spec 移动）
- [x] package.json 三处编辑、write-sbom.ts、release-validator.ts、cli.ts、conformance matrix、SBOM.spdx.json、pnpm-lock.yaml
- [x] 删除 packages/sbtd-workflow-kit
- [x] CLEAN 门对比（`compare-clean-gate.mjs`，本任务文件夹）+ 全量测试/lint/typecheck/p0 validator
- [ ] 移除额外 worktree；最终报告

## 验证证据

全部在分支 `feat/omp-sbtd-0.2.0-rc.1-pr-a-migrate-kit` 实测（COREPACK_HOME=/workspace/.worktrees/.corepack，pnpm 11.17.0，Node 22.20.0）：

- 基线构建：`/workspace/.worktrees/omp-sbtd-4f7388c`（detached `4f7388c`）`pnpm install --frozen-lockfile && pnpm --filter @kunolu/omp-sbtd build` → `generated output is current`，sourceTreeSha256 `f05806c0a00894a487b4361861770dc18791ab056b7404aa86685b96c711f176`；`npm pack` tarball sha256 `e811933a00614716720f8cfc64b971014304c4a080b3d5be05129a9c9a2f0184`（412 文件）。
- 分支构建：`pnpm --filter @kunolu/omp-sbtd build` → `generated output is current`，sourceTreeSha256 `f05806c0…f176`（与基线逐字节一致 → SBOM documentNamespace 一致），sbomSha256 `337d44b2…9c0`。
- CLEAN 门：`node ai/tasks/omp-sbtd-0-2-0-rc-1-pr-a-migrate-kit/compare-clean-gate.mjs --baseline …/baseline-4f7388c/kunolu-omp-sbtd-0.1.0-rc.14.tgz --candidate …/candidate-row-a/kunolu-omp-sbtd-0.1.0-rc.14.tgz` → **CLEAN GATE: PASS**：pack 清单 412 文件一致；逐文件 sha256 除 package.json 与 SBOM.spdx.json 外全同；嵌入 `kit/`（223 文件）、`skills/`（92 文件）、`kit/manifest.json` 哈希一致；package.json 恰好三处编辑（脚本断言 devDeps 仅删 kit 链 + 加 `yaml: 2.8.2`、scripts.build 仅替换 check-generated 段、其余字段全等）；SBOM 仅删 kit 包节点与其 relationship、documentNamespace 一致；tarball sha256 `87241982…05c3` ≠ 基线（预期不同，未声称一致）。
- 运行时 zod 两处（`src/kit/manifest.ts`、`src/environment/accepted-skip.ts`）：只含 sourceId 字面量 `sbtd-workflow-kit-upstream`（行 A 规定不变），实测无需编辑，未改。
- p0 release validator：`pnpm --filter @kunolu/omp-sbtd exec tsx scripts/p0/cli.ts check-package --packed <extracted candidate>` → exit 0，sourceTreeSha256 同基线，packedFileCount 412。
- 测试：`pnpm -r test` → dsh-sbtd 335 pass / 0 fail；omp-sbtd 834 passed / 3 skipped / 1 failed——`test/p0-authorized-omp-rpc-harness.test.ts` 的 “smoke-only: exact local OMP 17.3.5 …” 因 bun `--offline` 缓存无 zod/pi-coding-agent manifest 失败；在 `4f7388c` worktree 同条件复现同样失败（1 failed | 50 passed，同因），属环境性既有失败，非行 A 回归。迁移的 kit 测试单独复跑：`vitest run upstream/test` → 2 文件 49 passed / 2 skipped。
- typecheck：`pnpm -r typecheck` 两包全过；`tsc -p packages/omp-sbtd/upstream/tsconfig.json --noEmit` 通过。
- lint：`biome check src test scripts`（omp-sbtd）与 `biome check upstream/src upstream/test` 通过；根 `biome check .` 在 `4f7388c` 基线同样因 dsh-sbtd 既有 findings 失败，非行 A 引入。
- smoke：`pnpm --filter @kunolu/omp-sbtd smoke` 通过（分支与基线均 exit 0；首次冷跑在编译期 flake 一次，复跑通过）。
- lockfile：`pnpm-lock.yaml` 手术编辑仅 13 行删除（kit importer + kit devDep 链）并把 yaml 2.8.2 移入 omp-sbtd importer；`pnpm install --frozen-lockfile` 通过（先尝试过 `pnpm install` 重解析会把 vite 可选 peer yaml 升到 2.9.0，超出允许范围，已回滚改手术编辑）。
- 嵌入式 `kit/`、`skills/` 在 git 中零改动（`git status` / `git diff --stat` 均为空）。
- SBOM.spdx.json 文本 diff：仅两个 hunk——kit 包节点（22 行）与指向它的 CONTAINS relationship（7 行），纯删除。

## 决策记录（行 A 内的落点选择）

- `upstream/` 完整镜像旧 kit 包根（含 `package.json`、`LICENSE`、`THIRD_PARTY_NOTICES.md`、`agents-section-map.yaml`、`generated/`、`generated-omp/`、`generated-agent-plugin/`）：D10 括号清单未列这些，但行 A 要求纯搬移且 SBOM digest（含 `kit:{name,version,generatedSha256}` 键）必须逐字节保持 `documentNamespace` 不变——`upstream/package.json`（name/version 原样）是 digest 输入的搬移后来源；generated 三树在旧包内同样 git 跟踪，随搬移保持跟踪。
- 薄入口：`scripts/kit-{check-generated,generate,sync-upstream}.mjs`，以 `node_modules/tsx/dist/cli.mjs` 调 `upstream/src/*.ts`，cwd 钉 `upstream/`（sync-upstream 以 `process.cwd()` 为 packageRoot）。
- `write-sbom.ts`/`release-validator.ts`/`cli.ts` 的 `kitRoot` 统一改名 `upstreamRoot`（env `KPI_SBOM_KIT_ROOT` → `KPI_SBOM_UPSTREAM_ROOT`）；SBOM 渲染器删除 kit 包节点与其 relationship；sourceTreeSha256 digest 的 `kit` 键与值刻意保留（注释注明）以保 documentNamespace 逐字节一致。
- 恢复 `upstream/tsconfig.json`（extends `../../../tsconfig.base.json`、noEmit、仅 src——与旧 kit typecheck 覆盖一致），保持迁移代码可独立 typecheck。
- 根 `README.md`/`README_zh.md` 与 `docs/assets/omp/*.md` 的历史 kit 引用未动：README 属行 R，assets 为历史文档，均不在行 A 点名范围（见风险）。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T13:44:27+08:00 | planned | in-progress | 用户 2026-10-19 13:42 +08:00 批准「开始 A 行」 | 用户指令；分支 feat/omp-sbtd-0.2.0-rc.1-pr-a-migrate-kit 基于 main `1d9a5cd1d36c64381b1a95f8254fd217f2bcdba5`（PR #102，merge 时间 2026-10-19T13:39:54+08:00） |
| 2026-10-19T15:14:38+08:00 | in-progress | in-progress | 迁移与 CLEAN 门全部实测完成：分支构建 sourceTreeSha256 与 `4f7388c` 构建逐字节一致；compare-clean-gate.mjs 全 PASS；p0 check-package exit 0；dsh 335/0、omp-sbtd 834+49 passed（1 个 bun-offline 环境性失败在基线同因复现）；lint/typecheck/smoke 通过 | 本任务「验证证据」节；基线 tarball sha256 `e811933a…0184`、候选 `87241982…05c3`（预期不同）；`compare-clean-gate.mjs` 输出 11×PASS + CLEAN GATE: PASS |
