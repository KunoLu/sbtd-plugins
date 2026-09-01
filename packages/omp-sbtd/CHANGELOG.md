# Changelog

All notable changes to `@kunolu/omp-sbtd` are documented here. The format
follows Keep a Changelog; versions are release candidates until promotion.

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

## [0.1.0-rc.12] - 2026-08-18

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

## [0.1.0-rc.11] - 2026-08-17

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

## [0.1.0-rc.10] - 2026-08

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
