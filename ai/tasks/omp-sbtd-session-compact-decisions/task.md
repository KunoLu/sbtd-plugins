---
schema_version: 1
id: omp-sbtd-session-compact-decisions
workflow_mode: default
mode_source: default
mode_note: 编排方整理：新建独立 PRD-only 决策记录，未选择其他执行模式，按 default；唯一 writer；两个本地提交，不执行远端或全局配置写入。
status: checking
branch: docs/omp-sbtd-session-compact-decisions
created_at: '2026-10-23T18:36:09+08:00'
updated_at: '2026-10-23T18:39:30+08:00'
completed_at: null
---
# session_compact D1–D5 决策：PRD-only

## 目标、模式与授权

- 编排方整理：授权根 `/workspace/sbtd-plugins-session-compact-decisions`；分支与 frontmatter 一致；入口 clean，HEAD/origin/main 为 `c90fddb6c49af1f9d89c33f61f5b34f8f9081b99`。仅 `docs/prd/**` 与 `ai/tasks/**`；不改 packages、.github、任何 README/CHANGELOG；不 push、开 PR、comment、tag、publish、merge、触发 workflow 或修改全局配置。
- 选址：旧 [PRD task](../omp-sbtd-session-compact-prd/task.md) 已随 #120 done，保留其 strict 模式、原 branch、正文及事件，不重开或重绑定。此次是独立的决策记录交付，新任务缺省 default；按明确共享产物要求写入 `ai/tasks` 并在 index 按字母序导航，不把旧 strict 模式自动继承到新任务。
- 旧 task 回填仅执行编排方整理的跨分支历史文档授权，不接管其执行生命周期。沿用既有 TaskStore 全库历史 schema blocker，不重跑、不调用 helper lifecycle；共享 Markdown 文档落盘不等于 TaskStore 持久化或自动恢复通过，不写 active/developer/handoff/ignore。
- 目标及父路径已确认无 symlink、路径位于授权根；旧文件 tracked、新 task 不存在且不被 ignore。未完整调用 grill-with-docs：五项选择及 v2 确认明确，无需重新提问或新裁决；§3.2 原选项文字保留为历史，当前裁决结果另列。
- 第一个本地提交 `5363876` 完成 #121 回填；[host smoke task](../dsh-host-smoke-version-assert/task.md) 保存 merge/post-merge/pre-check/FINAL，row G task 追加时间纠正，dsh PRD row G 仅追加证据指针。#120 合并与 tag/prerelease/双语链接/逆序发布事实已存在，未重复记录。
- 本任务按仓库 PRD 交付惯例：本地文档与检查完成后记 checking，completed_at 保持 null；只有后续实际合并回填才记 done。本轮完成不包含远端合并、代码实现或宿主认证。

## 群内确认（原文）

- 用户 2026-10-23 18:30 +08:00 群内确认（采纳 D1-B/D2-A/D3-B/D4-A/D5-A，与 OMP/Researchy/Reviewy 投票一致），Lord 记录
- 用户 2026-10-23 18:31 +08:00 群内确认（v2，开始），Lord 记录

## 决策与只读核对

完整选项真源为 [PRD §3.2](../../../docs/prd/omp-sbtd-session-compact.md)。当前决定为 D1-B、D2-A、D3-B（v2）、D4-A、D5-A；没有新增 PRD 裁决。

| 项目 | 已确认要求 / 证据 |
|---|---|
| D1-B | 结构 + 关联窗口 + `compactionEntry.method === "handoff"`；缺 method 失败，不从 fromExtension 推导 |
| D2-A | session_compact required；13 required + 1 optional，共 14 subscriptions |
| D3-B | inventory/contract 与 evidence profile 同时 v2；代码重命名留在后续代码 PR |
| D4-A | 一次一个 handoff，以同 run、同 session、可证明窗口匹配；须证明窗口内无竞争 compact |
| D5-A | peer `>=18 <19` 不变，认证目标 18.11.1；不得降级主用/全局 omp |

- 本轮只读字面量检索并读取定义：`src/runtime/omp-extension-v1.ts:46–65` 的 inventory.version=`omp-extension-v1`；`scripts/p0/compatibility-ledger.ts:435` 的 contractProfile、`scripts/p0/three-profile-certification.ts:511` 的 inventoryVersion 同为 `omp-extension-v1`；`scripts/p0/host-event/validate.ts:147,612,729` 的 profile=`omp-host-events-v1`。路径均相对 `packages/omp-sbtd`。实际基名与编排材料一致，后续名称确定为 **omp-extension-v2 / omp-host-events-v2**，本轮没有重命名代码。
- 编排方整理：18.11.1 的 npm 源码证据由 OMP 与 Researchy 独立发现，dist.shasum `e8cb333e5d6d471cdbedf66b8be5af902502927e` 已由编排方以 npm view 再核对；具体文件/行及 awaited emit 边界见 PRD §2.1。本轮按该材料记录，未重新 npm view、安装或运行宿主；**source-only，不是 live/runtime certification**。
- 旧 omp-sbtd 0.2.0-rc.1 PRD 指针仍称五项开放，因此只追加当前决定指针，保留原历史行；不改 rc.1 验收或主序列。

## 后续代码 PR 门禁

- 必须在隔离安装的 18.11.1 live cell 捕获真实 handoff 的 session_compact；绝不降级主用/全局 omp。
- method 缺失就是失败；若 live run 中缺失，返回用户重新选择，不默认改选 D1-A、不放宽 schema、不默认升降宿主下限。
- 证明同 run/session、窗口基线/完成边界及排空可见，且窗口内没有竞争 compact；不能用跨进程 seq 或墙钟伪造全序，response 前事件不能被误拒，重复 entry 不增加覆盖。
- 代码 PR 不包含 PRD 裁决；任何新决定先返回独立 PRD-only PR。现有 HANDOFF_TRIGGER_BLOCKED / HANDOFF_NOT_ATTEMPTED 等级不变；代码 PR 合并后 HANDOFF_EVENT_UNOBSERVABLE 恢复硬失败。

