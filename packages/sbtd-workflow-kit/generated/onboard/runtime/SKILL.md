---
name: sbtd-workflow-onboard
description: Checks, installs, or resets SBTD workflow tools, global Skills, AGENTS templates, and per-project configuration for one or more local project roots.
---

# SBTD Workflow Onboard Skills

Use this Skill to onboard a local machine and initialize one or more projects with the SBTD workflow templates bundled under `templates/`.

The repository root installers are `install.sh` and `install.ps1`. `scripts/onboard.py` is the shared implementation for checks, plans, template writes, global Skill installation, per-project checks, Trellis initialization, and bootstrap reporting.

The directory remains self-contained: `catalog.json` is the machine-readable source catalog, `catalog.schema.json` is its Draft 2020-12 contract, `scripts/` is the Onboard implementation, `templates/` is the install payload, and `assets/` contains managed third-party fallback snapshots. Keep this separation when adding catalog entries; do not move install payloads beside runtime code merely to flatten paths.

Do not install the source repository root `AGENTS.md`, `ENTRYPOINT.md`, `README.html`, `archive/`, or `docs/lessons.md` as target templates.

## Required Questions

Resolve these questions in order:

1. Which target Agent platform is being configured: `codex`, `claude`, `kimi`, or `oh-my-pi` / `omp`?
2. Is this a normal `init` / `reset`, or project-only initialization equivalent to `--init-projects`?
3. What are the project roots? Accept one or more existing absolute paths separated by English commas.
4. Should project `AGENTS.md` be installed into every selected project root?
5. If any selected root has no `.trellis/`, what Trellis developer username and optional Trellis platform flags should be used?
   Treat Trellis flags as a separate namespace: requested OMP uses `omp` and generates `--omp`; `pi` generates only `--pi`. Never substitute or infer one from the other, including from the Oh My Pi package name.

The Agent platform selects the CLI and MCP adapter; it does not select the global AGENTS target. Unless the user explicitly supplies a global AGENTS path, normal onboarding writes the Codex global template to the resolved `$CODEX_HOME/AGENTS.md` / `~/.codex/AGENTS.md` path. Project-only mode does not write any global AGENTS file.

If multiple paths are supplied to this Skill but the user did not explicitly say they are projects to initialize, ask whether they are the intended initialization roots before running checks or writes. Do not infer that every mentioned repository path should be initialized.

Normal `init` / `reset` always installs bundled and external workflow Skills globally. There is no global/project/none Skill scope choice. Project-only initialization must not check, install, update, or configure global Agent CLIs, runtimes, tools, Skills, AGENTS, or MCP.

## Skill Installation Modes

The official `skills` CLI may install this self-contained directory as the bootstrap Skill without cloning the whole repository first:

```bash
npx --yes skills@latest add \
  https://github.com/KunoLu/640-skills \
  --skill sbtd-workflow-onboard \
  --global \
  --agent codex \
  --yes \
  --copy
```

The `npx skills add` command installs only the `sbtd-workflow-onboard` package. It does not execute `scripts/onboard.py`, install Trellis or GitNexus, write AGENTS files, install the other bundled/external Skills, or initialize a project. After installation, invoke this Skill through the Agent and run `scripts/onboard.py plan --json`, `init`, or `reset` as required.


The repository root `install.sh` and `install.ps1` remain the complete interactive entrypoints when the repository is already cloned. Do not duplicate `templates/skills/**` at the repository root or add a second bootstrap Skill to accommodate the `skills` CLI; the top-level `SKILL.md` is the single discovery entrypoint.

## Root Installer Interfaces

Normal onboarding:

```bash
bash install.sh \
  --platform codex \
  --projects-root /abs/project-one,/abs/project-two \
  --action init
```

```powershell
.\install.ps1 \
  -Platform codex \
  -ProjectsRoot "C:\work\one,C:\work\two" \
  -Action init
```

Project-only initialization:

```bash
bash install.sh \
  --platform codex \
  --init-projects /abs/project-one,/abs/project-two
```

```powershell
.\install.ps1 \
  -Platform codex \
  -InitProjects "C:\work\one,C:\work\two"
```

`--projects-root` / `-ProjectsRoot` and `--init-projects` / `-InitProjects` are mutually exclusive. Every path must be absolute and must already be a directory. Duplicate paths are normalized and processed once.

When normal onboarding omits the `projects-root` argument, explain that multiple absolute paths are supported with English commas, ask whether the current working directory is a target project, and otherwise prompt for the comma-separated list. A blank answer means global-only onboarding.

## Target Agent CLI Gate

Normal onboarding resolves the target Agent first and immediately checks its CLI before collecting the remaining inputs:

