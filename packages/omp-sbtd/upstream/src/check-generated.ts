import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { checkAgentPluginProjection } from "./agent-plugin-projection.js";
import { checkGenerated } from "./index.js";
import { checkOmpProjection } from "./omp-projection.js";

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
await checkGenerated({
  packageRoot,
  outputDirectory: `${packageRoot}/generated`,
});
await checkOmpProjection({
  packageRoot,
  canonicalDirectory: `${packageRoot}/generated`,
  outputDirectory: `${packageRoot}/generated-omp`,
});
await checkAgentPluginProjection({
  packageRoot,
  canonicalDirectory: `${packageRoot}/generated`,
  outputDirectory: `${packageRoot}/generated-agent-plugin`,
});
const [generatedLicense, packageLicense, generatedNotices, packageNotices] =
  await Promise.all([
    readFile(`${packageRoot}/generated/LICENSE`, "utf8"),
    readFile(`${packageRoot}/LICENSE`, "utf8"),
    readFile(`${packageRoot}/generated/THIRD_PARTY_NOTICES.md`, "utf8"),
    readFile(`${packageRoot}/THIRD_PARTY_NOTICES.md`, "utf8"),
  ]);
if (generatedLicense !== packageLicense || generatedNotices !== packageNotices)
  throw new Error("generated Kit release artifacts are stale");
process.stdout.write("generated output is current\n");
