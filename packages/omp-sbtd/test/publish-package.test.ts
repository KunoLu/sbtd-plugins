import { execFile } from "node:child_process";
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  realpath,
  rm,
  stat,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";

const runFile = promisify(execFile);
const workspaceRoot = new URL("../../..", import.meta.url).pathname;
const publishScript = join(workspaceRoot, "docs/deploy/publish-omp-sbtd.sh");
const temporaryRoots: string[] = [];

async function temporaryRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "kpi-omp-publish-"));
  temporaryRoots.push(root);
  return root;
}
async function createTarball(
  root: string,
  artifact: string,
  manifest: { readonly name: string; readonly version: string } = {
    name: "@kunolu/omp-sbtd",
    version: "0.1.0-rc.2",
  },
): Promise<void> {
  const contents = join(root, "contents");
  const packageRoot = join(contents, "package");
  await mkdir(packageRoot, { recursive: true });
  await writeFile(
    join(packageRoot, "package.json"),
    `${JSON.stringify(manifest)}\n`,
  );
  await runFile("tar", ["-czf", artifact, "-C", contents, "package"]);
}

async function isolatedPublishScript(root: string): Promise<string> {
  const script = join(root, "docs", "deploy", "publish-omp-sbtd.sh");
  await mkdir(join(root, "docs", "deploy"), { recursive: true });
  await writeFile(script, await readFile(publishScript, "utf8"));
  await chmod(script, 0o700);
  return script;
}

async function writeRecordingNpm(bin: string): Promise<void> {
  await mkdir(bin);
  await writeFile(
    join(bin, "npm"),
    `#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
call_log="$root/npm-called.txt"
printf '%s\\n' '---' "$@" >> "$call_log"
case $1 in
  view)
    printf '%s\\n%s\\n%s\\n%s' \
      "$PWD" \
      "\${NPM_TOKEN:-}" \
      "\${npm_config_userconfig:-}" \
      "\${npm_config_globalconfig:-}" \
      > "$root/view-context.txt"
    outcome="missing"
    if [[ -f "$root/npm-view-outcome.txt" ]]; then
      outcome=$(<"$root/npm-view-outcome.txt")
    fi
    case $outcome in
      missing)
        printf '%s\\n' 'npm ERR! code E404' >&2
        exit 1
        ;;
      occupied)
        printf '%s\\n' '"0.1.0-rc.2"'
        exit 0
        ;;
      *)
        printf '%s\\n' 'npm ERR! network unavailable' >&2
        exit 1
        ;;
    esac
    ;;
  publish)
    userconfig=""
    while [[ $# -gt 0 ]]; do
      if [[ $1 == --userconfig ]]; then
        userconfig=$2
        break
      fi
      shift
    done
    [[ -n $userconfig ]]
    printf '%s' "$userconfig" > "$root/userconfig-path.txt"
    cat "$userconfig" > "$root/userconfig-snapshot.txt"
    printf '%s' "\${NPM_TOKEN:-}" > "$root/token-capture.txt"
    ;;
  *)
    exit 1
    ;;
esac
`,
  );
  await chmod(join(bin, "npm"), 0o700);
}

async function publishAndCaptureToken(
  root: string,
  dotenvContents: string,
  inheritedToken: string,
  marker?: string,
): Promise<string> {
  const script = await isolatedPublishScript(root);
  const bin = join(root, "bin");
  const artifact = join(root, "plugin.tgz");
  const tokenCapture = join(root, "token-capture.txt");
  await writeFile(join(root, ".env"), dotenvContents);
  await writeRecordingNpm(bin);
  await createTarball(root, artifact);
  await runFile(script, [artifact], {
    env: {
      ...process.env,
      ...(marker === undefined ? {} : { MARKER: marker }),
      NPM_TOKEN: inheritedToken,
      PATH: `${bin}:${process.env.PATH ?? ""}`,
    },
  });
  return readFile(tokenCapture, "utf8");
}

async function exists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((root) => rm(root, { force: true, recursive: true })),
  );
});

