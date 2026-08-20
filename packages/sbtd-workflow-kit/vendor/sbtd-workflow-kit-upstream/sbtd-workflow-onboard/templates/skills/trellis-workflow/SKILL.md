---
name: trellis-workflow
description: Use for Trellis workflow tasks, including requirement clarification handoff, reading .trellis/workflow.md, task artifacts, before-dev, check, finish-work, update-spec, workflow template handling, and parent/child task handling. Do not use for non-Trellis projects.
---

# Trellis Workflow Skill

Use this Skill when the repository uses Trellis.

This Skill is responsible for the Trellis lifecycle, task artifacts, phase checks, workflow template decisions, before-dev, check, finish-work, update-spec, and parent / child task handling.

---

## Before Starting Work

1. Check whether `.trellis/` exists.
2. Read `.trellis/workflow.md`.
3. Read the relevant `.trellis/spec`; among them, `.trellis/spec/lessons.md` is the short entry point and high-priority summary.
4. Do not read the complete `.trellis/lessons/**` by default; first search as needed through `.trellis/lessons/index.md`, tags, error messages, or the current task topic, then read the matched topic / archive files.
5. If there is a currently active task, read:
   - `prd.md`
   - `design.md`, if it exists
   - `implement.md`, if it exists

`.trellis/workflow.md` is the workflow actually in effect for the current project.
All Trellis phase decisions must be based on this file.

## Requirement Clarification and PRD Entry Point

Trellis is responsible for the task lifecycle; it does not replace requirement clarification, domain terminology alignment, or PRD generation.

When the user provides only an initial requirement, and the requirement involves the project domain model, business terminology, long-term rules, existing documentation, or architectural decisions:

1. Before creating or rewriting Trellis task artifacts, preferentially use `grill-with-docs`.
2. First read the project's existing documentation and relevant code, such as `docs/CONTEXT.md`, `docs/contexts/<context>/CONTEXT.md`, `docs/adr/`, `.trellis/spec`, README, and relevant implementations; if the project already uses root-level `CONTEXT.md` or `CONTEXT-MAP.md`, read those as well; do not ask the user questions that can be answered from project facts.
3. Following the cadence of `grill-with-docs`, ask only one key question at a time and provide a recommended answer.
4. Only write terminology into the project's designated context documentation when long-term consensus has been reached; use `docs/CONTEXT.md` by default, and use `docs/contexts/<context>/CONTEXT.md` for multi-context projects; do not create a root-level `CONTEXT.md` unless the project already uses that path or project rules explicitly specify it; do not turn CONTEXT into a temporary specification.
5. Suggest writing an ADR only when a decision simultaneously meets all three conditions: difficult to roll back, surprising without context, and involving real trade-offs; write to `docs/adr/*.md` by default, and write to `docs/contexts/<context>/adr/*.md` for multi-context projects.
6. After consensus is reached, every completed `grill-with-docs` session, regardless of whether the Agent or the user initiated it, must be followed immediately by `book-ddd-distilled-modeling` as an independent second-pass boundary review. `domain-modeling` inside `grill-with-docs` does not satisfy or replace this gate.
7. Output a visible `DDD Boundary Review` with status `confirmed`, `needs-clarification`, or `blocked`, covering ubiquitous language, bounded-context assumptions, invariants, subdomain classification, corrections to the `grill-with-docs` result, and open conflicts.
8. If the review is not `confirmed`, resolve each finding through one-question-at-a-time clarification and rerun `book-ddd-distilled-modeling`; the workflow must not advance to requirement confirmation, PRD, design, task creation, or implementation.
9. After the review reaches `confirmed`, output a requirement confirmation summary covering the goal, users / scenarios, in-scope and out-of-scope items, terminology, constraints, acceptance criteria, and open questions.
10. Before outputting the requirement confirmation summary, a PRD / design / implement review gate, or `task.py start`, state the usage status of `grill-with-docs` and the latest `DDD Boundary Review` status. If `grill-with-docs` was not fully invoked, explain why. Ask only when using versus skipping the Skill presents a material trade-off that could change requirements, domain boundaries, or implementation decisions; otherwise proceed from the established project facts without creating a confirmation gate.
11. After the user confirms the summary, use `to-spec` to generate the Markdown spec / PRD; in a Trellis project, write or update the final spec / PRD in `.trellis/tasks/<task>/prd.md`.
12. After the spec / PRD is confirmed, use `to-tickets` to split it into Trellis-ready vertical slices, marking dependency order, AFK / HITL, acceptance criteria, and testing strategy; the decomposition results should be materialized as parent / child task artifacts under `.trellis/tasks/<task>/...`.
13. After running the PRD convergence pass, create or select a task according to `.trellis/workflow.md`, then continue through the Trellis phases.

The PRD convergence pass must be lossless consolidation: merge temporary brainstorm sections, resolved questions, duplicated facts, and parallel bug / requirement lists into stable goals, requirements, technical notes, acceptance criteria, or out-of-scope sections; do not discard existing requirements, evidence, severity, acceptance criteria, or explicit user scope decisions.

