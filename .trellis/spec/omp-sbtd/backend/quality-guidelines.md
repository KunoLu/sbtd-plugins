# omp-sbtd Quality Guidelines

> Style and IO conventions across `src/`, `test/`, and `scripts/`. Enforced by Biome
> (`biome check src test scripts` — scripts are linted too) and `tsc`; the rest is strong
> precedent.

---

## Style

- 2-space indent, double quotes, semicolons (Biome, root `biome.json`).
- **kebab-case string enums for all domain vocabulary**: route ids, gate ids, rule ids, reviewer
  statuses, tool capabilities, reason codes (`user-visible-behavior`,
  `missing-required-capability:...`).
- SCREAMING_CASE exported constants for budgets/keys: `SBTD_STATE_CUSTOM_TYPE`,
  `SBTD_STATE_COMPACTION_KEY`, `MAX_RENDERED_SBTD_REPORT_BYTES` (32 KiB),
  `MAX_REPORT_TOOL_EVIDENCE_RECORDS` (24), `MAX_ENVELOPE_BYTES` (256 KiB).
- Pervasive immutability: `readonly` fields, `Readonly<Record<…>>`, `as const` tables; transforms
  return new objects/arrays (see [Type Safety](./type-safety.md#immutability)).
- Src imports use `.js` suffixes (NodeNext); tests import `.ts` sources. Named exports; the single
  default export is the extension entry itself (`src/extension.ts`).

## Comments

Design-rationale comments are dense and cite provenance. Two recurring forms to match:

- Slice/task markers explaining why something changed or was removed:
  `// P1-04: the mtime-based hasFreshBddCoverage heuristic was removed...` (`src/extension.ts`).
- `// Trace: packages/omp-sbtd/features/<file>.feature` Rule citations where code implements a
  feature Rule (`src/runtime/omp-extension-v1.ts:8-10`).

Comment invariants and provenance, not mechanics.

## IO and Logging

- **No `console.*` anywhere in `src/`; no `process.exit` in `src/`.** User-facing output goes
  through `ctx.ui.notify(message, "info" | "warning")` (`src/extension.ts:1472-1485`).
- **No network calls, no telemetry** (README "Data handling and telemetry").
- File IO behind `FileAdapter` (`src/onboard/index.ts`):
  `readText/writeAtomic/makeDirectory/exists/remove/isSymlink`; `createNodeFileAdapter()` is the
  production implementation. Writes are atomic and journaled (`transactionJournalSchema`). Domain
  code takes a `FileAdapter`; it never imports `node:fs` directly.
- Process execution behind injected adapter interfaces with explicit timeouts — see
  [Security Invariants](./security-invariants.md#filesystem-and-process).
- Time is injected (`now: () => string`); see [Testing](./testing.md#filesystem-and-time).

## Registry and State Rules

- No implicit registry mutation — `setRuleEnabled` returns a new array; gate transforms are pure
  functions returning new arrays.
- No mtime/heuristic evidence — removed deliberately; BDD evidence derives exclusively from the
  validation evidence observer (`// P1-04` comment in `src/extension.ts`): an unrelated `.feature`
  touch never satisfies BDD.
- No silent swallowing: every catch records a blocked/degraded state with a repair path or returns
  `block: true` (see [Error Handling](./error-handling.md)).

## Anti-Patterns (observed as consistently avoided)

- No `exports` map sprawl, no secondary entry points — one extension entry.
- No state outside the host session log; no global config files written by the plugin.
- No new runtime dependencies — `zod` is the only one. Check
  [Directory Structure](./directory-structure.md#layout) before assuming a capability needs a new
  module; extend the owning module first.
- No React/UI/database patterns anywhere — this is a host extension; the frontend template guides
  were removed because they do not apply.

## Verification

```bash
pnpm --filter @kunolu/omp-sbtd lint        # biome check src test scripts
pnpm --filter @kunolu/omp-sbtd typecheck   # tsc --noEmit
pnpm --filter @kunolu/omp-sbtd test        # typecheck + serial vitest
pnpm --filter @kunolu/omp-sbtd build       # full chain — NOT bare tsc
pnpm --filter @kunolu/omp-sbtd smoke       # dist smoke against hand-rolled host
```
