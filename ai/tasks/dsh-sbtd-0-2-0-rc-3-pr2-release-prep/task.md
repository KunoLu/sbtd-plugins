---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-3-pr2-release-prep
workflow_mode: strict
mode_source: user
mode_note: 用户17:05批准PR2，当前消息进一步确认17:15扩围裁决，仅额外允许10个src文件的9项格式/2项安全导入排序，单独提交；其后继续原11文件，失败停报；本次只到验证/push/PR/同SHA CI，不合入或发布。
status: in-progress
branch: docs/dsh-sbtd-0.2.0-rc.3-pr2-plan
created_at: '2026-11-18T16:52:23.411687+08:00'
updated_at: '2026-11-18T17:45:37+08:00'
completed_at: null
---

# dsh PR2：0.2.0-rc.3 发版准备（17:05 已批准，执行记录）

## 本次 checker 纠正授权（2026-11-18T17:31:25+08:00）

- 当前用户明确授权一次临时验证方法纠正，属于已有 10 文件授权的验证工作，不增加产品范围。原 checker exit 1 仅保留为临时校验器缺陷；旧 lint 失败、checker 失败与取证错误及时间不覆盖、不追改成通过。
- 入口仍为原 PR2 分支/基线 `9b2610265d0f205bf8ed7dfa5167d664f0312bcd`，仅本 task 未跟踪，远端 main 未前进；无新增 writer 信号。按已知 in-progress 前态解除 blocked，恢复剩余工作。
- 新 checker 排除 SourceFile.text 全文、位置、parent、注释等非语义数据；保留有意义 token、表达式/初始化及模块声明顺序，不对任意 AST 子节点排序。命名绑定仅在明确核对模块顺序、绑定映射与 type-only 变化后按声明语义比较，不能假设排序自动安全。
- 先用独立正反样例证明空白通过、表达式变化拒绝、副作用 import 换序拒绝，再审查实际十文件。预期阴性被拒绝是 checker 自测成功；无法证明实际候选安全或发生模块/初始化顺序变化仍停报。
- 自测和十文件证明写入新的 ignored reports；只在有效证明后应用源码补丁、lint attempt 2 与独立 lint 提交，再执行原 11 文件和全部真实门禁。本轮仍仅至 PR/同 SHA CI，task 最终 checking，禁止自报 CLEAN/done、合入或发布。

## Checker v2 自测与十文件证明（2026-11-18T17:39:01+08:00）

- 新方法 `reports/lint-equivalence-v2.cjs` 自测 10/10 通过：3 个等价正例通过，7 个预期阴性被正确拒绝（表达式、模块副作用顺序、初始化顺序、单目 token、const/let、type-only→runtime、绑定别名变化）。阴性拒绝是自测成功，不是产品失败；原 checker/取证失败记录完整保留。
- 十个实际候选逐一通过四项比较：type-only/绑定身份、非模块 TS 结构、有序运行时结构、有序模块声明与绑定。仅声明绑定映射采用集合比较；模块声明、表达式和初始化顺序不排序；SourceFile.text/位置/parent/注释不进入语义摘要。原始/候选内容、SHA 与具体模块/绑定清单在新 JSON 证据中。
- index 人工核对：仅同一声明内命名/type 项排序及同一 `./commands/sbtd.js` 的 type-only 导出块移动；运行时模块来源和声明位置未变。lessons 仅将同一 `node:fs` 声明内 `type Stats` 调整位置，运行时导入列表及顺序未变。两文件的实际绑定和 type-only 身份均逐项相等，不是假设“排序必然安全”。
- LSP organize action 不可用已保留；Biome stdin 候选用临时参数隔离 import assist，未写源文件、未改配置。实际 lint 门禁仍完整执行原 `pnpm --filter @kunolu/dsh-sbtd lint`，不会关闭 linter/formatter。9 个 formatter 候选未处理任何 warning/info。
- Legacy Change Safety Review：characterized / normal，旧真实 lint red 保留，现有测试与方法正反自测构成安全网。Refactoring Review：proceed / normal，仅批准的格式/安全排序，无额外重构。现在才应用十文件候选，随后运行 lint attempt 2；完整 typecheck/包测试仍按后续门禁执行，不把静态等价证明当作全部测试通过。

## Lint attempt 2 与独立提交准备（2026-11-18T17:45:37+08:00）

- 已通过受控补丁应用十文件候选，逐文件 bytes/SHA 绑定与已证明候选一致；完整 `pnpm --filter @kunolu/dsh-sbtd lint` attempt 2 exit 0：19 文件，0 errors，原有 4 warnings/1 info 保留，`No fixes applied`。旧 attempt 1 的失败不覆盖、不追认通过。
- 新方法正反自测、实际十文件结构/绑定/模块顺序、落盘绑定与 lint attempt 2 均已有 raw JSON 与同 stem 中文报告。它们不替代后续 typecheck/full/pack/三宿主 CI；本轮未声称这些后续门禁通过。
- 提交前安全检查仅批准的十个 src 文件与本 task；版本、依赖/锁、手册、工作流及原 11 个业务文件尚未改变。现在只作独立 lint 修复提交（含本 task 真实过程记录），不 push，随后进入已批准 rc.3 准备。

## 17:15 扩围裁决与恢复（记录于 2026-11-18T17:17:22+08:00）

