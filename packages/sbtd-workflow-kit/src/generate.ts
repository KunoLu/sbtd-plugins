import { cp } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { generateAgentPluginProjection } from "./agent-plugin-projection.js";
import { generateKit } from "./index.js";
import { generateOmpProjection } from "./omp-projection.js";

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const result = await generateKit({
  packageRoot,
  outputDirectory: `${packageRoot}/generated`,
});
const [projection, agentPluginProjection] = await Promise.all([
  generateOmpProjection({
    packageRoot,
    canonicalDirectory: `${packageRoot}/generated`,
    outputDirectory: `${packageRoot}/generated-omp`,
  }),
  generateAgentPluginProjection({
    packageRoot,
    canonicalDirectory: `${packageRoot}/generated`,
    outputDirectory: `${packageRoot}/generated-agent-plugin`,
  }),
]);
await Promise.all([
  cp(`${packageRoot}/generated/LICENSE`, `${packageRoot}/LICENSE`),
  cp(
    `${packageRoot}/generated/THIRD_PARTY_NOTICES.md`,
    `${packageRoot}/THIRD_PARTY_NOTICES.md`,
  ),
]);
process.stdout.write(
  `${JSON.stringify({
    generatedSha256: result.manifest.generatedSha256,
    targets: result.targets,
    projectionGeneratedSha256: projection.manifest.projection.generatedSha256,
    agentPluginGeneratedSha256: agentPluginProjection.manifest.generatedSha256,
    certifiedCount: agentPluginProjection.manifest.certifiedCount,
  })}\n`,
);
