# P2-03：live 批次数据迁移与旧路由停用

## 1. 授权与边界

- 任务：P2-03。唯一状态事实源为主 PRD §14。
- 开发起点：`main` `f922991c5aef75c08e05494f9bef94b847516711`；最初任务分支 `p2-03-live-apply`，恢复修复分支 `p2-03-successor-blocked`。任务 PR #80 已合并，当前通过 `docs/p2-03-merged-status` 独立状态 PR 收口；执行模式保持用户选择的 `default`。不是重新启动 live 迁移。
- 观察时刻 `2026-09-24T23:05:27+0800` 是建立本分支时的 date 返回，不是用户消息发生时钟。
- 用户原文：「在新的任务分支下，启动 P2-03。范围仍是冻结协议的 demo／main、Codex+OMP，源仓不纳入。这是维护窗口，授权对 live 批次做数据迁移和旧路由停用。不部署新接线，不 smoke，不 cleanup，不删备份，不 sync，不改 hooks。隔离现场继续保留。」
- 该原文授权的是 live `demo` 项目的数据迁移和旧路由停用。它不授权部署、smoke、cleanup、备份销毁、sync、hooks 修改，也不授权改写隔离现场。
- 640-skills 不纳入。P2-01 原共享 HOME 不写政策后来仅对三份按 SHA 批准的路由作出覆盖决定，实际写入见第 3 节；不扩大为共享 HOME／Skill 根的部署授权。全局卸载仍 not-allowed，`--graft-hooks` 不使用。
- 隔离批次批准不能套用到 live；本批已有绑定 live 的批准、manifest 与真实回执，禁止重封或改写。当前整改只读 live，在新隔离现场验证，不修改 P2-02 保留现场。
- 本轮用户采纳分层验收整改方案，当前有效合同为主 PRD §15.2／AC-18 与 D-IMP-15：保留受管数据／配置恢复保证，不承诺旧 Trellis 可写回退。旧审查 blocked 与旧证据缺失仍按历史保存。

## 2. Book Gate Plan

