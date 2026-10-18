import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { apply, inject, name, SBTD_LESSONS_TOOL_NAME } from "../dist/index.js";
import {
  createLessonsTool,
  LESSON_EVENTS,
  LESSON_INTENTS,
  modelSchemaForbidsTrustHandles,
  pickLessonsInput,
  sbtdLessons,
} from "../dist/tools/lessons.js";

function fixtureRoot(label) {
  return mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-" + label + "-"));
}

function loadPlugin(host = {}) {
  const tools = [];
  apply({
    systemPrompt: { section() {} },
    tools: {
      register(definition) {
        tools.push(definition);
      },
    },
    on() {},
    ...host,
  });
  return { tools };
}

/** Identity is host-planted .sbtd/developer (name=<name>); the plugin never writes it. */
function plantDeveloper(root, name = "test") {
  mkdirSync(join(root, ".sbtd"), { recursive: true });
  writeFileSync(join(root, ".sbtd", "developer"), `name=${name}\n`, "utf8");
}

function layeredIndexPath(root) {
  return join(root, "docs", "lessons", "index.md");
}

function layeredTopicPath(root, topic) {
  return join(root, "docs", "lessons", "topics", `${topic}.md`);
}

/** Existing layered store (docs/lessons/{index.md,topics/}) with optional content. */
function plantLayeredStore(
  root,
  indexContent = `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
`,
) {
  mkdirSync(join(root, "docs", "lessons", "topics"), { recursive: true });
  writeFileSync(layeredIndexPath(root), indexContent, "utf8");
}

/** Read-only legacy flat store (v1 artifact): docs/lessons.md. */
function plantLegacyFlat(root, content) {
  mkdirSync(join(root, "docs"), { recursive: true });
  writeFileSync(join(root, "docs", "lessons.md"), content, "utf8");
}

/** Read-only legacy Trellis tree: .trellis/lessons/{index.md,topics/}. */
function plantLegacyTrellis(root, indexContent, topicContent) {
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    indexContent,
    "utf8",
  );
  if (topicContent != null) {
    writeFileSync(
      join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
      topicContent,
      "utf8",
    );
  }
}

const LEGACY_TRELLIS_INDEX = `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix | when fail | indexed only | topics/bug-fix.md#LESSON-20260101-bug-fix |
`;

const LEGACY_TRELLIS_TOPIC = `# bug-fix

## LESSON-20260101-bug-fix

**event:** bug-fix
**summary:** indexed only
`;

test("apply registers sbtd_lessons after sbtd_e2e (Q2A)", () => {
  const { tools } = loadPlugin();
  assert.equal(name, "dsh-sbtd");
  assert.deepEqual([...inject], ["tools", "systemPrompt", "commands"]);
  assert.equal(tools.length, 9);
  assert.equal(tools[7].name, "sbtd_e2e");
  assert.equal(tools[8].name, SBTD_LESSONS_TOOL_NAME);
});

test("Q4A: model schema forbids cwd/mcp/runRefresh/serverName/toolNames", () => {
  const tool = createLessonsTool();
  assert.equal(tool.name, SBTD_LESSONS_TOOL_NAME);
  assert.equal(modelSchemaForbidsTrustHandles(tool.parameters), true);
  const props = tool.parameters.properties;
  assert.deepEqual(Object.keys(props).sort(), [
    "event",
    "intent",
    "summary",
    "tags",
    "topic",
  ]);
  assert.deepEqual(tool.parameters.required, ["intent"]);
  assert.equal(tool.parameters.additionalProperties, false);
  assert.deepEqual(props.intent.enum, [...LESSON_INTENTS]);
  assert.deepEqual(props.event.enum, [...LESSON_EVENTS]);
});

test("Q4A: pickLessonsInput rejects T10 trust keys", () => {
  for (const key of ["cwd", "mcp", "runRefresh", "serverName", "toolNames"]) {
    assert.throws(
      () => pickLessonsInput({ intent: "record", event: "bug-fix", [key]: "x" }),
      /forbids trust handle/,
    );
  }
});

test("Q1A: ordinary/unknown record => skipped; no file", () => {
  const root = fixtureRoot("ordinary");
  const before = readdirSync(root, { recursive: true }).length;

  const missing = sbtdLessons("s1", { intent: "record" }, { cwd: root });
  assert.equal(missing.ok, false);
  assert.equal(missing.status, "skipped");
  assert.equal(missing.kind, "ordinary-or-unknown");

  const unknown = sbtdLessons(
    "s1",
    { intent: "record", event: "daily-note" },
    { cwd: root },
  );
  assert.equal(unknown.ok, false);
  assert.equal(unknown.status, "skipped");
  assert.equal(unknown.kind, "ordinary-or-unknown");

  const after = readdirSync(root, { recursive: true }).length;
  assert.equal(after, before);
  assert.equal(existsSync(join(root, "docs")), false);
  assert.equal(existsSync(join(root, ".sbtd")), false);
});

test("Q4A: absolute topic on record => skipped; no write", () => {
  const root = fixtureRoot("abs-topic");
  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", topic: "/etc/passwd" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "unsafe-path");
  assert.equal(existsSync(join(root, "docs")), false);
});

