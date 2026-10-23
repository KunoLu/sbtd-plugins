---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-1-plan
workflow_mode: strict
mode_source: user
mode_note: 用户要求每个 task 都用 strict
status: "done"
branch: docs/dsh-sbtd-0.2.0-rc.1-prd
created_at: '2026-10-17T21:43:52.311268+08:00'
updated_at: '2026-10-23T10:35:03+08:00'
completed_at: '2026-10-18T09:11:01+08:00'
---
# dsh-sbtd 0.2.0-rc.1 升级方案 grill

## 目标

对 `@kunolu/dsh-sbtd@0.2.0-rc.1` 升级跑完整 grill-with-docs，只问仍会改变实现或验收的开放问题。本轮不改代码、不写 PRD、不 commit、不 push、不 npm。不自行选定答案，等待群投票。

## 已锁定输入

用户 2026-10-17 锁定，本任务不重问：

- 版本 `@kunolu/dsh-sbtd@0.2.0-rc.1`，只发 next，latest 不动。
- dsh 宿主：peer 和 engines.dsh 写同一范围 `>=0.2.0-rc.2 <0.3.0-0`；T0 在 0.2.0-rc.2 不通过则退回 `>=0.2.1-rc.2 <0.3.0-0`；devDep 精确钉。
- 删除 Trellis 与 GitNexus 后端；本版就把 GitNexus 换成 Graft（需在未安装 Graft 时可降级）。
- book review 门禁与「无计划不准改生产代码」只在 strict 强制；完整 grill 后的 DDD 复审三种模式都强制。
- manuals 钉 640-skills v2.0.2（`1d82494d74f6df9bca7dccef2da409f87091883e`），白名单删 trellis-workflow、加 sbtd-task。
- 每个开发任务都用 strict；方案落 docs/prd，表格记录序号/任务/优先级/状态/PR/merge SHA/done 时间/strict 任务记录路径；每个 PR 合并后删本地+远程分支。
- PR 顺序：PRD 文档 → PR-A 手册 → PR-B 后端（sbtd-task 状态、模式门禁、lessons、Graft）→ PR-C 宿主适配+T0 → 文档/CHANGELOG → PR-D 发版。

已核对事实（不作为新决策）：dsh latest=`0.2.0-rc.2`，next=`0.2.1-rc.2`；0.2.0-rc.2 只检查 peer，0.2.1 起 engines.dsh 优先，均 `includePrerelease:true`；npm peer 默认不带 includePrerelease。现行包是 `0.1.0-rc.3`，peer 精确钉 `0.1.1-rc.2`，无 engines、无 CHANGELOG。`hooks.ts` 的 `runPreStep` 仍写 `source.kind:'plugin'`，并重组 `{kind:'enter'}`。插件写任务产物只到 `.trellis/tasks/<slug>/{prd,design,implement}.md`，不写 `task.md`。lessons 身份是 `.trellis/.developer`，store 随 Trellis workflow 或 `docs/lessons`。`sbtd_validate` 返回字段名是 `gitnexus`。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 完整 grill-with-docs 已完成（Round 1–3 全部锁定） | 复审已交付，见末节 | confirmed |
| book-ddia-data-design | 本任务不稳固 schema、迁移或跨进程数据设计 | 本轮 grill | not-required |
| book-legacy-change-safety | 本轮不改既有行为 | 本轮 grill | not-required |
| book-refactoring-pass | 本轮不改生产代码 | 本轮 grill | not-required |
| book-release-readiness | 本轮不发布、不改 runtime 交付 | 本轮 grill | not-required |

grill-with-docs 已完成（Round 1–3 全部锁定，frontier 为空）。DDD Boundary Review 已交付（见末节），用户 2026-10-18 确认，状态 confirmed。

## 下一步

PRD 已落地（`docs/prd/dsh-sbtd-0.2.0-rc.1.md`，DDD confirmed）。下一步：commit → PR → Reviewy 评审；评审 CLEAN 后再进入 PR-A（开发前新建对应 strict 任务）。

## Grill Round 1

# Grill Round 1 — dsh-sbtd 0.2.0-rc.1

未选定答案，等待群投票。已锁定决策不重问。完整 grill 未结束，所以还没跑 DDD Boundary Review，本轮也不改 `docs/CONTEXT.md`。

术语冲突（不单独成题，由 Q4 决定）：`docs/CONTEXT.md` 的 Runtime Mode 是 `enforced|advisory`（Avoid: strict mode），Policy Profile 是 `strict|relaxed`。本轮的 `strict|default|lite` 是 sbtd-task 的 workflow_mode，插件源码里没有这个字段。

已核对、不再问：版本与 dist-tag、peer/engines 范围及退回范围、devDep 精确钉、删除 Trellis/GitNexus 后端、Graft 必须可降级、book review 与无计划禁改只在 strict 强制、三种模式都强制完整 grill 后的 DDD、manuals 钉与白名单、本仓开发任务用 strict、方案落 `docs/prd`、PR 顺序与合后删分支。

---

**Q1** Graft 后端本 RC 覆盖哪些能力，未安装、guard 失败或无图时如何降级？现行 `sbtd_validate` 用 GitNexus 做 pre impact 与 post detectChanges，缺失只 `skipped` 且不把 post 打成 blocked；本仓只允许已接线的 managed launcher，禁止插件 spawn、init 或写 MCP，空图不算无影响。

