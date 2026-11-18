# Task state and recovery

Use this reference only when reading or changing persistent task state. Pure questions and explicit read-only work keep state in conversation and perform no task/pointer/handoff/identity/ignore writes.

## Runtime helper

Perform persistent operations with the Python task-state helper installed with `sbtd-workflow-onboard`: use `TaskStore` from `scripts/sbtd_task_state.py` in the installed Onboard Skill copy, with the interpreter dependencies declared in its `requirements.txt` (PyYAML, jsonschema, markdown-it-py>=4,<5). Markdown structure recognition uses markdown-it-py CommonMark tokens and table source ranges, parse-only, with no rendering and no network. It is a host-native library, not a new CLI, daemon, journal, or scheduler. If the installed helper copy or its declared dependencies are unavailable, say that persistence did not run; never claim a write that no helper performed, and do not fall back to hand-rolled scanning.

`TaskStore(root, read_only=False)` exposes `inspect`, `create`, `select`, `transition`, `set_mode`, `resume`, `reopen`, `protect_local_state`, `promote` and `archive` with the semantics in this reference. It also exposes the read-only `current_binding()` (actual branch, `detached:<full-sha>`, or None for a proven non-Git root), the read-only `recovery_candidates(task_id=None)` (the explicit task, the valid active bookmark, or all recorded candidates — never an mtime pick), and the confirmed `rebind(task_id, expected_branch=..., reason=..., evidence=..., confirmed=False)`. Only unconfirmed `promote` / `archive` return read-only transfer previews; ordinary writes and `rebind` raise `TaskStateError` without confirmation and perform no writes. `protect_local_state` returns a boolean indicating whether protection was added. `promote` / `archive` return a `TaskTransfer` describing status, source/target paths, files, the retained original location and the steps actually completed; failures carry the real `completed_steps` so a retry reconciles instead of duplicating events.

## 节点核对与及时记录

所有模式在开始任务、换会话、恢复、收到审查或决定、提交／push／开 PR 前以及退出前，先读 task.md 和实际进度。步骤成对追加「开始 X」／「完成 X＋验证结果」，带真实时间与写入者；决定到达就关闭相应等待项。每次写前重读，旧行不改写，事件与字段同次原子更新；进展、状态、事件与代码同 commit。多 PR 的中间轮只记进度。

使用 `scripts/sbtd_task_sync.py` 的 `TaskSync(TaskStore(root))`，不是 CLI／后台服务；不调用 gh 等平台工具，也不把节点核对放进 CI：

- `check(task_id=None, remote="origin", default_branch=None)` 返回 `ProgressCheck(task, method, differences, notes, discarded)`；省略 task_id 时读 active 引用。只检查，不写 task；A 按规则 fetch，显式只读工作不得更新引用，应报告不能执行 A，不把旧引用冒充新鲜核对。
- `record(task_id, step=..., writer=..., completed=False, validation="", files=(), evidence_files=(), scope=None, confirmed=False)` 记录开始或完成；完成必须有验证结果，`files` 是本步改动清单，删除路径可记录，`evidence_files` 必须存在。首次开始可把 planned 转为 in-progress；非 Git 新任务 create 后立即 record 开始，不把 planned 当成已开始。`scope` 是明确的项目相对目录列表，写入 frontmatter 扩展 `sync_scope`；不改 schema。
- 文件核对必须声明 scope；事件 evidence 内的 `sync_files` 保存范围内文件和额外改动／验收证据的 sha256、mtime_ns、size，包含 ignored 证据。task 本身不参与自引用哈希，Git 元数据与私有状态不得纳入范围。恢复读最近含文件证据的事件；清单／mtime 用于筛查，内容结论只看 sha256，也复核同尺寸同 mtime 文件。缺范围或快照记不可考，不宣称一致。
- `record_check(result, writer=..., confirmed=False)` 重读并比对核对时的 task 原文；有差异只追加「发现未记录的改动」，不改 status／completed_at，不自动 reopen。task 已变化则拒绝并重新核对；只读或缺授权不写。差异不是自动修复命令，不能用新的开始事件覆盖尚未处理的差异。

### A／B／C 判定

先用 `TaskStore.current_binding()` 判断 Git／非 Git 及真实 branch，再用 `git ls-files --error-unmatch` 判断 task 是否跟踪：

| 方法 | 条件 | 核对与边界 |
|---|---|---|
| A | lite／strict，ai/tasks 中 task 被跟踪，有远端 | fetch 后比较 `origin/<默认分支>:<task.md>` 与本地内容，不看祖先关系，squash 适用；默认分支从远端 HEAD 发现或明确传入，非 origin 远端须明确传入 |
| B | 同上但无远端 | 仅本地 HEAD、task 记录分支和工作区；HEAD 尚无 task 记不可考，不推断丢弃 |
| C | default、任何未跟踪 task、真正非 Git | 声明目录范围内文件清单与 sha256；额外验收证据也核对，不因 ignore 漏掉 |

