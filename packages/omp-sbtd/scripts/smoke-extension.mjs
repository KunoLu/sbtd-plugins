import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readdir,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { relative, resolve } from "node:path";
import { promisify } from "node:util";
import { z } from "zod";
import extension from "../dist/extension.js";

const execFileAsync = promisify(execFile);
const root = await mkdtemp(resolve(tmpdir(), "kpi-omp-extension-smoke-"));
const agentDirectory = resolve(root, "agent");
const previousAgentDirectory = process.env.PI_CODING_AGENT_DIR;
const skillsDirectory = await mkdtemp(resolve(tmpdir(), "kpi-omp-skills-"));
const previousSkillsDirectory = process.env.AGENT_SKILLS_DIR;
process.env.AGENT_SKILLS_DIR = skillsDirectory;
const coreGateSkillNames = [
  "book-ddd-distilled-modeling",
  "book-ddia-data-design",
  "book-legacy-change-safety",
  "book-refactoring-pass",
  "book-release-readiness",
];
process.env.PI_CODING_AGENT_DIR = agentDirectory;

const snapshot = async () => {
  const entries = {};
  const walk = async (directory) => {
    for (const name of await readdir(directory).catch(() => [])) {
      const path = resolve(directory, name);
      const details = await stat(path);
      if (details.isDirectory()) await walk(path);
      else {
        const content = await readFile(path);
        entries[relative(root, path)] = createHash("sha256")
          .update(content)
          .digest("hex");
      }
    }
  };
  await walk(root);
  return entries;
};
const sameSnapshot = (left, right) =>
  JSON.stringify(left) === JSON.stringify(right);

const commands = [];
const events = new Map();
const notices = [];
const sessionEntries = [];
const confirmations = [false, ...Array(8).fill(true)];
const context = {
  cwd: root,
  ui: {
    notify(message, level) {
      notices.push({ message, level });
    },
    async confirm() {
      const answer = confirmations.shift();
      if (answer === undefined) throw new Error("unexpected confirmation");
      return answer;
    },
  },
  sessionManager: {
    getBranch() {
      return sessionEntries;
    },
  },
};