- A. 只调用已接线 launcher 的只读查询（freshness、find、trace、file_api、repo_map）；上述失败都返回 skipped 并写明 reason，不 init、不写 MCP，空结果不算无影响，post 仍只因测试失败 blocked。
- B. 降级规则同 A，但把 trace/find 的非空结果映射成 pre impact 完成（pre=done），用来替代旧 GitNexus impact。
- C. 本 RC 不调用查询；无论 Graft 是否已接线，分析相位都只返回 skipped，结构查询留给模型直接用宿主 MCP。

推荐 A。理由：B 会把不能当证明的结构证据记成影响分析完成，C 没有替换 GitNexus 在 validate 里的分析角色。

---

**Q2** 删除 Trellis 后端后，插件还写哪些任务文件？今天只经 `writeArtifact` 写 `.trellis/tasks/<slug>/{prd,design,implement}.md`，没有 `.trellis` 时 `sbtd_spec`/`sbtd_tickets` 只回 draft；插件不写 `task.md`，mode/status 的 writer 是 sbtd-task TaskStore。

- A. 插件不写 `task.md`、`.sbtd`、`.trellis` 或 `docs/prd`；`sbtd_spec` 与 `sbtd_tickets` 只回 draft。
- B. 仍不写 `task.md`；仅当调用方传入已存在的 `docs/prd/` 下安全相对路径时才写该文件，否则 draft。
- C. 插件改写 `ai/tasks/<id>/{prd,design,implement}.md`，但不改 `task.md` 的 mode/status。
- D. 插件按模式写 `ai/tasks` 或 `.sbtd/tasks` 的 `task.md`，与 TaskStore 并列成为 writer。

推荐 A。理由：任务记录已有唯一 writer，删 Trellis 不应再开第二写入面，现成降级就是 draft。

---

**Q3** lessons 本 RC 的身份文件和写入路径是什么？今天身份只认 `.trellis/.developer` 的 `name=`，有 `.trellis/workflow.md` 就写 `.trellis/lessons/`，否则写 `docs/lessons/` 或 `docs/lessons.md`；本仓已有 `docs/lessons/index.md`，没有 `docs/spec/lessons.md`；lessons-record 的身份文件是 `.sbtd/developer`。

- A. 只写 v2：身份 `.sbtd/developer`（`^[a-z0-9]+$`，不猜测），库为 `docs/lessons/{index,topics,archive}`；不写 `.trellis`；仅有旧树时 record 返回迁移 skip，match/read 本 RC 仍可读旧树；不新建 `docs/spec/lessons.md`。
- B. 只认 v2，不读旧树；旧树项目的 record 和 match 都 skipped，直到人工迁走。
- C. 身份改为 `.sbtd/developer`，但有 `.trellis/workflow.md` 时仍写旧 lessons 树。

推荐 A。理由：删 Trellis 后端后不能再靠 workflow.md 决定写旧树，完全不读又会让已有 lessons 本 RC 不可查。

---

**Q4** strict/default/lite 由谁决定，插件如何得知当前模式？这不是 CONTEXT 的 Runtime Mode（`enforced|advisory`），也不是 Policy Profile（`strict|relaxed`）；插件今天没有该字段，section 和 hooks 对所有会话强制无计划禁改和 book review。

- A. 插件不推断：只接受工具参数或宿主注入的 workflow_mode，缺省当 default（不强制 book review 和无计划禁改），三种模式仍强制完整 grill 后的 DDD；不把「本仓每个任务用 strict」写进插件。
- B. 插件只读 active-task 指向的 task.md 里的 workflow_mode；没有或读失败则 default，并在结果里说明未读到。
- C. 插件硬编码始终 strict，因为本仓约定每个开发任务都用 strict。

推荐 A。理由：C 把本仓流程锁变成所有宿主项目的产品行为，B 把插件不拥有的 active 指针当成模式真源。

---

**Q5** `sbtd_*` 对外契约本 RC 允许多大的 breaking，迁移说明写在哪？现行对外是九个工具名加 `/sbtd` 的空、`plan`、`maestro`；`sbtd_validate` 返回字段名是 `gitnexus`，lessons 事件含 `gitnexus-mismatch`。

- A. 工具名和 `/sbtd` 子命令冻结；允许删除 `gitnexus` 字段并改为 `graft`，`gitnexus-mismatch` 同步改名，每项删除都写入本 RC 的 CHANGELOG 迁移说明，不留双字段。
- B. 工具名冻结，字段只增不删：保留 `gitnexus` 并标 deprecated，同时新增 `graft`。
- C. 工具名和字段都可以改，只在 README 写一句，不写迁移说明。

推荐 A。理由：已锁定本版替换 GitNexus，双字段是 shim；工具名已被宿主提示和测试当成契约。

---

**Q6** 0.2.0-rc.2 上怎样算 T0 通过，从而保留 `>=0.2.0-rc.2 <0.3.0-0`？退回范围已锁定；现行宿主兼容门是单测、pack 含 dist、临时 cell register smoke，人工最少项是 dsh web ask；npm peer 默认不含 includePrerelease，跨 patch rc 可能 ERESOLVE。0.2.1-rc.2 同一矩阵失败时发不发，留到下一轮。

