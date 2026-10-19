# P1-14 模式／安装／迁移／恢复回归与 CI

## 范围与边界

- 新增 `tests/test_sbtd_migration_recovery_integration.py`：真实 producer(plan/apply)→verify→cleanup→recovery 集成链；证明 cleanup/recovery 不删除原始备份，部分 cleanup 可累计续作，缺 cleanup 证据的 recovery plan 为 blocked、零删除且不生成收据。
- 新增 `sbtd-workflow-onboard/scripts/sbtd_backup_retention.py` 与 `tests/test_sbtd_backup_retention.py`：仅对删除范围外的既有私有准备记录或迁移报告做读-改-写-回读，写入 custodian、候选归属、精确范围、本次独立授权和实际确认时间；五项逐项缺失、确认时间非法、目标不存在、封闭 publication-decisions 任意加字段、写入失败或回读不一致均 blocked、零删除、不得 done。禁止用 `save_document` 新建处置文件，不注册处置 CLI、不创建 lifecycle/journal/lock，也不替代 P3-04 人工规程。
- 新增 `.github/workflows/validation.yml`：`actions/checkout` / `actions/setup-python` 按 commit SHA 固定并指定 Python `3.12.10`，PR 事件显式 checkout PR head SHA；Linux 全量、macOS Bash installer／多项目／contracts、Windows PowerShell installer／contracts 分工，Windows 另在 pwsh 可用时运行 `-k powershell` 真实安装器子集，三 job 均断言 checkout 干净；CI 不证明真实 host、完整 Windows 原生或发布完成。
- `tests.test_workflow_contracts` 新增 CI 工作流契约测试，固定 pin、平台分工和 clean SHA 验证命令。
- `README.md`、`README.html` 与 `CHANGELOG.md` 记录 CI gate、集成回归和 AC-37 实现期门禁边界。
- 残余风险：`sbtd-workflow-onboard/requirements.txt` 保持既有声明范围（jsonschema/PyYAML/markdown-it-py/tomlkit），P1-14 不新增 pip lock；CI 已固定 actions commit SHA、Python `3.12.10` 和 PR head SHA checkout，但 pip 解析仍随上游 minor 漂移。Windows `test_workflow_contracts` 使用仓库外空 `core.excludesFile` 与 LICENSE SHA-256 的 CRLF→LF 规范化，避免 `nul` exclude 与 checkout 换行；不把该规范化当成许可证内容变更。该风险由本任务 accountable owner 接受为 clean-SHA gate 的残余风险，不改变 Onboard 运行时依赖声明。

## 验证

- 定点：54 tests / 6.219s / OK（workflow contracts、backup retention、migration/recovery integration）。
- `tests.test_workflow_contracts`：纳入上述定点套件。
- CI YAML 静态解析：workflow-ok。
- 当前工作树最终全量：999 tests / 658.267s / OK（1 项 Windows ACL 既有 skip）。
- fresh clone `7ac428d` 目录内全量：999 tests / 608.123s / OK（1 项 Windows ACL 既有 skip）；compileall 通过。
- GitHub Actions 三平台：run `35519194036` 全绿（linux-full 3m4s、macos-bash-installer 59s、windows-powershell-installer 39s，含 Windows `test_workflow_contracts` 与 `-k powershell` 真实安装器子集）。CI 通过不代表真实 host 或发布完成。
