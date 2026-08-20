/**
 * Agent Plugins 1.0.0 root manifest gate for the Hybrid Plugin.
 *
 * Enforces the migration plan §5 / §28.1 contract: exact 1.0.0 `$schema`,
 * legal `name`, no non-standard top-level fields, correct field types, and
 * `plugin.json.version === package.json.version`.
 */

export const AGENT_PLUGINS_SCHEMA_URL =
  "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json";

const STANDARD_FIELDS = [
  "$schema",
  "name",
  "version",
  "description",
  "license",
  "keywords",
  "homepage",
  "repository",
];

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.length > 0;
}

export function validatePluginManifest(manifest, { expectedVersion } = {}) {
  if (!isPlainObject(manifest)) {
    throw new Error("Plugin manifest is not a JSON object");
  }
  const nonStandard = Object.keys(manifest).filter(
    (field) => !STANDARD_FIELDS.includes(field),
  );
  if (nonStandard.length > 0) {
    throw new Error(
      `Plugin manifest contains non-standard top-level fields: ${nonStandard.join(", ")}`,
    );
  }
  const missing = STANDARD_FIELDS.filter((field) => !(field in manifest));
  if (missing.length > 0) {
    throw new Error(
      `Plugin manifest is missing required fields: ${missing.join(", ")}`,
    );
  }
  if (manifest.$schema !== AGENT_PLUGINS_SCHEMA_URL) {
    throw new Error(
      "Plugin manifest $schema is not the Agent Plugins 1.0.0 schema",
    );
  }
  if (manifest.name !== "omp-sbtd") {
    throw new Error('Plugin manifest name is not "omp-sbtd"');
  }
  if (!isNonEmptyString(manifest.version)) {
    throw new Error("Plugin manifest version is not a non-empty string");
  }
  if (expectedVersion !== undefined && manifest.version !== expectedVersion) {
    throw new Error(
      `Plugin manifest version ${manifest.version} differs from package.json version ${expectedVersion}`,
    );
  }
  if (!isNonEmptyString(manifest.description)) {
    throw new Error("Plugin manifest description is not a non-empty string");
  }
  if (manifest.license !== "Apache-2.0") {
    throw new Error('Plugin manifest license is not "Apache-2.0"');
  }
  if (
    !Array.isArray(manifest.keywords) ||
    manifest.keywords.length === 0 ||
    manifest.keywords.some((keyword) => !isNonEmptyString(keyword))
  ) {
    throw new Error("Plugin manifest keywords is not a non-empty string array");
  }
  if (!isNonEmptyString(manifest.homepage)) {
    throw new Error("Plugin manifest homepage is not a non-empty string");
  }
  const repository = manifest.repository;
  if (
    !isPlainObject(repository) ||
    repository.type !== "git" ||
    !isNonEmptyString(repository.url) ||
    ("directory" in repository && !isNonEmptyString(repository.directory))
  ) {
    throw new Error(
      "Plugin manifest repository is not a valid git repository descriptor",
    );
  }
}
