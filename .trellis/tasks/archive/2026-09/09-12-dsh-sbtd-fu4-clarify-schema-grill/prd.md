# dsh-sbtd FU4 clarify JSON schema host compatibility grill

## Goal

Lock how to make tool `output.schema` host-compatible with `@deepseek-ai/dsh@0.1.1-rc.2` without reopening T6 clarify product semantics. Implementation landed on the same PR (#65).

## Requirements

- **Q1B** — Coupled pair: optional `type:"string"` schema **and** host-facing omit of present null keys. Domain `sbtdClarify()` / `runTaskArtifact` may still return JS `null`; host payload must omit those keys.
- **Q2B** — All current type-array `output.schema` sites (clarify + spec + tickets). Parameters unchanged.
- **Q3C** — Unit (no `Array.isArray(type)`) + pinned-host registration/execution asserting omit/null policy; package `test` runs `tsc` then `node --test`.
- **Q4A** — No npm; keep `0.1.0-rc.1`; T16 stays HEAD tarball.
- **Q5A** — After merge, rebuild tarball; re-run T16 from step 2; do not rewrite T16 acceptance.

## Acceptance Criteria

- [x] Q1B Q2B Q3C Q4A locked and implemented on PR #65
- [x] R1 CLOSED (pinned-host register/load smoke); R2 CLOSED (tsc-before-test provenance)
- [x] Review r3 CLEAN @ `ca9eb8fc79d31d8abd7bfc1096d1b8a713a3a025` (`/workspace/omp-tasks/fu4-pr65-review-r3-extract.md`); `REQUIRED_CHANGES=none`
- [x] Tests 331/331 on tip `ca9eb8f`; targeted Q3C `tsc && node --test test/fu4-host-schema.test.mjs` 1/1
- [x] `/trellis:finish-work` (scheme A, same PR)
- [ ] PR #65 merge to `main` (SHA pending squash)

## Notes

- Host pin `@deepseek-ai/dsh@0.1.1-rc.2`. Package `0.1.0-rc.1`.
- Fence: clarify/spec/tickets (+ task-artifact omit helper) + host-context optional bags + `fu4-host-schema.test.mjs` + package.json `test=tsc&&node --test` + related tests/features. NO npm.
- Q5A pending post-merge T16. Do not rewrite `docs/acceptance.md`.
