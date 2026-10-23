# omp-sbtd：session_compact handoff 证据 PRD

状态：**PRD-only 草案；D1–D5 open / pending，尚未裁决**。本文件交付已登记 follow-up 的步骤 (a)，不代表代码、CI、硬失败恢复或发布已完成。

## 1. 来源与范围

- 既有裁决：用户 2026-10-22 13:13 +08:00 裁决，见 [omp-sbtd 0.2.0-rc.1 PRD 的后续登记](omp-sbtd-0.2.0-rc.1.md)（基线第 76 行）与 [行 C task](../../ai/tasks/omp-sbtd-0-2-0-rc-1-pr-c-plugin-adapt/task.md) 的决策及「后续（follow-up）」第 66–67、93–100 行。
- 用户 2026-10-23 17:25 +08:00 群内确认（开始 session_compact），Lord 记录。
- 编排方整理：本轮仅将「订阅 `session_compact` 作为 handoff 证据」写入 host-event inventory/validator 的 PRD 契约，先交付包含待裁决选项的 PRD-only 草案；进入后续代码 PR 前须完成相关裁决与 PRD-only PR。**代码 PR 合并后，`HANDOFF_EVENT_UNOBSERVABLE` 恢复为硬失败**。这项顺序及最终硬失败要求已登记，不在本轮重新开放选择。
- 编排方整理：新增独立 PRD，因该事项已明确不在 rc.1 主序列；不改写 rc.1 历史验收或已发布证据。[strict 任务记录](../../ai/tasks/omp-sbtd-session-compact-prd/task.md)保存调查、选址、验证及历史回填。
- 检索覆盖 docs/prd、ai/tasks、docs/spec 的 session_compact / session compact / HANDOFF_EVENT_UNOBSERVABLE / handoff，以及 ROADMAP、backlog、follow-up。ROADMAP §20.2 的「Session Compaction」是旧专项测试条目，不据此扩展成 compaction 产品重构。offline-cache、README 命名、ROADMAP 归档等独立事项不并入本 PRD。

### 非目标

不改宿主 compaction 算法、handoff 文档生成、task/handoff 自动保存、session 恢复协议、dsh-sbtd、工具名、四命令发布授权或其他事件门禁。不新增遥测、重试服务或持久化系统。不安装/升级宿主，不改 packages、README、CHANGELOG、docs/spec、CI 或全局配置；这些必要实现面仅列为后续代码 PR 的影响面。本轮不 push、开 PR、comment、tag、publish、merge。

更新（2026-10-23，编排方整理）：上文「本轮不 push、开 PR…」保留为原执行授权边界；后续 #120 已开 PR 并 squash-merge 为 `67465db93e7c6f1e6f5f43704c1d4c22ae74306d`。git %cI 为 `2026-10-23T17:56:18+08:00`，GitHub mergedAt 为 `2026-10-23T17:56:19+08:00`，分别记录；不代表 D1–D5 已裁决或代码实现完成。

## 2. 当前事实与证据边界

仓库基线：`548a0bf125e3b3fe1407de11094409e55c2e779e`。下列为只读源码核对，不是本轮真实宿主 live-cell 测试。

| 当前事实 | 证据 |
|---|---|
| inventory 标识 `omp-extension-v1`；12 个 required + 1 个 optional（`credential_disabled`），共 13 个订阅名；包含 `session.compacting`，不含 `session_compact` | [inventory](../../packages/omp-sbtd/src/runtime/omp-extension-v1.ts):46–65；runtime/index.ts:195–299 |
| `session.compacting` 是既有事件，adapter-edge 要求 type、sessionId、messages；不能将它的 payload 套给 `session_compact` | inventory 文件:230–236 |
| observer 用实际 subject 包的 validator 验证事件，只保存字段名、稳定状态与不可逆身份摘要；ctxSessionDigest 来自 context 的 sessionManager | [observer](../../packages/omp-sbtd/scripts/p0/host-event/observer.mjs):164–255 |
| 当前 sessionDigest 仅从 event.sessionId 取值，尚无 compactionEntry 身份摘要采集；新增事件不能复用此前事件的 sessionId 假设 | observer:194–195、230–232；后续按 D1/D4 扩展必要的脱敏采集，不保存 entry 正文 |
| driver 的 handoff 位于场景末尾；当前只记录 attempted、ok、resultKeys 或错误，没有 handoff 专用事件关联字段 | [driver](../../packages/omp-sbtd/scripts/p0/host-event/drive.mjs):677–700 |
| handoff ok → `HANDOFF_EVENT_UNOBSERVABLE` diagnostic；失败 → `HANDOFF_TRIGGER_BLOCKED`；未尝试 → `HANDOFF_NOT_ATTEMPTED`；后两项也是 diagnostic | [validator](../../packages/omp-sbtd/scripts/p0/host-event/validate.ts):521–531 |
| failures 非空 → failed；否则 diagnostics 非空 → passed-with-diagnostics；否则 passed。observer_ready 的 subscriptions 须等于 inventory 大小；runId 不符为陈旧/共享日志失败 | validator:202–226、602–615；evidence profile 为 `omp-host-events-v1` |
| peer 范围 `>=18 <19`，dev/cell target 钉 18.11.1；不能把 range 等同所有 18.x 已实测 | [package manifest](../../packages/omp-sbtd/package.json)、[compatibility](../../packages/omp-sbtd/validation/p0/compatibility.v2.json)、[live cell](../../packages/omp-sbtd/scripts/p0/host-event/run-live-cell.ts) |
| 当前 BDD 仍明确 handoff diagnostic，不可因本 PRD 把它报告为已经恢复硬失败 | [feature](../../packages/omp-sbtd/features/sbtd-control-bootstrap.feature):443–447；[testing spec](../spec/omp-sbtd/backend/testing.md):111–117 |

