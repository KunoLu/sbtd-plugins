# Implement -- T11 sbtd_bdd

## Commits on feat/dsh-sbtd-t11-sbtd-bdd

1. 160292c feat(dsh-sbtd): T11 sbtd_bdd (scheme A)
2. b1b478a fix(dsh-sbtd): T11 sbtd_bdd r1 REQUIRED_CHANGES (Q1C/Q2B sync)
3. e132cdd fix(dsh-sbtd): T11 close R4 discovery-cap residual (Q2B)
4. decbf63 fix(dsh-sbtd): T11 Q1C realpath containment (R5 symlink)
5. 975d878 fix(dsh-sbtd): T11 close R5 residuals (features symlink + dangling)

## Files

- packages/dsh-sbtd/src/tools/bdd.ts
- packages/dsh-sbtd/src/index.ts
- packages/dsh-sbtd/test/t11-bdd.test.mjs
- packages/dsh-sbtd/test/t10-validate.test.mjs (tools.length)
- packages/dsh-sbtd/test/t2-plan.test.mjs
- packages/dsh-sbtd/test/t3-hooks.test.mjs
- packages/dsh-sbtd/test/t4-manuals.test.mjs
- packages/dsh-sbtd/test/t5-review.test.mjs
- packages/dsh-sbtd/test/t6-clarify.test.mjs
- packages/dsh-sbtd/test/t8-spec-tickets.test.mjs
- docs/TODO.md (finish closeout marks T11 done; merge SHA pending)

## Validation (tip 975d878)

- Combined r5 CLEAN; Main+Pr53R5Reviewer CLEAN/correct; Advisor no content verdict (CLEAN ≠ advisor approval); REQUIRED_CHANGES=none
- r1–r5 REQUIRED closed in 975d878
- tests: 228/228 green (per r5)
- Do not re-run full /review (CLEAN already at 975d878)

## Fence held

No manuals/gherkin-bdd nest, no session.bdd, no validate.ts rewrite, no docs/prd rewrite, no T7/T8/T9/T10 reopen, no MCP config writes, no registry publish, no omp config, host pin @deepseek-ai/dsh@0.1.1-rc.2.
