---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-b-sync-upstream
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-19 18:57 +08:00 指示「开始B行」
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream
created_at: '2026-10-19T19:11:42+08:00'
updated_at: '2026-10-19T21:40:32+08:00'
completed_at: null
---
# omp-sbtd 0.2.0-rc.1 行 B：同步上游到 v2.0.2（1d82494）

## 目标

按 `docs/prd/omp-sbtd-0.2.0-rc.1.md` 行 B（L66）与 §4 任务 B 验收执行：把 `packages/omp-sbtd/upstream/upstream.lock.json` 的 resolvedRevision 从 `f8aa0d7225a26c5e00b81d2f1b05121108e63630`（v1.0.13）升为 `1d82494d74f6df9bca7dccef2da409f87091883e`（v2.0.2），重算 sourceTreeSha256；对 distribution map 的每个新文件逐个决定收录（D9）；统一两个嵌入 AGENTS 模板的上游版本（现 `4222b15` 与 `f8aa0d7` 分叉）到 `1d82494`；重新生成 third-party notices。

## 范围

- 上游源：`/workspace/640-skills`（canonical `https://github.com/KunoLu/640-skills`），钉 `1d82494d74f6df9bca7dccef2da409f87091883e`（tag v2.0.2）。
- 入口：`node scripts/kit-sync-upstream.mjs --source-root /workspace/640-skills --revision 1d82494d74f6df9bca7dccef2da409f87091883e`（`--plan` → `--apply --plan-digest …`），随后按仓库惯例 generate / check-generated / embed。
- `packages/omp-sbtd/upstream/omp-distribution-map.yaml` 逐文件决策（详见「D9 逐文件决策」节）。
- 嵌入产物再生成：`upstream/generated*`、`packages/omp-sbtd/kit/`、`skills/`、`THIRD_PARTY_NOTICES.md`（插件根 + kit）、`SBOM.spdx.json`。
- 钉 `f8aa0d7`/`4222b15` 的测试与文档断言随同步更新到 `1d82494`。
- 本 PR 第一个 commit 回填行 A（PR #104 / merge SHA `f1bba41d168af04807914914ad8dce27dfc8688b` / done 2026-10-19T17:13:57+08:00）并修正行 A task.md 的 stale 措辞。

## 非目标（行 B 明确）

- sourceId 保持 `sbtd-workflow-kit-upstream`；transformVersion 按 R7/D14 升 `p0-v3` → `p0-v4`。行 B 改 resolvedRevision、sourceTreeSha256，并执行且仅执行 D14 三项 transform 变更：(b) PROJECTION_FORBIDDEN_TOKEN 豁免扩为 digest 绑定的 canonical onboard runtime 包路径集（`onboard/runtime/scripts/*.py`、`onboard/runtime/assets/*`、`onboard/runtime/onboard-contracts.schema.json`、`onboard/runtime/upgrade.schema.json`，内容仍逐字节绑定 canonical manifest digest，overlay 不得走私）；(c) CANDIDATES 删 `trellis-workflow`（ENOENT 仍 fail-closed）；(d) overlay catalog 删 `skill:trellis-workflow`/`skill:trellis-channel`、增 `skill:sbtd-task`。其余投影/生成逻辑不变。
- 不触碰 omp peerDependencies（`>=17.3.5 <18`）/ devDependency omp（`17.3.5`）及相关 `pnpm-lock.yaml` omp 条目——行 C（D11）独占。
- 不 bump package version、不发布、不做行 E 工作。
- 不执行 ROADMAP 归档 chore（D12）；不做 dsh-sbtd 行 G。
- 不自动 pip install Python 依赖（D8：fail-closed 预检；5 依赖预检接线属行 C，若非已存在）。
- 不 push、不开 PR（用户指示）。

## 验收（PRD §4 任务 B，逐字要点）

- v2.0.2 diff 实测 229 文件变更（67 新增 / 107 删除 / 53 修改，`sbtd-workflow-onboard/` 子树）；`scripts/` 33 个 `.py` 全 include；`assets/` 与两个 schema json 逐文件 include/omit 并逐条记录 reason（`requirements.txt` 由 D8 锁定随包发布，不在逐文件审清单）；AGENTS 模板统一到 `1d82494`；third-party notices 重新生成。
- 供应链身份不变量：sourceId `sbtd-workflow-kit-upstream` 不变；transformVersion 按 R7/D14 升 `p0-v4`；行 B 同时改 resolvedRevision、sourceTreeSha256 并执行 D14 三项 transform 变更（不再只是改钉）。
- check-generated、全量 package build、p0 validator / 测试按仓库惯例通过；基线既有 bun-offline harness flake 只作 pre-existing 记录，不冒充 PASS。

