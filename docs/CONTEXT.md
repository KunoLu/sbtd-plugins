# KPi Product Context

KPi defines the language for a runtime-neutral SBTD workflow product that coordinates engineering work without owning the underlying coding-agent execution environment.

## Language

**KPi**:
The product that provides the runtime-neutral SBTD workflow control plane and its user-facing distribution.
_Avoid_: OMP wrapper, Pi-derived agent, standalone agent runtime

**SBTD Workflow Control Plane**:
The KPi-owned domain that classifies work and governs workflow state, gates, policy, validation evidence, context orchestration, and reporting across compatible runtimes.
_Avoid_: agent loop, runtime, prompt bundle

**Runtime**:
A host coding-agent environment that owns the agent loop, model and provider execution, native tools, approvals, UI, and session primitives consumed by KPi.
_Avoid_: KPi Core, workflow engine

**Runtime Adapter**:
The boundary that translates a Runtime's public capabilities and events into the contracts required by the SBTD Workflow Control Plane.
_Avoid_: Runtime fork, provider adapter

**OMP-first**:
KPi's initial validation and delivery strategy using OMP as the first default Runtime Adapter; it is not KPi's product identity or permanent ownership boundary.
_Avoid_: OMP-only, OMP-native KPi

**Runtime Mode**:
The session-level choice between `enforced`, where KPi automatically governs the SBTD workflow, and `advisory`, where those automatic workflow controls are inactive.
_Avoid_: strict mode, environment status

**Effective Control State**:
The non-persistent `active`, `advisory`, `preflight-only`, or `blocked` result derived only from the current Runtime Mode and freshly observed Environment Mode; commands never set it directly.
_Avoid_: a user-selected mode, a persisted Session field

**Always-on Baseline**:
The safety, truthfulness, and imported Project Facts constraints that remain effective in every Effective Control State and are not disabled by `/sbtd off`.
_Avoid_: an Optional SBTD workflow check, conditional routing

**Runtime Marker (`sbtd-runtime`)**:
The Plugin-provided per-major-turn machine contract carrying state version, runtime mode, policy profile, Onboard Profile identifier, environment mode, effective control state, Route, and Stage. Mode-aware AGENTS conditional sections auto-run only when it reports `effective-control-state=active`.
_Avoid_: Project Facts, a user-authored AGENTS block

**Policy Profile**:
The `strict` or `relaxed` setting that changes optional workflow checks without changing Runtime Mode or bypassing route-required Gates.
_Avoid_: on/off mode, enforcement state

**Onboard Profile**:
The selected, non-policy installation baseline identified by a stable `onboardProfileId`; it declares each managed asset or capability as required or Optional for its Runtime and project scope. `AcceptedSkipV1` records and matches this identifier. It is independent of the `strict|relaxed` Policy Profile.
_Avoid_: Policy Profile, a transient command choice, an unversioned list of optional assets

**Managed Asset**:
A provenance-inventory unit with an explicit target, scope, source revision, and installed digest that KPi may update only while its recorded ownership and integrity still match.
_Avoid_: an entire file containing a Managed Block, any file or tool previously touched by Onboard

**Managed Block**:
A delimited, provenance-marked fragment of a file, identified by its target, source, revision, and digest. Content outside the block remains user or project owned and never acquires KPi ownership.
_Avoid_: the enclosing file, an unmarked template

**Provenance Inventory**:
The Environment Management record of Managed Assets, their ownership, target, scope, digest, source revision, lifecycle state, and repair path.
_Avoid_: a cache of every detected dependency

**Shared Dependency**:
An external tool, Skill, or configuration that KPi may detect or help install but does not own or remove by default.
_Avoid_: KPi-managed asset, bundled component

**Provider Login Delegation**:
A user-controlled handoff that opens a Runtime or official CLI login flow and returns only non-sensitive availability status to KPi.
_Avoid_: credential import, Coding Session delegation

**CLI Session Adapter**:
A Runtime Adapter that delegates Coding Session execution to an official external CLI under explicit capability, version, and Terms gates.
_Avoid_: login helper, token proxy

**SBTD Kit**:
The immutable, versioned KPi artifact generated from a full-SHA upstream SBTD workflow source and containing the aligned templates, machine rules, Skills, schemas, and compatibility metadata used by the control plane. It remains the complete Runtime-neutral canonical artifact. P0 derives the OMP Distribution Projection embedded in `@kunolu/omp-sbtd`; P1 manages the canonical artifact through a manifest and Doctor; P2 makes that canonical artifact independently publishable. The internal `sbtd-workflow-kit/` directory transforms the upstream baseline into the SBTD Kit; it is not a second product artifact nor the upstream source identity.
_Avoid_: live upstream checkout, Floating Main, prompt bundle, `@kunolu/omp-sbtd`, an OMP distribution

**OMP Distribution Projection**:
The deterministic, read-only subset and OMP-specific replacement view derived from one exact Canonical SBTD Kit for embedding in `@kunolu/omp-sbtd`. Every canonical asset is classified as included, omitted, or replaced; unknown assets fail closed. Its paths and bytes contain no non-OMP Runtime policy or compatibility payload, and its provenance binds both the canonical source and projection policy.
_Avoid_: KPi product identity, a second upstream source, a line-by-line mutation of third-party assets, the complete SBTD Kit

