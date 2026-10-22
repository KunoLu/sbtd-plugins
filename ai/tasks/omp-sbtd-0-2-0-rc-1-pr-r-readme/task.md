---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-r-readme
workflow_mode: strict
mode_source: user
mode_note: 用户明确要求 strict；按 PRD 行 R、D6/D7/D11/D13 执行，仅本 worktree 编辑与提交，不 push/PR/tag/publish。
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-r-readme
created_at: '2026-10-22T15:40:20+08:00'
updated_at: '2026-10-22T15:56:46+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 R：双语 README

## 目标

- 根 README.md / README_zh.md 对齐两个插件的版本事实，删除已移除 workspace kit 的陈旧引用。
- omp-sbtd README.md 为英文默认，新增一一对应的 README_zh.md；双向语言链接钉 release tag（D6/D7），D11 兼容说明逐字保留。
- 保持 npm 文件清单 471 项，README.md 在包内、README_zh.md 不在包内；正常 build 的 SBOM 只允许 README checksum 与 documentNamespace 两行变化。

## 非目标

不修改 packages/dsh-sbtd/**、任何 package.json、pnpm-lock.yaml、plugin.json、代码、测试、files/p0 清单或 PRD 判据。不发布、不 push、不开 PR、不打 tag，不访问其他 checkout、不修改全局配置。行 D 历史证据不改写，合并回填仅限用户指定字段与一条事件。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-22T15:40:20+08:00 | in-progress | in-progress | 创建当前 strict 任务快照；无可证明前态，不捏造 lifecycle transition；首 commit 已单独回填 D 并启动 R | 92113b5；基线 9f1ba036c4d461315ba42ad02ece8cc0475e904a |
| 2026-10-22T15:56:46+08:00 | in-progress | in-progress | README 与派生 SBOM 已提交，实际包检查通过，完整 suite 与 root lint 的既有/越界失败保留；独立文档复核 CLEAN，仍不声明发布或合并完成 | 604ee35；下方验证证据；本记录继续 in-progress，合并回填归 orchestrator |

## 决策

- 需求由用户与 PRD 锁定，未完整调用 grill-with-docs，无新领域歧义。
- 先读完 PRD、行 C/D 记录及 git show 29289dd；首 commit 92113b5 恰两文件，未混入本记录。行 D 只改 status/updated_at/completed_at 并追加一条合并事件。
- npm 实测快照与发布目标分开：2026-10-22 dsh latest=0.1.0-rc.1、next=0.2.0-rc.1；omp latest=0.1.0-rc.2、next=0.1.0-rc.14。文档面向 omp 0.2.0-rc.1，安装命令明确以行 E 发布到 next 为前提；latest 不动，不假称目标已发布。
- 包内两份 README 顶部沿用根 README 的 EN/中文切换形式，但两个地址均使用 omp-sbtd-v0.2.0-rc.1 绝对 tag 链接：对称固定版本，避免 npm 页面相对链接指向未打包的 ZH 文件；根 README 继续仓库内相对互链。tag 存在后的点击验证由行 E 执行，本行不冒充已验证在线可达。
- D11 原文中的 18.12.2 是锁定时快照，遵从用户 verbatim 裁决，不查询或改写为现在的 upstream latest。
- 沿用行 C/D 已知 TaskStore 全库历史 schema blocker，不重跑确认，不改 active pointer；仅维护明确授权的共享文档并验证当前 TaskDocument，不声称 TaskStore lifecycle 或自动恢复可靠。状态保持 in-progress，合并后由 orchestrator 回填。
- 主会话为唯一 writer / validation controller；独立 reviewer 只读、不运行 build/lint/tests/formatters，使用配置模型，不 override。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；只叙述锁定事实，无新领域规则或边界歧义 | before-dev | not-required |
| book-ddia-data-design | 无 schema/缓存/数据所有权/跨服务流设计 | before-dev | not-required |
| book-legacy-change-safety | 无运行时行为改动或 bug 修复；打包影响通过实际 build/pack 检查 | before-dev | not-required |
| book-refactoring-pass | 无既有生产代码编辑 | before-dev | not-required |
| book-release-readiness | 不改部署/runtime、不发布；生成 SBOM 仅跟随 README 内容 | finish | not-required（不声明 release-ready，行 E 仍须 bump/rebuild/验证） |

## 进度

- [x] strict、授权根/分支与 clean 起点核对；两文件首 commit。
- [x] npm dist-tags、两个 package.json、plugin.json、CHANGELOG Unreleased 事实核对。
- [x] 四份 README 更新与一一对应。
- [x] install/lint/README-focused tests/build/pack/check-package、D11 与相对链接验证（root lint 失败如实保留）。
- [x] 独立只读复核、完整包测试、证据与 scoped commits（完整 suite 的既有 Bun offline 失败保留）。

## 验证证据

- 初始 pwd / git status --short / git branch --show-current：授权根与分支匹配、clean。git rev-parse 9f1ba03 = 9f1ba036c4d461315ba42ad02ece8cc0475e904a；git show -s --format=%cI 9f1ba03 = 2026-10-22T13:58:39+08:00。
- date -Is = 2026-10-22T15:40:20+08:00；npm view @kunolu/dsh-sbtd dist-tags --json 与 npm view @kunolu/omp-sbtd dist-tags --json 均 exit 0，结果见决策。dsh package.json version=0.2.0-rc.1；omp package/plugin version=0.1.0-rc.14、peer >=18 <19、dev pin 18.11.1（行 E 才 bump）。
- 任务与父路径无 symlink；本任务路径初始不存在；git check-ignore -v 对本任务 reports/probe.txt 命中 .gitignore:125 /ai/tasks/**/reports。报告不暂存。
- README assertions 搜索：p0-package-release.test.ts 读取 README 并检查 telemetry/uninstall；p0-dist-hygiene.test.ts 拷贝 README；release-validator.ts inventory 收录 README。选择相关 package/release/pack 测试，不修改任何测试。
- 命令统一环境：`COREPACK_HOME=$HOME/.cache/node/corepack PYTHONDONTWRITEBYTECODE=1`。Node v22.20.0 / pnpm 11.17.0。证据为 developer-local / dirty / local-only，基于 `92113b5e507f3e3e8f17878a0224c4d417bf9549` 加本地 README/SBOM 变更，不当作 CI 或发布认证。原生输出与同 stem 中文汇总保存于本任务 ignored `reports/row-r-*.{txt,md}`。
- 根 `pnpm install --frozen-lockfile`：exit 0，738 packages reused、0 downloaded，2.1s；`reports/row-r-install.txt` / `.md`。
- 根 `pnpm lint`：**exit 1**，Biome checked 190 files，44 errors / 9 warnings / 19 infos；已显示的诊断来自未改的 `packages/dsh-sbtd`，输出上限另省略 52 条。未运行修复、未重跑确认，D13 禁止改该目录。`biome.json` 排除 SBOM，Markdown 不在该 lint 覆盖内，不冒充 README lint。包目录 `pnpm lint`：**exit 0**，checked 99 files。原生 `row-r-lint.txt` / `row-r-package-lint.txt` 与同 stem 汇总。
- 包目录 `pnpm build`：**exit 0**，`generated output is current`；sourceTreeSha256 `f8781cdddfd10c9da2bf94ddcce3bc3323c05115cf89e7aec78f96805dd3271e`，sbomSha256 `01f46ca5a39145911251c97c3d312011cae40172e80844c1a1fca4cc35bbdbf7`。`row-r-build.txt` / `.md`。
- SBOM 与 `9f1ba03` blob 的 JSON 递归比较恰两值：`/documentNamespace` 与 `/files/371/checksums/0/checksumValue`（fileName=`./README.md`）。文本同行比对也恰两行（L12/L5583）：namespace `5b8de290…f914f8` → `f8781cdd…3271e`；README hash `4ad61c103b8bd40ae918be71d3020817006046eb765e34c23cee38a9377d2f1a` → `2acc019b0e1148b641feae94f45816ef4f65a671f06b1d8604a01c45d7316a5f`，与实际 README SHA-256 相等。允许条件成立，可纳入；原生 `row-r-sbom-diff.json`。
- 包目录 `pnpm exec vitest run test/p0-dist-hygiene.test.ts test/p0-package-release.test.ts test/publish-package.test.ts test/agent-plugin-pack.test.ts --no-file-parallelism --maxWorkers=1 --testTimeout=30000`：**4 files / 28 passed / exit 0**，14.75s。`row-r-focused.txt` / `.md`。
- 包目录 `npm pack --dry-run --json`：**entryCount=471 / exit 0**；README.md 存在、README_zh.md 不存在。清单与基线 SBOM 的 469 项加自动打包的 package.json / SBOM.spdx.json 完全一致，未建立其他 checkout 或重建基线。`row-r-pack-dry.txt` / `.md`。
- 真实 tarball smoke，以下三命令均 **exit 0**；check-package 输出 `packedFileCount:471`，sourceTreeSha256 / sbomSha256 与 build 相同。`row-r-{pack,unpack,check-package}.txt` 与同 stem 中文汇总。包版本仍 0.1.0-rc.14，非发布目标已上线的证明：

  ```sh
  # cwd: packages/omp-sbtd
  pnpm pack --pack-destination /tmp/row-r-pack-_b_jujw2
  tar -xzf /tmp/row-r-pack-_b_jujw2/kunolu-omp-sbtd-0.1.0-rc.14.tgz -C /tmp/row-r-pack-_b_jujw2
  pnpm exec tsx scripts/p0/cli.ts check-package --packed /tmp/row-r-pack-_b_jujw2/package
  ```

