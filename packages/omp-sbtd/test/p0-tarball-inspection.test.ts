import { execFile as executeFile } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";
import { promisify } from "node:util";
import { gzipSync } from "node:zlib";
import { afterEach, describe, expect, it } from "vitest";
import { inspectPackedPluginTarball } from "../scripts/p0/release-validator.ts";

const workspaceRoot = new URL("../../..", import.meta.url).pathname;
const pluginRoot = join(workspaceRoot, "packages/omp-sbtd");
const p0CliPath = join(pluginRoot, "scripts/p0/cli.ts");
const tsxCliPath = join(pluginRoot, "node_modules/tsx/dist/cli.mjs");

const temporaryRoots: string[] = [];

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-p0-tarball-"));
  temporaryRoots.push(root);
  return root;
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

const runProcess = promisify(executeFile);
const packageManager = process.platform === "win32" ? "pnpm.cmd" : "pnpm";

interface TarEntry {
  readonly name: string;
  readonly payload?: Buffer;
  readonly typeflag?: string;
  readonly mode?: number;
  readonly prefix?: string;
}

function tarHeader(
  name: string,
  options: { size: number; typeflag: string; mode: number; prefix?: string },
): Buffer {
  const header = Buffer.alloc(512, 0);
  if (Buffer.byteLength(name) > 100) throw new Error("test name too long");
  header.write(name, 0, "utf8");
  header.write(`${options.mode.toString(8).padStart(7, "0")}\0`, 100, "utf8");
  header.write("0000000\0", 108, "utf8");
  header.write("0000000\0", 116, "utf8");
  header.write(`${options.size.toString(8).padStart(11, "0")}\0`, 124, "utf8");
  header.write("00000000000\0", 136, "utf8");
  header.fill(0x20, 148, 156);
  header.write(options.typeflag, 156, "utf8");
  header.write("ustar\0", 257, "utf8");
  header.write("00", 263, "utf8");
  if (options.prefix !== undefined) {
    if (Buffer.byteLength(options.prefix) > 155)
      throw new Error("test prefix too long");
    header.write(options.prefix, 345, "utf8");
  }
  let sum = 0;
  for (const byte of header) sum += byte;
  header.write(`${sum.toString(8).padStart(6, "0")} `, 148, "utf8");
  return header;
}

function paxRecord(key: string, value: string): string {
  const body = ` ${key}=${value}\n`;
  let length = body.length + 1;
  while (`${length}${body}`.length !== length)
    length = `${length}${body}`.length;
  return `${length}${body}`;
}

function buildTarGz(entries: readonly TarEntry[]): Buffer {
  const chunks: Buffer[] = [];
  for (const entry of entries) {
    const typeflag = entry.typeflag ?? "0";
    const isDirectory = typeflag === "5";
    const payload = entry.payload ?? Buffer.alloc(0);
    const name =
      isDirectory && !entry.name.endsWith("/") ? `${entry.name}/` : entry.name;
    chunks.push(
      tarHeader(name, {
        size: isDirectory ? 0 : payload.length,
        typeflag,
        mode: entry.mode ?? (isDirectory ? 0o755 : 0o644),
        ...(entry.prefix === undefined ? {} : { prefix: entry.prefix }),
      }),
    );
    if (!isDirectory && payload.length > 0) {
      chunks.push(payload);
      const padding = (512 - (payload.length % 512)) % 512;
      if (padding > 0) chunks.push(Buffer.alloc(padding));
    }
  }
  chunks.push(Buffer.alloc(1024));
  return gzipSync(Buffer.concat(chunks));
}

function expectTarballInvalid(bytes: Buffer, reason: string): void {
  try {
    inspectPackedPluginTarball(bytes);
  } catch (error) {
    expect(error).toMatchObject({
      name: "P0ValidationError",
      code: "CANDIDATE_TARBALL_INVALID",
    });
    expect(JSON.stringify(error)).toContain(reason);
    return;
  }
  throw new Error(`expected CANDIDATE_TARBALL_INVALID (${reason})`);
}

