# omp-sbtd Directory Structure

> Real layout of `packages/omp-sbtd/` and how the modules fit together.

---

## Layout

```
packages/omp-sbtd/
├── package.json                # main: dist/extension.js; host discovery via "omp"/"pi" blocks
├── plugin.json                 # Agent Plugins 1.0.0 manifest; version == package.json version
├── src/
│   ├── extension.ts            # single entry (~3000 lines): all host handlers + /sbtd dispatch
│   ├── version.ts              # getPluginVersion() reads own package.json (dual src/dist layout)
│   ├── runtime/index.ts        # registerRuntimeController: host registration seam
│   ├── runtime/omp-extension-v1.ts  # versioned host capability/event inventory + edge validator
│   ├── commands/index.ts       # declarative /sbtd command spec table + parser/completion/help
│   ├── workflow/index.ts       # task facts schema + deterministic classifier (Route)
│   ├── gates/index.ts          # book gate state machine (5 gates, pure transforms)
│   ├── rules/index.ts          # 11-rule typed registry + evaluator
│   ├── tool-risk/index.ts      # tool capability registry, shell analysis, approval book
│   ├── environment/index.ts    # evaluateEnvironment/evaluateProfileEnvironment
│   ├── environment/accepted-skip.ts   # AcceptedSkip records
│   ├── environment/tool-evidence.ts   # per-tool evidence probes/records/store
│   ├── state/index.ts          # session state schema + StateService over the session log
│   ├── evidence/index.ts       # validation-evidence envelope observer (v1/v2)
│   ├── report/index.ts         # zod report schemas, build/render/parse round-trip
│   ├── onboard/index.ts        # FileAdapter, OnboardService, transaction journal
│   ├── onboard/composite.ts    # CompositeOnboardService
│   ├── onboard/python-runtime.ts # canonical onboard.py subprocess runtime
│   ├── kit/index.ts            # embedded kit loader + digest verification
│   ├── kit/manifest.ts         # EmbeddedKitManifestV2 + verifyEmbeddedKitManifest
│   ├── agents/index.ts         # AGENTS.md managed-block targets, drift inspection, merge
│   └── skills/index.ts         # packaged skill inventory, certified cleanup, doctor block
├── test/                       # 45 *.test.ts + classifier-corpus.ts + fixtures/
├── features/                   # 8 Chinese Gherkin .feature files (behavior source of truth)
├── scripts/                    # build/embed/smoke .mjs + scripts/p0/*.ts release validator suite
├── kit/                        # BUILD-OWNED embedded kit snapshot — never hand-edit
├── skills/                     # BUILD-OWNED 12 certified portable skills — never hand-edit
└── validation/p0/              # compatibility policy/ledger/conformance JSON
```

## Single-Entry, Handler-Object Architecture

All host behavior lives in `src/extension.ts`, whose tail registers one handler object via
`registerRuntimeController(pi, { complete, handleCommand, transitionStage, reobserve,
beforeAgentStart, beforeToolCall, preserveCompaction, approvalResolved, toolResult,
credentialDisabled, turnStart, turnEnd, sessionStop })`.

Extend the extension by adding a handler (plus, when needed, an inventory entry in
`omp-extension-v1.ts`) — never by side-stepping the probe. `src/runtime/index.ts` runs
`probeOmpExtensionV1Capabilities(pi)` and **throws before any registration** when a required
capability or event is missing: a host lacking the contract never gets a `/sbtd` command, tool, or
event subscription.

Per-session mutation is serialized: `serialize(ctx, op)` chains promises keyed by
`sessionKeyFor(ctx)` so concurrent host events for one session never interleave.

Package surface notes:

- **No `exports` map.** Host discovery is via `"omp": { "extensions": ["./dist/extension.js"] }`
  (and an identical `"pi"` block). One entry point only — do not add secondary entry points.
- Runtime dependencies: **only `zod: 4.1.12`**. peerDependencies declare the host range
  `@oh-my-pi/pi-coding-agent >=17.3.5 <18`; devDependencies pin the same host exactly at `17.3.5`.
  That split (range for consumers, exact pin for development) is intentional.
- Publish surface is the `files` whitelist: `dist`, `kit`, `plugin.json`, `skills`, two explicit
  `gitignore.template` paths, legal/docs files, `validation/p0/compatibility.v2.json`.

## Registries as Data

The package's dominant organization idiom: **readonly const table + pure evaluator functions**.
Behavior is added by adding a table entry and an evaluator branch — not by scattering conditionals
through `extension.ts`.

| Registry | Location | Evaluator(s) |
|---|---|---|
| `definitions` (5 book gates) | `src/gates/index.ts` | `createBookGatePlan`, `startBookGate`, `recordBookGateReview`, … |
| `ruleRegistry` (11 rules) | `src/rules/index.ts` | `evaluateRuleRegistry`, `setRuleEnabled` |
| `sbtdCommandSpecs` | `src/commands/index.ts` | `parseSbtdCommand`, `completeSbtdCommand`, `suggestSbtdCommand`, `renderSbtdHelp` |
| `builtinToolCapabilities` | `src/tool-risk/index.ts` | tool capability lookup + shell analysis |
| `ompExtensionV1Inventory` | `src/runtime/omp-extension-v1.ts` | `probeOmpExtensionV1Capabilities`, `validateOmpExtensionV1Event` |

The command table is the source for parsing, completion, help text, and dispatch simultaneously —
help, completion, and handlers cannot drift apart. Keep it that way: one `SbtdCommandSpec`
definition per command (`path`, `aliases`, `category`, `summary`, `usage`, `examples`, `mutates`,
`requiresConfirmation`, `availableIn`).

## Module Rules

- `extension.ts` orchestrates; domain logic lives in the module directories. When `extension.ts`
  grows a decision that is not host-event plumbing, move it into the owning module.
- Src imports use `.js` suffixes (NodeNext): `from "./workflow/index.js"`. Tests import `.ts`
  sources directly (see [Testing](./testing.md)).
- `scripts/p0/` is first-class tested source (e.g. `release-validator.ts`), imported directly by
  `test/p0-*.test.ts` and executed via `tsx` — treat it with the same standards as `src/`.
