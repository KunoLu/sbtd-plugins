# dsh-sbtd 0.2.0-rc.1 升级方案（PRD）

> 状态：已锁定（grill Round 1–3 + DDD Boundary Review confirmed）
> 日期：2026-10-18（Asia/Shanghai）
> strict 任务记录：`ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md`

---

## 0. 元信息

| 项 | 值 |
|---|---|
| 版本 | `@kunolu/dsh-sbtd@0.2.0-rc.1` |
| 发布通道 | 只发 npm dist-tag `next`；`latest` 不动（仍 `0.1.0-rc.1`） |
| 基线 | 分支 `docs/dsh-sbtd-0.2.0-rc.1-prd`，基于 origin/main `c44c45a46e1f28248f3c922275a991051b8e52b0` |
| manuals 上游钉 | 640-skills `v2.0.2` / `1d82494d74f6df9bca7dccef2da409f87091883e` |
| dsh 宿主范围 | peerDependencies 与 engines.dsh 写同一范围，初始 `>=0.2.0-rc.2 <0.3.0-0`；T0 按锁退回则改 `>=0.2.1-rc.2 <0.3.0-0` |
| devDep | 精确钉 `@deepseek-ai/dsh@0.2.0-rc.2`；T0 退回时随 range 一并改钉 `0.2.1-rc.2` |
| 版本号说明 | 0.x 的 minor 表示 breaking；与 dsh 0.2 同号是巧合，不表示对齐 |

## 1. 背景与目标

从 `@kunolu/dsh-sbtd@0.1.0-rc.3` 升级，适配 dsh 0.2 宿主（latest `0.2.0-rc.2`，next `0.2.1-rc.2`；0.2.0-rc.2 只检查 peer，0.2.1 起 engines.dsh 优先，均 `includePrerelease:true`；npm peer 默认不带 includePrerelease）。本版删除 Trellis 与 GitNexus 后端，把 GitNexus 换成 Graft（未安装时可降级、不拒载），手册从 trellis-workflow 迁到 sbtd-task（v2 规则）。

## 2. 已锁定决策（全文转写）

来源：`ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md` 三个锁定小节，原样转写。

### 2.1 Round 1 锁定（用户 2026-10-17 22:19，采纳 Reviewy 版本）

- Q1 A：Graft 只做只读查询，走已接线的 launcher；缺失/版本不对/失败返回 skipped 并写明 reason，不拒载。
- Q2 A：插件不写任何任务文件；sbtd_spec/sbtd_tickets 只返回草稿。
- Q3 A：lessons 库为 docs/lessons/{index,topics,archive}，身份 .sbtd/developer；不新建 docs/spec/lessons.md；旧 .trellis 树仍可读。（按 Round 3 Q6 C 精化：不新建短入口；已有短入口仍可写。）
- Q4（A+B 分层）：模式取值顺序 = 工具参数或宿主注入的 workflow_mode → active-task 指向的 task.md 里的 workflow_mode（只读）→ default；返回结果写明模式来源层；读失败按 default 并提示，不拒载。README/CHANGELOG 写明无模式时为 default、无 book 门禁。
- Q5 A：冻结工具名；gitnexus 改名 graft 并写迁移说明。
- Q6 B（Reviewy 22:24 精化）：pack 后完整 A 清单。回退判据：在下限上用 `npm install` 装 dsh@0.2.0-rc.2 加本插件，报 ERESOLVE 即退回 `>=0.2.1-rc.2 <0.3.0-0`；按现有 host-compat 跑 `pnpm add`，失败才算 T0 失败，peer 警告只记录、不触发回退；跨 patch rc 的 peer 警告或 ERESOLVE 只写进 CHANGELOG 部署边界。T0 记录逐步写明所用包管理器与 strict-peer-dependencies 设置（Reviewy 评审必查）。
- Q7 B：方案和任务表都在 docs/prd/dsh-sbtd-0.2.0-rc.1.md；docs/TODO.md 每个里程碑只加一行指针。回填规则：每个任务的 merge SHA 和 done 时间由下一个任务的 PR 回填；PR-D 合并后用一个小 docs PR 回填自己那行。
- Q8 双语：packages/dsh-sbtd 内 CHANGELOG.md（英文）与 CHANGELOG.zh.md（中文）一一对应、最新在前、都加入 files；发版前 [Unreleased]，PR-D 改为版本+日期。
- Q9 A：三种模式都只告警；strict 下该项标为「未证明」而非 passed，交付需用其他证据补。

