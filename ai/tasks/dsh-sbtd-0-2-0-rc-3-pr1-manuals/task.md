---
schema_version: 1
id: dsh-sbtd-0-2-0-rc-3-pr1-manuals
workflow_mode: strict
mode_source: user
mode_note: 用户要求 strict；2026-11-18 13:55 批准 PR1，14:19 本人进一步批准仅修复共享兼容 smoke 的 executor 初始化，保留全部断言并重跑三个 dsh 版本。
status: checking
branch: docs/dsh-sbtd-0.2.0-rc.3-pr1-plan
created_at: '2026-11-18T13:49:26+08:00'
updated_at: '2026-11-18T14:29:55+08:00'
completed_at: null
---

## 当前扩围授权与恢复（2026-11-18T14:20:35+08:00）

- 用户确认本人于北京时间 2026-11-18 14:19 批准：“批准PR1扩展范围：修复共享兼容测试脚本的执行器初始化，保留全部断言并重跑三个dsh版本”。该原话与来源由当前用户消息确认，关闭此前“等待 smoke 扩围裁决”项；历史失败证据完整保留。
- 本轮基线 `301325fd976c012a81138df645ed7574568e6b90`，原分支、原 PR #127；本地 HEAD 与远端本分支一致，工作树干净。远端 main 仍为 `0d9331bd7d64c28dea368fd4385fd009809d58da`，没有基线迁移。进程快照只有当前 OMP，无另一个相关 writer。
- 新增代码写入范围仅 `.github/workflows/scripts/dsh-host-register-smoke.mjs` 的 executor 初始化；保留全部现有断言和门槛，三个宿主精确版本不变。允许本 task 的状态/证据及 ignored reports 写入；不改 workflow、依赖版本、lockfile、无关产品代码或其他上游手册。
- 保持 GPT-6 Astra/high、当前 OMP 会话；不新开 OMP、不更新软件或全局配置。可以向当前 PR 提交/push 修复及必要任务记录，但不发送群消息、PR 评论、评审请求或其他对外消息；Reviewy strict 由用户协调。
- 原真实阻塞前态为 checking；本次先按原态解除阻塞，再返回 in-progress 执行获批修复。Reviewy CLEAN 尚缺并未被“恢复”冒充通过；完成修复后仍须保持 checking 等待独立审查。
- 先调查三个实际宿主的 API，不凭错误文本猜初始化方法。历史 run 44248624861 的候选失败已是复现，不为确认而重跑；修复后真实重跑 0.2.0-rc.2、0.2.1-rc.2、0.2.2-rc.3 及受影响检查。candidate job 必须自身成功。
- 最终 HEAD 必须有真实三版本 CI，不能用旧实现 SHA 或后续只改 task 的提交冒充已验。若产生闭环记录提交，须再为该最终 HEAD 运行所需 CI，并分别列出代码提交、记录提交及测试 SHA；CI 原始日志/JSON 与同 stem 中文摘要保留。
- 本节覆盖历史计划“不修改共享 smoke”的限制；其他边界不变。不得 merge、PR2、tag、release、npm 发布；发现额外 dirty、并发 writer 或仍需超范围时停止报告，不 reset/stash/clean。

## Executor API 证据与最小修复决定（2026-11-18T14:23:26+08:00）

- 已下载三个精确版本的 `@deepseek-ai/dsh-tools` 与 `@deepseek-ai/dsh-tool-executor-native@0.2.2-rc.3` 发布包，仅在临时目录读取 source/lib，逐包核对 registry sha512 integrity；没有安装这些调查包、执行包脚本、修改仓库依赖或全局配置。记录：`reports/executor-api-source-20261118-1421.json`。
- 0.2.0-rc.2 与 0.2.1-rc.2 的 ToolRuntime 构造器均为 `defaultMode = config.mode ?? "native"`，没有 `setExecutor`；0.2.2-rc.3 的 ToolsService 提供 `setExecutor`，prompt assembly 必须经 `selectExecutor`，缺少 provider 即抛出已观察错误。
- 0.2.2-rc.3 官方 native 插件 `inject=['tools']`，`apply(ctx)` 调用 `ctx.tools.setExecutor(new NativeToolExecutor(ctx))`，提供真正的 describe/execute，不是模拟 executor。该包是宿主已有 `dsh-sdk-minimal@0.2.2-rc.3` 的精确依赖；通过 dsh → sdk-minimal → native 的实际依赖归属解析，不依赖偶然 hoist 或新增依赖。
- 最小修复：挂载 ToolRuntime 后，只有宿主支持 `setExecutor` 才导入并挂载官方 native 插件；旧宿主继续其内置 native 路径。模块找不到或注册失败直接失败，不 catch、不伪造 provider、不删任何原有断言。
- Legacy Change Safety Review = characterized / normal：原 run 44248624861 是已有失败复现，三个发布包提供根因证据；原共享 smoke 即回归 seam。Refactoring Review = proceed / normal：复用 `importPinned` 与 Cordis plugin 生命周期，无重构。before-dev 结论在代码修改前输出。
- TDD 使用已有真实 red，不重跑只为确认，不新增源文本型永久测试。保留共享 smoke 全部断言，用实际三宿主 smoke 转绿；本地 Node 24 与既有 Node 22 CI 分开记录。候选包声明 Node >=24.9.0，既有 workflow Node 22 是历史配置，本轮不擅改，其结果只证明该具体 smoke 环境，不扩称完整宿主支持认证。
- DDD/DDIA 不新增触发：不改变领域模型、数据 schema 或持久状态。LSP 仅配置 biome，无需符号改名或导出 API 变更；直接核对发布源。独立 Reviewy 继续由用户协调。

## 修复后本地三版本结果与提交准备（2026-11-18T14:26:41+08:00）

