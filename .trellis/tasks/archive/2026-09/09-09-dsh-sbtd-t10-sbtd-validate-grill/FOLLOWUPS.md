# T10 grill follow-ups / residuals (post-r4)

Head: 7a660af6404cd14bf5f8eaddc7de3abedb689406 on feat/dsh-sbtd-t10-sbtd-validate.

Review r4 CLEAN REQUIRED_CHANGES=none. Quality=pass (0.98); Security=pass; Advisor CLEAN.

## Residual -- live DSH ToolRunContext.token (non-blocking)

Live DSH 0.1.1-rc.2 `ToolRunContext.token` shape was not dynamically inspected. Types + forwarding + unit test exist.

## Residual -- T9 residuals out of fence (non-blocking)

T9 detect() outer catch / injected runRefresh timeout / SIGTERM-only tree remain T9 follow-ups. Not T10 coding debt.

## Residual -- nested-execute name allowlist (non-blocking)

Security optional: defense-in-depth allowlist nested execute names to GitNexus impact/detect_changes.

## Not in this PR

- No docs/prd rewrite / CONTEXT paste
- No host pin change / registry publish / omp config
- docs/TODO.md merge-SHA backfill is a post-merge chore if still pending after squash