test("security: invalid index topic cannot read outside lessons root", () => {
  const root = fixtureRoot("index-traversal");
  writeFileSync(join(root, "OUTSIDE_SECRET.md"), "LEAKED\n", "utf8");
  plantLayeredStore(
    root,
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-evil | bug-fix | when | stolen summary | ../../../OUTSIDE_SECRET.md |
| LESSON-20260101-good | bug-fix | when | safe summary | topics/bug-fix.md#LESSON-20260101-good |
`,
  );
  writeFileSync(
    layeredTopicPath(root, "bug-fix"),
    `# bug-fix

## LESSON-20260101-good

**event:** bug-fix
**summary:** safe summary
`,
    "utf8",
  );

  const matchEvil = sbtdLessons(
    "s1",
    { intent: "match", summary: "stolen" },
    { cwd: root },
  );
  assert.equal(matchEvil.status, "not-found");
  assert.deepEqual(matchEvil.hits, []);

  const readEvil = sbtdLessons(
    "s1",
    { intent: "read", summary: "stolen" },
    { cwd: root },
  );
  assert.equal(readEvil.status, "not-found");
  assert.deepEqual(readEvil.hits, []);

  const readGood = sbtdLessons(
    "s1",
    { intent: "read", event: "bug-fix", summary: "safe" },
    { cwd: root },
  );
  assert.equal(readGood.status, "read");
  assert.equal(readGood.hits.length, 1);
  assert.match(readGood.hits[0].body ?? "", /safe summary/);
  assert.doesNotMatch(readGood.hits[0].body ?? "", /LEAKED/);
});

test("Q3A: five-event record with nothing present creates docs/lessons/ layered", () => {
  const root = fixtureRoot("layered-five");
  plantDeveloper(root);

  for (const event of LESSON_EVENTS) {
    const result = sbtdLessons(
      "s1",
      {
        intent: "record",
        event,
        summary: `summary for ${event}`,
        tags: [event],
      },
      { cwd: root },
    );
    assert.equal(result.ok, true, event);
    assert.equal(result.status, "recorded");
    assert.equal(result.store, "docs");
  }

  assert.ok(existsSync(layeredIndexPath(root)));
  for (const event of LESSON_EVENTS) {
    assert.ok(existsSync(layeredTopicPath(root, event)), event);
  }
  // Flat legacy file and short-entry file are never created by the plugin.
  assert.equal(existsSync(join(root, "docs", "lessons.md")), false);
  assert.equal(existsSync(join(root, "docs", "spec", "lessons.md")), false);
  assert.equal(existsSync(join(root, ".trellis")), false);
});

test("Q3A: existing docs/lessons/index.md keeps the layered store", () => {
  const root = fixtureRoot("docs-layered");
  plantLayeredStore(root);
  plantDeveloper(root);

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "tool-misjudge", summary: "wrong gate" },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.store, "docs");
  assert.ok(existsSync(layeredTopicPath(root, "tool-misjudge")));
  assert.match(readFileSync(layeredIndexPath(root), "utf8"), /tool-misjudge/);
});

test("Q3A: existing docs/spec/lessons.md short entry gets appended (never created)", () => {
  const root = fixtureRoot("docs-short");
  mkdirSync(join(root, "docs", "spec"), { recursive: true });
  const shortPath = join(root, "docs", "spec", "lessons.md");
  writeFileSync(shortPath, "# Lessons\n\n", "utf8");
  plantDeveloper(root, "alice");

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "validation-fail", summary: "flaky gate" },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.status, "recorded");
  assert.equal(result.store, "docs");
  assert.equal(result.path, shortPath);

  const body = readFileSync(shortPath, "utf8");
  assert.match(body, /<!-- lessons:alice:start -->/);
  assert.match(body, /## LESSON-\d{8}-alice-validation-fail/);
  assert.match(body, /flaky gate/);
  // No layered store is created when the short file already exists.
  assert.equal(existsSync(layeredIndexPath(root)), false);
});

test("Q3A: legacy flat docs/lessons.md => record migration-skip; match/read still read", () => {
  const root = fixtureRoot("legacy-flat-skip");
  const flat = `# Lessons

## LESSON-20260101-rollback

**event:** rollback
**summary:** legacy flat entry
`;
  plantLegacyFlat(root, flat);
  plantDeveloper(root);

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "must not write" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "migration-skip");
  assert.equal(result.store, "docs");
  assert.equal(result.mutation, "none");
  assert.equal(readFileSync(join(root, "docs", "lessons.md"), "utf8"), flat);
  assert.equal(existsSync(layeredIndexPath(root)), false);

  const match = sbtdLessons(
    "s1",
    { intent: "match", event: "rollback" },
    { cwd: root },
  );
  assert.equal(match.status, "matched");
  assert.equal(match.hits.length, 1);
  assert.equal(match.hits[0].id, "LESSON-20260101-rollback");
});

test("Q3A: legacy .trellis/lessons tree => record migration-skip; match/read still read", () => {
  const root = fixtureRoot("legacy-trellis-skip");
  plantLegacyTrellis(root, LEGACY_TRELLIS_INDEX, LEGACY_TRELLIS_TOPIC);
  plantDeveloper(root);

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "must not write" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "migration-skip");
  assert.equal(result.store, "trellis");
  assert.equal(result.mutation, "none");
  assert.match(
    readFileSync(join(root, ".trellis", "lessons", "index.md"), "utf8"),
    /indexed only/,
  );
  assert.doesNotMatch(
    readFileSync(join(root, ".trellis", "lessons", "index.md"), "utf8"),
    /must not write/,
  );
  assert.equal(existsSync(join(root, "docs")), false);

  const match = sbtdLessons(
    "s1",
    { intent: "match", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(match.status, "matched");
  assert.equal(match.hits.length, 1);
  assert.equal(match.hits[0].id, "LESSON-20260101-bug-fix");

  const read = sbtdLessons(
    "s1",
    { intent: "read", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(read.status, "read");
  assert.match(read.hits[0].body ?? "", /indexed only/);
});

test("Q6A: match/read does not enumerate topics/archive (decoy ignored)", () => {
  const root = fixtureRoot("match-on-demand");
  plantLayeredStore(
    root,
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix | when fail | indexed only | topics/bug-fix.md#LESSON-20260101-bug-fix |
`,
  );
  writeFileSync(layeredTopicPath(root, "bug-fix"), LEGACY_TRELLIS_TOPIC, "utf8");
  writeFileSync(
    layeredTopicPath(root, "secret"),
    "# secret decoy\n\nnot in index\n",
    "utf8",
  );
  mkdirSync(join(root, "docs", "lessons", "archive"), { recursive: true });
  writeFileSync(
    join(root, "docs", "lessons", "archive", "old.md"),
    "# archive decoy\n",
    "utf8",
  );

  const match = sbtdLessons(
    "s1",
    { intent: "match", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(match.ok, true);
  assert.equal(match.status, "matched");
  assert.equal(match.hits.length, 1);
  assert.equal(match.hits[0].id, "LESSON-20260101-bug-fix");

  const read = sbtdLessons(
    "s1",
    { intent: "read", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(read.status, "read");
  assert.match(read.hits[0].body ?? "", /indexed only/);

  const miss = sbtdLessons(
    "s1",
    { intent: "match", event: "graft-mismatch" },
    { cwd: root },
  );
  assert.equal(miss.status, "not-found");
  assert.deepEqual(miss.hits, []);
});

test("Q6A: lessons.ts never imports readdirSync or deleted backends (no topic walk)", () => {
  const src = readFileSync(
    join(import.meta.dirname, "..", "src", "tools", "lessons.ts"),
    "utf8",
  );
  assert.doesNotMatch(src, /readdirSync/);
  assert.doesNotMatch(src, /backends\/gitnexus/);
  assert.doesNotMatch(src, /backends\/trellis/);
  assert.doesNotMatch(src, /from\s+["'].*(?:gitnexus|trellis)\.js["']/i);
});

test("graft-mismatch record writes a layered topic file", () => {
  const root = fixtureRoot("graft-event");
  plantDeveloper(root);
  const result = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "graft-mismatch",
      summary: "impact under-reported",
    },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.status, "recorded");
  assert.ok(existsSync(layeredTopicPath(root, "graft-mismatch")));
  assert.match(
    readFileSync(layeredTopicPath(root, "graft-mismatch"), "utf8"),
    /impact under-reported/,
  );
});

test("isConcurrencySafe: read/match true; record false", () => {
  const tool = createLessonsTool();
  assert.equal(tool.isConcurrencySafe({ intent: "read" }), true);
  assert.equal(tool.isConcurrencySafe({ intent: "match" }), true);
  assert.equal(tool.isConcurrencySafe({ intent: "record", event: "bug-fix" }), false);
});

test("R1: index round-trip keeps empty read_when in established column order", () => {
  const root = fixtureRoot("r1-roundtrip");
  plantDeveloper(root);

  const recorded = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "bug-fix",
      summary: "round-trip summary",
      tags: ["roundtrip"],
    },
    { cwd: root },
  );
  assert.equal(recorded.ok, true);
  assert.equal(recorded.status, "recorded");

  const indexBody = readFileSync(layeredIndexPath(root), "utf8");
  assert.match(indexBody, /\| id \| tags \| read_when \| summary \| detail \|/);
  assert.match(
    indexBody,
    /\| LESSON-[^|]+ \| bug-fix, roundtrip \| *\| round-trip summary \| topics\/bug-fix\.md#LESSON-/,
  );

  const matched = sbtdLessons(
    "s1",
    { intent: "match", tags: ["roundtrip"] },
    { cwd: root },
  );
  assert.equal(matched.status, "matched");
  assert.equal(matched.hits.length, 1);
  assert.equal(matched.hits[0].id, recorded.id);

  const readSel = sbtdLessons(
    "s1",
    { intent: "read", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(readSel.status, "read");
  assert.match(readSel.hits[0].body ?? "", /round-trip summary/);
});

test("R1/R4: existing-style index row is matchable via topics detail", () => {
  const root = fixtureRoot("r1-existing-style");
  plantLayeredStore(
    root,
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260903-dsh-sbtd | dsh-sbtd, t4 | when changing manuals | Copy only SKILL.md | topics/dsh-sbtd.md#lesson-anchor |
`,
  );
  writeFileSync(
    layeredTopicPath(root, "dsh-sbtd"),
    `# dsh-sbtd

## LESSON-20260903-dsh-sbtd

**event:** bug-fix
**summary:** Copy only SKILL.md
`,
    "utf8",
  );

  const match = sbtdLessons(
    "s1",
    { intent: "match", summary: "Copy only" },
    { cwd: root },
  );
  assert.equal(match.status, "matched");
  assert.equal(match.hits[0].topic, "dsh-sbtd");
});

test("R2: summary mentioning docs/lessons.md path is allowed on record", () => {
  const root = fixtureRoot("r2-summary-path");
  plantDeveloper(root);
  const result = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "bug-fix",
      summary: "fixed docs/lessons.md",
      tags: ["docs"],
    },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.status, "recorded");
  assert.ok(existsSync(layeredTopicPath(root, "bug-fix")));
});

test("R3: unqualified read returns index-only hits without bodies", () => {
  const root = fixtureRoot("r3-index-only-read");
  plantLayeredStore(
    root,
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix | | indexed only | topics/bug-fix.md#LESSON-20260101-bug-fix |
`,
  );
  writeFileSync(
    layeredTopicPath(root, "bug-fix"),
    `# bug-fix

## LESSON-20260101-bug-fix

**event:** bug-fix
**summary:** indexed only
**body:** DECOY-BODY-SECRET
`,
    "utf8",
  );

  const readAll = sbtdLessons("s1", { intent: "read" }, { cwd: root });
  assert.equal(readAll.status, "matched");
  assert.equal(readAll.hits.length, 1);
  assert.equal(readAll.hits[0].body, undefined);
});

test("R4: match covers tags column and read_when substring", () => {
  const root = fixtureRoot("r4-tags-readwhen");
  plantLayeredStore(
    root,
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix, gate | consult release gate docs | tag lesson | topics/bug-fix.md#LESSON-20260101-bug-fix |
`,
  );
  writeFileSync(layeredTopicPath(root, "bug-fix"), LEGACY_TRELLIS_TOPIC, "utf8");

  const byTag = sbtdLessons(
    "s1",
    { intent: "match", tags: ["gate"] },
    { cwd: root },
  );
  assert.equal(byTag.status, "matched");
  assert.equal(byTag.hits.length, 1);

  const byReadWhen = sbtdLessons(
    "s1",
    { intent: "match", tags: ["release"] },
    { cwd: root },
  );
  assert.equal(byReadWhen.status, "matched");
  assert.equal(byReadWhen.hits.length, 1);
});

test("R5: symlink docs/lessons store outside cwd refuses record", () => {
  const root = fixtureRoot("r5-symlink-store");
  plantDeveloper(root);
  const outsideDir = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-outside-"));
  const outsideLessons = join(outsideDir, "lessons");
  mkdirSync(outsideLessons, { recursive: true });
  mkdirSync(join(outsideLessons, "topics"), { recursive: true });
  writeFileSync(join(outsideLessons, "index.md"), "# Lessons index\n", "utf8");

  mkdirSync(join(root, "docs"), { recursive: true });
  const lessonsLink = join(root, "docs", "lessons");
  try {
    symlinkSync(outsideLessons, lessonsLink, "dir");
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "EPERM") {
      return;
    }
    throw err;
  }

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "symlink probe" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "unsafe-path");
  assert.doesNotMatch(
    readFileSync(join(outsideLessons, "index.md"), "utf8"),
    /symlink probe/,
  );
});

test("R4 docs-short: parseFlatSections unions event and user tags", () => {
  const root = fixtureRoot("r4-short-event-tags");
  mkdirSync(join(root, "docs", "spec"), { recursive: true });
  writeFileSync(join(root, "docs", "spec", "lessons.md"), "# Lessons\n\n", "utf8");
  plantDeveloper(root);
  const recorded = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "bug-fix",
      summary: "flat event keep",
      tags: ["custom-tag"],
    },
    { cwd: root },
  );
  assert.equal(recorded.ok, true);
  assert.equal(recorded.status, "recorded");

  const byEvent = sbtdLessons(
    "s1",
    { intent: "match", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(byEvent.status, "matched");
  assert.equal(byEvent.hits.length, 1);
  assert.equal(byEvent.hits[0].id, recorded.id);

  const byTag = sbtdLessons(
    "s1",
    { intent: "match", tags: ["custom-tag"] },
    { cwd: root },
  );
  assert.equal(byTag.status, "matched");
  assert.equal(byTag.hits.length, 1);
});

test("R5: symlink docs/lessons.md outside cwd refuses match/read", () => {
  const root = fixtureRoot("r5-symlink-flat-read");
  const outsideDir = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-outside-flat-"));
  const outsideFile = join(outsideDir, "lessons.md");
  writeFileSync(
    outsideFile,
    `# Lessons

## LESSON-20260101-bug-fix

**event:** bug-fix
**summary:** OUTSIDE-FLAT-SECRET
`,
    "utf8",
  );
  mkdirSync(join(root, "docs"), { recursive: true });
  const linkPath = join(root, "docs", "lessons.md");
  try {
    symlinkSync(outsideFile, linkPath);
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "EPERM") {
      return;
    }
    throw err;
  }

  const matchResult = sbtdLessons(
    "s1",
    { intent: "match", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(matchResult.ok, false);
  assert.equal(matchResult.status, "skipped");
  assert.equal(matchResult.kind, "unsafe-path");
  assert.doesNotMatch(JSON.stringify(matchResult), /OUTSIDE-FLAT-SECRET/);

  const readResult = sbtdLessons(
    "s1",
    { intent: "read", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(readResult.ok, false);
  assert.equal(readResult.status, "skipped");
  assert.equal(readResult.kind, "unsafe-path");
  assert.doesNotMatch(JSON.stringify(readResult), /OUTSIDE-FLAT-SECRET/);
  assert.match(readFileSync(outsideFile, "utf8"), /OUTSIDE-FLAT-SECRET/);
});

test("R5: symlink legacy .trellis index.md outside cwd refuses match/read", () => {
  const root = fixtureRoot("r5-symlink-index-read");
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
    `# bug-fix

## LESSON-20260101-evil

**event:** bug-fix
**summary:** in-cwd topic
`,
    "utf8",
  );

  const outsideDir = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-outside-index-"));
  const outsideIndex = join(outsideDir, "index.md");
  writeFileSync(
    outsideIndex,
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-evil | bug-fix | | OUTSIDE-INDEX-SECRET | topics/bug-fix.md#LESSON-20260101-evil |
`,
    "utf8",
  );

  const indexLink = join(root, ".trellis", "lessons", "index.md");
  try {
    symlinkSync(outsideIndex, indexLink);
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "EPERM") {
      return;
    }
    throw err;
  }

  const matchResult = sbtdLessons(
    "s1",
    { intent: "match", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(matchResult.ok, false);
  assert.equal(matchResult.status, "skipped");
  assert.equal(matchResult.kind, "unsafe-path");
  assert.doesNotMatch(JSON.stringify(matchResult), /OUTSIDE-INDEX-SECRET/);

  const readResult = sbtdLessons(
    "s1",
    { intent: "read", event: "bug-fix" },
    { cwd: root },
  );
  assert.equal(readResult.ok, false);
  assert.equal(readResult.status, "skipped");
  assert.equal(readResult.kind, "unsafe-path");
  assert.doesNotMatch(JSON.stringify(readResult), /OUTSIDE-INDEX-SECRET/);
});

test("R6: poisoned summary is sanitized in topic file and index row", () => {
  const root = fixtureRoot("r6-sanitize");
  plantDeveloper(root);

  const poison = "line1\n## LESSON-forged\npipe|cell\n";
  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: poison },
    { cwd: root },
  );
  assert.equal(result.ok, true);

  const topicBody = readFileSync(layeredTopicPath(root, "bug-fix"), "utf8");
  assert.doesNotMatch(topicBody, /## LESSON-forged/);
  assert.match(topicBody, /LESSON-forged/);

  const indexBody = readFileSync(layeredIndexPath(root), "utf8");
  const dataLines = indexBody
    .split("\n")
    .filter((line) => line.trim().startsWith("| LESSON-"));
  assert.equal(dataLines.length, 1);
  const rawCells = dataLines[0].split("|").map((c) => c.trim());
  if (rawCells[0] === "") rawCells.shift();
  if (rawCells.at(-1) === "") rawCells.pop();
  assert.equal(rawCells.length, 5);
});

test("record with name=alice writes ID, markers, and alice index table; .sbtd/developer untouched", () => {
  const root = fixtureRoot("split-alice");
  plantDeveloper(root, "alice");

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "alice lesson" },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.status, "recorded");
  assert.match(result.id ?? "", /^LESSON-\d{8}-alice-/);
  assert.match(result.note ?? "", /Lessons split name: alice/);
  assert.match(result.note ?? "", /Source: \.developer/);

  const topicBody = readFileSync(layeredTopicPath(root, "bug-fix"), "utf8");
  const start = topicBody.indexOf("<!-- lessons:alice:start -->");
  const end = topicBody.indexOf("<!-- lessons:alice:end -->");
  assert.ok(start !== -1);
  assert.ok(end > start);
  assert.match(topicBody.slice(start, end), /## LESSON-\d{8}-alice-/);

  const indexBody = readFileSync(layeredIndexPath(root), "utf8");
  const indexStart = indexBody.indexOf("<!-- lessons:alice:start -->");
  const indexEnd = indexBody.indexOf("<!-- lessons:alice:end -->");
  assert.ok(indexStart !== -1);
  assert.ok(indexEnd > indexStart);
  const aliceTable = indexBody.slice(indexStart, indexEnd);
  assert.match(aliceTable, /\| id \| tags \| read_when \| summary \| detail \|/);
  assert.match(aliceTable, /\| LESSON-\d{8}-alice-[^|]+ \|/);
  assert.match(indexBody, /^# Lessons index/m);

  // The plugin never writes or rewrites the identity file.
  assert.equal(
    readFileSync(join(root, ".sbtd", "developer"), "utf8"),
    "name=alice\n",
  );
});

test("missing .sbtd/developer skips record with split-name-unresolved and no write", () => {
  const root = fixtureRoot("split-missing");
  // Decoys that must never be guessed as identity.
  mkdirSync(join(root, ".trellis", "workspace", "alice"), { recursive: true });
  mkdirSync(join(root, ".sbtd"), { recursive: true });

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "no developer" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "split-name-unresolved");
  assert.equal(result.mutation, "none");
  assert.match(result.note ?? "", /Split name unresolved/);
  assert.match(result.note ?? "", /\.sbtd\/developer/);
  assert.match(result.note ?? "", /name=<name>/);
  assert.equal(existsSync(join(root, ".sbtd", "developer")), false);
  assert.equal(existsSync(join(root, "docs")), false);
});

test("non-conforming .sbtd/developer name skips invalid without write or normalize", () => {
  const root = fixtureRoot("split-invalid");
  plantDeveloper(root, "Alice");

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "should not write" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "split-name-invalid");
  assert.equal(result.mutation, "none");
  assert.match(result.note ?? "", /Alice/);
  assert.doesNotMatch(result.note ?? "", /name=alice[^<]/);
  assert.equal(existsSync(join(root, "docs")), false);
  // Identity file is never rewritten or normalized.
  assert.equal(
    readFileSync(join(root, ".sbtd", "developer"), "utf8"),
    "name=Alice\n",
  );

  const root2 = fixtureRoot("split-invalid-underscore");
  plantDeveloper(root2, "zhang_san");
  const result2 = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "underscore" },
    { cwd: root2 },
  );
  assert.equal(result2.kind, "split-name-invalid");
  assert.match(result2.note ?? "", /zhang_san/);
  assert.equal(existsSync(join(root2, "docs")), false);
});

