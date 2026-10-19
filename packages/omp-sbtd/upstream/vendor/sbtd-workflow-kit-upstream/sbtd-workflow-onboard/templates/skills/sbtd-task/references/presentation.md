# Presentation modes

This reference controls output only. SBTD default/lite/strict, tool permissions, code, validation and task state do not change when prose is shorter. RTK controls terminal output, Caveman controls reply compression, and i-have-adhd controls reply structure; they are not workflow modes.

## Availability and ownership

Use a visible `caveman` Skill's lite expression rules for automatic updates; the external Skill owns explicit manual modes, while this protocol owns the separate auto-lite lifecycle. Do not rewrite an external mirror, install hooks/statusline/plugins/extensions, or update a pin to enable a style. Onboard owns confirmed installation and managed payload maintenance. An installed payload does not mean a style is active.

An explicit runtime caveman `off` disables both manual and automatic activation. Absent/unexposed configuration is auto, not inferred off. Auto also requires the caveman Skill to be visible. If the required presentation rules cannot be read, do not claim automatic activation; explain the limitation once and keep clear normal output without changing execution mode or installing anything.

## Manual Caveman

Enter only for an explicit request such as `/caveman`, `use caveman`, `caveman mode`, 少说一点, 减少token or 压缩输出. Unspecified intensity is full, according to the external Skill, until normal mode/stop caveman or session end. Manual activation never clears task/session auto opt-outs. Runtime off still wins.

## Auto-lite lifecycle

Maintain in conversation state for the same major objective:

- `progressUpdateCount`: intermediate progress updates, including protected ones.
- `toolResultCount`: independent command/diff/log/read/tool results that have been summarized, including protected ones; they need not be consecutive.
- `autoLiteEligible`: a monotonic latch; `autoLiteActive`: whether automatic activation and its first notice occurred.
- `taskAutoExit`, `sessionAutoExit`, and whether the first notice was sent.

Set eligible immediately when progress count reaches3, result count reaches5, the task is clearly long/context-heavy, or automation/large review/verification has entered repeat rounds. Do not add a subjective requirement that more work must remain, and never reset eligibility within the same major goal.

At the next repetitive, nonblocking intermediate update that needs no user decision and is outside a protection zone, activate auto-lite if not opted out. Announce once in that same update: “后续重复状态更新将自动使用 lite 压缩；说 normal mode 可恢复完整输出并在本任务内停用自动压缩”. Do not send a separate notice. Auto may use lite only, never full/ultra/classical variants. Required progress updates still occur, including long-running tool updates; compression is not permission to stop reporting.

Full-expression protection zones: installation/permission/destructive confirmations; security/privacy/keys/production-data risks; ambiguous ordered or negative instructions; final requirement choices; PRD/design/implementation review gates and task artifacts; README/AGENTS正文; failure reasons, remaining risks, final validation and final answer. User requests for clarity/detail/repetition also get clear complete output. Compression or ADHD formatting cannot remove required evidence fields.

Protection is temporary: retain all counters/latches/opt-outs. Resume auto-lite on the next eligible ordinary update without a new threshold decision or repeated notice. “详细说明” covers the current answer only.

- normal mode / stop caveman / 恢复完整输出 / 不要压缩 / 本任务不要自动压缩 exits manual/auto compression immediately and sets taskAutoExit. No threshold re-enters it during this goal.
- Only 本任务恢复自动压缩 / 重新启用自动压缩 clears taskAutoExit; retain eligibility/counts and resume at the next eligible update.
- 本会话关闭自动压缩 sets sessionAutoExit; only 本会话重新启用自动压缩 clears it. Session opt-out wins over task state, but does not forbid an explicit manual mode unless runtime off.
- Priority: runtime off > sessionAutoExit > taskAutoExit > eligibility/active. Manual lifecycle remains separate.

Only a new major objective resets progress/result counts, eligibility/active and taskAutoExit; sessionAutoExit persists. Continue, confirmation, permission, recovery, status requests, extra evidence or related subtasks under one outcome do not reset them. Compaction/archiving/session resume are not new goals.

Runtime state stays in conversation, not a new config/task subsystem. An authorized handoff may carry a continuation snapshot, not a second live source: retain eligible/active/taskAutoExit/sessionAutoExit and notice-sent state. If a long repeated phase is known but exact counters are lost, retain eligible=true rather than inventing zero. Do not use `caveman-compress` to rewrite durable documents unless explicitly requested.

## i-have-adhd

The required external Skill is installed/maintained by normal Onboard init/reset from the managed stable set, but is not enabled by installation. Activate only for `/i-have-adhd`, adhd mode, ADHD输出 or an explicit preference, and keep it for the session. stop adhd mode or normal mode exits it. There is no automatic ADHD mode.

When active, use action-first scan-friendly structure, short numbered steps, status restatement and one concrete next action; the Skill supplies exact display rules. With Caveman, compression governs length and ADHD governs structure. Neither changes workflow gates or execution mode. Protection zones and final-report requirements win over brevity/no-recap rules. Respect host prohibitions on effort estimates; never replace an unproved cause with a confident story.