- `node --check .github/workflows/scripts/dsh-host-register-smoke.mjs` exit 0；`pnpm --filter @kunolu/dsh-sbtd pack --pack-destination <本轮隔离目录>` exit 0，未改版本。三 cell 使用同一 tarball，SHA256 `20acf48bfbc5a45bdb871c911be97ed4c8551d6889efa7a2f762692754313737`。
- 本地 Node v24.15.0 / pnpm 11.17.0，依次执行候选 0.2.2-rc.3 与 REQUIRED 0.2.0-rc.2、0.2.1-rc.2。三次精确宿主隔离安装均 exit 0，三次完整共享 smoke 均 exit 0，原文分别 `register smoke ok <宿主版本> 0.2.0-rc.2`；候选没有跳过后续断言。
- REQUIRED 两版使用 `DSH_PIN_SMOKE=1` 与真实 `GITHUB_WORKSPACE`；候选使用原 workflow 的 `DSH_PIN_SMOKE=0`。没有改变任何原断言、pin gate 或 continue-on-error 配置。原失败日志保留；本轮没有失败、命令重试或隐藏 skip。
- 语法、pack、三 install、三 smoke 各有独立 raw JSON 与同 stem 中文摘要：`reports/executor-*-20261118-1424.*`。API 调查另有配对报告。当前为 developer-local / dirty / local-only；不代替将要提交的真实 CI。
- 提交前安全检查仅两个预期修改文件：共享 smoke 与本 task；无额外用户 dirty、依赖/lockfile/workflow/产品代码变更。Code Readability / ponytail-review：五行局部初始化，复用现有 helper，无 fallback/no-op、无新增抽象，不需要重构；这不是独立 Reviewy。
- 开始提交并推送本次修复到 PR #127，只调度获准 CI，不修改 PR 描述、不发评论或审查消息。新 HEAD 须运行完整 dsh-host-compat 三版本、pin 检查与仓库自动 CI；CI 结果随后记录，保持 checking。

## 修复提交 CI 闭环与最终 HEAD 复验约定（2026-11-18T14:29:55+08:00）

- 代码修复提交 `cc9ff936017084f737cbea080bf0ddb043a50caa` 已推送原分支/PR #127；只修改共享 smoke 的五行初始化和本 task。没有修改 PR 描述、发送评论、请求评审或群消息。
- 该提交的 `dsh-host-compat` run `44251445990` 全部五个 job 分别 success；REQUIRED unit+pack 的原生计数 342 passed / 0 failed / 0 skipped，pack dist 检查成功。

| 精确宿主 | Job ID | 原始结果 |
|---|---|---|
| REQUIRED 0.2.0-rc.2 | 134623087253 | success；register smoke ok 0.2.0-rc.2 0.2.0-rc.2 |
| REQUIRED 0.2.1-rc.2 | 134623087142 | success；register smoke ok 0.2.1-rc.2 0.2.0-rc.2 |
| Candidate 0.2.2-rc.3 | 134623087117 | success；register smoke ok 0.2.2-rc.3 0.2.0-rc.2 |

- `dsh-manuals-pin` run `44251452139` success，6 passed / 0 failed / 0 skipped，真实上游重同步幂等成功；仓库自动 `omp-runtime-linux-probe` run `44251452147` success，不冒称新 OMP 版本认证。
- 三 run 的精确 headSha 均已核对为代码修复提交；`reports/executor-ci-{host,manuals,automatic-omp}-<run-id>.json/.md` 与 `-log.txt/-log.md` 保留完整原始结果、每个 job 状态及同 stem 中文汇总。旧失败 run 44248624861 未覆盖或删除。
- 本次只读源码、真实本地三 cell、真实 CI 已闭环；无失败重试，无测试删减或新增 mock。新 executor 通过宿主已有 sdk-minimal 精确依赖解析，旧宿主仍内置 native。没有升级仓库依赖、软件或全局配置。
- Release Readiness Review = blocked：修复提交技术门禁已通过；本记录提交之后仍需真实最终 HEAD CI，独立 Reviewy strict 尚待用户协调。容量/背压/服务告警/迁移不适用；原始日志可观测，未部署，无数据回滚动作。不提前声明整个 strict 生命周期完成或发布就绪。
- 接下来仅提交本 task 的闭环记录并推送；该记录提交不是 B 方案 done 收尾，保持 checking/completed_at=null。随后对记录提交后的最终 HEAD 真实重跑相同三版本 CI及适用检查，逐 job 核实 candidate，而不是复用上表旧 SHA。
- 最终复验原始结果保存为 `reports/executor-final-ci-<类别>-<run-id>*`，完整 HEAD、原生数字与交付边界另存 `reports/executor-final-delivery.json/.md` 并在会话输出。为避免报告写入再次移动已验 HEAD，最终报告仅写 ignored reports，不追加第三个记录提交；后续 Reviewy 结论到达时再按新节点追加 task。
- 原范围阻塞已由 14:19 授权解除，executor 技术失败已在代码修复提交转绿。仍不标 done、不发送外部消息、不合入/PR2/tag/发布。用户负责独立 Reviewy strict 协调。

## 当前执行授权（2026-11-18）

- 用户在本会话确认本人于北京时间 13:55 在 SBTD Plugins 群回复“批准PR1计划”；关闭计划待审项。以下原始草案保留为历史，凡“本轮仅计划／禁止提交”的措辞仅指 13:49 草案轮；当前授权以本节为准。
- 当前 OMP 会话继续作为唯一 writer/controller，保持 GPT-6 Astra/high；不切模型、不启动第二 OMP、不升级软件或同步全局配置。
- 获准正常公开 Git 定点取上游对象、PR1 范围实施与验证、报告保存、本分支 commit/push、创建面向 `KunoLu/sbtd-plugins:main` 的 PR。未授权 merge、PR2、tag、release、npm 发布、外部评论自动回复或登录流程。
- 入口 HEAD 与远端 main 均为 `0d9331bd7d64c28dea368fd4385fd009809d58da`；main 未前进，无需改变基线。唯一未跟踪文件为本 task；未发现另一 OMP/codex/claude/reviewy writer。当前 OMP cwd 已核对为本仓。
- 远端公开 tag 预检：`v2.1.0` 对象 `7390b47ba44b1d8cb138e6b82769aeb9f3a0ac2d`，peeled commit `3c835303c23d59d3157ca84121a92f1bd87d4997`。尚须隔离获取对象并核对十二技能精确差异；此处不宣称通过。
- `TaskStore.current_binding()` 与目标 `TaskDocument.parse` 只读执行成功。发现草案事件节标题不符合 parser 的精确标题，识别事件数为 0；本次仅将该标题改为 `## 状态事件`，保留两条原始事件并追加批准/开始事实。不运行已知会受历史全库 schema 影响的 catalog，不声称 TaskStore 全库生命周期操作通过。

