# T9 grill follow-ups / residuals (post-r2)

Head: df7abb2cf3bc8ef0a3cfc3532057ebe0f166082e on feat/dsh-sbtd-t9-gitnexus-backend.

Review r2 CLEAN REQUIRED_CHANGES=none. Quality=PASS; Security=pass. Advisor weighed non-blocker.

## Residual -- detect() outer catch fact-erasure (non-blocking)

Outer `detect()` catch can erase independent field facts. Review r2 did not mark REQUIRED.

## Residual -- injected runRefresh without timeout wrap (non-blocking)

Injected `runRefresh` is not timeout-wrapped the same way as `defaultRunRefresh`. Optional later wrap; not REQUIRED.

## Residual -- SIGTERM-only child process tree (non-blocking)

Refresh child process tree is SIGTERM-only. Optional later hardening; not REQUIRED.

## Residual -- T10 caller trust (non-blocking)

T10 callers must not pass model-controlled `cwd` / `mcp` / `runRefresh`. Named for T10; not T9 coding debt.

## Not in this PR

- No docs/prd rewrite / CONTEXT paste
- No `apply()` / `sbtd_validate` / T10 start
- No host pin change / registry publish / omp config
- docs/TODO.md merge-SHA backfill is a post-merge chore if still pending after squash