### 2.2 Round 2 锁定（用户 2026-10-17 23:10，采纳 Reviewy 版本）

- Q1 A：T0 同一矩阵跑 0.2.0-rc.2 与 0.2.1-rc.2 两行；0.2.0 行失败则 range 退回，且 0.2.1 行必须已通过；两行都失败则本 RC 不发，回炉宿主适配。
- Q2 A：devDep 精确钉 `0.2.0-rc.2`；T0 退回时随 range 一并改钉 `0.2.1-rc.2`。
- Q3 A：default/lite 下无 plan 生产 edit 仍 ask；required book gate 未过从 deny 降为 inject notice，不拦截；strict 不变。
- Q4 A：沿用 AnalysisResult 形状（ok|skipped|advisory + summary/reason），pre/post 映射不变；reason 词表为 `launcher-missing`、`version-unsupported`、`call-failed`、`guard-failed`、`graph-missing`、`graph-stale`，每个值都要有测试。
- Q5 A：sbtd-task 按现行规则同步 SKILL.md 加整个 references/，MANIFEST 逐文件 sha256；t4 原始字节比对必须覆盖非 md 文件 `task-data.schema.json`。
- Q6 B：插件只读 task.md 的 branch 字段做比较（不替 TaskStore 裁决）；指针缺失、task.md 缺失或损坏按 default；branch 不一致也按 default 并提示「任务属于其他分支」；来源层与原因写进返回结果；不抛错、不拒载。

注：Round 2 Q6 锁定为 B（读 branch 做比较并提示），Round 3 Q6 是另一题（lessons 新建落点）。

### 2.3 Round 3 锁定（用户 2026-10-18 00:24，采纳 Lord/Reviewy 版本）

- Q1 A：section.ts 改成统一中性文案：写明 strict 下无计划禁改与 book gate 强制、default/lite 只告警不拦截；不随模式动态切换。
- Q2 A：沿用 serverName 注入（默认 `sbtd-graft`），按 `mcp__<server>__graft_*` 探测；`version-unsupported` 只在宿主显式注入的版本声明不在支持集时产生，插件不主动探测版本。
- Q3 A：`dsh-host-compat.yml` unit-pack 扩成两行 REQUIRED 矩阵（0.2.0-rc.2 + 0.2.1-rc.2），保持 workflow_dispatch，红即停。
- Q4 A：仅 `sbtd_plan`/`sbtd_review`/`sbtd_validate` 返回加 `workflowMode` 与 `workflowModeSource`，`/sbtd` status 显示；其余工具不动。hooks 注入的 notice 文案也要带上模式和来源层。
- Q5 A：只认 `.trellis/lessons/index.md` 存在即可读旧树，不再看 `.trellis/workflow.md`；有 workflow.md 但无 lessons 树时按无旧树处理。
- Q6 C：已有 `docs/lessons/index.md` 写 layered；已有 `docs/spec/lessons.md` 写短入口（只写已有文件，不新建短入口）；只有 flat `docs/lessons.md` 时 record 返回迁移 skip（match/read 仍读）；都没有时新建 `docs/lessons/` layered，永不新建短入口。同时已修正 Round 1 Q3 锁定摘要。

### 2.4 DDD Boundary Review 摘要

Status：confirmed。全文见 `ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md` 末节。