## 上游核验完成与实施开始（2026-11-18T13:58:43+08:00）

- 在隔离目录 `/tmp/dsh-pr1-upstream.fN6coB` 使用 `--filter=blob:none --no-checkout --depth=1 --single-branch --branch v2.1.0` 克隆，只额外 fetch 旧 pin；未修改 `/Users/lusonglin/github/640-skills`，未 checkout 整棵上游。
- tag 对象 `7390b47ba44b1d8cb138e6b82769aeb9f3a0ac2d`；peeled commit / 隔离源 HEAD 均为 `3c835303c23d59d3157ca84121a92f1bd87d4997`；旧 pin 对象可读。clone 输出 annotated tag “is not a commit” warning，随后 peeled commit/HEAD 核对成功，命令整体退出 0；不是 fetch 失败或重试。
- 十二项白名单两端各十九文件，六个文件修改，零新增、零删除；变化技能严格等于 sbtd-task/domain-modeling/grilling/to-tickets。具体路径：`domain-modeling/SKILL.md`、`grilling/SKILL.md`、`to-tickets/SKILL.md`、`sbtd-task/SKILL.md`、`sbtd-task/references/presentation.md`、`sbtd-task/references/state.md`。其余十三文件 blob/mode/sourcePath 不变。
- 正文已读：上游 GLOSSARY 命名、提问推荐方向、ticket 关系、task 节点核对和 presentation 规则变化均按原文镜像；不在插件内重新设计领域模型，不执行手册描述的迁移或全局操作。JSON schema blob 不变。
- 前置审查：Legacy Change Safety Review = characterized / normal；保留十二项白名单、逐 blob 字节、错误拒绝、原子替换，既有 T4 fixture 已建立安全网，无新 seam。Refactoring Review = proceed / normal；仅 pin 配置及对应契约更新，无需重构。两项在首次生产编辑前输出。
- BDD 沿用中文场景、英文 Gherkin 关键词；仅目标 pin 变化，现有 T4 场景保持，两个 T4 测试负责可执行映射。本轮不是全仓 BDD 同步，也不新增措辞型测试。
- 原始证据：`reports/upstream-fetch-20261118-1357.txt`、`reports/upstream-diff-20261118-1358.json`、`reports/upstream-body-diff-20261118-1358.txt`；中文汇总将同 stem 保存。当前开始获批同步，未声称测试通过。

## 本地验证与提交准备（2026-11-18T14:03:15+08:00）

- `bash -n .../sync-manuals.sh` 与 T4 定点：6 passed / 0 failed / 0 skipped，exit 0，2820.799875 ms。两个测试文件覆盖原有正负向契约，不新增测试框架。
- 逐一验证十九个目标文件：Git blob 字节、MANIFEST sha256、精确文件集合一致；直接执行 `dsh-manuals-pin` 的现有静态断言步骤，exit 0。
- `pnpm --filter @kunolu/dsh-sbtd test`：TypeScript 编译成功；342 passed / 0 failed / 0 skipped，exit 0，runner 6051.483167 ms。包含真实 `dsh@0.2.0-rc.2` 注册与 pre-step 用例；不是三个宿主版本的完整证据。
- 该 pnpm test 命令自动触发 workspace supply-chain 检查与依赖补装（+403/-260，47.5s），含下载慢 warning；没有另行执行 install 命令，不冒称 frozen install 独立通过。随后安全核对未发现 lockfile、package 元数据、omp 文件或其他任务 dirty；只存在本 PR 预期十三个文件。没有修改全局软件或配置。
- 本地环境 Node v24.15.0 / pnpm 11.17.0，与 workflow Node 22 分开记。原始/中文配对报告已生成并核对九节顺序、无模板占位符、同 stem 与非空 raw；本地证据仍为 developer-local / dirty / local-only，不冒充提交后 CI。
- Code Readability Review：手写生产改动仅两条 pin 常量；测试/feature/workflow 对应值保持现有清晰结构，生成镜像不手改。ponytail-review：无新增抽象、依赖或冗余逻辑，无需简化；这是主会话自审，不是独立 Reviewy。
- 未独立运行 lint/typecheck/build：src 未改，包 test 已执行 tsc；不夹带既有 lint 清理。真实模型 E2E、Web/Mobile 未运行：非本 PR 手册同步验收面。BDD=traceable；T4 feature 中文场景/英文关键词保持；Cross-repo context=complete（目标 blob 与源路径），Mock Strategy=contract-backed（T4 fixture）。
- 开始提交、推送与 PR 创建准备；GitHub 仓库查询确认 push 权限，当前分支无既有 open PR，远端 main 仍等于原基线。CI、三版本矩阵与独立 Reviewy 尚待执行，保持 checking，不满足 done 或 release-ready。

## PR 与 CI 运行记录（2026-11-18T14:05:11+08:00）

- 实现提交 `b572e7241677a1519c09628cc5abecabe9524831` 已推送本分支；13 files changed，351 insertions，58 deletions。PR：<https://github.com/KunoLu/sbtd-plugins/pull/127>，base=`main`，state=`OPEN`。
- PR 描述明确请求独立 Reviewy strict；当前平台显示 `REVIEW_REQUIRED`、reviews=[]、reviewRequests=[]。没有 Reviewy CLEAN，未通过其他模型或主会话自审代替。
- `dsh-manuals-pin` run `44248627440` 在上述提交上 success；raw JSON 与完整日志已保存，含 T4 与真实上游重同步幂等步骤，详细数字随后由原生日志提取。
- 已用精确候选 `candidateDshVersions=0.2.2-rc.3` dispatch `dsh-host-compat` run `44248624861`；同一提交的两个 REQUIRED pin 与候选行结果待读取，不能以调度成功充当兼容通过。
- 仓库既有 PR 触发器自动启动 `omp-runtime-linux-probe` run `44248627354`，未修改 omp，也未主动增加 omp 验收范围；结果单独记录，不当作本机 OMP 18.20.3 或历史 18.19.0 的新认证。
- 当前 CI watcher 只等待本任务启动的运行；不登录、不改外部评论、不 merge、不启动 PR2。后续任务记录提交不得把旧 SHA CI 冒充新 HEAD，最终 HEAD 的 CI 将单独复核并留证。

