# omp-sbtd Security Invariants

> Trust boundaries this package maintains. These are enforced by tests; breaking them is a
> correctness bug, not a style issue.

---

## Fail-Closed Everywhere

- **Registration**: `probeOmpExtensionV1Capabilities` throws before any command/tool/event is
  registered when a required host capability or event is missing (`src/runtime/index.ts`). No
  partial registration, no optimistic ready state; `registerTool` runs before `registerCommand` so
  a later throw cannot leave a misleading ready state, and event subscriptions roll back via host
  `off`/`removeListener`.
- **Malformed events are never interpreted**: adapter-edge `.strict()` schemas +
  `OmpExtensionV1EventRejection`; reason codes are stable identifiers carrying no payload content
  (`src/runtime/omp-extension-v1.ts`). Feature Rule: "malformed event 不得被解释成批准或完成"
  (`features/sbtd-control-bootstrap.feature`).
- **Unknown tools are mutation-capable**: anything not in `builtinToolCapabilities` (including
  `mcp__*`) → capability `unknown`, `mutationOrPhaseAdvancing: true` (`src/tool-risk/index.ts`;
  asserted in `test/tool-risk.test.ts:38-43`).

## Approvals

- **Typed, one-shot, turn-bound.** `ToolApprovalBook` records a blocked risky call bound to
  `toolCallId` + risk classes + an input fingerprint (`fingerprintToolCall`); `turnStart` clears
  the book — nothing carries across a turn boundary (`src/extension.ts:2860-2870`,
  `src/tool-risk/index.ts`).
- `secret-read-guard` and `install-requires-approval` are **non-configurable hard rules**
  (`src/rules/index.ts:190-228`). Secret path patterns use word boundaries, a `.pub` exclusion, and
  a mixed-secret tier (`src/tool-risk/index.ts`). Do not weaken these patterns or make them
  configurable.

## Persistence

- **Session log only.** State is appended as host session entries of custom type
  `kpi.sbtd.session.v1` (`SBTD_STATE_CUSTOM_TYPE`, `src/state/index.ts`), restored by replaying
  `ctx.sessionManager.getBranch()`, and preserved across compaction under
  `SBTD_STATE_COMPACTION_KEY`. The plugin holds no state outside the session log and writes no
  global config files.
- **Digests, not contents.** Evidence descriptors persist only SHA-256 fingerprints (scenario
  locator digest, report digest, sidecar digest, commit) — never file contents, secrets, or prompt
  text (`validationEvidenceDescriptorSchema` in `src/report/index.ts`; README "Data handling and
  telemetry").
- State schema evolution is **additive only** (`migrateDraftSessionState` in
  `src/state/index.ts`); older readers must keep working (README uninstall section).

## Filesystem and Process

- **Embedded kit integrity**: `verifyEmbeddedKitManifest` binds manifest digests to asset bytes;
  per-segment symlink rejection; non-POSIX path rejection; **error messages never leak the local
  root path** — asserted by `expectSafeFailure` (`test/kit-security.test.ts:25-38`).
- **Path confinement in the evidence observer**: `resolveSafe` + `regularFileBytes` +
  `skippedDirectories` + a 256 KiB envelope cap (`MAX_ENVELOPE_BYTES`) + a 30 s validator timeout
  (`VALIDATOR_TIMEOUT_MS`) (`src/evidence/index.ts`). The embedded validator reads only files
  inside the project root.
- **All process execution behind injected adapters**: `EvidenceProcess` (`src/evidence/index.ts`),
  `CanonicalOnboardProcess` (`src/onboard/python-runtime.ts:29-37`), or the host's `pi.exec` —
  always with a timeout. No bare `child_process` in `src/`.
- **Report transport sanitization**: bounded `safeIdentifierSchema` / `safeCodeSchema` and
  `MAX_RENDERED_SBTD_REPORT_BYTES` (32 KiB) on assembled output (`src/report/index.ts:4-30`).

## Zero-Write Default

Plugin installation performs no project or global modification. Read-only commands
(status/doctor/help) receive a `readOnlyFiles` FileAdapter whose `writeAtomic` / `makeDirectory` /
`remove` **reject** (`src/extension.ts:1505-1525`) — the read-only boundary is structural, not
conventional. Keep new read-only commands on that adapter.

## Distribution Hygiene

- `scripts/embed-kit.mjs` scans embedded kit bytes for a forbidden token ("codex" as a byte
  array) — the OMP distribution must be zero-Codex.
- Publish surface is the `files` whitelist; SBOM is generated at build
  (`scripts/p0/write-sbom.ts`); the publish helper parses `.env` as data and never sources it
  (README).
- No telemetry, no network calls (README "Data handling and telemetry"). Do not add either.