始终按 task 的 branch 核对，detached 使用完整 SHA；checkout 不符仍须明确重绑定才能写。A 用 `git ls-remote --heads` 查记录分支，分支不存在且默认分支 task 非 done，按已丢弃记差异交人工判断，不自动 cancelled／reopen。远端不可达、默认分支／路径缺失是不可考，不等于分支已丢弃；从未推送与已删除仅凭当前远端不可区分，按 PRD 的缺分支规则提示并保留人工判断。

中途 git init 后，逐 task 明确 `rebind`，补真实 branch，旧 sha256 证据不动，不补造 commit。lite／strict 被跟踪后才切 A／B，default 继续 C。查合入用 `git log origin/<默认分支> -- <task.md>`，不把合并 SHA／时间回填 task；trailer 仅辅助。

### 旧格式事件与惰性基线

旧 task 原样保留，只读永不写入。不根据事件时间、Git 或合入边界猜新旧。无基线时，五列完整、`at` 为 `unknown` 或合法时间戳，但不符合当前事件 schema 的事件行算旧格式（例如状态名 `verifying`、`in_progress`），不设状态名枚举；空单元格、非法时间戳、非法行、frontmatter、重复事件节仍报普通解析错误。仅旧格式不兼容时 `TaskDocument.parse` 向 stderr 输出「旧格式事件，不追溯」，当前状态只取 frontmatter，不算未记录改动。

只有确需追加新事件，`updated` 才同次先追加 `旧事件基线：...`，evidence 为 `{"rows": <旧事件行数>, "sha256": "<旧事件行原文 UTF-8 sha256>"}`，不含 frontmatter／表头，不依赖 at 或 Git。基线内行保持原样且不再语义校验；`events` 是基线起的严格后缀，`event_lines` 保留所有原文行。后缀按当前 schema 校验，回填历史 done 也必须来自 checking（done 自事件不改变状态）。哈希／行数变化由 check 报差异，再经 record_check 追加事实，不覆盖或重建基线。

摘要包含落盘事件行的原始换行字节，CRLF 不归一化；若旧表恰好位于 EOF 且末行无换行，追加新行必需的分隔符同次纳入基线摘要，旧行内容字节不改。Git 内容比较同样保留原始换行，不能把换行归一化后的相等当成限定收尾 diff 的逐字保全。

`旧事件基线：` 是保留的 reason 前缀，仅由基线写入使用；普通事件不要以它开头。手工写入该前缀却没有合法基线 JSON 时按普通解析错误报告，不猜测或吞掉。

同目录原子替换前用 `<task.md>.sbtd-lock` 排他创建门及预期原文比较；竞争方报未持久化，重读后再执行。异常遗留标记必须先确认无写入者再人工处理，不自动抢锁。它只协调使用该库的写入者，不是锁服务；外部编辑器不遵守写入门时仍须单 writer。跨文件提升／归档不承诺事务。

### checking 与 B 方案收尾

新操作必须 in-progress → checking → done；历史直接 done 不追改、不补造 checking。审查期间保持 checking，退回则回 in-progress。文件核对无审查需求时，可同节点依次调用 checking、done 两次状态更新，真实 completed_at 与 done.at 一致。

CLEAN 后另作只改 task.md 的收尾 commit，仅允许 status／completed_at／updated_at 的值、一条追加 done 事件及证据。证据只记 CLEAN 对应的 SHA 和 CI run，不夹带其他内容。`check_finish_commit` 校验时要求证据为 JSON `{"clean_sha": "<收尾父提交完整 SHA>", "ci_run": "<CI run 标识>"}`，目前只在测试里调用；现行手写收尾提交用文字证据，内容同样只含这两项。`check_finish_commit(task_path, commit="HEAD")` 本地验证非 merge 提交、唯一文件、文件模式、正文／旧事件逐字保全及上述候选；额外行变化要整轮重审。此检查不查询平台、不证明 CLEAN／CI 真实性：宿主须已有相应证据，Reviewy 复核限定 diff，合入仍要求 CI 全绿。不自动提交、push 或发布。

## One effective record

The task's `task.md` owns mode, source, status, timestamps, body and events. Ordinary default tasks use `.sbtd/tasks/<logical-id>/task.md`; lite/strict use `ai/tasks/<logical-id>/task.md`. Explicit sharing can promote a default task without changing its mode. Switching down never deletes shared history.

`.sbtd/active-task.json` is only `{schema_version, task_id, task_path}`. A shared `ai/tasks/index.md` is navigation; handoff is a dated snapshot. Neither owns a second mode or status. Local files do not automatically move to another machine or worktree.

