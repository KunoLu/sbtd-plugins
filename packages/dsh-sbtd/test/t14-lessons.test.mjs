import assert from "node:assert/strict";
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
import { writeArtifact } from "../dist/backends/trellis.js";
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

function trellisFixture(root) {
  mkdirSync(join(root, ".trellis"), { recursive: true });
  writeFileSync(join(root, ".trellis", "workflow.md"), "# workflow\n", "utf8");
}

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
  trellisFixture(root);
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
  assert.equal(existsSync(join(root, "lessons.md")), false);
  assert.equal(existsSync(join(root, ".trellis", "spec", "lessons.md")), false);
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
  assert.equal(existsSync(join(root, "docs", "lessons.md")), false);
});

test("security: invalid index topic cannot read outside lessons root", () => {
  const root = fixtureRoot("index-traversal");
  trellisFixture(root);
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(join(root, "OUTSIDE_SECRET.md"), "LEAKED\n", "utf8");
  writeFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-evil | bug-fix | when | stolen summary | ../../../OUTSIDE_SECRET.md |
| LESSON-20260101-good | bug-fix | when | safe summary | topics/bug-fix.md#LESSON-20260101-good |
`,
    "utf8",
  );
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
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

test("Q3A: five-event Trellis record => topic+index; no root lessons.md", () => {
  const root = fixtureRoot("trellis-five");
  trellisFixture(root);

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
    assert.equal(result.store, "trellis");
  }

  assert.equal(existsSync(join(root, "lessons.md")), false);
  assert.equal(
    existsSync(join(root, ".trellis", "spec", "lessons.md")),
    false,
  );
  assert.ok(existsSync(join(root, ".trellis", "lessons", "index.md")));
  for (const event of LESSON_EVENTS) {
    assert.ok(
      existsSync(join(root, ".trellis", "lessons", "topics", `${event}.md`)),
    );
  }
});

test("Q3A: no-Trellis record => docs/lessons.md", () => {
  const root = fixtureRoot("docs-flat");
  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "rollback", summary: "reverted bad deploy" },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.store, "docs");
  const path = join(root, "docs", "lessons.md");
  assert.ok(existsSync(path));
  const body = readFileSync(path, "utf8");
  assert.match(body, /## LESSON-/);
  assert.match(body, /rollback/);
});

test("Q3A: layered docs store when docs/lessons/index.md exists", () => {
  const root = fixtureRoot("docs-layered");
  mkdirSync(join(root, "docs", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, "docs", "lessons", "index.md"),
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
`,
    "utf8",
  );

  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "tool-misjudge", summary: "wrong gate" },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.store, "docs");
  assert.ok(existsSync(join(root, "docs", "lessons", "topics", "tool-misjudge.md")));
  assert.match(readFileSync(join(root, "docs", "lessons", "index.md"), "utf8"), /tool-misjudge/);
});

test("Q6A: match/read does not enumerate topics/archive (decoy ignored)", () => {
  const root = fixtureRoot("match-on-demand");
  trellisFixture(root);
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix | when fail | indexed only | topics/bug-fix.md#LESSON-20260101-bug-fix |
`,
    "utf8",
  );
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
    `# bug-fix

## LESSON-20260101-bug-fix

**event:** bug-fix
**summary:** indexed only
`,
    "utf8",
  );
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "secret.md"),
    "# secret decoy\n\nnot in index\n",
    "utf8",
  );
  mkdirSync(join(root, ".trellis", "lessons", "archive"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "archive", "old.md"),
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
    { intent: "match", event: "gitnexus-mismatch" },
    { cwd: root },
  );
  assert.equal(miss.status, "not-found");
  assert.deepEqual(miss.hits, []);
});

test("Q6A: lessons.ts never imports readdirSync (no topic walk)", () => {
  const src = readFileSync(
    join(import.meta.dirname, "..", "src", "tools", "lessons.ts"),
    "utf8",
  );
  assert.doesNotMatch(src, /readdirSync/);
  assert.doesNotMatch(src, /backends\/gitnexus/);
  assert.doesNotMatch(src, /from\s+["'].*gitnexus\.js["']/i);
});

test("gitnexus-mismatch record writes lesson without GitNexus import", () => {
  const root = fixtureRoot("gitnexus-event");
  const result = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "gitnexus-mismatch",
      summary: "impact under-reported",
    },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.ok(existsSync(join(root, "docs", "lessons.md")));
});

test("writeArtifact still task-dir whitelist only (T7 unchanged)", () => {
  const root = fixtureRoot("write-artifact");
  trellisFixture(root);
  mkdirSync(join(root, ".trellis", "tasks", "demo-task"), { recursive: true });

  const ok = writeArtifact(root, "demo-task", "prd.md", "# prd\n");
  assert.equal(ok.ok, true);

  assert.throws(
    () => writeArtifact(root, "demo-task", "lessons.md", "# lessons\n"),
    /name rejected \(not whitelisted\)/,
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
  trellisFixture(root);

  const recorded = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "bug-fix",
      summary: "round-trip summary",
      tags: ["trellis"],
    },
    { cwd: root },
  );
  assert.equal(recorded.ok, true);
  assert.equal(recorded.status, "recorded");

  const indexBody = readFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    "utf8",
  );
  assert.match(indexBody, /\| id \| tags \| read_when \| summary \| detail \|/);
  assert.match(
    indexBody,
    /\| LESSON-[^|]+ \| bug-fix, trellis \| *\| round-trip summary \| topics\/bug-fix\.md#LESSON-/,
  );

  const matched = sbtdLessons(
    "s1",
    { intent: "match", tags: ["trellis"] },
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
  trellisFixture(root);
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260903-dsh-sbtd | dsh-sbtd, t4 | when changing manuals | Copy only SKILL.md | topics/dsh-sbtd.md#lesson-anchor |
`,
    "utf8",
  );
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "dsh-sbtd.md"),
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
  const result = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "bug-fix",
      summary: "fixed docs/lessons.md",
      tags: ["trellis"],
    },
    { cwd: root },
  );
  assert.equal(result.ok, true);
  assert.equal(result.status, "recorded");
  assert.ok(existsSync(join(root, "docs", "lessons.md")));
});

