# Sync omp-sbtd rc.14 onboard v1.0.13

## Goal

Workflow-only sync omp-sbtd from 640-skills v1.0.13, package 0.1.0-rc.14, validate, PR, publish next, clean install.

## Requirements

- Bump package to 0.1.0-rc.14; open/merge PR
- Workflow-only sync-upstream from 640-skills v1.0.13 commit f8aa0d7225a26c5e00b81d2f1b05121108e63630 into packages/omp-sbtd
- Verify clean plugin install at next and doctor four ok
- Keep registry dist-tag next only; do not touch latest

## Acceptance Criteria

- [x] Workflow-only sync from 640-skills v1.0.13 @ f8aa0d7225a26c5e00b81d2f1b05121108e63630
- [x] Package 0.1.0-rc.14; PR https://github.com/KunoLu/sbtd-plugins/pull/4 squash-merged as f11abd228e6f009ee3f6a3302ec016a4ac0e9c81
- [x] Published npm dist-tag next = 0.1.0-rc.14 (latest left alone)
- [x] Clean `omp plugin install @kunolu/omp-sbtd@next` + doctor 4 ok

## Notes

Work completed on `sync/omp-sbtd-rc14-onboard-v1.0.13`; merge commit `f11abd2`.