- A. 通过线是 dsh plugin add 本地 tarball、九工具加 section 加 `/sbtd` 注册、pre-step notice 的 kind 为 `dsh-sbtd` 且不丢 `startsRequestSeries`、无 plan 的生产 edit 仍 ask；任一行失败则整段 range 退到 `>=0.2.1-rc.2 <0.3.0-0`；pnpm/npm ERESOLVE 只记录，不触发退 range。
- B. 与 A 相同，但临时 cell 对 `dsh@0.2.0-rc.2` 的 `pnpm add` 若 ERESOLVE 也算失败并退 range。
- C. 只以 register smoke 为退 range 判据；notice kind、`startsRequestSeries` 和人工 ask 不进退 range。

推荐 B。理由：现有 dsh-host-compat 已把 pack 后的 pnpm add 当 REQUIRED，只信 dsh 自己的解析会把已知的 npm peer 坑留到发布后。

---

**Q7** 0.2.0-rc.1 的方案文件叫什么，任务表放哪？现有设计是 `docs/prd/dsh-sbtd-technical-design-and-task-breakdown.v1.2.md`；`docs/TODO.md` 自述是进度真源，且仍停在 0.1.0-rc.3；表列已锁定。

- A. 新文件 `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 只写方案；任务表只放 `docs/TODO.md` 新节，PRD 链接过去，不改 v1.2 正文。
- B. 方案和任务表都在 `docs/prd/dsh-sbtd-0.2.0-rc.1.md`；TODO 每个里程碑只加一行指针，不复制整表。
- C. 方案和任务表都追加进 v1.2 新章；TODO 等到发版再改。

推荐 A。理由：TODO 已经是进度真源，整表再放进 PRD 会有两个 writer；v1.2 是上一代设计，不应改成这份未决草案。

---

**Q8** CHANGELOG 首建放哪、用什么格式？`packages/dsh-sbtd` 和仓库根都没有 CHANGELOG；包 `files` 目前只有 `dist/`、`cordis.patch.yml`、`manuals/`；README 是中文，omp-sbtd 的 CHANGELOG 是英文 Keep a Changelog。

- A. 只建 `packages/dsh-sbtd/CHANGELOG.md`，中文、最新在前，发布前用 `## [Unreleased]`，PR-D 改为 `## [0.2.0-rc.1] - <发布日>`，并加入 `files`。
- B. 只建仓库根 `CHANGELOG.md`，格式同 A，不进 npm tarball。
- C. 只建包内英文 Keep a Changelog，对齐 omp-sbtd，并加入 `files`。

推荐 A。理由：安装方拿到的是包不是单仓根，读者语言跟 README，而不是 omp-sbtd。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-17T21:43:53.329101+08:00 | planned | in-progress | 用户要求本任务直接进入 in-progress 做 grill | 用户 2026-10-17 明确新建 strict 共享任务并立即 grill；分支 docs/dsh-sbtd-0.2.0-rc.1-prd HEAD c44c45a46e1f28248f3c922275a991051b8e52b0 |
| 2026-10-17T22:26:30+08:00 | in-progress | in-progress | Round 1 决策锁定（Q1–Q9，采纳 Reviewy 版本） | 用户 2026-10-17 22:19 消息；本文件「Grill Round 1 锁定」小节 |
| 2026-10-17T23:18:59+08:00 | in-progress | in-progress | Round 2 决策锁定（Q1–Q6，采纳 Reviewy 版本） | 用户 2026-10-17 23:10 消息；本文件「Grill Round 2 锁定」小节 |
| 2026-10-18T00:28:09+08:00 | in-progress | in-progress | grill 完成并交付 DDD Boundary Review（done-pending-confirmation） | Round 1–3 全部锁定；/tmp/g020/ddd.md；本文件「DDD Boundary Review」小节 |
| 2026-10-18T00:34:44+08:00 | in-progress | in-progress | 用户确认 DDD Boundary Review | 群消息「确认」 |
| 2026-10-18T00:37:56+08:00 | in-progress | in-progress | 进入 PRD 撰写（DDD 经用户确认为 confirmed） | docs/prd/dsh-sbtd-0.2.0-rc.1.md；docs/TODO.md 第三节指针行；本文件「PRD 撰写」小节 |
| 2026-10-18T09:11:01+08:00 | in-progress | done | 记录回填：PR #93 已合并 | gh pr view 93：MERGED，headRefName=docs/dsh-sbtd-0.2.0-rc.1-prd 与 branch 一致；merge SHA 3fafd73f828b0f61c3310e4828cfb63bbced3f9a；mergedAt=2026-10-18T09:11:01+08:00；git %cI=2026-10-18T09:11:01+08:00；于 2026-10-23T10:35:03+08:00 回填 updated_at |

---

**Q9** strict 模式下 Graft 缺失（未安装、版本不对、调用失败或无图）是硬拦还是只告警？已锁定「Graft 必须可降级、不拒载、不卡会话」。

- A. 三种模式都只告警：返回 skipped 并写明 reason；strict 下把这一项标为「未证明」而不是 passed，不阻塞会话和 validate，交付时要求用其他证据（源码、LSP、契约影响分析）补上。
- B. strict 下硬拦：validate 的分析相位记为 blocked，必须装好 Graft 才能过；default/lite 只告警。
- C. 由项目规则决定：项目声明 Graft 必需时 strict 硬拦，否则同 A。

推荐 A。理由：B 和已锁定的可降级相冲突，而且会把插件绑到宿主安装状态上；C 要新增一个项目级配置面，本 RC 不值得。A 用「skipped 不等于 passed」守住 strict 的证据底线。

> 更正（OMP 22:12 补注）：Q7 推荐改为 B。用户已明确要求任务表放在 `docs/prd` 的 PRD 文档里，A 与之冲突。

