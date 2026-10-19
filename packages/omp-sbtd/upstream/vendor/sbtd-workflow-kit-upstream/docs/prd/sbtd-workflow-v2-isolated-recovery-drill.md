# P2-02：隔离副本迁移及可调用恢复演练

## 1. 授权与边界

- 任务：P2-02；唯一状态事实源为[主 PRD §14](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md#14-优先级实施台账)。
- 开发起点：`main` `0f7bc979f63f4feeff3584750b4e6e1c6b831ed6`；任务分支 `p2-02-isolated-recovery-drill`。
- 用户授权原文：「启动 P2-02 任务」。观察时刻 `2026-09-23T16:25:17+0800` 是写入本协议时的 date 返回，不是用户消息发生时钟。
- 该原文只打开本任务。它不撤回 P2-01 已记录的「现在先别建」，也不授权建目录、填充、复制、plan、apply、deploy、cleanup、恢复执行或改 live。
- 范围只继承[冻结协议](sbtd-workflow-v2-migration-scope-freeze.md)：逻辑名 `demo`、声明 `main`、Codex+OMP、custodian `kuno`、源仓不纳入、闭包仅 `demo`。精确路径仍只在私有层。
- 没有本机 workflow sync、hooks opt-in、全局卸载、rc/tag、正式发布、备份销毁或 P2-03 授权。
- 后续用户原文「撤回「现在先别建」，开始创建隔离根」只授权创建已确认的空隔离根。观察时刻 `2026-09-23T16:32:42+0800`。该原文不授权填充、复制或 apply。

未完整调用 `grill-with-docs`。原因：本项不新增产品边界；项目、host、隔离政策和「先别建」已由冻结协议与主 PRD 固定。本启动不改变这些事实。

## 2. Book Gate Plan

Gate Plan 只使用 `planned / running / passed / blocked / not-required`。审查结论写在下一节，不另造终态。

| Gate | 判定／触发事实 | 状态 |
|---|---|---|
| DDIA | required；本项将涉及隔离副本、备份、迁移收据和可调用恢复。启动协议稳定前必须审查 | passed |
| Legacy safety | 无既有行为缺陷修复，不改生产运行代码 | not-required |
| DDD | 无新领域术语或上下文归属变化 | not-required |
| Refactoring | 不改生产实现 | not-required |
| Release readiness | 本启动不是部署、发布或真实迁移完成 | not-required |
| grill-with-docs | 沿用已冻结边界，无新实质歧义 | not-required |


启动表只记录协议启动时的范围。其后 migration planner 的批准行为已经改变，Refactoring、Legacy 与 DDIA 不再因「不改生产实现」而 not-required。启动表单元格不改写成当时已通过这些门。这些门没有在首次生产编辑前运行。本文件不把独立 review 写成通过。

本仓库仍不创建 `.trellis/`、`ai/tasks/` 或 `.feature`。当前项目根有 `AGENTS.md` 且没有 `.trellis/`，因此尚未 `trellis init`；本任务不补做该初始化。

### 2.1 DDIA Data Design Review

```text
DDIA Data Design Review
Status: confirmed
Data owner and source of truth: 用户拥有 live 项目树和 live HOME。custodian kuno 拥有 backup_root、私有原件和尚未创建的隔离副本。本协议与主 PRD 只拥有可追踪状态：任务已打开、演练尚未执行。manifest 尚不存在，不能当事实源。
Write / read / async / failure paths: 本次只写本协议和主 PRD 台账。不读 live 项目，不建隔离根，不复制，不写 HOME。后续副本写入必须发生在已确认且仍为空的隔离根内，并先证明它在 backup_root 之外且不互相包含。失败保持 live 不变，不删除备份。无队列或后台任务。
Consistency model: live 在本项完成前仍是唯一运行事实源。隔离演练成功不等于 live 已迁移。缺证据不能记成已恢复。
Idempotency / ordering / retry / deduplication: 重复启动不新增任务 ID，也不把 planned 再写成 done。建目录、填充、plan、apply、deploy、cleanup、恢复执行各自需要本协议明确的后续授权；缺任一项就停止。恢复只消费已绑定证据，不猜测。
Schema / migration / backfill / rollback / replay: 本启动不改迁移 schema，不 backfill，不 replay。撤回本启动只撤回协议和台账 in-progress；因尚未写用户数据，无数据回放。
Observability and repair: §14 的 P2-02 为 in-progress，完成时间保持 —。隔离根未创建是当前可观察事实。回读失败或路径漂移时不得继续。
Required tests: 证明本文件和本次台账更新不含目标绝对路径、HEAD、原件指纹或项目规则正文；P2-03 仍为 planned；本启动未创建隔离目录。
```

本审查只确认启动协议可以 fail-closed。它不是演练通过，也不是 P2-03 解锁。
上节是启动时审查。此后隔离根已创建并填充；隔离 apply、一次恢复和再次 apply 已发生。失败模型不变，live 仍是唯一运行事实源。当时的「未创建」和「未填充」都不再是当前边界。

## 3. 当前事实

- `2026-09-24T09:54:23+0800` 建立隔离 demo 副本时尚未 apply。活动 Codex `hooks.state` 现在只有指向该副本的条目，无 live HOME 路径、无他项路径、无敏感 `env`。精确路径只在私有记录。禁止用该配置启动 host。
- 原 `0.6.15` 副本已于 `2026-09-24T11:54:07+0800` 删除。12:21 的 plan block 已由后续用户决定解除：`2026-09-24T15:47:23+0800` 的只读 plan 为 planned 并生成 manifest。隔离 apply 回执于 `2026-09-24T16:05:32+0800` 完成，状态 `applied`，消费的是该 manifest。用户选择恢复后，恢复回执于 `2026-09-24T17:08:48+0800` 为 `restored`。`2026-09-24T17:11:22+0800` 的 deployment plan 为 planned 并生成新 manifest，解除 16:55 的已有目标 block。带 deployment 的再次 apply 于 `2026-09-24T17:13:43+0800` 完成，状态 `applied`，消费的是这次 manifest。
- 用户后来只同意在 TEMP 另设 npm prefix。私有记录没有把「只读 plan」记成另一项用户同意。TEMP Graft 安装、`init-projects` 和官方 verify 超出该同意，不撤回。deployment evidence 于 `2026-09-24T17:43:24+0800` 为 `succeeded`；官方 verify 于 `2026-09-24T17:45:34+0800` 返回 `verified`。`verified` 不是这些写入的事后同意，也不是 cleanup 或 done 授权。`2026-09-24T17:59:27+0800` 用户要求保留现场。未 cleanup。
- `2026-09-24T18:05:21+0800` 在隔离副本运行 `trellis platforms --json`，退出码 0，列出 `codex` 和 `omp`。这只证明只读探测可调用，不证明写操作、恢复或 host 可用。写操作仍按缺证据作安全拒绝。
- P2-03 及之后仍为 planned。

## 4. 明确不做

- 不读取或修改 live 项目、live HOME、源仓以外的用户项目。
- 不恢复整树复制，不复制认证文件，不把隔离根放进 `backup_root`。禁止用含他项路径或敏感字段的配置启动 host。不 cleanup，不把未经事前授权的 verify 当成 cleanup 同意，不启动 P2-03。
- 不 sync，不改 hooks，不卸载全局工具，不打 tag，不删备份。
- 不把本启动写成 checking 或 done。完成时间留到验收和任务 PR 合并之后的状态 PR。

## 5. 完成前必须另有授权的门

1. 已满足：用户撤回「现在先别建」后，已创建已确认的隔离根并回读它在 `backup_root` 之外。其后发生过未完成的部分复制；该句不是当前终点，选择性填充和隔离 apply 已经发生。
2. 活动配置的 `hooks.state` 已只指向隔离 demo 副本。这不等于演练通过，也不授权启动 host。整树复制不得重试。凭据风险由用户接受，不写成已撤销。live 原件保持不动。未把副本放进三个 HOME 子目录。
3. 未满足：现场已保留。一次隔离 apply 恢复已发生。官方 verify 曾返回 `verified`，但该运行不是事前授权，不能据此 cleanup。cleanup、再次恢复和 P2-03 仍未授权。
4. 有证据才可演练对应阶段的逆向恢复；证据不足必须 blocked，不得宣称旧工具可用。
5. 独立 review 无剩余 P0/P1，且任务 PR 与状态 PR 都闭环后，才把本项标 done。该闭环前不启动 P2-03。同一作者在 `2026-09-24T18:05:21+0800` 纠正了过期台账，这不是独立 review。其后的独立 review 又发现本协议仍把当前状态写成未 apply、启动 Gate Plan 仍否认生产代码变更，且主 PRD 状态事件缺 apply／恢复／verify。这些公开事实已改正。再后的独立复审发现事件表仍从 12:21 的 blocked plan 跳到 16:05 的 apply，缺少解除阻断的用户授权和 planned manifest，也缺少其后「不要 deploy」、无 deploy 闭包和缺 Graft 的阻断。该链已按私有记录补入，不改既有回执行。补链改正者不能自证。`2026-09-24T20:47:18+0800` 的独立复审核对回执后仍发现 1 个 P1：16:55 的 block 之后，公开链从 `17:08:48` restored 直接到 `17:13:43` apply，没有记下私有记录 `17:11:22` 那次 status `planned`、且被再次 apply 消费的 deployment plan。当时不补那一行。用户随后要求评估 advisor 并在必要时对应。`2026-09-24T20:50:45+0800` 已把该 planned plan 按时间插入，并收窄本段同意边界。该会话是补链改正者，不能自证。`2026-09-24T21:43:58+0800` 的另一会话独立复审核对三件事通过：`17:11:22` 只补 planned plan，未改 `17:13` 回执；`verified` 仍不是 cleanup 或 done；README 两份入口只放开完整 private-only 跳过。无剩余 P0/P1。本复审后由本提交开任务 PR。不标 done，不 cleanup，不启动 P2-03。`2026-09-24T22:31:35+0800` 记录任务 PR #73 已合并，merge `2e22adc1a2644c99cbbe830c13ffe99881b1afaa`。本状态更新只改为 checking。§5.3 仍未满足，完成时间仍不预填。状态 PR #74 已合并，merge `d6d38907c9aa5aec8a73d1c0c5617a022f45469b`。`2026-09-24T22:46:30+0800` 用户原文「P2-02 演练到此结束。不授权 cleanup，不再次恢复，不启动 P2-03。现场继续保留。在此前提下把 P2-02 标 done。」两条 PR 都已闭环，本项标 done。该原文不授权 cleanup、再次恢复或 P2-03。现场继续保留。§5.3 的 cleanup 授权仍然未满足。不启动 P2-03。