test("P1-3: symlink .sbtd/developer outside cwd refuses record; identity never followed", () => {
  const root = fixtureRoot("p13-symlink-developer");
  const outsideDir = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-p13-outside-"));
  const outsideFile = join(outsideDir, "developer");
  writeFileSync(outsideFile, "name=outsider0\n", "utf8");
  mkdirSync(join(root, ".sbtd"), { recursive: true });
  try {
    symlinkSync(outsideFile, join(root, ".sbtd", "developer"));
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "EPERM") {
      return;
    }
    throw err;
  }

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "symlink identity probe" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "unsafe-path");
  assert.equal(result.mutation, "none");
  assert.match(result.note ?? "", /unsafe/i);
  assert.doesNotMatch(JSON.stringify(result), /outsider0/);
  assert.equal(existsSync(join(root, "docs")), false);

  // Intermediate-component symlink (.sbtd itself) escapes the root too.
  const root2 = fixtureRoot("p13-symlink-sbtd-dir");
  try {
    symlinkSync(outsideDir, join(root2, ".sbtd"), "dir");
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "EPERM") {
      return;
    }
    throw err;
  }
  const result2 = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "symlink dir probe" },
    { cwd: root2 },
  );
  assert.equal(result2.ok, false);
  assert.equal(result2.status, "skipped");
  assert.equal(result2.kind, "unsafe-path");
  assert.equal(result2.mutation, "none");
  assert.doesNotMatch(JSON.stringify(result2), /outsider0/);
  assert.equal(existsSync(join(root2, "docs")), false);
});

