# T8 grill follow-ups / residuals (post-r3)

Head: 3fd773fad62028f827a6f6bbcb2c07f6413ac1c7 on feat/dsh-sbtd-t8-spec-tickets.

Review r3 CLEAN REQUIRED_CHANGES=none. Quality=pass; Security=pass.

## Residual -- T5 scenario title nit (non-blocking)

`packages/dsh-sbtd/features/t5-sbtd-review.feature` Scenario title still names the original three tools (`sbtd_plan`/`sbtd_review`/`sbtd_clarify`) while the Then step asserts five-tool containment. Review r3 treated this as documentation wording, not a control. Optional later wording sync; not REQUIRED.

## Residual -- T7 symlink-at-tasks-dir physical follow (non-blocking)

Inherited consume-only from T7: lexical `resolve` / `writeFileSync` follow a pre-planted `.trellis` or `.trellis/tasks` link. T8 does not add an argument-only sandbox escape. Optional hardening if an explicit physical-sandbox policy is adopted later.

## Not in this PR

- No docs/prd rewrite / CONTEXT paste
- No child-task creation
- No host pin change / registry publish / omp config
- No P2 T9 start