- 用户当前明确指令确认：已核实 17:06“全自动”原话，17:15 本轮范围裁决获 Reviewy/Researchy 多数同意并由 Lord 指派继续。本会话据当前明确指令执行，不冒称独立读取了群消息；workflow_mode 仍为 strict。“全自动”不覆盖本轮明确禁止合入/发布的边界。
- branch/HEAD/远端 main 仍为既定分支与 `9b2610265d0f205bf8ed7dfa5167d664f0312bcd`；预期仅本 task 未跟踪，无新增 writer 信号。原始 17:09:41 lint attempt 1 的 JSON 与中文报告原样保留，不覆盖、不改为通过。
- 本轮新增授权仅 `packages/dsh-sbtd/src/` 下：`backends/graft.ts`、`backends/maestro.ts`、`backends/sbtd-task.ts`、`hooks.ts`、`tools/e2e.ts`、`tools/lessons.ts`、`tools/spec.ts`、`tools/tickets.ts`、`tools/validate.ts`、`index.ts`。只修原报告的 9 个 format 与 2 个 organizeImports error，不处理 4 warnings/1 info，不改规则或逻辑。
- 先预览导入排序并证明运行时模块求值顺序不变；若影响副作用执行顺序，暂停该变更并报告。格式候选只在内存/ignored 证据中生成，正式文件通过受控补丁修改；不运行宽范围 --fix。
- 以上 lint 修复使用独立提交，与后续原 11 文件 rc.3 准备分开；新 lint attempt 如实编号，旧失败保留。任何新门禁失败立即停报，不自行扩围或豁免。
- 解除已知 in-progress 前态的范围阻塞，恢复未完成队列。宿主 pin/peer/engines/lock、manuals 的 19 文件/12 技能及 v2.1.0 SHA、其他依赖/实现/workflow、OMP 与 PR1 task 都不变。保持当前原会话 GPT-6 Astra/high，不更新工具或新建会话。
- 本轮仅获准本地验证、普通 commit/push、当前 PR 与准确 HEAD CI；外部 strict 审查仍由用户协调。不得 amend/rebase/force/reset/clean/stash/删除、merge/tag/release/npm/latest/next、PR1 收尾或 PR3/4；不发送群/评论/评审请求。

## 等价性预检失败与再次停止（2026-11-18T17:25:45+08:00）

- 两次只读 LSP organize code-action 请求均返回 `No language server found for this action`；未安装/重接工具，转为已读取源码和 TypeScript AST 的证据路径。
- 仅在 ignored `reports/lint-format-candidates-20261118.json` 生成 10 文件候选。9 个文件由现有 Biome 的 stdin formatter 产生文本，index/lessons 的排序候选只涉及命名/type 项；没有对实际 src 执行 formatter --write 或应用补丁。
- 随后的临时 Node 等价性预检退出 **1**，在首个 `src/backends/graft.ts` 候选处报告 `Unproven behavior or side-effect order`。原始工具结果记录时间 `2026-11-18T17:21:57.230+08:00`；不是 lint attempt 2，也不是产品测试失败。
- 校验器自身的 `canonical()` 将所有字符串 `node.text` 纳入摘要，包含 SourceFile 全文；格式文本变化因此可能造成摘要差异。这份证明不可靠，不能据此认定产品逻辑或导入副作用顺序已改变，也不能据此判定安全。未修正并重跑校验器、未应用候选。
- 已按“失败立即停报”停止后续实施。原始 checker 命令和 tool result 从本 session 只读匹配保存为 `reports/lint-equivalence-preview-error-20261118.json`。第一次证据提取命中自身正在运行的命令，产生 `Original checker result not recorded`；仅纠正取证选择器后取得原始结果，该取证错误也保留在报告中，未重新执行 checker 或 lint。
- 17:09:41 原始 lint JSON SHA256 为 `85e75f5e9234d93d488747e2b4649052913679d8f7f21536ee2abd3c835fbb2f`，中文报告 SHA256 为 `ab5e531cb59ac53b0b31d778220f2ed4160d701a3e633dc596c7321d578bb82b`；原失败不覆盖、不改写。
- 当前仍未修改任何 src 或原 11 个业务文件，版本仍为 0.2.0-rc.2；没有新的 lint attempt、独立 lint 修复 SHA、PR2 URL 或 CI run。后续定点/build/typecheck/full/pack/三宿主均未运行；没有 commit/push/合入/发布。
- 恢复需要先修正校验方法并重新取得可信的格式/安全排序证明；本轮不自动继续，不把内部校验错误包装成产品回归或验证成功。保留批准范围与未完成队列，task blocked/completed_at=null，等待后续指令。

## 当前实施授权与开始记录（2026-11-18T17:08:42+08:00）

