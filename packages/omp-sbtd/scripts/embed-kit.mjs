import { createHash } from "node:crypto";
import { realpathSync } from "node:fs";
import {
  cp,
  mkdtemp,
  readdir,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

function defaultSource() {
  const manifestUrl = import.meta.resolve(
    "@kunolu/sbtd-workflow-kit/generated-omp/manifest.json",
  );
  return fileURLToPath(new URL(".", manifestUrl));
}
const defaultDestination = fileURLToPath(new URL("../kit", import.meta.url));
const defaultLicense = fileURLToPath(new URL("../LICENSE", import.meta.url));
const defaultNotices = fileURLToPath(
  new URL("../THIRD_PARTY_NOTICES.md", import.meta.url),
);

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

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
        `generated Kit contains a non-regular entry: ${relative(base, path).split(sep).join("/")}`,
      );
    }
  }
  return files.sort();
}

const forbiddenToken = [0x63, 0x6f, 0x64, 0x65, 0x78];
const canonicalOnboardRuntimePath = "onboard/runtime/scripts/onboard.py";

function isCanonicalOnboardRuntime(path) {
  return path === canonicalOnboardRuntimePath;
}

function containsForbiddenToken(value) {
  const last = value.length - forbiddenToken.length;
  for (let index = 0; index <= last; index += 1) {
    let position = 0;
    while (
      position < forbiddenToken.length &&
      (value[index + position] | 0x20) === forbiddenToken[position]
    )
      position += 1;
    if (position === forbiddenToken.length) return true;
  }
  return false;
}

function assertOmpDistributionClean(leakingPaths) {
  if (leakingPaths.length > 0)
    throw new Error(
      `generated Kit contains forbidden non-OMP Runtime identifiers: ${leakingPaths.join(", ")}`,
    );
}

const hexDigest = (value, length) =>
  typeof value === "string" && new RegExp(`^[0-9a-f]{${length}}$`).test(value);

function validStableRepositories(repositories) {
  return (
    typeof repositories === "object" &&
    repositories !== null &&
    !Array.isArray(repositories) &&
    !Object.values(repositories).some(
      (repository) =>
        typeof repository !== "object" ||
        repository === null ||
        Array.isArray(repository) ||
        typeof repository.url !== "string" ||
        !hexDigest(repository.revision, 40) ||
        typeof repository.license !== "string" ||
        repository.license.length === 0,
    )
  );
}

function validStableSkills(skills) {
  return (
    typeof skills === "object" &&
    skills !== null &&
    !Array.isArray(skills) &&
    !Object.values(skills).some(
      (skill) =>
        typeof skill !== "object" ||
        skill === null ||
        Array.isArray(skill) ||
        typeof skill.repository !== "string" ||
        skill.repository.length === 0 ||
        typeof skill.sourceSubpath !== "string" ||
        skill.sourceSubpath.length === 0 ||
        typeof skill.stablePath !== "string" ||
        skill.stablePath.length === 0 ||
        !hexDigest(skill.treeSha256, 64),
    )
  );
}

function assertManifest(manifest) {
  const canonical = manifest.canonical;
  const projection = manifest.projection;
  if (
    manifest.schemaVersion !== 2 ||
    manifest.runtime !== "omp" ||
    typeof canonical !== "object" ||
    canonical === null ||
    canonical.sourceId !== "sbtd-workflow-kit-upstream" ||
    typeof canonical.canonicalSourceUri !== "string" ||
    !hexDigest(canonical.resolvedRevision, 40) ||
    !hexDigest(canonical.sourceTreeSha256, 64) ||
    typeof canonical.transformVersion !== "string" ||
    canonical.transformVersion.length === 0 ||
    !hexDigest(canonical.manifestSha256, 64) ||
    !hexDigest(canonical.generatedSha256, 64) ||
    typeof projection !== "object" ||
    projection === null ||
    projection.policyVersion !== 1 ||
    !hexDigest(projection.policySha256, 64) ||
    !hexDigest(projection.decisionsSha256, 64) ||
    !hexDigest(projection.generatedSha256, 64) ||
    typeof manifest.assets !== "object" ||
    manifest.assets === null ||
    typeof manifest.overlayDigests !== "object" ||
    manifest.overlayDigests === null
  ) {
    throw new Error("generated Kit manifest is invalid");
  }
  const provenance = manifest.retainedProvenance;
  if (
    typeof provenance !== "object" ||
    provenance === null ||
    typeof provenance.stableSet !== "string" ||
    provenance.stableSet.length === 0 ||
    !hexDigest(provenance.manifestSha256, 64) ||
    !validStableRepositories(provenance.repositories) ||
    !validStableSkills(provenance.skills)
  ) {
    throw new Error("generated Kit stable provenance is invalid");
  }
}

