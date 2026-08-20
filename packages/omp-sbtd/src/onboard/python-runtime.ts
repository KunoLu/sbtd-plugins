import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { relative, resolve, sep } from "node:path";
import { z } from "zod";

const canonicalOperationSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("check-omp-cli"),
      cwd: z
        .string()
        .min(1)
        .refine((value) => !value.includes("\0")),
    })
    .strict(),
  z
    .object({
      kind: z.literal("install-stable-external-skills"),
      cwd: z
        .string()
        .min(1)
        .refine((value) => !value.includes("\0")),
      globalSkillsDirectory: z
        .string()
        .min(1)
        .refine((value) => !value.includes("\0")),
    })
    .strict(),
]);
export type CanonicalOnboardOperation = z.infer<
  typeof canonicalOperationSchema
>;

export interface CanonicalOnboardProcessResult {
  readonly stdout: string;
  readonly stderr: string;
  readonly code: number | null;
  readonly killed: boolean;
}

export interface CanonicalOnboardProcess {
  exec(
    command: string,
    args: readonly string[],
    options: { readonly cwd: string; readonly timeout: number },
  ): Promise<CanonicalOnboardProcessResult>;
}

const agentCliResultSchema = z
  .object({
    mode: z.literal("check-agent-cli"),
    platform: z.literal("oh-my-pi"),
    label: z.literal("Oh My Pi"),
    command: z.literal("omp"),
    path: z.string().min(1).nullable(),
    version: z.string().min(1).nullable(),
    installed: z.boolean(),
    npmPackage: z.literal("@oh-my-pi/pi-coding-agent"),
    installCommand: z.string().min(1),
    verifyCommand: z.literal("omp --version"),
    advice: z.string().min(1),
  })
  .strict();

const canonicalSkillNameSchema = z.string().regex(/^[a-z0-9-]+$/);
const committedExternalSkillResultSchema = z
  .object({
    name: canonicalSkillNameSchema,
    repo: z.string().url(),
    target: z.string().min(1),
    status: z.enum(["installed", "replaced", "failed"]),
    phase: z.literal("commit"),
    replacedExisting: z.boolean().optional(),
    sourceUsed: z.literal("stable"),
    sourceRevision: z.string().regex(/^[0-9a-f]{40}$/),
    stableSet: z.string().min(1).nullable(),
    fallbackReason: z.string().min(1).nullable(),
    error: z.string().min(1).optional(),
  })
  .strict();
const removedLegacyExternalSkillResultSchema = z
  .object({
    name: canonicalSkillNameSchema,
    replacement: canonicalSkillNameSchema,
    target: z.string().min(1),
    status: z.literal("removed"),
    phase: z.literal("remove-legacy-after-commit"),
  })
  .strict();
const externalSkillResultSchema = z.union([
  committedExternalSkillResultSchema,
  removedLegacyExternalSkillResultSchema,
]);
const externalInstallResultSchema = z
  .object({
    mode: z.literal("install-external-skills"),
    scope: z.literal("global"),
    requestedSource: z.literal("auto"),
    targetDir: z.string().min(1),
    forceOverwriteExisting: z.literal(true),
    backupExistingTargets: z.literal("temporary-rollback"),
    replaceFlagProvided: z.boolean(),
    results: z.array(externalSkillResultSchema),
    transaction: z
      .object({
        status: z.enum([
          "committed",
          "not-started",
          "aborted-before-commit",
          "rolled-back",
          "rollback-failed",
          "repair-required",
        ]),
        rolledBack: z.boolean(),
        rollbackErrors: z.array(z.string()),
        rollbackPath: z.string().nullable(),
      })
      .strict(),
  })
  .strict();
export type CanonicalOnboardResult =
  | z.output<typeof agentCliResultSchema>
  | z.output<typeof externalInstallResultSchema>;

export class CanonicalOnboardRuntimeError extends Error {
  constructor(
    readonly code:
      | "INVALID_RUNTIME_PATH"
      | "INVALID_REQUEST"
      | "PROCESS_FAILED"
      | "OUTPUT_TOO_LARGE"
      | "MALFORMED_OUTPUT",
    message: string,
  ) {
    super(message);
    this.name = "CanonicalOnboardRuntimeError";
  }
}

export interface CanonicalOnboardRuntime {
  run(operation: CanonicalOnboardOperation): Promise<CanonicalOnboardResult>;
}

export interface CanonicalOnboardRuntimeInputs {
  readonly runtimeRoot: string;
  readonly runtimeScriptSha256: string;
  readonly process: CanonicalOnboardProcess;
  readonly timeoutMs?: number;
  readonly maxOutputBytes?: number;
}

const defaultTimeoutMs = 120_000;
const defaultMaxOutputBytes = 1_000_000;

