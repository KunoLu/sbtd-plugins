# FU3 follow-ups / locks (post-r2)

## Q4B re-lock (group+user, Locked A)

Original Q4B text read as “exactly two commits”. **Re-lock:** two *ordered feature* commits remain required —

1. persist-across-replans sticky Forced Docs DDD
2. multi-fact matching-set identity

— and **docs / review / fix** additional commits are permitted (honest Codex fix trail; tip includes `b33641f` canonicalize legacy DDD alias facts). **Do not rewrite history** to squash.

## Q1D alias scope (post-r2 artifact alignment)

Alias collapse is **DDD-only** (three grill-with-docs language rows → `完整执行 grill-with-docs`). persist/持久化 and schema/数据库 are **not** one identity; distinct ddia/legacy/release catalog rows stay distinct; set-expansion resets.

## Tip verify (post-`b33641f`)

Recorded on tip `b33641f97f15d694ebe29ecfe740ad9d5e550839` in `packages/dsh-sbtd`:

- `biome check src` pass
- `tsc --noEmit` pass
- `tsc` build pass
- `node --test test/*.test.mjs` **116/116**

No production logic change in the docs/verify follow-up.
