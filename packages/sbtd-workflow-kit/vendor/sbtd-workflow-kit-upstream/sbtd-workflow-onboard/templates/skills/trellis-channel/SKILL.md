---
name: trellis-channel
description: Use when the user requests Trellis Channel, multi-agent, worker, forum, parallel review, cross-validation, or when project rules require high-risk code review / validation preflight. Do not spawn workers unless the user has requested or confirmed Channel runtime.
---

# Trellis Channel Skill

Use this Skill when the user explicitly requests multiple Agents, multiple models, workers, forums, threads, parallel review, cross-validation, external orchestrator collaboration, or when project-level rules require high-risk code review / validation preflight.

`trellis channel` is an explicit collaboration runtime, not the default entry point for ordinary Trellis workflows.

Invoking this Skill for preflight does not mean starting the Channel runtime. Do not silently `spawn` workers unless the user has explicitly requested Channel or explicitly confirms it after preflight.

---

## Core Decision Criteria

- Complexity determines whether to enter Trellis planning.
- The form of collaboration determines whether to enable Channel.
- For decomposing large tasks, prefer parent / child task trees.
- Do not automatically enable Channel merely because a task is large, involves many files, crosses modules, or is complex.
- Do not switch to the `channel-driven-subagent-dispatch` workflow merely because a task is complex.
- Code review / validation review may proactively trigger Channel preflight; actually starting the runtime still requires an explicit user request or confirmation.
- A Trellis-managed platform role sub-agent alone is not a Channel trigger. Platform identity comes from the current host and its generated integration: `.codex/**` for Codex, `.omp/**` for OMP; shared `.trellis/**` files do not identify it. Both integrations may coexist, so static inspection must not choose one. In a current Codex host, auto mode uses a short-lived executor coordinated by the main session; in a current OMP host, it is an OMP `task` worker. Channel remains reserved for durable multi-worker collaboration.
- Each mutation responsibility has one executor: one platform-native Trellis role sub-agent, the main session, or one Channel worker. Do not combine or recursively dispatch mutation executors for the same responsibility. User-requested independent read-only review and cross-validation workers may run in parallel, but only one writer and one validation controller may operate in the same checkout or validation environment.


---

## Scenarios Where Channel Should Not Be Used

- Ordinary single-Agent code changes
- Simple questions and answers
- Small bug fixes
- Routine refactoring
- Adding tests
- Documentation changes
- Ordinary Trellis tasks
- Merely because the task is complex
- Merely because there are many files
- Merely because the task requires `prd.md` / `design.md` / `implement.md`
- Merely because the task requires a parent / child task
- Merely running lint / test / build / browser check
- No active Trellis task, no explicit diff, and no reviewable task artifacts
- Low-risk single-file changes already covered by project validation commands

---

## Scenarios Where Preflight May Be Proactively Performed

This Skill may be proactively invoked for preflight in the following scenarios:

- The user requests code review, pre-commit review, test validation review, validation coverage checks, parallel review, cross-validation, or perspectives from multiple reviewers
- High-risk validation gaps remain after `$trellis-check` or project validation
- GitNexus impact / detect_changes returns HIGH or CRITICAL
- Changes span the frontend, backend, database, deployment, test assets, external services, or release process
- After a validation failure has been fixed, an independent recheck of the cause of failure, coverage, and remaining risks is needed
- The consistency of the Trellis PRD / design / implement with the actual diff, validation results, or rollback strategy requires an independent check

If the user has explicitly requested any of the following collaboration forms, Channel runtime may be used after preflight:

- Multi-Agent collaboration
- Multi-model comparison
- Division of work among Claude / Codex / other workers
- Worker-based implementation or review
- Forum / thread-style discussion
- Parallel review
- Cross-validation
- Persistent conversation records across workers
- Sending messages to workers during execution
- Interrupting the current worker turn
- Waiting for output from multiple workers
- An external orchestrator managing worker lifecycles

---

## Preflight Output

Before starting Channel runtime, the preflight output must include:

- Active task
- Channel goal
- Trigger reason
- Why Channel instead of inline / parent-child task
- Review / validation target
- Proposed worker roles
- Read-only workers
- Writer worker, if any
- Validation controller, if any
- Allowed file areas
- Forbidden actions
- Required inputs
- Expected outputs
- Writeback target
- Stop condition
- Cleanup plan

If the user has not explicitly requested Channel runtime, you must ask whether to enable it after preflight and must not directly spawn workers.