Within shared `ai/tasks/`, a directory named `reports` at any depth is reserved for local raw evidence and report summaries, including nested and archived tasks. The project template protects it with `/ai/tasks/**/reports` (also matching a same-name file or symlink); task documents, the index and `reports.md` remain trackable. Verify protection before writing reports. Keep existing test-runner report locations unchanged. Publishing evidence requires redaction and an explicitly approved destination outside the ignored report tree; do not force-add it or automatically untrack existing files. Ignore rules do not sanitize content or authorize deletion.

Before any local write, inspect actual ignore rules and tracked state. If `.sbtd` or `docs/handoffs` lacks protection, request narrow authorization for the required root-anchored rules; do not initialize an entire project or remove old protection. A reserved path that contains user content is a conflict, not permission to hide or replace it. No authorization means no local persistence; say so and continue only unrelated safe work where the mode permits.

## Read and validate

1. Resolve the explicit task or current valid bookmark inside the authorized project. Do not scan unrelated projects or choose the newest file. Multiple candidates require a task choice before asking about that task's missing mode.
2. Inspect the full task and relevant events before changing it. Use [task-data.schema.json](task-data.schema.json) for the normalized frontmatter, active pointer and event shapes. Core version is integer 1; unknown versions are not silently interpreted. Validate timestamps with actual calendar/timezone parsing: a format annotation without a registered assertion is not a check.
3. Safely parse UTF-8/JSON-compatible YAML without executing tags, objects or commands. Reject duplicate keys, cycles and nonfinite values. Preserve unrelated body and extension data; an unsupported extension or parser must not lead to silent data loss.
4. Check actual filesystem containment and types, including every relevant parent and symlink. Lexical schema checks do not prove containment. Active paths must resolve under this project's `.sbtd/tasks/` or `ai/tasks/`, end at task.md and match the record's full logical ID. Archive paths may differ from the ID; basename equality is not identity.
5. Require unique IDs, resolvable parents and an acyclic parent graph. A parent may summarize in-progress children, but multiple executable leaves do not share one writer. Preserve a logical ID through promotion and archive.
6. Compare the task's branch/root with the actual checkout. A different ordinary branch, detached binding or Git/non-Git mismatch requires correct-worktree, explicit rebinding or read-only choice. Normal new commits on the same ordinary branch do not alone constitute a branch conflict. Missing historical SHA stays unknown.
7. Effective mode comes from the current explicit user choice, otherwise the selected task. Use `mode_source=default` only for a new implicit default; an explicit user choice or accepted recommendation uses `user`, even when the chosen mode is default. Preserve choices and refusals in `mode_note` where writing is allowed. `migration-unknown` pairs with null mode until the user chooses; do not assume a legacy task was strict. Do not use an old handoff to overwrite a current choice.

`rebind` is the only write path that changes a task's branch binding. It requires the binding observed at decision time as `expected_branch`, a real reason and evidence, and confirmation; it records a same-phase event naming the old and new binding and never checks out, stashes, or resets blocked recovery history. If the recorded branch changed since the decision, the history is inconsistent, or the checkout moved while preparing, the rebinding fails instead of forcing a write.

A missing optional checker does not grant permission to claim it ran. Use available tools for the actual validation, or report exactly which writes/claims remain unsafe. Strict required verification cannot be marked passed by inspection alone when executable proof is required.

## Write one task

Before writing, confirm the operation, authorization, branch and expected old content. Use one writer. Produce a complete candidate, validate it, and replace the task through a same-directory temporary file/atomic replacement when supported. Where a tool cannot guarantee the required safe replacement, do not pretend it can; preserve the original and stop that write. Unexpected concurrent edits are a conflict, not permission to force overwrite.

Core fields and an event that belongs to this operation must change together in the same task.md. The schema permits some historical unknown values, but a new task or operation needs actual timestamps and evidence. Unknown historical completion time remains null with its source explained; do not use today's time as its old completion time. Preserve the original legacy evidence separately under its migration policy.

Bind `branch` to the actual named Git branch, or `detached:<full-commit-sha>` for a detached checkout; only non-Git projects use null. Do not abbreviate the SHA or use HEAD as the detached identity. If the binding cannot be observed safely, do not invent a value or claim that persistence/recovery is valid.

A status change uses the documented lifecycle: planned → in-progress → checking → done; checking may return to in-progress; unfinished work may block; planned/in-progress/checking/blocked may be cancelled; done and cancelled are terminal and reopen to planned. Cancellation is never completion: `cancelled` keeps `completed_at` null, is never a bootstrap success and never silently alters a done record. Do not infer completion from a directory name or a successful command unrelated to acceptance.

