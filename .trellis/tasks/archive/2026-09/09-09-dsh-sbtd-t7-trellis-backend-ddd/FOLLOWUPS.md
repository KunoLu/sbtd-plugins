# T7 follow-ups / residuals (post-r3)

Head: e9bc7cbaae3ef1119cad0844babc80fb7d31e277 on feat/dsh-sbtd-t7-trellis-backend.

Review r3 CLEAN REQUIRED_CHANGES=none. Quality=pass; Security=pass. Combined=pass with residual.

## Residual -- symlink-at-tasks-dir physical follow (optional)

writeArtifact / path checks do not realpath a symlink placed at the tasks dir boundary. Security/Quality did not mark REQUIRED. Optional hardening if an explicit physical-sandbox policy is adopted later.

## T8 note -- pointer != slug

Q4A currentTask returns a session pointer. Q3A writeArtifact requires a safe slug. T8 must not pass currentTask.task pointer directly as writeArtifact slug.

## Not in this PR

- No index apply / T8 / Channel / trellis init
- No docs/TODO backfill (post-merge chore)
- No host pin change / registry publish / omp config