---

## Basic Rules

- Channel does not replace `.trellis/workflow.md`.
- Channel does not replace `$trellis-before-dev`.
- Channel does not replace `$trellis-check`.
- Channel does not replace `$trellis-finish-work`.
- Channel does not replace project validation commands, GitNexus, Playwright, Maestro, Chrome DevTools MCP, browser checks, or final human judgment.
- Channel conclusions do not automatically become `.trellis/spec`.
- Channel runtime / events / forum / thread records are local collaboration logs by default.
- Channel runtime files should not be committed to the remote repository by default.
- `.trellis/agents/<name>.md` is a Channel agent definition file, not a runtime log; if the workflow depends on these definitions, retain or commit them according to project policy.
- If `trellis channel spawn` reports `Agent '<name>' not found`, or the workflow references a missing `.trellis/agents/<name>.md`, first run `trellis update` to generate the agent definition, then continue.
- Channel and worker names must be safe path fragments, using only letters, digits, `.`, `_`, and `-`; do not include spaces, forward slashes, backslashes, `.` or `..`. If invalid Channel directories left over from an older version are skipped, treat this as a local cleanup / migration issue; do not manually construct paths to bypass the safe-name guard.

Long-term conclusions must be consolidated into one of the following locations:

- `.trellis/tasks/<task>/prd.md`
- `.trellis/tasks/<task>/design.md`
- `.trellis/tasks/<task>/implement.md`
- `.trellis/spec`, only when the conclusion belongs to long-term project specifications

## Review / Validation Runbook

A Review Channel is read-only by default. Suitable worker roles include:

- `architecture-reviewer`
- `test-coverage-reviewer`
- `ui-ux-reviewer`
- `api-data-contract-reviewer`
- `release-risk-reviewer`

A Validation Channel is used for validation planning, coverage review, and independent rechecking; it does not replace running project validation in the main session.

Rules:

- The main session is responsible for ultimately running or confirming validation commands.
- Workers may suggest commands, review Playwright report / trace, Maestro artifacts, Chrome DevTools MCP screenshots / trace / network evidence, and project test logs, and identify validation gaps.
- Do not run validation commands that can interfere with one another in parallel in the same checkout.
- Environment-sensitive validation such as Docker, database migrations, browser E2E, and Vercel deploy should be controlled serially by the main session.
- If a worker indicates that code must be modified, return to the main session for confirmation before the sole writer performs the modification.

## Ownership Rules

- Review / validation workers are read-only by default.
- Only one writer worker is allowed at a time in the same checkout.
- Only one validation controller is allowed at a time in the same validation environment.
- When multiple workers need to modify code, prefer splitting the work into parent / child tasks or using independent worktrees.
- Workers must not stage, commit, archive, finish-work, push, or deploy unless explicitly authorized by the user and the worker is the sole writer / controller.
- When worker outputs conflict, the main session must adjudicate and document the reasons for accepting / rejecting them.

## Worker Prompt Envelope

The prompt sent to a worker must include:

- Active task path
- Current phase
- Relevant `AGENTS.md` hierarchy
- Relevant `prd.md` / `design.md` / `implement.md`
- Relevant `.trellis/spec` and lessons matched as needed
- Role and scope
- Forbidden actions
- Output schema

## Worker Output Schema

Each review / validation worker must output in the following format:

- Verdict: `pass` / `concerns` / `block`
- Scope reviewed
- Evidence
- Findings
- Required changes
- Optional suggestions
- Validation gaps
- Files referenced
- Confidence
- Should write back to

## Worker Guard

When using `trellis channel spawn`, follow the `channel.worker_guard` settings in `.trellis/config.yaml`.

When Channel context must read a linked worktree, use `channel.trusted_context_dirs` only for the specific resolved external task or workspace directory that the user intends to trust. Do not make a broad parent-directory allowlist, manually dereference nested symlinks, or bypass Trellis containment checks. The default narrow handling of top-level `.trellis/tasks` and `.trellis/workspace` symlinks remains preferable; disabling it requires an explicit compatibility reason.

Default principles:

- Allow idle worker cleanup to take effect.
- Allow the live worker budget to take effect.
- Do not increase `--max-live-workers` without justification.
- Do not disable, extend, or bypass `--idle-timeout` without justification.
- Do not keep workers resident while idle for long periods.
- A mid-turn worker should not be treated as an idle worker.
- If the user requests high reasoning / Ultra-tier models to run multiple workers concurrently, first explain the usage and cost risks in the preflight, and prefer recommending lower concurrency, narrower worker scope, serial review instead, or using high reasoning only for critical workers.
- If a worker is killed due to idle timeout, state this in the output.

