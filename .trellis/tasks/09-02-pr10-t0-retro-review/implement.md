# Implement T0 README @next contract

## Order

1. Update `packages/dsh-sbtd/features/t0-installable-stub.feature` README scenario to `@kunolu/dsh-sbtd@next`, forbid local path and bare package add. Keep Chinese scenario text + English Gherkin keywords.
2. Update `packages/dsh-sbtd/test/t0-stub.test.mjs` to match the scenario name and assertions.
3. Update `packages/dsh-sbtd/README.md` install command to `dsh plugin --profile web add @kunolu/dsh-sbtd@next`.
4. Run `node --test packages/dsh-sbtd/test/t0-stub.test.mjs`.
5. Commit on a new branch, open PR to `main`, do not merge.

## Validation

```bash
node --test packages/dsh-sbtd/test/t0-stub.test.mjs
```

## Rollback

Revert the three `packages/dsh-sbtd` files.

## Non-goals

No `apply()` change, no T1 files, no lockfile, no root README, no merge.
