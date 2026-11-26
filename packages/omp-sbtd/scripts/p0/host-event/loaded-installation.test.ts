import {
  chmod,
  cp,
  mkdir,
  mkdtemp,
  rename,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  assertLoadedInstallationUnchanged,
  snapshotLoadedInstallation,
} from "./loaded-installation.ts";

const ownedRoots: string[] = [];

afterEach(async () => {
  for (const root of ownedRoots.splice(0)) {
    await rm(root, { recursive: true, force: true });
  }
});

async function fixture() {
  const owned = await mkdtemp(join(tmpdir(), "loaded-installation-"));
  ownedRoots.push(owned);
  const root = join(owned, "installation");
  await mkdir(join(root, "node_modules", ".bin"), { recursive: true });
  await mkdir(join(root, "empty"));
  await writeFile(join(root, "package.json"), "aaaa");
  await writeFile(join(root, "node_modules", "dependency.js"), "bbbb");
  await symlink(
    "../dependency.js",
    join(root, "node_modules", ".bin", "command"),
  );
  return { owned, root };
}

async function expectDrift(result: Promise<unknown>) {
  await expect(result).rejects.toMatchObject({
    message: "LOADED_INSTALLATION_DRIFT",
  });
}

describe("loaded installation snapshot", () => {
  it("covers the sorted complete physical tree, including root, empty directories and internal links", async () => {
    const { root } = await fixture();
    const baseline = await snapshotLoadedInstallation(root);
    expect([...baseline.keys()]).toEqual([
      ".",
      "empty",
      "node_modules",
      "node_modules/.bin",
      "node_modules/.bin/command",
      "node_modules/dependency.js",
      "package.json",
    ]);
    await expect(
      assertLoadedInstallationUnchanged(root, baseline),
    ).resolves.toBeUndefined();
  });

  it("does not descend through internal directory symlinks", async () => {
    const { root } = await fixture();
    await symlink("node_modules", join(root, "alias"));
    await symlink(".", join(root, "self"));
    const baseline = await snapshotLoadedInstallation(root);
    expect(baseline.has("alias")).toBe(true);
    expect(baseline.has("alias/dependency.js")).toBe(false);
    await expect(
      assertLoadedInstallationUnchanged(root, baseline),
    ).resolves.toBeUndefined();
    await writeFile(join(root, "node_modules", "dependency.js"), "cccc");
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it.each([
    "added",
    "missing",
    "same-size edit",
    "file mode",
    "directory mode",
  ])("rejects %s", async (mutation) => {
    const { root } = await fixture();
    await chmod(join(root, "package.json"), 0o644);
    await chmod(join(root, "empty"), 0o755);
    const baseline = await snapshotLoadedInstallation(root);
    if (mutation === "added") await writeFile(join(root, ".unlisted"), "new");
    if (mutation === "missing")
      await rm(join(root, "empty"), { recursive: true });
    if (mutation === "same-size edit")
      await writeFile(join(root, "package.json"), "zzzz");
    if (mutation === "file mode")
      await chmod(join(root, "package.json"), 0o600);
    if (mutation === "directory mode") await chmod(join(root, "empty"), 0o700);
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it("rejects missing files", async () => {
    const { root } = await fixture();
    const baseline = await snapshotLoadedInstallation(root);
    await rm(join(root, "package.json"));
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it("rejects symlink retargeting even with identical target content", async () => {
    const { root } = await fixture();
    await writeFile(join(root, "node_modules", "other.js"), "bbbb");
    const baseline = await snapshotLoadedInstallation(root);
    const link = join(root, "node_modules", ".bin", "command");
    await rm(link);
    await symlink("../other.js", link);
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it("rejects a regular file replaced by an internal symlink", async () => {
    const { root } = await fixture();
    await writeFile(join(root, "same-body"), "aaaa");
    const baseline = await snapshotLoadedInstallation(root);
    await rm(join(root, "package.json"));
    await symlink("same-body", join(root, "package.json"));
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it.each([
    "dangling",
    "outside",
    "indirect outside",
  ])("rejects %s links at baseline and comparison", async (kind) => {
    const { owned, root } = await fixture();
    const baseline = await snapshotLoadedInstallation(root);
    const outside = join(owned, "installation-other");
    await mkdir(outside);
    await writeFile(join(outside, "secret"), "private");
    const link = join(root, "invalid-link");
    if (kind === "dangling") await symlink("absent", link);
    if (kind === "outside") await symlink(join(outside, "secret"), link);
    if (kind === "indirect outside") {
      await symlink(outside, join(root, "indirect"));
      await symlink("indirect/secret", link);
    }
    await expectDrift(snapshotLoadedInstallation(root));
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it.each([
    "missing",
    "replaced",
    "symlink",
    "mode",
  ])("rejects a %s root", async (kind) => {
    const { owned, root } = await fixture();
    await chmod(root, 0o755);
    const baseline = await snapshotLoadedInstallation(root);
    if (kind === "mode") {
      await chmod(root, 0o700);
    } else {
      await rename(root, join(owned, "previous"));
      if (kind === "replaced")
        await cp(join(owned, "previous"), root, {
          recursive: true,
          verbatimSymlinks: true,
        });
      if (kind === "symlink") await symlink("previous", root);
    }
    await expectDrift(assertLoadedInstallationUnchanged(root, baseline));
  });

  it("rejects a different physical root even when its tree is identical", async () => {
    const first = await fixture();
    const second = await fixture();
    const baseline = await snapshotLoadedInstallation(first.root);
    await expectDrift(assertLoadedInstallationUnchanged(second.root, baseline));
  });

  it("sanitizes filesystem failures without exposing a cause or path", async () => {
    const { root } = await fixture();
    await expect(
      snapshotLoadedInstallation(join(root, "private-missing-name")),
    ).rejects.toEqual(new Error("LOADED_INSTALLATION_DRIFT"));
    try {
      await snapshotLoadedInstallation(join(root, "private-missing-name"));
    } catch (error) {
      expect((error as Error).message).toBe("LOADED_INSTALLATION_DRIFT");
      expect((error as Error).cause).toBeUndefined();
    }
  });
});
