# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl); DDD task archived
- [x] **R3** — GitNexus analyze + detect_changes bound to final pushed HEAD (PR #62 body only; no tracked `gitnexus-check.md`)
- [x] **R4** — `features/t15-sbtd-command.feature` + scenario comments in tests
- [ ] **Phase 2.2 trellis-check** — recorded below (2026-09-11 @ `48753bb`)
- [ ] **/review r2** — started after fix pass; verdict pending (do not claim CLEAN until r2 completes)

## Verification (2026-09-11 @ `48753bb`)

```bash
cd packages/dsh-sbtd
npm run typecheck
npm run build
node --test test/t15-sbtd-command.test.mjs   # 12/12
node --test test/*.test.mjs                   # 322/322
npm run lint                                  # pre-existing maestro.ts biome issues only
```

R1 proof: `parseSbtdArgv("sbtd")` throws; `parseSbtdArgv("plan")` → `"plan"`; `runSbtdCommand("")` → `no-plan`.

## Check gate results (Phase 2.2 — 2026-09-11 @ `48753bb`)

### GitNexus (mandatory)

| Step | Result |
|---|---|
| Index refresh (`node .gitnexus/run.cjs analyze`) | PASS — `lastCommit` = `48753bb3adff265b594dc1e727ea4f41fdeedc10` |
| `detect-changes --scope all` | PASS — `No changes detected.` |

**R3 evidence location:** PR #62 body only. Tracked `gitnexus-check.md` was removed in `48753bb` (supersedes stale `fb87a6e` artifact that pinned `05df370` and said “re-run after commit 2”).

### Unit / type / fence

- typecheck: PASS
- build: PASS
- `node --test test/t15-sbtd-command.test.mjs`: PASS (12/12)
- `node --test test/*.test.mjs`: PASS (322/322)
- forbidden src rewrite (hooks/tools/backends/gitnexus.ts): none

## Review / check

| Round | HEAD | Verdict | Notes |
|---|---|---|---|
| r1 | `a83ffd07` | **block / not CLEAN** | Quality block (argv grammar + Trellis/GitNexus/BDD process); Security pass |
| r2 | `48753bb` | **pending** | Post R1–R4 fix pass; `/review` r2 started 2026-09-11 |

- r1 REQUIRED_CHANGES R1–R4: implemented on branch; trellis-check gate recorded above.
- **Do not claim CLEAN** until r2 combined verdict + advisor conclude.
- **Task remains `in_progress`** until `/trellis:finish-work` after CLEAN review.

## GitNexus

HEAD-bound analyze/detect is recorded in PR #62 body at `48753bb`. No tracked task-file artifact (avoids stale `lastCommit` after follow-up commits).
