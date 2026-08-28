# SBTD Workflow / `omp-sbtd` Plugin 基于 Agent Plugins 1.0.0 的改造落地方案

> **文档版本**：0.6-draft
> **文档日期**：2026-08-20
> **适用基线**：精确 OMP `17.3.5` / Agent Plugins 1.0.0  
> **现有设计基线**：KPi PRD / ROADMAP v0.7  
> **目标插件**：`@kunolu/omp-sbtd`（npm 包名）/ `omp-sbtd`（Agent Plugin manifest `name`）  
> **核心原则**：**Portable Capability Layer + OMP Runtime Control Plane**  
> **不变原则**：P0 不 Fork OMP；SBTD 工作流语义、三层 AGENTS、Onboard 安全边界、Book Gates、BDD SOT、Trellis/GitNexus/Validation 规则均继续保留。

---

## 0.0 当前基线与版本冻结说明（Current Baseline / Revision Note）

本文档的 M0–M5 已完成。M4 静态门已通过（clean `ec849c62…` tarball）。`@kunolu/omp-sbtd@0.1.0-rc.12` 已发布到 npm `next`（SHA-256 `49edb4b7…`）。手册第 4 节已对该 tarball 全收。**第 28.4 节 Host 项为可选项** `not-run`，不得写成 passed / exact-host certified。**CI 未接入时 portable projection 晋升仍 blocked**。npm RC 发布不等于晋升。

| 事实 | 当前值 |
|---|---|
| npm 包 | `@kunolu/omp-sbtd` |
| 包版本 | `0.1.0-rc.12`（版本号与 `plugin.json`/`skills/**` 由 M2 写入；**可认证 tarball 冻结点在 M3 切流之后**。M4 只认证含本次 Runtime/Onboard/Doctor 切流的同一版本包。改版本号必须退回 M2） |
| OMP Host（peer dependency） | **精确 `17.3.5`**（`@oh-my-pi/pi-coding-agent: 17.3.5`，非 range） |
| Runtime 形态 | `src/**` 编译为 `dist/extension.js`，通过 `package.json` 的 `omp`/`pi` `extensions` 字段加载 |
| 根 `plugin.json` | **已存在**，Agent Plugins schema 1.0.0，`version=0.1.0-rc.12` |
| 根 `skills/` | **已存在**，12 个 certified 目录，digest 对照 `generated-agent-plugin/**` |
| 根 `mcp.json` | **尚不存在** |
| Workflow Kit 固定 revision | `4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb` |
| Kit catalog | 第三树仍是 15 个 bundled 候选；**当前 OMP Onboard overlay** 为 3 个 bundled-skill（`sbtd-workflow-onboard`、`trellis-workflow`、`trellis-channel`）+ 12 个 external-skill |
| 当前生成器输出 | `packages/sbtd-workflow-kit/generated/**`、`generated-omp/**` 与 `generated-agent-plugin/**`；第三树当前 `candidateCount=13`、`certifiedCount=12` |
| 冻结发布版本 | `0.1.0-rc.12`（已写入 `plugin.json` 与 `package.json`；改版本必须退回 M2） |

> **历史参考（非迁移目标）**：Agent Plugins 1.0.0 能力最早出现在 OMP 17.2.x 系列（含 17.2.11）。本方案的迁移目标、验证基线与发布断言一律针对**精确 17.3.5**；任何对更早版本的兼容声明均属历史叙述，不构成本方案的支持承诺。

**M0 冻结要求**：迁移开工前必须冻结一个可复现的 clean baseline——记录当时的 git revision、工作树 dirty/clean 状态、`640-skills` pin、Workflow Kit revision 与 15 个 bundled 候选的 digest。当前 dirty/clean revision 必须在 M0 被显式冻结，后续所有差异对比都以该冻结基线为准。

**M0 当前状态（2026-08-18）**：已冻结。可重建基线见 `.trellis/tasks/archive/2026-08/08-18-agent-plugins-m0-m1/research/baseline.md`；冻结 HEAD 为 `39aaa4287eb2f8e3bcc20a811db33def9ef3f125`，Kit revision、source tree、15 个 bundled digest 与 12 个 external skills 清单均已记录。M1 未修改 `upstream.lock.json`。

---

## 0. 执行结论

本次改造**不是重写 SBTD Workflow**，也不是用 Agent Plugins 1.0.0 替代 OMP Plugin。

最终推荐架构（Hybrid Plugin）：

```text
@kunolu/omp-sbtd
│
├─ Portable Capability Layer（新增）
│  ├─ plugin.json            ← 根 Manifest，Agent Plugins 1.0.0
│  └─ skills/                ← 由生成器投影产生，build-owned
│
├─ OMP Runtime Control Plane（保持现状）
│  ├─ src/** → dist/extension.js
│  └─ kit/**
│
└─ Optional Portable Integration Plugins（后续独立决策）
   ├─ sbtd-gitnexus/
   ├─ sbtd-playwright-mcp/
   └─ sbtd-maestro-mcp/
```

### 核心决策

1. **新增 Agent Plugins 1.0.0 根 `plugin.json`**，其 `version` 与 `package.json` `version` 完全一致（同一 artifact 单一版本事实）。
2. **通过 portability audit 认证的可跨 Agent 复用 Skills（certified set）使用 `skills/<name>/SKILL.md` 标准目录**，由 Workflow Kit 投影生成，build-owned、digest-verified、不手工编辑。
3. **`/sbtd on/off/help/...`、Session State、Book Gate、Rule/Policy/Validation、Runtime Marker 保持 OMP-specific**，继续由 `src/** → dist/extension.js` 承载。
4. **三层 AGENTS 不迁入 Agent Plugins。**
5. **`onboard.py` 不迁入 portable core，继续作为 P0/P1 的 OMP/KPi 安装与环境管理兼容层。**
6. **核心 `omp-sbtd` 包暂不直接携带所有可选 `mcp.json`。**
7. **GitNexus / Playwright MCP / Maestro MCP 等保持显式 opt-in；后续需要 portable MCP 时拆成独立 Integration Plugin。**
8. **第三方 Required External Skills 暂不重新打包，仍由 Onboard 管理。**
9. **Agent Plugins 只负责 portable capability packaging，不负责 SBTD Runtime enforcement。**
10. **OMP 精确 `17.3.5` 作为迁移目标与验证基线。** peer range 放宽是独立的认证/晋升决策，仅由 `docs/assets/omp/omp-plugin-compatibility-decoupling-plan.md` 治理，不属于本迁移范围。
11. **P0 分发渠道为 npm immutable tarball**；Marketplace 是 optional post-P0 决策。
12. **CI/Conformance 是 portable projection 发布的前置条件**，不再是晚期 backlog 项。

---

# 1. 当前 SBTD / KPi v0.7 基线

当前架构已经明确：

```text
OMP（精确 17.3.5）
  + @kunolu/omp-sbtd@0.1.0-rc.12
  │   ├─ plugin.json + skills/**（M2 组包；M3 Runtime 从 packaged skills/** 读 certified 证据）
  │   ├─ src/** → dist/extension.js（Runtime extension）
  │   └─ kit/**（Onboard、AGENTS 模板、catalog、外部资产）
  + Global AGENTS
  + Root Project AGENTS
  + .omp/AGENTS.md
  + SBTD Skills
  + Trellis
  + GitNexus
  + Playwright
  + Maestro
  + Book Gates
  + Validation / Evidence / Lessons
```

SBTD 主流程保持：

```text
intake
  → lessons-gate
  → repo-inspect
  → sbtd-classify
  → tool-evidence
  → route
  → requirement-clarify
  → specification
  → book-gate-plan
  → before-dev
  → implement
  → targeted-validate
  → full-validate
  → runtime/e2e-validate
  → review
  → release-gate
  → report
  → lessons-record
  → completed | blocked
```

现有三层规则继续保留：

```text
$PI_CODING_AGENT_DIR/AGENTS.md
  ↓ 用户级 Always-on + SBTD Mode Contract

<project-root>/AGENTS.md
  ↓ 跨 Agent 项目事实层

<project-root>/.omp/AGENTS.md
  ↓ OMP/KPi Runtime Adapter
  ↓ @../AGENTS.md
```

本次 Agent Plugins 改造**不改变上述状态机和 Context 分层**。

当前 bundled Skill 资产共 **15 个候选**：

- **13 个 portable candidate set（首批可移植候选）**：`trellis-workflow`、`project-validation`、`web-ui-autotest-generator`、`gherkin-bdd`、`knowledge-base-integration`、`maestro-mobile-e2e`、`lessons-record`、`book-refactoring-pass`、`book-legacy-change-safety`、`book-ddd-distilled-modeling`、`book-ddia-data-design`、`book-release-readiness`、`seo-geo`。
- **2 个 OMP-specific**：`sbtd-workflow-onboard`、`trellis-channel`。

13 个候选只是 audit 输入，不是打包承诺；最终进入 tarball 的数量由 **certified set**（见第 7 章）决定。

---

# 2. Agent Plugins 1.0.0 在本项目中的定位

Agent Plugins 1.0.0 应被定义为：

