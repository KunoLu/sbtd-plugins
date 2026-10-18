---
schema_version: 1
id: docs-retire-todo
workflow_mode: strict
mode_source: user
mode_note: 用户 2026-10-18 明确要求本任务用 strict workflow mode
status: "done"
branch: docs/retire-todo
created_at: '2026-10-18T09:41:01+08:00'
updated_at: '2026-10-18T10:05:52+08:00'
completed_at: '2026-10-18T10:05:52+08:00'
---
# 退役 docs/TODO.md

## 目标

按用户 2026-10-18 决定退役 `docs/TODO.md`：先回退 #93 加入的第 3 行指针（内容回到 c44c45a 版本），再 `git mv` 归档到 `docs/legacy-archive/dsh-sbtd-todo-through-2026-09-19.md`，更新活引用，不 commit、不 push，改动留在工作树。纯 docs 改动。

## 范围

- worktree `/workspace/sbtd-retire-todo`（branch `docs/retire-todo`，起点 origin/main `3fafd73`）；不触碰 `/workspace/sbtd-plugins`。
- 不改：PRD Appendix Q&A 原文、`ai/tasks/archive/**`、`docs/legacy-archive/tasks/**`、`ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md`、`packages/**` 证据文件。
- 例外（Lord/Reviewy/Researchy 2026-10-18 follow-up 明确授权，覆盖上一行限制各一处）：
  1. `docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md` 第 3 行仅替换尾部 `Live queue: \`docs/TODO.md\`.` 为退役说明（归档链接 + PRD 活进度链接），其余不动。
  2. PRD Appendix Q7 块保持 Q&A 原文逐字不变，仅在其后加一行作废注（「TODO 每个里程碑只加一行指针」部分被 2026-10-18 退役取代，见 §2.1 注）。

## 验收条件

1. 回退后 `git diff c44c45a -- docs/TODO.md` 为空（移动前验证）。
2. 归档文件顶部插入退役 blockquote 一行；其余内容逐字节同 c44c45a 版本，仅修因移动断裂的相对链接。
3. `docs/assets/dsh/README.md` 活队列指向 `../../prd/dsh-sbtd-0.2.0-rc.1.md` 并注明旧 TODO 归档路径。
4. PRD §2.1 Q7 B 锁定行后加作废注；任务表 D 行删「；TODO 指针」。
5. rg 扫描残留的每个命中都有保留理由。
6. （follow-up 1）archive 第 3 行 diff 仅含该一处替换；`../../legacy-archive/dsh-sbtd-todo-through-2026-09-19.md` 与 `../../prd/dsh-sbtd-0.2.0-rc.1.md` 两个链接目标都存在。
7. （follow-up 2）PRD Appendix Q7 块 Q&A 原文逐字不变，仅新增一行作废注；§2.1 注行（第 38 行）保留。

## Book Gate Plan

| Reviewer | 触发事实 | 阶段 | 状态 |
|---|---|---|---|
| book-ddd-distilled-modeling | 本任务未做完整 grill；需求由用户逐条明确指定，无领域歧义 | 需求确认前 | not-required |
| book-ddia-data-design | 无 schema / 迁移 / 持久数据设计 | 设计稳定前 | not-required |
| book-legacy-change-safety | 不改任何既有运行时行为（纯文档移动与指针更新） | 行为修改前 | not-required |
| book-refactoring-pass | 不改生产代码（仅 Markdown） | 实现前 | not-required |
| book-release-readiness | 无部署 / runtime / 集成行为变更，无发布 | 完成前 | not-required |

grill-with-docs 未完整调用：用户在任务消息中给出了全部操作步骤、确切文本与验证命令，无开放决策点，无需 grill。

TDD / BDD：纯文档归档，无可执行行为面，不适用。ponytail-review / 独立复核：diff 仅为文档移动与链接修正，不触及持久迁移、授权、全局配置或公共接口，不触发。project-validation：改动全部为 Markdown，无代码路径；项目命令（pnpm build/lint/typecheck/test）与文档改动无关，未运行。

