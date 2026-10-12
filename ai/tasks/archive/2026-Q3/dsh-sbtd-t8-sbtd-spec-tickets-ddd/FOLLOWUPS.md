# T8 follow-ups / residuals (post-r3)

Head: 3fd773fad62028f827a6f6bbcb2c07f6413ac1c7 on feat/dsh-sbtd-t8-spec-tickets.

Review r3 CLEAN REQUIRED_CHANGES=none. Quality=pass; Security=pass.

## Residual -- T5 scenario title nit (non-blocking)

`packages/dsh-sbtd/features/t5-sbtd-review.feature` Scenario title still names the original three tools while the Then step asserts five-tool containment (`含 sbtd_plan、sbtd_review、sbtd_clarify、sbtd_spec、sbtd_tickets`). r3 Quality/Security: documentation wording, not a control. Optional later title sync; not REQUIRED.

## Residual -- T7 symlink-at-tasks-dir physical follow (non-blocking)

writeArtifact / path checks do not realpath a symlink placed at the tasks dir boundary. Inherited consume-only from T7. Security did not mark REQUIRED for T8. Optional hardening if an explicit physical-sandbox policy is adopted later.

## Docs debt (out of T8 fence)

- Design v1.2 §6.2 still says `sbtd_tickets` writes parent/child artifacts. Q4A locked `implement.md` slices. Do not patch `docs/prd` in this PR.
- Optional Lord paste of CONTEXT fragment (spec/tickets, Pointer vs Slug, DDD Unconfirmed Refuse, Has-Trellis Write Gate).

## Not in this PR

- No child-task creation / Channel / trellis init
- No host pin change / registry publish / omp config
- No P2 T9 start
- docs/TODO.md merge-SHA backfill is a post-merge chore if still pending after squash