### 2.1 宿主 payload：已知与未知

本轮由 `command -v omp` / `readlink -f` 定位本机已安装的 `@oh-my-pi/pi-coding-agent`，manifest 版本 **18.12.6**；只读其源码，没有启动宿主、修改配置或读取凭据。本机包根为 `~/.bun/install/global/node_modules/@oh-my-pi/pi-coding-agent`，下列 `src/` 文件确实存在且已读取；不保证其他安装布局相同，不以未读取的 dist 文件替代本轮证据。可复核源位置以该包根为相对根：

- `src/extensibility/shared-events.ts:89–102`：`session.compacting` 在 summarization 前；`SessionCompactEvent` 在 compaction 后，字段为 `type: "session_compact"`、`compactionEntry: CompactionEntry`、`fromExtension: boolean`。顶层没有声明 sessionId、RPC requestId 或 handoff reason。
- `src/session/session-entries.ts:79–83,144–153`：entry 有 id、parentId 等基础字段；CompactionEntry 有 `type: "compaction"`、summary、firstKeptEntryId、tokensBefore；`method` 为 optional。不能把 summary 正文作为公开证据，不能假定所有历史 entry 都有 method。
- `src/session/session-maintenance.ts:2084–2118,2484–2538`：handoff 生成文档后提交 compaction，设置 `fromExtension: false`、`method: "handoff"`；保存 entry 后发出 `session_compact`，该 handoff 调用等待 emit 后返回。普通 compact 也走 compaction 提交，故仅看到事件名不能证明由本次 handoff 引起。
- **未知**：18.11.1 的精确 payload 是否具有同样的 entry.method、相关可用性下限、所有受支持版本的跨流落盘顺序。本仓行 C 留有 18.11.1 同 session compaction 的历史源码核对，但本 worktree 未安装该版本；18.12.6 源码不是 18.11.1 类型或运行验收。后续代码 PR 必须补目标版本证据，不能按全局版本替换 D11 钉版。

## 3. host-event inventory / validator 新判据

### 3.1 已登记要求（本 PRD 写明，代码尚未实现）

1. 订阅并验证真实宿主发出的 **`session_compact`**，用作 handoff 的事件证据；不伪造 `session_switch.reason=handoff`，不以 RPC 成功代替事件观测。
2. `session.compacting` 保留既有独立语义与验收；新增判据不能以改名/替换旧事件降低其覆盖。
3. handoff 覆盖通过必须有符合最终裁决规则、可归属于该次 handoff 的 `session_compact` 证据。单纯 inventory 中存在名字、observer_ready 订阅数正确或另一场 compact 的事件不足以证明覆盖。
4. 代码 PR 合并后：成功 handoff 缺少有效关联观测时，`HANDOFF_EVENT_UNOBSERVABLE` 进入硬失败路径，不能再仅进入 diagnostics 而得到 passed-with-diagnostics。本轮不改变当前运行语义、不追改旧证据结果；代码 PR 的预合并测试需先证明新硬失败分支，合并是主线切换点，不是再等一次 release。
5. 保留既有证据身份、schema、脱敏、session 隔离及其他失败门禁。事件归属与 payload 的具体最小字段、订阅分级和版本标识由 D1–D5 裁决后落地，不在本文暗定。

### 3.2 待裁决方案（均为编排方整理）

各项状态均 **open / pending**；所有推荐均为 **推荐（仅建议，待用户裁决）**。选项不是已经锁定的契约，不以多数推荐或本轮完成自动生效。

#### D1 — 哪些 payload 字段足以证明 handoff？

