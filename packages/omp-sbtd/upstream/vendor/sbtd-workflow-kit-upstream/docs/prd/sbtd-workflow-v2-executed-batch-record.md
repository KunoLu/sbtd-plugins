# P2-06 密封批次已执行事实登记

本文件只登记已经发生的 live apply 事实。它不是 P2-03 的关闭合同，不修改 AC-18，也不把缺证据写成通过。

## 1. 与 P2-03 的边界

- P2-03 的当前完成依据独立见主 PRD §15.2／live 协议第9节；C1–C6 与 AC-17/18/29/30 的本阶段子项始终由 P2-03 拥有，不由本登记决定其状态。
- 本批仍没有原始 partial apply receipt，旧 Trellis 仍没有可写证据；历史事实不改为通过。按用户采纳的 D-IMP-15，partial retry 必须另有新隔离真实生产者证明，旧 Trellis 可写回退保证明确撤回，runtime_readiness 保持 not-verified；本登记不证明这些新检查通过。
- `2026-09-27T19:20:54+0800` 的旧 §15.2 已被独立审查判为非法 waiver，该历史判定保留。现行 §15.2 已与有效 AC-18 同步修订，其验证、独立审查及完成依据见 live 协议第9节；本项不复活旧关闭尝试，不替代 P2-03 验收。
- P2-04 的 P2-03 前置保持不变。本项完成、登记或审查都不授权 P2-04、cleanup、删备份、sync、改 hooks、host smoke、108 步 live 回滚，或调用已退役 Trellis。

## 2. 本项只登记的事实

这些事实已经发生。登记它们不等于 AC-18 通过。

1. live apply status `applied`。manifest `81a0c3d4bc63d906da67f6502b4f218d14a0d410376ad4ad9b354d93f5e280d2`。apply_id `9ad029161fe57421a682ed44adaddf8c54d73c45d84eea7ea3341d5fa4497c6f`。
2. 同一密封批次的完整回执重试 status `already-complete`。apply_id `3621a7fc6a1e3758338cb5e6114f20a5933bb2a830d0e6a0f13e5bfdebbc8ccc`。没有再写 live。
3. 恢复续作代码在提交 `bb8eb0b3fe68e151c1dea6aec285ff294f321116`。未执行 live recovery apply。

## 3. 本项验收

本项只验收：台账有独立行，三项已执行事实与保全证据一致，且登记没有把自己当作 AC-18 或 P2-03 通过的依据。P2-03 已通过任务 PR #80／状态 PR #81 独立收口；本项继续检查不改变或重新打开 P2-03 的 done，也不替代其 C1–C6。

本项按自己的任务分支、独立审查、任务 PR 和合并后状态 PR 收口。任务 PR 中最多 checking、完成时间留空；确认任务 PR 合并后，另在状态 PR 记录真实完成时间。本项不解除 P2-04 对 P2-03 的依赖，也不授权开始 P2-04。

## 4. 独立事实核对

观察时刻 `2026-09-28T10:46:26+08:00`，不是历史 apply／重试发生时钟。用户为 P2-06 单独选择 `default`；该次核对使用的任务分支为 `p2-06-executed-batch-closeout`。用户另行明确授权本项任务 PR 合并后，通过 TaskStore 从该任务分支重绑定到 `docs/p2-06-merged-status`；模式选择不代替这项独立授权。

| 登记项 | 实际核对 | 证明边界 |
|---|---|---|
| applied | manifest／原 apply ID 与已保全的最终只读审计记录一致，原始审计报告 hash 与索引一致 | 核对已保存记录，不是本轮重新 apply 或重新观察 live 状态 |
| already-complete | retry ID、原累计校验结果及历史原生 toolResult `b497ee08` 的 `live_changed 0` 一致；历史记录 hash 与索引一致 | 保持 historical-not-rerun；不能由“新保存一份回执”推断所有文件都零写入，此处仅指受管 live 目标未改 |
| 初次恢复续作提交 | `bb8eb0b3fe68e151c1dea6aec285ff294f321116` 为当前已合并历史的祖先提交 | 是初次修复事实，不把它冒称最终运行时版本；后续阶段血统修复和最终验证见 P2-03 live 协议第8/9节 |

私有核对报告及同 stem 中文汇总保留；共享文档不发布精确原件路径、私钥或原始内容。没有重新运行 live 命令，也不以本登记证明旧 Trellis 可写、live partial 重试或实际 live 恢复。

本轮是文档事实登记，不改变运行时、恢复契约、数据结构或安装行为；未完整调用 grill-with-docs，因为目标和三项事实已确定。只做文档结构／来源一致性检查和独立审查，不重复 P2-03 的运行时验收；本仓库不创建 `.feature`。

README.md、README.html、版本化 automation prompt 的能力／流程边界不变，无需重复修改；CHANGELOG 已记录实现变化，本登记不新增发布能力或验证契约，不追加过程日志。未读写 live automation，未执行 sync。

## 5. 任务合并与独立状态登记

[本项任务 PR #82](https://github.com/KunoLu/640-skills/pull/82) 已于 `2026-09-28T03:02:23Z` MERGED，merge `20b651ed13c007d997e5b41f65a77aeffbf05b6f`。精确任务 head `d9fded766773ac2a326f090a25afd394ca922110` 的登记文档 smoke、45项 workflow tests／1.328s／OK、两路独立文档审查以及 [CI run36371680249](https://github.com/KunoLu/640-skills/actions/runs/36371680249) 的 Linux／macOS／Windows 三个平台 job 均通过。实际合并树与该 head 一致。

用户单独选择的 default 模式和指定任务→状态分支重绑定授权已分别记录；任务合并之后才通过 TaskStore 执行该指定重绑定。本独立状态 PR 将 P2-06 记为 done，台账完成时间 `2026-09-28T11:04:03+08:00` 是任务验收与合并确认后的实际记录时刻，不是历史 apply 时钟，也不预报状态 PR 的合并时钟。

本项满足的只是三项事实登记及其独立交付流程。P2-03 已由 PR #80／#81 另行完成；P2-06 不作为 AC-18 或 P2-03 通过依据，不修改其完成时间，不新增后续任务依赖，不重新执行 live。P2-04／P2-05 保持 planned；部署、host smoke、回滚、cleanup、sync、hooks、旧 Trellis 调用和备份处置仍不在本次授权内。