export function pluginNoticesFor(kitNotices) {
  const pluginNotices = kitNotices
    .replaceAll(
      "Retained license: onboard/runtime/",
      "Retained license: kit/onboard/runtime/",
    )
    .replaceAll(
      "Retained notice: onboard/runtime/",
      "Retained notice: kit/onboard/runtime/",
    );
  if (pluginNotices === kitNotices) {
    throw new Error(
      "generated Kit notices do not expose retained attribution paths",
    );
  }
  return pluginNotices;
}

export async function validateEmbeddedKit({
  source,
  destination,
  pluginLicense,
  pluginNotices,
}) {
  const [sourceFiles, embeddedFiles] = await Promise.all([
    listFiles(source),
    listFiles(destination),
  ]);
  if (sourceFiles.join("\0") !== embeddedFiles.join("\0")) {
    throw new Error("embedded Kit files differ from the generated Kit");
  }
  const manifest = JSON.parse(
    await readFile(`${destination}/manifest.json`, "utf8"),
  );
  assertManifest(manifest);
  // The canonical runtime payload is the only file allowed to carry legacy
  // non-OMP Runtime identifiers, so its manifest digest binding is mandatory
  // and verified before any exemption is granted.
  const canonicalRuntimeDigest = manifest.assets[canonicalOnboardRuntimePath];
  if (!hexDigest(canonicalRuntimeDigest, 64)) {
    throw new Error(
      "generated Kit manifest does not bind the canonical Onboard runtime asset digest",
    );
  }

  const leakingPaths = [];
  for (const path of sourceFiles) {
    const [expected, actual] = await Promise.all([
      readFile(`${source}/${path}`),
      readFile(`${destination}/${path}`),
    ]);
    if (!expected.equals(actual)) {
      throw new Error(`embedded Kit differs from generated Kit: ${path}`);
    }
    const approvedCanonicalRuntime =
      isCanonicalOnboardRuntime(path) &&
      sha256(actual) === canonicalRuntimeDigest;
    if (
      !approvedCanonicalRuntime &&
      (path.toLowerCase().includes("codex") || containsForbiddenToken(actual))
    )
      leakingPaths.push(path);
  }
  assertOmpDistributionClean(leakingPaths);

  const embeddedStableManifestBytes = await readFile(
    `${destination}/onboard/runtime/assets/external-skills/stable/MANIFEST.json`,
  );
  if (
    sha256(embeddedStableManifestBytes) !==
    manifest.retainedProvenance.manifestSha256
  ) {
    throw new Error(
      "embedded Kit stable manifest digest does not match derived provenance",
    );
  }
  const embeddedStableManifest = JSON.parse(
    embeddedStableManifestBytes.toString("utf8"),
  );
  const embeddedRepositories = embeddedStableManifest?.repositories;
  const provenanceRepositories = manifest.retainedProvenance.repositories;
  const embeddedSkills = embeddedStableManifest?.skills;
  const provenanceSkills = manifest.retainedProvenance.skills;
  if (
    !validStableRepositories(embeddedRepositories) ||
    !validStableSkills(embeddedSkills) ||
    embeddedStableManifest.stableSet !==
      manifest.retainedProvenance.stableSet ||
    Object.keys(embeddedRepositories).length !==
      Object.keys(provenanceRepositories).length ||
    Object.entries(provenanceRepositories).some(([name, repository]) => {
      const embedded = embeddedRepositories[name];
      return (
        embedded.url !== repository.url ||
        embedded.revision !== repository.revision ||
        embedded.license !== repository.license
      );
    }) ||
    Object.keys(embeddedSkills).length !==
      Object.keys(provenanceSkills).length ||
    Object.entries(provenanceSkills).some(([name, skill]) => {
      const embedded = embeddedSkills[name];
      return (
        embedded === undefined ||
        embedded.repository !== skill.repository ||
        embedded.sourceSubpath !== skill.sourceSubpath ||
        embedded.stablePath !== skill.stablePath ||
        embedded.treeSha256 !== skill.treeSha256
      );
    })
  ) {
    throw new Error(
      "embedded Kit stable provenance drifted from the embedded stable manifest",
    );
  }
  for (const [path, expectedDigest] of Object.entries(manifest.assets)) {
    if (
      typeof expectedDigest !== "string" ||
      path.startsWith("/") ||
      path.split("/").some((segment) => segment === "" || segment === "..")
    ) {
      throw new Error(
        `generated Kit manifest contains an unsafe asset: ${path}`,
      );
    }
    const content = await readFile(`${destination}/${path}`);
    if (sha256(content) !== expectedDigest) {
      throw new Error(`generated Kit asset digest mismatch: ${path}`);
    }
  }
  const generatedDigest = sha256(
    [
      ...Object.entries(manifest.assets)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([path, digest]) => `${path}\0${digest}`),
      ...Object.entries(manifest.overlayDigests)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([path, digest]) => `overlay:${path}\0${digest}`),
    ].join("\n"),
  );
  if (
    generatedDigest !== manifest.projection.generatedSha256 ||
    manifest.targets?.["AGENTS.global.md"] !==
      manifest.assets["AGENTS.global.md"] ||
    manifest.targets?.["AGENTS.project-root.md"] !==
      manifest.assets["AGENTS.project-root.md"] ||
    manifest.targets?.["AGENTS.project-omp.md"] !==
      manifest.assets["AGENTS.project-omp.md"] ||
    manifest.profileCatalogSha256 !== manifest.assets["catalog.json"]
  ) {
    throw new Error("generated Kit manifest is internally inconsistent");
  }

  const [kitLicense, actualLicense, kitNotices, actualNotices] =
    await Promise.all([
      readFile(`${destination}/LICENSE`),
      readFile(pluginLicense),
      readFile(`${destination}/THIRD_PARTY_NOTICES.md`, "utf8"),
      readFile(pluginNotices, "utf8"),
    ]);
  if (!kitLicense.equals(actualLicense)) {
    throw new Error("Plugin LICENSE differs from the embedded Kit LICENSE");
  }
  if (actualNotices !== pluginNoticesFor(kitNotices)) {
    throw new Error("Plugin notices differ from the embedded Kit notices");
  }
}