> **KPi/SBTD 的跨 Agent 可移植能力封装层，而不是工作流 Runtime。**

迁移目标 Host（精确 OMP 17.3.5）原生实现的标准能力主要是：

```text
plugin.json
skills/
mcp.json
${PLUGIN_ROOT}
${PLUGIN_DATA}
package containment / validation
```

因此能力分层调整为：

| 层 | 标准 | 责任 |
|---|---|---|
| Portable Package | Agent Plugins 1.0.0 | 插件身份、certified Skills、可选 MCP |
| Portable Skill | Agent Skills | 专项知识、流程、检查清单 |
| Runtime | OMP Extension / Plugin | `/sbtd`、Session、Gate、Hook、Tool |
| Context | AGENTS.md | Always-on / Project Facts / Runtime Contract |
| Environment | Onboard | 安装、迁移、Managed Block、MCP opt-in |
| External Tool | Trellis/GitNexus/Playwright/Maestro | 真实执行能力 |

---

# 3. 为什么不能把整个 `omp-sbtd` 都“标准化”

Agent Plugins 1.0.0 当前不承载以下 SBTD 必需能力：

- `/sbtd on`
- `/sbtd off`
- `/sbtd help`
- `/sbtd doctor`
- `/sbtd onboard ...`
- OMP Session State
- Compaction/Resume 状态恢复
- Tool Call 拦截
- `block-tool`
- `block-stage`
- `block-delivery`
- Book Gate 状态机
- Validation Engine
- Runtime Marker
- Advisor / Task / Model Role 管理
- OMP Hook
- OMP Custom Tool
- OMP-specific Command Registry
- Project Context Shadowing 检测

因此：

```text
Agent Plugins 1.0.0
≠
OMP Plugin Runtime
```

正确关系是：

```text
Agent Plugins 1.0.0
      ↓
Portable Skills / MCP（model-visible capability）

OMP Plugin Runtime
      ↓
执行 SBTD 状态机与硬门禁
```

---

# 4. 目标目录结构

推荐将 `@kunolu/omp-sbtd` 改造成一个 **Hybrid Plugin**。**现有 Runtime 布局保持不变**：`src/**` 继续编译为 `dist/extension.js`，继续通过 `package.json` 的 `omp`/`pi` `extensions` 字段加载。迁移只**新增**根 `plugin.json` 与生成式根 `skills/**`，不搬迁现有 Runtime。

```text
omp-sbtd/                       （npm 包 @kunolu/omp-sbtd）
├─ plugin.json                  ← 新增：Agent Plugins 1.0.0 根 Manifest
├─ package.json                 ← 保持：omp/pi extensions、peer 精确 17.3.5
├─ README.md
├─ LICENSE                      （GPL-3.0-only）
├─ SECURITY.md / CHANGELOG.md / THIRD_PARTY_NOTICES.md / SBOM.spdx.json
│
├─ skills/                      ← 新增：build-owned 投影输出，digest-verified，不手工编辑
│  └─ <certified-set 中的每个 Skill>/
│     ├─ SKILL.md
│      ...
│
├─ src/                         ← 保持：Runtime 源码
│  ├─ extension.ts
│  ├─ commands/  hooks/  tools/  gates/  rules/  workflow/  ...
│  └─ ...
├─ dist/                        ← 保持：构建产物 dist/extension.js（npm files 白名单）
│
├─ kit/                         ← 保持：Onboard / AGENTS 模板 / catalog / 外部资产
│  ├─ onboard/
│  │  └─ onboard.py
│  ├─ AGENTS.global.md
│  ├─ AGENTS.project-root.md
│  ├─ AGENTS.project-omp.md
│  ├─ catalog.json / manifest.json
│  ├─ schemas/
│  └─ third-party/ + 外部 skill 资产
│
├─ scripts/                     ← 保持：embed-kit / clean-dist / sbom 等
├─ test/                        ← 保持
├─ features/                    ← 保持：BDD SOT
└─ docs/                        ← 保持：随包文档
```

### P0 明确不创建的根目录

```text
commands/
hooks/
tools/
runtime/
```

这些目录在当前 Agent Plugins 1.0.0 标准下没有对应的声明式语义。P0 **不**把现有 `src/**` Runtime 迁到这些根目录；只有当未来出现真正声明式的 OMP 资产（例如标准 commands/hooks/tools 清单）且有明确收益时，才单独评估是否引入。

### 暂不建议在核心包根目录放置

```text
mcp.json
```

原因见第 8 章。

---

# 5. `plugin.json` 落地设计

