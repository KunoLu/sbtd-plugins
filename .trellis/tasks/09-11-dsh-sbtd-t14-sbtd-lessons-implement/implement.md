# Implement — T14 sbtd_lessons

## Execution order (workflow.md)

1. Phase 1: `task.py create` → artifacts → `add-context` → `validate` → `start`
2. Phase 2.1: implement *(pre-gate commits already on branch — verify, do not re-implement)*
3. Phase 2.2: `trellis-check` *(validation commands below)*
4. Phase 3.3: `trellis-update-spec` *(`.trellis/spec/dsh-sbtd/backend/index.md`)*
5. Phase 3.4: post-gate commit only

## Pre-gate commits (NOT workflow-complete)

| SHA | Message |
|---|---|
| `ac5aed6` | feat(dsh-sbtd): T14 sbtd_lessons (scheme A) |
| `b26d0b9` | docs: TODO sync T14 #59 in progress |

Branch: `feat/t14-sbtd-lessons` · PR: https://github.com/KunoLu/sbtd-plugins/pull/59

## Files (pre-gate)

- `packages/dsh-sbtd/src/tools/lessons.ts`
- `packages/dsh-sbtd/src/index.ts`
- `packages/dsh-sbtd/test/t14-lessons.test.mjs`
- `packages/dsh-sbtd/test/t{2,3,5,6,8,10,11,13}-*.test.mjs` (tools.length 9)
- `packages/dsh-sbtd/test/t4-manuals.test.mjs` (whitelist)
- `docs/TODO.md`

## Check gate commands

```bash
cd packages/dsh-sbtd
../../node_modules/.bin/biome check src/tools/lessons.ts
../../node_modules/.bin/tsc -p tsconfig.json
node --test test/t14-lessons.test.mjs
node --test test/*.test.mjs
cd ../.. && git diff --name-only origin/main | rg 'trellis|e2e|maestro|validate|bdd|gitnexus' && exit 1 || true
```

## Spec update gate

Update `.trellis/spec/dsh-sbtd/backend/index.md`:
- Current State section: T14 `sbtd_lessons`, nine tools on `apply()`
- Source files list includes `src/tools/lessons.ts`

## Post-gate commit

Single commit after check + spec update pass, e.g.:

`chore(trellis): T14 gate — spec update + task artifacts (pre-gate ac5aed6+b26d0b9)`

## Fence

No trellis/e2e/maestro/validate/bdd/gitnexus rewrite; no npm publish; host pin `@deepseek-ai/dsh@0.1.1-rc.2`.

## Check gate results (2026-09-11)

- biome check src/tools/lessons.ts: PASS
- tsc -p tsconfig.json: PASS
- node --test test/t14-lessons.test.mjs: PASS (13/13)
- node --test test/*.test.mjs: PASS (299/299)
- forbidden src rewrite (trellis/e2e/maestro/validate/bdd/gitnexus.ts): none

## Spec update gate (2026-09-11)

- Updated `.trellis/spec/dsh-sbtd/backend/index.md` — T14 `sbtd_lessons`, nine tools, lessons.ts entry