function isMissingPath(error) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

async function replaceStagedFiles(replacements, renameOperation) {
  const backedUp = [];
  const promoted = [];
  try {
    for (const replacement of replacements) {
      try {
        await renameOperation(replacement.destination, replacement.backup);
        backedUp.push(replacement);
      } catch (error) {
        if (!isMissingPath(error)) throw error;
      }
    }
    for (const replacement of replacements) {
      await renameOperation(replacement.stage, replacement.destination);
      promoted.push(replacement);
    }
  } catch (error) {
    const rollbackErrors = [];
    for (const replacement of promoted.reverse()) {
      try {
        await rm(replacement.destination, { force: true, recursive: true });
      } catch (rollbackError) {
        rollbackErrors.push(rollbackError);
      }
    }
    for (const replacement of backedUp.reverse()) {
      try {
        await renameOperation(replacement.backup, replacement.destination);
      } catch (rollbackError) {
        rollbackErrors.push(rollbackError);
      }
    }
    if (rollbackErrors.length > 0)
      throw new AggregateError(
        [error, ...rollbackErrors],
        "embedded Kit replacement failed and rollback was incomplete",
      );
    throw error;
  }
}

export async function embedKit({
  source,
  destination,
  pluginLicense,
  pluginNotices,
  renameOperation = rename,
}) {
  const stage = await mkdtemp(
    join(dirname(destination), `.${basename(destination)}.stage-`),
  );
  const replacements = [
    {
      stage,
      destination,
      backup: `${stage}.kit-backup`,
    },
    {
      stage: `${stage}.LICENSE`,
      destination: pluginLicense,
      backup: `${stage}.license-backup`,
    },
    {
      stage: `${stage}.THIRD_PARTY_NOTICES.md`,
      destination: pluginNotices,
      backup: `${stage}.notices-backup`,
    },
  ];
  let completed = false;
  try {
    await cp(source, stage, { recursive: true, errorOnExist: false });
    const kitNotices = await readFile(
      `${stage}/THIRD_PARTY_NOTICES.md`,
      "utf8",
    );
    await Promise.all([
      cp(`${stage}/LICENSE`, replacements[1].stage),
      writeFile(replacements[2].stage, pluginNoticesFor(kitNotices), "utf8"),
    ]);
    await validateEmbeddedKit({
      source,
      destination: stage,
      pluginLicense: replacements[1].stage,
      pluginNotices: replacements[2].stage,
    });
    await replaceStagedFiles(replacements, renameOperation);
    completed = true;
  } finally {
    await Promise.all([
      ...replacements.map((replacement) =>
        rm(replacement.stage, { force: true, recursive: true }),
      ),
      ...(completed
        ? replacements.map((replacement) =>
            rm(replacement.backup, { force: true, recursive: true }),
          )
        : []),
    ]);
  }
}

const source = resolve(process.env.KPI_KIT_SOURCE ?? defaultSource());
const destination = resolve(
  process.env.KPI_EMBED_DESTINATION ?? defaultDestination,
);
const pluginLicense = resolve(
  process.env.KPI_PLUGIN_LICENSE_DESTINATION ?? defaultLicense,
);
const pluginNotices = resolve(
  process.env.KPI_PLUGIN_NOTICES_DESTINATION ?? defaultNotices,
);

const invokedDirectly =
  process.argv[1] !== undefined &&
  realpathSync(resolve(process.argv[1])) ===
    realpathSync(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  if (process.env.KPI_EMBED_VERIFY_ONLY === "1") {
    await validateEmbeddedKit({
      source,
      destination,
      pluginLicense,
      pluginNotices,
    });
  } else {
    await embedKit({ source, destination, pluginLicense, pluginNotices });
  }
}
