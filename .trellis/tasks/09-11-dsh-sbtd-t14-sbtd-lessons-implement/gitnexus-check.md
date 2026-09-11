# GitNexus check gate — T14 (2026-09-11)

Session: `python3 ./.trellis/scripts/task.py current --json` → `session:dsh-sbtd-t1`

## 1. Index freshness

**Before refresh** (`list_repos`):

| Field | Value |
|---|---|
| indexedAt | 2026-09-11T03:34:30.861Z |
| lastCommit | `6fadd16b8a1d042baef5bcc8ef3542ac452fd6c7` |
| HEAD | `3ef2c0eabc6986e0aafc6aae209b9127912f40ce` |
| staleness | **2 commits behind** |

**Refresh command:**

```bash
cd /workspace/sbtd-plugins && node .gitnexus/run.cjs analyze .
```

**Refresh result:** success (21.6s incremental; changed=1 file)

**After refresh** (`list_repos`):

| Field | Value |
|---|---|
| indexedAt | 2026-09-11T03:37:46.221Z |
| lastCommit | `3ef2c0eabc6986e0aafc6aae209b9127912f40ce` |
| nodes / edges / flows | 25,787 / 59,645 / 761 |
| staleness | **0** (matches HEAD) |

## 2. Mandatory pre-commit check (`detect-changes --scope all`)

**Command:**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

**CLI output (verbatim):**

```
3ef2c0eabc6986e0aafc6aae209b9127912f40ce
No changes detected.
```

**MCP `detect_changes` (scope: all):**

```json
{
  "summary": {
    "changed_count": 0,
    "affected_count": 0,
    "risk_level": "none",
    "message": "No changes detected."
  },
  "changed_symbols": [],
  "affected_processes": [],
  "partial": false,
  "truncated": false
}
```

Interpretation: clean working tree at HEAD `3ef2c0e` — no unstaged/staged production edits pending commit.

## 3. PR blast radius (`detect-changes --scope compare --base-ref origin/main`)

**Command:**

```bash
node .gitnexus/run.cjs detect-changes --scope compare --base-ref origin/main --repo .
```

**CLI summary:**

```
Changes: 20 files, 155 symbols
Affected processes: 8
Risk level: high
```

**MCP `detect_changes` (scope: compare, base: origin/main):**

| Field | Value |
|---|---|
| changed_files | 20 |
| changed_count (symbols) | 155 |
| affected_count (processes) | 8 |
| risk_level | high |
| partial | false |
| truncated | false |

**Affected execution flows (complete, 8/8):**

1. RecordLesson → IsDirectory — changed: recordLesson, trellisPresent
2. RecordLesson → IsReadableFile — changed: recordLesson, trellisPresent
3. RecordLesson → IsTrellisOnPath — changed: recordLesson, trellisPresent
4. RecordLesson → TrellisDir — changed: recordLesson, trellisPresent
5. Apply → CreateClarifyTool — changed: apply
6. Apply → CreatePlanTool — changed: apply
7. Apply → CreateReviewTool — changed: apply
8. RecordLesson → HasUnsafePath — changed: recordLesson, resolveTopicSlug, hasUnsafePath

**Production hotspots:** `packages/dsh-sbtd/src/tools/lessons.ts` (new), `packages/dsh-sbtd/src/index.ts` (`apply`, `PluginHost`), `docs/TODO.md`, test whitelist bumps.

**Fence note:** flows touching `IsDirectory`/`IsTrellisOnPath`/`TrellisDir` are **read-only consumers** of T7 `detect()` — `src/backends/trellis.ts` diff vs `origin/main` is empty (Q5A held).

## 4. Process gap (still open)

| Check | Required when | T14 actual |
|---|---|---|
| Pre-edit `impact()` on `apply` / shared symbols | Before editing | **Missed** on `ac5aed6` |
| `detect-changes --scope all` | Before each production commit | **Missed** on `ac5aed6`/`b26d0b9`; **passed post-hoc** @ `3ef2c0e` (empty tree) |

Post-hoc compare HIGH risk is **expected** for new tool + `apply()` registration; it does **not** restore pre-commit timing on `ac5aed6`.

## 5. Verdict

- **GitNexus graph check gate:** PASS (index fresh; `scope all` clean; compare report complete, non-partial)
- **Workflow / merge:** still **NOT ready** — Trellis violations + missed pre-commit on production SHA + parent `/review` pending

## 6. r1 fix pass (2026-09-11)

- Pre-gate `detect-changes --scope all` was **missed** on production SHAs `ac5aed6` and tip `4adb6e3` before the r1 fix; any `scope all` run on this pass is **post-hoc only**.
- Dirty worktree vs CLI/MCP `detect-changes` discrepancy remains: not an unqualified clean pass.
- Trellis implement-before-create / lifecycle ordering gap remains **open** (not closed by r1 code fixes).
