# Implement -- T8 sbtd_spec / sbtd_tickets

## Commits on feat/dsh-sbtd-t8-spec-tickets

1. 522657a feat(dsh-sbtd): T8 sbtd_spec / sbtd_tickets via Trellis backend
2. bfe893f fix(dsh-sbtd): reject empty sbtd_spec/tickets body; add T8 BDD
3. 3fd773f fix(dsh-sbtd): align T5 registry BDD with five-tool apply

## Files

- packages/dsh-sbtd/src/tools/spec.ts
- packages/dsh-sbtd/src/tools/tickets.ts
- packages/dsh-sbtd/src/tools/task-artifact.ts
- packages/dsh-sbtd/src/index.ts
- packages/dsh-sbtd/features/t8-sbtd-spec-tickets.feature
- packages/dsh-sbtd/features/t5-sbtd-review.feature (registry Then: five-tool containment)
- packages/dsh-sbtd/test/t8-spec-tickets.test.mjs
- packages/dsh-sbtd/test/t2-plan.test.mjs
- packages/dsh-sbtd/test/t3-hooks.test.mjs
- packages/dsh-sbtd/test/t4-manuals.test.mjs
- packages/dsh-sbtd/test/t5-review.test.mjs
- packages/dsh-sbtd/test/t6-clarify.test.mjs
- docs/TODO.md (tip / T8 in-progress; finish closeout marks done)

## Validation (tip 3fd773f)

- lint / typecheck / build / test green
- node --test 150 pass in packages/dsh-sbtd
- Review r3: Quality=pass, Security=pass, REQUIRED=0

## Fence held

No extra sbtd_*, no docs/prd rewrite, no T7 API change, no Channel, no trellis init, no GitHub/Linear, no registry publish, no omp config, host pin @deepseek-ai/dsh@0.1.1-rc.2.