test("P1-3: symlink main-worktree .sbtd/developer stops fallback identity resolution", () => {
  const parent = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-p13-wt-"));
  const main = join(parent, "main");
  const linked = join(parent, "linked");
  mkdirSync(main, { recursive: true });
  const git = (args, cwd) => {
    const r = spawnSync("git", args, { cwd, encoding: "utf8" });
    if (r.error != null || r.status !== 0) return null;
    return r;
  };
  if (git(["init"], main) == null) return; // git unavailable
  if (
    git(
      ["-c", "user.email=t14@example.invalid", "-c", "user.name=t14", "commit", "--allow-empty", "-m", "init"],
      main,
    ) == null
  ) {
    return;
  }
  if (git(["worktree", "add", linked], main) == null) return;

  const outsideDir = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-p13-wt-outside-"));
  const outsideFile = join(outsideDir, "developer");
  writeFileSync(outsideFile, "name=outsider0\n", "utf8");
  mkdirSync(join(main, ".sbtd"), { recursive: true });
  try {
    symlinkSync(outsideFile, join(main, ".sbtd", "developer"));
  } catch (err) {
    if (err && typeof err === "object" && "code" in err && err.code === "EPERM") {
      return;
    }
    throw err;
  }

  // Linked worktree has no local identity; the unsafe main file must not be followed.
  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "worktree symlink probe" },
    { cwd: linked },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "unsafe-path");
  assert.equal(result.mutation, "none");
  assert.doesNotMatch(JSON.stringify(result), /outsider0/);
  assert.equal(existsSync(join(linked, "docs")), false);
});