- 用户本轮明确确认：SBTD 群 17:05 本人直接批准，已核对群原消息，不是仅用 Lord 转述；批准包括 Reviewy 17:01 收窄后的 T0/feature 方案。此处记录用户提供的授权来源，不冒充本会话读取过群聊。
- 原计划已逐字保存为 `reports/approved-plan-20261118-1705.md`；原件与快照 SHA256 均为 `6b4cb82c2689a25bfef2d0a7c2fe0d2cde8305e3ac487a07ad46f32886ccdcfa`。下文原“待批准/仅计划”的措辞保留为计划历史，当前权限以本节为准；旧状态事件不改写。
- 当前分支 `docs/dsh-sbtd-0.2.0-rc.3-pr2-plan`、HEAD/远端 main 均为 `9b2610265d0f205bf8ed7dfa5167d664f0312bcd`；预期仅本 task 未跟踪，未发现其他 dirty 或新增 writer 信号。原 OMP 会话和既有 broker 子进程保持，不清理用户内容。
- 保持 GPT-6 Astra/high，不更新工具/模型、不开新会话、不动全局配置。只允许获批 11 文件、本 task 与 ignored reports；不改 PR1 task、OMP、宿主依赖/锁文件/peer/engines、手册字节与 pin，不生成 SBOM。
- T0 保留当前版本状态保护：rc.3 误称已发布应被拒绝，正确准备态应通过，rc.2 历史不误伤；安装、版本、链接、包内容和宿主契约原有断言保留。不得通过删断言、改 workflow、忽略失败或扩大修改绕门禁。
- 为及早发现计划已列明的既有 lint 风险，先前置运行现有 `pnpm --filter @kunolu/dsh-sbtd lint`，不带修复选项；这是同一必需门禁，不替代后续 build/定点/typecheck/full/pack/三版本验证。任何失败按用户要求立即停止，保留证据并报告，不继续实现或提交 PR。
- 本地门禁全部成功后，本次直接批准允许普通 commit/push、创建当前 PR、必要正文更新及既有三版本/manuals/自动 Host Event CI；所有结果须精确绑定实际 HEAD/attempt。禁止强推、删除、reset/stash/clean/rebase，不合入/tag/release/npm/PR3/4，不发群/评论或请求他人。
- 按会话记录还原的 PR2 已结束轮次：计划轮 `16:42:55.466 → 16:58:05.747`，主模型 assistant 11、顶层 toolCall 40；修订轮 `17:02:30.993 → 17:05:11.607`，assistant 5、顶层 toolCall 8（均为 2026-11-18 +08:00，模型 openai-codex/gpt-6-astra）。辅助 model_usage 单列于原始脱敏报告，不混算为主模型调用。
- 当前实施轮于 `2026-11-18T17:06:49.852+08:00` 开始；最终主/辅助数、结束时间及会话最终结束均为“无法核对：进行中”。原始 session 只读，未输出凭据/provider payload；脱敏证据为 `reports/execution-entry-session-20261118-1707.json`，不记录假最终数。

## 门禁失败与停止记录（2026-11-18T17:10:49+08:00）

- 实际命令：`pnpm --filter @kunolu/dsh-sbtd lint`，调用现有 `biome check src`；attempt=1，开始 `17:09:41.233821+08:00`，结束 `17:09:41.657443+08:00`，退出码 **1**。原生输出：`Checked 19 files in 38ms. No fixes applied.`、`Found 11 errors.`、`Found 4 warnings.`、`Found 1 info.`。
- 11 errors 为 9 个 format 诊断与 2 个 organizeImports 诊断；错误涉及 `src/backends/graft.ts`、`src/backends/maestro.ts`、`src/backends/sbtd-task.ts`、`src/hooks.ts`、`src/index.ts`、`src/tools/e2e.ts`、`src/tools/lessons.ts`、`src/tools/spec.ts`、`src/tools/tickets.ts`、`src/tools/validate.ts`。另有 maestro/e2e 的 noPrototypeBuiltins、bdd 的未用函数 warning，以及 maestro 的 useTemplate info。
- 这是本轮修改任何获批业务文件之前发生的现有源码门禁失败，不是 rc.3 改动引入。没有运行 --write/--fix、没有自动修复、没有重跑确认，也没有忽略诊断或降低门槛。失败后只整理已产生的证据并记录 blocked。
- **尚未实施**：11 个获批业务文件全部未改；插件仍为 `0.2.0-rc.2`。T0 正反状态校验、feature、双语准备说明和版本 bump 都未实施，既有断言没有删改；PR1、OMP、依赖/锁文件/peer/engines、手册字节/pin 均未改。
- **未执行验证**：build、定点测试、typecheck、full package、dry-run/真实 pack、tarball/schema/MANIFEST 字节检查、三个宿主 CI、manuals CI、自动 Host Event probe。本轮没有这些验证的通过数量、run 或 job 结论，不复用 PR1 统计填补。
- 原始 stdout/stderr/命令/真实时间/退出码保留于 `reports/lint-preflight-20261118-170941.json`，中文同 stem 摘要另存。原计划快照与 session 脱敏统计保留，不删除失败记录。
- **提交/PR状态**：HEAD 仍为 `9b2610265d0f205bf8ed7dfa5167d664f0312bcd`；没有 commit/push、没有 PR2 URL、没有 CI run。未向群、评论或任何 reviewer 发送消息，未合入或发布。
- 需要用户另行裁决如何处理当前白名单外的既有 lint 问题；本轮不扩大到 src 修复，不提议绕过门禁。恢复前必须有明确权限和真实验证；当前保持 blocked/completed_at=null，不是 checking、CLEAN 或 done。

## 1. 当前授权、基线与顺序