| Gate | 判定 | 状态 |
|---|---|---|
| DDIA | required；本轮只读 live，隔离生产者生成真实回执，原件与批准保持绑定；设计确认不代表验证通过 | passed |
| Legacy safety | required；阶段血统缺陷先由回归复现，再修复最新已知阶段后态选择；红绿、拒绝分支与最终精确提交验证通过，见第8/9节 | passed |
| DDD | 无新领域术语 | not-required |
| Refactoring | 未做生产结构重构；测试夹具复用用于跨环境回归，不替代真实运行证据 | not-required |
| Release readiness | required；最终精确 `58bd118` 的 C1–C6、独立证据复核和 Release Readiness 均通过，无剩余 P0/P1。任务 PR #80 已合并，完成状态按独立状态 PR 发布；旧 blocked 审查保留，第9节仅确认本阶段，不代表整体迁移／发布就绪 | passed |
| grill-with-docs | 未完整调用。沿用已冻结范围和用户本句，不新增领域边界 | not-required |

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: 用户拥有 live demo 项目和共享 live HOME。custodian kuno 拥有 backup_root、私有原件和隔离现场。本协议与主 PRD 只拥有可追踪状态。精确路径只进私有层。隔离副本的批准文件不是 live 事实源。
Write / read / async / failure paths: 本轮只读 plan live demo。失败保持 live、共享 HOME、hooks 和隔离现场不变。无队列。apply 未执行。
Consistency model: live 仍是未迁移的运行事实源。隔离演练成功不等于 live 已迁移。缺批准不能记成已 apply。
Idempotency / ordering / retry / deduplication: 不复用隔离 manifest。缺批准就停止，不伪造投影。
Schema / migration / backfill / rollback / replay: 本轮不改 schema，不 backfill，不 replay。
Observability and repair: §14 的 P2-03 为 in-progress，完成时间保持 —。plan blocked 是当前可观察事实。
Required tests: 本文件和台账不含目标绝对路径；P2-04 仍 planned；本轮未 apply。
```

本审查只确认启动可以 fail-closed。它不是 apply 通过，也不是 P2-04 解锁。

上节是启动时审查。此后 live apply 已发生；当前事实见第 3 节末条。该审查不是 done，也不是 P2-04 解锁。

`2026-09-24T23:05:27+0800` 初稿把 Release readiness 写成 not-required，理由只是本轮不部署、不发布、不 cleanup。该结论撤回。live apply 属于 migration／runtime 运维行为变更，Gate 改为 required／planned。适用验证完成前不运行 reviewer，也不把本启动写成 ready。


## 3. 当前事实

- `2026-09-24T23:10:47+0800` 只对 live `demo` 运行 migration plan。不传 `--deployment-mode`，不传 `--graft-hooks`，不使用隔离副本批准文件。
- 退出码 2，status `blocked`，reason 为 `a legacy task has no approved projections`。未生成 manifest。未 apply。
- live 项目、共享 HOME 的路由文件、hooks 和隔离现场的观察哨兵未变。
- P2-04 及之后仍为 planned。
- `2026-09-24T23:29:02+0800` 用户书面批准：bootstrap 整夹 private-only 跳过；spec 私有保全；journal 与 runtime marker private-only。归档任务只准备 redact 候选，未看前不批。未写批准文件，未 plan，未 apply。
- `2026-09-24T23:57:48+0800` 用户书面批准这份 live 归档 redact 候选。私有批准文件只绑定 live 原件：bootstrap 整夹跳过、归档 redact、spec 私有保全、journal 与 runtime marker private-only。只读 plan 退出码 2，status `blocked`，reason 为 `unowned legacy runtime content requires approval`。未覆盖的是 legacy `scripts/common/__pycache__/` 下 19 个 `.pyc`。未生成 manifest。未 apply。live 项目、共享 HOME 路由文件、hooks 和隔离现场未变。
- `2026-09-25T08:16:43+0800` 用户书面批准 19 个 pyc private-only，不发布，不删除。该决定已写入私有批准文件。重跑只读 plan 仍退出码 2，status `blocked`，reason 为 `directory contains a link or special entry`。阻断点是计划器为判断 OMP 家目录是否存在而整树扫描，碰到无关符号链接。未生成 manifest。未 apply。未改 live，未改共享路由文件，未删链接。
- `2026-09-25T09:00:24+0800` 只修了 OMP 家目录存在性检查，不扫子树。当时写了「不跟随链接」，该句不完整：只 `lstat` 了最后一级，父目录是符号链接时仍会被跟随。重跑只读 plan 退出码 2，status `blocked`，reason 为 `customized legacy global routing requires explicit reconciliation`。Codex 与 OMP 两份共享路由文件都未改。未生成 manifest。未 apply。
- `2026-09-25T09:04:58+0800` 存在性检查改为逐级 no-follow，仍不扫子树。父目录是符号链接时在分类前拒绝。重跑只读 plan 仍退出码 2，status `blocked`，reason 仍为 `customized legacy global routing requires explicit reconciliation`。未改两份共享路由，未生成 manifest，未 apply。
- `2026-09-25T09:12:15+0800` 回滚警告：不得单独回滚 `2bb2089`。那会回到 `2e5e42c`，父目录符号链接仍会被跟随。要恢复修复前的整树扫描，必须成对撤回 `2bb2089` 与 `2e5e42c` 并复验。当前安全实现保持不动。
- `2026-09-25T09:54:00+0800` 只读核对两份共享路由，未改文件。两份都不等于 v1.0.15 暂停销，也不等于当前短模板，且仍含旧工具名。OMP 与销同目录，只改了 3 个小节。Codex 少了 `i-have-adhd` 小节，交互工具节已改名，另有 8 个小节与销不同。暂停块不在任一文件中。未 plan，未 apply。
- `2026-09-25T09:55:51+0800` 撤回「保留两份定制路由、不暂停、改计划器放行」。该建议违反协议 §1 的旧路由停用。现有含旧工具名的定制路由就是所有权门的阻断对象。跳过暂停会让旧入口继续生效。plan 保持 blocked。不新增无暂停例外。未改两份路由，未改计划器，未 apply。
- `2026-09-25T10:02:11+0800` 按受控暂停方案在私有层准备了 Codex 与 OMP 两份路由候选。开头是暂停块原文。两个旧入口小节已换成一段否定句。其余定制规则保留，只改了会继续调用旧入口的句子。候选未批准，未写入 live，未改计划器，未 plan，未 apply。
- `2026-09-25T10:06:44+0800` 两份全局候选不能证明 demo 旧入口已停用。候选写明项目 `AGENTS.md` 优先于全局规则。live 项目规则第 50–57 行仍要求加载 `trellis-workflow`、读取 `.trellis/workflow.md`；第 173–193 行管理块仍要求优先使用 Trellis 命令。这是独立阻断。批准两份全局候选不得放行 plan 或 apply。项目级规则还没有单独的受控停用候选。未改项目文件，未 plan，未 apply。
- `2026-09-25T10:09:05+0800` 在私有层准备了 demo 项目规则的受控停用候选。开头是暂停块原文。`## Trellis` 到目录清单、以及 `TRELLIS:START` 到 `TRELLIS:END` 管理块已换成一段否定句。Channel 加载句和 lesson 写入旧目录的句子已改成不得执行。filesystem-safety 与非法 dispatch fail-closed 两条保留。候选未批准，未写入 live，未 plan，未 apply。批准这一份仍不能单独放行 plan。
- `2026-09-25T10:16:26+0800` 用户书面「批准」只绑定 demo 项目规则候选，checksum `cb5f99ea620f77028ab7323aae1cf4c0989230afd9385da40aa9811370e5f767`。不绑定两份全局候选。未写入 live。未改计划器。未 plan。未 apply。这一份批准不能放行 plan。
- `2026-09-25T10:18:13+0800` 撤回对两份全局候选的绑定。用户那句只批准已展示的否定句，不能覆盖未展示的 `to-spec` / `to-tickets` 落盘改写、Lessons 路径改写和 Skill 文案改写。私有批准记录已改为 withdrawn-not-binding。未写入 live。未 plan。未 apply。
- `2026-09-25T10:21:27+0800` 用户按已展示 SHA 批准两份全局候选。Codex `f206428ce4ccb2dc67b364f81264d851401cda67ad94b2f60dda1a2ccef034a9`。OMP `e52100f279aad36e2c629b3dc11dc9f12ba79fe9a1044e4b1401e5125eb16577`。写入前复核与这两个 SHA 一致。未写入 live。未改计划器。未 plan。未 apply。
- `2026-09-25T10:24:41+0800` 撤回「计划器只接受三个 SHA」的实现建议。共享暂停校验只认可 pinned `ensure-file-block`，apply 只追加暂停块，不写入已批候选。项目 `AGENTS.md` 的现有操作只删管理块。硬编码放行会让 plan 变绿却执行错误暂停。未改计划器，未写 live，未 plan。
- `2026-09-26T13:51:48+0800` 记入 live apply 回执。观察时刻，不是用户消息发生时钟，也不是回执时钟。用户原文「把这次 apply 回执记入台账，不要 cleanup」。回执 finished_at 为 `2026-09-26T13:37:05.318875+08:00`，status `applied`，apply_id `9ad029161fe57421a682ed44adaddf8c54d73c45d84eea7ea3341d5fa4497c6f`，manifest `81a0c3d4bc63d906da67f6502b4f218d14a0d410376ad4ad9b354d93f5e280d2`。单独 apply 确认是用户原文「apply」。写入对象是按已展示 SHA 批准的 Orca Codex 候选 `3e22679bf5fac0a6c36cc3840b4c707e3f8c12a20d8787a3d20246cd21f1209e`、OMP 候选 `ea7b3ce951864ff55964ce4cab9a6eba024d610be0560b24795d1ae10d7b3440`，以及此前 demo 候选 `cb5f99ea620f77028ab7323aae1cf4c0989230afd9385da40aa9811370e5f767`。旧全局候选 `f206428c…` / `e52100f2…` 不是本次写入对象。共享两项与项目内 106 项成功。`~/.codex` 未写。`.trellis` 仍在。精确路径只在私有层。不 cleanup，不删备份，不部署，不 smoke，不 sync，不改 hooks。隔离现场保留。P2-03 仍 in-progress。P2-04 仍 planned。
- `2026-09-26T14:58:49+0800` 只读 Release Readiness Review 为 blocked。观察时刻，不是用户消息发生时钟。用户原文「按你推荐的下一步执行」。审查不是 apply 作者自证。回执仍是 applied，三份已批路由与候选 SHA 一致，`~/.codex` 未写。P1：带回执重试时，路由重绑先对照批准前快照，已成功替换在跳过前变成 `state-conflict`。未改代码，未复跑 live apply。不 cleanup，不部署，不启动 P2-04。P2-03 仍 in-progress。
- `2026-09-26T17:25:32+0800` 修复带回执的路由重试。观察时刻，不是用户消息发生时钟。用户原文「推荐的下一步是什么，请推进」。只改临时目录证明：已成功且 live 仍等于回执 `after` 时跳过，不写第二次；live 被改后仍是 `retry-conflict`。首次 apply 仍对照批准前快照。未复跑 live apply。审查未重开为 ready。P2-03 仍 in-progress。
- `2026-09-26T17:33:19+0800` 本次 live 回执仍被版本门挡住。观察时刻，不是用户消息发生时钟。重试门之前先比对 `tool_versions` 与当前 `runtime_versions()`。live manifest 在 `sbtd_migration.py` 修改前密封，新代码消费它会先报 `version-conflict`。同版本临时测试不证明本次 live 批次可重试。不重封 manifest，不放松版本门。本次 live 批次的 AC-18 未修复。P2-03 仍 in-progress。
- `2026-09-26T21:21:19+08:00` 任务 PR #76 已合并，未标 done。观察时刻，不是用户消息发生时钟。用户原文「CI运行完毕了，都成功了。请继续下一步」。任务 PR #76 已于 GitHub `2026-09-26T13:16:43Z` 合并，merge `bf3af67a28162335eb2e0121e133e6469f613191`。合并前 head `4726245c687a9a0f3d2c9106cd05a0db24de307d` 的 linux-full、macos-bash-installer、windows-powershell-installer 均为 SUCCESS。Codex 对 `bb9c4ec` 留了两条 P2 建议，不是批准；合并使用已授权的 `--admin`。这两条建议未修。不标 done。本次 live 批次的 AC-18 仍未修复。不重封 manifest，不放松版本门。不 cleanup，不部署，不启动 P2-04。P2-03 仍 in-progress。
- `2026-09-26T21:51:32+0800` 重开的只读 Release Readiness Review 为 blocked。观察时刻，不是用户消息发生时钟。用户原文「重开审查，不标 done」。审查不是 apply 作者自证。`apply_migration` 在 `_retry_block` 之前调用 `_validate_context`；`manifest.payload.tool_versions` 不等于当前 `runtime_versions()` 即 `version-conflict`。`runtime_versions()` 摘要包含 `scripts/sbtd_migration.py` 与 `assets/routing-approval.pub`。`ApprovedRoutingReplacementTests.test_receipt_retry_skips_an_applied_routing_replacement` mock 了同版本 `runtime_versions`，只证明临时目录行为，不证明本次已密封 live manifest。AC-18 的 partial receipt 重试是 required check，不能改写成 residual risk。`plan_recovery` 与 `apply_recovery` 也调用 `_validate_context`。`plan_recovery` 只把 `state-conflict` 收成 blocked plan，`version-conflict` 会直接抛出，得不到恢复计划。`apply_recovery` 同样先过版本门。备份保留不等于本次已密封 manifest 的可执行恢复。该限制同样是 required check，不能改写成 residual risk。因此不能关闭 P2-03。不重封 manifest，不放松版本门，不复跑 live apply，也不把备份保留写成可执行恢复。不 cleanup，不部署，不启动 P2-04，不标 done。完成时间保持 —。
- `2026-09-26T22:39:57+0800` 只读后继 plan 被批准前态挡住。观察时刻，不是用户消息发生时钟。用户原文「计划走你说的“能通过规则的关闭形状只有一个新的、版本一致的证据链”，请实施」。未完整调用 grill-with-docs：用户已明确选择先前说出的关闭形状，没有新的领域边界。用当前代码、同一项目、同一 vault、同一 publication decisions 和同一 routing approval 跑 migration plan，不传私钥，不写 live。退出码 2，status blocked，reason 为 `a routing target no longer matches its approval`。Codex、OMP、demo 三份 live 路由都等于已批 candidate，不等于 approval before。无批准 plan 也不能绑定当前 live：它既不是 ownership pin，也不是当前模板。未制造新批准，未签名，未 apply，未恢复 live，未标 done。P2-03 仍 in-progress。
- `2026-09-27T15:56:33+0800` 恢复续作按绑定回执的最新状态判断。观察时刻，不是用户消息发生时钟。上一会话建议先修恢复续作，不执行 108 步 live 回滚，不标 done。本轮只改这个校验：已成功的逆向步骤按恢复回执最新 `after` 判断，未动过的资源仍必须等于 apply `after`。临时目录红测先复现 `lineage-conflict`，修复后续作退出码 0。未列出后继和坏签名仍是 `version-conflict`。配对已用内存密钥重签，后继为 `runtime-sha256:74de3e3c7a5821fe7390b5db82e73b75b9edf9bb47775383e233b0dde640b20e`。未执行 live 回滚，未重开审查，不标 done。P2-03 仍 in-progress。
- `2026-09-27T16:41:20+0800` 同一资源的多相位逆向续作只看最后一次成功状态。观察时刻，不是用户消息发生时钟。顾问指出续作预检会把更早的成功 `after` 当成当前文件。当前计划器不会发出这种步骤，契约允许。预检已收窄。真实 `apply_recovery` 对两步累计回执返回 `already-complete`，文件未改。`sbtd_recovery.py` 在指纹内，配对再次重签，后继为 `runtime-sha256:1f645a3abefc1279d4e1937d5f847feed41c57cb50a8d04d45de0e5abe722bda`。未执行 live 回滚，不标 done。P2-03 仍 in-progress。
- `2026-09-27T17:32:39+0800` 多相位续作补了合法绑定证据，不把 mock 绿测当成闭环。观察时刻，不是用户消息发生时钟。只 mock 加载和绑定门的测试仍只证明预检选择。新测试用批准路由替换加 `init-projects` 生成同一 `AGENTS.md` 的 apply 与 deploy，再经真实 `plan_recovery` 和两次 `apply_recovery`。续作是 `already-complete`，文件未改。未执行 live 回滚，不标 done。P2-03 仍 in-progress。
- `2026-09-27T18:15:26+0800` 独立审查 blocked，旧运行时写探针停止。观察时刻，不是用户消息发生时钟。可审查提交 `bb8eb0b3fe68e151c1dea6aec285ff294f321116`。独立 Release Readiness Review 为 blocked。未执行 live recovery apply 不是关闭条件。旧运行时可写证据仍 blocked：全局规则禁止初始化或调用已退役 Trellis 运行时。本轮在收到阻断前已经执行过 `trellis --version` 和 `trellis --help`，没有执行 `init` 或其他写命令。随后停止。安装元数据只读见到 `@mindfoldhq/trellis` `0.6.17`。隔离副本和 live 未改。不把这次调用写成可写证据。P2-03 仍 in-progress。
- `2026-09-27T18:29:41+0800` 不把缺证据改成完成。观察时刻，不是用户消息发生时钟。用户要完成 P2-03。整体评估后两项 required check 不能在现行规则下变成 pass：旧 Trellis 写操作不能再调用；密封 live 批次没有原始 partial apply receipt，补造只会在写前被拒绝，不是正向证明。不改 AC-18，不标 done，不跑 108 步回滚。P2-03 仍 in-progress。
- `2026-09-27T19:15:12+0800` 新关闭合同已写入，尚未审查。观察时刻，不是用户消息发生时钟。用户选择合法路径并要求落地。主 PRD §15.2 是新合同。原 AC-18 两项仍未满足，不涂成通过。独立审查写成 ready 之前不标 done。P2-03 仍 in-progress。
- `2026-09-27T19:20:54+0800` 新关闭合同审查 blocked。观察时刻，不是用户消息发生时钟。两份独立审查都判定主 PRD §15.2 是非法 waiver，不是新范围。第 14.5 节仍把 P2-03 绑在 AC-18 上。不标 done。P2-03 仍 in-progress。
- `2026-09-27T19:39:44+0800` 另立 P2-06，不关闭 P2-03。观察时刻，不是用户消息发生时钟。用户要求先评估 advisor，再另立不声称 AC-18 已通过的新任务。advisor 成立，不把 blocked 改成通过。P2-06 只登记已执行事实。P2-03 仍 in-progress。P2-04 仍 planned。
- `2026-09-27T20:47:29+08:00` 用户采纳整改方案并选择 default。观察时刻，不是用户消息发生时钟。有效 AC-18 与关闭合同同步修订，旧运行时可写保证明确撤回但不声称旧检查通过。C1–C6 仍 required，当前未完成本轮验证或独立审查；不改 live，不执行 108 步回滚，不调用 Trellis，不启动 P2-04。P2-06 保留事实登记，不替代 P2-03。

