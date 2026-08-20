import { describe, expect, it } from "vitest";
import {
  inspectManagedBlock,
  type ManagedBlock,
  renderManagedBlock,
} from "../src/agents/index.ts";

const block: ManagedBlock = {
  role: "global",
  sourceId: "sbtd-workflow-kit-upstream",
  sourceRevision: "340f9dd4dc7a92e8b91c31e111de9a8de06cef36",
  transformVersion: "p0-v1",
  content: "managed content\n",
};

describe("Feature: Managed Block ownership", () => {
  it("Scenario: 重复 ownership metadata 会 fail closed", () => {
    const duplicateDigest = renderManagedBlock(block).replace(
      " digest=",
      " source=forged digest=",
    );

    expect(inspectManagedBlock(duplicateDigest, "global")).toMatchObject({
      state: "blocked",
    });
  });

  it("Scenario: 换行结尾的模板写入后仍可验证 managed digest", () => {
    expect(
      inspectManagedBlock(renderManagedBlock(block), "global"),
    ).toMatchObject({
      state: "merge-required",
      block: { content: "managed content\n" },
    });
  });

  it("Scenario: 无换行结尾的模板写入后仍可验证 managed digest", () => {
    expect(
      inspectManagedBlock(
        renderManagedBlock({ ...block, content: "managed content" }),
        "global",
      ),
    ).toMatchObject({
      state: "merge-required",
      block: { content: "managed content\n" },
    });
  });
});
