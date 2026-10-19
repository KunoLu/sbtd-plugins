# P1-07 Bash installer migration／recovery 转发

## 范围与边界

- 交付 `./install.sh migration ...` 与 `./install.sh recovery ...` 直转：剥离 installer 的 `--source-root` 后，直接执行 `scripts/onboard.py <mode>`，不进入 banner、交互、全局工具/Skill/Agent CLI/MCP 检查或项目安装流程。
- Bash 不解析、不重写、不补默认值或授权；migration/recovery 参数、JSON、退出码由 Python 唯一拥有。
- 不支持 `--dry-run` 包裹 migration/recovery；`--source-root` 仅用于定位 Onboard。
- 不实现 PowerShell（P1-08）、不执行真实迁移/恢复、不修改项目/HOME。

## 门禁状态

- 未完整调用 `grill-with-docs`：P1-07 只按主 PRD §10.2、AC-13/29/35 要求转发统一接口。
- Legacy Change Safety Review: characterized；Bash installer 33 项基线通过，直转前 migration/recovery 被 argparse 拒绝。
- Refactoring Review: proceed；新增单一 `forward_workflow_mode`，不改既有 init/reset 路径。
- DDD/DDIA: not-required；无新领域或持久数据。
- BDD: skipped（本配置源仓不新增 `.feature`）；CLI 行为由 Bash 3.2 unittest 与原生 smoke 固化。
- Release Readiness: planned。

## 验证计划与结果

- 红测先行：`migration/recovery` 原先进 installer 被 `Unknown option` 拒绝；新增直转后 fake Onboard 只收到目标 mode 和原始参数，stdout 为单个 JSON，stderr 为空，未触发 check-agent-cli。
- 定点：`tests.test_install_sh_agent_cli_flow` 33 tests / 10.767s / OK（5 项既有 skip）；`/bin/bash -n install.sh` 通过。
- 原生 smoke：`./install.sh migration --source-root sbtd-workflow-onboard --help` 展示 `migration {plan,apply,verify,cleanup}`；`recovery --help` 展示 `{plan,apply}`。
- 未执行真实迁移/恢复、PowerShell、sync/live automation、Windows 原生操作或备份销毁。

## 复审与最终结果

- 独立 review：无 P0/P1；4 条 P2 测试缺口（source-root 剥离、退出码透传、等值 source-root、副作用精确断言）与 2 条 P3（Usage、空行）均已修复并复核。
- 最终定点：`tests.test_install_sh_agent_cli_flow` 34 tests / 9.936s / OK（5 项既有 skip）；`/bin/bash -n install.sh` 通过。
- 最终全量：982 tests / 225.052s / OK（6 项既有 skip）。
- `rtk`: used；未生成 runner 原生报告，报告 gate not-needed。
