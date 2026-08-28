// Slice 5 Host Event Surface suite — read-only Host event observer (companion
// extension, promoted from the Gate 0.2 spike observer). Loaded alongside the
// frozen candidate Plugin tarball inside the real OMP Host process. It only
// subscribes via the public `pi.on(...)` surface and appends sanitized records
// to SPIKE_OBSERVER_LOG (JSONL). It never returns policy results, never
// mutates Plugin/Host state, and never records prompt text, tool I/O text,
// tokens, transcripts, local paths, or other PII — only event names, schema
// verdicts, non-sensitive reason codes, field presence, and irreversible
// digests.
//
// Slice 5 changes vs the spike:
// - The subscribed event list comes from HOST_EVENT_OBSERVE_EVENTS, which the
//   suite runner builds from `ompExtensionV1Inventory` — the inventory is the
//   single event list; this file declares none.
// - Payloads are validated with the Slice 4 adapter-edge schemas by importing
//   `validateOmpExtensionV1Event` from the *subject tarball's* own
//   dist/runtime/omp-extension-v1.js (HOST_EVENT_VALIDATOR_MODULE). A missing
//   module/export or a rejection is recorded fail-closed, never tolerated.
// - Every record carries HOST_EVENT_RUN_ID so a shared/stale log from another
//   run is detectable by the evidence validator.
import { appendFileSync, readFileSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { sha256, sha256File } from "./lib.mjs";

const requiredEnv = (name) => {
  const value = process.env[name];
  if (typeof value !== "string" || value.length === 0)
    throw new Error(`missing env ${name}`);
  return value;
};

const logPath = requiredEnv("SPIKE_OBSERVER_LOG");
const runId = requiredEnv("HOST_EVENT_RUN_ID");
const validatorModulePath = requiredEnv("HOST_EVENT_VALIDATOR_MODULE");
const observeEvents = JSON.parse(requiredEnv("HOST_EVENT_OBSERVE_EVENTS"));
if (
  !Array.isArray(observeEvents) ||
  observeEvents.length === 0 ||
  observeEvents.some((name) => typeof name !== "string" || name.length === 0)
)
  throw new Error(
    "HOST_EVENT_OBSERVE_EVENTS must be a non-empty JSON string array",
  );

let sequence = 0;
const startedAt = Date.now();
const record = (entry) => {
  sequence += 1;
  appendFileSync(
    logPath,
    `${JSON.stringify({ seq: sequence, atMs: Date.now() - startedAt, runId, ...entry })}\n`,
    "utf8",
  );
};

// --- Subject adapter-edge validator (from the frozen tarball under test) ----
// The observer validates each payload with the exact code the Plugin ships at
// its adapter edge. This doubles as proof that the frozen tarball contains
// dist/runtime/omp-extension-v1.js with the Slice 4 contract surface.
let validateHostEvent;
let validatorModuleSha256;
let validatorInventoryVersion;
let validatorLoadFailure;
try {
  const modulePath = realpathSync(validatorModulePath);
  validatorModuleSha256 = sha256File(modulePath);
  const mod = await import(pathToFileURL(modulePath).href);
  if (typeof mod.validateOmpExtensionV1Event !== "function")
    throw new Error("validateOmpExtensionV1Event export missing");
  validateHostEvent = mod.validateOmpExtensionV1Event;
  validatorInventoryVersion =
    typeof mod.ompExtensionV1Inventory?.version === "string"
      ? mod.ompExtensionV1Inventory.version
      : undefined;
} catch (error) {
  validatorLoadFailure = `VALIDATOR_MODULE_LOAD_FAILED:${error instanceof Error ? error.name : "unknown"}`;
}

// --- Host artifact identity, proven from inside the real Host process --------
// The running entrypoint (dist/cli.js of the loaded @oh-my-pi/pi-coding-agent
// package) and its owning package.json are hashed in-process. Only digests and
// the public name/version are recorded — never local paths.
try {
  const entrypoint = realpathSync(process.argv[1]);
  let dir = dirname(entrypoint);
  let pkgPath;
  for (let depth = 0; depth < 8; depth += 1) {
    const candidate = join(dir, "package.json");
    try {
      const parsed = JSON.parse(readFileSync(candidate, "utf8"));
      if (parsed?.name === "@oh-my-pi/pi-coding-agent") {
        pkgPath = candidate;
        break;
      }
    } catch {
      // keep walking up
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  record({
    kind: "host_identity",
    runtime: "node",
    hostEntrypointSha256: sha256File(entrypoint),
    hostEntrypointPathDigest: sha256(entrypoint),
    ...(pkgPath === undefined
      ? { hostPackageFound: false }
      : {
          hostPackageFound: true,
          hostPackageName: "@oh-my-pi/pi-coding-agent",
          hostPackageVersion: JSON.parse(readFileSync(pkgPath, "utf8")).version,
          hostPackageJsonSha256: sha256File(pkgPath),
        }),
    ...(validatorModuleSha256 === undefined
      ? { validatorLoaded: false, validatorReason: validatorLoadFailure }
      : {
          validatorLoaded: true,
          validatorModuleSha256,
          ...(validatorInventoryVersion === undefined
            ? {}
            : { validatorInventoryVersion }),
        }),
  });
} catch (error) {
  record({
    kind: "host_identity",
    hostPackageFound: false,
    reason: `IDENTITY_CAPTURE_FAILED:${error instanceof Error ? error.name : "unknown"}`,
  });
}

// Structure-only digest of a message array: roles + content block types, never text.
const isArray = Array.isArray;
const isString = (v) => typeof v === "string";
const isNumber = (v) => typeof v === "number" && Number.isFinite(v);
const isBoolean = (v) => typeof v === "boolean";
const isStringOrNull = (v) => v === null || isString(v);
const isStringNullOrUndefined = (v) =>
  v === null || v === undefined || isString(v);
const isObject = (v) => typeof v === "object" && v !== null && !isArray(v);

// Host-supplied reason text is free-form and can embed local paths or PII.
// Only the pinned session_switch vocabulary may persist verbatim; every
// other reason (notably tool_approval_resolved) is recorded as an
// irreversible digest, never raw text.
const SESSION_SWITCH_HOST_REASONS = new Set([
  "new",
  "resume",
  "fork",
  "handoff",
]);

const messagesDigest = (messages) =>
  isArray(messages)
    ? sha256(
        JSON.stringify(
          messages.map((m) => ({
            role: m?.role,
            content: isArray(m?.content)
              ? m.content.map((c) => c?.type)
              : typeof m?.content,
          })),
        ),
      )
    : undefined;

const summarize = (name, event, ctx) => {
  const keys = isObject(event) ? Object.keys(event) : [];
  let schemaValid = false;
  let reason;
  if (validateHostEvent === undefined) {
    reason = validatorLoadFailure ?? "VALIDATOR_MODULE_UNAVAILABLE";
  } else {
    try {
      validateHostEvent(name, event);
      schemaValid = true;
    } catch (error) {
      // OmpExtensionV1EventRejection carries a stable, content-free reason
      // code; anything else is an observer-side validator fault. Neither
      // path echoes payload content.
      if (
        error?.name === "OmpExtensionV1EventRejection" &&
        isString(error.reasonCode)
      )
        reason = `EVENT_REJECTED:${error.reasonCode}`;
      else
        reason = `VALIDATOR_ERROR:${error instanceof Error ? error.name : "unknown"}`;
    }
  }
  const out = {
    kind: "event",
    event: name,
    schemaValid,
    fields: keys.sort(),
  };
  if (reason !== undefined) out.reason = reason;
  // Irreversible identity digests only.
  if (isString(event?.sessionId)) out.sessionDigest = sha256(event.sessionId);
  if (isString(event?.toolCallId))
    out.toolCallDigest = sha256(event.toolCallId);
  if (isString(event?.previousSessionFile))
    out.previousSessionFileDigest = sha256(event.previousSessionFile);
  if ("previousSessionFile" in (event ?? {}))
    out.previousSessionFilePresent = event.previousSessionFile !== undefined;
  if (isStringOrNull(event?.newLeafId))
    out.newLeafDigest =
      event.newLeafId === null ? null : sha256(event.newLeafId);
  if (isStringNullOrUndefined(event?.oldLeafId))
    out.oldLeafDigest =
      event.oldLeafId == null
        ? (event.oldLeafId ?? null)
        : sha256(event.oldLeafId);
  if (isNumber(event?.turnIndex)) out.turnIndex = event.turnIndex;
  if (isNumber(event?.turn_id)) out.turnId = event.turn_id;
  if (isString(event?.reason)) {
    if (
      name === "session_switch" &&
      SESSION_SWITCH_HOST_REASONS.has(event.reason)
    )
      out.hostReason = event.reason;
    else out.hostReasonDigest = sha256(event.reason);
  }
  if (isBoolean(event?.approved)) out.approved = event.approved;
  if (isString(event?.toolName)) out.toolNameDigest = sha256(event.toolName);
  if (isBoolean(event?.isError)) out.isError = event.isError;
  if (isArray(event?.messages)) {
    out.messageCount = event.messages.length;
    out.messagesDigest = messagesDigest(event.messages);
  }
  if (isArray(event?.toolResults))
    out.toolResultCount = event.toolResults.length;
  if (isString(event?.prompt)) out.promptDigest = sha256(event.prompt);
  try {
    const sessionId = ctx?.sessionManager?.getSessionId?.();
    if (isString(sessionId)) out.ctxSessionDigest = sha256(sessionId);
  } catch {
    out.reason = `${out.reason ? `${out.reason};` : ""}CTX_SESSION_ID_UNAVAILABLE`;
  }
  return out;
};

export default function hostEventObserver(pi) {
  for (const name of observeEvents)
    pi.on(name, (event, ctx) => {
      try {
        record(summarize(name, event ?? {}, ctx ?? {}));
      } catch (error) {
        record({
          kind: "event",
          event: name,
          schemaValid: false,
          reason: `OBSERVER_ERROR:${error instanceof Error ? error.name : "unknown"}`,
        });
      }
      // Read-only: never return a policy result.
      return undefined;
    });
  record({ kind: "observer_ready", subscriptions: observeEvents.length });
}
