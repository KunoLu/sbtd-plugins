---
schema_version: 1
id: omp-sbtd-session-compact-prd
workflow_mode: strict
mode_source: user
mode_note: 编排方整理：strict、唯一 writer；先 records-only 回填，再 PRD-only；仅本地提交，不执行远端写入或全局配置变更。
status: done
branch: docs/omp-sbtd-session-compact-prd
created_at: '2026-10-23T17:29:07+08:00'
updated_at: '2026-10-23T18:00:01+08:00'
completed_at: '2026-10-23T17:56:19+08:00'
---
# session_compact handoff 证据：PRD-only

## 目标与授权边界

- 用户 2026-10-23 17:25 +08:00 群内确认（开始 session_compact），Lord 记录。
- 编排方整理：提交 1 仅追加 #118/#119 记录回填及 dsh PRD 行 G 状态单元格；提交 2 起交付 session_compact PRD、待裁决选项及本记录。只修改 docs/prd/**、ai/tasks/**，不修改 packages/**、README 或 CHANGELOG。
- 编排方整理：根 /workspace/sbtd-plugins-session-compact-prd；实际分支与 frontmatter 一致；入口 clean，HEAD 与 origin/main 均为 548a0bf125e3b3fe1407de11094409e55c2e779e。不 push、开 PR、comment、tag、publish、merge 或修改全局配置。
- 编排方整理：旧 task 正文和事件 append-only，仅允许更新 status/updated_at/completed_at；旧 branch 保留，历史回填不重绑定。源于本轮编排材料的事实与建议均标明编排方整理；未知信息不补造。
- 未完整调用 grill-with-docs：已登记范围与文档交付明确；新判据的未决细节列 A/B 选项，等待裁决，不将 PRD 草案当作稳定实现设计。
- 沿用 #118/#119 已记录的 TaskStore 全库历史 schema blocker，不重跑、不调用 lifecycle、不写 active pointer。本文件是明确要求的共享文档产物，不声称 helper 持久化或自动恢复通过。目标及父路径无 symlink，旧文件 tracked，新 task/PRD 不被 ignore；不写本地状态、身份或 handoff。
- PRD 选址：新增 docs/prd/omp-sbtd-session-compact.md，作为既有 omp-sbtd PRD 主序列之外的已登记 follow-up；不改写已发布 rc.1 的历史判据。沿用 ai/tasks/index.md 字母序导航约定新增一行。

## Book Gate Plan

| Reviewer | 触发事实 / 判定 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 区分 handoff RPC、同 session compaction 与 task 交接文档的语义边界 | PRD 草案审查 | planned |
| book-ddia-data-design | host-event 异步观测、证据归属、顺序及 contract 兼容性 | PRD 草案审查；稳定设计前 | planned |
| book-legacy-change-safety | 本轮无生产行为修改；旧记录由追加式检查保护 | before-dev | not-required |
| book-refactoring-pass | 不编辑生产代码 | before-dev | not-required |
| book-release-readiness | 不改变运行时、部署或发布；历史发布仅回填 | after-validation | not-required |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-23T17:29:07+08:00 | planned | in-progress | 编排方整理：建立 strict PRD-only 文档记录，开始历史回填与契约调查 | 根/分支/基线及路径检查通过；17:25 群内确认；仅共享文档写入，不调用 TaskStore lifecycle |
| 2026-10-23T17:41:10+08:00 | in-progress | checking | 编排方整理：已完成 PRD-only 草案、开放选项与文档验证；待裁决及后续 PR 流程，不标 done | python3 文档 smoke 通过；D1–D5 open / pending；DDD confirmed（边界），DDIA blocked（稳定设计/实现）；completed_at null；提交后检查在最终交付报告 |
| 2026-10-23T17:56:19+08:00 | checking | done | 编排方整理：#120 已 squash-merge，完成 PRD-only 交付；历史回填保留原 branch 与所有旧记录 | squash 67465db93e7c6f1e6f5f43704c1d4c22ae74306d；GitHub mergedAt 2026-10-23T17:56:19+08:00；git %cI 2026-10-23T17:56:18+08:00；D1–D5 仍 open / pending，不代表实现门禁通过 |

## 调查与提交 1 证据