- **A：结构 + 关联窗口。** 按目标宿主真实类型验证 type、compactionEntry、fromExtension；证据至少保留 entry 身份摘要与 ctx session 摘要，结合 D4 的隔离窗口归属 handoff，不要求 entry.method。优点是兼容无 method 的形态；风险是窗口内其他 compaction 可能误归属，必须能证明隔离。
- **B：A + handoff 方法标识。推荐（仅建议，待用户裁决）** 额外要求真实 entry 的 `method="handoff"`，不从 fromExtension=false 推导 handoff。18.12.6 源码支持该区别，可拒绝普通 compact 冒充；18.11.1 是否支持未知，必须先补证，不能造字段或自动抬版本下限。
- 裁决结果：**未知；open / pending**。两方案都不持久化 summary/details/raw session 路径，不用 method 或事件名代替 session/run 关联。

#### D2 — inventory 必需性与 13 → 14

- **A：将 session_compact 加入 requiredEvents。推荐（仅建议，待用户裁决）** 保留原 12 required 与 1 optional，成为 13 required + 1 optional，总订阅数 14；全量 host-event profile 必须观测它，handoff 还需单独满足 D1/D4。优点是新契约 fail-closed，代价是缺少该能力的宿主不满足新契约。
- **B：加入 optionalEvents，但 handoff 成功场景条件必需。** 总订阅数同样为 14（12 required + 2 optional）；成功 handoff 无证据仍硬失败，不能以 optional 逃逸。其他场景不强制出现；需明确 optional 能力与 handoff profile 条件的区别。
- 裁决结果：**未知；open / pending**。新增事件而不删除旧事件时，订阅名总数自然为 14；争议是 required/optional 与认证含义，不把手工改 count 当事件覆盖。

#### D3 — contract / evidence profile 如何版本化？

- **A：保留 `omp-extension-v1` / `omp-host-events-v1` 名称。** 以精确 subject、validator 与 scenario-set 身份区分新旧判据，验证所有消费者都不会把旧 diagnostic 结果当作新合格证据。改动较小，但同名结果含义变更需明确说明。
- **B：为变更后的 inventory/contract 与 evidence profile 使用新版本。推荐（仅建议，待用户裁决）** 让新硬失败判据与旧证据身份明确分离；具体版本值、compatibility/ledger 引用清单须在代码 PR 前补齐裁决，不预写为已存在的 v2。旧记录只读保留，不为新产物保留旧语义兼容 shim。
- 裁决结果：**未知；open / pending**。不借此重做 p0 ledger/schema 或四命令协议；只同步本判据实际影响的消费者。两方案均禁止重新解释或覆盖历史认证证据。

#### D4 — 如何关联 handoff RPC、同 session 与事件顺序？

- **A：单次串行 handoff + 明确观测窗口。推荐（仅建议，待用户裁决）** 使用现有 runId 与 session 摘要，建立 handoff 发起前基线、一次 RPC 及观测完成边界；只认可窗口内同 session 的合格新 entry。代码 PR 需证明窗口内无竞争 compact、事件日志排空可见及边界可靠；不能用两个进程各自 seq 大小或墙钟先后假装全局顺序，也不能要求事件必须在 RPC response 之后才算数。
- **B：原生因果 ID 关联。** 仅当目标宿主契约证明可获得 handoff/RPC 与 compaction entry 的稳定对应 ID 时采用；当前 SessionCompactEvent 顶层未声明 requestId，是否有其他可靠映射未知。若需修改上游宿主协议，须另行授权，本 PRD 不包含该实现。
- 裁决结果：**未知；open / pending**。重复同一 entry 不形成新的覆盖；旧 run、跨 session、窗口外或无法关联的事件不能消除 handoff 证据缺失。具体观测等待上限与排空方案须由真实宿主行为确定，不虚构超时数值，不加重试框架。

#### D5 — 宿主版本与兼容性下限

- **A：保留 D11 peer `>=18 <19` 与认证目标 18.11.1。推荐（仅建议，待用户裁决）** 先补 18.11.1 类型、发射路径和真实 live-cell 证据；若 D1/D4 所选方案在该版本不可实现，停止该方案并返回裁决，不把缺事件降级为通过。
- **B：将新判据的兼容/认证下限提高到有充分证据的版本。** 具体版本未知；18.12.6 只有本轮源码证据，尚非运行认证。须显式裁决 peer/dev/CI 是否联动及兼容影响，不能由本 PRD 的本机版本自动选择。
- 裁决结果：**未知；open / pending**。D1-B 与 D5-A 的组合须先证明 18.11.1 的 method 字段；没有证据时不可宣称两个推荐已能同时落地。

### 3.3 不重新裁决的诊断边界

