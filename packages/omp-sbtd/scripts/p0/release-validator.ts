import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import {
  lstat,
  mkdir,
  readdir,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { gunzipSync } from "node:zlib";
import { z } from "zod";
import {
  type EmbeddedKitManifestV2,
  verifyEmbeddedKitManifest,
} from "../../src/kit/manifest.ts";
import {
  hasForbiddenLocalPath,
  hasSensitiveFieldName,
  hasSensitiveText,
} from "./sanitization.ts";

const HASH_PATTERN = /^[a-f0-9]{64}$/;
const RUN_ID_PATTERN = /^[a-z0-9][a-z0-9-]{2,127}$/;
const VALUE_STUDY_CATEGORIES = [
  "docs-config",
  "user-visible-feature",
  "existing-behavior-bug",
  "existing-production-code",
  "data-schema-async",
  "production-integration",
  "web-e2e",
  "mobile-tool-state",
  "cross-repo-contract-only",
  "session-resume-compaction",
] as const;
const ROUTE_IDS = [
  "small-direct-change",
  "bugfix",
  "bdd-user-visible-change",
  "trellis-managed-task",
  "legacy-safe-change",
  "refactoring-pass",
  "data-design-risk",
  "web-runtime-diagnostics",
  "web-e2e-regression",
  "mobile-e2e",
  "release-readiness",
  "review",
] as const;
const REQUIRED_GATE_IDS = [
  "bdd",
  "tdd",
  "legacy-change-safety",
  "refactoring-pass",
  "ddia-data-design",
  "ddd-distilled-modeling",
  "release-readiness",
] as const;
const RETRYABLE_FAILURES = new Set([
  "host-start",
  "transport-interruption",
  "runtime-crash",
]);

const hashSchema = z.string().regex(HASH_PATTERN, "expected a SHA-256 digest");
export const runIdSchema = z.string().regex(RUN_ID_PATTERN, "invalid run ID");
const isoDateSchema = z.string().datetime({ offset: true });
const relativePathSchema = z
  .string()
  .min(1)
  .refine(
    (value) =>
      !isAbsolute(value) &&
      !value
        .split(/[\\/]/)
        .some((segment) => segment === "" || segment === ".."),
    "path must be a safe non-empty relative path",
  );
const statusSchema = z.enum(["passed", "failed", "blocked", "not-applicable"]);
const routeCostSchema = z.enum(["light", "standard", "heavy"]);
const blockerSchema = z
  .object({
    code: z.string().min(1),
    reason: z.string().min(1).optional(),
    recovery: z.string().min(1),
  })
  .strict();

export class P0ValidationError extends Error {
  readonly code: string;
  readonly recovery: string;
  readonly details: Readonly<Record<string, unknown>>;

  constructor(
    code: string,
    message: string,
    recovery: string,
    details: Readonly<Record<string, unknown>> = {},
  ) {
    super(message);
    this.name = "P0ValidationError";
    this.code = code;
    this.recovery = recovery;
    this.details = details;
  }
}

export interface P0DirectoryEntry {
  readonly name: string;
  readonly kind: "file" | "directory" | "symlink" | "other";
}

export interface P0FileSystem {
  readonly readText: (path: string) => Promise<string>;
  readonly readBytes?: (path: string) => Promise<Uint8Array>;
  readonly writeText: (path: string, content: string) => Promise<void>;
  readonly makeDirectory: (path: string) => Promise<void>;
  readonly move: (from: string, to: string) => Promise<void>;
  readonly remove: (path: string) => Promise<void>;
  readonly list: (path: string) => Promise<readonly P0DirectoryEntry[]>;
  readonly inspect: (path: string) => Promise<P0DirectoryEntry["kind"]>;
}

export function createNodeFileSystem(): P0FileSystem {
  return {
    readText: (path) => readFile(path, "utf8"),
    readBytes: (path) => readFile(path),
    writeText: async (path, content) => {
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, content, "utf8");
    },
    makeDirectory: async (path) => {
      await mkdir(path, { recursive: true });
    },
    move: (from, to) => rename(from, to),
    remove: async (path) => {
      await rm(path, { force: true, recursive: true });
    },
    list: async (path) => {
      const entries = await readdir(path, { withFileTypes: true });
      return entries.map((entry) => ({
        name: entry.name,
        kind: entry.isFile()
          ? "file"
          : entry.isDirectory()
            ? "directory"
            : entry.isSymbolicLink()
              ? "symlink"
              : "other",
      }));
    },
    inspect: async (path) => {
      const entry = await lstat(path);
      if (entry.isFile()) return "file";
      if (entry.isDirectory()) return "directory";
      if (entry.isSymbolicLink()) return "symlink";
      return "other";
    },
  };
}

function digest(value: string | Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

async function digestFile(path: string, files: P0FileSystem): Promise<string> {
  return digest(
    files.readBytes === undefined
      ? await files.readText(path)
      : await files.readBytes(path),
  );
}

function safeRelativePath(root: string, candidate: string): string {
  const normalizedRoot = resolve(root);
  const normalizedCandidate = resolve(candidate);
  const pathFromRoot = relative(normalizedRoot, normalizedCandidate);
  if (
    pathFromRoot === "" ||
    pathFromRoot.startsWith(`..${sep}`) ||
    pathFromRoot === ".." ||
    isAbsolute(pathFromRoot)
  )
    throw new P0ValidationError(
      "UNSAFE_PATH",
      "P0 validation refused a path outside its declared root",
      "Correct the manifest path so it stays below the declared validation root.",
      { root: normalizedRoot, candidate: normalizedCandidate },
    );
  return normalizedCandidate;
}

function parsedJson<T>(schema: z.ZodType<T>, raw: string, context: string): T {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new P0ValidationError(
      "JSON_INVALID",
      `${context} is not valid JSON`,
      "Regenerate the versioned validation asset from its source of truth.",
    );
  }
  const parsed = schema.safeParse(value);
  if (parsed.success) return parsed.data;
  throw new P0ValidationError(
    "SCHEMA_INVALID",
    `${context} does not satisfy the strict P0 schema`,
    "Repair the invalid record or create a new versioned asset; do not edit an immutable run in place.",
    { issues: parsed.error.issues.map((issue) => issue.message) },
  );
}

function sortedJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortedJson);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, sortedJson(nested)]),
    );
  }
  return value;
}

function stableJson(value: unknown): string {
  return `${JSON.stringify(sortedJson(value), null, 2)}\n`;
}

const SEMVER_PATTERN =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
const RC_VERSION_PATTERN =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-rc\.(0|[1-9]\d*)(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
const npmPackageNameSchema = z
  .string()
  .min(1)
  .max(214)
  .regex(
    /^(?:@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*$/,
    "invalid npm package name",
  );
const packageVersionSchema = z
  .string()
  .regex(SEMVER_PATTERN, "invalid semantic package version");
export const currentRuntimeVersionSchema = packageVersionSchema;
const distTagSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[a-z0-9][a-z0-9._-]*$/, "invalid dist-tag");

export const candidateIdentitySchema = z
  .object({
    sourceTreeSha256: hashSchema,
    packedTarballSha256: hashSchema,
    packageName: npmPackageNameSchema,
    packageVersion: packageVersionSchema,
  })
  .strict();
export type CandidateIdentity = z.infer<typeof candidateIdentitySchema>;

export const candidateRecordSchema = z
  .object({
    schemaVersion: z.literal(1),
    candidate: candidateIdentitySchema,
    channel: z.enum(["rc", "stable"]),
    distTag: distTagSchema.optional(),
    createdAt: isoDateSchema,
  })
  .strict();
export type CandidateRecord = z.infer<typeof candidateRecordSchema>;

const candidateEvidenceStatusSchema = z.enum(["passed", "failed", "blocked"]);
const candidateEvidenceBaseSchema = z
  .object({
    schemaVersion: z.literal(1),
    evidenceId: runIdSchema,
    candidate: candidateIdentitySchema,
    status: candidateEvidenceStatusSchema,
    recordedAt: isoDateSchema,
    reportSha256: hashSchema,
    blockers: z.array(blockerSchema).max(32),
  })
  .strict();
const compatibilityProtocolSchema = z
  .object({
    currentRuntimeVersion: currentRuntimeVersionSchema,
  })
  .strict();
const valueProtocolSchema = z
  .object({
    armCount: z.literal(40),
    pairCount: z.literal(20),
    completionProvenanceSha256: hashSchema,
  })
  .strict();
export const candidateEvidenceSchema = z.discriminatedUnion("gate", [
  candidateEvidenceBaseSchema.extend({ gate: z.literal("technical") }).strict(),
  candidateEvidenceBaseSchema.extend({ gate: z.literal("package") }).strict(),
  candidateEvidenceBaseSchema
    .extend({
      gate: z.literal("compatibility"),
      protocol: compatibilityProtocolSchema,
    })
    .strict(),
  candidateEvidenceBaseSchema
    .extend({ gate: z.literal("value"), protocol: valueProtocolSchema })
    .strict(),
]);
export type CandidateEvidence = z.infer<typeof candidateEvidenceSchema>;

const candidateObservationEnvironmentSchema = z
  .record(z.string().min(1).max(128), z.string().min(1).max(512))
  .refine(
    (environment) => Object.keys(environment).length <= 16,
    "observation environment has too many fields",
  );

export const candidateObservationSchema = z
  .object({
    schemaVersion: z.literal(1),
    observationId: runIdSchema,
    candidate: candidateIdentitySchema,
    runtimeVersion: currentRuntimeVersionSchema,
    outcome: z.enum(["passed", "failed", "blocked"]),
    blocker: blockerSchema.optional(),
    environment: candidateObservationEnvironmentSchema.optional(),
    createdAt: isoDateSchema,
  })
  .strict();
export type CandidateObservation = z.infer<typeof candidateObservationSchema>;

export const candidateEquivalenceAttestationSchema = z
  .object({
    schemaVersion: z.literal(1),
    rcCandidate: candidateIdentitySchema,
    stableCandidate: candidateIdentitySchema,
    normalizedPayloadSha256: hashSchema,
    attestationSha256: hashSchema,
    createdAt: isoDateSchema,
  })
  .strict();
export type CandidateEquivalenceAttestation = z.infer<
  typeof candidateEquivalenceAttestationSchema
>;

export interface PackedPayloadFile {
  readonly path: string;
  readonly kind: "file" | "directory" | "symlink" | "other";
  readonly executable: boolean;
  readonly bytes: Uint8Array;
}

export interface CandidateEquivalenceVerificationInput {
  readonly rcCandidate: CandidateIdentity;
  readonly stableCandidate: CandidateIdentity;
  readonly rcFiles: readonly PackedPayloadFile[];
  readonly stableFiles: readonly PackedPayloadFile[];
  readonly createdAt?: string;
}

function isRcPackageVersion(version: string): boolean {
  return RC_VERSION_PATTERN.test(version);
}

function isStablePackageVersion(version: string): boolean {
  return SEMVER_PATTERN.test(version) && !version.includes("-");
}

function parseCandidateIdentity(
  input: unknown,
  context: string,
): CandidateIdentity {
  assertSanitizedValue(input, context);
  const parsed = candidateIdentitySchema.safeParse(input);
  if (parsed.success) return parsed.data;
  throw new P0ValidationError(
    "CANDIDATE_SCHEMA_INVALID",
    "Release candidate identity violates its strict schema.",
    "Provide the exact source-tree digest, packed-tarball digest, package name, and semantic version.",
    { issues: parsed.error.issues.map((issue) => issue.message) },
  );
}

export function candidateIdentitySha256(input: unknown): string {
  return digest(
    stableJson(parseCandidateIdentity(input, "candidate-identity")),
  );
}

function assertCandidateRecord(input: unknown): CandidateRecord {
  assertSanitizedValue(input, "candidate-record");
  const parsed = candidateRecordSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "CANDIDATE_RECORD_SCHEMA_INVALID",
      "Candidate admission record violates its strict schema.",
      "Create a new sanitized candidate record with only documented fields.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const record = parsed.data;
  if (
    record.channel === "rc" &&
    (!isRcPackageVersion(record.candidate.packageVersion) ||
      record.distTag === undefined ||
      record.distTag === "latest")
  )
    throw new P0ValidationError(
      "RC_CANDIDATE_INVALID",
      "RC admission requires an immutable <semver>-rc.<n> candidate and a non-latest dist-tag.",
      "Create a new RC candidate with an rc.<n> version and a non-latest dist-tag.",
    );
  if (
    record.channel === "stable" &&
    (!isStablePackageVersion(record.candidate.packageVersion) ||
      record.distTag !== undefined)
  )
    throw new P0ValidationError(
      "STABLE_CANDIDATE_INVALID",
      "Stable candidate records require a stable semantic version and no publication dist-tag.",
      "Create a stable candidate record without a prerelease tag or publication tag.",
    );
  return record;
}

function assertCandidateEvidence(input: unknown): CandidateEvidence {
  assertSanitizedValue(input, "candidate-evidence");
  const parsed = candidateEvidenceSchema.safeParse(input);
  if (parsed.success) {
    if (parsed.data.status === "passed" && parsed.data.blockers.length > 0)
      throw new P0ValidationError(
        "CANDIDATE_EVIDENCE_SCHEMA_INVALID",
        "Passing candidate evidence cannot carry blockers.",
        "Append a new failing or blocked record with typed blockers instead.",
      );
    if (parsed.data.status !== "passed" && parsed.data.blockers.length === 0)
      throw new P0ValidationError(
        "CANDIDATE_EVIDENCE_SCHEMA_INVALID",
        "Failed or blocked candidate evidence requires at least one typed blocker.",
        "Record the failure code, reason, and recovery before appending evidence.",
      );
    return parsed.data;
  }
  throw new P0ValidationError(
    "CANDIDATE_EVIDENCE_SCHEMA_INVALID",
    "Candidate evidence violates its strict gate-specific schema.",
    "Create a new exact-candidate evidence record with the complete required protocol fields.",
    { issues: parsed.error.issues.map((issue) => issue.message) },
  );
}

function assertCandidateObservation(input: unknown): CandidateObservation {
  assertSanitizedValue(input, "candidate-observation");
  const parsed = candidateObservationSchema.safeParse(input);
  if (parsed.success) {
    if (parsed.data.outcome === "blocked" && parsed.data.blocker === undefined)
      throw new P0ValidationError(
        "OBSERVATION_SCHEMA_INVALID",
        "Blocked observations require a typed blocker.",
        "Record the observed blocker code and recovery without adding sensitive diagnostics.",
      );
    if (parsed.data.outcome === "passed" && parsed.data.blocker !== undefined)
      throw new P0ValidationError(
        "OBSERVATION_SCHEMA_INVALID",
        "Passing observations cannot carry a blocker.",
        "Append a separate failed or blocked observation for the reported blocker.",
      );
    return parsed.data;
  }
  throw new P0ValidationError(
    "OBSERVATION_SCHEMA_INVALID",
    "Candidate observation violates its strict sanitized schema.",
    "Append a new observation containing only the candidate, exact Runtime, typed outcome, and safe environment metadata.",
    { issues: parsed.error.issues.map((issue) => issue.message) },
  );
}

function attestationDigest(
  input: Readonly<{
    rcCandidate: CandidateIdentity;
    stableCandidate: CandidateIdentity;
    normalizedPayloadSha256: string;
  }>,
): string {
  return digest(
    stableJson({
      schemaVersion: 1,
      rcCandidate: input.rcCandidate,
      stableCandidate: input.stableCandidate,
      normalizedPayloadSha256: input.normalizedPayloadSha256,
    }),
  );
}

function assertCandidateEquivalenceAttestation(
  input: unknown,
): CandidateEquivalenceAttestation {
  assertSanitizedValue(input, "candidate-equivalence-attestation");
  const parsed = candidateEquivalenceAttestationSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_SCHEMA_INVALID",
      "Candidate-equivalence attestation violates its strict schema.",
      "Create a new verifier-produced attestation from the exact RC and stable packed payloads.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const attestation = parsed.data;
  if (
    !isRcPackageVersion(attestation.rcCandidate.packageVersion) ||
    !isStablePackageVersion(attestation.stableCandidate.packageVersion)
  )
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "An equivalence attestation must bind one RC candidate to one stable candidate.",
      "Select an <semver>-rc.<n> source candidate and a stable target candidate.",
    );
  const expectedDigest = attestationDigest(attestation);
  if (expectedDigest !== attestation.attestationSha256)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "Candidate-equivalence attestation digest does not match its exact candidate pair and normalized payload.",
      "Discard the attestation and rerun packed payload verification for the exact candidates.",
    );
  return attestation;
}

type ParsedJsonNode =
  | Readonly<{
      kind: "object";
      start: number;
      end: number;
      properties: ReadonlyMap<string, ParsedJsonNode>;
    }>
  | Readonly<{
      kind: "array";
      start: number;
      end: number;
      items: readonly ParsedJsonNode[];
    }>
  | Readonly<{
      kind: "string";
      start: number;
      end: number;
      value: string;
    }>
  | Readonly<{ kind: "primitive"; start: number; end: number }>;

function parseJsonSource(source: string, context: string): ParsedJsonNode {
  let index = 0;
  const fail = (message: string): never => {
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      `${context} is not a strictly parseable JSON payload: ${message}`,
      "Regenerate the packed artifact; version-only metadata exceptions require valid JSON.",
    );
  };
  const skipWhitespace = (): void => {
    while (/\s/u.test(source[index] ?? "")) index += 1;
  };
  const parseString = (): Extract<ParsedJsonNode, { kind: "string" }> => {
    const start = index;
    if (source[index] !== '"') fail("expected a JSON string");
    index += 1;
    let closed = false;
    while (index < source.length) {
      const character = source[index];
      index += 1;
      if (character === "\\") {
        if (index >= source.length) fail("unterminated escape");
        index += 1;
        continue;
      }
      if (character === '"') {
        closed = true;
        break;
      }
      if ((character?.charCodeAt(0) ?? 0) < 0x20)
        fail("unescaped control character");
    }
    if (!closed) fail("unterminated JSON string");
    const raw = source.slice(start, index);
    try {
      return {
        kind: "string",
        start,
        end: index,
        value: JSON.parse(raw) as string,
      };
    } catch {
      fail("invalid JSON string escape");
    }
  };
  const parseValue = (): ParsedJsonNode => {
    skipWhitespace();
    const start = index;
    const character = source[index];
    if (character === '"') return parseString();
    if (character === "{") {
      index += 1;
      skipWhitespace();
      const properties = new Map<string, ParsedJsonNode>();
      if (source[index] === "}") {
        index += 1;
        return { kind: "object", start, end: index, properties };
      }
      while (true) {
        skipWhitespace();
        const key = parseString();
        skipWhitespace();
        if (source[index] !== ":") fail("missing object key separator");
        index += 1;
        const value = parseValue();
        if (properties.has(key.value)) fail("duplicate object key");
        properties.set(key.value, value);
        skipWhitespace();
        if (source[index] === "}") {
          index += 1;
          return { kind: "object", start, end: index, properties };
        }
        if (source[index] !== ",") fail("missing object entry separator");
        index += 1;
      }
    }
    if (character === "[") {
      index += 1;
      skipWhitespace();
      const items: ParsedJsonNode[] = [];
      if (source[index] === "]") {
        index += 1;
        return { kind: "array", start, end: index, items };
      }
      while (true) {
        items.push(parseValue());
        skipWhitespace();
        if (source[index] === "]") {
          index += 1;
          return { kind: "array", start, end: index, items };
        }
        if (source[index] !== ",") fail("missing array entry separator");
        index += 1;
      }
    }
    const literalMatch =
      /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(
        source.slice(index),
      );
    if (literalMatch === null) fail("invalid JSON value");
    index += literalMatch[0].length;
    const raw = source.slice(start, index);
    try {
      JSON.parse(raw);
    } catch {
      fail("invalid primitive value");
    }
    return { kind: "primitive", start, end: index };
  };
  const root = parseValue();
  skipWhitespace();
  if (index !== source.length) fail("trailing bytes");
  return root;
}

function requiredJsonProperty(
  object: ParsedJsonNode,
  name: string,
  context: string,
): ParsedJsonNode {
  if (object.kind !== "object")
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      `${context} must be a JSON object.`,
      "Regenerate the packed metadata using the supported package and SPDX JSON shape.",
    );
  const value = object.properties.get(name);
  if (value !== undefined) return value;
  throw new P0ValidationError(
    "CANDIDATE_EQUIVALENCE_INVALID",
    `${context} is missing required parsed field ${name}.`,
    "Regenerate the packed metadata with the required version identity fields.",
  );
}

function requiredJsonString(
  object: ParsedJsonNode,
  name: string,
  context: string,
): Extract<ParsedJsonNode, { kind: "string" }> {
  const value = requiredJsonProperty(object, name, context);
  if (value.kind === "string") return value;
  throw new P0ValidationError(
    "CANDIDATE_EQUIVALENCE_INVALID",
    `${context}.${name} must be a JSON string.`,
    "Regenerate the packed metadata with the required parsed version identity field.",
  );
}

function decodePackedJson(bytes: Uint8Array, context: string): string {
  const buffer = Buffer.from(bytes);
  const source = buffer.toString("utf8");
  if (!Buffer.from(source, "utf8").equals(buffer))
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      `${context} is not valid UTF-8 JSON.`,
      "Regenerate the packed artifact; parsed version metadata must be valid UTF-8 JSON.",
    );
  return source;
}

function replaceJsonStringNodes(
  source: string,
  replacements: readonly Readonly<{
    node: Extract<ParsedJsonNode, { kind: "string" }>;
    marker: string;
  }>[],
): Uint8Array {
  const ordered = [...replacements].sort(
    (left, right) => right.node.start - left.node.start,
  );
  let normalized = source;
  let previousStart = source.length + 1;
  for (const { node, marker } of ordered) {
    if (node.end > previousStart)
      throw new P0ValidationError(
        "CANDIDATE_EQUIVALENCE_INVALID",
        "Parsed version metadata fields overlap.",
        "Regenerate the packed artifact with ordinary non-overlapping JSON fields.",
      );
    normalized = `${normalized.slice(0, node.start)}${marker}${normalized.slice(node.end)}`;
    previousStart = node.start;
  }
  return Buffer.from(normalized, "utf8");
}

function normalizePackageManifestPayload(
  bytes: Uint8Array,
  candidate: CandidateIdentity,
): Uint8Array {
  const source = decodePackedJson(bytes, "package/package.json");
  const root = parseJsonSource(source, "package/package.json");
  const name = requiredJsonString(root, "name", "package/package.json");
  if (name.value !== candidate.packageName)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "package/package.json name does not match its candidate identity.",
      "Repack the exact candidate before comparing payload equivalence.",
    );
  const version = requiredJsonString(root, "version", "package/package.json");
  if (version.value !== candidate.packageVersion)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "package/package.json version does not match its candidate identity.",
      "Repack the exact candidate before comparing payload equivalence.",
    );
  return replaceJsonStringNodes(source, [
    { node: version, marker: JSON.stringify("__KPI_PACKAGE_VERSION__") },
  ]);
}

