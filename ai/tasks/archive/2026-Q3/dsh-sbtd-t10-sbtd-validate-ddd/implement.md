# Implement -- T10 sbtd_validate

## Commits on feat/dsh-sbtd-t10-sbtd-validate

1. 0efe88e feat(dsh-sbtd): T10 sbtd_validate (scheme A)
2. 7e41438 fix(dsh-sbtd): T10 r1 REQUIRED — host GitNexus inject + non-Node tests
3. 8de7ec8 fix(dsh-sbtd): T10 r2 REQUIRED — multi-candidate docs + cancel≠blocked
4. 7a660af fix(dsh-sbtd): T10 r3 REQUIRED — nested agent/parent + cancel≠post

## Files

- packages/dsh-sbtd/src/tools/validate.ts
- packages/dsh-sbtd/src/index.ts
- packages/dsh-sbtd/src/tools/plan.ts
- packages/dsh-sbtd/test/t10-validate.test.mjs
- packages/dsh-sbtd/test/t2-plan.test.mjs (tools.length)
- packages/dsh-sbtd/test/t3-hooks.test.mjs
- packages/dsh-sbtd/test/t4-manuals.test.mjs
- packages/dsh-sbtd/test/t5-review.test.mjs
- packages/dsh-sbtd/test/t6-clarify.test.mjs
- packages/dsh-sbtd/test/t8-spec-tickets.test.mjs
- docs/TODO.md (finish closeout marks T10 done; merge SHA pending)

## Validation (tip 7a660af)

- Review r4: Quality=pass (0.98), Security=pass, Advisor CLEAN, REQUIRED=0
- r1/r2/r3 REQUIRED closed in 7a660af
- tests: 201 green (per r4 tldr)
- Do not re-run full /review (CLEAN already at 7a660af)

## Fence held

No gitnexus.ts rewrite, no docs/prd rewrite, no T7/T8/T9 reopen, no MCP config writes, no registry publish, no omp config, host pin @deepseek-ai/dsh@0.1.1-rc.2.