- D11：专用 grep 工具逐字查找两串，EN 命中根 README.md:L38 / 包 README.md:L17，ZH 命中根 README_zh.md:L38 / 包 README_zh.md:L17；Python `sum(needle in line for line in text.splitlines())` 执行 `grep -cF` 等价逐行计数。按根 EN、根 ZH、包 EN、包 ZH 顺序，EN=`1,0,1,0`，ZH=`0,1,0,1`（各合计 2）；受工具策略限制未调用 shell grep，不伪称执行过。两组 EN/ZH fenced code blocks 逐字相同，heading 数相同。
- Markdown links 与 HTML href 扫描：四份 README 共 36 个相对链接（含自身 fragment）目标存在；根目录锚点与标题匹配。根 README 无 `packages/sbtd-workflow-kit` 陈旧路径。`row-r-links-counts.json` 保留逐项结果。D7 两个绝对 tag 地址在文档中匹配要求；tag 尚未创建，链接预期 404，未声称在线通过，行 E 打 tag 后、publish 前负责点击核验。
- 当前行 R `TaskDocument.parse` 通过（schema/时间/状态事件）；额外解析行 D 时 bundled stateEvent schema 拒绝其记录，未改写受保护历史、未尝试全库 TaskStore、未将此失败写成通过。行 D 只保留已授权的最小合并回填。
- 工具边界：rtk=skipped-for-report（保存原生完整输出）；BDD=skipped（docs-only，无行为或 .feature 变更）；Cross-repo context/API Contract=not-needed；Mock Strategy=none（本行未新增 mock）；Web/Mobile/Graft/真实全局 omp 未调用，不把包 smoke 当作重跑行 C 宿主认证。无生产代码可读性/重构门触发；无新增长期 lesson。
- 最终完整包测试：包目录 `pnpm test`（`tsc -p tsconfig.json && vitest run --no-file-parallelism --maxWorkers=1 --testTimeout=30000`），15:46:31+08:00 开始，320.62s，**exit 1；46 files：45 passed / 1 failed；888 tests：884 passed / 1 failed / 3 skipped**。唯一失败为 `test/p0-authorized-omp-rpc-harness.test.ts > authorized OMP public-RPC harness > smoke-only: exact local OMP 18.11.1 blocks a dependency-resolved packed host before RPC without a provider`：Bun `--offline` 缺 `zod` 与 `@oh-my-pi/pi-coding-agent` cached manifest，`zod@4.1.12 failed to resolve`，未到 RPC。用户允许保留的既有环境失败；不修全局缓存、不改测试、不重跑确认。3 skipped 为两个 upstream transform 场景和一个 env-gated host-event live cell。原生 `row-r-full-tests.txt` / 同 stem 中文汇总 `.md`；suite 后 SBOM sha256 仍为 `01f46ca5…dbf7`。
- 独立只读 `BilingualReadmeReview`：**CLEAN**，无具体修复项；逐节核对四份 README 对应、D6/D7/D11、包元数据、CHANGELOG、上游 pin、五依赖与模板/资产数量。未代替主会话运行 build/tests；在线 tag 链接待行 E。`ReadmeContractReview` 同样结论 **CLEAN**，核对相对链接、发布 helper、files/p0/SBOM；其首报告将首 commit 与工作树范围混写，主会话指出后，该 reviewer 通过 `git show --stat` 更正：92113b5 恰 2 文件、604ee35 恰 7 文件，撤回对 task 首 commit 说明的误报；无待修复发现。
- 提交：首 commit `92113b5e507f3e3e8f17878a0224c4d417bf9549`（仅 PRD / 行 D task）与实现 commit `604ee35`（四份 README、index、本 task、SBOM）。`git diff --stat origin/main..HEAD` 在实现提交后仅 9 个授权路径，339 insertions / 36 deletions；`git status --short` 无输出。末尾证据提交只更新本 task，不改变已验证 README/SBOM 字节。
- 恢复边界：只提交文档与两个生成派生值，可按 scoped commits 回滚；无运行时/数据/全局配置迁移。task 文档已保存但不保证全库 TaskStore 恢复；发布、D7 在线验证与目标版本 bump 均归行 E。