describe("Scenario: 安全发布 OMP Plugin", () => {
  it.skipIf(process.platform === "win32")(
    "Scenario: 缺少 npm access token 时发布被拒绝",
    async () => {
      const root = await temporaryRoot();
      const script = await isolatedPublishScript(root);
      const callLog = join(root, "npm-called.txt");
      const artifact = join(root, "plugin.tgz");
      await writeFile(artifact, "tarball");

      const { NPM_TOKEN: _token, ...environment } = process.env;
      await expect(
        runFile(script, [artifact], {
          env: { ...environment, CALL_LOG: callLog },
        }),
      ).rejects.toMatchObject({ stderr: expect.stringContaining("NPM_TOKEN") });
      expect(await exists(callLog)).toBe(false);
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: 无效的发布输入在调用 npm 前被拒绝",
    async () => {
      const root = await temporaryRoot();
      const script = await isolatedPublishScript(root);
      const bin = join(root, "bin");
      const callLog = join(root, "npm-called.txt");
      const artifact = join(root, "plugin.tgz");
      const nonTarball = join(root, "plugin.txt");
      const validArtifact = join(root, "valid-plugin.tgz");
      await mkdir(bin);
      await writeFile(
        join(bin, "npm"),
        '#!/usr/bin/env bash\n: > "$CALL_LOG"\n',
      );
      await chmod(join(bin, "npm"), 0o700);
      await writeFile(artifact, "not a readable gzip tar archive");
      await writeFile(nonTarball, "not a tarball");
      await createTarball(root, validArtifact);

      for (const arguments_ of [
        [join(root, "missing.tgz")],
        [nonTarball],
        [artifact],
        [validArtifact, "--tag", "1invalid"],
        [validArtifact, "--tag", "latest"],
        [validArtifact, "--tag", "beta"],
      ]) {
        await expect(
          runFile(script, arguments_, {
            env: {
              ...process.env,
              CALL_LOG: callLog,
              NPM_TOKEN: "test-token",
              PATH: `${bin}:${process.env.PATH ?? ""}`,
            },
          }),
        ).rejects.toMatchObject({
          stderr: expect.stringContaining("publish-omp-sbtd:"),
        });
        expect(await exists(callLog)).toBe(false);
      }
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: stable、格式错误或其他包 tarball 在调用 npm 前被拒绝",
    async () => {
      const root = await temporaryRoot();
      const script = await isolatedPublishScript(root);
      const bin = join(root, "bin");
      const callLog = join(root, "npm-called.txt");
      const invalidArtifacts = [
        join(root, "stable.tgz"),
        join(root, "other.tgz"),
      ];
      await writeRecordingNpm(bin);
      await createTarball(root, invalidArtifacts[0], {
        name: "@kunolu/omp-sbtd",
        version: "0.1.0",
      });
      await createTarball(root, invalidArtifacts[1], {
        name: "@other/plugin",
        version: "0.1.0-rc.2",
      });
      for (const [index, version] of [
        "01.0.0-rc.1",
        "1.0.0-01",
        "1.0.0-rc..1",
        "1.0.0-rc.",
      ].entries()) {
        const artifactPath = join(root, `malformed-${index}.tgz`);
        await createTarball(root, artifactPath, {
          name: "@kunolu/omp-sbtd",
          version,
        });
        invalidArtifacts.push(artifactPath);
      }

      for (const artifactPath of invalidArtifacts) {
        await expect(
          runFile(script, [artifactPath], {
            env: {
              ...process.env,
              NPM_TOKEN: "test-token",
              PATH: `${bin}:${process.env.PATH ?? ""}`,
            },
          }),
        ).rejects.toMatchObject({
          stderr: expect.stringContaining("publish-omp-sbtd:"),
        });
        expect(await exists(callLog)).toBe(false);
      }
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: 已占用或无法确认的版本在 npm publish 前被拒绝",
    async () => {
      const root = await temporaryRoot();
      const script = await isolatedPublishScript(root);
      const bin = join(root, "bin");
      const callLog = join(root, "npm-called.txt");
      const artifact = join(root, "plugin.tgz");
      await writeRecordingNpm(bin);
      await createTarball(root, artifact);

      for (const outcome of ["occupied", "unavailable"]) {
        await writeFile(join(root, "npm-view-outcome.txt"), outcome);
        await expect(
          runFile(script, [artifact], {
            env: {
              ...process.env,
              NPM_TOKEN: "test-token",
              PATH: `${bin}:${process.env.PATH ?? ""}`,
            },
          }),
        ).rejects.toMatchObject({
          stderr: expect.stringContaining("publish-omp-sbtd:"),
        });
        const calls = await readFile(callLog, "utf8");
        expect(calls).toContain("view");
        expect(calls).not.toContain("publish");
        await rm(callLog);
      }
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: 根目录 .env 中的 NPM_TOKEN 优先于继承环境变量",
    async () => {
      const token = await publishAndCaptureToken(
        await temporaryRoot(),
        "NPM_TOKEN=dotenv-token\n",
        "environment-token",
      );

      expect(token).toBe("dotenv-token");
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: 空的 .env NPM_TOKEN 回退到继承环境变量",
    async () => {
      const token = await publishAndCaptureToken(
        await temporaryRoot(),
        "NPM_TOKEN=\n",
        "environment-token",
      );

      expect(token).toBe("environment-token");
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: .env 中的非 token 内容不会被执行",
    async () => {
      const root = await temporaryRoot();
      const marker = join(root, "dotenv-command-ran.txt");

      await publishAndCaptureToken(
        root,
        'UNRELATED=$(touch "$MARKER")\nNPM_TOKEN=dotenv-token\n',
        "environment-token",
        marker,
      );

      expect(await exists(marker)).toBe(false);
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: 根目录 .env 符号链接被拒绝",
    async () => {
      const root = await temporaryRoot();
      const script = await isolatedPublishScript(root);
      const bin = join(root, "bin");
      const callLog = join(root, "npm-called.txt");
      const artifact = join(root, "plugin.tgz");
      const externalDotenv = join(root, "external.env");
      await mkdir(bin);
      await writeFile(
        join(bin, "npm"),
        '#!/usr/bin/env bash\n: > "$CALL_LOG"\n',
      );
      await chmod(join(bin, "npm"), 0o700);
      await writeFile(externalDotenv, "NPM_TOKEN=dotenv-token\n");
      await symlink(externalDotenv, join(root, ".env"));
      await createTarball(root, artifact);

      await expect(
        runFile(script, [artifact], {
          env: {
            ...process.env,
            CALL_LOG: callLog,
            NPM_TOKEN: "environment-token",
            PATH: `${bin}:${process.env.PATH ?? ""}`,
          },
        }),
      ).rejects.toMatchObject({
        stderr: expect.stringContaining("must not be a symbolic link"),
      });
      expect(await exists(callLog)).toBe(false);
    },
  );

  it.skipIf(process.platform === "win32")(
    "Scenario: 使用环境变量发布新的 tarball",
    async () => {
      const root = await temporaryRoot();
      const script = await isolatedPublishScript(root);
      const bin = join(root, "bin");
      const callLog = join(root, "npm-called.txt");
      const userconfigPath = join(root, "userconfig-path.txt");
      const userconfigSnapshot = join(root, "userconfig-snapshot.txt");
      const tokenCapture = join(root, "token-capture.txt");
      const viewContext = join(root, "view-context.txt");
      const artifact = join(root, "kunolu-omp-sbtd-0.1.0-rc.2.tgz");
      await createTarball(root, artifact);
      await writeRecordingNpm(bin);
      const canonicalArtifact = await realpath(artifact);
      await writeFile(
        join(root, ".npmrc"),
        "//registry.npmjs.org/:_authToken=ambient-token\n",
      );

      const { stderr, stdout } = await runFile(
        script,
        [artifact, "--tag", "next"],
        {
          env: {
            NPM_TOKEN: "test-token",
            PATH: `${bin}:${process.env.PATH ?? ""}`,
          },
        },
      );
      const npmArguments = (await readFile(callLog, "utf8"))
        .split("\n")
        .filter(Boolean);
      const userconfig = await readFile(userconfigPath, "utf8");

      expect(npmArguments).toEqual([
        "---",
        "view",
        "@kunolu/omp-sbtd@0.1.0-rc.2",
        "version",
        "--json",
        "--registry",
        "https://registry.npmjs.org/",
        "---",
        "publish",
        canonicalArtifact,
        "--tag",
        "next",
        "--access",
        "public",
        "--registry",
        "https://registry.npmjs.org/",
        "--userconfig",
        userconfig,
      ]);
      expect(await readFile(userconfigSnapshot, "utf8")).toBe(
        "//registry.npmjs.org/:_authToken=$" + "{NPM_TOKEN}\n",
      );
      expect(await exists(userconfig)).toBe(false);
      expect(await readFile(tokenCapture, "utf8")).toBe("test-token");
      const [viewCwd, viewToken, viewUserConfig, viewGlobalConfig] = (
        await readFile(viewContext, "utf8")
      ).split("\n");
      expect(viewCwd).not.toBe(root);
      expect(viewToken).toBe("");
      expect(viewUserConfig).toContain("omp-sbtd-npm");
      expect(viewGlobalConfig).toContain("omp-sbtd-npm");
      expect(`${stdout}${stderr}${npmArguments.join("\n")}`).not.toContain(
        "test-token",
      );
    },
  );
});
