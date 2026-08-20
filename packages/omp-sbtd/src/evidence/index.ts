import { createHash } from "node:crypto";
import { lstat, readdir, readFile, realpath } from "node:fs/promises";
import { relative, resolve, sep } from "node:path";
import { z } from "zod";

/**
 * Validation evidence observer (P1-04/P1-06 consumer).
 *
 * Reuses the promoted upstream validator semantics: v2 scenario traceability
 * is decided exclusively by the embedded Kit's
 * `project-validation/scripts/validate_validation_evidence.py` run against
 * SHA-verified report bytes. This module adds only host-side duties the
 * validator deliberately does not perform: envelope discovery, current
 * revision binding (git HEAD/worktree), and a compact hash-bound descriptor
 * for session persistence. It never invents a private mapping, never trusts
 * sidecar claims alone, and fails closed when the validator is unavailable.
 */

export interface EvidenceProcessResult {
  readonly stdout: string;
  readonly stderr: string;
  readonly code: number | null;
  readonly killed: boolean;
}

export interface EvidenceProcess {
  exec(
    command: string,
    args: readonly string[],
    options: { readonly cwd: string; readonly timeout: number },
  ): Promise<EvidenceProcessResult>;
}

export interface RevisionObservation {
  /** Current HEAD commit (full lowercase hex), or null when unknown. */
  readonly commit: string | null;
  readonly worktreeDirty: boolean;
}

export type RevisionObserver = (
  projectRoot: string,
) => Promise<RevisionObservation>;

export interface ScenarioLinkFingerprint {
  readonly sourceLocatorDigest: string;
  readonly reportSha256: string;
  readonly reportFormat: "junit-xml-v1" | "playwright-json-v1";
}

/** Compact, hash-bound record of a verified evidence envelope (v1 persist). */
export interface ValidationEvidenceDescriptorInput {
  readonly descriptorVersion: 1;
  readonly evidenceVersion: 1 | 2;
  readonly sidecarPath: string;
  readonly sidecarSha256: string;
  readonly repositoryKey: string;
  readonly sourceRef: string;
  readonly sourceCommit: string;
  readonly scenarioLinks: ScenarioLinkFingerprint[];
  readonly verifiedAt: string;
}

export interface ValidationEvidenceObservation {
  readonly found: boolean;
  readonly envelopePath?: string | undefined;
  readonly version?: 1 | 2 | undefined;
  /** A current source locator is attributable to this repository/revision. */
  readonly specificationTraceable: boolean;
  /** The semantic validator fully verified the linked report evidence. */
  readonly executionVerified: boolean;
  /** The evidence attests the current HEAD revision. */
  readonly revisionCurrent: boolean;
  /** Exact, clean revision binding suitable for release attestation. */
  readonly exactRevision: boolean;
  readonly evidenceSource?: string | undefined;
  readonly sourceRevision?: string | undefined;
  readonly environmentAlignment?: string | undefined;
  readonly evidencePublication?: string | undefined;
  readonly e2eMode?: string | undefined;
  readonly descriptor?: ValidationEvidenceDescriptorInput | undefined;
  readonly code?: string | undefined;
  readonly message?: string | undefined;
}

const notFound: ValidationEvidenceObservation = {
  found: false,
  specificationTraceable: false,
  executionVerified: false,
  revisionCurrent: false,
  exactRevision: false,
  code: "EVIDENCE_NOT_FOUND",
  message: "no validation evidence envelope was found",
};

const MAX_ENVELOPE_BYTES = 256 * 1024;
const VALIDATOR_TIMEOUT_MS = 30_000;

const skippedDirectories: Readonly<Record<string, true>> = {
  node_modules: true,
  ".git": true,
  ".hg": true,
  ".svn": true,
  dist: true,
};

const evidenceSourceValues = [
  "developer-local",
  "ci",
  "knowledge-server",
] as const;
const sourceRevisionValues = ["exact", "dirty", "unknown"] as const;
const environmentAlignmentValues = [
  "verified",
  "unverified",
  "mismatch",
  "not-needed",
] as const;
const evidencePublicationValues = [
  "local-only",
  "published",
  "blocked",
  "not-configured",
] as const;
const e2eModeValues = [
  "full-stack",
  "contract-backed",
  "mock-backed",
  "app-mocked",
  "smoke-only",
  "backend-only",
  "blocked",
  "not-needed",
] as const;

