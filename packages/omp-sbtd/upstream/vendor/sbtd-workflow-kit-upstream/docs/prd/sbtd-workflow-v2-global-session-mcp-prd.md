# SBTD v2：全局会话 Graft MCP 整改 PRD

## 1. 状态、来源与主 PRD 关系

- 用户在本次会话明确确认 OMP session `01a0fb46-a6aa-7305-9db5-6942c2a05be9` 最后一轮修正方案，并要求新建分支、按 strict 实施。
- 实施分支：`feat/graft-global-session-mcp`（合并成功后已删除本地及远程分支）；起始 HEAD：`39cf00bb7299d9f7b92153a5bd147382a40c478d`。
- 主线：[去 Trellis 化与 Graft 替换主 PRD](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md)。本文承接全局安装／会话项目解析整改；主 PRD 保留原始审核、已执行批次与发布台账，不重写历史成功的含义。
- 文档选择：新增关联 PRD。整改横跨安装、全局配置、项目初始化、受管 launcher 和旧接线迁移，具有独立验收生命周期；不把完整实现设计继续堆入主 PRD。原主 PRD P3-05 承接实际环境退役，P3-04 继续拥有备份销毁边界。
- 当前状态：源码与验收已完成；[PR #108](https://github.com/KunoLu/640-skills/pull/108) 已于 `2026-10-03T04:38:30Z` 合并，merge `a2d0971c8fb10f91f4fb8c11be2d4432884762bf`。源码证据见 §7.3；独立授权的本机全局接线、新宿主验收及2026-10-05增量同步见 §11。P3-05已按精确清理及保留交接收口；[v2.0.0](https://github.com/KunoLu/640-skills/releases/tag/v2.0.0)于2026-10-14正式发布，实际SHA/CI见主PRD P3-03。不由源码发布推定所有GUI会话重载、所有历史环境删除或本机已升级。
- 前序可行性证明仅覆盖真实 OMP CLI/RPC、Codex CLI/app-server 与 Orca 终端到诊断 MCP 的 cwd 传递；不是新 Graft 查询实现证明。未验证的 GUI 专用启动器／managed-daemon／SDK 不扩大宣称。
- 历史输入：实施开始时的五份未提交文档修改属于前序调查成果，当时要求保留、不 reset、不丢弃；此项记录输入来源，不表示当前工作树仍有未提交修改。

## 2. 目标与授权

每个所选 host 的有效配置域只有一条通用受管 `sbtd-graft` stdio 定义；无固定 cwd、无固定项目 `--root`。进程实际 cwd 决定一条连接的唯一项目。全局安装可不选项目；项目初始化只准备本项目规则、图与 stamp。一次批量初始化和随后逐次追加使用同一项目操作，不引入 daemon、跨项目路由服务或全局项目注册表。

初始实施授权仅包含仓库代码、测试、文档和隔离验证，不自动授权真实 HOME 接线替换、全局安装、sync、发布、终止用户连接或备份销毁。后续管理员合并、分支删除及范围限定 sync 见 §7.3；另行确认的本机切换与增量对齐见 §11，不能将其中一项授权扩大为其他操作。真实 PC 切换须先展示精确前态／目标清单。条件清理只有在替代生效、host 验收、旧连接停止且无运行／恢复用途时才成立；本轮明确保留旧环境和全部备份。

## 3. 领域及不变量

- 全局运行时：正式安装的 Onboard launcher、声明依赖 Python、固定 pin Node/Graft。不得把验证 TEMP 路径作为正式安装默认目标。
- 配置域：OMP active profile、普通 Codex HOME 或宿主实际使用的 Codex HOME；一份逻辑定义不等于整个 PC 只有一份物理配置文件。
- 项目：当前工作目录所属的明确 Git repository/worktree；取最近边界，不能跳过未初始化嵌套仓去借外层图。
- 连接：启动时确定项目，整个生命周期不换根；shell cd 或协议 roots 变化不把旧连接切向别的项目。
- 无项目、HOME、中立共同父目录、缺图、旧 stamp、越界／symlink/reparse、工作区聚合图均 fail closed，不自动初始化、联网修复或回退 demo。
- 保持 pin、DNT、Python 启动隔离、私有 HOME、dotenv／LLM／cloud 隔离及每请求图路径复验。
- hooks 保持独立 opt-in；hook/analyze 的显式 root 不是全局 MCP 的项目绑定。
- 用户文件拥有所有权；仅凭 `sbtd-graft-*` 名字不足以删除。原迁移计划、回执、备份不可变，新切换保存新前态，不伪造旧证据。

## 4. 行为规格与验收

本仓禁止持久 `.feature`，使用本文中文场景及 English Given/When/Then；现有 unittest 承接自动化，不新增 BDD 框架。

| ID | Scenario / Given / When / Then | 验证边界 |
|---|---|---|
| GM-01 | Given 未选择项目且运行时就绪；When 安装所选 host 全局配置；Then 生成一条不含 cwd/root 的通用定义，不能声称任何图已可查询 | 全局 plan/init 与配置读回 |
| GM-02 | Given A 已初始化且全局定义存在；When 仅追加 B；Then A 的配置／图和全局定义不变，B 可独立查询 | 单项／批量等价及文件快照 |
| GM-03 | Given A/B 有不同真实代码图；When 同一全局定义启动并发连接；Then A 只命中 A，B 只命中 B，连接不共享根 | 真实 Graft + OMP/Codex/Orca 已用入口 |
| GM-04 | Given 已初始化仓库的子目录或 linked worktree；When MCP 启动；Then 锁定最近真实仓／worktree 根，不借主 checkout 图 | 原生 CLI 与根解析测试 |
| GM-05 | Given HOME／无仓／共同父目录／未初始化嵌套仓／缺图／旧 stamp／越界数据；When MCP 启动或请求；Then 非零或协议拒绝，原文件不变、不启动错误项目 | 安全拒绝与无副作用断言 |
| GM-06 | Given 已有无关 MCP 和用户配置；When 重复同一全局安装；Then 无关字节／语义保留，通用定义幂等；不同运行时或同名未知配置拒绝隐式覆盖 | TOML/JSON 候选及安装回归 |
| GM-07 | Given 精确旧受管固定根条目及独立迁移授权；When 切换至通用定义；Then 仅删除已验证归属和授权范围的旧项，保全前态；漂移、中断、重试、恢复均可核验 | 新切换计划／备份与回归；旧证据解析保留 |
| GM-08 | Given 无独立迁移授权或继承源含未知／冲突旧项；When 普通安装；Then 明确冲突，不删除或隐藏旧项、不清空 HOME | 所有权拒绝 |
| GM-09 | Given init-projects 模式；When 初始化一个或多个项目；Then 不写 HOME，复用全局连接且不隐式升级运行时 | 项目初始化集成 |
| GM-10 | Given 原受管安全策略；When 全局入口运行；Then pin/DNT/环境隔离／每请求复验仍生效，root 参数不能覆写 MCP cwd 选择 | 既有守卫回归 |

必过：全量项目测试、相应三平台 CI、独立代码与安全复核。未执行的远程 CI、未授权 live 切换不得标通过。所有正式本地证据保留原生/raw 与同 stem 中文汇总，dirty 证据仅 local-only。

## 5. 设计与最小实施边界

1. 在既有 `sbtd_graft_entry.py` 中按最近安全 `.git` 边界解析项目，再由 `_trusted_git` 选择项目外绝对 PATH 中的真实 Git，对实际启动 cwd 执行 `git rev-parse --show-toplevel --is-inside-git-dir`。探针移除继承的 `GIT_*`、禁用 system/global Git 配置；HOME 是停止边界，bare／Git 管理目录及顶层不匹配 fail closed，不借外层图。MCP CLI 不接受固定 root，hook/analyze 保持显式根约束；校验前不创建临时 HOME、不调用 native Graft。
2. Codex/OMP 既有候选渲染器改为单一 `sbtd-graft`；运行时身份与项目列表分离，无项目时仍能渲染。多个项目不能携带不同全局运行时。
3. `sbtd_graft_deployment.py` 复用现有资源操作、snapshot、前态备份与失败状态；全局阶段无项目可运行，init-projects 不写 HOME。逐项本地图生成不修改其他项目。
4. 旧固定根配置只作为显式迁移输入和历史回执验证格式保留，不再生成，不保留旧 MCP CLI alias。非授权旧项 fail closed；切换只改所有权已证明的精确条目，保留用户配置、历史备份和恢复路径。
5. 原生产任务表仍由主 PRD 拥有；本地 strict 任务记录仅恢复本次执行。PRD 记录需求、设计和验收，不充当第二模式状态源。

### 5.1 旧运行时切换的明确输入

普通安装遇到旧固定根条目时拒绝隐式替换。`--graft-retire-legacy`（Bash 同名，PowerShell `-GraftRetireLegacy`）仅授权已选根、完整旧 argv/env/cwd/hash 形状与运行时身份匹配的条目退役，不授权目录删除。

从旧 TEMP／旧 pin 切换到不同稳定运行时时，另传 `--graft-legacy-bindings <private-json>`（PowerShell `-GraftLegacyBindings`），由维护者从实际旧配置和保留证据核对后提供：

```json
{
  "schema_version": 1,
  "bindings": [
    {
      "root": "/absolute/selected-project",
      "python": "/absolute/old-runtime/python",
      "node": "/absolute/old-runtime/node",
      "cli": "/absolute/old-runtime/dist/cli.js",
      "launcher": "/absolute/old-onboard/scripts/sbtd_graft_entry.py"
    }
  ]
}
```

输入必须位于受保护私有目录且在部署写目标之外；闭集字段、重复 root、非绝对路径、非所选根均拒绝。计划保存输入快照，执行前漂移／缺失阻断零写入；逐资源仍核对配置前态并保留原件。该文件是本次操作者明确指定的旧运行时契约，不是从名字推测授权，也不修改历史 manifest。旧继承源不由另一 host 的安装器擅改，需在其真实归属配置域另行处理。

无 `--graft-retire-legacy` 的输入文件、project-only 全局退役、把本次退役选项混入已密封历史迁移部署均拒绝。源码没有自动销毁旧运行时或备份的入口。

## 6. Book Gate Plan 与 before-dev

| Gate | 客观触发 | 阶段 | 状态／证据 |
|---|---|---|---|
| DDD | 前序讨论已明确配置域／项目／连接边界；没有完整 grill，本轮无未决领域歧义 | 需求 | not-needed；术语见 §3 |
| DDIA | 全局持久配置、项目图、切换和恢复所有权 | 设计前 | confirmed：单文件候选、预期前态检查、原子资源提交及既有备份；跨资源失败如实部分完成，禁止覆盖漂移 |
| Legacy | 原固定项目连接语义与迁移历史有回归风险 | 代码前 | characterized：修改前原生候选复现追加 B 产生两个 cwd 绑定；空批次不渲染。既有配置／launcher／迁移 tests 为安全网 |
| Refactoring | strict 修改既有生产代码 | 代码前 | proceed：沿用 launcher、候选渲染与资源执行 seam，无前置结构重构 |
| Release | 安装／宿主启动／迁移行为变化 | 测试后 | ready，仅限源码／PR交付；最终验证与独立复核见 §7.3，不等于 live 切换或 v2 发布就绪 |

未完整调用 grill-with-docs：用户已确认具有实测依据的最终方案，无需重问已明确问题。LSP references 调用返回无可用 language server，因此本轮影响分析用实际源码、符号搜索和契约测试；未调用有未证明副作用的 Graft 查询。

TDD 公共 seam：用户确认的 MCP 进程启动、安装 CLI、TOML/JSON 配置候选、项目初始化和迁移资源输出。保留修改前失败原因，测试消费者可见隔离／边界／幂等／所有权行为，不新增源码文字断言。

## 7. 实施跟踪与验证证据

| 切片 | 交付 | 当前状态 |
|---|---|---|
| GM-A | cwd 根解析与会话固定、拒绝边界、launcher 回归 | 已实施；复核后加入实际 cwd 的 bare/admin 拒绝与可信 Git 探针 |
| GM-B | 单全局 Codex/OMP 候选、旧项所有权及回执验证 | 已实施；复核后收紧旧项闭集形状，项目继承不再代替全局覆盖 |
| GM-C | 全局安装／本地初始化分离、无项目支持及切换契约 | 已实施；完整安装写集避让批准文件、首写／逐资源复验，尊重 --no-mcp |
| GM-D | 真 Graft A/B、宿主验证、全套测试与独立复核 | 最终实现 head `d3a6b5813a85768ac470d0e8d76cc024f9bc9846` 本地完整1433项／10 skipped、三平台CI与独立复核通过；真实 Graft／Codex／OMP smoke通过，分平台范围见 §7.3；早期 Orca 入口证明和失败记录保留在 §7.1–7.2 |
| GM-E | README 两种入口、automation、CHANGELOG、主 PRD 同步 | 源码行为文档已更新；PR已合并，后续独立授权的本机规则／Skills及live automation prompt同步已完成；本次补齐台账，MCP绑定和环境退役仍归P3-05 |

修改前原生复现：两个项目候选追加后 server_count=2，均固定 cwd；期望一条通用定义的断言 exit 1。首次会话 Python 缺 tomlkit 属于环境失败，保留但不作为产品 red；随后复用既有依赖完整的验证解释器得到上述真实 red。

历史授权与恢复边界：实施阶段保留起始 dirty patch，不改真实生效 MCP 或删除历史环境。最初提交／推送／创建 PR 的授权不包含合并、发布或 live 切换；后续合并与 sync 的独立授权及实际结果见 §7.3，不改写当时边界。另获授权的 Orca 专用终端和隔离 HOME 仅查询合成图，完成后已关闭终端并移除本轮临时注册，项目文件保留。源码回退不能替代 HOME／ignored 数据恢复；live 退役继续遵守主 PRD P3-05/P3-04。

### 7.1 本地验证记录

以下为早期阶段的历史验证记录，不作为最终实现 head 的计数或合并状态；最终结果统一见 §7.3。

- `full-suite-02`：原生 `python -B -m unittest discover -s tests -p 'test_*.py'`，1425 tests，8 skipped，exit 0；首轮 1414 tests／8 skipped 记录仍保留，不冒充复核后结果。
- `review-fixes-focused-02`：批准完整写集／首写及构图期间漂移、MCP opt-out、OMP 生效域与闭集退役、launcher、候选渲染和隔离 92 项通过。此前 fixture 语法失败记录保留；修复的是测试括号，不是压低安全断言。
- `post-review-native/native-smoke`：真实 Graft 0.21.1；逐次 A/B/C 与批量同源项目的图 bytes、AGENTS bytes 和除实际生成时间外的 stamp 相等；新增 B 不改 A／全局定义；A/B 并发和子目录查询正确。同一 Codex app-server 两线程查询各自图。
- `omp-smoke-post-review-02`：两个原生 OMP 会话共享同一隔离全局配置，分别得到 `alpha_only`／`beta_only`；回环确定性模型只调度真实工具调用，不模拟 Graft，不声称真实模型推理。增强输出采集后的复跑 exit 0，约 1.08s。前次 150s 超时发生在全量测试重叠期间，控制器 0 请求且初版驱动未保全 TimeoutExpired 的子进程输出；重叠负载是可能因素，尚未证明确切根因，不能写成产品缺陷已修复。
- `orca-host-entry-01`：经追加授权，用一个本轮专用 Orca 终端、隔离 HOME，runner 不改 cwd、不传 thread cwd；Codex 与 OMP 均从继承目录查询真实图成功。shell wait 的 `stop_unverified` 不作为成功退出证据；随后关闭返回 `ptyKilled=true`，本轮注册已 metadata-only 移除，合成项目文件仍存在。
- 代码复审：原 4 项问题均关闭；安全复审：原 5 项问题均关闭，重复问题合并修正。Ponytail 无可安全删除的生产抽象；保留现有候选、资源和隔离边界。Code Readability 已核对手写代码／测试；未改 vendor/generated。
- 静态验证：Bash 语法与 PowerShell 原生 parser 通过；新增／改造模块的 ruff 检查和 onboard 既有诊断分别记录；onboard 的 ty 基线及当前均为 92 项既有诊断，不把已有错误标为通过。
- 报告位置为本轮私有 `sbtd-global-session-mcp-*` 证据目录，保留 raw／同 stem 中文汇总与失败记录；提交前证据均为 developer-local / dirty / local-only。远程 CI 只能以随后创建的 PR 精确 head 为准。

### 7.2 精确提交 CI 与 Windows 测试辅助修正

[PR #108](https://github.com/KunoLu/640-skills/pull/108) 的首个 head `6373f9cf4a7a4e6c78edb4179455cf58ecd0cce3`，Windows job `110949024431`（run `37040462165`）在 `SessionRootResolutionTests` 报 7 个错误：全部来自测试 `read_reply` 对匿名管道调用 `select.select`，原生日志为 `WinError 10038`（not a socket）。安装器／工作流 50 项与 pwsh 15 项此前通过。这个失败不证明 Git 路径解析有误，不能据此放宽生产路径安全守卫。

测试 helper 改为带超时的后台 `readline`，保留全部协议与拒绝断言；本地完整 launcher 43 项及 ruff 通过。生产模块不因该测试平台问题改变。每个新 head 必须重新取得 Linux／macOS／Windows 结果，旧 head 的绿色或失败记录只作为历史证据保留。当时 PR 尚未合并，主 PRD P1-25 因而保持 checking；后续已合并并补记 done，见 §7.3。

后续诊断 head `24d715357b074568ae6ba01aa4b18530637bbd65` 的 Windows stderr 进一步确认普通图被 `tree-unsafe` 硬链接分支误拒绝。Python 3.12 的 [DirEntry.stat 契约](https://docs.python.org/3.12/library/os.html#os.DirEntry.stat) 明确 Windows `st_nlink=0`；生产守卫仅改为 `os.stat(entry.path, follow_symlinks=False)` 获取真实值，仍要求单链接并拒绝 symlink/reparse/special。新增真实硬链接启动拒绝场景，本地 launcher 44 项和 ruff 通过，独立代码／安全窄复审再次 GO。

同一 head 的 macOS job 曾在嵌套根拒绝场景发生整树 checksum 漂移，旧日志没有逐文件差异，不能指认某个具体文件。隔离 fixture 的 Git trace 证明 commit 会启动 `maintenance run --auto --detach`；仅在测试 fixture 命令设置 `maintenance.auto=false`，排除独立后台 writer，保持原完整无写入断言，生产安装器逻辑不变。后续以新 head 原生 CI 验收。

OMP 超时补充取证：带启动期 stderr 的复现明确停在 `readPipedInput`，等待继承 stdin 的 EOF，尚未进入 MCP。仓外驱动已通过 argv 提供完整 prompt，却继承持久工具 stdin；改为 `stdin=DEVNULL` 后同一共享隔离 HOME 的并发 A/B 查询约 1.1s 通过。负载重叠不再作为根因结论；这次只修正验证驱动，没有为超时修改产品源码。全部失败、采样和复跑输出保留。

### 7.3 最终验收、合并与独立同步

| 事项 | 已核验事实 | 边界 |
|---|---|---|
| 最终实现验收 | head `d3a6b5813a85768ac470d0e8d76cc024f9bc9846`；[CI run 37094601001](https://github.com/KunoLu/640-skills/actions/runs/37094601001) 三平台全部 success；本地完整1433项／10 skipped，聚焦53项／2 skipped，ruff及两路独立复核通过 | 这些结果绑定实现 head，不冒充后续文档提交的重新运行 |
| 原生平台结果 | Linux全量1433项／15 skipped；macOS268项／2 skipped；Windows安装器／契约49、pwsh15、MCP边界22（1项POSIX专属skip）、junction1、ACL1全部通过 | Unicode仓库用例在Windows `utf8_mode=0`、`cp1252` 下由red转green，未跳过；真实Git／launcher使用下游协议fixture，不冒充Windows真实Graft全栈；macOS真实Graft／Codex／OMP smoke另行通过 |
| 合并与分支清理 | 用户另行授权管理员合并；PR #108 的 `mergedAt=2026-10-03T04:38:30Z`，merge `a2d0971c8fb10f91f4fb8c11be2d4432884762bf`；合并树与验证head一致，确认MERGED后删除本地及远程开发分支 | 未修改分支保护规则；不是tag发布或live接线切换 |
| 独立sync | 用户显式输入sync；于 `2026-10-03T13:33:52.449160+08:00` 完成记录。16个目标与源一致：更新两份全局AGENTS及完整Onboard，其余13个bundled Skill已一致；5个required external Skills经stable安装器重装并校验 | 旧Onboard及六个legacy external目录原已不存在，完整迁移命令返回无需迁移；备份保留，不等于环境退役 |
| live automation | 完整prompt已按仓库版本同步并读回一致；enabled仍为false，计划、时区、工作区模式／路径和其他配置不变 | 未启用或运行automation；未改MCP绑定 |
| 该次sync时尚未执行（历史快照） | 在 `2026-10-03T13:33:52.449160+08:00` 该次sync完成时，OMP和Orca Codex旧固定根仍引用TEMP运行时，未执行新的live全局替代 | 不作为当前现场结论；后续独立授权的准备见§10，已执行接线及2026-10-05补记见§11。环境退役仍按主PRD §11.9独立确认，备份销毁归P3-04 |

P1-25在主PRD的状态补记为done，仅关闭源码／验收／合并交付；该表完成时间记录本次台账补记时刻，不回填成先前实现、合并或sync时刻。旧失败、原生报告与同步备份均保留在既有私有证据目录；本节不发布真实HOME配置、账户标识或敏感原件。附带sync检查未识别可用Java，Maestro CLI未检查，不据此宣称完整本机工具栈就绪。

## 8. PR #108 审查修正

用户要求修复独立审查最终保留的五项问题，并在该阶段追加明确确认 R6（`--yes` 省略项目参数时 global-only），共六项。基线为 `a9305c57c5ac04b592a7d74194ff69ea1bfb344b`，沿用原分支与 strict，旧完成事件及旧 CI 证据保留。该修正阶段的授权不包含合并、live HOME/MCP、sync、环境或备份删除；后续独立授权及执行事实见 §7.3。

| ID | 问题与 Given / When / Then | 修正及回归边界 |
|---|---|---|
| R1 | Given Windows PATH 优先目录含 git.cmd/git.bat；When 启动 MCP 根证明；Then 不执行批处理，存在外部原生 Git 时可继续，否则安全拒绝 | 只选择明确目录中的 git.exe；原生 Windows marker 回归，保留 PATH／物理包含守卫 |
| R2 | Given 受管 OMP 全局记录的 launcher 或 cli 被改为相对路径；When 校验 ownership/state；Then 返回 state-conflict 且不改变配置 | 全局记录两处路径均须绝对；同一 ownership 入口的历史 reader 保持相同约束，合法历史格式和退役识别不变；分别覆盖 launcher／cli 篡改和合法记录正向控制 |
| R3 | Given Windows 项目 cwd 内有 git.exe，外部 PATH 也有真实 Git；When 启动 MCP；Then 忽略项目内文件，使用外部 Git，不误报缺失 | 使用完全限定的外部可执行文件候选，避免 which 隐式搜索 cwd；原生 Windows 正向启动回归 |
| R4 | Given 用户按文档执行旧绑定切换；When 从 plan 转入 init；Then 两个命令显式保留同一平台、根、退役授权及适用的旧运行时契约 | README.md／README.html 给出成对完整命令；不暗示 plan 参数会跨进程继承 |
| R5 | Given 版本自动化检查当前部署；When 评估 MCP；Then 仅要求每个有效 host 配置域一条全局定义，同时逐项目检查图 | 删除当前规则中的逐仓 MCP 判据；历史 PRD／回执不做全局词语替换 |
| R6 | Given 普通根安装器带 --yes／-Yes 且没有项目参数；When 从项目 cwd 执行 init／reset；Then 只安装全局范围，不自动选择 cwd，不安装项目资产 | Bash／PowerShell 保持空项目集合；显式 roots 和 project-only 不变，不带自动确认仍保留交互选择；原生解释器回归 |

该阶段 Book Gate：DDD not-needed（无新领域歧义、未完整 grill，R6 默认行为由用户明确选择）；DDIA confirmed（配置证明及安装范围收紧，读写所有权和回滚规则不变）；Legacy characterized（OMP 当前／历史 reader 的相对路径消费者红测、Bash／PowerShell 省略 roots 的原生 red，以及 Windows 机制证据／原生回归）；Refactoring proceed（原有函数内的最小修正，不增加调度器、缓存或平台模拟层）；Release Readiness 复核已完成，后续 Unicode 修复的最终实现 head 验收见 §7.3，未继承旧 head 的通过结论。

验证使用现有 Python／原生 CLI／三平台 CI。Windows 专属场景必须在 Windows runner 执行，不能把本机平台 skip 当通过；文案通过命令参数和行为核对，不新增源码措辞断言。本轮进度与最终证据记录在本地唯一 task 和 PR #108，不预写未执行结果。

## 9. Windows Unicode 仓库路径修正

用户在 `11b0a7130526097869889ccda5982eb998feb471` 的审查后确认修复 Git 根证明的编码问题。该修正阶段沿用 strict、原分支与 PR #108，不自动合并、不执行 live 切换；后续独立合并与sync事实见 §7.3。用户没有本地 Windows，原生证明使用既有 Windows GitHub Actions，不能以 macOS 通过或 Windows skip 代替。

| 场景 | Given / When / Then | 自动化边界 |
|---|---|---|
| Unicode 仓库不受 Windows 默认代码页影响 | Given 合法 Git 仓库路径含中文或 é，Windows Python 关闭 UTF-8 模式且默认解码非 UTF-8；When 从该仓库启动 MCP；Then 完成初始化并仍绑定真实仓库，不误报 root-unsafe | 真实 Git／真实 launcher／既有协议 fixture；测试明确核对解释器编码前置条件，先取得 Windows red，再验证 green |
| 不可解码的 Git 证明安全拒绝 | Given Git 探针返回无法解码的输出；When 启动 MCP；Then 返回受控 root-unsafe，不启动下游、不输出 traceback，也不修改项目或创建遗留临时 HOME | CLI 错误边界回归，不放宽路径相等、最近仓边界或原生 Git 选择规则 |

Book Gate：DDD not-needed（无领域歧义，未完整 grill）；DDIA not-needed（不改图、stamp、配置或回执格式）；Legacy characterized（原生 Windows 已确认 cp1252／UTF-8 模式关闭时合法仓库被拒绝，POSIX 畸形输出已确认抛出未捕获解码异常）；Refactoring proceed（仅调整探针解码与错误边界，无新抽象）；Release Readiness ready，仅限源码／PR交付，真实场景、聚焦／三平台检查及独立复核均已完成，见 §7.3。既有 POSIX 解码约定未变，未以全局编码改写扩大修复范围；不把合并或sync作为live切换及环境退役证明。

## 10. P3-05 第一阶段准备与 Codex 分散表兼容

用户随后批准按推荐顺序执行第一阶段：备份并清除已证实失效的项目任务指针；通过独立代码流程修复 Codex TOML 兼容并更新已验证 Onboard；准备专用 Python／Graft；重新生成只读切换计划。两份 live MCP 配置、项目 AGENTS／图／ignore、现有会话及旧运行环境不在本阶段的修改／停止／删除范围内，第二阶段仍需用户确认最终清单。精确路径、前态和原件仅进入私有准备记录。

| 场景 | Given / When / Then | 保留边界 |
|---|---|---|
| 分散的合法 MCP 表可生成切换候选 | Given MCP 表和受管 server 的子表分散在合法 TOML 的其他表之间；When 显式授权退役已证明归属的旧绑定；Then 仅将该旧绑定替换为一个通用定义，保留其他 server、模型／功能设置及注释，重复调用不再改变候选 | 公共 `codex_mcp_candidate` seam；合成配置与真实配置的只读内存渲染，不写 live |
| 布局支持不扩大所有权 | Given 相同布局但未授权、所选根／旧运行时不匹配、受管项被用户扩展或顶层为受拒绝的 inline table；When 构造候选；Then 仍按原契约拒绝，不靠容器类型放宽退役范围 | 不新增 alias、旁路 writer 或整体配置重写 |

DDIA confirmed：候选生成仍为单份输入到候选字节的纯转换，跨宿主切换不宣称原子事务，正式执行前重新核对快照；Legacy characterized：实际 Orca 只读预览与合成公共接口回归都在同一 `invalid-config` 容器门失败；Refactoring proceed：仅补齐合法 TOML 表类型，无新架构。未完整调用 grill-with-docs：技术原因与阶段授权已明确。此节不预写尚未完成的代码、安装或 live 验收结果。

依赖边界：tomlkit最低支持版本为0.13.2；上游修复了旧版本删除分散表时遗留片段的问题。原生隔离依赖验证已观察到0.13.0残留旧条目、0.13.2正确删除。候选生成还会复核序列化结果，若仍含受管旧条目则拒绝返回，不能把半切换交给执行器；安装副本须按更新后的requirements准备依赖。

## 11. 本机后续切换与对齐事实

2026-10-05按用户确认的四项范围执行，并核对本地P3-05任务记录与私有原生报告，补齐主PRD遗漏的现场事实；不改写§7.3和§10当时的授权边界。

| 阶段 | 已核验事实 | 验收与保留边界 |
|---|---|---|
| 2026-10-03后续第二阶段 | 用户展示完整写集后另行确认；Codex先部署，OMP按新前态重新plan后部署，全局通用MCP及demo图／stamp等所选资源成功，新连接从demo根／子目录握手、列工具与freshness通过 | 私有 `second-stage-final.json`／同stem中文汇总及原件映射保留；不等于既有会话重载 |
| 2026-10-03本机2.0对齐 | `alignment-summary` 记录完成于 `2026-10-03T21:32:28.043131+08:00`；共享／Orca安装副本与规则对齐、普通Codex窄接线、获批旧入口处理及PATH对齐完成，普通／Orca Codex和OMP独立新宿主通过 | 历史处理仅按当次授权记实；不是本轮新增清理授权，不据此删除旧运行时或备份 |
| 2026-10-05增量同步 | 以源 `61e89ebdd2721360f78f67b2ec3867da8c79a1b8` 更新共享和已知Orca Onboard（各6项内容变化、6项新增），其余15个同步目标原已一致；required五项经已同步stable安装器处理，legacy迁移为skipped／零删除；automation完整prompt已同步，除prompt和更新时间外全部字段保持 | 28项独立原件校验保全；不修改ENTRYPOINT版本、不归档UPDATE、不升级上游pin |
| 当前仓库Graft启动修整 | 原配置与运行时身份正确，但本仓无图，启动前返回 `graph-missing`／exit 2；经独立确认仅调用受控建图，生成0.21.1结构图与stamp，项目AGENTS／ignore不变；两Codex的Playwright仅补 `-y`，其余配置字节保留 | 不运行完整项目init/reset、不处理其他项目、不启用deep／LLM／cloud；freshness的概念图缺失提示与结构图 `graph check: OK` 分开解释 |
| 当前验收 | 三域磁盘／运行时及真实宿主隔离投影通过；普通／Orca Codex使用各自原配置启动新app-server，OMP使用原MCP配置启动临时RPC，均加载0.21.1六工具并正常退出；根／子目录真实结构查询及HOME／未初始化仓拒绝通过；Chrome DevTools、Playwright、Maestro、Context7握手／工具列表通过 | OMP只用临时 `tools.xdev=false` 展开注册表，未改变MCP来源或持久设置；无模型请求。最初OMP探针误用未规范化前缀导致失败，修正探针后定点及三宿主最终完整复验通过，失败证据保留；没有网页／移动业务E2E或既有GUI会话重载证明 |

本轮证据保存于私有批次 `20261005-220758-pc-v2-alignment-px_0n22q`，原始JSON和同stem中文汇总分别覆盖同步、建图、配置保全、协议、原配置域新宿主及恢复映射。主PRD §14.6仍是总进度事实源；P3-05保持in-progress，旧环境和全部备份保留，既有连接及退役／保留交接尚未收口，不声明v2发布就绪。本轮只修改现场与进度文档，未提交、推送或发布。

### 11.1 P3-05 精准清理与保留交接完成

2026-10-13用户明确批准“五项删除并接受保留交接”。P3-01隔离tiktoken环境、编码表/uv缓存和两个AC22合成现场已精准删除；原生报告、版本/输入指纹、失败及最终任务副本保留，95份相关证据字节不变。三个所选host域现行Graft均绑定稳定runtime，当前可见launcher/Graft对无旧TEMP引用；五份已核对配置未变，无MCP/shell/认证改写，无模型请求。

清理后已有omp toks复算1921/3010/1883一致；稳定Graft0.21.1真实MCP握手、六工具列表及正常退出通过。沿用既有新宿主验收，不把直接协议smoke当作全GUI重载。旧Python/Graft/launcher、隔离项目/HOME及原始材料共37个历史TEMP根原位保留（五个删除子目录除外），三个cutover批次原件/回执不动；原基线113份备份复核全部匹配。已知Chrome/Crashpad及其resume-logs工作目录保留，不误当测试进程停止。

用户接受逐路径保管与P3-04交接，下一人工复核为2026-10-27或P3-03前，取先到者；未来销毁仍需独立确认。私有`20261013-230941-p305-retirement`保存完整原生证据和中文汇总，TaskStore实际完成时间`2026-10-13T23:47:45.066884+08:00`。本次P3-05 done不等于P3-04 done或v2发布，不触发sync、commit/push、tag或备份销毁。

最终记录核对另发现一份.DS_Store在即刻95份保全检查之后变化，写入者未证实，当前文件保留；其余94份文件及排除平台元数据后的93份实际证据SHA均未变。私有失败记录保留，不把平台元数据变化宣称为原生证据损坏，也不隐藏该检查失败。

### 11.2 v2.0.0正式源码发布

2026-10-14T11:30:23+08:00正式GitHub Release发布，annotated tag指向`8f6c46993e7546b68f949bd52ede806d9b1afa61`，实际main CI38500935539三平台九job通过。根双语README提供v2初始化、v1迁移及init/reset/upgrade分阶段提示词，英文`CHANGELOG.md`与中文`CHANGELOG.zh.md`逐项对应。该源码发布不执行本机sync、用户项目迁移、凭据变更或旧备份销毁；P3-04继续持有独立处置责任。