## 4. 明确不做

- 不把隔离副本的批准、manifest 或回执套到 live。
- 不改 P2-02 保留现场；仅本轮新建的私有隔离现场允许验证写入。不删备份，不 cleanup，不 sync，不改 hooks，不部署 live，不做 host smoke。
- 不把本启动写成 done。完成时间留到 live apply 回执和任务 PR 之后的状态 PR。
- 不启动 P2-04。
- 不得单独回滚 `2bb2089`。它的父提交 `2e5e42c` 只检查最后一级。成对撤回这两笔才会回到整树扫描，撤回后必须复验。

## 5. apply 前的历史前置条件（后续事实见第 3 节）

1. live `demo` 的批准投影必须绑定 live 原件，而不是隔离副本。缺批准时保持 blocked。
2. 批准不得要求改 hooks、删备份、cleanup，或写入隔离现场。
3. 只有新的 live plan 为 `planned` 并生成 manifest 后，才可以按本授权 apply。该 apply 仍不部署、不 smoke。
4. 归档 redact 候选已经用户书面批准，并写入私有批准文件。它仍不是 apply 授权；plan 尚未 `planned`。
5. 三份暂停候选已按 checksum 书面批准，但都未写入 live。第 6 节已补契约缺口和失败路径。实现范围不是只改计划器。该设计尚未被接受为实现授权。接受前不改 schema、计划器、apply 或 verify，不写 live。