const LONG_DIRECTORY = `package/kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data`;
const LONG_FILE = `${LONG_DIRECTORY}/stacks/avalonia.csv`;

function validEntries(): TarEntry[] {
  return [
    { name: "package", typeflag: "5" },
    {
      name: "package/package.json",
      payload: Buffer.from('{"name":"@kunolu/omp-sbtd"}\n', "utf8"),
    },
    { name: "package/dist", typeflag: "5" },
    {
      name: "package/dist/extension.js",
      payload: Buffer.from("export default 1;\n", "utf8"),
      mode: 0o755,
    },
    {
      name: "package/kit/AGENTS.global.md",
      payload: Buffer.from("# OMP\n", "utf8"),
    },
  ];
}

async function candidateTemporaryRoot(): Promise<string> {
  const parent = join(workspaceRoot, ".tmp/kpi-p0");
  await mkdir(parent, { recursive: true });
  const root = await mkdtemp(join(parent, "candidate-tarball-"));
  temporaryRoots.push(root);
  return root;
}

async function runP0Cli(arguments_: readonly string[], evidenceRoot: string) {
  try {
    const { stdout, stderr } = await runProcess(
      process.execPath,
      [tsxCliPath, p0CliPath, ...arguments_],
      {
        cwd: pluginRoot,
        env: { ...process.env, KPI_P0_EVIDENCE_ROOT: evidenceRoot },
      },
    );
    return { exitCode: 0, stdout, stderr };
  } catch (error) {
    const result = error as Readonly<{ stdout?: string; stderr?: string }>;
    return {
      exitCode: 1,
      stdout: result.stdout ?? "",
      stderr: result.stderr ?? "",
    };
  }
}