- 限界上下文：dsh 宿主 / dsh-sbtd 插件 / sbtd-task 任务真源 / Graft 结构证据 / 640-skills manuals 供应链 / lessons 库，六个上下文各自拥有数据与生命周期。
- 防腐层：宿主↔插件走本地宿主类型加 inject（不 import dsh 类型，V4 kind 适配在 PR-C）；任务真源↔插件单向只读；Graft↔分析后端用 serverName 注入与 AnalysisResult 隔离；manuals↔sync-manuals.sh 单向同步、checksum 失败即失败。
- 不变量：插件不拒载；task.md 唯一 writer 是 TaskStore；lessons 只写 v2 路径与已有短入口、身份不猜；Graft skipped ≠ passed（strict 记「未证明」）；工具名冻结、字段一次性改名带迁移说明；T0 两行 REQUIRED、双失败不发；manuals 同步不部分生效。
- PR 切分吻合：PRD → PR-A（供应链）→ PR-B（四个聚合各一主题）→ PR-C（ACL 翻译层 + T0）→ 文档/CHANGELOG → PR-D（发版）均吻合；唯一接缝是 hooks.ts 被 PR-B 与 PR-C 先后触及，顺序已锁 B→C。
- 风险：hooks.ts 双 PR 触及需 rebase 复核；clarify/review 对 trellis-workflow 手册的运行时引用随 PR-A 核实清理；dsh 0.2.x 适配点完整性在 PR-C 以宿主 changelog 核实；workflow_mode 与 Runtime Mode／Policy Profile 的区分已写入 docs/CONTEXT.md（本 PR 同步）。

## 3. 任务表

回填规则：每个任务的 merge SHA 与 done 时间由**下一个**任务的 PR 回填；PR-D 合并后由 F（小 docs PR）回填自己那行。PR 合并后删本地+远程任务分支。每完成一行更新本表状态。