以上记录 apply 前的门禁，不要求已经成功的批次重新 plan/apply。当前继续与关闭仅按主 PRD §15.2；不得用本节历史授权触发新 live 写入。

## 6. 已批路由候选的复制与回读设计

`2026-09-25T10:42:55+0800` 只出设计，不改代码。这不是实现授权，也不是 apply 授权。

现有共享暂停只认可 pinned `ensure-file-block`，apply 只追加固定暂停块。项目 `AGENTS.md` 若命中所有权哈希，现有操作只删除 `TRELLIS` 管理块。这两条都不能写入已批全文。不得在源码里硬编码三个 SHA 来放行它们。

三项目标按角色解析，不按 SHA 名单解析：

1. Codex 全局路由：当前 Codex home 下的 `AGENTS.md`。
2. OMP 全局路由：当前 OMP home 下的全局 `AGENTS.md`。
3. demo 项目路由：本次选中的 live `demo` 根下的 `AGENTS.md`。

私有批准记录是绑定事实源。每项只含角色、live 目标、原件快照、候选引用和批准句。候选引用的 checksum 必须等于已批 SHA。源码不保存这三个 SHA。测试只用夹具，不把 live checksum 写进仓库。

plan 对每一项重新快照 live 目标和候选。任一与批准记录不一致就 blocked，不自动改批准记录。候选必须以内置暂停块原文开头。通过后只发一条既有 `copy-file` 操作：目标是 live 路径，来源是候选引用，前置状态是 live 快照，所有权指向批准记录而不是暂停销。选择器使用新的 `approved-routing-replacement`，避免被现有暂停校验当成 `ensure-file-block`。同一目标不得再发追加暂停块或只删管理块。两条同时出现就 blocked。