- 作者：当前原始 Mac Orca OMP 会话；主模型 `openai-codex/gpt-6-astra`，thinking `high`，由本会话原始记录只读核对。未切模型、未新建 OMP、未更新工具或全局配置。
- 当前只允许写本 task.md 与本任务 ignored `reports/`；状态 `planned` 表示计划待审，不代表 PR2 实施已获批准。没有运行安装、同步、构建、测试、pack 或 CI；没有 commit/push/开 PR/合入/tag/release/npm 操作。
- 已核实基线：`9b2610265d0f205bf8ed7dfa5167d664f0312bcd`。普通 `git fetch --no-tags` 后 `origin/main` 与该 SHA 一致；提交标题为 `docs(dsh): sync manuals to 640-skills v2.1.0 (PR1) (#127)`，父提交 `0d9331bd7d64c28dea368fd4385fd009809d58da`。
- PR127 合入来源：用户明确说明 16:26 批准、Lord 已 squash 合入；Git main/提交标题/SHA 相符。Git committer time 为 `2026-11-18T16:26:27+08:00`，不冒充另行查询的 GitHub mergedAt。该树与 PR1 最终 HEAD `a435a9601a95da335d8c93722ea3d2738fdacb5d` 无文件差异；这不等于本轮在合并 SHA 运行过测试。
- 入口工作树干净；原 PR1 本地分支仍指向 `a435a9601a95da335d8c93722ea3d2738fdacb5d`。新分支由已核实 `origin/main` 用 `git switch --no-track -c` 建立；没有改写旧分支或本地 main，没有 reset/stash/clean/rebase/删分支。
- 原四 PR 路线保持串行：PR1 dsh 手册同步（已合入）→ PR2 dsh 发版准备（本计划）→ PR3 omp 同步 → PR4 omp 发版准备。每 PR 先审 strict task，实施后独立 Reviewy strict CLEAN + 同 HEAD CI 全绿，再等用户合入决定；不能自动推进下一 PR。
- **PR1 收尾仅拟议**：已合入的 `ai/tasks/dsh-sbtd-0-2-0-rc-3-pr1-manuals/task.md` 仍为 `checking`、`completed_at: null`。本轮不改它、不重绑定它的分支、不从“已合入”伪造 CLEAN/done。推荐另行授权补齐真实审查/CI/完成证据；不纳入本 PR2 默认白名单，也不阻断本计划草案。
- 已加载项目/全局 AGENTS、sbtd-task strict/state 与既有 dsh release task 格式。未完整调用 grill-with-docs：本轮是清楚的计划请求；实质分歧列在第 8 节，先读事实，不重复访谈。
- 本次计划修订依据用户转述的 Reviewy 17:01 建议：T0 改为面向当前插件版本的正反发布状态校验，而非直接删除准备状态检查。仅修订本计划及本地摘要，版本目标、11 文件名单与其余边界不变，仍待用户批准实施。

## 2. 版本事实与不应误改的身份

| 对象 | 实际当前值 | 拟议 PR2 结果 |
|---|---|---|
| `@kunolu/dsh-sbtd` 自身版本 | `packages/dsh-sbtd/package.json`：`0.2.0-rc.2` | `0.2.0-rc.3`；来自原用户四 PR 路线的 `dsh-sbtd-v0.2.0-rc.3` 目标，仍待本计划批准 |
| 插件注册身份 | `cordis.patch.yml`：id=`sbtd`、name=`@kunolu/dsh-sbtd`；package 的 dsh.bundle.patch 指向该文件 | 不变；该 patch 没有版本字段，不能机械 bump |
| 宿主开发 pin | `@deepseek-ai/dsh@0.2.0-rc.2` | 不变；不是插件版本，不能批量替换为 rc.3 |
| peer / engines.dsh | 均为 `>=0.2.0-rc.2 <0.3.0-0` | 不变，不提升宿主支持门槛 |
| 手册 / MANIFEST | `640-skills 2.1.0` / `3c835303c23d59d3157ca84121a92f1bd87d4997`，19 文件 / 12 技能 | 全部字节与 pin 保持；仅修正 README 中仍写 2.0.2 的描述 |
| 锁文件 | `pnpm-lock.yaml` 的 dsh importer 只记录宿主依赖，没有插件自身发布版本字段 | 不变，不升级依赖或重解锁文件 |
| 独立 plugin.json / SBOM | dsh 已跟踪 79 文件中不存在；build 仅 `tsc -p tsconfig.json`，无 SBOM 生成步骤 | 不新造文件或生成器；标 not-applicable，不借用/改动 omp 的 manifest 或 SBOM |

仓库和文档的当前版本事实已读；本轮未查询 npm 当前 dist-tag，不把旧 README 的“已发布 rc.2”记录当作当前 registry 重新核验。rc.2 有日期的发布事实保留；rc.3 只能写准备态，不能声明 tag、release、npm 或安装认证已完成。

## 3. 文件清单：当前允许与拟议实施名单分开

**本轮最终允许清单只有：**

1. `ai/tasks/dsh-sbtd-0-2-0-rc-3-pr2-release-prep/task.md`
2. 同目录 `reports/**` 的计划证据；受现有 `/ai/tasks/**/reports` 保护，不强制入库。

**拟请用户批准的实施白名单：以下 11 个现有文件，加本 task 的过程记录。尚未获准实施。**

