# P1-11 README／Onboard docs／prompt／CHANGELOG 同步

## 范围与边界

- `README.md` 当前工具主线、工作流主线、关键边界、SBTD 表、工具职责边界与安装说明切到 `Codex / OMP + sbtd-task + Graft`；旧 Trellis/GitNexus 只保留迁移和历史边界。
- `README.html`、`sbtd-workflow-onboard/SKILL.md`、`sbtd-workflow-onboard/REFERENCE.md` 同步 P1-07/P1-08 已完成的根安装器转发边界，不再写成待办。
- `prompts/automations/sbtd-workflow-tools-version-check.md` 的专用版本检查规则从 Trellis/GitNexus 现行监控改为 Graft 固定 pin/source、native lifecycle、telemetry、MCP/hooks 和平台接线核验。
- `sbtd-workflow-onboard/REFERENCE.md` 另补充 AC-37 规程文档：cleanup、Graft uninstall、任务完成和恢复成功均不删除备份；恢复可用仅限 manifest、阶段/恢复收据、实际备份和登记副本仍证明归属、精确范围与当前状态，缺证据为 evidence-insufficient 并 blocked/零删除/不得 done。人工销毁须先保存并回读 custodian、候选归属、精确范围、本次独立授权和实际确认时间；载体为删除范围外的既有私有准备记录或迁移报告，不新增处置 CLI。
- `CHANGELOG.md` 增加 P1-07～P1-11 用户可见变更，并在 P1-11 行记录上述 AC-37 文档边界。
- 未改 `UPDATE.md`、`archive/`、live automation、真实 HOME、版本写回或本机实际生效路径。

## 验证

- `tests.test_workflow_contracts`：44 tests / 1.118s / OK。
- 最终全量：989 tests / 220.331s / OK(1 项 Windows ACL 既有 skip)。
- `rtk`: used；未生成 runner 原生报告，报告 gate `not-needed`。