Overriding the default worker guard requires an explicit reason, for example:

- The user explicitly requests long-lived workers
- An external orchestrator requires long-lived workers
- The current task genuinely requires multiple workers to run in parallel

After overriding it, you must state:

- Which parameters were overridden
- Why they were overridden
- Potential resource risks
- Whether workers have been cleaned up

## Windows Worker Spawn

When running Channel workers on Windows, npm CLI may expose the actual provider executable through a `.cmd` shim. If `trellis channel spawn`, `run`, or supervisor startup fails with errors related to `.cmd`, `.exe`, `spawn`, `ENOENT`, `EACCES`, provider paths, or shell execution:

- First confirm that Trellis CLI has been upgraded, and run `trellis update` in the project to refresh the Channel runtime / agent definitions.
- Verify that the provider CLI itself can be executed directly, for example `codex --version` or `claude --version`, and record the actual executable resolved from PATH.
- Do not change worker startup to arbitrary `shell: true` usage or a handwritten shell wrapper to bypass `.cmd` shim issues; prefer the spawnable executable resolution capability already provided by Trellis.
- If it still fails, record the provider, Trellis version, PATH resolution result, spawn error, and worker config in task artifacts or the Channel check summary before deciding whether to fall back to inline review / validation.

---

## Message Routing

Do not rely on message tags for `send` / `wait` / `run` routing.

When targeting a specific worker, prefer:

- An explicit `to`
- worker inbox policy
- channel events
- Explicit routing mechanisms supported by the current Trellis Channel

Interrupts must use the dedicated interrupt flow; do not simulate them through ordinary tag routing.

---

## Codex Multi-Agent

- In a current Codex host with `.codex/**` integration, use shared `.trellis/config.yaml`, `.trellis/workflow.md`, and task artifacts to determine the `native` / `tdd` workflow gates; then apply effective Codex dispatch. In auto mode, the main session coordinates one role executor per responsibility; do not force ordinary Trellis tasks into the Codex Inline main session.
- `dispatch_mode=inline` is an explicit main-session choice. An invalid explicit Codex dispatch value fails closed to effective Inline; report and repair it before continuing, and do not dispatch role subagents while fallback is active. Effective Trellis-managed role dispatch is distinct from both Inline and Channel.
- Prefer `trellis channel` only for Trellis Multi-Agent work requiring durable peer workers, multi-round conversation, interruption or waiting, a shared event log, or forum / thread history.
- Do not rely on Codex's built-in `features.multi_agent_v2` as the primary Trellis workflow.
- Do not add `[features.multi_agent_v2]` to the project-level `.codex/config.toml`.
- When Trellis generates or updates Codex project config, it should not generate a `[features.multi_agent_v2]` block; this prevents compatibility differences in structured feature tables across Codex CLI versions from blocking Codex startup.
- If the project inherited a `[features.multi_agent_v2]` block generated by an older version of Trellis, prefer running `trellis update` to regenerate `.codex/config.toml`; do not manually retain the project-level structured feature table configuration.
- If testing or tuning Codex's built-in multi-agent is truly necessary, place it only in the user-level `~/.codex/config.toml` after confirming Codex CLI version compatibility.
- Do not mix Trellis Channel with Codex's built-in multi-agent unless explicitly testing that behavior.
- Avoid recursive dispatch, nested subthreads, or recursively nested sub-threads.

---

## Required Consolidation After Use

After using Channel, valid conclusions must be consolidated back into the project context.

Minimum requirements:

- State the channel name
- State the worker type
- State the primary inputs
- State the primary outputs
- State whether the output has been written back to task artifacts or .trellis/spec
- State whether any workers are still alive
- State whether runtime state has been cleaned up

If Channel was used only for temporary review or discussion and does not need to be retained long-term, clean it up or explicitly state why it was not cleaned up.

---

## Output Requirements

At the end of the task, if Channel was used, the final output must include:

- Channel name
- Workers / Agents used
- Whether an interrupt occurred
- Whether any worker was killed by idle timeout
- Whether any workers remain uncleaned
- Key conclusions
- Conclusion writeback location
- Validation results
- Remaining risks