| 文件 | 必要修改与保留边界 |
|---|---|
| `packages/dsh-sbtd/package.json` | 只改自身 version 为 0.2.0-rc.3；name/files/peer/engines/devDependencies/scripts 不变 |
| `packages/dsh-sbtd/README.md` | 更新 rc.3 准备说明、未来自身 tag 的语言链接、已合入 manuals 2.1.0 pin 与兼容证据边界；保留 rc.2 有日期发布历史及既有安装方式 |
| `packages/dsh-sbtd/README.zh.md` | 与英文语义、命令、版本和准备/发布状态一致；不冒称新 tag 链接已可访问 |
| `packages/dsh-sbtd/CHANGELOG.md` | 在旧记录之上准备 rc.3 双语对应条目，覆盖 PR127 手册与兼容 smoke 修复；显式未发布，旧 Released 记录不改 |
| `packages/dsh-sbtd/CHANGELOG.zh.md` | 中文对照同一范围；实施时使用真实准备日期，不提前写发布时间 |
| `README.md` | 只改 DSH 包行/DSH 安装或路线图的 rc.3 准备状态；保留已发布 rc.2 历史，所有 OMP 段落不动 |
| `README_zh.md` | 仅同步 DSH 中文段落；不全局替换共享的 0.2.0-rc.2 字符串 |
| `docs/assets/dsh/README.md` | 当前索引仍写 manuals 2.0.2，须对齐已合入 2.1.0；区分 rc.3 准备与 rc.2 历史，链接本任务，旧 0–G PRD 仍作为历史 |
| `packages/dsh-sbtd/test/t0-stub.test.mjs` | 更新插件 version/自身 release-tag 链接契约；将整份 README 的全局禁词约束改为仅面向当前插件版本的正反状态校验，不直接删除准备状态检查。拟验证当前 rc.3 正确准备态通过、误写已发布应失败、rc.2 已发布历史不误伤；安装、版本、链接、包内容与宿主契约的原有断言保留 |
| `packages/dsh-sbtd/test/fu4-host-schema.test.mjs` | 只更新 `pluginPkg.version` 预期；宿主版本、peer、engines、tools 版本和真实 Host Event 断言保持 |
| `packages/dsh-sbtd/features/t0-installable-stub.feature` | 对齐插件自身 rc.3 与 tag 链接；中文场景 + 英文关键词保持；描述当前版本准备态、当前版本误报已发布、旧版发布历史三类验收预期。宿主 rc.2、安装路径和不写用户磁盘契约不变；不把历史发布声明当作当前版本状态 |

**检查过但不进入默认修改名单：**

- `packages/dsh-sbtd/cordis.patch.yml`、`pnpm-lock.yaml`：身份/依赖未变，没有应 bump 的插件版本字段；意外变动即停，不“顺手”更新。
- `packages/dsh-sbtd/manuals/**`、`scripts/sync-manuals.sh`、两个 T4 测试及 T4 feature：PR1 已对齐，PR2 只验证、不重同步或迁 pin。
- `.github/workflows/dsh-host-compat.yml`、`.github/workflows/dsh-manuals-pin.yml`、`.github/workflows/scripts/dsh-host-register-smoke.mjs`：沿用已合入版本，不继续扩展实现或改变断言。
- `docs/assets/dsh/ci-dsh-host-compat.md`、`docs/assets/dsh/ci-640-skills-adapt.md`：现有索引明确其保留历史背景，推荐保持；若用户要求改成当前运行手册，须另行确认这两个确切文件，不夹带重写。
- `docs/prd/dsh-sbtd-0.2.0-rc.1.md` 与 PR1 task：历史/收尾候选，不属于 PR2 默认改动。旧任务收尾另批。
- `packages/dsh-sbtd/src/**`、其他 feature/test、全部 omp/kit 文件、根 package/config/AGENTS：不变；发现需改产品代码或增加 SBOM 时立即停报。

## 4. 未来验证矩阵与命令（本轮全部未运行）

### 当前插件版本发布状态（拟议验收，尚未执行）

校验对象是实施后当前插件自身版本 `0.2.0-rc.3` 的状态，不是全文中任意版本的发布措辞，也不是 DSH 宿主版本。英文与中文说明均须符合下列预期；不预先指定解析方式、正则、测试组织或新增抽象。

| 拟验证内容 | 预期判定 | 保留边界 |
|---|---|---|
| 尚未发布的当前 rc.3 被写成“已发布” | 状态校验应失败 | 防止准备版本冒充发布事实；不能只允许准备词而漏掉相反错误 |
| 当前 rc.3 准确写为“准备中/未发布” | 状态校验应通过 | 允许真实准备说明，不以全局禁词拒绝 |
| 当前 rc.3 为正确准备态，同时保留 rc.2 已发布历史 | 状态校验应通过，不误伤旧版历史 | 不把 rc.2 历史当作 rc.3 已发布，也不删除历史证据 |

上述为未来实施的正反验收要求，不是已运行结果。安装、版本、语言链接、包内容及宿主契约的现有断言保留；不得用直接删除检查或同义词绕过替代当前版本状态校验。

### 三个精确宿主