test("R3: unqualified read returns index-only hits without bodies", () => {
  const root = fixtureRoot("r3-index-only-read");
  trellisFixture(root);
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix | | indexed only | topics/bug-fix.md#LESSON-20260101-bug-fix |
`,
    "utf8",
  );
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
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
  trellisFixture(root);
  mkdirSync(join(root, ".trellis", "lessons", "topics"), { recursive: true });
  writeFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-20260101-bug-fix | bug-fix, trellis | consult trellis gate docs | tag lesson | topics/bug-fix.md#LESSON-20260101-bug-fix |
`,
    "utf8",
  );
  writeFileSync(
    join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
    `# bug-fix

## LESSON-20260101-bug-fix

**event:** bug-fix
**summary:** tag lesson
`,
    "utf8",
  );

  const byTag = sbtdLessons(
    "s1",
    { intent: "match", tags: ["trellis"] },
    { cwd: root },
  );
  assert.equal(byTag.status, "matched");
  assert.equal(byTag.hits.length, 1);

  const byReadWhen = sbtdLessons(
    "s1",
    { intent: "match", tags: ["gate"] },
    { cwd: root },
  );
  assert.equal(byReadWhen.status, "matched");
  assert.equal(byReadWhen.hits.length, 1);
});

test("R5: symlink lessons store outside cwd refuses record", () => {
  const root = fixtureRoot("r5-symlink-store");
  trellisFixture(root);
  const outsideDir = mkdtempSync(join(tmpdir(), "dsh-sbtd-t14-outside-"));
  const outsideLessons = join(outsideDir, "lessons");
  mkdirSync(outsideLessons, { recursive: true });
  mkdirSync(join(outsideLessons, "topics"), { recursive: true });
  writeFileSync(join(outsideLessons, "index.md"), "# Lessons index\n", "utf8");

  const lessonsLink = join(root, ".trellis", "lessons");
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


test("R4 docs-flat: parseFlatSections unions event and user tags", () => {
  const root = fixtureRoot("r4-flat-event-tags");
  const recorded = sbtdLessons(
    "s1",
    {
      intent: "record",
      event: "bug-fix",
      summary: "flat event keep",
      tags: ["trellis"],
    },
    { cwd: root },
  );
  assert.equal(recorded.ok, true);
  assert.equal(recorded.status, "recorded");
  assert.ok(existsSync(join(root, "docs", "lessons.md")));

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
    { intent: "match", tags: ["trellis"] },
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

test("R5: symlink Trellis index.md outside cwd refuses match/read", () => {
  const root = fixtureRoot("r5-symlink-index-read");
  trellisFixture(root);
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
  trellisFixture(root);

  const poison = "line1\n## LESSON-forged\npipe|cell\n";
  const result = sbtdLessons(
    "s1",
    { intent: "record", event: "bug-fix", summary: poison },
    { cwd: root },
  );
  assert.equal(result.ok, true);

  const topicBody = readFileSync(
    join(root, ".trellis", "lessons", "topics", "bug-fix.md"),
    "utf8",
  );
  assert.doesNotMatch(topicBody, /## LESSON-forged/);
  assert.match(topicBody, /LESSON-forged/);

  const indexBody = readFileSync(
    join(root, ".trellis", "lessons", "index.md"),
    "utf8",
  );
  const dataLines = indexBody
    .split("\n")
    .filter((line) => line.trim().startsWith("| LESSON-"));
  assert.equal(dataLines.length, 1);
  const rawCells = dataLines[0].split("|").map((c) => c.trim());
  if (rawCells[0] === "") rawCells.shift();
  if (rawCells.at(-1) === "") rawCells.pop();
  assert.equal(rawCells.length, 5);
});