function normalizeSpdxPayload(
  bytes: Uint8Array,
  candidate: CandidateIdentity,
  packageManifestBytes: Uint8Array,
): Uint8Array {
  const source = decodePackedJson(bytes, "package/SBOM.spdx.json");
  const root = parseJsonSource(source, "package/SBOM.spdx.json");
  const documentName = requiredJsonString(
    root,
    "name",
    "package/SBOM.spdx.json",
  );
  if (
    documentName.value !==
    `${candidate.packageName}-${candidate.packageVersion}`
  )
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX document name is not derived exactly from the candidate package identity.",
      "Regenerate the SPDX document for the exact candidate version.",
    );
  const documentNamespace = requiredJsonString(
    root,
    "documentNamespace",
    "package/SBOM.spdx.json",
  );
  if (
    documentNamespace.value !==
    `https://kpi.local/spdx/${candidate.sourceTreeSha256}`
  )
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX document namespace is not derived exactly from the candidate source identity.",
      "Regenerate the SPDX document for the exact candidate source.",
    );
  const packages = requiredJsonProperty(
    root,
    "packages",
    "package/SBOM.spdx.json",
  );
  if (packages.kind !== "array")
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX packages must be an array.",
      "Regenerate the SPDX document using the supported package identity shape.",
    );
  const matchingPackages = packages.items.filter(
    (entry) =>
      entry.kind === "object" &&
      requiredJsonString(entry, "name", "package/SBOM.spdx.json packages")
        .value === candidate.packageName,
  );
  if (matchingPackages.length !== 1)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX must contain exactly one package entry for the candidate package name.",
      "Regenerate the SPDX document with one exact candidate package identity.",
    );
  const versionInfo = requiredJsonString(
    matchingPackages[0] as ParsedJsonNode,
    "versionInfo",
    "package/SBOM.spdx.json candidate package",
  );
  if (versionInfo.value !== candidate.packageVersion)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX package versionInfo does not match its candidate identity.",
      "Regenerate the SPDX document for the exact candidate version.",
    );
  const files = requiredJsonProperty(root, "files", "package/SBOM.spdx.json");
  if (files.kind !== "array")
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX files must be an array.",
      "Regenerate the SPDX document with the packed package file inventory.",
    );
  const packageManifestEntries = files.items.filter((entry) => {
    if (entry.kind !== "object") return false;
    return (
      requiredJsonString(entry, "fileName", "package/SBOM.spdx.json files")
        .value === "./package.json"
    );
  });
  if (packageManifestEntries.length !== 1)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX must contain exactly one checksum entry for package/package.json.",
      "Regenerate the SPDX document with the exact packed package manifest inventory.",
    );
  const checksums = requiredJsonProperty(
    packageManifestEntries[0] as ParsedJsonNode,
    "checksums",
    "package/SBOM.spdx.json package manifest",
  );
  if (checksums.kind !== "array" || checksums.items.length !== 1)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX package/package.json must have one SHA-256 checksum.",
      "Regenerate the SPDX document with one package-manifest checksum.",
    );
  const checksum = checksums.items[0];
  if (checksum === undefined || checksum.kind !== "object")
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX package manifest checksum must be an object.",
      "Regenerate the SPDX document with a structured package-manifest checksum.",
    );
  if (
    requiredJsonString(
      checksum,
      "algorithm",
      "package/SBOM.spdx.json package manifest checksum",
    ).value !== "SHA256"
  )
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX package manifest checksum must use SHA256.",
      "Regenerate the SPDX document with a SHA-256 package-manifest checksum.",
    );
  const checksumValue = requiredJsonString(
    checksum,
    "checksumValue",
    "package/SBOM.spdx.json package manifest checksum",
  );
  if (checksumValue.value !== digest(Buffer.from(packageManifestBytes)))
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "SPDX package manifest checksum does not match the packed package.json bytes.",
      "Regenerate the SPDX document from the exact packed package manifest.",
    );
  return replaceJsonStringNodes(source, [
    {
      node: documentName,
      marker: JSON.stringify("__KPI_SPDX_DOCUMENT_PACKAGE_IDENTITY__"),
    },
    {
      node: documentNamespace,
      marker: JSON.stringify("__KPI_SPDX_SOURCE_IDENTITY__"),
    },
    {
      node: versionInfo,
      marker: JSON.stringify("__KPI_SPDX_PACKAGE_VERSION__"),
    },
    {
      node: checksumValue,
      marker: JSON.stringify("__KPI_SPDX_PACKAGE_MANIFEST_SHA256__"),
    },
  ]);
}

function normalizeDifferingPayload(
  path: string,
  bytes: Uint8Array,
  candidate: CandidateIdentity,
  packageManifestBytes: Uint8Array,
): Uint8Array {
  if (path === "package/package.json")
    return normalizePackageManifestPayload(bytes, candidate);
  if (path === "package/SBOM.spdx.json")
    return normalizeSpdxPayload(bytes, candidate, packageManifestBytes);
  throw new P0ValidationError(
    "CANDIDATE_PAYLOAD_DIFFERENCE",
    `Packed payload differs at ${path}, which is outside the closed parsed version-metadata allowlist.`,
    "Rebuild the stable artifact so every non-version payload byte matches the RC artifact.",
    { path },
  );
}

function normalizedPayloadMap(
  files: readonly PackedPayloadFile[],
  context: string,
): readonly Readonly<{
  path: string;
  kind: "file";
  executable: boolean;
  bytes: Uint8Array;
}>[] {
  let previousPath: string | undefined;
  return files.map((file) => {
    const path = relativePathSchema.safeParse(file.path);
    if (
      !path.success ||
      file.kind !== "file" ||
      !(file.bytes instanceof Uint8Array)
    )
      throw new P0ValidationError(
        "CANDIDATE_PAYLOAD_SCHEMA_INVALID",
        `${context} contains an invalid packed payload file entry.`,
        "Compare only sorted regular files with safe relative paths and raw bytes.",
      );
    if (typeof file.executable !== "boolean")
      throw new P0ValidationError(
        "CANDIDATE_PAYLOAD_SCHEMA_INVALID",
        `${context} contains an invalid executable flag.`,
        "Rebuild the packed file map with explicit regular-file metadata.",
      );
    if (previousPath !== undefined && previousPath >= path.data)
      throw new P0ValidationError(
        "CANDIDATE_PAYLOAD_ORDER_INVALID",
        `${context} is not in strict packed-path order.`,
        "Rebuild the file map in bytewise ascending path order without duplicate paths.",
      );
    previousPath = path.data;
    return {
      path: path.data,
      kind: "file" as const,
      executable: file.executable,
      bytes: file.bytes,
    };
  });
}

function requiredPackedPayloadBytes(
  files: readonly Readonly<{
    path: string;
    kind: "file";
    executable: boolean;
    bytes: Uint8Array;
  }>[],
  path: string,
  context: string,
): Uint8Array {
  const file = files.find((entry) => entry.path === path);
  if (file !== undefined) return file.bytes;
  throw new P0ValidationError(
    "CANDIDATE_PAYLOAD_PATH_MISMATCH",
    `${context} is missing ${path}, required for parsed version-metadata equivalence.`,
    "Rebuild both packed artifacts with the required package metadata files.",
    { path },
  );
}

export function verifyCandidateEquivalence(
  input: CandidateEquivalenceVerificationInput,
): CandidateEquivalenceAttestation {
  const rcCandidate = parseCandidateIdentity(input.rcCandidate, "rc-candidate");
  const stableCandidate = parseCandidateIdentity(
    input.stableCandidate,
    "stable-candidate",
  );
  if (!isRcPackageVersion(rcCandidate.packageVersion))
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "Candidate equivalence source must be an <semver>-rc.<n> package.",
      "Select the exact RC candidate whose protocol evidence may be forwarded.",
    );
  if (!isStablePackageVersion(stableCandidate.packageVersion))
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_INVALID",
      "Candidate equivalence target must be a stable semantic package version.",
      "Select the exact final stable candidate.",
    );
  const rcFiles = normalizedPayloadMap(input.rcFiles, "RC payload");
  const stableFiles = normalizedPayloadMap(input.stableFiles, "stable payload");
  const rcPackageManifestBytes = requiredPackedPayloadBytes(
    rcFiles,
    "package/package.json",
    "RC payload",
  );
  const stablePackageManifestBytes = requiredPackedPayloadBytes(
    stableFiles,
    "package/package.json",
    "stable payload",
  );
  if (rcFiles.length !== stableFiles.length)
    throw new P0ValidationError(
      "CANDIDATE_PAYLOAD_PATH_MISMATCH",
      "RC and stable packed payloads contain different file counts.",
      "Rebuild the stable artifact so it has exactly the RC packed file map.",
      { rcFileCount: rcFiles.length, stableFileCount: stableFiles.length },
    );
  const normalizedFiles: {
    path: string;
    kind: "file";
    executable: boolean;
    sha256: string;
  }[] = [];
  for (let index = 0; index < rcFiles.length; index += 1) {
    const rcFile = rcFiles[index];
    const stableFile = stableFiles[index];
    if (rcFile === undefined || stableFile === undefined) continue;
    if (rcFile.path !== stableFile.path)
      throw new P0ValidationError(
        "CANDIDATE_PAYLOAD_PATH_MISMATCH",
        "RC and stable packed payloads add, delete, or rename a file.",
        "Rebuild the stable artifact so it has the exact RC packed file paths.",
        { rcPath: rcFile.path, stablePath: stableFile.path },
      );
    if (
      rcFile.kind !== stableFile.kind ||
      rcFile.executable !== stableFile.executable
    )
      throw new P0ValidationError(
        "CANDIDATE_PAYLOAD_METADATA_MISMATCH",
        `Packed file metadata differs at ${rcFile.path}.`,
        "Rebuild the stable artifact with identical regular-file class and executable metadata.",
        { path: rcFile.path },
      );
    const rcBytes = Buffer.from(rcFile.bytes);
    const stableBytes = Buffer.from(stableFile.bytes);
    const hasParsedVersionMetadata =
      rcFile.path === "package/package.json" ||
      rcFile.path === "package/SBOM.spdx.json";
    if (hasParsedVersionMetadata) {
      const normalizedRc = normalizeDifferingPayload(
        rcFile.path,
        rcBytes,
        rcCandidate,
        rcPackageManifestBytes,
      );
      const normalizedStable = normalizeDifferingPayload(
        stableFile.path,
        stableBytes,
        stableCandidate,
        stablePackageManifestBytes,
      );
      if (!Buffer.from(normalizedRc).equals(Buffer.from(normalizedStable)))
        throw new P0ValidationError(
          "CANDIDATE_PAYLOAD_DIFFERENCE",
          `Packed payload differs outside the closed parsed version-metadata allowlist at ${rcFile.path}.`,
          "Restore byte-identical non-version payload content before requesting equivalence.",
          { path: rcFile.path },
        );
      normalizedFiles.push({
        path: rcFile.path,
        kind: rcFile.kind,
        executable: rcFile.executable,
        sha256: digest(normalizedRc),
      });
      continue;
    }
    if (!rcBytes.equals(stableBytes))
      throw new P0ValidationError(
        "CANDIDATE_PAYLOAD_DIFFERENCE",
        `Packed payload differs at ${rcFile.path}, which is outside the closed parsed version-metadata allowlist.`,
        "Restore byte-identical non-version payload content before requesting equivalence.",
        { path: rcFile.path },
      );
    normalizedFiles.push({
      path: rcFile.path,
      kind: rcFile.kind,
      executable: rcFile.executable,
      sha256: digest(rcBytes),
    });
  }
  const normalizedPayloadSha256 = digest(stableJson(normalizedFiles));
  const createdAt = isoDateSchema.safeParse(
    input.createdAt ?? new Date().toISOString(),
  );
  if (!createdAt.success)
    throw new P0ValidationError(
      "CANDIDATE_EQUIVALENCE_SCHEMA_INVALID",
      "Candidate-equivalence creation time must be an ISO-8601 timestamp.",
      "Supply a valid creation timestamp when recording the verifier-produced attestation.",
    );
  return {
    schemaVersion: 1,
    rcCandidate,
    stableCandidate,
    normalizedPayloadSha256,
    attestationSha256: attestationDigest({
      rcCandidate,
      stableCandidate,
      normalizedPayloadSha256,
    }),
    createdAt: createdAt.data,
  };
}
function requiredIds(prefix: string, count: number): readonly string[] {
  return Array.from(
    { length: count },
    (_, index) => `${prefix}${String(index + 1).padStart(2, "0")}`,
  );
}

function setDifference(
  left: readonly string[],
  right: readonly string[],
): readonly string[] {
  const rightSet = new Set(right);
  return left.filter((value) => !rightSet.has(value));
}

function assertSanitizedValue(value: unknown, location: string): void {
  if (typeof value === "string") {
    if (hasForbiddenLocalPath(value))
      throw new P0ValidationError(
        "REDACTION_REJECTED",
        `P0 evidence contains an absolute local path at ${location}`,
        "Remove local paths from the sanitized record and retain raw diagnostics only in .tmp/kpi-p0.",
      );
    if (hasSensitiveText(value))
      throw new P0ValidationError(
        "REDACTION_REJECTED",
        `P0 evidence contains a sensitive value at ${location}`,
        "Keep credentials, headers, cookies, and Provider data out of P0 evidence.",
      );
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      assertSanitizedValue(entry, `${location}[${index}]`);
    });
    return;
  }
  if (value === null || typeof value !== "object") return;
  for (const [key, nested] of Object.entries(
    value as Record<string, unknown>,
  )) {
    if (hasSensitiveFieldName(key))
      throw new P0ValidationError(
        "REDACTION_REJECTED",
        `P0 evidence contains a forbidden sensitive field at ${location}.${key}`,
        "Keep credentials, account data, provider responses, and transport headers in neither canonical evidence nor reports.",
      );
    assertSanitizedValue(nested, `${location}.${key}`);
  }
}

const evidenceLocatorSchema = z
  .object({
    kind: z.enum(["test", "feature", "file", "report"]),
    path: relativePathSchema,
    title: z.string().min(1).optional(),
    command: z.array(z.string().min(1)).min(1).optional(),
    mode: z.enum([
      "unit",
      "contract-backed",
      "smoke-only",
      "package-content",
      "manual",
      "blocked",
    ]),
  })
  .strict();
const catalogEntrySchema = z
  .object({
    id: z.string().regex(/^P0-(?:E11|EXIT)-\d{2}$/),
    source: z
      .object({
        path: relativePathSchema,
        locator: z.string().min(1),
      })
      .strict(),
    title: z.string().min(1),
    evidenceRequirement: z.enum([
      "automated",
      "manual",
      "blocked",
      "not-applicable",
    ]),
    evidence: z.array(evidenceLocatorSchema),
    blocker: blockerSchema.optional(),
    notApplicableRationale: z.string().min(1).optional(),
  })
  .strict();
export const conformanceCatalogSchema = z
  .object({
    schemaVersion: z.literal(1),
    entries: z.array(catalogEntrySchema),
  })
  .strict();
export type ConformanceCatalog = z.infer<typeof conformanceCatalogSchema>;
export type ConformanceCatalogEntry = z.infer<typeof catalogEntrySchema>;

async function assertLocatorExists(
  locator: z.infer<typeof evidenceLocatorSchema>,
  workspaceRoot: string,
  files: P0FileSystem,
): Promise<void> {
  const path = safeRelativePath(
    workspaceRoot,
    join(workspaceRoot, locator.path),
  );
  let kind: P0DirectoryEntry["kind"];
  try {
    kind = await files.inspect(path);
  } catch {
    throw new P0ValidationError(
      "CATALOG_EVIDENCE_INVALID",
      `Evidence locator does not exist: ${locator.path}`,
      "Point the matrix at a current test, feature, report, or declared blocker.",
      { path: locator.path },
    );
  }
  if (kind !== "file")
    throw new P0ValidationError(
      "CATALOG_EVIDENCE_INVALID",
      `Evidence locator must be a regular file: ${locator.path}`,
      "Replace the directory or link with a stable regular-file locator.",
      { path: locator.path, kind },
    );
  if (locator.title === undefined) return;
  const content = await files.readText(path);
  if (!content.includes(locator.title))
    throw new P0ValidationError(
      "CATALOG_EVIDENCE_INVALID",
      `Evidence title is not present in ${locator.path}`,
      "Use the exact scenario or test title from the evidence file.",
      { path: locator.path, title: locator.title },
    );
}

async function assertSourceExists(
  entry: ConformanceCatalogEntry,
  workspaceRoot: string,
  files: P0FileSystem,
): Promise<void> {
  const path = safeRelativePath(
    workspaceRoot,
    join(workspaceRoot, entry.source.path),
  );
  let content: string;
  try {
    content = await files.readText(path);
  } catch {
    throw new P0ValidationError(
      "CATALOG_SOURCE_INVALID",
      `Catalog source path does not exist: ${entry.source.path}`,
      "Restore the referenced product source or update the matrix with the current source locator.",
      { id: entry.id, path: entry.source.path },
    );
  }
  if (!content.includes(entry.source.locator))
    throw new P0ValidationError(
      "CATALOG_SOURCE_INVALID",
      `Catalog source locator is not present for ${entry.id}`,
      "Use the exact ROADMAP or PRD text that defines this requirement.",
      { id: entry.id, locator: entry.source.locator },
    );
}

export async function validateConformanceCatalog(
  input: unknown,
  workspaceRoot: string,
  files: P0FileSystem = createNodeFileSystem(),
): Promise<ConformanceCatalog> {
  const parsed = conformanceCatalogSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "CATALOG_SCHEMA_INVALID",
      "The P0 conformance catalog violates its strict schema",
      "Repair the versioned catalog; unknown fields and malformed entries are not accepted.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const entries = parsed.data.entries;
  const ids = entries.map((entry) => entry.id);
  const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
  const expectedMatrixIds = requiredIds("P0-E11-", 39);
  const expectedExitIds = requiredIds("P0-EXIT-", 14);
  const missing = [
    ...setDifference(expectedMatrixIds, ids),
    ...setDifference(expectedExitIds, ids),
  ];
  const extras = [
    ...setDifference(
      ids.filter((id) => id.startsWith("P0-E11-")),
      expectedMatrixIds,
    ),
    ...setDifference(
      ids.filter((id) => id.startsWith("P0-EXIT-")),
      expectedExitIds,
    ),
  ];
  if (duplicateIds.length > 0 || missing.length > 0 || extras.length > 0)
    throw new P0ValidationError(
      "CATALOG_MATRIX_INVALID",
      "The P0 catalog must contain every numbered matrix and exit criterion exactly once",
      "Restore the missing requirement entries and remove duplicate or unrecognized IDs.",
      { duplicateIds, missing, extras },
    );

  for (const entry of entries) {
    if (entry.evidence.length === 0)
      throw new P0ValidationError(
        "CATALOG_EVIDENCE_INVALID",
        `${entry.id} has no stable evidence locator`,
        "Attach named automated evidence, manual evidence, a blocker, or a not-applicable rationale.",
        { id: entry.id },
      );
    if (entry.evidenceRequirement === "blocked" && entry.blocker === undefined)
      throw new P0ValidationError(
        "CATALOG_EVIDENCE_INVALID",
        `${entry.id} is blocked without a recovery path`,
        "Record a safe blocker code and explicit recovery action.",
        { id: entry.id },
      );
    if (
      entry.evidenceRequirement === "not-applicable" &&
      entry.notApplicableRationale === undefined
    )
      throw new P0ValidationError(
        "CATALOG_EVIDENCE_INVALID",
        `${entry.id} is not applicable without a rationale`,
        "State why the requirement cannot apply; do not aggregate it away.",
        { id: entry.id },
      );
    if (
      entry.evidenceRequirement === "automated" &&
      !entry.evidence.some((evidence) => evidence.command !== undefined)
    )
      throw new P0ValidationError(
        "CATALOG_EVIDENCE_INVALID",
        `${entry.id} has automated evidence without an executable command`,
        "Attach the package-native command that produces the evidence.",
        { id: entry.id },
      );
    await assertSourceExists(entry, workspaceRoot, files);
    await Promise.all(
      entry.evidence.map((evidence) =>
        assertLocatorExists(evidence, workspaceRoot, files),
      ),
    );
  }
  return parsed.data;
}

export async function loadConformanceCatalog(
  catalogPath: string,
  workspaceRoot: string,
  files: P0FileSystem = createNodeFileSystem(),
): Promise<ConformanceCatalog> {
  const raw = await files.readText(catalogPath);
  return validateConformanceCatalog(
    parsedJson(conformanceCatalogSchema, raw, "P0 conformance catalog"),
    workspaceRoot,
    files,
  );
}

export const compatibilityCommandsSchema = z.tuple([
  z.literal("help"),
  z.literal("status"),
  z.literal("report"),
  z.literal("onboard plan"),
]);

export const compatibilityManifestSchema = z
  .object({
    schemaVersion: z.literal(1),
    currentRuntimeVersion: currentRuntimeVersionSchema,
    pluginPackage: z.literal("@kunolu/omp-sbtd"),
    commands: compatibilityCommandsSchema,
  })
  .strict();
export type CompatibilityManifest = z.infer<typeof compatibilityManifestSchema>;

export function resolveCurrentRuntimeVersionFromLockfile(
  lockfile: string,
): string {
  const importerMarker = "  packages/omp-sbtd:\n";
  const importerStart = lockfile.indexOf(importerMarker);
  if (importerStart === -1)
    throw new P0ValidationError(
      "CURRENT_RUNTIME_UNRESOLVED",
      "The workspace lockfile does not contain the Plugin importer.",
      "Regenerate the lockfile with the installed @oh-my-pi/pi-coding-agent dependency.",
    );
  const importerTail = lockfile.slice(importerStart + importerMarker.length);
  const nextImporter = importerTail.search(/\n {2}[^\s]/u);
  const importerSection =
    nextImporter === -1 ? importerTail : importerTail.slice(0, nextImporter);
  const dependency =
    /^ {6}'@oh-my-pi\/pi-coding-agent':\n {8}specifier: ([^\n]+)\n {8}version: ([^\n]+)$/mu.exec(
      importerSection,
    );
  if (dependency === null)
    throw new P0ValidationError(
      "CURRENT_RUNTIME_UNRESOLVED",
      "The Plugin importer does not pin one installed OMP Runtime version.",
      "Pin @oh-my-pi/pi-coding-agent to one exact version in the workspace lockfile.",
    );
  const specifier = dependency[1]?.trim();
  const version = dependency[2]?.trim();
  const parsed = currentRuntimeVersionSchema.safeParse(version);
  if (
    specifier === undefined ||
    version === undefined ||
    !parsed.success ||
    specifier !== parsed.data
  )
    throw new P0ValidationError(
      "CURRENT_RUNTIME_UNRESOLVED",
      "The lockfile OMP Runtime specifier and installed version are not one matching exact semantic version.",
      "Restore one exact @oh-my-pi/pi-coding-agent lockfile pin before compatibility validation.",
    );
  return parsed.data;
}

export function validateCompatibilityManifest(
  input: unknown,
  expectedCurrentRuntimeVersion?: string,
): CompatibilityManifest {
  const parsed = compatibilityManifestSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "CURRENT_RUNTIME_COMPATIBILITY_INVALID",
      "The OMP compatibility manifest must name one current Runtime version and the exact required read-only commands.",
      "Restore one exact currentRuntimeVersion and the exact required read-only commands.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  if (expectedCurrentRuntimeVersion !== undefined) {
    const expected = currentRuntimeVersionSchema.safeParse(
      expectedCurrentRuntimeVersion,
    );
    if (!expected.success)
      throw new P0ValidationError(
        "CURRENT_RUNTIME_UNRESOLVED",
        "The requested current Runtime identity is not a semantic version.",
        "Resolve the exact installed Runtime version from the lockfile or pass a checked semantic version.",
      );
    if (parsed.data.currentRuntimeVersion !== expected.data)
      throw new P0ValidationError(
        "CURRENT_RUNTIME_MISMATCH",
        "Compatibility manifest Runtime identity does not match the resolved current Runtime.",
        "Regenerate the manifest for the checked Runtime identity before running compatibility.",
        {
          manifestRuntimeVersion: parsed.data.currentRuntimeVersion,
          currentRuntimeVersion: expected.data,
        },
      );
  }
  return parsed.data;
}

export interface CurrentRuntimeCompatibilityResult {
  readonly currentRuntimeVersion: string;
  readonly status: "passed" | "failed" | "blocked";
  readonly agentInvoked: false;
  readonly acceptanceMode?: "profile-isolated";
  readonly supportDecision?: "requires-separate-support-review";
  readonly filesystemBeforeSha256?: string;
  readonly filesystemAfterSha256?: string;
  readonly packageSha256?: string;
  readonly blocker?: z.infer<typeof blockerSchema>;
  readonly commandResults: Readonly<
    Record<
      "help" | "status" | "report" | "onboard plan",
      "passed" | "failed" | "blocked"
    >
  >;
}

export interface CurrentRuntimeCompatibilityAdapter {
  readonly runCurrentRuntime: (
    input: Readonly<{
      currentRuntimeVersion: string;
      pluginPackagePath: string;
      pluginTarballPath: string;
      sandboxRoot: string;
      commands: CompatibilityManifest["commands"];
    }>,
  ) => Promise<CurrentRuntimeCompatibilityResult>;
}

export function createBlockedCompatibilityAdapter(
  recovery = "Provide an isolated OMP host harness for the resolved current Runtime and rerun compatibility.",
): CurrentRuntimeCompatibilityAdapter {
  return {
    runCurrentRuntime: async ({ currentRuntimeVersion }) => ({
      currentRuntimeVersion,
      status: "blocked",
      agentInvoked: false,
      blocker: {
        code: "OMP_HOST_UNAVAILABLE",
        reason: "No authorized isolated OMP public-host adapter was provided.",
        recovery,
      },
      commandResults: {
        help: "blocked",
        status: "blocked",
        report: "blocked",
        "onboard plan": "blocked",
      },
    }),
  };
}

export async function runCurrentRuntimeCompatibility(
  manifestInput: unknown,
  adapter: CurrentRuntimeCompatibilityAdapter,
  options: Readonly<{
    pluginPackagePath: string;
    pluginTarballPath: string;
    sandboxRoot: string;
    currentRuntimeVersion: string;
  }>,
): Promise<
  Readonly<{
    schemaVersion: 1;
    currentRuntimeVersion: string;
    result: CurrentRuntimeCompatibilityResult;
  }>
