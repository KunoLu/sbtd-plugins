<div align="center">

# SBTD Workflow

**面向循证开发的 Agent 规则、Skills 与环境初始化工具。**

[![内置技能](https://img.shields.io/badge/bundled_skills-14-7c3aed?style=flat-square)](#skills) [![外部技能](https://img.shields.io/badge/external_skills-19-0d9488?style=flat-square)](#external-skills) [![许可证](https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square)](LICENSE)

[English](README.md) · **简体中文**

[安装](#install) · [使用与提示词](#usage) · [工作流](#workflow) · [技能目录](#skills) · [详细参考](#reference)

</div>

SBTD 将**规格、行为、测试与领域语言**连接起来。Coding Agent 负责执行，工作流负责把范围、授权和验证说清楚。

本仓库是**配置与 Skill 的摘录／同步源**，不是真实业务应用。工作流主线面向 **Codex 与 Oh My Pi（OMP）**；安装器也提供 Claude Code、Kimi 适配入口。有适配入口，不等于各宿主行为已取得同等验证。

> **正式版 [v2.0.1](https://github.com/KunoLu/640-skills/releases/tag/v2.0.1) 已发布。** 当前 catalog 包含 14 个 bundled Skills 和 19 个 required external Skills。[中文变更日志](CHANGELOG.zh.md)与[英文对应版](CHANGELOG.md)记录相同发布历史。代码、CI、安装、原生检查与真实宿主验收仍是不同证据层级；发布 tag 不会升级你的环境。详见[交付计划与验收边界](docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md)。

| [首次安装](#install) | [已经安装](#onboard-prompts) | [开始任务](#task-prompts) |
|---|---|---|
| 先安装 Onboard，再审阅初始化范围 | 检查、升级或追加项目 | 选择执行模式，复制任务提示词 |

<a id="install"></a>
## 安装：先让 Agent 帮你处理

### 1. 只安装 Onboard Skill

将下面的提示词交给 Coding Agent；需要时替换目标 Agent：

```text
请从 KunoLu/640-skills 的 v2.0.1 tag 只安装 sbtd-workflow-onboard，
目标是 Codex 用户级全局 Skills 目录，不是当前项目。
先解析并确认该 revision 存在；不得静默替换为 main 或 v1 包。
使用官方 skills CLI 复制整个目录，报告实际来源与目标路径。
暂不执行 init/reset、不安装其他工具，也不修改 AGENTS/MCP 配置。
```

偏好终端操作？在已有 Node/npm 的环境中，使用[官方 Skills CLI](https://github.com/vercel-labs/skills)：

```bash
npx --yes skills@latest add https://github.com/KunoLu/640-skills \
  --skill sbtd-workflow-onboard --global --agent codex --yes --copy
npx skills list --global --agent codex
```

`skills@latest` 选择的是 CLI 版本，**不是 Skill 发布版本**。未固定 ref 的仓库源读取默认分支，而非最新 tag。固定来源的语法为 `'KunoLu/640-skills#<reviewed-ref>@sbtd-workflow-onboard'`：将 `<reviewed-ref>` 替换为已存在的 v2 tag 或已审阅 commit，并遵循该 revision 的文档。**不要将历史 v1 包与下文 v2 初始化提示词混用**：旧版初始化可能安装或调用已退役的 Trellis／GitNexus 工作流。已有 v1 数据应使用下方迁移提示词，不用 init/reset 代替。

**安装入口 Skill 不等于完成初始化。** 这一步只复制自包含的 Onboard 包，不运行 `onboard.py`、不安装其他 Skills 或 Python 依赖、不配置 MCP，也不初始化项目。应定位实际安装目录，不猜测 HOME 下的路径。为 OMP 或其他宿主安装时，先确认 Skills CLI 支持的 Agent 标识和发现路径，不要假设它与 Onboard 的 platform 名称相同。

### 2. 审阅计划，再初始化明确选择的项目

```text
请使用 sbtd-workflow-onboard 初始化 /abs/project-one,/abs/project-two。
目标平台是 codex；这些是我明确要初始化、且已存在的项目绝对路径，
两个项目都安装项目级 AGENTS.md。先检查已安装包所需的 Python 依赖，
输出 plan --json，列出全局 Skills、全局 AGENTS、宿主和 MCP 的实际目标。
安装缺失前置条件或应用计划前先询问。经我批准后执行 init，
逐项目报告实际写入、备份、跳过的检查与剩余操作。
```

OMP 初始化将 `codex` 改为 `omp`。多个项目路径用英语逗号分隔。正常初始化会把 **14 个 bundled + 19 个 required external Skills 安装到全局目录**；可选工具仍遵守各自的确认门。

Onboard 的契约、状态与迁移校验需要 **Python 3.10+** 和声明依赖。审阅并授权依赖安装后，使用实际执行已安装副本的解释器运行：

```bash
python -m pip install -r /path/to/installed/sbtd-workflow-onboard/requirements.txt
```

> **先看清写入范围。** 正常 `init`/`reset` 默认写入 Codex 全局规则；若 `~/.omp` 已存在，还会备份并覆盖 `~/.omp/agent/AGENTS.md`。选择 platform 不等于选择全局 AGENTS 目标；`--global-agents-path` 只改变 Codex 目标。不希望全局写入时，使用 project-only 模式。

[Bootstrap 说明](sbtd-workflow-onboard/REFERENCE.md#official-skills-cli-bootstrap) · [初始化契约](sbtd-workflow-onboard/REFERENCE.md#two-execution-modes) · [路径解析](sbtd-workflow-onboard/REFERENCE.md#paths)

<a id="usage"></a>
## 使用说明：按目标复制提示词

以下是**发给 Agent 的自然语言请求**，不是新增的 CLI 命令。请替换方括号内容与 `/abs/...` 路径。Agent 应先读取本地事实，只询问缺失的选择或必要授权。

<a id="onboard-prompts"></a>
### 管理安装环境

| 目标 | 选择 | 含义 |
|---|---|---|
| 检查而不安装 | `check` / `plan` | 只读盘点和拟执行内容，不代表已完成初始化 |
| 首次完整初始化 | `init` | 安装缺失／无效 Skill；保留合法 Skill 壳，不保证其内容最新 |
| 只追加项目 | `init-projects` | 项目 AGENTS／ignore 与适用本地资产；不做全局安装或用户级 MCP／hooks 写入 |
| 对齐已有环境 | `upgrade` | 固定基线的 plan/apply/verify，显式裁决漂移，保留备份与恢复入口 |
| 明确要求重装 | `reset` | **不备份**覆盖 bundled Skills，重装 required external Skills；不是带恢复保证的升级流程 |
| 迁移旧数据 | `migration` | 批准投影、保留原件和验证回执；部署另行授权；中断未保存的部署证据只按当前状态调和，绝不回填伪造 |
| 退役已检测旧资产 | `cleanup-legacy` | 展示实际候选，再单独确认执行 |
| 恢复已授权批次 | `recovery` | 根据可信批次证据计划并确认恢复，不是通用撤销命令 |

[首次初始化提示词](#install)用于 bootstrap 之后的新 v2 环境。已有安装或 v1 项目使用下列对应提示词；执行前替换为精确的已审阅 v2 来源、项目根和配置域。

<details>
<summary><strong>再次执行 v2 init——不等于版本升级</strong></summary>

```text
请使用已审阅的 v2 sbtd-workflow-onboard，为平台 codex 和已有项目 /abs/project
制定 init 计划；我需要安装项目级 AGENTS.md。
先核对已安装包的 revision 和解释器依赖，再展示 plan --json，
列明全局 Skills/AGENTS/MCP 目标、项目写入及备份，等待我批准后才 init。
保留任务、身份、lessons 和旧数据。说明哪些合法 Skill 壳会被跳过，
不要把跳过说成内容已升级；如果需要版本对齐，停下来提出显式 upgrade 计划。
本次不授权 reset、迁移、旧资产删除或 hooks 启用。
```

</details>

<details>
<summary><strong>检查与 project-only 初始化提示词</strong></summary>

**检查已有环境：**

```text
请使用 sbtd-workflow-onboard 检查我的 codex 环境和 /abs/project。
本次只读：报告已安装 Skills、实际路径、项目冲突和缺失前置条件。
不要安装、reset、迁移、清理或修改任何配置。
```

**只追加项目，不改全局配置：**

```text
请使用 sbtd-workflow-onboard 的 init-projects 模式处理 /abs/project，平台 omp。
安装项目级 AGENTS.md。先执行 project-only 前置检查并展示本地写入范围，
等待我批准后再写入。不要安装或修改全局工具、Skills、AGENTS、MCP 或 hooks。
报告本地 Graft 图是已构建还是不可用。
```

</details>

<details>
<summary><strong>升级与 reset 提示词——两者不是同一操作</strong></summary>

**已有环境优先使用显式升级。**

```text
请使用 sbtd-workflow-onboard，为已有环境计划升级到已审阅的 Onboard 包基线。
先确认精确的全局 Skills 根、全局 AGENTS 目标、codex/omp 配置域、
需要处理的 shell profile，以及已有的私有备份 vault；只盘点该范围。
展示 upgrade --phase plan，并逐项说明定制内容的 replace/preserve 决定，
等待批准后才 apply。随后分别验证磁盘内容、运行时协议和真实宿主加载。
宿主 probe 另行询问；不要清理旧资产，也不要同步到其他环境。
```

隔离 probe 默认仍拒绝链接 Skill。需要保留链接时，先用 `upgrade --phase authorize-link` 明确批准其物理目标，再将生成的文档传给 `verify --probe --yes --link-authorization`。这只授权精确的本地目标访问及临时普通目录投影，不替换原链接、不跟随嵌套链接，也不证明现有会话已重载。命令及拒绝边界见[链接授权说明](sbtd-workflow-onboard/REFERENCE.md#probe-skill-link-authorization)。

**只应用已经审阅并批准的计划：**

```text
我确认[upgrade-plan 文件]中上一轮已展示的精确升级范围和 replace/preserve 决定。
请使用匹配的受信 v2 Onboard 执行器，复核来源、目标和私有 vault，
从该文件读取 plan_id，带实际所需确认执行 upgrade --phase apply，不让我手抄 hash。
保存实际回执和备份；如果范围或现场已变化，停下，不在旧授权下静默重新规划。
部分失败时报告已测得写入和续作路径。本次不授权宿主 probe、项目迁移、
清理或其他环境同步。
```

**核验已应用的升级，不启动宿主 probe：**

```text
请使用 upgrade --phase verify，消费[已批准计划]和[其实际 upgrade 回执]。
按精确基线核验安装包与选定资源，分别报告磁盘、运行时/协议、宿主加载和旧资产清理，
未执行层明确标 unverified。不要添加 --probe 或 --yes，不修复配置，也不删除备份。
```

**可选宿主及链接 Skill 验证——先确认范围：**

```text
请展示针对[upgrade 计划和回执]拟执行的宿主 probe，列明配置域、子进程、
临时投影及潜在副作用。该升级探测无需真实认证或模型请求，不读取或复制凭据文件；
等待我明确批准 probe。若遇到链接 Skill，先展示逻辑路径、物理目标、身份与内容范围，
只有我批准该目标后，才用 upgrade --phase authorize-link 保存精确授权。
随后按需要携带该授权运行 upgrade --phase verify --probe --yes。
保留原链接和无关配置；隔离宿主加载与现有会话重载分开报告。
无法证明隔离时标 blocked，不绕过；真实模型/行为 smoke另行确定范围和受控认证，
不包含在本升级 probe中。
```

**计划恢复本次升级，不混用迁移恢复：**

```text
请使用 recovery --phase plan，提供 --upgrade-plan [计划]和 --upgrade-receipt [回执]。
确认私有 vault 来源可信，核对当前漂移，展示精确恢复范围与限制，
只把恢复计划保存到已批准的私有位置。
另获恢复授权后才 recovery --phase apply，使用实际 --upgrade-recovery-plan，
从计划读取 recovery_id 供 --confirm-recovery 使用。
保留用户改动、备份和部分完成回执，不执行不受信历史代码。
```

这些提示词对应[实际 upgrade／recovery 命令](sbtd-workflow-onboard/REFERENCE.md#upgrade-alignment)。`verify` 成功不授权 cleanup；旧计划也不能授权已经变化的新包或新目标集合。

**只有明确要替换 Skill 内容时才使用 reset：**

```text
请使用已审阅的 v2 sbtd-workflow-onboard，为平台 codex 和 /abs/project 制定 reset 计划。
我需要重写项目级 AGENTS.md，但须先看到实际计划并确认。
核对包 revision 和解释器依赖；说明 bundled Skills 会无备份覆盖、
required external Skills 会重装。识别定制 Skill 内容；如果我需要保留，
停下来另行确认备份，或建议改用 upgrade。
列出所有全局/项目目标、AGENTS 备份和 MCP 影响，保留检测到的 React Bits tier/registry。
等待我批准后才 reset；保留任务、developer 身份、spec、lessons、handoff 和旧数据。
reset 不等于迁移、清理、全机升级，也不提供自动回滚保证。
```

</details>

<details>
<summary><strong>旧数据迁移、清理与恢复提示词</strong></summary>

**SBTD v1 项目迁移到 v2——包升级与数据迁移分开：**

```text
我的 /abs/project 正在使用 SBTD v1，希望迁移到[已审阅 v2 tag 或 commit]，
目标为[codex 和/或 omp，以及明确选定的配置域]。
先只读盘点：Onboard 版本、旧 Trellis/GitNexus 布局、项目分支、
定制规则、任务/spec/lessons、共享 HOME/Skills 的使用者和活动进程。
暂不运行 v1 init/reset、不复制凭据、不创建目录或修改配置。
分别制定 Onboard/Skills 包升级计划与项目数据迁移计划。
若旧执行器没有 v2 upgrade 入口，先展示如何准备已审阅的 v2 执行器、
保全既有安装，并单独请求该安装授权。
确认项目外私有 vault、保管人、保留原件、publication decisions、
已批准候选和恢复限制；展示真实 migration plan 后再请求 apply 授权。
获准 apply 后，部署另行确认；消费绑定 manifest/回执部署新规则/Skills/接线，
再验证数据、真实宿主行为和恢复证据。
验证后才展示批次及新鲜 cleanup 候选，另行请求删除授权；未知内容和备份继续保留，
不承诺旧 Trellis 可写回退。每个未获授权的阶段都停下，不用 reset 代替升级或迁移。
```

**请求清理计划，而非立即删除：**

```text
对 /abs/project 执行 sbtd cleanup 规划。若有已验证批次，展示批次候选，
并实际运行新的 cleanup-legacy plan。逐项列出目标，说明全局 MCP 对其他项目
的共享影响，然后再请求执行确认。保留未知内容、CLI 包、全局数据和备份。
```

**恢复指定批次：**

```text
请使用 sbtd-workflow-onboard recovery 恢复[明确选择的迁移或升级批次]。
验证可信私有 vault 和绑定回执，展示 recovery --phase plan、当前漂移、
精确恢复范围及不可恢复项。等待我批准后才 apply；保留备份，
如实报告部分完成结果。
```

**调和中断未保存的部署证据：**

```text
请使用 sbtd-workflow-onboard migration --phase reconcile 处理[apply 已完成
但累计部署证据未及保存的批次]。绑定精确的 manifest 与完整成功 apply 回执，
证明历史证据路径真实缺失，把当前状态新鲜实测写入新私有路径上的
一份带类型标记的新证据文档。不得伪造缺失的历史回执，也不得声称原部署
已运行完成；--yes 由我显式确认，之后运行标准 verify。
```

迁移器接受已刻画的 Trellis **0.6.15／0.6.17 数据布局**，不接受任意旧版本。用户内容的 hash 声明不是删除授权；批准缺失、任务关系矛盾或宿主配置不明仍会阻断。确实没有宿主配置的项目可保留空平台列表，不伪造宿主文件。vendor 卸载运行时仍独立钉版。

旧模板登记 hash 过期时，只能用安装包内已审核的**精确路径／版本／内容钉**补足识别；迁移不刷新旧 hash 文件，也不在运行时下载模板。混合项目规则的 `AGENTS.md` 不是整份生成资产，其替换仍须已有签名批准，绑定实际前态和精确候选。识别成功不等于授权 apply 或清理。
迁移部署保留已批准的项目规则正文，仅解除维护暂停前缀并追加受管 Graft 段，不静默换回通用模板。
OMP 部署也接受由绑定的成功迁移回执及完整原件证明的配置输入后态；未记录的漂移仍阻断，不豁免运行时版本检查，也不自动授权重试部署。

中断而未保存证据的部署只按**当前状态**调和，绝不回填：`migration --phase reconcile` 要求完整成功的 apply 回执、真实缺失的历史证据路径、全新不覆盖的输出路径以及显式 `--yes`。它重新验证签名运行时血统、保留原件与封存资源，然后写入一份显式标记 `kind: current-state`／`historical_execution: unknown` 的新证据文档——每项结果的 before 由保留原件证明，after 为本次新鲜实测，不伪造历史退出码、成功事实或旧时间戳。接受只表示当前后置条件成立，不代表原进程 exit0 或发生新的目标写入；随后的标准 `verify` 报告 `acceptance_basis: current-state`。这不授权任何安装、部署重试或清理，常规 deploy/retry/recovery 各门禁不变。

消费时重新核验所引用的 manifest／apply 是安全文件且摘要相符。观察者必须属于 manifest 同运行时或经签名批准的精确后继；反向或无关血统拒绝。历史观察者不要求等于当前消费者，累计重试不改写来源；这仍不证明未知历史执行，也不授权刷新旧证据。

新跨运行时观察在 `observer_lineage` 中保留原验签授权，后续配对文件轮换不会抹去历史观察者授权；消费者只信任已安装公钥，不接受证据自带密钥。旧无该证明的记录仍要求匹配的当前配对（同运行时除外），不补造已丢失的授权。计划／证据在接受输出前复核直接来源及 followup 祖先来源；cleanup/recovery 写前也须复核。晚期拒绝保留真实实测结果，但不宣称验收成功。

现态接受先完成语义／血统验证，再对实测对象和固定输入做最后的纯快照复核，包含 absent 资源；这不是跨进程原子快照，也不保证对象在检查后永不变化。

已与项目模板逐字对齐的规则可凭精确证据保持不动。只有文档的旧任务目录按历史文档归档，不伪造任务；历史任务分支保持原值，通过明确的延后恢复说明承接，不自动切分支或重绑定。

普通 RC 升级按内容比较和原生升级回执执行，不要求每次新增本机 lineage 签名。已验收的原始迁移批次在一次 Onboard 替换后，可仅在 cleanup 中成对提供 `--upgrade-plan`／`--upgrade-receipt` 及完整旧包备份：只读验证既有历史签名，不执行旧包代码，不授权 followup 或迁移恢复。可证明与实际清理无关的部署发现输入 file／absent 漂移可保持原样；目标、保留资产、profile、工具、vendor footprint 或来源漂移仍阻断。详见[清理契约](sbtd-workflow-onboard/REFERENCE.md#cleanup-runtime)。

[升级与恢复](sbtd-workflow-onboard/REFERENCE.md#upgrade-alignment) · [迁移](sbtd-workflow-onboard/REFERENCE.md#migration-runtime) · [清理](sbtd-workflow-onboard/REFERENCE.md#cleanup-runtime)

</details>

<a id="task-prompts"></a>
### 日常开发如何使用 SBTD

**普通任务从这里开始：**

```text
请在当前仓库使用 sbtd-task 的 default 模式完成[目标]。
先读取项目规则与相关 lessons，检查既有实现，做最小正确改动，
并实际运行、验证受影响路径。报告修改文件、真实验证结果、跳过项和剩余风险。
未经单独授权，不安装工具、不迁移数据、不部署，也不同步配置。
```

| 场景 | 建议提示词 |
|---|---|
| 小而边界明确的改动 | “使用 sbtd-task 的 **lite** 模式完成[改动]。保留共享短任务卡、验收清单和聚焦验证，不降低项目安全要求。” |
| 高风险或需要完整审计的交付 | “使用 sbtd-task 的 **strict** 模式完成[目标]。检出新分支，记录需求与验收，给出 Book Gate Plan，完成适用门禁和独立复核后报告证据。” |
| 需求尚不清晰 | “对[想法]使用 **grill-with-docs**。先读仓库事实，澄清决策并记录领域语言。完整访谈后调用 **book-ddd-distilled-modeling**，单独输出 DDD Boundary Review，通过后再设计或实现。” |
| 可复现故障 | “使用 **diagnosing-bugs** 分析[观察到的故障]。先建立可失败的反馈回路、定位根因，再按需使用 **tdd** 保留回归测试；同时验证修复与原有应保留行为。” |
| UI 与回归 | “对[页面／流程]使用 **ui-ux-pro-max**；项目已有 shadcn 时使用 **shadcn**，视觉复核使用 **impeccable**。调用 **gherkin-bdd** 和 **project-validation**；只有输入稳定可维护时，才用 **web-ui-autotest-generator** 沉淀 Playwright 资产。” |
| Mobile / Hybrid | “使用 **maestro-mobile-e2e** 验证[iOS/Android]上的[旅程]。生成 flow 前确认 BDD 来源、app、设备、后端、账号和 selector。执行适用 Maestro 验证，保留原生报告及中文汇总。” |
| 简化审查 | “使用 **ponytail-review** 审查本次 diff，建议可删除内容和更简单的原生方案，不牺牲正确性、可读性与安全。”全仓审计用 **ponytail-audit**，已有延后标记的清单用 **ponytail-debt**。 |
| 续作或交接 | “继续 SBTD 任务[task ID]。核对 root、branch 和有效 mode；保留原模式，多候选或冲突时询问。”／“为[task ID]准备 **sbtd-task** handoff，保留完成内容、证据、下一步与限制。” |
| 将行为读取到知识库 | “使用 **knowledge-base-integration**，读取[已配置产品／仓库]在[目标 ref]下的行为。解析精确 SHA，生成行为目录并报告缺失映射。**Mutation: none**；不改写 `.feature`，不发布 evidence。” |

需要工单产物？明确请求 **to-spec** 或 **to-tickets**，指定 tracker 并授权发布。它们不替代本地 task 状态；Onboard 也不会自动提供它们需要的 tracker 配置。

需要调整回复风格？`adhd mode` 显式启用 **i-have-adhd**；Caveman 可用时，`/caveman lite` 请求精简回复；`normal mode` 同时退出两者。**输出风格不改变 default/lite/strict 的执行义务。**

<a id="workflow"></a>
## 工作流如何配合

SBTD 是本仓库对四种实践的组合称呼，不是新的运行时或框架：

| 实践 | 回答的问题 | 常见产物或方法 |
|---|---|---|
| **SDD** — Specification-Driven Development | 要做什么，为什么做？ | 需求、PRD／design、验收标准 |
| **BDD** — Behavior-Driven Development | 用户能观察到什么？ | 项目拥有的 Gherkin 场景与可追踪测试 |
| **TDD** — Test-Driven Development | 如何在正确边界证明改动？ | 在约定测试 seam 上执行红—绿—重构 |
| **DDD** — Domain-Driven Design | 哪些术语、规则和边界必须一致？ | 词汇表、context／ADR 决策、独立边界审核 |

```text
读取项目事实与 lessons，确定任务、分支、范围和模式
  → 按需澄清需求与领域语言
  → 完整执行了 grill-with-docs？独立 DDD Boundary Review 必须 confirmed
  → 固化可观察行为，完成设计与适用的开发前门禁
  → 按风险采用 TDD 实现，运行 smoke 并检查可读性
  → 项目原生验证，以及适用 Web／Mobile／证据检查
  → 命中条件时执行发布就绪审核，记录真实完成状态
```

### 选择执行模式

| 模式 | 适合 | 工作契约 |
|---|---|---|
| `default` | 普通任务 | 按需调查、实现与聚焦验证，只保留必要本地记录 |
| `lite` | 需要共享轨迹的有限范围任务 | 短清单和共享任务卡，不机械补齐全套文档 |
| `strict` | 明确要求严谨交付 | 完成适用 before-dev／check／finish 义务、Book Gate Plan 与必需证据 |

模式优先级是：**本次明确选择 → 同一任务有效记录 → 真正新任务默认 default**。建议换模式必须等待你决定；“继续”不会重置模式。所有模式都保留明确交付、项目规范和安全边界。每次完整执行 `grill-with-docs` 后，**三种模式均必须**进行独立 DDD 审核。

Strict 门禁由事实触发：领域歧义、持久／共享数据、不明确的既有行为、生产代码改动、生产运行时／部署变化等。不是每个任务都运行全部门禁；必需门禁不可用时是 **blocked**，不是通过。[Strict 契约](sbtd-workflow-onboard/templates/skills/sbtd-task/references/strict.md) · [方法路由](sbtd-workflow-onboard/templates/skills/sbtd-task/references/methods.md) · [工作路径图](docs/assets/sbtd-workflow-paths.md)

### 状态只保留一个事实源

- `task.md` 拥有 mode、status 与 events。普通 default 任务在 `.sbtd/tasks/<id>/`；lite／strict 或明确共享任务在 `ai/tasks/<id>/`。`.sbtd/active-task.json` 只是书签。
- `cancelled` 是取消终止，**不是成功完成**，`completed_at` 保持 null；不自动取消子任务，归档和显式重开保留取消历史。导入的 `blocked` 记录若无法证明原阶段，恢复必须明确选择。旧安装使用这些记录前，应成套更新任务运行库、schema 与 Skill references。
- 真实暂停／切换或手动请求时，handoff 写入受保护的 `docs/handoffs/`；它不覆盖任务事实。纯问答／只读任务不创建 task、身份或 handoff 文件。
- 真正要写长期 lesson 时才需要 developer 身份，普通工作不需要。本地合法 `.sbtd/developer` 优先；只有确实缺失且已验证为 linked worktree，才只读主 checkout 的身份。不得猜名字或覆盖异常身份。

[任务状态](sbtd-workflow-onboard/templates/skills/sbtd-task/references/state.md) · [交接](sbtd-workflow-onboard/templates/skills/sbtd-task/references/handoff.md) · [Lessons](sbtd-workflow-onboard/templates/skills/lessons-record/SKILL.md)

<a id="skills"></a>
## 技能目录

**成套安装，按需使用。** 正常 Onboard `init`/`reset` 面向全局 Skills。仅 bootstrap 或 project-only 初始化，不会安装或激活完整全局工作流。成员以 [catalog](sbtd-workflow-onboard/catalog.json) 为准；点击 Skill 可查看完整说明与 references。

### 14 个 bundled Skills

| Skill | 职责／使用时机 |
|---|---|
| [sbtd-workflow-onboard](sbtd-workflow-onboard/SKILL.md) | 检查、安装、初始化、升级、迁移与恢复明确选择的环境 |
| [sbtd-task](sbtd-workflow-onboard/templates/skills/sbtd-task/SKILL.md) | default／lite／strict 任务路由、状态管理与续接 |
| [gherkin-bdd](sbtd-workflow-onboard/templates/skills/gherkin-bdd/SKILL.md) | 固化可观察行为，区分可写 BDD sync 与只读 ingest |
| [project-validation](sbtd-workflow-onboard/templates/skills/project-validation/SKILL.md) | 选择原生检查、适用测试工具，约束证据与报告状态真实性 |
| [web-ui-autotest-generator](sbtd-workflow-onboard/templates/skills/web-ui-autotest-generator/SKILL.md) | 生成／审计可维护 Playwright 资产与 selector／coverage manifest |
| [maestro-mobile-e2e](sbtd-workflow-onboard/templates/skills/maestro-mobile-e2e/SKILL.md) | 从 BDD 派生 Mobile／Hybrid Maestro flow，核对真实设备前置条件 |
| [knowledge-base-integration](sbtd-workflow-onboard/templates/skills/knowledge-base-integration/SKILL.md) | 产品注册、Evidence Policy、Revision Set、只读 ingest 与分阶段 smoke |
| [lessons-record](sbtd-workflow-onboard/templates/skills/lessons-record/SKILL.md) | 核验作者身份，按 topic／index 所有权记录长期经验 |
| [book-ddd-distilled-modeling](sbtd-workflow-onboard/templates/skills/book-ddd-distilled-modeling/SKILL.md) | 审核领域语言与边界；完整 grill-with-docs 后强制调用 |
| [book-ddia-data-design](sbtd-workflow-onboard/templates/skills/book-ddia-data-design/SKILL.md) | 审核数据所有权、一致性、schema、cache、migration 与 recovery 设计 |
| [book-legacy-change-safety](sbtd-workflow-onboard/templates/skills/book-legacy-change-safety/SKILL.md) | 风险改动前刻画既有行为并建立安全网 |
| [book-refactoring-pass](sbtd-workflow-onboard/templates/skills/book-refactoring-pass/SKILL.md) | 生产代码编辑前，审核最小且安全的结构变化 |
| [book-release-readiness](sbtd-workflow-onboard/templates/skills/book-release-readiness/SKILL.md) | 必需验证后审核运行风险与回滚能力 |
| [seo-geo](sbtd-workflow-onboard/templates/skills/seo-geo/SKILL.md) | 公开 Web 资产的搜索／AI 可见性检查，不替代内部应用或 API 回归 |

<a id="external-skills"></a>
### 19 个 required external Skills

这些是经过审阅的**上游原样镜像**，不是本地 fork。`auto` 与 `stable` 从包内快照安装，不获取上游；只有显式选择 `upstream` 才进入当前上游评估。精确 revision、checksum 与许可证见 [stable manifest](sbtd-workflow-onboard/assets/external-skills/stable/MANIFEST.json)。

| 分类 | Skills | 用途 |
|---|---|---|
| 澄清 | [grilling](sbtd-workflow-onboard/assets/external-skills/stable/skills/grilling/SKILL.md)、[grill-me](sbtd-workflow-onboard/assets/external-skills/stable/skills/grill-me/SKILL.md)、[grill-with-docs](sbtd-workflow-onboard/assets/external-skills/stable/skills/grill-with-docs/SKILL.md) | 压力测试决策；需要领域记录时使用 with-docs 版本 |
| 规格 | [to-spec](sbtd-workflow-onboard/assets/external-skills/stable/skills/to-spec/SKILL.md)、[to-tickets](sbtd-workflow-onboard/assets/external-skills/stable/skills/to-tickets/SKILL.md) | 将已达成共识的讨论转为 tracker 规格与带依赖的工作切片 |
| 设计 | [domain-modeling](sbtd-workflow-onboard/assets/external-skills/stable/skills/domain-modeling/SKILL.md)、[codebase-design](sbtd-workflow-onboard/assets/external-skills/stable/skills/codebase-design/SKILL.md) | 统一语言、context 决策、模块接口与测试 seam |
| 调试与测试 | [diagnosing-bugs](sbtd-workflow-onboard/assets/external-skills/stable/skills/diagnosing-bugs/SKILL.md)、[tdd](sbtd-workflow-onboard/assets/external-skills/stable/skills/tdd/SKILL.md) | 证据优先诊断与红—绿反馈回路 |
| UI | [ui-ux-pro-max](sbtd-workflow-onboard/assets/external-skills/stable/skills/ui-ux-pro-max/SKILL.md)、[impeccable](sbtd-workflow-onboard/assets/external-skills/stable/skills/impeccable/SKILL.md)、[shadcn](sbtd-workflow-onboard/assets/external-skills/stable/skills/shadcn/SKILL.md) | UX／设计系统、视觉打磨与 shadcn/ui 专项实现 |
| 简化 | [ponytail](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail/SKILL.md)、[ponytail-review](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail-review/SKILL.md)、[ponytail-audit](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail-audit/SKILL.md)、[ponytail-debt](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail-debt/SKILL.md) | 最小实现、diff 审查、全仓审计与延后事项清单 |
| Agent 协作 | [handoff](sbtd-workflow-onboard/assets/external-skills/stable/skills/handoff/SKILL.md)、[writing-for-agents](sbtd-workflow-onboard/assets/external-skills/stable/skills/writing-for-agents/SKILL.md) | 通用交接摘要与 Agent 文档写作；SBTD 状态仍由 sbtd-task 管理 |
| 回复结构 | [i-have-adhd](sbtd-workflow-onboard/assets/external-skills/stable/skills/i-have-adhd/SKILL.md) | 显式启用、会话级、行动优先的回复结构；安装不等于启用 |

Onboard 使用 **Ponytail skill-only provider**。官方 Ponytail plugin 已启用时属于冲突，不代表获准禁用它；plugin 管理及 `ponytail-gain`／`ponytail-help` 不归 Onboard 负责。[Provider 边界](sbtd-workflow-onboard/REFERENCE.md#ponytail-provider-boundary)

<a id="verification"></a>
## 工具分工与验证边界

| 工具／层次 | 主责 | 不能证明 |
|---|---|---|
| Graft | 固定版本、明确范围的结构分析与影响辅助 | 编译器语义、业务正确性或宿主自动就绪 |
| Chrome DevTools MCP | 浏览器运行时、console／network／performance 诊断 | 可重复 CI 回归 |
| Playwright MCP | 页面探索与 locator 辅助 | 项目 Playwright suite 已通过 |
| Playwright CLI | 项目级 Web 回归与 E2E | 只有 mock／contract 时的真实 full-stack 行为 |
| Maestro CLI / MCP | Mobile／Hybrid flow、设备与 flow 诊断、可选 Web smoke | Web 回归主责或缺失设备上的真实行为 |
| RTK / Caveman | 终端输出／对话压缩 | 测试执行、报告生成或工作流义务降低 |

Graft 安装须单独确认，版本由[受管运行时](sbtd-workflow-onboard/scripts/graft_runtime.py)固定。每个有效 Codex／OMP 配置域只有一条全局 `sbtd-graft` 连接，按启动 cwd 锁定真实仓库／worktree；项目初始化准备本地图。不做共同父目录多项目图、不隐式开启 cloud enrichment、不静默替换旧绑定。Codex hooks 单独 opt-in；OMP 初始化不写 hooks。[接线契约](sbtd-workflow-onboard/REFERENCE.md#codex-and-omp-wiring-and-deployment)

即使本机安装了 Trail，受管 Graft 也保持 Graft 命令／工具合同：子进程禁用自动 Trail 切换并隔离继承的 Trail 配置。项目 `.trail` 笔记与原生图输入同样执行拒绝链接／特殊文件的范围检查。见 [pin 验收场景](sbtd-workflow-onboard/REFERENCE.md#graft-pin-acceptance-scenarios)。

**只报告实际执行结果。** 报告型测试优先原生命令；保留失败轮次、命名后的 native／raw 报告及同 stem **中文**汇总。区分 `full-stack`、`contract-backed`、`mock-backed`／`app-mocked`、`backend-only`、`smoke-only` 和 `blocked`；报告已生成不等于测试通过。dirty 本地证据不代表精确 PR head 的 CI 证明。

Agent 编写的执行汇总统一使用[固定中文报告模板](sbtd-workflow-onboard/templates/skills/project-validation/references/run-summary.zh-CN.md.template)：结论与统计、运行信息、命令、BDD／范围、逐例结果、失败与复跑、API URI 覆盖、产物与状态、限制。保留失败轮次及源码／部署边界；无法提供的字段必须写原因，不填造数值。覆盖率评分作为附录，不能替代执行结果。历史报告不改写；已有证据的重新排版须另存并标明预览，不代表新的测试运行。

| 资产 | 目标项目中的默认位置 |
|---|---|
| BDD 源 | 项目既有 `.feature` 约定；无约定时使用中文场景正文与英文结构关键词 |
| Playwright 测试 manifest | `tests/e2e/manifest/`，显式传路径，不使用生成器的根目录默认值 |
| Playwright 留存报告 | `tests/e2e/reports/html/` |
| API 报告 | `tests/api/reports/` |
| Maestro flow／报告 | `maestro/flow/`／`.maestro/reports/` |
| Unit 报告 | 优先项目约定；需要报告而无约定时用 `tests/unit/reports/` |
| SBTD 任务本地证据 | `ai/tasks/**/reports/`，忽略报告，任务正文仍可共享 |

知识库 P1.1 生成只读目录与 smoke bundle；远端 Evidence Store／PR Check 和发布仍属于 P2。BDD `sync` 是另一条可写工作流。[知识库说明](sbtd-workflow-onboard/templates/skills/knowledge-base-integration/SKILL.md) · [证据契约](sbtd-workflow-onboard/templates/skills/project-validation/SKILL.md)

<details>
<summary><strong>可选工具与常见误区</strong></summary>

- Playwright 是项目依赖。Java 17+ 与 Maestro、可选 MCP、RTK、Caveman 遵守相应安装选择；Skill 存在不证明其 CLI／server 在当前会话可调用。
- Caveman 可按全局 auto-lite 规则压缩重复进度；`normal mode` 在当前任务退出自动压缩。ADHD 结构只能显式启用。详见[表达规则](sbtd-workflow-onboard/templates/skills/sbtd-task/references/presentation.md)。
- React Bits 是可选项目增强，不是 shadcn 必装依赖。Free registry 必须明确；付费 tier 需要已有授权及本地 key 处理。密钥不得写入聊天、示例或报告。[React Bits 范围](sbtd-workflow-onboard/REFERENCE.md#react-bits)
- `init` 不等于内容对齐；`reset` 不等于带恢复保证的升级。升级验收分别报告磁盘、协议和真实宿主加载；保留定制差异不等于完全对齐。
- 旧 Trellis／GitNexus 是迁移输入，不是当前工作流。正常初始化不建立 Trellis，也不执行旧资产清理。清理须展示清单再确认；备份保留与销毁另有边界。

</details>

<a id="reference"></a>
## 详细参考与手动入口

| 需要了解 | 入口 |
|---|---|
| 完整 Onboard 命令、范围与排障 | [SKILL](sbtd-workflow-onboard/SKILL.md) · [REFERENCE](sbtd-workflow-onboard/REFERENCE.md) |
| Bootstrap／init／reset／project-only 流程图 | [Bootstrap](docs/assets/npx-skills-global-onboard-install.md) · [Init](docs/assets/onboard-skill-init.md) · [Reset](docs/assets/onboard-skill-reset.md) · [Project-only](docs/assets/onboard-init-projects.md) |
| 升级／迁移／清理／恢复 | [升级](sbtd-workflow-onboard/REFERENCE.md#upgrade-alignment) · [迁移与恢复](sbtd-workflow-onboard/REFERENCE.md#migration-runtime) · [清理](sbtd-workflow-onboard/REFERENCE.md#cleanup-runtime) |
| 全局／项目规则 | [全局模板](sbtd-workflow-onboard/templates/agents/AGENTS.global.md) · [项目模板](sbtd-workflow-onboard/templates/agents/AGENTS.project.md) |
| 发布历史／监控版本 | [中文变更日志](CHANGELOG.zh.md) · [English CHANGELOG](CHANGELOG.md) · [ENTRYPOINT](ENTRYPOINT.md) |

<details>
<summary><strong>Bootstrap 后手动执行，或从已克隆仓库启动</strong></summary>

将 `SBTD_ONBOARD_DIR` 设为**实际安装包目录**，并先准备所需依赖。首先审阅计划：

```bash
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" plan \
  --platform codex --projects-root /abs/project-one,/abs/project-two --json
```

审阅并批准相同范围后，再执行：

```bash
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" init \
  --platform codex --projects-root /abs/project-one,/abs/project-two --yes --json
```

已克隆仓库时，也可以启动完整交互式安装器：

```bash
bash install.sh
```

```powershell
pwsh -File .\install.ps1
```

Project-only 使用 `bash install.sh --platform codex --init-projects /abs/project`，或 `pwsh -File .\install.ps1 -Platform codex -InitProjects "C:\work\project"`；与普通 `--projects-root`／`--action` 选择互斥。根安装器正常 `init`／`reset` 带 `--yes`／`-Yes` 而没有项目路径时，表示 **global-only**，不隐式选择 cwd。确认参数只批准所选操作，不绕过冲突，也不授权迁移。

</details>

<a id="repository"></a>
## 仓库与维护

| 路径 | 职责 |
|---|---|
| `README.md`／`README.zh.md` | 英文与中文阅读入口；详细契约留在链接指向的源文件 |
| `sbtd-workflow-onboard/` | 自包含可安装 Skill：运行实现 `scripts/`、载荷 `templates/`、镜像 `assets/`、catalog 与参考说明 |
| `install.sh`／`install.ps1` | 根安装入口；source root 是 Onboard 目录 |
| `ENTRYPOINT.md` | 已追踪的版本监控基线与可恢复维护入口 |
| `docs/lessons.md` | 必读 lessons 短入口，按需读取 index／topic 详情 |
| `prompts/automations/sbtd-workflow-tools-version-check.md` | 版本化 automation prompt，不等于 live automation 已更新 |
| `prompts/automations/references/` | 版本检查每轮必读的权限范围与按主题加载的兼容性清单 |
| `.github/workflows/validation.yml` | 项目原生验证矩阵 |

本摘录仓根 `AGENTS.md` 是**可选、被忽略、仅本机保留**的规则，不是项目模板，也不是新 clone 的前置条件。根 `.gitignore` 与[目标项目模板](sbtd-workflow-onboard/templates/project/.gitignore)有意分开：

```gitignore
.DS_Store
/.sbtd
/docs/handoffs
/ai/tasks/**/reports
/graft
/.graft
__pycache__/
AGENTS.md
.chrome-devtools-mcp/
.playwright-mcp/
```

Ignore 不会脱敏、不取消已有 tracked 状态，也不授权删除。任务报告默认本地留存；发布证据必须先脱敏并单独确认目标位置。**本配置源仓不生成 `.feature` 文件**；持久行为规格使用 Markdown 与现有测试。

源文件变化时，同轮评估两种语言的 README、[英文 CHANGELOG](CHANGELOG.md)、[中文变更日志](CHANGELOG.zh.md)和[版本化 automation prompt](prompts/automations/sbtd-workflow-tools-version-check.md)。两份变更日志逐条对应，版本、日期、顺序、事实、URL、提交SHA和代码标识相同，仅正文语言不同；同步更新最上方未发布章节，保留已发布历史。普通改动**不**同步已安装副本或 live automation。仓库维护 `sync`／`同步` 需要明确授权；`update`／`更新` 推进除 Graft 以外的监控基线并归档已分析更新。Graft 的 ENTRYPOINT 基线只跟已发布 SBTD workflow 版本中的 pin，不由官方 Graft 发行或 `update` 推进。它们不是 Onboard upgrade，也不是 BDD sync。

版本检查自动化采用精简主prompt、每轮权限清单及按需影响检查。先核对Orca分配的工作区并保护已有改动，区分证据不可用与“没有更新”，官方工具始终以 `ENTRYPOINT.md` 为固定基线。Graft 是例外：只有已发布 workflow 版本中的受管 pin 变化时，才同步其 ENTRYPOINT 版本字段。原始tag与比较版本分别记录。没有已确认的未发布CHANGELOG章节时，发布条目建议留在 `UPDATE.md` 或本轮输出，不由自动化猜下一tag。修改这些源文件不会更新live automation，后者仍须明确 `sync`。

原生全量命令仍为 `python -B -m unittest discover -s tests -p 'test_*.py'`。CI 自动发现完整 Linux 集合，按逐例实测耗时权重分为互不重叠的分片：无fixture的用例逐个分配，类级／模块级fixture保持同片，缺少权重的用例按中位数估算并在各分片清单中列出；Windows 将原生范围分片，消除 PowerShell／Unicode 选择器重叠；macOS 保留原生范围。既有检查名称聚合全部必需分片，任一失败、取消或缺失均不能通过。最低 TOML 编辑器检查使用不同依赖版本，仍独立保留，不当作重复。逐例耗时、skip 原因和中文结果摘要保存为 CI artifact。精确范围见 [workflow](.github/workflows/validation.yml) 与[运行器](tests/run_ci.py)。源码检查、安装副本检查、真实宿主加载与发布验收仍是不同层次的证据。

不依赖完整清单的迁移边界测试仅缩小安装输入：仍保留完整 Onboard 启动器包、多个兄弟 Skill 和全部文件路由操作；完整清单生命周期与已安装副本测试继续作为独立锚点。每个阶段仍调用真实迁移／恢复 API 并重新执行安全校验；小型夹具不授权缓存通过结论、复用回执或省略漂移场景。总 runner 成本与并行墙钟等待分别比较。

Windows 必需原生检查（ACL、junction、Unicode、PowerShell 及已启用的大小写敏感路径）与 Linux 大小写敏感检查必须实际通过；仅被选中不够，skip 或预期失败也会阻断所在分片。

CI artifact 按原生运行 attempt 保留，不覆盖失败记录。部分重跑可沿用同一 SHA 已成功的分片；聚合取各分片最新报告，拒绝较新的失败或同 attempt 重复证据，并核对分片并集完整且不重叠。skip 总数按原生事件统计，包含被跳过的子场景，可能不同于父例状态计数；跨轮对照保留子场景身份与理由。

当前Windows四分片、Linux三分片、macOS单job。下载完整成功的原生报告集合后，可执行 `python -B tests/run_ci.py --platform windows --output <downloaded-reports> --refresh-weights` 刷新调度输入（Linux使用 `linux`）。刷新要求非空源码修订身份及无歧义、完整互斥的最新attempt集合；重复测量或非规范分片文件名会被拒绝。权重只影响分配，不决定是否执行用例；行／分支覆盖相同本身不足以删除行为或平台边界测试。

<a id="license"></a>
## 许可证与致谢

仓库原创与 bundled 原创内容使用 [Apache License 2.0](LICENSE)，包内分发 [Onboard LICENSE](sbtd-workflow-onboard/LICENSE) 与 [NOTICE](sbtd-workflow-onboard/NOTICE)。第三方镜像保留各自许可证和固定来源；衍生的 [seo-geo NOTICE](sbtd-workflow-onboard/templates/skills/seo-geo/NOTICE) 记录上游来源与本地修改范围。
