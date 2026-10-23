<p align="center">
  <a href="https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.md">EN</a>
  ·
  <a href="https://github.com/KunoLu/sbtd-plugins/blob/dsh-sbtd-v0.2.0-rc.2/packages/dsh-sbtd/README.zh.md">中文</a>
</p>

# @kunolu/dsh-sbtd

DSH-hosted SBTD workflow adapter with a short Chinese sbtd section, hooks, nine model tools, read-only manuals, and the human `/sbtd` command.

## Requirements

- Target and development host: `@deepseek-ai/dsh@0.2.0-rc.2`.
- `peerDependencies` and `engines.dsh` both declare `>=0.2.0-rc.2 <0.3.0-0`; this docs-only RC does not change that range.
- MCP is optional and degrades when unavailable. Graft queries use an already-wired managed launcher; the plugin does not initialize Graft or write MCP configuration.

With `@deepseek-ai/dsh@0.2.1-rc.2`, npm can report `ERESOLVE` because its default peer resolution does not include cross-patch prereleases. Prefer pnpm or the dsh plugin manager; see the [deployment boundary in CHANGELOG.md](CHANGELOG.md#deployment-boundary).

## Install

Install from dist-tag `next`.

`0.2.0-rc.2` was published to npm on 2026-10-23 17:08:50 +08:00;
both `next` and `latest` point to it. GitHub prerelease:
[`dsh-sbtd-v0.2.0-rc.2`](https://github.com/KunoLu/sbtd-plugins/releases/tag/dsh-sbtd-v0.2.0-rc.2).
The existing `@next` installation guidance is unchanged.

Use `@next`, not the bare package name, `@latest`, or a GitHub path:

```bash
dsh plugin --profile web add @kunolu/dsh-sbtd@next
```

On load, `apply()` registers the short Chinese sbtd section (name `sbtd`, order 50), hooks, all nine tools listed below, and `/sbtd`. Registration does not write user files or `AGENTS.md`. The plugin does not modify the `640-skills` source repository, run `trellis init`, silently install an app/JDK/Maestro, or change the host pin.

## Embedded workflow

`apply()` registers `sbtd_plan`, `sbtd_review`, `sbtd_clarify`, `sbtd_spec`, `sbtd_tickets`, `sbtd_validate`, `sbtd_bdd`, `sbtd_e2e`, and `sbtd_lessons`.

Without a plan, production-code write/edit operations ask for `sbtd_plan` first; README edits are allowed. Under `strict`, applicable required book gates must pass through `sbtd_review`. Under `default`/`lite`, other pending book gates produce notices rather than blocking; full docs-grill DDD remains mandatory in every workflow mode. A missing workflow mode resolves to `default`, not an implicit strict book-gate requirement.

Mode resolution is tool argument / host injection → active-task's `task.md` (read-only) → `default`. Missing or corrupt task data and branch mismatches fall back with a reason. `sbtd_plan`, `sbtd_review`, and `sbtd_validate` return `workflowMode` and `workflowModeSource`; `/sbtd` and hook notices also show the mode and source.

### /sbtd

Human commands (`ctx.commands`, not model tools):

- `/sbtd` — read-only: current Book Gate Plan or `no-plan`, workflow mode/source, and maestro missing summary; installs nothing.
- `/sbtd plan` — shows the session plan or explicitly reports its absence; does not create a plan.
- `/sbtd maestro` — reuses T12 `preflight()`; guidance requires consent before installation, never silent installation.

### sbtd_clarify

The first call must pass `mode`: `docs` (grill-with-docs) or `generic` (grill-me). Later calls inherit it when omitted. Changing mode throws until `reset: true` (Interview Reset). Compaction snapshot restoration preserves mode and `clarifyStatus`; it is not Reset.

Ask one `question` per round. `clarifyStatus=complete` requires both `frontier_empty` and `user_confirmed`; merely reading manuals is not Complete. Partial can proceed without a plan; Complete requires `sbtd_plan` first. docs Complete adds the haystack fact `完整执行 grill-with-docs`, elevates `ddd` to required, and uses the shared `sbtd_review kind=ddd` path. generic Complete does not automatically require DDD. If Complete has a required DDD review that is not `confirmed`, it returns blocked once and no longer suggests PRD/implementation; further clarify calls are not the resume path.

### sbtd_review

`kind` accepts only five values: `legacy`, `refactor`, `ddd`, `ddia`, `release`. Aliases and skill IDs are rejected.

| kind | status values | 3.4 passing state |
|---|---|---|
| `legacy` | `characterized` `needs-safety-net` `seam-required` `blocked` | `characterized` → `passed` |
| `refactor` | `proceed` `refactor-first` `blocked` | `proceed` → `passed` |
| `ddd` | `confirmed` `needs-clarification` `blocked` | `confirmed` → `passed` |
| `ddia` | `confirmed` `needs-design-change` `blocked` | `confirmed` → `passed` |
| `release` | `ready` `needs-mitigation` `blocked` | `ready` → `passed` |

3.4 mapping: `needs-*`, `seam-required`, and `refactor-first` remain `running`; `blocked` maps to `blocked`. The mapping does not change `requirement`.

Example:

```js
await sbtd_review({
  kind: "legacy",
  status: "characterized",
  conclusions: "Safety net in t5-review.test.mjs",
});
```

### Other tools

- `sbtd_plan` builds the session Book Gate Plan. `sbtd_spec` and `sbtd_tickets` return drafts only; they do not write task files. Task-record ownership stays with sbtd-task's TaskStore.
- `sbtd_validate` runs pre/post validation using project tests and optional Graft evidence. Missing Graft is `skipped`, not passed; in strict mode its evidence is unproven. Empty graph results do not prove no impact.
- `sbtd_bdd` supports feature discovery and generation; `sbtd_e2e` supports Web/Mobile test generation and execution with local prerequisites and host-provided trust boundaries. These tools can write selected feature/test/report files; they do not silently install missing dependencies.
- `sbtd_lessons` matches, reads, and records lessons. Identity comes from `.sbtd/developer`, never a guessed name. Writes use the v2 layered store `docs/lessons/{index,topics,archive}` or an existing `docs/spec/lessons.md` short entry; no new short entry is created. Legacy flat `docs/lessons.md` and `.trellis/lessons` remain readable, but recording requires migration rather than automatic conversion.

### Manuals

`manuals/` contains read-only skill text synced from `KunoLu/640-skills` **v2.0.2** (sourceRevision `1d82494d74f6df9bca7dccef2da409f87091883e`). Each skill contributes only `SKILL.md` and its own `references/`. Do not edit manual text by hand.

To resync, supply a local SOURCE directory, or omit it to clone at the pinned SHA:

```bash
packages/dsh-sbtd/scripts/sync-manuals.sh /path/to/640-skills
```

Each `manuals/MANIFEST.json` entry records `sourcePath` (relative to the 640-skills repository), `sha256`, and `sourceRevision`. Missing sources, SHA mismatches, copy failures, or checksum failures exit nonzero.

## Platform support

The package declares no `os` or `cpu` restriction. Runtime support depends on the DSH host and its Node.js environment; this is not a platform certification. The manuals sync script requires Bash. Mobile execution additionally requires the local JDK/Maestro/device/app prerequisites checked by `/sbtd maestro`.

## Publishing an RC release

Publication is separate from this README/version bump. After review and merge, create the annotated tag `dsh-sbtd-v0.2.0-rc.2` on the merge commit, verify both top language links after tagging and before publishing, and create a bilingual GitHub prerelease.

Run package tests, lint, typecheck, and `npm pack --dry-run` before release; the Chinese mirror is linked via the release-tag-pinned URL, and `README.zh.md` ships in the npm package. From `packages/dsh-sbtd`, the release operation is `npm publish --tag next`; leave `latest` untouched. Do not treat a changelog date or local version bump as publication evidence. See [CHANGELOG.md](CHANGELOG.md) and [CHANGELOG.zh.md](CHANGELOG.zh.md) for mirrored release notes.

## Support

Report reproducible issues at <https://github.com/KunoLu/sbtd-plugins/issues>. Include plugin/host versions, workflow mode, and sanitized reproduction steps; do not include credentials or private session contents.

## Data handling and telemetry

The plugin has no telemetry client. Session plan, gate, clarification, and Maestro state live in an in-process map, with explicit serialize/restore support. Registration itself does not write user files; later BDD/E2E/lessons operations can write the project artifacts described above. Task files are read-only to the plugin.

Optional MCP tools and invoked project tests, Playwright, or Maestro may access external systems according to their own configuration. Do not interpret the absence of plugin telemetry as a no-network guarantee for those tools or the DSH host.

## Uninstall and rollback

1. Remove or disable this plugin's `sbtd` entry using the DSH profile/plugin configuration that installed it, then restart the host.
2. Restarting clears the plugin's in-process state; host-managed snapshots are separate. Preserve generated features, tests, reports, and lessons unless you explicitly choose to remove them—unloading the plugin does not delete them.
3. For rollback, restore the previous plugin version through the DSH plugin manager with a compatible host. Older 0.1.x releases have different host and workflow contracts; consult their changelog rather than assuming a drop-in downgrade. This docs-only RC introduces no data migration.

## License

Apache-2.0. See [LICENSE](./LICENSE).