test("second record for same name extends the same marker block", () => {
  const root = fixtureRoot("split-extend");
  plantDeveloper(root, "alice");

  const first = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "first" },
    { cwd: root },
  );
  const second = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "second" },
    { cwd: root },
  );
  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.notEqual(first.id, second.id);

  const topicBody = readFileSync(layeredTopicPath(root, "bug-fix"), "utf8");
  assert.equal(
    topicBody.split("<!-- lessons:alice:start -->").length - 1,
    1,
  );
  assert.equal(topicBody.split("<!-- lessons:alice:end -->").length - 1, 1);
  const start = topicBody.indexOf("<!-- lessons:alice:start -->");
  const end = topicBody.indexOf("<!-- lessons:alice:end -->");
  const inner = topicBody.slice(start, end);
  assert.match(inner, /first/);
  assert.match(inner, /second/);

  const indexBody = readFileSync(layeredIndexPath(root), "utf8");
  assert.equal(
    indexBody.split("<!-- lessons:alice:start -->").length - 1,
    1,
  );
  const indexInner = indexBody.slice(
    indexBody.indexOf("<!-- lessons:alice:start -->"),
    indexBody.indexOf("<!-- lessons:alice:end -->"),
  );
  assert.match(indexInner, /first/);
  assert.match(indexInner, /second/);
});

