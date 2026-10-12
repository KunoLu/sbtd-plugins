# omp-sbtd Build and Release

> Build chain, build-owned artifacts, version facts, and publish surface for
> `@kunolu/omp-sbtd`.

---

## Build Chain (order matters)

`pnpm --filter @kunolu/omp-sbtd build` runs, in order:

```
pnpm --filter @kunolu/sbtd-workflow-kit check-generated
  && node scripts/embed-kit.mjs
  && node scripts/embed-agent-skills.mjs
  && node scripts/clean-dist.mjs
  && tsc -p tsconfig.json
  && tsx scripts/p0/write-sbom.ts
```

- The kit drift gate runs FIRST — stale `generated-omp/` output in the sibling package fails this
  build before anything is embedded.
- `scripts/embed-kit.mjs` copies the kit's `generated-omp/` projection into `kit/`, validates
  manifest/asset digests, enforces the zero-Codex token scan, and installs via atomic staged
  rename. Env overrides exist (`KPI_KIT_SOURCE`, `KPI_EMBED_DESTINATION`, …) for tests.
- `scripts/embed-agent-skills.mjs` copies the certified 12-skill projection into root `skills/`,
  digest-verified against the kit manifest. Hand edits, extra dirs, or symlinks fail the build
  (CHANGELOG rc.12).
- `clean-dist.mjs` → `tsc` (outDir `dist`, rootDir `src`; extends `../../tsconfig.base.json`) →
  SBOM via `scripts/p0/write-sbom.ts`.

**Always run the full `pnpm build`, never bare `tsc`**, when you need a real `dist/` — embedding
and SBOM are part of the artifact contract.

## Build-Owned Artifacts (never hand-edit)

`kit/`, `skills/`, `SBOM.spdx.json`, `dist/`. `kit/manifest.json` carries per-asset sha256;
`test/kit-stable-provenance.test.ts` and `test/kit-embedding.test.ts` enforce the binding. Change
the inputs in `@kunolu/sbtd-workflow-kit` and rebuild instead.

## Version Facts

- **`plugin.json` `version` === `package.json` `version`** — CHANGELOG calls `plugin.json.version`
  "the single version fact". Bump both together.
- `src/version.ts` `getPluginVersion()` reads `../package.json` via `new URL(...,
  import.meta.url)` — one relative path serves both `src/` (dev/tests) and `dist/` (packed)
  layouts. It falls back to `"unknown"` and never throws. Preserve both properties when editing.
- Peer range vs dev pin split is intentional: peer `>=17.3.5 <18` (OMP 18 out of range),
  devDependency + lockfile exactly `17.3.5`.

## published / installable / certified Are Distinct

- `validation/p0/compatibility.v2.json` is the packed installability contract (in `files`).
- Targets/ledger/evidence (`compatibility-targets.v1.json`, `compatibility-ledger.v1.json`,
  `validation/p0/evidence/`) stay repo-side and are NOT packed.
- The compatibility ledger is **append-only with revocation** (`p0-conformance-release.feature`
  Rule "认证历史只可追加且独立于 npm 发布"); certification never gates npm publication, and
  publication never implies certification.

## Publishing (human-run, documented in README)

- RCs publish only to the `next` dist-tag, via `docs/deploy/publish-omp-sbtd.sh` — the only
  approved Registry writer. It rejects stable versions, other packages, `latest`, occupied
  versions, and unknown Registry availability before calling `npm publish`.
- `NPM_TOKEN` resolves from root `.env` (parsed as data, never sourced) or the inherited
  environment; the helper never prints or accepts a token argument.
- Before publishing, run the isolated exact-tarball four-command acceptance (`/sbtd help`,
  `/sbtd status`, `/sbtd report`, `/sbtd onboard plan`) per
  `docs/assets/omp/omp-plugin-host-acceptance.md`.

## CI Trust Boundary

`.github/workflows/omp-compatibility-*.yml` implement the certification pipeline. Key invariants
(documented in the workflow headers): fail-closed guard outside `refs/heads/main`; third-party
actions pinned to full commit SHAs; subject tarballs installed only via `npm ci --offline` from a
staged lock+cache; no job fakes a passed/certified result; no job publishes npm or moves dist-tags.
Treat these workflows as security-sensitive code — changes need the same care as
`scripts/p0/`.
