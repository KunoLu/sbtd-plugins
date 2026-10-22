import { resolve } from "node:path";
import { z } from "zod";
import type { CanonicalOnboardProcess } from "./python-runtime.js";

const packages = [
  "jsonschema",
  "PyYAML",
  "markdown-it-py",
  "tomlkit",
  "cryptography",
] as const;
const resultSchema = z
  .object({ missingPackages: z.array(z.enum(packages)) })
  .strict();
const probe = `import importlib, json
missing = []
for package, module in [("jsonschema", "jsonschema"), ("PyYAML", "yaml"), ("markdown-it-py", "markdown_it"), ("tomlkit", "tomlkit"), ("cryptography", "cryptography")]:
    try:
        importlib.import_module(module)
    except Exception:
        missing.append(package)
print(json.dumps({"missingPackages": missing}))`;

// This is an entry guard, not a shell sandbox. Recognized SBTD dependency
// commands with ambiguous interpreter selection fail closed, never get a probe
// against an unrelated Python. Arbitrary user programs remain host-owned.
export function needsIsolatedDependencies(command: string): boolean {
  const invokesPython =
    /(?:^|[\s"';&|])(?:[^\s"';&|]+\/)?python(?:3(?:\.\d+)?)?(?:[\s"']|$)/.test(
      command,
    );
  const invokesScript =
    /^\s*["']?(?:[^\s"']*\/)?(?:onboard|sbtd_[a-z_]+)\.py\b/.test(command);
  if (!invokesPython && !invokesScript) return false;
  return (
    /\bsbtd_(?:upgrade|migration|recovery|cleanup|graft_deployment|reconciliation)\w*\b/.test(
      command,
    ) ||
    /\bonboard\.py["']?\s+(?:upgrade|migration|recovery|cleanup-legacy)(?:\s|$)/.test(
      command,
    ) ||
    (/\bonboard\.py\b/.test(command) &&
      /--migration-manifest(?:[=\s]|$)/.test(command))
  );
}

export async function dependencyPreflightRefusal(
  command: string,
  runtimeRoot: string,
  process: CanonicalOnboardProcess,
  cwd: string,
): Promise<{ block: true; reason: string } | undefined> {
  const requirements = resolve(runtimeRoot, "requirements.txt");
  const installCommand = `python3 -m pip install -r '${requirements.replaceAll("'", "'\\''")}'`;
  const refuse = (
    code: string,
    missingPackages: readonly string[],
    message: string,
  ) => ({
    block: true as const,
    reason: JSON.stringify({ code, missingPackages, installCommand, message }),
  });
  // Accept a direct Python command only. Shell wrappers, assignments, pipelines,
  // substitutions and multiple commands cannot establish interpreter identity.
  const executable = /^\s*(?:"([^"\n]+)"|'([^'\n]+)'|([^\s"']+))\s/.exec(
    command,
  );
  const python = executable?.[1] ?? executable?.[2] ?? executable?.[3];
  if (
    python === undefined ||
    !/(?:^|\/)python(?:3(?:\.\d+)?)?$/.test(python) ||
    /[;&|`$\n\r<>]/.test(command)
  ) {
    return refuse(
      "ISOLATED_INTERPRETER_UNRESOLVED",
      [],
      "Use a direct Python invocation for the SBTD entry; shell indirection cannot be preflighted safely.",
    );
  }
  try {
    const result = await process.exec(python, ["-I", "-B", "-c", probe], {
      cwd,
      timeout: 30_000,
    });
    if (
      result.killed ||
      result.code !== 0 ||
      Buffer.byteLength(result.stdout) > 4096
    ) {
      return refuse(
        "ISOLATED_DEPENDENCIES_UNAVAILABLE",
        [],
        "The isolated dependency probe did not complete; the entry was not run.",
      );
    }
    const parsed = resultSchema.parse(JSON.parse(result.stdout));
    if (parsed.missingPackages.length > 0) {
      return refuse(
        "ISOLATED_DEPENDENCIES_UNAVAILABLE",
        parsed.missingPackages,
        "Install the declared dependencies manually in the selected interpreter; the entry was not run.",
      );
    }
    return undefined;
  } catch {
    return refuse(
      "ISOLATED_DEPENDENCIES_UNAVAILABLE",
      [],
      "The isolated dependency probe was unavailable or returned an invalid result; the entry was not run.",
    );
  }
}
