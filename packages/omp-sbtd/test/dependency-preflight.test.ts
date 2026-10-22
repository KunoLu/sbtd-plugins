import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";
import extension from "../src/extension.ts";

const exec = promisify(execFile);
const roots: string[] = [];
afterEach(async () => {
  await Promise.all(
    roots.splice(0).map((root) => rm(root, { recursive: true, force: true })),
  );
});

function host(
  preflight: (
    command: string,
    args: string[],
    options: { cwd?: string },
  ) => Promise<unknown>,
  projectRoot = tmpdir(),
) {
  const hooks = new Map<
    string,
    (event: unknown, ctx: unknown) => Promise<unknown>
  >();
  extension({
    zod: z,
    registerCommand() {},
    registerTool() {},
    on(
      name: string,
      handler: (event: unknown, ctx: unknown) => Promise<unknown>,
    ) {
      hooks.set(name, handler);
    },
    appendEntry() {},
    exec: preflight,
  } as never);
  const toolCall = hooks.get("tool_call");
  if (toolCall === undefined) throw new Error("tool_call was not registered");
  return (command: string, cwd?: string) =>
    toolCall(
      {
        type: "tool_call",
        toolName: "bash",
        toolCallId: "dependency-check",
        input: { command, ...(cwd === undefined ? {} : { cwd }) },
      },
      {
        cwd: projectRoot,
        sessionManager: {
          getBranch() {
            return [];
          },
        },
      },
    );
}