apply 走现有 `copy-file` 路径，写入候选全文，然后回读快照。回读 checksum 必须等于候选状态，也必须等于回执 `after`。不得走追加暂停块。

verify 再读 live 目标。当前快照必须等于回执 `after`，也必须等于已批候选 checksum。不一致就是 drift，不得报已停用。checksum 一致即全文一致，不再用关键字扫描代替回读。

这三项写入前仍须另有 `planned` manifest 和单独的 apply 确认。本设计不授权现在写 live，不授权部署、smoke、cleanup、删备份、sync 或改 hooks。

`2026-09-25T11:01:28+0800` 补失败路径。当时的契约缺口已由后续实现关闭，不改写该时刻的历史。

`2026-09-25T11:56:19+0800` 工作树实现了第 6 节的复制与回读，未写 live，未 plan，未 apply 真实家目录。schema 接受 `approved-candidate`。plan 只在批准记录、live 快照和候选一致，且候选以暂停块开头时发 `copy-file`。共享校验和项目闭包接受该形状，并拒绝同一目标再追加暂停块或只删管理块。apply 写入候选全文并回读。verify 重开候选，不一致即 `approved-routing-drift`。部分写入重试返回 `unsafe-retry`，不退回追加暂停块。

`2026-09-25T12:22:59+0800` 补批准文件绑定。形状检查不再单独放行重封装的 `copy-file`。apply 前按批准文件逐项重建，角色、目标和候选必须一致，引用必须在私有 vault 内。批准文件漂移在写入前 `state-conflict`。未写 live。

