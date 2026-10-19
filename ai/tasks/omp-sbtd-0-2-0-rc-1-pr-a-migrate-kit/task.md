---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-a-migrate-kit
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-19 13:42 +08:00 批准「开始 A 行」
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-a-migrate-kit
created_at: '2026-10-19T13:44:27+08:00'
updated_at: '2026-10-19T13:44:27+08:00'
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
| book-legacy-change-safety | 删除既有包并改动构建管线，高回归风险；CLEAN 门字节级对比即安全网 | 行 A | running（CLEAN 门对比 + 全量测试为安全网） |
| book-refactoring-pass | 首次修改既有生产代码（脚本路径与生成器）前 | 行 A | running |
| book-release-readiness | 本行不发布、不改 runtime 交付 | 行 A | not-required |

## 进度

- [ ] 基线 worktree `4f7388c` 构建与 pack 逐文件 sha256 捕获
- [ ] kit 代码迁入 omp-sbtd（scripts/ + upstream/ + docs/spec 移动）
- [ ] package.json 三处编辑、write-sbom.ts、release-validator.ts、cli.ts、zod 两处、conformance matrix、SBOM.spdx.json、pnpm-lock.yaml
- [ ] 删除 packages/sbtd-workflow-kit
- [ ] CLEAN 门对比（对比脚本入本任务文件夹）+ 全量测试/lint/typecheck/p0 validator
- [ ] 移除额外 worktree；最终报告

## 验证证据

（随执行回填）

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T13:44:27+08:00 | planned | in-progress | 用户 2026-10-19 13:42 +08:00 批准「开始 A 行」 | 用户指令；分支 feat/omp-sbtd-0.2.0-rc.1-pr-a-migrate-kit 基于 main `1d9a5cd1d36c64381b1a95f8254fd217f2bcdba5`（PR #102，merge 时间 2026-10-19T13:39:54+08:00） |
