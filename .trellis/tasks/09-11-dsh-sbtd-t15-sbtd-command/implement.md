# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl); DDD task archived via `task.py archive`
- [x] **R3** — GitNexus analyze + detect_changes (PR #62 body only)
- [x] **R4** — `features/t15-sbtd-command.feature`; `node:test` titles mirror Chinese `Scenario:` titles
- [x] **Phase 2.2 trellis-check** — @ **`f8561bf`** (product tip)
- [x] **/review r3b** — CLEAN @ **`f8561bf`** — `/workspace/omp-tasks/t15-pr62-review-r3b.md` (T15QualityR3b pass; T15QualityR3 block void)
- [ ] **/review r4** — process commits `f8561bf`..`HEAD` (pending)
- [ ] **/trellis:finish-work** — pending after r4

## Verification @ `f8561bf` (2026-09-11)

```bash
cd packages/dsh-sbtd
npm run typecheck && npm run build
node --test test/t15-sbtd-command.test.mjs   # 12/12
node --test test/*.test.mjs                   # 322/322
```

## Check gate @ `f8561bf`

| Gate | Result |
|---|---|
| GitNexus `lastCommit` | `f8561bf0a88b18a941fc24623b52a93900e17005` |
| detect_changes scope all | No changes detected |

## Review history

| Round | HEAD | Verdict | Notes |
|---|---|---|---|
| r1 | `a83ffd07` | block | REQUIRED_CHANGES R1–R4 |
| r2 | `b7d346b` | **STALE** | do not credit |
| r3 (T15QualityR3) | `f8561bf` | **block** | stale GitNexus — void |
| **r3b (T15QualityR3b)** | `f8561bf` | **CLEAN** | authoritative product review |
| r3 (T15SecurityR3) | `f8561bf` | **pass** | not re-run |
| r4 (prior file) | `8b61d5d` | **VOID** | written while r3 invalid |

Premature archives @ `5670f14` and `7f273d7` reverted; task restored `in_progress`.

## GitNexus

HEAD-bound evidence in PR #62 body. No tracked `gitnexus-check.md`.
