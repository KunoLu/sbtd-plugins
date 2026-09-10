# Design -- T11 sbtd_bdd

## Modules

- `packages/dsh-sbtd/src/tools/bdd.ts` -- `sbtdBdd` / `resolveBddHost` / `registerBddTool` / `findDistinctFeatureParentDirs` / `validateExtraPaths`
- `packages/dsh-sbtd/src/index.ts` -- `apply()` `registerBddTool(ctx, resolveBddHost(ctx))`
- `packages/dsh-sbtd/test/t11-bdd.test.mjs` -- tool tests

## Decisions (locked)

1. Q1C -- model-visible args = intent + slug/relative `.feature` path; extra_paths host-allowlisted; T10 keys forbidden.
2. Q2B -- existing features/ conventions win; plugin fixtures not consumer SoT; no `found[0]` / discovery-cap hide.
3. Q3A -- register from apply.
4. Q4A -- spec/tickets do not override `.feature`; no validate.ts rewrite.
5. Q5A -- read = local catalog, Mutation none.
6. Q6A -- no manuals nest; no session.bdd.
7. r1–r5 -- extra default-deny; sync-not-capable; `.feature` suffix; distinct parents; realpath + features-dir symlink + dangling symlink reject.

## Out of scope

T12/T13, knowledge-base-integration, CONTEXT paste, `docs/prd` body, residuals listed in FOLLOWUPS.