| 宿主 | 来源与角色 | 验收门槛 |
|---|---|---|
| `0.2.0-rc.2` | package dev pin；`dsh-host-compat.yml:109` REQUIRED；`DSH_PIN_SMOKE=1` | 同一 rc.3 tarball，job 自身 success |
| `0.2.1-rc.2` | 同一 workflow REQUIRED；`DSH_PIN_SMOKE=1` | 独立 cell/job 证据，不由另一行代替 |
| `0.2.2-rc.3` | 原 PR1 用户目标及已合入 smoke 修复；`candidateDshVersions` 输入；`DSH_PIN_SMOKE=0` | 虽配置为 advisory，PR2 验收仍要求其 job 自身 success；顶层 continue-on-error 的 success 不够 |

不提升候选为 workflow REQUIRED，不改变版本范围。沿用现有工具；本会话已观察本地 Node 24.15.0，候选包声明 Node >=24.9.0；既有 CI Node 22 的成功只证明具体 smoke，不扩称官方完整支持，不在 PR2 升级 workflow/runtime。实施前只读重核环境，缺条件即报告，不全局安装或同步配置。

### 项目原生命令

以下仅在本计划及相应实施权限获批后执行；依赖安装采用现有 CI 的 `pnpm install --frozen-lockfile`，不改 lockfile。报告命令使用 native，保留失败轮、stdout/stderr/退出码、同 stem 中文摘要、真实 SHA/worktree/环境。

```bash
pnpm --filter @kunolu/dsh-sbtd build
(cd packages/dsh-sbtd && node --test test/t0-stub.test.mjs test/fu4-host-schema.test.mjs test/t4-manuals.test.mjs test/t4-sync-exit.test.mjs)
pnpm --filter @kunolu/dsh-sbtd typecheck
pnpm --filter @kunolu/dsh-sbtd lint
pnpm --filter @kunolu/dsh-sbtd test
(cd packages/dsh-sbtd && npm pack --dry-run --json)
pack_dir="$(mktemp -d)"
pnpm --filter @kunolu/dsh-sbtd pack --pack-destination "$pack_dir"
tgz="$pack_dir/kunolu-dsh-sbtd-0.2.0-rc.3.tgz"
tar -tzf "$tgz"
tar -xOf "$tgz" package/package.json
```

- 定点 unit 与 full package 分开记；full test 自带 tsc。旧 PR1 的 342/0/0、T4 6/0/0 仅历史，不预填 PR2 用例数；改测试后以实际输出为准。lint 若暴露既有 src 问题，保留证据并停报，不借 PR2 无关修复或豁免门禁。
- tarball 必须唯一且自身 version/name 正确，包含 `package/dist/index.js`、`package/cordis.patch.yml`、两份 README、两份 CHANGELOG、manuals/MANIFEST 与实际 19 文件；核验文件集合/逐文件 checksum 和 JSON schema 字节，不把安装成功当打包正确。
- MANIFEST 保持 `2.1.0 / 3c835303c23d59d3157ca84121a92f1bd87d4997`，同步脚本和 T4 pin 不改。T4 覆盖缺源/SHA mismatch/copy/checksum 失败等原有契约。
- 只有获得后续 push/PR/远端 CI 权限才调度：

```bash
gh workflow run dsh-host-compat.yml --repo KunoLu/sbtd-plugins --ref docs/dsh-sbtd-0.2.0-rc.3-pr2-plan -f candidateDshVersions=0.2.2-rc.3
gh workflow run dsh-manuals-pin.yml --repo KunoLu/sbtd-plugins --ref docs/dsh-sbtd-0.2.0-rc.3-pr2-plan
```

- `dsh-host-compat` 现有流程：unit+pack 后将同一 tarball 分别装入三个隔离 cell，复制共享 `dsh-host-register-smoke.mjs`，执行 `DSH_VERSION=<该行版本> DSH_PIN_SMOKE=<原角色> node smoke.mjs`。required cell 设置真实 `GITHUB_WORKSPACE`；使用现有 `pnpm add --config.dangerouslyAllowAllBuilds=true`，仅隔离环境执行依赖构建，不动用户全局宿主。
- DSH Host Event 证据来自共享 smoke 的真实 Cordis `agent/pre-step` notice/startsRequestSeries 与 `tools/pre-execute` ask，连同注册/schema 断言全部保持；不是完整模型 E2E，也不把包 test 当三版本矩阵。
- “无手册重同步”指不在 PR2 开发树改 pin/重生成镜像。`dsh-manuals-pin` 现有 CI 在隔离 runner 按固定已合入 pin 克隆并重建，是无 diff 的再现检查（会联网），不是引入新上游内容；不修改该 gate。若用户连此隔离再现也禁止，须明确裁决，不能静默跳过。
- 仓库自动 `omp-runtime-linux-probe` 仍是 PR 必跑的既有 CI，不是 PR3。其现行命令为 `pnpm --filter @kunolu/omp-sbtd exec tsx scripts/p0/host-event/run-live-cell.ts`，使用 workflow 当轮构建的 tarball、`SPIKE_OMP_BIN`、`HOST_EVENT_RUNS_ROOT`、`HOST_EVENT_TARGET_VERSION=18.11.1`；不手工伪造输入，不改 omp 或该 workflow。
- 本机 OMP 18.20.3、原 omp 验收基线 18.19.0、自动 probe 的 18.11.1 是三个不同来源，不相互冒充。本轮仅计划，不运行任何 probe。

## 5. 双语准备内容与发布边界

