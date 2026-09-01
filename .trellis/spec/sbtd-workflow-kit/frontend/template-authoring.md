# sbtd-workflow-kit Template Authoring

> Rules for the authored text artifacts that drive generation: upstream AGENTS templates, the
> section map, and overlays. Transform code: `packages/sbtd-workflow-kit/src/index.ts`
> (`AGENTS_SOURCES` at :19-22, `TARGETS` at :23-27, section transform in
> `parseSections`/`assignmentsFor`/`render*`).

---

## Two Sources, Three Targets

Two upstream templates (`AGENTS.global.md`, `AGENTS.project.md`) are split into sections and
reassembled into three committed targets (`AGENTS.global.md`, `AGENTS.project-root.md`,
`AGENTS.project-omp.md`) according to `agents-section-map.yaml` (schemaVersion 2).

## Section Mapping Rules

- Every section must be classified exactly once: `include` (with `owner` or `splitTargets`),
  `omit`, or `replace-with-overlay`. Unmapped sections fail generation with `SECTION_UNMAPPED`;
  unknown mapping keys fail with `SECTION_MAPPING_UNKNOWN`.
- **Nested (level >2) sections inherit their level-2 parent's policy and targets** — classify the
  level-2 section, not every descendant.
- `introducedRevision` (40-hex SHA) gates a classification to the pinned source revision that
  introduced the section: it applies only while that exact revision is pinned, is ignored for an
  earlier pinned source, and fails closed once the revision is pinned. Use it when upstream adds a
  section you are not ready to classify for older baselines.
- Cross-field shape is schema-enforced: include requires exactly one of `owner` or `splitTargets`
  (`src/index.ts:118-126`).

## Overlay Rules

- A `replace-with-overlay` policy requires the overlay file at `overlays/<target>` (Kit level) or
  `omp-overlays/<canonical-path>` (OMP projection). Missing overlay → `SECTION_OVERLAY_MISSING` /
  `PROJECTION_OVERLAY_MISSING`.
- **No leakage**: after overlay append, omitted/replaced upstream sections must not appear
  verbatim in any rendered target — `assertExcludedSectionsAbsent` (`src/index.ts:798-833`)
  enforces this. If it fails, the map or overlay text is wrong; do not weaken the check.
- **Single writer per path**: derived outputs (e.g. `THIRD_PARTY_NOTICES.md`, embedded stable
  manifest/notices) must have their canonical counterparts `omit`-ted so exactly one writer owns
  each path (`DERIVED_OUTPUTS` check, `src/omp-projection.ts:38-44, 495-503`).

## Editing Upstream Templates

Templates under `vendor/` change **only** via `sync-upstream --plan → --apply` — never by hand
(see [../backend/codegen-workflow.md](../backend/codegen-workflow.md#upstream-promotion-sync-upstream)).
Overlay files and the maps are the hand-edited surface.

## Language

Upstream templates and overlays are predominantly Chinese; keep an edited section's existing
language. Feature files are Chinese Gherkin with English structural keywords
(`Feature`/`Rule`/`Scenario`) — mirror that mix when adding scenarios.