try {
  extension({
    registerCommand(name, options) {
      commands.push({ name, options });
    },
    registerTool() {},
    zod: z,
    on(event, handler) {
      events.set(event, handler);
    },
    appendEntry(type, data) {
      sessionEntries.push({ customType: type, data });
    },
    async exec(command, args, options) {
      try {
        const { stdout, stderr } = await execFileAsync(command, args, {
          cwd: options?.cwd,
        });
        return { stdout, stderr, code: 0, killed: false };
      } catch (error) {
        return {
          stdout: error.stdout || "",
          stderr: error.stderr || String(error),
          code: error.code || 1,
          killed: error.killed || false,
        };
      }
    },
  });
  if (commands.length !== 1 || commands[0]?.name !== "sbtd")
    throw new Error("compiled extension did not register /sbtd exactly once");
  if (!events.has("session_start"))
    throw new Error(
      "compiled extension did not subscribe to session lifecycle",
    );

  const command = commands[0].options.handler;
  const before = await snapshot();
  await command("help", context);
  const afterHelp = await snapshot();
  await command("report", context);
  const afterReport = await snapshot();
  await command("doctor", context);
  const afterDoctor = await snapshot();
  await command("onboard plan", context);
  const compositePlanNotice = JSON.parse(notices.at(-1)?.message ?? "{}");
  const afterPlan = await snapshot();
  await command("on", context);
  const preflightNotice = notices.at(-1)?.message;
  const afterPreflight = await snapshot();
  await command("off", context);
  const afterPreflightReset = await snapshot();
  const advisoryNotice = notices.at(-1)?.message;
  await command("onboard init", context);
  const afterCancelledInit = await snapshot();
  await command("onboard init", context);
  const afterAppliedInit = await snapshot();
  await command(
    'onboard skip plan create ui --scope project --expires 2099-01-01T00:00:00.000Z --reason "compiled smoke exemption"',
    context,
  );
  const skipPlan = JSON.parse(notices.at(-1)?.message ?? "");
  const afterSkipPlan = await snapshot();
  await command(`onboard skip apply ${skipPlan.digest}`, context);
  const activeSkipStore = JSON.parse(
    await readFile(
      resolve(agentDirectory, "kpi/provenance/accepted-skips-v1.json"),
      "utf8",
    ),
  );
  const activeSkipRecord = activeSkipStore.records
    .filter((record) => record.recordId === skipPlan.create.recordId)
    .at(-1);
  if (activeSkipRecord?.status !== "active")
    throw new Error("compiled extension did not apply its AcceptedSkip");
  await command(
    `onboard skip plan revoke ${skipPlan.create.recordId} --reason "compiled smoke recovery"`,
    context,
  );
  const revokePlan = JSON.parse(notices.at(-1)?.message ?? "");
  await command(`onboard skip apply ${revokePlan.digest}`, context);
  const revokedSkipStore = JSON.parse(
    await readFile(
      resolve(agentDirectory, "kpi/provenance/accepted-skips-v1.json"),
      "utf8",
    ),
  );
  const revokedSkipRecord = revokedSkipStore.records
    .filter((record) => record.recordId === skipPlan.create.recordId)
    .at(-1);
  if (revokedSkipRecord?.status !== "revoked")
    throw new Error("compiled extension did not revoke its AcceptedSkip");
  await Promise.all(
    coreGateSkillNames.map(async (name) => {
      const directory = resolve(skillsDirectory, name);
      await mkdir(directory, { recursive: true });
      await writeFile(resolve(directory, "SKILL.md"), `${name}\n`, "utf8");
    }),
  );
  await events.get("session_start")({ type: "session_start" }, context);
  await command("on", context);
  for (const capability of [
    "trellis",
    "gitnexus",
    "bdd-tdd",
    "ui",
    "web-mobile-e2e",
  ]) {
    await command(
      `onboard skip plan create ${capability} --scope project --expires 2099-01-01T00:00:00.000Z --reason "compiled preflight exemption"`,
      context,
    );
    const preflightSkipPlan = JSON.parse(notices.at(-1)?.message ?? "");
    await command(`onboard skip apply ${preflightSkipPlan.digest}`, context);
  }
  const afterPreflightSkipApply = await snapshot();
  await command("status", context);
  await command("off", context);

  if (
    !sameSnapshot(before, afterHelp) ||
    !sameSnapshot(before, afterDoctor) ||
    !sameSnapshot(before, afterReport) ||
    !sameSnapshot(before, afterPlan) ||
    !sameSnapshot(before, afterPreflight) ||
    !sameSnapshot(before, afterPreflightReset) ||
    !sameSnapshot(before, afterCancelledInit) ||
    !sameSnapshot(afterAppliedInit, afterSkipPlan)
  )
    throw new Error(
      "a read-only or cancelled command changed the isolated filesystem",
    );

  const changed = Object.keys(afterPreflightSkipApply).sort();
  const requiredAssets = [
    ".omp/AGENTS.md",
    "AGENTS.md",
    "agent/AGENTS.md",
    "agent/kpi/provenance/accepted-skips-v1.json",
    "agent/kpi/provenance/inventory-v1.json",
    "agent/kpi/tool-evidence-v1.json",
  ];
  const allowed = new Set(requiredAssets);
  const transactionJournal =
    /^agent\/kpi\/transactions\/[0-9a-f-]+\.journal\.json$/;
  const compositeOperationRecord =
    /^agent\/kpi\/composite\/[a-f0-9]{64}\.json$/;
  const compositeOperationRecords = changed.filter((path) =>
    compositeOperationRecord.test(path),
  );
  if (
    !requiredAssets.every((path) => changed.includes(path)) ||
    compositeOperationRecords.length !== 1 ||
    changed.some(
      (path) =>
        !allowed.has(path) &&
        !transactionJournal.test(path) &&
        !compositeOperationRecord.test(path),
    )
  )
    throw new Error(
      `confirmed Onboard wrote unexpected files: ${changed.join(", ")}`,
    );
  const expectedCompositeRecord = `agent/kpi/composite/${compositePlanNotice.digest}.json`;
  const compositeRecord = JSON.parse(
    await readFile(resolve(root, expectedCompositeRecord), "utf8"),
  );
  if (
    compositeOperationRecords[0] !== expectedCompositeRecord ||
    compositeRecord.schemaVersion !== 1 ||
    compositeRecord.planDigest !== compositePlanNotice.digest ||
    typeof compositeRecord.operationId !== "string" ||
    compositeRecord.operationId.length === 0 ||
    typeof compositeRecord.completedAt !== "string" ||
    typeof compositeRecord.bootstrapRequired !== "boolean" ||
    Object.keys(compositeRecord.participants ?? {}).length === 0
  )
    throw new Error(
      "compiled extension did not persist a composite operation record bound to the displayed plan digest",
    );
  if (
    !preflightNotice?.includes("SBTD is preflight-only") ||
    !advisoryNotice?.includes("SBTD is advisory") ||
    !notices.some(({ message }) => message.includes("confirmation")) ||
    !notices.some(({ message }) =>
      message.includes("Environment Mode is degraded"),
    ) ||
    !notices.some(({ message }) => message.includes("Effective Control State"))
  )
    throw new Error(
      `compiled extension did not complete the expected command flow: ${JSON.stringify(notices.map(({ message }) => message.split("\n")[0]))}`,
    );

  console.log(
    JSON.stringify(
      {
        status: "compiled OMP extension acceptance smoke passed",
        commands: [
          "help",
          "report",
          "on preflight",
          "off preflight",
          "onboard plan",
          "onboard init cancelled",
          "onboard init applied",
          "onboard skip plan",
          "onboard skip apply",
          "onboard skip recovery",
          "session_start",
          "on reobserve",
        ],
        changed,
      },
      null,
      2,
    ),
  );
} finally {
  if (previousSkillsDirectory === undefined)
    delete process.env.AGENT_SKILLS_DIR;
  else process.env.AGENT_SKILLS_DIR = previousSkillsDirectory;
  await rm(skillsDirectory, { force: true, recursive: true });
  if (previousAgentDirectory === undefined)
    delete process.env.PI_CODING_AGENT_DIR;
  else process.env.PI_CODING_AGENT_DIR = previousAgentDirectory;
  await rm(root, { force: true, recursive: true });
}
