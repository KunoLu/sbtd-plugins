import { readFile } from "node:fs/promises";

/**
 * Reads the Plugin version from its own package.json. The file sits one level
 * above both `src/` (development, tests) and `dist/` (packed runtime), so a
 * single relative URL serves both layouts.
 */
export async function getPluginVersion(): Promise<string> {
  try {
    const parsed: unknown = JSON.parse(
      await readFile(new URL("../package.json", import.meta.url), "utf8"),
    );
    const version = (parsed as { version?: unknown }).version;
    return typeof version === "string" && version.length > 0
      ? version
      : "unknown";
  } catch {
    return "unknown";
  }
}