将来在既有中英文 CHANGELOG/README 准备 rc.3 内容，不新建 GitHub Release 或 tag。建议内容：PR127 的 640-skills v2.1.0 四技能手册更新；共享兼容 smoke 的官方 native executor 初始化；宿主范围/开发 pin/运行时 API 不变；具体新版本验证结果由实施后的真实 run 填入。

- 中文状态语义：`0.2.0-rc.3 发版准备；尚未发布。保留 rc.2 的有日期发布历史，不宣称当前 registry 已指向 rc.3。`
- English meaning: `0.2.0-rc.3 release preparation; not yet published. Preserve dated rc.2 release history; do not claim registry tags already point to rc.3.`

语言链接可准备为未来 `dsh-sbtd-v0.2.0-rc.3` 的同版本链接，但明确 tag 尚未创建；本轮不能给出 HTTP 已通过或 tag 已存在的结论。安装示例仍沿用现有宿主/`@next` 方式；`@next` 安装结果不能代替当轮 rc.3 tarball 验证。

准备日期使用未来实施时真实 Asia/Shanghai 时间，不伪造发布时间。合入、tag/release/npm 发布、dist-tag latest/next 决策分别需要用户明确授权；PR2 计划或实现批准不授予发布权限。PR1/历史 README 的旧发布命令不是本轮可执行指令。

## 6. 串行执行与 strict 闭环

1. 用户先确认目标版本、11 文件白名单及第 8 节分歧；未批前保持 planned，只允许计划文档修订。
2. 获批实施后重新核对 branch/main/dirty/并发与实际文件；有额外用户改动、基线冲突或超范围需求即停报，不自动 rebase/reset/stash/clean。追加带作者与真实时间的开始事件，转 in-progress。
3. 先对齐既有 feature 中“当前插件版本”的状态语义，拟具备当前 rc.3 误报已发布的负例、正确准备态的正例及 rc.2 历史不误伤的验证，再按获批范围调整 package、双语文档和必要测试。保留安装、版本、链接、包内容与宿主契约原有断言；具体实现形式在实施时选择，不在计划阶段预设解析器或框架。
4. 实施后核验上述三类状态预期，再跑定点、全包、静态检查、真实 pack 与三版本 Host Event smoke；保存真实原始/中文结果与失败，不在本计划填入通过数字，不以旧 SHA 或顶层 success 补齐证据。仍不扩实现、不新建 SBOM、不迁上游 pin。
5. 转 checking，完成 project-validation、可读性/精简复核及适用 Book gates。需要 commit/push/PR 时先取得对应明确授权；按实际最终 HEAD 获取 CI 与独立 Reviewy strict CLEAN，主会话自审不能代替。
6. Reviewy 退回则回 in-progress 修本 PR 范围并复验；真正 CLEAN 前不 done。按现有 B 方案作仅改 task 的限定 done 收尾（status/completed_at/updated_at、一条 done 事件和 CLEAN SHA/CI run），独立复核限定 diff，最终 HEAD 的适用 CI 仍须全绿。真实 completed_at，不回填成未经核验的合入时间。
7. 闭环记录提交改变 HEAD 后重新绑定真实验证；最终证据可写 ignored reports/获准 PR 正文，避免无限追加记录提交。用户决定是否合入；发布另批；不自动进入 omp PR3/4。

### Book Gate Plan（计划状态，不是通过结果）

| Gate | 事实与阶段 | 状态 |
|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；无新领域模型或术语歧义 | not-required；若后续完整 grill 则按共同规则先做独立 DDD |
| book-ddia-data-design | 不变 schema、数据所有权、持久存储或迁移 | not-required |
| book-legacy-change-safety | 将全局禁词约束改为当前插件版本正反状态校验；实施前锁定历史不误伤与原有安装/版本等契约 | planned；不删除准备状态检查，不借机修改产品行为 |
| book-refactoring-pass | 推荐范围无既有生产实现编辑，仅元数据/文档/契约测试 | not-required；若需改 src/同步算法即超范围停报 |
| book-release-readiness | 包版本/文档/真实 tarball 一致性；适用测试后、准备交付前 | planned；结论最多覆盖准备范围，不是发布授权 |

## 7. 模型、会话与证据口径

同一原始会话 header 起始 `2026-11-16T18:06:56.701+08:00`；本轮 PR2 请求时间 `2026-11-18T16:42:55.466+08:00`。当前 latest model_change=`openai-codex/gpt-6-astra`、thinking-level=`high` 已只读核对；不读取或公开凭据/provider payload。

按“已结束 user-message 工作轮次”统计主 assistant 记录、其顶层 toolCall 块；辅助 `model_usage` 按 purpose/provider/model 单列并保留 aborted，model_change 不算执行次数。开始/结束时间分别取原始用户时间与该轮最终 assistant.completedAt；明确“按会话记录还原”，不把选择记录当调用、不算节省率/账单。

本轮仍在进行，最终主/辅助次数、工具数、会话最终结束时间及未落盘请求/重试、服务端实际 effort 均写 **无法核对**。阶段快照注明截止；不记录假最终数，不为滚动统计重写已验提交。计划证据见 `reports/baseline.json` 与同 stem 中文摘要；不创建 active/index/handoff/developer，不宣称 TaskStore 全库恢复或任何测试 gate 已通过。