## Grill Round 1 锁定（用户 2026-10-17 22:19，采纳 Reviewy 版本）

- Q1 A：Graft 只做只读查询，走已接线的 launcher；缺失/版本不对/失败返回 skipped 并写明 reason，不拒载。
- Q2 A：插件不写任何任务文件；sbtd_spec/sbtd_tickets 只返回草稿。
- Q3 A：lessons 库为 docs/lessons/{index,topics,archive}，身份 .sbtd/developer；不新建 docs/spec/lessons.md；旧 .trellis 树仍可读。（按 Round 3 Q6 C 精化：不新建短入口；已有短入口仍可写。）
- Q4（A+B 分层）：模式取值顺序 = 工具参数或宿主注入的 workflow_mode → active-task 指向的 task.md 里的 workflow_mode（只读）→ default；返回结果写明模式来源层；读失败按 default 并提示，不拒载。README/CHANGELOG 写明无模式时为 default、无 book 门禁。
- Q5 A：冻结工具名；gitnexus 改名 graft 并写迁移说明。
- Q6 B（Reviewy 22:24 精化）：pack 后完整 A 清单。回退判据：在下限上用 `npm install` 装 dsh@0.2.0-rc.2 加本插件，报 ERESOLVE 即退回 `>=0.2.1-rc.2 <0.3.0-0`；按现有 host-compat 跑 `pnpm add`，失败才算 T0 失败，peer 警告只记录、不触发回退；跨 patch rc 的 peer 警告或 ERESOLVE 只写进 CHANGELOG 部署边界。T0 记录逐步写明所用包管理器与 strict-peer-dependencies 设置（Reviewy 评审必查）。
- Q7 B：方案和任务表都在 docs/prd/dsh-sbtd-0.2.0-rc.1.md；docs/TODO.md 每个里程碑只加一行指针。回填规则：每个任务的 merge SHA 和 done 时间由下一个任务的 PR 回填；PR-D 合并后用一个小 docs PR 回填自己那行。
- Q8 双语：packages/dsh-sbtd 内 CHANGELOG.md（英文）与 CHANGELOG.zh.md（中文）一一对应、最新在前、都加入 files；发版前 [Unreleased]，PR-D 改为版本+日期。
- Q9 A：三种模式都只告警；strict 下该项标为「未证明」而非 passed，交付需用其他证据补。

## Grill Round 2

# Grill Round 2 — dsh-sbtd 0.2.0-rc.1

未选定答案，等待群投票。输入：Round 1 锁定（2026-10-17 22:19，Q1–Q9 采纳 Reviewy 版本）。已锁定不重问。

---

**Q1** T0 矩阵里 0.2.1-rc.2 的角色：退回范围 `>=0.2.1-rc.2 <0.3.0-0` 的下限就是它；若 0.2.0-rc.2 失败退回、而 0.2.1-rc.2 同矩阵也失败，本 RC 发不发？

- A. T0 同矩阵跑 0.2.0-rc.2 与 0.2.1-rc.2 两行：0.2.0 行失败 → range 退回且 0.2.1 行必须已通过；两行都失败 → 本 RC 不发，回炉宿主适配后再评。
- B. T0 只跑 0.2.0-rc.2 一行；退回后另起一轮只对 0.2.1-rc.2 补跑同矩阵，通过才发。
- C. 0.2.1-rc.2 只做 advisory register smoke，不阻塞发版；双失败也照发，把风险写进 CHANGELOG 部署边界。

推荐 A。理由：退回 range 的下限就是 0.2.1-rc.2，不事先验收等于退回一个未验证的宿主。

---

**Q2** devDep 精确钉哪个 dsh 版本？它决定本地构建、单测和钉版 smoke 的宿主事实。

- A. 钉 `0.2.0-rc.2`（range 下限），0.2.1-rc.2 由 T0 矩阵行覆盖；若 T0 退回，devDep 随 range 一并改钉 `0.2.1-rc.2`。
- B. 钉 `0.2.1-rc.2`（engines.dsh 优先的宿主行为从它开始），0.2.0-rc.2 只进 T0 矩阵。

推荐 A。理由：日常单测和构建应对齐支持范围下限，上限行为由矩阵证明；锁定的退回判据也以下限为主语。

---

**Q3** default/lite 下 hooks 的降级形态？strict 保持现行（无 plan 生产 edit ask，required book gate 未过 deny）；T0 清单已锁「无 plan 的生产 edit 仍 ask」，开放的只是 book gate deny 怎么降。

- A. 无 plan 生产 edit 仍 ask；required book gate 未过的 deny 降级为 inject notice，不拦截。
- B. 两条路径在 default/lite 都只 inject notice；无 plan 不再 ask。
- C. default/lite 完全不注入、不拦截，静默放行。

推荐 A。理由：与锁定的 T0 ask 行一致，只把强制 deny 收回 strict，不丢告警面；B 与 T0 锁定冲突。

---

**Q4** `sbtd_validate` 返回的 `graft` 字段用什么词表？现行 `AnalysisResult` 是 `status: ok|skipped|advisory`、`summary`、可选 `advisory`、`reason`，validate 用 `skipped→pre=skipped` 映射。

- A. 沿用 AnalysisResult 形状，另定 reason 词表（如 `launcher-missing`、`guard-failed`、`graph-missing`、`graph-stale`）；pre/post 映射不变。
- B. 新词表：`status: available|degraded|unavailable` + `detail`，与旧 GitNexus 形状彻底断开。
- C. 只保留 `status` 和 `summary`，不规定 reason 词表。

