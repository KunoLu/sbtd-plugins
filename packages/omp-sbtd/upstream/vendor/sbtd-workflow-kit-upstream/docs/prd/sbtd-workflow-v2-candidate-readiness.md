# P1-16：候选 release-readiness 审查

## 1. 审查对象与授权

- 任务：P1-16；唯一状态事实源为[主 PRD §14](sbtd-workflow-v2-trellis-removal-graft-migration-prd.md#14-优先级实施台账)。本报告不另建任务台账。
- 精确代码候选：`a50ade4586a780e2061f9eb20b0c0c58f9426e20`，PR #68 合并后的 clean main；审查分支 `p1-16-candidate-readiness` 仅维护任务文档，不改生产实现。
- 用户授权：开始候选就绪审查与隔离验证。没有 rc tag、正式发布、真实 HOME 接线、workflow sync、真实项目迁移／清理或备份销毁授权。
- 本次判断对象：候选实现及进入 P2 准备工作的技术前置，不是宣布完整 v2 已通过真实项目迁移和观察验收。P2/P3 的后置证明不能反过来成为 P1-16 的循环依赖，也不能被本报告提前判为完成。
- 审查结论：两路独立复核均为 `ready`，仅限本精确候选的 P1-16 门与进入 P2 准备工作；不是 rc、正式发布或真实迁移授权。任务仍须按既有 PR／合并后状态协议收口，不预填 `done`。
- `grill-with-docs`：未完整调用。沿用已批准领域、阶段与 AC 边界，没有新增产品术语；本次不以访谈代替代码和报告证据。

## 2. Book Gate Plan 与范围

| Gate | 判定／触发事实 | 状态 |
|---|---|---|
| Release readiness | required；本任务核心验收，必须区分候选、真实迁移和正式发布 | passed |
| DDIA | on-demand，已选用；审查迁移、恢复、批准与备份边界 | passed |
| Legacy safety | on-demand；没有修改既有运行行为 | not-required |
| Refactoring | on-demand；没有修改生产代码 | not-required |
| DDD | on-demand；未改变领域规则或上下文归属 | not-required |

本仓库是配置源，不创建 `.trellis/`、`ai/tasks/` 或 `.feature`。BDD 行为依据沿用主 PRD、既有行为说明及测试；没有新增用户可见产品行为。

## 3. 证据索引及版本边界

| 编号 | 证据 | 身份与实测范围 |
|---|---|---|
| E01 | [合并提交三平台 CI](https://github.com/KunoLu/640-skills/actions/runs/35610384575) | 精确 `a50ade4586a780e2061f9eb20b0c0c58f9426e20`；Linux 1126 tests / 8 skip / OK，macOS 与 Windows job 通过；Linux 大小写敏感路径、Windows junction／ACL 定点实际通过 |
| E02 | 本轮完整 Git 导出副本与 CLI smoke | 328 个 Skill 源文件；归档 SHA-256 `c9f567e3a52fd9bbc918fcbef30f57dae370e9e12657490bdf738d538ffa1e6c`；按副本 requirements 创建隔离 Python 环境，9 个原生 CLI 场景通过 |
| E03 | 本轮固定 Graft 原生安装 | darwin/arm64、Node 24.15.0；受管固定 `@nanonets/graft@0.18.0`，先计划、再明确确认安装、再重复 probe；native 启动及遥测关闭通过。独立 npm prefix／HOME／配置／缓存，不改真实全局安装 |
| E04 | 本轮 Codex／OMP 项目级图 smoke | 两个合成 Git 项目分别实际执行 `init-projects` 与受管 `analyze map`，4 项通过；使用真实 Graft，隔离 HOME 全树前后相同。不是 Codex／OMP 模型会话或全局 MCP 接线 |
| E05 | P1-15 五份历史 host 报告 | mode、refuse、Gate、restore、save-failure 的 raw／中文摘要／sidecar 都存在，raw SHA-256 匹配；sidecar 为 dirty/local-only，没有精确 source commit。保留历史实测，不重标为当前候选运行 |
| E06 | P1-15 merge 与候选的 Git blob 对比 | 两份 AGENTS、sbtd-task 入口、strict reference 字节相同；task routing/state、handoff、Graft entry/runtime、OMP wiring/sources 有后续变化。比较对象是两个已提交树，不证明历史 dirty 运行时所有字节 |
| E07 | [完整 findings 归档](../archive/sbtd-workflow-v2-findings.md) | 199 项：195 fixed、4 dismissed；无 deferred。归档中的历史裁决不覆盖后续 closure，PLAN-008 不再作为未修代码缺口 |
| E08 | 当前 CI 内的迁移／恢复集成测试 | `test_sbtd_migration_recovery_integration.py` 等组合真实 plan/apply/verify/cleanup/recovery 实现，但 deploy 环节由测试 fixture 生成合成报告，不调用真实部署生产者；不能说成已对真实 host／用户项目完成整链迁移 |
| E09 | 既有 P1 分项原生与运行说明 | P1-03/04/05/06 的安装、离线、接线、worktree 等历史证据保留其当时 SHA 与平台范围；未被本轮重新执行的内容不重新标记日期或版本 |

### 本轮命名报告

以下均在本机 exclude 的正式报告目录，不纳入版本库。raw、同 stem 中文 Markdown 和 `.evidence.json` 配对；本轮 3 份 sidecar 已通过现有 schema、raw checksum 及摘要存在性校验。

- E02：`tests/api/reports/api-report-p1-16-candidate-smoke-p1-16-candidate-readiness-2026_09_21-22_35_20.{json,md,evidence.json}`。
- E03：`tests/api/reports/api-report-p1-16-graft-install-p1-16-candidate-readiness-2026_09_21-22_40_17.{json,md,evidence.json}`。
- E04：`tests/api/reports/api-report-p1-16-project-graph-p1-16-candidate-readiness-2026_09_21-22_44_18.{json,md,evidence.json}`。
- 审计：`tests/unit/reports/unit-report-p1-16-evidence-map-p1-16-candidate-readiness-2026_09_21-22_49_32.{json,md}`，记录历史报告摘要及逐文件 blob 对比。
- E05 的完整 raw stem 分别为 `api-report-p1-15-host-mode-smoke-p1-15-codex-omp-mode-smoke-2026_09_21-07_49_31`、`08_15_53`、`10_41_50`、`10_57_30`、`11_26_51`（后四项沿用同一日期及前缀），均在 `tests/api/reports/`。

E02/E03/E04 为 developer-local / exact / local-only / smoke-only，精确身份来自 Git archive；不证明本审查文档未来提交的 PR head，也不冒充生产环境对齐。E01 为 ci / exact / published，不能替代模型行为证明。

## 4. 全部 AC 的阶段化核对

“机器通过”表示当前候选的实现／自动化证据，不表示未来真实环境验收已经完成。“历史部分”保持 P1-15 经用户接受的原范围，不静默提升为完整 AC 达标。

| AC | 主题 | 当前证据与结论 | 尚属后续的证明／约束 |
|---|---|---|---|
| AC-01 | 固定 Graft 安装与能力 | E03 当前 darwin/arm64 原生安装和重复执行通过；E09 历史能力说明 | 不宣称原生 Graft 全平台兼容；P2 所选目标环境先核对 native 可用性 |
| AC-02 | 三模式方法与 Gate | E01 规则／路由回归；E05 分层 smoke | 完整方法执行仍有 AC-14/23 的历史部分限制 |
| AC-03 | 任务状态与恢复 | E01 task schema/document/state/recovery 回归；E02 当前 handoff 可读 | 真实项目状态归 P2 验收 |
| AC-04 | 两 host 三模式可用 | E05 六格真实会话历史 partial/smoke | 不是完整澄清、实施验证和 strict Gate；未作当前 SHA 全流程模型复验 |
| AC-05 | 事件交接与恢复 | E01 handoff/routing 回归、E02 迁移摘要读取；E05 历史恢复 | 模型自动触发不由 CI 硬保证；P3 观察真实使用 |
| AC-06 | lessons 身份与历史 | E01 identity、workflow contracts；E07 历史无损归档 | 真实身份／旧资料只在明确授权范围迁移 |
| AC-07 | freshness 与 diff 边界 | E01 entry/isolation 回归；E04 当前受管 map；E09 历史负面场景 | 不宣称所有查询始终 fresh；失败／不支持语言用源码补证 |
| AC-08 | 接线、幂等与隔离 | E04 当前 project-only 两平台、HOME 零改动；E01 接线回归；E09 历史全局／hooks | 当前全局 host 信任和模型事件不由 project-only 证明；P2-04 执行所选接线与 smoke |
| AC-09 | 多仓／worktree 隔离 | E01 graft isolation 回归；E09 历史真实 linked worktree | 当前真实目标根、shared HOME 与未选项目范围由 P2-01/02 核验 |
| AC-10 | 网络、遥测与离线 | E03 受管固定安装、关闭遥测；E01 环境／失败分支；E09 历史断网实验 | 本轮允许 npm 安装下载，未重做完整断网／网络流量实验；不声称绝对零联网 |
| AC-11 | Skill cutover 与安装 | E01 catalog/external/installer 回归；E02 完整328文件副本与声明依赖可执行 | 完整用户环境安装不是目录复制；真实部署另行授权 |
| AC-12 | ignore 正反与幂等 | E01 ignore/path 回归；E02 handoff 保护；Linux/Windows 补证 | 实际项目自定义规则冲突在 P2 拒绝或人工处理 |
| AC-13 | CLI／JSON／两安装器 | E01 三平台安装器；E02 原生9场景，含确认拒绝／漂移拒绝 | 平台机器通过不等于模型行为通过 |
| AC-14 | Book/BDD/Ponytail 分层 | E01 契约回归；E05 Gate 历史 partial/smoke | 没有完整真实方法序列证明；不改写为全通过 |
| AC-15 | 文档／sync／发布边界 | E01 workflow contracts；本报告明确授权与证据边界 | 本轮不写 live automation，不 sync，不创建 tag |
| AC-16 | 旧运行依赖退役 | E01 退役路由／catalog 回归；E07 历史保留 | 已有真实旧包、配置和数据不因源仓切换自动删除 |
| AC-17 | 数据完整与无越权 | E01 migration/files/legacy 回归；E02 私有原件与恢复 | P2-01 完整盘点真实 tracked/ignored/untracked，再做 P2-02 演练 |
| AC-18 | 幂等、失败与恢复 | E02 applied→already-complete、漂移拒绝、恢复；E08 partial/整链机器回归 | 真实旧运行时可用性与实际恢复演练由 P2-02 证明 |
| AC-19 | 可复现验证与 CI | E01 精确三平台CI；E02/E03/E04 精确导出副本 | 历史 dirty host 报告不能变成当前 clean-SHA 证明 |
| AC-20 | token 收益可复算 | E05 保持 measured-not-met；Codex usage 有记录，OMP 无 usage | 主机总输入含固定prompt／cache／上下文，不等于SBTD可控核心；不得造2k达标或缩减安全以达标；P3再评估实际任务收益 |
| AC-21 | 授权项目真正迁移 | 尚未执行，不属于 P1-16 实现前置 | P2-04/05 的逐项目真实证据与用户验收 |
| AC-22 | 初始路由与用户选择 | E01 routing 回归＋E05 历史 refuse/pause split | 不以 TaskRouter 返回值冒充当前模型必然先暂停 |
| AC-23 | default/lite 非强流程 | E01 分层规则；E05 partial/smoke | 完整弱流程和所有场景保留交付不由六格读取事件证明 |
| AC-24 | 持久化、恢复、提升 | E01 机器回归；E02 当前摘要读取／不自动选 active；E05 历史 restore+save-failure passed | 历史 passed 仅 live harness 范围；当前运行模块已有后续修复 |
| AC-25 | 身份条件与授权 | E01 identity/迁移回归；E02 合成旧身份流程 | 真实 custodian／developer 不从 Git、OS 或旧报告猜测 |
| AC-26 | ignore迁移与二次确认 | E01 negative/confirmation 回归；E02 未批准 apply 拒绝 | P2-03 先保护，P2-05 验证后再确认清理；不自动 untrack |
| AC-27 | 只读优先 | E01 routing/task/handoff/developer 回归；E02 未确认零执行 | 真实只读会话不因阶段要求落盘；本轮任务文档写入有用户授权 |
| AC-28 | 跨分支恢复裁决 | E01 task recovery/routing 回归 | 真实分支冲突仍需正确 worktree／明确 rebind／只读选择 |
| AC-29 | 四阶段与独立部署 I/O | E01/E08 contract链；E02 当前 plan/apply/recovery CLI | P2-04 才执行所选真实独立部署；apply 不递归部署／sync |
| AC-30 | 旧元数据与私有原件 | E01 legacy/projection/privacy 回归；E02 原件与备份保留 | 真实候选的完整脱敏批准不能由 hash 或测试代替 |
| AC-31 | 状态事件完整 | E01 task document/state 回归 | 真实历史未知时不补造时间或完成事实 |
| AC-32 | blocked前态恢复 | E01 task state/recovery 回归 | 缺失／冲突旧事件仍须用户指定，不直接 done |
| AC-33 | 共享HOME批次唯一性 | E01/E08 共享闭包、报告共享身份及累计回执回归 | P2-01/02 盘点实际共享消费者，不能假定只影响已选项目 |
| AC-34 | 私有摘要不外泄 | E01 redaction/null-hash 回归 | 真实低熵资料与公开产物在 P2 审核；不新增密钥系统 |
| AC-35 | 恢复入口与回执 | E02 当前原生恢复；E01/E08 逆序／partial／缺证据拒绝 | P2-02 真实副本演练与旧运行时恢复；不把备份存在等同恢复可用 |
| AC-36 | 全共享产物隐私门 | E01 全闭包／候选绑定；E02 未批handoff阻断 | P2 审查实际正文、附件、文件名、二进制；必要未知项继续 blocked |
| AC-37 | 备份保留与人工处置 | E01/E08 保留／授权拒绝；Windows ACL 原生补证；E02 恢复后备份仍在 | P2 确认责任与保留安排，P3观察；备份销毁单独授权，不由cleanup/recovery代替 |

## 5. DDIA Data Design Review

- Status：confirmed（既有设计与本轮证据边界审查，不是授权真实迁移）。
- Data owner and source of truth：task.md 拥有状态／模式；active 仅引用；handoff 是批准快照；manifest、不可变阶段收据及私有原件拥有迁移来源与恢复证明；用户拥有真实项目和 HOME。
- Write / read / failure paths：plan/verify只读；apply备份、保护并应用批准候选；部署独立；cleanup消费完整验证和再次确认；recovery按有证据的逆序范围恢复。
- Consistency：精确内容／来源与当前状态核验、单写入者；不宣称跨资源事务或对任意外部 writer 的 CAS。遥测已有可变文件安全拒绝，新文件采用 no-clobber 创建。
- Idempotency / retry：显式前次回执，已成功且后态未变的资源不重复执行；漂移和未知部分写入停止，不扫描最近文件猜恢复。
- Schema / rollback：版本、资源ID、source/candidate/checksum、报告边界同时绑定；改变实现后不复用旧 manifest。恢复不删除原件备份，不自动处置用户后来写入。
- Observability / repair：单JSON、明确状态／退出码、累计结果、私有保存失败可见；P2运行手册必须保留完整证据链及恢复命令。
- Required tests：E01、E02及E08覆盖当前实现和失败边界；P2-02才负责实际选中环境的迁移／恢复与旧运行时可用性演练。

## 6. Release Readiness Review

- Status：ready，限定候选 `a50ade4586a780e2061f9eb20b0c0c58f9426e20` 的实现与 P2 准备前置；不扩展成完整 v2 正式发布结论。
- Production path and affected systems：源仓安装器、任务库、Graft受管入口及迁移／恢复实现；本轮只操作私有测试环境，未部署用户环境。
- Failure modes and safeguards：版本／路径／权限／批准／来源不确定时拒绝；既有可变遥测不覆盖；无完整回执不恢复／清理；用户后续改动不被吞掉；备份保留。
- Capacity / backpressure / limits：本地CLI、单写入者，外部进程有超时与退出码；不新增服务、队列或无限重试，不承诺任意并发隔离。
- Observability / runbook：单JSON、明确阶段状态和保存失败；原生raw／中文摘要／sidecar保留，P2使用既有manifest／收据／命令，不凭文件名猜前次状态。
- Rollout / rollback / cleanup：先完成任务PR与状态PR；真实部署／迁移／cleanup及备份处置仍按P2/P3独立确认；rc可选且无本轮授权。源码回退不等于用户数据恢复，也不删除备份。
- Required validation and result：精确三平台CI1126tests/8skip；完整328文件副本的9个CLI、3个固定Graft安装、4个project-only原生图场景通过；文档契约45项通过；3份本轮证据schema/hash/摘要配对通过。
- Optional checks, owner acceptance and residual risk：P1-15的用户接受仅保留其历史partial/smoke和measured-not-met范围，不新增全局豁免。本候选不声称当前SHA完整模型方法运行、所有平台native Graft或真实迁移；所选目标环境及真实任务观察继续由P2/P3持有。

| 独立 reviewer | 复核范围 | 结论 |
|---|---|---|
| P116ReadinessReview | 阶段边界、风险、P1-15限制及P2前置，避免循环依赖或把partial变为完整通过 | ready（候选范围）；无发现 |
| P116EvidenceReview | 精确身份、raw/sidecar校验和、9/3/4数量、历史dirty边界及E08合成deploy定界 | ready（候选范围）；无发现 |

Code Readability／Ponytail：本轮仅任务文档，没有新增生产抽象或重复运行机制；审查未发现需要扩大改动的可读性或过度设计问题。

## 7. 候选风险与后续门

| 风险／限制 | 本次处理 | 后续责任与停止条件 |
|---|---|---|
| 将P1-15部分证据当完整方法／成本达标 | 保留 partial/smoke、split、measured-not-met；不改历史报告 | rc／发布说明必须披露；P3真实任务观察和最终readiness不能宣称已达标 |
| 历史host报告缺精确revision | 校验原文件和hash，比较已提交入口；不重标旧运行 | 若需要当前候选的完整host证明，另做受控实测；不得复制或公开凭据 |
| 已有 enabled telemetry 无共同写协议 | 用户已明确接受安全拒绝；E03证明全新安装与幂等路径 | 实际环境遇到此状态先独占处理，不放宽数据保全门 |
| OMP plugin来源未完整建模 | 当前preflight保守拒绝发现的registry，CLI/CI回归保持 | 目标项目若依赖plugin MCP，P2准备阶段先解决兼容性；不静默并存冲突 |
| Graft原生依赖具有平台限制 | 当前Darwin原生证明＋三平台机器CI分层 | 不把Windows ACL通过扩大成Graft全平台native通过；P2选定平台先做相应预检 |
| 全链集成夹具被当作真实迁移 | E08明确synthetic deployment evidence | P2-02/04/05采集真正的部署／host／恢复证据，不使用fixture生成正式验收 |
| 备份被过早删除 | cleanup/recovery不删备份；保留与销毁分离 | P2-01确定custodian与保留安排；P3-04再独立授权，不是P1-16前置 |

## 8. RC、P2 与状态推进

- 当前仓库没有 `v2.0.0*` tag；本轮没有创建任何 tag。
- 若选择 rc，建议名称仍为主 PRD 的 `v2.0.0-rc.1`；创建前必须明确不可变 SHA、适用范围、已知限制及用户批准，不跟随浮动 main 自动重打。
- P2-01需确定真实项目根、host/HOME范围、custodian、私有vault、完整备份清单与保留安排；P2-02完成隔离副本演练后才允许真实apply。
- P2-03只apply并停旧路由；P2-04独立部署／逐项目smoke；P2-05verify、再次确认后cleanup。任何阶段失败都不借下一阶段补造通过。
- P3的两周观察、3–5个真实任务及最终v2.0.0发布保持独立；不因本候选审查完成提前标done。
- P1-16只有独立review达到其候选范围内的ready并完成规定PR／状态闭环才可done；rc是可选项且需独立批准。当前不预填未来merge SHA、完成时间或用户选择。

## 9. 验证与文档维护说明

- 本轮未修改生产代码；当前精确候选三平台全量CI仍有效，不为了文档审查机械重复同一全量。当前新原生smoke补的是安装／project-only入口与完整副本证据。
- E02首轮临时驱动因macOS `/var`别名被真实路径守卫拒绝；规范化临时根并换全新夹具后通过。保留失败报告，不将错误驱动的失败当作产品缺陷。
- 所有导出源文件在原生验证后逐字不变；没有新增未声明文件。临时运行数据仅用于本次测试，报告保存后清理本任务拥有的目录。
- Web/Mobile、Knowledge Ingest、HTTP API契约、SEO：not-needed。CLI集成报告的URI明确not-needed，没有虚构HTTP接口；不安装浏览器／移动测试工具。
- README.md、README.html、版本化automation prompt、CHANGELOG：本轮是任务级readiness证据，不改变产品行为、安装路径或版本监控范围，暂不改写；若后续实际rc／发布另行发生，再维护对应入口。
- rtk：Git使用；报告型验证原生命令执行，skipped-for-report。未同步live automation、真实HOME或用户项目。