If the requirement is only a general solution inquiry and has no project documentation or domain terminology constraints, `grill-me` may be used instead of `grill-with-docs`.

`$trellis-brainstorm` may be used to clarify ambiguous requirements within Trellis, but it does not replace `grill-with-docs` when the requirement needs to be checked against project documentation, domain language, or ADRs.

### Transparency of grill-with-docs Usage Status

During Phase 1 planning, in the requirement confirmation summary, at a PRD / design / implement review gate, or before `task.py start`, state according to the global rules whether `grill-with-docs` was fully invoked and explain any omission. Ask only when using versus skipping the Skill presents a material trade-off; otherwise proceed from established project facts.

When `grill-with-docs` was fully completed, also state whether the mandatory `book-ddd-distilled-modeling` second pass ran and output its visible `DDD Boundary Review`. A missing, unreadable, or evidence-blocked reviewer is `blocked`, not a reason to skip the gate.

Do not execute `$trellis-before-dev` or begin implementation before the requirement confirmation summary, PRD, or task artifacts are stable.

## Workflow Template Rules

If Trellis supports workflow templates, a workflow may be selected / switched during initialization or later through `trellis workflow`.

Default rules:

- Do not proactively switch workflow templates without an explicit user request.
- `native` may be used as the default standard workflow.
- Use `tdd` only when the user explicitly requests TDD, the project already follows a test-driven process, or the current task is a high-risk behavioral modification suitable for tests-first development.
- BDD is not an independent workflow template; user-visible behavior is executed by default through `gherkin-bdd` as a workflow overlay.
- Use `channel-driven-subagent-dispatch` only when the user explicitly requests a durable Channel / multi-Agent collaboration process; Trellis-managed platform role subagent dispatch remains part of the effective `native` or `tdd` workflow.
- Even if a `channel-driven-subagent-dispatch` template exists, do not automatically switch to or enable that template merely because the task is complex.
- After switching workflows, `.trellis/workflow.md` must be read again, and the new file must be treated as authoritative.
- If the workflow references `.trellis/agents/<name>.md` but the file does not exist, first run `trellis update` to generate the missing channel runtime agent definition, then continue the Channel workflow.

Decision principles:

- Complexity determines whether to enter Trellis planning.
- The collaboration model determines whether to enable Channel or a channel-driven workflow.
- For large tasks, preferentially consider parent / child tasks; do not switch to a Channel workflow by default.

## Codex Dispatch and Channel Boundary

- Shared `.trellis/config.yaml`, `.trellis/workflow.md`, and task artifacts define workflow gates, not platform identity. The current host and generated integration decide execution: `.codex/**` for Codex and `.omp/**` for OMP. Both may coexist; static inspection must not select a runtime.
- **Codex only, when the current host is Codex and `.codex/**` integration is available:** in `native` or `tdd`, an effective Codex `dispatch_mode=auto` keeps the main session as phase coordinator and dispatches one Trellis-managed role subagent for each responsibility in the required `trellis-implement` → `trellis-check` sequence. A role subagent executes its assigned responsibility; this is not a `trellis channel` runtime.
- **Codex only, when the current host is Codex and `.codex/**` integration is available:** `dispatch_mode=inline` is an explicit project or user choice that keeps implementation and checks in the main session. An invalid explicit Codex dispatch value also fails closed to effective Inline: report and repair the invalid setting before continuing, and do not dispatch Codex role subagents while that fallback is active.
- **OMP, when the current host is OMP and `.omp/**` integration is available:** use the generated OMP `task` workers and `trellis-implement` / `trellis-check` agent definitions. Do not apply or infer `codex.dispatch_mode` or its Inline fallback; read the generated OMP extension and obey its workflow planning gate instead.
- Channel is a separate durable, multi-round, interruptible collaboration runtime. Start it only after an explicit user request or explicit confirmation following Channel preflight.
- Each mutation responsibility has exactly one executor: one platform-native Trellis role subagent, the main session, or one Channel worker. Do not double-dispatch or recursively dispatch that mutation responsibility. User-requested independent read-only review and cross-validation may run in parallel, but only one writer and one validation controller may operate in the same checkout or validation environment.

Workflow selection table:

| Scenario | Recommended approach |
|---|---|
| Documentation, configuration explanations, styling, small templates, low-risk localized changes | `native` workflow |
| Bug fixes, core business logic, algorithms, data transformation, synchronization / import / export, changes requiring regression tests | `native` workflow + proactively assess the `tdd` Skill |
| Permissions, billing, state machines, critical data consistency, complex algorithms, high-risk backend logic, or projects that have explicitly adopted a test-driven process | Trellis `tdd` workflow + `tdd` Skill |
| UI, API, CLI, exported files, notifications, permission outcomes, error responses, state changes, or externally observable integration behavior | Current workflow + `gherkin-bdd` overlay |

Do not switch every task to the Trellis `tdd` workflow by default merely to “place more emphasis on testing”; preferentially invoke the `tdd` Skill as needed within `native`. Switch to the Trellis `tdd` workflow only when the task itself requires tests-first development to become a phase constraint.

---

