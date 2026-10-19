# Method routing

Read only the branch relevant to the task. Mode controls method selection and artifact depth, not the truth of a result. Project rules and explicit deliverables remain binding. After any completed full `grill-with-docs`, the named post-grill DDD gate is mandatory in all modes; it has no missing-Skill substitute.

## Requirements and domain

- Use `grill-with-docs` for unresolved project/domain questions after reading facts, or when explicitly requested; `grilling` and `domain-modeling` support the interview. State whether the complete method actually ran. Mere reading/evidence-first thinking is not full invocation.
- Use `grill-me`/`grilling` for a requested general plan challenge. Do not turn every clear request into an interview.
- Use `book-ddd-distilled-modeling` after every full grill-with-docs and when the domain review is selected/required. The post-grill pass is separate, visible and governed by that Skill's result/correction loop; unavailable/unreadable/insufficient evidence blocks dependent confirmation/design in every mode.
- Use `domain-modeling` for durable vocabulary/context/ADR needs; existing project paths win, otherwise `docs/CONTEXT.md` and `docs/adr/`, or per-context subdirectories. Temporary task plans do not become permanent domain rules.
- Use `to-spec` for a requested durable requirement specification and `to-tickets` for requested implementation slices. Put task artifacts under the chosen SBTD task record when appropriate; do not publish to an issue tracker without authorization. Do not route these methods back to a retired runtime or create a compatibility alias.

## Implementation and safety

- `codebase-design` is for real module/interface/seam questions, not a reason to add ports or wrappers to a simple task.
- `diagnosing-bugs` is for uncertain failure causes; establish observed behavior before choosing a fix. Distinguish code, tests, fixtures and environment with evidence.
- `tdd` applies when selected/required for behavior, state, data conversion or high-risk changes. Agree the real consumer seam, establish a meaningful red, implement the smallest correct slice, then green. Test observable contracts rather than forwarding or mock echoes.
- `ponytail` selects the simplest correct solution after scope/design/gates are settled. `ponytail-review` follows a proven smoke for nontrivial production changes; adjudicate against readability, not line count. `ponytail-audit` is only for an explicitly requested whole-repo audit; `ponytail-debt` for touched/requested markers. These do not expand ordinary scope.
- Keep one coherent responsibility, meaningful names and clear guard clauses. Preserve real seams; avoid shallow wrappers, speculative abstraction and clever dense expressions. Comments explain constraints/reasons rather than repeating code. Review handwritten code/tests before final validation; do not edit vendor/generated code.
- The five Book reviewers keep their own result schemas and correction loops. Strict's objective triggers/order are in [strict.md](strict.md). Default/lite select methods by actual risk and explicit requirements; when a method is invoked, never fake its result or bypass essential data safety. A missing necessary fact still blocks its dependent action.

## Behavior and evidence

- Use `gherkin-bdd` for the applicable user-visible behavior specification. Preserve existing project conventions and explicit scenario requirements. Strict keeps its full applicable no-new-uncovered-behavior gate; default/lite use necessary methods without mechanically creating every artifact. Source/template repositories may explicitly forbid .feature files; do not export that exception to business projects.
- Default new scenario prose is Chinese with English Gherkin keywords unless project convention/user choice differs. Describe observable behavior, not selectors, fixture plumbing or implementation details. Unautomatable required scenarios retain the reason and manual proof plan; do not claim they ran.
- BDD sync is a requested behavior synchronization, not workflow/config sync. Explicit read-only ingest fixes source refs/SHAs and does not mutate the source or switch its active branch. `knowledge-base-integration` owns product registry, Revision Set, Evidence Decision, runner and integrity behavior; do not invent missing cross-repository facts or promote mock/smoke to full-stack.
- Use `project-validation` to select and run real project commands and formal evidence rules. Testing/diagnostics tool roles are in [tooling.md](tooling.md). Once formal validation is in scope, mode does not waive native reports, same-stem Chinese summaries, SHA/worktree/environment bindings, privacy or rerun closure.
- Use `maestro-mobile-e2e` for requested/needed Mobile/Hybrid flows and their native reports; use `web-ui-autotest-generator` only for durable Web test assets/coverage. Lack of a stable app, contract, environment, data or locator is a fact to resolve, not permission to invent fixtures.

## UI and public surfaces

- `ui-ux-pro-max` establishes the first UI direction against the project's users, stack, design system and accessibility needs. `impeccable` may then shape/critique/polish; do not initialize context, force a visual rewrite or bypass confirmation without need. Context normally lives at `docs/PRODUCT.md` and `docs/DESIGN.md`, with one canonical location; sidecar `.impeccable/design.json` remains at the project root.
- `shadcn` applies when the project has components.json, already uses/initializes shadcn/ui, or explicitly needs its registry/preset/component behavior. Inspect actual runner/config/components, do not invent a third-party registry. Update config incrementally.
- React Bits is not default onboarding scope. React + shadcn and explicit need precede tier/registry confirmation; paid use needs the chosen registry, entitlement/key and project-local Skill. Preserve an existing tier at reset; never print/copy a license key or overwrite unrelated components.json settings. Project Skill placement is `.agents/skills/react-bits-pro/`, not an accidental root SKILL.md. Onboard owns the install command and overwrite rules.
- `seo-geo` applies to requested search visibility or appropriate public-release scope, not every internal UI/API/test. Without a public/preview surface, report static-only or blocked; external paid-data credentials are optional and never enter artifacts.

## Records and authoring

- `lessons-record` captures genuinely durable fixes, rollback/tool/workflow failures and lost context. Resolve authorized identity first; never guess it or rewrite old IDs/other authors' blocks. Use the existing layered lesson entry/index/topic structure, not a growing task log.
- `handoff` can assist real cross-session handover, but [handoff.md](handoff.md) owns SBTD event triggers, opt-outs, identity/mode precedence and read-only behavior. Counters used for output compression are not handoff triggers.
- Use `writing-for-agents` for rule/Skill documents. Keep trigger pointers explicit and the common entry small; branch-specific detail belongs in references. Preserve upstream external Skill payloads and licenses; caller routing controls when to invoke them, not a fork of the stable mirror.