> {
  const manifest = validateCompatibilityManifest(
    manifestInput,
    options.currentRuntimeVersion,
  );
  const result = await adapter.runCurrentRuntime({
    currentRuntimeVersion: manifest.currentRuntimeVersion,
    pluginPackagePath: options.pluginPackagePath,
    pluginTarballPath: options.pluginTarballPath,
    sandboxRoot: join(options.sandboxRoot, manifest.currentRuntimeVersion),
    commands: manifest.commands,
  });
  if (result.currentRuntimeVersion !== manifest.currentRuntimeVersion)
    throw new P0ValidationError(
      "CURRENT_RUNTIME_MISMATCH",
      "Compatibility adapter returned evidence for a different Runtime identity.",
      "Rerun the isolated compatibility check against the resolved current Runtime.",
      {
        expectedRuntimeVersion: manifest.currentRuntimeVersion,
        actualRuntimeVersion: result.currentRuntimeVersion,
      },
    );
  return {
    schemaVersion: 1,
    currentRuntimeVersion: manifest.currentRuntimeVersion,
    result,
  };
}

const fixtureCategorySchema = z.enum(VALUE_STUDY_CATEGORIES);
const requiredGateSchema = z.enum(REQUIRED_GATE_IDS);
const rubricCriterionSchema = z
  .object({
    id: z.string().min(1),
    description: z.string().min(1),
    weight: z.number().int().positive(),
    severe: z.boolean(),
  })
  .strict();
export const valueStudyFixtureSchema = z
  .object({
    schemaVersion: z.literal(1),
    id: z.string().regex(/^P0-VS-[A-Z0-9-]+$/),
    category: fixtureCategorySchema,
    prompt: z.string().min(1),
    startingFiles: z.record(relativePathSchema, z.string()),
    startingSnapshotSha256: hashSchema,
    expected: z
      .object({
        route: z.enum(ROUTE_IDS),
        routeCost: routeCostSchema,
        requiredGates: z.array(requiredGateSchema),
        obligations: z.array(z.string().min(1)).min(1),
      })
      .strict(),
    rubric: z.array(rubricCriterionSchema).min(1),
    cleanupBoundary: z.string().min(1),
    permittedNetwork: z.enum(["none", "contract-only", "omp-owned-model-only"]),
  })
  .strict();
export type ValueStudyFixture = z.infer<typeof valueStudyFixtureSchema>;
const corpusFixtureReferenceSchema = z
  .object({
    id: z.string().regex(/^P0-VS-[A-Z0-9-]+$/),
    category: fixtureCategorySchema,
    path: relativePathSchema,
  })
  .strict();
export const valueStudyCorpusSchema = z
  .object({
    schemaVersion: z.literal(1),
    randomSeed: z.string().min(1),
    fixtures: z.array(corpusFixtureReferenceSchema).length(20),
  })
  .strict();
export type ValueStudyCorpus = z.infer<typeof valueStudyCorpusSchema>;

export function startingFilesSha256(
  files: Readonly<Record<string, string>>,
): string {
  return digest(
    Object.entries(files)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([path, content]) => `${path}\0${digest(content)}`)
      .join("\n"),
  );
}

function validateValueStudyFixture(input: unknown): ValueStudyFixture {
  assertSanitizedValue(input, "fixture");
  const parsed = valueStudyFixtureSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "CORPUS_FIXTURE_INVALID",
      "A P0 value-study fixture violates its strict schema",
      "Repair the frozen fixture or introduce a new corpus version.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const duplicateCriteria = parsed.data.rubric
    .map((criterion) => criterion.id)
    .filter((id, index, values) => values.indexOf(id) !== index);
  const totalWeight = parsed.data.rubric.reduce(
    (sum, criterion) => sum + criterion.weight,
    0,
  );
  if (duplicateCriteria.length > 0 || totalWeight !== 100)
    throw new P0ValidationError(
      "CORPUS_RUBRIC_INVALID",
      "A P0 value-study rubric must have unique criteria totaling exactly 100",
      "Fix the frozen rubric weights before any paired run begins.",
      { id: parsed.data.id, duplicateCriteria, totalWeight },
    );
  if (
    startingFilesSha256(parsed.data.startingFiles) !==
    parsed.data.startingSnapshotSha256
  )
    throw new P0ValidationError(
      "CORPUS_SNAPSHOT_INVALID",
      "Fixture starting files do not match the recorded source checksum",
      "Regenerate the fixture checksum after intentionally changing its self-contained project input.",
      { id: parsed.data.id },
    );
  return parsed.data;
}

export function valueStudyFixtureSha256(fixture: ValueStudyFixture): string {
  return digest(stableJson(validateValueStudyFixture(fixture)));
}

export function valueStudyRubricSha256(
  fixtures: readonly ValueStudyFixture[],
): string {
  return digest(
    stableJson(
      fixtures
        .map((fixture) => ({ fixtureId: fixture.id, rubric: fixture.rubric }))
        .sort((left, right) => left.fixtureId.localeCompare(right.fixtureId)),
    ),
  );
}

export async function loadValueStudyCorpus(
  corpusPath: string,
  validationRoot: string,
  files: P0FileSystem = createNodeFileSystem(),
): Promise<ValueStudyCorpus> {
  const corpus = parsedJson(
    valueStudyCorpusSchema,
    await files.readText(corpusPath),
    "P0 value-study corpus",
  );
  const ids = corpus.fixtures.map((fixture) => fixture.id);
  const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
  const categoryCounts = new Map<string, number>();
  if (duplicateIds.length > 0)
    throw new P0ValidationError(
      "CORPUS_INVALID",
      "The P0 value-study corpus contains duplicate fixture IDs",
      "Assign every frozen task a unique stable ID.",
      { duplicateIds },
    );
  for (const reference of corpus.fixtures) {
    const fixturePath = safeRelativePath(
      validationRoot,
      join(validationRoot, reference.path),
    );
    const fixture = validateValueStudyFixture(
      parsedJson(
        valueStudyFixtureSchema,
        await files.readText(fixturePath),
        `P0 value-study fixture ${reference.id}`,
      ),
    );
    if (fixture.id !== reference.id || fixture.category !== reference.category)
      throw new P0ValidationError(
        "CORPUS_INVALID",
        "Corpus fixture metadata does not match its frozen manifest",
        "Align the corpus reference with the immutable fixture manifest.",
        { reference, fixture: { id: fixture.id, category: fixture.category } },
      );
    categoryCounts.set(
      reference.category,
      (categoryCounts.get(reference.category) ?? 0) + 1,
    );
  }
  const invalidCategories = VALUE_STUDY_CATEGORIES.filter(
    (category) => categoryCounts.get(category) !== 2,
  );
  if (invalidCategories.length > 0)
    throw new P0ValidationError(
      "CORPUS_INVALID",
      "The P0 value-study corpus requires exactly two fixtures in every approved category",
      "Restore the missing or extra frozen fixtures before running the study.",
      { invalidCategories },
    );
  return corpus;
}

export interface LoadedValueStudyCorpus {
  readonly corpus: ValueStudyCorpus;
  readonly fixtures: readonly ValueStudyFixture[];
}

export async function loadValueStudyCorpusBundle(
  corpusPath: string,
  validationRoot: string,
  files: P0FileSystem = createNodeFileSystem(),
): Promise<LoadedValueStudyCorpus> {
  const corpus = await loadValueStudyCorpus(corpusPath, validationRoot, files);
  const fixtures: ValueStudyFixture[] = [];
  for (const reference of corpus.fixtures) {
    const fixturePath = safeRelativePath(
      validationRoot,
      join(validationRoot, reference.path),
    );
    fixtures.push(
      validateValueStudyFixture(
        parsedJson(
          valueStudyFixtureSchema,
          await files.readText(fixturePath),
          `P0 value-study fixture ${reference.id}`,
        ),
      ),
    );
  }
  return { corpus, fixtures };
}

const attemptOutcomeSchema = z.enum([
  "completed",
  "host-start",
  "transport-interruption",
  "runtime-crash",
  "model-quality",
  "task-test-failure",
  "workflow-blocked",
  "timeout",
  "turn-limit",
  "token-limit",
]);
const valueStudyArmSchema = z.enum(["control", "treatment"]);
const armAttemptSchema = z
  .object({
    attempt: z.number().int().positive(),
    outcome: attemptOutcomeSchema,
  })
  .strict();
const scoredArmSchema = z
  .object({
    status: z.enum(["completed", "failed", "blocked"]),
    observedRequiredGates: z.array(requiredGateSchema),
    // Optional so an explicitly unclassified advisory control is preserved
    // without a synthetic cost; the scorer still requires a treatment cost.
    actualRouteCost: routeCostSchema.optional(),
    severeWorkflowOmissions: z.array(z.string().min(1)),
    attempts: z.array(armAttemptSchema).min(1).max(2),
  })
  .strict();
const judgeCriterionScoreSchema = z
  .object({
    id: z.string().min(1),
    score: z.number().min(0).max(100),
    reason: z.string().min(1).max(4_096),
  })
  .strict();
const judgeArmScoreSchema = z
  .object({
    total: z.number().min(0).max(100),
    severeAcceptanceFailure: z.boolean(),
    criteria: z.array(judgeCriterionScoreSchema).min(1),
  })
  .strict();
const scoredPairSchema = z
  .object({
    fixtureId: z.string().min(1),
    expectedRequiredGates: z.array(requiredGateSchema),
    expectedRouteCost: routeCostSchema,
    control: scoredArmSchema,
    treatment: scoredArmSchema,
    judge: z
      .object({
        control: judgeArmScoreSchema,
        treatment: judgeArmScoreSchema,
      })
      .strict(),
  })
  .strict();
export const valueStudyScoringInputSchema = z
  .object({
    schemaVersion: z.literal(1),
    sourceTreeSha256: hashSchema,
    execution: z
      .object({
        runtimeVersion: z.string().min(1),
        modelId: z.string().min(1),
        processId: z.string().min(1),
      })
      .strict(),
    judge: z
      .object({
        modelId: z.string().min(1),
        processId: z.string().min(1),
      })
      .strict(),
    pairs: z.array(scoredPairSchema).max(20),
  })
  .strict();

export interface ValueStudyScoreReport {
  readonly schemaVersion: 1;
  readonly status: "passed" | "failed" | "blocked";
  readonly metrics: Readonly<{
    pairCount: number;
    gateRecall: number;
    controlSevereOmissions: number;
    treatmentSevereOmissions: number;
    unnecessaryHeavyRouteActivations: number;
    unnecessaryHeavyRouteRate: number;
    treatmentMeanCorrectness: number;
    controlMeanCorrectness: number;
    treatmentOnlySevereAcceptanceFailures: number;
  }>;
  readonly blockers: readonly z.infer<typeof blockerSchema>[];
}

function hasValidRetryLineage(
  attempts: readonly z.infer<typeof armAttemptSchema>[],
): boolean {
  if (attempts.some((attempt, index) => attempt.attempt !== index + 1))
    return false;
  if (attempts.length === 1) return true;
  const initialAttempt = attempts[0];
  return (
    initialAttempt !== undefined &&
    RETRYABLE_FAILURES.has(initialAttempt.outcome)
  );
}

function statusForAttemptOutcome(
  outcome: z.infer<typeof attemptOutcomeSchema>,
): z.infer<typeof scoredArmSchema>["status"] {
  if (outcome === "completed") return "completed";
  if (outcome === "model-quality" || outcome === "task-test-failure")
    return "failed";
  return "blocked";
}

function hasAcceptedOutcomeMatchingStatus(
  arm: Readonly<{
    status: z.infer<typeof scoredArmSchema>["status"];
    attempts: readonly z.infer<typeof armAttemptSchema>[];
  }>,
): boolean {
  const acceptedAttempt = arm.attempts[arm.attempts.length - 1];
  return (
    acceptedAttempt !== undefined &&
    arm.status === statusForAttemptOutcome(acceptedAttempt.outcome)
  );
}

function routeCostRank(cost: z.infer<typeof routeCostSchema>): number {
  if (cost === "light") return 1;
  if (cost === "standard") return 2;
  return 3;
}

function blockedScoreReport(
  pairCount: number,
  code: string,
  reason: string,
  recovery: string,
): ValueStudyScoreReport {
  return {
    schemaVersion: 1,
    status: "blocked",
    metrics: {
      pairCount,
      gateRecall: 0,
      controlSevereOmissions: 0,
      treatmentSevereOmissions: 0,
      unnecessaryHeavyRouteActivations: 0,
      unnecessaryHeavyRouteRate: 0,
      treatmentMeanCorrectness: 0,
      controlMeanCorrectness: 0,
      treatmentOnlySevereAcceptanceFailures: 0,
    },
    blockers: [{ code, reason, recovery }],
  };
}

export function scoreValueStudy(input: unknown): ValueStudyScoreReport {
  const parsed = valueStudyScoringInputSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "VALUE_SCORE_SCHEMA_INVALID",
      "The value-study score input violates its strict schema",
      "Rebuild the score input from a complete sanitized immutable run.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const { pairs } = parsed.data;
  if (parsed.data.execution.modelId === parsed.data.judge.modelId)
    return blockedScoreReport(
      pairs.length,
      "JUDGE_NOT_INDEPENDENT",
      "The judge model ID must differ from the task-execution model ID.",
      "Select a distinct fixed judge model and start it in a separate process.",
    );
  if (parsed.data.execution.processId === parsed.data.judge.processId)
    return blockedScoreReport(
      pairs.length,
      "JUDGE_PROCESS_NOT_INDEPENDENT",
      "The judge process must be distinct from the task-execution process.",
      "Start the fixed judge in a separate process before evaluating masked artifacts.",
    );
  if (pairs.length !== 20)
    return blockedScoreReport(
      pairs.length,
      "VALUE_PAIR_INCOMPLETE",
      "P0 requires exactly 20 complete paired fixtures.",
      "Complete every fixed corpus pair without selecting retries for quality outcomes.",
    );
  const duplicateFixtures = pairs
    .map((pair) => pair.fixtureId)
    .filter((id, index, ids) => ids.indexOf(id) !== index);
  if (duplicateFixtures.length > 0)
    return blockedScoreReport(
      pairs.length,
      "VALUE_PAIR_DUPLICATE",
      "A value-study fixture appears more than once.",
      "Run each frozen fixture exactly once per arm and rebuild the score input.",
    );
  for (const pair of pairs) {
    if (
      !hasAcceptedOutcomeMatchingStatus(pair.control) ||
      !hasAcceptedOutcomeMatchingStatus(pair.treatment)
    )
      return blockedScoreReport(
        pairs.length,
        "VALUE_ARM_OUTCOME_INVALID",
        "A scored arm status does not match its final accepted attempt outcome.",
        "Use only the final accepted completed outcome for a passing paired arm.",
      );
    if (
      pair.control.status !== "completed" ||
      pair.treatment.status !== "completed"
    )
      return blockedScoreReport(
        pairs.length,
        "VALUE_PAIR_INCOMPLETE",
        "A paired arm did not reach a complete outcome.",
        "Resolve the recorded blocker or failure in a new run; do not select a rerun for quality.",
      );
    if (
      !hasValidRetryLineage(pair.control.attempts) ||
      !hasValidRetryLineage(pair.treatment.attempts)
    )
      return blockedScoreReport(
        pairs.length,
        "RETRY_LINEAGE_INVALID",
        "A paired arm used an ineligible or out-of-order retry.",
        "Restart the affected fixture in a new run and retain only eligible infrastructure retries.",
      );
  }

  let expectedGateCount = 0;
  let observedGateCount = 0;
  let controlSevereOmissions = 0;
  let treatmentSevereOmissions = 0;
  let unnecessaryHeavyRouteActivations = 0;
  let treatmentCorrectness = 0;
  let controlCorrectness = 0;
  let treatmentOnlySevereAcceptanceFailures = 0;
  for (const pair of pairs) {
    const expected = new Set(pair.expectedRequiredGates);
    const observed = new Set(pair.treatment.observedRequiredGates);
    expectedGateCount += expected.size;
    observedGateCount += [...expected].filter((gate) =>
      observed.has(gate),
    ).length;
    controlSevereOmissions += pair.control.severeWorkflowOmissions.length;
    treatmentSevereOmissions += pair.treatment.severeWorkflowOmissions.length;
    const treatmentRouteCost = pair.treatment.actualRouteCost;
    if (treatmentRouteCost === undefined)
      return blockedScoreReport(
        pairs.length,
        "VALUE_ROUTE_UNCLASSIFIED",
        "A treatment arm has no classified route cost measurement.",
        "Record a named effective route and concrete cost for every treatment arm in a new complete run.",
      );
    if (
      routeCostRank(treatmentRouteCost) > routeCostRank(pair.expectedRouteCost)
    )
      unnecessaryHeavyRouteActivations += 1;
    controlCorrectness += pair.judge.control.total;
    treatmentCorrectness += pair.judge.treatment.total;
    if (
      pair.judge.treatment.severeAcceptanceFailure &&
      !pair.judge.control.severeAcceptanceFailure
    )
      treatmentOnlySevereAcceptanceFailures += 1;
  }
  const gateRecall =
    expectedGateCount === 0 ? 1 : observedGateCount / expectedGateCount;
  const controlMeanCorrectness = controlCorrectness / pairs.length;
  const treatmentMeanCorrectness = treatmentCorrectness / pairs.length;
  const unnecessaryHeavyRouteRate =
    unnecessaryHeavyRouteActivations / pairs.length;
  const severeOmissionPass =
    controlSevereOmissions === 0
      ? treatmentSevereOmissions === 0
      : treatmentSevereOmissions <= controlSevereOmissions * 0.7;
  const passed =
    gateRecall === 1 &&
    severeOmissionPass &&
    unnecessaryHeavyRouteRate <= 0.05 &&
    treatmentMeanCorrectness >= controlMeanCorrectness &&
    treatmentOnlySevereAcceptanceFailures === 0;
  return {
    schemaVersion: 1,
    status: passed ? "passed" : "failed",
    metrics: {
      pairCount: pairs.length,
      gateRecall,
      controlSevereOmissions,
      treatmentSevereOmissions,
      unnecessaryHeavyRouteActivations,
      unnecessaryHeavyRouteRate,
      treatmentMeanCorrectness,
      controlMeanCorrectness,
      treatmentOnlySevereAcceptanceFailures,
    },
    blockers: passed
      ? []
      : [
          {
            code: "VALUE_THRESHOLD_FAILED",
            reason: "One or more immutable P0 value thresholds were not met.",
            recovery:
              "Record the actual metrics, correct the product cause, then start a new complete paired run.",
          },
        ],
  };
}

export const VALUE_STUDY_LIMITS = {
  wallClockMs: 600_000,
  maxTurns: 24,
  maxTokens: 80_000,
} as const;

const acceptanceArtifactSchema = z
  .object({
    finalResponse: z
      .string()
      .min(1)
      .max(32 * 1024)
      .optional(),
    patch: z
      .string()
      .max(64 * 1024)
      .optional(),
    commandOutcomes: z
      .array(
        z
          .object({
            command: z.string().min(1).max(512),
            status: z.enum(["passed", "failed", "blocked"]),
          })
          .strict(),
      )
      .max(24),
  })
  .strict()
  .refine(
    (artifact) =>
      artifact.finalResponse !== undefined ||
      artifact.patch !== undefined ||
      artifact.commandOutcomes.length > 0,
    "expected a bounded acceptance artifact",
  );
export type AcceptanceArtifact = z.infer<typeof acceptanceArtifactSchema>;

export function acceptanceArtifactSha256(input: unknown): string {
  assertSanitizedValue(input, "acceptance-artifact");
  const parsed = acceptanceArtifactSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "ACCEPTANCE_ARTIFACT_INVALID",
      "The bounded acceptance artifact violates the strict value-study schema.",
      "Return only the documented sanitized final response, patch, and command outcomes.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  return digest(stableJson(parsed.data));
}

const blindJudgeResultBindingSchema = z
  .object({
    fixtureId: z.string().min(1),
    firstArtifactSha256: hashSchema,
    secondArtifactSha256: hashSchema,
    first: judgeArmScoreSchema,
    second: judgeArmScoreSchema,
  })
  .strict();

export function blindJudgeResultSha256(input: unknown): string {
  assertSanitizedValue(input, "blind-judge-result");
  const parsed = blindJudgeResultBindingSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "JUDGE_RESULT_INVALID",
      "The blind judge result violates its strict bounded schema.",
      "Return exactly the masked pair scores, reasons, and artifact bindings.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  return digest(stableJson(parsed.data));
}

const executionLimitSchema = z
  .object({
    wallClockMs: z
      .number()
      .int()
      .positive()
      .max(VALUE_STUDY_LIMITS.wallClockMs),
    maxTurns: z.number().int().positive().max(VALUE_STUDY_LIMITS.maxTurns),
    maxTokens: z.number().int().positive().max(VALUE_STUDY_LIMITS.maxTokens),
  })
  .strict();
const fixtureBindingSchema = z
  .object({
    fixtureId: z.string().min(1),
    fixtureSha256: hashSchema,
    expectedRequiredGates: z.array(requiredGateSchema),
    expectedRouteCost: routeCostSchema,
    rubric: z.array(rubricCriterionSchema).min(1),
  })
  .strict();
const randomizedArmSchema = z
  .object({
    position: z.number().int().min(0).max(39),
    fixtureId: z.string().min(1),
    arm: valueStudyArmSchema,
  })
  .strict();
const randomizedJudgeSchema = z
  .object({
    position: z.number().int().min(0).max(19),
    fixtureId: z.string().min(1),
    firstArm: valueStudyArmSchema,
    secondArm: valueStudyArmSchema,
  })
  .strict();
const randomizedOrderSchema = z
  .object({
    seed: z.string().min(1),
    arms: z.array(randomizedArmSchema).max(40),
    judgments: z.array(randomizedJudgeSchema).max(20),
  })
  .strict();
const canonicalArmSchema = z
  .object({
    fixtureId: z.string().min(1),
    arm: valueStudyArmSchema,
    position: z.number().int().min(0).max(39),
    fixtureSha256: hashSchema,
    attempts: z.array(armAttemptSchema).min(1).max(2),
    acceptedAttempt: z.number().int().positive(),
    status: z.enum(["completed", "failed", "blocked"]),
    observedRequiredGates: z.array(requiredGateSchema),
    actualRouteCost: routeCostSchema.optional(),
    severeWorkflowOmissions: z.array(z.string().min(1)),
    limits: executionLimitSchema,
    usage: z
      .object({
        turns: z.number().int().min(0),
        tokenCount: z.number().int().min(0),
      })
      .strict(),
    acceptanceArtifactSha256: hashSchema,
  })
  .strict();
const canonicalJudgmentSchema = z
  .object({
    fixtureId: z.string().min(1),
    position: z.number().int().min(0).max(19),
    firstArtifactSha256: hashSchema,
    secondArtifactSha256: hashSchema,
    first: judgeArmScoreSchema,
    second: judgeArmScoreSchema,
    judgeResultSha256: hashSchema,
  })
  .strict();
const completionProvenanceSchema = z
  .object({
    controllerProvenanceSha256: hashSchema,
    fixtures: z.array(fixtureBindingSchema).max(20),
    arms: z.array(canonicalArmSchema).max(40),
    judgments: z.array(canonicalJudgmentSchema).max(20),
  })
  .strict();
const valueStudyMetricsSchema = z
  .object({
    pairCount: z.number().int().min(0).max(20),
    gateRecall: z.number().min(0).max(1),
    controlSevereOmissions: z.number().int().min(0),
    treatmentSevereOmissions: z.number().int().min(0),
    unnecessaryHeavyRouteActivations: z.number().int().min(0).max(20),
    unnecessaryHeavyRouteRate: z.number().min(0).max(1),
    treatmentMeanCorrectness: z.number().min(0).max(100),
    controlMeanCorrectness: z.number().min(0).max(100),
    treatmentOnlySevereAcceptanceFailures: z.number().int().min(0).max(20),
  })
  .strict();
export const canonicalEvidenceRunSchema = z
  .object({
    schemaVersion: z.literal(1),
    runId: runIdSchema,
    createdAt: isoDateSchema,
    sourceTreeSha256: hashSchema,
    catalogSha256: hashSchema,
    corpusSha256: hashSchema,
    rubricSha256: hashSchema,
    environment: z
      .object({
        runtimeVersion: z.string().min(1),
        executionModelId: z.string().min(1),
        judgeModelId: z.string().min(1),
        executionProcessId: z.string().min(1),
        judgeProcessId: z.string().min(1),
      })
      .strict(),
    randomizedOrder: randomizedOrderSchema,
    technicalStatus: statusSchema,
    valueGateStatus: z.enum(["passed", "failed", "blocked"]),
    releaseDecision: z.enum(["ready", "blocked"]),
    metrics: valueStudyMetricsSchema,
    completionProvenance: completionProvenanceSchema,
    blockers: z.array(blockerSchema),
  })
  .strict();
