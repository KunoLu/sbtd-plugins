# dsh-sbtd Backend Guidelines

> Conventions for `@kunolu/dsh-sbtd` (`packages/dsh-sbtd/`): the DSH host adapter.
> T15 adds human `/sbtd` commands on `ctx.commands`. T14 adds `sbtd_lessons`. T6 `sbtd_clarify`, T5 `sbtd_review`, T4 manuals sync remain. Host `@deepseek-ai/dsh@0.1.1-rc.2`.

---

## Current State (T15 + T14 + T6 + FU3)

Per `packages/dsh-sbtd/README.md`: DSH SBTD adapter registers a short Chinese `sbtd` section,
in-process session state, nine tools on `apply()` (`sbtd_plan`, `sbtd_review`, `sbtd_clarify`,
`sbtd_spec`, `sbtd_tickets`, `sbtd_validate`, `sbtd_bdd`, `sbtd_e2e`, `sbtd_lessons`), hooks,
plus manuals/. T15 registers one human command `sbtd` via `inject` + `registerCommand` (not a model tool): bare `/sbtd` (read-only status), `/sbtd plan` (session plan view), `/sbtd maestro` (T12 `preflight()` only).
Target host: `@deepseek-ai/dsh@0.1.1-rc.2`.
`apply()` does not write `AGENTS.md` or user disk.
FU3 is **delivered**: matching-set identity + docs-Complete same-task Forced Docs DDD stickiness via `mergeGate`.

Source files:

- `src/index.ts` — `name`, `inject = ["tools", "systemPrompt", "commands"]`, `apply` (registers all sbtd_* tools + hooks + human `sbtd` command)
- `src/commands/sbtd.ts` — human `/sbtd` command handler (`parseSbtdArgv`, `runSbtdCommand`, `registerCommand`); `rawInput` accepts only empty/`plan`/`maestro`
- `src/section.ts` — static Chinese section text, `name: "sbtd"`, `order: 50`; Forced DDD prose is docs-mode Complete only
- `src/state.ts` — `Map` keyed by caller `sessionId`; `serialize()` / `restore()` copy optional `clarifyMode` + `clarifyStatus` + `clarifyCompleteTaskId`
- `src/tools/plan.ts` — `sbtd_plan` registers/updates BookGatePlan. DDD is required only after completed `grill-with-docs`; bare `ddd` stays on-demand. FU3 **delivered**: trigger identity is the matching-set of distinct catalog facts; docs-Complete Forced Docs DDD stays `required` via `mergeGate` only when `clarifyCompleteTaskId` matches the current plan (omission ≠ withdraw).

- `src/tools/review.ts` — `sbtd_review` records one Book Gate; FU2 Review Recording Order when both legacy and refactor are required
- `src/tools/clarify.ts` — `sbtd_clarify` interview adapter; Q8 haystack elevate is one-shot on docs Complete
- `src/tools/lessons.ts` — `sbtd_lessons` record/match/read durable lessons (T14). Five event kinds only; Trellis → `.trellis/lessons/topics/<topic>.md` + `index.md`; no Trellis → `docs/lessons.md` or layered `docs/lessons/`; consumes T7 `detect()` only; no GitNexus; no `writeArtifact`; model schema forbids T10 trust keys (`cwd`, `mcp`, …)
- `src/hooks.ts` — `ctx.on("tools/pre-execute")` and `ctx.on("agent/pre-step")`. Allow via `next()`. Local host types only.
- `scripts/sync-manuals.sh` + `manuals/**` — 640-skills v1.0.13 whitelist SKILL.md + that skill's references/; MANIFEST.json sourcePath + sha256 + sourceRevision

Do not import `@deepseek-ai/dsh` types. Local context type only.

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Layout and the DSH host boundary |
| [Quality Guidelines](./quality-guidelines.md) | Inherited toolchain conventions |

When later tasks add tools or backends, model new guidance on the sibling specs
(`../../omp-sbtd/backend/`, `../../sbtd-workflow-kit/backend/`) rather than reinstating generic
templates.

---

## Pre-Development Checklist

- [ ] Confirm host pin `@deepseek-ai/dsh@0.1.1-rc.2`. Do not start T7/T8 from an unrelated task. FU3 matching-set / `mergeGate` stickiness is delivered.
- [ ] When adding real behavior, check the DSH host contract first: `cordis.patch.yml` +
  `package.json#dsh.bundle.patch` + the `name`/`inject`/`apply` exports in `src/index.ts`.
- [ ] Tests use `node:test` against `dist/` after `tsc`, with BDD-mirrored titles under `features/`.

## Quality Check

- [ ] `pnpm --filter @kunolu/dsh-sbtd lint`, `typecheck`, `build`, and `test` pass.
- [ ] The package remains `"private": true`.
- [ ] `plugin.json`-style publish surface does NOT exist here.
- [ ] `apply()` still does not write `AGENTS.md` or user disk.

---

**Language**: Spec documentation is written in **English**.
