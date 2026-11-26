export const AGENT_PLUGINS_SCHEMA_URL: "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json";

/** Validates the manifest or throws; it does not narrow the caller's value. */
export function validatePluginManifest(
  manifest: unknown,
  options?: Readonly<{ expectedVersion?: string }>,
): void;