推荐 A。理由：改名不改形状是最小 diff，t9/t10 的 pre/post 语义和测试可直接迁移。

---

**Q5** PR-A 白名单加 sbtd-task 时，sync-manuals 是否连同它的 `references/` 一起拷进 manuals？钉死 SHA 上 sbtd-task 有 SKILL.md 加 7 个 reference 文件（含 strict.md、state.md、task-data.schema.json）；现行规则是每个 skill 拷 SKILL.md 加它自己的 references/。

- A. 按现行规则全拷 SKILL.md 加整个 references/，MANIFEST 逐文件记 sha256。
- B. 只拷 SKILL.md，为 sbtd-task 单开白名单例外。
- C. 全拷 references/ 但排除 task-data.schema.json 等非 md 文件。

推荐 A。理由：SKILL.md 正文直接引用 strict.md 和 state.md，部分拷贝让手册引用悬空；B 和 C 都是第二套拷贝规则。

---

**Q6** Q4 第二层（active-task 指向的 task.md）的读取边界：指针缺失、task.md 缺失或损坏、或其 branch 与当前分支不一致时怎么办？已锁定该层只读、读失败按 default 并提示、不拒载。

- A. 三种情况都按 default，返回写明来源层与原因；不读 branch 字段，不抛错。
- B. 缺失或损坏按 default；branch 不一致时同样按 default，但额外提示「任务属于其他分支」。
- C. branch 不一致时该层报错（不拒载插件），仍按 default。

推荐 A。理由：branch 裁决是 TaskStore 的职责；Q4 锁定只读 workflow_mode，插件不该解析 branch。

## Grill Round 2 锁定（用户 2026-10-17 23:10，采纳 Reviewy 版本）

- Q1 A：T0 同一矩阵跑 0.2.0-rc.2 与 0.2.1-rc.2 两行；0.2.0 行失败则 range 退回，且 0.2.1 行必须已通过；两行都失败则本 RC 不发，回炉宿主适配。
- Q2 A：devDep 精确钉 `0.2.0-rc.2`；T0 退回时随 range 一并改钉 `0.2.1-rc.2`。
- Q3 A：default/lite 下无 plan 生产 edit 仍 ask；required book gate 未过从 deny 降为 inject notice，不拦截；strict 不变。
- Q4 A：沿用 AnalysisResult 形状（ok|skipped|advisory + summary/reason），pre/post 映射不变；reason 词表为 `launcher-missing`、`version-unsupported`、`call-failed`、`guard-failed`、`graph-missing`、`graph-stale`，每个值都要有测试。
- Q5 A：sbtd-task 按现行规则同步 SKILL.md 加整个 references/，MANIFEST 逐文件 sha256；t4 原始字节比对必须覆盖非 md 文件 `task-data.schema.json`。
- Q6 B：插件只读 task.md 的 branch 字段做比较（不替 TaskStore 裁决）；指针缺失、task.md 缺失或损坏按 default；branch 不一致也按 default 并提示「任务属于其他分支」；来源层与原因写进返回结果；不抛错、不拒载。

注：Round 2 Q6 锁定为 B（读 branch 做比较并提示），Round 3 Q6 是另一题（lessons 新建落点）。

## Grill Round 3

# Grill Round 3 — dsh-sbtd 0.2.0-rc.1

未选定答案，等待群投票。输入：Round 1+2 全部锁定（采纳 Reviewy 版本）。已锁定不重问。

---

**Q1** section.ts 的静态文案怎么跟模式行为对齐？`apply()` 注册时拿不到会话模式（模式由工具参数/宿主注入/task.md 在调用时解析），现行文案对所有会话写死「未出计划不准改生产代码、命中 book gate 必须 sbtd_review 到通过态」，但锁定后这两条只在 strict 强制。

- A. 改成统一中性文案：写明 strict 下无计划禁改与 book gate 强制、default/lite 只告警不拦截；不随模式动态切换。
- B. 保留现行强制语气文案不改；行为降级由 hooks 决定，差异写进 README/CHANGELOG。
- C. section 删掉强制句，改由 pre-step 按解析到的模式动态注入对应提示。

推荐 A。理由：注册时拿不到模式，按模式切 section 不可行；B 让文案与行为脱节，会误导模型在 default 下仍以为被强制。

---

**Q2** 插件如何发现已接线的 Graft launcher，又怎么判定 `version-unsupported`？managed 规则禁止插件 spawn/init，版本信息不能靠跑 CLI 拿；GitNexus 旧实现是 serverName 注入（默认 `gitnexus`）加 `mcp__<server>__*` 工具名探测。

- A. 沿用 serverName 注入模式（默认 `sbtd-graft`），按 `mcp__<server>__graft_*` 探测；`version-unsupported` 只在宿主显式注入的版本声明不在支持集时产生，插件不主动探测版本。
- B. 不配置名字：扫描宿主工具表，任一 `*__graft_find_code` 存在即视为已接线；版本同样只认注入声明。
- C. 要求宿主必须注入 McpClient 和版本声明；无注入即 `launcher-missing`，不自探测。

推荐 A。理由：镜像 GitNexus 已验收的 Q6A 注入/探测模式，测试可直接迁移；B 的名字扫描会把别的 Graft 接线误当本插件后端。

---