test("match/read sees lessons from another name's markers", () => {
  const root = fixtureRoot("split-unscoped-read");
  plantLayeredStore(
    root,
    `# Lessons index

<!-- lessons:bob:start -->
| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bob-bug-fix | bug-fix | | bob secret | topics/bug-fix.md#LESSON-20260101-bob-bug-fix |
<!-- lessons:bob:end -->
`,
  );
  writeFileSync(
    layeredTopicPath(root, "bug-fix"),
    `# bug-fix

<!-- lessons:bob:start -->
## LESSON-20260101-bob-bug-fix

**event:** bug-fix
**topic:** bug-fix
**summary:** bob secret
<!-- lessons:bob:end -->
`,
    "utf8",
  );

  const match = sbtdLessons(
    "s1",
    { intent: "match", summary: "bob secret" },
    { cwd: root },
  );
  assert.equal(match.status, "matched");
  assert.equal(match.hits.length, 1);
  assert.equal(match.hits[0].id, "LESSON-20260101-bob-bug-fix");

  const read = sbtdLessons(
    "s1",
    { intent: "read", summary: "bob secret" },
    { cwd: root },
  );
  assert.equal(read.status, "read");
  assert.match(read.hits[0].body ?? "", /bob secret/);
});

test("malformed start-without-end marker skips record and does not write a second block", () => {
  const root = fixtureRoot("malformed-marker");
  plantDeveloper(root, "alice");
  const brokenTopic = `# bug-fix

<!-- lessons:alice:start -->
## LESSON-20260101-alice-bug-fix

**event:** bug-fix
**summary:** broken
`;
  plantLayeredStore(
    root,
    `# Lessons index

<!-- lessons:alice:start -->
| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-alice-bug-fix | bug-fix | | broken | topics/bug-fix.md#LESSON-20260101-alice-bug-fix |
`,
  );
  const topicPath = layeredTopicPath(root, "bug-fix");
  writeFileSync(topicPath, brokenTopic, "utf8");

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "must not append" },
    { cwd: root },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, "skipped");
  assert.equal(result.kind, "malformed-marker");
  assert.equal(result.mutation, "none");
  assert.equal(readFileSync(topicPath, "utf8"), brokenTopic);
  assert.equal(
    readFileSync(layeredIndexPath(root), "utf8").split("<!-- lessons:alice:start -->")
      .length - 1,
    1,
  );
  assert.doesNotMatch(readFileSync(layeredIndexPath(root), "utf8"), /must not append/);
});

