# Design -- T9 GitNexus backend

## Modules

- `packages/dsh-sbtd/src/backends/gitnexus.ts` -- `detect` / `impact` / `detectChanges` / `defaultRunRefresh`
- `packages/dsh-sbtd/test/t9-gitnexus.test.mjs` -- module tests

No `index.ts` apply wiring. T10 is the later consumer.

## Decisions (locked)

1. Q1B -- three independent detect fields; CLI-on-PATH is refresh-only, not detect.
2. Q2A -- missing MCP or missing index ⇒ `skipped`; stale+refresh fail ⇒ `advisory:true`; never hard-fail.
3. Q3A -- locked AnalysisResult shape; functions never throw for unavailability.
4. Q4A -- best-effort project refresh with `--index-only` so writes stay inside `.gitnexus/`. Never MCP config.
5. Q5A -- module + tests only.
6. Q6A -- `serverName` then fallback `mcp__gitnexus__*`. Read-only.
7. r1 -- THIS-op MCP tool + `options.mcp` must validate before `ensureRefreshIfStale`.

## Out of scope

`apply()` / `sbtd_validate`, CONTEXT paste, `docs/prd` GitNexus wording, residuals listed in FOLLOWUPS.