| Platform | Verify | Required global npm package when missing |
|---|---|---|
| `codex` | `codex --version` | `@openai/codex@latest` |
| `claude` | `claude --version` | `@anthropic-ai/claude-code@latest` |
| `kimi` | `kimi --version` | `@moonshot-ai/kimi-code@latest` |
| `oh-my-pi` / `omp` | `omp --version` | `@oh-my-pi/pi-coding-agent@latest` |

If the target CLI is missing or broken, ensure npm is available, install the selected package globally, and require the version command to pass. If npm is missing but the target CLI already works, npm is still required because Trellis and GitNexus are mandatory global tools.

Project-only `--init-projects` asks for or accepts the platform but skips this Agent CLI/npm gate and every other global preflight.

## Mandatory Global Installation Policy

Normal `init` and `reset` require these global tools:

- Trellis CLI: `npm install -g @mindfoldhq/trellis@latest`
- GitNexus CLI: `npm install -g gitnexus@latest`

Project-local Trellis and GitNexus CLI installation is not supported. Trellis state under `.trellis/` and GitNexus indexes under `.gitnexus/` remain project-specific.

All bundled Skills install globally as one required set:

- `sbtd-workflow-onboard`
- `trellis-workflow`
- `trellis-channel`
- `project-validation`
- `web-ui-autotest-generator`
- `gherkin-bdd`
- `knowledge-base-integration`
- `maestro-mobile-e2e`
- `lessons-record`
- `book-refactoring-pass`
- `book-legacy-change-safety`
- `book-ddd-distilled-modeling`
- `book-ddia-data-design`
- `book-release-readiness`
- `seo-geo`

After the canonical `sbtd-workflow-onboard` target is written and its `SKILL.md` frontmatter validates, remove a legacy `kuno-workflow-onboard-skills` target only when that directory's own `SKILL.md` frontmatter still identifies it as `kuno-workflow-onboard-skills`. A conflicting file, unrelated directory, or mismatched frontmatter blocks `init` / `reset` before any target changes and remains untouched; deletion errors are reported as migration failures. This is a clean rename migration, not an alias: never retain both directories after a successful normal `init` or `reset`.

All referenced external Skills are also required globally. Install every missing item without a scope or selection prompt:

- `diagnosing-bugs`, `tdd`, `grill-me`, `grill-with-docs`, `grilling`
- `domain-modeling`, `codebase-design`, `handoff`, `writing-for-agents`
- `to-spec`, `to-tickets`, `ui-ux-pro-max`, `impeccable`
- `shadcn`

Dependencies are still expanded automatically: `tdd` includes `codebase-design`; `grill-me` includes `grilling`; `grill-with-docs` includes `grilling` and `domain-modeling`.

The mandatory runtime gate contracts are owned by the installed global `AGENTS.md`, project template, Trellis workflow, and bundled reviewer Skills. They become active only after normal `init` / `reset` successfully writes the global rules and installs the required bundled / external Skills. The public Skills CLI bootstrap and `init-projects` do not activate these runtime gates by themselves; they only install the Onboard Skill or process project-local assets respectively.

At runtime, every development task first produces a `Book Gate Plan` with objective predicates and lifecycle states. Every completed external `grill-with-docs` session invokes bundled `book-ddd-distilled-modeling`. Persisted/shared data, shared / persistent / cross-request / cross-process caches, async/cross-service flows, ownership, migrations, or recovery invoke `book-ddia-data-design`; existing-behavior bugs or uncertain existing code invoke `book-legacy-change-safety`; any existing-production-code edit invokes `book-refactoring-pass`; production-path runtime/deployment changes invoke `book-release-readiness` after all applicable testing-tool gates and project validation. Matched gates block their phase until passed; unmatched scenarios remain on demand.

External Skill installation uses a validated, stable-first source policy. The default `auto` policy and explicit `stable` policy both resolve every selected Skill from the reviewed vendored set under `assets/external-skills/stable/` without accessing Git or the network. Only explicit `upstream` opts into cloning and validating the current upstream repository group, and upstream failure does not fall back. Manifest, source-subpath, and license paths must stay contained by their declared roots. All selected Skills are staged before any target changes, and target replacement uses a temporary rollback transaction. Source-integrity and target-filesystem failures are fatal; an incomplete restore retains and reports the rollback directory.

The stable set is an unmodified mirror, not a fork. `assets/external-skills/stable/MANIFEST.json` records the exact upstream commit, source subpath, tree digest, and license files. Promote a new repository revision only through `promote-external-skills-stable`; promotion must validate the complete stable set before replacing it.

`caveman` remains a user-level global Skill with its existing explicit installation decision. Java 17+ and Maestro CLI remain local-machine prerequisites installed only after their existing conditional confirmation. RTK remains global with its existing confirmation and `rtk gain` verification behavior.

