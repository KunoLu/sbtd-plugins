# P1-08 PowerShell installer migration／recovery 对等转发

## 范围与边界

- 交付 `install.ps1 -WorkflowMode <migration|recovery>`：剩余参数原样转发给 `scripts/onboard.py <mode>`，只剥离 installer 的 `--source-root`。
- PowerShell 不实现迁移/恢复判定、不重写 JSON、不改变退出码；直转路径跳过 banner、交互、全局工具/Skill/Agent CLI/MCP 和项目安装流程。
- 非直转调用仍按既有 named parameter 约定；未知剩余参数在进入安装流程前拒绝。
- 不修改迁移/恢复逻辑，不执行真实迁移/恢复、sync/live automation 或备份销毁。

## 门禁状态

- 未完整调用 `grill-with-docs`：P1-08 只按主 PRD §10.2、AC-13/29/35 与 P1-07 对等转发。
- Legacy Change Safety Review: characterized；installer suite 基线在本机原缺 pwsh，安装后真实参数绑定可执行。
- Refactoring Review: proceed；新增单一 `Invoke-WorkflowMode`，不改 init/reset 路径。
- DDD/DDIA: not-required。
- BDD: skipped（本配置源仓不新增 `.feature`）；PowerShell 行为由真实 pwsh smoke 固化。
- Release Readiness: planned。

## 验证计划与结果

- 用户确认后安装 Homebrew `powershell` 7.6.6；`pwsh --version` 通过。
- 红测/静态契约：`WorkflowMode` ValidateSet、`ValueFromRemainingArguments`、直转分支先于 Help、直转不调用 `Invoke-Onboard`。
- 真实 pwsh smoke：fake Onboard 收到 `migration --phase cleanup --confirm-cleanup abc123 --json`，stdout 为单 JSON，stderr 为空，`--source-root` 不透传。
- `tests.test_install_sh_agent_cli_flow` 36 tests / 18.695s / OK。
- 环境暴露 main 上既有夹具问题：真实 pwsh 下 project-only 会触发 Graft runtime 的只读 `npm root -g` 探测，旧 fake npm 将其误判为 forbidden。夹具已收窄为只拒绝非只读 npm 调用，`npm root -g` 返回隔离空全局根。
- 未执行 Windows 原生 ACL/路径测试；真实 Windows 仍需目标环境。

## 复审与最终结果

- 首轮独立 review 发现 PowerShell 吞掉 `--yes/--help` 的 P1；已改为直转回填并新增真实 pwsh 覆盖。`--` 分隔符不支持已写入 usage。
- 复审 NO P0/P1；`--yes:$true` 拼写和大小写宽容差异记录为 deferred P3：`P1-08-R1-PS-001/002`。
- 定点：`tests.test_install_sh_agent_cli_flow` 37 tests / 17.378s / OK（安装 pwsh 后无 PowerShell skip）。
- 原生 pwsh smoke：migration/recovery `--help` 均正确转发；`--yes`、等值 source-root、rc=7 与 MIGRATION 归一化经真实参数绑定验证。
- 最终全量：985 tests / 233.472s / OK（1 项 Windows ACL 既有 skip）。
- `rtk`: used；未生成 runner 原生报告，报告 gate not-needed。