- 编排方整理：本地提交 `9c732cc`，`docs(sbtd): backfill #118 merge release and final model records`，3 files changed / 61 insertions / 5 deletions。两份旧 task 删除行只涉及三个允许的 frontmatter 字段；正文、状态事件与 branch 原样保留。dsh PRD 仅行 G 状态单元格变化，其他单元格含旧 latest 计划保留；新增状态与回填说明明确实际 latest 已更新、未新增群内政策裁决。
- 主会话读取 `~/.omp/logs/sbtd-rowg-dsh-rc2/pr118-body.v2.md`，FINAL 使用量与 title-gen 数字全部匹配，无数字差异；git %cI 独立核对为 17:03:31+08:00，mergedAt 17:03:32+08:00 与发布数据只按编排方整理。#118 completed_at 采用明确标注的 mergedAt，未混同 commit 时间；#119 fix1 使用量与中止时点改以追加说明记未知。
- `BackfillEvidence` 独立只读审查进一步以现有 count.py 重数 session JSONL、核对 title 日志，与 PR body 数字一致；未验证 GitHub/npm 发布结果。主会话先前「未重数」描述的是其自身核对路径，此追加条目记录后来独立复核，不改写旧条目。两位历史 k3 子代理的配置/effort 映射结论仍按编排方整理，不冒充 JSONL 中包含实际 effort 字段。
- `python3` 一次性文档检查：两份旧 task 的 YAML 解析、旧行删除白名单、branch 保留、row G 唯一单元格、Markdown 实际渲染均通过；新增行归因过滤与冲突标记为 0 hits；提交前 `git diff --check` exit 0。
- 已检索 docs/prd、ai/tasks、docs/spec 的 session_compact / session compact / HANDOFF_EVENT_UNOBSERVABLE / handoff，核对 ROADMAP §20.2 与 follow-up 登记；采用行 C 步骤 (a)–(c)，不纳入其他 backlog 项。
- `HostEvidence` 只读调查 inventory、observer、driver、validator、tests 与 CI；主会话再读关键源码确认 12 required + 1 optional、旧 diagnostic 路径与事件脱敏结构。没有执行 package 测试/build/lint。
- 主会话额外通过 `command -v omp` 与 `readlink -f` 定位本机已安装宿主，manifest 18.12.6；只读 shared-events.ts、session-entries.ts、session-maintenance.ts，确认 session_compact 的 type/compactionEntry/fromExtension、optional entry.method 与 handoff 的 method=handoff 发射路径。未启动宿主或读取凭据。该证据不替代 D11 18.11.1 的源码与运行认证。

## 当前开放决策

完整选项及风险见 [PRD §3.2](../../../docs/prd/omp-sbtd-session-compact.md)。下列全为编排方整理，状态均 **open / pending**，没有选项已获裁决。

| ID | A | B | omp 推荐 | 状态 |
|---|---|---|---|---|
| D1 payload | 真实结构验证 + 身份摘要 + 隔离窗口 | A 再要求真实 entry.method=handoff | B：推荐（仅建议，待用户裁决）；18.11.1 字段支持未知 | open / pending |
| D2 inventory | 新事件 required：13 required + 1 optional | 新事件 optional，但成功 handoff 条件必需：12 required + 2 optional | A：推荐（仅建议，待用户裁决）；两者总订阅均 14 | open / pending |
| D3 版本 | 保留 v1 标识，以精确产物/判据身份区分 | inventory/contract 与 evidence profile 使用新版本，具体值待裁决 | B：推荐（仅建议，待用户裁决） | open / pending |
| D4 关联 | 串行 handoff、同 run/session、可证明观测窗口 | 有宿主原生因果 ID 证据后按 ID 关联 | A：推荐（仅建议，待用户裁决）；不比较跨进程 seq，不虚构超时 | open / pending |
| D5 宿主 | 保留 D11 范围及 18.11.1 认证目标，补证后判断可行性 | 显式提高新判据下限，具体版本未知 | A：推荐（仅建议，待用户裁决）；不得以 18.12.6 源码代替运行认证 | open / pending |

已登记的 session_compact 证据方向、先 PRD-only 再代码 PR、代码 PR 合并后 HANDOFF_EVENT_UNOBSERVABLE 恢复硬失败不重新开放选择。trigger-blocked/not-attempted 的等级不扩大修改；后续真实验收仍必须执行成功 handoff。

## DDD Boundary Review

- Status: **confirmed**（仅术语与职责边界；不是 D1–D5 裁决或实现批准）。
- Ubiquitous language：handoff RPC 是动作，session_compact 是宿主提交 compaction 后的事实，session.compacting 是此前事件；共享 task/handoff 文档不是该宿主事件。
- Bounded contexts：宿主拥有 session/compaction，插件拥有订阅与 adapter-edge 验证，observer 拥有脱敏采集，validator 拥有覆盖判定；不把 RPC 结果当作宿主事件，不写 task 状态来代替运行证据。
- Invariants and business rules：沿用 13:13 既有裁决；不得伪造 session_switch.reason=handoff；不放宽其他门禁或把旧 evidence 重标为新认证。
- Core / supporting / generic subdomains：本项是支持性的宿主兼容证据，不涉及新增业务子域。
- Corrections to the grill-with-docs result：not-applicable，未进行完整 grill；明确区分 task 交接与宿主同 session compaction。
- Open conflicts and questions：D1–D5 待裁决，但不影响上述职责归属和 PRD-only 边界。

