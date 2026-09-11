/**
 * sbtd_lessons (T14) — record / match / read durable project lessons.
 *
 * Locks: Q1A / Q2A / Q3A / Q4A / Q5A / Q6A.
 * Host injects cwd; model never supplies trust handles.
 * No GitNexus; no writeArtifact; no trellis init; no manuals nest.
 */

import {
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { detect } from "../backends/trellis.js";
import {
  type PlanToolExec,
  sessionIdFromExec,
  type ToolsHost,
} from "./plan.js";

export const SBTD_LESSONS_TOOL_NAME = "sbtd_lessons";

export const LESSON_INTENTS = ["record", "match", "read"] as const;
export type LessonIntent = (typeof LESSON_INTENTS)[number];

export const LESSON_EVENTS = [
  "bug-fix",
  "rollback",
  "tool-misjudge",
  "validation-fail",
  "gitnexus-mismatch",
] as const;
export type LessonEvent = (typeof LESSON_EVENTS)[number];

/** Model-visible args only (Q4A). */
export type LessonsInput = {
  intent: string;
  event?: string;
  summary?: string;
  tags?: string[];
  topic?: string;
};

export type LessonsHostOptions = { cwd?: string };

export type LessonsPluginHost = ToolsHost & {
  cwd?: string;
  lessonsHost?: LessonsHostOptions;
};

export type LessonHit = {
  id: string;
  tag: string;
  summary: string;
  topic: string;
  read_when: string;
  detail?: string;
  body?: string;
};

export type LessonsToolResult = {
  ok: boolean;
  intent: string;
  status: "recorded" | "skipped" | "matched" | "not-found" | "read";
  kind?: string;
  id?: string;
  path?: string;
  store?: "trellis" | "docs";
  hits?: LessonHit[];
  mutation: "none" | "write";
  note?: string;
};

export type LessonsToolDefinition = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  output: {
    schema: Record<string, unknown>;
    render: (
      args: unknown,
      value: LessonsToolResult,
    ) => Array<{ type: "text"; text: string }>;
  };
  isConcurrencySafe: (args: unknown) => boolean;
  execute: (
    args: LessonsInput,
    exec: PlanToolExec,
  ) => Promise<LessonsToolResult>;
};

const FORBIDDEN_MODEL_KEYS = [
  "cwd",
  "mcp",
  "runRefresh",
  "serverName",
  "toolNames",
] as const;

const SAFE_SLUG_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/;

export const SBTD_LESSONS_DESCRIPTION =
  "Record, match, or read durable project lessons. Five event kinds only (bug-fix, rollback, tool-misjudge, validation-fail, gitnexus-mismatch). Ordinary/unknown record is refused with no file write. Trellis present: .trellis/lessons/topics/<topic>.md + index.md. No Trellis: docs/lessons.md or docs/lessons/ layered store. Match/read are on-demand via index filters; never walks all topics/archive. No GitNexus; no writeArtifact; no trellis init.";

type IndexRow = {
  id: string;
  tags: string;
  read_when: string;
  summary: string;
  detail: string;
};

type StoreLayout =
  | {
      kind: "trellis";
      root: string;
      indexPath: string;
      topicsDir: string;
    }
  | {
      kind: "docs-layered";
      root: string;
      indexPath: string;
      topicsDir: string;
    }
  | {
      kind: "docs-flat";
      filePath: string;
    };

function isLessonIntent(value: string): value is LessonIntent {
  return (LESSON_INTENTS as readonly string[]).includes(value);
}

function isLessonEvent(value: string): value is LessonEvent {
  return (LESSON_EVENTS as readonly string[]).includes(value);
}

function hasUnsafePath(value: string): boolean {
  if (isAbsolute(value)) return true;
  if (value.includes("..")) return true;
  if (value.includes("/") || value.includes("\\")) return true;
  return false;
}

