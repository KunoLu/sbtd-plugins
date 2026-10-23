import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import {
  mkdir,
  mkdtemp,
  readFile,
  realpath,
  stat,
  writeFile,
} from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { stripVTControlCharacters } from "node:util";

// Build and pnpm pack first; pass the resulting tarball, never a source directory.
const packageRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const executable = join(packageRoot, "node_modules/.bin/omp");
const tarball = resolve(process.argv[2] ?? "");
assert(
  process.argv[2]?.endsWith(".tgz"),
  "Usage: node row-c-install-smoke.mjs <packed.tgz>",
);
assert((await stat(tarball)).isFile());
const root = await mkdtemp("/tmp/row-c-install-smoke-");
const home = join(root, "home");
const project = join(root, "project");
const agent = join(home, ".omp/agent");
await mkdir(agent, { recursive: true });
await mkdir(project);
await mkdir(join(root, "run"), { mode: 0o700 });
await writeFile(
  join(agent, "config.yml"),
  "disabledProviders:\n  - ollama\n  - llama.cpp\n  - lm-studio\nstartup:\n  setupWizard: false\n  showSplash: false\n",
);
// No inherited provider credentials, config, NODE_OPTIONS, or model selection.
const env = {
  HOME: home,
  PATH: `${dirname(executable)}:/usr/local/bin:/usr/bin:/bin`,
  XDG_CACHE_HOME: join(home, ".cache"),
  XDG_CONFIG_HOME: join(home, ".config"),
  XDG_DATA_HOME: join(home, ".local/share"),
  XDG_STATE_HOME: join(home, ".local/state"),
  XDG_RUNTIME_DIR: join(root, "run"),
  PI_CODING_AGENT_DIR: agent,
  AGENT_SKILLS_DIR: join(home, "skills"),
  TMPDIR: root,
  TERM: "xterm-256color",
  DO_NOT_TRACK: "1",
  PYTHONDONTWRITEBYTECODE: "1",
};
const commands = [];
let host;
let socket;
let output = "";
const result = { status: "failed", executable, tarball, root, commands };
console.log(JSON.stringify({ executable, tarball, root }));

async function run(args) {
  const command = spawnSync(executable, args, {
    cwd: project,
    env,
    encoding: "utf8",
    timeout: 180_000,
    maxBuffer: 8_000_000,
  });
  const evidence = {
    args,
    exitCode: command.status,
    stdout: command.stdout,
    stderr: command.stderr,
  };
  commands.push(evidence);
  await writeFile(
    join(root, "commands.json"),
    `${JSON.stringify(commands, null, 2)}\n`,
  );
  console.log(JSON.stringify(evidence));
  assert.equal(command.status, 0, command.error?.message ?? command.stderr);
  return command.stdout;
}

async function until(read, label) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const value = read();
    if (value) return value;
    assert(host?.exitCode == null, `Host exited while waiting for ${label}`);
    await delay(50);
  }
  throw new Error(
    `Timed out waiting for ${label}; inspect ${root}/host-output.txt`,
  );
}

function screen() {
  return stripVTControlCharacters(output);
}