export type CanonicalEvidenceRun = z.infer<typeof canonicalEvidenceRunSchema>;

function scoringArm(
  arm: z.infer<typeof canonicalArmSchema>,
): z.infer<typeof scoredArmSchema> {
  return {
    status: arm.status,
    observedRequiredGates: arm.observedRequiredGates,
    actualRouteCost: arm.actualRouteCost,
    severeWorkflowOmissions: arm.severeWorkflowOmissions,
    attempts: arm.attempts,
  };
}

const controllerArmLedgerSchema = canonicalArmSchema
  .extend({ acceptanceArtifact: acceptanceArtifactSchema })
  .strict();
const controllerProvenanceLedgerSchema = z
  .object({
    schemaVersion: z.literal(1),
    runId: runIdSchema,
    sourceTreeSha256: hashSchema,
    catalogSha256: hashSchema,
    corpusSha256: hashSchema,
    rubricSha256: hashSchema,
    environment: canonicalEvidenceRunSchema.shape.environment,
    randomizedOrder: randomizedOrderSchema,
    fixtures: z.array(fixtureBindingSchema).max(20),
    arms: z.array(controllerArmLedgerSchema).max(40),
    judgments: z.array(canonicalJudgmentSchema).max(20),
  })
  .strict();

function validateRubric(
  rubric: readonly z.infer<typeof rubricCriterionSchema>[],
  location: string,
): void {
  const ids = rubric.map((criterion) => criterion.id);
  const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
  const totalWeight = rubric.reduce(
    (total, criterion) => total + criterion.weight,
    0,
  );
  if (duplicateIds.length > 0 || totalWeight !== 100)
    throw new P0ValidationError(
      "CORPUS_RUBRIC_INVALID",
      `The frozen rubric at ${location} has duplicate criteria or an invalid weight total.`,
      "Use unique criterion IDs whose integer weights total exactly 100.",
      { duplicateIds, totalWeight },
    );
}

export function assertJudgeScoreMatchesRubric(
  score: z.infer<typeof judgeArmScoreSchema>,
  rubric: readonly z.infer<typeof rubricCriterionSchema>[],
  location: string,
): void {
  const criteriaById = new Map(
    score.criteria.map((criterion) => [criterion.id, criterion]),
  );
  const rubricIds = rubric.map((criterion) => criterion.id);
  const missing = rubricIds.filter((id) => !criteriaById.has(id));
  const extra = score.criteria
    .map((criterion) => criterion.id)
    .filter((id) => !rubricIds.includes(id));
  const duplicate = score.criteria
    .map((criterion) => criterion.id)
    .filter((id, index, ids) => ids.indexOf(id) !== index);
  const total = rubric.reduce((sum, criterion) => {
    const result = criteriaById.get(criterion.id);
    return (
      sum + (result === undefined ? 0 : (result.score * criterion.weight) / 100)
    );
  }, 0);
  if (
    missing.length > 0 ||
    extra.length > 0 ||
    duplicate.length > 0 ||
    Math.abs(total - score.total) > Number.EPSILON
  )
    throw new P0ValidationError(
      "JUDGE_RESULT_INVALID",
      `The blind judge score at ${location} does not bind every frozen rubric criterion exactly once.`,
      "Return one score and bounded reason for each rubric criterion with the correctly weighted total.",
      {
        missing,
        extra,
        duplicate,
        expectedTotal: total,
        actualTotal: score.total,
      },
    );
}

function deterministicShuffle<T>(seed: string, values: readonly T[]): T[] {
  const shuffled = [...values];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const value = Number.parseInt(
      digest(`${seed}\0${index}\0${JSON.stringify(shuffled)}`).slice(0, 12),
      16,
    );
    const selected = value % (index + 1);
    const current = shuffled[index];
    shuffled[index] = shuffled[selected] as T;
    shuffled[selected] = current as T;
  }
  return shuffled;
}

export interface DeterministicValueStudySchedule {
  readonly seed: string;
  readonly arms: readonly z.infer<typeof randomizedArmSchema>[];
  readonly judgments: readonly z.infer<typeof randomizedJudgeSchema>[];
}

export function deterministicValueStudySchedule(
  seed: string,
  fixtureIds: readonly string[],
): DeterministicValueStudySchedule {
  const duplicateFixtureIds = fixtureIds.filter(
    (id, index) => fixtureIds.indexOf(id) !== index,
  );
  if (fixtureIds.length !== 20 || duplicateFixtureIds.length > 0)
    throw new P0ValidationError(
      "VALUE_FIXTURE_COMPLETENESS_INVALID",
      "A deterministic P0 value-study schedule requires exactly 20 unique frozen fixture IDs.",
      "Restore the complete frozen corpus before scheduling any arms.",
      { fixtureCount: fixtureIds.length, duplicateFixtureIds },
    );
  const armKeys = fixtureIds.flatMap((fixtureId) => [
    { fixtureId, arm: "control" as const },
    { fixtureId, arm: "treatment" as const },
  ]);
  const arms = deterministicShuffle(`${seed}\0arms`, armKeys).map(
    (entry, position) => ({ ...entry, position }),
  );
  const judgments = deterministicShuffle(`${seed}\0judgments`, fixtureIds).map(
    (fixtureId, position) => {
      const controlFirst =
        Number.parseInt(
          digest(`${seed}\0judge-order\0${fixtureId}`).slice(0, 2),
          16,
        ) %
          2 ===
        0;
      return {
        position,
        fixtureId,
        firstArm: controlFirst ? ("control" as const) : ("treatment" as const),
        secondArm: controlFirst ? ("treatment" as const) : ("control" as const),
      };
    },
  );
  return { seed, arms, judgments };
}

function assertCanonicalEvidenceRun(input: unknown): CanonicalEvidenceRun {
  assertSanitizedValue(input, "canonical-run");
  const parsed = canonicalEvidenceRunSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "EVIDENCE_SCHEMA_INVALID",
      "The canonical P0 evidence record violates its strict allowlist schema.",
      "Create a new sanitized record with only documented public fields.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const run = parsed.data;
  if (run.environment.executionModelId === run.environment.judgeModelId)
    throw new P0ValidationError(
      "JUDGE_NOT_INDEPENDENT",
      "Canonical value evidence uses the same model identity for execution and judging.",
      "Use a different fixed judge model before running the paired study.",
    );
  if (run.environment.executionProcessId === run.environment.judgeProcessId)
    throw new P0ValidationError(
      "JUDGE_PROCESS_NOT_INDEPENDENT",
      "Canonical value evidence uses the same process identity for execution and judging.",
      "Start the independent judge in a distinct process before running the paired study.",
    );
  const provenance = run.completionProvenance;
  const fixtureIds = provenance.fixtures.map((fixture) => fixture.fixtureId);
  const duplicateFixtureIds = fixtureIds.filter(
    (id, index) => fixtureIds.indexOf(id) !== index,
  );
  if (fixtureIds.length !== 20 || duplicateFixtureIds.length > 0)
    throw new P0ValidationError(
      "VALUE_FIXTURE_COMPLETENESS_INVALID",
      "Canonical evidence must bind exactly 20 unique frozen fixtures.",
      "Restore every frozen fixture binding before promotion.",
      { fixtureCount: fixtureIds.length, duplicateFixtureIds },
    );
  for (const fixture of provenance.fixtures)
    validateRubric(fixture.rubric, `fixture ${fixture.fixtureId}`);
  const expectedSchedule = deterministicValueStudySchedule(
    run.randomizedOrder.seed,
    fixtureIds,
  );
  if (
    stableJson(expectedSchedule.arms) !==
      stableJson(run.randomizedOrder.arms) ||
    stableJson(expectedSchedule.judgments) !==
      stableJson(run.randomizedOrder.judgments)
  )
    throw new P0ValidationError(
      "VALUE_ORDER_INVALID",
      "Canonical arm or blind-judge order does not match the frozen deterministic seed.",
      "Rebuild the complete run with the controller's seeded schedule.",
    );
  if (provenance.arms.length !== 40)
    throw new P0ValidationError(
      "VALUE_ARM_COMPLETENESS_INVALID",
      "Canonical evidence requires exactly 40 accepted arm outcomes.",
      "Record one control and one treatment outcome for every frozen fixture.",
      { armCount: provenance.arms.length },
    );
  const fixtureById = new Map(
    provenance.fixtures.map((fixture) => [fixture.fixtureId, fixture]),
  );
  const armByKey = new Map<string, z.infer<typeof canonicalArmSchema>>();
  for (const arm of provenance.arms) {
    const key = `${arm.fixtureId}\0${arm.arm}`;
    if (armByKey.has(key))
      throw new P0ValidationError(
        "VALUE_ARM_COMPLETENESS_INVALID",
        "Canonical evidence contains a duplicate fixture-arm outcome.",
        "Record each fixture control/treatment arm exactly once.",
        { fixtureId: arm.fixtureId, arm: arm.arm },
      );
    const fixture = fixtureById.get(arm.fixtureId);
    const schedule = run.randomizedOrder.arms[arm.position];
    if (
      fixture === undefined ||
      arm.fixtureSha256 !== fixture.fixtureSha256 ||
      schedule === undefined ||
      schedule.fixtureId !== arm.fixtureId ||
      schedule.arm !== arm.arm
    )
      throw new P0ValidationError(
        "EVIDENCE_LINEAGE_INVALID",
        "An accepted arm is not bound to its frozen fixture and seeded position.",
        "Rebuild the arm outcome from the controller's immutable fixture binding.",
        { fixtureId: arm.fixtureId, arm: arm.arm, position: arm.position },
      );
    if (
      !hasValidRetryLineage(arm.attempts) ||
      arm.acceptedAttempt !== arm.attempts.length
    )
      throw new P0ValidationError(
        "RETRY_LINEAGE_INVALID",
        "An accepted arm has an ineligible retry lineage.",
        "Retain only one retry after host-start, transport-interruption, or runtime-crash.",
        { fixtureId: arm.fixtureId, arm: arm.arm },
      );
    const acceptedOutcome = arm.attempts[arm.attempts.length - 1]?.outcome;
    if (!hasAcceptedOutcomeMatchingStatus(arm))
      throw new P0ValidationError(
        "ATTEMPT_STATUS_INVALID",
        "An accepted arm status contradicts its final attempt outcome.",
        "Derive the canonical arm status from the controller-recorded final attempt outcome.",
        {
          fixtureId: arm.fixtureId,
          arm: arm.arm,
          status: arm.status,
          acceptedOutcome,
        },
      );
    const limitExceeded =
      arm.usage.turns > arm.limits.maxTurns ||
      arm.usage.tokenCount > arm.limits.maxTokens;
    if (
      arm.limits.wallClockMs !== VALUE_STUDY_LIMITS.wallClockMs ||
      arm.limits.maxTurns !== VALUE_STUDY_LIMITS.maxTurns ||
      arm.limits.maxTokens !== VALUE_STUDY_LIMITS.maxTokens ||
      (limitExceeded &&
        acceptedOutcome !== "turn-limit" &&
        acceptedOutcome !== "token-limit")
    )
      throw new P0ValidationError(
        "VALUE_LIMITS_UNEQUAL",
        "An accepted arm does not prove the identical fixed P0 resource limits.",
        "Use the fixed 600-second, 24-turn, and 80,000-token limits for every arm.",
        { fixtureId: arm.fixtureId, arm: arm.arm },
      );
    armByKey.set(key, arm);
  }
  for (const schedule of run.randomizedOrder.arms) {
    if (!armByKey.has(`${schedule.fixtureId}\0${schedule.arm}`))
      throw new P0ValidationError(
        "VALUE_ARM_COMPLETENESS_INVALID",
        "Canonical evidence is missing a scheduled fixture-arm outcome.",
        "Complete every deterministic control/treatment schedule position.",
        schedule,
      );
  }
  if (provenance.judgments.length !== 20)
    throw new P0ValidationError(
      "VALUE_JUDGMENT_COMPLETENESS_INVALID",
      "Canonical evidence requires exactly 20 blind pair judgments.",
      "Return one independent judgment for every frozen pair.",
      { judgmentCount: provenance.judgments.length },
    );
  const judgmentByFixture = new Map<
    string,
    z.infer<typeof canonicalJudgmentSchema>
  >();
  for (const judgment of provenance.judgments) {
    if (judgmentByFixture.has(judgment.fixtureId))
      throw new P0ValidationError(
        "VALUE_JUDGMENT_COMPLETENESS_INVALID",
        "Canonical evidence contains duplicate blind judgments for a fixture.",
        "Return one bound blind judgment for every frozen pair.",
        { fixtureId: judgment.fixtureId },
      );
    const fixture = fixtureById.get(judgment.fixtureId);
    const schedule = run.randomizedOrder.judgments[judgment.position];
    if (
      fixture === undefined ||
      schedule === undefined ||
      schedule.fixtureId !== judgment.fixtureId
    )
      throw new P0ValidationError(
        "EVIDENCE_LINEAGE_INVALID",
        "A blind judgment is not bound to its seeded fixture position.",
        "Rebuild the judgment from the controller's deterministic blind order.",
        { fixtureId: judgment.fixtureId, position: judgment.position },
      );
    const first = armByKey.get(`${judgment.fixtureId}\0${schedule.firstArm}`);
    const second = armByKey.get(`${judgment.fixtureId}\0${schedule.secondArm}`);
    if (
      first === undefined ||
      second === undefined ||
      judgment.firstArtifactSha256 !== first.acceptanceArtifactSha256 ||
      judgment.secondArtifactSha256 !== second.acceptanceArtifactSha256
    )
      throw new P0ValidationError(
        "EVIDENCE_LINEAGE_INVALID",
        "A blind judgment artifact digest does not bind the controller-produced arm artifacts.",
        "Rebuild the masked judge request from the accepted arm artifact digests.",
        { fixtureId: judgment.fixtureId },
      );
    assertJudgeScoreMatchesRubric(
      judgment.first,
      fixture.rubric,
      `${judgment.fixtureId} first`,
    );
    assertJudgeScoreMatchesRubric(
      judgment.second,
      fixture.rubric,
      `${judgment.fixtureId} second`,
    );
    const expectedDigest = blindJudgeResultSha256({
      fixtureId: judgment.fixtureId,
      firstArtifactSha256: judgment.firstArtifactSha256,
      secondArtifactSha256: judgment.secondArtifactSha256,
      first: judgment.first,
      second: judgment.second,
    });
    if (expectedDigest !== judgment.judgeResultSha256)
      throw new P0ValidationError(
        "EVIDENCE_LINEAGE_INVALID",
        "A blind judge result digest does not match its masked artifact bindings and score.",
        "Recreate the judge result from the immutable masked pair.",
        { fixtureId: judgment.fixtureId },
      );
    judgmentByFixture.set(judgment.fixtureId, judgment);
  }
  const pairs = provenance.fixtures.map((fixture) => {
    const control = armByKey.get(`${fixture.fixtureId}\0control`);
    const treatment = armByKey.get(`${fixture.fixtureId}\0treatment`);
    const judgment = judgmentByFixture.get(fixture.fixtureId);
    const order = run.randomizedOrder.judgments.find(
      (entry) => entry.fixtureId === fixture.fixtureId,
    );
    if (
      control === undefined ||
      treatment === undefined ||
      judgment === undefined ||
      order === undefined
    )
      throw new P0ValidationError(
        "VALUE_PAIR_INCOMPLETE",
        "Canonical evidence cannot reconstruct one complete scored fixture pair.",
        "Restore both arm outcomes and the bound blind judgment for every fixture.",
        { fixtureId: fixture.fixtureId },
      );
    const scoresByArm = {
      [order.firstArm]: judgment.first,
      [order.secondArm]: judgment.second,
    };
    return {
      fixtureId: fixture.fixtureId,
      expectedRequiredGates: fixture.expectedRequiredGates,
      expectedRouteCost: fixture.expectedRouteCost,
      control: scoringArm(control),
      treatment: scoringArm(treatment),
      judge: {
        control: scoresByArm.control,
        treatment: scoresByArm.treatment,
      },
    };
  });
  const score = scoreValueStudy({
    schemaVersion: 1,
    sourceTreeSha256: run.sourceTreeSha256,
    execution: {
      runtimeVersion: run.environment.runtimeVersion,
      modelId: run.environment.executionModelId,
      processId: run.environment.executionProcessId,
    },
    judge: {
      modelId: run.environment.judgeModelId,
      processId: run.environment.judgeProcessId,
    },
    pairs,
  });
  if (
    stableJson(score.metrics) !== stableJson(run.metrics) ||
    score.status !== run.valueGateStatus
  )
    throw new P0ValidationError(
      "VALUE_SCORE_MISMATCH",
      "Canonical value metrics or gate status do not match deterministic recomputation.",
      "Discard the tampered snapshot and create a new controller-produced complete run.",
      { recomputedStatus: score.status, recordedStatus: run.valueGateStatus },
    );
  if (
    run.releaseDecision === "ready" &&
    (run.technicalStatus !== "passed" || run.valueGateStatus !== "passed")
  )
    throw new P0ValidationError(
      "RELEASE_DECISION_INVALID",
      "A ready release decision requires both technical and value gates to pass.",
      "Record a blocked decision until both independently verified gates pass.",
    );
  return run;
}

function assertPromotableRun(
  input: unknown,
  controllerLedger?: unknown,
): CanonicalEvidenceRun {
  const run = assertCanonicalEvidenceRun(input);
  if (controllerLedger === undefined) return run;
  assertSanitizedValue(controllerLedger, "controller-provenance");
  const parsedLedger =
    controllerProvenanceLedgerSchema.safeParse(controllerLedger);
  if (!parsedLedger.success)
    throw new P0ValidationError(
      "EVIDENCE_LINEAGE_INVALID",
      "The controller provenance ledger is absent or invalid.",
      "Use only a controller-produced temporary ledger for canonical promotion.",
      { issues: parsedLedger.error.issues.map((issue) => issue.message) },
    );
  const ledger = parsedLedger.data;
  if (
    digest(stableJson(ledger)) !==
    run.completionProvenance.controllerProvenanceSha256
  )
    throw new P0ValidationError(
      "EVIDENCE_LINEAGE_INVALID",
      "The canonical run is not bound to the controller-produced provenance ledger.",
      "Start a new complete study; caller-authored canonical records cannot be promoted.",
      { runId: run.runId },
    );
  const canonicalLedgerView = {
    runId: run.runId,
    sourceTreeSha256: run.sourceTreeSha256,
    catalogSha256: run.catalogSha256,
    corpusSha256: run.corpusSha256,
    rubricSha256: run.rubricSha256,
    environment: run.environment,
    randomizedOrder: run.randomizedOrder,
    fixtures: run.completionProvenance.fixtures,
    arms: run.completionProvenance.arms,
    judgments: run.completionProvenance.judgments,
  };
  const ledgerView = {
    runId: ledger.runId,
    sourceTreeSha256: ledger.sourceTreeSha256,
    catalogSha256: ledger.catalogSha256,
    corpusSha256: ledger.corpusSha256,
    rubricSha256: ledger.rubricSha256,
    environment: ledger.environment,
    randomizedOrder: ledger.randomizedOrder,
    fixtures: ledger.fixtures,
    arms: ledger.arms.map(({ acceptanceArtifact: _artifact, ...arm }) => arm),
    judgments: ledger.judgments,
  };
  if (stableJson(canonicalLedgerView) !== stableJson(ledgerView))
    throw new P0ValidationError(
      "EVIDENCE_LINEAGE_INVALID",
      "The canonical run differs from its controller-produced provenance ledger.",
      "Promote only the exact controller-produced digest graph.",
      { runId: run.runId },
    );
  for (const arm of ledger.arms) {
    if (
      acceptanceArtifactSha256(arm.acceptanceArtifact) !==
      arm.acceptanceArtifactSha256
    )
      throw new P0ValidationError(
        "EVIDENCE_LINEAGE_INVALID",
        "A controller acceptance artifact digest does not match its bounded artifact.",
        "Discard the temporary run and execute a new isolated arm.",
        { fixtureId: arm.fixtureId, arm: arm.arm },
      );
  }
  return run;
}
const checksumsSchema = z
  .object({
    schemaVersion: z.literal(1),
    files: z.record(relativePathSchema, hashSchema),
  })
  .strict();
const latestPointerSchema = z
  .object({
    schemaVersion: z.literal(1),
    runId: runIdSchema,
    sourceTreeSha256: hashSchema,
    completedAt: isoDateSchema,
  })
  .strict();
export type LatestEvidencePointer = z.infer<typeof latestPointerSchema>;

function renderRunSummary(run: CanonicalEvidenceRun): string {
  const status = run.releaseDecision === "ready" ? "就绪" : "阻断";
  const blockers =
    run.blockers.length === 0
      ? "- 无\n"
      : run.blockers
          .map((blocker) => `- ${blocker.code}：${blocker.recovery}`)
          .join("\n")
          .concat("\n");
  return [
    `# P0 发布证据摘要 — ${run.runId}`,
    "",
    `- 发布决定：${status} (${run.releaseDecision})`,
    `- 来源树 SHA-256：${run.sourceTreeSha256}`,
    `- 技术一致性：${run.technicalStatus}`,
    `- 价值 Gate：${run.valueGateStatus}`,
    `- 配对数：${run.metrics.pairCount}`,
    `- Mandatory Gate recall：${run.metrics.gateRecall}`,
    `- 不必要重 Route：${run.metrics.unnecessaryHeavyRouteActivations}`,
    "",
    "## 阻断与恢复",
    "",
    blockers.trimEnd(),
    "",
  ].join("\n");
}