本轮增加写入前鉴权边界：批准文件、路由候选和项目根不能落在会写 evidence/apply 的目录里。manifest 目录若在 `backup_root` 内，该 vault 也算写入根。批准文件必须存在，且 SHA 必须等于 sealed 记录。apply 另要求调用方传入 `--routing-approvals`；SHA 对不上、或操作不能从该文件重建，就在 `_render_resource` 前拒绝。无批准必须显式 `--no-routing-approvals`，且不得再对 `AGENTS.md` 追加暂停块或删除管理块。批准文件必须带安装包公钥验得过的签名。公钥是 `assets/routing-approval.pub`，由安装副本路径加载，不从 manifest 或调用方路径读。调用方把 `--routing-approvals` 指到攻击者文件时，签名对不上安装包公钥就拒绝。未写 live。

失败路径仍是契约，不是已全部用测试覆盖的清单：

- 批准记录缺失、字段不全、目标重复或候选 checksum 与记录不一致：plan blocked。零写入。
- live 快照与批准记录中的原件不一致，或候选文件与记录中的候选快照不一致：plan blocked，`state-conflict`。不自动改批准记录。
- 候选不以暂停块原文开头：plan blocked，`candidate-conflict`。已有测试。
- 同一目标同时出现 `copy-file` 与 `ensure-file-block` 或管理块删除：plan blocked，`approval-conflict`。
- apply 时候选字节已变：`state-conflict`，该资源不写。
- apply 写入后回读不等于候选快照：`post-state-conflict`。停止后续资源。回执保留实际 `after`，不得报 succeeded。
- verify 发现 live 不等于候选快照：`approved-routing-drift`。已有测试。不得报已停用。
- 重试时上次已成功且 live 仍等于 `after`：跳过，不写第二次。带回执重试不再先用 live 当前字节对照批准前快照。已有临时目录测试。首次 apply 仍对照批准前快照。
- 重试时 live 与上次 `after` 不一致：`retry-conflict`。
- 部分写入或未知写入：`unsafe-retry`。已有测试。不得退回追加暂停块。
- 批准文件、路由候选或项目根落在会写 evidence/apply 的目录里，包括 manifest 目录位于 `backup_root` 内：apply 前 `private-scope`，不得写入。批准文件缺失或 SHA 与 sealed 记录不一致：`state-conflict`，不得写入。证据目录留在 vault 外再换 vault，而调用方仍传原批准文件：`state-conflict`，不得写入。把 `routing_approvals` 改成 null 后再删管理块，且调用方传 `--no-routing-approvals`：`approval-conflict`，不得写入。调用方把 `--routing-approvals` 指到攻击者文件，且该文件不是安装包公钥的有效签名：`approval-conflict`，不得写入。
- 批准文件在 plan 之后被改：`state-conflict`。已有测试。不得写入。

已测的是临时目录里的 Codex 全局、OMP 全局和 demo 项目目标：写入候选全文、错误路径或批外目标被拒、重封装不写 live、候选漂移失败。没有真实家目录的 planned manifest，也没有 apply 确认。不得把这次工作树实现当成 live 路由已停用。

## 7. 分层验收执行证据（待独立就绪裁决）

观察时刻 `2026-09-27T22:12:58+0800`。第 6 节末尾“没有真实 manifest／apply 确认”属于当时实现期记录，不覆盖第 3 节后来发生的 live apply。当前合同为主 PRD §15.2。

验证候选为 clean `5eee55ea04ac166ed5e27f5cedb69249ad3a0b68`；绝对解释器、Python patch 与依赖版本均记录在私有报告。实际运行指纹 `runtime-sha256:1f645a3abefc1279d4e1937d5f847feed41c57cb50a8d04d45de0e5abe722bda` 等于已签名后继，前驱仍绑定原 live manifest。未安装依赖、未重签、未改生产实现。

