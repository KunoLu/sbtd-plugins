import { randomUUID } from "node:crypto";
import { describe, expect, it } from "vitest";
import {
  type AcceptedSkipContext,
  createAcceptedSkipService,
  eligibleAcceptedSkips,
} from "../src/environment/accepted-skip.ts";
import type { FileAdapter } from "../src/onboard/index.ts";

function memoryFiles(): FileAdapter & {
  readonly files: Map<string, string>;
  readonly writes: string[];
} {
  const files = new Map<string, string>();
  const writes: string[] = [];
  return {
    files,
    writes,
    async readText(path) {
      return files.get(path);
    },
    async writeAtomic(path, content) {
      writes.push(path);
      files.set(path, content);
    },
    async makeDirectory(path) {
      if (files.has(path)) {
        const error = Object.assign(new Error("EEXIST"), { code: "EEXIST" });
        throw error;
      }
      files.set(path, "");
    },
    async exists(path) {
      return files.has(path);
    },
    async remove(path) {
      files.delete(path);
    },
    async isSymlink() {
      return false;
    },
  };
}

const provenance = {
  sourceId: "sbtd-workflow-kit-upstream" as const,
  kitRevision: "a".repeat(64),
  transformVersion: "p0-v1",
};
const projectRootKey = "b".repeat(64);

function context(
  overrides: Partial<AcceptedSkipContext> = {},
): AcceptedSkipContext {
  return {
    scope: "project",
    projectRootKey,
    onboardProfileId: "omp-p0-standard-v1",
    kitMajor: 1,
    route: "auto",
    profile: { required: ["plugin-kit-alignment"], optional: ["ui"] },
    routeRequiredCapabilities: [],
    provenance,
    ...overrides,
  };
}