**Q3** T0 矩阵两行（0.2.0-rc.2、0.2.1-rc.2）在哪执行？现行 `dsh-host-compat.yml` 是 workflow_dispatch，unit-pack 钉版 REQUIRED、候选矩阵 advisory；R2 Q1 已锁 0.2.1 行是 gate 性质。

- A. `dsh-host-compat.yml` 的 unit-pack 扩成两行 REQUIRED 矩阵（0.2.0-rc.2 加 0.2.1-rc.2），保持 workflow_dispatch，红即停。
- B. unit-pack 钉 0.2.0-rc.2 REQUIRED；0.2.1-rc.2 行用本地 cell 人工跑，结果记进 T0 证据。
- C. 两行都本地人工跑，CI 不动，T0 证据只贴群里。

推荐 A。理由：R2 已把 0.2.1 行定为 gate，本地人工行不可复盘；现有 workflow 本就是 dispatch 模式，扩行不改变触发策略。

---

**Q4** 「返回结果写明模式来源层」落在哪些表面？锁定只要求写明来源层，没说哪些返回要加字段。

- A. 只有行为随模式变化的表面写：`sbtd_plan`、`sbtd_review`、`sbtd_validate` 返回加 `workflowMode` 和 `workflowModeSource`，`/sbtd` status 显示；其余工具不动。
- B. 九个工具返回统一加 `workflowMode` 和 `workflowModeSource`，保持契约一致。
- C. 不动任何工具返回；模式来源只出现在 hooks 的 notice 文案和 `/sbtd` status。

推荐 A。理由：Q5 已冻结工具名，字段变更要最小且有迁移说明；给不受影响的工作加字段是契约噪音。

---

**Q5** 删除 Trellis 后端后，「旧 .trellis lessons 树仍可读」按什么判定？lessons.ts 今天靠 trellis 后端的 `detect()`（看 `.trellis/workflow.md`）决定写旧树；后端删除后该依赖没了。

- A. 只认 `.trellis/lessons/index.md` 存在即可读，不再看 `.trellis/workflow.md`；有 workflow.md 但没有 lessons 树时按无旧树处理。
- B. 保留「workflow.md 存在才认旧树」的语义，把 detect 逻辑复制进 lessons 模块，不引用被删的后端文件。
- C. 旧树可读还要求 `.trellis/.developer` 存在，与旧身份同源。

推荐 A。理由：删后端后 lessons 语义不该再挂在 workflow.md 上；树在就该能读，与能否写（v2 身份）解耦。

---

**Q6** lessons record 的新建落点：Q3 已锁只写 v2 路径（`docs/spec/lessons.md`、`docs/lessons/**`），旧 `.trellis` 树只读；但现行 flat `docs/lessons.md` 是 v1 插件产物，锁里没提。

- A. 解析链：已有 `docs/lessons/index.md` 写 layered；否则已有 `docs/spec/lessons.md` 写短入口；只有 flat `docs/lessons.md` 时 record 返回迁移 skip（match/read 仍读）；都没有时新建 `docs/spec/lessons.md` 短入口。
- B. 读取链同 A，但 flat 项目由插件把内容迁进 `docs/spec/lessons.md` 后继续写。
- C. 都没有时新建 `docs/lessons/` layered 完整库，永不新建短入口；flat 同 A 处理。

推荐 A。理由：Q3 已锁只写 v2，flat 按旧树同规则迁移 skip 最一致；B 让插件迁用户文件，超出本 RC 边界。

## Grill Round 3 锁定（用户 2026-10-18 00:24，采纳 Lord/Reviewy 版本）

- Q1 A：section.ts 改成统一中性文案：写明 strict 下无计划禁改与 book gate 强制、default/lite 只告警不拦截；不随模式动态切换。
- Q2 A：沿用 serverName 注入（默认 `sbtd-graft`），按 `mcp__<server>__graft_*` 探测；`version-unsupported` 只在宿主显式注入的版本声明不在支持集时产生，插件不主动探测版本。
- Q3 A：`dsh-host-compat.yml` unit-pack 扩成两行 REQUIRED 矩阵（0.2.0-rc.2 + 0.2.1-rc.2），保持 workflow_dispatch，红即停。
- Q4 A：仅 `sbtd_plan`/`sbtd_review`/`sbtd_validate` 返回加 `workflowMode` 与 `workflowModeSource`，`/sbtd` status 显示；其余工具不动。hooks 注入的 notice 文案也要带上模式和来源层。
- Q5 A：只认 `.trellis/lessons/index.md` 存在即可读旧树，不再看 `.trellis/workflow.md`；有 workflow.md 但无 lessons 树时按无旧树处理。
- Q6 C：已有 `docs/lessons/index.md` 写 layered；已有 `docs/spec/lessons.md` 写短入口（只写已有文件，不新建短入口）；只有 flat `docs/lessons.md` 时 record 返回迁移 skip（match/read 仍读）；都没有时新建 `docs/lessons/` layered，永不新建短入口。同时已修正 Round 1 Q3 锁定摘要。

## 状态事件（续）

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-18T00:25:08+08:00 | in-progress | in-progress | Round 3 锁定（Q1–Q5 A，Q6 C；修正 Round 1 Q3 摘要） | 用户 2026-10-18 采纳 Lord 建议 |

## DDD Boundary Review

grill 完成标记：grill-with-docs 会话已于 2026-10-18 完成（Round 1–3 全部锁定，frontier 为空）。以下为 book-ddd-distilled-modeling 的独立第二遍复审。