## Per-Project Processing

For every selected project root, normal `init` / `reset` and project-only `init-projects` independently:

1. Check whether project `AGENTS.md` should be installed.
2. Ensure every non-empty line from the bundled project `.gitignore` exists, appending only missing lines without reordering or duplicating existing project content.
3. Check whether `.trellis/` exists.
4. If missing and not explicitly skipped, require the global Trellis CLI and run `trellis init -u <username> ... --yes --skip-existing` in that project.
5. Check `.trellis/tasks/00-bootstrap-guidelines` after initialization.
6. If the bootstrap task exists, report `bootstrap-required` for that project and require a `trellis-workflow` handoff. Continue checking every other selected root before returning the aggregate status.
7. Check project Playwright applicability. Only offer project installation when an existing Playwright dependency/config/script or E2E directory makes it applicable.
8. Check React Bits only when the root is a React project and contains `components.json`.

Playwright CLI remains project-only and is installed with `install-playwright-cli --project-root <one-root> --yes` after confirmation.

React Bits remains project-only and optional:

- shadcn/ui-only is the default choice.
- React Bits Free requires an explicitly configured free registry item.
- Paid Starter / Pro / Ultimate setup requires an existing entitlement and a readable `REACTBITS_LICENSE_KEY`; install the Skill at `.agents/skills/react-bits-pro/SKILL.md`, overwriting that target without a backup, and never print or persist the key.
- Preserve a detected tier/registry during reset.

## MCP Scope Policy

MCP selection remains interactive and is skipped entirely in project-only mode. The built-in choices remain Chrome DevTools MCP, Playwright MCP, Maestro MCP, GitNexus MCP, and custom stdio MCP.

The target scope is fixed by Agent platform:

- Codex: user-level `codex mcp add` behavior.
- Claude Code: always `--scope user`.
- Kimi Code: keep the CLI default behavior; do not add a scope flag.
- Oh My Pi: always write the global `~/.omp/agent/mcp.json` file.

Do not couple MCP scope to project roots or Skill scope. Do not configure project-level Claude or Oh My Pi MCP entries during onboarding.

## Shared Python Commands

Global and multi-project check:

```bash
python scripts/onboard.py check \
  --projects-root /abs/project-one,/abs/project-two
```

Project-only check without global runtime/tool/Skill inspection:

```bash
python scripts/onboard.py check-projects \
  --projects-root /abs/project-one,/abs/project-two
```

Normal plan/init/reset:

```bash
python scripts/onboard.py plan --projects-root /abs/one,/abs/two
python scripts/onboard.py init --projects-root /abs/one,/abs/two --trellis-user your-name --yes
python scripts/onboard.py reset --projects-root /abs/one,/abs/two --trellis-user your-name --yes
```

Project-only initialization:

```bash
python scripts/onboard.py init-projects \
  --projects-root /abs/one,/abs/two \
  --trellis-user your-name \
  --yes
```

External Skill installation accepts global scope only:

```bash
python scripts/onboard.py install-external-skills --all --scope global --yes
```

Choose an explicit source policy when needed:

```bash
python scripts/onboard.py install-external-skills --all --scope global --source upstream --yes
python scripts/onboard.py install-external-skills --all --scope global --source stable --yes
```

Migrate every recognized mattpocock legacy directory in a global Skill root:

```bash
python scripts/onboard.py migrate-external-skills --scope global --source auto --yes
```

The migration validates each legacy `SKILL.md` identity before it changes any target, installs required canonical replacements transactionally, and then removes the verified legacy directories.

Promote a reviewed upstream repository revision into a new stable set:

```bash
python scripts/onboard.py promote-external-skills-stable \
  --repository mattpocock-skills \
  --revision <full-commit-sha> \
  --stable-set <yyyy-mm-dd.index> \
  --yes
```

## Reporting

Normal `check`, `init`, and `reset` report global runtime/tools/Skills plus a `projectChecks` entry for every selected root. `check-projects` and `init-projects` report only project-local checks and writes.

Aggregate Trellis status uses this priority: `failed`, `blocked`, `needs-user`, `bootstrap-required`, `success`, `skipped`. A bootstrap task in one project must not stop checks or initialization for the remaining roots.

Every External Skill install result must report `requestedSource`, `sourceUsed`, `sourceRevision`, `stableSet`, `fallbackReason`, and transaction status when applicable. Every project result must identify the affected project root. Do not merge failures, bootstrap tasks, Playwright applicability, or React Bits decisions across projects without preserving the root path.

See [REFERENCE.md](REFERENCE.md) for exact overwrite, backup, troubleshooting, and platform details.
