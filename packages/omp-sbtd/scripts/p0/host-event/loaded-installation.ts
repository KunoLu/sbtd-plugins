import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, readdir, readlink, realpath } from "node:fs/promises";
import { isAbsolute, join, relative, sep } from "node:path";

/** Complete physical-tree snapshot; symlinks are recorded, never traversed. */
export async function snapshotLoadedInstallation(
  root: string,
): Promise<ReadonlyMap<string, string>> {
  try {
    const rootStat = await lstat(root, { bigint: true });
    if (!rootStat.isDirectory()) throw new Error();
    const physicalRoot = await realpath(root);
    const entries = new Map<string, string>();

    async function visit(path: string, key: string): Promise<void> {
      const stat = await lstat(path, { bigint: true });
      const mode = stat.mode.toString();
      if (stat.isSymbolicLink()) {
        const target = await realpath(path);
        const withinRoot = relative(physicalRoot, target);
        if (
          isAbsolute(withinRoot) ||
          withinRoot === ".." ||
          withinRoot.startsWith(`..${sep}`)
        ) {
          throw new Error();
        }
        entries.set(key, JSON.stringify(["link", mode, await readlink(path)]));
      } else if (stat.isDirectory()) {
        if (key === ".") {
          if (stat.dev !== rootStat.dev || stat.ino !== rootStat.ino)
            throw new Error();
          entries.set(
            key,
            JSON.stringify([
              "root",
              mode,
              physicalRoot,
              stat.dev.toString(),
              stat.ino.toString(),
            ]),
          );
        } else {
          entries.set(key, JSON.stringify(["directory", mode]));
        }
        for (const name of (await readdir(path)).sort()) {
          await visit(join(path, name), key === "." ? name : `${key}/${name}`);
        }
      } else if (stat.isFile()) {
        const file = await open(
          path,
          constants.O_RDONLY | constants.O_NOFOLLOW,
        );
        try {
          const opened = await file.stat({ bigint: true });
          if (
            !opened.isFile() ||
            opened.dev !== stat.dev ||
            opened.ino !== stat.ino ||
            opened.mode !== stat.mode
          ) {
            throw new Error();
          }
          const hash = createHash("sha256");
          for await (const chunk of file.createReadStream({ autoClose: false }))
            hash.update(chunk);
          entries.set(key, JSON.stringify(["file", mode, hash.digest("hex")]));
        } finally {
          await file.close();
        }
      } else {
        throw new Error();
      }
    }

    await visit(physicalRoot, ".");
    return entries;
  } catch {
    throw new Error("LOADED_INSTALLATION_DRIFT");
  }
}

/** Reject any missing, added, changed, unreadable or invalid installation entry. */
export async function assertLoadedInstallationUnchanged(
  root: string,
  baseline: ReadonlyMap<string, string>,
): Promise<void> {
  const current = await snapshotLoadedInstallation(root);
  if (current.size !== baseline.size)
    throw new Error("LOADED_INSTALLATION_DRIFT");
  for (const [path, value] of baseline) {
    if (current.get(path) !== value)
      throw new Error("LOADED_INSTALLATION_DRIFT");
  }
}
