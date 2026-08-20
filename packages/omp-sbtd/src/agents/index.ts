import { createHash } from "node:crypto";

export type AgentTargetRole = "global" | "project-root" | "project-omp";
export type ManagedAssetState =
  | "absent"
  | "exact"
  | "drifted"
  | "merge-required"
  | "blocked";

export interface AgentTarget {
  readonly role: AgentTargetRole;
  readonly path: string;
}

export interface AgentContextTarget extends AgentTarget {
  readonly exists: boolean;
  readonly discovered: boolean;
  readonly loaded: boolean;
  readonly effective: boolean;
  readonly shadowedBy?: AgentTargetRole;
  readonly imports: readonly string[];
}

export interface AgentContext {
  readonly targets: readonly AgentContextTarget[];
  readonly importValid: boolean;
}

export interface DiscoverAgentContextInputs {
  readonly targets: readonly AgentTarget[];
  readonly readText: (path: string) => Promise<string | undefined>;
}

export interface ManagedBlock {
  readonly role: AgentTargetRole;
  readonly sourceId: string;
  readonly sourceRevision: string;
  readonly transformVersion: string;
  readonly content: string;
}

export interface ManagedBlockOwnership {
  readonly role: AgentTargetRole;
  readonly sourceId: string;
  readonly sourceRevision: string;
  readonly transformVersion: string;
  readonly installedDigest: string;
}

export interface InspectedBlock {
  readonly state: ManagedAssetState;
  readonly block?: ManagedBlock;
  readonly digest?: string;
  readonly repairPath?: string;
}

export function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

export function resolveAgentTargets(
  projectRoot: string,
  agentDirectory: string,
): readonly AgentTarget[] {
  if (!projectRoot || !agentDirectory)
    throw new Error(
      "Onboard requires explicit project root and OMP agent directory.",
    );
  return [
    { role: "global", path: `${agentDirectory}/AGENTS.md` },
    { role: "project-root", path: `${projectRoot}/AGENTS.md` },
    { role: "project-omp", path: `${projectRoot}/.omp/AGENTS.md` },
  ];
}

export async function discoverAgentContext(
  inputs: DiscoverAgentContextInputs,
): Promise<AgentContext> {
  const contents = await Promise.all(
    inputs.targets.map(async (target) => ({
      target,
      content: await inputs.readText(target.path),
    })),
  );
  const projectRoot = contents.find(
    ({ target }) => target.role === "project-root",
  );
  const projectOmp = contents.find(
    ({ target }) => target.role === "project-omp",
  );
  const adapterImportsRoot =
    projectOmp?.content
      ?.split(/\r?\n/)
      .some((line) => line.trim() === "@../AGENTS.md") ?? false;
  const importValid = projectRoot?.content !== undefined && adapterImportsRoot;
  const targets = contents.map(({ target, content }) => {
    const exists = content !== undefined;
    const imports =
      content
        ?.split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.startsWith("@")) ?? [];
    const effective =
      target.role === "project-root"
        ? exists && (projectOmp?.content === undefined || importValid)
        : target.role === "project-omp"
          ? exists && importValid
          : exists;
    return {
      ...target,
      exists,
      discovered: exists,
      loaded: exists,
      effective,
      ...(target.role === "project-root" && projectOmp?.content !== undefined
        ? { shadowedBy: "project-omp" as const }
        : {}),
      imports,
    };
  });
  return { targets, importValid };
}

export function normalizeManagedBlockContent(content: string): string {
  return content.replace(/\n?$/, "\n");
}

export function renderManagedBlock(block: ManagedBlock): string {
  const content = normalizeManagedBlockContent(block.content);
  const digest = sha256(content);
  return `<!-- kpi:managed-begin role=${block.role} source=${block.sourceId} revision=${block.sourceRevision} transform=${block.transformVersion} digest=${digest} -->\n${content}<!-- kpi:managed-end role=${block.role} -->\n`;
}

