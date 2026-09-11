# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl); DDD task archived via `task.py archive 09-11-dsh-sbtd-t15-sbtd-command-ddd --skip-branch-validation`
- [x] **R3** — GitNexus analyze + detect_changes bound to product tip `f8561bf` (PR #62 body only; no tracked `gitnexus-check.md`)
- [x] **R4** — `features/t15-sbtd-command.feature`; `node:test` titles mirror Chinese `Scenario:` titles (English Gherkin keywords)
- [x] **Phase 2.2 trellis-check** — recorded below (2026-09-11 @ **`f8561bf`**)
- [x] **/review r3** — CLEAN @ **`f8561bf`** (2026-09-11); see `/workspace/omp-tasks/t15-pr62-review-r3.md`
- [ ] **/trellis:finish-work** — pending (premature finish-work @ `5670f14` reverted)

## Verification (2026-09-11 @ `f8561bf`)

```bash
cd packages/dsh-sbtd
npm run typecheck
npm run build
node --test test/t15-sbtd-command.test.mjs   # 12/12
node --test test/*.test.mjs                   # 322/322
npm run lint                                  # pre-existing maestro.ts biome issues only
```

R1 proof: `parseSbtdArgv("sbtd")` throws; `parseSbtdArgv("plan")` → `"plan"`; `runSbtdCommand("")` → `no-plan`.

## Check gate results (Phase 2.2 — 2026-09-11 @ `f8561bf`)

### GitNexus (mandatory)

| Step | Result |
|---|---|
| Index refresh (`node .gitnexus/run.cjs analyze`) @ `f8561bf` | PASS — `lastCommit` = `f8561bf0a88b18a941fc24623b52a93900e17005` |
| `detect-changes --scope all` @ `f8561bf` | PASS — `No changes detected.` |

**R3 evidence location:** PR #62 body only.

**Stale evidence note:** r2 @ `b7d346b` and premature finish-work @ `5670f14` do **not** cover `f8561bf`.

### R2 DDD archive (task.py)

| Check | Result |
|---|---|
| `task.py archive 09-11-dsh-sbtd-t15-sbtd-command-ddd --skip-branch-validation` | PASS → `archive/2026-09/09-11-dsh-sbtd-t15-sbtd-command-ddd/` |
| Archived `task.json` `status` / `completedAt` | `completed` / `2026-09-11` |

### Unit / type / fence

- typecheck: PASS
- build: PASS
- t15: 12/12; full suite: 322/322
- forbidden src rewrite: none

## Review / check

| Round | HEAD | Verdict | Notes |
|---|---|---|---|
| r1 | `a83ffd07` | **block** | REQUIRED_CHANGES R1–R4 |
| r2 | `b7d346b` | **STALE** | Superseded by `f8561bf` test/trellis changes — do not credit |
| r3 | `f8561bf` | **CLEAN** | Quality pass (after GitNexus re-bind) + Security pass |

- Finish-work @ `5670f14` was **reverted**; task restored `in_progress` pending proper finish-work after r3.

## GitNexus

HEAD-bound analyze/detect @ `f8561bf` recorded in PR #62 body. No tracked task-file artifact.