**SBTD Workflow Kit**:
The external upstream baseline and provenance identity for the SBTD Kit: `sourceId=sbtd-workflow-kit-upstream`, canonical source URI `https://github.com/KunoLu/640-skills`, resolved full SHA, optional source tag, and source digest. These fields are locked in `upstream.lock.json`; P0 consumes the resulting vendored snapshot and P1 additionally manages its immutable manifest.
_Avoid_: the internal `sbtd-workflow-kit/` transform directory, an unlocatable SHA, Floating Main

**Evidence Envelope**:
A local, exportable record that binds validation artifacts to an exact source revision, environment alignment, integrity metadata, and publication state.
_Avoid_: cloud evidence store, test output alone

**Evidence Service**:
A future post-v0.3 bounded context that stores and publishes Evidence Envelopes across tenants and external PR systems.
_Avoid_: local report renderer, P3 exit requirement

**Runtime Capability Status**:
The evidence-backed `native`, `adapter`, `degraded`, or `unsupported` classification of one Runtime Contract capability for a specific Runtime version.
_Avoid_: installed, assumed available, prompt-equivalent

**Project Facts**:
Repository-owned commands, paths, constraints, and local rules expressed through Root Project Facts and deeper project context, independent of the selected Runtime.
_Avoid_: KPi global policy, Runtime instructions

**Root Project Facts**:
The Runtime-independent project facts in the root `AGENTS.md`; they remain the source of truth when a Runtime-specific adapter is present.
_Avoid_: an OMP Project Adapter, KPi global policy

**OMP Project Adapter**:
The Runtime-specific `.omp/AGENTS.md` contract that imports Root Project Facts and carries OMP runtime and mode instructions without copying or owning the imported project facts.
_Avoid_: a replacement root `AGENTS.md`, an independently owned project-facts file

**Nearest-native Shadowing**:
The rule that the nearest native OMP Project Adapter is the effective entry point; it must explicitly preserve the required root-contract inheritance rather than silently hiding a root adapter.
_Avoid_: arbitrary AGENTS precedence, an ignored Workspace Adapter

**Context Bridge**:
An equivalent, digest-deduplicated injection of Root Project Facts only when a Runtime cannot natively express required import or inheritance. It never changes the owner of those facts.
_Avoid_: copying project facts into KPi policy, a fallback that bypasses imports

**Runtime-native Profile**:
An Onboard Profile where a Runtime Adapter injects workflow contracts directly without installing KPi Global AGENTS while still consuming Project Facts.
_Avoid_: no-AGENTS mode, project-facts-free mode

**Environment Mode**:
The deterministic `managed`, `needs-onboard`, `degraded`, or `blocked` assessment derived from effective assets, accepted skips, and the current Route's required capabilities.
_Avoid_: Runtime Mode, ambiguous fallback state

**Accepted Skip (`AcceptedSkipV1`)**:
An explicit, versioned, revocable, and expiring exception record that precisely matches an asset or capability, scope, `onboardProfileId`, and Kit major. It is created by a separately confirmed Plan action, carries provenance, and can cover only an Optional gap that the current Route does not require.
_Avoid_: a `--skip-*` flag by itself, a waiver for Route-required capability

**KPi Core**:
The Runtime-neutral implementation of the SBTD Workflow Control Plane contracts and decisions.
_Avoid_: entire KPi product, CLI shell, Onboard, Kit supply chain, Runtime

**Route**:
The classification result that selects the applicable workflow, required capabilities, Gates, and Checks for a task.
_Avoid_: model prompt, Runtime path

**Gate**:
A stateful workflow decision barrier with an objective predicate, required evidence, allowed transitions, and blocking behavior.
_Avoid_: optional suggestion, test command alone

**Rule Registry**:
The KPi-owned registry of machine-readable Rule predicates and policy decisions; only entries explicitly marked `configurable` may be toggled.
_Avoid_: the Command Registry, arbitrary prompt prose

**Rule**:
A Rule Registry entry used by classification, Routing, Gates, or Checks.
_Avoid_: an arbitrary prompt statement, a disableable Hard Gate

**Command Registry**:
The deterministic KPi control-plane source of command metadata. One `SbtdCommandSpec` definition generates parser and handler mapping, Help, unknown-command candidates, documentation, completion, and contract tests; Help paths neither call the model nor modify Session state.
_Avoid_: a separate CLI help table, a Rule Registry

**Onboard**:
The Environment Management workflow that plans and applies installation, migration, rollback, and scoped uninstall operations using provenance and Managed Asset contracts.
_Avoid_: SBTD workflow engine, package postinstall

**Artifact Supply Chain**:
The supporting context that synchronizes reviewed upstream sources and produces integrity- and license-verified Plugin, Kit, CLI, SBOM, and notice artifacts.
_Avoid_: live upstream loading, package registry alone

**Provider Coordination**:
The KPi supporting context for Provider Profiles, secret references, role/capability requirements, availability, fallback policy, and selection results passed to a Runtime.
_Avoid_: model execution, credential refresh, streaming transport, Provider Gateway