## 验收阻塞与停止记录（2026-11-18T14:07:57+08:00）

- 本轮 CI 实际源 SHA 全部为 `b572e7241677a1519c09628cc5abecabe9524831`；以下不是稍后阻塞记录提交的 CI 证明。最终记录提交只改 task，不主动重跑已失败候选；恢复时须针对真实新 HEAD 完成适用 CI。
- `dsh-manuals-pin`：run `44248627440` success，T4 6 passed / 0 failed / 0 skipped；真实上游同步后的 `git diff --exit-code -- packages/dsh-sbtd/manuals` 成功。
- `dsh-host-compat`：run `44248624861` 顶层 success，但候选 job failure。已逐 job 核对，**本任务兼容验收失败**，不接受 continue-on-error 的顶层绿灯。

| 验证项 | Job ID | 原始结果 |
|---|---|---|
| REQUIRED unit + pack dist/ | 134613574751 | 342 passed / 0 failed / 0 skipped；pack dist 检查成功 |
| REQUIRED dsh 0.2.0-rc.2 | 134613916674 | success；register smoke ok 0.2.0-rc.2 0.2.0-rc.2 |
| REQUIRED dsh 0.2.1-rc.2 | 134613916672 | success；register smoke ok 0.2.1-rc.2 0.2.0-rc.2 |
| Advisory dsh 0.2.2-rc.3 | 134613916615 | failure；exit 1；TOOL_EXECUTOR_UNAVAILABLE |

- 候选已成功安装并加载插件；失败位于共享 `smoke.mjs:68` 的 `ctx.systemPrompt.assemble({})`，调用 `dsh-tools@0.2.2-rc.3` 的 `ToolsService.selectExecutor`。原文：`ToolExecutorUnavailableError: The selected tool executor is unavailable. Load an executor in this composition before running the agent.` Node v22.23.4。此后 schema/pre-step/ask 检查未完成；不能将未执行算作通过。
- 已有真实失败即复现，不重复执行以确认。直接机制为 smoke composition 未提供候选宿主所需 executor；现有证据不能证明插件本体在完整宿主中不兼容。获批范围明确复用而不改 `dsh-host-register-smoke.mjs`；不擅自加载未知 executor、修改宿主依赖、生产 src、workflow 或跳过断言。需要用户裁决是否扩充 PR1 为 smoke 组合适配，还是另立适配任务。
- 自动 `omp-runtime-linux-probe` run `44248627354` success；仅保留既有自动检查事实，不声明 OMP 18.20.3/18.19.0 新验收。Actions Node 引擎/Ubuntu 镜像迁移 annotation 未作为本 PR 改配置的理由。
- 三个 CI run 的 raw JSON、完整日志和各自同 stem 中文汇总已存于 `reports/ci-{manuals,host,automatic-omp}-<run-id>*`；失败日志保留，候选与两条 REQUIRED 的 job ID/结果分别列出。API/模型 E2E 未运行，不补造测试数字或模型调用统计。
- Release Readiness Review = blocked：容量/背压/服务告警不适用；供应链 pin 与原子替换保持，未部署、迁移或清理。必需候选验证失败，Reviewy strict CLEAN 尚缺，不能完成任务、合入或发布。
- lessons-record 已评估：草案事件标题问题已由现有精确标题规则覆盖，不新增重复 lesson；候选 executor 更深适配方案尚未验证，不写推测性长期知识。不解析或创建 developer 身份。
- 接下来仅提交并推送本任务阻塞记录，向用户报告后等待指示；不回复外部评论、不合入、不开始 PR2、不发布。该记录提交不是 CLEAN 后 B 方案 done 收尾；`completed_at` 保持 null。

# PR1 计划草案：dsh manuals 同步 640-skills v2.1.0

## 任务身份、阶段与授权

- 作者／唯一 writer：当前 Mac Orca 中的 OMP 会话（AI 计划执笔，不冒用用户身份）。
- 模型：`openai-codex/gpt-6-astra`；effort：`high`（用户指定保留）。不切模型，不开新 OMP，不派发实现任务。
- 当前阶段：计划草案待用户审核；PR1 尚未开始实施。`planned` 不代表任何开发或验收门禁通过。
- 时间统一使用 Asia/Shanghai（`+08:00`）。未统计模型调用次数，不虚构 assistant messages、tool calls 或 reviewer 调用数据。
- 本轮唯一文件产物为本 task.md；仅另建获准的本地分支。不改 active、index、handoff、developer、ignore 或全局配置。
- 本机 OMP 为 `18.20.3`，来源为用户确认；原 omp 验收基线 `18.19.0` 单独保留。本轮不运行宿主版本命令，不升级、降级或将两个环境的证据混用。
- 未完整调用 grill-with-docs：用户已明确四 PR 顺序、PR1 边界和计划先审门槛；本轮只依据现有脚本和配置起草，不确认尚缺的上游差异。

## 四 PR 顺序与先审后做门槛

1. PR1：dsh 手册同步；本文件仅覆盖此项。
2. PR2：dsh 发版准备，包括 package/plugin/SBOM 版本提升及 CHANGELOG/README 发版内容。
3. PR3：omp 同步。
4. PR4：omp 发版准备。

逐包、逐 PR 串行推进，不并行。每个 PR 都先提交 strict task.md 给用户审核；获得该 PR 的明确实施批准后才执行。实现完成后取得对应提交的 Reviewy strict CLEAN 与 CI 全绿，再等待用户合入；不得自动合入或提前推进下一 PR。

本轮不 commit、push、开 PR 或 dispatch CI。后续提交、远端写入与 CI 调度须有相应授权。任何发布、Git tag、GitHub release、npm publish、npm latest/next 修改均未获授权；四 PR 准备方案不授予这些权限。

## 只读入口事实与证据边界