## 证据

- 回退：`git diff c44c45a -- docs/TODO.md` → 空（exit 0，移动前执行，2026-10-18 09:2x Asia/Shanghai）。
- 归档内容核对：`diff <(git show c44c45a:docs/TODO.md) docs/legacy-archive/dsh-sbtd-todo-through-2026-09-19.md` → 仅 3 处差异：顶部新增 blockquote 两行；链接 `./assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md` → `../assets/archive/...`（1 处）；`./assets/dsh/ci-dsh-host-compat.md` → `../assets/dsh/...`（2 处）。其余逐字节一致。
- 残留扫描（2026-10-18 10:0x Asia/Shanghai 复跑，含 follow-up 改动后）：`rg -n "docs/TODO\.md|\(\.\./\.\./TODO\.md\)|\./TODO\.md" --glob '!ai/tasks/archive/**'` 残留命中及逐条理由见下表。
- follow-up 1：`git diff -- docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md` 仅第 3 行一处替换（尾部 `Live queue: \`docs/TODO.md\`.` → 退役说明）；两链接目标 `docs/legacy-archive/dsh-sbtd-todo-through-2026-09-19.md`、`docs/prd/dsh-sbtd-0.2.0-rc.1.md` 经 `ls` 确认存在。
- follow-up 2：PRD Appendix Q7 块（176–182 行 Q&A 原文未动），其后第 184 行新增作废注一行，指向 §2.1 注（第 38 行，上一轮已加）。
- 未执行：pnpm build/lint/typecheck/test（纯 Markdown 改动，无代码路径，不运行）。

### 残留命中表（rg 复跑 2026-10-18 10:0x）

| 命中 | 保留理由 |
|---|---|
| `ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md:122,124` | 计划任务内历史 Q7 Q&A 原文，用户指定不改 |
| `ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md:149` | 历史状态事件证据（记录当时 TODO 指针行），不改 |
| `ai/tasks/dsh-sbtd-0-2-0-rc-1-plan/task.md:171,428` | 历史 PRD 撰写要求记录，用户指定不改 |
| `ai/tasks/docs-retire-todo/task.md`（本文件多处） | 本任务自身目标/验收/证据记录 |
| `docs/assets/archive/dsh-sbtd-todo-archive-through-2026-09-13.md:3` | follow-up 1 授权的退役说明新文本 |
| `docs/assets/dsh/README.md:8` | 上一轮新增的活队列指针与退役说明 |
| `docs/legacy-archive/tasks/archive/2026-09/09-07-dsh-sbtd-fu2-legacy-before-refactor/implement.md:57` | 归档任务历史文档，用户指定不改 |
| `docs/prd/dsh-sbtd-0.2.0-rc.1.md:37` | §2.1 Q7 B 锁定行原文（第 38 行已有作废注） |
| `docs/prd/dsh-sbtd-0.2.0-rc.1.md:38` | §2.1 作废注本身 |
| `docs/prd/dsh-sbtd-0.2.0-rc.1.md:176,178` | Appendix Q7 Q&A 原文，follow-up 2 要求逐字保留 |
| `docs/prd/dsh-sbtd-0.2.0-rc.1.md:184` | follow-up 2 新增的作废注本身 |

## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-10-18T09:41:01+08:00 | planned | in-progress | 用户明确要求新建 strict 任务并立即执行退役 | 用户 2026-10-18 任务消息；分支 docs/retire-todo，起点 origin/main 3fafd73 |
| 2026-10-18T10:05:52+08:00 | in-progress | done | 退役及 Lord/Reviewy/Researchy 2026-10-18 两项 follow-up 全部落地，验收 1–7 满足 | `git diff` 仅授权改动；rg 残留复跑全部有保留理由（见证据表）；链接目标 `ls` 确认存在 |
