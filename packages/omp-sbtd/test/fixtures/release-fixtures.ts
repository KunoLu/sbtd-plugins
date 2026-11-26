import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";

const memberCounts = {
  old: 276,
  mixed: 276,
  domain: 276,
  outer: 8,
  metadata: 5,
  inventory: 1,
  "stage-package": 209,
  "old-input": 1,
} as const;

type ReleaseFixtureName = keyof typeof memberCounts;
interface FixtureMember {
  path: string;
  sha256: string;
  bytes: number;
  mode: number;
}
interface FixtureCorpus {
  schemaVersion: number;
  profiles: Record<ReleaseFixtureName, FixtureMember[]>;
  blobs: Record<string, string>;
}

let corpus: Promise<Map<ReleaseFixtureName, ReadonlyMap<string, Buffer>>> | undefined;

// Sealed input data only: never import the archived source/dist or consult live outputs.
export async function readReleaseFixture(
  name: ReleaseFixtureName,
): Promise<Map<string, Buffer>> {
  corpus ??= readFile(new URL("./release-corpus.json.gz.b64", import.meta.url)).then(
    (encoded) => {
      if (
        createHash("sha256").update(encoded).digest("hex") !==
        "23e38dacd53411390dd0065f3731a2e2659c31e9717c1fc1605f01132bf98b79"
      )
        throw new Error("Sealed release fixture corpus changed");
      const data: FixtureCorpus = JSON.parse(
        gunzipSync(Buffer.from(encoded.toString("utf8"), "base64")).toString("utf8"),
      );
      if (data.schemaVersion !== 1) throw new Error("Unknown release fixture corpus");
      const blobs = new Map<string, Buffer>();
      for (const [hash, base64] of Object.entries(data.blobs)) {
        const bytes = Buffer.from(base64, "base64");
        if (createHash("sha256").update(bytes).digest("hex") !== hash)
          throw new Error(`Sealed release fixture blob changed: ${hash}`);
        blobs.set(hash, bytes);
      }
      const profiles = new Map<ReleaseFixtureName, ReadonlyMap<string, Buffer>>();
      for (const profile of Object.keys(memberCounts) as ReleaseFixtureName[]) {
        const files = new Map<string, Buffer>();
        for (const member of data.profiles[profile]) {
          const bytes = blobs.get(member.sha256);
          if (
            bytes === undefined || bytes.length !== member.bytes || member.mode !== 0o644 ||
            files.has(member.path) || member.path.includes("\\") ||
            member.path.split("/").some((part) => part === "" || part === "." || part === "..")
          )
            throw new Error(`Invalid sealed release fixture member: ${profile}/${member.path}`);
          files.set(member.path, bytes);
        }
        if (files.size !== memberCounts[profile])
          throw new Error(`Incomplete sealed release fixture: ${profile}`);
        profiles.set(profile, files);
      }
      return profiles;
    },
  );
  const files = (await corpus).get(name);
  if (files === undefined) throw new Error(`Unknown release fixture: ${name}`);
  // Each caller owns its buffers, including coherent-claim attack mutations.
  return new Map([...files].map(([path, bytes]) => [path, Buffer.from(bytes)]));
}