- 授权根：`/Users/lusonglin/github/sbtd-plugins`。
- 入口分支为 `main`；HEAD：`0d9331bd7d64c28dea368fd4385fd009809d58da`。
- `git status --porcelain=v1 --untracked-files=all` 无输出；目标分支原先不存在。创建分支前再次核对 main、完整 HEAD、dirty 和目标路径，均符合本轮写入条件。
- 本地 `origin/main` 与 `origin/HEAD` 指向同一 HEAD；没有 fetch，不能据此声明远端当前状态。
- 本地插件 tags：`dsh-sbtd-v0.2.0-rc.1`、`dsh-sbtd-v0.2.0-rc.2`、`omp-sbtd-v0.2.0-rc.1`、`omp-sbtd-v0.2.0-rc.2`；未发现 rc.3 tag。
- `ai/tasks` 与 `.sbtd/tasks` 未检出 planned/in-progress/checking/blocked 状态；active 指向已 done 的 `publish-graft-0.22.0-agents`，不改旧记录或指针。
- 只读进程名及相关进程 cwd 检查未发现另一 OMP 在本仓执行；当前 OMP cwd 为本仓。该检查是当前观察，不是持续锁或对未暴露会话的保证。
- `ai`、`ai/tasks` 为正常目录，目标目录此前不存在；目标 task 可跟踪，reports 由 `/ai/tasks/**/reports` 保护，`.sbtd` 由 `/.sbtd` 保护。
- 模板沿用既有 `dsh-sbtd-0-2-0-rc-1-pr-a-manuals/task.md` 与 `omp-sbtd-0-2-0-rc-2-prep/task.md` 的 frontmatter、Book Gate Plan、五列事件和证据边界，不复制旧测试或 CLEAN 结论。
- 本文件为明确要求的共享 Markdown 草案，未调用 TaskStore/TaskSync 执行生命周期操作，不声明 helper 校验或自动恢复成功。未跟踪阶段按 C 文件范围留证；本轮范围仅本任务目录，task 不作自引用哈希；所读关键输入 SHA256 见文末。没有执行需要 fetch 的 A 核对。

## 上游 pin：完整 SHA 待核

| 项目 | 本轮事实 |
|---|---|
| 目标来源 | `KunoLu/640-skills`，用户指定 `v2.1.0` / 短 SHA `3c83530` |
| 目标完整 commit SHA | **待核，未解析成功；不得填写推测的 40 位 SHA** |
| 本地上游根 | `/Users/lusonglin/github/640-skills`，仅定点只读检查，不遍历其他项目 |
| 本地上游 HEAD | `80f14263e7d8bc6ae84f04ba94218e4857fc8b8f`，不是目标 pin 的替代品 |
| tag/object 检查 | 上游与本仓的 `rev-parse --verify 'refs/tags/v2.1.0^{commit}'` 和 `rev-parse --verify '3c83530^{commit}'` 均报 `fatal: Needed a single revision` |
| 已有上游 tag | 本地有 `v2.0.2` 及 `v2.1.0-rc.1` 至 `v2.1.0-rc.4`，没有 `v2.1.0`；不采用任何 rc tag 替代 |
| 当前 dsh manuals pin | `2.0.2` / `1d82494d74f6df9bca7dccef2da409f87091883e`，脚本、MANIFEST、T4 与 pin workflow 一致 |

用户允许缺对象时明确待核，因此仍可提交计划草案；**上游身份核实与实际差异确认是后续同步的前置阻断项**。本轮未联网取 tag、clone、fetch 或下载依赖。

后续获准取上游后，必须记录 tag 对象与 peeled commit 的完整 SHA，确认 commit 以 `3c83530` 开头，并将完整 SHA 回填本计划及全部 pin 点。如果 tag、短 SHA、四技能差异或十二项白名单前提不符，停止并报告，不能悄悄换源或扩大范围。

## PR1 拟议范围与预期文件

保持十二项白名单不变：`book-ddd-distilled-modeling`、`book-ddia-data-design`、`book-legacy-change-safety`、`book-refactoring-pass`、`book-release-readiness`、`grill-with-docs`、`grill-me`、`grilling`、`domain-modeling`、`to-spec`、`to-tickets`、`sbtd-task`。

脚本每次生成全部十二项的 `SKILL.md` 与各自 `references/**`，不是仅跑四项。预期正文差异只在 `sbtd-task`、`domain-modeling`、`grilling`、`to-tickets`；其他八项必须核实无正文变化。MANIFEST 中全部条目的 sourceRevision 会随 pin 更新，即使相应文件字节未变。

| 预期文件／边界 | 后续获准修改内容 |
|---|---|
| `packages/dsh-sbtd/scripts/sync-manuals.sh` | 仅 `PINNED_REVISION` 与 `PINNED_VERSION` 改为核实后的完整 SHA / `2.1.0`；保留白名单、源定位、字节复制、失败拒绝和原子替换算法 |
| `packages/dsh-sbtd/manuals/sbtd-task/SKILL.md`、`references/**` | 由脚本按目标 Git blob 生成；现有 references 为 handoff.md、methods.md、presentation.md、state.md、strict.md、task-data.schema.json、tooling.md |
| `packages/dsh-sbtd/manuals/{domain-modeling,grilling,to-tickets}/SKILL.md` 及目标树确有的 `references/**` | 仅脚本生成；目标新增、删除、变更的精确路径须待完整 SHA 可读后列明，不预称本地旧清单就是目标清单 |
| `packages/dsh-sbtd/manuals/MANIFEST.json` | 脚本重建 version、sourceRevision、sourcePath 与逐文件 sha256；不手工改镜像正文或伪造摘要 |
| `.github/workflows/dsh-manuals-pin.yml` | 注释、静态断言 pin_rev/pin_ver、clone 阶段 pin 同步为目标值；保留独立 dsh 门禁 |
| `packages/dsh-sbtd/test/t4-manuals.test.mjs` | 更新 PIN 与版本断言；保留十二项白名单、checksum、JSON schema 覆盖 |
| `packages/dsh-sbtd/test/t4-sync-exit.test.mjs` | 更新现行 PIN；保留缺源/SHA mismatch/copy/checksum 失败与原始 blob 字节、无旧目标目录场景 |
| `packages/dsh-sbtd/features/t4-manuals-sync.feature` | 只对齐目标版本与完整 SHA，沿用中文场景、英文 Gherkin 关键词及既有可观察契约 |
| 本 `task.md` | 用户决定、精确差异清单、实际命令结果、Reviewy 与 CI 证据；只在真实阶段更新 |

