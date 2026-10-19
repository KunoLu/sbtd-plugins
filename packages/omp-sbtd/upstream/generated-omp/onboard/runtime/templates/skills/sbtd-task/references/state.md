# Task state and recovery

Use this reference only when reading or changing persistent task state. Pure questions and explicit read-only work keep state in conversation and perform no task/pointer/handoff/identity/ignore writes.

## Runtime helper

Perform persistent operations with the Python task-state helper installed with `sbtd-workflow-onboard`: use `TaskStore` from `scripts/sbtd_task_state.py` in the installed Onboard Skill copy, with the interpreter dependencies declared in its `requirements.txt` (PyYAML, jsonschema, markdown-it-py>=4,<5). Markdown structure recognition uses markdown-it-py CommonMark tokens and table source ranges, parse-only, with no rendering and no network. It is a host-native library, not a new CLI, daemon, journal, or scheduler. If the installed helper copy or its declared dependencies are unavailable, say that persistence did not run; never claim a write that no helper performed, and do not fall back to hand-rolled scanning.

`TaskStore(root, read_only=False)` exposes `inspect`, `create`, `select`, `transition`, `set_mode`, `resume`, `reopen`, `protect_local_state`, `promote` and `archive` with the semantics in this reference. It also exposes the read-only `current_binding()` (actual branch, `detached:<full-sha>`, or None for a proven non-Git root), the read-only `recovery_candidates(task_id=None)` (the explicit task, the valid active bookmark, or all recorded candidates — never an mtime pick), and the confirmed `rebind(task_id, expected_branch=..., reason=..., evidence=..., confirmed=False)`. Only unconfirmed `promote` / `archive` return read-only transfer previews; ordinary writes and `rebind` raise `TaskStateError` without confirmation and perform no writes. `protect_local_state` returns a boolean indicating whether protection was added. `promote` / `archive` return a `TaskTransfer` describing status, source/target paths, files, the retained original location and the steps actually completed; failures carry the real `completed_steps` so a retry reconciles instead of duplicating events.

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

Reasons and evidence must be nonempty and safe for Markdown. Escape cell delimiters/newlines without losing meaning. Missing historical evidence is `not-recorded` with an explanation, not an invented path. Private credentials, accounts or source hashes do not belong in a shared event table.

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