## DDIA Data Design Review

- Status: **blocked**（稳定设计与代码实现；不阻断交付明确标为 pending 的 PRD 草案）。
- Data owner and source of truth：宿主的真实 compaction entry 为事实，observer 的当前 run 脱敏事件为观测；RPC 成功不能补造事件，历史认证保持原解释。
- Write / read / async / failure paths：宿主提交/发射，observer 只读验证/脱敏记录，driver 记录 RPC，validator 关联并评分；当前成功 handoff 缺事件是 diagnostic，未来按既有裁决恢复硬失败。
- Consistency model：要求可归属同一次运行/同 session 的事件证据；当前没有可直接复用的 handoff 关联字段，D4 的跨流窗口边界/排空证据待定，不能用墙钟或两个 seq 建立虚假全序。
- Idempotency / ordering / retry / deduplication：同 entry 重复不构成新覆盖，窗口外/旧 run/跨 session 不合格；不新增重试框架。事件在 response 前到达不能被误拒；具体关联方案仍 pending。
- Schema / migration / backfill / rollback / replay：payload 最小字段 D1、inventory D2 与版本 D3 待裁决；不迁移或重放旧证据为新通过。仅回退文档本地提交不会改变 runtime。
- Observability and repair：保留稳定失败码与脱敏摘要；缺少有效观测不得以 RPC 成功修补；目标版本无字段/能力证据时停止对应实现，返回裁决。
- Required tests：PRD §4 正向/缺失/普通 compact 冒充/跨 run-session/schema/顺序与重复/脱敏负例；后续真实 tarball live cell 必须证明成功 handoff 的事件链，本轮未执行。
- Blocker：D1–D5 未裁决；18.11.1 payload 与所选关联方案兼容性、实际事件链证据未知。稳定设计前须补证并重跑本 review，不以草案完成标为 confirmed。

## Book Gate Plan 更新

以上追加复核取代初始 planned 快照：DDD **passed / confirmed**（仅边界）；DDIA **blocked**（仅稳定设计与后续实现）；legacy/refactor/release 继续 **not-required**（本轮没有生产代码、运行时或发布变更）。不把 pending 决策当作已批准需求。

## 独立复核与处理

- `HostEvidence`：只读调查后复核 PRD，提出顺序措辞、observer 新字段缺口、安装源码路径及 runtime 测试描述四项。已澄清先交付待裁决草案、代码 PR 前裁决；补明 observer 尚无 entry 身份摘要；将注册面明确为 stub host，不冒充真实投递。
- 两项源码推测经主会话实证校正：本机 18.12.6 包确有已读取的 src 文件；runtime.test.ts:175–185、188–198 确实比较注册键与 inventory。reviewer 再读实际宿主源文件与测试后返回 **CLEAN**，不是用「通常只有 dist」或过时注释代替实证。
- `BackfillEvidence`：PRD 范围/决策权限 **CLEAN**，数字与交叉引用一致；提出四项标题仅三 bullet、状态时间标签、顺序验收候选措辞三项。通过追加第四项与 FINAL 的对应关系解决计数；仅在 row G 状态格标清 GitHub mergedAt；顺序/重复验收注明细则待 D4，不提前锁定实现。reviewer 复查后确认 **F1/F2/F3 全部关闭，无新增发现**。
- 时间口径：#118 task 已明示 completed_at 用 mergedAt 17:03:32+08:00、git %cI 为 17:03:31+08:00。本轮未改 PRD 的独立 PR/SHA/done 时间列；不从既有个别行的 commit-time 注记推导全表未写明的时钟规则。
- 两位 reviewer 都只读；主会话唯一 writer/文档验证 controller。未运行 reviewer build/lint/tests/formatter，也未启动持久协作服务。

## 实际验证与交付边界

