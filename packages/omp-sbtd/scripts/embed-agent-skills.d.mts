/** Read-only subset guaranteed by the JS manifest validator and used by callers. */
export interface AgentPluginManifest {
  readonly certified: readonly string[];
  readonly certifiedCount: number;
  readonly skills: Readonly<
    Record<string, Readonly<{ files: Readonly<Record<string, string>> }>>
  >;
}

export interface AgentSkillsPaths {
  readonly source: string;
  readonly destination: string;
}

export function readAgentPluginManifest(
  source: string,
): Promise<AgentPluginManifest>;

export function validateEmbeddedAgentSkills(
  options: AgentSkillsPaths,
): Promise<void>;

export function embedAgentSkills(
  options: AgentSkillsPaths & {
    readonly renameOperation?: (from: string, to: string) => Promise<void>;
  },
): Promise<void>;
