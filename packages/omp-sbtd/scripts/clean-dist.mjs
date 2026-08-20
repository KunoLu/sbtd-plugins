import { rm } from "node:fs/promises";
import { isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";

// Deterministic, cross-platform dist cleaning. The TypeScript compiler never
// removes outputs for deleted sources, so a build that skips this step can
// ship stale artifacts (for example a removed Onboard bridge) with a
// self-consistent SBOM. Runs before `tsc` in the build script; `force` makes
// a missing directory a successful no-op so rebuilds stay idempotent.
const override = process.env.KPI_DIST_DESTINATION;
if (override !== undefined && !isAbsolute(override)) {
  throw new Error("KPI_DIST_DESTINATION must be an absolute path");
}
const destination =
  override ?? fileURLToPath(new URL("../dist", import.meta.url));
await rm(destination, { force: true, recursive: true });