- 环境：Linux；Python 3.13.5、PyYAML 6.0.3、markdown-it。`python3 -c <一次性文档检查> worktree` 在 2026-10-23T17:39:55+08:00 与复核修改后的 17:41:10+08:00 均 exit 0：七个允许文件，三个 task YAML 可解析、schema_version 整数 1、strict、时间 +08:00；旧 task 仅允许三个 frontmatter 字段删除，历史 branch/正文/事件保留；row G 仅状态格；旧 omp PRD 仅新增链接；index 字母序/唯一性及链接目标通过；七个 Markdown 实际渲染及新增相对链接通过；新增行归因过滤 0 hits、冲突标记 0；`git diff --check` exit 0。
- 两次 edit 因未显示的行锚点被工具拒绝，未产生修改；随后读取确切范围再编辑成功。没有删除历史行、重写事件或产生临时脚本/fixture。
- 提交前证据为 developer-local / dirty / local-only；提交后将执行 `git diff --stat origin/main..HEAD`、`git diff --check origin/main..HEAD` 及同一 Python 检查的 HEAD 模式，并在最终交付给出真实提交与结果，不在此预写成功。
- 已调用 project-validation 与 gherkin-bdd。BDD=skipped（本轮只编写 PRD 验收意图，未修改运行行为或 feature）；后续按既有中文场景 + 英文关键词同步 feature 和 Vitest。当前没有新增永久测试、mock 或 .feature，也未把 PRD 候选称作已通过行为测试。
- lint/build/typecheck、单元/集成/E2E、宿主 live cell、CI 与发布核验均 skipped：本轮没有代码变更，且代码 PR/新判据实现不在授权范围；不复跑已知历史 lint/TaskStore 失败。Markdown 渲染是本轮实际 smoke，不是宿主认证。
- rtk=not-needed：按编排方验收使用原生 Git 和 python3。Graft=skipped：使用源码/契约证据，不启动或配置。Cross-repo context=contract-only（18.12.6 本机源码可读，目标 18.11.1 新判据证据不完整）；API Contract=missing（指待裁决的新判据；当前仓库契约已核对）；Mock Strategy=none；Final Test Report / Run Summary MD=not-needed（本轮为文档解析/渲染检查，无正式测试 runner）。
- 尚未获 D1–D5 裁决，DDIA 稳定设计门未通过；本 task 保持 checking / completed_at null。这是完整的待裁决 PRD-only 交付，不是代码、硬失败恢复、合并或发布完成。
- 恢复边界：本地 docs 提交与共享 task 记录；不调用 TaskStore、不写 active/handoff/developer/ignore，不承诺自动恢复。没有远端写入、全局配置变更或运行时回滚；回退文档不会改变已发布包。

## #120 合并回填（2026-10-23，编排方整理）

- 编排方整理：#120 已开 PR 并 squash-merge 为 `67465db93e7c6f1e6f5f43704c1d4c22ae74306d`。本轮 `git show -s --format='%H %cI' 67465db` 核对 commit 时间 `2026-10-23T17:56:18+08:00`；GitHub mergedAt `2026-10-23T17:56:19+08:00` 按编排方约 17:58 +08:00 核验材料记录，二者分别保留，completed_at 采用 mergedAt。
- 编排方整理：本次追加更新上方「实际验证与交付边界」的 checking / 未合并历史快照，done 仅指 PRD-only PR 已交付并合并；D1–D5 仍 open / pending，DDIA 稳定设计/后续实现 blocker 未解除，代码 PR 与硬失败恢复未完成。旧事件、正文及 branch 不改写；不调用 TaskStore 或执行远端操作。

## 使用的模型（FINAL，#120）

编排方整理：以下是 #120 runs 的最终统计，不是本 chore 的使用量；来源为本次编排材料，本轮未重数原始 session 日志。

| run | model / 配置与实际 thinking | assistant msgs / tool calls |
|---|---|---|
| ping | openai-codex/gpt-6-astra:high | 1 / 0 |
| main | openai-codex/gpt-6-astra:high | 37 / 76 |
| HostEvidence | scout 子代理；cursor/composer-2.5；agent default @smol、thinking medium；spawned effort=hi，实际 high | 3 / 89 |
| BackfillEvidence | reviewer 子代理；kimi-code/k3；agent default @slow = k3:max；spawned effort=med，实际 high | 32 / 42 |

- 编排方整理：无 advisor、无主任务 fallback（resolvedModelIsFallback=false），watchdog 未触发，exit 0；运行窗口为 `2026-10-23T17:27:42+08:00` → `2026-10-23T17:44:22+08:00`。
- 编排方整理：title-gen pid `283212`；ping pid `281766` 为 0 requests。main session 共 8 requests：首个 composer-2.5 请求成功，产出一个标题；第二条 7-request chain 为 composer-2.5 → k3-256k → deepseek-flash（401 provider-response-error）→ gpt-6-astra → grok-4.7 → grok-4.6 → gpt-6.1-sol，无标题产出。grok-4.7/4.6 计为 title-gen fallback，均未产出标题，不混同主任务 fallback。
- 编排方整理：子代理 title-gen 为 HostEvidence 1 request + BackfillEvidence 1 request，均 composer-2.5 success；与 main 的 8 requests 分列。