## Trellis TDD Workflow and `tdd` Skill

The Trellis `tdd` workflow is for task lifecycle and phase orchestration; the `tdd` Skill is the tests-first method used during concrete implementation. They can be combined, but neither can replace the other.

When the project actually uses the Trellis TDD workflow, or the user explicitly requests Trellis TDD:

- Continue executing Trellis phases according to `.trellis/workflow.md`.
- Still execute `$trellis-before-dev` before development.
- During concrete implementation, if the `tdd` Skill is available, use `tdd` to guide red-green-refactor.
- Still execute `$trellis-check` and the project's validation commands after development.

When the project uses the Trellis `native` workflow:

- Do not prohibit the `tdd` Skill because the workflow is `native`.
- For bug fixes, core business logic, algorithms, data transformation, synchronization / import / export, high-risk changes, or changes requiring regression tests, you must proactively assess whether to use the `tdd` Skill.
- If the `tdd` Skill is skipped after proactive assessment, the final output must explain why, for example: no testable interface, no testing framework in the project, the change is only documentation / configuration, or the current risk is already covered by existing tests.
- Do not require `tdd` for simple copy, styling, configuration explanations, or pure documentation changes.

---

## BDD Overlay and `gherkin-bdd` Skill

BDD is the default hard rule for user-visible behavior and does not replace the Trellis workflow. Trellis manages the task lifecycle; `gherkin-bdd` manages user-visible behavior specifications.

Applicable scope:

- UI, API, CLI, exported files, notifications, permission outcomes, error responses, state changes, and behavior observable by external integration systems.
- User-visible bug fixes.
- User-visible behavior appearing in Trellis `prd.md`, `design.md`, `implement.md`, or acceptance criteria.

Skip scope:

- Pure internal refactoring, dependency / tooling configuration, and mechanical formatting.
- Typos, visual polish, className / token / CSS refactoring, or layout cleanup that does not change behavior or semantics.

Language rules:

- When `.feature` files or project-level persistent BDD specifications already exist, follow the existing language and keyword style of the same bounded context or functional area.
- When the project has no `.feature` files and the user has not explicitly requested another language, use Chinese scenario titles, descriptions, and step text by default, with English Gherkin structural keywords.
- English PRDs, design documents, implementation documents, code identifiers, or product names must not override the default language decision above; domain-specific names may be preserved according to the glossary / `docs/CONTEXT.md` / `.trellis/spec`.

Phase orchestration:

1. Requirements / PRD phase: `prd.md` may draft Given/When/Then, but user-visible behavior must enter a persistent `.feature` file or a persistent BDD specification path designated by project-level rules before implementation.
2. Language decision: before creating or rewriting a `.feature` file, first inspect existing `.feature` files, BDD runner configuration, and project rules; if there are no existing `.feature` files and no user override, explicitly record “Chinese scenario text + English Gherkin keywords.”
3. When frontend and backend are in separate repositories, or a cross-service, Web + API, Mobile + API, or Hybrid chain is incomplete, first record `Cross-repo context`: `complete` / `contract-only` / `environment-only` / `missing`; when contract, account, environment, device, selector, or data facts are missing, do not treat the scenario as confirmed.
4. When domain terminology is unclear: first use `grill-with-docs` and `book-ddd-distilled-modeling`, then finalize the scenario text.
5. Before development: before running `$trellis-before-dev`, confirm that added / modified / fixed user-visible behavior has corresponding BDD scenarios, or explicitly state the reason for skipping BDD; also confirm that scenario text conforms to the language decision.
6. During development: derive tests from BDD scenarios. When a Gherkin runner exists, bind step definitions or runner tests; when no runner exists, use the project's existing testing framework and trace tests back to scenarios through test names, comments, directory structure, or project conventions.
7. Bug fixes: first write the correct-behavior scenario, then write a failing regression test, then fix the bug.
8. `$trellis-check`: verify that the PRD, persistent `.feature` files, tests, and code are consistent, and check whether the `.feature` language status is: following the project's existing style, default Chinese scenario text + English keywords, explicit user override, or blocked.

Existing projects use `no new uncovered behavior`: untouched historical behavior may temporarily have no `.feature`; new or touched user-visible behavior must be covered.

Default persistent paths:

- Follow project conventions when existing `.feature` files / a BDD runner / project rules exist.
- For a single-application project, default to `<project-root>/features/<capability-slug>.feature`.
- For a monorepo, default to `features/**/*.feature` under the owning workspace.
- `.trellis/tasks/**` stores only process artifacts and is not the default long-term behavioral source of truth.

For confirmed user-visible behavior, the persistent `.feature` file is the behavioral source of truth; the PRD explains context and intent, while `design.md` / `implement.md` explain the technical approach. When conflicts exist, first align the PRD and `.feature`, then implement.

---

## Task Artifacts

- `prd.md`: requirements, constraints, acceptance criteria
- `design.md`: technical design
- `implement.md`: implementation plan
- `implement.jsonl` / `check.jsonl`: implementation / check context manifests for sub-agent-capable platforms

Current task artifacts take precedence over general assumptions.

