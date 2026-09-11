# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl)
- [x] **R3** — GitNexus analyze + detect_changes bound to HEAD (see `gitnexus-check.md`)
- [x] **R4** — `features/t15-sbtd-command.feature` + scenario comments in tests

## Verification (2026-09-11)

```bash
cd packages/dsh-sbtd
npm run typecheck
npm run build
node --test test/t15-sbtd-command.test.mjs   # 12/12
node --test test/*.test.mjs                   # 322/322
npm run lint                                  # pre-existing maestro.ts biome issues only
```

R1 proof: `parseSbtdArgv("sbtd")` throws; `parseSbtdArgv("plan")` → `"plan"`; `runSbtdCommand("")` → `no-plan`.

## Review / check

- r1 combined verdict at `a83ffd07`: **block / not CLEAN** (Quality block, Security pass).
- This pass implements REQUIRED_CHANGES R1–R4.
- **Do not claim CLEAN.** `/review` not started.

## GitNexus

See `gitnexus-check.md` for HEAD SHA, `lastCommit`, and detect_changes summary.
