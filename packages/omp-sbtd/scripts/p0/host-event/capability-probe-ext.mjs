// Slice 7 three-profile certification — capability probe companion extension
// for the omp-runtime-capabilities-v1 profile. Loaded inside the real OMP
// Host next to the frozen subject Plugin tarball; records ONLY the presence
// flags of the omp-extension-v1 inventory capabilities on the live Host API
// object plus the in-process Host artifact identity (digests and the public
// package name/version, never local paths). It never mutates Host or Plugin
// state, never records prompt text, tool I/O, tokens, or PII.
//
// Required env: CAPABILITY_PROBE_LOG, HOST_EVENT_RUN_ID,
//   CAPABILITY_PROBE_NAMES (JSON { required: string[], optional: string[] }).
import { appendFileSync, readFileSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { sha256File } from "./lib.mjs";

const requiredEnv = (name) => {
  const value = process.env[name];
  if (typeof value !== "string" || value.length === 0)
    throw new Error(`missing env ${name}`);
  return value;
};

const logPath = requiredEnv("CAPABILITY_PROBE_LOG");
const runId = requiredEnv("HOST_EVENT_RUN_ID");
const names = JSON.parse(requiredEnv("CAPABILITY_PROBE_NAMES"));
if (
  names === null ||
  typeof names !== "object" ||
  !Array.isArray(names.required) ||
  !Array.isArray(names.optional) ||
  [...names.required, ...names.optional].some(
    (name) => typeof name !== "string" || name.length === 0,
  )
)
  throw new Error(
    "CAPABILITY_PROBE_NAMES must be JSON { required: string[], optional: string[] }",
  );

const record = (entry) =>
  appendFileSync(logPath, `${JSON.stringify({ runId, ...entry })}\n`, "utf8");

// In-process Host artifact identity: hash the running entrypoint
// (dist/cli.js of the loaded @oh-my-pi/pi-coding-agent package) and walk up
// to the owning package.json. Digests + public name/version only.
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
    hostEntrypointSha256: sha256File(entrypoint),
    ...(pkgPath === undefined
      ? { hostPackageFound: false }
      : {
          hostPackageFound: true,
          hostPackageName: "@oh-my-pi/pi-coding-agent",
          hostPackageVersion: JSON.parse(readFileSync(pkgPath, "utf8")).version,
          hostPackageJsonSha256: sha256File(pkgPath),
        }),
  });
} catch (error) {
  record({
    kind: "host_identity",
    hostPackageFound: false,
    reason: `IDENTITY_CAPTURE_FAILED:${error instanceof Error ? error.name : "unknown"}`,
  });
}

export default function capabilityProbe(pi) {
  const present = {};
  for (const name of [...names.required, ...names.optional]) {
    const value = pi?.[name];
    // `zod` is the injected schema-builder namespace; behavior-carrying
    // capabilities (registerCommand/on/registerTool) must be callable.
    // Mirrors hasCapability in src/runtime/omp-extension-v1.ts.
    present[name] =
      name === "zod"
        ? (typeof value === "object" && value !== null) ||
          typeof value === "function"
        : typeof value === "function";
  }
  record({
    kind: "capabilities",
    inventoryVersion: "omp-extension-v1",
    present,
  });
}
