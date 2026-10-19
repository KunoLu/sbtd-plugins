# P1-15：Codex / OMP 三模式 smoke 与 token 计量

操作说明：[Codex / OMP 三模式 host smoke 验证手册](../assets/codex-omp-host-mode-smoke.md)。

## 收口

用户确认本项收口并走 PR #64 合并。接受 AC-20 measured-not-met、AC-14/23 仅为 Gate 分层 smoke、AC-24 live harness 已过。不启动 P1-16 / P2 / P3。



## 范围与边界

- 基线 `main` merge `bf996395d3fa034b64ce624417c352288ee4ba8f`（PR #63）。分支 `p1-15-codex-omp-mode-smoke`。
- 依据主 PRD P1-15 / AC-04、AC-14、AC-19、AC-20、AC-22、AC-23、AC-24。六个 host×mode 组合必须是真实 CLI 会话；mock、源码字符串匹配或 TaskRouter 返回值不能冒充 Agent 已按模式执行。
- 不写真实 HOME、不 sync live automation、不创建 rc tag、不跑 P2 迁移。CI 默认跳过 host 会话；本机用 `SBTD_P115_HOST=1` 才跑。
- **grill-with-docs：未完整调用。** 只读了 Skill 与既有 PRD/P0-10/P1-18 事实。P1-15 是已冻结 AC 的验收，不新增领域术语或边界；完整访谈不会改变六格 host×mode、token 分层或拒绝/恢复口径。不进入 grilling 轮次，也不触发后置 DDD 门禁。

## Book Gate Plan

| Skill | 触发 | Gate |
|---|---|---|
| grill-with-docs | 未完整访谈 | not-required（现有契约已消除歧义） |
| book-ddd-distilled-modeling | 无新领域选择 | not-required |
| book-ddia-data-design | 仅隔离临时项目写 task 记录 | not-required |
| book-legacy-change-safety | 不改既有生产执行路径 | not-required |
| book-refactoring-pass | 无生产重构 | not-required |
| book-release-readiness | 不改生产运行时 | not-required |
| ponytail | 编码前 | running |

## 分层证明

| 层 | 证明什么 | 不能证明什么 |
|---|---|---|
| TaskRouter / 既有 unittest | AC-22/24 机器可检查的选择来源、拒绝保存、只读零写入 | Agent 是否先暂停推荐 |
| 入口文件规模观察 | UTF-8 字节与空白分词，只作规模观察 | AC-20 token 目标 |
| 真实 `codex exec` / `omp -p` | AC-04 六个组合的可观察回复、隔离目录副作用 | CI 可复现模型成功、Windows host、P3 观察统计 |

## Host 会话约定

- 隔离 `HOME` / `USERPROFILE`；Graft 走 `HOME/.codex`，与 `CODEX_HOME` 同指临时目录。只复制 `auth.json`。
- OMP 的 `PI_CODING_AGENT_DIR` 也在该临时 HOME 下，不设持久 `--profile`。
- Codex：`exec --ephemeral --sandbox read-only --skip-git-repo-check --json`。保存失败格改 `workspace-write`。
- OMP：`--print --no-session --no-extensions --tools read`。`--no-extensions` 只关 extension 发现，**不**关 Skill（`--no-skills` 才关）。保存失败格改 `--tools read,write`。
- Mode JSON / refuse 提示不含 default/lite/strict。Gate / 跨会话提示同样不点名模式，也不点名 `book_gate_plan` / `loaded_strict_ref`。
- Gate 格用根目录 `MODE`，**不**写 `task.md`。跨会话 / 保存失败格**不**写 `MODE`：default → `.sbtd/tasks/<id>/task.md`，lite/strict → `ai/tasks/<id>/task.md`，外加 `.sbtd/active-task.json`；过期 handoff 单独放 `docs/handoffs/`。
- Gate：Codex 只解析 JSONL 读事件与 `agent_message`。无 tool-trace 记 `no-read-trace` blocked，**不算** default/lite AC-23。OMP **仅 Gate** 加 `--mode json`（restore/save 仍用文本回复抽 mode）。单对象 JSON 也当读事件。AC-14/23 要两个 host 共 6 格 passed。



- 只断言临时项目树；不 rglob 真实 `~/.codex`。缺登录或 CLI 记 `blocked`；两 host 未齐或跨会话未观察到 `lite` 则 skip，不当对应 AC 绿。




## Token 计量

- 公共核心目标约 2k、轻入口 ≤3k 是测量目标，不是保证。
- 优先使用 host JSON 中的实际 usage。没有 usage 时不得把字数换算成 token 并宣称达标。
- 可选 tokenizer 仅作并列观察，须写明编码名。

## 本轮实测

- 无 host：`python -B -m unittest tests.test_p1_15_host_mode_smoke` → 19 tests / 5 skip / OK。

- `SBTD_P115_HOST=1` 六格 mode JSON 全 passed（约 67s）。报告：`tests/api/reports/api-report-p1-15-host-mode-smoke-p1-15-codex-omp-mode-smoke-2026_09_21-07_49_31`（本机 exclude，不入库）。
- `SBTD_P115_HOST=1` refuse/pause：Codex+OMP passed（约 24s）。
- `SBTD_P115_HOST=1` Gate 约 200s：六格 smoke passed。报告 `…-2026_09_21-10_41_50`（exclude）。不是完整 Book/BDD，不是 AC-20。
- `SBTD_P115_HOST=1` AC-24 restore 约 172s：两 host passed（散文 lite）。不是单独的 AC-24。
- `SBTD_P115_HOST=1` save-failure 约 64s：两 host **passed**（Codex+OMP）。与 restore 合起来是 AC-24 live harness，不是 AC-20，也不是完整 Book/BDD。












- Codex JSON usage mode JSON 约 3.9 万、Gate 约 6–8.6 万 input tokens／格，含大量 cache；OMP 无 usage 字段。AC-20 仍为 measured-not-met。
- `evidenceSource=developer-local`，`publication=local-only`。



## AC 缺口与本轮口径

| AC | 口径 | 证据 |
|---|---|---|
| AC-04 | **partial**：六格隔离会话能读 MODE 并返回 JSON。不是完整澄清／实现验证／strict Gate | live matrix；`SBTD_P115_HOST=1` |
| AC-14 | **partial**：六格 Gate smoke 在 kind/name 读事件规则下 passed。不是完整 Book/BDD/Ponytail 执行 | live Gate 200s |
| AC-19 | **inherited**：仓库 CI 可复现归 P1-14。本项 opt-in host 不进 CI | 无 host unittest |
| AC-20 | **measured-not-met**：Gate Codex 约 6.5–8.7 万 input tokens／格；OMP 无 usage。不是 2k 达标 | 主机 JSON usage |
| AC-22 | **split**：TaskRouter 已覆盖推荐暂停与拒绝保存；host 增加 refuse/pause JSON | `test_sbtd_task_routing` + live refuse |
| AC-23 | **partial**：default/lite 有工具读且未开 `strict.md`；strict 有 `strict.md` 工具读。不是完整弱流程验收 | live Gate 200s |
| AC-24 | **passed**：restore 两 host lite；save 两 host 会话 strict 且 persist 失败信号。磁盘未改。不是 token/完整流程 | restore 172s；save 64s |










## 报告

- 正式 raw + 同 stem 中文 Markdown 写入 `tests/api/reports/`。
- `evidenceSource=developer-local`，dirty 只能 `local-only`。
- host 不可用、未登录或拒绝网络时标记 `blocked`，不伪造通过。