| 验收 | 实际结果 | 证据与限制 |
|---|---|---|
| C1 | 108 个 apply 结果当前 after／备份匹配，一个完整来源目录备份核验，三份批准路由一致 | 私有 live-audit r3 原生 JSON 与 before/after；全量只读，不是重新 apply |
| C2 | 原 apply 与 already-complete 回执通过绑定／累计校验，资源结果相等；历史原生 toolResult `b497ee08` 记录 live_changed 0 | 该历史输出与来源已保全，不重标为当前提交运行，不再次执行 live retry |
| C3 | 真实 plan→os.link 故障→生产者 partial 回执→重试→already-complete，44 条断言通过；已成功目标内容／inode／mtime和写调用观察未变 | 新隔离报告 A，当前实际指纹；没有绑定／版本／累计／签名校验替身 |
| C4 | 真实恢复→依赖级故障→partial recovery 回执→续作→already-complete，60 条断言通过；两个项目共享路由实际只有一个共享结果、一个逆向步骤、一次目标恢复，重试不改目标 | 新隔离报告 B 与 shared-proof。共享安装副本只替换独立合成公钥，其余文件逐字等于候选 archive；实际签名／验签，不读取真实私钥，不称为生产信任根实测 |
| C4 多相位 | 合法绑定的同资源 deploy→apply 逆向完成后，再次恢复为 already-complete；实际隔离 manifest／回执已保留 | `test_bound_multi_phase_continuation_uses_real_recovery_gates` 通过；有合成公钥提供者及 graph/smoke 依赖替身，恢复绑定／上下文／累计校验真实执行，不称为 host/full-stack |
| C5 | 当前只读 recovery plan 为 planned、无冲突；109 个声明资源完整闭包、108 个实际逆向步骤；核验前后受管状态相等 | 一个额外声明资源是未执行的 cleanup 资源。只读计划不证明未来 live 写权限／容量或每步执行，不运行 108 步 live 回滚 |
| C6 | 隔离漂移／未知写入／不安全重试拒绝的44条断言通过；坏签名、未列出后继、缺完整证据负例通过；连同多相位共4项无跳过 | 未知写入为明确标注的合成拒绝输入，不冒充真实历史故障；正向 partial 回执由生产者实际生成 |
| 原生 CLI | 新隔离 onboard.py migration plan/apply/完整重试与 recovery plan/apply/完整重试全部退出0，27条断言通过，目标最终恢复原态 | 报告 E；子进程不重写由快照证明，不声称父进程观察了子进程内部调用 |

精确候选全量命令：`python -B -m unittest discover -s tests -p 'test_*.py'`，1160 tests／1781.605s／OK（8 skipped），运行前后源码状态一致；四项补充边界另有原生输出及同 stem 中文汇总。8项skip不算对应平台／host通过。RTK `skipped-for-report`；本仓库不建 `.feature`，场景沿主 PRD C1–C6，证据映射如上。

失败记录全部保留：普通 python3 缺 tomlkit，改用历史绝对解释器后指纹匹配；live首轮300s timeout不计通过；r2校验脚本把109个声明资源误要求为108，改为完整集合与实际逆向集合断言后r3通过；隔离首轮外围写保护误拒自己的fdopen，改为用macOS F_GETPATH验证描述符位于隔离根，完整重跑通过。这些修正未改生产实现。

主隔离脚本的可选D“用生产公钥对应私钥重签合成批准”保持not-run，不读取真实私钥；所需覆盖分别由C1真实安装公钥批准验证及C4合成信任根共享恢复提供，不称D通过。runtime_readiness始终not-verified；旧可写检查与缺失live partial历史不改成通过。

合同复审ready-for-validation，源代码独立安全复核无P0/P1；本节不是最终Release Readiness ready或done。原始路径、快照、回执、raw+同stem中文报告及checksum清单仅保存在本轮私有证据目录。任务PR／状态PR与P2-04授权尚未闭环。

## 8. 独立就绪审查发现的阶段血统修复

针对 `5eee55e` 的独立审查确认第7节 C1–C6 证据通过，但总体 needs-mitigation：签名例外面向整个前驱运行时，不只本次无部署的 live manifest；合法部署写入 apply／deploy 重叠资源后，旧血统检查仍要求 apply after，阻断部署重试及恢复。早先“代码无P0/P1”的裁决已由安全审查撤回，不把本次发现转成非阻塞风险。

回归先复现 predecessor 重叠部署在 `load_deployment_context` 报 lineage-conflict，同运行时对照通过。最小修复把调用者已经绑定的 deployment／cleanup 传入血统检查，按已知最新正向后态再覆盖已成功逆向状态；完整成功 apply、签名配对、未知状态、普通部分写入重试和恢复备份门保持。真实写后故障的部署仍拒绝普通重试，但可凭完整已知前后态及备份恢复；缺失阶段、漂移、错误 apply 绑定、未知后态和缺失／损坏备份负例通过。

生产实现指纹已变化，原第7节 `5eee55e`／`1f645a3a…` 的证据仅属该历史候选，不能直接冒充修复后通过。使用仅驻内存的独立密钥重签，前驱不变，新后继为 `runtime-sha256:0ba72e4ebaf84578c7bf83233d847a3874065be3a8ebc9ed951b9a13b1f319be`；未读取路由批准私钥，未执行live写入。当前待修复后完整复验、独立复审和两层PR收口。

