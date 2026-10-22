import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const executable = join(packageRoot, "node_modules/.bin/omp");
const metadata = JSON.parse(
  await readFile(
    join(packageRoot, "node_modules/@oh-my-pi/pi-coding-agent/package.json"),
    "utf8",
  ),
);
assert.equal(metadata.version, "18.11.1");
const root = await mkdtemp(join(tmpdir(), "row-c-omp-18.11.1-"));
const home = join(root, "home");
const project = join(root, "project");
const agent = join(home, ".omp/agent");
await mkdir(agent, { recursive: true });
await mkdir(project);
await writeFile(
  join(agent, "config.yml"),
  "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\n",
);
const resultPath = join(root, "result.json");
const env = {
  HOME: home,
  PATH: `${dirname(executable)}:/usr/local/bin:/usr/bin:/bin`,
  XDG_CACHE_HOME: join(home, ".cache"),
  XDG_CONFIG_HOME: join(home, ".config"),
  XDG_DATA_HOME: join(home, ".local/share"),
  PI_CODING_AGENT_DIR: agent,
  AGENT_SKILLS_DIR: join(home, "skills"),
  ROW_C_SMOKE_RESULT: resultPath,
  ROW_C_SMOKE_PYTHON: join(root, "venv/bin/python3"),
  TERM: "xterm-256color",
  DO_NOT_TRACK: "1",
  PYTHONDONTWRITEBYTECODE: "1",
  PIP_NO_INDEX: "1",
  npm_config_offline: "true",
};
const venv = spawnSync(
  "python3",
  ["-B", "-m", "venv", "--without-pip", join(root, "venv")],
  {
    cwd: project,
    env,
    encoding: "utf8",
    timeout: 30_000,
  },
);
assert.equal(venv.status, 0, venv.stderr);
const version = spawnSync(executable, ["--version"], {
  cwd: project,
  env,
  encoding: "utf8",
  timeout: 30_000,
});
assert.equal(version.status, 0, version.stderr);
assert.equal(version.stdout.trim(), "omp/18.11.1");
console.log(
  JSON.stringify({ executable, version: version.stdout.trim(), root }),
);
const quote = (value) => `'${value.replaceAll("'", "'\\''")}'`;
const args = [
  executable,
  "--no-session",
  "--no-tools",
  "--no-skills",
  "--no-rules",
  "--no-extensions",
  "--no-lsp",
  "--no-pty",
  "--no-title",
  "--extension",
  join(packageRoot, "scripts/p0/host-event/row-c-smoke-extension.mjs"),
];
// RPC startup requires a model. A real PTY permits the credential-free interactive
// host; the companion runs only deterministic commands at session_start, then exits.
const host = spawnSync(
  "/usr/bin/script",
  ["--quiet", "--return", "--command", args.map(quote).join(" "), "/dev/null"],
  {
    cwd: project,
    env,
    encoding: "utf8",
    timeout: 120_000,
    maxBuffer: 8_000_000,
  },
);
await writeFile(
  join(root, "host-output.txt"),
  `${host.stdout ?? ""}\n${host.stderr ?? ""}`,
);
const result = JSON.parse(
  await readFile(resultPath, "utf8").catch(() =>
    JSON.stringify({
      status: "failed",
      error: `No result; inspect ${root}/host-output.txt`,
      exitCode: host.status,
    }),
  ),
);
console.log(JSON.stringify(result, null, 2));
assert.equal(host.status, 0, host.error?.message ?? result.error);
assert.equal(result.status, "passed", result.error);