/** Lenient fact extraction; authoritative validation stays with the validator. */
const envelopeFactsSchema = z
  .object({
    schemaVersion: z.union([z.literal(1), z.literal(2)]),
    evidenceSource: z.enum(evidenceSourceValues),
    sourceRevision: z.enum(sourceRevisionValues),
    environmentAlignment: z.enum(environmentAlignmentValues),
    evidencePublication: z.enum(evidencePublicationValues),
    e2eMode: z.enum(e2eModeValues),
    repository: z
      .object({
        repositoryKey: z.string().min(1),
        sourceRef: z.string().min(1),
        sourceCommit: z.string().nullable().optional(),
        worktreeState: z.enum(["clean", "dirty", "unknown"]),
      })
      .passthrough(),
    reports: z.array(
      z
        .object({
          path: z.string().min(1),
          sha256: z.string(),
          status: z.enum(["passed", "failed", "blocked", "skipped"]),
          reportFormat: z.string().optional(),
        })
        .passthrough(),
    ),
    scenarioLinks: z
      .array(
        z
          .object({
            sourceLocatorDigest: z.string(),
            reportSha256: z.string(),
            reportFormat: z.enum(["junit-xml-v1", "playwright-json-v1"]),
          })
          .passthrough(),
      )
      .optional(),
  })
  .passthrough();

type EnvelopeFacts = z.infer<typeof envelopeFactsSchema>;

class EvidenceRejection extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

function posixRelative(path: string): string {
  if (path.trim().length === 0)
    throw new EvidenceRejection("UNSAFE_PATH", "path is empty");
  const candidate = path.replaceAll("\\", "/");
  if (candidate.startsWith("/") || candidate.startsWith("~"))
    throw new EvidenceRejection(
      "UNSAFE_PATH",
      `absolute path rejected: ${path}`,
    );
  const parts = candidate
    .split("/")
    .filter((part) => part !== "" && part !== ".");
  if (parts.length === 0 || parts.includes(".."))
    throw new EvidenceRejection("UNSAFE_PATH", `path escape rejected: ${path}`);
  return parts.join("/");
}

async function resolveSafe(
  root: string,
  relativePath: string,
): Promise<string> {
  const rel = posixRelative(relativePath);
  const resolvedRoot = await realpath(root);
  const target = resolve(resolvedRoot, rel);
  const resolvedTarget = await realpath(target).catch(() => target);
  if (
    resolvedTarget !== resolvedRoot &&
    !resolvedTarget.startsWith(`${resolvedRoot}${sep}`)
  )
    throw new EvidenceRejection(
      "UNSAFE_PATH",
      `symlink or path escape: ${rel}`,
    );
  return target;
}

async function regularFileBytes(
  root: string,
  relativePath: string,
): Promise<Buffer> {
  const target = await resolveSafe(root, relativePath);
  const details = await lstat(target).catch(() => undefined);
  if (details === undefined || !details.isFile() || details.isSymbolicLink())
    throw new EvidenceRejection(
      "UNSAFE_PATH",
      `not a regular file: ${relativePath}`,
    );
  return readFile(target);
}

async function discoverEnvelopes(root: string): Promise<string[]> {
  const found: string[] = [];
  const walk = async (directory: string): Promise<void> => {
    const entries = await readdir(directory, {
      withFileTypes: true,
    }).catch(() => []);
    for (const entry of entries) {
      const path = resolve(directory, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        if (skippedDirectories[entry.name] === true) continue;
        await walk(path);
        continue;
      }
      if (!entry.isFile() || !entry.name.endsWith(".evidence.json")) continue;
      const details = await lstat(path).catch(() => undefined);
      if (
        details === undefined ||
        !details.isFile() ||
        details.isSymbolicLink() ||
        details.size > MAX_ENVELOPE_BYTES
      )
        continue;
      found.push(relative(root, path).split(sep).join("/"));
    }
  };
  await walk(root);
  return found.sort();
}

interface ValidatorResult {
  readonly ok: boolean;
  readonly code?: string | undefined;
  readonly message?: string | undefined;
}

const validatorOutputSchema = z.object({
  ok: z.boolean(),
  code: z.string().optional(),
  message: z.string().optional(),
});

