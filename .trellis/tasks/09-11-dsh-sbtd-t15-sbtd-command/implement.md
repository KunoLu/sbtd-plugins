# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl); DDD task archived via `task.py archive 09-11-dsh-sbtd-t15-sbtd-command-ddd --skip-branch-validation`
- [x] **R3** — GitNexus analyze + detect_changes (PR #62 body only; no tracked `gitnexus-check.md`)
- [x] **R4** — `features/t15-sbtd-command.feature`; `node:test` titles mirror Chinese `Scenario:` titles
- [x] **Phase 2.2 trellis-check** — @ **`8b61d5d`** (final PR tip)
- [x] **/review r4** — CLEAN @ **`8b61d5d`**; `/workspace/omp-tasks/t15-pr62-review-r4.md`
- [x] **/trellis:finish-work** — pending archive after this record commit

## Verification @ `8b61d5d` (2026-09-11)

```bash
cd packages/dsh-sbtd
npm run typecheck && npm run build
node --test test/t15-sbtd-command.test.mjs   # 12/12
node --test test/*.test.mjs                   # 322/322
```

## Check gate @ `8b61d5d`

| Gate | Result |
|---|---|
| GitNexus `lastCommit` | `8b61d5d4da48e8d5ecec224ed6b69940f516ea90` |
| detect_changes scope all | No changes detected |
| Product fence | unchanged since `f8561bf` |

## Review history

| Round | HEAD | Verdict |
|---|---|---|
| r1 | `a83ffd07` | block |
| r2 | `b7d346b` | **STALE** |
| r3 | `f8561bf` | CLEAN (product only) |
| r4 | `8b61d5d` | **CLEAN** (final tip) |

Premature archive @ `5670f14` reverted. r2 cannot certify post-`f8561bf` changes.

## GitNexus

HEAD-bound evidence in PR #62 body @ final tip. No tracked task-file artifact.
