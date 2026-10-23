# Changelog

All notable changes to `@kunolu/omp-sbtd` are documented here. The format
follows Keep a Changelog; versions are release candidates until promotion.

Full Chinese mirror: [CHANGELOG.zh.md](CHANGELOG.zh.md).

## [0.2.0-rc.2] - 2026-10-23

### Breaking

- **Host event evidence v2.** The current contract and evidence profile are
  `omp-extension-v2` / `omp-host-events-v2`. Evidence consumers must use v2;
  historical v1 ledger records remain read-only and are not relabeled as v2.
- **Required handoff proof.** `session_compact` is now a required Host Event:
  13 required events plus 1 optional event make 14 subscriptions. A successful
  handoff must be proven by a correlated `session_compact` with
  `compactionEntry.method === "handoff"`. A missing method or competing compact
  in the window fails; `HANDOFF_EVENT_UNOBSERVABLE` is a hard failure again.

### Changed

- Renamed the Chinese README from `README_zh.md` to `README.zh.md` and included
  it in the npm package, with both language links pinned to the rc.2 release tag.

Sources: [#123](https://github.com/KunoLu/sbtd-plugins/pull/123) (implementation)
and [#122](https://github.com/KunoLu/sbtd-plugins/pull/122) (contract decisions).
This entry's date records preparation, not publication.

## [0.2.0-rc.1] - 2026-10-22

### Breaking

- No longer supports omp 17.x; tested only on 18.11.1; as of the D11 lock on 2026-10-19, upstream latest was 18.12.2
- Unversioned installs (`omp plugin install @kunolu/omp-sbtd`) now resolve to
  0.2.0-rc.1, because npm dist-tags `latest` and `next` both point to it;
  it requires omp `>=18 <19`. omp 17.x users must explicitly pin an older
  0.1.x version.

### Added

- **Expanded onboard runtime bundle.** Includes all 33 upstream Python
  scripts, nine runtime assets, `onboard-contracts.schema.json`,
  `upgrade.schema.json`, and the `sbtd-task` template tree (eight template files, plus LICENSE and NOTICE).
- **Python dependency preflight.** Ships `kit/onboard/runtime/requirements.txt`
  with five pinned dependencies: `jsonschema`, `PyYAML`, `markdown-it-py`,
  `tomlkit`, and `cryptography`. Recognized dependency-requiring SBTD
  Python commands, including upgrade and migration, are checked in isolation
  before execution and fail closed if any dependency is missing; signature
  verification refuses to run without `cryptography`. No automatic
  installation or skipped fallback. Standard-library-only onboard commands
  remain usable; this host guard is not a general shell sandbox.
- **Install-path host smoke.** Verified the packed plugin on omp `18.11.1`
  through installation and discovery via `omp.extensions`, real command,
  tool and hook registration, and project onboard. This is smoke evidence,
  not model end-to-end testing or full host-event certification.

### Changed

- **Kit ownership.** Moved sync, projection and generation into
  `packages/omp-sbtd/scripts/` and `packages/omp-sbtd/upstream/`, then
  deleted the private `packages/sbtd-workflow-kit` workspace package.
  Supply-chain `sourceId` remains `sbtd-workflow-kit-upstream`.
- **Upstream sync.** Updated to `640-skills` `v2.0.2`
  (`1d82494d74f6df9bca7dccef2da409f87091883e`) with
  `transformVersion: p0-v4`. Both embedded AGENTS templates now use that
  revision; third-party notices were regenerated.
- **Canonical runtime projection.** Expanded the `PROJECTION_FORBIDDEN_TOKEN`
  exemption from `onboard.py` to the canonical onboard runtime Python
  scripts, assets and two schemas. Content remains digest-bound to the
  canonical manifest; overlays cannot use the exemption for non-canonical
  content.
- **Portable Skill candidates.** Removed the deleted upstream
  `trellis-workflow` candidate; missing candidates still fail closed.
- **Onboard Skill catalog.** Replaced `skill:trellis-workflow` and
  `skill:trellis-channel` with `skill:sbtd-task`.
- **omp 18 host contract.** The peer range is `>=18 <19`, with the development
  dependency pinned to `18.11.1`. Event schemas accept `session_branch`
  reasons `branch`, `fork`, `btw` and `session_switch` reasons `new`,
  `resume`, `fork`.
- **v2.0.2 task routing.** The optional `trellis` capability now maps to
  `sbtd-task`, without requiring `.trellis/workflow.md` for Skill readiness.
  Read-only task observation recognizes `in-progress` and `checking` records
  under `ai/tasks/**` and `.sbtd/tasks/**`; legacy `.trellis` observation
  remains read-only. Task state writing stays with sbtd-task.

### Known limitations

- **Handoff evidence on omp 18.x.** Handoff is not observable as
  `session_switch`. The p0 host-event live cell temporarily records
  `HANDOFF_EVENT_UNOBSERVABLE` as a diagnostic rather than a hard failure.
  A registered follow-up will first update the PRD, then implement
  `session_compact` observation in a separate code PR and restore the hard
  failure for missing handoff evidence after that code PR merges.

## [0.1.0-rc.14] - 2026-09-01

### Changed

- Synced embedded Kit from `640-skills` `v1.0.13` (`f8aa0d7225a26c5e00b81d2f1b05121108e63630`) via workflow-only `sync-upstream`.
- Updated OMP distribution map for new stable assets (ponytail, ui-ux-pro-max) and AGENTS section map for upstream renames.
- Retargeted `docs/assets/omp/sbtd-workflow-onboard-to-omp-plugin-sync.md` from KPi to sbtd-plugins package paths.

## [0.1.0-rc.13] - 2026-08-27

Widened-peer RC published to npm `next` after cloud §4 run `33052112414`.
Registry SHA-256 `b0e1f1332c3d9d5799423ab23ae1936b05efeb492cfb3ff65131c146b3028185`.
Not `certified`. The candidate envelope tarball `61610988…f9c7` is a
different pre-publication pack and is not the Registry identity.



### Changed

- The peer dependency on `@oh-my-pi/pi-coding-agent` is widened from exact
  `17.3.5` to the range `>=17.3.5 <18`. The development dependency and the
  lockfile-installed OMP stay exact `17.3.5`; OMP 18 remains out of range.
- Compatibility Policy v2 (`validation/p0/compatibility.v2.json`) is the
  packaged installability contract and is listed in `package.json` `files`.
  Target catalog, ledger, and evidence stay repository-side and are not packed.
  The v1 exact-current policy file and semantics are removed.
- Compatibility certification (`published` / `installable` / `certified`)
  stays decoupled from npm publication: the release validator derives the
  overall compatibility state from trusted profile evidence only, and that
  state never authorizes or blocks publication.

## [0.1.0-rc.12] - 2026-08-20

Hybrid Plugin M2 package assembly candidate. Published to npm under the
`next` dist-tag on 2026-08-20 after the handbook §4 isolated exact-tarball
four-command acceptance; the Registry tarball SHA-256 is
`49edb4b7cab68f851359179b2c27bb53be8eff5682f16285f5caf9a351c39a33`. Its peer
dependency stays exact `17.3.5` and its identity remains immutable; its
compatibility certification state starts at `eligible` and the four-command
result is retained only as a Command Surface baseline.

### Added

- Root `plugin.json` (Agent Plugins schema 1.0.0) with the standard field set
  from the migration plan §5. `plugin.json.version` is the single version
  fact and equals `package.json.version`.
- Root `skills/**`: the certified portable Skill projection
  (`generated-agent-plugin/skills/**`, Workflow Kit `4222b15`,
  `transformVersion=agent-plugin-p0-v1`, `certifiedCount=12`, digest
  `e97e283c…`) copied at build time by `scripts/embed-agent-skills.mjs`.
  The copy is build-owned and digest-verified against the Kit manifest;
  hand edits, missing or extra directories, and symbolic links fail the
  build. `trellis-workflow` stays onboard-owned;
  `sbtd-workflow-onboard` and `trellis-channel` remain explicit
  non-candidates and are not packaged.
- `plugin.json` and `skills/**` join the npm `files` whitelist and the SPDX
  SBOM inventory.

### Unchanged

- `kit/**` still embeds only the `generated-omp/**` projection; the portable
  tree is not embedded into `kit/**`.
- `/sbtd` runtime semantics, the exact `@oh-my-pi/pi-coding-agent@17.3.5`
  peer, and the Onboard/Doctor skill sources are unchanged.
- No `mcp.json` and no `commands/`, `hooks/`, `tools/`, or `runtime/` root
  directories are added.

## [0.1.0-rc.11] - 2026-08-18

Next RC candidate. Includes the eight confirmed RC6 findings, the
reviewer follow-up fixes, Workflow Kit `4222b15`, and exact OMP `17.3.5`.

### Fixed (RC6 review findings)

- **P1-01** Tool approvals are typed one-shot descriptors: dependency-install
  and secret-read approvals live in separate risk classes, bind the exact
  SHA-256 input fingerprint, are consumed by the tool result, and never
  interchange or survive deny/replay/turn boundaries.
- **P1-02** The deterministic task classifier is multilingual (EN/ZH/JA):
  per-line instruction detection (context-before-instruction), case-fixed
  `Review`, JA change-intent/bug vocabulary (`不具合`, `バグ`, `障害`,
  `修正してください`, `レビュー`), ZH `问题/故障/错误`, and a versioned
  synthetic regression corpus. `/sbtd route` override is unchanged. The
  NeoX 100+ production corpus remains deferred promotion evidence.
- **P1-04** BDD delivery evidence no longer uses `.feature` file mtimes. A
  version-aware observer runs the promoted Kit
  `validate_validation_evidence.py` (SHA-pinned from the embedded manifest)
  with repository revision binding; v1 envelopes never satisfy BDD scenario
  traceability; specification presence and execution evidence are reported
  separately.
- **P1-06** `release-readiness ready` is derived from a verified, current,
  exact-revision evidence observation and a persisted hash-bound descriptor —
  never from a caller-supplied boolean. A later repository mutation invalidates
  that descriptor and resets the gate to `planned`.
- **P2-01** A capability registry decides tool blocking: safe diagnostics
  (read/grep/glob/lsp/ast_grep/debug/recall/web_search/todo/ask) stay
  available in preflight-only/blocked states; unknown tools and remote
  (`ssh://`) locators fail closed.
- **P2-02** Dependency mutation detection covers npm/pnpm/yarn/bun, pip/uv,
  cargo, brew, go, npx/bunx, dotnet, nuget, choco, winget, composer, and
  PowerShell `Install-Package`, including `powershell`/`pwsh` `-Command` and
  `-CommandWithArgs` wrappers, across `&&`, `;`, `|`, and newlines, with
  `sudo`/`corepack` prefixes. Pure queries (`npm ls`, `pip show`, `go list`)
  are not flagged.
- **P2-03** The secret inventory expanded to `.envrc`, `.netrc`,
  `.git-credentials`, `.npmrc`, `.pypirc`, Docker/Kube/AWS/Azure/gcloud
  credentials, `*.p12/pfx/keystore/jks`, usersecrets, and redirect/git-show
  read forms. Public certs, `.env.example`-style templates, `appsettings.*`
  and public keys are observable mixed assets, not hard blocks.
- **P3-01** Package metadata (repository/bugs/homepage), SECURITY.md, this
  changelog, and README support/data-handling/uninstall sections now ship in
  the tarball.

### Changed

- Public OMP target is exact `17.3.5`. `17.2.9` is historical. `17.3.5`
  stays `unverified` until isolated four-command acceptance passes;
  publication remains blocked until then.

### Fixed (post-implementation review)

- Missing `jsonschema` is `VALIDATOR_UNAVAILABLE` (fail-closed). The
  embedded Skill ships `requirements.txt`. Kit lock is `4222b15`.
- Staged promotion copies `SECURITY.md` and `CHANGELOG.md` so SBOM
  inventory matches the declared package files.

## [0.1.0-rc.10] - 2026-08-14

- Prior RC. Workflow Kit was later rebound from `078267f` to `4222b15` in
  0.1.0-rc.11.

### Migration notes

- Sessions predating this release keep `stateVersion = 1`; an optional
  `validationEvidence` descriptor field is additive and ignored by older
  readers.
- Hosts that relied on "touch any .feature file to unblock delivery" must now
  produce a v2 evidence envelope (see the project-validation skill's
  validation-evidence contract references) verified against the current
  commit.
- Recording `release-readiness ready` no longer survives a later write/edit;
  re-observe current evidence before advancing.
- Validator hosts need `jsonschema` (`python3 -m pip install -r
  requirements.txt` from the installed `project-validation` Skill root).

## [0.1.0-rc.6] - 2026-08-06

### Changed

- Pinned the OMP peer to `17.2.9` (from `17.1.3` in rc.2).
- Published the 253-file candidate whose tarball matches the archived
  isolated OMP `17.2.9` four-command acceptance record.
- Other changes: Published; change details not recoverable.

## [0.1.0-rc.2] - 2026-07-28

### Added

- Package README with installation and compatibility guidance. Compared
  with rc.1, the published tarball adds only `README.md` and changes only
  `package.json` and `SBOM.spdx.json`; runtime files are unchanged.

## [0.1.0-rc.1] - 2026-07-28

### Added

- Initial npm release of the OMP SBTD plugin, including `dist/extension.js`,
  the embedded workflow Kit, and SPDX SBOM (356 files).
- Exact peer dependency on `@oh-my-pi/pi-coding-agent@17.1.3`.
