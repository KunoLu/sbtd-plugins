import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { writePluginSpdxSbom } from "./release-validator.ts";

const pluginRoot = resolve(
  process.env.KPI_SBOM_PLUGIN_ROOT ??
    fileURLToPath(new URL("../..", import.meta.url)),
);
const workspaceRoot = resolve(
  process.env.KPI_SBOM_WORKSPACE_ROOT ??
    fileURLToPath(new URL("../../../..", import.meta.url)),
);
const kitRoot = resolve(
  process.env.KPI_SBOM_KIT_ROOT ??
    `${workspaceRoot}/packages/sbtd-workflow-kit`,
);
const releaseRoot =
  process.env.KPI_SBOM_RELEASE_ROOT === "staged-promotion"
    ? "staged-promotion"
    : "source-package";
const result = await writePluginSpdxSbom({
  workspaceRoot,
  pluginRoot,
  kitRoot,
  releaseRoot,
});
process.stdout.write(`${JSON.stringify(result)}\n`);