async function verifyRuntimeScript(
  inputs: CanonicalOnboardRuntimeInputs,
): Promise<string> {
  const root = resolve(inputs.runtimeRoot);
  const script = resolve(root, "scripts/onboard.py");
  const pathFromRoot = relative(root, script);
  if (
    pathFromRoot.length === 0 ||
    pathFromRoot === ".." ||
    pathFromRoot.startsWith(`..${sep}`)
  )
    throw new CanonicalOnboardRuntimeError(
      "INVALID_RUNTIME_PATH",
      "Canonical Onboard script escapes the verified runtime root.",
    );
  if (!/^[0-9a-f]{64}$/.test(inputs.runtimeScriptSha256))
    throw new CanonicalOnboardRuntimeError(
      "INVALID_RUNTIME_PATH",
      "Canonical Onboard script digest is invalid.",
    );
  let actualDigest: string;
  try {
    actualDigest = createHash("sha256")
      .update(await readFile(script))
      .digest("hex");
  } catch {
    throw new CanonicalOnboardRuntimeError(
      "INVALID_RUNTIME_PATH",
      "Canonical Onboard script is unavailable under the verified runtime root.",
    );
  }
  if (actualDigest !== inputs.runtimeScriptSha256)
    throw new CanonicalOnboardRuntimeError(
      "INVALID_RUNTIME_PATH",
      "Canonical Onboard script digest differs from the verified embedded Kit.",
    );
  return script;
}

function parseResult(
  operation: CanonicalOnboardOperation,
  stdout: string,
  globalSkillsDirectory?: string,
): CanonicalOnboardResult {
  try {
    const parsed: unknown = JSON.parse(stdout);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed))
      throw new Error("Canonical Onboard did not return an object.");
    if (operation.kind === "check-omp-cli") {
      const { runtime: _runtime, ...result } = parsed as Record<
        string,
        unknown
      >;
      return agentCliResultSchema.parse(result);
    }
    const {
      plan: _plan,
      postCheck: _postCheck,
      installationReport: _installationReport,
      ...candidate
    } = parsed as Record<string, unknown>;
    const result = externalInstallResultSchema.parse(candidate);
    const targetDirectory = resolve(globalSkillsDirectory as string);
    if (
      resolve(result.targetDir) !== targetDirectory ||
      result.results.some((entry) => {
        const path = relative(targetDirectory, resolve(entry.target));
        return path === "" || path === ".." || path.startsWith(`..${sep}`);
      })
    )
      throw new Error(
        "External Skill result escaped the requested target root.",
      );
    return result;
  } catch {
    throw new CanonicalOnboardRuntimeError(
      "MALFORMED_OUTPUT",
      "Canonical Onboard returned an unrecognized or unsafe JSON protocol result.",
    );
  }
}

export async function createCanonicalOnboardRuntime(
  inputs: CanonicalOnboardRuntimeInputs,
): Promise<CanonicalOnboardRuntime> {
  const script = await verifyRuntimeScript(inputs);
  const timeout = inputs.timeoutMs ?? defaultTimeoutMs;
  const maxOutputBytes = inputs.maxOutputBytes ?? defaultMaxOutputBytes;
  if (!Number.isSafeInteger(timeout) || timeout <= 0)
    throw new CanonicalOnboardRuntimeError(
      "INVALID_REQUEST",
      "Canonical Onboard timeout must be a positive integer.",
    );
  if (!Number.isSafeInteger(maxOutputBytes) || maxOutputBytes <= 0)
    throw new CanonicalOnboardRuntimeError(
      "INVALID_REQUEST",
      "Canonical Onboard output limit must be a positive integer.",
    );
  return {
    async run(operation) {
      const request = canonicalOperationSchema.parse(operation);
      const args =
        request.kind === "check-omp-cli"
          ? ["check-agent-cli", "--platform", "omp", "--json"]
          : [
              "install-external-skills",
              "--all",
              "--scope",
              "global",
              "--source",
              "auto",
              "--global-skills-dir",
              resolve(request.globalSkillsDirectory),
              "--yes",
              "--json",
            ];
      const result = await inputs.process.exec("python3", [script, ...args], {
        cwd: resolve(request.cwd),
        timeout,
      });
      if (
        Buffer.byteLength(result.stdout) + Buffer.byteLength(result.stderr) >
        maxOutputBytes
      )
        throw new CanonicalOnboardRuntimeError(
          "OUTPUT_TOO_LARGE",
          "Canonical Onboard output exceeded the bounded protocol limit.",
        );
      if (result.killed || result.code !== 0)
        throw new CanonicalOnboardRuntimeError(
          "PROCESS_FAILED",
          "Canonical Onboard process failed; inspect the sanitized Onboard report.",
        );
      return parseResult(
        request,
        result.stdout,
        request.kind === "install-stable-external-skills"
          ? request.globalSkillsDirectory
          : undefined,
      );
    },
  };
}