Where a generated workflow classifies its platform as sub-agent dispatch, `implement.jsonl` and `check.jsonl` must both contain real spec / research / task artifact entries before `task.py start` or dispatch begins; seed / `_example` rows are tolerated by runtime consumers for compatibility but are never planning-ready. Codex effective Inline, including its invalid-config fail-closed fallback, skips JSONL curation; report and repair a Codex invalid dispatch setting instead of treating a seed-only sub-agent task as ready. For OMP, obey the generated workflow's planning gate: its extension may parse role-specific JSONL non-fatally, but that does not relax workflow readiness.

`.trellis/spec` stores only long-term project rules.

`.trellis/spec/lessons.md` is the required short entry point for lessons, not the complete historical repository. Complete lessons are stored by default in:

- `.trellis/lessons/index.md`
- `.trellis/lessons/topics/<topic>.md`
- `.trellis/lessons/archive/YYYY-QN.md`

Do not read all of `.trellis/lessons/**` by default; only after a match based on the current task, error message, tool name, language, tags, or the index's `read_when`, read the corresponding topic or archive.

Do not write the following directly into `.trellis/spec`:

- One-off checklists
- Temporary research
- Local implementation notes
- Plans applicable only to the current task

---

## Common Commands

- `$trellis-continue`: resume interrupted work
- `$trellis-before-dev`: execute before code modifications
- `$trellis-check`: execute after code modifications
- `$trellis-finish-work`: execute after validation passes
- `$trellis-update-spec`: update long-term project specifications
- `$trellis-brainstorm`: clarify ambiguous requirements within a Trellis task; when project documentation and domain terminology alignment are required, use `grill-with-docs` first

## Trellis Updates and Migrations

When upgrading Trellis, switching templates, or discovering missing generated files, preferentially run `trellis update`, then reread `.trellis/workflow.md`, the relevant `.trellis/spec`, and the current task artifacts.
- When `trellis update` changes SessionStart, PreToolUse, or other hook configuration, restart the affected Agent host or IDE before testing the refreshed hook behavior; an already-running process is not evidence that the new hook configuration loaded.

- Run `trellis update --migrate` if the upstream migration manifest recommends it, the project contains the misspelled `trellis-spec-bootstarp/` skill directory, or a Pi project has legacy `.pi/skills/`; let Trellis perform the cross-platform directory rename rather than moving or deleting these directories manually.
- `trellis update` may install new bundled skills, platform templates, or `.trellis/agents/{check,implement}.md` channel runtime files; these are generated Trellis workflow assets, not channel runtime logs.
- When an update changes sub-agent context injection, preserve the default bounded injection behavior. Review `.trellis/config.yaml` before raising `context_injection` byte limits; treat `0` (unlimited) as an explicit, user-owned trade-off rather than a workaround for missing task artifacts. Binary referenced files may be represented by a notice instead of inlined content, so inspect the referenced path rather than retrying dispatch with copied binary data.
- For Codex hook-based sub-agents, treat saved `SubagentStart` output as the recovery source when an injected marker is incomplete. After `trellis update`, verify the generated `trellis-{implement,check,research}` agents retain a single context prelude and recover context without manually pasting task data or increasing injection limits.
- The configured `prompt_injection.skip_keyword` can suppress per-turn workflow-state injection for the matching turn. Do not infer that a skipped breadcrumb disables Trellis task rules, required artifacts, or explicit workflow commands.
- Treat `channel.trusted_context_dirs` as a narrow allowlist for known linked-worktree locations. Do not broaden it to arbitrary external directories or bypass containment checks; when a top-level `.trellis/tasks` or `.trellis/workspace` symlink is intentional, confirm its resolved destination and review the generated configuration.
- `trellis update` preserves user-set `model` and `model_reasoning_effort` keys in generated `.codex/agents/trellis-*.toml`. Preserve only these documented user-owned keys; after updating, verify the agent files retain the intended settings and that the generated context prelude remains singular.
- When Trellis adds or renames an AI platform, review the generated commands, skills, agents, shared skills directories, and the project's `.gitignore` / commit policy; do not treat reusable platform template directories, runtime logs, and local caches as the same category.
- For agent-capable platforms without session-start / per-turn hooks, after updating, you must confirm that an explicit workflow startup entry point still exists, such as the `trellis-start` skill or `/trellis:start` command; do not assume startup context will be injected automatically merely because the platform supports agents.
- For platforms that support both CLI agent hooks and IDE hook files, after updating, separately review the main-session agent, sub-agent, per-turn prompt hook, session-start hook, and workflow resource injection; do not inspect only the sub-agent hook or only the IDE configuration.
- For class-2 platforms using a pull-based sub-agent prelude, implement / check dispatch must remain in the pull-based routing path; do not place these platforms in the hook auto-handles branch. After updating, verify that the corresponding agent definitions still proactively read task artifacts, `implement.jsonl` / `check.jsonl`, and the active task.
- When Trellis adds platform support, review whether commands, skills, agents, hooks, settings, or equivalent configurations involved in `init` / `update` / `uninstall` are managed as a complete set; if main-session hooks and sub-agent context loading use different mechanisms, validate both paths.
- For platforms such as Pi where session-start can only notify and cannot directly inject model context, after updating, you must confirm that startup context still has a valid injection path and manual fallback, such as agent-start extension injection, start prompts, agent tools frontmatter, and tool-name casing conventions; do not inspect only whether `session_start` configuration exists.
- For optional platform hooks, statusline, or status-bar enhancements, do not assume `trellis update` will forcibly install, delete, or rewrite them; enable them only when the user selects the corresponding init/update flag, the project already has the configuration, or the manifest explicitly requires it, and review the generated diff.
- When using registry-backed spec templates, `trellis update` may refresh `.trellis/spec`; you must review hash / conflict prompts and the actual diff, and must not silently overwrite long-term project specifications.
- Trellis updates may refresh filesystem-safety behavior, including atomic state writes, task archive guard, Channel safe-name guard, uninstall dirty-data guard, active-task pointer containment, AGENTS managed-block scrubber, template overwrite temp-first swap, rename-dir ownership check, and traces-to-journal non-clobber migration; after updating, review the generated diff before performing operations that delete, move, overwrite, or resolve paths by name. Do not assume `trellis update` rewrites existing session pointers; if a task ref resolves outside the project, treat it as no active task instead of following the escaped path.
- When `trellis uninstall --yes` or an automated uninstall encounters an uncommitted-data guard for `.trellis/spec`, `.trellis/tasks`, or `.trellis/workspace`, do not set `TRELLIS_ALLOW_DIRTY_UNINSTALL=1` to bypass it unless the user has explicitly confirmed the backup and deletion scope; preferentially run a dry-run first or ask the user to manually clean up / commit the relevant data.
- When a Trellis update involves workflow phases, step numbering, status routing, or resume / continue behavior, after updating, you must review whether the generated workflow, `/continue` command, workflow variants, bundled skill references, and platform prompts remain aligned with `.trellis/workflow.md`; do not inspect only references containing the words `Phase X.Y`, but also inspect bare numeric routing.
- If a command reports that `.trellis/agents/<name>.md` referenced by the workflow is missing, first run `trellis update`, then retry the workflow or Channel operation.