`.github/workflows/dsh-host-compat.yml` 与共享 `dsh-host-register-smoke.mjs` 仅复用，不计划修改。使用现有 `candidateDshVersions` 输入传 `0.2.2-rc.3`，不调整 peer、engines、devDependencies 或 lockfile。

明确排除：全部 omp 文件；package/plugin/SBOM 版本提升；CHANGELOG/README 发版；640-skills rc.2 替代方案；graft 移除新计划；全局同步、软件更新、安装器复制、上游代码修改。目标树若要求源布局或同步算法适配，先停止重新审核，不临时扩围。

## Book Gate Plan

以下为计划状态，不是已执行 reviewer 结论。

| Reviewer | 触发事实与阶段 | 当前状态／后续门槛 |
|---|---|---|
| book-ddd-distilled-modeling | 未完整 grill；上游词汇手册按 blob 镜像，无本项目新领域模型设计或歧义 | not-required；目标正文已读，不借本 PR 重设计术语 |
| book-ddia-data-design | JSON schema blob 未变；只镜像 task 状态说明，不改变插件存储或执行迁移 | not-required；无 schema 语义或数据所有权设计 |
| book-legacy-change-safety | 原候选 CI 已提供真实 red；三个发布包证实 builtin/native executor API 差异 | passed；本次修复 characterized / normal，现有完整 smoke 是回归 seam，无新增 seam 或模拟 provider |
| book-refactoring-pass | 首次共享 smoke 编辑前复核初始化、模块归属与保留断言 | passed；本次修复 proceed / normal，仅能力探测后挂载官方 native 插件，无重构 |
| book-release-readiness | 修复提交三版本与包/pin CI 已成功，记录提交须再次绑定最终 HEAD | blocked；仅剩最终记录 HEAD 的 CI 复验及用户协调的独立 Reviewy，非原 executor 技术失败 |

后续 before-dev 还须读取适用 ponytail、gherkin-bdd、project-validation 方法，核对影响面。若发现新行为或 bug，先确认行为规范与回归证据；不得以改 PIN 掩盖失败。已有测试足够时不另造措辞型测试。

## 后续执行顺序与准确命令（本轮一律未执行）

### 1. 用户审核与上游身份

获得明确实施批准后，先重读本 task，核对分支、dirty、任务并发及授权范围，追加真实开始记录。发现用户改动或别的任务在运行即停，不 reset/stash/clean。

对已有本地上游只读复核：

```bash
UPSTREAM=/Users/lusonglin/github/640-skills
GIT_NO_LAZY_FETCH=1 git -C "$UPSTREAM" rev-parse --verify 'refs/tags/v2.1.0'
GIT_NO_LAZY_FETCH=1 git -C "$UPSTREAM" rev-parse --verify 'refs/tags/v2.1.0^{commit}'
GIT_NO_LAZY_FETCH=1 git -C "$UPSTREAM" rev-parse --verify '3c83530^{commit}'
```

本地缺对象时，联网获取仍待后续授权；使用隔离源目录，不切换用户现有上游 checkout。核实目标完整 SHA、十二项目录和源 blob 差异，再回填精确新增/删除/变更列表。没有完整 SHA 时禁止开始 pin 编辑或同步。

### 2. 对齐契约与同步

完成适用 before-dev 门禁后，先对齐既有 feature、T4 pin、脚本常量及 pin workflow。脚本无 SOURCE 时会执行 clone、fetch、detached checkout；以下命令仅在联网取源获准且完整 pin 已核实后执行：

```bash
bash packages/dsh-sbtd/scripts/sync-manuals.sh
bash -n packages/dsh-sbtd/scripts/sync-manuals.sh
node --test packages/dsh-sbtd/test/t4-manuals.test.mjs packages/dsh-sbtd/test/t4-sync-exit.test.mjs
```

离线路径为 `bash packages/dsh-sbtd/scripts/sync-manuals.sh "$SOURCE"`；`SOURCE` 必须指向已核实且 HEAD 等于完整 pin 的隔离 Git worktree。脚本读取 Git blob，不读取本地修改后的技能正文。不得用本机 tip、当前全局 Skill 或未验证缓存代替目标 commit。

同步后将全部 MANIFEST 项与目标 Git blob、实际文件集合及 sha256 逐一比较；检查非 Markdown schema 字节。再次同步的幂等性由 `dsh-manuals-pin` workflow 的 `git diff --exit-code -- packages/dsh-sbtd/manuals` 检查；其前提是首次同步结果已纳入待验提交，不拿首次预期 diff 当作失败。

### 3. dsh-host-compat 验证

当前 workflow 为仅 `workflow_dispatch`；必需 pin-smoke 两行仍为 `0.2.0-rc.2`、`0.2.1-rc.2`。目标 `0.2.2-rc.3` 使用 advisory 输入，不能因顶层 workflow success 就忽略 `continue-on-error` 的候选行失败。

获准提交、push 及调度后，对承载已批准实现的同一分支运行：

```bash
gh workflow run dsh-host-compat.yml \
  --ref docs/dsh-sbtd-0.2.0-rc.3-pr1-plan \
  -f candidateDshVersions=0.2.2-rc.3
```

若后续改用其他实施分支，必须先明确重绑定 task，再使用真实分支；不得照抄本命令把验证发到错误 SHA。本轮不核实 gh 登录、不触发远端操作。

复用 workflow 的实际命令链：`pnpm install --frozen-lockfile` → `pnpm --filter @kunolu/dsh-sbtd test` → `pnpm --filter @kunolu/dsh-sbtd pack --pack-destination "$dest"` → 检查唯一 tarball 含 `package/dist/index.js` → 同一 tarball 的独立宿主 cell。

候选 cell 精确沿用共享 smoke，以下只展示后续隔离环境步骤；`cell`、`tarball`、`GITHUB_WORKSPACE` 须由已核验的 workflow 步骤提供：