| 序号 | 任务 | 优先级 | 状态 | PR | merge SHA | done 时间 | strict 任务记录路径 |
|---|---|---|---|---|---|---|---|
| 0 | PRD 本文档 | 1 | done | [#93](https://github.com/KunoLu/sbtd-plugins/pull/93) | `3fafd73f828b0f61c3310e4828cfb63bbced3f9a` | 2026-10-18T09:11:01+08:00（以 merge commit 时间记，非 API merged_at） | `ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md` |
| A | manuals：白名单删 trellis-workflow、加 sbtd-task 含整个 references/；MANIFEST 逐文件 sha256；t4 字节比对覆盖 `task-data.schema.json`；PINNED_REVISION → v2.0.2 SHA `1d82494d` | 2 | in-progress | PR-A | — | — | `ai/tasks/dsh-sbtd-0-2-0-rc-1-pr-a-manuals/task.md` |
| B | 后端：sbtd-task 只读层 + workflow_mode 分层；hooks/section 模式门禁；lessons v2 落点；Graft 后端 + 六 reason | 3 | planned | PR-B | — | — | —（开发前新建 strict 任务） |
| C | 宿主适配 + T0：V4 `kind:'dsh-sbtd'` 且识别兼容 `'plugin:dsh-sbtd'`；runPreStep 保留 `startsRequestSeries`；peer/engines.dsh 同范围；CI 两行 REQUIRED；npm ERESOLVE / pnpm add 判据 | 4 | planned | PR-C | — | — | —（开发前新建 strict 任务） |
| D | 文档/CHANGELOG 双语 [Unreleased]：`packages/dsh-sbtd/CHANGELOG.md` + `CHANGELOG.zh.md` 一一对应、最新在前、加入 files；TODO 指针 | 5 | planned | 文档 PR（PR-C 后、PR-D 前） | — | — | —（开发前新建 strict 任务） |
| E | 发版：bump `0.2.0-rc.1`、`npm publish --tag next`、双语 Release/tag 走 bilingual-release-notes | 6 | planned | PR-D | — | — | —（开发前新建 strict 任务） |
| F | PR-D 合并后小 docs PR：回填 E 行的 merge SHA 与 done 时间 | 7 | planned | 小 docs PR | — | — | —（开发前新建 strict 任务） |

## 4. 验收要点

- **T0 清单**（引用锁定，不复制）：R1 Q6 B 精化（pack 后完整 A 清单；npm 下限 ERESOLVE 退回 range；pnpm add 失败才算 T0 失败；peer 警告只记 CHANGELOG 部署边界；记录包管理器与 strict-peer-dependencies）+ R2 Q1 A（两行矩阵，双失败不发）+ R3 Q3 A（`dsh-host-compat.yml` unit-pack 两行 REQUIRED、workflow_dispatch、红即停）。
- **Graft 降级**：launcher-missing / version-unsupported / call-failed / guard-failed / graph-missing / graph-stale 六个 reason 每个都有测试；skipped 不阻断 validate，post 只随测试失败 blocked。
- **模式来源字段表面**：`sbtd_plan`/`sbtd_review`/`sbtd_validate` 返回 `workflowMode` + `workflowModeSource`；`/sbtd` status 显示；hooks notice 文案带模式与来源层；其余工具不动。
- **lessons 落点**：R3 Q6 C 解析链（layered → 已有短入口 → flat 迁移 skip → 都没有新建 layered）；旧 `.trellis` 树按 `.trellis/lessons/index.md` 存在即可读；身份只认 `.sbtd/developer`。

## 5. 非目标

- 不 bump `latest`（仍 `0.1.0-rc.1`）。
- 不自动迁移用户 flat `docs/lessons.md` 或旧 `.trellis` lessons 树（record 只返回迁移 skip）。
- 插件不写 `task.md`、`.sbtd`、`ai/tasks` 或任何任务文件。
- 不 init/spawn 上游 Graft，不写 MCP 配置，只走已接线的 managed launcher。

## 附录 A. 三轮 Grill 完整 Q&A（题干 + 选定答案）

各轮末尾的「选定」汇总与第 2 节为锁定答案；下面保留原题与当时推荐，不用加粗标记选项。推荐与最终选定不同时，以锁定答案为准。

### A.1 Round 1

# Grill Round 1 — dsh-sbtd 0.2.0-rc.1


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

---

**Q9** strict 模式下 Graft 缺失（未安装、版本不对、调用失败或无图）是硬拦还是只告警？已锁定「Graft 必须可降级、不拒载、不卡会话」。

- A. 三种模式都只告警：返回 skipped 并写明 reason；strict 下把这一项标为「未证明」而不是 passed，不阻塞会话和 validate，交付时要求用其他证据（源码、LSP、契约影响分析）补上。
- B. strict 下硬拦：validate 的分析相位记为 blocked，必须装好 Graft 才能过；default/lite 只告警。
- C. 由项目规则决定：项目声明 Graft 必需时 strict 硬拦，否则同 A。

推荐 A。理由：B 和已锁定的可降级相冲突，而且会把插件绑到宿主安装状态上；C 要新增一个项目级配置面，本 RC 不值得。A 用「skipped 不等于 passed」守住 strict 的证据底线。

> 更正（OMP 22:12 补注）：Q7 推荐改为 B。用户已明确要求任务表放在 `docs/prd` 的 PRD 文档里，A 与之冲突。


**Round 1 选定：** Q1 A · Q2 A · Q3 A（后按 R3 Q6 C 精化：不新建短入口；已有短入口仍可写）· Q4 A+B 分层 · Q5 A · Q6 B（Reviewy 精化：npm ERESOLVE / pnpm add）· Q7 B · Q8 双语 CHANGELOG.md + CHANGELOG.zh.md · Q9 A。

### A.2 Round 2

# Grill Round 2 — dsh-sbtd 0.2.0-rc.1


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
> 锁定说明：本题最终选定 **B**；上方「推荐 A」仅保留当时的评审历史，实施按第 2.2 节 Q6 执行。


**Round 2 选定：** Q1 A · Q2 A · Q3 A · Q4 A（reason 六值：`launcher-missing`、`version-unsupported`、`call-failed`、`guard-failed`、`graph-missing`、`graph-stale`）· Q5 A（含 `task-data.schema.json`）· Q6 B。

### A.3 Round 3

# Grill Round 3 — dsh-sbtd 0.2.0-rc.1


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


**Round 3 选定：** Q1 A · Q2 A · Q3 A · Q4 A（hooks notice 亦带模式与来源层）· Q5 A · Q6 **C**（不新建短入口；已有短入口仍可写；都没有时新建 layered）。