## DDIA Data Design Review

- Status: **blocked（仅后续稳定实现设计；不阻断本次已决定的 PRD-only 记录交付）**。五项选择和版本不再开放；阻塞是隔离 18.11.1 的真实事件链及 D4 排空/边界/无竞争证明尚未执行，不将源码证据提升为运行认证。
- Data owner / source of truth：宿主保存的 entry 和真实事件；observer 只采集脱敏结构/身份摘要；driver 的 RPC 成功不是事件替代品。
- Write / read / async / failure paths：宿主保存 entry 后 awaited emit，observer 落盘，validator 按 run/session/window 与 method 校验；任一必要证据缺失 fail-closed。跨流落盘排空的实际方案须由代码 PR 证明。
- Consistency / ordering / deduplication：一次一个 handoff；窗口内同 session 新 entry；拒绝旧 run、跨 session、窗口外、普通 compact；同 entry 重复不新增覆盖，事件早于 response 仍可有效；不引入重试框架。
- Schema / migration / replay / rollback：新判据使用 omp-extension-v2 / omp-host-events-v2；只同步实际受影响消费者，旧认证只读保留、不重标/重放为 v2 通过；本轮文档回退不改变运行时。
- Observability / repair：保留稳定失败码与脱敏摘要，不保存 summary/details/raw session 路径；实跑缺 method 返回裁决，而非静默降级。
- Required tests：PRD §4 的成功/无事件/缺 method/普通 compact/跨 run-session/顺序/重复/脱敏，以及隔离 18.11.1 的真实 live cell。本轮均未执行宿主行为测试。
- 其他 Book Gate：DDD 无完整 grill 或新增领域歧义；legacy/refactoring 无生产 edit；release 无运行时、部署或发布变更，均 not-required；不冒称旧 gate 重跑或通过。

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T18:36:09+08:00 | planned | in-progress | 编排方整理：建立独立 default 共享决策记录，不重开 #120 done task | 分支/路径/ignore/tracked 检查；两条群内确认；真实 v1 标识只读核对；首个本地回填提交 5363876 |
| 2026-10-23T18:39:30+08:00 | in-progress | checking | 编排方整理：D1–D5 与 v2、source-only 补证、四项代码 PR 门禁已写入；本地文档验证通过，等待后续独立 PR/合并，不标 done | python3 文档 smoke：7 个允许文件、3 份 task YAML、追加保护、10 条原选项保留、当前决定、渲染/链接/锚点/index、删除白名单均通过；whitespace exit 0 |

## 本次验证与交付边界

- `2026-10-23T18:39:30+08:00`：`python3 -c <文档检查> WORKTREE`，Python 3.13.5 / PyYAML 6.0.3 / markdown-it，exit 0。7 个允许文件，3 份 changed task frontmatter 可解析；旧 task 正文及事件逐行、顺序保留，仅允许 frontmatter status/updated_at/completed_at 变化。Markdown 实际渲染、相对链接、两个新增锚点、验收表的缺 method/顺序重复行及 index 字母序/唯一性通过。
- 决策检查：两条确认原文齐全，五项裁决均已决定；§3.2 的 10 条原 A/B 选项逐字保留；真实基名与两项 v2 目标、source-only shasum、隔离 live cell/缺字段失败/无竞争 compact/代码 PR 不裁决四项门禁均通过文档检查。新增行归因过滤 0 hits、changed files 冲突标记 0；`git diff --check origin/main` exit 0。最终 committed HEAD 的检查结果在最终交付报告，不预写成功。
- 删除行清单（按 origin/main 行号）：host smoke task 第 7/10/11 行为 status/updated_at/completed_at；row G task 第 10 行为 updated_at；dsh PRD 第 85 行为状态格整行 diff，但原格完整保留、仅尾部追加指针，其他格逐字一致；session_compact PRD 第 3/52/54/56/62/68/74/80/86/94/103/113/117 行均为当前状态/裁决结果/验收待决/分步状态更新。没有删除旧事件、旧选项或历史 task 正文。旧 omp PRD 指针仅追加。
- 未执行：包 lint/build/typecheck、单元/集成/E2E、BDD runner、18.11.1 live cell、CI 或发布；原因是本轮 PRD-only 且禁止代码/运行门禁改动。历史 lint/TaskStore 失败不重跑；没有安装、降级或改动主用/全局宿主。文档解析/渲染 smoke 不冒充宿主认证。
- rtk=not-needed（按验收使用原生 Git/Python）；BDD=skipped（仅 PRD 验收意图，后续沿用中文场景 + 英文关键词及现有 feature/Vitest）；Cross-repo context=contract-only；API Contract=verified（仅仓库 v1 标识及编排方 source-only 材料，不含 live 认证）；Mock Strategy=none；Graft=skipped（源码与文档证据足够，不启动或接线）。Final Test Report / Run Summary MD=not-needed（无正式测试 runner，文档检查结果直接记录）。
- 完成边界：本地两提交文档交付；共享 task 保持 checking，后续合并事实未知，completed_at null。实现/live 认证尚未执行，DDIA 后续实现门未解除；本轮不制造 PRD 新裁决，也不声称代码、部署或发布完成。回退这两次文档提交不会改变已发布包；历史纠错继续追加，不承诺 TaskStore 自动恢复。
