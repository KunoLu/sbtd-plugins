import { createHash } from "node:crypto";
import { realpathSync } from "node:fs";
import { cp, mkdtemp, readdir, readFile, rename, rm } from "node:fs/promises";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Projects the certified Agent Plugin skills from the Workflow Kit third tree
 * (`generated-agent-plugin/skills/<name>/**`) into the Plugin root `skills/**`.
 *
 * The copy is build-owned and digest-verified against
 * `generated-agent-plugin/manifest.json`; hand edits, missing or extra
 * directories, and symbolic links fail validation. The Kit embed seam
 * (`embed-kit.mjs`) is untouched: `kit/**` keeps embedding only
 * `generated-omp/**`.
 */

function defaultSource() {
  const manifestUrl = import.meta.resolve(
    "@kunolu/sbtd-workflow-kit/generated-agent-plugin/manifest.json",
  );
  return fileURLToPath(new URL(".", manifestUrl));
}
const defaultDestination = fileURLToPath(new URL("../skills", import.meta.url));

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

const hexDigest = (value, length) =>
  typeof value === "string" && new RegExp(`^[0-9a-f]{${length}}$`).test(value);

async function listFiles(root, base = root) {
  const files = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = `${root}/${entry.name}`;
    if (entry.isDirectory()) {
      files.push(...(await listFiles(path, base)));
    } else if (entry.isFile()) {
      files.push(relative(base, path).split(sep).join("/"));
    } else {
      throw new Error(
        `Agent Plugin skills contain a non-regular entry: ${relative(base, path).split(sep).join("/")}`,
      );
    }
  }
  return files.sort();
}

function assertSafeRelativePath(path) {
  if (
    typeof path !== "string" ||
    path.startsWith("/") ||
    path.split("/").some((segment) => segment === "" || segment === "..")
  ) {
    throw new Error(
      `generated Agent Plugin manifest contains an unsafe asset path: ${path}`,
    );
  }
}

function assertSafeSkillName(name) {
  if (
    typeof name !== "string" ||
    name.length === 0 ||
    name === "." ||
    name === ".." ||
    name.includes("/") ||
    name.includes("\\")
  ) {
    throw new Error(
      `generated Agent Plugin manifest contains an unsafe certified skill name: ${name}`,
    );
  }
}

function assertAgentPluginManifest(manifest) {
  if (
    typeof manifest !== "object" ||
    manifest === null ||
    Array.isArray(manifest) ||
    manifest.schemaVersion !== 1 ||
    manifest.sourceId !== "sbtd-workflow-kit-upstream" ||
    manifest.transformVersion !== "agent-plugin-p0-v1" ||
    !hexDigest(manifest.resolvedRevision, 40) ||
    !hexDigest(manifest.sourceTreeSha256, 64) ||
    !hexDigest(manifest.auditSha256, 64) ||
    !hexDigest(manifest.catalogSha256, 64) ||
    !hexDigest(manifest.generatedSha256, 64) ||
    !Number.isInteger(manifest.candidateCount) ||
    manifest.candidateCount < 0 ||
    !Array.isArray(manifest.certified) ||
    manifest.certifiedCount !== manifest.certified.length ||
    manifest.certified.some(
      (name, index) =>
        typeof name !== "string" ||
        name.length === 0 ||
        manifest.certified.indexOf(name) !== index,
    ) ||
    !Array.isArray(manifest.excluded) ||
    manifest.excluded.some(
      (excluded) =>
        typeof excluded !== "object" ||
        excluded === null ||
        typeof excluded.name !== "string" ||
        manifest.certified.includes(excluded.name),
    ) ||
    typeof manifest.skills !== "object" ||
    manifest.skills === null ||
    Array.isArray(manifest.skills)
  ) {
    throw new Error("generated Agent Plugin manifest is invalid");
  }
  const skillNames = Object.keys(manifest.skills).sort();
  if (skillNames.join("\0") !== [...manifest.certified].sort().join("\0")) {
    throw new Error(
      "generated Agent Plugin manifest skills do not match the certified set",
    );
  }
  for (const name of manifest.certified) {
    assertSafeSkillName(name);
    const skill = manifest.skills[name];
    if (
      typeof skill !== "object" ||
      skill === null ||
      Array.isArray(skill) ||
      typeof skill.files !== "object" ||
      skill.files === null ||
      Array.isArray(skill.files) ||
      Object.keys(skill.files).length === 0
    ) {
      throw new Error(
        `generated Agent Plugin manifest skill is invalid: ${name}`,
      );
    }
    for (const [path, digest] of Object.entries(skill.files)) {
      assertSafeRelativePath(path);
      if (!hexDigest(digest, 64)) {
        throw new Error(
          `generated Agent Plugin manifest binds an invalid digest: ${name}/${path}`,
        );
      }
    }
  }
  return manifest;
}