## 8. 待用户决定（推荐与依据）

1. **版本和实施清单**：推荐确认 `0.2.0-rc.2 → 0.2.0-rc.3` 及第 3 节 11 文件名单；plugin patch/锁文件/SBOM 不改。依据：实际 package、完整 dsh tracked inventory、锁 importer、仅 tsc 的 build 与既有 release task 先例。
2. **当前插件版本发布状态契约**：推荐采用用户转述的 Reviewy 17:01 建议，将 T0 全局禁词约束调整为面向当前插件版本的正反状态校验，替换原“直接移除禁词断言”的拟议方案。待用户批准的验收预期为：尚未发布的当前 rc.3 误写已发布应失败；准确准备中/未发布应通过；rc.2 已发布历史与 rc.3 准备态并存时不误伤。对应 feature 对齐该语义，安装、版本、链接、包内容与宿主契约原有断言保留；不在计划阶段规定具体实现或编造结果。
3. **PR1 收尾**：推荐独立授权处理，而非夹带 PR2。现记录 checking/null 是已查事实；合并不等于 task 已完成。没有对应审查证据时明确缺口，不假造 CLEAN/done。
4. **候选事项不默认扩围**：旧 CI 笔记改写、新 SBOM、CI Node 24 迁移、提升候选为 REQUIRED、真实用户 profile/UI 安装或发布动作，均不在推荐白名单；如要纳入须先修改计划并另行批准。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-11-18T16:52:23.411687+08:00 | planned | planned | OMP 当前会话：开始落盘用户要求的 PR2 strict 计划草案 | 用户仅授权计划；main=9b2610265d0f205bf8ed7dfa5167d664f0312bcd；同一会话/模型；新计划分支，旧 PR1 分支保留 |
| 2026-11-18T16:52:23.411687+08:00 | planned | planned | OMP 当前会话：完成只读事实整理，计划待用户审核，不进入实施 | package 0.2.0-rc.2；无独立 dsh SBOM/plugin.json；11 文件拟议白名单、三宿主与真实工作流命令已列；本轮未构建/测试/提交/发布 |
| 2026-11-18T17:02:39+08:00 | planned | planned | OMP 当前会话：按用户转述的 Reviewy 17:01 建议修订 T0 计划，完成白名单说明、验收矩阵、串行步骤与待批准事项同步 | 改为当前插件版本正反状态校验；拟验证 rc.3 误报已发布失败、正确准备态通过、rc.2 历史不误伤；版本及 11 文件名单不变；仅计划/摘要，未实施或运行测试，继续待用户批准 |
| 2026-11-18T17:08:42+08:00 | planned | in-progress | OMP 当前会话：记录用户 17:05 直接批准，保存原计划并开始获批 PR2 执行 | 用户确认群原消息已核实；branch/base/dirty 符合预期；原计划 SHA256 6b4cb82c2689a25bfef2d0a7c2fe0d2cde8305e3ac487a07ad46f32886ccdcfa；先前置现有 lint 门禁，失败即停 |
| 2026-11-18T17:10:49+08:00 | in-progress | blocked | OMP 当前会话：首个 lint 门禁失败，按用户要求立即停止实施与后续验证，保存失败并报告 | pnpm --filter @kunolu/dsh-sbtd lint，attempt 1，exit 1；19 文件，11 errors/4 warnings/1 info，No fixes applied；reports/lint-preflight-20261118-170941.json；未改业务文件、未提交或开 PR |
| 2026-11-18T17:17:22+08:00 | blocked | in-progress | OMP 当前会话：记录当前用户明确提供的17:15扩围裁决，恢复原实施阶段及未完成队列 | 仅新增10个src文件既有9格式/2安全排序；保留17:09:41失败；先核对模块副作用顺序、修复lint并独立提交，再继续原PR2；本次仍不合入或发布 |
| 2026-11-18T17:25:45+08:00 | in-progress | blocked | OMP 当前会话：临时等价性预检失败，按失败即停要求暂停，未应用任何源码候选 | checker exit 1，SourceFile.text 进入摘要导致证明不可靠；原命令/结果及一次取证选择器错误已保存；没有 lint attempt 2、提交或 PR；reports/lint-equivalence-preview-error-20261118.json |
| 2026-11-18T17:31:25+08:00 | blocked | in-progress | OMP 当前会话：记录本次明确 checker 纠正授权，恢复既有范围 | 保留原失败/取证时间；先独立正反样例与十文件模块/type-only证明，再允许源码补丁和lint attempt2；不扩产品范围、不合入发布 |
| 2026-11-18T17:39:01+08:00 | in-progress | in-progress | OMP 当前会话：完成 checker v2 独立自测与十文件证明，开始应用限定格式/排序补丁 | self-test 10/10（预期阴性7项正确拒绝）；十文件4项结构/模块/type-only比较全同；index/lessons 人工核对安全；原失败未覆盖；随后 lint attempt2 |
| 2026-11-18T17:45:37+08:00 | in-progress | in-progress | OMP 当前会话：完成十文件格式/安全排序及lint attempt2，开始独立lint提交 | 十文件与已证明候选逐字节一致；完整 lint exit0，19文件/0errors/4warnings/1info；仅10个src+task；版本仍rc.2，后续全部门禁未冒称通过 |
