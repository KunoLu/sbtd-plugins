---
name: lessons-record
description: Use when a durable lesson should be recorded after bug fixes, rollbacks, tool misjudgments, workflow errors, failed validation, GitNexus mismatch, or multi-agent context loss.
---

# Lessons Recording Skill

Use this Skill when durable lessons learned need to be recorded.

## Default Recording Structure

Trellis projects use the following layered lessons structure by default:

- `.trellis/spec/lessons.md`: A short required-reading entry point that stores only high-priority summaries, the reading protocol, and index guidance.
- `.trellis/lessons/index.md`: Maintains an index by `id`, tags, applicable scenarios, and detail paths.
- `.trellis/lessons/topics/<topic>.md`: Stores lesson details organized by topic.
- `.trellis/lessons/archive/YYYY-QN.md`: Stores infrequently accessed historical archives and is not read by default.

When recording a lesson, write it to `.trellis/lessons/topics/<topic>.md` and update `.trellis/lessons/index.md` by default; synchronize a summary to `.trellis/spec/lessons.md` only if it occurs frequently across tasks and its absence would repeatedly cause errors. Do not accumulate the complete lesson history in `.trellis/spec/lessons.md` over the long term.

Do not write to other locations unless the user explicitly specifies another path. Only when it has been confirmed that the project does not use Trellis should the default location be `docs/lessons.md`.

If the project does not use Trellis, but the project-level `AGENTS.md`, `docs/lessons.md`, or README explicitly adopts a layered lessons structure, follow the project structure instead of falling back to writing to a single file. A common non-Trellis layered structure is:

- `docs/lessons.md`: A short required-reading entry point that stores only the reading protocol, topic routing, and high-frequency summaries.
- `docs/lessons/index.md`: Maintains an index by `id`, tags, applicable scenarios, and detail paths.
- `docs/lessons/topics/<topic>.md`: Stores complete lesson details.
- `docs/lessons/archive/YYYY-QN.md`: Stores infrequently accessed historical archives and is not read by default.

Under this structure, when writing a new lesson, both the topic details and the index must be updated; only summaries of lessons that occur frequently across tasks should also be synchronized to `docs/lessons.md`.

## Scenarios That Must Be Recorded

A lesson must be recorded when any of the following occurs:

- bug fixes
- rollbacks
- incorrect tool judgments
- mode-switching errors
- Trellis stage errors
- inappropriate parent / child task decomposition
- child tasks that cannot be independently validated
- task artifacts omitted during the check stage
- conflicts between task artifacts and `.trellis/spec`
- GitNexus impact analysis mismatches
- Channel / multi-Agent context loss
- recursive dispatch issues
- abnormal worker exits

---

## Recording Format

Use the following format for each lesson in a topic file:

```md
## LESSON-YYYYMMDD-<slug>: <short title>

- Date:
- Tags:
- Applicable scenarios:
- Severity:
- Source:
- Problem:
- Root cause:
- Fix:
- Prevention:
```

Use the following format for `index.md`:

```md
| id | tags | read_when | summary | detail |
|---|---|---|---|---|
| LESSON-YYYYMMDD-<slug> | tag-a, tag-b | When to read details | One-sentence summary | topics/<topic>.md#lesson-yyyymmdd-slug-short-title |
```

`.trellis/spec/lessons.md` stores only short summaries and the reading protocol, and should preferably remain within 150-200 lines. When it exceeds this range, first move infrequently accessed content into a topic or archive, then retain the index guidance.

## Writing Process

1. Determine whether it truly qualifies as a durable lesson; do not record ordinary task summaries, one-off implementation details, or temporary research.
2. Select a topic, such as `workflow`, `validation`, `shell`, `markdown`, `gitnexus`, `trellis-channel`, `ui`, or a project domain name.
3. Append the complete lesson to `.trellis/lessons/topics/<topic>.md`.
4. Add or update an index row in `.trellis/lessons/index.md`, ensuring that the tags, `read_when`, and detail path are searchable.
5. Only when the lesson represents a frequently occurring risk across tasks should a one-sentence prevention rule be synchronized to `.trellis/spec/lessons.md`.
6. When a topic file becomes too long or its content is infrequently accessed, retain the summary and index, and move the old details into `.trellis/lessons/archive/YYYY-QN.md`.

## Reading Boundaries

- When starting ordinary Trellis work, read only `.trellis/spec/lessons.md` by default.
- Do not read all of `.trellis/lessons/**` by default.
- Read the corresponding topic or archive only after a match is found based on the current task, error message, tool name, language, tags, or `read_when`.
- Do not read `archive/` by default; read it only for recurring issues, failed troubleshooting, user-requested traceability, or when the index explicitly points to it.