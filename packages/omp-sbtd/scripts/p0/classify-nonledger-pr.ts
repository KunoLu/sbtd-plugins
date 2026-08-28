// Non-ledger required-status decision for ordinary production PRs.
//
// The GitHub Actions workflow never checkouts the PR head. It feeds this
// module API JSON collected on trusted main. Absence of ledger filenames is
// not sufficient for success.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { z } from "zod";

const TRUSTED_HEAD_REPO = "KunoLu/sbtd-plugins";
const TRUSTED_BASE_REF = "main";
const AUTOMATION_BRANCH_PREFIX = "omp-compatibility/";

export const LINUX_PROBE_CHECK_NAME =
  "Frozen-tarball Host Event live cell on ubuntu-latest";
export const LINUX_PROBE_WORKFLOW_PATH =
  ".github/workflows/omp-runtime-linux-probe.yml";
const GITHUB_ACTIONS_APP_SLUG = "github-actions";

const ALLOWLISTED_CHECKS = [
  {
    checkName: LINUX_PROBE_CHECK_NAME,
    workflowPath: LINUX_PROBE_WORKFLOW_PATH,
    appSlug: GITHUB_ACTIONS_APP_SLUG,
  },
] as const;

const CONTROL_PLANE_PREFIXES = [
  ".github/",
  "packages/omp-sbtd/validation/p0/evidence/",
] as const;

const CONTROL_PLANE_FILES: Record<string, true> = {
  "packages/omp-sbtd/validation/p0/compatibility-targets.v1.json": true,
  "packages/omp-sbtd/validation/p0/compatibility-ledger.v1.json": true,
  "packages/omp-sbtd/validation/p0/compatibility-trust-policy.v1.json": true,
  "packages/omp-sbtd/validation/p0/compatibility.v2.json": true,
};

const sha40Schema = z
  .string()
  .regex(/^[a-f0-9]{40}$/, "expected a 40-hex commit SHA");

const checkRunSchema = z.object({
  name: z.string().min(1),
  appSlug: z.string().min(1),
  status: z.string().min(1),
  conclusion: z.string().nullable(),
});

const workflowRunSchema = z.object({
  id: z.number().int().positive(),
  path: z.string().min(1),
  headSha: sha40Schema,
  status: z.string().min(1),
  conclusion: z.string().nullable(),
});

const jobSchema = z.object({
  name: z.string().min(1),
  status: z.string().min(1),
  conclusion: z.string().nullable(),
});

export const nonledgerStatusInputSchema = z.object({
  state: z.string().min(1),
  headRepo: z.string().min(1),
  headRef: z.string().min(1),
  baseRef: z.string().min(1),
  headSha: sha40Schema,
  expectedHeadSha: sha40Schema,
  freshHeadSha: sha40Schema.optional(),
  files: z.array(
    z.object({
      filename: z.string().min(1),
      previousFilename: z.string().min(1).optional(),
    }),
  ),
  checkRuns: z.array(checkRunSchema),
  workflowRuns: z.array(workflowRunSchema),
  jobsByRunId: z.record(z.string(), z.array(jobSchema)),
});

export type NonledgerStatusInput = z.infer<typeof nonledgerStatusInputSchema>;

export type NonledgerDecision =
  | "reject-identity"
  | "reject-control-plane"
  | "reject-prerequisites"
  | "reject-head-changed"
  | "allow-success";

export interface NonledgerStatusResult {
  readonly decision: NonledgerDecision;
  readonly reason: string;
  readonly mayWriteSuccess: boolean;
}

function isControlPlanePath(filename: string): boolean {
  if (CONTROL_PLANE_FILES[filename] === true) return true;
  return CONTROL_PLANE_PREFIXES.some((prefix) => filename.startsWith(prefix));
}

function allowlistedChecksSucceeded(input: NonledgerStatusInput): boolean {
  const sha = input.expectedHeadSha;
  return ALLOWLISTED_CHECKS.every((row) => {
    const checkOk = input.checkRuns.some(
      (run) =>
        run.name === row.checkName &&
        run.appSlug === row.appSlug &&
        run.status === "completed" &&
        run.conclusion === "success",
    );
    if (!checkOk) return false;
    return input.workflowRuns.some((workflowRun) => {
      if (workflowRun.path !== row.workflowPath) return false;
      if (workflowRun.headSha !== sha) return false;
      if (workflowRun.status !== "completed") return false;
      if (workflowRun.conclusion !== "success") return false;
      const jobs = input.jobsByRunId[String(workflowRun.id)] ?? [];
      return jobs.some(
        (job) =>
          job.name === row.checkName &&
          job.status === "completed" &&
          job.conclusion === "success",
      );
    });
  });
}

export function evaluateNonledgerStatus(raw: unknown): NonledgerStatusResult {
  const input = nonledgerStatusInputSchema.parse(raw);
  if (
    input.state !== "open" ||
    input.headRepo !== TRUSTED_HEAD_REPO ||
    input.baseRef !== TRUSTED_BASE_REF ||
    input.headSha !== input.expectedHeadSha ||
    input.headRef.startsWith(AUTOMATION_BRANCH_PREFIX)
  ) {
    return {
      decision: "reject-identity",
      reason:
        "PR failed non-ledger identity (open, same-repo, base main, exact SHA, non-automation branch)",
      mayWriteSuccess: false,
    };
  }
  if (input.freshHeadSha && input.freshHeadSha !== input.expectedHeadSha) {
    return {
      decision: "reject-head-changed",
      reason: `PR head moved from ${input.expectedHeadSha} to ${input.freshHeadSha}`,
      mayWriteSuccess: false,
    };
  }
  if (
    input.files.length === 0 ||
    input.files.some(
      (file) =>
        isControlPlanePath(file.filename) ||
        (file.previousFilename !== undefined &&
          isControlPlanePath(file.previousFilename)),
    )
  ) {
    return {
      decision: "reject-control-plane",
      reason: "PR files are empty or include a fail-closed control-plane path",
      mayWriteSuccess: false,
    };
  }
  if (!allowlistedChecksSucceeded(input)) {
    return {
      decision: "reject-prerequisites",
      reason:
        "Every allowlisted GitHub Actions check must succeed on the exact head SHA",
      mayWriteSuccess: false,
    };
  }
  return {
    decision: "allow-success",
    reason: "Ordinary production PR with allowlisted checks succeeded",
    mayWriteSuccess: true,
  };
}

function isDirectCli(): boolean {
  const entry = process.argv[1];
  if (typeof entry !== "string" || entry.length === 0) return false;
  return import.meta.url === pathToFileURL(resolve(entry)).href;
}

if (isDirectCli()) {
  const result = evaluateNonledgerStatus(
    JSON.parse(readFileSync(0, "utf8")) as unknown,
  );
  process.stdout.write(`${JSON.stringify(result)}\n`);
  process.exit(result.mayWriteSuccess ? 0 : 1);
}
