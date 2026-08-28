import { describe, expect, it } from "vitest";
import { consumeNotifyMessage } from "../scripts/p0/host-event/run-command-surface-cell.ts";
import { hasSensitiveText } from "../scripts/p0/sanitization.ts";

const DIGEST = "a".repeat(64);
const pathBearingPlan = JSON.stringify({
  digest: DIGEST,
  targets: [{ path: "/home/runner/work/KPi/KPi/.omp/AGENTS.md" }],
});

function sanitizationDelta(message: string): number {
  const consumed = consumeNotifyMessage(message);
  if (!consumed.recordAsText) return 0;
  return hasSensitiveText(message) ? 1 : 0;
}

describe("consumeNotifyMessage", () => {
  it("does not record a schema-valid path-bearing onboard plan as text", () => {
    expect(hasSensitiveText(pathBearingPlan)).toBe(true);
    const consumed = consumeNotifyMessage(pathBearingPlan);
    expect(consumed.recordAsText).toBe(false);
    expect(consumed.planNotification).toEqual({
      digest: DIGEST,
      targetCount: 1,
    });
    expect(hasSensitiveText(JSON.stringify(consumed.planNotification))).toBe(
      false,
    );
    expect(sanitizationDelta(pathBearingPlan)).toBe(0);
  });

  it("fail-closes an unparsed path-bearing notify", () => {
    const message = "plan written to /home/runner/work/KPi/KPi/.omp";
    expect(hasSensitiveText(message)).toBe(true);
    const consumed = consumeNotifyMessage(message);
    expect(consumed.recordAsText).toBe(true);
    expect(consumed.planNotification).toBeUndefined();
    expect(sanitizationDelta(message)).toBe(1);
  });
});