export async function readAgentPluginManifest(source) {
  return assertAgentPluginManifest(
    JSON.parse(await readFile(`${source}/manifest.json`, "utf8")),
  );
}

export async function validateEmbeddedAgentSkills({ source, destination }) {
  const manifest = await readAgentPluginManifest(source);
  const entries = await readdir(destination, { withFileTypes: true });
  const names = entries.map((entry) => entry.name).sort();
  const expected = [...manifest.certified].sort();
  if (names.join("\0") !== expected.join("\0")) {
    throw new Error(
      `embedded Agent Plugin skills differ from the certified set: expected ${expected.join(", ")}; found ${names.join(", ")}`,
    );
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      throw new Error(
        `embedded Agent Plugin skills contain a non-directory entry: ${entry.name}`,
      );
    }
  }
  for (const name of expected) {
    const expectedFiles = manifest.skills[name].files;
    const actualFiles = await listFiles(`${destination}/${name}`);
    const expectedPaths = Object.keys(expectedFiles).sort();
    if (actualFiles.join("\0") !== expectedPaths.join("\0")) {
      throw new Error(
        `embedded Agent Plugin skill files differ from the manifest: ${name}`,
      );
    }
    for (const path of expectedPaths) {
      const [embedded, projected] = await Promise.all([
        readFile(`${destination}/${name}/${path}`),
        readFile(`${source}/skills/${name}/${path}`),
      ]);
      if (sha256(embedded) !== expectedFiles[path]) {
        throw new Error(
          `embedded Agent Plugin skill digest mismatch: ${name}/${path}`,
        );
      }
      if (!embedded.equals(projected)) {
        throw new Error(
          `embedded Agent Plugin skill differs from the certified projection: ${name}/${path}`,
        );
      }
    }
  }
}

export async function embedAgentSkills({
  source,
  destination,
  renameOperation = rename,
}) {
  const manifest = await readAgentPluginManifest(source);
  const stage = await mkdtemp(
    join(dirname(destination), `.${basename(destination)}.stage-`),
  );
  const backup = `${stage}.skills-backup`;
  let completed = false;
  let backedUp = false;
  try {
    for (const name of manifest.certified) {
      // listFiles rejects symbolic links and other non-regular entries before
      // anything is copied out of the certified source tree.
      await listFiles(`${source}/skills/${name}`);
      await cp(`${source}/skills/${name}`, `${stage}/${name}`, {
        recursive: true,
        errorOnExist: false,
      });
    }
    await validateEmbeddedAgentSkills({ source, destination: stage });
    try {
      await renameOperation(destination, backup);
      backedUp = true;
    } catch (error) {
      if (
        !(
          typeof error === "object" &&
          error !== null &&
          "code" in error &&
          error.code === "ENOENT"
        )
      )
        throw error;
    }
    try {
      await renameOperation(stage, destination);
      completed = true;
    } catch (error) {
      if (backedUp) await renameOperation(backup, destination);
      throw error;
    }
  } finally {
    await Promise.all([
      rm(stage, { force: true, recursive: true }),
      ...(completed ? [rm(backup, { force: true, recursive: true })] : []),
    ]);
  }
}

const source = resolve(process.env.KPI_AGENT_SKILLS_SOURCE ?? defaultSource());
const destination = resolve(
  process.env.KPI_AGENT_SKILLS_DESTINATION ?? defaultDestination,
);

const invokedDirectly =
  process.argv[1] !== undefined &&
  realpathSync(resolve(process.argv[1])) ===
    realpathSync(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  if (process.env.KPI_AGENT_SKILLS_VERIFY_ONLY === "1") {
    await validateEmbeddedAgentSkills({ source, destination });
  } else {
    await embedAgentSkills({ source, destination });
  }
}
