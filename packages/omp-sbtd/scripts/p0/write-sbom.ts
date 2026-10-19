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
const upstreamRoot = resolve(
  process.env.KPI_SBOM_UPSTREAM_ROOT ?? `${pluginRoot}/upstream`,
);
const releaseRoot =
  process.env.KPI_SBOM_RELEASE_ROOT === "staged-promotion"
    ? "staged-promotion"
    : "source-package";
const result = await writePluginSpdxSbom({
  workspaceRoot,
  pluginRoot,
  upstreamRoot,
  releaseRoot,
});
process.stdout.write(`${JSON.stringify(result)}\n`);