## Troubleshooting Codex Sub-agent Generated Files

Trellis sub-agent TOML files for the Codex platform are generated jointly by templates and the context prelude injector.

If `Required: Load Trellis Context First` appears repeatedly in `.codex/agents/trellis-check.toml` or `.codex/agents/trellis-implement.toml`:

- Preferentially run `trellis update` to regenerate `.codex/agents/`.
- Do not manually preserve or maintain duplicate preludes.
- After updating, check that each relevant agent file retains only one context-loading prelude and can still locate the active task and read `check.jsonl` / `implement.jsonl` and task artifacts.

---

## Before Development

Run:

```bash
$trellis-before-dev
```

Do not begin implementation before completing this step.

---

## After Development

Run:

```bash
$trellis-check
```

During the check, you must compare against:

- `prd.md`
- Persistent `.feature` files or the BDD specification path designated by project-level rules, for user-visible behavior
- `design.md` / `implement.md`, if they exist
- `.trellis/spec`
- `.trellis/spec/lessons.md` and the `.trellis/lessons` topic / archive matched as needed
- The actual code diff
- Validation command results

Do not complete the task without executing $trellis-check.

---

## Book-derived Skill Gate

During requirements, design, implementation, and validation phases, first produce a task-level `Book Gate Plan`. For each bundled book-derived Skill, record `required` or `on-demand`, objective trigger evidence, execution phase, and a separate Gate state: `planned` / `running` / `passed` / `blocked` / `not-required`. A required or selected on-demand gate starts `planned`; an unselected on-demand gate is `not-required`; the only normal transition is `planned` → `running` → `passed` / `blocked`. Record the reviewer-specific status only after that Skill actually runs. The workflow must not downgrade a matched mandatory gate to on-demand because the Agent expects a low-risk result; only changed scope or project evidence may remove the trigger, and that change must be recorded.

Do not invoke all 5 Skills mechanically for every task. The following objective development triggers are mandatory; unmatched scenarios remain on-demand and may still invoke a Skill because the user requests it or a secondary risk warrants it.

Phase orchestration:

- Requirements / PRD phase: every completed `grill-with-docs` session must immediately invoke `book-ddd-distilled-modeling`, emit a visible `DDD Boundary Review`, and reach `confirmed` before `to-spec` / `to-tickets`; this is mandatory even when the embedded `domain-modeling` pass found no ambiguity. When `grill-with-docs` was not used, invoke `book-ddd-distilled-modeling` independently only when business terminology, domain rules, bounded contexts, or model boundaries warrant it.
- Design phase: when persisted or shared data, schemas / migrations, shared / persistent / cross-request / cross-process cache, queues / events / streams / jobs, ETL / analytics, cross-service data flow, data ownership, source of truth, transaction boundaries, read / write paths, backfill, replay, rollback, or recovery changes, invoke `book-ddia-data-design` before design artifacts become stable or implementation begins. Emit `DDIA Data Design Review` with status `confirmed`, `needs-design-change`, or `blocked`; do not advance until `confirmed`.
- Before behavior changes: for every existing-behavior bug fix, or when existing code has weak / missing tests, unclear behavior, hidden dependencies, or high regression risk, invoke `book-legacy-change-safety` before the first behavior-changing edit. Emit `Legacy Change Safety Review` with status `characterized`, `needs-safety-net`, `seam-required`, or `blocked`. Use `seam-required` only when current behavior and preserved behavior are established but the safety net requires a production seam.
- Before implementation edits: whenever the task modifies existing production code, invoke `book-refactoring-pass` before the first implementation edit to existing production code. Emit `Refactoring Review` with status `proceed`, `refactor-first`, or `blocked`; `proceed` may explicitly conclude that no refactoring is needed, while `refactor-first` requires the smallest behavior-preserving refactor and a rerun before feature or fix edits.
- After validation / before completion: when production-path services, APIs, auth, billing, notifications, background jobs, queues, schedulers, external integrations, data pipelines, or deployment behavior changes, invoke `book-release-readiness` after all applicable testing-tool gates and project validation, but before the task is declared complete, the final release decision, or Channel preflight. Emit `Release Readiness Review` with status `ready`, `needs-mitigation`, or `blocked`; required validation that did not run is always `blocked`, while only an optional check may be accepted by an explicit accountable owner as residual risk.

If the legacy and refactoring gates both match, normally complete `Legacy Change Safety Review` first, then `Refactoring Review`. Controlled exception: `seam-required` → `Refactoring Review` (`safety-seam-only`) → implement and validate only the smallest behavior-preserving test seam → rerun legacy to `characterized` → rerun the normal refactoring gate. No feature / fix behavior or unrelated cleanup is allowed in `safety-seam-only` mode. For any `needs-*`, `seam-required`, or `refactor-first` result, keep Gate state `running`, complete the correction, and rerun the relevant Skill. A missing Skill or missing evidence is `blocked` for a matched mandatory gate rather than a skip.

Conclusions from book-derived Skills should preferentially be written into the current task's `prd.md`, `design.md`, `implement.md`, or check summary. Only long-term architecture, APIs, data models, permissions, business rules, or technical conventions belong in `.trellis/spec`.

---

## Testing Tool Gate

After `$trellis-check` and project validation, but before the Phase 3.4 commit plan, if the task involves Web UI, API integration, end-to-end flows, mobile App user journeys, Hybrid Apps, user-visible bug fixes, pre-release smoke testing, or repeatable regression validation, you must proactively determine whether Chrome DevTools MCP, Playwright MCP, Playwright CLI, Maestro CLI, Maestro MCP, and `web-ui-autotest-generator` apply, according to project-level `AGENTS.md` and the `project-validation` Skill.

The Trellis phase is responsible only for the following requirements:

- Do not treat Chrome DevTools MCP, Playwright MCP, Playwright CLI, Maestro, or Web UI automated testing assets as substitutes for `$trellis-check`, project validation, or human review.
- When Playwright CLI, Java, Maestro CLI, MCP configuration, test accounts, authentication methods, the test environment, devices, simulators, app binary, appId / bundleId, or service URL are unavailable, record `blocked`; do not claim that testing is complete.
- For API, Web E2E, Mobile E2E, or Hybrid E2E, `E2E Mode` must be recorded before the Phase 3.4 commit plan as one of: `full-stack` / `contract-backed` / `mock-backed` / `app-mocked` / `smoke-only` / `backend-only` / `blocked`. mock-backed, app-mocked, or contract-backed tests must not be reported as a full-stack pass.
- When mocks are required, confirm that mock behavior comes from a contract, schema, real response, existing fixture, or user confirmation; otherwise mark `Mock Strategy` as `blocked`.
- If Mobile / Hybrid E2E requires generating or maintaining Maestro flows from BDD scenarios, before the Phase 3.4 commit plan you must confirm that `maestro/flow/*.yml` has been generated / reused according to `maestro-mobile-e2e`, that the full regression flow is fixed as `maestro/flow/smoke.yml`, and that the `Maestro Flow Assets` status has been recorded.
- If iOS / Android require different flows, `maestro/flow/ios/*.yml` and `maestro/flow/android/*.yml` may be used; each flow must trace its source `.feature`, Scenario, platform, and test mode.
- Before the Phase 3.4 commit plan, you must record the `rtk` decision for unit tests, API / integration tests, Playwright Web E2E, and Maestro Mobile / Hybrid E2E as: `used` / `skipped-for-report` / `fallback-native` / `not-available` / `not-needed`. For any test in this cycle that must produce coverage, JUnit, HTML, JSON, trace, raw report, or Markdown summary, use the native command or a project-defined no-cache / report-safe command by default; if `rtk` was used and report files are missing, mtime / size did not change, content does not correspond to the current run, or output indicates cache hit / replay / skipped writing, you must rerun with the native command before determining validation and report status.
- When formal reports will serve as PR evidence or be read by a knowledge base, before the Phase 3.4 commit plan record only the current local evidence status, intended publication target, and sidecar / envelope plan; dirty developer-local results may only be `local-only` and cannot prove the PR head. After creating the final commit and before publishing or updating the PR Check, you must execute `post-commit evidence refresh`: regenerate or revalidate evidence against the final PR head SHA, update the complete commit SHA, worktree state, trigger, `Source Revision`, `Environment Alignment`, and `Evidence Publication` in the report sidecar / envelope, and invalidate evidence from before the commit or from an old head. `ci` evidence must likewise be bound to the final PR head SHA; knowledge-server results must include the exact revision set, and `branch_slug` must not serve as version identity.
- Before the Phase 3.4 commit plan, you must distinguish diagnostic runs from formal validation runs. Playwright `--reporter=list`, custom API scripts that only print terminal output, stdout-only Maestro runs, and any command that does not enable the project's reporter / output path count only as diagnostics or targeted reruns; if the corresponding API / Web E2E / Mobile E2E / Hybrid E2E is within this cycle's formal validation scope, you must additionally run the planned-scope command with a reporter enabled, or capture API stdout / stderr / exit code and promote it to a formal raw report, or mark `Final Test Report` / `Run Summary MD` as `blocked`.
- If Playwright executes and produces `index.html`, `results.json`, `junit.xml`, or equivalent runner artifacts, before the Phase 3.4 commit plan you must confirm that the named report is located in `tests/e2e/reports/html/`, that its name follows `playwright-report-{feature_file_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.html`, and that a Chinese `.md` run summary with the same stem exists in the same directory; `branch_slug` comes from the current branch, and `/`, spaces, and special characters must be replaced with `_`; use `smoke` for smoke tests, and for runs involving multiple `.feature` files, preferentially use the suite name, otherwise use `multi-feature`. Here, the same stem refers only to the named HTML report; `results.md`, `result.md`, `junit.md`, or `index.md` must not be used as the final run summary. Even if `Final Full Rerun` is `failed`, `blocked`, or `skipped-with-risk`, the named report and summary from the latest relevant run must be retained.
- If Maestro executes and produces a native report, before the Phase 3.4 commit plan you must confirm that the report is located in `.maestro/reports/`, that its name follows `maestro-report-{flow_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.xml` or `maestro-report-{flow_name}-{branch_slug}-{YYYY_mm_dd}-{HH_MM_SS}.html`, and that a Chinese `.md` run summary with the same stem exists in the same directory. Even if the final flow fails, the named report and summary from the latest relevant run must be retained.
- If an API / integration or unit test runner produces JUnit, coverage, HTML, JSON, or equivalent reports that need to be retained as validation evidence for this cycle, before the Phase 3.4 commit plan you must confirm that they do not remain only in `coverage/`, `test-results/`, a fixed `junit.xml`, or a runner `current` directory that will be rebuilt by the next run; when retention is required, they must already have been copied / promoted to the project-designated directory or to branch-named and timestamped snapshots under `tests/api/reports/` or `tests/unit/reports/`, with a Chinese Markdown summary using the same stem. If an API / integration command without a native reporter is part of formal validation, at minimum preserve under `tests/api/reports/` an `api-report-*-{branch_slug}-*.txt` / `.json` raw report containing stdout, stderr, exit code, command, and timestamp, together with a Markdown summary using the same stem.
- If API / integration enters formal validation scope, before the Phase 3.4 commit plan you must confirm that the API Markdown summary contains a URI coverage matrix: each coverage-scope description must map to a specific `method + URI path`, test script / case, expected status code or side effect, and associated `.feature` / contract / schema. Coverage items whose URI cannot be determined must be marked `blocked` or `missing-uri`; do not treat a report containing only script names or domain-level summaries as complete.
- If an iOS physical-device Maestro run encounters known driver, transport, view hierarchy, tap crash, or version issues, first handle them according to the lazy-loaded lesson in `maestro-mobile-e2e`, then rerun the minimal failing flow.
- If `web-ui-autotest-generator` is enabled, before the Phase 3.4 commit plan you must confirm that script invocation follows the Web UI test asset path contract in global / project-level `AGENTS.md`, and that committable JSON assets are located in `tests/e2e/manifest/`: `ui-test-manifest.json`, `ui-selector-audit.json`, `ui-test-coverage.json`.
- During `$trellis-check`, you must verify that no `ui-test-manifest.json`, `ui-selector-audit.json`, or `ui-test-coverage.json` remains at the project root. If any remain, first migrate them to `tests/e2e/manifest/` and update references accordingly; if migration or confirmation is not possible, mark `Web UI test assets` as `blocked` and do not mark them as `generated`.
- If failure-analysis output `ui-test-repair-plan.json` is generated, its default path is `tests/e2e/manifest/ui-test-repair-plan.json`, and it must be handled as a runtime artifact according to the project's `.gitignore` policy; unless the user explicitly requests that it be organized into a formal task or report, do not commit the repair plan as a long-term test asset.
- API, Web E2E, Mobile E2E, or Hybrid E2E debugging cycles may accumulate multiple local formal report snapshots containing business names, branch names, and timestamps; do not delete existing named snapshots from the same task. Whenever a runner produces a native report that must be retained for this cycle, before the next command that may clear / overwrite the same runner output, you must generate a named report and a Chinese Markdown summary in the same directory with the same stem. Playwright's Markdown summary must follow the stem of `playwright-report-*.html`, not `results.json`, `junit.xml`, or the default `index.html`. The Markdown summary records the list of run cases / specs / flows, current branch, associated BDD `.feature` paths and scenario names, total number of rounds, failing cases / specs / flows in each round, failure reasons, fix actions, targeted reruns, affected-scope reruns, and the result of the final full rerun; API / integration summaries must additionally record a URI coverage matrix mapping coverage scope to `method + URI path`; status enum values, commands, file paths, case / spec / flow names, and original error text may remain in English.
- If an issue within the current task's scope is fixed after validation fails, first rerun the failing case / spec / flow, then run the affected subset, and finally run full validation within the planned scope. If fail-fast stops at the first failure, after fixing it you must continue executing the uncovered subsequent tests or rerun full validation within the planned scope.
- Before the Phase 3.4 commit plan, you must record the status and reason, as relevant, for Chrome DevTools MCP, Playwright MCP / CLI / Web Tests, Java, Maestro CLI / MCP / Mobile / Web Smoke, and Web UI automated testing assets.
- Before the Phase 3.4 commit plan, you must record the status of `Final Test Report`, `Run Summary MD`, `Targeted Rerun`, and `Final Full Rerun`; when PR / knowledge-base evidence is involved, also record `Evidence Source`, `Source Revision`, `Environment Alignment`, and `Evidence Publication`. If the final full run does not pass, do not execute `$trellis-finish-work`.
- Status values and tool responsibilities follow global / project-level `AGENTS.md` and the `project-validation` Skill; write testing-tool conclusions into the current task artifacts or check summary.