async function readOptionalJson<T>(
  path: string,
  schema: z.ZodType<T>,
  context: string,
  files: P0FileSystem,
): Promise<T | undefined> {
  try {
    return parsedJson(schema, await files.readText(path), context);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

export interface EvidenceStoreOptions {
  readonly evidenceRoot: string;
  readonly temporaryRoot: string;
  readonly files?: P0FileSystem;
}

export class EvidenceStore {
  private readonly files: P0FileSystem;
  private readonly evidenceRoot: string;
  private readonly temporaryRoot: string;

  constructor(options: EvidenceStoreOptions) {
    this.files = options.files ?? createNodeFileSystem();
    this.evidenceRoot = resolve(options.evidenceRoot);
    this.temporaryRoot = resolve(options.temporaryRoot);
  }

  private candidateRoot(candidate: CandidateIdentity): string {
    return safeRelativePath(
      this.evidenceRoot,
      join(this.evidenceRoot, "candidates", candidateIdentitySha256(candidate)),
    );
  }

  private async writeImmutableJson(
    path: string,
    value: unknown,
    code: string,
    message: string,
    recovery: string,
  ): Promise<void> {
    try {
      await this.files.inspect(path);
      throw new P0ValidationError(code, message, recovery);
    } catch (error) {
      if (error instanceof P0ValidationError) throw error;
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    const staging = join(dirname(path), `.${randomUUID()}.stage.json`);
    try {
      await this.files.makeDirectory(dirname(path));
      await this.files.writeText(staging, stableJson(value));
      await this.files.move(staging, path);
    } catch (error) {
      await this.files.remove(staging);
      throw error;
    }
  }

  private async readImmutableRecords<T>(
    directory: string,
    schema: z.ZodType<T>,
    context: string,
  ): Promise<readonly T[]> {
    let entries: readonly P0DirectoryEntry[];
    try {
      entries = await this.files.list(directory);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
    const records: T[] = [];
    for (const entry of entries) {
      if (entry.kind !== "file" || !entry.name.endsWith(".json"))
        throw new P0ValidationError(
          "EVIDENCE_STORE_INVALID",
          `${context} contains a non-record entry.`,
          "Discard the malformed local evidence directory and create a new immutable record.",
        );
      records.push(
        parsedJson(
          schema,
          await this.files.readText(join(directory, entry.name)),
          `${context} ${entry.name}`,
        ),
      );
    }
    return records;
  }

  async recordCandidate(input: unknown): Promise<CandidateRecord> {
    const candidate = assertCandidateRecord(input);
    const candidateId = candidateIdentitySha256(candidate.candidate);
    const recordPath = join(
      this.candidateRoot(candidate.candidate),
      "candidate.json",
    );
    const existing = await readOptionalJson(
      recordPath,
      candidateRecordSchema,
      "immutable release candidate",
      this.files,
    );
    if (existing !== undefined) {
      const verified = assertCandidateRecord(existing);
      if (stableJson(verified) === stableJson(candidate)) return verified;
      throw new P0ValidationError(
        "CANDIDATE_ALREADY_EXISTS",
        "Candidate identity already has a different immutable admission record.",
        "Create a new candidate identity rather than mutating its channel, dist-tag, or timestamp.",
        { candidateId },
      );
    }
    await this.writeImmutableJson(
      recordPath,
      candidate,
      "CANDIDATE_ALREADY_EXISTS",
      "Candidate identity already has an immutable admission record.",
      "Create a new candidate identity rather than overwriting an existing record.",
    );
    return candidate;
  }

  async readCandidate(
    candidateId: string,
  ): Promise<CandidateRecord | undefined> {
    const parsedId = hashSchema.safeParse(candidateId);
    if (!parsedId.success)
      throw new P0ValidationError(
        "CANDIDATE_ID_INVALID",
        "Candidate lookup requires the immutable candidate identity digest.",
        "Use the candidate identity SHA-256 returned by the release validator.",
      );
    const record = await readOptionalJson(
      join(this.evidenceRoot, "candidates", parsedId.data, "candidate.json"),
      candidateRecordSchema,
      "immutable release candidate",
      this.files,
    );
    return record === undefined ? undefined : assertCandidateRecord(record);
  }

  private async requireCandidate(
    candidate: CandidateIdentity,
  ): Promise<CandidateRecord> {
    const candidateId = candidateIdentitySha256(candidate);
    const record = await this.readCandidate(candidateId);
    if (record === undefined)
      throw new P0ValidationError(
        "CANDIDATE_MISSING",
        "Candidate-bound evidence requires an immutable candidate admission record.",
        "Record the exact candidate before appending its gate evidence or observations.",
        { candidateId },
      );
    if (candidateIdentitySha256(record.candidate) !== candidateId)
      throw new P0ValidationError(
        "CANDIDATE_BINDING_MISMATCH",
        "Candidate admission record does not match the candidate-bound evidence identity.",
        "Create a new exact candidate record and regenerate the bound evidence.",
        { candidateId },
      );
    return record;
  }

  async recordCandidateEvidence(input: unknown): Promise<CandidateEvidence> {
    const evidence = assertCandidateEvidence(input);
    await this.requireCandidate(evidence.candidate);
    const recordPath = join(
      this.candidateRoot(evidence.candidate),
      "evidence",
      `${evidence.evidenceId}.json`,
    );
    await this.writeImmutableJson(
      recordPath,
      evidence,
      "CANDIDATE_EVIDENCE_ALREADY_EXISTS",
      "Candidate gate evidence ID already exists and is immutable.",
      "Use a new evidence ID for a new exact-candidate gate result.",
    );
    return evidence;
  }

  async readCandidateEvidence(
    candidate: CandidateIdentity,
  ): Promise<readonly CandidateEvidence[]> {
    await this.requireCandidate(candidate);
    const records = await this.readImmutableRecords(
      join(this.candidateRoot(candidate), "evidence"),
      candidateEvidenceSchema,
      "candidate gate evidence",
    );
    return records.map(assertCandidateEvidence);
  }

  async appendObservation(input: unknown): Promise<CandidateObservation> {
    const observation = assertCandidateObservation(input);
    await this.requireCandidate(observation.candidate);
    const recordPath = join(
      this.candidateRoot(observation.candidate),
      "observations",
      `${observation.observationId}.json`,
    );
    await this.writeImmutableJson(
      recordPath,
      observation,
      "OBSERVATION_ALREADY_EXISTS",
      "Candidate observation ID already exists and observations are append-only.",
      "Append a new observation ID; never edit or overwrite a prior observation.",
    );
    return observation;
  }

  async readCandidateObservations(
    candidate: CandidateIdentity,
  ): Promise<readonly CandidateObservation[]> {
    await this.requireCandidate(candidate);
    const records = await this.readImmutableRecords(
      join(this.candidateRoot(candidate), "observations"),
      candidateObservationSchema,
      "candidate observations",
    );
    return records.map(assertCandidateObservation);
  }

  async attestCandidateEquivalence(
    input: CandidateEquivalenceVerificationInput,
  ): Promise<CandidateEquivalenceAttestation> {
    const attestation = verifyCandidateEquivalence(input);
    await Promise.all([
      this.requireCandidate(attestation.rcCandidate),
      this.requireCandidate(attestation.stableCandidate),
    ]);
    const attestationPath = join(
      this.evidenceRoot,
      "attestations",
      `${candidateIdentitySha256(attestation.rcCandidate)}-${candidateIdentitySha256(attestation.stableCandidate)}.json`,
    );
    const existing = await readOptionalJson(
      attestationPath,
      candidateEquivalenceAttestationSchema,
      "immutable candidate-equivalence attestation",
      this.files,
    );
    if (existing !== undefined) {
      const verified = assertCandidateEquivalenceAttestation(existing);
      if (
        candidateIdentitySha256(verified.rcCandidate) ===
          candidateIdentitySha256(attestation.rcCandidate) &&
        candidateIdentitySha256(verified.stableCandidate) ===
          candidateIdentitySha256(attestation.stableCandidate) &&
        verified.normalizedPayloadSha256 === attestation.normalizedPayloadSha256
      )
        return verified;
      throw new P0ValidationError(
        "ATTESTATION_CONFLICT",
        "The exact RC/stable pair already has a conflicting immutable equivalence attestation.",
        "Create a new candidate pair; never replace an existing attestation.",
      );
    }
    await this.writeImmutableJson(
      attestationPath,
      attestation,
      "ATTESTATION_CONFLICT",
      "The exact RC/stable pair already has an immutable equivalence attestation.",
      "Create a new candidate pair; never overwrite an existing attestation.",
    );
    return attestation;
  }

  private async readCandidateAttestations(): Promise<
    readonly CandidateEquivalenceAttestation[]
  > {
    const records = await this.readImmutableRecords(
      join(this.evidenceRoot, "attestations"),
      candidateEquivalenceAttestationSchema,
      "candidate-equivalence attestations",
    );
    return records.map(assertCandidateEquivalenceAttestation);
  }

  async decideCandidate(
    candidateId: string,
  ): Promise<CandidateReleaseDecision> {
    const record = await this.readCandidate(candidateId);
    if (record === undefined)
      throw new P0ValidationError(
        "CANDIDATE_MISSING",
        "Release decision requires an immutable candidate record.",
        "Record the exact candidate before deciding its RC eligibility or stable readiness.",
        { candidateId },
      );
    const [directEvidence, observations, allAttestations] = await Promise.all([
      this.readCandidateEvidence(record.candidate),
      this.readCandidateObservations(record.candidate),
      this.readCandidateAttestations(),
    ]);
    const attestations = allAttestations.filter(
      (attestation) =>
        candidateIdentitySha256(attestation.stableCandidate) === candidateId,
    );
    const forwardedEvidence = (
      await Promise.all(
        attestations.map((attestation) =>
          this.readCandidateEvidence(attestation.rcCandidate),
        ),
      )
    ).flat();
    const decision = decideRelease({
      candidate: record.candidate,
      candidateRecord: record,
      evidence: [...directEvidence, ...forwardedEvidence],
      attestations,
      observations,
    });
    if ("candidate" in decision) return decision;
    throw new P0ValidationError(
      "CANDIDATE_RELEASE_DECISION_INVALID",
      "Candidate evidence was evaluated through the legacy release decision path.",
      "Rebuild the candidate decision from its immutable candidate-bound records.",
    );
  }

  async createRawRun(runId: string): Promise<string> {
    const validRunId = runIdSchema.safeParse(runId);
    if (!validRunId.success)
      throw new P0ValidationError(
        "RUN_ID_INVALID",
        "Raw P0 evidence needs a safe stable run ID.",
        "Create a new lowercase run ID before writing local raw events.",
      );
    const path = join(this.temporaryRoot, validRunId.data);
    safeRelativePath(this.temporaryRoot, path);
    await this.files.makeDirectory(path);
    return path;
  }

  async materializeFixture(
    runId: string,
    fixture: ValueStudyFixture,
    arm: "control" | "treatment",
  ): Promise<string> {
    const safeFixture = validateValueStudyFixture(fixture);
    const rawRun = await this.createRawRun(runId);
    const workspace = safeRelativePath(
      rawRun,
      join(rawRun, "workspaces", safeFixture.id, arm),
    );
    await this.files.makeDirectory(workspace);
    for (const [relativePath, content] of Object.entries(
      safeFixture.startingFiles,
    )) {
      const file = safeRelativePath(workspace, join(workspace, relativePath));
      await this.files.writeText(file, content);
    }
    return workspace;
  }

  async writeRawRecord(
    runId: string,
    relativePath: string,
    value: unknown,
  ): Promise<void> {
    assertSanitizedValue(value, `temporary-run:${runId}:${relativePath}`);
    const rawRun = await this.createRawRun(runId);
    const parsedPath = relativePathSchema.safeParse(relativePath);
    if (!parsedPath.success)
      throw new P0ValidationError(
        "UNSAFE_PATH",
        "Raw P0 evidence record path is unsafe.",
        "Use a non-empty relative path below the local run directory.",
      );
    const path = safeRelativePath(rawRun, join(rawRun, parsedPath.data));
    await this.files.writeText(path, stableJson(value));
  }

  async readLatest(): Promise<LatestEvidencePointer | undefined> {
    return readOptionalJson(
      join(this.evidenceRoot, "latest.json"),
      latestPointerSchema,
      "P0 latest evidence pointer",
      this.files,
    );
  }

  async readApproval(): Promise<
    z.infer<typeof approvalPointerSchema> | undefined
  > {
    return readOptionalJson(
      join(this.evidenceRoot, "approved.json"),
      approvalPointerSchema,
      "P0 approved evidence pointer",
      this.files,
    );
  }

  async approveLatest(): Promise<z.infer<typeof approvalPointerSchema>> {
    const latest = await this.readLatest();
    if (latest === undefined)
      throw new P0ValidationError(
        "LATEST_EVIDENCE_MISSING",
        "A current complete P0 evidence run is required before approval.",
        "Promote and verify the current immutable evidence run before approving it.",
      );
    const run = await verifyEvidenceSnapshot(
      this.evidenceRoot,
      latest.runId,
      this.files,
    );
    if (
      run.sourceTreeSha256 !== latest.sourceTreeSha256 ||
      run.releaseDecision !== "ready" ||
      run.technicalStatus !== "passed" ||
      run.valueGateStatus !== "passed"
    )
      throw new P0ValidationError(
        "APPROVAL_NOT_ELIGIBLE",
        "Only the newest complete run with passing technical and value gates may be approved.",
        "Resolve the latest run blockers and create a new immutable ready run before approval.",
        { runId: latest.runId, releaseDecision: run.releaseDecision },
      );
    const approval = approvalPointerSchema.parse({
      schemaVersion: 1,
      runId: latest.runId,
      sourceTreeSha256: latest.sourceTreeSha256,
    });
    const staging = join(this.evidenceRoot, `.approved-${randomUUID()}.json`);
    try {
      await this.files.writeText(staging, stableJson(approval));
      await this.files.move(staging, join(this.evidenceRoot, "approved.json"));
      return approval;
    } catch (error) {
      await this.files.remove(staging);
      throw error;
    }
  }

  async promote(input: unknown): Promise<LatestEvidencePointer> {
    const candidate = assertCanonicalEvidenceRun(input);
    const rawRun = join(this.temporaryRoot, candidate.runId);
    let rawLedger: string;
    try {
      rawLedger = await this.files.readText(
        safeRelativePath(rawRun, join(rawRun, "controller-provenance.json")),
      );
    } catch {
      throw new P0ValidationError(
        "EVIDENCE_LINEAGE_INVALID",
        "Canonical promotion requires the controller-produced temporary provenance ledger.",
        "Run the authorized complete study; caller-authored records cannot create canonical evidence.",
        { runId: candidate.runId },
      );
    }
    const controllerLedger = parsedJson(
      controllerProvenanceLedgerSchema,
      rawLedger,
      "controller-produced temporary value-study provenance",
    );
    const run = assertPromotableRun(candidate, controllerLedger);
    const runsRoot = join(this.evidenceRoot, "runs");
    const destination = join(runsRoot, run.runId);
    try {
      await this.files.inspect(destination);
      throw new P0ValidationError(
        "RUN_ALREADY_EXISTS",
        `Canonical P0 evidence run ${run.runId} already exists and is immutable.`,
        "Choose a new run ID; never overwrite an existing canonical evidence snapshot.",
        { runId: run.runId },
      );
    } catch (error) {
      if (error instanceof P0ValidationError) throw error;
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    const staging = join(this.evidenceRoot, `.stage-${randomUUID()}`);
    const runJson = stableJson(run);
    const summary = renderRunSummary(run);
    const checksums = {
      schemaVersion: 1 as const,
      files: {
        "run.json": digest(runJson),
        "summary.md": digest(summary),
      },
    };
    const pointer: LatestEvidencePointer = {
      schemaVersion: 1,
      runId: run.runId,
      sourceTreeSha256: run.sourceTreeSha256,
      completedAt: run.createdAt,
    };
    try {
      await this.files.makeDirectory(staging);
      await Promise.all([
        this.files.writeText(join(staging, "run.json"), runJson),
        this.files.writeText(join(staging, "summary.md"), summary),
        this.files.writeText(
          join(staging, "checksums.json"),
          stableJson(checksums),
        ),
      ]);
      await this.files.makeDirectory(runsRoot);
      await this.files.move(staging, destination);
      const pointerStaging = join(
        this.evidenceRoot,
        `.latest-${randomUUID()}.json`,
      );
      await this.files.writeText(pointerStaging, stableJson(pointer));
      await this.files.move(
        pointerStaging,
        join(this.evidenceRoot, "latest.json"),
      );
      return pointer;
    } catch (error) {
      await this.files.remove(staging);
      throw error;
    }
  }
}

export function createEvidenceStore(
  options: EvidenceStoreOptions,
): EvidenceStore {
  return new EvidenceStore(options);
}

export async function verifyEvidenceSnapshot(
  evidenceRoot: string,
  runId: string,
  files: P0FileSystem = createNodeFileSystem(),
): Promise<CanonicalEvidenceRun> {
  const safeRunId = runIdSchema.safeParse(runId);
  if (!safeRunId.success)
    throw new P0ValidationError(
      "RUN_ID_INVALID",
      "Evidence verification needs a safe stable run ID.",
      "Use the run ID from latest.json or the immutable runs directory.",
    );
  const runRoot = join(resolve(evidenceRoot), "runs", safeRunId.data);
  const checksums = parsedJson(
    checksumsSchema,
    await files.readText(join(runRoot, "checksums.json")),
    "P0 evidence checksum inventory",
  );
  for (const [path, expectedDigest] of Object.entries(checksums.files)) {
    const target = safeRelativePath(runRoot, join(runRoot, path));
    const actualDigest = digest(await files.readText(target));
    if (actualDigest !== expectedDigest)
      throw new P0ValidationError(
        "EVIDENCE_CHECKSUM_MISMATCH",
        `Canonical P0 evidence checksum differs for ${path}`,
        "Discard the tampered snapshot and create a new immutable run from verified raw local evidence.",
        { path, expectedDigest, actualDigest },
      );
  }
  return assertPromotableRun(
    parsedJson(
      canonicalEvidenceRunSchema,
      await files.readText(join(runRoot, "run.json")),
      "canonical P0 evidence run",
    ),
  );
}

const approvalPointerSchema = z
  .object({
    schemaVersion: z.literal(1).optional().default(1),
    runId: runIdSchema,
    sourceTreeSha256: hashSchema,
  })
  .strict();
const releaseDecisionInputSchema = z
  .object({
    sourceTreeSha256: hashSchema,
    technicalStatus: statusSchema,
    valueGateStatus: statusSchema,
    latest: z
      .object({
        runId: runIdSchema,
        sourceTreeSha256: hashSchema,
        releaseDecision: z.enum(["ready", "blocked"]),
      })
      .strict()
      .optional(),
    approved: approvalPointerSchema.optional(),
  })
  .strict();
export const candidateReleaseDecisionInputSchema = z
  .object({
    candidate: candidateIdentitySchema,
    candidateRecord: candidateRecordSchema,
    evidence: z.array(candidateEvidenceSchema),
    attestations: z.array(candidateEquivalenceAttestationSchema),
    observations: z.array(candidateObservationSchema),
  })
  .strict();
type CandidateReleaseDecisionInput = z.infer<
  typeof candidateReleaseDecisionInputSchema
>;
type CandidateGateSource =
  | "direct"
  | "attested-rc"
  | "missing"
  | "not-required";

export interface LegacyReleaseDecision {
  readonly schemaVersion: 1;
  readonly decision: "ready" | "blocked";
  readonly blockers: readonly z.infer<typeof blockerSchema>[];
}

export interface CandidateReleaseDecision {
  readonly schemaVersion: 1;
  readonly decision: "ready" | "rc-eligible" | "blocked";
  readonly candidate: CandidateIdentity;
  readonly gateSources: Readonly<{
    technical: CandidateGateSource;
    package: CandidateGateSource;
    compatibility: CandidateGateSource;
    value: CandidateGateSource;
  }>;
  readonly blockers: readonly z.infer<typeof blockerSchema>[];
}

function assertCandidateReleaseDecisionInput(
  input: unknown,
): CandidateReleaseDecisionInput {
  assertSanitizedValue(input, "candidate-release-decision");
  const parsed = candidateReleaseDecisionInputSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "CANDIDATE_RELEASE_DECISION_SCHEMA_INVALID",
      "Candidate release decision input violates its strict schema.",
      "Decide from one candidate record and exact candidate-bound evidence only.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const candidate = parseCandidateIdentity(
    parsed.data.candidate,
    "candidate-release-decision candidate",
  );
  const candidateRecord = assertCandidateRecord(parsed.data.candidateRecord);
  if (
    candidateIdentitySha256(candidate) !==
    candidateIdentitySha256(candidateRecord.candidate)
  )
    throw new P0ValidationError(
      "CANDIDATE_BINDING_MISMATCH",
      "Candidate decision record is bound to a different candidate identity.",
      "Use the immutable candidate record for the exact candidate being decided.",
    );
  return {
    ...parsed.data,
    candidate,
    candidateRecord,
    evidence: parsed.data.evidence.map(assertCandidateEvidence),
    attestations: parsed.data.attestations.map(
      assertCandidateEquivalenceAttestation,
    ),
    observations: parsed.data.observations.map(assertCandidateObservation),
  };
}

function currentPassedCandidateEvidence(
  evidence: readonly CandidateEvidence[],
  candidateId: string,
  gate: CandidateEvidence["gate"],
): CandidateEvidence | undefined {
  const matching = evidence.filter(
    (record) =>
      record.gate === gate &&
      candidateIdentitySha256(record.candidate) === candidateId,
  );
  const latestRecordedAt = matching.reduce<string | undefined>(
    (latest, record) =>
      latest === undefined || record.recordedAt > latest
        ? record.recordedAt
        : latest,
    undefined,
  );
  if (latestRecordedAt === undefined) return undefined;
  const current = matching.filter(
    (record) => record.recordedAt === latestRecordedAt,
  );
  return current.every((record) => record.status === "passed")
    ? current[0]
    : undefined;
}

function decideCandidateRelease(
  input: CandidateReleaseDecisionInput,
): CandidateReleaseDecision {
  const candidateId = candidateIdentitySha256(input.candidate);
  const attestations = input.attestations.filter(
    (attestation) =>
      candidateIdentitySha256(attestation.stableCandidate) === candidateId,
  );
  const attestedRcCandidateIds = new Set(
    attestations.map((attestation) =>
      candidateIdentitySha256(attestation.rcCandidate),
    ),
  );
  const allowedEvidenceCandidateIds = new Set([
    candidateId,
    ...attestedRcCandidateIds,
  ]);
  const directTechnical = currentPassedCandidateEvidence(
    input.evidence,
    candidateId,
    "technical",
  );
  const directPackage = currentPassedCandidateEvidence(
    input.evidence,
    candidateId,
    "package",
  );
  const directCompatibility = currentPassedCandidateEvidence(
    input.evidence,
    candidateId,
    "compatibility",
  );
  const directValue = currentPassedCandidateEvidence(
    input.evidence,
    candidateId,
    "value",
  );
  const forwardedCompatibility =
    input.candidateRecord.channel === "stable"
      ? attestations
          .map((attestation) =>
            currentPassedCandidateEvidence(
              input.evidence,
              candidateIdentitySha256(attestation.rcCandidate),
              "compatibility",
            ),
          )
          .find((evidence) => evidence !== undefined)
      : undefined;
  const forwardedValue =
    input.candidateRecord.channel === "stable"
      ? attestations
          .map((attestation) =>
            currentPassedCandidateEvidence(
              input.evidence,
              candidateIdentitySha256(attestation.rcCandidate),
              "value",
            ),
          )
          .find((evidence) => evidence !== undefined)
      : undefined;
  const gateSources: CandidateReleaseDecision["gateSources"] = {
    technical: directTechnical === undefined ? "missing" : "direct",
    package: directPackage === undefined ? "missing" : "direct",
    compatibility:
      directCompatibility !== undefined
        ? "direct"
        : forwardedCompatibility !== undefined
          ? "attested-rc"
          : input.candidateRecord.channel === "rc"
            ? "not-required"
            : "missing",
    value:
      directValue !== undefined
        ? "direct"
        : forwardedValue !== undefined
          ? "attested-rc"
          : input.candidateRecord.channel === "rc"
            ? "not-required"
            : "missing",
  };
  const blockers: z.infer<typeof blockerSchema>[] = [];
  if (gateSources.technical === "missing")
    blockers.push({
      code: "TECHNICAL_EVIDENCE_MISSING",
      reason:
        "No passing current technical evidence is bound to this exact candidate.",
      recovery:
        "Rerun technical conformance for this candidate source and packed-tarball identity.",
    });
  if (gateSources.package === "missing")
    blockers.push({
      code: "PACKAGE_EVIDENCE_MISSING",
      reason:
        "No passing packed-package evidence is bound to this exact candidate.",
      recovery:
        "Inspect the exact packed tarball and append a passing package evidence record.",
    });
  if (
    input.candidateRecord.channel === "stable" &&
    gateSources.compatibility === "missing"
  )
    blockers.push({
      code: "COMPATIBILITY_EVIDENCE_MISSING",
      reason:
        "No passing direct or exact-attested RC compatibility evidence is available for this stable candidate.",
      recovery:
        "Run compatibility for this stable candidate or verify equivalence with the exact RC that supplied it.",
    });
  if (
    input.candidateRecord.channel === "stable" &&
    gateSources.value === "missing"
  )
    blockers.push({
      code: "VALUE_EVIDENCE_MISSING",
      reason:
        "No passing direct or exact-attested RC value-study evidence is available for this stable candidate.",
      recovery:
        "Run the complete value study for this stable candidate or verify equivalence with the exact RC that supplied it.",
    });
  const externalProtocolEvidence = input.evidence.some(
    (evidence) =>
      (evidence.gate === "compatibility" || evidence.gate === "value") &&
      evidence.status === "passed" &&
      candidateIdentitySha256(evidence.candidate) !== candidateId,
  );
  if (
    input.candidateRecord.channel === "stable" &&
    externalProtocolEvidence &&
    attestations.length === 0
  )
    blockers.push({
      code: "CANDIDATE_EQUIVALENCE_MISSING",
      reason:
        "Protocol evidence belongs to another candidate without an exact RC-to-stable equivalence attestation.",
      recovery:
        "Verify packed payload equivalence for the exact RC and stable candidate pair before forwarding protocol evidence.",
    });
  if (
    input.evidence.some(
      (evidence) =>
        !allowedEvidenceCandidateIds.has(
          candidateIdentitySha256(evidence.candidate),
        ),
    )
  )
    blockers.push({
      code: "CANDIDATE_EVIDENCE_MISMATCH",
      reason:
        "Decision input contains evidence bound to a candidate outside this candidate or its exact attested RC source.",
      recovery:
        "Remove cross-candidate evidence and rerun the missing Gate for the exact candidate.",
    });
  if (
    input.observations.some(
      (observation) =>
        candidateIdentitySha256(observation.candidate) !== candidateId,
    )
  )
    blockers.push({
      code: "CANDIDATE_OBSERVATION_MISMATCH",
      reason:
        "Decision input contains an observation bound to another candidate.",
      recovery:
        "Keep observations with their exact candidate; observations never satisfy a release Gate.",
    });
  if (input.candidateRecord.channel === "rc")
    return {
      schemaVersion: 1,
      decision: blockers.length === 0 ? "rc-eligible" : "blocked",
      candidate: input.candidate,
      gateSources,
      blockers,
    };
  return {
    schemaVersion: 1,
    decision: blockers.length === 0 ? "ready" : "blocked",
    candidate: input.candidate,
    gateSources,
    blockers,
  };
}

export type ReleaseDecision = LegacyReleaseDecision | CandidateReleaseDecision;

function decideLegacyRelease(input: unknown): LegacyReleaseDecision {
  const parsed = releaseDecisionInputSchema.safeParse(input);
  if (!parsed.success)
    throw new P0ValidationError(
      "RELEASE_DECISION_SCHEMA_INVALID",
      "Release decision input violates its strict schema.",
      "Rebuild the decision from current technical, value, latest, and approval records.",
      { issues: parsed.error.issues.map((issue) => issue.message) },
    );
  const blockers: z.infer<typeof blockerSchema>[] = [];
  if (parsed.data.technicalStatus !== "passed")
    blockers.push({
      code: "TECHNICAL_CONFORMANCE_NOT_PASSED",
      reason: `Technical conformance is ${parsed.data.technicalStatus}.`,
      recovery:
        "Resolve every current technical failure or blocker and regenerate its report.",
    });
  if (parsed.data.valueGateStatus !== "passed")
    blockers.push({
      code: "VALUE_GATE_NOT_PASSED",
      reason: `Value Gate is ${parsed.data.valueGateStatus}.`,
      recovery:
        "Complete a valid paired study and score its immutable sanitized evidence.",
    });
  if (parsed.data.latest === undefined)
    blockers.push({
      code: "LATEST_EVIDENCE_MISSING",
      reason: "No complete current evidence snapshot is recorded.",
      recovery:
        "Promote a complete sanitized immutable run before deciding release readiness.",
    });
  else {
    if (parsed.data.latest.sourceTreeSha256 !== parsed.data.sourceTreeSha256)
      blockers.push({
        code: "SOURCE_TREE_MISMATCH",
        reason: "latest.json was produced for a different source-tree digest.",
        recovery:
          "Rerun conformance and value evidence for the exact current source snapshot.",
      });
    if (parsed.data.latest.releaseDecision !== "ready")
      blockers.push({
        code: "LATEST_RUN_BLOCKED",
        reason: "The newest complete evidence run is blocked.",
        recovery:
          "Resolve the latest run blockers; an older approved run cannot override it.",
      });
  }
  if (
    parsed.data.approved === undefined ||
    parsed.data.latest === undefined ||
    parsed.data.approved.runId !== parsed.data.latest.runId ||
    parsed.data.approved.sourceTreeSha256 !== parsed.data.sourceTreeSha256
  )
    blockers.push({
      code: "APPROVAL_STALE",
      reason:
        "approved.json does not attest to the newest complete run and current source tree.",
      recovery:
        "Approve only the latest complete run after reviewing its immutable evidence.",
    });
  return {
    schemaVersion: 1,
    decision: blockers.length === 0 ? "ready" : "blocked",
    blockers,
  };
}

export function decideRelease(input: unknown): ReleaseDecision {
  if (
    input !== null &&
    typeof input === "object" &&
    "candidate" in (input as Record<string, unknown>)
  )
    return decideCandidateRelease(assertCandidateReleaseDecisionInput(input));
  return decideLegacyRelease(input);
}

export interface ProcessResult {
  readonly exitCode: number | null;
  readonly stdout: string;
  readonly stderr: string;
  readonly timedOut: boolean;
}

export interface ProcessRunner {
  readonly run: (
    command: readonly string[],
    options: Readonly<{ cwd: string; timeoutMs: number }>,
  ) => Promise<ProcessResult>;
}

export function createNodeProcessRunner(): ProcessRunner {
  return {
    run: async (command, options) => {
      const [executable, ...args] = command;
      if (executable === undefined)
        throw new P0ValidationError(
          "COMMAND_INVALID",
          "P0 validation refuses an empty command.",
          "Attach an explicit executable command array to the evidence locator.",
        );
      return new Promise<ProcessResult>((resolveResult, rejectResult) => {
        const child = spawn(executable, args, {
          cwd: options.cwd,
          shell: false,
          stdio: ["ignore", "pipe", "pipe"] as const,
        });
        let stdout = "";
        let stderr = "";
        let timedOut = false;
        const timer = setTimeout(() => {
          timedOut = true;
          child.kill("SIGTERM");
        }, options.timeoutMs);
        child.stdout.setEncoding("utf8");
        child.stderr.setEncoding("utf8");
        child.stdout.on("data", (chunk: string) => {
          stdout += chunk;
        });
        child.stderr.on("data", (chunk: string) => {
          stderr += chunk;
        });
        child.once("error", (error) => {
          clearTimeout(timer);
          rejectResult(error);
        });
        child.once("close", (exitCode) => {
          clearTimeout(timer);
          resolveResult({ exitCode, stdout, stderr, timedOut });
        });
      });
    },
  };
}

export interface TechnicalEvidenceResult {
  readonly id: string;
  readonly status: z.infer<typeof statusSchema>;
  readonly commandDigests: readonly Readonly<{
    command: readonly string[];
    exitCode: number | null;
    stdoutSha256: string;
    stderrSha256: string;
    timedOut: boolean;
  }>[];
  readonly blocker?: z.infer<typeof blockerSchema>;
}

export function candidateTechnicalCatalog(
  catalog: ConformanceCatalog,
): Readonly<{
  catalog: ConformanceCatalog;
  excludedExternalEntryIds: readonly string[];
}> {
  return {
    catalog: {
      ...catalog,
      entries: catalog.entries.filter(
        (entry) => entry.evidenceRequirement === "automated",
      ),
    },
    excludedExternalEntryIds: catalog.entries
      .filter((entry) => entry.evidenceRequirement !== "automated")
      .map((entry) => entry.id),
  };
}

export function assertCandidateSourceTree(
  candidate: CandidateIdentity,
  sourceTreeSha256: string,
): void {
  if (candidate.sourceTreeSha256 === sourceTreeSha256) return;
  throw new P0ValidationError(
    "CANDIDATE_BINDING_MISMATCH",
    "Current source artifacts do not match the immutable candidate identity.",
    "Rebuild and record evidence for the exact admitted candidate.",
  );
}

export async function checkTechnicalConformance(
  catalog: ConformanceCatalog,
  workspaceRoot: string,
  runner: ProcessRunner,
  timeoutMs = 180_000,
): Promise<
  Readonly<{ schemaVersion: 1; entries: readonly TechnicalEvidenceResult[] }>
> {
  const commandCache = new Map<string, ProcessResult>();
  const results: TechnicalEvidenceResult[] = [];
  for (const entry of catalog.entries) {
    if (entry.evidenceRequirement === "blocked") {
      const blocker = entry.blocker;
      if (blocker === undefined)
        throw new P0ValidationError(
          "CATALOG_EVIDENCE_INVALID",
          `${entry.id} is blocked without a recovery path.`,
          "Attach a blocker before producing technical evidence.",
        );
      results.push({
        id: entry.id,
        status: "blocked",
        commandDigests: [],
        blocker,
      });
      continue;
    }
    if (entry.evidenceRequirement === "not-applicable") {
      results.push({
        id: entry.id,
        status: "not-applicable",
        commandDigests: [],
      });
      continue;
    }
    if (entry.evidenceRequirement === "manual") {
      results.push({
        id: entry.id,
        status: "blocked",
        commandDigests: [],
        blocker: {
          code: "MANUAL_EVIDENCE_REQUIRED",
          reason: "This P0 requirement needs named manual evidence.",
          recovery:
            "Attach approved manual evidence to a new current technical report.",
        },
      });
      continue;
    }
    const commands = entry.evidence
      .map((evidence) => evidence.command)
      .filter((command): command is string[] => command !== undefined);
    const commandDigests: Array<
      TechnicalEvidenceResult["commandDigests"][number]
    > = [];
    let failed = false;
    for (const command of commands) {
      const key = JSON.stringify(command);
      const cached = commandCache.get(key);
      const result =
        cached ??
        (await runner.run(command, { cwd: workspaceRoot, timeoutMs }));
      if (cached === undefined) commandCache.set(key, result);
      commandDigests.push({
        command,
        exitCode: result.exitCode,
        stdoutSha256: digest(result.stdout),
        stderrSha256: digest(result.stderr),
        timedOut: result.timedOut,
      });
      if (result.exitCode !== 0 || result.timedOut) failed = true;
    }
    results.push({
      id: entry.id,
      status: failed ? "failed" : "passed",
      commandDigests,
    });
  }
  return { schemaVersion: 1, entries: results };
}

const packageMetadataSchema = z
  .object({
    name: z.string().min(1),
    version: z.string().min(1),
    license: z.literal("Apache-2.0"),
    files: z.array(z.string().min(1)).optional(),
    dependencies: z.record(z.string(), z.string()).optional(),
    peerDependencies: z.record(z.string(), z.string()).optional(),
  })
  .passthrough();

const packageReleaseContractSchema = z.object({
  name: z.string().min(1),
  version: z.string().min(1),
  license: z.literal("Apache-2.0"),
  type: z.literal("module"),
  main: z.literal("./dist/extension.js"),
  types: z.literal("./dist/extension.d.ts"),
  files: z.array(z.string().min(1)),
  dependencies: z.record(z.string(), z.string()),
  peerDependencies: z.record(z.string(), z.string()),
  omp: z.object({ extensions: z.array(z.string().min(1)) }).strict(),
  pi: z.object({ extensions: z.array(z.string().min(1)) }).strict(),
});
const packageManifestSchema = z.record(z.string(), z.unknown());
const workspacePackageManifestSchema = z
  .object({
    name: z.string().min(1),
    version: z.string().min(1),
  })
  .passthrough();
const rootPackageMetadataSchema = z
  .object({
    license: z.string().min(1),
  })
  .passthrough();

export interface SbomFile {
  readonly path: string;
  readonly sha256: string;
  readonly license?: "Apache-2.0" | "Apache-2.0";
}

export function renderPluginSpdxSbom(
  input: Readonly<{
    plugin: z.infer<typeof packageMetadataSchema>;
    kit: z.infer<typeof packageMetadataSchema>;
    sourceTreeSha256: string;
    files: readonly SbomFile[];
    kitManifest: Readonly<{
      canonical: Readonly<{ resolvedRevision: string }>;
      projection: Readonly<{ generatedSha256: string }>;
    }>;
  }>,
): string {
  const files = [...input.files]
    .sort((left, right) => left.path.localeCompare(right.path))
    .map((file, index) => {
      const license = file.license ?? "Apache-2.0";
      return {
        SPDXID: `SPDXRef-File-${String(index + 1).padStart(4, "0")}`,
        fileName: `./${file.path}`,
        checksums: [{ algorithm: "SHA256", checksumValue: file.sha256 }],
        licenseConcluded: license,
        licenseInfoInFiles: [license],
        copyrightText: "NOASSERTION",
      };
    });
  const pluginSpdxId = "SPDXRef-Package-kunolu-omp-sbtd";
  const kitSpdxId = "SPDXRef-Package-kunolu-sbtd-workflow-kit";
  const relationships = files.map((file) => ({
    spdxElementId: pluginSpdxId,
    relationshipType: "CONTAINS",
    relatedSpdxElement: file.SPDXID,
  }));
  return stableJson({
    spdxVersion: "SPDX-2.3",
    dataLicense: "CC0-1.0",
    SPDXID: "SPDXRef-DOCUMENT",
    name: `${input.plugin.name}-${input.plugin.version}`,
    documentNamespace: `https://kpi.local/spdx/${input.sourceTreeSha256}`,
    creationInfo: {
      created: "1970-01-01T00:00:00Z",
      creators: ["Tool: kpi-p0-release-validator/1"],
    },
    documentDescribes: [pluginSpdxId],
    packages: [
      {
        SPDXID: pluginSpdxId,
        name: input.plugin.name,
        versionInfo: input.plugin.version,
        downloadLocation: "NOASSERTION",
        filesAnalyzed: true,
        licenseConcluded: "Apache-2.0",
        licenseDeclared: "Apache-2.0",
        copyrightText: "NOASSERTION",
      },
      {
        SPDXID: kitSpdxId,
        name: input.kit.name,
        versionInfo: input.kit.version,
        downloadLocation: "NOASSERTION",
        filesAnalyzed: false,
        licenseConcluded: "Apache-2.0",
        licenseDeclared: "Apache-2.0",
        copyrightText: "NOASSERTION",
        externalRefs: [
          {
            referenceCategory: "OTHER",
            referenceType: "kpi-upstream-revision",
            referenceLocator: input.kitManifest.canonical.resolvedRevision,
          },
          {
            referenceCategory: "OTHER",
            referenceType: "kpi-generated-sha256",
            referenceLocator: input.kitManifest.projection.generatedSha256,
          },
        ],
      },
    ],
    files,
    relationships: [
      ...relationships,
      {
        spdxElementId: pluginSpdxId,
        relationshipType: "CONTAINS",
        relatedSpdxElement: kitSpdxId,
      },
    ],
  });
}

export async function inventoryFiles(
  root: string,
  files: P0FileSystem = createNodeFileSystem(),
  prefix = "",
): Promise<readonly SbomFile[]> {
  const result: SbomFile[] = [];
  for (const entry of await files.list(root)) {
    const path = join(root, entry.name);
    const nextPrefix = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
    if (entry.kind === "symlink")
      throw new P0ValidationError(
        "PACKAGE_CONTENT_INVALID",
        `Package inventory rejects symbolic links: ${nextPrefix}`,
        "Replace the link with a checked-in regular file before packing.",
      );
    if (entry.kind === "directory") {
      result.push(...(await inventoryFiles(path, files, nextPrefix)));
      continue;
    }
    if (entry.kind !== "file") continue;
    result.push({
      path: nextPrefix,
      sha256: await digestFile(path, files),
    });
  }
  return result.sort((left, right) => left.path.localeCompare(right.path));
}

export async function inspectPackageMetadata(
  input: Readonly<{
    workspaceRoot: string;
    pluginRoot: string;
    kitRoot: string;
    files?: P0FileSystem;
  }>,
): Promise<
  Readonly<{
    plugin: z.infer<typeof packageMetadataSchema>;
    kit: z.infer<typeof packageMetadataSchema>;
  }>
> {
  const files = input.files ?? createNodeFileSystem();
  const [rootRaw, pluginRaw, kitRaw] = await Promise.all([
    files.readText(join(input.workspaceRoot, "package.json")),
    files.readText(join(input.pluginRoot, "package.json")),
    files.readText(join(input.kitRoot, "package.json")),
  ]);
  const root = parsedJson(
    rootPackageMetadataSchema,
    rootRaw,
    "root package metadata",
  );
  const plugin = parsedJson(
    packageMetadataSchema,
    pluginRaw,
    "Plugin package metadata",
  );
  const kit = parsedJson(packageMetadataSchema, kitRaw, "Kit package metadata");
  const requiredPluginFiles = [
    "dist",
    "kit",
    "plugin.json",
    "skills",
    "LICENSE",
    "SBOM.spdx.json",
    "THIRD_PARTY_NOTICES.md",
  ];
  const missingDeclarations = requiredPluginFiles.filter(
    (path) => !plugin.files?.includes(path),
  );
  if (missingDeclarations.length > 0)
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Plugin package metadata does not declare every required release artifact.",
      "Add the missing release artifacts to the Plugin package files allowlist.",
      { missingDeclarations },
    );
  if (root.license !== "Apache-2.0")
    throw new P0ValidationError(
      "LICENSE_MISMATCH",
      "Root package metadata must declare Apache-2.0.",
      "Align root, Plugin, and Kit license metadata before release validation.",
    );
  return { plugin, kit };
}

const publicEventSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("usage"),
      turns: z.number().int().min(0),
      tokens: z.number().int().min(0),
    })
    .strict(),
  z
    .object({
      kind: z.literal("report"),
      requiredGates: z.array(requiredGateSchema),
      // Absent only for an explicitly unclassified observation; a classified
      // route always carries its concrete cost.
      routeCost: routeCostSchema.optional(),
    })
    .strict(),
  z
    .object({
      kind: z.literal("terminal"),
      outcome: attemptOutcomeSchema,
      finalResponse: z
        .string()
        .min(1)
        .max(32 * 1024)
        .optional(),
    })
    .strict(),
]);
export type SanitizedOmpEvent = z.infer<typeof publicEventSchema>;

