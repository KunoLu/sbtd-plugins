# T4 implement

## Legacy Change Safety Review

```text
Legacy Change Safety Review
Status: characterized
Behavior to change: HEAD fba44da copied domain-modeling ADR-FORMAT.md and CONTEXT-FORMAT.md; MANIFEST used dest-relative path + top-level revision.
Behavior to preserve: 12 whitelist ids from templates/skills and assets/external-skills/stable/skills; SKILL.md always copied; references/ copied only if present; missing source / SHA mismatch / copy fail / checksum fail exit 1; no install.sh, onboard.py, agents/; unpublished private package; hooks.ts and sbtd_plan unchanged.
Current reproduction evidence: committed manuals/domain-modeling/{ADR,CONTEXT}-FORMAT.md and MANIFEST files[].path entries on fba44da; pin SHA f8aa0d7225a26c5e00b81d2f1b05121108e63630 still required.
Safety net: features/t4-manuals-sync.feature + test/t4-manuals.test.mjs (every MANIFEST sourcePath/sha256/sourceRevision vs dest; package walk skip node_modules/dist forbids install.sh) + test/t4-sync-exit.test.mjs.
Hidden dependencies / seam: script is CLI-only; not imported by apply/hooks. GitNexus impact UNKNOWN (bash not in graph); callers confirmed by text search: tests, README, Trellis artifacts.
Validation plan: bash packages/dsh-sbtd/scripts/sync-manuals.sh /workspace/640-skills; biome/tsc/node --test.
Review mode: normal
```

## Refactoring Review

```text
Refactoring Review
Status: proceed
Review mode: normal
Existing-code scope: packages/dsh-sbtd/scripts/sync-manuals.sh. No src/*.ts.
Behavior that must remain unchanged: whitelist 12 ids; search templates/skills and assets/external-skills/stable/skills; copy only SKILL.md + references/; fail nonzero on missing source / SHA mismatch / copy fail / checksum fail; no install.sh/onboard.py/agents/.
Structural friction: none. Linear resolve → find → copy → manifest.
Decision and smallest safe step: no refactor. MANIFEST uses origin sourcePath + source sha256 + sourceRevision; dest must equal source digest.
Safety net and validation: t4-manuals.test.mjs + t4-sync-exit.test.mjs; bash packages/dsh-sbtd/scripts/sync-manuals.sh /workspace/640-skills; package lint/typecheck/build/test.
Deferred refactors: none.
```

## Order

1. BDD `features/t4-manuals-sync.feature` 锁 origin sourcePath / sha256 / sourceRevision 与失败非 0。
2. `scripts/sync-manuals.sh`：源字节 sha256 写入 MANIFEST，dest 必须等于该 digest。
3. `bash packages/dsh-sbtd/scripts/sync-manuals.sh /workspace/640-skills`
4. `test/t4-manuals.test.mjs` / `t4-sync-exit.test.mjs`
5. Package README：pin SHA、如何跑 sync、不要手改 manuals。
6. backend spec → T4。
7. 不改 `src/hooks.ts`。不加 tool。不 commit。

## Validation

```bash
bash packages/dsh-sbtd/scripts/sync-manuals.sh /workspace/640-skills
./node_modules/.bin/biome check packages/dsh-sbtd/src
./node_modules/.bin/tsc -p packages/dsh-sbtd/tsconfig.json --noEmit
./node_modules/.bin/tsc -p packages/dsh-sbtd/tsconfig.json
node --test packages/dsh-sbtd/test/*.test.mjs
```

`pnpm --filter` 因既有 lockfile 与 peer `@deepseek-ai/dsh@0.1.1-rc.2` 不一致而无法 frozen install；本轮不改 lockfile。`rtk` 不可用。

## Rollback

丢弃本工作树对 `packages/dsh-sbtd`、`.trellis/tasks/09-03-dsh-sbtd-t4`、`.trellis/spec/dsh-sbtd/backend` 的未提交改动。