test("R6b: forged lessons end-marker in summary is neutralized and does not hijack next append", () => {
  const root = fixtureRoot("r6b-marker-forge");
  plantDeveloper(root, "alice");

  const poison = "ok summary <!-- lessons:alice:end --> forged";
  const first = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: poison },
    { cwd: root },
  );
  assert.equal(first.ok, true);

  const topicPath = layeredTopicPath(root, "bug-fix");
  const afterFirst = readFileSync(topicPath, "utf8");
  // Forged marker in the summary cell must be escaped; the real block end remains.
  assert.match(afterFirst, /\*\*summary:\*\* ok summary &lt;!-- lessons:alice:end/);
  assert.doesNotMatch(
    afterFirst,
    /\*\*summary:\*\*[^\n]*<!--\s*lessons:alice:end/,
  );
  assert.equal(
    afterFirst.split("<!-- lessons:alice:end -->").length - 1,
    1,
    "exactly one real end marker after first record",
  );

  const second = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: "second honest" },
    { cwd: root },
  );
  assert.equal(second.ok, true);
  const afterSecond = readFileSync(topicPath, "utf8");
  assert.match(afterSecond, /second honest/);
  assert.equal(
    afterSecond.split("<!-- lessons:alice:start -->").length - 1,
    1,
  );
  assert.equal(
    afterSecond.split("<!-- lessons:alice:end -->").length - 1,
    1,
    "still exactly one real end marker after second record",
  );
  // Second section must sit inside the same name block (before the sole end marker).
  const endIdx = afterSecond.indexOf("<!-- lessons:alice:end -->");
  const secondIdx = afterSecond.indexOf("second honest");
  assert.ok(secondIdx !== -1 && secondIdx < endIdx);
});