export type ValueStudyArm = z.infer<typeof valueStudyArmSchema>;

export interface OmpPreflightReady {
  readonly status: "ready";
  readonly runtimeVersion: string;
  readonly executionModelId: string;
  readonly judgeModelId: string;
  readonly executionProcessId: string;
  readonly judgeProcessId: string;
  readonly supportsUsageEvents: true;
}

export interface OmpPreflightBlocked {
  readonly status: "blocked";
  readonly supportsUsageEvents: false;
  readonly blocker: z.infer<typeof blockerSchema>;
}

export type OmpPreflightResult = OmpPreflightReady | OmpPreflightBlocked;

export interface OmpExecutionInput {
  readonly runId: string;
  readonly fixture: ValueStudyFixture;
  readonly fixtureSha256: string;
  readonly arm: ValueStudyArm;
  readonly mode: "advisory" | "enforced";
  readonly attempt: number;
  readonly workspacePath: string;
  readonly limits: Readonly<{
    wallClockMs: number;
    maxTurns: number;
    maxTokens: number;
  }>;
}

export interface OmpExecutionCompleted {
  readonly status: "completed";
  readonly runId: string;
  readonly fixtureId: string;
  readonly arm: ValueStudyArm;
  readonly attempt: number;
  readonly fixtureSha256: string;
  readonly executionProcessId: string;
  readonly events: readonly SanitizedOmpEvent[];
  readonly acceptanceArtifact: AcceptanceArtifact;
  readonly acceptanceArtifactSha256: string;
}

export interface OmpExecutionBlocked {
  readonly status: "blocked";
  readonly blocker: z.infer<typeof blockerSchema>;
}

export type OmpExecutionResult = OmpExecutionCompleted | OmpExecutionBlocked;

export interface BlindJudgeInput {
  readonly runId: string;
  readonly fixtureId: string;
  readonly fixtureSha256: string;
  readonly rubric: readonly z.infer<typeof rubricCriterionSchema>[];
  readonly first: Readonly<{
    artifact: AcceptanceArtifact;
    artifactSha256: string;
  }>;
  readonly second: Readonly<{
    artifact: AcceptanceArtifact;
    artifactSha256: string;
  }>;
}

export interface BlindJudgeCompleted {
  readonly status: "completed";
  readonly runId: string;
  readonly fixtureId: string;
  readonly fixtureSha256: string;
  readonly judgeProcessId: string;
  readonly firstArtifactSha256: string;
  readonly secondArtifactSha256: string;
  readonly first: z.infer<typeof judgeArmScoreSchema>;
  readonly second: z.infer<typeof judgeArmScoreSchema>;
  readonly judgeResultSha256: string;
}

export interface BlindJudgeBlocked {
  readonly status: "blocked";
  readonly blocker: z.infer<typeof blockerSchema>;
}

export type BlindJudgeResult = BlindJudgeCompleted | BlindJudgeBlocked;

export interface OmpRuntimeModeReady {
  readonly status: "ready";
}

export interface OmpRuntimeModeBlocked {
  readonly status: "blocked";
  readonly blocker: z.infer<typeof blockerSchema>;
}

export type OmpRuntimeModeResult = OmpRuntimeModeReady | OmpRuntimeModeBlocked;

export interface OmpProcessAdapter {
  readonly preflight: (
    input: Readonly<{
      executionModelId: string;
      judgeModelId: string;
      runtimeVersion: string;
    }>,
  ) => Promise<OmpPreflightResult>;
  readonly setRuntimeMode: (
    input: Readonly<{ fixtureId: string; mode: "advisory" | "enforced" }>,
  ) => Promise<OmpRuntimeModeResult>;
  readonly execute: (input: OmpExecutionInput) => Promise<OmpExecutionResult>;
  readonly judge: (input: BlindJudgeInput) => Promise<BlindJudgeResult>;
}

export function createUnavailableOmpProcessAdapter(
  recovery = "Authorize a public OMP process adapter with distinct execution and judge models, then rerun preflight.",
): OmpProcessAdapter {
  const blocker = {
    code: "OMP_VALUE_STUDY_PREREQUISITE_UNAVAILABLE",
    reason:
      "No authorized public OMP process adapter is available in this local run.",
    recovery,
  };
  return {
    preflight: async () => ({
      status: "blocked",
      supportsUsageEvents: false,
      blocker,
    }),
    setRuntimeMode: async () => ({ status: "blocked", blocker }),
    execute: async () => ({ status: "blocked", blocker }),
    judge: async () => ({ status: "blocked", blocker }),
  };
}

export async function preflightValueStudy(
  adapter: OmpProcessAdapter,
  input: Readonly<{
    executionModelId: string;
    judgeModelId: string;
    runtimeVersion: string;
  }>,
): Promise<OmpPreflightResult> {
  if (input.executionModelId === input.judgeModelId)
    return {
      status: "blocked",
      supportsUsageEvents: false,
      blocker: {
        code: "JUDGE_NOT_INDEPENDENT",
        reason:
          "The configured judge model must differ from the execution model.",
        recovery:
          "Choose a different fixed judge model before starting the 40 task arms.",
      },
    };
  const result = await adapter.preflight(input);
  if (result.status === "blocked") return result;
  if (
    !result.supportsUsageEvents ||
    result.runtimeVersion !== input.runtimeVersion ||
    result.executionModelId !== input.executionModelId ||
    result.judgeModelId !== input.judgeModelId ||
    result.executionProcessId === result.judgeProcessId
  )
    return {
      status: "blocked",
      supportsUsageEvents: false,
      blocker: {
        code: "OMP_EVENT_PRECONDITION_UNMET",
        reason:
          "The public OMP adapter cannot prove fixed identities, identical limits, and judge-process independence.",
        recovery:
          "Expose matching sanitized identity and usage-event facts from separate execution and judge processes.",
      },
    };
  return result;
}

export interface CompleteValueStudyInput {
  readonly runId: string;
  readonly sourceTreeSha256: string;
  readonly catalogSha256: string;
  readonly corpusSha256: string;
  readonly rubricSha256: string;
  readonly technicalStatus: z.infer<typeof statusSchema>;
  readonly corpus: ValueStudyCorpus;
  readonly fixtures: readonly ValueStudyFixture[];
  readonly execution: Readonly<{
    runtimeVersion: string;
    modelId: string;
  }>;
  readonly judge: Readonly<{ modelId: string }>;
}

export interface ValueStudyExecutionResult {
  readonly status: "passed" | "failed" | "blocked";
  readonly preflight: OmpPreflightResult;
  readonly run?: CanonicalEvidenceRun;
  readonly blocker?: z.infer<typeof blockerSchema>;
}

function blockedValueStudyExecution(
  preflight: OmpPreflightResult,
  code: string,
  reason: string,
  recovery: string,
): ValueStudyExecutionResult {
  return {
    status: "blocked",
    preflight,
    blocker: { code, reason, recovery },
  };
}

function summarizeExecution(
  execution: OmpExecutionCompleted,
  fixture: ValueStudyFixture,
): Readonly<{
  status: "completed" | "failed" | "blocked";
  outcome: z.infer<typeof attemptOutcomeSchema>;
  observedRequiredGates: readonly z.infer<typeof requiredGateSchema>[];
  actualRouteCost: z.infer<typeof routeCostSchema> | undefined;
  severeWorkflowOmissions: readonly string[];
  usage: Readonly<{ turns: number; tokenCount: number }>;
}> {
  const terminalEvents = execution.events.filter(
    (
      event,
    ): event is Extract<SanitizedOmpEvent, { readonly kind: "terminal" }> =>
      event.kind === "terminal",
  );
  const terminal = terminalEvents[0];
  const reportEvents = execution.events.filter(
    (event): event is Extract<SanitizedOmpEvent, { readonly kind: "report" }> =>
      event.kind === "report",
  );
  const report = reportEvents[0];
  const usageEvents = execution.events.filter(
    (event): event is Extract<SanitizedOmpEvent, { readonly kind: "usage" }> =>
      event.kind === "usage",
  );
  if (
    terminalEvents.length !== 1 ||
    terminal === undefined ||
    execution.events[execution.events.length - 1] !== terminal ||
    reportEvents.length !== 1 ||
    report === undefined ||
    usageEvents.length === 0
  )
    throw new P0ValidationError(
      "OMP_EXECUTION_RESPONSE_INVALID",
      "The execution response must contain one report and a final terminal event.",
      "Return the strict bounded execution event sequence from the authorized host.",
      { fixtureId: fixture.id },
    );
  let turns = 0;
  let tokenCount = 0;
  for (const event of execution.events) {
    if (event.kind !== "usage") continue;
    turns += event.turns;
    tokenCount += event.tokens;
  }
  let outcome = terminal.outcome;
  if (turns > VALUE_STUDY_LIMITS.maxTurns) outcome = "turn-limit";
  if (tokenCount > VALUE_STUDY_LIMITS.maxTokens) outcome = "token-limit";
  const observed = new Set(report.requiredGates);
  const severeWorkflowOmissions = fixture.expected.requiredGates.filter(
    (gate) => !observed.has(gate),
  );
  const status =
    outcome === "completed"
      ? "completed"
      : outcome === "model-quality" || outcome === "task-test-failure"
        ? "failed"
        : "blocked";
  return {
    status,
    outcome,
    observedRequiredGates: report.requiredGates,
    actualRouteCost: report.routeCost,
    severeWorkflowOmissions,
    usage: { turns, tokenCount },
  };
}