try {
  result.version = (await run(["--version"])).trim();
  assert.equal(result.version, "omp/18.11.1");
  await run(["plugin", "--help"]);
  // 18.11.1 routes bare local paths to directory linking. The named npm spec
  // installs the actual archive through PluginManager.install / bun install.
  await run(["plugin", "install", `@kunolu/omp-sbtd@file:${tarball}`]);
  result.list = JSON.parse(await run(["plugin", "list", "--json"]));
  result.doctor = JSON.parse(await run(["plugin", "doctor", "--json"]));
  const installed = result.list.npm.find(
    (item) => item.name === "@kunolu/omp-sbtd",
  );
  assert(installed?.enabled);
  assert.deepEqual(installed.manifest.extensions, ["./dist/extension.js"]);
  assert(installed.path.startsWith(`${home}/`));
  assert.equal(
    await realpath(installed.path),
    installed.path,
    "Installed package must not link to source",
  );
  assert(result.doctor.length > 0);
  assert(result.doctor.every((check) => check.status === "ok"));
  const installedManifest = JSON.parse(
    await readFile(join(installed.path, "package.json"), "utf8"),
  );
  assert.deepEqual(installedManifest.omp.extensions, ["./dist/extension.js"]);
  result.installedDependencies = JSON.parse(
    await readFile(join(home, ".omp/plugins/package.json"), "utf8"),
  ).dependencies;
  result.zodVersion = JSON.parse(
    await readFile(
      join(home, ".omp/plugins/node_modules/zod/package.json"),
      "utf8",
    ),
  ).version;
  assert.equal(result.zodVersion, "4.1.12");
  // Bun may resolve the broad peer range to a newer package. Record that
  // dependency separately; it is never the executable used for this smoke.
  result.installerPeerVersion = JSON.parse(
    await readFile(
      join(
        home,
        ".omp/plugins/node_modules/@oh-my-pi/pi-coding-agent/package.json",
      ),
      "utf8",
    ),
  ).version;

  // Native debugger introspection only: no observer extension, preload, plugin
  // import, API proxy, or host patch. These two source anchors belong to 18.11.1.
  // list/doctor and the capability dashboard do not expose runtime handler Maps.
  const cli = await realpath(
    join(packageRoot, "node_modules/@oh-my-pi/pi-coding-agent/dist/cli.js"),
  );
  const source = await readFile(cli, "utf8");
  const marker = "`Failed to load extension ${";
  assert.equal(
    source.split(marker).length,
    2,
    "Native load-error anchor changed",
  );
  const errorStart = source.lastIndexOf("function ", source.indexOf(marker));
  const errorHeader = source
    .slice(errorStart)
    .match(/^function \w+\((\w+)\)\{/);
  assert(errorHeader, "Native error formatter signature changed");
  const inputMarker = "async getUserInput(){";
  assert.equal(
    source.split(inputMarker).length,
    2,
    "Native input-loop anchor changed",
  );
  const inputOffset = source.indexOf(inputMarker) + inputMarker.length;

  const args = [
    executable,
    "--no-session",
    "--no-tools",
    "--no-skills",
    "--no-rules",
    "--no-lsp",
    "--no-pty",
    "--no-title",
  ];
  result.hostArgs = args;
  const quote = (value) => `'${value.replaceAll("'", "'\\''")}'`;
  // RPC refuses no-model startup. PTY interactive mode permits it; the debugger
  // waits before startup, so the actual loader errors array cannot be missed.
  host = spawn(
    "/usr/bin/script",
    [
      "--quiet",
      "--return",
      "--command",
      args.map(quote).join(" "),
      "/dev/null",
    ],
    {
      cwd: project,
      env: { ...env, BUN_OPTIONS: "--inspect-wait=127.0.0.1:0/rowc" },
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 120_000,
    },
  );
  let hostError;
  host.on("error", (error) => {
    hostError = error;
  });
  const capture = (chunk) => {
    output += chunk.toString();
  };
  host.stdout.on("data", capture);
  host.stderr.on("data", capture);
  const endpoint = await until(
    () => output.match(/ws:\/\/127\.0\.0\.1:\d+\/rowc/)?.[0],
    "loopback inspector",
  );
  assert.ifError(hostError);
  socket = new WebSocket(endpoint);
  const pending = new Map();
  const pauses = [];
  let sequence = 0;
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) {
      const entry = pending.get(message.id);
      if (!entry) return;
      pending.delete(message.id);
      clearTimeout(entry.timer);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
      else entry.resolve(message.result);
    } else if (message.method === "Debugger.paused")
      pauses.push(message.params);
  });
  await until(
    () => socket.readyState === WebSocket.OPEN,
    "inspector connection",
  );
  const rpc = (method, params = {}) =>
    new Promise((resolveReply, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`Inspector timeout: ${method}`));
      }, 10_000);
      pending.set(id, { resolve: resolveReply, reject, timer });
      socket.send(JSON.stringify({ id, method, params }));
    });
  const breakpoint = async (offset) => {
    const prefix = source.slice(0, offset);
    return rpc("Debugger.setBreakpointByUrl", {
      url: cli,
      lineNumber: prefix.split("\n").length - 1,
      columnNumber: prefix.length - prefix.lastIndexOf("\n") - 1,
    });
  };
  const inspect = async (expression) => {
    const pause = await until(
      () => pauses.shift(),
      "native debugger breakpoint",
    );
    const reply = await rpc("Debugger.evaluateOnCallFrame", {
      callFrameId: pause.callFrames[0].callFrameId,
      expression: `JSON.stringify(${expression})`,
      returnByValue: true,
    });
    assert.equal(reply.wasThrown, false, JSON.stringify(reply));
    return JSON.parse(reply.result.value);
  };
  await rpc("Inspector.enable");
  await rpc("Runtime.enable");
  await rpc("Debugger.enable");
  await rpc("Debugger.setBreakpointsActive", { active: true });
  const errorBreakpoint = await breakpoint(errorStart + errorHeader[0].length);
  const inputBreakpoint = await breakpoint(inputOffset);
  await rpc("Inspector.initialized");
  result.extensionErrors = await inspect(errorHeader[1]);
  assert.deepEqual(result.extensionErrors, []);
  await rpc("Debugger.removeBreakpoint", {
    breakpointId: errorBreakpoint.breakpointId,
  });
  await rpc("Debugger.resume");
  result.runtime = await inspect(`(() => {
    const session = this.session;
    return {
      hostEntry: Bun.main,
      model: session.model ?? null,
      tools: session.getAllToolInfos().filter(tool => tool.name === "sbtd_workflow"),
      extensions: session.extensionRunner.getLoadedExtensions().map(extension => ({
        path: extension.resolvedPath,
        hooks: [...extension.handlers.keys()],
        commands: [...extension.commands.keys()],
        tools: [...extension.tools.keys()]
      }))
    };
  })()`);
  assert.equal(result.runtime.model, null);
  assert.equal(await realpath(result.runtime.hostEntry), cli);
  const extensionPath = join(installed.path, "dist/extension.js");
  const extensions = result.runtime.extensions.filter(
    (item) => item.path === extensionPath,
  );
  assert.equal(extensions.length, 1);
  const extension = extensions[0];
  assert.deepEqual(extension.commands, ["sbtd"]);
  assert.deepEqual(extension.tools, ["sbtd_workflow"]);
  assert.equal(extension.hooks.length, 14);
  assert(
    extension.hooks.includes("session_start") &&
      extension.hooks.includes("tool_call"),
  );
  assert.equal(result.runtime.tools.length, 1);
  assert.equal(result.runtime.tools[0].sourceInfo.path, extensionPath);
  await rpc("Debugger.removeBreakpoint", {
    breakpointId: inputBreakpoint.breakpointId,
  });
  await rpc("Debugger.resume");
  await until(() => screen().includes("no-model"), "no-model TUI");
  host.stdin.write("/tools\r");
  await until(
    () =>
      screen().includes("Available Tools") &&
      screen().includes("sbtd_workflow"),
    "native tool listing",
  );
  host.stdin.write("\x1b");
  await delay(200);
  host.stdin.write("/sbtd onboard plan\r");
  await until(
    () =>
      screen().includes(
        '"confirmation": "required per approval class for Apply"',
      ),
    "onboard plan",
  );
  const confirmationStart = output.length;
  host.stdin.write("/sbtd onboard init-projects\r");
  await until(() => {
    const text = stripVTControlCharacters(output.slice(confirmationStart));
    return (
      text.includes("Apply SBTD Onboard Plan") &&
      text.includes("2 managed AGENTS targets") &&
      text.includes("inspected or modified?")
    );
  }, "project-files confirmation");
  result.confirmation =
    "Apply SBTD Onboard Plan: 2 managed AGENTS targets; global Skills not inspected or modified";
  host.stdin.write("\r");
  await until(
    () => screen().includes("Composite Onboard applied (agents: applied"),
    "onboard apply",
  );
  result.artifacts = ["AGENTS.md", ".omp/AGENTS.md"];
  for (const artifact of result.artifacts) {
    assert((await readFile(join(project, artifact), "utf8")).includes("sbtd"));
  }
  host.stdin.write("/exit\r");
  await until(() => host.exitCode !== null, "host exit");
  assert.equal(host.exitCode, 0);
  result.status = "passed";
} catch (error) {
  result.error = String(error);
  process.exitCode = 1;
} finally {
  socket?.close();
  if (host && host.exitCode === null) {
    host.kill("SIGTERM");
    await delay(500);
  }
  await writeFile(join(root, "host-output.txt"), output);
  await writeFile(
    join(root, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
  );
  console.log(JSON.stringify(result, null, 2));
}
