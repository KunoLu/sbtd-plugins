import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const pluginRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

function unexpected(rel: string): boolean {
  const out = execFileSync(
    "python3",
    [
      "-c",
      "import sys; sys.path.insert(0, 'scripts/p0/host-event'); from section4_write_check import is_unexpected_host_project_write; print('1' if is_unexpected_host_project_write(sys.argv[1]) else '0')",
      rel,
    ],
    { cwd: pluginRoot, encoding: "utf8" },
  ).trim();
  return out === "1";
}

describe("is_unexpected_host_project_write", () => {
  it("ignores kit templates that contain /project/ in the path", () => {
    expect(
      unexpected(
        "host-run/run-1/agent/plugins/node_modules/@kunolu/omp-sbtd/kit/onboard/runtime/templates/project/gitignore.template",
      ),
    ).toBe(false);
  });

  it("allows the driver's pre-written Host config", () => {
    expect(unexpected("host-run/run-1/project/.omp/config.yml")).toBe(false);
  });

  it("flags a real Host project write", () => {
    expect(unexpected("host-run/run-1/project/.gitignore")).toBe(true);
  });
});