---

## Optional Channel Review Gate

After `$trellis-check` and project validation, but before the Phase 3.4 commit plan, if the user explicitly requests code review, test-validation review, parallel review, or cross-validation, or if the current task meets high-risk review / validation conditions, the `trellis-channel` Skill may be invoked for Channel preflight.

High-risk review / validation conditions include:

- GitNexus impact / detect_changes returns HIGH or CRITICAL
- Validation failed and was subsequently fixed, requiring independent verification of the failure cause and coverage scope
- Changes span frontend, backend, database, deployment, test assets, external services, or the release process
- PRD / design / implement and the actual diff, validation results, or rollback strategy require an independent consistency check
- Multiple acceptance criteria, browser states, E2E, API, Docker, Vercel, Playwright, Maestro, or Chrome DevTools MCP results require coverage review

Rules:

- Invoking the `trellis-channel` Skill for preflight does not mean starting the Channel runtime.
- Do not spawn a worker unless the user has explicitly requested Channel or explicitly confirms it after preflight.
- Channel review / validation does not replace `$trellis-check`, project validation commands, GitNexus, Playwright, Maestro, Chrome DevTools MCP, browser checks, or final human judgment.
- If Channel finds that code must be modified, after the main session applies the accepted changes, focused validation and any necessary `$trellis-check` must be rerun.
- Valid Channel conclusions must be written back into the current task artifacts; only long-term rules belong in `.trellis/spec` or `.trellis/lessons`.

---

## Complete the Task

Run:

```bash
$trellis-finish-work
```

Execute only after validation passes. Do not execute $trellis-finish-work in any of the following situations:

- $trellis-check was not executed
- Validation failed
- Task artifacts are inconsistent with the actual implementation
- Long-term rules in .trellis/spec were not satisfied

---

## Update Specifications

Use `$trellis-update-spec` only when the task changes any of the following:

- Architecture
- APIs
- Data models
- Permissions
- Business rules
- Long-term technical conventions
- Project rules that need to be reused across tasks

Do not use it for:

- One-off checklists
- Temporary research
- Local implementation notes
- Plans applicable only to the current task
- Unconfirmed design ideas

---

## Parent / Child Task

Use parent / child tasks when the work is too large, spans modules or phases, or cannot be independently validated as a single task.

The parent task records:

- Overall goal
- Scope
- Constraints
- Phase plan
- Final acceptance strategy

Each child task must:

- Be independently implementable
- Be independently testable
- Be independently checkable
- Have clear boundaries
- Have explicit acceptance criteria

Do not create child tasks that cannot be independently validated.

After a child task is completed, summarize it back into the parent task as needed.

---

## Prohibitions

This Skill retains only the minimum prohibitions related to the Trellis workflow; other constraints follow project-level `AGENTS.md`.

- Do not bypass `.trellis/workflow.md` or manually skip a Trellis phase.
- Do not begin implementation without executing `$trellis-before-dev`.
- Do not execute `$trellis-finish-work` without executing `$trellis-check` or when validation has not passed.
- Do not write one-off task plans, temporary research, or local implementation notes into `.trellis/spec`.
- Do not switch workflow templates merely because the task is complex, especially do not automatically switch to `channel-driven-subagent-dispatch`.