## D9 逐文件决策（vs f8aa0d7→1d82494）

> 决策在执行节「验证证据」补全实测结果；下表为决策与理由（reason 同时写入 map 条目）。

硬锁（不在逐文件审清单或已锁定）：

- `onboard/runtime/scripts/*.py`（33 个：32 新增 + `onboard.py` 修改）：全部 include（D9 硬锁）。
- `onboard/runtime/requirements.txt`：include（D8 锁定随包发布；5 个钉版依赖 jsonschema/PyYAML/markdown-it-py/tomlkit/cryptography；不自动 pip install；fail-closed 预检接线为行 C 范围）。
- `onboard/runtime/templates/skills/sbtd-task/`（8 文件：SKILL.md + references/7）：include，随模板树收录（D9 锁定）。

逐文件审（`assets/` 9 个 + 2 个 schema json + stable 新增），reason 写入 map：

| path | policy | reason |
|---|---|---|
| onboard/runtime/assets/graft-build-policy.json | include | 被收录脚本 `sbtd_migration.py` 运行时读取（上游 1d82494 实测引用），OMP 投影随包分发该脚本 |
| onboard/runtime/assets/graft-hook-entry.mjs | include | 被收录脚本 `sbtd_graft_entry.py`/`sbtd_migration.py` 引用 |
| onboard/runtime/assets/graft-instructions.txt | include | 被收录脚本 `sbtd_codex_wiring.py`/`sbtd_migration.py` 引用 |
| onboard/runtime/assets/migration-legacy-ownership.json | include | 被收录脚本 `sbtd_migration.py`/`sbtd_upgrade_inventory.py` 引用 |
| onboard/runtime/assets/migration-local-ignore.txt | include | 被收录脚本 `sbtd_migration.py` 引用 |
| onboard/runtime/assets/migration-paused-agents.txt | include | 被收录脚本 `sbtd_migration.py` 引用 |
| onboard/runtime/assets/routing-approval.pub | include | 被收录脚本 `sbtd_migration.py` 验签路径引用（D8 验签 fail-closed 资产） |
| onboard/runtime/assets/runtime-lineage.json | include | 被收录脚本 `sbtd_migration.py`（`_LINEAGE_DOCUMENT`）运行时读取 |
| onboard/runtime/assets/runtime-lineage.pub | include | 被收录脚本 `sbtd_migration.py`（`_LINEAGE_PUBLIC_KEY`）验签路径引用 |
| onboard/runtime/onboard-contracts.schema.json | include | 被收录脚本 `onboard_contracts.py`/`sbtd_migration.py`/`sbtd_upgrade_inventory.py` 加载校验 |
| onboard/runtime/upgrade.schema.json | include | 被收录脚本 `sbtd_migration.py` 加载校验 |
| onboard/runtime/assets/external-skills/stable/skills/i-have-adhd/{SKILL.md,agents/gemini.toml,agents/openai.yaml} | omit | Stable Skill tree is not retained in the OMP distribution（同 impeccable/shadcn 先例：OMP overlay catalog 不消费该 stable 树，非插件认证技能集） |
| onboard/runtime/assets/external-skills/stable/licenses/i-have-adhd-LICENSE | omit | License for a non-retained stable repository |
| onboard/runtime/assets/external-skills/stable/skills/impeccable/scripts/{VERSION,impeccable,impeccable.cmd,live-browser-ignores.js,data/font-index.json,data/font-index-failures.json} | omit | Stable Skill tree is not retained in the OMP distribution（impeccable 全树 omit 先例） |
| onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/scripts/tests/test_catalog_summary_line_endings.py 等 3 个新增测试 | include | ui-ux-pro-max stable 树已整体收录；legal inventory 要求 retained stable Skill 整树保留 |
| onboard/runtime/templates/skills/lessons-record/references/identity-migration.md | include | lessons-record 模板树已收录，随模板树新增文件 |
| onboard/runtime/templates/skills/project-validation/references/run-summary.zh-CN.md.template | include | project-validation 模板树已收录，随模板树新增文件 |