# DDD Boundary Review — dsh-sbtd 0.2.0-rc.1

前置：grill-with-docs 会话已完成（Round 1–3 全部锁定，frontier 为空）。本复审是 grill 后的独立第二遍，依据 task.md 锁定小节与已核对的源码/文档事实，不重复访谈内容。

Status: confirmed（用户 2026-10-18 00:34 确认）

## 统一语言（Ubiquitous language）

| 术语 | 含义（本决策集） | 不得混用 |
|---|---|---|
| workflow_mode | sbtd-task 的执行模式：`strict`/`default`/`lite`；由用户选择或 task.md 记录，插件分层只读 | CONTEXT.md 的 Runtime Mode（`enforced`/`advisory`）与 Policy Profile（`strict`/`relaxed`） |
| Runtime Mode | KPi 语境的会话级 enforced/advisory，本插件不实现 | workflow_mode |
| clarify mode | `sbtd_clarify` 的 `docs`/`generic` 访谈模式 | workflow_mode |
| Book Gate | 插件 BookGatePlan 的 legacy/refactor/ddd/ddia/release 五门 | CI 的 REQUIRED 门、T0 矩阵行 |
| T0 矩阵行 | 宿主版本 × 验收清单的一行（0.2.0-rc.2、0.2.1-rc.2），CI REQUIRED | Book Gate |
| 后端（backend） | 可选能力提供方：Trellis/GitNexus（删除）、Graft（本版接入）、Maestro | sbtd-task 任务存储 |
| 任务（task） | sbtd-task 的 task.md 记录（唯一 writer：TaskStore）；历史语境指 .trellis 任务 slug；PRD 任务表行是计划条目 | 三者不再共用写入面 |
| lessons 库 | v2：`docs/lessons/{index,topics,archive}`；已有 `docs/spec/lessons.md` 是短入口（只写已有文件，不新建） | v1 flat `docs/lessons.md`、旧 `.trellis/lessons/` 树（均只读） |
| 身份 | lessons 写入署名：`.sbtd/developer` 的 `name=`（`^[a-z0-9]+$`），不猜测 | 旧 `.trellis/.developer`（只读兼容） |
| graft 字段 | `sbtd_validate` 返回里的分析结果对象，沿用 AnalysisResult 形状 | 旧名 `gitnexus` 字段（本版改名，写迁移说明） |
| skipped | 后端不可用时的结构化降级（带 reason），不等于 passed | strict 下记「未证明」，交付需其他证据补 |
| draft | `sbtd_spec`/`sbtd_tickets` 的唯一输出形态（不落盘） | 旧 `writeArtifact` 写盘行为（移除） |

## 限界上下文（Bounded contexts）

1. **dsh 宿主**：拥有 agent loop、工具注册、会话消息格式（V4 `source.kind`、`startsRequestSeries`）、审批（ask）、MCP 接线、插件生命周期（`apply`/`inject`）。
2. **dsh-sbtd 插件**：SBTD 适配器。拥有会话内 BookGatePlan（state.ts 的 Map）、九个 `sbtd_*` 工具、hooks、section、`/sbtd` 命令、manuals 只读消费。
3. **sbtd-task 任务真源**：TaskStore 唯一拥有 task.md 的 mode/status/事件与 active-task 指针；插件只是只读读者。
4. **Graft 结构证据**：managed launcher 拥有图数据与 guard；插件的分析后端只是查询调用方。
5. **640-skills manuals 供应链**：上游仓库与 sync-manuals.sh 拥有内容；插件 manuals/ 是带 sha256 的只读快照。
6. **lessons 库**：lessons-record 规则拥有格式与身份；`sbtd_lessons` 是 v2 路径的写入执行者。

## 聚合与所有者

- **BookGatePlan**（插件会话态聚合）：gates 五门 + requirement/reviewStatus；strict 下由 hooks 强制，default/lite 只告警；DDD 门三模式都强制（完整 grill 后）。
- **TaskRecord**（TaskStore 聚合）：插件不进入其写入面（Q2 A）；只读 workflow_mode 与 branch 比较（R2 Q6 B）。
- **Lesson**（`LESSON-YYYYMMDD-<name>-<slug>`）：写入只走 v2 路径 + 已有短入口；身份缺失不猜；flat/旧树 record 一律迁移 skip。
- **AnalysisResult（graft）**：插件拥有的对外契约；status `ok|skipped|advisory` + reason 六值词表；post 只随测试失败 blocked。
- **WorkflowModeResolution**：分层规则（参数/宿主注入 → active-task task.md → default）+ 来源层标注；解析失败一律 default 并提示，不抛错、不拒载。
- **Manual**：只读快照聚合；sync-manuals.sh 是唯一 writer，MANIFEST 逐文件 sha256（含非 md 的 task-data.schema.json）。

## 上下文映射与防腐层

