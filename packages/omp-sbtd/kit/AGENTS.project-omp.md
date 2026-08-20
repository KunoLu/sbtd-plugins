<!-- KPi template: project-omp; sourceId=sbtd-workflow-kit-upstream; revision=4222b15cc0e101bfe3489f1cebc0e5bfb4d1bddb; transform=p0-v3 -->
@../AGENTS.md

# OMP Project Adapter

This adapter preserves Root Project Facts through the import above.

<!-- KPi overlay: project-omp policy; version=p0-v2 -->

## KPi OMP Trellis Phase Routing

KPi owns the OMP task-worker route. A worker follows the active Trellis phase and may not activate a different dispatch model by inheriting upstream text. The upstream dispatch model is not an OMP runtime policy.

- Use OMP task workers only for the explicit active task and its declared phase.
- Keep planning, implementation, validation, and completion gates distinct; do not treat dispatch configuration as permission to skip a gate.
- A Trellis Channel runtime is separate from OMP task workers and is never enabled merely because a task has multiple changes.

## Trellis Channel

Only start the Channel runtime after the user explicitly requests it or confirms a preflight recommendation. Channel preflight is advisory and does not replace Trellis checks, package validation, or the OMP runtime contract.

### 主动 Preflight 场景

- 用户明确要求代码 review、并行 review、交叉验证或多 Agent 工作。
- Kit/Plugin promotion requires an independent rollback or validation review after the normal checks.
- Trellis artifacts, the generated Kit, and the embedded Plugin snapshot need a consistency review.

### Review / Validation 用法

Channel reviewers are read-only by default. The sole OMP task worker retains write ownership; Channel must not publish, install a Plugin, mutate user configuration, or replace a local validation controller.

## KPi Runtime Marker Contract

The Plugin supplies a per-major-turn `sbtd-runtime` machine contract. It contains the Kit revision, Runtime Mode, Policy Profile, Environment Mode, Effective Control State, Route, and Stage. Project Facts imported above remain authoritative.

## Mode-aware SBTD Overlay

Always preserve the imported Root Project Facts and safety baseline. Activate automatic SBTD routing, Book Gates, Skill routing, and delivery gates only when `sbtd-runtime.effective-control-state=active`. In every other control state, retain only the always-on safety, truthfulness, and Project Facts constraints.
