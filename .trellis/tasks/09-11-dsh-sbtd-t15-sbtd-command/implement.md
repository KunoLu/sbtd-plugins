# Implement — T15 /sbtd human command (R1–R4 fix pass)

## Checklist

- [x] **R1** — Tighten `parseSbtdArgv` to empty/`plan`/`maestro` only; alias/trailing rejection tests
- [x] **R2** — Trellis implement task artifacts (prd, design, implement, jsonl); DDD task archived via `task.py archive 09-11-dsh-sbtd-t15-sbtd-command-ddd --skip-branch-validation`
- [x] **R3** — GitNexus analyze + detect_changes bound to final pushed HEAD (PR #62 body only; no tracked `gitnexus-check.md`)
- [x] **R4** — `features/t15-sbtd-command.feature`; `node:test` titles mirror Chinese `Scenario:` titles (English Gherkin keywords)
- [x] **Phase 2.2 trellis-check** — recorded below (2026-09-11 @ `b7d346b`)
- [x] **/review r2** — CLEAN @ `b7d346b` (2026-09-11); see `/workspace/omp-tasks/t15-pr62-review-r2.md`

## Verification (2026-09-11 @ `b7d346b`)

```bash
cd packages/dsh-sbtd
npm run typecheck
npm run build
node --test test/t15-sbtd-command.test.mjs   # 12/12
node --test test/*.test.mjs                   # 322/322
npm run lint                                  # pre-existing maestro.ts biome issues only
```

R1 proof: `parseSbtdArgv("sbtd")` throws; `parseSbtdArgv("plan")` → `"plan"`; `runSbtdCommand("")` → `no-plan`.

## Check gate results (Phase 2.2 — 2026-09-11 @ `b7d346b`)

### GitNexus (mandatory)

| Step | Result |
|---|---|
| Index refresh (`node .gitnexus/run.cjs analyze`) | PASS — `lastCommit` = `b7d346bfb212f86109f85d888e432d5d96e0aa12` |
| `detect-changes --scope all` | PASS — `No changes detected.` |

**R3 evidence location:** PR #62 body only. Tracked `gitnexus-check.md` was removed in `48753bb` (supersedes stale `fb87a6e` artifact that pinned `05df370` and said “re-run after commit 2”).

### R2 DDD archive (task.py)

| Check | Result |
|---|---|
| `task.py archive 09-11-dsh-sbtd-t15-sbtd-command-ddd --skip-branch-validation` | PASS → `archive/2026-09/09-11-dsh-sbtd-t15-sbtd-command-ddd/` |
| Archived `task.json` `status` / `completedAt` | `completed` / `2026-09-11` (matches T14 DDD pattern) |
| `task.py current --json` | `current_task: null` (active pointer not on DDD task) |

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
| r2 | `b7d346b` | **CLEAN / pass** | Quality pass + Security pass; R1–R4 CLOSED; `/workspace/omp-tasks/t15-pr62-review-r2.md` |

- r1 REQUIRED_CHANGES R1–R4: **CLOSED** on branch; trellis-check gate recorded above.
- **Review convergence:** r2 CLEAN (2026-09-11). PR #62 still OPEN; no merge.
- **Task remains `in_progress`** until `/trellis:finish-work` (archive is separate).

## GitNexus

HEAD-bound analyze/detect recorded in PR #62 body at `b7d346b`. No tracked task-file artifact (avoids stale `lastCommit` after follow-up commits).