describe("Feature: P0 发布一致性与证据 - 原始 tarball 成员校验", () => {
  it("Scenario: 合法 ustar、pax 长路径与 prefix 成员的 tarball 通过原始检查", () => {
    const extensionPayload = Buffer.from("export default 1;\n", "utf8");
    const inspection = inspectPackedPluginTarball(
      buildTarGz([
        ...validEntries(),
        { name: LONG_DIRECTORY, typeflag: "5" },
        {
          name: "pax-long-path",
          typeflag: "x",
          payload: Buffer.from(paxRecord("path", LONG_FILE), "utf8"),
        },
        {
          name: "PaxHeader.1",
          payload: Buffer.from("avalonia\n", "utf8"),
        },
        {
          name: "products.csv",
          prefix:
            "package/kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data",
          payload: Buffer.from("a,b\n", "utf8"),
        },
      ]),
    );

    expect(inspection.leaks).toEqual([]);
    const byPath = new Map(
      inspection.members.map((member) => [member.path, member]),
    );
    expect([...byPath.keys()].sort()).toEqual(
      [
        "package",
        "package/package.json",
        "package/dist",
        "package/dist/extension.js",
        "package/kit/AGENTS.global.md",
        LONG_DIRECTORY,
        LONG_FILE,
        "package/kit/onboard/runtime/assets/external-skills/stable/skills/ui-ux-pro-max/data/products.csv",
      ].sort(),
    );
    expect(byPath.get("package/dist")).toMatchObject({
      kind: "directory",
      executable: false,
      sha256: undefined,
    });
    expect(byPath.get("package/dist/extension.js")).toMatchObject({
      kind: "file",
      executable: true,
      sha256: createHash("sha256").update(extensionPayload).digest("hex"),
    });
    expect(byPath.get(LONG_FILE)).toMatchObject({ kind: "file" });
  });

  it("Scenario: RC 候选 tarball 拒绝重复或歧义成员", () => {
    const marker = "CoDeX-shadowed-payload-marker";
    const duplicate = buildTarGz([
      ...validEntries(),
      {
        name: "package/kit/AGENTS.global.md",
        payload: Buffer.from(`shadow ${marker}\n`, "utf8"),
      },
      {
        name: "package/kit/AGENTS.global.md",
        payload: Buffer.from("clean overwrite\n", "utf8"),
      },
    ]);
    try {
      inspectPackedPluginTarball(duplicate);
    } catch (error) {
      expect(error).toMatchObject({
        name: "P0ValidationError",
        code: "CANDIDATE_TARBALL_INVALID",
      });
      expect(JSON.stringify(error)).toContain("package/kit/AGENTS.global.md");
      expect(JSON.stringify(error)).not.toContain(marker);
      return;
    }
    throw new Error("expected duplicate member rejection");
  });

  it("Scenario: 文件与目录同名或 GNU 长路径遮蔽的 tarball 失败关闭", () => {
    expectTarballInvalid(
      buildTarGz([
        { name: "package/kit", typeflag: "5" },
        { name: "package/kit", payload: Buffer.from("file\n", "utf8") },
      ]),
      "package/kit",
    );
    expectTarballInvalid(
      buildTarGz([
        {
          name: "././@LongLink",
          typeflag: "L",
          payload: Buffer.from("package/legit.md\0", "utf8"),
        },
        {
          name: "package/legit.md",
          payload: Buffer.from("first\n", "utf8"),
        },
        {
          name: "package/legit.md",
          payload: Buffer.from("second\n", "utf8"),
        },
      ]),
      "package/legit.md",
    );
  });

  it("Scenario: 发布校验器拒绝含不安全路径段的 tarball 成员", () => {
    const unsafeNames = [
      "package/../outside.md",
      "package/./hidden.md",
      "package/a//b.md",
      "package/sub/../../escape.md",
      "package\\windows.md",
      "/package/absolute.md",
      "stranger/package.json",
      "package/has space.md",
    ];
    for (const name of unsafeNames) {
      expectTarballInvalid(
        buildTarGz([{ name, payload: Buffer.from("x\n", "utf8") }]),
        "CANDIDATE_TARBALL_INVALID",
      );
    }
    // A pax override cannot smuggle an unsafe path past name validation.
    expectTarballInvalid(
      buildTarGz([
        {
          name: "pax-override",
          typeflag: "x",
          payload: Buffer.from(
            paxRecord("path", "package/../pax-escape.md"),
            "utf8",
          ),
        },
        { name: "PaxHeader.2", payload: Buffer.from("x\n", "utf8") },
      ]),
      "CANDIDATE_TARBALL_INVALID",
    );
  });

  it("Scenario: 发布校验器拒绝链接、设备或畸形归档成员", () => {
    const rejectedTypeflags = ["1", "2", "3", "4", "6", "7", "g", "K"];
    for (const typeflag of rejectedTypeflags) {
      expectTarballInvalid(
        buildTarGz([
          {
            name: "package/member",
            typeflag,
            payload: Buffer.from("x", "utf8"),
          },
        ]),
        "CANDIDATE_TARBALL_INVALID",
      );
    }
    const checksumBroken = buildTarGz(validEntries());
    checksumBroken[10] = checksumBroken[10] ^ 0xff;
    expectTarballInvalid(checksumBroken, "CANDIDATE_TARBALL_INVALID");
    expectTarballInvalid(
      Buffer.from("not a gzip stream", "utf8"),
      "CANDIDATE_TARBALL_INVALID",
    );
    const trailing = Buffer.concat([
      buildTarGz(validEntries()),
      Buffer.from([1]),
    ]);
    expectTarballInvalid(trailing, "CANDIDATE_TARBALL_INVALID");
  });

  it("Scenario: 原始归档扫描覆盖每个成员载荷且不泄露内容", () => {
    const secretSentence = "See the CoDeX runtime migration guide.";
    const inspection = inspectPackedPluginTarball(
      buildTarGz([
        { name: "package", typeflag: "5" },
        {
          // macOS bsdtar hides AppleDouble metadata during extraction, but its
          // raw regular payload still belongs to the archive scan.
          name: "._package",
          payload: Buffer.from("AppleDouble CoDeX metadata\n", "utf8"),
        },
        { name: "package/codex-dir", typeflag: "5" },
        {
          name: "package/codex-dir/notes.md",
          payload: Buffer.from("clean\n", "utf8"),
        },
        {
          name: "package/kit/docs/codex-notes.md",
          payload: Buffer.from("clean payload\n", "utf8"),
        },
        {
          name: "package/kit/onboard/runtime/scripts/onboard.py",
          payload: Buffer.from("Codex compatibility branch\n", "utf8"),
        },
        {
          name: "package/kit/docs/README.md",
          payload: Buffer.from(`${secretSentence}\nCODEX again\n`, "utf8"),
        },
        {
          name: "package/kit/docs/binary.bin",
          payload: Buffer.from([0x00, 0x43, 0x4f, 0x44, 0x45, 0x58, 0xff]),
        },
      ]),
    );

    expect(inspection.leaks).toEqual([
      { path: "._package", pathMatches: 0, payloadMatches: 1 },
      { path: "package/codex-dir", pathMatches: 1, payloadMatches: 0 },
      {
        path: "package/codex-dir/notes.md",
        pathMatches: 1,
        payloadMatches: 0,
      },
      {
        path: "package/kit/docs/binary.bin",
        pathMatches: 0,
        payloadMatches: 1,
      },
      {
        path: "package/kit/docs/codex-notes.md",
        pathMatches: 1,
        payloadMatches: 0,
      },
      {
        path: "package/kit/docs/README.md",
        pathMatches: 0,
        payloadMatches: 2,
      },
      {
        // No embedded manifest binds this member's digest, so the canonical
        // path exemption does not apply and its payload is scanned raw.
        path: "package/kit/onboard/runtime/scripts/onboard.py",
        pathMatches: 0,
        payloadMatches: 1,
      },
    ]);
    expect(
      inspection.members.some((member) => member.path === "._package"),
    ).toBe(false);
    expect(JSON.stringify(inspection.leaks)).not.toContain(secretSentence);
  });

  it("Scenario: 只有与嵌入清单摘要绑定的 canonical runtime 成员可豁免泄漏扫描", () => {
    const canonicalPayload = Buffer.from(
      "Codex compatibility branch\n",
      "utf8",
    );
    const canonicalDigest = createHash("sha256")
      .update(canonicalPayload)
      .digest("hex");
    const manifestPayload = Buffer.from(
      `${JSON.stringify({
        assets: {
          "onboard/runtime/scripts/onboard.py": canonicalDigest,
        },
      })}\n`,
      "utf8",
    );

    // The genuine canonical member stays admissible when the embedded
    // manifest binds its exact digest, even declared after the member.
    const bound = inspectPackedPluginTarball(
      buildTarGz([
        { name: "package", typeflag: "5" },
        { name: "package/kit", typeflag: "5" },
        {
          name: "package/kit/onboard/runtime/scripts/onboard.py",
          payload: canonicalPayload,
        },
        { name: "package/kit/manifest.json", payload: manifestPayload },
      ]),
    );
    expect(bound.leaks).toEqual([]);

    // Any drift from the approved digest turns the same path into a leak.
    const tampered = inspectPackedPluginTarball(
      buildTarGz([
        { name: "package", typeflag: "5" },
        { name: "package/kit", typeflag: "5" },
        { name: "package/kit/manifest.json", payload: manifestPayload },
        {
          name: "package/kit/onboard/runtime/scripts/onboard.py",
          payload: Buffer.from(
            "Codex compatibility branch\nwith an extra CODEX marker\n",
            "utf8",
          ),
        },
      ]),
    );
    expect(tampered.leaks).toEqual([
      {
        path: "package/kit/onboard/runtime/scripts/onboard.py",
        pathMatches: 0,
        payloadMatches: 2,
      },
    ]);
  });

  it("Scenario: 重复成员、不安全段或原始载荷泄漏的 tarball 不能成为 RC 候选", async () => {
    const root = await candidateTemporaryRoot();
    const evidenceRoot = join(root, "candidate-evidence");
    const packedRoot = join(root, "packed-package");
    await mkdir(packedRoot, { recursive: true });
    const marker = "CoDeX-shadowed-cli-marker";
    const candidates = [
      {
        name: "duplicate.tgz",
        code: "CANDIDATE_TARBALL_INVALID",
        bytes: buildTarGz([
          {
            name: "package/kit/AGENTS.global.md",
            payload: Buffer.from("first\n", "utf8"),
          },
          {
            name: "package/kit/AGENTS.global.md",
            payload: Buffer.from("second\n", "utf8"),
          },
        ]),
      },
      {
        name: "unsafe.tgz",
        code: "CANDIDATE_TARBALL_INVALID",
        bytes: buildTarGz([
          {
            name: "package/../escape.md",
            payload: Buffer.from("x\n", "utf8"),
          },
        ]),
      },
      {
        name: "leaking.tgz",
        code: "OMP_DISTRIBUTION_LEAKAGE",
        bytes: buildTarGz([
          { name: "package", typeflag: "5" },
          {
            name: "package/kit/docs/README.md",
            payload: Buffer.from(`prefix ${marker} suffix\n`, "utf8"),
          },
        ]),
      },
    ] as const;

    for (const candidate of candidates) {
      const tarball = join(root, candidate.name);
      await writeFile(tarball, candidate.bytes);
      const result = await runP0Cli(
        [
          "record-candidate",
          "--packed",
          packedRoot,
          "--tarball",
          tarball,
          "--dist-tag",
          "next",
          "--created-at",
          "2026-08-04T00:00:00.000Z",
        ],
        evidenceRoot,
      );
      expect(result.exitCode).toBe(1);
      expect(JSON.parse(result.stderr)).toMatchObject({
        code: candidate.code,
      });
      expect(result.stderr).not.toContain(marker);
    }
    await expect(
      readdir(join(evidenceRoot, "candidates")),
    ).rejects.toMatchObject({ code: "ENOENT" });
  }, 60_000);

  it("Scenario: 发布校验器以原始归档成员扫描实际 tarball 并与解包内容一致", async () => {
    const root = await temporaryRoot();
    const packedDestination = join(root, "packed");
    const extractedRoot = join(root, "extracted");
    await mkdir(packedDestination, { recursive: true });
    await mkdir(extractedRoot, { recursive: true });
    const { stdout } = await runProcess(
      packageManager,
      ["pack", "--pack-destination", packedDestination, "--json"],
      { cwd: pluginRoot },
    );
    const packed = JSON.parse(stdout) as { filename: string };
    const tarball = isAbsolute(packed.filename)
      ? packed.filename
      : resolve(packedDestination, packed.filename);
    await runProcess("tar", ["-xzf", tarball, "-C", extractedRoot]);

    const tarballBytes = await readFile(tarball);
    const inspection = inspectPackedPluginTarball(tarballBytes);
    expect(inspection.leaks).toEqual([]);
    const memberFiles = inspection.members.filter(
      (member) => member.kind === "file",
    );
    expect(memberFiles.length).toBeGreaterThan(50);
    for (const member of memberFiles) {
      const extracted = await readFile(join(extractedRoot, member.path));
      expect(member.sha256).toBe(
        createHash("sha256").update(extracted).digest("hex"),
      );
    }
    // Every regular member payload was scanned, including entries an
    // extraction-based scanner would silently overwrite or skip.
    expect(
      inspection.members.some(
        (member) => member.path === "package/package.json",
      ),
    ).toBe(true);
    // The packed tarball must ship the canonical Onboard runtime member, and
    // its digest must be exactly the one the embedded Kit manifest declares.
    const embeddedManifest = JSON.parse(
      await readFile(join(pluginRoot, "kit", "manifest.json"), "utf8"),
    ) as { assets: Record<string, string> };
    const approvedRuntimeDigest =
      embeddedManifest.assets["onboard/runtime/scripts/onboard.py"];
    expect(approvedRuntimeDigest).toMatch(/^[0-9a-f]{64}$/);
    const canonicalMember = inspection.members.find(
      (member) =>
        member.path === "package/kit/onboard/runtime/scripts/onboard.py",
    );
    expect(canonicalMember).toMatchObject({ kind: "file" });
    expect(canonicalMember?.sha256).toBe(approvedRuntimeDigest);
    expect(
      inspection.members.every(
        (member) =>
          member.path === "package" || member.path.startsWith("package/"),
      ),
    ).toBe(true);
  }, 120_000);
});
