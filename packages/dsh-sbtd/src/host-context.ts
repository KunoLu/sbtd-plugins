/**
 * Optional Cordis services / stub bags.
 * Direct `ctx.key` throws on a real Context unless `key` is in `inject`.
 * Unit tests pass plain objects without `get()`.
 */
export function optionalHostBag<T>(ctx: object, key: string): T | undefined {
  const host = ctx as { get?: (name: string) => unknown };
  if (typeof host.get === "function") {
    return host.get(key) as T | undefined;
  }
  return (ctx as Record<string, T | undefined>)[key];
}

export function optionalHostCwd(ctx: object, explicitCwd?: string): string {
  if (typeof explicitCwd === "string" && explicitCwd.length > 0) {
    return explicitCwd;
  }
  const cwd = optionalHostBag<string>(ctx, "cwd");
  if (typeof cwd === "string" && cwd.length > 0) {
    return cwd;
  }
  return process.cwd();
}
