# P1 十项门后证据边界修复

## 授权、基线与范围

- 触发：P1-06 闭环后按 D-IMP-14 暂停后续 P1；用户确认“修复证据边界后继续”。
- 基线 main `b96392be6dda4d4cacaeeca6715b07cf9db5f38a`；分支 `p1-evidence-boundary-remediation`。
- 只修复用户确认的 7 项 deferred P2：`P1-12-R1-VERIFY-005/006/007/008`、`P1-01-R11-P2-001`、`P1-01-R12-P2-002`、`P1-01-R12-P2-003`。
- 不处理 RUN、Windows junction、planner/legacy、TaskStore/handoff、Graft runtime、installer 或文档 UX 延期项；不恢复 P1-13 直至本批 review/合并/状态闭环。

## 门禁状态

- 未完整调用 `grill-with-docs`：本批不改变产品边界，只执行已确认的修复清单。
- Legacy characterized：当前相关 `test_sbtd_migration_verify` 与 `test_onboard_contracts` 共 263 项通过；先为每个缺陷补红测。
- Refactoring proceed/normal：不先重构；只修改现有证据 validator seam。
- DDD not-required：无新领域术语。
- DDIA confirmed：部署报告、同 stem 中文摘要、raw run、envelope、deployment evidence 输出与 manifest 输入/目标必须保持明确所有权；路径父子或内容冲突 fail-closed；不做迁移/重写历史证据。
- Release planned：最终全量、独立 review 与合并后才 ready。

## 修复契约

1. `verify` 的 genuine-mode gate 只对实际满足 API smoke 的 entry 生效；辅助报告仍须通过 checksum/status 等通用检查。
2. `summaryMd` 必须是已绑定且 checksum 匹配的正式报告对，不得只按路径打开。
3. 报告/尝试时间必须带显式 timezone/UTC offset；naive timestamp 不进入比较。
4. raw API run 的 repository/evidence/trigger/revision/worktree 等来源字段必须与 enclosing envelope 一致，禁止 dirty/local 冒充 clean/CI/knowledge。
5. deployment `report_refs` 中任意两个路径不得互为严格祖先/后代；同一路径同状态仍允许共享。
6. stage `report_refs` 不得与 manifest 的受管 operation targets 或 input references 等同/互为父子。
7. `deployment_result.path` 不得与内嵌 evidence 引用的报告/backup 路径等同/互为父子。

## 验证计划

- 每项先写公开 validator 行为红测，再实现；保留既有有效 fixture。
- 定点运行 `test_sbtd_migration_verify`、`test_onboard_contracts` 及相关 migration/deployment 套件。
- 最终运行完整 unittest、Ruff 聚焦检查、git diff check、独立 review；报告型验证保留正式 raw/中文 summary/evidence。
- 不执行真实迁移、cleanup、recovery、live automation、sync/update、真实 HOME 或 Windows 原生操作。

## 验证与审查结果

- 红测先行：8 项授权缺陷和 1 项同类 epoch timestamp 残留均先复现；`VERIFY-005` 的辅助报告场景、summary 绑定、naive timestamp、raw provenance、跨项目/同项目 report_refs 父子、manifest 输入/目标重叠、deployment output 覆盖 report/backup 均覆盖。
- 定点：`tests.test_sbtd_migration_verify` + `tests.test_onboard_contracts`，274 tests / 7.098s / OK。
- 最终全量：`python -B -m unittest discover -s tests -p 'test_*.py'`，952 tests / 223.692s / OK（6 项既有 skip）。
- 静态检查：`ruff check` 对 `sbtd_migration_verify.py` 与两份测试无诊断；`onboard_contracts.py` 仍有 main 基线相同的 3 项既有诊断（I001/UP012/SIM102），本分支未扩大。`ruff format --check` 对 `sbtd_migration_verify.py` 与 `test_sbtd_migration_verify.py` 通过；`onboard_contracts.py`、`test_onboard_contracts.py` 保留既有格式债。
- 独立 review：`AdorableKangaroo` 只读复审结论 `NO P0/P1 REMAINING`，确认 7 项授权修复完整且未越权；`epoch_started` naive 残留已同批补红测并修复。剩余 P2 风险作为 deferred findings 保留。
- 不执行真实迁移、cleanup、recovery、live automation、sync/update、真实 HOME 或 Windows 原生操作。