修复候选 `b0c36e4` 的本地精确全量为1162 tests／396.669s／OK（8 skipped），受影响169项／89.801s／OK；新指纹下live只读全量、新隔离producer/CLI、共享恢复与4项绑定边界复验通过。首次PR #80 CI（run `36327598712`）macOS／Windows jobs通过，Linux失败：两条旧测试把本机运维配对硬套到Python3.12 CI。失败记录保留；删除源码字符串／固定环境偶然断言，前驱恢复改用独立签名夹具，仍真实校验当前解释器指纹、签名和恢复链，不改生产版本门。测试修订后的精确CI与最终审查仍待完成，不能用上述本地绿测替代。

## 9. 最终验收与任务合并

用户在独立就绪审查完成后要求暂停；本次明确「确认，请继续」，恢复的仅是任务 PR／状态 PR 收口及 P2-06 事实登记处理，不包含 P2-04 或 live 写入。

- 最终候选：`58bd1180913d9e639b98d762dbadf2445ed48618`。原生全量 `python -B -m unittest discover -s tests -p 'test_*.py'`：1161 tests／991.387s／OK（8 skipped），运行前后 source unchanged。删除一条源码／固定环境偶然断言使1162降为1161，不是跳过失败用例；签名、漂移和恢复行为回归保留。
- [精确 head CI](https://github.com/KunoLu/640-skills/actions/runs/36328556337)：Linux 全量、macOS Bash、Windows PowerShell 三个平台 job 均 SUCCESS，包括各自 clean-checkout 门。
- 最终运行指纹仍为 `runtime-sha256:0ba72e4ebaf84578c7bf83233d847a3874065be3a8ebc9ed951b9a13b1f319be`。本候选重新执行 live 全量只读核验、新隔离 producer／CLI、共享恢复和多相位边界，不用第7节旧指纹证据替代。
- C1：108 个 apply 后态、全部备份／保全原件及三份批准路由一致。C2：原完整重试回执与历史零写入观察交叉一致，不再次执行 live retry。
- C3／C4：新隔离真实 partial apply／recovery 回执续作、no-op、双项目共享只恢复一次，以及合法多相位／前驱阶段恢复通过；合成信任根、旧生产者身份模拟、graph/smoke 依赖替身均保留标注，不称 host/full-stack。
- C5：只读 live recovery plan 为 planned；完整109声明资源、108实际逆向步骤，before/after一致。C6：漂移、未知／缺失证据、坏签名、未列出后继、损坏／缺失备份和不安全重试拒绝通过；合成负例不冒充历史故障。
- 独立 `P203ReadinessFinal`：Release Readiness **ready**，仅本阶段代码／证据门，无剩余 P0/P1。独立 `P203EvidenceAudit`：8/8索引hash匹配，原生报告、回执链、声明集合与CI head一致，无P0/P1证据缺口。原始回执不复制到共享仓库，复核者对live血统的直接审计限于记录的生产者验证及交叉一致性，不声称重新运行live。
- Ruff changed files通过；ty基线3条／当前3条、无新增，不声称完整ty通过。8项skip不算相应平台／host通过；可选生产私钥重签场景D保持not-run，所需边界分别由live安装公钥只读核验和独立合成信任根执行证明。

```text
Release Readiness Review
Status: ready（P2-03 当前分层验收，不是 v2 发布）
Production path and affected users / systems: 已 apply 的 demo 批次及三份批准路由，继续受维护窗口约束。
Failure modes and safeguards: 真实阶段绑定、签名版本门、已知前后态、原件／备份、累计回执和未知写入 fail-closed；历史失败全部保留。
Capacity / backpressure / limits: 有限离线批次，无队列／服务背压；多资源不宣称原子事务。
Observability / alerts / runbook: 私有原生报告、回执与完整性索引；人工对账，未建立服务告警。
Rollout / migration / rollback / cleanup: 未执行 live 回滚／新部署／cleanup；只读计划不证明未来写权限、空间或逐步恢复执行；原现场和备份保留。
Required validation and result: 精确58bd118的C1–C6、原生CLI、全量与三平台CI通过，独立审查无剩余P0/P1。
Optional checks, accountable owner acceptance, and residual risk: D未运行且未称通过；旧Trellis可写回退已由用户明确撤回，runtime_readiness保持not-verified，旧缺证据不改成通过。
```

[任务 PR #80](https://github.com/KunoLu/640-skills/pull/80) 于 `2026-09-28T02:03:20Z` 确认 MERGED，merge `09d430e1725d630b81d56e25dbf8b83161548977`；实际合并树等于已验证 head。按既有授权使用 `--admin` 合并，不能把 GitHub 当时的 REVIEW_REQUIRED 显示写成线上 reviewer approval。

完成记录时间为 `2026-09-28T10:13:26+0800`，通过本独立状态 PR 写回主 PRD。该时间是验收与任务合并均确认后的台账更新时间；状态 PR 闭环前不解除后续依赖，闭环后也不自动执行 P2-04。P2-03 done 不等于整体迁移完成、恢复日常 Agent 工作、清理或正式发布。

本轮维护判断：README.md、README.html 的恢复保证说明已随任务 PR 合并，本状态更新不改变其含义，无需再改；版本化 automation prompt 的评估契约不变，无需再改且不读写 live automation；CHANGELOG 已记录修复与兼容边界，状态登记不是新能力／发布变化，不重复新增 release note。
