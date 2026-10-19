<div align="center">

# SBTD Workflow

**Reusable agent rules, skills and onboarding for evidence-driven development.**

[![Bundled skills](https://img.shields.io/badge/bundled_skills-14-7c3aed?style=flat-square)](#skills) [![External skills](https://img.shields.io/badge/external_skills-19-0d9488?style=flat-square)](#external-skills) [![License](https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square)](LICENSE)

**English** · [简体中文](README.zh.md)

[Install](#install) · [Usage & prompts](#usage) · [Workflow](#workflow) · [Skills](#skills) · [Reference](#reference)

</div>

SBTD connects **specifications, behavior, tests and domain language**. Your coding agent does the work; the workflow makes scope, permissions and verification explicit.

This repository is a **configuration and Skill source**, not a business application. The main workflow targets **Codex and Oh My Pi (OMP)**; the installers also expose Claude Code and Kimi adapters. Adapter availability is not proof of identical host behavior.

> **Stable [v2.0.1](https://github.com/KunoLu/640-skills/releases/tag/v2.0.1) is released.** The catalog contains 14 bundled and 19 required external Skills. See the [English CHANGELOG](CHANGELOG.md) and [Chinese counterpart](CHANGELOG.zh.md) for the same release history. Code, CI, installation, native checks and actual host acceptance remain separate evidence layers; publishing a tag does not upgrade your environment. See the [delivery plan and acceptance boundaries](docs/prd/sbtd-workflow-v2-trellis-removal-graft-migration-prd.md).

| [New installation](#install) | [Already installed](#onboard-prompts) | [Start a task](#task-prompts) |
|---|---|---|
| Bootstrap Onboard, then review setup | Check, upgrade or initialize another project | Choose a mode and copy a task prompt |

<a id="install"></a>
## Install: start with your agent

### 1. Install the Onboard Skill only

Paste this into your coding agent; replace the target agent if needed:

```text
Install only sbtd-workflow-onboard from the KunoLu/640-skills v2.0.1 tag
into my user-level global Skills directory for Codex, not this project.
First resolve that revision and verify it exists; do not silently substitute main or a v1 package.
Use the official skills CLI and copy the full directory. Show the resolved source and target.
Do not run init/reset, install other tools, or change AGENTS/MCP configuration yet.
```

Prefer the terminal? With Node/npm available, use the [official Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx --yes skills@latest add https://github.com/KunoLu/640-skills \
  --skill sbtd-workflow-onboard --global --agent codex --yes --copy
npx skills list --global --agent codex
```

`skills@latest` selects the CLI version, **not a Skill release**. An unpinned repository source reads the default branch, not the latest tag. Pinning syntax is `'KunoLu/640-skills#<reviewed-ref>@sbtd-workflow-onboard'`: replace `<reviewed-ref>` with an existing v2 tag or reviewed commit, and follow that revision's documentation. **Do not combine a historical v1 package with the v2 setup prompts below**: its initialization may install or invoke the retired Trellis/GitNexus workflow. For v1 data, use the migration prompt below instead of init/reset.

**Bootstrap is not setup.** It copies the self-contained Onboard package; it does not execute `onboard.py`, install the remaining Skills or Python dependencies, configure MCP, or initialize projects. Find the actual installed directory rather than assuming a HOME path. For OMP or another host, confirm its supported Skills CLI agent identifier and discovery path instead of assuming Onboard's platform name is the same identifier.

### 2. Review and initialize selected projects

```text
Use sbtd-workflow-onboard to initialize /abs/project-one,/abs/project-two.
Target platform: codex. These are the existing absolute project roots I want initialized;
install project AGENTS.md in both. First check the installed package's Python dependencies
and show plan --json, including global Skills, global AGENTS and host/MCP targets.
Ask before installing missing prerequisites or applying the plan. After I approve,
run init and report each project's writes, backups, skipped checks and remaining actions.
```

Use `omp` instead of `codex` for OMP setup. Multiple project roots are separated by English commas. A normal setup installs the **14 bundled + 19 required external Skills globally**; optional tools retain their own confirmation gates.

Onboard needs **Python 3.10+** and its declared dependencies for contract/state/migration validation. After reviewing and authorizing dependency installation, run this with the interpreter that will execute the installed copy:

```bash
python -m pip install -r /path/to/installed/sbtd-workflow-onboard/requirements.txt
```

> **Check the write scope.** Normal `init`/`reset` writes global Codex rules by default, and also backs up and overwrites `~/.omp/agent/AGENTS.md` when `~/.omp` already exists. Selecting a platform does not select the global AGENTS destination. `--global-agents-path` changes only the Codex target. Use project-only mode when global writes are not wanted.

[Bootstrap guide](sbtd-workflow-onboard/REFERENCE.md#official-skills-cli-bootstrap) · [Setup contract](sbtd-workflow-onboard/REFERENCE.md#two-execution-modes) · [Path resolution](sbtd-workflow-onboard/REFERENCE.md#paths)

<a id="usage"></a>
## Usage: copy a prompt for your goal

These are **natural-language requests to your agent**, not new CLI commands. Replace bracketed inputs and `/abs/...` paths. The agent should read local facts first and ask only for missing choices or required authorization.

<a id="onboard-prompts"></a>
### Manage an installation

| Goal | Choose | What it means |
|---|---|---|
| Inspect without installing | `check` / `plan` | Read-only inventory and proposed work; not proof that setup ran |
| First full setup | `init` | Install missing/invalid Skills; preserve valid Skill shells, not necessarily current content |
| Add a project only | `init-projects` | Project AGENTS/ignore and applicable local assets; no global installation or user MCP/hooks |
| Align an existing environment | `upgrade` | Fixed-baseline plan/apply/verify, explicit drift decisions, backups and recovery |
| Deliberately reinstall | `reset` | Overwrite bundled Skills **without backup**, reinstall required externals; not an upgrade recovery protocol |
| Move legacy data | `migration` | Approved projections, retained originals and verified receipts; separate deployment authorization; interrupted deployment evidence is reconciled from current state, never backfilled |
| Retire detected legacy assets | `cleanup-legacy` | Display actual candidates, then obtain separate execution consent |
| Restore an authorized batch | `recovery` | Plan and confirm restoration from trusted batch evidence; not a general undo command |

The [first-time initialization prompt](#install) covers a new v2 installation after bootstrap. Use the following prompts for an existing installation or a v1 project; substitute the exact reviewed v2 source, project roots and configuration domains before execution.

<details>
<summary><strong>Run v2 init again — not a version upgrade</strong></summary>

```text
Use the reviewed v2 sbtd-workflow-onboard package to plan init for platform codex
and the existing project /abs/project. I want project AGENTS.md installed.
Inspect the installed package revision and interpreter dependencies first.
Show plan --json, exact global Skills/AGENTS/MCP targets and project writes/backups;
wait for my approval before init. Preserve tasks, identity, lessons and legacy data.
Explain which valid Skill shells init will skip; do not claim their contents were upgraded.
If version alignment is needed, stop and propose an explicit upgrade plan instead.
Do not reset, migrate, remove legacy assets or enable hooks under this request.
```

</details>

<details>
<summary><strong>Inspection and project-only setup prompts</strong></summary>

**Inspect the existing environment:**

```text
Use sbtd-workflow-onboard to check my codex environment and /abs/project.
This is read-only: report installed Skills, resolved paths, project conflicts,
and missing prerequisites. Do not install, reset, migrate, clean up or change configuration.
```

**Add a project without changing global configuration:**

```text
Use sbtd-workflow-onboard in init-projects mode for /abs/project, platform omp.
Install project AGENTS.md. First run project-only preflight and show the local write scope;
wait for approval before writing. Do not install or modify global tools, Skills,
AGENTS, MCP or hooks. Report whether the local Graft graph was built or unavailable.
```

</details>

<details>
<summary><strong>Upgrade and reset prompts — different operations</strong></summary>

**Recommended for an existing environment: explicit upgrade.**

```text
Use sbtd-workflow-onboard to plan an upgrade to the reviewed Onboard package baseline.
First confirm the exact global Skills root, global AGENTS targets, codex/omp configuration
homes, any shell profiles, and an existing private backup vault. Inventory only that scope.
Show upgrade --phase plan and all replace/preserve decisions for custom content; wait for
approval before apply. Then verify disk content separately from protocol and real host loading.
Ask separately before host probes. Do not clean up old assets or sync other environments.
```

An isolated probe still rejects linked Skills by default. To retain a link, explicitly approve its physical target with `upgrade --phase authorize-link`, then pass the resulting document to `verify --probe --yes --link-authorization`. This grants only exact local target access and a temporary plain-directory projection; it does not replace the original link, follow nested links or prove a live session reload. See the [authorization commands and refusal boundaries](sbtd-workflow-onboard/REFERENCE.md#probe-skill-link-authorization).

**Apply only the plan you have reviewed and approved:**

```text
I approve the exact upgrade scope and replace/preserve decisions already shown in
[upgrade-plan file]. Use the matching trusted v2 Onboard executor and recheck the source,
targets and private vault. Read plan_id from that file and run upgrade --phase apply
with the required confirmation; do not ask me to transcribe hashes.
Save the actual receipt and backups. If scope or state has changed, stop rather than silently
replanning under this approval. On partial failure, report measured writes and the retry path.
Do not probe hosts, migrate projects, clean up or sync other environments.
```

**Verify the applied upgrade without starting host probes:**

```text
Use upgrade --phase verify with [the approved plan] and [its actual upgrade receipt].
Verify the installed package and selected resources against that exact baseline.
Report disk, runtime/protocol, host loading and legacy cleanup separately; mark unexecuted
layers unverified. Do not add --probe or --yes, repair configuration, or delete backups.
```

**Optional host and linked-Skill verification — approve the scope first:**

```text
Show the exact host probes proposed for [upgrade plan and receipt], including configuration
domains, subprocesses, temporary projections and potential side effects. These upgrade probes
need no real authentication or model request; do not read or copy credential files.
Wait for my explicit probe approval.
For a linked Skill, show its logical path, physical target, identity and content boundary.
Only after I approve that target, use upgrade --phase authorize-link and preserve its output.
Then run upgrade --phase verify --probe --yes with that authorization where required.
Keep the original link and unrelated configuration; report isolated host loading separately
from any live session reload. Unproven isolation is blocked, not bypassed; real model/behavior
smoke requires its own scope and controlled authentication, outside this upgrade probe.
```

**Plan recovery of this upgrade, not a migration rollback:**

```text
Use recovery --phase plan with --upgrade-plan [plan] and --upgrade-receipt [receipt].
Confirm the private vault is trusted, inspect current drift and show the exact restoration
scope and limits. Save the recovery plan only to the approved private location.
Wait for separate recovery approval before recovery --phase apply; use the actual
--upgrade-recovery-plan and read its recovery_id for --confirm-recovery.
Preserve user changes, backups and partial receipts; do not execute untrusted historical code.
```

These prompts map to the [implemented upgrade and recovery commands](sbtd-workflow-onboard/REFERENCE.md#upgrade-alignment). A successful `verify` does not grant cleanup permission; an old plan does not authorize a newly changed package or target set.

**Use reset only when you intend to replace Skill content:**

```text
Use the reviewed v2 sbtd-workflow-onboard package to plan reset for platform codex
and /abs/project. I want project AGENTS.md rewritten, subject to the displayed plan.
Verify the package revision and interpreter dependencies. Explain that bundled Skills
will be overwritten without backup and required external Skills reinstalled.
Identify custom Skill content; if I need it preserved, stop for a separately approved backup
or propose upgrade instead. Show all global/project targets, AGENTS backups and MCP impact;
preserve detected React Bits tier/registry. Wait for approval before reset.
Preserve tasks, developer identity, specs, lessons, handoffs and legacy data.
Reset is not migration, cleanup, a full-machine upgrade, or an automatic rollback guarantee.
```

</details>

<details>
<summary><strong>Legacy migration, cleanup and recovery prompts</strong></summary>

**Migrate an SBTD v1 project to v2 — package upgrade and data migration are separate:**

```text
I use SBTD v1 in /abs/project and want to move to [reviewed v2 tag or commit]
for [codex and/or omp, with the exact selected configuration domains].
Start read-only: identify the installed Onboard version, old Trellis/GitNexus layout,
project branch, custom rules, tasks/specs/lessons, shared HOME/Skills users and active processes.
Do not run v1 init/reset, copy credentials, create directories or modify configuration yet.
Separate the plan for upgrading the Onboard/Skills package from the project-data migration.
If the old executor lacks the v2 upgrade entry point, show how to prepare the reviewed v2
executor and preserve the existing installation; request that installation approval separately.
Agree an external private vault, custodian, retained originals, publication decisions,
approved candidates and recovery limits. Show the real migration plan before requesting apply.
After authorized apply, request deployment approval separately; consume the bound
manifest/receipts for new rules/Skills/wiring, then verify data, host behavior and recovery evidence.
Only after verification, display batch and fresh cleanup candidates and request deletion
approval separately. Keep unknown content and backups; do not promise writable Trellis rollback.
Stop at each unapproved phase. Do not use reset as a substitute for upgrade or migration.
```

**Request cleanup planning, not immediate deletion:**

```text
sbtd cleanup for /abs/project. Show verified batch candidates if available and run a fresh
cleanup-legacy plan. List every target and disclose shared global MCP impact before asking
for execution consent. Preserve unknown content, CLI packages, global data and backups.
```

**Recover a specific batch:**

```text
Use sbtd-workflow-onboard recovery for [the explicitly selected migration or upgrade batch].
Verify the trusted private vault and bound receipts. Show recovery --phase plan,
current drift, exact restoration scope and what cannot be restored. Wait for my approval
before apply; retain backups and report partial results honestly.
```

**Reconcile interrupted deployment evidence:**

```text
Use sbtd-workflow-onboard migration --phase reconcile for [the batch whose apply completed
but whose cumulative deployment evidence was never saved]. Bind the exact manifest and
complete apply receipt, prove the historical evidence path genuinely absent, and freshly
observe current state into one new typed evidence document at a new private path.
Do not forge the missing receipt or claim the original deployment ran to completion;
I confirm --yes explicitly and run the standard verify afterwards.
```

The migration planner accepts characterized Trellis **0.6.15 / 0.6.17 data layouts**, not arbitrary old versions. Hash claims on user content are not deletion authority; missing approvals, contradictory task relationships and unknown host configuration still block. A genuinely host-free project can retain an empty platform list without inventing host files. Vendor-uninstall runtime support remains separately pinned.

Stale recorded template hashes may be reconciled only against the installed package's reviewed **exact path/version/content pins**; migration neither refreshes the old hash file nor fetches templates at runtime. Mixed project `AGENTS.md` content is not generated-file ownership: replacing it still requires the existing signed approval, bound to the actual before-state and exact candidate. Recognition is not authorization to apply or clean up.
Migration deployment retains the approved project-rule body, removing only the maintenance pause and adding the managed Graft fence; it does not silently swap that body for the generic template.
OMP deployment also recognizes configuration-input changes already proved by bound successful migration receipts and intact originals. Unrecorded drift still blocks; this does not waive runtime-version checks or authorize a deployment retry.

An interrupted deployment whose evidence was never saved is reconciled from **current state**, not backfilled: `migration --phase reconcile` requires the complete successful apply receipt, a genuinely absent historical evidence path, a new non-overwriting output path and explicit `--yes`. It revalidates the signed runtime lineage, retained originals and sealed resources, then writes one new evidence document explicitly typed `kind: current-state` / `historical_execution: unknown` — each result pairs a before-state proven by the retained original with a freshly measured after-state, and no historical exit code, success claim or timestamp is invented. Acceptance means the current postconditions hold, not that the original process exited cleanly or wrote new targets; the subsequent standard `verify` reports `acceptance_basis: current-state`. This authorizes no install, deployment retry or cleanup, and the regular deploy/retry/recovery gates are unchanged.

Consumers recheck that the cited manifest/apply objects are safe files with the recorded digests. The observer must match the manifest runtime or its exact signature-approved successor; reverse or unrelated lineage is rejected. Historical observers need not match the current consumer, and cumulative retries never rewrite their provenance. This does not authenticate historical execution or authorize refreshing old evidence.

New cross-runtime observations retain the verified signed authorization in `observer_lineage`, so later pair-file rotation does not erase historical observer authority. Consumers verify it with the installed trusted key, never a key supplied by the evidence. Legacy records without this proof still require the matching current pair (unless observer and manifest runtimes match); lost authority is not invented. Accepted plans and evidence recheck direct and followup-ancestor provenance at output; cleanup and recovery also recheck before writes. Post-write refusals preserve measured results without claiming successful acceptance.

Current-state acceptance completes semantic/lineage validation before its final snapshot-only pass over observed artifacts and pinned inputs. That pass includes absent resources; it is not an atomic cross-process snapshot and does not promise objects can never change afterward.

Already aligned project rules can remain untouched under exact-template evidence. Document-only legacy task folders are archived as documents, not fabricated tasks; historical task branches remain historical, with explicit deferred recovery instead of an automatic checkout or rebinding.

Ordinary RC upgrades use content comparison and native upgrade receipts, not a new local lineage signature on every release. To retire an already verified original migration after one Onboard replacement, cleanup can consume paired `--upgrade-plan` / `--upgrade-receipt` and the intact old package backup. This is cleanup-only: it verifies existing historical signatures without executing old code and does not authorize followup or migration recovery. Proven unrelated deployment-discovery file/absent drift may be left untouched; target, retained-asset, profile, tool, footprint and provenance drift still block. See the [cleanup contract](sbtd-workflow-onboard/REFERENCE.md#cleanup-runtime).

[Upgrade & recovery](sbtd-workflow-onboard/REFERENCE.md#upgrade-alignment) · [Migration](sbtd-workflow-onboard/REFERENCE.md#migration-runtime) · [Cleanup](sbtd-workflow-onboard/REFERENCE.md#cleanup-runtime)

</details>

<a id="task-prompts"></a>
### Use SBTD in daily development

**Start here for ordinary work:**

```text
Use sbtd-task in default mode for [goal] in this repository.
Read the project rules and relevant lessons, inspect the existing implementation,
make the smallest correct change, and exercise the changed path.
Report changed files, actual verification, skipped checks and remaining risks.
Do not install tools, migrate data, deploy or sync configuration without separate authorization.
```

| Situation | Recommended prompt |
|---|---|
| Small, bounded change | “Use sbtd-task in **lite** mode for [change]. Keep a shared short task card, acceptance checklist and focused verification; preserve all project safety requirements.” |
| High-risk or audited delivery | “Use sbtd-task in **strict** mode for [goal]. Create a new branch, record requirements and acceptance, produce the Book Gate Plan, complete applicable gates and independent review, then report evidence.” |
| Unclear requirements | “Use **grill-with-docs** for [idea]. Read repository facts first, clarify decisions and record domain language. After the full interview, run **book-ddd-distilled-modeling** and show the independent DDD Boundary Review before design or implementation.” |
| Reproducible bug | “Use **diagnosing-bugs** for [observed failure]. Establish a failing feedback loop, identify the cause, then use **tdd** for a regression test where appropriate. Verify the preserved behavior as well as the fix.” |
| UI and regression | “For [page/flow], use **ui-ux-pro-max**, **shadcn** if the project uses it, and **impeccable** for visual review. Use **gherkin-bdd** and **project-validation**; persist Playwright assets with **web-ui-autotest-generator** only if maintainable inputs are available.” |
| Mobile / Hybrid | “Use **maestro-mobile-e2e** for [journey] on [iOS/Android]. Confirm the BDD source, app, device, backend, accounts and selectors before creating flows. Run the applicable Maestro validation and retain native reports plus Chinese summaries.” |
| Simplicity review | “Use **ponytail-review** on this diff. Propose deletions and simpler native solutions without weakening correctness, readability or safety.” Use **ponytail-audit** for a whole-repository audit, **ponytail-debt** for existing deferral markers. |
| Resume or hand off | “Continue SBTD task [task ID]. Check its root, branch and effective mode; preserve that mode and ask if candidates conflict.” / “Prepare an **sbtd-task** handoff for [task ID], preserving completed work, evidence, next action and limitations.” |
| Read behavior into a knowledge base | “Use **knowledge-base-integration** to read [configured product/repositories] at [target ref]. Resolve exact SHAs, produce the behavior catalog, and report missing mappings. **Mutation: none**; do not rewrite `.feature` or publish evidence.” |

Want tracker deliverables? Explicitly request **to-spec** or **to-tickets**, identify the tracker and authorize publication. These are not substitutes for local task state, and their tracker setup is not automatically supplied by Onboard.

Want a different reply style? `adhd mode` opts into **i-have-adhd**; `/caveman lite` requests compact replies when Caveman is available. `normal mode` exits both. **Reply style never changes default/lite/strict execution requirements.**

<a id="workflow"></a>
## How the workflow fits together

SBTD is this repository's combination of four practices, not a new runtime or framework:

| Practice | Question it answers | Typical artifact or method |
|---|---|---|
| **SDD** — Specification-Driven Development | What are we building, and why? | Requirements, PRD/design, acceptance criteria |
| **BDD** — Behavior-Driven Development | What can a user observe? | Project-owned Gherkin scenarios and traceable tests |
| **TDD** — Test-Driven Development | How do we prove a change at the right boundary? | Red–green–refactor at agreed test seams |
| **DDD** — Domain-Driven Design | Which terms, rules and boundaries must agree? | Glossary, context/ADR decisions, independent boundary review |

```text
Read project facts and lessons → resolve task, branch, scope and mode
  → clarify requirements / domain language as needed
  → full grill-with-docs? Independent DDD Boundary Review must be confirmed
  → specify observable behavior → design and applicable pre-development gates
  → implement with risk-appropriate TDD → smoke and readability review
  → project-native validation + applicable Web / Mobile / evidence checks
  → release-readiness review when triggered → record actual completion
```

### Choose an execution mode

| Mode | Use it for | Working contract |
|---|---|---|
| `default` | Ordinary tasks | On-demand investigation, implementation and focused validation; only needed local records |
| `lite` | Bounded tasks needing a shared trail | Short checklist and shared task card, not a mandatory full document pack |
| `strict` | Explicitly rigorous delivery | Applicable before-dev/check/finish obligations, Book Gate Plan and required evidence |

Mode precedence is **your current explicit choice → the same task's valid record → default for a genuinely new task**. A suggested change waits for your decision; continuing a task does not reset its mode. All modes preserve explicit deliverables, project rules and safety. Every completed full `grill-with-docs` requires the independent DDD review in **all three modes**.

Strict gates are triggered by facts: domain ambiguity, persistent/shared data, uncertain legacy behavior, existing production-code edits, or production runtime/deployment changes. Not every gate runs on every task; a required but unavailable gate is **blocked**, not passed. [Strict contract](sbtd-workflow-onboard/templates/skills/sbtd-task/references/strict.md) · [Method routing](sbtd-workflow-onboard/templates/skills/sbtd-task/references/methods.md) · [Workflow paths](docs/assets/sbtd-workflow-paths.md)

### State without a second source of truth

- `task.md` owns mode, status and events. Ordinary default tasks use `.sbtd/tasks/<id>/`; lite/strict or explicitly shared tasks use `ai/tasks/<id>/`. `.sbtd/active-task.json` is only a bookmark.
- `cancelled` is a terminal cancellation, **not successful completion**: `completed_at` stays null. Cancellation never cascades to children; archive and explicit reopen preserve its history. Imported `blocked` records with an unknown prior phase require an explicit recovery choice. Update the task runtime, schema and Skill references together before using these records with older installations.
- Handoffs live under protected `docs/handoffs/` on a real pause/switch or explicit request; they never override the task. Pure Q&A/read-only work creates no task, identity or handoff files.
- Developer identity is needed for a durable lesson write, not ordinary work. A valid local `.sbtd/developer` wins; only genuine absence in a verified linked worktree allows reading the main checkout's identity. Never guess names or replace a malformed identity.

[Task state](sbtd-workflow-onboard/templates/skills/sbtd-task/references/state.md) · [Handoffs](sbtd-workflow-onboard/templates/skills/sbtd-task/references/handoff.md) · [Lessons](sbtd-workflow-onboard/templates/skills/lessons-record/SKILL.md)

<a id="skills"></a>
## Skill catalog

**Installed together, used when relevant.** Normal Onboard `init`/`reset` targets global Skills. Bootstrap alone and project-only initialization do not install or activate the complete global workflow. The [catalog](sbtd-workflow-onboard/catalog.json) owns membership; click a Skill for its full instructions and references.

### 14 bundled Skills

| Skill | Job / when to use it |
|---|---|
| [sbtd-workflow-onboard](sbtd-workflow-onboard/SKILL.md) | Check, install, initialize, upgrade, migrate and recover explicitly selected environments |
| [sbtd-task](sbtd-workflow-onboard/templates/skills/sbtd-task/SKILL.md) | Route work through default/lite/strict; manage task state and continuation |
| [gherkin-bdd](sbtd-workflow-onboard/templates/skills/gherkin-bdd/SKILL.md) | Author observable behavior; distinguish writable BDD sync from read-only ingest |
| [project-validation](sbtd-workflow-onboard/templates/skills/project-validation/SKILL.md) | Select native checks, applicable testing tools and truthful evidence/report status |
| [web-ui-autotest-generator](sbtd-workflow-onboard/templates/skills/web-ui-autotest-generator/SKILL.md) | Generate/audit maintainable Playwright assets and selector/coverage manifests |
| [maestro-mobile-e2e](sbtd-workflow-onboard/templates/skills/maestro-mobile-e2e/SKILL.md) | Derive Mobile/Hybrid Maestro flows from BDD and verify real device prerequisites |
| [knowledge-base-integration](sbtd-workflow-onboard/templates/skills/knowledge-base-integration/SKILL.md) | Product registry, Evidence Policy, Revision Sets, read-only ingest and staged smoke |
| [lessons-record](sbtd-workflow-onboard/templates/skills/lessons-record/SKILL.md) | Record durable lessons with validated author identity and topic/index ownership |
| [book-ddd-distilled-modeling](sbtd-workflow-onboard/templates/skills/book-ddd-distilled-modeling/SKILL.md) | Review domain language and boundaries; mandatory after every full grill-with-docs |
| [book-ddia-data-design](sbtd-workflow-onboard/templates/skills/book-ddia-data-design/SKILL.md) | Review data ownership, consistency, schema, cache, migration and recovery design |
| [book-legacy-change-safety](sbtd-workflow-onboard/templates/skills/book-legacy-change-safety/SKILL.md) | Characterize existing behavior and establish a safety net before risky changes |
| [book-refactoring-pass](sbtd-workflow-onboard/templates/skills/book-refactoring-pass/SKILL.md) | Review the smallest safe structure change before production-code edits |
| [book-release-readiness](sbtd-workflow-onboard/templates/skills/book-release-readiness/SKILL.md) | Review operational risk and rollback after required validation |
| [seo-geo](sbtd-workflow-onboard/templates/skills/seo-geo/SKILL.md) | Audit search/AI visibility for public web surfaces, not internal apps or API regression |

<a id="external-skills"></a>
### 19 required external Skills

These are reviewed **upstream mirrors**, not local forks. `auto` and `stable` install from the bundled snapshot without fetching upstream; only an explicit `upstream` selection opts into current upstream evaluation. Exact revisions, checksums and licenses live in the [stable manifest](sbtd-workflow-onboard/assets/external-skills/stable/MANIFEST.json).

| Area | Skills | Purpose |
|---|---|---|
| Clarification | [grilling](sbtd-workflow-onboard/assets/external-skills/stable/skills/grilling/SKILL.md), [grill-me](sbtd-workflow-onboard/assets/external-skills/stable/skills/grill-me/SKILL.md), [grill-with-docs](sbtd-workflow-onboard/assets/external-skills/stable/skills/grill-with-docs/SKILL.md) | Stress-test decisions; use the documented variant for domain records |
| Specifications | [to-spec](sbtd-workflow-onboard/assets/external-skills/stable/skills/to-spec/SKILL.md), [to-tickets](sbtd-workflow-onboard/assets/external-skills/stable/skills/to-tickets/SKILL.md) | Turn agreed discussions into tracker specs and dependency-aware work slices |
| Design | [domain-modeling](sbtd-workflow-onboard/assets/external-skills/stable/skills/domain-modeling/SKILL.md), [codebase-design](sbtd-workflow-onboard/assets/external-skills/stable/skills/codebase-design/SKILL.md) | Shared language, context decisions, module interfaces and test seams |
| Debug & test | [diagnosing-bugs](sbtd-workflow-onboard/assets/external-skills/stable/skills/diagnosing-bugs/SKILL.md), [tdd](sbtd-workflow-onboard/assets/external-skills/stable/skills/tdd/SKILL.md) | Evidence-first diagnosis and red–green feedback loops |
| UI | [ui-ux-pro-max](sbtd-workflow-onboard/assets/external-skills/stable/skills/ui-ux-pro-max/SKILL.md), [impeccable](sbtd-workflow-onboard/assets/external-skills/stable/skills/impeccable/SKILL.md), [shadcn](sbtd-workflow-onboard/assets/external-skills/stable/skills/shadcn/SKILL.md) | UX/design systems, visual refinement and shadcn/ui-specific implementation |
| Simplicity | [ponytail](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail/SKILL.md), [ponytail-review](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail-review/SKILL.md), [ponytail-audit](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail-audit/SKILL.md), [ponytail-debt](sbtd-workflow-onboard/assets/external-skills/stable/skills/ponytail-debt/SKILL.md) | Minimal implementation, diff review, whole-repo audit and deferral ledger |
| Agent collaboration | [handoff](sbtd-workflow-onboard/assets/external-skills/stable/skills/handoff/SKILL.md), [writing-for-agents](sbtd-workflow-onboard/assets/external-skills/stable/skills/writing-for-agents/SKILL.md) | General handoff prose and agent-facing documentation; SBTD state remains owned by sbtd-task |
| Reply structure | [i-have-adhd](sbtd-workflow-onboard/assets/external-skills/stable/skills/i-have-adhd/SKILL.md) | Opt-in, session-level, action-first replies; installation does not activate it |

Onboard uses the **Ponytail skill-only provider**. An enabled official Ponytail plugin is a conflict, not permission to disable it; plugin management and `ponytail-gain`/`ponytail-help` are outside Onboard. [Provider boundary](sbtd-workflow-onboard/REFERENCE.md#ponytail-provider-boundary)

<a id="verification"></a>
## Tools and verification boundaries

| Tool / layer | Owns | Does not prove |
|---|---|---|
| Graft | Pinned, scoped structural analysis and impact assistance | Compiler semantics, business correctness or automatic host readiness |
| Chrome DevTools MCP | Browser runtime, console/network/performance diagnosis | Repeatable CI regression |
| Playwright MCP | Page exploration and locator assistance | A passing project Playwright suite |
| Playwright CLI | Project-local Web regression and E2E | Full-stack behavior when only mocks/contracts are available |
| Maestro CLI / MCP | Mobile/Hybrid flows; device/flow diagnostics; optional Web smoke | Primary Web regression or unavailable real-device behavior |
| RTK / Caveman | Terminal-output / reply compression | Test execution, reports or reduced workflow obligations |

Graft installation is separately confirmed and pinned by the [managed runtime](sbtd-workflow-onboard/scripts/graft_runtime.py). One global `sbtd-graft` connection per effective Codex/OMP configuration domain locks the real repository/worktree from startup cwd; project initialization prepares local graphs. No parent-directory multi-project graph, implicit cloud enrichment, or silent legacy binding replacement. Codex hooks are a separate opt-in; OMP setup does not write hooks. [Wiring contract](sbtd-workflow-onboard/REFERENCE.md#codex-and-omp-wiring-and-deployment)

Managed Graft stays on the Graft command/tool contract even when Trail is installed: child environments disable automatic Trail switching and inherited Trail configuration. Project `.trail` notes are subject to the same no-link/no-special-file scope checks as native graph inputs. See [pin acceptance scenarios](sbtd-workflow-onboard/REFERENCE.md#graft-pin-acceptance-scenarios).

**Report what actually ran.** Native commands are preferred for report-producing tests. Keep failed runs, named native/raw reports and same-stem **Chinese** summaries. Distinguish `full-stack`, `contract-backed`, `mock-backed`/`app-mocked`, `backend-only`, `smoke-only` and `blocked`; a generated report is not a passing test. Dirty local evidence is not exact PR-head CI proof.

Agent-authored execution summaries use the [fixed Chinese report template](sbtd-workflow-onboard/templates/skills/project-validation/references/run-summary.zh-CN.md.template): conclusion/counts, run metadata, commands, BDD/scope, case results, failures/reruns, API URI coverage, artifacts/status, and limitations. Preserve failed rounds and source/deployment boundaries; unsupported fields need an explicit reason, not fabricated values. Coverage scoring is an appendix, not a substitute for execution results. Historical reports remain unchanged; reformatting retained evidence is a separately labeled preview, not a new test run.

| Asset | Default location in a target project |
|---|---|
| BDD source | Existing project `.feature` convention; Chinese scenario text + English keywords when no convention exists |
| Playwright test manifests | `tests/e2e/manifest/` — pass explicit paths, not root-level generator defaults |
| Playwright retained reports | `tests/e2e/reports/html/` |
| API reports | `tests/api/reports/` |
| Maestro flows / reports | `maestro/flow/` / `.maestro/reports/` |
| Unit reports | Project convention; otherwise `tests/unit/reports/` when required |
| SBTD task-local evidence | `ai/tasks/**/reports/` — ignored; task documents remain shareable |

Knowledge-base P1.1 produces read-only catalogs and smoke bundles; remote Evidence Store/PR Checks and publication remain P2 scope. BDD `sync` is a separate writable workflow. [Knowledge-base guide](sbtd-workflow-onboard/templates/skills/knowledge-base-integration/SKILL.md) · [Evidence contract](sbtd-workflow-onboard/templates/skills/project-validation/SKILL.md)

<details>
<summary><strong>Optional tools and common pitfalls</strong></summary>

- Playwright is project-local. Java 17+ and Maestro, optional MCPs, RTK and Caveman require their applicable setup choices; an installed Skill does not prove its CLI/server is callable.
- Caveman may compress repeated status updates under the global auto-lite policy; `normal mode` opts out for the task. ADHD structure is explicit opt-in only. See [presentation rules](sbtd-workflow-onboard/templates/skills/sbtd-task/references/presentation.md).
- React Bits is an optional project enhancement, not a shadcn dependency. Free registries must be known; paid tiers require an existing entitlement and local key handling. Never put keys in chat, examples or reports. [React Bits scope](sbtd-workflow-onboard/REFERENCE.md#react-bits)
- `init` is not content alignment; `reset` is not safe upgrade recovery. Upgrade verification separates disk, protocol and actual host loading; a preserved customization is not full alignment.
- Legacy Trellis/GitNexus is migration input, not the current workflow. Normal setup does not initialize Trellis or perform legacy cleanup. Cleanup requires a displayed list and consent; backups have a separate retention/destruction boundary.

</details>

<a id="reference"></a>
## Reference and manual entrypoints

| Need | Read |
|---|---|
| Full Onboard commands, scope and troubleshooting | [SKILL](sbtd-workflow-onboard/SKILL.md) · [REFERENCE](sbtd-workflow-onboard/REFERENCE.md) |
| Bootstrap / init / reset / project-only flowcharts | [Bootstrap](docs/assets/npx-skills-global-onboard-install.md) · [Init](docs/assets/onboard-skill-init.md) · [Reset](docs/assets/onboard-skill-reset.md) · [Project-only](docs/assets/onboard-init-projects.md) |
| Upgrade / migration / cleanup / recovery | [Upgrade](sbtd-workflow-onboard/REFERENCE.md#upgrade-alignment) · [Migration & recovery](sbtd-workflow-onboard/REFERENCE.md#migration-runtime) · [Cleanup](sbtd-workflow-onboard/REFERENCE.md#cleanup-runtime) |
| Global / project rules | [Global template](sbtd-workflow-onboard/templates/agents/AGENTS.global.md) · [Project template](sbtd-workflow-onboard/templates/agents/AGENTS.project.md) |
| Release history / monitored versions | [English CHANGELOG](CHANGELOG.md) · [中文变更日志](CHANGELOG.zh.md) · [ENTRYPOINT](ENTRYPOINT.md) |

<details>
<summary><strong>Manual setup after bootstrap, or from a cloned checkout</strong></summary>

Set `SBTD_ONBOARD_DIR` to the **actual installed package directory**, with dependencies prepared. First inspect:

```bash
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" plan \
  --platform codex --projects-root /abs/project-one,/abs/project-two --json
```

Only after reviewing and approving that same scope:

```bash
python "$SBTD_ONBOARD_DIR/scripts/onboard.py" init \
  --platform codex --projects-root /abs/project-one,/abs/project-two --yes --json
```

A cloned checkout also provides complete interactive installers:

```bash
bash install.sh
```

```powershell
pwsh -File .\install.ps1
```

For project-only setup, use `bash install.sh --platform codex --init-projects /abs/project` or `pwsh -File .\install.ps1 -Platform codex -InitProjects "C:\work\project"`. This is mutually exclusive with ordinary `--projects-root`/`--action` selections. Normal root-installer `init`/`reset` with `--yes`/`-Yes` and no project roots is **global-only**, not an implicit selection of cwd. Confirmation flags approve selected operations; they do not bypass conflicts or authorize migration.

</details>

<a id="repository"></a>
## Repository and maintenance

| Path | Role |
|---|---|
| `README.md` / `README.zh.md` | English and Chinese reader entrypoints; detailed contracts stay in linked sources |
| `sbtd-workflow-onboard/` | Self-contained installable Skill: runtime `scripts/`, payload `templates/`, mirrored `assets/`, catalog and reference |
| `install.sh` / `install.ps1` | Root installation interfaces; source root is the Onboard directory |
| `ENTRYPOINT.md` | Tracked monitoring baseline and recoverable maintenance entrypoint |
| `docs/lessons.md` | Required short lessons entry; index/topic detail is loaded only when relevant |
| `prompts/automations/sbtd-workflow-tools-version-check.md` | Versioned automation prompt, not a live automation update |
| `prompts/automations/references/` | Mandatory version-check scope policy and topic-routed compatibility checks |
| `.github/workflows/validation.yml` | Project-native validation matrix |

This source repository's root `AGENTS.md` is **optional, ignored and local-only**; it is not the project template or a fresh-clone prerequisite. Its root `.gitignore` is intentionally separate from the [target-project template](sbtd-workflow-onboard/templates/project/.gitignore):

```gitignore
.DS_Store
/.sbtd
/docs/handoffs
/ai/tasks/**/reports
/graft
/.graft
__pycache__/
AGENTS.md
.chrome-devtools-mcp/
.playwright-mcp/
```

Ignore rules do not sanitize secrets, untrack existing files or authorize deletion. Task reports are local by default; publishing evidence requires redaction and a separately approved destination. **This template-source repository does not create `.feature` files**; its durable behavioral specifications use Markdown and existing tests.

For source changes, assess both language READMEs, [English CHANGELOG](CHANGELOG.md), [Chinese CHANGELOG](CHANGELOG.zh.md) and the [versioned automation prompt](prompts/automations/sbtd-workflow-tools-version-check.md). The changelogs must match entry for entry: same versions, dates, order, facts, URLs, commit SHAs and code identifiers; only prose language differs. Update the top unpublished section in both, and preserve published history. Ordinary edits do **not** sync installed copies or live automation. Repository-maintenance `sync` requires explicit authorization; `update` advances monitored baselines other than Graft and archives the analyzed update. Graft's ENTRYPOINT baseline follows the pin in a published SBTD workflow version and is not advanced by official Graft releases or `update`. These are not Onboard upgrade commands or BDD sync requests.

The version-check automation uses a short main prompt, a per-run scope policy and an on-demand impact checklist. It validates the assigned Orca workspace, protects existing changes, distinguishes unavailable evidence from “no update”, and keeps `ENTRYPOINT.md` as the fixed baseline for official tool releases. Graft is the exception: its recorded baseline changes only when a published workflow version contains a new agreed pin. Native tag names are retained separately from comparison versions. When no confirmed unpublished CHANGELOG section exists, release-note proposals stay in `UPDATE.md` or the run output; the automation does not invent the next tag. Updating these source files does not update the live automation; that remains an explicit `sync` operation.

The native full-suite command remains `python -B -m unittest discover -s tests -p 'test_*.py'`. CI discovers that complete Linux set and partitions it into disjoint shards weighted by measured per-case seconds, splitting fixture-free cases individually and keeping class/module fixtures together (cases without a recorded weight are estimated at the median and listed in each shard inventory); Windows partitions its native scope without repeating overlapping PowerShell/Unicode selectors. macOS keeps its native scope. The existing check names aggregate all required shards; any failed, cancelled or missing shard blocks success. The minimum supported TOML-editor run remains a separate dependency variant, not a duplicate. Per-case timings, skip reasons and Chinese result summaries are retained as CI artifacts. Consult the [workflow](.github/workflows/validation.yml) and [runner](tests/run_ci.py) for exact scope. Source checks, installed-copy checks, real host loading and release acceptance remain separate evidence.

Catalog-independent migration boundary tests narrow only their installation inputs: they retain the complete Onboard launcher package, multiple sibling Skills and all file-routing operations. Full-catalog lifecycle and installed-copy tests remain separate anchors. Every stage still runs the real migration/recovery APIs and fresh safety checks; smaller fixtures do not authorize cached verdicts, reused receipts or omitted drift cases. Compare total runner cost separately from parallel wall-clock time.

Required native Windows checks (including ACLs, junctions, Unicode, PowerShell and enabled case-sensitive paths) and Linux case-sensitive checks must pass, not merely be selected: skip or expected failure blocks their shard.

CI artifacts retain each native run attempt without overwriting failures. Partial retries may reuse successful shards from the same SHA; aggregation selects each shard's newest report, rejects newer failures or ambiguous duplicates, and proves that the union covers the complete scope exactly once. Skip totals count native events, including skipped subtests; parent-case status counts can differ. Preserve subtest identities and reasons when comparing runs.

Windows currently uses four shards, Linux three, and macOS one job. After downloading a complete successful native report set, refresh scheduling inputs with `python -B tests/run_ci.py --platform windows --output <downloaded-reports> --refresh-weights` (use `linux` for Linux). Refresh requires a nonempty source revision and an unambiguous, complete, disjoint latest-attempt set; duplicate measurements or noncanonical shard filenames are rejected. Weights only change allocation, never test selection. Equal line/branch coverage alone does not justify removing a behavioral or platform boundary test.

<a id="license"></a>
## License and credits

Original repository and bundled original content use [Apache License 2.0](LICENSE), with [Onboard LICENSE](sbtd-workflow-onboard/LICENSE) and [NOTICE](sbtd-workflow-onboard/NOTICE) shipped in the package. Third-party mirrors retain their own licenses and pinned provenance; the adapted [seo-geo NOTICE](sbtd-workflow-onboard/templates/skills/seo-geo/NOTICE) records its upstream source and local changes.
