# dsh-sbtd T16 端到端验收 grill

## Goal

Lock T16 e2e acceptance (grill-with-docs product forks) then record PASS on the same PR (#64). Host pin `@deepseek-ai/dsh@0.1.1-rc.2`.

## Requirements

- Consume T8/T10/T12/T13/T14/T15 as-is. Do not rewrite T0–T15 product modules.
- Host pin remains `@deepseek-ai/dsh@0.1.1-rc.2`. Package stays `0.1.0-rc.1`. No npm.
- Venue: this repo (`sbtd-plugins`). Human `dsh web` on Mac. Do not `trellis init`.
- **Q1A** — this-repo venue.
- **Q2A** — all 8 PRD v1.2 §T16 scenarios.
- **Q3A** — human `dsh web`.
- **Q4A** — `docs/acceptance.md` is the Acceptance Record (not a KPi Evidence Envelope).
- **Q5A** — record-only fence: docs + optional gitignore. No product/tools/hooks/backends.
- **Q6A** — HEAD-based local `npm pack` install, not registry `@next`.

## Acceptance Criteria

- [x] LIVE grill Q1A–Q6A locked (`/workspace/omp-tasks/t16-e2e-acceptance-grill.md`)
- [x] T16 PASS all 8 steps recorded in `docs/acceptance.md`
- [x] Review r2 CLEAN @ `97e365cbbf34dac658af33dceaab6e325a9765a8` (`/workspace/omp-tasks/t16-pr64-review-r2-extract.md`); `REQUIRED_CHANGES=none`
- [x] Under-test subject `98edd712efa46274fce7644b650937c9f5361929` (FU4 merged); PR tip adds `*.tgz` gitignore
- [x] `/trellis:finish-work` (scheme A, same PR)
- [ ] PR #64 merge to `main` (SHA pending squash)

## Notes

- Host pin `@deepseek-ai/dsh@0.1.1-rc.2`. Package `0.1.0-rc.1`.
- Fence: `docs/acceptance.md` + root `.gitignore` `*.tgz`. NO npm. NO product code.
- DDD sibling: `09-11-dsh-sbtd-t16-e2e-acceptance-ddd`.