function isValidIndexTopic(topic: string): boolean {
  return SAFE_SLUG_RE.test(topic) && !hasUnsafePath(topic);
}

function isInsideRootLexical(parent: string, child: string): boolean {
  const p = resolve(parent);
  const c = resolve(child);
  if (p === c) return true;
  const rel = relative(p, c);
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
}

function tryRealpath(path: string): string | null {
  try {
    return realpathSync(path);
  } catch {
    return null;
  }
}

function projectThroughExistingAncestor(path: string): string | null {
  const resolved = resolve(path);
  if (existsSync(resolved)) {
    return tryRealpath(resolved);
  }
  let cursor = resolved;
  while (!existsSync(cursor)) {
    const parentDir = dirname(cursor);
    if (parentDir === cursor) break;
    cursor = parentDir;
  }
  if (!existsSync(cursor)) {
    return resolved;
  }
  const ancestorReal = tryRealpath(cursor);
  if (ancestorReal == null) return null;
  const suffix = relative(cursor, resolved);
  return suffix === "" ? ancestorReal : resolve(ancestorReal, suffix);
}

function isInsideRoot(parent: string, child: string): boolean {
  const parentProjected = projectThroughExistingAncestor(parent);
  const childProjected = projectThroughExistingAncestor(child);
  if (parentProjected == null || childProjected == null) return false;
  return isInsideRootLexical(parentProjected, childProjected);
}

function rejectSymlinkWriteTarget(
  absPath: string,
): { ok: true } | { ok: false; reason: string } {
  try {
    if (lstatSync(absPath).isSymbolicLink()) {
      return {
        ok: false,
        reason:
          "target-is-symlink: refusing to follow/overwrite a lessons symlink outside cwd (Q4A)",
      };
    }
  } catch {
    // ENOENT — final component absent; safe to create a new regular file.
  }
  return { ok: true };
}

function lessonPathAllowed(cwd: string, absPath: string): boolean {
  if (!isInsideRoot(cwd, absPath)) return false;
  return rejectSymlinkWriteTarget(absPath).ok;
}

function sanitizeCell(value: string): string {
  return value
    .replace(/\r?\n/g, " ")
    .replace(/\|/g, "/")
    .replace(/##\s*LESSON-/gi, "LESSON-")
    .trim();
}

function sanitizeTags(tags: string[] | undefined): string[] {
  if (tags == null) return [];
  return tags.map((t) => sanitizeCell(t)).filter(Boolean);
}

function buildTagsColumn(
  event: LessonEvent,
  tags: string[] | undefined,
): string {
  const parts: string[] = [event];
  const seen = new Set<string>([event]);
  for (const t of sanitizeTags(tags)) {
    if (!seen.has(t)) {
      parts.push(t);
      seen.add(t);
    }
  }
  return parts.join(", ");
}

function topicFromDetail(detail: string): string | null {
  const pathPart = detail.split("#")[0] ?? detail;
  const match = pathPart.match(/(?:^|\/)topics\/([^/]+)\.md$/);
  if (!match?.[1]) return null;
  const slug = match[1];
  return isValidIndexTopic(slug) ? slug : null;
}

function trellisPresent(cwd: string): boolean {
  const det = detect(cwd);
  return det.exists || det.workflowPresent;
}

function resolveStore(cwd: string, present: boolean): StoreLayout {
  if (present) {
    const root = join(cwd, ".trellis", "lessons");
    return {
      kind: "trellis",
      root,
      indexPath: join(root, "index.md"),
      topicsDir: join(root, "topics"),
    };
  }
  const layeredIndex = join(cwd, "docs", "lessons", "index.md");
  if (existsSync(layeredIndex)) {
    const root = join(cwd, "docs", "lessons");
    return {
      kind: "docs-layered",
      root,
      indexPath: layeredIndex,
      topicsDir: join(root, "topics"),
    };
  }
  return { kind: "docs-flat", filePath: join(cwd, "docs", "lessons.md") };
}

function readTextIfAllowed(cwd: string, absPath: string): string | null {
  if (!lessonPathAllowed(cwd, absPath)) return null;
  if (!existsSync(absPath)) return "";
  return readFileSync(absPath, "utf8");
}

function parseIndexRows(content: string): IndexRow[] {
  const rows: IndexRow[] = [];
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("|")) continue;
    if (trimmed.includes("---")) continue;
    const rawCells = trimmed.split("|").map((c) => c.trim());
    if (rawCells[0] === "") rawCells.shift();
    if (rawCells.at(-1) === "") rawCells.pop();
    if (rawCells.length < 5) continue;
    if (rawCells[0] === "id") continue;
    if (!rawCells[0]?.startsWith("LESSON-")) continue;
    const id = rawCells[0];
    const tags = rawCells[1] ?? "";
    const readWhen = rawCells[2] ?? "";
    const summary = rawCells[3] ?? "";
    const detail = rawCells[4] ?? "";
    rows.push({
      id,
      tags,
      read_when: readWhen,
      summary,
      detail,
    });
  }
  return rows;
}