删除文件（107 个，绝大多数为已 omit 的 impeccable scripts）：其 map 条目随同步移除（stale decision 会触发 `PROJECTION_POLICY_INVALID` fail-closed）。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill 后 DDD 已在任务 0 执行（draft，Reviewy R1 findings 已修复）；行 B 无领域模型变更（供应链身份不变量保持） | 行 B | not-required（沿用任务 0 DDD） |
| book-ddia-data-design | 行 B 引入上游 `requirements.txt`/schema/assets 分发，但均为上游内容随包收录，无新数据设计；数据流（sync→projection→embed）在行 A 已固定 | 行 B | not-required |
| book-legacy-change-safety | 修改投影 transform 代码（D14 门禁豁免/CANDIDATES）+ 生成输入（map/钉）影响嵌入产物；现有行为证据见「验证证据」4/5（两墙实测）；安全网为 upstream/test 既有门禁/audit 测试 + check-generated 确定性校验 + p0 validator + 全量测试 | 行 B | running |
| book-refactoring-pass | R7/D14 后行 B 修改既有生产代码（`omp-projection.ts` 豁免谓词、`agent-plugin-projection.ts` CANDIDATES）；编辑前需 emit Refactoring Review | 行 B | running |
| book-release-readiness | 本行不发布、不改 runtime 交付（行 E 才发布） | 行 B | not-required |

## 进度

- [x] 行 A 回填（PRD 行 A done：#104 / `f1bba41d168af04807914914ad8dce27dfc8688b` / 2026-10-19T17:13:57+08:00；行 A task.md 完结 + stale 措辞修正）— commit `9bce16e`（rebase 后 `e4bc0f7`）
- [x] map 逐文件决策落地（新增 69 条 include/omit、删除 109 条 stale）+ agents-section-map 按 v2.0.2 新标题结构重写 — commit `23ca561`（rebase 后 `6431db3`）
- [x] R7 回填 + 解除 blocked：PR #105 / merge SHA `c041b2c1aa2794e085ab442d763ce2876b4e50ed` / done 2026-10-19T21:07:19+08:00；R7/D14 授权 p0-v4；stale「transformVersion 须保持 p0-v3 / 行 B 只改钉」措辞修正；`ai/tasks/index.md` 接线
- [ ] p0-v4 transform 代码：`omp-projection.ts` 豁免扩为 D14 路径集（digest 绑定）+ `agent-plugin-projection.ts` CANDIDATES 删 `trellis-workflow` + `upstream.lock.json` transformVersion `p0-v4` + 对应测试
- [ ] overlay catalog：删 `skill:trellis-workflow`/`skill:trellis-channel`、增 `skill:sbtd-task`（对齐 D9 收录 `templates/skills/sbtd-task/` 模板树）；孤儿 overlay 清理；feature/测试同步
- [ ] sync plan → apply 到 `1d82494`，sourceTreeSha256 重算（新 digest 已由 scratch stage 独立算出 `c1fc3f679c375a22c6272de92c3377ac04ea8edb996acd314ea76f73257739b0`，旧 `a513e97635691a97c6994bae8b45b70f450d501eedaf24d00d5c23b262816400`）
- [ ] AGENTS 模板统一 `1d82494`（落点为 `omp-overlays/AGENTS.project-root.md` 首行 pin `4222b15`→`1d82494` + 再生成，`AGENTS.project-omp.md` 由 generate 自动带新钉）
- [ ] notices 再生成（sync apply 的 embed 阶段自动再生成插件根 + kit/THIRD_PARTY_NOTICES.md）
- [ ] check-generated / build / p0 validator / 全量测试
- [ ] 测试钉更新（`f8aa0d7`→`1d82494` 断言，如 `test/extension.test.ts` L544/L1844）
- [ ] PRD 行 B 状态与证据回填（未 done 前不回填）

## 验证证据

实测环境：`/workspace/sbtd-plugins` 分支 feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream，Node 22.20.0，pnpm 11.17.0；上游 `/workspace/640-skills`（HEAD bb52bf8 不影响——sync 用 `git archive <revision>` 取钉住对象，已实测 `cat-file -t 1d82494…` = commit）。

