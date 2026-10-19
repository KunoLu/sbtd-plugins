import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Thin CLI wrapper: syncs the pinned 640-skills upstream into
// `upstream/vendor/sbtd-workflow-kit-upstream`. Implementation lives in
// `upstream/src/sync-upstream.ts` (moved from @kunolu/sbtd-workflow-kit).
const upstreamRoot = fileURLToPath(new URL("../upstream", import.meta.url));
const result = spawnSync(
  process.execPath,
  [
    fileURLToPath(new URL("../node_modules/tsx/dist/cli.mjs", import.meta.url)),
    fileURLToPath(new URL("../upstream/src/sync-upstream.ts", import.meta.url)),
    ...process.argv.slice(2),
  ],
  { cwd: upstreamRoot, stdio: "inherit" },
);
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
