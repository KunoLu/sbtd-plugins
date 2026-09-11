# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl); DDD task archived via `task.py archive`
- [x] **R3** — GitNexus analyze + detect_changes (PR #62 body only)
- [x] **R4** — `features/t15-sbtd-command.feature`; `node:test` titles mirror Chinese `Scenario:` titles
- [x] **Phase 2.2 trellis-check** — @ **`f8561bf`** (product tip)
- [x] **/review r3b** — CLEAN @ **`f8561bf`** — `/workspace/omp-tasks/t15-pr62-review-r3b.md` (T15QualityR3b pass; T15QualityR3 block void)
- [x] **/review r4b** — CLEAN @ `70d3a60` — `/workspace/omp-tasks/t15-pr62-review-r4b.md` (T15QualityR4b pass)
- [x] **/review r5** — CLEAN @ `3529daf` — `/workspace/omp-tasks/t15-pr62-review-r5.md` (T15QualityR5+T15SecurityR5 pass)
- [x] **/trellis:finish-work** — archived completed; FOLLOWUPS; TODO ready; merge SHA pending

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
| r3 (T15SecurityR3) | `f8561bf` | **pass** | product authority |
| r4 (T15QualityR4-2) | `70d3a60` (pre-fix) | **block** | invalid artifact claims |
| **r4b (T15QualityR4b)** | `70d3a60` | **CLEAN** | authoritative process quality |
| r4 (T15SecurityR4) | `8b61d5d` | **pass** | `/workspace/omp-tasks/t15-pr62-review-r4-security.md` |
| **r5 (T15QualityR5+T15SecurityR5)** | `3529daf` | **CLEAN** | `/workspace/omp-tasks/t15-pr62-review-r5.md`; REQUIRED_CHANGES=none; R1–R4 CLOSED |

Premature archives @ `5670f14` and `7f273d7` reverted; task restored `in_progress` then re-archived after r4b.

## GitNexus

HEAD-bound evidence in PR #62 body. No tracked `gitnexus-check.md`.
