# sbtd-workflow-kit Codegen Workflow

> How `generate`, `check-generated`, and `sync-upstream` fit together. All scripts run through
> `tsx` and are declared in `packages/sbtd-workflow-kit/package.json`.

---

## The Pipeline

`pnpm --filter @kunolu/sbtd-workflow-kit generate` (`src/generate.ts`) runs in a fixed order:

1. `generateKit()` → `generated/` (canonical Kit from `vendor/` + `agents-section-map.yaml` +
   `overlays/`).
2. In parallel: `generateOmpProjection()` → `generated-omp/` and
   `generateAgentPluginProjection()` → `generated-agent-plugin/`.

**Both projections read `generated/` as their canonical input** (`canonicalDirectory:
${packageRoot}/generated`) — they are transforms OF the canonical output, not of `vendor/`.
`generated/` must exist first; do not reorder this in `src/generate.ts`.

Finally `generate.ts` copies `LICENSE` and `THIRD_PARTY_NOTICES.md` out of `generated/` to the
package root.

## The Drift Gate

`pnpm --filter @kunolu/sbtd-workflow-kit check-generated` (`src/check-generated.ts`) regenerates
all three trees into `.{uuid}.check` temp dirs and byte-compares file lists and contents against
the committed trees; any difference throws `KitError("GENERATED_DRIFT")`
(`src/index.ts`, `src/omp-projection.ts`, `src/agent-plugin-projection.ts`). It also compares the
root `LICENSE` / notices against `generated/`.

**Downstream wiring**: `packages/omp-sbtd/package.json` runs
`pnpm --filter @kunolu/sbtd-workflow-kit check-generated` as the FIRST step of the plugin `build`,
before `scripts/embed-kit.mjs`. Stale generated output breaks the sibling package build.

## Inputs vs Outputs

| Inputs (hand-edited) | Outputs (never hand-edited) |
|---|---|
| `vendor/sbtd-workflow-kit-upstream/` | `generated/` |
| `upstream.lock.json` | `generated-omp/` |
| `agents-section-map.yaml` (v2) | `generated-agent-plugin/` |
| `omp-distribution-map.yaml` (v1) | root `LICENSE`, `THIRD_PARTY_NOTICES.md` |
| `overlays/<target>` | |
| `omp-overlays/<canonical-path>` | |

### Adding inputs

- **New upstream AGENTS section** → classify it in `agents-section-map.yaml` (owner /
  splitTargets / omit / replace-with-overlay). Nested (level >2) sections inherit their level-2
  parent's policy and targets. `introducedRevision` (40-hex SHA) gates a classification to the
  pinned source revision that introduced the section (`src/index.ts` `introducedRevisionSchema`).
  Unmapped sections fail generation with `SECTION_UNMAPPED`; unknown mapping keys fail with
  `SECTION_MAPPING_UNKNOWN`.
- **New canonical Kit asset** → add exactly one decision per path to `omp-distribution-map.yaml`;
  `replace-with-overlay` additionally requires `omp-overlays/<same-path>`. Duplicates, stale paths,
  and unclassified assets all fail closed (`resolveDecisions` in `src/omp-projection.ts`).
- Classification is exhaustive by design: every canonical asset must have exactly one decision;
  unknown assets never pass silently.

## Upstream Promotion (`sync-upstream`)

`pnpm --filter @kunolu/sbtd-workflow-kit sync-upstream -- --plan|--apply --source-root <dir>
--revision <sha> [--plan-digest <d>]` (`src/sync-upstream.ts`):

- `--plan` is **zero-write**: stages everything in a temp dir, `git archive`s the requested
  committed SHA from a local clone whose `origin` must normalize to the lock's
  `canonicalSourceUri`, regenerates all three trees, re-embeds into a staged copy of
  `packages/omp-sbtd` (`scripts/embed-kit.mjs` + `scripts/p0/write-sbom.ts`), and returns a
  deterministic `planDigest` binding every input digest.
- `--apply` requires the matching `--plan-digest` (`STALE_PLAN` otherwise), refuses when
  promotion-owned paths are dirty in git (`PROMOTION_DESTINATION_DIRTY`), and applies with
  backup + rollback (`TRANSACTION_FAILED` with `cause` and `rollbackCause` on double failure).
- Promotion may only replace paths listed in `PROMOTION_OWNED_PACKAGE_PATHS` /
  `PROMOTION_OWNED_PLUGIN_PATHS` (`src/sync-upstream.ts`).
- The vendored runbook
  (`vendor/sbtd-workflow-kit-upstream/docs/assets/omp-sbtd-upstream-sync-runbook.md`) explicitly
  forbids hand-copying vendor/lock/plugin kit to simulate a promotion.

## Write Mechanics (all generators)

Every output write is an **atomic directory replacement**: build into `.{uuid}.stage`,
`rename(output, .{uuid}.previous)`, `rename(stage, output)`, `rm(backup)`; on failure restore the
backup or remove the stage (`generateKit` in `src/index.ts`; same pattern in both projection
modules). Never write output files in place.

## Determinism Requirements

Generation must be byte-reproducible — tests assert it (`test/omp-projection.test.ts` generates
twice and compares manifest bytes):

- Recursive file listings are sorted (`listFiles` in `src/index.ts`).
- Digest maps are sorted with `localeCompare` before hashing; path/digest pairs joined with `\0`.
- JSON is written with 2-space indent + trailing newline.
- Manifests use POSIX paths on every OS (`portablePath` in `src/agent-plugin-projection.ts`).

## The `codex` Token Gate

Every path and payload emitted into the OMP projection is scanned case-insensitively for the token
`codex` (latin1 byte scan so binaries cannot smuggle ASCII, `src/omp-projection.ts`). The single
exemption is the canonical `onboard/runtime/scripts/onboard.py`, and only when its bytes exactly
match the digest the canonical manifest declares for that path. Violations throw
`PROJECTION_FORBIDDEN_TOKEN` with **paths only, never payload content**. Check this before adding
any file or text that reaches `generated-omp/`.
