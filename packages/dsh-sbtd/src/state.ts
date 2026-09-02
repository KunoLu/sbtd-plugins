export type GateState =
  | "planned"
  | "running"
  | "passed"
  | "blocked"
  | "not-required";

export interface BookGatePlan {
  taskId: string;
  summary: string;
  gates: Record<
    "ddd" | "ddia" | "legacy" | "refactor" | "release",
    {
      requirement: "required" | "on-demand";
      state: GateState;
      fact?: string;
      reviewStatus?: string;
    }
  >;
  taskAutoExit?: boolean;
}

export interface SbtdSessionState {
  plan?: BookGatePlan;
  validate: { pre?: "done" | "skipped"; post?: "done" | "blocked" };
  maestro?: {
    java?: string;
    cli?: string;
    device?: string;
    appInstalled?: boolean;
    appEnv?: string;
    lastPreflight?: "ok" | "blocked";
    missing: string[];
  };
}

export interface SbtdHandoffSnapshot {
  plan?: BookGatePlan;
  maestro?: { missing: string[] };
}

const sessions = new Map<string, SbtdSessionState>();

export function getSession(sessionId: string): SbtdSessionState {
  const existing = sessions.get(sessionId);
  if (existing !== undefined) {
    return existing;
  }
  const created: SbtdSessionState = { validate: {} };
  sessions.set(sessionId, created);
  return created;
}

export function serialize(sessionId: string): SbtdHandoffSnapshot {
  const state = sessions.get(sessionId);
  if (state === undefined) {
    return {};
  }
  const snapshot: SbtdHandoffSnapshot = {};
  if (state.plan !== undefined) {
    snapshot.plan = structuredClone(state.plan);
  }
  if (state.maestro !== undefined) {
    snapshot.maestro = { missing: [...state.maestro.missing] };
  }
  return snapshot;
}

export function restore(
  sessionId: string,
  snapshot: SbtdHandoffSnapshot,
): void {
  const state = getSession(sessionId);
  if (snapshot.plan !== undefined) {
    state.plan = structuredClone(snapshot.plan);
  }
  if (snapshot.maestro !== undefined) {
    const current = state.maestro;
    state.maestro = {
      ...(current ?? { missing: [] }),
      missing: [...snapshot.maestro.missing],
    };
  }
}
