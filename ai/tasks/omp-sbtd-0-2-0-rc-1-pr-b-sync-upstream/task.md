---
schema_version: 1
id: omp-sbtd-0-2-0-rc-1-pr-b-sync-upstream
workflow_mode: strict
mode_source: user
mode_note: PRD 规则为每个任务都用 strict；用户 2026-10-19 18:57 +08:00 指示「开始B行」
status: "in-progress"
branch: feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream
created_at: '2026-10-19T19:11:42+08:00'
updated_at: '2026-10-19T19:11:42+08:00'
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

- sourceId 保持 `sbtd-workflow-kit-upstream`；transformVersion 保持 `p0-v3`。行 B 只改 resolvedRevision 与 sourceTreeSha256（及按需要的再生成 kit 产物 / map / notices）。
- 不触碰 omp peerDependencies（`>=17.3.5 <18`）/ devDependency omp（`17.3.5`）及相关 `pnpm-lock.yaml` omp 条目——行 C（D11）独占。
- 不 bump package version、不发布、不做行 E 工作。
- 不执行 ROADMAP 归档 chore（D12）；不做 dsh-sbtd 行 G。
- 不自动 pip install Python 依赖（D8：fail-closed 预检；5 依赖预检接线属行 C，若非已存在）。
- 不 push、不开 PR（用户指示）。

## 验收（PRD §4 任务 B，逐字要点）

- v2.0.2 diff 实测 229 文件变更（67 新增 / 107 删除 / 53 修改，`sbtd-workflow-onboard/` 子树）；`scripts/` 33 个 `.py` 全 include；`assets/` 与两个 schema json 逐文件 include/omit 并逐条记录 reason（`requirements.txt` 由 D8 锁定随包发布，不在逐文件审清单）；AGENTS 模板统一到 `1d82494`；third-party notices 重新生成。
- 供应链身份不变量：sourceId `sbtd-workflow-kit-upstream`、transformVersion `p0-v3` 不变；行 B 只改 resolvedRevision 与 sourceTreeSha256。
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
| book-legacy-change-safety | 修改生成输入（map/钉）影响嵌入产物；安全网为 check-generated 确定性校验 + p0 validator + 全量测试 | 行 B | running |
| book-refactoring-pass | 不改生产代码逻辑（仅供应链输入与再生成产物）；map/测试钉更新为机械编辑 | 行 B | not-required |
| book-release-readiness | 本行不发布、不改 runtime 交付（行 E 才发布） | 行 B | not-required |

## 进度

- [x] 行 A 回填（PRD 行 A done：#104 / `f1bba41d168af04807914914ad8dce27dfc8688b` / 2026-10-19T17:13:57+08:00；行 A task.md 完结 + stale 措辞修正）
- [ ] map 逐文件决策落地（新增 include/omit、删除 stale 条目）
- [ ] sync plan → apply 到 `1d82494`，sourceTreeSha256 重算
- [ ] AGENTS 模板统一 `1d82494`（嵌入头部 revision 证据）
- [ ] notices 再生成（插件根 + kit/THIRD_PARTY_NOTICES.md）
- [ ] check-generated / build / p0 validator / 全量测试
- [ ] 测试钉更新（`f8aa0d7`→`1d82494` 断言）
- [ ] PRD 行 B 状态与证据回填

## 验证证据

（待执行后填写真实命令输出）

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-19T18:57:00+08:00 | planned | in-progress | 用户 2026-10-19 18:57 +08:00 指示「开始B行」（PRD 规则：每任务 strict、开工新建任务记录） | 用户指令；分支 feat/omp-sbtd-0.2.0-rc.1-pr-b-sync-upstream 基于 main `f1bba41d168af04807914914ad8dce27dfc8688b`（PR #104，merge 2026-10-19T17:13:57+08:00） |
