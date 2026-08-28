// Slice 6 CLI for the compatibility target/ledger/trust data and the
// minimum/latest/new-Runtime certification matrix report.
//
// Commands:
//   validate   Parse the targets/trust-policy documents and fully validate
//              the append-only ledger (schema, RFC 8785 digests, successor
//              chain, trusted provenance, subject binding, derived outcome).
//   report     Plan minimum/latest/new-Runtime cells for the published
//              targets and print the run report. Without --live-harness true
//              every runnable cell reports blocked; this command NEVER
//              reports passed or certified — those states exist only as
//              ledger-derived outcomes of trusted CI runs.
//
// This command never packs, publishes, or moves dist-tags.
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createRepoEvidenceReader,
  deriveSupportMatrix,
  parseCompatibilityTargets,
  parseCompatibilityTrustPolicy,
  planCompatibilityMatrixRun,
  reportCompatibilityMatrixRun,
  verifyCompatibilityLedgerEvidence,
} from "./compatibility-ledger.ts";
import { P0ValidationError } from "./release-validator.ts";

const pluginRoot = fileURLToPath(new URL("../..", import.meta.url));
const defaultDataRoot = join(pluginRoot, "validation", "p0");
const commands = new Set(["validate", "report"]);

function parseArguments(argv: readonly string[]): {
  readonly command: string;
  readonly options: Readonly<Record<string, string>>;
} {
  const [command, ...rest] = argv;
  const options: Record<string, string> = {};
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index];
    if (token === undefined || !token.startsWith("--"))
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Unexpected compatibility matrix argument: ${token}`,
        "Use only documented --name value options.",
      );
    const value = rest[index + 1];
    if (value === undefined || value.startsWith("--"))
      throw new P0ValidationError(
        "CLI_ARGUMENT_INVALID",
        `Missing value for ${token}`,
        "Supply a value for every compatibility matrix option.",
      );
    options[token.slice(2)] = value;
    index += 1;
  }
  if (command === undefined || !commands.has(command))
    throw new P0ValidationError(
      "CLI_COMMAND_INVALID",
      "The compatibility matrix command is missing or unsupported.",
      "Use validate or report.",
    );
  return { command, options };
}

async function readJson(path: string): Promise<unknown> {
  let raw: string;
  try {
    raw = await readFile(path, "utf8");
  } catch {
    throw new P0ValidationError(
      "COMPATIBILITY_DATA_MISSING",
      `The compatibility data file ${path} is unreadable.`,
      "Restore the versioned validation/p0 compatibility data files.",
    );
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new P0ValidationError(
      "JSON_INVALID",
      `The compatibility data file ${path} is not valid JSON.`,
      "Regenerate the versioned validation asset from its source of truth.",
    );
  }
}

async function loadDocuments(dataRoot: string): Promise<{
  readonly targets: unknown;
  readonly ledger: unknown;
  readonly trustPolicy: unknown;
}> {
  const [targets, ledger, trustPolicy] = await Promise.all([
    readJson(join(dataRoot, "compatibility-targets.v1.json")),
    readJson(join(dataRoot, "compatibility-ledger.v1.json")),
    readJson(join(dataRoot, "compatibility-trust-policy.v1.json")),
  ]);
  return { targets, ledger, trustPolicy };
}

async function runCommand(
  command: string,
  options: Readonly<Record<string, string>>,
): Promise<{
  readonly status: "passed" | "ready" | "blocked";
  readonly report: unknown;
}> {
  const dataRoot = resolve(options["data-root"] ?? defaultDataRoot);
  const documents = await loadDocuments(dataRoot);
  if (command === "validate") {
    const targets = parseCompatibilityTargets(documents.targets);
    const trustPolicy = parseCompatibilityTrustPolicy(documents.trustPolicy);
    // Evidence locators resolve against the workspace root; PR-head
    // validation stages the PR's evidence files under --workspace-root.
    const reader = createRepoEvidenceReader(options["workspace-root"]);
    const ledger = await verifyCompatibilityLedgerEvidence(
      documents.ledger,
      trustPolicy,
      reader,
    );
    const matrix = await deriveSupportMatrix(
      targets,
      ledger,
      trustPolicy,
      reader,
    );
    return {
      status: "passed",
      report: {
        kind: "compatibility-ledger-validation",
        targets: targets.targets.length,
        ledgerEntries: ledger.entries.length,
        matrixCells: matrix.cells.length,
        matrixProjection: matrix.generatedFrom,
      },
    };
  }
  const minimum = options.minimum;
  const latest = options.latest;
  if (minimum === undefined || latest === undefined)
    throw new P0ValidationError(
      "CLI_ARGUMENT_INVALID",
      "The report command requires --minimum and --latest.",
      "Supply exact stable minimum and latest-in-range OMP Runtime versions.",
    );
  const plan = planCompatibilityMatrixRun(documents.targets, {
    minimumRuntime: minimum,
    latestInRangeRuntime: latest,
    ...(options["new-runtime"] === undefined
      ? {}
      : { newRuntime: options["new-runtime"] }),
  });
  const report = reportCompatibilityMatrixRun(plan, {
    liveHarnessAvailable: options["live-harness"] === "true",
  });
  return { status: report.status, report };
}

try {
  const parsed = parseArguments(process.argv.slice(2));
  const result = await runCommand(parsed.command, parsed.options);
  process.stdout.write(`${JSON.stringify(result.report)}\n`);
  if (result.status !== "passed" && result.status !== "ready")
    process.exitCode = 1;
} catch (error) {
  const normalized =
    error instanceof P0ValidationError
      ? {
          code: error.code,
          message: error.message,
          recovery: error.recovery,
          details: error.details,
        }
      : {
          code: "COMPATIBILITY_MATRIX_UNEXPECTED_FAILURE",
          message:
            "The compatibility matrix command stopped before producing a safe result.",
          recovery:
            "Inspect the local output and correct the deterministic validation input.",
        };
  process.stderr.write(`${JSON.stringify(normalized)}\n`);
  process.exitCode = 1;
}