function indexHeader(): string {
  return `# Lessons index

| id | tags | read_when | summary | detail |
|---|---|---|---|---|
`;
}

function ensureIndex(content: string): string {
  if (content.trim().length === 0) return indexHeader();
  return content.endsWith("\n") ? content : `${content}\n`;
}

function utcDateStamp(): string {
  return new Date().toISOString().slice(0, 10).replace(/-/g, "");
}

function nextLessonIdFromRows(topic: string, rows: IndexRow[]): string {
  const base = `LESSON-${utcDateStamp()}-${topic}`;
  const ids = new Set(rows.map((r) => r.id));
  if (!ids.has(base)) return base;
  let n = 2;
  while (ids.has(`${base}-${n}`)) n += 1;
  return `${base}-${n}`;
}

function nextLessonId(topic: string, indexContent: string): string {
  return nextLessonIdFromRows(topic, parseIndexRows(indexContent));
}

function resolveTopicSlug(
  input: LessonsInput,
  event: LessonEvent,
): string | null {
  if (input.topic != null && input.topic.trim() !== "") {
    const topic = input.topic.trim();
    if (hasUnsafePath(topic) || !SAFE_SLUG_RE.test(topic)) return null;
    return topic;
  }
  return event;
}

function formatTags(tags: string[] | undefined): string {
  if (tags == null || tags.length === 0) return "";
  return tags.join(", ");
}

function formatRecordSection(
  id: string,
  event: LessonEvent,
  topic: string,
  summary: string,
  tags: string[] | undefined,
): string {
  const lines = [`## ${id}`, "", `**event:** ${event}`, `**topic:** ${topic}`];
  if (summary.length > 0) lines.push(`**summary:** ${summary}`);
  const tagLine = formatTags(tags);
  if (tagLine.length > 0) lines.push(`**tags:** ${tagLine}`);
  lines.push("", "");
  return lines.join("\n");
}

function appendIndexRow(indexContent: string, row: IndexRow): string {
  const base = ensureIndex(indexContent);
  return `${base}| ${row.id} | ${row.tags} | ${row.read_when} | ${row.summary} | ${row.detail} |\n`;
}

function topicFileHeader(topic: string): string {
  return `# ${topic}\n\n`;
}