export async function runCompleteValueStudy(
  adapter: OmpProcessAdapter,
  store: EvidenceStore,
  input: CompleteValueStudyInput,
): Promise<ValueStudyExecutionResult> {
  let preflight: OmpPreflightResult = {
    status: "blocked",
    supportsUsageEvents: false,
    blocker: {
      code: "OMP_PREFLIGHT_FAILED",
      reason: "The value-study preflight did not return a bounded result.",
      recovery:
        "Correct the authorized host preflight and start a new complete study.",
    },
  };
  try {
    assertSanitizedValue(
      {
        runtimeVersion: input.execution.runtimeVersion,
        executionModelId: input.execution.modelId,
        judgeModelId: input.judge.modelId,
      },
      "value-study-identities",
    );
    preflight = await preflightValueStudy(adapter, {
      executionModelId: input.execution.modelId,
      judgeModelId: input.judge.modelId,
      runtimeVersion: input.execution.runtimeVersion,
    });
    assertSanitizedValue(preflight, "value-study-preflight");
    if (preflight.status === "blocked")
      return { status: "blocked", preflight, blocker: preflight.blocker };
    const parsedCorpus = valueStudyCorpusSchema.safeParse(input.corpus);
    if (!parsedCorpus.success)
      return blockedValueStudyExecution(
        preflight,
        "CORPUS_INVALID",
        "The controller received an invalid value-study corpus manifest.",
        "Reload the frozen versioned corpus before starting any arm.",
      );
    const corpus = parsedCorpus.data;
    const frozenFixtures = input.fixtures.map((fixture) =>
      validateValueStudyFixture(fixture),
    );
    const corpusIds = corpus.fixtures.map((fixture) => fixture.id);
    const fixtureById = new Map(
      frozenFixtures.map((fixture) => [fixture.id, fixture]),
    );
    const fixtureMismatch = corpus.fixtures.some((reference) => {
      const fixture = fixtureById.get(reference.id);
      return fixture === undefined || fixture.category !== reference.category;
    });
    const invalidCategories = VALUE_STUDY_CATEGORIES.filter(
      (category) =>
        corpus.fixtures.filter((fixture) => fixture.category === category)
          .length !== 2,
    );
    if (
      !runIdSchema.safeParse(input.runId).success ||
      ![
        input.sourceTreeSha256,
        input.catalogSha256,
        input.corpusSha256,
        input.rubricSha256,
      ].every((value) => hashSchema.safeParse(value).success) ||
      frozenFixtures.length !== 20 ||
      fixtureById.size !== 20 ||
      fixtureMismatch ||
      invalidCategories.length > 0
    )
      return blockedValueStudyExecution(
        preflight,
        "VALUE_FIXTURE_COMPLETENESS_INVALID",
        "The controller did not receive the exact 20 frozen fixture manifests and source bindings.",
        "Reload the versioned corpus and its immutable fixture files before execution.",
      );
    const schedule = deterministicValueStudySchedule(
      corpus.randomSeed,
      corpusIds,
    );
    const arms: Array<
      z.infer<typeof canonicalArmSchema> & {
        acceptanceArtifact: AcceptanceArtifact;
      }
    > = [];
    for (const scheduled of schedule.arms) {
      const fixture = fixtureById.get(scheduled.fixtureId);
      if (fixture === undefined)
        return blockedValueStudyExecution(
          preflight,
          "VALUE_FIXTURE_COMPLETENESS_INVALID",
          "A deterministic arm references an unavailable frozen fixture.",
          "Reload the complete frozen corpus before execution.",
        );
      const fixtureDigest = valueStudyFixtureSha256(fixture);
      const mode = scheduled.arm === "control" ? "advisory" : "enforced";
      const workspacePath = await store.materializeFixture(
        input.runId,
        fixture,
        scheduled.arm,
      );
      const attempts: z.infer<typeof armAttemptSchema>[] = [];
      let accepted:
        | (z.infer<typeof canonicalArmSchema> & {
            acceptanceArtifact: AcceptanceArtifact;
          })
        | undefined;
      for (let attempt = 1; attempt <= 2; attempt += 1) {
        const modeResult = await adapter.setRuntimeMode({
          fixtureId: fixture.id,
          mode,
        });
        if (modeResult.status === "blocked")
          return blockedValueStudyExecution(
            preflight,
            modeResult.blocker.code,
            modeResult.blocker.reason ??
              "The host blocked the requested runtime mode.",
            modeResult.blocker.recovery,
          );
        const execution = await adapter.execute({
          runId: input.runId,
          fixture,
          fixtureSha256: fixtureDigest,
          arm: scheduled.arm,
          mode,
          attempt,
          workspacePath,
          limits: VALUE_STUDY_LIMITS,
        });
        if (execution.status === "blocked")
          return blockedValueStudyExecution(
            preflight,
            execution.blocker.code,
            execution.blocker.reason ??
              "The host blocked execution before returning a bounded result.",
            execution.blocker.recovery,
          );
        if (
          execution.runId !== input.runId ||
          execution.fixtureId !== fixture.id ||
          execution.fixtureSha256 !== fixtureDigest ||
          execution.arm !== scheduled.arm ||
          execution.attempt !== attempt ||
          execution.executionProcessId !== preflight.executionProcessId ||
          acceptanceArtifactSha256(execution.acceptanceArtifact) !==
            execution.acceptanceArtifactSha256
        )
          return blockedValueStudyExecution(
            preflight,
            "EVIDENCE_LINEAGE_INVALID",
            "An execution response was not bound to the controller request and bounded acceptance artifact.",
            "Restart the complete study with a host that returns the strict execute response.",
          );
        const summary = summarizeExecution(execution, fixture);
        if (
          scheduled.arm === "treatment" &&
          summary.actualRouteCost === undefined
        )
          return blockedValueStudyExecution(
            preflight,
            "VALUE_ROUTE_UNCLASSIFIED",
            "The treatment execution did not report a classified route cost.",
            "Run the treatment with a named effective route and concrete cost in a new complete study.",
          );
        attempts.push({ attempt, outcome: summary.outcome });
        await store.writeRawRecord(
          input.runId,
          `arms/${fixture.id}-${scheduled.arm}-attempt-${attempt}.json`,
          {
            schemaVersion: 1,
            events: execution.events,
            acceptanceArtifact: execution.acceptanceArtifact,
            acceptanceArtifactSha256: execution.acceptanceArtifactSha256,
          },
        );
        const arm = {
          fixtureId: fixture.id,
          arm: scheduled.arm,
          position: scheduled.position,
          fixtureSha256: fixtureDigest,
          attempts: [...attempts],
          acceptedAttempt: attempt,
          status: summary.status,
          observedRequiredGates: summary.observedRequiredGates,
          actualRouteCost: summary.actualRouteCost,
          severeWorkflowOmissions: summary.severeWorkflowOmissions,
          limits: VALUE_STUDY_LIMITS,
          usage: summary.usage,
          acceptanceArtifactSha256: execution.acceptanceArtifactSha256,
          acceptanceArtifact: execution.acceptanceArtifact,
        };
        if (attempt === 1 && RETRYABLE_FAILURES.has(summary.outcome)) continue;
        accepted = arm;
        break;
      }
      if (accepted === undefined)
        return blockedValueStudyExecution(
          preflight,
          "RETRY_LINEAGE_INVALID",
          "A value-study arm exhausted its only eligible infrastructure retry.",
          "Correct the host failure and start a new complete study.",
        );
      arms.push(accepted);
    }
    const judgments: z.infer<typeof canonicalJudgmentSchema>[] = [];
    for (const scheduled of schedule.judgments) {
      const fixture = fixtureById.get(scheduled.fixtureId);
      const first = arms.find(
        (arm) =>
          arm.fixtureId === scheduled.fixtureId &&
          arm.arm === scheduled.firstArm,
      );
      const second = arms.find(
        (arm) =>
          arm.fixtureId === scheduled.fixtureId &&
          arm.arm === scheduled.secondArm,
      );
      if (fixture === undefined || first === undefined || second === undefined)
        return blockedValueStudyExecution(
          preflight,
          "VALUE_PAIR_INCOMPLETE",
          "A scheduled blind judgment has no pair of controller-produced arm artifacts.",
          "Complete both arms before sending any masked pair to the judge.",
        );
      const fixtureDigest = valueStudyFixtureSha256(fixture);
      const judgment = await adapter.judge({
        runId: input.runId,
        fixtureId: fixture.id,
        fixtureSha256: fixtureDigest,
        rubric: fixture.rubric,
        first: {
          artifact: first.acceptanceArtifact,
          artifactSha256: first.acceptanceArtifactSha256,
        },
        second: {
          artifact: second.acceptanceArtifact,
          artifactSha256: second.acceptanceArtifactSha256,
        },
      });
      if (judgment.status === "blocked")
        return blockedValueStudyExecution(
          preflight,
          judgment.blocker.code,
          judgment.blocker.reason ??
            "The independent judge did not return a bounded result.",
          judgment.blocker.recovery,
        );
      if (
        judgment.runId !== input.runId ||
        judgment.fixtureId !== fixture.id ||
        judgment.fixtureSha256 !== fixtureDigest ||
        judgment.judgeProcessId !== preflight.judgeProcessId ||
        judgment.firstArtifactSha256 !== first.acceptanceArtifactSha256 ||
        judgment.secondArtifactSha256 !== second.acceptanceArtifactSha256
      )
        return blockedValueStudyExecution(
          preflight,
          "EVIDENCE_LINEAGE_INVALID",
          "A blind judge response is not bound to the controller-produced masked artifact pair.",
          "Restart the complete study with a host that returns the strict judge response.",
        );
      assertJudgeScoreMatchesRubric(
        judgment.first,
        fixture.rubric,
        "judge first",
      );
      assertJudgeScoreMatchesRubric(
        judgment.second,
        fixture.rubric,
        "judge second",
      );
      const expectedJudgeDigest = blindJudgeResultSha256({
        fixtureId: judgment.fixtureId,
        firstArtifactSha256: judgment.firstArtifactSha256,
        secondArtifactSha256: judgment.secondArtifactSha256,
        first: judgment.first,
        second: judgment.second,
      });
      if (expectedJudgeDigest !== judgment.judgeResultSha256)
        return blockedValueStudyExecution(
          preflight,
          "EVIDENCE_LINEAGE_INVALID",
          "A blind judge digest does not match its returned masked score.",
          "Restart the complete study with a host that returns the strict judge digest.",
        );
      judgments.push({
        fixtureId: judgment.fixtureId,
        position: scheduled.position,
        firstArtifactSha256: judgment.firstArtifactSha256,
        secondArtifactSha256: judgment.secondArtifactSha256,
        first: judgment.first,
        second: judgment.second,
        judgeResultSha256: judgment.judgeResultSha256,
      });
    }
    const fixtures = corpusIds.map((fixtureId) => {
      const fixture = fixtureById.get(fixtureId);
      if (fixture === undefined) throw new Error("fixture binding missing");
      validateRubric(fixture.rubric, `fixture ${fixture.id}`);
      return {
        fixtureId: fixture.id,
        fixtureSha256: valueStudyFixtureSha256(fixture),
        expectedRequiredGates: fixture.expected.requiredGates,
        expectedRouteCost: fixture.expected.routeCost,
        rubric: fixture.rubric,
      };
    });
    const ledger = {
      schemaVersion: 1 as const,
      runId: input.runId,
      sourceTreeSha256: input.sourceTreeSha256,
      catalogSha256: input.catalogSha256,
      corpusSha256: input.corpusSha256,
      rubricSha256: input.rubricSha256,
      environment: {
        runtimeVersion: preflight.runtimeVersion,
        executionModelId: preflight.executionModelId,
        judgeModelId: preflight.judgeModelId,
        executionProcessId: preflight.executionProcessId,
        judgeProcessId: preflight.judgeProcessId,
      },
      randomizedOrder: schedule,
      fixtures,
      arms,
      judgments,
    };
    await store.writeRawRecord(
      input.runId,
      "controller-provenance.json",
      ledger,
    );
    const provenance = {
      controllerProvenanceSha256: digest(stableJson(ledger)),
      fixtures,
      arms: arms.map(({ acceptanceArtifact: _artifact, ...arm }) => arm),
      judgments,
    };
    const draftPairs = fixtures.map((fixture) => {
      const control = provenance.arms.find(
        (arm) => arm.fixtureId === fixture.fixtureId && arm.arm === "control",
      );
      const treatment = provenance.arms.find(
        (arm) => arm.fixtureId === fixture.fixtureId && arm.arm === "treatment",
      );
      const judgment = provenance.judgments.find(
        (entry) => entry.fixtureId === fixture.fixtureId,
      );
      const order = schedule.judgments.find(
        (entry) => entry.fixtureId === fixture.fixtureId,
      );
      if (
        control === undefined ||
        treatment === undefined ||
        judgment === undefined ||
        order === undefined
      )
        throw new P0ValidationError(
          "VALUE_PAIR_INCOMPLETE",
          "The controller cannot reconstruct a complete immutable pair.",
          "Restart the complete study from the frozen corpus.",
          { fixtureId: fixture.fixtureId },
        );
      const scoresByArm = {
        [order.firstArm]: judgment.first,
        [order.secondArm]: judgment.second,
      };
      return {
        fixtureId: fixture.fixtureId,
        expectedRequiredGates: fixture.expectedRequiredGates,
        expectedRouteCost: fixture.expectedRouteCost,
        control: scoringArm(control),
        treatment: scoringArm(treatment),
        judge: {
          control: scoresByArm.control,
          treatment: scoresByArm.treatment,
        },
      };
    });
    const score = scoreValueStudy({
      schemaVersion: 1,
      sourceTreeSha256: input.sourceTreeSha256,
      execution: {
        runtimeVersion: preflight.runtimeVersion,
        modelId: preflight.executionModelId,
        processId: preflight.executionProcessId,
      },
      judge: {
        modelId: preflight.judgeModelId,
        processId: preflight.judgeProcessId,
      },
      pairs: draftPairs,
    });
    const run: CanonicalEvidenceRun = {
      schemaVersion: 1,
      runId: input.runId,
      createdAt: new Date().toISOString(),
      sourceTreeSha256: input.sourceTreeSha256,
      catalogSha256: input.catalogSha256,
      corpusSha256: input.corpusSha256,
      rubricSha256: input.rubricSha256,
      environment: ledger.environment,
      randomizedOrder: schedule,
      technicalStatus: input.technicalStatus,
      valueGateStatus: score.status,
      releaseDecision:
        input.technicalStatus === "passed" && score.status === "passed"
          ? "ready"
          : "blocked",
      metrics: score.metrics,
      completionProvenance: provenance,
      blockers: [
        ...score.blockers,
        ...(input.technicalStatus === "passed"
          ? []
          : [
              {
                code: "TECHNICAL_CONFORMANCE_REQUIRED",
                reason:
                  "This value-study execution does not replace current technical conformance evidence.",
                recovery:
                  "Run and record the current technical conformance gate before a release decision.",
              },
            ]),
      ],
    };
    assertCanonicalEvidenceRun(run);
    return { status: score.status, preflight, run };
  } catch (error) {
    if (error instanceof P0ValidationError)
      return {
        status: "blocked",
        preflight,
        blocker: {
          code: error.code,
          reason: error.message,
          recovery: error.recovery,
        },
      };
    return blockedValueStudyExecution(
      preflight,
      "VALUE_STUDY_CONTROLLER_FAILED",
      "The local value-study controller could not create a complete sanitized provenance graph.",
      "Inspect the local temporary run and start a new study after correcting the deterministic controller failure.",
    );
  }
}

export function replayValueStudyScore(input: unknown): ValueStudyScoreReport {
  const run = assertCanonicalEvidenceRun(input);
  return {
    schemaVersion: 1,
    status: run.valueGateStatus,
    metrics: run.metrics,
    blockers: run.blockers,
  };
}

async function readReleaseKitFile(
  kitRoot: string,
  relativePath: string,
  files: P0FileSystem,
): Promise<Uint8Array> {
  let kind: P0DirectoryEntry["kind"];
  try {
    kind = await files.inspect(join(kitRoot, relativePath));
  } catch {
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      `Embedded Kit asset is unavailable: ${relativePath}`,
      "Rebuild the tarball from a complete generated OMP Distribution Projection.",
    );
  }
  if (kind !== "file")
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      `Embedded Kit asset is not a regular file: ${relativePath}`,
      "Rebuild the tarball with only regular embedded Kit assets.",
    );
  try {
    return files.readBytes === undefined
      ? new TextEncoder().encode(
          await files.readText(join(kitRoot, relativePath)),
        )
      : await files.readBytes(join(kitRoot, relativePath));
  } catch {
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      `Embedded Kit asset is unreadable: ${relativePath}`,
      "Rebuild the tarball from a complete generated OMP Distribution Projection.",
    );
  }
}

/**
 * Runs the Runtime loader's schema-v2/digest/provenance verifier against a
 * release root. Callers own their source-versus-packed inventory comparison;
 * this gate proves the candidate's own embedded projection is coherent.
 */
export async function verifyEmbeddedKitReleaseIntegrity(
  input: Readonly<{ kitRoot: string; files?: P0FileSystem }>,
): Promise<EmbeddedKitManifestV2> {
  const files = input.files ?? createNodeFileSystem();
  let rootKind: P0DirectoryEntry["kind"];
  try {
    rootKind = await files.inspect(input.kitRoot);
  } catch {
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Embedded Kit root is unavailable.",
      "Rebuild the tarball from a complete generated OMP Distribution Projection.",
    );
  }
  if (rootKind !== "directory")
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Embedded Kit root is not a regular directory.",
      "Rebuild the tarball with a regular embedded Kit directory.",
    );
  let manifestInput: unknown;
  try {
    manifestInput = JSON.parse(
      Buffer.from(
        await readReleaseKitFile(input.kitRoot, "manifest.json", files),
      ).toString("utf8"),
    );
  } catch (error) {
    if (error instanceof P0ValidationError) throw error;
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Embedded Kit manifest is not valid JSON.",
      "Regenerate the embedded OMP Distribution Projection manifest.",
    );
  }
  let manifest: EmbeddedKitManifestV2;
  try {
    manifest = (
      await verifyEmbeddedKitManifest(manifestInput, (path) =>
        readReleaseKitFile(input.kitRoot, path, files),
      )
    ).manifest;
  } catch {
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Embedded Kit does not satisfy the schema-v2 projection integrity contract.",
      "Regenerate the embedded OMP Distribution Projection and rebuild the tarball.",
    );
  }
  // The canonical runtime payload is the one asset permitted to retain the
  // legacy non-OMP Runtime identifier, so its digest binding is mandatory:
  // an omitted or malformed declaration fails closed even when every other
  // manifest binding is internally consistent.
  const canonicalRuntimeDigest =
    manifest.assets[kitManifestCanonicalRuntimeAsset];
  if (
    typeof canonicalRuntimeDigest !== "string" ||
    !/^[0-9a-f]{64}$/.test(canonicalRuntimeDigest)
  )
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Embedded Kit manifest does not bind the canonical Onboard runtime asset digest.",
      "Regenerate the embedded OMP Distribution Projection and rebuild the tarball.",
    );
  return manifest;
}

function isVendoredOnboardFile(path: string): boolean {
  return path.startsWith("kit/onboard/runtime/");
}

export type PluginReleaseRoot = "source-package" | "staged-promotion";

async function inventoryDeclaredPackageContent(
  pluginRoot: string,
  files: P0FileSystem,
  releaseRoot: PluginReleaseRoot,
): Promise<readonly SbomFile[]> {
  const declaredPaths = [
    "dist",
    "kit",
    "plugin.json",
    "skills",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
  ];
  const inventory: SbomFile[] = [];
  for (const declaredPath of declaredPaths) {
    const path = join(pluginRoot, declaredPath);
    let kind: P0DirectoryEntry["kind"];
    try {
      kind = await files.inspect(path);
    } catch {
      throw new P0ValidationError(
        "PACKAGE_CONTENT_INVALID",
        `Required release artifact is missing: ${declaredPath}`,
        "Build the Plugin from a generated Kit before producing or checking its SPDX SBOM.",
      );
    }
    if (kind === "directory") {
      if (declaredPath === "dist" && releaseRoot === "source-package")
        await assertCompiledArtifactsMatchSources(pluginRoot, files);
      inventory.push(...(await inventoryFiles(path, files, declaredPath)));
      continue;
    }
    if (kind !== "file")
      throw new P0ValidationError(
        "PACKAGE_CONTENT_INVALID",
        `Required release artifact is not a regular file: ${declaredPath}`,
        "Replace the non-regular release artifact and rebuild the package.",
      );
    inventory.push({
      path: declaredPath,
      sha256: await digestFile(path, files),
      license: declaredPath.startsWith("kit/third-party/")
        ? "Apache-2.0"
        : "Apache-2.0",
    });
  }
  return inventory
    .map((file) => ({
      ...file,
      license:
        isVendoredOnboardFile(file.path) || file.path.startsWith("skills/")
          ? ("Apache-2.0" as const)
          : ("Apache-2.0" as const),
    }))
    .sort((left, right) => left.path.localeCompare(right.path));
}

export async function writePluginSpdxSbom(
  input: Readonly<{
    workspaceRoot: string;
    pluginRoot: string;
    kitRoot: string;
    releaseRoot?: PluginReleaseRoot;
    files?: P0FileSystem;
  }>,
): Promise<Readonly<{ sourceTreeSha256: string; sbomSha256: string }>> {
  const files = input.files ?? createNodeFileSystem();
  const metadata = await inspectPackageMetadata({ ...input, files });
  const kitManifest = await verifyEmbeddedKitReleaseIntegrity({
    kitRoot: join(input.pluginRoot, "kit"),
    files,
  });
  const inventory = await inventoryDeclaredPackageContent(
    input.pluginRoot,
    files,
    input.releaseRoot ?? "source-package",
  );
  const sourceTreeSha256 = digest(
    stableJson({
      plugin: { name: metadata.plugin.name, version: metadata.plugin.version },
      kit: {
        name: metadata.kit.name,
        version: metadata.kit.version,
        generatedSha256: kitManifest.projection.generatedSha256,
      },
      files: inventory,
    }),
  );
  const sbom = renderPluginSpdxSbom({
    plugin: metadata.plugin,
    kit: metadata.kit,
    sourceTreeSha256,
    files: inventory,
    kitManifest,
  });
  await files.writeText(join(input.pluginRoot, "SBOM.spdx.json"), sbom);
  return { sourceTreeSha256, sbomSha256: digest(sbom) };
}

export interface PackedPackageFile {
  readonly path: string;
  readonly sha256: string;
  readonly executable: boolean;
}

export function verifyPackedPackageContents(
  expected: readonly SbomFile[],
  packedFiles: readonly PackedPackageFile[],
  expectedSbomSha256: string,
): void {
  const expectedByPath = new Map<string, string | undefined>([
    ...expected.map((file) => [file.path, file.sha256] as const),
    ["SBOM.spdx.json", expectedSbomSha256],
    ["package.json", undefined],
  ]);
  const packedByPath = new Map(
    packedFiles.map((file) => [
      file.path.replace(/^package\//, ""),
      { sha256: file.sha256, executable: file.executable },
    ]),
  );
  const missing = [...expectedByPath.keys()].filter(
    (path) => !packedByPath.has(path),
  );
  const checksumDrift = [...expectedByPath.entries()]
    .filter(
      ([path, sha256]) =>
        sha256 !== undefined && packedByPath.get(path)?.sha256 !== sha256,
    )
    .map(([path]) => path);
  const unexpectedFiles = [...packedByPath.keys()].filter(
    (path) => !expectedByPath.has(path),
  );
  const unexpectedExecutables = [...packedByPath.entries()]
    .filter(
      ([path, file]) =>
        file.executable && !path.startsWith("dist/") && path !== "LICENSE",
    )
    .map(([path]) => path);
  if (
    missing.length > 0 ||
    checksumDrift.length > 0 ||
    unexpectedFiles.length > 0 ||
    unexpectedExecutables.length > 0
  )
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Packed Plugin contents differ from the immutable release inventory.",
      "Rebuild the tarball, regenerate the SPDX SBOM, and remove unexpected executable content.",
      { missing, checksumDrift, unexpectedFiles, unexpectedExecutables },
    );
}

