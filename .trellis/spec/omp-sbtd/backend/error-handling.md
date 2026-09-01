# omp-sbtd Error Handling

> The package uses BOTH throws and result objects. The split is consistent; learn it before adding
> either.

---

## The Split

| Use throws (exceptions) for | Use result objects for |
|---|---|
| Invariant violations (illegal state transitions) | Expected domain outcomes |
| Integrity failures at load/verification time | Classification and evaluation results |
| Host-contract violations at the adapter edge | Missing-but-normal conditions (not found) |

And at the outermost layer: **every host event handler has a fail-closed catch** — exceptions never
escape into the host.

## Pattern 1: Throw on illegal state transitions

`recordBookGateReview` throws `"must be running"` when a review is recorded against a gate not in
`running` (`src/gates/index.ts`; asserted by `test/gates.test.ts` Scenario "Gate 不能由 planned
直接通过"). `setRuleEnabled` throws on unknown or non-configurable rules
(`src/rules/index.ts:236-246`).

## Pattern 2: Throw on integrity failure at load

`loadEmbeddedKitFromDirectory` throws for unsafe asset paths, symlinks, digest mismatch, and
inconsistent catalogs (`src/kit/index.ts:84-160`). `acceptedSkipKitMajor` throws `"Verified Kit has
no supported AcceptedSkip major."` (`src/extension.ts:163`). Callers catch these and degrade to a
blocked state with a repair path — they never proceed on partial trust.

## Pattern 3: Result objects for domain outcomes

- `evaluateRuleRegistry` → `RuleDecision` `{decision, ruleId?, reason?, recovery?}`; precedence
  `allow < remind < interrupt < block-delivery < block-stage < block-tool` picks exactly one winner
  (`src/rules/index.ts`).
- `parseSbtdCommand` → discriminated `ParseResult` (`{kind:"command"…}` / unknown + suggestions)
  (`src/commands/index.ts`).
- `evaluateEnvironment` → `EnvironmentObservation` with `mode:
  "blocked"|"needs-onboard"|"degraded"|"managed"` plus `repairPath` (`src/environment/index.ts`).
- `observeValidationEvidence` → `ValidationEvidenceObservation`, sharing a `notFound` constant for
  the missing-envelope case (`src/evidence/index.ts`).

Result objects carry machine-readable fields (`decision`, `mode`, `ruleId`) and human text
(`reason`, `recovery`) separately. Do not encode outcomes into message strings.

## Pattern 4: Fail-closed catch at the host boundary

Every handler in `src/extension.ts` wraps its body so a thrown error becomes a blocked state, never
a host crash:

- `beforeToolCall` catch → `{block: true, reason: "KPi could not restore a valid SBTD state. Run
  /sbtd doctor before executing tools."}`.
- `beforeAgentStart` catch → appends a runtime marker with `effective-control-state="blocked"
  repair="/sbtd doctor"`.
- `reobserve` catch → records a blocked observation and `ctx.ui.notify(...)`.

(All in the `src/extension.ts:2600-2780` region.) When you add a handler, add its fail-closed catch
in the same change.

## Rules of Thumb

- Never convert a failure into a pass. Degrade to `blocked` + `repairPath: "/sbtd doctor"` or
  return `block: true`.
- Malformed host input is rejected at the adapter edge with stable reason codes
  (`OmpExtensionV1EventRejection`), never interpreted (see
  [Security Invariants](./security-invariants.md)).
- Error text shown to users goes through `ctx.ui.notify(message, "info" | "warning")`; there is no
  console logging in `src/`.