1. `node scripts/kit-sync-upstream.mjs --source-root /workspace/640-skills --revision 1d82494d74f6df9bca7dccef2da409f87091883e --plan`（于 `packages/omp-sbtd`）首轮 → `SECTION_MAPPING_UNKNOWN`：v2.0.2 把 AGENTS 模板从「Codex 全局规则」（15+ 小节）整体重构为「SBTD 全局规则」（H1+5×H2）/「SBTD 项目规则」（H1+4×H2），旧 section key 全部失效；新模板实测零 `codex` token、无 Trellis 专节。
2. 重写 `agents-section-map.yaml`（11 条：global 6 include→global，project 5 include→project-root；project-omp 维持「marker + overlay」拓扑不变）后复跑 → `PROJECTION_POLICY_INVALID` stale 109（103 impeccable scripts + trellis-channel/3 + trellis-workflow/3，上游已删；其中 trellis-channel LICENSE/NOTICE 经 R100 改名为 sbtd-task/LICENSE/NOTICE）。
3. 删除 109 条 stale 后复跑 → `PROJECTION_ASSET_UNCLASSIFIED` unclassified 69（32 新脚本 + requirements.txt + 2 schema + assets/ 9 + sbtd-task 10 + 模板新增 2 + i-have-adhd 4 + impeccable 新增 6 + ui-ux-pro-max 测试 3）。按 D9/D8 决策补齐 69 条（reason 见「D9 逐文件决策」表与 map 条目）。
4. 补齐后复跑 → **墙 1**：`PROJECTION_POLICY_INVALID: Agent Plugin audit contains blocked candidates`（phase `agent-plugin`）：`trellis-workflow` 候选 `checks.portable blocked — ENOENT`（上游已删模板树，`generated/` 里 `templates/skills/trellis-workflow` 不存在）；基线 f8aa0d7 该候选为 `fail`（非 blocked）故通过。candidateCount 13 / certifiedCount 12 不变。
5. 墙 2 独立实证（scratch stage `/tmp/rowB-stage-*`，不改仓库：复制 map/overlays/lock + `git archive 1d82494` 到 vendor，tsx 直调真实 `generateKit`+`generateOmpProjection`）：`generateKit OK`（generatedSha256 `e535bb1a…`），`generateOmpProjection` → **`PROJECTION_FORBIDDEN_TOKEN`**：pathViolations `["onboard/runtime/scripts/sbtd_codex_wiring.py"]`，payloadViolations 19（`sbtd_codex_wiring.py`、`sbtd_graft_deployment.py`(69 处)、`sbtd_upgrade_hosts.py`(58)、`sbtd_omp_sources.py`(25)、`sbtd_migration_plan.py`(28)、`onboard_arguments.py`(11)、`migration-legacy-ownership.json`(12)、`sbtd_cleanup_targets.py`(8)、`sbtd_graft_entry.py`(7)、`onboard_contracts.py`(3)、`sbtd_upgrade_inventory.py`(3)、`sbtd_migration.py`(2)、`sbtd_omp_wiring.py`(2)、`graft-instructions.txt`(1)、`sbtd_migration_verify.py`(1)、`sbtd_upgrade.py`(1)、`onboard-contracts.schema.json`(4)，及派生 `manifest.json`/`projection-report.json`）；violationCount 20。scratch 已删除。
6. 新 sourceTreeSha256 独立实测：`c1fc3f679c375a22c6272de92c3377ac04ea8edb996acd314ea76f73257739b0`（`sourceTreeSha256()` 真实函数对 `git archive 1d82494` 解出树计算；旧值 `a513e976…6400`）。

## CONTRACT-CHANGE-NEEDED（已裁决：R7/D14，option 2）

> 裁决记录：用户 2026-10-19 ~20:31 +08:00 选定 option 2（团队投票 4× option 2）——先修 PRD，行 B transformVersion 升 `p0-v4`，catalog 跟随 row B。PRD R7 已 squash-merge：PR #105 / merge SHA `c041b2c1aa2794e085ab442d763ce2876b4e50ed` / done 2026-10-19T21:07:19+08:00；D14 锁定授权三项 transform 变更（见「非目标」节）。本分支已 rebase 到 main `c041b2c`（原 `9bce16e`/`23ca561`/`f420cc4` 现为 `e4bc0f7`/`6431db3`/`b8f98e5`），本任务 2026-10-19T21:40:32+08:00 解除 blocked 续作。以下为原始 blocked 记录，保留作证据。

**What**：行 B sync 无法在不触碰行 B 边界的情况下完成，两处硬冲突均已实测：