export function inspectManagedBlock(
  content: string,
  role: AgentTargetRole,
  expectedOwnership?: ManagedBlockOwnership,
): InspectedBlock {
  const begins = [...content.matchAll(/<!-- kpi:managed-begin\s+([^>]+) -->/g)];
  const ends = [
    ...content.matchAll(/<!-- kpi:managed-end\s+role=([^\s>]+)\s*-->/g),
  ];
  if (begins.length === 0 && ends.length === 0) return { state: "absent" };
  if (begins.length !== 1 || ends.length !== 1)
    return {
      state: "blocked",
      repairPath:
        "Repair duplicate or malformed KPi managed markers before onboarding.",
    };
  const begin = begins[0];
  const end = ends[0];
  if (
    !begin ||
    !end ||
    begin[1] === undefined ||
    end.index <= begin.index ||
    end[1] !== role
  )
    return {
      state: "blocked",
      repairPath: "Repair managed marker ownership before onboarding.",
    };
  const metadata: Record<string, string> = {};
  const expectedKeys = new Set([
    "role",
    "source",
    "revision",
    "transform",
    "digest",
  ]);
  const parts = begin[1].trim().split(/\s+/);
  for (const part of parts) {
    const [key, value, extra] = part.split("=");
    if (
      !key ||
      !value ||
      extra !== undefined ||
      !expectedKeys.has(key) ||
      metadata[key] !== undefined
    )
      return {
        state: "blocked",
        repairPath:
          "Repair duplicate or malformed KPi managed marker metadata before onboarding.",
      };
    metadata[key] = value;
  }
  if (
    parts.length !== expectedKeys.size ||
    Object.keys(metadata).length !== expectedKeys.size ||
    metadata.role !== role
  )
    return {
      state: "blocked",
      repairPath:
        "Repair incomplete KPi managed marker metadata before onboarding.",
    };
  const start =
    begin.index +
    begin[0].length +
    (content[begin.index + begin[0].length] === "\n" ? 1 : 0);
  const body = content.slice(start, end.index);
  const block: ManagedBlock = {
    role,
    sourceId: metadata.source as string,
    sourceRevision: metadata.revision as string,
    transformVersion: metadata.transform as string,
    content: body,
  };
  const digest = sha256(body);
  if (metadata.digest !== digest)
    return {
      state: "blocked",
      repairPath:
        "Managed block digest is corrupt; use /sbtd onboard reset after review.",
    };
  if (
    expectedOwnership === undefined ||
    expectedOwnership.role !== role ||
    expectedOwnership.sourceId !== block.sourceId ||
    expectedOwnership.sourceRevision !== block.sourceRevision ||
    expectedOwnership.transformVersion !== block.transformVersion
  )
    return {
      state: "merge-required",
      block,
      digest,
      repairPath:
        "Managed block ownership is unrecorded or foreign; reconcile provenance before onboarding.",
    };
  if (expectedOwnership.installedDigest !== digest)
    return {
      state: "merge-required",
      block,
      digest,
      repairPath:
        "Managed block content differs from recorded provenance; reconcile it before onboarding.",
    };
  return { state: "drifted", block, digest };
}

export function mergeManagedBlock(
  existing: string,
  block: ManagedBlock,
  expectedOwnership?: ManagedBlockOwnership,
): { next: string; state: ManagedAssetState } {
  const inspected = inspectManagedBlock(
    existing,
    block.role,
    expectedOwnership,
  );
  const rendered = renderManagedBlock(block);
  if (inspected.state === "blocked" || inspected.state === "merge-required")
    return { next: existing, state: inspected.state };
  if (inspected.state === "absent")
    return {
      next: `${existing}${existing.length > 0 && !existing.endsWith("\n") ? "\n" : ""}${rendered}`,
      state: "absent",
    };
  const existingRendered = renderManagedBlock(inspected.block as ManagedBlock);
  const actual = existing.slice(
    existing.indexOf("<!-- kpi:managed-begin"),
    existing.indexOf("<!-- kpi:managed-end") +
      existing
        .slice(existing.indexOf("<!-- kpi:managed-end"))
        .indexOf("-->\n") +
      4,
  );
  if (actual === rendered) return { next: existing, state: "exact" };
  if (existingRendered === actual)
    return { next: existing.replace(actual, rendered), state: "drifted" };
  return { next: existing, state: "blocked" };
}
