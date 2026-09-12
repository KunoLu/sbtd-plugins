# dsh-sbtd FU4 clarify JSON schema host compatibility DDD

## Goal

DDD-only boundary review after LIVE grill Q1B/Q2B/Q3C/Q4A/Q5A. Implementation on sibling grill task / PR #65. Host pin `@deepseek-ai/dsh@0.1.1-rc.2`.

## Requirements

- Consume LIVE locks. Do not re-interview. Do not reopen T6 Q1–Q11.
- Q1B is a coupled pair: optional `type:"string"` schema **and** host-facing omit of present null keys. Not present-null on the host payload.
- Q2B: all current type-array `output.schema` sites (clarify + spec + tickets). Parameters unchanged.
- Q3C: unit (no `Array.isArray(type)`) + host registration + execution asserting omit/null policy.
- Q4A: no npm; keep `0.1.0-rc.1`; T16 stays HEAD tarball.
- Q5A: after merge, rebuild tarball; re-run T16 from step 2; do not rewrite T16 acceptance.

## Acceptance Criteria

- [x] Independent DDD Boundary Review emitted with Status **confirmed**
- [x] No CONTEXT / ADR / npm this turn; production writes belonged to PR #65 fence only
- [x] r3 CLEAN @ `ca9eb8fc79d31d8abd7bfc1096d1b8a713a3a025`; Q1B Q2B Q3C Q4A PASS; Q5A pending post-merge T16
- [x] `/trellis:finish-work` archive as completed (scheme A, same PR #65)

## Notes

- Lightweight DDD-only sibling of `09-12-dsh-sbtd-fu4-clarify-schema-grill`.
- Merge SHA pending squash of https://github.com/KunoLu/sbtd-plugins/pull/65.
