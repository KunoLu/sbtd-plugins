const absoluteLocalPathPattern =
  /(?:\bfile:\/{1,2}(?:localhost)?|(?:^|[\s"'=:(]))(?:\/(?!\/)(?!sbtd(?:\s|$))[^\s"'\\]+\/[^\s"'\\]+|[A-Za-z]:\\(?:[^\\\s"'=]+(?:\\[^\\\s"'=]+)*))/i;

const sensitiveTextPatterns = [
  /\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}/i,
  /(?:api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|credential|cookie|set-cookie|authorization|\btoken\b)\s*[:=]\s*\S+/i,
  /\b(?:sk|pk|rk|ghp|gho)[_-][A-Za-z0-9_-]{8,}\b/,
] as const;

const sensitiveFieldFragments = [
  "credential",
  "token",
  "cookie",
  "header",
  "authorization",
  "apikey",
  "secret",
  "provider",
  "account",
  "email",
  "disabledcause",
] as const;

export function hasForbiddenLocalPath(value: string): boolean {
  return absoluteLocalPathPattern.test(value);
}

export function hasSensitiveText(value: string): boolean {
  return (
    hasForbiddenLocalPath(value) ||
    sensitiveTextPatterns.some((pattern) => pattern.test(value))
  );
}

export function hasSensitiveFieldName(name: string): boolean {
  const normalized = name.toLowerCase().replace(/[^a-z0-9]/g, "");
  if (
    normalized === "tokens" ||
    normalized === "tokencount" ||
    normalized === "maxtokens"
  )
    return false;
  return sensitiveFieldFragments.some((fragment) =>
    normalized.includes(fragment),
  );
}