- **墙 1（agent-plugin CANDIDATES）**：`upstream/src/agent-plugin-projection.ts` L62 `CANDIDATES` 硬编码 `trellis-workflow`，其模板树在 v2.0.2 被上游删除（R100：trellis-channel LICENSE/NOTICE → sbtd-task）；audit 对 ENOENT fail-closed（blocked ≠ 基线的 fail）。修复需改 transform 代码（删候选）——projection 逻辑变更，而 transformVersion 锁 `p0-v3`。连带：`upstream/omp-overlays/onboard/runtime/catalog.json` 仍列 `skill:trellis-workflow`/`skill:trellis-channel`（指向已删路径），且上游 v2.0.2 catalog 新增 `skill:sbtd-task`——overlay catalog 是否同步增删是插件可见行为，须裁决归属行 B 还是行 C。
- **墙 2（零泄漏门禁 vs D9 硬锁）**：`upstream/src/omp-projection.ts` 的 PROJECTION_FORBIDDEN_TOKEN（输出路径/载荷零 `codex`，仅 digest 绑定的 canonical `onboard.py` 豁免）拒绝 D9 硬锁 include 的文件：`sbtd_codex_wiring.py` 路径本身含 codex（overlay 机制无法改路径，且 overlay 分叉上游脚本会破坏字节同一性），另 17 个上游文件 payload 含 codex（v2.0.2 上游新增 Codex host 接线支持）。豁免/改门禁 = transform 逻辑变更；omit = 违反 D9 且 grill Q2 已明确拒绝部分收录（互相 import，运行时才 ImportError）。

**Why**：行 B 硬边界「transformVersion 保持 p0-v3、只改 resolvedRevision + sourceTreeSha256 及再生成产物/map/notices」与「D9：33 脚本全 include」在 v2.0.2 实际上游内容下不可同时满足。

**Options**：

1. （推荐）最小放宽行 B 边界，两处都按「数据修正」处理并记录：(a) CANDIDATES 删除 trellis-workflow（上游实体已不存在，候选列表跟随上游清单），overlay catalog 同步删 trellis 两项（是否新增 sbtd-task 项单独裁决，可留行 C）；(b) 门禁豁免从单一 `onboard.py` 扩为「digest 绑定的 canonical onboard runtime 包路径集」（`onboard/runtime/scripts/*.py`、`onboard/runtime/assets/*`、两个 schema json——内容仍逐字节钉 canonical manifest digest，豁免仍 content-bound，overlay/drift 不能走私）。保持 p0-v3 需明确豁免属 bug 级跟随上游；否则应 bump transformVersion（选项 2）。
2. bump transformVersion（如 `p0-v4`）做上述门禁/CANDIDATES 变更——违反行 B 硬边界「transformVersion 不变」，需 PRD 修订。
3. 修 D9：omit/改名 codex 相关文件——不可行：路径违例无法 overlay；部分 omit 破坏 Python 包互相 import（grill Q2 已否决）；「同步后可用」失守。
4. 请上游 640-skills 去掉 codex 字样——仓库外依赖，行 B 无限期阻塞。

待用户选定后继续；map/section-map 决策（commit `23ca561`）在选项 1/2 下均保持有效。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T18:57:00+08:00 | planned | in-progress | 用户 2026-10-19 18:57 +08:00 指示「开始B行」（PRD 规则：每任务 strict、开工新建任务记录） | 用户指令；分支 feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream 基于 main `f1bba41d168af04807914914ad8dce27dfc8688b`（PR #104，merge 2026-10-19T17:13:57+08:00） |
| 2026-10-19T19:43:22+08:00 | in-progress | blocked | 两处 p0-v3 投影不变量与 v2.0.2 + D9 硬锁冲突实测成立（PROJECTION_FORBIDDEN_TOKEN 20 处违例；agent-plugin CANDIDATES trellis-workflow blocked/ENOENT），修复均需 transform 代码或门禁/D9 语义变更，超出行 B 授权；按指令 STOP 并输出 CONTRACT-CHANGE-NEEDED | 本任务「验证证据」节第 4/5 条与「CONTRACT-CHANGE-NEEDED」节；scratch stage 实测输出；commit `23ca561`（rebase 后 `6431db3`） |
| 2026-10-19T21:40:32+08:00 | blocked | in-progress | 用户裁决 option 2（2026-10-19 ~20:31 +08:00，团队投票 4× option 2）：PRD R7 授权行 B transformVersion 升 `p0-v4` 并锁定 D14 三项 transform 变更 + catalog 属行 B；R7 已 squash-merge（PR #105 / `c041b2c1aa2794e085ab442d763ce2876b4e50ed` / 2026-10-19T21:07:19+08:00），本分支 rebase 到 main `c041b2c` 后续作 | PRD `docs/prd/omp-sbtd-0.2.0-rc.1.md` D14 + 修订日志 R7；R7 任务记录 `ai/tasks/omp-sbtd-0-2-0-rc-1-prd-r7-p0-v4/task.md`（done）；用户 2026-10-19 ~21:07 +08:00 续作指令（D14 / p0-v4） |