async function runValidator(
  process: EvidenceProcess,
  validatorScript: string,
  envelopePath: string,
  root: string,
  version: 1 | 2,
): Promise<ValidatorResult> {
  const args = [
    validatorScript,
    "--envelope",
    envelopePath,
    "--schema-version",
    String(version),
    ...(version === 2 ? ["--root", root] : []),
  ];
  let result: EvidenceProcessResult;
  try {
    result = await process.exec("python3", args, {
      cwd: root,
      timeout: VALIDATOR_TIMEOUT_MS,
    });
  } catch {
    return {
      ok: false,
      code: "VALIDATOR_UNAVAILABLE",
      message: "python3 validation evidence validator could not run",
    };
  }
  const parsed = validatorOutputSchema.safeParse(
    (() => {
      try {
        return JSON.parse(result.stdout);
      } catch {
        return undefined;
      }
    })(),
  );
  if (!parsed.success)
    return {
      ok: false,
      code: "VALIDATOR_UNAVAILABLE",
      message: `validator did not produce a verdict (exit ${result.code ?? "null"})`,
    };
  return parsed.data.ok
    ? { ok: true }
    : {
        ok: false,
        code: parsed.data.code ?? "SCHEMA_INVALID",
        message: parsed.data.message,
      };
}

/** Codes raised before scenario links are checked: specification-stage failures. */
const specificationStageCodes: Readonly<Record<string, true>> = {
  SCHEMA_INVALID: true,
  DUPLICATE_LINK: true,
  REVISION_MISMATCH: true,
  LOCATOR_DIGEST_MISMATCH: true,
  FEATURE_NOT_FILE: true,
  UNSAFE_PATH: true,
};

/**
 * v1 generic compatibility: schema shape (validator) plus recomputed report
 * SHA-256 against file bytes and at least one passed report. Co-membership of
 * featureSources and reports is never scenario traceability.
 */
async function verifyV1Generic(
  root: string,
  envelope: EnvelopeFacts,
): Promise<void> {
  for (const report of envelope.reports) {
    const bytes = await regularFileBytes(root, report.path);
    const actual = createHash("sha256").update(bytes).digest("hex");
    if (actual !== report.sha256.toLowerCase())
      throw new EvidenceRejection(
        "REPORT_HASH_MISMATCH",
        `${report.path} sha256 ${actual} != ${report.sha256}`,
      );
  }
  if (!envelope.reports.some((report) => report.status === "passed"))
    throw new EvidenceRejection(
      "REPORT_NOT_PASSED",
      "v1 envelope has no passed report",
    );
}