A completed task records a completion event whose `at` equals `completed_at`. Reopening first preserves the original completion/cancellation event/time/evidence, then appends done→planned or cancelled→planned and clears the current completed_at. Reopen terminal ancestors before the child; cross-file writes are not a transaction. On partial failure, report the actual completed steps and stop the remaining ones.

## Events and blocked recovery

Use the task body's single `## 状态事件` table, created when one of these meaningful events occurs:

| at | from | to | reason | evidence |
|---|---|---|---|---|

Reasons and evidence must be nonempty and safe for Markdown. Escape cell delimiters/newlines without losing meaning. Missing historical evidence is `not-recorded` with an explanation, not an invented path. 节点事件包含写入者；文件及验收证据按上述范围记录 sha256，凭据、账号和生产数据不得进入共享事件表。

- New block: validate `blockEntryEvent`, which requires an actual timestamp and from planned/in-progress/checking. Set status, blocked_reason and updated_at with that event.
- Continuing block: update the reason/time only. Do not append a new blocked→blocked ingress or replace the saved previous phase.
- Cancellation: planned/in-progress/checking/blocked → cancelled records the real decision with its reason and evidence; cancelling a blocked task clears blocked_reason in the same atomic update and completed_at stays null. Cancelled is terminal: only an explicit reopen (cancelled → planned) or a real archive/rebinding self-event follows; a done record never becomes cancelled. Unfinished descendants prevent every terminal parent transition; cancelled descendants count as finished.
  Cancellation also closes the old blocked recovery phase. After explicit reopen, a later block/resume cycle uses its own ingress; validate the resulting event chain before saving.
- Archive or explicitly authorized rebinding can record identical from/to states, including blocked→blocked. Validate `stateEvent`, but require a real corresponding operation; this is not an ingress and must not reset recovery history.
- Recovery pairs genuine ingress and release events and selects the latest unmatched ingress. Restore its real from value, only planned/in-progress/checking; clear blocked_reason and append the release event. A mode change or metadata self-transition does not change this match.
  Resume retry is idempotent only when the current planned/in-progress/checking state matches the last blocked→that-state recovery event. A blocked→cancelled event is cancellation, never recovery; resume refuses it without changing the original.
- If the historical chain is missing, contradictory or cannot prove the previous phase, ask the user to select planned/in-progress/checking and preserve existing records. Once the user answers and writes are authorized, append a `blocked` → selected-phase release event with the actual time and a reason explicitly recording unknown/conflicting history and the user's choice. Clear blocked_reason and update status/updated_at in the same atomic task update. Preserve the unresolved old history rather than inventing an ingress to make it appear consistent; if the update fails, report that recovery was not persisted. Read-only work records the choice only in conversation. Never guess from mode or return directly to done.
- `from=unknown,to=done` is only for substantiated old completion whose previous state is unavailable; `from=unknown,to=cancelled` and `from=unknown,to=blocked` are the same kind of historical fact for legacy cancellation/blocked records. `at=unknown` is only historical. A first historical unknown→blocked is a consistent snapshot whose recovery phase stays unknown — recovery still requires the explicit user phase choice above and never invents an ingress. None of these is a shortcut for a new completion.

On a retry, compare actual content and events: an already-completed identical operation is not appended again. Event history is not a separate journal service and does not supply concurrency isolation or authorization by itself.

## Promotion, archive and handoff

Promote with the same format and ID. The first confirmed call writes and validates the complete target candidate, then updates the effective active reference and the necessary shared index. Retiring the original is a separate confirmed step that requires an already prepared target: the original directory is atomically moved into `.sbtd/task-originals/<generated>/task` and retained, never recursively deleted. Candidate copies live only in the protected `.sbtd/task-transfer-candidates/` area owned by the current operation and are cleaned up afterwards; a candidate is never a second valid record. Other logical task records inside the directory must each be explicitly authorized with `include_tasks`; path nesting is not ownership. Preserve originals and recovery information until the handover is proven. Do not write both copies or select by mtime; reconcile explicit references and user modifications after interruption.

Archive only after confirmation, preserving the complete directory/events, with the same two-phase preparation, explicit `include_tasks` scope and original-retirement rules as promotion. Only terminal tasks (done or cancelled) archive. Shared terminal tasks use `ai/tasks/archive/YYYY-QN/` from a reliable completion date or the last proven cancellation event date; unknown dates use `undated`, never a directory or folder name date. Archiving local data does not authorize publishing it or deleting backups.
Logical descendants in separate directories are included in this guard: any unfinished descendant prevents archive preparation and source retirement. Physical directory scope does not replace the parent/child graph.

When a real continuation event occurs, use [handoff.md](handoff.md). After a successful status operation, update only the navigation the task needs and report what actually persisted. Damaged state does not justify creating a same-name replacement; default/lite can continue unrelated safe work, while strict required artifacts remain incomplete.