根目录 **已存在** `plugins/omp-sbtd/plugin.json`（M2 落地，不是待写建议）。当前冻结样例如下。

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "omp-sbtd",
  "version": "0.1.0-rc.12",
  "description": "SBTD workflow capabilities for coding agents, with an OMP runtime control plane.",
  "license": "GPL-3.0-only",
  "keywords": [
    "oh-my-pi",
    "omp",
    "sbtd",
    "kpi",
    "workflow-gates",
    "bdd",
    "validation-evidence"
  ],
  "homepage": "https://github.com/KunoLu/KPi",
  "repository": {
    "type": "git",
    "url": "https://github.com/KunoLu/KPi.git",
    "directory": "plugins/omp-sbtd"
  }
}
```

注意：

- **包名与 manifest 名的区别**：npm 包名是 `@kunolu/omp-sbtd`（带 scope 的分发身份）；Agent Plugin manifest `name` 是 `omp-sbtd`（标准要求的插件短名，也是 Marketplace/Host 内的插件 id）。两者不是同一个事实，不互相替代。
- **版本单一事实**：`plugin.json.version` 必须与 `package.json.version` 完全一致。当前冻结值为 `0.1.0-rc.12`。可认证 tarball 冻结点在 M3 切流之后；M4 认证含该切流的同一版本包。改版本必须退回 M2 并重跑 M3–M4。
- **不写重复的 Host 版本事实**：不在 manifest 中用自定义 `extensions.*.minimumOmpVersion` 之类的字段重复声明 OMP 版本。Host 兼容性事实只存在于两处：`package.json` 的 `peerDependencies`（精确 `17.3.5`）和 Runtime extension 自己的启动期版本检查。自定义 namespace 当前也不被 Agent Plugins loader 解释，写入只会制造漂移源。
- 不增加非标准顶层字段。
- 不用 `plugin.json` 保存 Session State 或用户配置。

---

# 6. 现有资产迁移矩阵

| 现有资产 | 新归属 | 是否 Portable | 处理方式 |
|---|---|---:|---|
| `plugin manifest` | 根 `plugin.json` | 是 | 新增为 Agent Plugins 1.0.0 |
| Bundled Skills（certified set） | `skills/*`（生成投影） | 是 | 仅 audit 认证通过的子集进入 Agent Skills 严格格式投影 |
| Bundled Skills（未通过 audit） | Onboard/Runtime 保持 | 否 | 保持现状或 blocked，不强行打包 |
| External Skills（12 个） | Onboard | 否/上游相关 | 暂不重新打包 |
| `/sbtd` Commands | OMP Runtime（`src/commands`） | 否 | 保持 |
| Hooks | OMP Runtime（`src/**`） | 否 | 保持 |
| Custom Tools | OMP Runtime（`src/**`） | 否 | 保持 |
| Rule Engine | OMP Runtime/Core | 否 | 保持 |
| Book Gates | OMP Runtime/Core | 否 | 保持 |
| Session State | OMP Runtime | 否 | 保持 |
| Report Renderer | OMP Runtime/Core | 否 | 保持 |
| `onboard.py` | `kit/onboard` | 否 | P0/P1 继续权威实现 |
| Global AGENTS | Kit/Onboard | 否 | 保持 |
| Root Project AGENTS | Kit/Onboard | 跨 Agent 但非 Plugin 标准 | 保持 |
| `.omp/AGENTS.md` | Kit/Onboard | 否 | 保持 |
| GitNexus MCP | Optional Integration Plugin / Onboard | 可 | 不放入 Core 默认包 |
| Playwright MCP | Optional Integration / Onboard | 可 | 后续 |
| Maestro MCP | Optional Integration / Onboard | 可 | 后续 |
| Chrome DevTools MCP | Onboard | 可但非 SBTD Core | 不随核心包自动启用 |

---

# 7. Bundled Skills 改造与 certified set

当前 KPi v0.7 有 15 个 bundled Skill 候选。

## 7.1 术语

- **portable candidate set（13 个）**：首批进入 portability audit 的候选，仅为审计输入。
- **certified set**：13 个候选中**通过全部审计**的子集。只有 certified set 才进入 `generated-agent-plugin/**` 投影、Plugin 根 `skills/**` 和 npm tarball。
- **certifiedCount**：certified set 的实际大小，作为所有计数断言的参数。本文档**不预设 certifiedCount = 13**；任何 "13/13 打包/清理/加载" 的写法都是错误的。

## 7.2 portable candidate set（audit 输入）

| Skill | 审计前建议 |
|---|---|
| `trellis-workflow` | 候选；`compatibility` 声明需要 Trellis CLI |
| `project-validation` | 候选 |
| `web-ui-autotest-generator` | 候选 |
| `gherkin-bdd` | 候选 |
| `knowledge-base-integration` | 候选 |
| `maestro-mobile-e2e` | 候选；声明 Maestro 环境要求 |
| `lessons-record` | 候选 |
| `book-refactoring-pass` | 候选 |
| `book-legacy-change-safety` | 候选 |
| `book-ddd-distilled-modeling` | 候选 |
| `book-ddia-data-design` | 候选 |
| `book-release-readiness` | 候选 |
| `seo-geo` | 候选 |

**M1 审计结果（2026-08-18）**：13 个候选均产生六类审计结论；12 个进入 certified set。`trellis-workflow` 因正文引用 OMP 私有 `.omp/**` 路径与 host-specific `.codex` dispatch 指令，保持 `onboard-owned`，不进入第三树 `skills/**`。`sbtd-workflow-onboard` 与 `trellis-channel` 仍不属于 portable candidate set。

## 7.3 certified set 的认证审计

一个候选进入 certified set，必须同时通过：

1. **语义可移植性审计**：内容不硬编码 OMP-only 命令/私有 Tool/私有路径；
2. **frontmatter 审计**：严格六字段（见第 10 章）；
3. **containment 审计**：reference/script 无 path escape，全部位于 Plugin root 内；
4. **license 审计**：许可证允许随 GPL-3.0-only 包分发，attribution 进入 THIRD_PARTY_NOTICES；
5. **reference/script 审计**：引用的脚本在目标环境可解析、可执行或明确声明缺失降级；
6. **runtime-dependency 审计**：Skill 声明的外部依赖（CLI/服务）用 `compatibility` 显式声明，而非隐式假设。

M1 实现约束：审计器使用 Python 3.10+ 的 `ast` 解析全部 bundled `.py`，从标准库/同目录模块中分离第三方 import，并要求解释器、第三方库同时出现在 `runtimeDependencies` 与 `compatibility`；`.sh` 使用 `bash -n`，`.js` / `.mjs` / `.cjs` 使用 `node --check`。当前候选没有 `.ts` 脚本；在引入 TypeScript parser 前，发现 `.ts` 会使 `reference/script` 审计失败，不得认证。

未通过的候选：

```text
保持 Onboard/Runtime-owned（现状）
或标记 blocked 并记录原因
不进入 generated-agent-plugin/**
不进入 tarball skills/**
```

后续所有章节中的打包数量、Onboard 所有权切换范围、managed cleanup 范围、Doctor 计数、里程碑退出条件、pack 断言，一律以 `certified set` / `certifiedCount` 参数化。

## 7.4 暂留 Runtime/OMP Specific

### `sbtd-workflow-onboard`

当前职责包含平台检测、AGENTS、OMP MCP、全局工具安装、多项目事务和 `onboard.py`，不适合作为真正的跨 Agent portable Skill。

推荐：

```text
canonical implementation
→ src/** runtime + kit/onboard

可选说明 Skill
→ 未来单独评估的 skills/sbtd-onboard-guide
```

### `trellis-channel`

当前 Channel 行为高度依赖 Agent Runtime 的多 Agent/worker/forum/thread 能力。

推荐：

```text
P0:
  保留 OMP-specific

P2/P3:
  拆为 portable collaboration policy
  +
  runtime-omp channel adapter
  +
  runtime-pi adapter
```

---

# 8. 为什么 Core Plugin 暂不直接带 `mcp.json`

把 GitNexus 等直接放进核心包的 `mcp.json`，会让它成为插件发现的一部分；这与现有 SBTD 的以下边界冲突：

- GitNexus MCP 必须用户选择；
- configured ≠ callable；
- MCP 不应该因为插件安装而静默启用；
- Playwright/Maestro/Chrome DevTools 也属于条件能力；
- `/sbtd on` 不执行环境安装。

因此 P0 推荐：

```text
Core omp-sbtd
  → plugin.json
  → certified portable Skills
  → 无 mcp.json
```

MCP 继续：

```text
/sbtd onboard plan
  ↓
用户明确选择
  ↓
/sbtd onboard init/reset
  ↓
OMP user MCP config
```

---

# 9. Portable MCP 的第二阶段方案

为了利用 Agent Plugins 的 MCP portability，可以新增独立 Integration Plugins。

## 9.1 GitNexus Integration Plugin

```text
sbtd-gitnexus/
├─ plugin.json
└─ mcp.json
```

`plugin.json`：

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "sbtd-gitnexus",
  "version": "<next-approved-version>",
  "description": "Optional GitNexus MCP integration for SBTD workflows."
}
```

`mcp.json`：

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "gitnexus": {
      "type": "stdio",
      "command": "gitnexus",
      "args": ["mcp"]
    }
  }
}
```

该改造是独立的后续决策（post-P0），不与第一轮 Agent Plugins 迁移同时完成。

---

# 10. Agent Skills Frontmatter 严格化

推荐统一：

```yaml
---
name: gherkin-bdd
description: Maintain behavior specifications and traceability using Gherkin feature files.
license: Apache-2.0
compatibility: Requires filesystem access to the target repository.
allowed-tools: read grep glob bash
metadata:
  sbtd.category: behavior
  sbtd.portable: "true"
---
```

`license` 表示该 Skill 投影自身的来源许可证，不等同于外层 npm 包的 `GPL-3.0-only`。当前 certified set 来源经 audit 识别为 Apache-2.0；外层 GPL 包通过保留每项 `LICENSE` / `NOTICE` 与根 `THIRD_PARTY_NOTICES.md` 满足归属要求。不得把来源 Apache-2.0 误标成 GPL。

只允许：

```text
name
description
license
allowed-tools
metadata
compatibility
```

因此当前 Skill 中如存在：

```text
globs
alwaysApply
hide
disableModelInvocation
enabled
```

不能继续放在 portable `SKILL.md` frontmatter 中。这些 OMP-only 字段在投影时由 Workflow Kit 剥离并转写入 Runtime 侧的 policy registry（见第 11 章）。

---

# 11. OMP-specific Skill Metadata 外置

例如新增（Runtime 侧，随 `src/**` 或 kit 分发）：

```text
skill-registry.yaml
```

```yaml
skills:
  gherkin-bdd:
    activation:
      routes:
        - feature
        - bugfix
      predicates:
        - userVisibleBehavior
    requiredFor:
      - bdd-required-for-visible-behavior

  book-release-readiness:
    activation:
      predicates:
        - productionPathRisk
    requiredFor:
      - release-gate-before-complete
```

形成：

```text
SKILL.md
→ portable knowledge/workflow

skill-registry.yaml
→ OMP/KPi runtime routing policy 映射
```

**边界声明**：Runtime policy registry 描述的是"哪个 route/predicate 下哪个 Skill 是相关/必需"的**策略映射**。它不是 Host 的 Skill discovery 事实源，也不声称模型实际调用了哪个 Skill。Host 侧的发现（discovered）、选择/调用（selected/invoked）状态只能由 Host API 证明；当 Host API 无法证明时，Doctor/Report 必须输出 `source-unverified` 或等价状态（见第 22 章）。

---

# 12. Skill 内容可移植性规则

Portable Skill 中避免硬编码：

```text
必须执行 /sbtd ...
必须调用 OMP 某私有 Tool
必须读取 ~/.omp/...
必须调用某 OMP Extension API
```

改为：

```text
如果宿主 Runtime 提供 SBTD state，则遵循其 gate state。
如果对应工具可调用，则使用；否则报告 blocked/skipped。
```

需要 Runtime-specific 细节时使用 reference：

```text
skills/trellis-workflow/
├─ SKILL.md
└─ references/
   ├─ generic.md
   └─ omp.md
```

---

# 13. 第三方 External Skills 的处理

当前 Onboard 管理的 External Skills 共 **12 个**（以 Workflow Kit `generated-omp/**` 的 stable 资产为准）：

- `diagnosing-bugs`
- `tdd`
- `grill-me`
- `grill-with-docs`
- `grilling`
- `domain-modeling`
- `codebase-design`
- `handoff`
- `writing-for-agents`
- `to-spec`
- `to-tickets`
- `ui-ux-pro-max`

`impeccable` / `shadcn` **不是**当前 Onboard catalog 条目；它们属于可选的 Host 能力（若宿主环境已提供则可使用），不纳入本方案的安装、迁移或计数范围。

P0 不建议把这 12 个复制进 `@kunolu/omp-sbtd/skills/`。

原因：

1. 上游版权/License；
2. 更新节奏不同；
3. 可能不符合 Agent Skills strict schema；
4. 重新打包会造成版本漂移；
5. 当前 Onboard 已有 upstream/stable transaction。

继续：

```text
Onboard
  → resolve upstream/stable
  → validate
  → install
  → runtime discovery
```

P1 以后若上游本身发布 Agent Plugin，则优先直接安装上游 Agent Plugin。

---

# 14. 三层 AGENTS 保持原设计

## Global

```text
$PI_CODING_AGENT_DIR/AGENTS.md
默认 ~/.omp/agent/AGENTS.md
```

继续承载 Always-on、SBTD Mode Contract、真实性、安全和高层工具职责。

## Root Project

```text
<project-root>/AGENTS.md
```

继续承载 Project Facts、Commands、Validation、BDD conventions、Trellis、Paths、Cross-repo facts、Protected paths。

## OMP Adapter

```text
<project-root>/.omp/AGENTS.md
```

继续：

```markdown
@../AGENTS.md
```

以及 Runtime Marker Contract、enforced/advisory overlay、Tool Evidence Contract 和 OMP-specific project behavior。

---

# 15. `/sbtd on/off` 不受 Agent Plugins 影响

Skill 生命周期状态必须分开表述，不可混用：

```text
packaged            随 tarball 分发（certified set）
discovered          Host 加载并列出该 Skill（Host 可证明）
selected / invoked  模型在某次交互中选择/调用了该 Skill（Host 可证明）
required gate satisfied  Runtime 判定该 Skill 对应的必需门槛已满足（Runtime 可证明）
```

Agent Plugins 的 `skills/` 目录和 tarball inventory 只能直接证明 `packaged`；`discovered` 必须由 Host 实际加载与列举结果单独证明。**不存在确定性的“自动激活”**：模型是否使用某个 Skill 由模型可见性（model-visible）与人工调用（`/skill:*` 等 manual invocation）决定；Runtime 通过 Runtime Marker 与三层 AGENTS 中的 route guidance 提供“当前 route/stage 下哪个 Skill 相关/必需”的提示，并通过 required gate 判定结果是否满足。Runtime policy registry（第 11 章）只是该策略的映射表，不是 Host discovery 或模型调用的事实源。

## `/sbtd on`

仍然：

```text
Preflight
  → managed / needs-onboard / degraded / blocked
  → runtime-mode=enforced（目标模式）
  → runtime marker 注入
  → classifier
  → route
  → gates
  → route guidance（经 Runtime Marker / AGENTS 提示相关/必需 Skill）
```

## `/sbtd off`

仍然请求：

```text
runtime-mode=advisory
```

停止：

- auto classification；
- auto route；
- Book Gates；
- route guidance 注入；
- SBTD delivery enforcement。

保留：

- AGENTS；
- Skills 的 model-visible/manual invocation；
- project facts；
- OMP native safety；
- 手动 `/skill:*`。

---

# 16. Runtime Marker 保持

继续由 OMP extension 在主要 Turn 注入（当前契约字段）：

```xml
<sbtd-runtime
  state-version="1"
  kit-revision="c4d57837545ccde0dc767701b16d328dc7914a871f3ac4bf5d533cf6e757b80c"
  runtime-mode="advisory"
  policy-profile="strict"
  environment-mode="needs-onboard"
  effective-control-state="advisory"
  route="auto"
  stage="intake" />
```

字段语义：

- `runtime-mode`：用户/配置**请求**的模式（`enforced` / `advisory`）。
- `effective-control-state`：Preflight 之后**实际生效**的控制状态，仅为 `advisory` / `active` / `preflight-only` / `blocked`。

这两个字段必须保持区分：请求 `enforced` 时，`managed` / `degraded` 环境得到 `active`，`needs-onboard` 得到 `preflight-only`，blocked 环境得到 `blocked`；任何消费方不得把 `runtime-mode` 或 `environment-mode` 当作实际控制状态。其余字段（`state-version`、`kit-revision`、`policy-profile`、`environment-mode`、`route`、`stage`）按当前 Runtime 契约原样保留。

Agent Plugins 不负责生成或解释这个 Marker。

---

# 17. Book Gates 保持 Runtime-owned

以下 Gate 不迁入 Skill 自身状态：

```text
DDD Boundary Review
DDIA Data Design Review
Legacy Change Safety Review
Refactoring Review
Release Readiness Review
```

Skill 负责：

```text
如何评审
检查什么
如何输出
```

Runtime 负责：

```text
什么时候必须评审
是否允许进入下一阶段
当前 gate state
是否可以 edit/deliver
```

即：Skill 被 packaged/discovered/invoked 都不等于 required gate satisfied；后者只能由 Runtime 的 gate state 证明。

---

# 18. `grill-with-docs` 多轮交互

Agent Plugins 迁移不会改变 `grill-with-docs` 的交互性质。

正确职责：

```text
grill-with-docs Skill
  ↓
提供需求澄清方法

OMP/SBTD Runtime
  ↓
控制多轮 Session
  ↓
记录 DDD Boundary Gate
  ↓
决定何时可以 specification
```

因此不要把多轮状态写进 portable Skill。

---

# 19. Trellis 集成

`trellis-workflow` 可以 portable，但 Trellis lifecycle enforcement 仍归 Runtime。

```text
Portable Skill
  → 如何使用 Trellis

Runtime
  → 是否应该使用 Trellis
  → 是否存在强证据
  → before-dev/check/finish-work 是否满足
  → 是否允许推进 Stage
```

普通任务继续禁止自动：

```text
trellis init
```

Onboard 例外保持不变。

---

# 20. GitNexus 集成

GitNexus 的强证据规则继续：

```text
GitNexus MCP callable
AND
project index valid/current
```

才可以使用。

Agent Plugin MCP 的"已发现"仍然不等于：

```text
callable
```

因此 Tool Evidence 继续记录：

```text
configured
discovered
connected
callable
index-current
branch-match
```

---

# 21. Playwright / Maestro

这些能力优先继续保持：

```text
Skill → portable（若通过 certified set 审计）
CLI → project/runtime
MCP → optional integration
```

例如：

```text
web-ui-autotest-generator
→ portable skill（audit 通过后）

Playwright CLI
→ 项目 dependency

Playwright MCP
→ optional Agent Plugin / Onboard config
```

同理：

```text
maestro-mobile-e2e
→ portable skill（audit 通过后）

Maestro CLI
→ environment dependency

Maestro MCP
→ optional integration
```

---

# 22. Onboard 改造

P0 的 `onboard.py` 继续权威。

但 Doctor/Plan 需要新增 Agent Plugins 状态。

## 22.1 Doctor 新增字段

```text
Agent Plugin:
  schema: 1.0.0
  manifest: valid | invalid | missing
  portableSkills:
    packaged: certifiedCount        ← 随 tarball 分发的 certified set 大小
    discovered: <Host 证明的数量>   ← 仅当 Host API 可证明，否则 source-unverified
    invalidSkills: [...]
  portableMcp: absent | valid | invalid
  ompRuntimeExtension: loaded | missing | incompatible
```

## 22.2 `/sbtd doctor` 输出建议

```text
OMP Runtime
  version: 17.3.5 (exact)
  agent-plugins: supported

omp-sbtd
  plugin.json: valid
  packaged portable skills: <certifiedCount>
  discovered portable skills: <count> | source-unverified
  runtime extension: loaded
  command registry: loaded

AGENTS
  global: effective
  root project: effective
  omp adapter: effective

Optional Integrations
  GitNexus MCP: configured-only | callable | unavailable
  Playwright MCP: ...
```

Doctor 只报告**已证明**的状态：

- `packaged` 及其数量由 tarball（或已安装 package）的 `skills/**` inventory、Skill validation 与 projection digest report 共同证明；`plugin.json` 只证明 manifest identity/schema/version，不证明 Skill 数量；
- `discovered`、`selected/invoked` 只能由 Host API 证明；
- 当 Host API 无法证明 Skill 的 resolved source 时，输出 `source-unverified`（或等价状态），**不得**用 Runtime policy registry 的内容冒充 discovery 事实；
- required gate 状态由 Runtime gate state 证明，与 Skill 的 packaged/discovered/invoked 状态分开报告。

---

# 23. Plugin 安装仍保持零副作用

继续保持现有原则：

```bash
omp plugin install --scope project @kunolu/omp-sbtd@<version>
# 或本地 tarball：
omp plugin install --scope project ./kunolu-omp-sbtd-<version>.tgz
```

只允许改变：

- OMP plugin registry；
- plugin cache；
- package files；
- plugin-owned state。

不得：

- 写 Global AGENTS；
- 写 Project AGENTS；
- 修改 `.omp/AGENTS.md`；
- 安装 Trellis；
- 安装 GitNexus；
- 安装 Playwright；
- 安装 Maestro；
- 写 OMP MCP；
- 登录 Provider；
- 修改 Model Roles；
- 自动运行 `gitnexus analyze`；
- 自动 `trellis init`。

---

# 24. 安装与使用流程

## 24.1 用户安装（npm tarball，P0 唯一分发渠道）

```text
1. OMP 精确 17.3.5

2. omp plugin install --scope project @kunolu/omp-sbtd@<version>
   （或已下载的 .tgz）

3. /reload-plugins
   或启动新 Session

4. /sbtd doctor

5. /sbtd onboard plan

6. 用户确认

7. /sbtd onboard init

8. 新 Session

9. /sbtd on
```

## 24.2 本地开发

```bash
omp --plugin-dir /absolute/path/to/omp-sbtd
```

修改：

```text
plugin.json
skills/（应改投影源，而非手改产物）
src/**（commands/hooks/tools/runtime 逻辑）
```

后：

```text
/reload-plugins
```

验证：

```text
/sbtd doctor
/mcp list
/skill:<name>
```

注意：本地 workspace install 用于开发调试，**不能替代** clean exact-host artifact 验证（见第 28 章）；发布断言必须在干净工作树的 tarball 上完成。

---

# 25. Marketplace 发布（optional，post-P0）

Marketplace 属于 OMP 分发层，不属于 Agent Plugins 标准。**P0 不使用 Marketplace**；它是 P0 之后的可选分发渠道决策。

若未来启用，推荐布局（保留 `.omp-plugin/marketplace.json` 约定）：

```text
kpi-marketplace/
├─ .omp-plugin/
│  └─ marketplace.json
└─ plugins/
   ├─ omp-sbtd/
   │  ├─ plugin.json
   │  ├─ skills/
   │  ├─ src/
   │  ├─ dist/
   │  └─ kit/
   └─ sbtd-gitnexus/
      ├─ plugin.json
      └─ mcp.json
```

安装（使用实际 CLI 语法）：

```bash
omp plugin marketplace add <source>
omp plugin install --scope project omp-sbtd@<marketplace>
```

以后选择 GitNexus portable integration：

```bash
omp plugin install --scope project sbtd-gitnexus@<marketplace>
```

---

# 26. OMP-specific 与 Portable Ownership

建议定义：

```text
plugin.json
skills/（生成投影）
  = Portable Ownership

src/** → dist/
kit/
scripts/ test/ features/ docs/
  = OMP/KPi Ownership
```

规则：

- Agent Plugins loader 管 `skills`；
- 不再让 legacy OMP loader 重复加载同一个 Skill；
- OMP Runtime extension 继续处理 commands/hooks/tools 等非 portable surface（实现在 `src/**`，无独立根目录）；
- 不创建同名双份 Skill。

---

# 27. `catalog.json` 调整

当前 Kit Catalog 建议增加 portability 元数据。

Portable 候选：

```json
{
  "id": "gherkin-bdd",
  "kind": "bundled-skill",
  "portable": true,
  "agentSkillsConformant": true,
  "certification": "pending | certified | failed",
  "target": "skills/gherkin-bdd"
}
```

`certification` 由 audit 结果写入；只有 `certified` 的条目进入 `generated-agent-plugin/**` 投影与 tarball。catalog 中 `portable: true` 的条目数是候选数（≤13），certified 条目数是 `certifiedCount`，两者不得混用。

OMP-only：

```json
{
  "id": "trellis-channel",
  "kind": "runtime-skill",
  "portable": false,
  "reason": "Requires OMP-specific channel runtime"
}
```

第三方：

```json
{
  "id": "grill-with-docs",
  "kind": "external-skill",
  "portable": "upstream-dependent"
}
```

---

# 28. CI / Conformance Pipeline（静态门为发布前置；Host 可选）

CI/Conformance 的**静态门**（manifest / skill / containment / pack / SBOM）是 portable projection 发布前置条件（M4 出口，见第 34 章）。

- 第 28.4 节 **Host 项是可选项**，不是 M4 出口或后续开发的必需验证。未跑不得标 passed，也不得因未跑 Host 阻断开发。
- 若项目 CI 尚未接入静态门 pipeline，可用证据仅限 **local clean-worktree**，且 portable projection 的**晋升保持 blocked**。本地静态门可结束 M4，不能替代 CI release gate；CI 落地并复跑通过后方可解除晋升阻断。
- 任何 tarball 发布断言不得在 dirty worktree 或本地 workspace install 上做出（与是否跑 Host 无关）。

Agent Plugins Gate：

```text
build（clean worktree）
  ↓
validate plugin.json
  ↓
validate certified SKILL.md 集合
  ↓
validate package containment
  ↓
validate optional mcp.json（Integration Plugins）
  ↓
pack tarball
  ↓
clean exact-host（OMP 17.3.5）安装验证（可选）
  ↓
OMP discovery test（可选）
  ↓
OMP runtime extension test（可选）
  ↓
SBTD conformance（Host-observable 项可选）
  ↓
Onboard regression（Host 项可选）
  ↓
integration test
```

## 28.1 Manifest Gate

必须验证：

- `$schema` 精确为 1.0.0；
- name 合法（`omp-sbtd`）；
- 无非法顶层字段；
- version/description/license 类型正确；
- **`plugin.json.version` 与 `package.json.version` 完全一致**。

## 28.2 Skill Gate

certified set 中每个 portable Skill：

- 目录名 = frontmatter.name；
- name lowercase；
- 不含 `--`；
- description 必填；
- 只允许六个标准字段；
- metadata value 全部 string；
- `allowed-tools` 为 string；
- 无 path escape；
- reference/script 仍位于 plugin root；
- 内容 digest 与 projection report 一致（digest-verified）。

## 28.3 MCP Gate

若某 Integration Plugin 有 `mcp.json`：

- schema 精确；
- stdio command 只能 bare executable 或 `./relative`；
- `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` 仅在规范允许的位置；
- 不允许覆盖保留 env；
- 非 loopback `http://` 拒绝；
- remote 应用 HTTPS；
- header 不含换行/control chars；
- 不把 secret 写进 package。

## 28.4 Clean exact-host tarball 验证清单

对从 clean worktree 打出的 tarball。前四项与最后一项是**静态门**（不需要 Host）。中间 Host 项是**可选项**：有独立授权 isolated OMP 17.3.5 时才跑；未跑记 `not-run`，不得记 passed，也不得阻断任何步骤。

```text
[ ] manifest schema 校验通过
[ ] plugin.json.version == package.json.version
[ ] skills/ 数量 == certifiedCount，且每个 digest 与 projection report 一致
[ ] containment：tarball 内无 path escape，reference/script 均在 plugin root
[ ] omp plugin install --scope project <tarball> 成功
[ ] plugin list / /sbtd doctor 显示 manifest valid、packaged=certifiedCount
[ ] /reload-plugins 或新 Session 后 Host 可发现 certified Skills（或如实报 source-unverified）
[ ] 手动 /skill:<name> 调用 certified Skills 正常
[ ] /sbtd on/off/help/status 行为无回归（runtime-mode 与 effective-control-state 正确区分）
[ ] Skill 碰撞/所有权迁移：同名 Skill 无双份加载，legacy→portable 切换无残留
[ ] 安装过程零静默副作用：不写 project 文件、不装 MCP、不装工具
[ ] uninstall/rollback 后环境恢复到安装前状态
[ ] SBOM.spdx.json / THIRD_PARTY_NOTICES.md / LICENSE / SECURITY.md 随包且内容正确
```

---

# 29. SBTD Conformance Test

Agent Plugins 改造后必须证明工作流行为没有改变。

| 场景 | 预期 |
|---|---|
| `/sbtd off` | Skill 仍可 model-visible/手动调用，但无 Gate、无 route guidance |
| `/sbtd on` | Runtime Marker/AGENTS 注入 route guidance；Host 已发现的 certified Skills 继续 model-visible，但 route guidance 不证明模型已选择或调用 |
| missing current-route required certified Skill | 对应的 Required Gate 保持 blocked；缺少无关 Skill 不得泛化为该 Gate blocked |
| invalid Skill frontmatter | Doctor 显示明确失败 |
| Agent Plugin manifest invalid | 不进入 managed |
| Root Project AGENTS missing | degraded |
| `.omp/AGENTS.md` missing | needs-onboard/degraded |
| GitNexus plugin discovered but MCP unavailable | 不声称 callable |
| GitNexus MCP callable but index missing | 不执行 Impact |
| Host 无法证明 Skill resolved source | Doctor/Report 输出 source-unverified，不冒充 discovered |
| BDD-visible behavior | 仍触发 Feature Gate |
| Book Gate 未通过 | 仍阻止生产代码编辑 |
| mock-backed test | 仍不能标记 full-stack |
| report artifact missing | 仍 block delivery |


# 30. Compatibility Matrix

迁移目标为**精确 OMP 17.3.5**：

| OMP | 行为 |
|---|---|
| `≠ 17.3.5` | 不满足 peer 约束；迁移后 artifact 不承诺可用，Runtime 启动时提示版本不匹配 |
| `17.3.5`（exact） | 迁移目标与验证基线，Agent Plugins 1.0.0 路径在此版本上认证 |
| 其他版本（含更宽 range） | **不属于本迁移**；range 放宽是独立的认证/晋升决策，仅由 `docs/assets/omp/omp-plugin-compatibility-decoupling-plan.md` 治理 |

P0 不建议为了兼容旧 OMP 长期维护两份 Skills。

> 历史说明（非目标）：Agent Plugins 1.0.0 支持最早出现于 17.2.x 系列；本方案不针对该系列做任何迁移断言。

---

# 31. Versioning

三个版本独立管理，但 plugin 版本只有一个事实源：

```text
omp-sbtd version          = plugin.json.version == package.json.version（同一 artifact，必须相等）
SBTD Kit revision         = 640-skills / Workflow Kit 固定 revision（当前 4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb）
Agent Plugins schema      = 1.0.0
```

例如 `/sbtd status` 输出：

```text
Plugin: 0.1.0-rc.12
Kit: <sha>
Agent Plugins: 1.0.0
OMP: 17.3.5 (exact)
```

规则：

- `0.1.0-rc.12` 已在 M2 写入 `plugin.json` 与 `package.json`。可认证 tarball 冻结点在 M3 切流之后；M4 认证该精确版本的 post-M3 包，M5 不再改写版本。任何版本号变更都会产生新 artifact，必须回到 M2 并重新执行 M3–M4。
- Kit revision 与 Agent Plugins schema version 独立跟踪，不随 plugin 版本变化。
- Host 兼容性事实只在 `package.json` `peerDependencies`（精确 17.3.5）与 Runtime 启动期检查中声明；manifest 不重复。

---

# 32. 上游 `640-skills` 同步流程与 portable 投影路径

现有 Section Mapping 保持。统一的 portable 投影路径（唯一）：

```text
640-skills upstream（pin SHA；当前 resolved 4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb）
  ↓
packages/sbtd-workflow-kit
  ├─ 现有：AGENTS Section Mapping → generated/**（三目标 AGENTS 等）
  ├─ 现有：OMP 投影 → generated-omp/**
  └─ 新增：
       Skill Portability Audit（六类审计，产出 certified set）
       ↓
       Agent Skills Frontmatter Transform（剥离 OMP-only 字段 → runtime policy registry）
       ↓
       audited portable projection → generated-agent-plugin/**
       ↓
       Plugin 根 skills/**（打包阶段物化复制，digest 校验；不使用手工编辑或跨包 symlink）
  ↓
Conformance（clean exact-host tarball 验证）
  ↓
publish（npm tarball）
```

所有权与变更要求：

- **`packages/sbtd-workflow-kit` 必须在未来实施中变更**：新增 `generated-agent-plugin/**` 投影目标、portability audit、frontmatter transform、digest/report 产物，以及 catalog 的 `certification` 元数据。这是本迁移的必备工程，不是可选项。
- **`640-skills` 上游变更是有条件的**：只有当 audit 发现上游 Skill 内容本身不满足可移植性（如硬编码 OMP-only 措辞、frontmatter 非法）且无法在 transform 层修复时，才提交上游变更。
- **`generated/**`、`generated-omp/**`、`generated-agent-plugin/**`、`vendor/**`、插件内 `kit/**` 与根 `skills/**` 均为 promotion-owned 产物**：由生成/晋升流水线产出并 digest 校验，**任何人不得手工编辑**；要改内容只能改源（640-skills / transform / overlay）后重新生成。
- Plugin 根 `skills/**` 与所有生成投影均为 build-owned：打包时校验其 digest 与 `generated-agent-plugin/**` 一致。

新增 `sync-report` 内容：

```text
portableCandidates: 13
certifiedSet:
  added / changed / removed / invalid / ompSpecific
certifiedCount: <n>
```

---

# 33. 不要把 Runtime Rule 塞回 Skill

例如：

```text
BDD 是必须的
```

可以写在 Skill 中解释。

但真正的：

```text
没有 Feature → 禁止 completed
```

必须继续在 Rule Engine。

同理：

- GitNexus 需要 MCP + index；
- report artifact required；
- release gate；
- secret read guard；
- install requires approval；

都继续 machine-enforced。

---

# 34. P0 改造阶段（Milestones）

里程碑按依赖顺序重排；每个里程碑的计数断言一律以 `certified set` / `certifiedCount` 参数化。

## M0 — Freeze Clean Baseline

- 冻结当前 git revision 并记录工作树 dirty/clean 状态（当前 dirty revision 必须显式冻结后方可开工）；
- 固定 `640-skills` pin 与 Workflow Kit revision（当前 `4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb`）；
- 固定精确 OMP `17.3.5` 作为 Host；
- 导出 15 个 bundled 候选 digest、12 个 Onboard external skills 清单、command/gate tests 基线。

退出条件：

```text
baseline reproducible（clean worktree 可重建同一 tarball 与 digest 集合）
```

**实施状态（2026-08-18）**：已完成。冻结记录位于 `.trellis/tasks/archive/2026-08/08-18-agent-plugins-m0-m1/research/baseline.md`；M1 开始时未改变冻结 Kit identity。任务已归档。

## M1 — Workflow Kit Portable Audit / Projection

- `packages/sbtd-workflow-kit` 新增 portability audit、frontmatter transform、`generated-agent-plugin/**` 投影、catalog `certification` 元数据与 digest report；
- 13 个 portable candidates 全部完成六类审计，产出 certified set；
- 未通过项保持 Onboard/Runtime-owned 或标记 blocked，并记录原因。

退出条件：

```text
generated-agent-plugin/** 可复现生成
certifiedCount 与 digest report 稳定
（不要求 certifiedCount == 13）
```

**实施状态（2026-08-18）**：已完成并归档于 `.trellis/tasks/archive/2026-08/08-18-agent-plugins-m0-m1/`。`transformVersion=agent-plugin-p0-v1`，`candidateCount=13`，`certifiedCount=12`，`generatedSha256=e97e283c9ff205d6658ff68e4afe2f86a4a4250642b942091c1d9658913696e4`。

## M2 — Hybrid Package Assembly

- 在 M2 输入端批准并冻结版本（历史输入曾写作 `<next-approved-version>`；现已冻结为 `0.1.0-rc.12`），同步写入 `package.json` 与根 `plugin.json`；不得把未解析占位符带入 tarball；
- 打包阶段把 `generated-agent-plugin/**` 投影到根 `skills/**`（build-owned、digest-verified）；
- npm files 白名单纳入 `skills/**` 与 `plugin.json`；
- 不改 commands/hooks/tools/runtime 逻辑，不新增 P0 根目录。

退出条件：

```text
clean worktree 打出的 tarball 通过 manifest/skill/containment gate
plugin.json.version == package.json.version
skills/ 数量 == certifiedCount
```

**实施状态（2026-08-18）**：已完成并归档于 `.trellis/tasks/archive/2026-08/08-18-assemble-hybrid-plugin-m2/`。冻结版本 `0.1.0-rc.12`；根 `plugin.json` 与 12 个 certified `skills/**` 已进 Plugin pack；`kit/**` 仍只嵌入 `generated-omp/**`。

## M3 — OMP / Onboard Certified-Set Ownership Cutover

- Agent Plugins provider 接管 certified set 的加载；legacy loader 不再重复加载同名 Skill；
- Onboard managed cleanup 只针对 certified set 对应的旧安装位置（按 certifiedCount 参数化，不做全量 13 项清理假设）；
- `sbtd-workflow-onboard` 退出 portable list；`trellis-channel` 标记 OMP-specific；
- runtime policy registry 成为 route guidance 策略事实源（非 Host discovery 事实源）；
- Doctor 显示 source=agent-plugins 或 source-unverified；Report 记录 Skill source 与 gate 证明。

退出条件：

```text
portable 与 runtime ownership 无重叠
certified set 所有权切换完成且可回滚
```

**实施状态（2026-08-19）**：已完成并归档于 `.trellis/tasks/archive/2026-08/08-18-cutover-certified-skill-ownership-m3/`。工作提交 `20896d1` / `9d152e4` / `08dfabe`。当前代码事实：`package.json` 与 `plugin.json` 均为 `0.1.0-rc.12`；根 `skills/**` 12 个 certified 目录；OMP overlay / generated-omp / kit catalog 仅保留 3 个 bundled-skill + 12 个 external-skill；无根 `mcp.json`；Runtime 从 packaged `skills/**` 读 certified 证据，`invalidSkills` 不回落全局；composite leftover cleanup 先于 external installer；`/sbtd doctor` 在成功与环境观察失败路径都输出 Agent Plugin 块，`discovered=source-unverified`。可认证 tarball 必须在本切流之后的 clean worktree 上重打（M4 已用 `ec849c62…` 打出）。Host-proven discovered / exact-host collision 现为 28.4 **可选**项（`not-run`），不再作为 M4 必需尾项。


## M4 — Integrated Conformance（静态门必需；Host 可选）

- 必需：第 28.1–28.3 与 28.4 静态门（manifest / version / certifiedCount+digest / containment / SBOM）；
- 可选：第 28.4 Host 项与第 29 节 Host-observable 项。未跑记 `not-run`，不得记 passed，也不得因此阻断 M4 出口或后续开发；
- 不得把未跑的 Host 写成 exact-host certified；
- CI 未接入时 **portable projection 晋升**保持 blocked（M5 决策可开始）。晋升 ≠ npm RC 发布；RC/stable 能否 `npm publish` 只看 `docs/assets/omp/omp-plugin-host-acceptance.md` 第 3–4 节。

退出条件：

```text
静态门通过；Host 项为 not-run 或 passed（不得用 blocked 冒充 passed）
```

**实施状态（2026-08-20）**：静态门已通过。tarball `kunolu-omp-sbtd-0.1.0-rc.12.tgz`（clean `ec849c62…`，SHA-256 `49edb4b7…`）。28.4 Host / §29 Host-observable = `not-run`（可选）。任务 `.trellis/tasks/archive/2026-08/08-19-exact-host-certify-post-m3-rc12/` 已归档。不得表述为 exact-host certified。M5 已发布该 tarball 到 `next`；**无 CI，晋升 blocked**。


## M5 — Release Decision

- 依据 M0–M4 **静态**证据做是否发布的决策；不要求 28.4 Host；
- **CI 未接入则不得把本地静态结果写成已晋升**；npm RC/stable 发布门槛只在手册第 3–4 节（含第 4 节四命令），不含 28.4 Host，也不把 CI 晋升写成手册发布条件。
- 如需修改版本号或 portable 布局，必须回到 M2，并重跑 M3 与 M4 静态门；Host 仍可选；
- Marketplace、optional MCP Integration Plugins、peer-range widening 均为 M5 之后的**独立后续决策**，不在本 P0 内承诺。

**实施状态（2026-08-20）**：已完成。决策为发布 RC。同一冻结 tarball 已以 `next` 发布；Registry 身份复核 passed；`latest` 仍为 `0.1.0-rc.2`。手册第 4 节全收。任务 `.trellis/tasks/08-20-m5-publish-omp-sbtd-rc12/`。不得表述为 exact-host certified 或 CI-promoted。

---

# 35. P0 ROADMAP 调整建议

原 P0：

```text
OMP-hosted SBTD MVP
```

不变。

新增内部泳道：

```text
P0-A Agent Plugins Portable Skills（certified set）
P0-B OMP Runtime Control Plane
P0-C Onboard/AGENTS Compatibility
P0-D CI/Conformance（前置，非 backlog）
```

### P0-A Exit

- Agent Plugin manifest valid；
- certified Skills 全部 standard-conformant（certifiedCount 参数化，不要求等于候选数）；
- `/skill:*` 手动调用可用；
- route guidance 正确注入（Runtime Marker/AGENTS）；
- no duplicate skill discovery。

### P0-B Exit

- `/sbtd on/off/help/status/doctor` 无回归；
- Gate 无回归；
- Resume/Compaction 状态恢复；
- plugin runtime version check（精确 17.3.5）。

### P0-C Exit

- 三层 AGENTS unchanged；
- Managed Block unchanged；
- Onboard transaction unchanged；
- Doctor 新增 Agent Plugin status（含 source-unverified 语义）。

### P0-D Exit

- 第 28 章**静态门**在 clean worktree 上通过；
- 28.4 Host 清单为可选项，不是本泳道出口。

Marketplace、optional MCP plugins（GitNexus 等）、peer-range widening、`latest`/stable 及其他 dist-tag 均不列入 P0 泳道出口，作为 M5 之后的独立决策跟踪。本 RC `@kunolu/omp-sbtd@0.1.0-rc.12` 已发到 `next`；不得写成 CI-promoted 或 exact-host certified。

---

# 36. 安全边界

## Package Boundary

任何：

```text
SKILL.md
reference
script
plugin.json
mcp.json
```

不得 symlink/path escape 出 Plugin Root。

## Secret

不得在：

```text
plugin.json
SKILL.md
mcp.json
headers
README
reports
```

写真实 Secret。

## MCP

remote MCP：

```text
non-loopback → HTTPS
```

stdio：

```text
command
→ bare executable
或
→ ./plugin-relative
```

---

# 37. `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` 使用原则

## `${PLUGIN_ROOT}`

用于 immutable package assets：

```text
references
scripts
bundled executables
templates
```

## `${PLUGIN_DATA}`

用于 persistent mutable state：

```text
cache
index
database
downloaded metadata
generated state
```

不要写：

```text
PLUGIN_ROOT/cache.db
```

应写：

```text
PLUGIN_DATA/cache.db
```

---

# 38. `omp-sbtd` 自身是否需要 `PLUGIN_DATA`

Core Plugin 初期不建议把 SBTD Session State 放到 `${PLUGIN_DATA}`。

原因：

- Session State 已由 OMP Runtime 管理；
- Resume/Branch/Compaction 需要和 Session 生命周期绑定；
- 插件 data dir 更适合 MCP/subprocess 的 durable state。

可用于：

```text
portable integration cache
non-session plugin cache
migration metadata
```

---

# 39. Local Development Checklist

每次修改 portable layer（应改投影源，而非手改 `skills/**` 产物）：

```text
[ ] plugin.json schema
[ ] skill frontmatter
[ ] skill directory/name
[ ] no OMP-only frontmatter
[ ] no path escape
[ ] no secrets
[ ] OMP discovery（Host 可证明；否则 source-unverified）
[ ] /skill manual invocation
[ ] route guidance 注入正确（Runtime Marker / AGENTS）
[ ] /reload-plugins
```

每次修改 runtime layer：

```text
[ ] /sbtd help
[ ] /sbtd on
[ ] /sbtd off
[ ] /sbtd status
[ ] /sbtd doctor
[ ] gate tests
[ ] resume
[ ] compaction
[ ] onboarding boundaries
```

---

# 40. Release Checklist

发布前（在 clean worktree 与精确 17.3.5 Host 上）：

```text
Agent Plugins
[ ] schema 1.0.0
[ ] manifest valid
[ ] plugin.json.version == package.json.version
[ ] certified skills 全部 valid，数量 == certifiedCount，digest 一致

OMP
[ ] exact 17.3.5 tested
[ ] commands registered
[ ] hooks loaded
[ ] tools loaded

SBTD
[ ] classifier golden tests
[ ] gates
[ ] BDD
[ ] Trellis
[ ] GitNexus evidence
[ ] report truthfulness

Onboard
[ ] plan read-only
[ ] init confirmation
[ ] reset rollback
[ ] managed blocks
[ ] external skills transaction
[ ] certified-set ownership cutover 与 cleanup（按 certifiedCount 参数化）

Security
[ ] no secrets
[ ] path containment
[ ] no silent MCP/install
[ ] SBOM / licenses / notices 随包
```

---

# 41. 推荐的最终架构图

```text
                ┌──────────────────────────────┐
                │  npm registry（P0 唯一渠道）  │
                │  immutable tarball           │
                │  ── Marketplace（optional    │
                │     post-P0，独立决策）       │
                └──────────────┬───────────────┘
                               │
                ┌──────────────▼───────────────┐
                │   @kunolu/omp-sbtd           │
                │   Hybrid Agent Plugin        │
                └──────────────┬───────────────┘
                               │
             ┌─────────────────┼─────────────────────┐
             │                 │                     │
   ┌─────────▼────────┐ ┌──────▼──────────┐ ┌────────▼─────────┐
   │ Portable Layer   │ │ OMP Runtime     │ │ Kit / Onboard    │
   │ Agent Plugins    │ │ Control Plane   │ │ Environment Mgmt │
   ├──────────────────┤ ├─────────────────┤ ├──────────────────┤
   │ plugin.json      │ │ src/** →        │ │ onboard.py       │
   │ skills/*         │ │ dist/extension  │ │ AGENTS templates │
   │ (certified set,  │ │ /sbtd commands  │ │ external skills  │
   │  build-owned)    │ │ hooks/tools     │ │ (12 个)          │
   │ optional MCP*    │ │ state machine   │ └────────┬─────────┘
   └─────────┬────────┘ │ gates/policy    │          │
             │          │ validation      │          │
             │          └───────┬─────────┘          │
             └──────────────────┼────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │   SBTD Workflow     │
                     │ SDD BDD TDD DDD     │
                     └──────────┬──────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
     ┌──────▼─────┐      ┌─────▼──────┐     ┌──────▼──────┐
     │ Trellis    │      │ GitNexus   │     │ Validation  │
     │ lifecycle  │      │ impact     │     │ Web/Mobile  │
     └────────────┘      └────────────┘     └─────────────┘
```

`optional MCP*` 在 P0 Core Package 中默认为空；采用独立 Integration Plugin 后才进入标准 `mcp.json`。`skills/*` 的实际内容由 `packages/sbtd-workflow-kit` 的 `generated-agent-plugin/**` 投影生成，数量等于 `certifiedCount`。

---

# 42. 最终建议

对当前 `sbtd workflow + omp-sbtd`，最合理的落地不是：

```text
把所有 OMP Plugin 内容都迁到 Agent Plugins
```

而是：

```text
1. 用 Agent Plugins 1.0.0 定义 portable package identity（plugin.json，version 与 package.json 一致）；
2. 对 13 个 portable candidates 做六类审计，只把 certified set 标准化进根 skills/**；
3. 把 OMP-specific metadata 从 SKILL.md 外置到 runtime policy registry（策略映射，非 discovery 事实源）；
4. 保留 /sbtd Runtime Control Plane（src/** → dist/extension.js，不新增 P0 根目录）；
5. 保留三层 AGENTS；
6. 保留 Onboard（含 12 个 external skills 的 upstream/stable transaction）；
7. 暂不在 Core Plugin 中静默携带 optional MCP；
8. 后续用独立 Agent Plugin 打包 GitNexus 等可选 MCP（post-P0 决策）；
9. 第三方 External Skills 暂由 Onboard 继续管理；
10. 用 CI/clean-worktree **静态门**作为 portable projection 发布前置条件；28.4 Host 为可选项，防止未跑 Host 被写成 certified；
11. 分发保持 npm immutable tarball 优先；Marketplace 为 optional post-P0；
12. Host 锁定精确 17.3.5；peer-range widening 交由 omp-plugin-compatibility-decoupling-plan.md 独立治理。
```

这条路线同时满足：

- Agent Plugins portability；
- 精确 OMP 17.3.5 上的 Agent Plugins 1.0.0 能力；
- 当前 KPi v0.7 的 P0 目标；
- `/sbtd on/off` Runtime enforcement；
- 三层 AGENTS；
- 用户明确授权；
- MCP 强证据原则；
- 不 Fork OMP；
- 后续 P2/P3 Runtime-agnostic 演进。

---

# Appendix A — 实施 Backlog（对齐 M0–M5）

## AP-000 Baseline Freeze（M0）

状态：已完成（任务已归档到 `.trellis/tasks/archive/2026-08/08-18-agent-plugins-m0-m1/`）。command/gate tests 基线未单独导出，现有 Plugin/Kit 测试套件仍是回归证据。

- [x] 冻结 git revision 与 dirty/clean 状态
- [x] 固定 640-skills pin / Kit revision（4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb）
- [x] 固定精确 OMP 17.3.5
- [x] 导出 15 bundled 候选 digest 与 12 external skills 清单
- [ ] 导出 command/gate tests 基线（未纳入 M0 artifacts；M2 前按现有套件复跑，不另补历史清单）

## AP-001 Portable Skill Audit（M1，Workflow Kit 变更）

状态：已完成。`candidateCount=13`，`certifiedCount=12`；`trellis-workflow` 为 `onboard-owned`。15 个 bundled 分为 13 个 portable 审计候选，以及 2 个明确不进候选集的 `sbtd-workflow-onboard`、`trellis-channel`。二者不是同一类 OMP-specific：M3 只把 `trellis-channel` 标为 OMP-specific，`sbtd-workflow-onboard` 是退出 portable list 的 Onboard/Runtime-owned 资产。

- [x] 15 bundled skill 分类（13 portable candidates + 2 explicit non-candidates）
- [x] 六类审计：语义可移植性 / frontmatter / containment / license / reference-script / runtime-dependency
- [x] 产出 certified set 与 certifiedCount
- [x] 未通过项保持 Onboard/Runtime-owned 或 blocked 并记录原因

## AP-002 Frontmatter Transform + Projection（M1，Workflow Kit 变更）

状态：投影与 digest report 已完成。legacy frontmatter → runtime policy registry 属于 M3 AP-005，不在 M1 范围。

- [x] strict six-field schema
- [x] directory/name match
- [x] metadata string-only
- [x] compatibility / allowed-tools
- [ ] 剥离 legacy frontmatter 到 runtime policy registry（M3 AP-005）
- [x] 新增 generated-agent-plugin/** 投影与 digest report
- [x] catalog certification 元数据

## AP-003 Agent Plugin Manifest（M2）

状态：已完成（任务已归档到 `.trellis/tasks/archive/2026-08/08-18-assemble-hybrid-plugin-m2/`）。exact-peer / 启动期最低版本守卫沿用既有回归，不是 M4 四命令。

- [x] 新增根 plugin.json（标准字段，GPL-3.0-only）
- [x] schema 1.0.0
- [x] manifest validator test
- [x] plugin.json.version == package.json.version 校验
- [x] OMP 17.3.5（exact）discovery test（既有 peer / 启动守卫）
- [x] min OMP version runtime guard（既有启动期检查）

## AP-004 Hybrid Package Assembly（M2）

状态：已完成。`certifiedCount=12`；根 `skills/**` 与第三树 digest 对照；无 `commands/` `hooks/` `tools/` `runtime/` `mcp.json`。

- [x] skills/** 打包投影（build-owned、digest-verified）
- [x] npm files 白名单更新
- [x] clean worktree tarball pack 断言（数量 == certifiedCount）
- [x] 不新增 commands/hooks/tools/runtime 根目录

## AP-005 Runtime Skill Registry（M3）

状态：已完成并归档于 `.trellis/tasks/archive/2026-08/08-18-cutover-certified-skill-ownership-m3/`。Host-proven discovered 留给 M4。

- [x] activation predicates / route mapping / required gates
- [x] 声明 registry 为策略映射而非 Host discovery/invocation 事实源
- [x] Doctor source reporting（当前完成态为 `source-unverified`；Host-proven `agent-plugins` 留给 M4）

## AP-006 Duplicate Discovery Guard + Ownership Cutover（M3）

状态：已完成并归档（同上）。catalog / Runtime 证据 / leftover cleanup 已在 `20896d1` 落地。exact-host collision 证明留给 M4。

- [x] certified skills 仅由 packaged `skills/**` 提供 Runtime 证据
- [x] Onboard catalog 不再把 certified 名列为 bundled copy 来源
- [ ] collision tests（exact-host / Host loader 证明留给 M4）
- [x] Onboard managed cleanup 按 certified set 参数化执行，可回滚

## AP-007 Onboard Doctor（M3）

状态：已完成并归档（同上）。§22 块已在成功与环境观察失败路径输出。Host-proven discovered 留给 M4。

- [x] Agent Plugins support（schema / manifest / packaged digest）
- [x] manifest status
- [x] packaged 计数与 `source-unverified` discovered
- [x] invalid skill list
- [x] runtime extension status

## AP-008 CI / Conformance（M4；Host 可选；无 CI 则晋升 blocked）

状态：静态门已在 clean `ec849c62…` tarball 上通过，可结束 M4。28.4 Host / §29 为可选项 `not-run`。CI 未接入，**晋升 blocked**。不得写成 exact-host certified。

- [x] manifest gate / skill gate / containment gate（local clean-worktree）
- [ ] clean exact-host Host 项（可选 / `not-run`）
- [ ] SBTD Host-observable §29（可选 / `not-run`）
- [ ] Onboard Host regression（可选 / `not-run`）
- [x] CI 未接入：local clean-worktree 静态证据可结束 M4；**晋升 blocked**

## AP-009 Release Decision（M5）

- [x] 汇总 M0–M4 证据
- [x] 冻结版本已在 M2 确定为 `0.1.0-rc.12`；M5 不得改版本
- [x] npm tarball 发布决策：发布到 `next`；Registry 身份 `passed`

## 后续独立决策（不在本 Backlog 承诺）

- Marketplace 渠道（`.omp-plugin/marketplace.json` + `omp plugin marketplace add <source>`）
- GitNexus / Playwright / Maestro optional MCP Integration Plugins
- peer-range widening（由 omp-plugin-compatibility-decoupling-plan.md 治理）
- `latest` / stable / 其他 dist-tag（本 RC 已在 `next`；不得 retag `latest`）

---

# Appendix B — 决策记录

| ID | 决策 | 结论 |
|---|---|---|
| ADR-AP-001 | Agent Plugins 是否替代 OMP Plugin | 否 |
| ADR-AP-002 | Core 是否加入根 `plugin.json` | 是（标准字段，version 与 package.json 一致） |
| ADR-AP-003 | Bundled Skills 是否标准化 | 是，仅 certified set（audit 参数化，不预设 13/13） |
| ADR-AP-004 | 三层 AGENTS 是否迁入插件标准 | 否 |
| ADR-AP-005 | `/sbtd` 是否迁入标准 | 否 |
| ADR-AP-006 | Core 是否默认包含 GitNexus `mcp.json` | P0 否 |
| ADR-AP-007 | Optional MCP 是否可拆独立 Agent Plugin | 是（post-P0 独立决策） |
| ADR-AP-008 | External Skills（12 个）是否 vendoring | 否 |
| ADR-AP-009 | `onboard.py` 是否 portable | 否 |
| ADR-AP-010 | 迁移 Host 基线 | 精确 OMP 17.3.5；range widening 由 decoupling plan 独立治理 |
| ADR-AP-011 | P0 分发渠道 | npm immutable tarball；Marketplace optional post-P0 |
| ADR-AP-012 | Runtime 根目录布局 | 保持 src/** → dist/extension.js；P0 不新增 commands/hooks/tools/runtime 根目录 |
| ADR-AP-013 | Skill 激活语义 | model-visible/manual invocation + Runtime route guidance；无确定性自动激活；registry 非 discovery 事实源 |
| ADR-AP-014 | CI/Conformance 位置 | portable projection 发布前置条件，非晚期 backlog |

---

# Appendix C — 参考标准

- Agent Plugins 1.0.0 Manifest Schema  
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`
- Agent Plugins 1.0.0 MCP Schema  
  `https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`
- OMP 17.3.5（exact）Agent Plugins discovery
- OMP plugin peer-range 解耦治理：`docs/assets/omp/omp-plugin-compatibility-decoupling-plan.md`
- KPi PRD / ROADMAP v0.7
- SBTD Workflow / `640-skills`（pin revision `4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb`）
