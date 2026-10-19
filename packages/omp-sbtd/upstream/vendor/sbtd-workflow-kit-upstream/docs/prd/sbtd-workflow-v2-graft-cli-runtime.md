# P1-03：Graft CLI 检测、安装与离线边界

> 台账路径迁移：本文所述 `findings.log` 已完整归档至 [SBTD v2 findings](../archive/sbtd-workflow-v2-findings.md)。下文保留当时的状态与证据，当前处置以归档表为准。

## 范围与事实源

- 实时任务状态以主 PRD 为准；基线 `dc5fe800e573232237ddd1e3e923bb327972e755`，分支 `p1-03-graft-cli-runtime`。
- 交付 CLI 检测、显式确认安装、遥测保护、精确版本约束，以及 AC-10 剩余禁网证明。不交付 graph build、host/MCP 接线、旧数据迁移/清理或完整 v2 发布。
- 审查按 D-IMP-13：有效 P0/P1 阻断；P2/P3 原级别记录到 `findings.log` 留待评估。
- 精确候选为 `@nanonets/graft@0.18.0`；registry gitHead `de8456e892bad5aeee11403e47fb2227773eb27e`，Node `>=20`，tarball integrity `sha512-sNshNND1Q/qSXiuSh9nW8NniWyaD+m55oJZ6oCGJsLzxot52WSJrdThsQ3NZVTNT+lqivlYkkqN8b/nf22S/Xw==`。不自动换 latest；版本变化需重新证明能力。
- [固定 npm metadata](https://registry.npmjs.org/@nanonets%2Fgraft/0.18.0) 与实际发布包是版本事实源。Context7/main 文档仅作导航，不覆盖固定版本结论。

## 已建立的运行证据

- 既有 Agent/tool suite：5 tests / 4.434s / exit 0，报告 `tests/unit/reports/unit-report-tool-detection-baseline-p1-03-graft-cli-runtime-2026_09_18-19_51_47.json`。
- 已下载固定 tarball 并核验 integrity；保留 P0 安装内 576 个发布文件逐字节一致。安装 manifest 本身没有 gitHead，不伪称从安装文件验证了 gitHead。
- 原生固定版本调查：本地 `--version`、dotenv 屏蔽、registry 在线 HTTP 200、sandbox 内同 URL 网络失败、禁网本地版本可用、独立空 npm cache 的 `version` 输出 `latest: unreachable (offline?)` 全部通过；HOME/项目字节及 mtime 快照不变。
- 报告：`tests/api/reports/api-report-graft-pinned-probe-p1-03-graft-cli-runtime-2026_09_18-19_57_21.json`，中文同 stem 汇总与 envelope 已验证。
- P0 旧脚本共享 npm cache 且设置 offline=true；不能只凭其 latest 输出判断当时网络来源。本轮不倒推旧结果，而用真实网络正反控制和逐 case 空 cache 独立证明。
- 所有运行均为私有 HOME/cwd/cache；未修改保留 P0 安装、真实 HOME 或系统代理。当前仅调查通过，尚未交付新生产 handler。

## 实施契约
- 另对既有完整 `check --json` 做真实隔离HOME刻画：退出0但创建 `Library/Application Support/rtk/history.db`。这不是只读验收通过；已定位到RTK gain，改在私有probe HOME/cwd验证并明确scope，不检测/修改用户实际历史库。生产集成后重跑全HOME/项目快照。

### 检测

1. 只读检测 executable/package identity、固定版本与 Node 兼容性；固定版本 CLI 使用 `--version` 验证 native 启动，不调用 `version`、init、build、telemetry mutation 或 upkeep。
2. 检测与 npm 是否存在解耦：已安装本地能力不能因 npm/latest 不可达被错误判为不可用。check/plan 不为缺失工具自动安装或升级。
3. `check`/`plan` 输出 `graft` 状态，明确包存在、可运行、受支持及阻断原因；不将这些状态提升为图或 host 可用。检测到未知/冲突 executable 身份时不覆盖。
4. 安全子进程环境固定 `DO_NOT_TRACK=1`、dotenv 空输入，并排除会启用 LLM/cloud 的相关继承变量与 Node preload。此保护只作用于受管子进程，不改用户全局环境；不提供任意 Graft 命令代理。

### 安装

1. 新增真实 `install-graft` 入口，沿用 `--yes`/`--json` 确认与单 JSON 约定。没有确认只返回安装计划/needs-confirmation，不写入。
2. 安装目标为冻结包，不自动 latest；验证下载完整性及实际安装版本/CLI。缺 Node/npm、native 失败、版本冲突或配置写入失败均报告真实阶段，不循环安装。
3. npm 生命周期设置 DNT，并使用非交互 CI 环境避开固定版本 postinstall 的后台 flush/update 路径；native lifecycle scripts 仍需按 npm 版本明确允许并实测。
4. telemetry disable 仅在授权的全局安装/管理动作后持久化。避免调用会触发 upkeep 的 telemetry CLI；对已确认目标 JSON 做类型/containment 检查、保留未知字段、原子替换及回读 `enabled=false`。遇到用户数据冲突不猜测、不删除或覆盖异常对象。
5. 已装可用版本、缺失、损坏、拒绝确认和部分失败分别报告。不要把 npm exit 0、目录存在或 fail-soft 上游返回当作成功证明。
6. 不新增离线镜像或 fork；离线没有完整适配产物时明确安装未完成，不能拿一个顶层 tarball 冒充完整依赖集合。

### 直接消费者与职责

- Python 保持唯一 Graft 安装实现；Bash/PowerShell 展示计划、取得确认并调用，不再自行安装 GitNexus，也不各写一套 Graft 处置逻辑。
- 移除被替代的 GitNexus inventory/manual-MCP/menu 消费者，保留其他 MCP 能力。尚未完成的 Graft host/MCP 接线不注册占位菜单或假可用配置；其后续生产者按 D-IMP-12 原子激活。
- 不删除已有用户 GitNexus MCP/图/目录；受管退役仍归 P1-13。project-only 不安装全局 Graft、写 telemetry HOME 或进行 host 接线。
- 普通任务可降级，但显式请求的安装失败必须非零且如实报告；installer 成功与普通任务可安全继续不是同一个状态。

## 开发门禁

- `grill-with-docs`：未完整调用；PRD、固定包与代码提供了所需产品/技术边界。
- DDD：confirmed。区分存在/可运行/受支持/安装完成/图与host可用；安装与普通任务交付正交。
- Legacy：characterized。既有5项基线与固定包6项真实调查构成移前证据；不以fixture冒充真实Graft。
- Refactoring：proceed。内聚 Graft 模块加现有编排/direct callers，不新增通用provider框架。
- DDIA：confirmed。只读无状态写入、显式安装授权、受管子进程环境、telemetry JSON保全与回读、失败不自动卸载。
- Release readiness：ready（仅 P1-03）。2026-09-18 在最终精确提交的全量、真实CLI/安装副本及报告验证后通过；Windows、host和完整v2发布门禁不提前验收。

## 验证要求

- 无工具、坏身份/版本、缺Node/npm/native、拒绝确认、成功、重复安装、配置冲突、持久化失败与单JSON退出。
- check/plan 的 HOME/项目 byte+mtime 零变化；CI不得成为DNT测试通过的唯一原因。
- 真实固定包安装到私有 npm prefix，验证native启动、实际版本、telemetry持久状态和所有副作用目录；不触碰真实全局环境。
- 固定版本禁网 `--version` 可用、`version`/npm metadata 不可达且不触发循环安装；缓存和网络分别说明。
- 两个安装器 normal/project-only、确认/拒绝、前置屏障及其他工具回归；真实 Bash 3.2/macOS PowerShell 与未来 Windows 证据分开。
- 最终报告、精确 SHA、独立 P0/P1 审查、PR/admin merge、分支清理及独立完成状态 PR，沿用主计划顺序。

## 首轮实现与独立审查

- 原生全量 632 tests / 116.183s 通过；报告 `tests/unit/reports/unit-report-onboard-integration-p1-03-graft-cli-runtime-2026_09_18-21_01_35.json`。早期缺导入、下载 fixture、交互输入失败均保留原始报告，不覆盖历史。
- 真实固定 tarball 安装到私有 npm prefix，native 启动、telemetry `enabled=false`、重复安装及完整 check 的 HOME/项目/prefix 快照通过；独立 DNT 控制明确没有 CI，正向确认同包无 DNT 时允许记录，再证明 DNT 下无事件/状态写入。报告 `tests/api/reports/api-report-graft-real-install-p1-03-graft-cli-runtime-2026_09_18-21_01_35.json`。
- 独立审查发现两项 P1：shim 文本不能证明执行目标身份；optional Graft 不应进入强制缺失工具或原始 npm 安装建议。均先建立红测后修复；44 项 runtime/消费者影响范围通过，仍须最终精确提交全量及实际 CLI 重跑。
- executable 身份现在必须解析到受支持包的精确 `dist/cli.js`，安装后验证复用同一绑定。未验证的 Windows shim 安全返回 blocked，不将 macOS PowerShell 结果冒称 Windows 支持；Windows 适配/真实执行仍由 P1-08 完成。
- 保留 `tools[name=graft]` 与根 `graft` 状态投影，标记 `optional=true`；required missing/install report 排除 optional，human check 独立显示原状态、原因和下一步。唯一安装建议为受管 `install-graft`，不向用户绕过 SRI/DNT/native/telemetry 安全门推荐原始 npm 命令。
- P2/P3 按 D-IMP-13 记录到根 `findings.log` 延期，不因当前修改邻接而追加处理。此节是 dirty/local-only 中间证据，不是 PR head、Windows、host 或完整 v2 验收。

## 可读性与审查收口

- Code Readability Review：覆盖本轮手写模块、编排、两个installer和测试；未发现需要扩大结构重构的问题。安装状态、实际失败阶段与副作用边界保持显式，不压成密集表达式。
- Ponytail Review：未引入provider框架或通用调度器；保留单一安装实现、真实telemetry读写接缝和现有调用方。无需要额外删除/合并的有效发现，冲突裁决 none。
- 独立审查：`P103RuntimeReviewOne` 与 `P103IntegrationReviewOne` 均确认无剩余P0/P1。`findings.log` 本任务2 fixed P1、7 deferred P2、1随P1同根关闭的fixed P2；不是零问题声明。
- 修复后全量报告：`tests/unit/reports/unit-report-graft-reviewed-full-p1-03-graft-cli-runtime-2026_09_18-21_18_25.json`，636 tests / 374.554s / exit 0，无skip。新模块/测试Ruff与ty通过，已有范围按base对比而非声称全仓静态全绿。
- 文档入口维护：README.md/html、Onboard SKILL/REFERENCE、两张安装图及versioned automation prompt均已按本轮Graft边界更新；CHANGELOG新增能力及RTK只读修复。历史deferred文案保持原状，live automation、ENTRYPOINT版本与真实本地配置均未操作。

## 最终精确证据与实际合并

- 最终实现提交：`01e27cfc75b1c302dbff04b17388a8dff4b185fb`。原生636 tests / 639.290s / exit 0，无skip；新模块/测试Ruff、format、ty和Bash语法通过，已有修改范围Ruff30→29、ty96→93，无新增诊断。不是全仓静态零诊断声明。
- 最终报告：`tests/unit/reports/unit-report-graft-exact-full-p1-03-graft-cli-runtime-2026_09_18-21_31_36.json`；`tests/api/reports/api-report-graft-exact-install-p1-03-graft-cli-runtime-2026_09_18-21_27_40.json`；`tests/api/reports/api-report-graft-exact-offline-p1-03-graft-cli-runtime-2026_09_18-21_30_16.json`。同stem中文MD与envelope齐备，本轮16份envelope全部通过；raw保留实际临时driver源码，删除runner后仍可追溯。
- git archive的完整305文件Skill包含新模块，执行前后逐文件SHA256一致；五项真实安装/幂等/check/DNT与五项plan/禁网/缺包失败场景全部通过。证据为developer-local / exact / local-only，未发布到CI或知识服务器。
- Release Readiness Review：ready，仅本任务；探针/下载/安装有时限，失败阶段与partial状态可见，不自动卸载；7项P2按用户D-IMP-13授权延期。回滚源码不等于授权删除真实安装或用户数据，真实环境动作继续独立确认。
- [PR #31](https://github.com/KunoLu/640-skills/pull/31) 于2026-09-18T21:44:12+08:00实际合并，merge `908a8a65952ee82ce0381a5955000c3b26daab15`。main与origin/main同步，合并tree与验证候选一致，本地/远端任务分支已删除并prune。
- 2026-09-18T21:45:28+08:00完成私有临时清理：12份源码快照先按manifest/base哈希核验；仅删除Main拥有的P1-03临时runner/包/prefix/HOME/cache/私有PowerShell。48份报告保留，最终unit raw/envelope另记清理事实；保留P0安装、真实HOME、用户数据及真实迁移备份未触碰。此后的完成状态记录通过独立status PR审查/合入，闭环前不启动下一任务。
- 独立status review无P0/P1；另提出1项metadata复核措辞P2，已按原级记录为`P1-03-R2-P2-001`，未为低级文案扩大修改。实现阶段7项与状态阶段1项合计8项deferred P2；前述7项是实现PR的历史快照，不重写为当时尚未出现的发现数。
