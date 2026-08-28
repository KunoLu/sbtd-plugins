// Slice 5 Host Event Surface suite — shared helpers for the .mjs driver side.
// Extracted from the Gate 0.2 spike (scripts/p0/gate-0-2, promoted and then
// deleted) so the sanitizer is importable and contract-tested on its own.
// These helpers never see prompt text, tool I/O text, tokens, or PII by
// design; sanitizeStderrText exists precisely because Host stderr can embed
// local paths and file URIs.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

export const sha256 = (value) =>
  createHash("sha256").update(value).digest("hex");

export const sha256File = (path) => sha256(readFileSync(path));

/**
 * Strip absolute local paths and file:// URIs from Host stderr before it is
 * interpolated into errors or logs. `roots` is a list of [absolutePath,
 * label] pairs; longer paths are replaced first so nested roots collapse to
 * their most specific label. Any remaining absolute POSIX path token becomes
 * `<path>`. Non-path content is preserved verbatim.
 */
export const sanitizeStderrText = (text, roots) => {
  let out = String(text).replace(/file:\/\/\S+/g, "<file-uri>");
  const sorted = roots
    .filter(([absolute]) => typeof absolute === "string" && absolute.length > 1)
    .sort((a, b) => b[0].length - a[0].length);
  for (const [absolute, label] of sorted) out = out.split(absolute).join(label);
  out = out.replace(/(?<![\w:.-])\/[\w./-]+/g, "<path>");
  return out;
};