## CONTRACT-CHANGE-NEEDED

**无。** SBOM 恰好为允许的两行派生值；未扩大 files/p0/运行时/PRD 判据契约。Root lint 与 Bun offline 失败保留，不属于本行契约变更；D7 在线闭环按既定行 E 执行。

## 使用的模型

> 数据取自本任务 session jsonl，快照时间 **2026-10-22T15:56:46+08:00**；不含此后最终记录/提交/回复调用，orchestrator 可在会话结束后精化。assistant 消息按实际 provider/model；工具按 assistant toolCall；thinking 取 thinking_level_change。原生快照保留 `reports/row-r-model-usage.json`。没有 model override；runtime model_change 记录版本为 18.12.5；resolvedModel 字段未写入。

| # | 会话 / 用途 | provider/model | thinkingLevel | resolvedModelIsFallback | 快照计数 |
|---|---|---|---|---|---|
| 1 | 主会话 `01a1628c-873c-715d-a38e-4e946f8f6127`；唯一 writer、验证与 commits | openai-codex / gpt-6-astra | high | false | 1 user / 36 assistant / 66 toolResult；67 toolCall（read 26、eval 10、bash 7、todo 5、edit 5、write 5、glob 3、wait 3、grep 2、task 1）；error 1（行 D TaskDocument schema 拒绝） |
| 2 | `BilingualReadmeReview` / `01a16291-7588-71e0-b952-bf593d29202f`；只读双语/事实复核 CLEAN | kimi-code / k3 | max | false | 3 user / 15 assistant / 24 toolResult；24 toolCall（read 12、bash 10、grep 2）；error 0 |
| 3 | `ReadmeContractReview` / `01a16291-762a-7638-8531-5984410a8315`；只读链接/发布与打包契约复核 CLEAN；首 commit 归属更正在快照后 | kimi-code / k3 | max | false | 3 user / 22 assistant / 32 toolResult；32 toolCall（bash 19、read 8、grep 4、wait 1）；error 1 |
| 4 | 主会话辅助 `type:model_usage`，purpose=`job-widget`，非主实现或独立 reviewer | cursor / composer-2.5 | 未记录 | 不适用 | 1 条辅助用量 |

主 jsonl：`~/.omp/agent/sessions/--workspace-sbtd-plugins-row-r--/2026-10-22T07-38-59-260Z_01a1628c-873c-715d-a38e-4e946f8f6127.jsonl`；两名 reviewer 位于同 stem 目录的 `BilingualReadmeReview.jsonl` / `ReadmeContractReview.jsonl`。快照时主会话最后一条 eval 仍在执行，因此 toolCall 比 toolResult 多 1；不是丢失验证结果。所有文件编辑与提交由主会话完成，subagent 未写仓库文件或执行 build/lint/tests/formatters。