export const OMP_DISTRIBUTION_FORBIDDEN_TOKEN = "codex";
const canonicalOnboardRuntimeRelativePath =
  "kit/onboard/runtime/scripts/onboard.py";
const packedCanonicalOnboardRuntimePath = `package/${canonicalOnboardRuntimeRelativePath}`;
const embeddedKitManifestRelativePath = "kit/manifest.json";
const packedEmbeddedKitManifestPath = `package/${embeddedKitManifestRelativePath}`;
const kitManifestCanonicalRuntimeAsset = "onboard/runtime/scripts/onboard.py";
// M2 portable capability layer: the root skills/** tree is the
// digest-verified copy of the M1-certified Agent Plugin projection. Its
// payloads are audit-certified rather than OMP-distribution-clean, so the
// forbidden-token gate scans its member names but exempts its payloads.
const portableSkillsRootDirectory = "skills";
const packedPortableSkillsPrefix = `package/${portableSkillsRootDirectory}/`;

function isCanonicalOnboardRuntime(path: string): boolean {
  return (
    path === canonicalOnboardRuntimeRelativePath ||
    path === packedCanonicalOnboardRuntimePath
  );
}

/**
 * Reads the embedded Kit manifest's approved digest for the canonical
 * Onboard runtime asset. The leakage exemption below is content-bound: only
 * bytes matching this exact digest may retain the legacy identifier. Any
 * unreadable, malformed, or unbound manifest yields no approved digest, so
 * the canonical path payload is then scanned like any other file.
 */
function approvedCanonicalRuntimeDigest(
  manifestBytes: Uint8Array | undefined,
): string | undefined {
  if (manifestBytes === undefined) return undefined;
  try {
    const manifest: unknown = JSON.parse(
      Buffer.from(manifestBytes).toString("utf8"),
    );
    if (
      typeof manifest !== "object" ||
      manifest === null ||
      !("assets" in manifest)
    )
      return undefined;
    const assets = manifest.assets;
    if (
      typeof assets !== "object" ||
      assets === null ||
      !(kitManifestCanonicalRuntimeAsset in assets)
    )
      return undefined;
    const declared = assets[kitManifestCanonicalRuntimeAsset];
    if (typeof declared !== "string" || !/^[0-9a-f]{64}$/.test(declared))
      return undefined;
    return declared;
  } catch {
    return undefined;
  }
}

async function readOptionalEmbeddedKitManifest(
  root: string,
  files: P0FileSystem,
): Promise<Uint8Array | undefined> {
  const manifestPath = join(root, embeddedKitManifestRelativePath);
  try {
    if ((await files.inspect(manifestPath)) !== "file") return undefined;
    return files.readBytes === undefined
      ? new TextEncoder().encode(await files.readText(manifestPath))
      : await files.readBytes(manifestPath);
  } catch {
    return undefined;
  }
}

export interface OmpDistributionLeak {
  readonly path: string;
  readonly pathMatches: number;
  readonly payloadMatches: number;
}

function countTokenOccurrencesInText(text: string, token: string): number {
  const haystack = text.toLowerCase();
  let matches = 0;
  let index = 0;
  while (index <= haystack.length - token.length) {
    const found = haystack.indexOf(token, index);
    if (found === -1) break;
    matches += 1;
    index = found + 1;
  }
  return matches;
}

export function countCaseInsensitiveTokenOccurrences(
  haystack: Uint8Array,
  token: string = OMP_DISTRIBUTION_FORBIDDEN_TOKEN,
): number {
  const needle = [...token.toLowerCase()].map((character) =>
    character.charCodeAt(0),
  );
  if (needle.some((code) => code < 0x61 || code > 0x7a))
    throw new Error("forbidden token must be lowercase ASCII letters");
  let matches = 0;
  const last = haystack.length - needle.length;
  for (let index = 0; index <= last; index += 1) {
    let position = 0;
    while (
      position < needle.length &&
      (haystack[index + position] | 0x20) === needle[position]
    )
      position += 1;
    if (position === needle.length) matches += 1;
  }
  return matches;
}

async function scanOmpDistributionEntry(
  root: string,
  relativePath: string,
  files: P0FileSystem,
  leaks: OmpDistributionLeak[],
  approvedRuntimeDigest: string | undefined,
  portableSkillsLayer: boolean,
): Promise<void> {
  const absolutePath = relativePath === "" ? root : join(root, relativePath);
  for (const entry of await files.list(absolutePath)) {
    const entryRelative =
      relativePath === "" ? entry.name : `${relativePath}/${entry.name}`;
    const entryAbsolute = join(absolutePath, entry.name);
    const pathMatches = countTokenOccurrencesInText(
      entryRelative,
      OMP_DISTRIBUTION_FORBIDDEN_TOKEN,
    );
    if (entry.kind === "symlink" || entry.kind === "other")
      throw new P0ValidationError(
        "PACKAGE_CONTENT_INVALID",
        `Packed Plugin contains a non-regular entry: ${entryRelative}`,
        "Package only regular files and directories.",
      );
    // The root skills/** tree is the M1-certified portable capability layer:
    // its payloads are audit-certified and digest-verified at the M2 pack
    // gates, so the OMP-distribution token gate scans its member names but
    // exempts its payloads, exactly like the audit exempts portable Skills
    // from OMP-only wording rules.
    const entryPortableLayer =
      portableSkillsLayer ||
      (entry.kind === "directory" &&
        entryRelative === portableSkillsRootDirectory);
    if (entry.kind === "directory") {
      if (pathMatches > 0)
        leaks.push({ path: entryRelative, pathMatches, payloadMatches: 0 });
      await scanOmpDistributionEntry(
        root,
        entryRelative,
        files,
        leaks,
        approvedRuntimeDigest,
        entryPortableLayer,
      );
      continue;
    }
    const payload =
      files.readBytes !== undefined
        ? await files.readBytes(entryAbsolute)
        : new TextEncoder().encode(await files.readText(entryAbsolute));
    const exemptApprovedCanonicalRuntime =
      approvedRuntimeDigest !== undefined &&
      isCanonicalOnboardRuntime(entryRelative) &&
      digest(payload) === approvedRuntimeDigest;
    const payloadMatches =
      exemptApprovedCanonicalRuntime || entryPortableLayer
        ? 0
        : countCaseInsensitiveTokenOccurrences(payload);
    if (pathMatches > 0 || payloadMatches > 0)
      leaks.push({ path: entryRelative, pathMatches, payloadMatches });
  }
}

export async function scanOmpDistributionLeaks(
  root: string,
  options?: { readonly files?: P0FileSystem },
): Promise<readonly OmpDistributionLeak[]> {
  const files = options?.files ?? createNodeFileSystem();
  const approvedRuntimeDigest = approvedCanonicalRuntimeDigest(
    await readOptionalEmbeddedKitManifest(root, files),
  );
  const leaks: OmpDistributionLeak[] = [];
  await scanOmpDistributionEntry(
    root,
    "",
    files,
    leaks,
    approvedRuntimeDigest,
    false,
  );
  return leaks.sort((left, right) => left.path.localeCompare(right.path));
}

export function assertOmpDistributionClean(
  leaks: readonly OmpDistributionLeak[],
): void {
  if (leaks.length === 0) return;
  throw new P0ValidationError(
    "OMP_DISTRIBUTION_LEAKAGE",
    "Packed Plugin contains forbidden non-OMP Runtime identifiers.",
    "Regenerate the OMP Distribution Projection from the canonical Kit and rebuild the tarball before retrying.",
    {
      forbiddenToken: OMP_DISTRIBUTION_FORBIDDEN_TOKEN,
      violations: leaks,
    },
  );
}

export interface PackedTarballMember {
  readonly path: string;
  readonly kind: "file" | "directory";
  readonly executable: boolean;
  readonly sha256: string | undefined;
}

export interface PackedPluginTarballInspection {
  readonly members: readonly PackedTarballMember[];
  readonly leaks: readonly OmpDistributionLeak[];
}

const TAR_BLOCK_SIZE = 512;
const PACKED_MEMBER_SEGMENT_PATTERN = /^[A-Za-z0-9._@+-]+$/;

function candidateTarballInvalid(
  message: string,
  details: Readonly<Record<string, unknown>> = {},
): P0ValidationError {
  return new P0ValidationError(
    "CANDIDATE_TARBALL_INVALID",
    message,
    "Create a regular packed Plugin tarball with only safe package paths and retry.",
    details,
  );
}

function parseTarOctal(field: Uint8Array, context: string): number {
  if ((field[0] ?? 0) & 0x80)
    throw candidateTarballInvalid(
      "Candidate tarball uses an unsupported binary numeric field.",
      { context },
    );
  let digits = "";
  for (const byte of field) {
    if (byte === 0 || byte === 0x20) {
      if (digits === "") continue;
      break;
    }
    if (byte < 0x30 || byte > 0x37)
      throw candidateTarballInvalid(
        "Candidate tarball contains a malformed numeric field.",
        { context },
      );
    digits += String.fromCharCode(byte);
  }
  if (digits === "")
    throw candidateTarballInvalid(
      "Candidate tarball contains a malformed numeric field.",
      { context },
    );
  return Number.parseInt(digits, 8);
}

function tarFieldText(field: Uint8Array): string {
  const zero = field.indexOf(0);
  return Buffer.from(zero === -1 ? field : field.subarray(0, zero)).toString(
    "utf8",
  );
}

function normalizeTarballMemberName(rawName: string): string {
  if (
    rawName === "" ||
    rawName.includes("\0") ||
    rawName.includes("\\") ||
    rawName.startsWith("/") ||
    /^[A-Za-z]:/.test(rawName)
  )
    throw candidateTarballInvalid(
      "Candidate tarball contains an unsafe member path.",
      { reason: "unsafe-path", member: rawName },
    );
  const stripped = rawName.endsWith("/") ? rawName.slice(0, -1) : rawName;
  const segments = stripped.split("/");
  if (
    segments.some(
      (segment) =>
        segment === "" ||
        segment === "." ||
        segment === ".." ||
        !PACKED_MEMBER_SEGMENT_PATTERN.test(segment),
    )
  )
    throw candidateTarballInvalid(
      "Candidate tarball contains an unsafe member path.",
      { reason: "unsafe-path", member: rawName },
    );
  return stripped;
}

function parsePaxExtendedPath(payload: Uint8Array): string | undefined {
  const text = Buffer.from(payload).toString("utf8");
  let offset = 0;
  let path: string | undefined;
  while (offset < text.length) {
    const space = text.indexOf(" ", offset);
    if (space === -1)
      throw candidateTarballInvalid(
        "Candidate tarball contains a malformed extended header.",
      );
    const length = Number(text.slice(offset, space));
    if (
      !Number.isInteger(length) ||
      String(length) !== text.slice(offset, space) ||
      length < 3 ||
      offset + length > text.length ||
      text[offset + length - 1] !== "\n"
    )
      throw candidateTarballInvalid(
        "Candidate tarball contains a malformed extended header.",
      );
    const record = text.slice(space + 1, offset + length - 1);
    const equals = record.indexOf("=");
    if (equals > 0 && record.slice(0, equals) === "path")
      path = record.slice(equals + 1);
    offset += length;
  }
  return path;
}

/**
 * Parses one packed Plugin `.tgz` into a structural member inventory without
 * trusting extraction semantics. Every member name is validated, duplicate or
 * ambiguous names are rejected, non-regular members are refused, and every raw
 * regular payload is scanned for the forbidden non-OMP Runtime token. The
 * canonical Onboard runtime member is exempt from the payload scan only when
 * its bytes exactly match the digest the embedded Kit manifest declares for
 * it. The result exposes only relative paths, counts, and digests - never
 * payloads.
 */
export function inspectPackedPluginTarball(
  bytes: Uint8Array,
): PackedPluginTarballInspection {
  let archive: Buffer;
  try {
    archive = gunzipSync(bytes);
  } catch {
    throw candidateTarballInvalid(
      "Candidate tarball is not a readable gzip archive.",
    );
  }
  const members: PackedTarballMember[] = [];
  const leaks: OmpDistributionLeak[] = [];
  const seen = new Set<string>();
  let kitManifestPayload: Buffer | undefined;
  let canonicalRuntimePayload: Buffer | undefined;
  let pendingName: string | undefined;
  let offset = 0;
  while (true) {
    if (offset + TAR_BLOCK_SIZE > archive.length)
      throw candidateTarballInvalid("Candidate tarball is truncated.");
    const header = archive.subarray(offset, offset + TAR_BLOCK_SIZE);
    offset += TAR_BLOCK_SIZE;
    if (header.every((byte) => byte === 0)) break;
    const storedChecksum = parseTarOctal(header.subarray(148, 156), "checksum");
    let computedChecksum = 0;
    for (let index = 0; index < TAR_BLOCK_SIZE; index += 1)
      computedChecksum +=
        index >= 148 && index < 156 ? 0x20 : (header[index] ?? 0);
    if (computedChecksum !== storedChecksum)
      throw candidateTarballInvalid(
        "Candidate tarball member checksum does not match.",
      );
    const typeflag = String.fromCharCode(header[156] ?? 0);
    const size = parseTarOctal(header.subarray(124, 136), "size");
    if (offset + size > archive.length)
      throw candidateTarballInvalid("Candidate tarball is truncated.");
    const payload = archive.subarray(offset, offset + size);
    offset += Math.ceil(size / TAR_BLOCK_SIZE) * TAR_BLOCK_SIZE;

    if (typeflag === "x") {
      const extendedPath = parsePaxExtendedPath(payload);
      if (extendedPath !== undefined) pendingName = extendedPath;
      continue;
    }
    if (typeflag === "L") {
      pendingName = Buffer.from(payload).toString("utf8").replace(/\0+$/, "");
      continue;
    }
    if (typeflag !== "0" && typeflag !== "\0" && typeflag !== "5")
      throw candidateTarballInvalid(
        "Candidate tarball contains a non-regular member.",
        { reason: "unsupported-member-type", typeflag: header[156] ?? 0 },
      );

    let rawName = pendingName;
    pendingName = undefined;
    if (rawName === undefined) {
      const magic = tarFieldText(header.subarray(257, 263));
      const prefix =
        magic === "ustar" ? tarFieldText(header.subarray(345, 500)) : "";
      const name = tarFieldText(header.subarray(0, 100));
      rawName = prefix === "" ? name : `${prefix}/${name}`;
    }
    const name = normalizeTarballMemberName(rawName);
    // AppleDouble companions (`._*`) are macOS metadata entries: bsdtar hides
    // them on listing and merges them as extended attributes on extraction,
    // and node-tar/npm pack never materializes them. They stay out of the
    // package member inventory, but their raw regular payload is still
    // scanned before being ignored so no control-plane archive byte bypasses
    // the token gate.
    const basename = name.slice(name.lastIndexOf("/") + 1);
    const isDirectory = typeflag === "5";
    const pathMatches = countTokenOccurrencesInText(
      name,
      OMP_DISTRIBUTION_FORBIDDEN_TOKEN,
    );
    const payloadMatches =
      isDirectory ||
      isCanonicalOnboardRuntime(name) ||
      name.startsWith(packedPortableSkillsPrefix)
        ? 0
        : countCaseInsensitiveTokenOccurrences(payload);
    if (seen.has(name))
      throw candidateTarballInvalid(
        "Candidate tarball contains duplicate or ambiguous members.",
        { reason: "duplicate-member", member: name },
      );
    seen.add(name);
    if (basename.startsWith("._")) {
      if (pathMatches > 0 || payloadMatches > 0)
        leaks.push({ path: name, pathMatches, payloadMatches });
      continue;
    }
    if (name !== "package" && !name.startsWith("package/"))
      throw candidateTarballInvalid(
        "Candidate tarball members must stay below the package root.",
        { reason: "unsafe-path", member: rawName },
      );

    if (!isDirectory) {
      // Retain the raw manifest and canonical runtime payloads so the leak
      // exemption can be bound to the manifest's declared digest after every
      // member is parsed, independent of member order.
      if (name === packedEmbeddedKitManifestPath) kitManifestPayload = payload;
      else if (name === packedCanonicalOnboardRuntimePath)
        canonicalRuntimePayload = payload;
    }

    const mode = parseTarOctal(header.subarray(100, 108), "mode");
    const sha256 = isDirectory ? undefined : digest(payload);
    if (pathMatches > 0 || payloadMatches > 0)
      leaks.push({ path: name, pathMatches, payloadMatches });
    members.push({
      path: name,
      kind: isDirectory ? "directory" : "file",
      executable: !isDirectory && (mode & 0o111) !== 0,
      sha256,
    });
  }
  for (let index = offset; index < archive.length; index += 1)
    if (archive[index] !== 0)
      throw candidateTarballInvalid(
        "Candidate tarball contains trailing data after the archive end.",
      );
  // The canonical runtime member keeps its exemption only while its bytes
  // exactly match the digest the embedded Kit manifest declares; a missing,
  // unbound, or drifted payload is scanned like any other member.
  const approvedRuntimeDigest =
    approvedCanonicalRuntimeDigest(kitManifestPayload);
  if (
    canonicalRuntimePayload !== undefined &&
    (approvedRuntimeDigest === undefined ||
      digest(canonicalRuntimePayload) !== approvedRuntimeDigest)
  ) {
    const payloadMatches = countCaseInsensitiveTokenOccurrences(
      canonicalRuntimePayload,
    );
    if (payloadMatches > 0)
      leaks.push({
        path: packedCanonicalOnboardRuntimePath,
        pathMatches: 0,
        payloadMatches,
      });
  }
  return {
    members,
    leaks: leaks.sort((left, right) => left.path.localeCompare(right.path)),
  };
}

const COMPILED_ARTIFACT_SUFFIXES = [
  ".js.map",
  ".d.ts.map",
  ".js",
  ".d.ts",
] as const;

/**
 * Fail-closed dist hygiene: every compiled artifact must be traceable to a
 * current TypeScript source file. Stale residue from deleted sources (for
 * example a removed bridge module) can otherwise survive an incremental
 * compiler run and enter a self-consistent SBOM and tarball.
 */
export async function assertCompiledArtifactsMatchSources(
  pluginRoot: string,
  files: P0FileSystem = createNodeFileSystem(),
): Promise<void> {
  const artifacts = await inventoryFiles(join(pluginRoot, "dist"), files);
  const staleArtifacts: string[] = [];
  for (const artifact of artifacts) {
    const suffix = COMPILED_ARTIFACT_SUFFIXES.find((candidate) =>
      artifact.path.endsWith(candidate),
    );
    const source =
      suffix === undefined
        ? undefined
        : `${artifact.path.slice(0, -suffix.length)}.ts`;
    let sourceKind: P0DirectoryEntry["kind"] | undefined;
    if (source !== undefined) {
      try {
        sourceKind = await files.inspect(join(pluginRoot, "src", source));
      } catch {
        sourceKind = undefined;
      }
    }
    if (source === undefined || sourceKind !== "file")
      staleArtifacts.push(`dist/${artifact.path}`);
  }
  if (staleArtifacts.length > 0)
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Packed Plugin dist contains compiled artifacts with no current TypeScript source.",
      "Clean the dist directory and rebuild so every packed artifact is compiled from current sources.",
      { staleArtifacts: staleArtifacts.sort() },
    );
}

export async function verifyPluginReleaseArtifacts(
  input: Readonly<{
    workspaceRoot: string;
    pluginRoot: string;
    kitRoot: string;
    files?: P0FileSystem;
  }>,
): Promise<Readonly<{ sourceTreeSha256: string; sbomSha256: string }>> {
  const files = input.files ?? createNodeFileSystem();
  const metadata = await inspectPackageMetadata({ ...input, files });
  const [rootLicense, pluginLicense, kitLicense, notices, committedSbom] =
    await Promise.all([
      files.readText(join(input.workspaceRoot, "LICENSE")),
      files.readText(join(input.pluginRoot, "LICENSE")),
      files.readText(join(input.kitRoot, "LICENSE")),
      files.readText(join(input.pluginRoot, "THIRD_PARTY_NOTICES.md")),
      files.readText(join(input.pluginRoot, "SBOM.spdx.json")),
    ]);
  if (pluginLicense !== rootLicense || kitLicense !== rootLicense)
    throw new P0ValidationError(
      "LICENSE_MISMATCH",
      "Root, Plugin, and Kit Apache-2.0 license files must be byte-identical.",
      "Regenerate package license artifacts from the repository root license.",
    );
  if (
    !notices.includes("kit/onboard/runtime/LICENSE") ||
    !notices.includes("kit/onboard/runtime/NOTICE")
  )
    throw new P0ValidationError(
      "NOTICE_MISMATCH",
      "Third-party notices do not retain the upstream Onboard attribution paths.",
      "Regenerate notices from the immutable generated Kit provenance.",
    );
  const kitManifest = await verifyEmbeddedKitReleaseIntegrity({
    kitRoot: join(input.pluginRoot, "kit"),
    files,
  });
  const inventory = await inventoryDeclaredPackageContent(
    input.pluginRoot,
    files,
    "source-package",
  );
  const sourceTreeSha256 = digest(
    stableJson({
      plugin: { name: metadata.plugin.name, version: metadata.plugin.version },
      kit: {
        name: metadata.kit.name,
        version: metadata.kit.version,
        generatedSha256: kitManifest.projection.generatedSha256,
      },
      files: inventory,
    }),
  );
  const regenerated = renderPluginSpdxSbom({
    plugin: metadata.plugin,
    kit: metadata.kit,
    sourceTreeSha256,
    files: inventory,
    kitManifest,
  });
  if (committedSbom !== regenerated)
    throw new P0ValidationError(
      "SBOM_MISMATCH",
      "The committed Plugin SPDX SBOM is not byte-identical to the current release inventory.",
      "Regenerate SBOM.spdx.json after building and embedding the exact Kit.",
    );
  return { sourceTreeSha256, sbomSha256: digest(regenerated) };
}

export function verifyPackedPackageMetadata(
  source: unknown,
  packed: unknown,
  workspaceDependencyManifests: Readonly<Record<string, unknown>>,
): void {
  const sourceContract = packageReleaseContractSchema.safeParse(source);
  const packedContract = packageReleaseContractSchema.safeParse(packed);
  const sourceManifest = packageManifestSchema.safeParse(source);
  const packedManifest = packageManifestSchema.safeParse(packed);
  const parsedWorkspaceDependencyManifests = z
    .record(z.string(), z.unknown())
    .safeParse(workspaceDependencyManifests);
  if (
    !sourceContract.success ||
    !packedContract.success ||
    !sourceManifest.success ||
    !packedManifest.success ||
    !parsedWorkspaceDependencyManifests.success
  )
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Packed Plugin metadata does not satisfy the release contract.",
      "Restore the required Plugin identity, entrypoints, dependencies, and OMP extension declarations.",
    );
  const sourceDevDependencies = z
    .record(z.string(), z.string())
    .safeParse(sourceManifest.data.devDependencies ?? {});
  if (!sourceDevDependencies.success)
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Plugin development dependencies are not a valid package manifest map.",
      "Restore the source package development dependency declarations.",
    );
  const normalizedSourceManifest = {
    ...sourceManifest.data,
    devDependencies: Object.fromEntries(
      Object.entries(sourceDevDependencies.data).map(([name, version]) => {
        if (version !== "workspace:*") return [name, version];
        const workspacePackage = workspacePackageManifestSchema.safeParse(
          parsedWorkspaceDependencyManifests.data[name],
        );
        if (!workspacePackage.success || workspacePackage.data.name !== name)
          throw new P0ValidationError(
            "PACKAGE_CONTENT_INVALID",
            "Plugin workspace development dependency cannot be resolved.",
            "Restore the referenced workspace package manifest and version.",
          );
        return [name, workspacePackage.data.version];
      }),
    ),
  };
  if (stableJson(normalizedSourceManifest) !== stableJson(packedManifest.data))
    throw new P0ValidationError(
      "PACKAGE_CONTENT_INVALID",
      "Packed Plugin metadata differs from the release contract.",
      "Restore the packed Plugin identity, entrypoints, dependencies, and OMP extension declarations.",
    );
}
