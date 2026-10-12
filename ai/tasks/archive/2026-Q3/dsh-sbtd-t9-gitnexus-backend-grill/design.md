# Design -- T9 grill (product forks only)

T9 is a GitNexus Backend Module (`src/backends/gitnexus.ts`). It is not `sbtd_validate`, not GitNexus-the-product, not a T7 reopen.

## Decisions (locked in grill, confirmed in DDD)

1. Detect fields are independent: `mcpVisible`, `indexPresent`, `stale`. CLI-on-PATH is not a detect field.
2. Missing MCP or missing `.gitnexus/` is `skipped`. Stale after failed refresh is printable `advisory:true`, not skip, not throw.
3. Backend contract is `{ status, summary, advisory?, reason? }` with `status` ∈ {`ok`,`skipped`,`advisory`}.
4. Stale triggers best-effort project refresh; never write MCP config.
5. Fence is the module + its tests only.
6. Tool names from `serverName` then fallback `mcp__gitnexus__*`.

## Out of scope

`apply()` wiring, `sbtd_validate`, CONTEXT/ADR disk write, `docs/prd` rewrite, host pin retarget.
