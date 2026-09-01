# omp-sbtd Type Safety

> zod 4.1.12 discipline as practiced in `packages/omp-sbtd/src/`. zod is the package's only runtime
> dependency; schemas ARE the boundary contracts.

---

## Core Rules

1. **`.strict()` on every persisted or boundary object.** Unknown keys are rejected.
   Examples: `sbtdSessionStateSchema` (`src/state/index.ts`), `validationReportSchema` /
   `providerObservationSchema` / `evidenceEnvelopeSchema` (`src/report/index.ts`),
   `toolEvidenceRecordSchema` (`src/environment/tool-evidence.ts:33-77`),
   `acceptedSkipRecordSchema` (`src/environment/accepted-skip.ts:35`), `kitSnapshotSchema` /
   `onboardPlanSchema` / `transactionJournalSchema` (`src/onboard/index.ts`), and all host event
   schemas (`src/runtime/omp-extension-v1.ts`).

2. **`.passthrough()` only at the host/tool-call edge**, where payloads are host-owned, and always
   with a justifying comment. Examples: `toolCallSchema` / `bashToolCallSchema` (`src/extension.ts`,
   `src/tool-risk/index.ts`); `envelopeFactsSchema` (`src/evidence/index.ts`) carries the comment
   "Lenient fact extraction; authoritative validation stays with the validator." If you add a
   `.passthrough()` without that justification, expect check to reject it.

3. **Cross-field invariants via `.superRefine`.** Example: `toolEvidenceRecordSchema` enforces
   "only a non-executable Skill may record callability as not-needed"
   (`src/environment/tool-evidence.ts:62-77`). Same technique in `sbtdSessionStateSchema`,
   `validationReportSchema`, `evidenceEnvelopeSchema`.

4. **Discriminated unions for variant shapes.**
   `formalArtifactDescriptorSchema = z.discriminatedUnion("status", …)` (`src/report/index.ts`);
   `canonicalOperationSchema = z.discriminatedUnion("kind", …)` (`src/onboard/python-runtime.ts:6-27`).

5. **Format-heavy string schemas.** Hashes `z.string().regex(/^[0-9a-f]{64}$/)`, timestamps
   `z.string().datetime()`, ids `z.string().uuid()`. Rendered identifiers go through bounded
   `safeIdentifierSchema` / `safeCodeSchema` / `safeRelativePathSchema` (regexes + max lengths,
   `src/report/index.ts:4-30`).

6. **`z.input` / `z.output` split when defaults exist.** `taskFactsSchema`
   (`src/workflow/index.ts:26-45`) uses `.optional().default(false)` fields and exports
   `TaskFacts = z.input<typeof taskFactsSchema>` for callers, while internal logic works on
   `z.output`. Export the input type; compute with the output type.

## Parse Strategy by Trust Level

- `.parse` (throw) at trusted/domain boundaries: `classifyTask`, `evaluateEnvironment`.
- `.safeParse` for untrusted host event field extraction, degrading to `undefined` — e.g.
  `commandFromToolEvent` and toolCallId extraction in `src/extension.ts`.
- Host event payloads are validated at the adapter edge by `.strict()` schemas with a `type`
  literal discriminator; `validateOmpExtensionV1Event` throws `OmpExtensionV1EventRejection` with
  stable reason codes that never echo payload content (`src/runtime/omp-extension-v1.ts`). An
  unknown event name or wrong discriminator is malformed and never reaches a handler.

## TypeScript Configuration Inheritance

`tsconfig.json` extends `../../tsconfig.base.json`: `strict`, `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, `verbatimModuleSyntax`, NodeNext, ES2024. Practical consequences:

- Indexing returns `T | undefined` — guard with `??` / explicit checks.
- Optional fields distinguish "absent" from `undefined` — build objects with conditional spread
  (`...(x === undefined ? {} : { x })`, heavily used when assembling `RuleEvaluationFacts` in
  `src/extension.ts:2740-2760`) or declare `field?: T | undefined` explicitly.
- Type-only imports use `import type` or inline `type` qualifiers.
- Src imports carry `.js` suffixes (NodeNext).

## Immutability

`readonly` fields on every interface, `Readonly<Record<…>>`, `as const` closed tuples
(`bookGateIds`, `gateStates`, `gatePhases`, `reviewerStatuses` in `src/gates/index.ts`; rule ids as
a closed literal union in `src/rules/index.ts`). Transforms return new objects/arrays — e.g.
`setRuleEnabled` returns a new array instead of mutating the registry.