describe("Feature: SBTD 控制引导", () => {
  it("Scenario: AcceptedSkip Plan 与 list 均不写入持久存储", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });

    expect((await service.list()).kind).toBe("ok");
    const planned = await service.planCreate(context(), {
      capability: "ui",
      reason: "temporary local exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });

    expect(planned.kind).toBe("planned");
    expect(files.writes).toEqual([]);
    expect(files.files).toEqual(new Map());
  });

  it("Scenario: AcceptedSkip Plan 的 Route 由摘要保护", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });
    const planned = await service.planCreate(context(), {
      capability: "ui",
      reason: "route digest protection",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (planned.kind !== "planned")
      throw new Error("expected AcceptedSkip Plan");

    await expect(
      service.apply({
        ...planned.plan,
        context: { ...planned.plan.context, route: "bugfix" },
      }),
    ).resolves.toMatchObject({
      kind: "stale",
      message: "AcceptedSkip Plan digest is invalid.",
    });
    expect(files.writes).toEqual([]);
  });

  it("Scenario: 未知或畸形 AcceptedSkip schema fail closed", async () => {
    const files = memoryFiles();
    files.files.set(
      "/agent/kpi/provenance/accepted-skips-v1.json",
      JSON.stringify({ schemaVersion: 2, revision: 0, records: [] }),
    );
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });

    await expect(service.list()).resolves.toMatchObject({
      kind: "invalid-store",
      records: [],
    });
  });

  it("Scenario: 仅精确 active Optional AcceptedSkip 使环境降级", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
      operationId: randomUUID,
    });
    const planned = await service.planCreate(context(), {
      capability: "ui",
      reason: "temporary local exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (planned.kind !== "planned")
      throw new Error("expected AcceptedSkip Plan");
    await expect(service.apply(planned.plan)).resolves.toMatchObject({
      kind: "applied",
      record: { status: "active", capability: "ui" },
    });
    const listed = await service.list();
    if (listed.kind !== "ok") throw new Error("expected AcceptedSkip store");

    expect(
      eligibleAcceptedSkips(
        listed.records,
        context(),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toHaveLength(1);
    expect(
      eligibleAcceptedSkips(
        listed.records,
        context({ projectRootKey: "c".repeat(64) }),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toEqual([]);
    expect(
      eligibleAcceptedSkips(
        listed.records,
        context({ scope: "global", projectRootKey: undefined }),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toEqual([]);
    expect(
      eligibleAcceptedSkips(
        listed.records,
        context({ profile: { required: ["ui"], optional: [] } }),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toEqual([]);
    expect(
      eligibleAcceptedSkips(
        listed.records,
        context({ routeRequiredCapabilities: ["ui"] }),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toEqual([]);
    expect(
      eligibleAcceptedSkips(
        listed.records,
        context({
          provenance: { ...provenance, transformVersion: "p0-v2" },
        }),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toEqual([]);
  });

  it("Scenario: 项目与全局 AcceptedSkip 仅在精确作用域内有效", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });
    const project = await service.planCreate(context(), {
      capability: "ui",
      reason: "project exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (project.kind !== "planned") throw new Error("expected project Plan");
    await service.apply(project.plan);
    const globalContext = context({
      scope: "global",
      projectRootKey: undefined,
    });
    const global = await service.planCreate(globalContext, {
      capability: "ui",
      reason: "global exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (global.kind !== "planned") throw new Error("expected global Plan");
    await service.apply(global.plan);
    const listed = await service.list();
    if (listed.kind !== "ok") throw new Error("expected AcceptedSkip store");
    expect(
      eligibleAcceptedSkips(
        listed.records,
        context({ projectRootKey: "c".repeat(64) }),
        "2026-07-25T00:00:00.000Z",
      ),
    ).toEqual([]);
    expect(
      eligibleAcceptedSkips(
        listed.records,
        globalContext,
        "2026-07-25T00:00:00.000Z",
      ),
    ).toHaveLength(1);
  });

  it("Scenario: 并发 AcceptedSkip Apply 不丢失 append-only 历史", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
      operationId: randomUUID,
    });
    const [first, second] = await Promise.all([
      service.planCreate(context(), {
        capability: "ui",
        reason: "first concurrent exemption",
        expiresAt: "2026-08-01T00:00:00.000Z",
      }),
      service.planCreate(context(), {
        capability: "ui",
        reason: "second concurrent exemption",
        expiresAt: "2026-08-01T00:00:00.000Z",
      }),
    ]);
    if (first.kind !== "planned" || second.kind !== "planned")
      throw new Error("expected concurrent AcceptedSkip Plans");
    const results = await Promise.all([
      service.apply(first.plan),
      service.apply(second.plan),
    ]);
    expect(results.filter((result) => result.kind === "applied")).toHaveLength(
      1,
    );
    expect(results.filter((result) => result.kind === "stale")).toHaveLength(1);
    const listed = await service.list();
    if (listed.kind !== "ok") throw new Error("expected AcceptedSkip store");
    expect(listed.records).toHaveLength(1);
  });

  it("Scenario: 到期与撤销保留 append-only 历史并立即失效", async () => {
    const files = memoryFiles();
    let now = "2026-07-25T00:00:00.000Z";
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => now,
      operationId: randomUUID,
    });
    const created = await service.planCreate(context(), {
      capability: "ui",
      reason: "temporary local exemption",
      expiresAt: "2026-07-25T00:01:00.000Z",
    });
    if (created.kind !== "planned") throw new Error("expected create Plan");
    const applied = await service.apply(created.plan);
    if (applied.kind !== "applied") throw new Error("expected active record");
    now = "2026-07-25T00:02:00.000Z";
    const beforeReconcile = await service.list();
    if (beforeReconcile.kind !== "ok")
      throw new Error("expected AcceptedSkip store");
    expect(
      eligibleAcceptedSkips(beforeReconcile.records, context(), now),
    ).toEqual([]);
    const expired = await service.planExpire(context(), {
      recordId: applied.record.recordId,
      reason: "expiry reconciliation",
    });
    if (expired.kind !== "planned") throw new Error("expected expiry Plan");
    const expiredApplied = await service.apply(expired.plan);
    expect(expiredApplied).toMatchObject({
      kind: "applied",
      record: { status: "expired", predecessorVersion: 1 },
      revision: 2,
    });
    now = "2026-07-25T00:08:00.000Z";
    const writesAfterExpiry = files.writes.length;
    await expect(service.apply(expired.plan)).resolves.toMatchObject(
      expiredApplied,
    );
    expect(files.writes).toHaveLength(writesAfterExpiry);

    now = "2026-07-26T00:00:00.000Z";
    const second = await service.planCreate(context(), {
      capability: "ui",
      reason: "new temporary exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (second.kind !== "planned")
      throw new Error("expected second create Plan");
    const secondApplied = await service.apply(second.plan);
    if (secondApplied.kind !== "applied")
      throw new Error("expected second active record");
    now = "2026-07-26T00:00:01.000Z";
    const revoked = await service.planRevoke(context(), {
      recordId: secondApplied.record.recordId,
      reason: "tool is available",
    });
    if (revoked.kind !== "planned") throw new Error("expected revoke Plan");
    const revokedApplied = await service.apply(revoked.plan);
    expect(revokedApplied).toMatchObject({
      kind: "applied",
      record: { status: "revoked", predecessorVersion: 1 },
      revision: 4,
    });
    now = "2026-07-26T00:06:00.000Z";
    const writesAfterRevocation = files.writes.length;
    await expect(service.apply(revoked.plan)).resolves.toMatchObject(
      revokedApplied,
    );
    expect(files.writes).toHaveLength(writesAfterRevocation);
    const listed = await service.list();
    if (listed.kind !== "ok") throw new Error("expected AcceptedSkip store");
    expect(listed.records).toHaveLength(4);
    expect(eligibleAcceptedSkips(listed.records, context(), now)).toEqual([]);
  });

  it("Scenario: 已完成 AcceptedSkip Plan 可重放，过期与陈旧 Plan 被拒绝且零写入", async () => {
    let now = "2026-07-25T00:00:00.000Z";
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => now,
      operationId: randomUUID,
    });
    const first = await service.planCreate(context(), {
      capability: "ui",
      reason: "first exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (first.kind !== "planned") throw new Error("expected first Plan");
    const firstApplied = await service.apply(first.plan);
    if (firstApplied.kind !== "applied")
      throw new Error("expected first Applied result");
    const writesAfterApply = files.writes.length;
    now = "2026-07-25T00:06:00.000Z";
    await expect(service.apply(first.plan)).resolves.toMatchObject(
      firstApplied,
    );
    expect(files.writes).toHaveLength(writesAfterApply);

    const stale = await service.planCreate(context(), {
      capability: "ui",
      reason: "stale exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    const current = await service.planCreate(context(), {
      capability: "ui",
      reason: "current exemption",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (stale.kind !== "planned" || current.kind !== "planned")
      throw new Error("expected Plans");
    await expect(service.apply(current.plan)).resolves.toMatchObject({
      kind: "applied",
    });
    await expect(service.apply(stale.plan)).resolves.toMatchObject({
      kind: "stale",
    });
  });

  it("Scenario: Plan 在到期边界时被拒绝且零写入", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
      planTtlMs: 0,
    });
    const planned = await service.planCreate(context(), {
      capability: "ui",
      reason: "boundary test",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (planned.kind !== "planned")
      throw new Error("expected AcceptedSkip Plan");
    await expect(service.apply(planned.plan)).resolves.toMatchObject({
      kind: "stale",
    });
    expect(files.writes).toEqual([]);
  });

  it("Scenario: 时间顺序错误的 AcceptedSkip 存储 fail closed", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });
    const planned = await service.planCreate(context(), {
      capability: "ui",
      reason: "chronology test",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (planned.kind !== "planned")
      throw new Error("expected AcceptedSkip Plan");
    await service.apply(planned.plan);
    const stored = JSON.parse(
      files.files.get("/agent/kpi/provenance/accepted-skips-v1.json") as string,
    ) as { records: Array<Record<string, string>> };
    stored.records[0] = {
      ...(stored.records[0] as Record<string, string>),
      confirmedAt: "2000-01-01T00:00:00.000Z",
    };
    files.files.set(
      "/agent/kpi/provenance/accepted-skips-v1.json",
      JSON.stringify(stored),
    );
    await expect(service.list()).resolves.toMatchObject({
      kind: "invalid-store",
    });
  });
  it("Scenario: 历史 AcceptedSkip 记录缺少回放摘要时仍可读取", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });
    const planned = await service.planCreate(context(), {
      capability: "ui",
      reason: "legacy record",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (planned.kind !== "planned")
      throw new Error("expected AcceptedSkip Plan");
    await service.apply(planned.plan);
    const stored = JSON.parse(
      files.files.get("/agent/kpi/provenance/accepted-skips-v1.json") as string,
    ) as { records: Array<Record<string, unknown>> };
    delete stored.records[0]?.planDigest;
    files.files.set(
      "/agent/kpi/provenance/accepted-skips-v1.json",
      JSON.stringify(stored),
    );
    await expect(service.list()).resolves.toMatchObject({ kind: "ok" });
  });

  it("Scenario: 重复 AcceptedSkip 回放摘要 fail closed", async () => {
    const files = memoryFiles();
    const service = createAcceptedSkipService({
      files,
      agentDirectory: "/agent",
      now: () => "2026-07-25T00:00:00.000Z",
    });
    const first = await service.planCreate(context(), {
      capability: "ui",
      reason: "first digest",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (first.kind !== "planned") throw new Error("expected first Plan");
    await service.apply(first.plan);
    const second = await service.planCreate(context(), {
      capability: "ui",
      reason: "second digest",
      expiresAt: "2026-08-01T00:00:00.000Z",
    });
    if (second.kind !== "planned") throw new Error("expected second Plan");
    await service.apply(second.plan);
    const stored = JSON.parse(
      files.files.get("/agent/kpi/provenance/accepted-skips-v1.json") as string,
    ) as { records: Array<Record<string, unknown>> };
    stored.records[1] = {
      ...(stored.records[1] as Record<string, unknown>),
      planDigest: stored.records[0]?.planDigest,
    };
    files.files.set(
      "/agent/kpi/provenance/accepted-skips-v1.json",
      JSON.stringify(stored),
    );
    await expect(service.list()).resolves.toMatchObject({
      kind: "invalid-store",
    });
  });
});