```bash
mkdir -p "$cell"
printf '%s\n' '{"name":"dsh-host-cell","private":true}' > "$cell/package.json"
cp "$GITHUB_WORKSPACE/.github/workflows/scripts/dsh-host-register-smoke.mjs" "$cell/smoke.mjs"
(
  cd "$cell"
  pnpm add --config.dangerouslyAllowAllBuilds=true "@deepseek-ai/dsh@0.2.2-rc.3" "$tarball"
  DSH_PIN_SMOKE=0 DSH_VERSION=0.2.2-rc.3 node smoke.mjs
)
```

此步骤会联网并执行依赖构建脚本，只能在获准的隔离 CI/cell 运行，不升级本机宿主、不改仓库依赖或全局配置。候选 smoke 精确断言实际 dsh 版本、工具/section/命令注册、schema、pre-step notice 与无 plan 时 ask；它不是完整模型 E2E。`DSH_PIN_SMOKE=0` 不覆盖仅 pin 模式执行的 dsh-tools 版本及包 peer/engines 附加断言，必须如实保留此证据边界。

## 验收、Reviewy 与收尾计划

- [x] 用户明确审核通过本 PR1 strict 计划并批准实施；2026-11-18 13:55 Asia/Shanghai 本人原话已由当前用户消息确认。
- [x] `v2.1.0` 与 `3c83530` 解析到同一可核实完整 commit SHA，已回填 pin 及证据；目标实际差异符合四技能范围。
- [x] 十二项白名单保持，复制范围仅各自 SKILL.md/references；没有安装器、agents 或 skill-root 附加 Markdown；其他八项正文未变。
- [x] MANIFEST 元数据、文件集合、逐项 sha256 和 Git blob 原始字节一致；脚本、feature、T4、workflow 的 pin 全部一致。
- [x] T4 既有正负向契约通过，sync 幂等；本地 6/0/0，CI run 44248627440 的真实重同步无 diff；候选宿主失败另记，不以此勾选冒充全验收通过。
- [x] 代码修复提交 cc9ff936017084f737cbea080bf0ddb043a50caa 的 dsh-manuals-pin、完整三版本及自动仓库 CI 已通过；记录提交后的最终 HEAD 另行真实复验并输出精确 SHA，不能沿用本项旧证据。
- [ ] project-validation、Code Readability Review、适用 ponytail-review 与 Book gates 留存真实结论；本轮不得预填 passed/CLEAN。
- [ ] Reviewy strict 对实际实现提交给出 CLEAN；记录完整 SHA、审查轮次及真实证据，不用主会话自审替代。
- [ ] 按 B 方案收尾：CLEAN 后另作只改 task 的限定收尾提交，仅变 status/completed_at/updated_at、追加 done 事件及 CLEAN SHA/CI run 证据；Reviewy 复核限定 diff，最终 CI 仍全绿。其他变化必须重新完整审查。
- [ ] 等待用户合入 PR1；未经合入决定不推进 PR2，不执行发布/tag/npm dist-tag。

正式报告沿用本任务 `reports/` 的原生/raw 与同 stem 中文汇总，记录实际 SHA/worktree/环境、失败、跳过与发布状态。本轮不创建 reports，也不生成测试结果。不能把本机 `18.20.3`、历史 `18.19.0` 或旧 CI 的证据归入本次 dsh `0.2.2-rc.3` 验收。

