import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Thin CLI wrapper: verifies the moved upstream projection outputs
// (`upstream/generated*`) are current. Implementation lives in
// `upstream/src/check-generated.ts` (moved from @kunolu/sbtd-workflow-kit).
const upstreamRoot = fileURLToPath(new URL("../upstream", import.meta.url));
const result = spawnSync(
  process.execPath,
  [
    fileURLToPath(new URL("../node_modules/tsx/dist/cli.mjs", import.meta.url)),
    fileURLToPath(
      new URL("../upstream/src/check-generated.ts", import.meta.url),
    ),
    ...process.argv.slice(2),
  ],
  { cwd: upstreamRoot, stdio: "inherit" },
);
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