- **dsh 宿主 ↔ 插件**：ACL = 本地宿主类型 + `inject`（tools/systemPrompt/commands）；不 import `@deepseek-ai/dsh` 类型。V4 会话格式适配（`kind:'dsh-sbtd'`、识别兼容迁移后的 `'plugin:dsh-sbtd'`、`startsRequestSeries` 保留）是该 ACL 的翻译层，归 PR-C。
- **sbtd-task 任务真源 ↔ 插件**：单向只读。插件读 `.sbtd/active-task.json` 与 task.md 的 workflow_mode/branch；任何读取失败（缺失/损坏/分支不一致）按 default 并提示，不替 TaskStore 裁决。
- **Graft ↔ 分析后端**：serverName 注入（默认 `sbtd-graft`）+ `mcp__<server>__graft_*` 探测为防腐层入口；AnalysisResult 形状把 validate 与 Graft 工具细节隔离；launcher 缺失/guard 失败/图缺失/图过期全部译成 skipped+reason，插件永不 init/spawn/写 MCP。
- **640-skills manuals ↔ 同步脚本**：sync-manuals.sh 单向同步白名单（删 trellis-workflow、加 sbtd-task 含整个 references/），checksum 失败非 0 退出；运行时工具只读 `manuals/<id>/SKILL.md`，不回写。

## 子域分级

- **Core**：BookGatePlan 门禁与 workflow_mode 分层（本插件的差异化行为）。
- **Supporting**：lessons 记录、validate 分析相位、hooks notice/ask。
- **Generic**：manuals 同步（纯供应链）、Graft 探测（通用能力发现）。

## 不变量与业务规则

1. 插件不拒载：后端、模式、任务指针的任何失败都降级为 skipped/default+提示；`apply()` 的 fail-closed 仅指宿主能力探测，与可选后端降级不冲突。
2. task.md 唯一 writer 是 TaskStore；插件只读，不写任何任务文件。
3. lessons record 只写 v2 路径与已有短入口；身份缺失/非法不猜、不写。
4. Graft skipped ≠ passed；strict 下记「未证明」，交付需源码/LSP/契约证据补。
5. 工具名与 `/sbtd` 子命令冻结；`gitnexus`→`graft` 一次性改名并写迁移说明，不留双字段。
6. T0 两行矩阵 REQUIRED、红即停；双失败不发本 RC；npm 下限 ERESOLVE 触发 range 退回，pnpm add 失败算 T0 失败，peer 警告只记 CHANGELOG 部署边界。
7. manuals 只读同步；checksum 失败即失败，不部分生效。

## 与 PRD→PR-A~PR-D 切分的吻合度

- PRD 文档先行（含任务表与回填规则）：纯计划产物，无模型耦合。吻合。
- PR-A 手册：Generic 供应链，独立成 PR。吻合。
- PR-B 后端：四个主题（sbtd-task 只读层、模式门禁、lessons v2、Graft 后端）各对应一个聚合，边界互不交叉。吻合。
- PR-C 宿主适配 + T0：ACL 翻译层 + 验收矩阵。吻合。
- 文档/CHANGELOG 与 PR-D 发版：发布面收口。吻合。
- 唯一接缝风险：hooks.ts 被 PR-B（模式门禁）与 PR-C（V4 格式）先后触及；顺序已锁 B→C，rebase 面可控。

## 对 grill 结果的修正

- Round 1 Q3 锁定摘要的括号「短入口不在写入面」按 Round 3 Q6 C 精化：**不新建** `docs/spec/lessons.md`，但已存在的短入口文件仍接受写入。以 Q6 C 为准。
- 其余无修正；三轮锁定相互一致。

## 风险与待确认点

1. hooks.ts 双 PR 触及（PR-B/PR-C），合并顺序已锁，需在 PR-C rebase 时复核 runPreStep 两处改动不互相覆盖。
2. clarify.ts/review.ts 运行时是否引用 trellis-workflow 手册：PR-A 实现期用 grep 核实并随白名单删除一并清理（实现核查项，非决策）。
3. 「## 状态事件（续）」是宿主写入的第二张事件表；TaskStore 只认精确标题「状态事件」，续表不进 helper 历史链。本复审保留原样，后续事件写入主表。
4. dsh 0.2.x 适配点清单（kind、startsRequestSeries、peer/engines 之外是否还有 break）：PR-C 执行期以宿主 changelog 核实，不属于 grill 决策。
5. CONTEXT.md 未改：本任务只产任务级复审；稳定跨任务术语（workflow_mode 与 Runtime Mode 的区分）是否录入 docs/CONTEXT.md 留待用户确认后另行处理。

Open conflicts and questions: 无阻塞项；第 1、2、4 条是实现期核查/执行项，第 5 条待用户确认。

## PRD 撰写

- 产物：`docs/prd/dsh-sbtd-0.2.0-rc.1.md`（元信息、背景目标、Round 1–3 锁定全文转写、DDD 摘要、任务表、验收要点、非目标）。
- 任务表：7 行（0 PRD、A manuals、B 后端、C 宿主适配+T0、D 文档/CHANGELOG、E 发版 PR-D、F 回填小 docs PR）× 8 列（序号/任务/优先级/状态/PR/merge SHA/done 时间/strict 任务记录路径）；行 0 状态 in-progress，其余 planned。
- TODO：`docs/TODO.md` 第三节加一行指针（顺序 3），不复制整表。
- 下一步：commit → PR → Reviewy 评审；CLEAN 后进入 PR-A（开发前新建 strict 任务）。
| 2026-10-18T09:06:13+08:00 | in-progress | in-progress | 补齐 CONTEXT + Q&A 附录并开 PRD PR | Lord 09:05 催办 |

## 当前值（offline-cache chore 记录回填）

- PR #93 已合并，status = done；completed_at 取 merge commit 时间。上文进度及下一步保留为历史。用户明确授权本次仅修正文档状态，不重绑定历史 branch，不补造旧事件或重跑历史门禁。