function extractSection(content: string, lessonId: string): string | null {
  const marker = `## ${lessonId}`;
  const idx = content.indexOf(marker);
  if (idx === -1) return null;
  const rest = content.slice(idx + marker.length);
  const next = rest.search(/\n## /);
  const body = (next === -1 ? rest : rest.slice(0, next)).trim();
  return body.length > 0 ? body : null;
}

function parseFlatSections(content: string, filePath: string): IndexRow[] {
  const rows: IndexRow[] = [];
  const re = /^## (LESSON-\d{8}-[^\s]+)/gm;
  let match = re.exec(content);
  while (match !== null) {
    const id = match[1];
    if (id === undefined) {
      match = re.exec(content);
      continue;
    }
    const body = extractSection(content, id) ?? "";
    const topicMatch = body.match(/\*\*topic:\*\*\s*(\S+)/);
    const topic = topicMatch?.[1]?.trim() ?? id.replace(/^LESSON-\d{8}-/, "");
    if (!isValidIndexTopic(topic)) {
      match = re.exec(content);
      continue;
    }
    const summaryMatch = body.match(/\*\*summary:\*\*\s*(.+)/);
    const eventMatch = body.match(/\*\*event:\*\*\s*(\S+)/);
    const tagsMatch = body.match(/\*\*tags:\*\*\s*(.+)/);
    const eventRaw = eventMatch?.[1]?.trim();
    const userTags = tagsMatch?.[1]
      ? tagsMatch[1]
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      : [];
    let tags: string;
    if (eventRaw != null && isLessonEvent(eventRaw)) {
      tags = buildTagsColumn(eventRaw, userTags);
    } else if (userTags.length > 0) {
      tags = userTags.join(", ");
    } else {
      tags = topic;
    }
    rows.push({
      id,
      tags,
      read_when: "",
      summary: summaryMatch?.[1]?.trim() ?? "",
      detail: filePath,
    });
    match = re.exec(content);
  }
  return rows;
}

function flatRowTopic(
  row: IndexRow,
  filePath: string,
  cwd: string,
): string | null {
  const content = readTextIfAllowed(cwd, filePath);
  if (content == null) {
    const fromId = row.id.replace(/^LESSON-\d{8}-/, "");
    return isValidIndexTopic(fromId) ? fromId : null;
  }
  const body = extractSection(content, row.id);
  if (body) {
    const topicMatch = body.match(/\*\*topic:\*\*\s*(\S+)/);
    if (topicMatch?.[1]) {
      const slug = topicMatch[1].trim();
      if (isValidIndexTopic(slug)) return slug;
    }
  }
  const fromId = row.id.replace(/^LESSON-\d{8}-/, "");
  return isValidIndexTopic(fromId) ? fromId : null;
}

function rowTopic(row: IndexRow, store: StoreLayout, cwd: string): string {
  if (store.kind === "docs-flat") {
    return flatRowTopic(row, store.filePath, cwd) ?? "";
  }
  return topicFromDetail(row.detail) ?? "";
}

function hasSelector(input: LessonsInput): boolean {
  if (input.event != null && input.event.trim() !== "") return true;
  if (input.topic != null && input.topic.trim() !== "") return true;
  if (input.summary != null && input.summary.trim() !== "") return true;
  if (input.tags != null) {
    for (const tag of input.tags) {
      if (tag.trim() !== "") return true;
    }
  }
  return false;
}

function rowMatchesFilters(
  row: IndexRow,
  input: LessonsInput,
  store: StoreLayout,
  cwd: string,
): boolean {
  if (input.event != null && input.event.trim() !== "") {
    const event = input.event.trim();
    const rowTags = row.tags.split(",").map((t) => t.trim());
    if (!rowTags.includes(event)) return false;
  }
  if (input.topic != null && input.topic.trim() !== "") {
    if (rowTopic(row, store, cwd) !== input.topic.trim()) return false;
  }
  if (input.summary != null && input.summary.trim() !== "") {
    const needle = input.summary.trim().toLowerCase();
    if (!row.summary.toLowerCase().includes(needle)) return false;
  }
  if (input.tags != null && input.tags.length > 0) {
    const rowTags = row.tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const readWhenLower = row.read_when.toLowerCase();
    for (const needle of input.tags) {
      const trimmed = needle.trim();
      if (trimmed === "") continue;
      const tagMatch = rowTags.includes(trimmed);
      const readWhenMatch = readWhenLower.includes(trimmed.toLowerCase());
      if (!tagMatch && !readWhenMatch) return false;
    }
  }
  return true;
}

function safeDetailPathForRow(
  store: StoreLayout,
  row: IndexRow,
  cwd: string,
): { ok: true; path: string } | { ok: false } {
  if (store.kind === "docs-flat") {
    if (!lessonPathAllowed(cwd, store.filePath)) return { ok: false };
    return { ok: true, path: store.filePath };
  }
  const topic = topicFromDetail(row.detail);
  if (topic == null) return { ok: false };
  const abs = resolve(store.topicsDir, `${topic}.md`);
  if (!isInsideRoot(cwd, abs)) return { ok: false };
  if (!isInsideRoot(store.root, abs)) return { ok: false };
  if (!lessonPathAllowed(cwd, abs)) return { ok: false };
  return { ok: true, path: abs };
}

function loadIndexRows(store: StoreLayout, cwd: string): IndexRow[] {
  if (store.kind === "docs-flat") {
    const text = readTextIfAllowed(cwd, store.filePath);
    if (text == null) return [];
    return parseFlatSections(text, store.filePath);
  }
  const text = readTextIfAllowed(cwd, store.indexPath);
  if (text == null) return [];
  return parseIndexRows(text);
}

function buildHit(
  row: IndexRow,
  store: StoreLayout,
  detailPath: string,
  cwd: string,
  body?: string,
): LessonHit {
  const hit: LessonHit = {
    id: row.id,
    tag: row.tags,
    summary: row.summary,
    topic: rowTopic(row, store, cwd),
    read_when: row.read_when,
    detail: detailPath,
  };
  if (body != null) hit.body = body;
  return hit;
}

function skipped(intent: string, kind: string): LessonsToolResult {
  return {
    ok: false,
    intent,
    status: "skipped",
    kind,
    mutation: "none",
  };
}

function recordLesson(
  cwd: string,
  input: LessonsInput,
  event: LessonEvent,
): LessonsToolResult {
  const topic = resolveTopicSlug(input, event);
  if (topic == null) return skipped("record", "unsafe-path");

  const present = trellisPresent(cwd);
  const store = resolveStore(cwd, present);
  const summary = sanitizeCell(input.summary?.trim() ?? "");
  const sanitizedTags = sanitizeTags(input.tags);

  if (store.kind === "docs-flat") {
    if (!lessonPathAllowed(cwd, store.filePath)) {
      return skipped("record", "unsafe-path");
    }
    mkdirSync(join(cwd, "docs"), { recursive: true });
    const existing = readTextIfAllowed(cwd, store.filePath);
    if (existing == null) return skipped("record", "unsafe-path");
    const id = nextLessonIdFromRows(
      topic,
      parseFlatSections(existing, store.filePath),
    );
    const section = formatRecordSection(
      id,
      event,
      topic,
      summary,
      sanitizedTags,
    );
    const prefix = existing.length === 0 ? `# Lessons\n\n` : "";
    writeFileSync(store.filePath, `${existing}${prefix}${section}`, "utf8");
    return {
      ok: true,
      intent: "record",
      status: "recorded",
      id,
      path: store.filePath,
      store: "docs",
      mutation: "write",
    };
  }

  if (!lessonPathAllowed(cwd, store.root)) {
    return skipped("record", "unsafe-path");
  }
  if (!lessonPathAllowed(cwd, store.indexPath)) {
    return skipped("record", "unsafe-path");
  }

  mkdirSync(store.topicsDir, { recursive: true });
  const indexContent = readTextIfAllowed(cwd, store.indexPath);
  if (indexContent == null) return skipped("record", "unsafe-path");
  const id = nextLessonId(topic, indexContent);
  const topicPath = join(store.topicsDir, `${topic}.md`);
  if (!lessonPathAllowed(cwd, topicPath)) {
    return skipped("record", "unsafe-path");
  }

  const topicExisting = readTextIfAllowed(cwd, topicPath);
  if (topicExisting == null) return skipped("record", "unsafe-path");
  const topicPrefix =
    topicExisting.length === 0
      ? topicFileHeader(topic)
      : topicExisting.endsWith("\n")
        ? topicExisting
        : `${topicExisting}\n`;
  const section = formatRecordSection(id, event, topic, summary, sanitizedTags);
  writeFileSync(topicPath, `${topicPrefix}${section}`, "utf8");

  const indexRow: IndexRow = {
    id,
    tags: buildTagsColumn(event, sanitizedTags),
    read_when: "",
    summary,
    detail: `topics/${topic}.md#${id}`,
  };
  writeFileSync(
    store.indexPath,
    appendIndexRow(indexContent, indexRow),
    "utf8",
  );

  return {
    ok: true,
    intent: "record",
    status: "recorded",
    id,
    path: topicPath,
    store: present ? "trellis" : "docs",
    mutation: "write",
  };
}

function queryLessons(
  cwd: string,
  input: LessonsInput,
  intent: "match" | "read",
): LessonsToolResult {
  if (input.topic != null && hasUnsafePath(input.topic)) {
    return skipped(intent, "unsafe-path");
  }

  const present = trellisPresent(cwd);
  const store = resolveStore(cwd, present);
  if (store.kind === "docs-flat") {
    if (!lessonPathAllowed(cwd, store.filePath)) {
      return skipped(intent, "unsafe-path");
    }
  } else if (
    !lessonPathAllowed(cwd, store.root) ||
    !lessonPathAllowed(cwd, store.indexPath)
  ) {
    return skipped(intent, "unsafe-path");
  }

  const rows = loadIndexRows(store, cwd).filter((row) =>
    rowMatchesFilters(row, input, store, cwd),
  );

  if (rows.length === 0) {
    return {
      ok: true,
      intent,
      status: "not-found",
      hits: [],
      mutation: "none",
    };
  }

  const hits: LessonHit[] = [];
  const indexOnlyRead = intent === "read" && !hasSelector(input);

  for (const row of rows) {
    const pathResult = safeDetailPathForRow(store, row, cwd);
    if (!pathResult.ok) continue;
    if (indexOnlyRead) {
      hits.push(buildHit(row, store, pathResult.path, cwd));
      continue;
    }
    if (intent === "read") {
      const topicText = readTextIfAllowed(cwd, pathResult.path);
      if (topicText == null) continue;
      const body = extractSection(topicText, row.id);
      hits.push(
        buildHit(
          row,
          store,
          pathResult.path,
          cwd,
          body != null ? body : undefined,
        ),
      );
      continue;
    }
    hits.push(buildHit(row, store, pathResult.path, cwd));
  }

  if (hits.length === 0) {
    return {
      ok: true,
      intent,
      status: "not-found",
      hits: [],
      mutation: "none",
    };
  }

  return {
    ok: true,
    intent,
    status: indexOnlyRead ? "matched" : intent === "read" ? "read" : "matched",
    hits,
    store: present ? "trellis" : "docs",
    mutation: "none",
  };
}

export function pickLessonsInput(args: unknown): LessonsInput {
  const src =
    args != null && typeof args === "object"
      ? (args as Record<string, unknown>)
      : {};
  for (const key of FORBIDDEN_MODEL_KEYS) {
    if (Object.hasOwn(src, key)) {
      throw new Error(
        `sbtd_lessons model input forbids trust handle "${key}" (host-injected only)`,
      );
    }
  }
  const out: LessonsInput = {
    intent: typeof src.intent === "string" ? src.intent : "",
  };
  if (typeof src.event === "string") out.event = src.event;
  if (typeof src.summary === "string") out.summary = src.summary;
  if (typeof src.topic === "string") out.topic = src.topic;
  if (Array.isArray(src.tags)) {
    out.tags = src.tags.filter((t): t is string => typeof t === "string");
  }
  return out;
}

export function modelSchemaForbidsTrustHandles(
  parameters: Record<string, unknown>,
): boolean {
  const props = parameters.properties as Record<string, unknown> | undefined;
  if (props == null) return false;
  for (const key of FORBIDDEN_MODEL_KEYS) {
    if (Object.hasOwn(props, key)) return false;
  }
  return true;
}

export function resolveLessonsHost(ctx: LessonsPluginHost): LessonsHostOptions {
  const explicit = ctx.lessonsHost ?? {};
  const cwd =
    typeof explicit.cwd === "string" && explicit.cwd.length > 0
      ? explicit.cwd
      : typeof ctx.cwd === "string" && ctx.cwd.length > 0
        ? ctx.cwd
        : process.cwd();
  return { cwd };
}

export function sbtdLessons(
  _sessionId: string,
  input: LessonsInput,
  host: LessonsHostOptions = {},
): LessonsToolResult {
  const cwd = host.cwd ?? process.cwd();
  const intent = input.intent;

  if (!isLessonIntent(intent)) {
    return skipped(intent, "unknown-intent");
  }

  if (intent === "record") {
    const event = input.event?.trim() ?? "";
    if (!isLessonEvent(event)) {
      return skipped("record", "ordinary-or-unknown");
    }
    return recordLesson(cwd, input, event);
  }

  return queryLessons(cwd, input, intent);
}

export function createLessonsTool(
  host: LessonsHostOptions = {},
): LessonsToolDefinition {
  return {
    name: SBTD_LESSONS_TOOL_NAME,
    description: SBTD_LESSONS_DESCRIPTION,
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        intent: {
          type: "string",
          enum: [...LESSON_INTENTS],
          description:
            "record = append a lesson; match = query index rows; read = match plus section body.",
        },
        event: {
          type: "string",
          enum: [...LESSON_EVENTS],
          description:
            "Lesson event kind (required for record; optional filter for match/read).",
        },
        summary: {
          type: "string",
          description:
            "Short lesson summary (record) or substring filter (match/read).",
        },
        tags: {
          type: "array",
          items: { type: "string" },
          description: "Optional tag list (record metadata or match filter).",
        },
        topic: {
          type: "string",
          description:
            "Topic slug (defaults to event on record; optional filter for match/read).",
        },
      },
      required: ["intent"],
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          ok: { type: "boolean" },
          intent: { type: "string" },
          status: { type: "string" },
          kind: { type: "string" },
          id: { type: "string" },
          path: { type: "string" },
          store: { type: "string" },
          hits: { type: "array" },
          mutation: { type: "string" },
          note: { type: "string" },
        },
      },
      render(_args, value) {
        const lines = [
          `intent: ${value.intent}`,
          `status: ${value.status}`,
          `mutation: ${value.mutation}`,
        ];
        if (value.kind != null) lines.push(`kind: ${value.kind}`);
        if (value.id != null) lines.push(`id: ${value.id}`);
        if (value.path != null) lines.push(`path: ${value.path}`);
        if (value.store != null) lines.push(`store: ${value.store}`);
        if (value.hits != null) lines.push(`hits: ${value.hits.length}`);
        if (value.note != null) lines.push("", value.note);
        return [{ type: "text", text: lines.join("\n") }];
      },
    },
    isConcurrencySafe(args) {
      const picked = pickLessonsInput(args);
      return picked.intent === "match" || picked.intent === "read";
    },
    async execute(args, exec) {
      const modelArgs = pickLessonsInput(args);
      return sbtdLessons(sessionIdFromExec(exec), modelArgs, host);
    },
  };
}

export function registerLessonsTool(
  ctx: ToolsHost,
  host: LessonsHostOptions = {},
): void {
  ctx.tools.register(createLessonsTool(host));
}