BDD 仅计划对齐现有 T4 场景并映射至两个 T4 测试文件；本轮没有修改 feature、没有运行全仓 BDD sync。跨仓目标内容证据为 missing，脚本现有同步契约可读，但不冒称已验证 v2.1.0。Graft skipped：仅用源码与本地 Git 元数据，无图刷新或接线；Web/Mobile 和真实模型 E2E 本轮未运行。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-11-18T13:47:37+08:00 | planned | planned | OMP 当前会话：开始 PR1 计划只读预检；实施未授权 | main / 0d9331bd7d64c28dea368fd4385fd009809d58da；入口工作树干净；读取已加载 AGENTS 与 strict 工作流 |
| 2026-11-18T13:49:26+08:00 | planned | planned | OMP 当前会话：完成只读预检并建立草案分支；保持计划待审 | 本地目标 tag/object 缺失已记录；模板、脚本、T4、feature、CI 配置已读；仅创建 docs/dsh-sbtd-0.2.0-rc.3-pr1-plan，无同步、构建、安装或测试 |
| 2026-11-18T13:57:10+08:00 | planned | in-progress | OMP 当前会话：记录用户 13:55 批准 PR1，开始获批执行的上游身份与范围核验 | 当前用户消息；本任务唯一未跟踪产物；远端 main 与 HEAD 一致；公开 tag peeled SHA 以 3c83530 开头；尚未同步或测试 |
| 2026-11-18T13:58:43+08:00 | in-progress | in-progress | OMP 当前会话：完成上游身份与范围核验 | tag peeled=3c835303c23d59d3157ca84121a92f1bd87d4997；12 技能/19 文件/6 修改/0 新增删除；恰四技能；reports/upstream-diff-20261118-1358.json |
| 2026-11-18T13:58:43+08:00 | in-progress | in-progress | OMP 当前会话：开始 PR1 pin、生成手册与契约对齐 | before-dev Legacy characterized、Refactoring proceed；只编辑批准的 dsh PR1 范围；报告与验证待执行 |
| 2026-11-18T13:59:56+08:00 | in-progress | checking | OMP 当前会话：完成 PR1 pin/契约编辑与脚本生成，开始本地验证及宿主兼容验收 | sync-manuals.sh 指向隔离目标 HEAD，退出 0；reports/manuals-sync-20261118-1359.txt；测试与 CI 尚未执行，不预填通过 |
| 2026-11-18T14:03:15+08:00 | checking | checking | OMP 当前会话：完成本地定点、完整包与十九文件核验 | T4 6/0/0；全包 342/0/0；MANIFEST/blob 与 workflow 断言成功；reports 原始+中文同 stem 已核对；CI 未跑 |
| 2026-11-18T14:03:15+08:00 | checking | checking | OMP 当前会话：开始获准本分支 commit/push 与 PR 创建，后续执行三版本 CI | 远端 main 未前进；安全核对仅十三个预期文件；gh 仓库 push 权限已核对；不合入、不发布、不自动回复评论 |
| 2026-11-18T14:05:11+08:00 | checking | checking | OMP 当前会话：完成实现提交、push 与 PR 创建 | b572e7241677a1519c09628cc5abecabe9524831；PR #127 OPEN/main；无 merge/tag/release/npm；Reviewy 尚无结论 |
| 2026-11-18T14:05:11+08:00 | checking | checking | OMP 当前会话：开始记录提交后 CI 与三版本兼容结果 | dsh-manuals-pin 44248627440 success；dsh-host-compat 44248624861 运行中；自动 omp-runtime-linux-probe 44248627354 运行中 |
| 2026-11-18T14:07:57+08:00 | checking | blocked | OMP 当前会话：完成首轮三版本 CI 结果核对，候选失败触发阻塞并停止实现 | b572e7241677a1519c09628cc5abecabe9524831；host run 44248624861，job 134613916615 exit 1 / TOOL_EXECUTOR_UNAVAILABLE；两条 REQUIRED 分别 success；不改获批范围外 smoke |
| 2026-11-18T14:07:57+08:00 | blocked | blocked | OMP 当前会话：开始提交阻塞记录并准备报告，等待用户裁决 smoke 适配范围 | PR #127 保持 OPEN；原始+中文 CI 证据已保留；Reviewy strict CLEAN 尚缺；无 merge、PR2、tag、release、npm 操作 |
| 2026-11-18T14:20:35+08:00 | blocked | checking | OMP 当前会话：记录用户 14:19 扩围批准，按已证明的 checking 前态解除范围阻塞 | 当前用户原话；入口 HEAD 301325fd976c012a81138df645ed7574568e6b90；工作树干净；历史失败保留；不声称验证或 Reviewy 通过 |
| 2026-11-18T14:20:35+08:00 | checking | in-progress | OMP 当前会话：开始获批 executor API 调查与共享 smoke 最小修复 | 仅共享 smoke 初始化与任务/报告；保留全部断言，不改依赖/产品代码；真实三版本新 HEAD CI 待执行 |
| 2026-11-18T14:23:26+08:00 | in-progress | in-progress | OMP 当前会话：完成三个实际宿主 executor API 调查，开始最小初始化修复 | 发布包 sha512 验证；旧两版 builtin native，新版 setExecutor + 官方 native 插件；从 sdk-minimal 的既有精确依赖解析；保留全部断言 |
| 2026-11-18T14:24:19+08:00 | in-progress | checking | OMP 当前会话：完成共享 smoke 五行初始化增量，开始三版本实际回归 | 仅新增 setExecutor 能力判断与从 sdk-minimal 解析/挂载官方 native executor；原有断言未删改；先本地 Node 24，后新 HEAD CI |
| 2026-11-18T14:26:41+08:00 | checking | checking | OMP 当前会话：完成本地三版本完整 smoke，开始获批修复 commit/push 与新 HEAD CI | 三 cell 均 exit 0，同 tarball SHA256 20acf48bfbc5a45bdb871c911be97ed4c8551d6889efa7a2f762692754313737；仅 smoke/task 两文件 dirty；raw+中文已保留；不对外发送评审消息 |
| 2026-11-18T14:29:55+08:00 | checking | checking | OMP 当前会话：完成修复提交 push 与首轮真实三版本 CI，保留全部原生证据 | cc9ff936017084f737cbea080bf0ddb043a50caa；host 44251445990 三 cell success/342 单测；manuals 44251452139 6 单测；自动 omp 44251452147 success |
| 2026-11-18T14:29:55+08:00 | checking | checking | OMP 当前会话：完成闭环记录准备，开始最终记录提交后的同范围新 HEAD CI | 只提交 task，不改 smoke/依赖；最终真实 SHA 与 CI/raw/中文交付保存 ignored reports，避免再移动已验 HEAD；Reviewy 留用户协调，不发外部消息 |

本轮只执行只读核对、分支创建与本文件写入。没有实现、测试结果、Reviewy CLEAN、CI 成功、commit、push、PR 或发布事实可报告。草案交付不将任务转 checking/done，`completed_at` 保持 null。

## C 范围输入快照（SHA256）

以下为创建计划分支时实际读取的关键输入，不是测试报告；task 自身不参与自引用哈希。

```text
b4db5073df32cd999653fa67703bdab41e08063d5ca9b9be9593ed152c679a45  packages/dsh-sbtd/scripts/sync-manuals.sh
aa75362516731ceeca684c0f0a57fcf7c02905275fc71f83cb36248ac8933b87  packages/dsh-sbtd/manuals/MANIFEST.json
cd13674b5dc7957d377b831e451495bb816975b1553b9580ff3f65868f4c40fc  .github/workflows/dsh-manuals-pin.yml
6311d2f13474f5488976ddf36af07f0a5d669fa2b05acce5eeab82df03f9852e  .github/workflows/dsh-host-compat.yml
1602172c177652714c8ecdfeff1b8bb0295ff6fd5114197b72bd1ea6d2533241  packages/dsh-sbtd/test/t4-manuals.test.mjs
eebb2a054aafb161e74702952a41e518890d3bcdfa38aa55703fbb0aedb84d3e  packages/dsh-sbtd/test/t4-sync-exit.test.mjs
573c9311cdf874a79623cae69593a363f0911fdeeda599528ab9aba56e4ccc0b  packages/dsh-sbtd/features/t4-manuals-sync.feature
a2ffd3c89d793277a7b905316cecea7bb6e081c073c68608ca0d6b603215e8b7  .github/workflows/scripts/dsh-host-register-smoke.mjs
7bb34f9ebec72c8faca67f3471fe36c8ecc3ef3da0b1fc86550f6080dea1e02c  packages/dsh-sbtd/package.json
```

## 停止与恢复边界

下一步仅为用户审核。上游完整 SHA 与精确变更路径待后续取源授权后核实；该缺口不能被当作同步成功。若发现 dirty、并发 writer、分支不符或方案偏差，停止对应写入并报告，不 reset/stash/clean，不切模型或重开 OMP。

本轮不执行回滚。后续若需撤销实现，只能针对已批准范围提出保留用户数据的撤销方案，另取授权；不能借“恢复”删除用户改动、清理 ignored 证据或修改 HOME。当前草案不保证 TaskStore 自动恢复，不代表完整 strict 生命周期或发布就绪。
