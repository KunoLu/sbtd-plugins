# Strict gates

Load this reference only for a confirmed `strict` task. It is not a prerequisite for ordinary default/lite work. Project-specific mandatory controls and explicit user acceptance remain applicable in every mode.

A required unavailable Skill, environment or evidence item is blocked, not passed. A genuinely inapplicable item is not-needed with its reason. Do not silently downgrade a strict task; changing mode requires a user decision and never waives data safety.

## Before development

1. Confirm task identity/root/branch, selected mode and explicit scope. Read the relevant project facts and task artifacts, not an entire historical archive. Resolve substantive ambiguity; state whether full `grill-with-docs` ran and why it did or did not. After a full grill, independently run `book-ddd-distilled-modeling` before requirements/design confirmation.
2. Stabilize applicable requirements, behavior specifications and design. Reuse the project's BDD location and language. User-visible new/changed behavior needs its applicable persistent scenarios before implementation; source/template repositories with an explicit no-.feature policy use their designated specification path instead. Do not invent contracts, fixtures, accounts or cross-repository facts.
3. Record a task-level Book Gate Plan with objective predicates, execution stage and real lifecycle state. The reviewer Skills own their result vocabulary and correction loops:

   | Reviewer | Trigger and timing |
   |---|---|
   | `book-ddd-distilled-modeling` | Every completed full grill; otherwise domain terms/rules or context ambiguity, before stabilizing requirements. |
   | `book-ddia-data-design` | Persisted/shared data, schemas, migrations, caches across requests/processes, async/cross-service flows, ownership or recovery; before design is stable. |
   | `book-legacy-change-safety` | Existing-behavior bug or weak/unclear/high-risk existing behavior; establish a safety net before changing behavior. |
   | `book-refactoring-pass` | Existing production-code edit; before implementation. A legacy safety-seam-only exception permits only the recorded behavior-preserving seam, then returns to legacy characterization and the normal gate. |
   | `book-release-readiness` | Production runtime/deployment, integration, service/job/queue or migration risk; after applicable testing-tool gates and project validation, before completion/release. |

4. Use TDD for task state, migration, data conversion and high-risk behavior at the agreed consumer interface. Keep tests deterministic and meaningful; a source-wording assertion or mock echo is not behavior proof. Record the actual red cause, then make the smallest correct change and confirm green.
5. Use `ponytail` and source/LSP/contract impact analysis as applicable. Optional graph output must be cross-checked; unsupported language, stale/empty output or a missing graph does not prove safety. No default install, cloud query or parent-root scan to satisfy a gate.

Advance only when applicable preconditions are genuinely met. A plan or reviewer label is not executed proof.

## Check

1. Compare the requirements, behavior scenarios, design, task record, project rules and actual diff. Resolve disagreements before claiming validation.
2. Exercise the changed path with a focused smoke and relevant tests. Match the real surface: terminal interaction for CLI/TUI, actual browser/device where relevant; report unavailable environments and use honest narrower evidence rather than a fake full-stack claim.
3. After the functional smoke, run `ponytail-review` for a nontrivial production diff. Decide each simplification against readability and safety; keep real seams and necessary validation. Apply only task-scoped fixes and rerun affected checks.
4. Perform Code Readability Review on modified handwritten code/tests. Do not edit vendor/generated code. If a broad refactor is needed, return to its gate rather than hiding it in cleanup.
5. Run `project-validation` using project-defined commands. Complete required BDD consistency and applicable Web/Mobile tool gates. Do not use an MCP exploration result as a CLI regression or CI pass.
6. Retain required named native/raw reports and same-stem Chinese summaries outside runner-managed current directories. Preserve failed runs. Bind evidence to the actual source ref/SHA, worktree, environment and publication state; a new commit invalidates older PR-head evidence until native rerun or sound revalidation. Native report-producing commands are the default when wrapper caching/side effects are unproven.
7. Obtain independent review when the task touches persistent migration, authorization/identity, global configuration, installation/uninstallation, cross-service contracts, broad public interfaces, or at least three established subsystems/hotspots. Native read-only review or independent human review is sufficient; it does not create a persistent coordination runtime. The writer owns integration and the validation controller remains unique.
8. Fix valid review/advisor findings, rerun affected checks, and review the resulting scope again. A prior clean review covers only its examined snapshot. Run `book-release-readiness` after the applicable validation sequence when triggered.

## Finish work

- Confirm all requested acceptance conditions and required checks. Report skipped/not-needed/blocked honestly; accepting a risk is not a required test pass.
- Update long-term specifications only for lasting rules, not transient task status. Record genuinely durable lessons using `lessons-record`; preserve identity ownership and historical content. Required missing artifacts remain incomplete.
- Update the task's real status, completion event/time, needed index links and any user-requested master ledger. A document contract, implementation, deployment, migration and release are distinct completion levels.
- Summarize files, commands/results, report locations, unresolved risks and rollback limits. Default/lite documentation shortcuts never justify leaving out a user-requested deliverable.
- Archive, push, deploy, workflow sync, destructive cleanup and backup disposal require their own applicable authorizations. Completion alone does not authorize them.