硬失败恢复时间和 `HANDOFF_EVENT_UNOBSERVABLE` 名称沿用既有裁决。`HANDOFF_TRIGGER_BLOCKED` / `HANDOFF_NOT_ATTEMPTED` 当前仍是 diagnostic，本轮不扩大为修改其等级；二者不证明 handoff 覆盖通过。后续验收必须实际执行成功 handoff 并检查关联事件，不能拿未尝试/触发失败的 passed-with-diagnostics 替代验收。若要额外改变这些诊断等级，须另列范围与裁决，不随本 PRD 偷带。

## 4. 验收意图与后续证明

以下为 PRD 验收意图，不是已执行测试，也不替代项目既有 `.feature`。实现阶段沿用中文场景 + 英文 Gherkin 关键词，将最终裁决同步到 `packages/omp-sbtd/features/sbtd-control-bootstrap.feature` 并映射既有 Vitest 测试。当前全部 **待后续代码 PR 验证**；D1–D5 未裁决前不得把候选细节锁入行为测试。

| 场景 | 前提 / 动作 | 预期边界 |
|---|---|---|
| 有效 handoff 证据 | 同一 run/session 的成功 handoff，观测到符合裁决的 session_compact | handoff 覆盖成立；其他失败仍可令整体 failed |
| 成功但无事件 | handoff RPC 成功，没有有效关联事件 | 代码 PR 合并后的新契约：HANDOFF_EVENT_UNOBSERVABLE 为硬失败，不是 diagnostic-only |
| 普通 compact 冒充 | 只有先前普通 compact 的事件或 session.compacting | 不满足 handoff 证据；保留原 compact 覆盖规则 |
| 陈旧 / 跨 session | 有事件但属于旧 run、其他 session 或窗口外 | 不可通过；既有身份/隔离失败保持，handoff 缺证据仍失败 |
| payload / 订阅不完整 | 事件 schema 无效、缺少最终必需字段或 observer 订阅清单不完整 | 不计作有效证据；保留 schema/subscription 硬门 |
| 顺序与重复（细则待 D4） | 事件在 RPC response 前到达，或同一 entry 重复观测 | 关联/窗口规则待裁决；候选验收须覆盖 response 前到达与重复事件，不能将该候选当作已锁定实现 |
| 未尝试 / 触发失败 | driver 无成功 handoff | 如实保留当前诊断区别，不宣称新增 handoff 路径已验收 |
| 脱敏 | 事件包含 summary、details、身份/路径等 | 公开证据不泄露正文、凭据、原始身份或路径；仅保留裁决允许的结构与摘要 |

后续验证面：`test/omp-host-contract.test.ts`（adapter-edge schema）、`test/host-event-surface.test.ts`（validator 与负例、live cell）、`test/runtime.test.ts` / `test/extension.test.ts`（runtime 注册面；stub host 不等于真实宿主投递）、frozen-tarball CI live cell。必需真实场景：按批准的精确宿主版本加载实际新 tarball，执行一次成功 handoff，核对脱敏 observer/driver/scenario 与新失败判据。测试 fixture 不冒充宿主事件投递；旧 13-hook/diagnostic-only 证据不冒充新判据认证。

## 5. 分步交付与影响面

| 步骤 | 内容 | 本轮状态 |
|---|---|---|
| (a) PRD-only | 本文写入新判据、现状证据、D1–D5 与验收边界；后续裁决并审阅 PRD-only PR | 本地文档交付；裁决 pending；未开 PR、未合并 |
| (b) 代码 PR | 在裁决后同步 inventory/adapter schema、runtime 订阅、observer、driver 关联证据、validator、tests、BDD 与 CI live cell；按 D3 同步实际受影响的 contract/evidence 引用 | 未开始；本 PRD 不修改这些文件 |
| (c) 合并切换 | 代码 PR 的新判据与预合并验证通过后合并，主线 HANDOFF_EVENT_UNOBSERVABLE 恢复硬失败；保留旧证据的历史语义 | 未执行；不把 (a) 完成或文档合并当作恢复完成 |

更新（2026-10-23，编排方整理）：步骤 (a) 的「未开 PR、未合并」是历史快照；#120 已开 PR 并以 `67465db93e7c6f1e6f5f43704c1d4c22ae74306d` squash-merge（git %cI `2026-10-23T17:56:18+08:00`；GitHub mergedAt `2026-10-23T17:56:19+08:00`）。D1–D5 仍 **open / pending**；步骤 (b)/(c) 未完成，不把文档合并当作硬失败恢复。

后续实现须由同一批准的 inventory 派生订阅/validator 清单，避免 observer、runtime、tests 手工分叉；这些是现有单一真源约束的延续，不新增第二套 registry。与新判据有关的 docs/spec、现有说明和发布材料应由后续代码/发布任务按授权更新；本轮不越界。回退本 PRD 的本地提交只影响文档，不恢复或改变任何宿主行为。
