# omp-sbtd Testing

> vitest 4.0.16, serial, no config file. 45 test files bound to Chinese Gherkin features by naming
> convention. Real filesystem, hand-rolled host fakes, no mock framework.

---

## Runner

`pnpm --filter @kunolu/omp-sbtd test` =
`tsc -p tsconfig.json && vitest run --no-file-parallelism --maxWorkers=1 --testTimeout=30000`
(`package.json`). Serial execution is deliberate: tests share real tmpdirs and embedded-kit state.
Do not add a vitest.config or re-enable parallelism without proving isolation.

Note the test script typechecks first — unlike the kit package, `src/` must compile before tests
run.

## Feature → Test Binding

`features/*.feature` (8 Chinese Gherkin files) is the behavior source of truth. Tests adopt
Scenario titles verbatim:

- `describe("Feature: SBTD 运行时工作流与门禁", …)` + `it("Scenario: 可见行为缺少 BDD 在交付前被阻断",
  …)` — see `test/gates.test.ts`, `test/rules.test.ts`, `test/environment.test.ts`.
- Source files back-reference features with `// Trace: packages/omp-sbtd/features/<file>.feature`
  comments citing Rules (e.g. `src/runtime/omp-extension-v1.ts:8-10`).

There is no Gherkin runner; the binding is naming convention + Trace comments. **New behavior
starts as a `.feature` Rule/Scenario; tests mirror the title.**

Mapping (feature → covering tests):

| Feature | Tests |
|---|---|
| `runtime-workflow-gates.feature` | `workflow`, `gates`, `rules`, `tool-risk`, `evidence`, `extension` |
| `sbtd-control-bootstrap.feature` | `environment`, `accepted-skip`, `onboard`, `composite-onboard`, `runtime`, `omp-host-contract` |
| `validation-report-provider.feature` | `report`, `report-command` |
| `omp-distribution-projection.feature` | `kit-security`, `kit-embedding`, `kit-stable-provenance`, `kit` |
| `p0-conformance-release.feature` | `p0-release-validator`, `p0-compatibility-ledger`, `p0-package-release`, `p0-tarball-inspection`, `p0-three-profile-certification`, `p0-authorized-*` |
| `agent-plugin-assembly.feature` | `agent-plugin-manifest`, `agent-plugin-pack`, `agent-skills-embedding` |
| `certified-skill-ownership-m3.feature` | `certified-skill-ownership` |
| `publish-package.feature` | `publish-package` |

(all under `test/`, as `<name>.test.ts`).

## Filesystem and Time

- **Real tmpdirs, no FS mocking**: `mkdtemp(join(tmpdir(), "kpi-...-"))` + `afterEach` `rm -rf`
  cleanup (`test/kit-security.test.ts:13-47`, `test/extension.test.ts`,
  `test/p0-release-validator.test.ts:36-41`).
- **Time is injected**: services take `now: () => string` (`createStateService(adapter, now)`,
  `createOnboardService({…, now})`); tests pin constants like `"2026-07-24T00:00:00.000Z"`. Never
  call `new Date()` inside domain logic — pass `now` in.

## Host Fakes, Not Mock Frameworks

`test/extension.test.ts:24-93` builds a `fillHostEvent` defaults table and a hand-rolled
`hostContract = { zod, registerTool() {} }`; `scripts/smoke-extension.mjs:46-63` implements a full
host context (commands array, events Map, sessionEntries) by hand. `vi` is imported but used
sparingly. When you need a host interaction in a test, extend the hand-rolled fake rather than
reaching for a mocking library.

## Fixtures and Corpus

- `test/fixtures/validation-evidence-v2/<name>/`: 5 `positive-*` + 12 `negative-*` self-contained
  mini projects (`envelope.json` + `features/` + `reports/`). The negative set includes security
  cases — `negative-xxe-doctype`, `negative-xxe-entity`, `negative-xxe-junit`,
  `negative-unsafe-path`, `negative-tampered-hash`, `negative-dangling-locator`,
  `negative-fabricated-label`. Provenance is documented in `test/evidence.test.ts:1-3` (KPi-owned
  copy of upstream fixtures at a promotion revision) — keep provenance headers when adding
  fixtures.
- `test/classifier-corpus.ts`: versioned (`classifierCorpusVersion = 1`) typed entries `{id,
  language: "en"|"zh"|"ja", prompt, expectedRoute, expectedFacts?, riskLevel, source}`. Its header
  scope note states production prompts stay promotion-time evidence and no production-accuracy
  claim is derived from these entries — do not treat the corpus as a production benchmark.
- `test/fixtures/p0-reports.ts`: frozen report text fixtures for `report.test.ts`.

## Assertion Style

- `toMatchObject` / `toEqual(expect.objectContaining(...))` for structural checks;
  `toThrow("must be running")` for invariants.
- `it.each` tables for matrices (`test/tool-risk.test.ts:12-36` tool-capability table;
  `test/evidence.test.ts:70-88` fixture-name table).
- Security assertions reuse helpers like `expectSafeFailure` (`test/kit-security.test.ts:25-38`)
  which additionally assert error messages do not leak local paths.

## scripts/p0 Is Tested Source

`test/p0-*.test.ts` import typed functions directly from `scripts/p0/release-validator.ts` and
`scripts/p0/compatibility-ledger.ts`, executed via `tsx`. Changes to release-governance scripts
require the same test discipline as `src/`.

## Smoke

`pnpm --filter @kunolu/omp-sbtd smoke` runs `scripts/smoke-extension.mjs`: loads
`dist/extension.js` against a hand-rolled host and snapshots a tmp HOME. Use it after touching the
registration seam or command dispatch.