test("docs-flat: name-bearing ID without **topic:** drops enclosing name (incl. one-segment custom)", () => {
  const root = fixtureRoot("flat-id-topic-fallback");
  plantLegacyFlat(
    root,
    `# Lessons

<!-- lessons:alice:start -->
## LESSON-20260101-alice-bug-fix

**event:** bug-fix
**summary:** hyphenated topic no topic line

## LESSON-20260101-alice-refactor

**event:** bug-fix
**summary:** one-segment custom topic no topic line

<!-- lessons:alice:end -->
`,
  );

  const hyphenated = sbtdLessons(
    "s1",
    { intent: "match", topic: "bug-fix" },
    { cwd: root },
  );
  assert.equal(hyphenated.status, "matched");
  assert.equal(hyphenated.hits.length, 1);
  assert.equal(hyphenated.hits[0].id, "LESSON-20260101-alice-bug-fix");
  assert.equal(hyphenated.hits[0].topic, "bug-fix");

  const custom = sbtdLessons(
    "s1",
    { intent: "match", topic: "refactor" },
    { cwd: root },
  );
  assert.equal(custom.status, "matched");
  assert.equal(custom.hits.length, 1);
  assert.equal(custom.hits[0].id, "LESSON-20260101-alice-refactor");
  assert.equal(custom.hits[0].topic, "refactor");
});

test("docs-flat: legacy IDs without **topic:** keep full multi-hyphen slug", () => {
  const root = fixtureRoot("flat-legacy-id-topic");
  plantLegacyFlat(
    root,
    `# Lessons

<!-- lessons:alice:start -->
## LESSON-20260903-dsh-sbtd

**event:** bug-fix
**summary:** legacy two-segment

## LESSON-20260903-api-client-timeout

**event:** bug-fix
**summary:** legacy three-segment

<!-- lessons:alice:end -->
`,
  );

  const two = sbtdLessons(
    "s1",
    { intent: "match", topic: "dsh-sbtd" },
    { cwd: root },
  );
  assert.equal(two.status, "matched");
  assert.equal(two.hits[0].topic, "dsh-sbtd");

  const three = sbtdLessons(
    "s1",
    { intent: "match", topic: "api-client-timeout" },
    { cwd: root },
  );
  assert.equal(three.status, "matched");
  assert.equal(three.hits[0].id, "LESSON-20260903-api-client-timeout");
  assert.equal(three.hits[0].topic, "api-client-timeout");
});

test("docs-flat: exact heading owner survives longer legacy prefix in another block", () => {
  const root = fixtureRoot("flat-heading-prefix-collision");
  plantLegacyFlat(
    root,
    `# Lessons

<!-- lessons:bob:start -->
## LESSON-20260101-alice-refactor-extra

**event:** bug-fix
**summary:** longer legacy-looking id under bob

<!-- lessons:bob:end -->

<!-- lessons:alice:start -->
## LESSON-20260101-alice-refactor

**event:** bug-fix
**summary:** shorter new-format id under alice, no topic line

<!-- lessons:alice:end -->
`,
  );

  const match = sbtdLessons(
    "s1",
    { intent: "match", topic: "refactor" },
    { cwd: root },
  );
  assert.equal(match.status, "matched");
  assert.equal(match.hits.length, 1);
  assert.equal(match.hits[0].id, "LESSON-20260101-alice-refactor");
  assert.equal(match.hits[0].topic, "refactor");

  const read = sbtdLessons(
    "s1",
    { intent: "read", topic: "refactor" },
    { cwd: root },
  );
  assert.equal(read.status, "read");
  assert.equal(read.hits[0].id, "LESSON-20260101-alice-refactor");
  assert.equal(read.hits[0].topic, "refactor");
});

test("docs-flat: legacy slug that prefixes the enclosing name keeps full topic via **topic:**", () => {
  const root = fixtureRoot("flat-legacy-needs-topic-in-name-block");
  plantLegacyFlat(
    root,
    `# Lessons

<!-- lessons:alice:start -->
## LESSON-20260101-alice-refactor

**event:** bug-fix
**topic:** alice-refactor
**summary:** legacy full slug documented via topic line

<!-- lessons:alice:end -->
`,
  );

  const match = sbtdLessons(
    "s1",
    { intent: "match", topic: "alice-refactor" },
    { cwd: root },
  );
  assert.equal(match.status, "matched");
  assert.equal(match.hits[0].topic, "alice-refactor");
});