const missingAll = [
  "jsonschema",
  "PyYAML",
  "markdown-it-py",
  "tomlkit",
  "cryptography",
];
describe("Feature: 依赖型 Python 入口在执行前隔离预检", () => {
  it.each([
    "upgrade plan",
    "migration verify",
    "recovery plan",
    "cleanup-legacy plan",
  ])("Scenario: upgrade 或 migration 缺任一依赖时拒绝执行: %s", async (entry) => {
    const root = await mkdtemp(join(tmpdir(), "sbtd-dependency-preflight-"));
    roots.push(root);
    await exec("python3", [
      "-B",
      "-m",
      "venv",
      "--without-pip",
      join(root, "venv"),
    ]);
    const python = join(root, "venv/bin/python3");
    await Promise.all(
      ["jsonschema", "yaml", "markdown_it", "tomlkit", "cryptography"].map(
        (module) =>
          writeFile(
            join(root, `${module}.py`),
            "# Must not satisfy isolated imports\n",
          ),
      ),
    );
    const check = host(async (command, args) => {
      const result = await exec(command, args, {
        env: {
          PATH: process.env.PATH,
          PYTHONDONTWRITEBYTECODE: "1",
          PYTHONPATH: root,
        },
      });
      return { ...result, code: 0, killed: false };
    });
    const refusal = (await check(
      `${python} /package/kit/onboard/runtime/scripts/onboard.py ${entry}`,
    )) as { block: boolean; reason: string };
    expect(refusal?.block).toBe(true);
    const detail = JSON.parse(refusal.reason);
    expect(detail).toMatchObject({
      code: "ISOLATED_DEPENDENCIES_UNAVAILABLE",
      missingPackages: missingAll,
    });
    expect(detail.installCommand).toMatch(
      /^python3 -m pip install -r .*requirements\.txt/,
    );
  });

  it.each([
    "relative",
    "absolute",
  ])("Scenario: bash cwd 中的相对 Python 使用实际解释器: %s", async (kind) => {
    const root = await mkdtemp(join(tmpdir(), "sbtd-probe-cwd-"));
    roots.push(root);
    const work = join(root, "nested");
    await exec("python3", [
      "-B",
      "-m",
      "venv",
      "--without-pip",
      join(work, "venv"),
    ]);
    const check = host(async (command, args, options) => {
      const result = await exec(command, args, {
        cwd: options.cwd,
        env: { PATH: process.env.PATH, PYTHONDONTWRITEBYTECODE: "1" },
      });
      return { ...result, code: 0, killed: false };
    }, root);
    const refusal = (await check(
      "./venv/bin/python3 onboard.py migration verify",
      kind === "absolute" ? work : "nested",
    )) as { block: boolean; reason: string };
    expect(refusal.block).toBe(true);
    expect(JSON.parse(refusal.reason).missingPackages).toEqual(missingAll);
  });

  it.each([
    "~/nested",
    "~//nested",
    "~\\nested",
    "~nested",
  ])("Scenario: bash tilde cwd 保留宿主 home 前缀: %s", async (cwd) => {
    const root = await mkdtemp(join(tmpdir(), "sbtd-probe-home-"));
    roots.push(root);
    const home = join(root, "home");
    // Pinned host expandTilde concatenates the home prefix for ~\ as well.
    const work = cwd === "~\\nested" ? `${home}\\nested` : join(home, "nested");
    await exec("python3", [
      "-B",
      "-m",
      "venv",
      "--without-pip",
      join(work, "venv"),
    ]);
    const previousHome = process.env.HOME;
    try {
      process.env.HOME = home;
      const check = host(async (command, args, options) => {
        const result = await exec(command, args, {
          cwd: options.cwd,
          env: { PATH: process.env.PATH, PYTHONDONTWRITEBYTECODE: "1" },
        });
        return { ...result, code: 0, killed: false };
      }, root);
      const refusal = (await check(
        "./venv/bin/python3 onboard.py migration verify",
        cwd,
      )) as { block: boolean; reason: string };
      expect(refusal.block).toBe(true);
      expect(JSON.parse(refusal.reason).missingPackages).toEqual(missingAll);
    } finally {
      if (previousHome === undefined) delete process.env.HOME;
      else process.env.HOME = previousHome;
    }
  });

  it("Scenario: 验签入口缺 cryptography 时拒绝执行", async () => {
    const check = host(async (_command, args) => {
      expect(args.slice(0, 3)).toEqual(["-I", "-B", "-c"]);
      return {
        stdout: JSON.stringify({ missingPackages: ["cryptography"] }),
        stderr: "",
        code: 0,
        killed: false,
      };
    });
    const refusal = (await check(
      "python3 /package/kit/onboard/runtime/scripts/onboard.py migration verify",
    )) as { block: boolean; reason: string };
    expect(refusal?.block).toBe(true);
    expect(JSON.parse(refusal.reason)).toMatchObject({
      missingPackages: ["cryptography"],
    });
  });

  it("Scenario: 普通 onboard stdlib 入口不要求五个依赖", async () => {
    let probes = 0;
    const check = host(async () => {
      probes += 1;
      throw new Error("unexpected probe");
    });
    for (const entry of [
      "check-agent-cli --platform omp --json",
      "install-external-skills --all --source stable",
    ]) {
      expect(
        await check(
          `python3 /package/migration-project/kit/onboard/runtime/scripts/onboard.py ${entry}`,
        ),
      ).toBeUndefined();
    }
    expect(probes).toBe(0);
  });

  it.each([
    { stdout: "not-json", code: 0, killed: false },
    { stdout: '{"missingPackages":[]}', code: 1, killed: false },
    { stdout: '{"missingPackages":[]}', code: 0, killed: true },
  ])("Scenario: 预检失败不得解释为依赖齐全: %j", async (result) => {
    const check = host(async () => ({ ...result, stderr: "" }));
    expect(await check("python3 onboard.py upgrade verify")).toMatchObject({
      block: true,
    });
  });

  it("Scenario: 依赖预检不缓存成功且涵盖直接验签模块", async () => {
    let probes = 0;
    const check = host(async () => ({
      stdout: JSON.stringify({
        missingPackages: probes++ === 0 ? [] : ["cryptography"],
      }),
      stderr: "",
      code: 0,
      killed: false,
    }));
    expect(await check('python3 -c "import sbtd_migration"')).toBeUndefined();
    expect(await check('python3 -c "import sbtd_migration"')).toMatchObject({
      block: true,
    });
  });

  it("Scenario: 无法绑定解释器的依赖入口拒跑但文件读取不预检", async () => {
    let probes = 0;
    const check = host(async () => {
      probes += 1;
      throw new Error("unexpected probe");
    });
    expect(await check("env python3 onboard.py upgrade plan")).toMatchObject({
      block: true,
    });
    expect(
      await check("cat file && python3 onboard.py migration verify"),
    ).toMatchObject({ block: true });
    expect(await check("cat sbtd_migration.py")).toBeUndefined();
    expect(probes).toBe(0);
  });
});