async function evaluateEnvelope(
  root: string,
  envelopePath: string,
  options: {
    readonly process: EvidenceProcess;
    readonly validatorScript: string;
    readonly validatorSha256?: string | undefined;
    readonly observeRevision: RevisionObserver;
    readonly observedAt: string;
  },
): Promise<ValidationEvidenceObservation> {
  const base = {
    found: true,
    envelopePath,
    specificationTraceable: false,
    executionVerified: false,
    revisionCurrent: false,
    exactRevision: false,
  };
  const absolutePath = await resolveSafe(root, envelopePath).catch(
    () => undefined,
  );
  const envelopeBytes =
    absolutePath === undefined
      ? undefined
      : await readFile(absolutePath).catch(() => undefined);
  const parsedEnvelope = (() => {
    if (envelopeBytes === undefined) return undefined;
    try {
      return envelopeFactsSchema.safeParse(
        JSON.parse(envelopeBytes.toString("utf8")),
      );
    } catch {
      return undefined;
    }
  })();
  if (
    absolutePath === undefined ||
    envelopeBytes === undefined ||
    parsedEnvelope?.success !== true
  )
    return {
      ...base,
      code: "SCHEMA_INVALID",
      message: "envelope is unreadable or not a v1/v2 evidence envelope",
    };
  const envelope = parsedEnvelope.data;
  const facts = {
    evidenceSource: envelope.evidenceSource,
    sourceRevision: envelope.sourceRevision,
    environmentAlignment: envelope.environmentAlignment,
    evidencePublication: envelope.evidencePublication,
    e2eMode: envelope.e2eMode,
  };
  if (options.validatorSha256 !== undefined) {
    const scriptBytes = await readFile(options.validatorScript).catch(
      () => undefined,
    );
    if (
      scriptBytes === undefined ||
      createHash("sha256").update(scriptBytes).digest("hex") !==
        options.validatorSha256
    )
      return {
        ...base,
        ...facts,
        version: envelope.schemaVersion,
        code: "VALIDATOR_UNTRUSTED",
        message:
          "embedded validation evidence validator failed integrity check",
      };
  }
  const verdict = await runValidator(
    options.process,
    options.validatorScript,
    absolutePath,
    root,
    envelope.schemaVersion,
  );
  let specificationTraceable = false;
  let executionVerified = false;
  let code = verdict.code;
  let message = verdict.message;
  if (verdict.ok && envelope.schemaVersion === 2) {
    specificationTraceable = true;
    executionVerified = true;
  } else if (verdict.ok) {
    try {
      await verifyV1Generic(root, envelope);
      executionVerified = true;
    } catch (error) {
      if (error instanceof EvidenceRejection) {
        code = error.code;
        message = error.message;
      } else {
        code = "UNSAFE_PATH";
        message = "v1 report verification failed";
      }
    }
  } else if (
    envelope.schemaVersion === 2 &&
    specificationStageCodes[code ?? ""] !== true
  )
    // The validator passed the locator stage and failed at link/report stage:
    // the specification side is traceable, the execution side is not.
    specificationTraceable = true;
  const revision = await options.observeRevision(root).catch(() => ({
    commit: null,
    worktreeDirty: true,
  }));
  const envelopeCommit = envelope.repository.sourceCommit?.trim().toLowerCase();
  const commitMatches =
    revision.commit !== null &&
    envelopeCommit !== undefined &&
    envelopeCommit === revision.commit;
  // Evidence recorded as exact cannot attest a worktree that has since changed.
  const revisionCurrent =
    commitMatches &&
    !(revision.worktreeDirty && envelope.sourceRevision !== "dirty");
  const exactRevision =
    revisionCurrent &&
    envelope.sourceRevision === "exact" &&
    envelope.repository.worktreeState === "clean" &&
    !revision.worktreeDirty;
  if (executionVerified && !revisionCurrent) {
    code = "STALE_REVISION";
    message =
      "evidence does not attest the current repository revision or worktree";
  }
  const descriptor: ValidationEvidenceDescriptorInput | undefined =
    executionVerified && revisionCurrent && envelopeCommit !== undefined
      ? {
          descriptorVersion: 1,
          evidenceVersion: envelope.schemaVersion,
          sidecarPath: envelopePath,
          sidecarSha256: createHash("sha256")
            .update(envelopeBytes)
            .digest("hex"),
          repositoryKey: envelope.repository.repositoryKey,
          sourceRef: envelope.repository.sourceRef,
          sourceCommit: envelopeCommit,
          scenarioLinks: (envelope.scenarioLinks ?? []).map((link) => ({
            sourceLocatorDigest: link.sourceLocatorDigest,
            reportSha256: link.reportSha256.toLowerCase(),
            reportFormat: link.reportFormat,
          })),
          verifiedAt: options.observedAt,
        }
      : undefined;
  return {
    ...base,
    ...facts,
    version: envelope.schemaVersion,
    specificationTraceable,
    executionVerified,
    revisionCurrent,
    exactRevision,
    descriptor,
    code,
    message,
  };
}

export async function observeValidationEvidence(options: {
  readonly projectRoot: string;
  readonly validatorScript: string;
  /** Manifest SHA-256 of the embedded validator script (integrity binding). */
  readonly validatorSha256?: string | undefined;
  readonly process: EvidenceProcess;
  readonly observeRevision: RevisionObserver;
  readonly observedAt: string;
  /** Explicit envelope paths (POSIX, repository-relative); bypasses discovery. */
  readonly envelopePaths?: readonly string[] | undefined;
}): Promise<ValidationEvidenceObservation> {
  const envelopes = (
    options.envelopePaths === undefined
      ? await discoverEnvelopes(options.projectRoot).catch(() => [])
      : options.envelopePaths.map((path) => posixRelative(path))
  ).sort();
  if (envelopes.length === 0) return notFound;
  let firstRejection: ValidationEvidenceObservation | undefined;
  for (const envelopePath of envelopes) {
    const observation = await evaluateEnvelope(
      options.projectRoot,
      envelopePath,
      options,
    );
    if (observation.executionVerified && observation.revisionCurrent)
      return observation;
    if (firstRejection === undefined) firstRejection = observation;
  }
  return firstRejection ?? notFound;
}
