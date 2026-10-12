# Implement -- T7 Trellis backend

## Commits on feat/dsh-sbtd-t7-trellis-backend

1. d2a36af feat(dsh-sbtd): T7 Trellis backend FS primitives
2. 536b760 fix(dsh-sbtd): drop unlocked DSH_SESSION_ID->dsh_ mapping (T7 P2)
3. e9bc7cb fix(dsh-sbtd): Q6B validate-before-missing + Trellis sanitizeKey (T7 P2)

## Files

- packages/dsh-sbtd/src/backends/trellis.ts
- packages/dsh-sbtd/test/t7-trellis.test.mjs

## Validation (tip e9bc7cb)

- lint / typecheck / build / test green
- node --test 136 pass in packages/dsh-sbtd
- Review r3: Quality=pass, Security=pass, REQUIRED=0

## Fence held

No index.ts apply, no new sbtd tools, no docs/prd, no Channel, no trellis init, no T8, no registry publish, no omp config, host pin @deepseek-ai/dsh@0.1.1-rc.2.
